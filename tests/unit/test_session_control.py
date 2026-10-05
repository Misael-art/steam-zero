# SPDX-License-Identifier: GPL-3.0-or-later
"""Provas do canal de controle pertencente ao processo da sessão."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.session_control import (
    SessionControlOwner,
    SessionControlServer,
    control_path,
    resolve_remote_session_control,
)
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore


def _start_ticks(pid: int) -> int:
    fields = Path(f"/proc/{pid}/stat").read_text().rpartition(") ")[2].split()
    return int(fields[19])


def _seed_session(
    database: Path, *, pid: int | None = None, start_ticks: int | None = None
) -> tuple[str, str]:
    session_id, game_id = "session-control-1", "game-control-1"
    process_id = os.getpid() if pid is None else pid
    process_start_ticks = _start_ticks(process_id) if start_ticks is None else start_ticks
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(
            {
                "id": session_id,
                "game_id": game_id,
                "owner": SESSION_OWNER,
                "state": "launching",
            }
        )
        store.transition_game_session(
            session_id,
            "running",
            pid=process_id,
            start_ticks=process_start_ticks,
        )
    return session_id, game_id


def _process_state(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rpartition(") ")[2].split()
    except FileNotFoundError:
        return None
    return fields[0] if fields else None


def _wait_process_state(pid: int, expected: str, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _process_state(pid) == expected:
            return True
        time.sleep(0.01)
    return _process_state(pid) == expected


class _PeripheralControl:
    def list_peripherals(self) -> dict[str, object]:
        return {
            "state": "ready",
            "selectedBezel": "aura-default",
            "bezels": [
                {
                    "id": "aura-default",
                    "label": "AURA Cinema",
                    "assetUrl": "asset://bezels/aura-bezel.svg",
                    "available": True,
                    "selected": True,
                }
            ],
            "fade": {"phase": "idle", "progress": 0.0, "durationMs": 180},
        }


def test_remote_control_uses_owner_transitions_and_never_signals_from_ui(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    observed_signals: list[tuple[int, int]] = []
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid, pid),
        signal_process=lambda pid, signum: observed_signals.append((pid, signum)),
    )
    socket_root = tmp_path.parent
    server = SessionControlServer(owner, control_path(session_id, root=socket_root))
    server.start()
    try:

        def observe(requested: str) -> dict[str, object]:
            return observe_game_session(database, requested)

        remote = resolve_remote_session_control(
            session_id, game_id, observe=observe, root=socket_root
        )
        assert remote is not None
        overlay = SessionOverlayAdapter(
            observe,
            lambda _session, _game: cast(Any, remote),
        )

        paused = overlay.dispatch(game_id, session_id, "pause")
        resumed = overlay.dispatch(game_id, session_id, "pause")
        exit_pending = overlay.dispatch(game_id, session_id, "exit", confirmed=True)
        duplicate_exit = overlay.dispatch(game_id, session_id, "exit", confirmed=True)

        assert paused.accepted is True
        assert paused.state == "suspended"
        assert resumed.accepted is True
        assert resumed.state == "running"
        assert exit_pending.accepted is True
        assert exit_pending.confirmed is False
        assert exit_pending.state == "closing"
        assert duplicate_exit.accepted is True
        assert duplicate_exit.state == "closing"
        assert observed_signals == [
            (os.getpid(), signal.SIGSTOP),
            (os.getpid(), signal.SIGCONT),
            (os.getpid(), signal.SIGTERM),
        ]
    finally:
        server.close()
    assert not server.path.exists()


def test_control_channel_rejects_stale_identity_without_transition(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        signal_process=lambda _pid, _signum: None,
    )
    socket_root = tmp_path.parent
    server = SessionControlServer(owner, control_path(session_id, root=socket_root))
    server.start()
    try:

        def observe(requested: str) -> dict[str, object]:
            return observe_game_session(database, requested)

        remote = resolve_remote_session_control(
            session_id, "other-game", observe=observe, root=socket_root
        )
        assert remote is not None
        with pytest.raises(RuntimeError, match="recusou"):
            remote.suspend()
        with StateStore(database) as store:
            row = store.get_game_session(session_id)
            assert row is not None
            assert row["state"] == "running"
    finally:
        server.close()


def test_exit_rejects_unowned_group_and_stale_process_identity(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    observed_signals: list[tuple[int, int]] = []
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid + 1, pid),
        signal_process=lambda pid, signum: observed_signals.append((pid, signum)),
    )
    with pytest.raises(RuntimeError, match="grupo"):
        owner.request_exit(confirmed=True)
    assert observed_signals == []
    with StateStore(database) as store:
        row = store.get_game_session(session_id)
        assert row is not None and row["state"] == "running"

    stale_owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()) + 1,
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid, pid),
        signal_process=lambda pid, signum: observed_signals.append((pid, signum)),
    )
    with pytest.raises(RuntimeError, match="identidade"):
        stale_owner.request_exit(confirmed=True)
    assert observed_signals == []


def test_failed_exit_signal_stays_pending_and_retries_without_false_success(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    observed_signals: list[tuple[int, int]] = []

    def fail_once(pid: int, signum: int) -> None:
        observed_signals.append((pid, signum))
        if len(observed_signals) == 1:
            raise OSError("synthetic signal failure")

    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid, pid),
        signal_process=fail_once,
    )
    with pytest.raises(RuntimeError, match="tente novamente"):
        owner.request_exit(confirmed=True)
    current = owner.current
    assert current is not None and current.state == "closing"
    assert owner.request_exit(confirmed=True).state == "closing"
    assert observed_signals == [
        (os.getpid(), signal.SIGTERM),
        (os.getpid(), signal.SIGTERM),
    ]


def test_control_path_does_not_accept_path_injection() -> None:
    try:
        control_path("../outside")
    except ValueError as exc:
        assert "sessionId" in str(exc)
    else:
        raise AssertionError("session id inválido foi aceito")


def test_remote_control_projects_complete_session_peripherals(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        signal_process=lambda _pid, _signum: None,
        peripheral_control=cast(Any, _PeripheralControl()),
    )
    socket_root = tmp_path.parent
    server = SessionControlServer(owner, control_path(session_id, root=socket_root))
    server.start()
    try:
        remote = resolve_remote_session_control(
            session_id,
            game_id,
            observe=lambda requested: observe_game_session(database, requested),
            root=socket_root,
        )
        assert remote is not None
        data = remote.list_peripherals()
        assert data["selectedBezel"] == "aura-default"
        assert data["bezels"][0]["assetUrl"] == "asset://bezels/aura-bezel.svg"
    finally:
        server.close()


@pytest.mark.parametrize("start_suspended", [False, True], ids=["running", "suspended"])
def test_confirmed_exit_terminates_only_the_owned_real_process_group(
    tmp_path: Path, start_suspended: bool
) -> None:
    """A paused session must receive TERM and be allowed to process it."""
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert os.getpgid(child.pid) == child.pid
        assert os.getsid(child.pid) == child.pid
        database = tmp_path / "state.db"
        child_start_ticks = _start_ticks(child.pid)
        session_id, game_id = _seed_session(database, pid=child.pid, start_ticks=child_start_ticks)
        observed_signals: list[tuple[int, int]] = []
        owner = SessionControlOwner(
            session_id,
            game_id,
            child.pid,
            child_start_ticks,
            store_factory=lambda: StateStore(database),
            read_start_ticks=lambda pid: _start_ticks(pid) if _process_state(pid) else None,
            signal_process=lambda pid, signum: _signal_test_child(
                child, pid, signum, observed_signals
            ),
        )
        # AF_UNIX paths are bounded; share only the pytest-owned short ancestor.
        socket_root = tmp_path.parent.parent
        server = SessionControlServer(owner, control_path(session_id, root=socket_root))
        server.start()

        def observe(requested: str) -> dict[str, Any] | None:
            return observe_game_session(database, requested)

        remote = resolve_remote_session_control(
            session_id, game_id, observe=observe, root=socket_root
        )
        assert remote is not None
        overlay = SessionOverlayAdapter(
            observe,
            lambda requested_session, requested_game: (
                remote if (requested_session, requested_game) == (session_id, game_id) else None
            ),
        )
        if start_suspended:
            paused = overlay.dispatch(game_id, session_id, "pause")
            assert paused.accepted and paused.state == "suspended"
            assert _wait_process_state(child.pid, "T")

        result = overlay.dispatch(game_id, session_id, "exit", confirmed=True)
        assert result.accepted and result.state == "closing"
        assert result.confirmed is False
        terminated = False
        try:
            child.wait(timeout=1.0)
            terminated = True
        except subprocess.TimeoutExpired:
            pass
        assert terminated, (
            "the confirmed exit left the owned process alive; "
            f"start_suspended={start_suspended}, process_state={_process_state(child.pid)}"
        )
        # The request owner cannot publish a terminal state; the observer owns it.
        current = owner.current
        assert current is not None and current.state == "closing"
        duplicate = remote.request_exit(confirmed=True)
        assert duplicate.state == "closing"
        assert [signum for _pid, signum in observed_signals] == (
            [signal.SIGSTOP, signal.SIGTERM, signal.SIGCONT]
            if start_suspended
            else [signal.SIGTERM]
        )
    finally:
        if "server" in locals():
            server.close()
        if child.poll() is None:
            # Cleanup is restricted to this test's own new session/process group.
            for signum in (signal.SIGCONT, signal.SIGTERM):
                try:
                    os.killpg(child.pid, signum)
                except ProcessLookupError:
                    break
            child.wait(timeout=3.0)


def _signal_test_child(
    child: subprocess.Popen[bytes],
    pid: int,
    signum: int,
    observed: list[tuple[int, int]],
) -> None:
    assert pid == child.pid
    observed.append((pid, signum))
    os.killpg(pid, signum)
