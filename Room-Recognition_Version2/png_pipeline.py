# -*- coding: utf-8 -*-
"""PNG 平面圖尺寸辨識管線（古典形態學 PoC 版）。

執行順序（依規格定案，不可調換）：
  1. OCR 收割：先讀取全圖文字，保留尺寸標註數字
  2. 屏蔽：移除文字框；形態學開運算移除家具等細線，保留牆體
  3. 結構量測：萃取水平／垂直牆段與開口（門、窗）
  4. 校準：OCR 標註優先，手動兩點參考為保底
  5. 家具辨識與空間判定：屏蔽掉的家具層交給 furniture_match 分類，
     依家具種類判定各空間用途（廚房／臥室／衛浴…）
限制：本版假設 Manhattan 佈局（水平／垂直牆），斜牆不在範圍內。
"""
from __future__ import annotations

import base64
import os
import re
import shutil
from typing import Optional

import cv2
import numpy as np

from furniture_match import assign_rooms, detect_furniture, load_templates

try:
    import pytesseract
    from pytesseract import Output

    def _locate_tesseract() -> Optional[str]:
        """定位 tesseract 執行檔：PATH 優先，其次常見安裝位置。

        Windows 安裝器預設不會把 Tesseract 加進 PATH，故在此自動補上，
        避免使用者得手動設定環境變數。
        """
        found = shutil.which("tesseract")
        if found:
            return found
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
        return next((p for p in candidates if os.path.isfile(p)), None)

    _TESSERACT_CMD = _locate_tesseract()
    if _TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    _HAS_TESSERACT = _TESSERACT_CMD is not None
except Exception:  # pragma: no cover - 環境未安裝 tesseract 時降級
    _HAS_TESSERACT = False

# 尺寸標註的合理範圍（mm）：小於門把、大於 20 公尺的數字不視為標註
_DIM_MIN_MM = 250
_DIM_MAX_MM = 20000
# mm/px 合理範圍，用來排除離譜的配對
_RATIO_MIN, _RATIO_MAX = 0.15, 60.0


# ---------------------------------------------------------------------------
# 步驟 1：OCR 收割（在任何屏蔽之前執行）
# ---------------------------------------------------------------------------
def _harvest_text(gray: np.ndarray) -> tuple[list[dict], list[tuple[int, int, int, int]], list[str]]:
    """回傳 (尺寸標註候選, 所有文字框, 警告)。"""
    warnings: list[str] = []
    if not _HAS_TESSERACT:
        warnings.append("OCR 不可用（未安裝 Tesseract），已略過標註校準，可改用手動校準。")
        return [], [], warnings
    try:
        data = pytesseract.image_to_data(gray, config="--psm 11", output_type=Output.DICT)
    except Exception as exc:  # pragma: no cover
        warnings.append(f"OCR 執行失敗（{exc}），已略過標註校準。")
        return [], [], warnings

    dims: list[dict] = []
    boxes: list[tuple[int, int, int, int]] = []
    for i, raw in enumerate(data["text"]):
        word = (raw or "").strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 30:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        boxes.append((x, y, w, h))
        cleaned = word.replace(",", "").replace("，", "")
        if re.fullmatch(r"\d{3,5}", cleaned):
            value = int(cleaned)
            if _DIM_MIN_MM <= value <= _DIM_MAX_MM:
                dims.append({"value": value, "cx": x + w / 2.0, "cy": y + h / 2.0})
    return dims, boxes, warnings


# ---------------------------------------------------------------------------
# 步驟 2：屏蔽（文字框 + 家具細線），保留牆／窗／門所在的粗筆劃
# ---------------------------------------------------------------------------
def _mask_text(ink: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    out = ink.copy()
    pad = 3
    h_img, w_img = out.shape
    for x, y, w, h in boxes:
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w_img, x + w + pad), min(h_img, y + h + pad)
        out[y0:y1, x0:x1] = 0
    return out


def _estimate_wall_thickness(ink_clean: np.ndarray) -> float:
    """以距離轉換估計主要筆劃厚度（牆厚，像素）。"""
    dist = cv2.distanceTransform((ink_clean > 0).astype(np.uint8), cv2.DIST_L2, 5)
    vals = dist[dist >= 2.0]
    if vals.size < 50:
        vals = dist[dist > 0]
    if vals.size == 0:
        return 8.0
    half = float(np.percentile(vals, 90))
    return max(6.0, 2.0 * half)


def _odd(v: float, minimum: int = 3) -> int:
    k = max(minimum, int(round(v)))
    return k if k % 2 == 1 else k + 1


