#!/usr/bin/env bash
# 02-central.sh — abre a Central (steamzero desktop ui) que ESTA bateria vai
# dirigir nos cenários S-1/S-2/S-3/S-9 e registra pid/janela em /tmp/bateria-1470.
set -uo pipefail
SCRATCH=/tmp/bateria-1470
mkdir -p "$SCRATCH"
if [ ! -s "$SCRATCH/sz-central.pid" ] || ! kill -0 "$(cat "$SCRATCH/sz-central.pid" 2>/dev/null)" 2>/dev/null; then
  nohup /usr/local/bin/steamzero desktop ui >"$SCRATCH/central.log" 2>&1 &
  echo $! > "$SCRATCH/sz-central.pid"
  sleep 10
fi
CENT_PID="$(cat "$SCRATCH/sz-central.pid")"
echo "central pid=$CENT_PID"
CENT_WIN=""
for id in $(kdotool search "" 2>/dev/null); do
  n="$(kdotool getwindowname "$id" 2>/dev/null)"
  case "$n" in *"Central de jogos"*) CENT_WIN="$id"; break;; esac
done
echo "CENT_WIN=$CENT_WIN"
{ echo "CENT_PID=$CENT_PID"; echo "CENT_WIN=$CENT_WIN"; } >> "$SCRATCH/sz-central.env"
# pid do qml6 da central (para filtro AT-SPI)
CENT_QML=""
for p in $(pgrep -P "$CENT_PID" 2>/dev/null) "$CENT_PID"; do
  cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)"
  case "$cmd" in *qml6*Main.qml*) CENT_QML=$p; break;; esac
done
[ -z "$CENT_QML" ] && for p in $(pgrep qml6 2>/dev/null); do
  cmd="$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)"
  case "$cmd" in *Main.qml*) CENT_QML=$p; break;; esac
done
echo "CENT_QML=$CENT_QML" >> "$SCRATCH/sz-central.env"
echo "central qml6=$CENT_QML"
