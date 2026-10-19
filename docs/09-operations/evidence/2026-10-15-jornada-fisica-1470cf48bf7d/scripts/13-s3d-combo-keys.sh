#!/usr/bin/env bash
# 13-s3d-combo-keys.sh — escolher AURA sem popup: com o combo focado (sz_press
# confere FOCUSED), enviar K_DOWN muda currentIndex e dispara onActivated.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/13-s3-escolha-down.md"
exec > >(tee "$OUT") 2>&1
echo "# S-3d combo Down real ($(date -Is))"
J=~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_key $K_ESC; sleep 0.6
sz_press "Tema para este menu" $K_DOWN; rc=$?; echo "down rc=$rc"
sleep 1
sz_shot "S3d-1-combo-valor"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Aplicar ao menu" "$SZ_PID" 2>/dev/null | head -3
sz_press "Aplicar ao menu" $K_SPACE; rc=$?; echo "apply rc=$rc"
sleep 1.5
sz_shot "S3d-2-pos-aplicar"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Salvar" "$SZ_PID" 2>/dev/null | grep "button|Salvar" | head -3
echo "FIM $(date -Is)"
