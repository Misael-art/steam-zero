# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only observation of the canonical game lifecycle, not a second manager."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from steamzero.core.errors import ERROR_CATALOG
from steamzero.core.session_state import SESSION_OWNER, SESSION_STATES, normalize_session_state


def observe_game_session(
    database: Path, game_id: str, *, session_id: str | None = None
) -> dict[str, Any]:
    """Never create/migrate a database or infer a running game from spawn alone.

    Running rows require matching Linux process start time to reject PID reuse.
    A missing process is unknown until the lifecycle owner records its result.
    An explicit session_id never falls back to another row for the same game.
    """
    unknown = {"gameId": game_id, "state": "unknown", "sessionId": None}
    exact = session_id is not None
    try:
        connection = sqlite3.connect(
            database.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.2
        )
        try:
            if session_id is None:
                row = connection.execute(
                    "SELECT id,state,pid,start_ticks,failure_code,metadata_json,"
                    "finished_at,exit_code "
                    "FROM game_session "
                    "WHERE game_id=? AND owner=? ORDER BY updated_at DESC,id DESC LIMIT 1",
                    (game_id, SESSION_OWNER),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT id,state,pid,start_ticks,failure_code,metadata_json,"
                    "finished_at,exit_code "
                    "FROM game_session "
                    "WHERE id=? AND game_id=? AND owner=? LIMIT 1",
                    (session_id, game_id, SESSION_OWNER),
                ).fetchone()
        finally:
            connection.close()
    except (sqlite3.Error, OSError, ValueError):
        return {**unknown, "diagnostic": "LAUNCHER-SESSION-UNAVAILABLE-001"}
    if row is None:
        return {**unknown, "diagnostic": "LAUNCHER-SESSION-NOT-OBSERVED-001"}
    session_id, raw_state, pid, ticks, failure_code, metadata, finished_at, exit_code = row
    state = normalize_session_state(raw_state)
    result = {
        "gameId": game_id,
        "sessionId": session_id,
        "state": state if state in SESSION_STATES else "unknown",
    }
    if (
        exact
        and state == "failed"
        and pid is None
        and ticks is None
        and exit_code is None
        and isinstance(finished_at, str)
        and finished_at
        and isinstance(failure_code, str)
        and failure_code in ERROR_CATALOG
    ):
        try:
            decoded = json.loads(metadata)
        except (TypeError, ValueError, RecursionError):
            decoded = None
        acknowledgment = decoded.get("launchAcknowledgment") if isinstance(decoded, dict) else None
        if (
            isinstance(decoded, dict)
            and decoded.get("source") == "emulation"
            and isinstance(acknowledgment, dict)
            and type(acknowledgment.get("schemaVersion")) is int
            and acknowledgment.get("schemaVersion") == 1
            and acknowledgment.get("state") == "notStarted"
        ):
            result.update(launchAcknowledgment="notStarted", failureCode=failure_code)
    if state in {"running", "suspended", "suspending", "resuming", "closing"}:
        if not isinstance(pid, int) or pid <= 1 or not isinstance(ticks, int):
            return {**result, "state": "unknown", "diagnostic": "LAUNCHER-SESSION-IDENTITY-001"}
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rpartition(") ")[2].split()
            matches = int(fields[19]) == ticks and fields[0] not in {"Z", "X"}
        except (OSError, ValueError, IndexError):
            matches = False
        if not matches:
            return {**result, "state": "unknown", "diagnostic": "LAUNCHER-SESSION-IDENTITY-001"}
    return result
