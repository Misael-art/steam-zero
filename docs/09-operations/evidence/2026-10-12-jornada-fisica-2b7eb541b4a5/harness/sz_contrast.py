"""Mede contraste real em pixels de um elemento acessível numa captura.

Uso: sz_contrast.py <png> <uuid-janela> <nome> [<nome> ...]
Fundo = luminância do p90 da caixa; texto = p2 (traço mais escuro/claro).
WCAG AA para texto normal exige 4,5:1; para texto grande 3:1.
"""
import re, subprocess, sys, gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi
from PIL import Image

png, uuid = sys.argv[1], sys.argv[2]
names = sys.argv[3:]
out = subprocess.run(["kdotool", "getwindowgeometry", uuid], capture_output=True, text=True).stdout
pos = re.search(r"Position:\s*(-?\d+),(-?\d+)", out)
ox, oy = (int(pos.group(1)), int(pos.group(2))) if pos else (0, 0)

d = Atspi.get_desktop(0)
app = None
for i in range(d.get_child_count()):
    a = d.get_child_at_index(i)
    try:
        nm = a.get_name() or ""
    except Exception:
        continue
    if "qml" in nm.lower():
        app = a
        break

def find(want):
    """Retorna a primeira caixa homônima visível na captura (há nomes repetidos
    na árvore: o catálogo de temas fica montado atrás do estúdio)."""
    hits = []
    def walk(o, depth=0):
        if depth > 24:
            return
        try:
            if (o.get_name() or "") == want:
                e = o.get_extents(Atspi.CoordType.SCREEN)
                hits.append((e.x, e.y, e.width, e.height,
                             o.get_state_set().contains(Atspi.StateType.ENABLED)))
            else:
                n = o.get_child_count()
        except Exception:
            return
        for k in range(o.get_child_count()):
            c = o.get_child_at_index(k)
            if c is not None:
                walk(c, depth + 1)
    walk(app)
    for r in hits:
        if r[2] > 8 and r[3] > 8:
            return r
    return hits[0] if hits else None

def L(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v / 255) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

im = Image.open(png).convert("RGB")
W, H = im.size
for want in names:
    r = find(want)
    if not r:
        print(f"{want!r}: AUSENTE na árvore"); continue
    x, y, w, h, enabled = r
    lx, ly = x - ox, y - oy
    if lx < 0 or ly < 0 or lx + w > W or ly + h > H or w <= 4 or h <= 4:
        print(f"{want!r}: caixa fora da captura ({lx},{ly} {w}x{h} de {W}x{H})"); continue
    px = list(im.crop((lx, ly, lx + w, ly + h)).getdata())
    modal = max(set(px), key=px.count)
    ls = sorted(L(c) for c in px)
    n = len(ls)
    bg, txt = ls[int(n * 0.90)], ls[int(n * 0.02)]
    hi, lo = max(bg, txt), min(bg, txt)
    ratio = (hi + 0.05) / (lo + 0.05)
    verdict = "AA-ok" if ratio >= 4.5 else ("grande-ok" if ratio >= 3.0 else "REPROVADO")
    print(f"{want!r}: caixa=({lx},{ly},{w}x{h}) hab={enabled} "
          f"fundo=#{modal[0]:02X}{modal[1]:02X}{modal[2]:02X} "
          f"contraste={ratio:.2f}:1 {verdict}")
