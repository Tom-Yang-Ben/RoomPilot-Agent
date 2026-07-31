"""走道攔腰切合併（_merge_nondoor_bridges）——floor04 實案。
牆縫封口把 40~260cm 全封，走道被 85cm（恰為單門尺寸）的橋切成兩段。
尺寸無法區分真門與走道橫斷；鑑別特徵＝兩側空間沿橋軸寬度：
真門的房間遠寬於門洞（浴廁 1.32×/客廳 4.6×），走道兩段 ≈1.0×。"""
import numpy as np

import floorplan2room as fp


def _scene(gap_px, room_w=None, with_door_arc=False):
    """上下兩空間被水平橋(帶 y=48..52)分開。room_w=None 時兩空間寬=gap
    （走道橫斷情境）；指定 room_w 時下方空間為寬房（真門情境）。"""
    labels = np.zeros((200, 400), np.int32)
    x0 = 200 - gap_px // 2
    labels[5:48, x0:x0 + gap_px] = 1               # 上：走道段（寬=gap）
    w2 = room_w or gap_px
    xb = 200 - w2 // 2
    labels[53:195, xb:xb + w2] = 2                 # 下：走道段或寬房
    rooms = []
    for rid in (1, 2):
        m = labels == rid
        ys, xs = np.nonzero(m)
        rooms.append({"id": rid, "area_px": int(m.sum()),
                      "bbox": (int(xs.min()), int(ys.min()),
                               int(xs.max() + 1), int(ys.max() + 1)),
                      "cx": float(xs.mean()), "cy": float(ys.mean()),
                      "aspect": 1.0})
    bridges = [(True, float(x0), float(x0 + gap_px), 48.0, 52.0)]
    doors = [(200.0, 100.0, float(gap_px))] if with_door_arc else []
    det = {"cm": 1.0, "T": 4, "doors": doors}
    return labels, rooms, bridges, det


def test_corridor_crossing_merges():
    # 兩側皆走道寬（1.0×橋長）→ 走道橫斷 → 合併，且該橋自清單移除
    labels, rooms, bridges, det = _scene(gap_px=100)
    out, kept = fp._merge_nondoor_bridges(labels, rooms, bridges, det)
    assert len(out) == 1
    assert kept == []                              # 失效橋不再畫、不再產生假門位
    assert not np.any(labels == 2)
    assert np.count_nonzero(labels == out[0]["id"]) == out[0]["area_px"]


def test_real_door_wide_room_kept_apart():
    # 下方是寬房（3×橋長）→ 真門 → 照舊隔房
    labels, rooms, bridges, det = _scene(gap_px=100, room_w=300)
    out, kept = fp._merge_nondoor_bridges(labels, rooms, bridges, det)
    assert len(out) == 2 and len(kept) == 1


def test_slightly_wider_side_kept_apart():
    # floor04 浴廁實案：一側 1.32×橋長 > 1.15 門檻 → 真門
    labels, rooms, bridges, det = _scene(gap_px=100, room_w=132)
    out, kept = fp._merge_nondoor_bridges(labels, rooms, bridges, det)
    assert len(out) == 2 and len(kept) == 1


def test_door_arc_evidence_kept_apart():
    # 兩側都走道寬但橋位有門弧（玄關擋門情境）→ 是門 → 不合併
    labels, rooms, bridges, det = _scene(gap_px=100, with_door_arc=True)
    out, kept = fp._merge_nondoor_bridges(labels, rooms, bridges, det)
    assert len(out) == 2 and len(kept) == 1


def test_wide_gap_missing_wall_no_merge():
    # >160cm 為雙開門/缺牆補償（floor04 廚房左牆 215cm 長橋實案）→ 不動
    labels, rooms, bridges, det = _scene(gap_px=210)
    out, kept = fp._merge_nondoor_bridges(labels, rooms, bridges, det)
    assert len(out) == 2 and len(kept) == 1
