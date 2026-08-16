"""Confirmed pixel geometry to RoomPilot metre coordinates."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


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
    bottom_y = max(
        (float(point[1]) for point in wall_points), default=float(image_height)
    )
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
            item["width_m"] = round(
                math.dist((start["x"], start["y"]), (end["x"], end["y"])),
                3,
            )
        if kind == "door":
            item["opening_direction"] = str(
                observation.get("opening_direction") or "unknown"
            )
            item["swing_confidence"] = round(
                float(observation.get("swing_confidence", 0.0)), 3
            )
            item["clearance_radius_m"] = item["width_m"]
            if observation.get("room_ids"):
                item["room_ids"] = [str(value) for value in observation["room_ids"]]
        result[target].append(item)
    return result
