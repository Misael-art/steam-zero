# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistência e fusão do ``GameRecord`` descritivo por jogo (R2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from steamzero.adapters.state_store_game_metadata import (
    MetadataUpdate,
    StateStoreGameMetadataAdapter,
    record_id,
)
from steamzero.core.state import StateStore
from steamzero.domain.game_record import ConflictPolicy, GameRecord, ProvenanceEntry

GAME = "01J9ZK3Q4M5N6P7R8S9T0V1W2X"
WHEN = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
FIELDS = {
    "description": "English description.",
    "developer": "Nintendo R&D4",
    "releaseDate": "1985-10-18",
    "genres": ["Platform"],
}


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path / "state.db")
    state.migrate()
    return state


def _merge(adapter: StateStoreGameMetadataAdapter, fields: dict[str, object]) -> MetadataUpdate:
    return adapter.merge_provider_fields(
        game_id=GAME,
        title="Super Mario Bros.",
        platform_id="nes-famicom",
        path="/roms/nes/smb.nes",
        fields=fields,
        source="screenscraper",
        confidence=1.0,
        retrieved_at=WHEN,
    )


def test_first_fetch_persists_fields_with_provenance(store: StateStore) -> None:
    adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
    update = _merge(adapter, FIELDS)
    record = adapter.load(GAME)
    assert record is not None
    assert record.id == record_id(GAME)
    payload = record.to_mapping()
    for key, value in FIELDS.items():
        assert payload[key] == value
        entry = record.provenance_of(key)
        assert entry is not None
        assert (entry.source, entry.retrieved_at) == ("screenscraper", "2026-10-21T12:00:00Z")
    assert set(update.changed) == set(FIELDS)


def test_survives_reopening_the_database(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    first = StateStore(path)
    first.migrate()
    _merge(StateStoreGameMetadataAdapter(first.adapter_connection()), FIELDS)
    first.close()
    reopened = StateStore(path)
    record = StateStoreGameMetadataAdapter(reopened.adapter_connection()).load(GAME)
    assert record is not None
    assert record.to_mapping()["developer"] == "Nintendo R&D4"


@pytest.mark.parametrize("empty", [{}, {"description": ""}, {"unknownField": "x"}])
def test_empty_result_never_erases_existing_data(
    store: StateStore, empty: dict[str, object]
) -> None:
    adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
    _merge(adapter, FIELDS)
    update = _merge(adapter, empty)
    record = adapter.load(GAME)
    assert record is not None
    assert record.to_mapping()["description"] == "English description."
    assert update.changed == ()


def test_poorer_value_does_not_replace_richer_one(store: StateStore) -> None:
    adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
    _merge(adapter, FIELDS)
    _merge(adapter, {"description": "Short."})
    record = adapter.load(GAME)
    assert record is not None
    assert record.to_mapping()["description"] == "English description."


def test_manual_value_is_never_overwritten_and_conflict_is_recorded(store: StateStore) -> None:
    adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
    manual = ProvenanceEntry(
        source="user",
        retrieved_at="2026-10-20T08:00:00Z",
        confidence=1.0,
        conflict_policy=ConflictPolicy.MANUAL,
    )
    adapter.save(
        GAME,
        GameRecord.from_mapping(
            {
                "schemaVersion": 1,
                "id": record_id(GAME),
                "title": "Super Mario Bros.",
                "platformId": "nes-famicom",
                "path": "/roms/nes/smb.nes",
                "availability": "available",
                "updatedAt": "2026-10-20T08:00:00Z",
                "description": "Minha descrição editada à mão.",
                "provenance": {"description": manual.to_mapping()},
            }
        ),
    )
    update = _merge(adapter, FIELDS)
    record = adapter.load(GAME)
    assert record is not None
    payload = record.to_mapping()
    assert payload["description"] == "Minha descrição editada à mão."
    assert payload["developer"] == "Nintendo R&D4"
    assert "description" in update.conflicts
    assert record.warnings
