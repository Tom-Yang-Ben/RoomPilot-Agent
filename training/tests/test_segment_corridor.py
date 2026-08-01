"""窄走道存活測試（segment_rooms）——閉運算填實害徵防護。
floor13/35 實案：走道高僅約 45px（85cm 門寬尺度），最小封口核
g=1.5×T=21 → 65px，閉運算直接把走道填成牆，走道與只經走道出入的
浴室/儲藏整片從室內消失（own_dataset 45 個漏切中 11 個源於此）。
防護設計：大核閉運算只當灌水屏障，室內面積改以「原始牆遮罩＋
髮絲縫小核」扣除——窄房間不再被封口核吃掉。"""
import numpy as np

import floorplan2dxf_color as fp_c


def _corridor_plan(T=20, W=600, H=420):
    """全封閉三層平面：上房、40px 窄走道、下房（皆無門洞——
    連通性只由牆決定，走道是否存活全看閉運算是否填掉它）。
    walls: 外框四面 + 兩道橫牆夾出 y=170~210 的走道。"""
    rects = [
        (0, 0, W, T),                    # 上外牆
        (0, H - T, W, H),                # 下外牆
        (0, 0, T, H),                    # 左外牆
        (W - T, 0, W, H),                # 右外牆
        (T, 150, W - T, 170),            # 走道上壁
        (T, 210, W - T, 230),            # 走道下壁
    ]
    return rects, W, H


def test_narrow_corridor_survives_closing_kernel():
    # T=20 → 最小封口核 2*round(1.5*20)+1 = 61px > 走道 40px。
    # 舊行為：走道被閉運算填實，只剩上下兩房。
    # 要求：三個空間都存活，且走道面積約 40px ×走道長。
    rects, W, H = _corridor_plan()
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0)
    assert labels is not None
    assert len(rooms) == 3, f"應切出 3 間（含 40px 走道），實得 {len(rooms)}"
    heights = sorted(r["bbox"][3] - r["bbox"][1] for r in rooms)
    assert heights[0] <= 45, f"最矮的空間應是 ~40px 走道，實得 {heights}"


def test_image_margin_is_not_a_room():
    # floor19 實案：外牆與影像邊界間的窄邊條，舊行為被大核閉運算填掉而
    # 隱性排除；牆扣除改髮絲核後邊條裸露成「室內」，整圈白邊變假房間。
    # 要求：把建物平移離影像邊 60px 後，仍只切出 3 間，且無任何房間
    # 的 bbox 觸及影像邊界。
    rects, W, H = _corridor_plan()
    off = 60
    rects = [(x0 + off, y0 + off, x1 + off, y1 + off)
             for x0, y0, x1, y1 in rects]
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W + 2 * off, H + 2 * off, T=20, T_out=20, cm=1.0)
    assert labels is not None
    assert len(rooms) == 3, f"邊條不應成房，應 3 間，實得 {len(rooms)}"
    for r in rooms:
        x0, y0, x1, y1 = r["bbox"]
        assert x0 > 2 and y0 > 2 and x1 < W + 2 * off - 2 \
            and y1 < H + 2 * off - 2, f"房間 bbox 觸及影像邊界: {r['bbox']}"


def test_keep_small_defers_area_floor():
    # floor13 實案：走道被跨走道封口盒切成 ~3600px 碎片，正好卡在
    # amin=2*(2T)^2=3200~3528 邊緣線上，碎片死在門檻、橋合併無從救起。
    # 修法：keep_small=True 時門檻降為 (2T)^2，碎片先活著進橋合併，
    # 面積終篩由 build_rooms 在合併後執行。
    rects, W, H = _corridor_plan()
    # 加一間 55×55=3025px 的小房（< 2*(2T)^2=3200、> (2T)^2=1600）：
    # 右下角以牆隔出，完全封閉
    rects += [
        (505, 325, 580, 345),                # 小房上壁
        (505, 345, 525, 400),                # 小房左壁
    ]                                        # 右/下沿用外牆，內部 55×55=3025px
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0)
    assert len(rooms) == 3, f"預設行為：小房仍被門檻淘汰，實得 {len(rooms)}"
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0, keep_small=True)
    assert len(rooms) == 4, f"keep_small：小房應存活，實得 {len(rooms)}"


