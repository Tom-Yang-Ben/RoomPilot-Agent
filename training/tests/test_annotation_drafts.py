"""make_annotation_drafts 測試：房型映射、SVG 組裝、House round-trip。"""
import os
import sys
import tempfile
from xml.dom import minidom

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from make_annotation_drafts import to_cubicasa_class, build_svg


def test_mapping_covers_all_pipeline_labels():
    import floorplan2room as f2r
    import floorplan2dxf_color as fp_c
    keys = set(fp_c.ROOM_ZH) | set(f2r.ROOM_ZH_EX) | {None}
    for k in keys:
        assert to_cubicasa_class(k), f"label {k!r} 無映射"
    assert to_cubicasa_class(None) == "Undefined"
    assert to_cubicasa_class("bed") == "Bedroom"
    assert to_cubicasa_class("balcony") == "Outdoor"


def _sample_svg():
    rects = [(10.0, 10.0, 100.0, 18.0), (10.0, 10.0, 18.0, 100.0)]
    wins = [(0, 40.0, 10.0, 60.0, 18.0)]
    zones = [([(70.0, 10.0), (90.0, 10.0), (90.0, 18.0), (70.0, 18.0)], None)]
    spaces = [("bed", np.array([[20, 20], [95, 20], [95, 95], [20, 95]]))]
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


def test_house_round_trip():
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "training/CubiCasa5k"))
    from floortrans.loaders.house import House
    doc = _sample_svg()
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(doc.toxml())
        path = f.name
    try:
        h = House(path, 120, 120)
        assert int(np.count_nonzero(h.walls == 2)) > 0        # 牆像素
        seg = h.get_segmentation_tensor()
        assert seg.shape[-2:] == (120, 120)
    finally:
        os.unlink(path)
