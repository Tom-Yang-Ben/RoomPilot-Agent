"""房型 OCR 文字證據層（第 5 層）單元測試——TODO_ROOM_OCR.md 立項。
OCR 引擎本體不進測試（重、慢）；引擎輸出以 monkeypatch 假資料替代，
只驗證字典映射／模糊比對／座標縮放／classify_rooms_cc 計分整合。"""
import os

import cv2
import numpy as np
import pytest

import floorplan2room as fp


# ─────────────────────────── 字典映射 ───────────────────────────

def test_ocr_label_exact():
    assert fp.ocr_room_label("KITCHEN") == "kitchen"
    assert fp.ocr_room_label("DORMITORY") == "bed"
    assert fp.ocr_room_label("BEDROOM") == "bed"
    assert fp.ocr_room_label("BATHROOM") == "bath"
    assert fp.ocr_room_label("WC") == "bath"
    assert fp.ocr_room_label("DEPOSIT") == "storage"     # 標注者裁決：storage（GT 同步修正）
    assert fp.ocr_room_label("CIRCULATION") == "entry"
    assert fp.ocr_room_label("BALCONY") == "outdoor"
    assert fp.ocr_room_label("GARAGE") == "garage"


def test_ocr_label_concat_case_and_phrase():
    assert fp.ocr_room_label("LIVINGROOM") == "living"   # rapidocr 實測 floor04 連寫
    assert fp.ocr_room_label("Living Room") == "living"
    assert fp.ocr_room_label("living") == "living"
    assert fp.ocr_room_label("MASTER BEDROOM") == "bed"  # 片語含鍵
    assert fp.ocr_room_label("BEDROOM 2") == "bed"


def test_ocr_label_fuzzy_typo():
    assert fp.ocr_room_label("KITCHEM") == "kitchen"     # OCR 錯一字
    assert fp.ocr_room_label("BATHR0OM") == "bath"       # O→0
    assert fp.ocr_room_label("DORMITORV") == "bed"


def test_ocr_label_rejects_noise():
    assert fp.ocr_room_label("") is None
    assert fp.ocr_room_label("120") is None              # 尺寸標注
    assert fp.ocr_room_label("A") is None
    assert fp.ocr_room_label("SCALE") is None
    assert fp.ocr_room_label("WALL") is None             # 與 HALL 一字之差也不可誤收
    assert fp.ocr_room_label("PLAN") is None


# ─────────────────────────── 偵測（引擎 mock）───────────────────────────

def _fake_words(items):
    """組 _ocr_words 假輸出：[(text, conf, cx, cy, bbox)]（原圖座標）。"""
    full = [(t, c, x, y, (x - 5, y - 3, x + 5, y + 3)) for t, c, x, y in items]
    return lambda _path: list(full)


def test_detect_room_text_conf_filter_and_mapping(monkeypatch):
    monkeypatch.setattr(fp, "_ocr_words", _fake_words([
        ("KITCHEN", 0.99, 10.0, 20.0),
        ("DORMITORY", 0.40, 30.0, 40.0),    # 信心不足 → 濾掉
        ("3200", 0.99, 50.0, 60.0),         # 非房型詞 → 濾掉
    ]))
    out = fp.detect_room_text("dummy.png")
    assert out == [("kitchen", 10.0, 20.0, "KITCHEN")]


def test_detect_room_text_engine_missing(monkeypatch):
    monkeypatch.setattr(fp, "_ocr_words", _fake_words([]))
    assert fp.detect_room_text("dummy.png") == []


# ─────────────────────────── classify_rooms_cc 整合 ───────────────────────────

def _mk_det_labels(tmp_path, texts=(), probs=None):
    """兩房迷你場景：labels 左=1 右=2。probs 為每房的房型機率（預設無證據）。
    2026-07-30 CubiCasa 移除後，層 1 由 DINOv2 機率供給，不再有語意遮罩。"""
    labels = np.zeros((20, 40), np.int32)
    labels[:, :20] = 1
    labels[:, 20:] = 2
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": list(texts)}
    rooms = [{"id": 1, "area_px": 400}, {"id": 2, "area_px": 400}]
    return det, labels, rooms, list(probs or [{}, {}])


