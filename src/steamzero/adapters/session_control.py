# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Controle local do processo pelo dono canônico da sessão.

O processo que inicia o emulador continua sendo o dono do lifecycle. Este
módulo só oferece uma porta AF_UNIX efêmera para que a ponte do Launcher envie
intenções ``pause``/``resume`` correlacionadas; o QML nunca recebe PID nem
sinaliza processos diretamente.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import struct
import threading
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from steamzero.core import fs, paths
from steamzero.core.errors import SteamZeroError
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore

if TYPE_CHECKING:
    from steamzero.adapters.session_peripherals import SessionPeripheralControl

MAX_CONTROL_REQUEST = 1024
MAX_CONTROL_RESPONSE = 2048
CONTROL_DIRECTORY = "session-controls"
DIAG_CONTROL_UNAVAILABLE = "AURA-SESSION-CONTROL-UNAVAILABLE-001"
DIAG_CONTROL_REQUEST = "AURA-SESSION-CONTROL-REQUEST-002"
DIAG_CONTROL_FAILED = "AURA-SESSION-CONTROL-FAILED-003"
# D-20: a rota /journey/event já recusa o slot fora da faixa com esta frase e esta
# recuperação (launcher_ui); o canal de sessão e o overlay passam a dizer o mesmo.
SAVE_STATE_SLOT_DETAIL = "O slot de save-state deve estar entre 0 e 999."
SAVE_STATE_SLOT_RECOVERY = "choose-valid-slot"
# D-23: o servidor do canal **não** vive dentro da árvore que a pausa SIGSTOPa —
# ele roda no processo que lançou o jogo (CLI spawned pelo launcher), que continua
# respondendo. O gate mesmo assim vale: o handler de uma ação de periférico
# conversa com o emulador parado, pendura, o cliente expira em 1 s, e o pedido
# fica enfileirado para executar **depois** — contra a recusa que a UI já
# publicou (logs/11:89-90: o saveState "recusado" foi escrito no kill -CONT
# manual). O gate roda no cliente, antes do connect.
E_SESSION_CHANNEL_SUSPENDED = "E-SESSION-CHANNEL-SUSPENDED"
CHANNEL_READY_STATES = frozenset({"launching", "running"})
# D-28: os comandos transitórios conversam com o emulador vivo e valem o mesmo
# gate D-23 dos save-states: em árvore parada o pedido ficaria enfileirado para
# executar depois da recusa publicada.
CHANNEL_LIVE_ACTIONS = frozenset(
    {"saveState", "loadState", "swapDisc", "mute", "screenshot", "fastForward", "rewind"}
)
# D-28: fonte única das portas de ação do backend de sessão. O literal vivia
# dentro de `_dispatch`; extraído sem mudança de comportamento, ele passa a ser
# o contrato que o teste de fronteira do OSD compara com `OSD_ACTIONS`: um
# botão publicado sem porta aqui é a divisão medida pela jornada (D-28).
ACCEPTED_ACTIONS = frozenset(
    {
        "pause",
        "resume",
        "exit",
        "listSaveStates",
        "saveState",
        "loadState",
        "listDiscs",
        "swapDisc",
        "listPeripherals",
        "mute",
        "screenshot",
        "fastForward",
        "rewind",
    }
)

_log = logging.getLogger(__name__)

StoreFactory = Callable[[], StateStore]
SignalProcess = Callable[[int, int], None]
ReadStartTicks = Callable[[int], int | None]
ReadProcessGroupIdentity = Callable[[int], tuple[int, int] | None]
ObserveSession = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class SessionControlRecord:
    id: str
    game_id: str
    state: str


class _InvalidSaveSlot(ValueError):
    """Slot de save-state fora da faixa: recusa de pedido, não falha de operação."""


