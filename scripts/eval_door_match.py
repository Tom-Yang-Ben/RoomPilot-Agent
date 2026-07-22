"""eval_door_match.py — 門候選評分：score vs score_fused 的 A/B（26 題 own GT）。

GT = Identify_ans/own_dataset/<名>/model.svg 的 Door quad（人工校正過）。
候選 = json/gray/<名>.json 的 doors（跑過 door_match.py 後含 score_fused）。

配對規則：候選鉸鏈點落在 GT quad（外擴 TOL px）內。
對每個門檻策略（score ≥ 0.85 / score_fused ≥ 0.85）算：
    P = 入選候選中配對到 GT 的比例（誤報看這裡）
    R = GT 門中被任一入選候選命中的比例（漏門看這裡）

用法：python scripts/eval_door_match.py [--thr 0.85] [--tol 12]
"""
import argparse
import glob
import json
import os
import re
import xml.etree.ElementTree as ET

import cv2
import numpy as np

SVG = "{http://www.w3.org/2000/svg}"


def gt_quads(svg_path):
    """model.svg → [np.array(4,2)]；吃 polygon points ＋ 可能的 translate。"""
    quads = []
    root = ET.parse(svg_path).getroot()
    for g in root.iter(SVG + "g"):
        if (g.get("class") or "") != "Door":
            continue
        tf = g.get("transform") or ""
        m = re.match(r"translate\(([-\d.]+),([-\d.]+)\)", tf)
        off = (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
        for p in g.iter(SVG + "polygon"):
            pts = np.array([[float(v) for v in t.split(",")]
                            for t in p.get("points").split()], np.float32)
            quads.append((pts + off).astype(np.float32))
    return quads


def evaluate(thr, tol, key):
    tp = fp = 0
    gt_total = gt_hit = 0
    for svg_path in sorted(glob.glob("Identify_ans/own_dataset/*/model.svg")):
        name = os.path.basename(os.path.dirname(svg_path))
        jpath = os.path.join("json/gray", name + ".json")
        if not os.path.isfile(jpath):
            continue
        quads = gt_quads(svg_path)
        doors = json.load(open(jpath)).get("doors", [])
        sel = [d for d in doors if d.get(key, d["score"]) >= thr]
        hit_gt = set()
        for d in sel:
            pt = (d["px"]["cx"], d["px"]["cy"])
            ok = False
            for qi, q in enumerate(quads):
                if cv2.pointPolygonTest(q.reshape(-1, 1, 2), pt, True) >= -tol:
                    ok = True
                    hit_gt.add(qi)
            tp += ok
            fp += not ok
        gt_total += len(quads)
        gt_hit += len(hit_gt)
    P = tp / (tp + fp) if tp + fp else 0.0
    R = gt_hit / gt_total if gt_total else 0.0
    return P, R, tp, fp, gt_hit, gt_total


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--thr", type=float, default=0.85)
    ap.add_argument("--tol", type=float, default=12.0)
    a = ap.parse_args()

    for label, key in [("score      (基線)", "score"),
                       ("score_fused(融合)", "score_fused")]:
        P, R, tp, fp, gh, gt = evaluate(a.thr, a.tol, key)
        print(f"{label}: P={P:.3f} ({tp}/{tp+fp})  R={R:.3f} ({gh}/{gt})")


if __name__ == "__main__":
    main()
