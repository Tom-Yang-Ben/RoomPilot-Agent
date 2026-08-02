"""eval_door_json.py — 產品前端 json（temp/json/gray/*.json）門位 P/R。

門偵測重建（2026-08-02）端到端量尺：直接跑 floorplan2dxf.run()（
產品 DXF 批次路），讀它寫出的前端 json doors 欄位對 own GT 配分——
與 eval_door_zones（room 管線 zones）互補，量的是前端實際拿到的資料。

GT = own_dataset/<名>/model.svg 的 Door 多邊形 bbox（±TOL px）。
配對：door px 中心落在 GT bbox（外擴 TOL）內，1-1 貪婪。

用法：python training/scripts/eval_door_json.py [--tol 12]
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "backend", "floorplan"))

SCRATCH = os.environ.get("DOOR_JSON_SCRATCH", "temp/eval_doors")


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
    ap.add_argument("--tol", type=int, default=12)
    a = ap.parse_args()

    import floorplan2dxf as fp_bw
    cfg0 = fp_bw.load_config("config.ini")
    os.makedirs(SCRATCH, exist_ok=True)

    tp = fp_ = fn = 0
    for d in sorted(glob.glob("testdata/Identify_ans/own_dataset/floor*")):
        sid = os.path.basename(d)
        img = os.path.join(d, "F1_scaled.png")
        svg = os.path.join(d, "model.svg")
        if not (os.path.isfile(img) and os.path.isfile(svg)):
            continue
        staged = os.path.join(SCRATCH, sid + ".png")   # base 決定 json 檔名
        shutil.copy(img, staged)
        jp = os.path.join("temp/json/gray", sid + ".json")
        if os.path.isfile(jp):
            os.remove(jp)                              # 防讀到舊批次殘留
        cfg = replace(cfg0, input=staged,
                      output=os.path.join(SCRATCH, sid + ".dxf"),
                      preview=None)
        try:
            fp_bw.run(cfg)
        except SystemExit:
            pass
        if not os.path.isfile(jp):
            print(f"{sid}: 無 json 輸出，跳過")
            continue
        doors = json.load(open(jp, encoding="utf-8")).get("doors", [])
        quads = gt_quads(svg)
        used = set()
        n_tp = 0
        for dd in doors:
            cx, cy = dd["px"]["cx"], dd["px"]["cy"]
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
        print(f"{sid}: GT {len(quads)} json doors {len(doors)} TP {n_tp}")
    p = tp / max(1, tp + fp_)
    r = tp / max(1, tp + fn)
    print(f"\n產品 json 門位: P={p:.2f} ({tp}/{tp + fp_})  "
          f"R={r:.2f} ({tp}/{tp + fn})")


if __name__ == "__main__":
    main()
