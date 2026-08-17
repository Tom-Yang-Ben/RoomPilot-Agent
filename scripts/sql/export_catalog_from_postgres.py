#!/usr/bin/env python3
"""Export the active PostgreSQL furniture catalog to an importable JSON file.

The default public export contains only active rows with verified licenses.
Private export is an explicit local backup mode and may contain rows that must
not be published. Generated files belong under ``.runtime/exports`` and are
ignored by Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__:
    from .import_public_catalog_to_postgres import (
        COLUMNS,
        connect_db,
        normalize_catalog,
    )
else:  # pragma: no cover - direct script execution
    from import_public_catalog_to_postgres import COLUMNS, connect_db, normalize_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / ".runtime" / "exports"
VISIBILITIES = ("public", "private")
GENERIC_RELATION = "roompilot.furniture_catalog"
NORMALIZED_RELATION = "roompilot.furniture_catalog_api_current"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export active RoomPilot furniture metadata from PostgreSQL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--visibility", choices=VISIBILITIES, default="public")
    parser.add_argument(
        "--output",
        type=Path,
        help="Destination JSON. Defaults to .runtime/exports for the visibility.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate rows without writing a JSON file.",
    )
    return parser.parse_args(argv)


def default_output_path(visibility: str) -> Path:
    if visibility not in VISIBILITIES:
        raise ValueError(f"unsupported visibility: {visibility}")
    return DEFAULT_EXPORT_DIR / f"furniture_catalog_{visibility}.json"


def catalog_query(visibility: str) -> str:
    if visibility not in VISIBILITIES:
        raise ValueError(f"unsupported visibility: {visibility}")
    predicates = ["is_active"]
    if visibility == "public":
        predicates.append("license_status = 'verified'")
    return (
        f"SELECT {', '.join(COLUMNS)} "
        f"FROM {GENERIC_RELATION} "
        f"WHERE {' AND '.join(predicates)} ORDER BY item_id"
    )


def normalized_catalog_query() -> str:
    """Map the operator's normalized catalog views to the public importer shape."""
    return f"""
        SELECT
            catalog.item_id,
            'furniture' AS kind,
            catalog.name_en,
            catalog.name_zh,
            catalog.category_code,
            catalog.category_name_zh,
            catalog.source_type,
            catalog.normalized_type,
            catalog.taxonomy_group,
            catalog.taxonomy_group_zh,
            catalog.taxonomy_type_zh,
            'developer_supplied' AS catalog_scope,
            catalog.role,
            catalog.width_cm::double precision,
            catalog.depth_cm::double precision,
            catalog.height_cm::double precision,
            catalog.primary_color,
            catalog.primary_material,
            COALESCE(catalog.style_codes, ARRAY[]::text[]) AS style_codes,
            COALESCE(catalog.style_confidences, ARRAY[]::double precision[])
                AS style_confidences,
            catalog.style_confidence::double precision,
            catalog.style_assignment_source,
            COALESCE(catalog.room_codes, ARRAY[]::text[]) AS room_codes,
            catalog.description,
            COALESCE(catalog.rag_text, ARRAY[]::text[]) AS rag_text,
            COALESCE(catalog.mood_tags, ARRAY[]::text[]) AS mood_tags,
            COALESCE(catalog.features, ARRAY[]::text[]) AS features,
            COALESCE(catalog.search_keywords, ARRAY[]::text[]) AS search_keywords,
            catalog.object_type_zh,
            catalog.visual_weight,
            catalog.height_zone,
            catalog.size_class,
            catalog.pattern,
            catalog.must_against_wall,
            catalog.can_rotate,
            catalog.usable_for_moodboard,
            catalog.glb_url,
            catalog.front_image_url,
            catalog.side_image_url,
            catalog.angle_45_image_url,
            catalog.price_twd,
            TRUE AS is_active,
            COALESCE(
                NULLIF(BTRIM(item.raw_data ->> 'source_license'), ''),
                CASE
                    WHEN item.raw_data ->> 'license_status' = 'permission_required'
                    THEN 'permission_required'
                END
            ) AS source_license,
            COALESCE(
                NULLIF(BTRIM(item.raw_data ->> 'license_status'), ''),
                'permission_required'
            ) AS license_status,
            COALESCE(
                NULLIF(BTRIM(item.raw_data ->> 'source_url'), ''),
                catalog.product_url
            ) AS source_url
        FROM {NORMALIZED_RELATION} AS catalog
        INNER JOIN roompilot.furniture_items AS item
            ON item.item_id = catalog.item_id
        WHERE catalog.kind = 'furniture'
        ORDER BY catalog.item_id
    """.strip()


