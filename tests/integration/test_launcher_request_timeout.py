# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""A cena devolve controle quando a ponte loopback aceita e congela."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_request_timeout.qml"


def _runner() -> str | None:
    for candidate in (
        Path("/usr/lib/qt6/bin/qmltestrunner"),
        Path("/usr/lib64/qt6/bin/qmltestrunner"),
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("qmltestrunner6")


RUNNER = _runner()


def _require_runner() -> str:
    if RUNNER is None:
        pytest.fail("QML-VISUAL-ENVIRONMENT-001: qmltestrunner do Qt6 não está disponível")
    return RUNNER


class _HoldingHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/hold":
            self.server.received.set()
            self.server.release.wait(timeout=15)
            return
        if self.path.endswith("/model"):
            with self.server.count_lock:
                count = self.server.counts.get(self.path, 0) + 1
                self.server.counts[self.path] = count
            if self.path == "/old/model" and count == 1:
                self.server.old_started.set()
                self.server.release_old.wait(6)
                self._reply(503, {})
                self.server.old_finished.set()
                return
            if self.path in {"/retry/model", "/escape/model"} and count == 2:
                self._reply(503, {})
                return
            if self.path in {"/invalid/model", "/invalid-shape/model"} and count == 2:
                invalid = (
                    None
                    if self.path == "/invalid/model"
                    else {"focusMap": {"initial": "missing", "nodes": {}}, "sections": []}
                )
                self._reply(200, invalid)
                return
            self._reply(
                200,
                {
                    "focusMap": {
                        "initial": "library:first",
                        "nodes": {
                            "library:first": {"section": "library", "column": 0, "action": None},
                            "library:second": {"section": "library", "column": 1, "action": None},
                        },
                    },
                    "sections": [
                        {
                            "id": "library",
                            "title": "Library",
                            "items": [
                                {"id": "first", "title": "First"},
                                {"id": "second", "title": "Second"},
                            ],
                        }
                    ],
                },
            )
        elif self.path == "/old/release":
            self.server.release_old.set()
            self._reply(200, {})
        elif self.path == "/old/started":
            self._reply(200, {"ready": self.server.old_started.is_set()})
        elif self.path == "/old/finished":
            self._reply(200, {"ready": self.server.old_finished.is_set()})
        elif "/session?" in self.path:
            self._reply(
                200, {"gameId": "second", "sessionId": "session-fixture", "state": "running"}
            )
        else:
            self._reply(200, {})

    def _reply(self, status, value):
        content = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # A substituted catalog request is deliberately cancelled.

    def log_message(self, *_: object) -> None:
        pass


@pytest.mark.visual
def test_qml_watchdog_times_out_when_loopback_peer_is_suspended(tmp_path: Path) -> None:
    runner = _require_runner()
    server = ThreadingHTTPServer(("127.0.0.1", 18169), _HoldingHandler)
    server.daemon_threads = True
    server.received = threading.Event()  # type: ignore[attr-defined]
    server.release_old = threading.Event()  # type: ignore[attr-defined]
    server.old_started = threading.Event()  # type: ignore[attr-defined]
    server.old_finished = threading.Event()  # type: ignore[attr-defined]
    server.count_lock = threading.Lock()  # type: ignore[attr-defined]
    server.counts = {}  # type: ignore[attr-defined]
    server.release = threading.Event()  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QML_XHR_ALLOW_FILE_READ": "1"}
        harness = tmp_path / HARNESS.name
        harness.write_text(
            HARNESS.read_text().replace(
                'import "../../../src/steamzero/ui/qml/launcher"',
                f'import "{(ROOT / "src/steamzero/ui/qml/launcher").as_uri()}"',
            )
        )
        evidence = {"directory": ""}
        argv = [runner, "-input", str(harness)]
        if os.environ.get("STEAMZERO_CAPTURE_BRIDGE") == "1":
            destination = ROOT / "build/agent-runs/r3-bridge"
            destination.mkdir(parents=True, exist_ok=True)
            evidence["directory"] = str(destination)
        (tmp_path / "bridge-evidence.json").write_text(json.dumps(evidence))
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=ROOT,
            env=environment,
        )
        assert server.received.wait(timeout=5), (
            "o harness não alcançou o peer suspenso:\n" + completed.stdout + completed.stderr
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        server.release_old.set()  # type: ignore[attr-defined]
        server.release.set()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
