#!/usr/bin/env python3
"""Auditoria de cores da UI (somente leitura).

Três medidas, todas recomputáveis:

  1. Contraste WCAG 2.1 entre cada token cromático do tema e o fundo real sobre o qual
     ele é pintado (background / surface / sidebar / surfaceSelected). Limiar AA de texto
     normal = 4,5:1; de texto grande e de elemento não textual = 3:1.
  2. A classe D-01: os temas definem `palette.buttonText` claro, mas `DarkButton` é um
     QQC.Button puro que pinta o fundo com a **cor estática do estilo** — medida em pixels
     em logs/06: #FCFCFC habilitado, #E3E5E7 desabilitado. Cada tema é confrontado com
     essas duas estáticas, porque é ali que o rótulo realmente aparece.
  3. Cobertura de tokens: quais chaves de `tokens.color` cada tema deixa de definir depois
     de resolver a cadeia `extends` (um token ausente cai no tema herdado ou no default).

Fontes: os tema.json do pacote instalado e os do catálogo do host. Nada é escrito.
"""

from __future__ import annotations

import glob
import json
import os
import pathlib
import re
import sys

re_button = re.compile(r"^\s*(?:QQC\.)?Button\s*\{")

REL = pathlib.Path("/opt/steamzero/releases/2.0.0rc1-2b7eb541b4a5/venv/lib/python3.14/site-packages/steamzero")
HOST = pathlib.Path.home() / ".local/share/steamzero/themes"
STYLE_ENABLED = "#FCFCFC"
STYLE_DISABLED = "#E3E5E7"

# pares (token, fundo sobre o qual ele aparece) que a UI realmente compõe
PAIRS = [
    ("text", "background", "texto normal sobre o fundo"),
    ("text", "surface", "texto normal sobre o painel"),
    ("text", "surfaceSelected", "texto do item selecionado"),
    ("textMuted", "background", "texto secundário sobre o fundo"),
    ("textMuted", "surface", "texto secundário sobre o painel"),
    ("textDisabled", "background", "texto desabilitado sobre o fundo"),
    ("textDisabled", "surface", "texto desabilitado sobre o painel"),
    ("accent", "background", "acentos/links sobre o fundo"),
    ("accent", "surface", "acentos sobre o painel"),
    ("accentStrong", "background", "acento forte sobre o fundo"),
    ("success", "background", "sucesso sobre o fundo"),
    ("success", "successSurface", "sucesso sobre o painel de sucesso"),
    ("warning", "background", "aviso sobre o fundo"),
    ("warning", "warningSurface", "aviso sobre o painel de aviso"),
    ("danger", "background", "erro sobre o fundo"),
    ("danger", "dangerSurface", "erro sobre o painel de erro"),
    ("border", "background", "contorno contra o fundo (não textual)"),
    ("focus", "background", "anel de foco contra o fundo (não textual)"),
    ("sidebar", "background", "sidebar contra o fundo (não textual)"),
]
NONTEXT = {"border", "focus", "sidebar"}
REFERENCE = "org.steamzero.default"


def lum(hexs: str) -> float:
    h = hexs.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8):
        raise ValueError(hexs)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def load(path: str) -> dict:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def catalog(roots: list[tuple[str, pathlib.Path]]) -> dict[str, dict]:
    """theme.json por id, com a origem marcada; cadeia de extends resolvida depois."""
    out: dict[str, dict] = {}
    for label, root in roots:
        for f in sorted(glob.glob(str(root / "*" / "theme.json"))):
            try:
                d = load(f)
            except Exception as exc:  # tema importado por terceiros pode ser ilegível
                print(f"  ! {f}: {exc}")
                continue
            tid = d.get("id") or pathlib.Path(f).parent.name
            d["_arquivo"] = f
            d["_origem"] = label
            out.setdefault(tid, d)
    return out


def colors(cat: dict[str, dict], tid: str, seen: tuple[str, ...] = ()) -> dict[str, str]:
    """tokens.color com a cadeia `extends` resolvida (o tema vence o pai)."""
    d = cat.get(tid)
    if not d or tid in seen:
        return {}
    base = colors(cat, d.get("extends") or "", seen + (tid,))
    mine = (d.get("tokens") or {}).get("color") or {}
    base.update({k: v for k, v in mine.items() if isinstance(v, str)})
    return base


