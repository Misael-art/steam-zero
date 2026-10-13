#!/usr/bin/env python3
"""Censo de controles da UI x fiao de backend (somente leitura, AST exato).

Quatro eixos, todos contra a MESMA release instalada (2.0.0rc1-2b7eb541b4a5):

  A  registro de contratos da central (desktop_contracts.py: 154 chamadas _action)
     -> endpoint publicado? metodo? enabled/applicable/reason declarados?
     -> a rota existe no verbo correspondente em desktop_ui.py (POST _dispatch / GET do_GET)?

  B  catalogo de acoes de emulacao (emulation.py + emulation_workspace.py, chamadas _action)
     -> para cada id publicado, ha porta? portas = ramos de plan_action (igualdade, conjunto,
        prefixo startswith) ou ramo local tratado no Main.qml
     -> e, ao contrario, ids aceitos pelo backend que nenhum catalogo publica

  C  agoes do OSD de sessao (read-models capturados em logs/json/*.json)
     -> ids publicados x ids aceitos por session_control.py, com o motivo literal do produto

  D  arvore AT-SPI arquivada (logs/17-*.txt)
     -> classe de estado de cada controle acionavel e se o nome dele aparece como string no QML

Metodo: AST (ast.parse/ast.walk) para as chamadas _action e para os ramos de plan_action;
regex apenas para as rotas `path == "..."` e para literais do QML. Nada e escrito fora de
logs/json/censo-controles-backend.json. Fiao estatica: nao prova execucao nem runtime.
"""

from __future__ import annotations

import ast
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path.cwd()
EVID = "docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5"
DUMP = f"{EVID}/logs/17-arvore-atspi-central-pos-bateria.txt"
QML_ROOT = "src/steamzero/ui/qml"
CONTRACTS = "src/steamzero/adapters/desktop_contracts.py"
DESKTOP = "src/steamzero/adapters/desktop_ui.py"
EMULATION = "src/steamzero/adapters/emulation.py"
WORKSPACE = "src/steamzero/domain/emulation_workspace.py"
SESSION = "src/steamzero/adapters/session_control.py"

ACTIONABLE = {"button", "combo box", "check box", "slider", "toggle button", "list item", "spin button", "link"}
LIT = re.compile(r'"([a-z][a-z0-9_]*(?:\.[a-z0-9_-]+)+)"')


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def kwof(call: ast.Call) -> dict[str, object]:
    out: dict[str, object] = {}
    for kw in call.keywords:
        v = kw.value
        if isinstance(v, ast.Constant):
            out[kw.arg] = v.value
        elif isinstance(v, ast.Constant) is False and kw.arg == "schema":
            out[kw.arg] = "<schema>"
        else:
            out[kw.arg] = "EXPR:" + ast.unparse(v)[:60]
    return out


