# SPDX-License-Identifier: GPL-3.0-or-later
"""Lost canonical observer: preserve the game, reconcile only with evidence."""

from __future__ import annotations

import json
import os
import selectors
import signal
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest
from test_emulation_session_lifetime import _WORKER, _alive

from steamzero.adapters.emulation import EmulationController
from steamzero.adapters.launcher_receipt import LaunchAttempt, Receipt
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore
from steamzero.launcher.app import LaunchRouter
from steamzero.launcher.launch import CONTEXT_OWNER, consume_context
from steamzero.launcher.navigation import HomeSection

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _terminal_recovery(tmp_path, *, state="failed"):
    database = tmp_path / "state.db"
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "owner": CONTEXT_OWNER,
                "launchRequestId": REQUEST,
                "gameId": "lifetime-probe",
                "focusId": "library:lifetime-probe",
            }
        )
    )
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(
            {
                "id": REQUEST,
                "game_id": "lifetime-probe",
                "owner": SESSION_OWNER,
                "state": "launching" if state == "closed" else state,
                "started_at": "2026-10-28T23:59:53+00:00",
                "finished_at": "2026-10-29T00:00:00+00:00",
                "failure_code": "E-SESSION-ORPHANED" if state == "failed" else None,
                "exit_code": None if state == "failed" else 0,
                "metadata_json": '{"source":"emulation"}',
            }
        )
        if state == "closed":
            store.transition_game_session(
                REQUEST, "running", played_seconds=7, duration_source="observed-monotonic"
            )
            store.transition_game_session(
                REQUEST, "closed", exit_code=0, finished_at="2026-10-29T00:00:00+00:00"
            )
    calls = []

    def spawn(argv, *, request_id, game_id):
        calls.append(request_id)
        return LaunchAttempt(request_id=request_id, game_id=game_id)

    router = LaunchRouter(
        on_spawn=lambda _: 0,
        context_path=context,
        executable=lambda: "steamzero",
        receipt_spawner=spawn,
    )

    def reopen():
        return LauncherBridge(
            sections=(
                HomeSection(id="library", title="Library", items=("first", "lifetime-probe")),
            ),
            context_path=context,
            return_context=consume_context(context),
            on_launch=router.launch,
            session_observer=lambda game: observe_game_session(database, game),
            session_by_id=lambda game, identity: observe_game_session(
                database, game, session_id=identity
            ),
        )

    return database, context, calls, reopen


def test_closed_context_survives_lost_get_and_restarts_until_explicit_launch(tmp_path):
    database, context, calls, reopen = _terminal_recovery(tmp_path, state="closed")
    with StateStore(database) as store:
        before = store.get_game_session(REQUEST)
    assert before["exit_code"] == 0 and before["played_seconds"] == 7
    assert before["duration_source"] == "observed-monotonic"
    for _ in range(3):
        bridge = reopen()
        assert bridge.model()["launchRecovery"]["sessionId"] == REQUEST
        result = bridge.session("lifetime-probe")  # Every terminal reply is lost.
        assert result["state"] == "closed" and result["sessionId"] == REQUEST
        assert "failureCode" not in result and "launchAcknowledgment" not in result
        assert context.exists(), "lost closed reply erased the return context"
        assert calls == []
        with StateStore(database) as store:
            assert store.get_game_session(REQUEST) == before
    attempt = bridge.launch(
        "lifetime-probe", "library:lifetime-probe", client_request_id="explicit-next"
    )
    assert attempt is not None and attempt.request_id != REQUEST
    assert calls == [attempt.request_id]
    assert json.loads(context.read_text())["launchRequestId"] == attempt.request_id
    assert (
        bridge.launch("lifetime-probe", "library:lifetime-probe", client_request_id="explicit-next")
        is attempt
    )
    with StateStore(database) as store:
        assert store.get_game_session(REQUEST) == before


