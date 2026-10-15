#!/usr/bin/env bash
# 07-s2d-selecionar-teste.sh — no popup do combo, desce até
# 'Jornada Bateria 2b7eb541' (2º item) e confirma; verifica a árvore do editor.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/07-s2d-selecionar-teste.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2d selecionar jornada de teste ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
# fecha qualquer popup aberto
sz_key $K_ESC; sleep 0.5
sz_press "Jornada salva" $K_SPACE; sleep 1
sz_shot "S2d-1-popup"
sz_key $K_DOWN; sleep 0.4
sz_key $K_DOWN; sleep 0.4
sz_shot "S2d-2-highlight"
sz_key $K_ENTER; sleep 1.5
sz_shot "S2d-3-pos-enter"
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S2d-arvore.txt" || true
grep -iE "Menu ◆|Menu 　|Jornada salva|Herdar AURA neste|AURA ·" "$EV_DIR/logs/json/S2d-arvore.txt" | head -20
echo "FIM $(date -Is)"
