"""symbol_match 純函式測試：SVG 渲染、Hu 距離、chamfer。"""
import numpy as np
import cv2
import sys, os
from xml.dom import minidom
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from symbol_match import (collect_primitives, render_polylines, hu_of,
                          hu_dist, chamfer_score, CANVAS)

STOVE_SVG = """<g class="FixedFurniture ElectricalAppliance IntegratedStove"
  transform="matrix(0,1,-1,0,100,200)" fill="#ffffff" stroke="#000000">
  <g class="BoundaryPolygon" fill="rgb(255,255,255)" stroke="rgb(0,0,0)">
    <polygon points="2 2 58 2 58 58 2 58"/></g>
  <g class="OuterCircle" fill="rgb(255,255,255)" stroke="rgb(0,0,0)">
    <circle cx="16" cy="16" r="8"/><circle cx="44" cy="16" r="8"/>
    <circle cx="16" cy="44" r="8"/><circle cx="44" cy="44" r="8"/></g>
  <g class="Direction" style="display: none;">
    <polygon points="0 0 500 0 500 500" fill="#444444"/></g>
</g>"""

TOILET_SVG = """<g class="FixedFurniture Toilet" fill="#ffffff" stroke="#000000">
  <g class="BoundaryPolygon" fill="none" stroke="none">
    <polygon points="0,0 41,0 41,71 0,71"/></g>
  <g class="InnerPolygon">
    <rect x="0.5" y="0.5" width="40" height="18"/>
    <path d="M40.5,44.2S41.6,70.5,20.9,70.5C-.5,70.5.6,44.2.6,44.2L.5,18.5H40.5Z"/>
  </g>
</g>"""


def _node(xml):
    return minidom.parseString(xml).documentElement


def test_collect_excludes_hidden_and_invisible():
    polys = collect_primitives(_node(STOVE_SVG))
    allp = np.vstack(polys)
    assert allp[:, 0].max() < 100          # display:none 的 500 座標沒混進來
    assert len(polys) == 5                 # 外框 + 4 圈


def test_collect_skips_stroke_none_boundary():
    polys = collect_primitives(_node(TOILET_SVG))
    assert len(polys) == 2                 # 只有 InnerPolygon 的 rect+path


def test_render_nonempty_and_centered():
    r = render_polylines(collect_primitives(_node(STOVE_SVG)))
    assert r is not None and r.shape == (CANVAS, CANVAS)
    assert int(np.count_nonzero(r)) > 40


def test_hu_identity_and_separation():
    stove = render_polylines(collect_primitives(_node(STOVE_SVG)))
    toilet = render_polylines(collect_primitives(_node(TOILET_SVG)))
    hs, ht = hu_of(stove), hu_of(toilet)
    assert hu_dist(hs, hs) < 1e-9
    assert hu_dist(hs, ht) > 5 * hu_dist(hs, hs) + 0.01


def test_chamfer_identity_lt_cross():
    stove = render_polylines(collect_primitives(_node(STOVE_SVG)))
    toilet = render_polylines(collect_primitives(_node(TOILET_SVG)))
    assert chamfer_score(stove, stove) < 0.1
    assert chamfer_score(stove, toilet) > chamfer_score(stove, stove) + 1.0
