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
    grouped = {menu["id"]: menu["groupBy"] for menu in document["menus"]}
    assert grouped == {"platforms": [], "genres": ["genre"], "years": ["year"], "games": []}

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
    genres = runtime.current()
    assert genres["menuId"] == "genres"
    assert genres["items"][0]["title"] == "Action"
    send("select", str(genres["items"][0]["id"]))
    assert runtime.current()["menuId"] == "games"
    send("back")
    assert runtime.current()["menuId"] == "genres"
    send("back")
    assert runtime.current()["menuId"] == "platforms"
    send("route", "nes-famicom", "platforms-years")
    assert runtime.current()["menuId"] == "years"


def _library() -> dict[str, list[dict[str, object]]]:
    return {
        "library.platforms": [
            {
                "id": "nes-famicom",
                "name": "NES",
                "shortName": "NES",
                "state": "available",
                "gameCount": 4,
            },
            {
                "id": "sms",
                "name": "Master System",
                "shortName": "SMS",
                "state": "available",
                "gameCount": 1,
            },
        ],
        "library.games": [
            {
                "id": "emulation:alpha",
                "gameId": "alpha",
                "title": "Alpha",
                "name": "Alpha",
                "source": "emulation",
                "platformId": "nes-famicom",
                "year": 1986,
                "genre": "Action",
            },
            {
                "id": "emulation:beta",
                "gameId": "beta",
                "title": "Beta",
                "name": "Beta",
                "source": "emulation",
                "platformId": "nes-famicom",
                "year": 1986,
                "genre": "Action",
            },
            {
                "id": "emulation:gamma",
                "gameId": "gamma",
                "title": "Gamma",
                "name": "Gamma",
                "source": "emulation",
                "platformId": "nes-famicom",
                "year": 1987,
                "genre": "RPG",
            },
            {
                "id": "emulation:delta",
                "gameId": "delta",
                "title": "Delta",
                "name": "Delta",
                "source": "emulation",
                "platformId": "nes-famicom",
                "year": None,
                "genre": None,
            },
            {
                "id": "emulation:epsilon",
                "gameId": "epsilon",
                "title": "Epsilon",
                "name": "Epsilon",
                "source": "emulation",
                "platformId": "sms",
                "year": 1986,
                "genre": "Action",
            },
        ],
    }


