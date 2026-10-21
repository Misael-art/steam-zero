# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Persistência do ``GameRecord`` descritivo por jogo (R2).

A fusão é a do domínio (``GameRecord.merge``): valor manual não é
sobrescrito, fonte mais pobre não apaga a mais rica, e conflito vira
``warnings``. Este adapter só decide o que entra na fusão e grava o resultado;
uma busca sem campos não toca o registro, então erro de autenticação, quota,
rede ou resultado vazio nunca apaga o que já existe.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from steamzero.domain.game_record import GameRecord, ProvenanceEntry

#: Campos descritivos que provedores remotos podem preencher.
DESCRIPTIVE_FIELDS = ("description", "developer", "publisher", "releaseDate", "genres")


def record_id(game_id: str) -> str:
    """Id do registro no padrão do schema.

    Ids de jogo são ULIDs (Crockford, maiúsculos); ULID é insensível a caixa,
    então a forma minúscula identifica o mesmo jogo sem perda.
    """
    return game_id.lower()


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class MetadataUpdate:
    """Resultado de uma fusão: o registro gravado e o que mudou ou conflitou."""

    record: GameRecord | None
    changed: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


class StateStoreGameMetadataAdapter:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def load(self, game_id: str) -> GameRecord | None:
        row = self._conn.execute(
            "SELECT record_json FROM game_metadata WHERE game_id = ?", (game_id,)
        ).fetchone()
        if row is None:
            return None
        return GameRecord.from_mapping(json.loads(row[0]))

    def save(self, game_id: str, record: GameRecord) -> None:
        self._conn.execute(
            "INSERT INTO game_metadata (game_id, record_json, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(game_id) DO UPDATE SET record_json = excluded.record_json, "
            "updated_at = excluded.updated_at",
            (
                game_id,
                json.dumps(record.to_mapping(), ensure_ascii=False, sort_keys=True),
                _timestamp(datetime.now(UTC)),
            ),
        )
        self._conn.commit()

    def merge_provider_fields(
        self,
        *,
        game_id: str,
        title: str,
        platform_id: str,
        path: str,
        fields: Mapping[str, Any],
        source: str,
        confidence: float,
        retrieved_at: datetime | None = None,
    ) -> MetadataUpdate:
        """Funde campos de um provedor no registro do jogo e grava.

        Sem campos descritivos, nada é escrito: resultado vazio não apaga dado.
        """
        current = self.load(game_id)
        descriptive = {key: fields[key] for key in DESCRIPTIVE_FIELDS if fields.get(key)}
        if not descriptive:
            return MetadataUpdate(record=current)
        stamp = _timestamp(retrieved_at or datetime.now(UTC))
        provenance = ProvenanceEntry(source=source, retrieved_at=stamp, confidence=confidence)
        incoming = GameRecord.from_mapping(
            {
                "schemaVersion": 1,
                "id": record_id(game_id),
                "title": title,
                "platformId": platform_id,
                "path": path,
                "availability": "available",
                "updatedAt": stamp,
                **descriptive,
                "provenance": {key: provenance.to_mapping() for key in descriptive},
            }
        )
        if current is None:
            self.save(game_id, incoming)
            return MetadataUpdate(record=incoming, changed=tuple(descriptive))
        outcome = current.merge(incoming)
        before = current.to_mapping()
        after = outcome.record.to_mapping()
        changed = tuple(key for key in descriptive if before.get(key) != after.get(key))
        if changed or outcome.conflicts:
            self.save(game_id, outcome.record)
        return MetadataUpdate(record=outcome.record, changed=changed, conflicts=outcome.conflicts)


def public_view(adapter: StateStoreGameMetadataAdapter, game_id: str) -> dict[str, Any]:
    """Campos descritivos e a origem de cada um, para a Central e o Launcher.

    Nenhum caminho ou dado interno atravessa. Registro ilegível degrada para
    ``unreadable`` em vez de derrubar o payload da tela inteira.
    """
    try:
        record = adapter.load(game_id)
    except (ValueError, json.JSONDecodeError):
        return {"state": "unreadable", "fields": {}, "sources": {}}
    if record is None:
        return {"state": "empty", "fields": {}, "sources": {}}
    payload = record.to_mapping()
    fields = {key: payload[key] for key in DESCRIPTIVE_FIELDS if payload.get(key)}
    sources = {
        key: entry.source for key in fields if (entry := record.provenance_of(key)) is not None
    }
    return {"state": "available" if fields else "empty", "fields": fields, "sources": sources}
