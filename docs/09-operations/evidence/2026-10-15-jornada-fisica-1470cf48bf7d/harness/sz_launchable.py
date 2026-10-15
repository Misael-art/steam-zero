#!/usr/bin/env python3
"""Prova o portão de lançamento da release instalada, sem spawn.

Motivo: o Launcher exibe os 1163 itens do cache, mas o portão de lançamento
(``EmulationController._current_game``) só conhece os itens que sobrevivem à
revalidação de ``_load_library_cache``. Este probe chama o próprio método do
produto (não uma reimplementação) e publica, por sistema, o que é lançável —
evidência para D-09.

Somente leitura: o ``spawn`` injetado aborta se alguém tentar iniciar processo.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from steamzero.adapters.emulation import EmulationController

CACHE = Path.home() / ".local/share/steamzero/emulation-library-cache-v1.json"


def _no_spawn(argv, *args, **kwargs):  # noqa: ANN001, ARG001
    raise AssertionError(f"probe tentou iniciar processo: {argv!r}")


def main() -> int:
    controller = EmulationController(spawn=_no_spawn)
    valid, unidentified = controller._load_library_cache()  # noqa: SLF001
    cache = json.loads(CACHE.read_text()).get("games") or []
    ids = {str(g.get("id")) for g in valid}
    dropped = [g for g in cache if str(g.get("id")) not in ids]
    print(f"cache={len(cache)} lançáveis={len(valid)} não lançáveis={len(dropped)} "
          f"unidentified={unidentified}")
    print("\n## não lançáveis (navegáveis no Launcher, recusados pelo portão)")
    detail = []
    for g in sorted(dropped, key=lambda x: (str(x.get("platform")), str(x.get("name")))):
        row = {
            "id": g.get("id"), "name": g.get("name"), "platform": g.get("platform"),
            "format": g.get("format"), "path": g.get("path"),
            "evidence": g.get("evidence"), "contentKind": g.get("contentKind"),
            "titleId": g.get("titleId"), "identityScheme": g.get("identityScheme"),
        }
        detail.append(row)
        print(f"  {str(row['platform']):22s} [{str(row['format']):10s}] {str(row['name'])[:52]:54s} ev={row['evidence']}")
    print("\n## lançáveis por sistema (1 exemplo cada)")
    by_valid = collections.defaultdict(list)
    for g in valid:
        by_valid[str(g.get("platformId") or g.get("platform"))].append(g)
    for plat in sorted(by_valid, key=lambda p: -len(by_valid[p])):
        gs = sorted(by_valid[plat], key=lambda g: str(g["name"]))
        fmts = collections.Counter(str(g.get("format")) for g in gs)
        sample = gs[0]
        print(f"  {plat:22s} n={len(gs):4d} formatos={dict(fmts)}")
        print(f"      ex.: {sample['id']}  {str(sample['name'])[:52]}  .{sample.get('format')}")
    out = {
        "cache": len(cache),
        "launchable": len(valid),
        "not_launchable": len(dropped),
        "unidentified": unidentified,
        "by_platform": {
            p: [{"id": g["id"], "name": g["name"], "format": g.get("format"),
                 "path": g.get("path")} for g in sorted(by_valid[p], key=lambda x: str(x["name"]))]
            for p in by_valid
        },
        "not_launchable_detail": detail,
    }
    dest = Path(__file__).resolve().parent.parent / "logs/json/library-launchable.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\njson: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
