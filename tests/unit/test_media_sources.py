"""Preserved MediaRegistry sources are shared, decoded and never cache-pruned."""

from __future__ import annotations

import hashlib
import io
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from steamzero.core.errors import SteamZeroError
from steamzero.domain.media_pipeline import MediaPipeline
from steamzero.domain.media_registry import MediaMasterEntry, MediaRegistry, Provenance


def source_bytes() -> bytes:
    image = Image.new("RGBA", (12, 8), (230, 42, 60, 128))
    image.putpixel((0, 0), (20, 230, 50, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_preserved_source_reuses_exact_bytes_and_survives_cache_cleanup(tmp_path: Path) -> None:
    data = source_bytes()
    pipeline = MediaPipeline(tmp_path)
    provenance = Provenance("local-import", "https://example.org/original", "CC0-1.0", "Fixture")
    first = pipeline.preserve_source(data, "color.png", provenance)
    second = pipeline.preserve_source(data, "renamed.png", provenance)
    assert first == second
    assert first.digest == hashlib.sha256(data).hexdigest()
    assert (first.width, first.height, first.has_alpha) == (12, 8, True)
    assert (tmp_path / first.path).read_bytes() == data
    assert len(list((tmp_path / "masters").rglob("*.png"))) == 1
    assert MediaRegistry.read_source(tmp_path, first.digest) == first
    assert pipeline.plan_prune_orphan_cache().actions == []
    assert pipeline.audit().stats["preservedSources"] == 1
    assert pipeline.audit().stats["orphanMasters"] == 0
    assert MediaRegistry.resolve_source(tmp_path, first.digest) == (tmp_path / first.path).resolve()


def test_preserved_master_assignment_keeps_the_existing_game_identity_and_rolls_back(
    tmp_path: Path,
) -> None:
    import json

    from steamzero.adapters.launcher_media import launcher_media_metadata
    from steamzero.core import transaction

    source = MediaPipeline(tmp_path).preserve_source(
        source_bytes(), "original.png", Provenance("fixture", "", "CC0-1.0")
    )
    game = MediaMasterEntry("game-1", "TITLE-1", "fingerprint-1", "Game", "nes-famicom")
    old = replace(
        game, aliases=("Alternate name",), masters={"boxart": "masters/legacy.png", "video": "old"}
    ).to_dict()
    old["futureField"] = {"keep": True}
    target = tmp_path / "registry/assignments-v1.json"
    previous = json.dumps({"entries": [old], "extra": "keep"}).encode()
    target.write_bytes(previous)
    plan, replacing = MediaRegistry.plan_source_assignment(
        tmp_path, game, "cover", source.digest, session_id="owned-editor"
    )
    assert plan is not None and replacing
    assert target.read_bytes() == previous
    applied = MediaRegistry.apply_source_assignment(
        tmp_path, plan, plan.confirm_token, game, session_id="owned-editor"
    )
    updated = json.loads(target.read_bytes())
    assert updated == {
        "entries": [{**old, "masters": {"box2d": source.path, "video": "old"}}],
        "extra": "keep",
    }
    expected_uri = (tmp_path / source.path).as_uri()
    assert (
        launcher_media_metadata(
            media_root=tmp_path, platform_by_game={game.game_id: game.platform_id}
        )[game.game_id]["coverUrl"]
        == expected_uri
    )
    assert len(list((tmp_path / "masters/sources").iterdir())) == 1
    assert transaction.rollback(applied.operation_id).status == "rolled-back"
    assert target.read_bytes() == previous
    assert (tmp_path / source.path).read_bytes() == source_bytes()


def test_source_metadata_is_immutable_and_invalid_media_never_publishes(tmp_path: Path) -> None:
    pipeline = MediaPipeline(tmp_path)
    provenance = Provenance("local-import", "", "CC0-1.0")
    with pytest.raises(SteamZeroError):
        pipeline.preserve_source(b"\x89PNG\r\n\x1a\nbroken", "bad.png", provenance)
    assert not (tmp_path / "masters").exists()
    first = pipeline.preserve_source(source_bytes(), "color.png", provenance)
    with pytest.raises(SteamZeroError, match="procedência"):
        pipeline.preserve_source(source_bytes(), "color.png", replace(provenance, license="Other"))
    assert MediaRegistry.read_source(tmp_path, first.digest) == first
    (tmp_path / first.path).write_bytes(b"corrupt")
    with pytest.raises(SteamZeroError):
        MediaRegistry.resolve_source(tmp_path, first.digest)


def test_source_assignment_preserves_a_newer_publication_and_recovers_missing_master(
    tmp_path: Path,
) -> None:
    original = source_bytes()
    provenance = Provenance("fixture", "", "CC0-1.0")
    pipeline = MediaPipeline(tmp_path)
    master = pipeline.preserve_source(original, "original.png", provenance)
    first = MediaMasterEntry("game-1", "", "", "Game 1", "nes-famicom")
    second = MediaMasterEntry("game-2", "", "", "Game 2", "amiga")
    stale, _ = MediaRegistry.plan_source_assignment(
        tmp_path, first, "cover", master.digest, session_id="editor"
    )
    newer, _ = MediaRegistry.plan_source_assignment(
        tmp_path, second, "logo", master.digest, session_id="editor"
    )
    assert stale is not None and newer is not None
    MediaRegistry.apply_source_assignment(
        tmp_path, newer, newer.confirm_token, second, session_id="editor"
    )
    target = tmp_path / "registry/assignments-v1.json"
    saved = target.read_bytes()
    with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
        MediaRegistry.apply_source_assignment(
            tmp_path, stale, stale.confirm_token, first, session_id="editor"
        )
    assert target.read_bytes() == saved
    plan, _ = MediaRegistry.plan_source_assignment(
        tmp_path, first, "cover", master.digest, session_id="editor"
    )
    assert plan is not None
    (tmp_path / master.path).unlink()
    with pytest.raises(SteamZeroError, match="E-CONTENT-INCOMPLETE"):
        MediaRegistry.apply_source_assignment(
            tmp_path, plan, plan.confirm_token, first, session_id="editor"
        )
    assert target.read_bytes() == saved
    assert pipeline.preserve_source(original, "original.png", provenance) == master
    MediaRegistry.apply_source_assignment(
        tmp_path, plan, plan.confirm_token, first, session_id="editor"
    )
    assert set(MediaRegistry.load(tmp_path).entries) == {first.game_id, second.game_id}
    assert len(list((tmp_path / "masters/sources").iterdir())) == 1


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (b"invalid-json", "E-CONTENT-INCOMPLETE"),
        (b'{"entries":{}}', "E-CONTENT-INCOMPLETE"),
        (b'{"entries":[{"gameId":"game"},{"gameId":"game"}]}', "E-CONTENT-INCOMPLETE"),
        (b'{"entries":[{"gameId":"game","masters":[]}]}', "E-CONTENT-INCOMPLETE"),
        (b'{"entries":[{"gameId":"game","platformId":"amiga"}]}', "E-TX-STALE-PLAN"),
    ],
)
def test_source_assignment_refuses_unverified_registry_without_losing_bytes(
    tmp_path: Path, payload: bytes, error: str
) -> None:
    master = MediaPipeline(tmp_path).preserve_source(
        source_bytes(), "original.png", Provenance("fixture", "", "CC0-1.0")
    )
    target = tmp_path / "registry/assignments-v1.json"
    target.write_bytes(payload)
    game = MediaMasterEntry("game", "", "", "Game", "nes-famicom")
    with pytest.raises(SteamZeroError, match=error):
        MediaRegistry.plan_source_assignment(
            tmp_path, game, "cover", master.digest, session_id="editor"
        )
    assert target.read_bytes() == payload
    with pytest.raises(SteamZeroError, match="E-API-SCHEMA"):
        MediaRegistry.plan_source_assignment(
            tmp_path, game, "video", master.digest, session_id="editor"
        )
    assert target.read_bytes() == payload


