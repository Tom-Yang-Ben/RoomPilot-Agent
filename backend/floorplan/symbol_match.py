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
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(os.path.dirname(_PKG_DIR))
_DEFAULT_LIB_PATH = os.path.join(
    _PROJECT_DIR, ".runtime", "floorplan", "symbol_lib.npz"
)
LIB_PATH = (
    os.environ.get("ROOMPILOT_SYMBOL_LIBRARY", "").strip() or _DEFAULT_LIB_PATH
)
# 推論資產不進公開版控；預設從 .runtime/floorplan 讀取，也可用環境變數覆寫。
# 找不到資產時管線會誠實停用這條選配證據路徑。
# SVG class token → 證據 kind（oval/tubrect/stove 沿用既有計分；
# shower/sinkicon 為新 kind，classify_rooms_cc 給保守小權重）
TARGETS = {"Toilet": "oval", "Bathtub": "tubrect", "BathtubRound": "tubrect",
           "IntegratedStove": "stove", "Sink": "sinkicon", "Shower": "shower"}

# ── 比對閘門（2026-07-29 重構）────────────────────────────────────────
# 舊：尺寸 → Hu 粗篩(HU_THR=0.15) → chamfer(2.0)
# 新：尺寸 → chamfer(CH_THR)，Hu 粗篩整個移除
#
# 移除理由是實測而非推論：12 張灰階圖 2016 個輪廓候選，過尺寸閘門 509 個，
# **過 Hu 者 0 個**——這道粗篩從未放行過任何東西，路線 B 整條是死碼。
# 候選對全庫的最佳 Hu 距離，中位數 CubiCasa 系 8.67／Asset 系 3.98，
# 最小值 0.484／0.178，全都遠在 0.15 之外。
# 成因：Hu 矩對「向量渲染 vs 點陣化」極敏感，而查詢側是真實圖面裁出的輪廓
# （斷線、鄰接墨水、雜訊）。0.15 應是拿模板對模板校出來的，對真實查詢無效。
# 調高門檻已實測為淨負面（v2.18：bath precision 0.920→0.676），因為那是全域
# 旋鈕，真假證據一起放行——真正該換的是「用什麼指標」與「開哪幾類」。
CH_THR = 1.2                 # chamfer 平均邊緣距離門檻（48px 畫布上的 px）
                             # 1.2 為 v2.18 §4 天花板量測所用值；舊 2.0 是搭配
                             # Hu 粗篩的寬鬆值，粗篩移除後由它獨自把關故收緊

# 只有這兩類的模板證據進得了計分。依 Readme v2.18 §4 的逐類品質分級：
#   kstove/ksink  ✅ 四口爐與雙槽圖案獨特，是唯一穩定的真實增益
#   wardrobe      ❌ 假陽性大戶——平面圖衣櫃＝長方形＋內部分隔線，與牆體
#                    剖面線／樓梯踏步幾何同構，本質不可分辨
#   chair/basin/sofa/tub ⚠️ 混雜，basin 是 bath precision 崩壞元凶之一
#   bed/wc/dtable  準但量太少
# 在 load_lib() 就濾掉，未啟用的類別連 chamfer 都不算（尺寸閘門也隨之收窄）。
# SYMBOL_KINDS 環境變數可覆寫供 A/B 驗收（同 CC_WEIGHTS／CC_CACHE_DIR 慣例）。
ENABLED_KINDS = tuple(
    k for k in os.environ.get("SYMBOL_KINDS", "kstove,ksink").split(",") if k)


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


def dist_transform(raster):
    """線稿 → 各像素到最近線點的距離場。模板側可預算，見 load_lib()。"""
    return cv2.distanceTransform(255 - raster, cv2.DIST_L2, 3)


def _one_way(a, dt_b):
    pts = a > 0
    if not pts.any():
        return 1e9
    return float(dt_b[pts].mean())


def chamfer_dt(cand, dt_cand, tpl, dt_tpl):
    """對稱 chamfer，距離場由呼叫端提供（模板側預算、候選側每候選算一次）。
    與 chamfer_score 數值相同，只是把重複的 distanceTransform 提出迴圈——
    Hu 粗篩移除後每個候選要對整個 kind 的模板算 chamfer，這是可行性關鍵。"""
    return max(_one_way(cand, dt_tpl), _one_way(tpl, dt_cand))