def _structural_mask(ink_clean: np.ndarray, t: float) -> np.ndarray:
    """形態學開運算：細線（家具、標註線）消失，牆體留下。"""
    k = _odd(t * 0.55)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    opened = cv2.morphologyEx(ink_clean, cv2.MORPH_OPEN, kernel)
    # 移除殘餘小碎片
    n, labels, stats, _ = cv2.connectedComponentsWithStats((opened > 0).astype(np.uint8), 8)
    min_area = int(t * t * 4)
    keep = np.zeros_like(opened)
    for lbl in range(1, n):
        if stats[lbl, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == lbl] = 255
    return keep


# ---------------------------------------------------------------------------
# 步驟 3：結構量測（牆段、共線群組、開口偵測與分類）
# ---------------------------------------------------------------------------
def _extract_strips(wall_mask: np.ndarray, t: float, axis: str) -> list[dict]:
    """以方向性開運算取出水平（axis='h'）或垂直（axis='v'）牆段。"""
    long_k = _odd(t * 2.2, 9)
    thin_k = _odd(t * 0.5)
    size = (long_k, thin_k) if axis == "h" else (thin_k, long_k)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, size)
    strips = cv2.morphologyEx(wall_mask, cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats((strips > 0).astype(np.uint8), 8)
    segs: list[dict] = []
    for lbl in range(1, n):
        x, y, w, h = (stats[lbl, cv2.CC_STAT_LEFT], stats[lbl, cv2.CC_STAT_TOP],
                      stats[lbl, cv2.CC_STAT_WIDTH], stats[lbl, cv2.CC_STAT_HEIGHT])
        if axis == "h":
            if w < t * 2.5:
                continue
            segs.append({"axis": "h", "lo": float(x), "hi": float(x + w),
                         "pos": y + h / 2.0, "thickness": float(h)})
        else:
            if h < t * 2.5:
                continue
            segs.append({"axis": "v", "lo": float(y), "hi": float(y + h),
                         "pos": x + w / 2.0, "thickness": float(w)})
    return segs


def _group_collinear(segs: list[dict], t: float) -> list[dict]:
    groups: list[dict] = []
    tol = max(t * 0.8, 6.0)
    for s in sorted(segs, key=lambda s: s["pos"]):
        placed = False
        for g in groups:
            if abs(g["pos"] - s["pos"]) <= tol:
                g["segs"].append(s)
                g["pos"] = float(np.mean([x["pos"] for x in g["segs"]]))
                placed = True
                break
        if not placed:
            groups.append({"pos": s["pos"], "segs": [s]})
    for g in groups:
        g["segs"].sort(key=lambda s: s["lo"])
        g["lo"] = min(s["lo"] for s in g["segs"])
        g["hi"] = max(s["hi"] for s in g["segs"])
    return groups


def _classify_opening(ink_clean: np.ndarray, axis: str, pos: float, thickness: float,
                      lo: float, hi: float) -> str:
    """開口分類：窗（牆帶內有細線），其餘一律為開口。

    門不辨識（使用者規格）：牆上開口即使帶開啟弧也輸出「開口」，
    寬度尺寸照常量測，只是不冠上「門」的類別。
    """
    h_img, w_img = ink_clean.shape
    half_t = max(2, int(thickness / 2))
    p = int(round(pos))
    a, b = int(round(lo)), int(round(hi))
    if axis == "h":
        band = ink_clean[max(0, p - half_t):min(h_img, p + half_t), max(0, a):min(w_img, b)]
    else:
        band = ink_clean[max(0, a):min(h_img, b), max(0, p - half_t):min(w_img, p + half_t)]
    if band.size and (band > 0).mean() > 0.10:
        return "window"
    return "opening"


def _trim_t_junction(lo: float, hi: float, pos: float, perp_groups: list[dict], t: float) -> tuple[float, float]:
    """T 形相接時，把端點修剪到相交牆的內緣（轉角不修，維持外緣全長慣例）。

    判準：端點落在垂直向牆帶內，且該牆在本牆線兩側都有延伸（T 形）才修剪；
    只在單側延伸者為轉角（L 形），不修剪。
    """
    for g in perp_groups:
        g_th = float(np.mean([s["thickness"] for s in g["segs"]])) if g["segs"] else t
        half = g_th / 2.0 + 2.0
        left_pt, right_pt = pos - max(t, g_th), pos + max(t, g_th)
        covers_left = any(s["lo"] < left_pt < s["hi"] for s in g["segs"])
        covers_right = any(s["lo"] < right_pt < s["hi"] for s in g["segs"])
        if not (covers_left and covers_right):
            continue
        if g["pos"] - half <= lo <= g["pos"] + half:
            lo = g["pos"] + g_th / 2.0
        if g["pos"] - half <= hi <= g["pos"] + half:
            hi = g["pos"] - g_th / 2.0
    return lo, hi


def _detect_elements(wall_mask: np.ndarray, ink_clean: np.ndarray, t: float) -> tuple[list[dict], list[dict]]:
    """回傳 (元素清單, 共線群組清單)。元素座標為影像像素。"""
    elements: list[dict] = []
    groups_by_axis: dict[str, list[dict]] = {}
    for axis in ("h", "v"):
        segs = _extract_strips(wall_mask, t, axis)
        groups = _group_collinear(segs, t)
        for g in groups:
            g["axis"] = axis
        groups_by_axis[axis] = groups
    all_groups = groups_by_axis["h"] + groups_by_axis["v"]

    for axis in ("h", "v"):
        perp_groups = groups_by_axis["v" if axis == "h" else "h"]
        for g in groups_by_axis[axis]:
            # 牆段（端點經 T 形交接修剪；群組全長維持外緣慣例供校準使用）
            for s in g["segs"]:
                lo, hi = _trim_t_junction(s["lo"], s["hi"], g["pos"], perp_groups, t)
                if hi - lo < t:
                    continue
                if axis == "h":
                    p1, p2 = (lo, g["pos"]), (hi, g["pos"])
                else:
                    p1, p2 = (g["pos"], lo), (g["pos"], hi)
                elements.append({"kind": "wall", "p1": p1, "p2": p2,
                                 "px_length": hi - lo, "thickness_px": s["thickness"]})
            # 開口：同一直線上相鄰牆段之間的縫隙
            for cur, nxt in zip(g["segs"], g["segs"][1:]):
                gap = nxt["lo"] - cur["hi"]
                if t * 0.9 <= gap <= t * 16:
                    th = (cur["thickness"] + nxt["thickness"]) / 2.0
                    kind = _classify_opening(ink_clean, axis, g["pos"], th, cur["hi"], nxt["lo"])
                    if axis == "h":
                        p1, p2 = (cur["hi"], g["pos"]), (nxt["lo"], g["pos"])
                    else:
                        p1, p2 = (g["pos"], cur["hi"]), (g["pos"], nxt["lo"])
                    elements.append({"kind": kind, "p1": p1, "p2": p2,
                                     "px_length": gap, "thickness_px": th})
    return elements, all_groups


# ---------------------------------------------------------------------------
# 步驟 3.5：空間（房間）偵測——牆體圍出的封閉區域，容許缺漏邊
# ---------------------------------------------------------------------------
def _bottleneck_grow(free: np.ndarray, dist: np.ndarray, seed_masks: list[np.ndarray],
                     levels: int = 56, steps: int = 4) -> np.ndarray:
    """瓶頸生長：所有種子同時往外淹，優先高地（寬敞處），低谷（瓶頸）最後淹。

    dist＝寬度場（距最近牆體的距離）。門檻由高到低逐層下降，每層各生長面
    只推進固定步數——等速推進，任一面都不會在單層內跑完全場（否則貼牆的
    種子會被餓死，只長出自己的外框）。兩股生長面相遇處即邊界；因為低谷
    最後才開放通行，相遇點必然落在門口／牆垛／通道等瓶頸。
    回傳與 free 同尺寸的標籤圖（0＝邊界，1..n＝各種子的區域）。
    """
    labels = np.zeros(free.shape, np.int32)
    for i, m in enumerate(seed_masks, 1):
        labels[m] = i
    n = len(seed_masks)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dmax = float(dist.max())
    if dmax <= 0:
        return labels

    def advance(gate: np.ndarray) -> bool:
        allowed = free & gate & (labels == 0)
        if not allowed.any():
            return False
        claims = np.zeros(free.shape, np.uint8)
        first = np.zeros(free.shape, np.int32)
        for i in range(1, n + 1):
            g = (cv2.dilate((labels == i).astype(np.uint8), k) > 0) & allowed
            claims[g] += 1
            first = np.where((first == 0) & g, i, first)
        new = (claims == 1) & (first > 0)   # 兩股同時搶到者留白＝分水嶺
        if not new.any():
            return False
        labels[new] = first[new]
        return True

    for lv in np.linspace(dmax, 0.0, levels):
        gate = dist >= lv
        for _ in range(steps):              # 每層等速推進，不讓單一生長面跑完全場
            if not advance(gate):
                break
    everywhere = np.ones(free.shape, bool)  # 收尾：殘餘低谷由各面等速填滿
    for _ in range(400):
        if not advance(everywhere):
            break
    return labels


def _door_arc_seals(ink_clean: np.ndarray, wall_mask: np.ndarray, t: float,
                    mm_per_px: Optional[float] = None) -> list[dict]:
    """封門做法 #1（最可靠）：偵測門弧（四分之一圓）→ 回傳門洞兩端的封閉線段。

    門符號＝門扇（直線）＋開啟弧（四分之一圓）。判準：
      - 外接框近正方形，邊長落在合理門寬（60–130 cm，無比例尺時以牆厚推估）
      - 筆劃稀疏（細曲線，非實心塊）
      - 有相當比例的墨水點落在「距某個角落 ≈ 半徑」的細環帶上 → 該角落即鉸鏈
      - 鉸鏈相鄰的兩邊中，貼著牆的那一邊就是門洞，沿該邊連線即封住

    順帶得到門的位置與寬度。回傳 [{p1, p2, width_px}]。
    """
    wall_dil = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    detail = cv2.bitwise_and(ink_clean, cv2.bitwise_not(wall_dil))
    n, labels, stats, _ = cv2.connectedComponentsWithStats((detail > 0).astype(np.uint8), 8)
    if mm_per_px:
        lo_px, hi_px = 600.0 / mm_per_px, 1300.0 / mm_per_px   # 門寬 60–130 cm
    else:
        lo_px, hi_px = t * 3.5, t * 10.0                        # 無比例尺：以牆厚（≈15cm）推估
    h_img, w_img = ink_clean.shape
    seals: list[dict] = []

    for lbl in range(1, n):
        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        w = int(stats[lbl, cv2.CC_STAT_WIDTH])
        h = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if not (lo_px <= w <= hi_px and lo_px <= h <= hi_px):
            continue
        if not (0.65 <= w / max(h, 1) <= 1.55):        # 近正方形
            continue
        if area > w * h * 0.42:                        # 稀疏筆劃，排除實心／密集物件
            continue
        ys, xs = np.nonzero(labels[y:y + h, x:x + w] == lbl)
        if xs.size < 12:
            continue
        r = (w + h) / 2.0
        best = None
        for cx, cy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            d = np.hypot(xs - cx, ys - cy)
            ring = float(np.mean((d >= r * 0.82) & (d <= r * 1.18)))  # 落在細環帶的比例
            if best is None or ring > best[0]:
                best = (ring, cx, cy)
        ring, hx, hy = best
        if ring < 0.45:                                # 不成弧
            continue

        # 鉸鏈相鄰的兩邊：取牆體較多的那一邊為門洞
        hinge = (x + hx, y + hy)
        cand = [((hinge[0], hinge[1]), (x + (w - 1 - hx), y + hy)),   # 水平邊
                ((hinge[0], hinge[1]), (x + hx, y + (h - 1 - hy)))]   # 垂直邊
        scored = []
        for p1, p2 in cand:
            probe = np.zeros_like(wall_mask)
            cv2.line(probe, p1, p2, 255, max(3, int(round(t * 1.6))))
            scored.append((int(np.count_nonzero(cv2.bitwise_and(probe, wall_mask))), p1, p2))
        scored.sort(key=lambda s: -s[0])
        hits, p1, p2 = scored[0]
        if hits < max(6, int(r * 0.5)):                # 兩側都沒牆 → 不是門
            continue
        if not (0 <= p1[0] < w_img and 0 <= p1[1] < h_img):
            continue
        seals.append({"p1": [float(p1[0]), float(p1[1])], "p2": [float(p2[0]), float(p2[1])],
                      "width_px": float(r)})
    return seals


def _detect_rooms(wall_mask: np.ndarray, elements: list[dict], t: float,
                  groups: Optional[list[dict]] = None,
                  furniture: Optional[list[dict]] = None,
                  arc_seals: Optional[list[dict]] = None) -> list[dict]:
    """第一軌：封門 → 泛洪填充 → 取外接矩形。

    ① 二值化取牆體遮罩（wall_mask 由步驟 2 產生）
    ② 封住所有門洞，依可靠度兩道並用：
       #1 門弧線（四分之一圓）：弧的鉸鏈邊即門洞兩側牆端，沿其連線封住（arc_seals）
       #2 牆線斷點配對：步驟 3 的共線牆群已算出每個開口，開口元素兩端點即牆端；
       共線牆群再以全長補線，最後形態學閉運算修補殘餘小縫。
    ③ 泛洪填充：連通元件分析等同於「以每點為種子灌水」，一次得到所有區域；
       家具中心點所在的連通區域，就是該家具所屬的空間（回寫 room_id）。
    ④ 取該區域的外接矩形為空間範圍。

    有家具落在其中的區域＝有種子的空間（優先保留）；其餘封閉區域仍列出為未判定空間。
    """
    h_img, w_img = wall_mask.shape
    sealed = wall_mask.copy()
    thick = max(3, int(round(t)))
    for s in arc_seals or []:                  # ②-#1 門弧鉸鏈邊 → 封門（最可靠）
        cv2.line(sealed, (int(round(s["p1"][0])), int(round(s["p1"][1]))),
                 (int(round(s["p2"][0])), int(round(s["p2"][1]))), 255, thick)
    for e in elements:
        p1 = (int(round(e["p1"][0])), int(round(e["p1"][1])))
        p2 = (int(round(e["p2"][0])), int(round(e["p2"][1])))
        cv2.line(sealed, p1, p2, 255, thick)   # ②-#2 開口（牆端點配對）兩端連線
    for g in groups or []:
        if len(g["segs"]) < 2:
            continue  # 共線多段牆之間的任意寬缺口一律封閉
        lo, hi, pos = int(round(g["lo"])), int(round(g["hi"])), int(round(g["pos"]))
        p1, p2 = ((lo, pos), (hi, pos)) if g["axis"] == "h" else ((pos, lo), (pos, hi))
        cv2.line(sealed, p1, p2, 255, thick)
    k = _odd(t * 1.5)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    sealed = cv2.morphologyEx(sealed, cv2.MORPH_CLOSE, kernel)

    free = (sealed == 0).astype(np.uint8)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(free, 4)  # ③ 泛洪填充

    # ③' 以每個家具中心為種子，查出所在的填充區域
    seeds: dict[int, list[dict]] = {}
    for item in furniture or []:
        item["room_id"] = None
        cx = int(round(item["bbox"][0] + item["bbox"][2] / 2.0))
        cy = int(round(item["bbox"][1] + item["bbox"][3] / 2.0))
        if not (0 <= cx < w_img and 0 <= cy < h_img):
            continue
        lbl = int(labels[cy, cx])
        if lbl > 0:
            seeds.setdefault(lbl, []).append(item)

    rooms: list[dict] = []
    min_area = int((t * 4) ** 2)  # 過小碎片不視為空間（有種子者不受此限）
    for lbl in range(1, n):
        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        ww = int(stats[lbl, cv2.CC_STAT_WIDTH])
        hh = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        if x <= 1 or y <= 1 or x + ww >= w_img - 1 or y + hh >= h_img - 1:
            continue  # 與影像邊界相連者視為室外
        if area < min_area and lbl not in seeds:
            continue
        mask = (labels == lbl).astype(np.uint8)
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        yy, xx = np.unravel_index(int(np.argmax(dist)), dist.shape)  # 最內點，標籤不會壓牆
        rooms.append({
            "area_px": area,
            "bbox": [x, y, ww, hh],              # ④ 填充區域的外接矩形
            "centroid": [float(cents[lbl][0]), float(cents[lbl][1])],
            "label_pos": [float(xx), float(yy)],
            "_seed_label": lbl,
        })
    rooms.sort(key=lambda r: -r["area_px"])
    label_of: dict[str, int] = {}
    for i, r in enumerate(rooms, 1):
        r["id"] = f"R{i}"
        for item in seeds.get(r["_seed_label"], []):
            item["room_id"] = r["id"]   # 泛洪歸屬（比外框包含更準：L 形房間不會誤收鄰室家具）
        label_of[r["id"]] = r.pop("_seed_label")
        r["no_furniture"] = not seeds.get(label_of[r["id"]])
    # 寬度場：室內每點距最近牆體多遠（房間中央＝高地，門口／通道＝低谷）
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 5)
    return rooms, {"labels": labels, "dist": dist, "label_of": label_of}


