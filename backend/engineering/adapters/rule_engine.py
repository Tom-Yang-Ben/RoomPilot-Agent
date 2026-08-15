"""ExistingRuleEngineAdapter：把鎖定 Snapshot 交給既有 backend.engine 檢查。

既有引擎（shapely）提供：出界、家具重疊、穿牆、開合淨空衝突。
本 Adapter 只轉換資料格式，不重寫演算法；引擎沒有覆蓋的檢查
（門片/走道/窗簾等）不在此假造，缺項會在 RuleService 標示為 MVP 範圍外。

座標約定（與 backend.engine 一致）：
- 單位 cm；x_cm / y_cm 為家具中心點；rotation 逆時針角度。
- 房間以外接矩形 (0,0)-(width, depth) 表示；width=length_m*100、depth=width_m*100。
"""
from __future__ import annotations

from uuid import uuid4

from ...engine.clearance import check_placement_with_clearance
from ...engine.models import FurnitureCatalogItem, PlacedFurniture, Room
from ..contracts import ProjectSnapshot, RiskItem


# 依家具類別給的開合淨空需求（cm）；資料源自既有引擎 ClearanceZone 概念。
_CLEARANCE_BY_CATEGORY = {
    "wardrobe": 60.0,
    "refrigerator": 60.0,
    "storage-cabinet": 50.0,
    "appliance-cabinet": 50.0,
    "dresser": 50.0,
}


def _clearance_for(category: str):
    from ...engine.models import ClearanceZone

    depth = _CLEARANCE_BY_CATEGORY.get(category.strip().lower())
    if depth is None:
        return None
    return ClearanceZone(side="front", depth=depth)


class ExistingRuleEngineAdapter:
    """以既有 Geometry / Clearance Engine 驗證鎖定 Snapshot 的家具配置。"""

    engine_name = "backend.engine (shapely geometry + clearance)"

    def validate_rooms(self, snapshot: ProjectSnapshot) -> list[RiskItem]:
        results: list[RiskItem] = []
        for room in snapshot.rooms:
            engine_room = Room(
                width=room.geometry.length_m * 100,
                depth=room.geometry.width_m * 100,
                walls=[],
            )
            placed: list[PlacedFurniture] = []
            for item in room.furniture:
                placed.append(
                    PlacedFurniture(
                        id=item.furniture_id,
                        catalog=FurnitureCatalogItem(
                            type=item.category,
                            name=item.name,
                            width=item.width_cm,
                            depth=item.depth_cm,
                            height=item.height_cm,
                            clearance=_clearance_for(item.category),
                        ),
                        pos_x=item.x_cm,
                        pos_y=item.y_cm,
                        rotation=item.rotation_deg,
                    )
                )

            for item in placed:
                others = [other for other in placed if other.id != item.id]
                reason = check_placement_with_clearance(item, engine_room, others)
                passed = reason is None
                results.append(
                    RiskItem(
                        id=f"risk_{uuid4().hex[:10]}",
                        room_id=room.room_id,
                        rule="engine_placement_check",
                        severity="low" if passed else "high",
                        passed=passed,
                        message=(
                            f"{item.catalog.name}：{reason}"
                            if reason
                            else f"{item.catalog.name} 通過既有引擎的邊界／重疊／淨空檢查"
                        ),
                        related_items=[item.id],
                    )
                )
        return results
