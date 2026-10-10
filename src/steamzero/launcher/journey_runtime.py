# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Runtime consumer for the exact saved Experience Journey selected by Studio."""

from __future__ import annotations

import json
import math
import threading
from collections.abc import Mapping, Sequence
from typing import Any

from steamzero.domain.experience_journey import (
    SESSION_STAGES,
    JourneyDocument,
    JourneyExecutor,
    JourneyNavigator,
    JourneyStore,
    query_public_records,
)

_DEFAULT_FACETS = (
    "platformId",
    "genre",
    "year",
    "developer",
    "publisher",
    "family",
    "emulatorId",
    "availability",
)
_NON_FACET_FIELDS = frozenset({"id", "gameId", "title", "name", "source"})


def facet_items(
    group_by: Sequence[str], groups: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """One selectable row per grouped value, with the game count beside it.

    The launcher list reads ``items``. Leaving the underlying game rows there
    repeats every title that shares a genre or year. The row still carries the
    published field so the existing menu binding can filter the shared games menu.
    """
    if not group_by:
        return []
    primary = group_by[0]
    items: list[dict[str, Any]] = []
    for group in groups:
        raw_values = group.get("values")
        values = dict(raw_values) if isinstance(raw_values, Mapping) else {}
        projected = {field_id: values.get(field_id) for field_id in group_by}
        primary_value = projected.get(primary)
        label = "Desconhecido" if primary_value is None else str(primary_value)
        token = json.dumps(
            projected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        item: dict[str, Any] = {
            "id": f"facet:{token}",
            "title": label,
            "name": label,
            "count": int(group.get("count", 0)),
            "facet": True,
        }
        item.update(projected)
        items.append(item)
    return items


_PRIVATE_FIELD_IDS = frozenset(
    {
        "biospath",
        "configpath",
        "credential",
        "credentials",
        "filepath",
        "launchpath",
        "password",
        "pid",
        "processid",
        "rompath",
        "savepath",
        "secret",
        "token",
        "userpath",
    }
)
_MAX_PUBLIC_STRING = 4096
_MAX_PUBLIC_LIST = 64


class JourneyRuntime:
    """Execute menu routes against bounded, typed public models.

    This adapter never receives launch paths or process identity. It returns a
    semantic launch/session request to the existing Launcher and session
    adapters, and keeps navigation state separate from the organization tree.
    """

    def __init__(
        self,
        document: JourneyDocument,
        *,
        read_models: Mapping[str, Sequence[Mapping[str, Any]] | None],
        published_read_models: Mapping[str, Mapping[str, str]],
        source_states: Mapping[str, str] | None = None,
        launchable_game_ids: Sequence[str] = (),
        theme_resolver: Any = None,
        bezel_resolver: Any = None,
    ) -> None:
        self.document = document
        self._published = {
            key: {
                field_id: field_type
                for field_id, field_type in value.items()
                if not self._is_private_field_id(field_id)
            }
            for key, value in published_read_models.items()
        }
        # Query helpers preserve input rows for ordering/grouping. Project at
        # the consumer boundary first so an accidentally rich adapter record
        # can never leak paths, process identity, or undeclared fields to QML.
        self._read_models = {
            key: None
            if rows is None
            else tuple(self._project_public_row(row, self._published.get(key, {})) for row in rows)
            for key, rows in read_models.items()
        }
        self._source_states = dict(source_states or {})
        self._launchable_game_ids = frozenset(str(value) for value in launchable_game_ids)
        self._theme_resolver = theme_resolver
        self._bezel_resolver = bezel_resolver
        document.ensure_activatable(self._published)
        self.navigator = JourneyNavigator(document, published_read_models=self._published)
        self.executor = JourneyExecutor(
            document,
            self.navigator,
            published_read_models=self._published,
        )
        self._menus = {str(menu["id"]): dict(menu) for menu in document.menus}
        self._lock = threading.RLock()

    @staticmethod
    def _project_public_row(
        row: Mapping[str, Any], field_types: Mapping[str, str]
    ) -> dict[str, Any]:
        projected: dict[str, Any] = {}
        for field_id, field_type in field_types.items():
            value = row.get(field_id)
            if field_type == "string" and isinstance(value, str):
                projected[field_id] = value[:_MAX_PUBLIC_STRING]
            elif field_type == "integer" and isinstance(value, int) and not isinstance(value, bool):
                projected[field_id] = value
            elif (
                field_type == "number"
                and isinstance(value, int | float)
                and not isinstance(value, bool)
            ):
                if not isinstance(value, float) or math.isfinite(value):
                    projected[field_id] = value
            elif field_type == "boolean" and isinstance(value, bool):
                projected[field_id] = value
            elif field_type == "string[]" and isinstance(value, list):
                projected[field_id] = [
                    item[:512] for item in value[:_MAX_PUBLIC_LIST] if isinstance(item, str)
                ]
        return projected

    @staticmethod
    def _is_private_field_id(field_id: str) -> bool:
        normalized = "".join(character for character in field_id.casefold() if character.isalnum())
        return (
            normalized in _PRIVATE_FIELD_IDS
            or normalized.endswith("path")
            or any(
                marker in normalized
                for marker in (
                    "token",
                    "secret",
                    "credential",
                    "password",
                    "command",
                    "argv",
                    "launch",
                    "argument",
                    "executable",
                )
            )
        )

    @classmethod
    def from_store(
        cls,
        root: Any,
        *,
        read_models: Mapping[str, Sequence[Mapping[str, Any]] | None],
        published_read_models: Mapping[str, Mapping[str, str]],
        source_states: Mapping[str, str] | None = None,
        launchable_game_ids: Sequence[str] = (),
        theme_resolver: Any = None,
        bezel_resolver: Any = None,
    ) -> JourneyRuntime | None:
        store = JourneyStore(root)
        journey_id = store.active_id()
        if journey_id is None:
            return None
        document = store.load(journey_id)
        return cls(
            document,
            read_models=read_models,
            published_read_models=published_read_models,
            source_states=source_states,
            launchable_game_ids=launchable_game_ids,
            theme_resolver=theme_resolver,
            bezel_resolver=bezel_resolver,
        )

    @property
    def journey_id(self) -> str:
        return self.document.id

    def current(self) -> dict[str, Any]:
        with self._lock:
            return self._view()

    def stage_appearance(self, stage_id: str) -> dict[str, Any]:
        """Resolve a declared session stage through the same trusted theme catalog."""
        if stage_id not in SESSION_STAGES:
            return {
                "journeyId": self.journey_id,
                "stageId": stage_id,
                "appearanceState": "missing-reference",
                "diagnosticCode": "JOURNEY-STAGE-REFERENCE-MISSING",
                "diagnosticMessage": "A etapa pedida não existe no contrato da Jornada.",
            }
        assignment = next(
            (
                stage.get("appearance")
                for stage in self.document.data["sessionStages"]
                if str(stage.get("stageId")) == stage_id
            ),
            None,
        )
        if assignment is None:
            appearance_state = "omitted"
        elif isinstance(assignment, Mapping):
            appearance_state = str(assignment.get("mode", "invalid"))
        else:
            appearance_state = "invalid"
        result: dict[str, Any] = {
            "journeyId": self.journey_id,
            "stageId": stage_id,
            "appearanceState": appearance_state,
            "appearance": dict(assignment) if isinstance(assignment, Mapping) else None,
            "diagnosticCode": "",
            "diagnosticMessage": "",
        }
        if callable(self._theme_resolver):
            try:
                theme = self._theme_resolver(stage_id, assignment)
            except Exception:
                result.update(
                    appearanceState="aura-fallback",
                    diagnosticCode="JOURNEY-STAGE-THEME-UNAVAILABLE",
                    diagnosticMessage=(
                        "O tema desta etapa não foi resolvido; a superfície usa a aparência AURA."
                    ),
                )
            else:
                if isinstance(theme, Mapping):
                    result["theme"] = dict(theme)
                    resolution = str(theme.get("resolutionState", "resolved"))
                    if resolution != "resolved":
                        result["diagnosticCode"] = "JOURNEY-STAGE-THEME-FALLBACK"
                        result["diagnosticMessage"] = str(
                            theme.get("resolutionDiagnostic")
                            or "O tema não é compatível; a superfície usa AURA."
                        )[:240]
        return result

    def stage_bezel(self, stage_id: str) -> dict[str, Any]:
        """Resolve a version-locked bezel choice from the saved journey stage."""
        if stage_id not in SESSION_STAGES:
            return {
                "journeyId": self.journey_id,
                "stageId": stage_id,
                "state": "missing-reference",
                "resourceId": "aura-default",
                "diagnosticCode": "JOURNEY-STAGE-REFERENCE-MISSING",
                "diagnosticMessage": "A etapa pedida não existe no contrato da Jornada.",
                "applyMode": "next-launch",
            }
        assignment = next(
            (
                stage.get("bezelResource")
                for stage in self.document.data["sessionStages"]
                if str(stage.get("stageId")) == stage_id
            ),
            None,
        )
        selected = isinstance(assignment, str) and assignment != "aura-default"
        resource_id = str(assignment) if isinstance(assignment, str) else "aura-default"
        result: dict[str, Any] = {
            "journeyId": self.journey_id,
            "stageId": stage_id,
            "resourceId": resource_id,
            "state": "selected"
            if selected
            else ("explicit-aura" if assignment else "inherited-aura"),
            "applyMode": "next-launch",
            "diagnosticCode": "",
            "diagnosticMessage": "",
        }
        if selected and not callable(self._bezel_resolver):
            result.update(
                state="unavailable",
                diagnosticCode="JOURNEY-BEZEL-ADAPTER-UNAVAILABLE",
                diagnosticMessage=(
                    "Este runtime não publicou um resolver de bezel; a seleção fica "
                    "preservada, mas a etapa não pode aplicá-la."
                ),
            )
        if selected and callable(self._bezel_resolver):
            try:
                resolved = self._bezel_resolver(resource_id)
            except Exception as exc:
                resolved = None
                error_code = str(getattr(exc, "code", ""))
                detail = str(getattr(exc, "detail", ""))
                if error_code == "E-THEME-NOT-FOUND":
                    result.update(
                        state="missing-reference",
                        diagnosticCode="JOURNEY-BEZEL-REFERENCE-MISSING",
                        diagnosticMessage=detail[:240]
                        or (
                            "O tema/asset do bezel não está instalado; "
                            "selecione outro ou herde AURA."
                        ),
                    )
                else:
                    result.update(
                        state="incompatible",
                        diagnosticCode="JOURNEY-BEZEL-INCOMPATIBLE",
                        diagnosticMessage=detail[:240]
                        or "O tema, versão, conteúdo ou formato do bezel não é compatível.",
                    )
            if not isinstance(resolved, Mapping):
                if result["state"] == "selected":
                    result.update(
                        state="missing-reference",
                        diagnosticCode="JOURNEY-BEZEL-REFERENCE-MISSING",
                        diagnosticMessage=(
                            "O bezel escolhido não está instalado na versão declarada; "
                            "selecione outro recurso ou herde AURA."
                        ),
                    )
            else:
                result.update(
                    origin=str(resolved.get("origin") or "unknown"),
                    version=str(resolved.get("version") or "unknown"),
                    license=str(resolved.get("license") or "unknown"),
                    label=str(resolved.get("label") or "Bezel personalizado")[:128],
                )
                if resolved.get("available") is not True or resolved.get("compatible") is not True:
                    result.update(
                        state="incompatible",
                        diagnosticCode="JOURNEY-BEZEL-INCOMPATIBLE",
                        diagnosticMessage=str(
                            resolved.get("reason")
                            or "O bezel escolhido não é compatível com o adapter desta sessão."
                        )[:240],
                    )
                else:
                    result["state"] = "available"
        return result

    def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Resolve one QML event and reject stale route generations."""
        with self._lock:
            request_id = request.get("requestId")
            event = request.get("event")
            menu_id = request.get("menuId")
            expected_generation = request.get("generation")
            current = self.navigator.context
            if (
                not isinstance(request_id, str)
                or not request_id
                or not isinstance(event, str)
                or not isinstance(menu_id, str)
                or not isinstance(expected_generation, int)
                or isinstance(expected_generation, bool)
            ):
                return self._failure(
                    request_id,
                    "JOURNEY-REQUEST-INVALID",
                    "O pedido da Jornada está incompleto.",
                    "retry",
                )
            slot = request.get("slot")
            if "slot" in request and (
                isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= 999
            ):
                return self._failure(
                    request_id,
                    "JOURNEY-SAVE-SLOT-INVALID",
                    "O slot de save-state deve estar entre 0 e 999.",
                    "choose-valid-slot",
                )
            if ("confirmed" in request and not isinstance(request.get("confirmed"), bool)) or (
                "confirmed" in request and event != "exit"
            ):
                return self._failure(
                    request_id,
                    "JOURNEY-CONFIRMATION-INVALID",
                    "A confirmação explícita só é aceita para encerrar uma sessão.",
                    "review-action",
                )
            if event == "exit" and request.get("confirmed") is not True:
                return self._failure(
                    request_id,
                    "JOURNEY-EXIT-CONFIRMATION-REQUIRED",
                    "Confirme que o jogo não tem progresso pendente antes de sair.",
                    "confirm-exit",
                    state="confirmation-required",
                )
            route_connection_id = request.get("connectionId")
            if (
                event == "route"
                and (
                    not isinstance(route_connection_id, str)
                    or not 1 <= len(route_connection_id) <= 128
                    or any(character in route_connection_id for character in "\x00\r\n")
                )
            ) or (event != "route" and route_connection_id is not None):
                return self._failure(
                    request_id,
                    "JOURNEY-ROUTE-CONNECTION-INVALID",
                    "Escolha uma conexão de navegação publicada para este menu.",
                    "choose-published-route",
                )
            if menu_id != current.menu_id or expected_generation != self.navigator.generation:
                return self._failure(
                    request_id,
                    "JOURNEY-RESPONSE-STALE",
                    "A resposta pertence a uma rota anterior; a seleção atual foi mantida.",
                    "keep-current-route",
                    state="stale-response",
                )

            if event == "facet":
                facet_result = self._set_facet(request)
                return {"requestId": request_id, **facet_result, "view": self._view()}

            view = self._view()
            record = None
            record_id = request.get("recordId")
            if event in {
                "select",
                "route",
                "play",
                "launch",
                "pause",
                "resume",
                "open-saves",
                "save",
                "load",
                "exit",
                "retry",
            }:
                if not isinstance(record_id, str) or not record_id:
                    return self._failure(
                        request_id,
                        "JOURNEY-SELECTION-MISSING",
                        "Selecione um item disponível neste menu antes de continuar.",
                        "select-item",
                    )
                record = next(
                    (row for row in view["items"] if str(row.get("id")) == record_id),
                    None,
                )
                if record is None:
                    return self._failure(
                        request_id,
                        "JOURNEY-SELECTION-UNAVAILABLE",
                        "O item selecionado não pertence aos resultados atuais.",
                        "refresh-menu",
                    )

            try:
                execution = self.executor.execute(
                    event,
                    source_endpoint={"kind": "menu", "id": current.menu_id},
                    selected_record=record,
                    selected_item_id=(
                        record_id if record is not None else current.selected_item_id
                    ),
                    filters=dict(current.filters),
                    scroll_position=self._finite_nonnegative(
                        request.get("scrollPosition", current.scroll_position)
                    ),
                    focus_id=self._request_focus(request.get("focusId", current.focus_id)),
                    read_models=self._read_models,
                    published_read_models=self._published,
                    route_connection_id=(
                        route_connection_id if isinstance(route_connection_id, str) else None
                    ),
                )
            except (TypeError, ValueError) as exc:
                return self._failure(
                    request_id,
                    "JOURNEY-EVENT-INVALID",
                    str(exc)[:240] or "O evento não corresponde ao contrato desta jornada.",
                    "review-route",
                )

            payload: dict[str, Any] = {
                "requestId": request_id,
                "state": execution.state,
                "generation": self.navigator.generation,
                "connectionId": execution.connection_id,
                "diagnosticCode": execution.diagnostic_code,
                "diagnosticMessage": execution.diagnostic_message,
                "recoveryAction": execution.recovery_action,
            }
            if execution.state == "operation-request":
                action = execution.action
                selected = record or {}
                if action == "launch":
                    game_id = selected.get("gameId")
                    if not isinstance(game_id, str) or game_id not in self._launchable_game_ids:
                        payload.update(
                            state="operation-unavailable",
                            diagnosticCode="JOURNEY-LAUNCH-UNAVAILABLE",
                            diagnosticMessage=(
                                "Este resultado não possui uma rota de lançamento publicada."
                            ),
                            recoveryAction="choose-launchable-game",
                        )
                    else:
                        payload["operationRequest"] = {
                            "action": action,
                            "gameId": game_id,
                            "recordId": record_id,
                            "connectionId": execution.connection_id,
                            "sessionStage": (execution.target or {}).get("id"),
                        }
                else:
                    payload["operationRequest"] = {
                        "action": action,
                        "gameId": selected.get("gameId"),
                        "recordId": record_id,
                        "connectionId": execution.connection_id,
                        "sessionStage": (execution.target or {}).get("id"),
                    }
                    if action in {"save", "load"} and isinstance(slot, int):
                        payload["operationRequest"]["slot"] = slot
                    if action == "exit":
                        payload["operationRequest"]["confirmed"] = request.get("confirmed") is True
            elif execution.state != "stale-response":
                payload["view"] = self._view()
            return payload

    def _set_facet(self, request: Mapping[str, Any]) -> dict[str, Any]:
        field_id = request.get("fieldId")
        clear = request.get("clear", False)
        unknown = request.get("unknown", False)
        if not isinstance(field_id, str) or not field_id:
            return {
                "state": "invalid-filter",
                "diagnosticCode": "JOURNEY-FACET-FIELD-INVALID",
                "diagnosticMessage": "A faceta não identifica um campo público.",
                "recoveryAction": "choose-public-field",
            }
        menu = self._menus[self.navigator.context.menu_id]
        source_id = str(menu["source"]["readModelId"])
        fields = self._published.get(source_id, {})
        if field_id not in fields or field_id in _NON_FACET_FIELDS:
            return {
                "state": "invalid-filter",
                "diagnosticCode": "JOURNEY-FACET-FIELD-UNAVAILABLE",
                "diagnosticMessage": "O campo não está publicado para esta fonte.",
                "recoveryAction": "choose-public-field",
            }
        filters = dict(self.navigator.context.filters)
        if clear is True:
            filters.pop(field_id, None)
        elif unknown is True:
            filters[field_id] = None
        else:
            value = request.get("value")
            if not self._matches_field_type(value, fields[field_id]):
                return {
                    "state": "invalid-filter",
                    "diagnosticCode": "JOURNEY-FACET-TYPE",
                    "diagnosticMessage": "O valor não corresponde ao tipo publicado desta faceta.",
                    "recoveryAction": "choose-compatible-value",
                }
            filters[field_id] = value
        self.navigator.update_context(
            filters=filters,
            selected_item_id=None,
            scroll_position=0.0,
            focus_id=f"facet:{field_id}",
        )
        return {"state": "filtered", "generation": self.navigator.generation}

    def _view(self) -> dict[str, Any]:
        context = self.navigator.context
        menu = self._menus[context.menu_id]
        source_id = str(menu["source"]["readModelId"])
        fields = self._published.get(source_id, {})
        rows = self._read_models.get(source_id)
        context_filters = [
            {
                "fieldId": field_id,
                "operator": "isUnknown" if value is None else "equals",
                **({} if value is None else {"value": value}),
            }
            for field_id, value in context.filters
        ]
        query = query_public_records(
            rows,
            [*menu.get("filters", []), *context_filters],
            published_fields=fields,
            sort=menu.get("sort", []),
            group_by=menu.get("groupBy", []),
        )
        group_by = [
            str(field_id) for field_id in menu.get("groupBy", []) if isinstance(field_id, str)
        ]
        items = (
            facet_items(group_by, query.groups) if group_by else [dict(row) for row in query.rows]
        )
        filters = dict(context.filters)
        facets = self._facets(menu, source_id, fields, rows, filters)
        theme: Mapping[str, Any] | None = None
        if callable(self._theme_resolver):
            candidate = self._theme_resolver(context.menu_id, menu.get("appearance"))
            if isinstance(candidate, Mapping):
                theme = dict(candidate)
        return {
            "active": True,
            "journeyId": self.document.id,
            "journeyName": str(self.document.data["name"]),
            "menuId": context.menu_id,
            "menuName": str(menu["name"]),
            "entryMenuId": self.document.entry_menu_id,
            "availableEvents": [
                {
                    "event": str(connection["event"]),
                    "connectionId": str(connection["id"]),
                    "action": str(connection["action"]),
                    "label": str(connection["label"]),
                }
                for connection in self.document.data["connections"]
                if connection["from"] == {"kind": "menu", "id": context.menu_id}
                and connection["when"] == "user-input"
            ],
            "generation": self.navigator.generation,
            "selectedItemId": context.selected_item_id,
            "filters": filters,
            "scrollPosition": context.scroll_position,
            "focusId": context.focus_id,
            "canGoBack": self.navigator.can_go_back,
            "sourceState": self._source_states.get(source_id, query.source_state),
            "resultState": query.result_state,
            "items": items,
            "totalCount": query.total_count,
            "resultCount": query.result_count,
            "unknownValueCounts": dict(query.unknown_value_counts),
            "diagnosticCode": query.diagnostic_code,
            "diagnosticMessage": query.diagnostic_message,
            "recoveryAction": query.recovery_action,
            "facets": facets,
            "groups": [
                {"values": dict(group["values"]), "count": int(group["count"])}
                for group in query.groups
            ],
            "appearance": dict(menu.get("appearance", {})),
            "theme": dict(theme) if theme is not None else None,
        }

    def _facets(
        self,
        menu: Mapping[str, Any],
        _source_id: str,
        fields: Mapping[str, str],
        rows: Sequence[Mapping[str, Any]] | None,
        active_filters: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        field_ids = [
            field_id
            for field_id in _DEFAULT_FACETS
            if field_id in fields and field_id not in _NON_FACET_FIELDS
        ]
        field_ids.extend(
            field_id
            for field_id, field_type in fields.items()
            if field_id not in _NON_FACET_FIELDS
            and field_id not in field_ids
            and field_type in {"string", "integer", "number", "boolean"}
        )
        for item_filter in menu.get("filters", []):
            field_id = str(item_filter.get("fieldId", ""))
            if (
                field_id in fields
                and field_id not in _NON_FACET_FIELDS
                and field_id not in field_ids
            ):
                field_ids.append(field_id)
        facets: list[dict[str, Any]] = []
        for field_id in field_ids:
            other_context = [
                {
                    "fieldId": key,
                    "operator": "isUnknown" if value is None else "equals",
                    **({} if value is None else {"value": value}),
                }
                for key, value in active_filters.items()
                if key != field_id
            ]
            base = query_public_records(
                rows,
                [*menu.get("filters", []), *other_context],
                published_fields=fields,
                sort=menu.get("sort", []),
            )
            known: dict[str, tuple[Any, int]] = {}
            unknown_count = 0
            for row in base.rows:
                value = row.get(field_id)
                if value is None:
                    unknown_count += 1
                    continue
                values = (
                    value if fields[field_id] == "string[]" and isinstance(value, list) else [value]
                )
                for item in values:
                    token = json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False)
                    previous = known.get(token)
                    known[token] = (item, (previous[1] if previous else 0) + 1)
            options: list[dict[str, Any]] = [
                {"kind": "all", "label": "Todos", "count": len(base.rows)}
            ]
            for token in sorted(known, key=lambda value: value.casefold()):
                item, count = known[token]
                options.append({"kind": "value", "value": item, "label": str(item), "count": count})
            if unknown_count:
                options.append({"kind": "unknown", "label": "Desconhecido", "count": unknown_count})
            facets.append(
                {
                    "fieldId": field_id,
                    "label": self._field_label(field_id),
                    "type": fields[field_id],
                    "selected": field_id in active_filters,
                    "selectedValue": active_filters.get(field_id),
                    "options": options,
                }
            )
        return facets

    @staticmethod
    def _field_label(field_id: str) -> str:
        return {
            "platformId": "Plataforma",
            "genre": "Gênero",
            "year": "Ano",
            "developer": "Desenvolvedora",
            "publisher": "Publicadora",
            "family": "Família",
            "emulatorId": "Emulador",
            "availability": "Disponibilidade",
        }.get(field_id, field_id)

    @staticmethod
    def _matches_field_type(value: Any, field_type: str) -> bool:
        if value is None:
            return False
        if field_type == "number":
            return (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and (not isinstance(value, float) or math.isfinite(value))
            )
        return {
            "string": isinstance(value, str),
            "string[]": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
        }.get(field_type, False)

    @staticmethod
    def _finite_nonnegative(value: Any) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value < 0
        ):
            return 0.0
        return float(value)

    @staticmethod
    def _request_focus(value: Any) -> str | None:
        return value if value is None or isinstance(value, str) else None

    def _failure(
        self,
        request_id: Any,
        code: str,
        message: str,
        recovery: str,
        *,
        state: str = "rejected",
    ) -> dict[str, Any]:
        return {
            "requestId": request_id if isinstance(request_id, str) else None,
            "state": state,
            "generation": self.navigator.generation,
            "diagnosticCode": code,
            "diagnosticMessage": message,
            "recoveryAction": recovery,
        }
