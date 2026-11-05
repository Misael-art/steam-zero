# SPDX-License-Identifier: GPL-3.0-or-later
"""Recovery requires exact, durable identity evidence and atomic transition."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from steamzero.adapters import emulation
from steamzero.adapters import game_session_probe as probe
from steamzero.core.errors import SteamZeroError
from steamzero.core.session_state import SESSION_OWNER
from steamzero.core.state import StateStore

IDENTITY = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
BOOT = "00000000-0000-0000-0000-000000000001"


def _stat(root, pid, ticks, state="S", *, group=None, session=None):
    path = root / str(pid) / "stat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{pid} (fixture) "
        + " ".join([state, "1", str(group or pid), str(session or pid), *(["0"] * 15), str(ticks)])
    )
    return path


def _proc(tmp_path):
    root = tmp_path / "proc"
    boot = root / "sys/kernel/random/boot_id"
    boot.parent.mkdir(parents=True)
    boot.write_text(BOOT)
    namespace = root / "self/ns/pid"
    namespace.parent.mkdir(parents=True)
    namespace.symlink_to("pid:[1234]")
    return root


def _row(**changes):
    return {
        "id": IDENTITY,
        "game_id": "game",
        "owner": SESSION_OWNER,
        "state": "running",
        "pid": 4300,
        "start_ticks": 20,
        "metadata_json": json.dumps(
            {
                "source": "emulation",
                "gameProcess": {
                    "schemaVersion": 1,
                    "pid": 4300,
                    "startTicks": 20,
                    "processGroup": 4300,
                    "session": 4300,
                },
                "lifecycleOwner": {
                    "schemaVersion": 1,
                    "pid": 4200,
                    "startTicks": 10,
                    "bootId": BOOT,
                    "pidNamespace": "pid:[1234]",
                },
            }
        ),
        **changes,
    }


@pytest.mark.parametrize(
    "owner,game,available",
    [
        (None, None, True),
        (10, None, False),
        (None, 20, False),
        (11, None, True),
        (None, 21, True),
        (11, 21, True),
        (10, 21, False),
    ],
)
def test_recovery_needs_both_original_identities_gone(tmp_path, owner, game, available):
    root = _proc(tmp_path)
    if owner is not None:
        _stat(root, 4200, owner)
    if game is not None:
        _stat(
            root, 4300, game, group=999 if game != 20 else 4300, session=999 if game != 20 else 4300
        )
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is available


@pytest.mark.parametrize(
    "change",
    [
        {"owner": "external"},
        {"state": "closed"},
        {"pid": True},
        {"start_ticks": None},
        {"metadata_json": "invalid"},
        {"metadata_json": "[]"},
        {"metadata_json": None},
        {"metadata_json": json.dumps({"source": "emulation"})},
        {"metadata_json": json.dumps({"source": "other", "lifecycleOwner": {}})},
    ],
)
def test_missing_or_invalid_evidence_never_grants_recovery(tmp_path, change):
    root = _proc(tmp_path)
    assert probe.orphan_recovery(_row(**change), proc_root=root)["available"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("schemaVersion", True),
        ("schemaVersion", 2),
        ("pid", True),
        ("startTicks", None),
        ("bootId", "different"),
        ("pidNamespace", "different"),
    ],
)
def test_owner_identity_version_and_boot_are_required(tmp_path, field, value):
    root = _proc(tmp_path)
    row = _row()
    metadata = json.loads(row["metadata_json"])
    metadata["lifecycleOwner"][field] = value
    row["metadata_json"] = json.dumps(metadata)
    assert probe.orphan_recovery(row, proc_root=root)["available"] is False


def test_denied_and_malformed_proc_are_unknown_and_zombies_are_not_live(tmp_path, monkeypatch):
    root = _proc(tmp_path)
    target = _stat(root, 4300, 20)
    read = Path.read_text

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("fixture denied")
        return read(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", denied)
        assert probe.process_identity(4300, 20, proc_root=root) == "unknown"
        assert probe.orphan_recovery(_row(), proc_root=root)["available"] is False
    target.write_text("malformed")
    assert probe.process_identity(4300, 20, proc_root=root) == "unknown"
    _stat(root, 4300, 20, "Z")
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is True
    (root / "sys/kernel/random/boot_id").unlink()
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is False


def test_capture_records_only_current_owner_identity(tmp_path):
    root = _proc(tmp_path)
    _stat(root, os.getpid(), 33)
    assert probe.lifecycle_owner(proc_root=root) == {
        "schemaVersion": 1,
        "pid": os.getpid(),
        "startTicks": 33,
        "bootId": BOOT,
        "pidNamespace": "pid:[1234]",
    }
    (root / str(os.getpid()) / "stat").write_text("malformed")
    assert probe.lifecycle_owner(proc_root=root) is None


def test_descendants_and_live_threads_of_a_zombie_leader_prevent_recovery(tmp_path):
    root = _proc(tmp_path)
    descendant = _stat(root, 4400, 30, group=4400, session=4300)
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is False
    descendant.unlink()
    _stat(root, 4300, 20, "Z")
    thread = _stat(root / "4300/task", 4301, 21, group=4300, session=4300)
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is False
    thread.unlink()
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is True


def test_group_capture_and_unknown_members_cannot_create_recovery_proof(tmp_path):
    root = _proc(tmp_path)
    _stat(root, 4300, 20)
    assert probe.game_process(4300, 20, proc_root=root) == {
        "schemaVersion": 1,
        "pid": 4300,
        "startTicks": 20,
        "processGroup": 4300,
        "session": 4300,
    }
    assert probe.game_process(4300, 21, proc_root=root) is None
    assert probe.game_process(9999, 20, proc_root=root) is None
    (root / "4300/stat").unlink()
    _stat(root, 4400, 30).write_text("malformed")
    assert probe.orphan_recovery(_row(), proc_root=root)["available"] is False


def _controller(tmp_path, monkeypatch):
    database = tmp_path / "state.db"
    root = _proc(tmp_path)
    controller = emulation.EmulationController.__new__(emulation.EmulationController)
    controller._store_factory = lambda: StateStore(database)
    monkeypatch.setattr(
        emulation, "orphan_recovery", lambda row: probe.orphan_recovery(row, proc_root=root)
    )
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(_row(state="launching"))
        store.transition_game_session(
            IDENTITY,
            "running",
            pid=4300,
            start_ticks=20,
            played_seconds=7,
            duration_source="observed-monotonic",
        )
    return controller, database, root


def test_exact_recovery_is_idempotent_and_does_not_estimate_playtime(tmp_path, monkeypatch):
    controller, database, _root = _controller(tmp_path, monkeypatch)
    with StateStore(database) as store:
        store.create_game_session(_row(id=OTHER, state="failed"))  # newer unrelated history
    result = controller.recover_game_session("game", IDENTITY)
    assert result["status"] == "recovered" and result["state"] == "failed"
    with StateStore(database) as store:
        row = store.get_game_session(IDENTITY)
        assert row["failure_code"] == "E-SESSION-ORPHANED"
        assert row["exit_code"] is None and row["pid"] is None
        assert row["played_seconds"] == 7 and row["duration_source"] == "observed-monotonic"
        assert store.get_game_session(OTHER)["failure_code"] is None
    assert controller.recover_game_session("game", IDENTITY)["status"] == "clean"
    with StateStore(database) as store:
        assert store.get_game_session(IDENTITY) == row


def test_live_owner_retains_authority_even_after_game_disappears(tmp_path, monkeypatch):
    controller, database, root = _controller(tmp_path, monkeypatch)
    _stat(root, 4200, 10)
    assert controller.recover_game_session("game", IDENTITY)["status"] == "blocked"
    assert controller._reap_dead_game_sessions() == 0
    with StateStore(database) as store:
        assert store.get_game_session(IDENTITY)["state"] == "running"
    (root / "4200/stat").unlink()
    assert controller._reap_dead_game_sessions() == 1
    with StateStore(database) as store:
        assert store.get_game_session(IDENTITY)["state"] == "failed"


@pytest.mark.parametrize("game,identity", [("other", IDENTITY), ("game", OTHER)])
def test_exact_recovery_never_adopts_another_game_or_identity(
    tmp_path, monkeypatch, game, identity
):
    controller, database, _root = _controller(tmp_path, monkeypatch)
    assert controller.recover_game_session(game, identity)["status"] == "blocked"
    with StateStore(database) as store:
        assert store.get_game_session(IDENTITY)["state"] == "running"


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner", "external"),
        ("game_id", "other"),
        ("state", "closing"),
        ("pid", 4400),
        ("start_ticks", 21),
        ("metadata_json", "{}"),
    ],
)
def test_transition_rejects_changed_identity_inside_the_write_transaction(tmp_path, field, value):
    database = tmp_path / "state.db"
    with StateStore(database) as store:
        store.migrate()
        store.create_game_session(_row())
        before = store.get_game_session(IDENTITY)
        expected = {
            k: before[k]
            for k in ("owner", "game_id", "state", "pid", "start_ticks", "metadata_json")
        }
        with closing(sqlite3.connect(database)) as external:
            queries = {
                "owner": "UPDATE game_session SET owner=? WHERE id=?",
                "game_id": "UPDATE game_session SET game_id=? WHERE id=?",
                "state": "UPDATE game_session SET state=? WHERE id=?",
                "pid": "UPDATE game_session SET pid=? WHERE id=?",
                "start_ticks": "UPDATE game_session SET start_ticks=? WHERE id=?",
                "metadata_json": "UPDATE game_session SET metadata_json=? WHERE id=?",
            }
            external.execute(queries[field], (value, IDENTITY))
            external.commit()
        changed = store.get_game_session(IDENTITY)
        with pytest.raises(SteamZeroError) as rejected:
            store.transition_game_session(IDENTITY, "failed", expected=expected)
        assert rejected.value.code == "E-TX-STALE-PLAN"
        assert store.get_game_session(IDENTITY) == changed


def test_recovery_survives_a_canonical_change_between_probe_and_commit(tmp_path, monkeypatch):
    controller, database, _root = _controller(tmp_path, monkeypatch)
    transition = StateStore.transition_game_session

    def raced(store, identity, target, **changes):
        with closing(sqlite3.connect(database)) as external:
            external.execute("UPDATE game_session SET metadata_json=? WHERE id=?", ("{}", identity))
            external.commit()
        return transition(store, identity, target, **changes)

    monkeypatch.setattr(StateStore, "transition_game_session", raced)
    result = controller.recover_game_session("game", IDENTITY)
    assert result["status"] == "blocked" and result["diagnostic"] == "E-TX-STALE-PLAN"
    with StateStore(database) as store:
        assert store.get_game_session(IDENTITY)["state"] == "running"


def test_invalid_snapshot_guard_is_rejected_without_a_write(tmp_path):
    with StateStore(tmp_path / "state.db") as store:
        store.migrate()
        store.create_game_session(_row())
        before = store.get_game_session(IDENTITY)
        with pytest.raises(SteamZeroError) as refused:
            store.transition_game_session(IDENTITY, "failed", expected={"unsupported": "value"})
        assert refused.value.code == "E-API-SCHEMA"
        assert store.get_game_session(IDENTITY) == before


def test_invalid_recovery_id_never_creates_a_store(tmp_path):
    controller = emulation.EmulationController.__new__(emulation.EmulationController)
    controller._store_factory = lambda: pytest.fail("invalid identity opened storage")
    with pytest.raises(SteamZeroError) as refused:
        controller.recover_game_session("game", "bad")
    assert refused.value.code == "E-API-SCHEMA"
