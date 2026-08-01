"""封口來源長度守門（_wall_gaps）——短柱亂射防護。
floor35 實案：陽台側壁 56px 短柱的端點射線往下找到 160px（216cm）外
的廚房底牆，封口盒直貫廚房把它切成三條假房。牆柱不該投出比自己長
一大截的封口；真門的封口不受影響——門另一側的長牆會以自己的端點
重新提出同一道縫（雙向提案），只有「兩側都提不出」的孤柱亂射被擋。"""
import floorplan2dxf_color as fp_c


def test_stub_cannot_project_long_seal():
    # 短柱（長 56）垂直端點對 160px 外的長橫牆——封口 160 > 2×56，拒收
    rects = [
        (73, 2, 84, 58),                     # 陽台側壁短柱
        (2, 218, 172, 229),                  # 廚房底牆（橫）
    ]
    gaps = fp_c._wall_gaps(rects, [], T=11, cm=1.349, lo_cm=40.0, hi_cm=260.0)
    assert gaps == [], f"短柱不得投出 3 倍於自身的封口：{gaps}"


def test_door_gap_between_long_walls_still_sealed():
    # 兩道長牆間的 60px 門縫——雙方都夠長，照封
    rects = [
        (0, 100, 200, 120),                  # 左長牆
        (260, 100, 460, 120),                # 右長牆
    ]
    gaps = fp_c._wall_gaps(rects, [], T=20, cm=1.5, lo_cm=40.0, hi_cm=260.0)
    assert len(gaps) == 1
    horiz, g0, g1, _b0, _b1 = gaps[0]
    assert horiz and abs(g0 - 200) <= 1 and abs(g1 - 260) <= 1


def test_short_stub_beside_door_rescued_by_long_side():
    # 40px 短柱與長牆夾一道 63px 門縫：柱側提案被擋（63 > 2×40 不成立
    # ——63 < 80 其實過得了），改用更短的柱 25px 驗證長側救援：
    # 柱側 63 > 2×25 被擋，但長牆端點的反向射線重新提出同一道縫
    rects = [
        (0, 100, 25, 120),                   # 25px 短柱
        (88, 100, 400, 120),                 # 長牆
    ]
    gaps = fp_c._wall_gaps(rects, [], T=20, cm=1.5, lo_cm=40.0, hi_cm=260.0)
    assert len(gaps) == 1, f"長側應救回門縫：{gaps}"


def test_door_size_gap_exempt_from_stub_guard():
    # floor08 實案：19px 短柱與 75cm 真門縫、對側無長牆救援——
    # 門尺寸範圍（60~200cm）豁免守門，照封
    rects = [
        (160, 93, 179, 100),                 # 19px 短柱（橫向）
        (226, 90, 420, 101),                 # 對側牆帶錯位、無法反提
    ]
    gaps = fp_c._wall_gaps(rects, [], T=11, cm=1.604, lo_cm=40.0,
                           hi_cm=260.0)
    # 兩側可各提案一次（band 差一個去重桶），重點是縫有被封
    assert gaps and all(round(g0) == 179 and round(g1) == 226
                        for _h, g0, g1, _b0, _b1 in gaps), \
        f"門尺寸縫應豁免短柱守門：{gaps}"


def test_rescue_mode_disables_stub_guard():
    # 救援輪（floor02）需要短柱投長封口封 L 型大開口——stub_guard=False
    rects = [
        (73, 2, 84, 58),
        (2, 218, 172, 229),
    ]
    gaps = fp_c._wall_gaps(rects, [], T=11, cm=1.349, lo_cm=40.0,
                           hi_cm=360.0, stub_guard=False)
    assert len(gaps) == 1
