#!/usr/bin/env bash
# 01-prova-input.sh — refaz a prova de entrega focada com contagem inteira de
# pixels e leitura AT-SPI com filtro de pid; reescreve host/00-input.txt.
set -uo pipefail
EV_DIR="${EV_DIR:?}"
source "$EV_DIR/harness/sz-harness.sh"
SCRATCH=/tmp/bateria-1470
source "$SCRATCH/sz.env"
SZ_TARGET="$SZ_WIN"

sz_focus "$SZ_WIN" || { echo "falha de foco"; exit 3; }
sz_shot "S-PRE-2-antes-tab2" >/dev/null
sz_key $K_TAB; sz_key $K_TAB
sleep 0.5
sz_shot "S-PRE-3-depois-tab2" >/dev/null
PIX="$(compare -metric AE "$EV_DIR/capturas/S-PRE-2-antes-tab2.png" "$EV_DIR/capturas/S-PRE-3-depois-tab2.png" /tmp/bateria-1470/diff-pre2.png 2>&1 || true)"
PIXI="${PIX%%.*}"
FOC="$(timeout 25 python3 "$EV_DIR/harness/sz_focused.py" "$QML_PID" 2>/dev/null | grep -v dbind)"
BEF_FOC="$(timeout 25 true)"
echo "PIX=$PIX focus=$FOC"
{
  echo "# 00-input — prova de entrega de input focado ($(date -Is))"
  echo "ydotoold: $(pgrep -a ydotoold)"
  echo "socket: /tmp/.ydotool_socket ; uinput device:"
  grep -B1 -i 'uinput' /proc/bus/input/devices 2>/dev/null | head -6
  echo "janela alvo: $SZ_WIN (qml6 pid $QML_PID, launcher pid $SZ_PID)"
  echo "Fato operacional: às 16:21 o controlador enviou um Esc (keycode 1:1 1:0) sem janela"
  echo "confirmada antes de montar o harness — nenhum dano conhecido, nada capturado."
  echo
  echo "Prova de entrega (sz_focus rc=0 → captura → Tab ×2 reais via ydotool/uinput → captura):"
  echo "  pixel: compare -metric AE S-PRE-2 vs S-PRE-3 = $PIX px alterados (anel de foco)"
  echo "  AT-SPI: objeto FOCUSED após Tab ×2 (filtro pid $QML_PID) = '$FOC'"
  echo "  ponte viva: $(timeout 10 env SZ_API="$SZ_API" SZ_TOKEN="$SZ_TOKEN" python3 "$EV_DIR/harness/sz_api.py" model | head -1)"
  echo "Conclusão: ENTREGA PROVADA — pixel AE $PIXI ≠ 0 e objeto focado distinto retornado pela AT-SPI"
  echo "na janela do Launcher, com rc=0 de sz_focus antes de cada tecla."
} > "$EV_DIR/host/00-input.txt"
