#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""floorplan2room.py — 平面圖 → 房間方塊（不出 DXF）。

自動判斷輸入是黑白線稿還是彩色渲染圖：
  黑白 → 走 floorplan2dxf.py 的偵測（牆/門/窗全開）
  彩色 → 走 floorplan2dxf_color.py 的 detect_walls（現階段只抓牆）

抓到牆(紅色牆塊)後，把牆端點沿軸向連到對面的牆端點/牆面（封門洞、
牆縫開口），平面就閉合成一塊塊方塊＝房間，再依規則分類房型。

輸出：
  chk/room/<名>_room.png   房間疊圖：紅=牆、橘=牆端連線(封口)、綠=窗、房型色塊+房名
  chk/room/<名>_door.png   門位檢查圖（獨立）：黃框=門位+門寬標註；
                           連線長度 80~95(單門) 或 160~190(雙開門) cm 才算門
  json/<名>_room.json      房間清單（房型/面積/bbox/有無門/辨識證據）＋門位＋比例資訊

比例尺以門寬鐵律校正（refine_scale）：單門 85cm / 雙門 175cm / 牆厚 17.5cm。
房型以辨識決定（放棄面積規則）：CubiCasa 語意投票 + 圖示 + 古典符號偵測。

用法：
  python floorplan2room.py              # 批次 png/ → chk/room/
  python floorplan2room.py 圖.png       # 單張
  python floorplan2room.py 目錄 [輸出]  # 批次指定目錄
