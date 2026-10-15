"""sz_press_visible.py — como sz_press, mas escolhe o primeiro nó com o nome
EXATO que esteja VISIBLE+SHOWING (a Central mantém páginas empilhadas na mesma
janela; o primeiro 'Desfazer' da árvore é um item de histórico oculto).

Uso: sz_press_visible.py <uuid-janela> <nome-exato> [keycode] [pid]
Aborta sem injetar se a janela ativa divergir (rc=3) ou o foco falhar (rc=4).
"""
import os, subprocess, sys, time, gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

uuid, want = sys.argv[1], sys.argv[2]
code = sys.argv[3] if len(sys.argv) > 3 else "57"
YDOTOOL = os.environ.get("YDOTOOL", "/home/misael/.local/bin/ydotool")
env = dict(os.environ, YDOTOOL_SOCKET="/tmp/.ydotool_socket")

def active():
    return subprocess.run(["kdotool", "getactivewindow"], capture_output=True,
                          text=True).stdout.strip()

def _pid(acc):
    p = acc.get_process_id()
    if isinstance(p, tuple):
        return next((int(x) for x in p if int(x) > 1), 0)
    return int(p)

want_pid = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
app = None
d = Atspi.get_desktop(0)
for i in range(d.get_child_count()):
    a = d.get_child_at_index(i)
    try:
        nm = a.get_name() or ""
        pid = _pid(a)
    except Exception:
        continue
    if "qml" not in nm.lower():
        continue
    if want_pid is not None and pid != want_pid:
        continue
    app = a
    break
if app is None:
    print("fail|app"); sys.exit(2)

hits = []
def walk(o, depth=0):
    if depth > 60:
        return
    try:
        if (o.get_name() or "") == want:
            hits.append(o)
        n = o.get_child_count()
    except Exception:
        return
    for k in range(n):
        c = o.get_child_at_index(k)
        if c is not None:
            walk(c, depth + 1)

walk(app)
hit = None
for o in hits:
    try:
        s = o.get_state_set()
    except Exception:
        continue
    if s.contains(Atspi.StateType.SHOWING) and s.contains(Atspi.StateType.VISIBLE):
        hit = o
        break
if hit is None:
    print("fail|%r ausente ou não-showing (%d hits)" % (want, len(hits))); sys.exit(1)

subprocess.run(["kdotool", "windowactivate", uuid], capture_output=True)
time.sleep(0.5)
if active() != uuid:
    print("fail|janela ativa %s" % active()); sys.exit(3)
try:
    hit.grab_focus()
except Exception as e:
    print("fail|grab_focus %s" % e); sys.exit(1)
time.sleep(0.15)
if not hit.get_state_set().contains(Atspi.StateType.FOCUSED):
    print("fail|nao focado"); sys.exit(4)
if active() != uuid:
    print("fail|janela ativa mudou para %s" % active()); sys.exit(3)
subprocess.run([YDOTOOL, "key", f"{code}:1", f"{code}:0"], env=env, capture_output=True)
print("ok|%s|%s" % (hit.get_role_name(), want))
