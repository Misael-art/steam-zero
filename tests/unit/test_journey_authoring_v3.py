# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Visual Journey authoring: instance natures, launch entry, graph edits (v3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

from steamzero.adapters.journey_studio import JourneyStudioService
from steamzero.domain.experience_journey import (
    JourneyDocument,
    JourneyExecutor,
    migrate_journey_v2_to_v3,
)

_FIELDS = {"library.games": {"platformId": "string", "genre": "string", "title": "string"}}


def _menu(menu_id: str, name: str) -> dict[str, Any]:
    return {
        "id": menu_id,
        "name": name,
        "source": {"readModelId": "library.games"},
        "filters": [],
        "sort": [],
        "groupBy": [],
    }


def _link(
    cid: str,
    source: str,
    event: str,
    action: str,
    target: dict[str, str],
    when: str = "user-input",
) -> dict[str, Any]:
    return {
        "id": cid,
        "from": {"kind": "menu", "id": source},
        "event": event,
        "when": when,
        "action": action,
        "to": target,
        "label": cid,
    }


def _codes(snapshot: dict[str, Any]) -> set[str]:
    return {item["code"] for item in snapshot["diagnostics"]}


def _add(service: JourneyStudioService, sid: str, menu_id: str, name: str, nature: str) -> None:
    service.transact(sid, "add-menu", {"menu": _menu(menu_id, name)})
    service.transact(sid, "set-nature", {"menuId": menu_id, "nature": nature})


def test_v2_documents_stay_v2_until_a_v3_feature_is_authored(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path)
    snap = service.create(template="blank", journey_id="org.test.empty")
    assert snap["document"]["schemaVersion"] == 2
    sid = snap["sessionId"]
    snap = service.transact(sid, "set-layout", {"menuId": "home", "x": 40, "y": 80})
    assert snap["document"]["schemaVersion"] == 3
    assert snap["document"]["kind"] == "steamzero-experience-journey-v3"
    assert snap["document"]["menus"][0]["layout"] == {"x": 40.0, "y": 80.0}
    snap = service.undo(sid)
    assert snap["document"]["schemaVersion"] == 2


def test_migration_preserves_ids_and_is_idempotent() -> None:
    raw = JourneyStudioService(Path("/nonexistent")).natures()
    assert "direct-launch" in raw
    doc = {
        "schemaVersion": 2,
        "kind": "steamzero-experience-journey-v2",
        "id": "org.test.keep",
        "name": "Keep",
        "entryMenuId": "a",
        "organization": [],
        "menus": [_menu("a", "A")],
        "connections": [],
        "sessionStages": [],
    }
    once = migrate_journey_v2_to_v3(doc)
    assert migrate_journey_v2_to_v3(once) == once
    assert once["menus"] == doc["menus"]
    assert JourneyDocument.parse(once).id == "org.test.keep"


def test_edit_journey_from_empty_change_nature_remap_delete_and_undo(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path / "journeys")
    sid = service.create(template="blank", journey_id="org.test.edit")["sessionId"]
    service.transact(sid, "set-nature", {"menuId": "home", "nature": "free"})
    _add(service, sid, "games", "Jogos", "games")
    _add(service, sid, "cats", "Categorias", "categories")
    service.transact(sid, "rename-menu", {"menuId": "cats", "name": "Gêneros"})
    service.transact(sid, "set-layout", {"menuId": "cats", "x": 300, "y": 10})
    service.transact(
        sid,
        "add-connection",
        {
            "connection": _link(
                "to-cats", "home", "select", "navigate", {"kind": "menu", "id": "cats"}
            )
        },
    )
    service.transact(
        sid,
        "add-connection",
        {
            "connection": _link(
                "cats-games", "cats", "select", "navigate", {"kind": "menu", "id": "games"}
            )
        },
    )
    # Changing nature keeps the ID and leaves the now-invalid output for remapping.
    snap = service.transact(sid, "set-nature", {"menuId": "cats", "nature": "transition"})
    cats = next(m for m in snap["document"]["menus"] if m["id"] == "cats")
    assert cats["name"] == "Gêneros" and cats["layout"] == {"x": 300.0, "y": 10.0}
    assert any(c["id"] == "cats-games" for c in snap["document"]["connections"])
    assert "JOURNEY-NATURE-OUTPUT-INCOMPATIBLE" in _codes(snap)
    snap = service.transact(
        sid,
        "update-connection",
        {"connectionId": "cats-games", "event": "complete", "when": "operation-success"},
    )
    assert "JOURNEY-NATURE-OUTPUT-INCOMPATIBLE" not in _codes(snap)

    impact = service.removal_impact(sid, "games")
    assert impact["incomingConnectionIds"] == ["cats-games"] and not impact["isEntry"]
    snap = service.transact(sid, "delete-instance", {"menuId": "games"})
    assert "games" not in {m["id"] for m in snap["document"]["menus"]}
    assert "cats-games" not in {c["id"] for c in snap["document"]["connections"]}
    snap = service.undo(sid)
    assert "games" in {m["id"] for m in snap["document"]["menus"]}
    assert "cats-games" in {c["id"] for c in snap["document"]["connections"]}
    with pytest.raises(ValueError, match="entrada"):
        service.transact(sid, "delete-instance", {"menuId": "home"})


