# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Concrete RetroArch session peripherals behind the canonical control port."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from steamzero.adapters.theme_catalog import list_bezel_resources, resolve_bezel_resource
from steamzero.core import fs, ids, paths
from steamzero.core.errors import SteamZeroError

MAX_SLOT = 31
DEFAULT_COMMAND_PORT = 55355
STATE_COMMAND_SETTLE_SECONDS = 0.05
MAX_RUNTIME_LOG_BYTES = 64 * 1024
SESSION_CONFIG_NAME = "session-peripherals.cfg"
BEZEL_CONFIG_NAME = "aura-bezel-overlay.cfg"
BEZEL_SOURCE_NAME = "aura-bezel.svg"
BEZEL_ASSET_NAME = "aura-bezel.png"
DISC_ID_MARKER = "# SteamZero-MultiDisc-Disc:"


@dataclass(frozen=True)
class _DiscReference:
    """Bounded M3U entry retaining the generated logical disc identity."""

    identity: str
    path: Path


class SessionPeripheralRecord(Protocol):
    state: str


class SessionPeripheralControl(Protocol):
    def list_save_states(self) -> Mapping[str, Any]: ...

    def save_state(self, slot: int) -> SessionPeripheralRecord: ...

    def load_state(self, slot: int) -> SessionPeripheralRecord: ...

    def list_discs(self) -> Mapping[str, Any]: ...

    def swap_disc(self, disc_id: str) -> SessionPeripheralRecord: ...

    def list_peripherals(self) -> Mapping[str, Any]: ...


SendCommand = Callable[[str], None]


def default_retroarch_runtime_log_root() -> Path:
    """Return the host-visible per-content log root used by RetroArch Flatpak."""

    return Path.home() / ".var/app/org.libretro.RetroArch/config/retroarch/playlists/logs"


_SESSION_ID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_SESSION_BEZEL_RESOURCE = re.compile(
    r"^asset://bezels/(?P<theme>[a-z0-9]+(?:[.-][a-z0-9]+)+)@"
    r"(?P<version>[0-9]+\.[0-9]+\.[0-9]+)-(?P<digest>[0-9a-f]{64})\.png$"
)
_SESSION_CONFIG_FILES = (SESSION_CONFIG_NAME, BEZEL_CONFIG_NAME, BEZEL_ASSET_NAME)


