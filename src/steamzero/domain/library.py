# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Library: scan, organização transacional, import, dedupe e multidisco.

- Scan: leitura pura (hash blake2b + classificação); NUNCA escreve fora do state
  (AC-LB-01).
- Import: cópia com verificação de hash; a origem NUNCA é alterada (import é
  cópia — RT-07/AC-LB-02). Dedupe por hash. Archive passa por safezip; inseguro =>
  staging limpo + E-CONTENT-UNSAFE-ARCHIVE, origem intocada (AC-LB-03).
- Multidisco: agrupa "(Disc N)" no mesmo multi_disc_group.
- Organização: scan→plan→apply→verify→commit, com confirmação e rollback
  byte-idêntico pelo núcleo transacional (M7/G-FULL).
- Scan multi-plataforma (D1): PlatformRomScanner classifica ROMs por extensão,
  pareamento .bin+.cue e exclusividade sem ler o arquivo.

Conteúdo é sempre do usuário (CONTENT-POLICY): nada é obtido, sugerido ou baixado.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steamzero.core import fs, ids, paths, safezip, transaction
from steamzero.core.errors import SteamZeroError
from steamzero.core.state import StateStore

_DISC_RE = re.compile(r"\s*\((?:disc|disk)\s*(\d+)\)", re.IGNORECASE)

_FORMAT_BY_EXT = {
    ".chd": "chd",
    ".rvz": "rvz",
    ".iso": "iso",
    ".cue": "cue",
    ".bin": "bin",
    ".m3u": "m3u",
    ".zip": "zip",
    ".7z": "7z",
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".gba": "gba",
    ".nds": "nds",
    ".gcm": "gcm",
    ".wbfs": "wbfs",
    ".wad": "wad",
    ".ciso": "ciso",
    ".gcz": "gcz",
    ".pbp": "pbp",
    ".nsp": "nsp",
    ".nsz": "nsz",
    ".xci": "xci",
    ".xcz": "xcz",
    ".nca": "nca",
    ".nro": "nro",
    ".gb": "gb",
    ".gbc": "gbc",
    ".fds": "fds",
    ".unf": "unf",
    ".fig": "fig",
    ".md": "md",
    ".gen": "gen",
    ".32x": "32x",
}


def detect_format(name: str) -> str:
    return _FORMAT_BY_EXT.get(Path(name).suffix.lower(), "unknown")


def build_ext_map(
    manifests: Sequence[dict[str, Any]],
) -> dict[str, list[str]]:
    ext_map: dict[str, list[str]] = {}
    for manifest in manifests:
        platform_id = manifest["id"]
        for ext in manifest.get("media", {}).get("extensions", []):
            key = f".{ext.lower()}"
            ext_map.setdefault(key, []).append(platform_id)
    return ext_map


def classify_rom(
    name: str,
    siblings: set[str],
    ext_map: Mapping[str, Sequence[str]],
    *,
    root_platform: str | None = None,
) -> tuple[str | None, str, str]:
    """Pure classifier: (platform_id|None, content_kind, evidence).

    Regras D1 executadas em ordem de precedência:

    1. *root configurado vence* — se ``root_platform`` está definido e a
       extensão é reconhecida por alguma plataforma, o resultado é
       ``root_platform`` independentemente de ambiguidade.
    2. Arquivos .zip e .7z → sempre unknown (archives, não ROMs).
    3. Arquivos .cue com par .bin no mesmo diretório → PlayStation.
    4. .cue sem .bin → unknown (tracklist órfã).
    5. .bin com par .cue no mesmo diretório → PlayStation.
    6. .bin sem .cue → unknown (mega-drive e PS1 compartilham .bin).
    7. Extensão exclusiva de uma plataforma → classifica nela.
    8. Extensão em múltiplas plataformas → unknown (ambíguo sem root).
    9. Extensão não listada → unknown.
    """
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    lower_siblings = {s.lower() for s in siblings}

    if suffix in {".zip", ".7z"}:
        return None, "unknown", "archived"

    if suffix == ".cue":
        expected_bin = f"{stem}.bin".lower()
        if expected_bin in lower_siblings:
            return "playstation", "base", "cue-pair"
        return None, "unknown", "cue-orphan"

    if suffix == ".bin":
        expected_cue = f"{stem}.cue".lower()
        if expected_cue in lower_siblings:
            return "playstation", "base", "cue-pair"
        if root_platform is not None and ext_map.get(suffix):
            return root_platform, "base", "root-wins"
        return None, "unknown", "bin-orphan"

    platforms = ext_map.get(suffix, [])
    if len(platforms) == 0:
        return None, "unknown", "no-ext-match"
    if root_platform is not None:
        return root_platform, "base", "root-wins"
    if len(platforms) == 1:
        return platforms[0], "base", "exclusive-ext"
    return None, "unknown", "ambiguous-ext"


def disc_group(title: str) -> tuple[str, int | None]:
    """Retorna (título-base, número do disco|None) para agrupamento multidisco."""
    match = _DISC_RE.search(title)
    if match is None:
        return title, None
    base = _DISC_RE.sub("", title).strip()
    return base, int(match.group(1))


@dataclass(frozen=True)
class RomCandidate:
    path: Path
    format: str
    platform: str | None
    content_kind: str
    evidence: str


