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
import json
import os
import re
import shutil
from pathlib import Path
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
    # 移除殘餘小碎片。門檻必須低於「牆墩」面積——兩開口之間的短牆
    # （長 ≈2.5t × 厚 t ＝ 2.5t²）是合法結構，砍掉它會讓兩個開口
    # 靜默併成一個大開口（開口資訊在破壞性運算中消失，自檢還會通過）
    n, labels, stats, _ = cv2.connectedComponentsWithStats((opened > 0).astype(np.uint8), 8)
    min_area = int(t * t * 1.8)
    keep = np.zeros_like(opened)
    for lbl in range(1, n):
        if stats[lbl, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == lbl] = 255
    return keep


def _carve_band_openings(wall_mask: np.ndarray, ink_clean: np.ndarray,
                         t: float) -> tuple[np.ndarray, list[dict]]:
    """牆帶異物偵測（線寬三分類＋帶內取樣）：把被吸進牆層的門窗線挖出斷口。

    細牆畫風的平面圖裡，門扇／窗線與牆同粗，形態學抽牆會把它們一併留在
    牆層 → 牆體連續無斷口 → 端點配對在結構上永遠找不到這些門窗。
    沿每道牆段取「橫斷面」逐位置分類：
      - 實牆：整個厚度為一段連續墨水（單一粗段）
      - 異物：斷面出現 ≥2 段分離墨水（窗雙線／滑門錯位門板），或最長段
        明顯細於本段牆的中位厚度（門扇、軌道）
    異常斷面連續達最小門寬的一半以上 → 在牆層挖出該段（開洞是必要的，
    不是補強——窗永遠站在牆內部，不挖就永遠抓不到）。門窗線仍留在
    ink_clean，挖洞後的縫隙由開口分類器照常判門／窗。
    整段幾乎都異常（>70%）者不挖——那是空心雙線牆的畫風，不是內嵌門窗。
    """
    carved = wall_mask.copy()
    log: list[dict] = []
    # 最小開口長度：沿牆連續 20px 以上（濾除單點雜訊），並隨牆厚放大
    min_run = max(20, int(t * 1.2))
    h_img, w_img = wall_mask.shape
    # 吸收發生在「群組層」：窗線與牆段被併進同一共線群組，群組看起來連續。
    # 因此沿整條群組帶掃描，而非逐段——逐段的橫斷面各自都正常。
    for axis in ("h", "v"):
        segs = _extract_strips(wall_mask, t, axis)
        for g in _group_collinear(segs, t):
            a, b = int(round(g["lo"])), int(round(g["hi"]))
            if b - a < min_run * 2:
                continue
            pos = int(round(g["pos"]))
            wall_th_nom = float(np.median([s["thickness"] for s in g["segs"]]))
            band_half = int(round(wall_th_nom / 2.0 + 2))   # 緊貼牆帶：避免掃到貼牆家具
            if axis == "h":
                band = (ink_clean[max(0, pos - band_half):min(h_img, pos + band_half + 1),
                                  max(0, a):min(w_img, b)] > 0)
            else:
                band = (ink_clean[max(0, a):min(h_img, b),
                                  max(0, pos - band_half):min(w_img, pos + band_half + 1)] > 0).T
            if band.size == 0:
                continue
            n_pos = band.shape[1]
            col = band.astype(np.int8)
            diff = np.diff(col, axis=0, prepend=0)
            runs_n = np.zeros(n_pos, np.int32)
            run_max = np.zeros(n_pos, np.int32)
            for j in range(n_pos):
                starts = np.nonzero(diff[:, j] == 1)[0]
                runs_n[j] = len(starts)
                if len(starts):
                    ends = np.nonzero(diff[:, j] == -1)[0]
                    if len(ends) < len(starts):
                        ends = np.append(ends, band.shape[0])
                    run_max[j] = int((ends[:len(starts)] - starts).max())
            solid_vals = run_max[(runs_n == 1) & (run_max >= wall_th_nom * 0.7)]
            wall_th = float(np.median(solid_vals)) if solid_vals.size >= n_pos * 0.2 else wall_th_nom
            if wall_th < 3:
                continue
            # 剖面掃描門檻（實測：開口處連續墨長僅為牆厚的 5–9%，十倍安全邊際，
            # 門檻設 0.15–0.5 結果相同 → 取 0.3，不需調參）：
            #   連續墨 < 牆厚×0.3 → 開口（門扇線、窗線、純白子段一併涵蓋——
            #   滑門的門扇之間有純白空隙，併入才不會把一個開口切成碎段）
            #   細牆畫風（線寬達牆厚一半、比值失效）由後兩條補上：
            #   ≥2 段分離墨水（雙線窗），或單段明顯偏細（門扇差 2px 以上）
            anomalous = ((run_max < wall_th * 0.3)
                         | ((runs_n >= 2) & (run_max < wall_th * 0.8))
                         | ((runs_n == 1) & (run_max < wall_th * 0.75)
                            & (run_max <= wall_th - 2)))
            if anomalous.mean() > 0.70:
                continue   # 空心雙線牆畫風：整條皆異常 → 不是內嵌門窗，不挖
            j = 0
            while j < n_pos:
                if not anomalous[j]:
                    j += 1
                    continue
                k0 = j
                while j < n_pos and anomalous[j]:
                    j += 1
                if j - k0 < min_run:
                    continue
                lo_c, hi_c = a + k0, a + j
                half_cut = band_half + 1
                if axis == "h":
                    carved[max(0, pos - half_cut):min(h_img, pos + half_cut + 1), lo_c:hi_c] = 0
                    p1, p2 = [float(lo_c), float(pos)], [float(hi_c), float(pos)]
                else:
                    carved[lo_c:hi_c, max(0, pos - half_cut):min(w_img, pos + half_cut + 1)] = 0
                    p1, p2 = [float(pos), float(lo_c)], [float(pos), float(hi_c)]
                log.append({"p1": p1, "p2": p2, "axis": axis,
                            "width_px": float(j - k0), "source": "band_carve"})
    return carved, log


def _band_strip(img: np.ndarray, axis: str, pos: float, half: int,
                a: int, b: int) -> np.ndarray:
    """沿牆帶取水平長條（v 軸自動轉置）：rows=厚度向、cols=沿牆向。"""
    h_img, w_img = img.shape
    p = int(round(pos))
    if axis == "h":
        return img[max(0, p - half):min(h_img, p + half + 1), max(0, a):min(w_img, b)]
    return img[max(0, a):min(h_img, b), max(0, p - half):min(w_img, p + half + 1)].T


