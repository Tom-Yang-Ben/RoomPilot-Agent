from __future__ import annotations

import math
from typing import Any


WALL_KEYWORDS = ("wall", "牆", "墙", "壁", "mur", "wand", "muro")
WINDOW_KEYWORDS = ("window", "win", "glaz", "窗", "glass")
DOOR_KEYWORDS = ("door", "gate", "entry", "門", "门")


def _tokenize_dxf(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    pairs: list[tuple[int, str]] = []
    index = 0

    while index + 1 < len(lines):
        code_text = lines[index].strip()
        value = lines[index + 1]
        if code_text and code_text.lstrip("-").isdigit():
            pairs.append((int(code_text), value))
            index += 2
        else:
            index += 1

    return pairs


def _segment_length(segment: list[list[float]]) -> float:
    start, end = segment
    return math.hypot(end[0] - start[0], end[1] - start[1])


def _segment_midpoint(segment: list[list[float]]) -> tuple[float, float]:
    start, end = segment
    return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)


def _distance_point_to_segment(point: tuple[float, float], segment: list[list[float]]) -> float:
    px, py = point
    (ax, ay), (bx, by) = segment
    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-9:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    closest_x = ax + dx * t
    closest_y = ay + dy * t
    return math.hypot(px - closest_x, py - closest_y)


def _segment_key(segment: list[list[float]], precision: int = 3) -> tuple[tuple[float, float], tuple[float, float]]:
    start = (round(segment[0][0], precision), round(segment[0][1], precision))
    end = (round(segment[1][0], precision), round(segment[1][1], precision))
    return tuple(sorted((start, end)))


