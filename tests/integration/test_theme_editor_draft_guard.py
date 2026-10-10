# SPDX-License-Identifier: GPL-3.0-or-later
"""Saída do editor de temas com rascunho e histórico das edições de metadados.

O harness QML substitui a ponte por uma fila que ele mesmo responde, o que
permite provar a ordem que importa: save que falha, save que conclui, descarte
com pedido em voo e resposta atrasada chegando numa sessão seguinte.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

QML = shutil.which("qml6")
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(QML is None, reason="qml6 ausente; o harness do editor não pode rodar")
@pytest.mark.parametrize(
    "harness",
    [
        "tests/qml/check_theme_editor_draft_guard.qml",
        # Fechar a janela da Central é a saída que o painel sozinho não enxerga.
        "tests/qml/check_main_theme_draft_close.qml",
    ],
)
def test_editor_protege_rascunho_e_consome_historico_de_metadados(harness: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QT_QPA_PLATFORM": "offscreen",
            "QML_DISABLE_DISK_CACHE": "1",
        }
    )
    completed = subprocess.run(
        [str(QML), harness],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert "FAIL:" not in output, output
