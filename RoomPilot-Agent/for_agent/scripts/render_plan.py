#!/usr/bin/env python3
"""render_plan.py — 從 architecture.json + furniture.json 渲一張俯視平面圖。

為什麼要這支：
  純 JSON 讓 agent「算得對」但「看不到」。這支把當前布置渲成一張俯視正投影
  （orthographic top-down），給多模態 agent（agent 3/4）一雙眼睛做視覺定位，
  也給人看。它不是真值來源——真值永遠是 furniture.json，這只是它的可視化。

輸出：
  - SVG：向量母檔，給人看 / 進版控 / 無限縮放不糊。
  - PNG：點陣，餵多模態 LLM（線稿 + 文字，PNG 無損不糊；不要用 JPEG）。

畫什麼（皆為俯視佔地投影，不是透視）：
  - 房間輪廓、牆（實心）、窗（牆上藍色段）、門（開口 + 虛線開合弧）。
  - 家具佔地框：實體家具半透明填色 + 實線；地毯等墊底扁平件畫在最底層、虛線淡色。
  - 每件家具中央標 object id（agent 4 的違規報告是用 id 指涉，圖上務必對得上）。
  - 朝向箭頭：從中心指向正面（本地 +Y 經 rotation 旋轉後的世界方向）。
  - 可選：套疊 validation_report.json 的違規（紅框 + ⚠ + 底部清單）。
  - 可選：走道自由空間（--show-walkway，把可通行區侵蝕後淡綠標示）。

用法：
  python render_plan.py --architecture a.json --furniture f.json --out plan
      → 產生 plan.svg 與 plan.png
  python render_plan.py ... --report validation_report.json      # 套疊違規
  python render_plan.py ... --formats png --dpi 128               # 只出 PNG
  python render_plan.py ... --show-walkway --walkway-clearance 60 # 標走道
  python render_plan.py ... --long-edge 900                       # 控制 PNG 長邊像素
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # 無顯示環境
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, FancyArrow, Arc
from matplotlib import font_manager

# 沿用管線共用幾何（同一套座標約定：cm、中心為原點、逆時針、0°朝 +Y）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geometry as geo  # noqa: E402

# ── 與 validate_layout 一致的扁平件判定（墊底/壁掛，不算實體佔地）──────────
FLAT_CATEGORIES = {"地毯", "rug", "掛畫", "壁飾"}


def _is_flat(item: Dict) -> bool:
    return (item.get("category") in FLAT_CATEGORIES
            or item.get("dimensions", {}).get("height", 99) <= 3)


# ── 配色（低彩度、線稿優先，讓 id 與箭頭讀得清楚）───────────────────────────
COL = {
    "room_fill": "#faf8f4",
    "wall": "#3f3a34",
    "window": "#4a90d9",
    "door_arc": "#c98a3a",
    "door_leaf": "#c98a3a",
    "solid_fill": "#cfe0d8",
    "solid_edge": "#4b6b5e",
    "flat_fill": "#efe7d6",
    "flat_edge": "#b9a77e",
    "arrow": "#2f5d50",
    "id_text": "#1e1a15",
    "walkway": "#7cc48b",
    "violation": "#d64545",
    "grid": "#e6e0d6",
}
# 依類別給實體家具一點色彩區分（找不到就用預設）
CATEGORY_TINT = {
    "坐墊": "#d9e6cf", "沙發": "#cfe0d8", "茶几": "#e6dcc9", "電視櫃": "#d8dbe6",
    "落地燈": "#efe3c8", "單椅": "#e0d6e6", "書櫃": "#d8dbe6", "床": "#e6d6d6",
}


def _register_cjk_font() -> Optional[str]:
    """註冊 Noto Sans CJK TC，避免中文字型變成豆腐框；回傳字型名或 None。"""
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
                name = font_manager.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = name
                plt.rcParams["axes.unicode_minus"] = False
                return name
            except Exception:
                continue
    return None


def _load(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _poly_xy(poly) -> List:
    """shapely polygon → matplotlib 需要的 (N,2) 座標列表（取外環）。"""
    return list(poly.exterior.coords)


def _draw_room(ax, arch: Dict) -> None:
    room = geo.room_polygon(arch)
    ax.add_patch(MplPolygon(_poly_xy(room), closed=True,
                            facecolor=COL["room_fill"], edgecolor="none", zorder=0))
    # 牆：實心佔地框
    for w in arch.get("walls", []):
        fp = geo.wall_footprint(w)
        ax.add_patch(MplPolygon(_poly_xy(fp), closed=True,
                                facecolor=COL["wall"], edgecolor="none", zorder=2))
    # 窗：沿牆一段藍色粗線
    for win in arch.get("windows", []):
        _draw_opening(ax, win, COL["window"], lw=4.0, zorder=3)
    # 門：開口 + 開合弧
    for door in arch.get("doors", []):
        _draw_opening(ax, door, COL["door_leaf"], lw=2.5, zorder=3)
        _draw_door_swing(ax, door)


def _opening_endpoints(op: Dict):
    """由中心、寬、rotation 求開口兩端點（沿牆向,牆向=本地 X 旋轉後）。"""
    p = op["position"]
    r = math.radians(op.get("rotation", 0.0))
    hw = op["width"] / 2.0
    dx, dy = math.cos(r), math.sin(r)  # 本地 +X 的世界方向
    return ((p["x"] - hw * dx, p["y"] - hw * dy),
            (p["x"] + hw * dx, p["y"] + hw * dy))


def _draw_opening(ax, op: Dict, color: str, lw: float, zorder: int) -> None:
    (x1, y1), (x2, y2) = _opening_endpoints(op)
    ax.plot([x1, x2], [y1, y2], color=color, lw=lw, solid_capstyle="butt",
            zorder=zorder)


def _draw_door_swing(ax, door: Dict) -> None:
    """門葉 + 四分之一圓開合弧（半徑=門寬），純視覺提示。"""
    p = door["position"]
    r = door["width"]
    rot = door.get("rotation", 0.0)
    nx, ny = geo.inward_normal(rot) if door.get("swing_in", True) else geo.inward_normal(rot + 180)
    base_ang = math.degrees(math.atan2(ny, nx))
    hinge_sign = -1.0 if door.get("hinge", "left") == "left" else 1.0
    # 鉸鏈點：開口靠 hinge 側端點
    (x1, y1), (x2, y2) = _opening_endpoints(door)
    if door.get("hinge", "left") == "left":
        hx, hy = x1, y1
    else:
        hx, hy = x2, y2
    # 門葉終止角
    a0 = base_ang
    a1 = base_ang + hinge_sign * 90.0
    theta1, theta2 = (a1, a0) if a1 < a0 else (a0, a1)
    ax.add_patch(Arc((hx, hy), 2 * r, 2 * r, angle=0, theta1=theta1, theta2=theta2,
                     color=COL["door_arc"], lw=1.0, ls="--", zorder=3))
    # 門葉本身（從鉸鏈指向開啟方向）
    leaf_ang = math.radians(a1)
    ax.plot([hx, hx + r * math.cos(leaf_ang)], [hy, hy + r * math.sin(leaf_ang)],
            color=COL["door_leaf"], lw=1.5, ls="-", zorder=3)


def _draw_furniture(ax, furn: List[Dict], violating: set) -> None:
    # 先畫扁平件（地毯）墊底，再畫實體，確保實體壓在地毯上
    order = sorted(furn, key=lambda f: 0 if _is_flat(f) else 1)
    for item in order:
        fp = geo.furniture_footprint(item)
        flat = _is_flat(item)
        vid = item.get("id")
        is_bad = vid in violating
        if flat:
            face, edge, ls, z, alpha = COL["flat_fill"], COL["flat_edge"], "--", 1, 0.6
        else:
            face = CATEGORY_TINT.get(item.get("category"), COL["solid_fill"])
            edge, ls, z, alpha = COL["solid_edge"], "-", 4, 0.85
        if is_bad:
            edge = COL["violation"]
        ax.add_patch(MplPolygon(_poly_xy(fp), closed=True, facecolor=face,
                                edgecolor=edge, lw=2.2 if is_bad else 1.3,
                                ls=ls, alpha=alpha, zorder=z))
        p = item["position"]
        cx, cy = p["x"], p["y"]
        # 朝向箭頭（實體件才畫；扁平件無意義）
        if not flat:
            nx, ny = geo.inward_normal(item.get("rotation", 0.0))
            L = 0.30 * min(item["dimensions"]["width"], item["dimensions"]["depth"]) + 12
            ax.add_patch(FancyArrow(cx, cy, nx * L, ny * L, width=1.5,
                                    head_width=9, head_length=9,
                                    length_includes_head=True,
                                    color=COL["arrow"], zorder=6))
        # id 標籤
        label = vid if vid else "?"
        ax.text(cx, cy, label, ha="center", va="center", zorder=7,
                fontsize=9, fontweight="bold", color=COL["id_text"],
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
        if is_bad:
            ax.text(cx, cy + 14, "×", ha="center", va="center", zorder=8,
                    fontsize=13, fontweight="bold", color=COL["violation"])


def _draw_walkway(ax, arch: Dict, furn: List[Dict], clearance: float) -> None:
    """自由空間侵蝕法可視化：房間 − 實體家具，向內縮 clearance/2，剩下即可通行區。"""
    try:
        from shapely.ops import unary_union
    except ImportError:
        return
    room = geo.room_polygon(arch)
    solids = [geo.furniture_footprint(f) for f in furn if not _is_flat(f)]
    free = room.difference(unary_union(solids)) if solids else room
    walk = free.buffer(-clearance / 2.0).buffer(clearance / 2.0)
    if walk.is_empty:
        return
    geoms = getattr(walk, "geoms", [walk])
    for g in geoms:
        if g.is_empty or g.geom_type != "Polygon":
            continue
        ax.add_patch(MplPolygon(_poly_xy(g), closed=True, facecolor=COL["walkway"],
                                edgecolor="none", alpha=0.18, zorder=1))


def render(arch: Dict, furn_doc: Dict, out_base: str, formats: List[str],
           dpi: int, long_edge: int, report: Optional[Dict],
           show_walkway: bool, walkway_clearance: float) -> List[str]:
    furn = furn_doc.get("furniture", [])
    violating = set()
    if report:
        for v in report.get("violations", []):
            if v.get("object_id"):
                violating.add(v["object_id"])

    room = geo.room_polygon(arch)
    minx, miny, maxx, maxy = room.bounds
    pad = 0.06 * max(maxx - minx, maxy - miny) + 10
    w_cm, h_cm = (maxx - minx) + 2 * pad, (maxy - miny) + 2 * pad

    # 讓 PNG 長邊約等於 long_edge：figsize(inch) × dpi = px
    long_cm = max(w_cm, h_cm)
    fig_long_in = long_edge / dpi
    scale = fig_long_in / long_cm
    fig = plt.figure(figsize=(w_cm * scale, h_cm * scale))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(minx - pad, maxx + pad)
    ax.set_ylim(miny - pad, maxy + pad)
    ax.set_aspect("equal")

    # 淡格線（每 50cm）給人一點比例感
    for gx in range(int(math.floor(minx / 50) * 50), int(maxx) + 1, 50):
        ax.axvline(gx, color=COL["grid"], lw=0.6, zorder=0)
    for gy in range(int(math.floor(miny / 50) * 50), int(maxy) + 1, 50):
        ax.axhline(gy, color=COL["grid"], lw=0.6, zorder=0)

    if show_walkway:
        _draw_walkway(ax, arch, furn, walkway_clearance)
    _draw_room(ax, arch)
    _draw_furniture(ax, furn, violating)

    # 標題列 + 違規清單
    room_type = furn_doc.get("room_type", "")
    status = ""
    if report is not None:
        status = "  [PASS]" if report.get("passed") else f"  [FAIL] {len(report.get('violations', []))} 項違規"
    ax.text(minx - pad + 6, maxy + pad - 6, f"{room_type} 俯視平面圖{status}",
            ha="left", va="top", fontsize=11, fontweight="bold",
            color=COL["id_text"], zorder=9)
    if report and not report.get("passed"):
        lines = []
        for v in report.get("violations", [])[:8]:
            mark = "■" if v.get("severity", "error") == "error" else "□"
            lines.append(f'{mark} {v.get("object_id","-")}: {v.get("message","")}')
        ax.text(minx - pad + 6, miny - pad + 6, "\n".join(lines), ha="left", va="bottom",
                fontsize=7.5, color=COL["violation"], zorder=9,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=COL["violation"], alpha=0.85))

    ax.axis("off")
    written = []
    for fmt in formats:
        path = f"{out_base}.{fmt}"
        if fmt == "png":
            fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.05,
                        facecolor="white")
        else:
            fig.savefig(path, bbox_inches="tight", pad_inches=0.05, facecolor="white")
        written.append(path)
    plt.close(fig)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染俯視平面圖（SVG 母檔 + PNG 給 agent）")
    ap.add_argument("--architecture", required=True)
    ap.add_argument("--furniture", required=True)
    ap.add_argument("--out", required=True, help="輸出檔名（不含副檔名）")
    ap.add_argument("--formats", default="svg,png", help="逗號分隔：svg,png")
    ap.add_argument("--dpi", type=int, default=128, help="PNG 解析度")
    ap.add_argument("--long-edge", type=int, default=900,
                    help="PNG 長邊目標像素（768–1024 通常最省 token 又清楚）")
    ap.add_argument("--report", default=None, help="validation_report.json，套疊違規")
    ap.add_argument("--show-walkway", action="store_true", help="標示可通行自由空間")
    ap.add_argument("--walkway-clearance", type=float, default=60.0,
                    help="走道淨寬（cm），侵蝕半徑取其一半")
    args = ap.parse_args()

    font = _register_cjk_font()
    if not font:
        print("[render_plan] 警告：找不到 CJK 字型，中文標籤可能顯示為方框", file=sys.stderr)

    arch = _load(args.architecture)
    furn_doc = _load(args.furniture)
    report = _load(args.report) if args.report else None
    formats = [f.strip().lower() for f in args.formats.split(",") if f.strip()]

    written = render(arch, furn_doc, args.out, formats, args.dpi, args.long_edge,
                     report, args.show_walkway, args.walkway_clearance)
    print(f"[render_plan] 已輸出：{', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
