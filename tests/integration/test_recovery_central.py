# SPDX-License-Identifier: GPL-3.0-or-later
"""R0/R1: persistência real isolada, readback e recusa por plataforma."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from steamzero.adapters.emulation import EmulationController, SessionSecretStore
from steamzero.core.errors import SteamZeroError
from steamzero.core.state import StateStore


def _controller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EmulationController:
    for kind in ("STATE", "DATA", "CONFIG", "CACHE"):
        monkeypatch.setenv(f"XDG_{kind}_HOME", str(tmp_path / kind.lower()))
    return EmulationController(
        store_factory=lambda: StateStore(tmp_path / "state.db"),
        which=lambda _command: None,
        spawn=lambda _argv: pytest.fail("nenhum processo deve iniciar no readback"),
        secret_store=SessionSecretStore(),
    )


def _game(tmp_path: Path, platform: str) -> dict[str, Any]:
    rom = tmp_path / f"{platform}.rom"
    rom.write_bytes(b"isolated-test-fixture")
    stamp = rom.stat()
    fingerprint = hashlib.sha256(
        f"{rom}\0{stamp.st_size}\0{stamp.st_mtime_ns}".encode()
    ).hexdigest()
    return {
        "id": platform,
        "titleId": platform,
        "name": platform,
        "platformId": platform,
        "path": str(rom),
        "fingerprint": fingerprint,
        "state": "ready",
        "statusLabel": "Fixture",
    }


@pytest.mark.parametrize("platform", ["nes-famicom", "amiga"])
def test_emulator_preference_reopens_without_touching_other_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    controller = _controller(tmp_path, monkeypatch)
    game = _game(tmp_path, platform)
    monkeypatch.setattr(controller, "_load_library_cache", lambda: ([game], 0))
    monkeypatch.setattr(controller, "library_roots", lambda: [str(tmp_path)])
    # Uma preferência por jogo não deve gerar INIs, keys ou firmware do Switch.
    monkeypatch.setattr(
        controller, "_runtime_config_writes", lambda: pytest.fail("writer de outro runtime")
    )
    original = tmp_path / "config" / "owned-retroarch.cfg"
    original.parent.mkdir(exist_ok=True)
    original.write_bytes(b"video_driver = user-choice\n")
    try:
        plan = controller.plan_action(
            {"actionId": "game.emulator.set", "gameId": game["id"], "emulatorId": "retroarch"}
        )
        assert controller._load_game_settings(strict=True) == {}
        controller.apply_action(plan["planId"], plan["confirmToken"])
    finally:
        controller.close()

    reopened = _controller(tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(
            reopened, "game_readiness", lambda _id: {"playable": False, "reason": "core ausente"}
        )
        row = reopened._enrich_platform_games([game])[0]
        assert row["emulatorId"] == "retroarch"
        assert row["playAction"]["enabled"] is False
        assert row["playAction"]["reason"] == "core ausente"
        assert row["playAction"]["id"] == f"game.launch:{game['id']}"
        monkeypatch.setattr(
            reopened, "game_readiness", lambda _id: {"playable": True, "reason": ""}
        )
        assert reopened._enrich_platform_games([game])[0]["playAction"]["enabled"] is True
        assert set(reopened._load_game_settings(strict=True)) == {game["id"]}
        assert reopened._load_global_settings() == {}
        assert original.read_bytes() == b"video_driver = user-choice\n"
    finally:
        reopened.close()


def test_incompatible_emulator_is_refused_before_persisting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _controller(tmp_path, monkeypatch)
    game = _game(tmp_path, "nes-famicom")
    monkeypatch.setattr(controller, "_load_library_cache", lambda: ([game], 0))
    monkeypatch.setattr(controller, "library_roots", lambda: [str(tmp_path)])
    try:
        with pytest.raises(SteamZeroError) as rejected:
            controller.plan_action(
                {"actionId": "game.emulator.set", "gameId": game["id"], "emulatorId": "eden"}
            )
        assert rejected.value.code == "E-API-SCHEMA"
        assert controller._load_game_settings(strict=True) == {}
    finally:
        controller.close()


def test_bios_permission_failure_does_not_report_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _controller(tmp_path, monkeypatch)
    original_stat = Path.stat

    def unreadable(path: Path, *, follow_symlinks: bool = True) -> Any:
        if path.name == "kick34005.A500":
            raise PermissionError("isolated permission failure")
        return original_stat(path, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", unreadable)
    try:
        with pytest.raises(PermissionError):
            controller._bios_present_for("amiga", "retroarch", "kick34005.A500")
    finally:
        controller.close()
