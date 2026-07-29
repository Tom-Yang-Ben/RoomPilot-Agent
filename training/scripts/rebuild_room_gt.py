"""rebuild_room_gt.py — 用 GT 牆重建 Space 房間輪廓（量尺幾何修正）。

own_eval 人工審定的 Space 多邊形多為三角楔形（Inkscape 粗畫），只蓋住
房間一部分——正確的切割預測對楔形算 IoU 也過不了 0.5，量尺失真。
本腳本以同一份 model.svg 內審定過的 Wall/Window/Door 多邊形為屏障做
flood fill，自動長出乾淨房間輪廓；既有楔形只當「標籤指針」：
- 一個連通區域只被一個楔形命中 → 整區承接該標籤
- 一區被多個楔形命中（開放式空間）→ 區內以「距最近楔形」分水嶺切分
幾何全自動、語意沿用人工審定；Space 群組的 class 與數量不變，只換
polygon 座標。

用法：python scripts/rebuild_room_gt.py [--dir testdata/Identify_ans/own_eval]
      [--check]（只回報不寫檔）
"""
import argparse
import os
import sys
from xml.dom import minidom

import cv2
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "training/CubiCasa5k"))

BARRIER_CLASSES = {"Wall", "Window", "Door", "Railing"}
MIN_REGION_PX = 300


def poly_points(g):
    """群組第一個 polygon 的 points → Nx2 int array（x, y）；無則 None。"""
    polys = g.getElementsByTagName("polygon")
    if not polys:
        return None
    import re
    nums = [float(v) for v in
            re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?",
                       polys[0].getAttribute("points"))]
    if len(nums) < 6:
        return None
    return np.array(list(zip(nums[::2], nums[1::2])), np.float64)


def rasterize(pts, h, w):
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 1)
    return m


def split_by_seeds(region, seeds):
    """單一連通區域被多個楔形命中：區內像素依「距最近楔形」歸屬。
    seeds = [(space_idx, seed_mask ∩ region)]，回傳 {space_idx: mask}。"""
    dists = []
    for _, sm in seeds:
        d = cv2.distanceTransform((sm == 0).astype(np.uint8),
                                  cv2.DIST_L2, 3)
        dists.append(d)
    owner = np.argmin(np.stack(dists), axis=0)
    out = {}
    for k, (idx, _) in enumerate(seeds):
        out[idx] = ((owner == k) & (region > 0)).astype(np.uint8)
    return out


def mask_to_polygon(mask, eps=2.0):
    """房間 mask → 最大外輪廓 → 簡化多邊形（x, y 點列）；退化回 None。"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < MIN_REGION_PX:
        return None
    approx = cv2.approxPolyDP(c, eps, True).reshape(-1, 2)
    return approx if len(approx) >= 3 else None


def rebuild_floor(svg_path, img_path, check_only):
    """單層：回傳 (重建數, 保留數, 警告列表)。"""
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    doc = minidom.parse(svg_path)

    barrier = np.zeros((h, w), np.uint8)
    spaces = []                                  # [(g, wedge_pts)]
    for g in doc.getElementsByTagName("g"):
        cls = g.getAttribute("class").split(" ")
        if not cls or not cls[0]:
            continue
        if cls[0] in BARRIER_CLASSES:
            pts = poly_points(g)
            if pts is not None:
                barrier |= rasterize(pts, h, w)
        elif cls[0] == "Space":
            spaces.append((g, poly_points(g)))

    barrier = cv2.dilate(barrier, np.ones((3, 3), np.uint8))
    barrier[0, :] = barrier[-1, :] = 1           # 影像邊框視為屏障——
    barrier[:, 0] = barrier[:, -1] = 1           # 掃描裁邊處牆常未封閉
    n_lab, lab = cv2.connectedComponents((barrier == 0).astype(np.uint8), 4)
    border = {0} | {int(lab[r, c]) for r, c in    # 室外=含四角的區
               ((1, 1), (1, w - 2), (h - 2, 1), (h - 2, w - 2))}

    claims = {}                                  # region_id -> [(sidx, seed)]
    for sidx, (_g, wedge) in enumerate(spaces):
        if wedge is None:
            continue
        wm = rasterize(wedge, h, w)
        best, best_ov = 0, 0
        for rid in np.unique(lab[wm > 0]):
            if rid in border or rid == 0:
                continue
            ov = int(((lab == rid) & (wm > 0)).sum())
            if ov > best_ov:
                best, best_ov = rid, ov
        if best:
            claims.setdefault(best, []).append((sidx, wm))

    new_masks, warns = {}, []
    for rid, seeds in claims.items():
        region = (lab == rid).astype(np.uint8)
        if int(region.sum()) < MIN_REGION_PX:
            continue
        if len(seeds) == 1:
            new_masks[seeds[0][0]] = region
        else:
            for sidx, m in split_by_seeds(region, [
                    (i, s & region) for i, s in seeds]).items():
                new_masks[sidx] = m

    rebuilt = kept = 0
    for sidx, (g, wedge) in enumerate(spaces):
        poly = (mask_to_polygon(new_masks[sidx])
                if sidx in new_masks else None)
        if poly is None:
            kept += 1
            if wedge is not None:
                warns.append(f"Space#{sidx}({g.getAttribute('class')}) "
                             "無法重建，保留原多邊形")
            continue
        rebuilt += 1
        if not check_only:
            g.getElementsByTagName("polygon")[0].setAttribute(
                "points", " ".join(f"{x},{y}" for x, y in poly) + " ")  # 尾空格：House get_polygon 會砍最後一項
    if rebuilt and not check_only:
        with open(svg_path, "w", encoding="utf-8") as f:
            doc.writexml(f)
    return rebuilt, kept, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="testdata/Identify_ans/own_eval")
    ap.add_argument("--check", action="store_true", help="只回報不寫檔")
    a = ap.parse_args()

    import glob
    tot_r = tot_k = 0
    for svg in sorted(glob.glob(os.path.join(a.dir, "floor*", "model.svg"))):
        img = os.path.join(os.path.dirname(svg), "F1_scaled.png")
        r, k, warns = rebuild_floor(svg, img, a.check)
        tot_r += r
        tot_k += k
        tag = "可重建" if a.check else "已重建"
        print(f"{svg}: {tag} {r}、保留 {k}"
              + ("".join("\n  ⚠️ " + m for m in warns)))
    print(f"\n合計{'可' if a.check else '已'}重建 {tot_r}、保留原樣 {tot_k}")


if __name__ == "__main__":
    main()
