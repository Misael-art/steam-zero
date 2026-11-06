# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Studio sessions for direct scene authoring, backed by ``scene_authoring``.

Media is read from a path the author picked (canonical library or an
accessible folder); bytes are hashed into a master and never rewritten. The
original file is copied once into the project's master store so a reopened
project can verify integrity even if the source later moves.
"""

from __future__ import annotations

import re
import secrets
import struct
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from steamzero.core import fs
from steamzero.domain import scene_authoring as sa

_PROJECT_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")


def sniff_image(payload: bytes) -> tuple[str, int, int]:
    """Return media type and pixel size from the file header, or refuse."""
    if payload.startswith(b"\x89PNG\r\n\x1a\n") and payload[12:16] == b"IHDR":
        width, height = struct.unpack(">II", payload[16:24])
        return "image/png", width, height
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        chunk = payload[12:16]
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(payload[24:27], "little")
            height = 1 + int.from_bytes(payload[27:30], "little")
            return "image/webp", width, height
        if chunk == b"VP8 ":
            width, height = struct.unpack("<HH", payload[26:30])
            return "image/webp", width & 0x3FFF, height & 0x3FFF
        if chunk == b"VP8L":
            bits = int.from_bytes(payload[21:25], "little")
            return "image/webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if payload[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(payload):
            if payload[index] != 0xFF:
                index += 1
                continue
            marker = payload[index + 1]
            length = struct.unpack(">H", payload[index + 2 : index + 4])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3}:
                height, width = struct.unpack(">HH", payload[index + 5 : index + 9])
                return "image/jpeg", width, height
            index += 2 + length
    raise sa.SceneAuthoringError("formato de imagem não permitido (PNG, JPEG ou WebP)")


class SceneStudioService:
    """Transactional scene-authoring sessions persisted under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._sessions: dict[str, tuple[str, sa.SceneAuthoringSession]] = {}
        self._lock = threading.RLock()

    def _project_path(self, project_id: str) -> Path:
        if not _PROJECT_ID.match(project_id):
            raise sa.SceneAuthoringError("ID de projeto inválido")
        return self.root / f"{project_id}.scene.json"

    def _masters_dir(self) -> Path:
        return self.root / "masters"

    def create(self, project_id: str, name: str) -> dict[str, Any]:
        self._project_path(project_id)
        return self._open(project_id, sa.SceneAuthoringSession(sa.new_document(name)))

    def load(self, project_id: str) -> dict[str, Any]:
        document = sa.load(self._project_path(project_id))
        return self._open(project_id, sa.SceneAuthoringSession(document))

    def _open(self, project_id: str, session: sa.SceneAuthoringSession) -> dict[str, Any]:
        token = secrets.token_urlsafe(18)
        with self._lock:
            self._sessions[token] = (project_id, session)
        return self.snapshot(token)

    def _get(self, token: str) -> tuple[str, sa.SceneAuthoringSession]:
        found = self._sessions.get(token)
        if found is None:
            raise sa.SceneAuthoringError("sessão de cena não existe ou expirou")
        return found

    def snapshot(self, token: str) -> dict[str, Any]:
        with self._lock:
            project_id, session = self._get(token)
            return {
                "sessionId": token,
                "projectId": project_id,
                "sceneId": session.scene_id,
                "selection": list(session.selection),
                "document": session.document,
                "media": session.media_report(self._locate),
                "history": {"canUndo": session.can_undo, "canRedo": session.can_redo},
                "masterRoot": str(self._masters_dir()),
            }

    def _locate(self, master: Mapping[str, Any]) -> bytes | None:
        stored = self._masters_dir() / str(master["id"])
        try:
            return stored.read_bytes()
        except OSError:
            return None

    def import_media(self, token: str, source: Path, *, origin: str) -> dict[str, Any]:
        with self._lock:
            _project, session = self._get(token)
            if origin not in {"library", "folder"}:
                raise sa.SceneAuthoringError("origem precisa ser biblioteca ou pasta")
            if not source.is_file() or source.is_symlink():
                raise sa.SceneAuthoringError("foto indisponível ou movida")
            if source.stat().st_size > sa.MAX_MASTER_BYTES:
                raise sa.SceneAuthoringError("foto excede 8 MiB")
            payload = source.read_bytes()
            media_type, width, height = sniff_image(payload)
            media_id = session.import_master(
                payload,
                name=source.stem,
                media_type=media_type,
                width=width,
                height=height,
                origin=origin,
                source_ref=source.name,
            )
            stored = self._masters_dir() / media_id
            if not stored.exists():
                fs.ensure_dir(self._masters_dir())
                fs.write_atomic(stored, payload)
            result = self.snapshot(token)
            result["mediaId"] = media_id
            return result

    def master_path(self, media_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", media_id):
            raise sa.SceneAuthoringError("ID de mídia inválido")
        return self._masters_dir() / media_id

    def transact(self, token: str, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            _project, session = self._get(token)
            ids = [str(item) for item in payload.get("layerIds", [])]
            if operation == "drop":
                session.drop_master(
                    str(payload["mediaId"]),
                    float(payload["x"]),
                    float(payload["y"]),
                    width=float(payload.get("width", 0.3)),
                )
            elif operation == "move":
                result = session.move(
                    ids,
                    float(payload["dx"]),
                    float(payload["dy"]),
                    snap=bool(payload.get("snap", True)),
                )
                snapshot = self.snapshot(token)
                snapshot["guides"] = list(result.guides)
                return snapshot
            elif operation == "resize":
                keep = payload.get("keepAspect")
                session.resize(
                    str(payload["layerId"]),
                    str(payload["handle"]),
                    float(payload["x"]),
                    float(payload["y"]),
                    keep_aspect=None if keep is None else bool(keep),
                )
            elif operation == "align":
                session.align(ids, str(payload["mode"]))
            elif operation == "select":
                layer = payload.get("layerId")
                session.select(
                    None if layer is None else str(layer), extend=bool(payload.get("extend"))
                )
            elif operation == "reorder":
                session.reorder(str(payload["layerId"]), int(payload["index"]))
            elif operation == "set-flag":
                session.set_flag(
                    str(payload["layerId"]), str(payload["flag"]), bool(payload["value"])
                )
            elif operation == "set-recipe":
                session.set_recipe(str(payload["layerId"]), **dict(payload["recipe"]))
            elif operation == "remove-layer":
                session.remove_layer(str(payload["layerId"]))
            elif operation == "add-text":
                session.add_text(str(payload["text"]), float(payload["x"]), float(payload["y"]))
            elif operation == "add-scene":
                session.add_scene(str(payload["name"]))
            elif operation == "open-scene":
                session.open_scene(str(payload["sceneId"]))
            elif operation == "undo":
                session.undo()
            elif operation == "redo":
                session.redo()
            else:
                raise sa.SceneAuthoringError(f"operação de cena não permitida: {operation}")
            return self.snapshot(token)

    def save(self, token: str) -> dict[str, Any]:
        with self._lock:
            project_id, session = self._get(token)
            fs.ensure_dir(self.root)
            sa.save(self._project_path(project_id), session.document)
            return {"status": "saved", "projectId": project_id, "snapshot": self.snapshot(token)}

    def list(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            path.name.removesuffix(".scene.json") for path in self.root.glob("*.scene.json")
        )
