# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI, bridge e QML em processos distintos, usando contexto e SQLite reais."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from test_emulation_session_lifetime import _WORKER, _alive

from steamzero.adapters.emulation import EmulationController
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.core import fs
from steamzero.core.errors import LaunchNotStartedError, SteamZeroError
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore
from steamzero.launcher.launch import (
    CONTEXT_OWNER,
    LaunchPlan,
    consume_context,
    forget_context,
    launch_detached,
)
from steamzero.launcher.navigation import HomeSection

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER = "01ARZ3NDEKTSV4RRFFQ69G5FAW"

_CREATOR = r"""
import json,sys,time
from pathlib import Path
from steamzero.launcher.app import LaunchRouter
from steamzero.adapters.launcher_receipt import spawn_receipt
worker,database,context,release,mode,preflight = sys.argv[1:]
def spawn(argv, *, request_id, game_id):
    args = [sys.executable, worker, database, '0', release, 'json']
    assert argv[argv.index('--launch-request-id')+1] == request_id
    args += [request_id, '60']
    if mode == 'pending':args += [preflight]
    return spawn_receipt(tuple(args), request_id=request_id, game_id=game_id)
router = LaunchRouter(on_spawn=lambda argv: 0, context_path=Path(context),
    executable=lambda:'steamzero', receipt_spawner=spawn)
attempt = router.launch('lifetime-probe', 'library:lifetime-probe')
deadline = time.monotonic()+8
if mode != 'pending':
    while attempt.state == 'pending' and time.monotonic()<deadline: time.sleep(.01)
    assert attempt.state == 'confirmed', attempt.outcome()
print(json.dumps({**attempt.outcome(),'observerPid':attempt.pid}), flush=True)
"""

_SERVER = r"""
import json,sys,time
from pathlib import Path
from steamzero.adapters import launcher_ui
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.launcher.launch import consume_context
from steamzero.launcher.navigation import HomeSection
database,context,stop,release,counters,preflight = map(Path,sys.argv[1:])
calls=[]
def launch(game, focus): calls.append(game); raise AssertionError('restart must not spawn')
bridge=launcher_ui.LauncherBridge(
    sections=(HomeSection(id='library',title='Library',items=('first','lifetime-probe')),),
    titles={'first':'First','lifetime-probe':'Synthetic game'},context_path=context,
    on_launch=launch,return_context=consume_context(context),
    session_observer=lambda game:observe_game_session(database,game),
    session_by_id=lambda game,identity:observe_game_session(database,game,session_id=identity))
original=launcher_ui._Handler.do_GET
def get(handler):
    if handler.path == '/restart-control/finish' and handler._authorized():
        release.touch(); handler._send(200,{})
    elif handler.path == '/restart-control/publish' and handler._authorized():
        preflight.touch(); handler._send(200,{})
    else: original(handler)
launcher_ui._Handler.do_GET=get
with bridge.serving() as api:
    print(json.dumps({'api':api,'token':bridge.token}),flush=True)
    deadline=time.monotonic()+40
    while not stop.exists() and time.monotonic()<deadline:time.sleep(.02)
counters.write_text(json.dumps({'launchCalls':len(calls)}))
"""