def _dedupe_segments(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    deduped: list[list[list[float]]] = []
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for segment in segments:
        if _segment_length(segment) <= 1e-6:
            continue
        key = _segment_key(segment)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(segment)

    return deduped


def _parse_dxf_segments(text: str) -> list[dict[str, Any]]:
    pairs = _tokenize_dxf(text)
    segments: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    index = 0
    total = len(pairs)

    def finalize(entity: dict[str, Any] | None) -> None:
        if not entity:
            return

        entity_type = entity.get("type")
        layer = entity.get("layer") or "0"

        if entity_type == "LINE" and entity.get(10) is not None and entity.get(11) is not None:
            segments.append({"layer": layer, "segment": [[entity[10], entity[20]], [entity[11], entity[21]]]})
        elif entity_type == "LWPOLYLINE" and entity.get("points") and len(entity["points"]) >= 2:
            points = entity["points"]
            for point_index in range(len(points) - 1):
                segments.append({"layer": layer, "segment": [points[point_index], points[point_index + 1]]})
            if entity.get("closed") and len(points) > 2:
                segments.append({"layer": layer, "segment": [points[-1], points[0]]})
        elif entity_type == "ARC" and entity.get(10) is not None and entity.get(40) is not None:
            start_angle = math.radians(entity.get(50, 0.0))
            end_angle = math.radians(entity.get(51, 0.0))
            if end_angle < start_angle:
                end_angle += math.pi * 2
            steps = max(2, int((end_angle - start_angle) / 0.35))
            previous = None
            for step in range(steps + 1):
                angle = start_angle + (end_angle - start_angle) * step / steps
                point = [
                    entity[10] + entity[40] * math.cos(angle),
                    entity[20] + entity[40] * math.sin(angle),
                ]
                if previous is not None:
                    segments.append({"layer": layer, "segment": [previous, point]})
                previous = point
        elif entity_type == "CIRCLE" and entity.get(10) is not None and entity.get(40) is not None:
            previous = None
            steps = 28
            for step in range(steps + 1):
                angle = step / steps * math.pi * 2
                point = [
                    entity[10] + entity[40] * math.cos(angle),
                    entity[20] + entity[40] * math.sin(angle),
                ]
                if previous is not None:
                    segments.append({"layer": layer, "segment": [previous, point]})
                previous = point
        elif entity_type == "MLINE" and entity.get("mline_points") and len(entity["mline_points"]) >= 2:
            points = entity["mline_points"]
            for point_index in range(len(points) - 1):
                segments.append({"layer": layer, "segment": [points[point_index], points[point_index + 1]]})

    while index < total:
        code, value = pairs[index]

        if code == 0:
            if not (current and current.get("type") == "POLYLINE"):
                finalize(current)

            entity_type = (value or "").strip()
            if entity_type == "VERTEX" and current and current.get("type") == "POLYLINE":
                vertex_x = None
                vertex_y = None
                probe = index + 1
                while probe < total and pairs[probe][0] != 0:
                    group_code, group_value = pairs[probe]
                    if group_code == 10:
                        vertex_x = float(group_value)
                    elif group_code == 20:
                        vertex_y = float(group_value)
                    probe += 1
                if vertex_x is not None and vertex_y is not None:
                    current.setdefault("points", [])
                    if current["points"]:
                        segments.append(
                            {
                                "layer": current.get("layer") or "0",
                                "segment": [current["points"][-1], [vertex_x, vertex_y]],
                            }
                        )
                    current["points"].append([vertex_x, vertex_y])
                index = probe
                continue
            if entity_type == "SEQEND":
                current = None
                index += 1
                continue
            if entity_type in {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "MLINE", "CIRCLE"}:
                current = {"type": entity_type, "layer": None}
            else:
                current = None
            index += 1
            continue

        if not current:
            index += 1
            continue

        entity_type = current["type"]
        if code == 8:
            current["layer"] = (value or "").strip()
        elif entity_type == "LINE":
            if code in {10, 20, 11, 21}:
                current[code] = float(value)
        elif entity_type == "LWPOLYLINE":
            if code == 70:
                current["closed"] = bool(int(value) & 1)
            elif code == 10:
                current.setdefault("points", []).append([float(value), None])
            elif code == 20 and current.get("points"):
                if current["points"][-1][1] is None:
                    current["points"][-1][1] = float(value)
        elif entity_type in {"ARC", "CIRCLE"}:
            if code in {10, 20, 40, 50, 51}:
                current[code] = float(value)
        elif entity_type == "MLINE":
            if code == 11:
                current.setdefault("_mx", []).append(float(value))
            elif code == 21 and current.get("_mx"):
                current.setdefault("mline_points", []).append([current["_mx"][-1], float(value)])

        index += 1

    finalize(current)
    return segments


def _filter_window_segments(
    raw_window_segments: list[list[list[float]]],
    wall_segments: list[list[list[float]]],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> list[list[list[float]]]:
    if not raw_window_segments or not wall_segments:
        return []

    span = max(max_x - min_x, max_y - min_y)
    bbox_padding = span * 0.04
    max_wall_distance = span * 0.03

    filtered: list[list[list[float]]] = []
    for segment in raw_window_segments:
        midpoint = _segment_midpoint(segment)
        if not (
            min_x - bbox_padding <= midpoint[0] <= max_x + bbox_padding
            and min_y - bbox_padding <= midpoint[1] <= max_y + bbox_padding
        ):
            continue

        nearest_wall = min(_distance_point_to_segment(midpoint, wall_segment) for wall_segment in wall_segments)
        if nearest_wall <= max_wall_distance:
            filtered.append(segment)

    return _dedupe_segments(filtered)


def parse_dxf_floorplan(text: str, target_span_m: float = 14.0) -> dict[str, Any] | None:
    all_segments = _parse_dxf_segments(text)
    if len(all_segments) < 2:
        return None

    layers = sorted({segment["layer"] for segment in all_segments})
    wall_layers = [layer for layer in layers if any(keyword in layer.lower() for keyword in WALL_KEYWORDS)]
    use_wall_layers = bool(wall_layers)
    window_layers = [layer for layer in layers if any(keyword in layer.lower() for keyword in WINDOW_KEYWORDS)] if use_wall_layers else []
    door_layers = [layer for layer in layers if any(keyword in layer.lower() for keyword in DOOR_KEYWORDS)] if use_wall_layers else []

    wall_segments = [
        item["segment"]
        for item in (all_segments if not use_wall_layers else [segment for segment in all_segments if segment["layer"] in wall_layers])
    ]
    wall_segments = _dedupe_segments(wall_segments)
    if len(wall_segments) < 2:
        return None

    min_x = min(point[0] for segment in wall_segments for point in segment)
    max_x = max(point[0] for segment in wall_segments for point in segment)
    min_y = min(point[1] for segment in wall_segments for point in segment)
    max_y = max(point[1] for segment in wall_segments for point in segment)

    raw_window_segments = [segment["segment"] for segment in all_segments if segment["layer"] in window_layers]
    window_segments = _filter_window_segments(raw_window_segments, wall_segments, min_x, min_y, max_x, max_y)
    floorplan_layers = set(wall_layers) | set(window_layers) | set(door_layers)
    plan_segments = _dedupe_segments(
        [
            segment["segment"]
            for segment in all_segments
            if not use_wall_layers or segment["layer"] in floorplan_layers
        ]
    )
    door_segments = _dedupe_segments([segment["segment"] for segment in all_segments if segment["layer"] in door_layers])

    extent_x = max_x - min_x
    extent_y = max_y - min_y
    span = max(extent_x, extent_y)
    if not math.isfinite(span) or span <= 0:
        return None

    estimated_scale = target_span_m / span
    width_m = extent_x * estimated_scale if extent_x > 0 else target_span_m
    depth_m = extent_y * estimated_scale if extent_y > 0 else target_span_m
    scale_x = width_m / (extent_x or 1.0)
    scale_y = depth_m / (extent_y or 1.0)

    def to_world(point: list[float]) -> dict[str, float]:
        return {
            "x": round((point[0] - min_x) * scale_x - width_m / 2, 4),
            "z": round((point[1] - min_y) * scale_y - depth_m / 2, 4),
        }

    def normalize_segments(
        segments: list[list[list[float]]],
        min_world_length: float = 0.04,
        max_world_length: float | None = None,
    ) -> list[dict[str, dict[str, float]]]:
        normalized = []
        for segment in segments:
            start = to_world(segment[0])
            end = to_world(segment[1])
            world_length = math.hypot(end["x"] - start["x"], end["z"] - start["z"])
            if world_length < min_world_length:
                continue
            if max_world_length is not None and world_length > max_world_length:
                continue
            normalized.append({"start": start, "end": end})
        return normalized

    normalized_walls = normalize_segments(wall_segments, min_world_length=0.04)
    normalized_plan = normalize_segments(plan_segments, min_world_length=0.03)
    normalized_doors = normalize_segments(door_segments, min_world_length=0.03, max_world_length=3.0)

    normalized_windows = []
    for segment in window_segments:
        start = to_world(segment[0])
        end = to_world(segment[1])
        world_length = math.hypot(end["x"] - start["x"], end["z"] - start["z"])
        if 0.18 <= world_length <= 3.2:
            normalized_windows.append({"start": start, "end": end})

    if len(normalized_walls) < 2:
        return None

    return {
        "width_cm": round(width_m * 100, 2),
        "depth_cm": round(depth_m * 100, 2),
        "wall_segments": normalized_walls,
        "plan_segments": normalized_plan,
        "door_segments": normalized_doors,
        "window_segments": normalized_windows,
        "source": "dxf",
        "wall_count": len(normalized_walls),
        "door_count": len(normalized_doors),
        "window_count": len(normalized_windows),
        "raw_segment_count": len(all_segments),
        "layers": layers,
        "wall_layers": wall_layers,
        "door_layers": door_layers,
        "window_layers": window_layers,
    }
