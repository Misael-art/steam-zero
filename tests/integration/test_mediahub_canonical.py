# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""MediaHub canônico: masters → optimized → views com associação por hash.

O contrato público é ``media-registry-v1.schema.json``. A razão de existir do
snapshot é reportar *caminhos*: o ``audit()`` já conta arquivos, mas ninguém
descobre com ele **quais** masters estão soltos em disco.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from jsonschema import ValidationError

from steamzero.api import contracts
from steamzero.domain.media_pipeline import MediaPipeline
from steamzero.domain.media_registry import MediaMasterEntry, Provenance
from steamzero.ports import MediaCandidate

_PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic-png-body"
_JPG = b"\xff\xd8\xff" + b"synthetic-jpeg-body"

_SCHEMA_ID = "media-registry-v1.schema.json"
_PLATFORM = "switch"
_SHA_A = "a" * 64
_NO_ORPHANS = {"masterFiles": [], "optimizedFiles": [], "brokenViewLinks": []}


def _entries(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], snapshot["entries"])


def _masters(entry: dict[str, object]) -> dict[str, dict[str, str]]:
    return cast(dict[str, dict[str, str]], entry["masters"])


def _orphans(snapshot: dict[str, object]) -> dict[str, list[str]]:
    return cast(dict[str, list[str]], snapshot["orphans"])


def _hash_index(snapshot: dict[str, object]) -> dict[str, list[str]]:
    return cast(dict[str, list[str]], snapshot["hashIndex"])


def _optimized(snapshot: dict[str, object]) -> dict[str, dict[str, list[str]]]:
    return cast(dict[str, dict[str, list[str]]], snapshot["optimized"])


def _views(snapshot: dict[str, object]) -> dict[str, list[str]]:
    return cast(dict[str, list[str]], snapshot["views"])


def _optimize_tool(src: Path, dst: Path, _profile: str) -> bool:
    dst.write_bytes(src.read_bytes())
    return True


def _import_master(
    pipeline: MediaPipeline,
    game_id: str,
    kind: str,
    data: bytes,
    *,
    platform_id: str = _PLATFORM,
) -> Path:
    src = pipeline._media_root / f"src-{game_id}-{kind}.png"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(data)
    result = pipeline.collect(
        source=src,
        game_id=game_id,
        title_id=f"0100{game_id.upper()[-12:]}",
        fingerprint=f"fp-{game_id}",
        canonical_name=f"Game {game_id}",
        kind=kind,
        platform_id=platform_id,
    )
    assert result.success, result.failed
    return next(iter(result.collected.values()))


def _stray_master(pipeline: MediaPipeline, kind: str, sha: str) -> Path:
    stray = pipeline._media_root / "masters" / _PLATFORM / kind / f"{sha}.png"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(_PNG)
    return stray


@pytest.mark.integration
def test_mediahub_canonical_flow_with_hash_association(tmp_path: Path) -> None:
    pipeline = MediaPipeline(
        tmp_path / "media",
        optimizer_tool=_optimize_tool,
        candidate_fetcher=lambda url: _PNG,
    )
    master = _import_master(pipeline, "GAME-A", "box2d", _PNG)
    _import_master(pipeline, "GAME-B", "hero", _JPG)

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)

    assert snapshot["schemaVersion"] == 1
    entries = _entries(snapshot)
    assert set(entries) == {"GAME-A", "GAME-B"}
    assert entries["GAME-A"]["platformId"] == _PLATFORM
    masters = _masters(entries["GAME-A"])
    assert masters["box2d"]["relPath"] == master.relative_to(pipeline._media_root).as_posix()
    sha_a = masters["box2d"]["sha256"]
    assert len(sha_a) == 64
    assert _hash_index(snapshot)[sha_a] == ["GAME-A"]

    optimized = pipeline.optimize("GAME-A")
    assert optimized.success, optimized.failed
    after = pipeline.registry_snapshot()
    contracts.validate(after, _SCHEMA_ID)
    assert "steam-portrait" in _optimized(after)["GAME-A"]
    assert "steam-landscape" in _optimized(after)["GAME-A"]
    assert _orphans(after) == _NO_ORPHANS


