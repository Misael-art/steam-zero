# SPDX-License-Identifier: GPL-3.0-or-later
"""A lost pre-spawn refusal must be recoverable from canonical evidence."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_emulation_session_lifetime import _WORKER
from test_launcher_restart import _CREATOR, _alive

from steamzero.adapters.emulation import EmulationController
from steamzero.adapters.launcher_receipt import LaunchAttempt
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.core.errors import LaunchNotStartedError, SteamZeroError
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore
from steamzero.launcher.app import LaunchRouter
from steamzero.launcher.launch import CONTEXT_OWNER, consume_context
from steamzero.launcher.navigation import HomeSection

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER = "01ARZ3NDEKTSV4RRFFQ69G5FAW"

# Only the controlled platform preflight is refused. CLI, controller and store
# remain real; stdout has no reader, just as after the originating UI dies.
_REFUSING_WORKER = _WORKER.replace(
    "with patch.object(emulation, 'EmulationController', return_value=controller):",
    """
from steamzero.core.errors import SteamZeroError
def refuse(_):
    raise SteamZeroError('E-CONTENT-UNSUPPORTED', detail='private-fixture-path-' + str(database))
controller._launch_preflight = refuse
def unexpected_spawn(_):
    (database.parent / 'unexpected-spawn').touch()
    raise AssertionError('preflight refusal must never spawn')
