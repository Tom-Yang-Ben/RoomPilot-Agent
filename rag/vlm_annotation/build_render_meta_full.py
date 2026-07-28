# -*- coding: utf-8 -*-
"""掃描 rendering/output/ikea & abo/ 的預渲染 PNG，建立全量 render_meta。
每件 id 對應 正面 + 45度 兩張圖。
輸出: vlm_annotation/render_meta_full.jsonl  {id, brand, images:[front,iso], is_gray}

註：這批是「灰色背景上的真實貼圖渲染」（沙發/木桌等皆有真實材質色），
非無貼圖灰模；且色度無法區分「灰模」與「本來就是黑/白/灰的家具」。
故一律 is_gray=False（全部送圖給 VLM，由 VLM 依實際外觀判斷）。
"""
import json, os, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # vlm_annotation/
PROJ = ROOT.parent
IMG_BASE = PROJ / "rendering" / "output" / "ikea & abo"
OUT = ROOT / "render_meta_full.jsonl"


def main():
    pngs = glob.glob(f"{IMG_BASE}/**/*.png", recursive=True)
    # 依 id(stem) 分組，正面/45度 靠路徑判斷
    by_id = {}
    for p in pngs:
        stem = os.path.splitext(os.path.basename(p))[0]
        view = "front" if "正面" in p else ("iso" if ("45度" in p or "45" in p) else "other")
        brand = "IKEA" if "/IKEA/" in p else ("ABO" if "/ABO/" in p else "?")
        d = by_id.setdefault(stem, {"brand": brand})
        d[view] = p
    rows, no_front = [], 0
    for i, (stem, d) in enumerate(sorted(by_id.items()), 1):
        front, iso = d.get("front"), d.get("iso")
        imgs = [x for x in (front, iso) if x]
        if not front:
            no_front += 1
        rows.append({"id": stem, "brand": d["brand"], "images": imgs, "is_gray": False})
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"寫出 {len(rows)} 件 → {OUT.name}")
    print(f"  全部 is_gray=False（送圖）；缺正面圖 {no_front} 件")
    from collections import Counter
    print("  品牌分布:", Counter(r["brand"] for r in rows).most_common())


if __name__ == "__main__":
    main()
