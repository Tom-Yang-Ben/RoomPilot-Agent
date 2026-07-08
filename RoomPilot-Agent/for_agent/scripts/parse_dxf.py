#!/usr/bin/env python3
"""parse_dxf.py — 讀 2D 平面圖 (DXF)，輸出 architecture.json。

抽取牆 / 窗 / 門，各自的 id、position（中心）、rotation（逆時針度）、width，
並推導房間可用區域多邊形 room_polygon。

DXF 沒有統一的「這是牆」語意，實務上靠**圖層 (layer) 命名**約定。預設圖層名可用
--wall-layer / --window-layer / --door-layer 覆寫。牆以 LINE / LWPOLYLINE 線段表示；
窗、門以 INSERT（圖塊參照）或短線段表示，取其位置與旋轉。

用法：
  python parse_dxf.py --dxf plan.dxf --out architecture.json \
      --unit-scale 0.1   # 若 DXF 單位是 mm，用 0.1 轉成 cm

這是參考實作：DXF 慣例因繪圖者而異，請依你的圖層命名與圖塊定義調整下方對應規則。
"""
from __future__ import annotations
import argparse, json, math, sys
from typing import Dict, List

try:
    import ezdxf
except ImportError:
    ezdxf = None


def _len_and_angle(p1, p2):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))  # 逆時針度
    center = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    return length, angle, center


def _iter_line_segments(msp, layer: str, scale: float):
    """回傳指定圖層上所有線段的 (p1, p2)。支援 LINE 與 LWPOLYLINE。"""
    segs = []
    for e in msp.query(f'LINE[layer=="{layer}"]'):
        segs.append(((e.dxf.start.x * scale, e.dxf.start.y * scale),
                     (e.dxf.end.x * scale, e.dxf.end.y * scale)))
    for e in msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
        pts = [(p[0] * scale, p[1] * scale) for p in e.get_points("xy")]
        closed = e.closed
        n = len(pts)
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            segs.append((pts[i], pts[(i + 1) % n]))
    return segs


def _openings_from_inserts(msp, layer: str, scale: float, prefix: str):
    """從 INSERT（圖塊）抽窗/門：用插入點為 position、圖塊旋轉為 rotation。"""
    items = []
    for i, e in enumerate(msp.query(f'INSERT[layer=="{layer}"]')):
        pos = (e.dxf.insert.x * scale, e.dxf.insert.y * scale)
        rot = float(getattr(e.dxf, "rotation", 0.0))
        # 圖塊寬度不一定可靠，取 x 縮放 * 常見門寬當估計，實務請讀圖塊屬性
        width = abs(float(getattr(e.dxf, "xscale", 1.0))) * 90.0 * scale
        items.append({"id": f"{prefix}_{i+1}",
                      "position": {"x": round(pos[0], 2), "y": round(pos[1], 2)},
                      "rotation": round(rot, 2), "width": round(width, 2)})
    return items


def _openings_from_segments(msp, layer: str, scale: float, prefix: str):
    """後備：若窗/門用短線段畫，取線段中點與角度。"""
    items = []
    for i, (p1, p2) in enumerate(_iter_line_segments(msp, layer, scale)):
        length, angle, center = _len_and_angle(p1, p2)
        items.append({"id": f"{prefix}_{i+1}",
                      "position": {"x": round(center[0], 2), "y": round(center[1], 2)},
                      "rotation": round(angle, 2), "width": round(length, 2)})
    return items


def _room_polygon_from_walls(wall_segs: List) -> List[List[float]]:
    """由牆線段端點取凸包當房間外框（簡化）。複雜格局請改用房間封閉多段線圖層。"""
    pts = []
    for p1, p2 in wall_segs:
        pts.append(p1); pts.append(p2)
    if len(pts) < 3:
        return []
    # Andrew monotone chain 凸包，避免額外依賴
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in pts))
    if len(pts) < 3:
        return [list(p) for p in pts]

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [[round(x, 2), round(y, 2)] for x, y in hull]


def parse(dxf_path, wall_layer, window_layer, door_layer, scale, default_thickness, default_height):
    if ezdxf is None:
        raise RuntimeError("需要 ezdxf：pip install ezdxf")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    wall_segs = _iter_line_segments(msp, wall_layer, scale)
    walls = []
    for i, (p1, p2) in enumerate(wall_segs):
        length, angle, center = _len_and_angle(p1, p2)
        if length < 1e-3:
            continue
        walls.append({
            "id": f"wall_{i+1}",
            "position": {"x": round(center[0], 2), "y": round(center[1], 2)},
            "rotation": round(angle, 2),
            "width": round(length, 2),
            "thickness": default_thickness,
            "height": default_height,
        })

    windows = _openings_from_inserts(msp, window_layer, scale, "win") \
        or _openings_from_segments(msp, window_layer, scale, "win")
    doors = _openings_from_inserts(msp, door_layer, scale, "door") \
        or _openings_from_segments(msp, door_layer, scale, "door")

    architecture = {
        "units": "cm",
        "room_polygon": _room_polygon_from_walls(wall_segs),
        "walls": walls,
        "windows": windows,
        "doors": doors,
    }
    return architecture


def main(argv=None):
    ap = argparse.ArgumentParser(description="DXF 平面圖 → architecture.json")
    ap.add_argument("--dxf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wall-layer", default="WALL")
    ap.add_argument("--window-layer", default="WINDOW")
    ap.add_argument("--door-layer", default="DOOR")
    ap.add_argument("--unit-scale", type=float, default=1.0,
                    help="DXF 單位轉 cm 的倍率（mm→cm 用 0.1）")
    ap.add_argument("--wall-thickness", type=float, default=15.0)
    ap.add_argument("--wall-height", type=float, default=280.0)
    args = ap.parse_args(argv)

    arch = parse(args.dxf, args.wall_layer, args.window_layer, args.door_layer,
                 args.unit_scale, args.wall_thickness, args.wall_height)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(arch, f, ensure_ascii=False, indent=2)
    print(f"[parse_dxf] walls={len(arch['walls'])} windows={len(arch['windows'])} "
          f"doors={len(arch['doors'])} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
