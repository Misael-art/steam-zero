# SPDX-License-Identifier: GPL-3.0-or-later
"""Provas do canal de controle pertencente ao processo da sessão."""

from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

from steamzero.adapters import session_control
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.session_control import (
    SessionControlOwner,
    SessionControlServer,
    control_path,
    resolve_remote_session_control,
)
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.adapters.session_peripherals import SessionPeripheralControl
from steamzero.core.errors import SteamZeroError
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


def _owner_and_server(
    tmp_path: Path,
    *,
    signals: list[tuple[int, int]],
    peripheral_control: SessionPeripheralControl | None = None,
    supervised_pids: tuple[int, ...] = (),
    unverifiable_pids: tuple[int, ...] = (),
) -> tuple[SessionControlOwner, SessionControlServer, str, str]:
    """Dono + canal reais, com os sinais gravados em `signals` em vez de enviados.

    `supervised_pids` são os pids dos grupos supervisionados que a unidade 3a registra
    no `suspend`: falsos de propósito, porque nada aqui sinaliza um processo real.
    `unverifiable_pids` ficam registrados mas não lideram o próprio grupo — o conjunto
    de sinais é o que prova que um pid assim nunca é sinalizado.
    """
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    own_pid = os.getpid()
    synthetic_ticks = {pid: 900_000 + index for index, pid in enumerate(supervised_pids)}

    def read_start_ticks(pid: int) -> int | None:
        if pid == own_pid:
            return _start_ticks(pid)
        return synthetic_ticks.get(pid)

    def read_process_group_identity(pid: int) -> tuple[int, int] | None:
        if pid == own_pid:
            return (pid, pid)
        if pid in unverifiable_pids:
            # Vivo, porém em grupo de outro processo: o killpg atingiria outro jogo.
            return (pid + 1, pid)
        if pid in synthetic_ticks:
            return (pid, pid)
        return None

    owner = SessionControlOwner(
        session_id,
        game_id,
        own_pid,
        _start_ticks(own_pid),
        store_factory=lambda: StateStore(database),
        read_start_ticks=read_start_ticks,
        read_process_group_identity=read_process_group_identity,
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
        peripheral_control=peripheral_control,
        supervised_pids=supervised_pids,
    )
    server = SessionControlServer(owner, control_path(session_id, root=tmp_path.parent))
    server.start()
    return owner, server, session_id, game_id


