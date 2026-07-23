"""Centimeter contract adapters for floor-plan recognition payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def _point_cm(point: Mapping[str, Any], scale: float) -> dict[str, float]:
    y_value = point["y"] if "y" in point else point.get("z", 0)
    return {
        "x": round(float(point.get("x", 0)) * scale, 2),
        "y": round(float(y_value) * scale, 2),
    }


def _polygon_cm(points: list[Mapping[str, Any]], scale: float) -> list[dict[str, float]]:
    return [_point_cm(point, scale) for point in points]


def _dimensions_cm(value: Mapping[str, Any] | None, scale: float) -> dict[str, float] | None:
    if not value:
        return None
    return {
        key: round(float(item) * scale, 2)
        for key, item in value.items()
    }


def canonicalize_analysis_cm(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Return one canonical centimeter payload without mutating the source."""
    result = deepcopy(dict(analysis))
    coordinate_system = dict(result.get("coordinate_system") or {})
    scale = dict(result.get("scale") or {})
    already_cm = (
        coordinate_system.get("unit") in {"centimeter", "centimetre", "cm"}
        or "cm_per_px" in scale
        or any("polygon_cm" in room for room in result.get("rooms") or [])
    )
    scale_factor = 1.0 if already_cm else 100.0
    coordinate_system["unit"] = "centimeter"
    result["coordinate_system"] = coordinate_system

    if scale:
        if "distance_cm" not in scale and "distance_m" in scale:
            scale["distance_cm"] = round(float(scale["distance_m"]) * 100, 2)
        if "cm_per_px" not in scale and "m_per_px" in scale:
            scale["cm_per_px"] = round(float(scale["m_per_px"]) * 100, 8)
        scale.pop("distance_m", None)
        scale.pop("m_per_px", None)
        result["scale"] = scale

    for evidence in result.get("evidence") or []:
        if "distance_cm" not in evidence and "distance_m" in evidence:
            evidence["distance_cm"] = round(float(evidence["distance_m"]) * 100, 2)
        evidence.pop("distance_m", None)

    for key in ("walls", "doors", "windows"):
        for item in result.get(key) or []:
            if isinstance(item.get("start"), Mapping):
                item["start"] = _point_cm(item["start"], scale_factor)
            if isinstance(item.get("end"), Mapping):
                item["end"] = _point_cm(item["end"], scale_factor)
            if isinstance(item.get("swing_end"), Mapping):
                item["swing_end"] = _point_cm(item["swing_end"], scale_factor)
            for cm_key, meter_key in (
                ("width_cm", "width_m"),
                ("thickness_cm", "thickness_m"),
                ("clearance_radius_cm", "clearance_radius_m"),
            ):
                if cm_key not in item and meter_key in item:
                    item[cm_key] = round(float(item[meter_key]) * 100, 2)
                item.pop(meter_key, None)

    for room in result.get("rooms") or []:
        if "centroid_cm" not in room and isinstance(room.get("centroid_m"), Mapping):
            room["centroid_cm"] = _point_cm(room["centroid_m"], 100)
        room.pop("centroid_m", None)
        if "polygon_cm" not in room and room.get("polygon_m"):
            room["polygon_cm"] = _polygon_cm(room["polygon_m"], 100)
        room.pop("polygon_m", None)

    report = result.get("spatial_report")
    if isinstance(report, dict):
        report["unit"] = "centimeter"
        for room in report.get("rooms") or []:
            if "polygon_cm" not in room and room.get("polygon_m"):
                room["polygon_cm"] = _polygon_cm(room["polygon_m"], 100)
            room.pop("polygon_m", None)
            for cm_key, meter_key in (
                ("inner_dimensions_cm", "inner_dimensions_m"),
                ("bounding_dimensions_cm", "bounding_dimensions_m"),
                ("maximum_usable_rectangle_cm", "maximum_usable_rectangle_m"),
            ):
                if cm_key not in room:
                    room[cm_key] = _dimensions_cm(room.get(meter_key), 100)
                room.pop(meter_key, None)
            if "wall_lengths_cm" not in room and room.get("wall_lengths_m") is not None:
                room["wall_lengths_cm"] = [
                    round(float(length) * 100, 2)
                    for length in room["wall_lengths_m"]
                ]
            room.pop("wall_lengths_m", None)
            if "minimum_clear_width_cm" not in room and room.get("minimum_clear_width_m") is not None:
                room["minimum_clear_width_cm"] = round(
                    float(room["minimum_clear_width_m"]) * 100,
                    2,
                )
            room.pop("minimum_clear_width_m", None)
    return result
