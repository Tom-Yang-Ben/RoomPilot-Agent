from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union

from ..engine.dxf_room import build_room_from_dxf
from ..engine.models import Room
from ..upgrade3d.dxf_parser import parse_dxf_bytes


def _flip_parsed_z(parsed: dict[str, Any]) -> dict[str, Any]:
    """把 dxf_parser 輸出的 z 軸取負。

    DXF 的 y 軸朝北(俯視圖),three.js 的 +z 軸朝向觀察者(南)——
    不翻轉的話畫面等於從地板下方往上看(鏡像/下視圖)。
    在來源處翻轉一次,下游(Room/引擎/payload)全部同一座標框。
    """
    def flip_ring(ring: list) -> list:
        return [[p[0], -p[1]] for p in ring]

    out = dict(parsed)
    out["wall_polys"] = [
        {
            "exterior": flip_ring(poly.get("exterior") or []),
            "holes": [flip_ring(hole) for hole in poly.get("holes") or []],
        }
        for poly in parsed.get("wall_polys") or []
    ]
    # 含門窗開口的牆體(upgrade3d/wall_openings.py 產出)必須跟 wall_polys 同框,
    # 否則有開口的牆會相對其他幾何鏡像。parsed 沒有這個鍵時本段為 no-op。
    if parsed.get("wall_solids") is not None:
        out["wall_solids"] = [
            {
                **solid,
                "polys": [
                    {
                        "exterior": flip_ring(poly.get("exterior") or []),
                        "holes": [flip_ring(hole) for hole in poly.get("holes") or []],
                    }
                    for poly in solid.get("polys") or []
                ],
            }
            for solid in parsed.get("wall_solids") or []
        ]
    for key in ("windows", "doors"):
        out[key] = [
            {"x1": s["x1"], "z1": -s["z1"], "x2": s["x2"], "z2": -s["z2"]}
            for s in parsed.get(key) or []
        ]
    bbox = parsed.get("bbox") or {}
    if bbox:
        out["bbox"] = {
            "minx": bbox["minx"],
            "maxx": bbox["maxx"],
            "minz": -bbox["maxz"],
            "maxz": -bbox["minz"],
        }
    return out


def parse_floorplan_with_engine(dxf_text: str) -> tuple[dict[str, Any] | None, Room | None]:
    """DXF 文字 → (payload 的 floorplan 區塊, 引擎 Room)。

    解析走 upgrade3d.dxf_parser(ezdxf,平面中心原點、公尺),
    再由 engine.dxf_room 取最大封閉房間轉成 Room(角落原點)。
    回傳的線段座標一律換算成「房間中心原點、公分」。
    """
    try:
        parsed = _flip_parsed_z(parse_dxf_bytes(dxf_text.encode("utf-8", errors="ignore"), "upload.dxf"))
        build = build_room_from_dxf(parsed)
        bbox = parsed.get("bbox") or {}
        plan_area = max(
            (float(bbox.get("maxx", 0)) - float(bbox.get("minx", 0)))
            * (float(bbox.get("maxz", 0)) - float(bbox.get("minz", 0))),
            0.0,
        )
        selected_area = build.room.width * build.room.depth / 10_000
        if build.mode == "largest" and plan_area and selected_area / plan_area < 0.25:
            build = build_room_from_dxf(parsed, mode="plan")
    except Exception:
        return None, None

    room = build.room
    ox, oz = build.offset
    room_center_x_cm = ox + room.width / 2
    room_center_z_cm = oz + room.depth / 2

    wall_segments = [
        {
            "start": {"x": round(w.x1 - room.width / 2, 1), "z": round(w.y1 - room.depth / 2, 1)},
            "end": {"x": round(w.x2 - room.width / 2, 1), "z": round(w.y2 - room.depth / 2, 1)},
        }
        for w in room.walls
    ]

    def _convert(segs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "start": {
                    "x": round(s["x1"] * 100 - room_center_x_cm, 1),
                    "z": round(s["z1"] * 100 - room_center_z_cm, 1),
                },
                "end": {
                    "x": round(s["x2"] * 100 - room_center_x_cm, 1),
                    "z": round(s["z2"] * 100 - room_center_z_cm, 1),
                },
            }
            for s in segs
        ]

    doors = _convert(parsed.get("doors", []))
    windows = _convert(parsed.get("windows", []))
    stats = parsed.get("stats", {})

    def _ring_to_payload(coords) -> list:
        return [
            [
                round(point[0] * 100 - room_center_x_cm, 1),
                round(point[1] * 100 - room_center_z_cm, 1),
            ]
            for point in coords
        ]

    wall_polys = [
        {
            "exterior": _ring_to_payload(poly.get("exterior") or []),
            "holes": [
                _ring_to_payload(hole)
                for hole in poly.get("holes") or []
                if len(hole) >= 3
            ],
        }
        for poly in parsed.get("wall_polys") or []
        if len(poly.get("exterior") or []) >= 3
    ]

    # 可擺放區域 = bbox 減去牆體實心區(自由空間),面積 ≥1m² 的每一塊當一個 region。
    # 這對「有封閉房間」與「開放式牆線(如 floor01,沒有 holes)」兩種 DXF 都成立;
    # 不能用 Room.walls 重建多邊形 —— fallback 模式下那是多個獨立環串接,會得到垃圾幾何。
    room_regions = []
    try:
        solids = []
        for poly in parsed.get("wall_polys") or []:
            shell = poly.get("exterior") or []
            if len(shell) < 3:
                continue
            solid = Polygon(shell, [h for h in (poly.get("holes") or []) if len(h) >= 3])
            if not solid.is_valid:
                solid = solid.buffer(0)
            if not solid.is_empty:
                solids.append(solid)
        bb = parsed["bbox"]
        free = shapely_box(bb["minx"], bb["minz"], bb["maxx"], bb["maxz"]).difference(unary_union(solids))
        pieces = list(free.geoms) if free.geom_type == "MultiPolygon" else [free]
        for piece in pieces:
            if piece.is_empty or piece.area < 1.0:
                continue
            # 必須保留 interiors:牆體在自由空間裡是「洞」,丟掉洞家具就能疊在牆上
            room_regions.append(
                {
                    "exterior": _ring_to_payload(piece.exterior.coords),
                    "holes": [_ring_to_payload(ring.coords) for ring in piece.interiors],
                }
            )
    except Exception:
        room_regions = []

    floorplan = {
        "coordinate_unit": "cm",
        "width_cm": round(room.width, 1),
        "depth_cm": round(room.depth, 1),
        "source": "dxf",
        "wall_count": len(room.walls),
        "door_count": len(doors),
        "window_count": len(windows),
        "raw_segment_count": int(stats.get("wall_segments", 0)),
        "layers": [],
        "wall_layers": [],
        "door_layers": [],
        "window_layers": [],
        "wall_segments": wall_segments,
        "wall_polys": wall_polys,
        "plan_segments": wall_segments,
        "door_segments": doors,
        "window_segments": windows,
        "room_regions": room_regions,
    }
    return floorplan, room
