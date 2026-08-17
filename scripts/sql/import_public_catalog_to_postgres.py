#!/usr/bin/env python3
"""Validate and import a developer-supplied furniture catalog into PostgreSQL.

The importer has no bundled production dataset and no fixed record-count
assumption. Every row must carry a license, directly or through the catalog
root, and dimensions are expressed in centimeters.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = PROJECT_ROOT / "docker_postgresql" / "init" / "001_roompilot.sql"

COLUMNS = (
    "item_id",
    "kind",
    "name_en",
    "name_zh",
    "category_code",
    "category_name_zh",
    "source_type",
    "normalized_type",
    "taxonomy_group",
    "taxonomy_group_zh",
    "taxonomy_type_zh",
    "catalog_scope",
    "role",
    "width_cm",
    "depth_cm",
    "height_cm",
    "primary_color",
    "primary_material",
    "style_codes",
    "style_confidences",
    "style_confidence",
    "style_assignment_source",
    "room_codes",
    "description",
    "rag_text",
    "mood_tags",
    "features",
    "search_keywords",
    "object_type_zh",
    "visual_weight",
    "height_zone",
    "size_class",
    "pattern",
    "must_against_wall",
    "can_rotate",
    "usable_for_moodboard",
    "glb_url",
    "front_image_url",
    "side_image_url",
    "angle_45_image_url",
    "price_twd",
    "is_active",
    "source_license",
    "license_status",
    "source_url",
)

_UPDATE_COLUMNS = tuple(column for column in COLUMNS if column != "item_id")
UPSERT_SQL = f"""
INSERT INTO roompilot.furniture_catalog ({', '.join(COLUMNS)})
VALUES %s
ON CONFLICT (item_id) DO UPDATE SET
    {', '.join(f'{column} = EXCLUDED.{column}' for column in _UPDATE_COLUMNS)},
    updated_at = NOW()
