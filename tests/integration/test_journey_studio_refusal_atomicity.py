# SPDX-License-Identifier: GPL-3.0-or-later
"""D-25 (Tarefa 11): recusa não marca o documento como não salvo.

Trava de estado antes/depois da recusa na bridge real (capturas L35 vs L36 da
bateria física): uma recusa — ``E-THEME-NOT-FOUND`` com impacto "nenhuma mudança
foi feita", rascunho obsoleto recusado pelo `transact`, ou pré-visualização
recusada por geração — não pode alterar documento, dirty flag nem histórico
(``canUndo``/``Desfazer``). Dirty/undo só flipam em apply bem-sucedido.
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
from steamzero.core.state import StateStore
from steamzero.domain.desktop import DesktopContext, ExperienceCoordinator
from steamzero.domain.theme_editor import ThemeEditorManager


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


class _RefusalDashboard:
    def __init__(self) -> None:
        self.theme_editor = ThemeEditorManager()
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
                "id": "org.steamzero.default",
                "name": "SteamZero",
                "version": "1.1.0",
                "state": "available",
                "compatible": True,
                "origin": "builtin",
            }
        ]

    def editor_load(self, theme_id: str) -> dict[str, Any]:
        return self.theme_editor.load(theme_id)

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
def refusal_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str, _RefusalDashboard]:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    store = StateStore(tmp_path / "refusal-state.db")
    store.migrate()
    dashboard = _RefusalDashboard()
    server = DesktopControlServer(
        ExperienceCoordinator(_Context(), (), store),
        "journey-refusal-test-token",
        dashboard,  # type: ignore[arg-type]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", "journey-refusal-test-token", dashboard
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        store.close()


def _rename(
    base_url: str,
    token: str,
    *,
    session_id: str,
    expected_generation: int,
    name: str,
) -> dict[str, Any]:
    return _request(
        base_url,
        token,
        "/journey/studio/transact",
        method="POST",
        payload={
            "operation": "rename-menu",
            "payload": {
                "sessionId": session_id,
                "expectedGeneration": expected_generation,
                "menuId": "home",
                "name": name,
            },
        },
    )


def _state_key(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Projeção do estado do editor: documento, dirty flag e histórico."""
    return {
        "document": snapshot["document"],
        "dirty": snapshot["dirty"],
        "history": snapshot["history"],
        "generation": snapshot["generation"],
    }


def test_stale_draft_refusal_is_structured_and_leaves_editor_state_untouched(
    refusal_bridge: tuple[str, str, _RefusalDashboard],
) -> None:
    """D-25: a recusa de rascunho obsoleto declara "nenhuma mudança" e não altera o estado.

    Na bateria física (L35 vs L36) o aviso de recusa convivia com a barra
    "Salvar · não salvo" e Desfazer habilitado. O contrato: recusa → documento,
    dirty flag e histórico idênticos ao instante anterior à recusa.
    """
    base_url, token, _dashboard = refusal_bridge
    created = _request(
        base_url,
        token,
        "/journey/studio/create",
        method="POST",
        payload={"name": "Recusa obsoleta"},
    )
    session_id = str(created["sessionId"])
    applied = _rename(
        base_url,
        token,
        session_id=session_id,
        expected_generation=int(created["generation"]),
        name="Menu renomeado",
    )
    state_before = _state_key(applied)

    with pytest.raises(urllib.error.HTTPError) as error:
        _rename(
            base_url,
            token,
            session_id=session_id,
            expected_generation=int(created["generation"]),  # obsoleta
            name="Nome que a recusa não pode aplicar",
        )
    assert error.value.code == 400
    refused = json.loads(error.value.read())
    # A recusa precisa ser um objeto error-v1 com impacto "recusada antes de
    # qualquer efeito" — hoje a bridge devolve uma string solta de ValueError,
    # indistinguível para o editor de um erro interno qualquer.
    assert isinstance(refused["error"], dict), json.dumps(refused)
    error_object = refused["error"]
    assert error_object["code"] == "E-API-SCHEMA"
    assert "recarregue" in str(error_object.get("detail") or "")
    assert "nenhuma mudança foi feita" in str(error_object.get("detail") or "")
    assert "recusada" in str(error_object.get("impact") or "")

    probe = _rename(
        base_url,
        token,
        session_id=session_id,
        expected_generation=int(applied["generation"]),
        name="Menu renomeado",  # no-op: mesmo nome não gera transação
    )
    assert _state_key(probe) == state_before
    # Dirty/undo só flipam em apply bem-sucedido: o rename acima (sucesso)
    # habilitou Desfazer; a recusa não pode ter aumentado o histórico nem
    # retido sujo além do que o apply já havia marcado.
    assert probe["history"]["canUndo"] is True
    assert probe["history"]["undoDepth"] == applied["history"]["undoDepth"]


def test_clean_draft_refusal_does_not_enable_dirty_or_undo(
    refusal_bridge: tuple[str, str, _RefusalDashboard],
) -> None:
    """D-25 (L35→L36): com rascunho limpo, nenhuma recusa pode sujar ou habilitar Desfazer."""
    base_url, token, _dashboard = refusal_bridge
    created = _request(
        base_url,
        token,
        "/journey/studio/create",
        method="POST",
        payload={"name": "Rascunho limpo"},
    )
    session_id = str(created["sessionId"])
    saved = _request(
        base_url,
        token,
        "/journey/studio/save",
        method="POST",
        payload={"sessionId": session_id, "overwrite": False},
    )
    loaded = _request(
        base_url,
        token,
        "/journey/studio/load",
        method="POST",
        payload={"journeyId": saved["journeyId"]},
    )
    clean_session = str(loaded["sessionId"])
    assert loaded["dirty"] is False
    assert loaded["history"]["canUndo"] is False
    state_before = _state_key(loaded)

    # Recusa 1: geração obsoleta no transact.
    with pytest.raises(urllib.error.HTTPError) as stale_error:
        _rename(
            base_url,
            token,
            session_id=clean_session,
            expected_generation=int(loaded["generation"]) - 1,
            name="Inútil",
        )
    assert stale_error.value.code == 400

    # Recusa 2: E-THEME-NOT-FOUND no editor de tema (o aviso literal
    # "nenhuma mudança foi feita" da bateria física).
    with pytest.raises(urllib.error.HTTPError) as theme_error:
        _request(base_url, token, "/theme/editor/load?themeId=org.example.missing")
    assert theme_error.value.code == 404
    theme_object = json.loads(theme_error.value.read())["error"]
    assert theme_object["code"] == "E-THEME-NOT-FOUND"
    assert "nenhuma mudança foi feita" in theme_object["impact"]

    # Recusa 3: engine-preview com geração obsoleta.
    with pytest.raises(urllib.error.HTTPError) as preview_error:
        _request(
            base_url,
            token,
            "/journey/studio/engine-preview",
            method="POST",
            payload={
                "sessionId": clean_session,
                "menuId": "home",
                "expectedGeneration": int(loaded["generation"]) - 1,
            },
        )
    assert preview_error.value.code == 400

    probe = _rename(
        base_url,
        token,
        session_id=clean_session,
        expected_generation=int(loaded["generation"]),
        name=loaded["document"]["menus"][0]["name"],  # no-op
    )
    assert probe["dirty"] is False
    assert probe["history"]["canUndo"] is False
    assert _state_key(probe) == state_before
