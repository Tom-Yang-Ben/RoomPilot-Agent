"""樓梯足跡切分（_carve_stairs）——開放區嵌樓梯的功能區切分第一塊。
floor08/12/31/52/54 實案：樓梯無四面牆、嵌在大廳/客廳開放區，被併入
鄰房而漏切（own_dataset 6 個 Stair 漏切）。踏板偵測（detect_stairs）
已能認出「4+ 條等距等長平行線」，本模組把踏板串的外框從所屬房間
切出成獨立房——切線一律軸對齊（使用者域約束：房間只有直角矩形系）。"""
import numpy as np

import floorplan2room as fp


def _one_room(w=300, h=200):
    labels = np.zeros((h, w), np.int32)
    labels[20:180, 20:280] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()),
              "bbox": (20, 20, 280, 180), "cx": float(xs.mean()),
              "cy": float(ys.mean()), "aspect": 1.62, "touch_env": True}]
    return labels, rooms


def test_carve_stair_box_into_own_room():
    labels, rooms = _one_room()
    out = fp._carve_stairs(labels, rooms, [(200, 40, 270, 140)], T=8)
    assert len(out) == 2, f"應切出樓梯房，實得 {len(out)}"
    stair = max(out, key=lambda r: r["id"])
    assert stair["bbox"] == (200, 40, 270, 140)
    assert stair["area_px"] == 70 * 100
    host = min(out, key=lambda r: r["id"])
    assert host["area_px"] == 160 * 260 - 70 * 100   # 主房面積同步扣除
    assert int((labels == stair["id"]).sum()) == stair["area_px"]


def test_stair_covering_room_not_carved():
    # 樓梯間本來就有牆自成一房（floor13 右側）→ 足跡蓋掉大半房間
    # 時不切，避免把已正確的樓梯間再切一刀
    labels, rooms = _one_room()
    out = fp._carve_stairs(labels, rooms, [(25, 25, 275, 175)], T=8)
    assert len(out) == 1


def test_tiny_or_outside_box_ignored():
    labels, rooms = _one_room()
    out = fp._carve_stairs(labels, rooms, [(0, 0, 10, 10),      # 房外
                                           (100, 100, 108, 108)],  # 過小
                           T=8)
    assert len(out) == 1


def test_adjacent_runs_merge_into_one_stair():
    # 迴轉梯：兩道相鄰平行梯段 → 只切一間樓梯房（間隙 < 2T 視為同座）
    labels, rooms = _one_room()
    out = fp._carve_stairs(labels, rooms,
                           [(200, 40, 235, 140), (245, 40, 270, 140)], T=8)
    assert len(out) == 2
    stair = max(out, key=lambda r: r["id"])
    assert stair["bbox"] == (200, 40, 270, 140)


def test_landing_separated_runs_merge():
    # floor40 實案：上下兩段梯隔著 ~55cm 樓梯平台（> 2T），x 對齊
    # → 仍屬同座，該併（對齊梯段間隙 <140cm 併同座）
    labels, rooms = _one_room()
    out = fp._carve_stairs(labels, rooms,
                           [(200, 30, 260, 70), (200, 125, 260, 160)],
                           T=8, cm=1.0)
    assert len(out) == 2
    stair = max(out, key=lambda r: r["id"])
    assert stair["bbox"] == (200, 30, 260, 160)


def test_walled_stairwell_not_recarved():
    # floor40 實案：樓梯間本有牆自成一房（房寬 ≈ 踏板框寬），覆蓋率
    # 47% 躲過 50% 防呆仍不該切——框寬 ≥85% 宿主寬即否決
    labels = np.zeros((300, 120), np.int32)
    labels[20:280, 10:110] = 1                   # 窄長樓梯間 100 寬
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (10, 20, 110, 280),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 2.6, "touch_env": True}]
    out = fp._carve_stairs(labels, rooms, [(12, 30, 108, 150)], T=8)
    assert len(out) == 1, "樓梯間不該被再切一刀"
