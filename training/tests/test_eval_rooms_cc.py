"""eval_rooms_cc 純函式測試：配對、正規化、混淆矩陣。"""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval_rooms_cc import match_rooms, norm_label, confusion


def _m(h, w, y0, y1, x0, x1):
    m = np.zeros((h, w), bool)
    m[y0:y1, x0:x1] = True
    return m


def test_match_perfect_overlap():
    gt = [_m(20, 20, 0, 10, 0, 10)]
    pred = [_m(20, 20, 0, 10, 0, 10)]
    got = match_rooms(gt, pred)
    assert got == [(0, 0, pytest.approx(1.0))]


def test_match_below_threshold_excluded():
    gt = [_m(20, 20, 0, 10, 0, 10)]          # 100 px
    pred = [_m(20, 20, 0, 10, 0, 4)]         # 交 40 聯 100 → IoU 0.4 < 0.5
    assert match_rooms(gt, pred) == []


def test_match_greedy_one_to_one():
    # 兩 GT 兩 pred：pred0 與 gt0 IoU 高、與 gt1 也重疊——貪婪應各配各的
    gt = [_m(30, 30, 0, 10, 0, 10), _m(30, 30, 10, 20, 0, 10)]
    pred = [_m(30, 30, 0, 11, 0, 10), _m(30, 30, 11, 20, 0, 10)]
    got = match_rooms(gt, pred)
    assert sorted((g, p) for g, p, _ in got) == [(0, 0), (1, 1)]


def test_norm_label():
    assert norm_label("balcony") == "outdoor"
    assert norm_label("room") == "space"
    assert norm_label(None) == "space"
    assert norm_label("bed") == "bed"


def test_confusion_counts():
    pairs = [("bed", "bed"), ("bed", "bath"), ("space", "space")]
    cm = confusion(pairs)
    assert cm["bed"]["bed"] == 1 and cm["bed"]["bath"] == 1
    assert cm["space"]["space"] == 1
