# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path

from steamzero.adapters.journey_public import journey_public_field_types, project_game_row
from steamzero.core.errors import SteamZeroError
from steamzero.domain.experience_journey import JourneyDocument, JourneyStore
from steamzero.launcher.journey_runtime import JourneyRuntime


def _journey() -> JourneyDocument:
    return JourneyDocument.parse(
        {
            "schemaVersion": 2,
            "kind": "steamzero-experience-journey-v2",
            "id": "org.steamzero.launcher-test",
            "name": "Launcher de teste",
            "entryMenuId": "platforms",
            "organization": [],
            "menus": [
                {
                    "id": "platforms",
                    "name": "Plataformas",
                    "source": {"readModelId": "library.platforms"},
                    "filters": [],
                    "sort": [],
                },
                {
                    "id": "genres",
                    "name": "Gêneros",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [],
                },
                {
                    "id": "years",
                    "name": "Anos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [],
                },
                {
                    "id": "games",
                    "name": "Jogos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [],
                },
            ],
            "connections": [
                {
                    "id": "platforms-to-genres",
                    "from": {"kind": "menu", "id": "platforms"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "genres"},
                    "label": "Abrir gêneros",
                    "bindings": [{"sourceFieldId": "id", "targetFieldId": "platformId"}],
                },
                {
                    "id": "genres-to-games",
                    "from": {"kind": "menu", "id": "genres"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "games"},
                    "label": "Abrir jogos",
                    "bindings": [{"sourceFieldId": "genre", "targetFieldId": "genre"}],
                },
                {
                    "id": "years-to-games",
                    "from": {"kind": "menu", "id": "years"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "games"},
                    "label": "Abrir jogos",
                    "bindings": [{"sourceFieldId": "year", "targetFieldId": "year"}],
                },
                {
                    "id": "games-back",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "back",
                    "when": "user-input",
                    "action": "back",
                    "to": {"kind": "history"},
                    "label": "Voltar",
                },
                {
                    "id": "games-play",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "play",
                    "when": "user-input",
                    "action": "launch",
                    "to": {"kind": "stage", "id": "entryFade"},
                    "label": "Jogar",
                },
            ],
            "sessionStages": [],
        }
    )


def _runtime() -> JourneyRuntime:
    fields = journey_public_field_types()
    platform_fields = {
        "id": "string",
        "name": "string",
        "shortName": "string",
        "state": "string",
        "gameCount": "integer",
    }
    games = [
        {
            "id": "emulation:celeste",
            "gameId": "celeste",
            "title": "Celeste",
            "name": "Celeste",
            "source": "emulation",
            "platformId": "nes-famicom",
            "year": 2018,
            "genre": "Platformer",
            "developer": "Maddy Makes Games",
        },
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
        },
        {
            "id": "emulation:unknown",
            "gameId": "unknown",
            "title": "Sem metadados",
            "name": "Sem metadados",
            "source": "emulation",
            "platformId": "snes",
            "year": None,
            "genre": None,
            "developer": None,
        },
    ]
    return JourneyRuntime(
        _journey(),
        read_models={
            "library.games": games,
            "library.platforms": [
                {
                    "id": "nes-famicom",
                    "name": "NES",
                    "shortName": "NES",
                    "state": "available",
                    "gameCount": 2,
                },
                {
                    "id": "snes",
                    "name": "Super Nintendo",
                    "shortName": "SNES",
                    "state": "available",
                    "gameCount": 1,
                },
            ],
        },
        published_read_models={
            "library.games": fields,
            "library.platforms": platform_fields,
        },
        source_states={"library.games": "available", "library.platforms": "available"},
        launchable_game_ids=("celeste", "metroid", "unknown"),
    )


