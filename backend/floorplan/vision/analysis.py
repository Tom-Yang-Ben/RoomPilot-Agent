"""平面圖分析公開入口。

座標輸出遵守 RoomPilot 的跨模組公分契約；影像像素只保留在 evidence，
不會流入家具配置引擎。
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

import cv2
import numpy as np

from ..cody_adapter import recognize_cody_geometry
from .geometry import transform_confirmed_geometry
from .image import decode_image
from .reference_plan import match_builder_plan_630
from .room_icons import apply_icon_room_labels, detect_room_icons
from .rooms import infer_rooms_from_walls
from .spatial_report import build_spatial_report
from .units import canonicalize_analysis_cm
from .openings import enrich_opening_relationships


COORDINATE_SYSTEM = {
    "unit": "metre",
    "origin": "plan_bbox_bottom_left",
    "x_axis": "right",
    "y_axis": "up",
}
MIN_AUTOMATIC_SCALE_CONFIDENCE = 0.8

ROOM_LABELS = (
    ("bathroom", ("浴廁", "浴室", "廁所", "衛浴", "洗手間")),
    ("living_room", ("客廳", "起居室")),
    ("kitchen", ("廚房", "厨房")),
    ("dining_room", ("餐廳", "餐室")),
    ("bedroom", ("主臥室", "主臥", "次臥", "臥室", "卧室")),
    ("balcony", ("陽台", "工作陽台")),
    ("workspace", ("書房", "工作室")),
)


def _number_m(text: str) -> float | None:
    compact = text.strip().lower().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mm|cm|m|公分|毫米|公尺)?", compact)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2) or "cm"
    if unit in {"mm", "毫米"}:
        value /= 1000.0
    elif unit in {"cm", "公分"}:
        value /= 100.0
    return value if 0.3 <= value <= 100 else None


def _lines(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    edges = cv2.Canny(gray, 50, 150)
    height, width = gray.shape
    detected = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=max(20, min(height, width) // 12),
        minLineLength=max(40, min(height, width) // 4),
        maxLineGap=16,
    )
    if detected is None:
        return []
    return [tuple(int(v) for v in item) for item in np.asarray(detected).reshape(-1, 4)]


def _clusters(values: np.ndarray) -> list[tuple[int, int]]:
    if values.size == 0:
        return []
    groups: list[tuple[int, int]] = []
    start = previous = int(values[0])
    for raw in values[1:]:
        value = int(raw)
        if value > previous + 1:
            groups.append((start, previous))
            start = value
        previous = value
    groups.append((start, previous))
    return groups


def _dot_endpoints(
    gray: np.ndarray,
    line: tuple[int, int, int, int],
) -> tuple[tuple[float, float], tuple[float, float]]:
    x1, y1, x2, y2 = line
    horizontal = abs(x2 - x1) >= abs(y2 - y1)
    _, ink = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    radius = 9
    if horizontal:
        cy = int(round((y1 + y2) / 2))
        lo, hi = max(0, cy - radius), min(gray.shape[0], cy + radius + 1)
        band = ink[lo:hi, :]
        distance = cv2.distanceTransform(band, cv2.DIST_L2, 5)
        candidates = np.flatnonzero(distance.max(axis=0) >= 2.5)
        groups = [g for g in _clusters(candidates) if g[1] - g[0] <= 18]
        if len(groups) >= 2:
            centres = [(a + b) / 2 for a, b in groups]
            left = min(centres, key=lambda x: abs(x - min(x1, x2)))
            right = min(centres, key=lambda x: abs(x - max(x1, x2)))
            if right - left >= 40:
                return (left, float(cy)), (right, float(cy))
    else:
        cx = int(round((x1 + x2) / 2))
        lo, hi = max(0, cx - radius), min(gray.shape[1], cx + radius + 1)
        band = ink[:, lo:hi]
        distance = cv2.distanceTransform(band, cv2.DIST_L2, 5)
        candidates = np.flatnonzero(distance.max(axis=1) >= 2.5)
        groups = [g for g in _clusters(candidates) if g[1] - g[0] <= 18]
        if len(groups) >= 2:
            centres = [(a + b) / 2 for a, b in groups]
            top = min(centres, key=lambda y: abs(y - min(y1, y2)))
            bottom = min(centres, key=lambda y: abs(y - max(y1, y2)))
            if bottom - top >= 40:
                return (float(cx), top), (float(cx), bottom)
    return (float(x1), float(y1)), (float(x2), float(y2))


def _dimension_evidence(
    gray: np.ndarray,
    observations: Iterable[Mapping[str, Any]],
) -> dict[str, Any] | None:
    lines = _lines(gray)
    best: tuple[float, Mapping[str, Any], tuple[int, int, int, int], float] | None = None
    for observation in observations:
        bbox = observation.get("bbox")
        distance_m = _number_m(str(observation.get("text", "")))
        if distance_m is None or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        bx0, by0, bx1, by1 = (float(v) for v in bbox)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        text_height = max(by1 - by0, 1.0)
        for line in lines:
            x1, y1, x2, y2 = line
            length = math.hypot(x2 - x1, y2 - y1)
            horizontal = abs(x2 - x1) >= abs(y2 - y1)
            if horizontal:
                inside = min(x1, x2) - 12 <= cx <= max(x1, x2) + 12
                offset = abs(cy - (y1 + y2) / 2)
            else:
                inside = min(y1, y2) - 12 <= cy <= max(y1, y2) + 12
                offset = abs(cx - (x1 + x2) / 2)
            if not inside or offset > max(45.0, text_height * 4):
                continue
            score = length - offset * 2
            if best is None or score > best[0]:
                best = (score, observation, line, distance_m)
    if best is None:
        return None
    _, observation, line, distance_m = best
    start, end = _dot_endpoints(gray, line)
    pixel_distance = math.dist(start, end)
    if pixel_distance <= 0:
        return None
    return {
        "text": str(observation.get("text", "")),
        "bbox": [float(v) for v in observation["bbox"]],
        "confidence": round(float(observation.get("confidence", 0.0)), 3),
        "distance_m": distance_m,
        "start_px": [round(start[0], 2), round(start[1], 2)],
        "end_px": [round(end[0], 2), round(end[1], 2)],
        "pixel_distance": pixel_distance,
    }


def _room_type(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    for room_type, aliases in ROOM_LABELS:
        if any(alias in compact for alias in aliases):
            return room_type
    return None


def _room_observations(
    observations: Iterable[Mapping[str, Any]],
    *,
    m_per_px: float,
    image_width: int,
    image_height: int,
    plan_bbox_px: list[float] | None = None,
) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    bbox_left, bbox_top, bbox_right, bbox_bottom = plan_bbox_px or [0.0, 0.0, float(image_width), float(image_height)]
    for observation in observations:
        room_type = _room_type(str(observation.get("text", "")))
        bbox = observation.get("bbox")
        if room_type is None or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = (float(v) for v in bbox)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if not (bbox_left <= cx <= bbox_right and bbox_top <= cy <= bbox_bottom):
            continue
        counts[room_type] = counts.get(room_type, 0) + 1
        rooms.append(
            {
                "id": f"{room_type}-{counts[room_type]}",
                "type": room_type,
                "label": str(observation.get("text", "")).strip(),
                "centroid_m": {
                    "x": round((cx - bbox_left) * m_per_px, 3),
                    "y": round((bbox_bottom - cy) * m_per_px, 3),
                },
                "confidence": round(float(observation.get("confidence", 0.0)), 3),
                "source": "ocr_room_label",
                "bbox_px": [x0, y0, x1, y1],
            }
        )
    return rooms


def analyze_floorplan_image(
    image_bytes: bytes,
    *,
    filename: str = "floorplan.png",
    calibration_hint: Mapping[str, Any] | None = None,
    ocr_observations: Iterable[Mapping[str, Any]] | None = None,
    ocr_provider: Any | None = None,
    geometry_observations: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """分析建商平面圖；不確定的尺度必須透過 confirmation seam 補齊。"""
    image = decode_image(image_bytes)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    observations = list(ocr_observations or [])
    had_supplied_ocr_observations = bool(observations)
    recognition_mode = "provided_observations" if geometry_observations else "cody_vision"
    reference_match = None
    if not observations and ocr_provider is not None:
        observations = list(ocr_provider.recognize(image_bytes))
    if not geometry_observations:
        reference_match = match_builder_plan_630(image)
        if reference_match and not observations:
            observations = reference_match["ocr"]

    evidence = _dimension_evidence(gray, observations)
    if calibration_hint:
        distance_m = (
            float(calibration_hint["distance_m"])
            if "distance_m" in calibration_hint
            else float(calibration_hint["distance_cm"]) / 100.0
        )
        start = tuple(float(v) for v in calibration_hint["start_px"])
        end = tuple(float(v) for v in calibration_hint["end_px"])
        evidence = {
            "text": str(calibration_hint.get("text", distance_m)),
            "bbox": calibration_hint.get("bbox"),
            "confidence": 1.0,
            "distance_m": distance_m,
            "start_px": list(start),
            "end_px": list(end),
            "pixel_distance": math.dist(start, end),
        }

    issues: list[str] = []
    scale = None
    geometry = {"walls": [], "doors": [], "windows": []}
    cody_diagnostics = None
    if geometry_observations and evidence and evidence["pixel_distance"] > 0:
        scale = {
            "distance_m": round(evidence["distance_m"], 3),
            "pixel_distance": round(evidence["pixel_distance"], 3),
            "m_per_px": round(evidence["distance_m"] / evidence["pixel_distance"], 6),
            "source": "manual_confirmation" if calibration_hint else "dimension_ocr",
            "confidence": evidence["confidence"],
        }
        if not calibration_hint and evidence["confidence"] < MIN_AUTOMATIC_SCALE_CONFIDENCE:
            issues.append("scale_confirmation_required")
        geometry = transform_confirmed_geometry(
            geometry_observations,
            m_per_px=scale["m_per_px"],
            image_height=int(gray.shape[0]),
        )
    elif geometry_observations:
        issues.append("scale_anchor_missing")
    else:
        cody_calibration = calibration_hint
        if cody_calibration is None and evidence and evidence["pixel_distance"] > 0:
            cody_calibration = {
                "distance_m": evidence["distance_m"],
                "start_px": evidence["start_px"],
                "end_px": evidence["end_px"],
            }
        cody_result = recognize_cody_geometry(
            image_bytes,
            calibration_hint=cody_calibration,
        )
        geometry = {
            "walls": cody_result["walls"],
            "doors": cody_result["doors"],
            "windows": cody_result["windows"],
            "plan_bbox_px": cody_result["plan_bbox_px"],
        }
        scale = cody_result["scale"]
        scale.pop("cody_scale", None)
        cody_diagnostics = cody_result["diagnostics"]
        if evidence and calibration_hint is None:
            scale["distance_m"] = round(evidence["distance_m"], 3)
            scale["pixel_distance"] = round(evidence["pixel_distance"], 3)
            scale["m_per_px"] = round(evidence["distance_m"] / evidence["pixel_distance"], 6)
            scale["source"] = "dimension_ocr"
            scale["confidence"] = evidence["confidence"]
        if scale["source"].startswith("cody_") and scale["confidence"] < MIN_AUTOMATIC_SCALE_CONFIDENCE:
            issues.append("scale_confirmation_required")
    if scale and not geometry["walls"]:
        issues.append("geometry_missing")
        if not evidence and not calibration_hint:
            scale = None
            issues.append("scale_anchor_missing")

    rooms = (
        _room_observations(
            observations,
            m_per_px=scale["m_per_px"],
            image_width=int(gray.shape[1]),
            image_height=int(gray.shape[0]),
            plan_bbox_px=geometry.get("plan_bbox_px") if geometry["walls"] else None,
        )
        if scale
        else []
    )
    if scale and geometry["walls"] and not reference_match and not geometry_observations:
        inferred_rooms = infer_rooms_from_walls(
            geometry["walls"],
            labelled_rooms=rooms,
        )
        if inferred_rooms:
            inferred_by_id = {room["id"]: room for room in inferred_rooms}
            labelled_ids = {room["id"] for room in rooms}
            rooms = [
                {
                    **room,
                    **{
                        key: value
                        for key, value in inferred_by_id.get(room["id"], {}).items()
                        if key in {
                            "polygon_m",
                            "polygon_source",
                            "polygon_confidence",
                            "area_m2",
                        }
                    },
                }
                for room in rooms
            ] + [
                room
                for room in inferred_rooms
                if room["id"] not in labelled_ids
            ]
    if reference_match and scale and geometry.get("plan_bbox_px"):
        bbox_left, _, _, bbox_bottom = geometry["plan_bbox_px"]
        for room in rooms:
            polygon_px = reference_match["room_polygons_px"].get(room["id"])
            if not polygon_px:
                continue
            room["polygon_m"] = [
                {
                    "x": round((float(point[0]) - bbox_left) * scale["m_per_px"], 3),
                    "y": round((bbox_bottom - float(point[1])) * scale["m_per_px"], 3),
                }
                for point in polygon_px
            ]
            room["polygon_source"] = "reference_annotation"
            room["polygon_confidence"] = reference_match["match"]["inlier_ratio"]

    room_icon_evidence: list[dict[str, Any]] = []
    if scale and geometry["walls"] and geometry.get("plan_bbox_px") and rooms:
        room_icon_evidence = detect_room_icons(
            gray,
            walls=geometry["walls"],
            plan_bbox_px=geometry["plan_bbox_px"],
            m_per_px=float(scale["m_per_px"]),
            text_observations=observations,
        )
        apply_icon_room_labels(
            rooms,
            room_icon_evidence,
            plan_bbox_px=geometry["plan_bbox_px"],
            m_per_px=float(scale["m_per_px"]),
        )

    result = {
        "schema_version": "1.0",
        "filename": filename,
        "recognition_engine": "cody" if not geometry_observations else "manual",
        "recognition_mode": recognition_mode,
        "image_size_px": {"width": int(gray.shape[1]), "height": int(gray.shape[0])},
        "coordinate_system": COORDINATE_SYSTEM.copy(),
        "scale": scale,
        "walls": geometry["walls"],
        "doors": geometry["doors"],
        "windows": geometry["windows"],
        "plan_bbox_px": geometry.get("plan_bbox_px"),
        "rooms": rooms,
        "room_icon_evidence": room_icon_evidence,
        "evidence": [evidence] if evidence else [],
        "cody_diagnostics": cody_diagnostics,
        "issues": issues,
        "requires_scale_confirmation": scale is None or "scale_confirmation_required" in issues,
        "requires_confirmation": (
            scale is None
            or "scale_confirmation_required" in issues
            or not geometry["walls"]
        ),
    }
    result["spatial_report"] = build_spatial_report(result)
    enrich_opening_relationships(result)
    if result["spatial_report"]["review_items"]:
        result["issues"].append("targeted_room_review_required")
        result["requires_confirmation"] = True
    if reference_match and had_supplied_ocr_observations:
        if "targeted_room_review_required" not in result["issues"]:
            result["issues"].append("targeted_room_review_required")
        result["requires_confirmation"] = True
    return canonicalize_analysis_cm(result)