def test_manual_cycle_is_allowed_and_automatic_cycle_is_blocked(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path)
    sid = service.create(template="blank", journey_id="org.test.cycle")["sessionId"]
    _add(service, sid, "b", "B", "free")
    service.transact(
        sid,
        "add-connection",
        {"connection": _link("h-b", "home", "select", "navigate", {"kind": "menu", "id": "b"})},
    )
    snap = service.transact(
        sid,
        "add-connection",
        {"connection": _link("b-h", "b", "back", "back", {"kind": "menu", "id": "home"})},
    )
    assert "JOURNEY-AUTOMATIC-CYCLE" not in _codes(snap)
    _add(service, sid, "f1", "Fade 1", "transition")
    _add(service, sid, "f2", "Fade 2", "transition")
    for cid, a, b in (("f1-f2", "f1", "f2"), ("f2-f1", "f2", "f1")):
        snap = service.transact(
            sid,
            "add-connection",
            {
                "connection": _link(
                    cid, a, "complete", "navigate", {"kind": "menu", "id": b}, "operation-success"
                )
            },
        )
    assert "JOURNEY-AUTOMATIC-CYCLE" in _codes(snap)
    with pytest.raises(ValueError):
        service.save(sid)


def _direct_launch(service: JourneyStudioService, sid: str, source: str) -> dict[str, Any]:
    service.transact(sid, "set-nature", {"menuId": "home", "nature": "direct-launch"})
    service.transact(
        sid,
        "set-launch-request",
        {"menuId": "home", "launchRequest": {"gameSource": source, "timeoutSeconds": 30}},
    )
    _add(service, sid, "pick", "Escolher jogo", "games")
    _add(service, sid, "recover", "Recuperação", "recovery")
    _add(service, sid, "session", "Sessão", "session")
    return service.snapshot(sid)


def test_direct_launch_entry_requires_outcomes_and_context_route(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path)
    sid = service.create(template="blank", journey_id="org.test.direct")["sessionId"]
    snap = _direct_launch(service, sid, "context")
    codes = _codes(snap)
    assert {"JOURNEY-LAUNCH-OUTCOME-MISSING", "JOURNEY-LAUNCH-CONTEXT-ROUTE"} <= codes
    links = [
        _link(
            "ok", "home", "play", "launch", {"kind": "menu", "id": "session"}, "operation-success"
        ),
        _link(
            "fail", "home", "play", "launch", {"kind": "menu", "id": "recover"}, "operation-failure"
        ),
        _link("late", "home", "play", "launch", {"kind": "menu", "id": "recover"}, "timeout"),
        _link(
            "none",
            "home",
            "context-missing",
            "navigate",
            {"kind": "menu", "id": "pick"},
            "operation-failure",
        ),
        _link("retry", "recover", "retry", "retry", {"kind": "menu", "id": "home"}),
        _link("pick-back", "pick", "back", "back", {"kind": "history"}),
        _link("end", "session", "exit", "exit", {"kind": "history"}),
    ]
    for link in links:
        snap = service.transact(sid, "add-connection", {"connection": link})
    errors = {i["code"] for i in snap["diagnostics"] if i["severity"] == "error"}
    assert not errors, snap["diagnostics"]
    service.save(sid)
    reopened = JourneyStudioService(tmp_path).load("org.test.direct")["document"]
    home = next(m for m in reopened["menus"] if m["id"] == "home")
    assert home["launchRequest"] == {"gameSource": "context", "timeoutSeconds": 30}
    with pytest.raises(ValidationError):
        service.transact(
            sid, "set-launch-request", {"menuId": "home", "launchRequest": {"gameSource": "fixed"}}
        )


