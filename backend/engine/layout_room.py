"""layout_room.py — 把辨識管線的 `layout_json` 轉成 furniture_engine 的 Room。

比照 `dxf_room.py` 的定位：**只做純資料轉換**，不讀檔、不呼叫辨識管線、
不打任何 API。輸入是呼叫端已經取得的 `layout_json` dict。

── 為什麼需要轉換 ──────────────────────────────────────────────
  `layout_json` 的座標：
    - 原點在平面 bbox 左下角，x 向右、y 向上，單位**公分**（`coordinate_system`）。
    - 房間是 `polygon_cm`；門窗是獨立清單，各自帶 `start`／`end`，
      **`room_ids` 目前是空的**，所以歸屬要由本模組用幾何算出來。
  Room 引擎需要：
    - 每間房各自一個 Room，原點在該房左下角，座標全為正。
    - 門窗要落在房間邊界上，`layout_strategy` 才認得出它們在哪面牆。

因此本模組：① 取房間 bbox 當 Room；② 把門窗指派給邊界對得上的房間；
③ 平移到房間局部座標；④ 把門窗座標吸附到最接近的那面牆。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.engine.models import Opening, Room


# 門窗與房間邊界的最大容許距離。辨識輸出的門窗畫在牆中線上，房間多邊形畫在
# 牆內緣，兩者天生差半個牆厚（floor04 實測約 8～11 公分），取 12 公分涵蓋。
DEFAULT_BOUNDARY_TOLERANCE_CM = 12.0


@dataclass
class LayoutRoomBuild:
    """一間房的轉換結果，座標與尺寸皆為公分。"""

    room_id: str
    room_type: str
    label: str
    room: Room
    offset: tuple[float, float]  # (ox, oy)：該房左下角在平面座標中的位置
    area_m2: float = 0.0
    unassigned_openings: list[str] = field(default_factory=list)


def _polygon_bbox(polygon: list[dict]) -> tuple[float, float, float, float]:
    xs = [float(point["x"]) for point in polygon]
    ys = [float(point["y"]) for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _segment(opening: dict) -> tuple[float, float, float, float]:
    start = opening["start"]
    end = opening["end"]
    return (
        float(start["x"]),
        float(start["y"]),
        float(end["x"]),
        float(end["y"]),
    )


def _overlaps(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:
    return min(high_a, high_b) - max(low_a, low_b) > 1.0


def opening_belongs_to(
    bbox: tuple[float, float, float, float],
    opening: dict,
    tolerance: float = DEFAULT_BOUNDARY_TOLERANCE_CM,
) -> str | None:
    """判斷門窗是否落在房間的某一面牆上；回傳牆面名稱或 None。"""
    min_x, min_y, max_x, max_y = bbox
    x1, y1, x2, y2 = _segment(opening)

    if abs(y1 - y2) <= 1.0:  # 水平段 → 南牆或北牆
        low, high = sorted((x1, x2))
        if not _overlaps(low, high, min_x, max_x):
            return None
        if abs(y1 - min_y) <= tolerance:
            return "south"
        if abs(y1 - max_y) <= tolerance:
            return "north"
        return None

    if abs(x1 - x2) <= 1.0:  # 垂直段 → 西牆或東牆
        low, high = sorted((y1, y2))
        if not _overlaps(low, high, min_y, max_y):
            return None
        if abs(x1 - min_x) <= tolerance:
            return "west"
        if abs(x1 - max_x) <= tolerance:
            return "east"
    return None


def _to_local_opening(
    kind: str,
    opening: dict,
    bbox: tuple[float, float, float, float],
    side: str,
) -> Opening:
    """平移到房間局部座標，並把門窗吸附到它所屬的那面牆。"""
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    depth = max_y - min_y
    x1, y1, x2, y2 = _segment(opening)

    local_x1, local_x2 = x1 - min_x, x2 - min_x
    local_y1, local_y2 = y1 - min_y, y2 - min_y

    if side == "south":
        local_y1 = local_y2 = 0.0
    elif side == "north":
        local_y1 = local_y2 = depth
    elif side == "west":
        local_x1 = local_x2 = 0.0
    else:
        local_x1 = local_x2 = width

    swing = opening.get("swing_end") if kind == "door" else None
    swing_x = float(swing["x"]) - min_x if isinstance(swing, dict) else None
    swing_y = float(swing["y"]) - min_y if isinstance(swing, dict) else None

    window_type = opening.get("window_type") if kind == "window" else None
    sill = opening.get("sill_height_cm")

    return Opening(
        kind="door" if kind == "door" else "window",
        x1=round(local_x1, 2),
        y1=round(local_y1, 2),
        x2=round(local_x2, 2),
        y2=round(local_y2, 2),
        window_type=window_type if window_type in {"standard", "floor_to_ceiling"} else None,
        sill_height_cm=float(sill) if isinstance(sill, (int, float)) else None,
        swing_x=None if swing_x is None else round(swing_x, 2),
        swing_y=None if swing_y is None else round(swing_y, 2),
    )


def rooms_from_layout_json(
    layout: dict,
    *,
    tolerance: float = DEFAULT_BOUNDARY_TOLERANCE_CM,
) -> list[LayoutRoomBuild]:
    """把 `layout_json` 的每間房轉成一個 Room，並把門窗指派給對得上的房間。

    同一道門若同時貼著兩間房的邊界（例如隔間門），兩邊都會拿到，這是刻意的：
    兩邊都不該擋住它。
    """
    builds: list[LayoutRoomBuild] = []
    doors = list(layout.get("doors") or [])
    windows = list(layout.get("windows") or [])

    for entry in layout.get("rooms") or []:
        polygon = entry.get("polygon_cm") or []
        if len(polygon) < 3:
            continue
        bbox = _polygon_bbox(polygon)
        min_x, min_y, max_x, max_y = bbox

        openings: list[Opening] = []
        for kind, source in (("door", doors), ("window", windows)):
            for opening in source:
                side = opening_belongs_to(bbox, opening, tolerance)
                if side is not None:
                    openings.append(_to_local_opening(kind, opening, bbox, side))

        builds.append(
            LayoutRoomBuild(
                room_id=str(entry.get("id") or ""),
                room_type=str(entry.get("type") or "unknown"),
                label=str(entry.get("label") or ""),
                room=Room(
                    width=round(max_x - min_x, 1),
                    depth=round(max_y - min_y, 1),
                    openings=openings,
                ),
                offset=(min_x, min_y),
                area_m2=float(entry.get("area_m2") or 0.0),
            )
        )

    return builds


__all__ = [
    "DEFAULT_BOUNDARY_TOLERANCE_CM",
    "LayoutRoomBuild",
    "opening_belongs_to",
    "rooms_from_layout_json",
]
