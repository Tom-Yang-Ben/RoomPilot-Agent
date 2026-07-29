"""symbol_match.py — 符號模板庫的渲染與比對（路線圖 B）。

FixedFurniture 向量線稿 → 48×48 標準模板；查詢圖細線層輪廓以
Hu moments 預篩＋chamfer 驗證兩階段比對模板庫，作為與手寫幾何
規則（floorplan2room.detect_symbols）並行互補的證據來源。
庫檔 symbol_lib.npz 缺失時 match_symbols 回空清單，管線行為不變。
"""
import os

import cv2
import numpy as np

CANVAS = 48
LIB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "symbol_lib.npz")                # repo 根（2026-07-29 由 training/ 移出）
# SVG class token → 證據 kind（oval/tubrect/stove 沿用既有計分；
# shower/sinkicon 為新 kind，classify_rooms_cc 給保守小權重）
TARGETS = {"Toilet": "oval", "Bathtub": "tubrect", "BathtubRound": "tubrect",
           "IntegratedStove": "stove", "Sink": "sinkicon", "Shower": "shower"}
HU_THR = 0.15                # Hu 預篩門檻（matchShapes I1 等價）
CH_THR = 2.0                 # chamfer 平均邊緣距離門檻（48px 畫布上的 px）
_PATH_SAMPLES = 120


def _pts_attr(node):
    raw = node.getAttribute("points").replace(",", " ").split()
    return np.array([float(x) for x in raw], float).reshape(-1, 2)


def collect_primitives(e, _hidden=False, _invisible=False):
    """遞迴收集節點下可見繪圖元素為折線清單（local 座標，不套 transform）。
    排除 display:none 群組（Direction/Name）與 fill=none stroke=none 的
    隱形 BoundaryPolygon。可見元素實測只有 rect/path/polygon/circle 四種。"""
    from svgpathtools import parse_path
    polys = []
    for k in e.childNodes:
        if k.nodeType != 1:
            continue
        hidden = _hidden or "display: none" in (k.getAttribute("style") or "")
        if hidden:
            continue
        if k.nodeName == "g":
            f, s = k.getAttribute("fill"), k.getAttribute("stroke")
            invisible = _invisible or (f == "none" and s == "none")
            polys += collect_primitives(k, hidden, invisible)
        elif _invisible:
            continue
        elif k.nodeName == "polygon":
            p = _pts_attr(k)
            if len(p) >= 2:
                polys.append(np.vstack([p, p[:1]]))
        elif k.nodeName == "rect":
            x = float(k.getAttribute("x") or 0)
            y = float(k.getAttribute("y") or 0)
            w = float(k.getAttribute("width") or 0)
            h = float(k.getAttribute("height") or 0)
            if w > 0 and h > 0:
                polys.append(np.array([[x, y], [x + w, y], [x + w, y + h],
                                       [x, y + h], [x, y]]))
        elif k.nodeName == "circle":
            cx = float(k.getAttribute("cx") or 0)
            cy = float(k.getAttribute("cy") or 0)
            r = float(k.getAttribute("r") or 0)
            if r > 0:
                t = np.linspace(0, 2 * np.pi, 32)
                polys.append(np.stack([cx + r * np.cos(t),
                                       cy + r * np.sin(t)], 1))
        elif k.nodeName == "path":
            try:
                pp = parse_path(k.getAttribute("d"))
                if pp.length() > 0:
                    ts = np.linspace(0, 1, _PATH_SAMPLES)
                    zz = np.array([pp.point(t) for t in ts])
                    polys.append(np.stack([zz.real, zz.imag], 1))
            except Exception:
                pass                         # 退化 path 跳過（建庫端計數回報）
    return polys


def render_polylines(polys, canvas=CANVAS):
    """折線清單 → 等比縮放置中的 uint8 線稿 raster（黑底白線）。"""
    if not polys:
        return None
    allp = np.vstack(polys)
    x0, y0 = allp.min(0)
    x1, y1 = allp.max(0)
    w, h = x1 - x0, y1 - y0
    if w < 2 or h < 2:
        return None
    s = (canvas - 4) / max(w, h)
    ox = (canvas - w * s) / 2 - x0 * s
    oy = (canvas - h * s) / 2 - y0 * s
    img = np.zeros((canvas, canvas), np.uint8)
    for p in polys:
        q = np.round(p * s + (ox, oy)).astype(np.int32)
        cv2.polylines(img, [q], False, 255, 1)
    return img


