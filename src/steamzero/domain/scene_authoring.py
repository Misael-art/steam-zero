# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Direct-manipulation scene authoring for the Theme Studio ("renderize, não edite").

Layers reference canonical masters by SHA-256 and carry a declarative recipe
(brightness, saturation, framing). The master is never rewritten. Geometry is
stored in normalized stage units (0..1 of a 16:9 stage) so the composition is
preserved when the Studio window changes size; pixels are derived per viewport.

This module is pure data: no QML, no file decoding, no process execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from steamzero.core import fs

KIND = "steamzero-scene-authoring-v1"
SCHEMA_VERSION = 1
STAGE_ASPECT = 16 / 9
MAX_SCENES = 20
MAX_LAYERS_PER_SCENE = 60
MAX_MASTERS = 30
MAX_MASTER_BYTES = 8 * 1024 * 1024
MAX_MASTER_PIXELS = 24_000_000
MAX_TOTAL_MASTER_BYTES = 32 * 1024 * 1024
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_HISTORY = 100
MIN_SIZE = 0.01
SNAP_THRESHOLD = 0.01
MEDIA_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
FITS = frozenset({"cover", "contain"})
PRESETS = frozenset({"none", "mono", "warm", "cool"})
ALIGN_MODES = frozenset({"left", "hcenter", "right", "top", "vcenter", "bottom"})
HANDLES = frozenset({"nw", "n", "ne", "e", "se", "s", "sw", "w"})
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class SceneAuthoringError(ValueError):
    """Refused edit; the document and history are unchanged."""


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise SceneAuthoringError(f"{name} precisa ser numérico")
    return float(value)


def default_recipe() -> dict[str, Any]:
    return {
        "brightness": 0.0,
        "saturation": 1.0,
        "preset": "none",
        "fit": "cover",
        "focalX": 0.5,
        "focalY": 0.5,
    }


def validate_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    merged = {**default_recipe(), **dict(recipe)}
    if set(merged) != set(default_recipe()):
        raise SceneAuthoringError("receita contém campos não publicados")
    merged["brightness"] = _clamp(_number(merged["brightness"], "brilho"), -1.0, 1.0)
    merged["saturation"] = _clamp(_number(merged["saturation"], "saturação"), 0.0, 2.0)
    merged["focalX"] = _clamp(_number(merged["focalX"], "enquadramento"), 0.0, 1.0)
    merged["focalY"] = _clamp(_number(merged["focalY"], "enquadramento"), 0.0, 1.0)
    if merged["preset"] not in PRESETS:
        raise SceneAuthoringError(f"preset desconhecido: {merged['preset']}")
    if merged["fit"] not in FITS:
        raise SceneAuthoringError(f"enquadramento desconhecido: {merged['fit']}")
    return merged


@dataclass(frozen=True)
class Viewport:
    """Pixel rectangle of the 16:9 stage inside an editor area (letterboxed)."""

    x: float
    y: float
    width: float
    height: float

    @classmethod
    def fit(cls, area_width: float, area_height: float) -> Viewport:
        if area_width <= 0 or area_height <= 0:
            raise SceneAuthoringError("área de edição precisa ter tamanho positivo")
        width = min(area_width, area_height * STAGE_ASPECT)
        height = width / STAGE_ASPECT
        return cls((area_width - width) / 2, (area_height - height) / 2, width, height)

    def to_stage(self, px: float, py: float) -> tuple[float, float]:
        return (px - self.x) / self.width, (py - self.y) / self.height

    def to_pixels(self, layer: Mapping[str, Any]) -> dict[str, float]:
        return {
            "x": self.x + float(layer["x"]) * self.width,
            "y": self.y + float(layer["y"]) * self.height,
            "width": float(layer["w"]) * self.width,
            "height": float(layer["h"]) * self.height,
        }


def master_id(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def resolve_master(
    master: Mapping[str, Any], locate: Callable[[Mapping[str, Any]], bytes | None]
) -> dict[str, str]:
    """Report whether a referenced master is usable, without substituting another.

    ``locate`` reads the source through the canonical library or an authorized
    folder and returns ``None`` when it cannot be found.
    """
    payload = locate(master)
    if payload is None:
        return {"mediaId": str(master["id"]), "status": "missing", "action": "relink-or-remove"}
    if master_id(payload) != master["id"]:
        return {"mediaId": str(master["id"]), "status": "changed", "action": "relink-or-accept"}
    return {"mediaId": str(master["id"]), "status": "available", "action": ""}


def new_document(name: str = "Experiência") -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "name": name,
        "masters": [],
        "scenes": [{"id": "scene-1", "name": "Cena 1", "layers": []}],
    }


