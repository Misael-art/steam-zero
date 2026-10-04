# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved Studio journey through the authenticated Launcher bridge and Cinema."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from tests.integration.test_ui_shell_retrofe_import_late_response import RUNNER

from steamzero.adapters.journey_public import journey_public_field_types, project_game_row
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.domain import theme_assets, theme_scene
from steamzero.domain.experience_journey import JourneyDocument, JourneyStore
from steamzero.launcher.app import (
    _render_journey_xml_scene,
    build_sections,
    build_titles,
)
from steamzero.launcher.app import (
    main as launcher_main,
)
from steamzero.launcher.journey_runtime import JourneyRuntime

ROOT = Path(__file__).resolve().parents[2]
QML_HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_journey.qml"
XML_THEME_ID = "org.steamzero.fixture.xml-journey"


class _JourneySessionRecord:
    def __init__(self) -> None:
        self.id = "synthetic-session-celeste"
        self.game_id = "celeste"
        self.state = "running"


class _JourneySessionControl:
    def __init__(self) -> None:
        self.current = _JourneySessionRecord()
        self.saved_slots: set[int] = {4}
        self.saved: list[int] = []
        self.loaded: list[int] = []

    def suspend(self) -> _JourneySessionRecord:
        self.current.state = "suspended"
        return self.current

    def resume(self) -> _JourneySessionRecord:
        self.current.state = "running"
        return self.current

    def list_save_states(self) -> list[dict[str, Any]]:
        return [
            {
                "slot": slot,
                "timestamp": "2026-10-04T12:00:00Z",
                "compatibility": "native",
                "available": True,
            }
            for slot in sorted(self.saved_slots)
        ]

    def save_state(self, slot: int) -> _JourneySessionRecord:
        self.saved.append(slot)
        self.saved_slots.add(slot)
        return self.current

    def load_state(self, slot: int) -> _JourneySessionRecord:
        self.loaded.append(slot)
        return self.current

    def request_exit(self, *, confirmed: bool) -> _JourneySessionRecord:
        if not confirmed:
            raise AssertionError("synthetic session exit requires explicit confirmation")
        self.current.state = "closed"
        return self.current


def _document() -> JourneyDocument:
    return JourneyDocument.parse(
        {
            "schemaVersion": 2,
            "kind": "steamzero-experience-journey-v2",
            "id": "org.steamzero.launcher-e2e",
            "name": "Jornada Launcher E2E",
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
                    "sort": [{"fieldId": "title", "direction": "ascending"}],
                },
                {
                    "id": "years",
                    "name": "Anos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [{"fieldId": "year", "direction": "descending"}],
                },
                {
                    "id": "games",
                    "name": "Jogos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [{"fieldId": "title", "direction": "ascending"}],
                    "appearance": {"mode": "custom", "themeId": XML_THEME_ID},
                },
            ],
            "connections": [
                {
                    "id": "platforms-genres",
                    "from": {"kind": "menu", "id": "platforms"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "genres"},
                    "label": "Explorar por gênero",
                    "bindings": [{"sourceFieldId": "id", "targetFieldId": "platformId"}],
                },
                {
                    "id": "platforms-route-genres",
                    "from": {"kind": "menu", "id": "platforms"},
                    "event": "route",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "genres"},
                    "label": "Explorar por gênero",
                    "bindings": [{"sourceFieldId": "id", "targetFieldId": "platformId"}],
                },
                {
                    "id": "platforms-years",
                    "from": {"kind": "menu", "id": "platforms"},
                    "event": "route",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "years"},
                    "label": "Explorar por ano",
                    "bindings": [{"sourceFieldId": "id", "targetFieldId": "platformId"}],
                },
                {
                    "id": "genres-games",
                    "from": {"kind": "menu", "id": "genres"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "games"},
                    "label": "Abrir jogos por gênero",
                    "bindings": [{"sourceFieldId": "genre", "targetFieldId": "genre"}],
                },
                {
                    "id": "years-games",
                    "from": {"kind": "menu", "id": "years"},
                    "event": "select",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "games"},
                    "label": "Abrir jogos por ano",
                    "bindings": [{"sourceFieldId": "year", "targetFieldId": "year"}],
                },
                {
                    "id": "genres-back",
                    "from": {"kind": "menu", "id": "genres"},
                    "event": "back",
                    "when": "user-input",
                    "action": "back",
                    "to": {"kind": "history"},
                    "label": "Voltar às plataformas",
                },
                {
                    "id": "years-back",
                    "from": {"kind": "menu", "id": "years"},
                    "event": "back",
                    "when": "user-input",
                    "action": "back",
                    "to": {"kind": "history"},
                    "label": "Voltar às plataformas",
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
                {
                    "id": "games-pause",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "pause",
                    "when": "user-input",
                    "action": "pause",
                    "to": {"kind": "stage", "id": "pause"},
                    "label": "Pausar",
                },
                {
                    "id": "games-resume",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "resume",
                    "when": "user-input",
                    "action": "resume",
                    "to": {"kind": "stage", "id": "pause"},
                    "label": "Retomar",
                },
                {
                    "id": "games-saves",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "open-saves",
                    "when": "user-input",
                    "action": "open-saves",
                    "to": {"kind": "stage", "id": "saves"},
                    "label": "Abrir saves",
                },
                {
                    "id": "games-save",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "save",
                    "when": "user-input",
                    "action": "save",
                    "to": {"kind": "stage", "id": "saves"},
                    "label": "Salvar",
                },
                {
                    "id": "games-load",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "load",
                    "when": "user-input",
                    "action": "load",
                    "to": {"kind": "stage", "id": "saves"},
                    "label": "Carregar",
                },
                {
                    "id": "games-exit",
                    "from": {"kind": "menu", "id": "games"},
                    "event": "exit",
                    "when": "user-input",
                    "action": "exit",
                    "to": {"kind": "stage", "id": "exitFade"},
                    "label": "Sair do jogo",
                },
            ],
            "sessionStages": [
                {"stageId": "entryFade", "appearance": {"mode": "inherit-aura"}},
                {"stageId": "exitFade", "appearance": {"mode": "inherit-aura"}},
                {
                    "stageId": "pause",
                    "appearance": {"mode": "custom", "themeId": XML_THEME_ID},
                },
                {
                    "stageId": "saves",
                    "appearance": {"mode": "custom", "themeId": XML_THEME_ID},
                },
            ],
        }
    )