@pytest.mark.visual
@pytest.mark.parametrize("pending", [False, True])
def test_launcher_restarts_twice_while_original_lifecycle_owner_survives(
    tmp_path: Path,
    pending: bool,
) -> None:
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    assert Path(runner).is_file(), "QML-VISUAL-ENVIRONMENT-001: Qt6 obrigatório"
    worker = tmp_path / "lifecycle.py"
    worker.write_text(_WORKER)
    database, context, release = (tmp_path / n for n in ("state.db", "context.json", "release"))
    preflight = tmp_path / "publish-session"
    env = {**os.environ, "QML_XHR_ALLOW_FILE_READ": "1", "QT_QPA_PLATFORM": "offscreen"}
    source = ROOT / "tests/qml/launcher/check_launcher_restart.qml"
    harness = tmp_path / source.name
    harness.write_text(
        source.read_text().replace(
            'import "../../../src/steamzero/ui/qml/launcher"',
            f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
        )
    )
    observer_pid = None
    try:
        created = subprocess.run(
            [
                sys.executable,
                "-c",
                _CREATOR,
                str(worker),
                str(database),
                str(context),
                str(release),
                "pending" if pending else "confirmed",
                str(preflight),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=12,
            check=True,
        )
        accepted = json.loads(created.stdout)
        observer_pid = accepted["observerPid"]
        if not pending:
            assert accepted["state"] == "confirmed"
            assert accepted["requestId"] == accepted["sessionId"]
        assert json.loads(context.read_text())["launchRequestId"] == accepted["requestId"]
        for mode in ("active", "return"):
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
                    str(preflight),
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
                    destination = ""
                    if os.environ.get("STEAMZERO_CAPTURE_RESTART") == "1":
                        folder = ROOT / "build/agent-runs/r3-bridge-restart"
                        folder.mkdir(parents=True, exist_ok=True)
                        destination = str(folder)
                    config = {
                        **json.loads(process.stdout.readline()),
                        "mode": mode,
                        "pending": pending and mode == "active",
                        "capture": destination,
                    }
                    (tmp_path / "restart-config.json").write_text(json.dumps(config))
                    result = subprocess.run(
                        [runner, "-input", str(harness)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    assert result.returncode == 0, result.stdout + result.stderr
                finally:
                    stop.touch()
                    process.communicate(timeout=10)
            assert json.loads(counters.read_text())["launchCalls"] == 0
            if mode == "active":
                assert context.exists(), "a primeira retomada não pode consumir a sessão ativa"
        assert not context.exists(), "terminalização deve consumir somente o contexto próprio"
    finally:
        release.touch()
        if observer_pid is not None:
            deadline = time.monotonic() + 10
            while _alive(observer_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(observer_pid), "o owner de fixture deve encerrar após o jogo"


def _context():
    return {
        "schemaVersion": 2,
        "owner": CONTEXT_OWNER,
        "gameId": "second",
        "focusId": "library:second",
        "launchRequestId": REQUEST,
    }


def _restored_bridge(tmp_path, payload, by_id):
    context = tmp_path / "context.json"
    context.write_text(json.dumps(payload))
    return LauncherBridge(
        sections=(HomeSection(id="library", title="Library", items=("first", "second")),),
        context_path=context,
        return_context=consume_context(context),
        on_launch=lambda *_: pytest.fail("recovery must not launch"),
        session_observer=lambda game: {"gameId": game, "state": "running", "sessionId": OTHER},
        session_by_id=by_id,
    )


def test_v2_survives_reads_and_only_matching_owned_context_can_be_consumed(tmp_path):
    path = tmp_path / "context.json"
    plan = LaunchPlan(
        game_id="second",
        focus_id="library:second",
        argv=("fixture",),
        context_path=path,
        launch_request_id=REQUEST,
    )
    launch_detached(plan, spawn=lambda _: 42)
    assert consume_context(path) == consume_context(path) == _context()
    assert not forget_context(path, OTHER)
    assert path.exists()
    assert forget_context(path, REQUEST)
    assert not path.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"owner": "other"},
        {"schemaVersion": 3},
        {"schemaVersion": 2.0},
        {"launchRequestId": "bad"},
        {"launchRequestId": 42},
        {"gameId": "../bad"},
        {"focusId": "bad"},
    ],
)
def test_invalid_versioned_context_is_preserved(tmp_path, changes):
    path = tmp_path / "context.json"
    path.write_text(json.dumps({**_context(), **changes}))
    before = path.read_bytes()
    value, diagnostics = consume_context(path, with_diagnostics=True)
    assert value is None and diagnostics
    assert not forget_context(path, REQUEST)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["legacy", "owned", "unowned", "symlink"])
def test_new_tracked_launch_never_overwrites_pending_or_unowned_data(tmp_path, kind):
    path = tmp_path / "context.json"
    if kind == "symlink":
        target = tmp_path / "keep"
        target.write_text("fixture-data")
        path.symlink_to(target)
    elif kind == "legacy":
        path.write_text(json.dumps({"gameId": "first", "focusId": "library:first"}))
    else:
        path.write_text(json.dumps(_context()) if kind == "owned" else "fixture-data")
    before = path.read_bytes()
    calls = []
    plan = LaunchPlan(
        game_id="second",
        focus_id="library:second",
        argv=("fixture",),
        context_path=path,
        launch_request_id=REQUEST,
    )
    with pytest.raises(SteamZeroError):
        launch_detached(plan, spawn=lambda argv: calls.append(argv))
    assert calls == [] and path.read_bytes() == before
    if kind == "symlink":
        assert consume_context(path) is None
        assert path.is_symlink()


@pytest.mark.parametrize(
    "kind", ["absent", "other-owner", "other-game", "reused-pid", "wrong-port"]
)
def test_unverifiable_recovery_stays_locked_without_latest_session_fallback(tmp_path, kind):
    database = tmp_path / "state.db"
    with StateStore(database) as store:
        store.migrate()
        if kind not in {"absent", "wrong-port"}:
            store.create_game_session(
                {
                    "id": REQUEST,
                    "game_id": "first" if kind == "other-game" else "second",
                    "owner": "other" if kind == "other-owner" else SESSION_OWNER,
                    "state": "launching",
                }
            )
            store.transition_game_session(REQUEST, "running", pid=os.getpid(), start_ticks=1)

    def exact(game, identity):
        if kind == "wrong-port":
            return {"gameId": "first", "sessionId": identity, "state": "closed"}
        return observe_game_session(database, game, session_id=identity)

    bridge = _restored_bridge(tmp_path, _context(), exact)
    assert bridge.session("second")["state"] in {"awaiting", "unknown"}
    assert (tmp_path / "context.json").exists()
    with pytest.raises(ValueError):
        bridge.launch("first", "library:first")