def test_save_state_while_suspended_never_reaches_the_control_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-23: um pedido entregue a uma árvore parada executa depois, contra a recusa publicada."""
    signals: list[tuple[int, int]] = []
    connections: list[str] = []

    class SpySocket(socket.socket):
        """O socket do stdlib usa __slots__; o connect só pode ser observado por subclasse."""

        def connect(self, address: str) -> None:
            connections.append(address)
            super().connect(address)

    def spy(*args: Any, **kwargs: Any) -> socket.socket:
        # `accept()` reconecta a conexão aceita via socket(family, type, proto, fileno=…).
        return SpySocket(*args, **kwargs)

    monkeypatch.setattr(session_control.socket, "socket", spy)
    _owner, server, session_id, game_id = _owner_and_server(tmp_path, signals=signals)
    try:
        database = tmp_path / "state.db"
        remote = resolve_remote_session_control(
            session_id,
            game_id,
            observe=lambda sid: observe_game_session(database, sid),
            root=tmp_path.parent,
        )
        assert remote is not None
        connections.clear()  # o resolve/observe do caminho de subida não conta
        remote.suspend()
        # O espião precisa ter visto o connect real do pause; sem isso a asserção
        # vazia abaixo seria satisfeita por um spy desligado.
        assert connections == [str(control_path(session_id, root=tmp_path.parent))]
        signals.clear()
        connections.clear()

        with pytest.raises(SteamZeroError) as refusal:
            remote.save_state(1)

        assert refusal.value.code == "E-SESSION-CHANNEL-SUSPENDED"
        assert connections == []  # o socket do canal nunca foi aberto
        assert signals == []  # nem um sinal escondido atrás do pedido
    finally:
        server.close()


def test_resume_continues_every_group_the_pause_stopped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """C-4/D-23: retomar tem de alcançar o supervisor externo que a pausa parou."""
    signals: list[tuple[int, int]] = []
    supervised = (900_001, 900_002)
    foreign_group = 900_003
    _owner, server, session_id, game_id = _owner_and_server(
        tmp_path,
        signals=signals,
        supervised_pids=(*supervised, foreign_group),
        unverifiable_pids=(foreign_group,),
    )
    remote = resolve_remote_session_control(
        session_id,
        game_id,
        observe=lambda sid: observe_game_session(tmp_path / "state.db", sid),
        root=tmp_path.parent,
    )
    assert remote is not None
    try:
        with caplog.at_level(logging.WARNING, logger="steamzero.adapters.session_control"):
            remote.suspend()
        stopped = {pid for pid, _ in signals}
        # Não-vacuidade: sem o registro, `stopped` seria só o pid da sessão e a
        # igualdade abaixo passaria sem provar nada — é exatamente o caso medido em
        # `logs/11` item 6, em que o bwrap externo ficou em `T` e o produto não o
        # alcançava.
        assert set(supervised) <= stopped
        assert foreign_group not in stopped
        assert str(foreign_group) in caplog.text  # a recusa de sinalizar é registrada
        signals.clear()

        remote.resume()

        assert {pid for pid, _ in signals} == stopped
        assert all(int(sig) == signal.SIGCONT for _, sig in signals)
    finally:
        server.close()


def test_resume_skips_a_supervised_pid_that_changed_identity(tmp_path: Path) -> None:
    """3a: reuso de PID não ganha sinal — só continua quem a pausa parou verificando."""
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    own_pid = os.getpid()
    supervised = (900_010, 900_011)
    ticks: dict[int, int | None] = {
        own_pid: _start_ticks(own_pid),
        900_010: 71,
        900_011: 72,
    }
    identities: dict[int, tuple[int, int] | None] = {
        own_pid: (own_pid, own_pid),
        900_010: (900_010, 900_010),
        900_011: (900_011, 900_011),
    }
    signals: list[tuple[int, int]] = []
    owner = SessionControlOwner(
        session_id,
        game_id,
        own_pid,
        ticks[own_pid],
        store_factory=lambda: StateStore(database),
        read_start_ticks=lambda pid: ticks.get(pid),
        read_process_group_identity=lambda pid: identities.get(pid),
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
        supervised_pids=supervised,
    )

    owner.suspend()
    assert {pid for pid, _ in signals} == {own_pid, *supervised}
    signals.clear()

    # 900_011 saiu e o pid foi reutilizado por outro processo, de outro grupo.
    ticks[900_011] = 99
    identities[900_011] = (5_000, 5_000)

    assert owner.resume().state == "running"

    resumed = {pid for pid, _ in signals}
    assert resumed == {own_pid, 900_010}
    assert all(int(signum) == signal.SIGCONT for _, signum in signals)


def test_request_exit_continues_the_recorded_supervised_groups(tmp_path: Path) -> None:
    """D-23: o encerramento de uma sessão suspensa continua o conjunto parado, não só o líder."""
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    own_pid = os.getpid()
    ticks: dict[int, int | None] = {own_pid: _start_ticks(own_pid), 900_020: 81}
    signals: list[tuple[int, int]] = []
    owner = SessionControlOwner(
        session_id,
        game_id,
        own_pid,
        ticks[own_pid],
        store_factory=lambda: StateStore(database),
        read_start_ticks=lambda pid: ticks.get(pid),
        read_process_group_identity=lambda pid: (pid, pid) if pid in ticks else None,
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
        supervised_pids=(900_020,),
    )

    owner.suspend()
    signals.clear()

    assert owner.request_exit(confirmed=True).state == "closing"

    assert signals == [
        (own_pid, signal.SIGTERM),
        (own_pid, signal.SIGCONT),
        (900_020, signal.SIGCONT),
    ]
