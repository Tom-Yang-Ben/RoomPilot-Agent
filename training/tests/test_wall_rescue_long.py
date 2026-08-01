"""灰度過濾的長牆豁免——木紋牆不再被色度/紋理規則誤刪。

floor_09 實案：暖棕木紋牆（厚≈T、長 9~14T、灰度核心極暗 p25 36~47）
被色度規則（chroma>18 或 chroma>12＋spread>30）整段刪除，左半戶灌水
漏到影像邊界整片判室外（命中 1/7）。與家具邊線的可分維度是長度——
該圖 34 個真刪除候選中家具全部 <5T，真牆全部 ≥8T。

豁免條件（全部成立才留）：厚 ≤1.5T、長 ≥8T、p25 ≤ ref+δ/2（核心夠
暗，非淺色櫃體）、chroma ≤30（暖棕可過、彩色家具面不行）。"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 20
DELTA = 25.0


def _scene():
    """400x400：一段深灰基準牆（定 ref）＋一段木紋長牆＋一段木紋短櫃。"""
    bgr = np.full((400, 400, 3), 245, np.uint8)
    bw = np.zeros((400, 400), np.uint8)
    # 基準牆：深灰(35)、無色度，佔大面積 → ref≈35
    bgr[20:40, 20:380] = 35
    bw[20:40, 20:380] = 255
    ref_wall = (20, 20, 380, 40)
    # 木紋長牆：厚 16(≤1.5T)、長 240(=12T)，BGR 暖棕（B<R，chroma≈24）
    # 帶木紋（亮暗交替 → spread>30）
    for i, x in enumerate(range(80, 320)):
        v = 30 if (i // 6) % 2 == 0 else 75
        bgr[200:216, x] = (v, v + 10, v + 24)
    bw[200:216, 80:320] = 255
    long_wall = (80, 200, 320, 216)
    # 木紋短櫃：同材質、長 80(=4T) → 該刪
    for i, x in enumerate(range(100, 180)):
        v = 30 if (i // 6) % 2 == 0 else 75
        bgr[300:316, x] = (v, v + 10, v + 24)
    bw[300:316, 100:180] = 255
    cabinet = (100, 300, 180, 316)
    return bgr, bw, [ref_wall, long_wall, cabinet]


def test_long_grain_wall_rescued_short_cabinet_dropped(monkeypatch):
    # 豁免預設關閉（衣櫃長邊同為長細深木紋會被誤救，dev 淨 ±0）——
    # 本測試驗證「開啟時」的行為契約，供後續找到牆/衣櫃可分維度再啟用
    monkeypatch.setattr(fp_c, "WALL_RESCUE_LONG", True)
    bgr, bw, rects = _scene()
    kept, _p, dropped, _rec = fp_c.drop_light_rects(
        rects, [], bgr, bw, bw, DELTA, T)
    assert rects[1] in kept, "木紋長牆（12T）應被長牆豁免留下"
    assert rects[2] not in kept, "木紋短櫃（4T）仍應被色度規則刪除"
    assert rects[0] in kept


def test_long_grain_wall_dropped_when_disabled():
    bgr, bw, rects = _scene()
    kept, _p, _d, _rec = fp_c.drop_light_rects(
        rects, [], bgr, bw, bw, DELTA, T)
    assert rects[1] not in kept, "預設關閉時木紋長牆仍走色度刪除"