def chamfer_score(cand, tpl):
    """對稱 chamfer：兩張 48×48 線稿互相取「線點到對方最近線點」平均距離(px)。
    參考實作（每次重算距離場）；熱路徑請用 chamfer_dt。"""
    return chamfer_dt(cand, dist_transform(cand), tpl, dist_transform(tpl))


_lib_cache = "unloaded"


def load_lib(path=LIB_PATH, kinds=ENABLED_KINDS):
    """載入模板庫；檔案不存在回 None（管線行為不變）。模組級快取。

    只保留 `kinds` 指定的類別——未啟用者連 chamfer 都不必算，且尺寸閘門
    隨之收窄（少了 wardrobe/sofa 那些大尺寸區間，雜訊候選先被擋一輪）。
    同時預算每條模板的距離場供 chamfer_dt 使用。"""
    global _lib_cache
    if _lib_cache == "unloaded":
        if not os.path.isfile(path):
            _lib_cache = None
            return _lib_cache
        z = np.load(path, allow_pickle=False)
        all_labels = [str(x) for x in z["labels"]]
        missing = sorted(set(kinds) - set(all_labels))
        if missing:                    # 靜默停用是本模組的既有陷阱，這裡出聲
            print(f"[RoomPilot] symbol kinds unavailable: {', '.join(missing)}")
        keep = [i for i, l in enumerate(all_labels) if l in kinds]
        if not keep:
            print("[RoomPilot] no enabled symbol kinds; optional matching is disabled")
            _lib_cache = None
            return _lib_cache
        labels = [all_labels[i] for i in keep]
        rasters = z["rasters"][keep]
        wh = z["wh"][keep]
        _lib_cache = {
            "rasters": rasters,
            "hu": z["hu"][keep],          # 保留供研發工具/去重用，比對已不讀
            "labels": labels,
            "dt": np.stack([dist_transform(r) for r in rasters]),
            # 每 kind 的實體尺寸閘門：短邊/長邊的 P5~P95（svg 單位≈cm）
            "size": {k: (np.percentile(wh[[i for i, l in enumerate(labels)
                                           if l == k]].min(1), [5, 95]),
                         np.percentile(wh[[i for i, l in enumerate(labels)
                                           if l == k]].max(1), [5, 95]))
                     for k in sorted(set(labels))},
        }
    return _lib_cache


def _in_text_box(x, y, w, h, boxes):
    """候選 bbox 中心落在任一文字框內 → 判為圖面文字，不是家具符號。
    floor06 的「LNDRY」「BALCONY」字樣 chamfer 1.58/1.68 曾被判成 ksink/sofa。"""
    cx, cy = x + w / 2.0, y + h / 2.0
    return any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in boxes)


def match_symbols(det, lib=None):
    """細線層輪廓對模板庫比對 → [(kind, cx, cy)]，kind ∈ ENABLED_KINDS。

    閘門：文字抑制 → 尺寸(P5~P95 ±20%) → chamfer ≤ CH_THR。
    Hu 粗篩已於 2026-07-29 移除（實測從未放行任何候選，見檔頭說明）。
    `det["text_boxes"]` 缺席＝不抑制（彩圖管線無 OCR、deskew 開啟時亦然）。"""
    lib = lib if lib is not None else load_lib()
    thin, cm = det.get("thin"), det["cm"]
    if lib is None or thin is None:
        return []
    boxes = det.get("text_boxes") or ()
    closed = cv2.morphologyEx(thin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    rasters, dts, labels = lib["rasters"], lib["dt"], lib["labels"]
    idx_of = {k: [i for i, l in enumerate(labels) if l == k]
              for k in lib["size"]}
    syms = []
    for c in cnts:
        if len(c) < 20:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if _in_text_box(x, y, w, h, boxes):
            continue
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
        dt_cand = dist_transform(cand)
        best_kind, best_ch = None, 1e9
        for k in ok_kinds:
            for i in idx_of[k]:
                ch = chamfer_dt(cand, dt_cand, rasters[i], dts[i])
                if ch < best_ch:
                    best_kind, best_ch = k, ch
        if best_kind is not None and best_ch <= CH_THR:
            syms.append((best_kind, x + w / 2.0, y + h / 2.0))
    return syms
