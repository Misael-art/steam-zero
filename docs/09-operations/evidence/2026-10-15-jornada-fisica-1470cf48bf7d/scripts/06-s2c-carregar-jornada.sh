#!/usr/bin/env bash
# 06-s2c-carregar-jornada.sh — abre o popup do combo "Jornada salva" e navega
# com Down/Enter REAIS (teclas vão para a janela ativa; o popup do QML é parte
# da mesma janela). Captura cada passo para escolher o item certo.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/06-s2c-carregar-jornada.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2c carregar jornada salva ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_press "Jornada salva" $K_SPACE; sleep 1
sz_shot "S2c-1-popup"
sz_key $K_DOWN; sleep 0.5
sz_shot "S2c-2-down1"
sz_key $K_ENTER; sleep 1.2
sz_shot "S2c-3-pos-enter"
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S2c-arvore.txt" || true
grep -iE "Plataformas|Gêneros|Jornada|Árvore" "$EV_DIR/logs/json/S2c-arvore.txt" | head -20
echo "FIM $(date -Is)"
