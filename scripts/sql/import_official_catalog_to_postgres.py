#!/usr/bin/env python3
"""交易式驗證並匯入 8,675 筆官方家具與雲端資產。

家具分類、名稱、顏色、材質、尺寸、風格、房間、VLM 與啟用狀態
一律以官方 JSON 為準；CSV 只提供資產識別、上傳狀態與 delivery URL，
不再反向覆蓋家具欄位。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = PROJECT_ROOT / "JSON" / "furniture" / "furniture_official_catagory.json"
DEFAULT_MANIFEST_DIR = PROJECT_ROOT / "JSON" / "manifests"
DEFAULT_GLB_MANIFEST = DEFAULT_MANIFEST_DIR / "glb_upload_manifest.csv"
DEFAULT_GLB_RESULT = DEFAULT_MANIFEST_DIR / "glb_upload_all_result.csv"
DEFAULT_IMAGE_MANIFEST = DEFAULT_MANIFEST_DIR / "image_upload_manifest.csv"
DEFAULT_IMAGE_RESULT = DEFAULT_MANIFEST_DIR / "image_upload_all_result.csv"
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_postgresql_schema.sql")

EXPECTED_ITEM_COUNT = 8_675
EXPECTED_IMAGE_ROLES = {"front", "side", "angle-45"}
IMPORT_ISSUE_SOURCE = "official_catalog_import"

STYLE_NAMES_ZH = {
    "american": "美式風",
    "cream": "奶油風",
    "industrial": "工業風",
    "japanese": "日式風",
    "modern_minimal": "現代簡約風",
    "scandinavian": "北歐風",
}

# category_final 是目前 56 種正式分類的唯一來源。
# 固定 mapping 可避免 CSV type、舊 canonical_category_zh 或資料順序改變時，
# category_code 被重新推導成錯誤或帶 hash 的不穩定值。
CATEGORY_CODES_ZH = {
    "PAX 衣櫃": "pax-wardrobe",
    "兒童凳子與長凳": "childrens-stools-bench",
    "兒童家具": "childrens-furniture",
    "兒童桌": "childrens-table",
    "兒童椅與凳子": "kids-chairs-stool",
    "凳子與長凳": "stool-bench",
    "吧檯桌": "bar-table",
    "圓形地毯": "round-rug",
    "地毯": "rug",
    "壁架": "wall-shelf",
    "大型與中型地毯": "large-medium-rug",
    "大型鏡子": "large-mirror",
    "屏風與隔間": "room-divider",
    "展示櫃": "display-cabinet",
    "層架": "shelving-unit",
    "布沙發": "fabric-sofa",
    "床": "bed",
    "床墊": "mattress",
    "床邊桌": "bedside-table",
    "戶外地毯": "outdoor-rug",
    "手工地毯": "handmade-rug",
    "扶手椅": "armchair",
    "抱枕靠墊": "pillow-cushion",
    "抽屜櫃": "chests-of-drawer",
    "收納家具": "storage-furniture",
    "收納盒與籃子": "storage-boxes-basket",
    "收納系統": "storage-solution-system",
    "書桌": "desk",
    "書櫃": "bookcase",
    "桌子": "table",
    "椅子": "chair",
    "模組沙發": "modular-sofa",
    "櫃體": "cabinet-cupboard",
    "沙發": "sofa",
    "沙發床": "sofa-bed",
    "皮沙發": "leather-sofa",
    "盆栽植器": "planter",
    "羊皮與牛皮地毯": "sheepskins-cowhide",
    "花器": "vase",
    "茶几": "coffee-table",
    "落地燈": "floor-lamp",
    "衣帽架": "clothes-rack",
    "衣櫃": "wardrobe",
    "裝飾配件": "decoration",
    "走道地毯與小地毯": "runner-small-rug",
    "辦公椅": "office-chair",
    "鏡子": "mirror",
    "鏡櫃": "mirror-cabinet",
    "門墊": "door-mat",
    "電競椅": "gaming-chair",
    "電視櫃": "tv-bench",
    "電視與影音家具": "tv-media-furniture",
    "鞋櫃": "shoe-cabinet",
    "餐桌": "dining-table",
    "餐椅": "dining-chair",
    "餐邊櫃": "sideboard",
}

RESET_CATALOG_SQL = """
DROP VIEW IF EXISTS roompilot.furniture_catalog_api_current;
DROP VIEW IF EXISTS roompilot.furniture_catalog_current;
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector') THEN
        EXECUTE 'DROP FUNCTION IF EXISTS roompilot.search_furniture_embeddings_filtered(vector, character varying, integer, character varying, text[], integer, integer, numeric, numeric, character varying, character varying)';
        EXECUTE 'DROP FUNCTION IF EXISTS roompilot.search_furniture_embeddings(vector, character varying, integer)';
    END IF;