controller._spawn = unexpected_spawn
with patch.object(emulation, 'EmulationController', return_value=controller):
""",
)


def test_cli_refusal_survives_lost_stdout_without_spawn(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    worker = tmp_path / "refusing-cli.py"
    worker.write_text(_REFUSING_WORKER)
    with subprocess.Popen(
        [
            sys.executable,
            str(worker),
            str(database),
            "0",
            str(tmp_path / "release"),
            "json",
            REQUEST,
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        process.stdout.close()
        process.wait(timeout=10)
    assert not (tmp_path / "unexpected-spawn").exists()
    with StateStore(database) as store:
        row = store.get_game_session(REQUEST)
    assert row is not None, "pre-spawn refusal vanished with the CLI reply"
    assert row["state"] == "failed"
    assert row["pid"] is None
    assert row["failure_code"] == "E-CONTENT-UNSUPPORTED"
    assert row["started_at"] == row["finished_at"]
    assert "private-fixture-path" not in (row["metadata_json"] or "")
    observed = observe_game_session(database, "lifetime-probe", session_id=REQUEST)
    assert observed["launchAcknowledgment"] == "notStarted"
    assert observed["failureCode"] == "E-CONTENT-UNSUPPORTED"
    assert "launchAcknowledgment" not in observe_game_session(database, "lifetime-probe")


def _controller(database, failure):
    controller = EmulationController.__new__(EmulationController)
    controller._store_factory = lambda: StateStore(database)
    controller._process_waiter = lambda _: 0
    controller._prepare_launch = lambda _: None

    def preflight(_):
        raise failure

    controller._launch_preflight = preflight
    controller._spawn = lambda _: pytest.fail("refused attempt spawned")
    return controller


def _record_refusal(database):
    controller = _controller(database, SteamZeroError("E-CONTENT-UNSUPPORTED"))
    with pytest.raises(LaunchNotStartedError):
        controller.launch_game("second", launch_request_id=REQUEST)


def _bridge(tmp_path, launch):
    return LauncherBridge(
        sections=(HomeSection(id="library", title="Library", items=("first", "second")),),
        context_path=tmp_path / "context.json",
        return_context=consume_context(tmp_path / "context.json"),
        on_launch=launch,
        session_observer=lambda game: observe_game_session(tmp_path / "state.db", game),
        session_by_id=lambda game, identity: observe_game_session(
            tmp_path / "state.db", game, session_id=identity
        ),
    )


def _context(path):
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "owner": CONTEXT_OWNER,
                "launchRequestId": REQUEST,
                "gameId": "second",
                "focusId": "library:second",
            }
        )
    )


def test_refusal_survives_lost_get_and_another_bridge_until_explicit_retry(tmp_path):
    database = tmp_path / "state.db"
    _record_refusal(database)
    path = tmp_path / "context.json"
    _context(path)
    calls = []

    def spawn(argv, *, request_id, game_id):
        calls.append(request_id)
        return LaunchAttempt(request_id=request_id, game_id=game_id)

    router = LaunchRouter(
        on_spawn=lambda _: 0,
        context_path=path,
        executable=lambda: "steamzero",
        receipt_spawner=spawn,
    )
    first = _bridge(tmp_path, router.launch)
    first.session("second")  # response lost; the next process must recover it again
    second = _bridge(tmp_path, router.launch)
    for _ in range(3):
        result = second.session("second")
        assert result["attempt"]["state"] == "notStarted"
        assert result["attempt"]["requestId"] == REQUEST
        assert result["attempt"]["error"]["code"] == "E-CONTENT-UNSUPPORTED"
        assert path.exists()
        assert calls == []
    attempt = second.launch("second", "library:second", client_request_id="explicit-retry")
    assert attempt is not None and attempt.request_id != REQUEST
    assert json.loads(path.read_text())["launchRequestId"] == attempt.request_id
    assert calls == [attempt.request_id]
    assert second.session("second")["state"] == "awaiting"
    assert second.launch("second", "library:second", client_request_id="explicit-retry") is attempt
    assert len(calls) == 1
    with StateStore(database) as store:
        assert store.get_game_session(REQUEST)["state"] == "failed"


@pytest.mark.parametrize("replacement", ["foreign", "other-request", "symlink"])
def test_retry_preserves_replaced_context_without_new_effect(tmp_path, replacement):
    _record_refusal(tmp_path / "state.db")
    path = tmp_path / "context.json"
    _context(path)
    bridge = _bridge(tmp_path, lambda *_: pytest.fail("changed context launched"))
    assert bridge.session("second")["attempt"]["state"] == "notStarted"
    if replacement == "symlink":
        path.unlink()
        target = tmp_path / "other.json"
        target.write_text("foreign")
        path.symlink_to(target)
    else:
        payload = json.loads(path.read_text())
        payload["owner" if replacement == "foreign" else "launchRequestId"] = (
            "other" if replacement == "foreign" else OTHER
        )
        path.write_text(json.dumps(payload))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="context changed"):
        bridge.launch("first", "library:first")
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "change",
    [
        {"metadata_json": "garbage"},
        {"metadata_json": "[]"},
        {
            "metadata_json": '{"source":"other","launchAcknowledgment":'
            '{"schemaVersion":1,"state":"notStarted"}}'
        },
        {
            "metadata_json": '{"source":"emulation","launchAcknowledgment":'
            '{"schemaVersion":true,"state":"notStarted"}}'
        },
        {
            "metadata_json": '{"source":"emulation","launchAcknowledgment":'
            '{"schemaVersion":2,"state":"notStarted"}}'
        },
        {
            "metadata_json": '{"source":"emulation","launchAcknowledgment":'
            '{"schemaVersion":1,"state":"confirmed"}}'
        },
        {"pid": 123},
        {"start_ticks": 1},
        {"exit_code": 0},
        {"finished_at": None},
        {"failure_code": "unregistered"},
        {"owner": "other"},
        {"game_id": "other"},
        {"state": "launching"},
        {"state": "closed"},
    ],
)
def test_only_exact_typed_terminal_evidence_proves_pre_spawn_refusal(tmp_path, change):
    database = tmp_path / "state.db"
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(
            {
                "id": REQUEST,
                "game_id": "second",
                "owner": SESSION_OWNER,
                "state": "failed",
                "failure_code": "E-CONTENT-UNSUPPORTED",
                "finished_at": "2026-10-29T00:00:00+00:00",
                "metadata_json": json.dumps(
                    {
                        "source": "emulation",
                        "launchAcknowledgment": {"schemaVersion": 1, "state": "notStarted"},
                    }
                ),
                **change,
            }
        )
    result = observe_game_session(database, "second", session_id=REQUEST)
    assert "launchAcknowledgment" not in result


def test_generic_preflight_exception_does_not_create_a_refusal(tmp_path):
    database = tmp_path / "state.db"
    controller = _controller(database, RuntimeError("uncertain"))
    with pytest.raises(RuntimeError, match="uncertain"):
        controller.launch_game("second", launch_request_id=REQUEST)
    with StateStore(database) as store:
        assert store.get_game_session(REQUEST) is None


def test_failed_persistence_keeps_original_error_and_recovery_unknown(
    tmp_path, monkeypatch, caplog
):
    database = tmp_path / "state.db"

    def fail(*_):
        raise OSError("private-storage-detail")

    monkeypatch.setattr(StateStore, "create_game_session", fail)
    controller = _controller(
        database, SteamZeroError("E-CONTENT-UNSUPPORTED", detail="private-error")
    )
    with pytest.raises(LaunchNotStartedError) as refused:
        controller.launch_game("second", launch_request_id=REQUEST)
    assert refused.value.detail == "private-error"
    assert "não persistida" in caplog.text
    assert "private-" not in caplog.text
    assert observe_game_session(database, "second", session_id=REQUEST)["state"] == "unknown"


def test_concurrent_identity_use_is_not_overwritten_by_refusal(tmp_path):
    database = tmp_path / "state.db"
    controller = _controller(database, SteamZeroError("E-CONTENT-UNSUPPORTED"))

    def raced(_):
        with StateStore(database) as store:
            store.create_game_session(
                {"id": REQUEST, "game_id": "other", "owner": "external", "state": "closed"}
            )
        raise SteamZeroError("E-CONTENT-UNSUPPORTED")

    controller._launch_preflight = raced
    with pytest.raises(LaunchNotStartedError):
        controller.launch_game("second", launch_request_id=REQUEST)
    with StateStore(database) as store:
        row = store.get_game_session(REQUEST)
    assert row["game_id"] == "other" and row["owner"] == "external" and row["state"] == "closed"


def test_legacy_call_does_not_publish_correlated_evidence(tmp_path):
    database = tmp_path / "state.db"
    controller = _controller(database, SteamZeroError("E-CONTENT-UNSUPPORTED"))
    with pytest.raises(LaunchNotStartedError):
        controller.launch_game("second")
    assert not database.exists()


def test_refusal_does_not_take_ownership_of_another_running_game(tmp_path):
    database = tmp_path / "state.db"
    ticks = int(Path(f"/proc/{os.getpid()}/stat").read_text().rpartition(") ")[2].split()[19])
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(
            {"id": OTHER, "game_id": "first", "owner": SESSION_OWNER, "state": "launching"}
        )
        store.transition_game_session(OTHER, "running", pid=os.getpid(), start_ticks=ticks)
        before = store.get_game_session(OTHER)
    _record_refusal(database)
    with StateStore(database) as store:
        assert store.get_game_session(OTHER) == before
    assert observe_game_session(database, "first")["state"] == "running"
    assert (
        observe_game_session(database, "second", session_id=REQUEST)["launchAcknowledgment"]
        == "notStarted"
    )


_SERVER = r"""
import json,sys,time
from pathlib import Path
from steamzero.adapters import launcher_ui
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.launcher_receipt import spawn_receipt
from steamzero.launcher.app import LaunchRouter
from steamzero.launcher.launch import consume_context
from steamzero.launcher.navigation import HomeSection
database,context,stop,release,counters,worker=map(Path,sys.argv[1:])
calls=[]
def spawn(argv,*,request_id,game_id):
    assert argv[argv.index('--launch-request-id')+1]==request_id
    calls.append(request_id)
    return spawn_receipt((sys.executable,str(worker),str(database),'0',str(release),
        'json',request_id,'60'),request_id=request_id,game_id=game_id)
