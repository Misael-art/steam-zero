from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from steamzero.core import fs
from steamzero.core.errors import SteamZeroError


@dataclass(frozen=True)
class PlatformEntry:
    slug: str
    name: str
    kinds: tuple[str, ...] = ("box2d", "hero", "logo", "icon", "screenshot")


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_url: str
    license: str = ""
    attribution: str = ""
    downloaded_at: str = ""
    hash_sha256: str = ""


@dataclass(frozen=True)
class MediaSource:
    """Preserved artwork identity; assignments, recipes and caches are separate."""

    digest: str
    path: str
    filename: str
    format: str
    width: int
    height: int
    has_alpha: bool
    size: int
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.digest, str) or not re.fullmatch(r"[a-f0-9]{64}", self.digest):
            raise ValueError("identidade de fonte inválida")
        if self.format not in {"png", "jpeg", "webp", "avif"}:
            raise ValueError("formato de fonte não publicado")
        if self.path != f"masters/sources/{self.digest}.{self.format}":
            raise ValueError("caminho de fonte inválido")
        if (
            not isinstance(self.filename, str)
            or not self.filename
            or len(self.filename) > 256
            or Path(self.filename).name != self.filename
            or "\\" in self.filename
            or any(ord(c) < 32 for c in self.filename)
        ):
            raise ValueError("nome de fonte inválido")
        for value in (self.width, self.height):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8192:
                raise ValueError("dimensão de fonte fora de 1..8192")
        if self.width * self.height > 32 * 1024 * 1024:
            raise ValueError("fonte excede 32 megapixels")
        if not isinstance(self.has_alpha, bool):
            raise ValueError("alpha de fonte inválido")
        if (
            isinstance(self.size, bool)
            or not isinstance(self.size, int)
            or not 0 < self.size <= 16 * 1024 * 1024
        ):
            raise ValueError("fonte vazia ou acima de 16 MiB")
        if not isinstance(self.provenance, Provenance):
            raise ValueError("procedência de fonte inválida")
        for value in asdict(self.provenance).values():
            if not isinstance(value, str) or len(value) > 1024 or any(ord(c) < 32 for c in value):
                raise ValueError("procedência de fonte inválida")
        if not self.provenance.license.strip() or self.provenance.hash_sha256 != self.digest:
            raise ValueError("declare licença e identidade da fonte")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> MediaSource:
        payload = dict(raw)
        payload["provenance"] = Provenance(**payload["provenance"])
        return MediaSource(**payload)


def _source_path(root: Path, relative: str) -> Path:
    """Canonical source storage never follows links, including its parents."""
    candidate = root
    for part in Path(relative).parts:
        candidate /= part
        if candidate.is_symlink():
            raise SteamZeroError("E-CONTENT-UNSAFE-PATH", detail="link na fonte canônica")
    fs.resolve_within(root, candidate)
    return candidate


def _source_record(root: Path, digest: str) -> Path:
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise SteamZeroError("E-API-SCHEMA", detail="identidade de fonte inválida")
    return _source_path(root, f"registry/sources-v1/{digest}.json")


def _publish_source_bytes(target: Path, data: bytes) -> None:
    temporary = fs.write_tmp(target.parent, data)
    try:
        fs.publish_link(temporary, target)
    except FileExistsError:
        if target.is_symlink() or target.read_bytes() != data:
            raise SteamZeroError(
                "E-CONTENT-INCOMPLETE", detail="fonte canônica divergente"
            ) from None
    finally:
        fs.discard_tmp(temporary)


