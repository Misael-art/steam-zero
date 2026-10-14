# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Adapter bounded entre o lifecycle de sessão e o overlay AURA.

Este módulo é a autoridade de execução do overlay. A Theme Engine recebe apenas
um read model e intents semânticos; nunca recebe um processo, argv, caminho ou
objeto de gerenciador para executar por conta própria.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from steamzero.adapters.session_control import (
    E_SESSION_CHANNEL_SUSPENDED,
    SAVE_STATE_SLOT_DETAIL,
)
from steamzero.domain.save_states import resolve_save_state_gallery, unavailable_gallery
from steamzero.domain.session_overlay import (
    OSD_ACTIONS,
    OverlayIntent,
    request_overlay_action,
)
from steamzero.domain.session_peripherals import (
    resolve_session_peripherals,
    unavailable_peripherals,
)

SESSION_ACTIONS = frozenset({"pause"})
UNSUPPORTED_REASON = "Esta ação ainda não possui adapter de sessão."
DIAG_SESSION_MISMATCH = "AURA-SESSION-ADAPTER-001"
DIAG_SESSION_UNAVAILABLE = "AURA-SESSION-ADAPTER-002"
DIAG_ACTION_FAILED = "AURA-SESSION-ADAPTER-003"
DIAG_INVALID_INTENT = "AURA-SESSION-ADAPTER-004"
DIAG_EXIT_CONFIRMATION_REQUIRED = "AURA-SESSION-ADAPTER-005"
DIAG_EXIT_PENDING = "AURA-SESSION-ADAPTER-006"
DIAG_CHANNEL_SUSPENDED = "AURA-SESSION-ADAPTER-007"
SUSPENDED_CHANNEL_REASON = "A sessão está suspensa; retome antes de salvar."
SUSPENDED_CHANNEL_DETAIL = "A sessão está suspensa; o pedido não foi enviado ao emulador."
SUSPENDED_CHANNEL_NEXT_ACTION = "Retome a sessão e tente novamente."
CHANNEL_SUSPENDED_CAPABILITY_ACTIONS = ("saveState", "loadState", "swapDisc")
# D-28: comandos e leituras que falam com o emulador vivo. Valem o mesmo gate
# D-23 da gravação de estado — em árvore parada a recusa é publicada antes do
# toque, nunca uma oferta que enfileira efeito para depois.
SUSPENDED_COMMAND_REASON = "A sessão está suspensa; retome antes de enviar um pedido ao emulador."
CHANNEL_SUSPENDED_COMMAND_ACTIONS = (
    "mute",
    "screenshot",
    "fastForward",
    "rewind",
    "listSaveStates",
    "listDiscs",
    "listPeripherals",
)
EPHEMERAL_ACTION_METHODS = {
    "mute": "toggle_mute",
    "screenshot": "take_screenshot",
    "fastForward": "toggle_fast_forward",
    "rewind": "step_rewind",
}
READ_ACTION_METHODS = {
    "listSaveStates": "list_save_states",
    "listDiscs": "list_discs",
    "listPeripherals": "list_peripherals",
}
NO_PORT_REASON = "O adapter desta sessão não oferece esta operação."
NON_ACTIVE_REASON = "A sessão não está em um estado que aceite pedidos ao emulador."
MAX_DETAIL_LENGTH = 240


class SessionRecord(Protocol):
    id: str
    game_id: str
    state: str


class SessionControl(Protocol):
    """Parte mínima do SessionManager necessária para o overlay."""

    @property
    def current(self) -> SessionRecord | None: ...

    def suspend(self) -> SessionRecord: ...

    def resume(self) -> SessionRecord: ...

    def request_exit(self, *, confirmed: bool) -> SessionRecord: ...


class SaveStateControl(Protocol):
    """Optional save-state surface owned by the concrete session adapter."""

    def list_save_states(self) -> Sequence[Mapping[str, Any]]: ...

    def save_state(self, slot: int) -> SessionRecord: ...

    def load_state(self, slot: int) -> SessionRecord: ...


