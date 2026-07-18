"""像素幾何到 RoomPilot 公尺座標的可信邊界。"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import cv2
import numpy as np


def transform_confirmed_geometry(
    observations: Iterable[Mapping[str, Any]],
    *,
    m_per_px: float,
    image_height: int,
    source: str = "confirmed_geometry",
) -> dict[str, Any]:
    result: dict[str, Any] = {"walls": [], "doors": [], "windows": []}
    names = {"wall": "walls", "door": "doors", "window": "windows"}

    buffered = list(observations)
    wall_points = [
        point
        for item in buffered
        if item.get("kind") == "wall"
        for key in ("start_px", "end_px")
        for point in [item.get(key)]
        if isinstance(point, (list, tuple)) and len(point) == 2
    ]
    origin_x = min((float(point[0]) for point in wall_points), default=0.0)
    right_x = max((float(point[0]) for point in wall_points), default=0.0)
    top_y = min((float(point[1]) for point in wall_points), default=0.0)
    bottom_y = max((float(point[1]) for point in wall_points), default=float(image_height))
    result["plan_bbox_px"] = [origin_x, top_y, right_x, bottom_y]

    def point(raw: Any) -> dict[str, float]:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError("geometry_point_must_be_xy_pair")
        x, y = (float(value) for value in raw)
        return {
            "x": round((x - origin_x) * m_per_px, 3),
            "y": round((bottom_y - y) * m_per_px, 3),
        }

    for observation in buffered:
        kind = str(observation.get("kind", ""))
        target = names.get(kind)
        if target is None:
            continue
        start = point(observation.get("start_px"))
        end = point(observation.get("end_px"))
        item = {
            "start": start,
            "end": end,
            "confidence": round(float(observation.get("confidence", 1.0)), 3),
            "source": source,
        }
        if kind in {"door", "window"}:
            item["width_m"] = round(math.dist((start["x"], start["y"]), (end["x"], end["y"])), 3)
        if kind == "door":
            item["opening_direction"] = str(observation.get("opening_direction") or "unknown")
            item["swing_confidence"] = round(float(observation.get("swing_confidence", 0.0)), 3)
            item["clearance_radius_m"] = item["width_m"]
            if observation.get("room_ids"):
                item["room_ids"] = [str(value) for value in observation["room_ids"]]
        result[target].append(item)
    return result


def _hough_segments(gray: np.ndarray) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 20, minLineLength=25, maxLineGap=8)
    horizontal: list[tuple[float, float, float]] = []
    vertical: list[tuple[float, float, float]] = []
    if lines is None:
        return horizontal, vertical
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        angle = abs(math.degrees(math.atan2(float(y2 - y1), float(x2 - x1))))
        if angle < 8 or angle > 172:
            horizontal.append(((float(y1) + float(y2)) / 2, float(min(x1, x2)), float(max(x1, x2))))
        elif 82 < angle < 98:
            vertical.append(((float(x1) + float(x2)) / 2, float(min(y1, y2)), float(max(y1, y2))))
    return horizontal, vertical


def _overlap(a0: float, a1: float, b0: float, b1: float) -> tuple[float, float]:
    return max(a0, b0), min(a1, b1)


def _dedupe(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    for item in sorted(observations, key=lambda value: -math.dist(value["start_px"], value["end_px"])):
        sx, sy = item["start_px"]
        ex, ey = item["end_px"]
        if any(
            math.dist((sx, sy), other["start_px"]) < 8
            and math.dist((ex, ey), other["end_px"]) < 8
            for other in unique
        ):
            continue
        unique.append(item)
    return unique


def _wall_observations(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
) -> list[dict[str, Any]]:
    walls: list[dict[str, Any]] = []
    for index, (constant, start, end) in enumerate(horizontal):
        for other_constant, other_start, other_end in horizontal[index + 1 :]:
            separation = abs(other_constant - constant)
            overlap_start, overlap_end = _overlap(start, end, other_start, other_end)
            if 4 <= separation <= 20 and overlap_end - overlap_start >= 30:
                centre = (constant + other_constant) / 2
                walls.append({"kind": "wall", "start_px": [overlap_start, centre], "end_px": [overlap_end, centre], "confidence": 0.82})
    for index, (constant, start, end) in enumerate(vertical):
        for other_constant, other_start, other_end in vertical[index + 1 :]:
            separation = abs(other_constant - constant)
            overlap_start, overlap_end = _overlap(start, end, other_start, other_end)
            if 4 <= separation <= 20 and overlap_end - overlap_start >= 30:
                centre = (constant + other_constant) / 2
                walls.append({"kind": "wall", "start_px": [centre, overlap_start], "end_px": [centre, overlap_end], "confidence": 0.82})
    return _dedupe(walls)


def _window_observations(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    m_per_px: float,
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for orientation, segments in (("h", horizontal), ("v", vertical)):
        for constant, start, end in segments:
            peers = [
                candidate
                for candidate in segments
                if abs(candidate[1] - start) <= 8
                and abs(candidate[2] - end) <= 8
                and abs(candidate[0] - constant) <= 20
            ]
            constants = {round(candidate[0], 1) for candidate in peers}
            width_m = (end - start) * m_per_px
            thickness_m = (max(constants) - min(constants)) * m_per_px if constants else 0
            if len(constants) < 3 or not (0.3 <= width_m <= 3.0) or thickness_m > 0.35:
                continue
            centre = sum(constants) / len(constants)
            start_px = [start, centre] if orientation == "h" else [centre, start]
            end_px = [end, centre] if orientation == "h" else [centre, end]
            windows.append({"kind": "window", "start_px": start_px, "end_px": end_px, "confidence": 0.78})
    return _dedupe(windows)


def _arc_score(ink: np.ndarray, hinge: tuple[float, float], h_free: tuple[float, float], v_free: tuple[float, float]) -> float:
    cx, cy = hinge
    radius = (math.dist(hinge, h_free) + math.dist(hinge, v_free)) / 2
    h_angle = math.atan2(h_free[1] - cy, h_free[0] - cx)
    v_angle = math.atan2(v_free[1] - cy, v_free[0] - cx)
    delta = (v_angle - h_angle) % (2 * math.pi)
    if delta > math.pi:
        delta -= 2 * math.pi
    hits = 0
    samples = 31
    for step in range(samples):
        angle = h_angle + delta * step / (samples - 1)
        x = int(round(cx + radius * math.cos(angle)))
        y = int(round(cy + radius * math.sin(angle)))
        x0, x1 = max(0, x - 2), min(ink.shape[1], x + 3)
        y0, y1 = max(0, y - 2), min(ink.shape[0], y + 3)
        hits += int(bool(np.any(ink[y0:y1, x0:x1])))
    return hits / samples


def _door_observations(
    gray: np.ndarray,
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    m_per_px: float,
) -> list[dict[str, Any]]:
    _, ink = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    doors: list[dict[str, Any]] = []
    for hy, hx0, hx1 in horizontal:
        h_length = hx1 - hx0
        for vx, vy0, vy1 in vertical:
            v_length = vy1 - vy0
            width_m = (h_length + v_length) / 2 * m_per_px
            if not (0.45 <= width_m <= 1.5) or abs(h_length - v_length) > 0.25 * max(h_length, v_length):
                continue
            for hx in (hx0, hx1):
                for vy in (vy0, vy1):
                    if abs(hx - vx) > 5 or abs(hy - vy) > 5:
                        continue
                    hinge = ((hx + vx) / 2, (hy + vy) / 2)
                    h_free = (hx1 if hx == hx0 else hx0, hy)
                    v_free = (vx, vy1 if vy == vy0 else vy0)
                    score = _arc_score(ink, hinge, h_free, v_free)
                    if score >= 0.45:
                        doors.append({"kind": "door", "start_px": list(hinge), "end_px": list(h_free), "confidence": round(score, 3)})
    return _dedupe(doors)


def detect_geometry(
    image: np.ndarray,
    *,
    m_per_px: float,
    text_boxes: Iterable[Any] = (),
    dimension_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    masked = gray.copy()
    for raw in text_boxes:
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            x0, y0, x1, y1 = (int(round(float(value))) for value in raw)
            cv2.rectangle(masked, (x0 - 3, y0 - 3), (x1 + 3, y1 + 3), 255, -1)
    if dimension_evidence:
        start = tuple(int(round(value)) for value in dimension_evidence["start_px"])
        end = tuple(int(round(value)) for value in dimension_evidence["end_px"])
        cv2.line(masked, start, end, 255, 12)

    horizontal, vertical = _hough_segments(masked)
    observations = (
        _wall_observations(horizontal, vertical)
        + _door_observations(masked, horizontal, vertical, m_per_px)
        + _window_observations(horizontal, vertical, m_per_px)
    )
    return transform_confirmed_geometry(
        observations,
        m_per_px=m_per_px,
        image_height=image.shape[0],
        source="opencv_geometry",
    )
