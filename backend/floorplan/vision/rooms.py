"""從 Cody 牆體幾何推導可人工確認的房間多邊形。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from typing import Any

import cv2
import numpy as np


def _polygon_area(points: list[Mapping[str, Any]]) -> float:
    return abs(
        sum(
            float(point["x"]) * float(points[(index + 1) % len(points)]["y"])
            - float(points[(index + 1) % len(points)]["x"]) * float(point["y"])
            for index, point in enumerate(points)
        )
    ) / 2


def _remove_narrow_spikes(
    polygon: list[Mapping[str, Any]],
    *,
    max_base_m: float = 0.35,
    min_height_m: float = 0.15,
) -> list[dict[str, Any]]:
    """Remove thin raster-closure needles without flattening normal room corners."""
    repaired = [dict(point) for point in polygon]
    changed = True
    while changed and len(repaired) > 3:
        changed = False
        area = _polygon_area(repaired)
        for index, point in enumerate(repaired):
            previous = repaired[index - 1]
            following = repaired[(index + 1) % len(repaired)]
            ax = float(previous["x"])
            ay = float(previous["y"])
            bx = float(point["x"])
            by = float(point["y"])
            cx = float(following["x"])
            cy = float(following["y"])
            dx = cx - ax
            dy = cy - ay
            base = math.hypot(dx, dy)
            if base <= 1e-9 or base > max_base_m:
                if base <= 1e-9:
                    continue
            projection = ((bx - ax) * dx + (by - ay) * dy) / (base * base)
            height = abs(dx * (ay - by) - (ax - bx) * dy) / base
            if 0.0 <= projection <= 1.0 and height <= 0.02:
                repaired = repaired[:index] + repaired[index + 1 :]
                changed = True
                break
            if base > max_base_m:
                continue
            if not 0.1 <= projection <= 0.9:
                continue
            if height < min_height_m or height < base * 0.75:
                continue
            candidate = repaired[:index] + repaired[index + 1 :]
            area_change = abs(area - _polygon_area(candidate))
            if area_change > max(0.05, area * 0.05):
                continue
            repaired = candidate
            changed = True
            break
    return repaired


def _apply_layout_label_suggestions(
    rooms: list[dict[str, Any]],
    *,
    width_m: float,
    depth_m: float,
) -> None:
    """在沒有 OCR 房名時，對常見七區住宅格局提供低信心候選名稱。"""
    if len(rooms) != 7 or any(room.get("type") != "default" for room in rooms):
        return

    def center(room: Mapping[str, Any]) -> tuple[float, float]:
        polygon = room.get("polygon_m") or []
        return (
            sum(float(point["x"]) for point in polygon) / len(polygon),
            sum(float(point["y"]) for point in polygon) / len(polygon),
        )

    by_height = sorted(rooms, key=lambda room: center(room)[1], reverse=True)
    top = sorted(by_height[:2], key=lambda room: center(room)[0])
    middle = sorted(by_height[2:5], key=lambda room: center(room)[0])
    bottom = sorted(by_height[5:], key=lambda room: center(room)[0])
    if (
        min(center(room)[1] for room in top)
        <= max(center(room)[1] for room in middle) + depth_m * 0.08
        or min(center(room)[1] for room in middle)
        <= max(center(room)[1] for room in bottom) + depth_m * 0.08
    ):
        return

    suggestions = [
        (top[0], "bedroom", "臥室"),
        (top[1], "kitchen", "廚房"),
        (middle[0], "storage", "儲藏室"),
        (middle[1], "circulation", "走道"),
        (middle[2], "bathroom", "浴室"),
        (bottom[0], "balcony", "陽台"),
        (bottom[1], "living_room", "客廳"),
    ]
    for room, room_type, label in suggestions:
        room["type"] = room_type
        room["label"] = f"{label}（待確認）"
        room["source"] = "layout_heuristic"
        room["confidence"] = min(float(room.get("confidence", 0.55)), 0.55)


def infer_rooms_from_walls(
    walls: Iterable[Mapping[str, Any]],
    *,
    labelled_rooms: Iterable[Mapping[str, Any]] = (),
    minimum_area_m2: float = 1.0,
) -> list[dict[str, Any]]:
    """將牆中心線光柵化，封閉門洞後取不接觸外框的空間。"""
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
    enable_doorway_closure = longest >= 6.0
    pixels_per_m = min(120.0, max(45.0, 640.0 / longest))
    width_px = max(96, int(round(width_m * pixels_per_m)) + 1)
    depth_px = max(96, int(round(depth_m * pixels_per_m)) + 1)
    obstacle = np.zeros((depth_px, width_px), dtype=np.uint8)

    def pixel(point: Mapping[str, Any]) -> tuple[int, int]:
        return (
            int(round(float(point.get("x") or 0) * pixels_per_m)),
            int(round((depth_m - float(point.get("y") or 0)) * pixels_per_m)),
        )

    def axis(item: Mapping[str, Any]) -> tuple[str, float] | None:
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            return None
        dx = abs(float(end.get("x") or 0) - float(start.get("x") or 0))
        dy = abs(float(end.get("y") or 0) - float(start.get("y") or 0))
        if dx >= dy * 3:
            return ("horizontal", (float(start.get("y") or 0) + float(end.get("y") or 0)) / 2)
        if dy >= dx * 3:
            return ("vertical", (float(start.get("x") or 0) + float(end.get("x") or 0)) / 2)
        return None

    for item in wall_items:
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            continue
        start_x = float(start.get("x") or 0)
        start_y = float(start.get("y") or 0)
        end_x = float(end.get("x") or 0)
        end_y = float(end.get("y") or 0)
        length = float(np.hypot(end_x - start_x, end_y - start_y))
        if length <= 0:
            continue
        # Cody 的牆中心線會在門窗處中斷。只沿牆本身的方向延伸端點，
        # 封閉一般住宅開口供房間分區使用；原始牆線仍保持不變。
        item_axis = axis(item)
        has_collinear_peer = item_axis is not None and any(
            peer is not item
            and (peer_axis := axis(peer)) is not None
            and peer_axis[0] == item_axis[0]
            and abs(peer_axis[1] - item_axis[1]) <= 0.08
            for peer in wall_items
        )
        closure_m = (
            1.2
            if enable_doorway_closure and (length >= 1.0 or has_collinear_peer)
            else 0.0
        )
        unit_x = (end_x - start_x) / length
        unit_y = (end_y - start_y) / length
        raster_start = {
            "x": start_x - unit_x * closure_m,
            "y": start_y - unit_y * closure_m,
        }
        raster_end = {
            "x": end_x + unit_x * closure_m,
            "y": end_y + unit_y * closure_m,
        }
        thickness = max(
            3,
            int(round(float(item.get("thickness_m") or 0.12) * pixels_per_m)),
        )
        cv2.line(obstacle, pixel(raster_start), pixel(raster_end), 255, thickness)

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
        polygon_m = _remove_narrow_spikes(polygon_m)
        if len(polygon_m) < 3:
            continue

        # OCR 房名的錨點是「文字方塊中心」，不是房間幾何中心，所以印在交界附近的
        # 房名很容易落進隔壁房。舊寫法有兩個問題：(1) 取 label_candidates 的第一個
        # 命中就 break，順序決定勝負，不看信心值也不看離邊界多遠；(2) 命中後不把它
        # 從候選清單移除，同一個房名會被多個空間重複認領，連 id 都重複。
        # 實際後果就是 QA #6：圖上「主臥室」被配到 7.29 m² 的小房，8.04 m² 的真主臥
        # 只拿到通用標籤。改成在所有落在此多邊形內的候選中取信心最高者，同分時取
        # 離邊界最遠（最深入房內）者，並在認領後移出候選。
        matching_index = None
        best_score: tuple[float, float] | None = None
        for index, candidate in enumerate(label_candidates):
            centroid = candidate.get("centroid_m")
            if not isinstance(centroid, Mapping):
                continue
            test_point = (
                float(centroid.get("x") or 0) * pixels_per_m,
                (depth_m - float(centroid.get("y") or 0)) * pixels_per_m,
            )
            depth_inside = float(cv2.pointPolygonTest(contour, test_point, True))
            if depth_inside < 0:
                continue
            score = (float(candidate.get("confidence") or 0.0), depth_inside)
            if best_score is None or score > best_score:
                best_score = score
                matching_index = index
        matching_label = (
            label_candidates.pop(matching_index) if matching_index is not None else None
        )
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
    inferred = sorted(
        inferred,
        key=lambda room: (
            -max(point["y"] for point in room["polygon_m"]),
            min(point["x"] for point in room["polygon_m"]),
        ),
    )
    _apply_layout_label_suggestions(inferred, width_m=width_m, depth_m=depth_m)
    return inferred