def _event(
    runtime: JourneyRuntime, event: str, *, record_id: str | None = None
) -> dict[str, object]:
    view = runtime.current()
    request: dict[str, object] = {
        "requestId": f"request-{runtime.navigator.generation}-{event}",
        "event": event,
        "menuId": view["menuId"],
        "generation": view["generation"],
        "scrollPosition": 84,
        "focusId": "card:focused",
    }
    if record_id is not None:
        request["recordId"] = record_id
    return runtime.handle(request)


def test_saved_runtime_executes_shared_menu_routes_and_restores_origin_context() -> None:
    runtime = _runtime()
    platforms = runtime.current()
    assert platforms["menuName"] == "Plataformas"
    assert len(platforms["facets"]) >= 2

    selected_platform = _event(runtime, "select", record_id="nes-famicom")
    assert selected_platform["state"] == "navigated"
    assert selected_platform["view"]["menuId"] == "genres"
    assert selected_platform["view"]["filters"]["platformId"] == "nes-famicom"

    selected_genre = _event(runtime, "select", record_id="emulation:celeste")
    assert selected_genre["state"] == "navigated"
    assert selected_genre["connectionId"] == "genres-to-games"
    assert selected_genre["view"]["menuId"] == "games"
    assert selected_genre["view"]["filters"]["genre"] == "Platformer"

    returned = _event(runtime, "back")
    assert returned["state"] == "navigated"
    assert returned["view"]["menuId"] == "genres"
    assert returned["view"]["filters"]["platformId"] == "nes-famicom"
    assert returned["view"]["scrollPosition"] == 84
    assert returned["view"]["focusId"] == "card:focused"

    # A second origin resolves the same games menu without cloning its identity.
    runtime.navigator.navigate("years")
    runtime.navigator.update_context(filters={})
    selected_year = _event(runtime, "select", record_id="emulation:celeste")
    assert selected_year["state"] == "navigated"
    assert selected_year["connectionId"] == "years-to-games"
    assert selected_year["view"]["menuId"] == "games"
    assert len([menu for menu in runtime.document.menus if menu["id"] == "games"]) == 1


def test_facets_are_typed_unknowns_and_stale_events_cannot_rewrite_the_route() -> None:
    runtime = _runtime()
    before = runtime.current()
    request = {
        "requestId": "facet-platform",
        "event": "facet",
        "menuId": "platforms",
        "generation": before["generation"],
        "fieldId": "gameCount",
        "value": "2",
    }
    rejected = runtime.handle(request)
    assert rejected["state"] == "invalid-filter"

    facet = {
        **request,
        "requestId": "facet-platform-valid",
        "fieldId": "id",
        "value": "nes-famicom",
    }
    assert runtime.handle(facet)["state"] == "invalid-filter"

    moved = _event(runtime, "select", record_id="nes-famicom")
    stale = runtime.handle({**request, "requestId": "old", "generation": before["generation"]})
    assert moved["view"]["menuId"] == "genres"
    assert stale["state"] == "stale-response"
    assert runtime.current()["menuId"] == "genres"

    runtime.navigator.navigate("games")
    games = runtime.current()
    changed = runtime.handle(
        {
            "requestId": "facet-year",
            "event": "facet",
            "menuId": "games",
            "generation": games["generation"],
            "fieldId": "year",
            "value": 2018,
        }
    )
    assert changed["state"] == "filtered"
    assert [row["gameId"] for row in changed["view"]["items"]] == ["celeste"]


def test_filter_values_use_public_projection_and_never_publish_local_paths() -> None:
    row = project_game_row(
        {
            "id": "celeste",
            "title": "Celeste",
            "platformId": "nes-famicom",
            "releaseDate": "2018-09-06",
            "genres": ["Platformer"],
            "developer": "Maddy Makes Games",
            "path": "/home/operator/private.rom",
            "saves": [{"path": "/home/operator/save.srm"}],
        },
        source="emulation",
    )
    assert row is not None
    assert row["year"] == 2018
    assert row["genre"] == "Platformer"
    assert row["developer"] == "Maddy Makes Games"
    assert "path" not in row
    assert "saves" not in row


