#!/usr/bin/env python3
r"""RoomPilot S3 GLB uploader：依照 CSV Manifest 上傳模型到 Amazon S3。

這支程式預設只做本機檢查，不會連線或修改 AWS。
確認檢查結果正確後，必須加上 ``--execute`` 才會真的上傳。

常用範例（PowerShell）：
python .\scripts\roompilot_s3_glb_uploader.py `
  --manifest "D:\RoomPilot-Agent\backend\catalog\data\manifests\glb_upload_manifest.csv" `
  --output "D:\RoomPilot-Agent\.runtime\catalog-uploads\glb_upload_results.csv" `
  --project-root "D:\RoomPilot-Agent" `
  --bucket "roompilot-furniture-glb-prod-825555019055-ap-east-2-an" `
  --region "ap-east-2" `
  --profile "roompilot-s3-uploader" `
  --sources ikea sf `
  --execute

安全設計：
1. 沒有 --execute 時只做 Dry Run。
2. 原始 Manifest 永遠不會被覆蓋。
3. S3 已有同大小檔案時會自動略過。
4. S3 同名檔案大小不同時，除非加上 --force，否則不會覆蓋。
5. 上傳進度會定期寫入結果 CSV，可用 --resume 繼續。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote


# -----------------------------------------------------------------------------
# 固定設定
# -----------------------------------------------------------------------------

# Manifest 至少要有這些欄位，程式才知道要上傳哪一個檔案。
REQUIRED_COLUMNS = {
    "item_id",
    "source",
    "original_glb_path",
    "object_key",
    "file_size_bytes",
    "validation_status",
    "upload_status",
}

# 上傳後會寫入結果 CSV 的欄位。
RESULT_COLUMNS = [
    "s3_uri",
    "s3_https_url",
    "delivery_url",
    "delivery_url_type",
    "temporary_presigned_url",
    "presigned_expires_at",
    "s3_etag",
    "s3_version_id",
    "s3_last_modified",
    "uploaded_at",
    "upload_error",
]

# 使用 --resume 時，這兩種狀態視為已完成，不會重複處理。
SUCCESS_STATUSES = {"uploaded", "already_exists"}

# Presigned URL 最長允許 7 天。
MAX_PRESIGN_SECONDS = 7 * 24 * 60 * 60


# -----------------------------------------------------------------------------
# 1. 讀取命令列參數
# -----------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """建立命令列參數，並回傳使用者輸入的設定。"""
    parser = argparse.ArgumentParser(
        description="依照 CSV Manifest 上傳 GLB 到 S3，並把結果與 URL 寫入新 CSV。"
    )

    # 必填：本機檔案與 AWS 位置。
    parser.add_argument("--manifest", required=True, help="來源 Manifest CSV 路徑。")
    parser.add_argument("--project-root", required=True, help="本機專案根目錄。")
    parser.add_argument("--bucket", required=True, help="目標 S3 Bucket 名稱。")
    parser.add_argument("--region", required=True, help="AWS Region，例如 ap-east-2。")
    parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="要處理的 source，例如：--sources ikea sf",
    )

    # 選填：輸出位置與 AWS Profile。
    parser.add_argument(
        "--output",
        help="結果 CSV 路徑；未填時會建立在 Manifest 旁邊。",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS Profile 名稱，例如 roompilot-s3-uploader。",
    )

    # 選填：URL 與 S3 物件設定。
    parser.add_argument(
        "--required-prefix",
        default="models/",
        help="object_key 必須使用的開頭，預設為 models/。",
    )
    parser.add_argument(
        "--delivery-base-url",
        default=None,
        help="CloudFront 網址，例如 https://example.cloudfront.net。",
    )
    parser.add_argument(
        "--presign-seconds",
        type=int,
        default=0,
        help="建立臨時下載網址的有效秒數；0 代表不建立。",
    )
    parser.add_argument(
        "--cache-control",
        default="public, max-age=86400",
        help="S3 Cache-Control，預設為 public, max-age=86400。",
    )

    # 選填：測試、續傳與效能設定。
    parser.add_argument("--limit", type=int, help="只處理前 N 筆，適合先測試 5 筆。")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
        help="每處理 N 筆儲存一次結果，預設為 10。",
    )
    parser.add_argument(
        "--multipart-threshold-mib",
        type=int,
        default=64,
        help="檔案達到幾 MiB 時使用分段上傳，預設為 64。",
    )
    parser.add_argument(
        "--multipart-chunk-mib",
        type=int,
        default=64,
        help="每個分段的大小（MiB），預設為 64。",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=4,
        help="單一檔案的同時上傳數，預設為 4。",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="從既有結果 CSV 繼續，略過已成功的項目。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允許覆蓋 S3 上同名但大小不同的檔案，請謹慎使用。",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="真的連線並上傳；未加此參數時只做 Dry Run。",
    )

    return parser.parse_args()


# -----------------------------------------------------------------------------
# 2. 一般小工具：文字、數字、路徑與 CSV
# -----------------------------------------------------------------------------

def clean_text(value: object) -> str:
    """把 CSV 或 AWS 回傳值安全地轉成去除頭尾空白的文字。"""
    return "" if value is None else str(value).strip()


def parse_int(value: object, default: int = 0) -> int:
    """把 CSV 數值轉成整數；無法轉換時使用預設值。"""
    try:
        return int(float(clean_text(value)))
    except (TypeError, ValueError):
        return default


def resolve_local_path(project_root: Path, file_path: str) -> Path:
    """相對路徑以 project_root 為起點；絕對路徑則直接使用。"""
    path = Path(file_path)
    return path if path.is_absolute() else project_root / path


def read_manifest(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """讀取 UTF-8 CSV，回傳所有資料列與原始欄位順序。"""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError("Manifest 沒有標題列。")
        return [dict(row) for row in reader], list(reader.fieldnames)


def add_result_columns(fieldnames: list[str]) -> list[str]:
    """保留原欄位順序，並在最後補上尚未存在的結果欄位。"""
    result = list(fieldnames)
    for column in RESULT_COLUMNS:
        if column not in result:
            result.append(column)
    return result


def write_csv_safely(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
) -> None:
    """先寫入暫存檔，再取代正式檔，避免中斷時留下半份 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_number, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(file_number, "w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, path)
    except Exception:
        # 寫入失敗時刪除暫存檔，但保留原本的正式結果檔。
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


# -----------------------------------------------------------------------------
# 3. 上傳前檢查
# -----------------------------------------------------------------------------

def get_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """整理 Manifest、輸出 CSV、專案根目錄的絕對路徑。"""
    manifest_path = Path(args.manifest).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()

    # 沒指定 --output 時，自動在 Manifest 旁建立 *_upload_results.csv。
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = manifest_path.with_name(f"{manifest_path.stem}_upload_results.csv")

    return manifest_path, output_path, project_root


def validate_settings(
    args: argparse.Namespace,
    manifest_path: Path,
    output_path: Path,
    project_root: Path,
) -> list[str]:
    """檢查命令列設定；回傳所有錯誤，空清單代表通過。"""
    errors: list[str] = []

    if output_path == manifest_path:
        errors.append("--output 不可和 --manifest 相同，以免覆蓋原始資料。")
    if not manifest_path.is_file():
        errors.append(f"找不到 Manifest：{manifest_path}")
    if not project_root.is_dir():
        errors.append(f"找不到專案根目錄：{project_root}")
    if not 0 <= args.presign_seconds <= MAX_PRESIGN_SECONDS:
        errors.append(f"--presign-seconds 必須介於 0 和 {MAX_PRESIGN_SECONDS}。")
    if args.limit is not None and args.limit <= 0:
        errors.append("--limit 必須大於 0。")
    if args.checkpoint_every <= 0:
        errors.append("--checkpoint-every 必須大於 0。")
    if args.multipart_threshold_mib <= 0 or args.multipart_chunk_mib <= 0:
        errors.append("分段上傳大小必須大於 0 MiB。")
    if args.max_concurrency <= 0:
        errors.append("--max-concurrency 必須大於 0。")

    # 續傳時一定要有既有結果；正式新上傳則不覆蓋舊結果。
    if args.resume and not output_path.is_file():
        errors.append(f"使用 --resume，但找不到結果 CSV：{output_path}")
    if not args.resume and args.execute and output_path.exists():
        errors.append(
            f"結果 CSV 已存在：{output_path}。請改用 --resume，或指定新的 --output。"
        )

    return errors


def validate_manifest(
    rows: list[dict[str, str]],
    project_root: Path,
    selected_sources: set[str],
    required_prefix: str,
) -> tuple[list[int], list[str]]:
    """找出要處理的資料列，並檢查每個本機 GLB 與 object_key。"""
    if not rows:
        return [], ["Manifest 沒有任何資料。"]

    missing_columns = REQUIRED_COLUMNS - set(rows[0])
    if missing_columns:
        names = ", ".join(sorted(missing_columns))
        return [], [f"Manifest 缺少欄位：{names}"]

    selected_indices: list[int] = []
    errors: list[str] = []
    seen_keys: set[str] = set()

    for index, row in enumerate(rows):
        source = clean_text(row.get("source")).lower()
        if source not in selected_sources:
            continue

        selected_indices.append(index)
        item_id = clean_text(row.get("item_id")) or f"CSV 第 {index + 2} 列"
        object_key = clean_text(row.get("object_key"))
        original_path = clean_text(row.get("original_glb_path"))
        validation_status = clean_text(row.get("validation_status")).lower()
        content_type = clean_text(row.get("content_type"))

        # 先確認 Manifest 內容符合上傳條件。
        if validation_status != "ready":
            errors.append(f"{item_id}：validation_status 必須是 ready。")
        if not object_key:
            errors.append(f"{item_id}：object_key 是空白。")
        elif required_prefix and not object_key.startswith(required_prefix):
            errors.append(f"{item_id}：object_key 必須以 {required_prefix!r} 開頭。")
        elif object_key in seen_keys:
            errors.append(f"{item_id}：object_key 重複：{object_key}")
        seen_keys.add(object_key)

        # 再確認本機檔案存在、大小正確，而且副檔名是 .glb。
        if not original_path:
            errors.append(f"{item_id}：original_glb_path 是空白。")
            continue

        local_path = resolve_local_path(project_root, original_path)
        if not local_path.is_file():
            errors.append(f"{item_id}：找不到本機檔案：{local_path}")
            continue

        expected_size = parse_int(row.get("file_size_bytes"), -1)
        actual_size = local_path.stat().st_size
        if expected_size >= 0 and actual_size != expected_size:
            errors.append(
                f"{item_id}：本機大小 {actual_size} 與 Manifest {expected_size} 不同。"
            )
        if local_path.suffix.lower() != ".glb":
            errors.append(f"{item_id}：檔案不是 .glb：{local_path}")
        if content_type and content_type != "model/gltf-binary":
            errors.append(f"{item_id}：content_type 應為 model/gltf-binary。")

    return selected_indices, errors


def print_errors(title: str, errors: list[str], maximum: int = 30) -> None:
    """顯示錯誤摘要，避免一次輸出過多內容。"""
    print(f"錯誤：{title}，共 {len(errors):,} 項。")
    for message in errors[:maximum]:
        print(f"  - {message}")
    if len(errors) > maximum:
        print(f"  ...另有 {len(errors) - maximum:,} 項")


def print_plan(
    rows: list[dict[str, str]],
    selected_indices: list[int],
    sources: list[str],
    output_path: Path,
    execute: bool,
) -> None:
    """列出即將處理的數量、容量與前五個 S3 object_key。"""
    total_bytes = sum(
        parse_int(rows[index].get("file_size_bytes")) for index in selected_indices
    )
    source_counts = Counter(
        clean_text(rows[index].get("source")).lower() for index in selected_indices
    )

    print("\n=== 上傳前摘要 ===")
    print(f"來源              ：{', '.join(sources)}")
    print(f"檔案數量          ：{len(selected_indices):,}")
    print(f"總容量            ：{total_bytes / (1024 ** 3):.3f} GiB")
    print(f"各來源數量        ：{dict(source_counts)}")
    print(f"結果 CSV          ：{output_path}")
    print("前 5 個 object_key：")
    for index in selected_indices[:5]:
        print(f"  - {rows[index].get('object_key', '')}")

    if execute:
        print("\n已指定 --execute，接下來會連線 AWS。")
    else:
        print("\nDry Run 完成：沒有連線或修改 AWS。加上 --execute 才會真的上傳。")


# -----------------------------------------------------------------------------
# 4. AWS 與 URL 小工具
# -----------------------------------------------------------------------------

def create_aws_clients(profile: str | None, region: str):
    """建立 S3、STS Client，以及 boto3 的分段上傳設定類別。"""
    try:
        import boto3
        from boto3.s3.transfer import TransferConfig
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError("尚未安裝 boto3，請執行：python -m pip install boto3") from exc

    # adaptive retry 可在網路短暫不穩時自動重試。
    retry = {"max_attempts": 10, "mode": "adaptive"}
    session = boto3.Session(profile_name=profile, region_name=region)
    s3 = session.client(
        "s3",
        config=Config(
            region_name=region,
            signature_version="s3v4",
            retries=retry,
        ),
    )
    sts = session.client("sts", config=Config(region_name=region, retries=retry))
    return s3, sts, TransferConfig


def find_s3_object(s3, bucket: str, object_key: str):
    """讀取 S3 物件資訊；物件不存在時回傳 None。"""
    from botocore.exceptions import ClientError

    try:
        return s3.head_object(Bucket=bucket, Key=object_key)
    except ClientError as exc:
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = clean_text(exc.response.get("Error", {}).get("Code"))
        if status_code == 404 or error_code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def safe_metadata(value: str, maximum: int = 512) -> str:
    """S3 自訂 metadata 使用簡單 ASCII，並限制長度。"""
    ascii_value = value.encode("ascii", errors="ignore").decode("ascii")
    return ascii_value[:maximum]


def make_s3_https_url(bucket: str, region: str, object_key: str) -> str:
    """建立 S3 HTTPS URL，並正確編碼空白或中文。"""
    encoded_key = quote(object_key, safe="/")
    return f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}"


