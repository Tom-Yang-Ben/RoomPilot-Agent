import json
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_PATH = PROJECT_ROOT / ".env"
CATALOG_PATH = PROJECT_ROOT / "data" / "processed" / "furniture_catalog.json"

load_dotenv(dotenv_path=ENV_PATH)


def get_num(obj, *keys):
    """
    安全讀取巢狀數字欄位。
    例如：
    get_num(item, "size_cm", "width")
    """
    current = obj

    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)

    return current


def build_search_text(item):
    """
    建立之後 FastAPI / RAG 可以搜尋用的文字。
    先把英文名、中文名、分類、顏色、材質串起來。
    """
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
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "roompilot_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

    return conn


def main():
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"找不到檔案：{CATALOG_PATH}")

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not isinstance(items, list):
        raise ValueError("furniture_catalog.json 最外層應該要是 list，也就是 []")

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

            [],  # style_tags：之後再補，例如 ["北歐風", "簡約風"]
            [],  # room_tags：之後再補，例如 ["客廳", "臥室"]

            build_search_text(item),

            Json(item),  # raw_data：完整保留原始 JSON
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
                execute_values(
                    cur,
                    insert_sql,
                    rows,
                    page_size=500
                )

                cur.execute("SELECT COUNT(*) FROM furniture_items;")
                count = cur.fetchone()[0]

        print(f"匯入完成：{len(rows)} 筆")
        print(f"資料庫 furniture_items 目前總筆數：{count}")

        if count == 1508:
            print("確認成功：SELECT COUNT(*) = 1508")
        else:
            print("注意：筆數不是 1508，請檢查是否有舊資料或匯入檔案不同。")

    finally:
        conn.close()


if __name__ == "__main__":
    main()