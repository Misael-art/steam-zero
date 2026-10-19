#!/usr/bin/env python3
"""Estados acessíveis dos controles do Launcher (prova de habilitação real).

Percorre a árvore AT-SPI do processo informado e imprime nome, papel e os
estados de cada botão — é a resposta à pergunta "o controle está habilitado?",
independente da cor renderizada.
"""
from __future__ import annotations

import sys

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

WANT = sys.argv[1] if len(sys.argv) > 1 else ""
PID = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 0


def _pid(acc) -> int:
    p = acc.get_process_id()
    if isinstance(p, tuple):
        return next((int(x) for x in p if int(x) > 1), 0)
    return int(p)


def walk(node, depth=0):
    try:
        role = node.get_role_name()
        name = node.get_name() or ""
    except Exception:  # noqa: BLE001
        return
    if role in {"button", "push button", "toggle button", "combo box", "list item", "label"}:
        states = node.get_state_set()
        flags = [
            s for s in ("ENABLED", "SENSITIVE", "VISIBLE", "SHOWING", "FOCUSABLE",
                        "FOCUSED", "SELECTED", "CHECKED", "BUSY")
            if states.contains(getattr(Atspi.StateType, s))
        ]
        if not WANT or WANT.lower() in name.lower():
            print(f"{'  '*depth}{role}|{name[:60]}|{','.join(flags)}")
    for i in range(node.get_child_count()):
        child = node.get_child_at_index(i)
        if child is not None:
            walk(child, depth + 1)


def main() -> int:
    Atspi.init()
    desktop = Atspi.get_desktop(0)
    found = False
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app is None:
            continue
        if PID and _pid(app) != PID:
            continue
        if not PID and "qml" not in (app.get_name() or "").lower():
            continue
        found = True
        walk(app)
    if not found:
        print("app não encontrado", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
