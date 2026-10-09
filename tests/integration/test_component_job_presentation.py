# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Contrato QML do resultado terminal e rastreamento de component.apply."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "qml" / "check_component_job_presentation.qml"
QML = shutil.which("qml6")


@pytest.mark.visual
def test_component_job_outcome_and_trace_are_presented_without_false_success() -> None:
    if QML is None:
        pytest.fail("QML-VISUAL-ENVIRONMENT-001: qml6 não está disponível")
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_FORCE_STDERR_LOGGING"] = "1"
    completed = subprocess.run(
        [QML, str(HARNESS)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (
        f"resultado de component.apply inconsistente:\n{completed.stdout}\n{completed.stderr}"
    )