def test_recovered_failure_survives_lost_get_and_restart_until_explicit_launch(tmp_path):
    database, context, calls, reopen = _terminal_recovery(tmp_path)
    with StateStore(database) as store:
        before = store.get_game_session(REQUEST)
    first = reopen()
    result = first.session("lifetime-probe")  # The terminal reply never reaches the UI.
    assert result["state"] == "failed" and result["sessionId"] == REQUEST
    assert result["failureCode"] == "E-SESSION-ORPHANED"
    assert "launchAcknowledgment" not in result and "attempt" not in result
    assert context.exists(), "a lost terminal GET consumed the only restart context"
    second = reopen()
    assert second.model()["launchRecovery"]["sessionId"] == REQUEST
    for _ in range(3):
        assert second.session("lifetime-probe") == result
        assert context.exists() and calls == []
    attempt = second.launch(
        "lifetime-probe", "library:lifetime-probe", client_request_id="explicit-retry"
    )
    assert attempt is not None and attempt.request_id != REQUEST
    assert calls == [attempt.request_id]
    assert json.loads(context.read_text())["launchRequestId"] == attempt.request_id
    assert (
        second.launch(
            "lifetime-probe", "library:lifetime-probe", client_request_id="explicit-retry"
        )
        is attempt
    )
    assert calls == [attempt.request_id]
    with StateStore(database) as store:
        assert store.get_game_session(REQUEST) == before


@pytest.mark.parametrize("next_game", ["first", "lifetime-probe"])
@pytest.mark.parametrize("terminal", ["failed", "closed"])
def test_live_confirmed_attempt_retains_terminal_for_restart_and_explicit_retry(
    tmp_path, next_game, terminal
):
    database, context, calls, reopen = _terminal_recovery(tmp_path, state=terminal)
    context.unlink()  # This bridge starts before its own launch, without restoration.
    bridge = reopen()
    attempt = bridge.launch("lifetime-probe", "library:lifetime-probe", client_request_id="old")
    assert attempt is not None
    attempt._settle(Receipt(state="confirmed", session_id=attempt.request_id))
    with StateStore(database) as store:
        store.create_game_session(
            {
                "id": attempt.request_id,
                "game_id": "lifetime-probe",
                "owner": SESSION_OWNER,
                "state": "launching" if terminal == "closed" else terminal,
                "failure_code": "E-SESSION-ORPHANED" if terminal == "failed" else None,
                "metadata_json": '{"source":"emulation"}',
            }
        )
        if terminal == "closed":
            store.transition_game_session(
                attempt.request_id,
                "running",
                played_seconds=9,
                duration_source="observed-monotonic",
            )
            store.transition_game_session(attempt.request_id, "closed", exit_code=0)
        before = store.get_game_session(attempt.request_id)
    for _ in range(3):
        result = bridge.session("lifetime-probe", client_request_id="old")
        assert result["state"] == terminal and result["sessionId"] == attempt.request_id
        assert result["attempt"]["state"] == "confirmed"
        assert "launchAcknowledgment" not in result
        assert context.exists() and calls == [attempt.request_id]
    assert bridge.model()["launchRecovery"]["requestId"] == attempt.request_id
    restored = reopen()
    assert restored.model()["launchRecovery"]["sessionId"] == attempt.request_id
    observed = restored.session("lifetime-probe")
    assert observed["state"] == terminal
    if terminal == "failed":
        assert observed["failureCode"] == "E-SESSION-ORPHANED"
    else:
        assert "failureCode" not in observed
    new = bridge.launch(next_game, f"library:{next_game}", client_request_id="new")
    assert new is not None and new.request_id != attempt.request_id
    assert calls == [attempt.request_id, new.request_id]
    assert json.loads(context.read_text())["gameId"] == next_game
    assert bridge.model()["launchRecovery"] is None
    with StateStore(database) as store:
        assert store.get_game_session(attempt.request_id) == before


