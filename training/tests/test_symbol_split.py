"""符號錨點功能區切分（_symbol_anchors）——無文字開放區的補位機制。
v2.23 殘餘 36 個漏切中 14 個（39%）是無文字開放區誤併（floor54/52/
47/09/31/19/20 型），OCR 錨點天生吃不到。圖上沒字但有家具符號：
爐台/水槽/餐桌＝廚房系證據、沙發＝客廳系證據——一房同時含兩系
符號群即產生兩個錨點，交給既有 _split_by_text_anchors 的方正度
切線處理。刻意只做廚 vs 客這一種（臥浴不參與），寧漏勿誤。"""
import numpy as np

import floorplan2room as fp


def _room(w=400, h=200):
    labels = np.zeros((h, w), np.int32)
    labels[20:180, 20:380] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (20, 20, 380, 180),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 2.25, "touch_env": True}]
    return labels, rooms


def test_kitchen_and_sofa_symbols_make_two_anchors():
    labels, rooms = _room()
    det = {"symbols": [("kstove", 60.0, 60.0), ("ksink", 80.0, 120.0),
                       ("sofa", 320.0, 100.0)], "cm": 1.0}
    anch = fp._symbol_anchors(det, labels, rooms)
    labs = sorted(a[0] for a in anch)
    assert labs == ["Kitchen", "LivingRoom"], f"應各一錨點，實得 {anch}"
    kit = next(a for a in anch if a[0] == "Kitchen")
    assert 60 <= kit[1] <= 80, f"廚房錨點應在符號群質心附近: {kit}"


def test_single_family_small_room_no_anchor():
    # 單側廚房路徑有 15m² 門檻——5.76m² 小房不會是開放廚客，不出錨點
    labels, rooms = _room()
    det = {"symbols": [("kstove", 60.0, 60.0), ("ksink", 80.0, 120.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def _big_room(w=800, h=500, cm=1.0):
    # 760×460 px @cm=1 → 34.96m²：夠大的開放廚客
    labels = np.zeros((h, w), np.int32)
    labels[20:480, 20:780] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (20, 20, 780, 480),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 1.65, "touch_env": True}]
    return labels, rooms


def test_one_sided_kitchen_cluster_makes_anchor_pair():
    # 實測主力路徑：客廳側符號全滅（沙發模板比對不到），大房間裡
    # 緊湊偏心的廚房符號群單側觸發，對側錨點＝遠半質量質心
    labels, rooms = _big_room()
    det = {"symbols": [("kstove", 80.0, 80.0), ("ksink", 150.0, 60.0)],
           "cm": 1.0}
    anch = fp._symbol_anchors(det, labels, rooms)
    labs = sorted(a[0] for a in anch)
    assert labs == ["Kitchen", "LivingRoom"], f"實得 {anch}"
    liv = next(a for a in anch if a[0] == "LivingRoom")
    assert liv[1] > 400, f"對側錨點應落在遠半（x>400）: {liv}"


def test_one_sided_scattered_symbols_no_anchor():
    # 廚房符號跨距 >350cm ＝ 散落假陽性，不觸發
    labels, rooms = _big_room()
    det = {"symbols": [("kstove", 80.0, 80.0), ("ksink", 700.0, 400.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_one_sided_centered_cluster_no_anchor():
    # 符號群居中 ＝ 這房本身就是廚房，不切
    labels, rooms = _big_room()
    det = {"symbols": [("kstove", 380.0, 240.0), ("ksink", 420.0, 260.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_one_sided_weak_evidence_no_anchor():
    # 只有弱證據（dtable/sinkicon）不得單獨撐起單側切分
    labels, rooms = _big_room()
    det = {"symbols": [("dtable", 80.0, 80.0), ("sinkicon", 150.0, 60.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_chair_alone_is_not_living_evidence():
    # 單人沙發椅常出現在臥室——chair 單獨不構成客廳錨點（寧漏勿誤）
    labels, rooms = _room()
    det = {"symbols": [("kstove", 60.0, 60.0), ("chair", 320.0, 100.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_close_centroids_no_anchor():
    # 兩系質心 <200cm＝證據糾纏（開放小空間）→ 不切
    labels, rooms = _room()
    det = {"symbols": [("kstove", 150.0, 100.0), ("sofa", 250.0, 100.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_symbols_outside_room_ignored():
    labels, rooms = _room()
    det = {"symbols": [("kstove", 5.0, 5.0), ("sofa", 320.0, 100.0)],
           "cm": 1.0}
    assert fp._symbol_anchors(det, labels, rooms) == []


def test_end_to_end_split_via_symbol_anchors():
    # 錨點餵給既有 _split_by_text_anchors → 一房切二
    labels, rooms = _room()
    det = {"symbols": [("kstove", 60.0, 60.0), ("ksink", 80.0, 120.0),
                       ("sofa", 320.0, 100.0)], "cm": 1.0}
    anch = fp._symbol_anchors(det, labels, rooms)
    out = fp._split_by_text_anchors(labels, rooms, anch, T=8, cm=1.0,
                                    amin=1000)
    assert len(out) == 2, f"應切成 2 區，實得 {len(out)}"
