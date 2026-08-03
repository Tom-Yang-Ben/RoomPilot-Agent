"""OCR 房名錨點功能區切分（_split_by_text_anchors）。
E1 誤併型態（own_dataset 21 件）：廚/餐/客一體、玄關-走道虛線分界，
GT 沿「無牆邊界」分區，封口規則無牆可封。圖面文字是作者親口說的
答案——一房含 2+ 個房名文字錨點＝作者標了 2+ 個功能區，沿主軸在
錨點間隙中點下軸對齊直刀（使用者域約束：切線只有水平/垂直）。"""
import numpy as np

import floorplan2room as fp


def _room(w=400, h=200, x0=20, y0=20, x1=None, y1=None):
    x1, y1 = x1 or w - 20, y1 or h - 20
    labels = np.zeros((h, w), np.int32)
    labels[y0:y1, x0:x1] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (x0, y0, x1, y1),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 2.1, "touch_env": True}]
    return labels, rooms


def test_two_anchors_split_at_gap_midpoint():
    labels, rooms = _room()
    texts = [("Kitchen", 100.0, 100.0, "KITCHEN"),
             ("LivingRoom", 300.0, 100.0, "LIVING")]
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 2, f"應切成 2 區，實得 {len(out)}"
    left = min(out, key=lambda r: r["cx"])
    right = max(out, key=lambda r: r["cx"])
    assert left["bbox"][2] <= 205 and right["bbox"][0] >= 195, \
        f"切線應在 x=200 中點附近：{left['bbox']} / {right['bbox']}"
    assert int((labels == left["id"]).sum()) == left["area_px"]


def test_three_anchors_two_cuts():
    labels, rooms = _room()
    texts = [("Kitchen", 70.0, 100.0, "KITCHEN"),
             ("LivingRoom", 200.0, 100.0, "DINNING"),
             ("LivingRoom", 330.0, 100.0, "FAMILY")]
    # cm=2：房寬 8 米、同標籤錨距 260cm > 200cm 群聚半徑（4 米房塞
    # 三個功能區不真實，會被折行文字規則誤併）
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=2.0,
                                    amin=1000)
    assert len(out) == 3, f"三錨點應切成 3 區，實得 {len(out)}"


def test_cut_snaps_to_shape_step():
    # 使用者裁決（2026-08-01）：分區位置取決於「切給誰較方正」。
    # L 型連通塊（左窄高、右寬矮）的正確切線在輪廓階梯 x=150 處，
    # 而非錨點中點 x=200——階梯切出兩個完整矩形，方正度最高。
    labels = np.zeros((200, 400), np.int32)
    labels[20:180, 20:150] = 1                   # 左：窄高矩形（廚房）
    labels[80:180, 150:380] = 1                  # 右：寬矮矩形（客廳）
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (20, 20, 380, 180),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 1.0, "touch_env": True}]
    texts = [("Kitchen", 85.0, 100.0, "KITCHEN"),
             ("LivingRoom", 315.0, 130.0, "LIVING")]
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 2
    left = min(out, key=lambda r: r["cx"])
    assert abs(left["bbox"][2] - 150) <= 6, \
        f"切線應貼齊階梯 x=150，實得左房 bbox={left['bbox']}"
    for r in out:                                # 兩側皆應接近滿版矩形
        bx0, by0, bx1, by1 = r["bbox"]
        fill = r["area_px"] / ((bx1 - bx0) * (by1 - by0))
        assert fill > 0.95, f"方正度 {fill:.2f} 應 >0.95：{r['bbox']}"


def test_single_anchor_no_split():
    labels, rooms = _room()
    texts = [("Kitchen", 200.0, 100.0, "KITCHEN")]
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 1


def test_close_same_label_anchors_are_one_zone():
    # 「WASH AREA」折兩行 → 同標籤兩錨點相距 <200cm ＝同一區，不切
    labels, rooms = _room()
    texts = [("Bath", 195.0, 95.0, "WASH"),
             ("Bath", 205.0, 110.0, "AREA")]
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 1


def test_tiny_part_cancels_split():
    # 切出來的區塊低於 amin → 整刀取消，不產生碎屑
    labels, rooms = _room()
    texts = [("Kitchen", 30.0, 100.0, "KITCHEN"),
             ("LivingRoom", 350.0, 100.0, "LIVING")]
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=30000)                # 門檻拉高
    assert len(out) == 1


def test_anchor_outside_room_ignored():
    labels, rooms = _room()
    texts = [("Kitchen", 100.0, 100.0, "KITCHEN"),
             ("LivingRoom", 500.0, 100.0, "LIVING")]   # 房外
    out = fp._split_by_text_anchors(labels, rooms, texts, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 1
