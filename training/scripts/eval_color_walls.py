#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_color_walls.py — 彩色管線「牆體(含建築基柱)」偵測評分

答案集 testdata/Identify_ans/pngans/color/{名稱}_ans.png：在原圖(或管線的 2 倍放大圖)上，
用純色 RGB(136, 0, 21) 實心塗出牆與建築基柱。
本腳本抽出標註遮罩，與 floorplan2dxf_color.detect_walls() 輸出的牆矩形
(含基柱) rasterize 後做像素級比對；ans 與管線處理尺寸不同時自動縮放。

用法:
    python3 eval_color_walls.py                    (跑 testdata/Identify_ans/pngans/color/ 全部)
    python3 eval_color_walls.py color_floor_01     (只跑指定幾張)
    python3 eval_color_walls.py --vis              (另存差異圖 temp/chk/color_eval/eval_*.png)

指標(像素級):
    精準率 = 預測牆中真的是牆的比例   (低 = 多抓假牆)
    召回率 = 標註牆中有被抓到的比例   (低 = 漏抓)
    IoU    = 交集 / 聯集
差異圖: 白=正確(TP)  紅=多抓(FP)  綠=漏抓(FN)
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "floorplan"))
import floorplan2dxf_color as fc

ANS_DIR = "testdata/Identify_ans/pngans/color"
PNG_DIR = "testdata/color_png"
ANS_BGR = np.array([21, 0, 136], np.int16)   # 標註純色 RGB(136,0,21) 的 BGR
TOL = 40                                     # 每通道容差(防壓縮/重存色偏)


def gt_mask(ans_bgr):
    """答案圖 → 牆標註遮罩(0/1)。"""
    d = np.abs(ans_bgr.astype(np.int16) - ANS_BGR[None, None, :])
    return ((d[..., 0] <= TOL) & (d[..., 1] <= TOL) & (d[..., 2] <= TOL)) \
        .astype(np.uint8)


def pred_mask(name, config_path, ans_h, ans_w):
    """跑管線偵測，把牆矩形(含基柱) rasterize 成 ans 尺寸的遮罩(0/1)。"""
    cfg = fc.load_config(config_path)
    cfg.input = os.path.join(PNG_DIR, name + ".png")
    rects, _bgr, _bw, _bwo, _T, w, h, _is_color = fc.detect_walls(cfg)
    sx, sy = ans_w / float(w), ans_h / float(h)
    m = np.zeros((ans_h, ans_w), np.uint8)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(m, (int(round(x0 * sx)), int(round(y0 * sy))),
                      (max(int(round(x1 * sx)) - 1, 0),
                       max(int(round(y1 * sy)) - 1, 0)), 1, -1)
    return m


def save_vis(name, ans_bgr, gt, pr):
    """差異圖：白=TP 紅=FP 綠=FN，墊在淡化的答案圖上。"""
    vis = (ans_bgr // 2 + 96).astype(np.uint8)   # 淡化背景
    vis[(gt == 1) & (pr == 1)] = (255, 255, 255)
    vis[(gt == 0) & (pr == 1)] = (0, 0, 255)
    vis[(gt == 1) & (pr == 0)] = (0, 200, 0)
    os.makedirs("temp/chk/color_eval", exist_ok=True)   # 與管線疊圖 temp/chk/color/ 分開放
    out = os.path.join("temp/chk/color_eval", f"eval_{name}.png")
    cv2.imwrite(out, vis)
    return out


def main():
    p = argparse.ArgumentParser(description="彩色管線牆體偵測評分")
    p.add_argument("names", nargs="*", help="指定圖名(如 color_floor_01)；不給就全部")
    p.add_argument("--config", default="config_color.ini")
    p.add_argument("--vis", action="store_true", help="另存差異圖到 temp/chk/color_eval/")
    a = p.parse_args()

    ans_files = sorted(glob.glob(os.path.join(ANS_DIR, "*_ans.png")))
    if a.names:
        want = set(a.names)
        ans_files = [f for f in ans_files
                     if os.path.basename(f)[:-len("_ans.png")] in want]
    if not ans_files:
        sys.exit(f"{ANS_DIR}/ 裡找不到 *_ans.png")

    tot_tp = tot_fp = tot_fn = 0
    rows = []
    for f in ans_files:
        name = os.path.basename(f)[:-len("_ans.png")]
        src = os.path.join(PNG_DIR, name + ".png")
        if not os.path.isfile(src):
            print(f"!! 跳過 {name}：找不到 {src}")
            continue
        ans = cv2.imread(f)
        gt = gt_mask(ans)
        if not gt.any():
            print(f"!! 跳過 {name}：答案圖抽不到標註色 RGB(136,0,21)")
            continue
        print(f"--- {name} ---")
        pr = pred_mask(name, a.config, *gt.shape[:2])
        tp = int(np.count_nonzero(gt & pr))
        fp = int(np.count_nonzero(pr & ~gt))
        fn = int(np.count_nonzero(gt & ~pr))
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
        rows.append((name, prec, rec, iou))
        if a.vis:
            print(f"    差異圖 → {save_vis(name, ans, gt, pr)}")

    if not rows:
        sys.exit("沒有可評分的圖")
    print(f"\n{'圖':24s} {'精準率':>7s} {'召回率':>7s} {'IoU':>7s}")
    for name, prec, rec, iou in rows:
        print(f"{name:24s} {prec:7.1%} {rec:7.1%} {iou:7.1%}")
    tp, fp, fn = tot_tp, tot_fp, tot_fn
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    print(f"{'整體(' + str(len(rows)) + '張,像素加權)':24s} "
          f"{prec:7.1%} {rec:7.1%} {iou:7.1%}")


if __name__ == "__main__":
    main()
