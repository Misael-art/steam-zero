#!/usr/bin/env bash
# 03-s1-central.sh — S-1: a Central declara conexão com o núcleo?
set -uo pipefail
EV_DIR="${EV_DIR:?}"; SCRATCH=/tmp/bateria-1470
export EV_DIR
source "$EV_DIR/harness/sz-harness.sh"
source "$SCRATCH/sz.env"
source "$SCRATCH/sz-central.env"
SZ_TARGET="$CENT_WIN"; export SZ_TARGET
sz_focus "$CENT_WIN" || { echo "S-1 abortado: foco não confirmado"; exit 3; }

sz_shot "S1-1-central-inicio"
timeout 60 python3 "$EV_DIR/harness/sz_states.py" conect 2>/dev/null > "$EV_DIR/logs/S1-arvore-conex.txt" || true
timeout 90 python3 "$EV_DIR/harness/sz_states.py" "" "$CENT_QML" 2>/dev/null > "$EV_DIR/logs/S1-arvore-central.txt" || true
{
  echo "# S-1 Conectividade da Central ($(date -Is))"
  echo
  echo "Esperado: a Central declara conexão com o núcleo (sem faixa 'Central desconectada')."
  echo "Observado:"
  echo "  - ocorrências de 'desconect' na árvore AT-SPI da Central (pid $CENT_QML):"
  grep -ci "desconect" "$EV_DIR/logs/S1-arvore-central.txt" | sed 's/^/      /'
  grep -i "desconect" "$EV_DIR/logs/S1-arvore-central.txt" | sed 's/^/      /' | head -5
  echo "  - ocorrências de 'conect' (afirmativas):"
  grep -i "conect" "$EV_DIR/logs/S1-arvore-central.txt" | grep -vi "desconect" | sed 's/^/      /' | head -10
  echo "  - núcleo: $(timeout 20 /usr/local/bin/steamzero service status | head -2 | tr '\n' ' ')"
  echo "  - ponte do Launcher viva (sz_api model): $(timeout 10 env SZ_API="$SZ_API" SZ_TOKEN="$SZ_TOKEN" python3 "$EV_DIR/harness/sz_api.py" model | head -1 | cut -c1-120)"
  echo "Evidência: capturas/S1-1-central-inicio.png; logs/S1-arvore-central.txt"
} > "$EV_DIR/logs/03-s1-central.md"
