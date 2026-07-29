"""extract_asset_lib.py — 階段 A：Asset 家具素材灌入符號模板庫。

testdata/Asset/ 的 10 類 DWG 切割線稿 PNG → 48×48 標準模板，
近重複去重後「併入」既有 symbol_lib.npz（repo 根，保留 CubiCasa 系模板）。
房型歸屬依使用者裁決：dinner_table→kitchen、chairs（單人沙發）→living。

Asset PNG 無比例資訊，實體尺寸閘門（wh）以家具物理常識範圍給值：
每類模板的 wh 沿範圍線性鋪開，使 match_symbols 的 P5~P95 閘門
覆蓋整段合理尺寸。

用法：python extract_asset_lib.py [--out symbol_lib.npz]
分批模式：預設一次只算 --batch 個類別，算完存檢查點（--ckpt-dir）即停；
重複執行同指令續跑，十類檢查點齊全那次才合併寫入 --out。
"""
import argparse
import glob
import os
import sys
from collections import Counter

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "backend", "floorplan"))

from symbol_match import CANVAS, hu_of

# Asset 目錄 → (kind, (短邊lo, 短邊hi, 長邊lo, 長邊hi) cm)
ASSET_KINDS = [
    ("bathroom/wc",           ("wc",       (35, 60, 50, 85))),
    ("bathroom/tub",          ("tub",      (70, 95, 140, 190))),
    ("bathroom/washbasin",    ("basin",    (30, 60, 40, 95))),
    ("kitchen/cook_stove",    ("kstove",   (50, 75, 55, 95))),
    ("kitchen/sink",          ("ksink",    (40, 70, 45, 120))),
    ("kitchen/dinner_table",  ("dtable",   (70, 120, 90, 220))),
    ("bedroom/beds",          ("bed",      (90, 180, 180, 225))),
    ("bedroom/wardrobe",      ("wardrobe", (45, 70, 80, 250))),
    ("livingroom/sofas",      ("sofa",     (80, 110, 140, 260))),
    ("livingroom/chairs",     ("chair",    (60, 95, 65, 110))),
]
ASSET_ROOT = "testdata/Asset"
DEDUP_CHAMFER = 0.6            # 近重複門檻（48px 畫布 chamfer px）


def png_to_template(path, canvas=CANVAS):
    """線稿 PNG → 48×48 標準模板（黑底白線，等比置中，同 crop_to_canvas 正規化）。
    alpha 圖先合成白底；內容 bbox 裁切後縮放，線寬歸一 ~1px。"""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 3 and img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        bgr = cv2.merge([b, g, r]).astype(np.float32)
        am = a.astype(np.float32)[..., None] / 255.0
        img = (bgr * am + 255.0 * (1 - am)).astype(np.uint8)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    ys, xs = np.nonzero(bw)
    if ys.size < 20:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = bw[y0:y1, x0:x1]
    w, h = x1 - x0, y1 - y0
    s = (canvas - 4) / max(w, h)
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    small = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    small = (small > 40).astype(np.uint8) * 255
    out = np.zeros((canvas, canvas), np.uint8)
    ox, oy = (canvas - nw) // 2, (canvas - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out


def _chamfer(a, b):
    da = cv2.distanceTransform(255 - b, cv2.DIST_L2, 3)
    db = cv2.distanceTransform(255 - a, cv2.DIST_L2, 3)
    pa, pb = a > 0, b > 0
    if not pa.any() or not pb.any():
        return 1e9
    return max(float(da[pa].mean()), float(db[pb].mean()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="symbol_lib.npz")
    ap.add_argument("--ckpt-dir", default="training/asset_ckpt")
    ap.add_argument("--batch", type=int, default=1,
                    help="本次最多新算幾個類別（已有檢查點的直接沿用）")
    ap.add_argument("--redo", action="store_true", help="忽略檢查點全部重算")
    a = ap.parse_args()

    cv2.setNumThreads(1)                       # 壓低瞬時負載
    os.makedirs(a.ckpt_dir, exist_ok=True)
    entries = []                               # (kind, raster, wh)
    stats = Counter()
    budget, pending = a.batch, []
    for sub, (kind, (s_lo, s_hi, l_lo, l_hi)) in ASSET_KINDS:
        ck = os.path.join(a.ckpt_dir, kind + ".npz")
        if os.path.isfile(ck) and not a.redo:  # 沿用檢查點
            z = np.load(ck)
            kept = list(z["rasters"])
            stats[kind + "_dup"] = int(z["dup"])
            src = "檢查點"
        elif budget > 0:                       # 本批新算
            budget -= 1
            files = sorted(glob.glob(os.path.join(ASSET_ROOT, sub, "*.png")))
            kept = []
            for f in files:
                r = png_to_template(f)
                if r is None:
                    continue
                if any(_chamfer(r, k) < DEDUP_CHAMFER for k in kept):
                    stats[kind + "_dup"] += 1
                    continue                   # 近重複去重
                kept.append(r)
            arr = (np.stack(kept) if kept
                   else np.zeros((0, CANVAS, CANVAS), np.uint8))
            np.savez_compressed(ck, rasters=arr, dup=stats[kind + "_dup"])
            src = f"{len(files)} 張新算"
        else:
            pending.append(kind)
            continue
        # wh 沿物理範圍線性鋪開 → P5~P95 閘門涵蓋整段
        n = max(1, len(kept))
        for i, r in enumerate(kept):
            t = i / max(1, n - 1) if n > 1 else 0.5
            wh = (s_lo + t * (s_hi - s_lo), l_lo + t * (l_hi - l_lo))
            entries.append((kind, r, wh))
        stats[kind] = len(kept)
        print(f"{kind:9s} {src} → 模板 {len(kept):4d}"
              f"（重複 {stats[kind + '_dup']}）")

    if pending:
        print(f"\n本批額度（--batch {a.batch}）用盡，尚餘 {len(pending)} 類："
              f"{', '.join(pending)}。重跑同指令續算；全部完成那次才會寫入 {a.out}。")
        return

    if os.path.isfile(a.out):                  # 併入既有庫（保留 CubiCasa 系）
        z = np.load(a.out, allow_pickle=False)
        old_labels = [str(x) for x in z["labels"]]
        keep = [i for i, l in enumerate(old_labels)
                if l not in {k for _s, (k, _r) in ASSET_KINDS}]  # 舊 Asset 條目換新
        rasters = [z["rasters"][i] for i in keep]
        labels = [old_labels[i] for i in keep]
        wh = [tuple(z["wh"][i]) for i in keep]
        print(f"既有庫保留 {len(keep)} 條")
    else:
        rasters, labels, wh = [], [], []

    for kind, r, s in entries:
        rasters.append(r); labels.append(kind); wh.append(s)
    rasters = np.stack(rasters)
    hu = np.stack([hu_of(r) for r in rasters]).astype(np.float32)
    np.savez_compressed(a.out, rasters=rasters, hu=hu,
                        labels=np.array(labels), wh=np.array(wh, np.float32))
    print(f"\n完成 → {a.out}：共 {len(labels)} 模板（Asset 新增 {len(entries)}）")


if __name__ == "__main__":
    main()
