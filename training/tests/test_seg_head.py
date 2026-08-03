"""seg_head 語意牆帶——監督式分割頭的管線接入面（TDD）。

spec: docs/superpowers/specs/2026-08-03-seg-head-design.md（已隨收尾移除，見 git 歷史）
機率圖低機率脊線 → 軸對齊牆帶 rects（1x 座標），餵白牆救援 flood。
資產 backend/floorplan/seg_head.npz 缺檔＝停用（回空清單、不炸）。
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "backend", "floorplan"))

import seg_head as sh


def _prob_two_rooms(gw=40, gh=30, seam_col=20):
    """兩房夾一條 1-patch 寬的低機率豎縫。"""
    p = np.full((gh, gw), 0.9, np.float32)
    p[:, seam_col] = 0.2
    p[:3, :] = 0.05                      # 外圈背景
    p[-3:, :] = 0.05
    p[:, :3] = 0.05
    p[:, -3:] = 0.05
    return p


def test_ridge_bands_finds_vertical_seam():
    p = _prob_two_rooms()
    H, W, T = 300, 400, 10               # 1x 尺寸與牆厚
    bands = sh.ridge_bands(p, (H, W), T)
    assert bands, "低機率豎縫必須產出牆帶"
    # 至少一條豎帶蓋住縫的 x 位置（grid x=20/40 → 1x x≈200）
    hit = [b for b in bands if (b[2] - b[0]) < (b[3] - b[1])
           and b[0] <= 215 and b[2] >= 195]     # 縫在 x≈200~210（含縮放偏移）
    assert hit, f"豎縫未被帶覆蓋: {bands}"
    # 帶不得寬於 2.5T（過寬會吃掉地板）
    for x0, y0, x1, y1 in hit:
        assert (x1 - x0) <= 2.5 * T + 1


def test_ridge_bands_ignores_background():
    """外圈背景（大片低機率）不是脊線，不得整片變牆。"""
    p = _prob_two_rooms()
    H, W, T = 300, 400, 10
    bands = sh.ridge_bands(p, (H, W), T)
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in bands)
    assert area < 0.15 * H * W, "牆帶總面積失控（背景被當牆）"


def test_missing_asset_disables_quietly(tmp_path, capsys):
    old = sh.ASSET_PATH
    sh._state_cache = "unloaded"
    try:
        sh.ASSET_PATH = str(tmp_path / "nope.npz")
        assert sh.load_state() is None
        assert sh.wall_bands(np.zeros((100, 100, 3), np.uint8), 10) == []
        assert "seg_head" in capsys.readouterr().out
    finally:
        sh.ASSET_PATH = old
        sh._state_cache = "unloaded"