""".strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and UPSERT a licensed furniture catalog.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        required=True,
        help="JSON array, or an object containing items/furniture.",
    )
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Apply the public generic schema before importing.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--page-size", type=int, default=500)
    return parser.parse_args(argv)


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


def db_config(env_path: Path) -> dict[str, Any]:
    file_values = _read_env_file(env_path)

    def setting(name: str, default: str = "") -> str:
        return os.getenv(name, file_values.get(name, default)).strip()

    return {
        "host": setting("DB_HOST", "127.0.0.1"),
        "port": int(setting("DB_PORT", "5432")),
        "dbname": setting("DB_NAME", "roompilot_db"),
        "user": setting("DB_USER", "roompilot"),
        "password": setting("DB_PASSWORD"),
        "sslmode": setting("DB_SSLMODE", "disable"),
        "connect_timeout": int(setting("DB_CONNECT_TIMEOUT", "10")),
        "application_name": setting(
            "DB_APPLICATION_NAME", "roompilot_catalog_import"
        ),
    }


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"catalog does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
        metadata: dict[str, Any] = {}
    elif isinstance(payload, dict):
        raw_items = payload.get("items")
        if raw_items is None:
            raw_items = payload.get("furniture")
        items = raw_items
        metadata = {
            key: value
            for key, value in payload.items()
            if key not in {"items", "furniture"}
        }
    else:
        raise ValueError("catalog root must be an array or object")
    if not isinstance(items, list) or not items:
        raise ValueError("catalog must contain at least one item")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("every catalog item must be an object")
    return items, metadata


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values: Iterable[Any] = [value]
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        raise ValueError(f"expected a string list, got {type(value).__name__}")
    result: list[str] = []
    for raw in values:
        text = _text(raw)
        if text and text not in result:
            result.append(text)
    return result


def _number(value: Any, *, field: str, required: bool = False) -> float | None:
    if value is None or value == "":
        if required:
            raise ValueError(f"{field} is required")
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if required and number <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return number


def _boolean(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def _dimension(item: dict[str, Any], field: str) -> float:
    nested = item.get("size_cm") if isinstance(item.get("size_cm"), dict) else {}
    nested_key = field.removesuffix("_cm")
    value = item.get(field, nested.get(nested_key))
    result = _number(value, field=field, required=True)
    assert result is not None
    return result


def _style_values(item: dict[str, Any]) -> tuple[list[str], list[float], float | None]:
    codes = _text_list(item.get("style_codes"))
    candidates = item.get("style_candidates") or []
    candidate_scores: dict[str, float] = {}
    if not isinstance(candidates, list):
        raise ValueError("style_candidates must be a list")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("style candidate must be an object")
        style_id = _text(candidate.get("style_id"))
        if not style_id:
            continue
        if style_id not in codes:
            codes.append(style_id)
        score = _number(candidate.get("score"), field="style score")
        if score is not None:
            candidate_scores[style_id] = score
    for field in ("primary_style", "style_primary", "style_secondary"):
        style_id = _text(item.get(field))
        if style_id and style_id not in codes:
            codes.append(style_id)

    raw_confidences = item.get("style_confidences")
    if raw_confidences is not None:
        if not isinstance(raw_confidences, list):
            raise ValueError("style_confidences must be a list")
        confidences = [
            float(_number(value, field="style confidence") or 0.0)
            for value in raw_confidences
        ]
    else:
        confidences = [candidate_scores.get(code, 1.0) for code in codes]
    if len(confidences) != len(codes):
        raise ValueError("style_codes and style_confidences must have equal lengths")
    primary = _number(item.get("style_confidence"), field="style_confidence")
    if primary is None and confidences:
        primary = confidences[0]
    return codes, confidences, primary


def _url(value: Any, field: str) -> str | None:
    url = _text(value)
    if url and not url.casefold().startswith(("https://", "http://")):
        raise ValueError(f"{field} must use HTTP or HTTPS")
    return url


def normalize_catalog(
    items: list[dict[str, Any]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    root_license = _text(metadata.get("source_license") or metadata.get("license"))
    root_license_status = _text(metadata.get("license_status")) or "verified"
    root_source_url = _text(metadata.get("source_url"))
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, item in enumerate(items, start=1):
        try:
            item_id = _text(
                item.get("item_id") or item.get("furniture_id") or item.get("id")
            )
            if not item_id:
                raise ValueError("item_id is required")
            if item_id in seen_ids:
                raise ValueError(f"duplicate item_id: {item_id}")
            seen_ids.add(item_id)

            kind = _text(item.get("kind")) or "furniture"
            if kind != "furniture":
                raise ValueError("only kind=furniture may enter the planning catalog")
            name_zh = _text(item.get("name_zh") or item.get("name_zh_raw"))
            name_en = _text(item.get("name_en") or item.get("name") or name_zh)
            if not name_en:
                raise ValueError("name_en, name, or name_zh is required")
            source_license = _text(item.get("source_license")) or root_license
            if not source_license:
                raise ValueError("source_license is required")
            license_status = (
                _text(item.get("license_status")) or root_license_status
            ).casefold()
            if license_status not in {
                "verified",
                "permission_required",
                "unverified",
            }:
                raise ValueError(
                    "license_status must be verified, permission_required, or unverified"
                )

            styles, style_confidences, style_confidence = _style_values(item)
            room_codes = _text_list(item.get("room_codes") or item.get("room_types"))
            price_value = _number(item.get("price_twd"), field="price_twd")
            if price_value is not None and price_value < 0:
                raise ValueError("price_twd cannot be negative")

            normalized.append(
                {
                    "item_id": item_id,
                    "kind": kind,
                    "name_en": name_en,
                    "name_zh": name_zh,
                    "category_code": _text(item.get("category_code")),
                    "category_name_zh": _text(
                        item.get("category_name_zh") or item.get("category_label")
                    ),
                    "source_type": _text(item.get("source_type")),
                    "normalized_type": _text(item.get("normalized_type")),
                    "taxonomy_group": _text(item.get("taxonomy_group")),
                    "taxonomy_group_zh": _text(item.get("taxonomy_group_zh")),
                    "taxonomy_type_zh": _text(item.get("taxonomy_type_zh")),
                    "catalog_scope": _text(item.get("catalog_scope"))
                    or "developer_supplied",
                    "role": _text(item.get("role") or item.get("catalog_role")),
                    "width_cm": _dimension(item, "width_cm"),
                    "depth_cm": _dimension(item, "depth_cm"),
                    "height_cm": _dimension(item, "height_cm"),
                    "primary_color": _text(
                        item.get("primary_color") or item.get("color")
                    ),
                    "primary_material": _text(
                        item.get("primary_material") or item.get("material")
                    ),
                    "style_codes": styles,
                    "style_confidences": style_confidences,
                    "style_confidence": style_confidence,
                    "style_assignment_source": _text(
                        item.get("style_assignment_source")
                    )
                    or "developer_supplied",
                    "room_codes": room_codes,
                    "description": _text(item.get("description")),
                    "rag_text": _text_list(item.get("rag_text")),
                    "mood_tags": _text_list(item.get("mood_tags")),
                    "features": _text_list(item.get("features")),
                    "search_keywords": _text_list(item.get("search_keywords")),
                    "object_type_zh": _text(item.get("object_type_zh")),
                    "visual_weight": _text(item.get("visual_weight")),
                    "height_zone": _text(item.get("height_zone")),
                    "size_class": _text(item.get("size_class")),
                    "pattern": _text(item.get("pattern")),
                    "must_against_wall": _boolean(
                        item.get("must_against_wall"), False
                    ),
                    "can_rotate": _boolean(item.get("can_rotate"), True),
                    "usable_for_moodboard": _boolean(
                        item.get("usable_for_moodboard"), True
                    ),
                    "glb_url": _url(
                        item.get("glb_url") or item.get("model_url"), "glb_url"
                    ),
                    "front_image_url": _url(
                        item.get("front_image_url"), "front_image_url"
                    ),
                    "side_image_url": _url(
                        item.get("side_image_url"), "side_image_url"
                    ),
                    "angle_45_image_url": _url(
                        item.get("angle_45_image_url"), "angle_45_image_url"
                    ),
                    "price_twd": int(price_value) if price_value is not None else None,
                    "is_active": _boolean(item.get("is_active"), True),
                    "source_license": source_license,
                    "license_status": license_status,
                    "source_url": _url(
                        item.get("source_url") or root_source_url, "source_url"
                    ),
                }
            )
        except ValueError as exc:
            raise ValueError(f"catalog item {index}: {exc}") from exc
    return normalized


def connect_db(env_path: Path):
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("install the postgres extra before importing") from exc
    return psycopg2.connect(**db_config(env_path))


def apply_schema(connection: Any, schema_path: Path) -> None:
    if not schema_path.is_file():
        raise FileNotFoundError(f"schema does not exist: {schema_path}")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8"))


def upsert_catalog(connection: Any, rows: list[dict[str, Any]], page_size: int) -> None:
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    try:
        from psycopg2.extras import execute_values
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("install the postgres extra before importing") from exc
    values = [tuple(row[column] for column in COLUMNS) for row in rows]
    with connection:
        with connection.cursor() as cursor:
            execute_values(cursor, UPSERT_SQL, values, page_size=page_size)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    items, metadata = load_catalog(args.catalog)
    rows = normalize_catalog(items, metadata)
    summary = {
        "catalog": str(args.catalog.resolve()),
        "count": len(rows),
        "active_count": sum(row["is_active"] for row in rows),
        "licensed_count": sum(bool(row["source_license"]) for row in rows),
        "public_count": sum(
            row["is_active"] and row["license_status"] == "verified" for row in rows
        ),
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    connection = connect_db(args.env)
    try:
        if args.create_schema:
            apply_schema(connection, args.schema_sql)
        upsert_catalog(connection, rows, args.page_size)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
