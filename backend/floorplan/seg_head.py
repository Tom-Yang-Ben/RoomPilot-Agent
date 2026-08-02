# -*- coding: utf-8 -*-
"""seg_head — 監督式分割頭的語意牆帶（色塊分割線，2026-08-03）。

背景：彩色棄守畫風的「近白暗示牆」暗色/白帶偵測都抓不到（帶級三角度
量測皆低天花板，見 COLOR_PIPELINE_PLAN）。本模組把 DINOv2 patch 特徵
＋線性頭（19 張彩 dev GT 訓練，LOIO patch AUC 0.974）的機率圖轉成
「低機率脊線＝語意牆帶」，餵給白牆救援 flood——門洞由既有門尺寸縫
封口機制處理，語意層只補牆證據。

資產 `seg_head.npz`（w/b/mu/sd/backbone/max_side）缺檔＝停用出聲、
行為不變。骨幹重用 room_classifier 的共用載入。
"""
import os

import cv2
import numpy as np

ASSET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "seg_head.npz")
PATCH = 14
RIDGE_P = 0.45          # 低於此機率的房內縫隙視為語意牆脊
_state_cache = "unloaded"

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def load_state():
    """資產＋骨幹；缺件回 None（停用出聲一次）。"""
    global _state_cache
    if _state_cache != "unloaded":
        return _state_cache
    _state_cache = None
    if not os.path.isfile(ASSET_PATH):
        print(f"⚠ seg_head 資產不存在（{os.path.basename(ASSET_PATH)}）"
              "→ 語意牆帶停用")
        return _state_cache
    import room_classifier as rc
    st = rc._load("color")
    if st is None:
        print("⚠ seg_head: DINOv2 骨幹不可用 → 語意牆帶停用")
        return _state_cache
    z = np.load(ASSET_PATH, allow_pickle=False)
    if str(z["backbone"]) != st["backbone"]:
        print(f"⚠ seg_head 骨幹不符（{z['backbone']} vs {st['backbone']}）"
              "→ 語意牆帶停用")
        return _state_cache
    _state_cache = {"torch": st["torch"], "model": st["model"],
                    "w": z["w"], "b": float(z["b"]),
                    "mu": z["mu"], "sd": z["sd"],
                    "max_side": int(z["max_side"])}
    return _state_cache


def prob_map(bgr, st=None):
    """1x bgr → patch 機率格（房內機率）。停用回 None。"""
    st = st if st is not None else load_state()
    if st is None or bgr is None:
        return None
    torch, model = st["torch"], st["model"]
    h, w = bgr.shape[:2]
    s = min(1.0, st["max_side"] / max(h, w))
    nh = max(PATCH, int(round(h * s / PATCH)) * PATCH)
    nw = max(PATCH, int(round(w * s / PATCH)) * PATCH)
    img = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    x = (cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
         / 255.0 - _MEAN) / _STD
    with torch.no_grad():
        t = torch.from_numpy(x.transpose(2, 0, 1)[None])
        f = model.get_intermediate_layers(t, 1, reshape=True)[0]
        f = f[0].permute(1, 2, 0).cpu().numpy()
    Z = (f - st["mu"]) / st["sd"]
    logit = Z @ st["w"] + st["b"]
    return 1.0 / (1.0 + np.exp(-logit))


def ridge_bands(prob, shape_1x, T):
    """機率格 → 語意牆帶 rects（1x 座標）。

    脊線＝房內縫隙的低機率帶：p < RIDGE_P 且兩側（法向 ±2 patch 內）
    皆有房內（p>0.5）——大片背景兩側無房，不會整片變牆。方向性長核
    掃 h/v，帶長 ≥3T、厚 ≤2.5T（過厚裁到中線 ±1.25T）。"""
    H, W = shape_1x
    p_up = cv2.resize(prob.astype(np.float32), (W, H),
                      interpolation=cv2.INTER_LINEAR)
    interior = (p_up > 0.5).astype(np.uint8)
    low = (p_up < RIDGE_P).astype(np.uint8)
    reach = max(2 * PATCH, int(round(2.5 * T)) + 2)
    kx = np.ones((1, reach), np.uint8)
    ky = np.ones((reach, 1), np.uint8)
    # 兩側皆有房內（單側＝建物外緣，外牆已有暗牆 rects，不重複產帶）：
    # anchor 偏置 dilate——(0,0) 看正向、(len-1) 看反向
    int_r = cv2.dilate(interior, kx, anchor=(0, 0))
    int_l = cv2.dilate(interior, kx, anchor=(reach - 1, 0))
    int_d = cv2.dilate(interior, ky, anchor=(0, 0))
    int_u = cv2.dilate(interior, ky, anchor=(0, reach - 1))
    near_h = int_u & int_d                       # 橫縫：上下皆房內
    near_v = int_l & int_r                       # 豎縫：左右皆房內
    out = []
    for horiz, ker, near in ((True, cv2.getStructuringElement(
                                  cv2.MORPH_RECT, (3 * T, 1)), near_h),
                             (False, cv2.getStructuringElement(
                                  cv2.MORPH_RECT, (1, 3 * T)), near_v)):
        seam = cv2.morphologyEx(low & near, cv2.MORPH_OPEN, ker)
        n, _lab, stt, _c = cv2.connectedComponentsWithStats(seam, 8)
        for i in range(1, n):
            x, y, w_, h_ = (int(stt[i, 0]), int(stt[i, 1]),
                            int(stt[i, 2]), int(stt[i, 3]))
            th = h_ if horiz else w_
            ln = w_ if horiz else h_
            if ln < 3 * T:
                continue
            if th > 2.5 * T:                     # 過厚裁到中線附近
                if horiz:
                    cyy = y + h_ / 2.0
                    y = int(round(cyy - 1.25 * T))
                    h_ = int(round(2.5 * T))
                else:
                    cxx = x + w_ / 2.0
                    x = int(round(cxx - 1.25 * T))
                    w_ = int(round(2.5 * T))
            out.append((float(x), float(y), float(x + w_), float(y + h_)))
    return out


def wall_bands(bgr, T):
    """1x bgr → 語意牆帶 rects（1x）。停用回 []。"""
    st = load_state()
    if st is None:
        return []
    p = prob_map(bgr, st)
    if p is None:
        return []
    return ridge_bands(p, bgr.shape[:2], T)