def fetch_catalog_rows(
    connection: Any, visibility: str
) -> tuple[list[dict[str, Any]], str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                TO_REGCLASS(%s)::TEXT,
                TO_REGCLASS(%s)::TEXT
            """,
            (GENERIC_RELATION, NORMALIZED_RELATION),
        )
        generic_relation, normalized_relation = cursor.fetchone()
        if generic_relation:
            source_relation = GENERIC_RELATION
            query = catalog_query(visibility)
        elif normalized_relation:
            source_relation = NORMALIZED_RELATION
            cursor.execute(
                "SELECT SET_CONFIG('roompilot.catalog_visibility', %s, FALSE)",
                (visibility,),
            )
            query = normalized_catalog_query()
        else:
            raise RuntimeError("no supported RoomPilot furniture catalog relation found")
        cursor.execute(query)
        raw_rows = cursor.fetchall()
    return [dict(zip(COLUMNS, row, strict=True)) for row in raw_rows], source_relation


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _canonicalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = {column: _json_value(row[column]) for column in COLUMNS}
    raw_style_codes = list(item.get("style_codes") or [])
    raw_confidences = list(item.get("style_confidences") or [])
    primary_confidence = item.get("style_confidence")
    style_pairs = []
    seen_style_codes: set[str] = set()
    for index, code in enumerate(raw_style_codes):
        normalized_code = "" if code is None else str(code).strip()
        if not normalized_code or normalized_code in seen_style_codes:
            continue
        seen_style_codes.add(normalized_code)
        style_pairs.append((normalized_code, index))
    style_codes = [code for code, _ in style_pairs]
    item["style_codes"] = style_codes
    item["style_confidences"] = [
        (
            raw_confidences[source_index]
            if source_index < len(raw_confidences)
            and raw_confidences[source_index] is not None
            else primary_confidence
            if index == 0 and primary_confidence is not None
            else 1.0
        )
        for index, (_, source_index) in enumerate(style_pairs)
    ]
    return item


def build_payload(
    rows: Sequence[Mapping[str, Any]],
    visibility: str,
    *,
    source_relation: str = GENERIC_RELATION,
) -> dict[str, Any]:
    if visibility not in VISIBILITIES:
        raise ValueError(f"unsupported visibility: {visibility}")
    items = []
    for index, row in enumerate(rows, start=1):
        missing = [column for column in COLUMNS if column not in row]
        if missing:
            raise ValueError(f"row {index} is missing columns: {', '.join(missing)}")
        items.append(_canonicalize_row(row))
    return {
        "schema_version": "1.0",
        "catalog_name": f"RoomPilot PostgreSQL {visibility} export",
        "visibility": visibility,
        "source_relation": source_relation,
        "item_count": len(items),
        "items": items,
    }


def write_payload(payload: Mapping[str, Any], output_path: Path) -> str:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        temporary_path.write_text(serialized, encoding="utf-8")
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def export_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    visibility: str,
    output_path: Path,
    dry_run: bool,
    sha256: str | None,
) -> dict[str, Any]:
    license_status_counts = Counter(str(row["license_status"]) for row in rows)
    return {
        "visibility": visibility,
        "count": len(rows),
        "license_status_counts": dict(sorted(license_status_counts.items())),
        "output": None if dry_run else str(output_path.resolve()),
        "sha256": sha256,
        "dry_run": dry_run,
        "git_ignored_runtime_export": output_path.resolve().is_relative_to(
            DEFAULT_EXPORT_DIR.resolve()
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = args.output or default_output_path(args.visibility)
    connection = connect_db(args.env)
    try:
        connection.set_session(readonly=True, autocommit=True)
        rows, source_relation = fetch_catalog_rows(connection, args.visibility)
    finally:
        connection.close()
    if not rows:
        raise RuntimeError(f"no active {args.visibility} catalog rows found")

    payload = build_payload(
        rows,
        args.visibility,
        source_relation=source_relation,
    )
    normalize_catalog(
        payload["items"],
        {key: value for key, value in payload.items() if key != "items"},
    )
    sha256 = None if args.dry_run else write_payload(payload, output_path)
    print(
        json.dumps(
            export_summary(
                rows,
                visibility=args.visibility,
                output_path=output_path,
                dry_run=args.dry_run,
                sha256=sha256,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
