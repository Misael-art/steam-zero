# SPDX-License-Identifier: GPL-3.0-or-later
"""Contracts and concrete boundaries for AURA session peripherals."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from steamzero.adapters.session_peripherals import (
    RetroArchSessionPeripheral,
    cleanup_retroarch_session_artifacts,
    prepare_retroarch_session_config,
)
from steamzero.core import paths
from steamzero.domain.session_peripherals import resolve_session_peripherals


def test_resolver_bounds_and_hides_private_bezel_paths() -> None:
    model = resolve_session_peripherals(
        {
            "state": "ready",
            "activeDisc": 1,
            "discs": [
                {"id": "disc-0", "label": "A", "available": True},
                {"id": "disc-1", "label": "B", "available": True},
            ],
            "selectedBezel": "crt",
            "bezels": [
                {"id": "crt", "label": "CRT", "assetUrl": "/home/user/private.png"},
                {"id": "safe", "label": "Safe", "assetUrl": "asset://bezels/safe.png"},
            ],
            "fade": {"phase": "return", "progress": 2, "durationMs": 99999},
        },
        reduced_motion=True,
    )
    payload = model.to_dict()
    assert payload["activeDisc"] == 1
    assert payload["discs"][1]["inserted"] is True
    assert payload["bezels"][0]["assetUrl"] == ""
    assert payload["bezels"][0]["available"] is False
    assert payload["bezels"][1]["assetUrl"] == "asset://bezels/safe.png"
    assert payload["fade"] == {
        "phase": "return",
        "progress": 1.0,
        "durationMs": 10000,
        "reducedMotion": True,
    }


def test_retroarch_session_config_publishes_managed_aura_bezel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "config_home", lambda: tmp_path / "config")
    monkeypatch.setattr(paths, "saves_dir", lambda: tmp_path / "saves")

    config = prepare_retroarch_session_config()
    text = config.read_text(encoding="utf-8")
    bezel_config = config.parent / "aura-bezel-overlay.cfg"
    bezel_asset = config.parent / "aura-bezel.png"

    assert "SteamZero-Session-Managed: true" in text
    assert 'input_overlay_enable = "true"' in text
    assert f'input_overlay = "{bezel_config}"' in text
    bezel_text = bezel_config.read_text(encoding="utf-8")
    assert bezel_text.startswith("# SteamZero-Session-Managed: true")
    assert 'overlays = "1"' in bezel_text
    assert bezel_asset.is_file()
    assert bezel_asset.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_retroarch_session_config_creates_managed_state_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "config_home", lambda: tmp_path / "config")
    monkeypatch.setattr(paths, "saves_dir", lambda: tmp_path / "saves")

    prepare_retroarch_session_config()

    state_root = tmp_path / "saves" / "states"
    assert state_root.is_dir()
    assert state_root.stat().st_mode & 0o777 == 0o700


def test_retroarch_complete_peripheral_projection_uses_logical_bezel_asset(
    tmp_path: Path,
) -> None:
    content = tmp_path / "game.sfc"
    content.write_bytes(b"content")
    projection = RetroArchSessionPeripheral(content, tmp_path / "states").list_peripherals()

    assert projection["state"] == "ready"
    assert projection["selectedBezel"] == "aura-default"
    assert projection["appliedBezel"] is None
    assert projection["bezelExecutionState"] == "launch-configured-unconfirmed"
    assert len(projection["bezels"]) == 1
    assert projection["bezels"][0]["id"] == "aura-default"
    assert projection["bezels"][0]["assetUrl"] == "asset://bezels/aura-bezel.svg"
    assert projection["bezels"][0]["selected"] is True
    assert projection["bezels"][0]["applied"] is False
    assert projection["bezels"][0]["executionState"] == "launch-configured-unconfirmed"
    assert projection["fade"] == {"phase": "idle", "progress": 0.0, "durationMs": 180}


def test_custom_bezel_config_is_session_private_and_cleanup_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PIL import Image

    monkeypatch.setattr(paths, "config_home", lambda: tmp_path / "config")
    monkeypatch.setattr(paths, "saves_dir", lambda: tmp_path / "saves")
    output = io.BytesIO()
    Image.new("RGBA", (20, 12), (90, 30, 10, 255)).save(output, format="PNG")
    png = output.getvalue()
    resource_id = "asset://bezels/org.test.bezel@1.0.0-" + hashlib.sha256(png).hexdigest() + ".png"
    session_id = "A" * 26
    unrelated_config = tmp_path / "config" / "retroarch" / "retroarch.cfg"
    unrelated_config.parent.mkdir(parents=True)
    unrelated_config.write_text("third-party = true\n", encoding="utf-8")

    config = prepare_retroarch_session_config(
        resource_id,
        session_id=session_id,
        resolved_bezel={
            "resourceId": resource_id,
            "_sourceBytes": png,
            "available": True,
            "compatible": True,
            "origin": "custom-theme",
            "themeId": "org.test.bezel",
            "version": "1.0.0",
            "license": "CC-BY-4.0",
        },
    )
    overlay_config = config.parent / "aura-bezel-overlay.cfg"
    overlay_asset = config.parent / "aura-bezel.png"
    session_text = config.read_text(encoding="utf-8")
    assert config.parent.parent.name == "sessions"
    assert config.parent.name == session_id
    assert f'input_overlay = "{overlay_config}"' in session_text
    assert 'config_save_on_exit = "false"' in session_text
    assert overlay_asset.read_bytes() == png
    assert unrelated_config.read_text(encoding="utf-8") == "third-party = true\n"
    assert cleanup_retroarch_session_artifacts(session_id, config_home=tmp_path / "config") is True
    assert cleanup_retroarch_session_artifacts(session_id, config_home=tmp_path / "config") is True
    assert config.parent.is_dir()
    assert list(config.parent.iterdir()) == []
    assert unrelated_config.read_text(encoding="utf-8") == "third-party = true\n"


def test_session_read_model_preserves_custom_uri_and_does_not_claim_applied(
    tmp_path: Path,
) -> None:
    content = tmp_path / "game.sfc"
    content.write_bytes(b"content")
    resource_id = "asset://bezels/org.test.bezel@1.0.0-" + "b" * 64 + ".png"
    selected = {
        "id": resource_id,
        "resourceId": resource_id,
        "assetUrl": resource_id,
        "label": "Test bezel",
        "origin": "custom-theme",
        "themeId": "org.test.bezel",
        "version": "1.0.0",
        "license": "CC-BY-4.0",
        "format": "png",
        "available": True,
        "compatible": True,
        "applyMode": "next-launch",
    }
    adapter = RetroArchSessionPeripheral(
        content,
        tmp_path / "states",
        bezel_resource=selected,
        bezel_catalog=[selected],
    )
    projection = resolve_session_peripherals(adapter.list_peripherals()).to_dict()
    bezel = projection["bezels"][0]
    assert bezel["id"] == resource_id
    assert bezel["assetUrl"] == resource_id
    assert bezel["selected"] is True
    assert bezel["applied"] is False
    assert bezel["executionState"] == "launch-configured-unconfirmed"
    assert "pixels" in bezel["reason"]


def test_retroarch_save_state_slot_zero_waits_for_a_real_file(tmp_path: Path) -> None:
    commands: list[str] = []
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    states = tmp_path / "states"
    states.mkdir()

    def send(command: str) -> None:
        commands.append(command)
        (states / "game.state").write_bytes(b"real-state")

    adapter = RetroArchSessionPeripheral(content, states, send_command=send, sleep=lambda _: None)
    result = adapter.save_state(0)
    assert result.state == "running"
    assert commands == ["SAVE_STATE"]
    assert adapter.list_save_states()["entries"][0]["compatibility"] == "native"


def test_retroarch_save_state_backups_the_previous_snapshot_atomically(tmp_path: Path) -> None:
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    states = tmp_path / "states"
    states.mkdir()
    previous = states / "game.state"
    previous.write_bytes(b"previous")

    def send(command: str) -> None:
        assert command == "SAVE_STATE"
        previous.write_bytes(b"next")

    adapter = RetroArchSessionPeripheral(content, states, send_command=send, sleep=lambda _: None)
    adapter.save_state(0)

    assert (states / ".backups" / "game.slot0.state").read_bytes() == b"previous"
    assert adapter.list_save_states()["entries"][0]["backupAvailable"] is True


def test_retroarch_gallery_saves_and_loads_a_bounded_nonzero_slot(tmp_path: Path) -> None:
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    states = tmp_path / "states"
    states.mkdir()
    commands: list[str] = []

    def send(command: str) -> None:
        commands.append(command)
        if command == "SAVE_STATE":
            (states / "game.state2").write_bytes(b"slot-two")

    adapter = RetroArchSessionPeripheral(content, states, send_command=send, sleep=lambda _: None)
    adapter.save_state(2)
    assert commands == ["STATE_SLOT_PLUS", "STATE_SLOT_PLUS", "SAVE_STATE"]
    assert adapter.load_state(2).state == "running"
    assert commands[-1] == "LOAD_STATE_SLOT 2"


def test_retroarch_session_cursor_starts_from_per_content_runtime_log(tmp_path: Path) -> None:
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    states = tmp_path / "states"
    (states / "Core Name").mkdir(parents=True)
    logs = tmp_path / "logs" / "Core Name"
    logs.mkdir(parents=True)
    (logs / "game.lrtl").write_text('{"state_slot":"1"}', encoding="utf-8")
    commands: list[str] = []

    def send(command: str) -> None:
        commands.append(command)
        if command == "SAVE_STATE":
            (states / "Core Name" / "game.state3").write_bytes(b"slot-three")

    adapter = RetroArchSessionPeripheral(
        content,
        states,
        send_command=send,
        sleep=lambda _: None,
        runtime_log_root=tmp_path / "logs",
    )
    adapter.save_state(3)

    assert commands == ["STATE_SLOT_PLUS", "STATE_SLOT_PLUS", "SAVE_STATE"]


def test_retroarch_invalid_runtime_log_falls_back_to_slot_zero(tmp_path: Path) -> None:
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    logs = tmp_path / "logs" / "Core Name"
    logs.mkdir(parents=True)
    (logs / "game.lrtl").write_text("not-json", encoding="utf-8")

    adapter = RetroArchSessionPeripheral(
        content,
        tmp_path / "states",
        send_command=lambda _: None,
        sleep=lambda _: None,
        runtime_log_root=tmp_path / "logs",
    )

    assert adapter._state_slot == 0


def test_retroarch_slot_commands_are_settled_before_the_next_command(tmp_path: Path) -> None:
    content = tmp_path / "game.zip"
    content.write_bytes(b"content")
    states = tmp_path / "states"
    states.mkdir()
    commands: list[str] = []
    settles: list[float] = []

    def send(command: str) -> None:
        commands.append(command)
        if command == "SAVE_STATE":
            (states / "game.state3").write_bytes(b"slot-three")

    adapter = RetroArchSessionPeripheral(
        content,
        states,
        send_command=send,
        sleep=settles.append,
    )
    adapter.save_state(3)

    assert commands == ["STATE_SLOT_PLUS", "STATE_SLOT_PLUS", "STATE_SLOT_PLUS", "SAVE_STATE"]
    assert settles[:3] == [0.05, 0.05, 0.05]
    assert settles[-1] == 0.05


def test_retroarch_bounds_save_slots_and_supports_m3u_swap(tmp_path: Path) -> None:
    first = tmp_path / "disc-one.cue"
    second = tmp_path / "disc-two.cue"
    first.write_text("FILE one.bin BINARY\n", encoding="utf-8")
    second.write_text("FILE two.bin BINARY\n", encoding="utf-8")
    playlist = tmp_path / "game.m3u"
    playlist.write_text("disc-one.cue\ndisc-two.cue\n", encoding="utf-8")
    commands: list[str] = []
    adapter = RetroArchSessionPeripheral(
        playlist, tmp_path / "states", send_command=commands.append, sleep=lambda _: None
    )
    with pytest.raises(ValueError, match=r"limite 0\.\.31"):
        adapter.save_state(32)
    assert adapter.list_discs()["discs"][1]["label"] == "disc-two.cue"
    adapter.swap_disc("disc-1")
    assert commands == ["DISK_EJECT_TOGGLE", "DISK_NEXT", "DISK_EJECT_TOGGLE"]


def test_retroarch_managed_m3u_preserves_stable_disc_identity(tmp_path: Path) -> None:
    first = tmp_path / "converted-disc-one.chd"
    second = tmp_path / "converted-disc-two.chd"
    first.write_bytes(b"disc-one")
    second.write_bytes(b"disc-two")
    playlist = tmp_path / "game.m3u"
    playlist.write_text(
        "\n".join(
            (
                "# SteamZero-MultiDisc-Managed: true",
                "# SteamZero-MultiDisc-Set: psx:game",
                "# SteamZero-MultiDisc-Disc: psx:game:disc-1",
                first.name,
                "# SteamZero-MultiDisc-Disc: psx:game:disc-2",
                second.name,
                "",
            )
        ),
        encoding="utf-8",
    )
    commands: list[str] = []
    adapter = RetroArchSessionPeripheral(
        playlist, tmp_path / "states", send_command=commands.append, sleep=lambda _: None
    )

    discs = adapter.list_discs()["discs"]
    assert [entry["id"] for entry in discs] == ["psx:game:disc-1", "psx:game:disc-2"]
    adapter.swap_disc("psx:game:disc-2")
    assert commands == ["DISK_EJECT_TOGGLE", "DISK_NEXT", "DISK_EJECT_TOGGLE"]
