#!/usr/bin/env python3
"""將家具素材 DXF 切成獨立小 PNG（辨識素材用）。

DXF 內的家具通常是散開的原始幾何（LINE/ARC/CIRCLE/ELLIPSE），沒有 block insert，
無法按 block 拆分。此工具改用空間聚類：

1. 將所有實體攤平成線段
2. 低解析度點陣化 + 形態學膨脹，連通元件 = 一件家具
3. 依連通元件範圍把實體分群，逐群以向量重新渲染成固定尺寸 PNG

用法：
    python scripts/dxf2png_pieces.py Asset/furniture/dinner_table.dxf \
        -o Asset/furniture/dinner_table_png --size 512 --gap 120
"""

import argparse
import math
import sys
from pathlib import Path

import cv2
import ezdxf
import ezdxf.path
import numpy as np
from PIL import Image, ImageDraw

FLATTEN_DIST = 0.5  # 攤平曲線的最大弦高（圖面單位，mm 級圖面下 0.5 已足夠平滑；公尺級圖面請用 --flatten 調小）
SKIP_TYPES = {"DIMENSION", "TEXT", "MTEXT", "ATTRIB", "ATTDEF", "LEADER", "MULTILEADER"}


def entity_segments(entity):
    """將單一 DXF 實體攤平成 [(x1,y1,x2,y2), ...] 線段列表。"""
    kind = entity.dxftype()
    try:
        if kind == "LINE":
            s, e = entity.dxf.start, entity.dxf.end
            return [(s.x, s.y, e.x, e.y)]
        if kind in ("ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
            pts = [(v.x, v.y) for v in entity.flattening(FLATTEN_DIST)]
            return [(*pts[i], *pts[i + 1]) for i in range(len(pts) - 1)]
        if kind in ("LWPOLYLINE", "POLYLINE", "HATCH", "SOLID", "TRACE"):
            # 這些型別沒有 flattening()，統一轉成 path 再攤平
            paths = ezdxf.path.from_hatch(entity) if kind == "HATCH" \
                else [ezdxf.path.make_path(entity)]
            segs = []
            for p in paths:
                pts = [(v.x, v.y) for v in p.flattening(FLATTEN_DIST)]
                segs.extend((*pts[i], *pts[i + 1]) for i in range(len(pts) - 1))
            return segs
    except Exception as exc:  # 單一壞實體不應中斷整批轉換
        print(f"  跳過無法攤平的 {kind}: {exc}", file=sys.stderr)
    return []


def collect_segments(msp):
    """回傳每個實體的線段組（略過空實體與標註類）。"""
    groups = []
    for e in msp:
        if e.dxftype() in SKIP_TYPES:
            continue
        segs = entity_segments(e)
        if segs:
            groups.append(np.array(segs, dtype=np.float64))
    return groups


def insert_segments(insert, depth=0):
    """遞迴展開 INSERT，回傳其全部線段（已套用座標變換）。"""
    segs = []
    if depth > 4:  # 防止異常巢狀
        return segs
    for e in insert.virtual_entities():
        kind = e.dxftype()
        if kind in SKIP_TYPES:
            continue
        if kind == "INSERT":
            segs.extend(insert_segments(e, depth + 1))
        else:
            segs.extend(entity_segments(e))
    return segs


def collect_inserts(msp, dedupe=True):
    """以 INSERT 為單位分群。回傳 [(block名, 線段陣列), ...]，可按 block 名去重。"""
    pieces = []
    seen = set()
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        name = e.dxf.name
        if dedupe and name in seen:
            continue
        segs = insert_segments(e)
        if segs:
            seen.add(name)
            pieces.append((name, np.array(segs, dtype=np.float64)))
    return pieces


def cluster_by_raster(groups, gap):
    """點陣化 + 膨脹 + 連通元件，回傳每群的實體索引列表。"""
    all_segs = np.concatenate(groups)
    xmin = min(all_segs[:, 0].min(), all_segs[:, 2].min())
    xmax = max(all_segs[:, 0].max(), all_segs[:, 2].max())
    ymin = min(all_segs[:, 1].min(), all_segs[:, 3].min())
    ymax = max(all_segs[:, 1].max(), all_segs[:, 3].max())

    # 解析度取 gap/4，確保膨脹核至少數個像素寬
    res = max(gap / 4.0, (max(xmax - xmin, ymax - ymin)) / 8000.0)
    w = int((xmax - xmin) / res) + 3
    h = int((ymax - ymin) / res) + 3
    canvas = np.zeros((h, w), np.uint8)

    def to_px(x, y):
        return int((x - xmin) / res) + 1, int((y - ymin) / res) + 1

    for segs in groups:
        for x1, y1, x2, y2 in segs:
            cv2.line(canvas, to_px(x1, y1), to_px(x2, y2), 255, 1)

    k = max(3, int(gap / res) | 1)
    dilated = cv2.dilate(canvas, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    n_labels, labels = cv2.connectedComponents(dilated)

    clusters = {}
    for idx, segs in enumerate(groups):
        cx, cy = to_px(segs[:, [0, 2]].mean(), segs[:, [1, 3]].mean())
        cx = min(max(cx, 0), w - 1)
        cy = min(max(cy, 0), h - 1)
        label = labels[cy, cx]
        if label == 0:  # 中心落在空白處（如環形排列），改用任一線段端點
            px, py = to_px(segs[0, 0], segs[0, 1])
            label = labels[min(py, h - 1), min(px, w - 1)]
        clusters.setdefault(label, []).append(idx)
    clusters.pop(0, None)
    return list(clusters.values())


def render_cluster(groups, indices, size, line_px, pad_ratio):
    """將一群實體以向量渲染成 size×size 白底黑線 PNG。"""
    segs = np.concatenate([groups[i] for i in indices])
    xmin = min(segs[:, 0].min(), segs[:, 2].min())
    xmax = max(segs[:, 0].max(), segs[:, 2].max())
    ymin = min(segs[:, 1].min(), segs[:, 3].min())
    ymax = max(segs[:, 1].max(), segs[:, 3].max())
    span = max(xmax - xmin, ymax - ymin)
    if span <= 0:
        return None, (0, 0)

    pad = span * pad_ratio
    scale = size / (span + 2 * pad)
    # 以群中心為基準置中，保持原始長寬比
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2

    ss = 4  # 超取樣抗鋸齒
    img = Image.new("L", (size * ss, size * ss), 255)
    draw = ImageDraw.Draw(img)
    half = size * ss / 2

    def to_px(x, y):
        return (x - cx) * scale * ss + half, half - (y - cy) * scale * ss  # y 軸翻轉

    for x1, y1, x2, y2 in segs:
        draw.line([to_px(x1, y1), to_px(x2, y2)], fill=0, width=line_px * ss)
    img = img.resize((size, size), Image.LANCZOS)
    return img, (xmax - xmin, ymax - ymin)


def make_contact_sheet(images, out_path, thumb=128):
    """輸出總覽圖，方便人工檢查切割結果。"""
    cols = math.ceil(math.sqrt(len(images)))
    rows = math.ceil(len(images) / cols)
    sheet = Image.new("L", (cols * thumb, rows * thumb), 220)
    for i, img in enumerate(images):
        t = img.resize((thumb - 4, thumb - 4), Image.LANCZOS)
        sheet.paste(t, ((i % cols) * thumb + 2, (i // cols) * thumb + 2))
    sheet.save(out_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dxf", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True, help="輸出目錄")
    ap.add_argument("--size", type=int, default=512, help="輸出 PNG 邊長（預設 512）")
    ap.add_argument("--gap", type=float, default=120.0,
                    help="聚類間距門檻，圖面單位（預設 120，即間距小於此值視為同一件）")
    ap.add_argument("--line-px", type=int, default=2, help="線寬 px（預設 2）")
    ap.add_argument("--pad", type=float, default=0.06, help="邊界留白比例（預設 0.06）")
    ap.add_argument("--min-span", type=float, default=100.0,
                    help="小於此尺寸（圖面單位）的群視為雜訊捨棄（預設 100）")
    ap.add_argument("--mode", choices=["auto", "cluster", "insert"], default="auto",
                    help="切割模式：insert=按 block 拆（自動去重）；cluster=空間聚類；"
                         "auto=modelspace 有 INSERT 就用 insert（預設）")
    ap.add_argument("--no-dedupe", action="store_true",
                    help="insert 模式下不按 block 名去重")
    ap.add_argument("--flatten", type=float, default=None,
                    help="攤平曲線最大弦高，圖面單位（預設 0.5，公尺級圖面建議 0.005）")
    args = ap.parse_args()
    if args.flatten:
        global FLATTEN_DIST
        FLATTEN_DIST = args.flatten

    doc = ezdxf.readfile(args.dxf)
    msp = doc.modelspace()
    mode = args.mode
    if mode == "auto":
        mode = "insert" if any(e.dxftype() == "INSERT" for e in msp) else "cluster"
    print(f"切割模式: {mode}")

    if mode == "insert":
        pieces = collect_inserts(msp, dedupe=not args.no_dedupe)
        print(f"獨立 block 數: {len(pieces)}")
        clusters = [[i] for i in range(len(pieces))]
        groups = [segs for _, segs in pieces]
    else:
        groups = collect_segments(msp)
        print(f"實體數（可攤平）: {len(groups)}")
        clusters = cluster_by_raster(groups, args.gap)
        print(f"聚類結果: {len(clusters)} 群")

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.dxf.stem.replace(" ", "_")
    kept, images = [], []
    for indices in clusters:
        img, (w, h) = render_cluster(groups, indices, args.size, args.line_px, args.pad)
        if img is None or max(w, h) < args.min_span:
            continue
        kept.append((img, w, h, len(indices)))

    # 依尺寸排序讓命名穩定（大桌在前）
    kept.sort(key=lambda t: -(t[1] * t[2]))
    for i, (img, w, h, n) in enumerate(kept, 1):
        name = f"{stem}_{i:02d}.png"
        img.save(args.out / name)
        images.append(img)
        print(f"  {name}: {w:.0f} x {h:.0f} 單位, {n} 實體")

    if images:
        make_contact_sheet(images, args.out / f"{stem}_overview.png")
        print(f"共輸出 {len(images)} 張 → {args.out}（含 {stem}_overview.png 總覽）")


if __name__ == "__main__":
    main()
