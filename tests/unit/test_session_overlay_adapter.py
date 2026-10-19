# SPDX-License-Identifier: GPL-3.0-or-later
"""Provas do adapter AURA entre read model e SessionManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from steamzero.adapters.session_control import E_SESSION_CHANNEL_SUSPENDED
from steamzero.adapters.session_overlay import (
    DIAG_SESSION_MISMATCH,
    SessionOverlayAdapter,
)
from steamzero.core.errors import SteamZeroError


@dataclass
class FakeSession:
    id: str = "session-1"
    game_id: str = "game-1"
    state: str = "running"


class FakeControl:
    def __init__(self, session: FakeSession) -> None:
        self.current = session
        self.calls: list[str] = []
        self.fail = False

    def suspend(self) -> FakeSession:
        self.calls.append("suspend")
        if self.fail:
            raise RuntimeError("flush indisponível")
        self.current.state = "suspended"
        return self.current

    def resume(self) -> FakeSession:
        self.calls.append("resume")
        self.current.state = "running"
        return self.current

    def request_exit(self, *, confirmed: bool) -> FakeSession:
        self.calls.append(f"exit:{confirmed}")
        if confirmed:
            self.current.state = "closing"
        return self.current


class WrongStateControl(FakeControl):
    def suspend(self) -> FakeSession:
        self.calls.append("suspend")
        return FakeSession(state="running")

    def resume(self) -> FakeSession:
        self.calls.append("resume")
        return FakeSession(state="suspended")


class SaveStateControl(FakeControl):
    def __init__(self, session: FakeSession) -> None:
        super().__init__(session)
        self.save_states = [
            {
                "slot": 2,
                "timestamp": "2026-09-13T20:00:00Z",
                "playtimeSeconds": 120,
                "thumbnailUrl": "asset://save-states/slot-2.png",
                "compatibility": "native",
                "backupAvailable": True,
            }
        ]

    def list_save_states(self) -> list[dict[str, Any]]:
        return self.save_states

    def save_state(self, slot: int) -> FakeSession:
        self.calls.append(f"save:{slot}")
        return self.current

    def load_state(self, slot: int) -> FakeSession:
        self.calls.append(f"load:{slot}")
        return self.current


class DiscControl(FakeControl):
    def list_discs(self) -> dict[str, Any]:
        return {
            "state": "ready",
            "activeDisc": 0,
            "discs": [
                {"id": "disc-0", "label": "Disco 1", "inserted": True},
                {"id": "disc-1", "label": "Disco 2", "inserted": False},
            ],
        }

    def swap_disc(self, disc_id: str) -> FakeSession:
        self.calls.append(f"disc:{disc_id}")
        return self.current


class EphemeralCommandControl(SaveStateControl, DiscControl):
    """Sessão com adapter RetroArch real: os quatro comandos transitórios existem."""

    def toggle_mute(self) -> FakeSession:
        self.calls.append("mute")
        return self.current

    def take_screenshot(self) -> FakeSession:
        self.calls.append("screenshot")
        return self.current

    def toggle_fast_forward(self) -> FakeSession:
        self.calls.append("fastForward")
        return self.current

    def step_rewind(self) -> FakeSession:
        self.calls.append("rewind")
        return self.current


class PeripheralControl(DiscControl):
    def list_peripherals(self) -> dict[str, Any]:
        return {
            "state": "ready",
            "activeDisc": 0,
            "discs": [
                {"id": "disc-0", "label": "Disco 1", "inserted": True},
                {"id": "disc-1", "label": "Disco 2", "inserted": False},
            ],
            "selectedBezel": "aura-default",
            "bezels": [
                {
                    "id": "aura-default",
                    "label": "AURA Cinema",
                    "assetUrl": "asset://bezels/aura-bezel.svg",
                    "available": True,
                    "selected": True,
                }
            ],
            "fade": {"phase": "idle", "progress": 0.0, "durationMs": 180},
        }


def make_adapter(control: FakeControl) -> SessionOverlayAdapter:
    def observe(_game_id: str) -> dict[str, Any]:
        return {
            "gameId": control.current.game_id,
            "sessionId": control.current.id,
            "state": control.current.state,
        }

    return SessionOverlayAdapter(
        observe,
        lambda session_id, game_id: (
            control
            if (session_id, game_id) == (control.current.id, control.current.game_id)
            else None
        ),
    )


def test_read_model_declares_real_pause_and_explicit_unsupported_actions() -> None:
    control = FakeControl(FakeSession())
    model = make_adapter(control).read_model("game-1", visible=True)

    capabilities = model["osd"]["capabilities"]
    assert model["session"] == {
        "gameId": "game-1",
        "sessionId": "session-1",
        "state": "running",
    }
    assert capabilities["pause"] == {"available": True, "reason": ""}
    assert capabilities["exit"] == {"available": True, "reason": ""}
    assert capabilities["saveState"]["available"] is False
    assert capabilities["saveState"]["reason"]


def test_dispatch_pause_and_resume_use_the_same_canonical_control() -> None:
    control = FakeControl(FakeSession())
    adapter = make_adapter(control)

    paused = adapter.dispatch("game-1", "session-1", "pause")
    resumed = adapter.dispatch("game-1", "session-1", "pause")

    assert paused.accepted is True
    assert paused.operation == "pause"
    assert paused.state == "suspended"
    assert resumed.accepted is True
    assert resumed.operation == "resume"
    assert resumed.state == "running"
    assert control.calls == ["suspend", "resume"]


@pytest.mark.parametrize(
    ("initial_state", "expected_state", "expected_operation"),
    [("running", "running", "suspend"), ("suspended", "suspended", "resume")],
)
def test_dispatch_never_accepts_an_unconfirmed_pause_state(
    initial_state: str, expected_state: str, expected_operation: str
) -> None:
    control = WrongStateControl(FakeSession(state=initial_state))

    result = make_adapter(control).dispatch("game-1", "session-1", "pause")

    assert result.accepted is False
    assert result.state == expected_state
    assert result.diagnostic == "AURA-SESSION-ADAPTER-003"
    assert control.calls == [expected_operation]


def test_dispatch_rejects_stale_session_before_calling_control() -> None:
    control = FakeControl(FakeSession())
    result = make_adapter(control).dispatch("game-1", "old-session", "pause")

    assert result.accepted is False
    assert result.diagnostic == DIAG_SESSION_MISMATCH
    assert control.calls == []


def test_exit_requires_explicit_confirmation_and_reports_closing_as_pending() -> None:
    control = FakeControl(FakeSession())
    adapter = make_adapter(control)

    rejected = adapter.dispatch("game-1", "session-1", "exit")
    assert rejected.accepted is False
    assert rejected.confirmed is False
    assert rejected.diagnostic == "AURA-SESSION-ADAPTER-005"
    assert control.calls == []

    requested = adapter.dispatch("game-1", "session-1", "exit", confirmed=True)
    assert requested.accepted is True
    assert requested.confirmed is False
    assert requested.operation == "exit"
    assert requested.state == "closing"
    assert requested.diagnostic == "AURA-SESSION-ADAPTER-006"
    assert control.calls == ["exit:True"]


def test_dispatch_keeps_unsupported_action_visible_without_side_effect() -> None:
    control = FakeControl(FakeSession())
    result = make_adapter(control).dispatch("game-1", "session-1", "saveState")

    assert result.accepted is False
    assert result.diagnostic == "AURA-OSD-ACTION-003"
    assert control.calls == []


def test_read_model_publishes_save_state_gallery_and_declares_real_operations() -> None:
    control = SaveStateControl(FakeSession())
    model = make_adapter(control).read_model("game-1", visible=True)

    assert model["osd"]["capabilities"]["saveState"] == {"available": True, "reason": ""}
    assert model["osd"]["capabilities"]["loadState"] == {"available": True, "reason": ""}
    assert model["saveStates"]["state"] == "ready"
    assert model["saveStates"]["entries"][0]["slot"] == 2
    assert model["saveStates"]["entries"][0]["backupAvailable"] is True


def test_save_and_load_dispatch_requires_a_bounded_slot_and_same_session() -> None:
    control = SaveStateControl(FakeSession())
    adapter = make_adapter(control)

    saved = adapter.dispatch("game-1", "session-1", "saveState", slot=2)
    loaded = adapter.dispatch("game-1", "session-1", "loadState", slot=2)

    assert saved.accepted is True
    assert saved.operation == "saveState"
    assert saved.slot == 2
    assert loaded.accepted is True
    assert loaded.operation == "loadState"
    assert loaded.slot == 2
    assert control.calls == ["save:2", "load:2"]


def test_save_state_without_slot_refuses_with_the_unified_range_message() -> None:
    """D-20: a recusa de slot da rota de sessão diz o mesmo que a /journey/event.

    O texto era o resíduo visível do defeito: o toque sem galeria chegava ao
    adapter sem slot e o jogador lia "slot de save-state inválido" enquanto a
    rota de jornada já sabia explicar a faixa e a recuperação.
    """
    control = SaveStateControl(FakeSession())
    result = make_adapter(control).dispatch("game-1", "session-1", "saveState")

    assert result.accepted is False
    assert result.diagnostic == "AURA-SESSION-ADAPTER-003"
    assert result.detail == "O slot de save-state deve estar entre 0 e 999."
    assert control.calls == []


def test_dispatch_returns_recoverable_error_when_session_operation_fails() -> None:
    control = FakeControl(FakeSession())
    control.fail = True
    result = make_adapter(control).dispatch("game-1", "session-1", "pause")

    assert result.accepted is False
    assert result.diagnostic == "AURA-SESSION-ADAPTER-003"
    assert result.state == "running"
    assert "flush indisponível" in result.detail


def test_disc_surface_is_available_only_from_a_multi_disc_adapter() -> None:
    control = DiscControl(FakeSession())
    adapter = make_adapter(control)

    model = adapter.read_model("game-1", visible=True)
    result = adapter.dispatch("game-1", "session-1", "swapDisc", disc_id="disc-1")

    assert model["osd"]["capabilities"]["swapDisc"] == {"available": True, "reason": ""}
    assert model["peripherals"]["discs"][1]["id"] == "disc-1"
    assert result.accepted is True
    assert result.disc_id == "disc-1"
    assert control.calls == ["disc:disc-1"]


def test_read_model_projects_declared_bezel_and_fade_from_complete_adapter() -> None:
    control = PeripheralControl(FakeSession())
    model = make_adapter(control).read_model("game-1", visible=True)

    assert model["peripherals"]["bezels"] == [
        {
            "id": "aura-default",
            "label": "AURA Cinema",
            "assetUrl": "asset://bezels/aura-bezel.svg",
            "available": True,
            "selected": True,
            "reason": "",
        }
    ]
    assert model["peripherals"]["fade"] == {
        "phase": "idle",
        "progress": 0.0,
        "durationMs": 180,
        "reducedMotion": False,
    }


def test_suspended_session_publishes_channel_actions_as_unavailable() -> None:
    """D-23: a OSD não pode oferecer "Galeria de saves" a uma árvore parada."""
    control = SaveStateControl(FakeSession(state="suspended"))
    model = make_adapter(control).read_model("game-1", visible=True)

    capabilities = model["osd"]["capabilities"]
    for action_id in ("saveState", "loadState"):
        assert capabilities[action_id] == {
            "available": False,
            "reason": "A sessão está suspensa; retome antes de salvar.",
        }

    disc_control = PeripheralControl(FakeSession(state="suspended"))
    disc_model = make_adapter(disc_control).read_model("game-1", visible=True)
    assert disc_model["osd"]["capabilities"]["swapDisc"] == {
        "available": False,
        "reason": "A sessão está suspensa; retome antes de salvar.",
    }


def test_dispatch_never_reaches_the_control_on_suspended_session() -> None:
    """A recusa publicada vale também para o despacho: nada é entregue ao canal parado."""
    control = SaveStateControl(FakeSession(state="suspended"))
    saved = make_adapter(control).dispatch("game-1", "session-1", "saveState", slot=2)
    assert saved.accepted is False
    assert saved.diagnostic == "AURA-OSD-ACTION-003"
    assert control.calls == []

    disc_control = PeripheralControl(FakeSession(state="suspended"))
    swapped = make_adapter(disc_control).dispatch(
        "game-1", "session-1", "swapDisc", disc_id="disc-1"
    )
    assert swapped.accepted is False
    assert swapped.diagnostic == "AURA-OSD-ACTION-003"
    assert disc_control.calls == []


class SuspendedChannelSaveControl(SaveStateControl):
    """Simula a corrida entre a leitura do estado e o gate do cliente (D-23)."""

    def save_state(self, slot: int) -> FakeSession:
        self.calls.append(f"save:{slot}")
        raise SteamZeroError(
            E_SESSION_CHANNEL_SUSPENDED,
            detail="saveState exige uma sessão viva; o pedido não foi enviado ao emulador.",
        )


def test_channel_suspension_maps_to_structured_refusal_with_next_action() -> None:
    control = SuspendedChannelSaveControl(FakeSession())
    result = make_adapter(control).dispatch("game-1", "session-1", "saveState", slot=2)

    assert result.accepted is False
    assert result.diagnostic == "AURA-SESSION-ADAPTER-007"
    assert result.detail == "A sessão está suspensa; o pedido não foi enviado ao emulador."
    body = result.to_dict()
    assert body["nextAction"] == "Retome a sessão e tente novamente."
    assert control.calls == ["save:2"]


def test_ephemeral_commands_are_published_only_when_the_adapter_has_the_port() -> None:
    """D-28: botão só existe se houver porta; sem porta, a recusa diz por quê."""
    plain_model = make_adapter(FakeControl(FakeSession())).read_model("game-1", visible=True)
    capabilities = plain_model["osd"]["capabilities"]
    for action_id in ("mute", "screenshot", "fastForward", "rewind"):
        assert capabilities[action_id]["available"] is False
        assert capabilities[action_id]["reason"]

    control = EphemeralCommandControl(FakeSession())
    model = make_adapter(control).read_model("game-1", visible=True)
    for action_id in ("mute", "screenshot", "fastForward", "rewind"):
        assert model["osd"]["capabilities"][action_id] == {"available": True, "reason": ""}


@pytest.mark.parametrize(
    ("action_id", "call"),
    [
        ("mute", "mute"),
        ("screenshot", "screenshot"),
        ("fastForward", "fastForward"),
        ("rewind", "rewind"),
    ],
)
def test_dispatch_routes_each_ephemeral_command_to_the_control_method(
    action_id: str, call: str
) -> None:
    control = EphemeralCommandControl(FakeSession())
    result = make_adapter(control).dispatch("game-1", "session-1", action_id)

    assert result.accepted is True
    assert result.operation == action_id
    assert control.calls == [call]


def test_suspended_session_refuses_ephemeral_commands_before_they_look_pressable() -> None:
    """D-23/D-28: o mesmo gate que barra o saveState barra os comandos novos."""
    control = EphemeralCommandControl(FakeSession(state="suspended"))
    model = make_adapter(control).read_model("game-1", visible=True)
    capabilities = model["osd"]["capabilities"]
    for action_id in ("mute", "screenshot", "fastForward", "rewind", "listSaveStates"):
        assert capabilities[action_id] == {
            "available": False,
            "reason": "A sessão está suspensa; retome antes de enviar um pedido ao emulador.",
        }

    result = make_adapter(control).dispatch("game-1", "session-1", "mute")
    assert result.accepted is False
    assert result.diagnostic == "AURA-OSD-ACTION-003"
    assert control.calls == []


def test_resume_is_the_explicit_non_toggle_alternative_to_pause() -> None:
    """D-28 passo 4: `resume` era aceito pelo backend e nunca tinha virado botão."""
    running = make_adapter(FakeControl(FakeSession())).read_model("game-1", visible=True)
    assert running["osd"]["capabilities"]["resume"]["available"] is False

    control = FakeControl(FakeSession(state="suspended"))
    model = make_adapter(control).read_model("game-1", visible=True)
    assert model["osd"]["capabilities"]["resume"] == {"available": True, "reason": ""}

    result = make_adapter(control).dispatch("game-1", "session-1", "resume")
    assert result.accepted is True
    assert result.operation == "resume"
    assert result.state == "running"
    assert control.calls == ["resume"]


def test_list_actions_reach_the_reader_port_of_the_canonical_control() -> None:
    """D-28 passo 4: as leituras aceitas pelo canal também viram ações declaradas."""
    control = EphemeralCommandControl(FakeSession())
    model = make_adapter(control).read_model("game-1", visible=True)
    for action_id in ("listSaveStates", "listDiscs"):
        assert model["osd"]["capabilities"][action_id] == {"available": True, "reason": ""}
    assert model["osd"]["capabilities"]["listPeripherals"]["available"] is False

    saved = make_adapter(control).dispatch("game-1", "session-1", "listSaveStates")
    assert saved.accepted is True
    assert saved.operation == "listSaveStates"

    peripheral_control = PeripheralControl(FakeSession())
    peripheral_model = make_adapter(peripheral_control).read_model("game-1", visible=True)
    assert peripheral_model["osd"]["capabilities"]["listPeripherals"] == {
        "available": True,
        "reason": "",
    }
    peripherals = make_adapter(peripheral_control).dispatch(
        "game-1", "session-1", "listPeripherals"
    )
    assert peripherals.accepted is True
    assert peripherals.operation == "listPeripherals"
