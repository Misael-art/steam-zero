# SPDX-License-Identifier: GPL-3.0-or-later
"""Golden objetivo do D-10: a linha de atalhos cabe com as ações de sessão visíveis.

Reprodução registrada na Tarefa 12 do lote de coesão da UI. A correção do
layout pertence ao RowLayout do rodapé em ``LauncherJourney.qml`` — superfície
reservada à Tarefa 13, fora da cessão desta tarefa. Por isto o golden entra
como ``xfail(strict=True)``: ele falha hoje exatamente pela medida da evidência
(capturas L22/L24: linha cortada em 263px quando pede 392px no viewport lógico
853x534 — 1280x801 físicos em escala de interface 1.5) e vira XPASS — forçando
re-pin da régua — no dia em que o layout corrigir. Não se aceita aqui correção
por elisão: ``Text.ElideNone`` e o texto inteiro dentro da janela são parte
do portão.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tests.integration.test_launcher_session_footer_observed import (
    ROOT,
    RUNNER,
    _qml_environment,
)

LAYOUT_HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_session_footer_layout.qml"


@pytest.mark.visual
@pytest.mark.xfail(
    strict=True,
    reason=(
        "D-10 exige correção no RowLayout do rodapé de LauncherJourney.qml "
        "(superfície reservada à T13; fora da cessão desta tarefa). O golden "
        "objetivo mede no viewport lógico da evidência (853x534 = 1280x801 "
        "físicos em escala de interface 1.5, calibrado pelas capturas L22/L24) "
        "que a linha de atalhos recebe largura igual à sua largura implícita "
        "com as seis ações de sessão visíveis e fica inteira dentro da janela. "
        "Quando a T13 corrigir o layout, este teste vira XPASS e a régua "
        "deverá ser re-pinnada para PASS."
    ),
)
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
