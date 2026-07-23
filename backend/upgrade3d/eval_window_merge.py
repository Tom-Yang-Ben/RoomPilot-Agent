"""窗段合併 eval:dxf_parser 的 3D 窗輸出 vs floorplan 管線的窗偵測 ground truth。

比對基準:data/testdata/dxf_scale/floorXX.dxf(公分 DXF)經 parse_dxf_file 解析後,
每扇窗應收斂成「一條」中心線段;data/testdata/json/floorXX.json 的 windows(每扇一筆,
cm 座標與 dxf_scale 同座標系)當 ground truth。

配對規則(貪婪一對一):方向相同、中心距離 ≤ 0.25 m、長度差 ≤ max(0.12 m, 12%)。
指標:precision = 配對數/解析窗段數、recall = 配對數/GT 窗數。目標:整體皆 ≥90%。

執行:uv run python backend/upgrade3d/eval_window_merge.py
"""
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.upgrade3d.dxf_parser import parse_dxf_file  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "testdata")
CENTER_TOL = 0.25          # 中心距離容差(m)
LEN_TOL_ABS = 0.12         # 長度容差(m)
LEN_TOL_PCT = 0.12


def gt_windows(meta):
    """json 的窗 bbox(cm,原點左下)→ (orient, cx, cz, length) 公尺。"""
    out = []
    for w in meta["windows"]:
        x0, z0, x1, z1 = [v / 100.0 for v in w["cm"]]
        horiz = (x1 - x0) >= (z1 - z0)
        out.append(("h" if horiz else "v",
                    (x0 + x1) / 2, (z0 + z1) / 2,
                    (x1 - x0) if horiz else (z1 - z0)))
    return out


def parsed_windows(d, meta):
    """parser 窗段(公尺,牆範圍中心原點)→ 同 gt 座標系(原點左下)。
    對齊:兩邊的牆範圍中心應一致,用 json 牆 bbox 中心把 parser 座標平移回去。"""
    xs = [v / 100.0 for w in meta["walls"] for v in (w["cm"][0], w["cm"][2])]
    zs = [v / 100.0 for w in meta["walls"] for v in (w["cm"][1], w["cm"][3])]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    out = []
    for s in d["windows"]:
        x1, z1, x2, z2 = s["x1"] + cx, s["z1"] + cz, s["x2"] + cx, s["z2"] + cz
        horiz = abs(x2 - x1) >= abs(z2 - z1)
        out.append(("h" if horiz else "v",
                    (x1 + x2) / 2, (z1 + z2) / 2,
                    math.hypot(x2 - x1, z2 - z1)))
    return out


def match(gt, got):
    """貪婪一對一配對,回傳配對數。"""
    used = [False] * len(got)
    tp = 0
    for o, cx, cz, ln in gt:
        best, best_d = -1, CENTER_TOL
        for i, (o2, cx2, cz2, ln2) in enumerate(got):
            if used[i] or o2 != o:
                continue
            if abs(ln2 - ln) > max(LEN_TOL_ABS, LEN_TOL_PCT * ln):
                continue
            dist = math.hypot(cx2 - cx, cz2 - cz)
            if dist <= best_d:
                best, best_d = i, dist
        if best >= 0:
            used[best] = True
            tp += 1
    return tp


def main():
    rows, TP, GT, GOT = [], 0, 0, 0
    for jf in sorted(glob.glob(os.path.join(ROOT, "json", "floor*.json"))):
        base = os.path.splitext(os.path.basename(jf))[0]
        dxf = os.path.join(ROOT, "dxf_scale", base + ".dxf")
        if not os.path.isfile(dxf):
            continue
        with open(jf, encoding="utf-8") as fp:
            meta = json.load(fp)
        gt = gt_windows(meta)
        try:
            got = parsed_windows(parse_dxf_file(dxf), meta)
        except Exception as e:
            rows.append((base, len(gt), 0, 0, f"✗ 解析失敗: {e}"))
            GT += len(gt)
            continue
        tp = match(gt, got)
        TP, GT, GOT = TP + tp, GT + len(gt), GOT + len(got)
        mark = "✓" if tp == len(gt) == len(got) else "✗"
        rows.append((base, len(gt), len(got), tp, mark))

    print(f"{'樓層':<10}{'GT窗':>5}{'解析':>5}{'配對':>5}  結果")
    for base, g, n, tp, mark in rows:
        print(f"{base:<10}{g:>5}{n:>5}{tp:>5}  {mark}")
    prec = TP / GOT if GOT else 0.0
    rec = TP / GT if GT else 0.0
    print(f"\n總計: GT {GT} 扇、解析 {GOT} 段、配對 {TP}")
    print(f"precision = {prec:.1%}   recall = {rec:.1%}   (目標皆 ≥90%)")
    ok = prec >= 0.9 and rec >= 0.9
    print("✅ PASS" if ok else "❌ FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