def validate_document(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate structure, budgets and references of a scene-authoring document."""
    if raw.get("schemaVersion") != SCHEMA_VERSION or raw.get("kind") != KIND:
        raise SceneAuthoringError("documento de cena não é da versão publicada")
    if set(raw) != {"schemaVersion", "kind", "name", "masters", "scenes"}:
        raise SceneAuthoringError("documento de cena contém campos não publicados")
    document = json.loads(json.dumps(raw, ensure_ascii=False, allow_nan=False))
    masters = document["masters"]
    scenes = document["scenes"]
    if not isinstance(masters, list) or not isinstance(scenes, list) or not scenes:
        raise SceneAuthoringError("documento precisa de mestres e ao menos uma cena")
    if len(masters) > MAX_MASTERS or len(scenes) > MAX_SCENES:
        raise SceneAuthoringError("documento excede o limite de mestres ou cenas")
    master_ids: set[str] = set()
    total = 0
    for master in masters:
        if not _SHA.match(str(master.get("id", ""))):
            raise SceneAuthoringError("mestre precisa de SHA-256")
        if master.get("mediaType") not in MEDIA_TYPES:
            raise SceneAuthoringError("tipo de mídia não permitido")
        size = int(master.get("bytes", 0))
        pixels = int(master.get("width", 0)) * int(master.get("height", 0))
        if size <= 0 or size > MAX_MASTER_BYTES or pixels <= 0 or pixels > MAX_MASTER_PIXELS:
            raise SceneAuthoringError("mestre excede o limite publicado")
        if master.get("origin") not in {"library", "folder"}:
            raise SceneAuthoringError("origem do mestre precisa ser biblioteca ou pasta")
        total += size
        master_ids.add(str(master["id"]))
    if len(master_ids) != len(masters):
        raise SceneAuthoringError("mestre duplicado")
    if total > MAX_TOTAL_MASTER_BYTES:
        raise SceneAuthoringError("fotos importadas excedem o limite do projeto")
    scene_ids: set[str] = set()
    for scene in scenes:
        if not _ID.match(str(scene.get("id", ""))) or scene["id"] in scene_ids:
            raise SceneAuthoringError("cena com ID inválido ou duplicado")
        scene_ids.add(scene["id"])
        layers = scene.get("layers")
        if not isinstance(layers, list) or len(layers) > MAX_LAYERS_PER_SCENE:
            raise SceneAuthoringError("cena excede o limite de camadas")
        layer_ids: set[str] = set()
        for layer in layers:
            if not _ID.match(str(layer.get("id", ""))) or layer["id"] in layer_ids:
                raise SceneAuthoringError("camada com ID inválido ou duplicado")
            layer_ids.add(layer["id"])
            if layer.get("kind") == "image" and layer.get("mediaId") not in master_ids:
                raise SceneAuthoringError(f"camada {layer['id']} referencia mestre ausente")
            if layer.get("kind") not in {"image", "text"}:
                raise SceneAuthoringError("natureza de camada desconhecida")
            for key in ("x", "y", "w", "h"):
                _number(layer.get(key), key)
            if layer["w"] < MIN_SIZE or layer["h"] < MIN_SIZE:
                raise SceneAuthoringError("camada abaixo do tamanho mínimo")
            layer["recipe"] = validate_recipe(layer.get("recipe", {}))
    result: dict[str, Any] = document
    return result


@dataclass
class SnapResult:
    x: float
    y: float
    guides: tuple[dict[str, Any], ...]


def _edges(x: float, size: float) -> tuple[float, float, float]:
    return x, x + size / 2, x + size


def snap_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    others: Iterable[Mapping[str, Any]],
    threshold: float = SNAP_THRESHOLD,
) -> SnapResult:
    """Snap a rectangle's edges or center to the stage and to other layers."""
    vertical = [0.0, 0.5, 1.0]
    horizontal = [0.0, 0.5, 1.0]
    for other in others:
        vertical.extend(_edges(float(other["x"]), float(other["w"])))
        horizontal.extend(_edges(float(other["y"]), float(other["h"])))
    guides: list[dict[str, Any]] = []

    def best(origin: float, size: float, targets: Sequence[float]) -> tuple[float, float | None]:
        chosen: tuple[float, float] | None = None
        for anchor_offset in (0.0, size / 2, size):
            for target in targets:
                distance = abs(origin + anchor_offset - target)
                if distance <= threshold and (chosen is None or distance < chosen[0]):
                    chosen = (distance, target - anchor_offset)
        if chosen is None:
            return origin, None
        snapped = chosen[1]
        line = next(
            t for t in targets if any(abs(snapped + o - t) < 1e-9 for o in (0, size / 2, size))
        )
        return snapped, line

    nx, vline = best(x, w, vertical)
    ny, hline = best(y, h, horizontal)
    if vline is not None:
        guides.append({"axis": "vertical", "at": vline})
    if hline is not None:
        guides.append({"axis": "horizontal", "at": hline})
    return SnapResult(nx, ny, tuple(guides))


class SceneAuthoringSession:
    """Edit one scene-authoring document with transactional undo/redo."""

    def __init__(self, document: Mapping[str, Any] | None = None) -> None:
        self._data = validate_document(document or new_document())
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []
        self.selection: list[str] = []
        self.scene_id: str = str(self._data["scenes"][0]["id"])
        self._counter = 0

    @property
    def document(self) -> dict[str, Any]:
        return deepcopy(self._data)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def _scene(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        source = self._data if data is None else data
        for scene in source["scenes"]:
            if scene["id"] == self.scene_id:
                return dict(scene)
        raise SceneAuthoringError(f"cena não existe: {self.scene_id}")

    def layers(self) -> list[dict[str, Any]]:
        return deepcopy(self._scene()["layers"])

    def layer(self, layer_id: str) -> dict[str, Any]:
        for layer in self._scene()["layers"]:
            if layer["id"] == layer_id:
                return deepcopy(layer)
        raise SceneAuthoringError(f"camada não existe: {layer_id}")

    def _commit(self, mutate: Callable[[dict[str, Any]], None]) -> None:
        candidate = deepcopy(self._data)
        mutate(candidate)
        validated = validate_document(candidate)
        if validated != self._data:
            self._undo.append(self._data)
            del self._undo[:-MAX_HISTORY]
            self._redo.clear()
            self._data = validated

    def undo(self) -> None:
        if self._undo:
            self._redo.append(self._data)
            self._data = self._undo.pop()
            self._repair_context()

    def redo(self) -> None:
        if self._redo:
            self._undo.append(self._data)
            self._data = self._redo.pop()
            self._repair_context()

    def _repair_context(self) -> None:
        scene_ids = [scene["id"] for scene in self._data["scenes"]]
        if self.scene_id not in scene_ids:
            self.scene_id = scene_ids[0]
        present = {layer["id"] for layer in self._scene()["layers"]}
        self.selection = [item for item in self.selection if item in present]

    def _new_id(self, prefix: str, existing: Iterable[str]) -> str:
        taken = set(existing)
        while True:
            self._counter += 1
            candidate = f"{prefix}-{self._counter}"
            if candidate not in taken:
                return candidate

    def _scene_layers(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        for scene in data["scenes"]:
            if scene["id"] == self.scene_id:
                layers: list[dict[str, Any]] = scene["layers"]
                return layers
        raise SceneAuthoringError(f"cena não existe: {self.scene_id}")

    def _editable(self, data: dict[str, Any], layer_id: str) -> dict[str, Any]:
        for layer in self._scene_layers(data):
            if layer["id"] == layer_id:
                if layer.get("locked"):
                    raise SceneAuthoringError(f"camada bloqueada: {layer_id}")
                return layer
        raise SceneAuthoringError(f"camada não existe: {layer_id}")

    # --- media -----------------------------------------------------------
    def import_master(
        self,
        payload: bytes,
        *,
        name: str,
        media_type: str,
        width: int,
        height: int,
        origin: str,
        source_ref: str,
    ) -> str:
        """Register a master once; reusing the same bytes returns the same ID."""
        identity = master_id(payload)
        if any(item["id"] == identity for item in self._data["masters"]):
            return identity

        def mutate(data: dict[str, Any]) -> None:
            data["masters"].append(
                {
                    "id": identity,
                    "name": name[:120],
                    "mediaType": media_type,
                    "bytes": len(payload),
                    "width": int(width),
                    "height": int(height),
                    "origin": origin,
                    "sourceRef": source_ref[:512],
                }
            )

        self._commit(mutate)
        return identity

    def library(self, *, origin: str | None = None, query: str = "") -> list[dict[str, Any]]:
        """Library search/filter: locates masters, never changes how a layer looks."""
        needle = query.casefold().strip()
        return [
            deepcopy(item)
            for item in self._data["masters"]
            if (origin is None or item["origin"] == origin)
            and (not needle or needle in str(item["name"]).casefold())
        ]

    # --- composition ------------------------------------------------------
    def drop_master(self, media_id: str, x: float, y: float, *, width: float = 0.3) -> str:
        master = next((m for m in self._data["masters"] if m["id"] == media_id), None)
        if master is None:
            raise SceneAuthoringError("foto não está na biblioteca do projeto")
        w = _clamp(width, MIN_SIZE, 1.0)
        h = w * STAGE_ASPECT * master["height"] / master["width"]
        layer_id = self._new_id("layer", (layer["id"] for layer in self._scene()["layers"]))

        def mutate(data: dict[str, Any]) -> None:
            layers = self._scene_layers(data)
            layers.append(
                {
                    "id": layer_id,
                    "kind": "image",
                    "name": master["name"],
                    "mediaId": media_id,
                    "x": _clamp(x - w / 2, -1.0, 2.0),
                    "y": _clamp(y - h / 2, -1.0, 2.0),
                    "w": w,
                    "h": h,
                    "visible": True,
                    "locked": False,
                    "recipe": default_recipe(),
                }
            )

        self._commit(mutate)
        self.selection = [layer_id]
        return layer_id

    def add_text(self, text: str, x: float, y: float) -> str:
        layer_id = self._new_id("text", (layer["id"] for layer in self._scene()["layers"]))

        def mutate(data: dict[str, Any]) -> None:
            self._scene_layers(data).append(
                {
                    "id": layer_id,
                    "kind": "text",
                    "name": text[:40] or "Texto",
                    "text": text[:500],
                    "x": x,
                    "y": y,
                    "w": 0.3,
                    "h": 0.08,
                    "visible": True,
                    "locked": False,
                    "recipe": default_recipe(),
                }
            )

        self._commit(mutate)
        self.selection = [layer_id]
        return layer_id

    def select(self, layer_id: str | None, *, extend: bool = False) -> list[str]:
        if layer_id is None:
            self.selection = []
            return []
        self.layer(layer_id)
        if extend:
            if layer_id in self.selection:
                self.selection.remove(layer_id)
            else:
                self.selection.append(layer_id)
        else:
            self.selection = [layer_id]
        return list(self.selection)

    def move(
        self, layer_ids: Sequence[str], dx: float, dy: float, *, snap: bool = True
    ) -> SnapResult:
        ids = list(layer_ids)
        current = [self.layer(item) for item in ids]
        left = min(layer["x"] for layer in current) + dx
        top = min(layer["y"] for layer in current) + dy
        right = max(layer["x"] + layer["w"] for layer in current) + dx
        bottom = max(layer["y"] + layer["h"] for layer in current) + dy
        result = SnapResult(left, top, ())
        if snap:
            others = [
                layer
                for layer in self._scene()["layers"]
                if layer["id"] not in ids and layer["visible"]
            ]
            result = snap_rect(left, top, right - left, bottom - top, others)
        offset_x = dx + (result.x - left)
        offset_y = dy + (result.y - top)

        def mutate(data: dict[str, Any]) -> None:
            for layer_id in ids:
                layer = self._editable(data, layer_id)
                layer["x"] += offset_x
                layer["y"] += offset_y

        self._commit(mutate)
        return result

    def resize(
        self, layer_id: str, handle: str, x: float, y: float, *, keep_aspect: bool | None = None
    ) -> dict[str, Any]:
        """Drag a handle to a stage point. Corners keep aspect by default."""
        if handle not in HANDLES:
            raise SceneAuthoringError(f"alça desconhecida: {handle}")
        layer = self.layer(layer_id)
        left, top = layer["x"], layer["y"]
        right, bottom = left + layer["w"], top + layer["h"]
        if "w" in handle:
            left = min(x, right - MIN_SIZE)
        if "e" in handle:
            right = max(x, left + MIN_SIZE)
        if "n" in handle:
            top = min(y, bottom - MIN_SIZE)
        if "s" in handle:
            bottom = max(y, top + MIN_SIZE)
        corner = len(handle) == 2
        if keep_aspect if keep_aspect is not None else corner:
            ratio = layer["w"] / layer["h"]
            width = right - left
            height = width / ratio
            if "n" in handle:
                top = bottom - height
            else:
                bottom = top + height

        def mutate(data: dict[str, Any]) -> None:
            target = self._editable(data, layer_id)
            target.update(x=left, y=top, w=right - left, h=bottom - top)

        self._commit(mutate)
        return self.layer(layer_id)

    def align(self, layer_ids: Sequence[str], mode: str) -> None:
        """One layer aligns to the scene; a group aligns to its own bounds."""
        if mode not in ALIGN_MODES:
            raise SceneAuthoringError(f"alinhamento desconhecido: {mode}")
        current = [self.layer(item) for item in layer_ids]
        if not current:
            raise SceneAuthoringError("selecione ao menos uma camada")
        if len(current) == 1:
            bounds = (0.0, 0.0, 1.0, 1.0)
        else:
            bounds = (
                min(layer["x"] for layer in current),
                min(layer["y"] for layer in current),
                max(layer["x"] + layer["w"] for layer in current),
                max(layer["y"] + layer["h"] for layer in current),
            )

        def mutate(data: dict[str, Any]) -> None:
            for layer_id in layer_ids:
                layer = self._editable(data, layer_id)
                if mode == "left":
                    layer["x"] = bounds[0]
                elif mode == "right":
                    layer["x"] = bounds[2] - layer["w"]
                elif mode == "hcenter":
                    layer["x"] = (bounds[0] + bounds[2]) / 2 - layer["w"] / 2
                elif mode == "top":
                    layer["y"] = bounds[1]
                elif mode == "bottom":
                    layer["y"] = bounds[3] - layer["h"]
                else:
                    layer["y"] = (bounds[1] + bounds[3]) / 2 - layer["h"] / 2

        self._commit(mutate)

    def reorder(self, layer_id: str, index: int) -> None:
        def mutate(data: dict[str, Any]) -> None:
            layers = self._scene_layers(data)
            position = next(i for i, layer in enumerate(layers) if layer["id"] == layer_id)
            layer = layers.pop(position)
            layers.insert(max(0, min(index, len(layers))), layer)

        self.layer(layer_id)
        self._commit(mutate)

    def set_flag(self, layer_id: str, flag: str, value: bool) -> None:
        if flag not in {"visible", "locked"}:
            raise SceneAuthoringError(f"propriedade não editável: {flag}")

        def mutate(data: dict[str, Any]) -> None:
            for layer in self._scene_layers(data):
                if layer["id"] == layer_id:
                    layer[flag] = bool(value)
                    return
            raise SceneAuthoringError(f"camada não existe: {layer_id}")

        self._commit(mutate)

    def set_recipe(self, layer_id: str, **changes: Any) -> dict[str, Any]:
        def mutate(data: dict[str, Any]) -> None:
            layer = self._editable(data, layer_id)
            layer["recipe"] = validate_recipe({**layer["recipe"], **changes})

        self._commit(mutate)
        recipe: dict[str, Any] = self.layer(layer_id)["recipe"]
        return recipe

    def remove_layer(self, layer_id: str) -> None:
        def mutate(data: dict[str, Any]) -> None:
            layers = self._scene_layers(data)
            layers[:] = [layer for layer in layers if layer["id"] != layer_id]

        self.layer(layer_id)
        self._commit(mutate)
        self._repair_context()

    def add_scene(self, name: str) -> str:
        scene_id = self._new_id("scene", (scene["id"] for scene in self._data["scenes"]))
        self._commit(
            lambda data: data["scenes"].append({"id": scene_id, "name": name[:80], "layers": []})
        )
        self.scene_id = scene_id
        self.selection = []
        return scene_id

    def open_scene(self, scene_id: str) -> None:
        if scene_id not in {scene["id"] for scene in self._data["scenes"]}:
            raise SceneAuthoringError(f"cena não existe: {scene_id}")
        self.scene_id = scene_id
        self.selection = []

    def media_report(
        self, locate: Callable[[Mapping[str, Any]], bytes | None]
    ) -> list[dict[str, str]]:
        return [resolve_master(master, locate) for master in self._data["masters"]]


def serialize(document: Mapping[str, Any]) -> bytes:
    payload = json.dumps(
        validate_document(document), ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise SceneAuthoringError("documento de cena excede o limite")
    return payload


def parse(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise SceneAuthoringError("documento de cena excede o limite")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SceneAuthoringError("arquivo de cena inválido") from exc
    if not isinstance(raw, dict):
        raise SceneAuthoringError("arquivo de cena inválido")
    return validate_document(raw)


def save(path: Path, document: Mapping[str, Any]) -> None:
    """Atomic write: a failed write leaves the previous file intact."""
    fs.write_atomic(path, serialize(document))


def load(path: Path) -> dict[str, Any]:
    return parse(path.read_bytes())