def test_exact_recovery_ignores_newer_history_and_preserves_a_replaced_context(tmp_path):
    database = tmp_path / "state.db"
    ticks = int(Path(f"/proc/{os.getpid()}/stat").read_text().rpartition(") ")[2].split()[19])
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(
            {"id": REQUEST, "game_id": "second", "owner": SESSION_OWNER, "state": "launching"}
        )
        store.transition_game_session(REQUEST, "running", pid=os.getpid(), start_ticks=ticks)
        store.create_game_session(
            {"id": OTHER, "game_id": "second", "owner": SESSION_OWNER, "state": "failed"}
        )
    bridge = _restored_bridge(
        tmp_path,
        _context(),
        lambda game, identity: observe_game_session(database, game, session_id=identity),
    )
    assert observe_game_session(database, "second")["sessionId"] == OTHER
    assert bridge.session("second")["state"] == "running"
    path = tmp_path / "context.json"
    path.write_text(json.dumps({**_context(), "launchRequestId": OTHER}))
    before = path.read_bytes()
    with StateStore(database) as store:
        store.transition_game_session(REQUEST, "closing")
        store.transition_game_session(REQUEST, "closed")
    assert bridge.session("second")["state"] == "closed"
    assert path.read_bytes() == before


def test_missing_exact_read_port_is_not_permission_to_adopt_latest(tmp_path):
    bridge = _restored_bridge(tmp_path, _context(), None)
    assert bridge.session("second") == {"gameId": "second", "state": "awaiting", "sessionId": None}


@pytest.mark.parametrize("failure", [FileNotFoundError, RuntimeError])
def test_spawn_failure_distinguishes_known_absence_from_uncertainty(tmp_path, failure):
    path = tmp_path / "context.json"
    plan = LaunchPlan(
        game_id="second",
        focus_id="library:second",
        argv=("fixture",),
        context_path=path,
        launch_request_id=REQUEST,
    )

    def spawn(_):
        raise failure("controlled")

    with pytest.raises(failure):
        launch_detached(plan, spawn=spawn)
    assert path.exists() is (failure is RuntimeError)


def test_tracked_context_publication_is_exclusive_across_concurrent_requests(tmp_path, monkeypatch):
    path = tmp_path / "context.json"
    calls = []
    barrier = threading.Barrier(2)
    original = fs.write_tmp

    def synchronized(*args, **kwargs):
        temporary = original(*args, **kwargs)
        barrier.wait(timeout=5)
        return temporary

    monkeypatch.setattr(fs, "write_tmp", synchronized)

    def launch(identity):
        plan = LaunchPlan(
            game_id="second",
            focus_id="library:second",
            argv=("fixture",),
            context_path=path,
            launch_request_id=identity,
        )
        try:
            launch_detached(plan, spawn=lambda _: calls.append(identity) or 42)
        except SteamZeroError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(launch, [REQUEST, OTHER]))
    assert sorted(results) == [False, True]
    assert len(calls) == 1 and json.loads(path.read_text())["launchRequestId"] == calls[0]
    assert not list(tmp_path.glob(".*.tmp.*"))


@pytest.mark.parametrize("case", ["invalid", "untracked", "reused"])
def test_preallocated_identity_refused_before_configuration_or_spawn(tmp_path, case):
    controller = EmulationController.__new__(EmulationController)
    effects = []
    controller._process_waiter = None if case == "untracked" else lambda _: 0
    controller._prepare_launch = lambda _: effects.append("prepare")
    database = tmp_path / "state.db"
    controller._store_factory = lambda: StateStore(database)
    if case == "reused":
        with StateStore(database) as store:
            store.migrate()
            store.create_game_session(
                {"id": REQUEST, "game_id": "other", "owner": SESSION_OWNER, "state": "closed"}
            )
            original = store.get_game_session(REQUEST)
    with pytest.raises(LaunchNotStartedError):
        controller.launch_game("second", launch_request_id="bad" if case == "invalid" else REQUEST)
    assert effects == []
    if case == "reused":
        with StateStore(database) as store:
            assert store.get_game_session(REQUEST) == original


def test_removed_game_does_not_prevent_exact_terminal_observation(tmp_path):
    path = tmp_path / "context.json"
    path.write_text(json.dumps(_context()))
    bridge = LauncherBridge(
        sections=(HomeSection(id="library", title="Library", items=("first",)),),
        context_path=path,
        return_context=consume_context(path),
        on_launch=lambda *_: pytest.fail("recovery must not launch"),
        session_by_id=lambda game, identity: {
            "gameId": game,
            "sessionId": identity,
            "state": "closed",
        },
    )
    assert bridge.session("second")["state"] == "closed"
    assert not path.exists()
