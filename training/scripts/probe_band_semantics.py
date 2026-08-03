#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_band_semantics.py — 帶級 DINO 語意可分性標定（白牆萃取品質輪，階段 0）。

spec: docs/superpowers/specs/2026-08-02-band-semantics-design.md

彩圖白牆帶的真/假判定既有手工特徵五五開（floor_09 收案）。本工具量測
「帶級 DINO 語意」這個未試過的粒度：19 張彩 dev 的 white_wall_rects
候選帶，以 GT 弱標籤（帶身落 GT 房內比例）標真假，抽帶身/側翼 DINO
patch 特徵＋手工特徵，留一張交叉驗證量 AUC（DINO／手工／合併三組）。

量尺紀律：只掃彩 dev，holdout 不碰。AUC ≥0.65 才進管線接入（Task 3）。
產出 temp/json/band_semantics.json。
"""
import json
import os
import sys
from collections import defaultdict

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))
sys.path.insert(0, os.path.join(_ROOT, "training", "scripts"))

N_HAND = 7          # 手工特徵維度（見 band_hand_features）
FLANK_T = 2.5       # 側翼展開量（×T，與 white_wall_rects 採樣範圍一致）
OUT = "temp/json/band_semantics.json"


# ─────────────────────────── 幾何與弱標籤 ───────────────────────────
def band_gt_label(band, gt, lo=0.3, hi=0.7):
    """帶身像素落 GT 房內比例 → "fake"(≥hi)/"true"(≤lo)/None(灰區棄標)。

    真牆帶位於房間夾縫廊道（GT 多邊形之外）；假帶（家具緣/磁磚帶/地毯緣）
    橫在房內部。gt = parse_gt 輸出 [(label, mask)]。"""
    x0, y0, x1, y1 = [int(round(v)) for v in band]
    h, w = gt[0][1].shape
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    union = np.zeros((y1 - y0, x1 - x0), bool)
    for _lab, m in gt:
        union |= m[y0:y1, x0:x1]
    fr = float(union.mean())
    if fr >= hi:
        return "fake"
    if fr <= lo:
        return "true"
    return None


def band_region(band, T, shape):
    """帶 bbox 沿法向 ±FLANK_T·T 展開（帶長方向不動），裁到圖框。"""
    x0, y0, x1, y1 = [int(round(v)) for v in band]
    h, w = shape
    off = int(round(FLANK_T * T))
    if (x1 - x0) >= (y1 - y0):          # 水平帶 → 法向為 y
        y0, y1 = y0 - off, y1 + off
    else:
        x0, x1 = x0 - off, x1 + off
    return (max(0, x0), max(0, y0), min(w, x1), min(h, y1))


# ─────────────────────────── 手工特徵 ───────────────────────────
def band_hand_features(bgr, band, T, dark_rects):
    """長厚比、th/T、兩側 tint 佔比(max/min)、暗牆端接數、帶內 chroma/L。"""
    x0, y0, x1, y1 = [int(round(v)) for v in band]
    horiz = (x1 - x0) >= (y1 - y0)
    th = (y1 - y0) if horiz else (x1 - x0)
    ln = (x1 - x0) if horiz else (y1 - y0)
    lab = cv2.cvtColor(cv2.medianBlur(bgr, 3), cv2.COLOR_BGR2LAB)
    a_ = lab[:, :, 1].astype(np.int16) - 128
    b_ = lab[:, :, 2].astype(np.int16) - 128
    chroma = np.sqrt(a_ * a_ + b_ * b_)
    L = lab[:, :, 0]
    tint = (chroma > 10) & (L > 60)
    H, W = tint.shape
    side = [0, 0]
    samples = 0
    step = max(1, ln // 20)
    offs = [int(0.5 * T) + 2, int(1.5 * T), int(2.5 * T)]
    for p in range(0, ln, step):
        samples += 1
        for si, sign in ((0, -1), (1, 1)):
            hit = False
            for off in offs:
                if horiz:
                    iy = (y0 - off) if sign < 0 else (y1 + off)
                    ix = x0 + p
                else:
                    ix = (x0 - off) if sign < 0 else (x1 + off)
                    iy = y0 + p
                if 0 <= iy < H and 0 <= ix < W:
                    hit = hit or bool(tint[iy, ix])
            side[si] += hit
    tf = sorted((s / max(1, samples) for s in side), reverse=True)
    # 暗牆端接：兩端點 2T 內有暗牆 rect
    ends = ([(x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0)] if horiz
            else [((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1)])
    touch = 0
    for ex, ey in ends:
        for rx0, ry0, rx1, ry1 in (dark_rects or []):
            if (rx0 - 2 * T <= ex <= rx1 + 2 * T
                    and ry0 - 2 * T <= ey <= ry1 + 2 * T):
                touch += 1
                break
    bx0, by0 = max(0, x0), max(0, y0)
    bx1, by1 = min(W, x1), min(H, y1)
    band_ch = float(chroma[by0:by1, bx0:bx1].mean()) if by1 > by0 and bx1 > bx0 else 0.0
    band_l = float(L[by0:by1, bx0:bx1].mean()) if by1 > by0 and bx1 > bx0 else 0.0
    return np.array([ln / max(1.0, th), th / max(1.0, T),
                     tf[0], tf[1], float(touch), band_ch, band_l],
                    np.float32)


# ─────────────────────────── DINO 帶特徵 ───────────────────────────
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _strip_feat(st, strip):
    """單條帶狀影像 → resize 14×W → 1 patch 列 → mean 向量。"""
    torch, model = st["torch"], st["model"]
    h, w = strip.shape[:2]
    if h == 0 or w == 0:
        return None
    tw = int(np.clip(round(w * (14.0 / h) / 14.0) * 14, 14, 518))
    img = cv2.resize(strip, (tw, 14), interpolation=cv2.INTER_AREA)
    x = (cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
         / 255.0 - _MEAN) / _STD
    with torch.no_grad():
        t = torch.from_numpy(x.transpose(2, 0, 1)[None])
        f = model.get_intermediate_layers(t, 1, reshape=True)[0]
    return f[0].cpu().numpy().mean(axis=(1, 2))


def band_dino_features_v2(st, bgr, band, T):
    """精確對齊版：帶身條帶與兩側翼條帶各自裁切、各自 1 patch 列前向。
    v1 的「region 置中假設」在圖緣帶（外圈真牆）失準，本版不依賴置中。
    回傳 [身, 翼mean, 身−翼] 串接。"""
    x0, y0, x1, y1 = [int(round(v)) for v in band]
    H, W = bgr.shape[:2]
    horiz = (x1 - x0) >= (y1 - y0)
    off = int(round(FLANK_T * T))
    def cut(a0, b0, a1, b1):
        a0, b0 = max(0, a0), max(0, b0)
        a1, b1 = min(W, a1), min(H, b1)
        if a1 <= a0 or b1 <= b0:
            return None
        s = bgr[b0:b1, a0:a1]
        return np.ascontiguousarray(np.rot90(s)) if not horiz else s
    if horiz:
        body = cut(x0, y0, x1, y1)
        f1 = cut(x0, y0 - off, x1, y0)
        f2 = cut(x0, y1, x1, y1 + off)
    else:
        body = cut(x0, y0, x1, y1)
        f1 = cut(x0 - off, y0, x0, y1)
        f2 = cut(x1, y0, x1 + off, y1)
    if body is None:
        return None
    fb = _strip_feat(st, body)
    fls = [f for f in (_strip_feat(st, s) if s is not None else None
                       for s in (f1, f2)) if f is not None]
    if fb is None or not fls:
        return None
    fl = np.mean(fls, axis=0)
    return np.concatenate([fb, fl, fb - fl]).astype(np.float32)


def band_dino_features(st, bgr, band, T):
    """帶身＋側翼區域一次前向：resize 到 3 patch 列(42px)，中列＝帶身、
    上下列＝側翼。回傳 [mean(帶身), mean(側翼), 差] 串接（3×C 維）。"""
    torch, model = st["torch"], st["model"]
    x0, y0, x1, y1 = band_region(band, T, bgr.shape[:2])
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    bx0, by0, bx1, by1 = [int(round(v)) for v in band]
    if (bx1 - bx0) < (by1 - by0):        # 垂直帶 → 轉成水平處理
        crop = np.ascontiguousarray(np.rot90(crop))
    h, w = crop.shape[:2]
    tw = int(np.clip(round(w * (42.0 / h) / 14.0) * 14, 14, 518))
    img = cv2.resize(crop, (tw, 42), interpolation=cv2.INTER_AREA)
    x = (cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
         / 255.0 - _MEAN) / _STD
    with torch.no_grad():
        t = torch.from_numpy(x.transpose(2, 0, 1)[None])
        f = model.get_intermediate_layers(t, 1, reshape=True)[0]
        f = f[0].cpu().numpy()           # (C, 3, tw/14)
    body = f[:, 1, :].mean(axis=1)
    flank = f[:, (0, 2), :].mean(axis=(1, 2))
    return np.concatenate([body, flank, body - flank]).astype(np.float32)


# ─────────────────────────── probe 與 AUC ───────────────────────────
def fit_logistic(X, y, epochs=300, lr=0.5, l2=1e-3):
    """z-score ＋ numpy GD logistic。回傳 (w, b, mu, sd)。"""
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


def predict(w, b, mu, sd, X):
    Z = (X - mu) / sd
    return 1.0 / (1.0 + np.exp(-(Z @ w + b)))


def auc_score(y, s):
    """Mann-Whitney AUC（含平手 0.5 計）。"""
    pos = s[y == 1]
    neg = s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def loio_auc(X, y, groups):
    """留一張（image）交叉驗證 AUC：逐張留出、其餘訓練、集中打分。"""
    scores = np.zeros(len(y), np.float64)
    for g in sorted(set(groups)):
        te = np.array([gi == g for gi in groups])
        tr = ~te
        if y[tr].min() == y[tr].max():   # 訓練側單類 → 全 0.5
            scores[te] = 0.5
            continue
        w, b, mu, sd = fit_logistic(X[tr], y[tr])
        scores[te] = predict(w, b, mu, sd, X[te])
    return auc_score(y, scores), scores


# ─────────────────────────── 主流程（階段 0） ───────────────────────────
def main():
    import eval_rooms_cc as ev
    import floorplan2dxf as fp_bw
    import floorplan2dxf_color as fp_c
    import room_classifier as rc

    st = rc._load("color")
    assert st is not None, "DINOv2 backbone 載入失敗"
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_c = fp_c.load_config("config_color.ini")
    root = "testdata/Identify_ans/own_dataset_color"
    rows = []
    import glob
    for d in sorted(glob.glob(os.path.join(root, "color_floor_*"))):
        sid = os.path.basename(d)
        img = os.path.join("temp/eval_rooms/input", sid + ".png")
        if not os.path.isfile(img):
            continue
        det, _l, _r = ev.run_pipeline(img, cfg_bw, cfg_c, build=False)
        bgr1 = det.get("bgr")
        if bgr1 is None:
            print(f"{sid}: 無 1x bgr，跳過")
            continue
        sc = det["img_w"] / float(bgr1.shape[1])
        T1 = max(6, int(round(det["T"] / sc)))
        dark1 = [(r_[0] / sc, r_[1] / sc, r_[2] / sc, r_[3] / sc)
                 for r_ in det["rects"]]
        bands = fp_c.white_wall_rects(bgr1, T1, dark_rects=dark1)
        gt = ev.parse_gt(os.path.join(d, "model.svg"), *bgr1.shape[:2])
        if gt is None:
            print(f"{sid}: parse_gt 對位失敗，跳過")
            continue
        kept = 0
        for band in bands:
            lab = band_gt_label(band, gt)
            if lab is None:
                continue
            extract = (band_dino_features_v2
                       if os.environ.get("BAND_FEAT") == "v2"
                       else band_dino_features)
            fd = extract(st, bgr1, band, T1)
            if fd is None:
                continue
            fh = band_hand_features(bgr1, band, T1, dark1)
            rows.append({"img": sid, "band": [float(v) for v in band],
                         "label": lab, "dino": fd.tolist(),
                         "hand": fh.tolist()})
            kept += 1
        print(f"{sid}: 帶 {len(bands)} 標到 {kept}")

    y = np.array([1 if r["label"] == "true" else 0 for r in rows])
    groups = [r["img"] for r in rows]
    Xd = np.array([r["dino"] for r in rows], np.float64)
    Xh = np.array([r["hand"] for r in rows], np.float64)
    res = {}
    for tag, X in (("dino", Xd), ("hand", Xh),
                   ("both", np.hstack([Xd, Xh]))):
        auc, scores = loio_auc(X, y, groups)
        res[tag] = auc
        for r, s in zip(rows, scores):
            r["score_" + tag] = round(float(s), 4)
        print(f"AUC[{tag}] = {auc:.3f}")
    print(f"樣本: {len(rows)}（true {int(y.sum())} / fake {int((1-y).sum())}）")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # 原始特徵落 npz 供離線變體實驗（PCA/差分/加權），免重抽
    np.savez_compressed(OUT.replace(".json", ".npz"),
                        Xd=Xd, Xh=Xh, y=y,
                        groups=np.array(groups),
                        bands=np.array([r["band"] for r in rows], np.float32))
    json.dump({"auc": res, "n": len(rows),
               "n_true": int(y.sum()), "n_fake": int((1 - y).sum()),
               "details": [{k: v for k, v in r.items() if k != "dino"}
                           for r in rows]},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"報表 → {OUT}")


if __name__ == "__main__":
    main()
