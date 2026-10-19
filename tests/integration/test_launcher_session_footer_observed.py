# SPDX-License-Identifier: GPL-3.0-or-later
"""Rodapé de sessão: capacidades nascem da sessão observada, não da seleção.

Reprodução objetiva de D-12 e D-22 do registro da jornada física
(docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/
12-defeitos-registrados.txt):

* D-22 — com uma sessão ativa e ``selectedItemId`` nulo no /model, todas as
  capacidades vinham indisponíveis com "Selecione um jogo com uma sessão
  observável.", inclusive Retomar e Sair, que o OSD oferecia habilitados.
* D-12 — Pausar/Salvar/Sair só ficavam ENABLED|FOCUSABLE depois do botão
  "Atualizar"; a régua de estados é
  docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/
  17-arvore-atspi-central-pos-bateria.txt (role|name|ENABLED,SENSITIVE,FOCUSABLE).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from tests.integration.test_launcher_journey_e2e import _document

from steamzero.adapters.journey_public import journey_public_field_types, project_game_row
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.domain.experience_journey import JourneyDocument, JourneyStore
from steamzero.launcher.app import build_sections, build_titles
from steamzero.launcher.journey_runtime import JourneyRuntime

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "build" / "launcher-session-footer-e2e.json"
FOOTER_HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_session_footer.qml"
SELECTION_REASON = "Selecione um jogo com uma sessão observável."

SESSION_EVENT_KEYS = ("pause", "resume", "open-saves", "save", "load", "exit")


def _qt6_runner() -> Path | None:
    for candidate in (
        Path("/usr/lib/qt6/bin/qmltestrunner"),
        Path("/usr/lib64/qt6/bin/qmltestrunner"),
    ):
        if candidate.is_file():
            return candidate
    found = shutil.which("qmltestrunner6") or shutil.which("qmltestrunner")
    return Path(found) if found else None


RUNNER = _qt6_runner()


class _FooterSession:
    """Sessão sintética do rodapé: nasce inexistente e é aberta pelo bridge."""

    def __init__(self) -> None:
        self.game_id = "celeste"
        self.id: str | None = None
        self.state = "none"
        # Contrato SessionControl: `_matching_control` exige control.current
        # apontando para o registro {id, game_id, state} da sessão viva.
        self.current = self
        self.saved: list[int] = []
        self.loaded: list[int] = []
        self.saved_slots: set[int] = {4}

    def observe(self, _game_id: str) -> dict[str, Any]:
        return {"gameId": self.game_id, "sessionId": self.id, "state": self.state}

    def open(self) -> None:
        self.id = "footer-session-celeste"
        self.state = "running"

    def suspend(self) -> None:
        self.state = "suspended"

    def close(self) -> None:
        # O registro canônico de sessão sobrevive ao encerramento com o mesmo
        # sessionId (estado "closed") — é a observação terminal que libera o
        # acompanhamento da ponte; apagar o id seria fabricar outra sessão.
        self.state = "closed"

    # Porta de controle exigida pelo SessionOverlayAdapter quando a sessão é
    # consistente (mesmo conjunto do fixture _JourneySessionControl do e2e).
    def list_save_states(self) -> list[dict[str, Any]]:
        return [
            {
                "slot": slot,
                "timestamp": "2026-10-12T12:00:00Z",
                "compatibility": "native",
                "available": True,
            }
            for slot in sorted(self.saved_slots)
        ]

    def save_state(self, slot: int) -> None:
        self.saved.append(slot)
        self.saved_slots.add(slot)

    def load_state(self, slot: int) -> None:
        self.loaded.append(slot)

    def request_exit(self, *, confirmed: bool) -> None:
        if not confirmed:
            raise AssertionError("a saída sintética exige confirmação explícita")
        self.close()


def _bridge(tmp_path: Path, session: _FooterSession) -> LauncherBridge:
    tmp_path.mkdir(parents=True, exist_ok=True)
    document_data = json.loads(_document().serialize())
    # A jornada física exercitava o menu de jogos, onde os eventos de sessão
    # do documento estão declarados; o defeito aparecia exatamente ali.
    document_data["entryMenuId"] = "games"
    document = JourneyDocument.parse(document_data)
    store = JourneyStore(tmp_path / "journey-store")
    store.root.mkdir()
    store.save(document)
    assert store.set_active(store.load(document.id)) is None
    row = project_game_row(
        {
            "id": "celeste",
            "title": "Celeste",
            "platform": "nes",
            "year": 2018,
            "genre": "Platformer",
        },
        source="emulation",
    )
    assert row is not None
    runtime = JourneyRuntime.from_store(
        store.root,
        read_models={
            "library.platforms": [
                {"id": "nes", "name": "NES", "state": "available", "gameCount": 1}
            ],
            "library.games": [row],
        },
        published_read_models={
            "library.platforms": {
                "id": "string",
                "name": "string",
                "state": "string",
                "gameCount": "integer",
            },
            "library.games": journey_public_field_types(),
        },
        source_states={"library.platforms": "available", "library.games": "available"},
        launchable_game_ids=("celeste",),
        theme_resolver=lambda stage_id, appearance: {
            "requestedThemeId": "org.steamzero.default",
            "resolutionState": "resolved",
            "resolved": {"color": {"accent": "#22d3ee", "text": "#f2f6fb"}},
        },
    )
    assert runtime is not None
    overlay = SessionOverlayAdapter(
        session.observe,
        lambda session_id, game_id: (
            session if (session_id, game_id) == (session.id, session.game_id) else None
        ),
    )
    library_rows = [{"id": "celeste", "title": "Celeste", "section": "library"}]

    def on_launch(game_id: str, _focus_id: str) -> None:
        assert game_id == session.game_id
        session.open()
        return None

    return LauncherBridge(
        sections=build_sections(library_rows),
        titles=build_titles(library_rows),
        context_path=tmp_path / "return-context.json",
        on_launch=on_launch,
        session_observer=session.observe,
        session_overlay=overlay,
        journey_runtime=runtime,
    )


def _journey(model: Mapping[str, Any]) -> dict[str, Any]:
    journey = model["journey"]
    assert isinstance(journey, dict)
    return journey


def test_suspended_session_without_selection_publishes_resume_and_exit(
    tmp_path: Path,
) -> None:
    """D-22: sessão observada suspensa + selectedItemId nulo → Retomar/Sair disponíveis.

    O estado é exatamente o da evidência física: sessão 01M4RYBPZ3X9PXX1JY37FEQ69H
    suspensa enquanto /model reportava selected=None/focus=None; o rodapé dizia
    "Selecione um jogo com uma sessão observável." para ações que o OSD oferecia
    habilitadas na mesma janela.
    """
    session = _FooterSession()
    bridge = _bridge(tmp_path, session)
    with bridge.serving() as base:
        assert session.id is None  # nenhuma sessão antes do lançamento
        launch = _post_json(
            base,
            "/launch",
            bridge.token,
            {"gameId": "celeste", "focusId": "library:celeste"},
        )
        assert launch == {"requestId": None}
        assert session.state == "running"
        session.suspend()

        model = _get_json(base, "/model", bridge.token)
        journey = _journey(model)
        assert journey["selectedItemId"] is None
        assert journey["session"]["state"] == "suspended"
        caps = journey["sessionCapabilities"]
        assert caps["resume"]["available"] is True
        assert caps["resume"]["reason"] == ""
        assert caps["exit"]["available"] is True
        assert caps["exit"]["reason"] == ""
        for key in SESSION_EVENT_KEYS:
            assert caps[key]["reason"] != SELECTION_REASON, (
                f"D-22: a capacidade {key!r} ainda culpa a ausência de seleção"
            )


def test_running_session_published_at_model_startup_without_any_refresh(
    tmp_path: Path,
) -> None:
    """D-12 na ponte: /model já publica Pausar/Salvar/Sair de uma sessão em execução.

    A régua 17-arvore-atspi-central-pos-bateria.txt exige ENABLED e FOCUSABLE
    nos três botões sem depender do botão "Atualizar". Na ponte isso significa
    que a própria resposta do /model — o snapshot que o processo consome ao
    nascer — tem de carregar as capacidades da sessão observada, sem nenhum
    POST /journey/event nem requisição de atualização intermediária.
    """
    session = _FooterSession()
    bridge = _bridge(tmp_path, session)
    journey = _journey(bridge.model())
    assert journey["sessionCapabilities"]["pause"]["available"] is False
    assert journey["selectedItemId"] is None

    bridge.launch("celeste", "library:celeste")
    assert session.state == "running"

    journey = _journey(bridge.model())
    assert journey["selectedItemId"] is None
    assert journey["session"]["state"] == "running"
    caps = journey["sessionCapabilities"]
    assert caps["pause"]["available"] is True
    assert caps["pause"]["reason"] == ""
    assert caps["save"]["available"] is True
    assert caps["save"]["reason"] == ""
    assert caps["exit"]["available"] is True
    assert caps["exit"]["reason"] == ""
    assert caps["resume"]["available"] is False
    for key in SESSION_EVENT_KEYS:
        assert caps[key]["reason"] != SELECTION_REASON


def test_no_session_and_no_selection_keeps_the_selection_reason(
    tmp_path: Path,
) -> None:
    """Guarda contra regressão: sem sessão observada, o motivo histórico permanece.

    D-22 exige que a sessão observada substitua a seleção; não exige (nem o
    layout permitiria) prometer capacidades onde não há sessão nenhuma. O
    motivo "Selecione um jogo com uma sessão observável." continua correto
    quando não há seleção E nenhuma sessão acompanhada pela ponte.
    """
    session = _FooterSession()
    bridge = _bridge(tmp_path, session)
    journey = _journey(bridge.model())
    assert journey["selectedItemId"] is None
    caps = journey["sessionCapabilities"]
    assert caps["pause"]["available"] is False
    assert caps["pause"]["reason"] == SELECTION_REASON
    assert caps["exit"]["available"] is False
    assert caps["exit"]["reason"] == SELECTION_REASON


def test_observed_session_fallback_is_released_after_terminal_observation(
    tmp_path: Path,
) -> None:
    """D-22 não pode fantasma: encerrada a sessão, o rodapé volta ao estado vazio."""
    session = _FooterSession()
    bridge = _bridge(tmp_path, session)
    bridge.launch("celeste", "library:celeste")
    journey = _journey(bridge.model())
    assert journey["sessionCapabilities"]["exit"]["available"] is True

    session.close()
    observation = bridge.session("celeste")
    assert observation["state"] == "closed"

    journey = _journey(bridge.model())
    caps = journey["sessionCapabilities"]
    assert caps["pause"]["available"] is False
    assert caps["pause"]["reason"] == SELECTION_REASON


def _get_json(base: str, route: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(base + route, headers={"X-SteamZero-Token": token})  # noqa: S310
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read())


def _post_json(base: str, route: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - helper targets the test's loopback bridge.
        base + route,
        data=json.dumps(payload, allow_nan=False).encode("utf-8"),
        headers={"X-SteamZero-Token": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read())


def _qml_environment(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "",
            "QML_XHR_ALLOW_FILE_READ": "1",
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        }
    )
    for key in (
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        Path(env[key]).mkdir(mode=0o700, parents=True, exist_ok=True)
    return env


@pytest.mark.visual
def test_session_footer_qml_enables_actions_without_the_refresh_button(
    tmp_path: Path,
) -> None:
    """D-12 na cena: LauncherMain observando a sessão habilita o rodapé sozinho.

    A cena é o caminho de produção: LauncherMain busca /model ao nascer
    (snapshot antigo, capacidades indisponíveis), o lançamento passa pelo bridge
    real e o shell entra em ``emulator-visible``. O polling de 400 ms observa a
    transição de estado e é ele — não o botão "Atualizar" — que devolve as
    capacidades ao rodapé. O harness nunca toca em ``journeyRefresh``; as
    asserções cobrem ENABLED (``enabled === true``) e o análogo QML do estado
    AT-SPI FOCUSABLE (``focusPolicy !== Qt.NoFocus``), conforme a régua
    17-arvore-atspi-central-pos-bateria.txt.
    """
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    assert not CONFIG.exists(), "há um arquivo efêmero anterior que precisa ser inspecionado"
    session = _FooterSession()
    bridge = _bridge(tmp_path / "bridge", session)
    env = _qml_environment(tmp_path)
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps({"apiUrl": "", "apiToken": ""}), encoding="utf-8")
    try:
        with bridge.serving() as base:
            CONFIG.write_text(
                json.dumps({"apiUrl": base, "apiToken": bridge.token}),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(RUNNER), "-input", str(FOOTER_HARNESS)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
    finally:
        CONFIG.unlink(missing_ok=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, f"rodapé de sessão reprovou na cena:\n{output[-7000:]}"
    assert "FAIL!" not in output, f"assertion QML reprovou:\n{output[-7000:]}"
