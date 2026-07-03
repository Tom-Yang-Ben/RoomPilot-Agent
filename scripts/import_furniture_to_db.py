"""Import RoomPilot furniture catalog JSONL into PostgreSQL.

這支腳本用途：
1. 從 .env 讀取 DATABASE_URL。
2. 自動建立 furniture_items 資料表。
3. 將 data/processed/furniture_catalog.jsonl 一筆一筆 upsert 到 PostgreSQL。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    MetaData,
    String,
    Table,
    Text,
    TIMESTAMP,
    create_engine,
    func,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine


def parse_args() -> argparse.Namespace:
    """解析命令列參數，讓使用者可指定 catalog 與錯誤報告位置。"""
    parser = argparse.ArgumentParser(
        description="Import RoomPilot furniture catalog JSONL into PostgreSQL."
    )
    parser.add_argument(
        "--input",
        default="data/processed/furniture_catalog.jsonl",
        help="家具 catalog JSONL 路徑，預設為 data/processed/furniture_catalog.jsonl",
    )
    parser.add_argument(
        "--error-output",
        default="data/reports/import_errors.csv",
        help="匯入失敗 CSV 輸出路徑，預設為 data/reports/import_errors.csv",
    )
    return parser.parse_args()


def build_table(metadata: MetaData) -> Table:
    """定義 furniture_items 資料表欄位，SQLAlchemy 會用它自動建表。"""
    raw_json_type = JSONB().with_variant(JSON(), "sqlite")

    return Table(
        "furniture_items",
        metadata,
        Column("catalog_id", Text, primary_key=True),
        Column("sku", Text, unique=True, nullable=False),
        Column("raw_id", Text),
        Column("name", Text, nullable=False),
        Column("chinese_name", Text),
        Column("type", Text),
        Column("category", Text),
        Column("color", Text),
        Column("material", Text),
        Column("glb_path", Text, nullable=False),
        Column("width_cm", Float),
        Column("depth_cm", Float),
        Column("height_cm", Float),
        Column("collision_width_cm", Float),
        Column("collision_depth_cm", Float),
        Column("collision_height_cm", Float),
        Column("can_rotate", Boolean),
        Column("must_against_wall", Boolean),
        Column("project_id", Text),
        Column("dataset_title", Text),
        Column("source_json", Text),
        Column("raw_json", raw_json_type),
        Column("created_at", TIMESTAMP, server_default=func.now()),
        Column("updated_at", TIMESTAMP, server_default=func.now(), onupdate=func.now()),
    )


def get_database_url() -> str:
    """從 .env 載入 DATABASE_URL，沒有設定時停止執行並提示使用者。"""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "找不到 DATABASE_URL，請在 .env 加上例如："
            "DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/roompilot"
        )
    return database_url


def to_float(value: Any) -> float | None:
    """把尺寸欄位安全轉成 float；空值或無法轉換時回傳 None。"""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_row(item: dict[str, Any]) -> dict[str, Any]:
    """把 catalog JSON 欄位轉成資料表欄位。"""
    size = item.get("size_cm") if isinstance(item.get("size_cm"), dict) else {}
    collision = (
        item.get("collision_box_cm")
        if isinstance(item.get("collision_box_cm"), dict)
        else {}
    )

    return {
        "catalog_id": str(item.get("catalog_id") or item.get("sku") or "").strip(),
        "sku": str(item.get("sku") or "").strip(),
        "raw_id": item.get("raw_id") or item.get("id"),
        "name": str(item.get("name") or "").strip(),
        "chinese_name": item.get("chinese_name"),
        "type": item.get("type"),
        "category": item.get("category") or item.get("type"),
        "color": item.get("color"),
        "material": item.get("material"),
        "glb_path": str(item.get("glb_path") or "").strip().replace("\\", "/"),
        "width_cm": to_float(size.get("width")),
        "depth_cm": to_float(size.get("depth")),
        "height_cm": to_float(size.get("height")),
        "collision_width_cm": to_float(collision.get("width")),
        "collision_depth_cm": to_float(collision.get("depth")),
        "collision_height_cm": to_float(collision.get("height")),
        "can_rotate": item.get("can_rotate"),
        "must_against_wall": item.get("must_against_wall"),
        "project_id": item.get("project_id"),
        "dataset_title": item.get("dataset_title"),
        "source_json": item.get("source_json"),
        "raw_json": item,
    }


def validate_row(row: dict[str, Any]) -> None:
    """匯入前做最基本的必填欄位檢查，避免資料庫錯誤訊息太難讀。"""
    for field in ["catalog_id", "sku", "name", "glb_path"]:
        if not row.get(field):
            raise ValueError(f"缺少必要欄位：{field}")


def read_catalog(jsonl_path: Path) -> list[dict[str, Any]]:
    """讀取 JSONL；每一行必須是一筆家具 object。"""
    if not jsonl_path.exists():
        raise FileNotFoundError(f"找不到輸入檔案：{jsonl_path}")

    items: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {line_number} 行 JSON 格式錯誤：{exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"第 {line_number} 行必須是 JSON object")
            items.append(item)
    return items


def upsert_row(engine: Engine, table: Table, row: dict[str, Any]) -> bool:
    """依 catalog_id 或 sku 判斷資料是否存在，存在就更新，不存在就新增。"""
    with engine.begin() as connection:
        existing_by_catalog_id = connection.execute(
            select(table.c.catalog_id).where(table.c.catalog_id == row["catalog_id"])
        ).first()
        existing_by_sku = connection.execute(
            select(table.c.catalog_id).where(table.c.sku == row["sku"])
        ).first()

        if (
            existing_by_catalog_id
            and existing_by_sku
            and existing_by_catalog_id.catalog_id != existing_by_sku.catalog_id
        ):
            raise ValueError(
                "catalog_id 與 sku 分別對應到不同既有資料，請先清理資料庫重複資料"
            )

        existing = existing_by_catalog_id or existing_by_sku

        if existing:
            update_values = dict(row)
            update_values["updated_at"] = func.now()
            connection.execute(
                table.update()
                .where(table.c.catalog_id == existing.catalog_id)
                .values(**update_values)
            )
            return True

        connection.execute(insert(table).values(**row))
        return False


def write_import_errors(error_output: Path, errors: list[dict[str, Any]]) -> None:
    """把匯入失敗的資料寫成 CSV，方便用 Excel 或文字編輯器查看。"""
    error_output.parent.mkdir(parents=True, exist_ok=True)
    with error_output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["catalog_id", "sku", "reason"])
        writer.writeheader()
        writer.writerows(errors)


def import_items(
    engine: Engine,
    table: Table,
    items: list[dict[str, Any]],
    error_output: Path,
) -> dict[str, int]:
    """逐筆匯入家具資料，並統計新增、更新與失敗數量。"""
    inserted = 0
    updated = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    for item in items:
        row = build_row(item)
        try:
            validate_row(row)
            exists = upsert_row(engine, table, row)
            if exists:
                updated += 1
            else:
                inserted += 1
        except Exception as exc:
            failed += 1
            errors.append(
                {
                    "catalog_id": row.get("catalog_id", ""),
                    "sku": row.get("sku", ""),
                    "reason": str(exc),
                }
            )

    write_import_errors(error_output, errors)
    return {
        "total": len(items),
        "inserted": inserted,
        "updated": updated,
        "failed": failed,
    }


def main() -> int:
    """主流程：讀 catalog、建表、匯入資料並輸出統計。"""
    args = parse_args()
    input_path = Path(args.input)
    error_output = Path(args.error_output)

    try:
        database_url = get_database_url()
        engine = create_engine(database_url, future=True)
        metadata = MetaData()
        table = build_table(metadata)
        metadata.create_all(engine)

        items = read_catalog(input_path)
        summary = import_items(engine, table, items, error_output)
    except Exception as exc:
        print(f"匯入失敗：{exc}", file=sys.stderr)
        return 1

    print("RoomPilot 家具資料匯入完成")
    print(f"- 總筆數：{summary['total']}")
    print(f"- 新增：{summary['inserted']}")
    print(f"- 更新：{summary['updated']}")
    print(f"- 失敗：{summary['failed']}")
    print(f"- 失敗報告：{error_output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
