#!/usr/bin/env python3
"""sync_room_labels.py — 把 Inkscape 人工改的房型「文字標籤」同步回 class 屬性。

Inkscape 一般介面只能改 <text> 文字，看不到 <g> 的 class 屬性；但 CubiCasa
House 解析器讀的是 class（"Space Bedroom"），文字只是顯示用。人工標注後
兩者會脫節：文字寫 Bedroom、class 仍是 Undefined（或草稿的錯誤房型）。
本腳本以「文字標籤 = 人工正確答案」為準，把 class 改成對應的 CubiCasa
房型名；文字寫法（大小寫/空格/同義詞）先正規化再映射。

用法：
    python scripts/sync_room_labels.py            # 直接改檔（git 可回復）
    python scripts/sync_room_labels.py --dry-run  # 只列出將改什麼
    python scripts/sync_room_labels.py --no-validate  # 跳過 House 回讀驗證

改檔方式是對原始文字做「逐 g-id 定點替換」，不重排版——保留 Inkscape
既有格式，git diff 乾淨。改完後逐張以 House() 回讀驗證（同
make_annotation_drafts.py 的守門標準）。
"""
import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"

# 人工文字寫法 → CubiCasa rooms_selected 詞彙（鍵一律小寫、去空格比對）
# Study/Stair 在 CubiCasa 12 類中仍歸 class 11（Undefined/other），但寫成
# 正式詞彙可與「真正沒標」區分，也讓 House 解析不會遇到陌生名稱。
LABEL_MAP = {
    "bedroom": "Bedroom",
    "livingroom": "LivingRoom",
    "kitchen": "Kitchen",
    "bath": "Bath",
    "bathroom": "Bath",
    "washroom": "Bath",
    "hallway": "HallWay",
    "entrance": "Entry",
    "entry": "Entry",
    "storage": "Storage",
    "study": "Office",
    "stair": "StairWell",
    "terrace": "Outdoor",
    "outdoor": "Outdoor",
    "garage": "Garage",
    "closet": "Closet",
    "sauna": "Sauna",
    "undefined": "Undefined",
}


def space_label(g):
    """取 g 內第一個非空文字（tspan 優先層層找）。"""
    for el in g.iter():
        if el.tag in (SVG_NS + "text", SVG_NS + "tspan") and el.text and el.text.strip():
            return el.text.strip()
    return ""


def collect_changes(svg_path):
    """回傳 [(gid, 舊名, 新名)]、未知標籤清單、沒文字的 Undefined 清單。"""
    changes, unknown, unlabeled = [], [], []
    root = ET.parse(svg_path).getroot()
    for g in root.iter(SVG_NS + "g"):
        cls = g.get("class") or ""
        if not cls.startswith("Space"):
            continue
        cur = cls.split(" ", 1)[1] if " " in cls else "Undefined"
        label = space_label(g)
        if not label or label.lower() == "undefined":
            if cur == "Undefined":
                unlabeled.append(g.get("id"))
            continue
        new = LABEL_MAP.get(label.lower().replace(" ", ""))
        if new is None:
            unknown.append((g.get("id"), label))
        elif new != cur:
            changes.append((g.get("id"), cur, new))
    return changes, unknown, unlabeled


def apply_changes(svg_path, changes):
    """對原始檔逐 g-id 定點替換 class，不動其他內容。"""
    src = open(svg_path).read()
    for gid, old, new in changes:
        pat = re.compile(r'(<g\b[^>]*\bid="%s"[^>]*>)' % re.escape(gid))
        hits = pat.findall(src)
        if len(hits) != 1:
            raise ValueError(f"{svg_path}: id={gid} 匹配到 {len(hits)} 處，放棄改檔")
        tag = hits[0]
        new_tag = tag.replace(f'class="Space {old}"', f'class="Space {new}"')
        if new_tag == tag:
            raise ValueError(f"{svg_path}: id={gid} 的 tag 內找不到 class=\"Space {old}\"")
        src = src.replace(tag, new_tag)
    open(svg_path, "w").write(src)


def validate(svg_path):
    """House 回讀驗證：能解析且有牆像素。"""
    import cv2
    import numpy as np
    from floortrans.loaders.house import House
    png = os.path.join(os.path.dirname(svg_path), "F1_scaled.png")
    h, w = cv2.imread(png).shape[:2]
    house = House(svg_path, h, w)
    if int(np.count_nonzero(house.walls == 2)) == 0:
        raise ValueError("round-trip 無牆像素")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="Identify_ans/own_dataset")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(_root, "training/CubiCasa5k"))

    n_changed, n_files = 0, 0
    all_unknown, all_unlabeled = [], []
    for svg_path in sorted(glob.glob(os.path.join(a.dataset, "*", "model.svg"))):
        floor = os.path.basename(os.path.dirname(svg_path))
        changes, unknown, unlabeled = collect_changes(svg_path)
        all_unknown += [(floor, *u) for u in unknown]
        all_unlabeled += [(floor, u) for u in unlabeled]
        if not changes:
            continue
        for gid, old, new in changes:
            print(f"{floor} {gid}: {old} → {new}")
        if not a.dry_run:
            apply_changes(svg_path, changes)
            if not a.no_validate:
                validate(svg_path)
        n_changed += len(changes)
        n_files += 1

    verb = "將同步" if a.dry_run else "已同步"
    print(f"\n{verb} {n_changed} 處（{n_files} 張圖）")
    if all_unknown:
        print("未知文字標籤（未動，請補進 LABEL_MAP 或改文字）：")
        for floor, gid, label in all_unknown:
            print(f"  {floor} {gid}: {label!r}")
    if all_unlabeled:
        print("仍為 Undefined 且無文字（需人工判斷房型）：")
        for floor, gid in all_unlabeled:
            print(f"  {floor} {gid}")


if __name__ == "__main__":
    main()
