# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Launcher root, authenticated bridge and visible preparation observation."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

import pytest
from tests.integration.test_ui_shell_retrofe_import_late_response import RUNNER

from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.launcher.app import build_sections

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.visual
@pytest.mark.parametrize("real_archive", [False, True])
def test_launcher_details_readiness_and_preparation_qml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, real_archive: bool
) -> None:
    assert RUNNER is not None
    ready = threading.Event()
    release = threading.Event()
    prepared, launched = [], []
    observations = []

    class ObservedBridge(LauncherBridge):
        def readiness(self, game_id):
            result = super().readiness(game_id)
            if result["state"] == "preparing":
                observations.append(game_id)
                # POST publishes the first observation. A subsequent GET
                # proves the UI started observing before the fixture finishes.
                if len(observations) >= 2:
                    release.set()
            return result

    def prepare(game):
        prepared.append(game)
        assert release.wait(10)
        ready.set()
        return {"prepared": True}

    game_id = "game"

    def readiness(game):
        return {
            "playable": ready.is_set(),
            "canPrepare": not ready.is_set(),
            "reason": "Fixture: extração necessária" if not ready.is_set() else "",
        }

    if real_archive:
        from tests.integration.test_launcher_archive_preparation import archive_controller

        controller, game_id = archive_controller(monkeypatch, tmp_path)
        readiness = controller.game_readiness

        def prepare(game):
            prepared.append(game)
            assert release.wait(10)
            return controller.prepare_game(game)

    bridge = ObservedBridge(
        sections=build_sections([{"id": game_id, "title": "Fixture", "section": "library"}]),
        titles={game_id: "Fixture"},
        context_path=tmp_path / "return.json",
        readiness=readiness,
        prepare=prepare,
        on_launch=lambda game, focus: launched.append(game),
    )
    env = os.environ.copy()
    env.update(
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        QT_FORCE_STDERR_LOGGING="1",
        QT_LOGGING_RULES="",
        QML_XHR_ALLOW_FILE_READ="1",
    )
    for name in ("CONFIG", "DATA", "STATE", "CACHE", "RUNTIME"):
        path = tmp_path / ("qml-" + name.lower())
        path.mkdir(mode=0o700)
        env[f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
    try:
        with bridge.serving() as base:
            fixture = tmp_path / "bridge.json"
            fixture.write_text(json.dumps({"api": base, "token": bridge.token}))
            fixture.chmod(0o600)
            harness = tmp_path / "check_launcher_readiness.qml"
            source = (ROOT / "tests/qml/launcher/check_launcher_readiness.qml").read_text()
            source = source.replace('"game"', json.dumps(game_id))
            harness.write_text(
                source.replace(
                    'import "../../../src/steamzero/ui/qml/launcher"',
                    f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
                )
            )
            completed = subprocess.run(
                [
                    str(RUNNER),
                    "-input",
                    str(harness),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
    finally:
        release.set()
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output[-10000:]
    assert "FAIL!" not in output
    assert "ZLauncherRootReadiness" in output
    assert prepared == [game_id] and launched == []
