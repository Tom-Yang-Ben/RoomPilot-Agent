#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""opening_classifier.py — 牆開口的本地分類器(窗 / 非窗)。

傳統 CV 規則的天花板案例(窗簾弧≈門弧、空心牆≈窗、窗符號被吸進牆塊)改用
「訓練出來的判斷」解決:HOG 形狀特徵 + 結構量測 + 嶺回歸線性分類器。

- 樣本:管線自己的候選(收錄/被殺/提案)對 pngans/ 標準答案自動標注
- 驗證:leave-one-floor-out(逐張圖留出)交叉驗證,防止「背答案」
- HOG 與分類器都是純 numpy 自實作(OpenCV 5 移除了 HOGDescriptor 與 ml 模組),
  零新依賴、毫秒級推論、輸出確定性 —— 取代實測不可靠的免費 VLM 仲裁

模型檔:同目錄 opening_model.npz(權重+偏置+特徵版本)。
沒有模型檔時 available() 回 False,管線沿用純 CV 判斷。
"""
from __future__ import annotations

import math
import os

import cv2
import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(os.path.dirname(_DIR))
MODEL_PATH = os.environ.get(
    "ROOMPILOT_OPENING_MODEL",
    os.path.join(_PROJECT_DIR, ".runtime", "floorplan", "opening_model.npz"),
)
FEATURE_VERSION = 6

_model = None
_model_loaded = False


def available() -> bool:
    """實驗性功能,預設關閉(FP2DXF_SVM=1 才啟用)。

    LOOCV 93.1% 的分類器拿來當「裁判」會把 CV 已判對的改錯:實測出摺分數上,
    誤抓與真窗、誤殺與真門的分數區間重疊,不存在安全的干預門檻(詳見
    README 2026-07-13 記錄)。保留模型與訓練管線,作為學習式辨識的地基。"""
    if os.environ.get("FP2DXF_SVM") != "1":
        return False
    return _load() is not None


def _load():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    _model_loaded = True
    if os.path.isfile(MODEL_PATH):
        try:
            data = np.load(MODEL_PATH)
            if int(data["feature_version"]) == FEATURE_VERSION:
                _model = (data["w"].astype(np.float64), float(data["b"]))
        except Exception:
            _model = None
    return _model


def _arc_run(thin, cx, cy, r, ux, vx, uy, vy):
    """與 floorplan2dxf._arc_run 相同的 90 度弧掃描(避免循環匯入,本地複製)。"""
    Himg, Wimg = thin.shape
    hits = []
    for deg in range(5, 86, 3):
        th = math.radians(deg)
        px = int(cx + r * (math.cos(th) * ux + math.sin(th) * vx))
        py = int(cy + r * (math.cos(th) * uy + math.sin(th) * vy))
        tol = max(2, int(r * 0.07))
        xa, xb = max(0, px - tol), min(Wimg, px + tol + 1)
        ya, yb = max(0, py - tol), min(Himg, py + tol + 1)
        hits.append(1 if (xa < xb and ya < yb and thin[ya:yb, xa:xb].any()) else 0)
    run = mx = 0
    for h in hits:
        run = run + 1 if h else 0
        mx = max(mx, run)
    return mx / len(hits)


def _door_arc_features(thin, orient, box):
    """開口兩端的門弧響應(半徑=開口寬,兩側象限取最大)。門≈1.0,窗多≤0.6。"""
    x0, y0, x1, y1 = box
    if orient == "h":
        g0, g1, c = x0, x1, (y0 + y1) / 2.0
    else:
        g0, g1, c = y0, y1, (x0 + x1) / 2.0
    r = max(6.0, g1 - g0)
    best0 = best1 = 0.0
    for side in (1, -1):
        for leaf, end in ((1, g0), (-1, g1)):
            if orient == "h":
                v = _arc_run(thin, end, c, r, leaf, 0, 0, side)
            else:
                v = _arc_run(thin, c, end, r, 0, side, leaf, 0)
            if end == g0:
                best0 = max(best0, v)
            else:
                best1 = max(best1, v)
    return best0, best1


def _resample(profile: np.ndarray, n: int) -> np.ndarray:
    """一維剖面重取樣到固定 n 格(尺寸不變性)。"""
    if profile.size == 0:
        return np.zeros(n)
    src = np.linspace(0, profile.size - 1, n)
    return np.interp(src, np.arange(profile.size), profile.astype(np.float64))


def _scallop_score(thin, orient, box, side_dist):
    """窗簾扇貝弧密度:窗簾=沿窗一排小半圓,門=單一大弧。
    在開口室側 side_dist 處沿窗掃小半徑弧響應,取多點平均——
    窗簾多點皆有響應、門只有鉸鏈端一點有。"""
    x0, y0, x1, y1 = box
    if orient == "h":
        g0, g1, c = x0, x1, (y0 + y1) / 2.0
    else:
        g0, g1, c = y0, y1, (x0 + x1) / 2.0
    length = max(6.0, g1 - g0)
    r = max(4.0, length / 6.0)
    centers = [g0 + length * f for f in (0.2, 0.4, 0.6, 0.8)]
    best = 0.0
    for side in (1, -1):
        vals = []
        for gc in centers:
            if orient == "h":
                v = max(_arc_run(thin, gc, c + side * side_dist, r, 1, 0, 0, side),
                        _arc_run(thin, gc, c + side * side_dist, r, -1, 0, 0, side))
            else:
                v = max(_arc_run(thin, c + side * side_dist, gc, r, 0, side, 1, 0),
                        _arc_run(thin, c + side * side_dist, gc, r, 0, side, -1, 0))
            vals.append(v)
        best = max(best, float(np.mean(vals)))
    return best


def extract(orig_bw, thin, T, orient, box, soft=None) -> np.ndarray:
    """候選開口 → 工程化結構特徵(42 維)。小樣本跨圖風格要泛化,
    靠的是尺寸正規化後的「剖面形狀」而不是高維原始外觀:

    - 跨牆向覆蓋剖面 12 格:每個跨牆位置有多少比例被沿牆線覆蓋——
      空心牆=兩端兩個峰、窗=3~4 個峰(含中間玻璃線)、門=全空、門檻=單峰
    - 沿牆向填墨剖面 10 格:窗沿開口均勻、家具線/子段只蓋一部分
    - 門弧響應 6 維 + 窗簾扇貝弧 2 維:門=單一大弧、窗簾=一排小弧
    - 端蓋 2 維:窗符號兩端的封口豎線(空心牆沒有,直通牆交點)
    - 幾何與端點錨定 + soft 線群數
    """
    Himg, Wimg = orig_bw.shape
    x0, y0, x1, y1 = (float(v) for v in box)
    length = max(2.0, (x1 - x0) if orient == "h" else (y1 - y0))
    thick = max(2.0, (y1 - y0) if orient == "h" else (x1 - x0))
    pad = max(2, int(round(0.3 * T)))

    def clip_box(a0, b0, a1, b1):
        return (max(0, int(a0)), max(0, int(b0)), min(Wimg, int(a1)), min(Himg, int(b1)))

    if orient == "h":
        bx0, by0, bx1, by1 = clip_box(x0, y0 - pad, x1, y1 + pad)
        band = orig_bw[by0:by1, bx0:bx1]
    else:
        bx0, by0, bx1, by1 = clip_box(x0 - pad, y0, x1 + pad, y1)
        band = orig_bw[by0:by1, bx0:bx1].T      # 轉成「列=跨牆向、行=沿牆向」
    if not band.size:
        band = np.zeros((4, 4), np.uint8)

    cross_cov = (band > 0).mean(axis=1)          # 每個跨牆位置的沿牆覆蓋率
    along_fill = (band > 0).mean(axis=0)         # 每個沿牆位置的跨牆填墨率
    cross_prof = _resample(cross_cov, 12)
    along_prof = _resample(along_fill, 10)

    groups = prev = 0                            # 貫穿線群數(覆蓋 ≥0.7 的跨牆位置)
    for v in cross_cov:
        cur = v >= 0.7
        if cur and not prev:
            groups += 1
        prev = cur

    # 門弧響應:兩端點 × 全寬/半寬
    if thin is not None:
        arc0, arc1 = _door_arc_features(thin, orient, (x0, y0, x1, y1))
        if orient == "h":
            g0, g1, c = x0, x1, (y0 + y1) / 2.0
            half0 = max(_arc_run(thin, g0, c, length / 2, 1, 0, 0, s) for s in (1, -1))
            half1 = max(_arc_run(thin, g1, c, length / 2, -1, 0, 0, s) for s in (1, -1))
        else:
            g0, g1, c = y0, y1, (x0 + x1) / 2.0
            half0 = max(_arc_run(thin, c, g0, length / 2, 0, s, 1, 0) for s in (1, -1))
            half1 = max(_arc_run(thin, c, g1, length / 2, 0, s, -1, 0) for s in (1, -1))
    else:
        arc0 = arc1 = half0 = half1 = 0.0

    # 端點錨定:兩端外側 0.8T 是否有實牆(窗至少一端接牆墩)
    d = max(3, int(round(0.8 * T)))
    def solid_at(lo, hi, c0, c1):
        blk = orig_bw[max(0, int(c0)):min(Himg, int(c1)), max(0, int(lo)):min(Wimg, int(hi))] \
            if orient == "h" else \
            orig_bw[max(0, int(lo)):min(Himg, int(hi)), max(0, int(c0)):min(Wimg, int(c1))]
        return float((blk > 0).mean()) if blk.size else 0.0
    if orient == "h":
        end0 = solid_at(x0 - d, x0, y0, y1)
        end1 = solid_at(x1, x1 + d, y0, y1)
    else:
        end0 = solid_at(y0 - d, y0, x0, x1)
        end1 = solid_at(y1, y1 + d, x0, x1)

    # 端蓋:開口兩端「帶內」的短豎線(窗符號有封口,空心牆直通交點沒有)
    capw = max(2, int(round(0.15 * T)))
    def cap_at(lo):
        if orient == "h":
            blk = orig_bw[by0:by1, max(0, int(lo)):min(Wimg, int(lo) + capw)]
            return float((blk.max(axis=1) > 0).mean()) if blk.size else 0.0
        blk = orig_bw[max(0, int(lo)):min(Himg, int(lo) + capw), bx0:bx1]
        return float((blk.max(axis=0) > 0).mean()) if blk.size else 0.0
    cap0 = cap_at((x0 if orient == "h" else y0))
    cap1 = cap_at((x1 if orient == "h" else y1) - capw)

    # 窗簾扇貝弧(室側兩個距離取大)vs 門單弧
    if thin is not None:
        scallop = max(_scallop_score(thin, orient, (x0, y0, x1, y1), thick),
                      _scallop_score(thin, orient, (x0, y0, x1, y1), thick + 0.5 * length / 6))
    else:
        scallop = 0.0

    # soft(寬鬆二值化)帶內線群數:淺灰玻璃線只有 soft 看得到
    soft_groups = 0
    if soft is not None:
        sband = soft[by0:by1, bx0:bx1] if orient == "h" else soft[by0:by1, bx0:bx1].T
        if sband.size:
            scov = (sband > 0).mean(axis=1)
            prev2 = False
            for v in scov:
                cur = v >= 0.7
                if cur and not prev2:
                    soft_groups += 1
                prev2 = cur

    # 內部貫穿線:排除跨牆向兩緣 20% 後,中央區有幾條沿窗長中段(70%)覆蓋 ≥0.5 的線。
    # 真窗=牆面兩線之外「多出」玻璃線 ≥1;空心牆/門洞=0(這是視覺上最硬的區別)。
    def _mid_lines(b):
        if b.shape[0] < 5 or not b.size:
            return 0
        m = max(1, int(round(0.2 * b.shape[0])))
        core = b[m:-m]
        if not core.size:
            return 0
        q = max(1, int(round(0.15 * b.shape[1])))
        seg = core[:, q:-q] if b.shape[1] > 2 * q else core
        cov = (seg > 0).mean(axis=1)
        cnt = prev2 = 0
        for v in cov:
            cur = v >= 0.5
            if cur and not prev2:
                cnt += 1
            prev2 = cur
        return cnt
    mid_lines = _mid_lines(band)
    mid_lines_soft = 0
    if soft is not None:
        sband2 = soft[by0:by1, bx0:bx1] if orient == "h" else soft[by0:by1, bx0:bx1].T
        mid_lines_soft = _mid_lines(sband2)

    # 延伸對比:沿同一條牆線往兩端各取 0.5 倍開口長的延伸帶,跨牆剖面與帶內的差異。
    # 空心牆=段內外同構(差異≈0)、真窗=局部多出玻璃線(差異大)。
    def _ext_profile(sign):
        extl = max(4, int(round(0.5 * length)))
        if orient == "h":
            ex0 = int(x1) if sign > 0 else int(x0) - extl
            blk = orig_bw[by0:by1, max(0, ex0):min(Wimg, ex0 + extl)]
        else:
            ey0 = int(y1) if sign > 0 else int(y0) - extl
            blk = orig_bw[max(0, ey0):min(Himg, ey0 + extl), bx0:bx1].T
        if not blk.size:
            return None
        return _resample((blk > 0).mean(axis=1), 12)
    diffs = []
    for sign in (1, -1):
        prof = _ext_profile(sign)
        if prof is not None:
            diffs.append(float(np.abs(cross_prof - prof).mean()))
    ext_contrast = min(diffs) if diffs else 0.5   # 取小=與「較像的那側」比

    fill = float((band > 0).mean())
    scalars = np.array([
        fill,
        float(np.std(along_fill)),
        min(groups, 6) / 6.0,
        min(length / max(T, 1), 20.0) / 20.0,
        min(thick / max(T, 1), 5.0) / 5.0,
        min(length / thick, 25.0) / 25.0,
        arc0, arc1, max(half0, half1), min(half0, half1) if (half0 and half1) else 0.0,
        scallop,
        max(arc0, arc1) - scallop,               # 門弧扣掉扇貝弧:真門為正、窗簾為負
        cap0, cap1,
        min(soft_groups, 6) / 6.0,
        min(mid_lines, 4) / 4.0,
        min(mid_lines_soft, 4) / 4.0,
        min(ext_contrast, 1.0),
    ], np.float64)
    ends = np.array([end0, end1], np.float64)
    return np.concatenate([cross_prof, along_prof, scalars, ends])


def scores(orig_bw, thin, T, items, soft=None) -> np.ndarray:
    """items = [(orient, x0, y0, x1, y1), ...] → 決策分數(正=窗)。無模型回空陣列。"""
    model = _load()
    if model is None or not items:
        return np.zeros(0)
    w, b = model
    feats = np.stack([extract(orig_bw, thin, T, it[0], it[1:], soft=soft) for it in items])
    return feats @ w + b


def judge_openings(orig_bw, thin, T, items, soft=None) -> dict[int, str]:
    """items → {索引: "window"|"other"}(以分數正負判)。"""
    s = scores(orig_bw, thin, T, items, soft=soft)
    return {i: ("window" if v > 0 else "other") for i, v in enumerate(s)}


def train(features: np.ndarray, labels: np.ndarray, lam: float = 1.0):
    """嶺回歸線性分類器(labels: 1=窗 → +1,0=非窗 → −1)。

    dual form:α = (XXᵀ + λI)⁻¹ y、w = Xᵀα —— n(樣本數)級矩陣求逆,
    n≈數百時瞬間完成;完全確定性。回傳 (w, b)。
    """
    X = features.astype(np.float64)
    y = labels.astype(np.float64) * 2.0 - 1.0
    mu = X.mean(axis=0)
    Xc = X - mu
    G = Xc @ Xc.T
    alpha = np.linalg.solve(G + lam * np.eye(len(y)), y)
    w = Xc.T @ alpha
    b = float(-mu @ w)
    return w, b


def save(w: np.ndarray, b: float, extra_meta: dict | None = None) -> None:
    meta = extra_meta or {}
    np.savez_compressed(MODEL_PATH, w=w, b=np.float64(b),
                        feature_version=np.int64(FEATURE_VERSION),
                        **{k: np.asarray(v) for k, v in meta.items()})
