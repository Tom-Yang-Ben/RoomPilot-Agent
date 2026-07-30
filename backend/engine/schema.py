"""
schema.py — furniture_engine 對外介面定義(v0.1 提案)

用途:
1. 定義 Agent(LLM function-calling)呼叫本引擎的 tool schema
2. 提供 Python 物件 <-> JSON dict 的序列化工具
3. 作為與 Agent 核心(林柏彥)、後端(蘇立凱)對介面的單一依據

單位契約:所有長度/座標一律公分(cm)。

版本狀態:v0.1 草案,待與 Agent 核心對齊後定版
"""
from backend.engine.models import (
    ClearanceSpec,
    ClearanceZone,
    FurnitureCatalogItem,
    PlacedFurniture,
)


# ---------- 序列化:Python 物件 <-> JSON dict ----------

def placed_to_dict(item: PlacedFurniture) -> dict:
    """PlacedFurniture -> JSON dict(後端存 DB、前端渲染、回給 Agent 都吃這個)"""
    return {
        "schema_version": "2.0",
        "coordinate_unit": "cm",
        "id": item.id,
        "type": item.catalog.type,
        "name": item.catalog.name,
        "width": item.catalog.width,
        "depth": item.catalog.depth,
        "height": item.catalog.height,
        "pos_x": round(item.pos_x, 1),
        "pos_y": round(item.pos_y, 1),
        "rotation": item.rotation,
    }


def _zone_from_dict(raw: dict) -> ClearanceZone:
    if not isinstance(raw, dict):
        raise ValueError("clearance_zones 的項目必須是物件")
    return ClearanceZone(
        side=str(raw["side"]),
        depth=float(raw["depth"]) if raw.get("depth") is not None else None,
        kind=str(raw.get("kind") or "operation"),
        ideal_cm=(
            float(raw["ideal_cm"]) if raw.get("ideal_cm") is not None else None
        ),
        floor_cm=(
            float(raw["floor_cm"]) if raw.get("floor_cm") is not None else None
        ),
        reason=str(raw["reason"]) if raw.get("reason") else None,
    )


def _clearance_fields_from_dict(d: dict) -> tuple[ClearanceZone | None, ClearanceSpec | None]:
    """讀取 clearance_zones；一面時同時填 legacy clearance，多面用 clearance_spec。"""
    raw_zones = d.get("clearance_zones")
    if raw_zones is None and isinstance(d.get("clearance"), dict):
        raw_zones = [d["clearance"]]
    if raw_zones in (None, []):
        return None, None
    if not isinstance(raw_zones, list):
        raise ValueError("clearance_zones 必須是陣列")
    zones = [_zone_from_dict(raw) for raw in raw_zones]
    mode = str(d.get("clearance_mode") or "all")
    enforce_raw = d.get("clearance_enforce_floor")
    enforce_floor = bool(enforce_raw) if enforce_raw is not None else False
    if len(zones) == 1 and mode == "all" and not enforce_floor:
        # 相容舊單面資料：仍走 clearance 欄位語意。
        return zones[0], None
    return None, ClearanceSpec(zones=zones, mode=mode, enforce_floor=enforce_floor)


def catalog_from_dict(d: dict) -> FurnitureCatalogItem:
    """JSON dict -> FurnitureCatalogItem；所有長度仍為公分。"""
    clearance, clearance_spec = _clearance_fields_from_dict(d)
    return FurnitureCatalogItem(
        type=d["type"],
        name=d["name"],
        width=float(d["width"]),
        depth=float(d["depth"]),
        height=float(d.get("height", 80)),
        style=d.get("style"),
        clearance=clearance,
        clearance_spec=clearance_spec,
    )


def placed_from_dict(d: dict) -> PlacedFurniture:
    """JSON dict -> PlacedFurniture(從 DB/前端還原目前場景狀態用)"""
    return PlacedFurniture(
        id=d["id"],
        catalog=catalog_from_dict(d),
        pos_x=float(d["pos_x"]),
        pos_y=float(d["pos_y"]),
        rotation=float(d.get("rotation", 0)),
    )


# ---------- LLM function-calling tool 定義(給 Agent 核心貼進 tools 清單)----------

PLACE_FURNITURE_TOOL = {
    "name": "place_furniture",
    "description": "把一件或多件家具自動擺進房間,回傳每件家具的座標(pos_x, pos_y)與朝向(rotation)。放不下時回報失敗原因。",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "要擺放的家具清單",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "家具類型,如 sofa / bed / wardrobe / table"},
                        "name": {"type": "string", "description": "顯示名稱,如 三人沙發"},
                        "width": {"type": "number", "description": "寬(公分)"},
                        "depth": {"type": "number", "description": "深(公分)"},
                        "clearance_zones": {
                            "type": "array",
                                                        "description": "一面或多面淨空；多面時搭配 clearance_mode=all|any",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "side": {"type": "string", "enum": ["front", "back", "left", "right"]},
                                    "kind": {"type": "string", "enum": ["operation", "access"]},
                                    "ideal_cm": {"type": "number"},
                                    "floor_cm": {"type": "number"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["side", "kind", "ideal_cm", "floor_cm"],
                            },
                        },
                    },
                    "required": ["type", "name", "width", "depth"],
                },
            },
        },
        "required": ["items"],
    },
}

ADJUST_FURNITURE_TOOL = {
    "name": "adjust_furniture",
    "description": "調整已擺放的家具。v0.1 支援動作:move(位移)、rotate(旋轉)。v0.2 預計支援:add(新增)、remove(移除)、相對方位指令(如 toward_window)。",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["move", "rotate"], "description": "動作類型"},
            "target": {"type": "string", "description": "目標家具 id,如 sofa_1"},
            "dx": {"type": "number", "description": "move 用:X 方向位移(公分,+右 -左)"},
            "dy": {"type": "number", "description": "move 用:Y 方向位移(公分,+深 -淺)"},
            "rotation": {"type": "number", "description": "rotate 用:目標角度(度,0~360)"},
        },
        "required": ["action", "target"],
    },
}