def test_active_pointer_reopens_the_same_persisted_journey(tmp_path: Path) -> None:
    store = JourneyStore(tmp_path / "journeys")
    document = _journey()
    store.root.mkdir()
    store.save(document)
    assert store.active_id() is None
    assert store.set_active(document) is None
    assert store.active_id() == document.id
    assert store.load(store.active_id() or "").serialize() == document.serialize()


def test_runtime_projects_raw_rows_before_they_can_reach_launcher_or_cinema() -> None:
    fields = journey_public_field_types()
    fields.update(
        {
            "rom_path": "string",
            "privatePath": "string",
            "authToken": "string",
            "launchArguments": "string[]",
        }
    )
    runtime = JourneyRuntime(
        _journey(),
        read_models={
            "library.games": [
                {
                    "id": "emulation:celeste",
                    "gameId": "celeste",
                    "title": "Celeste",
                    "name": "Celeste",
                    "source": "emulation",
                    "platformId": "nes-famicom",
                    "year": 2018,
                    "genre": "Platformer",
                    "rom_path": "/home/operator/roms/celeste.rom",
                    "privatePath": "/home/operator/private",
                    "authToken": "never-publish",
                    "launchArguments": ["/home/operator/private --password=secret"],
                    "unpublished": "never-publish-this-either",
                }
            ],
            "library.platforms": [],
        },
        published_read_models={
            "library.games": fields,
            "library.platforms": {
                "id": "string",
                "name": "string",
                "shortName": "string",
                "state": "string",
                "gameCount": "integer",
            },
        },
        launchable_game_ids=("celeste",),
    )

    runtime.navigator.navigate("games")
    view = runtime.current()

    assert view["items"] == [
        {
            "id": "emulation:celeste",
            "gameId": "celeste",
            "title": "Celeste",
            "name": "Celeste",
            "source": "emulation",
            "platformId": "nes-famicom",
            "year": 2018,
            "genre": "Platformer",
        }
    ]
    assert not any("path" in field.casefold() for field in runtime._published["library.games"])
    assert "authToken" not in runtime._published["library.games"]


def test_stage_bezel_distinguishes_inheritance_missing_incompatible_and_available() -> None:
    runtime = _runtime()
    assert runtime.stage_bezel("bezel")["state"] == "inherited-aura"
    resource_id = "asset://bezels/org.test.bezel@1.2.3-" + "e" * 64 + ".png"
    document = dict(runtime.document.data)
    document["sessionStages"].append({"stageId": "bezel", "bezelResource": resource_id})
    runtime.document = JourneyDocument.parse(document)

    runtime._bezel_resolver = lambda _resource: {
        "resourceId": resource_id,
        "origin": "custom-theme",
        "version": "1.2.3",
        "license": "CC-BY-4.0",
        "label": "Test bezel",
        "available": True,
        "compatible": True,
    }
    available = runtime.stage_bezel("bezel")
    assert available["state"] == "available"
    assert available["resourceId"] == resource_id
    assert available["applyMode"] == "next-launch"

    def missing(_resource: str) -> dict[str, object]:
        raise SteamZeroError("E-THEME-NOT-FOUND", detail="tema ausente")

    runtime._bezel_resolver = missing
    absent = runtime.stage_bezel("bezel")
    assert absent["state"] == "missing-reference"
    assert absent["diagnosticMessage"] == "tema ausente"

    def incompatible(_resource: str) -> dict[str, object]:
        raise SteamZeroError("E-THEME-INCOMPATIBLE", detail="digest desatualizado")

    runtime._bezel_resolver = incompatible
    invalid = runtime.stage_bezel("bezel")
    assert invalid["state"] == "incompatible"
    assert invalid["diagnosticMessage"] == "digest desatualizado"

    runtime._bezel_resolver = None
    unsupported = runtime.stage_bezel("bezel")
    assert unsupported["state"] == "unavailable"
    assert unsupported["resourceId"] == resource_id
