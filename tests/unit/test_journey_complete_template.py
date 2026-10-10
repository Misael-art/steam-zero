# SPDX-License-Identifier: GPL-3.0-or-later
"""Jornada completa como ponto de partida do Studio.

O modelo precisa ser um documento comum: válido, salvável, editável pelas
mesmas operações e navegável pelo runtime do Launcher. Um modelo que só
"parecesse" completo e reprovasse na primeira edição seria pior que o vazio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from steamzero.adapters.journey_public import journey_public_field_types
from steamzero.adapters.journey_studio import JOURNEY_TEMPLATES, JourneyStudioService
from steamzero.domain.experience_journey import SESSION_STAGES, JourneyDocument
from steamzero.launcher.journey_runtime import JourneyRuntime


def _complete(tmp_path: Path) -> tuple[JourneyStudioService, dict[str, object]]:
    service = JourneyStudioService(tmp_path / "journeys")
    return service, service.create(name="Minha sala", template="complete")


def test_complete_template_declares_menu_levels_session_actions_and_stages(tmp_path: Path) -> None:
    _service, snapshot = _complete(tmp_path)
    document = snapshot["document"]

    assert snapshot["diagnostics"] == []
    assert document["name"] == "Minha sala"
    assert document["entryMenuId"] == "platforms"
    assert [menu["id"] for menu in document["menus"]] == ["platforms", "genres", "years", "games"]

    parents = {node["menuId"]: node["parentId"] for node in document["organization"]}
    assert parents == {
        "platforms": None,
        "genres": "menu-platforms",
        "years": "menu-platforms",
        "games": "menu-genres",
    }

    session_events = {
        connection["event"]: connection["to"]["id"]
        for connection in document["connections"]
        if connection["to"]["kind"] == "stage"
    }
    assert session_events == {
        "play": "entryFade",
        "pause": "pause",
        "resume": "pause",
        "open-saves": "saves",
        "save": "saves",
        "load": "saves",
        "exit": "exitFade",
    }

    stages = {stage["stageId"]: stage for stage in document["sessionStages"]}
    assert {"entryFade", "exitFade", "pause", "saves", "bezel", "gameplay", "osd"} <= set(stages)
    assert set(stages) <= SESSION_STAGES
    # Aparência herdada e nenhum bezel inventado: a imagem é escolha do autor.
    assert all(stage["appearance"] == {"mode": "inherit-aura"} for stage in stages.values())
    assert "bezelResource" not in stages["bezel"]


def test_complete_template_saves_reopens_and_accepts_normal_edits(tmp_path: Path) -> None:
    service, snapshot = _complete(tmp_path)
    session_id = str(snapshot["sessionId"])

    edited = service.transact(
        session_id,
        "rename-menu",
        {"menuId": "games", "name": "Todos os jogos"},
        expected_generation=int(snapshot["generation"]),
    )
    assert edited["document"]["menus"][3]["name"] == "Todos os jogos"
    undone = service.undo(session_id)
    assert undone["document"]["menus"][3]["name"] == "Jogos"

    saved = service.save(session_id)
    reopened = service.load(str(saved["journeyId"]))
    assert reopened["document"] == undone["document"]
    assert reopened["dirty"] is False


def test_blank_remains_the_default_and_unknown_template_is_refused(tmp_path: Path) -> None:
    service = JourneyStudioService(tmp_path / "journeys")
    blank = service.create(name="Simples")
    assert [menu["id"] for menu in blank["document"]["menus"]] == ["home"]
    assert blank["document"]["sessionStages"] == []
    assert JOURNEY_TEMPLATES == ("blank", "complete")
    with pytest.raises(ValueError, match="modelo de jornada desconhecido"):
        service.create(name="Outra", template="surpresa")


def test_launcher_runtime_walks_every_menu_level_of_the_template(tmp_path: Path) -> None:
    _service, snapshot = _complete(tmp_path)
    games = [
        {
            "id": "emulation:metroid",
            "gameId": "metroid",
            "title": "Metroid",
            "name": "Metroid",
            "source": "emulation",
            "platformId": "nes-famicom",
            "year": 1986,
            "genre": "Action",
            "developer": "Nintendo",
        }
    ]
    runtime = JourneyRuntime(
        JourneyDocument.parse(snapshot["document"]),
        read_models={
            "library.games": games,
            "library.platforms": [
                {
                    "id": "nes-famicom",
                    "name": "NES",
                    "shortName": "NES",
                    "state": "available",
                    "gameCount": 1,
                }
            ],
        },
        published_read_models={
            "library.games": journey_public_field_types(),
            "library.platforms": {
                "id": "string",
                "name": "string",
                "shortName": "string",
                "state": "string",
                "gameCount": "integer",
            },
        },
        source_states={"library.games": "available", "library.platforms": "available"},
        launchable_game_ids=("metroid",),
    )

    def send(
        event: str, record_id: str | None = None, connection_id: str | None = None
    ) -> dict[str, object]:
        view = runtime.current()
        request: dict[str, object] = {
            "requestId": f"request-{view['generation']}-{event}",
            "event": event,
            "menuId": view["menuId"],
            "generation": view["generation"],
            "scrollPosition": 0,
            "focusId": "card:focused",
        }
        if record_id is not None:
            request["recordId"] = record_id
        if connection_id is not None:
            request["connectionId"] = connection_id
        return runtime.handle(request)

    assert runtime.current()["menuId"] == "platforms"
    send("select", "nes-famicom")
    assert runtime.current()["menuId"] == "genres"
    send("select", "emulation:metroid")
    assert runtime.current()["menuId"] == "games"
    send("back")
    assert runtime.current()["menuId"] == "genres"
    send("back")
    assert runtime.current()["menuId"] == "platforms"
    send("route", "nes-famicom", "platforms-years")
    assert runtime.current()["menuId"] == "years"
