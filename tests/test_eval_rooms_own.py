"""own_eval 量尺模式（eval_rooms_cc --own-eval）樣本挑選與報表路徑測試。"""
import os

import eval_rooms_cc as ev


def test_pick_own_samples_twelve_complete():
    samples = ev.pick_own_samples()
    assert len(samples) == 12
    assert all(split == "own" for split, _ in samples)
    ids = [sid for _, sid in samples]
    assert ids[0] == "floor55" and ids[-1] == "floor79"
    for sid in ids:
        d = os.path.join(ev.OWN_DIR, sid)
        assert os.path.isfile(os.path.join(d, "F1_scaled.png")), sid
        assert os.path.isfile(os.path.join(d, "model.svg")), sid


def test_report_path_for_all_modes():
    assert ev.report_path_for(False, False) == "json/eval_rooms/report.json"
    assert ev.report_path_for(False, True) == "json/eval_rooms/report_gtseg.json"
    assert ev.report_path_for(True, False) == "json/eval_rooms/report_own.json"
    assert ev.report_path_for(True, True) == "json/eval_rooms/report_own_gtseg.json"


def test_transform_baking_matrix_translate_scale():
    import fix_annotation_paths as fx
    m = fx.parse_transform("translate(10,20) scale(2)")
    assert fx.mat_mul(m, fx.IDENTITY) == m
    x, y = 3.0, 4.0
    a, b, c, d, tx, ty = m
    assert (a * x + c * y + tx, b * x + d * y + ty) == (16.0, 28.0)
    assert fx.is_identity(fx.parse_transform(""))
    m2 = fx.parse_transform("matrix(1.5,0,0,0.5,-100,7)")
    assert m2 == (1.5, 0, 0, 0.5, -100, 7)
    try:
        fx.parse_transform("rotate(45)")
        assert False, "rotate 應報錯"
    except ValueError:
        pass


def test_fix_svg_bakes_group_transform(tmp_path):
    import fix_annotation_paths as fx
    svg = tmp_path / "model.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="Model"><g class="Space Kitchen" '
        'transform="translate(100,0) scale(2,1)">'
        '<polygon points="0,0 10,0 10,10 0,10"/></g></g></svg>')
    converted, errors = fx.fix_svg(str(svg), check_only=False)
    assert converted == ["Space Kitchen[transform]"] and not errors
    from xml.dom import minidom
    doc = minidom.parse(str(svg))
    g = [e for e in doc.getElementsByTagName("g")
         if "Space" in e.getAttribute("class")][0]
    assert not g.getAttribute("transform")
    pts = g.getElementsByTagName("polygon")[0].getAttribute("points")
    assert pts == "100,0 120,0 120,10 100,10"


def test_fix_svg_path_own_transform_and_text_child(tmp_path):
    import fix_annotation_paths as fx
    svg = tmp_path / "model.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<g class="Model"><g class="Space Bath" transform="translate(50,0)">'
        '<text transform="scale(2)">Bath</text>'
        '<path transform="translate(0,10)" d="M 0,0 H 10 V 10 H 0 Z"/>'
        '</g></g></svg>')
    converted, errors = fx.fix_svg(str(svg), check_only=False)
    assert converted == ["Space Bath[path+transform]"] and not errors
    from xml.dom import minidom
    doc = minidom.parse(str(svg))
    g = [e for e in doc.getElementsByTagName("g")
         if "Space" in e.getAttribute("class")][0]
    assert not g.getAttribute("transform")
    pts = g.getElementsByTagName("polygon")[0].getAttribute("points")
    assert pts == "50,10 60,10 60,20 50,20"     # g平移+path平移 兩層都烘進座標
    text = g.getElementsByTagName("text")[0]
    assert text.getAttribute("transform") == "translate(50,0) scale(2)"
