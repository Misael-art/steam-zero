# SPDX-License-Identifier: GPL-3.0-or-later
"""Cada tema do pacote deve sustentar o próprio texto — D-29 como gate, não como planilha."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

THEMES = sorted((Path(__file__).resolve().parents[2] / "src/steamzero/themes").glob("*/theme.json"))
TEXT = 4.5
NONTEXT = 3.0
PAIRS_TEXT = [
    ("text", "background"),
    ("text", "surface"),
    ("text", "surfaceRaised"),
    ("textMuted", "background"),
    ("textMuted", "surface"),
    ("accent", "background"),
    ("accentStrong", "background"),
    ("success", "background"),
    ("warning", "background"),
    ("danger", "background"),
]
PAIRS_NONTEXT = [("border", "background"), ("sidebar", "background"), ("focus", "background")]
EXEMPT = {("textDisabled", "background"), ("textDisabled", "surface")}  # WCAG 1.4.3 estado inativo

# Ruling P12: o gate não entra na suíte vermelho. As 11 reprovações medidas em 2026-10-13
# (logs/04-t8-medicao-gate.txt) ficam pinadas aqui com o valor exato da ratio() abaixo.
# Queda abaixo do pin é regressão e falha; par fora da lista que reprova o AA é violação nova
# e falha; pino cujo tema já limpa o AA é pino obsoleto e falha — a Tarefa 9 corrige as
# paletas e remove as entradas ao restaurar o texto.
KNOWN_OPEN_AT_MEASURED: dict[str, dict[tuple[str, str], float]] = {
    # tema do pacote; (fg, bg) -> razão medida
    "org.steamzero.default": {
        ("border", "background"): 1.6258628393900012,
        ("sidebar", "background"): 1.1322487623069288,
    },
    "org.steamzero.asset-recipes-demo": {
        ("border", "background"): 1.6258628393900012,
        ("sidebar", "background"): 1.1322487623069288,
    },
    "org.steamzero.aura": {
        ("accentStrong", "background"): 3.5336659870477414,
        ("border", "background"): 1.439037358729696,
        ("sidebar", "background"): 1.0261876166181085,
    },
    "org.steamzero.steamdeck": {
        ("accent", "background"): 2.914998485406919,
        ("border", "background"): 1.6258628393900012,
        ("sidebar", "background"): 1.1322487623069288,
        ("focus", "background"): 2.914998485406919,
    },
}
PIN_TOLERANCE = 1e-9


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    def rgb(h: str) -> tuple[int, int, int]:
        return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)

    l1, l2 = luminance(rgb(fg)), luminance(rgb(bg))
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def colors(theme: Path) -> dict[str, str]:
    data = json.loads(theme.read_text(encoding="utf-8"))
    merged: dict[str, str] = {}
    parent = data.get("extends")
    if parent:
        # THEMES vem de themes/*/theme.json, então o id do tema é o nome do diretório.
        merged.update(colors(next(p for p in THEMES if p.parent.name == parent)))
    # `org.steamzero.asset-recipes-demo` traz `tokens` sem chave `color`: herda inteiro do default.
    merged.update(data.get("tokens", {}).get("color", {}))
    return merged


def measured_failures(palette: dict[str, str]) -> list[tuple[str, str, float, float]]:
    """Pares abaixo do AA medidos pela própria ratio() do gate: (fg, bg, razão, limiar)."""
    failures: list[tuple[str, str, float, float]] = []
    for fg, bg in PAIRS_TEXT:
        if (fg, bg) in EXEMPT or fg not in palette or bg not in palette:
            continue
        value = ratio(palette[fg], palette[bg])
        if value < TEXT:
            failures.append((fg, bg, value, TEXT))
    for fg, bg in PAIRS_NONTEXT:
        if fg in palette and bg in palette:
            value = ratio(palette[fg], palette[bg])
            if value < NONTEXT:
                failures.append((fg, bg, value, NONTEXT))
    return failures


def check_palette(theme_id: str, palette: dict[str, str]) -> list[str]:
    """Corpo do gate, separado para os testes de fronteira exercitarem as três invariantes da P12.

    Retorna a lista de problemas; vazia significa verde. Não assere — o chamador decide.
    """
    pins = KNOWN_OPEN_AT_MEASURED.get(theme_id, {})
    failures = measured_failures(palette)
    failed_pairs = {(fg, bg) for fg, bg, _, _ in failures}
    problems: list[str] = []
    for fg, bg, value, threshold in failures:
        kind = "" if threshold == TEXT else " (não textual)"
        medida = f"{fg}/{bg} {value:.2f}:1 < {threshold}:1{kind}"
        if (fg, bg) in pins:
            pin = pins[(fg, bg)]
            if value < pin - PIN_TOLERANCE:
                problems.append(f"regressão: {medida} caiu abaixo do pin {pin:.2f}:1")
        else:
            problems.append(f"violação nova sem pin: {medida}")
    for (fg, bg), pin in pins.items():
        if fg not in palette or bg not in palette or (fg, bg) in failed_pairs:
            continue
        problems.append(
            f"pin obsoleto {fg}/{bg} (pinado em {pin:.2f}:1): "
            "remove the pin; the theme now clears AA"
        )
    return problems


def check_theme(theme: Path) -> None:
    """Aplica o gate AA ao tema e cobra a lista de pins aberta (Ruling P12)."""
    theme_id = theme.parent.name
    problems = check_palette(theme_id, colors(theme))
    assert not problems, f"{theme_id}: " + "; ".join(problems)


def test_every_pinned_theme_is_a_package_theme() -> None:
    """Nenhum pin vive num tema fora do glob: renomear o pacote não apaga a dívida."""
    globbed = {p.parent.name for p in THEMES}
    stale_keys = set(KNOWN_OPEN_AT_MEASURED) - globbed
    assert not stale_keys, (
        f"pins para temas que não existem mais no pacote: {sorted(stale_keys)}. "
        "Renomeie/mantenha o pin conforme a decisão do operador na Tarefa 9."
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda p: p.parent.name)
def test_semantic_tokens_clear_wcag_aa(theme: Path) -> None:
    check_theme(theme)


def test_gate_fails_on_a_theme_below_aa_without_a_pin() -> None:
    """Não-vacuidade (a): violação nova sem pin leva o portão inteiro ao vermelho."""
    palette = {"background": "#ffffff", "text": "#777777"}  # ~4,48:1 (< 4,5:1), sem pin
    problems = check_palette("org.steamzero.inventado", palette)
    assert any("violação nova sem pin" in p for p in problems), problems


def test_gate_fails_when_a_pinned_pair_regresses() -> None:
    """Não-vacuidade (b): par pinado que cai abaixo do valor registrado é regressão."""
    real = colors(next(p for p in THEMES if p.parent.name == "org.steamzero.default"))
    pin = KNOWN_OPEN_AT_MEASURED["org.steamzero.default"][("border", "background")]
    # Empata o luminance do `border` com o do fundo: a razão despenca para ~1,0 (pin é 1,63).
    regressed = dict(real, border=real["background"])
    current = ratio(real["border"], real["background"])
    after = ratio(regressed["border"], regressed["background"])
    assert current >= pin - 1e-9, "baseline mudou; atualize o pino antes de testar regressão"
    assert after < pin - 1e-9, "a alteração não produziu regressão mensurável"
    problems = check_palette("org.steamzero.default", regressed)
    assert any("regressão" in p for p in problems), problems


def test_gate_fails_when_a_pinned_pair_now_clears_aa() -> None:
    """Não-vacuidade (c): par pinado que passa a limpar o AA é pino obsoleto."""
    real = colors(next(p for p in THEMES if p.parent.name == "org.steamzero.default"))
    pair = ("border", "background")
    assert pair in KNOWN_OPEN_AT_MEASURED["org.steamzero.default"]
    # `#000000` sobre o fundo claro do default passa folgado o AA não textual (>= 3,0:1).
    fixed = dict(real, border="#000000")
    assert ratio(fixed["border"], fixed["background"]) >= 3.0 + 1e-9
    problems = check_palette("org.steamzero.default", fixed)
    assert any("pin obsoleto" in p for p in problems), problems
    assert not any("regressão" in p or "violação nova" in p for p in problems), problems
