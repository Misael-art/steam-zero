#!/usr/bin/env bash
# 09-s2f-salvar.sh — salva o documento após Herdar AURA e confere o JSON em disco.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/09-s2-salvar.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2f salvar documento pós-Herdar ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_press "Salvar · não salvo" $K_SPACE; echo "press rc=$?"
sleep 1.5
sz_shot "S2f-1-pos-salvar"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Salvar" "$SZ_PID" 2>/dev/null | head -8
cp ~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json "$EV_DIR/logs/json/S2-journey-depois.json"
sha256sum "$EV_DIR/logs/json/S2-journey-antes.json" "$EV_DIR/logs/json/S2-journey-depois.json" ~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json
python3 - <<'PY'
import json, os
p = os.environ['EV_DIR']+'/logs/json/'
a = json.load(open(p+'S2-journey-antes.json')); b = json.load(open(p+'S2-journey-depois.json'))
pa = {m['id']: m.get('appearance') for m in a['menus']}
pb = {m['id']: m.get('appearance') for m in b['menus']}
print('ANTES :', json.dumps(pa, ensure_ascii=False))
print('DEPOIS:', json.dumps(pb, ensure_ascii=False))
print('equal:', pa == pb)
PY
echo "FIM $(date -Is)"
