"""PostgreSQL read repository for a developer-supplied furniture catalog."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from ..runtime_profile import current_profile


# The public full-profile schema publishes this stable compatibility view.
_VIEW = "roompilot.furniture_catalog_current"

_STYLE_ID_MAP = {
    "american": "american",
    "american_classic": "american",
    "boho": "cream",
    "cream": "cream",
    "contemporary": "modern_minimal",
    "french_country": "cream",
    "industrial": "industrial",
    "japanese": "japanese",
    "japandi": "japanese",
    "mid_century": "modern_minimal",
    "minimalist": "modern_minimal",
    "modern": "modern_minimal",
    "modern_minimal": "modern_minimal",
    "nordic": "scandinavian",
    "rustic": "cream",
    "scandinavian": "scandinavian",
    "scandi_luxe": "scandinavian",
}

_TYPE_ID_MAP = {"planter": "flower-pots-planter"}

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
    "bedroom": {
        "bed", "bed-frame", "mattress", "bedside-table", "pax-wardrobe", "wardrobe",
    },
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

_HAS_MODEL_SQL = "(glb_url IS NOT NULL AND BTRIM(glb_url) <> '')"


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


def _setting(project_dir: Path, name: str, default: str = "") -> str:
    file_values = _read_env_file(project_dir / ".env")
    return os.getenv(name, file_values.get(name, default)).strip()


def catalog_provider_mode(project_dir: Path) -> str:
    """Return the selected catalog provider for the active runtime profile."""
    configured = _setting(project_dir, "ROOMPILOT_CATALOG_PROVIDER", "").casefold()
    if not configured:
        return "fixture" if current_profile() == "portable" else "postgres"
    value = configured
    if value in {"fixture", "portable", "procedural"}:
        return "fixture"
    if value == "postgres":
        return "postgres"
    raise RuntimeError(
        "invalid ROOMPILOT_CATALOG_PROVIDER; expected fixture or postgres"
    )


def _database_config(project_dir: Path) -> dict[str, Any]:
    return {
        "host": _setting(project_dir, "DB_HOST", "localhost"),
        "port": int(_setting(project_dir, "DB_PORT", "5432")),
        "dbname": _setting(project_dir, "DB_NAME", "roompilot_db"),
        "user": _setting(project_dir, "DB_USER", "postgres"),
        "password": _setting(project_dir, "DB_PASSWORD"),
        "connect_timeout": int(_setting(project_dir, "DB_CONNECT_TIMEOUT", "3")),
        "sslmode": _setting(project_dir, "DB_SSLMODE", "disable"),
        "application_name": _setting(
            project_dir, "DB_APPLICATION_NAME", "roompilot_catalog_api"
        ),
    }


_POOL_LOCK = Lock()
_POOLS: dict[tuple[tuple[str, Any], ...], Any] = {}


def _connection_pool(project_dir: Path):
    try:
        from psycopg2.pool import ThreadedConnectionPool
    except ImportError as exc:  # pragma: no cover - depends on deployment extra
        raise RuntimeError("postgres_driver_unavailable") from exc

    config = _database_config(project_dir)
    key = tuple(sorted(config.items()))
    with _POOL_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            minimum = max(1, int(_setting(project_dir, "DB_POOL_MIN", "1")))
            maximum = max(minimum, int(_setting(project_dir, "DB_POOL_MAX", "8")))
            pool = ThreadedConnectionPool(minimum, maximum, **config)
            _POOLS[key] = pool
    return pool


@contextmanager
def _borrow_connection(project_dir: Path) -> Iterator[Any]:
    pool = _connection_pool(project_dir)
    connection = pool.getconn()
    try:
        connection.autocommit = True
        yield connection
    except Exception:
        if not getattr(connection, "closed", True):
            connection.rollback()
        raise
    finally:
        pool.putconn(connection, close=bool(getattr(connection, "closed", False)))


@contextmanager
def borrow_catalog_connection(project_dir: Path) -> Iterator[Any]:
    """Share the catalog pool with other Kai-owned PostgreSQL repositories."""
    with _borrow_connection(project_dir) as connection:
        yield connection


def close_catalog_pools() -> None:
    with _POOL_LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()
    for pool in pools:
        pool.closeall()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [_repair_text(item) for item in value if str(item).strip()]
    return []


def _as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_numbers(value: Any) -> list[float | None]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_as_number(item) for item in value]


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


def _payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    width = _as_number(row.get("width_cm"))
    depth = _as_number(row.get("depth_cm"))
    height = _as_number(row.get("height_cm"))
    database_style_codes = _as_list(row.get("style_codes"))
    style_codes = [_STYLE_ID_MAP.get(code, code) for code in database_style_codes]
    style_confidences = _as_numbers(row.get("style_confidences"))
    primary_confidence = _as_number(row.get("style_confidence"))
    room_codes = _as_list(row.get("room_codes"))
    raw_category_code = str(
        row.get("category_code") or row.get("source_type") or "furniture"
    )
    category_code = str(
        row.get("normalized_type") or _TYPE_ID_MAP.get(raw_category_code, raw_category_code)
    )
    taxonomy_group = str(
        row.get("taxonomy_group") or _catalog_group(raw_category_code, room_codes)
    )
    image_urls = {
        "front": row.get("front_image_url"),
        "side": row.get("side_image_url"),
        "angle-45": row.get("angle_45_image_url"),
    }
    image_urls = {key: value for key, value in image_urls.items() if value}
    model_url = row.get("glb_url") or None
    role = (
        _repair_text(row.get("role"))
        or _repair_text(row.get("source_type"))
        or _repair_text(row.get("kind"))
        or "furniture"
    )

    candidates = []
    for index, style_code in enumerate(style_codes):
        confidence = style_confidences[index] if index < len(style_confidences) else None
        if confidence is None and index == 0:
            confidence = primary_confidence
        candidates.append(
            {"style_id": style_code, "score": confidence if confidence is not None else 1.0}
        )

    return {
        "furniture_id": row.get("item_id"),
        "name_en": _repair_text(row.get("name_en")),
        "name_zh": _repair_text(row.get("name_zh")) or _repair_text(row.get("name_en")),
        "name_zh_raw": _repair_text(row.get("name_zh")) or _repair_text(row.get("name_en")),
        "category_label": _repair_text(row.get("category_label"))
        or _repair_text(row.get("category_name_zh"))
        or category_code,
        "taxonomy_group": taxonomy_group,
        "taxonomy_group_zh": _repair_text(row.get("taxonomy_group_zh"))
        or _GROUP_NAMES.get(taxonomy_group, taxonomy_group),
        "taxonomy_type_zh": _repair_text(row.get("taxonomy_type_zh"))
        or _repair_text(row.get("category_name_zh"))
        or category_code,
        "catalog_scope": _repair_text(row.get("catalog_scope")) or "developer_supplied",
        "normalized_type": category_code,
        "primary_style": style_codes[0] if style_codes else None,
        "style_primary": style_codes[0] if style_codes else None,
        "style_secondary": style_codes[1] if len(style_codes) > 1 else None,
        "style_candidates": candidates,
        "style_confidence": primary_confidence,
        "style_assignment_source": _repair_text(row.get("style_assignment_source"))
        or "developer_supplied",
        "room_types": room_codes,
        "catalog_role": role,
        "role": role,
        "visual_weight": _repair_text(row.get("visual_weight")),
        "height_zone": _repair_text(row.get("height_zone")),
        "size_class": _repair_text(row.get("size_class")),
        "pattern": _repair_text(row.get("pattern")),
        "description": _repair_text(row.get("description")),
        "rag_text": _as_list(row.get("rag_text")),
        "mood_tags": _as_list(row.get("mood_tags")),
        "features": _as_list(row.get("features")),
        "search_keywords": _as_list(row.get("search_keywords")),
        "object_type_zh": _repair_text(row.get("object_type_zh")),
        "color": _repair_text(row.get("primary_color")),
        "material": _repair_text(row.get("primary_material")),
        "price_twd": _as_number(row.get("price_twd")),
        "price_is_estimated": bool(row.get("price_is_estimated")),
        "size_cm": {"width": width, "depth": depth, "height": height},
        "must_against_wall": bool(row.get("must_against_wall", False)),
        "can_rotate": True if row.get("can_rotate") is None else bool(row.get("can_rotate")),
        "usable_for_moodboard": (
            True
            if row.get("usable_for_moodboard") is None
            else bool(row.get("usable_for_moodboard"))
        ),
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
        "match_reason": "依開發者家具資料庫的風格、房間與描述推薦。",
        "rule": {},
    }


def _dict_cursor(connection: Any):
    try:
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - depends on deployment extra
        raise RuntimeError("postgres_driver_unavailable") from exc
    return connection.cursor(cursor_factory=RealDictCursor)


def catalog_dict_cursor(connection: Any):
    """Return a RealDictCursor without duplicating psycopg2 setup code."""
    return _dict_cursor(connection)


def get_catalog_items_by_ids(
    project_dir: Path, furniture_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Fetch a bounded set of active official items without N+1 queries."""
    unique_ids = list(dict.fromkeys(str(item_id) for item_id in furniture_ids if item_id))
    if not unique_ids:
        return {}
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT * FROM {_VIEW} "
                "WHERE kind = 'furniture' AND item_id = ANY(%s::TEXT[])",
                (unique_ids,),
            )
            rows = cursor.fetchall()
    return {
        str(row["item_id"]): _payload_from_row(dict(row))
        for row in rows
    }


