"""Read the approved Kai furniture catalog without leaking database settings.

The API consumes a stable, frontend-oriented payload.  PostgreSQL is the
authoritative source when available; callers can fall back to the checked-in
catalog when it is not.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_VIEW = "roompilot.furniture_catalog_current"

_STYLE_ID_MAP = {
    "american_classic": "american",
    "boho": "cream",
    "contemporary": "modern_minimal",
    "french_country": "cream",
    "industrial": "industrial",
    "japandi": "japanese",
    "mid_century": "modern_minimal",
    "minimalist": "modern_minimal",
    "modern": "modern_minimal",
    "nordic": "scandinavian",
    "rustic": "cream",
    "scandi_luxe": "scandinavian",
}

_TYPE_ID_MAP = {
    "planter": "flower-pots-planter",
}

_GROUP_NAMES = {
    "living": "客廳家具",
    "dining_kitchen": "餐廚家具",
    "bedroom": "臥室家具",
    "study": "書房家具",
    "storage": "收納家具",
    "soft_decor": "軟裝與燈飾",
}

_GROUP_TYPES = {
    "living": {
        "fabric-sofa", "leather-sofa", "sofa", "sofa-bed", "modular-sofa",
        "armchair", "coffee-table", "tv-bench", "tv-media-furniture",
    },
    "dining_kitchen": {
        "dining-chair", "dining-table", "bar-table", "stool-bench", "table",
    },
    "bedroom": {"bed", "bed-frame", "mattress", "bedside-table", "pax-wardrobe", "wardrobe"},
    "study": {"desk", "office-chair", "gaming-chair", "work-lamp"},
    "storage": {
        "bookcase", "cabinet-cupboard", "chests-of-drawer", "shelving-unit",
        "storage-boxes-basket", "storage-solution-system", "sideboard", "wall-shelf",
        "display-cabinet", "shoe-cabinet", "storage-furniture", "clothes-rack",
    },
    "soft_decor": {
        "large-medium-rug", "runner-small-rug", "rug", "round-rug", "handmade-rug",
        "sheepskins-cowhide", "outdoor-rug", "planter", "lamp", "table-lamp",
        "floor-lamp", "wall-lamp", "ceiling-lamp", "pendant-lamp", "lamp-shades-base",
        "pillow-cushion", "decoration", "vase", "mirror", "large-mirror",
        "standing-mirror", "wall-art", "wall-mirror", "door-mat",
    },
}


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _database_config(project_dir: Path) -> dict[str, Any]:
    file_values = _read_env_file(project_dir / ".env")

    def value(name: str, default: str = "") -> str:
        return os.getenv(name, file_values.get(name, default)).strip()

    return {
        "host": value("DB_HOST", "localhost"),
        "port": int(value("DB_PORT", "5432")),
        "dbname": value("DB_NAME", "roompilot_db"),
        "user": value("DB_USER", "postgres"),
        "password": value("DB_PASSWORD"),
        "connect_timeout": int(value("DB_CONNECT_TIMEOUT", "3")),
        "sslmode": value("DB_SSLMODE", "disable"),
        "application_name": value("DB_APPLICATION_NAME", "roompilot_catalog_api"),
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_repair_text(item) for item in value if str(item).strip()]
    return []


def _repair_text(value: Any) -> str:
    text = str(value or "")
    try:
        return text.encode("latin1").decode("big5")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _catalog_group(category_code: str, room_codes: list[str]) -> str:
    for group, item_types in _GROUP_TYPES.items():
        if category_code in item_types:
            return group
    if "study" in room_codes:
        return "study"
    if "bedroom" in room_codes:
        return "bedroom"
    if "dining_room" in room_codes:
        return "dining_kitchen"
    if "living_room" in room_codes:
        return "living"
    return "soft_decor"


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    width = _as_number(row.get("width_cm"))
    depth = _as_number(row.get("depth_cm"))
    height = _as_number(row.get("height_cm"))
    style_codes = [
        _STYLE_ID_MAP.get(style_code, style_code)
        for style_code in _as_list(row.get("style_codes"))
    ]
    room_codes = _as_list(row.get("room_codes"))
    raw_category_code = str(row.get("category_code") or row.get("source_type") or "furniture")
    category_code = _TYPE_ID_MAP.get(raw_category_code, raw_category_code)
    taxonomy_group = _catalog_group(raw_category_code, room_codes)
    image_urls = {
        "front": row.get("front_image_url"),
        "side": row.get("side_image_url"),
        "angle-45": row.get("angle_45_image_url"),
    }
    image_urls = {key: value for key, value in image_urls.items() if value}
    model_url = row.get("glb_url") or None
    return {
        "furniture_id": row.get("item_id"),
        "name_en": _repair_text(row.get("name_en")),
        "name_zh": _repair_text(row.get("name_zh")) or _repair_text(row.get("name_en")),
        "name_zh_raw": _repair_text(row.get("name_zh")) or _repair_text(row.get("name_en")),
        "category_label": _repair_text(row.get("category_name_zh")) or category_code,
        "taxonomy_group": taxonomy_group,
        "taxonomy_group_zh": _GROUP_NAMES[taxonomy_group],
        "taxonomy_type_zh": _repair_text(row.get("category_name_zh")) or category_code,
        "catalog_scope": "kai_postgresql",
        "normalized_type": category_code,
        "primary_style": style_codes[0] if style_codes else None,
        "style_primary": style_codes[0] if style_codes else None,
        "style_secondary": style_codes[1] if len(style_codes) > 1 else None,
        "style_candidates": [
            {"style_id": style_code, "score": 1.0}
            for style_code in style_codes
        ],
        "style_confidence": None,
        "style_assignment_source": "kai_postgresql_vlm",
        "room_types": room_codes,
        "catalog_role": _repair_text(row.get("source_type")) or _repair_text(row.get("kind")) or "furniture",
        "role": _repair_text(row.get("source_type")) or _repair_text(row.get("kind")) or "furniture",
        "description": _repair_text(row.get("description")),
        "rag_text": _as_list(row.get("rag_text")),
        "object_type_zh": _repair_text(row.get("object_type_zh")),
        "color": _repair_text(row.get("primary_color")),
        "material": _repair_text(row.get("primary_material")),
        "size_cm": {"width": width, "depth": depth, "height": height},
        "must_against_wall": False,
        "can_rotate": True,
        "has_model": bool(model_url),
        "missing_model_reason": None if model_url else "缺少可載入的 GLB 模型。",
        "model_url": model_url,
        "image_url": image_urls.get("front") or image_urls.get("angle-45") or image_urls.get("side"),
        "thumbnail_url": image_urls.get("front") or image_urls.get("angle-45") or image_urls.get("side"),
        "preview_url": image_urls.get("front") or image_urls.get("angle-45") or image_urls.get("side"),
        "preview_images": image_urls,
        "quantity": {"min": None, "max": None, "recommended": None},
        "placement_hints": {},
        "clearance_zones": [],
        "layout_relations": [],
        "match_reason": "依 Kai 正式家具資料庫的風格、房間與 VLM 描述推薦。",
        "rule": {},
    }


def load_catalog(project_dir: Path) -> tuple[dict[str, Any], ...]:
    """Return active Kai furniture rows, or raise a normal connection error."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - depends on optional local driver
        raise RuntimeError("postgres_driver_unavailable") from exc

    with psycopg2.connect(**_database_config(project_dir)) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                f"SELECT * FROM {_VIEW} WHERE kind = 'furniture' ORDER BY item_id"
            )
            rows = cursor.fetchall()
    if not rows:
        raise RuntimeError("postgres_catalog_empty")
    return tuple(_payload_from_row(dict(row)) for row in rows)


def catalog_provider_status(project_dir: Path) -> dict[str, Any]:
    """A cheap status probe used by /api/catalog/status and diagnostics."""
    try:
        import psycopg2
    except ImportError:
        return {"provider": "json_fallback", "available": False, "reason": "postgres_driver_unavailable"}

    try:
        with psycopg2.connect(**_database_config(project_dir)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT count(*) FROM {_VIEW} WHERE kind = 'furniture'")
                count = int(cursor.fetchone()[0])
        return {"provider": "kai_postgresql", "available": count > 0, "count": count}
    except Exception as exc:  # The web server must remain usable without PostgreSQL.
        return {"provider": "json_fallback", "available": False, "reason": type(exc).__name__}
