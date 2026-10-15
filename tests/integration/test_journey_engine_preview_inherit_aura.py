# SPDX-License-Identifier: GPL-3.0-or-later
"""D-06 (Tarefa 11): o engine-preview abre o tema que o resolver realmente produziu.

Depois de d512dc8c um menu ``inherit-aura`` resolve para o builtin empacotado
``org.steamzero.aura``; a bridge precisa carregar esse tema (e não apenas o
``org.steamzero.default``) para que a pré-visualização não levante
``E-COMPONENT-DEGRADED``. Os caminhos ``custom`` e referência-ausente-como-
fallback também são travados aqui porque a cessão impede editar o arquivo e2e
original.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from steamzero.adapters.desktop_ui import DesktopControlServer
from steamzero.adapters.theme_catalog import read_builtin_manifest
from steamzero.core.state import StateStore
from steamzero.domain.desktop import DesktopContext, ExperienceCoordinator
from steamzero.domain.theme_editor import ThemeEditorManager

AURA_ID = "org.steamzero.aura"
DEFAULT_ID = "org.steamzero.default"


class _Context:
    def snapshot(self) -> DesktopContext:
        return DesktopContext(
            "linux",
            "wayland",
            (),
            False,
            False,
            False,
            frozenset(),
        )


class _PreviewDashboard:
    """Dashboard mínimo com o ThemeEditorManager real (temas empacotados)."""

    def __init__(self) -> None:
        self.theme_editor = ThemeEditorManager()
        self.loaded_theme_sessions: list[str] = []
        self.cancelled_theme_sessions: list[str] = []

    def snapshot(self, _status: dict[str, Any]) -> dict[str, Any]:
        return {
            "emulation": {
                "editorialPlatforms": [
                    {
                        "id": "nes",
                        "name": "Nintendo Entertainment System",
                        "shortName": "NES",
                        "state": "ready",
                        "games": [
                            {
                                "id": "rom-001",
                                "name": "Synthetic Platformer",
                                "platform": "nes",
                                "genres": ["Platformer"],
                                "releaseDate": "1992-06-01",
                                "publisher": "Example Publisher",
                                "path": "/private/roms/synthetic.nes",
                            }
                        ],
                    }
                ]
            },
            "steamGameplay": {"games": []},
        }

    def theme_list(self) -> list[dict[str, Any]]:
        return [
            {
                "id": DEFAULT_ID,
                "name": "SteamZero",
                "version": read_builtin_manifest(DEFAULT_ID).version,
                "state": "available",
                "compatible": True,
                "origin": "builtin",
            },
            {
                "id": AURA_ID,
                "name": "AURA",
                "version": read_builtin_manifest(AURA_ID).version,
                "state": "available",
                "compatible": True,
                "origin": "builtin",
            },
        ]

    def editor_load(self, theme_id: str) -> dict[str, Any]:
        result = self.theme_editor.load(theme_id)
        session_id = str(result.get("sessionId") or "")
        if session_id:
            self.loaded_theme_sessions.append(session_id)
        return result

    def editor_preview(
        self,
        session_id: str,
        *,
        scene_layout_read_model: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.theme_editor.preview(
            session_id, scene_layout_read_model=scene_layout_read_model
        )

    def editor_cancel(self, session_id: str) -> dict[str, str]:
        self.cancelled_theme_sessions.append(session_id)
        return self.theme_editor.cancel(session_id)


def _request(
    base_url: str,
    token: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    # The base URL is created by DesktopControlServer on loopback in this test.
    request = urllib.request.Request(  # noqa: S310
        base_url + path,
        data=body,
        method=method,
        headers={
            "X-SteamZero-Token": token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        value = json.loads(response.read())
    assert isinstance(value, dict)
    return value


@pytest.fixture
def preview_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str, _PreviewDashboard]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    store = StateStore(tmp_path / "preview-state.db")
    store.migrate()
    dashboard = _PreviewDashboard()
    server = DesktopControlServer(
        ExperienceCoordinator(_Context(), (), store),
        "journey-preview-test-token",
        dashboard,  # type: ignore[arg-type]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", "journey-preview-test-token", dashboard
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        store.close()


def _create_journey(base_url: str, token: str, name: str) -> dict[str, Any]:
    return _request(
        base_url,
        token,
        "/journey/studio/create",
        method="POST",
        payload={"name": name},
    )


def _transact(
    base_url: str,
    token: str,
    *,
    session_id: str,
    expected_generation: int,
    appearance: dict[str, str],
) -> dict[str, Any]:
    return _request(
        base_url,
        token,
        "/journey/studio/transact",
        method="POST",
        payload={
            "operation": "set-menu-appearance",
            "payload": {
                "sessionId": session_id,
                "expectedGeneration": expected_generation,
                "menuId": "home",
                "appearance": appearance,
            },
        },
    )


def _engine_preview(
    base_url: str,
    token: str,
    *,
    session_id: str,
    generation: int,
) -> dict[str, Any]:
    return _request(
        base_url,
        token,
        "/journey/studio/engine-preview",
        method="POST",
        payload={"sessionId": session_id, "menuId": "home", "expectedGeneration": generation},
    )


def test_engine_preview_inherit_aura_loads_packaged_aura_without_degraded_error(
    preview_bridge: tuple[str, str, _PreviewDashboard],
) -> None:
    """A2b: menu inherit-aura pré-visualiza org.steamzero.aura sem E-COMPONENT-DEGRADED."""
    base_url, token, dashboard = preview_bridge
    aura_manifest = read_builtin_manifest(AURA_ID)

    created = _create_journey(base_url, token, "Herança AURA")
    changed = _transact(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        expected_generation=int(created["generation"]),
        appearance={"mode": "inherit-aura"},
    )
    # O apply bem-sucedido é o único momento em que dirty/undo flipam (D-25,
    # cruzamento com a Parte C): o rascunho salvo do teste começa limpo.
    assert changed["dirty"] is True
    assert changed["history"]["canUndo"] is True

    result = _engine_preview(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        generation=int(changed["generation"]),
    )

    assert result["themeId"] == AURA_ID
    assert result["declaredThemeId"] is None
    assert result["themeResolutionState"] == "inherited"
    assert result["themeResolutionDiagnostic"] == ""

    manifest = result["manifest"]
    assert manifest["id"] == AURA_ID
    assert manifest["version"] == aura_manifest.version
    assert manifest["tokens"]["color"]["background"] == "#0b1020"

    stage = result["coverage"]["stages"][0]
    assert stage["stageId"] == "menu:home"
    assert stage["appearance"] == "inherited"
    assert stage["reason"] == "explicit-choice"
    assert stage["sourceThemeId"] == AURA_ID
    # A2e: a versão resolvida bate com o manifesto carregado (não com a versão
    # do tema default passado como aura_version pela rota).
    assert stage["sourceVersion"] == aura_manifest.version

    summary = result["coverage"]["summary"]
    assert summary["auraExplicitStages"] == ["menu:home"]
    assert summary["auraExplicitCount"] == 1
    # A2d: todas as etapas em AURA explícito jamais podem virar "tema personalizado".
    assert summary["auraEffectiveStages"] == ["menu:home"]
    assert "Tema personalizado" not in summary["label"]
    assert summary["requiresPreApplyConfirmation"] is True

    # Toda sessão de leitura aberta no Theme Engine foi fechada no finally.
    assert sorted(dashboard.cancelled_theme_sessions) == sorted(dashboard.loaded_theme_sessions)


def test_engine_preview_custom_still_previews_declared_theme(
    preview_bridge: tuple[str, str, _PreviewDashboard],
) -> None:
    """A1 exige manter o caminho custom: tema declarado é carregado e pré-visualizado."""
    base_url, token, _dashboard = preview_bridge
    created = _create_journey(base_url, token, "Tema custom")
    changed = _transact(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        expected_generation=int(created["generation"]),
        appearance={"mode": "custom", "themeId": "org.steamzero.asset-recipes-demo"},
    )

    result = _engine_preview(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        generation=int(changed["generation"]),
    )

    assert result["themeId"] == "org.steamzero.asset-recipes-demo"
    assert result["declaredThemeId"] == "org.steamzero.asset-recipes-demo"
    assert result["themeResolutionState"] == "custom"
    assert result["coverage"]["stages"][0]["appearance"] == "custom"


def test_engine_preview_absent_reference_still_falls_back_to_default(
    preview_bridge: tuple[str, str, _PreviewDashboard],
) -> None:
    """A1 exige manter o fallback: referência ausente resolve para org.steamzero.default."""
    base_url, token, _dashboard = preview_bridge
    created = _create_journey(base_url, token, "Referência ausente")
    changed = _transact(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        expected_generation=int(created["generation"]),
        appearance={"mode": "custom", "themeId": "org.example.missing"},
    )

    result = _engine_preview(
        base_url,
        token,
        session_id=str(created["sessionId"]),
        generation=int(changed["generation"]),
    )

    assert result["themeId"] == DEFAULT_ID
    assert result["declaredThemeId"] == "org.example.missing"
    assert result["themeResolutionState"] == "missing-reference"
    assert result["coverage"]["stages"][0]["reason"] == "theme-reference-missing"
    assert "AURA" in result["themeResolutionDiagnostic"]