def test_classify_ocr_evidence_names_room(tmp_path):
    det, labels, rooms, probs = _mk_det_labels(
        tmp_path, texts=[("kitchen", 5.0, 10.0, "KITCHEN")])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "kitchen"                # 文字落在房 1 → 命名
    assert rooms[0]["ocr_text"] == {"kitchen": ["KITCHEN"]}
    assert rooms[1]["label"] == "room"                   # 無任何證據 → 中性
    assert "ocr_text" not in rooms[1]


def test_classify_ocr_weight_beats_weak_semantic(tmp_path):
    # 房 1 語意弱票 living 0.30（floor04 KITCHEN 實案為 0.275）＋文字 KITCHEN → 廚房勝
    det, labels, rooms, probs = _mk_det_labels(
        tmp_path,
        texts=[("kitchen", 5.0, 10.0, "KITCHEN")],
        probs=[{"living": 0.30}, {}])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "kitchen"                # 0.65 文字 > 0.30 弱語意（不再被放大）


def test_classify_text_outside_all_rooms_is_ignored(tmp_path):
    det, labels, rooms, probs = _mk_det_labels(
        tmp_path, texts=[("bath", 999.0, 999.0, "BATHROOM")])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "room"
    assert rooms[1]["label"] == "room"


# 註（2026-07-30）：test_weak_vote_no_boost_below_floor /
# test_weak_vote_boost_above_floor 兩支已刪除。它們測的是 classify_rooms_cc
# 的「弱票不放大」加成邏輯（top 票 <0.35 不加成，≥0.35 乘 1.12），該機制是
# 為 CubiCasa 語意投票的平緩分數分布而設，隨 CubiCasa 整批移除一併消失。
# DINOv2 的機率本身已是校準過的分布，不需要也不應該再加成。


def _mk_multi(tmp_path, votes):
    """三房迷你場景：labels 左/中/右 = 1/2/3，各房房型機率由 votes 指定。
    votes: {房id: {類別碼: 機率}}，類別碼沿用 CC_ROOM_LABEL（4=living, 3=kitchen,
    5=bed, 6=bath）——保留數字寫法以免大改既有案例，內部轉成 label 機率。"""
    labels = np.zeros((20, 60), np.int32)
    labels[:, :20], labels[:, 20:40], labels[:, 40:] = 1, 2, 3
    probs = [{} for _ in range(3)]
    for rid, dist in votes.items():
        probs[rid - 1] = {fp.CC_ROOM_LABEL[c]: v for c, v in dist.items()}
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": []}
    rooms = [{"id": 1, "area_px": 400}, {"id": 2, "area_px": 300},
             {"id": 3, "area_px": 200}]
    return det, labels, rooms, probs


def test_singleton_living_keeps_largest(tmp_path):
    # 房1(大)與房3(小)都判 living → 只留房1，房3 降級為次高分 bed
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 3: {4: 0.6, 5: 0.4}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "living"
    assert rooms[2]["label"] == "bed"
    assert rooms[2]["relabel_from"] == "living"


def test_singleton_kitchen_keeps_largest(tmp_path):
    # 房1 客廳固定（避免觸發有廚無廳升級），隔離驗證 kitchen 同類保大
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 2: {3: 0.9}, 3: {3: 0.8, 6: 0.2}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "kitchen"          # 房2 面積 > 房3
    assert rooms[2]["label"] == "bath"             # 次高分 bath 0.2 ≥ 0.15


def test_singleton_demote_below_threshold_is_room(tmp_path):
    # 降級後次高分 <0.15 → 中性「空間」
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 3: {4: 0.6, 5: 0.1}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[2]["label"] == "room"


def test_singleton_demoted_living_never_becomes_kitchen(tmp_path):
    # 降級不得流向另一個限額類：房3 次高分是 kitchen，仍須跳過取第三高
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 3: {4: 0.5, 3: 0.3, 5: 0.2}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[2]["label"] == "bed"


def test_singleton_single_instances_untouched(tmp_path):
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 2: {3: 0.9}, 3: {5: 0.9}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert [r["label"] for r in rooms] == ["living", "kitchen", "bed"]
    assert not any("relabel_from" in r for r in rooms)


# ─────────────────────────── 有廚無廳 → 廚房改叫客廳 ───────────────────────────

