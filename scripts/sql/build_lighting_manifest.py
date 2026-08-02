"""產生 `backend/catalog/data/manifests/lighting_assets_manifest.csv`。

2026-07-30 的型錄切換（`furniture_official_catagory.json` 的 `removed_lighting_*`）
把 793 筆燈具記錄從 items 移除，但沒有補上契約說好的 lighting manifest，於是那批
資產卡在半路：GLB 與三視角圖都已上傳 CloudFront，產品卻拿不到。

這支腳本從三個現存來源把那批記錄重建成契約要求的交付清單：

  backend/catalog/data/manifests/glb_upload_all_result.csv    交付網址、object_key、etag
  backend/catalog/data/manifests/image_upload_all_result.csv  三視角圖交付網址
  backend/catalog/data/furniture_catalog_cloud_9350.json      品名、分類、尺寸
  rag/vlm_annotation/annotations_full.jsonl                   VLM 描述與風格

「被移除的那批」定義為兩份 GLB manifest 的差集：舊那份有、`JSON/` 那份沒有。

checksum 用 S3 ETag——manifest 的 sha256 欄整批是空的，實測 793 筆都有 etag。
單段上傳的 ETag 即 MD5，作為交付憑據足夠，欄位另記 checksum_algo 以免誤讀成 SHA。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.catalog.lighting_classification import (  # noqa: E402
    classify_lighting_type,
    is_contract_fixture,
)

DEFAULT_CURRENT_GLB = PROJECT_ROOT / "JSON/manifests/glb_upload_all_result.csv"
DEFAULT_FULL_GLB = (
    PROJECT_ROOT / "backend/catalog/data/manifests/glb_upload_all_result.csv"
)
DEFAULT_FULL_IMAGE = (
    PROJECT_ROOT / "backend/catalog/data/manifests/image_upload_all_result.csv"
)
DEFAULT_CATALOG = (
    PROJECT_ROOT / "backend/catalog/data/furniture_catalog_cloud_9350.json"
)
DEFAULT_ANNOTATIONS = PROJECT_ROOT / "rag/vlm_annotation/annotations_full.jsonl"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "backend/catalog/data/manifests/lighting_assets_manifest.csv"
)

MANIFEST_VERSION = "1.0"
FIELDNAMES = (
    "manifest_version",
    "item_id",
    "lighting_type",
    "classification_basis",
    "verification_status",
    "source",
    "source_group",
    "catalog",
    "canonical_category_zh",
    "name_en",
    "name_zh",
    "width_cm",
    "depth_cm",
    "height_cm",
    "glb_url",
    "thumbnail_url",
    "image_url_side",
    "image_url_angle_45",
    "object_key",
    "checksum",
    "checksum_algo",
    "license",
    "style_primary",
    "style_secondary",
)

# ABO 與 IKEA 兩批都是型錄自帶授權，契約列舉是 CC0|catalog-origin。
_LICENSE_BY_SOURCE = {"ikea": "catalog-origin", "abo": "catalog-origin"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                obj = json.loads(line)
                records[str(obj["id"])] = obj
    return records


def _number(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def build_rows(
    current_glb: Path,
    full_glb: Path,
    full_image: Path,
    catalog_path: Path,
    annotations_path: Path,
) -> list[dict[str, str]]:
    current_ids = {row["item_id"] for row in _read_csv(current_glb)}
    stripped = [row for row in _read_csv(full_glb) if row["item_id"] not in current_ids]
    if not stripped:
        raise SystemExit("兩份 GLB manifest 沒有差集，沒有需要重建的燈具記錄。")

    images: dict[str, dict[str, str]] = {}
    for row in _read_csv(full_image):
        url = (row.get("delivery_url") or "").strip()
        if url:
            images.setdefault(row["item_id"], {})[row.get("image_role", "")] = url

    catalog = {
        str(item["id"]): item
        for item in json.loads(catalog_path.read_text(encoding="utf-8"))["items"]
    }
    annotations = _read_jsonl(annotations_path)

    rows: list[dict[str, str]] = []
    for row in stripped:
        item_id = row["item_id"]
        item = catalog.get(item_id, {})
        note = annotations.get(item_id, {})
        lighting_type, basis = classify_lighting_type(
            item.get("canonical_category_zh"),
            note.get("description"),
            f"{item.get('name_zh', '')} {item.get('name_en', '')}",
        )
        views = images.get(item_id, {})
        source = (row.get("source") or "").strip()
        rows.append(
            {
                "manifest_version": MANIFEST_VERSION,
                "item_id": item_id,
                "lighting_type": lighting_type,
                "classification_basis": basis,
                # 契約：verification_status != verified 不得進 RAG 或第 6 步自動配置。
                "verification_status": (
                    "verified" if is_contract_fixture(lighting_type) else "needs_review"
                ),
                "source": source,
                "source_group": row.get("source_group", ""),
                "catalog": row.get("catalog", ""),
                "canonical_category_zh": item.get("canonical_category_zh", ""),
                "name_en": row.get("name_en") or item.get("name_en", ""),
                "name_zh": item.get("name_zh", ""),
                "width_cm": _number(item.get("width_cm")),
                "depth_cm": _number(item.get("depth_cm")),
                "height_cm": _number(item.get("height_cm")),
                "glb_url": (row.get("delivery_url") or "").strip(),
                "thumbnail_url": views.get("front", ""),
                "image_url_side": views.get("side", ""),
                "image_url_angle_45": views.get("angle-45", ""),
                "object_key": (row.get("object_key") or "").strip(),
                "checksum": (row.get("s3_etag") or "").strip(),
                "checksum_algo": "s3-etag",
                "license": _LICENSE_BY_SOURCE.get(source, "catalog-origin"),
                "style_primary": note.get("style_primary", "") or "",
                "style_secondary": note.get("style_secondary", "") or "",
            }
        )
    rows.sort(key=lambda entry: entry["item_id"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-glb", type=Path, default=DEFAULT_CURRENT_GLB)
    parser.add_argument("--full-glb", type=Path, default=DEFAULT_FULL_GLB)
    parser.add_argument("--full-image", type=Path, default=DEFAULT_FULL_IMAGE)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="只印統計，不寫檔。")
    args = parser.parse_args()

    rows = build_rows(
        args.current_glb, args.full_glb, args.full_image, args.catalog, args.annotations
    )

    counts = Counter(row["lighting_type"] for row in rows)
    fixtures = sum(1 for row in rows if row["verification_status"] == "verified")
    print(f"重建燈具記錄：{len(rows)} 筆")
    for lighting_type, count in counts.most_common():
        mark = "" if is_contract_fixture(lighting_type) else "   ← 待人工分流"
        print(f"  {lighting_type:<24} {count:>4}{mark}")
    print(f"\nverified（可交付燈具本體）：{fixtures}")
    print(f"needs_review：{len(rows) - fixtures}")

    missing_glb = [row["item_id"] for row in rows if not row["glb_url"]]
    missing_thumb = [row["item_id"] for row in rows if not row["thumbnail_url"]]
    missing_style = [row["item_id"] for row in rows if not row["style_primary"]]
    print(f"\n缺 glb_url：{len(missing_glb)}")
    print(f"缺 thumbnail_url：{len(missing_thumb)}")
    print(f"缺 style_primary：{len(missing_style)}")

    if args.dry_run:
        print("\n--dry-run：未寫檔。")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDNAMES))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n已寫出：{args.output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