def test_platform_game_fade_session_and_shared_list_from_two_origins(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path)
    sid = service.create(template="blank", journey_id="org.test.abcd")["sessionId"]
    service.transact(sid, "set-nature", {"menuId": "home", "nature": "platforms"})
    _add(service, sid, "games", "Jogos", "games")
    _add(service, sid, "genres", "Gêneros", "categories")
    _add(service, sid, "fade", "Fade", "transition")
    _add(service, sid, "session", "Sessão com bezel", "session")
    _add(service, sid, "recover", "Recuperação", "recovery")
    mid = {"kind": "menu"}
    links = [
        {
            **_link("plat", "home", "select", "navigate", {**mid, "id": "games"}),
            "bindings": [{"sourceFieldId": "platformId", "targetFieldId": "platformId"}],
        },
        _link("cat", "home", "route", "navigate", {**mid, "id": "genres"}),
        {
            **_link("genre", "genres", "select", "navigate", {**mid, "id": "games"}),
            "bindings": [{"sourceFieldId": "genre", "targetFieldId": "genre"}],
        },
        _link("g-back", "genres", "back", "back", {"kind": "history"}),
        _link("play", "games", "play", "launch", {**mid, "id": "fade"}, "operation-success"),
        _link(
            "play-fail", "games", "play", "launch", {**mid, "id": "recover"}, "operation-failure"
        ),
        _link("play-late", "games", "play", "launch", {**mid, "id": "recover"}, "timeout"),
        _link("games-back", "games", "back", "back", {"kind": "history"}),
        _link(
            "faded", "fade", "complete", "navigate", {**mid, "id": "session"}, "operation-success"
        ),
        _link("exit", "session", "exit", "exit", {"kind": "history"}),
        _link("r-retry", "recover", "retry", "retry", {**mid, "id": "games"}),
    ]
    for link in links:
        snap = service.transact(sid, "add-connection", {"connection": link})
    assert not [i for i in snap["diagnostics"] if i["severity"] == "error"], snap["diagnostics"]
    service.transact(sid, "set-stage-bezel", {"stageId": "bezel", "bezelResource": "aura-default"})
    service.save(sid)
    document = JourneyDocument.parse(
        (tmp_path / "org.test.abcd.json").read_bytes()
        if (tmp_path / "org.test.abcd.json").exists()
        else json.dumps(service.snapshot(sid)["document"])
    )
    executor = JourneyExecutor(document, published_read_models=_FIELDS)
    records = {
        "library.games": [
            {"id": "g1", "platformId": "snes", "genre": "rpg", "title": "Um"},
            {"id": "g2", "platformId": "gba", "genre": "rpg", "title": "Dois"},
        ]
    }
    result = executor.execute(
        "select",
        selected_record={"platformId": "snes"},
        read_models=records,
        published_read_models=_FIELDS,
    )
    assert executor.navigator.context.menu_id == "games", result
    assert ("platformId", "snes") in executor.navigator.context.filters
    pending = executor.request_operation("play")
    assert pending.state == "operation-request"
    # Session is not entered until the service reports the observed result.
    assert executor.navigator.context.menu_id == "games"
    assert executor.request_operation("play").state == "operation-pending"
    done = executor.resolve_operation(pending.connection_id, "operation-success")
    assert executor.navigator.context.menu_id == "fade", done
    executor.execute("complete", when="operation-success")
    assert executor.navigator.context.menu_id == "session"
    # Bezel availability and fallback are separate published stage contracts.
    assert any(
        stage.get("bezelResource") == "aura-default" for stage in document.data["sessionStages"]
    )


