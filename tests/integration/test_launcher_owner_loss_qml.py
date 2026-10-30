# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt, canonical lifecycle and terminal replay across bridge processes."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from test_emulation_session_lifetime import _WORKER, _alive
from test_launcher_restart import _CREATOR

from steamzero.adapters.game_session_probe import process_identity
from steamzero.core.state import StateStore
from steamzero.launcher.launch import CONTEXT_OWNER

ROOT = Path(__file__).resolve().parents[2]

_SERVER = r"""
import json,sys,time
from pathlib import Path
from steamzero.adapters import launcher_ui
from steamzero.adapters.launcher_session import observe_game_session
from steamzero.adapters.launcher_receipt import spawn_receipt
from steamzero.launcher.app import LaunchRouter
from steamzero.launcher.launch import consume_context
from steamzero.launcher.navigation import HomeSection
database,context,stop,release,counters,worker,entry=map(Path,sys.argv[1:8])
mode=sys.argv[8]
removed=len(sys.argv)>9 and sys.argv[9]=='removed'
launches=[];recoveries=[];dropped=[];terminal_dropped=[]
def spawn(argv,*,request_id,game_id):
    launches.append(request_id);release.unlink(missing_ok=True)
    launch_worker=worker
    if game_id!='lifetime-probe':
        launch_worker=worker.with_name('next-lifecycle.py')
        launch_worker.write_text(worker.read_text().replace("'lifetime-probe'",repr(game_id)))
    return spawn_receipt(
        (sys.executable,str(launch_worker),str(database),'0',str(release),'json',request_id,'60'),
        request_id=request_id,game_id=game_id)
router=LaunchRouter(on_spawn=lambda _:0,context_path=context,
    executable=lambda:str(entry),receipt_spawner=spawn)
def recover(game,identity):
    recoveries.append(identity)
    return router.recover_session(game,identity)
sections=(HomeSection(id='library',title='Library',items=('first','lifetime-probe')),)
if removed:
    items=('lifetime-probe','survivor') if mode=='closed-finish-lost' else ('survivor',)
    sections=(HomeSection(id='top',title='Top',items=('first',)),
        HomeSection(id='library',title='Library',items=items))
bridge=launcher_ui.LauncherBridge(
    sections=sections,
    titles={'first':'First','lifetime-probe':'Synthetic game','survivor':'Surviving game'},
    context_path=context,
    on_launch=router.launch,return_context=consume_context(context),recover_session=recover,
    readiness=lambda _: {'playable':True,'canPrepare':False},
    session_observer=lambda game:observe_game_session(database,game),
    session_by_id=lambda game,identity:observe_game_session(database,game,session_id=identity))
original_get=launcher_ui._Handler.do_GET
original_send=launcher_ui._Handler._send
def get(handler):
    if handler.path=='/owner-control/finish' and handler._authorized():
        release.touch();original_send(handler,200,{})
    elif handler.path=='/owner-control/count' and handler._authorized():
        original_send(handler,200,{'launches':len(launches),'recoveries':len(recoveries),
            'terminalDrops':len(terminal_dropped)})
    else:original_get(handler)
def send(handler,status,body):
    if (mode in {'closed-finish-lost','closed-restart-lost'}
            and handler.path.startswith('/session?') and body.get('state')=='closed'):
        terminal_dropped.append(True);handler.close_connection=True;return
    if (mode in {'lost-terminal','restart-lost-terminal'}
            and handler.path.startswith('/session?')
            and body.get('state')=='failed' and body.get('failureCode')=='E-SESSION-ORPHANED'):
        terminal_dropped.append(True);handler.close_connection=True;return
    if handler.path=='/session/recover' and mode!='lost-terminal' and not dropped:
        dropped.append(True);handler.close_connection=True;return
    original_send(handler,status,body)
launcher_ui._Handler.do_GET=get
launcher_ui._Handler._send=send
with bridge.serving() as api:
    print(json.dumps({'api':api,'token':bridge.token}),flush=True)
    deadline=time.monotonic()+45
    while not stop.exists() and time.monotonic()<deadline:time.sleep(.02)
counters.write_text(json.dumps({'launches':launches,'recoveries':recoveries,
    'dropped':len(dropped),'terminalDrops':len(terminal_dropped)}))
"""


