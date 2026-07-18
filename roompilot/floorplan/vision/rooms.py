"""從 Cody 牆體幾何推導可人工確認的房間多邊形。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import cv2
import numpy as np


def infer_rooms_from_walls(
    walls: Iterable[Mapping[str, Any]],
    *,
    labelled_rooms: Iterable[Mapping[str, Any]] = (),
    minimum_area_m2: float = 1.0,
) -> list[dict[str, Any]]:
    """將牆中心線光柵化，取不接觸外框的封閉空間。"""
    wall_items = list(walls)
    points = [
        item.get(key)
        for item in wall_items
        for key in ("start", "end")
        if isinstance(item.get(key), Mapping)
    ]
    if len(points) < 4:
        return []
    width_m = max(float(point.get("x") or 0) for point in points)
    depth_m = max(float(point.get("y") or 0) for point in points)
    if width_m <= 0 or depth_m <= 0:
        return []

    longest = max(width_m, depth_m)
    pixels_per_m = min(120.0, max(45.0, 640.0 / longest))
    width_px = max(96, int(round(width_m * pixels_per_m)) + 1)
    depth_px = max(96, int(round(depth_m * pixels_per_m)) + 1)
    obstacle = np.zeros((depth_px, width_px), dtype=np.uint8)

    def pixel(point: Mapping[str, Any]) -> tuple[int, int]:
        return (
            int(round(float(point.get("x") or 0) * pixels_per_m)),
            int(round((depth_m - float(point.get("y") or 0)) * pixels_per_m)),
        )

    for item in wall_items:
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            continue
        thickness = max(
            3,
            int(round(float(item.get("thickness_m") or 0.12) * pixels_per_m)),
        )
        cv2.line(obstacle, pixel(start), pixel(end), 255, thickness)

    boundary_thickness = max(3, int(round(0.12 * pixels_per_m)))
    cv2.rectangle(
        obstacle,
        (0, 0),
        (width_px - 1, depth_px - 1),
        255,
        boundary_thickness,
    )
    obstacle = cv2.morphologyEx(
        obstacle,
        cv2.MORPH_CLOSE,
        np.ones((3, 3), dtype=np.uint8),
        iterations=2,
    )
    free = np.where(obstacle == 0, 255, 0).astype(np.uint8)
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(free)

    label_candidates = [dict(item) for item in labelled_rooms]
    inferred: list[dict[str, Any]] = []
    for component_id in range(1, component_count):
        x, y, width, height, area_px = stats[component_id]
        if x <= 0 or y <= 0 or x + width >= width_px or y + height >= depth_px:
            continue
        area_m2 = float(area_px) / (pixels_per_m**2)
        if area_m2 < minimum_area_m2:
            continue
        component = np.where(labels == component_id, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, max(2.0, perimeter * 0.012), True)
        polygon_m = [
            {
                "x": round(float(point[0][0]) / pixels_per_m, 3),
                "y": round(depth_m - float(point[0][1]) / pixels_per_m, 3),
            }
            for point in polygon
        ]
        if len(polygon_m) < 3:
            continue

        matching_label = None
        for candidate in label_candidates:
            centroid = candidate.get("centroid_m")
            if not isinstance(centroid, Mapping):
                continue
            test_point = (
                float(centroid.get("x") or 0) * pixels_per_m,
                (depth_m - float(centroid.get("y") or 0)) * pixels_per_m,
            )
            if cv2.pointPolygonTest(contour, test_point, False) >= 0:
                matching_label = candidate
                break
        room_index = len(inferred) + 1
        inferred.append(
            {
                "id": str(matching_label.get("id")) if matching_label else f"room-{room_index}",
                "type": str(matching_label.get("type")) if matching_label else "default",
                "label": str(matching_label.get("label")) if matching_label else f"空間 {room_index}",
                "confidence": round(
                    float(matching_label.get("confidence", 0.55))
                    if matching_label
                    else 0.82,
                    3,
                ),
                "source": "cody_wall_enclosure",
                "polygon_source": "cody_wall_enclosure",
                "polygon_confidence": 0.82,
                "polygon_m": polygon_m,
                "area_m2": round(area_m2, 2),
            }
        )
    return sorted(
        inferred,
        key=lambda room: (
            -max(point["y"] for point in room["polygon_m"]),
            min(point["x"] for point in room["polygon_m"]),
        ),
    )
