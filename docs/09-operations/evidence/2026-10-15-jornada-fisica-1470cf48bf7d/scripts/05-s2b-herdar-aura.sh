#!/usr/bin/env bash
# 05-s2b-herdar-aura.sh — S-2 refeito: ativação por SPACE (Enter não ativou os
# botões de navegação da Central; tecla alcança a janela — anel de foco move —
# mas só Space dispara).
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/05-s2b-herdar-aura.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2 (refeito, ativação por Space) ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco não confirmado"; exit 3; }
sz_shot "S2b-0-inicio"
cp ~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json "$EV_DIR/logs/json/S2-journey-antes.json"
step() { echo "--- step: $*"; }

step "Temas (Space)"
sz_press "Temas" $K_SPACE; sleep 1.2
sz_shot "S2b-1-temas"
step "aba Editar aparência (Space)"
sz_press "Editar aparência" $K_SPACE; sleep 1.2
sz_shot "S2b-2-aba-aparencia"
step "Abrir autoria de Jornadas (Space)"
sz_press "Abrir autoria de Jornadas" $K_SPACE; sleep 1.5
sz_shot "S2b-3-editor"
step "combo Jornada salva (Space abre popup)"
sz_press "Jornada salva" $K_SPACE; sleep 1
sz_shot "S2b-4-combo-aberto"
step "item da jornada de teste no popup"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Jornada" "$SZ_PID" 2>/dev/null | head -12
if sz_press "Jornada Bateria 2b7eb541" $K_ENTER; then :
else
  sz_key $K_DOWN; sleep 0.4; sz_key $K_ENTER
fi
sleep 1.2
sz_shot "S2b-5-jornada-carregada"
echo "FIM $(date -Is)"
