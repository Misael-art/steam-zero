# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Ponte entre o processo do AURA Launcher e a cena QML.

Segue o mesmo desenho já usado pela central: servidor em loopback, token por
execução e o QML como processo separado. O token não é formalidade — sem ele,
qualquer processo local poderia disparar jogos na máquina do usuário.

Vive num adapter porque abre socket e cria processo; o domínio resolve foco e
página, e nada aqui decide navegação.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import secrets
import shutil
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from steamzero.adapters.launcher_process import supervised_child
from steamzero.adapters.launcher_receipt import LaunchAttempt
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.core import ids
from steamzero.core.errors import SteamZeroError
from steamzero.core.title_variants import (
    TITLE_VARIANT_MODES,
    normalize_title_variants,
    select_title_variant,
)
from steamzero.core.title_variants import (
    title_variants as build_title_variants,
)
from steamzero.domain.catalog_search import CatalogSearchQuery, search_records
from steamzero.domain.experience_journey import SESSION_STAGES
from steamzero.domain.scene_layout import LayoutBounds, LayoutRecipe
from steamzero.domain.session_overlay import resolve_session_overlay
from steamzero.launcher.cinema import resolve_cinema_covers
from steamzero.launcher.journey_runtime import JourneyRuntime
from steamzero.launcher.navigation import HomeSection, resolve_home_focus

#: Devolve a tentativa com recibo (ou ``None`` na rota Steam, sem recibo).
LaunchCallback = Callable[[str, str], LaunchAttempt | None]
LaunchBezelCallback = Callable[[str, str, str], LaunchAttempt | None]
# AURA Launcher deve usar o backend acelerado do host.  O caminho software
# continua disponível como degradação explícita para hosts sem RHI utilizável;
# valores vindos do ambiente nunca são repassados diretamente ao QML.
_QT_QUICK_BACKEND = "opengl"
_ALLOWED_QT_QUICK_BACKENDS = frozenset({"opengl", "software"})
_QSG_RENDER_LOOP = "basic"
_ALLOWED_QSG_RENDER_LOOPS = frozenset({"basic", "threaded"})


def _resolve_qt_quick_backend() -> str:
    requested = os.environ.get("STEAMZERO_QT_QUICK_BACKEND", _QT_QUICK_BACKEND)
    return requested if requested in _ALLOWED_QT_QUICK_BACKENDS else _QT_QUICK_BACKEND


def _resolve_qsg_render_loop() -> str:
    requested = os.environ.get(
        "STEAMZERO_QSG_RENDER_LOOP", os.environ.get("QSG_RENDER_LOOP", _QSG_RENDER_LOOP)
    )
    return requested if requested in _ALLOWED_QSG_RENDER_LOOPS else _QSG_RENDER_LOOP


