# -*- coding: utf-8 -*-
"""家具符號辨識與空間類型判定（路線 A：模板比對，免訓練）。

素材來源：room_recognition/<類別>/*.png（類別資料夾名即類別鍵）。

架構（物件切割 → 正規化比對＋機器學習雙軌，非滑動視窗）：
  1. 樣板清理：裁掉對照表文字欄與框線、一圖多變體自動拆開、二值化，記憶體快取
  2. 家具層萃取：墨水圖 − 膨脹牆體 − 樓梯（週期平行線）＝獨立家具物件
  3. 尺寸閘門：以校準值（或牆厚 ≈15cm 的保底錨）換算實體尺寸，
     先用「這個大小可能是什麼家具」淘汰類別，再比外形
  4. 雙軌判定：
     - 樣板相似度（chamfer＋粗網格，實測調校的門檻）＝守門員，持否決權
     - 深度學習分類器（furniture_ml：CNN；無 torch 時退回 softmax）
       ＝增強信心、仲裁類別
     兩軌皆不過 → 物件列為「無法辨識」，裁切存入 room_recognition/uncertain/
     高信心偵測則自動收割至 .autolabel/ —— 兩者連同使用者整理的資料夾，
     在每輪重訓中回流為訓練資料（含偽標籤），形成自我訓練閉環
  5. 房間指派（中心點落點）＋規則式空間類型判定

限制：斜放家具（非 90 度倍數）與樣板庫未涵蓋的畫風可能漏抓；
      新來源的圖面請把該來源的符號畫法加進 room_recognition/ 對應資料夾。
"""
from __future__ import annotations

import base64
import hashlib
import itertools
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

_ASSET_DIR = Path(__file__).resolve().parent / "room_recognition"

# ---------------------------------------------------------------------------
# 家具類別註冊表（縮減版 SSOT）：僅七類參與辨識，其餘一律排除定義
#   zh＝中文；room＝對應空間（一對一規則）；size＝實體長邊範圍 cm；
#   short＝短邊下限 cm；thr＝樣板比對接受門檻（實測調校值）；
#   confuse＝易混類別（偽標籤守門會要求與其拉開差距）
# ---------------------------------------------------------------------------
CLASSES: dict[str, dict] = {
    # w＝空間指向權重（room-inference-from-furniture skill 第 1 節：
    #    ≥0.90 看到即可單獨定案；0.50–0.89 需同伴佐證；<0.50 僅供加分）
    "toilet":     {"zh": "馬桶", "room": "廁所", "w": 0.98, "size": (50, 95), "short": 30, "thr": 0.36, "confuse": ["bathtub"]},
    "bathtub":    {"zh": "浴缸", "room": "浴室", "w": 0.95, "size": (110, 200), "short": 60, "thr": 0.55, "confuse": ["toilet"]},
    "shower":     {"zh": "淋浴設備", "room": "浴室", "w": 0.90, "size": (80, 160), "short": 70, "thr": 0.55, "confuse": []},
    "stove":      {"zh": "爐台", "room": "廚房", "w": 0.98, "size": (55, 110), "short": 40, "thr": 0.52, "confuse": []},
    "sofa":       {"zh": "沙發", "room": "客廳", "w": 0.95, "size": (130, 280), "short": 55, "thr": 0.55, "confuse": ["bed"]},
    "bed":        {"zh": "床", "room": "臥室", "w": 0.98, "size": (150, 280), "short": 80, "thr": 0.55, "confuse": ["sofa"]},
    "dining_set": {"zh": "餐桌", "room": "餐廳", "w": 0.90, "size": (110, 320), "short": 80, "thr": 0.60, "confuse": []},
}
# 既有資料夾名 → 標準 key（免改使用者的資料夾）
LEGACY_DIRS = {"tolit": "toilet", "gas stove": "stove",
               "dining table": "dining_set", "tub": "bathtub"}

def resolve_class_dir(name: str) -> Optional[str]:
    """資料夾名 → 標準類別 key；非類別資料夾回傳 None（供負類判定）。"""
    key = LEGACY_DIRS.get(name, name)
    return key if key in CLASSES else None

# 衍生表（維持既有程式碼的存取介面）
ZH_LABEL = {k: v["zh"] for k, v in CLASSES.items()}
_RANGE_CM = {k: v["size"] for k, v in CLASSES.items()}
_SHORT_MIN_CM = {k: v["short"] for k, v in CLASSES.items()}
_CLASS_THRESHOLD = {k: v["thr"] for k, v in CLASSES.items()}

# 空間判定規則（一對一）：
#   馬桶＝廁所；浴缸／淋浴設備＝浴室；爐台＝廚房；沙發＝客廳；床＝臥室；餐桌＝餐廳
_ROOM_RULES: list[tuple[set[str], str]] = [
    ({"toilet"}, "廁所"),
    ({"bathtub", "shower"}, "浴室"),
    ({"stove"}, "廚房"),
    ({"sofa"}, "客廳"),
    ({"bed"}, "臥室"),
    ({"dining_set"}, "餐廳"),
]

# 方法五：複合空間標籤——同一空間出現多種機能證據時「不切」，誠實輸出複合名稱。
# 牆面、門窗尺寸不因分界線位置而變，複合標籤即為正確答案。
_COMPOSITE_ROOMS: dict[frozenset, str] = {
    frozenset({"廁所", "浴室"}): "衛浴",
    frozenset({"客廳", "餐廳"}): "客餐廳",
    frozenset({"餐廳", "廚房"}): "餐廚",
    frozenset({"客廳", "廚房"}): "客廚",
    frozenset({"客廳", "餐廳", "廚房"}): "客餐廚",
}

# 第二軌的機能分組由 CLASSES[*]["room"] 直接推得（見 _zone_group）

_WALL_MM = 150.0    # 保底尺度錨：隔間牆厚約 15cm
_NORM = 48          # 正規化比對邊長
_OVERSIZE_CM = 320  # 長邊超過此值視為黏連群組，嘗試二次拆解
_MIN_OBJ_PX = 18    # 物件最小邊長（px）
_MIN_OBJ_INK = 60   # 物件最少墨水像素


# ---------------------------------------------------------------------------
# 樣板載入與清理
# ---------------------------------------------------------------------------
def _to_ink(img: np.ndarray) -> np.ndarray:
    """任意 PNG → 白底黑線的二值墨水圖（線條=255）。透明部分視為白底。"""
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        img = (rgb * alpha + 255.0 * (1 - alpha)).astype(np.uint8)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return ink

def _strip_table(ink: np.ndarray) -> np.ndarray:
    """對照表截圖：裁掉文字標籤欄（以貫穿全高的直線為欄界，取最右欄）再去框線。"""
    w = ink.shape[1]
    col_full = (ink > 0).mean(axis=0) > 0.85
    dividers = [x for x in range(int(w * 0.08), int(w * 0.92)) if col_full[x]]
    if dividers:
        ink = ink[:, max(dividers) + 3:]
    ink = ink.copy()
    ink[(ink > 0).mean(axis=1) > 0.9, :] = 0
    ink[:, (ink > 0).mean(axis=0) > 0.9] = 0
    return ink

