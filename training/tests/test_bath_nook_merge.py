"""浴室隔屏碎格合併（_merge_bath_nooks）。
floor38/44 實案：浴缸屏/馬桶半牆＋封口盒把一間浴室切成 3~4 格，
每格對 GT 整間浴室 IoU 皆 <0.5（floor44），或碎格直接死在面積終篩
（floor38）。規則：相鄰（間距 ≤2T）的小碎房（各 <8m²）只要都含
浴具符號（oval/tubrect/wc/tub/basin/shower）就併成一間——在面積
終篩之前執行，合併後的浴室才活得過門檻。
2026-08-01 二落：首落時浴具模板未啟用、零觸發而還原；tub/wc 依
品質掃描（probe_symbol_quality.py）啟用後證據到位重新上線。"""
import numpy as np

import floorplan2room as fp


def _rooms_from_labels(labels):
    rooms = []
    for rid in np.unique(labels[labels > 0]):
        m = labels == rid
        ys, xs = np.nonzero(m)
        rooms.append({"id": int(rid), "area_px": int(m.sum()),
                      "bbox": (int(xs.min()), int(ys.min()),
                               int(xs.max() + 1), int(ys.max() + 1)),
                      "cx": float(xs.mean()), "cy": float(ys.mean()),
                      "aspect": 1.0, "touch_env": False})
    return rooms


def test_adjacent_fixture_nooks_merge():
    labels = np.zeros((200, 300), np.int32)
    labels[20:90, 20:120] = 1                    # 馬桶格
    labels[110:180, 20:120] = 2                  # 浴缸格（隔 20px 半牆帶）
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0), ("tub", 60.0, 140.0)],
           "cm": 1.0}
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 1, f"兩浴具碎格應併一間，實得 {len(out)}"
    assert int((labels == out[0]["id"]).sum()) == out[0]["area_px"]
    assert out[0]["area_px"] == 70 * 100 * 2


def test_no_fixture_no_merge():
    labels = np.zeros((200, 300), np.int32)
    labels[20:90, 20:120] = 1
    labels[110:180, 20:120] = 2
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0)], "cm": 1.0}   # 只有一格有浴具
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 2


def test_big_room_with_fixture_not_merged():
    # 大房（≥8m²）不參與——避免浴具誤偵測把臥室吸進浴室
    labels = np.zeros((400, 500), np.int32)
    labels[20:90, 20:120] = 1                    # 浴具碎格
    labels[110:380, 20:480] = 2                  # 34m² 大房（也放個誤偵測浴具）
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0), ("oval", 200.0, 200.0)],
           "cm": 1.0}
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 2


def test_kitchen_symbol_vetoes_candidacy():
    # floor39 實案：wc 模板在廚房打假陽性，廚房被當浴具碎格與相鄰
    # 真浴室誤併——含廚房系符號（爐台/水槽）的房間不得作為候選
    labels = np.zeros((200, 300), np.int32)
    labels[20:90, 20:120] = 1                    # 廚房（wc 假陽性＋爐台）
    labels[110:180, 20:120] = 2                  # 真浴室
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0), ("kstove", 90.0, 40.0),
                       ("oval", 60.0, 140.0)], "cm": 1.0}
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 2, "含廚房符號的房不該被吸進浴室"


def test_extra_absorbed_only_with_two_seeds():
    # 吸收制：無浴具小格鄰接「≥2 種子」的群才被吸收（floor38 浴缸格
    # 無配對符號）；單種子不吸——真浴室不得吞隔壁儲藏室
    labels = np.zeros((300, 300), np.int32)
    labels[20:90, 20:120] = 1                    # 種子：馬桶格
    labels[110:180, 20:120] = 2                  # 種子：洗手台格
    labels[200:270, 20:120] = 3                  # 無浴具的浴缸格
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0), ("basin", 60.0, 140.0)],
           "cm": 1.0}
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 1, f"三格應併一間，實得 {len(out)}"

    labels2 = np.zeros((300, 300), np.int32)
    labels2[20:90, 20:120] = 1                   # 唯一種子
    labels2[110:180, 20:120] = 2                 # 鄰接無浴具小格（儲藏室）
    rooms2 = _rooms_from_labels(labels2)
    det2 = {"symbols": [("wc", 60.0, 50.0)], "cm": 1.0}
    out2 = fp._merge_bath_nooks(labels2, rooms2, det2, T=10)
    assert len(out2) == 2, "單種子不得吸收鄰格"


def test_far_apart_nooks_not_merged():
    labels = np.zeros((200, 500), np.int32)
    labels[20:90, 20:120] = 1
    labels[20:90, 300:400] = 2                   # 相距 180px ≫ 2T
    rooms = _rooms_from_labels(labels)
    det = {"symbols": [("wc", 60.0, 50.0), ("tub", 350.0, 50.0)],
           "cm": 1.0}
    out = fp._merge_bath_nooks(labels, rooms, det, T=10)
    assert len(out) == 2
