# SPDX-License-Identifier: GPL-3.0-or-later
"""Golden objetivo do D-10: a linha de atalhos cabe com as ações de sessão visíveis.

Reprodução registrada na Tarefa 12 do lote de coesão da UI e corrigida na
Tarefa 13: o rodapé de ``LauncherJourney.qml`` era um RowLayout de linha única
em que o Label de atalhos (``Layout.fillWidth``, sem elisão) nascia esmagado a
263px quando as seis ações de sessão pediam ~502px no viewport lógico da
evidência (853x534 = 1280x801 físicos em escala de interface 1.5 — capturas
L22/L24). O rodapé agora é um grid de duas linhas: a linha de atalhos inteira
na primeira, as seis ações visíveis na segunda. Não se aceitou correção por
elisão: ``Text.ElideNone`` e o texto inteiro dentro da janela seguem sendo
parte do portão.

O portão era ``xfail(strict=True)`` (``808bf2d9``) enquanto a superfície era
reservada à T13; com a correção aterrissada ele foi re-pinnado para PASS — e a
régua agora também recusa passe falso: a saída do qmltestrunner precisa mostrar
que a função de medição foi realmente localizada e executada (linha PASS
específica + totais sem falha). Um harness quebrado reprova alto; xfail
silencioso não é mais opção.

Segundo re-pin (após o CI): a asserção "largura >= implícita de linha única"
passava no host mas reproduzia falso-corte no Qt 6.11.2 do CI (implícita 876 >
alocada 866) — métrica de fonte é ambiente. A régua passa a medir o defeito em
qualquer ambiente: sem elisão, sem clip, quebra de linha real assumida pelo
produto, altura cobrindo o texto quebrado por inteiro e a faixa dentro da
janela.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from tests.integration.test_launcher_session_footer_observed import (
    ROOT,
    RUNNER,
    _qml_environment,
)

LAYOUT_HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_session_footer_layout.qml"

_MEASUREMENT_PASS = re.compile(
    r"PASS\s*:\s*\S*::LauncherSessionFooterLayout::"
    r"test_shortcut_line_fits_when_session_actions_are_visible\b"
)
_TOTALS = re.compile(r"Totals:\s*(\d+) passed,\s*(\d+) failed")


@pytest.mark.visual
def test_session_footer_shortcut_line_fits_with_visible_actions(
    tmp_path: Path,
) -> None:
    """D-10 golden: a linha de atalhos não pode nascer cortada com as ações visíveis."""
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    env = _qml_environment(tmp_path)
    completed = subprocess.run(
        [str(RUNNER), "-input", str(LAYOUT_HARNESS)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, f"golden D-10 reprovou:\n{output[-4000:]}"
    assert "FAIL!" not in output, f"golden D-10 mediu corte:\n{output[-4000:]}"
    # Guarda anti-vácuo (cobrança da revisão da T12): o passe só vale se a
    # corrida localizou o nó da linha de atalhos e chegou à medição. A função
    # de teste verifica ``shortcut !== null`` antes de medir; sua linha PASS é
    # a prova de que o caminho foi executado. Totais zerados (harness que não
    # carregou, teste que não rodou) reprovam aqui em vez de virar verde.
    assert _MEASUREMENT_PASS.search(output), (
        f"golden D-10 não executou a medição; saída do qmltestrunner:\n{output[-4000:]}"
    )
    totals = _TOTALS.search(output)
    assert totals is not None, (
        f"golden D-10 não publicou totais de execução;\nsaída:\n{output[-4000:]}"
    )
    passed, failed = (int(value) for value in totals.groups())
    assert failed == 0 and passed >= 3, (
        f"golden D-10: esperado a suíte de medição completa (3 passed, 0 failed), "
        f"obtido {passed} passed, {failed} failed"
    )
