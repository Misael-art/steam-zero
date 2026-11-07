# SPDX-License-Identifier: GPL-3.0-or-later
"""SceneStudioService: media sniffing, operations, persistence and refusals."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from steamzero.adapters.scene_studio import SceneStudioService, sniff_image
from steamzero.domain.scene_authoring import SceneAuthoringError


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x02\x00\x00\x00"
    )


def test_sniff_png_jpeg_webp_and_refusal() -> None:
    assert sniff_image(_png(10, 20)) == ("image/png", 10, 20)
    jpeg = (
        b"\xff\xd8"
        + b"\xff\xe0\x00\x04ab"
        + b"\xff\xc0\x00\x11\x08"
        + struct.pack(">HH", 30, 40)
        + b"\x00" * 8
    )
    assert sniff_image(jpeg) == ("image/jpeg", 40, 30)
    vp8x = (
        b"RIFF\x00\x00\x00\x00WEBPVP8X"
        + b"\x00" * 8
        + (99).to_bytes(3, "little")
        + (49).to_bytes(3, "little")
    )
    assert sniff_image(vp8x) == ("image/webp", 100, 50)
    vp8 = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 10 + struct.pack("<HH", 64, 32)
    assert sniff_image(vp8) == ("image/webp", 64, 32)
    bits = (15 - 1) | ((7 - 1) << 14)
    vp8l = b"RIFF\x00\x00\x00\x00WEBPVP8L" + b"\x00" * 5 + bits.to_bytes(4, "little")
    assert sniff_image(vp8l) == ("image/webp", 15, 7)
    with pytest.raises(SceneAuthoringError):
        sniff_image(b"GIF89a")


def test_every_operation_persists_and_unknown_is_refused(tmp_path: Path) -> None:
    service = SceneStudioService(tmp_path / "scenes")
    assert service.list() == []
    with pytest.raises(SceneAuthoringError):
        service.create("Bad ID", "x")
    sid = service.create("org.test.ops", "Ops")["sessionId"]
    photo = tmp_path / "p.png"
    photo.write_bytes(_png(32, 18) + b"payload")
    media = service.import_media(sid, photo, origin="library")["mediaId"]
    assert service.master_path(media).is_file()
    with pytest.raises(SceneAuthoringError):
        service.master_path("../x")
    with pytest.raises(SceneAuthoringError):
        service.import_media(sid, photo, origin="web")
    with pytest.raises(SceneAuthoringError):
        service.import_media(sid, tmp_path / "missing.png", origin="folder")
    snap = service.transact(sid, "drop", {"mediaId": media, "x": 0.5, "y": 0.5})
    layer = snap["document"]["scenes"][0]["layers"][0]["id"]
    moved = service.transact(sid, "move", {"layerIds": [layer], "dx": 0.001, "dy": 0.0})
    assert "guides" in moved
    service.transact(
        sid, "resize", {"layerId": layer, "handle": "e", "x": 0.9, "y": 0.0, "keepAspect": False}
    )
    service.transact(sid, "resize", {"layerId": layer, "handle": "nw", "x": 0.1, "y": 0.1})
    service.transact(sid, "align", {"layerIds": [layer], "mode": "vcenter"})
    service.transact(sid, "select", {"layerId": layer, "extend": True})
    service.transact(sid, "select", {"layerId": None})
    service.transact(sid, "add-text", {"text": "Olá", "x": 0.1, "y": 0.1})
    service.transact(sid, "reorder", {"layerId": layer, "index": 5})
    service.transact(sid, "set-flag", {"layerId": layer, "flag": "visible", "value": False})
    service.transact(
        sid, "set-recipe", {"layerId": layer, "recipe": {"preset": "cool", "fit": "contain"}}
    )
    service.transact(sid, "undo", {})
    service.transact(sid, "redo", {})
    scene = service.transact(sid, "add-scene", {"name": "Dois"})["sceneId"]
    service.transact(sid, "open-scene", {"sceneId": "scene-1"})
    service.transact(sid, "remove-layer", {"layerId": layer})
    with pytest.raises(SceneAuthoringError):
        service.transact(sid, "exec", {})
    with pytest.raises(SceneAuthoringError):
        service.transact("nope", "undo", {})
    saved = service.save(sid)
    assert saved["status"] == "saved"
    assert service.list() == ["org.test.ops"]
    reopened = service.load("org.test.ops")
    assert scene in {item["id"] for item in reopened["document"]["scenes"]}
    assert reopened["media"][0]["status"] == "available"
    service.master_path(media).unlink()
    assert service.load("org.test.ops")["media"][0]["status"] == "missing"