router=LaunchRouter(on_spawn=lambda _:0,context_path=context,
    executable=lambda:'steamzero',receipt_spawner=spawn)
bridge=launcher_ui.LauncherBridge(
    sections=(HomeSection(id='library',title='Library',items=('first','lifetime-probe')),),
    titles={'first':'First','lifetime-probe':'Synthetic game'},context_path=context,
    on_launch=router.launch,return_context=consume_context(context),
    readiness=lambda _: {'playable':True,'canPrepare':False},
    session_observer=lambda game:observe_game_session(database,game),
    session_by_id=lambda game,identity:observe_game_session(database,game,session_id=identity))
original_get=launcher_ui._Handler.do_GET
original_send=launcher_ui._Handler._send
dropped=[]
def get(handler):
    if handler.path=='/refusal-control/finish' and handler._authorized():
        release.touch();original_send(handler,200,{})
    elif handler.path=='/refusal-control/count' and handler._authorized():
        original_send(handler,200,{'count':len(calls)})
    else:original_get(handler)
def send(handler,status,body):
    if handler.path.startswith('/session?') and not dropped:
        dropped.append(True);handler.close_connection=True;return
    original_send(handler,status,body)
launcher_ui._Handler.do_GET=get
launcher_ui._Handler._send=send
with bridge.serving() as api:
    print(json.dumps({'api':api,'token':bridge.token}),flush=True)
    deadline=time.monotonic()+45
    while not stop.exists() and time.monotonic()<deadline:time.sleep(.02)
