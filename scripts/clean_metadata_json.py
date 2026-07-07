import json
from pathlib import Path

RAW_DIR = Path("data/ikea抓取家具glb_中文命名版")
CLEAN_DIR = Path("data/clean_json")

CLEAN_DIR.mkdir(parents=True, exist_ok=True)

for json_path in RAW_DIR.rglob("*_glb_metadata.json"):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("scene", {}).get("objects", [])

    for obj in objects:
        # 1. chinese name -> chinese_name
        if "chinese name" in obj:
            obj["chinese_name"] = obj.pop("chinese name")

        # 2. glb_path 反斜線改正斜線
        if "glb_path" in obj and isinstance(obj["glb_path"], str):
            obj["glb_path"] = obj["glb_path"].replace("\\", "/")

        # 3. 加上 category，方便之後查詢
        if "category" not in obj:
            obj["category"] = data.get("project_id", "")

    output_path = CLEAN_DIR / json_path.name

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"完成：{json_path.name} -> {output_path}")