def prepare_retroarch_session_config(
    bezel_resource: str = "aura-default",
    *,
    session_id: str | None = None,
    resolved_bezel: Mapping[str, Any] | None = None,
) -> Path:
    """Create a per-session RetroArch config with the selected validated PNG."""

    session_id = session_id or ids.new_ulid()
    if not _SESSION_ID.fullmatch(session_id):
        raise ValueError("identificador de sessão inválido para a configuração RetroArch")
    state_root = paths.saves_dir() / "states"
    # RetroArch falls back to its sandbox default when the override points to
    # a directory that does not exist. Create the managed root before spawn so
    # the session adapter and the emulator observe the same state files.
    fs.ensure_dir(state_root, mode=0o700)
    config_root = paths.config_home() / "retroarch"
    fs.ensure_dir(config_root, mode=0o700)
    sessions_root = fs.ensure_private_child(config_root, "sessions", mode=0o700)
    session_root = fs.ensure_private_child(sessions_root, session_id, mode=0o700)
    config_path = session_root / SESSION_CONFIG_NAME
    asset_root = Path(__file__).resolve().parents[1] / "ui" / "assets"
    bezel_source = asset_root / BEZEL_SOURCE_NAME
    bezel_asset_source = asset_root / BEZEL_ASSET_NAME
    if bezel_source.is_symlink() or not bezel_source.is_file():
        raise SteamZeroError(
            "E-COMPONENT-DEGRADED", detail=f"fonte de bezel AURA ausente: {BEZEL_SOURCE_NAME}"
        )
    if bezel_asset_source.is_symlink() or not bezel_asset_source.is_file():
        raise SteamZeroError(
            "E-COMPONENT-DEGRADED", detail=f"derivado de bezel AURA ausente: {BEZEL_ASSET_NAME}"
        )
    if resolved_bezel is None:
        resolved = resolve_bezel_resource(bezel_resource)
    else:
        resolved = dict(resolved_bezel)
        if resolved.get("resourceId") != bezel_resource:
            raise SteamZeroError(
                "E-THEME-UNSAFE", detail="bezel resolvido não corresponde à seleção"
            )
    image = resolved.get("_sourceBytes")
    if not isinstance(image, bytes):
        raise SteamZeroError("E-THEME-UNSAFE", detail="asset validado do bezel está ausente")
    if resolved.get("available") is not True or resolved.get("compatible") is not True:
        raise SteamZeroError(
            "E-THEME-INCOMPATIBLE", detail="bezel indisponível para RetroArch Flatpak"
        )
    try:
        from steamzero.domain.asset_recipes import validate_retroarch_bezel_source

        validate_retroarch_bezel_source(image)
    except ValueError as exc:
        raise SteamZeroError("E-THEME-UNSAFE", detail=str(exc)) from exc
    if bezel_resource == "aura-default":
        if resolved.get("origin") != "aura":
            raise SteamZeroError("E-THEME-UNSAFE", detail="identidade do bezel AURA inválida")
    else:
        match = _SESSION_BEZEL_RESOURCE.fullmatch(bezel_resource)
        if match is None:
            raise SteamZeroError("E-THEME-UNSAFE", detail="URI lógico de bezel inválido")
        if hashlib.sha256(image).hexdigest() != match.group("digest"):
            raise SteamZeroError("E-THEME-UNSAFE", detail="digest do asset de bezel não confere")
        if (
            resolved.get("origin") != "custom-theme"
            or resolved.get("themeId") != match.group("theme")
            or resolved.get("version") != match.group("version")
        ):
            raise SteamZeroError("E-THEME-UNSAFE", detail="namespace/versão do bezel não conferem")
    bezel_asset = session_root / BEZEL_ASSET_NAME
    fs.write_atomic(bezel_asset, image)
    bezel_config = session_root / BEZEL_CONFIG_NAME
    config_values = (str(bezel_asset), str(bezel_config), str(state_root))
    if any(any(character in value for character in '"\r\n') for value in config_values):
        raise SteamZeroError(
            "E-COMPONENT-DEGRADED", detail="caminho incompatível com a configuração do RetroArch"
        )
    fs.write_atomic_text(
        bezel_config,
        "\n".join(
            (
                "# SteamZero-Session-Managed: true",
                'overlays = "1"',
                f'overlay0_overlay = "{bezel_asset}"',
                'overlay0_full_screen = "true"',
                'overlay0_normalized = "true"',
                'overlay0_descs = "0"',
                'overlay0_rect = "0.0,0.0,1.0,1.0"',
                'overlay0_alpha = "1.0"',
                "",
            )
        ),
    )
    fs.write_atomic_text(
        config_path,
        "\n".join(
            (
                "# SteamZero-Session-Managed: true",
                'network_cmd_enable = "true"',
                f'network_cmd_port = "{DEFAULT_COMMAND_PORT}"',
                f'savestate_directory = "{state_root}"',
                f'input_overlay = "{bezel_config}"',
                'input_overlay_enable = "true"',
                'config_save_on_exit = "false"',
                "",
            )
        ),
    )
    return config_path


