"""make_annotation_drafts 測試：房型映射、SVG 組裝、草稿回讀驗證。"""
import os
import sys
import tempfile
from xml.dom import minidom

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from make_annotation_drafts import (SPACE_FILL, to_cubicasa_class, build_svg,
                                    verify_draft)


def test_mapping_covers_all_pipeline_labels():
    import floorplan2room as f2r
    import floorplan2dxf_color as fp_c
    keys = set(fp_c.ROOM_ZH) | set(f2r.ROOM_ZH_EX) | {None}
    for k in keys:
        assert to_cubicasa_class(k), f"label {k!r} 無映射"
    assert to_cubicasa_class(None) == "Undefined"
    assert to_cubicasa_class("Bedroom") == "Bedroom"
    assert to_cubicasa_class("Balcony") == "Balcony"   # 2026-08-01 詞彙統一


def _sample_svg():
    rects = [(10.0, 10.0, 100.0, 18.0), (10.0, 10.0, 18.0, 100.0)]
    wins = [(0, 40.0, 10.0, 60.0, 18.0)]
    zones = [([(70.0, 10.0), (90.0, 10.0), (90.0, 18.0), (70.0, 18.0)], None)]
    spaces = [("Bedroom", np.array([[20, 20], [95, 20], [95, 95], [20, 95]]))]
    symbols = [("oval", 50.0, 50.0)]
    return build_svg(120, 120, rects, wins, zones, spaces, symbols)


def test_build_svg_structure():
    doc = _sample_svg()
    xml = doc.toxml()
    reparsed = minidom.parseString(xml)          # XML 合法
    walls = [e for e in reparsed.getElementsByTagName("g")
             if e.getAttribute("id") == "Wall"]
    assert len(walls) == 2
    pts = walls[0].getElementsByTagName("polygon")[0].getAttribute("points")
    assert pts.endswith(" ")                     # PolygonWall split(' ')[:-1] 陷阱
    assert len(pts.split(" ")[:-1]) == 4         # 去尾後仍 4 頂點
    spaces = [e for e in reparsed.getElementsByTagName("g")
              if e.getAttribute("class").startswith("Space ")]
    assert spaces and "Bedroom" in spaces[0].getAttribute("class")
    assert [e for e in reparsed.getElementsByTagName("g")
            if e.getAttribute("id") == "Window"]


def _written(spaces):
    """把草稿寫成暫存檔，回傳路徑（呼叫端負責刪）。"""
    rects = [(10.0, 10.0, 100.0, 18.0), (10.0, 10.0, 18.0, 100.0)]
    doc = build_svg(120, 120, rects, [], [], spaces, [])
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False,
                                     encoding="utf-8") as f:
        f.write(doc.toxml())
        return f.name


# ─────────────────────── 草稿回讀（不經 CubiCasa House）───────────────────────
@pytest.mark.parametrize("lab", ["Hallway", "Stair", "Balcony", "Storage",
                                 "Bedroom", "LivingRoom"])
def test_verify_draft_accepts_every_new_class(lab):
    """10 類詞彙每一個都要能產草稿再回讀。

    這是 2026-08-01 改名時漏掉的路徑：舊驗證走 CubiCasa 的 `House`，其
    `room_name_map` 只認得舊詞彙且查表無防護（house.py:548），`Hallway`／
    `Stair`／`Balcony` 一律 KeyError。舊測試只用 `Bedroom`——CubiCasa 認得
    的 token——所以整條路壞掉卻全綠。"""
    path = _written([(lab, np.array([[20, 20], [95, 20], [95, 95], [20, 95]]))])
    try:
        n_room, n_wall = verify_draft(path, 120, 120)
        assert (n_room, n_wall) == (1, 2)
    finally:
        os.unlink(path)


def test_verify_draft_rejects_missing_walls():
    doc = build_svg(120, 120, [], [], [], [], [])
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False,
                                     encoding="utf-8") as f:
        f.write(doc.toxml())
        path = f.name
    try:
        with pytest.raises(ValueError, match="無牆"):
            verify_draft(path, 120, 120)
    finally:
        os.unlink(path)


def test_space_fill_covers_exactly_the_ten_classes():
    """草稿配色表漏一類就會靜默塗成灰色，人工修正時看不出那是未命名還是走道。"""
    from eval_rooms_cc import CLASSES
    assert set(SPACE_FILL) == set(CLASSES) | {"Undefined"}


def test_cubicasa_house_still_cannot_read_new_vocabulary():
    """釘住「為何不能用 House 驗證」——它對新詞彙會炸，別再把它接回來。

    若哪天這個測試失敗（House 能讀了），代表上游或 vendored checkout 換了，
    屆時才可以重新考慮。"""
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "training/CubiCasa5k"))
    from floortrans.loaders.house import House
    path = _written([("Hallway",
                      np.array([[20, 20], [95, 20], [95, 95], [20, 95]]))])
    try:
        with pytest.raises(KeyError):
            House(path, 120, 120)
    finally:
        os.unlink(path)