def _split_variants(ink: np.ndarray) -> list[np.ndarray]:
    """一張樣板可能畫了多個變體：以膨脹群聚拆開，各自裁到緊貼邊界。"""
    if not (ink > 0).any():
        return []
    k = max(7, int(0.06 * max(ink.shape)))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k | 1, k | 1))
    blob = cv2.dilate(ink, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats((blob > 0).astype(np.uint8), 8)
    total_ink = int((ink > 0).sum())
    out: list[np.ndarray] = []
    for lbl in range(1, n):
        x, y = stats[lbl, cv2.CC_STAT_LEFT], stats[lbl, cv2.CC_STAT_TOP]
        ww, hh = stats[lbl, cv2.CC_STAT_WIDTH], stats[lbl, cv2.CC_STAT_HEIGHT]
        crop = ink[y:y + hh, x:x + ww] * (labels[y:y + hh, x:x + ww] == lbl)
        if int((crop > 0).sum()) < max(60, total_ink * 0.08):
            continue  # 雜點或殘線
        cys, cxs = np.nonzero(crop)
        out.append(crop[cys.min():cys.max() + 1, cxs.min():cxs.max() + 1])
    return out

def _is_plausible(v: np.ndarray) -> bool:
    """排除鑑別力不足的變體：極端長寬比、實心色塊、過小碎片、純外框形狀。"""
    h, w = v.shape
    if min(h, w) < 14:
        return False
    if max(h, w) / min(h, w) > 4.5:
        return False  # 細長條多為殘線或標尺
    ink_ratio = float((v > 0).mean())
    if not (0.02 <= ink_ratio <= 0.40):
        return False  # 家具符號為線稿，實心塊視為雜訊
    ring = max(3, int(0.10 * min(h, w)))
    interior = (v[ring:h - ring, ring:w - ring] > 0).sum()
    total = (v > 0).sum()
    return total > 0 and interior / total >= 0.18  # 純外框（圓角矩形）沒有鑑別力

def _signature(v: np.ndarray) -> bytes:
    """24×24 縮圖二值簽章，用於變體／方向去重。"""
    small = cv2.resize(v, (24, 24), interpolation=cv2.INTER_AREA)
    return bytes((small > 60).astype(np.uint8).flatten())

@lru_cache(maxsize=1)
def load_templates() -> dict[str, list[np.ndarray]]:
    """回傳 {標準類別 key: [二值樣板, ...]}；資料夾不存在時回傳空 dict。

    資料夾名經 resolve_class_dir 對應（舊名 tolit／gas stove… 自動歸戶），
    同類多資料夾的變體會合併。
    """
    if not _ASSET_DIR.is_dir():
        return {}
    templates: dict[str, list[np.ndarray]] = {}
    seen_by_cls: dict[str, list[np.ndarray]] = {}
    for class_dir in sorted(_ASSET_DIR.iterdir()):
        if not class_dir.is_dir():
            continue
        key = resolve_class_dir(class_dir.name)
        if key is None:
            continue
        variants = templates.setdefault(key, [])
        seen = seen_by_cls.setdefault(key, [])
        for f in sorted(class_dir.glob("*.png")):
            raw = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if raw is None:
                continue
            ink = _strip_table(_to_ink(raw))
            for v in _split_variants(ink):
                if not _is_plausible(v):
                    continue
                sig = np.frombuffer(_signature(v), dtype=np.uint8)
                if any(np.count_nonzero(sig != s) < 576 * 0.16 for s in seen):
                    continue  # 與既有變體幾乎相同，修剪以加速比對
                seen.append(sig)
                variants.append(v)
    return {k: v for k, v in templates.items() if v}


# ---------------------------------------------------------------------------
# 樓梯（週期平行線）排除遮罩
# ---------------------------------------------------------------------------
def _ladder_mask(ink: np.ndarray) -> np.ndarray:
    """偵測樓梯等「多條等長、等距、對齊的平行細線」，回傳排除遮罩。

    樓梯是結構而非家具，卻是形狀比對的誤報磁鐵。判準：≥6 條長度相近、
    跨距重疊、沿法線等距排列的細線段。床的枕頭線、餐桌椅群因線長不一
    或數量不足，不會被誤殺。
    """
    mask = np.zeros_like(ink)
    for axis in ("h", "v"):
        k = (31, 1) if axis == "h" else (1, 31)
        lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
        n, _, stats, _ = cv2.connectedComponentsWithStats((lines > 0).astype(np.uint8), 8)
        segs = []
        for lbl in range(1, n):
            x, y = int(stats[lbl, cv2.CC_STAT_LEFT]), int(stats[lbl, cv2.CC_STAT_TOP])
            ww, hh = int(stats[lbl, cv2.CC_STAT_WIDTH]), int(stats[lbl, cv2.CC_STAT_HEIGHT])
            length, thick = (ww, hh) if axis == "h" else (hh, ww)
            if length >= 31 and thick <= 8:  # 細線段（粗牆線排除）
                lo, hi = (x, x + ww) if axis == "h" else (y, y + hh)
                pos = y + hh / 2.0 if axis == "h" else x + ww / 2.0
                segs.append({"lo": lo, "hi": hi, "len": length, "pos": pos,
                             "bbox": (x, y, ww, hh)})
        segs.sort(key=lambda s: s["pos"])
        used = [False] * len(segs)
        for i, s in enumerate(segs):
            if used[i]:
                continue
            group_idx = [i]
            for j in range(i + 1, len(segs)):
                if used[j]:
                    continue
                o = segs[j]
                overlap = min(s["hi"], o["hi"]) - max(s["lo"], o["lo"])
                if overlap < 0.7 * min(s["len"], o["len"]):
                    continue
                if not (0.7 <= o["len"] / s["len"] <= 1.43):
                    continue
                group_idx.append(j)
            if len(group_idx) < 6:
                continue
            gaps = np.diff([segs[j]["pos"] for j in group_idx])
            if gaps.size == 0 or gaps.std() / max(gaps.mean(), 1.0) > 0.35 or gaps.mean() > 60:
                continue  # 間距不規則或過疏 → 非樓梯
            for j in group_idx:
                used[j] = True
            boxes = [segs[j]["bbox"] for j in group_idx]
            x0 = min(b[0] for b in boxes)
            y0 = min(b[1] for b in boxes)
            x1 = max(b[0] + b[2] for b in boxes)
            y1 = max(b[1] + b[3] for b in boxes)
            mask[y0:y1, x0:x1] = 255
    return mask


# ---------------------------------------------------------------------------
# 正規化外形比對
# ---------------------------------------------------------------------------
def _orient8(tmpl: np.ndarray) -> list[np.ndarray]:
    """4 向旋轉 × 鏡像，並以縮圖簽章去除因對稱而重複的方向。"""
    cands = [tmpl, cv2.rotate(tmpl, cv2.ROTATE_90_CLOCKWISE),
             cv2.rotate(tmpl, cv2.ROTATE_180), cv2.rotate(tmpl, cv2.ROTATE_90_COUNTERCLOCKWISE)]
    flipped = cv2.flip(tmpl, 1)
    cands += [flipped, cv2.rotate(flipped, cv2.ROTATE_90_CLOCKWISE),
              cv2.rotate(flipped, cv2.ROTATE_180), cv2.rotate(flipped, cv2.ROTATE_90_COUNTERCLOCKWISE)]
    out: list[np.ndarray] = []
    sigs: list[np.ndarray] = []
    for c in cands:
        sig = np.frombuffer(_signature(c), dtype=np.uint8)
        if any(np.count_nonzero(sig != s) < 576 * 0.06 for s in sigs):
            continue
        sigs.append(sig)
        out.append(c)
    return out

def _norm48(a: np.ndarray) -> np.ndarray:
    out = cv2.resize(a, (_NORM, _NORM), interpolation=cv2.INTER_AREA)
    _, out = cv2.threshold(out, 40, 255, cv2.THRESH_BINARY)
    return out

def _chamfer_sim(a: np.ndarray, b: np.ndarray) -> float:
    """雙向 chamfer 相似度：兩圖線條互相的平均距離，容忍畫風差異。"""
    da = cv2.distanceTransform((a == 0).astype(np.uint8), cv2.DIST_L2, 3)
    db = cv2.distanceTransform((b == 0).astype(np.uint8), cv2.DIST_L2, 3)
    if not (a > 0).any() or not (b > 0).any():
        return 0.0
    d = max(float(da[b > 0].mean()), float(db[a > 0].mean())) / (_NORM * 0.5)
    return max(0.0, 1.0 - d * 4)

def _coarse_sim(a: np.ndarray, b: np.ndarray) -> float:
    """12×12 粗網格相關：比的是墨水分佈輪廓，不是筆劃細節。"""
    ga = cv2.resize(a, (12, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
    gb = cv2.resize(b, (12, 12), interpolation=cv2.INTER_AREA).astype(np.float32)
    ga -= ga.mean()
    gb -= gb.mean()
    denom = float(np.linalg.norm(ga) * np.linalg.norm(gb)) or 1.0
    return max(0.0, float((ga * gb).sum()) / denom)

# ---------------------------------------------------------------------------
# 門／窗符號辨識（樣板庫：room_recognition/door、room_recognition/windows）
# ---------------------------------------------------------------------------
_OPEN_H, _OPEN_W = 40, 100     # 開口符號正規化為水平長條（寬 > 高）
_OPEN_DIRS = {"door": "door", "windows": "window", "window": "window"}
_OPEN_ACCEPT = 0.42            # 樣板相似度門檻：低於此值 → 不冠門/窗類別（仍列為開口）


def _open_norm(a: np.ndarray) -> np.ndarray:
    out = cv2.resize(a, (_OPEN_W, _OPEN_H), interpolation=cv2.INTER_AREA)
    _, out = cv2.threshold(out, 40, 255, cv2.THRESH_BINARY)
    return out


def _open_chamfer(a: np.ndarray, b: np.ndarray) -> float:
    """水平長條的雙向 chamfer 相似度（門弧／窗雙線與樣板比對）。"""
    if not (a > 0).any() or not (b > 0).any():
        return 0.0
    da = cv2.distanceTransform((a == 0).astype(np.uint8), cv2.DIST_L2, 3)
    db = cv2.distanceTransform((b == 0).astype(np.uint8), cv2.DIST_L2, 3)
    d = max(float(da[b > 0].mean()), float(db[a > 0].mean())) / (_OPEN_H * 0.5)
    return max(0.0, 1.0 - d * 4)


def _opening_fingerprint() -> tuple:
    """door／windows 資料夾內容指紋（檔名＋大小＋修改時間）。

    新增／替換／刪除門窗樣板時指紋改變 → load_opening_templates 自動重載，
    不必重啟伺服器即可讓新圖立即成為辨識樣本。
    """
    items = []
    if _ASSET_DIR.is_dir():
        for name in _OPEN_DIRS:
            d = _ASSET_DIR / name
            if not d.is_dir():
                continue
            for fp in sorted(d.glob("*.png")):
                st = fp.stat()
                items.append((f"{name}/{fp.name}", st.st_size, st.st_mtime_ns))
    return tuple(items)


_opening_cache: dict = {"fp": None, "tpl": None}


def load_opening_templates() -> dict[str, list[np.ndarray]]:
    """門／窗樣板 → {'door':[長條二值圖…], 'window':[…]}；資料夾不存在則對應為空。

    以資料夾指紋為快取鍵：內容一有變動即自動重建（新增的門圖立即納入辨識）。
    """
    fp = _opening_fingerprint()
    if _opening_cache["fp"] == fp and _opening_cache["tpl"] is not None:
        return _opening_cache["tpl"]
    out: dict[str, list[np.ndarray]] = {"door": [], "window": []}
    if _ASSET_DIR.is_dir():
        for name, key in _OPEN_DIRS.items():
            d = _ASSET_DIR / name
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.png")):
                raw = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                if raw is None:
                    continue
                ink = _to_ink(raw)
                ys, xs = np.nonzero(ink)
                if xs.size < 20:
                    continue
                ink = ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                if ink.shape[0] > ink.shape[1]:          # 一律轉成水平長條
                    ink = cv2.rotate(ink, cv2.ROTATE_90_CLOCKWISE)
                out[key].append(_open_norm(ink))
    _opening_cache["fp"], _opening_cache["tpl"] = fp, out
    return out


def classify_opening_region(region_ink: np.ndarray) -> tuple[Optional[str], float]:
    """以門／窗樣本判定一段開口周邊的墨水圖。

    深度學習優先：opening_ml 以 door/windows 資料夾樣本增強訓練的 CNN
    （door／window／純開口三分類）；不可用時退回 chamfer 樣板比對。
    回傳 (kind, score)，kind ∈ {'door','window',None}。純空缺（無門弧、無窗線）
    → 回傳 (None, score)，由呼叫端列為一般「開口」。
    比對時展開 4 種翻轉，容忍門弧朝任一側、窗線上下顛倒。
    """
    try:
        import opening_ml
        ml = opening_ml.predict(region_ink)
    except Exception:
        ml = None
    if ml is not None:
        return ml
    tpl = load_opening_templates()
    if not tpl["door"] and not tpl["window"]:
        return None, 0.0
    ys, xs = np.nonzero(region_ink)
    if xs.size < 20:
        return None, 0.0
    crop = region_ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if crop.shape[0] > crop.shape[1]:
        crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
    variants = [_open_norm(crop), _open_norm(cv2.flip(crop, 0)),
                _open_norm(cv2.flip(crop, 1)), _open_norm(cv2.flip(crop, -1))]
    best = {"door": 0.0, "window": 0.0}
    for key in ("door", "window"):
        for t in tpl[key]:
            for v in variants:
                s = _open_chamfer(v, t)
                if s > best[key]:
                    best[key] = s
    kind = "door" if best["door"] >= best["window"] else "window"
    return kind, best[kind]


@lru_cache(maxsize=1)
def _oriented_norm_templates() -> dict[str, list[tuple[np.ndarray, float]]]:
    """{類別: [(48×48 正規化樣板, 原始長寬比 w/h), ...]}，含 8 向展開。"""
    out: dict[str, list[tuple[np.ndarray, float]]] = {}
    for cls, variants in load_templates().items():
        entries = []
        for v in variants:
            for o in _orient8(v):
                entries.append((_norm48(o), o.shape[1] / o.shape[0]))
        out[cls] = entries
    return out

def _size_allowed(obj_shape: tuple[int, int], mm_per_px: float) -> set[str]:
    """尺寸閘門：這個實體大小可能是哪些類別。"""
    long_cm = max(obj_shape) * mm_per_px / 10.0
    short_cm = min(obj_shape) * mm_per_px / 10.0
    return {cls for cls, (lo, hi) in _RANGE_CM.items()
            if lo <= long_cm <= hi and short_cm >= _SHORT_MIN_CM[cls]}

def _chamfer_scores(obj: np.ndarray, allowed: set[str]) -> dict[str, float]:
    """尺寸閘門內各類別的樣板相似度最佳值。"""
    aspect = obj.shape[1] / obj.shape[0]
    obj_n = _norm48(obj)
    scores: dict[str, float] = {}
    for cls in allowed:
        cls_best = 0.0
        for tmpl_n, t_aspect in _oriented_norm_templates().get(cls, []):
            if not (0.6 <= aspect / t_aspect <= 1.67):
                continue  # 長寬比差太多，免比
            s = 0.5 * _chamfer_sim(obj_n, tmpl_n) + 0.5 * _coarse_sim(obj_n, tmpl_n)
            cls_best = max(cls_best, s)
        scores[cls] = cls_best
    return scores

_KNOWN_OTHER = "__other__"  # 哨兵：ML 有把握是「已知的非家具」（盆栽等負類）

def _classify(obj: np.ndarray, mm_per_px: float) -> tuple[Optional[str], float]:
    """單一物件 → (類別, 信心)。

    雙軌混合決策：
      - 樣板相似度（chamfer）需過該類實測門檻 —— 守門員，無它不成案
      - ML 分類器同意 → 信心提升（兩者平均）；ML 強烈主張另一個
        尺寸合理的類別且該類 chamfer 接近門檻 → 改判該類
    回傳 (None, 0)＝無法辨識（外層列入 uncertain）；
    回傳 (_KNOWN_OTHER, p)＝ML 確信是已整理過的負類（盆栽等），毋須再收集。
    """
    allowed = _size_allowed(obj.shape, mm_per_px)
    if not allowed:
        return None, 0.0
    cham = _chamfer_scores(obj, allowed)
    passing = {c: s for c, s in cham.items() if s >= _CLASS_THRESHOLD[c]}

    ml_probs: dict[str, float] = {}
    try:
        from furniture_ml import get_model
        model = get_model()
        if model is not None:
            ml_probs = model.predict_proba(obj)
    except Exception:
        pass  # ML 層故障時退回純樣板比對

    if not passing:
        if ml_probs.get("other", 0.0) >= 0.7:
            return _KNOWN_OTHER, ml_probs["other"]
        return None, 0.0
    best_cls = max(passing, key=lambda c: passing[c])
    conf = passing[best_cls]
    if ml_probs:
        # 負類否決權：使用者整理過的負類（plant/ 等）訓練出的 other 機率，
        # 可以否決「樣板證據不壓倒性」的偵測。盆栽這類形近干擾物是每個
        # 低門檻類別的毒源，唯有負類資料累積才能永久根除（樣板加得再多、
        # 門檻調得再細都只是換個地方漏）。
        if ml_probs.get("other", 0.0) >= 0.75 and conf < 0.65:
            return _KNOWN_OTHER, ml_probs["other"]
        top_ml = max((c for c in ml_probs if c != "other"), key=lambda c: ml_probs[c])
        if top_ml == best_cls:
            conf = 0.5 * conf + 0.5 * ml_probs[top_ml]  # 兩軌一致 → 信心增強
        elif (top_ml in allowed and ml_probs[top_ml] >= 0.85
              and cham.get(top_ml, 0.0) >= max(_CLASS_THRESHOLD[top_ml] * 0.85, 0.45)
              and cham.get(top_ml, 0.0) >= cham.get(best_cls, 0.0) - 0.03):
            # 仲裁改判三條件：ML 極高信心、樣板分數在絕對地板之上、
            # 且樣板「不明確反對」改判方向（差距 ≤0.03）——
            # 床↔沙發這類易混對，CNN 跨畫風誤信時樣板明確偏向原判，不得挾持
            best_cls = top_ml
            conf = 0.5 * cham[top_ml] + 0.5 * ml_probs[top_ml]
        else:
            conf *= 0.9  # ML 不同意（或指向尺寸不合的類別）→ 信心小幅下修
    return best_cls, min(conf, 0.99)


# ---------------------------------------------------------------------------
# 物件切割與偵測主流程
# ---------------------------------------------------------------------------
def _merge_nested(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """把互相重疊／包含的 bbox 合併（爐台與其爐口、水槽內外圈等）。"""
    merged = True
    boxes = list(boxes)
    while merged:
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ax, ay, aw, ah = boxes[i]
                bx, by, bw, bh = boxes[j]
                if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                    x0, y0 = min(ax, bx), min(ay, by)
                    x1, y1 = max(ax + aw, bx + bw), max(ay + ah, by + bh)
                    boxes[i] = (x0, y0, x1 - x0, y1 - y0)
                    boxes.pop(j)
                    merged = True
                    break
            if merged:
                break
    return boxes

def _crop_object(furn: np.ndarray, x: int, y: int, w: int, h: int) -> Optional[np.ndarray]:
    m = furn[y:y + h, x:x + w]
    ys, xs = np.nonzero(m)
    if xs.size == 0:
        return None
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

# 無法辨識物件的收集條件：太小是雜訊、太大是結構，不值得人工整理
_UNC_MIN_PX = 24
_UNC_MIN_INK = 120
_UNC_MAX_CM = 360
# 顯示／成立門檻：信心 ≥ _GRAY_HIGH（80%）才列入偵測結果並自動收割訓練資料；
# 低於門檻一律降級「待確認」並保留原判為建議答案（不硬猜、不直接刪除）——
# 「快認得但還不會」的樣本正是重訓價值最高的資料
_GRAY_HIGH = 0.80
_AUTOLABEL_CAP = 300  # 自動收割每類上限，避免同風格樣本淹沒資料集

def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")

def _crop_png(source_gray: np.ndarray, x: int, y: int, w: int, h: int) -> Optional[bytes]:
    """從原圖裁物件（白底灰階、含 4px 邊距）→ PNG bytes。"""
    h_img, w_img = source_gray.shape
    x0, y0 = max(0, x - 4), max(0, y - 4)
    x1, y1 = min(w_img, x + w + 4), min(h_img, y + h + 4)
    ok, buf = cv2.imencode(".png", source_gray[y0:y1, x0:x1])
    return buf.tobytes() if ok else None

def _save_uncertain(source_gray: Optional[np.ndarray], x: int, y: int, w: int, h: int) -> tuple[Optional[str], Optional[bytes], bool]:
    """無法辨識的物件 → room_recognition/uncertain/（雜湊命名，重複自動略過）。

    回傳 (檔名, png bytes, 是否新建)。"""
    if source_gray is None:
        return None, None, False
    png = _crop_png(source_gray, x, y, w, h)
    if png is None:
        return None, None, False
    name = f"unc_{hashlib.sha1(png).hexdigest()[:10]}.png"
    try:
        unc_dir = _ASSET_DIR / "uncertain"
        unc_dir.mkdir(parents=True, exist_ok=True)
        path = unc_dir / name
        created = not path.exists()
        if created:
            path.write_bytes(png)
    except OSError:
        return None, png, False  # 寫檔失敗仍回傳縮圖供前端顯示
    return name, png, created

_LABEL_FILE_RE = None  # 延遲編譯

def label_uncertain(filename: str, target: str) -> dict:
    """極簡標註介面後端：把 uncertain 裁圖移入目標資料夾或刪除。

    target：六大類鍵、"other"（非家具負類）或 "delete"。
    黃金分流：每約 10 件（依檔名雜湊決定，可重現）改送 .golden/<target>/
    作為永不進訓練的黃金測試集——重訓後的驗證閘門靠它評分。
    """
    global _LABEL_FILE_RE
    import re
    if _LABEL_FILE_RE is None:
        _LABEL_FILE_RE = re.compile(r"^unc_[0-9a-f]{10}\.png$")
    if not _LABEL_FILE_RE.fullmatch(filename or ""):
        return {"error": "檔名格式不符"}
    if target != "delete" and target != "other" and target not in ZH_LABEL:
        return {"error": f"未知的目標類別：{target}"}
    src = _ASSET_DIR / "uncertain" / filename
    if not src.is_file():
        return {"error": "檔案不存在（可能已標註過）"}
    log = {"file": filename, "target": target, "at": _now()}
    try:
        if target == "delete":
            src.unlink()
            log["golden"] = False
            _append_label_log(log)
            return {"status": "deleted"}
        to_golden = int(filename[4:6], 16) % 10 == 0  # 依雜湊分流 ~10%
        dest_dir = _ASSET_DIR / (".golden" if to_golden else ".") / target
        dest_dir.mkdir(parents=True, exist_ok=True)
        src.rename(dest_dir / filename)
        log["golden"] = to_golden
        _append_label_log(log)
        return {"status": "golden" if to_golden else "labeled",
                "dest": f"{'.golden/' if to_golden else ''}{target}/{filename}"}
    except OSError as exc:
        return {"error": f"檔案操作失敗：{exc}"}

def save_correction(png_bytes: bytes, target: str, from_class: Optional[str] = None,
                    source: Optional[str] = None) -> dict:
    """使用者修正辨識錯誤：裁圖以正確類別存入訓練庫。

    - target＝正確類別 key 或 "other"（根本不是有效物件 → 負類）
    - 黃金分流：與標註介面同規則（依內容雜湊 ~10% 進 .golden/，永不訓練）
    - 撤銷污染：若該裁圖曾被高信心自動收割進 .autolabel/<原類別>/，一併刪除
      （錯誤標籤留在收割區會抵銷這次修正）
    """
    if target != "other" and target not in ZH_LABEL:
        return {"error": f"未知的目標類別：{target}"}
    if not png_bytes or len(png_bytes) > 500_000:
        return {"error": "裁圖缺漏或過大"}
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    if cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE) is None:
        return {"error": "裁圖不是有效的 PNG"}
    digest = hashlib.sha1(png_bytes).hexdigest()[:10]
    # 撤銷曾被自動收割的錯誤標籤（同內容雜湊）
    if from_class:
        stale = _ASSET_DIR / ".autolabel" / from_class / f"al_{digest}.png"
        try:
            stale.unlink(missing_ok=True)
        except OSError:
            pass
    to_golden = int(digest[:2], 16) % 10 == 0
    dest_dir = _ASSET_DIR / (".golden" if to_golden else ".") / target
    name = f"cor_{digest}.png"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / name
        if not path.exists():
            path.write_bytes(png_bytes)
    except OSError as exc:
        return {"error": f"檔案寫入失敗：{exc}"}
    _append_label_log({"file": name, "kind": "correction", "from": from_class,
                       "target": target, "golden": to_golden, "source": source,
                       "at": _now()})
    return {"status": "golden" if to_golden else "corrected",
            "dest": f"{'.golden/' if to_golden else ''}{target}/{name}"}

def _append_label_log(record: dict) -> None:
    """標註事件日誌（資料批次的版本紀錄，供回溯）。"""
    import json
    try:
        with open(_ASSET_DIR / "labels_log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass

def append_manifest(record: dict) -> None:
    """待確認庫清單（append-only）：來源圖、座標、模型猜測與信心，供追溯與批次整理。"""
    import json
    try:
        unc_dir = _ASSET_DIR / "uncertain"
        unc_dir.mkdir(parents=True, exist_ok=True)
        with open(unc_dir / "manifest.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass

def _save_autolabel(source_gray: Optional[np.ndarray], cls: str,
                    x: int, y: int, w: int, h: int) -> None:
    """高信心偵測 → room_recognition/.autolabel/<類別>/，供下輪訓練收割。"""
    if source_gray is None:
        return
    png = _crop_png(source_gray, x, y, w, h)
    if png is None:
        return
    try:
        d = _ASSET_DIR / ".autolabel" / cls
        d.mkdir(parents=True, exist_ok=True)
        if sum(1 for _ in d.glob("*.png")) >= _AUTOLABEL_CAP:
            return
        path = d / f"al_{hashlib.sha1(png).hexdigest()[:10]}.png"
        if not path.exists():
            path.write_bytes(png)
    except OSError:
        pass  # 收割失敗不影響辨識

def detect_furniture(ink_clean: np.ndarray, wall_mask: np.ndarray, wall_t_px: float,
                     mm_per_px: Optional[float] = None,
                     source_gray: Optional[np.ndarray] = None,
                     source_name: Optional[str] = None) -> tuple[list[dict], list[dict]]:
    """物件切割 → 尺寸閘門 → 雙軌判定。回傳 (家具清單, 待確認清單)。

    mm_per_px 缺漏時以牆厚（≈15cm）作保底尺度錨，尺寸閘門才有依據。
    source_gray 提供時，無法辨識與灰色地帶的物件會裁存到 room_recognition/uncertain/，
    並在 manifest.jsonl 記錄來源（source_name）、座標與模型猜測。
    """
    if not load_templates():
        return [], []
    mmpp = mm_per_px or (_WALL_MM / max(wall_t_px, 2.0))

    # 家具層 = 墨水 − 膨脹牆體 − 樓梯
    wall_dil = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    furn = cv2.bitwise_and(ink_clean, cv2.bitwise_not(wall_dil))
    furn = cv2.bitwise_and(furn, cv2.bitwise_not(_ladder_mask(furn)))

    # R5 牆帶（room-inference skill）：中心點落在牆體鄰域（±半牆厚）的偵測
    # 一律不得判為家具——門窗是牆上開口，家具中心必在房間內部
    k5 = max(3, int(wall_t_px)) | 1
    wall_near = cv2.dilate(wall_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (k5, k5)))

    # 筆劃群聚成物件
    k = max(3, int(wall_t_px * 0.6)) | 1
    blob = cv2.dilate(furn, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats((blob > 0).astype(np.uint8), 8)

    found: list[dict] = []
    uncertain: list[dict] = []

    def _harvest(bx: int, by: int, bw: int, bh: int, reason: str,
                 guess: Optional[str] = None, guess_score: Optional[float] = None) -> None:
        """裁存進待確認庫＋登記 manifest（僅新檔），並列入回傳清單。"""
        fname, png, created = _save_uncertain(source_gray, bx, by, bw, bh)
        entry = {"bbox": [bx, by, bw, bh], "file": fname, "reason": reason,
                 "png_b64": base64.b64encode(png).decode("ascii") if png else None}
        if guess is not None:
            entry["guess"] = guess
            entry["guess_score"] = round(guess_score or 0.0, 3)
        uncertain.append(entry)
        if created and fname:
            append_manifest({"file": fname, "source": source_name, "reason": reason,
                             "bbox": [bx, by, bw, bh], "guess": guess,
                             "guess_score": round(guess_score or 0.0, 3) if guess else None,
                             "at": _now()})

    def _consider(obj: Optional[np.ndarray], bx: int, by: int, bw: int, bh: int) -> None:
        if obj is None or int((obj > 0).sum()) < _MIN_OBJ_INK:
            return
        cls, score = _classify(obj, mmpp)
        if cls == _KNOWN_OTHER:
            return  # 已整理過的負類（盆栽等）：不標註也不再收集
        if cls:
            # R5：中心點在牆帶上 → 一律不得判為家具（優先於一切信心值），降級待確認
            cy_i = min(wall_near.shape[0] - 1, max(0, int(by + bh / 2)))
            cx_i = min(wall_near.shape[1] - 1, max(0, int(bx + bw / 2)))
            if wall_near[cy_i, cx_i] > 0:
                _harvest(bx, by, bw, bh, "wall_object", ZH_LABEL[cls], score)
                return
            # 第 4 節尺寸複核：被判浴缸但面積 <0.8 m² → 多半是馬桶，降級待確認
            if cls == "bathtub":
                area_m2 = (bw * mmpp / 1000.0) * (bh * mmpp / 1000.0)
                if area_m2 < 0.8:
                    _harvest(bx, by, bw, bh, "size_filter", ZH_LABEL["toilet"], score)
                    return
            if score >= _GRAY_HIGH:
                # 信心 ≥80% 才成立偵測（使用者規格），並自動收割為訓練資料
                crop = _crop_png(source_gray, bx, by, bw, bh) if source_gray is not None else None
                found.append({"class": cls, "score": score, "bbox": [bx, by, bw, bh],
                              "png": crop})  # 附裁圖供前端「辨識錯誤修正」回傳訓練
                _save_autolabel(source_gray, cls, bx, by, bw, bh)
            else:
                # 信心 <80%：不進偵測清單，降級「待確認」並保留原判為建議答案
                # ——「快認得但還不會」的樣本重訓價值最高
                _harvest(bx, by, bw, bh, "gray_zone", ZH_LABEL[cls], score)
            return
        # 無法辨識：尺寸像家具、墨水量足夠者才收集
        if (min(bw, bh) >= _UNC_MIN_PX and int((obj > 0).sum()) >= _UNC_MIN_INK
                and max(bw, bh) * mmpp / 10.0 <= _UNC_MAX_CM):
            _harvest(bx, by, bw, bh, "unknown")

    for lbl in range(1, n):
        x = int(stats[lbl, cv2.CC_STAT_LEFT])
        y = int(stats[lbl, cv2.CC_STAT_TOP])
        w = int(stats[lbl, cv2.CC_STAT_WIDTH])
        h = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        if w < _MIN_OBJ_PX or h < _MIN_OBJ_PX:
            continue
        comp = (labels[y:y + h, x:x + w] == lbl) & (furn[y:y + h, x:x + w] > 0)
        if int(comp.sum()) < _MIN_OBJ_INK:
            continue
        region = np.where(comp, np.uint8(255), np.uint8(0))

        if max(w, h) * mmpp / 10.0 > _OVERSIZE_CM:
            # 黏連群組（如廚房整組）：不膨脹二次拆解，巢狀 bbox 合併後逐件分類
            n2, _, stats2, _ = cv2.connectedComponentsWithStats((region > 0).astype(np.uint8), 8)
            sub_boxes = []
            for l2 in range(1, n2):
                sx, sy = int(stats2[l2, cv2.CC_STAT_LEFT]), int(stats2[l2, cv2.CC_STAT_TOP])
                sw, sh = int(stats2[l2, cv2.CC_STAT_WIDTH]), int(stats2[l2, cv2.CC_STAT_HEIGHT])
                if int(stats2[l2, cv2.CC_STAT_AREA]) >= 40:
                    sub_boxes.append((sx, sy, sw, sh))
            for sx, sy, sw, sh in _merge_nested(sub_boxes):
                if sw < _MIN_OBJ_PX or sh < _MIN_OBJ_PX:
                    continue
                _consider(_crop_object(region, sx, sy, sw, sh), x + sx, y + sy, sw, sh)
            continue

        _consider(_crop_object(region, 0, 0, w, h), x, y, w, h)

    found.sort(key=lambda d: -d["score"])
    out = []
    for i, d in enumerate(found, 1):
        out.append({"id": f"F{i}", "class": d["class"], "label": ZH_LABEL[d["class"]],
                    "score": round(d["score"], 3),
                    "bbox": [float(v) for v in d["bbox"]],
                    "png_b64": base64.b64encode(d["png"]).decode("ascii") if d.get("png") else None})
    for i, u in enumerate(uncertain, 1):
        u["id"] = f"U{i}"
        u["bbox"] = [float(v) for v in u["bbox"]]
    return out, uncertain


def _boxes_overlap(a: list, b: list, iou_min: float = 0.25) -> bool:
    """兩框是否指同一物件：任一中心落在對方框內，或 IoU ≥ 門檻。"""
    ax, ay, aw, ah = [float(v) for v in a]
    bx, by, bw, bh = [float(v) for v in b]
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    if bx <= acx <= bx + bw and by <= acy <= by + bh:
        return True
    if ax <= bcx <= ax + aw and ay <= bcy <= ay + ah:
        return True
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return union > 0 and inter / union >= iou_min


def apply_overrides(found: list[dict], uncertain: list[dict], overrides: list[dict],
                    source_gray: Optional[np.ndarray] = None,
                    source_name: Optional[str] = None) -> tuple[list[dict], list[dict], dict]:
    """把使用者定義（標註／修正／刪除／框選）套用到本次偵測結果。

    使用者定義視為事實：
    - delete：抑制與該框重疊的自動偵測與待確認項（並刪除已裁存的待確認檔）
    - add／correct：抑制重疊的自動偵測，改置入使用者類別（信心 1.00、user_defined）
    另把使用者定義區域的裁圖存入訓練庫（雜湊命名，重複自動略過），
    即「將正確的更新內容截圖存入資料庫」。
    回傳 (家具清單, 待確認清單, 統計)。
    """
    valid: list[dict] = []
    for ov in overrides or []:
        bbox = ov.get("bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            continue
        action = ov.get("action") or ("delete" if not ov.get("class") else "add")
        cls = ov.get("class")
        if action != "delete" and cls not in CLASSES:
            continue  # 未知類別（含 other）→ 視為刪除
        valid.append({"bbox": [float(v) for v in bbox], "action": action, "cls": cls})

    if not valid:
        return found, uncertain, {"applied": 0, "suppressed": 0, "saved": 0}

    suppressed = 0
    kept: list[dict] = []
    for det in found:
        hit = next((ov for ov in valid if _boxes_overlap(det["bbox"], ov["bbox"])), None)
        if hit is None:
            kept.append(det)
        else:
            suppressed += 1   # 排除最初錯誤的辨識

    kept_unc: list[dict] = []
    for u in uncertain:
        hit = next((ov for ov in valid if _boxes_overlap(u["bbox"], ov["bbox"])), None)
        if hit is None:
            kept_unc.append(u)
            continue
        suppressed += 1
        if u.get("file"):   # 已解決 → 移除重複裁存的待確認檔
            try:
                (_ASSET_DIR / "uncertain" / u["file"]).unlink(missing_ok=True)
            except OSError:
                pass

    saved = 0
    for ov in valid:
        if ov["action"] == "delete" or not ov["cls"]:
            continue
        bx, by, bw, bh = [int(round(v)) for v in ov["bbox"]]
        png = _crop_png(source_gray, bx, by, bw, bh) if source_gray is not None else None
        kept.append({"class": ov["cls"], "label": ZH_LABEL[ov["cls"]], "score": 1.0,
                     "bbox": ov["bbox"], "user_defined": True,
                     "png_b64": base64.b64encode(png).decode("ascii") if png else None})
        if png and _save_user_sample(png, ov["cls"], source_name):
            saved += 1

    kept.sort(key=lambda d: (not d.get("user_defined"), -d["score"]))
    for i, d in enumerate(kept, 1):
        d["id"] = f"F{i}"
    for i, u in enumerate(kept_unc, 1):
        u["id"] = f"U{i}"
    return kept, kept_unc, {"applied": len(valid), "suppressed": suppressed, "saved": saved}


def _save_user_sample(png_bytes: bytes, cls: str, source: Optional[str] = None) -> bool:
    """使用者定義樣本入庫（雜湊命名 → 同內容只存一次）。回傳是否為新樣本。"""
    digest = hashlib.sha1(png_bytes).hexdigest()[:10]
    to_golden = int(digest[:2], 16) % 10 == 0
    dest_dir = _ASSET_DIR / (".golden" if to_golden else ".") / cls
    path = dest_dir / f"usr_{digest}.png"
    try:
        if path.exists():
            return False
        dest_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png_bytes)
    except OSError:
        return False
    _append_label_log({"file": path.name, "kind": "user_override", "target": cls,
                       "golden": to_golden, "source": source, "at": _now()})
    return True


# ---------------------------------------------------------------------------
# 房間指派與空間類型判定
# ---------------------------------------------------------------------------
def _room_type(items: list[tuple[str, float]]) -> tuple[Optional[str], bool]:
    """空間判定（room-inference skill 第 2、5 節）：權重投票＋必要條件＋複合空間優先。

    - 每件家具依指向空間累加其權重 w（第 1 節表）
    - 複合空間優先：同空間滿足兩空間必要條件→衛浴／客餐廳（延伸：餐廚等），不強行切割
    - 最高分 ≥0.90 直接定案；0.60–0.89 輸出並標「建議人工複核」；
      <0.60 輸出未定（None）——「未定是合格答案，硬猜不是」
    回傳 (空間名稱或 None, 是否建議人工複核)。
    """
    votes: dict[str, float] = {}
    present: set[str] = set()
    for c, _s in items:
        info = CLASSES.get(c)
        if not info:
            continue
        present.add(c)
        votes[info["room"]] = votes.get(info["room"], 0.0) + info["w"]
    if not votes:
        return None, False
    signals: list[str] = []
    for keys, zh in _ROOM_RULES:
        if present & keys and zh not in signals:
            signals.append(zh)
    if "廁所" in signals and "浴室" in signals:
        # 必要條件：toilet＋(bathtub|shower) → 衛浴（合一），台灣住宅最常見
        idx = signals.index("廁所")
        signals = [s for s in signals if s not in ("廁所", "浴室")]
        signals.insert(idx, "衛浴")
    if len(signals) >= 2:
        name = _COMPOSITE_ROOMS.get(frozenset(signals), "＋".join(signals))
        return name, sum(votes.values()) < 0.90
    best = max(votes, key=lambda k: votes[k])
    score = votes[best]
    if len(signals) == 1 and signals[0] == "衛浴":
        best = "衛浴"
    if score < 0.60:
        return None, False   # 物件不足以定案 → 未定，留給使用者人工判定
    return best, score < 0.90


_ZONE_PAD_CM = 50.0     # 外擴留白：模擬走動空間（沙發前的地毯區也算客廳）
_ZONE_SPLIT_CM = 250.0  # 同機能但相距超過此值 → 拆成兩區（例如兩處獨立休憩區）


def _zone_group(cls: str) -> Optional[str]:
    """家具 → 機能分組名。廁所／浴室視為同一衛浴機能，不算開放空間。"""
    room = (CLASSES.get(cls) or {}).get("room")
    if room in ("廁所", "浴室"):
        return "衛浴"
    return room


def _spatial_split(items: list[dict], gap_px: float) -> list[list[dict]]:
    """空間鄰近性再分群：同機能但距離超過門檻者拆開（單連結分群）。"""
    clusters: list[list[dict]] = []
    for it in items:
        x1, y1, w1, h1 = it["bbox"]
        merged: list[list[dict]] = []
        target = [it]
        for cl in clusters:
            near = any(
                max(0.0, max(x1, b[0]) - min(x1 + w1, b[0] + b[2])) <= gap_px
                and max(0.0, max(y1, b[1]) - min(y1 + h1, b[1] + b[3])) <= gap_px
                for b in (o["bbox"] for o in cl))
            (target.extend(cl) if near else merged.append(cl))
        merged.append(target)
        clusters = merged
    return clusters


def compute_zones(furniture: list[dict], rooms: list[dict],
                  mm_per_px: Optional[float] = None, grow_fn=None) -> None:
    """第二軌：錨點種子 ＋ 瓶頸生長（marker-controlled watershed）。

    ① 錨點分群：區內家具依知識庫的空間指向分組
    ② B3 種子唯一性：同型但相距 >2.5 m 者才拆開，近的合併成一顆種子
       （兩張單椅＋一組沙發只長一個客廳）
    ③ 生長：由 grow_fn 從各種子同時往外淹，優先高地、瓶頸最後淹
       → 邊界自然落在門口／通道；B1 牆體不可跨越、B2 家具不可切開由 grow_fn 保證
       無影像時（/api/rezone）退回「外接矩形＋外擴 50 cm」的近似做法
    ④ 轉軸對齊矩形：取生長區域外接框，殘餘重疊以正交中垂線互相剪裁
    ⑤ 與牆剪裁：裁進所屬空間的外接矩形內

    區域數恆等於種子數——過切在機制上不可能。單一機能＝封閉房間，
    第一軌的外接矩形就是答案。同時寫入每件家具的 room_label。
    """
    px = (10.0 / mm_per_px) if mm_per_px else None   # 1 cm 等於幾 px
    pad = (_ZONE_PAD_CM * px) if px else 24.0
    gap = (_ZONE_SPLIT_CM * px) if px else 160.0

    by_room: dict[str, list[dict]] = {}
    for it in furniture:
        it.setdefault("room_label", None)
        if it.get("room_id"):
            by_room.setdefault(it["room_id"], []).append(it)

    for r in rooms:
        r["zones"] = []
        r["zone_lines"] = []   # 保留欄位相容；分區改以矩形表達
        items = by_room.get(r["id"], [])
        groups: dict[str, list[dict]] = {}
        for it in items:
            zh = _zone_group(it["class"])
            if zh:
                groups.setdefault(zh, []).append(it)   # ① 錨點分群
        if len(groups) < 2:
            for it in items:
                it["room_label"] = r.get("room_type")
            continue   # 封閉房間：第一軌的外接矩形即為答案

        clusters: list[list[dict]] = []
        names: list[str] = []
        for zh, its in groups.items():
            for cl in _spatial_split(its, gap):        # ② B3 種子唯一性
                clusters.append(cl)
                names.append(zh)
                for i in cl:
                    i["room_label"] = zh

        grown = grow_fn(r, clusters) if grow_fn else None   # ③ 瓶頸生長
        zones: list[dict] = []
        for idx, cl in enumerate(clusters):
            x1 = min(i["bbox"][0] for i in cl)
            y1 = min(i["bbox"][1] for i in cl)
            x2 = max(i["bbox"][0] + i["bbox"][2] for i in cl)
            y2 = max(i["bbox"][1] + i["bbox"][3] for i in cl)
            # 生長結果與「外擴 50 cm」取聯集：有瓶頸時聽分水嶺（邊界落在門口／通道），
            # 沒有瓶頸把兩群隔開時（例如爐台卡在角落），至少保住走動空間的最小範圍
            base = [x1 - pad, y1 - pad, x2 + pad, y2 + pad]
            g = (grown[idx] or None) if (grown and idx < len(grown)) else None
            ge = g.get("ext") if g else None
            ext = [min(base[0], ge[0]), min(base[1], ge[1]),
                   max(base[2], ge[2]), max(base[3], ge[3])] if ge else base
            zones.append({"label": names[idx], "core": [x1, y1, x2, y2], "box": ext,
                          "grown_px": (g or {}).get("area_px"),
                          "poly": (g or {}).get("poly"),   # 貼牆輪廓（分水嶺邊界＝隱形牆）
                          "pole": (g or {}).get("pole"),
                          "items": [i["id"] for i in cl]})

        for a, b in itertools.combinations(zones, 2):  # ⑤ 互相剪裁（正交中垂線）
            ax, ay, ax2, ay2 = a["box"]
            bx, by, bx2, by2 = b["box"]
            if ax2 <= bx or bx2 <= ax or ay2 <= by or by2 <= ay:
                continue
            acx, acy = (a["core"][0] + a["core"][2]) / 2, (a["core"][1] + a["core"][3]) / 2
            bcx, bcy = (b["core"][0] + b["core"][2]) / 2, (b["core"][1] + b["core"][3]) / 2
            if abs(acx - bcx) >= abs(acy - bcy):       # 左右相鄰 → 垂直分界
                lo, hi = (a, b) if acx <= bcx else (b, a)
                mid = (lo["core"][2] + hi["core"][0]) / 2.0
                lo["box"][2] = min(lo["box"][2], mid)
                hi["box"][0] = max(hi["box"][0], mid)
            else:                                      # 上下相鄰 → 水平分界
                lo, hi = (a, b) if acy <= bcy else (b, a)
                mid = (lo["core"][3] + hi["core"][1]) / 2.0
                lo["box"][3] = min(lo["box"][3], mid)
                hi["box"][1] = max(hi["box"][1], mid)

        rx, ry, rw, rh = r["bbox"]
        for z in zones:                                # ⑥ 與牆剪裁
            gx1, gy1, gx2, gy2 = z["box"]
            x1 = max(rx, min(gx1, rx + rw))
            y1 = max(ry, min(gy1, ry + rh))
            x2 = max(rx, min(gx2, rx + rw))
            y2 = max(ry, min(gy2, ry + rh))
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            z["bbox"] = [x1, y1, x2 - x1, y2 - y1]
            z["cx"], z["cy"] = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            # 面積：以生長區域實際像素為準，依剪裁比例折算（外框只是外接矩形）
            gw, gh = max(1.0, gx2 - gx1), max(1.0, gy2 - gy1)
            grown_px = z.pop("grown_px", None)
            frac = ((x2 - x1) * (y2 - y1)) / (gw * gh)
            z["area_px"] = (grown_px * min(1.0, frac)) if grown_px else (x2 - x1) * (y2 - y1)
            z.pop("box", None)
            z.pop("core", None)
        r["zones"] = [z for z in zones if z["bbox"][2] > 2 and z["bbox"][3] > 2]


def split_rooms_by_zones(furniture: list[dict], rooms: list[dict]) -> list[dict]:
    """分區即空間：把開放空間依機能分區拆成獨立空間，畫面只留一套空間標籤。

    避免「R1 廚房＋客廳＋臥室＋餐廳」這種整層連通的複合名稱與分區框並存——
    拆完之後，每個機能區就是一個有自己編號、名稱、面積與外框的空間。
    同步更新家具的 room_id 並重新編號（依面積排序）。
    """
    out: list[dict] = []
    for r in rooms:
        zones = r.get("zones") or []
        if len(zones) < 2:
            r["zones"] = []
            out.append(r)
            continue
        for z in zones:
            x, y, w, h = z["bbox"]
            out.append({
                "area_px": int(round(z.get("area_px") or (w * h))),
                "bbox": [x, y, w, h],
                "poly": z.get("poly"),   # 貼牆輪廓：虛線框依此繪製，不越牆、不重疊
                "centroid": [x + w / 2.0, y + h / 2.0],
                "label_pos": z.get("pole") or [x + w / 2.0, y + h / 2.0],
                "room_type": z["label"],
                "room_review": False,
                "no_furniture": False,
                "zones": [],
                "_items": list(z.get("items") or []),
            })
    out.sort(key=lambda r: -r["area_px"])
    by_item: dict[str, str] = {}
    for i, r in enumerate(out, 1):
        r["id"] = f"R{i}"
        items = r.pop("_items", None)
        if items is not None:
            r["furniture"] = items
        for fid in (items if items is not None else r.get("furniture", [])):
            by_item[fid] = r["id"]
    for it in furniture:
        if it.get("id") in by_item:
            it["room_id"] = by_item[it["id"]]
            it["room_label"] = next((r["room_type"] for r in out
                                     if r["id"] == it["room_id"]), it.get("room_label"))
    return out

# R4／R6 矛盾攔截（room-inference skill 第 3 節）：同一空間出現兩造即異常，
# 以 權重 w × 信心 加權比較，較輕的一方降級「待確認」（不投票、不直接刪除）
_CONFLICT_PAIRS: list[tuple[set[str], set[str]]] = [
    ({"stove"}, {"toilet"}),               # R4：爐台 × 馬桶
    ({"stove"}, {"bed"}),                  # R4：爐台 × 床
    ({"bed"}, {"bathtub", "shower"}),      # R4＋R6：床 × 濕區（多為門/衣櫃誤判）
    ({"stove"}, {"bathtub", "shower"}),    # R6：爐台 × 濕區
]

def assign_rooms(furniture: list[dict], rooms: list[dict],
                 mm_per_px: Optional[float] = None,
                 grow_fn=None) -> tuple[list[dict], list[dict]]:
    """空間歸屬與命名。room_id 優先採用泛洪填充結果（第一軌），缺漏才退回外框包含。

    依 room-inference skill：R4/R6 矛盾攔截（權重較輕方降級待確認）、
    同空間 ≥2 個浴缸只留信心最高者、R6 濕區正反饋（同室有馬桶的
    浴缸／淋浴信心 +0.10），最後以權重投票判定空間名稱。
    回傳 (清理後家具清單, 矛盾剔除清單)。
    """
    for r in rooms:
        r["furniture"] = []
    known = {r["id"] for r in rooms}
    for item in furniture:
        if item.get("room_id") in known:
            continue   # 泛洪填充已歸屬（比外框包含準確：L 形房間不會誤收鄰室家具）
        cx = item["bbox"][0] + item["bbox"][2] / 2.0
        cy = item["bbox"][1] + item["bbox"][3] / 2.0
        best = None
        for r in rooms:
            x, y, ww, hh = r["bbox"]
            if x <= cx <= x + ww and y <= cy <= y + hh:
                if best is None or r["area_px"] < best["area_px"]:
                    best = r
        item["room_id"] = best["id"] if best else None

    def _side_w(items: list[dict], side: set[str]) -> float:
        return sum(CLASSES[it["class"]]["w"] * it["score"]
                   for it in items if it["class"] in side)

    # 使用者定義的物件是事實，不受矛盾攔截剔除（只有模型的判斷需要被質疑）
    def _drop(items) -> list[dict]:
        return [it for it in items if not it.get("user_defined")]

    conflicted: list[dict] = []
    room_ids = {item["room_id"] for item in furniture if item["room_id"]}
    for rid in room_ids:
        in_room = [it for it in furniture if it["room_id"] == rid]
        for side_a, side_b in _CONFLICT_PAIRS:
            wa, wb = _side_w(in_room, side_a), _side_w(in_room, side_b)
            if wa > 0 and wb > 0:
                loser = side_b if wa >= wb else side_a
                conflicted.extend(it for it in _drop(in_room)
                                  if it["class"] in loser and it not in conflicted)
        # R4：同空間 ≥2 個浴缸 → 只保留信心最高者（其餘多為誤判的馬桶／淋浴間）
        tubs = sorted((it for it in in_room if it["class"] == "bathtub"),
                      key=lambda it: -it["score"])
        conflicted.extend(it for it in _drop(tubs[1:]) if it not in conflicted)
        # R6 正反饋：同室有馬桶 → 浴缸／淋浴信心 +0.10（上限 1.0）
        if any(it["class"] == "toilet" and it not in conflicted for it in in_room):
            for it in in_room:
                if it["class"] in ("bathtub", "shower") and it not in conflicted:
                    it["score"] = round(min(1.0, it["score"] + 0.10), 3)

    cleaned = [item for item in furniture if item not in conflicted]
    for i, item in enumerate(cleaned, 1):
        item["id"] = f"F{i}"  # 剔除後重新編號，避免跳號

    by_room: dict[str, list[tuple[str, float]]] = {}
    for item in cleaned:
        if item["room_id"]:
            by_room.setdefault(item["room_id"], []).append((item["class"], item["score"]))
    for r in rooms:
        r["furniture"] = [item["id"] for item in cleaned if item.get("room_id") == r["id"]]
        r["room_type"], r["room_review"] = _room_type(by_room.get(r["id"], []))
    compute_zones(cleaned, rooms, mm_per_px, grow_fn)  # 第二軌：錨點種子＋瓶頸生長
    return cleaned, conflicted


def rezone(furniture: list[dict], rooms: list[dict],
           mm_per_px: Optional[float] = None) -> dict:
    """依（使用者修正／刪除後的）家具定義重算空間名稱與機能分區。

    與 assign_rooms 的差異：不做矛盾剔除、不重新編號——修正後的類別視為
    使用者給定的事實。輸入輸出皆為顯示所需的最小欄位，供前端就地更新。
    """
    furniture = [
        {"id": str(f.get("id")), "class": str(f.get("class") or ""),
         "score": float(f.get("score") or 0.0),
         "bbox": [float(v) for v in f["bbox"]]}
        for f in furniture
        if isinstance(f.get("bbox"), list) and len(f["bbox"]) == 4
    ]
    rooms = [
        {"id": str(r.get("id")), "area_px": float(r.get("area_px") or 0.0),
         "bbox": [float(v) for v in r["bbox"]]}
        for r in rooms
        if isinstance(r.get("bbox"), list) and len(r["bbox"]) == 4
    ]
    for item in furniture:
        cx = item["bbox"][0] + item["bbox"][2] / 2.0
        cy = item["bbox"][1] + item["bbox"][3] / 2.0
        best = None
        for r in rooms:
            x, y, ww, hh = r["bbox"]
            if x <= cx <= x + ww and y <= cy <= y + hh:
                if best is None or r["area_px"] < best["area_px"]:
                    best = r
        item["room_id"] = best["id"] if best else None
    by_room: dict[str, list[tuple[str, float]]] = {}
    for item in furniture:
        if item["room_id"]:
            by_room.setdefault(item["room_id"], []).append((item["class"], item["score"]))
    for r in rooms:
        r["room_type"], r["room_review"] = _room_type(by_room.get(r["id"], []))
    compute_zones(furniture, rooms, mm_per_px)
    return {
        "rooms": [{"id": r["id"], "room_type": r["room_type"],
                   "room_review": r["room_review"],
                   "no_furniture": not by_room.get(r["id"]),
                   "zones": r["zones"], "zone_lines": r["zone_lines"]} for r in rooms],
        "furniture": [{"id": it["id"], "room_id": it["room_id"],
                       "room_label": it["room_label"]} for it in furniture],
    }
