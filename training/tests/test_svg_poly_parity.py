"""svg_poly.get_polygon 與 CubiCasa5k 原版的逐位元對拍。

走過 own_eval + own_dataset 全部 GT SVG 的每一個 Space 群組，兩份實作
各解一次，np.array_equal 斷言 rr/cc 完全相等——證明「去 floortrans」
是純搬家，量尺數字不可能變。

原版需要 training/CubiCasa5k/（不進版控）；沒有就 skip 整組，
自家實作的煙霧測試（test_smoke_parses_own_eval）仍會跑。
"""
import glob
import os
import sys
from xml.dom import minidom

import numpy as np
import pytest

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
_CC = os.path.join(_ROOT, "training", "CubiCasa5k")

from svg_poly import get_polygon as get_polygon_ours  # noqa: E402（conftest 已把 scripts/ 加路徑）

GT_GLOBS = [
    os.path.join(_ROOT, "testdata", "Identify_ans", "own_eval", "*", "model.svg"),
    os.path.join(_ROOT, "testdata", "Identify_ans", "own_dataset", "*", "model.svg"),
]


def _all_svgs():
    return sorted(p for g in GT_GLOBS for p in glob.glob(g))


def _space_groups(svg_path):
    doc = minidom.parse(svg_path)
    for e in doc.getElementsByTagName("g"):
        cls = e.getAttribute("class").split(" ")
        if cls and cls[0] == "Space":
            yield e


def test_smoke_parses_own_eval():
    """不靠原版：自家實作至少要能解出非空多邊形。"""
    svgs = _all_svgs()
    assert svgs, "找不到任何 GT model.svg——答案集路徑變了？"
    parsed = 0
    for svg in svgs:
        for e in _space_groups(svg):
            try:
                rr, cc = get_polygon_ours(e)
            except StopIteration:      # 空群組（Inkscape 殘留）與原版同行為
                continue
            assert rr.shape == cc.shape
            parsed += 1
    assert parsed > 0, "所有 SVG 都沒解出 Space 多邊形"


@pytest.mark.skipif(
    not os.path.isdir(os.path.join(_CC, "floortrans")),
    reason="training/CubiCasa5k/ 不在（gitignore 大檔），無原版可對拍")
def test_bit_for_bit_parity_with_floortrans():
    sys.path.insert(0, _CC)
    from floortrans.loaders.svg_utils import get_polygon as get_polygon_cc

    total = 0
    for svg in _all_svgs():
        for e in _space_groups(svg):
            try:
                ours = get_polygon_ours(e)
            except StopIteration:
                with pytest.raises(StopIteration):
                    get_polygon_cc(e)
                continue
            theirs = get_polygon_cc(e)
            assert np.array_equal(ours[0], theirs[0]), f"rr 不等：{svg}"
            assert np.array_equal(ours[1], theirs[1]), f"cc 不等：{svg}"
            total += 1
    assert total > 0, "對拍樣本數為 0——答案集是空的？"
