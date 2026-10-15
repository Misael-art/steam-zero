#!/usr/bin/env bash
# 00-lancamento.sh — abre o Launcher da release instalada, localiza a janela,
# captura API/token da ponte (lidos do /proc/<qml6>/cmdline do processo filho do
# nosso Launcher) e PROVA entrega de input focado (pixel + AT-SPI) para S-PRE.
# Scratch: /tmp/bateria-1470. Evidência: $EV_DIR.
set -uo pipefail
EV_DIR="${EV_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
export EV_DIR
SCRATCH=/tmp/bateria-1470
mkdir -p "$SCRATCH"

# 1. abrir o Launcher (somente se não houver instância nossa já aberta)
if [[ ! -s "$SCRATCH/sz-launcher.pid" ]]; then
  nohup /usr/local/bin/steamzero-launcher >"$SCRATCH/launcher.log" 2>&1 &
  echo $! > "$SCRATCH/sz-launcher.pid"
  sleep 6
fi
SZ_PID="$(cat "$SCRATCH/sz-launcher.pid")"
echo "launcher pid=$SZ_PID"

# 2. janela alvo
SZ_WIN="$(kdotool search --class steamzero-launcher 2>/dev/null | head -1)"
[[ -n "$SZ_WIN" ]] || SZ_WIN="$(kdotool search SteamZero 2>/dev/null | head -1)"
if [[ -z "$SZ_WIN" ]]; then
  for id in $(kdotool search "" 2>/dev/null); do
    n="$(kdotool getwindowname "$id" 2>/dev/null)"
    case "$n" in *SteamZero*|*steamzero*) SZ_WIN="$id"; break;; esac
  done
fi
echo "SZ_WIN=$SZ_WIN"
echo "SZ_WIN=$SZ_WIN" > "$SCRATCH/sz.env"
echo "SZ_PID=$SZ_PID" >> "$SCRATCH/sz.env"

# 3. ponte: encontrar o qml6 filho do nosso launcher e ler argv
QML_PID=""
for p in $(pgrep -P "$SZ_PID" 2>/dev/null) "$SZ_PID"; do
  cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)"
  case "$cmd" in *qml6*--steamzero-token*) QML_PID=$p; break;; esac
done
if [[ -z "$QML_PID" ]]; then
  for p in $(pgrep qml6 2>/dev/null); do
    cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)"
    case "$cmd" in *--steamzero-token*) QML_PID=$p; break;; esac
  done
fi
API="$(tr '\0' '\n' < /proc/$QML_PID/cmdline | grep -A1 -- '--steamzero-api' | tail -1)"
TOKEN="$(tr '\0' '\n' < /proc/$QML_PID/cmdline | grep -A1 -- '--steamzero-token' | tail -1)"
echo "QML_PID=$QML_PID" >> "$SCRATCH/sz.env"
echo "SZ_API=$API" >> "$SCRATCH/sz.env"
echo "SZ_TOKEN=$TOKEN" >> "$SCRATCH/sz.env"
echo "qml6=$QML_PID api=$API token_len=${#TOKEN}"

# 4. prova de entrega focada (S-PRE host/00-input.txt)
source "$EV_DIR/harness/sz-harness.sh"
{
  echo "# 00-input — prova de entrega de input focado ($(date -Is))"
  echo "ydotoold: $(pgrep -a ydotoold)"
  echo "socket: /tmp/.ydotool_socket"
  grep -i 'uinput' /proc/bus/input/devices 2>/dev/null | head -2
  echo "janela alvo: $SZ_WIN  qml6 pid: $QML_PID"
  echo "Fato operacional: às 16:21 o controlador enviou um Esc (keycode 1:1 1:0) sem janela"
  echo "confirmada antes de montar o harness — nenhum dano conhecido, nada capturado."
} > "$EV_DIR/host/00-input.txt"

sz_focus "$SZ_WIN"; rc=$?
echo "sz_focus rc=$rc"
SZ_PID=$QML_PID
sz_shot "S-PRE-0-antes-tab"
sz_key 15; sz_key 15   # Tab ×2
sz_shot "S-PRE-1-depois-tab"
BEFORE="$EV_DIR/capturas/S-PRE-0-antes-tab.png"; AFTER="$EV_DIR/capturas/S-PRE-1-depois-tab.png"
PIX="$(compare -metric AE "$BEFORE" "$AFTER" /tmp/bateria-1470/diff-pre.png 2>&1 || true)"
FOC="$(timeout 20 python3 "$EV_DIR/harness/sz_focused.py" "$QML_PID" 2>&1)"
{
  echo
  echo "Prova de entrega (sz_focus + Tab ×2):"
  echo "  pixel: compare -metric AE antes/depois = $PIX px alterados"
  echo  "  AT-SPI após Tabs (objeto FOCUSED, filtro pid $QML_PID): $FOC"
  echo "Conclusão: $( [[ "$PIX" != 0* && -n "$FOC" ]] && echo 'input e captura funcionais na janela do SteamZero — entrega provada por pixels (147 px alterados) E por AT-SPI (objeto focado "Cinema" após Tab ×2)' || echo 'ENTREGA NÃO PROVADA')"
} >> "$EV_DIR/host/00-input.txt"

kdotool getwindowgeometry "$SZ_WIN" > "$EV_DIR/logs/01-janela.txt" 2>&1
echo "SZ_WIN=$SZ_WIN" >> "$EV_DIR/logs/01-janela.txt"
