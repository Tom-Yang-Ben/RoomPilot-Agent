"""Cody 平面圖辨識核心的 RoomPilot 記憶體介面。"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import cv2
import numpy as np

from . import floorplan2dxf as cody


CONFIG_PATH = Path(__file__).with_name("config.ini")


def _decode_image(image_bytes: bytes) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    from .vision.image import profile_floorplan_image

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("floorplan_image_decode_failed")
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        return image, bgr, profile_floorplan_image(bgr)
    if image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3].astype(np.float32) / 255
        white = np.full_like(bgr, 255)
        bgr = (bgr * alpha[..., None] + white * (1 - alpha[..., None])).astype(np.uint8)
    else:
        bgr = image
    profile = profile_floorplan_image(bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if profile["kind"] == "color_line_art":
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        colored_ink = (saturation > 35) & (value < 248)
        dark_ink = gray < 215
        ink = np.where(colored_ink | dark_ink, 255, 0).astype(np.uint8)
        gray = cv2.bitwise_not(ink)
    return gray, bgr, profile


def _point(
    x_px: float,
    y_px: float,
    *,
    origin_x: float,
    bottom_y: float,
    m_per_px: float,
) -> dict[str, float]:
    return {
        "x": round((x_px - origin_x) * m_per_px, 4),
        "y": round((bottom_y - y_px) * m_per_px, 4),
    }


def _opening_segment(
    door: tuple[float, float, float, float],
    rects: list[tuple[int, int, int, int]],
) -> tuple[tuple[float, float], tuple[float, float], str]:
    cx, cy, width, _ = door
    candidates: list[tuple[float, str, float]] = []
    for x0, y0, x1, y1 in rects:
        if x1 - x0 >= y1 - y0:
            wall_y = (y0 + y1) / 2
            distance = abs(cy - wall_y) + max(x0 - cx, 0, cx - x1)
            candidates.append((distance, "horizontal", wall_y))
        else:
            wall_x = (x0 + x1) / 2
            distance = abs(cx - wall_x) + max(y0 - cy, 0, cy - y1)
            candidates.append((distance, "vertical", wall_x))
    _, orientation, constant = min(candidates, default=(0.0, "horizontal", cy))
    half = width / 2
    if orientation == "horizontal":
        return (cx - half, constant), (cx + half, constant), orientation
    return (constant, cy - half), (constant, cy + half), orientation


def _door_width_cm(door: Mapping[str, Any]) -> float:
    start, end = door.get("start") or {}, door.get("end") or {}
    fallback = math.dist(
        (float(start.get("x", 0.0)), float(start.get("y", 0.0))),
        (float(end.get("x", 0.0)), float(end.get("y", 0.0))),
    ) * 100
    return float(door.get("width_m") or 0.0) * 100 or fallback


def _door_score(door: Mapping[str, Any]) -> float:
    width = _door_width_cm(door)
    width_bonus = 12.0 if 70 <= width <= 120 else -abs(width - 90) * 0.08
    return (
        float(door.get("confidence") or 0.0) * 100
        + (16.0 if door.get("swing_end") else 0.0)
        + width_bonus
    )


def _door_axis(door: Mapping[str, Any]) -> tuple[str, float, float, float] | None:
    start = door.get("start") or {}
    end = door.get("end") or {}
    x0, y0 = float(start.get("x", 0.0)) * 100, float(start.get("y", 0.0)) * 100
    x1, y1 = float(end.get("x", 0.0)) * 100, float(end.get("y", 0.0)) * 100
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    length = math.hypot(dx, dy)
    if length < 5:
        return None
    if dx > dy * 3:
        return "horizontal", (y0 + y1) / 2, min(x0, x1), max(x0, x1)
    if dy > dx * 3:
        return "vertical", (x0 + x1) / 2, min(y0, y1), max(y0, y1)
    return None


def _doors_overlap(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    first_axis = _door_axis(first)
    second_axis = _door_axis(second)
    if not first_axis or not second_axis or first_axis[0] != second_axis[0]:
        return False
    if abs(first_axis[1] - second_axis[1]) > 35:
        return False
    overlap = max(0.0, min(first_axis[3], second_axis[3]) - max(first_axis[2], second_axis[2]))
    width = min(first_axis[3] - first_axis[2], second_axis[3] - second_axis[2])
    center_distance = abs(
        (first_axis[2] + first_axis[3]) / 2
        - (second_axis[2] + second_axis[3]) / 2
    )
    return overlap / max(1.0, width) >= 0.35 or center_distance <= max(45.0, width * 0.75)


def _clean_door_items(doors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for door in doors:
        width_cm = _door_width_cm(door)
        confidence = float(door.get("confidence") or 0.0)
        if confidence < 0.75 or not 55 <= width_cm <= 150:
            continue
        duplicate_index = next(
            (index for index, item in enumerate(cleaned) if _doors_overlap(item, door)),
            None,
        )
        if duplicate_index is None:
            cleaned.append(door)
            continue
        if _door_score(door) > _door_score(cleaned[duplicate_index]):
            cleaned[duplicate_index] = door
    return cleaned


def _axis_segment(item: Mapping[str, Any]) -> tuple[str, float, float, float] | None:
    start = item.get("start") or {}
    end = item.get("end") or {}
    x0, y0 = float(start.get("x", 0)), float(start.get("y", 0))
    x1, y1 = float(end.get("x", 0)), float(end.get("y", 0))
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    if dx >= max(0.01, dy * 3):
        return "horizontal", (y0 + y1) / 2, min(x0, x1), max(x0, x1)
    if dy >= max(0.01, dx * 3):
        return "vertical", (x0 + x1) / 2, min(y0, y1), max(y0, y1)
    return None


def _door_candidates_from_wall_gaps(
    walls: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Infer review-only door candidates from door-sized gaps between collinear walls."""
    wall_axes = [axis for wall in walls if (axis := _axis_segment(wall))]
    window_axes = [axis for window in windows if (axis := _axis_segment(window))]
    candidates: list[dict[str, Any]] = []

    for index, first in enumerate(wall_axes):
        orientation, constant, first_lo, first_hi = first
        for second in wall_axes[index + 1 :]:
            other_orientation, other_constant, second_lo, second_hi = second
            if orientation != other_orientation or abs(constant - other_constant) > 0.08:
                continue
            left, right = sorted((first, second), key=lambda axis: axis[2])
            gap_start, gap_end = left[3], right[2]
            gap_width = gap_end - gap_start
            if not 0.65 <= gap_width <= 1.35:
                continue
            gap_constant = (constant + other_constant) / 2
            overlaps_window = any(
                window_orientation == orientation
                and abs(window_constant - gap_constant) <= 0.15
                and min(gap_end, window_hi) - max(gap_start, window_lo) > 0.3
                for window_orientation, window_constant, window_lo, window_hi in window_axes
            )
            if overlaps_window:
                continue
            midpoint = (gap_start + gap_end) / 2
            if any(
                candidate["orientation"] == orientation
                and math.dist(
                    (
                        (candidate["start"]["x"] + candidate["end"]["x"]) / 2,
                        (candidate["start"]["y"] + candidate["end"]["y"]) / 2,
                    ),
                    (midpoint, gap_constant) if orientation == "horizontal" else (gap_constant, midpoint),
                ) < 0.35
                for candidate in candidates
            ):
                continue
            if orientation == "horizontal":
                start = {"x": round(gap_start, 4), "y": round(gap_constant, 4)}
                end = {"x": round(gap_end, 4), "y": round(gap_constant, 4)}
            else:
                start = {"x": round(gap_constant, 4), "y": round(gap_start, 4)}
                end = {"x": round(gap_constant, 4), "y": round(gap_end, 4)}
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "width_m": round(gap_width, 4),
                    "clearance_radius_m": round(gap_width, 4),
                    "opening_direction": "manual_review",
                    "orientation": orientation,
                    "confidence": 0.62,
                    "swing_confidence": 0.0,
                    "source": "cody_wall_gap_candidate",
                }
            )
    return candidates


