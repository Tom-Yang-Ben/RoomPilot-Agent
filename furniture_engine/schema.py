"""
schema.py — furniture_engine 對外介面定義(v0.1 提案)
"""
from furniture_engine.models import FurnitureCatalogItem, PlacedFurniture


def placed_to_dict(item: PlacedFurniture) -> dict:
    """PlacedFurniture -> JSON dict"""
    return {
        "id": item.id,
        "type": item.catalog.type,
        "name": item.catalog.name,
        "width": item.catalog.width,
        "depth": item.catalog.depth,
        "height": item.catalog.height,
        "pos_x": round(item.pos_x, 3),
        "pos_y": round(item.pos_y, 3),
        "rotation": item.rotation,
    }


def catalog_from_dict(d: dict) -> FurnitureCatalogItem:
    """JSON dict -> FurnitureCatalogItem"""
    return FurnitureCatalogItem(
        type=d["type"],
        name=d["name"],
        width=float(d["width"]),
        depth=float(d["depth"]),
        height=float(d.get("height", 0.8)),
        style=d.get("style"),
    )


def placed_from_dict(d: dict) -> PlacedFurniture:
    """JSON dict -> PlacedFurniture"""
    return PlacedFurniture(
        id=d["id"],
        catalog=catalog_from_dict(d),
        pos_x=float(d["pos_x"]),
        pos_y=float(d["pos_y"]),
        rotation=float(d.get("rotation", 0)),
    )


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
                        "type": {
                            "type": "string",
                            "description": "家具類型,如 sofa / bed / wardrobe / table",
                        },
                        "name": {"type": "string", "description": "顯示名稱,如 三人沙發"},
                        "width": {"type": "number", "description": "寬(公尺)"},
                        "depth": {"type": "number", "description": "深(公尺)"},
                    },
                    "required": ["type", "name", "width", "depth"],
                },
            }
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
            "dx": {"type": "number", "description": "move 用:X 方向位移(公尺,+右 -左)"},
            "dy": {"type": "number", "description": "move 用:Y 方向位移(公尺,+深 -淺)"},
            "rotation": {"type": "number", "description": "rotate 用:目標角度(度,0~360)"},
        },
        "required": ["action", "target"],
    },
}

