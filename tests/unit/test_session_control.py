# SPDX-License-Identifier: GPL-3.0-or-later
"""Provas do canal de controle pertencente ao processo da sessão."""

from __future__ import annotations

import json
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
) -> tuple[SessionControlOwner, SessionControlServer, str, str]:
    """Dono + canal reais, com os sinais gravados em `signals` em vez de enviados."""
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(database),
        read_start_ticks=_start_ticks,
        read_process_group_identity=lambda pid: (pid, pid),
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
        peripheral_control=peripheral_control,
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


def test_resume_continues_the_group_the_pause_stopped(tmp_path: Path) -> None:
    """C-4/D-23: retomar alcança a árvore inteira que a pausa parou — o grupo, não só o líder.

    A causa afirmada pelo plano era falsa: o produto **já** sinaliza o grupo completo.
    `signal_process` default é `os.killpg` (este arquivo), `_verify_process_identity`
    exige que o pid gravado seja o líder `(pgid, sid)` — e o jogo é criado com
    `start_new_session=True` (`adapters/emulation.py` `_spawn_detached`), então o
    `flatpak run` e seus `bwrap` externo/interno e retroarch (todos `T` em `logs/11`
    item 6) estão dentro do mesmo grupo que o `SIGSTOP` da pausa atingiu. O `resume`
    refaz exatamente esse caminho: o mesmo grupo, agora com `SIGCONT`.
    """
    signals: list[tuple[int, int]] = []
    _owner, server, session_id, game_id = _owner_and_server(tmp_path, signals=signals)
    remote = resolve_remote_session_control(
        session_id,
        game_id,
        observe=lambda sid: observe_game_session(tmp_path / "state.db", sid),
        root=tmp_path.parent,
    )
    assert remote is not None
    try:
        remote.suspend()
        stopped = list(signals)
        # Não-vacuidade: a pausa sinalizou o grupo do líder gravado — o pid da
        # sessão, verificado como `(pid, pid)` antes de qualquer sinal.
        assert stopped == [(os.getpid(), int(signal.SIGSTOP))]
        signals.clear()

        remote.resume()

        assert {pid for pid, _ in signals} == {pid for pid, _ in stopped}
        assert all(int(sig) == signal.SIGCONT for _, sig in signals)
    finally:
        server.close()

    # O caminho de produção sinaliza o **grupo**: sem injeção, o hook é `os.killpg`,
    # e é isso que faz um único SIGCONT alcançar a árvore do flatpak inteira.
    production_owner = SessionControlOwner(
        session_id,
        game_id,
        os.getpid(),
        _start_ticks(os.getpid()),
        store_factory=lambda: StateStore(tmp_path / "state.db"),
        read_start_ticks=_start_ticks,
    )
    assert production_owner._signal_process is os.killpg


def test_resume_never_signals_a_recycled_or_stale_group_leader(tmp_path: Path) -> None:
    """C-4/D-23: identidade re-verificada antes do sinal — pid reciclado ou grupo
    que não é mais o do líder gravado nunca recebe `SIGCONT`.
    """
    database = tmp_path / "state.db"
    session_id, game_id = _seed_session(database)
    own_pid = os.getpid()
    original_ticks = _start_ticks(own_pid)
    ticks: dict[int, int | None] = {own_pid: original_ticks}
    identities: dict[int, tuple[int, int] | None] = {own_pid: (own_pid, own_pid)}
    signals: list[tuple[int, int]] = []
    owner = SessionControlOwner(
        session_id,
        game_id,
        own_pid,
        original_ticks,
        store_factory=lambda: StateStore(database),
        read_start_ticks=lambda pid: ticks.get(pid),
        read_process_group_identity=lambda pid: identities.get(pid),
        signal_process=lambda pid, signum: signals.append((pid, int(signum))),
    )

    owner.suspend()
    assert signals == [(own_pid, int(signal.SIGSTOP))]
    signals.clear()

    # Reuso de PID: o mesmo número passou a ser outro processo.
    ticks[own_pid] = original_ticks + 1
    with pytest.raises(RuntimeError, match="identidade"):
        owner.resume()
    assert signals == []  # nenhum sinal saiu
    ticks[own_pid] = original_ticks

    # O líder gravado saiu e `(pgid, sid)` deixou de ser o grupo que ele criou:
    # sinalizá-lo atingiria processos de fora da sessão.
    identities[own_pid] = (own_pid + 1, own_pid + 1)
    with pytest.raises(RuntimeError, match="grupo"):
        owner.resume()
    assert signals == []

    # Estado intacto: as recusas não moveram a sessão.
    current = owner.current
    assert current is not None and current.state == "suspended"


def test_vanished_client_does_not_kill_the_control_channel(tmp_path: Path) -> None:
    """C-4/D-23: um cliente que expira antes de ler a resposta não pode fechar o ouvinte.

    É a causa medida do D-23, não a que o plano afirmou: o `sendall` da resposta vive
    fora do `try` do `_serve`, então um `BrokenPipeError` num pipe fechado escapa do
    laço, o `with server:` fecha o socket de escuta, o arquivo `.sock` sobrevive (só
    `close()` o remove), `resolve_remote_session_control` continua achando o canal e
    todo pedido vira `ECONNREFUSED` — o mesmo 409 de `logs/11:87-88` para sempre.
    Servidor e clientes aqui são sockets reais sobre `tmp_path`: a propriedade é a
    sobrevivência do ouvinte, e nenhuma falsificação de servidor a prova.
    """

    class _SlowPeripheral:
        def list_peripherals(self) -> dict[str, object]:
            # Um handler lento é o que faz o cliente de 1 s expirar numa sessão presa
            # (ele conversa com o emulador parado); aqui só garante que o cliente
            # desapareceu ANTES de o servidor escrever a resposta.
            time.sleep(0.3)
            return {"state": "ready"}

    signals: list[tuple[int, int]] = []
    _owner, server, session_id, game_id = _owner_and_server(
        tmp_path, signals=signals, peripheral_control=cast(Any, _SlowPeripheral())
    )
    endpoint = str(control_path(session_id, root=tmp_path.parent))
    try:
        vanished = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        vanished.connect(endpoint)
        vanished.sendall(
            json.dumps(
                {"sessionId": session_id, "gameId": game_id, "action": "listPeripherals"}
            ).encode("utf-8")
            + b"\n"
        )
        vanished.close()  # saiu sem ler: o sendall da resposta vai estourar EPIPE
        time.sleep(0.6)  # margem sobre o handler lento; o sendall já falhou

        remote = resolve_remote_session_control(
            session_id,
            game_id,
            observe=lambda sid: observe_game_session(tmp_path / "state.db", sid),
            root=tmp_path.parent,
        )
        assert remote is not None
        # Um cliente novo, no mesmo caminho de socket, ainda recebe resposta normal.
        data = remote.list_peripherals()
        assert data["state"] == "ready"
    finally:
        server.close()
