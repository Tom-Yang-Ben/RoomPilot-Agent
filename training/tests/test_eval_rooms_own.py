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
    assert ev.report_path_for(False, False) == "training/json/eval_rooms/report.json"
    assert ev.report_path_for(False, True) == "training/json/eval_rooms/report_gtseg.json"
    assert ev.report_path_for(True, False) == "training/json/eval_rooms/report_own.json"
    assert ev.report_path_for(True, True) == "training/json/eval_rooms/report_own_gtseg.json"


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
    assert pts == "100,0 120,0 120,10 100,10 "


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
    assert pts == "50,10 60,10 60,20 50,20 "     # g平移+path平移 兩層都烘進座標
    text = g.getElementsByTagName("text")[0]
    assert text.getAttribute("transform") == "translate(50,0) scale(2)"


def test_crop_bbox_margin_and_clip():
    import numpy as np
    import extract_room_crops as ex
    img = np.zeros((100, 200, 3), np.uint8)
    rr = np.array([10, 50]); cc = np.array([20, 80])
    crop, bbox = ex.crop_bbox(img, rr, cc, margin=0.1)
    assert bbox == [6, 54, 14, 86]              # ±10% 邊距
    assert crop.shape[:2] == (48, 72)
    crop2, bbox2 = ex.crop_bbox(img, np.array([0, 99]), np.array([0, 199]), 0.2)
    assert bbox2 == [0, 100, 0, 200]            # 邊距不得超出圖面


def test_crop_labels_share_one_source_of_truth():
    """extract_room_crops 原本自帶一份 norm_label 副本，會與量尺各自漂移
    （office/stair 拆分後就現形了）。2026-07-29 起改用 eval_rooms_cc.gt_label_of，
    分類器、量尺、管線三方類別空間一致。"""
    import extract_room_crops as ex
    from eval_rooms_cc import gt_label_of
    assert not hasattr(ex, "norm_label")        # 副本已移除，勿再長回來
    assert gt_label_of("Office") == "storage"
    assert gt_label_of("StairWell") == "stair"


def test_rebuild_split_by_seeds_and_polygon():
    import numpy as np
    import rebuild_room_gt as rb
    region = np.zeros((40, 60), np.uint8)
    region[5:35, 5:55] = 1                       # 一大區
    s_left = np.zeros_like(region); s_left[10:15, 8:12] = 1
    s_right = np.zeros_like(region); s_right[10:15, 48:52] = 1
    out = rb.split_by_seeds(region, [(0, s_left), (1, s_right)])
    assert out[0][12, 10] == 1 and out[1][12, 50] == 1
    assert out[0][12, 50] == 0 and out[1][12, 10] == 0
    assert int(out[0].sum()) + int(out[1].sum()) == int(region.sum())
    poly = rb.mask_to_polygon(out[0] * 255 // 255)
    assert poly is not None and len(poly) >= 3


def test_all_annotation_polygons_have_trailing_space():
    """House get_polygon 會把 points split(' ') 後砍最後一項——
    CubiCasa 慣例是尾空格結尾；缺尾空格的 polygon 會丟失最後一個頂點。"""
    import glob
    from xml.dom import minidom
    for svg in (glob.glob("Identify_ans/own_eval/floor*/model.svg")
                + glob.glob("Identify_ans/own_dataset/floor*/model.svg")):
        doc = minidom.parse(svg)
        for p in doc.getElementsByTagName("polygon"):
            pts = p.getAttribute("points")
            assert pts and pts[-1].isspace(), f"{svg} 有 polygon 缺尾空格"
