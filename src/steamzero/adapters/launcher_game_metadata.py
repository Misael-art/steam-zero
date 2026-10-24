# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the Central's canonical GameRecord without migrating the user's database."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from steamzero.adapters.state_store_game_metadata import (
    StateStoreGameMetadataAdapter,
    public_view,
)


def launcher_game_metadata(database: Path, game_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Publish the same fields/sources as Central, scoped by canonical game ID.

    Never instantiate StateStore here: the installed Launcher may observe a
    pre-v23 database. Opening it must neither create nor upgrade it. Unavailable
    storage and an unreadable row remain explicit states; neither empties the
    catalog nor initiates a remote provider request.
    """
    if not game_ids:
        return {}
    unavailable = {"state": "unavailable", "fields": {}, "sources": {}}
    try:
        connection = sqlite3.connect(
            database.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.2
        )
        try:
            adapter = StateStoreGameMetadataAdapter(connection)
            # A storage error affects the whole database. Abort after one
            # timeout instead of waiting once for every catalog item. Invalid
            # GameRecords still degrade per row inside public_view.
            return {game_id: public_view(adapter, game_id) for game_id in dict.fromkeys(game_ids)}
        finally:
            connection.close()
    except (sqlite3.Error, OSError, ValueError):
        return {game_id: dict(unavailable) for game_id in game_ids}
