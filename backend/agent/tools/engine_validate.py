"""硬規則驗證 tool：把場景丟回 engine 重新檢查合法性。

Validation Agent 的「硬規則軌」：碰撞、淨空、超界全部呼叫
``backend.engine.clearance.check_placement_with_clearance``，結果 deterministic。
LLM 不參與這裡的任何判斷。
"""
from __future__ import annotations

from backend.engine.clearance import check_placement_with_clearance
from backend.engine.schema import placed_from_dict

from ..documents import HardViolation, LayoutDoc, SceneDoc
from .base import ToolContract
from .place_furniture import clearance_zone
from .read_layout import to_engine_room


class EngineValidateTool:
    contract = ToolContract(
        name="engine_validate",
        description="以 engine 重新驗證場景中每件家具的碰撞、淨空與邊界合法性。",
        input_schema={
            "type": "object",
            "properties": {
                "layout": {"type": "object"},
                "scene": {"type": "object"},
            },
            "required": ["layout", "scene"],
        },
        output_schema={
            "type": "array",
            "items": {"type": "object", "description": "HardViolation dict"},
        },
    )

    def run(self, layout: LayoutDoc, scene: SceneDoc) -> list[HardViolation]:
        violations: list[HardViolation] = []
        for room in layout.rooms:
            rows = scene.placed_in(room.room_id)
            if not rows:
                continue
            engine_room = to_engine_room(room)
            items = []
            for row in rows:
                item = placed_from_dict(row)
                # placed_to_dict 不帶淨空；由場景附加欄位還原，維持與擺放時同標準。
                item.catalog.clearance = clearance_zone(row.get("clearance"))
                items.append(item)
            for index, item in enumerate(items):
                others = items[:index] + items[index + 1 :]
                reason = check_placement_with_clearance(item, engine_room, others)
                if reason is not None:
                    violations.append(
                        HardViolation(
                            room_id=room.room_id,
                            item_id=item.id,
                            reason=str(reason),
                            source="engine",
                        )
                    )
        return violations