def test_kitchen_without_living_promoted(tmp_path):
    # 全戶只判出 kitchen（無 living）→ 客餐廚一體，改叫 living
    # 2026-07-29 起需該房本身有 living 概念（≥0.05）才升級，故給 0.2 living 票
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        2: {3: 0.7, 4: 0.2}, 3: {5: 0.9}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "living"
    assert rooms[1]["relabel_from"] == "kitchen"
    assert rooms[2]["label"] == "bed"


def test_kitchen_with_living_untouched(tmp_path):
    # living 存在 → kitchen 不改名
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        1: {4: 0.9}, 2: {3: 0.9}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "living"
    assert rooms[1]["label"] == "kitchen"


def test_kitchen_ocr_text_exempt_from_promotion(tmp_path):
    # 圖面文字明寫 KITCHEN（作者親口說）→ 即使無 living 也不改名
    det, labels, rooms, probs = _mk_multi(tmp_path, {2: {3: 0.9}})
    det["texts"] = [("kitchen", 30.0, 10.0, "KITCHEN")]   # 落在房 2
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "kitchen"
    assert "relabel_from" not in rooms[1]


def test_kitchen_with_zero_living_not_promoted(tmp_path):
    """模型對該房完全沒有 living 概念 → 它就是一間獨立廚房，不是客餐廚一體。
    floor73 實案：真廚房 kitchen 1.00 / living 0.00 卻被無條件升級成 living，
    是 DINOv2 路徑 kitchen recall 掉到 0.6 的成因之一（修正後 0.8）。"""
    det, labels, rooms, probs = _mk_multi(tmp_path, {2: {3: 0.9}, 3: {5: 0.9}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "kitchen"
    assert "relabel_from" not in rooms[1]


def test_two_kitchens_no_living_dedup_then_promote(tmp_path):
    # 兩間 kitchen 無 living：大的留下再改叫 living，小的降級
    # （留下者需有 living 概念才升級，故房2 給 0.2 living 票）
    det, labels, rooms, probs = _mk_multi(tmp_path, {
        2: {3: 0.7, 4: 0.2}, 3: {3: 0.8, 6: 0.2}})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "living"           # 房2 面積大：kitchen→living
    assert rooms[1]["relabel_from"] == "kitchen"
    assert rooms[2]["label"] == "bath"             # 房3 讓位降級


# ─────────────────────────── 文字框與門位墨水證據 ───────────────────────────

def test_detect_text_boxes_any_word(monkeypatch):
    monkeypatch.setattr(fp, "_ocr_words", _fake_words([
        ("3200", 0.99, 50.0, 60.0),         # 非房型詞也要收（扣墨水用）
        ("KITCHEN", 0.99, 10.0, 20.0),
        ("blur", 0.30, 70.0, 80.0),         # conf <0.5 → 不收
    ]))
    boxes = fp.detect_text_boxes("dummy.png")
    assert len(boxes) == 2


def _ink_scene(with_arc=False, with_text=False):
    """水平橋(帶 y=48..52，開口 x=150..250)；迴轉區下方可放弧墨/文字墨。"""
    thin = np.zeros((200, 400), np.uint8)
    if with_arc:
        cv2.ellipse(thin, (150, 52), (100, 100), 0, 0, 90, 255, 2)
    if with_text:
        cv2.rectangle(thin, (160, 90), (240, 110), 255, -1)   # 文字墨塊
    det = {"thin": thin,
           "text_boxes": [(160, 90, 240, 110)] if with_text else []}
    return det


def test_bridge_ink_empty_passage_is_not_door():
    det = _ink_scene()
    assert not fp._bridge_has_door_ink(det, True, 150.0, 250.0, 48.0, 52.0)


def test_bridge_ink_arc_is_door():
    det = _ink_scene(with_arc=True)
    assert fp._bridge_has_door_ink(det, True, 150.0, 250.0, 48.0, 52.0)


def test_bridge_ink_text_pollution_filtered():
    # 迴轉區只有文字墨（CIRCULATION 實案）→ 扣掉文字框後不是門
    det = _ink_scene(with_text=True)
    assert not fp._bridge_has_door_ink(det, True, 150.0, 250.0, 48.0, 52.0)


def test_bridge_ink_color_pipeline_passthrough():
    assert fp._bridge_has_door_ink({"thin": None}, True, 150.0, 250.0, 48.0, 52.0)
