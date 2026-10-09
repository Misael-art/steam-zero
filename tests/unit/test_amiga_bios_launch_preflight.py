# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from steamzero.adapters.emulation import EmulationController
from steamzero.core.errors import SteamZeroError


def _preflight_controller(
    monkeypatch, tmp_path: Path, *, bios_present: bool
) -> EmulationController:  # type: ignore[no-untyped-def]
    controller = EmulationController.__new__(EmulationController)
    rom = tmp_path / "game.adf"
    rom.write_bytes(b"fixture")
    monkeypatch.setattr(
        controller,
        "_current_game",
        lambda _game_id: {
            "platformId": "amiga",
            "path": str(rom),
            "evidence": "rom",
            "format": "adf",
            "contentKind": "base",
        },
    )
    monkeypatch.setattr(
        controller, "_load_game_settings", lambda *, strict: {"emulatorId": "retroarch"}
    )
    monkeypatch.setattr(
        controller, "_settings_for_game_with_global", lambda _game, settings: settings
    )
    monkeypatch.setattr(controller, "_require_launchable_emulator", lambda _emulator: None)
    monkeypatch.setattr(
        controller,
        "_launch_profile_for",
        lambda _platform, _emulator: SimpleNamespace(requires_bios=("kick34005.A500",)),
    )
    monkeypatch.setattr(
        controller, "_bios_present_for", lambda _platform, _emulator, _name: bios_present
    )
    monkeypatch.setattr(controller, "_bios_projection_copies", lambda _platform, _emulator: [])
    monkeypatch.setattr(
        controller,
        "_emulator_source",
        lambda _emulator: pytest.fail(
            "o preflight de BIOS deveria encerrar antes do source lookup"
        ),
    )
    return controller


def test_launch_preflight_blocks_when_declared_bios_is_missing(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    controller = _preflight_controller(monkeypatch, tmp_path, bios_present=False)

    with pytest.raises(SteamZeroError) as excinfo:
        controller._launch_preflight("game")

    assert excinfo.value.code == "E-CONTENT-BIOS-MISSING"
    assert "kick34005.A500" in str(excinfo.value.detail)


def test_launch_preflight_blocks_bios_imported_but_not_projected(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    controller = _preflight_controller(monkeypatch, tmp_path, bios_present=True)
    target = tmp_path / "retroarch" / "system" / "kick34005.A500"
    monkeypatch.setattr(
        controller,
        "_bios_projection_copies",
        lambda _platform, _emulator: [(tmp_path / "bios" / "kick34005.A500", target)],
    )

    with pytest.raises(SteamZeroError) as excinfo:
        controller._launch_preflight("game")

    assert excinfo.value.code == "E-CONTENT-BIOS-MISSING"
    assert str(target) in str(excinfo.value.detail)


def test_prepare_launch_projects_imported_bios_so_play_needs_no_manual_link(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    from steamzero.adapters import emulation as emulation_module

    controller = _preflight_controller(monkeypatch, tmp_path, bios_present=True)
    source = tmp_path / "bios" / "kick34005.A500"
    source.parent.mkdir()
    source.write_bytes(b"kickstart")
    target = tmp_path / "retroarch" / "system" / "kick34005.A500"
    copies = [(source, target)]
    applied: list[object] = []
    monkeypatch.setattr(controller, "_bios_projection_copies", lambda _p, _e: copies)
    monkeypatch.setattr(controller, "_compatible_root", lambda _targets: tmp_path)
    plan = SimpleNamespace(plan_id="p1", confirm_token="t1")
    monkeypatch.setattr(
        emulation_module.transaction, "plan_copy_files", lambda c, **_kw: applied.append(c) or plan
    )
    monkeypatch.setattr(
        emulation_module.transaction,
        "apply",
        lambda pid, token: applied.append((pid, token)),
    )

    controller._prepare_launch("game")

    assert applied == [copies, ("p1", "t1")]


def test_prepare_launch_ignores_blockers_and_leaves_reason_to_preflight(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    controller = _preflight_controller(monkeypatch, tmp_path, bios_present=False)

    def _missing(_platform: str, _emulator: str) -> list[tuple[Path, Path]]:
        raise SteamZeroError("E-CONTENT-BIOS-MISSING", detail="importe a BIOS")

    monkeypatch.setattr(controller, "_bios_projection_copies", _missing)

    controller._prepare_launch("game")  # não levanta: o preflight reporta o motivo


def test_readiness_treats_unprojected_imported_bios_as_playable(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    controller = _preflight_controller(monkeypatch, tmp_path, bios_present=True)
    target = tmp_path / "retroarch" / "system" / "kick34005.A500"
    monkeypatch.setattr(
        controller,
        "_bios_projection_copies",
        lambda _platform, _emulator: [(tmp_path / "bios" / "kick34005.A500", target)],
    )

    class _PastBios(Exception):
        """Marca que o preflight passou do bloco de BIOS."""

    def _stop(_emulator: str) -> None:
        raise _PastBios

    monkeypatch.setattr(controller, "_emulator_source", _stop)

    # Passa do bloco de BIOS (a projeção é feita no launch); o que vier depois é
    # outro preflight, aqui interrompido de propósito.
    with pytest.raises(_PastBios):
        controller._launch_preflight("game", projection_ready=True)


def _archive_controller(monkeypatch, tmp_path: Path, name: str, evidence: str):  # type: ignore[no-untyped-def]
    controller = EmulationController.__new__(EmulationController)
    rom = tmp_path / name
    rom.write_bytes(b"x")
    monkeypatch.setattr(
        controller,
        "_current_game",
        lambda _id: {
            "platformId": "amiga",
            "systemId": "amiga",
            "name": "Jogo",
            "path": str(rom),
            "evidence": evidence,
        },
    )
    monkeypatch.setattr(controller, "_root_for_game", lambda _p: tmp_path.resolve())
    return controller


def test_prepare_game_extracts_archive_and_refreshes_catalog(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from steamzero.adapters import emulation as module

    controller = _archive_controller(monkeypatch, tmp_path, "jogo.zip", "archive-needs-extraction")
    ran: list[object] = []
    monkeypatch.setattr(
        module.ArchiveMaterializer,
        "run",
        lambda self, req, **kw: ran.append(req) or {"status": "ok"},
    )
    monkeypatch.setattr(controller, "_scan_library_now", lambda *a, **k: {"games": 7})

    out = controller.prepare_game("g")

    assert out["prepared"] is True
    assert out["catalogRefresh"] == {"status": "scanned", "games": 7}
    assert len(ran) == 1


def test_prepare_game_is_a_noop_for_plain_roms(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    controller = _archive_controller(monkeypatch, tmp_path, "jogo.adf", "rom")

    assert controller.prepare_game("g") == {
        "prepared": False,
        "reason": "nada a preparar para este jogo",
    }


def test_readiness_flags_archive_that_can_be_prepared(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from steamzero.adapters import emulation as module

    controller = _archive_controller(monkeypatch, tmp_path, "jogo.zip", "archive-needs-extraction")
    monkeypatch.setattr(
        controller, "_load_game_settings", lambda *, strict: {"emulatorId": "retroarch"}
    )
    monkeypatch.setattr(
        controller, "_settings_for_game_with_global", lambda _game, settings: settings
    )
    monkeypatch.setattr(controller, "_require_launchable_emulator", lambda _emulator: None)
    monkeypatch.setattr(
        module.ArchiveMaterializer,
        "inspect",
        lambda self, req: SimpleNamespace(state="needs-extraction"),
    )

    verdict = controller.game_readiness("g")

    assert verdict["playable"] is False
    assert verdict["canPrepare"] is True
