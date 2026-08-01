"""殼外陽台口袋收割（_harvest_balcony_pockets）——color 集 Balcony 漏切主因。

陽台在牆殼之外、由圍欄細線圈住；牆偵測不含圍欄 → 主分割灌水判定室外
整片剪掉（dev 實測 Balcony 漏切 18 間、散在 16 張）。收割：把圍欄線補
進屏障重灌水，「主分割室外、圍欄屏障下灌不到」的口袋＝陽台候選，
以新房間附加——既有房間 label 一概不動，純加法零風險。"""
import numpy as np

import floorplan2room as f2r

T = 10


def _scene():
    """300x300：上半是牆殼圍的室內房；殼下方一個圍欄圈住的陽台口袋，
    以及一片開放到影像邊界的室外（不得成房）。"""
    img_w = img_h = 300
    rects = [(40, 40, 260, 50), (40, 150, 260, 160),     # 上下牆
             (40, 40, 50, 160), (250, 40, 260, 160)]     # 左右牆
    labels = np.zeros((img_h, img_w), np.int32)
    labels[50:150, 50:250] = 1                           # 室內房
    rooms = [{"id": 1, "area_px": int((150 - 50) * (250 - 50)),
              "bbox": (50, 50, 250, 150), "cx": 150.0, "cy": 100.0}]
    outside = np.ones((img_h, img_w), bool)
    outside[40:160, 40:260] = False                      # 殼內非室外
    fence = np.zeros((img_h, img_w), np.uint8)
    # 陽台圍欄：貼殼下緣 (60,160)-(200,220) 的 ㄩ 形細線
    fence[218:220, 60:200] = 255                         # 底欄
    fence[160:220, 60:62] = 255                          # 左欄
    fence[160:220, 198:200] = 255                        # 右欄
    det = {"rects": rects, "wins": [], "T": T, "cm": 1.0,
           "img_w": img_w, "img_h": img_h, "fence": fence, "thin": None}
    return det, labels, rooms, outside


def test_fenced_pocket_harvested():
    det, labels, rooms, outside = _scene()
    out = f2r._harvest_balcony_pockets(det, labels, rooms, outside)
    assert len(out) == 2, f"應收割一個陽台口袋：{[r['id'] for r in out]}"
    new = out[-1]
    x0, y0, x1, y1 = new["bbox"]
    assert 160 <= y0 and y1 <= 222 and 55 <= x0 and x1 <= 205, \
        f"口袋範圍應在圍欄內：{new['bbox']}"
    assert (labels == new["id"]).sum() == new["area_px"]
    assert rooms[0]["bbox"] == (50, 50, 250, 150), "既有房間不得被動到"


def test_open_outside_not_harvested():
    # 沒有圍欄 → 口袋灌得到影像邊界，不得成房
    det, labels, rooms, outside = _scene()
    det["fence"] = np.zeros_like(det["fence"])
    out = f2r._harvest_balcony_pockets(det, labels, rooms, outside)
    assert len(out) == 1


def test_no_fence_layer_noop():
    det, labels, rooms, outside = _scene()
    det["fence"] = None
    out = f2r._harvest_balcony_pockets(det, labels, rooms, outside)
    assert len(out) == 1
