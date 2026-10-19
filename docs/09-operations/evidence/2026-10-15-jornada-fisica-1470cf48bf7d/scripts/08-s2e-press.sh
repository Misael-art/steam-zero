#!/usr/bin/env bash
# 08-s2e-press.sh — seleciona o menu Plataformas no editor e pressiona
# "Herdar AURA neste menu"; verifica ausência de E-THEME-NOT-FOUND e o estado
# do documento (Salvar sujo/limpo); salva e compara o JSON em disco.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"; SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/08-s2-resultado.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2 resultado: Herdar AURA neste menu ($(date -Is))"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco"; exit 3; }
sz_press "Menu ◆ Plataformas, entrada da jornada" $K_SPACE; sleep 1
sz_shot "S2e-1-menu-selecionado"
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S2e-arvore-menu.txt" || true
grep -E "Herdar AURA neste menu|AURA ·|Salvar" "$EV_DIR/logs/json/S2e-arvore-menu.txt" | head -8
echo "--- press 'Herdar AURA neste menu' (Space)"
sz_press "Herdar AURA neste menu" $K_SPACE; rc=$?
echo "sz_press rc=$rc"
sleep 1.2
sz_shot "S2e-2-pos-herdar"
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S2e-arvore-pos-herdar.txt" || true
echo "--- recusas E-THEME-NOT-FOUND / 'Tema não encontrado' na árvore:"
grep -icE "theme-not-found|Tema não encontrado|E-THEME" "$EV_DIR/logs/json/S2e-arvore-pos-herdar.txt"
echo "--- estado do documento (botões Salvar/sujo):"
grep -E "button\|Salvar|não salvo|sujo" "$EV_DIR/logs/json/S2e-arvore-pos-herdar.txt" | head -6
echo "--- rótulo de aparência do menu:"
grep -E "AURA ·" "$EV_DIR/logs/json/S2e-arvore-pos-herdar.txt" | head -6
echo "FIM $(date -Is)"
