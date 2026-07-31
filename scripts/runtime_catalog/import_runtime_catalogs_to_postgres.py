#!/usr/bin/env python3
"""Validate and import RoomPilot Phase 4 runtime catalogs into PostgreSQL.

The importer stays beside its schema under ``scripts/sql`` so repository-root
and sibling-schema discovery remain deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DATA = PROJECT_ROOT / "backend" / "catalog" / "data"
DEFAULT_STYLE_CARDS = CATALOG_DATA / "taiwan_style_cards.json"
DEFAULT_DESIGN_STYLES = CATALOG_DATA / "furniture_catalog_6styles_zh.json"
DEFAULT_SURFACES = CATALOG_DATA / "surface_catalog.json"
DEFAULT_COSTS = CATALOG_DATA / "taiwan_renovation_price_seed.json"
DEFAULT_EXTERNAL_IMPORT = next(
    CATALOG_DATA.glob("*/external_furniture_import_index.json"),
    CATALOG_DATA / "external_furniture_import_index.json",
)
DEFAULT_UNMATCHED = (
    CATALOG_DATA
    / "quarantine"
    / "unmatched_cloud_furniture"
    / "unmatched_catalog_items.json"
)
DEFAULT_LEGACY = (
    CATALOG_DATA / "quarantine" / "sf3d_legacy" / "ikea_furniture_style_database.json"
)
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_runtime_catalog_schema.sql")
DEFAULT_REPORT = Path(__file__).with_name("runtime_catalog_import_validation.json")


@dataclass(frozen=True)
class SourcePayload:
    key: str
    path: Path
    sha256: str
    payload: dict[str, Any]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="驗證並匯入 Phase 4 色卡、材質、裝修單價與隔離資料。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--style-cards", type=Path, default=DEFAULT_STYLE_CARDS)
    parser.add_argument("--design-styles", type=Path, default=DEFAULT_DESIGN_STYLES)
    parser.add_argument("--surfaces", type=Path, default=DEFAULT_SURFACES)
    parser.add_argument("--costs", type=Path, default=DEFAULT_COSTS)
    parser.add_argument("--external-import", type=Path, default=DEFAULT_EXTERNAL_IMPORT)
    parser.add_argument("--unmatched", type=Path, default=DEFAULT_UNMATCHED)
    parser.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--validation-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-schema", action="store_true")
    return parser.parse_args(argv)


def _repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_json(payload: dict[str, Any]) -> str:
    return _sha256_bytes(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _load_source(key: str, path: Path) -> SourcePayload:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{key}: JSON 頂層必須是 object")
    return SourcePayload(key=key, path=path, sha256=_sha256_bytes(raw), payload=payload)


def _metadata_without(payload: dict[str, Any], *record_keys: str) -> dict[str, Any]:
    excluded = set(record_keys)
    return {key: value for key, value in payload.items() if key not in excluded}


def _dict_list(payload: dict[str, Any], key: str, errors: list[str]) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        errors.append(f"{key} 必須是 JSON object array")
        return []
    return value


def _unique(rows: list[dict[str, Any]], key: str, label: str, errors: list[str]) -> None:
    values = [str(row.get(key) or "").strip() for row in rows]
    if any(not value for value in values):
        errors.append(f"{label}: {key} 不可空白")
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"{label}: {key} 重複：{duplicates[:5]}")


def validate_sources(sources: dict[str, SourcePayload]) -> dict[str, Any]:
    errors: list[str] = []

    styles = _dict_list(sources["style_cards"].payload, "styles", errors)
    cards = [card for style in styles for card in (style.get("cards") or [])]
    if len(styles) != 6 or any(len(style.get("cards") or []) != 3 for style in styles):
        errors.append("style_cards 必須是 6 個風格群組、每組 3 張卡")
    if not all(isinstance(card, dict) for card in cards):
        errors.append("style_cards.cards 必須全為 JSON object")
        cards = [card for card in cards if isinstance(card, dict)]
    _unique(cards, "card_id", "style_cards", errors)

    design_styles = _dict_list(
        sources["design_style_profiles"].payload, "styles", errors
    )
    _unique(design_styles, "style_id", "design_style_profiles", errors)
    if len(design_styles) != 6:
        errors.append("design_style_profiles 必須是正式 UI 的 6 種風格")

    surfaces = _dict_list(sources["surface_materials"].payload, "surfaces", errors)
    _unique(surfaces, "surface_id", "surface_materials", errors)
    profiles = sources["surface_materials"].payload.get("style_surface_profiles")
    if not isinstance(profiles, dict):
        errors.append("style_surface_profiles 必須是 JSON object")
        profiles = {}

    rates = _dict_list(sources["renovation_costs"].payload, "rates", errors)
    cost_sources = _dict_list(sources["renovation_costs"].payload, "sources", errors)
    _unique(rates, "work_code", "renovation_cost_rates", errors)
    _unique(cost_sources, "id", "renovation_cost_sources", errors)
    source_ids = {str(item.get("id")) for item in cost_sources}
    for rate in rates:
        values = rate.get("range_twd") or {}
        try:
            low, base, high = (float(values[key]) for key in ("low", "base", "high"))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{rate.get('work_code')}: range_twd 無效")
            continue
        if not (0 <= low <= base <= high):
            errors.append(f"{rate.get('work_code')}: range_twd 必須 low <= base <= high")
        missing = set(map(str, rate.get("source_ids") or [])) - source_ids
        if missing:
            errors.append(f"{rate.get('work_code')}: 缺少來源 {sorted(missing)}")

    external = _dict_list(sources["external_import"].payload, "items", errors)
    unmatched = _dict_list(sources["unmatched_cloud"].payload, "items", errors)
    legacy = _dict_list(sources["sf3d_legacy"].payload, "furniture", errors)
    for label, rows in (
        ("external_import", external),
        ("unmatched_cloud", unmatched),
    ):
        _unique(rows, "furniture_id", label, errors)
    legacy_ids = [str(item.get("furniture_id") or "").strip() for item in legacy]
    if any(not value for value in legacy_ids):
        errors.append("sf3d_legacy: furniture_id 不可空白")
    legacy_duplicate_count = len(legacy_ids) - len(set(legacy_ids))

    declared_unmatched = sources["unmatched_cloud"].payload.get("count")
    if declared_unmatched != len(unmatched):
        errors.append(
            f"unmatched_cloud.count={declared_unmatched!r}，實際 items={len(unmatched)}"
        )

    counts = {
        "style_groups": len(styles),
        "style_cards": len(cards),
        "design_style_profiles": len(design_styles),
        "surface_materials": len(surfaces),
        "style_surface_profiles": len(profiles),
        "renovation_cost_rates": len(rates),
        "renovation_cost_sources": len(cost_sources),
        "external_import_quarantine": len(external),
        "unmatched_cloud_quarantine": len(unmatched),
        "sf3d_legacy_quarantine": len(legacy),
        "sf3d_legacy_duplicate_ids": legacy_duplicate_count,
        "quarantine_total": len(external) + len(unmatched) + len(legacy),
        "rag_documents": len(cards) + len(surfaces) + len(rates),
    }
    return {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "counts": counts,
        "sources": {
            key: {"path": _repo_path(source.path), "sha256": source.sha256}
            for key, source in sources.items()
        },
    }


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _db_config(env_path: Path) -> dict[str, Any]:
    values = _read_env(env_path)

    def setting(name: str, default: str = "") -> str:
        return os.getenv(name, values.get(name, default)).strip()

    return {
        "host": setting("DB_HOST", "localhost"),
        "port": int(setting("DB_PORT", "5432")),
        "dbname": setting("DB_NAME", "roompilot_db"),
        "user": setting("DB_USER", "postgres"),
        "password": setting("DB_PASSWORD"),
        "sslmode": setting("DB_SSLMODE", "disable"),
        "connect_timeout": int(setting("DB_CONNECT_TIMEOUT", "10")),
        "application_name": setting(
            "DB_APPLICATION_NAME", "roompilot_runtime_catalog_import"
        ),
    }


def _require_psycopg():
    try:
        import psycopg2
        from psycopg2.extras import Json, execute_values
    except ImportError as exc:
        raise RuntimeError(
            "找不到 psycopg2；請先安裝 catalog/server dependencies"
        ) from exc
    return psycopg2, Json, execute_values


def _join_text(*values: Any) -> str:
    result: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple)):
            result.extend(str(item) for item in value if str(item).strip())
        elif value is not None and str(value).strip():
            result.append(str(value))
    return " ".join(result)


def _upsert_import_metadata(cursor: Any, Json: Any, sources: dict[str, SourcePayload]) -> None:
    definitions = {
        "style_cards": (
            sources["style_cards"],
            ("styles",),
            "schema_version",
            "schema_version",
            sum(len(style.get("cards") or []) for style in sources["style_cards"].payload["styles"]),
        ),
        "design_style_profiles": (
            sources["design_style_profiles"],
            (
                "styles",
                "furniture",
                "summary",
                "style_distribution_by_type",
                "style_distribution_by_category",
                "surface_catalog",
            ),
            "schema_version",
            "version",
            len(sources["design_style_profiles"].payload["styles"]),
        ),
        "surface_materials": (
            sources["surface_materials"],
            ("surfaces", "style_surface_profiles"),
            "schema_version",
            "version",
            len(sources["surface_materials"].payload["surfaces"]),
        ),
        "renovation_costs": (
            sources["renovation_costs"],
            ("rates", "sources"),
            None,
            "catalog_version",
            len(sources["renovation_costs"].payload["rates"]),
        ),
        "external_import": (
            sources["external_import"],
            ("items",),
            "schema_version",
            "schema_version",
            len(sources["external_import"].payload["items"]),
        ),
        "unmatched_cloud": (
            sources["unmatched_cloud"],
            ("items",),
            "schema_version",
            "schema_version",
            len(sources["unmatched_cloud"].payload["items"]),
        ),
        "sf3d_legacy": (
            sources["sf3d_legacy"],
            ("furniture", "surface_catalog"),
            "version",
            "version",
            len(sources["sf3d_legacy"].payload["furniture"]),
        ),
    }
    for key, (source, omitted, schema_key, version_key, count) in definitions.items():
        payload = source.payload
        cursor.execute(
            """
            INSERT INTO roompilot.runtime_catalog_imports (
                catalog_key, schema_version, catalog_version, source_path,
                source_sha256, metadata, record_count, imported_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (catalog_key) DO UPDATE SET
                schema_version = EXCLUDED.schema_version,
                catalog_version = EXCLUDED.catalog_version,
                source_path = EXCLUDED.source_path,
                source_sha256 = EXCLUDED.source_sha256,
                metadata = EXCLUDED.metadata,
                record_count = EXCLUDED.record_count,
                imported_at = NOW()
            """,
            (
                key,
                str(payload.get(schema_key)) if schema_key and payload.get(schema_key) is not None else None,
                str(payload.get(version_key)) if version_key and payload.get(version_key) is not None else None,
                _repo_path(source.path),
                source.sha256,
                Json(_metadata_without(payload, *omitted)),
                count,
            ),
        )


def _import_style_cards(cursor: Any, Json: Any, execute_values: Any, source: SourcePayload, page_size: int) -> None:
    cursor.execute("UPDATE roompilot.style_cards SET is_active = FALSE, updated_at = NOW()")
    rows = []
    for style_order, style in enumerate(source.payload["styles"]):
        style_payload = {key: value for key, value in style.items() if key != "cards"}
        for card_order, card in enumerate(style["cards"]):
            rows.append(
                (
                    card["card_id"], style["style_id"], style_order, card_order,
                    style["style_name_zh"], style["scene_style_id"],
                    style.get("description_zh") or "", card["name_zh"], card["image_file"],
                    card.get("palette_hex") or [], Json(style_payload), Json(card),
                    _join_text(style["style_name_zh"], style.get("description_zh"), card["name_zh"], card.get("palette_hex")),
                    source.sha256,
                )
            )
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.style_cards (
            card_id, style_id, style_order, card_order, style_name_zh,
            scene_style_id, description_zh, name_zh, image_file, palette_hex,
            style_payload, card_payload, rag_text, source_sha256
        ) VALUES %s
        ON CONFLICT (card_id) DO UPDATE SET
            style_id = EXCLUDED.style_id, style_order = EXCLUDED.style_order,
            card_order = EXCLUDED.card_order, style_name_zh = EXCLUDED.style_name_zh,
            scene_style_id = EXCLUDED.scene_style_id,
            description_zh = EXCLUDED.description_zh, name_zh = EXCLUDED.name_zh,
            image_file = EXCLUDED.image_file, palette_hex = EXCLUDED.palette_hex,
            style_payload = EXCLUDED.style_payload, card_payload = EXCLUDED.card_payload,
            rag_text = EXCLUDED.rag_text, source_sha256 = EXCLUDED.source_sha256,
            is_active = TRUE, imported_at = NOW(), updated_at = NOW()
        """,
        rows,
        page_size=page_size,
    )


