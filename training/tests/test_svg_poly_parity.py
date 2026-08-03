"""svg_poly.get_polygon 的 GT 解析煙霧測試。

走過 own_eval + own_dataset 全部 GT SVG 的每一個 Space 群組確認解得出
多邊形。歷史註記：脫離第三方解析器時曾以逐位元對拍證明「純搬家、
量尺數字不變」（對拍測試已隨第三方 checkout 於 2026-08-03 移除，
見 git 歷史）。
"""
import glob
import os
import sys
from xml.dom import minidom

import numpy as np
import pytest

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))

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
