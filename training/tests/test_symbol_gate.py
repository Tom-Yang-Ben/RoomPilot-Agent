"""模板比對閘門重構（2026-07-29）——Hu 粗篩移除、逐類啟用、文字抑制。

背景實測（12 張灰階圖）：輪廓候選 2016 → 過尺寸閘門 509 → **過 Hu 粗篩 0**。
`HU_THR=0.15` 從未放行過任何東西，模板比對整條路線是死碼。成因是 Hu 矩對
「向量渲染 vs 點陣化」極度敏感，而查詢側是真實圖面裁出的輪廓（斷線、鄰接
墨水、雜訊），與任何模板的 Hu 距離都差 1~2 個數量級。
"""
import numpy as np
import cv2

import symbol_match as sm


# ─────────────────────────── 逐類啟用 ───────────────────────────
def test_enabled_kinds_is_the_measured_shortlist():
    """2026-08-01 偵測層強化輪：probe_symbol_quality.py 以 GT 房型多邊形
    當弱標籤逐模板掃描後擴充啟用清單——tub(P0.85@0.8)/wc(P0.86@1.2)/
    bed/chair(0.8 嚴門檻 0FP) 加入；basin 全類 P=0.33 但以模板白名單
    ＋1.35 門檻外科啟用（7 條 ~8TP/0FP）；sofa/wardrobe/dtable P≤0.5
    續停（wardrobe 與牆剖面線／樓梯踏步幾何同構，本質不可分辨）。
    2026-08-02 美式素材輪（symbol_quality_v225.json）：trashcan 新啟用
    （0.8 嚴門檻 2TP/0FP，floor09 廚房證據）；basin 白名單補 4 條新模板
    （1.35 門檻下無 FP）。"""
    assert set(sm.ENABLED_KINDS) == {"kstove", "ksink", "tub", "wc",
                                     "bed", "chair", "basin", "trashcan"}
    assert sm.CH_THR_BY_KIND == {"tub": 0.8, "bed": 0.8, "chair": 0.8,
                                 "basin": 1.35, "trashcan": 0.8}
    assert set(sm.TPL_WHITELIST) == {"basin"}
    assert set(sm.TPL_BLACKLIST) == {"tub"}


def test_per_template_threshold_overrides_kind():
    """TPL_THR（2026-08-02 美式素材輪）：類門檻放行但逐模板門檻更嚴時，
    該模板不得放行——basin 262 型「Bath TP ≤1.011 / Kitchen FP ≥1.187」
    只有逐模板 1.1 能全收 TP、全擋 FP（kind 門檻 1.35 動不得，
    舊白名單 tpl 236 的 floor38 救援 TP 在 1.277）。"""
    gi = int(sm.load_lib()["gidx"][sm.load_lib()["labels"].index("basin")])
    old_wl, old_thr = sm.TPL_WHITELIST, sm.TPL_THR
    try:
        # 白名單縮到單條，再以「縮後庫」的尺寸閘門植入 → chamfer≈0 必放行
        #（尺寸閘門是逐 kind 百分位，縮名單會挪動，植入必須照縮後的算）
        sm.TPL_WHITELIST = {"basin": (gi,)}
        sm.TPL_THR = dict(old_thr)
        sm._lib_cache = "unloaded"
        lib = sm.load_lib()
        i = lib["labels"].index("basin")
        det = {"thin": _thin_with_raster(lib["rasters"][i], lib, "basin"),
               "cm": 1.0}
        assert "basin" in [k for k, _x, _y in sm.match_symbols(det)]
        # 對同一條模板設不可能過的逐模板門檻 → 同畫面不得再放行
        sm.TPL_THR = {**old_thr, gi: -1.0}
        sm._lib_cache = "unloaded"
        assert "basin" not in [k for k, _x, _y in sm.match_symbols(det)]
    finally:
        sm.TPL_WHITELIST, sm.TPL_THR = old_wl, old_thr
        sm._lib_cache = "unloaded"


def test_tpl_thr_is_the_measured_surgical_set():
    """v225 probe 全集稽核：257→0.8（floor47 方盤 TP 0.366、floor09 FP
    1.078）；258/261/262 同族 1.1（262 的 Bath TP 全 ≤1.011、Kitchen FP
    全 ≥1.187）。259 有 floor07 五連 FP（1.16~1.28），不入白名單。"""
    assert sm.TPL_THR == {257: 0.8, 258: 1.1, 261: 1.1, 262: 1.1}
    assert 259 not in sm.TPL_WHITELIST["basin"]


def test_lib_exposes_only_enabled_kinds():
    lib = sm.load_lib()
    assert lib is not None
    assert set(lib["labels"]) == set(sm.ENABLED_KINDS)
    assert set(lib["size"]) == set(sm.ENABLED_KINDS)


def test_cubicasa_vector_templates_are_pruned():
    """3516 條 CubiCasa 向量模板已於 2026-07-29 剪除（4459→943）。
    A/B 實測：新閘門下把它們全部加回，24 圖/157 房的混淆矩陣逐格完全相同、
    具名 118/157 一分未動——零貢獻。其中 sinkicon 2110＋stove 1402 就佔 3512，
    oval/shower 各僅 1 條、tubrect 2 條。
    註：手寫幾何規則 detect_symbols 仍獨立產出 oval/tubrect/bedrect/stove，
    那條路不受本次剪除影響。"""
    import numpy as np
    z = np.load(sm.LIB_PATH, allow_pickle=False)
    labels = {str(x) for x in z["labels"]}
    assert not (labels & {"oval", "tubrect", "stove", "sinkicon", "shower"})


