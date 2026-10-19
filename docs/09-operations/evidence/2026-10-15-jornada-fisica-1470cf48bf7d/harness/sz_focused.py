"""Imprime o objeto FOCUSED do app SteamZero (ou NONE). Uso: sz_focused.py [pid]

Há dois processos `qml6` no desktop (central e Launcher); sem filtro o primeiro
da lista do AT-SPI vence e o resultado é um NONE que não diz nada. Com pid, a
consulta é feita só no app visado.
"""
import sys, gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

def _pid(acc):
    p = acc.get_process_id()
    if isinstance(p, tuple):
        return next((int(x) for x in p if int(x) > 1), 0)
    return int(p)

want_pid = int(sys.argv[1]) if len(sys.argv) > 1 else None

d = Atspi.get_desktop(0)
for i in range(d.get_child_count()):
    app = d.get_child_at_index(i)
    try:
        nm = app.get_name()
        pid = _pid(app)
    except Exception:
        continue
    if not nm or "qml" not in nm.lower():
        continue
    if want_pid is not None and pid != want_pid:
        continue
    found = []

    def walk(o, depth=0):
        if len(found) or depth > 16:
            return
        try:
            s = o.get_state_set()
            if s.contains(Atspi.StateType.FOCUSED):
                found.append((o.get_role_name(), o.get_name()))
                return
            n = o.get_child_count()
        except Exception:
            return
        for k in range(n):
            c = o.get_child_at_index(k)
            if c is not None:
                walk(c, depth + 1)

    walk(app)
    if found:
        print(f"{found[0][0]}|{found[0][1]}")
        sys.exit(0)
if want_pid is not None:
    print("NONE|")
else:
    print("NOAPP|")
