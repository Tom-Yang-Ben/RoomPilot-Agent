"""樓梯(stair) 類新增 ＋ 書房(Office) 併入 storage——全鏈路測試。

背景：CubiCasa 的 12 個 room class 沒有樓梯與書房，`StairWell` 與 `Office`
在 `rooms_selected` 都是 11(Undefined)，語意投票（層 1/2）結構上產不出來。

2026-07-29 使用者裁決把 `Office` 併入 `storage`：兩者實務上是同一種空間的
兩個狀態（放東西叫書房、空著叫儲藏），且 DINOv2 裁切分類器在 72 房上
**從未把兩者互相搞混**，合併前後正確率完全相同（65/72）——分開標不帶來
任何可量測的資訊。故本檔測 stair 的證據鏈，以及 Office→storage 的映射。
"""
import cv2
import numpy as np

import floorplan2room as fp
from eval_rooms_cc import CLASSES, gt_label_of, norm_label


# ─────────────────────────── 詞彙表與色表 ───────────────────────────
def test_label_tables_cover_new_kinds():
    assert fp.ROOM_ZH_EX["stair"] == "樓梯"
    assert "stair" in fp.ROOM_BGR_EX
    assert "office" not in fp.ROOM_ZH_EX      # 已併入 storage，勿再長回來


def test_new_labels_are_scoreable_keys():
    """兩類不在 CC_ROOM_LABEL（模型無此輸出通道），必須另行播種進 score，
    否則 OCR 層的 `if lab_t in score` 防呆會把證據靜默丟掉。"""
    assert set(fp.EXTRA_LABELS) == {"stair"}
    assert not set(fp.EXTRA_LABELS) & set(fp.CC_ROOM_LABEL.values())


# ─────────────────────────── 層 5：OCR 文字 ───────────────────────────
def test_ocr_words_map_to_new_kinds():
    for word, lab in (("OFFICE", "storage"), ("STUDY", "storage"),
                      ("WORKROOM", "storage"), ("DEN", "storage"),
                      ("STAIR", "stair"), ("STAIRS", "stair"),
                      ("STAIRWELL", "stair"), ("STAIRCASE", "stair")):
        assert fp.ocr_room_label(word) == lab, word


def test_ocr_short_key_needs_exact_match():
    """DEN 僅 3 字，依 ocr_room_label 規則只走精確比對——
    GARDEN/WARDEN 這類含 DEN 的雜訊詞不得誤收。"""
    assert fp.ocr_room_label("GARDEN") != "storage"


# ─────────────────────────── 層 4：樓梯幾何 ───────────────────────────
def _thin_with_treads(n, depth_cm=28.0, width_cm=100.0, cm=1.0):
    """細線層：n 條等距平行踏板線（水平踏板、縱向排列）。"""
    img = np.zeros((400, 400), np.uint8)
    step, w = int(round(depth_cm / cm)), int(round(width_cm / cm))
    for i in range(n):
        y = 60 + i * step
        cv2.line(img, (100, y), (100 + w, y), 255, 1)
    return {"thin": img, "cm": cm}


def test_detect_stairs_finds_tread_run():
    det = _thin_with_treads(7)
    kinds = [k for k, _x, _y in fp.detect_stairs(det)]
    assert kinds.count("stair") == 1


def test_detect_stairs_rejects_wardrobe_dividers():
    """衣櫃分隔線僅 1~3 條；Readme 已記「衣櫃/牆剖面線/樓梯踏步幾何同構」，
    條數下限是本偵測器唯一可靠的鑑別軸——寧漏勿誤。"""
    assert fp.detect_stairs(_thin_with_treads(3)) == []


def test_detect_stairs_rejects_wall_hatching():
    """牆體剖面線間距遠密於踏面深度(21~35cm)，須被尺寸閘門擋下。"""
    assert fp.detect_stairs(_thin_with_treads(8, depth_cm=6.0)) == []


def test_detect_stairs_rejects_uneven_spacing():
    """間距不一致＝散落家具線，不是踏板。"""
    img = np.zeros((400, 400), np.uint8)
    for y in (60, 92, 150, 176, 260):
        cv2.line(img, (100, y), (200, y), 255, 1)
    assert fp.detect_stairs({"thin": img, "cm": 1.0}) == []


def test_detect_stairs_no_thin_layer():
    """彩圖管線沒有細線層 → 空清單（同 detect_symbols 契約）。"""
    assert fp.detect_stairs({"thin": None, "cm": 1.0}) == []


# ─────────────────────────── 計分整合 ───────────────────────────
def _mk(tmp_path, symbols=(), texts=()):
    """房1=受測房；房2=客廳錨（語意 living 滿票），避免觸發有廚無廳升級。"""
    labels = np.zeros((20, 40), np.int32)
    labels[:, :20], labels[:, 20:] = 1, 2
    det = {"cm": 1.0, "thin": None,
           "symbols": [(k, 10.0, 10.0) for k in symbols],
           "texts": [(lab, 10.0, 10.0, lab.upper()) for lab in texts]}
    rooms = [{"id": 1, "area_px": 400}, {"id": 2, "area_px": 400}]
    return det, labels, rooms, [{}, {"living": 1.0}]


def test_stair_symbol_names_room(tmp_path):
    det, labels, rooms, probs = _mk(tmp_path, symbols=["stair"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "stair"


def test_ocr_text_names_storage(tmp_path):
    """書房系文字（OFFICE/STUDY…）走 OCR 落到 storage。"""
    det, labels, rooms, probs = _mk(tmp_path, texts=["storage"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "storage"


def test_new_kinds_do_not_leak_into_other_rooms(tmp_path):
    """無證據時不得憑空冒出 stair（0 分播種不是 0.15 門檻的免死金牌）。"""
    det, labels, rooms, probs = _mk(tmp_path)
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] != "stair"


def test_stair_survives_singleton_demotion(tmp_path):
    """living/kitchen 限額降級時，次高分挑選不得被新類的 0 分播種干擾。"""
    det, labels, rooms, probs = _mk(tmp_path, symbols=["stair"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["label"] == "living"       # 錨房不受影響


# ─────────────────────────── GT 側：不再混入 space ───────────────────────────
def test_eval_classes_include_new_kinds():
    assert "stair" in CLASSES and "office" not in CLASSES
    assert len(CLASSES) == len(set(CLASSES)) == 10


def test_gt_label_separates_office_and_stairwell():
    """Office 與 StairWell 在 rooms_selected 同為 11，塌陷前必須先攔下來，
    否則兩者連同真正的 Undefined 一起變成 space 混合桶（recall 0.286 的成因）。
    Office 攔下後併入 storage（2026-07-29 裁決），不再是獨立類別。"""
    assert gt_label_of("Office") == "storage"
    assert gt_label_of("StairWell") == "stair"
    assert gt_label_of("Undefined") == "space"
    assert gt_label_of("Kitchen") == "kitchen"
    assert gt_label_of("Bath") == "bath"


def test_norm_label_passes_new_kinds_through():
    assert norm_label("stair") == "stair"
    assert norm_label("room") == "space"
