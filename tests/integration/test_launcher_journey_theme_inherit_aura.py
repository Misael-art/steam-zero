# SPDX-License-Identifier: GPL-3.0-or-later
"""D-07: o Launcher resolve ``inherit-aura`` por menu sem alternância claro/escuro.

Dirige o caminho REAL do Launcher (``main`` → ``resolve_journey_theme`` aninhado →
``JourneyRuntime`` → ``LauncherBridge.journey_current`` / ``journey_event``), a mesma
cadeia que produz ``GET /journey/current`` com o tema por menu. Espelha o ruling P13:
``inherit-aura`` resolve para o builtin ``org.steamzero.aura``; ``custom`` permanece
inalterado; aparência ausente continua no ``org.steamzero.default``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from steamzero.domain.experience_journey import JourneyDocument, JourneyStore
from steamzero.launcher.app import main as launcher_main

AURA_ID = "org.steamzero.aura"
DEFAULT_ID = "org.steamzero.default"
CUSTOM_ID = "org.steamzero.steamdeck"
AURA_BACKGROUND = "#0b1020"
DEFAULT_BACKGROUND = "#e7eceb"
CUSTOM_ACCENT = "#157a39"  # steamdeck sobrepõe o accent do default (#006f99)


def _document() -> JourneyDocument:
    return JourneyDocument.parse(
        {
            "schemaVersion": 2,
            "kind": "steamzero-experience-journey-v2",
            "id": "org.steamzero.launcher-d07",
            "name": "Jornada D-07",
            "entryMenuId": "platforms",
            "organization": [],
            "menus": [
                {
                    "id": "platforms",
                    "name": "Plataformas",
                    "source": {"readModelId": "library.platforms"},
                    "filters": [],
                    "sort": [],
                    "appearance": {"mode": "inherit-aura"},
                },
                {
                    "id": "genres",
                    "name": "Gêneros",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [{"fieldId": "title", "direction": "ascending"}],
                    "appearance": {"mode": "inherit-aura"},
                },
                {
                    "id": "years",
                    "name": "Anos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [{"fieldId": "year", "direction": "descending"}],
                    # Sem ``appearance``: herança implícita continua o default do host.
                },
                {
                    "id": "games",
                    "name": "Jogos",
                    "source": {"readModelId": "library.games"},
                    "filters": [],
                    "sort": [{"fieldId": "title", "direction": "ascending"}],
                    "appearance": {"mode": "custom", "themeId": CUSTOM_ID},
                },
            ],
            "connections": [
                {
                    "id": "platforms-genres",
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
                    "id": "platforms-games",
                    "from": {"kind": "menu", "id": "platforms"},
                    "event": "route",
                    "when": "user-input",
                    "action": "navigate",
                    "to": {"kind": "menu", "id": "games"},
                    "label": "Abrir jogos",
                    "bindings": [{"sourceFieldId": "id", "targetFieldId": "platformId"}],
                },
                {
                    "id": "genres-back",
                    "from": {"kind": "menu", "id": "genres"},
                    "event": "back",
                    "when": "user-input",
                    "action": "back",
                    "to": {"kind": "history"},
                    "label": "Voltar",
                },
                {
                    "id": "years-back",
                    "from": {"kind": "menu", "id": "years"},
                    "event": "back",
                    "when": "user-input",
                    "action": "back",
                    "to": {"kind": "history"},
                    "label": "Voltar",
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
            ],
            "sessionStages": [],
        }
    )


def _route(view: dict[str, Any], connection_id: str, request_id: str) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "event": "route",
        "menuId": view["menuId"],
        "generation": view["generation"],
        "recordId": "nes",
        "connectionId": connection_id,
    }


def _back(view: dict[str, Any], request_id: str) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "event": "back",
        "menuId": view["menuId"],
        "generation": view["generation"],
    }


def _run_launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Ativar a jornada e construir a ponte pelo caminho real de ``main`` (isolado)."""
    isolated_root = tmp_path / "isolated-root"
    isolated_root.mkdir(mode=0o700)
    data_root = isolated_root / "data"
    data_root.mkdir(mode=0o700)
    app_data = data_root / "steamzero"
    store = JourneyStore(app_data / "journeys")
    document = _document()
    store.save(document)
    assert store.set_active(store.load(document.id)) is None

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

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("o launcher isolado consultou uma capacidade do host")

    monkeypatch.setattr("steamzero.launcher.app._steam_catalog", forbidden)
    monkeypatch.setattr("steamzero.launcher.app._host_accessibility", forbidden)

    captured: dict[str, Any] = {}

    def capture_bridge(bridge: Any) -> int:
        captured["bridge"] = bridge
        return 0

    monkeypatch.setattr("steamzero.adapters.launcher_ui.launch_launcher_ui", capture_bridge)

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
    assert bridge is not None
    return bridge


