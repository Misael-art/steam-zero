# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Instalação de pacotes de tema via URL ou caminho local."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from steamzero.core import fs, ids, log, paths
from steamzero.core.errors import SteamZeroError
from steamzero.core.net import HttpClient, NetworkPolicy, RetryPolicy, fetch_bytes
from steamzero.core.safezip import SafeZipLimits, extract_safe
from steamzero.domain.themes import ThemeManifest, validate_theme_manifest

THEME_PACKAGE_MAX = 64 * 1024 * 1024
_THEME_EXTRACT_LIMITS = SafeZipLimits(
    max_entries=128,
    max_total_bytes=THEME_PACKAGE_MAX,
    max_entry_bytes=16 * 1024 * 1024,
    max_depth=8,
)


def _confirm_size(url: str, content_length: int | None) -> None:
    if content_length is not None and content_length > 5 * 1024 * 1024:
        raise SteamZeroError(
            "E-THEME-DOWNLOAD-FAILED",
            detail=(
                f"o pacote tem {content_length / 1024 / 1024:.1f} MiB. "
                "Use --yes para confirmar o download."
            ),
        )


class ThemeInstaller:
    def __init__(
        self,
        validate: Callable[[Path], ThemeManifest] | None = None,
    ) -> None:
        self._validate = validate

    def install(
        self,
        source: str,
        *,
        force: bool = False,
        yes: bool = False,
        checksum_sha256: str | None = None,
        http_client: HttpClient | None = None,
    ) -> dict[str, str]:
        op_id = ids.new_ulid()
        parsed = urllib.parse.urlparse(source)
        is_url = parsed.scheme in ("http", "https")

        if is_url:
            if not yes:
                self._check_size(source, http_client=http_client)
            zip_bytes = self._download(source, http_client=http_client)
            if checksum_sha256:
                digest = hashlib.sha256(zip_bytes).hexdigest()
                if digest != checksum_sha256:
                    raise SteamZeroError(
                        "E-CONTENT-INCOMPLETE",
                        detail="checksum SHA-256 do pacote não confere",
                    )
        elif Path(source).is_file():
            zip_bytes = Path(source).read_bytes()
        else:
            raise SteamZeroError(
                "E-THEME-DOWNLOAD-FAILED",
                detail=f"origem inválida: {source}",
            )

        zip_path = paths.staging_for(op_id) / "package.zip"
        fs.write_atomic(zip_path, zip_bytes)

        extract_op_id = f"{op_id}-ext"
        extract_safe(zip_path, extract_op_id, limits=_THEME_EXTRACT_LIMITS)

        extract_dir = paths.staging_for(extract_op_id)
        theme_dir = self._find_theme_dir(extract_dir)
        if theme_dir is None:
            fs.remove_tree(paths.staging_for(op_id))
            fs.remove_tree(extract_dir)
            raise SteamZeroError(
                "E-THEME-MANIFEST",
                detail="o pacote não contém um theme.json na raiz",
            )

        try:
            manifest_path = theme_dir / "theme.json"
            if manifest_path.stat().st_size > 256 * 1024:
                raise ValueError("manifesto excede 256 KiB")
            raw = json.loads(manifest_path.read_bytes())
            validate_theme_manifest(raw)
            manifest = ThemeManifest.from_dict(raw)
            if self._validate is not None:
                manifest = self._validate(theme_dir)
            if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", manifest.id):
                raise ValueError("identidade de tema inválida")
        except (OSError, ValueError, TypeError, SteamZeroError) as exc:
            fs.remove_tree(paths.staging_for(op_id))
            fs.remove_tree(extract_dir)
            if isinstance(exc, SteamZeroError):
                raise
            raise SteamZeroError("E-THEME-MANIFEST", detail=str(exc)[:400]) from exc

        target = paths.themes_dir() / manifest.id
        if target.exists() and not force:
            fs.remove_tree(paths.staging_for(op_id))
            fs.remove_tree(extract_dir)
            raise SteamZeroError(
                "E-THEME-DOWNLOAD-FAILED",
                detail=f"tema '{manifest.id}' já instalado. Use --force para sobrescrever.",
            )
        # Resolve/ingest masters before replacing anything. Transport sources
        # are removed from staging, never copied into each installed consumer.
        self._ingest_sources(theme_dir, manifest)
        staged = target.parent / f".{manifest.id}.stage.{op_id.lower()}"
        publishing = False
        published = False
        try:
            fs.move_tree(theme_dir, staged)
            publishing = True
            fs.publish_tree(staged, target, replace_existing=force)
            published = True
        finally:
            if staged.exists() and (not publishing or published):
                fs.remove_tree(staged)
        fs.remove_tree(paths.staging_for(op_id))
        fs.remove_tree(extract_dir)

        return {
            "themeId": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
        }

    @staticmethod
    def _ingest_sources(theme_dir: Path, manifest: ThemeManifest) -> None:
        from steamzero.domain.media_pipeline import MediaPipeline
        from steamzero.domain.media_registry import MediaRegistry, MediaSource

        transport = theme_dir / "media-sources"
        for reference in sorted(set(manifest.assets.values())):
            if not reference.startswith("master:"):
                continue
            if not re.fullmatch(r"master:sha256:[a-f0-9]{64}", reference):
                raise SteamZeroError("E-THEME-UNSAFE", detail="referência de master inválida")
            digest = reference[14:]
            record = transport / f"{digest}.json"
            if not record.exists():
                MediaRegistry.resolve_source(paths.media_dir(), digest)
                continue
            try:
                if record.is_symlink() or record.stat().st_size > 8192:
                    raise ValueError("metadados de master inválidos")
                source = MediaSource.from_dict(json.loads(record.read_text(encoding="utf-8")))
                if source.digest != digest:
                    raise ValueError("identidade de master divergente")
                master = transport / f"{digest}.{source.format}"
                if master.is_symlink() or master.stat().st_size != source.size:
                    raise ValueError("tamanho de master divergente")
                MediaPipeline(paths.media_dir()).preserve_source(
                    master.read_bytes(),
                    source.filename,
                    source.provenance,
                    expected_source=source,
                )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise SteamZeroError(
                    "E-CONTENT-INCOMPLETE", detail="master do pacote inválido"
                ) from exc
        if transport.exists():
            fs.remove_tree(transport)

    def _check_size(self, url: str, *, http_client: HttpClient | None = None) -> None:
        try:
            # A allowlist é derivada do próprio host pedido, como em
            # ``core.net.fetch_bytes``: impede que um redirect leve a sondagem
            # para outro host. Curinga aqui anularia a fronteira de rede.
            host = (urllib.parse.urlsplit(url).hostname or "").casefold().rstrip(".")
            if not host:
                return
            policy = NetworkPolicy(
                allowed_hosts=frozenset({host}),
                timeout_seconds=15.0,
                max_bytes=1,
                retry=RetryPolicy(attempts=1),
            )
            client = http_client or HttpClient()
            resp = client.get(url, policy=policy)
            raw = resp.headers.get("Content-Length")
            if raw is not None:
                _confirm_size(url, int(raw))
        except SteamZeroError:
            raise
        except Exception:
            log.get_logger().warning("theme_install.head-failed", url=url)

    def _download(
        self,
        url: str,
        *,
        http_client: HttpClient | None = None,
    ) -> bytes:
        return fetch_bytes(
            url,
            max_bytes=THEME_PACKAGE_MAX,
            client=http_client,
        )

    def _find_theme_dir(self, extract_dir: Path) -> Path | None:
        if not extract_dir.is_dir():
            return None
        entries = sorted(extract_dir.iterdir())
        for entry in entries:
            if entry.is_dir() and (entry / "theme.json").is_file():
                return entry
        if (extract_dir / "theme.json").is_file():
            return extract_dir
        return None
