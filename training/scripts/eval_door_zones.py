"""eval_door_zones.py — 產品門位（build_rooms zones）對 own GT 的 P/R。

門偵測重建（2026-08-02）：弧掃描 detect_doors 的 P 0.38/R 0.17 遠低於
可用線，且產品 room json 的 doors 欄位本就來自 zones（門尺寸牆縫＋墨
水證據，`write_rooms_json`）——本工具把量尺對準產品實際輸出路。

GT = own_dataset(_color)/<名>/model.svg 的 Door 多邊形 bbox（±TOL px）。
配對：zone 四邊形中心落在 GT bbox（外擴 TOL）內，1-1 貪婪。

用法：python training/scripts/eval_door_zones.py [--color] [--tol 12]
"""
import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "backend", "floorplan"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def gt_quads(svg):
    out = []
    root = ET.parse(svg).getroot()
    for g in root.iter():
        if g.get("class", "").startswith("Door"):
            for p in g.iter():
                pts = p.get("points")
                if pts:
                    xy = [float(v) for v in re.split(r"[ ,]+", pts.strip())
                          if v]
                    xs, ys = xy[0::2], xy[1::2]
                    out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--color", action="store_true",
                    help="量 own_dataset_color（預設灰階 own_dataset）")
    ap.add_argument("--tol", type=int, default=12)
    a = ap.parse_args()

    import eval_rooms_cc as ev
    import floorplan2dxf as fp_bw
    import floorplan2dxf_color as fp_c
    import floorplan2room as f2r
    cfg_bw = fp_bw.load_config("config.ini")
    cfg_c = fp_c.load_config("config_color.ini")

    root = ("testdata/Identify_ans/own_dataset_color" if a.color
            else "testdata/Identify_ans/own_dataset")
    pat = "color_floor_*" if a.color else "floor*"
    tp = fp_ = fn = 0
    for d in sorted(glob.glob(os.path.join(root, pat))):
        sid = os.path.basename(d)
        img = os.path.join("temp/eval_rooms/input", sid + ".png")
        svg = os.path.join(d, "model.svg")
        if not (os.path.isfile(img) and os.path.isfile(svg)):
            continue
        det, _l, _r = ev.run_pipeline(img, cfg_bw, cfg_c, build=False)
        _labels, _rooms, _b, zones, _e = f2r.build_rooms(det)
        # 彩圖管線 2x：zones 座標除回 1x 與 GT 對齊
        sc = det["img_w"] / float(__import__("cv2").imread(
            os.path.join(d, "F1_scaled.png")).shape[1])
        quads = gt_quads(svg)
        used = set()
        n_tp = 0
        for quad, _dd in zones:
            cx = sum(p[0] for p in quad) / 4.0 / sc
            cy = sum(p[1] for p in quad) / 4.0 / sc
            hit = None
            for i, (x0, y0, x1, y1) in enumerate(quads):
                if i in used:
                    continue
                if x0 - a.tol <= cx <= x1 + a.tol \
                        and y0 - a.tol <= cy <= y1 + a.tol:
                    hit = i
                    break
            if hit is not None:
                used.add(hit)
                n_tp += 1
            else:
                fp_ += 1
        tp += n_tp
        fn += len(quads) - len(used)
        print(f"{sid}: GT {len(quads)} zones {len(zones)} TP {n_tp}")
    p = tp / max(1, tp + fp_)
    r = tp / max(1, tp + fn)
    print(f"\n產品門位（zones）: P={p:.2f} ({tp}/{tp+fp_})  "
          f"R={r:.2f} ({tp}/{tp+fn})")


if __name__ == "__main__":
    main()
