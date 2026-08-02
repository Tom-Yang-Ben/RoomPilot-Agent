"""
clearance.py — 開合淨空運算(F3/F6 分工範圍:碰撞/淨空運算)

處理:衣櫃門、冰箱門、抽屜等開合時所需的額外空間,
不能與其他家具本體、其他家具的淨空範圍、或牆體衝突。

設計原則:
- 淨空範圍 = 家具本體某一面向外延伸的矩形,跟著家具 rotation 一起旋轉
- 淨空 vs 牆:衝突(門打不開)
- 淨空 vs 其他家具本體:衝突(門撞到家具)
- 淨空 vs 其他家具的淨空:衝突(兩個門互相打架)——較嚴格,可討論放寬
"""
from shapely.geometry import Polygon, box
from shapely.affinity import rotate

from backend.engine.models import Room, PlacedFurniture
from backend.engine.geometry import furniture_polygon, vertical_overlap, wall_polygon


_SIDE_OFFSETS = {
    # side: (x方向係數, y方向係數) —— 未旋轉時延伸的方向
    "front": (0, 1),
    "back": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


def clearance_polygon(item: PlacedFurniture) -> Polygon | None:
    """算出這件家具的淨空範圍多邊形(不含本體),無淨空需求時回傳 None"""
    cz = item.catalog.clearance
    if cz is None:
        return None

    hw, hd = item.catalog.width / 2, item.catalog.depth / 2
    dx, dy = _SIDE_OFFSETS[cz.side]

    if dy != 0:
        # front/back:淨空區跟家具同寬,往 y 方向延伸 cz.depth
        y_inner = item.pos_y + dy * hd
        y_outer = y_inner + dy * cz.depth
        poly = box(item.pos_x - hw, min(y_inner, y_outer),
                   item.pos_x + hw, max(y_inner, y_outer))
    else:
        # left/right:淨空區跟家具同深,往 x 方向延伸 cz.depth
        x_inner = item.pos_x + dx * hw
        x_outer = x_inner + dx * cz.depth
        poly = box(min(x_inner, x_outer), item.pos_y - hd,
                   max(x_inner, x_outer), item.pos_y + hd)

    if item.rotation:
        poly = rotate(poly, item.rotation, origin=(item.pos_x, item.pos_y))
    return poly


def clearance_conflict(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
) -> str | None:
    """
    檢查這件家具的淨空範圍是否有衝突,回傳 None 表示無衝突。

    檢查順序:淨空撞牆 → 淨空撞其他家具本體 → 淨空撞其他家具的淨空
    """
    zone = clearance_polygon(item)
    if zone is None:
        return None

    # 1. 淨空 vs 牆(門打不開)
    for wall in room.walls:
        if zone.intersects(wall_polygon(wall)):
            return f"「{item.catalog.name}」的開合空間被牆體阻擋"

    for other in others:
        if other.id == item.id:
            continue
        # 開合空間的高度就是家具本身的高度:垂直帶不重疊的東西擋不到門片。
        # 地毯鋪進衣櫃門前是正常的,不該判成「開合空間被擋住」。
        if not vertical_overlap(item, other):
            continue
        # 2. 淨空 vs 其他家具本體
        if zone.intersects(furniture_polygon(other)):
            return f"「{item.catalog.name}」的開合空間與「{other.catalog.name}」衝突"
        # 3. 淨空 vs 其他家具的淨空
        other_zone = clearance_polygon(other)
        if other_zone is not None and zone.intersects(other_zone):
            return f"「{item.catalog.name}」與「{other.catalog.name}」的開合空間互相衝突"

    return None


def check_placement_with_clearance(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
) -> str | None:
    """本體碰撞 + 淨空檢查的總入口(之後 placement/adjustment 可改用這個)"""
    from backend.engine.geometry import check_placement

    reason = check_placement(item, room, others)
    if reason is not None:
        return reason

    reason = clearance_conflict(item, room, others)
    if reason is not None:
        return reason

    # 反向檢查:我的本體有沒有壓到「別人」的淨空範圍
    body = furniture_polygon(item)
    for other in others:
        if other.id == item.id:
            continue
        if not vertical_overlap(item, other):
            continue
        other_zone = clearance_polygon(other)
        if other_zone is not None and body.intersects(other_zone):
            return f"擋住了「{other.catalog.name}」的開合空間"

    return None