def _make_grow_fn(geo: dict, furniture: list[dict], scale_max: int = 260):
    """回傳 grow(room, clusters) → 各種子群生長後的外接框（B1/B2 由此保證）。

    B1 牆體不可跨越：生長只在該空間的泛洪區域內進行（牆本來就不在區域裡）。
    B2 家具不可切開：生長完成後，每件家具外框內以多數決歸屬，整框強制同一區。
    為效能在縮圖上運算（門寬 90cm 在縮圖仍有十餘像素，瓶頸判定不受影響）。
    """
    labels_full, dist_full, label_of = geo["labels"], geo["dist"], geo["label_of"]
    h, w = labels_full.shape
    s = min(1.0, scale_max / max(h, w))
    sw, sh = max(1, int(w * s)), max(1, int(h * s))
    labels_s = cv2.resize(labels_full.astype(np.int32), (sw, sh), interpolation=cv2.INTER_NEAREST)
    dist_s = cv2.resize(dist_full, (sw, sh), interpolation=cv2.INTER_NEAREST) * s

    def grow(room: dict, clusters: list[list[dict]]) -> list[list[float]]:
        lbl = label_of.get(room["id"])
        if lbl is None:
            return []
        free = labels_s == lbl
        if not free.any():
            return []
        seed_masks = []
        for cl in clusters:
            m = np.zeros(free.shape, bool)
            for it in cl:
                x, y, bw, bh = it["bbox"]
                x0, y0 = int(x * s), int(y * s)
                x1, y1 = int(np.ceil((x + bw) * s)), int(np.ceil((y + bh) * s))
                m[max(0, y0):min(sh, y1), max(0, x0):min(sw, x1)] = True
            seed_masks.append(m & free)
        if any(not m.any() for m in seed_masks):
            return []      # 種子落在區域外（座標異常）→ 交回退回路徑處理
        grown = _bottleneck_grow(free, dist_s, seed_masks)
        # B2：每件家具整框歸同一區（多數決），徹底消除「餐桌被切兩半」
        for cl_i, cl in enumerate(clusters, 1):
            for it in cl:
                x, y, bw, bh = it["bbox"]
                x0, y0 = max(0, int(x * s)), max(0, int(y * s))
                x1, y1 = min(sw, int(np.ceil((x + bw) * s))), min(sh, int(np.ceil((y + bh) * s)))
                if x1 > x0 and y1 > y0:
                    grown[y0:y1, x0:x1] = cl_i
        out: list[dict] = []
        for i in range(1, len(clusters) + 1):
            ys, xs = np.nonzero(grown == i)
            if xs.size == 0:
                out.append({})
                continue
            out.append({
                "ext": [float(xs.min() / s), float(ys.min() / s),
                        float((xs.max() + 1) / s), float((ys.max() + 1) / s)],
                "area_px": float(xs.size) / (s * s),   # 生長區域實際面積（還原原尺度）
            })
        return out

    return grow


