"""窗內外側守門（window_side_gate）——彩圖假窗過濾的原則性判別。

floor_05 實案：左下房內的白色櫃體被誤判成窗（長 295px、兩端有牆可錨、
離外圈 7.5T），畫進封口遮罩把房間攔腰切（5/10→3/10）。距離與錨定
都分不開真假；真窗的物理特徵是「恰好一側通室外」——把牆＋封口＋
全部候選窗畫成屏障後從影像邊界灌水，逐窗探測兩側：一側室外＝真窗、
兩側皆室內＝家具假窗、兩側皆室外＝懸空雜訊。"""
import numpy as np

import floorplan2dxf_color as fp_c

T = 10


def _walled_scene():
    """300x300：實心外牆圍一圈（上牆開一個 60px 窗洞），室內一道假窗。"""
    rects = [(20, 20, 280, 30),                  # 上牆（先整條，洞用座標拆兩段）
             (20, 270, 280, 280),                # 下牆
             (20, 20, 30, 280),                  # 左牆
             (270, 20, 280, 280)]                # 右牆
    # 上牆開洞：拆成兩段，洞在 x 120~180
    rects[0] = (20, 20, 120, 30)
    rects.append((180, 20, 280, 30))
    win_true = (1, 120, 20, 180, 30)             # 洞裡的真窗
    win_false = (1, 100, 150, 200, 160)          # 室內橫櫃假窗
    return rects, [win_true, win_false]


def test_true_window_kept_false_dropped():
    rects, cand = _walled_scene()
    kept = fp_c.window_side_gate(cand, rects, T, cm=1.0, img_w=300, img_h=300)
    assert cand[0] in kept, "外牆洞上的真窗應保留"
    assert cand[1] not in kept, "室內櫃體假窗（兩側皆室內）應剔除"


def test_floating_candidate_dropped():
    # 建物外的懸空候選（離殼 > 1.5T 閉運算補縫範圍，兩側皆室外）——剔除。
    # 貼殼 ≤1.5T 的候選視同殼補丁保留無妨（在殼外，畫進遮罩不影響房間）
    rects, _ = _walled_scene()
    rects = [(x0, y0 if y1 != 280 else 220, x1, y1 if y1 != 280 else 230)
             if (y0, y1) == (270, 280) else (x0, y0, x1, y1)
             for x0, y0, x1, y1 in rects]
    rects = [(20, 20, 120, 30), (180, 20, 280, 30),      # 上牆(帶洞)
             (20, 220, 280, 230),                        # 下牆(上移)
             (20, 20, 30, 230), (270, 20, 280, 230)]     # 側牆
    floating = (1, 100, 280, 200, 286)                   # 離下牆 50px = 5T
    kept = fp_c.window_side_gate([floating], rects, T, cm=1.0,
                                 img_w=300, img_h=300)
    assert kept == []
