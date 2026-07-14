#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seg_infer.py — 分割模型(U-Net,雲端微調 CubiCasa5k)本地推論。

「雲端訓練、本地推論」:模型在 Kaggle GPU 上微調成 floorseg.onnx(~93MB),
這裡用 onnxruntime 在 M2 CPU 上跑,一張圖 160~220ms。輸出每個像素的類別
(0=背景 1=牆 2=窗 3=門),我們取窗類連通塊當「模型偵測到的窗」。

角色:規則管線(floorplan2dxf)的第二意見。單獨精準率不如規則(領域落差:
訓練用芬蘭圖風),但與規則融合後召回率提升、且兩者交集近乎零誤抓
(見 README 2026-07-14 的對決表)。onnxruntime 未裝或模型檔不存在時 available()
回 False,管線退回純規則,不影響既有行為。
"""
from __future__ import annotations

import os

import cv2
import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_DIR, "models", "floorseg.onnx")

# 訓練時的正規化(ImageNet 統計)——推論必須一致
_MEAN = np.array([0.485, 0.456, 0.406])
_STD = np.array([0.229, 0.224, 0.225])
_SIDE = 512                                    # 訓練輸入長邊

_session = None
_session_tried = False


def available() -> bool:
    if os.environ.get("FP2DXF_SEG") == "0":
        return False
    return _load() is not None


def _load():
    global _session, _session_tried
    if _session_tried:
        return _session
    _session_tried = True
    if not os.path.isfile(MODEL_PATH):
        return None
    try:
        import onnxruntime as ort

        _session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
    except Exception:
        _session = None
    return _session


def _predict(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """整張圖 → (逐像素類別遮罩, 窗類 softmax 機率圖),皆原圖尺寸。失敗回 None。"""
    sess = _load()
    if sess is None:
        return None
    h, w = bgr.shape[:2]
    k = _SIDE / max(h, w)
    nh, nw = max(32, int(h * k) // 32 * 32), max(32, int(w * k) // 32 * 32)
    rgb = cv2.cvtColor(cv2.resize(bgr, (nw, nh)), cv2.COLOR_BGR2RGB) / 255.0
    x = ((rgb - _MEAN) / _STD).transpose(2, 0, 1)[None].astype("float32")
    try:
        logits = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    except Exception:
        return None
    ex = np.exp(logits - logits.max(0))
    prob = ex / ex.sum(0)                          # softmax over 4 類
    pred = cv2.resize(logits.argmax(0).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    winprob = cv2.resize(prob[2], (w, h))          # 窗類機率
    return pred, winprob


def detect_windows(bgr: np.ndarray, min_area: int = 60) -> list[tuple[str, float, float, float, float, float]]:
    """模型偵測到的窗 → [(orient, x0, y0, x1, y1, conf)](影像 px)。

    conf = 該窗塊內窗類 softmax 機率均值(模型自信度)——融合層用它當閘門:
    模型很有把握、規則又沒看到的窗才追加(seg 信心對自己的預測比外部分類器可靠)。
    orient 由 bbox 長邊決定(橫窗 h / 豎窗 v),供融合層與規則結果配對。
    """
    got = _predict(bgr)
    if got is None:
        return []
    pred, winprob = got
    win = (pred == 2).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(win, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < min_area:
            continue
        blk = win[y:y + h, x:x + w] > 0
        conf = float(winprob[y:y + h, x:x + w][blk].mean()) if blk.any() else 0.0
        orient = "h" if w >= h else "v"
        out.append((orient, float(x), float(y), float(x + w), float(y + h), conf))
    return out
