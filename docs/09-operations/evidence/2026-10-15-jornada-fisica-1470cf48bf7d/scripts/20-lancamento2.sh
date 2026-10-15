#!/usr/bin/env bash
# 20-lancamento2.sh — abre o Launcher da release instalada para a metade de
# sessão (S-5..S-9). Registra pid, janela, ponte API/token em logs/20-janela2.txt.
# Não injeta nenhuma tecla aqui. Scratch: /tmp/bateria-1470/sz-launcher2.pid, sz2.env.
set -uo pipefail
EV_DIR="${EV_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
export EV_DIR
SCRATCH=/tmp/bateria-1470

# 0. confira baselines das jornadas ANTES de abrir (proteção do incidente)
J=~/.local/share/steamzero/journeys
{
  echo "# 20-janela2 — abertura do Launcher para S-5..S-9 ($(date -Is))"
  echo "## hashes de jornada antes de abrir"
  sha256sum "$J/active.json" "$J/org.steamzero.journey-4095b915.journey.json" \
    "$J/org.steamzero.journey-bc4d258a.journey.json"
  echo "  esperado: 2a37d09a…  d7c114f9…  81d313df…"
} > "$EV_DIR/logs/20-janela2.txt"

# 1. abrir o Launcher (nossa instância: pid file separado do executor 1)
if [[ ! -s "$SCRATCH/sz-launcher2.pid" ]] || ! kill -0 "$(cat "$SCRATCH/sz-launcher2.pid")" 2>/dev/null; then
  nohup /usr/local/bin/steamzero-launcher >"$SCRATCH/launcher2.log" 2>&1 &
  echo $! > "$SCRATCH/sz-launcher2.pid"
  sleep 9
fi
SZ_PID="$(cat "$SCRATCH/sz-launcher2.pid")"

# 2. janela alvo
SZ_WIN="$(kdotool search --class steamzero-launcher 2>/dev/null | head -1)"
[[ -n "$SZ_WIN" ]] || SZ_WIN="$(kdotool search SteamZero 2>/dev/null | head -1)"
if [[ -z "$SZ_WIN" ]]; then
  for id in $(kdotool search "" 2>/dev/null); do
    n="$(kdotool getwindowname "$id" 2>/dev/null)"
    case "$n" in *SteamZero*|*steamzero*) SZ_WIN="$id"; break;; esac
  done
fi

# 3. ponte: qml6 filho do nosso Launcher; ler argv (api/token)
QML_PID=""
for p in $(pgrep -P "$SZ_PID" 2>/dev/null) "$SZ_PID"; do
  cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)"
  case "$cmd" in *qml6*--steamzero-token*) QML_PID=$p; break;; esac
done
API="$(tr '\0' '\n' < /proc/$QML_PID/cmdline | grep -A1 -- '--steamzero-api' | tail -1)"
TOKEN="$(tr '\0' '\n' < /proc/$QML_PID/cmdline | grep -A1 -- '--steamzero-token' | tail -1)"

cat > "$SCRATCH/sz2.env" <<EOF
SZ_WIN=$SZ_WIN
SZ_PID=$SZ_PID
QML_PID=$QML_PID
SZ_API=$API
SZ_TOKEN=$TOKEN
EOF

{
  echo "launcher pid=$SZ_PID  qml6 pid=$QML_PID"
  echo "SZ_WIN=$SZ_WIN"
  echo "SZ_API=$API token_len=${#TOKEN}"
  echo "## geometria inicial"
  kdotool getwindowgeometry "$SZ_WIN" 2>&1
  echo "## nome da janela"
  kdotool getwindowname "$SZ_WIN" 2>&1
} >> "$EV_DIR/logs/20-janela2.txt"
echo "OK win=$SZ_WIN qml=$QML_PID api=$API"
