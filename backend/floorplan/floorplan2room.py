#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""floorplan2room.py — 平面圖 → 房間方塊（不出 DXF）。

自動判斷輸入是黑白線稿還是彩色渲染圖：
  黑白 → 走 floorplan2dxf.py 的偵測（牆/門/窗全開）
  彩色 → 走 floorplan2dxf_color.py 的 detect_walls（現階段只抓牆）

抓到牆(紅色牆塊)後，把牆端點沿軸向連到對面的牆端點/牆面（封門洞、
牆縫開口），平面就閉合成一塊塊方塊＝房間，再依規則分類房型。

輸出：
  temp/chk/room/<名>_room.png  房間疊圖：紅=牆、橘=牆端連線(封口)、綠=窗、房型色塊+房名
  temp/chk/door/<名>_door.png  門位檢查圖（獨立目錄）：黃框=門位+門寬標註；
                               連線長度 75~100(單門) 或 160~190(雙開門) cm 且有門扇墨水才算門
  temp/json/room/<名>_room.json 房間清單（房型/面積/bbox/有無門/辨識證據）＋門位＋比例資訊

比例尺以門寬鐵律校正（refine_scale）：單門 85cm / 雙門 175cm / 牆厚 17.5cm。
房型以辨識決定：DINOv2 房間裁切分類 + 古典符號偵測 + OCR 文字證據。

用法（不帶參數不跑，會要求給圖檔或目錄）：
  python floorplan2room.py 圖.png         # 單張，路徑相對當前目錄
  python floorplan2room.py png            # 批次 testdata/png/ → chk/room/
  python floorplan2room.py color_png      # 批次 testdata/color_png/
  python floorplan2room.py 目錄 [輸出]    # 批次指定目錄（相對當前目錄的路徑照用）
