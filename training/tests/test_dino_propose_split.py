"""DINO 提案式切分（_dino_propose_splits）——無錨點大房的最後切分手段。

彩圖無 OCR 文字也無符號證據（thin=None）、灰階 floor47/52/13 的符號
召回被模板庫卡死——開放 LDK 誤併兩域合計 ~15 間沒有任何錨點可用。
提案器：對「夠大且無錨點觸發」的房，沿主軸輪廓階梯出候選刀，每刀
切兩半交 DINO 驗證；兩半 top-1 恰為 {Kitchen, LivingRoom} 對且信心
達標才收，取信心和最高的一刀。寧漏勿誤：驗證不過＝整房不動。"""
import numpy as np

import floorplan2room as fp


def _big_room(w=800, h=400):
    labels = np.zeros((h, w), np.int32)
    labels[20:380, 20:780] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (20, 20, 780, 380),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 2.1, "touch_env": True}]
    return labels, rooms


def _probs_by_x(split_x=400, pk=0.9, pl=0.9):
    """假分類器：質心在 split_x 左＝Kitchen、右＝LivingRoom（信心 pk/pl，
    其餘機率放到第三類，避免互補翻面）。"""
    def classify(bgr, labels, rooms, variant="gray"):
        out = []
        for r in rooms:
            ys, xs = np.nonzero(labels == r["id"])
            if xs.mean() < split_x:
                out.append({"Kitchen": pk, "Bedroom": (1 - pk) / 2,
                            "LivingRoom": (1 - pk) / 2})
            else:
                out.append({"LivingRoom": pl, "Bedroom": (1 - pl) / 2,
                            "Kitchen": (1 - pl) / 2})
        return out
    return classify


def test_ldk_pair_split_accepted(monkeypatch):
    labels, rooms = _big_room()
    monkeypatch.setattr(fp.room_classifier, "classify", _probs_by_x())
    det = {"cm": 1.0, "bgr": np.zeros((400, 800, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 2, f"LDK 對驗證通過應切二，實得 {len(out)}"
    assert sorted(int((labels == r["id"]).sum()) > 0 for r in out) == [True, True]


def test_low_confidence_rejected(monkeypatch):
    labels, rooms = _big_room()
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x(pk=0.4, pl=0.4))
    det = {"cm": 1.0, "bgr": np.zeros((400, 800, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 1, "信心不足應整房不動"


def test_same_label_both_halves_rejected(monkeypatch):
    # 兩半都判 LivingRoom（真的只是大客廳）——不切
    labels, rooms = _big_room()
    monkeypatch.setattr(
        fp.room_classifier, "classify",
        lambda bgr, la, rs, variant="gray": [{"LivingRoom": 0.9}
                                             for _ in rs])
    det = {"cm": 1.0, "bgr": np.zeros((400, 800, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 1


def test_small_room_not_touched(monkeypatch):
    labels = np.zeros((200, 200), np.int32)
    labels[20:180, 20:180] = 1                   # 2.56m²@cm=1
    rooms = [{"id": 1, "area_px": int((labels == 1).sum()),
              "bbox": (20, 20, 180, 180), "cx": 100.0, "cy": 100.0,
              "aspect": 1.0, "touch_env": False}]
    monkeypatch.setattr(fp.room_classifier, "classify", _probs_by_x(100))
    det = {"cm": 1.0, "bgr": np.zeros((200, 200, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=100)
    assert len(out) == 1, "小房不提案"
