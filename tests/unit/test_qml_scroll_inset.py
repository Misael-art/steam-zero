# SPDX-License-Identifier: GPL-3.0-or-later
"""O inset inferior rola com o conteúdo; ele não encolhe a viewport.

`bottomPadding` num ScrollView reduz a área visível em vez de acrescentar
espaço rolável, o que deixava uma faixa morta acima do rodapé em 1280x800
(aceite instalado de 2026-10-21, Visão geral).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

QML = Path(__file__).resolve().parents[2] / "src" / "steamzero" / "ui" / "qml"

# Residual registrado: o filho direto destes ScrollViews é o painel de temas, não
# um layout onde caiba o espaçador; a correção pertence à frente de temas.
KNOWN_THEME_PANEL_SCROLLS = {"themeCatalogScroll", "themeEditorScroll"}


@pytest.mark.parametrize("name", ["Main.qml", "SteamGameplay.qml", "Emulation.qml"])
def test_scrollviews_do_not_pad_viewport_with_safe_inset(name: str) -> None:
    source = (QML / name).read_text(encoding="utf-8")
    offenders = [
        match.group(0)
        for match in re.finditer(r"ScrollView \{(?:(?!\n\s*\w+ \{).)*", source, re.S)
        if re.search(r"bottomPadding: (root|page)\.bottomSafeInset", match.group(0))
        and not any(f"id: {known}" in match.group(0) for known in KNOWN_THEME_PANEL_SCROLLS)
    ]
    assert offenders == [], f"{name}: ScrollView com bottomPadding de inset seguro"