def action_calls(rel: str) -> list[dict[str, object]]:
    """Toda chamada `_action(id, ...)`, inclusive `self._action(...)`.

    Quando o id e uma expressao (ternario, f-string), `candidatos` contem as strings
    literais dentro da expressao e `prefixos` os prefijos de template (ex. `game.media.import:`).
    """
    rows: list[dict[str, object]] = []
    for node in ast.walk(ast.parse(text(rel))):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        if name != "_action" or not node.args:
            continue
        first = node.args[0]
        kind = "literal"
        cands: list[str] = []
        prefs: list[str] = []
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            cands = [first.value]
        else:
            kind = "dinamico"
            cands = [c.value for c in ast.walk(first) if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            for c in ast.walk(first):
                if isinstance(c, ast.JoinedStr):
                    # prefixo literal do template: concatena as partes ate o primeiro buraco
                    head = ""
                    for part in c.values:
                        if isinstance(part, ast.Constant) and isinstance(part.value, str):
                            head += part.value
                        else:
                            break
                    if head:
                        prefs.append(head)
        aid = cands[0] if cands else "<sem literal>"
        label = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else ""
        row = {"id": aid, "kind": kind, "candidatos": cands, "prefixos": prefs,
               "label": label, "line": node.lineno, "file": rel.split("/")[-1]}
        # desktop_contracts._action(id, rotulo, endpoint, ...) — endpoint posicional
        if len(node.args) > 2:
            a2 = node.args[2]
            row["endpoint"] = None if isinstance(a2, ast.Constant) and a2.value is None else (
                a2.value if isinstance(a2, ast.Constant) else "EXPR:" + ast.unparse(a2)[:40])
        row.update(kwof(node))
        rows.append(row)
    return rows


def plan_action_doors(rel: str) -> tuple[set[str], set[str], set[str]]:
    """Ids aceitos por plan_action: igualdade, conjunto/lista, prefixo startswith."""
    tree = ast.parse(text(rel))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "plan_action")
    exact: set[str] = set()
    starts: set[str] = set()
    dyn: set[str] = set()

    def left_name(node) -> bool:
        if isinstance(node, ast.Name) and node.id == "action":
            return True
        # action_id vem de payload em alguns ramos; trata como dinamico
        return False

    for node in ast.walk(fn):
        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators, strict=False):
                if not left_name(node.left):
                    if isinstance(node.left, ast.Attribute) and getattr(node.left.value, "id", "") == "action":
                        pass
                    continue
                if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                    exact.add(comp.value)
                elif isinstance(op, ast.In) and isinstance(comp, (ast.Set, ast.List, ast.Tuple)):
                    exact |= {e.value for e in comp.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                elif isinstance(op, ast.In):
                    dyn.add("in " + ast.unparse(comp)[:50])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("startswith", "indexOf"):
            owner = node.func.value
            if (isinstance(owner, ast.Name) and owner.id == "action") or (isinstance(owner, ast.Attribute) and getattr(owner.value, "id", "") == "action"):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    starts.add(node.args[0].value)
                else:
                    dyn.add("startswith " + ast.unparse(owner)[:40])
            elif isinstance(owner, ast.Constant):
                dyn.add("list.indexOf " + str(owner.value)[:40])
    return exact, starts, dyn


def routes(rel: str) -> tuple[set[str], set[str]]:
    t = text(rel)
    post = set(re.findall(r'path == "([^"]+)"', t[t.index("def _dispatch("):]))
    get = set(re.findall(r'path == "([^"]+)"', t[t.index("def do_GET(") : t.index("def do_POST(")]))
    return post - get, get


def qml_index() -> tuple[dict[str, list[str]], set[str]]:
    qml = {str(f.relative_to(ROOT)): f.read_text(encoding="utf-8").splitlines() for f in sorted((ROOT / QML_ROOT).rglob("*.qml"))}
    body = "\n".join("".join(lines) for lines in qml.values())
    return qml, {m for m in LIT.findall("\n".join("".join(l) for l in qml.values())) if "." in m}


def atspi_rows() -> list[dict[str, str]]:
    out = []
    for raw in text(DUMP).splitlines():
        if "|" not in raw:
            continue
        parts = raw.strip().split("|")
        role = parts[0]
        states = parts[-1] if parts[-1].replace(",", "").isupper() else ""
        name = ("|".join(parts[1:-1]) if states else "|".join(parts[1:])).strip().rstrip("|")
        if role in ACTIONABLE and name:
            out.append({"role": role, "name": name, "states": states})
    return out


def state_class(states: str) -> str:
    if "VISIBLE" in states and "SHOWING" in states:
        return "visivel"
    if "VISIBLE" in states or "SHOWING" in states:
        return "parcial"
    return "invisivel-acionavel" if "ENABLED" in states else "invisivel-inerte"


def main() -> int:
    report: dict[str, object] = {}

    # ---------------- eixo A: registro da central
    contracts = action_calls(CONTRACTS)
    post, get = routes(DESKTOP)
    a_rows = []
    for c in contracts:
        ep, method = c.get("endpoint"), c.get("method", "POST")
        if ep is None:
            classe = "SEM_ENDPOINT"
        elif method == "GET":
            classe = "PORTA_GET" if ep in get else "ROTA_AUSENTE_NO_GET"
        else:
            classe = "PORTA_POST" if ep in post else "ROTA_AUSENTE_NO_POST"
        a_rows.append({"id": c["id"], "rotulo": c["label"], "classe": classe, "rota": ep, "metodo": method,
                       "enabled": c.get("enabled", True), "applicable": c.get("applicable", True),
                       "reason": c.get("reason", ""), "confirmacao": c.get("confirmation", "none"),
                       "tela": c.get("screen", ""), "controle": c.get("control", ""), "linha": c["line"]})
    a_counts = collections.Counter(r["classe"] for r in a_rows)
    report["A_registro"] = {"total": len(a_rows), "rollup": dict(a_counts),
                            "sem_endpoint": [r for r in a_rows if r["classe"] == "SEM_ENDPOINT"],
                            "sem_porta": [r for r in a_rows if r["classe"].startswith("ROTA_AUSENTE")]}

    # ---------------- eixo B: catalogo de emulacao
    pub = action_calls(EMULATION) + action_calls(WORKSPACE)
    exact, starts, dyn = plan_action_doors(EMULATION)
    qml_map, qml_ids = qml_index()
    main_qml = "\n".join(qml_map[f"{QML_ROOT}/Main.qml"])
    treated = set(re.findall(r'action\.id === "([^"]+)"', main_qml)) | set(LIT.findall(main_qml[main_qml.index('"library.root.add", "keys.import"') :][:1200])) | {"emulation.refresh", "requirements.verify", "library.scan", "open-credential-dialog"}
    qml_prefixes = set(re.findall(r'action\.id\.indexOf\("([^"]+)"\) === 0', main_qml))

    def match(aid: str) -> str:
        if aid in exact:
            return "plan_action:igualdade"
        if any(aid.startswith(p) for p in starts):
            return "plan_action:prefixo"
        if aid in treated or any(aid.startswith(p) for p in qml_prefixes):
            return "ramo no Main.qml"
        return ""

    def door(p) -> tuple[str, str]:
        """(classe, detalhe) — SIM / INDIRETA / NAO."""
        ach = {a: match(a) for a in p["candidatos"] if match(a)}
        if ach:
            return "SIM", "; ".join(f"{a}->{v}" for a, v in sorted(ach.items()))
        pref = {pf: match(pf) or ("Main.qml" if any(pf.startswith(q) or q.startswith(pf) for q in qml_prefixes | starts) else "")
                for pf in p["prefixos"]}
        achp = {k: v for k, v in pref.items() if v}
        if achp:
            return "SIM", "; ".join(f"{k}*->{v}" for k, v in sorted(achp.items()))
        if p["kind"] == "dinamico":
            # o id e montado a partir de variavel (ex. f"{action_prefix}.backup:{game_id}"):
            # a porta existe para algum prefixo, mas nao e resolvidivel estaticamente
            return "INDIRETA", "prefixo do id vem de variavel: " + ", ".join(p["candidatos"][:3])
        return "NAO", ""

    b_rows = []
    for p in pub:
        cls, det = door(p)
        b_rows.append({"id": p["id"], "kind": p["kind"], "candidatos": p["candidatos"], "templates": p["prefixos"],
                       "label": p["label"], "file": p["file"], "linha": p["line"],
                       "enabled": p.get("enabled", True), "reason": p.get("reason"),
                       "porta": det or "NENHUMA", "classe_porta": cls})
    b_rows.sort(key=lambda r: r["id"])
    no_door = [r for r in b_rows if r["classe_porta"] == "NAO"]
    indireta = [r for r in b_rows if r["classe_porta"] == "INDIRETA"]
    declaradas = [r for r in b_rows if r["enabled"] is False]
    por_id = collections.defaultdict(set)
    for r in b_rows:
        por_id[r["id"]].add(str(r["enabled"]))
    contradit = {k: sorted(v) for k, v in por_id.items() if len(v) > 1}
    publicados_ids = {c for r in b_rows for c in r["candidatos"]}
    templates = [t for r in b_rows for t in r["templates"]]
    nunca = sorted(a for a in exact if a not in publicados_ids and not any(a.startswith(t) or t.startswith(a) for t in templates))
    report["B_emulacao"] = {"publicacoes": len(b_rows), "ids_distintos": len(por_id),
                            "rollup_porta": dict(collections.Counter(r["classe_porta"] for r in b_rows)),
                            "aceitos_plan_action": len(exact), "prefixos_plan_action": sorted(starts),
                            "prefixos_main_qml": sorted(qml_prefixes),
                            "ramos_dinamicos": sorted(dyn),
                            "sem_porta": no_door, "porta_indireta": indireta,
                            "enabled_false": declaradas,
                            "enabled_contraditorio": contradit, "aceitos_nunca_publicados": nunca}

    # ---------------- eixo C: OSD de sessao x backend
    sess = text(SESSION)
    seg = sess.split("if action not in {")[-1].split("}:")[0]
    accepted = set(re.findall(r'"([A-Za-z][A-Za-z]+)"', seg))
    osd: dict[str, dict[str, object]] = {}
    for p in sorted((ROOT / EVID / "logs/json").glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        stack = [doc]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for a in o.get("actions") or []:
                    if isinstance(a, dict) and a.get("id"):
                        e = osd.setdefault(str(a["id"]), {"hab": 0, "desab": 0, "motivos": set(), "amostras": []})
                        e["hab" if a.get("enabled") is True else "desab"] += 1
                        m = a.get("reason") or a.get("disabledReason")
                        if m:
                            e["motivos"].add(str(m))
                        e["amostras"].append(p.name)
                stack.extend(v for v in o.values() if isinstance(v, (dict, list)))
            elif isinstance(o, list):
                stack.extend(v for v in o if isinstance(v, (dict, list)))
    c_rows = [{"id": a, "hab": e["hab"], "desab": e["desab"], "aceita_no_backend": a in accepted,
               "motivos": sorted(e["motivos"]), "amostras": len(e["amostras"])} for a, e in osd.items()]
    c_rows.sort(key=lambda r: (-r["hab"], r["id"]))
    report["C_sessao"] = {"read_models": len(list((ROOT / EVID / "logs/json").glob("*.json"))),
                          "aceitos_backend": sorted(accepted), "acoes": c_rows,
                          "publicadas_sem_backend": sorted(r["id"] for r in c_rows if not r["aceita_no_backend"]),
                          "aceitas_nunca_publicadas": sorted(accepted - set(osd))}

    # ---------------- eixo D: AT-SPI x QML
    rows, seen = [], set()
    exact_lit: dict[str, list[str]] = collections.defaultdict(list)
    for path, lines in qml_map.items():
        for i, line in enumerate(lines):
            for lit in re.findall(r'qsTr\("([^"]*)"', line) + re.findall(r'=\s*"([^"]{3,})"', line) + re.findall(r"`([^`$]{3,})`", line):
                exact_lit[lit].append(path.split("/")[-1])
    for n in atspi_rows():
        key = (n["role"], n["name"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({"papel": n["role"], "nome": n["name"], "estado": state_class(n["states"]),
                     "no_qml": bool(exact_lit.get(n["name"])),
                     "qml": sorted(set(exact_lit.get(n["name"], [])))[:4],
                     "no_registro": bool([c for c in a_rows if c["rotulo"] == n["name"]])})
    d_estado = collections.Counter(r["estado"] for r in rows)
    report["D_atspi"] = {"acionaveis_dedup": len(rows), "estados": dict(d_estado),
                         "sem_nome_no_qml": sum(1 for r in rows if not r["no_qml"]),
                         "invisivel_acionavel": [f'{r["papel"]} · {r["nome"]}' for r in rows if r["estado"] == "invisivel-acionavel"][:80]}

    out = ROOT / EVID / "logs/json/censo-controles-backend.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ---------------- impressao
    def sec(t: str) -> None:
        print(f"\n## {t}")

    print("# Censo de controles da UI x backend (AST exato, somente leitura)")
    print(f"# release: 2.0.0rc1-2b7eb541b4a5 | fontes: {CONTRACTS}, {DESKTOP}, {EMULATION},")
    print(f"#          {WORKSPACE}, {SESSION}, {QML_ROOT}, {DUMP}, {EVID}/logs/json/*.json")
    print(f"#POST _dispatch={len(post)}  GET do_GET={len(get)}  plan_action exatos={len(exact)}  prefixos={len(starts)}")

    sec("Eixo A — registro de contratos da central")
    for k, v in a_counts.most_common():
        print(f"  {k:22} {v}")
    print(f"\n  contratos sem endpoint (o proprio produto diz por que):")
    for r in report["A_registro"]["sem_endpoint"]:
        print(f"    {r['id']:26} enabled={r['enabled']} applicable={r['applicable']} tela={r['tela']:14} {str(r['reason'])[:104]}")
    if report["A_registro"]["sem_porta"]:
        print("  contratos com rota ausente no verbo declarado:")
        for r in report["A_registro"]["sem_porta"]:
            print(f"    {r['id']:26} {r['metodo']} {r['rota']}")
    else:
        print(f"  contratos com rota ausente no verbo declarado: {len(report['A_registro']['sem_porta'])} de {a_counts['PORTA_POST'] + a_counts['PORTA_GET']} com endpoint")

    sec("Eixo B — catalogo de acoes de emulacao")
    print(f"  publicacoes={report['B_emulacao']['publicacoes']} ids={report['B_emulacao']['ids_distintos']} aceitos por plan_action={len(exact)}")
    print(f"  rollup de porta: {report['B_emulacao']['rollup_porta']}")
    print(f"  prefixos aceitos no plan_action: {report['B_emulacao']['prefixos_plan_action']}")
    print(f"  prefixos tratados no Main.qml: {report['B_emulacao']['prefixos_main_qml']}")
    print(f"  publicados SEM porta ({len(no_door)}):")
    for r in no_door:
        print(f"    {r['id']:44} enabled={str(r['enabled'])[:26]:26} {r['file']}:{r['linha']} candidatos={r['candidatos'][:4]}")
    print(f"  publicados com porta NAO RESOLVIDA estaticamente ({len(indireta)}):")
    for r in indireta:
        print(f"    {r['id']:44} {r['file']}:{r['linha']} {str(r['porta'])[:96]}")
    print(f"  publicados com enabled=false — ausencia auto-declarada ({len(declaradas)}):")
    for r in declaradas:
        print(f"    {r['id']:44} {str(r['reason'])[:88]}  {r['file']}:{r['linha']}")
    print(f"  mesmo id com enabled contraditorio: {report['B_emulacao']['enabled_contraditorio']}")
    print(f"  aceitos pelo backend e nunca publicados como acao ({len(nunca)}):")
    for a in nunca:
        print(f"    {a}")

    sec("Eixo C — OSD de sessao x session_control")
    print(f"  luidos em {report['C_sessao']['read_models']} read-models; aceitos pelo backend: {', '.join(sorted(accepted))}")
    for r in c_rows:
        motivo = " | ".join(r["motivos"])[:96] if r["motivos"] else "-"
        print(f"    {r['id']:16} hab={r['hab']:>2} desab={r['desab']:>2} backend={'sim' if r['aceita_no_backend'] else 'NAO':3} amostras={r['amostras']:>2}  {motivo}")
    print(f"  publicadas sem porta no backend: {report['C_sessao']['publicadas_sem_backend']}")
    print(f"  aceitas e nunca publicadas como acao de OSD: {report['C_sessao']['aceitas_nunca_publicadas']}")

    sec("Eixo D — arvore AT-SPI arquivada")
    for k, v in d_estado.most_common():
        print(f"  {k:22} {v}")
    print(f"  nomes acionaveis sem string correspondente no QML: {report['D_atspi']['sem_nome_no_qml']}")
    print()
    print(f"# JSON integral: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