def _bounded_text(value: Any, *, limit: int = 128) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _peer_is_same_uid(connection: socket.socket) -> bool:
    try:
        _pid, uid, _gid = struct.unpack(
            "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
    except (OSError, struct.error):
        return False
    return bool(int(uid) == os.getuid())


def _read_line(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= MAX_CONTROL_REQUEST:
        chunk = connection.recv(256)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks)
    if len(raw) > MAX_CONTROL_REQUEST or b"\n" not in raw:
        raise ValueError("requisição de controle excede o limite")
    return raw.split(b"\n", 1)[0]


def _process_group_identity(pid: int) -> tuple[int, int] | None:
    """Return (process group, session) for a live pid without guessing on errors."""
    try:
        return os.getpgid(pid), os.getsid(pid)
    except OSError:
        return None


class SessionControlOwner:
    """Implementa pause/retomada/saída dentro do processo que lançou o jogo."""

    def __init__(
        self,
        session_id: str,
        game_id: str,
        pid: int,
        start_ticks: int | None,
        *,
        store_factory: StoreFactory = StateStore,
        read_start_ticks: ReadStartTicks,
        read_process_group_identity: ReadProcessGroupIdentity | None = None,
        signal_process: SignalProcess | None = None,
        peripheral_control: SessionPeripheralControl | None = None,
    ) -> None:
        self.session_id = session_id
        self.game_id = game_id
        self.pid = pid
        self.start_ticks = start_ticks
        self._store_factory = store_factory
        self._read_start_ticks = read_start_ticks
        self._read_process_group_identity = read_process_group_identity or _process_group_identity
        # Sinal de grupo, não de processo: `killpg` alcança toda a árvore do grupo
        # liderado por `self.pid` — o `flatpak run` e seus `bwrap`/retroarch medidos
        # em logs/11 item 6 estão todos ali, porque o jogo é criado com
        # `start_new_session=True` (`adapters/emulation.py` `_spawn_detached`) e
        # `_verify_process_identity` exige que `self.pid` seja o líder (pgid, sid).
        self._signal_process = signal_process or os.killpg
        self._peripheral_control = peripheral_control
        self._lock = threading.RLock()
        # The request owner lives for the session. Keep partial two-signal exit
        # progress so a failed SIGCONT can be retried without sending SIGTERM
        # twice. A new owner that only observes `closing` returns it unchanged.
        self._exit_stage = "idle"
        self._exit_was_suspended = False

    @property
    def current(self) -> SessionControlRecord | None:
        with self._store_factory() as store:
            store.migrate()
            row = store.get_game_session(self.session_id)
        if row is None or row.get("game_id") != self.game_id:
            return None
        return SessionControlRecord(
            id=self.session_id,
            game_id=self.game_id,
            state=str(row.get("state") or "unknown"),
        )

    def suspend(self) -> SessionControlRecord:
        return self._transition_with_signal("suspending", signal.SIGSTOP, "suspended")

    def resume(self) -> SessionControlRecord:
        return self._transition_with_signal("resuming", signal.SIGCONT, "running")

    def request_exit(self, *, confirmed: bool) -> SessionControlRecord:
        """Ask the exact owned session to stop; never escalate to SIGKILL."""
        if confirmed is not True:
            raise RuntimeError("o encerramento da sessão exige confirmação explícita")
        with self._lock:
            with self._store_factory() as store:
                store.migrate()
                row = store.get_game_session(self.session_id)
                if (
                    row is None
                    or row.get("id") != self.session_id
                    or row.get("game_id") != self.game_id
                    or row.get("owner") != SESSION_OWNER
                ):
                    raise RuntimeError("a sessão mudou antes do encerramento")
                state = str(row.get("state") or "unknown")
                if state in {"running", "suspended"}:
                    self._verify_process_identity(row)
                    self._exit_was_suspended = state == "suspended"
                    self._exit_stage = "term"
                    store.transition_game_session(self.session_id, "closing")
                elif state == "closing":
                    self._verify_recorded_identity(row)
                elif state != "closing":
                    raise RuntimeError("a sessão já não está em um estado encerrável")
                if self._exit_stage == "term":
                    self._verify_process_identity(row)
                    self._send_exit_signal(signal.SIGTERM)
                    self._exit_stage = "continue" if self._exit_was_suspended else "complete"
                if self._exit_stage == "continue":
                    # TERM is pending for a stopped process. Continuing only this
                    # verified session lets Linux deliver it; it does not publish
                    # `running` and never targets a general process group.
                    still_owned = self._verify_process_identity(row, allow_exited=True)
                    if still_owned:
                        self._send_exit_signal(signal.SIGCONT)
                    self._exit_stage = "complete"
            updated = self.current
        if updated is None:
            raise RuntimeError("a sessão desapareceu após o pedido de encerramento")
        return updated

    def _verify_recorded_identity(self, row: Mapping[str, Any]) -> None:
        if (
            row.get("id") != self.session_id
            or row.get("game_id") != self.game_id
            or row.get("owner") != SESSION_OWNER
            or row.get("pid") != self.pid
            or row.get("start_ticks") != self.start_ticks
        ):
            raise RuntimeError("a identidade da sessão mudou antes do sinal")

    def _verify_process_identity(
        self, row: Mapping[str, Any], *, allow_exited: bool = False
    ) -> bool:
        self._verify_recorded_identity(row)
        if self.start_ticks is None:
            raise RuntimeError("a identidade do processo da sessão não pôde ser confirmada")
        observed_ticks = self._read_start_ticks(self.pid)
        if observed_ticks is None and allow_exited:
            return False
        if observed_ticks != self.start_ticks:
            raise RuntimeError("a identidade do processo da sessão não pôde ser confirmada")
        if self._read_process_group_identity(self.pid) != (self.pid, self.pid):
            raise RuntimeError("o grupo da sessão não pertence ao processo iniciado")
        return True

    def _send_exit_signal(self, signum: int) -> None:
        try:
            self._signal_process(self.pid, signum)
        except OSError as exc:
            raise RuntimeError(
                "o pedido de encerramento falhou; atualize a sessão e tente novamente"
            ) from exc

    def list_save_states(self) -> Mapping[str, Any]:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece save-state")
        return self._peripheral_control.list_save_states()

    def save_state(self, slot: int) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece save-state")
        self._peripheral_control.save_state(slot)
        return self._require_current()

    def load_state(self, slot: int) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece save-state")
        self._peripheral_control.load_state(slot)
        return self._require_current()

    def toggle_mute(self) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece controle de áudio")
        self._peripheral_control.toggle_mute()
        return self._require_current()

    def take_screenshot(self) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece captura de tela")
        self._peripheral_control.take_screenshot()
        return self._require_current()

    def toggle_fast_forward(self) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece avanço rápido")
        self._peripheral_control.toggle_fast_forward()
        return self._require_current()

    def step_rewind(self) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece rebobinar")
        self._peripheral_control.step_rewind()
        return self._require_current()

    def state_path(self, slot: int) -> Path:
        """O destino que um `saveState` deste slot escreveria — nomeado pelo adapter.

        D-26: a recusa de um pedido já despachado precisa dizer *onde* o arquivo pode
        ter ficado. A sufixação pertence ao adapter (`state_path`); reimplementá-la
        aqui daria ao produto um segundo dono do nome.
        """
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece save-state")
        return self._peripheral_control.state_path(slot)

    def list_discs(self) -> Mapping[str, Any]:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece troca de disco")
        return self._peripheral_control.list_discs()

    def swap_disc(self, disc_id: str) -> SessionControlRecord:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece troca de disco")
        self._peripheral_control.swap_disc(disc_id)
        return self._require_current()

    def list_peripherals(self) -> Mapping[str, Any]:
        if self._peripheral_control is None:
            raise RuntimeError("o adapter desta sessão não oferece periféricos")
        list_peripherals = getattr(self._peripheral_control, "list_peripherals", None)
        if callable(list_peripherals):
            return cast(Mapping[str, Any], list_peripherals())
        # Keep the control socket compatible with adapters deployed before
        # the complete peripheral projection existed.
        list_discs = getattr(self._peripheral_control, "list_discs", None)
        if callable(list_discs):
            return cast(Mapping[str, Any], list_discs())
        raise RuntimeError("o adapter desta sessão não oferece periféricos")

    def _require_current(self) -> SessionControlRecord:
        current = self.current
        if current is None:
            raise RuntimeError("a sessão não está mais disponível")
        return current

    def _transition_with_signal(
        self, intermediate: str, signum: int, target: str
    ) -> SessionControlRecord:
        with self._lock:
            current = self.current
            if current is None or current.state not in {
                "running" if target == "suspended" else "suspended"
            }:
                raise RuntimeError("a sessão não está no estado esperado")
            if self.start_ticks is None or self._read_start_ticks(self.pid) != self.start_ticks:
                raise RuntimeError("a identidade do processo da sessão não pôde ser confirmada")
            with self._store_factory() as store:
                store.migrate()
                row = store.get_game_session(self.session_id)
                if (
                    row is None
                    or row.get("id") != self.session_id
                    or row.get("game_id") != self.game_id
                    or row.get("owner") != SESSION_OWNER
                ):
                    raise RuntimeError("a sessão mudou antes do controle")
                self._verify_process_identity(row)
                store.transition_game_session(self.session_id, intermediate)
                try:
                    self._signal_process(self.pid, signum)
                except OSError:
                    store.transition_game_session(
                        self.session_id,
                        "failed",
                        pid=None,
                        failure_code=DIAG_CONTROL_FAILED,
                    )
                    raise RuntimeError("não foi possível controlar o processo da sessão") from None
                store.transition_game_session(self.session_id, target)
            updated = self.current
        if updated is None:
            raise RuntimeError("a sessão desapareceu após o controle")
        return updated


class SessionControlServer:
    """Servidor efêmero, autenticado por UID e delimitado à sessão criada."""

    def __init__(self, owner: SessionControlOwner, path: Path) -> None:
        self.owner = owner
        self.path = Path(path)
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        fs.ensure_dir(self.path.parent, mode=0o700)
        with suppress(FileNotFoundError):
            fs.remove_file(self.path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.path))
        fs.set_mode(self.path, 0o600)
        server.listen(4)
        server.settimeout(0.2)
        self._socket = server
        self._thread = threading.Thread(target=self._serve, name="steamzero-session-control")
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        server = self._socket
        if server is not None:
            server.close()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        with suppress(FileNotFoundError):
            fs.remove_file(self.path)

    def _serve(self) -> None:
        server = self._socket
        if server is None:
            return
        with server:
            while not self._stop.is_set():
                try:
                    connection, _address = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    return
                with connection:
                    if not _peer_is_same_uid(connection):
                        continue
                    # Toda a troca por conexão tem fronteira de falha própria,
                    # inclusive a escrita da resposta. Um cliente que expira (timeout
                    # de 1 s) e fecha o pipe antes de ler faz o `sendall` estourar
                    # `BrokenPipeError`/EPIPE: isso mata **esta** conexão, nunca o
                    # ouvinte — se o erro escapasse, o `with server:` abaixo fecharia o
                    # socket de escuta enquanto o arquivo `.sock` sobreviveria (só
                    # `close()` o remove), e todo pedido seguinte viraria
                    # `ECONNREFUSED` → "o dono da sessão não respondeu" para sempre
                    # (a cadeia medida de D-23 em logs/11:84-94).
                    try:
                        request = json.loads(_read_line(connection).decode("utf-8"))
                        result = self._dispatch(request)
                        payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
                        connection.sendall(payload[:MAX_CONTROL_RESPONSE].encode("utf-8") + b"\n")
                    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                        with suppress(OSError):
                            refusal = json.dumps(
                                {
                                    "accepted": False,
                                    "diagnostic": DIAG_CONTROL_REQUEST,
                                    "detail": "A requisição da sessão é inválida.",
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            connection.sendall(
                                refusal[:MAX_CONTROL_RESPONSE].encode("utf-8") + b"\n"
                            )
                    except OSError:
                        _log.warning(
                            "o cliente do canal de controle %s desapareceu antes de ler a resposta",
                            self.owner.session_id,
                        )

    def _dispatch(self, request: Any) -> dict[str, Any]:
        allowed = {"sessionId", "gameId", "action", "slot", "discId", "confirmed"}
        if not isinstance(request, dict) or not set(request).issubset(allowed):
            raise ValueError("schema inválido")
        if not {"sessionId", "gameId", "action"}.issubset(request):
            raise ValueError("schema inválido")
        if (
            _bounded_text(request.get("sessionId")) != self.owner.session_id
            or _bounded_text(request.get("gameId")) != self.owner.game_id
        ):
            return {
                "accepted": False,
                "state": "unknown",
                "diagnostic": DIAG_CONTROL_REQUEST,
                "detail": "A sessão não corresponde ao processo controlado.",
            }
        action = _bounded_text(request.get("action"), limit=16)
        confirmed = request.get("confirmed")
        if (action == "exit" and confirmed is not True) or (
            action != "exit" and "confirmed" in request
        ):
            return {
                "accepted": False,
                "state": "unknown",
                "diagnostic": DIAG_CONTROL_REQUEST,
                "detail": "A confirmação só é aceita para o encerramento explícito da sessão.",
            }
        if action not in ACCEPTED_ACTIONS:
            return {
                "accepted": False,
                "state": "unknown",
                "diagnostic": DIAG_CONTROL_REQUEST,
                "detail": "A ação da sessão não é permitida.",
            }
        # Duas metades de falha dentro do mesmo `try` (D-26): o que quebra antes de
        # chamar o adapter não teve nenhum efeito; o que quebra depois pode ter
        # escrito o arquivo do slot mesmo assim.
        dispatched_slot: int | None = None
        try:
            if action == "pause":
                record = self.owner.suspend()
            elif action == "resume":
                record = self.owner.resume()
            elif action == "exit":
                record = self.owner.request_exit(confirmed=True)
            elif action == "mute":
                record = self.owner.toggle_mute()
            elif action == "screenshot":
                record = self.owner.take_screenshot()
            elif action == "fastForward":
                record = self.owner.toggle_fast_forward()
            elif action == "rewind":
                record = self.owner.step_rewind()
            elif action == "listSaveStates":
                current = self.owner.current
                if current is None:
                    raise RuntimeError("a sessão não está mais disponível")
                return {
                    "accepted": True,
                    "state": current.state,
                    "data": self.owner.list_save_states(),
                }
            elif action == "listDiscs":
                current = self.owner.current
                if current is None:
                    raise RuntimeError("a sessão não está mais disponível")
                return {
                    "accepted": True,
                    "state": current.state,
                    "data": self.owner.list_discs(),
                }
            elif action == "listPeripherals":
                current = self.owner.current
                if current is None:
                    raise RuntimeError("a sessão não está mais disponível")
                return {
                    "accepted": True,
                    "state": current.state,
                    "data": self.owner.list_peripherals(),
                }
            elif action in {"saveState", "loadState"}:
                slot = request.get("slot")
                # D-20: o toque de salvar sem galeria chegava sem slot e a recusa
                # caía no genérico pós-falha. Fora da faixa o canal responde com a
                # mesma frase e a mesma recuperação da rota /journey/event; o erro
                # nasce antes de `dispatched_slot`, então a recusa segue podendo
                # afirmar que nenhum pedido chegou ao adapter (D-26).
                if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999:
                    raise _InvalidSaveSlot(SAVE_STATE_SLOT_DETAIL)
                if action == "saveState":
                    # D-26: a partir desta linha o pedido já foi entregue ao adapter;
                    # a recusa deixa de poder afirmar que nada aconteceu.
                    dispatched_slot = slot
                record = (
                    self.owner.save_state(slot)
                    if action == "saveState"
                    else self.owner.load_state(slot)
                )
            else:
                disc_id = request.get("discId")
                if not isinstance(disc_id, str):
                    raise ValueError("disco não informado")
                record = self.owner.swap_disc(disc_id)
        except _InvalidSaveSlot:
            return {
                "accepted": False,
                "state": "unknown",
                "diagnostic": DIAG_CONTROL_REQUEST,
                "detail": SAVE_STATE_SLOT_DETAIL,
                "recoveryAction": SAVE_STATE_SLOT_RECOVERY,
            }
        except Exception:
            current = self.owner.current
            refusal: dict[str, Any] = {
                "accepted": False,
                "state": current.state if current is not None else "unknown",
                "diagnostic": DIAG_CONTROL_FAILED,
                "detail": "A operação da sessão falhou; atualize o overlay e tente novamente.",
            }
            written = self._possible_save_write(dispatched_slot)
            if written is not None:
                refusal["written"] = written
            return refusal
        return {"accepted": True, "state": record.state}

    def _possible_save_write(self, slot: int | None) -> dict[str, Any] | None:
        """O que uma recusa de `saveState` não pode negar: o arquivo que ela pode ter escrito.

        `None` é a resposta honesta quando o pedido **não** chegou ao adapter (slot
        inválido, sessão ausente, sessão sem save-state) ou quando o destino não é
        resolvível: sem caminho declarável, o corpo fica exatamente como era, e um
        diagnóstico nunca pode destruir a recusa que ele tenta completar.
        """
        if slot is None:
            return None
        try:
            state_path = self.owner.state_path(slot)
            return {"slot": slot, "path": str(state_path), "exists": state_path.is_file()}
        except Exception:
            return None


class RemoteSessionControl:
    """Proxy usado pelo adapter da ponte; não conhece PID nem envia sinais."""

    def __init__(self, path: Path, session_id: str, game_id: str, observe: ObserveSession) -> None:
        self._path = Path(path)
        self._session_id = session_id
        self._game_id = game_id
        self._observe = observe

    @property
    def current(self) -> SessionControlRecord | None:
        observed = dict(self._observe(self._game_id))
        if observed.get("sessionId") != self._session_id or observed.get("gameId") != self._game_id:
            return None
        return SessionControlRecord(
            id=self._session_id,
            game_id=self._game_id,
            state=_bounded_text(observed.get("state"), limit=32) or "unknown",
        )

    def suspend(self) -> SessionControlRecord:
        return self._request("pause")

    def resume(self) -> SessionControlRecord:
        return self._request("resume")

    def request_exit(self, *, confirmed: bool) -> SessionControlRecord:
        if confirmed is not True:
            raise RuntimeError("o encerramento da sessão exige confirmação explícita")
        return self._request("exit", confirmed=True)

    def _refuse_if_not_live(self, action: str) -> None:
        """A pausa não congela o canal — quem atende é o processo dono do ciclo de
        vida, pai da árvore SIGSTOPada — mas o handler da ação conversa com um
        emulador parado: o pedido pendura até o timeout do cliente e fica
        enfileirado para executar depois, contra a recusa já publicada. A recusa
        no cliente fecha essa fila antes do connect."""
        record = self.current
        if record is None or record.state not in CHANNEL_READY_STATES:
            raise SteamZeroError(
                E_SESSION_CHANNEL_SUSPENDED,
                detail=f"{action} exige uma sessão viva; o pedido não foi enviado ao emulador.",
            )

    def _request(self, action: str, **extra: Any) -> SessionControlRecord:
        if action in CHANNEL_LIVE_ACTIONS:
            self._refuse_if_not_live(action)
        request: dict[str, Any] = {
            "sessionId": self._session_id,
            "gameId": self._game_id,
            "action": action,
        }
        request.update(extra)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(1.0)
                connection.connect(str(self._path))
                connection.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
                response = json.loads(_read_line(connection).decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("o dono da sessão não respondeu") from exc
        if not isinstance(response, dict) or response.get("accepted") is not True:
            detail = (
                _bounded_text(response.get("detail"), limit=256)
                if isinstance(response, dict)
                else ""
            )
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"o dono da sessão recusou a operação{suffix}")
        response_state = _bounded_text(response.get("state"), limit=32)
        if response_state in {
            "launching",
            "running",
            "suspending",
            "suspended",
            "resuming",
            "closing",
            "closed",
            "failed",
        }:
            # Use the owner's acknowledgement. An exit may terminate the child
            # before a separate read-only observer can revalidate its PID; that
            # observer will publish `closed` when its watcher collects the exit.
            return SessionControlRecord(self._session_id, self._game_id, response_state)
        current = self.current
        if current is None:
            raise RuntimeError("a sessão não está mais disponível")
        return current

    def _request_data(self, action: str) -> Mapping[str, Any]:
        self._refuse_if_not_live(action)
        request = {
            "sessionId": self._session_id,
            "gameId": self._game_id,
            "action": action,
        }
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(1.0)
                connection.connect(str(self._path))
                connection.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
                response = json.loads(_read_line(connection).decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("o dono da sessão não respondeu") from exc
        data = response.get("data") if isinstance(response, dict) else None
        if (
            not isinstance(response, dict)
            or response.get("accepted") is not True
            or not isinstance(data, Mapping)
        ):
            raise RuntimeError("o dono da sessão recusou a consulta")
        return data

    def list_save_states(self) -> Mapping[str, Any]:
        return self._request_data("listSaveStates")

    def save_state(self, slot: int) -> SessionControlRecord:
        return self._request("saveState", slot=slot)

    def load_state(self, slot: int) -> SessionControlRecord:
        return self._request("loadState", slot=slot)

    def list_discs(self) -> Mapping[str, Any]:
        return self._request_data("listDiscs")

    def swap_disc(self, disc_id: str) -> SessionControlRecord:
        return self._request("swapDisc", discId=disc_id)

    def list_peripherals(self) -> Mapping[str, Any]:
        return self._request_data("listPeripherals")

    def toggle_mute(self) -> SessionControlRecord:
        return self._request("mute")

    def take_screenshot(self) -> SessionControlRecord:
        return self._request("screenshot")

    def toggle_fast_forward(self) -> SessionControlRecord:
        return self._request("fastForward")

    def step_rewind(self) -> SessionControlRecord:
        return self._request("rewind")


def control_path(session_id: str, *, root: Path | None = None) -> Path:
    """Retorna o endpoint derivado de um id ULID, sem aceitar caminhos externos."""
    safe_id = _bounded_text(session_id, limit=128)
    if not safe_id or any(character in safe_id for character in "/\\\x00"):
        raise ValueError("sessionId inválido")
    return (root or paths.state_home() / CONTROL_DIRECTORY) / f"{safe_id}.sock"


def resolve_remote_session_control(
    session_id: str,
    game_id: str,
    *,
    observe: ObserveSession,
    root: Path | None = None,
) -> RemoteSessionControl | None:
    try:
        endpoint = control_path(session_id, root=root)
        if not endpoint.is_socket():
            return None
    except (OSError, ValueError):
        return None
    return RemoteSessionControl(endpoint, session_id, game_id, observe)


__all__ = [
    "ACCEPTED_ACTIONS",
    "CHANNEL_READY_STATES",
    "DIAG_CONTROL_FAILED",
    "DIAG_CONTROL_REQUEST",
    "DIAG_CONTROL_UNAVAILABLE",
    "E_SESSION_CHANNEL_SUSPENDED",
    "SAVE_STATE_SLOT_DETAIL",
    "SAVE_STATE_SLOT_RECOVERY",
    "RemoteSessionControl",
    "SessionControlOwner",
    "SessionControlRecord",
    "SessionControlServer",
    "control_path",
    "resolve_remote_session_control",
]
