"""擺家具 tool：把家具清單（語意意圖）交給 engine 計算合法座標。

邊界（CLAUDE.md）：家具座標只有 ``backend.engine`` 能算。本 tool 把
``PlacementHint``（free / adjacent / overlay）翻成對應的 engine 呼叫；
所有座標與失敗原因都來自 engine，agent 不得自行發明或修改座標。

engine 能力偵測：現行引擎必有 ``place_furniture``；``place_adjacent_to_furniture``
與 ``place_overlay_on_furniture`` 為選配（部分分支尚未提供）。缺少時
adjacent / overlay 意圖降級為 free 自由擺放（仍由 engine 決定座標），
並在 hint note 註記——agent 層不自行實作幾何來補位。

場景 placed 條目沿用 ``backend.engine.schema.placed_to_dict``
（``schema_version: "2.0"``、``coordinate_unit: "cm"``），並附加
catalog 追溯欄位（catalog_id、style、price、clearance、matched_requirements）。
"""
from __future__ import annotations

from backend.engine import placement as engine_placement
from backend.engine.models import ClearanceZone, FurnitureCatalogItem, PlacedFurniture
from backend.engine.schema import placed_to_dict

from ..documents import ChosenItem, FurnitureListDoc, LayoutDoc, SceneDoc
from .base import ToolContract
from .pick_furniture import order_for_placement
from .read_layout import to_engine_room

# 選配的 engine 進階擺位；不存在時為 None（意圖降級 free）。
_place_adjacent = getattr(engine_placement, "place_adjacent_to_furniture", None)
_place_overlay = getattr(engine_placement, "place_overlay_on_furniture", None)


def clearance_zone(data: dict | None) -> ClearanceZone | None:
    if not isinstance(data, dict):
        return None
    side = data.get("side")
    depth = data.get("depth_cm", data.get("depth"))
    if side in ("front", "back", "left", "right") and depth:
        return ClearanceZone(side=str(side), depth=float(depth))
    return None


def to_engine_item(item: ChosenItem) -> FurnitureCatalogItem:
    return FurnitureCatalogItem(
        type=item.category,
        name=item.name,
        width=item.width_cm,
        depth=item.depth_cm,
        height=item.height_cm,
        style=item.style,
        price=item.price,
        clearance=clearance_zone(item.clearance),
    )


class PlaceFurnitureTool:
    contract = ToolContract(
        name="place_furniture",
        description=(
            "依家具清單的語意擺位意圖呼叫 engine 計算合法座標，"
            "產出場景配置文件；座標只來自 engine。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "layout": {"type": "object"},
                "furniture_list": {"type": "object"},
            },
            "required": ["layout", "furniture_list"],
        },
        output_schema={"type": "object", "description": "SceneDoc dict"},
    )

    def run(self, layout: LayoutDoc, furniture_list: FurnitureListDoc) -> SceneDoc:
        scene = SceneDoc(variant=furniture_list.variant, strategy=furniture_list.strategy)
        for room in layout.rooms:
            items = order_for_placement(furniture_list.in_room(room.room_id))
            if not items:
                scene.rooms[room.room_id] = {"placed": [], "failed": []}
                continue
            engine_room = to_engine_room(room)
            placed_objs: list[PlacedFurniture] = []
            placed_by_id: dict[str, PlacedFurniture] = {}
            placed_rows: list[dict] = []
            failed_rows: list[dict] = []
            for item in items:
                result = self._place_one(engine_room, item, placed_objs, placed_by_id)
                if result["success"]:
                    placed = result["placed"]
                    placed_objs.append(placed)
                    placed_by_id[item.item_id] = placed
                    row = placed_to_dict(placed)
                    row.update(
                        {
                            "coordinate_unit": "cm",
                            "catalog_id": item.catalog_id,
                            "style": item.style,
                            "price": item.price,
                            "clearance": item.clearance,
                            "matched_requirements": list(item.matched_requirements),
                            "hint_method": item.hint.method,
                        }
                    )
                    placed_rows.append(row)
                else:
                    failed_rows.append(
                        {
                            "id": item.item_id,
                            "name": item.name,
                            "category": item.category,
                            "catalog_id": item.catalog_id,
                            "matched_requirements": list(item.matched_requirements),
                            "reason": result["reason"] or "engine 未回報原因",
                        }
                    )
            scene.rooms[room.room_id] = {"placed": placed_rows, "failed": failed_rows}
        return scene

    def _place_one(
        self,
        engine_room,
        item: ChosenItem,
        placed_objs: list[PlacedFurniture],
        placed_by_id: dict[str, PlacedFurniture],
    ) -> dict:
        catalog_item = to_engine_item(item)
        method = item.hint.method
        anchor = placed_by_id.get(item.hint.anchor_item_id or "")
        if method == "adjacent" and anchor is not None and _place_adjacent is not None:
            result = _place_adjacent(
                engine_room, catalog_item, item.item_id, anchor, placed_objs
            )
            if result["success"]:
                return result
            # 主件周圍放不下時退回自由擺放，仍由 engine 決定座標。
            return engine_placement.place_furniture(
                engine_room, catalog_item, item.item_id, placed_objs
            )
        if method == "overlay" and anchor is not None and _place_overlay is not None:
            return _place_overlay(engine_room, catalog_item, item.item_id, anchor)
        if method in ("adjacent", "overlay") and (
            (method == "adjacent" and _place_adjacent is None)
            or (method == "overlay" and _place_overlay is None)
        ):
            item.hint.note = (item.hint.note + "（引擎無此擺位模式，降級自由擺放）").strip()
        return engine_placement.place_furniture(
            engine_room, catalog_item, item.item_id, placed_objs
        )