def _performance_report_url() -> str:
    value = os.environ.get("STEAMZERO_PERF_REPORT_URL", "")
    if value.startswith("http://127.0.0.1:") and " " not in value and "\n" not in value:
        return value
    return ""


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    @property
    def _bridge(self) -> LauncherBridge:
        bridge = getattr(self.server, "bridge", None)
        if not isinstance(bridge, LauncherBridge):
            raise RuntimeError("servidor sem ponte associada")
        return bridge

    def _authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-SteamZero-Token", ""), self._bridge.token)

    def do_GET(self) -> None:
        if not self._authorized():
            self._send(403, {"error": "token inválido"})
            return
        if self.path == "/model":
            self._send(200, self._bridge.model())
            return
        if self.path == "/journey/current":
            self._send(200, self._bridge.journey_current())
            return
        if self.path.startswith("/session?"):
            stage = self._query_param("stage")
            if stage is not None and stage not in SESSION_STAGES:
                self._send(400, {"error": "JOURNEY-STAGE-REFERENCE-MISSING"})
                return
            self._send(
                200,
                self._bridge.session(
                    self._query_param("gameId") or "",
                    include_overlay=self._query_param("overlay") == "1",
                    journey_stage=stage,
                ),
            )
            return
        if self.path.startswith("/cinema?"):
            try:
                body = self._bridge.cinema(
                    self._query_param("focus") or "",
                    width=float(self._query_param("width") or "0"),
                    height=float(self._query_param("height") or "0"),
                )
            except ValueError:
                self._send(400, {"error": "LAUNCHER-CINEMA-REQUEST-001"})
                return
            self._send(200, body)
            return
        if self.path.startswith("/search?"):
            params = self._query_params()
            query = params.get("query", params.get("q"))
            if query is None:
                self._send(400, {"error": "parâmetro query/q ausente"})
                return
            payload: dict[str, str] = {"query": query}
            for canonical, aliases in (
                ("platformId", ("platformId", "platform")),
                ("systemId", ("systemId", "system")),
                ("mediaKind", ("mediaKind", "kind")),
            ):
                for alias in aliases:
                    if alias in params:
                        payload[canonical] = params[alias]
                        break
            self._send(200, self._bridge.search(payload))
            return
        self._send(404, {"error": "rota desconhecida"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(403, {"error": "token inválido"})
            return
        if self.path not in {"/launch", "/session/action", "/journey/event"}:
            self._send(404, {"error": "rota desconhecida"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= 4096:
            self.close_connection = True
            self._send(400, {"error": "LAUNCHER-REQUEST-SIZE-001"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error": "corpo inválido"})
            return
        if not isinstance(payload, dict):
            self._send(400, {"error": "corpo inválido"})
            return
        if self.path == "/journey/event":
            result = self._bridge.journey_event(payload)
            self._send(200, result)
            return
        if self.path == "/session/action":
            game_id = payload.get("gameId")
            session_id = payload.get("sessionId")
            action_id = payload.get("actionId")
            slot = payload.get("slot")
            disc_id = payload.get("discId")
            confirmed = payload.get("confirmed", False)
            request_id = payload.get("requestId")
            if (
                not isinstance(game_id, str)
                or not game_id
                or not isinstance(session_id, str)
                or not session_id
                or not isinstance(action_id, str)
                or not action_id
                or not isinstance(confirmed, bool)
                or not isinstance(request_id, str)
                or not 1 <= len(request_id) <= 128
                or any(character in request_id for character in "\x00\r\n")
            ):
                self._send(400, {"error": "AURA-OSD-REQUEST-001"})
                return
            if slot is not None and (
                isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999
            ):
                self._send(400, {"error": "AURA-SAVE-STATE-REQUEST-002"})
                return
            if disc_id is not None and (not isinstance(disc_id, str) or not 0 < len(disc_id) <= 64):
                self._send(400, {"error": "AURA-DISC-REQUEST-003"})
                return
            result = self._bridge.session_action(
                game_id,
                session_id,
                action_id,
                request_id=request_id,
                slot=slot,
                disc_id=disc_id,
                confirmed=confirmed,
            )
            self._send(200 if result["accepted"] else 409, result)
            return
        game_id = str(payload.get("gameId", ""))
        focus_id = str(payload.get("focusId", ""))
        if not game_id:
            self._send(400, {"error": "gameId ausente"})
            return
        try:
            attempt = self._bridge.launch(game_id, focus_id)
        except LaunchBlocked as blocked:
            # Falha comprovadamente anterior ao spawn: o motivo já é escrito
            # para o usuário e dá a ação que resolve.
            self._send(
                409,
                {
                    "error": {
                        "code": blocked.code,
                        "detail": blocked.reason,
                        "impact": "O jogo não foi iniciado.",
                        "canPrepare": blocked.can_prepare,
                    }
                },
            )
            return
        except (OSError, ValueError, SteamZeroError):
            # Exception text can contain local paths or credentials. Publish a
            # stable recovery contract, never an unfiltered traceback/detail.
            self._send(
                409,
                {
                    "error": {
                        "code": "LAUNCHER-LAUNCH-FAILED-001",
                        "cause": "Não foi possível preparar o lançamento.",
                        "impact": "O Launcher não confirmou o início do jogo.",
                        "nextAction": (
                            "Verifique o emulador e os requisitos na central e tente novamente."
                        ),
                    }
                },
            )
            return
        # O requestId publica a tentativa criada: é ele que o shell exige de
        # volta numa falha sem sessionId, para que resposta de tentativa antiga
        # nunca altere um pedido novo. Sem recibo (rota Steam), requestId nulo.
        self._send(
            200,
            {"requestId": attempt.request_id if attempt is not None else None},
        )

    def _query_param(self, name: str) -> str | None:
        return self._query_params().get(name)

    def _query_params(self) -> dict[str, str]:
        from urllib.parse import parse_qs, urlsplit

        parsed = urlsplit(self.path)
        return {
            name: values[0]
            for name, values in parse_qs(parsed.query, keep_blank_values=True).items()
            if values
        }

    def _send(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: Any) -> None:
        """Silencia o log HTTP: ele carregaria o token na linha de requisição."""


class _Server(ThreadingHTTPServer):
    bridge: LauncherBridge


class LaunchBlocked(Exception):
    """Prontidão negou o lançamento antes de qualquer spawn."""

    def __init__(self, code: str, reason: str, can_prepare: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.reason = reason
        self.can_prepare = can_prepare


def _public_reason(reason: str) -> str:
    """Motivo acionável sem caminho local: o home vira ``~``."""
    home = str(Path.home())
    return reason.replace(home, "~")[:240]


class LauncherBridge:
    """Serve o modelo resolvido e recebe o pedido de lançamento."""

    def __init__(
        self,
        *,
        sections: Sequence[HomeSection],
        context_path: Path,
        on_launch: LaunchCallback,
        on_launch_bezel: LaunchBezelCallback | None = None,
        titles: Mapping[str, str] | None = None,
        covers: Mapping[str, str] | None = None,
        title_variants: Mapping[str, Sequence[str]] | None = None,
        title_mode: str = "full",
        accessibility: Mapping[str, Any] | None = None,
        return_context: Mapping[str, Any] | None = None,
        catalog_summary: Mapping[str, Any] | None = None,
        catalog_records: Sequence[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Mapping[str, Any]] | None = None,
        session_observer: Callable[[str], dict[str, Any]] | None = None,
        session_overlay: SessionOverlayAdapter | None = None,
        journey_runtime: JourneyRuntime | None = None,
        journey_diagnostic: Mapping[str, Any] | None = None,
        readiness: Callable[[str], Mapping[str, Any]] | None = None,
        prepare: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self._readiness = readiness
        self._prepare = prepare
        self._preparing: dict[str, threading.Thread] = {}
        self._prepare_failures: dict[str, str] = {}
        self._sections = tuple(sections)
        self._titles = dict(titles or {})
        self._covers = dict(covers or {})
        self._metadata = {key: dict(value) for key, value in (metadata or {}).items()}
        self._catalog_records = {
            str(record.get("id")): dict(record)
            for record in (catalog_records or ())
            if isinstance(record, Mapping) and record.get("id")
        }
        self._session_observer = session_observer
        self._session_overlay = session_overlay
        self._journey_runtime = journey_runtime
        self._journey_diagnostic = dict(journey_diagnostic or {})
        self._previous_sessions: dict[str, str | None] = {}
        self._pending_game: str | None = None
        self._attempts: dict[str, LaunchAttempt] = {}
        self._session_lock = threading.RLock()
        self._journey_request_results: dict[str, tuple[str, dict[str, Any]]] = {}
        self._session_action_results: dict[str, tuple[str, dict[str, Any]]] = {}
        if title_mode not in TITLE_VARIANT_MODES:
            raise ValueError(f"modo de título desconhecido: {title_mode}")
        self._title_mode = title_mode
        supplied_variants = title_variants or {}
        self._title_variants = {
            game_id: normalize_title_variants(supplied_variants.get(game_id, ()))
            or build_title_variants(title)
            for game_id, title in self._titles.items()
        }
        self._context_path = Path(context_path)
        self._on_launch = on_launch
        self._on_launch_bezel = on_launch_bezel
        self._accessibility = dict(accessibility or {})
        self._return_context = dict(return_context or {}) or None
        self._catalog_summary = dict(catalog_summary or {})
        self.token = secrets.token_urlsafe(32)
        self._focus = resolve_home_focus(self._sections)

    def model(self) -> dict[str, Any]:
        return {
            "titleMode": self._title_mode,
            "accessibility": {
                "highContrast": bool(self._accessibility.get("highContrast", False)),
                "visualScale": float(self._accessibility.get("visualScale", 1.0)),
                "reducedMotion": bool(self._accessibility.get("reducedMotion", False)),
            },
            "focusMap": self._focus.to_qml_object(),
            # O processo consome o contexto antes de iniciar o QML. Publicá-lo
            # aqui faz a restauração existir no entry point real, e não apenas
            # no harness que injeta returnContext diretamente.
            "returnContext": self._return_context,
            "catalogSummary": self._catalog_summary,
            "journey": self.journey_current(),
            "sections": [
                {
                    "id": section.id,
                    "title": section.title,
                    "items": [
                        {
                            **self._metadata.get(item, {}),
                            "id": item,
                            "title": self._display_title(item),
                            "titleVariants": list(self._variants_for(item)),
                            "coverUrl": self._covers.get(item)
                            or self._metadata.get(item, {}).get("coverUrl", ""),
                        }
                        for item in section.items
                    ],
                }
                for section in self._sections
            ],
        }

    def journey_current(self) -> dict[str, Any]:
        """Return the active saved journey or a visible safe fallback diagnostic."""
        if self._journey_runtime is not None:
            return self._decorate_journey_view(self._journey_runtime.current())
        return {
            "active": False,
            "journeyId": None,
            "diagnosticCode": str(self._journey_diagnostic.get("code", "JOURNEY-NOT-ACTIVE")),
            "diagnosticMessage": str(
                self._journey_diagnostic.get(
                    "message", "Nenhuma Jornada foi ativada; a Home AURA continua disponível."
                )
            ),
            "recoveryAction": str(
                self._journey_diagnostic.get("recoveryAction", "activate-in-studio")
            ),
        }

    def journey_event(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Run a typed event against the active navigator and session adapters."""
        required = {"requestId", "event", "menuId", "generation"}
        optional = {
            "recordId",
            "connectionId",
            "scrollPosition",
            "focusId",
            "fieldId",
            "clear",
            "unknown",
            "value",
            "slot",
            "confirmed",
        }
        request_id = payload.get("requestId")
        if (
            not required <= set(payload)
            or not set(payload) <= required | optional
            or not isinstance(request_id, str)
            or not 1 <= len(request_id) <= 128
            or any(character in request_id for character in "\x00\r\n")
        ):
            return {
                "requestId": request_id if isinstance(request_id, str) else None,
                "state": "rejected",
                "diagnosticCode": "JOURNEY-REQUEST-INVALID",
                "diagnosticMessage": "O pedido da Jornada contém campos inválidos.",
                "recoveryAction": "review-request",
            }
        slot = payload.get("slot")
        if "slot" in payload and (
            isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999
        ):
            return {
                "requestId": request_id,
                "state": "rejected",
                "diagnosticCode": "JOURNEY-SAVE-SLOT-INVALID",
                "diagnosticMessage": "O slot de save-state deve estar entre 0 e 999.",
                "recoveryAction": "choose-valid-slot",
            }
        try:
            fingerprint = json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError):
            return {
                "requestId": request_id,
                "state": "rejected",
                "diagnosticCode": "JOURNEY-REQUEST-INVALID",
                "diagnosticMessage": "O pedido da Jornada não contém valores JSON válidos.",
                "recoveryAction": "review-request",
            }
        with self._session_lock:
            cached = self._journey_request_results.get(request_id)
            if cached is not None:
                prior_fingerprint, prior_result = cached
                if prior_fingerprint != fingerprint:
                    return {
                        "requestId": request_id,
                        "state": "rejected",
                        "diagnosticCode": "JOURNEY-REQUEST-ID-REUSED",
                        "diagnosticMessage": "Este requestId já foi usado para outro evento.",
                        "recoveryAction": "create-request-id",
                    }
                return cast(
                    dict[str, Any], json.loads(json.dumps(prior_result, ensure_ascii=False))
                )
            runtime = self._journey_runtime
            if runtime is None:
                result = self.journey_current()
                result.update(
                    requestId=request_id,
                    state="inactive",
                    diagnosticCode="JOURNEY-NOT-ACTIVE",
                    recoveryAction="activate-in-studio",
                )
            else:
                result = runtime.handle(payload)
                operation = result.get("operationRequest")
                if isinstance(operation, dict):
                    action = operation.get("action")
                    game_id = operation.get("gameId")
                    if action == "launch" and isinstance(game_id, str):
                        focus_id = self._focus_id_for_game(game_id)
                        if focus_id is None:
                            result.update(
                                state="operation-unavailable",
                                diagnosticCode="JOURNEY-LAUNCH-FOCUS-UNAVAILABLE",
                                diagnosticMessage=(
                                    "O jogo não possui um alvo de retorno no catálogo atual."
                                ),
                                recoveryAction="refresh-library",
                            )
                        else:
                            operation["focusId"] = focus_id
                    elif action in {"pause", "resume"}:
                        result = self._dispatch_journey_session_action(
                            result,
                            operation,
                            request_id=request_id,
                        )
                    elif action == "open-saves":
                        result = self._resolve_journey_saves(result, operation)
                    elif action in {"save", "load", "exit"}:
                        result = self._dispatch_journey_session_action(
                            result,
                            operation,
                            request_id=request_id,
                        )
                    else:
                        result.update(
                            state="operation-unavailable",
                            diagnosticCode="JOURNEY-OPERATION-UNAVAILABLE",
                            diagnosticMessage=(
                                "O runtime desta sessão não publica esta operação. "
                                "A aparência personalizada não altera a capability."
                            ),
                            recoveryAction="choose-supported-path",
                        )
                    result["view"] = runtime.current()
                if isinstance(result.get("view"), Mapping):
                    result["view"] = self._decorate_journey_view(result["view"])
            self._journey_request_results[request_id] = (fingerprint, dict(result))
            if len(self._journey_request_results) > 128:
                self._journey_request_results.pop(next(iter(self._journey_request_results)))
            return result

    def _decorate_journey_view(self, view: Mapping[str, Any]) -> dict[str, Any]:
        """Attach only the selected game's published session capabilities."""
        result = dict(view)
        items = result.get("items", [])
        selected_id = result.get("selectedItemId")
        selected = (
            next(
                (
                    item
                    for item in items
                    if isinstance(item, Mapping) and item.get("id") == selected_id
                ),
                None,
            )
            if isinstance(items, list)
            else None
        )
        game_id = selected.get("gameId") if isinstance(selected, Mapping) else None
        declared = {
            str(item.get("event"))
            for item in result.get("availableEvents", [])
            if isinstance(item, Mapping) and isinstance(item.get("event"), str)
        }
        capabilities: dict[str, dict[str, Any]] = {}
        unavailable = "Selecione um jogo com uma sessão observável."
        model: Mapping[str, Any] = {}
        session: Mapping[str, Any] = {}
        gallery: Mapping[str, Any] = {}
        if isinstance(game_id, str) and self._session_overlay is not None:
            candidate = self._session_overlay.read_model(game_id, visible=True)
            if isinstance(candidate, Mapping):
                model = candidate
                raw_session = model.get("session")
                raw_gallery = model.get("saveStates")
                session = raw_session if isinstance(raw_session, Mapping) else {}
                gallery = raw_gallery if isinstance(raw_gallery, Mapping) else {}
                unavailable = "Nenhuma sessão controlável publicou esta capability."
        state = str(session.get("state", "unknown"))
        osd = model.get("osd", {})
        raw_capabilities = osd.get("capabilities", {}) if isinstance(osd, Mapping) else {}
        raw_capabilities = raw_capabilities if isinstance(raw_capabilities, Mapping) else {}

        def declared_capability(key: str) -> tuple[bool, str]:
            raw = raw_capabilities.get(key)
            if not isinstance(raw, Mapping) or raw.get("available") is not True:
                reason = raw.get("reason") if isinstance(raw, Mapping) else None
                return False, str(reason or unavailable)[:240]
            return True, ""

        for event in ("pause", "resume", "open-saves", "save", "load", "exit", "retry"):
            if event not in declared:
                continue
            if event == "pause":
                available, reason = declared_capability("pause")
                available = available and state == "running"
                if not available and not reason:
                    reason = "A sessão precisa estar confirmada em execução para pausar."
            elif event == "resume":
                available, reason = declared_capability("pause")
                available = available and state == "suspended"
                if not available and not reason:
                    reason = "A sessão precisa estar confirmada como pausada para retomar."
            elif event == "open-saves":
                available = any(
                    gallery.get(field) is True
                    for field in ("available", "saveAvailable", "loadAvailable")
                )
                reason = str(gallery.get("reason") or unavailable)[:240] if not available else ""
            elif event == "save":
                available, reason = declared_capability("saveState")
            elif event == "load":
                available, reason = declared_capability("loadState")
            elif event == "exit":
                available, reason = declared_capability("exit")
                available = available and state in {"running", "suspended", "closing"}
                if not available and not reason:
                    reason = "A sessão precisa estar ativa para pedir encerramento."
            else:
                available = False
                reason = "O adapter desta sessão ainda não publica esta operação."
            capabilities[event] = {"available": available, "reason": reason}
        result["sessionCapabilities"] = capabilities
        if session:
            result["session"] = {
                "gameId": str(session.get("gameId", "")),
                "sessionId": session.get("sessionId"),
                "state": state,
            }
        if gallery:
            result["saveStates"] = dict(gallery)
        return result

    def _focus_id_for_game(self, game_id: str) -> str | None:
        for section in self._sections:
            candidate = f"{section.id}:{game_id}"
            node = self._focus.nodes.get(candidate)
            if node is not None and node.action is None:
                return candidate
        return None

    def _dispatch_journey_session_action(
        self,
        result: dict[str, Any],
        operation: Mapping[str, Any],
        *,
        request_id: str,
    ) -> dict[str, Any]:
        game_id = operation.get("gameId")
        action = operation.get("action")
        confirmed_exit = operation.get("confirmed") is True
        if not isinstance(game_id, str) or self._session_overlay is None:
            return {
                **result,
                "state": "operation-unavailable",
                "diagnosticCode": "JOURNEY-SESSION-CAPABILITY-UNKNOWN",
                "diagnosticMessage": "Nenhuma sessão controlável publicou esta capability.",
                "recoveryAction": "keep-session-safe",
            }
        observed = self.session(game_id)
        session_id = observed.get("sessionId")
        state = observed.get("state")
        if action in {"pause", "save", "load"}:
            expected_current = "running" if action == "pause" else state
        elif action == "exit":
            expected_current = "running, suspended ou closing"
        else:
            expected_current = "suspended"
        valid_current = (
            state == expected_current
            if action in {"pause", "resume"}
            else state in {"running", "suspended", "closing"}
            if action == "exit"
            else state in {"running", "suspended"}
        )
        if not isinstance(session_id, str) or not valid_current:
            return {
                **result,
                "state": "operation-unavailable",
                "diagnosticCode": "JOURNEY-SESSION-CAPABILITY-UNAVAILABLE",
                "diagnosticMessage": (
                    f"A operação {action} exige uma sessão confirmada em {expected_current}; "
                    f"estado observado: {state or 'unknown'}."
                ),
                "recoveryAction": "refresh-session",
                "operationResult": {
                    "requestId": request_id,
                    "gameId": game_id,
                    "sessionId": session_id,
                    "state": state or "unknown",
                    "confirmed": False,
                },
            }
        if action == "exit" and not confirmed_exit:
            return {
                **result,
                "state": "confirmation-required",
                "diagnosticCode": "JOURNEY-EXIT-CONFIRMATION-REQUIRED",
                "diagnosticMessage": (
                    "Confirme que o jogo não tem progresso pendente antes de sair."
                ),
                "recoveryAction": "confirm-exit",
            }
        read_model = self._session_overlay.read_model(game_id, visible=True)
        capability_id = {
            "pause": "pause",
            "resume": "pause",
            "save": "saveState",
            "load": "loadState",
            "exit": "exit",
        }.get(str(action), "")
        capability = read_model.get("osd", {}).get("capabilities", {}).get(capability_id, {})
        if not isinstance(capability, Mapping) or capability.get("available") is not True:
            return {
                **result,
                "state": "operation-unavailable",
                "diagnosticCode": "JOURNEY-SESSION-CAPABILITY-UNAVAILABLE",
                "diagnosticMessage": str(
                    capability.get("reason")
                    if isinstance(capability, Mapping)
                    else "capability unknown"
                ),
                "recoveryAction": "choose-supported-path",
            }
        adapter_action = (
            "pause"
            if action in {"pause", "resume"}
            else {
                "save": "saveState",
                "load": "loadState",
                "exit": "exit",
            }.get(str(action), "")
        )
        slot = operation.get("slot")
        if action in {"save", "load"} and (
            isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999
        ):
            return {
                **result,
                "state": "operation-unavailable",
                "diagnosticCode": "JOURNEY-SAVE-SLOT-INVALID",
                "diagnosticMessage": "Escolha um slot de save-state entre 0 e 999.",
                "recoveryAction": "choose-valid-slot",
            }
        dispatched = self.session_action(
            game_id,
            session_id,
            adapter_action,
            request_id=request_id,
            slot=slot if isinstance(slot, int) else None,
            confirmed=action == "exit" and confirmed_exit,
        )
        expected_result = (
            "suspended" if action == "pause" else "running" if action == "resume" else state
        )
        expected_operation = {
            "pause": "pause",
            "resume": "resume",
            "save": "saveState",
            "load": "loadState",
            "exit": "exit",
        }.get(str(action))
        if action == "exit":
            pending = (
                dispatched.get("accepted") is True
                and dispatched.get("gameId") == game_id
                and dispatched.get("sessionId") == session_id
                and dispatched.get("operation") == "exit"
                and dispatched.get("state") == "closing"
                and dispatched.get("requestId") == request_id
                and dispatched.get("confirmed") is False
            )
            confirmed = (
                dispatched.get("accepted") is True
                and dispatched.get("gameId") == game_id
                and dispatched.get("sessionId") == session_id
                and dispatched.get("operation") == "exit"
                and dispatched.get("state") == "closed"
                and dispatched.get("confirmed") is True
                and dispatched.get("requestId") == request_id
            )
            return {
                **result,
                "state": "operation-confirmed"
                if confirmed
                else "operation-pending"
                if pending
                else "operation-failed",
                "operationResult": {
                    **dispatched,
                    "confirmed": confirmed,
                    "expectedState": "closed",
                },
                "diagnosticCode": ""
                if confirmed
                else "JOURNEY-SESSION-EXIT-PENDING"
                if pending
                else str(dispatched.get("diagnostic") or "JOURNEY-SESSION-OPERATION-FAILED"),
                "diagnosticMessage": ""
                if confirmed
                else str(dispatched.get("detail") or "Aguarde a confirmação da sessão."),
                "recoveryAction": "refresh-session" if not confirmed else "",
            }
        confirmed = (
            dispatched.get("accepted") is True
            and dispatched.get("gameId") == game_id
            and dispatched.get("sessionId") == session_id
            and dispatched.get("state") == expected_result
            and dispatched.get("operation") == expected_operation
            and (action not in {"save", "load"} or dispatched.get("slot") == slot)
            and dispatched.get("requestId") == request_id
        )
        return {
            **result,
            "state": "operation-confirmed" if confirmed else "operation-failed",
            "operationResult": {
                **dispatched,
                "confirmed": confirmed,
                "expectedState": expected_result,
            },
            "diagnosticCode": ""
            if confirmed
            else str(dispatched.get("diagnostic") or "JOURNEY-SESSION-OPERATION-FAILED"),
            "diagnosticMessage": ""
            if confirmed
            else str(dispatched.get("detail") or "A operação não foi confirmada pelo adapter."),
            "recoveryAction": "refresh-session" if not confirmed else "",
        }

    def _resolve_journey_saves(
        self,
        result: dict[str, Any],
        operation: Mapping[str, Any],
    ) -> dict[str, Any]:
        game_id = operation.get("gameId")
        if not isinstance(game_id, str) or self._session_overlay is None:
            return {
                **result,
                "state": "operation-unavailable",
                "diagnosticCode": "JOURNEY-SAVES-CAPABILITY-UNKNOWN",
                "diagnosticMessage": "O adapter de sessão não publica a galeria de saves.",
                "recoveryAction": "choose-supported-path",
            }
        model = self._session_overlay.read_model(game_id, visible=True)
        session = model.get("session", {})
        gallery = model.get("saveStates", {})
        can_open = isinstance(gallery, Mapping) and any(
            gallery.get(field) is True for field in ("available", "saveAvailable", "loadAvailable")
        )
        return {
            **result,
            "state": "operation-confirmed" if can_open else "operation-unavailable",
            "saveStates": gallery,
            "sessionId": session.get("sessionId"),
            "diagnosticCode": "" if can_open else "JOURNEY-SAVES-CAPABILITY-UNAVAILABLE",
            "diagnosticMessage": ""
            if can_open
            else str(gallery.get("reason") or "A galeria não está disponível."),
            "recoveryAction": "refresh-session" if not can_open else "",
        }

    def search(self, query: str | Mapping[str, Any]) -> dict[str, Any]:
        """Busca catálogo e mídia pelo contrato canônico do domínio.

        A ponte continua sendo a dona do mapa id->título, mas não replica as
        regras de normalização. ``query`` aceita a string legada do QML ou o
        envelope com filtros independentes da rota HTTP.
        """
        search_query = (
            CatalogSearchQuery.from_mapping(query)
            if isinstance(query, Mapping)
            else CatalogSearchQuery(text=query)
        )
        raw_query = query.get("query", query.get("q", "")) if isinstance(query, Mapping) else query
        records = tuple(self._search_record(game_id) for game_id in self._titles)
        matches = (
            ()
            if not search_query.text and search_query.is_global
            else search_records(records, search_query)
        )
        projected = [self._search_result(record) for record in matches]
        projected.sort(key=lambda row: str(row["title"]).casefold())
        return {"query": str(raw_query), "games": projected}

    def _search_record(self, game_id: str) -> dict[str, Any]:
        """Join catalog identity and published media for one search record."""
        record = dict(self._catalog_records.get(game_id, {}))
        record["id"] = game_id
        record.setdefault("title", self._titles.get(game_id, game_id))
        record.setdefault("titleVariants", list(self._variants_for(game_id)))
        if not record.get("platformId") and not record.get("platform"):
            record["platform"] = record.get("systemId") or record.get("system") or ""
        if not record.get("systemId") and not record.get("system"):
            record["system"] = record.get("platformId") or record.get("platform") or ""

        media = record.get("media")
        roles = dict(media) if isinstance(media, Mapping) else {}
        metadata = self._metadata.get(game_id, {})
        for role, key in (
            ("cover", "coverUrl"),
            ("fanart", "fanartUrl"),
            ("screenshot", "screenshotUrls"),
            ("marquee", "marqueeUrl"),
            ("video", "videoUrl"),
            ("icon", "iconUrl"),
        ):
            if (
                metadata.get(key)
                or record.get(key)
                or (self._covers.get(game_id) and role == "cover")
            ):
                roles.setdefault(role, True)
        record["media"] = roles
        return record

    def _search_result(self, record: Mapping[str, Any]) -> dict[str, Any]:
        game_id = str(record.get("id", ""))
        variants = self._variants_for(game_id)
        row: dict[str, Any] = {
            "id": game_id,
            "title": self._display_title(game_id),
            "titleVariants": list(variants),
            "coverUrl": self._covers.get(game_id, "")
            or self._metadata.get(game_id, {}).get("coverUrl", "")
            or record.get("coverUrl", ""),
        }
        for key in (
            "fanartUrl",
            "logoUrl",
            "iconUrl",
            "marqueeUrl",
            "videoUrl",
            "screenshotUrls",
            "releaseDate",
            "genres",
            "platform",
            "platformId",
            "platformLabel",
            "system",
            "systemId",
        ):
            value = self._metadata.get(game_id, {}).get(key, record.get(key))
            if value not in (None, "", [], {}):
                row[key] = value
        return row

    def cinema(self, focus_id: str, *, width: float, height: float) -> dict[str, Any]:
        """Resolve only the focused collection; no navigation decision is made here."""
        bounds = LayoutBounds(width, height)
        if self._journey_runtime is not None:
            view = self._journey_runtime.current()
            if view.get("active") is True:
                return self._journey_cinema(
                    view, focus_id, bounds=bounds, width=width, height=height
                )
        node = self._focus.nodes.get(focus_id)
        if node is None:
            raise ValueError("unknown focus")
        section = next((row for row in self._sections if row.id == node.section), None)
        if section is None:
            return {"layouts": {}, "sourceIndices": [], "selected": 0, "focusId": focus_id}
        items = [
            {
                **self._metadata.get(game, {}),
                "id": game,
                "title": self._titles.get(game, game),
                "coverUrl": self._covers.get(game)
                or self._metadata.get(game, {}).get("coverUrl", ""),
            }
            for game in section.items
        ]
        cover_height = min(height * 0.72, 640)
        recipe = LayoutRecipe.from_dict(
            "covers",
            {
                "source": "cinema.items",
                "kind": "coverFlow",
                "item": {"width": max(1, cover_height * 2 / 3), "height": max(1, cover_height)},
                "template": {
                    "kind": "image",
                    "id": "cover",
                    "properties": {"source": {"binding": "item.coverUrl", "fallback": ""}},
                },
                "offset": {
                    "scaleStep": 0.18,
                    "opacityStep": 0.2,
                    "minScale": 0.5,
                    "minOpacity": 0.35,
                    "rotationStep": 0,
                    "overlap": 0.65,
                },
                "highlight": {"scale": 1, "opacity": 1, "outlineWidth": 3},
            },
        )
        result = resolve_cinema_covers(recipe, items, node.column, bounds=bounds)
        result.update(
            focusId=focus_id,
            collection=section.title,
            performanceTier="balanced",
            connectionState="connected",
            viewport={"width": width, "height": height},
            items=[items[index] for index in result["sourceIndices"]],
        )
        return result

    def _journey_cinema(
        self,
        view: Mapping[str, Any],
        focus_id: str,
        *,
        bounds: LayoutBounds,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        raw_rows = view.get("items")
        rows = raw_rows if isinstance(raw_rows, list) else []
        items: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            game_id = str(row.get("gameId") or "")
            metadata = dict(self._metadata.get(game_id, {})) if game_id else {}
            title = row.get("title") or row.get("name") or row.get("platformName") or row.get("id")
            items.append(
                {
                    **metadata,
                    **dict(row),
                    "id": game_id or str(row.get("id", "")),
                    "title": str(title or ""),
                    "coverUrl": self._covers.get(game_id, "") or metadata.get("coverUrl", ""),
                    "journeyRecordId": str(row.get("id", "")),
                }
            )
        selected_id = str(view.get("selectedItemId") or "")
        focus_prefix = f"journey:{view.get('menuId', '')}:"
        if focus_id.startswith(focus_prefix):
            focused_record_id = focus_id[len(focus_prefix) :]
            if any(
                str(row.get("id", "")) == focused_record_id
                for row in rows
                if isinstance(row, Mapping)
            ):
                selected_id = focused_record_id
        selected = next(
            (index for index, row in enumerate(items) if row.get("journeyRecordId") == selected_id),
            0,
        )
        recipe, layout_state, layout_diagnostic = self._journey_cinema_recipe(view, height)
        result = resolve_cinema_covers(recipe, items, selected, bounds=bounds)
        source_indices = result["sourceIndices"]
        result.update(
            focusId=focus_id,
            collection=str(view.get("menuName") or "Jornada"),
            journeyId=str(view.get("journeyId") or ""),
            menuId=str(view.get("menuId") or ""),
            journeyGeneration=int(view.get("generation", 0)),
            resultState=str(view.get("resultState") or "unknown"),
            diagnosticCode=str(view.get("diagnosticCode") or ""),
            diagnosticMessage=str(view.get("diagnosticMessage") or ""),
            recoveryAction=str(view.get("recoveryAction") or ""),
            theme=view.get("theme"),
            layoutId=recipe.id,
            themeResolutionState=str(
                view.get("theme", {}).get("resolutionState", "fallback")
                if isinstance(view.get("theme"), Mapping)
                else "fallback"
            ),
            layoutResolutionState=layout_state,
            layoutDiagnostic=layout_diagnostic,
            performanceTier="balanced",
            connectionState="connected",
            viewport={"width": width, "height": height},
            items=[items[index] for index in source_indices],
        )
        return result

    @staticmethod
    def _journey_cinema_recipe(
        view: Mapping[str, Any], height: float
    ) -> tuple[LayoutRecipe, str, str]:
        theme = view.get("theme")
        book = theme.get("sceneLayouts") if isinstance(theme, Mapping) else None
        raw_layouts = book.get("layouts") if isinstance(book, Mapping) else None
        if isinstance(raw_layouts, Mapping):
            for layout_id, raw in raw_layouts.items():
                if not isinstance(layout_id, str) or not isinstance(raw, Mapping):
                    continue
                if raw.get("kind") != "coverFlow":
                    continue
                try:
                    recipe = LayoutRecipe.from_dict(layout_id, raw)
                except ValueError:
                    continue
                return recipe, "theme", ""
        cover_height = min(height * 0.72, 640)
        fallback = LayoutRecipe.from_dict(
            "covers",
            {
                "source": "cinema.items",
                "kind": "coverFlow",
                "item": {"width": max(1, cover_height * 2 / 3), "height": max(1, cover_height)},
                "template": {
                    "kind": "image",
                    "id": "cover",
                    "properties": {"source": {"binding": "item.coverUrl", "fallback": ""}},
                },
                "offset": {
                    "scaleStep": 0.18,
                    "opacityStep": 0.2,
                    "minScale": 0.5,
                    "minOpacity": 0.35,
                    "rotationStep": 0,
                    "overlap": 0.65,
                },
                "highlight": {"scale": 1, "opacity": 1, "outlineWidth": 3},
            },
        )
        diagnostic = (
            "O tema da etapa não publica um layout coverFlow compatível; "
            "o Cinema usa a composição AURA."
            if isinstance(book, Mapping)
            else "A etapa não declara layout; o Cinema usa a composição AURA."
        )
        return fallback, "aura-fallback", diagnostic

    def launch(self, game_id: str, focus_id: str) -> LaunchAttempt | None:
        """Lança o jogo e devolve a tentativa com requestId correlacionado.

        ``None`` significa rota sem recibo (Steam): falha sem sessionId não é
        aceita para ela — não há como confirmar o que aconteceu.
        """
        # Connections are concurrent; validation, spawn and reservation form
        # one critical section so two clients cannot both launch the game.
        with self._session_lock:
            return self._launch_locked(game_id, focus_id)

    def _auto_prepare(self, game_id: str, verdict: Mapping[str, Any]) -> None:
        """Inicia, em segundo plano, o que o jogo precisa para abrir.

        Extrair um archive leva minutos, mais que o prazo de uma requisição da
        UI. Então o primeiro "Jogar" dispara a preparação e responde na hora com
        o que está acontecendo; o seguinte já encontra o jogo pronto. Nada é
        iniciado enquanto isso.
        """
        if self._prepare is None or verdict.get("canPrepare") is not True:
            return
        running = self._preparing.get(game_id)
        if running is not None and running.is_alive():
            raise LaunchBlocked(
                "LAUNCHER-PREPARING-001",
                "Preparando o jogo (extraindo o arquivo). Tente Jogar de novo em instantes.",
            )
        failure = self._prepare_failures.pop(game_id, None)
        if failure is not None:
            raise LaunchBlocked("LAUNCHER-PREPARE-FAILED-001", failure)
        prepare = self._prepare

        def work() -> None:
            try:
                result = prepare(game_id)
                if result.get("prepared") is not True:
                    self._prepare_failures[game_id] = _public_reason(
                        str(result.get("reason") or "a preparação não foi concluída")
                    )
            except Exception as exc:  # qualquer falha vira motivo ao usuário
                self._prepare_failures[game_id] = _public_reason(
                    str(getattr(exc, "detail", "") or "a preparação falhou")
                )

        thread = threading.Thread(target=work, name=f"prepare-{game_id}", daemon=True)
        self._preparing[game_id] = thread
        thread.start()
        raise LaunchBlocked(
            "LAUNCHER-PREPARING-001",
            "Preparando o jogo (extraindo o arquivo). Tente Jogar de novo em instantes.",
        )

    def _launch_locked(self, game_id: str, focus_id: str) -> LaunchAttempt | None:
        if self._pending_game is not None:
            self.session(self._pending_game)
            if self._pending_game is not None:
                raise ValueError("a launch is still active or unconfirmed")
        node = self._focus.nodes.get(focus_id)
        if node is None or node.action is not None:
            raise ValueError("launch requires a current game focus")
        section = next((row for row in self._sections if row.id == node.section), None)
        if (
            section is None
            or not 0 <= node.column < len(section.items)
            or section.items[node.column] != game_id
        ):
            raise ValueError("launch game does not match its return focus")
        if self._readiness is not None:
            verdict = self._readiness(game_id)
            if verdict.get("playable") is False:
                self._auto_prepare(game_id, verdict)
                raise LaunchBlocked(
                    str(verdict.get("code") or "E-CONTENT-UNSUPPORTED"),
                    _public_reason(str(verdict.get("reason") or "")),
                    can_prepare=verdict.get("canPrepare") is True,
                )
        if self._session_observer is not None:
            previous = self._session_observer(game_id)
            if previous.get("state") in {
                "launching",
                "running",
                "suspending",
                "suspended",
                "resuming",
                "closing",
            }:
                raise ValueError("the game already has an active canonical session")
            self._previous_sessions[game_id] = previous.get("sessionId")
        bezel_resource = "aura-default"
        if self._journey_runtime is not None:
            selection = self._journey_runtime.stage_bezel("bezel")
            bezel_resource = str(selection.get("resourceId") or "aura-default")
        attempt = (
            self._on_launch_bezel(game_id, focus_id, bezel_resource)
            if self._on_launch_bezel is not None
            else self._on_launch(game_id, focus_id)
        )
        if attempt is not None:
            # Uma tentativa substitui a anterior do mesmo jogo; respostas da
            # antiga deixam de ser consultáveis pelo caminho da ponte.
            self._attempts[game_id] = attempt
        if self._session_observer is not None:
            self._pending_game = game_id
        return attempt

    def session(
        self,
        game_id: str,
        *,
        include_overlay: bool = False,
        journey_stage: str | None = None,
    ) -> dict[str, Any]:
        with self._session_lock:
            result = self._session_locked(game_id)
            if include_overlay:
                result["overlay"] = self._overlay_locked(
                    game_id, result, journey_stage=journey_stage
                )
            return result

    def session_action(
        self,
        game_id: str,
        session_id: str,
        action_id: str,
        *,
        request_id: str | None = None,
        slot: int | None = None,
        disc_id: str | None = None,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Dispatch one idempotent action and return its confirmed session state."""

        with self._session_lock:
            identity = request_id or ids.new_ulid()
            if not 1 <= len(identity) <= 128 or any(char in identity for char in "\x00\r\n"):
                return {
                    "accepted": False,
                    "requestId": identity,
                    "gameId": game_id,
                    "sessionId": session_id,
                    "operation": None,
                    "state": "unknown",
                    "diagnostic": "AURA-OSD-REQUEST-001",
                    "detail": "requestId inválido.",
                }
            request_body = {
                "gameId": game_id,
                "sessionId": session_id,
                "actionId": action_id,
                "slot": slot,
                "discId": disc_id,
                "confirmed": confirmed,
            }
            fingerprint = json.dumps(
                request_body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            cached = self._session_action_results.get(identity)
            if cached is not None:
                prior_fingerprint, prior_result = cached
                if prior_fingerprint != fingerprint:
                    return {
                        "accepted": False,
                        "requestId": identity,
                        "gameId": game_id,
                        "sessionId": session_id,
                        "operation": None,
                        "state": "unknown",
                        "diagnostic": "AURA-OSD-REQUEST-ID-REUSED-006",
                        "detail": "Este requestId já foi usado para outra ação.",
                    }
                return cast(
                    dict[str, Any], json.loads(json.dumps(prior_result, ensure_ascii=False))
                )
            if self._session_overlay is None:
                result = {
                    "accepted": False,
                    "gameId": game_id,
                    "sessionId": session_id,
                    "operation": None,
                    "state": "unknown",
                    "diagnostic": "AURA-OSD-ADAPTER-UNAVAILABLE-005",
                    "detail": "O adapter de sessão ainda não está conectado ao runtime.",
                }
            else:
                result = self._session_overlay.dispatch(
                    game_id,
                    session_id,
                    action_id,
                    slot=slot,
                    disc_id=disc_id,
                    confirmed=confirmed,
                ).to_dict()
            result["requestId"] = identity
            self._session_action_results[identity] = (fingerprint, dict(result))
            if len(self._session_action_results) > 128:
                self._session_action_results.pop(next(iter(self._session_action_results)))
            return result

    def _overlay_locked(
        self,
        game_id: str,
        session: Mapping[str, Any],
        *,
        journey_stage: str | None = None,
    ) -> dict[str, Any]:
        if self._session_overlay is None:
            result = {
                "sessionId": session.get("sessionId"),
                "gameId": game_id,
                "state": session.get("state", "unknown"),
                "visible": False,
                "focusedAction": "",
                "actions": [],
                "saveStates": {
                    "schemaVersion": 1,
                    "state": "unavailable",
                    "available": False,
                    "saveAvailable": False,
                    "loadAvailable": False,
                    "reason": "O adapter de sessão ainda não está conectado ao runtime.",
                    "entries": [],
                },
                "peripherals": {
                    "schemaVersion": 1,
                    "state": "unavailable",
                    "available": False,
                    "discs": [],
                    "activeDisc": None,
                    "bezels": [],
                    "fade": {
                        "phase": "idle",
                        "progress": 0.0,
                        "durationMs": 180,
                        "reducedMotion": False,
                    },
                    "reason": "O adapter de sessão ainda não está conectado ao runtime.",
                },
                "criticalError": None,
                "diagnostic": "AURA-OSD-ADAPTER-UNAVAILABLE-005",
            }
        else:
            model = self._session_overlay.read_model(game_id, visible=True)
            result = resolve_session_overlay(model).to_qml_object()
        if self._journey_runtime is not None:
            state = str(session.get("state", "unknown"))
            selected_stage = journey_stage or {
                "suspended": "pause",
                "running": "osd",
                "launching": "loading",
                "suspending": "pause",
                "resuming": "osd",
                "closing": "exitFade",
                "failed": "error",
            }.get(state, "osd")
            result["journeyAppearance"] = self._journey_runtime.stage_appearance(selected_stage)
            result["journeyBezel"] = self._journey_runtime.stage_bezel("bezel")
        return result

    def _session_locked(self, game_id: str) -> dict[str, Any]:
        if self._session_observer is None or not any(
            game_id in section.items for section in self._sections
        ):
            return {"gameId": game_id, "state": "unknown", "sessionId": None}
        result = self._session_observer(game_id)
        attempt = self._attempts.get(game_id)
        outcome = attempt.outcome() if attempt is not None else None
        if outcome is not None and outcome.get("state") == "notStarted":
            # Falha comprovadamente anterior ao spawn, confirmada pelo requestId
            # do pedido atual: nada foi criado, a tentativa é liberada e Jogar
            # volta a ser elegível. O erro viaja na projeção da tentativa.
            self._attempts.pop(game_id, None)
            if self._pending_game == game_id:
                self._pending_game = None
            return {**result, "state": "failed", "sessionId": None, "attempt": outcome}
        if outcome is not None:
            receipt_state = outcome.get("state")
            receipt_session = outcome.get("sessionId")
            if receipt_state != "confirmed" or result.get("sessionId") != receipt_session:
                # A observação só pertence a ESTE pedido depois que o recibo
                # confirmar o sessionId exato. Uma sessão diferente do mesmo
                # jogo pode ter sido criada externamente; pending/delayed ou
                # unconfirmed também nunca fabricam essa correlação.
                return {
                    "gameId": game_id,
                    "state": "awaiting",
                    "sessionId": None,
                    "attempt": outcome,
                }
        if (
            game_id in self._previous_sessions
            and result.get("sessionId") == self._previous_sessions[game_id]
        ):
            awaiting: dict[str, Any] = {"gameId": game_id, "state": "awaiting", "sessionId": None}
            if outcome is not None:
                awaiting["attempt"] = outcome
            return awaiting
        if self._pending_game == game_id and result.get("state") in {"closed", "failed"}:
            self._pending_game = None
            # Terminalização canônica encerra a tentativa; retenção liberada.
            self._attempts.pop(game_id, None)
        if outcome is not None:
            result = {**result, "attempt": outcome}
        return result

    def _variants_for(self, game_id: str) -> tuple[str, ...]:
        return self._title_variants.get(game_id, ()) or build_title_variants(
            self._titles.get(game_id, game_id)
        )

    def _display_title(self, game_id: str) -> str:
        return select_title_variant(self._titles.get(game_id, game_id), self._title_mode)

    @contextmanager
    def serving(self) -> Iterator[str]:
        server = _Server(("127.0.0.1", 0), _Handler)
        server.bridge = self
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()


def launch_launcher_ui(bridge: LauncherBridge) -> int:
    """Abre a cena do Launcher e espera o processo terminar.

    Runtime Qt ausente é condição esperada num host sem sessão gráfica, e vira
    código de saída com mensagem — não traceback.
    """
    executable = shutil.which("qml6") or shutil.which("qml")
    if executable is None:
        return 3
    resource = importlib.resources.files("steamzero.ui").joinpath("qml/launcher/LauncherMain.qml")
    with bridge.serving() as base, importlib.resources.as_file(resource) as scene:
        argv: tuple[str, ...] = (
            executable,
            str(scene),
            "--",
            "--steamzero-api",
            base,
            "--steamzero-token",
            bridge.token,
        )
        report_url = _performance_report_url()
        if report_url:
            argv += ("--steamzero-perf-url", report_url)
        environment = {
            **os.environ,
            "QT_QUICK_BACKEND": _resolve_qt_quick_backend(),
            "QSG_RENDER_LOOP": _resolve_qsg_render_loop(),
            "STEAMZERO_CLASS": "launcher",
        }
        # A cena vive sob supervisão: quando este processo acabar — por retorno,
        # exceção ou sinal — o `qml6` acaba junto. Sobrevivendo, ele mantinha uma
        # janela com o título e a classe da sessão viva, já sem a ponte HTTP.
        with supervised_child(argv, env=environment) as process:
            status = process.wait()
    # Morte por sinal chega como código negativo, que não é código de saída
    # válido; a convenção de shell (128+sinal) preserva a causa.
    return 128 - status if status < 0 else int(status)
