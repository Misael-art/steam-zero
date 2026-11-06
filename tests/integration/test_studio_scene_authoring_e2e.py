# SPDX-License-Identifier: GPL-3.0-or-later
"""Scene authoring and Journey map through the production bridge (offscreen Qt)."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import urllib.error
import zlib
from pathlib import Path

import pytest
from tests.integration.test_experience_journey_bridge_e2e import (  # noqa: F401
    _request,
    journey_bridge,
)
from tests.integration.test_ui_shell_retrofe_import_late_response import RUNNER


def _png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> Path:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return path


def test_scene_bridge_roundtrip_and_refusals(journey_bridge, tmp_path: Path) -> None:  # noqa: F811
    base, token, _ = journey_bridge
    photo = _png(tmp_path / "a.png", 64, 36, (200, 40, 40))
    created = _request(
        base,
        token,
        "/studio/scene/create",
        method="POST",
        payload={"projectId": "org.test.bridge-scene", "name": "Ponte"},
    )
    sid = created["sessionId"]
    imported = _request(
        base,
        token,
        "/studio/scene/import-media",
        method="POST",
        payload={"sessionId": sid, "path": str(photo), "origin": "folder"},
    )
    media_id = imported["mediaId"]
    assert imported["document"]["masters"][0]["width"] == 64
    dropped = _request(
        base,
        token,
        "/studio/scene/transact",
        method="POST",
        payload={
            "sessionId": sid,
            "operation": "drop",
            "payload": {"mediaId": media_id, "x": 0.5, "y": 0.5},
        },
    )
    assert len(dropped["document"]["scenes"][0]["layers"]) == 1
    with pytest.raises(urllib.error.HTTPError) as refused:
        _request(
            base,
            token,
            "/studio/scene/transact",
            method="POST",
            payload={"sessionId": sid, "operation": "exec", "payload": {}},
        )
    assert refused.value.code == 400
    bogus = tmp_path / "x.png"
    bogus.write_bytes(b"not an image")
    with pytest.raises(urllib.error.HTTPError):
        _request(
            base,
            token,
            "/studio/scene/import-media",
            method="POST",
            payload={"sessionId": sid, "path": str(bogus), "origin": "folder"},
        )
    saved = _request(base, token, "/studio/scene/save", method="POST", payload={"sessionId": sid})
    assert saved["status"] == "saved"
    photo.unlink()  # source moved: the project master store keeps integrity
    reopened = _request(
        base,
        token,
        "/studio/scene/load",
        method="POST",
        payload={"projectId": "org.test.bridge-scene"},
    )
    assert reopened["media"][0]["status"] == "available"
    assert reopened["document"] == saved["snapshot"]["document"]


@pytest.mark.visual
def test_scene_authoring_qml_with_mouse_through_real_bridge(journey_bridge, tmp_path: Path) -> None:  # noqa: F811
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    base, token, _ = journey_bridge
    root = Path(__file__).resolve().parents[2]
    config = root / "build" / "studio-scene-e2e.json"
    config.parent.mkdir(exist_ok=True)
    assert not config.exists(), "há um arquivo efêmero anterior que precisa ser inspecionado"
    config.write_text(
        json.dumps(
            {
                "apiUrl": base,
                "apiToken": token,
                "photoA": str(_png(tmp_path / "capa-a.png", 160, 90, (30, 120, 200))),
                "photoB": str(_png(tmp_path / "capa-b.png", 80, 80, (220, 180, 40))),
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QML_XHR_ALLOW_FILE_READ": "1",
        }
    )
    try:
        completed = subprocess.run(
            [
                str(RUNNER),
                "-input",
                str(root / "tests" / "qml" / "check_studio_scene_authoring_e2e.qml"),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        config.unlink(missing_ok=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, output[-7000:]
    assert "FAIL!" not in output, output[-7000:]
