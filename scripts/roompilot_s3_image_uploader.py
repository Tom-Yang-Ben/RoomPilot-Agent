#!/usr/bin/env python3
"""依 CSV manifest 安全地將 RoomPilot PNG 圖片上傳到 Amazon S3。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import roompilot_s3_glb_uploader as base


REQUIRED_COLUMNS = {
    "image_id",
    "item_id",
    "source",
    "image_role",
    "original_image_path",
    "object_key",
    "file_size_bytes",
    "validation_status",
    "upload_status",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="依 CSV manifest 上傳 PNG 圖片到 S3，並將結果與 URL 寫入新 CSV。"
    )
    parser.add_argument("--manifest", required=True, help="來源 manifest CSV 路徑。")
    parser.add_argument("--project-root", required=True, help="本機專案根目錄。")
    parser.add_argument("--bucket", required=True, help="目標 S3 Bucket 名稱。")
    parser.add_argument("--region", required=True, help="AWS Region，例如 ap-east-2。")
    parser.add_argument("--sources", nargs="+", required=True, help="要處理的 source。")
    parser.add_argument("--output", help="結果 CSV 路徑；未填時建立在 manifest 旁。")
    parser.add_argument("--profile", default=None, help="AWS Profile 名稱。")
    parser.add_argument(
        "--required-prefix", default="images/", help="object_key 必須使用的開頭。"
    )
    parser.add_argument("--delivery-base-url", default=None, help="CloudFront 基底網址。")
    parser.add_argument("--presign-seconds", type=int, default=0)
    parser.add_argument("--cache-control", default="public, max-age=86400")
    parser.add_argument("--limit", type=int, help="只處理前 N 筆。")
    parser.add_argument("--checkpoint-every", type=int, default=50)
    parser.add_argument("--multipart-threshold-mib", type=int, default=64)
    parser.add_argument("--multipart-chunk-mib", type=int, default=64)
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def validate_manifest(
    rows: list[dict[str, str]],
    project_root: Path,
    selected_sources: set[str],
    required_prefix: str,
) -> tuple[list[int], list[str]]:
    if not rows:
        return [], ["Manifest 沒有任何資料。"]

    missing_columns = REQUIRED_COLUMNS - set(rows[0])
    if missing_columns:
        return [], [f"Manifest 缺少欄位：{', '.join(sorted(missing_columns))}"]

    selected_indices: list[int] = []
    errors: list[str] = []
    seen_keys: set[str] = set()
    seen_image_ids: set[str] = set()
    allowed_roles = {"front", "side", "angle-45"}

    for index, row in enumerate(rows):
        source = base.clean_text(row.get("source")).lower()
        if source not in selected_sources:
            continue

        selected_indices.append(index)
        image_id = base.clean_text(row.get("image_id")) or f"CSV 第 {index + 2} 列"
        object_key = base.clean_text(row.get("object_key"))
        original_path = base.clean_text(row.get("original_image_path"))
        validation_status = base.clean_text(row.get("validation_status")).lower()
        content_type = base.clean_text(row.get("content_type"))
        image_role = base.clean_text(row.get("image_role")).lower()

        if image_id in seen_image_ids:
            errors.append(f"{image_id}：image_id 重複。")
        seen_image_ids.add(image_id)
        if validation_status != "ready":
            errors.append(f"{image_id}：validation_status 必須是 ready。")
        if image_role not in allowed_roles:
            errors.append(f"{image_id}：不支援的 image_role：{image_role}")
        if not object_key:
            errors.append(f"{image_id}：object_key 是空白。")
        elif required_prefix and not object_key.startswith(required_prefix):
            errors.append(f"{image_id}：object_key 必須以 {required_prefix!r} 開頭。")
        elif object_key in seen_keys:
            errors.append(f"{image_id}：object_key 重複：{object_key}")
        seen_keys.add(object_key)

        if not original_path:
            errors.append(f"{image_id}：original_image_path 是空白。")
            continue

        local_path = base.resolve_local_path(project_root, original_path)
        if not local_path.is_file():
            errors.append(f"{image_id}：找不到本機檔案：{local_path}")
            continue
        if local_path.suffix.lower() != ".png":
            errors.append(f"{image_id}：檔案不是 .png：{local_path}")
        if content_type and content_type != "image/png":
            errors.append(f"{image_id}：content_type 應為 image/png。")

        actual_size = local_path.stat().st_size
        expected_size = base.parse_int(row.get("file_size_bytes"), -1)
        if expected_size >= 0 and actual_size != expected_size:
            errors.append(
                f"{image_id}：本機大小 {actual_size} 與 Manifest {expected_size} 不同。"
            )
        row["file_size_bytes"] = str(actual_size)

    return selected_indices, errors


def upload_one_file(row, args, project_root, s3, transfer_config) -> str:
    image_id = base.clean_text(row.get("image_id"))
    item_id = base.clean_text(row.get("item_id"))
    source = base.clean_text(row.get("source")).lower()
    image_role = base.clean_text(row.get("image_role")).lower()
    object_key = base.clean_text(row.get("object_key"))
    local_path = base.resolve_local_path(
        project_root, base.clean_text(row.get("original_image_path"))
    )
    local_size = local_path.stat().st_size
    row["upload_error"] = ""

    existing = base.find_s3_object(s3, args.bucket, object_key)
    if existing is not None:
        remote_size = base.parse_int(existing.get("ContentLength"), -1)
        if remote_size == local_size:
            row["upload_status"] = "already_exists"
            base.fill_s3_result(row, args, object_key, existing)
            base.fill_presigned_url(row, s3, args.bucket, object_key, args.presign_seconds)
            print("    略過：S3 已有相同大小的檔案")
            return "already_exists"
        if not args.force:
            row["upload_status"] = "conflict_size_mismatch"
            row["upload_error"] = (
                f"S3 檔案為 {remote_size} bytes，本機為 {local_size} bytes；"
                "確認後才能使用 --force 覆蓋。"
            )
            print(f"    衝突：{row['upload_error']}")
            return "conflict_size_mismatch"
        print(f"    覆蓋：S3 {remote_size} bytes → 本機 {local_size} bytes (--force)")

    extra_args = {
        "ContentType": "image/png",
        "CacheControl": args.cache_control,
        "Metadata": {
            "image-id": base.safe_metadata(image_id),
            "item-id": base.safe_metadata(item_id),
            "source": base.safe_metadata(source),
            "image-role": base.safe_metadata(image_role),
        },
    }
    s3.upload_file(
        str(local_path), args.bucket, object_key, ExtraArgs=extra_args, Config=transfer_config
    )
    uploaded_info = s3.head_object(Bucket=args.bucket, Key=object_key)
    remote_size = base.parse_int(uploaded_info.get("ContentLength"), -1)
    if remote_size != local_size:
        raise RuntimeError(f"上傳後大小不符：本機={local_size}，S3={remote_size}")

    from datetime import datetime, timezone

    row["upload_status"] = "uploaded"
    row["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    base.fill_s3_result(row, args, object_key, uploaded_info)
    base.fill_presigned_url(row, s3, args.bucket, object_key, args.presign_seconds)
    print(f"    完成：{local_size:,} bytes")
    return "uploaded"


def main() -> None:
    base.REQUIRED_COLUMNS = REQUIRED_COLUMNS
    base.validate_manifest = validate_manifest
    base.upload_one_file = upload_one_file
    try:
        exit_code = base.run(parse_args())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"錯誤：{exc}")
        exit_code = 2
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
