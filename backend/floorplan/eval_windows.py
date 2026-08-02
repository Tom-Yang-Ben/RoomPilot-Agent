#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_windows.py — 用 testdata/Identify_ans/pngans/gray/ 的人工標準答案評分 temp/chk/gray/ 的窗戶偵測結果

    python3 eval_windows.py [答案目錄] [chk目錄]     (預設 testdata/Identify_ans/pngans/gray/ temp/chk/gray/)

兩邊都抽「綠色框」再互相配對：
  TP = chk 的綠框有對到答案的綠框(抓對)
  FP = chk 多畫的綠框(誤抓)
  FN = 答案有、chk 沒畫的綠框(漏抓)
配對標準：交集面積 / 較小框面積 >= 0.3，或一框中心落在另一框內。
一個答案框可由多個預測框共同覆蓋(算 1 個 TP，不重複計)。
"""

import glob
import os
import sys

import cv2
import numpy as np


def green_boxes(path, size=None):
    """抽出圖中所有綠色框的 bbox 清單 [(x0,y0,x1,y1)]。
    同時吃程式畫的 (0,170,0) 與小畫家綠 (34,177,76)，含反鋸齒容差。
    size=(w,h) 時先把圖縮放到該尺寸再抽框——彩色管線可能以 2 倍圖處理，
    chk 疊圖與答案圖尺寸不同（灰階管線兩邊同尺寸，縮放係數=1 不影響）。"""
    img = cv2.imread(path)
    if img is None:
        sys.exit(f"讀不到 {path}")
    if size is not None and (img.shape[1], img.shape[0]) != size:
        img = cv2.resize(img, size, interpolation=cv2.INTER_NEAREST)
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    mask = ((g >= 110) & (g - b >= 45) & (g - r >= 45)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))   # 把 2px 框線黏成一塊
    n, _, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 30:                                    # 雜點
            continue
        boxes.append((int(x), int(y), int(x + w), int(y + h)))
    return boxes


def matched(a, b):
    """兩框是否算同一個窗。"""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    if inter >= 0.3 * min(area_a, area_b):
        return True
    ca = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return (b[0] <= ca[0] <= b[2] and b[1] <= ca[1] <= b[3]) or \
           (a[0] <= cb[0] <= a[2] and a[1] <= cb[1] <= a[3])


def main():
    ans_dir = sys.argv[1] if len(sys.argv) > 1 else "data/testdata/Identify_ans/pngans/gray"
    chk_dir = sys.argv[2] if len(sys.argv) > 2 else "temp/chk/gray"
    ans_files = sorted(glob.glob(os.path.join(ans_dir, "*_ans.png")))
    if not ans_files:
        sys.exit(f"{ans_dir}/ 裡找不到 *_ans.png")

    tot_tp = tot_fp = tot_fn = 0
    print(f"{'圖':<10} {'抓對':>4} {'誤抓':>4} {'漏抓':>4}   誤抓/漏抓位置")
    for ap in ans_files:
        base = os.path.basename(ap).replace("_ans.png", "")
        cp = os.path.join(chk_dir, base + "_chk.png")
        if not os.path.exists(cp):
            print(f"{base:<10} (缺 {cp}，跳過)")
            continue
        ans = green_boxes(ap)
        a_img = cv2.imread(ap)
        pred = green_boxes(cp, size=(a_img.shape[1], a_img.shape[0]))
        hit_ans = [any(matched(a, p) for p in pred) for a in ans]
        fp_boxes = [p for p in pred if not any(matched(a, p) for a in ans)]
        fn_boxes = [a for a, h in zip(ans, hit_ans) if not h]
        tp, fp, fn = sum(hit_ans), len(fp_boxes), len(fn_boxes)
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        notes = []
        for x0, y0, x1, y1 in fp_boxes:
            notes.append(f"誤(x{x0}-{x1},y{y0}-{y1})")
        for x0, y0, x1, y1 in fn_boxes:
            notes.append(f"漏(x{x0}-{x1},y{y0}-{y1})")
        print(f"{base:<10} {tp:>4} {fp:>4} {fn:>4}   {' '.join(notes)}")

    prec = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 1.0
    rec = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 1.0
    print("─" * 60)
    print(f"{'總計':<10} {tot_tp:>4} {tot_fp:>4} {tot_fn:>4}   "
          f"精準率 {prec*100:.0f}%  召回率 {rec*100:.0f}%")


if __name__ == "__main__":
    main()