# ---------------------------------------------------------------------------
# 步驟 4：校準（OCR 標註 ↔ 牆線全長配對；手動兩點為保底）
# ---------------------------------------------------------------------------
def _calibrate_by_ocr(dims: list[dict], groups: list[dict], t: float) -> tuple[Optional[float], int, Optional[float]]:
    """以 OCR 標註與牆線全長配對推估 mm/px。

    配對條件（三者皆須成立）：
      1. 標籤沿牆方向落在牆段跨距的「中央區域」——真實標註寫在所量牆段中段，
         不會落在端點外。此條件可排除標籤恰好位於垂直牆延長線上的假配對。
      2. 標籤與牆的垂直距離在合理範圍內。
      3. 換算比例落在合理區間。
    """
    candidates: list[float] = []
    for d in dims:
        for g in groups:
            span = g["hi"] - g["lo"]
            if span < t * 3:
                continue
            if g["axis"] == "h":
                along, across = d["cx"], abs(d["cy"] - g["pos"])
            else:
                along, across = d["cy"], abs(d["cx"] - g["pos"])
            centre = (g["lo"] + g["hi"]) / 2.0
            # 標籤須位於跨距中央 60% 內（容許至少 t*2 的緩衝，短牆才不會過嚴）
            if abs(along - centre) > max(span * 0.30, t * 2):
                continue
            if across > t * 12:
                continue
            r = d["value"] / span
            if _RATIO_MIN <= r <= _RATIO_MAX:
                candidates.append(r)
    if not candidates:
        return None, 0, None
    med = float(np.median(candidates))
    spread = float(max(abs(c - med) for c in candidates) / med) if len(candidates) > 1 else 0.0
    if len(candidates) >= 2 and spread > 0.06:
        return None, len(candidates), spread  # 候選互相矛盾，不採用
    return med, len(candidates), spread


