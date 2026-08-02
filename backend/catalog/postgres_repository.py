"""PostgreSQL read repository for Kai's official furniture catalog.

The repository owns catalog querying and row-to-domain mapping.  FastAPI is a
consumer of this module: it must not load the complete catalog merely to
filter, count, facet, or paginate it.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Iterator


# The imported Kai migration currently publishes this compatibility view.  Keep
# the runtime on it until Django owns the api_current view migration as well.
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

_STYLE_CODES_BY_API_ID: dict[str, tuple[str, ...]] = {}
for _database_style, _api_style in _STYLE_ID_MAP.items():
    _STYLE_CODES_BY_API_ID.setdefault(_api_style, ())
    _STYLE_CODES_BY_API_ID[_api_style] += (_database_style,)

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

_FACET_TRANSLATIONS = {
    "color": {
        "white": "白色",
        "black": "黑色",
        "grey": "灰色",
        "gray": "灰色",
        "beige": "米色",
        "brown": "棕色",
        "green": "綠色",
        "blue": "藍色",
        "red": "紅色",
        "silver": "銀色",
        "gold": "金色",
        "yellow": "黃色",
        "wood": "木色",
        "walnut": "胡桃木色",
        "navy": "海軍藍",
    },
    "material": {
        "wood": "木材",
        "oak": "橡木",
        "metal": "金屬",
        "fabric": "布料",
        "textile": "織物",
        "leather": "皮革",
        "glass": "玻璃",
        "steel": "鋼材",
        "birch": "樺木",
        "walnut": "胡桃木",
        "wood veneer": "木皮",
        "solid wood": "實木",
        "plywood": "夾板",
        "plastic": "塑膠",
    },
}

_IGNORED_FACET_VALUES = {"", "尚未整理", "未整理", "unknown", "none", "null", "-"}
_SIZE_OPTIONS = [
    {"value": "small", "label": "小型（80 cm 以下）"},
    {"value": "medium", "label": "中型（81–160 cm）"},
    {"value": "large", "label": "大型（161 cm 以上）"},
]


_TYPE_SQL = "COALESCE(normalized_type, category_code, source_type, 'furniture')"
_GROUP_SQL = "COALESCE(taxonomy_group, 'soft_decor')"
_HAS_MODEL_SQL = "(glb_url IS NOT NULL AND BTRIM(glb_url) <> '')"
_SIZE_SQL = """
CASE
    WHEN GREATEST(width_cm, depth_cm) <= 80 THEN 'small'
    WHEN GREATEST(width_cm, depth_cm) <= 160 THEN 'medium'
    WHEN GREATEST(width_cm, depth_cm) > 160 THEN 'large'
    ELSE NULL
