# SPDX-License-Identifier: GPL-3.0-or-later
"""D-08: o 409 estruturado de lançamento aparece na sobreposição de jornada.

Reprodução do registro da jornada física
(docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/
12-defeitos-registrados.txt): o lançamento bloqueado devolve o 409 estruturado
da D-17 pela API, mas a overlay de jornada voltava ao estado normal — o erro
não tinha superfície. A cena exerce o caminho de produção completo: P na
Jornada → POST /journey/event (operationRequest de lançamento) → POST /launch
→ 409 (a ``on_launch`` real recusa com detalhe privado) → restauração da
sobreposição, que agora precisa publicar ``code``, motivo, impacto e a única
ação que resolve, sem vazar o texto da exceção.

Fix round 1: a mesma cena prova o ciclo de vida do 409 pendente — publicado
uma única vez por um refresh limpo, e descartado por refreshs que não o
consomem (não-200 ou applyView recusado) para não ressurgir em janela sem
recusa recente.

Como no golden do D-10, o passe não vale por silêncio: a saída do
qmltestrunner precisa localizar o nó da sobreposição e executar a medição
(linha PASS específica + totais sem falha); um harness quebrado reprova alto.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from tests.integration.test_launcher_journey_e2e import _document
from tests.integration.test_launcher_session_footer_observed import (
    ROOT,
    RUNNER,
    _qml_environment,
)

from steamzero.adapters.journey_public import journey_public_field_types, project_game_row
from steamzero.adapters.launcher_ui import LauncherBridge
from steamzero.adapters.session_overlay import SessionOverlayAdapter
from steamzero.domain.experience_journey import JourneyDocument, JourneyStore
from steamzero.launcher.app import build_sections, build_titles
from steamzero.launcher.journey_runtime import JourneyRuntime

CONFIG = ROOT / "build" / "launcher-journey-launch-error-d08.json"
HARNESS = ROOT / "tests" / "qml" / "launcher" / "check_launcher_journey_launch_error.qml"
PRIVATE_DETAIL = "recusa privada /caminho-local/celeste.rom"

_SCENE_PASSES = (
    re.compile(
        r"PASS\s*:\s*\S*::LauncherJourneyLaunchError::"
        r"test_structured_409_surfaces_on_the_journey_overlay\b"
    ),
    re.compile(
        r"PASS\s*:\s*\S*::LauncherJourneyLaunchError::"
        r"test_pending_launch_error_does_not_resurface_after_a_failed_refresh\b"
    ),
    re.compile(
        r"PASS\s*:\s*\S*::LauncherJourneyLaunchError::"
        r"test_pending_launch_error_is_cleared_when_apply_view_fails\b"
    ),
)
_TOTALS = re.compile(r"Totals:\s*(\d+) passed,\s*(\d+) failed")


class _D08Session:
    """Sessão que nunca nasce: o lançamento recusa antes de abrir qualquer cosa."""

    def __init__(self) -> None:
        self.game_id = "celeste"
        self.id: str | None = None
        self.state = "none"
        self.current = self

    def observe(self, _game_id: str) -> dict[str, Any]:
        return {"gameId": self.game_id, "sessionId": self.id, "state": self.state}


def _bridge(tmp_path: Path) -> LauncherBridge:
    tmp_path.mkdir(parents=True, exist_ok=True)
    document_data = json.loads(_document().serialize())
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
    session = _D08Session()
    overlay = SessionOverlayAdapter(
        session.observe,
        lambda session_id, game_id: None,
    )
    library_rows = [{"id": "celeste", "title": "Celeste", "section": "library"}]

    def on_launch(_game_id: str, _focus_id: str) -> None:
        # Exatamente o contrato da D-17: um texto privado jamais pode chegar à
        # superfície; só o corpo estruturado do 409 é publicável.
        raise OSError(PRIVATE_DETAIL)

    return LauncherBridge(
        sections=build_sections(library_rows),
        titles=build_titles(library_rows),
        context_path=tmp_path / "return-context.json",
        on_launch=on_launch,
        session_observer=session.observe,
        session_overlay=overlay,
        journey_runtime=runtime,
    )


@pytest.mark.visual
def test_journey_overlay_surfaces_the_structured_launch_error(
    tmp_path: Path,
) -> None:
    """D-08 na cena: o 409 estruturado chega à overlay de jornada pelo caminho do P."""
    assert RUNNER is not None, "qmltestrunner Qt 6 é obrigatório para esta prova"
    assert not CONFIG.exists(), "há um arquivo efêmero anterior que precisa ser inspecionado"
    bridge = _bridge(tmp_path / "bridge")
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
                [str(RUNNER), "-input", str(HARNESS)],
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
    assert completed.returncode == 0, f"o 409 não chegou à sobreposição:\n{output[-7000:]}"
    assert "FAIL!" not in output, f"assertion QML reprovou:\n{output[-7000:]}"
    # Saída limpa (mesma diagonal de _assert_qml_clean): um TypeError residual
    # — como requisição órfã destruída com a cena — reprova o passe.
    unexpected = [
        line
        for line in output.splitlines()
        if any(
            needle in line
            for needle in (
                "Binding loop",
                "Unable to assign",
                "TypeError:",
                "ReferenceError:",
                "QFATAL",
            )
        )
    ]
    assert not unexpected, (
        "a cena D-08 emitiu diagnósticos QML inesperados:\n"
        + "\n".join(unexpected)
        + f"\nsaída:\n{output[-7000:]}"
    )
    # Guarda anti-vácuo: o passe só vale se a corrida localizou a sobreposição
    # e percorreu o caminho play → /launch → 409 → restauração até a medição,
    # incluindo os dois refreshs que não consomem o pendente (fix round 1).
    missing = [pattern.pattern for pattern in _SCENE_PASSES if not pattern.search(output)]
    assert not missing, (
        f"a cena D-08 não executou todas as medições; saída do qmltestrunner:\n{output[-7000:]}"
    )
    totals = _TOTALS.search(output)
    assert totals is not None, (
        f"a cena D-08 não publicou totais de execução;\nsaída:\n{output[-7000:]}"
    )
    passed, failed = (int(value) for value in totals.groups())
    assert failed == 0 and passed >= 4, (
        f"D-08: esperado a suíte completa (initTestCase + três medições) sem falhas, "
        f"obtido {passed} passed, {failed} failed"
    )


def test_launch_refusal_keeps_the_private_detail_out_of_the_409(
    tmp_path: Path,
) -> None:
    """A recusa usada pela cena publica o contrato estruturado da D-17, não o texto privado.

    Prova de ponte do mesmo corpo 409 que a overlay deve mostrar: code, causa,
    impacto, nextAction — e jamais o detalhe privado da exceção.
    """
    bridge = _bridge(tmp_path)
    with bridge.serving() as base:
        request = urllib.request.Request(  # noqa: S310 - alvo é o loopback da própria prova
            base + "/launch",
            data=json.dumps({"gameId": "celeste", "focusId": "library:celeste"}).encode("utf-8"),
            headers={"X-SteamZero-Token": bridge.token, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request, timeout=5)  # noqa: S310
        assert failure.value.code == 409
        body = json.loads(failure.value.read())
    error = body["error"]
    assert error["code"] == "LAUNCHER-LAUNCH-FAILED-001"
    assert error["cause"] == "Não foi possível preparar o lançamento."
    assert error["impact"] == "O Launcher não confirmou o início do jogo."
    assert "Consulte o diagnóstico" in error["nextAction"]
    assert error["diagnosticId"]
    assert PRIVATE_DETAIL not in json.dumps(body)
