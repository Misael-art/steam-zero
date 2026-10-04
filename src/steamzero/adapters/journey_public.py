# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 SteamZero contributors
"""Typed public read-model fields shared by Studio and fullscreen consumers."""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

PUBLIC_GAME_RECORD_FIELDS = frozenset(
    {
        "sortTitle",
        "aliases",
        "systemId",
        "family",
        "region",
        "language",
        "container",
        "size",
        "developer",
        "publisher",
        "releaseDate",
        "genres",
        "series",
        "franchise",
        "description",
        "rating",
        "ageRating",
        "players",
        "features",
        "runtime",
        "core",
        "emulatorId",
        "availability",
    }
)


@cache
def game_record_public_field_types() -> dict[str, str]:
    """Read types from the canonical schema, excluding identity and private paths."""
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "game-record-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        raise RuntimeError("schema GameRecord sem propriedades públicas")
    types: dict[str, str] = {}
    for field_id in sorted(PUBLIC_GAME_RECORD_FIELDS):
        definition = properties.get(field_id)
        if not isinstance(definition, dict):
            continue
        field_type = definition.get("type")
        if field_type in {"string", "integer", "number", "boolean"}:
            types[field_id] = str(field_type)
        elif (
            field_type == "array"
            and isinstance(definition.get("items"), dict)
            and definition["items"].get("type") == "string"
        ):
            types[field_id] = "string[]"
    return types


def journey_public_field_types() -> dict[str, str]:
    """Return the exact game fields exposed by ``library.games``."""
    return {
        "id": "string",
        "gameId": "string",
        "title": "string",
        "name": "string",
        "source": "string",
        "platformId": "string",
        "platformName": "string",
        "shortName": "string",
        "gameCount": "integer",
        "year": "integer",
        "genre": "string",
        **game_record_public_field_types(),
    }


def safe_public_value(value: Any, field_type: str) -> object:
    """Bound public scalar/list values and reject values outside the schema type."""
    if field_type == "string" and isinstance(value, str):
        return value[:4096]
    if field_type == "integer" and isinstance(value, int) and not isinstance(value, bool):
        return value
    if field_type == "number" and isinstance(value, int | float) and not isinstance(value, bool):
        return value if not isinstance(value, float) or math.isfinite(value) else None
    if field_type == "boolean" and isinstance(value, bool):
        return value
    if field_type == "string[]" and isinstance(value, list):
        return [item[:512] for item in value[:64] if isinstance(item, str)]
    return None


def project_game_row(record: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    """Project one catalog entry through public fields; never copy launch paths."""
    game_id = record.get("id")
    title = record.get("title", record.get("name"))
    if not isinstance(game_id, str) or not game_id or not isinstance(title, str) or not title:
        return None
    row: dict[str, Any] = {
        "id": f"{source}:{game_id}"[:256],
        "gameId": game_id[:128],
        "source": source[:32],
        "title": title[:512],
        "name": title[:512],
    }
    fields = game_record_public_field_types()
    for field_id, field_type in fields.items():
        value = record.get(field_id)
        if field_id in {"platformId", "systemId"} and value is None:
            value = record.get("platform") or record.get("system")
        projected = safe_public_value(value, field_type)
        if projected is not None:
            row[field_id] = projected
    release_date = row.get("releaseDate")
    explicit_year = record.get("year")
    if isinstance(explicit_year, int) and not isinstance(explicit_year, bool):
        row["year"] = explicit_year
    elif isinstance(release_date, str) and len(release_date) >= 4:
        year = release_date[:4]
        if year.isdecimal() and len(year) == 4:
            row["year"] = int(year)
    genres = row.get("genres")
    if isinstance(genres, list) and genres and isinstance(genres[0], str):
        row["genre"] = genres[0]
    elif isinstance(record.get("genre"), str):
        row["genre"] = str(record["genre"])[:256]
    platform_id = row.get("platformId") or row.get("systemId")
    platform_label = record.get("platformLabel") or record.get("platformName")
    if isinstance(platform_id, str):
        row["platformId"] = platform_id[:128]
    if isinstance(platform_label, str):
        row["platformName"] = platform_label[:256]
    return row
