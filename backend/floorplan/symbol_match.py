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
LIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "symbol_lib.npz")
# 推論期資產，與消費它的模組同目錄（2026-07-29 由 repo 根移入）——
# 只搬 backend/floorplan/ 的部署不會再解析到錯路徑（舊版往上三層推導，
# 且找不到檔不報錯、靜默停用，是無聲失效的高風險寫法）
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
                             # 1.2 為 v2.18 §4 天花板量測所用值；2026-08-01
                             # 起為預設值，逐類覆寫見 CH_THR_BY_KIND
# 逐類門檻（2026-08-01 偵測層強化輪）：probe_symbol_quality.py 對
# own_dataset 24 題以 GT 房型多邊形當弱標籤逐模板掃描，各 kind 的
# TP/FP–門檻曲線量出的甜蜜點——tub 在 0.8 是 11TP/2FP（P=0.85），
# 放到 1.2 則 FP 翻五倍；wc 在 1.2 即有 P=0.86。
CH_THR_BY_KIND = {"tub": 0.8, "bed": 0.8, "chair": 0.8, "basin": 1.35,
                  # trashcan（2026-08-02 美式素材輪）：0.8 嚴門檻 2TP/0FP
                  #（floor09 廚房×2@0.21/0.24；FP 最近在 0.977 被擋）
                  "trashcan": 0.8}

# 模板白名單（npz 全域序號）：類別整體混雜但個別模板乾淨時的外科手術。
# basin 全類 P=0.33（tpl 157 一條就打 45 個 FP），但這七條在 1.35 門檻
# 下合計 ~8TP/0FP——floor38 浴室漏切正缺 basin 證據（tpl 235@1.277）。
# 未列名的類別＝全部模板可用。
# 序號基準＝2026-08-02 重建庫（961 條，美式畫風素材併入）；舊 943 庫
# 序號經 raster 逐位元比對映射（174→175, …, 251→252），語意不變。
# 2026-08-02 美式素材輪補 4 條新模板（257/258/261/262，方盤/橢圓盆），
# 各掛 TPL_THR 逐模板門檻（見下）。259 在 floor07 有五連 FP（1.16~1.28）、
# 256/260 帶 ≤1.35 FP（LivingRoom/Kitchen 誤擊），不入。
TPL_WHITELIST = {"basin": (175, 179, 180, 236, 244, 250, 252,
                           257, 258, 261, 262)}
# 逐模板門檻覆寫（npz 全域序號 → chamfer 上限），優先於 CH_THR_BY_KIND。
# 用於「類門檻動不得、個別模板 TP/FP 分界更緊」的外科場景：basin 類門檻
# 1.35 由舊白名單 tpl 236 的 floor38 救援 TP（1.277）鎖住，但美式新模板
# 257 的分界在 0.8（TP 0.366/FP 1.078）、262 在 1.1（Bath TP ≤1.011/
# Kitchen FP ≥1.187）——probe v225 全集量測，258/261 零命中掛同族 1.1。
TPL_THR = {257: 0.8, 258: 1.1, 261: 1.1, 262: 1.1}
# 模板黑名單：類別整體乾淨但個別模板出格。tub 主力是 tpl 118
#（10TP 全在浴室），舊 119/128（新 120/129）在 0.8 嚴門檻內仍各打一次
# 臥室/客廳假陽性（floor38/31 實測），剪除。
TPL_BLACKLIST = {"tub": (120, 129)}

# 啟用清單依 2026-08-01 逐模板品質掃描（temp/json/symbol_quality.json）：
#   kstove/ksink  ✅ 沿用（v2.18 判定的穩定增益）
#   tub/wc        ✅ 新啟用——P 0.85/0.86，正是 floor38/44 浴室漏切缺的證據
#   bed/chair     ✅ 新啟用（0.8 嚴門檻下 0 FP，量少但乾淨）
#   sofa          ❌ P≤0.5，本畫風沙發比對不穩，續停
#   basin/wardrobe/dtable ❌ P≤0.5，v2.18 的判斷獲弱標籤掃描證實
# 在 load_lib() 就濾掉，未啟用的類別連 chamfer 都不算（尺寸閘門也隨之收窄）。
# SYMBOL_KINDS 環境變數可覆寫供 A/B 驗收（同 CC_WEIGHTS／CC_CACHE_DIR 慣例）。
ENABLED_KINDS = tuple(
    k for k in os.environ.get(
        "SYMBOL_KINDS", "kstove,ksink,tub,wc,bed,chair,basin,trashcan").split(",")
    if k)
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
            print(f"⚠ 模板庫無這些 kind：{', '.join(missing)}"
                  f"（庫內有 {', '.join(sorted(set(all_labels)))}）")
        keep = [i for i, l in enumerate(all_labels)
                if l in kinds
                and (l not in TPL_WHITELIST or i in TPL_WHITELIST[l])
                and i not in TPL_BLACKLIST.get(l, ())]
        if not keep:
            print(f"⚠ 模板庫沒有任何啟用中的 kind → 模板比對停用")
            _lib_cache = None
            return _lib_cache
        labels = [all_labels[i] for i in keep]
        rasters = z["rasters"][keep]
        wh = z["wh"][keep]
        _lib_cache = {
            "gidx": np.array(keep),       # 過濾後 → npz 全域序號（TPL_THR 用）
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
        # 「各自門檻內的最佳者」勝出——不是全域最佳再驗門檻。逐類門檻
        # 引入後兩者不同：嚴門檻類（tub 0.8）以 0.9 搶下全域最佳會讓
        # 整個候選被丟棄，而寬門檻類（wc 1.2）的 0.95 本可合格
        best_kind, best_ch = None, 1e9
        gidx = lib.get("gidx")
        for k in ok_kinds:
            thr_k = CH_THR_BY_KIND.get(k, CH_THR)
            for i in idx_of[k]:
                # 逐模板門檻覆寫（無 gidx 的外部庫沿用類門檻）
                thr_i = (TPL_THR.get(int(gidx[i]), thr_k)
                         if gidx is not None else thr_k)
                ch = chamfer_dt(cand, dt_cand, rasters[i], dts[i])
                if ch <= thr_i and ch < best_ch:
                    best_kind, best_ch = k, ch
        if best_kind is not None:
            syms.append((best_kind, x + w / 2.0, y + h / 2.0))
    return syms