@dataclass(frozen=True)
class MediaMasterEntry:
    game_id: str
    title_id: str
    fingerprint: str
    canonical_name: str
    platform_id: str = ""
    aliases: tuple[str, ...] = ()
    region: str = ""
    language: str = ""
    version: str = ""
    metadata_origin: str = ""
    confirmed: bool = False
    steam_appid: int | None = None
    provenance: Provenance | None = None
    masters: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "gameId": self.game_id,
            "titleId": self.title_id,
            "fingerprint": self.fingerprint,
            "canonicalName": self.canonical_name,
            "platformId": self.platform_id,
            "aliases": list(self.aliases),
            "region": self.region,
            "language": self.language,
            "version": self.version,
            "metadataOrigin": self.metadata_origin,
            "confirmed": self.confirmed,
            "steamAppid": self.steam_appid,
            "masters": dict(sorted(self.masters.items())),
        }
        if self.provenance:
            d["provenance"] = {
                "provider": self.provenance.provider,
                "sourceUrl": self.provenance.source_url,
                "license": self.provenance.license,
                "attribution": self.provenance.attribution,
                "downloadedAt": self.provenance.downloaded_at,
                "hashSha256": self.provenance.hash_sha256,
            }
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MediaMasterEntry:
        prov_data = d.get("provenance")
        provenance = None
        if prov_data:
            provenance = Provenance(
                provider=prov_data.get("provider", ""),
                source_url=prov_data.get("sourceUrl", ""),
                license=prov_data.get("license", ""),
                attribution=prov_data.get("attribution", ""),
                downloaded_at=prov_data.get("downloadedAt", ""),
                hash_sha256=prov_data.get("hashSha256", ""),
            )
        return MediaMasterEntry(
            game_id=d.get("gameId", ""),
            title_id=d.get("titleId", ""),
            fingerprint=d.get("fingerprint", ""),
            canonical_name=d.get("canonicalName", ""),
            # Registros v1 não carregavam plataforma. A ausência fica
            # explicitamente desconhecida; não inventamos Switch numa API
            # genérica.
            platform_id=d.get("platformId", ""),
            aliases=tuple(d.get("aliases", [])),
            region=d.get("region", ""),
            language=d.get("language", ""),
            version=d.get("version", ""),
            metadata_origin=d.get("metadataOrigin", ""),
            confirmed=d.get("confirmed", False),
            steam_appid=d.get("steamAppid"),
            provenance=provenance,
            masters={
                str(kind): str(path)
                for kind, path in d.get("masters", {}).items()
                if isinstance(kind, str) and isinstance(path, str)
            }
            if isinstance(d.get("masters", {}), dict)
            else {},
        )


