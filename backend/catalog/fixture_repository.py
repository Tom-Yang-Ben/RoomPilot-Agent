"""Small, project-authored furniture catalog for the portable profile."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


FIXTURE_PATH = Path(__file__).resolve().parent / "data" / "portable_furniture.json"


@lru_cache(maxsize=1)
def load_fixture_catalog() -> tuple[dict[str, Any], ...]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("portable furniture fixture must contain items")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for source in items:
        item = dict(source)
        item_id = str(item.get("furniture_id") or "").strip()
        if not item_id or item_id in seen:
            raise ValueError(f"portable furniture IDs must be present and unique: {item_id}")
        if item.get("render_mode") != "procedural_fixture":
            raise ValueError(f"portable furniture must be procedural: {item_id}")
        seen.add(item_id)
        normalized.append(item)
    return tuple(normalized)
