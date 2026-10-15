#!/usr/bin/env bash
# 10-s3a-tema-popup.sh — S-3 passo 1: selecionar menu Gêneros e abrir o combo
# "Tema para este menu" para ver as opções do catálogo do editor.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/10-s3a-opcoes-tema.md"
exec > >(tee "$OUT") 2>&1
echo "# S-3a opções do catálogo do editor ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_press "Menu 　Gêneros" $K_SPACE; echo "select Gêneros rc=$?"
sleep 1
sz_shot "S3-0-menu-generos"
sz_press "Tema para este menu" $K_SPACE; echo "combo rc=$?"
sleep 1
sz_shot "S3-1-combo-tema-aberto"
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S3a-arvore-popup.txt" || true
echo "--- itens visíveis do popup (papéis list item/menu item/radio):"
grep -iE "list item|menu item|AURA|es-de|steamdeck|default|tema" "$EV_DIR/logs/json/S3a-arvore-popup.txt" | head -25
echo "FIM $(date -Is)"
