#!/usr/bin/env bash
# 21-s5a-rodape.sh — S-5 parte A: geometria 1280x801, readiness do título GB,
# lançamento pela ponte, primeira captura do rodapé + dump AT-SPI da janela.
set -uo pipefail
EV_DIR="${EV_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
export EV_DIR
SCRATCH=/tmp/bateria-1470
set -a; . "$SCRATCH/sz2.env"; set +a
export SZ_WIN SZ_API SZ_TOKEN
GAME=2419aee3011f923f38611f1d   # Castlevania Legends (USA, Europe) (Translated PtBr) .gb
LOG="$EV_DIR/logs/21-s5-rodape.md"
exec > >(tee "$LOG") 2>&1
echo "# S-5 parte A — D-10 rodapé + sessão ativa ($(date -Is))"

echo "## 1. geometria antes"
kdotool getwindowgeometry "$SZ_WIN"
echo "## resize 1280x801 físico (kdotool windowresize)"
kdotool windowresize "$SZ_WIN" 1280 801
sleep 1
echo "## geometria depois"
kdotool getwindowgeometry "$SZ_WIN"
echo "## escala do host (plasmactl/kinfo6 se disponível)"
kdotool getdisplaygeometry 2>/dev/null || true
/usr/lib/qt6/bin/qeval >/dev/null 2>&1 || true

echo "## 2. readiness do título (EmulationController.game_readiness, spawn bloqueado)"
/opt/steamzero/current/venv/bin/python3 - <<'PY'
from steamzero.adapters.emulation import EmulationController
def _no_spawn(argv, *a, **k): raise AssertionError(f"probe tentou iniciar processo: {argv!r}")
c = EmulationController(spawn=_no_spawn)
print("readiness:", c.game_readiness("2419aee3011f923f38611f1d"))
PY

echo "## 3. slots de save mGBA do título (livres: state1..)"; ls -la ~/.local/share/steamzero/saves/states/mGBA/ 2>/dev/null

echo "## 4. lançamento via ponte POST /launch"
SZ_OUT="$EV_DIR/logs/json/S5-launch.json" python3 "$EV_DIR/harness/sz_api.py" launch "$GAME" | head -20
sleep 12

echo "## 5. sessão (GET /session stage=running)"
SZ_OUT="$EV_DIR/logs/json/S5-session-running.json" python3 "$EV_DIR/harness/sz_api.py" session "$GAME" running 1 | head -30

echo "## 6. processos retroarch/flatpak da sessão"
pgrep -af "retroarch|mesen|mgba" | head

echo "## 7. foco + captura do rodapé"
source "$EV_DIR/harness/sz-harness.sh"
SZ_PID=$QML_PID
sz_focus "$SZ_WIN"; echo "sz_focus rc=$?"
sz_shot "S5-1-rodape-1280x801" || echo "FALHA captura"
echo "## 8. dump AT-SPI (botões + labels da janela do Launcher)"
python3 "$EV_DIR/harness/sz_states.py" "" "$QML_PID" > "$EV_DIR/logs/S5-arvore-botones.txt" 2>&1
grep -i "journeySessionEvent\|Pausar\|atualizar\|atalh\|Ações de sessão" "$EV_DIR/logs/S5-arvore-botones.txt" | head -30
echo "fim parte A $(date -Is)"
