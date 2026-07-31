"""Entry 與 Hallway 的幾何區分（2026-08-01 使用者裁決）。

兩者都是「沒有東西的空房間」，裁切圖上長得一模一樣——own_eval 實測 GT 4 間
走道被 DINOv2 判成 Entry 3、Bedroom 1，Hallway 的 P/R 掛零。外觀證據結構上
分不開，判別只能靠位置：玄關要通到屋外，一定貼外牆；走道在屋內，不貼。

本檔測那條規則本身（純幾何，不需要 torch/骨幹）。
"""
import numpy as np

import floorplan2room as fp


def _scene(room_cols, outside_from=36, h=40, w=40):
    """單間房 + 右側屋外自由區。room_cols=(c0, c1) 為房間的欄範圍（含頭不含尾）。"""
    labels = np.zeros((h, w), np.int32)
    labels[10:30, room_cols[0]:room_cols[1]] = 1
    outside = np.zeros((h, w), bool)
    outside[:, outside_from:] = True
    return labels, outside


# ─────────────────────────── touches_exterior ───────────────────────────
def test_touches_exterior_true_when_room_abuts_outside():
    labels, outside = _scene((30, 35))          # 右緣 34，距屋外 36 僅 2px
    assert fp.touches_exterior(labels, outside, 1, T_out=2.0) is True


def test_touches_exterior_false_for_interior_room():
    labels, outside = _scene((5, 15))           # 離屋外 20px 以上
    assert fp.touches_exterior(labels, outside, 1, T_out=2.0) is False


def test_touches_exterior_none_without_outside_info():
    """沒有屋外遮罩時不表態——呼叫端不得據此改判（寧可不動也不要猜）。"""
    labels, _ = _scene((5, 15))
    assert fp.touches_exterior(labels, None, 1, T_out=2.0) is None


def test_touches_exterior_none_for_missing_room():
    labels, outside = _scene((5, 15))
    assert fp.touches_exterior(labels, outside, 99, T_out=2.0) is None


# ─────────────────────────── 降級規則 ───────────────────────────
# 判準是「有沒有門通到屋外」而非「貼不貼外牆」（使用者裁決 2026-08-01）：
# floor74/76 的走道沿外牆走卻沒有對外的門，貼牆版規則擋不住它們。
def test_entry_without_exterior_door_demoted():
    """沒有大門的「玄關」就是走道——量尺上賠掉那幾房的成因。"""
    assert fp._entry_or_hallway("Entry", 1, set()) == "Hallway"
    assert fp._entry_or_hallway("Entry", 1, {2, 3}) == "Hallway"


def test_entry_with_exterior_door_stays_entry():
    assert fp._entry_or_hallway("Entry", 1, {1}) == "Entry"


def test_entry_kept_when_door_info_unavailable():
    """無門位/屋外資訊時不表態——寧可不動也不要猜。"""
    assert fp._entry_or_hallway("Entry", 1, None) == "Entry"


def test_rule_is_one_way_only():
    """有大門不足以證明是玄關（客廳也可能直接對外），故只降級不升級。"""
    for lab in ("LivingRoom", "Bedroom", "Bath", "Hallway", "room"):
        assert fp._entry_or_hallway(lab, 1, set()) == lab
        assert fp._entry_or_hallway(lab, 1, {1}) == lab


# ─────────────────────────── 接進計分鏈 ───────────────────────────
def _mk(outside=None):
    """房1=受測房（屋內）、房2=客廳錨，避免觸發有廚無廳升級。"""
    labels = np.zeros((40, 40), np.int32)
    labels[10:30, 5:15], labels[10:30, 20:30] = 1, 2
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": [], "T_out": 2.0}
    rooms = [{"id": 1, "area_px": 200}, {"id": 2, "area_px": 200}]
    return det, labels, rooms, [{"Entry": 1.0}, {"LivingRoom": 1.0}]


def test_classify_keeps_entry_when_no_doors_detected():
    """門偵測全空＝沒有資訊，不等於「沒有對外門」——此時必須不表態。

    兩者的差別是刻意的：`doors` 為空代表偵測失敗或該圖沒畫門，據此把所有
    玄關降級成走道會在門偵測退化時造成大面積誤判。真正該降級的是
    「有門位資料、但沒有一扇通到屋外」。"""
    det, labels, rooms, probs = _mk()
    det["rects"], det["doors"], det["T"] = [(0, 0, 40, 2)], [], 2.0
    outside = np.zeros((40, 40), bool)
    outside[:, 38:] = True
    fp.classify_rooms_dino(det, labels, rooms, probs, outside)
    assert rooms[0]["label"] == "Entry"


def test_classify_demotes_entry_via_empty_exterior_door_set(monkeypatch):
    """有門位資料但沒有一扇通到屋外 → 判 Entry 者降級為 Hallway。"""
    monkeypatch.setattr(fp, "rooms_with_exterior_door",
                        lambda det, labels, outside: set())
    det, labels, rooms, probs = _mk()
    fp.classify_rooms_dino(det, labels, rooms, probs, object())
    assert rooms[0]["label"] == "Hallway"
    assert rooms[0]["label_zh"] == "走道"


def test_classify_without_outside_keeps_entry():
    """未傳 outside（既有呼叫端、單元測試）時行為不變——不得悄悄改判。"""
    det, labels, rooms, probs = _mk()
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "Entry"


# ─────────────────────────── rooms_with_exterior_door ────────────────────────
def test_exterior_door_none_without_inputs():
    """缺門位/牆/屋外任一 → None（不表態），呼叫端維持原判。"""
    labels, outside = _scene((5, 15))
    assert fp.rooms_with_exterior_door({}, labels, outside) is None
    assert fp.rooms_with_exterior_door(
        {"rects": [(0, 0, 4, 4)], "doors": [], "T": 2.0}, labels, None) is None