def load_catalog(project_dir: Path) -> tuple[dict[str, Any], ...]:
    """Compatibility loader for non-API consumers that still require all rows."""
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT * FROM {_VIEW} WHERE kind = 'furniture' ORDER BY item_id"
            )
            rows = cursor.fetchall()
    if not rows:
        raise RuntimeError("postgres_catalog_empty")
    return tuple(_payload_from_row(dict(row)) for row in rows)


def load_price_index(project_dir: Path) -> dict[str, int]:
    """型錄單價表（``item_id`` → 元），只給第 8 步報價回查。

    刻意不併進 ``_payload_from_row``：單價不進 site_payload / scene_objects，
    選件、擺位與生圖都不該看到價格。
    """
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT item_id, price_twd FROM {_VIEW} "
                "WHERE kind = 'furniture' AND price_twd > 0"
            )
            rows = cursor.fetchall()
    index: dict[str, int] = {}
    for row in rows:
        item_id = str(row.get("item_id") or "").strip()
        price = _as_number(row.get("price_twd"))
        if item_id and price:
            index[item_id] = round(price)
    return index


def catalog_provider_status(project_dir: Path) -> dict[str, Any]:
    """Probe the selected provider without exposing any connection settings."""
    mode = catalog_provider_mode(project_dir)
    if mode == "fixture":
        from .fixture_repository import load_fixture_catalog

        return {
            "provider": "portable_fixture",
            "available": True,
            "ready": True,
            "count": len(load_fixture_catalog()),
            "source_of_truth": "project_authored_fixture",
            "reason": "portable_profile",
            "strict": False,
        }
    try:
        with _borrow_connection(project_dir) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) AS item_count,
                        COUNT(*) FILTER (WHERE {_HAS_MODEL_SQL}) AS model_count,
                        COUNT(*) FILTER (
                            WHERE front_image_url IS NOT NULL AND BTRIM(front_image_url) <> ''
                        ) AS front_image_count,
                        COUNT(*) FILTER (
                            WHERE side_image_url IS NOT NULL AND BTRIM(side_image_url) <> ''
                        ) AS side_image_count,
                        COUNT(*) FILTER (
                            WHERE angle_45_image_url IS NOT NULL
                              AND BTRIM(angle_45_image_url) <> ''
                        ) AS angle_45_image_count,
                        COUNT(*) FILTER (
                            WHERE front_image_url IS NOT NULL AND BTRIM(front_image_url) <> ''
                              AND side_image_url IS NOT NULL AND BTRIM(side_image_url) <> ''
                              AND angle_45_image_url IS NOT NULL
                              AND BTRIM(angle_45_image_url) <> ''
                        ) AS complete_image_item_count
                    FROM {_VIEW}
                    WHERE kind = 'furniture'
                    """
                )
                row = cursor.fetchone()
                count = int(row[0])
                assets = {
                    "model_count": int(row[1]),
                    "front_image_count": int(row[2]),
                    "side_image_count": int(row[3]),
                    "angle_45_image_count": int(row[4]),
                    "complete_image_item_count": int(row[5]),
                }
                # The canonical import may have been loaded directly without the
                # optional staging schema.  Status probing must not mark a healthy
                # catalog unavailable just because import history is absent.
                batch = None
                cursor.execute(
                    """
                    SELECT
                        CURRENT_DATABASE(),
                        CURRENT_SETTING('server_version'),
                        TO_REGCLASS('roompilot.furniture_catalog_current') IS NOT NULL,
                        FALSE AS project_table_ready,
                        NULL::TIMESTAMPTZ AS data_revision,
                        NULL::BIGINT AS project_count
                    """
                )
                database = cursor.fetchone()
                import_batch = (
                    {
                        "batch_key": str(batch[0]),
                        "imported_at": batch[1].isoformat(),
                        "source_file": str(batch[2]),
                        "record_count": int(batch[3]),
                    }
                    if batch
                    else None
                )
        return {
            "provider": "postgres",
            "available": count > 0,
            "ready": count > 0 and bool(database[2]),
            "count": count,
            "assets": assets,
            "strict": mode == "postgres",
            "source_of_truth": "postgresql",
            "api_view": "roompilot.furniture_catalog_current",
            "data_revision": database[4].isoformat() if database[4] else None,
            "import_batch": import_batch,
            "database": {
                "name": str(database[0]),
                "server_version": str(database[1]),
                "api_view_ready": bool(database[2]),
                "project_table_ready": bool(database[3]),
                "project_count": int(database[5]) if database[5] is not None else None,
            },
        }
    except Exception as exc:
        return {
            "provider": "postgres",
            "available": False,
            "ready": False,
            "reason": type(exc).__name__,
            "strict": True,
            "source_of_truth": "postgresql",
        }
