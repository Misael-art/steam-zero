# SPDX-License-Identifier: GPL-3.0-or-later
"""D-21: a miniatura já escrita ao lado do save-state é publicada na superfície.

Reprodução do registro da jornada física
(docs/09-operations/evidence/2026-10-12-jornada-fisica-2b7eb541b4a5/logs/
12-defeitos-registrados.txt): o PNG existe em
``~/.local/share/steamzero/saves/states/<core>/*.png`` (6 418 bytes na bateria)
e o overlay devolve ``thumbnailUrl=""`` com ``thumbnailFallback=true`` — a
galeria mostra sempre o placeholder. O adapter da sessão é o dono do arquivo;
é ele que resolve a URL real, pela única autoridade de nomenclatura promovida
na D-26 (``state_path``), com o mesmo padrão ``file://`` + percent-encoding já
usado pelas capas e fanarts locais (adapters/launcher_media.py). O domínio
continua sanitizando o que nasce do adapter; a publicação post-resolve não
contorna o allowlist — ela substitui o fallback do próprio adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

from steamzero.adapters.session_overlay import SessionOverlayAdapter

STATE_ROOT_NAME = "saves-states"


class _D21Record:
    def __init__(self) -> None:
        self.id = "d21-session"
        self.game_id = "celeste"
        self.state = "running"


class _D21Control:
    """Esqueleto do controle real: os mesmos dados crus de session_peripherals.

    ``list_save_states`` devolve entries sem miniatura (thumbnailUrl=""), como
    o adapter RetroArch faz hoje; ``state_path`` é a única autoridade de
    nomenclatura do arquivo de estado — o PNG segue a convenção
    ``<state_path>.png``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self.current = _D21Record()

    def _state_file(self, slot: int) -> Path:
        return self._root / ("celeste.state" if slot == 0 else f"celeste.state{slot}")

    def state_path(self, slot: int) -> Path:
        return self._state_file(slot)

    def list_save_states(self) -> list[dict[str, Any]]:
        return [
            {
                "slot": slot,
                "timestamp": "2026-10-12T12:00:00Z",
                "playtimeSeconds": 0,
                "thumbnailUrl": "",
                "compatibility": "native",
                "available": True,
                "backupAvailable": False,
            }
            for slot in self._slots_with_states()
        ]

    def _slots_with_states(self) -> list[int]:
        return [slot for slot in (0, 2, 4) if self._state_file(slot).is_file()]

    def save_state(self, slot: int) -> _D21Record:
        return self.current

    def load_state(self, slot: int) -> _D21Record:
        return self.current


def _write_state_files(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for slot in (0, 2, 4):
        state_file = root / ("celeste.state" if slot == 0 else f"celeste.state{slot}")
        state_file.write_bytes(b"state-bytes")
    # O PNG existe exatamente onde a evidência física o deixou: ao lado do
    # estado, com o sufixo .png acrescentado ao nome canônico.
    (root / "celeste.state4.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 6408)


def _adapter(control: object | None) -> SessionOverlayAdapter:
    record = control.current if control is not None else None

    def observe(_game_id: str) -> dict[str, Any]:
        if control is None or record is None:
            return {"gameId": "celeste", "sessionId": None, "state": "none"}
        return {"gameId": record.game_id, "sessionId": record.id, "state": record.state}

    def resolve_control(_session_id: str, _game_id: str) -> Any:
        return control

    return SessionOverlayAdapter(observe, resolve_control)


def test_existing_thumbnail_png_is_published_as_real_file_url(tmp_path: Path) -> None:
    """D-21: com o PNG do lado do estado, a galeria publica a URL real, não o fallback."""
    state_root = tmp_path / STATE_ROOT_NAME
    _write_state_files(state_root)
    control = _D21Control(state_root)

    gallery = _adapter(control).read_model("celeste")["saveStates"]

    by_slot = {entry["slot"]: entry for entry in gallery["entries"]}
    assert set(by_slot) == {0, 2, 4}
    expected = "file://" + quote(str(state_root / "celeste.state4.png"), safe="/")
    assert by_slot[4]["thumbnailUrl"] == expected
    assert by_slot[4]["thumbnailFallback"] is False
    # Slots sem PNG continuam com o fallback honesto: nada é inventado.
    assert by_slot[0]["thumbnailUrl"] == ""
    assert by_slot[0]["thumbnailFallback"] is True
    assert by_slot[2]["thumbnailUrl"] == ""
    assert by_slot[2]["thumbnailFallback"] is True


def test_thumbnail_url_percent_encodes_paths_needing_it(tmp_path: Path) -> None:
    """A URL publicada é carregável: espaços e acentos viram percent-encoding."""
    state_root = tmp_path / "saves states com espaço" / "núcleo"
    _write_state_files(state_root)
    control = _D21Control(state_root)

    gallery = _adapter(control).read_model("celeste")["saveStates"]

    entry = {item["slot"]: item for item in gallery["entries"]}[4]
    url = entry["thumbnailUrl"]
    assert url.startswith("file://")
    assert " " not in url
    assert "%20" in url

    assert Path(unquote(urlparse(url).path)) == state_root / "celeste.state4.png"


def test_empty_or_forged_thumbnails_never_cross_the_surface(tmp_path: Path) -> None:
    """Guardas: PNG vazio e link simbólico continuam publicados como fallback."""
    state_root = tmp_path / STATE_ROOT_NAME
    _write_state_files(state_root)
    (state_root / "celeste.state.png").write_bytes(b"")  # slot 0: PNG de zero bytes
    forged = state_root / "outside.png"
    forged.write_bytes(b"\x89PNG real fora do destino")
    (state_root / "celeste.state2.png").symlink_to(forged)  # slot 2: symlink
    control = _D21Control(state_root)

    gallery = _adapter(control).read_model("celeste")["saveStates"]

    by_slot = {entry["slot"]: entry for entry in gallery["entries"]}
    assert by_slot[0]["thumbnailUrl"] == ""
    assert by_slot[0]["thumbnailFallback"] is True
    assert by_slot[2]["thumbnailUrl"] == ""
    assert by_slot[2]["thumbnailFallback"] is True
    assert by_slot[4]["thumbnailFallback"] is False


def test_control_without_state_path_keeps_the_fallback(tmp_path: Path) -> None:
    """Compatibilidade: um controle sem a porta state_path não trava a galeria."""
    state_root = tmp_path / STATE_ROOT_NAME
    _write_state_files(state_root)

    class _LegacyControl(_D21Control):
        state_path = None  # type: ignore[assignment]

    control = _LegacyControl(state_root)
    gallery = _adapter(control).read_model("celeste")["saveStates"]
    assert all(entry["thumbnailFallback"] is True for entry in gallery["entries"])
