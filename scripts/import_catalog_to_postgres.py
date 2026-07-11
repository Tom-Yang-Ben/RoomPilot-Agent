import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
CATALOG_PATH = PROJECT_ROOT / "data" / "processed" / "furniture_catalog.json"

load_dotenv(dotenv_path=ENV_PATH)


def get_num(obj, *keys):
    """從巢狀 dict 安全取出數值欄位；任一路徑不存在或不是 dict 就回傳 None。"""
    current = obj

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def build_search_text(item):
    """把名稱、分類、顏色、材質等欄位串成搜尋文字，供 API/RAG 查詢使用。"""
    parts = [
        item.get("name", ""),
        item.get("chinese_name", ""),
        item.get("type", ""),
        item.get("category_name_zh", ""),
        item.get("category_name_en", ""),
        item.get("color", ""),
        item.get("material", ""),
    ]

    return " ".join(str(part) for part in parts if part)


def connect_db():
    """讀取 .env 裡的 PostgreSQL 設定並建立資料庫連線。"""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "roompilot_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

    return conn


def main():
    """讀取 furniture_catalog.json，整理欄位後批次 upsert 到 furniture_items 資料表。"""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"找不到 catalog 檔案：{CATALOG_PATH}")

    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        items = json.load(file)

    if not isinstance(items, list):
        raise ValueError("furniture_catalog.json 必須是 list，也就是最外層要是 []。")

    rows = []

    for item in items:
        position = item.get("position") or [0, 0]

        row = (
            item.get("sku"),
            item.get("catalog_id"),
            item.get("raw_id"),
            item.get("name"),
            item.get("chinese_name"),
            item.get("type"),
            item.get("category"),
            item.get("category_name_zh"),
            item.get("category_name_en"),
            get_num(item, "size_cm", "width"),
            get_num(item, "size_cm", "depth"),
            get_num(item, "size_cm", "height"),
            get_num(item, "collision_box_cm", "width"),
            get_num(item, "collision_box_cm", "depth"),
            get_num(item, "collision_box_cm", "height"),
            item.get("glb_path"),
            item.get("material"),
            item.get("color"),
            item.get("can_rotate", True),
            item.get("must_against_wall", False),
            position[0] if len(position) > 0 else 0,
            position[1] if len(position) > 1 else 0,
            item.get("rotation", 0),
            item.get("project_id"),
            item.get("dataset_title"),
            item.get("source_json"),
            [],
            [],
            build_search_text(item),
            Json(item),
        )

        rows.append(row)

    insert_sql = """
        INSERT INTO furniture_items (
            sku,
            catalog_id,
            raw_id,

            name,
            chinese_name,

            type,
            category,
            category_name_zh,
            category_name_en,

            width_cm,
            depth_cm,
            height_cm,

            collision_width_cm,
            collision_depth_cm,
            collision_height_cm,

            glb_path,

            material,
            color,

            can_rotate,
            must_against_wall,

            position_x,
            position_y,
            rotation,

            project_id,
            dataset_title,
            source_json,

            style_tags,
            room_tags,

            search_text,

            raw_data
        )
        VALUES %s
        ON CONFLICT (sku) DO UPDATE SET
            catalog_id = EXCLUDED.catalog_id,
            raw_id = EXCLUDED.raw_id,

            name = EXCLUDED.name,
            chinese_name = EXCLUDED.chinese_name,

            type = EXCLUDED.type,
            category = EXCLUDED.category,
            category_name_zh = EXCLUDED.category_name_zh,
            category_name_en = EXCLUDED.category_name_en,

            width_cm = EXCLUDED.width_cm,
            depth_cm = EXCLUDED.depth_cm,
            height_cm = EXCLUDED.height_cm,

            collision_width_cm = EXCLUDED.collision_width_cm,
            collision_depth_cm = EXCLUDED.collision_depth_cm,
            collision_height_cm = EXCLUDED.collision_height_cm,

            glb_path = EXCLUDED.glb_path,

            material = EXCLUDED.material,
            color = EXCLUDED.color,

            can_rotate = EXCLUDED.can_rotate,
            must_against_wall = EXCLUDED.must_against_wall,

            position_x = EXCLUDED.position_x,
            position_y = EXCLUDED.position_y,
            rotation = EXCLUDED.rotation,

            project_id = EXCLUDED.project_id,
            dataset_title = EXCLUDED.dataset_title,
            source_json = EXCLUDED.source_json,

            search_text = EXCLUDED.search_text,
            raw_data = EXCLUDED.raw_data,

            updated_at = NOW();
    """

    conn = connect_db()

    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, rows, page_size=500)
                cur.execute("SELECT COUNT(*) FROM furniture_items;")
                count = cur.fetchone()[0]

        print(f"匯入完成：{len(rows)} 筆")
        print(f"furniture_items 目前總筆數：{count}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