"""
import argparse
import difflib
import glob
import json
import os
import re
import subprocess
import sys
from dataclasses import replace

import cv2
import numpy as np

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_PKG_DIR))
sys.path.insert(0, _PKG_DIR)           # 管線模組（room_classifier、symbol_match）同在 backend/floorplan/

import floorplan2dxf as fp_bw          # 黑白線稿管線（凍結，只 import 不改）
import floorplan2dxf_color as fp_c     # 彩色管線（牆偵測 + 房間分割/分類工具）
import room_classifier                 # DINOv2 房型裁切分類（缺件＝停用，退回面積規則）
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

    T = fp_bw.derive_wall_T(bw)                  # 抗離群牆厚（與 fp_bw.run 同式）
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
            "cm": mmpp / 10.0, "bgr": bgr, "thin": thin, "domain": "gray",
            "img_w": img_w, "img_h": img_h, "scale_info": sinfo}


def detect_color(cfg):
    """彩色渲染圖：直接用 fp_c.detect_walls 共用流程（含基柱/灰度過濾/語意融合）。
    窗與細線層接回（floor_09 實案：外牆窗帶沒封口，灌水從窗漏到影像
    邊界，左半客廳/主臥被室外過濾整片剪掉）——窗封灌水的洞、thin 供
    segment_rooms 救援輪與門墨水否決。門弧偵測在彩圖未驗證，doors
    維持空，只借給 detect_windows 做誤判抑制。"""
    rects, bgr, bw, bw_open, T, img_w, img_h, _is_color = fp_c.detect_walls(cfg)
    T_out = fp_c.outer_wall_thickness(rects, T)
    orig_win, soft, thin = fp_c.color_window_layers(bgr, bw, bw_open)
    wins = []
    if cfg.windows and rects:
        arc_doors = fp_c.detect_doors(thin, T, cfg.door_arc_pct)
        cand = fp_c.detect_windows(orig_win, rects, cfg, T, arc_doors,
                                   thin, soft)
        # 內外側守門：彩圖窗偵測 P 63%，室內誤判窗（floor_04 中央假窗、
        # floor_05 房內白櫃）畫進封口遮罩會把房間攔腰切。真窗物理特徵
        # ＝恰好一側通室外；距離外圈/兩端錨定實測都分不開真假
        wins = fp_c.window_side_gate(cand, rects, T,
                                     fp_c.derive_door_scale(
                                         [], T_out, cfg)[0] / 10.0,
                                     img_w, img_h)
    mmpp, sinfo = fp_c.derive_door_scale([], T_out, cfg)
    # thin 只以 fence 身分供 segment_rooms 救援輪擋灌水；det["thin"] 維持
    # None——彩圖細線層滿是磁磚/家具中性線，墨水密度否決會把每道橋都
    # 當「有門墨水」，走道橫斷合併全被壓制（r1 實測過切 1.08→1.43、
    # floor_04 命中 8→3）
    return {"rects": rects, "wins": wins, "doors": [], "T": T, "T_out": T_out,
            "cm": mmpp / 10.0, "bgr": bgr, "thin": None, "fence": thin,
            "domain": "color",
            "img_w": img_w, "img_h": img_h, "scale_info": sinfo}


# ─────────────────────────── 比例尺校正 ───────────────────────────
DOOR_RANGES_CM = fp_c.DOOR_SIZE_RANGES_CM          # 單門/雙開門，門偵測重建後
                                                   # 與 DXF 批次同源。單門原 user
                                                   # spec 80~95，門位掛上墨水證據後放寬
                                                   # 75~100：own 集門 GT 實測 R 0.56→0.73、
                                                   # P 0.90→0.86（floor04 比例尺被走道假開
                                                   # 口拉偏，真門量成 78cm 全漏）
DOOR_SINGLE_CM = fp_c.DOOR_SINGLE_ANCHOR_CM        # 錨點常數移居 fp_c
DOOR_DOUBLE_CM = fp_c.DOOR_DOUBLE_ANCHOR_CM        # （gap_scale 單一事實來源）
WALL_MID_CM = fp_c.WALL_MID_ANCHOR_CM


def refine_scale(det):
    """比例尺校正（user spec）：門寬是物理鐵律——單門 80~95cm、雙門 160~190cm、
    牆厚 15~20cm。上游初始比例把外牆撐到 15cm「下限」，系統性偏大 5~8%，
    真門會被量成 100~108cm。改以牆縫開口的「單門候選群」中位數＝85cm 反推比例
    （樣本多、分布緊，是最強錨點）；沒有單門候選才用雙門群＝175cm；
    都沒有則回退 外牆厚=17.5cm。外牆換算落在 10~25cm 之外視為錨錯，同樣回退。"""
    rects, wins = det["rects"], det["wins"]
    T, T_out, cm0 = det["T"], det["T_out"], det["cm"]
    cm1, method, used = fp_c.gap_scale(rects, wins, T, T_out, cm0)
    wall_cm = T_out * cm1
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
    syms.extend(detect_stairs(det))              # 樓梯踏板（模型盲區類 stair）
    return syms


# ─────────────────────────── 樓梯幾何（層 4）───────────────────────────
# CubiCasa 沒有樓梯輸出通道（StairWell→11 Undefined），而樓梯區「不可擺設」
# 是管線的硬需求（v2.14 使用者裁決），只能自己抓。
# 踏板在圖面上＝一疊平行、等長、等距的細線，尺寸全是建築常數，比例尺已由
# 門寬校正 → 用 cm 規則辨識，與 detect_symbols 同套路。
TREAD_DEPTH_CM = (21.0, 35.0)   # 踏面深度（法規/人因常數）
STAIR_RUN_CM = (70.0, 160.0)    # 梯段淨寬：單人梯 ~75cm 起，雙人梯 ~140cm
MIN_TREADS = 4                  # 踏板條數下限。Readme 2026-07-29 已記「衣櫃內部
                                # 分隔線／牆體剖面線與樓梯踏步幾何同構，本質不可
                                # 分辨」——衣櫃分隔通常 1~3 條、牆剖面線間距遠密
                                # 於踏面深度，條數＋間距是僅有的鑑別軸，寧漏勿誤
_SPACING_TOL = 1.35             # 間距一致性：最寬/最窄比值上限


def _axis_segments(lines, cm, horiz):
    """Hough 線段 → 指定方向的 (pos, lo, hi)。
    pos＝垂直於線段的座標（踏板的排列軸），lo/hi＝線段自身的延伸範圍。"""
    tol = max(1.0, 2.0 / cm)                     # 2cm 內視為軸對齊
    out = []
    for seg in lines:
        x1, y1, x2, y2 = (float(v) for v in seg[0])
        if horiz and abs(y2 - y1) <= tol:
            out.append(((y1 + y2) / 2.0, min(x1, x2), max(x1, x2)))
        elif not horiz and abs(x2 - x1) <= tol:
            out.append(((x1 + x2) / 2.0, min(y1, y2), max(y1, y2)))
    return out


def _merge_collinear(segs, cm):
    """同一條踏板可能被 Hough 切成數段，或內外緣各給一條——
    位置差 <5cm 且範圍相接者合併，避免灌水成假的踏板數。"""
    near = 5.0 / cm
    merged = []
    for pos, lo, hi in sorted(segs):
        for i, (p, l, h) in enumerate(merged):
            if abs(p - pos) <= near and lo <= h + near and hi >= l - near:
                merged[i] = ((p + pos) / 2.0, min(l, lo), max(h, hi))
                break
        else:
            merged.append((pos, lo, hi))
    return merged


def _stair_runs(segs, cm, horiz):
    """等距平行線段 → [(cx, cy)]；不足 MIN_TREADS 或間距不齊者不採。"""
    lo_len, hi_len = STAIR_RUN_CM
    cand = sorted(s for s in _merge_collinear(segs, cm)
                  if lo_len <= (s[2] - s[1]) * cm <= hi_len)
    d_lo, d_hi = TREAD_DEPTH_CM
    out, used = [], set()
    for i in range(len(cand)):
        if i in used:
            continue
        run = [i]
        for j in range(i + 1, len(cand)):
            pos_k, lo_k, hi_k = cand[run[-1]]
            pos_j, lo_j, hi_j = cand[j]
            gap = (pos_j - pos_k) * cm
            if gap < d_lo:                       # 太近＝同踏板殘影，略過不斷鏈
                continue
            if gap > d_hi:                       # 已排序，再往後只會更遠
                break
            ov = min(hi_j, hi_k) - max(lo_j, lo_k)
            if ov < 0.6 * min(hi_j - lo_j, hi_k - lo_k):
                continue                         # 橫向沒疊在一起＝不同構件
            run.append(j)
        if len(run) < MIN_TREADS:
            continue
        gaps = [(cand[b][0] - cand[a][0]) * cm for a, b in zip(run, run[1:])]
        if max(gaps) > _SPACING_TOL * min(gaps):  # 間距不齊＝散落家具線
            continue
        used.update(run)
        pos_c = sum(cand[k][0] for k in run) / len(run)
        lat_c = sum((cand[k][1] + cand[k][2]) / 2.0 for k in run) / len(run)
        pos0, pos1 = cand[run[0]][0], cand[run[-1]][0]
        lat0 = min(cand[k][1] for k in run)
        lat1 = max(cand[k][2] for k in run)
        box = (lat0, pos0, lat1, pos1) if horiz else (pos0, lat0, pos1, lat1)
        out.append(((lat_c, pos_c) if horiz else (pos_c, lat_c)) + (box,))
    return out


def detect_stairs(det):
    """細線層 → [("stair", cx, cy)]（px 座標）。
    彩圖管線沒有細線層 → 空清單（同 detect_symbols 契約）。"""
    thin, cm = det.get("thin"), det["cm"]
    if thin is None:
        return []
    min_len = max(8, int(round(STAIR_RUN_CM[0] / cm)))
    lines = cv2.HoughLinesP(thin, 1, np.pi / 180,
                            threshold=max(15, int(min_len * 0.5)),
                            minLineLength=min_len,
                            maxLineGap=max(2, int(round(5.0 / cm))))
    if lines is None:
        return []
    out = []
    for horiz in (True, False):
        for cx, cy, _box in _stair_runs(_axis_segments(lines, cm, horiz),
                                        cm, horiz):
            out.append(("stair", cx, cy))
    return out


def detect_stair_boxes(det):
    """踏板串外框 [(x0,y0,x1,y1)]，供 _carve_stairs 切房。
    與 detect_stairs 同源同參數，只是保留 _stair_runs 的 box。"""
    thin, cm = det.get("thin"), det["cm"]
    if thin is None:
        return []
    min_len = max(8, int(round(STAIR_RUN_CM[0] / cm)))
    lines = cv2.HoughLinesP(thin, 1, np.pi / 180,
                            threshold=max(15, int(min_len * 0.5)),
                            minLineLength=min_len,
                            maxLineGap=max(2, int(round(5.0 / cm))))
    if lines is None:
        return []
    out = []
    for horiz in (True, False):
        for _cx, _cy, box in _stair_runs(_axis_segments(lines, cm, horiz),
                                         cm, horiz):
            out.append(box)
    return out


# ─────────────────────────── OCR 文字證據（層 5）───────────────────────────
# 美式極簡線稿無家具符號、正解以文字印在圖上（floor04：DORMITORY/KITCHEN/…），
# 對 CubiCasa 是 OOD——區分資訊只存在於文字，25 張 own 集再 finetune 也學不到。
# 文字是作者親口說的答案，權重設在圖示證據(0.5)之上；圖上沒字＝零貢獻，
# 引擎缺席＝空清單，其他評測集行為與現行完全相同。
OCR_CONF_MIN = 0.7                     # rapidocr 實測正字信心 0.99+，0.7 已很寬
OCR_TEXT_W = 1.3                       # 壓過語意滿票+加成(1.12)：floor04 實測 DEPOSIT
                                       # →living 語意 1.0「自信地錯」，TODO 草案 0.65
                                       # 壓不過；語意+圖示鐵證聯手(≥1.7)仍可反壓誤讀
# 鍵＝圖面文字（一律大寫比對），值＝2026-08-01 定案的 10 類詞彙。
OCR_WORD2LABEL = {
    "DORMITORY": "Bedroom", "BEDROOM": "Bedroom",
    "KITCHEN": "Kitchen",
    "BATH": "Bath", "BATHROOM": "Bath", "WC": "Bath", "TOILET": "Bath",
    "LIVING": "LivingRoom", "LIVINGROOM": "LivingRoom",
    "LOUNGE": "LivingRoom",
    # 2026-08-01 使用者裁決：10 類別以外的「子區印字」不做辨識證據——
    # DINING/FOYER 這類無牆子區（餐區、門廳）不成房也不觸發切分，
    # 其歸屬由切線方正度決定（floor05 的 FOYER 區 GT 實測併入客廳）。
    # FAMILY ROOM／WASHROOM 是房型同義詞（起居室/浴廁）非子區詞，保留
    "FAMILY": "LivingRoom", "FAMILYROOM": "LivingRoom",
    "WASHROOM": "Bath",
    "DEPOSIT": "Storage", "STORAGE": "Storage", "CLOSET": "Storage",
    # 走道系詞彙 2026-08-01 從 Entry 改指 Hallway：圖面寫 CIRCULATION／HALLWAY
    # 的就是走道，玄關另有 ENTRY／ENTRANCE。舊映射把三者都算成玄關，是
    # 「Entry 與 Hallway 難分」在 OCR 層的同一個病灶。
    "CIRCULATION": "Hallway", "HALL": "Hallway", "HALLWAY": "Hallway",
    "CORRIDOR": "Hallway", "PASSAGE": "Hallway",
    # FOYER 於 2026-08-01 移除：門廳是無牆子區印字（floor05 GT 實測
    # 該區併入客廳），依「10 類別以外的字不採用」裁決不做辨識證據
    "ENTRY": "Entry", "ENTRANCE": "Entry",
    "BALCONY": "Balcony", "TERRACE": "Balcony",
    "GARAGE": "Garage",
    # 書房系詞彙 → Storage（office 已於 2026-07-29 併入 storage）。
    # STAIRWELL/STAIRCASE 含 STAIR，片語比對取最長鍵仍是 Stair。
    "OFFICE": "Storage", "STUDY": "Storage", "WORKROOM": "Storage",
    "DEN": "Storage", "LIBRARY": "Storage",
    "STAIR": "Stair", "STAIRS": "Stair", "STAIRWELL": "Stair",
    "STAIRCASE": "Stair",
}

_ocr_engine = None                     # 模組級單例：模型載入 ~1s，批次只付一次
_ocr_cache = {"path": None, "words": []}   # 單格快取：同圖 texts/text_boxes 兩問只推一次


def _ocr_words(img_path):
    """RapidOCR 行級辨識 → [(text, conf, cx, cy, (x0, y0, x1, y1))]（原圖 px）。
    引擎未安裝＝空清單並提示一次（OCR 是 semantic 同級 extra，不是硬依賴）。"""
    global _ocr_engine
    if _ocr_cache["path"] == img_path:
        return _ocr_cache["words"]
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except ImportError:
            print("⚠ rapidocr-onnxruntime 未安裝 → OCR 文字證據層停用")
            _ocr_engine = False
    if _ocr_engine is False:
        return []
    result, _elapse = _ocr_engine(img_path)
    words = [] if not result else \
        [(text, float(conf),
          sum(p[0] for p in box) / len(box),
          sum(p[1] for p in box) / len(box),
          (min(p[0] for p in box), min(p[1] for p in box),
           max(p[0] for p in box), max(p[1] for p in box)))
         for box, text, conf in result]
    _ocr_cache.update(path=img_path, words=words)
    return words


def ocr_room_label(text):
    """標注詞 → 房型 key；None＝非房型詞（尺寸/圖名等雜訊）。
    三段比對：正規化後精確 → 片語含鍵（MASTER BEDROOM/LIVINGROOM2）→
    模糊比對容 OCR 錯字（BATHR0OM→BATHROOM）。片語/模糊只認 ≥4 字鍵，
    WC 這種短鍵僅精確命中，避免雜訊誤收。"""
    t = re.sub(r"[^A-Z]", "", text.upper())
    if len(t) < 2:
        return None
    if t in OCR_WORD2LABEL:
        return OCR_WORD2LABEL[t]
    hits = [k for k in OCR_WORD2LABEL if len(k) >= 4 and k in t]
    if hits:
        return OCR_WORD2LABEL[max(hits, key=len)]
    close = difflib.get_close_matches(
        t, [k for k in OCR_WORD2LABEL if len(k) >= 4], n=1, cutoff=0.8)
    return OCR_WORD2LABEL[close[0]] if close else None


def detect_room_text(img_path, dst_w=None, dst_h=None):
    """OCR 文字證據（與 detect_symbols 平行的第 5 層）：
    圖上印的房型文字 → [(label, cx, cy, raw_text)]。
    座標依 dst_w/dst_h 縮放到分析圖空間（彩圖管線可能放大 2 倍）。
    限制：OCR 讀原始檔，deskew=true 轉正後座標會錯位（預設 false 不受影響）。"""
    words = _ocr_words(img_path)
    if not words:
        return []
    sx = sy = 1.0
    if dst_w and dst_h:
        img = cv2.imread(img_path)
        if img is None:                    # 拿不到原圖尺寸＝縮放未知，寧缺勿錯位
            print("⚠ OCR 原圖尺寸讀取失敗 → 本張文字證據放棄")
            return []
        h, w = img.shape[:2]
        sx, sy = dst_w / float(w), dst_h / float(h)
    out = []
    for text, conf, cx, cy, _box in words:
        if conf < OCR_CONF_MIN:
            continue
        lab = ocr_room_label(text)
        if lab:
            out.append((lab, cx * sx, cy * sy, text))
    return out


def detect_text_boxes(img_path, dst_w=None, dst_h=None):
    """圖面上全部文字的框（不限房型詞，conf ≥0.5 即收）→ [(x0,y0,x1,y1)]，
    座標同 detect_room_text 縮放到分析圖空間。用途：把文字墨水從細線層
    扣掉，避免污染門扇迴轉區的證據量測（floor04 的 CIRCULATION 實案）。"""
    words = _ocr_words(img_path)
    if not words:
        return []
    sx = sy = 1.0
    if dst_w and dst_h:
        img = cv2.imread(img_path)
        if img is None:
            return []
        h, w = img.shape[:2]
        sx, sy = dst_w / float(w), dst_h / float(h)
    return [(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
            for _t, conf, _cx, _cy, (x0, y0, x1, y1) in words if conf >= 0.5]


# ─────────────────────────── 房型詞彙表 ───────────────────────────
# id 沿用 CubiCasa5k 標注格式的 room class 編碼——GT 標注仍是該格式的 SVG，
# `eval_rooms_cc.gt_label_of` 需要這層映射把標注 token 轉成類別。產品推論路徑
# 只用到 `.values()`（類別集合），不碰 CubiCasa 的任何模型、權重或程式碼。
# 2026-08-01 `outdoor` 更名為 `balcony`（使用者裁決）：管線本來就有 balcony
# 這個鍵（fp_c.ROOM_ZH），outdoor 是 CubiCasa 詞彙留下的第二個名字，同一種
# 空間掛兩個名字，量尺還得靠 norm_label 把 balcony 折回 outdoor 才對得上。
CC_ROOM_LABEL = {3: "Kitchen", 4: "LivingRoom", 5: "Bedroom", 6: "Bath",
                 7: "Entry", 9: "Storage", 10: "Garage", 1: "Balcony"}
# 模型盲區類：DINOv2 的線性頭雖有 stair 通道，但該類的證據仍主要來自
# 層 4 的 detect_stairs 踏板幾何。必須另行播種進 score，否則 OCR 層的
# `if lab_t in score` 防呆會靜默丟掉證據。
#
# 註：曾短暫存在的 `office`（書房）已於 2026-07-29 併入 `storage`（使用者裁決）
# ——兩者實務上是同一空間的兩個狀態，且 DINOv2 實測從未把它們互相搞混，
# 分開標不帶來可量測資訊。書房系 OCR 詞彙改指向 storage。
# `hallway` 2026-08-01 一併播種：它與 stair 同樣不在 CC_ROOM_LABEL 裡，
# 不播種的話 `if lab in score` 會靜默丟掉證據，且 _entry_or_hallway 也無處
# 可寫——量尺看得到這一類、管線卻永遠答不出來（實測 P=R=0，賠掉 3 房）。
EXTRA_LABELS = ("Stair", "Hallway")
ROOM_ZH_EX = {**fp_c.ROOM_ZH, "Entry": "玄關", "Storage": "儲藏室",
              "Garage": "車庫", "Stair": "樓梯", "Hallway": "走道"}
ROOM_BGR_EX = {**fp_c.ROOM_BGR, "Entry": (120, 210, 250),
               "Storage": (180, 180, 120), "Garage": (130, 130, 130),
               "Stair": (70, 70, 200), "Hallway": (170, 170, 210)}




















def _apply_evidence(det, labels, r, score, open_living):
    """層 4（符號幾何＋模板＋樓梯）與層 5（OCR 文字）加分。
    就地改 score，並在 r 上記錄證據供追溯。原為 CubiCasa 與 DINOv2 兩條命名
    路徑共用而抽出；2026-07-30 前者移除後只剩一個呼叫端，但保持獨立函式——
    這兩層與層 1 的證據來源正交，分開才看得清楚誰貢獻了什麼。
    open_living：客餐廚一體時廚房系證據不加分（爐台水槽只是角落）。"""
# 古典符號證據（層 4）：模型圖示沒抓到時的補充（美式極簡線稿）
    # 後十類為 Asset 家具模板庫 kind（extract_asset_lib.py，分類依
    # 使用者裁決：dtable→kitchen、chair(單人沙發)→living）
    n = {"oval": 0, "tubrect": 0, "bedrect": 0, "stove": 0,
         "shower": 0, "sinkicon": 0,
         "wc": 0, "tub": 0, "basin": 0, "kstove": 0, "ksink": 0,
         "dtable": 0, "bed": 0, "wardrobe": 0, "sofa": 0, "chair": 0,
         "stair": 0, "trashcan": 0}
    for kind, sx, sy in det.get("symbols", ()):
        iy, ix = int(round(sy)), int(round(sx))
        if 0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1] \
                and labels[iy, ix] == r["id"]:
            n[kind] += 1
    # 注意：`n` 的鍵是符號種類（bed＝床的圖示、stair＝踏板），與房型類別名
    # 同形但不同義，2026-08-01 房型改 CamelCase 時不得一併改動。
    if n["oval"]:                                # 馬桶/洗手台橢圓
        score["Bath"] += 0.45 + 0.2 * min(n["oval"] - 1, 2)
        if n["tubrect"]:                         # 浴缸矩形＋橢圓同室 → 鐵證
            score["Bath"] += 0.3
    if n["stove"] and not open_living:           # 爐台燃燒圈
        score["Kitchen"] += 0.5
    if n["bedrect"]:                             # 雙人床矩形
        score["Bedroom"] += 0.5
    if n["shower"]:                              # 模板：淋浴間（保守權重）
        score["Bath"] += 0.3
    if n["sinkicon"] and not open_living:        # 模板：水槽（保守權重）
        score["Kitchen"] += 0.15
    # Asset 家具模板證據（存在制不疊加，權重保守——模板與考卷畫風
    # 有落差，寧漏勿誤；廚房系沿用 open_living 防呆）
    if n["wc"]:
        score["Bath"] += 0.4
    if n["tub"]:
        score["Bath"] += 0.3
    if n["basin"]:
        score["Bath"] += 0.2
    if n["kstove"] and not open_living:
        score["Kitchen"] += 0.35
    if n["ksink"] and not open_living:
        score["Kitchen"] += 0.2
    if n["dtable"] and not open_living:          # user 裁決：餐桌歸廚房
        score["Kitchen"] += 0.25
    if n["trashcan"] and not open_living:        # 美式畫風廚房垃圾桶（弱證據）
        score["Kitchen"] += 0.15
    if n["bed"]:
        score["Bedroom"] += 0.4
    if n["wardrobe"]:
        score["Bedroom"] += 0.2
    if n["sofa"]:
        score["LivingRoom"] += 0.3
    if n["chair"]:                               # user 裁決：單人沙發＝客廳
        score["LivingRoom"] += 0.15
    if n["stair"]:                               # 樓梯踏板（detect_stairs）
        # 權重高於一般家具：4+ 條等距等長踏板是強幾何約束，且 Stair 沒有
        # 語意票可搭配（模型盲區類），證據不夠力就永遠叫不出這個名字
        score["Stair"] += 0.6
    r["symbols"] = {k: v for k, v in n.items() if v}
    # OCR 文字證據（層 5）：字框中心落在這間房 → 該房型加分。
    # 同房同型多字只加一次（重複字樣不疊權），異型各加（衝突交給總分裁決）
    txt_hits = {}
    for lab_t, tx, ty, raw in det.get("texts", ()):
        iy, ix = int(round(ty)), int(round(tx))
        if 0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1] \
                and labels[iy, ix] == r["id"]:
            txt_hits.setdefault(lab_t, []).append(raw)
    for lab_t in txt_hits:
        if lab_t in score:             # 防呆：字典日後加了量尺外的房型 key 不炸
            score[lab_t] += OCR_TEXT_W
    if txt_hits:
        r["ocr_text"] = txt_hits




DINO_W = 1.0            # DINOv2 機率的權重。設 1.0 使其與 OCR(1.3) 的相對關係
                        # 維持「圖面文字是作者親口說的答案，可壓過模型」，
                        # 而符號證據(0.15~0.6)只在模型沒把握時才翻得動總分


def exterior_mask(det, labels=None):
    """牆/窗（可選：已知房間）當屏障，自影像邊界灌水 → 屋外自由區遮罩。

    `build_rooms` 的 outside 由 `segment_rooms` 一併算出，不需要本函式；這裡
    是給**沒跑分割的路徑**用的——量尺的 GT 解耦模式（`--gt-seg`）直接拿 GT
    多邊形當房間，不呼叫 segment_rooms，卻同樣需要屋外資訊才能判 Entry。

    把已知房間一併當屏障是必要的：牆偵測有缺口時，單靠牆會讓灌水從缺口漏進
    室內，整棟房子都變成「貼外牆」。"""
    rects, wins = det.get("rects") or (), det.get("wins") or ()
    if not rects:
        return None
    h = det.get("img_h") or (labels.shape[0] if labels is not None else 0)
    w = det.get("img_w") or (labels.shape[1] if labels is not None else 0)
    if not (h and w):
        return None
    barrier = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(barrier, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for _o, x0, y0, x1, y1 in wins:
        cv2.rectangle(barrier, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    if labels is not None:
        barrier[labels > 0] = 255
    ff = np.pad(barrier, 1).copy()
    cv2.floodFill(ff, None, (0, 0), 128)
    return ff[1:-1, 1:-1] == 128


def touches_exterior(labels, outside, rid, T_out):
    """房間是否貼著建物外牆——遮罩往外膨脹一個外牆厚，碰得到屋外自由區即是。

    回 None＝無屋外資訊（呼叫端不得據此改判）。"""
    if labels is None or outside is None:
        return None
    m = (labels == rid)
    if not m.any():
        return None
    k = 2 * max(2, int(round(1.5 * max(1.0, T_out)))) + 1
    grown = cv2.dilate(m.astype(np.uint8), np.ones((k, k), np.uint8))
    return bool((grown.astype(bool) & outside).any())


def rooms_with_exterior_door(det, labels, outside):
    """有門直通屋外的房間 id 集合——玄關的判準（使用者裁決 2026-08-01）。

    **為什麼不是「貼外牆」**：初版規則用貼牆判定，own_eval 只救回 4 間走道中
    的 1 間。floor74/76 的走道沿著外牆走卻沒有對外的門，照樣被判成玄關。
    玄關的定義是「走得出去」，該看的是門而不是牆。

    作法同 `fp_c.room_graph` 的門兩側取樣：沿門洞法線逐步走，一側走到房間、
    另一側走到屋外，那扇門就是大門。無法取得門位或屋外資訊時回 None（不表態，
    呼叫端不得據此改判）。"""
    rects, wins = det.get("rects") or (), det.get("wins") or ()
    doors, T, cm = det.get("doors") or (), det.get("T"), det.get("cm")
    if outside is None or labels is None or not rects or not doors or not T:
        return None
    wall = np.zeros(labels.shape, np.uint8)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(wall, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for _o, x0, y0, x1, y1 in wins:
        cv2.rectangle(wall, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    H, W = labels.shape

    def sample(mx, my, sx, sy):
        """房間id(>0) / -1=室外 / -2=沒撞牆走完 / 0=撞牆。同 room_graph 語義。"""
        k = 0.5 * T
        while k <= 4.0 * T:
            x, y = int(round(mx + sx * k)), int(round(my + sy * k))
            if not (0 <= x < W and 0 <= y < H):
                return -1
            if labels[y, x] > 0:
                return int(labels[y, x])
            if outside[y, x]:
                return -1
            if wall[y, x]:
                return 0
            k += max(2.0, 0.35 * T)
        return -2

    out = set()
    for _quad, d in fp_c.door_zones(doors, rects, T, cm or 1.0):
        _h, (mx, my), _a, s = fp_c._door_geometry(d, rects, T)
        ra, rb = sample(mx, my, s[0], s[1]), sample(mx, my, -s[0], -s[1])
        if ra > 0 and rb == -1:
            out.add(ra)
        elif rb > 0 and ra == -1:
            out.add(rb)
    return out


def _entry_or_hallway(lab, rid, ext_doors):
    """玄關必須有門直通屋外，否則改判走道（使用者裁決 2026-08-01）。

    Entry 與 Hallway 都是「沒有東西的空房間」，裁切圖上長得一模一樣，DINOv2
    結構上分不開——own_eval 實測 GT 4 間走道被判成 Entry 3、Bedroom 1，
    Hallway 的 P/R 掛零。分水嶺不在外觀而在通行關係：玄關走得出去，走道不行。

    單向規則：有大門不足以證明是玄關（客廳也可能直接對外），故只降級不升級。
    `ext_doors` 為 None（無門位/屋外資訊）時不表態，維持原判。"""
    if lab != "Entry" or ext_doors is None:
        return lab
    return lab if rid in ext_doors else "Hallway"


def classify_rooms_dino(det, labels, rooms, probs, outside=None):
    """辨識式房型——**去 CubiCasa 版本**（層 1 換成 DINOv2 裁切分類）。

    證據層：
      層 1  DINOv2 房間裁切分類機率
      層 4  符號幾何＋模板＋樓梯踏板（_apply_evidence）
      層 5  OCR 圖面文字（_apply_evidence）
    2026-07-30 CubiCasa 整批移除前，此函式與 classify_rooms_cc 並存；
    後者的層 2（相對多數票）與層 3（圖示絕對面積 cm²）隨其一併消失——
    兩者的資料來源都是 CubiCasa 模型輸出的通道。

    `open_living` 原以 CubiCasa 的 living/kitchen 票判定，改用 DINOv2 機率同義：
    客廳機率夠高且遠勝廚房 → 客餐廚一體，廚房系證據不加分。"""
    cm = det["cm"]
    ext_doors = rooms_with_exterior_door(det, labels, outside)
    for r, pr in zip(rooms, probs):
        r["area_m2"] = round(r["area_px"] * cm * cm / 1e4, 2)
        score = {lab: 0.0 for lab in
                 tuple(CC_ROOM_LABEL.values()) + EXTRA_LABELS}
        for lab, p in (pr or {}).items():
            if lab in score:
                score[lab] += p * DINO_W
        # 開放式客餐廚防呆。沿用 CubiCasa 路徑的「living 票夠強且勝過 kitchen」
        # 語意，但係數由 2.0× 放寬為單純比大小——DINOv2 的機率是尖銳分布，
        # floor64 的客廳 living 0.56 / kitchen 0.41 過不了 2× 門檻，廚房符號
        # 便繼續加分把它推成 kitchen，再經限額鏈砍掉真正的廚房。
        # `>= 0.15` 的下限保留：模型對該房完全沒有 living 概念時（floor73 的
        # 真廚房 living 0.00）不該套用此防呆。
        open_living = (score["LivingRoom"] >= 0.15
                       and score["LivingRoom"] > score["Kitchen"])
        _apply_evidence(det, labels, r, score, open_living)
        lab, val = max(score.items(), key=lambda kv: kv[1])
        r["label"] = lab if val >= 0.15 else "room"
        r["label"] = _entry_or_hallway(r["label"], r["id"], ext_doors)
        r["label_zh"] = ROOM_ZH_EX[r["label"]]
        r["cc_share"] = {k: round(v, 3) for k, v in score.items() if v >= 0.02}
        r["icons_cm2"] = {}                    # 契約鍵保留（來源已移除）
        r["_score"] = score
    _enforce_singletons(rooms)
    for r in rooms:
        del r["_score"]


UNIQUE_LABELS = ("LivingRoom", "Kitchen")      # user spec：全戶各最多一間


def _enforce_singletons(rooms):
    """住宅常識約束（user spec）：living/kitchen 全戶各限一間。
    同類多間只保留**該類分數最高**者，其餘降級為自己的次高分房型。
    接著：有廚無廳＝那間「廚房」多半是客餐廚一體，改叫客廳優先；
    圖面文字明寫 KITCHEN（作者親口說的答案）則豁免不改。
    relabel_from 記錄原判供 JSON 追溯。

    **2026-07-29 實測：兩種「改良」皆為淨負面，勿再嘗試**（own_eval 72 房）。
    起因是 floor64 的真實缺陷——DINOv2 給小廚房 kitchen 1.00、給大客廳
    kitchen 0.41（被廚房符號推上去），照面積挑會砍掉模型有把握的那間：

    | 保留者 / 降級可取的類 | CubiCasa 路徑 | DINOv2 路徑 |
    | 面積最大 / 排除全部限額類（現行） | 57/72 | **63/72** |
    | 分數最高 / 排除全部限額類 | 58/72 | 60/72 |
    | 分數最高 / 只排除已被佔走者 | 59/72 | 62/72 |

    兩者都修好了 floor64，卻在 floor69/70 賠更多：那兩張的真客廳被 DINOv2
    判成 kitchen（living 僅 0.06~0.08，開放式客餐廚），**現行規則靠「留最大
    的那間 → 下方有廚無廳改叫客廳」這條鏈歪打正著救回來**，改了就斷。
    要真正解決得從 `open_living` 防呆下手（它用 `score["LivingRoom"]>=0.15`
    判定，模型把開放空間判成廚房時根本不觸發），而非動限額規則。"""
    for lab in UNIQUE_LABELS:
        cand = [r for r in rooms if r["label"] == lab]
        for r in sorted(cand, key=lambda c: c["area_m2"], reverse=True)[1:]:
            alt = {k: v for k, v in r["_score"].items()
                   if k not in UNIQUE_LABELS}
            alt_lab, alt_val = max(alt.items(), key=lambda kv: kv[1])
            r["relabel_from"] = lab
            r["label"] = alt_lab if alt_val >= 0.15 else "room"
            r["label_zh"] = ROOM_ZH_EX[r["label"]]
    if not any(r["label"] == "LivingRoom" for r in rooms):
        for r in rooms:                        # 限額後 Kitchen 至多一間
            # 門檻：模型對該房完全沒有 LivingRoom 概念時（floor73 的真廚房
            # 0.00），它就只是一間獨立廚房，不是客餐廚一體，別改名
            if r["label"] == "Kitchen" \
                    and r["_score"].get("LivingRoom", 0.0) >= 0.05 \
                    and "Kitchen" not in (r.get("ocr_text") or {}):
                r["relabel_from"] = "Kitchen"
                r["label"] = "LivingRoom"
                r["label_zh"] = ROOM_ZH_EX["LivingRoom"]


# ─────────────────────────── 房間方塊 ───────────────────────────
def _merge_nondoor_bridges(labels, rooms, bridges, det):
    """走道攔腰切修正（floor04 實案：走道被 85cm 的橋切成兩個玄關）。
    牆縫封口把 40~260cm 開口全封，走道會被「左右牆端點隔走道相對」的
    橋切段——而 85cm 恰為單門尺寸，尺寸無法區分真門與走道橫斷。
    鑑別特徵：真門的房間遠寬於門洞（floor04 浴廁 1.32×、客廳 4.6×）；
    走道橫斷的橋兩側空間沿橋軸寬度 ≈ 橋長（實測 1.0×，開口吃滿全寬）。
    合併條件（全部成立）：橋長 40~160cm（>160 為雙開門或缺牆補償——
    floor04 廚房左牆未偵測、215cm 長橋在補牆，合併會讓廚房吃掉走道）、
    橋位無門弧證據、兩側各為一間房且沿橋軸 bbox 寬皆 ≤1.15×橋長。
    labels 就地改，回傳 (新 rooms, 未合併的 bridges)——合併掉的橋已
    失效，不該再畫進疊圖，恰為門尺寸者也不該再產生假門位。"""
    cm, T = det["cm"], det["T"]
    doors = det.get("doors") or ()
    by_id = {r["id"]: r for r in rooms}
    h, w = labels.shape
    merged = False
    kept = []
    for horiz, g0, g1, b0, b1 in bridges:
        gap = g1 - g0
        if not 40.0 <= gap * cm <= 160.0:
            kept.append((horiz, g0, g1, b0, b1))
            continue                             # 雙開門/缺牆補償 → 照舊隔房
        mx, my = ((g0 + g1) / 2.0, (b0 + b1) / 2.0) if horiz \
            else ((b0 + b1) / 2.0, (g0 + g1) / 2.0)
        # 門弧證據：沿橋軸 ±0.3 橋長、垂直向 ±1.2 橋長（門扇迴轉範圍）
        def _arc_at_bridge(d):
            ax, ay = float(d[0]), float(d[1])
            u, v = (ax, ay) if horiz else (ay, ax)
            band_lo, band_hi = (b0, b1)
            return (g0 - 0.3 * gap <= u <= g1 + 0.3 * gap
                    and band_lo - 1.2 * gap <= v <= band_hi + 1.2 * gap)
        if any(_arc_at_bridge(d) for d in doors):
            kept.append((horiz, g0, g1, b0, b1))
            continue                             # 有門弧 → 是門
        # 門弧清單空≠無門（floor13 實案：門偵測整圖 0、真門只剩墨水
        # 證據，浴室因此被走道碎片誤併）——墨水密度否決補上這個盲區。
        # thin 缺席時 _bridge_has_door_ink 回 True 是門位語境的「不濾
        # 照舊」；合併語境相反——無細線層＝無證據，不得憑空否決
        if det.get("thin") is not None \
                and _bridge_has_door_ink(det, horiz, g0, g1, b0, b1):
            kept.append((horiz, g0, g1, b0, b1))
            continue                             # 有門扇墨水 → 是門
        # 橋兩側取樣（跳過封口線附近的牆帶，往外找到第一個房間像素）
        side = [0, 0]
        for k, sign in ((0, -1), (1, 1)):
            for off in range(int(T), int(6 * T) + 1):
                iy = int(round((b0 if sign < 0 else b1) + sign * off)) if horiz \
                    else int(round(my))
                ix = int(round(mx)) if horiz \
                    else int(round((b0 if sign < 0 else b1) + sign * off))
                if not (0 <= iy < h and 0 <= ix < w):
                    break
                if labels[iy, ix] > 0:
                    side[k] = labels[iy, ix]
                    break
        a, b = side
        if not (a > 0 and b > 0 and a != b):
            kept.append((horiz, g0, g1, b0, b1))
            continue
        ra, rb = by_id.get(a), by_id.get(b)
        if ra is None or rb is None:
            kept.append((horiz, g0, g1, b0, b1))
            continue
        ext = (lambda r: r["bbox"][2] - r["bbox"][0]) if horiz \
            else (lambda r: r["bbox"][3] - r["bbox"][1])
        if ext(ra) > 1.15 * gap or ext(rb) > 1.15 * gap:
            kept.append((horiz, g0, g1, b0, b1))
            continue                             # 有一側遠寬於開口 → 是真門
        labels[labels == b] = a                  # 後續橋取樣自動吃到合併結果
        y0, y1 = (int(b0), int(b1) + 1) if horiz else (int(g0), int(g1) + 1)
        x0, x1 = (int(g0), int(g1) + 1) if horiz else (int(b0), int(b1) + 1)
        band = labels[max(0, y0):y1, max(0, x0):x1]
        band[band == 0] = a                      # 封口帶填回房間，疊圖不留白縫
        ra["bbox"] = (min(ra["bbox"][0], rb["bbox"][0]),
                      min(ra["bbox"][1], rb["bbox"][1]),
                      max(ra["bbox"][2], rb["bbox"][2]),
                      max(ra["bbox"][3], rb["bbox"][3]))
        del by_id[b]
        merged = True
    if not merged:
        return rooms, bridges
    out = []
    for r in rooms:                              # 依合併後 labels 重算統計
        m = labels == r["id"]
        n = int(np.count_nonzero(m))
        if not n:
            continue
        ys, xs = np.nonzero(m)
        w_, h_ = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        r.update(area_px=n,
                 bbox=(int(xs.min()), int(ys.min()),
                       int(xs.max() + 1), int(ys.max() + 1)),
                 cx=float(xs.mean()), cy=float(ys.mean()),
                 aspect=round(max(w_, h_) / max(1.0, min(w_, h_)), 2))
        out.append(r)
    return out, kept





def _carve_stairs(labels, rooms, boxes, T, cm=1.0):
    """樓梯足跡切分：把踏板串外框從所屬房間切出成獨立房（labels 就地改，
    回傳新 rooms）。開放區嵌樓梯（floor08/12/31 實案）沒有牆可封，
    純封口規則切不出——這是功能區切分的第一塊，切線一律軸對齊
    （使用者域約束：房間只有直角矩形系）。

    規則：同座梯段先併——相鄰（間隙 <2T，迴轉梯）或對齊隔平台
    （間隙 <140cm，floor40 上下段梯隔 55cm 平台）；足跡 ≥(2T)² 且
    ≥70% 落在同一房、≤50% 該房面積、且未佔滿宿主同向尺寸 85%
    （樓梯間本有牆自成一房，floor40 曾被再切一刀）才動刀。"""
    if not boxes:
        return rooms
    boxes = [tuple(float(v) for v in b) for b in boxes]
    land = max(2.0 * T, 140.0 / max(cm, 1e-6))   # 平台合併距離（px）
    merged = True                                # 同座梯段合併
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ax0, ay0, ax1, ay1 = boxes[i]
                bx0, by0, bx1, by1 = boxes[j]
                near = (ax0 - 2 * T < bx1 and ax1 + 2 * T > bx0
                        and ay0 - 2 * T < by1 and ay1 + 2 * T > by0)
                ov_x = min(ax1, bx1) - max(ax0, bx0)     # 對齊隔平台：
                ov_y = min(ay1, by1) - max(ay0, by0)     # 一軸重疊 ≥60%、
                wx = min(ax1 - ax0, bx1 - bx0)           # 另一軸間隙 <land
                wy = min(ay1 - ay0, by1 - by0)
                aligned = ((ov_x >= 0.6 * wx and -land < ov_y <= 0)
                           or (ov_y >= 0.6 * wy and -land < ov_x <= 0))
                if near or aligned:
                    boxes[i] = (min(ax0, bx0), min(ay0, by0),
                                max(ax1, bx1), max(ay1, by1))
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    h, w = labels.shape
    out = list(rooms)
    by_id = {r["id"]: r for r in out}
    nid = max((r["id"] for r in out), default=0)
    for x0, y0, x1, y1 in boxes:
        ix0, iy0 = max(0, int(x0)), max(0, int(y0))
        ix1, iy1 = min(w, int(x1)), min(h, int(y1))
        if ix1 - ix0 < 2 or iy1 - iy0 < 2:
            continue
        win = labels[iy0:iy1, ix0:ix1]
        area_box = (ix1 - ix0) * (iy1 - iy0)
        if area_box < (2 * T) ** 2:
            continue                             # 過小＝雜訊串
        ids, counts = np.unique(win[win > 0], return_counts=True)
        if not len(ids):
            continue
        host_id = int(ids[np.argmax(counts)])
        host_n = int(counts.max())
        host = by_id.get(host_id)
        if host is None or host_n < 0.7 * area_box:
            continue                             # 足跡沒安坐在單一房裡
        if host_n > 0.25 * host["area_px"]:
            continue                             # 樓梯間本有牆自成一房：宿主
                                                 # 須 ≥4× 足跡（真大開放區）才切
        hx0, hy0, hx1, hy1 = host["bbox"]        # 佔滿宿主同向尺寸＝樓梯間
        if (ix1 - ix0) >= 0.85 * (hx1 - hx0) or (iy1 - iy0) >= 0.85 * (hy1 - hy0):
            continue
        nid += 1
        region = win == host_id
        win[region] = nid
        ys, xs = np.nonzero(labels == nid)
        stair = {"id": nid, "area_px": int(len(xs)),
                 "bbox": (int(xs.min()), int(ys.min()),
                          int(xs.max() + 1), int(ys.max() + 1)),
                 "cx": float(xs.mean()), "cy": float(ys.mean()),
                 "aspect": round(
                     max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
                     / max(1.0, min(xs.max() - xs.min() + 1,
                                    ys.max() - ys.min() + 1)), 2),
                 "touch_env": host.get("touch_env", False)}
        out.append(stair)
        by_id[nid] = stair
        m = labels == host_id                    # 主房統計同步扣除
        ys, xs = np.nonzero(m)
        if not len(xs):
            out.remove(host)
            del by_id[host_id]
            continue
        w_, h_ = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        host.update(area_px=int(m.sum()),
                    bbox=(int(xs.min()), int(ys.min()),
                          int(xs.max() + 1), int(ys.max() + 1)),
                    cx=float(xs.mean()), cy=float(ys.mean()),
                    aspect=round(max(w_, h_) / max(1.0, min(w_, h_)), 2))
    return out


# 符號錨點的兩系詞彙：只做「廚 vs 客」這一種誤併（v2.23 殘餘 36 件中
# 14 件的型態），臥浴不參與——bed+sofa 同室是套房、oval 到處有，寧漏勿誤。
# dtable→廚房系沿 extract_asset_lib 的使用者裁決；chair（單人沙發椅）
# 常出現在臥室，單獨不構成客廳證據，故不入表。
_KITCHEN_SYMS = ("stove", "kstove", "ksink", "sinkicon", "dtable",
                 "trashcan")   # 美式素材輪新增（弱證據，不入 STRONG）
_LIVING_SYMS = ("sofa",)


_KITCHEN_STRONG = ("stove", "kstove", "ksink")   # 弱證據（sinkicon/dtable）
                                                 # 不得單獨撐起單側切分


def _symbol_anchors(det, labels, rooms):
    """無文字開放區的錨點補位（格式同 detect_room_text）。兩條路徑：
    1) 雙系：廚房系＋客廳系符號群同房、質心相距 ≥200cm → 各出一錨點；
    2) 單側廚房（實測主力）：沙發模板在多數畫風上比對不到（floor31/
       54/52 客廳側符號全滅），改以「大房間裡緊湊且偏心的廚房符號群」
       單側觸發——對側錨點＝離群較遠那半房間質量的質心。
       防呆四道：強廚房符號 ≥1、符號群跨距 ≤350cm（散開＝假陽性）、
       房 ≥15m²（小房不會是開放廚客）、群質心偏離房質心 ≥200cm
       （居中＝這房就是廚房，不切）。"""
    cm = det.get("cm", 1.0)
    h, w = labels.shape
    out = []
    for r in rooms:
        kit, kit_strong, liv = [], 0, []
        for kind, sx, sy in det.get("symbols", ()):
            iy, ix = int(round(sy)), int(round(sx))
            if not (0 <= iy < h and 0 <= ix < w and labels[iy, ix] == r["id"]):
                continue
            if kind in _KITCHEN_SYMS:
                kit.append((float(sx), float(sy)))
                kit_strong += kind in _KITCHEN_STRONG
            elif kind in _LIVING_SYMS:
                liv.append((float(sx), float(sy)))
        if not kit:
            continue
        kx = sum(p[0] for p in kit) / len(kit)
        ky = sum(p[1] for p in kit) / len(kit)
        if liv:                                  # 路徑 1：雙系
            lx = sum(p[0] for p in liv) / len(liv)
            ly = sum(p[1] for p in liv) / len(liv)
            if ((kx - lx) ** 2 + (ky - ly) ** 2) ** 0.5 * cm >= 200.0:
                out.append(("Kitchen", kx, ky, f"sym:{len(kit)}"))
                out.append(("LivingRoom", lx, ly, f"sym:{len(liv)}"))
            continue
        # 路徑 2：單側廚房
        if not kit_strong:
            continue
        span = max(max(p[0] for p in kit) - min(p[0] for p in kit),
                   max(p[1] for p in kit) - min(p[1] for p in kit))
        if span * cm > 350.0:
            if det.get("domain") != "color":
                continue                         # 灰階維持一票否決（畫風
                                                 # 分流：color 機制不進灰階）
            # 跨距超限不整組否決（floor47/52 實案：一顆離群假陽性毀
            # 全局）——改取最緊密子群：以每顆為中心、半徑 175cm 內
            # 成員最多者；子群須 ≥2 顆且含強符號才續行
            r175 = 175.0 / max(cm, 1e-6)
            best = []
            for cx0, cy0 in kit:
                sub = [p for p in kit
                       if ((p[0] - cx0) ** 2 + (p[1] - cy0) ** 2) ** 0.5
                       <= r175]
                if len(sub) > len(best):
                    best = sub
            strong_in = sum(
                1 for kind, sx, sy in det.get("symbols", ())
                if kind in _KITCHEN_STRONG and (float(sx), float(sy)) in
                {(p[0], p[1]) for p in best})
            if len(best) < 2 or not strong_in:
                continue                         # 子群須 ≥2 顆＋強符號：
                                                 # 兩顆孤立遠距強符號分不出
                                                 # 誰真誰假，維持不觸發
            kit = best
            kx = sum(p[0] for p in kit) / len(kit)
            ky = sum(p[1] for p in kit) / len(kit)
        if r["area_px"] * cm * cm < 150000.0:
            continue                             # <15m² 不會是開放廚客
        if ((kx - r["cx"]) ** 2 + (ky - r["cy"]) ** 2) ** 0.5 * cm < 200.0:
            continue                             # 居中＝這房就是廚房
        ys, xs = np.nonzero(labels == r["id"])
        d2 = (xs - kx) ** 2 + (ys - ky) ** 2
        far = d2 > np.median(d2)                 # 離廚房群較遠那半的質心
        out.append(("Kitchen", kx, ky, f"sym:{len(kit)}"))
        out.append(("LivingRoom", float(xs[far].mean()),
                    float(ys[far].mean()), "sym:far-half"))
    return out


_BATH_SYMS = ("oval", "tubrect", "wc", "tub", "basin", "shower")


def _merge_bath_nooks(labels, rooms, det, T, seed_ids=None, veto_ids=None):
    """浴室隔屏碎格合併（labels 就地改，回傳新 rooms）。floor38/44
    實案：浴缸屏/馬桶半牆＋封口盒把一間浴室切成 3~4 格，每格對 GT
    整間浴室 IoU 皆 <0.5，或碎格死在面積終篩。
    規則：面積 <8m² 且含浴具符號的碎房，彼此間距 ≤2T 者併成一間。
    大房不參與（浴具誤偵測不至於把臥室吸進浴室）。須在面積終篩前
    執行——合併後的浴室才活得過門檻。
    2026-08-01 二落：首落時浴具模板未啟用、開發集零觸發而還原；
    tub/wc 依品質掃描啟用後證據到位，機制重新上線。"""
    cm = det.get("cm", 1.0)
    h, w = labels.shape
    cand, extras = [], []
    for r in rooms:
        if r["area_px"] * cm * cm >= 80000.0:    # ≥8m² 非浴室碎格
            continue
        if seed_ids is not None:
            # DINO 種子路（彩圖限定）：symbols=[] 時由呼叫端以 DINO
            # 判 Bath 的碎房當種子、判 Kitchen 者當反證
            has_fix = r["id"] in seed_ids
            has_kitchen = bool(veto_ids) and r["id"] in veto_ids
        else:
            has_fix = has_kitchen = False
            for kind, sx, sy in det.get("symbols", ()):
                iy, ix = int(round(sy)), int(round(sx))
                if not (0 <= iy < h and 0 <= ix < w
                        and labels[iy, ix] == r["id"]):
                    continue
                has_fix = has_fix or kind in _BATH_SYMS
                has_kitchen = has_kitchen or kind in _KITCHEN_SYMS
        # 廚房系符號是強反證（floor39 實案：wc 模板在廚房打假陽性，
        # 廚房被當浴具碎格與樓下真浴室誤併）——含爐台/水槽者不候選
        if has_kitchen:
            continue
        if has_fix:
            cand.append(r)
        elif r["area_px"] * cm * cm < 40000.0:
            extras.append(r)                     # 無浴具小格＝可吸收候補
    if len(cand) < 2:
        return rooms
    k = 4 * int(T) + 3                           # 膨脹半徑 2T+1＝隔屏牆厚度帶
    ker = np.ones((k, k), np.uint8)
    dil = {r["id"]: cv2.dilate((labels == r["id"]).astype(np.uint8), ker) > 0
           for r in cand}
    parent = {r["id"]: r["id"] for r in cand}    # 鄰接群組（union-find 簡版）

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            a, b = cand[i]["id"], cand[j]["id"]
            if (dil[a] & (labels == b)).any():
                parent[_find(a)] = _find(b)
    groups = {}
    for r in cand:
        groups.setdefault(_find(r["id"]), []).append(r)
    # 吸收制（floor38/44 實案）：浴缸格/梳妝格常無配對到的浴具符號，
    # 但被隔屏切出的碎格群不完整就蓋不滿 GT 浴室。無浴具的 <4m² 小格
    # 若鄰接「≥2 個種子」的群則吸收——單種子不吸，避免真浴室把隔壁
    # 儲藏室吞掉
    for root, members in list(groups.items()):
        if len(members) < 2:
            continue
        for e in extras:
            if e in members:
                continue
            if any((dil[s["id"]] & (labels == e["id"])).any()
                   for s in members if s["id"] in dil):
                members.append(e)
    out = list(rooms)
    for _root, members in groups.items():
        if len(members) < 2:
            continue
        keep = max(members, key=lambda r: r["area_px"])
        for r in members:
            if r is keep:
                continue
            labels[labels == r["id"]] = keep["id"]
            out.remove(r)
        upd = _room_stats(labels, keep["id"], keep.get("touch_env", False))
        keep.update(upd)
    return out


def _room_stats(labels, rid, touch_env):
    """依 labels 重算單一房間統計；該 id 已無像素時回 None。"""
    ys, xs = np.nonzero(labels == rid)
    if not len(xs):
        return None
    w_, h_ = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    return {"id": rid, "area_px": int(len(xs)),
            "bbox": (int(xs.min()), int(ys.min()),
                     int(xs.max() + 1), int(ys.max() + 1)),
            "cx": float(xs.mean()), "cy": float(ys.mean()),
            "aspect": round(max(w_, h_) / max(1.0, min(w_, h_)), 2),
            "touch_env": touch_env}


def _split_by_text_anchors(labels, rooms, texts, T, cm, amin,
                           min_part_ratio=None, verify=None):
    """OCR 房名錨點功能區切分（labels 就地改，回傳新 rooms）。
    E1 誤併型態：廚/餐/客一體、玄關-走道虛線分界——GT 沿無牆邊界分區，
    封口規則無牆可封。圖面文字是作者親口說的答案：一房含 2+ 個房名
    錨點＝作者標了 2+ 個功能區，沿主軸在錨點間隙中點下軸對齊直刀
    （使用者域約束：房間只有直角矩形系，切線只有水平/垂直）。

    防呆：同標籤錨點相距 <200cm 視為同一區（折行文字）；任一切塊
    低於 amin 則整房放棄不切；錨點取字框中心、落在該房 labels 上
    才算數。"""
    if not texts:
        return rooms
    h, w = labels.shape
    out = list(rooms)
    nid = max((r["id"] for r in out), default=0)
    xs_grid = np.arange(w)[None, :]
    ys_grid = np.arange(h)[:, None]

    def _rectness(m):
        ys, xs = np.nonzero(m)
        if not len(xs):
            return 0.0
        return len(xs) / float((xs.max() - xs.min() + 1)
                               * (ys.max() - ys.min() + 1))

    def _cut(region, anchors):
        if len(anchors) == 1:
            return [region]
        sx = max(a[1] for a in anchors) - min(a[1] for a in anchors)
        sy = max(a[2] for a in anchors) - min(a[2] for a in anchors)
        key = 1 if sx >= sy else 2               # 主軸＝錨點散得開的那軸
        vals = sorted(anchors, key=lambda a: a[key])
        gi = max(range(len(vals) - 1),
                 key=lambda i: vals[i + 1][key] - vals[i][key])
        lo, hi = vals[gi][key], vals[gi + 1][key]
        grid = xs_grid if key == 1 else ys_grid
        # 切線位置（使用者裁決 2026-08-01）：取決於「切給誰較方正」——
        # 候選＝兩錨點間的輪廓階梯（剖面寬跳變 >T 處），逐一評兩側
        # 方正度（面積/外接矩形），最高者勝；無階梯（純矩形）退回中點
        prof = region.sum(axis=0 if key == 1 else 1)
        a0, b0 = int(lo) + 2, int(hi) - 1
        cands = [float(c) for c in range(max(a0, 1), b0)
                 if abs(int(prof[c]) - int(prof[c - 1])) > T]
        cands.append((lo + hi) / 2.0)
        best_c, best_s = cands[-1], -1.0
        for c in cands:
            left, right = region & (grid < c), region & (grid >= c)
            if not left.any() or not right.any():
                continue
            s = _rectness(left) + _rectness(right)
            if s > best_s:
                best_s, best_c = s, c
        return (_cut(region & (grid < best_c), vals[:gi + 1])
                + _cut(region & (grid >= best_c), vals[gi + 1:]))

    for room in rooms:
        rid = room["id"]
        anch = []
        for t in texts:
            lab, cx, cy = t[0], float(t[1]), float(t[2])
            ix, iy = int(round(cx)), int(round(cy))
            if 0 <= iy < h and 0 <= ix < w and labels[iy, ix] == rid:
                anch.append([lab, cx, cy])
        merged = []                              # 折行文字＝同區
        for lab, cx, cy in anch:
            hit = next((m for m in merged
                        if m[0] == lab and abs(m[1] - cx) * cm < 200
                        and abs(m[2] - cy) * cm < 200), None)
            if hit:
                hit[1] = (hit[1] + cx) / 2.0
                hit[2] = (hit[2] + cy) / 2.0
            else:
                merged.append([lab, cx, cy])
        if len(merged) < 2:
            continue
        parts = _cut(labels == rid, merged)
        if any(int(p.sum()) < amin for p in parts):
            continue                             # 有碎屑 → 整房放棄不切
        if min_part_ratio and len(parts) == 2:
            a_, b_ = int(parts[0].sum()), int(parts[1].sum())
            if max(a_, b_) < min_part_ratio * min(a_, b_) \
                    and not (verify and verify(parts, merged)):
                continue                         # 兩半約等大＝廚餐一體
                                                 # （子區歸主房慣例），不切；
                                                 # verify 回呼（DINO 兩半驗證）
                                                 # 判真可放行（floor47/52 型
                                                 # 開放 LDK 的廚客真切分）
        for p in parts[1:]:
            nid += 1
            labels[p] = nid
        te = room.get("touch_env", False)
        out.remove(room)
        for r_ in filter(None, (_room_stats(labels, rid, te),
                                *(_room_stats(labels, i, te)
                                  for i in range(nid - len(parts) + 2,
                                                 nid + 1)))):
            out.append(r_)
    return out


def _bridge_has_door_ink(det, horiz, g0, g1, b0, b1):
    """門位證據——委派 fp_c.door_ink_evidence（門偵測重建後單一事實
    來源，DXF 批次 json 與 room zones 用同一把尺）。"""
    return fp_c.door_ink_evidence(det.get("thin"), det.get("text_boxes", ()),
                                  horiz, g0, g1, b0, b1)


def _bridge_zone(horiz, g0, g1, b0, b1):
    """牆端連線 → 門位框——委派 fp_c.door_zone_quad（同上）。"""
    return fp_c.door_zone_quad(horiz, g0, g1, b0, b1)


def _harvest_balcony_pockets(det, labels, rooms, outside):
    """殼外陽台口袋收割（color 集 Balcony 漏切主因，dev 實測 18 間）。

    陽台在牆殼之外、由圍欄細線圈住；牆偵測不含圍欄 → 主分割灌水判定
    室外整片剪掉。把圍欄線補進屏障重灌一次水，「主分割室外、圍欄屏障
    下灌不到」的封閉口袋＝陽台候選，以新房間附加。守門：貼殼（bbox
    距建物外圈 ≤2T）、面積 ≥max((2T)², 0.2m²) 且 ≤25% 建物 bbox。
    既有房間 labels 一概不動——純加法，命名交給下游 DINO。"""
    fence = det.get("fence") if det.get("fence") is not None else det.get("thin")
    if fence is None or labels is None or outside is None:
        return rooms
    T, cm = det["T"], det["cm"]
    img_h, img_w = labels.shape
    rects, wins = det["rects"], det["wins"]
    barrier = np.zeros((img_h, img_w), np.uint8)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(barrier, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for _o, x0, y0, x1, y1 in wins:
        cv2.rectangle(barrier, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for horiz, g0, g1, b0, b1 in fp_c._wall_gaps(rects, wins, T, cm,
                                                 40.0, 260.0):
        if horiz:
            cv2.rectangle(barrier, (int(g0), int(b0)), (int(g1), int(b1)), 255, -1)
        else:
            cv2.rectangle(barrier, (int(b0), int(g0)), (int(b1), int(g1)), 255, -1)
    walls_only = barrier.copy()                  # 牆＋窗＋封口（不含 fence）
    barrier = cv2.bitwise_or(
        barrier, cv2.dilate(((fence > 0) * 255).astype(np.uint8),
                            np.ones((5, 5), np.uint8)))
    ff = np.pad(barrier, 1).copy()
    cv2.floodFill(ff, None, (0, 0), 128)
    reach = ff[1:-1, 1:-1] == 128
    # 「未分配」而非「室外」：主分割大核閉運算會把露台整片吞成牆
    # （inside 但 labels=0，floor_17 頂部露台實案），outside 條件收不到。
    # 排除遮罩只用牆/封口——露台內部的植栽/磁磚紋理也在 fence 層，
    # 用含 fence 的 barrier 會把口袋自己蓋掉（fence 只負責擋 reach）
    pocket = ((labels == 0) & ~reach & (walls_only == 0)).astype(np.uint8)
    # 口袋內的圍欄線/曬衣桿會把同一座陽台切成多個連通塊（floor_10 實測
    # IoU 掉到 0.5 以下配不上）——閉運算把被細線分割的碎塊接回一體；
    # 不同陽台相距遠超過 T，不會被 1 個牆厚的核黏起來
    kp = 2 * max(2, int(round(0.5 * T))) + 1
    pocket = cv2.morphologyEx(pocket * 255, cv2.MORPH_CLOSE,
                              np.ones((kp, kp), np.uint8))
    pocket[reach | (labels > 0)] = 0             # 閉運算不得侵入室外通路/既有房
    pocket = (pocket > 0).astype(np.uint8)
    X0 = min(r[0] for r in rects); Y0 = min(r[1] for r in rects)
    X1 = max(r[2] for r in rects); Y1 = max(r[3] for r in rects)
    amin = max((2 * T) ** 2, int(2000.0 / max(cm * cm, 1e-6)))
    amax = 0.35 * (X1 - X0) * (Y1 - Y0)   # 圍欄環併入口袋後上修（0.30 會誤殺）
    # 低紮實度口袋頸縮分裂（floor_10 實案：陽台與殼緣窄條黏成 solidity
    # 0.08 的細長 L，IoU 只到 0.49）——erode 斷頸後窄條死於面積門檻，
    # 陽台本體以核心回膨脹活下來
    n0, lab0, st0, _c0 = cv2.connectedComponentsWithStats(pocket, 8)
    for i in range(1, n0):
        a0 = int(st0[i, cv2.CC_STAT_AREA])
        bb = st0[i, cv2.CC_STAT_WIDTH] * st0[i, cv2.CC_STAT_HEIGHT]
        if a0 < amin or a0 / max(1.0, float(bb)) >= 0.35:
            continue                             # 0.35~0.5 的鬆散口袋常仍
                                                 # 配得上（floor_13），只剝
                                                 # 極端細長者（floor_10 0.08）
        cc = (lab0 == i).astype(np.uint8)
        ke = np.ones((max(3, T // 2) | 1,) * 2, np.uint8)
        core = cv2.erode(cc, ke)
        grown = cv2.dilate(core, ke) & cc        # 核心回膨脹但不出原 CC
        if int(grown.sum()) < 0.4 * a0:
            continue                             # 核心保不住四成（環狀薄形
                                                 # 整顆蒸發，floor_13 陽台）
                                                 # → 整顆不動
        pocket[(cc > 0) & (grown == 0)] = 0      # 窄頸/細條剝除
    n, lab, st, cent = cv2.connectedComponentsWithStats(pocket, 8)
    nid = max((r["id"] for r in rooms), default=0)
    for i in range(1, n):
        a = int(st[i, cv2.CC_STAT_AREA])
        if not amin <= a <= amax:
            continue
        x, y, w, h = (int(st[i, cv2.CC_STAT_LEFT]), int(st[i, cv2.CC_STAT_TOP]),
                      int(st[i, cv2.CC_STAT_WIDTH]), int(st[i, cv2.CC_STAT_HEIGHT]))
        # 貼殼＝bbox 與外圈「環帶」相交：貼圈、跨圈（floor_17 頂部露台
        # 橫跨外圈上緣，舊的邊緣鄰近判定收不到）都算；完全在圈內深處
        # （室內縫隙）或懸空遠處（雜訊）都不算
        m = 2.0 * T
        overlaps = not (x > X1 + m or x + w < X0 - m
                        or y > Y1 + m or y + h < Y0 - m)
        deep_inside = (X0 + m < x and x + w < X1 - m
                       and Y0 + m < y and y + h < Y1 - m)
        if not overlaps or deep_inside:
            continue                             # 不貼殼＝浮空雜訊/室內縫
        nid += 1
        labels[lab == i] = nid
        rooms.append({"id": nid, "area_px": a,
                      "bbox": (x, y, x + w, y + h),
                      "cx": float(cent[i][0]), "cy": float(cent[i][1]),
                      "aspect": round(max(w, h) / max(1.0, min(w, h)), 2),
                      "touch_env": True, "pocket": True})
    return rooms


def _ww_suture_merge(det, labels, rooms, T, cm, p_min=0.70):
    """假帶縫合輪——白牆救援採用張的過切殘塊回併（floor_08 實案：
    救援白帶的假陽性把客廳切出 21k px 殘片，殘塊無符號無門被叫
    Hallway，主體 IoU 0.38 差線；縫回後 0.61 跨線）。

    寧漏勿誤，四道門全過才併：
    1. det["_ww_adopted"]——災難張限定，正常張零接觸；
    2. 相鄰面不是真暗牆（邊界帶與暗牆重疊 <0.3）——救援張的白帶/
       fence/封口切都是重跑期人工物（floor_08 實測殘塊多為 fence 切，
       邊界 dark 0.03/band 0.00），信任交給門 4，暗牆分隔的兩房不動；
    3. 一方是 Hallway/room（過切殘塊的典型歸宿）或兩方同名——
       兩個有正名的房不併；
    4. DINO 聯集重分類 top-1 == 主體房型且信心 ≥p_min——縫錯會被
       聯集的異質外觀壓信心。
    labels 就地改，回傳新 rooms。greedy 迭代至無可併（上限 4 併）。"""
    if not det.get("_ww_adopted") or len(rooms) < 2:
        return rooms
    h, w = labels.shape
    dark_m = np.zeros((h, w), np.uint8)
    for x0, y0, x1, y1 in det.get("rects") or []:
        cv2.rectangle(dark_m, (int(x0), int(y0)),
                      (int(x1) - 1, int(y1) - 1), 1, -1)
    ker = np.ones((2 * int(1.5 * T) + 1,) * 2, np.uint8)
    out = list(rooms)
    residue_lab = (None, "", "room", "Hallway")
    for _ in range(4):
        cand = None                              # (p, 主體, 殘塊, 主體名)
        dil = {r["id"]: cv2.dilate((labels == r["id"]).astype(np.uint8),
                                   ker) for r in out}
        for i, ra in enumerate(out):
            for rb in out[i + 1:]:
                la, lb = ra.get("label"), rb.get("label")
                a_res = la in residue_lab
                b_res = lb in residue_lab
                if not (a_res or b_res or la == lb):
                    continue                     # 門 3：兩正名不併
                # 主體＝非殘塊方（同名/雙殘取大者）
                if a_res == b_res:
                    host, res = (ra, rb) if ra["area_px"] >= rb["area_px"] \
                        else (rb, ra)
                else:
                    host, res = (rb, ra) if a_res else (ra, rb)
                if host.get("label") in residue_lab:
                    continue                     # 雙殘塊無主體房型可驗
                bound = (dil[ra["id"]] & dil[rb["id"]]) > 0
                nb = int(bound.sum())
                if not nb:
                    continue                     # 不相鄰
                f_dark = int(dark_m[bound].sum()) / nb
                ww_dbg = os.environ.get("WW_DEBUG") == "1"
                if f_dark >= 0.3:
                    if ww_dbg:
                        print(f"WW_DEBUG 縫合拒: {host['label']}"
                              f"({host['area_px']})×{res.get('label')}"
                              f"({res['area_px']}) 門2 "
                              f"dark {f_dark:.2f}")
                    continue                     # 門 2：真暗牆分隔
                tmp = np.zeros_like(labels)
                tmp[(labels == ra["id"]) | (labels == rb["id"])] = 1
                probs = room_classifier.classify(det.get("bgr"), tmp,
                                                 [{"id": 1}],
                                                 variant="color")
                pu = (probs[0] or {}) if probs else {}
                if not pu:
                    continue
                top = max(pu, key=pu.get)
                if top != host["label"] or pu[top] < p_min:
                    if ww_dbg:
                        print(f"WW_DEBUG 縫合拒: {host['label']}"
                              f"({host['area_px']})×{res.get('label')}"
                              f"({res['area_px']}) 門4 "
                              f"top {top} {pu[top]:.2f}")
                    continue                     # 門 4：聯集驗證
                if cand is None or pu[top] > cand[0]:
                    cand = (pu[top], host, res, top)
        if cand is None:
            break
        _p, host, res, top = cand
        labels[labels == res["id"]] = host["id"]
        keep = _room_stats(labels, host["id"], host.get("touch_env", False))
        keep["label"] = top
        keep["area_m2"] = round(keep["area_px"] * cm * cm / 1e4, 2)
        print(f"假帶縫合 : {res.get('label')}({res['area_px']}px) 併回 "
              f"{top}（聯集信心 {_p:.2f}）")
        out = [r for r in out if r["id"] not in (host["id"], res["id"])]
        out.append(keep)
    return out


def _dino_propose_splits(det, labels, rooms, T, cm, amin,
                         min_m2=250000.0, p_min=0.55):
    """DINO 提案式切分——無錨點大房的最後切分手段（floor47/52/13 灰、
    floor02/03 彩型開放 LDK）。彩圖無 OCR 也無符號證據、灰階符號召回
    被模板庫卡死，這些誤併沒有任何錨點可用。

    對面積 ≥25m² 的房：沿主軸輪廓階梯（剖面跳變 >T）＋fence 線密度峰
    （窗帶/圍欄在細線層是長直線——floor_04/18/19 型「陽台被鄰房吞」的
    分界帶）＋中點出候選刀，每刀切兩半交 DINO；兩半 top-1 為
    {Kitchen, LivingRoom} 對、或 {Balcony}×{Kitchen/LivingRoom/Bedroom}
    對，且雙方信心 ≥p_min 才收，取信心和最高的一刀。
    寧漏勿誤：驗證不過整房不動。labels 就地改，回傳新 rooms。"""
    h, w = labels.shape
    out = list(rooms)
    nid = max((r["id"] for r in out), default=0)
    variant = "color" if det.get("domain") == "color" else "gray"
    xs_grid = np.arange(w)[None, :]
    ys_grid = np.arange(h)[:, None]
    fence = det.get("fence") if det.get("fence") is not None else None
    rects_env = det.get("rects") or ()
    if rects_env:
        eX0 = min(r_[0] for r_ in rects_env); eY0 = min(r_[1] for r_ in rects_env)
        eX1 = max(r_[2] for r_ in rects_env); eY1 = max(r_[3] for r_ in rects_env)
    else:
        eX0 = eY0 = 0; eX1 = w; eY1 = h

    def _on_env(mask):
        """Balcony 半必須貼建物外圈（陽台在殼緣；室內磁磚被誤判
        Balcony 的假半不貼圈——floor_05 客廳誤切的守門）。"""
        ys, xs = np.nonzero(mask)
        if not len(xs):
            return False
        m = 2.5 * T
        return (xs.min() - eX0 <= m or eX1 - xs.max() <= m
                or ys.min() - eY0 <= m or eY1 - ys.max() <= m)
    pp_dbg = os.environ.get("WW_DEBUG") == "1"
    ww_adopted = bool(det.get("_ww_adopted"))
    # 災難張門檻下修（floor_07 實案）：救援採用張的複合 blob（臥+浴、
    # 臥+走道）計算面積僅 7~8.6m²——比例尺被門樣本稀少低估，10m²
    # big 線全擋、8m² 硬地板連場都進不了。災難張已無可失且有 DINO
    # 雙 0.7＋比例守門，硬地板降 5m²、big 線降 6m²；常規張兩門檻不動
    floor_m2 = 50000.0 if ww_adopted else 80000.0
    for room in rooms:
        area_m2 = room["area_px"] * cm * cm
        if area_m2 < floor_m2:                   # 硬地板：太小不提案
            if pp_dbg and area_m2 >= 40000.0:
                print(f"WW_DEBUG 提案拒: id {room['id']} "
                      f"{area_m2 / 1e4:.1f}m² < 硬地板")
            continue
        big = area_m2 >= (60000.0 if ww_adopted else min_m2)
        bx0, by0, bx1, by1 = room["bbox"]
        fill = room["area_px"] / max(1.0, float((bx1 - bx0) * (by1 - by0)))
        if pp_dbg:
            print(f"WW_DEBUG 提案評: id {room['id']} "
                  f"{area_m2 / 1e4:.1f}m² big {big} fill {fill:.2f}")
        # 門檻下修開放的 5~10m² 帶只吃證據刀（tint/fence/剖面跳變）：
        # 中點是唯一無證據亂刀，小房被對半誤切的主因（floor_08 左臥
        # 7.2m² 實案）；剖面跳變＝L 型幾何階梯，屬結構證據保留
        # （floor_07 臥+浴 blob 的浴界只有軸2 跳變刀看得見）；整房
        # DINO 信心在災難張是反向指標（floor_07 blob 整房 0.9+、
        # floor_08 乾淨臥反而 <0.8），不可用
        evidence_only = ww_adopted and area_m2 < 100000.0
        # 救援採用張的複合房常 12~20m²（floor_08 臥+走+客 17.6m²），
        # 25m² 門檻會全擋——災難張降 10m²
        region = labels == room["id"]
        x0, y0, x1, y1 = room["bbox"]
        # fence 刀：孤立高密度線才可信——窗帶/圍欄是 1~2 條長直線，
        # 磁磚格是幾十條（floor_05 客廳被磁磚紋誤切的教訓）。同軸
        # 高密度「線列（連續段）」超過 3 條＝紋理，整軸 fence 刀作廢
        fence_knives = {1: [], 2: []}
        if fence is not None:
            fmask = (fence > 0) & region
            for key in (1, 2):
                prof = region.sum(axis=0 if key == 1 else 1)
                fprof = fmask.sum(axis=0 if key == 1 else 1)
                lo, hi = (x0, x1) if key == 1 else (y0, y1)
                hits = [c for c in range(int(lo) + 2 * T, int(hi) - 2 * T)
                        if prof[c] > 0 and fprof[c] >= 0.7 * prof[c]]
                runs = []
                for c in hits:
                    if runs and c - runs[-1][-1] <= 2:
                        runs[-1].append(c)
                    else:
                        runs.append([c])
                if 1 <= len(runs) <= 3:
                    fence_knives[key] = [float(r_[len(r_) // 2])
                                         for r_ in runs]
        # 色染轉換刀（floor_08 實案：黃走道/白客廳、浴/廚無牆有色界）
        # ——房內逐列取主色染類（LAB ab 粗分桶），主類切換處出候選刀
        tint_knives = {1: [], 2: []}
        bgr_t = det.get("bgr")
        if bgr_t is not None and big and variant == "color":
            sc_t = labels.shape[1] / float(bgr_t.shape[1])
            lab_t = cv2.cvtColor(cv2.pyrMeanShiftFiltering(bgr_t, 5, 16),
                                 cv2.COLOR_BGR2LAB)
            at = lab_t[:, :, 1].astype(np.int16) - 128
            bt = lab_t[:, :, 2].astype(np.int16) - 128
            cls1 = np.zeros(lab_t.shape[:2], np.int8)   # 0=中性
            strong = (np.abs(at) + np.abs(bt)) > 14
            hue = np.arctan2(bt.astype(np.float32),
                             at.astype(np.float32))       # -π~π
            hue_bin = ((hue + np.pi) / (2 * np.pi) * 8).astype(np.int8) % 8
            cls1[strong] = hue_bin[strong] + 1           # 1~8 色相桶
                                                 # （ab 四象限太粗：黃與木棕
                                                 # 同象限無轉換點，floor_08
                                                 # 走道/臥室界抓不到）
            cls = cv2.resize(cls1, (labels.shape[1], labels.shape[0]),
                             interpolation=cv2.INTER_NEAREST)
            for key in (1, 2):
                lo, hi = (x0, x1) if key == 1 else (y0, y1)
                maj = np.full(int(hi) + 1, -9, np.int16)
                for c in range(int(lo), int(hi)):
                    colm = region[:, c] if key == 1 else region[c, :]
                    if not colm.any():
                        continue
                    vals = (cls[:, c] if key == 1 else cls[c, :])[colm]
                    bc = np.bincount(vals, minlength=9)
                    maj[c] = int(bc.argmax())
                run_len = 0
                prev = -9
                for c in range(int(lo), int(hi)):
                    if maj[c] == prev:
                        run_len += 1
                    else:
                        if prev != -9 and run_len >= 2 * T and maj[c] != -9:
                            tint_knives[key].append(float(c))
                        prev, run_len = maj[c], 1
        if not big and not (fence_knives[1] or fence_knives[2]):
            if pp_dbg:
                print(f"WW_DEBUG 提案拒: id {room['id']} 非 big 且無 fence 刀")
            continue                             # 小房須有 fence 刀證據
        best = None                              # (score, part_a, part_b)
        for key, grid, lo, hi in ((1, xs_grid, x0, x1), (2, ys_grid, y0, y1)):
            prof = region.sum(axis=0 if key == 1 else 1)
            cands = list(fence_knives[key]) + list(tint_knives[key])
            if big:
                cands += [float(c)
                          for c in range(int(lo) + 2 * T, int(hi) - 2 * T)
                          if abs(int(prof[c]) - int(prof[c - 1])) > T]
                if not evidence_only:
                    cands.append((lo + hi) / 2.0)
            seen = set()
            for c in cands:
                b = int(c // max(T, 1))          # 相鄰候選去重（一桶一刀）
                if b in seen:
                    continue
                seen.add(b)
                a_, b_ = region & (grid < c), region & (grid >= c)
                if a_.sum() < amin or b_.sum() < amin:
                    continue
                tmp = np.zeros_like(labels)
                tmp[a_] = 1
                tmp[b_] = 2
                probs = room_classifier.classify(det.get("bgr"), tmp,
                                                 [{"id": 1}, {"id": 2}],
                                                 variant=variant)
                if probs is None:
                    return out                   # 分類器缺席，整機制停用
                pa, pb = probs[0] or {}, probs[1] or {}
                if not pa or not pb:
                    continue
                la, lb = max(pa, key=pa.get), max(pb, key=pb.get)
                if pp_dbg and evidence_only:
                    print(f"WW_DEBUG 提案候選: id {room['id']} 軸{key} "
                          f"c {c:.0f} {la} {pa[la]:.2f} × {lb} {pb[lb]:.2f}")
                pair = {la, lb}
                if pair == {"Kitchen", "LivingRoom"} and big:
                    thr_pair = p_min
                elif ("Balcony" in pair
                      and (pair - {"Balcony"}) <= {"Kitchen", "LivingRoom",
                                                   "Bedroom"}):
                    thr_pair = 0.65              # Balcony 對從嚴（磁磚客廳
                                                 # 半邊易被誤判 Balcony）
                    bal_half = a_ if la == "Balcony" else b_
                    if not _on_env(bal_half):
                        continue                 # 假陽台半不貼殼緣
                elif pair in ({"Hallway", "LivingRoom"},
                              {"Kitchen", "Bath"}) and big                         and variant == "color":
                    thr_pair = 0.65              # 色界對從嚴（floor_08 型
                                                 # 黃走道/白客廳、浴/廚）；
                                                 # 彩圖限定——灰階實測
                                                 # floor47 被亂切 -2
                    ra, rb = int(a_.sum()), int(b_.sum())
                    if max(ra, rb) > 8 * min(ra, rb):
                        continue                 # 60:1 細條（floor_05 客廳
                                                 # 底緣地毯界）非真色界切分
                elif det.get("_ww_adopted") and variant == "color"                         and big and la != lb:
                    # 救援採用張（災難張）開放任意對：已無可失，雙 0.7
                    # 信心＋比例守門把關（floor_08 實測三塊大房各有
                    # 0.8+/0.9+ 的可切對但不在白名單）
                    thr_pair = 0.70
                    ra, rb = int(a_.sum()), int(b_.sum())
                    if max(ra, rb) > 8 * min(ra, rb):
                        continue
                elif pair == {"Entry", "LivingRoom"} and big:
                    # floor52 實案：玄關半 DINO 0.62/客廳半 0.99，只因不
                    # 在接受對而沒開刀。Entry 誤判常見，從嚴 0.6 且
                    # Entry 半須貼殼緣（玄關必有對外門）
                    thr_pair = 0.60
                    ent_half = a_ if la == "Entry" else b_
                    if not _on_env(ent_half):
                        continue
                else:
                    continue
                if pa[la] < thr_pair or pb[lb] < thr_pair:
                    continue
                score = pa[la] + pb[lb]
                if best is None or score > best[0]:
                    best = (score, a_, b_)
        if best is None:
            if pp_dbg:
                print(f"WW_DEBUG 提案拒: id {room['id']} 候選刀全滅"
                      f"（fence {len(fence_knives[1]) + len(fence_knives[2])}"
                      f" tint {len(tint_knives[1]) + len(tint_knives[2])}）")
            continue
        _s, a_, b_ = best
        nid += 1
        labels[b_] = nid
        te = room.get("touch_env", False)
        out.remove(room)
        for r_ in filter(None, (_room_stats(labels, room["id"], te),
                                _room_stats(labels, nid, te))):
            out.append(r_)
    return out


def build_rooms(det):
    """牆 → 房間方塊：牆端點沿軸向連到對面牆（fp_c._wall_gaps 封口）＋門洞補線
    ＋閉運算，閉合後灌水切連通塊＝房間，再依規則分類房型。
    門位：連線長度 75~100 或 160~190 cm 且有門扇墨水才算門、框黃框；
    範圍外的連線只封口不框。回傳 (labels, rooms, bridges, zones, edges)。"""
    rects, wins, doors = det["rects"], det["wins"], det["doors"]
    T, T_out, cm = det["T"], det["T_out"], det["cm"]
    img_w, img_h = det["img_w"], det["img_h"]

    # 牆端連線（「紅色線端點連到另一端」）：40~260cm 的牆縫開口全封
    bridges = fp_c._wall_gaps(rects, wins, T, cm, 40.0, 260.0)
    # 畫風分流（使用者裁定 2026-08-02）：灰階路凍結維護，color 循環的
    # 新機制一律以 domain 閘門，不進灰階——共用路徑的變更必須雙量尺
    # 護航，但預設灰階零接觸
    is_color_dom = det.get("domain") == "color"
    # 灌水圍欄：灰階用墨水細線層（v2.23 救援輪，灰階自有機制）；
    # 彩圖 thin 太吵只以 det["fence"] 身分供救援輪
    fence = det.get("thin") if det.get("thin") is not None else det.get("fence")
    # 外圈封口（彩圖限定）：外牆寬窗帶（>260cm、窗偵測漏抓）另開 600cm
    # 輪，只在建物外圈生效——floor_09 型「半戶被灌水判室外」的最後防線
    seg_wins = wins
    if is_color_dom:
        seg_wins = wins + fp_c.envelope_gap_seals(rects, wins, T, cm)
    labels, rooms, outside = fp_c.segment_rooms(rects, seg_wins, doors,
                                                img_w, img_h, T, T_out, cm,
                                                keep_small=True,
                                                thin=fence,
                                                fence_guard=is_color_dom)
    if labels is None:
        # 救援階梯第三級（floor02 實案）：寬封口 360cm 全域用是淨負向
        # （走道被寬封口切碎，A/B 實測 −2 命中/−10 命名），但對「常規
        # ＋細線圍欄都救不回」的整圖失敗，360cm 能封住 L 型大開口。
        # 只在整圖失敗時重試，通過的圖零觸碰
        labels, rooms, outside = fp_c.segment_rooms(rects, seg_wins, doors,
                                                    img_w, img_h, T, T_out,
                                                    cm, keep_small=True,
                                                    thin=fence,
                                                    seal_hi=360.0,
                                                    stub_guard=False,
                                                    fence_guard=is_color_dom)
    if labels is None or not rooms:
        zones = [_bridge_zone(*b) for b in bridges
                 if any(lo <= (b[2] - b[1]) * cm <= hi
                        for lo, hi in DOOR_RANGES_CM)]
        return None, [], bridges, zones, []
    # 白牆救援（色塊分割線，彩圖限定＋覆蓋率觸發）：棄守畫風的牆＝
    # 色染間白窄帶，暗色偵測原理性抓不到（floor_08 整戶黏成一塊）。
    # 只在主分割宣告面積 <50% 外圈時啟用（08/09 型災難張），以
    # white_wall_rects 補牆重跑，覆蓋明顯改善（+10pp）才採用——正常
    # 張零接觸，白牆帶的假陽性（床頭板/磁磚列）不波及
    if is_color_dom and rects and os.environ.get("WW_RESCUE", "1") == "1":
        eX0 = min(r_[0] for r_ in rects); eY0 = min(r_[1] for r_ in rects)
        eX1 = max(r_[2] for r_ in rects); eY1 = max(r_[3] for r_ in rects)
        env_a = max(1.0, (eX1 - eX0) * (eY1 - eY0))
        cov = sum(r_["area_px"] for r_ in rooms) / env_a
        big_blob = (len(rooms) <= 5
                    and max(r_["area_px"] for r_ in rooms) / env_a > 0.35)
        ww_dbg = os.environ.get("WW_DEBUG") == "1"
        if ww_dbg:
            print(f"WW_DEBUG 主分割: cov {cov:.3f} rooms {len(rooms)} "
                  f"big_blob {big_blob}")
        shatter = cov < 0.50 and len(rooms) >= 20
        if (cov < 0.50 and len(rooms) < 8) or shatter \
                or big_blob or os.environ.get("WW_FORCE") == "1":
                                                 # 災難張三型：低覆蓋房少
                                                 # （09 型）、巨塊黏連（08
                                                 # 型）、低覆蓋碎裂（07 型：
                                                 # cov 42%/58 房，白磁磚區
                                                 # 全碎）。floor_04 覆蓋被
                                                 # 外圈空地低估但 16 房正
                                                 # 常，8~19 房安全窗擋誤觸
                                                 # WW_FORCE 僅供離線診斷探測
            bgr1 = det.get("bgr")
            sc = img_w / float(bgr1.shape[1])
            T1x = max(6, int(round(T / sc)))
            ww = fp_c.white_wall_rects(
                bgr1, T1x,
                dark_rects=[(r_[0] / sc, r_[1] / sc, r_[2] / sc, r_[3] / sc)
                            for r_ in rects])
            # 語意牆帶（分割頭，2026-08-03）：近白暗示牆的白帶/暗色都抓
            # 不到，DINO patch 機率圖的低機率脊線補上；門洞照走既有門
            # 尺寸縫封口。資產缺檔＝空清單，行為不變。SEG_BANDS=0 供 A/B
            if os.environ.get("SEG_BANDS", "1") == "1":
                import seg_head
                sb = seg_head.wall_bands(bgr1, T1x)
                if sb:
                    print(f"語意牆帶 : {len(sb)} 段（seg_head）")
                    ww = ww + sb
            ww2 = [(x0 * sc, y0 * sc, x1 * sc, y1 * sc)
                   for x0, y0, x1, y1 in ww]
            if ww2:
                labels_w, rooms_w, outside_w = fp_c.segment_rooms(
                    rects + ww2, seg_wins, doors, img_w, img_h, T, T_out,
                    cm, keep_small=True, thin=fence, fence_guard=True,
                    seal_hi=360.0, stub_guard=False)
                if labels_w is not None and rooms_w:
                    cov_w = sum(r_["area_px"] for r_ in rooms_w) / env_a
                    ok_cov = cov_w >= 0.55 and cov_w > cov + 0.10
                    if shatter and len(rooms_w) >= len(rooms):
                        # 碎裂型救援的天職是收斂（floor_07 58→13）；
                        # 越補越碎（floor_04 22→41、9/10→6/10）＝白帶
                        # 在正常張灑假牆，覆蓋過閘也不可採
                        ok_cov = False
                    ok_blob = big_blob and cov_w >= 0.55                         and len(rooms_w) > len(rooms)
                    if ww_dbg:
                        print(f"WW_DEBUG 救援輪: 白牆帶 {len(ww2)} 段 "
                              f"cov_w {cov_w:.3f} rooms_w {len(rooms_w)} "
                              f"ok_cov {ok_cov} ok_blob {ok_blob}")
                        det["_ww_debug"] = {
                            "ww2": ww2, "labels_w": labels_w,
                            "rooms_w": rooms_w, "outside_w": outside_w,
                            "cov": cov, "cov_w": cov_w,
                            "rects": rects, "T": T}
                    if ok_cov or ok_blob:        # 半修復（floor_09 46% 採用
                                                 # 反而 2→1）不如不修——絕對
                                                 # 覆蓋 ≥55% 才接手；巨塊型
                                                 # 切牆後覆蓋自然下降，只要
                                                 # ≥55% 且房數增加即採
                                                 # （floor_08 73%→66%/3→6）
                        det["_ww_adopted"] = True
                        det["_ww_bands"] = ww2   # 縫合輪要分辨白帶/暗牆分隔
                        print(f"白牆救援 : 覆蓋 {cov:.0%}→{cov_w:.0%}，"
                              f"補 {len(ww2)} 段白牆帶")
                        labels, rooms, outside = labels_w, rooms_w, outside_w
    # 走道橫斷橋合併後即失效：疊圖不再畫、恰為門尺寸者的假門位一併移除
    rooms, bridges = _merge_nondoor_bridges(labels, rooms, bridges, det)
    # 浴室隔屏碎格合併（floor38/44 實案）——須在面積終篩前，
    # 合併後的浴室才活得過門檻
    if is_color_dom:
        # 彩圖無符號證據，浴室碎格合併改走 DINO 種子路：<8m² 碎房
        # 先過分類器，判 Bath（≥0.5）＝種子、判 Kitchen＝反證
        # 口袋房（陽台收割）不進種子也不可被吸收——磁磚陽台的裁切
        # 常被判 Bath，bath1 實測 -4 的主因。上限 4m²（非灰階路的
        # 8m²）：已成形的浴室不動，只併真碎格——bath2 實測 8m² 會把
        # floor_19 已配上的浴室吸進去稀釋
        small = [r for r in rooms
                 if r["area_px"] * cm * cm < 40000.0
                 and not r.get("pocket")]
        seeds, vetos = set(), set()
        if len(small) >= 2:
            probs_s = room_classifier.classify(det.get("bgr"), labels, small,
                                               variant="color")
            if probs_s is not None:
                for r_, pr in zip(small, probs_s):
                    if not pr:
                        continue
                    top = max(pr, key=pr.get)
                    if top == "Bath" and pr[top] >= 0.7:
                        seeds.add(r_["id"])
                    elif top != "Bath":
                        vetos.add(r_["id"])
        vetos |= {r_["id"] for r_ in rooms if r_.get("pocket")}
        rooms = _merge_bath_nooks(labels, rooms, det, T,
                                  seed_ids=seeds, veto_ids=vetos)
    else:
        rooms = _merge_bath_nooks(labels, rooms, det, T)
        # 灰階符號種子不足時（floor06 實案：整圖只偵測到 kstove，
        # 浴室碎格無種子可併）補一輪 DINO 種子路，守門同彩圖
        small = [r for r in rooms
                 if r["area_px"] * cm * cm < 40000.0
                 and not r.get("pocket")]
        if len(small) >= 2:
            probs_s = room_classifier.classify(det.get("bgr"), labels, small,
                                               variant="gray")
            if probs_s is not None:
                seeds, vetos = set(), set()
                for r_, pr in zip(small, probs_s):
                    if not pr:
                        continue
                    top = max(pr, key=pr.get)
                    if top == "Bath" and pr[top] >= 0.7:
                        seeds.add(r_["id"])
                    elif top != "Bath":
                        vetos.add(r_["id"])
                vetos |= {r_["id"] for r_ in rooms if r_.get("pocket")}
                rooms = _merge_bath_nooks(labels, rooms, det, T,
                                          seed_ids=seeds, veto_ids=vetos)
    # 面積終篩（keep_small 的另一半）：走道碎片已在上一步併回整條，
    # 這裡才執行原本的面積門檻——未被合併救回的碎片與雜訊小塊在此淘汰
    X0 = min(r_[0] for r_ in rects); Y0 = min(r_[1] for r_ in rects)
    X1 = max(r_[2] for r_ in rects); Y1 = max(r_[3] for r_ in rects)
    amin = max(int(0.003 * (X1 - X0) * (Y1 - Y0)), 2 * (2 * T) ** 2)
    dropped = [r for r in rooms if r["area_px"] < amin]
    if dropped:
        for r in dropped:
            labels[labels == r["id"]] = 0
        rooms = [r for r in rooms if r["area_px"] >= amin]
    if not rooms:
        zones = [_bridge_zone(*b) for b in bridges
                 if any(lo <= (b[2] - b[1]) * cm <= hi
                        for lo, hi in DOOR_RANGES_CM)]
        return None, [], bridges, zones, []
    zones = [_bridge_zone(*b) for b in bridges
             if any(lo <= (b[2] - b[1]) * cm <= hi for lo, hi in DOOR_RANGES_CM)
             and _bridge_has_door_ink(det, *b)]  # 迴轉區無墨=開放通道非門
    # 樓梯足跡切分：開放區嵌樓梯無牆可封，踏板串外框直接切出成房
    rooms = _carve_stairs(labels, rooms, detect_stair_boxes(det), T, cm)
    # OCR 錨點功能區切分：一房含 2+ 房名文字＝作者標了 2+ 個功能區
    rooms = _split_by_text_anchors(labels, rooms, det.get("texts") or [],
                                   T, cm, amin)
    # 符號錨點補位（無文字圖）：廚房系符號群觸發廚客分家。
    # 文字已切開的房不會再有雙系符號，兩機制天然互補不重疊。
    # min_part_ratio=1.8：廚餐一體房（子區歸主房慣例）兩半約等大，
    # 真開放廚客的客廳側遠大於廚房側——floor07 實案的守門
    # 方正守門讓行：兩半近等大時用 DINO 驗證兩半各自像不像錨點房型
    # （floor47/52/13 型開放 LDK 的廚客真切分兩半 ~1:1，硬守門會擋掉；
    # floor07 廚餐一體房的餐半不會被判成 LivingRoom，仍被擋）
    def _dino_verify(parts, merged):
        tmp = np.zeros(labels.shape, np.int32)
        tmp[parts[0]] = 1
        tmp[parts[1]] = 2
        variant = "color" if is_color_dom else "gray"
        probs = room_classifier.classify(det.get("bgr"), tmp,
                                         [{"id": 1}, {"id": 2}],
                                         variant=variant)
        if probs is None:
            return False
        ok = 0
        for lab_a, cx, cy in merged:
            iy, ix = int(round(cy)), int(round(cx))
            if not (0 <= iy < labels.shape[0] and 0 <= ix < labels.shape[1]):
                return False
            pi = 0 if parts[0][iy, ix] else 1
            pr = probs[pi] or {}
            if pr and max(pr, key=pr.get) == lab_a:
                ok += 1
        return ok == len(merged)                 # 兩半 top-1 都對才放行

    rooms = _split_by_text_anchors(labels, rooms,
                                   _symbol_anchors(det, labels, rooms),
                                   T, cm, amin, min_part_ratio=1.8,
                                   verify=_dino_verify if is_color_dom
                                   else None)
    # 殼外陽台口袋收割——彩圖常駐；灰階以自屬開關回收（2026-08-02
    # floor06 露台實案＋早前實測 dev +3/holdout +1，依分流原則另以灰階
    # 量尺獨立 A/B 後啟用）
    rooms = _harvest_balcony_pockets(det, labels, rooms, outside)
    # DINO 提案式切分：無錨點大房（無 OCR 房名、無符號可用）的開放
    # LDK 最後手段。房內已有作者房名文字者不提案（作者說了算）
    h_, w_ = labels.shape
    texted = set()
    for t in det.get("texts") or ():
        iy, ix = int(round(t[2])), int(round(t[1]))
        if 0 <= iy < h_ and 0 <= ix < w_ and labels[iy, ix] > 0:
            texted.add(int(labels[iy, ix]))
    untexted = [r for r in rooms if r["id"] not in texted]
    if untexted:
        kept_ids = {r["id"] for r in untexted}
        merged_out = _dino_propose_splits(det, labels, untexted, T, cm, amin)
        rooms = [r for r in rooms if r["id"] not in kept_ids] + merged_out
    # 房型命名（2026-07-30 起只剩兩層，CubiCasa 語意投票已整批移除）：
    #   1) DINOv2 裁切分類（room_classifier）——own_eval 72 房 90.3%
    #   2) 面積規則（純幾何兜底）——缺 torch/骨幹/線性頭時
    # 彩圖管線（det 帶 fence）用 color 專屬頭：混訓實測傷灰階基準，分域雙頭
    variant = "color" if is_color_dom else "gray"
    probs = room_classifier.classify(det.get("bgr"), labels, rooms,
                                     variant=variant)
    if probs is not None:
        classify_rooms_dino(det, labels, rooms, probs, outside)
        # 假帶縫合輪（救援採用張限定）：命名後才知道誰是 Hallway 殘塊
        rooms = _ww_suture_merge(det, labels, rooms, T, cm)
    else:
        print("⚠ DINOv2 房型分類不可用 → 房型退回面積規則（品質明顯較差）")
        fp_c.classify_rooms(rooms, cm, det["thin"], labels)
    # room_graph 只拿來算 has_door/相鄰圖——黃框依長度規則全畫，不被它篩掉
    edges, _kept = fp_c.room_graph(labels, outside, rooms, zones, rects, wins, T)
    return labels, rooms, bridges, zones, edges


def preview_rooms(det, labels, rooms, bridges, path):
    """房間疊圖：房間依房型上色、紅=牆、綠=窗、房名標字。
    牆端連線（封口）分兩種畫法（user 回饋：無門的縫畫橘色會被讀成
    「多切了一條」）——有門證據的開口＝橘實線；無門證據的縫＝當牆
    封死，畫暗紅與牆同色。門位黃框另出 _door.png（同一張太亂）。"""
    bgr = det["bgr"]
    cm = det["cm"]
    vis = bgr.copy()
    fill = vis.copy()
    if rooms and labels is not None:
        for r in rooms:
            fill[labels == r["id"]] = ROOM_BGR_EX.get(r["label"] or "room",
                                                      (150, 150, 150))
    for x0, y0, x1, y1 in det["rects"]:
        cv2.rectangle(fill, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), -1)
    vis = cv2.addWeighted(fill, 0.45, vis, 0.55, 0)   # 半透明：紅牆 + 房型色塊
    for horiz, g0, g1, b0, b1 in bridges:
        is_door = any(lo <= (g1 - g0) * cm <= hi for lo, hi in DOOR_RANGES_CM) \
            and _bridge_has_door_ink(det, horiz, g0, g1, b0, b1)
        color = (0, 140, 255) if is_door else (0, 0, 139)   # 橘=門開口、暗紅=封牆
        m = (b0 + b1) / 2.0
        p1 = (int(g0), int(m)) if horiz else (int(m), int(g0))
        p2 = (int(g1), int(m)) if horiz else (int(m), int(g1))
        cv2.line(vis, p1, p2, color, max(2, int(det["T"] // 2)))
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


def write_rooms_json(path, det, rooms, zones, edges, is_color, colorful,
                     emit_openings=True):
    """emit_openings=False（彩色預設，2026-08-02 使用者裁定）→ doors 發空
    清單交後端補建：彩門 P 0.38/R 0.47 低於可用線，畫出來反增人工刪除。
    灰階 zones 路 P 0.85/R 0.71 照常發射。"""
    data = {
        "openings_suppressed": not emit_openings,
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
        } for quad, d in (zones if emit_openings else [])],
        "rooms": [{
            "id": r["id"], "label": r["label"], "label_zh": r["label_zh"],
            "area_m2": r["area_m2"], "bbox": list(r["bbox"]),
            "center": [round(r["cx"], 1), round(r["cy"], 1)],
            "aspect": r["aspect"], "has_door": bool(r.get("has_door", False)),
            "reach": bool(r.get("reach", False)),
            "cc_share": r.get("cc_share"), "icons_cm2": r.get("icons_cm2"),
            "symbols": r.get("symbols"), "ocr_text": r.get("ocr_text"),
            "relabel_from": r.get("relabel_from"),
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
    # OCR 必須先於 detect_symbols：模板比對用 text_boxes 抑制圖面文字假陽性
    # （floor06 的 LNDRY/BALCONY 曾被判成 ksink/sofa）。順序反了不會報錯，
    # 只會拿到空的抑制清單——test_symbol_gate.py 有斷言釘住。
    if not is_color and cfg_bw.deskew:           # OCR 讀原始檔，轉正後座標對不上分析圖
        print("⚠ deskew 開啟 → OCR 文字證據層停用（座標無法對齊）")
        det["texts"], det["text_boxes"] = [], []
    else:
        det["texts"] = detect_room_text(path, det["img_w"], det["img_h"])  # OCR 文字證據（層 5）
        det["text_boxes"] = detect_text_boxes(path, det["img_w"], det["img_h"])
    det["symbols"] = detect_symbols(det)         # 古典家具符號（補模型盲區）

    labels, rooms, bridges, zones, edges = build_rooms(det)
    png_out = os.path.join(out_dir, base + "_room.png")
    door_dir = os.path.join(os.path.dirname(out_dir.rstrip("/\\")) or ".",
                            "door")              # 門位圖獨立目錄（room/ 的兄弟）
    os.makedirs(door_dir, exist_ok=True)
    door_out = os.path.join(door_dir, base + "_door.png")
    os.makedirs("temp/json/room", exist_ok=True)
    json_out = os.path.join("temp/json/room", base + "_room.json")
    preview_rooms(det, labels, rooms, bridges, png_out)
    preview_doors(det, zones, door_out)
    write_rooms_json(json_out, det, rooms, zones, edges, is_color, colorful,
                     emit_openings=(not is_color) or cfg_color.emit_openings)

    if rooms:
        names = "、".join(f'{r["label_zh"]}{r["area_m2"]}m²' for r in rooms)
        print(f"房間   : {len(rooms)} 間（{names}）  牆端連線 {len(bridges)} 條"
              f"  門位 {len(zones)} 個（75~100/160~190cm）")
    else:
        print("房間   : 分割失敗（殼封不起來）——疊圖仍輸出牆與連線供檢視")
    print(f"輸出   : {png_out}   {door_out}   {json_out}")
    return bool(rooms)


def resolve_input(arg):
    """輸入參數 → 實際路徑。當前目錄找得到就照用（單張圖檔一律當相對路徑），
    否則把簡名當成 testdata/ 底下的同名目錄：`png` → testdata/png/、
    `color_png` → testdata/color_png/。都找不到就原樣回傳，交給呼叫端報錯。"""
    if os.path.exists(arg):
        return arg
    cand = os.path.join(_ROOT, "testdata", arg)
    if os.path.isdir(cand):
        return cand
    return arg


def main():
    p = argparse.ArgumentParser(
        description="平面圖 → 房間方塊（自動判黑白/彩色，調用對應管線，不出 DXF）。")
    p.add_argument("input", nargs="?",
                   help="輸入圖檔(單張)或目錄(批次)；目錄簡名如 png/color_png 會解成 "
                        "testdata/ 底下的同名目錄")
    p.add_argument("output", nargs="?", help="輸出目錄（預設 chk/room/）")
    p.add_argument("--config", default="config.ini", help="黑白管線設定檔")
    p.add_argument("--config-color", default="config_color.ini", help="彩色管線設定檔")
    a = p.parse_args()

    cfg_bw = fp_bw.load_config(a.config)
    cfg_color = fp_c.load_config(a.config_color)
    out_dir = a.output or os.path.join("temp/chk", "room")
    os.makedirs(out_dir, exist_ok=True)

    if not a.input:
        sys.exit("請給要處理的圖檔或目錄"
                 "  (單張：floorplan2room.py 圖.png；批次：floorplan2room.py png)")

    src = resolve_input(a.input)
    if os.path.isfile(src):
        process(src, out_dir, cfg_bw, cfg_color)
        return

    in_dir = src
    if not os.path.isdir(in_dir):
        sys.exit(f"找不到 {a.input}  (也試過 testdata/{a.input}/)")
    imgs = sorted(p_ for p_ in glob.glob(os.path.join(in_dir, "*"))
                  if p_.lower().endswith(IMG_EXTS))
    if not imgs:
        sys.exit(f"{in_dir}/ 裡找不到圖檔 ({'/'.join(IMG_EXTS)})")
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
    print(f"  疊圖 → {out_dir}/  (紅牆、橘=牆端連線、房型色塊)")
    print(f"  門位 → {os.path.join(os.path.dirname(out_dir.rstrip('/')), 'door')}/"
          f"  (黃框=門位75~100/160~190cm)")
    print(f"  JSON → temp/json/room/  (<名>_room.json：房間+門位清單)")


if __name__ == "__main__":
    # Windows 原生的 stdout 重導預設 cp950，編不出本檔 9 處警告裡的 ⚠(U+26A0)
    # → `python floorplan2room.py > log.txt` 會整支炸掉。只動 __main__，
    # 被伺服器端 import 時不改動宿主行程的 stdout。
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    main()
