"""人工確認閘門與 DXF／引擎 payload 邊界。"""

from __future__ import annotations

import io
from copy import deepcopy
from typing import Any, Mapping

import ezdxf

from ...upgrade3d.dxf_parser import parse_dxf_bytes
from .requirements import infer_room_requirements
from .spatial_report import build_spatial_report


def _dxf_text(analysis: Mapping[str, Any]) -> str:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # millimetres
    modelspace = doc.modelspace()
    for layer, color in (("WALL", 7), ("DOOR", 1), ("WINDOW", 5)):
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)

    for key, layer in (("walls", "WALL"), ("doors", "DOOR"), ("windows", "WINDOW")):
        for item in analysis.get(key, []):
            start, end = item.get("start", {}), item.get("end", {})
            try:
                p1 = (float(start["x"]) * 1000, float(start["y"]) * 1000)
                p2 = (float(end["x"]) * 1000, float(end["y"]) * 1000)
            except (KeyError, TypeError, ValueError):
                continue
            if p1 != p2:
                modelspace.add_line(p1, p2, dxfattribs={"layer": layer})
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def confirm_floorplan_analysis(
    analysis: Mapping[str, Any],
    corrections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """套用使用者修正並產生可進入 RoomPilot 引擎的唯一確認版本。"""
    confirmed = deepcopy(dict(analysis))
    correction_values = dict(corrections or {})
    auto_geometry = "geometry_confirmation_required" in confirmed.get("issues", []) or any(
        item.get("source") == "opencv_geometry"
        for key in ("walls", "doors", "windows")
        for item in confirmed.get(key, [])
    )
    if auto_geometry and not all(key in correction_values for key in ("walls", "doors", "windows")):
        raise ValueError("geometry_confirmation_required")
    for key, value in correction_values.items():
        if key in {"scale", "walls", "doors", "windows", "rooms"}:
            confirmed[key] = deepcopy(value)
            if key == "scale":
                confirmed[key]["source"] = "manual_confirmation"
                confirmed[key]["confidence"] = 1.0
            if key in {"walls", "doors", "windows"}:
                for item in confirmed[key]:
                    item["source"] = "confirmed_geometry"
                    item["confidence"] = 1.0
    if not confirmed.get("scale"):
        raise ValueError("scale_confirmation_required")
    scale = confirmed["scale"]
    try:
        valid_scale = float(scale["distance_m"]) > 0 and float(scale["m_per_px"]) > 0
        trusted_scale = scale.get("source") == "manual_confirmation" or (
            scale.get("source") == "dimension_ocr" and float(scale.get("confidence", 0)) >= 0.8
        )
    except (KeyError, TypeError, ValueError):
        valid_scale = trusted_scale = False
    if not valid_scale or not trusted_scale or (
        "scale_confirmation_required" in confirmed.get("issues", []) and "scale" not in correction_values
    ):
        raise ValueError("scale_confirmation_required")
    if not confirmed.get("walls"):
        raise ValueError("wall_confirmation_required")

    confirmed["spatial_report"] = build_spatial_report(confirmed)
    if confirmed["spatial_report"]["review_items"]:
        raise ValueError("targeted_room_review_required")

    confirmed["confirmation_status"] = "confirmed"
    confirmed["requires_confirmation"] = False
    confirmed["requires_scale_confirmation"] = False
    confirmed["issues"] = [
        issue
        for issue in confirmed.get("issues", [])
        if issue not in {
            "geometry_confirmation_required",
            "geometry_missing",
            "scale_anchor_missing",
            "scale_confirmation_required",
        }
    ]
    dxf_text = _dxf_text(confirmed)
    floorplan = parse_dxf_bytes(dxf_text.encode("utf-8"), "confirmed-floorplan.dxf")
    width_m = float(floorplan.get("width_cm", 0.0)) / 100
    depth_m = float(floorplan.get("depth_cm", 0.0)) / 100
    floorplan["room_regions"] = []
    for room in confirmed["spatial_report"]["rooms"]:
        region = deepcopy(room)
        region["exterior"] = [
            [round(float(point["x"]) - width_m / 2, 4), round(float(point["y"]) - depth_m / 2, 4)]
            for point in room.get("polygon_m") or []
        ]
        region["holes"] = []
        floorplan["room_regions"].append(region)
    floorplan["recognition_report"] = {
        "room_counts": deepcopy(confirmed["spatial_report"]["room_counts"]),
        "measurement_basis": confirmed["spatial_report"]["measurement_basis"],
        "coordinate_system": deepcopy(confirmed.get("coordinate_system")),
    }
    requirements = infer_room_requirements(confirmed, confirmed.get("requirement_brief"))
    return {
        "schema_version": "1.0",
        "ready_for_design": True,
        "analysis": confirmed,
        "requirements": requirements,
        "dxf_text": dxf_text,
        "floorplan": floorplan,
    }
