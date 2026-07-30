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
    """Readme v2.18 §4 逐類品質分級：kstove/ksink 圖案獨特、證據可信；
    wardrobe 是假陽性大戶（平面圖衣櫃＝長方形＋分隔線，與牆剖面線／樓梯
    踏步幾何同構，本質不可分辨），chair/basin/sofa/tub 混雜。"""
    assert set(sm.ENABLED_KINDS) == {"kstove", "ksink"}


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
    """舊 Hu 閘門下這一定是 0 命中——本測試即「路線 B 不再是死碼」的證據。"""
    for kind in sm.ENABLED_KINDS:
        det = {"thin": _thin_with_template(kind), "cm": 1.0}
        got = [k for k, _x, _y in sm.match_symbols(det)]
        assert kind in got, (kind, got)


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
