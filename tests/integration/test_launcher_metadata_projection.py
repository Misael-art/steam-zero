# SPDX-License-Identifier: GPL-3.0-or-later
"""Persisted Central metadata must reach the real Launcher entrypoint offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from steamzero.adapters.emulation import EmulationController
from steamzero.adapters.journey_public import project_game_row
from steamzero.adapters.state_store_game_metadata import StateStoreGameMetadataAdapter
from steamzero.core import paths
from steamzero.core.state import StateStore
from steamzero.launcher.app import main

GAME = "01J9ZK3Q4M5N6P7R8S9T0V1W2X"
FIELDS = {
    "description": "Descrição de fixture, sem consulta remota.",
    "developer": "Desenvolvedor de fixture",
    "releaseDate": "1985-10-18",
    "genres": ["Plataforma"],
}


@pytest.mark.parametrize("has_canonical_date", [True, False])
def test_central_persistence_reaches_launcher_after_restart_with_same_media_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_canonical_date: bool
) -> None:
    fields = {
        key: value for key, value in FIELDS.items() if has_canonical_date or key != "releaseDate"
    }
    for name in ("DATA", "STATE", "CONFIG", "CACHE"):
        monkeypatch.setenv(f"XDG_{name}_HOME", str(tmp_path / name.lower()))
    library = tmp_path / "library.json"
    library.write_text(
        json.dumps(
            {
                "games": [
                    {
                        "id": GAME,
                        "name": "Jogo de fixture",
                        "platform": "nes-famicom",
                        "description": "Descrição antiga do cache",
                        "developer": "Cache antigo",
                        "year": 1999,
                    }
                ]
            }
        )
    )
    with StateStore(paths.state_db()) as store:
        store.migrate()
        StateStoreGameMetadataAdapter(store.adapter_connection()).merge_provider_fields(
            game_id=GAME,
            title="Jogo de fixture",
            platform_id="nes-famicom",
            path="/fixtures/game.nes",
            fields=fields,
            source="fixture",
            confidence=1.0,
        )
    controller = EmulationController(store_factory=lambda: StateStore(paths.state_db()))
    central = controller._attach_game_metadata([{"id": GAME}])[0]["metadata"]
    media_root = paths.media_dir()
    masters = {}
    for role in ("boxart", "fanart", "logo"):
        image = media_root / "masters" / f"{role}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"fixture: not a real image")
        masters[role] = str(image.relative_to(media_root))
    registry = media_root / "registry" / "assignments-v1.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "entries": [
                    {"gameId": GAME, "platformId": "nes-famicom", "masters": masters},
                    {"gameId": "outside", "platformId": "nes-famicom", "masters": masters},
                ]
            }
        )
    )
    monkeypatch.setattr("steamzero.launcher.app._steam_catalog", lambda: ())
    monkeypatch.setattr("steamzero.launcher.app._host_accessibility", lambda: {})
    observed = []
    public_rows = []

    def capture_public_row(record, *, source):
        row = project_game_row(record, source=source)
        public_rows.append(row)
        return row

    monkeypatch.setattr("steamzero.launcher.app.project_game_row", capture_public_row)

    def capture(bridge):
        observed.append(bridge)
        return 0

    monkeypatch.setattr("steamzero.adapters.launcher_ui.launch_launcher_ui", capture)
    for _ in range(2):
        assert main(["--library", str(library)]) == 0
        bridge = observed[-1]
        item = bridge.model()["sections"][0]["items"][0]
        assert item["description"] == FIELDS["description"]
        assert item["gameMetadata"] == central
        for field, value in fields.items():
            assert item[field] == value
            assert item["gameMetadata"]["sources"][field] == "fixture"
        assert item["id"] == GAME
        assert all(item[key].startswith("file://") for key in ("coverUrl", "fanartUrl", "logoUrl"))
        expected_year = 1985 if has_canonical_date else 1999
        assert public_rows[-1]["year"] == expected_year
        if has_canonical_date:
            assert bridge.search("Jogo")["games"][0]["releaseDate"] == FIELDS["releaseDate"]
        assert bridge._catalog_records[GAME]["developer"] == FIELDS["developer"]
        assert "path" not in item["gameMetadata"]["fields"]
        assert len(bridge.model()["sections"][0]["items"]) == 1
