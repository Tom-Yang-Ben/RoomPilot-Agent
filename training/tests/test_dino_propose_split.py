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


def _probs_by_x_pair(split_x, left_lab, right_lab, p=0.9):
    def classify(bgr, labels, rooms, variant="gray"):
        out = []
        for r in rooms:
            ys, xs = np.nonzero(labels == r["id"])
            lab = left_lab if xs.mean() < split_x else right_lab
            rest = (1 - p) / 2
            out.append({lab: p, "Bath": rest, "Storage": rest})
        return out
    return classify


def test_balcony_pair_split_with_fence_line(monkeypatch):
    # floor_04/18/19 型：陽台與客廳/臥室之間的窗帶沒被窗偵測抓到，
    # 兩區黏成一房。窗帶在 fence 層是長直線 → 提案器以 fence 線密度
    # 峰當切刀候選；兩半判 {Balcony, LivingRoom} 對也該收
    labels, rooms = _big_room()                  # 房 (20,20)-(780,380)
    fence = np.zeros((400, 800), np.uint8)
    fence[20:380, 600:603] = 255                 # 窗帶直線在 x=600
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(600, "LivingRoom", "Balcony"))
    det = {"cm": 1.0, "bgr": np.zeros((400, 800, 3), np.uint8),
           "domain": "color", "fence": fence}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 2, "Balcony 對＋fence 刀應切二"
    areas = sorted(int((labels == r["id"]).sum()) for r in out)
    assert areas[0] < areas[1] and areas[0] > 50000, \
        f"切線應在 fence 線附近（右半 ~180×360），實得 {areas}"


def test_balcony_bath_pair_rejected(monkeypatch):
    # {Balcony, Bath} 不在接受對——不切（寧漏勿誤）
    labels, rooms = _big_room()
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(400, "Bath", "Balcony"))
    det = {"cm": 1.0, "bgr": np.zeros((400, 800, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 1


def test_tint_boundary_knife_hallway_living(monkeypatch):
    # floor_08 實案：黃走道與白磁磚客廳無牆、有清晰色界——色染轉換
    # 位置該出候選刀；兩半判 {Hallway, LivingRoom} 對（0.65 從嚴）也收
    labels, rooms = _big_room()                  # (20,20)-(780,380)
    bgr = np.full((400, 800, 3), 240, np.uint8)
    bgr[20:380, 20:500] = (120, 230, 240)        # 黃染左半
    bgr[20:380, 500:780] = (245, 245, 245)       # 白磁磚右半
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(500, "Hallway", "LivingRoom"))
    det = {"cm": 1.0, "bgr": bgr, "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0, amin=1000)
    assert len(out) == 2, "色染轉換刀＋Hallway 對應切二"
    areas = sorted(int((labels == r["id"]).sum()) for r in out)
    assert 90000 < areas[0] < 190000, f"切線應在色界附近：{areas}"


def test_ww_adopted_small_blob_proposed(monkeypatch):
    # floor_07 實案：救援採用張的臥+浴複合 blob 計算面積僅 7~8.6m²
    # （比例尺低估），10m² big 線全擋、8m² 硬地板連場都進不了——
    # 災難張門檻下修（硬地板 5m²、big 6m²），任意對 0.7 開刀。
    # 5~10m² 帶只吃證據刀：色染轉換（左染右白）出刀、任意對 0.9 收
    labels = np.zeros((300, 300), np.int32)
    labels[10:290, 10:260] = 1                   # 70000px = 7m²@cm=1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (10, 10, 260, 290),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 1.1, "touch_env": True}]
    bgr = np.full((300, 300, 3), 245, np.uint8)
    bgr[:, :135] = (120, 230, 240)               # 左半色染、右半白＝色界
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(135, "Bedroom", "Kitchen"))
    det = {"cm": 1.0, "bgr": bgr, "domain": "color", "_ww_adopted": True}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0,
                                  amin=1000)
    assert len(out) == 2, f"災難張 7m² 複合房應依色界證據開刀，實得 {len(out)}"


def test_ww_adopted_no_evidence_not_cut(monkeypatch):
    # floor_08 左臥實案：7.2m² 乾淨單房無色界無 fence——中點/剖面
    # 跳變等無證據亂刀在 5~10m² 帶全禁，即使切半對信心 0.9 也不切
    labels = np.zeros((300, 300), np.int32)
    labels[10:290, 10:260] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (10, 10, 260, 290),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 1.1, "touch_env": True}]
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(135, "Bedroom", "Kitchen"))
    det = {"cm": 1.0, "bgr": np.full((300, 300, 3), 245, np.uint8),
           "domain": "color", "_ww_adopted": True}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0,
                                  amin=1000)
    assert len(out) == 1, "無證據刀的 5~10m² 單房不得試切"


def test_normal_small_room_floor_unchanged(monkeypatch):
    # 非災難張：8m² 硬地板不動——7m² 房不得提案（防常規張亂切）
    labels = np.zeros((300, 300), np.int32)
    labels[10:290, 10:260] = 1
    m = labels == 1
    ys, xs = np.nonzero(m)
    rooms = [{"id": 1, "area_px": int(m.sum()), "bbox": (10, 10, 260, 290),
              "cx": float(xs.mean()), "cy": float(ys.mean()),
              "aspect": 1.1, "touch_env": True}]
    monkeypatch.setattr(fp.room_classifier, "classify",
                        _probs_by_x_pair(135, "Bedroom", "Kitchen"))
    det = {"cm": 1.0, "bgr": np.zeros((300, 300, 3), np.uint8),
           "domain": "color"}
    out = fp._dino_propose_splits(det, labels, rooms, T=10, cm=1.0,
                                  amin=1000)
    assert len(out) == 1, "常規張 7m² 房不得提案"
