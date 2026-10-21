# SPDX-License-Identifier: GPL-3.0-or-later
"""Persist the canonical descriptive ``GameRecord`` of each game (R2).

One JSON document per game, validated by the domain before it is written. The
record carries per-field provenance, so the merge policy (manual values are
never overwritten, poorer sources never erase richer data) survives restarts.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 23


def up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS game_metadata (
          game_id     TEXT PRIMARY KEY,
          record_json TEXT NOT NULL,
          updated_at  TEXT NOT NULL
        )
        """
    )
