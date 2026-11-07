# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Acceptance 1: direct scene authoring with masters preserved and recipes."""

from __future__ import annotations

from pathlib import Path

import pytest

from steamzero.domain import scene_authoring as sa

PHOTO = b"\x89PNG\r\n\x1a\n" + b"fixture-photo-a" * 64
OTHER = b"\x89PNG\r\n\x1a\n" + b"fixture-photo-b" * 64


def _session() -> tuple[sa.SceneAuthoringSession, str, str]:
    session = sa.SceneAuthoringSession()
    a = session.import_master(
        PHOTO,
        name="Capa A",
        media_type="image/png",
        width=1600,
        height=900,
        origin="folder",
        source_ref="fixtures/a.png",
    )
    b = session.import_master(
        OTHER,
        name="Capa B",
        media_type="image/png",
        width=800,
        height=800,
        origin="library",
        source_ref="library://b",
    )
    return session, a, b


def test_drop_move_resize_align_recipe_undo_redo_and_reopen(tmp_path: Path) -> None:
    session, a, b = _session()
    assert (
        session.import_master(
            PHOTO,
            name="dup",
            media_type="image/png",
            width=1600,
            height=900,
            origin="folder",
            source_ref="x",
        )
        == a
    )
    first = session.drop_master(a, 0.3, 0.4)
    layer = session.layer(first)
    assert layer["x"] + layer["w"] / 2 == pytest.approx(0.3)
    # 16:9 photo on a 16:9 stage: normalized w == h keeps the pixel aspect.
    assert layer["w"] == pytest.approx(layer["h"])

    second = session.drop_master(b, 0.7, 0.6, width=0.2)
    snap = session.move(
        [second], 0.0, session.layer(first)["y"] - session.layer(second)["y"] + 0.004
    )
    assert any(guide["axis"] == "horizontal" for guide in snap.guides)
    assert session.layer(second)["y"] == pytest.approx(session.layer(first)["y"])

    before = session.layer(first)
    ratio = before["w"] / before["h"]
    resized = session.resize(first, "se", before["x"] + 0.5, before["y"] + 0.1)
    assert resized["w"] / resized["h"] == pytest.approx(ratio)
    free = session.resize(first, "e", resized["x"] + 0.3, 0)
    assert free["h"] == pytest.approx(resized["h"])

    session.align([first, second], "left")
    assert session.layer(first)["x"] == pytest.approx(session.layer(second)["x"])
    session.align([second], "hcenter")
    assert session.layer(second)["x"] + session.layer(second)["w"] / 2 == pytest.approx(0.5)

    recipe = session.set_recipe(first, brightness=0.2, saturation=0.0, preset="mono", focalX=0.3)
    assert recipe["preset"] == "mono"
    # The same master can be reused with another treatment.
    reuse = session.drop_master(a, 0.5, 0.5)
    assert session.layer(reuse)["recipe"] == sa.default_recipe()
    assert len(session.document["masters"]) == 2

    session.undo()
    assert reuse not in {layer["id"] for layer in session.layers()}
    session.redo()
    assert reuse in {layer["id"] for layer in session.layers()}

    # Window resize changes pixels only; normalized composition is unchanged.
    big, small = sa.Viewport.fit(1440, 900), sa.Viewport.fit(1024, 740)
    for viewport in (big, small):
        px = viewport.to_pixels(session.layer(first))
        sx, sy = viewport.to_stage(px["x"], px["y"])
        assert (sx, sy) == pytest.approx((session.layer(first)["x"], session.layer(first)["y"]))
    assert big.width / big.height == pytest.approx(small.width / small.height)

    path = tmp_path / "experience.scene.json"
    sa.save(path, session.document)
    reopened = sa.SceneAuthoringSession(sa.load(path))
    assert reopened.layer(first) == session.layer(first)
    assert reopened.layer(first)["recipe"]["preset"] == "mono"
    assert {m["id"] for m in reopened.document["masters"]} == {a, b}
    store = {"fixtures/a.png": PHOTO, "library://b": OTHER}
    report = reopened.media_report(lambda m: store.get(m["sourceRef"]))
    assert {item["status"] for item in report} == {"available"}


def test_layers_order_visibility_lock_and_text() -> None:
    session, a, _b = _session()
    one = session.drop_master(a, 0.2, 0.2)
    text = session.add_text("Título", 0.1, 0.1)
    session.reorder(text, 0)
    assert [layer["id"] for layer in session.layers()] == [text, one]
    session.set_flag(one, "visible", False)
    session.set_flag(one, "locked", True)
    with pytest.raises(sa.SceneAuthoringError, match="bloqueada"):
        session.move([one], 0.1, 0.1)
    assert session.select(one) == [one]
    assert session.select(text, extend=True) == [one, text]


def test_missing_moved_or_changed_master_is_reported_not_replaced() -> None:
    session, a, b = _session()
    session.drop_master(a, 0.5, 0.5)
    report = {
        item["mediaId"]: item
        for item in session.media_report(
            lambda m: {"fixtures/a.png": b"tampered"}.get(m["sourceRef"])
        )
    }
    assert report[a]["status"] == "changed"
    assert report[b]["status"] == "missing" and report[b]["action"] == "relink-or-remove"
    assert session.layers()[0]["mediaId"] == a


def test_library_filter_does_not_touch_treatment() -> None:
    session, a, _b = _session()
    layer = session.drop_master(a, 0.5, 0.5)
    session.set_recipe(layer, preset="warm")
    assert [m["id"] for m in session.library(origin="folder")] == [a]
    assert session.library(query="capa b")[0]["origin"] == "library"
    assert session.layer(layer)["recipe"]["preset"] == "warm"


def test_invalid_file_and_failed_write_preserve_previous_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, a, _b = _session()
    session.drop_master(a, 0.5, 0.5)
    path = tmp_path / "p.scene.json"
    sa.save(path, session.document)
    saved = path.read_bytes()
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"{not json")
    with pytest.raises(sa.SceneAuthoringError):
        sa.load(bad)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disco cheio")

    session.drop_master(a, 0.1, 0.1)
    monkeypatch.setattr(sa.fs, "write_atomic", boom)
    with pytest.raises(OSError):
        sa.save(path, session.document)
    assert path.read_bytes() == saved
    with pytest.raises(sa.SceneAuthoringError):
        sa.parse(saved.replace(a.encode(), b"0" * 64, 1))


def test_budgets_and_refusals_leave_history_intact() -> None:
    session, a, _b = _session()
    depth = session.can_undo
    with pytest.raises(sa.SceneAuthoringError):
        session.set_recipe("nope", preset="mono")
    with pytest.raises(sa.SceneAuthoringError):
        session.drop_master("f" * 64, 0.5, 0.5)
    assert session.can_undo == depth
    for _ in range(sa.MAX_LAYERS_PER_SCENE):
        session.drop_master(a, 0.5, 0.5, width=0.05)
    with pytest.raises(sa.SceneAuthoringError, match="limite"):
        session.drop_master(a, 0.5, 0.5)
