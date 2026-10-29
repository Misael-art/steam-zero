# SPDX-License-Identifier: GPL-3.0-or-later
"""Lost canonical observer: preserve the game, reconcile only with evidence."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

from test_emulation_session_lifetime import _WORKER, _alive

from steamzero.adapters.emulation import EmulationController
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.core.state import StateStore

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_owner_loss_preserves_game_and_exposes_recovery_after_its_exit(tmp_path):
    database = tmp_path / "state.db"
    release = tmp_path / "release-game"
    game_pid = None
    with subprocess.Popen(
        [sys.executable, "-c", _WORKER, str(database), "0", str(release), "json", REQUEST, "30"],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as owner:
        try:
            assert owner.stdout is not None
            with selectors.DefaultSelector() as ready:
                ready.register(owner.stdout, selectors.EVENT_READ)
                assert ready.select(timeout=10)
            reply = json.loads(owner.stdout.readline())
            assert reply["ok"] is True
            game_pid = reply["data"]["pid"]
            assert (
                observe_game_session(database, "lifetime-probe", session_id=REQUEST)["state"]
                == "running"
            )
            owner.send_signal(signal.SIGTERM)  # Only this fixture's lifecycle owner.
            owner.communicate(timeout=10)
            assert owner.returncode == -signal.SIGTERM
            assert _alive(game_pid), "loss of observer must not terminate its detached game"
            assert (
                observe_game_session(database, "lifetime-probe", session_id=REQUEST)["state"]
                == "running"
            )
            release.touch()
            deadline = time.monotonic() + 5
            while _alive(game_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(game_pid)
            observed = observe_game_session(database, "lifetime-probe", session_id=REQUEST)
            assert observed["state"] == "unknown"  # Never invent closed or notStarted.
            assert observed.get("recovery", {}).get("available") is True, observed
            with StateStore(database) as store:
                row = store.get_game_session(REQUEST)
            assert row["state"] == "running", (
                "read-only observation must not mutate canonical state"
            )
        finally:
            release.touch()
            if owner.poll() is None:
                owner.send_signal(signal.SIGTERM)
                owner.communicate(timeout=10)
            if game_pid is not None:
                deadline = time.monotonic() + 5
                while _alive(game_pid) and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert not _alive(game_pid)


def test_live_descendant_prevents_recovery_after_owner_and_leader_exit(tmp_path):
    database = tmp_path / "state.db"
    root_exit = tmp_path / "root-exit"
    child_exit = tmp_path / "child-exit"
    child_pid_file = tmp_path / "child-pid"
    child_program = (
        "from pathlib import Path; import sys,time; gate=Path(sys.argv[1]); "
        "deadline=time.monotonic()+30\n"
        "while not gate.exists() and time.monotonic()<deadline: time.sleep(.01)"
    )
    root_program = (
        "from pathlib import Path; import subprocess,sys,time; "
        f"child=subprocess.Popen([sys.executable,'-c',{child_program!r},sys.argv[2]]); "
        "Path(sys.argv[3]).write_text(str(child.pid)); gate=Path(sys.argv[1]); "
        "deadline=time.monotonic()+30\n"
        "while not gate.exists() and time.monotonic()<deadline: time.sleep(.01)"
    )
    injection = (
        f"controller._build_exec_argv=lambda *_,**__: (sys.executable,'-c',{root_program!r},"
        f"{str(root_exit)!r},{str(child_exit)!r},{str(child_pid_file)!r})\n"
    )
    worker = _WORKER.replace(
        "with patch.object(emulation, 'EmulationController', return_value=controller):",
        injection + "with patch.object(emulation, 'EmulationController', return_value=controller):",
    )
    child_pid = None
    game_pid = None
    with subprocess.Popen(
        [
            sys.executable,
            "-c",
            worker,
            str(database),
            "0",
            str(tmp_path / "unused"),
            "json",
            REQUEST,
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as owner:
        try:
            assert owner.stdout is not None
            with selectors.DefaultSelector() as ready:
                ready.register(owner.stdout, selectors.EVENT_READ)
                assert ready.select(timeout=10)
            reply = json.loads(owner.stdout.readline())
            assert reply["ok"] is True
            game_pid = reply["data"]["pid"]
            deadline = time.monotonic() + 5
            while not child_pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            child_pid = int(child_pid_file.read_text())
            owner.send_signal(signal.SIGTERM)
            owner.communicate(timeout=10)
            root_exit.touch()
            deadline = time.monotonic() + 5
            while _alive(game_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(game_pid) and _alive(child_pid)
            controller = EmulationController.__new__(EmulationController)
            controller._store_factory = lambda: StateStore(database)
            assert (
                observe_game_session(database, "lifetime-probe", session_id=REQUEST)["recovery"][
                    "available"
                ]
                is False
            )
            assert controller.recover_game_session("lifetime-probe", REQUEST)["status"] == "blocked"
            assert _alive(child_pid)
            child_exit.touch()
            deadline = time.monotonic() + 5
            while _alive(child_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(child_pid)
            assert (
                controller.recover_game_session("lifetime-probe", REQUEST)["status"] == "recovered"
            )
        finally:
            root_exit.touch()
            child_exit.touch()
            if owner.poll() is None:
                owner.send_signal(signal.SIGTERM)
                owner.communicate(timeout=10)
            for pid in (game_pid, child_pid):
                if pid is None:
                    continue
                deadline = time.monotonic() + 5
                while _alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert not _alive(pid)