@pytest.mark.parametrize(
    "replacement",
    [
        "foreign",
        "other-request",
        "other-game",
        "other-focus",
        "symlink",
        "malformed",
        "unicode",
        "deep",
    ],
)
@pytest.mark.parametrize("terminal", ["failed", "closed"])
def test_terminal_retry_preserves_replaced_or_unreadable_context(tmp_path, replacement, terminal):
    database, context, calls, reopen = _terminal_recovery(tmp_path, state=terminal)
    bridge = reopen()
    assert bridge.session("lifetime-probe")["state"] == terminal
    if replacement == "symlink":
        context.unlink()
        target = tmp_path / "foreign.json"
        target.write_text("foreign")
        context.symlink_to(target)
    elif replacement in {"malformed", "unicode", "deep"}:
        context.write_bytes(
            {"malformed": b"{not-json", "unicode": b"\xff", "deep": b"[" * 1200 + b"]" * 1200}[
                replacement
            ]
        )
    else:
        payload = json.loads(context.read_text())
        field, value = {
            "foreign": ("owner", "foreign"),
            "other-request": ("launchRequestId", "01ARZ3NDEKTSV4RRFFQ69G5FAW"),
            "other-game": ("gameId", "first"),
            "other-focus": ("focusId", "library:first"),
        }[replacement]
        payload[field] = value
        context.write_text(json.dumps(payload))
    before = context.read_bytes() if context.exists() else None
    with pytest.raises(ValueError, match="context changed"):
        bridge.launch("lifetime-probe", "library:lifetime-probe", client_request_id="retry")
    assert (context.read_bytes() if context.exists() else None) == before
    assert calls == []
    if replacement == "symlink":
        assert context.is_symlink() and target.read_text() == "foreign"
    with StateStore(database) as store:
        row = store.get_game_session(REQUEST)
        assert row["state"] == terminal
        assert row["failure_code"] == ("E-SESSION-ORPHANED" if terminal == "failed" else None)


@pytest.mark.parametrize("terminal", ["failed", "closed"])
def test_invalid_focus_does_not_consume_terminal_or_hide_its_next_observation(tmp_path, terminal):
    _database, context, calls, reopen = _terminal_recovery(tmp_path, state=terminal)
    bridge = reopen()
    result = bridge.session("lifetime-probe")
    before = context.read_bytes()
    with pytest.raises(ValueError, match="return focus"):
        bridge.launch("lifetime-probe", "library:first", client_request_id="bad-focus")
    assert context.read_bytes() == before and calls == []
    assert bridge.session("lifetime-probe") == result


@pytest.mark.parametrize("terminal", ["failed", "closed"])
def test_missing_context_is_not_recreated_by_get_and_allows_validated_terminal_retry(
    tmp_path, terminal
):
    _database, context, calls, reopen = _terminal_recovery(tmp_path, state=terminal)
    bridge = reopen()
    result = bridge.session("lifetime-probe")
    context.unlink()
    assert bridge.session("lifetime-probe") == result
    assert not context.exists() and calls == []
    new = bridge.launch("lifetime-probe", "library:lifetime-probe", client_request_id="retry")
    assert new is not None and new.request_id != REQUEST
    assert calls == [new.request_id]
    assert json.loads(context.read_text())["launchRequestId"] == new.request_id


@pytest.mark.parametrize(
    "terminal,field,value",
    [
        ("failed", "failure_code", "unregistered"),
        ("failed", "owner", "other"),
        ("failed", "game_id", "first"),
        ("failed", "state", "running"),
        ("closed", "owner", "other"),
        ("closed", "game_id", "first"),
        ("closed", "state", "running"),
    ],
)
def test_retry_revalidates_canonical_state_after_the_terminal_reply(
    tmp_path, terminal, field, value
):
    database, context, calls, reopen = _terminal_recovery(tmp_path, state=terminal)
    bridge = reopen()
    assert bridge.session("lifetime-probe")["state"] == terminal
    queries = {
        "failure_code": "UPDATE game_session SET failure_code=? WHERE id=?",
        "owner": "UPDATE game_session SET owner=? WHERE id=?",
        "game_id": "UPDATE game_session SET game_id=? WHERE id=?",
        "state": "UPDATE game_session SET state=? WHERE id=?",
    }
    with closing(sqlite3.connect(database)) as external:
        external.execute(queries[field], (value, REQUEST))
        external.commit()
    before = context.read_bytes()
    with StateStore(database) as store:
        row = store.get_game_session(REQUEST)
    with pytest.raises(ValueError, match="proven retryable terminal"):
        bridge.launch("lifetime-probe", "library:lifetime-probe", client_request_id="retry")
    assert context.read_bytes() == before and calls == []
    with StateStore(database) as store:
        assert store.get_game_session(REQUEST) == row


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