def cleanup_retroarch_session_artifacts(
    session_id: str, *, config_home: Path | None = None
) -> bool:
    """Remove only the known SteamZero files for this observed session."""
    if not _SESSION_ID.fullmatch(session_id):
        return False
    base = config_home or paths.config_home()
    retroarch_root = base / "retroarch"
    sessions_root = retroarch_root / "sessions"
    session_root = sessions_root / session_id
    if (
        session_root.is_symlink()
        or not session_root.is_dir()
        or sessions_root.is_symlink()
        or retroarch_root.is_symlink()
    ):
        return False
    try:
        session_root.resolve(strict=True).relative_to(sessions_root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    for filename in _SESSION_CONFIG_FILES:
        path = session_root / filename
        if path.is_symlink():
            return False
        if path.exists():
            if not path.is_file():
                return False
            fs.remove_file(path)
    return not any(session_root.iterdir())


def _send_udp(command: str, *, host: str, port: int, timeout: float) -> None:
    payload = command.encode("utf-8")
    if len(payload) > 512:
        raise ValueError("comando RetroArch excede o limite")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(timeout)
        connection.sendto(payload, (host, port))


class RetroArchSessionPeripheral:
    """Use only RetroArch's documented UDP commands and its state files.

    The adapter restores RetroArch's persisted per-content state slot and moves
    it with the documented ``STATE_SLOT_PLUS``/``STATE_SLOT_MINUS`` commands
    before saving. Loading uses the documented ``LOAD_STATE_SLOT`` command, so
    the gallery can operate on every bounded slot it lists.
    """

    def __init__(
        self,
        content_path: Path,
        state_root: Path,
        *,
        command_port: int = DEFAULT_COMMAND_PORT,
        send_command: SendCommand | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        runtime_log_root: Path | None = None,
        bezel_resource: Mapping[str, Any] | None = None,
        bezel_catalog: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        self._content_path = Path(content_path)
        self._state_root = Path(state_root)
        if not 1 <= command_port <= 65535:
            raise ValueError("porta RetroArch inválida")
        self._command_port = command_port
        self._send = send_command or (
            lambda command: _send_udp(command, host="127.0.0.1", port=command_port, timeout=1.0)
        )
        self._sleep = sleep
        self._now = now
        self._active_disc = 0
        self._state_subdir: str | None = None
        self._state_slot = self._read_runtime_state_slot(
            runtime_log_root or default_retroarch_runtime_log_root()
        )
        self._discs = self._read_m3u()
        self._bezel_resource = dict(bezel_resource or {})
        self._bezel_catalog = list(bezel_catalog or ())

    def list_save_states(self) -> Mapping[str, Any]:
        entries: list[dict[str, Any]] = []
        for slot in range(MAX_SLOT + 1):
            path = self._state_path(slot)
            try:
                stat = path.stat()
            except OSError:
                continue
            if path.is_symlink() or not path.is_file() or stat.st_size <= 0:
                continue
            entries.append(
                {
                    "slot": slot,
                    "timestamp": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                    "playtimeSeconds": 0,
                    "thumbnailUrl": "",
                    "compatibility": "native",
                    "available": True,
                    "backupAvailable": self._backup_path(slot).is_file(),
                }
            )
        return {
            "state": "ready" if entries else "empty",
            "entries": entries,
            "reason": "" if entries else "Nenhum save-state foi criado para esta sessão.",
        }

    def save_state(self, slot: int) -> SessionPeripheralRecord:
        self._require_slot(slot)
        self._select_state_slot(slot)
        fs.ensure_dir(self._state_root, mode=0o700)
        current = self._state_path(slot)
        if current.is_file() and not current.is_symlink() and current.stat().st_size > 0:
            fs.copy_file_atomic(current, self._backup_path(slot))
        self._send_command("SAVE_STATE")
        self._wait_for_state(slot)
        return self._record()

    def load_state(self, slot: int) -> SessionPeripheralRecord:
        self._require_slot(slot)
        if not self._state_path(slot).is_file():
            raise RuntimeError("o slot de save-state ainda não existe")
        self._send_command(f"LOAD_STATE_SLOT {slot}")
        self._state_slot = slot
        return self._record()

    def list_discs(self) -> Mapping[str, Any]:
        if len(self._discs) < 2:
            return {
                "state": "unavailable",
                "discs": [],
                "reason": "O jogo não declara um conjunto multi-disc.",
            }
        return {
            "state": "ready",
            "activeDisc": self._active_disc,
            "discs": [
                {
                    "id": disc.identity,
                    "label": disc.path.name,
                    "index": index,
                    "available": True,
                    "compatible": True,
                    "inserted": index == self._active_disc,
                }
                for index, disc in enumerate(self._discs)
            ],
        }

    def list_peripherals(self) -> Mapping[str, Any]:
        """Publish the complete, package-safe peripheral read model.

        The bezel is installed as part of the same managed RetroArch config
        that owns this adapter.  Only its logical asset URL crosses the
        session boundary; the private host path remains adapter-owned.
        """

        discs = self.list_discs()
        selected_id = str(self._bezel_resource.get("resourceId") or "aura-default")
        raw_catalog = self._bezel_catalog or list_bezel_resources()
        selected = next(
            (raw for raw in raw_catalog if (raw.get("resourceId") or raw.get("id")) == selected_id),
            None,
        )
        ordered_catalog = raw_catalog[:8]
        if selected is not None:
            others = [raw for raw in raw_catalog if raw is not selected]
            ordered_catalog = [selected, *others[:7]]
        elif self._bezel_resource and selected_id != "aura-default":
            # A valid theme can fall beyond the bounded catalog window. Keep
            # the already validated current selection visible without exposing
            # its private source bytes.
            ordered_catalog = [
                {
                    key: value
                    for key, value in self._bezel_resource.items()
                    if not str(key).startswith("_")
                },
                *ordered_catalog[:7],
            ]
        bezels: list[dict[str, Any]] = []
        for raw in ordered_catalog:
            identifier = raw.get("resourceId") or raw.get("id")
            if not isinstance(identifier, str) or not identifier:
                continue
            item = dict(raw)
            item["id"] = identifier
            item["assetUrl"] = raw.get("assetUrl", "")
            item["selected"] = identifier == selected_id
            if identifier == selected_id:
                # RetroArch's UDP GET_CONFIG_PARAM currently exposes only a
                # fixed set of values and does not return input_overlay. The
                # adapter can prove that it passed this session config at
                # launch, but not that the runtime loaded or drew the image.
                item["applied"] = False
                item["executionState"] = "launch-configured-unconfirmed"
                item["applyMode"] = "next-launch"
                item["reason"] = (
                    "Configuração da sessão enviada no launch; o runtime e os pixels "
                    "do overlay ainda não foram confirmados."
                )
            else:
                item["applied"] = False
                item["executionState"] = "available"
            bezels.append(item)
        return {
            "state": "ready",
            "activeDisc": discs.get("activeDisc"),
            "discs": discs.get("discs", []),
            "selectedBezel": selected_id,
            "appliedBezel": None,
            "bezelExecutionState": "launch-configured-unconfirmed",
            "bezelApplyMode": "next-launch",
            "bezels": bezels,
            "fade": {"phase": "idle", "progress": 0.0, "durationMs": 180},
        }

    def swap_disc(self, disc_id: str) -> SessionPeripheralRecord:
        if len(self._discs) < 2:
            raise RuntimeError("o jogo não oferece troca de disco")
        if not isinstance(disc_id, str) or not disc_id:
            raise ValueError("identificador de disco inválido")
        target = next(
            (index for index, disc in enumerate(self._discs) if disc.identity == disc_id),
            None,
        )
        # User-authored M3Us have no managed identity marker.  Keep their
        # legacy positional ids bounded, while generated descriptors use the
        # stable set/disc identity above.
        if target is None and disc_id.startswith("disc-"):
            try:
                target = int(disc_id[5:])
            except ValueError as exc:
                raise ValueError("identificador de disco inválido") from exc
        if target is None or not 0 <= target < len(self._discs):
            raise ValueError("disco fora do conjunto declarado")
        if target == self._active_disc:
            return self._record()
        self._send_command("DISK_EJECT_TOGGLE")
        step = "DISK_NEXT" if target > self._active_disc else "DISK_PREV"
        for _ in range(abs(target - self._active_disc)):
            self._send_command(step)
        self._send_command("DISK_EJECT_TOGGLE")
        self._active_disc = target
        return self._record()

    def _state_path(self, slot: int) -> Path:
        stem = self._content_path.name.rsplit(".", 1)[0]
        suffix = ".state" if slot == 0 else f".state{slot}"
        state_directory = self._state_root
        if self._state_subdir is None:
            discovered = self._discover_state_subdir(stem)
            if discovered is not None:
                self._state_subdir = discovered
                state_directory = self._state_root / discovered
        elif self._state_subdir:
            state_directory = self._state_root / self._state_subdir
        return state_directory / f"{stem}{suffix}"

    def _backup_path(self, slot: int) -> Path:
        stem = self._content_path.name.rsplit(".", 1)[0]
        return self._state_root / ".backups" / f"{stem}.slot{slot}.state"

    def _wait_for_state(self, slot: int) -> None:
        for _ in range(10):
            path = self._state_path(slot)
            if path.is_file() and not path.is_symlink() and path.stat().st_size > 0:
                return
            self._sleep(0.1)
        raise RuntimeError("RetroArch não publicou o save-state no diretório gerenciado")

    def _read_m3u(self) -> tuple[_DiscReference, ...]:
        if self._content_path.suffix.casefold() != ".m3u":
            return ()
        try:
            if self._content_path.is_symlink() or not self._content_path.is_file():
                return ()
            lines = self._content_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ()
        discs: list[_DiscReference] = []
        pending_identity: str | None = None
        for line in lines:
            value = line.strip()
            if not value:
                continue
            if value.startswith(DISC_ID_MARKER):
                identity = value[len(DISC_ID_MARKER) :].strip()
                if 1 <= len(identity) <= 256 and "\n" not in identity and "\r" not in identity:
                    pending_identity = identity
                continue
            if value.startswith("#"):
                continue
            raw_candidate = self._content_path.parent / value
            if raw_candidate.is_symlink() or not raw_candidate.is_file():
                pending_identity = None
                continue
            candidate = raw_candidate.resolve()
            if candidate.is_file():
                identity = pending_identity or f"disc-{len(discs)}"
                discs.append(_DiscReference(identity, candidate))
            pending_identity = None
        return tuple(discs[:16])

    def _read_runtime_state_slot(self, root: Path) -> int:
        """Read RetroArch's last per-content slot without modifying its state.

        RetroArch persists the current slot in a ``.lrtl`` file below the core
        name. The network interface only exposes relative slot movement, so
        starting from that persisted value is required when a prior session
        left the cursor on a non-zero slot. Missing, foreign, malformed, or
        out-of-range logs are deliberately treated as a fresh slot 0.
        """

        filename = f"{self._content_path.name.rsplit('.', 1)[0]}.lrtl"
        candidates: list[Path] = []
        try:
            direct = root / filename
            if direct.is_file() and not direct.is_symlink():
                candidates.append(direct)
            for entry in sorted(root.iterdir()):
                if entry.is_symlink() or not entry.is_dir():
                    continue
                candidate = entry / filename
                if candidate.is_file() and not candidate.is_symlink():
                    candidates.append(candidate)
        except OSError:
            return 0
        for candidate in candidates:
            try:
                if candidate.stat().st_size > MAX_RUNTIME_LOG_BYTES:
                    continue
                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(payload, Mapping):
                    continue
                value = payload.get("state_slot")
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    continue
                slot = int(value)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if -1 <= slot <= 999:
                self._state_subdir = candidate.parent.name
                # RetroArch's -1 means its automatic slot. The next PLUS
                # command selects slot 0, so retain it until selection.
                return slot
        return 0

    def _discover_state_subdir(self, stem: str) -> str | None:
        """Find an existing per-core directory without traversing user data."""

        try:
            entries = sorted(self._state_root.iterdir())
        except OSError:
            return None
        prefix = f"{stem}.state"
        for entry in entries:
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                matches = [
                    path
                    for path in entry.iterdir()
                    if path.name == stem or path.name.startswith(prefix)
                ]
            except OSError:
                continue
            if any(path.is_file() and not path.is_symlink() for path in matches):
                return entry.name
        return None

    def _select_state_slot(self, slot: int) -> None:
        if self._state_slot == -1:
            step = "STATE_SLOT_PLUS"
            distance = slot + 1
        else:
            step = "STATE_SLOT_PLUS" if slot > self._state_slot else "STATE_SLOT_MINUS"
            distance = abs(slot - self._state_slot)
        for _ in range(distance):
            self._send_command(step)
        self._state_slot = slot

    def _send_command(self, command: str) -> None:
        """Serialize UDP commands so RetroArch cannot drop slot transitions."""

        self._send(command)
        self._sleep(STATE_COMMAND_SETTLE_SECONDS)

    @staticmethod
    def _require_slot(slot: int) -> None:
        if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot <= MAX_SLOT:
            raise ValueError(f"slot de save-state fora do limite 0..{MAX_SLOT}")

    def _record(self) -> SessionPeripheralRecord:
        class Record:
            state = "running"

        return Record()


__all__ = [
    "BEZEL_ASSET_NAME",
    "BEZEL_CONFIG_NAME",
    "DEFAULT_COMMAND_PORT",
    "SESSION_CONFIG_NAME",
    "RetroArchSessionPeripheral",
    "SessionPeripheralControl",
    "cleanup_retroarch_session_artifacts",
    "default_retroarch_runtime_log_root",
    "prepare_retroarch_session_config",
]
