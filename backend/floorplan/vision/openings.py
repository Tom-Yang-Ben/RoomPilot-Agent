"""門窗與承載牆、房間的可追溯關係。"""

from __future__ import annotations

import math
from typing import Any, Mapping


def _point_segment_distance(point: tuple[float, float], segment: Mapping[str, Any]) -> float:
    start, end = segment.get("start") or {}, segment.get("end") or {}
    try:
        x, y = point
        x1, y1 = float(start["x"]), float(start["y"])
        x2, y2 = float(end["x"]), float(end["y"])
    except (KeyError, TypeError, ValueError):
        return math.inf
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.dist(point, (x1, y1))
    factor = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.dist(point, (x1 + factor * dx, y1 + factor * dy))


def enrich_opening_relationships(analysis: dict[str, Any]) -> None:
    walls = list(analysis.get("walls") or [])
    rooms = list((analysis.get("spatial_report") or {}).get("rooms") or [])
    legacy_rooms = {str(room.get("id")): room for room in analysis.get("rooms") or []}
    for kind in ("doors", "windows"):
        for opening in analysis.get(kind) or []:
            start, end = opening.get("start") or {}, opening.get("end") or {}
            midpoint = (
                (float(start.get("x", 0.0)) + float(end.get("x", 0.0))) / 2,
                (float(start.get("y", 0.0)) + float(end.get("y", 0.0))) / 2,
            )
            nearest_wall = min(
                enumerate(walls, start=1),
                key=lambda pair: _point_segment_distance(midpoint, pair[1]),
                default=None,
            )
            opening["host_wall_id"] = f"wall-{nearest_wall[0]}" if nearest_wall else "wall-unresolved"

            ranked_rooms: list[tuple[float, str]] = []
            for room in rooms:
                room_id = str(room.get("room_id"))
                centroid = legacy_rooms.get(room_id, {}).get("centroid_m") or {}
                try:
                    distance = math.dist(midpoint, (float(centroid["x"]), float(centroid["y"])))
                except (KeyError, TypeError, ValueError):
                    continue
                ranked_rooms.append((distance, room_id))
            ranked_rooms.sort()
            if not opening.get("room_ids"):
                opening["room_ids"] = [room_id for _, room_id in ranked_rooms[: (2 if kind == "doors" else 1)]]
                opening["relationship_source"] = "geometry_nearest_wall_and_room"
            else:
                opening["relationship_source"] = "reference_annotation"
