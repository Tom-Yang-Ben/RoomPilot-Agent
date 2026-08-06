#!/usr/bin/env python3
"""從 RoomPilot 成果包／專案資料夾蒐集寫交付文件所需的素材，輸出 report_data.json。

為什麼要有這支腳本：第 8 步的產出散在好幾個檔案裡（configuration_snapshot、
render_brief、manifest、rooms/*/最終渲染.png），每次都用手翻很慢也容易漏房間。
這支腳本只做「找出來、對起來、列出缺什麼」，不做任何詮釋或文案。

用法：
    python3 collect_context.py <成果包或專案資料夾> -o report_data.json

輸出結構見 references/data-contract.md。腳本刻意寬鬆：欄位名稱對不上時會
把整份原始 JSON 放進 raw，並在 gaps 裡標明「需人工確認」，讓你去讀原始檔，
而不是猜一個數字寫進提案裡。
"""

import argparse
import json
import re
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
RENDER_HINTS = ("最終渲染", "final", "render", "result")
VIEW_HINTS = ("鎖定視角", "camera", "view", "viewpoint", "白模", "whitebox")

# 房名可能是中文、英文或 slug；這張表只用來補英文名，找不到就留空，不要亂翻。
ROOM_EN = {
    "客廳": "Living Room", "餐廳": "Dining Room", "廚房": "Kitchen",
    "主臥": "Master Bedroom", "主臥室": "Master Bedroom", "臥室": "Bedroom",
    "次臥": "Second Bedroom", "書房": "Study", "衛浴": "Bathroom",
    "浴室": "Bathroom", "陽台": "Balcony", "玄關": "Entryway",
    "更衣室": "Walk-in Closet", "和室": "Tatami Room", "儲藏室": "Storage",
}


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # 壞掉的 JSON 不該讓整個流程停住
        return {"__error__": f"{path.name}: {exc}"}


def deep_find(obj, key_pattern, limit=40):
    """在巢狀結構裡找出 key 符合 pattern 的值，回傳 [(路徑, 值)]。

    schema 會演進，寫死路徑很快就會壞掉；用模糊搜尋比較耐用。
    """
    rx = re.compile(key_pattern, re.I)
    found = []

    def walk(node, path):
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if rx.search(str(k)) and not isinstance(v, (dict, list)):
                    found.append((p, v))
                elif rx.search(str(k)) and isinstance(v, (dict, list)):
                    found.append((p, v))
                else:
                    walk(v, p)
        elif isinstance(node, list):
            for i, v in enumerate(node[:60]):
                walk(v, f"{path}[{i}]")

    walk(obj, "")
    return found


def classify_image(name):
    low = name.lower()
    if any(h in name or h in low for h in RENDER_HINTS):
        return "render"
    if any(h in name or h in low for h in VIEW_HINTS):
        return "view"
    return "other"


def collect_rooms(root):
    """優先讀 rooms/<房名>/ 結構；沒有就退而求其次掃全資料夾的圖。"""
    rooms = {}
    rooms_dir = next((d for d in root.rglob("rooms") if d.is_dir()), None)
    if rooms_dir:
        for d in sorted(p for p in rooms_dir.iterdir() if p.is_dir()):
            imgs = sorted(p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXT)
            rooms[d.name] = {
                "name": d.name,
                "name_en": ROOM_EN.get(d.name, ""),
                "images": [
                    {"path": str(p.relative_to(root)), "kind": classify_image(p.name)}
                    for p in imgs
                ],
            }
    if not rooms:
        loose = [p for p in root.rglob("*") if p.suffix.lower() in IMAGE_EXT]
        if loose:
            rooms["__未分類__"] = {
                "name": "未分類",
                "name_en": "",
                "images": [
                    {"path": str(p.relative_to(root)), "kind": classify_image(p.name)}
                    for p in sorted(loose)[:40]
                ],
            }
    return rooms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="成果包或專案資料夾")
    ap.add_argument("-o", "--output", default="report_data.json")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    data = {"root": str(root), "sources": {}, "rooms": {}, "hints": {}, "gaps": []}

    wanted = {
        "configuration_snapshot": r"configuration_snapshot.*\.json$",
        "render_brief": r"render_brief.*\.json$",
        "manifest": r"manifest\.json$",
        "scene_json": r"scene.*\.json$",
        "layout_json": r"layout.*\.json$",
        "adjustments": r"(adjust|調整)[^/\\]*\.json$",
    }
    for label, pattern in wanted.items():
        # 比對相對路徑而非檔名，adjustments/ 這種靠資料夾命名的才找得到。
        hits = [
            p for p in root.rglob("*.json")
            if re.search(pattern, str(p.relative_to(root)).replace("\\", "/"), re.I)
        ]
        if hits:
            newest = max(hits, key=lambda p: p.stat().st_mtime)
            data["sources"][label] = {
                "path": str(newest.relative_to(root)),
                "raw": load_json(newest),
            }
        else:
            data["gaps"].append(f"找不到 {label}（{pattern}）")

    data["rooms"] = collect_rooms(root)
    if not data["rooms"]:
        data["gaps"].append("找不到任何渲染圖，無法產出逐空間篇章")

    # 常用欄位的模糊索引：給你當線索，不是最終答案。
    merged = {k: v["raw"] for k, v in data["sources"].items()}
    for label, pattern in {
        "style": r"style|風格",
        "palette": r"palette|color_?card|色卡|colorway",
        "area": r"area|坪|square|size_m2",
        "furniture": r"furniture|家具|items",
        "material": r"material|材質|finish",
        "lighting": r"light|燈|luminaire",
        "camera": r"camera|視角|view",
        "version": r"version|scene_version|render_brief_version",
        "room_name": r"room_?name|room_?label|房間",
    }.items():
        hits = deep_find(merged, pattern, limit=12)
        if hits:
            data["hints"][label] = [
                {"path": p, "value": v if not isinstance(v, (dict, list)) else "<巢狀結構，請讀原始檔>"}
                for p, v in hits
            ]
        else:
            data["gaps"].append(f"沒有找到 {label} 相關欄位，需人工確認")

    out = Path(args.output).resolve()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 已輸出：{out}")
    print(f"   來源檔：{', '.join(data['sources']) or '（無）'}")
    print(f"   空間數：{len(data['rooms'])} → {', '.join(data['rooms']) or '（無）'}")
    if data["gaps"]:
        print("⚠️ 需要注意：")
        for g in data["gaps"]:
            print(f"   - {g}")


if __name__ == "__main__":
    main()
