# SPDX-License-Identifier: GPL-3.0-or-later
"""Facetas da Jornada completa pela LauncherBridge real e pela UI QML."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from steamzero.adapters.journey_public import journey_public_field_types
from steamzero.adapters.journey_studio import JourneyStudioService
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.domain.experience_journey import JourneyDocument
from steamzero.launcher.journey_runtime import JourneyRuntime
from steamzero.launcher.navigation import HomeSection

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "build" / "journey-complete-facets-e2e.json"
HARNESS = ROOT / "tests" / "qml" / "check_journey_complete_facets.qml"


def _qt6_runner() -> Path | None:
    for candidate in (
        Path("/usr/lib/qt6/bin/qmltestrunner"),
        Path("/usr/lib64/qt6/bin/qmltestrunner"),
    ):
        if candidate.is_file():
            return candidate
    found = shutil.which("qmltestrunner6") or shutil.which("qmltestrunner")
    return Path(found) if found else None


RUNNER = _qt6_runner()


def _library() -> dict[str, list[dict[str, Any]]]:
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


def _document(tmp_path: Path) -> dict[str, Any]:
    service = JourneyStudioService(tmp_path / "journeys")
    return service.create(name="Sala completa", template="complete")["document"]


def _runtime(
    document: dict[str, Any],
    *,
    games: list[dict[str, Any]] | None,
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


def _bridge(tmp_path: Path, runtime: JourneyRuntime) -> LauncherBridge:
    return LauncherBridge(
        sections=(HomeSection(id="library", title="Biblioteca", items=("alpha",)),),
        context_path=tmp_path / "return.json",
        on_launch=lambda _game, _focus: None,
        titles={"alpha": "Alpha"},
        journey_runtime=runtime,
    )


def _request(
    base: str,
    token: str,
    path: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"X-SteamZero-Token": token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(  # noqa: S310
        base + path,
        data=data,
        headers=headers,
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        body = json.loads(response.read().decode())
    if not isinstance(body, dict):
        raise AssertionError("a bridge não devolveu um objeto")
    return body


def _event(view: Mapping[str, Any], event: str, request_id: str, **extra: Any) -> dict[str, Any]:
    request: dict[str, Any] = {
        "requestId": request_id,
        "event": event,
        "menuId": view["menuId"],
        "generation": view["generation"],
        "scrollPosition": extra.pop("scrollPosition", 0),
        "focusId": extra.pop("focusId", "card:focused"),
    }
    request.update(extra)
    return request


def _arm_delayed_select(bridge: LauncherBridge) -> None:
    """Atrasa o primeiro select para a UI conseguir renovar o pedido antes da resposta."""
    original = bridge.journey_event
    state = {"armed": True}
    lock = threading.Lock()

    def wrapped(payload: Mapping[str, Any]) -> dict[str, Any]:
        delay = False
        with lock:
            if state["armed"] and payload.get("event") == "select":
                state["armed"] = False
                delay = True
        if delay:
            time.sleep(1.2)
        return original(payload)

    bridge.journey_event = wrapped  # type: ignore[method-assign]


def test_complete_facets_cross_the_real_launcher_bridge(tmp_path: Path) -> None:
    """Três NES não repetem gênero nem ano; o retorno e a resposta tardia permanecem."""
    runtime = _runtime(_document(tmp_path), games=_library()["library.games"])
    bridge = _bridge(tmp_path, runtime)
    with bridge.serving() as base:
        platforms = _request(base, bridge.token, "/journey/current")
        genres = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(
                platforms,
                "select",
                "open-nes",
                recordId="nes-famicom",
                scrollPosition=24,
                focusId="platform:nes",
            ),
        )["view"]
        assert [(item["title"], item["count"]) for item in genres["items"]] == [
            ("Action", 2),
            ("RPG", 1),
            ("Desconhecido", 1),
        ]
        assert genres["filters"] == {"platformId": "nes-famicom"}
        action = genres["items"][0]
        games = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(
                genres,
                "select",
                "open-action",
                recordId=action["id"],
                scrollPosition=48,
                focusId="facet:action",
            ),
        )["view"]
        assert games["menuId"] == "games"
        assert games["filters"] == {"platformId": "nes-famicom", "genre": "Action"}
        assert [item["gameId"] for item in games["items"]] == ["alpha", "beta"]
        restored = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(games, "back", "back-genres"),
        )["view"]
        assert restored["menuId"] == "genres"
        assert restored["selectedItemId"] == action["id"]
        assert restored["scrollPosition"] == 48
        assert restored["focusId"] == "facet:action"
        assert restored["filters"] == {"platformId": "nes-famicom"}

        unknown = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(restored, "select", "open-unknown-genre", recordId=restored["items"][2]["id"]),
        )["view"]
        assert unknown["filters"]["genre"] is None
        assert [item["gameId"] for item in unknown["items"]] == ["delta"]

        platforms_again = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(
                _request(
                    base,
                    bridge.token,
                    "/journey/event",
                    _event(unknown, "back", "back-genres-again"),
                )["view"],
                "back",
                "back-platforms",
            ),
        )["view"]
        years = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(
                platforms_again,
                "route",
                "open-years",
                recordId="nes-famicom",
                connectionId="platforms-years",
            ),
        )["view"]
        assert [(item["title"], item["count"]) for item in years["items"]] == [
            ("1987", 1),
            ("1986", 2),
            ("Desconhecido", 1),
        ]
        year_games = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(years, "select", "open-1986", recordId=years["items"][1]["id"]),
        )["view"]
        assert year_games["menuId"] == "games"
        assert year_games["filters"] == {"platformId": "nes-famicom", "year": 1986}
        assert [item["gameId"] for item in year_games["items"]] == ["alpha", "beta"]
        stale = _request(
            base,
            bridge.token,
            "/journey/event",
            _event(years, "select", "late-year", recordId=years["items"][1]["id"]),
        )
        assert stale["state"] == "stale-response"
        assert stale["diagnosticCode"] == "JOURNEY-RESPONSE-STALE"
        assert "view" not in stale
        current = _request(base, bridge.token, "/journey/current")
        assert current["menuId"] == "games"
        assert current["filters"]["year"] == 1986


def test_complete_facets_bridge_distinguishes_empty_and_unavailable_sources(
    tmp_path: Path,
) -> None:
    document = _document(tmp_path)
    empty = _bridge(tmp_path / "empty", _runtime(document, games=[]))
    with empty.serving() as base:
        genres = _request(
            base,
            empty.token,
            "/journey/event",
            _event(
                _request(base, empty.token, "/journey/current"),
                "select",
                "empty-nes",
                recordId="nes-famicom",
            ),
        )["view"]
    assert genres["items"] == []
    assert genres["resultState"] == "zero-results"
    assert genres["sourceState"] == "available"

    offline = _bridge(
        tmp_path / "offline",
        _runtime(
            document,
            games=None,
            source_states={"library.platforms": "available", "library.games": "unavailable"},
        ),
    )
    with offline.serving() as base:
        blocked = _request(
            base,
            offline.token,
            "/journey/event",
            _event(
                _request(base, offline.token, "/journey/current"),
                "select",
                "offline-nes",
                recordId="nes-famicom",
            ),
        )["view"]
    assert blocked["items"] == []
    assert blocked["sourceState"] == "unavailable"
    assert blocked["resultState"] == "source-unavailable"


def _run_qml(tmp_path: Path, bridge: LauncherBridge, mode: str) -> None:
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    assert not CONFIG.exists(), "há um arquivo efêmero anterior que precisa ser inspecionado"
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(
        json.dumps({"apiUrl": "", "apiToken": bridge.token, "mode": mode}),
        encoding="utf-8",
    )
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
    try:
        with bridge.serving() as base:
            CONFIG.write_text(
                json.dumps({"apiUrl": base, "apiToken": bridge.token, "mode": mode}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(RUNNER), "-input", str(HARNESS)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
    finally:
        CONFIG.unlink(missing_ok=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, f"UI QML de facetas ({mode}) reprovou:\n{output[-7000:]}"
    assert "FAIL!" not in output, f"assertion QML reprovou:\n{output[-7000:]}"


@pytest.mark.visual
def test_complete_facets_qml_selects_and_returns_through_the_real_bridge(tmp_path: Path) -> None:
    bridge = _bridge(
        tmp_path,
        _runtime(_document(tmp_path), games=_library()["library.games"]),
    )
    _run_qml(tmp_path, bridge, "navigate")


@pytest.mark.visual
def test_complete_facets_qml_ignores_a_late_http_response(tmp_path: Path) -> None:
    bridge = _bridge(
        tmp_path,
        _runtime(_document(tmp_path), games=_library()["library.games"]),
    )
    _arm_delayed_select(bridge)
    _run_qml(tmp_path, bridge, "late")


@pytest.mark.visual
def test_complete_facets_qml_shows_empty_and_unavailable_sources(tmp_path: Path) -> None:
    document = _document(tmp_path)
    empty = _bridge(tmp_path / "empty", _runtime(document, games=[]))
    _run_qml(tmp_path / "empty-ui", empty, "empty")
    offline = _bridge(
        tmp_path / "offline",
        _runtime(
            document,
            games=None,
            source_states={"library.platforms": "available", "library.games": "unavailable"},
        ),
    )
    _run_qml(tmp_path / "offline-ui", offline, "unavailable")
