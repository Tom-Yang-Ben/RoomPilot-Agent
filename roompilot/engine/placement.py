"""
place_furniture:依需求把家具自動放進房間,回傳合法座標。

對應 SSOT 文件 F3:「依需求放真實尺寸軟裝;尺寸正確、不超出空間」
"""
from roompilot.engine.models import Room, PlacedFurniture, FurnitureCatalogItem
from roompilot.engine.clearance import check_placement_with_clearance as check_placement

def place_furniture(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
    existing: list[PlacedFurniture],
) -> dict:
    """
    嘗試把一件家具放進房間裡,找到第一個合法位置就採用。

    回傳格式(給 Agent / 後端用):
    {
        "success": bool,
        "placed": PlacedFurniture | None,
        "reason": str | None   # 失敗原因
    }
    """
    cx, cy = room.width / 2, room.depth / 2

    # 候選位置:先試房間正中央,再往四周擴散試(對應原型 placeFree 的 cands)
    candidates = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1),
                  (1, 1), (-1, 1), (1, -1), (-1, -1),
                  (2, 0), (-2, 0), (0, 2), (0, -2)]

    step = 95.0
    for rotation in (0, 90, 180, 270):  # 也嘗試不同角度
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

    items: [(catalog_item, item_id), ...]
    回傳: {"placed": [PlacedFurniture...], "failed": [{"id":..., "reason":...}]}
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