from __future__ import annotations

import math

from .models import ProjectSnapshot, QuantityResult, RoomQuantity


def _round(value: float) -> float:
    return round(value + 1e-12, 4)


def _polygon_area_perimeter_cm(points) -> tuple[float, float]:
    area_twice = 0.0
    perimeter = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        area_twice += current.x_cm * following.y_cm - following.x_cm * current.y_cm
        perimeter += math.hypot(
            following.x_cm - current.x_cm,
            following.y_cm - current.y_cm,
        )
    return abs(area_twice) / 2.0, perimeter


class QuantityService:
    """Deterministic centimeter geometry only; never calls an LLM."""

    def calculate(self, snapshot: ProjectSnapshot) -> QuantityResult:
        rooms: list[RoomQuantity] = []
        for room in snapshot.rooms:
            geometry = room.geometry
            if geometry.polygon_cm:
                area_cm2, perimeter_cm = _polygon_area_perimeter_cm(
                    geometry.polygon_cm
                )
                geometry_source = "polygon_cm"
            else:
                area_cm2 = geometry.length_cm * geometry.width_cm
                perimeter_cm = 2 * (geometry.length_cm + geometry.width_cm)
                geometry_source = "rectangle_cm"

            floor_area_m2 = area_cm2 / 10_000
            perimeter_m = perimeter_cm / 100
            height_m = geometry.height_cm / 100
            gross_wall_area_m2 = perimeter_m * height_m
            opening_area_m2 = min(geometry.opening_area_m2, gross_wall_area_m2)
            net_wall_area_m2 = max(0.0, gross_wall_area_m2 - opening_area_m2)
            rooms.append(
                RoomQuantity(
                    room_id=room.room_id,
                    length_cm=_round(geometry.length_cm),
                    width_cm=_round(geometry.width_cm),
                    height_cm=_round(geometry.height_cm),
                    floor_area_m2=_round(floor_area_m2),
                    ceiling_area_m2=_round(floor_area_m2),
                    perimeter_m=_round(perimeter_m),
                    gross_wall_area_m2=_round(gross_wall_area_m2),
                    opening_area_m2=_round(opening_area_m2),
                    net_wall_area_m2=_round(net_wall_area_m2),
                    geometry_source=geometry_source,
                )
            )

        return QuantityResult(
            rooms=rooms,
            total_floor_area_m2=_round(sum(item.floor_area_m2 for item in rooms)),
            total_ceiling_area_m2=_round(
                sum(item.ceiling_area_m2 for item in rooms)
            ),
            total_net_wall_area_m2=_round(
                sum(item.net_wall_area_m2 for item in rooms)
            ),
        )

