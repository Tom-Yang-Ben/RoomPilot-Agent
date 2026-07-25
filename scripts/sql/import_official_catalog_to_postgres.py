"""Validate and import RoomPilot's official 9,350 cloud furniture into PostgreSQL."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - catalog extra includes python-dotenv
    load_dotenv = None

from backend.catalog.cloud_catalog import (  # noqa: E402
    OFFICIAL_CATALOG_COUNT,
    build_official_catalog,
)

DATA_DIR = PROJECT_ROOT / "backend" / "catalog" / "data"
DEFAULT_CLOUD_CATALOG = DATA_DIR / "furniture_catalog_cloud_9350.json"
DEFAULT_STYLE_ENRICHMENT = DATA_DIR / "furniture_catalog_6styles_zh.json"
DEFAULT_MANIFEST = DATA_DIR / "manifests" / "glb_upload_all_result.csv"
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_postgresql_schema.sql")
READY_STATUSES = {
    "uploaded",
    "already_exists",
    "complete",
    "completed",
    "success",
    "skipped_existing",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import RoomPilot's official 9,350 CloudFront furniture records.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CLOUD_CATALOG)
    parser.add_argument("--style-enrichment", type=Path, default=DEFAULT_STYLE_ENRICHMENT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs without connecting to PostgreSQL.",
    )
    parser.add_argument(
        "--prune-extra",
        action="store_true",
        help="Remove database catalog rows outside the official 9,350 item IDs.",
    )
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_import_payload(
    catalog_path: Path,
    style_enrichment_path: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, int]]:
    manifest_rows = _load_csv(manifest_path)
    official, diagnostics = build_official_catalog(
        _load_json(catalog_path),
        _load_json(style_enrichment_path),
        manifest_rows,
    )
    if len(official["furniture"]) != OFFICIAL_CATALOG_COUNT:
        raise ValueError("Official catalog must contain exactly 9,350 items.")
    if any(
        str(row.get("upload_status") or "").strip().lower() not in READY_STATUSES
        or not str(row.get("delivery_url") or "").startswith("https://")
        for row in manifest_rows
    ):
        raise ValueError(
            "Every manifest row must be ready and have an HTTPS delivery_url."
        )
    return official, manifest_rows, diagnostics


def _search_text(item: dict[str, Any]) -> str:
    values = [
        item.get("furniture_id"),
        item.get("name_en"),
        item.get("name_zh"),
        item.get("category_label"),
        item.get("normalized_type"),
        item.get("color"),
        item.get("material"),
        item.get("primary_style"),
    ]
    values.extend(item.get("colors") or [])
    values.extend(item.get("materials") or [])
    return " ".join(str(value).strip() for value in values if str(value or "").strip())


def _catalog_rows(items: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    rows = []
    for item in items:
        size = item.get("size_cm") or {}
        placement = {
            key: item.get(key)
            for key in (
                "can_rotate",
                "must_against_wall",
                "usable_for_moodboard",
                "placement_hints",
                "clearance_zones",
                "layout_relations",
                "rule",
            )
            if item.get(key) is not None
        }
        rows.append(
            (
                item["furniture_id"],
                item.get("name_en") or "",
                item.get("name_zh") or "",
                item.get("category_label") or "",
                item.get("normalized_type") or "unknown",
                item.get("source") or "",
                item.get("source_dataset") or "",
                size.get("width"),
                size.get("depth"),
                size.get("height"),
                list(item.get("materials") or []),
                list(item.get("colors") or []),
                item.get("primary_style"),
                item.get("style_candidates") or [],
                placement,
                list(item.get("legacy_enrichment_ids") or []),
                _search_text(item),
                item,
            )
        )
    return rows


def _asset_rows(rows: list[dict[str, str]]) -> list[tuple[Any, ...]]:
    return [
        (
            row["item_id"],
            row.get("manifest_version"),
            row.get("object_key"),
            row.get("original_glb_path"),
            int(row["file_size_bytes"]) if row.get("file_size_bytes") else None,
            row.get("sha256"),
            row.get("validation_status"),
            row.get("upload_status"),
            row.get("s3_etag"),
            row.get("s3_uri"),
            row.get("s3_https_url"),
            row.get("delivery_url"),
            row.get("delivery_url_type"),
            row.get("uploaded_at") or None,
            row.get("s3_last_modified") or None,
            row,
        )
        for row in rows
    ]


def _connect():
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the catalog extra: uv sync --extra catalog") from exc
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "roompilot_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def import_to_postgres(
    official: dict[str, Any],
    manifest_rows: list[dict[str, str]],
    *,
    schema_path: Path,
    prune_extra: bool,
    catalog_filename: str,
    manifest_filename: str,
) -> tuple[int, int, int]:
    try:
        from psycopg2.extras import Json, execute_values
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install the catalog extra: uv sync --extra catalog") from exc

    items = list(official["furniture"])
    item_rows = _catalog_rows(items)
    asset_rows = _asset_rows(manifest_rows)
    db_item_rows = [
        row[:13] + (Json(row[13]), Json(row[14])) + row[15:17] + (Json(row[17]),)
        for row in item_rows
    ]
    db_asset_rows = [row[:15] + (Json(row[15]),) for row in asset_rows]
    official_ids = [item["furniture_id"] for item in items]
    schema_sql = schema_path.read_text(encoding="utf-8")
    batch_key = hashlib.sha256(
        ("\n".join(official_ids) + (manifest_rows[0].get("uploaded_at") or "")).encode(
            "utf-8"
        )
    ).hexdigest()

    catalog_sql = """
        INSERT INTO catalog_items (
            item_id, name_en, name_zh, category_zh, type_code,
            source, source_group, width_cm, depth_cm, height_cm,
            materials, colors, primary_style, style_candidates,
            placement_metadata, legacy_enrichment_ids, search_text, raw_data
        ) VALUES %s
        ON CONFLICT (item_id) DO UPDATE SET
            name_en = EXCLUDED.name_en, name_zh = EXCLUDED.name_zh,
            category_zh = EXCLUDED.category_zh, type_code = EXCLUDED.type_code,
            source = EXCLUDED.source, source_group = EXCLUDED.source_group,
            width_cm = EXCLUDED.width_cm, depth_cm = EXCLUDED.depth_cm,
            height_cm = EXCLUDED.height_cm, materials = EXCLUDED.materials,
            colors = EXCLUDED.colors, primary_style = EXCLUDED.primary_style,
            style_candidates = EXCLUDED.style_candidates,
            placement_metadata = EXCLUDED.placement_metadata,
            legacy_enrichment_ids = EXCLUDED.legacy_enrichment_ids,
            search_text = EXCLUDED.search_text, raw_data = EXCLUDED.raw_data,
            is_active = TRUE, updated_at = NOW()
    """
    asset_sql = """
        INSERT INTO glb_assets (
            item_id, manifest_version, object_key, original_glb_path,
            file_size_bytes, sha256, validation_status, upload_status,
            s3_etag, s3_uri, s3_https_url, delivery_url, delivery_url_type,
            uploaded_at, s3_last_modified, raw_upload_result
        ) VALUES %s
        ON CONFLICT (item_id) DO UPDATE SET
            manifest_version = EXCLUDED.manifest_version,
            object_key = EXCLUDED.object_key,
            original_glb_path = EXCLUDED.original_glb_path,
            file_size_bytes = EXCLUDED.file_size_bytes,
            sha256 = EXCLUDED.sha256,
            validation_status = EXCLUDED.validation_status,
            upload_status = EXCLUDED.upload_status,
            s3_etag = EXCLUDED.s3_etag, s3_uri = EXCLUDED.s3_uri,
            s3_https_url = EXCLUDED.s3_https_url,
            delivery_url = EXCLUDED.delivery_url,
            delivery_url_type = EXCLUDED.delivery_url_type,
            uploaded_at = EXCLUDED.uploaded_at,
            s3_last_modified = EXCLUDED.s3_last_modified,
            raw_upload_result = EXCLUDED.raw_upload_result,
            updated_at = NOW()
    """

    connection = _connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
                execute_values(cursor, catalog_sql, db_item_rows, page_size=500)
                execute_values(cursor, asset_sql, db_asset_rows, page_size=500)
                pruned = 0
                if prune_extra:
                    cursor.execute(
                        "DELETE FROM catalog_items WHERE NOT (item_id = ANY(%s))",
                        (official_ids,),
                    )
                    pruned = cursor.rowcount
                cursor.execute(
                    """
                    INSERT INTO catalog_import_batches (
                        batch_key, catalog_filename, manifest_filename,
                        catalog_rows, asset_rows, style_enriched_rows, pruned_rows
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (batch_key) DO UPDATE SET
                        catalog_rows = EXCLUDED.catalog_rows,
                        asset_rows = EXCLUDED.asset_rows,
                        style_enriched_rows = EXCLUDED.style_enriched_rows,
                        pruned_rows = EXCLUDED.pruned_rows,
                        imported_at = NOW()
                    """,
                    (
                        batch_key,
                        catalog_filename,
                        manifest_filename,
                        len(item_rows),
                        len(asset_rows),
                        official["summary"]["style_enriched"],
                        pruned,
                    ),
                )
                cursor.execute("SELECT COUNT(*) FROM official_furniture_with_glb")
                published = int(cursor.fetchone()[0])
        return len(item_rows), len(asset_rows), published
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    args = parse_args(argv)
    official, manifest_rows, diagnostics = load_import_payload(
        args.catalog,
        args.style_enrichment,
        args.manifest,
    )
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("dry-run complete; PostgreSQL was not modified.")
        return 0

    catalog_count, asset_count, published_count = import_to_postgres(
        official,
        manifest_rows,
        schema_path=args.schema,
        prune_extra=args.prune_extra,
        catalog_filename=args.catalog.name,
        manifest_filename=args.manifest.name,
    )
    if published_count != OFFICIAL_CATALOG_COUNT:
        raise RuntimeError(
            f"Published view count is {published_count}; expected "
            f"{OFFICIAL_CATALOG_COUNT}."
        )
    print(
        f"import complete: catalog={catalog_count:,}, assets={asset_count:,}, "
        f"published={published_count:,}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
