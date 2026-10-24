# SPDX-License-Identifier: GPL-3.0-or-later
"""v22 -> v23 upgrade and governed migration recovery, only in a test database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from steamzero.adapters.state_store_game_metadata import StateStoreGameMetadataAdapter
from steamzero.core import state
from steamzero.core.errors import SteamZeroError

GAME = "01J9ZK3Q4M5N6P7R8S9T0V1W2X"


def _v22_database(database: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as legacy:
        legacy.setattr(state, "MIGRATIONS", state.MIGRATIONS[:22])
        legacy.setattr(state, "LATEST", 22)
        with state.StateStore(database) as store:
            assert store.migrate() == 22
            store.save_job(
                {"id": "preserved", "type": "fixture", "priority": "background", "state": "queued"}
            )


def test_v23_upgrade_is_additive_and_idempotent_with_readable_v22_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "state.db"
    backups = tmp_path / "backups"
    monkeypatch.setattr(state.paths, "backups_dir", lambda: backups)
    _v22_database(database, monkeypatch)
    with state.StateStore(database) as store:
        assert store.migrate() == 23
        adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
        adapter.merge_provider_fields(
            game_id=GAME,
            title="Fixture",
            platform_id="nes-famicom",
            path="/fixtures/game.nes",
            fields={"developer": "Fixture Studio"},
            source="fixture",
            confidence=1.0,
        )
        assert store.migrate() == 23
        assert store.get_job("preserved")["state"] == "queued"
    with state.StateStore(database) as reopened:
        assert reopened.migrate() == 23
        assert (
            StateStoreGameMetadataAdapter(reopened.adapter_connection())
            .load(GAME)
            .to_mapping()["developer"]
            == "Fixture Studio"
        )
    artifacts = list(backups.glob("state-premigration-*.db"))
    assert len(artifacts) == 1, "idempotent reopen must not create a second backup"
    with closing(sqlite3.connect(artifacts[0].as_uri() + "?mode=ro", uri=True)) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 22
        assert (
            backup.execute("SELECT state FROM job WHERE id='preserved'").fetchone()[0] == "queued"
        )
        assert not backup.execute(
            "SELECT name FROM sqlite_master WHERE name='game_metadata'"
        ).fetchall()


def test_failed_v23_restores_v22_data_and_allows_clean_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "state.db"
    monkeypatch.setattr(state.paths, "backups_dir", lambda: tmp_path / "backups")
    _v22_database(database, monkeypatch)
    migrations = state.MIGRATIONS
    version, up = migrations[22]
    assert version == 23

    def interrupted(connection):
        up(connection)
        raise RuntimeError("fixture failure during v23")

    with monkeypatch.context() as failure:
        failure.setattr(state, "MIGRATIONS", [*migrations[:22], (23, interrupted)])
        with state.StateStore(database) as store:
            with pytest.raises(SteamZeroError, match="E-STATE-MIGRATION"):
                store.migrate()
            assert store.user_version == 22
            assert store.integrity_ok()
            assert store.get_job("preserved")["state"] == "queued"
            assert (
                not store.adapter_connection()
                .execute("SELECT name FROM sqlite_master WHERE name='game_metadata'")
                .fetchall()
            )
    with state.StateStore(database) as retried:
        assert retried.migrate() == 23
        assert retried.get_job("preserved")["state"] == "queued"
        assert StateStoreGameMetadataAdapter(retried.adapter_connection()).load(GAME) is None
