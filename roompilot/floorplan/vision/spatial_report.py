"""把平面圖辨識結果整理成可追溯的房間空間報告。"""

from __future__ import annotations

from collections import Counter
import math
from typing import Any, Iterable, Mapping


def _between(value: float, start: float, end: float, tolerance: float = 0.03) -> bool:
    return min(start, end) - tolerance <= value <= max(start, end) + tolerance


def _confidence(score: float) -> dict[str, Any]:
    level = "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"
    return {"score": round(score, 3), "level": level}


def _polygon_area(polygon: list[dict[str, float]]) -> float:
    return abs(sum(
        point["x"] * polygon[(index + 1) % len(polygon)]["y"]
        - polygon[(index + 1) % len(polygon)]["x"] * point["y"]
        for index, point in enumerate(polygon)
    )) / 2


def _wall_lengths(polygon: list[dict[str, float]]) -> list[float]:
    return [
        round(math.dist(
            (point["x"], point["y"]),
            (polygon[(index + 1) % len(polygon)]["x"], polygon[(index + 1) % len(polygon)]["y"]),
        ), 3)
        for index, point in enumerate(polygon)
    ]


def _rectangle_for_room(
    room: Mapping[str, Any], walls: Iterable[Mapping[str, Any]]
) -> tuple[list[dict[str, float]] | None, list[Mapping[str, Any]]]:
    centroid = room.get("centroid_m") or {}
    try:
        cx, cy = float(centroid["x"]), float(centroid["y"])
    except (KeyError, TypeError, ValueError):
        return None, []

    left: list[tuple[float, Mapping[str, Any]]] = []
    right: list[tuple[float, Mapping[str, Any]]] = []
    bottom: list[tuple[float, Mapping[str, Any]]] = []
    top: list[tuple[float, Mapping[str, Any]]] = []
    for wall in walls:
        start, end = wall.get("start") or {}, wall.get("end") or {}
        try:
            x1, y1 = float(start["x"]), float(start["y"])
            x2, y2 = float(end["x"]), float(end["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if abs(x1 - x2) <= 0.03 and _between(cy, y1, y2):
            (left if x1 <= cx else right).append((x1, wall))
        if abs(y1 - y2) <= 0.03 and _between(cx, x1, x2):
            (bottom if y1 <= cy else top).append((y1, wall))

    if not all((left, right, bottom, top)):
        return None, []
    lx, left_wall = max(left, key=lambda item: item[0])
    rx, right_wall = min(right, key=lambda item: item[0])
    by, bottom_wall = max(bottom, key=lambda item: item[0])
    ty, top_wall = min(top, key=lambda item: item[0])
    if rx <= lx or ty <= by:
        return None, []
    return (
        [
            {"x": round(lx, 3), "y": round(by, 3)},
            {"x": round(rx, 3), "y": round(by, 3)},
            {"x": round(rx, 3), "y": round(ty, 3)},
            {"x": round(lx, 3), "y": round(ty, 3)},
        ],
        [left_wall, right_wall, bottom_wall, top_wall],
    )


def build_spatial_report(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """建立房間數量、內淨尺寸、證據與只針對疑點的修正清單。"""
    walls = list(analysis.get("walls") or [])
    report_rooms: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    for room in analysis.get("rooms") or []:
        explicit_polygon = room.get("polygon_m")
        polygon = [dict(point) for point in explicit_polygon] if explicit_polygon else None
        boundary_walls: list[Mapping[str, Any]] = []
        if polygon is None:
            polygon, boundary_walls = _rectangle_for_room(room, walls)
        label_score = float(room.get("confidence", 0.0))
        wall_score = float(room.get("polygon_confidence", 0.0)) if explicit_polygon else min(
            (float(wall.get("confidence", 0.0)) for wall in boundary_walls), default=0.0
        )
        score = min(label_score, wall_score) if polygon else 0.0
        evidence = [
            {
                "kind": "ocr_room_label",
                "source": room.get("source"),
                "label": room.get("label"),
                "bbox_px": room.get("bbox_px"),
                "confidence": round(label_score, 3),
            }
        ]
        if polygon:
            width = round(max(point["x"] for point in polygon) - min(point["x"] for point in polygon), 3)
            depth = round(max(point["y"] for point in polygon) - min(point["y"] for point in polygon), 3)
            is_rectangle = len(polygon) == 4
            spatial_room = {
                "room_id": room.get("id"),
                "room_type": room.get("type"),
                "label": room.get("label"),
                "polygon_m": polygon,
                "shape_type": "rectangle" if is_rectangle else "irregular",
                "inner_dimensions_m": {"width": width, "depth": depth} if is_rectangle else None,
                "bounding_dimensions_m": {"width": width, "depth": depth},
                "wall_lengths_m": _wall_lengths(polygon),
                "net_area_m2": round(_polygon_area(polygon), 3),
                "minimum_clear_width_m": round(min(width, depth), 3) if is_rectangle else None,
                "maximum_usable_rectangle_m": {"width": width, "depth": depth} if is_rectangle else None,
                "confidence": _confidence(score),
                "evidence": evidence
                + [
                    {
                        "kind": "inner_wall_boundary",
                        "source": room.get("polygon_source") or "wall_geometry",
                        "wall_count": len(boundary_walls),
                        "confidence": round(wall_score, 3),
                    }
                ],
                "assumptions": ["尺寸量至辨識牆線；施工前仍須現場丈量"],
            }
        else:
            spatial_room = {
                "room_id": room.get("id"),
                "room_type": room.get("type"),
                "label": room.get("label"),
                "polygon_m": None,
                "shape_type": "unresolved",
                "inner_dimensions_m": None,
                "net_area_m2": None,
                "confidence": _confidence(0.0),
                "evidence": evidence,
                "assumptions": [],
            }
        report_rooms.append(spatial_room)
        if spatial_room["shape_type"] == "irregular":
            review_items.append(
                {
                    "id": f"room:{room.get('id')}:irregular_geometry",
                    "category": "room_geometry",
                    "room_id": room.get("id"),
                    "reason": "irregular_room_detailed_geometry_required",
                    "status": "needs_targeted_review",
                }
            )
        elif spatial_room["confidence"]["level"] != "high":
            review_items.append(
                {
                    "id": f"room:{room.get('id')}:geometry",
                    "category": "room_geometry",
                    "room_id": room.get("id"),
                    "reason": "room_boundary_unresolved" if not polygon else "room_geometry_low_confidence",
                    "status": "needs_targeted_review",
                }
            )

    counts = Counter(str(room.get("room_type") or "unknown") for room in report_rooms)
    return {
        "schema_version": "1.0",
        "measurement_basis": "inner_wall_finish_geometry",
        "unit": "metre",
        "room_counts": dict(counts),
        "rooms": report_rooms,
        "review_items": review_items,
    }
