"""
adjust_furniture:依 Agent 已拆解好的結構化指令,調整家具位置/角度。

對應 SSOT 文件 F6:「自然語言調家具位置/數量,重繪」
注意:自然語言理解不是這裡的工作(那是 Agent 核心),
這裡只吃結構化參數,例如 {"action": "move", "target": "sofa_1", "dx": 50, "dy": 0}(單位公分)
"""
from roompilot.engine.models import Room, PlacedFurniture
from roompilot.engine.clearance import check_placement_with_clearance as check_placement

def move_furniture(
    room: Room,
    item: PlacedFurniture,
    others: list[PlacedFurniture],
    dx: float,
    dy: float,
) -> dict:
    """
    嘗試移動家具,採用軸分離策略(對應原型的 moveTo):
    X 軸跟 Y 軸分開檢查,能走多少走多少,而不是全有全無。
    """
    original_x, original_y = item.pos_x, item.pos_y
    moved_x, moved_y = False, False

    # 先試 X 軸
    item.pos_x = original_x + dx
    if check_placement(item, room, others) is None:
        moved_x = True
    else:
        item.pos_x = original_x  # 擋下來,還原

    # 再試 Y 軸
    item.pos_y = original_y + dy
    if check_placement(item, room, others) is None:
        moved_y = True
    else:
        item.pos_y = original_y  # 擋下來,還原

    if not moved_x and not moved_y:
        return {
            "success": False,
            "placed": item,
            "reason": check_placement(
                PlacedFurniture(id=item.id, catalog=item.catalog,
                                 pos_x=original_x + dx, pos_y=original_y + dy,
                                 rotation=item.rotation),
                room, others,
            ) or "移動失敗",
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

    command 範例:
      {"action": "move", "dx": 50, "dy": 0}
      {"action": "rotate", "rotation": 90}
    """
    action = command.get("action")
    if action == "move":
        return move_furniture(room, item, others, command.get("dx", 0), command.get("dy", 0))
    elif action == "rotate":
        return rotate_furniture(room, item, others, command.get("rotation", item.rotation))
    else:
        return {"success": False, "placed": item, "reason": f"未知的動作:{action}"}