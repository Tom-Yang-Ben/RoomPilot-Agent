"""Asset 家具模板庫（階段 A）——PNG 正規化與新 kind 計分整合測試。
分類依使用者裁決：dinner_table→kitchen、chairs（單人沙發）→living。"""
import cv2
import numpy as np

import floorplan2room as fp
from extract_asset_lib import ASSET_KINDS, png_to_template


def _mk_png(tmp_path, name="a.png", alpha=False, size=200):
    """合成線稿 PNG：白底黑線一張桌子（矩形＋交叉線）。"""
    img = np.full((size, size), 255, np.uint8)
    cv2.rectangle(img, (40, 60), (160, 140), 0, 2)
    cv2.line(img, (40, 60), (160, 140), 0, 2)
    p = str(tmp_path / name)
    if alpha:
        rgba = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        rgba[:, :, 3] = np.where(img < 128, 255, 0).astype(np.uint8)
        rgba[:, :, :3][img >= 128] = 0          # 透明區底色隨便，須被合成掉
        cv2.imwrite(p, rgba)
    else:
        cv2.imwrite(p, img)
    return p


def test_png_to_template_gray(tmp_path):
    r = png_to_template(_mk_png(tmp_path))
    assert r is not None and r.shape == (48, 48)
    assert 0.02 <= np.count_nonzero(r) / r.size <= 0.5   # 線稿密度合理

def test_png_to_template_alpha(tmp_path):
    r = png_to_template(_mk_png(tmp_path, "b.png", alpha=True))
    assert r is not None and r.shape == (48, 48)
    assert np.count_nonzero(r) > 20


def test_asset_kind_room_mapping():
    m = dict(ASSET_KINDS)
    assert m["kitchen/dinner_table"][0] == "dtable"      # user 裁決：餐桌歸廚房
    assert m["livingroom/chairs"][0] == "chair"          # 單人沙發＝客廳


def _mk(tmp_path, symbols, anchor_living=True):
    """房1=受測符號；房2=錨房。

    錨房預設投 living 滿票以避免觸發「有廚無廳→改叫客廳」升級；但受測房
    本身要驗 living（sofa/chair）時必須換掉——living 是限額類，兩間同標會
    互相排擠，且 2026-07-29 起限額保留的是**分數最高**者（錨房滿票必勝）。"""
    labels = np.zeros((20, 40), np.int32)
    labels[:, :20], labels[:, 20:] = 1, 2
    det = {"cm": 1.0, "thin": None, "texts": [],
           "symbols": [(k, 10.0, 10.0) for k in symbols]}
    rooms = [{"id": 1, "area_px": 400}, {"id": 2, "area_px": 400}]
    anchor = {"LivingRoom": 1.0} if anchor_living else {"Bedroom": 1.0}
    return det, labels, rooms, [{}, anchor]


def test_asset_symbols_name_rooms(tmp_path):
    for kinds, expect in [
        (["wc"], "Bath"), (["tub", "basin"], "Bath"),
        (["kstove"], "Kitchen"), (["dtable", "ksink"], "Kitchen"),
        # 左欄是家具符號 kind（"bed"＝床的模板），與房型 "Bedroom" 同義不同名
        (["bed"], "Bedroom"), (["wardrobe", "bed"], "Bedroom"),
        (["sofa"], "LivingRoom"), (["chair", "sofa"], "LivingRoom"),
    ]:
        det, labels, rooms, probs = _mk(tmp_path, kinds,
                                          anchor_living=(expect != "LivingRoom"))
        fp.classify_rooms_dino(det, labels, rooms, probs)
        assert rooms[0]["label"] == expect, (kinds, rooms[0]["label"])


def test_asset_chair_alone_below_threshold(tmp_path):
    # 單一 chair 權重 0.15 剛好過 0.15 門檻 → living；確認弱證據不誤標他類
    det, labels, rooms, probs = _mk(tmp_path, ["chair"],
                                      anchor_living=False)
    fp.classify_rooms_dino(det, labels, rooms, probs)
    assert rooms[0]["label"] in ("LivingRoom", "room")
