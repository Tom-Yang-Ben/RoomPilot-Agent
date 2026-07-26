"""extract_door_lib.py — 門樣式模板庫（路線 B 符號救援的門版本，一次性）。

testdata/Asset/door/ 是人工剪裁的各類型門圖示（白底黑線，type01~type12，含雙開/
單開/摺疊等樣式）。本腳本把它們正規化成與 symbol_lib.npz 同規格的 48×48
線稿模板：實心牆段轉輪廓線（查詢側同樣處理才公平）、bbox 裁切置中、
8 向變體（4 旋轉 × 鏡射）展開後去重，存 door_lib.npz。

用途：door_match.py 對主管線的門候選做模板比對，救回弧吻合度低於
0.85 但樣式明確的真門（見 training/json/gray 的 score_fused 欄位）。

用法：python scripts/extract_door_lib.py [--src testdata/Asset/door] [--out door_lib.npz]
"""
import argparse
import glob
import os
import re
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from symbol_match import crop_to_canvas


def outline_bw(gray):
    """灰階 → 黑底白線二值稿：暗色為前景，實心區只留外輪廓。

    門圖示常帶實心牆段（剪裁殘留），整塊進 chamfer 會以面積壓過線條；
    erode-subtract 後粗線/實心塊一律變 1~2px 輪廓，與細線同權。"""
    bw = (gray < 128).astype(np.uint8) * 255
    er = cv2.erode(bw, np.ones((3, 3), np.uint8))
    return cv2.subtract(bw, er)


def to_template(gray):
    """灰階素材圖 → 48×48 標準模板（None = 內容不足）。"""
    ol = outline_bw(gray)
    ys, xs = np.nonzero(ol)
    if len(xs) < 30:
        return None
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    return crop_to_canvas(ol, x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def variants(t):
    """4 旋轉 × 鏡射 = 8 向變體。"""
    out = []
    for m in (t, cv2.flip(t, 1)):
        for k in range(4):
            out.append(np.rot90(m, k).copy())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default="testdata/Asset/door")
    ap.add_argument("--out", default="training/door_lib.npz")
    a = ap.parse_args()

    rasters, kinds, srcs = [], [], []
    seen = set()
    files = sorted(glob.glob(os.path.join(a.src, "*.png")))
    for f in files:
        name = os.path.basename(f)
        m = re.match(r"door_type(\d+)_\d+\.png", name)
        kind = f"door{m.group(1)}" if m else "door"
        gray = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        t = to_template(gray)
        if t is None:
            print(f"跳過（內容不足）：{name}")
            continue
        for v in variants(t):
            key = v.tobytes()
            if key in seen:
                continue
            seen.add(key)
            rasters.append(v)
            kinds.append(kind)
            srcs.append(name)

    np.savez_compressed(a.out, rasters=np.stack(rasters),
                        kinds=np.array(kinds), srcs=np.array(srcs))
    from collections import Counter
    c = Counter(kinds)
    print(f"{len(files)} 張素材 → {len(rasters)} 個模板（8 向展開去重）→ {a.out}")
    print("  " + "  ".join(f"{k}×{n}" for k, n in sorted(c.items())))


if __name__ == "__main__":
    main()