@pytest.mark.integration
def test_mediahub_hash_index_associates_shared_master(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "GAME-A", "box2d", _PNG)
    _import_master(pipeline, "GAME-B", "box2d", _PNG)
    _import_master(pipeline, "GAME-C", "box2d", _JPG)

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    index = _hash_index(snapshot)
    entries = _entries(snapshot)
    shared = entries["GAME-A"]["masters"]["box2d"]["sha256"]
    assert shared == entries["GAME-B"]["masters"]["box2d"]["sha256"]
    assert index[shared] == ["GAME-A", "GAME-B"]
    own = entries["GAME-C"]["masters"]["box2d"]["sha256"]
    assert own != shared
    assert index[own] == ["GAME-C"]


@pytest.mark.integration
def test_mediahub_snapshot_detects_orphans_and_broken_views(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "GAME-A", "box2d", _PNG)
    stray = _stray_master(pipeline, "icon", "f" * 64)

    optimized = pipeline.optimize("GAME-A")
    assert optimized.success, optimized.failed

    grid_dir = tmp_path / "media" / "views" / "steam" / "steam-user-1" / "grid"
    result = pipeline.view_steam("GAME-A", "steam-user-1", 12345, grid_dir=grid_dir)
    assert result.published, result.failed
    broken = grid_dir / "99999.png"
    absent = tmp_path / "media" / "optimized" / _PLATFORM / "steam-hero" / "absent.png"
    broken.symlink_to(absent)
    assert not broken.exists()

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    orphans = _orphans(snapshot)
    assert orphans["masterFiles"] == [stray.relative_to(pipeline._media_root).as_posix()]
    assert orphans["optimizedFiles"] == []
    assert len(orphans["brokenViewLinks"]) == 1
    assert orphans["brokenViewLinks"][0].startswith("views/steam/steam-user-1/grid/")
    assert _views(snapshot)["steam"], snapshot["views"]


@pytest.mark.integration
def test_mediahub_orphan_masters_match_the_prune_plan(tmp_path: Path) -> None:
    """Snapshot e limpeza de cache têm de apontar para os mesmos arquivos."""
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "GAME-A", "box2d", _PNG)
    for sha in ("a" * 64, "b" * 64):
        _stray_master(pipeline, "logo", sha)

    snapshot = pipeline.registry_snapshot()
    plan = pipeline.plan_prune_orphan_cache()
    removals = sorted(action.target for action in plan.actions if action.kind == "delete")
    root = pipeline._media_root.resolve(strict=False)
    assert removals == sorted(str(root / rel) for rel in _orphans(snapshot)["masterFiles"])
    assert len(removals) == 2


@pytest.mark.integration
def test_mediahub_attributes_optimized_to_the_longest_matching_game_id(
    tmp_path: Path,
) -> None:
    """gameId com underscore não pode perder o próprio optimized para o prefixo."""
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "SWITCH_GAME", "box2d", _PNG)
    _import_master(pipeline, "SWITCH", "hero", _JPG)

    optimized = pipeline.optimize("SWITCH_GAME")
    assert optimized.success, optimized.failed
    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    owners = _optimized(snapshot)
    assert "steam-portrait" in owners["SWITCH_GAME"]
    assert "SWITCH" not in owners
    assert _orphans(snapshot)["optimizedFiles"] == []


@pytest.mark.integration
def test_mediahub_snapshot_reports_unattributed_optimized_as_orphan(
    tmp_path: Path,
) -> None:
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "GAME-A", "box2d", _PNG)
    media_root = pipeline._media_root
    ghost = media_root / "optimized" / _PLATFORM / "steam-hero" / "GHOST_x.png"
    ghost.parent.mkdir(parents=True, exist_ok=True)
    ghost.write_bytes(_PNG)
    shallow = media_root / "optimized" / _PLATFORM / "stray.png"
    shallow.write_bytes(_PNG)

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    assert _orphans(snapshot)["optimizedFiles"] == [
        f"optimized/{_PLATFORM}/steam-hero/GHOST_x.png",
        f"optimized/{_PLATFORM}/stray.png",
    ]


