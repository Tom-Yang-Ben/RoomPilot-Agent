from __future__ import annotations

from ..contracts import ProjectSnapshot, QuantityResult, RoomQuantity


def _round(value: float) -> float:
    return round(value + 1e-12, 4)


class QuantityService:
    """只做 deterministic 幾何量計算；不呼叫 LLM 或 RAG。

    公式（房間以外接矩形表示）：
    - 地坪 = 長 × 寬；天花 = 地坪
    - 周長 = 2 × (長 + 寬)
    - 牆面毛面積 = 周長 × 高；淨面積 = 毛面積 − 開口面積
    """

    def calculate(self, snapshot: ProjectSnapshot) -> QuantityResult:
        rooms: list[RoomQuantity] = []

        for room in snapshot.rooms:
            geometry = room.geometry
            floor_area = geometry.length_m * geometry.width_m
            perimeter = 2 * (geometry.length_m + geometry.width_m)
            gross_wall_area = perimeter * geometry.height_m
            net_wall_area = max(0.0, gross_wall_area - geometry.opening_area_m2)

            rooms.append(
                RoomQuantity(
                    room_id=room.room_id,
                    floor_area_m2=_round(floor_area),
                    ceiling_area_m2=_round(floor_area),
                    perimeter_m=_round(perimeter),
                    gross_wall_area_m2=_round(gross_wall_area),
                    opening_area_m2=_round(geometry.opening_area_m2),
                    net_wall_area_m2=_round(net_wall_area),
                )
            )

        return QuantityResult(
            rooms=rooms,
            total_floor_area_m2=_round(sum(item.floor_area_m2 for item in rooms)),
            total_ceiling_area_m2=_round(sum(item.ceiling_area_m2 for item in rooms)),
            total_net_wall_area_m2=_round(
                sum(item.net_wall_area_m2 for item in rooms)
            ),
        )
