"""假帶縫合輪（_ww_suture_merge）——白牆救援採用張的過切殘塊回併。

白牆救援補的帶含假陽性（床頭板/磁磚列/沙發緣），會把大房切出殘塊；
殘塊無符號無門，常被叫 Hallway（floor_08 實案：客廳被切出 21k px
殘片獨立成房，主體 IoU 0.38 差線；縫回後 0.61 跨線）。

縫合鐵律（寧漏勿誤，全部滿足才併）：
1. det["_ww_adopted"]——災難張限定，正常張機制零接觸
2. 相鄰面不是真暗牆（邊界帶與暗牆重疊 <30%）——白帶/fence/封口切
   都是救援重跑期人工物（floor_08 實測殘塊多為 fence 切），放行給門 4
3. 一方是 Hallway/room（過切殘塊的典型歸宿）或兩方同名
4. DINO 聯集重分類 top-1 == 非 Hallway 方房型且信心 ≥0.7
"""
import numpy as np

import floorplan2room as fp

T = 10


def _two_rooms(band=True):
    """500x300：左大房（客廳）＋右殘塊，中間隔 2T 白帶（或暗牆）。"""
    labels = np.zeros((300, 500), np.int32)
    labels[20:280, 20:300] = 1                   # 左大房
    labels[20:280, 320:480] = 2                  # 右殘塊
    rooms = []
    for rid, lab in ((1, "LivingRoom"), (2, "Hallway")):
        r = fp._room_stats(labels, rid, True)
        r["label"] = lab
        rooms.append(r)
    sep = (300, 20, 320, 280)                    # 分隔帶（2T 寬）
    det = {"cm": 1.0, "bgr": np.zeros((300, 500, 3), np.uint8),
           "domain": "color", "_ww_adopted": True,
           "rects": [(0, 0, 500, 10)],           # 遠處一段暗牆（不當分隔）
           "_ww_bands": [sep] if band else []}
    if not band:
        det["rects"] = det["rects"] + [sep]      # 分隔改為暗牆
    return det, labels, rooms


def _union_probs(label="LivingRoom", p=0.9):
    def classify(bgr, labels, rooms, variant="gray"):
        return [{label: p, "Bedroom": (1 - p) / 2, "Hallway": (1 - p) / 2}
                for _ in rooms]
    return classify


def test_residue_across_band_merged(monkeypatch):
    det, labels, rooms = _two_rooms(band=True)
    monkeypatch.setattr(fp.room_classifier, "classify", _union_probs())
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 1, f"白帶殘塊應縫回，實得 {len(out)} 房"
    assert out[0]["label"] == "LivingRoom"
    assert int((labels == out[0]["id"]).sum()) == out[0]["area_px"]
    assert out[0]["area_px"] >= 260 * 280 + 260 * 160   # 兩塊都在

def test_dark_wall_boundary_not_merged(monkeypatch):
    det, labels, rooms = _two_rooms(band=False)
    monkeypatch.setattr(fp.room_classifier, "classify", _union_probs())
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 2, "暗牆分隔不得縫合"


def test_low_union_confidence_not_merged(monkeypatch):
    det, labels, rooms = _two_rooms(band=True)
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _union_probs(p=0.5))
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 2, "聯集信心不足不得縫合"


def test_two_named_rooms_not_merged(monkeypatch):
    det, labels, rooms = _two_rooms(band=True)
    rooms[1]["label"] = "Bedroom"                # 殘塊有正名＝可能真房
    monkeypatch.setattr(fp.room_classifier, "classify", _union_probs())
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 2, "兩個有正名的房不得縫合"


def test_same_label_pair_merged(monkeypatch):
    det, labels, rooms = _two_rooms(band=True)
    rooms[1]["label"] = "LivingRoom"             # 同名兩半（假帶對切）
    monkeypatch.setattr(fp.room_classifier, "classify", _union_probs())
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 1, "同名假帶對切應縫回"


def test_not_adopted_zero_touch(monkeypatch):
    det, labels, rooms = _two_rooms(band=True)
    det.pop("_ww_adopted")
    monkeypatch.setattr(fp.room_classifier, "classify", _union_probs())
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 2, "非救援採用張機制必須零接觸"


def test_union_top1_mismatch_not_merged(monkeypatch):
    # DINO 認為聯集是 Bedroom（≠ 主體 LivingRoom）——證據矛盾不併
    det, labels, rooms = _two_rooms(band=True)
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _union_probs(label="Bedroom"))
    out = fp._ww_suture_merge(det, labels, rooms, T=T, cm=1.0)
    assert len(out) == 2, "聯集 top-1 與主體不符不得縫合"