class PlatformRomScanner:
    """Scanner multi-plataforma barato, sem ler dumps inteiros (D1).

    Usa :func:`classify_rom` para classificar cada arquivo por extensão,
    pareamento .bin+.cue e exclusividade. .zip e .7z são rejeitados como
    unknown. A assinatura ``inventory(root)`` espelha
    ``SwitchLibraryScanner.inventory()``.
    """

    def __init__(
        self,
        ext_map: Mapping[str, Sequence[str]],
    ) -> None:
        self._ext_map = ext_map

    @classmethod
    def from_manifests(
        cls,
        manifests: Sequence[dict[str, Any]],
    ) -> PlatformRomScanner:
        return cls(ext_map=build_ext_map(manifests))

    def inventory(
        self, root: Path, *, root_platform: str | None = None
    ) -> list[RomCandidate]:
        results: list[RomCandidate] = []
        for path in fs.iter_files(root):
            siblings = {p.name for p in path.parent.iterdir()}
            platform_id, content_kind, evidence = classify_rom(
                path.name,
                siblings=siblings,
                ext_map=self._ext_map,
                root_platform=root_platform,
            )
            fmt = detect_format(path.name)
            results.append(
                RomCandidate(
                    path=path,
                    format=fmt,
                    platform=platform_id,
                    content_kind=content_kind,
                    evidence=evidence,
                )
            )
        return results


@dataclass(frozen=True)
class ScannedRom:
    relpath: str
    size: int
    hash_blake2b: str
    format: str


@dataclass
class ImportResult:
    status: str  # imported | duplicate
    rom_id: str | None
    relpath: str | None
    hash_blake2b: str


class LibraryScanner:
    """Scan read-only de uma árvore de ROMs (AC-LB-01)."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    def scan(self, root: Path) -> list[ScannedRom]:
        results: list[ScannedRom] = []
        for path in fs.iter_files(root):
            rel = path.relative_to(root)
            results.append(
                ScannedRom(
                    relpath=str(rel),
                    size=path.stat().st_size,
                    hash_blake2b=fs.hash_file(path),
                    format=detect_format(path.name),
                )
            )
        return results


class LibraryOrganizer:
    """Planeja e executa movimentos/renomes explícitos dentro da biblioteca.

    ``moves`` usa caminhos relativos ``origem -> destino``. A árvore inteira é
    escaneada antes do plano, mas nenhum arquivo é alterado até ``apply`` com o
    confirmToken correspondente.
    """

    def __init__(self, store: StateStore) -> None:
        self._scanner = LibraryScanner(store)

    def plan(self, root: Path, moves: dict[str, str]) -> transaction.Plan:
        scanned = {item.relpath: item for item in self._scanner.scan(root)}
        planned: dict[Path, Path] = {}
        for source_name, target_name in moves.items():
            source_rel = fs.validate_relative_entry(source_name)
            target_rel = fs.validate_relative_entry(target_name)
            normalized_source = str(source_rel)
            if normalized_source not in scanned:
                raise SteamZeroError(
                    "E-TX-STALE-PLAN", detail=f"origem não encontrada: {normalized_source}"
                )
            planned[root / source_rel] = root / target_rel
        return transaction.plan_move_files(planned, root=root, kind="library.organize")

    @staticmethod
    def apply(
        plan_id: str, confirm_token: str, *, dry_run: bool = False
    ) -> transaction.ApplyResult:
        return transaction.apply(plan_id, confirm_token, dry_run=dry_run)

    @staticmethod
    def rollback(operation_id: str) -> transaction.RollbackResult:
        return transaction.rollback(operation_id, reason="library-organize")


class LibraryImporter:
    """Import de dumps do usuário (cópia verificada; origem intocada)."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    def import_file(
        self, src: Path, platform_slug: str, *, title: str | None = None
    ) -> ImportResult:
        slug = ids.require_slug(platform_slug)
        src_hash = fs.hash_file(src)  # origem só é LIDA
        dup = self._store.find_rom_by_hash(src_hash)
        if dup is not None:
            return ImportResult("duplicate", dup["id"], dup["relpath"], src_hash)

        roms = paths.roms_dir()
        dest = fs.resolve_within(roms, roms / slug / src.name)
        data = src.read_bytes()
        fs.write_atomic(dest, data)
        if fs.hash_file(dest) != src_hash:  # cópia corrompida
            fs.remove_file(dest)
            raise SteamZeroError("E-CONTENT-INCOMPLETE", detail="cópia divergente da origem")

        rom_id = self._register(dest, slug, src_hash, title or src.stem)
        return ImportResult("imported", rom_id, str(dest.relative_to(roms)), src_hash)

    def import_archive(self, src: Path, platform_slug: str) -> list[ImportResult]:
        op_id = ids.new_ulid()
        try:
            extracted = safezip.extract_safe(src, op_id)
        except SteamZeroError as exc:
            fs.remove_tree(paths.staging_for(op_id))  # nunca deixa parcial fora
            self._store.append_event(
                "alert", entity=f"import:{src.name}", payload={"code": exc.code}
            )
            raise
        try:
            return [self.import_file(p, platform_slug) for p in extracted]
        finally:
            fs.remove_tree(paths.staging_for(op_id))  # limpa staging após import

    def _register(self, dest: Path, slug: str, rom_hash: str, title: str) -> str:
        self._store.save_platform({"id": slug, "name": slug.upper()})
        base_title, disc = disc_group(title)
        group = base_title if disc is not None else None
        game_id = ids.new_ulid()
        self._store.save_game(
            {
                "id": game_id,
                "platform_id": slug,
                "title": base_title,
                "multi_disc_group": group,
                "state": "ready",
            }
        )
        rom_id = ids.new_ulid()
        self._store.save_rom(
            {
                "id": rom_id,
                "game_id": game_id,
                "volume_id": None,
                "relpath": str(dest.relative_to(paths.roms_dir())),
                "size": dest.stat().st_size,
                "hash_blake2b": rom_hash,
                "format": detect_format(dest.name),
                "verified_at": _now_iso(),
            }
        )
        self._store.append_event(
            "entity.changed", entity=f"rom:{rom_id}", payload={"title": base_title}
        )
        return rom_id


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
