# SPDX-License-Identifier: GPL-3.0-or-later
"""ACK perdido: HTTP/QML reais, recibos e sessões controlados, sem spawn."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest

from steamzero.adapters import launcher_ui
from steamzero.adapters.launcher_receipt import LaunchAttempt, Receipt
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.launcher.navigation import HomeSection

ROOT = Path(__file__).resolve().parents[2]


def _scenario(tmp_path: Path, mode: str = "running"):
    state = {"calls": 0, "session": {"gameId": "second", "state": "unknown", "sessionId": None}}

    def launch(game_id, focus_id):
        state["calls"] += 1
        attempt = LaunchAttempt(request_id=f"server-{state['calls']}", game_id=game_id)
        if mode == "notStarted" and state["calls"] == 1:
            attempt._settle(
                Receipt(state="notStarted", error={"code": "TEST-NOT-STARTED", "detail": "fixture"})
            )
        else:
            state["session"] = {"gameId": game_id, "state": "running", "sessionId": "session-ack"}
            if mode == "delayed":
                attempt._delay()
            elif mode == "unconfirmed":
                attempt._settle(Receipt(state="unconfirmed", reason="eof"))
            elif mode != "pending":
                attempt._settle(Receipt(state="confirmed", session_id="session-ack"))
        return attempt

    bridge = LauncherBridge(
        sections=(HomeSection(id="library", title="Library", items=("first", "second")),),
        context_path=tmp_path / "context.json",
        titles={"first": "First", "second": "Second"},
        on_launch=launch,
        session_observer=lambda game: dict(state["session"]),
        readiness=lambda game: {"playable": True, "canPrepare": False},
    )
    return bridge, state


def _http(api, token, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    connection = HTTPConnection("127.0.0.1", urlsplit(api).port, timeout=5)
    try:
        connection.request(
            "GET" if body is None else "POST", path, data, {"X-SteamZero-Token": token}
        )
        response = connection.getresponse()
        if response.status >= 400:
            raise HTTPError(api + path, response.status, response.reason, response.headers, None)
        return json.load(response)
    finally:
        connection.close()


@pytest.mark.visual
@pytest.mark.parametrize("mode", ["running", "notStarted", "notAccepted", "delayedAck"])
def test_qml_recovers_lost_launch_ack_without_relaunch(tmp_path: Path, monkeypatch, mode) -> None:
    bridge, state = _scenario(tmp_path, mode)
    original_send = launcher_ui._Handler._send
    original_get = launcher_ui._Handler.do_GET
    original_post = launcher_ui._Handler.do_POST
    dropped = []
    release_ack = threading.Event()

    def send(handler, status, value):
        if handler.path == "/launch":
            if mode == "delayedAck":
                release_ack.wait(timeout=8)
            handler.close_connection = True
            return  # O serviço aceitou; só o ACK se perde.
        if handler.path.startswith("/session?") and state["calls"] and not dropped:
            dropped.append(True)
            handler.close_connection = True
            return  # Uma observação terminal também pode perder sua resposta.
        original_send(handler, status, value)

    def get(handler):
        if handler.path == "/ack-control/close" and handler._authorized():
            with bridge._session_lock:
                state["session"]["state"] = "closed"
            release_ack.set()
            original_send(handler, 200, {})
        else:
            original_get(handler)

    def post(handler):
        if mode == "notAccepted" and handler.path == "/launch":
            handler.close_connection = True
            return
        original_post(handler)

    monkeypatch.setattr(launcher_ui._Handler, "_send", send)
    monkeypatch.setattr(launcher_ui._Handler, "do_GET", get)
    monkeypatch.setattr(launcher_ui._Handler, "do_POST", post)
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    assert Path(runner).is_file(), "QML-VISUAL-ENVIRONMENT-001: Qt6 obrigatório"
    source = ROOT / "tests/qml/launcher/check_launcher_launch_ack.qml"
    harness = tmp_path / source.name
    harness.write_text(
        source.read_text().replace(
            'import "../../../src/steamzero/ui/qml/launcher"',
            f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
        )
    )
    with bridge.serving() as api:
        destination = ""
        if os.environ.get("STEAMZERO_CAPTURE_ACK") == "1":
            folder = ROOT / "build/agent-runs/r3-launch-ack"
            folder.mkdir(parents=True, exist_ok=True)
            destination = str(folder)
        (tmp_path / "ack-config.json").write_text(
            json.dumps({"api": api, "token": bridge.token, "mode": mode, "capture": destination})
        )
        try:
            completed = subprocess.run(
                [runner, "-input", str(harness)],
                capture_output=True,
                text=True,
                timeout=20,
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QML_XHR_ALLOW_FILE_READ": "1"},
            )
        finally:
            release_ack.set()
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert (
        state["calls"] == {"running": 1, "notStarted": 2, "notAccepted": 0, "delayedAck": 1}[mode]
    )


def test_concurrent_replay_has_one_effect_and_the_same_receipt(tmp_path: Path) -> None:
    bridge, state = _scenario(tmp_path)
    with bridge.serving() as api:
        body = {"gameId": "second", "focusId": "library:second", "clientRequestId": "same-client"}
        with ThreadPoolExecutor(max_workers=2) as workers:
            replies = list(
                workers.map(lambda _: _http(api, bridge.token, "/launch", body), range(2))
            )
        assert replies[0] == replies[1]
        assert replies[0]["clientRequestId"] == "same-client"
        assert state["calls"] == 1


def test_correlated_terminal_read_survives_lost_observation_and_replay(tmp_path: Path) -> None:
    bridge, state = _scenario(tmp_path, "notStarted")
    with bridge.serving() as api:
        body = {"gameId": "second", "focusId": "library:second", "clientRequestId": "client-one"}
        ack = _http(api, bridge.token, "/launch", body)
        # Outra observação pode consumir a retenção legada; o cliente ainda precisa ler.
        _http(api, bridge.token, "/session?gameId=second")
        first = _http(api, bridge.token, "/session?gameId=second&clientRequestId=client-one")
        second = _http(api, bridge.token, "/session?gameId=second&clientRequestId=client-one")
        assert first == second
        assert first["clientRequestId"] == "client-one"
        assert first["attempt"]["state"] == "notStarted"
        assert _http(api, bridge.token, "/launch", body) == ack
        assert state["calls"] == 1


def test_correlation_rejects_mismatch_and_never_adopts_external_session(tmp_path: Path) -> None:
    bridge, state = _scenario(tmp_path)
    with bridge.serving() as api:
        body = {"gameId": "second", "focusId": "library:second", "clientRequestId": "client-one"}
        _http(api, bridge.token, "/launch", body)
        wrong = _http(api, bridge.token, "/session?gameId=second&clientRequestId=other")
        assert wrong["sessionId"] is None and "attempt" not in wrong
        state["session"] = {"gameId": "second", "state": "running", "sessionId": "external"}
        observed = _http(api, bridge.token, "/session?gameId=second&clientRequestId=client-one")
        assert observed["sessionId"] is None and observed["state"] == "awaiting"
        with pytest.raises(HTTPError) as error:
            _http(
                api,
                bridge.token,
                "/launch",
                {**body, "gameId": "first", "focusId": "library:first"},
            )
        assert error.value.code == 409
        assert state["calls"] == 1


@pytest.mark.parametrize("identity", [None, "", 42, "x" * 129, "space bad", "não-ascii"])
def test_invalid_client_request_is_rejected_before_effect(tmp_path: Path, identity) -> None:
    bridge, state = _scenario(tmp_path)
    with bridge.serving() as api:
        with pytest.raises(HTTPError) as error:
            _http(
                api,
                bridge.token,
                "/launch",
                {"gameId": "second", "focusId": "library:second", "clientRequestId": identity},
            )
        assert error.value.code == 400
        assert state["calls"] == 0


@pytest.mark.parametrize("mode", ["pending", "delayed", "unconfirmed"])
def test_canonical_running_is_insufficient_without_matching_receipt(tmp_path: Path, mode) -> None:
    bridge, state = _scenario(tmp_path, mode)
    bridge.launch("second", "library:second", client_request_id="client-one")
    observed = bridge.session("second", client_request_id="client-one")
    assert observed["state"] == "awaiting" and observed["sessionId"] is None
    assert observed["attempt"]["state"] == mode
    assert state["calls"] == 1


def test_retention_is_replaced_by_next_request_and_invalid_reads_have_no_effect(
    tmp_path: Path,
) -> None:
    bridge, state = _scenario(tmp_path, "notStarted")
    with pytest.raises(ValueError):
        bridge.launch("second", "library:second", client_request_id="")
    assert state["calls"] == 0
    bridge.launch("second", "library:second", client_request_id="old")
    bridge.launch("second", "library:second", client_request_id="new")
    assert state["calls"] == 2
    assert bridge.session("second", client_request_id="old")["sessionId"] is None
    assert bridge.session("first", client_request_id="new")["sessionId"] is None
    with bridge.serving() as api:
        with pytest.raises(HTTPError) as error:
            _http(api, bridge.token, "/session?gameId=second&clientRequestId=bad%20id")
        assert error.value.code == 400
    state["session"]["state"] = "closed"
    bridge.session("second")
    bridge.launch("second", "library:second")
    assert bridge.session("second", client_request_id="new")["sessionId"] is None