def _install_xml_theme(root: Path, blob_root: Path) -> theme_assets.ThemeAssetStore:
    store = theme_assets.ThemeAssetStore(blob_root)
    files = {
        "theme.xml": (
            "<theme><view name='system'><image name='journey-logo'>"
            "<pos>0.1 0.1</pos><size>0.25 0.2</size>"
            "<path>./logo.png</path></image></view></theme>"
        ),
        "logo.png": "synthetic licensed fixture",
    }
    declared_assets: dict[str, dict[str, str]] = {}
    for relative, payload in files.items():
        stored = store.put(relative, payload.encode("utf-8"))
        declared_assets[relative] = {"digest": stored.digest}
    theme_dir = root / XML_THEME_ID
    theme_dir.mkdir(parents=True)
    (theme_dir / "theme.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "steamzero-theme-v1",
                "id": XML_THEME_ID,
                "name": "Tema XML sintético da Jornada",
                "version": "1",
                "license": "CC0-1.0",
                "assets": declared_assets,
            }
        ),
        encoding="utf-8",
    )
    return store


def _get_json(base: str, route: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(base + route, headers={"X-SteamZero-Token": token})  # noqa: S310
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read())


def _post_json(base: str, route: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - helper targets the test's loopback bridge.
        base + route,
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        headers={"X-SteamZero-Token": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read())


def _event(view: dict[str, Any], event_id: str, request_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "event": event_id,
        "menuId": view["menuId"],
        "generation": view["generation"],
        **extra,
    }


def test_journey_xml_renderer_rejects_symlink_theme_package(tmp_path: Path) -> None:
    themes_root = tmp_path / "themes"
    themes_root.mkdir()
    outside_package = tmp_path / "outside-theme"
    outside_package.mkdir()
    (themes_root / XML_THEME_ID).symlink_to(outside_package, target_is_directory=True)

    result = _render_journey_xml_scene(XML_THEME_ID, themes_root=themes_root)

    assert result == {
        "state": "failed",
        "scene": None,
        "diagnostic": "O pacote da cena XML não pode ser um link simbólico.",
    }


def test_launcher_entrypoint_loads_active_journey_and_compiles_xml_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path / "home"
    isolated_root = tmp_path / "isolated-root"
    isolated_root.mkdir(mode=0o700)
    data_root = isolated_root / "data"
    data_root.mkdir(mode=0o700)
    app_data = data_root / "steamzero"
    store = JourneyStore(app_data / "journeys")
    document_data = dict(_document().data)
    document_data["entryMenuId"] = "games"
    document = JourneyDocument.parse(document_data)
    store.save(document)
    assert store.set_active(store.load(document.id)) is None
    _install_xml_theme(app_data / "themes", app_data / "theme-assets")

    library = tmp_path / "library.json"
    library.write_text(
        json.dumps(
            {
                "games": [
                    {
                        "id": "celeste",
                        "name": "Celeste",
                        "platform": "nes",
                        "year": 2018,
                        "genre": "Platformer",
                        "developer": "Maddy Makes Games",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, Any] = {}

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("isolated launcher consulted a host capability")

    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr("steamzero.launcher.app._steam_catalog", forbidden)
    monkeypatch.setattr("steamzero.launcher.app._host_accessibility", forbidden)

    def capture_bridge(bridge: Any) -> int:
        captured["bridge"] = bridge
        return 0

    monkeypatch.setattr(
        "steamzero.adapters.launcher_ui.launch_launcher_ui",
        capture_bridge,
    )

    assert (
        launcher_main(
            [
                "--library",
                str(library),
                "--isolated-library",
                "--isolated-root",
                str(isolated_root),
            ]
        )
        == 0
    )
    bridge = captured["bridge"]
    assert bridge.journey_current()["journeyId"] == document.id
    assert bridge.journey_current()["theme"]["sceneResolutionState"] == "resolved"
    assert bridge.journey_current()["theme"]["compiledScene"]["views"][0]["id"] == "system"

    with bridge.serving() as base:
        cinema = _get_json(
            base,
            "/cinema?"
            + urllib.parse.urlencode(
                {
                    "focus": "journey:games:emulation:celeste",
                    "width": 1280,
                    "height": 800,
                }
            ),
            bridge.token,
        )
    assert cinema["theme"]["sceneResolutionState"] == "resolved"
    assert cinema["theme"]["compiledScene"]["views"][0]["id"] == "system"


def test_saved_activated_journey_drives_bridge_cinema_copy_and_xml_theme(tmp_path: Path) -> None:
    document = _document()
    original_store = JourneyStore(tmp_path / "studio-store")
    original_store.root.mkdir()
    original_store.save(document)
    bundle = original_store.export_copy(original_store.load(document.id))
    with ZipFile(BytesIO(bundle)) as archive:
        assert archive.namelist() == ["experience.json"]

    active_store = JourneyStore(tmp_path / "launcher-store")
    active_store.root.mkdir()
    copied = original_store.import_copy(
        bundle,
        copy_id="org.steamzero.launcher-e2e-copy",
        copy_name="Cópia ativa",
    )
    active_store.save(copied)
    assert active_store.set_active(active_store.load(copied.id)) is None

    theme_root = tmp_path / "themes"
    xml_store = _install_xml_theme(theme_root, tmp_path / "theme-blobs")
    rendered_xml = theme_scene.render_scene(
        XML_THEME_ID,
        themes_root=theme_root,
        store=xml_store,
        workspace=tmp_path / "scene-workspace",
    )
    assert rendered_xml["assets"]["resolved"] == 1
    assert rendered_xml["scene"]["views"][0]["elements"][0]["source"].startswith("file://")
    launcher_xml_scene = _render_journey_xml_scene(
        XML_THEME_ID, themes_root=theme_root, asset_store=xml_store
    )
    assert launcher_xml_scene["state"] == "resolved"
    assert launcher_xml_scene["scene"] == rendered_xml["scene"]

    recipe = {
        "source": "cinema.items",
        "kind": "coverFlow",
        "item": {"width": 310, "height": 440},
        "template": {
            "kind": "image",
            "id": "cover",
            "properties": {"source": {"binding": "item.coverUrl", "fallback": ""}},
        },
        "offset": {
            "scaleStep": 0.14,
            "opacityStep": 0.16,
            "minScale": 0.55,
            "minOpacity": 0.4,
            "rotationStep": 0,
            "overlap": 0.62,
        },
        "highlight": {"scale": 1.1, "opacity": 1, "outlineWidth": 4},
    }
    theme_calls: list[tuple[str, str]] = []

    def resolve_theme(menu_id: str, appearance: object) -> dict[str, Any]:
        theme_id = (
            str(appearance.get("themeId"))
            if isinstance(appearance, dict)
            else "org.steamzero.default"
        )
        theme_calls.append((menu_id, theme_id))
        theme = {
            "requestedThemeId": theme_id,
            "resolutionState": "resolved",
            "highContrast": False,
            "reducedMotion": False,
            "resolved": {
                "color": {"accent": "#cc22dd", "text": "#112233", "textMuted": "#445566"},
                "motion": {"durationNormal": 345},
                "performance": {"defaultTier": "balanced"},
            },
            "effects": {
                "contextualBackdrop": [
                    {"type": "vignette", "parameters": {"color": "#000000", "strength": 0.4}}
                ],
                "focusedCover": [],
                "peripheralCover": [],
            },
            "sceneLayouts": {"schemaVersion": 1, "layouts": {"journeyCovers": recipe}},
        }
        scene = (
            launcher_xml_scene
            if theme_id == XML_THEME_ID
            else {"state": "omitted", "scene": None, "diagnostic": ""}
        )
        theme["sceneResolutionState"] = scene["state"]
        theme["sceneDiagnostic"] = scene["diagnostic"]
        if scene["scene"] is not None:
            theme["compiledScene"] = scene["scene"]
        return theme

    records = [
        {
            "id": "celeste",
            "title": "Celeste",
            "platform": "nes",
            "year": 2018,
            "genre": "Platformer",
            "developer": "Maddy Makes Games",
            "path": "/synthetic-private/celeste.rom",
        },
        {
            "id": "cave-story",
            "title": "Cave Story",
            "platform": "nes",
            "year": 2018,
            "genre": "Platformer",
            "developer": "Studio Pixel",
        },
        {
            "id": "metroid",
            "title": "Metroid",
            "platform": "nes",
            "year": 1986,
            "genre": "Action",
            "developer": "Nintendo",
        },
        {
            "id": "mario",
            "title": "Super Mario World",
            "platform": "snes",
            "year": 1990,
            "genre": "Platformer",
            "developer": "Nintendo",
        },
    ]
    rows = [
        projected
        for record in records
        if (projected := project_game_row(record, source="emulation")) is not None
    ]
    assert all("path" not in row for row in rows)
    runtime = JourneyRuntime.from_store(
        active_store.root,
        read_models={
            "library.platforms": [
                {
                    "id": "nes",
                    "name": "Nintendo Entertainment System",
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
            "library.games": rows,
        },
        published_read_models={
            "library.platforms": {
                "id": "string",
                "name": "string",
                "shortName": "string",
                "state": "string",
                "gameCount": "integer",
            },
            "library.games": journey_public_field_types(),
        },
        source_states={"library.platforms": "available", "library.games": "available"},
        launchable_game_ids=("celeste", "metroid", "mario"),
        theme_resolver=resolve_theme,
    )
    assert runtime is not None
    assert runtime.document.id == copied.id
    assert runtime.document.data["menus"][3]["appearance"]["themeId"] == XML_THEME_ID
    home_rows = [{"id": "celeste", "title": "Celeste", "section": "library"}]
    launch_calls: list[tuple[str, str]] = []
    bridge = LauncherBridge(
        sections=build_sections(home_rows),
        titles=build_titles(home_rows),
        covers={"celeste": "asset://fixture/celeste-cover.png"},
        context_path=tmp_path / "return-context.json",
        on_launch=lambda game_id, focus_id: launch_calls.append((game_id, focus_id)),
        journey_runtime=runtime,
    )

    with bridge.serving() as base:
        view = _get_json(base, "/journey/current", bridge.token)
        assert view["journeyId"] == copied.id
        assert view["menuId"] == "platforms"
        assert {row["id"] for row in view["items"]} == {"nes", "snes"}

        platforms = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                view,
                "select",
                "select-nes",
                recordId="nes",
                focusId="platform-row:nes",
                scrollPosition=62,
            ),
        )["view"]
        assert platforms["menuId"] == "genres"
        assert platforms["filters"]["platformId"] == "nes"
        assert {facet["fieldId"] for facet in platforms["facets"]} >= {"genre", "year"}

        genres = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                platforms,
                "facet",
                "filter-genre",
                fieldId="genre",
                value="Platformer",
            ),
        )["view"]
        assert genres["resultCount"] == 2
        assert {row["gameId"] for row in genres["items"]} == {"cave-story", "celeste"}
        dated = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(genres, "facet", "filter-year", fieldId="year", value=2018),
        )["view"]
        assert dated["filters"] == {"genre": "Platformer", "platformId": "nes", "year": 2018}

        games = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(dated, "select", "open-celeste", recordId="emulation:celeste"),
        )["view"]
        assert games["menuId"] == "games"
        assert games["filters"]["genre"] == "Platformer"
        assert games["filters"]["year"] == 2018
        assert {row["gameId"] for row in games["items"]} == {"cave-story", "celeste"}
        assert all("path" not in str(row).casefold() for row in games["items"])
        assert games["theme"]["requestedThemeId"] == XML_THEME_ID
        assert games["theme"]["sceneResolutionState"] == "resolved"
        assert games["theme"]["compiledScene"]["views"][0]["id"] == "system"
        assert ("games", XML_THEME_ID) in theme_calls

        cinema = _get_json(
            base,
            "/cinema?"
            + urllib.parse.urlencode(
                {
                    "focus": "journey:games:emulation:celeste",
                    "width": 1280,
                    "height": 800,
                }
            ),
            bridge.token,
        )
        assert cinema["journeyId"] == copied.id
        assert cinema["menuId"] == "games"
        assert cinema["layoutResolutionState"] == "theme"
        assert cinema["themeResolutionState"] == "resolved"
        assert cinema["theme"]["sceneResolutionState"] == "resolved"
        assert (
            cinema["theme"]["compiledScene"]["views"][0]["elements"][0]["id"]
            == "image-journey-logo"
        )
        assert cinema["layouts"]["journeyCovers"]["entries"][0]["width"] == 310
        assert cinema["selected"] == 0
        assert cinema["items"][0]["journeyRecordId"] == "emulation:celeste"
        assert cinema["items"][0]["coverUrl"] == "asset://fixture/celeste-cover.png"

        developed = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                games,
                "facet",
                "filter-developer",
                fieldId="developer",
                value="Maddy Makes Games",
            ),
        )["view"]
        assert developed["filters"]["developer"] == "Maddy Makes Games"
        assert developed["resultCount"] == 1
        assert developed["items"][0]["gameId"] == "celeste"

        play = _event(
            developed,
            "play",
            "launch-request-once",
            recordId="emulation:celeste",
            focusId="journey-item:celeste",
        )
        first_play = _post_json(base, "/journey/event", bridge.token, play)
        second_play = _post_json(base, "/journey/event", bridge.token, play)
        assert first_play == second_play
        assert first_play["state"] == "operation-request"
        assert first_play["operationRequest"] == {
            "action": "launch",
            "gameId": "celeste",
            "recordId": "emulation:celeste",
            "connectionId": "games-play",
            "sessionStage": "entryFade",
            "focusId": "library:celeste",
        }
        reused_id = _post_json(
            base,
            "/journey/event",
            bridge.token,
            {**play, "event": "pause"},
        )
        assert reused_id["diagnosticCode"] == "JOURNEY-REQUEST-ID-REUSED"
        assert launch_calls == []  # Bridge returns intent; the UI owns the launch handoff.

        current_after_play = _get_json(base, "/journey/current", bridge.token)
        pause = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                current_after_play,
                "pause",
                "pause-without-session",
                recordId="emulation:celeste",
            ),
        )
        assert pause["state"] == "operation-unavailable"
        assert pause["diagnosticCode"] == "JOURNEY-SESSION-CAPABILITY-UNKNOWN"
        saves = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                current_after_play,
                "open-saves",
                "saves-without-session",
                recordId="emulation:celeste",
            ),
        )
        assert saves["state"] == "operation-unavailable"
        assert saves["diagnosticCode"] == "JOURNEY-SAVES-CAPABILITY-UNKNOWN"
        save_without_session = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                current_after_play,
                "save",
                "save-without-session",
                recordId="emulation:celeste",
                slot=4,
            ),
        )
        assert save_without_session["state"] == "operation-unavailable"
        assert save_without_session["diagnosticCode"] == "JOURNEY-SESSION-CAPABILITY-UNKNOWN"
        load_without_session = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                current_after_play,
                "load",
                "load-without-session",
                recordId="emulation:celeste",
                slot=4,
            ),
        )
        assert load_without_session["state"] == "operation-unavailable"
        assert load_without_session["diagnosticCode"] == "JOURNEY-SESSION-CAPABILITY-UNKNOWN"

        to_genres = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(current_after_play, "back", "back-to-genres"),
        )["view"]
        assert to_genres["menuId"] == "genres"
        assert to_genres["filters"]["year"] == 2018
        to_platforms = _post_json(
            base, "/journey/event", bridge.token, _event(to_genres, "back", "back-to-platforms")
        )["view"]
        assert to_platforms["menuId"] == "platforms"
        assert to_platforms["selectedItemId"] == "nes"
        assert to_platforms["scrollPosition"] == 62
        assert to_platforms["focusId"] == "platform-row:nes"
        unpublished_route = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                to_platforms,
                "route",
                "unknown-route",
                recordId="nes",
                connectionId="not-published",
            ),
        )
        assert unpublished_route["state"] == "unmatched"
        assert unpublished_route["view"]["menuId"] == "platforms"
        by_year = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                to_platforms,
                "route",
                "platforms-to-years",
                recordId="nes",
                connectionId="platforms-years",
            ),
        )["view"]
        assert by_year["menuId"] == "years"
        assert by_year["filters"]["platformId"] == "nes"
        by_year = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(by_year, "facet", "choose-1986", fieldId="year", value=1986),
        )["view"]
        metroid = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(by_year, "select", "years-to-metroid", recordId="emulation:metroid"),
        )["view"]
        assert metroid["menuId"] == "games"
        assert metroid["filters"] == {"platformId": "nes", "year": 1986}
        assert [row["gameId"] for row in metroid["items"]] == ["metroid"]


