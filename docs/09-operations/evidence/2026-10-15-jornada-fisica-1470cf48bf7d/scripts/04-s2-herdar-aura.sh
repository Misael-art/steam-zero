#!/usr/bin/env bash
# 04-s2-herdar-aura.sh — S-2 Studio/D-24+D-06: "Herdar AURA neste menu" sem
# E-THEME-NOT-FOUND; resolução inherit-aura aponta para o tema AURA.
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz-central.env"
SZ_WIN="$CENT_WIN"; SZ_PID="$CENT_QML"
SZ_TARGET="$CENT_WIN"
OUT="$EV_DIR/logs/04-s2-herdar-aura.md"
exec > >(tee "$OUT") 2>&1
echo "# S-2 Herdar AURA neste menu ($(date -Is))"
echo "janela: $SZ_WIN pid qml6: $SZ_PID"
sz_focus "$SZ_WIN" || { echo "ABORTADO: foco não confirmado"; exit 3; }
sz_shot "S2-0-inicio" || true
cp ~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json "$EV_DIR/logs/json/S2-journey-antes.json"
sha256sum "$EV_DIR/logs/json/S2-journey-antes.json"

step() { echo "--- step: $*"; }

step "navegar para Temas"
sz_press "Temas" $K_ENTER; sleep 1
sz_shot "S2-1-temas"
step "aba Editar aparência"
sz_press "Editar aparência" $K_SPACE; sleep 1
sz_shot "S2-2-aba-aparencia"
step "Abrir autoria de Jornadas"
sz_press "Abrir autoria de Jornadas" $K_ENTER; sleep 1.5
sz_shot "S2-3-editor"
step "carregar jornada salva 'Jornada Bateria 2b7eb541' no combo Jornada salva"
sz_press "Jornada salva" $K_SPACE; sleep 0.8
sz_shot "S2-4-combo-aberto" || true
sz_press "Jornada Bateria 2b7eb541" $K_ENTER; sleep 1
sz_shot "S2-5-jornada-carregada"
step "selecionar menu Plataformas"
sz_press "Plataformas" $K_ENTER; sleep 0.8
step "pressionar 'Herdar AURA neste menu'"
sz_press "Herdar AURA neste menu" $K_ENTER; sleep 1.2
sz_shot "S2-6-pos-herdar"
step "verificar recusa E-THEME-NOT-FOUND na árvore"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "Tema não encontrado" "$SZ_PID" 2>/dev/null | head -5
timeout 60 python3 "$EV_DIR/harness/sz_states.py" "E-THEME" "$SZ_PID" 2>/dev/null | head -5
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$SZ_PID" 2>/dev/null > "$EV_DIR/logs/json/S2-arvore-pos-herdar.txt" || true
grep -ci "theme-not-found\|Tema não encontrado" "$EV_DIR/logs/json/S2-arvore-pos-herdar.txt" || echo "0 ocorrências de E-THEME-NOT-FOUND na árvore"
step "estado do botão Salvar (sujo?) e rótulo de aparência"
grep -i "Salvar\|Herdar AURA\|AURA ·\|escolha explícita\|herdado" "$EV_DIR/logs/json/S2-arvore-pos-herdar.txt" | head -12
step "salvar documento"
sz_press "Salvar · não salvo" $K_ENTER || sz_press "Salvar" $K_ENTER
sleep 1.5
sz_shot "S2-7-pos-salvar"
cp ~/.local/share/steamzero/journeys/org.steamzero.journey-bc4d258a.journey.json "$EV_DIR/logs/json/S2-journey-depois.json"
sha256sum "$EV_DIR/logs/json/S2-journey-depois.json"
python3 - <<'PY'
import json
a=json.load(open(__import__('os').environ['EV_DIR']+'/logs/json/S2-journey-antes.json'))
b=json.load(open(__import__('os').environ['EV_DIR']+'/logs/json/S2-journey-depois.json'))
pa={m['id']:m.get('appearance') for m in a['menus']}
pb={m['id']:m.get('appearance') for m in b['menus']}
print('appearance ANTES:', json.dumps(pa, ensure_ascii=False))
print('appearance DEPOIS:', json.dumps(pb, ensure_ascii=False))
PY
echo "FIM $(date -Is)"
