"""窄走道存活測試（segment_rooms）——閉運算填實害徵防護。
floor13/35 實案：走道高僅約 45px（85cm 門寬尺度），最小封口核
g=1.5×T=21 → 65px，閉運算直接把走道填成牆，走道與只經走道出入的
浴室/儲藏整片從室內消失（own_dataset 45 個漏切中 11 個源於此）。
防護設計：大核閉運算只當灌水屏障，室內面積改以「原始牆遮罩＋
髮絲縫小核」扣除——窄房間不再被封口核吃掉。"""
import numpy as np

import floorplan2dxf_color as fp_c


def _corridor_plan(T=20, W=600, H=420):
    """全封閉三層平面：上房、40px 窄走道、下房（皆無門洞——
    連通性只由牆決定，走道是否存活全看閉運算是否填掉它）。
    walls: 外框四面 + 兩道橫牆夾出 y=170~210 的走道。"""
    rects = [
        (0, 0, W, T),                    # 上外牆
        (0, H - T, W, H),                # 下外牆
        (0, 0, T, H),                    # 左外牆
        (W - T, 0, W, H),                # 右外牆
        (T, 150, W - T, 170),            # 走道上壁
        (T, 210, W - T, 230),            # 走道下壁
    ]
    return rects, W, H


def test_narrow_corridor_survives_closing_kernel():
    # T=20 → 最小封口核 2*round(1.5*20)+1 = 61px > 走道 40px。
    # 舊行為：走道被閉運算填實，只剩上下兩房。
    # 要求：三個空間都存活，且走道面積約 40px ×走道長。
    rects, W, H = _corridor_plan()
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0)
    assert labels is not None
    assert len(rooms) == 3, f"應切出 3 間（含 40px 走道），實得 {len(rooms)}"
    heights = sorted(r["bbox"][3] - r["bbox"][1] for r in rooms)
    assert heights[0] <= 45, f"最矮的空間應是 ~40px 走道，實得 {heights}"


def test_room_area_reaches_wall_edge():
    # 牆扣除改用原始遮罩後，房間面積應貼回真牆邊——上房內部
    # (T..W-T)×(T..150) 的涵蓋率應 >0.9（舊行為被大核吃掉一圈）。
    rects, W, H = _corridor_plan()
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0)
    assert labels is not None
    top = (W - 2 * 20) * (150 - 20)
    got = max(int((labels[:150, :] == r["id"]).sum()) for r in rooms)
    assert got > 0.9 * top, f"上房涵蓋率 {got / top:.2f} 應 >0.9"
