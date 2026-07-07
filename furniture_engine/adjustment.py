"""
adjust_furniture: 依結構化指令調整家具位置/角度。
"""
from furniture_engine.clearance import check_placement_with_clearance as check_placement
from furniture_engine.models import PlacedFurniture, Room


def move_furniture(
    room: Room,
    item: PlacedFurniture,
    others: list[PlacedFurniture],
    dx: float,
    dy: float,
) -> dict:
    """
    嘗試移動家具,採用軸分離策略:
    X 軸跟 Y 軸分開檢查,能走多少走多少。
    """
    original_x, original_y = item.pos_x, item.pos_y
    moved_x, moved_y = False, False

    item.pos_x = original_x + dx
    if check_placement(item, room, others) is None:
        moved_x = True
    else:
        item.pos_x = original_x

    item.pos_y = original_y + dy
    if check_placement(item, room, others) is None:
        moved_y = True
    else:
        item.pos_y = original_y

    if not moved_x and not moved_y:
        return {
            "success": False,
            "placed": item,
            "reason": check_placement(
                PlacedFurniture(
                    id=item.id,
                    catalog=item.catalog,
                    pos_x=original_x + dx,
                    pos_y=original_y + dy,
                    rotation=item.rotation,
                ),
                room,
                others,
            )
            or "移動失敗",
        }

    return {"success": True, "placed": item, "reason": None}


def rotate_furniture(
    room: Room,
    item: PlacedFurniture,
    others: list[PlacedFurniture],
    new_rotation: float,
) -> dict:
    """旋轉家具,若旋轉後不合法就還原角度"""
    original_rotation = item.rotation
    item.rotation = new_rotation % 360

    reason = check_placement(item, room, others)
    if reason is not None:
        item.rotation = original_rotation
        return {"success": False, "placed": item, "reason": reason}

    return {"success": True, "placed": item, "reason": None}


def adjust_furniture(
    room: Room,
    item: PlacedFurniture,
    others: list[PlacedFurniture],
    command: dict,
) -> dict:
    """
    統一入口,吃 Agent 拆解好的結構化指令。
    """
    action = command.get("action")
    if action == "move":
        return move_furniture(room, item, others, command.get("dx", 0), command.get("dy", 0))
    if action == "rotate":
        return rotate_furniture(
            room,
            item,
            others,
            command.get("rotation", item.rotation),
        )
    return {"success": False, "placed": item, "reason": f"未知的動作:{action}"}