@pytest.mark.integration
def test_mediahub_snapshot_validates_through_registry_entry_types(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path / "media")
    pipeline._registry.register_platform(
        _PLATFORM,
        "Switch",
        ("box2d", "hero", "logo", "icon", "screenshot"),
    )
    pipeline._registry.add_entry(
        MediaMasterEntry(
            game_id="GAME-A",
            title_id="0100GAMEAAA",
            fingerprint="fp-a",
            canonical_name="Game A",
            platform_id=_PLATFORM,
            aliases=("Game A DX",),
            region="us",
            language="en",
            confirmed=True,
            metadata_origin="scraper",
            steam_appid=12345,
            provenance=Provenance(
                provider="test-provider",
                source_url="https://media.invalid/a.png",
                license="CC0-1.0",
                attribution="Fixture",
                hash_sha256=_SHA_A,
            ),
            masters={"box2d": f"masters/{_PLATFORM}/box2d/{_SHA_A}.png"},
        )
    )

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    entry = _entries(snapshot)["GAME-A"]
    assert entry["metadataOrigin"] == "scraper"
    assert entry["steamAppid"] == 12345
    assert entry["aliases"] == ["Game A DX"]
    provenance = cast(dict[str, str], entry["provenance"])
    assert provenance["provider"] == "test-provider"
    assert provenance["hashSha256"] == _SHA_A
    platforms = cast(dict[str, dict[str, object]], snapshot["platforms"])
    assert platforms[_PLATFORM]["name"] == "Switch"
    assert _masters(entry)["box2d"]["sha256"] == _SHA_A


@pytest.mark.integration
def test_mediahub_snapshot_without_entries_is_still_valid(tmp_path: Path) -> None:
    snapshot = MediaPipeline(tmp_path / "media").registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    assert snapshot["entries"] == {}
    assert snapshot["hashIndex"] == {}
    assert snapshot["optimized"] == {}
    assert snapshot["views"] == {}
    assert snapshot["platforms"] == {}
    assert _orphans(snapshot) == _NO_ORPHANS


@pytest.mark.golden
def test_mediahub_snapshot_is_json_serializable(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path / "media", optimizer_tool=_optimize_tool)
    _import_master(pipeline, "GAME-A", "box2d", _PNG)
    snapshot = pipeline.registry_snapshot()
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    assert json.loads(payload)["entries"]["GAME-A"]["canonicalName"] == "Game GAME-A"


@pytest.mark.golden
def test_mediahub_contract_rejects_invalid_snapshot() -> None:
    invalid = {
        "schemaVersion": 2,
        "generatedAt": "not-a-date",
        "platforms": {},
        "entries": {},
        "hashIndex": {},
        "optimized": {},
        "views": {},
        "orphans": _NO_ORPHANS,
    }
    with pytest.raises(ValidationError):
        contracts.validate(invalid, _SCHEMA_ID)


@pytest.mark.golden
def test_mediahub_candidate_collection_records_provenance_hash(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path / "media", candidate_fetcher=lambda url: _JPG)
    candidate = MediaCandidate(
        url="https://media.invalid/cover.jpg",
        media_kind="boxart",
        provider="fixture",
        confidence=0.9,
        license="CC0-1.0",
        attribution="Fixture",
    )
    result = pipeline.collect_from_candidate(
        candidate=candidate,
        game_id="GAME-A",
        title_id="0100GAMEAAA",
        fingerprint="fp-a",
        canonical_name="Game A",
        platform_id=_PLATFORM,
    )
    assert result.success, result.failed
    entry = pipeline.get_registry_entry("GAME-A")
    assert entry is not None and entry.provenance is not None

    snapshot = pipeline.registry_snapshot()
    contracts.validate(snapshot, _SCHEMA_ID)
    recorded = _entries(snapshot)["GAME-A"]
    provenance = cast(dict[str, str], recorded["provenance"])
    assert provenance["hashSha256"] == entry.provenance.hash_sha256
    assert provenance["hashSha256"] == _masters(recorded)["box2d"]["sha256"]