END
""".strip()
_SEARCH_SQL = """
LOWER(CONCAT_WS(
    ' ', item_id, name_en, name_zh, category_code, category_name_zh,
    source_type, primary_color, primary_material,
    ARRAY_TO_STRING(COALESCE(style_codes::TEXT[], ARRAY[]::TEXT[]), ' '),
    ARRAY_TO_STRING(COALESCE(room_codes::TEXT[], ARRAY[]::TEXT[]), ' '),
    object_type_zh, description,
    ARRAY_TO_STRING(COALESCE(rag_text, ARRAY[]::TEXT[]), ' ')
))
""".strip()


@dataclass(frozen=True)
class CatalogQuery:
    style: str | None = None
    group: str | None = None
    item_type: str | None = None
    q: str | None = None
    page: int = 1
    page_size: int = 24
    has_model: bool | None = None
    color: str | None = None
    material: str | None = None
    size: str | None = None


@dataclass(frozen=True)
class CatalogPage:
    items: tuple[dict[str, Any], ...]
    page: int
    page_size: int
    total: int
    type_options: tuple[dict[str, Any], ...]
    category_groups: tuple[dict[str, Any], ...]
    filter_options: dict[str, list[dict[str, Any]]]
    model_urls: tuple[str, ...]

    @property
    def has_next_page(self) -> bool:
        return self.page * self.page_size < self.total


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
    """Return strict ``postgres`` by default or explicit offline ``json``."""
    value = _setting(project_dir, "ROOMPILOT_CATALOG_PROVIDER", "postgres").casefold()
    if value in {"json", "local", "fallback"}:
        return "json"
    return "postgres"


def postgres_catalog_requested(project_dir: Path) -> bool:
    return catalog_provider_mode(project_dir) != "json"


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
        "catalog_scope": _repair_text(row.get("catalog_scope")) or "kai_postgresql",
        "normalized_type": category_code,
        "primary_style": style_codes[0] if style_codes else None,
        "style_primary": style_codes[0] if style_codes else None,
        "style_secondary": style_codes[1] if len(style_codes) > 1 else None,
        "style_candidates": candidates,
        "style_confidence": primary_confidence,
        "style_assignment_source": _repair_text(row.get("style_assignment_source"))
        or "kai_postgresql_vlm",
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
        "match_reason": "依 Kai 正式家具資料庫的風格、房間與 VLM 描述推薦。",
        "rule": {},
    }


def _normalize_facet_value(value: object, key: str) -> str:
    import re

    translations = _FACET_TRANSLATIONS.get(key, {})
    parts = [part.strip() for part in re.split(r"[,/、]+", str(value or "")) if part.strip()]
    return "、".join(translations.get(part.casefold(), part) for part in parts)


def _facet_candidates(value: str, key: str) -> list[str]:
    normalized = _normalize_facet_value(value, key).casefold()
    candidates = {value.strip().casefold(), normalized}
    for source, label in _FACET_TRANSLATIONS.get(key, {}).items():
        if label.casefold() == normalized:
            candidates.add(source.casefold())
    return sorted(candidate for candidate in candidates if candidate)


def _style_codes(style: str) -> list[str]:
    return list(_STYLE_CODES_BY_API_ID.get(style, (style,)))


def _where_clause(
    query: CatalogQuery,
    *,
    include_group: bool = True,
    include_type: bool = True,
    include_query: bool = True,
    include_color: bool = True,
    include_material: bool = True,
    include_size: bool = True,
) -> tuple[str, list[Any]]:
    predicates = ["kind = 'furniture'"]
    params: list[Any] = []

    if query.style:
        predicates.append(
            "COALESCE(style_codes::TEXT[], ARRAY[]::TEXT[]) && %s::TEXT[]"
        )
        params.append(_style_codes(query.style))
    if include_group and query.group:
        predicates.append(f"{_GROUP_SQL} = %s")
        params.append(query.group)
    if include_type and query.item_type:
        predicates.append(f"{_TYPE_SQL} = %s")
        params.append(query.item_type)
    if query.has_model is not None:
        predicates.append(f"{_HAS_MODEL_SQL} = %s")
        params.append(query.has_model)
    if include_query and query.q and query.q.strip():
        predicates.append(f"POSITION(LOWER(%s) IN {_SEARCH_SQL}) > 0")
        params.append(query.q.strip())
    if include_color and query.color:
        predicates.append("LOWER(BTRIM(COALESCE(primary_color, ''))) = ANY(%s::TEXT[])")
        params.append(_facet_candidates(query.color, "color"))
    if include_material and query.material:
        predicates.append("LOWER(BTRIM(COALESCE(primary_material, ''))) = ANY(%s::TEXT[])")
        params.append(_facet_candidates(query.material, "material"))
    if include_size and query.size:
        predicates.append(f"{_SIZE_SQL} = %s")
        params.append(query.size)
    return " WHERE " + " AND ".join(predicates), params


def _dict_cursor(connection: Any):
    try:
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:  # pragma: no cover - depends on deployment extra
        raise RuntimeError("postgres_driver_unavailable") from exc
    return connection.cursor(cursor_factory=RealDictCursor)


def catalog_dict_cursor(connection: Any):
    """Return a RealDictCursor without duplicating psycopg2 setup code."""
    return _dict_cursor(connection)


def _counted_facets(cursor: Any, where_sql: str, params: list[Any]) -> dict[str, list[dict[str, Any]]]:
    counts_by_key: dict[str, dict[str, int]] = {"color": {}, "material": {}}
    for key, column in (("color", "primary_color"), ("material", "primary_material")):
        cursor.execute(
            f"SELECT {column} AS value, COUNT(*) AS count FROM {_VIEW}"
            f"{where_sql} GROUP BY {column}",
            params,
        )
        for row in cursor.fetchall():
            value = _normalize_facet_value(row.get("value"), key)
            if value.casefold() in _IGNORED_FACET_VALUES or "�" in value:
                continue
            counts_by_key[key][value] = counts_by_key[key].get(value, 0) + int(row["count"])

    def options(key: str) -> list[dict[str, Any]]:
        return [
            {"value": value, "label": value, "count": count}
            for value, count in sorted(
                counts_by_key[key].items(), key=lambda pair: (-pair[1], pair[0])
            )[:18]
        ]

    return {"sizes": list(_SIZE_OPTIONS), "colors": options("color"), "materials": options("material")}


def _type_options(cursor: Any, query: CatalogQuery) -> tuple[dict[str, Any], ...]:
    where_sql, params = _where_clause(
        query,
        include_type=False,
        include_query=False,
        include_color=False,
        include_material=False,
        include_size=False,
    )
    cursor.execute(
        f"SELECT {_TYPE_SQL} AS type, "
        f"MAX(COALESCE(taxonomy_type_zh, category_name_zh, {_TYPE_SQL})) AS type_name_zh, "
        f"COUNT(*) AS count FROM {_VIEW}{where_sql} GROUP BY 1 ORDER BY count DESC, type",
        params,
    )
    return tuple(
        {
            "type": row["type"],
            "count": int(row["count"]),
            "type_name_zh": _repair_text(row.get("type_name_zh")) or row["type"],
        }
        for row in cursor.fetchall()
    )


def _category_groups(cursor: Any, query: CatalogQuery) -> tuple[dict[str, Any], ...]:
    where_sql, params = _where_clause(
        query,
        include_group=False,
        include_type=False,
        include_query=False,
        include_color=False,
        include_material=False,
        include_size=False,
    )
    cursor.execute(
        f"SELECT {_GROUP_SQL} AS group_id, {_TYPE_SQL} AS type, "
        f"MAX(COALESCE(taxonomy_type_zh, category_name_zh, {_TYPE_SQL})) AS type_name_zh, "
        f"COUNT(*) AS count FROM {_VIEW}{where_sql} GROUP BY 1, 2",
        params,
    )
    groups: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        group_id = str(row.get("group_id") or "soft_decor")
        group = groups.setdefault(
            group_id,
            {
                "group_id": group_id,
                "group_name_zh": _GROUP_NAMES.get(group_id, group_id),
                "types": [],
            },
        )
        group["types"].append(
            {
                "type": row["type"],
                "type_name_zh": _repair_text(row.get("type_name_zh")) or row["type"],
                "count": int(row["count"]),
            }
        )
    for group in groups.values():
        group["types"].sort(key=lambda entry: entry["type_name_zh"])
    return tuple(sorted(groups.values(), key=lambda entry: entry["group_name_zh"]))


def query_catalog_page(project_dir: Path, query: CatalogQuery) -> CatalogPage:
    """Execute SQL filtering, counting, facets and pagination for one API page."""
    if query.page < 1 or not 1 <= query.page_size <= 80:
        raise ValueError("catalog_page_out_of_range")

    final_where, final_params = _where_clause(query)
    facet_where, facet_params = _where_clause(
        query, include_color=False, include_material=False, include_size=False
    )
    offset = (query.page - 1) * query.page_size

    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM {_VIEW}{final_where}", final_params
            )
            total = int(cursor.fetchone()["total"])

            cursor.execute(
                f"SELECT * FROM {_VIEW}{final_where} ORDER BY item_id LIMIT %s OFFSET %s",
                [*final_params, query.page_size, offset],
            )
            items = tuple(_payload_from_row(dict(row)) for row in cursor.fetchall())

            type_options = _type_options(cursor, query)
            category_groups = _category_groups(cursor, query)
            filter_options = _counted_facets(cursor, facet_where, facet_params)

            cursor.execute(
                f"SELECT glb_url FROM {_VIEW}{final_where} ORDER BY item_id LIMIT 24",
                final_params,
            )
            model_urls = tuple(
                str(row["glb_url"])
                for row in cursor.fetchall()
                if str(row.get("glb_url") or "").startswith(("https://", "http://"))
            )

    return CatalogPage(
        items=items,
        page=query.page,
        page_size=query.page_size,
        total=total,
        type_options=type_options,
        category_groups=category_groups,
        filter_options=filter_options,
        model_urls=tuple(dict.fromkeys(model_urls)),
    )


def get_catalog_item(project_dir: Path, furniture_id: str) -> dict[str, Any] | None:
    """Fetch one active official furniture item by its primary key."""
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT * FROM {_VIEW} WHERE kind = 'furniture' AND item_id = %s",
                (furniture_id,),
            )
            row = cursor.fetchone()
    return _payload_from_row(dict(row)) if row else None


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


def catalog_summary(project_dir: Path) -> dict[str, Any]:
    """Build current six-style counts from SQL without a process-lifetime cache."""
    mapping = tuple(_STYLE_ID_MAP.items())
    values_sql = ", ".join(["(%s, %s)"] * len(mapping))
    mapping_params = [value for pair in mapping for value in pair]
    expanded_cte = f"""
        WITH style_map(database_style, ui_style) AS (VALUES {values_sql}),
        expanded AS (
            SELECT DISTINCT catalog.item_id, catalog.normalized_type, style_map.ui_style
            FROM {_VIEW} AS catalog
            CROSS JOIN LATERAL UNNEST(
                COALESCE(catalog.style_codes::TEXT[], ARRAY[]::TEXT[])
            ) AS source_style(database_style)
            JOIN style_map
              ON style_map.database_style = source_style.database_style
            WHERE catalog.kind = 'furniture'
        )
    """
    with _borrow_connection(project_dir) as connection:
        with _dict_cursor(connection) as cursor:
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM {_VIEW} WHERE kind = 'furniture'"
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                expanded_cte + "SELECT COUNT(DISTINCT item_id) AS styled FROM expanded",
                mapping_params,
            )
            styled_count = int(cursor.fetchone()["styled"])
            cursor.execute(
                expanded_cte
                + """
                  SELECT ui_style, normalized_type, COUNT(*) AS count
                  FROM expanded
                  GROUP BY ui_style, normalized_type
                  ORDER BY ui_style, count DESC, normalized_type
                  """,
                mapping_params,
            )
            rows = cursor.fetchall()
    style_counts: dict[str, int] = {}
    style_type_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        style_id = str(row["ui_style"])
        item_type = str(row.get("normalized_type") or "unknown")
        count = int(row["count"])
        style_counts[style_id] = style_counts.get(style_id, 0) + count
        style_type_counts.setdefault(style_id, {})[item_type] = count
    return {
        "total_furniture": total,
        "styled_furniture": styled_count,
        "fallback_furniture": total - styled_count,
        "style_furniture_counts": style_counts,
        "style_type_counts": {
            style_id: sorted(
                type_counts.items(), key=lambda pair: (-pair[1], pair[0])
            )
            for style_id, type_counts in style_type_counts.items()
        },
    }


def catalog_provider_status(project_dir: Path) -> dict[str, Any]:
    """Probe the selected provider without exposing any connection settings."""
    mode = catalog_provider_mode(project_dir)
    if mode == "json":
        return {
            "provider": "json_offline",
            "available": True,
            "ready": True,
            "source_of_truth": "versioned_files",
            "reason": "explicit_json_mode",
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
            "provider": "kai_postgresql",
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
            "provider": "kai_postgresql",
            "available": False,
            "ready": False,
            "reason": type(exc).__name__,
            "strict": True,
            "source_of_truth": "postgresql",
        }
