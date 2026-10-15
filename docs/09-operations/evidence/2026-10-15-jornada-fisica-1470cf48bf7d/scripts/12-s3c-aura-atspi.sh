#!/usr/bin/env bash
# 12-s3c-aura-atspi.sh — S-3: escolher AURA no combo via grab_focus AT-SPI no
# item do popup (teclas soltas não alcançavam o highlight do popup) e aplicar.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/12-s3-escolha-aura.md"
exec > >(tee "$OUT") 2>&1
echo "# S-3c escolher AURA via AT-SPI ($(date -Is))"
J=~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_key $K_ESC; sleep 0.6
sz_press "Tema para este menu" $K_SPACE; sleep 1
sz_shot "S3c-1-popup"
echo "--- grab no item 'AURA' + Enter"
sz_press "AURA" $K_ENTER; rc=$?; echo "item rc=$rc"
sleep 1.2
sz_shot "S3c-2-pos-escolha"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Aplicar ao menu" "$SZ_PID" 2>/dev/null | head -3
echo "--- Aplicar ao menu"
sz_press "Aplicar ao menu" $K_SPACE; rc=$?; echo "apply rc=$rc"
sleep 1.5
sz_shot "S3c-3-pos-aplicar"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Salvar" "$SZ_PID" 2>/dev/null | grep "button|Salvar" | head -3
cp "$J" "$EV_DIR/logs/json/S3-journey-depois.json"
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
