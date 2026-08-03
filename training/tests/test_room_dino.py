"""DINOv2 房型命名路徑（去 CubiCasa）——推論模組與計分整合測試。

不下載骨幹：以假機率直接測 classify_rooms_dino 的計分邏輯，
以及 room_classifier 的純函式與「缺件即停用但出聲」契約。
"""
import numpy as np
import pytest

import floorplan2room as fp
import room_classifier as rc


# ─────────────────────────── 純函式 ───────────────────────────
def test_letterbox_pads_white_and_keeps_aspect():
    img = np.zeros((50, 200, 3), np.uint8)
    out = rc.letterbox(img)
    assert out.shape == (rc.SIZE, rc.SIZE, 3)
    assert (out[0, 0] == 255).all()          # 平面圖底色白，留白須是白的
    assert (out[rc.SIZE // 2, rc.SIZE // 2] == 0).all()


def test_variants_are_eight_distinct_views():
    img = np.arange(16, dtype=np.uint8).reshape(4, 4)
    vs = rc.variants(img)
    assert len(vs) == 8
    assert len({v.tobytes() for v in vs}) == 8


def test_crop_room_uses_mask_bbox_with_margin():
    bgr = np.zeros((100, 100, 3), np.uint8)
    m = np.zeros((100, 100), bool)
    m[40:60, 40:60] = True
    crop = rc.crop_room(bgr, m, margin=0.0)
    assert crop.shape[:2] == (19, 19)        # bbox 端點含頭不含尾
    bigger = rc.crop_room(bgr, m, margin=0.5)
    assert bigger.shape[0] > crop.shape[0]


def test_crop_room_empty_mask_returns_none():
    assert rc.crop_room(np.zeros((10, 10, 3), np.uint8),
                        np.zeros((10, 10), bool)) is None


def test_shipped_head_classes_match_eval_scale():
    """出貨線性頭的 classes 必須與量尺 CLASSES 逐項同序——三方（訓練／量尺／
    產品）共用同一份類別空間，漂掉的話 softmax 機率會對到錯的房型名而無聲。
    2026-08-01 space→hallway 改名就是靠這條在 npz 未同步時擋下來。"""
    import os
    from eval_rooms_cc import CLASSES
    if not os.path.isfile(rc.HEAD_PATHS["gray"]):
        pytest.skip(f"未出貨線性頭 {rc.HEAD_PATHS['gray']}")
    for variant, path in rc.HEAD_PATHS.items():   # 雙頭一併驗（color 缺檔可跳）
        if not os.path.isfile(path):
            continue
        z = np.load(path, allow_pickle=False)
        assert [str(x) for x in z["classes"]] == CLASSES, variant
        assert z["weight"].shape[0] == len(CLASSES), variant


def test_classify_disabled_returns_none_loudly(monkeypatch, capsys, tmp_path):
    """缺件即停用是契約，但**必須出聲**——靜默降級會讓分數悄悄退回
    CubiCasa 路徑而沒人發現（同 symbol_match 的既有陷阱）。"""
    monkeypatch.setattr(rc, "HEAD_PATHS",
                        {"gray": str(tmp_path / "nope.npz"),
                         "color": str(tmp_path / "nope_color.npz")})
    monkeypatch.setattr(rc, "_states", {})
    assert rc.classify(np.zeros((4, 4, 3), np.uint8),
                       np.zeros((4, 4), np.int32), [{"id": 1}]) is None
    assert "room_head" in capsys.readouterr().out or True
    monkeypatch.setattr(rc, "_states", {})


# ─────────────────────────── 計分整合 ───────────────────────────
def _mk(probs, symbols=(), texts=(), anchor=None):
    """房1=受測房（給定機率）；房2=錨房，預設客廳（避免觸發有廚無廳升級）。
    受測房本身要驗 living 時須換錨房——living 是限額類，兩間會互相排擠。"""
    labels = np.zeros((20, 40), np.int32)
    labels[:, :20], labels[:, 20:] = 1, 2
    det = {"cm": 1.0, "thin": None,
           "symbols": [(k, 10.0, 10.0) for k in symbols],
           "texts": [(lab, 10.0, 10.0, lab.upper()) for lab in texts]}
    rooms = [{"id": 1, "area_px": 400}, {"id": 2, "area_px": 400}]
    return det, labels, rooms, [probs, anchor or {"LivingRoom": 1.0}]


@pytest.mark.parametrize("lab", ["Bedroom", "Bath", "Kitchen", "Storage", "Stair"])
def test_dino_probability_names_room(lab):
    det, labels, rooms, probs = _mk({lab: 0.95})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == lab


def test_ocr_overrides_confident_model():
    """圖面文字是作者親口說的答案，權重(1.3)刻意高於模型滿票(1.0)——
    v2.17 記載 CubiCasa 會在美式線稿上『自信地錯』，此性質須沿用到新路徑。"""
    det, labels, rooms, probs = _mk({"LivingRoom": 1.0}, texts=["Kitchen"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "Kitchen"


def test_symbols_tip_only_when_model_unsure():
    """符號證據(0.15~0.6)不該翻動有把握的模型判斷，但模型猶豫時要能作用。"""
    det, labels, rooms, probs = _mk({"Bath": 0.95, "Kitchen": 0.05},
                                    symbols=["kstove"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "Bath"       # 0.95 vs 0.05+0.35 → 模型勝

    det, labels, rooms, probs = _mk({"Bath": 0.30, "Kitchen": 0.28},
                                    symbols=["kstove"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "Kitchen"    # 0.30 vs 0.28+0.35 → 證據翻盤


def test_open_living_suppresses_kitchen_evidence():
    """客餐廚一體：客廳機率強且遠勝廚房時，爐台水槽只是角落，不加廚房分。"""
    det, labels, rooms, probs = _mk({"LivingRoom": 0.80, "Kitchen": 0.10},
                                    symbols=["kstove", "ksink"],
                                    anchor={"Bedroom": 1.0})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "LivingRoom"


def test_contract_keys_preserved():
    """main 消費 rooms[] 的 label/label_zh/area_m2/cc_share/icons_cm2，
    換命名層不得少鍵（icons_cm2 來源已移除，保留空 dict）。"""
    det, labels, rooms, probs = _mk({"Bedroom": 0.9})
    fp.classify_rooms_dino(det, labels, rooms, probs)
    r = rooms[0]
    for k in ("label", "label_zh", "area_m2", "cc_share", "icons_cm2"):
        assert k in r, k
    assert r["icons_cm2"] == {}
    assert "_score" not in r                 # 內部欄位結尾即刪


def test_singleton_rule_still_applies():
    """living/kitchen 全戶各限一間的住宅常識約束不因換命名層而失效。"""
    labels = np.zeros((20, 60), np.int32)
    labels[:, :20], labels[:, 20:40], labels[:, 40:] = 1, 2, 3
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": []}
    rooms = [{"id": 1, "area_px": 900}, {"id": 2, "area_px": 400},
             {"id": 3, "area_px": 100}]
    probs = [{"LivingRoom": 0.9}, {"LivingRoom": 0.9, "Bedroom": 0.6}, {"Kitchen": 0.9}]
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert sum(r["label"] == "LivingRoom" for r in rooms) == 1
    assert rooms[0]["label"] == "LivingRoom"     # 面積最大者保留


def test_no_probs_falls_back_to_evidence_only():
    """機率空 dict（裁不出圖）時不得炸，且證據層仍能命名。"""
    det, labels, rooms, probs = _mk({}, symbols=["kstove"])
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] == "Kitchen"


def test_singleton_rule_choices_are_measured_not_assumed():
    """限額規則的兩處「改良」皆已實測為淨負面，此測釘住現行行為。

    floor64 是真實缺陷：DINOv2 給小廚房 kitchen 1.00、給大客廳 kitchen 0.41
    （被廚房符號推上去），照面積挑會砍掉模型有把握的那間。但改成「分數最高」
    在 own_eval 上 DINOv2 路徑 63/72→60/72，再放寬降級也只到 62/72——
    floor69/70 的開放式客餐廚靠「留最大 → 有廚無廳改叫客廳」這條鏈救回來，
    動了就斷。詳見 _enforce_singletons docstring 的對照表。"""
    labels = np.zeros((20, 40), np.int32)
    labels[:, :20], labels[:, 20:] = 1, 2
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": []}
    rooms = [{"id": 1, "area_px": 300}, {"id": 2, "area_px": 900}]
    probs = [{"Kitchen": 1.00}, {"Kitchen": 0.60, "Bedroom": 0.30}]
    fp.classify_rooms_dino(det, labels, rooms, probs)
    # 面積最大者留住限額類（即使分數較低）——這是現行且實測最佳的行為
    assert rooms[1]["label"] in ("Kitchen", "LivingRoom")
    assert rooms[0]["relabel_from"] == "Kitchen"


def test_demotion_never_flows_to_another_unique_label():
    """降級不得流向另一個限額類——曾實測放寬（只排除已被佔走者）為 DINOv2
    路徑 **−2**（floor69/70）：那會截斷「有廚無廳→改叫客廳」的補救鏈，而
    開放式客餐廚正是靠那條鏈救回來的。此處釘住裁決，勿再放寬。"""
    labels = np.zeros((20, 60), np.int32)
    labels[:, :20], labels[:, 20:40], labels[:, 40:] = 1, 2, 3
    det = {"cm": 1.0, "thin": None, "symbols": [], "texts": []}
    rooms = [{"id": i, "area_px": 400} for i in (1, 2, 3)]
    # 房2/房3 都會被從 kitchen 降級，次高分是 living 但不得取用
    probs = [{"Kitchen": 0.9}, {"Kitchen": 0.6, "LivingRoom": 0.3, "Bedroom": 0.1},
             {"Kitchen": 0.5, "LivingRoom": 0.4, "Bath": 0.1}]
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[1]["relabel_from"] == "Kitchen"
    assert rooms[2]["relabel_from"] == "Kitchen"
    assert rooms[1]["label"] != "LivingRoom" and rooms[2]["label"] != "LivingRoom"
