#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
floorplan2dxf.py — 建築平面圖 PNG → DXF（強制正交：只輸出水平/垂直線）

參數全部寫在 config.ini，執行只要：
    python3 floorplan2dxf.py
指定別的設定檔：
    python3 floorplan2dxf.py 別的.ini

核心：不描輪廓（會歪），改成偵測線條後把每條「建構」成純水平或純垂直，
      H 線兩端共用同一個 y、V 線兩端共用同一個 x，數學上不可能歪。
依賴: pip install opencv-python ezdxf numpy
"""

from __future__ import annotations
import argparse
import configparser
import glob
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, replace

import cv2
import numpy as np
import ezdxf


# ─────────────────────────── 參數 ───────────────────────────
@dataclass
class Config:
    input: str
    output: str
    preview: str | None
    method: str          # morph | hough
    mm_per_px: float
    dpi: float | None
    invert: bool
    blur: int
    thresh: str          # otsu | fixed | adaptive
    thresh_value: int
    adaptive_block: int
    adaptive_c: int
    deskew: bool
    # 以下 px 類參數：None = 依自動量到的牆厚 T 推導(換圖免調)；給值則鎖定
    solid: int | None       # 去細線的開運算核
    style: str              # center=中線 | outline=兩面 | solid=實心牆
    h_len: int | None
    v_len: int | None
    wall_min_pct: float     # 牆厚低於 T 的此 % 者不畫出來
    windows: bool           # 在窗的開口畫窗戶符號
    win_cover_pct: float    # 開口長度被細線覆蓋超過此 % = 窗；其餘是門/空，留開
    win_min_pct: float      # 窗的跨牆寬度需 ≥ 牆厚的(100-此值)%；太薄的不算窗
    door_arc_pct: float     # 門偵測:L形等長線兩端連接弧的吻合度門檻(%)
    door_width_cm: float    # 假設的標準門寬(cm)，用門寬中位數反推每張圖的比例
    # architecture.json(白模交接)用的立面預設值——2D 平面圖量不到,只能用預設
    wall_height_cm: float
    window_height_cm: float
    sill_height_cm: float
    win_layer: str
    hough_thresh: int
    hough_min_len: int
    hough_max_gap: int
    angle_tol: float
    snap: float | None
    gap: float | None
    min_len: float | None
    layer: str


def load_config(path: str) -> Config:
    cp = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    flat = {}
    text = None
    try:
        raw = open(path, "rb").read()
        for enc in ("utf-8-sig", "utf-8", "cp950", "big5", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    except FileNotFoundError:
        text = None
    if text is not None:
        try:
            cp.read_string(text)
            for sec in cp.sections():
                for k, v in cp.items(sec):
                    flat[k.lower()] = v
        except configparser.Error as e:
            print(f"(設定檔解析失敗，改用內建預設值: {e})")
    else:
        print(f"(找不到設定檔 {path}，全部用內建預設值)")

    def s(k, d=None):
        v = flat.get(k)
        return v if v is not None else d

    def i(k, d):
        v = (flat.get(k) or "").strip()
        return int(v) if v else d

    def f(k, d):
        v = (flat.get(k) or "").strip()
        return float(v) if v else d

    def b(k, d):
        v = (flat.get(k) or "").strip().lower()
        return d if v == "" else v in ("1", "true", "yes", "on")

    def io_(k):                              # 可空整數：空 → None(自動)
        v = (flat.get(k) or "").strip()
        return int(v) if v else None

    def fo_(k):                              # 可空浮點
        v = (flat.get(k) or "").strip()
        return float(v) if v else None

    pv = (flat.get("preview") or "").strip()
    dpi = (flat.get("dpi") or "").strip()
    return Config(
        input=s("input"), output=s("output"), preview=(pv or None),
        method=s("method", "morph"),
        mm_per_px=f("mm_per_px", 0.1), dpi=(float(dpi) if dpi else None),
        invert=b("invert", False), blur=i("blur", 0),
        thresh=s("thresh", "otsu"), thresh_value=i("thresh_value", 128),
        adaptive_block=i("adaptive_block", 31), adaptive_c=i("adaptive_c", 5),
        deskew=b("deskew", False),
        solid=io_("solid"), style=s("style", "center"),
        h_len=io_("h_len"), v_len=io_("v_len"),
        wall_min_pct=f("wall_min_pct", 3.0),
        windows=b("windows", True), win_cover_pct=f("win_cover_pct", 70.0),
        win_min_pct=f("win_min_pct", 20.0),
        door_arc_pct=f("door_arc_pct", 50.0),
        door_width_cm=f("door_width_cm", 90.0),
        wall_height_cm=f("wall_height_cm", 280.0),
        window_height_cm=f("window_height_cm", 120.0),
        sill_height_cm=f("sill_height_cm", 90.0),
        win_layer=s("win_layer", "WINDOW"),
        hough_thresh=i("hough_thresh", 50), hough_min_len=i("hough_min_len", 25),
        hough_max_gap=i("hough_max_gap", 5), angle_tol=f("angle_tol", 8.0),
        snap=fo_("snap"), gap=fo_("gap"), min_len=fo_("min_len"),
        layer=s("layer", "WALL"),
    )


# ─────────────────────────── 前處理 ───────────────────────────
def load_gray(cfg: Config):
    img = cv2.imread(cfg.input, cv2.IMREAD_UNCHANGED)
    if img is None:
        sys.exit(f"讀不到圖: {cfg.input}")
    if img.ndim == 2:
        gray, bgr = img, cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        bgr = cv2.merge([b, g, r])
        white = np.full_like(bgr, 255)
        am = a.astype(np.float32) / 255
        bgr = (bgr * am[..., None] + white * (1 - am[..., None])).astype(np.uint8)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray, bgr = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), img
    return gray, bgr


def deskew(gray):
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return gray, 0.0
    angs = [math.degrees(t) - 90 for _, t in lines[:, 0] if -20 < math.degrees(t) - 90 < 20]
    if not angs:
        return gray, 0.0
    a = float(np.median(angs))
    h, w = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255), a


def binarize(gray, cfg: Config):
    if cfg.blur >= 3:
        k = cfg.blur | 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)
    if cfg.thresh == "otsu":
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    elif cfg.thresh == "fixed":
        _, bw = cv2.threshold(gray, cfg.thresh_value, 255, cv2.THRESH_BINARY_INV)
    elif cfg.thresh == "adaptive":
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, cfg.adaptive_block | 1, cfg.adaptive_c)
    else:
        sys.exit(f"未知 thresh: {cfg.thresh}")
    if cfg.invert:
        bw = cv2.bitwise_not(bw)
    return bw


# ─────────────────────────── 偵測 ───────────────────────────
# H = [y, x0, x1]（x0<x1）； V = [x, y0, y1]（y0<y1）
def detect_morph(bw, cfg: Config):
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (cfg.h_len, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, cfg.v_len))
    h_img = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)
    v_img = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)

    H, V = [], []
    n, _, st, _ = cv2.connectedComponentsWithStats(h_img, 8)
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if cfg.style == "outline":
            H.append([float(y), float(x), float(x + w - 1)])
            H.append([float(y + h - 1), float(x), float(x + w - 1)])
        else:
            H.append([y + (h - 1) / 2.0, float(x), float(x + w - 1)])
    n, _, st, _ = cv2.connectedComponentsWithStats(v_img, 8)
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if cfg.style == "outline":
            V.append([float(x), float(y), float(y + h - 1)])
            V.append([float(x + w - 1), float(y), float(y + h - 1)])
        else:
            V.append([x + (w - 1) / 2.0, float(y), float(y + h - 1)])
    return H, V


def detect_hough(bw, cfg: Config):
    lines = cv2.HoughLinesP(bw, 1, np.pi / 180, cfg.hough_thresh,
                            minLineLength=cfg.hough_min_len, maxLineGap=cfg.hough_max_gap)
    H, V, dropped = [], [], 0
    if lines is None:
        return H, V
    tol = math.radians(cfg.angle_tol)
    for x1, y1, x2, y2 in lines[:, 0]:
        dx, dy = abs(int(x2) - int(x1)), abs(int(y2) - int(y1))
        if dx >= dy:
            if math.atan2(dy, max(dx, 1)) <= tol:
                H.append([(y1 + y2) / 2.0, float(min(x1, x2)), float(max(x1, x2))])
            else:
                dropped += 1
        else:
            if math.atan2(dx, max(dy, 1)) <= tol:
                V.append([(x1 + x2) / 2.0, float(min(y1, y2)), float(max(y1, y2))])
            else:
                dropped += 1
    if dropped:
        print(f"  (丟棄 {dropped} 條斜線)")
    return H, V


def detect_solid(bw, cfg: Config, T: int):
    """抓 H/V 牆塊的 bbox，回傳矩形清單 [(x0,y0,x1,y1)]。直角矩形 → 實心牆，不可能歪。"""
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (cfg.h_len, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, cfg.v_len))
    thick_floor = (cfg.wall_min_pct / 100.0) * T     # 低於牆厚此 % 的厚度不算牆
    rects = []
    for img in (cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk),
                cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)):
        n, _, st, _ = cv2.connectedComponentsWithStats(img, 8)
        for i in range(1, n):
            x, y, w, h, _ = st[i]
            if max(w, h) < cfg.min_len:          # 太短的丟掉
                continue
            if min(w, h) < thick_floor:          # 太薄的丟掉(低於牆厚%)
                continue
            rects.append((float(x), float(y), float(x + w), float(y + h)))
    return rects


def _arc_run(thin, cx, cy, r, ux, vx, uy, vy):
    """以(cx,cy)為圓心、半徑 r，從(ux,uy)方向掃到(vx,vy)方向的 90 度弧，
    回傳弧上連續有墨跡的最長比例(0~1)。用來驗證『門的開闔動線』存在。"""
    Himg, Wimg = thin.shape
    hits = []
    for deg in range(5, 86, 3):
        th = math.radians(deg)
        px = int(cx + r * (math.cos(th) * ux + math.sin(th) * vx))
        py = int(cy + r * (math.cos(th) * uy + math.sin(th) * vy))
        tol = max(2, int(r * 0.07))
        xa, xb = max(0, px - tol), min(Wimg, px + tol + 1)
        ya, yb = max(0, py - tol), min(Himg, py + tol + 1)
        hits.append(1 if (xa < xb and ya < yb and thin[ya:yb, xa:xb].any()) else 0)
    run = mx = 0
    for h in hits:
        run = run + 1 if h else 0
        mx = max(mx, run)
    return mx / len(hits)


def _arc_crisp(thin, cx, cy, r, ux, vx, uy, vy):
    """弧中段(25°~65°)的墨要「貼在半徑上」：r 有墨、r±max(5,0.2r) 留白的樣本佔比夠高
    → 孤立細曲線(真門弧)。牆緣蝕刻殘影/家具墨團拼出的假弧內外圈也有墨 → 不算門，
    避免誤殺剛好被雜墨圈住的窗。"""
    Himg, Wimg = thin.shape

    def ink(rr, th):
        px = int(cx + rr * (math.cos(th) * ux + math.sin(th) * vx))
        py = int(cy + rr * (math.cos(th) * uy + math.sin(th) * vy))
        tol = max(2, int(r * 0.05))
        xa, xb = max(0, px - tol), min(Wimg, px + tol + 1)
        ya, yb = max(0, py - tol), min(Himg, py + tol + 1)
        return bool(xa < xb and ya < yb and thin[ya:yb, xa:xb].any())

    d = max(5.0, 0.2 * r)
    hits = clear = 0
    for deg in range(25, 66, 5):
        th = math.radians(deg)
        if ink(r, th):
            hits += 1
            if not ink(r - d, th) and not ink(r + d, th):
                clear += 1
    return hits >= 5 and clear / hits >= 0.6


def _has_door_swing(thin, orient, c, a, b, T, arc_pct, wall_t=None, cross_t=None,
                    allow_half=True):
    """備援門檢查：門扇畫成閉合狀態(細線橫躺在牆線上)時 detect_doors 的 L 形規則抓不到，
    會被誤認成窗。改拿開口兩端當鉸鏈，直接掃有沒有半徑=開口寬的 90 度弧(開闔動線)。
    orient/c = 牆線方向與中心座標，a~b = 開口在沿牆軸上的範圍。
    門尺寸基準 s 用可靠牆厚 wall_t 推(全圖最厚線 T 會被樓梯/實心塊撐大 2~3 倍,
    把正常寬度的門排除在檢查外——floor13/34/35 的閉合門扇全因此漏抓)。
    鉸鏈除了開口兩端,再試 c±cross_t/2(門軸釘在牆面,不在牆中線)；
    半徑除了開口寬,再試 1.2 倍(蝕刻讓開口比門寬窄)。
    門檻鎖 0.9(比 door_arc_pct 嚴)且弧要通過 _arc_crisp 孤立性檢查，不誤殺窗。
    allow_half=True 時寬開口(≥4s)再試「一端鉸鏈+半寬弧」= 門+固定扇共用開口；
    呼叫端在開口畫滿玻璃線(≥2 條貫穿線)時應傳 False,免得殺掉寬窗。"""
    gap = b - a
    s = float(min(T, max(1.6 * (wall_t or T), 0.6 * T)))   # 門尺寸基準
    if not (1.5 * s <= gap <= 16.0 * s):     # 尺寸不像門就不檢查，避免誤殺長窗
        return False
    thr = max(0.9, arc_pct / 100.0)
    perp = [0.0]
    if cross_t:
        perp += [-cross_t / 2.0, cross_t / 2.0]

    def hinge_arc(end, r):
        leaf = 1 if end == a else -1         # 門扇閉合時沿開口指向另一端
        for off in (0.0, -0.25 * s, 0.25 * s, -0.5 * s, 0.5 * s, 1.0 * s):
            hinge = end - leaf * off         # 鉸鏈與蝕刻後的開口端可能有小錯位(內外皆可能)
            radii = [r, 1.2 * r]
            if off > 0:
                radii.append(r + off)        # 外移時門寬可能連著一起變大
            for rr in radii:
                for pc in perp:              # 門軸可能在牆中線或兩側牆面
                    for side in (1, -1):     # 房間可能在牆的任一側
                        if orient == "v":
                            args = (c + pc, hinge, rr, 0, side, leaf, 0)
                        else:
                            args = (hinge, c + pc, rr, leaf, 0, 0, side)
                        if _arc_run(thin, *args) >= thr and _arc_crisp(thin, *args):
                            return True
        return False

    if 1.2 * s <= gap <= 16.0 * s and (hinge_arc(a, gap) or hinge_arc(b, gap)):
        return True                          # 單扇門：一端鉸鏈 + 全寬弧
    half = gap / 2.0
    if half >= 1.2 * s:
        if hinge_arc(a, half) and hinge_arc(b, half):
            return True                      # 雙開門：兩端鉸鏈 + 各自的半寬弧
        if allow_half and gap >= 4.0 * s and (hinge_arc(a, half) or hinge_arc(b, half)):
            return True                      # 寬開口的門+固定扇：一端鉸鏈 + 半寬弧
    return False


def detect_doors(thin, T: int, arc_pct: float):
    """依規則找門:一條垂直線 + 一條水平線(等長、垂直、共用一個角=鉸鏈)，
    兩自由端用半徑=門寬的弧連接(門的開闔動線)。
    回傳 [(cx, cy, width, score, ux, vy)]:鉸鏈、門寬、弧吻合度、
    水平/垂直線自由端相對鉸鏈的方向(±1，影像座標)——architecture.json 判開門側用。
    用 HoughLinesP 找實際線段，不靠假設，圓形家具沒有這對等長直線→不會中。"""
    segs = cv2.HoughLinesP(thin, 1, np.pi / 180, threshold=max(15, int(0.9 * T)),
                           minLineLength=int(1.2 * T), maxLineGap=int(0.4 * T))
    if segs is None:
        return []
    Hs, Vs = [], []
    for x1, y1, x2, y2 in segs[:, 0]:
        ln = math.hypot(x2 - x1, y2 - y1)
        ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
        if ang < 12 or ang > 168:
            Hs.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2.0, ln))
        elif 78 < ang < 102:
            Vs.append(((x1 + x2) / 2.0, min(y1, y2), max(y1, y2), ln))

    def arc_run(cx, cy, r, ux, vx, uy, vy):
        return _arc_run(thin, cx, cy, r, ux, vx, uy, vy)

    doors = []
    thr = arc_pct / 100.0
    for hx0, hx1, hy, hl in Hs:
        for vx, vy0, vy1, vl in Vs:
            if abs(hl - vl) > 0.35 * max(hl, vl):        # 兩線必須等長(=門寬)
                continue
            for hx in (hx0, hx1):
                for vy in (vy0, vy1):
                    if abs(hx - vx) <= T * 0.6 and abs(hy - vy) <= T * 0.6:  # 共用角(鉸鏈)
                        cx, cy = (hx + vx) / 2.0, (hy + vy) / 2.0
                        hfx = hx1 if hx == hx0 else hx0
                        vfy = vy1 if vy == vy0 else vy0
                        ux = (hfx - cx); ux = ux / (abs(ux) or 1)
                        vy_ = (vfy - cy); vy_ = vy_ / (abs(vy_) or 1)
                        r = (hl + vl) / 2.0
                        score = arc_run(cx, cy, r, ux, 0, 0, vy_)
                        if score >= thr:
                            doors.append((cx, cy, r, score, ux, vy_))
    uniq = []
    for d in sorted(doors, key=lambda d: -d[3]):
        if not any(math.hypot(d[0] - u[0], d[1] - u[1]) < T for u in uniq):
            uniq.append(d)
    return uniq


def _near_door(cx, cy, gap, doors, ends=None, T=0, tol_side=0.0):
    """開口是否對應到一扇偵測到的門：鉸鏈必須貼在開口其中一端(不能只是在附近，
    免得窗戶旁邊剛好有門/假門就整個被誤殺)，且門寬要與開口寬相符。
    只信弧線吻合度高的門(≥0.8)——家具/淋浴間的曲線拼出來的假門分數較低，不拿來殺窗。
    門寬下限 0.55×開口(門常與固定扇共用開口，弧比開口窄)。
    ends 前兩點=開口端點(容差寬)，其後=帶側面中點(容差 0.5×tol_side——
    門橫著閂在開口上時門軸幾乎貼著帶緣，離遠的一律不採信免得誤殺窗)。"""
    for dx, dy, dw, score, *_ in doors:
        if score < 0.8 or not (0.55 * gap <= dw <= 1.4 * gap):
            continue
        if ends is not None:
            tol = max(float(T), 0.15 * gap)
            for i, (ex, ey) in enumerate(ends):
                t_i = tol if i < 2 else max(3.0, 0.5 * tol_side)
                if math.hypot(dx - ex, dy - ey) <= t_i:
                    return True
        elif math.hypot(dx - cx, dy - cy) <= 1.1 * gap:
            return True
    return False


def detect_windows(orig_bw, rects, cfg: Config, T: int, doors=None, thin=None, soft=None):
    """在牆的開口偵測窗:開口長度被細線高度覆蓋=窗(玻璃線沿牆跨整段)；
    空的=門/通道，留開；落在偵測到的門附近=門，留開。回傳 [(orient, x0, y0, x1, y1)]。
    soft = 寬鬆二值化(灰<200)。玻璃線畫成淺灰時 Otsu 會把它消掉，開口在 orig_bw 上
    看起來是空的；此時改用 soft 重測，但要求至少一條線貫穿開口全長(擋掉文字/雜訊)。"""
    doors = doors or []
    Himg, Wimg = orig_bw.shape
    thr = cfg.win_cover_pct / 100.0

    def line_groups(band, along_axis, cov=0.8):
        """數 band 裡「貫穿開口全長的線」有幾群(相鄰的滿版列/行算同一條線)。"""
        line_cov = (band > 0).mean(axis=along_axis)
        groups = prev = 0
        for v in line_cov:
            cur = v >= cov
            if cur and not prev:
                groups += 1
            prev = cur
        return groups

    def covered(band, along_axis):
        """開口有沒有被玻璃線覆蓋：cover 過門檻，且線的結構要像窗——
        兩群以上分開的貫穿線(玻璃畫法)；或一條貫穿線＋其他部分覆蓋的線(梳齒窗的
        邊框+齒)。推拉門(兩片各半、無貫穿線)和門檻線(孤零零一條)都不像 → 擋掉。"""
        if not band.size or (band.max(axis=1 - along_axis) > 0).mean() < thr:
            return False
        groups = line_groups(band, along_axis)
        if groups >= 2:
            return True
        if groups == 0:
            return False
        line_cov = (band > 0).mean(axis=along_axis)
        partial = int(((line_cov >= 0.15) & (line_cov < 0.8)).sum())
        return partial >= 2

    def covered_soft(y0, y1, x0, x1, along_axis, edge_hug=False, min_groups=2):
        """orig 上是空的 → 用寬鬆二值化重測。要長得像窗才放行：
        至少 min_groups「群」分開的線貫穿開口全長(一群=一條實線；單條=家具/檯面邊線)，
        且整塊墨跡比例不能太高(樓梯踏板/斜線填充整片都是墨，玻璃線之間應留白)。
        edge_hug=True 再要求最外側兩條線貼著牆帶兩緣(窗符號的線畫在牆的兩個面上；
        浴缸邊/家具線只會出現在牆帶中間)。"""
        if soft is None:
            return False
        band = soft[max(0, y0):min(Himg, y1), max(0, x0):min(Wimg, x1)]
        if not band.size or (band.max(axis=1 - along_axis) > 0).mean() < thr:
            return False
        if (band > 0).mean() > 0.45:
            return False
        if line_groups(band, along_axis) < min_groups:
            return False
        if edge_hug:
            line_cov = (band > 0).mean(axis=along_axis)
            n = len(line_cov)
            idx = [i for i, v in enumerate(line_cov) if v >= 0.8]
            # 帶被影像邊界裁到時窗符號的外緣線會缺/位移，貼緣門檻放寬
            if along_axis == 1:
                clipped = y0 <= 0 or y1 >= Himg
            else:
                clipped = x0 <= 0 or x1 >= Wimg
            lo_r, hi_r = (0.42, 0.58) if clipped else (0.3, 0.7)
            if not idx or idx[0] > lo_r * n or idx[-1] < hi_r * n:
                return False
        return True
    long_th = [min(r[2] - r[0], r[3] - r[1]) for r in rects
               if max(r[2] - r[0], r[3] - r[1]) >= 2 * T]      # 只取夠長的真牆
    all_th = [min(r[2] - r[0], r[3] - r[1]) for r in rects]
    src = long_th if long_th else all_th
    wall_t = float(np.median(src)) if src else float(T)        # 代表性牆厚
    min_w = (1.0 - cfg.win_min_pct / 100.0) * wall_t           # 窗跨牆寬度下限
    gmin, gmax = 0.4 * T, 25.0 * T
    horiz = [r for r in rects if (r[2] - r[0]) >= (r[3] - r[1])]
    vert = [r for r in rects if (r[2] - r[0]) < (r[3] - r[1])]
    wins = []

    def group(rs, key):                      # 把同一條線上的牆段分群
        g = []
        for r in sorted(rs, key=key):
            c = key(r)
            if g and abs(c - g[-1][0]) <= T * 0.7:
                g[-1][1].append(r)
            else:
                g.append([c, [r]])
        return g

    def sub_window(orient, band_lo, band_hi, g_lo, g_hi, min_groups=2):
        """整個開口的覆蓋率不夠時，找其中「有線的連續子段」：窗常跟門洞共用同一個
        開口(中間的牆垛被蝕刻掉)，有線的那段是窗、全空的那段留開。回傳 (s0, s1) 或 None。"""
        if soft is None:
            return None
        def profile(img):
            if orient == "h":
                bd = img[max(0, int(band_lo)):min(Himg, int(band_hi)), max(0, int(g_lo)):min(Wimg, int(g_hi))]
                return (bd.max(axis=0) > 0) if bd.size else None
            bd = img[max(0, int(g_lo)):min(Himg, int(g_hi)), max(0, int(band_lo)):min(Wimg, int(band_hi))]
            return (bd.max(axis=1) > 0) if bd.size else None

        def find_runs(prof):                 # 找允許小斷點(毛邊)的覆蓋連續段
            runs, i = [], 0
            tol = max(2, int(round(0.15 * T)))
            while i < len(prof):
                if not prof[i]:
                    i += 1
                    continue
                j, miss = i, 0
                for k in range(i, len(prof)):
                    if prof[k]:
                        j, miss = k, 0
                    else:
                        miss += 1
                        if miss > tol:
                            break
                runs.append((i, j + 1))
                i = j + 1 + tol + 1
            return runs

        # 先用一般二值化找段(斜線填充/淺灰裝飾在這裡常是斷續的,能把窗跟它切開)，
        # 一般二值化上空空如也(淺灰玻璃線)才用寬鬆二值化。
        runs = []
        p_orig = profile(orig_bw)
        if p_orig is not None and p_orig.any():
            runs += find_runs(p_orig)
        p_soft = profile(soft)
        if p_soft is not None and p_soft.any():
            runs += [r for r in find_runs(p_soft) if r not in runs]

        def profile2(img):                   # 每行(列)至少 2 條線才算窗符號區——
            if orient == "h":                # 閉合門扇/家具的單條線把 runs 橋成一整段
                bd = img[max(0, int(band_lo)):min(Himg, int(band_hi)),
                         max(0, int(g_lo)):min(Wimg, int(g_hi))]
                return ((bd > 0).sum(axis=0) >= 2) if bd.size else None
            bd = img[max(0, int(g_lo)):min(Himg, int(g_hi)),
                     max(0, int(band_lo)):min(Wimg, int(band_hi))]
            return ((bd > 0).sum(axis=1) >= 2) if bd.size else None

        for img_ in (orig_bw, soft):
            p2 = profile2(img_)
            if p2 is not None and p2.any():
                runs += [r for r in find_runs(p2) if r not in runs]
        if not runs:
            return None
        def anchor_count(p0, p1):
            """數子段兩端外側有幾端貼著實心墨(牆垛)。窗至少一端貼牆垛(另一端可能直接
            連門洞)；隔屏/家具(沙發)的線末端是自由端或小端蓋,兩端都沒實牆。"""
            d = max(3, int(round(0.8 * T)))
            n = 0
            for lo, hi in ((p0 - d, p0), (p1, p1 + d)):
                if orient == "h":
                    blk = orig_bw[max(0, int(band_lo)):min(Himg, int(band_hi)),
                                  max(0, lo):min(Wimg, hi)]
                else:
                    blk = orig_bw[max(0, lo):min(Himg, hi),
                                  max(0, int(band_lo)):min(Wimg, int(band_hi))]
                if blk.size and (blk > 0).mean() >= 0.3:
                    n += 1
            return n

        for s in sorted(runs, key=lambda r: r[0] - r[1]):    # 由長到短試每個連續段
            s0, s1 = int(g_lo) + s[0], int(g_lo) + s[1]
            if (s1 - s0) < max(gmin, 1.5 * T):
                continue                     # 太短不算
            anc = anchor_count(s0, s1)
            if anc < 1:
                continue
            # 幾乎佔滿整段就不是「子段」情況——但兩端都貼牆垛時是真的小開口窗,放行
            if (s1 - s0) >= (0.98 if anc >= 2 else 0.9) * (g_hi - g_lo):
                continue
            # 子段用「貼緣」結構把關：窗線畫在牆的兩個面上(貼牆帶兩緣)，
            # 隔屏/沙發比牆薄,線落在帶中間 → 擋掉
            if orient == "h":
                ok = covered_soft(int(band_lo), int(band_hi), s0, s1, 1,
                                  edge_hug=True, min_groups=min_groups)
            else:
                ok = covered_soft(s0, s1, int(band_lo), int(band_hi), 0,
                                  edge_hug=True, min_groups=min_groups)
            if ok:
                return (s0, s1)
        return None

    def wall_through(orient, x0, y0, x1, y1):
        """開口中段是否被垂直向的牆穿過/抵住(T字口)——窗玻璃不可能有牆插在中間，
        這種開口是被跨線牆分成兩截的門洞/通道，交給 scan_extra 用虛擬夾邊分段
        重測，這裡整段否決。只看跨進開口內側(避開兩端夾牆)的牆。"""
        if orient == "h":
            lo, hi = x0, x1
            m = max(0.12 * (hi - lo), T * 0.3)
            for r in vert:
                if min(r[2], x1) - max(r[0], x0) > 0 and \
                        r[1] < (y0 + y1) / 2.0 < r[3] and \
                        lo + m < (r[0] + r[2]) / 2.0 < hi - m:
                    return True
        else:
            lo, hi = y0, y1
            m = max(0.12 * (hi - lo), T * 0.3)
            for r in horiz:
                if min(r[3], y1) - max(r[1], y0) > 0 and \
                        r[0] < (x0 + x1) / 2.0 < r[2] and \
                        lo + m < (r[1] + r[3]) / 2.0 < hi - m:
                    return True
        return False

    def try_window(orient, x0, y0, x1, y1, groups=None):
        """開口通過覆蓋/結構檢查後的最後一關：門過濾(原則3——有弧就是門)。過了就收錄。
        groups=開口帶的貫穿線群數：≥2(窗符號)時不啟用「半寬單鉸鏈弧」殺法——
        那是給 門+固定扇(帶內只有一條門扇線) 用的,不能拿來殺畫滿玻璃線的寬窗。"""
        cx_, cy_ = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if orient == "h":
            g0, g1, c_ = x0, x1, cy_
            ends = ((x0, c_), (x1, c_), (cx_, y0), (cx_, y1))
            ct = y1 - y0
        else:
            g0, g1, c_ = y0, y1, cx_
            ends = ((c_, y0), (c_, y1), (x0, cy_), (x1, cy_))
            ct = x1 - x0
        if wall_through(orient, x0, y0, x1, y1):
            return                           # 牆插在開口中段 → 不是窗
        if _near_door(cx_, cy_, g1 - g0, doors, ends, T, tol_side=wall_t):
            return                           # 開口處是門(鉸鏈貼端點/側面中點) → 留開
        if thin is not None and _has_door_swing(thin, orient, c_, g0, g1, T,
                                                cfg.door_arc_pct, wall_t, ct,
                                                allow_half=(groups is None or groups <= 1)):
            return                           # 端點掃到開闔弧線 → 門，不是窗
        wins.append((orient, float(x0), float(y0), float(x1), float(y1)))

    for _, grp in group(horiz, lambda r: (r[1] + r[3]) / 2):
        grp.sort(key=lambda r: r[0])
        for a, b in zip(grp, grp[1:]):
            gap = b[0] - a[2]
            if gap < gmin or gap > gmax:
                continue
            x0, x1 = int(a[2]), int(b[0])
            y0, y1 = int(min(a[1], b[1])), int(max(a[3], b[3]))
            if (y1 - y0) < min_w:            # 跨牆寬度太薄 → 不是窗
                continue
            pad = max(2, int(round(0.25 * T)))   # 窗符號比蝕刻後的牆塊略寬,帶朝兩側擴一點
            band = orig_bw[max(0, y0 - pad):min(Himg, y1 + pad), max(0, x0):min(Wimg, x1)]
            if covered(band, 1) or covered_soft(y0 - pad, y1 + pad, x0, x1, 1):
                try_window("h", x0, y0, x1, y1, groups=line_groups(band, 1))
            elif not (band.size and (band.max(axis=0) > 0).mean() >= thr):
                # 整段覆蓋率真的低(有大片空白)才找子段；覆蓋高但結構不像窗=推拉門/門檻,直接擋
                s = sub_window("h", y0 - pad, y1 + pad, x0, x1)
                if s:                        # 開口只有一部分有線 → 那段是窗,其餘留開
                    try_window("h", s[0], y0, s[1], y1)

    for _, grp in group(vert, lambda r: (r[0] + r[2]) / 2):
        grp.sort(key=lambda r: r[1])
        for a, b in zip(grp, grp[1:]):
            gap = b[1] - a[3]
            if gap < gmin or gap > gmax:
                continue
            y0, y1 = int(a[3]), int(b[1])
            x0, x1 = int(min(a[0], b[0])), int(max(a[2], b[2]))
            if (x1 - x0) < min_w:            # 跨牆寬度太薄 → 不是窗
                continue
            pad = max(2, int(round(0.25 * T)))   # 窗符號比蝕刻後的牆塊略寬,帶朝兩側擴一點
            band = orig_bw[max(0, y0):min(Himg, y1), max(0, x0 - pad):min(Wimg, x1 + pad)]
            if covered(band, 0) or covered_soft(y0, y1, x0 - pad, x1 + pad, 0):
                try_window("v", x0, y0, x1, y1, groups=line_groups(band, 0))
            elif not (band.size and (band.max(axis=1) > 0).mean() >= thr):
                # 整段覆蓋率真的低(有大片空白)才找子段；覆蓋高但結構不像窗=推拉門/門檻,直接擋
                s = sub_window("v", x0 - pad, x1 + pad, y0, y1)
                if s:                        # 開口只有一部分有線 → 那段是窗,其餘留開
                    try_window("v", x0, s[0], x1, s[1])

    # ── 補找「牆段跟垂直牆之間」與「整條被抹除的牆線上」的窗 ──
    # 細線畫的窗(甚至整條細線牆)會被 solid 開運算抹光，上面的成對牆段邏輯拿它沒轍：
    # 夾邊改用「跨過牆線的垂直牆」補足，牆線本身沒牆塊時用兩個對齊的垂直牆端點推斷。
    # 這些開口一律用最嚴格的 covered_soft(≥2 群貫穿線 + 墨跡比例)把關。
    def strict_window(orient, c, t, g_lo, g_hi):
        gap = g_hi - g_lo
        if gap < gmin or gap > gmax or t < min_w:
            return None
        pad = max(2, int(round(0.25 * T)))
        b_lo0, b_hi0 = int(round(c - t / 2)), int(round(c + t / 2))
        dim = Himg if orient == "h" else Wimg
        clipped = b_lo0 - pad <= 0 or b_hi0 + pad >= dim
        # 原帶要求 2 條貫穿線(邊窗放寬已含在 covered_soft)；加寬帶會撈進鄰近雜線，
        # 提高到 3 條(真窗符號 3~4 條;衣櫃門板/雙線畫法的牆端只有 2 條)。
        # 帶被影像邊裁到時窗線本來就會缺,加寬帶維持 2 條。
        bands = [(b_lo0, b_hi0, 2), (b_lo0 - pad, b_hi0 + pad, 2 if clipped else 3)]

        def gates(lo, hi):                   # 開口(lo,hi)通過門檢查則回傳成品框
            if orient == "h":
                x0, x1 = int(lo), int(hi)
                y0, y1 = b_lo0, b_hi0
                ends = ((x0, c), (x1, c), ((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1))
            else:
                y0, y1 = int(lo), int(hi)
                x0, x1 = b_lo0, b_hi0
                ends = ((c, y0), (c, y1), (x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0))
            if _near_door((x0 + x1) / 2.0, (y0 + y1) / 2.0, hi - lo, doors, ends, T,
                          tol_side=wall_t):
                return None
            if thin is not None and _has_door_swing(thin, orient, c, lo, hi, T,
                                                    cfg.door_arc_pct, wall_t, t,
                                                    allow_half=False):
                return None
            return (orient, float(max(0, x0)), float(max(0, y0)),
                    float(min(Wimg, x1)), float(min(Himg, y1)))

        for b_lo, b_hi, mg in bands:
            if orient == "h":
                full = covered_soft(b_lo, b_hi, int(g_lo), int(g_hi), 1,
                                    edge_hug=True, min_groups=mg)
            else:
                full = covered_soft(int(g_lo), int(g_hi), b_lo, b_hi, 0,
                                    edge_hug=True, min_groups=mg)
            if full:
                return gates(g_lo, g_hi)
        for b_lo, b_hi, _mg in bands:
            s = sub_window(orient, b_lo, b_hi, g_lo, g_hi, min_groups=3)
            if s:                            # 大開口裡只有一段有窗符號 → 收那段
                return gates(s[0], s[1])
        return None

    def crossing_spans(orient, c, perp):
        """跨過牆線 c 的垂直牆，投影到沿牆軸上的區間(虛擬夾邊)。"""
        out = []
        for r in perp:
            if orient == "h" and r[1] - T * 0.5 <= c <= r[3] + T * 0.5:
                out.append((r[0], r[2]))
            elif orient == "v" and r[0] - T * 0.5 <= c <= r[2] + T * 0.5:
                out.append((r[1], r[3]))
        return out

    def scan_extra(orient, c, t, real_spans, perp):
        """real_spans=線上實體牆段區間；補上虛擬夾邊後，只測「靠著虛擬夾邊」的新開口。"""
        flanks = [(s[0], s[1], False) for s in real_spans] + \
                 [(s[0], s[1], True) for s in crossing_spans(orient, c, perp)]
        flanks.sort()
        merged = []
        for lo, hi, virt in flanks:
            if merged and lo <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], hi)
                merged[-1][2] = merged[-1][2] or virt
            else:
                merged.append([lo, hi, virt])
        for a, b in zip(merged, merged[1:]):
            if not (a[2] or b[2]):
                continue                     # 兩邊都是實體牆段 → 上面已測過
            w = strict_window(orient, c, t, a[1], b[0])
            if w:
                wins.append(w)

    h_groups = [(np.mean([(r[1] + r[3]) / 2 for r in grp]),
                 float(np.median([r[3] - r[1] for r in grp])),
                 [(r[0], r[2]) for r in grp])
                for _, grp in group(horiz, lambda r: (r[1] + r[3]) / 2)]
    v_groups = [(np.mean([(r[0] + r[2]) / 2 for r in grp]),
                 float(np.median([r[2] - r[0] for r in grp])),
                 [(r[1], r[3]) for r in grp])
                for _, grp in group(vert, lambda r: (r[0] + r[2]) / 2)]

    for c, t, spans in h_groups:
        scan_extra("h", c, t, spans, vert)
    for c, t, spans in v_groups:
        scan_extra("v", c, t, spans, horiz)

    h_centers = [g[0] for g in h_groups]
    v_centers = [g[0] for g in v_groups]
    for orient, c, lo, hi in _infer_lines(horiz, vert, T):
        known = h_centers if orient == "h" else v_centers
        if any(abs(c - k) <= max(wall_t, 0.45 * T) * 0.9 for k in known):
            continue                         # 這條線已有實體牆塊，上面掃過了(容差用可靠
                                             # 牆厚:T 被實心塊撐大時會把貼邊的細線牆吃掉)
        c = min(max(c, wall_t / 2), (Himg if orient == "h" else Wimg) - wall_t / 2)
        scan_extra(orient, c, wall_t, [], vert if orient == "h" else horiz)

    # 去重(不同來源可能疊到同一個開口)
    uniq = []
    for w in wins:
        dup = False
        for u in uniq:
            if u[0] == w[0] and not (w[3] <= u[1] or w[1] >= u[3] or w[4] <= u[2] or w[2] >= u[4]):
                dup = True
                break
        if not dup:
            uniq.append(w)
    return uniq


def _infer_lines(horiz, vert, T):
    """找「兩個垂直牆端點對齊、但那條線上沒有任何牆塊」的候選牆線 [(orient, c, lo, hi)]。
    整條用細線畫的牆(如圖框邊的窗牆)會被 solid 開運算抹光，只能這樣推斷回來。"""
    tol = T * 0.8
    found = []
    v_ends = [((r[0] + r[2]) / 2, y) for r in vert for y in (r[1], r[3])]
    for i in range(len(v_ends)):
        for j in range(i + 1, len(v_ends)):
            (xa, ya), (xb, yb) = v_ends[i], v_ends[j]
            if abs(ya - yb) <= tol and abs(xa - xb) > 2 * T:
                lo, hi = sorted([xa, xb])
                found.append(("h", (ya + yb) / 2, lo, hi))
    h_ends = [(x, (r[1] + r[3]) / 2) for r in horiz for x in (r[0], r[2])]
    for i in range(len(h_ends)):
        for j in range(i + 1, len(h_ends)):
            (xa, ya), (xb, yb) = h_ends[i], h_ends[j]
            if abs(xa - xb) <= tol and abs(ya - yb) > 2 * T:
                lo, hi = sorted([ya, yb])
                found.append(("v", (xa + xb) / 2, lo, hi))
    return found


# ─────────────────────────── 後處理 ───────────────────────────
def cluster_const(segs, tol):
    if not segs:
        return [], []
    segs = sorted(segs, key=lambda s: s[0])
    groups, cur = [], [segs[0]]
    for s in segs[1:]:
        if s[0] - cur[-1][0] <= tol:
            cur.append(s)
        else:
            groups.append(cur)
            cur = [s]
    groups.append(cur)
    out, centers = [], []
    for grp in groups:
        wsum = sum((s[2] - s[1]) + 1 for s in grp)
        c = sum(s[0] * ((s[2] - s[1]) + 1) for s in grp) / max(wsum, 1)
        centers.append(c)
        for s in grp:
            out.append([c, s[1], s[2]])
    return out, centers


def merge_spans(segs, gap):
    groups = defaultdict(list)
    for c, a, b in segs:
        groups[c].append((a, b))
    out = []
    for c, spans in groups.items():
        spans.sort()
        ca, cb = spans[0]
        for a, b in spans[1:]:
            if a <= cb + gap:
                cb = max(cb, b)
            else:
                out.append([c, ca, cb])
                ca, cb = a, b
        out.append([c, ca, cb])
    return out


def nearest(v, centers, tol):
    if not centers:
        return v
    c = min(centers, key=lambda x: abs(x - v))
    return c if abs(c - v) <= tol else v


def snap_ends(segs, perp_centers, tol):
    for s in segs:
        s[1] = nearest(s[1], perp_centers, tol)
        s[2] = nearest(s[2], perp_centers, tol)
    return segs


def postprocess(H, V, cfg: Config):
    H, yc = cluster_const(H, cfg.snap)
    V, xc = cluster_const(V, cfg.snap)
    H = merge_spans(H, cfg.gap)
    V = merge_spans(V, cfg.gap)
    H = snap_ends(H, xc, cfg.snap)
    V = snap_ends(V, yc, cfg.snap)
    H = merge_spans(H, cfg.gap)
    V = merge_spans(V, cfg.gap)
    H = [s for s in H if (s[2] - s[1]) >= cfg.min_len]
    V = [s for s in V if (s[2] - s[1]) >= cfg.min_len]
    return H, V


# ─────────────────────────── 比例尺(門寬推算) ───────────────────────────
WALL_MIN_CM = 15.0                               # 外圍牆厚下限：周界牆一定 ≥ 15cm
WALL_MAX_CM = 40.0


def outer_wall_thickness(rects, T):
    """外圍牆厚(px)：取「貼著全圖外框、且沿外框方向延伸」的牆矩形短邊中位數。
    比 T(全圖最厚線)可靠——T 會被室內厚牆/樓梯等實心塊撐大，不代表外牆。
    只算沿邊延伸的牆段，避免把端點碰到外框的室內牆(可以比 15cm 薄)算進來。"""
    if not rects:
        return float(T)
    X0 = min(r[0] for r in rects); Y0 = min(r[1] for r in rects)
    X1 = max(r[2] for r in rects); Y1 = max(r[3] for r in rects)
    tol = max(3.0, 0.5 * T)
    t_min = max(3.0, 0.35 * T)                   # 太細的長條是標註/尺寸線，不是牆
    th = []
    for x0, y0, x1, y1 in rects:
        w, h = x1 - x0, y1 - y0
        t = min(w, h)
        if t < t_min or max(w, h) < 2 * t:       # 不夠細長的塊不算牆段
            continue
        if ((w >= h and (abs(y0 - Y0) <= tol or abs(y1 - Y1) <= tol)) or
                (h >= w and (abs(x0 - X0) <= tol or abs(x1 - X1) <= tol))):
            th.append(t)
    return float(np.median(th)) if th else float(T)


def derive_door_scale(doors, T_out, cfg: Config):
    """定每張圖的比例：以 config 比例為基準，強制外圍牆厚 ≥ 15cm——config 比例讓
    外牆不足 15cm 時，把比例撐到剛好 15cm(method=wall_min)。門寬偵測系統性不可靠
    (常抓到家具弧線拼成的假門，比例會被撐大 1.3~2 倍)，不再當錨點；只把偵測到的
    門寬用最終比例換算後寫進 info 給前端交叉檢核：落在 70~110cm → 信心 high，
    偏離 → low(比例或門偵測至少一個有問題)，沒門 → medium。
    回傳 (mm_per_px, info)。"""
    mm_per_px = (25.4 / cfg.dpi) if cfg.dpi else cfg.mm_per_px
    info = {"method": "config", "confidence": "medium",
            "doors_used": 0, "wall_min_cm": WALL_MIN_CM}
    wall_cm = T_out * mm_per_px / 10.0
    if wall_cm < WALL_MIN_CM:                    # 外牆 <15cm → 比例太小，撐到下限
        mm_per_px = WALL_MIN_CM * 10.0 / T_out
        wall_cm = WALL_MIN_CM
        info["method"] = "wall_min"
    info["outer_wall_cm"] = round(wall_cm, 1)
    widths = [d[2] for d in doors if d[3] >= 0.85]
    if widths:                                   # 門只做檢核，不回推比例
        door_cm = float(np.median(widths)) * mm_per_px / 10.0
        info.update(doors_used=len(widths), median_door_cm=round(door_cm, 1),
                    confidence="high" if 70.0 <= door_cm <= 110.0 else "low")
    return mm_per_px, info


def write_json(path, img_w, img_h, rects, wins, doors, mm_per_px, info, cfg: Config,
               dxf_scale_path):
    """前端交接 JSON：cm 座標與 dxf_scale/ 完全一致(原點左下、y 向上)，
    px 座標為影像座標(原點左上、y 向下)，方便前端疊回原圖。"""
    cm = mm_per_px / 10.0

    def box_cm(x0, y0, x1, y1):                  # 影像bbox → DXF座標bbox(y翻轉)
        return [round(x0 * cm, 2), round((img_h - y1) * cm, 2),
                round(x1 * cm, 2), round((img_h - y0) * cm, 2)]

    data = {
        "image": {"file": os.path.basename(cfg.input),
                  "width_px": img_w, "height_px": img_h},
        "scale": {"cm_per_px": round(cm, 4), "mm_per_px": round(mm_per_px, 4), **info},
        "units": {"cm": "同 dxf_scale：原點左下、y 向上",
                  "px": "影像座標：原點左上、y 向下"},
        "walls": [{"px": [int(x0), int(y0), int(x1), int(y1)],
                   "cm": box_cm(x0, y0, x1, y1)} for x0, y0, x1, y1 in rects],
        "windows": [{"orient": o, "px": [int(x0), int(y0), int(x1), int(y1)],
                     "cm": box_cm(x0, y0, x1, y1)} for o, x0, y0, x1, y1 in wins],
        "doors": [{"px": {"cx": round(dx, 1), "cy": round(dy, 1), "width": round(dw, 1)},
                   "cm": {"cx": round(dx * cm, 2), "cy": round((img_h - dy) * cm, 2),
                          "width": round(dw * cm, 2)},
                   "score": round(sc, 3)} for dx, dy, dw, sc, *_ in doors],
        "dxf_scale": dxf_scale_path,
    }
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


# ──────────────── architecture.json（白模交接格式） ────────────────
def _nearest_wall(px, py, rects):
    """點到牆矩形的最短距離，回傳 (最近牆的索引, 距離)。"""
    best, best_d = None, float("inf")
    for i, (x0, y0, x1, y1) in enumerate(rects):
        dx = max(x0 - px, 0.0, px - x1)
        dy = max(y0 - py, 0.0, py - y1)
        d = math.hypot(dx, dy)
        if d < best_d:
            best, best_d = i, d
    return best, best_d


def _host_wall_for_window(win, rects, T):
    """窗吸附的牆：同方向、跨牆範圍有重疊、沿牆軸最貼近的那段。
    窗是牆上的開口，兩側必貼牆——取沿牆軸間距最小者(重疊算負距離)。"""
    o, x0, y0, x1, y1 = win
    best, best_d = None, 2.5 * T
    for i, (wx0, wy0, wx1, wy1) in enumerate(rects):
        horiz = (wx1 - wx0) >= (wy1 - wy0)
        if horiz != (o == "h"):
            continue
        if horiz:
            cross = min(y1, wy1) - max(y0, wy0)
            d = max(wx0 - x1, x0 - wx1)
        else:
            cross = min(x1, wx1) - max(x0, wx0)
            d = max(wy0 - y1, y0 - wy1)
        if cross > 0 and d < best_d:
            best, best_d = i, d
    return best


def _door_geometry(door, rects, T):
    """由鉸鏈位置、L 形兩自由端方向與最近的牆，決定門的沿牆方向與開門側。
    回傳 (host牆索引|None, 門洞中心, 沿牆方向, 開門側方向)，皆影像座標。"""
    cx, cy, r, _sc, ux, vy = door
    idx, d = _nearest_wall(cx, cy, rects)
    horiz = True
    if idx is not None:
        x0, y0, x1, y1 = rects[idx]
        horiz = (x1 - x0) >= (y1 - y0)
    if horiz:                                    # 牆水平→門洞沿x、往y側開
        along, swing = (float(ux), 0.0), (0.0, float(vy))
    else:
        along, swing = (0.0, float(vy)), (float(ux), 0.0)
    center = (cx + r / 2.0 * along[0], cy + r / 2.0 * along[1])
    host = idx if (idx is not None and d <= 3.0 * T) else None
    return host, center, along, swing


def _room_polygon(rects, wins, doors, img_w, img_h, T, T_out):
    """房間可用區域外框(px)：牆+窗+門洞畫成實心遮罩 → 膨脹把沒偵測到的門洞封起來 →
    從影像邊界灌水,灌不進的區域=建物(含牆) → 同核侵蝕還原邊界(膨脹誤差互相抵銷) →
    最大連通塊再內縮外圍牆厚 = 可用區域內緣。膨脹半徑逐步放大;面積太小或只圈到
    局部(寬/高涵蓋不足)視為殼漏水,放大重試;仍失敗回傳 None 讓欄位留空。"""
    if not rects:
        return None
    mask = np.zeros((img_h, img_w), np.uint8)
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for _o, x0, y0, x1, y1 in wins:
        cv2.rectangle(mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, -1)
    for d in doors:                              # 偵測到的門洞沿牆補回
        _h, _c, along, _s = _door_geometry(d, rects, T)
        cx, cy, r = d[0], d[1], d[2]
        p2 = (int(round(cx + r * along[0])), int(round(cy + r * along[1])))
        cv2.line(mask, (int(round(cx)), int(round(cy))), p2, 255, max(2, int(T)))
    X0 = min(r_[0] for r_ in rects); Y0 = min(r_[1] for r_ in rects)
    X1 = max(r_[2] for r_ in rects); Y1 = max(r_[3] for r_ in rects)
    bbox_area = (X1 - X0) * (Y1 - Y0)
    for g in (1.5, 2.5, 3.5):                    # 膨脹半徑(×T)，可封 2 倍寬的洞
        k = 2 * max(2, int(round(g * T))) + 1
        ker = np.ones((k, k), np.uint8)
        ff = np.pad(cv2.dilate(mask, ker), 1).copy()
        cv2.floodFill(ff, None, (0, 0), 128)     # 外部自由區→128；封閉孔洞=室內
        filled = ((ff[1:-1, 1:-1] != 128).astype(np.uint8)) * 255
        fp = cv2.erode(filled, ker, borderValue=0)
        ero = 2 * max(2, int(round(T_out))) + 1  # 內縮 T_out → 外牆內緣
        blk = cv2.erode(fp, np.ones((ero, ero), np.uint8), borderValue=0)
        # 沒封住的房間會漏到室外、內縮後整塊消失——所以驗收要做在「內縮後的
        # 最大連通塊」上：面積夠大且寬高涵蓋整個牆 bbox，才代表殼真的封起來了
        n, lab, stats, _ = cv2.connectedComponentsWithStats(blk)
        if n < 2:
            continue
        i_max = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        s = stats[i_max]
        if (s[cv2.CC_STAT_AREA] < 0.25 * bbox_area or
                s[cv2.CC_STAT_WIDTH] < 0.55 * (X1 - X0) or
                s[cv2.CC_STAT_HEIGHT] < 0.55 * (Y1 - Y0)):
            continue                             # 漏水/只圈到局部 → 加大封口再試
        blk = (lab == i_max).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(blk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        poly = cv2.approxPolyDP(c, max(2.0, 0.4 * T), True)[:, 0, :]
        if len(poly) >= 4:
            return poly.astype(float)
    return None


def write_arch_json(path, img_w, img_h, rects, wins, doors, mm_per_px, info,
                    cfg: Config, T, T_out):
    """白模交接 architecture.json：units/walls/windows/doors 必填，cm、原點左下 y 向上。
    2D 平面圖沒有立面資訊——牆高/窗高/窗台高用 config [arch] 預設值。
    門的 position=門洞中心、rotation=門面法線(指向開門側)、
    hinge=站在開門側面對門時鉸鏈在左/右。swing_in=開闔弧中點落在可用區域內。"""
    cm = mm_per_px / 10.0

    def pt(x, y):                                # 影像座標 → cm(y 翻轉)
        return {"x": round(x * cm, 2), "y": round((img_h - y) * cm, 2)}

    walls = []
    for i, (x0, y0, x1, y1) in enumerate(rects, 1):
        w, h = x1 - x0, y1 - y0
        walls.append({"id": f"wall_{i}",
                      "position": pt((x0 + x1) / 2.0, (y0 + y1) / 2.0),
                      "rotation": 0 if w >= h else 90,
                      "width": round(max(w, h) * cm, 2),
                      "thickness": round(min(w, h) * cm, 2),
                      "height": cfg.wall_height_cm})

    windows = []
    for i, (o, x0, y0, x1, y1) in enumerate(wins, 1):
        entry = {"id": f"win_{i}",
                 "position": pt((x0 + x1) / 2.0, (y0 + y1) / 2.0),
                 "rotation": 0 if o == "h" else 90,
                 "width": round(((x1 - x0) if o == "h" else (y1 - y0)) * cm, 2),
                 "height": cfg.window_height_cm,
                 "sill_height": cfg.sill_height_cm}
        hw = _host_wall_for_window((o, x0, y0, x1, y1), rects, T)
        if hw is not None:
            entry["host_wall"] = f"wall_{hw + 1}"
        windows.append(entry)

    poly = _room_polygon(rects, wins, doors, img_w, img_h, T, T_out)
    cnt = poly.reshape(-1, 1, 2).astype(np.float32) if poly is not None else None

    # json/ 保留全部門(帶 score 給前端過濾)；arch/ 直接蓋白模：只收高信心門，
    # 且換算後門寬要合理(50~250cm)——高分小弧多半是櫃門/雙開門的半扇
    good = [d for d in doors if d[3] >= 0.85 and 50.0 <= d[2] * cm <= 250.0]
    door_list = []
    for i, d in enumerate(good, 1):
        cx, cy, r = d[0], d[1], d[2]
        host, (mx, my), along, swing = _door_geometry(d, rects, T)
        nx, ny = swing[0], -swing[1]             # 開門側方向：影像→cm(y 翻轉)
        rot = int(round(math.degrees(math.atan2(ny, nx)))) % 360
        fx, fy = -nx, -ny                        # 站在開門側面對門
        lx, ly = -fy, fx                         # 面向方向逆時針90° = 左手邊
        vx = cx * cm - mx * cm                   # 門洞中心→鉸鏈(cm，x 分量)
        vy_cm = (img_h - cy) * cm - (img_h - my) * cm
        entry = {"id": f"door_{i}", "position": pt(mx, my), "rotation": rot,
                 "width": round(r * cm, 2),
                 "hinge": "left" if vx * lx + vy_cm * ly > 0 else "right"}
        if host is not None:
            entry["host_wall"] = f"wall_{host + 1}"
        if cnt is not None:                      # 開闔弧中點在可用區域內=向內開
            ax = cx + r * 0.7071 * (along[0] + swing[0])
            ay = cy + r * 0.7071 * (along[1] + swing[1])
            entry["swing_in"] = bool(
                cv2.pointPolygonTest(cnt, (float(ax), float(ay)), False) >= 0)
        door_list.append(entry)

    data = {"units": "cm"}
    if poly is not None:
        data["room_polygon"] = [[round(float(x) * cm, 2),
                                 round((img_h - float(y)) * cm, 2)] for x, y in poly]
    data.update(walls=walls, windows=windows, doors=door_list,
                meta={"image": os.path.basename(cfg.input),
                      "cm_per_px": round(cm, 4),
                      "scale_method": info.get("method"),
                      "scale_confidence": info.get("confidence")})
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


# ─────────────────────────── 輸出 ───────────────────────────
def write_dxf(H, V, img_h, scale, cfg: Config):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    if cfg.layer not in doc.layers:
        doc.layers.add(cfg.layer)

    def P(x, y):
        return (x * scale, (img_h - y) * scale)

    for y, x0, x1 in H:
        msp.add_line(P(x0, y), P(x1, y), dxfattribs={"layer": cfg.layer})
    for x, y0, y1 in V:
        msp.add_line(P(x, y0), P(x, y1), dxfattribs={"layer": cfg.layer})
    doc.saveas(cfg.output)


def preview(bgr, H, V, path):
    vis = bgr.copy()
    for y, x0, x1 in H:
        cv2.line(vis, (int(x0), int(y)), (int(x1), int(y)), (0, 0, 255), 1)
    for x, y0, y1 in V:
        cv2.line(vis, (int(x), int(y0)), (int(x), int(y1)), (255, 0, 0), 1)
    cv2.imwrite(path, vis)


def write_solid_dxf(rects, wins, img_h, scale, cfg: Config, out=None, insunits=4):
    """牆：封閉矩形 + SOLID HATCH。窗：開口矩形 + 4 條玻璃線 + 兩端封口(照正規檔)。
    out/insunits 給 dxf_scale/ 用：另存一份門寬比例、公分單位(insunits=5)的檔。"""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    if cfg.layer not in doc.layers:
        doc.layers.add(cfg.layer, color=7)
    if wins and cfg.win_layer not in doc.layers:
        doc.layers.add(cfg.win_layer, color=5)

    def P(x, y):
        return (x * scale, (img_h - y) * scale)

    for x0, y0, x1, y1 in rects:
        corners = [P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)]
        msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": cfg.layer})
        hatch = msp.add_hatch(dxfattribs={"layer": cfg.layer})
        hatch.set_solid_fill(color=256)
        hatch.paths.add_polyline_path(corners, is_closed=True)

    L = {"layer": cfg.win_layer}
    for orient, x0, y0, x1, y1 in wins:
        if orient == "h":                    # 橫窗：4 條橫線(跨牆厚) + 兩端豎封口
            t = y1 - y0
            for y in (y0, y0 + t / 3, y0 + 2 * t / 3, y1):
                msp.add_line(P(x0, y), P(x1, y), dxfattribs=L)
            msp.add_line(P(x0, y0), P(x0, y1), dxfattribs=L)
            msp.add_line(P(x1, y0), P(x1, y1), dxfattribs=L)
        else:                                # 豎窗
            t = x1 - x0
            for x in (x0, x0 + t / 3, x0 + 2 * t / 3, x1):
                msp.add_line(P(x, y0), P(x, y1), dxfattribs=L)
            msp.add_line(P(x0, y0), P(x1, y0), dxfattribs=L)
            msp.add_line(P(x0, y1), P(x1, y1), dxfattribs=L)
    doc.saveas(out or cfg.output)


def preview_solid(bgr, rects, wins, path):
    vis = bgr.copy()
    fill = vis.copy()
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(fill, (int(x0), int(y0)), (int(x1), int(y1)), (0, 0, 255), -1)
    vis = cv2.addWeighted(fill, 0.45, vis, 0.55, 0)   # 半透明紅 = 實心牆
    for _, x0, y0, x1, y1 in wins:
        cv2.rectangle(vis, (int(x0), int(y0)), (int(x1), int(y1)), (0, 170, 0), 2)  # 綠框 = 窗
    cv2.imwrite(path, vis)


# ─────────────────────────── main ───────────────────────────
def remove_solid_blobs(bw):
    """移除大面積實心填充塊(緊湊、非細長，如被塗實的房間/井)。
    它們不是牆，又會把自動牆厚 T 撐爆，導致細牆被侵蝕掉。
    牆網是細長結構(面積遠大於內切圓)，緊湊度高的才移除。"""
    dt = cv2.distanceTransform(bw, cv2.DIST_L2, 5)
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    out = bw.copy()
    removed = 0
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 50:
            continue
        r = float(dt[lab == i].max())
        if r < 16:                                 # 只清掉很厚的實心塊(>32px)，不動一般牆/家具
            continue
        area = st[i, cv2.CC_STAT_AREA]
        if area / (math.pi * r * r) < 3.0:         # 緊湊 = 實心塊，非牆
            out[lab == i] = 0
            removed += 1
    return out, removed


def run(cfg: Config):
    scale = (25.4 / cfg.dpi) if cfg.dpi else cfg.mm_per_px
    gray, bgr = load_gray(cfg)
    if cfg.deskew:
        gray, a = deskew(gray)
        print(f"deskew : 轉正 {a:+.2f}°")
    bw = binarize(gray, cfg)
    img_h, img_w = bw.shape[:2]
    bw, nblob = remove_solid_blobs(bw)           # 去掉大實心填充塊(非牆)

    # 自動量牆厚 T(最厚的水平/垂直線寬)，再依 T 推導所有 px 參數(空白者才推)
    dt = cv2.distanceTransform(bw, cv2.DIST_L2, 5)
    T = max(2, int(round(2.0 * float(dt.max()))))
    pick = lambda v, d: (v if v not in (None, 0) else d)
    cfg.solid = pick(cfg.solid, max(3, int(round(0.35 * T))))
    cfg.h_len = pick(cfg.h_len, max(int(round(1.5 * T)), cfg.solid + 2))
    cfg.v_len = pick(cfg.v_len, cfg.h_len)
    cfg.snap = pick(cfg.snap, float(max(3, int(round(0.6 * T)))))
    cfg.gap = pick(cfg.gap, float(max(3, int(round(0.4 * T)))))
    cfg.min_len = pick(cfg.min_len, float(max(int(round(1.0 * T)), 4)))
    print(f"自動牆厚 T={T}px → solid={cfg.solid} h_len={cfg.h_len} v_len={cfg.v_len} "
          f"snap={cfg.snap:.0f} gap={cfg.gap:.0f} min_len={cfg.min_len:.0f} "
          f"(牆厚<{cfg.wall_min_pct:.0f}%者不畫)")

    if cfg.solid > 0:
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.solid, cfg.solid))
        bw_open = cv2.morphologyEx(bw, cv2.MORPH_OPEN, ker)
    else:
        bw_open = bw
    orig = bw                                # 含細線的原始二值(判窗用)

    if cfg.style == "solid":                 # 實心牆：矩形 + SOLID HATCH；窗：符號
        rects = detect_solid(bw_open, cfg, T)
        wins, doors = [], []
        if cfg.windows:
            thin = cv2.subtract(orig, cv2.dilate(bw_open, np.ones((3, 3), np.uint8)))
            doors = detect_doors(thin, T, cfg.door_arc_pct)
            if cfg.invert:
                soft = orig                  # 亮線稿抓不到「淺灰」,退回一般二值
            else:
                _, soft = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            wins = detect_windows(orig, rects, cfg, T, doors, thin, soft)
        if cfg.preview:
            preview_solid(bgr, rects, wins, cfg.preview)

        # 門寬推比例(外圍牆厚≥15cm 把關) → 公分單位的 dxf_scale/ + 前端交接 json/
        T_out = outer_wall_thickness(rects, T)
        mmpp, sinfo = derive_door_scale(doors, T_out, cfg)
        sinfo["outer_wall_px"] = round(T_out, 1)
        base = os.path.splitext(os.path.basename(cfg.input))[0]
        os.makedirs("json", exist_ok=True)
        os.makedirs("arch", exist_ok=True)
        if cfg.output:                       # 指令/config 有指定輸出就照用
            scale_out = cfg.output
        else:                                # 慣例：DXF(cm) → dxf_scale/gray/
            os.makedirs("dxf_scale/gray", exist_ok=True)
            scale_out = os.path.join("dxf_scale/gray", base + ".dxf")
        json_out = os.path.join("json", base + ".json")
        arch_out = os.path.join("arch", base + ".json")
        write_solid_dxf(rects, wins, img_h, mmpp / 10.0, cfg, out=scale_out, insunits=5)
        write_json(json_out, img_w, img_h, rects, wins, doors, mmpp, sinfo, cfg, scale_out)
        write_arch_json(arch_out, img_w, img_h, rects, wins, doors, mmpp, sinfo,
                        cfg, T, T_out)

        print(f"影像   : {img_w}x{img_h}px  比例 {scale:.4f} mm/px  風格 solid")
        print(f"實心牆塊 : {len(rects)} 個   窗 : {len(wins)} 個 (門洞留開)")
        print(f"比例尺 : {mmpp / 10.0:.4f} cm/px  ({sinfo['method']}, 信心 {sinfo['confidence']}, "
              f"高信心門 {sinfo['doors_used']} 扇)")
        print(f"輸出   : {scale_out} (cm)   {json_out}   {arch_out}"
              + (f"   預覽 {cfg.preview}" if cfg.preview else ""))
        return
    bw = bw_open

    if not cfg.output:                       # 慣例：DXF → dxf_scale/gray/
        os.makedirs("dxf_scale/gray", exist_ok=True)
        cfg.output = os.path.join(
            "dxf_scale/gray", os.path.splitext(os.path.basename(cfg.input))[0] + ".dxf")

    H, V = detect_hough(bw, cfg) if cfg.method == "hough" else detect_morph(bw, cfg)
    raw = len(H) + len(V)
    H, V = postprocess(H, V, cfg)

    write_dxf(H, V, img_h, scale, cfg)
    if cfg.preview:
        preview(bgr, H, V, cfg.preview)

    print(f"影像   : {img_w}x{img_h}px  比例 {scale:.4f} mm/px  方法 {cfg.method}  風格 {cfg.style}")
    print(f"偵測   : 原始 {raw} 段 → 整理後 水平 {len(H)} + 垂直 {len(V)} = {len(H)+len(V)}")
    print(f"輸出   : {cfg.output}" + (f"   預覽 {cfg.preview}" if cfg.preview else ""))


IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")


def run_batch(in_dir: str, out_dir: str, cfg: Config):
    """批次：跑 in_dir/*.png|jpg|bmp → out_dir/*.dxf(公分單位)，每張另存疊圖到 chk/gray/ 供快速檢視。"""
    pngs = sorted(p for p in glob.glob(os.path.join(in_dir, "*"))
                  if p.lower().endswith(IMG_EXTS))
    if not pngs:
        sys.exit(f"{in_dir}/ 裡找不到圖檔 ({'/'.join(IMG_EXTS)})")
    chk_dir = "chk/gray"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(chk_dir, exist_ok=True)
    ok = fail = 0
    for p in pngs:
        base = os.path.splitext(os.path.basename(p))[0]
        print(f"=== {base} ===")
        # 每檔用全新 copy：px 參數維持空(None)，才會各自依自己的牆厚重新推導
        c = replace(cfg, input=p,
                    output=os.path.join(out_dir, base + ".dxf"),
                    preview=os.path.join(chk_dir, base + "_chk.png"))
        try:
            run(c)
            ok += 1
        except Exception as e:
            print(f"  ✗ 失敗: {e}")
            fail += 1
    print(f"\n批次完成: 成功 {ok} / 失敗 {fail}")
    print(f"  DXF(cm) → {out_dir}/  (門寬推算比例、公分單位)")
    print(f"  疊圖 → {chk_dir}/  (原圖 + 紅實心牆 + 綠窗，一次翻完抓問題)")
    print(f"  JSON → json/ (前端交接)   白模 → arch/")


def main():
    p = argparse.ArgumentParser(
        description="平面圖 PNG/JPG/BMP → DXF。參數見 config.ini；輸入/輸出可用指令覆蓋。\n"
                    "不帶參數 = 批次跑 png/ 目錄下所有圖檔 → dxf_scale/gray/ + chk/gray/")
    p.add_argument("input", nargs="?",
                   help="輸入圖檔 png/jpg/bmp(單張)；不給或給目錄則批次")
    p.add_argument("output", nargs="?",
                   help="輸出 DXF/目錄（不給就自動輸出到 dxf_scale/gray/同檔名.dxf）")
    p.add_argument("--config", default="config.ini", help="設定檔（預設 config.ini）")
    p.add_argument("--preview", help="疊圖輸出路徑（覆蓋 config）")
    a = p.parse_args()

    cfg = load_config(a.config)

    # 批次模式：不帶參數(且 config 沒鎖單張)、第一參數是目錄、或字面 'png'
    if (not a.input and not cfg.input) or \
       (a.input and (os.path.isdir(a.input) or a.input.lower() == "png")):
        in_dir = a.input if (a.input and os.path.isdir(a.input)) else "png"
        if not os.path.isdir(in_dir):
            sys.exit(f"找不到目錄 {in_dir}/  (請把要批次的圖檔放進去)")
        run_batch(in_dir, (a.output or "dxf_scale/gray"), cfg)
        return

    if a.input:
        cfg.input = a.input
    if a.preview is not None:
        cfg.preview = a.preview
    if a.output:
        cfg.output = a.output

    if not cfg.input:
        sys.exit("缺輸入：用 floorplan2dxf.py 圖.png，或 floorplan2dxf.py png 批次，或在 config.ini 設 input")
    # 慣例：輸入放 png/ —— 給的路徑讀不到時自動去 png/ 找
    if not os.path.isfile(cfg.input):
        alt = os.path.join("png", cfg.input)
        if os.path.isfile(alt):
            cfg.input = alt
    base = os.path.splitext(os.path.basename(cfg.input))[0]
    if not cfg.preview:                      # 慣例：疊圖 → chk/gray/
        os.makedirs("chk/gray", exist_ok=True)
        cfg.preview = os.path.join("chk/gray", base + "_chk.png")
    run(cfg)


if __name__ == "__main__":
    main()
