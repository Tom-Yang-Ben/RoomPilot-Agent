"""Merge RoomPilot IKEA metadata JSON files into one furniture catalog.

這支腳本用途：
1. 遞迴讀取 data/raw_json 底下所有分類 JSON。
2. 把每個 JSON 的 scene.objects 攤平成家具清單。
3. 輸出 JSONL 與 JSON，供匯入資料庫或後端 API 使用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    """解析命令列參數，支援自訂輸入資料夾與輸出檔案。"""
    parser = argparse.ArgumentParser(
        description="Merge RoomPilot furniture metadata JSON files into catalog files."
    )
    parser.add_argument(
        "--input",
        default="data/raw_json",
        help="來源 JSON 資料夾，預設為 data/raw_json",
    )
    parser.add_argument(
        "--output",
        default="data/processed/furniture_catalog.jsonl",
        help="JSONL 輸出路徑，預設為 data/processed/furniture_catalog.jsonl",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="JSON 陣列輸出路徑，預設會跟 --output 同名但副檔名改成 .json",
    )
    parser.add_argument(
        "--allow-duplicate-sku",
        action="store_true",
        help="允許重複 sku；重複資料會保留並印出警告",
    )
    return parser.parse_args()


def load_json(file_path: Path) -> dict[str, Any]:
    """讀取單一 JSON 檔案，格式錯誤會直接拋出例外讓主流程中止。"""
    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{file_path} 的 JSON 根節點必須是 object")

    return data


def normalize_object(
    obj: dict[str, Any],
    source_json: str,
    project_id: str,
    dataset_title: str,
) -> dict[str, Any]:
    """把原始家具 object 補上 catalog 必要欄位並修正欄位名稱。"""
    item = dict(obj)

    # 舊資料可能使用 chinese name；合併輸出時自動轉成 chinese_name。
    if "chinese name" in item and "chinese_name" not in item:
        item["chinese_name"] = item.pop("chinese name")
    elif "chinese name" in item:
        item.pop("chinese name")

    # Windows 反斜線不利於跨平台與 URL 使用，統一改成 /。
    if isinstance(item.get("glb_path"), str):
        item["glb_path"] = item["glb_path"].replace("\\", "/")

    sku = str(item.get("sku", "")).strip()
    raw_id = item.get("id")

    item["catalog_id"] = sku
    item["raw_id"] = raw_id
    item["project_id"] = project_id
    item["dataset_title"] = dataset_title
    item["source_json"] = source_json

    return item


def collect_catalog(input_dir: Path, allow_duplicate_sku: bool) -> list[dict[str, Any]]:
    """掃描所有 JSON 並收集家具資料；預設遇到重複 sku 會報錯。"""
    if not input_dir.exists():
        raise FileNotFoundError(f"來源資料夾不存在：{input_dir}")

    catalog: list[dict[str, Any]] = []
    seen_skus: dict[str, Path] = {}
    json_files = sorted(input_dir.rglob("*.json"))

    for file_path in json_files:
        data = load_json(file_path)
        scene = data.get("scene", {})
        objects = scene.get("objects", []) if isinstance(scene, dict) else []

        if not isinstance(objects, list):
            raise ValueError(f"{file_path} 的 scene.objects 必須是 list")

        project_id = str(data.get("project_id", "")).strip()
        dataset_title = str(data.get("title", "")).strip()

        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError(f"{file_path} 內有家具資料不是 object")

            item = normalize_object(obj, file_path.name, project_id, dataset_title)
            sku = str(item.get("sku", "")).strip()

            if not sku:
                raise ValueError(f"{file_path} 內有家具缺少 sku，無法建立 catalog_id")

            if sku in seen_skus:
                message = f"sku 重複：{sku}，來源：{file_path}，第一次出現：{seen_skus[sku]}"
                if not allow_duplicate_sku:
                    raise ValueError(message)
                print(f"警告：{message}")
            else:
                seen_skus[sku] = file_path

            catalog.append(item)

    return catalog


def write_outputs(
    catalog: list[dict[str, Any]], jsonl_path: Path, json_path: Path
) -> None:
    """輸出一行一筆的 JSONL，以及容易閱讀的 JSON 陣列檔。"""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as file:
        for item in catalog:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(catalog, file, ensure_ascii=False, indent=2)


def main() -> int:
    """主流程：收集家具資料並輸出 catalog 檔案。"""
    args = parse_args()
    input_dir = Path(args.input)
    jsonl_path = Path(args.output)
    json_path = Path(args.json_output) if args.json_output else jsonl_path.with_suffix(".json")

    try:
        catalog = collect_catalog(input_dir, args.allow_duplicate_sku)
        write_outputs(catalog, jsonl_path, json_path)
    except Exception as exc:
        print(f"合併失敗：{exc}", file=sys.stderr)
        return 1

    print("RoomPilot catalog 合併完成")
    print(f"- 家具筆數：{len(catalog)}")
    print(f"- JSONL：{jsonl_path}")
    print(f"- JSON：{json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
