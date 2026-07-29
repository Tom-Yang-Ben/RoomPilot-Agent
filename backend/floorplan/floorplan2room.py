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
房型以辨識決定（放棄面積規則）：CubiCasa 語意投票 + 圖示 + 古典符號偵測。

用法：
  python floorplan2room.py              # 批次 testdata/png/ → chk/room/
  python floorplan2room.py 圖.png       # 單張
  python floorplan2room.py 目錄 [輸出]  # 批次指定目錄
"""
import argparse
import difflib
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import replace

import cv2
import numpy as np

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_PKG_DIR))
sys.path.insert(0, _PKG_DIR)           # 管線模組（含 symbol_match、infer_cubicasa）同在 backend/floorplan/

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
DOOR_RANGES_CM = ((75.0, 100.0), (160.0, 190.0))  # 單門 / 雙開門。單門原 user spec
                                                   # 80~95，門位掛上墨水證據後放寬
                                                   # 75~100：own 集門 GT 實測 R 0.56→0.73、
                                                   # P 0.90→0.86（floor04 比例尺被走道假開
                                                   # 口拉偏，真門量成 78cm 全漏）
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
        out.append((lat_c, pos_c) if horiz else (pos_c, lat_c))
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
        for cx, cy in _stair_runs(_axis_segments(lines, cm, horiz), cm, horiz):
            out.append(("stair", cx, cy))
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
OCR_WORD2LABEL = {
    "DORMITORY": "bed", "BEDROOM": "bed",
    "KITCHEN": "kitchen",
    "BATH": "bath", "BATHROOM": "bath", "WC": "bath", "TOILET": "bath",
    "LIVING": "living", "LIVINGROOM": "living", "LOUNGE": "living",
    "DEPOSIT": "storage", "STORAGE": "storage", "CLOSET": "storage",
    "CIRCULATION": "entry", "HALL": "entry", "HALLWAY": "entry",
    "ENTRY": "entry",
    "BALCONY": "outdoor", "TERRACE": "outdoor",
    "GARAGE": "garage",
    # 書房系詞彙 → storage（office 已於 2026-07-29 併入 storage）。
    # STAIRWELL/STAIRCASE 含 STAIR，片語比對取最長鍵仍是 stair。
    "OFFICE": "storage", "STUDY": "storage", "WORKROOM": "storage",
    "DEN": "storage", "LIBRARY": "storage",
    "STAIR": "stair", "STAIRS": "stair", "STAIRWELL": "stair",
    "STAIRCASE": "stair",
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


# ─────────────────────────── 語意辨識房型 ───────────────────────────
# 兩個預設路徑都以模組自身位置推導，不吃 cwd——本檔既被當腳本直接執行（cwd 可能是
# backend/floorplan/），也可能被伺服器端 import（cwd 由伺服器決定）。與 main 的 20cfd21 同步。
CC_CACHE_DIR = os.environ.get(
    "CC_CACHE_DIR", os.path.join(_ROOT, "cubicasa", "room"))  # CubiCasa 語意快取（含 room/icon 通道）；`cubicasa/room/` 是跨分支契約路徑，錨在 repo 根不搬進套件目錄
CC_WEIGHTS = os.environ.get(
    "CC_WEIGHTS", os.path.join(_PKG_DIR, "model_finetuned_v5.pkl"))  # 預設 v5 微調權重（與 main 統一放 backend/floorplan/；own 域主尺勝出 2026-07-25）；環境變數可換權重 A/B 驗收
# 權重 200M 超 GitHub 100MB 限制不進版控，掛在 Release 上，缺檔時自動下載（部署端 clone 即可用）。
# repo 目前 private：直鏈 404，須以 token 走 asset API 換 S3 簽名鏈（部署端本就有 clone 用 token，
# 設 GITHUB_TOKEN / GH_TOKEN 即可）；repo 若轉 public，直鏈自動生效、零設定
CC_WEIGHTS_URL = ("https://github.com/Tom-Yang-Ben/RoomPilot-Agent/"
                  "releases/download/weights-v5/model_finetuned_v5.pkl")
CC_WEIGHTS_ASSET_API = ("https://api.github.com/repos/Tom-Yang-Ben/RoomPilot-Agent/"
                        "releases/assets/489011637")
CC_WEIGHTS_SHA256 = "b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf"
CC_ROOM_LABEL = {3: "kitchen", 4: "living", 5: "bed", 6: "bath",
                 7: "entry", 9: "storage", 10: "garage", 1: "outdoor"}
# 模型盲區類：CubiCasa 的 12 個 room class 沒有樓梯，StairWell 在其
# rooms_selected 是 11(Undefined)——語意投票（層 1/2）結構上產不出來，
# 分數只能由證據層供給（層 4 的 detect_stairs 踏板幾何）。
# 必須另行播種進 score，否則 OCR 層的 `if lab_t in score` 防呆會靜默丟掉證據。
#
# 註：曾短暫存在的 `office`（書房）已於 2026-07-29 併入 `storage`（使用者裁決）
# ——兩者實務上是同一空間的兩個狀態，且 DINOv2 實測從未把它們互相搞混，
# 分開標不帶來可量測資訊。書房系 OCR 詞彙改指向 storage。
EXTRA_LABELS = ("stair",)
CC_ICON = {"closet": 3, "appliance": 4, "toilet": 5, "sink": 6,
           "sauna": 7, "fireplace": 8, "bathtub": 9}
ROOM_ZH_EX = {**fp_c.ROOM_ZH, "entry": "玄關", "storage": "儲藏室",
              "garage": "車庫", "outdoor": "陽台/戶外",
              "stair": "樓梯"}
ROOM_BGR_EX = {**fp_c.ROOM_BGR, "entry": (120, 210, 250),
               "storage": (180, 180, 120), "garage": (130, 130, 130),
               "outdoor": fp_c.ROOM_BGR["balcony"],
               "stair": (70, 70, 200)}


def _cc_path(img_path):
    base = os.path.splitext(os.path.basename(img_path))[0]
    return os.path.join(CC_CACHE_DIR, base + "_mask.npz")


def _cc_ok(npz_path):
    if not os.path.isfile(npz_path):
        return False
    with np.load(npz_path) as z:                   # 舊版快取沒有 room 通道 → 重推
        return "room" in z.files


def cc_cache_valid(cc_file, img_w, img_h, src_sha256=None):
    """語意快取來源驗證。infer_cubicasa 一律以來源圖「原尺寸」輸出遮罩，
    所以遮罩尺寸 ≠ 分析圖尺寸＝同名不同圖（跨分支同名檔已實際發生：
    main 的 floor10.png 419×687 vs 本分支遮罩 896×1200），視為快取失效，
    避免錯圖語意被 classify_rooms_cc 的 resize 靜默吞掉、套出錯房型。
    彩圖管線可能把圖放大 2 倍——img_w/img_h 收的是管線工作尺寸，
    故遮罩等於工作尺寸或其一半皆屬同圖。
    新版快取帶 src_sha256（infer_cubicasa 寫入）；呼叫端有給雜湊且快取有存時，
    再以內容嚴格比對，擋掉「不同圖恰好同尺寸」的殘餘風險。"""
    if not _cc_ok(cc_file):
        return False
    with np.load(cc_file) as z:
        mh, mw = z["room"].shape[:2]
        if (mh, mw) not in ((img_h, img_w), (img_h // 2, img_w // 2)):
            return False
        if src_sha256 and "src_sha256" in z.files:
            return str(z["src_sha256"]) == src_sha256
    return True


def _gh_token():
    """找部署/開發環境可用的 GitHub token：環境變數優先，其次 git 憑證系統。"""
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(
            ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}).stdout
        for line in out.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
    except Exception:
        pass
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _resolve_weights_url():
    """回傳實際可下載的 URL。公開 repo 直鏈即中；私有 repo 用 token 向 asset API
    換 S3 簽名鏈（簽名鏈本身免認證，避免 Authorization 頭被轉送到 S3 造成 400）。"""
    try:
        urllib.request.urlopen(
            urllib.request.Request(CC_WEIGHTS_URL, method="HEAD"), timeout=15)
        return CC_WEIGHTS_URL
    except Exception:
        pass
    tok = _gh_token()
    if not tok:
        return None
    req = urllib.request.Request(CC_WEIGHTS_ASSET_API, headers={
        "Accept": "application/octet-stream", "Authorization": "Bearer " + tok})
    try:
        urllib.request.build_opener(_NoRedirect()).open(req, timeout=30)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308):
            return e.headers.get("Location")
    except Exception:
        pass
    return None


def _ensure_cc_weights():
    """權重檔缺失時自動從 GitHub Release 下載（SHA-256 校驗）。
    使用者以 CC_WEIGHTS 環境變數指定的權重不代抓——缺了就該報錯而非默默換檔。"""
    if os.path.isfile(CC_WEIGHTS):
        return True
    if os.environ.get("CC_WEIGHTS"):
        return False
    url = _resolve_weights_url()
    if not url:
        print("⚠ 權重下載無可用管道：私有 repo 需 GITHUB_TOKEN / GH_TOKEN 或 git 憑證")
        return False
    print(f"權重下載 : {CC_WEIGHTS_URL}（約 200MB，僅首次）")
    os.makedirs(os.path.dirname(CC_WEIGHTS) or ".", exist_ok=True)  # 先建目錄，否則 200MB 抓完才在寫檔時失敗（與 main 的 20cfd21 同步）
    tmp = CC_WEIGHTS + ".part"
    try:
        urllib.request.urlretrieve(url, tmp)
        h = hashlib.sha256()
        with open(tmp, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != CC_WEIGHTS_SHA256:
            os.remove(tmp)
            print("⚠ 權重下載 SHA-256 校驗失敗，已捨棄")
            return False
        os.replace(tmp, CC_WEIGHTS)
        return True
    except Exception as e:
        if os.path.isfile(tmp):
            os.remove(tmp)
        print(f"⚠ 權重下載失敗：{e}")
        return False


def _cc_stale(img_path):
    """快取缺失或與來源圖對不上（尺寸／雜湊）＝該重推。
    遮罩由 infer_cubicasa 以來源圖原尺寸輸出，尺寸不符只可能是同名換圖。"""
    npz = _cc_path(img_path)
    if not _cc_ok(npz):
        return True
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False                               # 讀不到圖 → 交給下游報錯，別觸發推論
    with np.load(npz) as z:
        if z["room"].shape[:2] != img.shape[:2]:
            return True
        if "src_sha256" in z.files:
            with open(img_path, "rb") as f:
                return str(z["src_sha256"]) != hashlib.sha256(f.read()).hexdigest()
    return False


def ensure_cc_masks(paths):
    """缺（或失效）語意快取的圖先跑 CubiCasa 推論（一次 subprocess 全補，CPU 約 1 分/張）。"""
    miss = [p for p in paths if _cc_stale(p)]
    if not miss:
        return
    if not _ensure_cc_weights():
        print(f"⚠ 找不到 {CC_WEIGHTS}，跳過語意辨識（房型退回面積規則）")
        return
    print(f"CubiCasa 語意推論 : {len(miss)} 張（CPU 約 1 分/張 → {CC_CACHE_DIR}/）")
    subprocess.run([sys.executable,
                    os.path.join(_PKG_DIR, "infer_cubicasa.py"),
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
        score.update({lab: 0.0 for lab in EXTRA_LABELS})   # 模型盲區類：0 分起跳，
        # 全靠證據層加分；播種只是讓 OCR/幾何有 key 可加，不是 0.15 門檻的免死金牌
        typed = sum(score.values())               # 相對多數票（層 2）
        # 弱票不放大：top 票 <0.35 代表模型自己也沒把握（floor04 living 0.275
        # 弱票曾被放大到蓋過一切），加成只留給有把握的相對多數
        if typed >= 0.05:
            top = max(score, key=score.get)
            if score[top] >= 0.35:
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
        # 後十類為 Asset 家具模板庫 kind（extract_asset_lib.py，分類依
        # 使用者裁決：dtable→kitchen、chair(單人沙發)→living）
        n = {"oval": 0, "tubrect": 0, "bedrect": 0, "stove": 0,
             "shower": 0, "sinkicon": 0,
             "wc": 0, "tub": 0, "basin": 0, "kstove": 0, "ksink": 0,
             "dtable": 0, "bed": 0, "wardrobe": 0, "sofa": 0, "chair": 0,
             "stair": 0}
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
        # Asset 家具模板證據（存在制不疊加，權重保守——模板與考卷畫風
        # 有落差，寧漏勿誤；廚房系沿用 open_living 防呆）
        if n["wc"]:
            score["bath"] += 0.4
        if n["tub"]:
            score["bath"] += 0.3
        if n["basin"]:
            score["bath"] += 0.2
        if n["kstove"] and not open_living:
            score["kitchen"] += 0.35
        if n["ksink"] and not open_living:
            score["kitchen"] += 0.2
        if n["dtable"] and not open_living:          # user 裁決：餐桌歸廚房
            score["kitchen"] += 0.25
        if n["bed"]:
            score["bed"] += 0.4
        if n["wardrobe"]:
            score["bed"] += 0.2
        if n["sofa"]:
            score["living"] += 0.3
        if n["chair"]:                               # user 裁決：單人沙發＝客廳
            score["living"] += 0.15
        if n["stair"]:                               # 樓梯踏板（detect_stairs）
            # 權重高於一般家具：4+ 條等距等長踏板是強幾何約束，且 stair 沒有
            # 語意票可搭配（模型盲區類），證據不夠力就永遠叫不出這個名字
            score["stair"] += 0.6
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
        lab, val = max(score.items(), key=lambda kv: kv[1])
        r["label"] = lab if val >= 0.15 else "room"
        r["label_zh"] = ROOM_ZH_EX[r["label"]]
        r["cc_share"] = {k: round(v, 3) for k, v in score.items() if v >= 0.02}
        r["icons_cm2"] = {k: round(v) for k, v in icx.items() if v >= 20}
        r["_score"] = score                    # 供限額後處理挑次高分，結尾即刪
    _enforce_singletons(rooms)
    for r in rooms:
        del r["_score"]


UNIQUE_LABELS = ("living", "kitchen")          # user spec：全戶各最多一間，留面積最大


def _enforce_singletons(rooms):
    """住宅常識約束（user spec）：living/kitchen 全戶各限一間。
    同類多間只保留面積最大者，其餘降級為自己的次高分房型——限額類
    不得再選（降級又互撞），次高分 <0.15 照原則標中性「空間」。
    接著：有廚無廳＝那間「廚房」多半是客餐廚一體，改叫客廳優先；
    圖面文字明寫 KITCHEN（作者親口說的答案）則豁免不改。
    relabel_from 記錄原判供 JSON 追溯。"""
    for lab in UNIQUE_LABELS:
        cand = [r for r in rooms if r["label"] == lab]
        for r in sorted(cand, key=lambda c: c["area_m2"], reverse=True)[1:]:
            alt = {k: v for k, v in r["_score"].items()
                   if k not in UNIQUE_LABELS}
            alt_lab, alt_val = max(alt.items(), key=lambda kv: kv[1])
            r["relabel_from"] = lab
            r["label"] = alt_lab if alt_val >= 0.15 else "room"
            r["label_zh"] = ROOM_ZH_EX[r["label"]]
    if not any(r["label"] == "living" for r in rooms):
        for r in rooms:                        # 限額後 kitchen 至多一間
            if r["label"] == "kitchen" \
                    and "kitchen" not in (r.get("ocr_text") or {}):
                r["relabel_from"] = "kitchen"
                r["label"] = "living"
                r["label_zh"] = ROOM_ZH_EX["living"]


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





def _bridge_has_door_ink(det, horiz, g0, g1, b0, b1):
    """門位證據：門扇迴轉區（開口兩側各 1.1×開口深）扣掉 OCR 文字框後的
    細線墨水密度。真門畫弧/門扇必留墨（floor04 浴廁虛線弧 1.45%），
    開放通道空白（走道↔客廳 0%）；文字墨水（CIRCULATION 4.8%）已扣，
    門檻取 0.5%。弧掃描（_has_door_swing 0.9 覆蓋率）對虛線弧眼盲、
    detect_doors 亦然，故用密度而非形狀。thin 缺席（彩圖管線）不濾照舊。"""
    thin = det.get("thin")
    if thin is None:
        return True
    ink = thin.copy()
    for x0, y0, x1, y1 in det.get("text_boxes", ()):
        ink[max(0, int(y0) - 2):int(y1) + 3,
            max(0, int(x0) - 2):int(x1) + 3] = 0
    gap = g1 - g0
    H, W = ink.shape
    # 三個證據區：開口帶本身（雙開/滑門門扇畫在開口內）＋兩側迴轉區（單開門弧）
    regions = [(b0, b1)] + [(b0 - 1.1 * gap, b0), (b1, b1 + 1.1 * gap)]
    for lo, hi in regions:
        if horiz:
            y0, y1, x0, x1 = lo, hi, g0, g1
        else:
            x0, x1, y0, y1 = lo, hi, g0, g1
        box = ink[max(0, int(y0)):min(H, int(y1)),
                  max(0, int(x0)):min(W, int(x1))]
        if box.size and np.count_nonzero(box) / box.size >= 0.005:
            return True
    return False


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
    門位：連線長度 75~100 或 160~190 cm 且有門扇墨水才算門、框黃框；
    範圍外的連線只封口不框。回傳 (labels, rooms, bridges, zones, edges)。"""
    rects, wins, doors = det["rects"], det["wins"], det["doors"]
    T, T_out, cm = det["T"], det["T_out"], det["cm"]
    img_w, img_h = det["img_w"], det["img_h"]

    # 牆端連線（「紅色線端點連到另一端」）：40~260cm 的牆縫開口全封
    bridges = fp_c._wall_gaps(rects, wins, T, cm, 40.0, 260.0)
    labels, rooms, outside = fp_c.segment_rooms(rects, wins, doors,
                                                img_w, img_h, T, T_out, cm)
    if labels is None or not rooms:
        zones = [_bridge_zone(*b) for b in bridges
                 if any(lo <= (b[2] - b[1]) * cm <= hi
                        for lo, hi in DOOR_RANGES_CM)]
        return None, [], bridges, zones, []
    # 走道橫斷橋合併後即失效：疊圖不再畫、恰為門尺寸者的假門位一併移除
    rooms, bridges = _merge_nondoor_bridges(labels, rooms, bridges, det)
    zones = [_bridge_zone(*b) for b in bridges
             if any(lo <= (b[2] - b[1]) * cm <= hi for lo, hi in DOOR_RANGES_CM)
             and _bridge_has_door_ink(det, *b)]  # 迴轉區無墨=開放通道非門
    cc_f = det.get("cc_file")
    if cc_f and cc_cache_valid(cc_f, img_w, img_h,
                               det.get("src_sha256")):
        classify_rooms_cc(det, labels, rooms, cc_f)   # 辨識式房型（方塊切出來投票命名）
    else:                                        # 無（有效）語意快取才退回面積規則
        if cc_f and _cc_ok(cc_f):
            print("⚠ 語意快取來源不符（同名不同圖）→ 視為無快取，房型退回面積規則")
        else:
            print("⚠ 無語意快取 → 房型退回面積規則")
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
    det["cc_file"] = _cc_path(path)
    with open(path, "rb") as f:                  # 快取來源驗證用（cc_cache_valid）
        det["src_sha256"] = hashlib.sha256(f.read()).hexdigest()
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
    write_rooms_json(json_out, det, rooms, zones, edges, is_color, colorful)

    if rooms:
        names = "、".join(f'{r["label_zh"]}{r["area_m2"]}m²' for r in rooms)
        print(f"房間   : {len(rooms)} 間（{names}）  牆端連線 {len(bridges)} 條"
              f"  門位 {len(zones)} 個（75~100/160~190cm）")
    else:
        print("房間   : 分割失敗（殼封不起來）——疊圖仍輸出牆與連線供檢視")
    print(f"輸出   : {png_out}   {door_out}   {json_out}")
    return bool(rooms)


def main():
    p = argparse.ArgumentParser(
        description="平面圖 → 房間方塊（自動判黑白/彩色，調用對應管線，不出 DXF）。\n"
                    "不帶參數 = 批次跑 testdata/png/ 目錄 → chk/room/")
    p.add_argument("input", nargs="?", help="輸入圖檔(單張)或目錄(批次)；預設 png/")
    p.add_argument("output", nargs="?", help="輸出目錄（預設 chk/room/）")
    p.add_argument("--config", default="config.ini", help="黑白管線設定檔")
    p.add_argument("--config-color", default="config_color.ini", help="彩色管線設定檔")
    a = p.parse_args()

    cfg_bw = fp_bw.load_config(a.config)
    cfg_color = fp_c.load_config(a.config_color)
    out_dir = a.output or os.path.join("temp/chk", "room")
    os.makedirs(out_dir, exist_ok=True)

    if a.input and os.path.isfile(a.input):
        ensure_cc_masks([a.input])
        process(a.input, out_dir, cfg_bw, cfg_color)
        return

    in_dir = a.input or "testdata/png"
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
