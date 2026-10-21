# SPDX-License-Identifier: GPL-3.0-or-later
"""A busca de mídia também funde metadados descritivos no registro do jogo (R2)."""

from __future__ import annotations

from pathlib import Path

from steamzero.adapters.emulation import EmulationController, SessionSecretStore
from steamzero.adapters.state_store_game_metadata import StateStoreGameMetadataAdapter
from steamzero.core.errors import SteamZeroError
from steamzero.core.state import StateStore
from steamzero.ports import GameIdentity, MediaCandidate

GAME = "01J9ZK3Q4M5N6P7R8S9T0V1W2X"
METADATA = {
    "description": "English description.",
    "developer": "Nintendo R&D4",
    "releaseDate": "1985-10-18",
    "genres": ["Platform"],
}


class MetadataProvider:
    """Provider com ``search_with_metadata``, como o ScreenScraper."""

    def __init__(self, *, error_code: str | None = None) -> None:
        self.error_code = error_code

    @property
    def name(self) -> str:
        return "screenscraper"

    def supported_kinds(self) -> frozenset[str]:
        return frozenset({"boxart"})

    def supported_platforms(self) -> frozenset[str]:
        return frozenset({"nes-famicom"})

    def search(
        self, identity: GameIdentity, media_kinds: list[str], _region: list[str] | None = None
    ) -> list[MediaCandidate]:
        return self.search_with_metadata(identity, media_kinds)[0]

    def search_with_metadata(
        self, identity: GameIdentity, media_kinds: list[str], _region: list[str] | None = None
    ) -> tuple[list[MediaCandidate], dict[str, object]]:
        if self.error_code is not None:
            raise SteamZeroError(self.error_code, detail="falha simulada")
        candidate = MediaCandidate(
            url="https://example.com/box.png",
            media_kind="boxart",
            provider=self.name,
            confidence=1.0,
        )
        return [candidate], dict(METADATA)


def _controller(tmp_path: Path, provider: MetadataProvider) -> EmulationController:
    return EmulationController(
        store_factory=lambda: StateStore(tmp_path / "state.db"),
        which=lambda _command: None,
        spawn=lambda _argv: None,
        secret_store=SessionSecretStore(),
        media_providers=[provider],
        media_retry_delay=lambda _delay: None,
    )


def _run(controller: EmulationController, *, game_path: str = "/roms/nes/smb.nes") -> dict:
    job = controller._jobs.create(
        "media.search",
        params={
            "game_id": GAME,
            "title_id": "",
            "title": "Super Mario Bros.",
            "platform_slug": "nes-famicom",
            "media_kinds": ["boxart"],
            "game_path": game_path,
        },
        priority="interactive",
        created_by="ui",
    )
    completed = controller._jobs.run(job.id)
    assert completed.state == "completed"
    assert isinstance(completed.result, dict)
    return completed.result


def _record(tmp_path: Path) -> dict | None:
    store = StateStore(tmp_path / "state.db")
    try:
        record = StateStoreGameMetadataAdapter(store.adapter_connection()).load(GAME)
        return record.to_mapping() if record else None
    finally:
        store.close()


def test_search_persists_descriptive_fields_with_provenance(tmp_path: Path) -> None:
    result = _run(_controller(tmp_path, MetadataProvider()))
    assert result["candidate_count"] == 1
    assert result["metadata"]["state"] == "updated"
    assert set(result["metadata"]["changed"]) == set(METADATA)
    record = _record(tmp_path)
    assert record is not None
    for key, value in METADATA.items():
        assert record[key] == value
        assert record["provenance"][key]["source"] == "screenscraper"


def test_provider_error_after_success_keeps_existing_metadata(tmp_path: Path) -> None:
    _run(_controller(tmp_path, MetadataProvider()))
    for code in ("E-SCRAPE-CREDENTIAL-REJECTED", "E-SCRAPE-QUOTA-EXCEEDED"):
        result = _run(_controller(tmp_path, MetadataProvider(error_code=code)))
        assert result["metadata"]["state"] == "no-metadata"
        record = _record(tmp_path)
        assert record is not None
        assert record["developer"] == "Nintendo R&D4"


def test_missing_game_path_skips_merge_instead_of_writing_invalid_record(
    tmp_path: Path,
) -> None:
    result = _run(_controller(tmp_path, MetadataProvider()), game_path="")
    assert result["metadata"]["state"] == "skipped-no-path"
    assert _record(tmp_path) is None


def test_view_exposes_fields_and_sources_and_degrades_on_unreadable_record(
    tmp_path: Path,
) -> None:
    from steamzero.adapters.state_store_game_metadata import public_view

    _run(_controller(tmp_path, MetadataProvider()))
    store = StateStore(tmp_path / "state.db")
    try:
        adapter = StateStoreGameMetadataAdapter(store.adapter_connection())
        view = public_view(adapter, GAME)
        assert view["state"] == "available"
        assert view["fields"] == METADATA
        assert view["sources"] == dict.fromkeys(METADATA, "screenscraper")
        assert "path" not in view["fields"]
        store.adapter_connection().execute(
            "UPDATE game_metadata SET record_json = '{broken' WHERE game_id = ?", (GAME,)
        )
        assert public_view(adapter, GAME)["state"] == "unreadable"
        assert public_view(adapter, "UNKNOWN")["state"] == "empty"
    finally:
        store.close()
