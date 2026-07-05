"""Validate RoomPilot IKEA furniture metadata JSON files.

這支腳本用途：
1. 遞迴掃描 data/raw_json 底下的 JSON 檔案。
2. 檢查每個 JSON 是否符合後端與資料庫需要的欄位格式。
3. 輸出 JSON 與 CSV 報告，方便期末專題展示時快速找出資料問題。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 每筆家具物件都必須具備的欄位。
REQUIRED_OBJECT_FIELDS = [
    "id",
    "sku",
    "name",
    "chinese_name",
    "type",
    "position",
    "rotation",
    "size_cm",
    "collision_box_cm",
    "glb_path",
    "material",
    "color",
    "can_rotate",
    "must_against_wall",
]

# 尺寸欄位必須都包含寬、深、高；值可以是數字或 null。
REQUIRED_SIZE_FIELDS = ["width", "depth", "height"]


def parse_args() -> argparse.Namespace:
    """解析命令列參數，讓使用者可以指定資料來源與報告輸出位置。"""
    parser = argparse.ArgumentParser(
        description="Validate RoomPilot furniture metadata JSON files."
    )
    parser.add_argument(
        "--input",
        default="data/raw_json",
        help="要掃描的 JSON 資料夾，預設為 data/raw_json",
    )
    parser.add_argument(
        "--report-dir",
        default="data/reports",
        help="驗證報告輸出資料夾，預設為 data/reports",
    )
    return parser.parse_args()


def add_error(
    errors: list[dict[str, Any]],
    file_path: Path,
    sku: str | None,
    object_index: int | None,
    reason: str,
) -> None:
    """集中建立錯誤資料，讓 JSON 與 CSV 報告格式一致。"""
    errors.append(
        {
            "file": str(file_path),
            "sku": sku or "",
            "object_index": "" if object_index is None else object_index,
            "reason": reason,
        }
    )


def load_json(file_path: Path, errors: list[dict[str, Any]]) -> dict[str, Any] | None:
    """讀取單一 JSON；讀取失敗時記錄錯誤並回傳 None。"""
    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        add_error(errors, file_path, None, None, f"JSON 格式錯誤：{exc}")
        return None
    except OSError as exc:
        add_error(errors, file_path, None, None, f"無法讀取檔案：{exc}")
        return None

    if not isinstance(data, dict):
        add_error(errors, file_path, None, None, "JSON 根節點必須是 object")
        return None

    return data


def get_objects(
    data: dict[str, Any], file_path: Path, errors: list[dict[str, Any]]
) -> list[Any] | None:
    """取出 scene.objects，並檢查它是否存在且為 list。"""
    scene = data.get("scene")
    if not isinstance(scene, dict) or "objects" not in scene:
        add_error(errors, file_path, None, None, "缺少 scene.objects")
        return None

    objects = scene.get("objects")
    if not isinstance(objects, list):
        add_error(errors, file_path, None, None, "scene.objects 必須是 list")
        return None

    return objects


def validate_size_fields(
    value: Any,
    field_name: str,
    file_path: Path,
    sku: str | None,
    object_index: int,
    errors: list[dict[str, Any]],
) -> None:
    """檢查 size_cm 與 collision_box_cm 是否包含 width/depth/height。"""
    if not isinstance(value, dict):
        add_error(errors, file_path, sku, object_index, f"{field_name} 必須是 object")
        return

    for key in REQUIRED_SIZE_FIELDS:
        if key not in value:
            add_error(errors, file_path, sku, object_index, f"{field_name} 缺少 {key}")


def validate_object(
    obj: Any,
    file_path: Path,
    object_index: int,
    seen_skus: dict[str, Path],
    errors: list[dict[str, Any]],
) -> None:
    """檢查單筆家具資料的必要欄位、空字串與 sku 全域重複。"""
    if not isinstance(obj, dict):
        add_error(errors, file_path, None, object_index, "家具資料必須是 object")
        return

    sku = obj.get("sku")
    sku_text = str(sku) if sku is not None else ""

    for field in REQUIRED_OBJECT_FIELDS:
        if field not in obj:
            add_error(errors, file_path, sku_text, object_index, f"缺少必要欄位：{field}")

    if "chinese name" in obj:
        add_error(
            errors,
            file_path,
            sku_text,
            object_index,
            '不可使用舊欄位 "chinese name"，請改為 chinese_name',
        )

    for field in ["name", "glb_path", "type"]:
        value = obj.get(field)
        if isinstance(value, str) and value.strip() == "":
            add_error(errors, file_path, sku_text, object_index, f"{field} 不可以是空字串")
        elif value is None:
            add_error(errors, file_path, sku_text, object_index, f"{field} 不可以是空值")

    glb_path = obj.get("glb_path")
    if isinstance(glb_path, str) and "\\" in glb_path:
        add_error(errors, file_path, sku_text, object_index, "glb_path 不可以包含 Windows 反斜線")

    if not sku_text.strip():
        add_error(errors, file_path, sku_text, object_index, "sku 不可以是空值")
    elif sku_text in seen_skus:
        add_error(
            errors,
            file_path,
            sku_text,
            object_index,
            f"sku 全域重複，第一次出現在 {seen_skus[sku_text]}",
        )
    else:
        seen_skus[sku_text] = file_path

    validate_size_fields(
        obj.get("size_cm"), "size_cm", file_path, sku_text, object_index, errors
    )
    validate_size_fields(
        obj.get("collision_box_cm"),
        "collision_box_cm",
        file_path,
        sku_text,
        object_index,
        errors,
    )


def write_reports(
    report_dir: Path,
    report: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    """輸出 validation_report.json 與 validation_errors.csv。"""
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / "validation_report.json"
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    csv_path = report_dir / "validation_errors.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["file", "sku", "object_index", "reason"])
        writer.writeheader()
        writer.writerows(errors)


def main() -> int:
    """主流程：掃描 JSON、驗證資料、輸出報告與終端機摘要。"""
    args = parse_args()
    input_dir = Path(args.input)
    report_dir = Path(args.report_dir)

    errors: list[dict[str, Any]] = []
    seen_skus: dict[str, Path] = {}
    total_objects = 0
    valid_json_files = 0
    json_files = sorted(input_dir.rglob("*.json")) if input_dir.exists() else []

    if not input_dir.exists():
        add_error(errors, input_dir, None, None, "輸入資料夾不存在")

    for file_path in json_files:
        data = load_json(file_path, errors)
        if data is None:
            continue

        valid_json_files += 1
        objects = get_objects(data, file_path, errors)
        if objects is None:
            continue

        total_objects += len(objects)
        for index, obj in enumerate(objects):
            validate_object(obj, file_path, index, seen_skus, errors)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(input_dir),
        "total_json_files": len(json_files),
        "valid_json_files": valid_json_files,
        "total_objects": total_objects,
        "total_unique_skus": len(seen_skus),
        "error_count": len(errors),
        "passed": len(errors) == 0,
        "errors": errors,
    }

    write_reports(report_dir, report, errors)

    print("RoomPilot JSON 驗證 summary")
    print(f"- 掃描資料夾：{input_dir}")
    print(f"- JSON 檔案數：{len(json_files)}")
    print(f"- 家具筆數：{total_objects}")
    print(f"- 錯誤數：{len(errors)}")
    print(f"- 報告：{report_dir / 'validation_report.json'}")
    print(f"- 錯誤 CSV：{report_dir / 'validation_errors.csv'}")

    if errors:
        print("\n驗證未通過，錯誤如下：")
        for error in errors:
            print(f"- {error['file']} | sku={error['sku']} | {error['reason']}")
        return 1

    print("\n驗證通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