@dataclass(frozen=True)
class SessionActionDispatch:
    """Resultado serializável de uma tentativa de ação sem efeito implícito."""

    accepted: bool
    game_id: str
    session_id: str
    operation: str | None
    state: str
    slot: int | None = None
    disc_id: str | None = None
    diagnostic: str | None = None
    detail: str = ""
    confirmed: bool = False
    next_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "accepted": self.accepted,
            "gameId": self.game_id,
            "sessionId": self.session_id,
            "operation": self.operation,
            "state": self.state,
            "diagnostic": self.diagnostic,
            "detail": self.detail,
            "confirmed": self.confirmed,
        }
        if self.slot is not None:
            result["slot"] = self.slot
        if self.disc_id is not None:
            result["discId"] = self.disc_id
        if self.next_action:
            result["nextAction"] = self.next_action
        return result


def _text(value: Any, *, fallback: str = "", limit: int = MAX_DETAIL_LENGTH) -> str:
    if not isinstance(value, str):
        return fallback
    return value.strip()[:limit]


class SessionOverlayAdapter:
    """Publica a sessão observada e executa somente operações allowlisted.

    ``observe`` deve ser a leitura canônica da sessão e ``resolve_control``
    deve devolver o gerenciador que já é dono daquele ``sessionId``/``gameId``.
    O adapter não cria outro gerenciador e não faz spawn, kill ou acesso a disco.
    """

    def __init__(
        self,
        observe: Callable[[str], Mapping[str, Any]],
        resolve_control: Callable[[str, str], SessionControl | None],
    ) -> None:
        self._observe = observe
        self._resolve_control = resolve_control

    def read_model(
        self,
        game_id: str,
        *,
        visible: bool = False,
        focused_action: str = "",
    ) -> dict[str, Any]:
        """Converte a observação em um read model completo para a Theme Engine."""

        observed = dict(self._observe(game_id))
        session_game_id = _text(observed.get("gameId"), limit=128)
        session_id = _text(observed.get("sessionId"), limit=128)
        state = _text(observed.get("state"), fallback="unknown", limit=32)
        consistent = session_game_id == game_id and bool(session_id)
        control = self._matching_control(session_id, game_id) if consistent else None
        pause_available = control is not None and state in {"running", "suspended"}
        exit_method = getattr(control, "request_exit", None)
        exit_available = callable(exit_method) and state in {"running", "suspended", "closing"}
        gallery, save_available, load_available = self._save_state_surface(control, state)
        peripherals, disc_available = self._peripheral_surface(control, state)
        capabilities: dict[str, dict[str, Any]] = {
            action_id: {
                "available": (
                    (action_id in SESSION_ACTIONS and pause_available)
                    or (action_id == "exit" and exit_available)
                ),
                "reason": (
                    ""
                    if (action_id in SESSION_ACTIONS and pause_available)
                    or (action_id == "exit" and exit_available)
                    else (
                        "A saída exige uma sessão controlável e confirmação explícita."
                        if action_id == "exit"
                        else UNSUPPORTED_REASON
                    )
                ),
            }
            for action_id in OSD_ACTIONS
        }
        if not consistent:
            reason = (
                "A observação da sessão não corresponde ao jogo solicitado."
                if session_id
                else "Nenhuma sessão controlável foi observada."
            )
            capabilities["pause"] = {"available": False, "reason": reason}
        elif not pause_available:
            capabilities["pause"] = {
                "available": False,
                "reason": "A sessão não está em um estado pausável.",
            }
        capabilities["saveState"] = {
            "available": save_available,
            "reason": (
                "" if save_available else gallery.reason or "O adapter não oferece save-state."
            ),
        }
        capabilities["loadState"] = {
            "available": load_available,
            "reason": (
                ""
                if load_available
                else gallery.reason or "Nenhum save-state compatível está disponível."
            ),
        }
        capabilities["swapDisc"] = {
            "available": disc_available,
            "reason": "" if disc_available else peripherals.reason,
        }
        for action_id, method_name in EPHEMERAL_ACTION_METHODS.items():
            method = getattr(control, method_name, None) if control is not None else None
            available = callable(method) and state in {"running", "suspended"}
            reason = (
                "" if available else (NO_PORT_REASON if not callable(method) else NON_ACTIVE_REASON)
            )
            capabilities[action_id] = {"available": available, "reason": reason}
        for action_id, method_name in READ_ACTION_METHODS.items():
            method = getattr(control, method_name, None) if control is not None else None
            available = callable(method) and state in {"running", "suspended"}
            reason = (
                "" if available else (NO_PORT_REASON if not callable(method) else NON_ACTIVE_REASON)
            )
            capabilities[action_id] = {"available": available, "reason": reason}
        resume_available = control is not None and state == "suspended"
        capabilities["resume"] = {
            "available": resume_available,
            "reason": "" if resume_available else "A sessão não está suspensa para retomar.",
        }
        if state == "suspended":
            # D-23: o canal de uma árvore parada adia o pedido em vez de recusá-lo.
            # A superfície publica a recusa antes de a ação parecer alcançável —
            # foi assim que a "Galeria de saves" travou a sessão da jornada física.
            for action_id in CHANNEL_SUSPENDED_CAPABILITY_ACTIONS:
                capabilities[action_id] = {"available": False, "reason": SUSPENDED_CHANNEL_REASON}
            for action_id in CHANNEL_SUSPENDED_COMMAND_ACTIONS:
                capabilities[action_id] = {"available": False, "reason": SUSPENDED_COMMAND_REASON}
        result_session = {
            "gameId": game_id,
            "sessionId": session_id or None,
            "state": state,
        }
        if observed.get("diagnostic"):
            result_session["diagnostic"] = _text(observed["diagnostic"], limit=64)
        return {
            "session": result_session,
            "osd": {
                "visible": visible,
                "focusedAction": focused_action,
                "capabilities": capabilities,
            },
            "saveStates": gallery.to_dict(),
            "peripherals": peripherals.to_dict(),
        }

    def dispatch(
        self,
        game_id: str,
        session_id: str,
        action_id: str,
        slot: int | None = None,
        disc_id: str | None = None,
        confirmed: bool = False,
    ) -> SessionActionDispatch:
        """Valida correlação/capacidade e encaminha pause ou resume ao dono."""

        if not _text(game_id, limit=128) or not _text(session_id, limit=128):
            return SessionActionDispatch(
                accepted=False,
                game_id=_text(game_id, limit=128),
                session_id=_text(session_id, limit=128),
                operation=None,
                state="unknown",
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_INVALID_INTENT,
                detail="gameId e sessionId são obrigatórios.",
            )
        if action_id == "exit" and confirmed is not True:
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation="exit",
                state="unknown",
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_EXIT_CONFIRMATION_REQUIRED,
                detail="Confirme que o jogo não tem progresso pendente antes de sair.",
            )
        model = self.read_model(game_id, visible=True)
        session = model["session"]
        observed_id = session.get("sessionId")
        observed_state = _text(session.get("state"), fallback="unknown", limit=32)
        if observed_id != session_id or session.get("gameId") != game_id:
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=None,
                state=observed_state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_SESSION_MISMATCH,
                detail="A sessão mudou; atualize o overlay antes de tentar novamente.",
            )

        requested = request_overlay_action(model, action_id)
        if not requested.accepted or requested.intent is None:
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=(requested.action.operation if requested.action else None),
                state=observed_state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=requested.diagnostic,
                detail=(requested.action.reason if requested.action else "Ação não reconhecida."),
            )

        intent = requested.intent
        control = self._matching_control(session_id, game_id)
        if control is None:
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=intent.operation,
                state=observed_state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_SESSION_UNAVAILABLE,
                detail="O gerenciador canônico da sessão não está disponível.",
            )
        try:
            updated = self._execute(
                intent, control, slot=slot, disc_id=disc_id, confirmed=confirmed
            )
        except Exception as exc:  # boundary: transforma falha de adapter em estado recuperável
            if getattr(exc, "code", None) == E_SESSION_CHANNEL_SUSPENDED:
                # Gate D-23 no cliente: o pedido morreu antes do connect, então o
                # corpo publicado declara a recusa e a única recuperação possível.
                return SessionActionDispatch(
                    accepted=False,
                    game_id=game_id,
                    session_id=session_id,
                    operation=intent.operation,
                    state=_text(
                        getattr(control.current, "state", None),
                        fallback=observed_state,
                        limit=32,
                    ),
                    slot=slot,
                    disc_id=disc_id,
                    diagnostic=DIAG_CHANNEL_SUSPENDED,
                    detail=SUSPENDED_CHANNEL_DETAIL,
                    next_action=SUSPENDED_CHANNEL_NEXT_ACTION,
                )
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=intent.operation,
                state=_text(
                    getattr(control.current, "state", None),
                    fallback=observed_state,
                    limit=32,
                ),
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_ACTION_FAILED,
                detail=_text(str(exc), fallback="A operação da sessão falhou."),
            )
        state = _text(getattr(updated, "state", None), fallback=observed_state, limit=32)
        if intent.operation == "exit" and state not in {"closing", "closed"}:
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=intent.operation,
                state=state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_ACTION_FAILED,
                detail="O adapter não confirmou o estado de encerramento.",
            )
        if intent.operation == "pause" and state != "suspended":
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=intent.operation,
                state=state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_ACTION_FAILED,
                detail="O adapter não confirmou o estado pausado.",
            )
        if intent.operation == "resume" and state != "running":
            return SessionActionDispatch(
                accepted=False,
                game_id=game_id,
                session_id=session_id,
                operation=intent.operation,
                state=state,
                slot=slot,
                disc_id=disc_id,
                diagnostic=DIAG_ACTION_FAILED,
                detail="O adapter não confirmou o estado em execução.",
            )
        return SessionActionDispatch(
            accepted=True,
            game_id=game_id,
            session_id=session_id,
            operation=intent.operation,
            state=state,
            slot=slot,
            disc_id=disc_id,
            diagnostic=(
                DIAG_EXIT_PENDING if intent.operation == "exit" and state != "closed" else None
            ),
            detail=(
                "Pedido de encerramento enviado; aguardando o observer confirmar closed."
                if intent.operation == "exit" and state != "closed"
                else ""
            ),
            confirmed=(state == "closed" if intent.operation == "exit" else True),
        )

    @staticmethod
    def _peripheral_surface(control: SessionControl | None, state: str) -> tuple[Any, bool]:
        if control is None:
            return unavailable_peripherals("Nenhuma sessão controlável foi observada."), False
        list_peripherals = getattr(control, "list_peripherals", None)
        if not callable(list_peripherals):
            list_peripherals = getattr(control, "list_discs", None)
        if not callable(list_peripherals):
            return unavailable_peripherals(
                "O adapter desta sessão não oferece troca de disco."
            ), False
        try:
            raw = list_peripherals()
        except Exception as exc:  # boundary: peripheral failure remains visible
            return unavailable_peripherals(
                _text(str(exc), fallback="A troca de disco falhou.")
            ), False
        peripheral = resolve_session_peripherals(raw)
        available = state in {"running", "suspended"} and len(peripheral.discs) > 1
        return peripheral, available

    @staticmethod
    def _save_state_surface(control: SessionControl | None, state: str) -> tuple[Any, bool, bool]:
        if control is None:
            return unavailable_gallery("Nenhuma sessão controlável foi observada."), False, False
        list_states = getattr(control, "list_save_states", None)
        save = getattr(control, "save_state", None)
        load = getattr(control, "load_state", None)
        if not callable(list_states):
            return (
                unavailable_gallery("O adapter desta sessão não oferece save-state."),
                False,
                False,
            )
        try:
            raw_states = list_states()
        except Exception as exc:  # boundary: read failure remains visible and recoverable
            message = _text(str(exc), fallback="Não foi possível consultar os save-states.")
            gallery = resolve_save_state_gallery(
                {"state": "error", "reason": message, "entries": []},
                save_available=False,
                load_available=False,
            )
            return gallery, False, False
        active = state in {"running", "suspended"}
        gallery = resolve_save_state_gallery(
            raw_states,
            save_available=active and callable(save),
            load_available=active and callable(load),
        )
        return gallery, active and callable(save), gallery.load_available

    def _matching_control(self, session_id: str, game_id: str) -> SessionControl | None:
        control = self._resolve_control(session_id, game_id)
        if control is None:
            return None
        current = control.current
        if current is None or current.id != session_id or current.game_id != game_id:
            return None
        return control

    @staticmethod
    def _execute(
        intent: OverlayIntent,
        control: SessionControl,
        *,
        slot: int | None,
        disc_id: str | None,
        confirmed: bool,
    ) -> SessionRecord:
        if intent.action_id == "exit":
            if confirmed is not True:
                raise ValueError("o encerramento da sessão exige confirmação explícita")
            current = control.current
            if current is None or current.state not in {"running", "suspended", "closing"}:
                raise ValueError("a sessão não está disponível para encerramento")
            method = getattr(control, "request_exit", None)
            if not callable(method):
                raise RuntimeError("O adapter desta sessão não oferece encerramento.")
            return cast(Callable[..., SessionRecord], method)(confirmed=True)
        if intent.action_id in {"saveState", "loadState"}:
            if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999:
                # D-20: mesma frase e faixa da rota /journey/event (launcher_ui);
                # a recusa da rota de sessão não pode dizer algo diferente.
                raise ValueError(SAVE_STATE_SLOT_DETAIL)
            method = getattr(
                control,
                "save_state" if intent.action_id == "saveState" else "load_state",
                None,
            )
            if not callable(method):
                raise RuntimeError("O adapter desta sessão não oferece esta operação.")
            current = control.current
            if current is None or current.state not in {"running", "suspended"}:
                raise ValueError("a sessão não está disponível para save-state")
            return cast(Callable[[int], SessionRecord], method)(slot)
        if intent.action_id == "swapDisc":
            if not isinstance(disc_id, str) or not disc_id:
                raise ValueError("disco não informado")
            method = getattr(control, "swap_disc", None)
            if not callable(method):
                raise RuntimeError("O adapter desta sessão não oferece troca de disco.")
            current = control.current
            if current is None or current.state not in {"running", "suspended"}:
                raise ValueError("a sessão não está disponível para troca de disco")
            return cast(Callable[[str], SessionRecord], method)(disc_id)
        if intent.action_id in EPHEMERAL_ACTION_METHODS:
            method = getattr(control, EPHEMERAL_ACTION_METHODS[intent.action_id], None)
            if not callable(method):
                raise RuntimeError(NO_PORT_REASON)
            current = control.current
            if current is None or current.state not in {"running", "suspended"}:
                raise ValueError(NON_ACTIVE_REASON)
            return cast(Callable[[], SessionRecord], method)()
        if intent.action_id in READ_ACTION_METHODS:
            method = getattr(control, READ_ACTION_METHODS[intent.action_id], None)
            if not callable(method):
                raise RuntimeError(NO_PORT_REASON)
            current = control.current
            if current is None or current.state not in {"running", "suspended"}:
                raise ValueError(NON_ACTIVE_REASON)
            cast(Callable[[], Any], method)()
            return current
        if intent.action_id not in {"pause", "resume"} or intent.operation not in {
            "pause",
            "resume",
        }:
            raise ValueError("intent de sessão não allowlisted")
        current = control.current
        if current is None:
            raise RuntimeError("sessão sem estado atual")
        if intent.operation == "pause":
            if current.state != "running":
                raise ValueError("a sessão não está em execução")
            return control.suspend()
        if current.state != "suspended":
            raise ValueError("a sessão não está suspensa")
        return control.resume()


__all__ = ["SaveStateControl", "SessionActionDispatch", "SessionOverlayAdapter"]
