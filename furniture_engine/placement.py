"""
place_furniture: 依需求把家具自動放進房間,回傳合法座標。
"""
from furniture_engine.clearance import check_placement_with_clearance as check_placement
from furniture_engine.models import FurnitureCatalogItem, PlacedFurniture, Room


def place_furniture(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
    existing: list[PlacedFurniture],
) -> dict:
    """
    嘗試把一件家具放進房間裡,找到第一個合法位置就採用。
    """
    cx, cy = room.width / 2, room.depth / 2

    candidates = [
        (0, 0),
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (-1, 1),
        (1, -1),
        (-1, -1),
        (2, 0),
        (-2, 0),
        (0, 2),
        (0, -2),
    ]

    step = 0.95
    for rotation in (0, 90, 180, 270):
        for sx, sz in candidates:
            candidate = PlacedFurniture(
                id=item_id,
                catalog=catalog_item,
                pos_x=cx + sx * step,
                pos_y=cy + sz * step,
                rotation=rotation,
            )
            reason = check_placement(candidate, room, existing)
            if reason is None:
                return {"success": True, "placed": candidate, "reason": None}

    return {"success": False, "placed": None, "reason": "找不到合法擺放位置"}


def place_furniture_batch(
    room: Room,
    items: list[tuple[FurnitureCatalogItem, str]],
) -> dict:
    """
    批次放置多件家具(依序放,後放的要避開先放好的)。
    """
    placed: list[PlacedFurniture] = []
    failed: list[dict] = []

    for catalog_item, item_id in items:
        result = place_furniture(room, catalog_item, item_id, placed)
        if result["success"]:
            placed.append(result["placed"])
        else:
            failed.append({"id": item_id, "reason": result["reason"]})

    return {"placed": placed, "failed": failed}