def _background(theme: dict[str, Any]) -> str:
    return str(theme["resolved"]["color"]["background"])


def test_journey_current_inherit_aura_resolves_packaged_aura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso 1: menu ``inherit-aura`` → fundo AURA #0b1020, resolvido, id AURA."""
    bridge = _run_launcher(tmp_path, monkeypatch)
    theme = bridge.journey_current()["theme"]
    assert theme["requestedThemeId"] == AURA_ID
    assert theme["resolutionState"] == "resolved"
    assert _background(theme) == AURA_BACKGROUND


def test_two_inherit_aura_menus_share_the_same_background(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso 2 (régua D-07): dois menus ``inherit-aura`` → mesmo fundo, sem alternância."""
    bridge = _run_launcher(tmp_path, monkeypatch)
    platforms = bridge.journey_current()
    assert platforms["menuId"] == "platforms"
    genres = bridge.journey_event(_route(platforms, "platforms-genres", "route-genres"))["view"]
    assert genres["menuId"] == "genres"
    assert genres["theme"]["requestedThemeId"] == AURA_ID
    assert genres["theme"]["resolutionState"] == "resolved"
    # A troca de menu não deve alternar claro/escuro: os dois herdam o mesmo AURA.
    assert _background(genres["theme"]) == _background(platforms["theme"]) == AURA_BACKGROUND


def test_absent_appearance_still_resolves_host_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso 3: menu sem ``appearance`` → default #e7eceb (comportamento INALTERADO)."""
    bridge = _run_launcher(tmp_path, monkeypatch)
    platforms = bridge.journey_current()
    years = bridge.journey_event(_route(platforms, "platforms-years", "route-years"))["view"]
    assert years["menuId"] == "years"
    assert years["theme"]["requestedThemeId"] == DEFAULT_ID
    assert years["theme"]["resolutionState"] == "resolved"
    assert _background(years["theme"]) == DEFAULT_BACKGROUND


def test_custom_appearance_resolves_declared_theme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caso 4: menu ``custom`` → resolve o tema declarado (caminho custom preservado)."""
    bridge = _run_launcher(tmp_path, monkeypatch)
    platforms = bridge.journey_current()
    games = bridge.journey_event(_route(platforms, "platforms-games", "route-games"))["view"]
    assert games["menuId"] == "games"
    assert games["theme"]["requestedThemeId"] == CUSTOM_ID
    assert games["theme"]["resolutionState"] == "resolved"
    # Non-vacuação: o accent do steamdeck (#157a39) difere do default (#006f99) — o
    # caminho custom não caiu no fallback; o tema declarado é o que resolve.
    assert games["theme"]["resolved"]["color"]["accent"] == CUSTOM_ACCENT


def test_back_and_forth_never_flips_inherit_aura_to_light(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A volta de um menu default para um ``inherit-aura`` mantém o fundo escuro."""
    bridge = _run_launcher(tmp_path, monkeypatch)
    platforms = bridge.journey_current()
    years = bridge.journey_event(_route(platforms, "platforms-years", "route-years"))["view"]
    assert _background(years["theme"]) == DEFAULT_BACKGROUND
    back = bridge.journey_event(_back(years, "back-platforms"))["view"]
    assert back["menuId"] == "platforms"
    assert _background(back["theme"]) == AURA_BACKGROUND