def _direct_document(tmp_path: Path, source: str, game_id: str | None = None) -> JourneyDocument:
    service = JourneyStudioService(tmp_path)
    sid = service.create(template="blank", journey_id="org.test.direct")["sessionId"]
    _direct_launch(service, sid, source)
    if game_id is not None:
        service.transact(
            sid,
            "set-launch-request",
            {"menuId": "home", "launchRequest": {"gameSource": "fixed", "gameId": game_id}},
        )
    for link in (
        _link(
            "ok", "home", "play", "launch", {"kind": "menu", "id": "session"}, "operation-success"
        ),
        _link(
            "fail", "home", "play", "launch", {"kind": "menu", "id": "recover"}, "operation-failure"
        ),
        _link("late", "home", "play", "launch", {"kind": "menu", "id": "recover"}, "timeout"),
        _link(
            "none",
            "home",
            "context-missing",
            "navigate",
            {"kind": "menu", "id": "pick"},
            "operation-failure",
        ),
        _link("retry", "recover", "retry", "retry", {"kind": "menu", "id": "home"}),
        _link("pick-back", "pick", "back", "back", {"kind": "history"}),
        _link("end", "session", "exit", "exit", {"kind": "history"}),
    ):
        service.transact(sid, "add-connection", {"connection": link})
    return JourneyDocument.parse(json.dumps(service.snapshot(sid)["document"]))


def test_direct_launch_context_missing_failure_timeout_retry_and_stale(tmp_path: Path) -> None:
    executor = JourneyExecutor(
        _direct_document(tmp_path / "a", "context"), published_read_models=_FIELDS
    )
    missing = executor.request_operation("play")
    assert missing.state == "context-missing" and executor.navigator.context.menu_id == "pick"

    executor = JourneyExecutor(
        _direct_document(tmp_path / "b", "context", game_id="game-1"), published_read_models=_FIELDS
    )
    first = executor.request_operation("play")
    assert first.state == "operation-request"
    assert executor.pending_operation["gameId"] == "game-1"
    failed = executor.resolve_operation(first.connection_id, "operation-failure")
    assert failed.state == "navigated" and executor.navigator.context.menu_id == "recover"
    assert (
        executor.resolve_operation(first.connection_id, "operation-success").state
        == "stale-response"
    )
    assert executor.navigator.context.menu_id == "recover"
    executor.navigator.navigate("home")
    second = executor.request_operation("play")
    executor.resolve_operation(second.connection_id, "timeout")
    assert executor.navigator.context.menu_id == "recover"
    executor.navigator.navigate("home")
    third = executor.request_operation("play")
    assert executor.request_operation("play").state == "operation-pending"
    executor.resolve_operation(third.connection_id, "operation-success")
    assert executor.navigator.context.menu_id == "session"


def test_return_after_session_restores_selection_filters_focus_and_scroll(tmp_path: Path) -> None:
    executor = JourneyExecutor(
        _direct_document(tmp_path, "context", game_id="game-1"), published_read_models=_FIELDS
    )
    executor.navigator.navigate("pick", filters={"genre": "rpg"})
    executor.navigator.update_context(
        selected_item_id="g7", focus_id="tile-g7", scroll_position=420.0
    )
    stale = executor.navigator.capture_return_context()
    executor.navigator.navigate("session")
    restored = executor.navigator.back()
    assert restored is not None and restored.menu_id == "pick"
    assert ("genre", "rpg") in restored.filters
    assert (restored.selected_item_id, restored.focus_id, restored.scroll_position) == (
        "g7",
        "tile-g7",
        420.0,
    )
    # A late response captured before the newer navigation keeps the current context.
    executor.navigator.update_context(selected_item_id="g8")
    assert not executor.navigator.restore_return_context(stale)
    assert executor.navigator.context.selected_item_id == "g8"