def test_journey_session_cycle_dispatches_confirmed_pause_resume_and_save_states(
    tmp_path: Path,
) -> None:
    document_data = json.loads(_document().serialize())
    document_data["entryMenuId"] = "games"
    document = JourneyDocument.parse(document_data)
    store = JourneyStore(tmp_path / "journey-store")
    store.root.mkdir()
    store.save(document)
    assert store.set_active(store.load(document.id)) is None
    row = project_game_row(
        {
            "id": "celeste",
            "title": "Celeste",
            "platform": "nes",
            "year": 2018,
            "genre": "Platformer",
        },
        source="emulation",
    )
    assert row is not None
    runtime = JourneyRuntime.from_store(
        store.root,
        read_models={
            "library.platforms": [
                {"id": "nes", "name": "NES", "state": "available", "gameCount": 1}
            ],
            "library.games": [row],
        },
        published_read_models={
            "library.platforms": {
                "id": "string",
                "name": "string",
                "state": "string",
                "gameCount": "integer",
            },
            "library.games": journey_public_field_types(),
        },
        source_states={"library.platforms": "available", "library.games": "available"},
        launchable_game_ids=("celeste",),
        theme_resolver=lambda stage_id, appearance: {
            "requestedThemeId": (
                str(appearance.get("themeId"))
                if isinstance(appearance, dict) and appearance.get("mode") == "custom"
                else "org.steamzero.default"
            ),
            "resolutionState": "resolved",
            "resolved": {"color": {"accent": "#cc22dd", "text": "#112233"}},
        },
    )
    assert runtime is not None
    control = _JourneySessionControl()
    overlay = SessionOverlayAdapter(
        lambda game_id: {
            "gameId": game_id,
            "sessionId": control.current.id,
            "state": control.current.state,
        },
        lambda session_id, game_id: (
            control
            if (session_id, game_id) == (control.current.id, control.current.game_id)
            else None
        ),
    )
    library_rows = [{"id": "celeste", "title": "Celeste", "section": "library"}]
    bridge = LauncherBridge(
        sections=build_sections(library_rows),
        titles=build_titles(library_rows),
        context_path=tmp_path / "return-context.json",
        on_launch=lambda _game, _focus: None,
        session_observer=lambda game_id: {
            "gameId": game_id,
            "sessionId": control.current.id,
            "state": control.current.state,
        },
        session_overlay=overlay,
        journey_runtime=runtime,
    )
    record_id = "emulation:celeste"

    with bridge.serving() as base:
        initial = _get_json(base, "/journey/current", bridge.token)
        assert initial["sessionCapabilities"]["pause"]["available"] is False
        assert initial["sessionCapabilities"]["pause"]["reason"]
        session_overlay = _get_json(
            base,
            "/session?gameId=celeste&overlay=1&stage=gameplay",
            bridge.token,
        )
        assert session_overlay["overlay"]["journeyAppearance"]["stageId"] == "gameplay"
        assert session_overlay["overlay"]["journeyAppearance"]["appearanceState"] == "omitted"
        assert (
            session_overlay["overlay"]["journeyAppearance"]["theme"]["requestedThemeId"]
            == "org.steamzero.default"
        )

        paused = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(initial, "pause", "session-pause", recordId=record_id),
        )
        assert paused["state"] == "operation-confirmed"
        assert paused["operationResult"]["confirmed"] is True
        assert paused["operationResult"]["expectedState"] == "suspended"
        assert paused["view"]["session"]["state"] == "suspended"
        assert paused["view"]["sessionCapabilities"]["resume"]["available"] is True
        assert paused["view"]["sessionCapabilities"]["pause"]["available"] is False
        paused_overlay = _get_json(
            base,
            "/session?gameId=celeste&overlay=1&stage=pause",
            bridge.token,
        )
        assert paused_overlay["overlay"]["journeyAppearance"]["stageId"] == "pause"
        assert (
            paused_overlay["overlay"]["journeyAppearance"]["theme"]["requestedThemeId"]
            == XML_THEME_ID
        )

        resumed = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(paused["view"], "resume", "session-resume", recordId=record_id),
        )
        assert resumed["state"] == "operation-confirmed"
        assert resumed["operationResult"]["confirmed"] is True
        assert resumed["operationResult"]["expectedState"] == "running"
        assert resumed["view"]["session"]["state"] == "running"

        saves = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(resumed["view"], "open-saves", "session-open-saves", recordId=record_id),
        )
        assert saves["state"] == "operation-confirmed"
        assert saves["saveStates"]["state"] == "ready"
        assert saves["saveStates"]["entries"][0]["slot"] == 4

        save_request = _event(saves["view"], "save", "session-save-7", recordId=record_id, slot=7)
        saved = _post_json(base, "/journey/event", bridge.token, save_request)
        assert saved["state"] == "operation-confirmed"
        assert saved["operationResult"]["operation"] == "saveState"
        assert saved["operationResult"]["slot"] == 7
        assert saved["operationResult"]["state"] == "running"
        assert control.saved == [7]
        assert any(entry["slot"] == 7 for entry in saved["view"]["saveStates"]["entries"])
        assert _post_json(base, "/journey/event", bridge.token, save_request) == saved
        assert control.saved == [7]

        loaded = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(saved["view"], "load", "session-load-7", recordId=record_id, slot=7),
        )
        assert loaded["state"] == "operation-confirmed"
        assert loaded["operationResult"]["operation"] == "loadState"
        assert loaded["operationResult"]["slot"] == 7
        assert loaded["operationResult"]["state"] == "running"
        assert control.loaded == [7]

        exit_without_confirmation = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                loaded["view"],
                "exit",
                "session-exit-without-confirmation",
                recordId=record_id,
            ),
        )
        assert exit_without_confirmation["state"] == "confirmation-required"
        assert control.current.state == "running"

        exit_result = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(
                loaded["view"],
                "exit",
                "session-exit-confirmed",
                recordId=record_id,
                confirmed=True,
            ),
        )
        assert exit_result["state"] == "operation-confirmed"
        assert exit_result["operationResult"]["operation"] == "exit"
        assert exit_result["operationResult"]["confirmed"] is True
        assert exit_result["operationResult"]["state"] == "closed"
        assert exit_result["view"]["menuId"] == "games"

        invalid_slot = _post_json(
            base,
            "/journey/event",
            bridge.token,
            _event(loaded["view"], "save", "invalid-save-slot", recordId=record_id, slot=True),
        )
        assert invalid_slot["state"] == "rejected"
        assert invalid_slot["diagnosticCode"] == "JOURNEY-SAVE-SLOT-INVALID"
        assert control.saved == [7]


@pytest.mark.visual
def test_launcher_journey_qml_accepts_keyboard_facets_theme_and_stale_recovery(
    tmp_path: Path,
) -> None:
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para o controle Qt da Jornada"
    env = os.environ.copy()
    env.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QML_XHR_ALLOW_FILE_READ": "1",
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        }
    )
    for key in (
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        Path(env[key]).mkdir(mode=0o700, parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(RUNNER), "-input", str(QML_HARNESS)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, f"interação QML da Jornada reprovou:\n{output[-6000:]}"
    assert "FAIL!" not in output
    assert "LauncherJourneyKeyboardAndTheme" in output or "Totals:" in output
