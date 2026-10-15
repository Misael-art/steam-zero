#!/usr/bin/env bash
# 11-s3b-aplicar-tema.sh — S-3: aplicar tema específico (AURA) ao menu Gêneros;
# herança preservada nos demais; salvar; conferir JSON antes/depois.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/11-s3-aplicar-tema.md"
exec > >(tee "$OUT") 2>&1
echo "# S-3 aplicar tema a um menu ($(date -Is))"
J=~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_key $K_ESC; sleep 0.5
cp "$J" "$EV_DIR/logs/json/S3-journey-antes.json"
sha256sum "$EV_DIR/logs/json/S3-journey-antes.json"
echo "--- selecionar menu Gêneros"
sz_press "Menu 　Gêneros" $K_SPACE; sleep 1
echo "--- combo Tema para este menu: abrir, descer 1 (AURA), Enter"
sz_press "Tema para este menu" $K_SPACE; sleep 1
sz_key $K_DOWN; sleep 0.5
sz_shot "S3-2-aura-highlight"
sz_key $K_ENTER; sleep 1
sz_shot "S3-3-aura-escolhido"
echo "--- Aplicar ao menu"
sz_press "Aplicar ao menu" $K_SPACE; rc=$?; echo "press rc=$rc"
sleep 1.5
sz_shot "S3-4-pos-aplicar"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Salvar" "$SZ_PID" 2>/dev/null | grep -E "button\|Salvar" | head -4
echo "--- salvar documento"
sz_press "Salvar · não salvo" $K_SPACE; echo "save rc=$?"
sleep 1.5
sz_shot "S3-5-pos-salvar"
cp "$J" "$EV_DIR/logs/json/S3-journey-depois.json"
sha256sum "$EV_DIR/logs/json/S3-journey-depois.json"
python3 - <<'PY'
import json, os
p = os.environ['EV_DIR']+'/logs/json/'
a = json.load(open(p+'S3-journey-antes.json')); b = json.load(open(p+'S3-journey-depois.json'))
pa = {m['id']: m.get('appearance') for m in a['menus']}
pb = {m['id']: m.get('appearance') for m in b['menus']}
print('ANTES :', json.dumps(pa, ensure_ascii=False))
print('DEPOIS:', json.dumps(pb, ensure_ascii=False))
PY
echo "FIM $(date -Is)"
