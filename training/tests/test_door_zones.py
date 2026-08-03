"""產品門位輕量函式（fp_c.door_zones）——門偵測重建首件。

弧掃描 detect_doors 的產品門位 P 0.38/R 0.17 遠低於可用線；
build_rooms 的 zones（門尺寸牆縫＋門扇墨水證據）實測 P 0.86/R 0.75。
把同一把尺做成不需房間層/DINO 的輕量函式，DXF 批次 json 的 doors
欄位直接改源。

規則：_wall_gaps 找 40~260cm 牆縫 → 門尺寸窗（75~100/160~190cm）
→ 門扇墨水證據（開口帶＋兩側迴轉區細線密度 ≥0.5%，扣文字框；
thin=None 不濾照收）。回傳 [(quad, door_tuple)] 同 gap_openings 格式。
"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 10
CM = 1.0                                         # 1 px = 1 cm，數字好讀


def _walls_with_gap(gap_px=90):
    """兩段共線水平牆，中間留 gap_px 的門縫。"""
    y0, y1 = 100, 100 + T
    return [(20, y0, 200, y1), (200 + gap_px, y0, 400, y1)]


def _ink_at_gap(gap_px=90, h=300, w=500):
    """門縫下方迴轉區畫一段弧墨（密度 >0.5%）。"""
    thin = np.zeros((h, w), np.uint8)
    thin[115:150, 210:280] = 255                 # 開口下側迴轉區
    return thin


def test_door_size_gap_with_ink_detected():
    rects = _walls_with_gap(90)
    zones = fp_c.gap_door_zones(rects, [], T, CM, thin=_ink_at_gap(90))
    assert len(zones) == 1, f"90cm 門縫＋弧墨應成門位：{zones}"
    quad, d = zones[0]
    cx = sum(p[0] for p in quad) / 4.0
    assert 230 <= cx <= 260, f"門位中心應在縫中央：{cx}"
    assert abs(d[2] - 90) <= 2, f"門寬應為縫寬：{d[2]}"


def test_no_ink_open_passage_rejected():
    rects = _walls_with_gap(90)
    thin = np.zeros((300, 500), np.uint8)        # 全無墨＝開放通道
    assert fp_c.gap_door_zones(rects, [], T, CM, thin=thin) == []


def test_non_door_width_rejected():
    rects = _walls_with_gap(130)                 # 130cm：非單門也非雙開
    zones = fp_c.gap_door_zones(rects, [], T, CM, thin=_ink_at_gap(130))
    assert zones == [], f"130cm 縫不在門尺寸窗：{zones}"


def test_thin_none_no_filter():
    # 彩圖管線 thin 缺席：墨水濾不動，門尺寸縫照收
    rects = _walls_with_gap(90)
    zones = fp_c.gap_door_zones(rects, [], T, CM, thin=None)
    assert len(zones) == 1


def test_window_on_gap_rejected():
    # 縫上有窗＝窗洞非門
    rects = _walls_with_gap(90)
    wins = [(1, 210, 100, 280, 110)]
    assert fp_c.gap_door_zones(rects, wins, T, CM, thin=_ink_at_gap(90)) == []


def test_json_ranges_catch_borderline():
    # 漏門主宰型態（floor48 實案）：105cm 縫在嚴窗外 1~5cm——JSON
    # 產品路放寬窗（70-110/150-200）要撈回，房間層預設嚴窗維持拒收
    rects = _walls_with_gap(105)
    strict = fp_c.gap_door_zones(rects, [], T, CM, thin=_ink_at_gap(105))
    assert strict == [], "105cm 在房間層嚴窗外"
    wide = fp_c.gap_door_zones(rects, [], T, CM, thin=_ink_at_gap(105),
                               ranges=fp_c.DOOR_JSON_RANGES_CM)
    assert len(wide) == 1, "105cm 應被 JSON 放寬窗撈回"


def test_text_ink_excluded():
    # 迴轉區只有文字墨（文字框內）——扣掉後無證據，不成門
    rects = _walls_with_gap(90)
    thin = _ink_at_gap(90)
    boxes = [(205, 110, 285, 155)]               # 文字框整個蓋住墨區
    zones = fp_c.gap_door_zones(rects, [], T, CM, thin=thin, text_boxes=boxes)
    assert zones == [], "文字墨不得當門扇證據"
