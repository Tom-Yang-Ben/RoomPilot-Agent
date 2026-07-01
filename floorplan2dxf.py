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


def detect_doors(thin, T: int, arc_pct: float):
    """依規則找門:一條垂直線 + 一條水平線(等長、垂直、共用一個角=鉸鏈)，
    兩自由端用半徑=門寬的弧連接(門的開闔動線)。回傳 [(cx, cy, width)] 鉸鏈與門寬。
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
    Himg, Wimg = thin.shape

    def arc_run(cx, cy, r, ux, vx, uy, vy):
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
                        if arc_run(cx, cy, r, ux, 0, 0, vy_) >= thr:
                            doors.append((cx, cy, r))
    uniq = []
    for d in doors:
        if not any(math.hypot(d[0] - u[0], d[1] - u[1]) < T for u in uniq):
            uniq.append(d)
    return uniq


def _near_door(cx, cy, gap, doors):
    """開口中心附近有沒有偵測到的門(鉸鏈在約一個門寬內、門寬與開口相符)。"""
    for dx, dy, dw in doors:
        if math.hypot(dx - cx, dy - cy) <= 1.1 * gap and 0.55 * gap <= dw <= 1.6 * gap:
            return True
    return False


def detect_windows(orig_bw, rects, cfg: Config, T: int, doors=None):
    """在牆的開口偵測窗:開口長度被細線高度覆蓋=窗(玻璃線沿牆跨整段)；
    空的=門/通道，留開；落在偵測到的門附近=門，留開。回傳 [(orient, x0, y0, x1, y1)]。"""
    doors = doors or []
    Himg, Wimg = orig_bw.shape
    thr = cfg.win_cover_pct / 100.0
    long_th = [min(r[2] - r[0], r[3] - r[1]) for r in rects
               if max(r[2] - r[0], r[3] - r[1]) >= 2 * T]      # 只取夠長的真牆
    all_th = [min(r[2] - r[0], r[3] - r[1]) for r in rects]
    src = long_th if long_th else all_th
    wall_t = float(np.median(src)) if src else float(T)        # 代表性牆厚
    min_w = (1.0 - cfg.win_min_pct / 100.0) * wall_t           # 窗跨牆寬度下限
    gmin, gmax = 0.4 * T, 15.0 * T
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
            band = orig_bw[max(0, y0):min(Himg, y1), max(0, x0):min(Wimg, x1)]
            if not (band.size and (band.max(axis=0) > 0).mean() >= thr):
                continue
            if _near_door((x0 + x1) / 2.0, (y0 + y1) / 2.0, gap, doors):
                continue                     # 開口處是門(L+弧) → 留開，不畫窗
            wins.append(("h", float(x0), float(y0), float(x1), float(y1)))

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
            band = orig_bw[max(0, y0):min(Himg, y1), max(0, x0):min(Wimg, x1)]
            if not (band.size and (band.max(axis=1) > 0).mean() >= thr):
                continue
            if _near_door((x0 + x1) / 2.0, (y0 + y1) / 2.0, gap, doors):
                continue                     # 開口處是門(L+弧) → 留開，不畫窗
            wins.append(("v", float(x0), float(y0), float(x1), float(y1)))
    return wins


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


def write_solid_dxf(rects, wins, img_h, scale, cfg: Config):
    """牆：封閉矩形 + SOLID HATCH。窗：開口矩形 + 4 條玻璃線 + 兩端封口(照正規檔)。"""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
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
    doc.saveas(cfg.output)


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
        wins = []
        if cfg.windows:
            thin = cv2.subtract(orig, cv2.dilate(bw_open, np.ones((3, 3), np.uint8)))
            doors = detect_doors(thin, T, cfg.door_arc_pct)
            wins = detect_windows(orig, rects, cfg, T, doors)
        write_solid_dxf(rects, wins, img_h, scale, cfg)
        if cfg.preview:
            preview_solid(bgr, rects, wins, cfg.preview)
        print(f"影像   : {img_w}x{img_h}px  比例 {scale:.4f} mm/px  風格 solid")
        print(f"實心牆塊 : {len(rects)} 個   窗 : {len(wins)} 個 (門洞留開)")
        print(f"輸出   : {cfg.output}" + (f"   預覽 {cfg.preview}" if cfg.preview else ""))
        return
    bw = bw_open

    H, V = detect_hough(bw, cfg) if cfg.method == "hough" else detect_morph(bw, cfg)
    raw = len(H) + len(V)
    H, V = postprocess(H, V, cfg)

    write_dxf(H, V, img_h, scale, cfg)
    if cfg.preview:
        preview(bgr, H, V, cfg.preview)

    print(f"影像   : {img_w}x{img_h}px  比例 {scale:.4f} mm/px  方法 {cfg.method}  風格 {cfg.style}")
    print(f"偵測   : 原始 {raw} 段 → 整理後 水平 {len(H)} + 垂直 {len(V)} = {len(H)+len(V)}")
    print(f"輸出   : {cfg.output}" + (f"   預覽 {cfg.preview}" if cfg.preview else ""))


def run_batch(in_dir: str, out_dir: str, cfg: Config):
    """批次：跑 in_dir/*.png → out_dir/*.dxf，每張另存疊圖到 chk/ 供快速檢視。"""
    pngs = sorted(glob.glob(os.path.join(in_dir, "*.png")))
    if not pngs:
        sys.exit(f"{in_dir}/ 裡找不到 .png")
    chk_dir = "chk"
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
    print(f"  DXF  → {out_dir}/")
    print(f"  疊圖 → {chk_dir}/  (原圖 + 紅實心牆 + 綠窗，一次翻完抓問題)")


def main():
    p = argparse.ArgumentParser(
        description="平面圖 PNG → DXF。參數見 config.ini；輸入/輸出可用指令覆蓋。\n"
                    "批次：python3 floorplan2dxf.py png  (跑 png/*.png → dxf/*.dxf)")
    p.add_argument("input", nargs="?",
                   help="輸入 PNG；或目錄(或字面 'png')進批次模式")
    p.add_argument("output", nargs="?",
                   help="輸出 DXF/目錄（不給就用「輸入同檔名換 .dxf」或 dxf/）")
    p.add_argument("--config", default="config.ini", help="設定檔（預設 config.ini）")
    p.add_argument("--preview", help="疊圖輸出路徑（覆蓋 config）")
    a = p.parse_args()

    cfg = load_config(a.config)

    # 批次模式：第一參數是目錄，或字面 'png'
    if a.input and (os.path.isdir(a.input) or a.input.lower() == "png"):
        in_dir = a.input if os.path.isdir(a.input) else "png"
        if not os.path.isdir(in_dir):
            sys.exit(f"找不到目錄 {in_dir}/  (請把要批次的 png 放進去)")
        run_batch(in_dir, (a.output or "dxf"), cfg)
        return

    if a.input:
        cfg.input = a.input
    if a.preview is not None:
        cfg.preview = a.preview
    if a.output:
        cfg.output = a.output
    elif a.input:
        cfg.output = os.path.splitext(a.input)[0] + ".dxf"

    if not cfg.input:
        sys.exit("缺輸入：用 floorplan2dxf.py 圖.png，或 floorplan2dxf.py png 批次，或在 config.ini 設 input")
    if not cfg.output:
        cfg.output = os.path.splitext(cfg.input)[0] + ".dxf"
    run(cfg)


if __name__ == "__main__":
    main()