"""
import argparse
import glob
import json
import os
import subprocess
import sys
from dataclasses import replace

import cv2
import numpy as np

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
sys.path.insert(0, _SCRIPTS_DIR)       # 管線模組統一放 scripts/

import floorplan2dxf as fp_bw          # 黑白線稿管線（凍結，只 import 不改）
import floorplan2dxf_color as fp_c     # 彩色管線（牆偵測 + 房間分割/分類工具）
import symbol_match                    # 符號模板庫比對（庫檔缺失＝不啟用）

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")
COLOR_RATIO = 0.08                     # 與 fp_c.color_to_bw 同門檻：彩色像素比例


# ─────────────────────────── 彩色/黑白判斷 ───────────────────────────
def probe_color(path):
    """判斷圖是彩色還是黑白。與 fp_c.color_to_bw 用同一準則：
    HSV 飽和度>60 且亮度>60 的像素比例 ≥ 8% = 彩色；檔名含 color 強制彩色。
    alpha 圖層先合成到白底（同 load_gray），避免透明區干擾統計。"""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"讀不到圖: {path}")
    if img.ndim == 2:
        return False, 0.0
    if img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        bgr = cv2.merge([b, g, r])
        white = np.full_like(bgr, 255)
        am = a.astype(np.float32) / 255
        bgr = (bgr * am[..., None] + white * (1 - am[..., None])).astype(np.uint8)
    else:
        bgr = img[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    _h, s, v = cv2.split(hsv)
    colorful = float(np.count_nonzero((s > 60) & (v > 60))) / s.size
    force = "color" in os.path.basename(path).lower()
    return (force or colorful >= COLOR_RATIO), colorful


# ─────────────────────────── 兩條偵測管線 ───────────────────────────
def detect_bw(cfg):
    """黑白線稿：複製 fp_bw.run() solid 模式的偵測段（不寫任何檔案）。
    回傳統一格式 dict：rects/wins/doors/T/T_out/cm/bgr/thin/img_w/img_h。"""
    gray, bgr = fp_bw.load_gray(cfg)
    if cfg.deskew:
        gray, a = fp_bw.deskew(gray)
        print(f"deskew : 轉正 {a:+.2f}°")
    bw = fp_bw.binarize(gray, cfg)
    img_h, img_w = bw.shape[:2]
    bw, _n = fp_bw.remove_solid_blobs(bw)

    dt = cv2.distanceTransform(bw, cv2.DIST_L2, 5)
    T = max(2, int(round(2.0 * float(dt.max()))))
    pick = lambda v, d: (v if v not in (None, 0) else d)
    cfg.solid = pick(cfg.solid, max(3, int(round(0.35 * T))))
    cfg.h_len = pick(cfg.h_len, max(int(round(1.5 * T)), cfg.solid + 2))
    cfg.v_len = pick(cfg.v_len, cfg.h_len)
    cfg.snap = pick(cfg.snap, float(max(3, int(round(0.6 * T)))))
    cfg.gap = pick(cfg.gap, float(max(3, int(round(0.4 * T)))))
    cfg.min_len = pick(cfg.min_len, float(max(int(round(1.0 * T)), 4)))
    print(f"自動牆厚 T={T}px")

    if cfg.solid > 0:
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.solid, cfg.solid))
        bw_open = cv2.morphologyEx(bw, cv2.MORPH_OPEN, ker)
    else:
        bw_open = bw
    orig = bw                                    # 含細線的原始二值（判窗/設備線密度用）

    rects = fp_bw.detect_solid(bw_open, cfg, T)
    thin = cv2.subtract(orig, cv2.dilate(bw_open, np.ones((3, 3), np.uint8)))
    doors = fp_bw.detect_doors(thin, T, cfg.door_arc_pct)
    if cfg.invert:
        soft = orig
    else:
        _, soft = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    wins = fp_bw.detect_windows(orig, rects, cfg, T, doors, thin, soft)

    T_out = fp_bw.outer_wall_thickness(rects, T)
    mmpp, sinfo = fp_bw.derive_door_scale(doors, T_out, cfg)
    return {"rects": rects, "wins": wins, "doors": doors, "T": T, "T_out": T_out,
            "cm": mmpp / 10.0, "bgr": bgr, "thin": thin,
            "img_w": img_w, "img_h": img_h, "scale_info": sinfo}


def detect_color(cfg):
    """彩色渲染圖：直接用 fp_c.detect_walls 共用流程（含基柱/灰度過濾/語意融合）。
    彩色管線現階段門/窗停用 → doors/wins 空，封口全靠牆縫開口偵測。"""
    rects, bgr, _bw, _bw_open, T, img_w, img_h, _is_color = fp_c.detect_walls(cfg)
    T_out = fp_c.outer_wall_thickness(rects, T)
    mmpp, sinfo = fp_c.derive_door_scale([], T_out, cfg)
    return {"rects": rects, "wins": [], "doors": [], "T": T, "T_out": T_out,
            "cm": mmpp / 10.0, "bgr": bgr, "thin": None,
            "img_w": img_w, "img_h": img_h, "scale_info": sinfo}


# ─────────────────────────── 比例尺校正 ───────────────────────────
DOOR_RANGES_CM = ((80.0, 95.0), (160.0, 190.0))    # 單門 / 雙開門（user spec）
DOOR_SINGLE_CM = 85.0                              # 單門錨點：80~90(最多95) 取中值
DOOR_DOUBLE_CM = 175.0                             # 雙開門錨點：160~190 取中值
WALL_MID_CM = 17.5                                 # 人住建築牆厚 15~20cm 取中點


def refine_scale(det):
    """比例尺校正（user spec）：門寬是物理鐵律——單門 80~95cm、雙門 160~190cm、
    牆厚 15~20cm。上游初始比例把外牆撐到 15cm「下限」，系統性偏大 5~8%，
    真門會被量成 100~108cm。改以牆縫開口的「單門候選群」中位數＝85cm 反推比例
    （樣本多、分布緊，是最強錨點）；沒有單門候選才用雙門群＝175cm；
    都沒有則回退 外牆厚=17.5cm。外牆換算落在 10~25cm 之外視為錨錯，同樣回退。"""
    rects, wins = det["rects"], det["wins"]
    T, T_out, cm0 = det["T"], det["T_out"], det["cm"]
    gaps = [g1 - g0 for _h, g0, g1, _b0, _b1
            in fp_c._wall_gaps(rects, wins, T, cm0, 40.0, 300.0)]
    singles = [g for g in gaps if 60.0 <= g * cm0 <= 130.0]
    doubles = [g for g in gaps if 140.0 <= g * cm0 <= 240.0]
    if singles:
        cm1, method, used = DOOR_SINGLE_CM / float(np.median(singles)), \
            "door_single", len(singles)
    elif doubles:
        cm1, method, used = DOOR_DOUBLE_CM / float(np.median(doubles)), \
            "door_double", len(doubles)
    else:
        cm1, method, used = WALL_MID_CM / T_out, "wall_mid", 0
    wall_cm = T_out * cm1
    if not (10.0 <= wall_cm <= 25.0):            # 門錨算出離譜外牆 → 回退牆厚中點
        cm1, method, used = WALL_MID_CM / T_out, "wall_mid", 0
        wall_cm = WALL_MID_CM
    det["cm"] = cm1
    det["scale_info"] = {
        "method": method, "gaps_used": used,
        "cm_per_px_initial": round(cm0, 4),
        "outer_wall_cm": round(wall_cm, 1),
        "door_anchor_cm": {"door_single": DOOR_SINGLE_CM,
                           "door_double": DOOR_DOUBLE_CM}.get(method),
    }
    print(f"比例尺 : {cm1:.4f} cm/px（{method}, 開口樣本 {used}，"
          f"外牆 {wall_cm:.1f}cm；初始 {cm0:.4f}）")


# ─────────────────────────── 古典符號偵測 ───────────────────────────
def detect_symbols(det):
    """家具符號的古典幾何偵測——CubiCasa 對美式極簡線稿沒把握時的補充證據。
    在細線層(牆以外的家具線)上，以「實體尺寸(cm)」規則辨識，比例尺已由門寬校正：
      oval    衛浴橢圓設備(馬桶碗/洗手台)：20~60×28~75cm、拉長 1.15~1.8 倍
              (排除洗衣機圓鼓/圓桌/方椅)，且輪廓點對擬合橢圓的徑向偏差 ≤4%
              ——實測馬桶真橢圓偏差 ~1.6%，家具/圓角矩形 ≥7%，鑑別度極高
      tubrect 浴缸候選：貼滿 bbox 的矩形 70~100×150~190cm
              (計分時同室有 oval 才判浴缸——單人床/沙發同尺寸,單獨出現不採證)
      bedrect 床：貼滿 bbox 的矩形 120~230×180~235cm——雙人床寬 ≥120
              (沙發縱深 ≤100 進不來；單人床犧牲,精準優先)
      stove   爐台：≥2 個燃燒圈(半徑 5~14cm)聚在 80cm 內
    回傳 [(kind, cx, cy)]（px 座標）。彩圖管線沒有細線層 → 空清單。"""
    thin, cm = det.get("thin"), det["cm"]
    if thin is None:
        return []
    closed = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    syms = []
    cnts, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for c in cnts:
        if len(c) < 20:
            continue
        x, y, w, h = cv2.boundingRect(c)
        lo, hi = sorted((w * cm, h * cm))
        if 20.0 <= lo <= 60.0 and 28.0 <= hi <= 75.0 and 1.15 <= hi / lo <= 1.8:
            (ex, ey), (ma, mb), ang = cv2.fitEllipse(c)
            area = cv2.contourArea(c)
            ell = np.pi * ma * mb / 4.0
            hull_a = max(cv2.contourArea(cv2.convexHull(c)), 1.0)
            if not (ell > 0 and 0.75 <= area / ell <= 1.25
                    and area / hull_a >= 0.85):
                continue
            # 徑向偏差：輪廓點轉到橢圓座標系，|r-1| 平均 ≤5% 才是真橢圓
            th = np.deg2rad(ang)
            pts = c[:, 0, :].astype(np.float64) - (ex, ey)
            u = pts[:, 0] * np.cos(th) + pts[:, 1] * np.sin(th)
            v = -pts[:, 0] * np.sin(th) + pts[:, 1] * np.cos(th)
            rr = np.sqrt((u / (ma / 2.0)) ** 2 + (v / (mb / 2.0)) ** 2)
            if float(np.abs(rr - 1.0).mean()) <= 0.04:
                syms.append(("oval", x + w / 2.0, y + h / 2.0))
        elif cv2.contourArea(c) >= 0.75 * w * h:     # 貼滿 bbox＝矩形輪廓
            if 70.0 <= lo <= 100.0 and 150.0 <= hi <= 190.0:
                syms.append(("tubrect", x + w / 2.0, y + h / 2.0))
            elif 120.0 <= lo <= 230.0 and 180.0 <= hi <= 235.0:
                syms.append(("bedrect", x + w / 2.0, y + h / 2.0))
    uniq = []                                        # 同類 20cm 內去重(內外輪廓算兩次)
    for kind, sx, sy in syms:
        if not any(k == kind and abs(sx - ux) * cm < 20 and abs(sy - uy) * cm < 20
                   for k, ux, uy in uniq):
            uniq.append((kind, sx, sy))
    syms = uniq
    r_lo = max(3, int(round(5.0 / cm)))              # 燃燒圈半徑 5~14cm
    r_hi = max(r_lo + 2, int(round(14.0 / cm)))
    circ = cv2.HoughCircles(closed, cv2.HOUGH_GRADIENT, dp=1,
                            minDist=max(6, int(round(12.0 / cm))),
                            param1=120, param2=18, minRadius=r_lo, maxRadius=r_hi)
    if circ is not None:
        pts = [(float(cx), float(cy)) for cx, cy, _r in circ[0]]
        used = set()
        win = 80.0 / cm                              # 燃燒圈聚在 80cm 內＝一座爐台
        for i, (cx, cy) in enumerate(pts):
            if i in used:
                continue
            grp = [j for j, (px, py) in enumerate(pts)
                   if abs(px - cx) <= win and abs(py - cy) <= win]
            if len(grp) >= 2:
                used.update(grp)
                gx = sum(pts[j][0] for j in grp) / len(grp)
                gy = sum(pts[j][1] for j in grp) / len(grp)
                syms.append(("stove", gx, gy))
    # 模板庫比對（路線 B）：與上述手寫規則並行互補——規則命中的不動，
    # 模板只補漏網（同 kind 20cm 內視為已有）。庫檔缺失＝回空清單，行為不變。
    for kind, sx, sy in symbol_match.match_symbols(det):
        if not any(k == kind and abs(sx - ux) * cm < 20 and abs(sy - uy) * cm < 20
                   for k, ux, uy in syms):
            syms.append((kind, sx, sy))
    return syms


# ─────────────────────────── 語意辨識房型 ───────────────────────────
CC_CACHE_DIR = os.environ.get("CC_CACHE_DIR", "cubicasa_room")  # CubiCasa 語意快取（含 room/icon 通道）
CC_WEIGHTS = os.environ.get("CC_WEIGHTS", "model_best_val_loss_var.pkl")  # 環境變數可換微調權重 A/B 驗收
CC_ROOM_LABEL = {3: "kitchen", 4: "living", 5: "bed", 6: "bath",
                 7: "entry", 9: "storage", 10: "garage", 1: "outdoor"}
CC_ICON = {"closet": 3, "appliance": 4, "toilet": 5, "sink": 6,
           "sauna": 7, "fireplace": 8, "bathtub": 9}
ROOM_ZH_EX = {**fp_c.ROOM_ZH, "entry": "玄關", "storage": "儲藏室",
              "garage": "車庫", "outdoor": "陽台/戶外"}
ROOM_BGR_EX = {**fp_c.ROOM_BGR, "entry": (120, 210, 250),
               "storage": (180, 180, 120), "garage": (130, 130, 130),
               "outdoor": fp_c.ROOM_BGR["balcony"]}


def _cc_path(img_path):
    base = os.path.splitext(os.path.basename(img_path))[0]
    return os.path.join(CC_CACHE_DIR, base + "_mask.npz")


def _cc_ok(npz_path):
    if not os.path.isfile(npz_path):
        return False
    with np.load(npz_path) as z:                   # 舊版快取沒有 room 通道 → 重推
        return "room" in z.files


def ensure_cc_masks(paths):
    """缺語意快取的圖先跑 CubiCasa 推論（一次 subprocess 全補，CPU 約 1 分/張）。"""
    miss = [p for p in paths if not _cc_ok(_cc_path(p))]
    if not miss:
        return
    if not os.path.isfile(CC_WEIGHTS):
        print(f"⚠ 找不到 {CC_WEIGHTS}，跳過語意辨識（房型退回面積規則）")
        return
    print(f"CubiCasa 語意推論 : {len(miss)} 張（CPU 約 1 分/張 → {CC_CACHE_DIR}/）")
    subprocess.run([sys.executable,
                    os.path.join(_SCRIPTS_DIR, "infer_cubicasa.py"),
                    CC_WEIGHTS, CC_CACHE_DIR, *miss], check=True)


def classify_rooms_cc(det, labels, rooms, cc_file):
    """辨識式房型（user spec：放棄面積規則）：把每個方塊切出來，
    以 CubiCasa 房間語意像素投票 + 設備圖示證據命名用途。三層證據：
    1) 語意佔比：模型直接說這塊是臥室/客廳/…（乾淨渲染圖很準,佔比 0.9+）
    2) 相對多數票：線稿圖大片像素被標「未定義」,已分類像素內的多數類仍有資訊
    3) 圖示絕對面積(cm²)：馬桶/浴缸=浴室鐵證、爐具+水槽=廚房、衣櫃=儲藏——
       設備尺寸是物理常數,用絕對面積不會被大房間稀釋。
       桑拿椅在美式圖全是誤報(芬蘭訓練集特有),只記錄不採證。
    總分最高者勝；證據太弱(<0.15)標中性「空間」。"""
    cm = det["cm"]
    with np.load(cc_file) as z:
        cc_room, cc_icon = z["room"], z["icon"]
    if cc_room.shape != labels.shape:              # 彩圖管線可能放大 2 倍
        h, w = labels.shape
        cc_room = cv2.resize(cc_room, (w, h), interpolation=cv2.INTER_NEAREST)
        cc_icon = cv2.resize(cc_icon, (w, h), interpolation=cv2.INTER_NEAREST)
    for r in rooms:
        m = labels == r["id"]
        npx = max(1, int(np.count_nonzero(m)))
        area_cm2 = r["area_px"] * cm * cm
        r["area_m2"] = round(area_cm2 / 1e4, 2)
        votes = np.bincount(cc_room[m], minlength=12).astype(np.float64) / npx
        icx = {k: float(np.count_nonzero(cc_icon[m] == v)) / npx * area_cm2
               for k, v in CC_ICON.items()}       # 圖示絕對面積(cm²)
        score = {lab: votes[cls] for cls, lab in CC_ROOM_LABEL.items()}
        typed = sum(score.values())               # 相對多數票（層 2）
        if typed >= 0.05:
            top = max(score, key=score.get)
            score[top] += 0.12 * (score[top] / typed)
        if icx["toilet"] >= 150 or icx["bathtub"] >= 500:   # 圖示證據（層 3）
            score["bath"] += 0.5
        if icx["sink"] >= 150 and icx["toilet"] >= 100:
            score["bath"] += 0.3
        # 開放式客廳（客廳票強且遠勝廚房票）不給廚房圖示加分——
        # 客餐廚一體的大方塊應命名為客廳，爐台水槽只是角落
        open_living = votes[4] >= 0.15 and votes[4] > 2.0 * votes[3]
        if not open_living:
            if icx["appliance"] >= 500 and icx["sink"] >= 80:
                score["kitchen"] += 0.4
            elif icx["appliance"] >= 1200:
                score["kitchen"] += 0.25
        # 儲藏室=整間都是櫃(密度≥8%)且無臥室票；臥室附衣櫥只是牆邊一條,密度低
        if icx["closet"] >= 600 and votes[5] < 0.05 \
                and icx["closet"] / area_cm2 >= 0.08:
            score["storage"] += 0.2
        # 古典符號證據（層 4）：模型圖示沒抓到時的補充（美式極簡線稿）
        n = {"oval": 0, "tubrect": 0, "bedrect": 0, "stove": 0,
             "shower": 0, "sinkicon": 0}
        for kind, sx, sy in det.get("symbols", ()):
            iy, ix = int(round(sy)), int(round(sx))
            if 0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1] \
                    and labels[iy, ix] == r["id"]:
                n[kind] += 1
        if n["oval"]:                                # 馬桶/洗手台橢圓
            score["bath"] += 0.45 + 0.2 * min(n["oval"] - 1, 2)
            if n["tubrect"]:                         # 浴缸矩形＋橢圓同室 → 鐵證
                score["bath"] += 0.3
        if n["stove"] and not open_living:           # 爐台燃燒圈
            score["kitchen"] += 0.5
        if n["bedrect"]:                             # 雙人床矩形
            score["bed"] += 0.5
        if n["shower"]:                              # 模板：淋浴間（保守權重）
            score["bath"] += 0.3
        if n["sinkicon"] and not open_living:        # 模板：水槽（保守權重）
            score["kitchen"] += 0.15
        r["symbols"] = {k: v for k, v in n.items() if v}
        lab, val = max(score.items(), key=lambda kv: kv[1])
        r["label"] = lab if val >= 0.15 else "room"
        r["label_zh"] = ROOM_ZH_EX[r["label"]]
        r["cc_share"] = {k: round(v, 3) for k, v in score.items() if v >= 0.02}
        r["icons_cm2"] = {k: round(v) for k, v in icx.items() if v >= 20}


# ─────────────────────────── 房間方塊 ───────────────────────────


def _bridge_zone(horiz, g0, g1, b0, b1):
    """牆端連線 → 門位框：沿牆=連線長，垂直牆前後各一倍（1:2 黃框，
    同 fp_c.gap_openings 的格式，door tuple 供 room_graph 幾何驗證）。"""
    gap = g1 - g0
    m = (b0 + b1) / 2.0
    if horiz:
        d = (g0, m, gap, 1.0, 1.0, 1.0)
        mx, my = (g0 + g1) / 2.0, m
        ax, ay, sx, sy = gap / 2.0, 0.0, 0.0, gap
    else:
        d = (m, g0, gap, 1.0, 1.0, 1.0)
        mx, my = m, (g0 + g1) / 2.0
        ax, ay, sx, sy = 0.0, gap / 2.0, gap, 0.0
    quad = [(mx - ax - sx, my - ay - sy), (mx + ax - sx, my + ay - sy),
            (mx + ax + sx, my + ay + sy), (mx - ax + sx, my - ay + sy)]
    return quad, d


def build_rooms(det):
    """牆 → 房間方塊：牆端點沿軸向連到對面牆（fp_c._wall_gaps 封口）＋門洞補線
    ＋閉運算，閉合後灌水切連通塊＝房間，再依規則分類房型。
    門位（user spec）：連線長度 80~95 或 160~190 cm 才算門、框黃框；
    範圍外的連線只封口不框。回傳 (labels, rooms, bridges, zones, edges)。"""
    rects, wins, doors = det["rects"], det["wins"], det["doors"]
    T, T_out, cm = det["T"], det["T_out"], det["cm"]
    img_w, img_h = det["img_w"], det["img_h"]

    # 牆端連線（「紅色線端點連到另一端」）：40~260cm 的牆縫開口全封
    bridges = fp_c._wall_gaps(rects, wins, T, cm, 40.0, 260.0)
    zones = [_bridge_zone(*b) for b in bridges
             if any(lo <= (b[2] - b[1]) * cm <= hi for lo, hi in DOOR_RANGES_CM)]
    labels, rooms, outside = fp_c.segment_rooms(rects, wins, doors,
                                                img_w, img_h, T, T_out, cm)
    if labels is None or not rooms:
        return None, [], bridges, zones, []
    cc_f = det.get("cc_file")
    if cc_f and _cc_ok(cc_f):                    # 辨識式房型（方塊切出來投票命名）
        classify_rooms_cc(det, labels, rooms, cc_f)
    else:                                        # 無語意快取才退回面積規則
        print("⚠ 無語意快取 → 房型退回面積規則")
        fp_c.classify_rooms(rooms, cm, det["thin"], labels)
    # room_graph 只拿來算 has_door/相鄰圖——黃框依長度規則全畫，不被它篩掉
    edges, _kept = fp_c.room_graph(labels, outside, rooms, zones, rects, wins, T)
    return labels, rooms, bridges, zones, edges


def preview_rooms(det, labels, rooms, bridges, path):
    """房間疊圖：房間依房型上色、紅=牆、橘=牆端連線(封口)、綠=窗、房名標字。
    門位黃框另出 _door.png（user spec：同一張太亂）。"""
    bgr = det["bgr"]
    vis = bgr.copy()
    fill = vis.copy()
    if rooms and labels is not None:
        for r in rooms:
            fill[labels == r["id"]] = ROOM_BGR_EX.get(r["label"] or "room",
                                                      (150, 150, 150))
    for x0, y0, x1, y1 in det["rects"]:
        cv2.rectangle(fill, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), -1)
    vis = cv2.addWeighted(fill, 0.45, vis, 0.55, 0)   # 半透明：紅牆 + 房型色塊
    for horiz, g0, g1, b0, b1 in bridges:             # 橘實線 = 牆端點連線
        m = (b0 + b1) / 2.0
        p1 = (int(g0), int(m)) if horiz else (int(m), int(g0))
        p2 = (int(g1), int(m)) if horiz else (int(m), int(g1))
        cv2.line(vis, p1, p2, (0, 140, 255), max(2, int(det["T"] // 2)))
    for _o, x0, y0, x1, y1 in det["wins"]:
        cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (0, 170, 0), 2)
    if rooms:
        for r in rooms:                               # 無門空間 → 紅框警示
            if not r.get("has_door", True):
                x0, y0, x1, y1 = r["bbox"]
                cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 0, 255), 3)
        vis = fp_c._draw_room_text(vis, rooms)
    cv2.imwrite(path, vis)


def preview_doors(det, zones, path):
    """門位檢查圖（獨立輸出）：紅=牆、黃框=門位、框旁標門寬 cm。"""
    vis = det["bgr"].copy()
    fill = vis.copy()
    for x0, y0, x1, y1 in det["rects"]:
        cv2.rectangle(fill, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), -1)
    vis = cv2.addWeighted(fill, 0.35, vis, 0.65, 0)
    for quad, d in zones:
        pts = np.array([[int(round(x)), int(round(y))] for x, y in quad])
        cv2.polylines(vis, [pts], True, (0, 255, 255), 3)
        cx = int(sum(p[0] for p in quad) / 4)
        cy = int(sum(p[1] for p in quad) / 4)
        cv2.putText(vis, f'{d[2] * det["cm"]:.0f}cm', (cx - 30, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
    cv2.imwrite(path, vis)


def write_rooms_json(path, det, rooms, zones, edges, is_color, colorful):
    data = {
        "image": {"w": det["img_w"], "h": det["img_h"]},
        "is_color": bool(is_color),
        "color_ratio": round(colorful, 4),
        "pipeline": "floorplan2dxf_color" if is_color else "floorplan2dxf",
        "cm_per_px": round(det["cm"], 4),
        "scale_info": det["scale_info"],
        "walls": len(det["rects"]),
        "windows": len(det["wins"]),
        "door_ranges_cm": [list(r) for r in DOOR_RANGES_CM],
        "doors": [{
            "length_cm": round(d[2] * det["cm"], 1),
            "type": "double" if d[2] * det["cm"] >= 160.0 else "single",
            "bbox": [round(min(p[0] for p in quad), 1),
                     round(min(p[1] for p in quad), 1),
                     round(max(p[0] for p in quad), 1),
                     round(max(p[1] for p in quad), 1)],
        } for quad, d in zones],
        "rooms": [{
            "id": r["id"], "label": r["label"], "label_zh": r["label_zh"],
            "area_m2": r["area_m2"], "bbox": list(r["bbox"]),
            "center": [round(r["cx"], 1), round(r["cy"], 1)],
            "aspect": r["aspect"], "has_door": bool(r.get("has_door", False)),
            "reach": bool(r.get("reach", False)),
            "cc_share": r.get("cc_share"), "icons_cm2": r.get("icons_cm2"),
            "symbols": r.get("symbols"),
        } for r in rooms],
        "adjacency": [list(e) for e in edges],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────── 單張 / 批次 ───────────────────────────
def process(path, out_dir, cfg_bw, cfg_color):
    base = os.path.splitext(os.path.basename(path))[0]
    is_color, colorful = probe_color(path)
    print(f"判別   : {'彩色' if is_color else '黑白'}圖（彩色比例 {colorful:.0%}）"
          f" → {'floorplan2dxf_color' if is_color else 'floorplan2dxf'}")
    # 每張用全新 cfg copy：px 參數維持空(None)，各自依自己的牆厚重新推導
    if is_color:
        det = detect_color(replace(cfg_color, input=path, output="", preview=None))
    else:
        det = detect_bw(replace(cfg_bw, input=path, output="", preview=None))
    refine_scale(det)                            # 門寬鐵律反推比例尺，修上游系統性偏大
    det["cc_file"] = _cc_path(path)
    det["symbols"] = detect_symbols(det)         # 古典家具符號（補模型盲區）

    labels, rooms, bridges, zones, edges = build_rooms(det)
    png_out = os.path.join(out_dir, base + "_room.png")
    door_out = os.path.join(out_dir, base + "_door.png")
    os.makedirs("json", exist_ok=True)
    json_out = os.path.join("json", base + "_room.json")
    preview_rooms(det, labels, rooms, bridges, png_out)
    preview_doors(det, zones, door_out)
    write_rooms_json(json_out, det, rooms, zones, edges, is_color, colorful)

    if rooms:
        names = "、".join(f'{r["label_zh"]}{r["area_m2"]}m²' for r in rooms)
        print(f"房間   : {len(rooms)} 間（{names}）  牆端連線 {len(bridges)} 條"
              f"  門位 {len(zones)} 個（80~95/160~190cm）")
    else:
        print("房間   : 分割失敗（殼封不起來）——疊圖仍輸出牆與連線供檢視")
    print(f"輸出   : {png_out}   {door_out}   {json_out}")
    return bool(rooms)


def main():
    p = argparse.ArgumentParser(
        description="平面圖 → 房間方塊（自動判黑白/彩色，調用對應管線，不出 DXF）。\n"
                    "不帶參數 = 批次跑 png/ 目錄 → chk/room/")
    p.add_argument("input", nargs="?", help="輸入圖檔(單張)或目錄(批次)；預設 png/")
    p.add_argument("output", nargs="?", help="輸出目錄（預設 chk/room/）")
    p.add_argument("--config", default="config.ini", help="黑白管線設定檔")
    p.add_argument("--config-color", default="config_color.ini", help="彩色管線設定檔")
    a = p.parse_args()

    cfg_bw = fp_bw.load_config(a.config)
    cfg_color = fp_c.load_config(a.config_color)
    out_dir = a.output or os.path.join("chk", "room")
    os.makedirs(out_dir, exist_ok=True)

    if a.input and os.path.isfile(a.input):
        ensure_cc_masks([a.input])
        process(a.input, out_dir, cfg_bw, cfg_color)
        return

    in_dir = a.input or "png"
    if not os.path.isdir(in_dir):
        sys.exit(f"找不到目錄 {in_dir}/  (請把要批次的圖檔放進去，或給單張圖檔路徑)")
    imgs = sorted(p_ for p_ in glob.glob(os.path.join(in_dir, "*"))
                  if p_.lower().endswith(IMG_EXTS))
    if not imgs:
        sys.exit(f"{in_dir}/ 裡找不到圖檔 ({'/'.join(IMG_EXTS)})")
    ensure_cc_masks(imgs)
    ok = fail = no_room = 0
    for p_ in imgs:
        print(f"=== {os.path.splitext(os.path.basename(p_))[0]} ===")
        try:
            if process(p_, out_dir, cfg_bw, cfg_color):
                ok += 1
            else:
                no_room += 1
        except Exception as e:
            print(f"  ✗ 失敗: {e}")
            fail += 1
    print(f"\n批次完成: 成功 {ok} / 分割失敗 {no_room} / 錯誤 {fail}")
    print(f"  疊圖 → {out_dir}/  (紅牆、橘=牆端連線、黃=門位80~95/160~190cm、房型色塊)")
    print(f"  JSON → json/  (<名>_room.json：房間+門位清單)")


if __name__ == "__main__":
    main()
