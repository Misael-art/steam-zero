# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only metadata projection must preserve storage and degrade per game."""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

import pytest

from steamzero.adapters.launcher_game_metadata import launcher_game_metadata
from steamzero.adapters.state_store_game_metadata import StateStoreGameMetadataAdapter, public_view
from steamzero.core.state import StateStore
from steamzero.domain.game_record import GameRecord

GAME = "01J9ZK3Q4M5N6P7R8S9T0V1W2X"


def _seed(database: Path) -> None:
    with StateStore(database) as store:
        store.migrate()
        adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
        adapter.save(
            GAME,
            GameRecord.from_mapping(
                {
                    "schemaVersion": 1,
                    "id": GAME.lower(),
                    "title": "Fixture",
                    "platformId": "nes-famicom",
                    "path": "/fixtures/game.nes",
                    "availability": "available",
                    "updatedAt": "2026-10-23T12:00:00Z",
                    "description": "Valor manual que precisa sobreviver.",
                    "developer": "Fixture Studio",
                    "provenance": {
                        "description": {
                            "source": "user",
                            "retrievedAt": "2026-10-23T12:00:00Z",
                            "confidence": 1.0,
                            "conflictPolicy": "manual",
                        }
                    },
                }
            ),
        )
        adapter.merge_provider_fields(
            game_id=GAME,
            title="Fixture",
            platform_id="nes-famicom",
            path="/fixtures/game.nes",
            fields={"description": "Outro texto do provedor."},
            source="fixture",
            confidence=1.0,
        )


def test_projection_reuses_central_view_and_manual_merge_after_reopen(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    _seed(database)
    before = database.read_bytes()
    with closing(sqlite3.connect(database)) as connection, connection:
        expected = public_view(StateStoreGameMetadataAdapter(connection), GAME)
    for _ in range(2):
        result = launcher_game_metadata(database, [GAME, "missing"])
        assert result[GAME] == expected
        assert result[GAME]["fields"]["description"] == "Valor manual que precisa sobreviver."
        assert result[GAME]["sources"]["description"] == "user"
        assert result["missing"] == {"state": "empty", "fields": {}, "sources": {}}
        assert "path" not in result[GAME]["fields"]
    assert database.read_bytes() == before


@pytest.mark.parametrize("contents", [None, b"not sqlite"])
def test_missing_or_broken_database_does_not_create_or_repair_it(
    tmp_path: Path, contents: bytes | None
) -> None:
    database = tmp_path / "missing #?.db"
    if contents is not None:
        database.write_bytes(contents)
    result = launcher_game_metadata(database, [GAME])
    assert result[GAME] == {"state": "unavailable", "fields": {}, "sources": {}}
    assert database.read_bytes() == contents if contents is not None else not database.exists()


def test_pre_v23_database_is_not_migrated(tmp_path: Path) -> None:
    database = tmp_path / "v22.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA user_version = 22")
        connection.execute("CREATE TABLE existing (value TEXT)")
        connection.execute("INSERT INTO existing VALUES ('preserved')")
    before = database.read_bytes()
    assert launcher_game_metadata(database, [GAME])[GAME]["state"] == "unavailable"
    assert database.read_bytes() == before
    with closing(sqlite3.connect(database)) as connection, connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 22
        assert connection.execute("SELECT value FROM existing").fetchone()[0] == "preserved"


def test_corrupt_game_does_not_hide_other_metadata_or_rewrite_rows(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    _seed(database)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("INSERT INTO game_metadata VALUES (?, ?, ?)", ("broken", "{", "fixture"))
        connection.commit()
    before = database.read_bytes()
    result = launcher_game_metadata(database, ["broken", GAME])
    assert result["broken"]["state"] == "unreadable"
    assert result[GAME]["state"] == "available"
    assert database.read_bytes() == before


def test_locked_database_recovers_on_next_open(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    _seed(database)
    with closing(sqlite3.connect(database)) as connection, connection:
        # WAL permits readers during an exclusive writer. A rollback-journal
        # database reproduces the genuinely unavailable storage case.
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("BEGIN EXCLUSIVE")
        game_ids = [GAME, *(f"missing-{index}" for index in range(31))]
        started = time.monotonic()
        unavailable = launcher_game_metadata(database, game_ids)
        elapsed = time.monotonic() - started
        assert all(view["state"] == "unavailable" for view in unavailable.values())
        assert len(unavailable) == len(game_ids)
        assert elapsed < 2.0, "storage timeout must not repeat for every catalog game"
        connection.rollback()
    assert launcher_game_metadata(database, [GAME])[GAME]["state"] == "available"


def test_empty_catalog_does_not_open_database(tmp_path: Path) -> None:
    assert launcher_game_metadata(tmp_path, []) == {}
