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
from steamzero.domain.media_registry import MediaRegistry, Provenance


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
