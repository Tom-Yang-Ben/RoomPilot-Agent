"""make_annotation_drafts.py — 路線圖 C 準備：43 題標注初稿（管線輸出→人工修正）。

把 png/ 每張圖的管線輸出（牆矩形/窗/門位/房間方塊+房型/符號命中）組成
CubiCasa model.svg 格式草稿，存 own_dataset/<名>/{F1_scaled.png,
F1_original.png, model.svg}。FloorplanSVG loader format='txt' 可直接吃，
junction heatmap 由 House 從 SVG 自動推導；人工用 Inkscape 修正即可。

用法：python make_annotation_drafts.py [--png-dir png] [--out own_dataset]
產出後逐張以 House() 回讀驗證；own_train.txt 43 行 / own_val.txt 5 行。
"""
import argparse
import os
import shutil
import sys
from xml.dom import minidom

import cv2
import numpy as np

# 管線 label → CubiCasa 房型 class（rooms_selected 的鍵值域）
CUBI_CLASS = {"bed": "Bedroom", "bath": "Bath", "kitchen": "Kitchen",
              "living": "LivingRoom", "entry": "Entry", "storage": "Storage",
              "garage": "Garage", "outdoor": "Outdoor", "balcony": "Outdoor",
              "room": "Undefined", None: "Undefined", "": "Undefined"}
# 符號 kind → FixedFurniture class 與名義尺寸(px 於 cm=1 時)。
# bedrect 不輸出——CubiCasa 圖示分類法沒有床（床的訊息在房間類別）
SYM_CLASS = {"oval": ("Toilet", 40, 70), "tubrect": ("Bathtub", 75, 160),
             "stove": ("ElectricalAppliance IntegratedStove", 58, 58),
             "shower": ("Shower", 90, 90),
             "sinkicon": ("Sink", 45, 50)}
VAL_PICKS = {"floor01", "floor10", "floor20", "floor30", "floor40"}


def to_cubicasa_class(label):
    return CUBI_CLASS.get(label, "Undefined")


def _pts(points):
    """頂點清單 → points 屬性字串（尾隨空格：PolygonWall split(' ')[:-1]）。"""
    return "".join(f"{float(x):.1f},{float(y):.1f} " for x, y in points)


# 顯示樣式（人工修正用；House 訓練解析只讀 g/polygon 結構，不受影響）
FILL = {"Wall": ("#cc2222", 0.45), "Window": ("#22aa22", 0.6),
        "Door": ("#ddaa00", 0.6)}
SPACE_FILL = {"Bedroom": "#4a90d9", "Bath": "#3dbdbd", "Kitchen": "#e8843c",
              "LivingRoom": "#7dc37d", "Entry": "#c9a0dc", "Storage": "#b8a06a",
              "Garage": "#909090", "Outdoor": "#c77dbb", "Undefined": "#d9d9d9"}


def _g_poly(doc, points, gid=None, cls=None, fill=None, opacity=0.4,
            label=None):
    g = doc.createElement("g")
    if gid:
        g.setAttribute("id", gid)
    if cls:
        g.setAttribute("class", cls)
    p = doc.createElement("polygon")
    p.setAttribute("points", _pts(points))
    if fill:
        p.setAttribute("fill", fill)
        p.setAttribute("fill-opacity", str(opacity))
        p.setAttribute("stroke", fill)
        p.setAttribute("stroke-width", "2")
    g.appendChild(p)
    if label:                                    # 房型文字（修正時一眼可辨）
        pts_arr = np.asarray(points, float)
        cx, cy = pts_arr.mean(0)
        t = doc.createElement("text")
        t.setAttribute("x", f"{cx:.0f}")
        t.setAttribute("y", f"{cy:.0f}")
        t.setAttribute("font-size", "22")
        t.setAttribute("text-anchor", "middle")
        t.setAttribute("fill", "#000000")
        t.appendChild(doc.createTextNode(label))
        g.appendChild(t)
    return g


def room_polygons(labels, rooms):
    """每房 mask → 最大外輪廓 approxPolyDP → [(label, Nx2 頂點)]。"""
    out = []
    for r in rooms:
        m = (labels == r["id"]).astype(np.uint8)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea)
        ap = cv2.approxPolyDP(c, 2.0, True)[:, 0, :]
        if len(ap) >= 3:
            out.append((r.get("label"), ap))
    return out