def _runtime(
    document: dict[str, object],
    *,
    games: list[dict[str, object]] | None,
    source_states: dict[str, str] | None = None,
) -> JourneyRuntime:
    library = _library()
    return JourneyRuntime(
        JourneyDocument.parse(document),
        read_models={
            "library.platforms": library["library.platforms"],
            "library.games": games,
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
        source_states=source_states
        or {"library.games": "available", "library.platforms": "available"},
        launchable_game_ids=("alpha", "beta", "gamma", "delta", "epsilon"),
    )


def _event(
    view: dict[str, object],
    event: str,
    request_id: str,
    **extra: object,
) -> dict[str, object]:
    request: dict[str, object] = {
        "requestId": request_id,
        "event": event,
        "menuId": view["menuId"],
        "generation": view["generation"],
        "scrollPosition": extra.pop("scrollPosition", 0),
        "focusId": extra.pop("focusId", "card:focused"),
    }
    request.update(extra)
    return request


def test_complete_template_preview_keeps_game_rows_and_distinct_groups(tmp_path: Path) -> None:
    """A prévia do Studio continua devolvendo jogos; a lista usa os grupos."""
    service, snapshot = _complete(tmp_path)
    library = _library()
    published = {
        "library.games": journey_public_field_types(),
        "library.platforms": {
            "id": "string",
            "name": "string",
            "shortName": "string",
            "state": "string",
            "gameCount": "integer",
        },
    }
    preview = service.preview_menu(
        str(snapshot["sessionId"]),
        "genres",
        rows=library["library.games"],
        published_fields=journey_public_field_types(),
        published_read_models=published,
        context_filters={"platformId": "nes-famicom"},
    )
    assert [row["id"] for row in preview["rows"]] == [
        "emulation:alpha",
        "emulation:beta",
        "emulation:gamma",
        "emulation:delta",
    ]
    assert [(group["values"].get("genre"), group["count"]) for group in preview["groups"]] == [
        ("Action", 2),
        ("RPG", 1),
        (None, 1),
    ]
    games = service.preview_menu(
        str(snapshot["sessionId"]),
        "games",
        rows=library["library.games"],
        published_fields=journey_public_field_types(),
        published_read_models=published,
        context_filters={"platformId": "nes-famicom", "genre": "Action"},
    )
    assert [row["id"] for row in games["rows"]] == ["emulation:alpha", "emulation:beta"]
    assert games["groups"] == [{"values": {}, "count": 2}]


def test_complete_template_lists_distinct_genre_and_year_facets(tmp_path: Path) -> None:
    """Três jogos NES não podem repetir Action/1986 nos menus de faceta."""
    _service, snapshot = _complete(tmp_path)
    runtime = _runtime(snapshot["document"], games=_library()["library.games"])

    platforms = runtime.current()
    opened = runtime.handle(
        _event(
            platforms,
            "select",
            "open-nes",
            recordId="nes-famicom",
            scrollPosition=24,
            focusId="platform:nes",
        )
    )
    genres = opened["view"]
    assert genres["menuId"] == "genres"
    assert genres["filters"]["platformId"] == "nes-famicom"
    assert [(item["title"], item["count"]) for item in genres["items"]] == [
        ("Action", 2),
        ("RPG", 1),
        ("Desconhecido", 1),
    ]
    assert all(item["facet"] is True for item in genres["items"])
    assert {item["gameId"] for item in genres["items"] if "gameId" in item} == set()

    action = genres["items"][0]
    games = runtime.handle(
        _event(
            genres,
            "select",
            "open-action",
            recordId=action["id"],
            scrollPosition=48,
            focusId="facet:action",
        )
    )["view"]
    assert games["menuId"] == "games"
    assert games["filters"] == {"platformId": "nes-famicom", "genre": "Action"}
    assert [item["gameId"] for item in games["items"]] == ["alpha", "beta"]

    restored = runtime.handle(_event(games, "back", "back-genres"))["view"]
    assert restored["menuId"] == "genres"
    assert restored["selectedItemId"] == action["id"]
    assert restored["scrollPosition"] == 48
    assert restored["focusId"] == "facet:action"
    assert restored["filters"] == {"platformId": "nes-famicom"}

    years = runtime.handle(
        _event(
            runtime.handle(_event(restored, "back", "back-platforms"))["view"],
            "route",
            "open-years",
            recordId="nes-famicom",
            connectionId="platforms-years",
        )
    )["view"]
    assert years["menuId"] == "years"
    assert [(item["title"], item["count"]) for item in years["items"]] == [
        ("1987", 1),
        ("1986", 2),
        ("Desconhecido", 1),
    ]
    year_games = runtime.handle(
        _event(years, "select", "open-1986", recordId=years["items"][1]["id"])
    )["view"]
    assert year_games["menuId"] == "games"
    assert year_games["filters"] == {"platformId": "nes-famicom", "year": 1986}
    assert [item["gameId"] for item in year_games["items"]] == ["alpha", "beta"]

    unknown_years = runtime.handle(_event(year_games, "back", "back-years"))["view"]
    unknown = runtime.handle(
        _event(
            unknown_years,
            "select",
            "open-unknown-year",
            recordId=unknown_years["items"][2]["id"],
        )
    )["view"]
    assert unknown["filters"]["year"] is None
    assert [item["gameId"] for item in unknown["items"]] == ["delta"]

    stale = runtime.handle(_event(years, "select", "late-year", recordId=years["items"][1]["id"]))
    assert stale["state"] == "stale-response"
    assert runtime.current()["menuId"] == "games"
    assert runtime.current()["filters"]["year"] is None

    empty = _runtime(snapshot["document"], games=[])
    empty_genres = empty.handle(
        _event(empty.current(), "select", "empty-nes", recordId="nes-famicom")
    )["view"]
    assert empty_genres["items"] == []
    assert empty_genres["resultState"] == "zero-results"
    assert empty_genres["sourceState"] == "available"

    offline = _runtime(
        snapshot["document"],
        games=None,
        source_states={"library.platforms": "available", "library.games": "unavailable"},
    )
    offline_genres = offline.handle(
        _event(offline.current(), "select", "offline-nes", recordId="nes-famicom")
    )["view"]
    assert offline_genres["items"] == []
    assert offline_genres["sourceState"] == "unavailable"
    assert offline_genres["resultState"] == "source-unavailable"