def test_source_assignment_refuses_registry_growth_and_keeps_existing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.domain import media_registry

    master = MediaPipeline(tmp_path).preserve_source(
        source_bytes(), "original.png", Provenance("fixture", "", "CC0-1.0")
    )
    game = MediaMasterEntry("game", "", "", "Game", "nes-famicom")
    target = tmp_path / "registry/assignments-v1.json"
    original = b'{"entries": [], "preserved": true}'
    target.write_bytes(original)
    with monkeypatch.context() as patch:
        patch.setattr(media_registry, "_ASSIGNMENTS_LIMIT", len(original) - 1)
        with pytest.raises(SteamZeroError, match="E-CONTENT-INCOMPLETE"):
            MediaRegistry.plan_source_assignment(
                tmp_path, game, "cover", master.digest, session_id="editor"
            )
        assert target.read_bytes() == original
        patch.setattr(media_registry, "_ASSIGNMENTS_LIMIT", len(original))
        with pytest.raises(SteamZeroError, match="E-CONTENT-LIMIT"):
            MediaRegistry.plan_source_assignment(
                tmp_path, game, "cover", master.digest, session_id="editor"
            )
    assert target.read_bytes() == original
    plan, _ = MediaRegistry.plan_source_assignment(
        tmp_path, game, "cover", master.digest, session_id="editor"
    )
    assert plan is not None
    MediaRegistry.apply_source_assignment(
        tmp_path, plan, plan.confirm_token, game, session_id="editor"
    )
    assert MediaRegistry.load(tmp_path).entries[game.game_id].masters["box2d"] == master.path