@dataclass
class MediaRegistry:
    platforms: dict[str, PlatformEntry] = field(default_factory=dict)
    entries: dict[str, MediaMasterEntry] = field(default_factory=dict)

    @staticmethod
    def read_source(root: Path, digest: str) -> MediaSource | None:
        record = _source_record(root, digest)
        if not record.exists():
            return None
        try:
            if record.stat().st_size > 8192:
                raise ValueError("registro acima de 8192 bytes")
            source = MediaSource.from_dict(json.loads(record.read_text(encoding="utf-8")))
            if source.digest != digest:
                raise ValueError("identidade divergente")
            return source
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SteamZeroError(
                "E-CONTENT-INCOMPLETE", detail="registro de fonte inválido"
            ) from exc

    @staticmethod
    def sources(root: Path) -> Iterator[MediaSource]:
        folder = _source_path(root, "registry/sources-v1")
        if folder.is_dir():
            for record in sorted(folder.glob("*.json")):
                source = MediaRegistry.read_source(root, record.stem)
                if source is not None:
                    yield source

    @staticmethod
    def resolve_source(root: Path, digest: str) -> Path:
        source = MediaRegistry.read_source(root, digest)
        if source is None:
            raise SteamZeroError(
                "E-CONTENT-INCOMPLETE", detail="master ausente; importe a fonte preservada"
            )
        target = _source_path(root, source.path)
        try:
            if not target.is_file() or target.stat().st_size != source.size:
                raise ValueError("master ausente ou tamanho divergente")
            if hashlib.sha256(target.read_bytes()).hexdigest() != source.digest:
                raise ValueError("hash do master divergente")
        except (OSError, ValueError) as exc:
            raise SteamZeroError("E-CONTENT-INCOMPLETE", detail=str(exc)) from exc
        return target.resolve()

    @staticmethod
    def publish_source(root: Path, source: MediaSource, data: bytes) -> MediaSource:
        if len(data) != source.size or hashlib.sha256(data).hexdigest() != source.digest:
            raise SteamZeroError("E-CONTENT-INCOMPLETE", detail="identidade do master divergente")
        existing = MediaRegistry.read_source(root, source.digest)
        if existing is not None:
            # Renaming a file does not change its artwork. A conflicting rights
            # declaration must be reviewed instead of replacing provenance.
            if replace(existing.provenance, downloaded_at="") != replace(
                source.provenance, downloaded_at=""
            ):
                raise SteamZeroError(
                    "E-API-SCHEMA", detail="procedência divergente para o mesmo master"
                )
            try:
                MediaRegistry.resolve_source(root, existing.digest)
            except SteamZeroError as exc:
                if exc.code != "E-CONTENT-INCOMPLETE":
                    raise
                # The caller supplied the decoded, hash-verified original.
                # Repair only this owned identity; metadata and references stay intact.
                target = _source_path(root, existing.path)
                fs.write_atomic(target, data)
                MediaRegistry.resolve_source(root, existing.digest)
            return existing
        encoded = (json.dumps(source.to_dict(), ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        if len(encoded) > 8192:
            raise SteamZeroError("E-CONTENT-LIMIT", detail="procedência acima de 8192 bytes")
        _publish_source_bytes(_source_path(root, source.path), data)
        _publish_source_bytes(_source_record(root, source.digest), encoded)
        return source

    @staticmethod
    def load(root: Path) -> MediaRegistry:
        reg_path = root / "registry" / "platforms-v1.json"
        entries_path = root / "registry" / "assignments-v1.json"
        registry = MediaRegistry()
        if reg_path.is_file():
            data = json.loads(reg_path.read_text(encoding="utf-8"))
            for slug, pdata in data.get("platforms", {}).items():
                registry.platforms[slug] = PlatformEntry(
                    slug=slug,
                    name=pdata.get("name", slug),
                    kinds=tuple(pdata.get("kinds", [])),
                )
        if entries_path.is_file():
            data = json.loads(entries_path.read_text(encoding="utf-8"))
            for entry_dict in data.get("entries", []):
                entry = MediaMasterEntry.from_dict(entry_dict)
                registry.entries[entry.game_id] = entry
        return registry

    def save(self, root: Path) -> None:
        fs.ensure_dir(root)
        reg_path = root / "registry"
        fs.ensure_dir(reg_path)
        platform_data = {
            slug: {"name": p.name, "kinds": list(p.kinds)} for slug, p in self.platforms.items()
        }
        fs.write_atomic_text(
            reg_path / "platforms-v1.json",
            json.dumps({"platforms": platform_data}, indent=2, ensure_ascii=False),
        )
        entries_list = [e.to_dict() for e in self.entries.values()]
        fs.write_atomic_text(
            reg_path / "assignments-v1.json",
            json.dumps({"entries": entries_list}, indent=2, ensure_ascii=False),
        )

    @staticmethod
    def assignments_bytes(entries: dict[str, MediaMasterEntry]) -> bytes:
        """Renderiza o registro para entrar em um plano transacional.

        A migração de layout não pode mover o master e atualizar a referência
        em duas operações independentes: uma queda entre elas deixaria o
        registry apontando para um caminho inexistente. O núcleo transacional
        aplica e reverte ambos no mesmo journal.
        """
        entries_list = [entries[game_id].to_dict() for game_id in sorted(entries)]
        return (json.dumps({"entries": entries_list}, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )

    def register_platform(self, slug: str, name: str, kinds: tuple[str, ...]) -> None:
        self.platforms[slug] = PlatformEntry(slug=slug, name=name, kinds=kinds)

    def add_entry(self, entry: MediaMasterEntry) -> None:
        self.entries[entry.game_id] = entry

    def get_entry(self, game_id: str) -> MediaMasterEntry | None:
        return self.entries.get(game_id)

    def remove_entry(self, game_id: str) -> None:
        self.entries.pop(game_id, None)
