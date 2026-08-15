#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_training_data.py — 21 張測資 → 分割模型訓練資料(交接峙宏 CubiCasa5k 分支)。

    uv run --extra vision python backend/floorplan/export_training_data.py <輸出目錄>

輸出(每張圖):
    images/floorNN.png        原圖
    masks/floorNN.png         逐像素類別遮罩:0=背景 1=牆 2=窗 3=門
    meta.json                 類別定義、標注來源與品質聲明

標注來源與品質(誠實聲明,訓練時要知道):
    牆  = floorplan2dxf 管線的實心牆塊(機器標注,floor08 等難圖會缺漏)
    窗  = `.runtime/floorplan/training_answers/` 的外部人工標準答案
    門  = 管線 detect_doors 高信心門(score ≥0.85,機器標注,覆蓋率低)
用途:CubiCasa5k 預訓練模型的「台灣圖風微調集 + 驗收集」。樣本只有 21 張,
只夠微調與評測,不夠從零訓練。另附 opening_dataset.npz(130 個開口候選
+GT 標籤,LOOCV 驗證管線見 opening_classifier.py)可作輔助任務。
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import floorplan2dxf as fp  # noqa: E402
from eval_windows import green_boxes  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

CLASSES = {0: "background", 1: "wall", 2: "window", 3: "door"}


def build_mask(png_path: str, ans_path: str) -> np.ndarray:
    cfg = fp.load_config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"))
    cfg.input = png_path
    gray, _ = fp.load_gray(cfg)
    bw = fp.binarize(gray, cfg)
    bw, _ = fp.remove_solid_blobs(bw)
    dt = cv2.distanceTransform(bw, cv2.DIST_L2, 5)
    T = max(2, int(round(2.0 * float(dt.max()))))
    pick = lambda v, d: (v if v not in (None, 0) else d)
    cfg.solid = pick(cfg.solid, max(3, int(round(0.35 * T))))
    cfg.h_len = pick(cfg.h_len, max(int(round(1.5 * T)), cfg.solid + 2))
    cfg.v_len = pick(cfg.v_len, cfg.h_len)
    cfg.min_len = pick(cfg.min_len, float(max(int(round(1.0 * T)), 4)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.solid, cfg.solid))
    bw_open = cv2.morphologyEx(bw, cv2.MORPH_OPEN, ker)
    rects = fp.detect_solid(bw_open, cfg, T)
    thin = cv2.subtract(bw, cv2.dilate(bw_open, np.ones((3, 3), np.uint8)))
    doors = fp.detect_doors(thin, T, cfg.door_arc_pct)

    mask = np.zeros(gray.shape, np.uint8)
    for x0, y0, x1, y1 in rects:                       # 1=牆(機器)
        mask[int(y0):int(y1), int(x0):int(x1)] = 1
    for x0, y0, x1, y1 in green_boxes(ans_path):       # 2=窗(人工 GT,蓋過牆)
        mask[y0:y1, x0:x1] = 2
    for cx, cy, w, score in doors:                     # 3=門(高信心機器,方形近似)
        if score < 0.85:
            continue
        r = int(w / 2)
        y0, y1 = max(0, int(cy) - r), min(mask.shape[0], int(cy) + r)
        x0, x1 = max(0, int(cx) - r), min(mask.shape[1], int(cx) + r)
        region = mask[y0:y1, x0:x1]
        region[region == 0] = 3                        # 不覆蓋牆/窗
    return mask


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("用法: export_training_data.py <輸出目錄>")
    out = sys.argv[1]
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    os.makedirs(os.path.join(out, "masks"), exist_ok=True)

    entries = []
    for png in sorted(glob.glob(os.path.join(ROOT, ".runtime/floorplan/training_input/floor*.png"))):
        base = os.path.splitext(os.path.basename(png))[0]
        ans = os.path.join(ROOT, f".runtime/floorplan/training_answers/{base}_ans.png")
        if not os.path.exists(ans):
            print(f"{base}: 無人工答案,跳過")
            continue
        mask = build_mask(png, ans)
        shutil.copy(png, os.path.join(out, "images", f"{base}.png"))
        cv2.imwrite(os.path.join(out, "masks", f"{base}.png"), mask)
        counts = {CLASSES[k]: int((mask == k).sum()) for k in CLASSES}
        entries.append({"name": base, "pixels": counts})
        print(f"{base}: 牆 {counts['wall']}px 窗 {counts['window']}px 門 {counts['door']}px")

    meta = {
        "classes": CLASSES,
        "label_sources": {
            "wall": "machine (floorplan2dxf solid rects) — floor08 等難圖會缺漏",
            "window": "external human ground truth from ignored runtime data",
            "door": "machine (detect_doors score>=0.85, 方形近似) — 覆蓋率低",
        },
        "intended_use": "CubiCasa5k 預訓練模型的台灣圖風微調集+驗收集(21 張,不夠從零訓練)",
        "eval": "驗收請沿用 backend/floorplan/eval_windows.py(窗)與 eval_doors.py(門過濾)",
        "images": entries,
    }
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"\n完成:{len(entries)} 張 → {out}/(images/ masks/ meta.json)")


if __name__ == "__main__":
    main()
