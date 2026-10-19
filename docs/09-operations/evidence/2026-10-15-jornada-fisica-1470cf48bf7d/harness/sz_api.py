#!/usr/bin/env python3
"""Cliente da ponte do Launcher para a bateria física.

Uso: SZ_API=http://127.0.0.1:9337 SZ_TOKEN=... sz_api.py <comando> [args]
  model                     -- resumo do estado atual da jornada
  event <json>              -- POST /journey/event (payload verbatim)
  session <g> <st> [overlay]  -- GET /session
  action <g> <st> <a>       -- POST /session/action
  launch <gameId>           -- POST /launch
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ["SZ_API"].rstrip("/")
TOKEN = os.environ["SZ_TOKEN"]


def _call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"X-SteamZero-Token": TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode("utf-8", "replace")}


def main() -> int:
    cmd = sys.argv[1]
    if cmd == "model":
        code, body = _call("GET", "/model")
        j = body.get("journey") or {}
        print(f"HTTP {code} menu={j.get('menuId')}/{j.get('menuName')} "
              f"total={j.get('totalCount')} result={j.get('resultCount')} gen={j.get('generation')} "
              f"filters={json.dumps(j.get('filters'), ensure_ascii=False)} "
              f"selected={j.get('selectedItemId')} focus={j.get('focusId')} scroll={j.get('scrollPosition')} "
              f"theme={(j.get('theme') or {}).get('requestedThemeId')}/"
              f"{((j.get('theme') or {}).get('color') or {}).get('background')} "
              f"active={j.get('active')} journeyId={j.get('journeyId')} "
              f"events={j.get('availableEvents')} caps={json.dumps(j.get('sessionCapabilities'), ensure_ascii=False)}")
        for item in (j.get("items") or [])[:6]:
            print("  item:", json.dumps({k: item[k] for k in ("id", "title", "subtitle", "kind", "gameId") if k in item},
                                        ensure_ascii=False))
        return 0
    if cmd == "event":
        code, body = _call("POST", "/journey/event", json.loads(sys.argv[2]))
    elif cmd == "session":
        gid, stage = sys.argv[2], sys.argv[3]
        overlay = "1" if len(sys.argv) < 5 or sys.argv[4] == "1" else "0"
        code, body = _call("GET", f"/session?gameId={gid}&stage={stage}&overlay={overlay}")
    elif cmd == "action":
        # POST /session/action exige gameId, sessionId, actionId, requestId.
        code, body = _call("POST", "/session/action", {
            "requestId": os.environ.get("SZ_RID", "evidence-action"),
            "gameId": sys.argv[2],
            "sessionId": sys.argv[3],
            "actionId": sys.argv[4],
            "confirmed": (len(sys.argv) > 5 and sys.argv[5] == "confirm"),
        })
    elif cmd == "launch":
        code, body = _call("POST", "/launch", {
            "gameId": sys.argv[2],
            "focusId": (sys.argv[3] if len(sys.argv) > 3 else ""),
        })
    else:
        print("comando desconhecido", cmd, file=sys.stderr)
        return 2
    print(f"HTTP {code}")
    dest = os.environ.get("SZ_OUT")
    if dest:
        with open(dest, "w", encoding="utf-8") as handle:
            json.dump({"http": code, "body": body}, handle, ensure_ascii=False, indent=1)
        print(f"json: {dest}")
    print(json.dumps(body, ensure_ascii=False, indent=1)[: int(os.environ.get("SZ_PRINT", "4000"))])
    return 0


if __name__ == "__main__":
    sys.exit(main())
