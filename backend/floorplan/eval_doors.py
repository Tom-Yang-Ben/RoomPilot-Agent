#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_doors.py — 用 door/ 的門樣式圖驗證「門不會被誤判成窗」

    python3 eval_doors.py [door目錄]        (預設 door/)

每張樣式圖直接跑跟主程式相同的偵測管線；只要輸出任何窗框就算「漏過濾」。
過濾率 = 沒被誤判成窗的樣式數 / 總樣式數，目標 ≥ 95%。
"""

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import floorplan2dxf as fp

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")


def detect_on(path):
    """對單張樣式圖執行與 run() 相同的窗偵測流程，回傳 wins。"""
    cfg = fp.load_config(CONFIG_PATH)
    cfg.input = path
    gray, _ = fp.load_gray(cfg)
    bw = fp.binarize(gray, cfg)
    bw, _ = fp.remove_solid_blobs(bw)
    dt = cv2.distanceTransform(bw, cv2.DIST_L2, 5)
    T = max(2, int(round(2.0 * float(dt.max()))))
    pick = lambda v, d: (v if v not in (None, 0) else d)
    cfg.solid = pick(cfg.solid, max(3, int(round(0.35 * T))))
    cfg.h_len = pick(cfg.h_len, max(int(round(1.5 * T)), cfg.solid + 2))
    cfg.v_len = pick(cfg.v_len, cfg.h_len)
    cfg.snap = pick(cfg.snap, float(max(3, int(round(0.6 * T)))))
    cfg.gap = pick(cfg.gap, float(max(3, int(round(0.4 * T)))))
    cfg.min_len = pick(cfg.min_len, float(max(int(round(1.0 * T)), 4)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.solid, cfg.solid))
    bw_open = cv2.morphologyEx(bw, cv2.MORPH_OPEN, ker)
    rects = fp.detect_solid(bw_open, cfg, T)
    thin = cv2.subtract(bw, cv2.dilate(bw_open, np.ones((3, 3), np.uint8)))
    doors = fp.detect_doors(thin, T, cfg.door_arc_pct)
    _, soft = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    return fp.detect_windows(bw, rects, cfg, T, doors, thin, soft)


def main():
    door_dir = sys.argv[1] if len(sys.argv) > 1 else "testdata/door"
    files = sorted(glob.glob(os.path.join(door_dir, "*.png")))
    if not files:
        sys.exit(f"{door_dir}/ 裡找不到 .png")
    ok = 0
    for p in files:
        base = os.path.basename(p)
        try:
            wins = detect_on(p)
        except Exception as e:
            print(f"{base:<24} 執行失敗: {e}")
            continue
        if wins:
            boxes = " ".join(f"(x{int(w[1])}-{int(w[3])},y{int(w[2])}-{int(w[4])})" for w in wins)
            print(f"{base:<24} [失敗] 誤判成窗 {boxes}")
        else:
            ok += 1
            print(f"{base:<24} [通過] 正確過濾")
    rate = ok / len(files) * 100
    print("-" * 50)
    print(f"門過濾率: {ok}/{len(files)} = {rate:.0f}%  (目標 >=95%)")


if __name__ == "__main__":
    main()
