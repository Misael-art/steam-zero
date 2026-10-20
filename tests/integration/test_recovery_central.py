# SPDX-License-Identifier: GPL-3.0-or-later
"""R0/R1: persistência real isolada, readback e recusa por plataforma."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from steamzero.adapters.emulation import EmulationController, SessionSecretStore
from steamzero.adapters.flatpak import CommandResult, FlatpakCLI
from steamzero.adapters.registry import AdapterRegistry
from steamzero.core.errors import LaunchNotStartedError, SteamZeroError
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


def _catalog_controller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> tuple[EmulationController, list[dict[str, Any]], dict[str, bool], list[tuple[str, ...]]]:
    controller = _controller(tmp_path, monkeypatch)
    games = []
    for index in range(count):
        directory = tmp_path / f"game-{index}"
        directory.mkdir()
        game = _game(directory, "nes-famicom")
        game.update(id=f"nes-{index}", systemId="nes")
        games.append(game)
    monkeypatch.setattr(controller, "_load_library_cache", lambda: (games, 0))
    monkeypatch.setattr(controller, "library_roots", lambda: [str(tmp_path)])
    core = tmp_path / "mesen_libretro.so"
    core.write_bytes(b"readiness-only-core-fixture")
    monkeypatch.setattr("steamzero.adapters.emulation.find_core", lambda _core: core)
    source = AdapterRegistry.bundled().get("retroarch").preferred_source(None)
    deployment = {"installed": True}
    commands: list[tuple[str, ...]] = []

    def run(argv: Sequence[str], _timeout: float) -> CommandResult:
        commands.append(tuple(argv))
        if argv[1] == "list":
            return CommandResult(
                0, "org.libretro.RetroArch\tflathub\n" if deployment["installed"] else ""
            )
        assert argv[1] == "info"
        return CommandResult(0, source.version)

    monkeypatch.setattr(controller, "_flatpak_factory", lambda: FlatpakCLI(runner=run))
    return controller, games, deployment, commands


@pytest.mark.parametrize("count", [1, 100])
def test_catalog_probe_budget_preserves_per_game_truth_and_fresh_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    controller, games, deployment, commands = _catalog_controller(tmp_path, monkeypatch, count)
    try:
        rows = controller._enrich_platform_games(games)
        assert all(row["playAction"]["enabled"] for row in rows)
        # O orçamento depende dos adapters, não do tamanho do acervo: antes
        # cem jogos provocavam seiscentos comandos externos de instalação.
        assert len(commands) <= 4

        Path(games[0]["path"]).unlink()
        commands.clear()
        rows = controller._enrich_platform_games(games)
        assert rows[0]["playAction"]["enabled"] is False
        assert all(row["playAction"]["enabled"] for row in rows[1:])
        assert len(commands) <= 4

        deployment["installed"] = False
        if count > 1:
            assert controller.game_readiness(games[1]["id"])["playable"] is False
            with pytest.raises(LaunchNotStartedError):
                controller.launch_game(games[1]["id"])
        rows = controller._enrich_platform_games(games)
        assert all(row["playAction"]["enabled"] is False for row in rows)
    finally:
        controller.close()


def test_catalog_probe_scope_is_discarded_when_projection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, games, deployment, _commands = _catalog_controller(tmp_path, monkeypatch, 1)

    def fail(_game_id: str) -> dict[str, Any]:
        raise RuntimeError("projection interrupted")

    monkeypatch.setattr(controller, "game_readiness", fail)
    try:
        with pytest.raises(RuntimeError, match="projection interrupted"):
            controller._enrich_platform_games(games)
        deployment["installed"] = False
        with pytest.raises(SteamZeroError):
            controller._require_launchable_emulator("retroarch")
    finally:
        controller.close()


def test_catalog_probe_scope_does_not_hide_uninstall_from_another_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, games, deployment, _commands = _catalog_controller(tmp_path, monkeypatch, 2)
    observing = Event()
    release = Event()
    readiness = controller.game_readiness

    def paused(game_id: str) -> dict[str, Any]:
        result = readiness(game_id)
        if game_id == games[0]["id"]:
            observing.set()
            assert release.wait(5), "test did not release the snapshot request"
        return result

    monkeypatch.setattr(controller, "game_readiness", paused)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            snapshot = pool.submit(controller._enrich_platform_games, games)
            try:
                assert observing.wait(5), "snapshot did not observe the installed runtime"
                deployment["installed"] = False
                assert readiness(games[1]["id"])["playable"] is False
            finally:
                release.set()
            assert all(row["playAction"]["enabled"] for row in snapshot.result(timeout=5))
        assert readiness(games[1]["id"])["playable"] is False
    finally:
        controller.close()
