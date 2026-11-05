#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Run as the ordinary user. System packages require the operator's explicit flag.
set -eu
apply=false
system_packages=false
system_plan=false
ui=false
for option in "$@"; do
    case "$option" in
        --apply) apply=true ;;
        --system-packages) system_packages=true ;;
        --system-plan) system_plan=true ;;
        --ui) ui=true ;;
    esac
done
if [ "$(id -u)" = 0 ]; then
    echo "Execute como usuário comum; não crie o checkout/venv como root." >&2
    exit 1
fi
if [ -r /etc/os-release ]; then
    . /etc/os-release
fi
case " ${ID:-} ${ID_LIKE:-} " in
    *ubuntu*|*debian*)
        manager=apt-get
        packages="git make curl ca-certificates python3 python3-venv zstd"
        ;;
    *arch*|*manjaro*|*biglinux*)
        manager=pacman
        packages="git make curl ca-certificates python zstd"
        ;;
    *)
        manager=unsupported
        packages="git make curl python3>=3.11 tar sha256sum"
        ;;
esac
if "$system_plan"; then
    echo "Plano de pré-requisitos: $manager: $packages"
    echo "Qt nativo é opcional; baselines visuais exigem a imagem fixada do CI."
    echo "Não instala SteamZero em /opt nem configura serviços, emuladores ou boot."
    if "$ui"; then
        echo "UI nativa Arch/Manjaro: qt6-declarative qt6-base qt6-svg fontconfig freetype2 harfbuzz."
        echo "Ubuntu/Debian: use o gate visual remoto canônico; o runtime QML nativo não é equivalente."
    fi
    exit 0
fi
if "$system_packages" && "$apply"; then
    if [ -e /opt/steamzero/current ]; then
        echo "Modo de pacotes destinado a host vazio; instalação atual preservada." >&2
        exit 1
    fi
    case "$manager" in
        apt-get)
            sudo -- apt-get update
            # Fixed package list, no user-provided package names or shell evaluation.
            sudo -- apt-get install -y --no-install-recommends git make curl ca-certificates python3 python3-venv zstd
            ;;
        pacman)
            # No database sync or partial upgrade. A stale repository must be
            # updated separately by the operator according to distro policy.
            sudo -- pacman -S --needed --noconfirm git make curl ca-certificates python zstd
            if "$ui"; then
                sudo -- pacman -S --needed --noconfirm qt6-declarative qt6-base qt6-svg fontconfig freetype2 harfbuzz
            fi
            ;;
        *) echo "Distribuição sem plano automático; consulte o plano acima." >&2; exit 1 ;;
    esac
fi
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$script_dir/tools/bootstrap_dev.py" ]; then
    destination=${STEAMZERO_WORKSPACE:-"$HOME/Projects/SteamZero"}
    if ! "$apply"; then
        echo "Plano: clonar branch codex/product-recovery-2026-10-16 em $destination e preparar ambiente isolado."
        exit 0
    fi
    if [ -e "$destination" ]; then
        echo "Destino já existe; não será substituído: $destination" >&2
        exit 1
    fi
    command -v git >/dev/null 2>&1 || { echo "git ausente; use --system-plan." >&2; exit 1; }
    mkdir -p -- "$(dirname -- "$destination")"
    git clone --filter=blob:none --single-branch --branch codex/product-recovery-2026-10-16 https://github.com/Misael-art/steam-zero.git "$destination"
    git -C "$destination" fetch origin main:refs/remotes/origin/main
    script_dir=$destination
fi
command -v python3 >/dev/null 2>&1 || { echo "python3 ausente; use --system-plan." >&2; exit 1; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' || {
    echo "Pré-requisito: Python >=3.11 para o bootstrap. Nada foi recriado." >&2
    exit 1
}
exec python3 "$script_dir/tools/bootstrap_dev.py" "$@"
