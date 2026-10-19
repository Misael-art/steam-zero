#!/usr/bin/env bash
# Harness de prova física SteamZero — captura e input verificados.
# Uso: source sz-harness.sh <uuid-da-janela-alvo>
#
# Todo envio de tecla exige foco confirmado na janela alvo. Se a confirmação
# falhar, o passo aborta com rc=3 em vez de injetar em outra janela do desktop.
set -uo pipefail

export YDOTOOL_SOCKET=/tmp/.ydotool_socket
YDOTOOL=/home/misael/.local/bin/ydotool
EV_DIR="${EV_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CAP_DIR="$EV_DIR/capturas"
LOG_FILE="$CAP_DIR/manifest.tsv"
RELEASE="2.0.0rc1-2b7eb541b4a5"

# SZ_WIN pré-carrega o alvo (cada chamada Bash abre uma shell nova; sem isso o
# SZ_TARGET fica vazio e sz_key/sz_press abortam por segurança).
SZ_TARGET="${SZ_WIN:-}"

sz_focus() {
  local uuid="$1" attempt active
  for attempt in 1 2 3; do
    kdotool windowactivate "$uuid" >/dev/null 2>&1
    sleep 0.8
    active="$(kdotool getactivewindow 2>/dev/null | tr -d '[:space:]')"
    if [[ "$active" == "$uuid" ]]; then
      SZ_TARGET="$uuid"
      return 0
    fi
    sleep 0.6
  done
  echo "sz_focus: foco não confirmado (ativo=$active, alvo=$uuid)" >&2
  return 3
}

sz_key() {
  local code="$1" repeat="${2:-1}"
  [[ -n "$SZ_TARGET" ]] || { echo "sz_key: sem alvo focado" >&2; return 2; }
  local active
  active="$(kdotool getactivewindow 2>/dev/null | tr -d '[:space:]')"
  if [[ "$active" != "$SZ_TARGET" ]]; then
    echo "sz_key: foco perdido antes de key=$code (ativo=$active)" >&2
    return 3
  fi
  local i
  for ((i = 0; i < repeat; i++)); do
    "$YDOTOOL" key "${code}:1" "${code}:0" >/dev/null 2>&1 || return 1
    sleep 0.35
  done
}

sz_shot() {
  local label="$1"
  [[ -n "$SZ_TARGET" ]] || { echo "sz_shot: sem alvo" >&2; return 2; }
  local out="$CAP_DIR/$label.png"
  timeout 25 spectacle -a "$SZ_TARGET" -b -n -o "$out" >/dev/null 2>&1
  if [[ ! -s "$out" ]]; then
    echo "sz_shot: captura vazia em $out" >&2
    return 1
  fi
  local sha
  sha="$(sha256sum "$out" | cut -d' ' -f1)"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$RELEASE" "$label" "$sha" "$(identify -format '%wx%h' "$out")" >>"$LOG_FILE"
  echo "$out"
}

# Keycodes Linux (input-event-codes.h) usados pela bateria.
readonly K_UP=103 K_DOWN=108 K_LEFT=105 K_RIGHT=106 K_ENTER=28 K_ESC=1 K_TAB=15
readonly K_A=30 K_B=48 K_C=46 K_D=32 K_E=18 K_X=45 K_Y=21 K_Z=44
readonly K_1=2 K_2=3 K_3=4 K_4=5 K_5=6 K_9=7 K_0=11 K_SPACE=57 K_BACKSPACE=14

# --- helpers de navegação por teclado (adicionados após a prova de input) ---

sz_focused() { timeout 20 python3 "$EV_DIR/harness/sz_focused.py" ${SZ_PID:+"$SZ_PID"} | cut -d'|' -f2; }

# sz_tab_to <nome-exato-do-alvo> [maximo]
# Tab-ataca até o elemento focado ter o nome desejado; ecoa quantos Tabs.
# Retorna 4 se não alcançou (diagnóstico de cadeia de foco, sem clicar às cegas).
sz_tab_to() {
  local want="$1" max="${2:-40}" active n=0 cur
  active="$(kdotool getactivewindow 2>/dev/null | tr -d '[:space:]')"
  [[ "$active" == "$SZ_TARGET" ]] || { echo "sz_tab_to: foco perdido" >&2; return 3; }
  while (( n < max )); do
    cur="$(sz_focused)"
    if [[ "$cur" == "$want" ]]; then echo "$n"; return 0; fi
    sz_key $K_TAB || return 3
    n=$((n + 1))
    sleep 0.15
  done
  echo "$n" >&2
  return 4
}

# sz_activate <nome-alvo> [max] — Tab-ataca e aciona com Enter, reafirmando foco.
sz_activate() {
  local want="$1" max="${2:-40}"
  local steps
  steps="$(sz_tab_to "$want" "$max")" || return $?
  sz_key $K_ENTER || return 3
  echo "$steps"
}

# sz_grab <nome> — posiciona o foco via acessibilidade (nenhuma tecla enviada aqui).
# A ativação continua real: sz_key $K_SPACE depois de confirmar o FOCUSED.
sz_grab() {
  local want="$1" out
  out="$(timeout 25 python3 "$EV_DIR/harness/sz_grab.py" "$want" ${SZ_PID:-})"
  echo "$out" >&2
  [[ "$out" == ok* ]]
}

# sz_type <texto> — digitação real via ydotool (uinput), com foco reafirmado.
sz_type() {
  local active
  active="$(kdotool getactivewindow 2>/dev/null | tr -d '[:space:]')"
  [[ "$active" == "$SZ_TARGET" ]] || { echo "sz_type: foco perdido ($active)" >&2; return 3; }
  "$YDOTOOL" type -- "$1" >/dev/null 2>&1
}

# sz_press <nome-acessivel> [tecla] — sequência auto-curável num desktop com
# sessões concorrentes: reafirma a janela ativa, repõe o foco acessível, confere
# que o objeto FOCUSED é o alvo e só então envia a tecla real.
# Aborta sem injetar nada se qualquer elo falhar (rc=3/4).
sz_press() {
  local want="$1" key="${2:-$K_SPACE}" attempt out rc
  [[ -n "$SZ_TARGET" ]] || { echo "sz_press: chame sz_focus antes (SZ_TARGET vazio)" >&2; return 2; }
  for attempt in 1 2 3 4 5; do
    out="$(timeout 30 python3 "$EV_DIR/harness/sz_press.py" "$SZ_TARGET" "$want" "$key" "${SZ_PID:-}" 2>&1)"
    rc=$?
    echo "sz_press[$attempt]: $out" >&2
    [[ $rc -eq 0 ]] && return 0
    case $rc in
      1|2) return $rc ;;   # alvo ausente da árvore: insistir não ajuda
    esac
    sleep 0.6
  done
  return $rc
}
