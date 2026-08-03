"""空心雙線牆偵測（hollow_wall_rects）——color 圖第二種牆畫法。

floor_07/08 實案：內牆畫成「兩條 ~4px 深色描邊夾 ~13px 白色填充」
（1x 尺度；管線 2x 後約 8/26/8），外牆與基柱才是實心黑。detect_solid
只認實心深色條，雙線牆的細描邊活不過開運算 → 內牆全漏、整戶黏成一塊
（floor_08 命中 1/7、floor_07 直接 seg_fail）。

hollow_wall_rects 的驗收條件：深色雙線之間的填充必須是「白色中性」
（gray 高、chroma 低）；彩色填充（木地板、家具面）與孤線不得成牆。"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 18          # floor_08 實測自動牆厚（2x 尺度）


def _canvas(w=800, h=600):
    bw = np.zeros((h, w), np.uint8)
    gray = np.full((h, w), 245, np.uint8)      # 底＝白紙
    chroma = np.zeros((h, w), np.uint8)
    return bw, gray, chroma


def _double_line(bw, gray, chroma, x, y0, y1, line=8, gap=26,
                 fill_gray=250, fill_chroma=2):
    """畫一道垂直空心雙線牆：兩條深線夾填充。"""
    bw[y0:y1, x:x + line] = 255
    bw[y0:y1, x + line + gap:x + line + gap + line] = 255
    gray[y0:y1, x:x + line] = 10
    gray[y0:y1, x + line + gap:x + line + gap + line] = 10
    gray[y0:y1, x + line:x + line + gap] = fill_gray
    chroma[y0:y1, x + line:x + line + gap] = fill_chroma


def test_hollow_double_line_wall_detected():
    bw, gray, chroma = _canvas()
    _double_line(bw, gray, chroma, x=100, y0=50, y1=550)
    rects = fp_c.hollow_wall_rects(bw, gray, chroma, T)
    assert len(rects) == 1, f"雙線白填充應成一道牆：{rects}"
    x0, y0, x1, y1 = rects[0]
    assert x0 <= 102 and x1 >= 140, f"牆帶應涵蓋兩線全寬：{rects[0]}"
    assert y1 - y0 >= 400, f"牆帶應沿線全長：{rects[0]}"


def test_colored_fill_not_wall():
    # 兩條深線夾「彩色」填充（木地板/家具）——不得成牆
    bw, gray, chroma = _canvas()
    _double_line(bw, gray, chroma, x=100, y0=50, y1=550,
                 fill_gray=170, fill_chroma=60)
    assert fp_c.hollow_wall_rects(bw, gray, chroma, T) == []


def test_isolated_line_not_wall():
    # 孤線（無成對線）——閉運算搭不到對側，不得成牆
    bw, gray, chroma = _canvas()
    bw[50:550, 100:108] = 255
    gray[50:550, 100:108] = 10
    assert fp_c.hollow_wall_rects(bw, gray, chroma, T) == []


def test_wide_white_room_not_wall():
    # 兩道相距 3T 的實線（房間兩側牆，中間是白色房間）——間距超過
    # 填充上限，不得黏成一塊假牆
    bw, gray, chroma = _canvas()
    d = int(3 * T)
    bw[50:550, 100:108] = 255
    bw[50:550, 108 + d:116 + d] = 255
    gray[50:550, 100:108] = 10
    gray[50:550, 108 + d:116 + d] = 10
    assert fp_c.hollow_wall_rects(bw, gray, chroma, T) == []


def test_existing_solid_wall_not_duplicated():
    # 實心牆已由 detect_solid 負責——hollow 偵測不該對實心條出手
    bw, gray, chroma = _canvas()
    bw[50:550, 100:100 + T] = 255
    gray[50:550, 100:100 + T] = 10
    assert fp_c.hollow_wall_rects(bw, gray, chroma, T) == []