def amplitude() -> list[str]:
    """Tamanho da classe D-01 no QML: quem herda a cor de rótulo da paleta do pai."""
    qml = list((REL / "ui/qml").rglob("*.qml"))
    def count(pred) -> int:
        return sum(1 for f in qml for line in f.read_text(encoding="utf-8").splitlines() if pred(line))
    files = lambda pred: sorted({str(f.relative_to(REL)) for f in qml if pred(f.read_text(encoding="utf-8"))})
    dark = count(lambda l: "DarkButton {" in l)
    raw = count(lambda l: re_button.search(l) is not None)
    pal = count(lambda l: "palette.buttonText" in l)
    pal_files = files(lambda t: "palette.buttonText" in t)
    own = files(lambda t: "background:" in t)
    return [
        "## Amplitude da classe D-01 (medida no QML instalado)",
        f"  instâncias de DarkButton ................ {dark}",
        f"  instâncias de QQC.Button cru ............ {raw}",
        f"  bindings de palette.buttonText ......... {pal} em {len(pal_files)} arquivos",
        f"  arquivos que pintam background próprio  {len(own)} (esses escapam da classe)",
        "  mecanismo (ui/qml/DarkButton.qml:1-40): o componente é um QQC.Button **sem background**",
        "  próprio — só define `labelColor` a partir de `palette.buttonText` do pai, com fallback",
        "  `#16212a` (escuro) quando a paleta não traz cor. Quem pinta o fundo é o estilo, com a",
        "  estática medida (#FCFCFC habilitado / #E3E5E7 desabilitado). Tema escuro + estilo claro",
        "  = rótulo claro sobre fundo claro.",
    ]


def main() -> int:
    roots = [("pacote", REL / "themes"), ("host", HOST)]
    extra = os.environ.get("SZ_EXTRA_THEMES")
    if extra:
        roots.append(("extra", pathlib.Path(extra)))
    cat = catalog(roots)
    ref = colors(cat, REFERENCE)
    print("# Auditoria de cores — temas da release instalada e do catálogo do host")
    print(f"# pacote: {REL/'themes'} | host: {HOST}")
    print(f"# estáticas do estilo medidas em pixels (logs/06, harness/sz_contrast.py): "
          f"botão habilitado {STYLE_ENABLED}, desabilitado {STYLE_DISABLED}")
    print(f"# limiares WCAG 2.1 AA: 4,5:1 texto normal · 3:1 texto grande e elemento não textual")
    print(f"# referência de cobertura de tokens: {REFERENCE} ({len(ref)} chaves)")
    print()

    allfail: list[tuple[str, str, str, float]] = []
    for tid in sorted(cat):
        d = cat[tid]
        cs = colors(cat, tid)
        name = d.get("name", tid)
        print(f"## {tid} — “{name}” [{d['_origem']}] extends={d.get('extends') or '—'} tokens={len(cs)}")
        if not cs:
            print("   (sem tokens.color — tema de ativos/importado; nada a medir)")
            print()
            continue
        missing = sorted(set(ref) - set(cs))
        extra_keys = sorted(set(cs) - set(ref))
        bg = cs.get("background", ref.get("background", "#000000"))
        rows = []
        for tok, on, desc in PAIRS:
            a, b = cs.get(tok), cs.get(on)
            if not a or not b:
                rows.append((tok, on, None, desc, "sem token"))
                continue
            r = ratio(a, b)
            lim = 3.0 if tok in NONTEXT else 4.5
            rows.append((tok, on, r, desc, "ok" if r >= lim else f"REPROVADO (< {lim}:1)"))
            if r < lim:
                allfail.append((tid, f"{tok} sobre {on}", desc, r))
        for tok, on, r, desc, verdict in rows:
            if r is None:
                print(f"   {tok:14} vs {on:16} {'-':>7}  {verdict:16} {desc}")
            else:
                print(f"   {tok:14} vs {on:16} {r:6.2f}:1  {verdict:16} {desc}")
        print(f"   -- face do rótulo x estática do estilo (classe D-01) --")
        for tk in ("text", "textMuted", "textDisabled", "accent"):
            v = cs.get(tk)
            if not v:
                continue
            e, dis = ratio(v, STYLE_ENABLED), ratio(v, STYLE_DISABLED)
            print(f"   {tk:14} sobre {STYLE_ENABLED} (fundo real do botão) {e:6.2f}:1  "
                  f"{'ok' if e >= 4.5 else 'REPROVADO'}   | desabilitado {STYLE_DISABLED} {dis:6.2f}:1 "
                  f"{'ok' if dis >= 4.5 else 'REPROVADO'}")
            if e < 4.5:
                allfail.append((tid, f"{tk} {v} sobre {STYLE_ENABLED}", "rótulo pintado sobre a estática do estilo", e))
        print(f"   tokens ausentes vs {REFERENCE}: {', '.join(missing) or 'nenhum'}")
        if extra_keys:
            print(f"   tokens próprios (fora da referência): {', '.join(extra_keys)}")
        print()

    print("## Rollup de reprovações")
    print(f"  total: {len(allfail)}")
    per = {}
    for tid, par, _d, r in allfail:
        per.setdefault(tid, []).append((par, r))
    for tid, items in sorted(per.items(), key=lambda x: -len(x[1])):
        print(f"  {tid:34} {len(items):>3}  " + "; ".join(f"{p} {r:.2f}" for p, r in items[:6]))
    print()
    for line in amplitude():
        print(line)


if __name__ == "__main__":
    sys.exit(main())