@pytest.mark.visual
@pytest.mark.parametrize(
    "lose_terminal,normal_close,catalog_removed",
    [(False, False, False), (True, False, False), (True, True, False), (True, True, True)],
    ids=["post-reply-loss", "terminal-get-restart", "closed-get-restart", "removed-closed-restart"],
)
def test_qml_retains_terminal_context_after_reply_loss_and_restarts(
    tmp_path, lose_terminal, normal_close, catalog_removed
):
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    assert Path(runner).is_file(), "QML-VISUAL-ENVIRONMENT-001: Qt6 obrigatório"
    state_home = tmp_path / "xdg-state"
    database = state_home / "steamzero/state.db"
    context = tmp_path / "context.json"
    release = tmp_path / "release-game"
    worker = tmp_path / "lifecycle.py"
    worker.write_text(_WORKER)
    entry = tmp_path / "steamzero-cli"
    entry.write_text(
        f"#!{sys.executable}\nfrom steamzero.cli.main import main\nraise SystemExit(main())\n"
    )
    entry.chmod(0o700)
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "QT_QPA_PLATFORM": "offscreen",
        "QML_XHR_ALLOW_FILE_READ": "1",
        "XDG_STATE_HOME": str(state_home),
        "STEAMZERO_NO_DAEMON": "1",
    }
    source = ROOT / "tests/qml/launcher/check_launcher_owner_loss.qml"
    harness = tmp_path / source.name
    harness.write_text(
        source.read_text().replace(
            'import "../../../src/steamzero/ui/qml/launcher"',
            f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
        )
    )
    owner_pid = None
    game_pid = None
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
                "confirmed",
                str(tmp_path / "unused-preflight"),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=12,
        )
        assert created.returncode == 0, created.stdout + created.stderr
        accepted = json.loads(created.stdout)
        owner_pid = accepted["observerPid"]
        identity = accepted["sessionId"]
        with StateStore(database) as store:
            before = store.get_game_session(identity)
        game_pid = before["pid"]
        owner = json.loads(before["metadata_json"])["lifecycleOwner"]
        assert (
            owner["pid"] == owner_pid
            and process_identity(owner_pid, owner["startTicks"]) == "alive"
        )
        if normal_close:
            assert _alive(owner_pid) and _alive(game_pid)
            phases = ("closed-finish-lost", "closed-restart-lost", "closed-reopened")
        else:
            os.kill(owner_pid, signal.SIGTERM)
            deadline = time.monotonic() + 5
            while _alive(owner_pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(owner_pid) and _alive(game_pid)
            phases = (
                ("observe", "lost-terminal", "restart-lost-terminal", "recover-reopened")
                if lose_terminal
                else ("observe", "recover")
            )
        terminal_row = None
        for mode in phases:
            stop, counters = (tmp_path / f"{mode}-{name}" for name in ("stop", "counts.json"))
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
                    str(entry),
                    mode,
                    "removed" if catalog_removed else "unchanged",
                ],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as server:
                try:
                    assert server.stdout is not None
                    with selectors.DefaultSelector() as ready:
                        ready.register(server.stdout, selectors.EVENT_READ)
                        assert ready.select(timeout=8)
                    config = {
                        **json.loads(server.stdout.readline()),
                        "mode": mode,
                        "identity": identity,
                        "returnFocus": (
                            "library:survivor"
                            if catalog_removed and mode != "closed-finish-lost"
                            else "library:lifetime-probe"
                        ),
                        "nextGame": "survivor" if catalog_removed else "lifetime-probe",
                        "nextFocus": "library:survivor"
                        if catalog_removed
                        else "library:lifetime-probe",
                        "capture": "",
                    }
                    if os.environ.get("STEAMZERO_CAPTURE_OWNER_LOSS") == "1":
                        folder = (
                            "r3-removed-return"
                            if catalog_removed
                            else "r3-closed-restart"
                            if normal_close
                            else "r3-terminal-restart"
                            if lose_terminal
                            else "r3-owner-loss"
                        )
                        config["capture"] = str(ROOT / "build/agent-runs" / folder)
                    (tmp_path / "owner-loss-config.json").write_text(json.dumps(config))
                    result = subprocess.run(
                        [runner, "-input", str(harness)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    assert result.returncode == 0, result.stdout + result.stderr
                finally:
                    stop.touch()
                    server.communicate(timeout=10)
            counts = json.loads(counters.read_text())
            retried = mode in {"recover", "recover-reopened", "closed-reopened"}
            assert len(counts["launches"]) == int(retried)
            assert len(counts["recoveries"]) == int(mode in {"recover", "lost-terminal"})
            with StateStore(database) as store:
                row = store.get_game_session(identity)
            retained = json.loads(context.read_text())
            assert retained["owner"] == CONTEXT_OWNER and retained["schemaVersion"] == 2
            next_game = "survivor" if catalog_removed and retried else "lifetime-probe"
            assert retained["gameId"] == next_game
            assert retained["focusId"] == f"library:{next_game}"
            if normal_close:
                assert row["state"] == "closed" and row["exit_code"] == 0
                assert row["failure_code"] is None and counts["recoveries"] == []
                if terminal_row is None:
                    terminal_row = row
                    deadline = time.monotonic() + 5
                    while _alive(owner_pid) and time.monotonic() < deadline:
                        time.sleep(0.02)
                    assert not _alive(owner_pid) and not _alive(game_pid)
                else:
                    assert row == terminal_row, "terminal observation changed lifecycle/playtime"
                if retried:
                    latest_id = counts["launches"][0]
                    assert latest_id != identity
                    with StateStore(database) as store:
                        latest = store.latest_game_session(next_game)
                    assert latest["game_id"] == next_game
                    assert latest["id"] == latest_id and latest["state"] == "closed"
                    assert latest["exit_code"] == 0 and latest["failure_code"] is None
                else:
                    assert counts["terminalDrops"] > 0
                    latest_id = identity
                assert json.loads(context.read_text())["launchRequestId"] == latest_id
            elif mode == "observe":
                assert row == before, "GET/owner loss must not mutate the canonical row"
                assert json.loads(context.read_text())["launchRequestId"] == identity
            elif retried:
                assert counts["dropped"] == int(mode == "recover")
                assert counts["recoveries"] == ([identity] if mode == "recover" else [])
                assert counts["launches"][0] != identity
                assert json.loads(context.read_text())["launchRequestId"] == counts["launches"][0]
                assert row["state"] == "failed" and row["failure_code"] == "E-SESSION-ORPHANED"
                assert row["exit_code"] is None
                assert row["played_seconds"] == before["played_seconds"]
                assert row["duration_source"] == before["duration_source"]
                with StateStore(database) as store:
                    latest = store.latest_game_session("lifetime-probe")
                assert latest["state"] == "closed" and latest["id"] == counts["launches"][0]
            else:
                assert counts["terminalDrops"] > 0 and counts["dropped"] == 0
                assert context.exists(), "lost terminal GET consumed the restart context"
                assert json.loads(context.read_text())["launchRequestId"] == identity
                assert row["state"] == "failed" and row["failure_code"] == "E-SESSION-ORPHANED"
                assert row["exit_code"] is None
                assert row["played_seconds"] == before["played_seconds"]
                assert row["duration_source"] == before["duration_source"]
    finally:
        release.touch()
        for pid in (owner_pid, game_pid):
            if pid is None:
                continue
            deadline = time.monotonic() + 10
            while _alive(pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(pid)