def measure_manual_opening(image_bytes: bytes, x1: float, y1: float,
                           x2: float, y2: float, kind: str,
                           mm_per_px: Optional[float] = None,
                           source_name: Optional[str] = None) -> dict:
    """使用者自訂開口：使用者給位置，系統給尺寸（三層精度階梯）。

    互動約束：開口鎖定在使用者點選的牆帶中心線上、不可跨牆、不可與既有
    開口重疊、寬度須落在 60–350 cm。禁止使用者直接拖出尺寸數值——點擊
    只當「大約位置」，實際邊界由局部幾何決定：
      第一層：牆層在該處有乾淨缺口（含挖洞後）→ 缺口邊界（最高精度）
      第二層：無缺口，但附近有可吸附特徵（牆段端點、垂直牆面、線寬變化）→ 吸附
      第三層：完全無特徵 → 使用者兩點投影（輸出標明層級，報表須另行標記）
    情況甲＝原始牆層實心連續（門窗被併入牆層）：幾何不變、即時套用。
    情況乙＝真實缺口未封：補上後房間切割會變，前端須重跑空間辨識。
    同型批次：以該區帶狀裁圖為模板掃全圖，回傳相似位置候選（一次確認全標）。
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"error": "無法解讀影像檔。"}
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    t = _estimate_wall_thickness(ink)
    wall0 = _structural_mask(ink, t)
    wall, _carved = _carve_band_openings(wall0, ink, t)
    elements, groups = _detect_elements(wall, ink, t)

    # ① 點選的牆：兩點中點距哪條共線牆帶最近（帶內 ±3 倍牆厚、沿軸在跨距內）
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    best = None
    for g in groups:
        coord, along = (my, mx) if g["axis"] == "h" else (mx, my)
        if not (g["lo"] - t <= along <= g["hi"] + t):
            continue
        d = abs(coord - g["pos"])
        if d <= t * 3 and (best is None or d < best[0]):
            best = (d, g)
    if best is None:
        return {"error": "點選位置附近沒有牆——請先點一道牆線，再沿牆點出開口兩端。"}
    g = best[1]
    axis, pos = g["axis"], float(g["pos"])
    ua = (min(x1, x2) if axis == "h" else min(y1, y2))
    ub = (max(x1, x2) if axis == "h" else max(y1, y2))
    ua, ub = max(g["lo"], ua), min(g["hi"], ub)     # 鎖在同一牆帶上，不可跨牆
    # 單擊模式（與自動偵測共用同一機制）：使用者點一下開口的白色區域，
    # 邊界由同一套剖面邏輯計算——不必點兩端
    single = (ub - ua) < 4

    # ② 不可與既有開口重疊
    mid0 = (ua + ub) / 2.0
    for e in elements:
        if e["kind"] == "wall":
            continue
        e_axis = "h" if abs(e["p2"][0] - e["p1"][0]) >= abs(e["p2"][1] - e["p1"][1]) else "v"
        if e_axis != axis:
            continue
        e_pos = e["p1"][1] if axis == "h" else e["p1"][0]
        if abs(e_pos - pos) > t * 1.5:
            continue
        elo = min(e["p1"][0], e["p2"][0]) if axis == "h" else min(e["p1"][1], e["p2"][1])
        ehi = max(e["p1"][0], e["p2"][0]) if axis == "h" else max(e["p1"][1], e["p2"][1])
        if (min(ub, ehi) - max(ua, elo) > t) or (single and elo - t <= mid0 <= ehi + t):
            return {"error": f"與既有開口（{e['kind']}）重疊——該處已自動辨識，毋須手動標記。"}

    half = int(round(t / 2 + 2))

    # ④ 三層精度階梯
    lo_g, hi_g = int(round(g["lo"])), int(round(g["hi"]))
    occ = _band_strip(wall, axis, pos, half, lo_g, hi_g).any(axis=0)
    tier = 3
    a_px, b_px = float(ua), float(ub)
    runs = []                                        # 挖洞後牆層的缺口 run
    j = 0
    while j < len(occ):
        if occ[j]:
            j += 1
            continue
        k0 = j
        while j < len(occ) and not occ[j]:
            j += 1
        runs.append((lo_g + k0, lo_g + j))
    mid = (ua + ub) / 2.0
    for ra, rb in runs:                              # 第一層：乾淨開口
        if ra <= mid <= rb or (min(ub, rb) - max(ua, ra)) >= 0.5 * (ub - ua):
            a_px, b_px, tier = float(ra), float(rb), 1
            break
    if tier == 3 and single:
        # 單擊但剖面找不到包含該點的開口段 → 請使用者改點兩端
        return {"error": "此處剖面上找不到開口輪廓——請沿牆點出開口『兩端』。",
                "need_span": True}
    if tier == 3:                                    # 第二層：特徵吸附
        feats: list[float] = []
        for s in g["segs"]:
            feats.extend((s["lo"], s["hi"]))
        for og in groups:                            # 垂直牆面（跨此帶者）
            if og["axis"] == axis:
                continue
            o_th = float(np.mean([s["thickness"] for s in og["segs"]])) if og["segs"] else t
            if og["lo"] - t <= pos <= og["hi"] + t:
                feats.extend((og["pos"] - o_th / 2, og["pos"] + o_th / 2))
        snap_r = max(t * 1.5, 8.0)
        def _snap(v: float) -> Optional[float]:
            near = [f for f in feats if abs(f - v) <= snap_r]
            return min(near, key=lambda f: abs(f - v)) if near else None
        na, nb = _snap(ua), _snap(ub)
        if na is not None or nb is not None:
            a_px = na if na is not None else float(ua)
            b_px = nb if nb is not None else float(ub)
            tier = 2
    if b_px <= a_px:
        a_px, b_px = float(ua), float(ub)
        tier = 3

    # ③ 情況甲／乙：原始牆層（挖洞前）在最終邊界範圍內是否實心連續
    band0 = _band_strip(wall0, axis, pos, half, int(a_px), int(b_px))
    solid_frac = float((band0.any(axis=0)).mean()) if band0.size else 0.0
    case = "A" if solid_frac >= 0.97 else "B"

    # ⑤ 寬度驗證：60–350 cm（無比例尺以牆厚 ≈15cm 推估）
    w_px = b_px - a_px
    lo_px, hi_px = (600.0 / mm_per_px, 3500.0 / mm_per_px) if mm_per_px else (t * 3.5, t * 23.0)
    if not (lo_px <= w_px <= hi_px):
        w_cm = f"{w_px * mm_per_px / 10:.0f} cm" if mm_per_px else f"{w_px:.0f} px"
        return {"error": f"量得的開口寬 {w_cm} 不在 60–350 cm 合理範圍，"
                         "請把兩點點在開口實際兩端附近。"}

    p1 = [a_px, pos] if axis == "h" else [pos, a_px]
    p2 = [b_px, pos] if axis == "h" else [pos, b_px]
    kind = kind if kind in ("door", "window", "opening") else "opening"
    opening = {"kind": kind, "p1": p1, "p2": p2, "px_length": round(w_px, 1),
               "length_mm": round(w_px * mm_per_px, 1) if mm_per_px else None,
               "axis": axis, "tier": tier, "case": case}

    # ⑥ 手動標記即訓練資料：帶狀裁圖入庫（位置由幾何確定、類型由人確認）
    saved = False
    if kind in ("door", "window"):
        saved = _save_manual_sample(gray, axis, pos, a_px, b_px, t, kind)

    # ⑦ 同型批次：同一張圖同種符號畫法必定一致 → 模板掃其餘牆帶
    candidates = _scan_similar_openings(ink, groups, elements, axis, pos,
                                        a_px, b_px, t, kind, mm_per_px)
    return {"opening": opening, "tier": tier, "case": case,
            "saved_sample": saved, "candidates": candidates}


def _save_manual_sample(gray: np.ndarray, axis: str, pos: float,
                        a: float, b: float, t: float, kind: str) -> bool:
    """手動標記的帶狀裁圖 → door/window 樣本資料夾（hash 去重）。

    這是品質最高的標註：位置由幾何確定、類型由人確認。指紋快取會讓
    門窗 CNN 在下次辨識自動重訓吸收——跨圖泛化靠辨識器變強，不靠人工重標。
    """
    import hashlib
    from furniture_match import _ASSET_DIR
    pad = int(round(max(t * 1.8, 10)))
    p = int(round(pos))
    h_img, w_img = gray.shape
    if axis == "h":
        crop = gray[max(0, p - pad):min(h_img, p + pad), max(0, int(a) - 2):min(w_img, int(b) + 2)]
    else:
        crop = gray[max(0, int(a) - 2):min(h_img, int(b) + 2), max(0, p - pad):min(w_img, p + pad)]
    if crop.size < 400:
        return False
    folder = "door" if kind == "door" else ("window" if (_ASSET_DIR / "window").is_dir() else "windows")
    d = _ASSET_DIR / folder
    d.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return False
    digest = hashlib.sha1(buf.tobytes()).hexdigest()[:10]
    fp = d / f"manual_{digest}.png"
    if fp.exists():
        return False
    fp.write_bytes(buf.tobytes())
    return True


def _scan_similar_openings(ink: np.ndarray, groups: list[dict], elements: list[dict],
                           axis0: str, pos0: float, a0: float, b0: float,
                           t: float, kind: str,
                           mm_per_px: Optional[float]) -> list[dict]:
    """同型批次套用：以剛標定的帶狀裁圖為模板，比對全圖其餘牆帶。

    模板來自圖面自身，比對條件設嚴（chamfer ≥ 0.62）、跳過既有開口，
    誤判率低。回傳候選 [{kind,p1,p2,px_length,score}]，由使用者一次確認。
    """
    from furniture_match import _open_chamfer, _open_norm
    half = int(round(t / 2 + max(3, int(t * 0.5))))
    tpl = _band_strip(ink, axis0, pos0, half, int(a0), int(b0))
    if tpl.size == 0 or (tpl > 0).sum() < 20:
        return []
    tpl_n = _open_norm(tpl)
    tw = int(b0 - a0)
    occupied: list[tuple[str, float, float, float]] = []
    for e in elements:
        if e["kind"] == "wall":
            continue
        ax = "h" if abs(e["p2"][0] - e["p1"][0]) >= abs(e["p2"][1] - e["p1"][1]) else "v"
        pp = e["p1"][1] if ax == "h" else e["p1"][0]
        lo = min(e["p1"][0], e["p2"][0]) if ax == "h" else min(e["p1"][1], e["p2"][1])
        hi = max(e["p1"][0], e["p2"][0]) if ax == "h" else max(e["p1"][1], e["p2"][1])
        occupied.append((ax, pp, lo, hi))
    occupied.append((axis0, pos0, a0, b0))          # 原標記處不再回報

    out: list[dict] = []
    step = max(6, tw // 4)
    for g in groups:
        span = g["hi"] - g["lo"]
        if span < tw:
            continue
        for start in np.arange(g["lo"], g["hi"] - tw + 1, step):
            a, b = float(start), float(start + tw)
            if any(ax == g["axis"] and abs(pp - g["pos"]) <= t * 1.5
                   and min(b, hi) - max(a, lo) > tw * 0.3
                   for ax, pp, lo, hi in occupied):
                continue
            win = _band_strip(ink, g["axis"], g["pos"], half, int(a), int(b))
            if win.size == 0 or (win > 0).sum() < 20:
                continue
            score = _open_chamfer(tpl_n, _open_norm(win))
            if score < 0.62:
                continue
            p1 = [a, float(g["pos"])] if g["axis"] == "h" else [float(g["pos"]), a]
            p2 = [b, float(g["pos"])] if g["axis"] == "h" else [float(g["pos"]), b]
            cand = {"kind": kind, "p1": p1, "p2": p2, "px_length": round(b - a, 1),
                    "length_mm": round((b - a) * mm_per_px, 1) if mm_per_px else None,
                    "score": round(float(score), 3)}
            occupied.append((g["axis"], float(g["pos"]), a, b))   # NMS：不重複回報
            out.append(cand)
            if len(out) >= 12:
                return out
    return out


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
                      lo: float, hi: float, wide: bool = False) -> str:
    """開口分類：門／窗／一般開口。

    以 room_recognition/door、windows 的樣板為辨識基準（門弧、窗雙線），
    輔以幾何啟發：窗＝牆帶內有平行細線；門＝開口一側有開啟弧（墨水量偏一側）。
    兩者皆不成立 → 一般「開口」。門寬／窗寬照常量測並以紅色標於圖上。
    """
    h_img, w_img = ink_clean.shape
    half_t = max(2, int(thickness / 2))
    gap = hi - lo
    p = int(round(pos))
    a, b = int(round(lo)), int(round(hi))

    # 牆帶（窗雙線的所在）。比牆厚略寬：窗的外緣線常貼在牆帶邊上、
    # 差一兩個像素就落在帶外；加寬量仍小於側區的跳開邊距（off），
    # 帶與側區不重疊、互不干擾。
    half_b = half_t + max(2, int(thickness * 0.3))
    if axis == "h":
        band = ink_clean[max(0, p - half_b):min(h_img, p + half_b), max(0, a):min(w_img, b)]
    else:
        band = ink_clean[max(0, a):min(h_img, b), max(0, p - half_b):min(w_img, p + half_b)].T
    # 窗＝「連續貫穿整個開口」的雙線：逐列取最長連續墨水段 ≥ 開口的 85%，
    # 且這種貫穿列須形成 ≥2 組彼此分離的列群（雙線窗的兩條玻璃線）。
    # 推拉門的兩片門板也躺在牆帶內：各只蓋住開口的一半多、任一列跑不完全程；
    # 唯獨上板下緣與下板上緣相接的那一列會拼成一條貫穿線——但只有一組，
    # 到不了雙線的門檻，不再被誤判成窗。
    window_hint = False
    if band.size and band.shape[1] >= 8:
        need = band.shape[1] * 0.85
        full_rows = []
        for row in (band > 0):
            run = best = 0
            for v in row:
                run = run + 1 if v else 0
                best = max(best, run)
            full_rows.append(best >= need)
        groups_n = sum(1 for i, f in enumerate(full_rows)
                       if f and (i == 0 or not full_rows[i - 1]))
        window_hint = groups_n >= 2

    # 剖面恆定性（實測分類規則）：窗線貫穿整個開口、剖面全程無純白子段；
    # 「整欄無墨」的連續段＝門扇間空隙 → 滑門或無門開口，絕不是窗。
    # 此為硬性排除：連深度學習判窗也擋（樣本沒涵蓋到的畫法一樣適用）。
    has_zero_sub = False
    if band.size and band.shape[1] >= 8:
        zrun = zbest = 0
        for empty in ~(band > 0).any(axis=0):
            zrun = zrun + 1 if empty else 0
            zbest = max(zbest, zrun)
        has_zero_sub = zbest >= 3
    if has_zero_sub:
        window_hint = False

    # 滑門（規則版分類器第①條）：帶內有兩條「約開口一半長」的細線
    # （兩片門板），起點錯開、合起來蓋滿開口——即使兩片門板全畫在
    # 牆帶內（側區完全乾淨）也抓得到。窗線是全長貫穿（>78%），不會誤中。
    slide_hint = False
    if band.size and band.shape[1] >= 12:
        w_b = band.shape[1]
        segs: list[tuple[int, int]] = []
        for row in (band > 0):
            best = run = s = e = cur_s = 0
            for i, v in enumerate(row):
                if v:
                    if run == 0:
                        cur_s = i
                    run += 1
                    if run > best:
                        best, s, e = run, cur_s, i + 1
                else:
                    run = 0
            if 0.35 * w_b <= best <= 0.78 * w_b:
                segs.append((s, e))
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                (s1, e1), (s2, e2) = segs[i], segs[j]
                # 兩片門板相接或之間留純白空隙皆可（實測空隙可達開口 1/4）
                if (abs(s1 - s2) >= 0.12 * w_b
                        and max(s1, s2) - min(e1, e2) <= 0.25 * w_b
                        and max(e1, e2) - min(s1, s2) >= 0.85 * w_b):
                    slide_hint = True
                    break
            if slide_hint:
                break

    # 超寬縫隙（> 一般門洞尺寸）：窗（連續貫穿雙線＝整面長窗）與
    # 滑門（兩條錯位半長門板線＝大型落地推拉門）皆可成立；
    # 平開門不可能這麼寬，側區又太深（會掃到家具），不做門弧判斷、
    # 不交深度學習。皆非 → opening（呼叫端不輸出元素）。
    if wide:
        if window_hint:
            return "window"
        return "door" if slide_hint else "opening"

    # 開口兩側各取一塊（門弧朝室內側，墨水量會明顯偏一側）。
    # off 比牆帶多跳開幾個像素：窗的雙線貼著牆帶邊緣，像素進位會滲入側區
    # 一兩行、誤觸發門弧訊號——跳開後窗側區歸零，門弧（大片墨水）不受影響。
    depth = int(max(gap, thickness * 3))
    off = half_t + max(3, int(thickness * 0.3))
    side_ink = []
    for direction in (-1, 1):
        # 區間兩端各自夾回影像內：負起點若寫成 max(0,y0)+depth，側區會
        # 反過來蓋到牆帶本身（把窗線誤當門弧墨水）——牆厚或開口貼邊時必現
        if axis == "h":
            y0 = p + (0 if direction > 0 else -depth) + direction * off
            reg = ink_clean[max(0, y0):max(0, y0 + depth), max(0, a):min(w_img, b)]
        else:
            x0 = p + (0 if direction > 0 else -depth) + direction * off
            reg = ink_clean[max(0, a):min(h_img, b), max(0, x0):max(0, x0 + depth)]
        side_ink.append(int((reg > 0).sum()) if reg.size else 0)
    # 門檻 gap*0.8：門弧（≈gap*1.57）與推拉門板邊線（≈gap*1.1）都要能觸發；
    # 窗線滲漏已由 off 邊距隔絕（窗的側區歸零），不會誤觸發。
    door_hint = max(side_ink) > gap * 0.8 and max(side_ink) > 2 * (min(side_ink) + 1)

    # 樣板比對：擷取開口周邊（含牆帶與門弧側）交給門/窗樣板分類器
    d = int(max(gap * 1.1, thickness * 3))
    if axis == "h":
        region = ink_clean[max(0, p - d):min(h_img, p + d), max(0, a - half_t):min(w_img, b + half_t)]
    else:
        region = ink_clean[max(0, a - half_t):min(h_img, b + half_t), max(0, p - d):min(w_img, p + d)]
    from furniture_match import _OPEN_ACCEPT, classify_opening_region
    tpl_kind, tpl_score = classify_opening_region(region)
    tpl_ok = tpl_score >= _OPEN_ACCEPT

    # 判斷順序（規則優先、深度學習斷尾）：
    #   1. 滑門（帶內兩條半長錯位門板線）或門弧／偏側門板 → 門
    #      （閉合門扇常畫在牆帶內、會偽裝成窗線，故門的規則先於窗）
    #   2. 牆帶內 ≥2 組貫穿雙線 → 窗
    #   3. 深度學習判窗（CNN 以 door/windows 樣本增強訓練；窗先於門，
    #      避免通用門樣本吃掉窗。無 torch 時退回 chamfer 樣板比對）
    #   4. 深度學習判門
    #   5. 皆無 → 一般開口
    if door_hint or slide_hint:
        return "door"
    if window_hint:
        return "window"
    if tpl_ok and tpl_kind == "window" and not has_zero_sub:
        return "window"   # 剖面有純白子段者即使 CNN 判窗也不採（窗線必貫穿）
    if tpl_ok and tpl_kind in ("door", "window"):
        return "door" if has_zero_sub or tpl_kind == "door" else "opening"
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
            # 開口：同一直線上相鄰牆段之間的縫隙。
            # 一般開口（門洞尺寸）上限 t*16；更寬到 t*90 者唯有「連續貫穿的
            # 窗線」能成立（橫跨整面牆的長窗），非窗即不視為開口元素。
            for cur, nxt in zip(g["segs"], g["segs"][1:]):
                gap = nxt["lo"] - cur["hi"]
                if gap < t * 0.9 or gap > t * 90:
                    continue
                wide = gap > t * 16
                th = (cur["thickness"] + nxt["thickness"]) / 2.0
                kind = _classify_opening(ink_clean, axis, g["pos"], th,
                                         cur["hi"], nxt["lo"], wide=wide)
                if wide and kind not in ("window", "door"):
                    continue   # 超寬縫非窗非滑門 → 開放空間分界，不視為開口元素
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


def _outer_ring_seal(sealed: np.ndarray, ink_clean: np.ndarray, t: float,
                     thick: int) -> Optional[np.ndarray]:
    """外輪廓縫合——追蹤最外圈牆體，斷口無條件封閉。

    以全部墨水（含畫成細線的窗）閉運算成建築本體，取最大連通元件的
    外輪廓描回封閉圖。外牆上的窗洞（雙細線）本來就在輪廓上 → 直接封住；
    小於 2 倍牆厚的無配對斷口也一併縫合。斷口的門/窗/開口標籤由
    元素分類負責，此步只保證「外圈 watertight、室內不漏到室外」。
    回傳建築外輪廓的實心遮罩（footprint），供面積守恆自檢使用。
    """
    k = _odd(t * 2)
    solid = cv2.morphologyEx(((ink_clean > 0) * np.uint8(255)), cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    if n <= 1:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    cnts, _ = cv2.findContours((labels == big).astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    cv2.drawContours(sealed, [cnt], -1, 255, thick)
    footprint = np.zeros_like(sealed)
    cv2.drawContours(footprint, [cnt], -1, 255, -1)
    return footprint


def _border_virtual_walls(wall_mask: np.ndarray, t: float) -> list[dict]:
    """影像邊界虛擬牆（規格步驟 2-⑤）：牆體接觸影像邊界時，邊界本身視為牆。

    裁切圖（局部平面圖）的牆在切邊處中斷，房間會漏到「室外」；
    在該側邊界沿接觸範圍補一道虛擬牆，切邊房間即可封閉。
    完整圖面四周有留白、牆不會貼邊 → 此步自然不動作。
    """
    h, w = wall_mask.shape
    m = 3
    out: list[dict] = []
    sides = [("top", wall_mask[:m, :].any(axis=0), "h", 1),
             ("bottom", wall_mask[h - m:, :].any(axis=0), "h", h - 2),
             ("left", wall_mask[:, :m].any(axis=1), "v", 1),
             ("right", wall_mask[:, w - m:].any(axis=1), "v", w - 2)]
    for name, hit, axis, pos in sides:
        idx = np.nonzero(hit)[0]
        if idx.size < 2:
            continue
        lo, hi = int(idx.min()), int(idx.max())
        if hi - lo < t * 2:
            continue   # 單點擦邊不成邊界牆
        p1, p2 = ((lo, pos), (hi, pos)) if axis == "h" else ((pos, lo), (pos, hi))
        out.append({"p1": [float(p1[0]), float(p1[1])], "p2": [float(p2[0]), float(p2[1])],
                    "source": "border", "side": name})
    return out


def _pt_near_seg(p: tuple, seg: dict, tol: float) -> bool:
    """點是否落在牆段的帶狀範圍內（含厚度與容差）。"""
    x, y = p
    half = seg["thickness"] / 2.0 + tol
    if seg["axis"] == "h":
        return (seg["lo"] - tol <= x <= seg["hi"] + tol) and abs(y - seg["pos"]) <= half
    return (seg["lo"] - tol <= y <= seg["hi"] + tol) and abs(x - seg["pos"]) <= half


def _wall_between(wall_mask: np.ndarray, p1: tuple, p2: tuple, t: float) -> bool:
    """兩點之間（中段 80%）是否有牆體阻擋。"""
    probe = np.zeros_like(wall_mask)
    a = (p1[0] * 0.9 + p2[0] * 0.1, p1[1] * 0.9 + p2[1] * 0.1)
    b = (p1[0] * 0.1 + p2[0] * 0.9, p1[1] * 0.1 + p2[1] * 0.9)
    cv2.line(probe, (int(round(a[0])), int(round(a[1]))),
             (int(round(b[0])), int(round(b[1]))), 255, max(2, int(t * 0.5)))
    return int(np.count_nonzero(cv2.bitwise_and(probe, wall_mask))) > t * 2


def _free_end_seals(groups: list[dict], wall_mask: np.ndarray, t: float,
                    mm_per_px: Optional[float] = None) -> list[dict]:
    """自由端封口（規格步驟 2-①②③）：顯式幾何操作、可記錄可回溯。

    ① 端點分類：連接 ≥2 段牆的端點＝接點；只屬一段者＝自由端（開口候選）
    ② 自由端配對（四條件全數成立）：共線（位置差 ≤1.5 倍牆厚，避免斜封口線）、
       距離 60–350 cm（無比例尺時以牆厚推估）、兩點間無牆體阻擋、牆厚相近。
       一個自由端只能用一次；多候選時距離最短優先。
    ③ 單邊開口：落單的自由端 → 至鄰近「垂直向牆面」的垂足連線（T 形/轉角開口）。
    同群組內的縫隙已由既有邏輯封閉；本函式補的是跨群組與轉角的漏網開口。
    """
    segs = [s for g in groups for s in g["segs"]]
    if mm_per_px:
        lo_px, hi_px = 600.0 / mm_per_px, 3500.0 / mm_per_px
    else:
        lo_px, hi_px = t * 3.5, t * 23.0

    ends: list[dict] = []
    for i, s in enumerate(segs):
        for which in ("lo", "hi"):
            p = ((s[which], s["pos"]) if s["axis"] == "h" else (s["pos"], s[which]))
            if any(j != i and _pt_near_seg(p, o, t * 1.2) for j, o in enumerate(segs)):
                continue   # 接點（T/L 交接）＝非開口
            ends.append({"i": i, "axis": s["axis"], "which": which, "p": p,
                         "th": s["thickness"]})

    cands: list[tuple] = []
    for ai in range(len(ends)):
        for bi in range(ai + 1, len(ends)):
            A, B = ends[ai], ends[bi]
            if A["axis"] != B["axis"] or A["i"] == B["i"]:
                continue
            off_axis = 1 if A["axis"] == "h" else 0
            if abs(A["p"][off_axis] - B["p"][off_axis]) > max(t * 1.5, 8.0):
                continue   # 共線容差：過寬會產生斜封口線
            d = abs(A["p"][1 - off_axis] - B["p"][1 - off_axis])
            if not (lo_px <= d <= hi_px):
                continue
            if max(A["th"], B["th"]) > 2.2 * min(A["th"], B["th"]):
                continue   # 牆厚相近
            if _wall_between(wall_mask, A["p"], B["p"], t):
                continue
            cands.append((d, ai, bi))

    seals: list[dict] = []
    used: set[int] = set()
    for d, ai, bi in sorted(cands):
        if ai in used or bi in used:
            continue
        used.update((ai, bi))
        seals.append({"p1": [float(v) for v in ends[ai]["p"]],
                      "p2": [float(v) for v in ends[bi]["p"]],
                      "source": "pair", "width_px": float(d)})

    for ei, E in enumerate(ends):                    # ③ 單邊開口 → 垂足
        if ei in used:
            continue
        best = None
        for s in segs:
            if s["axis"] == E["axis"]:
                continue
            coord = E["p"][1] if E["axis"] == "h" else E["p"][0]   # 沿垂直牆跨距的座標
            if not (s["lo"] - t <= coord <= s["hi"] + t):
                continue
            along = E["p"][0] if E["axis"] == "h" else E["p"][1]
            d = abs(s["pos"] - along)
            if not (lo_px <= d <= hi_px):
                continue
            face = s["pos"] - np.sign(s["pos"] - along) * s["thickness"] / 2.0
            foot = (face, coord) if E["axis"] == "h" else (coord, face)
            if _wall_between(wall_mask, E["p"], foot, t):
                continue
            if best is None or d < best[0]:
                best = (d, foot)
        if best:
            used.add(ei)
            seals.append({"p1": [float(v) for v in E["p"]],
                          "p2": [float(best[1][0]), float(best[1][1])],
                          "source": "foot", "width_px": float(best[0])})
    return seals


def _region_poly(mask: np.ndarray, eps: float, scale: float = 1.0) -> Optional[list]:
    """區域遮罩 → 簡化輪廓多邊形（原圖座標）。

    空間虛線框依此輪廓繪製：泛洪／分水嶺區域本來就止於牆體內緣，
    輪廓因此貼著牆邊、不越牆也不與鄰區重疊；開放處的分水嶺邊界
    就是「自動補上的隱形牆」。eps 為 approxPolyDP 容差（原圖像素）。
    """
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea).astype(np.float32)
    if scale != 1.0:
        c = c / scale
    approx = cv2.approxPolyDP(c, float(eps), True).reshape(-1, 2)
    if len(approx) < 3:
        return None
    return [[float(px), float(py)] for px, py in approx]


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
                  arc_seals: Optional[list[dict]] = None,
                  ink_clean: Optional[np.ndarray] = None,
                  mm_per_px: Optional[float] = None) -> list[dict]:
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
    seal_log: list[dict] = []                  # 每條封口線：座標／寬度／生成來源（可回溯）
    footprint = None
    if ink_clean is not None:                  # ①-0 外輪廓縫合：最外圈無條件封閉
        footprint = _outer_ring_seal(sealed, ink_clean, t, thick)
        if footprint is not None:
            seal_log.append({"source": "outer_ring"})
    for s in _border_virtual_walls(wall_mask, t):   # ①-0' 影像邊界虛擬牆（裁切圖）
        cv2.line(sealed, (int(round(s["p1"][0])), int(round(s["p1"][1]))),
                 (int(round(s["p2"][0])), int(round(s["p2"][1]))), 255, thick)
        seal_log.append(s)
    for s in arc_seals or []:                  # ②-#1 門弧鉸鏈邊 → 封門（最可靠）
        cv2.line(sealed, (int(round(s["p1"][0])), int(round(s["p1"][1]))),
                 (int(round(s["p2"][0])), int(round(s["p2"][1]))), 255, thick)
        seal_log.append({**s, "source": "door_arc"})
    for e in elements:
        p1 = (int(round(e["p1"][0])), int(round(e["p1"][1])))
        p2 = (int(round(e["p2"][0])), int(round(e["p2"][1])))
        cv2.line(sealed, p1, p2, 255, thick)   # ②-#2 開口（牆端點配對）兩端連線
        if e.get("kind") != "wall":
            seal_log.append({"p1": list(e["p1"]), "p2": list(e["p2"]),
                             "source": f"element_{e.get('kind', 'opening')}",
                             "width_px": e.get("px_length")})
    # ②-#2' 共線群組縫隙：逐縫封閉並套「與自由端配對相同」的距離上限
    # （60–350cm；無比例尺以牆厚推估）。舊做法是整條群組全長無條件補線，
    # 會在開放空間中央拉出數公尺、無紀錄的封口線（中央誤切割的兇手）；
    # 超過上限的縫是真的空間分界（開放式廳區），留開，交給錨點生長。
    gap_cap = (3500.0 / mm_per_px) if mm_per_px else t * 23.0
    for g in groups or []:
        if len(g["segs"]) < 2:
            continue
        pos = int(round(g["pos"]))
        for cur, nxt in zip(g["segs"], g["segs"][1:]):
            gap = nxt["lo"] - cur["hi"]
            if gap <= 0 or gap > gap_cap:
                continue
            a, b = int(round(cur["hi"])), int(round(nxt["lo"]))
            p1, p2 = ((a, pos), (b, pos)) if g["axis"] == "h" else ((pos, a), (pos, b))
            cv2.line(sealed, p1, p2, 255, thick)
            if gap > t:   # 微小施工縫不進清單，避免噪音
                seal_log.append({"p1": [float(p1[0]), float(p1[1])],
                                 "p2": [float(p2[0]), float(p2[1])],
                                 "source": "group_gap", "width_px": float(gap)})
    for s in _free_end_seals(groups or [], wall_mask, t, mm_per_px):
        cv2.line(sealed, (int(round(s["p1"][0])), int(round(s["p1"][1]))),
                 (int(round(s["p2"][0])), int(round(s["p2"][1]))), 255, thick)
        seal_log.append(s)                     # ②-#3 自由端配對／垂足封口（跨群組、轉角）
    # 收尾閉運算只修殘餘小縫：結構元素（1.5 倍牆厚 ≈ 22cm）小於最小門寬
    # （60cm），不會把未記錄的門洞偷偷封死——顯式封口在前，此步僅補針孔。
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
    if mm_per_px:                 # 規格步驟 3：面積 < 1.5 m² 剔除（以實體尺度）
        min_area = max(min_area, int(1.5e6 / (mm_per_px ** 2)))
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
            "poly": _region_poly(mask, eps=max(2.0, t * 0.5)),  # 貼牆內緣的輪廓多邊形
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
    # 獨立開口數量檢查（自檢通過 ≠ 開口都找到）：牆層若把門窗吞掉，
    # 幾何仍封閉、泛洪自檢照樣通過，只是門窗標籤消失。這裡反向檢查：
    # 每個封閉空間都該有至少一個出入口（門／開口元素或封口線）相鄰，
    # 一個都沒有 → 疑有門窗被吸入牆層，標記人工檢視。
    passable: list[tuple] = []
    for e in elements:
        if e.get("kind") in ("door", "opening"):
            passable.append((e["p1"], e["p2"]))
    for s in seal_log:
        if s.get("source") in ("door_arc", "pair", "foot", "group_gap") and s.get("p1"):
            passable.append((s["p1"], s["p2"]))
    reach = max(4, int(t * 2))
    adj: set[int] = set()
    for p1, p2 in passable:
        for f in np.linspace(0.15, 0.85, 8):
            x = int(round(p1[0] * (1 - f) + p2[0] * f))
            y = int(round(p1[1] * (1 - f) + p2[1] * f))
            adj.update(np.unique(labels[max(0, y - reach):min(h_img, y + reach + 1),
                                        max(0, x - reach):min(w_img, x + reach + 1)]).tolist())
    for r in rooms:
        r["no_opening"] = label_of[r["id"]] not in adj

    # 寬度場：室內每點距最近牆體多遠（房間中央＝高地，門口／通道＝低谷）
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 5)

    # 自檢（規格步驟 3）：房間面積總和＋牆體面積 ≈ 建築外輪廓面積。
    # 誤差 > 5% 表示有漏封或漏牆 → 標記「須人工檢視」，不硬輸出。
    coverage = None
    if footprint is not None:
        fp_area = int(np.count_nonzero(footprint))
        if fp_area > 0:
            wall_in = int(np.count_nonzero((sealed > 0) & (footprint > 0)))
            coverage = (sum(r["area_px"] for r in rooms) + wall_in) / fp_area
    quality = {"coverage": (round(coverage, 4) if coverage is not None else None),
               "coverage_ok": (coverage is None or abs(coverage - 1.0) <= 0.05)}
    return rooms, {"labels": labels, "dist": dist, "label_of": label_of,
                   "seals": seal_log, "quality": quality}


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
            region = (grown == i).astype(np.uint8)
            ys, xs = np.nonzero(region)
            if xs.size == 0:
                out.append({})
                continue
            dreg = cv2.distanceTransform(region, cv2.DIST_L2, 3)
            py_, px_ = np.unravel_index(int(np.argmax(dreg)), dreg.shape)
            out.append({
                "ext": [float(xs.min() / s), float(ys.min() / s),
                        float((xs.max() + 1) / s), float((ys.max() + 1) / s)],
                "area_px": float(xs.size) / (s * s),   # 生長區域實際面積（還原原尺度）
                # 貼牆輪廓（原圖座標）：縮圖階梯以 eps≈2 個縮圖像素抹平
                "poly": _region_poly(region, eps=max(3.0, 2.0 / s), scale=s),
                "pole": [float(px_ / s), float(py_ / s)],   # 區域最內點：標籤不壓牆
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
                overrides: Optional[list] = None,
                manual_openings: Optional[list] = None) -> dict:
    """主流程。manual_ref = {x1, y1, x2, y2, length_mm}（原圖像素座標）；
    source_name 供待確認庫 manifest 記錄來源檔名；
    overrides = 使用者定義清單 [{bbox, class, action}]，視為事實疊加於模型判斷之上；
    manual_openings = 使用者自訂開口 [{p1, p2, kind}]（measure_manual_opening 的產物）
    ——來源標「手動」、跳過自動分類、與其重疊的自動開口由手動優先。"""
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
    # 2.5 牆帶異物偵測：把被吸進牆層的門窗線挖出斷口（細牆畫風的門窗漏辨主因）
    wall_mask, carved = _carve_band_openings(wall_mask, ink_clean, t)
    if carved:
        warnings.append(f"牆帶內偵測到 {len(carved)} 處內嵌門窗線（雙線／細線），"
                        "已在牆層開洞交由開口分類器判定。")

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

    # 4.5 使用者自訂開口疊加：來源標「手動」、跳過自動分類（類型由人指定）、
    #     與其重疊的自動開口元素移除（手動優先）
    for mo in (manual_openings or [])[:100]:
        try:
            p1 = (float(mo["p1"][0]), float(mo["p1"][1]))
            p2 = (float(mo["p2"][0]), float(mo["p2"][1]))
            m_kind = mo.get("kind") if mo.get("kind") in ("door", "window", "opening") else "opening"
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        px_len = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
        if px_len < 2:
            continue
        m_axis = "h" if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]) else "v"
        m_pos = p1[1] if m_axis == "h" else p1[0]
        m_lo = min(p1[0], p2[0]) if m_axis == "h" else min(p1[1], p2[1])
        m_hi = max(p1[0], p2[0]) if m_axis == "h" else max(p1[1], p2[1])
        def _clash(e: dict) -> bool:
            if e["kind"] == "wall":
                return False
            ax = "h" if abs(e["p2"][0] - e["p1"][0]) >= abs(e["p2"][1] - e["p1"][1]) else "v"
            if ax != m_axis:
                return False
            ep = e["p1"][1] if ax == "h" else e["p1"][0]
            if abs(ep - m_pos) > t * 1.5:
                return False
            lo = min(e["p1"][0], e["p2"][0]) if ax == "h" else min(e["p1"][1], e["p2"][1])
            hi = max(e["p1"][0], e["p2"][0]) if ax == "h" else max(e["p1"][1], e["p2"][1])
            return min(m_hi, hi) - max(m_lo, lo) > t
        elements = [e for e in elements if not _clash(e)]
        elements.append({"kind": m_kind, "p1": p1, "p2": p2, "px_length": px_len,
                         "thickness_px": t, "source": "manual"})

    for i, e in enumerate(elements, 1):
        prefix = "W" if e["kind"] == "wall" else ("M" if e.get("source") == "manual" else "O")
        e["id"] = f"{prefix}{i}"
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
        rooms, geo = _detect_rooms(wall_mask, elements, t, groups, furniture, arc_seals,
                                   ink_clean=ink_clean, mm_per_px=mm_per_px)
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
        rooms, _geo = _detect_rooms(wall_mask, elements, t, groups, ink_clean=ink_clean,
                                    mm_per_px=mm_per_px)  # 無種子：仍列出封閉區域
        geo = _geo
        warnings.append("找不到家具樣板庫（room_recognition/），已略過家具辨識與空間判定。")

    for r in rooms:
        if mm_per_px:
            m2 = r["area_px"] * (mm_per_px ** 2) / 1e6
            r["area_m2"] = round(m2, 2)
            r["area_m2_min"] = round(m2 * 0.95, 2)
            r["area_m2_max"] = round(m2 * 1.05, 2)
            r["w_m"] = round(r["bbox"][2] * mm_per_px / 1000, 2)
            r["h_m"] = round(r["bbox"][3] * mm_per_px / 1000, 2)
            # 規格步驟 3：寬度 < 90 cm 的無家具長條 → 走道（標建議複核，可改名）
            w_mm, h_mm = r["bbox"][2] * mm_per_px, r["bbox"][3] * mm_per_px
            if (r.get("no_furniture") and not r.get("room_type")
                    and min(w_mm, h_mm) < 900 and max(w_mm, h_mm) >= 2.5 * min(w_mm, h_mm)):
                r["room_type"] = "走廊"
                r["room_review"] = True
        else:
            r["area_m2"] = r["area_m2_min"] = r["area_m2_max"] = None
            r["w_m"] = r["h_m"] = None
        # 形狀合理性檢查：長寬比 > 3:1 且不含任何錨點家具 → 可疑分割
        # （90cm 走道門檻抓不到 180cm 帶狀區，此規則補上）
        bw, bh = r["bbox"][2], r["bbox"][3]
        if (r.get("no_furniture") and not r.get("room_type")
                and max(bw, bh) > 3.0 * max(1, min(bw, bh))):
            r["suspect_split"] = True
            r["room_review"] = True

    # 品質門檻（規格自檢）：任一未通過 → 標記須人工檢視，不硬輸出
    quality = dict(geo.get("quality") or {})
    unassigned = sum(1 for f in furniture if not f.get("room_id"))
    quality["unassigned_furniture"] = unassigned
    # 開口數量統計（回報格式用：與人工目視數比對即得漏辨數）
    quality["openings"] = {k: sum(1 for e in elements if e.get("kind") == k)
                           for k in ("door", "window", "opening")}
    quality["carved_openings"] = len(carved)
    # 手動介入率（防拐杖變義肢）：手動開口數 ÷ 總開口數，按來源記錄。
    # 某來源持續偏高（>30%）＝該畫法需專門處理，不應繼續以人力補；
    # 介入率應隨時間下降，否則 Active Learning 迴圈未實際閉合。
    n_manual = sum(1 for e in elements if e.get("source") == "manual")
    n_open_total = sum(quality["openings"].values())
    quality["manual_openings"] = n_manual
    quality["manual_ratio"] = round(n_manual / n_open_total, 3) if n_open_total else None
    if n_manual:
        try:
            import datetime
            _log = Path(__file__).resolve().parent / "room_recognition" / ".cache" / "manual_log.jsonl"
            _log.parent.mkdir(parents=True, exist_ok=True)
            with _log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"),
                                     "source": source_name, "manual": n_manual,
                                     "total": n_open_total}, ensure_ascii=False) + "\n")
        except OSError:
            pass
        if quality["manual_ratio"] and quality["manual_ratio"] > 0.30:
            warnings.append(
                f"手動介入率 {quality['manual_ratio']:.0%} 偏高——此畫法的門窗辨識需要"
                "專門處理；手動樣本已入庫，按「重新訓練模型」讓辨識器學會，別長期以人力補。")
    suspects = [r["id"] for r in rooms if r.get("suspect_split")]
    no_open = [r["id"] for r in rooms if r.get("no_opening")]
    quality["suspect_splits"] = suspects
    quality["rooms_without_opening"] = no_open
    quality["needs_review"] = (bool(unassigned) or not quality.get("coverage_ok", True)
                               or bool(suspects) or bool(no_open))
    if unassigned:
        warnings.append(
            f"自檢：有 {unassigned} 件家具落在未封閉區域（疑有漏封的開口）——"
            "該區空間範圍可能不準，建議人工檢視。")
    if not quality.get("coverage_ok", True) and quality.get("coverage") is not None:
        warnings.append(
            f"自檢：房間＋牆體面積佔建築外輪廓 {quality['coverage']:.0%}"
            "（偏離 100% 超過 5%），疑有漏封或漏牆，建議人工檢視。")
    if suspects:
        warnings.append(
            f"自檢：{ '、'.join(suspects) } 為長寬比 >3:1 且無錨點家具的帶狀區——"
            "可疑分割，建議人工檢視（可用 ✂ 切割空間重新定義）。")
    if no_open:
        warnings.append(
            f"自檢：{ '、'.join(no_open) } 找不到任何出入口——"
            "疑有門窗被吸入牆層而漏辨，建議人工檢視。")

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
        "seals": (geo.get("seals") or []) + carved,   # 每條封口線：座標／寬度／來源（可回溯）
        "quality": quality,                # 自檢：面積守恆、漏封偵測、須人工檢視旗標
        "warnings": warnings,
        "structural_png_b64": structural_b64,
        "original_png_b64": base64.b64encode(cv2.imencode(".png", bgr)[1].tobytes()).decode("ascii"),
        "wall_thickness_px": round(t, 1),
    }
