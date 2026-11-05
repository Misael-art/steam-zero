# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe and prepare the selected catalog game without launching it."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.launcher.app import LaunchRouter, build_sections


def _bridge(tmp_path: Path, **kwargs) -> LauncherBridge:
    kwargs.setdefault("on_launch", lambda game, focus: None)
    return LauncherBridge(
        sections=build_sections([{"id": "game", "title": "Fixture", "section": "library"}]),
        context_path=tmp_path / "return.json",
        **kwargs,
    )


def _request(base: str, token: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(  # noqa: S310 - address comes from our loopback server
        base + path,
        headers={"X-SteamZero-Token": token, "Content-Type": "application/json"},
        data=None if body is None else json.dumps(body).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_readiness_is_read_only_authenticated_and_public(tmp_path: Path) -> None:
    prepared, launched = [], []
    bridge = _bridge(
        tmp_path,
        readiness=lambda game: {
            "playable": False,
            "canPrepare": True,
            "code": "E-CONTENT-INCOMPLETE",
            "reason": f"Extraia o arquivo em {Path.home()}/private/roms.",
            "path": "/private/library.db",
        },
        prepare=lambda game: prepared.append(game),
        on_launch=lambda game, focus: launched.append(game),
    )
    with bridge.serving() as base:
        assert _request(base, "wrong", "/readiness?gameId=game")[0] == 403
        assert _request(base, "wrong", "/prepare", {"gameId": "game"})[0] == 403
        status, result = _request(base, bridge.token, "/readiness?gameId=game")
    assert status == 200
    assert result["gameId"] == "game"
    assert result["state"] == "blocked"
    assert result["playable"] is False and result["canPrepare"] is True
    assert "Extraia" in result["reason"] and str(Path.home()) not in result["reason"]
    assert "path" not in result
    assert prepared == launched == []


@pytest.mark.parametrize("verdict", [None, {}, {"playable": "true"}, {"playable": 1}])
def test_unobserved_readiness_is_unknown_not_ready(tmp_path: Path, verdict: dict | None) -> None:
    bridge = _bridge(tmp_path, readiness=None if verdict is None else lambda game: verdict)
    with bridge.serving() as base:
        status, result = _request(base, bridge.token, "/readiness?gameId=game")
    assert status == 200
    assert result["state"] == "unknown"
    assert result["playable"] is None and result["canPrepare"] is False


def test_readiness_error_is_recoverable_without_leaking_exception(tmp_path: Path) -> None:
    calls = []

    def readiness(game):
        calls.append(game)
        if len(calls) == 1:
            raise OSError("/private/path token=fixture-secret")
        return {"playable": True}

    bridge = _bridge(tmp_path, readiness=readiness)
    with bridge.serving() as base:
        _, failed = _request(base, bridge.token, "/readiness?gameId=game")
        _, recovered = _request(base, bridge.token, "/readiness?gameId=game")
    assert failed["state"] == "unknown" and "fixture-secret" not in json.dumps(failed)
    assert recovered["state"] == "ready" and recovered["playable"] is True


@pytest.mark.parametrize("path,status", [("/readiness", 400), ("/readiness?gameId=outside", 404)])
def test_readiness_requires_a_catalog_identity(tmp_path: Path, path: str, status: int) -> None:
    queried = []
    bridge = _bridge(tmp_path, readiness=lambda game: queried.append(game))
    with bridge.serving() as base:
        assert _request(base, bridge.token, path)[0] == status
        assert _request(base, bridge.token, "/prepare", {"gameId": "outside"})[0] == 404
        assert _request(base, bridge.token, "/prepare", {"gameId": 3})[0] == 400
    assert queried == []


def test_explicit_preparation_reports_activity_deduplicates_and_never_launches(
    tmp_path: Path,
) -> None:
    release = threading.Event()
    started = threading.Event()
    ready = threading.Event()
    prepared, launched = [], []

    def prepare(game):
        prepared.append(game)
        started.set()
        assert release.wait(5)
        ready.set()
        return {"prepared": True}

    bridge = _bridge(
        tmp_path,
        readiness=lambda game: {"playable": ready.is_set(), "canPrepare": not ready.is_set()},
        prepare=prepare,
        on_launch=lambda game, focus: launched.append(game),
    )
    try:
        with bridge.serving() as base:
            first, result = _request(base, bridge.token, "/prepare", {"gameId": "game"})
            assert started.wait(2)
            duplicate, result2 = _request(base, bridge.token, "/prepare", {"gameId": "game"})
            _, observed = _request(base, bridge.token, "/readiness?gameId=game")
            assert first == duplicate == 202
            assert result["state"] == result2["state"] == observed["state"] == "preparing"
            assert observed["preparing"] is True and observed["canPrepare"] is False
            assert "progress" not in observed
            release.set()
            bridge._preparing["game"].join(5)
            _, final = _request(base, bridge.token, "/readiness?gameId=game")
            assert final["state"] == "ready" and final["preparing"] is False
    finally:
        release.set()
    assert prepared == ["game"] and launched == []


@pytest.mark.parametrize("exceptional", [False, True])
def test_preparation_failure_remains_visible_and_explicit_retry_recovers(
    tmp_path: Path, exceptional: bool
) -> None:
    ready = threading.Event()
    attempts = []

    def prepare(game):
        attempts.append(game)
        if len(attempts) == 1:
            if exceptional:
                raise OSError("/private/path token=fixture-secret")
            return {"prepared": False, "reason": "Arquivo de fixture corrompido"}
        ready.set()
        return {"prepared": True}

    bridge = _bridge(
        tmp_path,
        readiness=lambda game: {"playable": ready.is_set(), "canPrepare": not ready.is_set()},
        prepare=prepare,
    )
    with bridge.serving() as base:
        _request(base, bridge.token, "/prepare", {"gameId": "game"})
        bridge._preparing["game"].join(5)
        for _ in range(2):
            _, result = _request(base, bridge.token, "/readiness?gameId=game")
            assert result["state"] == "failed"
            assert ("falhou" if exceptional else "corrompido") in result["reason"]
            assert "fixture-secret" not in json.dumps(result)
            assert result["canPrepare"] is True
        _request(base, bridge.token, "/prepare", {"gameId": "game"})
        bridge._preparing["game"].join(5)
        _, result = _request(base, bridge.token, "/readiness?gameId=game")
    assert result["state"] == "ready" and attempts == ["game", "game"]


@pytest.mark.parametrize("repaired", [True, False])
def test_retry_revalidates_external_changes_before_starting_work(
    tmp_path: Path, repaired: bool
) -> None:
    state = {"ready": False, "canPrepare": True}
    attempts = []

    def prepare(game):
        attempts.append(game)
        return {"prepared": False, "reason": "Fixture: falha inicial"}

    bridge = _bridge(
        tmp_path,
        readiness=lambda game: {"playable": state["ready"], "canPrepare": state["canPrepare"]},
        prepare=prepare,
    )
    with bridge.serving() as base:
        _request(base, bridge.token, "/prepare", {"gameId": "game"})
        bridge._preparing["game"].join(5)
        state.update(ready=repaired, canPrepare=False)
        status, result = _request(base, bridge.token, "/prepare", {"gameId": "game"})
    assert attempts == ["game"]
    assert status == (200 if repaired else 409)
    assert result["state"] == ("ready" if repaired else "blocked")


def test_prepare_without_a_supported_port_is_not_started(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, readiness=lambda game: {"playable": False, "canPrepare": True})
    with bridge.serving() as base:
        status, result = _request(base, bridge.token, "/prepare", {"gameId": "game"})
    assert status == 409 and result["canPrepare"] is False
    assert bridge._preparing == {}


def test_router_observation_does_not_confuse_fail_open_with_verified_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def query(executable, operation, game, *, timeout):
        calls.append((operation, game, timeout))
        return None

    monkeypatch.setattr("steamzero.launcher.app.query_product", query)
    router = LaunchRouter(
        on_spawn=lambda argv: 1,
        context_path=tmp_path / "return.json",
        executable=lambda: "fixture-cli",
        kinds={"steam-game": "steam"},
    )
    assert router.readiness("game") == {"playable": True}
    assert router.readiness_observation("game")["playable"] is None
    assert router.readiness_observation("steam-game")["playable"] is None
    assert calls == [("readiness", "game", 20), ("readiness", "game", 2)]