counters.write_text(json.dumps({'launchCalls':len(calls),'requests':calls,'dropped':len(dropped)}))
"""


@pytest.mark.visual
def test_qml_restores_lost_refusal_twice_then_retries_and_returns(tmp_path):
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    assert Path(runner).is_file(), "QML-VISUAL-ENVIRONMENT-001: Qt6 obrigatório"
    database = tmp_path / "state.db"
    context = tmp_path / "context.json"
    release = tmp_path / "release-game"
    preflight = tmp_path / "publish-refusal"
    refusing = tmp_path / "refusing-cli.py"
    refusing.write_text(_REFUSING_WORKER)
    worker = tmp_path / "lifecycle.py"
    worker.write_text(_WORKER)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "QT_QPA_PLATFORM": "offscreen",
        "QML_XHR_ALLOW_FILE_READ": "1",
    }
    source = ROOT / "tests/qml/launcher/check_launcher_refusal_restart.qml"
    harness = tmp_path / source.name
    harness.write_text(
        source.read_text().replace(
            'import "../../../src/steamzero/ui/qml/launcher"',
            f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
        )
    )
    original_pid = None
    try:
        created = subprocess.run(
            [
                sys.executable,
                "-c",
                _CREATOR,
                str(refusing),
                str(database),
                str(context),
                str(release),
                "pending",
                str(preflight),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=12,
        )
        assert created.returncode == 0, created.stdout + created.stderr
        accepted = json.loads(created.stdout)
        original_pid = accepted["observerPid"]
        identity = accepted["requestId"]
        assert accepted["state"] == "pending"
        preflight.touch()  # CLI refuses only after the originating process has exited.
        deadline = time.monotonic() + 8
        while _alive(original_pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not _alive(original_pid)
        assert not (tmp_path / "unexpected-spawn").exists()
        assert (
            observe_game_session(database, "lifetime-probe", session_id=identity)[
                "launchAcknowledgment"
            ]
            == "notStarted"
        )
        for mode in ("observe", "retry"):
            stop, counters = (tmp_path / f"{mode}-{n}" for n in ("stop", "counts.json"))
            with subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _SERVER,
                    str(database),
                    str(context),
                    str(stop),
                    str(release),
                    str(counters),
                    str(worker),
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as process:
                try:
                    assert process.stdout is not None
                    with selectors.DefaultSelector() as ready:
                        ready.register(process.stdout, selectors.EVENT_READ)
                        assert ready.select(timeout=8)
                    config = {**json.loads(process.stdout.readline()), "mode": mode, "capture": ""}
                    if os.environ.get("STEAMZERO_CAPTURE_REFUSAL") == "1":
                        config["capture"] = str(ROOT / "build/agent-runs/r3-refusal-restart")
                    (tmp_path / "refusal-config.json").write_text(json.dumps(config))
                    result = subprocess.run(
                        [runner, "-input", str(harness)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=25,
                    )
                    assert result.returncode == 0, result.stdout + result.stderr
                finally:
                    stop.touch()
                    process.communicate(timeout=10)
            counter = json.loads(counters.read_text())
            assert counter["dropped"] == 1
            assert counter["launchCalls"] == (0 if mode == "observe" else 1)
            if mode == "observe":
                assert json.loads(context.read_text())["launchRequestId"] == identity
            else:
                assert counter["requests"][0] != identity
                assert not context.exists()
        with StateStore(database) as store:
            refused = store.get_game_session(identity)
            retried = store.latest_game_session("lifetime-probe")
        assert refused["state"] == "failed" and refused["pid"] is None
        assert retried["id"] != identity and retried["state"] == "closed"
        assert retried["duration_source"] == "observed-monotonic"
    finally:
        preflight.touch()
        release.touch()
        if original_pid is not None:
            deadline = time.monotonic() + 10
            while _alive(original_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(original_pid)