def _dedupe_rects(
    rects: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    unique: list[tuple[int, int, int, int]] = []
    for rect in sorted(rects, key=lambda item: -max(item[2] - item[0], item[3] - item[1])):
        x0, y0, x1, y1 = rect
        if any(
            abs(x0 - other[0]) <= 6
            and abs(y0 - other[1]) <= 6
            and abs(x1 - other[2]) <= 6
            and abs(y1 - other[3]) <= 6
            for other in unique
        ):
            continue
        unique.append(rect)
    return unique


def _paired_wall_rects(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
    *,
    image_width: int,
    image_height: int,
) -> list[tuple[int, int, int, int]]:
    """將 Cody 中線模式的雙線牆轉成實心牆框，供 hatch 線稿使用。"""
    rects: list[tuple[int, int, int, int]] = []
    for index, (constant, start, end) in enumerate(horizontal):
        for other_constant, other_start, other_end in horizontal[index + 1 :]:
            thickness = abs(other_constant - constant)
            overlap_start = max(start, other_start)
            overlap_end = min(end, other_end)
            if 3 <= thickness <= 18 and overlap_end - overlap_start >= 30:
                rects.append(
                    (
                        int(round(overlap_start)),
                        int(round(min(constant, other_constant))),
                        int(round(overlap_end)),
                        int(round(max(constant, other_constant))),
                    )
                )
    for index, (constant, start, end) in enumerate(vertical):
        for other_constant, other_start, other_end in vertical[index + 1 :]:
            thickness = abs(other_constant - constant)
            overlap_start = max(start, other_start)
            overlap_end = min(end, other_end)
            if 3 <= thickness <= 18 and overlap_end - overlap_start >= 30:
                rects.append(
                    (
                        int(round(min(constant, other_constant))),
                        int(round(overlap_start)),
                        int(round(max(constant, other_constant))),
                        int(round(overlap_end)),
                    )
                )
    margin = 4
    return _dedupe_rects(
        [
            rect
            for rect in rects
            if rect[0] > margin
            and rect[1] > margin
            and rect[2] < image_width - margin
            and rect[3] < image_height - margin
            and not (
                rect[0] > image_width * 0.76
                and image_height * 0.35 < rect[1] < image_height * 0.78
            )
        ]
    )


def _parallel_window_boxes(
    horizontal: list[tuple[float, float, float]],
    vertical: list[tuple[float, float, float]],
) -> list[tuple[str, int, int, int, int]]:
    windows: list[tuple[str, int, int, int, int]] = []
    for orientation, segments in (("h", horizontal), ("v", vertical)):
        for constant, start, end in segments:
            if end - start < 30:
                continue
            peers = [
                item
                for item in segments
                if abs(item[1] - start) <= 10
                and abs(item[2] - end) <= 10
                and abs(item[0] - constant) <= 24
            ]
            constants = sorted({round(item[0], 1) for item in peers})
            if len(constants) < 3 or constants[-1] - constants[0] > 24:
                continue
            if orientation == "h":
                box = (
                    "h",
                    int(round(start)),
                    int(round(constants[0])),
                    int(round(end)),
                    int(round(constants[-1])),
                )
            else:
                box = (
                    "v",
                    int(round(constants[0])),
                    int(round(start)),
                    int(round(constants[-1])),
                    int(round(end)),
                )
            if not any(
                existing[0] == box[0]
                and max(abs(existing[index] - box[index]) for index in range(1, 5)) <= 10
                for existing in windows
            ):
                windows.append(box)
    return windows


def _hatch_wall_rects(
    binary: np.ndarray,
    cfg: cody.Config,
    wall_thickness_px: int,
) -> list[tuple[int, int, int, int]]:
    """把常見斜線填充牆封閉成實心區，再交回 Cody 的矩形偵測。"""
    image_height, image_width = binary.shape[:2]
    closed = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
    )
    opened = cv2.morphologyEx(
        closed,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    hatch_cfg = replace(
        cfg,
        solid=3,
        h_len=max(24, int(round(2.5 * wall_thickness_px))),
        v_len=max(24, int(round(2.5 * wall_thickness_px))),
        min_len=20.0,
    )
    candidates = cody.detect_solid(opened, hatch_cfg, wall_thickness_px)
    rects = []
    for raw in candidates:
        x0, y0, x1, y1 = (int(round(value)) for value in raw)
        width, height = x1 - x0, y1 - y0
        thickness, length = min(width, height), max(width, height)
        if not (2 <= thickness <= 18 and length >= 35 and length / max(thickness, 1) >= 3):
            continue
        if x0 <= 4 or y0 <= 4 or x1 >= image_width - 4 or y1 >= image_height - 4:
            continue
        if y1 < image_height * 0.16:
            continue
        in_right_annotation_band = (
            x0 > image_width * 0.76
            and image_height * 0.35 < y0 < image_height * 0.78
        )
        if in_right_annotation_band:
            continue
        rects.append((x0, y0, x1, y1))
    return _dedupe_rects(rects)


def recognize_cody_geometry(
    image_bytes: bytes,
    *,
    calibration_hint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """執行 origin/cody 的牆、門、窗演算法並轉成 RoomPilot 公分契約。"""
    cfg = replace(cody.load_config(str(CONFIG_PATH)))
    gray, _, image_profile = _decode_image(image_bytes)
    if cfg.deskew:
        gray, _ = cody.deskew(gray)
    binary = cody.binarize(gray, cfg)
    image_height, image_width = binary.shape[:2]
    binary, _ = cody.remove_solid_blobs(binary)

    distance = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    wall_thickness_px = max(2, int(round(2.0 * float(distance.max()))))

    def configured(value: float | int | None, fallback: float | int):
        return value if value not in (None, 0) else fallback

    cfg.solid = int(configured(cfg.solid, max(3, int(round(0.35 * wall_thickness_px)))))
    cfg.h_len = int(configured(cfg.h_len, max(int(round(1.5 * wall_thickness_px)), cfg.solid + 2)))
    cfg.v_len = int(configured(cfg.v_len, cfg.h_len))
    cfg.snap = float(configured(cfg.snap, max(3, int(round(0.6 * wall_thickness_px)))))
    cfg.gap = float(configured(cfg.gap, max(3, int(round(0.4 * wall_thickness_px)))))
    cfg.min_len = float(configured(cfg.min_len, max(int(round(wall_thickness_px)), 4)))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg.solid, cfg.solid))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    rects = cody.detect_solid(opened, cfg, wall_thickness_px)
    thin = cv2.subtract(binary, cv2.dilate(opened, np.ones((3, 3), np.uint8)))
    doors = cody.detect_doors(thin, wall_thickness_px, cfg.door_arc_pct)
    window_rects = rects
    window_thin = thin
    window_cfg = cfg
    detection_mode = "solid"
    horizontal: list[tuple[float, float, float]] = []
    vertical: list[tuple[float, float, float]] = []
    if len(rects) < 5:
        line_thickness = min(
            wall_thickness_px,
            max(6, int(min(image_width, image_height) * 0.012)),
        )
        line_cfg = replace(
            cfg,
            style="center",
            solid=max(3, int(round(0.35 * line_thickness))),
            h_len=max(24, int(round(2.5 * line_thickness))),
            v_len=max(24, int(round(2.5 * line_thickness))),
            snap=float(max(3, int(round(0.6 * line_thickness)))),
            gap=float(max(3, int(round(0.4 * line_thickness)))),
            min_len=float(max(20, int(round(2.0 * line_thickness)))),
        )
        horizontal, vertical = cody.detect_morph(binary, line_cfg)
        horizontal, vertical = cody.postprocess(horizontal, vertical, line_cfg)
        line_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (line_cfg.solid, line_cfg.solid),
        )
        line_opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, line_kernel)
        window_cfg = replace(
            line_cfg,
            h_len=max(12, int(round(1.5 * line_thickness))),
            v_len=max(12, int(round(1.5 * line_thickness))),
            min_len=float(max(8, line_thickness)),
        )
        window_rects = cody.detect_solid(line_opened, window_cfg, line_thickness)
        window_thin = cv2.subtract(
            binary,
            cv2.dilate(line_opened, np.ones((3, 3), np.uint8)),
        )
        hatch_rects = _hatch_wall_rects(binary, line_cfg, line_thickness)
        paired_rects = _paired_wall_rects(
            horizontal,
            vertical,
            image_width=image_width,
            image_height=image_height,
        )
        rects = paired_rects or hatch_rects
        wall_thickness_px = line_thickness
        cfg = line_cfg
        detection_mode = "paired_centerlines" if paired_rects else "hatch_normalized"

    threshold_mode = cv2.THRESH_BINARY if cfg.invert else cv2.THRESH_BINARY_INV
    _, door_ink = cv2.threshold(gray, 245, 255, threshold_mode)
    door_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (max(3, int(cfg.solid)), max(3, int(cfg.solid))),
    )
    door_walls = cv2.morphologyEx(door_ink, cv2.MORPH_OPEN, door_kernel)
    door_thin = cv2.subtract(
        door_ink,
        cv2.dilate(door_walls, np.ones((3, 3), np.uint8)),
    )
    door_roi = None
    if rects:
        door_roi = (
            min(rect[0] for rect in rects),
            min(rect[1] for rect in rects),
            max(rect[2] for rect in rects),
            max(rect[3] for rect in rects),
        )
    swing_doors = cody.detect_door_swing_arcs(
        door_thin,
        wall_thickness_px,
        cfg.door_arc_pct,
        roi=door_roi,
    )

    def hinge_wall_distance(door) -> float:
        cx, cy = float(door[0]), float(door[1])
        distances = []
        for x0, y0, x1, y1 in rects:
            dx = max(float(x0) - cx, 0.0, cx - float(x1))
            dy = max(float(y0) - cy, 0.0, cy - float(y1))
            distances.append(math.hypot(dx, dy))
        return min(distances, default=math.inf)

    swing_doors = [
        door
        for door in swing_doors
        if float(door[3]) >= 0.85
        and hinge_wall_distance(door) <= 1.25 * wall_thickness_px
    ]
    if not doors:
        doors = swing_doors
    elif swing_doors:
        matched_legacy = sum(
            any(
                math.hypot(float(door[0]) - float(swing[0]), float(door[1]) - float(swing[1]))
                <= 1.5 * wall_thickness_px
                for swing in swing_doors
            )
            for door in doors
        )
        if matched_legacy >= max(1, math.ceil(0.6 * len(doors))):
            merged_doors = [*swing_doors, *doors]
            doors = []
            for door in sorted(merged_doors, key=lambda item: (-len(item), -item[3])):
                if not any(
                    math.hypot(float(door[0]) - float(item[0]), float(door[1]) - float(item[1]))
                    < wall_thickness_px
                    for item in doors
                ):
                    doors.append(door)
    if cfg.invert:
        soft = binary
    else:
        _, soft = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    windows = cody.detect_windows(
        binary,
        window_rects,
        window_cfg,
        wall_thickness_px,
        doors,
        window_thin,
        soft,
    )
    if not windows and horizontal and vertical:
        windows = _parallel_window_boxes(horizontal, vertical)

    outer_px = cody.outer_wall_thickness(rects, wall_thickness_px)
    auto_mm_per_px, scale_info = cody.derive_door_scale(doors, outer_px, cfg)
    if calibration_hint:
        start = tuple(float(value) for value in calibration_hint["start_px"])
        end = tuple(float(value) for value in calibration_hint["end_px"])
        distance_m = (
            float(calibration_hint["distance_m"])
            if "distance_m" in calibration_hint
            else float(calibration_hint["distance_cm"]) / 100
        )
        pixel_distance = math.dist(start, end)
        if pixel_distance <= 0:
            raise ValueError("calibration_points_must_be_distinct")
        m_per_px = distance_m / pixel_distance
        scale_source = "manual_confirmation"
        scale_confidence = 1.0
    else:
        m_per_px = auto_mm_per_px / 1000
        distance_m = image_width * m_per_px
        pixel_distance = float(image_width)
        scale_source = f"cody_{scale_info['method']}"
        scale_confidence = 0.9 if scale_info["confidence"] == "high" else 0.7

    if rects:
        origin_x = float(min(rect[0] for rect in rects))
        top_y = float(min(rect[1] for rect in rects))
        right_x = float(max(rect[2] for rect in rects))
        bottom_y = float(max(rect[3] for rect in rects))
    else:
        origin_x, top_y, right_x, bottom_y = 0.0, 0.0, float(image_width), float(image_height)

    walls = []
    for x0, y0, x1, y1 in rects:
        horizontal = x1 - x0 >= y1 - y0
        if horizontal:
            centre = (y0 + y1) / 2
            start_px, end_px = (x0, centre), (x1, centre)
        else:
            centre = (x0 + x1) / 2
            start_px, end_px = (centre, y0), (centre, y1)
        walls.append(
            {
                "start": _point(*start_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px),
                "end": _point(*end_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px),
                "thickness_m": round(min(x1 - x0, y1 - y0) * m_per_px, 4),
                "confidence": 0.9,
                "source": "cody_vision",
                "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
            }
        )

    window_items = []
    for orientation, x0, y0, x1, y1 in windows:
        if orientation == "h":
            centre = (y0 + y1) / 2
            start_px, end_px = (x0, centre), (x1, centre)
        else:
            centre = (x0 + x1) / 2
            start_px, end_px = (centre, y0), (centre, y1)
        start = _point(*start_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px)
        end = _point(*end_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px)
        window_items.append(
            {
                "start": start,
                "end": end,
                "width_m": round(math.dist((start["x"], start["y"]), (end["x"], end["y"])), 4),
                "confidence": 0.9,
                "source": "cody_vision",
                "bbox_px": [int(x0), int(y0), int(x1), int(y1)],
            }
        )

    door_items = []
    for door in doors:
        raw_width_m = float(door[2]) * m_per_px
        display_width_px = (
            float(door[2]) if 0.65 <= raw_width_m <= 1.35 else 0.9 / m_per_px
        )
        display_door = (float(door[0]), float(door[1]), display_width_px, float(door[3]))
        swing_end_px = None
        if len(door) >= 8:
            start_px = (float(door[0]), float(door[1]))
            end_px = (
                float(door[0]) + float(door[4]) * display_width_px,
                float(door[1]) + float(door[5]) * display_width_px,
            )
            swing_end_px = (
                float(door[0]) + float(door[6]) * display_width_px,
                float(door[1]) + float(door[7]) * display_width_px,
            )
            orientation = (
                "horizontal"
                if abs(float(door[4])) >= abs(float(door[5]))
                else "vertical"
            )
        else:
            start_px, end_px, orientation = _opening_segment(display_door, rects)
        start = _point(*start_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px)
        end = _point(*end_px, origin_x=origin_x, bottom_y=bottom_y, m_per_px=m_per_px)
        width_m = math.dist((start["x"], start["y"]), (end["x"], end["y"]))
        door_item = {
            "start": start,
            "end": end,
            "width_m": round(width_m, 4),
            "clearance_radius_m": round(width_m, 4),
            "opening_direction": "manual_review",
            "orientation": orientation,
            "confidence": round(float(door[3]), 3),
            "swing_confidence": round(float(door[3]), 3),
            "source": "cody_vision",
            "hinge_px": [round(float(door[0]), 2), round(float(door[1]), 2)],
        }
        if swing_end_px is not None:
            door_item["swing_end"] = _point(
                *swing_end_px,
                origin_x=origin_x,
                bottom_y=bottom_y,
                m_per_px=m_per_px,
            )
        door_items.append(door_item)
    door_items = _clean_door_items(door_items)
    if not door_items and window_items:
        door_items = _door_candidates_from_wall_gaps(walls, window_items)

    return {
        "walls": walls,
        "doors": door_items,
        "windows": window_items,
        "plan_bbox_px": [origin_x, top_y, right_x, bottom_y],
        "scale": {
            "distance_m": round(distance_m, 4),
            "pixel_distance": round(pixel_distance, 3),
            "m_per_px": round(m_per_px, 8),
            "source": scale_source,
            "confidence": scale_confidence,
            "cody_scale": scale_info,
        },
        "diagnostics": {
            "detection_mode": detection_mode,
            "wall_thickness_px": wall_thickness_px,
            "outer_wall_thickness_px": round(float(outer_px), 2),
            "wall_count": len(walls),
            "door_count": len(door_items),
            "window_count": len(window_items),
            "image_profile": image_profile,
        },
    }
