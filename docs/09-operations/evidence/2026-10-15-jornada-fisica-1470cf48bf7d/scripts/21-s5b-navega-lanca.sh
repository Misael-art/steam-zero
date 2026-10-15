#!/usr/bin/env bash
# 21-s5b-navega-lanca.sh — S-5 parte B: navegação física até o jogo GB
# (evidência D-11/D-19: registra qual tecla responde), foco no item, lançamento
# real pela ponte, e captura do rodapé com sessão ativa.
set -uo pipefail
EV_DIR="${EV_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
export EV_DIR
SCRATCH=/tmp/bateria-1470
set -a; . "$SCRATCH/sz2.env"; set +a
export SZ_WIN SZ_API SZ_TOKEN
GAME=2419aee3011f923f38611f1d
ITEM="emulation:$GAME"
LOG="$EV_DIR/logs/21-s5-rodape.md"
exec >> "$LOG" 2>&1
cd "$EV_DIR"
echo; echo "# S-5 parte B — navegação + lançamento ($(date -Is))"
source "$EV_DIR/harness/sz-harness.sh"
SZ_PID=$QML_PID
sz_focus "$SZ_WIN" || { echo "sz_focus rc=$? ABORT"; exit 3; }

echo "## B1. entra na plataforma GB via grab+Enter (teclado seta testado depois)"
sz_grab "Game Boy, Game Boy Color e Game Boy Advance" && sz_key $K_ENTER && echo "grab+Enter ok"
sleep 2
python3 harness/sz_api.py model | head -2

echo "## B2. teste de setas (evidência D-11/D-19): foco antes/depois de Down×2"
echo "foco antes: $(sz_focused)"
sz_key $K_DOWN; sz_key $K_DOWN
echo "foco depois de Down×2: $(sz_focused)"
python3 harness/sz_api.py model | grep focus= | head -1

echo "## B3. busca por nome (atalho de navegação) até Castlevania Legends"
sz_grab "Digite o nome do jogo" && echo "grab search ok" || echo "grab search FALHOU"
sz_type "Castlevania Legends"; echo "digitou rc=$?"
sleep 2
python3 harness/sz_api.py model | head -4

echo "## B4. setas até o item do jogo; registra foco a cada passo"
for i in 1 2 3 4 5 6 7 8; do
  F="$(python3 harness/sz_api.py model 2>/dev/null | grep -o 'focus=[^ ]*' | cut -d= -f2)"
  echo "iter $i focus=$F"
  [[ "$F" == *"$GAME"* ]] && break
  sz_key $K_DOWN
  sleep 0.4
done
F="$(python3 harness/sz_api.py model 2>/dev/null | grep -o 'focus=[^ ]*' | cut -d= -f2)"
echo "focus final=$F"
python3 harness/sz_api.py model | head -3

echo "## B5. POST /launch"
SZ_OUT="$EV_DIR/logs/json/S5-launch2.json" python3 harness/sz_api.py launch "$GAME" "$ITEM" | head -12
sleep 14

echo "## B6. modelo pós-lançamento (estado da sessão + eventos)"
python3 harness/sz_api.py model | head -3
SZ_OUT="$EV_DIR/logs/json/S5-session-running.json" python3 harness/sz_api.py session "$GAME" running 1 >/dev/null
head -c 900 "$EV_DIR/logs/json/S5-session-running.json"; echo
echo "## B7. processos da sessão"; pgrep -af retroarch | head -4
echo "## B8. foco launcher + captura rodapé + dump AT-SPI"
sz_focus "$SZ_WIN"; echo "sz_focus rc=$?"
sz_shot "S5-2-rodape-sessao-ativa"
python3 harness/sz_states.py "" "$QML_PID" > "$EV_DIR/logs/S5-arvore-sessao.txt" 2>&1
grep -c "journeySessionEvent" "$EV_DIR/logs/S5-arvore-sessao.txt" || true
grep -a "journeySessionEvent\|Ações de sessão\|navegar ·" "$EV_DIR/logs/S5-arvore-sessao.txt" | head -12
echo "fim parte B $(date -Is)"
