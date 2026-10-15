#!/usr/bin/env python3
"""Diagnóstico de lançamento por sistema, sem efeito.

Usa ``EmulationController.game_readiness``, que a própria release documenta
como leitor EXATO das pré-condições de ``launch_game`` (``_launch_preflight``)
sem iniciar nada. Um jogo por sistema lançável + todos os não lançáveis.

``spawn`` injetado aborta: este probe não pode iniciar processo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from steamzero.adapters.emulation import EmulationController

EV = Path(__file__).resolve().parent.parent
LAUNCHABLE = EV / "logs/json/library-launchable.json"


def _no_spawn(argv, *args, **kwargs):  # noqa: ANN001, ARG001
    raise AssertionError(f"probe tentou iniciar processo: {argv!r}")


def main() -> int:
    data = json.loads(LAUNCHABLE.read_text())
    controller = EmulationController(spawn=_no_spawn)
    rows = []
    by_platform = data["by_platform"]
    print(f"# readiness por sistema — {len(by_platform)} sistemas, 1 jogo cada")
    for platform in sorted(by_platform, key=lambda p: -len(by_platform[p])):
        for game in by_platform[platform][:1]:
            try:
                verdict = controller.game_readiness(game["id"])
            except AssertionError:
                raise
            except Exception as exc:  # noqa: BLE001
                verdict = {"playable": None, "code": f"probe-erro:{type(exc).__name__}",
                           "reason": str(exc)[:160]}
            row = {
                "platform": platform, "gameId": game["id"], "name": game["name"],
                "format": game.get("format"), "path": game.get("path"),
                "verdict": verdict,
            }
            rows.append(row)
            print(f"{platform:22s} playable={str(verdict.get('playable')):5s} "
                  f"code={str(verdict.get('code')):26s} "
                  f"canPrepare={str(verdict.get('canPrepare')):5s} "
                  f"reason={str(verdict.get('reason'))[:96]}")
    print("\n# readiness dos NÃO lançáveis (contraste)")
    for game in data["not_launchable_detail"]:
        try:
            verdict = controller.game_readiness(game["id"])
        except AssertionError:
            raise
        except Exception as exc:  # noqa: BLE001
            verdict = {"playable": None, "code": f"probe-erro:{type(exc).__name__}",
                       "reason": str(exc)[:160]}
        rows.append({"platform": game.get("platform"), "gameId": game.get("id"),
                     "name": game.get("name"), "format": game.get("format"),
                     "path": game.get("path"), "verdict": verdict,
                     "set": "nao-lancavel"})
        print(f"{str(game.get('platform')):22s} [{str(game.get('format')):8s}] "
              f"playable={str(verdict.get('playable')):5s} code={str(verdict.get('code')):24s} "
              f"canPrepare={str(verdict.get('canPrepare')):5s} reason={str(verdict.get('reason'))[:80]}")
    dest = EV / "logs/json/readiness-by-system.json"
    dest.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"\njson: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
