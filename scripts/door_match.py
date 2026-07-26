"""door_match.py — 門候選 × 門樣式模板比對，產生融合分數（後處理，不動凍結檔）。

主管線（floorplan2dxf.py，已凍結）把全部門候選連同弧吻合度 score 交在
training/json/gray/<名>.json；白模端只收 score ≥ 0.85。本腳本對每個候選在原圖
裁出鉸鏈四象限窗，與 door_lib.npz 模板做對稱 chamfer 比對：

    模板命中（chamfer ≤ CH_STRONG）→ score_fused = max(score, RESCUE)
    未命中                        → score_fused = score（絕不降分）

結果寫回 training/json/gray（新增 tpl_chamfer / tpl_kind / score_fused 欄位，
原 score 不動），前端與白模端可選擇改讀 score_fused。

用法：python scripts/door_match.py [名 ...]     # 預設掃 training/json/gray/*.json
      --lib door_lib.npz  --png-dir png
"""
import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_door_lib import outline_bw
from symbol_match import chamfer_score, crop_to_canvas

CH_STRONG = 1.5   # 命中門檻：26 題實測真門 chamfer 中位 1.02（94%≤1.5）、非門中位 2.16（9%≤1.5）
RESCUE = 0.90     # 命中時的保底分數（> 白模端 0.85 門檻）
MIN_PX = 40       # 象限窗內最少線條像素，低於此不比對（空窗/邊緣外）


def _load_lib(path):
    if not os.path.isfile(path):
        return None
    z = np.load(path, allow_pickle=False)
    return {"rasters": z["rasters"], "kinds": z["kinds"]}


def match_door(ol, cx, cy, w, lib, margin=0.15):
    """對單一門候選比對模板。ol = outline_bw 全圖；回傳 (best_chamfer, kind)。

    detect_doors 的 (cx,cy) 是鉸鏈角、w 是門寬，但 json 沒存開向——
    直接試四個象限窗（門扇＋弧必落在其中一象限），取最好的一格。"""
    H, W = ol.shape
    m = int(round(w * margin))
    side = int(round(w)) + m
    best = (1e9, "")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0 = int(round(cx)) + (-side if sx < 0 else -m)
            y0 = int(round(cy)) + (-side if sy < 0 else -m)
            x1, y1 = x0 + side + m, y0 + side + m
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(W, x1), min(H, y1)
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue
            win = ol[y0:y1, x0:x1]
            ys, xs = np.nonzero(win)
            if len(xs) < MIN_PX:
                continue
            bx0, by0 = xs.min(), ys.min()
            bw_, bh_ = xs.max() - bx0 + 1, ys.max() - by0 + 1
            cand = crop_to_canvas(win, bx0, by0, bw_, bh_)
            if cand is None:
                continue
            for r, k in zip(lib["rasters"], lib["kinds"]):
                ch = chamfer_score(cand, r)
                if ch < best[0]:
                    best = (ch, str(k))
    return best


def rescore_file(jpath, png_dir, lib):
    data = json.load(open(jpath))
    img_file = data["image"]["file"]
    img_path = os.path.join(png_dir, img_file)
    if not os.path.isfile(img_path):
        return None
    gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    ol = outline_bw(gray)
    n_hit = 0
    for d in data.get("doors", []):
        cx, cy, w = d["px"]["cx"], d["px"]["cy"], d["px"]["width"]
        ch, kind = match_door(ol, cx, cy, w, lib)
        d["tpl_chamfer"] = round(ch, 2) if ch < 1e9 else None
        d["tpl_kind"] = kind or None
        hit = ch <= CH_STRONG
        d["score_fused"] = round(max(d["score"], RESCUE), 3) if hit else d["score"]
        n_hit += hit
    with open(jpath, "w") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    return len(data.get("doors", [])), n_hit


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="圖名（不含副檔名）；預設全部")
    ap.add_argument("--lib", default="training/door_lib.npz")
    ap.add_argument("--png-dir", default="testdata/png")
    ap.add_argument("--json-dir", default="training/json/gray")
    a = ap.parse_args()

    lib = _load_lib(a.lib)
    if lib is None:
        raise SystemExit(f"找不到模板庫 {a.lib}——先跑 scripts/extract_door_lib.py")

    if a.names:
        jpaths = [os.path.join(a.json_dir, n + ".json") for n in a.names]
    else:
        jpaths = sorted(glob.glob(os.path.join(a.json_dir, "*.json")))

    tot_d = tot_h = tot_f = 0
    for jp in jpaths:
        r = rescore_file(jp, a.png_dir, lib)
        if r is None:
            print(f"跳過（找不到原圖）：{os.path.basename(jp)}")
            continue
        nd, nh = r
        tot_d += nd; tot_h += nh; tot_f += 1
        print(f"{os.path.basename(jp):24} 候選 {nd:3d}  模板命中 {nh:3d}")
    print(f"\n共 {tot_f} 張圖、{tot_d} 個候選、命中 {tot_h}"
          f"（chamfer ≤ {CH_STRONG} → score_fused ≥ {RESCUE}）")


if __name__ == "__main__":
    main()