def _import_design_styles(
    cursor: Any,
    Json: Any,
    execute_values: Any,
    source: SourcePayload,
    page_size: int,
) -> None:
    cursor.execute(
        "UPDATE roompilot.design_style_profiles SET is_active = FALSE, updated_at = NOW()"
    )
    rows = [
        (style["style_id"], style_order, Json(style), source.sha256)
        for style_order, style in enumerate(source.payload["styles"])
    ]
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.design_style_profiles (
            style_id, style_order, payload, source_sha256
        ) VALUES %s
        ON CONFLICT (style_id) DO UPDATE SET
            style_order = EXCLUDED.style_order,
            payload = EXCLUDED.payload,
            source_sha256 = EXCLUDED.source_sha256,
            is_active = TRUE,
            imported_at = NOW(),
            updated_at = NOW()
        """,
        rows,
        page_size=page_size,
    )


def _import_surfaces(cursor: Any, Json: Any, execute_values: Any, source: SourcePayload, page_size: int) -> None:
    cursor.execute("UPDATE roompilot.surface_materials SET is_active = FALSE, updated_at = NOW()")
    rows = []
    for item in source.payload["surfaces"]:
        rows.append(
            (
                item["surface_id"], item["name_zh"], item.get("material_group"),
                item.get("category"), item.get("color_zh"), item.get("color_hex"),
                item.get("usage") or [], item.get("suitable_styles") or [],
                item.get("texture_url"), item.get("preview_url"), Json(item),
                _join_text(
                    item["surface_id"], item["name_zh"], item.get("material_group"),
                    item.get("category"), item.get("color_zh"), item.get("usage"),
                    item.get("suitable_styles"), item.get("style_notes_zh"),
                    item.get("source_license_status"), item.get("source_product_url"),
                ),
                source.sha256,
            )
        )
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.surface_materials (
            surface_id, name_zh, material_group, category, color_zh, color_hex,
            usage, suitable_styles, texture_url, preview_url, payload, rag_text,
            source_sha256
        ) VALUES %s
        ON CONFLICT (surface_id) DO UPDATE SET
            name_zh = EXCLUDED.name_zh, material_group = EXCLUDED.material_group,
            category = EXCLUDED.category, color_zh = EXCLUDED.color_zh,
            color_hex = EXCLUDED.color_hex, usage = EXCLUDED.usage,
            suitable_styles = EXCLUDED.suitable_styles,
            texture_url = EXCLUDED.texture_url, preview_url = EXCLUDED.preview_url,
            payload = EXCLUDED.payload, rag_text = EXCLUDED.rag_text,
            source_sha256 = EXCLUDED.source_sha256, is_active = TRUE,
            imported_at = NOW(), updated_at = NOW()
        """,
        rows,
        page_size=page_size,
    )

    cursor.execute("UPDATE roompilot.style_surface_profiles SET is_active = FALSE, updated_at = NOW()")
    profile_rows = [
        (style_id, Json(payload), source.sha256)
        for style_id, payload in source.payload["style_surface_profiles"].items()
    ]
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.style_surface_profiles (
            style_id, payload, source_sha256
        ) VALUES %s
        ON CONFLICT (style_id) DO UPDATE SET
            payload = EXCLUDED.payload, source_sha256 = EXCLUDED.source_sha256,
            is_active = TRUE, imported_at = NOW(), updated_at = NOW()
        """,
        profile_rows,
        page_size=page_size,
    )


def _import_costs(cursor: Any, Json: Any, execute_values: Any, source: SourcePayload, page_size: int) -> None:
    cursor.execute("UPDATE roompilot.renovation_cost_sources SET is_active = FALSE, updated_at = NOW()")
    source_rows = [
        (
            item["id"], item["publisher"], item.get("title"), item["url"],
            item["retrieved_on"], Json(item), source.sha256,
        )
        for item in source.payload["sources"]
    ]
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.renovation_cost_sources (
            source_id, publisher, title, url, retrieved_on, payload,
            source_sha256
        ) VALUES %s
        ON CONFLICT (source_id) DO UPDATE SET
            publisher = EXCLUDED.publisher, title = EXCLUDED.title, url = EXCLUDED.url,
            retrieved_on = EXCLUDED.retrieved_on, payload = EXCLUDED.payload,
            source_sha256 = EXCLUDED.source_sha256, is_active = TRUE,
            imported_at = NOW(), updated_at = NOW()
        """,
        source_rows,
        page_size=page_size,
    )

    cursor.execute("UPDATE roompilot.renovation_cost_rates SET is_active = FALSE, updated_at = NOW()")
    rate_rows = []
    for item in source.payload["rates"]:
        value_range = item["range_twd"]
        rate_rows.append(
            (
                item["work_code"], item["unit"], value_range["low"],
                value_range["base"], value_range["high"], item["source_ids"],
                item.get("valid_as_of"), Json(item),
                _join_text(
                    item["work_code"], item["unit"], item.get("inclusions"),
                    item.get("exclusions"), item.get("normalization_note"),
                    item.get("source_ids"),
                ),
                source.sha256,
            )
        )
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.renovation_cost_rates (
            work_code, unit, low_twd, base_twd, high_twd, source_ids,
            valid_as_of, payload, rag_text, source_sha256
        ) VALUES %s
        ON CONFLICT (work_code) DO UPDATE SET
            unit = EXCLUDED.unit, low_twd = EXCLUDED.low_twd,
            base_twd = EXCLUDED.base_twd, high_twd = EXCLUDED.high_twd,
            source_ids = EXCLUDED.source_ids, valid_as_of = EXCLUDED.valid_as_of,
            payload = EXCLUDED.payload, rag_text = EXCLUDED.rag_text,
            source_sha256 = EXCLUDED.source_sha256, is_active = TRUE,
            imported_at = NOW(), updated_at = NOW()
        """,
        rate_rows,
        page_size=page_size,
    )


def _quarantine_rows(source: SourcePayload, list_key: str, default_reason: str):
    seen: dict[str, int] = {}
    for item in source.payload[list_key]:
        furniture_id = str(item["furniture_id"])
        occurrence = seen.get(furniture_id, 0) + 1
        seen[furniture_id] = occurrence
        record_id = furniture_id if occurrence == 1 else f"{furniture_id}#{occurrence}"
        yield (
            source.key,
            record_id,
            str(item.get("quarantine_reason") or default_reason),
            item.get("catalog_scope"),
            item,
            _repo_path(source.path),
            source.sha256,
            _sha256_json(item),
        )


def _import_quarantine(cursor: Any, Json: Any, execute_values: Any, sources: dict[str, SourcePayload], page_size: int) -> None:
    definitions = (
        (sources["external_import"], "items", "external_import_unverified"),
        (sources["unmatched_cloud"], "items", "no_verified_cloudfront_match"),
        (sources["sf3d_legacy"], "furniture", "legacy_catalog_excluded"),
    )
    for source, _, _ in definitions:
        cursor.execute(
            """
            UPDATE roompilot.external_import_quarantine
            SET is_current = FALSE, updated_at = NOW()
            WHERE source_kind = %s
            """,
            (source.key,),
        )
    rows = []
    for source, list_key, reason in definitions:
        rows.extend(_quarantine_rows(source, list_key, reason))
    json_rows = [(*row[:4], Json(row[4]), *row[5:]) for row in rows]
    execute_values(
        cursor,
        """
        INSERT INTO roompilot.external_import_quarantine (
            source_kind, record_id, quarantine_reason, catalog_scope, raw_payload,
            source_path, source_sha256, record_sha256, is_current,
            eligible_for_api, eligible_for_rag
        ) VALUES %s
        ON CONFLICT (source_kind, record_id) DO UPDATE SET
            quarantine_reason = EXCLUDED.quarantine_reason,
            catalog_scope = EXCLUDED.catalog_scope,
            raw_payload = EXCLUDED.raw_payload,
            source_path = EXCLUDED.source_path,
            source_sha256 = EXCLUDED.source_sha256,
            review_status = CASE
                WHEN roompilot.external_import_quarantine.record_sha256 = EXCLUDED.record_sha256
                THEN roompilot.external_import_quarantine.review_status
                ELSE 'quarantined'
            END,
            eligible_for_api = FALSE,
            eligible_for_rag = FALSE,
            record_sha256 = EXCLUDED.record_sha256,
            is_current = TRUE,
            imported_at = NOW(),
            updated_at = NOW()
        """,
        [(*row, True, False, False) for row in json_rows],
        page_size=page_size,
    )


def import_to_postgres(args: argparse.Namespace, sources: dict[str, SourcePayload]) -> dict[str, int]:
    psycopg2, Json, execute_values = _require_psycopg()
    with psycopg2.connect(**_db_config(args.env)) as connection:
        with connection.cursor() as cursor:
            if not args.skip_schema:
                cursor.execute(args.schema_sql.read_text(encoding="utf-8"))
            _upsert_import_metadata(cursor, Json, sources)
            _import_style_cards(cursor, Json, execute_values, sources["style_cards"], args.page_size)
            _import_design_styles(
                cursor,
                Json,
                execute_values,
                sources["design_style_profiles"],
                args.page_size,
            )
            _import_surfaces(cursor, Json, execute_values, sources["surface_materials"], args.page_size)
            _import_costs(cursor, Json, execute_values, sources["renovation_costs"], args.page_size)
            _import_quarantine(cursor, Json, execute_values, sources, args.page_size)
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM roompilot.style_cards_current),
                    (SELECT COUNT(*) FROM roompilot.design_style_profiles_current),
                    (SELECT COUNT(*) FROM roompilot.surface_materials_current),
                    (SELECT COUNT(*) FROM roompilot.renovation_cost_catalog_current),
                    (SELECT COUNT(*) FROM roompilot.external_import_quarantine WHERE is_current),
                    (SELECT COUNT(*) FROM roompilot.runtime_catalog_rag_documents)
                """
            )
            values = cursor.fetchone()
    keys = (
        "style_cards",
        "design_style_profiles",
        "surface_materials",
        "renovation_cost_rates",
        "quarantine_total",
        "rag_documents",
    )
    return dict(zip(keys, map(int, values), strict=True))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        sources = {
            "style_cards": _load_source("style_cards", args.style_cards),
            "design_style_profiles": _load_source(
                "design_style_profiles", args.design_styles
            ),
            "surface_materials": _load_source("surface_materials", args.surfaces),
            "renovation_costs": _load_source("renovation_costs", args.costs),
            "external_import": _load_source("external_import", args.external_import),
            "unmatched_cloud": _load_source("unmatched_cloud", args.unmatched),
            "sf3d_legacy": _load_source("sf3d_legacy", args.legacy),
        }
        report = validate_sources(sources)
    except Exception as exc:
        report = {"status": "invalid", "errors": [str(exc)], "counts": {}, "sources": {}}

    args.validation_report.parent.mkdir(parents=True, exist_ok=True)
    args.validation_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}")
        return 1

    counts = report["counts"]
    print(
        "Runtime catalogs validated: "
        f"design styles={counts['design_style_profiles']}, "
        f"style cards={counts['style_cards']}, surfaces={counts['surface_materials']}, "
        f"cost rates={counts['renovation_cost_rates']}, "
        f"quarantine={counts['quarantine_total']}, RAG={counts['rag_documents']}"
    )
    if args.dry_run:
        print("Dry run only: PostgreSQL was not changed.")
        return 0

    imported = import_to_postgres(args, sources)
    expected = {
        "style_cards": counts["style_cards"],
        "design_style_profiles": counts["design_style_profiles"],
        "surface_materials": counts["surface_materials"],
        "renovation_cost_rates": counts["renovation_cost_rates"],
        "quarantine_total": counts["quarantine_total"],
        "rag_documents": counts["rag_documents"],
    }
    if imported != expected:
        raise RuntimeError(f"PostgreSQL count mismatch: expected={expected}, actual={imported}")
    print(f"PostgreSQL import complete: {imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
