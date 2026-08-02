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


def test_ratio_guard_yields_to_verify_callback():
    # floor47/52/13 實案：開放 LDK 的廚餐半與客廳半近等大，1.8 方正守門
    # 把該切的也擋掉。verify 回呼（產品端接 DINO 兩半驗證）判真才放行；
    # 回呼判假／缺席時維持守門不切（floor07 廚餐一體房不受影響）
    labels = np.zeros((200, 400), np.int32)
    labels[20:180, 20:380] = 1
    rooms = [{"id": 1, "area_px": int((labels == 1).sum()),
              "bbox": (20, 20, 380, 180), "cx": 200.0, "cy": 100.0,
              "aspect": 2.25, "touch_env": False}]
    anchors = [("Kitchen", 100.0, 100.0, "sym:2"),
               ("LivingRoom", 300.0, 100.0, "sym:far-half")]
    # 無 verify：兩半 1:1 被守門擋下
    out = fp._split_by_text_anchors(labels.copy(), list(rooms), anchors,
                                    T=10, cm=1.0, amin=100,
                                    min_part_ratio=1.8)
    assert len(out) == 1, "守門應擋下近等大切分"
    # verify 判真：放行
    lab2 = labels.copy()
    out2 = fp._split_by_text_anchors(lab2, list(rooms), anchors,
                                     T=10, cm=1.0, amin=100,
                                     min_part_ratio=1.8,
                                     verify=lambda parts, merged: True)
    assert len(out2) == 2, "verify 判真應放行切分"
    # verify 判假：仍擋
    out3 = fp._split_by_text_anchors(labels.copy(), list(rooms), anchors,
                                     T=10, cm=1.0, amin=100,
                                     min_part_ratio=1.8,
                                     verify=lambda parts, merged: False)
    assert len(out3) == 1


def test_outlier_symbol_does_not_veto_cluster():
    # floor47/52 實案：廚房符號群裡混入一顆離群假陽性（鋼琴/櫃體誤判），
    # 跨距守門把整組否決。應改取最緊密子群（半徑 175cm 內成員最多），
    # 離群點剔除而非一票否決
    labels = np.zeros((300, 700), np.int32)
    labels[20:280, 20:680] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (20, 20, 680, 280),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 2.5, "touch_env": True}]
    det = {"symbols": [("kstove", 60.0, 60.0), ("ksink", 80.0, 100.0),
                       ("kstove", 600.0, 240.0)],   # 離群假陽性
           "cm": 1.2}                               # 跨距 540*1.2=648cm 超限
    anch = fp._symbol_anchors(det, labels, rooms)
    labs = sorted(a[0] for a in anch)
    assert labs == ["Kitchen", "LivingRoom"], \
        f"離群點應被剔除、緊密子群仍出錨：{anch}"
    kit = next(a for a in anch if a[0] == "Kitchen")
    assert kit[1] < 120, f"廚房錨點應在緊密子群質心（左側），實得 {kit}"
