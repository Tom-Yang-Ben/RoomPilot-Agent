"""外圈封口（envelope_gap_seals）——外牆寬窗帶的灌水漏最後防線。

floor_09 實案：外牆窗帶寬 260cm 以上、窗偵測 R 僅 38%，牆縫封口上限
260cm 擋不住，灌水自外圈滲入把半戶判成室外。外圈（建物 bbox 周邊 3T
內）的牆縫另開一輪 260~600cm 封口——窗只會出現在外圈；室內的大開口
（客餐廳一體）遠離外圈，不受影響。"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 20


def test_wide_envelope_gap_sealed_interior_gap_not():
    # 800x600 殼：上牆開 300px(=300cm) 寬洞（窗帶）；室內一道隔牆也留
    # 300px 開口（客餐一體）——前者該封、後者不該
    rects = [
        (0, 0, 200, 20), (500, 0, 800, 20),      # 上牆帶 300px 洞
        (0, 580, 800, 600),                      # 下牆
        (0, 0, 20, 600), (780, 0, 800, 600),     # 左右牆
        (20, 300, 250, 320), (550, 300, 780, 320),  # 室內隔牆帶 300px 開口
    ]
    seals = fp_c.envelope_gap_seals(rects, [], T, cm=1.0)
    assert seals, "外圈 300cm 窗帶應被封"
    for _o, x0, y0, x1, y1 in seals:
        assert y1 <= 40, f"封口只該出現在外圈（上牆），出現 {x0,y0,x1,y1}"
        assert 180 <= x0 and x1 <= 520, f"封口應落在上牆洞範圍：{x0,x1}"


def test_normal_door_gap_not_duplicated():
    # 90px 門縫已由常規 40~260cm 封口處理——外圈輪（260 起跳）不重複收
    rects = [(0, 0, 300, 20), (390, 0, 700, 20),
             (0, 580, 700, 600), (0, 0, 20, 600), (680, 0, 700, 600)]
    assert fp_c.envelope_gap_seals(rects, [], T, cm=1.0) == []
