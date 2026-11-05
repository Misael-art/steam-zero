# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI/RPC and loopback UI share the exact canonical recovery operation."""

from __future__ import annotations

import json
import subprocess
from http.client import HTTPConnection
from urllib.parse import urlsplit

import pytest

from steamzero.adapters import emulation, launcher_process
from steamzero.adapters.launcher_receipt import LaunchAttempt, Receipt
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.cli import main as cli
from steamzero.launcher.app import LaunchRouter
from steamzero.launcher.navigation import HomeSection
from steamzero.service.methods import METHODS, InvalidParams

IDENTITY = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER = "01ARZ3NDEKTSV4RRFFQ69G5FAW"


@pytest.mark.parametrize(
    "status,exit_code",
    [("recovered", cli.EXIT_OK), ("clean", cli.EXIT_OK), ("blocked", cli.EXIT_BLOCKED)],
)
def test_cli_exact_session_uses_canonical_controller_and_always_closes(
    monkeypatch, capsys, status, exit_code
):
    calls = []

    class Controller:
        def recover_game_session(self, game, identity):
            calls.append((game, identity))
            return {
                "gameId": game,
                "sessionId": identity,
                "status": status,
                "state": "failed" if status != "blocked" else "unknown",
            }

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(emulation, "EmulationController", Controller)
    monkeypatch.setattr(
        cli,
        "_session_launcher",
        lambda: pytest.fail("library ID must not enter the Steam AppID path"),
    )
    assert (
        cli.main(
            ["session", "recover", "--game-id", "library-game", "--session-id", IDENTITY, "--json"]
        )
        == exit_code
    )
    result = json.loads(capsys.readouterr().out)
    assert result["data"]["sessionId"] == IDENTITY
    assert calls == [("library-game", IDENTITY), "closed"]


@pytest.mark.parametrize(
    "flags",
    [["--session-id"], ["--session-id", "bad"], ["--session-id", IDENTITY, "--session-id", OTHER]],
)
def test_invalid_cli_identity_has_no_controller_effect(monkeypatch, capsys, flags):
    monkeypatch.setattr(
        emulation,
        "EmulationController",
        lambda: pytest.fail("invalid input constructed controller"),
    )
    assert cli.main(["session", "recover", "--game-id", "game", *flags, "--json"]) != 0
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "E-API-SCHEMA"


def test_rpc_optional_identity_keeps_legacy_translation_and_rejects_unknown_fields():
    method = METHODS["session.recover"]
    assert method.mutation is True
    assert method.params_to_args({"gameId": "10"}) == ["--game-id", "10"]
    params = {"gameId": "library-game", "sessionId": IDENTITY}
    args = method.params_to_args(params)
    assert args == ["--game-id", "library-game", "--session-id", IDENTITY]
    assert method.args_to_params(args, "correlation") == {**params, "correlationId": "correlation"}
    with pytest.raises(InvalidParams):
        method.params_to_args({**params, "pid": 123})


def test_launcher_uses_the_same_fixed_cli_route_and_preserves_blocked_data(tmp_path, monkeypatch):
    calls = []

    def run(argv, **options):
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            cli.EXIT_BLOCKED,
            stdout=json.dumps({"data": {"status": "blocked", "state": "unknown"}}),
        )

    monkeypatch.setattr(launcher_process.subprocess, "run", run)
    router = LaunchRouter(
        on_spawn=lambda _: pytest.fail("recovery spawned a game"),
        context_path=tmp_path / "context.json",
        executable=lambda: "/controlled/steamzero",
    )
    assert router.recover_session("game", IDENTITY)["status"] == "blocked"
    assert calls == [
        [
            "/controlled/steamzero",
            "session",
            "recover",
            "--game-id",
            "game",
            "--session-id",
            IDENTITY,
            "--json",
        ]
    ]
    assert (
        launcher_process.query_product("fixture", "prepare", "game", timeout=1, session_id=IDENTITY)
        is None
    )
    assert (
        launcher_process.query_product("fixture", "recover", "game", timeout=1, session_id="bad")
        is None
    )
    assert len(calls) == 1


def _bridge(tmp_path):
    state = {"state": "running", "recovery": {"available": False}}
    calls = []
    attempt = LaunchAttempt(request_id=IDENTITY, game_id="game")
    attempt._settle(Receipt(state="confirmed", session_id=IDENTITY, game_id="game"))

    def observe(game):
        return {"gameId": game, "sessionId": IDENTITY, **state}

    def recover(game, identity):
        calls.append((game, identity))
        state.update(state="failed")
        return {"gameId": game, "sessionId": identity, "status": "recovered", "state": "failed"}

    bridge = LauncherBridge(
        sections=(HomeSection(id="library", title="Library", items=("game",)),),
        context_path=tmp_path / "context.json",
        on_launch=lambda *_: attempt,
        session_observer=observe,
        recover_session=recover,
    )
    # The old history is not the attempt: reserve without a prior canonical row.
    bridge._session_observer = lambda game: {"gameId": game, "sessionId": None, "state": "unknown"}
    bridge.launch("game", "library:game")
    bridge._session_observer = observe
    return bridge, state, calls


def test_bridge_does_not_recover_a_live_or_unrelated_session(tmp_path):
    bridge, state, calls = _bridge(tmp_path)
    assert bridge.recover_session("game", IDENTITY)["accepted"] is False
    state.update(state="unknown", recovery={"available": True})
    assert bridge.recover_session("game", OTHER)["accepted"] is False
    assert bridge.recover_session("other", IDENTITY)["accepted"] is False
    assert calls == []
    assert bridge.recover_session("game", IDENTITY)["accepted"] is True
    assert calls == [("game", IDENTITY)]
    assert bridge.recover_session("game", IDENTITY)["accepted"] is True
    assert len(calls) == 1


def test_bridge_rejects_wrong_callback_identity(tmp_path):
    bridge, state, _calls = _bridge(tmp_path)
    state.update(state="unknown", recovery={"available": True})
    bridge._recover_session = lambda *_: {
        "gameId": "game",
        "sessionId": OTHER,
        "status": "recovered",
        "state": "failed",
    }
    assert bridge.recover_session("game", IDENTITY)["accepted"] is False


def test_http_recovery_requires_token_closed_fields_and_correlated_identity(tmp_path):
    bridge, state, calls = _bridge(tmp_path)
    state.update(state="unknown", recovery={"available": True})
    with bridge.serving() as api:

        def post(payload, token):
            connection = HTTPConnection("127.0.0.1", urlsplit(api).port, timeout=3)
            try:
                connection.request(
                    "POST", "/session/recover", json.dumps(payload), {"X-SteamZero-Token": token}
                )
                response = connection.getresponse()
                return response.status, json.load(response)
            finally:
                connection.close()

        body = {"gameId": "game", "sessionId": IDENTITY}
        assert post(body, "wrong")[0] == 403
        assert post({**body, "pid": 123}, bridge.token)[0] == 400
        assert post({"gameId": "", "sessionId": IDENTITY}, bridge.token)[0] == 400
        assert post({**body, "sessionId": OTHER}, bridge.token)[0] == 409
        assert calls == []
        assert post(body, bridge.token)[0] == 200
        bridge.session("game")  # terminal GET consumed the active-attempt reference
        assert post(body, bridge.token)[0] == 200
        assert calls == [("game", IDENTITY)]
