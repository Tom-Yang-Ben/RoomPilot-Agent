"""白牆帶偵測（white_wall_rects）——色塊分割線第一個出貨件。

棄守畫風（color_floor_07/08/09）的牆＝「兩片色染地板之間的白色窄帶」，
描邊極淡（gray 189~200）暗色偵測原理性抓不到。反向偵測：meanshift
平滑 → 白色 top-hat 剝窄帶 → 方向性長核濾磁磚格 → 帶級側翼驗證
（沿法向採樣：≥一側色染 ≥50%、另一側非黑）。"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 10


def _scene():
    """400x300：左右兩片色染地板夾一條白牆帶；一條磁磚縫（短）；
    一條懸空白帶（兩側無色染）。"""
    bgr = np.full((300, 400, 3), 246, np.uint8)
    bgr[40:260, 30:180] = (140, 170, 200)        # 左房木色地板
    bgr[40:260, 200:370] = (150, 200, 170)       # 右房綠灰地板
    bgr[40:260, 180:200] = 246                   # 白牆帶（寬 20=2T）
    bgr[100:130, 80:100] = 246                   # 左房內白色小塊（家具）
    return bgr


def test_white_band_between_tints_detected():
    bgr = _scene()
    rects = fp_c.white_wall_rects(bgr, T)
    hits = [r for r in rects
            if r[0] <= 185 and r[2] >= 195 and (r[3] - r[1]) >= 150]
    assert hits, f"色染間白牆帶應被偵測：{rects}"


def test_floating_white_band_rejected():
    # 兩側都無色染的白帶（圖框緣）——不收
    bgr = np.full((300, 400, 3), 246, np.uint8)
    bgr[40:260, 180:200] = 255
    assert fp_c.white_wall_rects(bgr, T) == []


def test_furniture_white_patch_rejected():
    # 色染房內的白色家具塊（寬 > 2T）——top-hat 剝不出窄帶，不收
    bgr = np.full((300, 400, 3), 246, np.uint8)
    bgr[40:260, 30:370] = (140, 170, 200)
    bgr[100:200, 150:260] = 246                  # 110px 寬白塊
    rects = fp_c.white_wall_rects(bgr, T)
    assert all((r[2] - r[0]) < 60 or (r[3] - r[1]) < 60 for r in rects), \
        f"寬白家具塊不得成牆：{rects}"
