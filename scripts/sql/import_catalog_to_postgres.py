#!/usr/bin/env python3
"""將 RoomPilot catalog、GLB manifest、GLB upload result 整合後匯入 PostgreSQL。

新版資料格式：
1. all_furniture_appliance_catalog.json
2. glb_upload_manifest.csv
3. glb_upload_all_result.csv
4. glb_upload_manifest_report.json

每次驗證會更新：
- postgres_import_validation.json
- roompilot_type_category_mapping.csv
- roompilot_high_priority_data_review.csv

正式資料表：
- item_roles
- item_types
- catalog_items
- glb_assets
- import_batches

先執行 Dry Run（輸入路徑已有專案預設值）：
python scripts/sql/import_catalog_to_postgres.py --strict --dry-run

首次建立資料庫並正式匯入：
python scripts/sql/import_catalog_to_postgres.py --strict --create-database --create-schema
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = PROJECT_ROOT / "JSON" / "furniture" / "all_furniture_appliance_catalog.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "JSON" / "manifests" / "glb_upload_manifest.csv"
DEFAULT_UPLOAD_RESULT = PROJECT_ROOT / "JSON" / "manifests" / "glb_upload_all_result.csv"
DEFAULT_MANIFEST_REPORT = PROJECT_ROOT / "JSON" / "manifests" / "glb_upload_manifest_report.json"
DEFAULT_TYPE_MAPPING_REPORT = Path(__file__).with_name("roompilot_type_category_mapping.csv")
DEFAULT_REVIEW_REPORT = Path(__file__).with_name("roompilot_high_priority_data_review.csv")
EXPECTED_POST_IMPORT_COUNTS = {
    "catalog_items": 10_550,
    "glb_assets": 10_550,
    "item_types": 87,
    "item_roles": 11,
    "inactive_items": 1,
    "space_planning_items": 10_542,
}

HIGH_PRIORITY_FLAGS = {
    "dimensions_all_below_5cm_review",
    "missing_depth_cm",
    "missing_height_cm",
    "missing_width_cm",
    "possible_exact_product_duplicate",
    "suspected_brand_to_material_error",
    "suspected_type_misclassification",
}


REQUIRED_CATALOG_FIELDS = {
    "id", "name_en", "name_zh", "source_category", "source_type_code",
    "type_code", "source_role_zh", "role_code", "canonical_category_zh",
    "materials", "colors", "data_quality_flags", "object_key", "glb_url",
    "source", "catalog", "kind",
}
REQUIRED_MANIFEST_FIELDS = {
    "item_id", "object_key", "name_en", "source", "catalog", "kind",
    "validation_status", "upload_status",
}
REQUIRED_UPLOAD_FIELDS = REQUIRED_MANIFEST_FIELDS | {
    "delivery_url", "delivery_url_type", "s3_uri", "s3_etag", "uploaded_at",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="整合 RoomPilot catalog、manifest 與上傳結果後匯入 PostgreSQL。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="主 catalog JSON")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="GLB manifest CSV")
    parser.add_argument(
        "--upload-result", type=Path, default=DEFAULT_UPLOAD_RESULT,
        help="GLB 上傳結果 CSV",
    )
    parser.add_argument(
        "--manifest-report", type=Path, default=DEFAULT_MANIFEST_REPORT,
        help="GLB manifest 摘要 JSON",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="PostgreSQL 連線環境變數檔",
    )
    parser.add_argument(
        "--schema-sql",
        type=Path,
        default=Path(__file__).with_name("roompilot_catalog_10550_schema.sql"),
        help="PostgreSQL schema 與 migration SQL",
    )
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=Path(__file__).with_name("postgres_import_validation.json"),
        help="整合驗證報告 JSON",
    )
    parser.add_argument(
        "--type-mapping-report",
        type=Path,
        default=DEFAULT_TYPE_MAPPING_REPORT,
        help="來源 type 到標準 type 的稽核 CSV",
    )
    parser.add_argument(
        "--review-report",
        type=Path,
        default=DEFAULT_REVIEW_REPORT,
        help="高優先級資料品質複查 CSV",
    )
    parser.add_argument("--page-size", type=int, default=500, help="每批 UPSERT 筆數")
    parser.add_argument(
        "--create-database",
        action="store_true",
        help="若 DB_NAME 不存在，先連線 DB_ADMIN_DB 建立 UTF-8 資料庫",
    )
    parser.add_argument("--create-schema", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="只要上傳狀態不是 uploaded，或 CloudFront URL 不一致，就停止。",
    )
    return parser.parse_args(argv)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def parse_bool(value: Any) -> bool | None:
    text = clean_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"無法解析布林值：{value!r}")


def parse_int(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    return int(float(text))


def parse_float(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    return float(text)


def string_list(value: Any, field: str, item_id: str) -> list[str]:
    """讀取 catalog 已正規化的字串陣列，不再拆解舊版字串欄位。"""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{item_id}: {field} 必須是陣列。")

    result: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = clean_text(raw)
        if text is None:
            continue
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 catalog：{path}")

    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)

    if isinstance(payload, list):
        items = payload
        metadata: dict[str, Any] = {}
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
        metadata = {key: value for key, value in payload.items() if key != "items"}
    else:
        raise ValueError("catalog 必須是 list，或是含有 items 陣列的 dict。")

    if not all(isinstance(item, dict) for item in items):
        raise ValueError("catalog.items 的每一筆都必須是 JSON object。")

    return items, metadata


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"找不到 CSV：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"CSV 沒有欄位名稱：{path}")
        return [dict(row) for row in reader]


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"找不到 manifest report：{path}")
    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("manifest report 最外層必須是 JSON object。")
    return payload


def validate_required_fields(
    rows: list[dict[str, Any]], required: set[str], label: str
) -> None:
    if not rows:
        raise ValueError(f"{label} 沒有任何資料。")
    missing = sorted(required - set(rows[0].keys()))
    if missing:
        raise ValueError(f"{label} 缺少欄位：{', '.join(missing)}")


def index_unique(
    rows: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []

    for row in rows:
        value = clean_text(row.get(key))
        if value is None:
            raise ValueError(f"{label} 有空的 {key}。")
        if value in result:
            duplicates.append(value)
        result[value] = row

    if duplicates:
        examples = ", ".join(duplicates[:10])
        raise ValueError(f"{label} 的 {key} 重複，共 {len(duplicates)} 筆，例如：{examples}")

    return result


def build_search_text(item: dict[str, Any], canonical_type_zh: str) -> str:
    parts: Iterable[Any] = (
        item.get("name_en"),
        item.get("name_zh"),
        item.get("display_name_zh"),
        canonical_type_zh,
        item.get("source_category"),
        item.get("source_type_code"),
        item.get("type_code"),
        item.get("source_role_zh"),
        item.get("role_code"),
        *list(item.get("colors") or []),
        *list(item.get("materials") or []),
        item.get("source"),
    )
    return " ".join(text for value in parts if (text := clean_text(value)))


def compare_field(
    item_id: str,
    left: dict[str, Any],
    right: dict[str, Any],
    field: str,
    left_label: str,
    right_label: str,
    errors: list[str],
) -> None:
    left_value = clean_text(left.get(field))
    right_value = clean_text(right.get(field))
    if left_value != right_value:
        errors.append(
            f"{item_id}: {left_label}.{field}={left_value!r} != "
            f"{right_label}.{field}={right_value!r}"
        )


def validate_and_prepare(
    items: list[dict[str, Any]],
    catalog_metadata: dict[str, Any],
    manifest_rows: list[dict[str, Any]],
    upload_rows: list[dict[str, Any]],
    strict: bool,
) -> tuple[
    list[tuple[Any, ...]],
    list[tuple[Any, ...]],
    list[tuple[Any, ...]],
    list[tuple[Any, ...]],
    dict[str, Any],
]:
    validate_required_fields(items, REQUIRED_CATALOG_FIELDS, "catalog")
    validate_required_fields(manifest_rows, REQUIRED_MANIFEST_FIELDS, "manifest")
    validate_required_fields(upload_rows, REQUIRED_UPLOAD_FIELDS, "upload result")

    metadata_roles = catalog_metadata.get("item_roles")
    metadata_types = catalog_metadata.get("item_types")
    if not isinstance(metadata_roles, list) or not all(
        isinstance(row, dict) for row in metadata_roles
    ):
        raise ValueError("catalog.item_roles 必須是 object 陣列。")
    if not isinstance(metadata_types, list) or not all(
        isinstance(row, dict) for row in metadata_types
    ):
        raise ValueError("catalog.item_types 必須是 object 陣列。")

    validate_required_fields(
        metadata_roles,
        {"role_code", "name_zh", "name_en", "item_count", "type_count"},
        "catalog.item_roles",
    )
    validate_required_fields(
        metadata_types,
        {
            "type_code", "role_code", "canonical_name_zh", "canonical_name_en",
            "source_type_codes", "source_category_variants", "sources", "kinds",
            "item_count",
        },
        "catalog.item_types",
    )

    catalog_by_id = index_unique(items, "id", "catalog")
    manifest_by_id = index_unique(manifest_rows, "item_id", "manifest")
    upload_by_id = index_unique(upload_rows, "item_id", "upload result")
    role_by_code = index_unique(metadata_roles, "role_code", "catalog.item_roles")
    type_by_code = index_unique(metadata_types, "type_code", "catalog.item_types")

    catalog_ids = set(catalog_by_id)
    manifest_ids = set(manifest_by_id)
    upload_ids = set(upload_by_id)

    errors: list[str] = []
    warnings: list[str] = []

    role_rows: list[tuple[Any, ...]] = []
    for index, role in enumerate(metadata_roles, start=1):
        role_code = clean_text(role.get("role_code"))
        role_rows.append(
            (
                role_code,
                clean_text(role.get("name_zh")),
                clean_text(role.get("name_en")),
                parse_int(role.get("sort_order")) or index * 10,
                parse_int(role.get("item_count")) or 0,
                parse_int(role.get("type_count")) or 0,
            )
        )

    type_rows: list[tuple[Any, ...]] = []
    for item_type in metadata_types:
        type_code = clean_text(item_type.get("type_code")) or ""
        variants = item_type.get("source_category_variants")
        if not isinstance(variants, list) or not all(
            isinstance(variant, dict) for variant in variants
        ):
            errors.append(f"item_types.{type_code}.source_category_variants 必須是 object 陣列。")
            variants = []
        source_categories = [
            value
            for variant in variants
            if (value := clean_text(variant.get("value"))) is not None
        ]
        type_rows.append(
            (
                type_code,
                clean_text(item_type.get("role_code")),
                clean_text(item_type.get("canonical_name_zh")),
                clean_text(item_type.get("canonical_name_en")),
                source_categories,
                string_list(item_type.get("source_type_codes"), "source_type_codes", type_code),
                variants,
                string_list(item_type.get("sources"), "sources", type_code),
                string_list(item_type.get("kinds"), "kinds", type_code),
                parse_int(item_type.get("item_count")) or 0,
            )
        )

    for label, missing_ids in (
        ("catalog 中有、manifest 沒有", catalog_ids - manifest_ids),
        ("manifest 中有、catalog 沒有", manifest_ids - catalog_ids),
        ("catalog 中有、upload result 沒有", catalog_ids - upload_ids),
        ("upload result 中有、catalog 沒有", upload_ids - catalog_ids),
    ):
        if missing_ids:
            errors.append(f"{label}：{len(missing_ids)} 筆，例如 {sorted(missing_ids)[:5]}")

    type_categories: dict[str, set[str]] = defaultdict(set)
    type_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    role_types: dict[str, set[str]] = defaultdict(set)
    quality_flag_counts: Counter[str] = Counter()
    upload_status_counts: Counter[str] = Counter()

    item_rows: list[tuple[Any, ...]] = []
    asset_rows: list[tuple[Any, ...]] = []

    for item_id in sorted(catalog_ids & manifest_ids & upload_ids):
        item = catalog_by_id[item_id]
        manifest = manifest_by_id[item_id]
        upload = upload_by_id[item_id]

        for field in ("object_key", "name_en", "source", "catalog", "kind"):
            compare_field(item_id, item, manifest, field, "catalog", "manifest", errors)
            compare_field(item_id, item, upload, field, "catalog", "upload", errors)

        source_type_code = clean_text(item.get("source_type_code"))
        for row, label in ((manifest, "manifest"), (upload, "upload")):
            if source_type_code != clean_text(row.get("type")):
                errors.append(
                    f"{item_id}: catalog.source_type_code={source_type_code!r} != "
                    f"{label}.type={clean_text(row.get('type'))!r}"
                )

        catalog_url = clean_text(item.get("glb_url"))
        delivery_url = clean_text(upload.get("delivery_url"))
        if catalog_url != delivery_url:
            message = (
                f"{item_id}: catalog.glb_url={catalog_url!r} != "
                f"upload.delivery_url={delivery_url!r}"
            )
            (errors if strict else warnings).append(message)

        upload_status = clean_text(upload.get("upload_status")) or "unknown"
        upload_status_counts[upload_status] += 1
        if upload_status != "uploaded":
            message = f"{item_id}: upload_status={upload_status!r}"
            (errors if strict else warnings).append(message)

        if clean_text(upload.get("upload_error")):
            message = f"{item_id}: upload_error={upload.get('upload_error')!r}"
            (errors if strict else warnings).append(message)

        type_code = clean_text(item.get("type_code"))
        role_code = clean_text(item.get("role_code"))
        if type_code is None or role_code is None:
            errors.append(f"{item_id}: type_code 或 role_code 為空。")
            continue

        item_type = type_by_code.get(type_code)
        if item_type is None:
            errors.append(f"{item_id}: item_types 沒有 type_code={type_code!r}。")
            continue
        if role_code not in role_by_code:
            errors.append(f"{item_id}: item_roles 沒有 role_code={role_code!r}。")
            continue
        expected_role_code = clean_text(item_type.get("role_code"))
        if role_code != expected_role_code:
            errors.append(
                f"{item_id}: type_code={type_code!r} 應屬於 {expected_role_code!r}，"
                f"不是 {role_code!r}。"
            )
            continue

        canonical_type_zh = clean_text(item_type.get("canonical_name_zh")) or type_code
        item_canonical_zh = clean_text(item.get("canonical_category_zh"))
        if item_canonical_zh != canonical_type_zh:
            errors.append(
                f"{item_id}: canonical_category_zh={item_canonical_zh!r} != "
                f"item_types.canonical_name_zh={canonical_type_zh!r}"
            )

        source_category = clean_text(item.get("source_category"))
        type_categories[type_code].add(source_category or "")
        type_counts[type_code] += 1
        role_counts[role_code] += 1
        role_types[role_code].add(type_code)

        flags = string_list(item.get("data_quality_flags"), "data_quality_flags", item_id)
        materials = string_list(item.get("materials"), "materials", item_id)
        colors = string_list(item.get("colors"), "colors", item_id)
        quality_flag_counts.update(flags)

        dimension_review_status = clean_text(item.get("dimension_review_status"))
        if dimension_review_status not in {None, "needs_review", "reviewed", "accepted"}:
            errors.append(
                f"{item_id}: dimension_review_status={dimension_review_status!r} 不合法。"
            )

        is_ikea = parse_bool(item.get("is_ikea"))
        is_primary_variant = parse_bool(item.get("is_primary_variant"))
        is_active = parse_bool(item.get("is_active"))

        item_rows.append(
            (
                item_id,
                clean_text(item.get("name_en")),
                clean_text(item.get("name_zh")),
                clean_text(item.get("display_name_zh")),
                type_code,
                role_code,
                source_type_code,
                clean_text(item.get("source_role_zh")),
                source_category,
                item_canonical_zh,
                clean_text(item.get("kind")),
                clean_text(item.get("source")),
                clean_text(item.get("source_group")),
                clean_text(item.get("catalog")),
                clean_text(item.get("source_dataset")),
                False if is_ikea is None else is_ikea,
                parse_float(item.get("width_cm")),
                parse_float(item.get("depth_cm")),
                parse_float(item.get("height_cm")),
                dimension_review_status,
                materials,
                colors,
                build_search_text(item, canonical_type_zh),
                flags,
                clean_text(item.get("duplicate_group_id")),
                True if is_primary_variant is None else is_primary_variant,
                True if is_active is None else is_active,
                item,
            )
        )

        asset_rows.append(
            (
                item_id,
                clean_text(upload.get("manifest_version"))
                or clean_text(manifest.get("manifest_version")),
                clean_text(manifest.get("original_glb_path")),
                parse_bool(manifest.get("local_file_exists")),
                parse_int(manifest.get("file_size_bytes")),
                clean_text(manifest.get("sha256")),
                clean_text(manifest.get("upload_filename")),
                clean_text(upload.get("object_key")),
                clean_text(upload.get("content_type")) or "model/gltf-binary",
                clean_text(upload.get("validation_status")),
                clean_text(upload.get("validation_message")),
                upload_status,
                clean_text(upload.get("upload_error")),
                clean_text(upload.get("s3_etag")),
                clean_text(upload.get("s3_uri")),
                clean_text(upload.get("s3_https_url")),
                delivery_url,
                clean_text(upload.get("delivery_url_type")),
                clean_text(upload.get("temporary_presigned_url")),
                clean_text(upload.get("presigned_expires_at")),
                clean_text(upload.get("s3_version_id")),
                clean_text(upload.get("uploaded_at")),
                clean_text(upload.get("s3_last_modified")),
                manifest,
                upload,
            )
        )

    for type_code, item_type in type_by_code.items():
        declared = parse_int(item_type.get("item_count")) or 0
        if type_counts[type_code] != declared:
            errors.append(
                f"item_types.{type_code}.item_count={declared}，"
                f"實際為 {type_counts[type_code]}。"
            )
    for role_code, role in role_by_code.items():
        declared_items = parse_int(role.get("item_count")) or 0
        declared_types = parse_int(role.get("type_count")) or 0
        if role_counts[role_code] != declared_items:
            errors.append(
                f"item_roles.{role_code}.item_count={declared_items}，"
                f"實際為 {role_counts[role_code]}。"
            )
        if len(role_types[role_code]) != declared_types:
            errors.append(
                f"item_roles.{role_code}.type_count={declared_types}，"
                f"實際為 {len(role_types[role_code])}。"
            )

    if errors:
        preview = "\n".join(f"- {message}" for message in errors[:30])
        more = "" if len(errors) <= 30 else f"\n...另有 {len(errors) - 30} 筆錯誤"
        raise ValueError(f"資料整合驗證失敗，共 {len(errors)} 筆：\n{preview}{more}")

    report = {
        "catalog_rows": len(items),
        "manifest_rows": len(manifest_rows),
        "upload_result_rows": len(upload_rows),
        "prepared_item_rows": len(item_rows),
        "prepared_asset_rows": len(asset_rows),
        "type_count": len(type_rows),
        "role_count": len(role_rows),
        "upload_status_counts": dict(upload_status_counts),
        "quality_flag_counts": dict(quality_flag_counts),
        "warning_count": len(warnings),
        "warning_examples": warnings[:50],
        "types_with_multiple_source_categories": {
            type_code: sorted(categories)
            for type_code, categories in type_categories.items()
            if len(categories) > 1
        },
    }
    return role_rows, type_rows, item_rows, asset_rows, report


def write_quality_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def write_type_mapping_report(
    path: Path,
    items: list[dict[str, Any]],
    catalog_metadata: dict[str, Any],
) -> None:
    """由目前 catalog 產生來源 type → 標準 type 的可稽核對照。"""
    roles = {
        clean_text(row.get("role_code")): clean_text(row.get("name_zh"))
        for row in catalog_metadata["item_roles"]
    }
    types = {
        clean_text(row.get("type_code")): row
        for row in catalog_metadata["item_types"]
    }

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    targets_by_source: dict[str, set[str]] = defaultdict(set)
    for item in items:
        source_type = clean_text(item.get("source_type_code")) or ""
        type_code = clean_text(item.get("type_code")) or ""
        role_code = clean_text(item.get("role_code")) or ""
        grouped[(source_type, type_code, role_code)].append(item)
        targets_by_source[source_type].add(type_code)

    fieldnames = [
        "current_type_code",
        "recommended_type_code",
        "item_count",
        "role_code",
        "role_zh",
        "canonical_category_zh",
        "current_category_variant_count",
        "current_category_examples",
        "kinds",
        "sources",
        "migration_note",
    ]
    rows: list[dict[str, Any]] = []
    for (source_type, type_code, role_code), members in sorted(grouped.items()):
        category_counts = Counter(
            category
            for item in members
            if (category := clean_text(item.get("source_category"))) is not None
        )
        category_examples = " | ".join(
            f"{category} ({count})"
            for category, count in sorted(
                category_counts.items(), key=lambda pair: (-pair[1], pair[0])
            )[:8]
        )
        if len(targets_by_source[source_type]) > 1:
            migration_note = "同一 source type 有多個標準 type；需依 item 內容判斷"
        elif source_type != type_code:
            migration_note = "標準 type alias；保留 source_type_code 追溯"
        else:
            migration_note = ""

        type_metadata = types[type_code]
        rows.append(
            {
                "current_type_code": source_type,
                "recommended_type_code": type_code,
                "item_count": len(members),
                "role_code": role_code,
                "role_zh": roles[role_code],
                "canonical_category_zh": clean_text(
                    type_metadata.get("canonical_name_zh")
                ),
                "current_category_variant_count": len(category_counts),
                "current_category_examples": category_examples,
                "kinds": ", ".join(
                    sorted(
                        {
                            value
                            for item in members
                            if (value := clean_text(item.get("kind"))) is not None
                        }
                    )
                ),
                "sources": ", ".join(
                    sorted(
                        {
                            value
                            for item in members
                            if (value := clean_text(item.get("source"))) is not None
                        }
                    )
                ),
                "migration_note": migration_note,
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_high_priority_review_report(
    path: Path,
    items: list[dict[str, Any]],
) -> None:
    """輸出目前仍需人工追蹤的高優先級資料，並保留來源與標準欄位。"""
    fieldnames = [
        "item_id",
        "name_en",
        "name_zh",
        "source",
        "catalog",
        "kind",
        "role",
        "current_category",
        "type_code",
        "canonical_category_zh",
        "material",
        "color",
        "width_cm",
        "depth_cm",
        "height_cm",
        "issues",
        "object_key",
        "glb_url",
        "source_type_code",
        "source_role_zh",
        "role_code",
        "materials",
        "colors",
        "dimension_review_status",
        "is_active",
    ]
    rows: list[dict[str, Any]] = []
    for item in items:
        flags = string_list(
            item.get("data_quality_flags"), "data_quality_flags", str(item.get("id"))
        )
        issues = sorted(HIGH_PRIORITY_FLAGS.intersection(flags))
        if not issues:
            continue
        rows.append(
            {
                "item_id": item.get("id"),
                "name_en": item.get("name_en"),
                "name_zh": item.get("name_zh"),
                "source": item.get("source"),
                "catalog": item.get("catalog"),
                "kind": item.get("kind"),
                "role": item.get("role"),
                "current_category": item.get("source_category"),
                "type_code": item.get("type_code"),
                "canonical_category_zh": item.get("canonical_category_zh"),
                "material": item.get("material"),
                "color": item.get("color"),
                "width_cm": item.get("width_cm"),
                "depth_cm": item.get("depth_cm"),
                "height_cm": item.get("height_cm"),
                "issues": "|".join(issues),
                "object_key": item.get("object_key"),
                "glb_url": item.get("glb_url"),
                "source_type_code": item.get("source_type_code"),
                "source_role_zh": item.get("source_role_zh"),
                "role_code": item.get("role_code"),
                "materials": json.dumps(
                    item.get("materials") or [], ensure_ascii=False, separators=(",", ":")
                ),
                "colors": json.dumps(
                    item.get("colors") or [], ensure_ascii=False, separators=(",", ":")
                ),
                "dimension_review_status": item.get("dimension_review_status"),
                "is_active": str(item.get("is_active", True)).lower(),
            }
        )

    rows.sort(key=lambda row: str(row["item_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_db_config(env_path: Path) -> dict[str, Any]:
    """從專案外部的 .env 讀取並驗證 PostgreSQL 連線設定。"""
    if not env_path.exists():
        raise FileNotFoundError(
            f"找不到資料庫設定檔：{env_path}。"
            "請複製專案根目錄的 .env.example 為 .env，再填入連線資料。"
        )

    load_dotenv(dotenv_path=env_path, override=False)

    required_keys = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing_keys = [
        key
        for key in required_keys
        if key not in os.environ
        or (key != "DB_PASSWORD" and clean_text(os.environ.get(key)) is None)
    ]
    if missing_keys:
        raise ValueError(f"{env_path} 缺少設定：{', '.join(missing_keys)}")

    connect_timeout = parse_int(os.getenv("DB_CONNECT_TIMEOUT")) or 10
    if connect_timeout <= 0:
        raise ValueError("DB_CONNECT_TIMEOUT 必須大於 0。")

    config: dict[str, Any] = {
        "host": os.environ["DB_HOST"],
        "port": os.environ["DB_PORT"],
        "dbname": os.environ["DB_NAME"],
        "admin_dbname": clean_text(os.getenv("DB_ADMIN_DB")) or "postgres",
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "connect_timeout": connect_timeout,
        "application_name": clean_text(os.getenv("DB_APPLICATION_NAME"))
        or "roompilot_catalog_import",
    }
    sslmode = clean_text(os.getenv("DB_SSLMODE"))
    if sslmode:
        config["sslmode"] = sslmode

    return config


def connection_kwargs(config: dict[str, Any], dbname: str) -> dict[str, Any]:
    """將共用設定轉成 psycopg2.connect 可接受的參數。"""
    keys = (
        "host", "port", "user", "password", "connect_timeout",
        "application_name", "sslmode",
    )
    return {"dbname": dbname, **{key: config[key] for key in keys if key in config}}


def connect_db(env_path: Path):
    """連線目標 DB；Dry Run 不會呼叫此函式。"""
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "找不到 psycopg2。請先執行：pip install psycopg2-binary python-dotenv"
        ) from exc

    config = load_db_config(env_path)
    return psycopg2.connect(**connection_kwargs(config, config["dbname"]))


def ensure_database_exists(env_path: Path) -> bool:
    """連線維護資料庫，必要時建立 DB_NAME；回傳是否本次新建。"""
    try:
        import psycopg2
        from psycopg2 import sql
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "找不到 psycopg2。請先執行：pip install psycopg2-binary python-dotenv"
        ) from exc

    config = load_db_config(env_path)
    target_db = config["dbname"]
    admin_db = config["admin_dbname"]
    conn = psycopg2.connect(**connection_kwargs(config, admin_db))
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
            if cur.fetchone() is not None:
                return False
            cur.execute(
                sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0;").format(
                    sql.Identifier(target_db)
                )
            )
            return True
    finally:
        conn.close()


def execute_schema(conn, schema_sql_path: Path) -> None:
    if not schema_sql_path.exists():
        raise FileNotFoundError(f"找不到 schema SQL：{schema_sql_path}")
    sql = schema_sql_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def verify_post_import_counts(conn) -> dict[str, int]:
    queries = {
        "catalog_items": "SELECT COUNT(*) FROM catalog_items;",
        "glb_assets": "SELECT COUNT(*) FROM glb_assets;",
        "item_types": "SELECT COUNT(*) FROM item_types;",
        "item_roles": "SELECT COUNT(*) FROM item_roles;",
        "inactive_items": "SELECT COUNT(*) FROM catalog_items WHERE NOT is_active;",
        "space_planning_items": (
            "SELECT COUNT(*) FROM catalog_items_for_space_planning;"
        ),
    }
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for key, query in queries.items():
            cur.execute(query)
            counts[key] = int(cur.fetchone()[0])

    mismatches = {
        key: {"expected": expected, "actual": counts.get(key)}
        for key, expected in EXPECTED_POST_IMPORT_COUNTS.items()
        if counts.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(
            "PostgreSQL import counts did not match kai baseline: "
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )
    return counts


def upsert_to_postgres(
    conn,
    role_rows: list[tuple[Any, ...]],
    type_rows: list[tuple[Any, ...]],
    item_rows: list[tuple[Any, ...]],
    asset_rows: list[tuple[Any, ...]],
    report: dict[str, Any],
    args: argparse.Namespace,
    manifest_report: dict[str, Any] | None,
) -> dict[str, int]:
    try:
        from psycopg2.extras import Json, execute_values
    except ModuleNotFoundError as exc:
        raise RuntimeError("找不到 psycopg2-binary。") from exc

    role_sql = """
        INSERT INTO item_roles (
            role_code, name_zh, name_en, sort_order, item_count, type_count
        ) VALUES %s
        ON CONFLICT (role_code) DO UPDATE SET
            name_zh = EXCLUDED.name_zh,
            name_en = EXCLUDED.name_en,
            sort_order = EXCLUDED.sort_order,
            item_count = EXCLUDED.item_count,
            type_count = EXCLUDED.type_count,
            updated_at = NOW();
    """

    type_sql = """
        INSERT INTO item_types (
            type_code, role_code, canonical_name_zh, canonical_name_en,
            source_categories, source_type_codes, source_category_variants,
            sources, kinds, item_count
        ) VALUES %s
        ON CONFLICT (type_code) DO UPDATE SET
            role_code = EXCLUDED.role_code,
            canonical_name_zh = EXCLUDED.canonical_name_zh,
            canonical_name_en = EXCLUDED.canonical_name_en,
            source_categories = EXCLUDED.source_categories,
            source_type_codes = EXCLUDED.source_type_codes,
            source_category_variants = EXCLUDED.source_category_variants,
            sources = EXCLUDED.sources,
            kinds = EXCLUDED.kinds,
            item_count = EXCLUDED.item_count,
            updated_at = NOW();
    """

    item_sql = """
        INSERT INTO catalog_items (
            item_id, name_en, name_zh, display_name_zh,
            type_code, role_code, source_type_code, source_role_zh,
            source_category, canonical_category_zh,
            kind, source, source_group, catalog, source_dataset, is_ikea,
            width_cm, depth_cm, height_cm, dimension_review_status,
            materials, colors, search_text, data_quality_flags,
            duplicate_group_id, is_primary_variant, is_active, raw_data
        ) VALUES %s
        ON CONFLICT (item_id) DO UPDATE SET
            name_en = EXCLUDED.name_en,
            name_zh = EXCLUDED.name_zh,
            display_name_zh = EXCLUDED.display_name_zh,
            type_code = EXCLUDED.type_code,
            role_code = EXCLUDED.role_code,
            source_type_code = EXCLUDED.source_type_code,
            source_role_zh = EXCLUDED.source_role_zh,
            source_category = EXCLUDED.source_category,
            canonical_category_zh = EXCLUDED.canonical_category_zh,
            kind = EXCLUDED.kind,
            source = EXCLUDED.source,
            source_group = EXCLUDED.source_group,
            catalog = EXCLUDED.catalog,
            source_dataset = EXCLUDED.source_dataset,
            is_ikea = EXCLUDED.is_ikea,
            width_cm = EXCLUDED.width_cm,
            depth_cm = EXCLUDED.depth_cm,
            height_cm = EXCLUDED.height_cm,
            dimension_review_status = EXCLUDED.dimension_review_status,
            materials = EXCLUDED.materials,
            colors = EXCLUDED.colors,
            search_text = EXCLUDED.search_text,
            data_quality_flags = EXCLUDED.data_quality_flags,
            duplicate_group_id = EXCLUDED.duplicate_group_id,
            is_primary_variant = EXCLUDED.is_primary_variant,
            is_active = EXCLUDED.is_active,
            raw_data = EXCLUDED.raw_data,
            updated_at = NOW();
    """

    asset_sql = """
        INSERT INTO glb_assets (
            item_id, manifest_version,
            original_glb_path, local_file_exists, file_size_bytes, sha256,
            upload_filename, object_key, content_type,
            validation_status, validation_message, upload_status, upload_error,
            s3_etag, s3_uri, s3_https_url, delivery_url, delivery_url_type,
            temporary_presigned_url, presigned_expires_at, s3_version_id,
            uploaded_at, s3_last_modified, raw_manifest, raw_upload_result
        ) VALUES %s
        ON CONFLICT (item_id) DO UPDATE SET
            manifest_version = EXCLUDED.manifest_version,
            original_glb_path = EXCLUDED.original_glb_path,
            local_file_exists = EXCLUDED.local_file_exists,
            file_size_bytes = EXCLUDED.file_size_bytes,
            sha256 = EXCLUDED.sha256,
            upload_filename = EXCLUDED.upload_filename,
            object_key = EXCLUDED.object_key,
            content_type = EXCLUDED.content_type,
            validation_status = EXCLUDED.validation_status,
            validation_message = EXCLUDED.validation_message,
            upload_status = EXCLUDED.upload_status,
            upload_error = EXCLUDED.upload_error,
            s3_etag = EXCLUDED.s3_etag,
            s3_uri = EXCLUDED.s3_uri,
            s3_https_url = EXCLUDED.s3_https_url,
            delivery_url = EXCLUDED.delivery_url,
            delivery_url_type = EXCLUDED.delivery_url_type,
            temporary_presigned_url = EXCLUDED.temporary_presigned_url,
            presigned_expires_at = EXCLUDED.presigned_expires_at,
            s3_version_id = EXCLUDED.s3_version_id,
            uploaded_at = EXCLUDED.uploaded_at,
            s3_last_modified = EXCLUDED.s3_last_modified,
            raw_manifest = EXCLUDED.raw_manifest,
            raw_upload_result = EXCLUDED.raw_upload_result,
            updated_at = NOW();
    """

    # execute_values 需要將 dict 明確包成 Json。
    db_type_rows = [row[:6] + (Json(row[6]),) + row[7:] for row in type_rows]
    db_item_rows = [row[:-1] + (Json(row[-1]),) for row in item_rows]
    db_asset_rows = [
        row[:-2] + (Json(row[-2]), Json(row[-1]))
        for row in asset_rows
    ]

    batch_source = "|".join(
        [
            str(args.catalog.resolve()),
            str(args.manifest.resolve()),
            str(args.upload_result.resolve()),
            str(args.catalog.stat().st_size),
            str(args.manifest.stat().st_size),
            str(args.upload_result.stat().st_size),
        ]
    )
    batch_key = hashlib.sha256(batch_source.encode("utf-8")).hexdigest()[:24]

    batch_sql = """
        INSERT INTO import_batches (
            batch_key, catalog_filename, manifest_filename,
            upload_result_filename, manifest_report,
            catalog_rows, asset_rows, warning_count
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (batch_key) DO UPDATE SET
            manifest_report = EXCLUDED.manifest_report,
            catalog_rows = EXCLUDED.catalog_rows,
            asset_rows = EXCLUDED.asset_rows,
            warning_count = EXCLUDED.warning_count,
            imported_at = NOW();
    """

    with conn.cursor() as cur:
        execute_values(cur, role_sql, role_rows, page_size=args.page_size)
        execute_values(cur, type_sql, db_type_rows, page_size=args.page_size)
        execute_values(cur, item_sql, db_item_rows, page_size=args.page_size)
        execute_values(cur, asset_sql, db_asset_rows, page_size=args.page_size)
        cur.execute(
            batch_sql,
            (
                batch_key,
                args.catalog.name,
                args.manifest.name,
                args.upload_result.name,
                Json(manifest_report) if manifest_report is not None else None,
                len(item_rows),
                len(asset_rows),
                report["warning_count"],
            ),
        )
    return verify_post_import_counts(conn)


def main() -> int:
    args = parse_args()

    if args.page_size <= 0:
        raise ValueError("--page-size 必須大於 0。")

    items, catalog_metadata = load_catalog(args.catalog)
    manifest_rows = load_csv(args.manifest)
    upload_rows = load_csv(args.upload_result)
    manifest_report = load_optional_json(args.manifest_report)

    role_rows, type_rows, item_rows, asset_rows, report = validate_and_prepare(
        items, catalog_metadata, manifest_rows, upload_rows, strict=args.strict
    )
    report["catalog_metadata"] = catalog_metadata
    report["input_files"] = {
        "catalog": repo_relative(args.catalog),
        "manifest": repo_relative(args.manifest),
        "upload_result": repo_relative(args.upload_result),
        "manifest_report": (
            repo_relative(args.manifest_report) if args.manifest_report else None
        ),
    }
    report["output_files"] = {
        "quality_report": repo_relative(args.quality_report),
        "type_mapping_report": repo_relative(args.type_mapping_report),
        "review_report": repo_relative(args.review_report),
    }
    write_type_mapping_report(args.type_mapping_report, items, catalog_metadata)
    write_high_priority_review_report(args.review_report, items)
    write_quality_report(args.quality_report, report)

    print("資料驗證完成")
    print(f"- catalog：{len(items):,} 筆")
    print(f"- manifest：{len(manifest_rows):,} 筆")
    print(f"- upload result：{len(upload_rows):,} 筆")
    print(f"- item types：{len(type_rows):,} 種")
    print(f"- 警告：{report['warning_count']:,} 筆")
    print(f"- 品質報告：{args.quality_report}")
    print(f"- Type 對照：{args.type_mapping_report}")
    print(f"- 高優先級複查：{args.review_report}")

    if args.dry_run:
        print("Dry Run 完成，沒有連線 PostgreSQL，也沒有寫入資料。")
        return 0

    if args.create_database:
        created = ensure_database_exists(args.env)
        print("PostgreSQL 資料庫建立完成" if created else "PostgreSQL 資料庫已存在")

    conn = connect_db(args.env)
    try:
        with conn:
            if args.create_schema:
                execute_schema(conn, args.schema_sql)
            post_import_counts = upsert_to_postgres(
                conn,
                role_rows,
                type_rows,
                item_rows,
                asset_rows,
                report,
                args,
                manifest_report,
            )

        print("PostgreSQL 匯入完成")
        for name, count in post_import_counts.items():
            print(f"- {name}: {count:,}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
