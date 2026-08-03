"""帶級 DINO 語意判別——弱標籤器與帶幾何工具（白牆萃取品質輪，TDD）。

spec: docs/superpowers/specs/2026-08-02-band-semantics-design.md
帶 = (x0, y0, x1, y1) 軸對齊矩形（white_wall_rects 輸出，1x 座標）。
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "training", "scripts"))

import probe_band_semantics as pbs


def _gt_two_rooms():
    """100x100 圖、兩房夾一條 y=48..52 的水平牆廊道。"""
    a = np.zeros((100, 100), bool)
    b = np.zeros((100, 100), bool)
    a[10:48, 10:90] = True
    b[52:90, 10:90] = True
    return [("Bedroom", a), ("LivingRoom", b)]


def test_label_band_in_corridor_is_true_wall():
    gt = _gt_two_rooms()
    assert pbs.band_gt_label((10, 48, 90, 52), gt) == "true"


def test_label_band_inside_room_is_fake():
    gt = _gt_two_rooms()
    assert pbs.band_gt_label((20, 25, 80, 29), gt) == "fake"


def test_label_ambiguous_band_dropped():
    gt = _gt_two_rooms()
    # 帶一半在房內、一半在廊道＋房外 → 落 30~70% 灰區 → 棄標
    assert pbs.band_gt_label((10, 44, 90, 52), gt) is None


def test_band_region_expands_normal_and_clips():
    # 水平帶：法向（y）±2.5T 展開、帶長方向不動；越界裁到圖框
    x0, y0, x1, y1 = pbs.band_region((10, 48, 90, 52), T=4, shape=(100, 100))
    assert (x0, x1) == (10, 90)
    assert (y0, y1) == (38, 62)
    x0, y0, x1, y1 = pbs.band_region((10, 2, 90, 6), T=4, shape=(100, 100))
    assert (y0, y1) == (0, 16)          # 上緣越界裁剪


def test_band_region_vertical():
    x0, y0, x1, y1 = pbs.band_region((48, 10, 52, 90), T=4, shape=(100, 100))
    assert (y0, y1) == (10, 90)
    assert (x0, x1) == (38, 62)


def test_hand_features_shape_and_ratio():
    bgr = np.full((100, 100, 3), 255, np.uint8)
    bgr[:48] = (60, 120, 200)            # 上房色染
    bgr[52:] = (200, 120, 60)            # 下房色染
    f = pbs.band_hand_features(bgr, (10, 48, 90, 52), T=4, dark_rects=[])
    assert f.shape == (pbs.N_HAND,)
    assert f[0] > 10.0                   # 長厚比 80/4=20