def build_svg(w, h, rects, wins, zones, spaces, symbols):
    """管線輸出 → CubiCasa model.svg 草稿（minidom Document）。
    rects=[(x0,y0,x1,y1)] wins=[(o,x0,y0,x1,y1)] zones=[(quad,·)]
    spaces=[(label, Nx2)] symbols=[(kind,cx,cy)]。座標=圖像素。"""
    imp = minidom.getDOMImplementation()
    doc = imp.createDocument(None, "svg", None)
    svg = doc.documentElement
    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg")
    svg.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink")
    svg.setAttribute("width", str(w))
    svg.setAttribute("height", str(h))
    svg.setAttribute("viewBox", f"0 0 {w} {h}")
    img = doc.createElement("image")             # 底圖（人工修正的參照）
    img.setAttribute("href", "F1_scaled.png")
    img.setAttribute("xlink:href", "F1_scaled.png")
    img.setAttribute("x", "0")
    img.setAttribute("y", "0")
    img.setAttribute("width", str(w))
    img.setAttribute("height", str(h))
    svg.appendChild(img)
    model = doc.createElement("g")
    model.setAttribute("id", "Model")
    model.setAttribute("class", "Model")
    svg.appendChild(model)
    for x0, y0, x1, y1 in rects:
        model.appendChild(_g_poly(doc, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                  gid="Wall", cls="Wall", fill=FILL["Wall"][0],
                                  opacity=FILL["Wall"][1]))
    for _o, x0, y0, x1, y1 in wins:
        model.appendChild(_g_poly(doc, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                  gid="Window", cls="Window",
                                  fill=FILL["Window"][0],
                                  opacity=FILL["Window"][1]))
    for quad, _d in zones:
        model.appendChild(_g_poly(doc, quad, gid="Door", cls="Door",
                                  fill=FILL["Door"][0], opacity=FILL["Door"][1]))
    for label, pts in spaces:
        cc = to_cubicasa_class(label)
        model.appendChild(_g_poly(doc, pts, cls=f"Space {cc}",
                                  fill=SPACE_FILL.get(cc, "#d9d9d9"),
                                  opacity=0.35, label=cc))
    for kind, cx, cy in symbols:
        cls, sw, sh = SYM_CLASS.get(kind, (None, 0, 0))
        if not cls:
            continue
        g = doc.createElement("g")
        g.setAttribute("class", f"FixedFurniture {cls}")
        g.setAttribute("transform",
                       f"matrix(1,0,0,1,{cx - sw / 2:.1f},{cy - sh / 2:.1f})")
        b = doc.createElement("g")
        b.setAttribute("class", "BoundaryPolygon")
        p = doc.createElement("polygon")
        p.setAttribute("points", f"0,0 {sw},0 {sw},{sh} 0,{sh}")
        p.setAttribute("fill", "#8844cc")
        p.setAttribute("fill-opacity", "0.4")
        p.setAttribute("stroke", "#8844cc")
        p.setAttribute("stroke-width", "2")
        b.appendChild(p)
        g.appendChild(b)
        model.appendChild(g)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--png-dir", default="png")
    ap.add_argument("--out", default="own_dataset")
    a = ap.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "CubiCasa5k"))
    from floortrans.loaders.house import House
    import floorplan2dxf as fp_bw
    import floorplan2dxf_color as fp_c
    import floorplan2room as f2r
    from eval_rooms_cc import run_pipeline
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_color = fp_c.load_config("config_color.ini")

    imgs = sorted(p for p in os.listdir(a.png_dir) if p.endswith(".png"))
    ok, fail = [], []
    for n, fn in enumerate(imgs, 1):
        name = os.path.splitext(fn)[0]
        src = os.path.join(a.png_dir, fn)
        print(f"[{n}/{len(imgs)}] {name}", flush=True)
        try:
            det, labels, rooms = run_pipeline(src, cfg_bw, cfg_color)
            bgr = det["bgr"]
            h, w = bgr.shape[:2]
            if labels is not None and labels.shape != (h, w):
                labels = cv2.resize(labels.astype(np.int32), (w, h),
                                    interpolation=cv2.INTER_NEAREST)
            # 門位 quad 需重算（run_pipeline 不回傳 zones）
            _l, _r, _b, zones, _e = f2r.build_rooms(det)
            spaces = room_polygons(labels, rooms) if rooms else []
            doc = build_svg(w, h, det["rects"], det["wins"], zones, spaces,
                            det.get("symbols", []))
            d = os.path.join(a.out, name)
            os.makedirs(d, exist_ok=True)
            shutil.copy(src, os.path.join(d, "F1_scaled.png"))
            shutil.copy(src, os.path.join(d, "F1_original.png"))
            svg_path = os.path.join(d, "model.svg")
            with open(svg_path, "w") as f:
                f.write(doc.toprettyxml(indent=" "))
            house = House(svg_path, h, w)          # round-trip 驗證
            if int(np.count_nonzero(house.walls == 2)) == 0:
                raise ValueError("round-trip 無牆像素")
            ok.append(name)
        except Exception as e:
            fail.append((name, repr(e)))
            print(f"  ✗ {e!r}")

    with open(os.path.join(a.out, "own_train.txt"), "w") as f:
        f.writelines(f"/{n}/\n" for n in ok)
    with open(os.path.join(a.out, "own_val.txt"), "w") as f:
        f.writelines(f"/{n}/\n" for n in ok if n in VAL_PICKS)
    print(f"\n完成 {len(ok)}/{len(imgs)}；失敗：{fail if fail else '無'}")
    print(f"→ {a.out}/（含 own_train.txt {len(ok)} 行）")


if __name__ == "__main__":
    main()