def test_source_assignment_detects_a_write_between_snapshot_and_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from steamzero.core import transaction

    master = MediaPipeline(tmp_path).preserve_source(
        source_bytes(), "original.png", Provenance("fixture", "", "CC0-1.0")
    )
    game = MediaMasterEntry("game", "", "", "Game", "nes-famicom")
    target = tmp_path / "registry/assignments-v1.json"
    target.write_bytes(b'{"entries": []}')
    concurrent = b'{"entries": [], "otherWriter": true}'
    original_plan = transaction.plan_write_files

    def concurrent_write(*args: object, **kwargs: object) -> transaction.Plan:
        target.write_bytes(concurrent)
        return original_plan(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(transaction, "plan_write_files", concurrent_write)
        with pytest.raises(SteamZeroError, match="E-TX-STALE-PLAN"):
            MediaRegistry.plan_source_assignment(
                tmp_path, game, "cover", master.digest, session_id="editor"
            )
    assert target.read_bytes() == concurrent
    retry, _ = MediaRegistry.plan_source_assignment(
        tmp_path, game, "cover", master.digest, session_id="editor"
    )
    assert retry is not None
    MediaRegistry.apply_source_assignment(
        tmp_path, retry, retry.confirm_token, game, session_id="editor"
    )
    assert json.loads(target.read_bytes())["otherWriter"] is True


def test_source_write_interruption_leaves_no_false_registry_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steamzero.core import fs

    original = fs.publish_link

    def fail_metadata(source: Path, target: Path) -> None:
        if target.suffix == ".json":
            raise OSError("interrupted publication")
        original(source, target)

    monkeypatch.setattr(fs, "publish_link", fail_metadata)
    pipeline = MediaPipeline(tmp_path)
    digest = hashlib.sha256(source_bytes()).hexdigest()
    with pytest.raises(OSError):
        pipeline.preserve_source(
            source_bytes(), "color.png", Provenance("local-import", "", "CC0-1.0")
        )
    assert MediaRegistry.read_source(tmp_path, digest) is None
    monkeypatch.setattr(fs, "publish_link", original)
    restored = pipeline.preserve_source(
        source_bytes(), "color.png", Provenance("local-import", "", "CC0-1.0")
    )
    assert MediaRegistry.resolve_source(tmp_path, digest) == (tmp_path / restored.path).resolve()


@pytest.mark.parametrize("damage", ["missing", "truncated", "same-size-corruption"])
def test_reimport_original_repairs_its_canonical_identity_without_new_copy(
    tmp_path: Path,
    damage: str,
) -> None:
    data = source_bytes()
    provenance = Provenance("fixture", "", "CC0-1.0")
    pipeline = MediaPipeline(tmp_path)
    original = pipeline.preserve_source(data, "original.png", provenance)
    target = tmp_path / original.path
    if damage == "missing":
        target.unlink()
    elif damage == "truncated":
        target.write_bytes(b"broken")
    else:
        target.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(SteamZeroError):
        MediaRegistry.resolve_source(tmp_path, original.digest)
    restored = pipeline.preserve_source(data, "selected-again.png", provenance)
    assert restored == original
    assert target.read_bytes() == data
    assert list(MediaRegistry.sources(tmp_path)) == [original]
    assert len(list((tmp_path / "masters").rglob("*.png"))) == 1


@pytest.mark.parametrize(
    "field, value",
    [
        ("digest", "invalid"),
        ("path", "../escaped.png"),
        ("format", "gif"),
        ("filename", "../outside.png"),
        ("filename", ""),
        ("filename", "x" * 257),
        ("filename", "line\nfeed.png"),
        ("filename", "a\\b.png"),
        ("width", True),
        ("width", 0),
        ("width", 8193),
        ("height", "8"),
        ("has_alpha", "yes"),
        ("size", True),
        ("size", 0),
        ("size", 16 * 1024**2 + 1),
        ("provenance.license", ""),
        ("provenance.hash_sha256", "0" * 64),
        ("provenance.provider", "x" * 1025),
        ("provenance.attribution", "invalid\ncredit"),
    ],
)
def test_corrupt_source_metadata_cannot_rebind_or_rewrite_original(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    import json

    data = source_bytes()
    source = MediaPipeline(tmp_path).preserve_source(
        data, "source.png", Provenance("fixture", "", "CC0-1.0")
    )
    record = tmp_path / "registry/sources-v1" / (source.digest + ".json")
    raw = source.to_dict()
    if field.startswith("provenance."):
        raw["provenance"][field.split(".")[1]] = value
    else:
        raw[field] = value
    record.write_text(json.dumps(raw))
    with pytest.raises(SteamZeroError, match="registro de fonte inválido"):
        MediaRegistry.resolve_source(tmp_path, source.digest)
    assert (tmp_path / source.path).read_bytes() == data
    assert not (tmp_path.parent / "escaped.png").exists()


def test_failed_source_repair_is_retryable_and_never_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from steamzero.core import fs

    data = source_bytes()
    provenance = Provenance("fixture", "", "CC0-1.0")
    pipeline = MediaPipeline(tmp_path)
    original = pipeline.preserve_source(data, "source.png", provenance)
    target = tmp_path / original.path
    target.write_bytes(b"damaged")
    write = fs.write_atomic

    def fail(path: Path, payload: bytes, **kwargs: object) -> None:
        raise OSError("controlled repair interruption")

    monkeypatch.setattr(fs, "write_atomic", fail)
    with pytest.raises(OSError, match="controlled repair interruption"):
        pipeline.preserve_source(data, "source.png", provenance)
    assert target.read_bytes() == b"damaged"
    assert MediaRegistry.read_source(tmp_path, original.digest) == original
    monkeypatch.setattr(fs, "write_atomic", write)
    pipeline.preserve_source(data, "source.png", provenance)
    assert MediaRegistry.resolve_source(tmp_path, original.digest).read_bytes() == data


def test_source_repair_refuses_symlink_and_preserves_its_target(tmp_path: Path) -> None:
    data = source_bytes()
    provenance = Provenance("fixture", "", "CC0-1.0")
    pipeline = MediaPipeline(tmp_path)
    source = pipeline.preserve_source(data, "source.png", provenance)
    master = tmp_path / source.path
    master.unlink()
    protected = tmp_path / "unrelated.png"
    protected.write_bytes(b"preserve this unrelated fixture")
    master.symlink_to(protected)
    with pytest.raises(SteamZeroError):
        pipeline.preserve_source(data, "source.png", provenance)
    assert master.is_symlink()
    assert protected.read_bytes() == b"preserve this unrelated fixture"


@pytest.mark.parametrize("corrupt_metadata", [False, True])
def test_platform_audit_ignores_unassigned_global_sources_and_their_failures(
    tmp_path: Path,
    corrupt_metadata: bool,
) -> None:
    pipeline = MediaPipeline(tmp_path)
    source = pipeline.preserve_source(
        source_bytes(), "source.png", Provenance("fixture", "", "CC0-1.0")
    )
    if corrupt_metadata:
        (tmp_path / "registry/sources-v1" / (source.digest + ".json")).write_text("{")
    else:
        assert pipeline.audit().stats["preservedSources"] == 1
    scoped = pipeline.audit(platform_id="switch")
    assert scoped.stats == {
        "masterFiles": 0,
        "optimizedFiles": 0,
        "viewLinks": 0,
        "orphanMasters": 0,
        "registryEntries": 0,
    }
    assert (tmp_path / source.path).read_bytes() == source_bytes()
