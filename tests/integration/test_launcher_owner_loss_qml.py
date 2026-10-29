# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt, canonical CLI and detached game after the original owner disappears."""

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
database,context,stop,release,counters,worker,entry=map(Path,sys.argv[1:])
launches=[];recoveries=[];dropped=[]
def spawn(argv,*,request_id,game_id):
    launches.append(request_id);release.unlink(missing_ok=True)
    return spawn_receipt(
        (sys.executable,str(worker),str(database),'0',str(release),'json',request_id,'60'),
        request_id=request_id,game_id=game_id)
router=LaunchRouter(on_spawn=lambda _:0,context_path=context,
    executable=lambda:str(entry),receipt_spawner=spawn)
def recover(game,identity):
    recoveries.append(identity)
    return router.recover_session(game,identity)
bridge=launcher_ui.LauncherBridge(
    sections=(HomeSection(id='library',title='Library',items=('first','lifetime-probe')),),
    titles={'first':'First','lifetime-probe':'Synthetic game'},context_path=context,
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
        original_send(handler,200,{'launches':len(launches),'recoveries':len(recoveries)})
    else:original_get(handler)
def send(handler,status,body):
    if handler.path=='/session/recover' and not dropped:
        dropped.append(True);handler.close_connection=True;return
    original_send(handler,status,body)
launcher_ui._Handler.do_GET=get
launcher_ui._Handler._send=send
with bridge.serving() as api:
    print(json.dumps({'api':api,'token':bridge.token}),flush=True)
    deadline=time.monotonic()+45
    while not stop.exists() and time.monotonic()<deadline:time.sleep(.02)
counters.write_text(json.dumps({'launches':launches,'recoveries':recoveries,'dropped':len(dropped)}))
"""


@pytest.mark.visual
def test_qml_preserves_live_game_then_recovers_orphan_explicitly_and_retries(tmp_path):
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
        os.kill(owner_pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while _alive(owner_pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not _alive(owner_pid) and _alive(game_pid)
        for mode in ("observe", "recover"):
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
                    config = {**json.loads(server.stdout.readline()), "mode": mode, "capture": ""}
                    if os.environ.get("STEAMZERO_CAPTURE_OWNER_LOSS") == "1":
                        config["capture"] = str(ROOT / "build/agent-runs/r3-owner-loss")
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
            assert len(counts["launches"]) == (0 if mode == "observe" else 1)
            assert len(counts["recoveries"]) == (0 if mode == "observe" else 1)
            with StateStore(database) as store:
                row = store.get_game_session(identity)
            if mode == "observe":
                assert row == before, "GET/owner loss must not mutate the canonical row"
                assert json.loads(context.read_text())["launchRequestId"] == identity
            else:
                assert counts["dropped"] == 1 and counts["recoveries"] == [identity]
                assert counts["launches"][0] != identity and not context.exists()
                assert row["state"] == "failed" and row["failure_code"] == "E-SESSION-ORPHANED"
                assert row["exit_code"] is None
                assert row["played_seconds"] == before["played_seconds"]
                assert row["duration_source"] == before["duration_source"]
                with StateStore(database) as store:
                    latest = store.latest_game_session("lifetime-probe")
                assert latest["state"] == "closed" and latest["id"] == counts["launches"][0]
    finally:
        release.touch()
        for pid in (owner_pid, game_pid):
            if pid is None:
                continue
            deadline = time.monotonic() + 10
            while _alive(pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not _alive(pid)