def analyze_png(image_bytes: bytes, manual_ref: Optional[dict] = None,
                source_name: Optional[str] = None,
                overrides: Optional[list] = None) -> dict:
    """主流程。manual_ref = {x1, y1, x2, y2, length_mm}（原圖像素座標）；
    source_name 供待確認庫 manifest 記錄來源檔名；
    overrides = 使用者定義清單 [{bbox, class, action}]，視為事實疊加於模型判斷之上。"""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("無法解讀影像檔，請確認為有效的 PNG/JPG。")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    warnings: list[str] = ["本版採 Manhattan 假設（僅水平／垂直牆），斜牆不在辨識範圍。"]

    # 1. OCR 收割（先於任何屏蔽）
    dims, text_boxes, ocr_warnings = _harvest_text(gray)
    warnings.extend(ocr_warnings)

    # 2. 屏蔽：文字框 → 家具細線
    ink_clean = _mask_text(ink, text_boxes)
    t = _estimate_wall_thickness(ink_clean)
    wall_mask = _structural_mask(ink_clean, t)

    # 3. 結構量測
    elements, groups = _detect_elements(wall_mask, ink_clean, t)
    if not elements:
        warnings.append("未偵測到牆體結構，請確認圖面對比度或改用 DXF。")

    # 4. 校準：OCR 優先、手動保底；兩者衝突時以手動為準
    mm_per_px, samples, spread = _calibrate_by_ocr(dims, groups, t)
    method = "ocr" if mm_per_px else "none"
    if samples == 1 and method == "ocr":
        warnings.append("OCR 校準僅單一樣本，建議以手動校準交叉確認。")
    if spread is not None and mm_per_px is None and samples >= 2:
        warnings.append(f"OCR 標註彼此矛盾（離散 {spread:.1%}），未採用自動校準。")

    if manual_ref:
        px = float(np.hypot(manual_ref["x2"] - manual_ref["x1"], manual_ref["y2"] - manual_ref["y1"]))
        if px > 1:
            manual_ratio = manual_ref["length_mm"] / px
            if mm_per_px and abs(manual_ratio - mm_per_px) / mm_per_px > 0.10:
                warnings.append(
                    f"手動校準（{manual_ratio:.3f} mm/px）與 OCR 校準（{mm_per_px:.3f} mm/px）"
                    "差異超過 10%，以手動為準。")
                mm_per_px, method, samples, spread = manual_ratio, "manual", 1, None
            elif not mm_per_px:
                mm_per_px, method, samples, spread = manual_ratio, "manual", 1, None

    if mm_per_px is None:
        warnings.append("未取得比例：目前僅輸出像素長度。可於前端點兩點輸入已知長度進行手動校準。")

    for i, e in enumerate(elements, 1):
        e["id"] = f"{'W' if e['kind'] == 'wall' else 'O'}{i}"
        e["length_mm"] = round(e["px_length"] * mm_per_px, 1) if mm_per_px else None

    # 5. 家具辨識（樣板相似度＋ML 雙軌）→ 以家具為種子做空間辨識（兩軌）
    if load_templates():
        furniture, uncertain = detect_furniture(ink_clean, wall_mask, t, mm_per_px,
                                                source_gray=gray, source_name=source_name)
        # 5.1 套用使用者定義：排除最初錯誤的辨識，改以使用者的類別為準（信心 1.00），
        #     並把更新後的正確裁圖存入訓練庫，供「重新訓練模型」提升信心
        from furniture_match import apply_overrides
        furniture, uncertain, override_stats = apply_overrides(
            furniture, uncertain, overrides or [], source_gray=gray, source_name=source_name)
        # 5.2 第一軌：封門（門弧＋牆端點配對）→ 泛洪填充 → 外接矩形
        #     以家具中心為種子，「框選」與「歸屬」一次完成
        arc_seals = _door_arc_seals(ink_clean, wall_mask, t, mm_per_px)
        rooms, geo = _detect_rooms(wall_mask, elements, t, groups, furniture, arc_seals)
        if arc_seals:
            warnings.append(f"偵測到 {len(arc_seals)} 處門弧，已用於封閉門洞（空間切割更準確）。")
        # 5.3 權重投票命名；區內 ≥2 種機能者判為開放空間 → 第二軌：錨點種子＋瓶頸生長
        furniture, conflicted = assign_rooms(furniture, rooms, mm_per_px,
                                             grow_fn=_make_grow_fn(geo, furniture))
        # 5.4 分區即空間：開放空間依機能拆成獨立空間，畫面只留一套空間標籤
        from furniture_match import split_rooms_by_zones
        rooms = split_rooms_by_zones(furniture, rooms)
        # 房間規則反查：矛盾剔除項（廚房內的衛浴類）送進待確認庫
        from furniture_match import _now, _save_uncertain, append_manifest
        import base64 as _b64
        for item in conflicted:
            bx, by, bw, bh = [int(round(v)) for v in item["bbox"]]
            fname, png, created = _save_uncertain(gray, bx, by, bw, bh)
            uncertain.append({"bbox": item["bbox"], "file": fname, "reason": "room_conflict",
                              "guess": item["label"], "guess_score": item["score"],
                              "png_b64": _b64.b64encode(png).decode("ascii") if png else None})
            if created and fname:
                append_manifest({"file": fname, "source": source_name, "reason": "room_conflict",
                                 "bbox": [bx, by, bw, bh], "guess": item["label"],
                                 "guess_score": item["score"], "at": _now()})
        for i, u in enumerate(uncertain, 1):
            u["id"] = f"U{i}"  # 矛盾項併入後重新編號
        if override_stats["applied"]:
            warnings.append(
                f"已套用 {override_stats['applied']} 項使用者定義"
                f"（排除原偵測 {override_stats['suppressed']} 項"
                f"、新增訓練樣本 {override_stats['saved']} 張）；"
                "按「重新訓練模型」讓模型學會這些更正。")
        if not mm_per_px:
            warnings.append("家具辨識以牆厚（≈15cm）估算比例尺，校準後結果更可靠。")
        if not furniture:
            warnings.append("未辨識到家具符號，空間用途無法判定；可於 room_recognition/ 補充該圖畫風的樣板。")
        if uncertain:
            warnings.append(
                f"有 {len(uncertain)} 件物件無法辨識，已裁存至 room_recognition/uncertain/；"
                "整理進對應類別資料夾（或新建負類資料夾如 plant/）後，系統會自動重新訓練。")
        try:
            from furniture_ml import model_info
            ml_info = model_info()
            if ml_info.get("training"):
                warnings.append("辨識模型正在背景重新訓練（納入最新回饋資料），完成後自動生效。")
        except Exception:
            ml_info = None
    else:
        furniture, uncertain, ml_info = [], [], None
        override_stats = {"applied": 0, "suppressed": 0, "saved": 0}
        rooms, _geo = _detect_rooms(wall_mask, elements, t, groups)  # 無種子：仍列出封閉區域
        warnings.append("找不到家具樣板庫（room_recognition/），已略過家具辨識與空間判定。")

    for r in rooms:
        if mm_per_px:
            m2 = r["area_px"] * (mm_per_px ** 2) / 1e6
            r["area_m2"] = round(m2, 2)
            r["area_m2_min"] = round(m2 * 0.95, 2)
            r["area_m2_max"] = round(m2 * 1.05, 2)
            r["w_m"] = round(r["bbox"][2] * mm_per_px / 1000, 2)
            r["h_m"] = round(r["bbox"][3] * mm_per_px / 1000, 2)
        else:
            r["area_m2"] = r["area_m2_min"] = r["area_m2_max"] = None
            r["w_m"] = r["h_m"] = None

    # 邊全長加總：同一直線上由多段牆（含開口）組成的邊，補上總長標註
    edge_totals: list[dict] = []
    for g in groups:
        if len(g["segs"]) < 2:
            continue  # 單段牆本身已有標籤，毋須加總
        span = g["hi"] - g["lo"]
        if span < t * 3:
            continue
        if g["axis"] == "h":
            p1, p2 = (g["lo"], g["pos"]), (g["hi"], g["pos"])
        else:
            p1, p2 = (g["pos"], g["lo"]), (g["pos"], g["hi"])
        edge_totals.append({"axis": g["axis"], "p1": p1, "p2": p2,
                            "px_length": round(span, 1),
                            "length_mm": round(span * mm_per_px, 1) if mm_per_px else None})
    for i, et in enumerate(edge_totals, 1):
        et["id"] = f"E{i}"

    # 屏蔽後結構圖（黑牆白底）供前端檢視
    structural = cv2.bitwise_not(wall_mask)
    ok, buf = cv2.imencode(".png", structural)
    structural_b64 = base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    return {
        "source": "png",
        "image_size": [int(bgr.shape[1]), int(bgr.shape[0])],
        "calibration": {"method": method, "mm_per_px": round(mm_per_px, 4) if mm_per_px else None,
                        "samples": samples, "spread": round(spread, 4) if spread is not None else None},
        "elements": elements,
        "rooms": rooms,
        "furniture": furniture,
        "uncertain": uncertain,
        "ml_info": ml_info,
        "override_stats": override_stats,
        "edge_totals": edge_totals,
        "warnings": warnings,
        "structural_png_b64": structural_b64,
        "original_png_b64": base64.b64encode(cv2.imencode(".png", bgr)[1].tobytes()).decode("ascii"),
        "wall_thickness_px": round(t, 1),
    }