END
$block$;
DROP VIEW IF EXISTS roompilot.furniture_embedding_source_current;
DROP TABLE IF EXISTS roompilot.furniture_embeddings;
DROP TABLE IF EXISTS roompilot.furniture_admin_audit;
DROP TABLE IF EXISTS roompilot.furniture_quality_issues;
DROP TABLE IF EXISTS roompilot.furniture_assets;
DROP TABLE IF EXISTS roompilot.furniture_vlm_annotations;
DROP TABLE IF EXISTS roompilot.furniture_rooms;
DROP TABLE IF EXISTS roompilot.furniture_styles;
DROP TABLE IF EXISTS roompilot.furniture_items;
DROP TABLE IF EXISTS roompilot.rooms;
DROP TABLE IF EXISTS roompilot.styles;
DROP TABLE IF EXISTS roompilot.furniture_categories;
DROP TABLE IF EXISTS staging.stg_image_upload_result;
DROP TABLE IF EXISTS staging.stg_image_manifest;
DROP TABLE IF EXISTS staging.stg_glb_upload_result;
DROP TABLE IF EXISTS staging.stg_glb_manifest;
DROP TABLE IF EXISTS staging.stg_furniture_catalog;
"""

ROOM_NAMES_ZH = {
    "bathroom": "浴室",
    "bedroom": "臥室",
    "dining_room": "餐廳",
    "entryway": "玄關",
    "kids_room": "兒童房",
    "kitchen": "廚房",
    "living_room": "客廳",
    "outdoor": "戶外",
    "study": "書房",
}

VLM_FIELDS = (
    "object_type_zh",
    "description",
    "role",
    "visual_weight",
    "height_zone",
    "size_class",
    "pattern",
    "mood_tags",
    "shape_tags",
    "features",
    "search_keywords",
    "rag_text",
    "confidence",
    "desc_source",
)

REQUIRED_ITEM_FIELDS = {
    "id",
    "name_en",
    "category_final",
    "object_key",
    "glb_url",
    "colors",
    "materials",
    "style_primary",
    "style_secondary",
    "room_types",
    "rag_indexable",
}

# CSV 的正式用途只有資產關聯與 delivery URL；家具欄位不再依賴 CSV。
REQUIRED_GLB_MANIFEST_FIELDS = {"item_id"}
REQUIRED_GLB_RESULT_FIELDS = {"item_id", "delivery_url"}
REQUIRED_IMAGE_MANIFEST_FIELDS = {
    "image_id", "item_id", "image_role", "object_key"
}
REQUIRED_IMAGE_RESULT_FIELDS = REQUIRED_IMAGE_MANIFEST_FIELDS | {"delivery_url"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="驗證並匯入 RoomPilot 官方家具、VLM 與 GLB/圖片資產。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--glb-manifest", type=Path, default=DEFAULT_GLB_MANIFEST)
    parser.add_argument("--glb-upload-result", type=Path, default=DEFAULT_GLB_RESULT)
    parser.add_argument("--image-manifest", type=Path, default=DEFAULT_IMAGE_MANIFEST)
    parser.add_argument("--image-upload-result", type=Path, default=DEFAULT_IMAGE_RESULT)
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--validation-report",
        type=Path,
        help="選擇性輸出 JSON 驗證報告；預設不保留報告檔。",
    )
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="正式匯入時不執行 roompilot_postgresql_schema.sql。",
    )
    parser.add_argument(
        "--skip-staging",
        action="store_true",
        help="只更新正式表，不保存本批原始列到 staging。",
    )
    parser.add_argument(
        "--create-database",
        action="store_true",
        help="DB_NAME 不存在時，以 DB_ADMIN_DB 建立 UTF-8 資料庫。",
    )
    parser.add_argument(
        "--allow-incomplete-uploads",
        action="store_true",
        help="允許 upload result 含非 uploaded/ready 狀態；預設視為驗證錯誤。",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help=(
            "在同一 transaction 內只刪除家具 catalog tables/views/staging，"
            "重建 schema 後匯入；不影響 project、render 或 runtime catalog tables。"
        ),
    )
    return parser.parse_args(argv)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"none", "null", "nan"}:
        return None
    return text


def parse_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    text = clean_text(value)
    if text is None:
        return default
    lowered = text.casefold()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"無法解析布林值：{value!r}")


def parse_int(value: Any) -> int | None:
    text = clean_text(value)
    return None if text is None else int(float(text))


def parse_float(value: Any) -> float | None:
    text = clean_text(value)
    return None if text is None else float(text)


def text_list(value: Any, field: str, item_id: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{item_id}: {field} 必須是 JSON array。")
    result: list[str] = []
    for raw in value:
        text = clean_text(raw)
        if text is not None:
            result.append(text)
    return result


def final_category_zh(item: dict[str, Any]) -> str:
    """以 category_final 為準，舊欄位只作向後相容 fallback。"""
    value = clean_text(item.get("category_final")) or clean_text(
        item.get("canonical_category_zh")
    )
    if value is None:
        raise ValueError(f"{item.get('id')}: 缺少 category_final。")
    return value


def source_from_object_key(object_key: Any, item_id: str) -> str:
    """由 JSON object_key 的 models/{source}/furniture/... 取得來源。"""
    key = clean_text(object_key)
    if key is None:
        raise ValueError(f"{item_id}: 缺少 object_key。")
    parts = key.replace("\\", "/").split("/")
    if len(parts) < 4 or parts[0] != "models" or parts[2] != "furniture":
        raise ValueError(
            f"{item_id}: object_key 不符合 models/{{source}}/furniture/...：{key!r}"
        )
    source = clean_text(parts[1])
    if source is None:
        raise ValueError(f"{item_id}: 無法由 object_key 取得 source。")
    return source.casefold()


def first_or_fallback(values: list[str], fallback: Any) -> str | None:
    """主顏色／主材質優先使用正式陣列第一個值。"""
    return values[0] if values else clean_text(fallback)


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 catalog：{path}")
    with path.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("catalog 必須是含 items array 的 JSON object。")
    items = payload["items"]
    if not all(isinstance(item, dict) for item in items):
        raise ValueError("catalog.items 每一筆都必須是 JSON object。")
    metadata = {key: value for key, value in payload.items() if key != "items"}
    return items, metadata


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到 CSV：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV 沒有表頭：{path}")
        return list(reader.fieldnames), list(reader)


def index_unique(
    rows: Iterable[dict[str, Any]],
    key: str,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    missing = 0
    for row in rows:
        value = clean_text(row.get(key))
        if value is None:
            missing += 1
            continue
        if value in result and len(duplicates) < 5:
            duplicates.append(value)
        result[value] = row
    if missing:
        errors.append(f"{label}: {missing:,} 列缺少 {key}。")
    if duplicates:
        errors.append(f"{label}: {key} 重複，例如 {duplicates}。")
    return result


def compare_id_sets(
    expected: set[str],
    actual: set[str],
    label: str,
    errors: list[str],
    *,
    allowed_extra: set[str] | None = None,
) -> None:
    missing = sorted(expected - actual)
    extra = sorted((actual - expected) - (allowed_extra or set()))
    if missing:
        errors.append(f"{label}: 缺少 {len(missing):,} 個 item_id，例如 {missing[:5]}。")
    if extra:
        errors.append(f"{label}: 多出 {len(extra):,} 個 item_id，例如 {extra[:5]}。")


def validate_inputs(
    args: argparse.Namespace,
    items: list[dict[str, Any]],
    metadata: dict[str, Any],
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]],
    input_hashes: dict[str, str],
) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Any]]]]:
    errors: list[str] = []
    warnings: list[str] = []

    metadata_count = metadata.get("count")
    if metadata_count != len(items):
        errors.append(f"catalog metadata.count={metadata_count!r}，實際為 {len(items):,}。")
    if len(items) != EXPECTED_ITEM_COUNT:
        errors.append(f"官方 catalog 應為 {EXPECTED_ITEM_COUNT:,} 筆，實際為 {len(items):,}。")

    excluded_rows = metadata.get("excluded_items") or []
    if not isinstance(excluded_rows, list):
        errors.append("catalog metadata.excluded_items 必須是 array。")
        excluded_rows = []
    excluded_item_ids = {
        item_id
        for row in excluded_rows
        if isinstance(row, dict) and (item_id := clean_text(row.get("id")))
    }
    source_item_count = metadata.get("source_item_count")
    if source_item_count is not None and source_item_count != len(items) + len(excluded_item_ids):
        errors.append(
            "catalog metadata.source_item_count 必須等於正式家具加排除項目："
            f"{source_item_count!r} != {len(items):,} + {len(excluded_item_ids):,}。"
        )

    item_index: dict[str, dict[str, Any]] = {}
    missing_item_fields: Counter[str] = Counter()
    duplicate_ids: list[str] = []
    for item in items:
        item_id = clean_text(item.get("id"))
        for field in REQUIRED_ITEM_FIELDS:
            value = item.get(field)
            if value is None or value == "":
                missing_item_fields[field] += 1
        if item_id is None:
            continue
        if item_id in item_index and len(duplicate_ids) < 5:
            duplicate_ids.append(item_id)
        item_index[item_id] = item
    if missing_item_fields:
        errors.append(f"catalog 必填欄位缺漏：{dict(missing_item_fields)}。")
    if duplicate_ids:
        errors.append(f"catalog item_id 重複，例如 {duplicate_ids}。")
    if len(item_index) != len(items):
        errors.append(f"catalog 唯一且非空的 item_id 為 {len(item_index):,}，列數為 {len(items):,}。")

    required_by_label = {
        "glb_manifest": REQUIRED_GLB_MANIFEST_FIELDS,
        "glb_result": REQUIRED_GLB_RESULT_FIELDS,
        "image_manifest": REQUIRED_IMAGE_MANIFEST_FIELDS,
        "image_result": REQUIRED_IMAGE_RESULT_FIELDS,
    }
    for label, required in required_by_label.items():
        headers = set(csv_payloads[label][0])
        missing = sorted(required - headers)
        if missing:
            errors.append(f"{label} 缺少欄位：{missing}。")

    indexes = {
        "items": item_index,
        "glb_manifest": index_unique(csv_payloads["glb_manifest"][1], "item_id", "glb_manifest", errors),
        "glb_result": index_unique(csv_payloads["glb_result"][1], "item_id", "glb_result", errors),
        "image_manifest": index_unique(csv_payloads["image_manifest"][1], "image_id", "image_manifest", errors),
        "image_result": index_unique(csv_payloads["image_result"][1], "image_id", "image_result", errors),
    }

    catalog_ids = set(item_index)
    compare_id_sets(
        catalog_ids,
        set(indexes["glb_manifest"]),
        "glb_manifest",
        errors,
        allowed_extra=excluded_item_ids,
    )
    compare_id_sets(
        catalog_ids,
        set(indexes["glb_result"]),
        "glb_result",
        errors,
        allowed_extra=excluded_item_ids,
    )
    compare_id_sets(
        catalog_ids,
        {clean_text(row.get("item_id")) or "" for row in csv_payloads["image_manifest"][1]},
        "image_manifest",
        errors,
        allowed_extra=excluded_item_ids,
    )
    compare_id_sets(
        catalog_ids,
        {clean_text(row.get("item_id")) or "" for row in csv_payloads["image_result"][1]},
        "image_result",
        errors,
        allowed_extra=excluded_item_ids,
    )

    glb_mismatches: list[str] = []
    for item_id in sorted(catalog_ids & set(indexes["glb_result"])):
        item = item_index[item_id]
        manifest = indexes["glb_manifest"].get(item_id, {})
        result = indexes["glb_result"][item_id]
        json_object_key = clean_text(item.get("object_key"))
        json_delivery_url = clean_text(item.get("glb_url"))
        manifest_object_key = clean_text(manifest.get("object_key"))
        result_object_key = clean_text(result.get("object_key"))
        object_key_ok = all(
            value in {None, json_object_key}
            for value in (manifest_object_key, result_object_key)
        )
        if not object_key_ok or json_delivery_url != clean_text(result.get("delivery_url")):
            if len(glb_mismatches) < 5:
                glb_mismatches.append(item_id)
    if glb_mismatches:
        errors.append(
            "JSON object_key/glb_url 與 GLB 資產 CSV 不一致，例如 "
            f"{glb_mismatches}。"
        )

    image_pair_mismatches: list[str] = []
    for image_id in sorted(set(indexes["image_manifest"]) & set(indexes["image_result"])):
        manifest = indexes["image_manifest"][image_id]
        result = indexes["image_result"][image_id]
        compared = ("item_id", "image_role", "object_key")
        if any(clean_text(manifest.get(field)) != clean_text(result.get(field)) for field in compared):
            if len(image_pair_mismatches) < 5:
                image_pair_mismatches.append(image_id)
    if image_pair_mismatches:
        errors.append(f"image manifest/result 資產欄位不一致，例如 {image_pair_mismatches}。")

    role_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in csv_payloads["image_result"][1]:
        item_id = clean_text(row.get("item_id"))
        role = clean_text(row.get("image_role"))
        if item_id and role:
            role_counts[item_id][role] += 1
    bad_roles: list[tuple[str, dict[str, int]]] = []
    for item_id in sorted(catalog_ids):
        counts = role_counts.get(item_id, Counter())
        if set(counts) != EXPECTED_IMAGE_ROLES or any(counts[role] != 1 for role in counts):
            if len(bad_roles) < 5:
                bad_roles.append((item_id, dict(counts)))
    if bad_roles:
        errors.append(f"每件家具必須恰有三視角圖片，異常例如 {bad_roles}。")

    if not args.allow_incomplete_uploads:
        for label in ("glb_result", "image_result"):
            headers, rows = csv_payloads[label]
            if "upload_status" in headers:
                upload_status = Counter(row.get("upload_status", "") for row in rows)
                if upload_status != Counter({"uploaded": len(rows)}):
                    errors.append(
                        f"{label} upload_status 非全數 uploaded：{dict(upload_status)}。"
                    )
            if "validation_status" in headers:
                validation_status = Counter(
                    row.get("validation_status", "") for row in rows
                )
                if validation_status != Counter({"ready": len(rows)}):
                    errors.append(
                        f"{label} validation_status 非全數 ready："
                        f"{dict(validation_status)}。"
                    )

    batch_material = "|".join(f"{key}:{input_hashes[key]}" for key in sorted(input_hashes))
    batch_key = hashlib.sha256(batch_material.encode("utf-8")).hexdigest()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valid": not errors,
        "batch_key": batch_key,
        "catalog_metadata": metadata,
        "excluded_item_ids": sorted(excluded_item_ids),
        "input_files": {},
        "source_counts": {
            "catalog_items": len(items),
            "glb_manifest_rows": len(csv_payloads["glb_manifest"][1]),
            "glb_result_rows": len(csv_payloads["glb_result"][1]),
            "image_manifest_rows": len(csv_payloads["image_manifest"][1]),
            "image_result_rows": len(csv_payloads["image_result"][1]),
        },
        "errors": errors,
        "warnings": warnings,
    }
    paths = {
        "catalog": args.catalog,
        "glb_manifest": args.glb_manifest,
        "glb_result": args.glb_upload_result,
        "image_manifest": args.image_manifest,
        "image_result": args.image_upload_result,
    }
    for label, path in paths.items():
        report["input_files"][label] = {
            "path": repo_path(path),
            "size_bytes": path.stat().st_size,
            "sha256": input_hashes[label],
        }
    return report, indexes


def category_code_map(items: list[dict[str, Any]]) -> dict[str, str]:
    categories = {final_category_zh(item) for item in items}
    unknown = sorted(categories - set(CATEGORY_CODES_ZH))
    missing = sorted(set(CATEGORY_CODES_ZH) - categories)
    if unknown:
        raise ValueError(f"category_final 缺少 category_code mapping：{unknown}")
    if missing:
        raise ValueError(f"CATEGORY_CODES_ZH 含目前 catalog 未使用分類：{missing}")
    return {category: CATEGORY_CODES_ZH[category] for category in sorted(categories)}


def make_quality_issues(item: dict[str, Any]) -> list[dict[str, Any]]:
    item_id = str(item["id"])
    issues: list[dict[str, Any]] = []
    consistency_flag = clean_text(item.get("consistency_flag"))
    if consistency_flag:
        severity_text = clean_text(item.get("consistency_severity")) or ""
        severity = "high" if severity_text.startswith("high") else "medium"
        issues.append(
            {
                "item_id": item_id,
                "issue_type": consistency_flag,
                "severity": severity,
                "current_value": {
                    "name_en": item.get("name_en"),
                    "name_zh": item.get("name_zh"),
                    "canonical_category_zh": item.get("canonical_category_zh"),
                    "category_final": item.get("category_final"),
                },
                "suggested_value": {"category_final": item.get("suggested_category")},
            }
        )
    duplicate_group = clean_text(item.get("duplicate_group"))
    if duplicate_group:
        issues.append(
            {
                "item_id": item_id,
                "issue_type": "duplicate_group",
                "severity": "medium",
                "current_value": {"duplicate_group": duplicate_group},
                "suggested_value": None,
            }
        )
    dimension_status = clean_text(item.get("dimension_review_status"))
    if dimension_status:
        issues.append(
            {
                "item_id": item_id,
                "issue_type": "dimension_review",
                "severity": "high",
                "current_value": {
                    "status": dimension_status,
                    "width_cm": item.get("width_cm"),
                    "depth_cm": item.get("depth_cm"),
                    "height_cm": item.get("height_cm"),
                },
                "suggested_value": None,
            }
        )
    if clean_text(item.get("color")) is None:
        issues.append(
            {
                "item_id": item_id,
                "issue_type": "missing_primary_color",
                "severity": "medium",
                "current_value": {"color": item.get("color"), "colors": item.get("colors")},
                "suggested_value": None,
            }
        )
    if clean_text(item.get("object_type_zh")) is None:
        issues.append(
            {
                "item_id": item_id,
                "issue_type": "missing_object_type_zh",
                "severity": "medium",
                "current_value": {"object_type_zh": item.get("object_type_zh")},
                "suggested_value": None,
            }
        )
    return issues


def prepare_rows(
    items: list[dict[str, Any]], indexes: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any]:
    category_codes = category_code_map(items)
    categories = []
    for category_zh, code in sorted(category_codes.items(), key=lambda pair: pair[1]):
        categories.append(
            {
                "category_code": code,
                "name_zh": category_zh,
                "name_en": code.replace("-", " ").title(),
            }
        )

    style_codes = sorted(
        {
            str(item[field])
            for item in items
            for field in ("style_primary", "style_secondary")
            if clean_text(item.get(field))
        }
    )
    room_codes = sorted(
        {room for item in items for room in text_list(item.get("room_types"), "room_types", str(item["id"]))}
    )
    unknown_styles = sorted(set(style_codes) - set(STYLE_NAMES_ZH))
    unknown_rooms = sorted(set(room_codes) - set(ROOM_NAMES_ZH))
    if unknown_styles:
        raise ValueError(f"缺少風格中文名稱 mapping：{unknown_styles}")
    if unknown_rooms:
        raise ValueError(f"缺少房間中文名稱 mapping：{unknown_rooms}")

    item_rows: list[dict[str, Any]] = []
    style_links: list[dict[str, Any]] = []
    room_links: list[dict[str, str]] = []
    annotations: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []

    for item in items:
        item_id = str(item["id"])
        category_zh = final_category_zh(item)
        category_code = category_codes[category_zh]
        source = source_from_object_key(item.get("object_key"), item_id)
        colors = text_list(item.get("colors"), "colors", item_id)
        materials = text_list(item.get("materials"), "materials", item_id)
        item_rows.append(
            {
                "item_id": item_id,
                "category_code": category_code,
                "source": source,
                "source_group": "IKEA" if source == "ikea" else "non-IKEA",
                "catalog": f"{source}_furniture",
                "kind": "furniture",
                # JSON 沒有獨立 source_type；使用正式 category_code，
                # 避免再由 CSV type 覆蓋已修正的 category_final。
                "source_type": category_code,
                "name_en": clean_text(item.get("name_en")),
                "name_zh": clean_text(item.get("name_zh")),
                "primary_color": first_or_fallback(colors, item.get("color")),
                "colors": colors,
                "primary_material": first_or_fallback(
                    materials, item.get("material")
                ),
                "materials": materials,
                "width_cm": parse_float(item.get("width_cm")),
                "depth_cm": parse_float(item.get("depth_cm")),
                "height_cm": parse_float(item.get("height_cm")),
                "price_twd": parse_int(item.get("price_twd")),
                "price_is_estimated": parse_bool(
                    item.get("price_is_estimated"), False
                ),
                "product_url": clean_text(item.get("product_url")),
                "is_active": parse_bool(item.get("is_active"), True),
                "raw_data": item,
            }
        )
        confidence = parse_float(item.get("confidence"))
        for rank, field in ((1, "style_primary"), (2, "style_secondary")):
            style_links.append(
                {
                    "item_id": item_id,
                    "style_code": str(item[field]),
                    "style_rank": rank,
                    "confidence": confidence,
                }
            )
        for room_code in text_list(item.get("room_types"), "room_types", item_id):
            room_links.append({"item_id": item_id, "room_code": room_code})

        raw_response = {field: item.get(field) for field in VLM_FIELDS}
        annotation_json = json.dumps(
            raw_response, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        annotations.append(
            {
                "item_id": item_id,
                "annotation_hash": hashlib.sha256(annotation_json.encode("utf-8")).hexdigest(),
                "model_name": "source_catalog_vlm",
                "model_version": None,
                "prompt_version": None,
                "object_type_zh": clean_text(item.get("object_type_zh")),
                "description": clean_text(item.get("description")),
                "role": clean_text(item.get("role")),
                "visual_weight": clean_text(item.get("visual_weight")),
                "height_zone": clean_text(item.get("height_zone")),
                "size_class": clean_text(item.get("size_class")),
                "pattern": clean_text(item.get("pattern")),
                "mood_tags": text_list(item.get("mood_tags"), "mood_tags", item_id),
                "shape_tags": text_list(item.get("shape_tags"), "shape_tags", item_id),
                "features": text_list(item.get("features"), "features", item_id),
                "search_keywords": text_list(item.get("search_keywords"), "search_keywords", item_id),
                "rag_text": text_list(item.get("rag_text"), "rag_text", item_id),
                "confidence": confidence,
                "description_source": clean_text(item.get("desc_source")),
                "raw_response": raw_response,
            }
        )
        quality_issues.extend(make_quality_issues(item))

    return {
        "categories": categories,
        "styles": [
            {"style_code": code, "name_zh": STYLE_NAMES_ZH[code]}
            for code in style_codes
        ],
        "rooms": [
            {"room_code": code, "name_zh": ROOM_NAMES_ZH[code]}
            for code in room_codes
        ],
        "items": item_rows,
        "style_links": style_links,
        "room_links": room_links,
        "annotations": annotations,
        "quality_issues": quality_issues,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def db_config(env_path: Path, database: str | None = None) -> dict[str, Any]:
    load_env_file(env_path)
    required = ("DB_NAME", "DB_USER")
    missing = [key for key in required if clean_text(os.getenv(key)) is None]
    if missing:
        raise ValueError(f"資料庫設定缺少：{', '.join(missing)}（來源：{env_path} 或環境變數）")
    config: dict[str, Any] = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": database or os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        "application_name": os.getenv("DB_APPLICATION_NAME", "roompilot_official_import"),
    }
    sslmode = clean_text(os.getenv("DB_SSLMODE"))
    if sslmode:
        config["sslmode"] = sslmode
    return config


def require_psycopg():
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "找不到 psycopg2。請先執行：python -m pip install -r requirements.txt"
        ) from exc
    return psycopg2


def ensure_database_exists(env_path: Path) -> bool:
    psycopg = require_psycopg()
    from psycopg2 import sql

    load_env_file(env_path)
    target = clean_text(os.getenv("DB_NAME"))
    if target is None:
        raise ValueError("DB_NAME 未設定。")
    admin = clean_text(os.getenv("DB_ADMIN_DB")) or "postgres"
    config = db_config(env_path, admin)
    connection = psycopg.connect(**config)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
            if cursor.fetchone() is not None:
                return False
            cursor.execute(
                sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(target)
                )
            )
    finally:
        connection.close()
    return True


def execute_many(cursor, statement: str, rows: list[tuple[Any, ...]], page_size: int) -> None:
    for start in range(0, len(rows), page_size):
        cursor.executemany(statement, rows[start : start + page_size])


def s3_bucket(s3_uri: Any) -> str | None:
    uri = clean_text(s3_uri)
    if uri is None:
        return None
    parsed = urlparse(uri)
    return parsed.netloc if parsed.scheme == "s3" else None


def asset_tuple(
    asset_type: str,
    view_role: str | None,
    external_id: str,
    manifest: dict[str, Any],
    result: dict[str, Any],
    Jsonb,
    *,
    item_id_override: str | None = None,
    object_key_override: str | None = None,
    delivery_url_override: str | None = None,
    default_content_type: str | None = None,
) -> tuple[Any, ...]:
    """建立資產列；家具 GLB 的 item_id/object_key 以 JSON 為準。"""
    source_field = "original_glb_path" if asset_type == "glb" else "original_image_path"
    item_id = item_id_override or clean_text(result.get("item_id")) or clean_text(
        manifest.get("item_id")
    )
    object_key = object_key_override or clean_text(result.get("object_key")) or clean_text(
        manifest.get("object_key")
    )
    delivery_url = delivery_url_override or clean_text(result.get("delivery_url"))
    if item_id is None or object_key is None or delivery_url is None:
        raise ValueError(
            f"資產缺少 item_id/object_key/delivery_url：external_id={external_id!r}"
        )
    return (
        external_id,
        item_id,
        asset_type,
        view_role,
        clean_text(result.get(source_field)) or clean_text(manifest.get(source_field)),
        parse_bool(
            result.get("local_file_exists"),
            parse_bool(manifest.get("local_file_exists")),
        ),
        object_key,
        s3_bucket(result.get("s3_uri")),
        clean_text(result.get("s3_uri")),
        clean_text(result.get("s3_https_url")),
        delivery_url,
        clean_text(result.get("delivery_url_type")) or "cloudfront",
        clean_text(result.get("content_type"))
        or clean_text(manifest.get("content_type"))
        or default_content_type,
        parse_int(result.get("file_size_bytes"))
        or parse_int(manifest.get("file_size_bytes")),
        parse_int(result.get("width_px")) or parse_int(manifest.get("width_px")),
        parse_int(result.get("height_px")) or parse_int(manifest.get("height_px")),
        clean_text(result.get("sha256")) or clean_text(manifest.get("sha256")),
        clean_text(result.get("s3_etag")),
        clean_text(result.get("upload_status")) or "uploaded",
        clean_text(result.get("validation_status")) or "ready",
        clean_text(result.get("validation_message")),
        clean_text(result.get("upload_error")),
        clean_text(result.get("uploaded_at")),
        clean_text(result.get("s3_last_modified")),
        clean_text(result.get("s3_version_id")),
        clean_text(result.get("manifest_version"))
        or clean_text(manifest.get("manifest_version")),
        Jsonb(manifest),
        Jsonb(result),
    )


def import_staging(
    cursor,
    args: argparse.Namespace,
    items: list[dict[str, Any]],
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]],
    batch_key: str,
    Jsonb,
) -> None:
    specs = [
        (
            "staging.stg_furniture_catalog",
            "INSERT INTO staging.stg_furniture_catalog "
            "(batch_key, row_number, item_id, source_file, raw_data) VALUES (%s,%s,%s,%s,%s)",
            [
                (batch_key, number, item["id"], repo_path(args.catalog), Jsonb(item))
                for number, item in enumerate(items, 1)
            ],
        ),
        (
            "staging.stg_glb_manifest",
            "INSERT INTO staging.stg_glb_manifest "
            "(batch_key, row_number, item_id, object_key, source_file, raw_data) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            [
                (batch_key, number, row["item_id"], row.get("object_key"), repo_path(args.glb_manifest), Jsonb(row))
                for number, row in enumerate(csv_payloads["glb_manifest"][1], 1)
            ],
        ),
        (
            "staging.stg_glb_upload_result",
            "INSERT INTO staging.stg_glb_upload_result "
            "(batch_key, row_number, item_id, object_key, source_file, raw_data) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            [
                (batch_key, number, row["item_id"], row.get("object_key"), repo_path(args.glb_upload_result), Jsonb(row))
                for number, row in enumerate(csv_payloads["glb_result"][1], 1)
            ],
        ),
        (
            "staging.stg_image_manifest",
            "INSERT INTO staging.stg_image_manifest "
            "(batch_key, row_number, image_id, item_id, view_role, object_key, source_file, raw_data) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    batch_key,
                    number,
                    row["image_id"],
                    row["item_id"],
                    row.get("image_role"),
                    row.get("object_key"),
                    repo_path(args.image_manifest),
                    Jsonb(row),
                )
                for number, row in enumerate(csv_payloads["image_manifest"][1], 1)
            ],
        ),
        (
            "staging.stg_image_upload_result",
            "INSERT INTO staging.stg_image_upload_result "
            "(batch_key, row_number, image_id, item_id, view_role, object_key, source_file, raw_data) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    batch_key,
                    number,
                    row["image_id"],
                    row["item_id"],
                    row.get("image_role"),
                    row.get("object_key"),
                    repo_path(args.image_upload_result),
                    Jsonb(row),
                )
                for number, row in enumerate(csv_payloads["image_result"][1], 1)
            ],
        ),
    ]
    for table, statement, rows in specs:
        cursor.execute(f"DELETE FROM {table} WHERE batch_key = %s", (batch_key,))
        execute_many(cursor, statement, rows, args.page_size)


def import_formal_tables(
    cursor,
    args: argparse.Namespace,
    prepared: dict[str, Any],
    indexes: dict[str, dict[str, dict[str, Any]]],
    Jsonb,
) -> None:
    execute_many(
        cursor,
        """
        INSERT INTO roompilot.furniture_categories (category_code, name_zh, name_en)
        VALUES (%s,%s,%s)
        ON CONFLICT (category_code) DO UPDATE SET
            name_zh = EXCLUDED.name_zh,
            name_en = EXCLUDED.name_en,
            is_active = TRUE
        """,
        [(row["category_code"], row["name_zh"], row["name_en"]) for row in prepared["categories"]],
        args.page_size,
    )
    cursor.execute("SELECT category_code, category_id FROM roompilot.furniture_categories")
    category_ids = dict(cursor.fetchall())

    item_statement = """
        INSERT INTO roompilot.furniture_items (
            item_id, category_id, source, source_group, catalog, kind, source_type,
            name_en, name_zh, primary_color, colors, primary_material, materials,
            width_cm, depth_cm, height_cm, price_twd, price_is_estimated,
            product_url, is_active, raw_data
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (item_id) DO UPDATE SET
            category_id = EXCLUDED.category_id,
            source = EXCLUDED.source,
            source_group = EXCLUDED.source_group,
            catalog = EXCLUDED.catalog,
            kind = EXCLUDED.kind,
            source_type = EXCLUDED.source_type,
            name_en = EXCLUDED.name_en,
            name_zh = EXCLUDED.name_zh,
            primary_color = EXCLUDED.primary_color,
            colors = EXCLUDED.colors,
            primary_material = EXCLUDED.primary_material,
            materials = EXCLUDED.materials,
            width_cm = EXCLUDED.width_cm,
            depth_cm = EXCLUDED.depth_cm,
            height_cm = EXCLUDED.height_cm,
            price_twd = EXCLUDED.price_twd,
            price_is_estimated = EXCLUDED.price_is_estimated,
            product_url = EXCLUDED.product_url,
            is_active = EXCLUDED.is_active,
            raw_data = EXCLUDED.raw_data
    """
    item_values = []
    for row in prepared["items"]:
        item_values.append(
            (
                row["item_id"],
                category_ids[row["category_code"]],
                row["source"],
                row["source_group"],
                row["catalog"],
                row["kind"],
                row["source_type"],
                row["name_en"],
                row["name_zh"],
                row["primary_color"],
                row["colors"],
                row["primary_material"],
                row["materials"],
                row["width_cm"],
                row["depth_cm"],
                row["height_cm"],
                row["price_twd"],
                row["price_is_estimated"],
                row["product_url"],
                row["is_active"],
                Jsonb(row["raw_data"]),
            )
        )
    execute_many(cursor, item_statement, item_values, args.page_size)

    execute_many(
        cursor,
        """
        INSERT INTO roompilot.styles (style_code, name_zh)
        VALUES (%s,%s)
        ON CONFLICT (style_code) DO UPDATE SET name_zh = EXCLUDED.name_zh, is_active = TRUE
        """,
        [(row["style_code"], row["name_zh"]) for row in prepared["styles"]],
        args.page_size,
    )
    cursor.execute("SELECT style_code, style_id FROM roompilot.styles")
    style_ids = dict(cursor.fetchall())

    execute_many(
        cursor,
        """
        INSERT INTO roompilot.rooms (room_code, name_zh)
        VALUES (%s,%s)
        ON CONFLICT (room_code) DO UPDATE SET name_zh = EXCLUDED.name_zh, is_active = TRUE
        """,
        [(row["room_code"], row["name_zh"]) for row in prepared["rooms"]],
        args.page_size,
    )
    cursor.execute("SELECT room_code, room_id FROM roompilot.rooms")
    room_ids = dict(cursor.fetchall())

    item_ids = [row["item_id"] for row in prepared["items"]]
    cursor.execute("DELETE FROM roompilot.furniture_styles WHERE item_id = ANY(%s)", (item_ids,))
    execute_many(
        cursor,
        "INSERT INTO roompilot.furniture_styles (item_id, style_id, style_rank, confidence) "
        "VALUES (%s,%s,%s,%s)",
        [
            (row["item_id"], style_ids[row["style_code"]], row["style_rank"], row["confidence"])
            for row in prepared["style_links"]
        ],
        args.page_size,
    )

    cursor.execute("DELETE FROM roompilot.furniture_rooms WHERE item_id = ANY(%s)", (item_ids,))
    execute_many(
        cursor,
        "INSERT INTO roompilot.furniture_rooms (item_id, room_id) VALUES (%s,%s)",
        [(row["item_id"], room_ids[row["room_code"]]) for row in prepared["room_links"]],
        args.page_size,
    )

    cursor.execute(
        "UPDATE roompilot.furniture_vlm_annotations SET is_current = FALSE "
        "WHERE item_id = ANY(%s) AND is_current",
        (item_ids,),
    )
    annotation_statement = """
        INSERT INTO roompilot.furniture_vlm_annotations (
            item_id, annotation_hash, model_name, model_version, prompt_version,
            object_type_zh, description, role, visual_weight, height_zone, size_class,
            pattern, mood_tags, shape_tags, features, search_keywords, rag_text,
            confidence, description_source, raw_response, is_current
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (item_id, annotation_hash) DO UPDATE SET
            model_name = EXCLUDED.model_name,
            model_version = EXCLUDED.model_version,
            prompt_version = EXCLUDED.prompt_version,
            object_type_zh = EXCLUDED.object_type_zh,
            description = EXCLUDED.description,
            role = EXCLUDED.role,
            visual_weight = EXCLUDED.visual_weight,
            height_zone = EXCLUDED.height_zone,
            size_class = EXCLUDED.size_class,
            pattern = EXCLUDED.pattern,
            mood_tags = EXCLUDED.mood_tags,
            shape_tags = EXCLUDED.shape_tags,
            features = EXCLUDED.features,
            search_keywords = EXCLUDED.search_keywords,
            rag_text = EXCLUDED.rag_text,
            confidence = EXCLUDED.confidence,
            description_source = EXCLUDED.description_source,
            raw_response = EXCLUDED.raw_response,
            is_current = TRUE
    """
    execute_many(
        cursor,
        annotation_statement,
        [
            (
                row["item_id"], row["annotation_hash"], row["model_name"],
                row["model_version"], row["prompt_version"], row["object_type_zh"],
                row["description"], row["role"], row["visual_weight"], row["height_zone"],
                row["size_class"], row["pattern"], row["mood_tags"], row["shape_tags"],
                row["features"], row["search_keywords"], row["rag_text"], row["confidence"],
                row["description_source"], Jsonb(row["raw_response"]),
            )
            for row in prepared["annotations"]
        ],
        args.page_size,
    )

    asset_statement_prefix = """
        INSERT INTO roompilot.furniture_assets (
            external_id, item_id, asset_type, view_role, source_path, local_file_exists,
            object_key, bucket_name, s3_uri, s3_https_url, delivery_url, delivery_url_type,
            content_type, file_size_bytes, width_px, height_px, sha256, etag,
            upload_status, validation_status, validation_message, upload_error,
            uploaded_at, s3_last_modified, s3_version_id, manifest_version,
            raw_manifest, raw_upload_result
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    asset_update = """
        DO UPDATE SET
            external_id = EXCLUDED.external_id,
            source_path = EXCLUDED.source_path,
            local_file_exists = EXCLUDED.local_file_exists,
            object_key = EXCLUDED.object_key,
            bucket_name = EXCLUDED.bucket_name,
            s3_uri = EXCLUDED.s3_uri,
            s3_https_url = EXCLUDED.s3_https_url,
            delivery_url = EXCLUDED.delivery_url,
            delivery_url_type = EXCLUDED.delivery_url_type,
            content_type = EXCLUDED.content_type,
            file_size_bytes = EXCLUDED.file_size_bytes,
            width_px = EXCLUDED.width_px,
            height_px = EXCLUDED.height_px,
            sha256 = EXCLUDED.sha256,
            etag = EXCLUDED.etag,
            upload_status = EXCLUDED.upload_status,
            validation_status = EXCLUDED.validation_status,
            validation_message = EXCLUDED.validation_message,
            upload_error = EXCLUDED.upload_error,
            uploaded_at = EXCLUDED.uploaded_at,
            s3_last_modified = EXCLUDED.s3_last_modified,
            s3_version_id = EXCLUDED.s3_version_id,
            manifest_version = EXCLUDED.manifest_version,
            raw_manifest = EXCLUDED.raw_manifest,
            raw_upload_result = EXCLUDED.raw_upload_result
    """
    glb_assets = []
    for item_id in sorted(indexes["items"]):
        item = indexes["items"][item_id]
        glb_assets.append(
            asset_tuple(
                "glb",
                None,
                item_id,
                indexes["glb_manifest"].get(item_id, {}),
                indexes["glb_result"][item_id],
                Jsonb,
                item_id_override=item_id,
                object_key_override=clean_text(item.get("object_key")),
                # delivery URL 取 upload result；驗證階段已確認與 JSON glb_url 相同。
                delivery_url_override=clean_text(
                    indexes["glb_result"][item_id].get("delivery_url")
                )
                or clean_text(item.get("glb_url")),
                default_content_type="model/gltf-binary",
            )
        )
    execute_many(
        cursor,
        asset_statement_prefix + " ON CONFLICT (item_id) WHERE asset_type = 'glb' " + asset_update,
        glb_assets,
        args.page_size,
    )
    official_item_ids = set(indexes["items"])
    image_assets = [
        asset_tuple(
            "image",
            result["image_role"],
            image_id,
            indexes["image_manifest"][image_id],
            result,
            Jsonb,
            default_content_type="image/png",
        )
        for image_id, result in sorted(indexes["image_result"].items())
        if clean_text(result.get("item_id")) in official_item_ids
    ]
    execute_many(
        cursor,
        asset_statement_prefix
        + " ON CONFLICT (item_id, view_role) WHERE asset_type = 'image' "
        + asset_update,
        image_assets,
        args.page_size,
    )

    quality_statement = """
        INSERT INTO roompilot.furniture_quality_issues (
            item_id, issue_type, issue_source, severity, current_value, suggested_value
        ) VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (item_id, issue_type, issue_source) DO UPDATE SET
            severity = EXCLUDED.severity,
            current_value = EXCLUDED.current_value,
            suggested_value = EXCLUDED.suggested_value
    """
    execute_many(
        cursor,
        quality_statement,
        [
            (
                row["item_id"], row["issue_type"], IMPORT_ISSUE_SOURCE, row["severity"],
                Jsonb(row["current_value"]),
                Jsonb(row["suggested_value"]) if row["suggested_value"] is not None else None,
            )
            for row in prepared["quality_issues"]
        ],
        args.page_size,
    )


def verify_counts(
    cursor,
    prepared: dict[str, Any],
    batch_key: str,
    include_staging: bool,
) -> dict[str, int]:
    item_ids = [row["item_id"] for row in prepared["items"]]
    queries = {
        "furniture_items": (
            "SELECT COUNT(*) FROM roompilot.furniture_items WHERE item_id = ANY(%s)",
            (item_ids,),
        ),
        "furniture_styles": (
            "SELECT COUNT(*) FROM roompilot.furniture_styles WHERE item_id = ANY(%s)",
            (item_ids,),
        ),
        "furniture_rooms": (
            "SELECT COUNT(*) FROM roompilot.furniture_rooms WHERE item_id = ANY(%s)",
            (item_ids,),
        ),
        "current_vlm_annotations": (
            "SELECT COUNT(*) FROM roompilot.furniture_vlm_annotations "
            "WHERE item_id = ANY(%s) AND is_current",
            (item_ids,),
        ),
        "furniture_assets": (
            "SELECT COUNT(*) FROM roompilot.furniture_assets WHERE item_id = ANY(%s)",
            (item_ids,),
        ),
        "quality_issues": (
            "SELECT COUNT(*) FROM roompilot.furniture_quality_issues "
            "WHERE item_id = ANY(%s) AND issue_source = %s",
            (item_ids, IMPORT_ISSUE_SOURCE),
        ),
    }
    if include_staging:
        queries.update(
            {
                "stg_catalog": (
                    "SELECT COUNT(*) FROM staging.stg_furniture_catalog WHERE batch_key = %s",
                    (batch_key,),
                ),
                "stg_glb_manifest": (
                    "SELECT COUNT(*) FROM staging.stg_glb_manifest WHERE batch_key = %s",
                    (batch_key,),
                ),
                "stg_glb_result": (
                    "SELECT COUNT(*) FROM staging.stg_glb_upload_result WHERE batch_key = %s",
                    (batch_key,),
                ),
                "stg_image_manifest": (
                    "SELECT COUNT(*) FROM staging.stg_image_manifest WHERE batch_key = %s",
                    (batch_key,),
                ),
                "stg_image_result": (
                    "SELECT COUNT(*) FROM staging.stg_image_upload_result WHERE batch_key = %s",
                    (batch_key,),
                ),
            }
        )
    counts: dict[str, int] = {}
    for label, (statement, parameters) in queries.items():
        cursor.execute(statement, parameters)
        counts[label] = int(cursor.fetchone()[0])
    return counts


def expected_counts(
    prepared: dict[str, Any],
    include_staging: bool,
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]] | None = None,
) -> dict[str, int]:
    counts = {
        "furniture_items": len(prepared["items"]),
        "furniture_styles": len(prepared["style_links"]),
        "furniture_rooms": len(prepared["room_links"]),
        "current_vlm_annotations": len(prepared["annotations"]),
        "furniture_assets": len(prepared["items"]) * 4,
        "quality_issues": len(prepared["quality_issues"]),
    }
    if include_staging:
        glb_manifest_count = (
            len(csv_payloads["glb_manifest"][1]) if csv_payloads else len(prepared["items"])
        )
        glb_result_count = (
            len(csv_payloads["glb_result"][1]) if csv_payloads else len(prepared["items"])
        )
        image_manifest_count = (
            len(csv_payloads["image_manifest"][1])
            if csv_payloads
            else len(prepared["items"]) * 3
        )
        image_result_count = (
            len(csv_payloads["image_result"][1])
            if csv_payloads
            else len(prepared["items"]) * 3
        )
        counts.update(
            {
                "stg_catalog": len(prepared["items"]),
                "stg_glb_manifest": glb_manifest_count,
                "stg_glb_result": glb_result_count,
                "stg_image_manifest": image_manifest_count,
                "stg_image_result": image_result_count,
            }
        )
    return counts


def run_import(
    args: argparse.Namespace,
    items: list[dict[str, Any]],
    csv_payloads: dict[str, tuple[list[str], list[dict[str, str]]]],
    indexes: dict[str, dict[str, dict[str, Any]]],
    prepared: dict[str, Any],
    batch_key: str,
) -> dict[str, int]:
    psycopg = require_psycopg()
    from psycopg2.extras import Json as Jsonb

    if args.create_database:
        created = ensure_database_exists(args.env)
        print("PostgreSQL 資料庫已建立。" if created else "PostgreSQL 資料庫已存在。")

    with psycopg.connect(**db_config(args.env)) as connection:
        with connection.cursor() as cursor:
            if args.replace_existing:
                cursor.execute(RESET_CATALOG_SQL)
            if not args.skip_schema:
                if not args.schema_sql.is_file():
                    raise FileNotFoundError(f"找不到 schema SQL：{args.schema_sql}")
                cursor.execute(args.schema_sql.read_text(encoding="utf-8-sig"))
            if not args.skip_staging:
                import_staging(cursor, args, items, csv_payloads, batch_key, Jsonb)
            import_formal_tables(cursor, args, prepared, indexes, Jsonb)
            counts = verify_counts(
                cursor,
                prepared,
                batch_key,
                include_staging=not args.skip_staging,
            )

            expected = expected_counts(
                prepared,
                include_staging=not args.skip_staging,
                csv_payloads=csv_payloads,
            )
            mismatches = {
                key: {"expected": value, "actual": counts.get(key)}
                for key, value in expected.items()
                if counts.get(key) != value
            }
            if mismatches:
                raise RuntimeError(
                    "匯入後筆數不符，交易已回滾："
                    + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
                )
    return counts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.page_size <= 0:
        raise ValueError("--page-size 必須大於 0。")
    if args.replace_existing and args.skip_schema:
        raise ValueError("--replace-existing 不可與 --skip-schema 同時使用。")

    paths = {
        "catalog": args.catalog,
        "glb_manifest": args.glb_manifest,
        "glb_result": args.glb_upload_result,
        "image_manifest": args.image_manifest,
        "image_result": args.image_upload_result,
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"找不到輸入檔：{path}")

    print("讀取並驗證 5 個官方資料檔……")
    input_hashes = {label: sha256_file(path) for label, path in paths.items()}
    items, metadata = load_catalog(args.catalog)
    csv_payloads = {
        "glb_manifest": load_csv(args.glb_manifest),
        "glb_result": load_csv(args.glb_upload_result),
        "image_manifest": load_csv(args.image_manifest),
        "image_result": load_csv(args.image_upload_result),
    }
    report, indexes = validate_inputs(
        args, items, metadata, csv_payloads, input_hashes
    )
    if report["errors"]:
        if args.validation_report is not None:
            write_report(args.validation_report, report)
        print("資料驗證失敗：", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
        if args.validation_report is not None:
            print(f"驗證報告：{args.validation_report}", file=sys.stderr)
        return 2

    prepared = prepare_rows(items, indexes)
    report["prepared_counts"] = {
        "categories": len(prepared["categories"]),
        "furniture_items": len(prepared["items"]),
        "styles": len(prepared["styles"]),
        "furniture_styles": len(prepared["style_links"]),
        "rooms": len(prepared["rooms"]),
        "furniture_rooms": len(prepared["room_links"]),
        "vlm_annotations": len(prepared["annotations"]),
        "assets": len(prepared["items"]) * 4,
        "quality_issues": len(prepared["quality_issues"]),
    }
    report["quality_issue_counts"] = dict(
        sorted(Counter(row["issue_type"] for row in prepared["quality_issues"]).items())
    )
    if args.validation_report is not None:
        write_report(args.validation_report, report)

    print("資料驗證完成")
    print(f"- 家具：{len(prepared['items']):,}")
    print(f"- 分類／風格／房間：{len(prepared['categories'])}／{len(prepared['styles'])}／{len(prepared['rooms'])}")
    print(f"- GLB／三視角圖片：{len(prepared['items']):,}／{len(prepared['items']) * 3:,}")
    print(f"- VLM 標註：{len(prepared['annotations']):,}")
    print(f"- 品質問題：{len(prepared['quality_issues']):,}")
    if args.validation_report is not None:
        print(f"- 驗證報告：{args.validation_report}")

    if args.dry_run:
        print("Dry Run 完成；未連線 PostgreSQL，也未寫入資料庫。")
        return 0

    counts = run_import(
        args,
        items,
        csv_payloads,
        indexes,
        prepared,
        report["batch_key"],
    )
    report["post_import_counts"] = counts
    report["imported_at"] = datetime.now(timezone.utc).isoformat()
    if args.validation_report is not None:
        write_report(args.validation_report, report)
    print("PostgreSQL 匯入完成；所有正式表與 staging 筆數均已核對。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # 最外層只輸出可操作的錯誤，不吞掉非零 exit code。
        print(f"匯入失敗：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
