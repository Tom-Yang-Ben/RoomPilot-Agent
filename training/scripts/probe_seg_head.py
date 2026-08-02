#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_seg_head.py — 監督式分割頭可分性標定（階段 0）。

spec: docs/superpowers/specs/2026-08-03-seg-head-design.md

19 張彩 dev：DINOv2 patch 特徵 → GT「房內/非房內」patch 標籤 →
留一張 CV 線性頭。報告逐張 patch AUC/IoU，落預測機率圖供目視
（重點：棄守張 07/08/09 邊界是否成形）。

紀律：只碰 own_dataset_color；own_eval_color 不讀。
"""
import glob
import json
import os
import sys

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))
sys.path.insert(0, os.path.join(_ROOT, "training", "scripts"))

PATCH = 14
MAX_SIDE = 1148          # 前向解析度上限（82 patch 格；CPU 注意力可承受）
OUT = "temp/json/seg_head_probe.json"
VIS_DIR = "temp/seg_head"


def prep_image(bgr):
    """resize 到 14 倍數（等比、上限 MAX_SIDE），回 (img, sx, sy)。"""
    h, w = bgr.shape[:2]
    s = min(1.0, MAX_SIDE / max(h, w))
    nh = max(PATCH, int(round(h * s / PATCH)) * PATCH)
    nw = max(PATCH, int(round(w * s / PATCH)) * PATCH)
    img = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    return img, nw / w, nh / h


_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def patch_features(st, img):
    """整圖前向 → (gh, gw, C) patch 特徵。"""
    torch, model = st["torch"], st["model"]
    x = (cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
         / 255.0 - _MEAN) / _STD
    with torch.no_grad():
        t = torch.from_numpy(x.transpose(2, 0, 1)[None])
        f = model.get_intermediate_layers(t, 1, reshape=True)[0]
    return f[0].permute(1, 2, 0).cpu().numpy()      # (gh, gw, C)


def patch_labels(gt, shape_1x, sx, sy, gh, gw):
    """GT 房聯集 → patch 格標籤（房內佔比 >0.5）。"""
    h, w = shape_1x
    union = np.zeros((h, w), np.uint8)
    for _lab, m in gt:
        union |= m.astype(np.uint8)
    u = cv2.resize(union, (gw * PATCH, gh * PATCH),
                   interpolation=cv2.INTER_AREA if (sx < 1 or sy < 1)
                   else cv2.INTER_NEAREST)
    blocks = u.reshape(gh, PATCH, gw, PATCH).mean(axis=(1, 3))
    return (blocks > 0.5).astype(np.uint8)


def fit_head(X, y, epochs=200, lr=0.5, l2=1e-4):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    w = np.zeros(Z.shape[1], np.float64)
    b = 0.0
    n = len(y)
    for _ in range(epochs):
        p = 1.0 / (1.0 + np.exp(-(Z @ w + b)))
        g = p - y
        w -= lr * (Z.T @ g / n + l2 * w)
        b -= lr * float(g.mean())
    return w, b, mu, sd


def auc_of(y, s):
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    gt_ = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt_ + 0.5 * eq) / (len(pos) * len(neg)))


def main():
    import argparse
    import eval_rooms_cc as ev
    import room_classifier as rc
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fit-final", action="store_true",
                    help="19 張全訓、寫出 backend/floorplan/seg_head.npz"
                         "（dev 量測因此帶訓練偏差，真實成績以 holdout 判）")
    args = ap.parse_args()
    st = rc._load("color")
    assert st is not None
    os.makedirs(VIS_DIR, exist_ok=True)
    root = "testdata/Identify_ans/own_dataset_color"
    data = {}
    for d in sorted(glob.glob(os.path.join(root, "color_floor_*"))):
        sid = os.path.basename(d)
        bgr = cv2.imread(os.path.join(d, "F1_scaled.png"))
        gt = ev.parse_gt(os.path.join(d, "model.svg"), *bgr.shape[:2])
        if gt is None:
            print(f"{sid}: parse_gt 失敗，跳過")
            continue
        img, sx, sy = prep_image(bgr)
        feats = patch_features(st, img)
        gh, gw = feats.shape[:2]
        lab = patch_labels(gt, bgr.shape[:2], sx, sy, gh, gw)
        data[sid] = {"X": feats.reshape(-1, feats.shape[2]),
                     "y": lab.reshape(-1), "gh": gh, "gw": gw,
                     "shape": bgr.shape[:2]}
        print(f"{sid}: grid {gh}x{gw} 房內 {int(lab.sum())}/{lab.size}")

    ids = sorted(data)
    if args.fit_final:
        X = np.vstack([data[s]["X"] for s in ids])
        yy = np.concatenate([data[s]["y"] for s in ids])
        w, b, mu, sd = fit_head(X, yy.astype(np.float64))
        out = os.path.join(_ROOT, "backend", "floorplan", "seg_head.npz")
        np.savez_compressed(out, w=w, b=b, mu=mu, sd=sd,
                            backbone=st["backbone"], max_side=MAX_SIDE)
        print(f"出貨資產 → {out}（樣本 {len(yy)}）")
        return
    rep = {}
    for sid in ids:
        Xtr = np.vstack([data[s]["X"] for s in ids if s != sid])
        ytr = np.concatenate([data[s]["y"] for s in ids if s != sid])
        w, b, mu, sd = fit_head(Xtr, ytr.astype(np.float64))
        Z = (data[sid]["X"] - mu) / sd
        p = 1.0 / (1.0 + np.exp(-(Z @ w + b)))
        y = data[sid]["y"]
        auc = auc_of(y, p)
        pred = (p > 0.5).astype(np.uint8)
        inter = int((pred & y).sum())
        union = int((pred | y).sum())
        iou = inter / max(1, union)
        rep[sid] = {"auc": round(auc, 4), "iou": round(iou, 4)}
        gh, gw = data[sid]["gh"], data[sid]["gw"]
        vis = (p.reshape(gh, gw) * 255).astype(np.uint8)
        vis = cv2.resize(vis, (gw * PATCH, gh * PATCH),
                         interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(os.path.join(VIS_DIR, f"{sid}_prob.png"), vis)
        gtv = (data[sid]["y"].reshape(gh, gw) * 255).astype(np.uint8)
        cv2.imwrite(os.path.join(VIS_DIR, f"{sid}_gt.png"),
                    cv2.resize(gtv, (gw * PATCH, gh * PATCH),
                               interpolation=cv2.INTER_NEAREST))
        print(f"{sid}: AUC {auc:.3f}  IoU {iou:.3f}")

    aucs = [v["auc"] for v in rep.values()]
    ious = [v["iou"] for v in rep.values()]
    print(f"\n全集: AUC mean {np.mean(aucs):.3f}  IoU mean {np.mean(ious):.3f}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"per_image": rep,
               "mean_auc": float(np.mean(aucs)),
               "mean_iou": float(np.mean(ious))},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"報表 → {OUT}   預測圖 → {VIS_DIR}/")


if __name__ == "__main__":
    main()
