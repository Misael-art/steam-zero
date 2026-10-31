# SPDX-License-Identifier: GPL-3.0-or-later
"""Real scan and transactional preparation retain the canonical archive identity."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tests.unit.test_emulation_controller import _controller

from steamzero.adapters.ps5_runtime import Ps5RuntimeReadiness


def archive_controller(monkeypatch, tmp_path: Path):
    controller = _controller(monkeypatch, tmp_path)
    root = tmp_path / "roms"
    folder = root / "ps5"
    folder.mkdir(parents=True)
    archive = folder / "Fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("app/eboot.bin", b"fixture-game")
        output.writestr("app/sce_sys/param.sfo", b"fixture-metadata")
    monkeypatch.setattr(controller, "library_roots", lambda: [str(root)])
    scan = controller._scan_library_now()
    games, _ = controller._load_library_cache()
    assert len(games) == 1, (scan, controller._library_cache_path.read_text())
    game = games[0]
    game_id = game["id"]
    controller._game_settings_path.parent.mkdir(parents=True, exist_ok=True)
    controller._game_settings_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "games": {game_id: {"emulatorId": "sharpemu", "steamSelected": True}},
            }
        )
    )
    monkeypatch.setattr(controller, "_require_launchable_emulator", lambda emulator: None)
    monkeypatch.setattr(controller, "_emulator_source", lambda emulator: ("native", None, None))
    monkeypatch.setattr(
        controller,
        "_ps5_runtime_probe",
        lambda: Ps5RuntimeReadiness(True, "x86_64", True),
        raising=False,
    )
    return controller, game_id


def test_preparation_rescan_keeps_identity_and_resolves_launch_target(
    monkeypatch, tmp_path: Path
) -> None:
    controller, game_id = archive_controller(monkeypatch, tmp_path)
    games, _ = controller._load_library_cache()
    archive = Path(games[0]["path"])
    before = controller.game_readiness(game_id)
    assert before["playable"] is False and before["canPrepare"] is True
    assert controller.prepare_game(game_id)["prepared"] is True
    after, _ = controller._load_library_cache()
    assert after == games
    assert controller.game_readiness(game_id)["playable"] is True
    resolved = controller._launch_preflight(game_id)
    assert resolved["game"]["id"] == game_id
    assert resolved["rom"].read_bytes() == b"fixture-game"
    assert resolved["rom"] != archive
    assert controller.prepare_game(game_id)["result"]["status"] == "current"

    reopened = _controller(monkeypatch, tmp_path)
    monkeypatch.setattr(reopened, "library_roots", lambda: [str(archive.parent.parent)])
    assert reopened._current_game(game_id) == after[0]
    assert reopened._load_game_settings(strict=True)[game_id] == {
        "emulatorId": "sharpemu",
        "steamSelected": True,
    }
    resolved["rom"].write_bytes(b"corrupted")
    assert controller.game_readiness(game_id)["playable"] is False
    assert controller.game_readiness(game_id)["canPrepare"] is True
    assert controller.prepare_game(game_id)["prepared"] is True
    assert controller.game_readiness(game_id)["playable"] is True
