# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded identity evidence for the existing canonical session reconciler."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from steamzero.adapters.resource_probe import parse_stat
from steamzero.core.session_state import ACTIVE_SESSION_STATES, SESSION_OWNER

_BOOT_ID = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}")


def _pid_namespace(proc_root: Path) -> str | None:
    try:
        value = str((proc_root / "self/ns/pid").readlink())
    except OSError:
        return None
    return value if re.fullmatch(r"pid:\[[0-9]+\]", value) else None


def _boot_id(proc_root: Path) -> str | None:
    try:
        value = (proc_root / "sys/kernel/random/boot_id").read_text().strip()
    except (OSError, UnicodeError):
        return None
    return value if _BOOT_ID.fullmatch(value) else None


def process_identity(pid: object, ticks: object, *, proc_root: Path = Path("/proc")) -> str:
    """Distinguish positive disappearance/reuse from denied or malformed reads."""
    if type(pid) is not int or pid <= 1 or type(ticks) is not int or ticks <= 0:
        return "unknown"
    try:
        raw = (proc_root / str(pid) / "stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return "gone"
    except (OSError, UnicodeError):
        return "unknown"
    parsed = parse_stat(raw)
    if parsed is None or parsed["pid"] != pid:
        return "unknown"
    if parsed["starttime"] != ticks:
        return "reused"
    return "gone" if parsed["state"] in {"Z", "X"} else "alive"


def lifecycle_owner(*, proc_root: Path = Path("/proc")) -> dict[str, Any] | None:
    """Record this canonical owner's identity before the game's spawn."""
    pid = os.getpid()
    try:
        parsed = parse_stat((proc_root / str(pid) / "stat").read_text())
    except (OSError, UnicodeError):
        return None
    boot = _boot_id(proc_root)
    namespace = _pid_namespace(proc_root)
    if (
        parsed is None
        or parsed["pid"] != pid
        or parsed["starttime"] <= 0
        or boot is None
        or namespace is None
    ):
        return None
    return {
        "schemaVersion": 1,
        "pid": pid,
        "startTicks": parsed["starttime"],
        "bootId": boot,
        "pidNamespace": namespace,
    }


def game_process(
    pid: int, ticks: int | None, *, proc_root: Path = Path("/proc")
) -> dict[str, Any] | None:
    """Capture the detached group's identity from the same stat snapshot."""
    try:
        raw = (proc_root / str(pid) / "stat").read_text()
        parsed = parse_stat(raw)
        fields = raw[raw.rfind(")") + 1 :].split()
        group, session = int(fields[2]), int(fields[3])
    except (OSError, UnicodeError, ValueError, IndexError):
        return None
    if (
        parsed is None
        or parsed["pid"] != pid
        or parsed["starttime"] != ticks
        or group != pid
        or session != pid
    ):
        return None
    return {
        "schemaVersion": 1,
        "pid": pid,
        "startTicks": ticks,
        "processGroup": group,
        "session": session,
    }


def _group_clear(identity: Mapping[str, Any], *, proc_root: Path) -> bool:
    """No live process/thread in the original POSIX session; unreadable is unknown."""
    try:
        entries = list(proc_root.iterdir())
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                raw = (entry / "stat").read_text()
            except (FileNotFoundError, ProcessLookupError):
                continue
            parsed = parse_stat(raw)
            if parsed is None:
                return False
            fields = raw[raw.rfind(")") + 1 :].split()
            if int(fields[2]) != identity["processGroup"] and int(fields[3]) != identity["session"]:
                continue
            if parsed["state"] not in {"Z", "X"}:
                return False
            # A zombie leader can still have live threads after pthread_exit.
            try:
                tasks = list((entry / "task").iterdir())
            except FileNotFoundError:
                continue
            for task in tasks:
                try:
                    thread = parse_stat((task / "stat").read_text())
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if thread is None or thread["state"] not in {"Z", "X"}:
                    return False
    except (OSError, UnicodeError, ValueError, IndexError):
        return False
    return True


def orphan_recovery(row: Mapping[str, Any], *, proc_root: Path = Path("/proc")) -> dict[str, Any]:
    """No writes, signals, adoption, exit code or playtime estimates.

    Recovery requires both the recorded game and its recorded lifecycle owner
    to be positively absent/reused in the SAME boot. Older or denied evidence
    remains unknown; a live owner retains authority to finish its own watcher.
    """
    denied = {"available": False, "diagnostic": "LAUNCHER-SESSION-RECOVERY-UNPROVEN-001"}
    if row.get("owner") != SESSION_OWNER or row.get("state") not in ACTIVE_SESSION_STATES:
        return denied
    try:
        raw_metadata = row.get("metadata_json")
        metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else None
    except (TypeError, ValueError, RecursionError):
        return denied
    owner = metadata.get("lifecycleOwner") if isinstance(metadata, dict) else None
    game_identity = metadata.get("gameProcess") if isinstance(metadata, dict) else None
    boot = _boot_id(proc_root)
    namespace = _pid_namespace(proc_root)
    if (
        not isinstance(metadata, dict)
        or metadata.get("source") != "emulation"
        or not isinstance(owner, dict)
        or type(owner.get("schemaVersion")) is not int
        or owner.get("schemaVersion") != 1
        or boot is None
        or owner.get("bootId") != boot
        or namespace is None
        or owner.get("pidNamespace") != namespace
        or not isinstance(game_identity, dict)
        or type(game_identity.get("schemaVersion")) is not int
        or game_identity.get("schemaVersion") != 1
        or game_identity.get("pid") != row.get("pid")
        or game_identity.get("startTicks") != row.get("start_ticks")
        or game_identity.get("processGroup") != row.get("pid")
        or game_identity.get("session") != row.get("pid")
    ):
        return denied
    game = process_identity(row.get("pid"), row.get("start_ticks"), proc_root=proc_root)
    observer = process_identity(owner.get("pid"), owner.get("startTicks"), proc_root=proc_root)
    if (
        game in {"gone", "reused"}
        and observer in {"gone", "reused"}
        and _group_clear(game_identity, proc_root=proc_root)
    ):
        return {"available": True, "diagnostic": "E-SESSION-ORPHANED"}
    return denied
