#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_cc_masks.py — CubiCasa 牆遮罩對 testdata/Identify_ans/pngans/color/ 答案的像素級評分。

與 eval_color_walls.py 同一套指標(精準率/召回率/IoU)，但評的是
cubicasa/color/<名>_mask.npz 的 wall 遮罩(原圖尺寸)，不經過矩形化——
用來判斷 DL 遮罩本身的實力，決定融合策略。

用法:
    python3 eval_cc_masks.py            (跑 cubicasa/color/ 裡全部)
    python3 eval_cc_masks.py --vis      (另存差異圖 training/chk/color/evalcc_*.png)
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

ANS_DIR = "testdata/Identify_ans/pngans/color"
MASK_DIR = "cubicasa/color"
ANS_BGR = np.array([21, 0, 136], np.int16)
TOL = 40


def main():
    p = argparse.ArgumentParser(description="CubiCasa 牆遮罩評分")
    p.add_argument("names", nargs="*")
    p.add_argument("--dir", default=MASK_DIR, help="遮罩目錄(預設 cubicasa/color)")
    p.add_argument("--vis", action="store_true")
    a = p.parse_args()

    files = sorted(glob.glob(os.path.join(a.dir, "*_mask.npz")))
    if a.names:
        want = set(a.names)
        files = [f for f in files
                 if os.path.basename(f)[:-len("_mask.npz")] in want]
    if not files:
        sys.exit(f"{a.dir}/ 裡找不到 *_mask.npz")

    tot_tp = tot_fp = tot_fn = 0
    rows = []
    for f in files:
        name = os.path.basename(f)[:-len("_mask.npz")]
        ans_f = os.path.join(ANS_DIR, name + "_ans.png")
        if not os.path.isfile(ans_f):
            continue
        ans = cv2.imread(ans_f)
        d = np.abs(ans.astype(np.int16) - ANS_BGR[None, None, :])
        gt = ((d[..., 0] <= TOL) & (d[..., 1] <= TOL) & (d[..., 2] <= TOL)) \
            .astype(np.uint8)
        pr = np.load(f)["wall"].astype(np.uint8)
        if pr.shape != gt.shape:
            pr = cv2.resize(pr, (gt.shape[1], gt.shape[0]),
                            interpolation=cv2.INTER_NEAREST)
        tp = int(np.count_nonzero(gt & pr))
        fp = int(np.count_nonzero(pr & ~gt))
        fn = int(np.count_nonzero(gt & ~pr))
        tot_tp += tp; tot_fp += fp; tot_fn += fn
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
        rows.append((name, prec, rec, iou))
        if a.vis:
            vis = (ans // 2 + 96).astype(np.uint8)
            vis[(gt == 1) & (pr == 1)] = (255, 255, 255)
            vis[(gt == 0) & (pr == 1)] = (0, 0, 255)
            vis[(gt == 1) & (pr == 0)] = (0, 200, 0)
            os.makedirs("training/chk/color", exist_ok=True)
            cv2.imwrite(os.path.join("training/chk/color", f"evalcc_{name}.png"), vis)

    if not rows:
        sys.exit("沒有可評分的圖")
    print(f"{'圖':24s} {'精準率':>7s} {'召回率':>7s} {'IoU':>7s}")
    for name, prec, rec, iou in rows:
        print(f"{name:24s} {prec:7.1%} {rec:7.1%} {iou:7.1%}")
    tp, fp, fn = tot_tp, tot_fp, tot_fn
    print(f"{'整體(' + str(len(rows)) + '張,像素加權)':24s} "
          f"{tp / (tp + fp):7.1%} {tp / (tp + fn):7.1%} {tp / (tp + fp + fn):7.1%}")


if __name__ == "__main__":
    main()
