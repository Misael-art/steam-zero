# SPDX-License-Identifier: GPL-3.0-or-later
"""Backups include committed WAL rows and never overwrite the new host's data."""

from __future__ import annotations

import io
import json
import sqlite3
import tarfile
from pathlib import Path

import pytest

import export_host_handoff as handoff


def test_live_database_snapshot_and_restore(tmp_path: Path) -> None:
    source = tmp_path / "state"
    source.mkdir()
    database = source / "state.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE fixture(value TEXT)")
        connection.execute("INSERT INTO fixture VALUES ('uncheckpointed')")
        connection.commit()
        (source / "config.json").write_text('{"fixture":true}')
        (source / "outside-link").symlink_to(tmp_path / "outside")
        backup = tmp_path / "private"
        summary = handoff.export(backup, {"state": source})
        assert summary["sqliteSnapshots"] == 1 and summary["externallyStored"] is False
        assert handoff.verify(backup)["ok"] is True
        restored = tmp_path / "restored"
        assert handoff.restore(backup, restored)["restoreTested"] is True
        target = sqlite3.connect(restored / "state/state.db")
        try:
            assert target.execute("SELECT value FROM fixture").fetchone() == ("uncheckpointed",)
        finally:
            target.close()
        assert not (restored / "state/outside-link").exists()
        assert not (restored / "state/state.db-wal").exists()
        assert (restored / "state/config.json").stat().st_mode & 0o777 == 0o600
        with pytest.raises(handoff.HandoffError, match="novo"):
            handoff.restore(backup, restored)
        assert connection.execute("SELECT value FROM fixture").fetchone() == ("uncheckpointed",)
    finally:
        connection.close()


def test_tampered_backup_and_existing_output_are_refused(tmp_path: Path) -> None:
    source = tmp_path / "config"
    source.mkdir()
    (source / "settings").write_text("fixture")
    backup = tmp_path / "backup"
    handoff.export(backup, {"config": source})
    with pytest.raises(handoff.HandoffError, match="novo"):
        handoff.export(backup, {"config": source})
    archive = backup / "steamzero-private.tar.gz"
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(handoff.HandoffError, match="Hash"):
        handoff.verify(backup)


def test_path_traversal_is_refused_even_with_matching_archive_hash(tmp_path: Path) -> None:
    directory = tmp_path / "backup"
    directory.mkdir()
    archive = directory / "steamzero-private.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        member = tarfile.TarInfo("../escape")
        member.size = 1
        package.addfile(member, io.BytesIO(b"x"))
    (directory / "PRIVATE-MANIFEST.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "archive": archive.name,
                "archiveSha256": handoff.digest(archive),
                "files": [{"path": "../escape", "bytes": 1, "sha256": "unused"}],
            }
        )
    )
    with pytest.raises(handoff.HandoffError, match="path"):
        handoff.restore(directory, tmp_path / "restore")
    assert not (tmp_path / "escape").exists()


def test_export_cannot_recurse_into_itself(tmp_path: Path) -> None:
    with pytest.raises(handoff.HandoffError, match="própria origem"):
        handoff.export(tmp_path / "backup", {"data": tmp_path})