def test_thin_fence_rescue_round():
    # floor02 實案：通往露臺的 L 型開口 ~185px，牆端射線與大核閉運算
    # 都搭不到橋，室外灌進客餐廳，覆蓋率 0.27 < 0.30 整圖被拒。
    # 救援輪：四輪全敗時用細線層（露臺圍欄線）當灌水屏障再試一次。
    rects = [
        (0, 0, 600, 20),                     # 上外牆
        (0, 0, 20, 420),                     # 左外牆
        (580, 0, 600, 420),                  # 右外牆
        (0, 400, 200, 420),                  # 下外牆只蓋左 1/3——右側 380px
    ]                                        # 大開口通往「露臺」，無牆可封
    W, H = 600, 420
    thin = np.zeros((H, W), np.uint8)
    thin[410:412, 180:600] = 255             # 露臺圍欄細線把開口圍住
    thin[300:302, 300:500] = 255             # 室內雜線（家具），不影響
    no_rescue = fp_c.segment_rooms(rects, [], [], W, H, T=20, T_out=20,
                                   cm=1.0)
    assert no_rescue[0] is None, "無細線層時本圖應整圖失敗（前置條件）"
    labels, rooms, outside = fp_c.segment_rooms(rects, [], [], W, H,
                                                T=20, T_out=20, cm=1.0,
                                                thin=thin)
    assert labels is not None, "細線圍欄救援輪應把室內救回來"
    assert len(rooms) >= 1
    tot = sum(r["area_px"] for r in rooms)
    assert tot > 0.5 * (560 * 380), f"室內覆蓋應過半，實得 {tot}"


def test_room_area_reaches_wall_edge():
    # 牆扣除改用原始遮罩後，房間面積應貼回真牆邊——上房內部
    # (T..W-T)×(T..150) 的涵蓋率應 >0.9（舊行為被大核吃掉一圈）。
    rects, W, H = _corridor_plan()
    labels, rooms, outside = fp_c.segment_rooms(
        rects, [], [], W, H, T=20, T_out=20, cm=1.0)
    assert labels is not None
    top = (W - 2 * 20) * (150 - 20)
    got = max(int((labels[:150, :] == r["id"]).sum()) for r in rooms)
    assert got > 0.9 * top, f"上房涵蓋率 {got / top:.2f} 應 >0.9"


def test_noisy_fence_round_rejected():
    # floor30 實案（color 保留集）：深色磁磚地板讓細線層在室內佈滿噪點，
    # 常規輪全敗時 fence 輪用噪點屏障拼出 25 塊碎片房「成功」，反而搶走
    # build_rooms 第三級救援（360cm 封口）的路——碎片房紮實度低
    # （面積/bbox 遠小於直角房間的 ~0.9），fence 輪須驗收後讓路
    rects = [
        (0, 0, 600, 20),
        (0, 0, 20, 420),
        (580, 0, 600, 420),
        (0, 400, 200, 420),                  # 同 rescue 測試的大開口
    ]
    W, H = 600, 420
    rng = np.random.RandomState(9)
    coarse = (rng.rand(H // 24, W // 24) < 0.35).astype(np.uint8) * 255
    tile = np.kron(coarse, np.ones((24, 24), np.uint8))
    thin = np.zeros((H, W), np.uint8)
    thin[:tile.shape[0], :tile.shape[1]] = tile[:H, :W]
    # 磁磚紋理是塊狀而非鹽噪——留下的大塊碎片才過得了面積門檻
    labels, rooms, _ = fp_c.segment_rooms(rects, [], [], W, H,
                                          T=20, T_out=20, cm=1.0, thin=thin)
    assert labels is None, \
        f"噪點 fence 輪應驗收失敗讓路給上層救援，實得 {len(rooms)} 房"
