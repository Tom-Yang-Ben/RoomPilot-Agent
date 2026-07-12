#!/usr/bin/env python
"""
RoomPilot GLB Manifest Generator

用途：
1. 遞迴讀取 *.normalized.json 主資料。
2. 依 glb_path 檢查本機 GLB 是否存在。
3. 產生 S3 object_key。
4. 輸出 glb_upload_manifest.csv 與驗證報告 JSON。

此程式只讀取檔案，不會移動、重新命名或上傳 GLB。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_VERSION = "1.0"
CONTENT_TYPE = "model/gltf-binary"

MANIFEST_FIELDS = [
    "manifest_version",
    "item_id",
    "source",
    "source_group",
    "catalog",
    "kind",
    "type",
    "name_en",
    "original_glb_path",
    "local_file_exists",
    "file_size_bytes",
    "sha256",
    "upload_filename",
    "object_key",
    "content_type",
    "validation_status",
    "validation_message",
    "upload_status",
    "s3_etag",
    "uploaded_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根據 RoomPilot normalized JSON 產生 GLB 上傳 Manifest。"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help=(
            "專案根目錄。JSON 的 glb_path 會相對於此資料夾解析；"
            "通常是包含 downloaded-files/ 的 ROOMPILOT-AGENT 資料夾。"
        ),
    )
    parser.add_argument(
        "--json-root",
        type=Path,
        default=Path("JSON"),
        help="包含 *.normalized.json 的資料夾；程式會遞迴尋找。",
    )
    parser.add_argument(
    "--output",
    type=Path,
    default=Path("dataset/catalog_json/manifests/glb_upload_manifest.csv"),
    help="Manifest CSV 輸出位置。",
)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="驗證報告 JSON。未指定時會放在 Manifest 同資料夾。",
    )
    parser.add_argument(
        "--s3-prefix",
        default="models",
        help="S3 object key 的最上層前綴，預設 models。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只處理前 N 筆，適合先做抽樣測試。",
    )
    parser.add_argument(
        "--calculate-sha256",
        action="store_true",
        help=(
            "計算每個 GLB 的 SHA-256。150GB 資料會增加大量讀取時間，"
            "第一次建立 Manifest 不建議開啟。"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="只要有 missing／invalid／empty_file 就以非 0 狀態結束。",
    )
    return parser.parse_args()


def slugify(value: Any, fallback: str = "unknown") -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return fallback

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or fallback


def detect_source(item: dict[str, Any]) -> str:
    catalog = str(item.get("catalog", "")).lower()

    if item.get("is_ikea") is True or catalog.startswith("ikea"):
        return "ikea"
    if catalog.startswith("abo"):
        return "abo"
    if catalog.startswith("sketchfab"):
        return "sf"

    return slugify(item.get("source_group"), fallback="unknown")


def find_catalog_files(json_root: Path) -> list[Path]:
    files = sorted(json_root.rglob("*.normalized.json"))
    if not files:
        raise FileNotFoundError(
            f"找不到 *.normalized.json：{json_root.resolve()}"
        )
    return files


def load_items(json_files: Iterable[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_items: list[dict[str, Any]] = []
    catalog_checks: list[dict[str, Any]] = []

    for path in json_files:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        items = payload.get("items")
        if not isinstance(items, list):
            # 避免誤讀規則檔。
            continue

        declared_count = payload.get("count")
        catalog_checks.append(
            {
                "file": str(path),
                "catalog": payload.get("source_catalog", path.stem),
                "declared_count": declared_count,
                "actual_count": len(items),
                "count_matches": declared_count == len(items),
            }
        )

        all_items.extend(items)

    if not all_items:
        raise ValueError("找到 JSON 檔，但沒有讀到任何 items 陣列。")

    return all_items, catalog_checks


def resolve_local_path(project_root: Path, glb_path: str) -> Path:
    """
    glb_path 在 JSON 中統一使用 /。
    利用 PurePosixPath.parts 轉成本機 Windows／Linux 都能使用的 Path。
    """
    normalized = glb_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    return project_root.joinpath(*parts)


def calculate_sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def create_row(
    item: dict[str, Any],
    project_root: Path,
    s3_prefix: str,
    include_sha256: bool,
) -> dict[str, Any]:
    item_id = str(item.get("id", "")).strip()
    glb_path = str(item.get("glb_path", "")).strip().replace("\\", "/")
    source = detect_source(item)
    kind = slugify(item.get("kind"), fallback="unknown")
    item_type = slugify(item.get("type"), fallback="unknown")

    upload_filename = f"{item_id}.glb" if item_id else ""
    prefix = s3_prefix.strip("/")
    # object_key 不放 type/category，因為這些分類欄位未來可能修改。
    # source、kind、id 才是較穩定的雲端路徑組成。
    object_key = (
        f"{prefix}/{source}/{kind}/{upload_filename}"
        if prefix
        else f"{source}/{kind}/{upload_filename}"
    )

    messages: list[str] = []
    structural_error = False

    if not item_id:
        messages.append("缺少 id")
        structural_error = True
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", item_id):
        messages.append("id 含有非安全字元")
        structural_error = True

    if not glb_path:
        messages.append("缺少 glb_path")
        structural_error = True
        local_path = project_root
    else:
        posix_path = PurePosixPath(glb_path)
        if posix_path.is_absolute() or ".." in posix_path.parts:
            messages.append("glb_path 不是安全的相對路徑")
            structural_error = True

        if posix_path.suffix.lower() != ".glb":
            messages.append("glb_path 副檔名不是 .glb")
            structural_error = True

        if item_id and posix_path.name != upload_filename:
            messages.append("glb_path 檔名不等於 id.glb")
            structural_error = True

        local_path = resolve_local_path(project_root, glb_path)

    file_exists = local_path.is_file() if glb_path else False
    file_size = local_path.stat().st_size if file_exists else ""
    sha256 = ""

    if structural_error:
        validation_status = "invalid"
        upload_status = "blocked"
    elif not file_exists:
        validation_status = "missing"
        upload_status = "blocked"
        messages.append("本機找不到 GLB")
    elif file_size == 0:
        validation_status = "empty_file"
        upload_status = "blocked"
        messages.append("GLB 檔案大小為 0")
    else:
        validation_status = "ready"
        upload_status = "pending"
        if include_sha256:
            sha256 = calculate_sha256(local_path)

    return {
        "manifest_version": MANIFEST_VERSION,
        "item_id": item_id,
        "source": source,
        "source_group": item.get("source_group", ""),
        "catalog": item.get("catalog", ""),
        "kind": item.get("kind", ""),
        "type": item.get("type", ""),
        "name_en": item.get("name_en", ""),
        "original_glb_path": glb_path,
        "local_file_exists": str(file_exists).lower(),
        "file_size_bytes": file_size,
        "sha256": sha256,
        "upload_filename": upload_filename,
        "object_key": object_key,
        "content_type": CONTENT_TYPE,
        "validation_status": validation_status,
        "validation_message": "；".join(messages),
        "upload_status": upload_status,
        "s3_etag": "",
        "uploaded_at": "",
    }


def mark_duplicate_rows(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    duplicate_map: dict[str, list[str]] = {}

    for field in ("item_id", "original_glb_path", "object_key"):
        values = [str(row[field]) for row in rows if row[field]]
        duplicates = sorted(
            value for value, count in Counter(values).items() if count > 1
        )
        duplicate_map[field] = duplicates

        if not duplicates:
            continue

        duplicate_set = set(duplicates)
        for row in rows:
            if str(row[field]) in duplicate_set:
                row["validation_status"] = "invalid"
                row["upload_status"] = "blocked"
                message = f"{field} 重複"
                current = str(row["validation_message"])
                row["validation_message"] = (
                    f"{current}；{message}" if current else message
                )

    return duplicate_map


def write_csv(output: Path, rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_report(
    rows: list[dict[str, Any]],
    catalog_checks: list[dict[str, Any]],
    duplicate_map: dict[str, list[str]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    status_counts = Counter(row["validation_status"] for row in rows)
    source_counts = Counter(row["source"] for row in rows)
    catalog_counts = Counter(row["catalog"] for row in rows)

    ready_bytes = sum(
        int(row["file_size_bytes"])
        for row in rows
        if row["validation_status"] == "ready"
        and row["file_size_bytes"] != ""
    )

    error_examples = defaultdict(list)
    for row in rows:
        status = row["validation_status"]
        if status != "ready" and len(error_examples[status]) < 20:
            error_examples[status].append(
                {
                    "item_id": row["item_id"],
                    "glb_path": row["original_glb_path"],
                    "message": row["validation_message"],
                }
            )

    return {
        "manifest_version": MANIFEST_VERSION,
        "project_root": str(args.project_root.resolve()),
        "json_root": str(args.json_root.resolve()),
        "output": str(args.output.resolve()),
        "s3_prefix": args.s3_prefix.strip("/"),
        "calculate_sha256": args.calculate_sha256,
        "total_rows": len(rows),
        "validation_status_counts": dict(status_counts),
        "source_counts": dict(source_counts),
        "catalog_counts": dict(catalog_counts),
        "ready_file_size_bytes": ready_bytes,
        "duplicate_counts": {
            field: len(values) for field, values in duplicate_map.items()
        },
        "catalog_checks": catalog_checks,
        "error_examples": dict(error_examples),
    }


def main() -> int:
    args = parse_args()

    project_root = args.project_root.resolve()
    json_root = args.json_root.resolve()

    if not project_root.is_dir():
        print(f"[錯誤] project-root 不存在：{project_root}", file=sys.stderr)
        return 2
    if not json_root.is_dir():
        print(f"[錯誤] json-root 不存在：{json_root}", file=sys.stderr)
        return 2

    try:
        json_files = find_catalog_files(json_root)
        items, catalog_checks = load_items(json_files)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[錯誤] {exc}", file=sys.stderr)
        return 2

    if args.limit is not None:
        if args.limit <= 0:
            print("[錯誤] --limit 必須大於 0。", file=sys.stderr)
            return 2
        items = items[: args.limit]

    rows = [
        create_row(
            item=item,
            project_root=project_root,
            s3_prefix=args.s3_prefix,
            include_sha256=args.calculate_sha256,
        )
        for item in items
    ]

    duplicate_map = mark_duplicate_rows(rows)
    write_csv(args.output, rows)

    report_path = (
        args.report
        if args.report is not None
        else args.output.with_name(f"{args.output.stem}_report.json")
    )
    report = build_report(rows, catalog_checks, duplicate_map, args)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = Counter(row["validation_status"] for row in rows)

    print("=" * 60)
    print("RoomPilot GLB Manifest 建立完成")
    print("=" * 60)
    print(f"總筆數       ：{len(rows):,}")
    print(f"ready        ：{counts.get('ready', 0):,}")
    print(f"missing      ：{counts.get('missing', 0):,}")
    print(f"invalid      ：{counts.get('invalid', 0):,}")
    print(f"empty_file   ：{counts.get('empty_file', 0):,}")
    print(f"Manifest     ：{args.output.resolve()}")
    print(f"驗證報告     ：{report_path.resolve()}")

    has_blocking_errors = any(
        row["validation_status"] != "ready" for row in rows
    )
    if args.strict and has_blocking_errors:
        print("[失敗] strict 模式發現阻擋問題。", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