def test_missing_kind_is_not_silent(capsys):
    """要求的 kind 不在庫裡必須出聲——靜默停用是本模組的既有陷阱。"""
    sm._lib_cache = "unloaded"
    try:
        sm.load_lib(kinds=("sinkicon",))
        assert "sinkicon" in capsys.readouterr().out
    finally:
        sm._lib_cache = "unloaded"


def test_lib_arrays_stay_aligned_after_filtering():
    lib = sm.load_lib()
    n = len(lib["labels"])
    assert n > 0
    assert lib["rasters"].shape[0] == n
    assert lib["dt"].shape[0] == n          # 預算距離轉換與模板一一對應


# ─────────────────────────── chamfer 預算 ───────────────────────────
def _two_shapes():
    a = np.zeros((48, 48), np.uint8)
    cv2.rectangle(a, (10, 10), (38, 38), 255, 1)
    b = np.zeros((48, 48), np.uint8)
    cv2.circle(b, (24, 24), 14, 255, 1)
    return a, b


def test_precomputed_chamfer_equals_reference():
    """預算模板側距離轉換只是把重複運算提出迴圈，數值必須與原函式相同。"""
    a, b = _two_shapes()
    dt_b = sm.dist_transform(b)
    dt_a = sm.dist_transform(a)
    assert abs(sm.chamfer_dt(a, dt_a, b, dt_b) - sm.chamfer_score(a, b)) < 1e-6


def test_chamfer_identity_is_zero():
    a, _ = _two_shapes()
    assert sm.chamfer_dt(a, sm.dist_transform(a), a, sm.dist_transform(a)) < 1e-6


# ─────────────────────────── 端到端：閘門真的放行 ───────────────────────────
def _thin_with_template(kind, canvas=400):
    """把庫裡一條真模板貼進細線層，模擬圖面上的該符號。

    縮放需照「內容 bbox」而非畫布——png_to_template 保持長寬比置中，
    48×48 畫布內的內容通常小得多（實測某 kstove 僅 44×25）。直接縮放畫布
    會讓實體尺寸算錯而落在尺寸閘門外。cm=1.0 → 尺寸(px)即尺寸(cm)。"""
    lib = sm.load_lib()
    i = lib["labels"].index(kind)
    tpl = lib["rasters"][i]
    return _thin_with_raster(tpl, lib, kind, canvas)


def _thin_with_raster(tpl, lib, kind, canvas=400):
    ys, xs = np.nonzero(tpl)
    content = tpl[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch_, cw_ = content.shape
    (s5, s95), _ = lib["size"][kind]
    target_short = float(np.mean([s5, s95]))          # 尺寸閘門正中央
    scale = target_short / min(ch_, cw_)
    big = cv2.resize(content, (max(1, int(round(cw_ * scale))),
                               max(1, int(round(ch_ * scale)))),
                     interpolation=cv2.INTER_NEAREST)
    img = np.zeros((canvas, canvas), np.uint8)
    img[100:100 + big.shape[0], 100:100 + big.shape[1]] = big
    return img


def test_match_finds_planted_template():
    """舊 Hu 閘門下這一定是 0 命中——本測試即「路線 B 不再是死碼」的證據。

    2026-08-01 起逐模板試植：多部件符號（wc＝馬桶碗＋水箱）植入後裂成
    小輪廓過不了尺寸閘門，「第一條模板必可自我配對」不成立；改為每類
    至少有一條模板可自我配對（實圖命中證據見 symbol_quality 掃描）。"""
    lib = sm.load_lib()
    for kind in sm.ENABLED_KINDS:
        idx = [i for i, l in enumerate(lib["labels"]) if l == kind]
        ok = False
        for i in idx[:20]:
            det = {"thin": _thin_with_raster(lib["rasters"][i], lib, kind),
                   "cm": 1.0}
            if kind in [k for k, _x, _y in sm.match_symbols(det)]:
                ok = True
                break
        assert ok, f"{kind}: 前 {min(20, len(idx))} 條模板無一可自我配對"


def test_no_thin_layer_returns_empty():
    assert sm.match_symbols({"thin": None, "cm": 1.0}) == []


# ─────────────────────────── 文字抑制 ───────────────────────────
def test_text_box_suppresses_match():
    """圖面文字會被判成符號（floor06 的 LNDRY/BALCONY 實案被判 ksink/sofa）。
    detect_text_boxes() 早就存在，本輪才接進符號比對。"""
    kind = sm.ENABLED_KINDS[0]
    det = {"thin": _thin_with_template(kind), "cm": 1.0}
    assert kind in [k for k, _x, _y in sm.match_symbols(det)]

    det_txt = dict(det, text_boxes=[(90, 90, 180, 180)])   # 蓋住植入位置
    assert sm.match_symbols(det_txt) == []


def test_text_box_elsewhere_does_not_suppress():
    kind = sm.ENABLED_KINDS[0]
    det = {"thin": _thin_with_template(kind), "cm": 1.0,
           "text_boxes": [(250, 250, 290, 290)]}          # 不相干位置
    assert kind in [k for k, _x, _y in sm.match_symbols(det)]


def test_missing_text_boxes_key_is_safe():
    """det 沒有 text_boxes 鍵（彩圖管線／舊呼叫端）不得炸。"""
    kind = sm.ENABLED_KINDS[0]
    det = {"thin": _thin_with_template(kind), "cm": 1.0}
    assert kind in [k for k, _x, _y in sm.match_symbols(det)]


# ─────────────────────────── 管線接線 ───────────────────────────
def test_pipeline_computes_text_boxes_before_symbols():
    """process() 原本先算 symbols 再算 text_boxes，抑制會拿到空清單。
    以原始碼順序斷言，避免日後重構把它換回去。"""
    import inspect
    import floorplan2room as fp
    src = inspect.getsource(fp.process)
    assert src.index("text_boxes") < src.index('det["symbols"]')