def make_delivery_url(base_url: str | None, object_key: str) -> str:
    """有提供 CloudFront 網址時，建立穩定的 delivery_url。"""
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/{quote(object_key, safe='/')}"


def fill_s3_result(
    row: dict[str, str],
    args: argparse.Namespace,
    object_key: str,
    s3_info: dict[str, object],
) -> None:
    """把 S3 路徑、網址、ETag、版本與修改時間寫入結果列。"""
    row["s3_uri"] = f"s3://{args.bucket}/{object_key}"
    row["s3_https_url"] = make_s3_https_url(args.bucket, args.region, object_key)
    row["delivery_url"] = make_delivery_url(args.delivery_base_url, object_key)
    row["delivery_url_type"] = "cloudfront" if args.delivery_base_url else ""
    row["s3_etag"] = clean_text(s3_info.get("ETag")).strip('"')
    row["s3_version_id"] = clean_text(s3_info.get("VersionId"))

    last_modified = s3_info.get("LastModified")
    row["s3_last_modified"] = (
        last_modified.astimezone(timezone.utc).isoformat() if last_modified else ""
    )


def fill_presigned_url(
    row: dict[str, str],
    s3,
    bucket: str,
    object_key: str,
    seconds: int,
) -> None:
    """依設定建立臨時下載網址；seconds 為 0 時清空相關欄位。"""
    if seconds == 0:
        row["temporary_presigned_url"] = ""
        row["presigned_expires_at"] = ""
        return

    row["temporary_presigned_url"] = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=seconds,
        HttpMethod="GET",
    )
    row["presigned_expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).isoformat()


# -----------------------------------------------------------------------------
# 5. 單一檔案上傳
# -----------------------------------------------------------------------------

def upload_one_file(
    row: dict[str, str],
    args: argparse.Namespace,
    project_root: Path,
    s3,
    transfer_config,
) -> str:
    """處理一列 Manifest，回傳 uploaded、already_exists 或 conflict 狀態。"""
    item_id = clean_text(row.get("item_id"))
    source = clean_text(row.get("source")).lower()
    object_key = clean_text(row.get("object_key"))
    local_path = resolve_local_path(
        project_root,
        clean_text(row.get("original_glb_path")),
    )
    local_size = local_path.stat().st_size
    row["upload_error"] = ""

    # 先查 S3，避免不必要的重複上傳或意外覆蓋。
    existing = find_s3_object(s3, args.bucket, object_key)
    if existing is not None:
        remote_size = parse_int(existing.get("ContentLength"), -1)

        if remote_size == local_size:
            row["upload_status"] = "already_exists"
            fill_s3_result(row, args, object_key, existing)
            fill_presigned_url(
                row, s3, args.bucket, object_key, args.presign_seconds
            )
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

    # S3 不存在檔案，或使用者明確指定 --force 時，才進行上傳。
    content_type = clean_text(row.get("content_type")) or "model/gltf-binary"
    extra_args = {
        "ContentType": content_type,
        "CacheControl": args.cache_control,
        "Metadata": {
            "item-id": safe_metadata(item_id),
            "source": safe_metadata(source),
        },
    }
    s3.upload_file(
        str(local_path),
        args.bucket,
        object_key,
        ExtraArgs=extra_args,
        Config=transfer_config,
    )

    # 上傳後再次確認遠端大小，避免把不完整檔案記為成功。
    uploaded_info = s3.head_object(Bucket=args.bucket, Key=object_key)
    remote_size = parse_int(uploaded_info.get("ContentLength"), -1)
    if remote_size != local_size:
        raise RuntimeError(f"上傳後大小不符：本機={local_size}，S3={remote_size}")

    row["upload_status"] = "uploaded"
    row["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    fill_s3_result(row, args, object_key, uploaded_info)
    fill_presigned_url(row, s3, args.bucket, object_key, args.presign_seconds)
    print(f"    完成：{local_size:,} bytes")
    return "uploaded"


# -----------------------------------------------------------------------------
# 6. 批次上傳與主流程
# -----------------------------------------------------------------------------

def upload_selected_rows(
    rows: list[dict[str, str]],
    selected_indices: list[int],
    fieldnames: list[str],
    output_path: Path,
    project_root: Path,
    args: argparse.Namespace,
) -> int:
    """連線 AWS、依序上傳所選資料列，並定期保存結果。"""
    s3, sts, TransferConfig = create_aws_clients(args.profile, args.region)

    # 正式上傳前，先顯示目前使用的 AWS 身分並確認 Bucket 可存取。
    try:
        identity = sts.get_caller_identity()
        print(f"\nAWS Account ：{identity.get('Account', '')}")
        print(f"AWS 身分    ：{identity.get('Arn', '')}")
        s3.head_bucket(Bucket=args.bucket)
        print(f"目標 Bucket ：{args.bucket}")
    except Exception as exc:
        print(f"錯誤：無法確認 AWS 身分或 Bucket 權限：{exc}")
        return 3

    # 大檔案會依下列設定使用 boto3 分段上傳。
    mib = 1024 * 1024
    transfer_config = TransferConfig(
        multipart_threshold=args.multipart_threshold_mib * mib,
        multipart_chunksize=args.multipart_chunk_mib * mib,
        max_concurrency=args.max_concurrency,
        use_threads=True,
    )

    counters: Counter[str] = Counter()
    total = len(selected_indices)

    for position, row_index in enumerate(selected_indices, start=1):
        row = rows[row_index]
        source = clean_text(row.get("source")).lower()
        object_key = clean_text(row.get("object_key"))
        print(f"[{position:,}/{total:,}] {source} | {object_key}")

        try:
            status = upload_one_file(row, args, project_root, s3, transfer_config)
            counters[status] += 1
        except KeyboardInterrupt:
            # Ctrl+C 時也先保存目前結果，方便下次用 --resume 繼續。
            print("\n使用者中斷，正在保存目前進度……")
            write_csv_safely(output_path, rows, fieldnames)
            return 130
        except Exception as exc:
            # 單一檔案失敗不會中斷整批工作，錯誤會記在 CSV。
            row["upload_status"] = "failed"
            row["upload_error"] = f"{type(exc).__name__}: {exc}"
            counters["failed"] += 1
            print(f"    失敗：{row['upload_error']}")

        # 固定筆數存檔一次，降低程式中斷時的進度損失。
        if position % args.checkpoint_every == 0:
            write_csv_safely(output_path, rows, fieldnames)
            print(f"    已保存進度：{output_path}")

    # 全部處理完後再保存最後一次，確保不足 checkpoint 筆數的資料也寫入。
    write_csv_safely(output_path, rows, fieldnames)

    print("\n=== 上傳結果 ===")
    for status in ["uploaded", "already_exists", "conflict_size_mismatch", "failed"]:
        print(f"{status:24s}：{counters[status]:,}")
    print(f"結果 CSV               ：{output_path}")

    if counters["failed"] or counters["conflict_size_mismatch"]:
        print("工作已完成，但有問題；請查看 CSV 的 upload_status 與 upload_error。")
        return 4

    print("全部上傳成功。")
    return 0


def run(args: argparse.Namespace) -> int:
    """完整流程：檢查設定 → 讀取 CSV → Dry Run → 視需要正式上傳。"""
    manifest_path, output_path, project_root = get_paths(args)

    # 第一步：先檢查命令列設定與本機路徑。
    setting_errors = validate_settings(
        args,
        manifest_path,
        output_path,
        project_root,
    )
    if setting_errors:
        print_errors("設定檢查失敗", setting_errors)
        return 2

    # 續傳讀結果 CSV；全新工作讀原始 Manifest。
    input_path = output_path if args.resume else manifest_path
    rows, original_fields = read_manifest(input_path)
    fieldnames = add_result_columns(original_fields)

    # 第二步：檢查所有選定來源的 Manifest 資料與本機 GLB。
    sources = [source.lower() for source in args.sources]
    selected_indices, manifest_errors = validate_manifest(
        rows,
        project_root,
        set(sources),
        args.required_prefix,
    )
    if manifest_errors:
        print_errors("Manifest 或本機檔案檢查失敗", manifest_errors)
        print("沒有連線或修改 AWS。")
        return 2

    # 續傳時略過已完成項目，再套用測試筆數限制。
    if args.resume:
        selected_indices = [
            index
            for index in selected_indices
            if clean_text(rows[index].get("upload_status")).lower()
            not in SUCCESS_STATUSES
        ]
    if args.limit is not None:
        selected_indices = selected_indices[: args.limit]

    if not selected_indices:
        print("沒有符合條件或尚未完成的資料。")
        return 0

    # 第三步：永遠先印出上傳摘要；沒有 --execute 就到此結束。
    print_plan(rows, selected_indices, sources, output_path, args.execute)
    if not args.execute:
        return 0

    # 第四步：只有明確指定 --execute，才正式連線 AWS。
    return upload_selected_rows(
        rows,
        selected_indices,
        fieldnames,
        output_path,
        project_root,
        args,
    )


def main() -> None:
    """程式入口：統一顯示可理解的錯誤訊息與結束代碼。"""
    try:
        exit_code = run(parse_args())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"錯誤：{exc}")
        exit_code = 2
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
