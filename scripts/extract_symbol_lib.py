"""extract_symbol_lib.py — 路線圖 B：從 train 樣本建符號模板庫（一次性）。

走訪 CubiCasa5k train.txt 全部樣本的 model.svg，萃取六類 FixedFurniture
（Toilet/Bathtub/BathtubRound/IntegratedStove/Sink/Shower）的向量線稿，
以 local 座標渲染成 48×48 標準模板（方向已標準化，零牆線/文字污染），
去重後存 symbol_lib.npz。val/test 樣本完全不碰（評分集衛生，同路線 A）。

用法：python extract_symbol_lib.py [--out symbol_lib.npz]
"""
import argparse
import os
from collections import Counter
from xml.dom import minidom

import numpy as np

from symbol_match import CANVAS, TARGETS, collect_primitives, hu_of, \
    render_polylines

DATA = "training/CubiCasa5k/data/cubicasa5k"


def extract_sample(svg_path):
    """單一樣本 → [(kind, raster, (w, h))]；w/h 取 BoundaryPolygon 外框。"""
    out = []
    try:
        doc = minidom.parse(svg_path)
    except Exception:
        return out                            # 壞檔跳過（主迴圈計數）
    for e in doc.getElementsByTagName("g"):
        toks = set(e.getAttribute("class").split())
        hit = toks & set(TARGETS)
        if "FixedFurniture" not in toks or not hit:
            continue
        polys = collect_primitives(e)
        r = render_polylines(polys)
        if r is None:
            continue
        allp = np.vstack(polys)
        w, h = allp.max(0) - allp.min(0)
        out.append((TARGETS[hit.pop()], r, (float(w), float(h))))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="training/symbol_lib.npz")
    a = ap.parse_args()

    with open(os.path.join(DATA, "train.txt")) as f:
        ids = [ln.strip().strip("/") for ln in f if ln.strip()]
    total, bad = Counter(), 0
    seen = {}                                 # (kind, raster bytes) → 首見紀錄
    for n, rel in enumerate(ids, 1):
        svg_f = os.path.join(DATA, rel, "model.svg")
        if not os.path.isfile(svg_f):
            bad += 1
            continue
        for kind, r, wh in extract_sample(svg_f):
            total[kind] += 1
            key = (kind, r.tobytes())
            if key not in seen:
                seen[key] = (kind, r, wh)
        if n % 500 == 0:
            print(f"[{n}/{len(ids)}] 變體 {len(seen)}")

    kinds = [v[0] for v in seen.values()]
    rasters = np.stack([v[1] for v in seen.values()])
    wh = np.array([v[2] for v in seen.values()], np.float32)
    hu = np.stack([hu_of(r) for r in rasters]).astype(np.float32)
    np.savez_compressed(a.out, rasters=rasters, hu=hu,
                        labels=np.array(kinds), wh=wh)

    uniq = Counter(kinds)
    print(f"\n完成：{len(ids)} 樣本（壞檔 {bad}）→ {a.out}")
    for k in sorted(total):
        print(f"  {k:8s} 總數 {total[k]:6d} → 變體 {uniq[k]:5d}")


if __name__ == "__main__":
    main()