def crop_to_canvas(img, x, y, w, h, canvas=CANVAS):
    """二值線稿圖的 bbox 裁切 → 等比縮放置中到 canvas（與模板同正規化）。"""
    crop = img[y:y + h, x:x + w]
    if crop.size == 0 or not crop.any():
        return None
    s = (canvas - 4) / max(w, h)
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    small = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    small = (small > 40).astype(np.uint8) * 255   # 降採樣後回二值，線寬≈1px
    out = np.zeros((canvas, canvas), np.uint8)
    ox, oy = (canvas - nw) // 2, (canvas - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out


def hu_of(raster):
    """raster 全部線條像素的 log-Hu 向量 (7,)。
    用整張線稿的矩（非單一輪廓）——多部件符號（爐台四圈）才不會漏訊息。"""
    m = cv2.moments(raster, binaryImage=True)
    hu = cv2.HuMoments(m).flatten()
    return np.sign(hu) * np.log10(np.abs(hu) + 1e-30)


def hu_dist(hu_a, hu_b):
    """cv2.matchShapes CONTOURS_MATCH_I1 等價（作用在 log-Hu 向量上）。"""
    with np.errstate(divide="ignore"):
        ia = np.where(hu_a != 0, 1.0 / hu_a, 0.0)
        ib = np.where(hu_b != 0, 1.0 / hu_b, 0.0)
    return float(np.abs(ia - ib).sum())


def chamfer_score(cand, tpl):
    """對稱 chamfer：兩張 48×48 線稿互相取「線點到對方最近線點」平均距離(px)。"""
    def one_way(a, b):
        dt = cv2.distanceTransform(255 - b, cv2.DIST_L2, 3)
        pts = a > 0
        if not pts.any():
            return 1e9
        return float(dt[pts].mean())
    return max(one_way(cand, tpl), one_way(tpl, cand))


_lib_cache = "unloaded"


def load_lib(path=LIB_PATH):
    """載入模板庫；檔案不存在回 None（管線行為不變）。模組級快取。"""
    global _lib_cache
    if _lib_cache == "unloaded":
        if not os.path.isfile(path):
            _lib_cache = None
        else:
            z = np.load(path, allow_pickle=False)
            labels = [str(x) for x in z["labels"]]
            kinds = sorted(set(labels))
            _lib_cache = {
                "rasters": z["rasters"], "hu": z["hu"], "labels": labels,
                # 每 kind 的實體尺寸閘門：短邊/長邊的 P5~P95（svg 單位≈cm）
                "size": {k: (np.percentile(z["wh"][[i for i, l in
                             enumerate(labels) if l == k]].min(1), [5, 95]),
                             np.percentile(z["wh"][[i for i, l in
                             enumerate(labels) if l == k]].max(1), [5, 95]))
                        for k in kinds},
            }
    return _lib_cache


def match_symbols(det, lib=None):
    """細線層輪廓對模板庫兩階段比對 → [(kind, cx, cy)]。
    kind 為 TARGETS 的值域（oval/tubrect/stove/sinkicon/shower）。"""
    lib = lib if lib is not None else load_lib()
    thin, cm = det.get("thin"), det["cm"]
    if lib is None or thin is None:
        return []
    closed = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    hu_arr, rasters, labels = lib["hu"], lib["rasters"], lib["labels"]
    syms = []
    for c in cnts:
        if len(c) < 20:
            continue
        x, y, w, h = cv2.boundingRect(c)
        lo, hi = sorted((w * cm, h * cm))
        # 尺寸閘門：至少落在一個 kind 的 P5~P95 ±20% 區間
        ok_kinds = [k for k, ((s5, s95), (l5, l95)) in lib["size"].items()
                    if s5 * 0.8 <= lo <= s95 * 1.2 and l5 * 0.8 <= hi <= l95 * 1.2]
        if not ok_kinds:
            continue
        # 候選 = bbox 內整個細線層裁切（含巢狀圓圈/X 線等所有部件）——
        # 符號是多部件複合圖，單一輪廓（只有外框或只有一個圈）比不上模板
        cand = crop_to_canvas(closed, x, y, w, h)
        if cand is None:
            continue
        hc = hu_of(cand)
        best_kind, best_ch = None, 1e9
        for k in ok_kinds:
            idx = [i for i, l in enumerate(labels) if l == k]
            d = np.array([hu_dist(hc, hu_arr[i]) for i in idx])
            top = np.argsort(d)[:5]                      # Hu 前 5 名進 chamfer
            for j in top:
                if d[j] > HU_THR:
                    continue
                ch = chamfer_score(cand, rasters[idx[j]])
                if ch < best_ch:
                    best_kind, best_ch = k, ch
        if best_kind is not None and best_ch <= CH_THR:
            syms.append((best_kind, x + w / 2.0, y + h / 2.0))
    return syms
