"""Posiciona o foco acessível num elemento do SteamZero (não injeta input).
Uso: sz_grab.py <nome-ou-description> [pid]   -> ok|<role>|<name> ou fail|<motivo>
Há dois processos qml6 no desktop; com pid a busca é restrita ao app visado.
A ativação em si continua sendo tecla real enviada pelo harness."""
import sys, gi
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

want = sys.argv[1]
def _pid(acc):
    p = acc.get_process_id()
    if isinstance(p, tuple):
        return next((int(x) for x in p if int(x) > 1), 0)
    return int(p)

want_pid = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
d = Atspi.get_desktop(0)
app = None
for i in range(d.get_child_count()):
    a = d.get_child_at_index(i)
    try:
        nm = a.get_name()
        pid = _pid(a)
    except Exception:
        continue
    if not nm or "qml" not in nm.lower():
        continue
    if want_pid is not None and pid != want_pid:
        continue
    app = a
    break
if app is None:
    print("fail|app nao encontrado"); sys.exit(2)

hits = []
def walk(o, depth=0):
    if len(hits) > 3 or depth > 24:
        return
    try:
        n = o.get_name() or ""
        desc = ""
        try:
            desc = o.get_description() or ""
        except Exception:
            pass
    except Exception:
        return
    role = o.get_role_name()
    if (want in n or want in desc) and role in ("push button","button","page tab","check box","combo box","link","text","text field","text editor","slider"):
        hits.append(o)
        return
    try:
        cnt = o.get_child_count()
    except Exception:
        return
    for k in range(cnt):
        c = o.get_child_at_index(k)
        if c is not None:
            walk(c, depth + 1)

walk(app)
if not hits:
    print("fail|nenhum elemento com %r" % want); sys.exit(1)
o = hits[0]
try:
    comp = o.get_component_iface() if hasattr(o, "get_component_iface") else o
except Exception:
    pass
try:
    o.grab_focus()
except Exception as e:
    print("fail|grab_focus %s" % e); sys.exit(1)
import time
time.sleep(0.25)
try:
    ok = o.get_state_set().contains(Atspi.StateType.FOCUSED)
except Exception:
    ok = False
print(("ok" if ok else "fail") + "|" + o.get_role_name() + "|" + o.get_name())
