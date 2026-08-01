#!/usr/bin/env python
"""跑真實辨識管線 → 餵擺放策略層 → 印出每間房的擺放結果。

**刻意不凍結辨識結果**：每次執行都重新跑一次辨識＋定標，所以 Cody 那邊改進
辨識之後，這支工具會直接反映新數字，不會停在舊快照上。

用法：

    .venv/bin/python scripts/floor04_layout_preview.py
    .venv/bin/python scripts/floor04_layout_preview.py --image testdata/png/floor05.png

家具尺寸目前使用**代表尺寸**（見 ``REPRESENTATIVE_ITEMS``），不接 RAG、不挑風格。
這一步只驗證「擺得對不對」，不驗證「選得好不好」。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.engine.clearance_defaults import catalog_with_default_clearance
from backend.engine.layout_room import rooms_from_layout_json
from backend.agent.knowledge import family_of, normalize_room_type
from backend.engine.layout_strategy import ROOM_RULES, place_room, rule_for
from backend.engine.models import FurnitureCatalogItem, PlacedFurniture, Room


# 代表尺寸（公分）：寬 × 深 × 高。接 RAG／catalog 之後這張表會被真實單品取代。
REPRESENTATIVE_ITEMS: dict[str, tuple[float, float, float]] = {
    "bed": (150, 200, 45),
    "dining-table": (140, 80, 75),
    "dining-chair": (48, 52, 82),
    "desk": (120, 60, 75),
    "office-chair": (60, 60, 90),
    "bookcase": (80, 30, 202),
    "shoe-cabinet": (80, 35, 120),
    "wardrobe": (100, 60, 200),
    "bedside-table": (40, 40, 55),
    "sofa": (220, 90, 85),
    "tv-bench": (180, 40, 50),
    "coffee-table": (110, 60, 42),
    "shelving-unit": (80, 30, 180),
    "cabinet-cupboard": (100, 50, 200),
}

# 依 room_strategy/README.md v1 的最少自動配置。空清單 = 規格明訂留空。
ROOM_PLAN: dict[str, list[str]] = {
    "bedroom": ["bed", "wardrobe", "bedside-table", "bedside-table"],
    "dining_room": ["dining-table", "dining-chair", "dining-chair", "dining-chair", "dining-chair"],
    "workspace": ["desk", "office-chair", "bookcase"],
    "entry": ["shoe-cabinet"],
    "living_room": ["sofa", "tv-bench", "coffee-table"],
    "storage": ["shelving-unit", "shelving-unit", "cabinet-cupboard"],
    "kitchen": [],
    "bathroom": [],
    "balcony": [],
    "circulation": [],
    "hallway": [],
}


def analyze(image_path: Path) -> dict:
    """跑正式的辨識端點（含定標），回傳 layout_json。"""
    from fastapi.testclient import TestClient

    from backend.server.main import app

    with TestClient(app) as client:
        with image_path.open("rb") as handle:
            response = client.post(
                "/api/floorplan/analyze",
                files={"file": (image_path.name, handle, "image/png")},
            )
    response.raise_for_status()
    return response.json()["layout_json"]


def build_items(room_type: str) -> list[tuple[FurnitureCatalogItem, str]]:
    counters: dict[str, int] = {}
    items: list[tuple[FurnitureCatalogItem, str]] = []
    for furniture_type in ROOM_PLAN.get(room_type, []):
        size = REPRESENTATIVE_ITEMS.get(furniture_type)
        if size is None:
            continue
        counters[furniture_type] = counters.get(furniture_type, 0) + 1
        width, depth, height = size
        catalog = catalog_with_default_clearance(
            FurnitureCatalogItem(
                type=furniture_type,
                name=furniture_type,
                width=width,
                depth=depth,
                height=height,
            )
        )
        items.append((catalog, f"{furniture_type}_{counters[furniture_type]}"))
    return items


def footprint(placed: PlacedFurniture) -> tuple[float, float]:
    if int(placed.rotation) % 360 in (90, 270):
        return placed.catalog.depth, placed.catalog.width
    return placed.catalog.width, placed.catalog.depth


def describe(placed: PlacedFurniture, room: Room, room_type: str) -> tuple[str, bool]:
    """回傳 (顯示文字, 是否為不該有的浮空)。刻意不貼牆的家具不算浮空。"""
    width, depth = footprint(placed)
    left, bottom = placed.pos_x - width / 2, placed.pos_y - depth / 2
    right, top = placed.pos_x + width / 2, placed.pos_y + depth / 2
    touching = []
    if left <= 1.0:
        touching.append("西")
    if right >= room.width - 1.0:
        touching.append("東")
    if bottom <= 1.0:
        touching.append("南")
    if top >= room.depth - 1.0:
        touching.append("北")
    may_float = rule_for(
        normalize_room_type(room_type), family_of(placed.catalog.type)
    ).attach in {"front", "free", "center", "around"}
    if touching:
        where = f"貼{''.join(touching)}牆"
        stray = False
    elif may_float:
        where = "室內（刻意不貼牆）"
        stray = False
    else:
        where = "★ 浮在室內"
        stray = True
    facing = {0: "朝北", 90: "朝西", 180: "朝南", 270: "朝東"}[int(placed.rotation) % 360]
    line = (
        f"  {placed.id:22} x[{left:6.0f}~{right:6.0f}] y[{bottom:6.0f}~{top:6.0f}]"
        f"  rot={int(placed.rotation):3d} {facing}  {where}"
    )
    return line, stray


LEGEND: dict[str, str] = {
    "bed": "B", "wardrobe": "W", "bedside-table": "n", "sofa": "S",
    "tv-bench": "T", "coffee-table": "c", "shelving-unit": "s",
    "cabinet-cupboard": "C", "dining-table": "D", "dining-chair": "d",
    "desk": "K", "office-chair": "k", "bookcase": "b", "shoe-cabinet": "G",
}


def draw(room: Room, placed: list[PlacedFurniture], cols: int = 54, rows: int = 20) -> list[str]:
    """把一間房畫成字元平面圖，北在上。"""
    sx, sy = room.width / cols, room.depth / rows
    grid = [[" "] * cols for _ in range(rows)]
    for item in placed:
        fw, fd = footprint(item)
        mark = LEGEND.get(item.catalog.type, "?")
        for r in range(rows):
            for c in range(cols):
                x, y = (c + 0.5) * sx, (r + 0.5) * sy
                if abs(x - item.pos_x) <= fw / 2 and abs(y - item.pos_y) <= fd / 2:
                    grid[r][c] = mark

    def marks_on(side: str) -> set[int]:
        """該面牆上被門窗佔用的格子索引。"""
        taken: set[int] = set()
        for opening in room.openings:
            low_x, high_x = opening.span_along("x")
            low_y, high_y = opening.span_along("y")
            if side in ("south", "north"):
                on_wall = abs(low_y - (0 if side == "south" else room.depth)) <= 8 and \
                          abs(high_y - (0 if side == "south" else room.depth)) <= 8
                span, step, count = (low_x, high_x), sx, cols
            else:
                on_wall = abs(low_x - (0 if side == "west" else room.width)) <= 8 and \
                          abs(high_x - (0 if side == "west" else room.width)) <= 8
                span, step, count = (low_y, high_y), sy, rows
            if not on_wall:
                continue
            for i in range(count):
                if span[0] <= (i + 0.5) * step <= span[1]:
                    taken.add(i if opening.kind == "window" else -i - 1)
        return taken

    def wall_line(side: str, count: int, char_open: str) -> str:
        taken = marks_on(side)
        out = ""
        for i in range(count):
            if -i - 1 in taken:
                out += "▓"
            elif i in taken:
                out += "▒"
            else:
                out += char_open
        return out

    west, east = marks_on("west"), marks_on("east")
    lines = ["┌" + wall_line("north", cols, "─") + "┐"]
    for r in range(rows - 1, -1, -1):
        left = "▓" if -r - 1 in west else ("▒" if r in west else "│")
        right = "▓" if -r - 1 in east else ("▒" if r in east else "│")
        lines.append(left + "".join(grid[r]) + right)
    lines.append("└" + wall_line("south", cols, "─") + "┘")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="testdata/png/floor04.png")
    parser.add_argument("--no-draw", action="store_true", help="只印座標，不畫平面圖")
    parser.add_argument(
        "--retype", action="append", default=[], metavar="ROOM_ID=TYPE",
        help="把辨識出的房間改定義成別的房型（floor04 空間輪流定義用），例如 --retype room-2=dining_room",
    )
    args = parser.parse_args()

    image_path = (REPO_ROOT / args.image).resolve()
    if not image_path.exists():
        print(f"找不到圖檔：{image_path}")
        return 1

    print(f"辨識中（跑真實管線，不使用快照）：{image_path.name}")
    layout = analyze(image_path)
    scale = layout.get("scale") or {}
    print(
        f"定標：{scale.get('cm_per_px')} cm/px"
        f"（來源 {scale.get('source')}，信心 {scale.get('confidence')}）"
    )
    print(f"辨識到 {len(layout.get('rooms') or [])} 間房、"
          f"{len(layout.get('doors') or [])} 道門、{len(layout.get('windows') or [])} 扇窗\n")

    retype = dict(pair.split("=", 1) for pair in args.retype)
    total_placed = 0
    total_failed = 0
    floating = 0

    for build in rooms_from_layout_json(layout):
        if build.room_id in retype:
            build.room_type = retype[build.room_id]
        room = build.room
        doors = len(room.doors())
        windows = len(room.windows())
        print(
            f"── {build.room_id} {build.label}（{build.room_type}）"
            f" {room.width:.0f}×{room.depth:.0f} cm，門 {doors} 窗 {windows}"
        )

        items = build_items(build.room_type)
        if not items:
            reason = (
                "規格明訂留空" if build.room_type in ROOM_PLAN else "沒有對應的房型規則"
            )
            print(f"  （不擺放：{reason}）\n")
            continue

        if normalize_room_type(build.room_type) not in ROOM_RULES:
            print(f"  ⚠ 房型 {build.room_type} 沒有擺放規則，全部當一般貼牆處理")

        result = place_room(room, normalize_room_type(build.room_type), items)
        for placed in result["placed"]:
            line, stray = describe(placed, room, build.room_type)
            if stray:
                floating += 1
            print(line)
            total_placed += 1
        for failure in result["failed"]:
            print(f"  ✗ {failure['id']:20} {failure['reason']}")
            total_failed += 1
        if not args.no_draw and result["placed"]:
            print()
            for line in draw(room, result["placed"]):
                print("  " + line)
            used = sorted({p.catalog.type for p in result["placed"]})
            print("  " + "  ".join(f"{LEGEND.get(t, '?')}={t}" for t in used))
            print("  ▒=窗  ▓=門（含開門扇形所在牆段）")
        print()

    print("─" * 72)
    print(
        f"擺放成功 {total_placed} 件、失敗 {total_failed} 件、"
        f"不該浮空卻浮空 {floating} 件"
    )
    return 0 if floating == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
