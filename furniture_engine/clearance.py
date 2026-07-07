"""
clearance.py — 開合淨空運算
"""
from shapely.affinity import rotate
from shapely.geometry import Polygon, box

from furniture_engine.geometry import furniture_polygon, wall_polygon
from furniture_engine.models import PlacedFurniture, Room


_SIDE_OFFSETS = {
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
        y_inner = item.pos_y + dy * hd
        y_outer = y_inner + dy * cz.depth
        poly = box(
            item.pos_x - hw,
            min(y_inner, y_outer),
            item.pos_x + hw,
            max(y_inner, y_outer),
        )
    else:
        x_inner = item.pos_x + dx * hw
        x_outer = x_inner + dx * cz.depth
        poly = box(
            min(x_inner, x_outer),
            item.pos_y - hd,
            max(x_inner, x_outer),
            item.pos_y + hd,
        )

    if item.rotation:
        poly = rotate(poly, item.rotation, origin=(item.pos_x, item.pos_y))
    return poly


def clearance_conflict(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
) -> str | None:
    zone = clearance_polygon(item)
    if zone is None:
        return None

    for wall in room.walls:
        if zone.intersects(wall_polygon(wall)):
            return f"「{item.catalog.name}」的開合空間被牆體阻擋"

    for other in others:
        if other.id == item.id:
            continue
        if zone.intersects(furniture_polygon(other)):
            return f"「{item.catalog.name}」的開合空間與「{other.catalog.name}」衝突"
        other_zone = clearance_polygon(other)
        if other_zone is not None and zone.intersects(other_zone):
            return (
                f"「{item.catalog.name}」與「{other.catalog.name}」的開合空間互相衝突"
            )

    return None


def check_placement_with_clearance(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
) -> str | None:
    """本體碰撞 + 淨空檢查的總入口"""
    from furniture_engine.geometry import check_placement

    reason = check_placement(item, room, others)
    if reason is not None:
        return reason

    reason = clearance_conflict(item, room, others)
    if reason is not None:
        return reason

    body = furniture_polygon(item)
    for other in others:
        if other.id == item.id:
            continue
        other_zone = clearance_polygon(other)
        if other_zone is not None and body.intersects(other_zone):
            return f"擋住了「{other.catalog.name}」的開合空間"

    return None

