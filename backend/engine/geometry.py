"""
幾何運算工具:用 Shapely 判斷家具碰撞(穿牆 / 重疊 / 出界)

對應 2Dto3D.html 裡的 hitsWall / hitsFurniture / outOfBounds,
但改用嚴謹的多邊形交集判斷(支援旋轉),而不是簡化的包圍盒。
"""
import math
from shapely.geometry import Polygon, box
from shapely.affinity import rotate

from backend.engine.models import Room, Wall, PlacedFurniture


def furniture_polygon(item: PlacedFurniture) -> Polygon:
    """把一件家具轉成旋轉後的多邊形(以 pos_x, pos_y 為中心)"""
    hw, hd = item.catalog.width / 2, item.catalog.depth / 2
    poly = box(
        item.pos_x - hw, item.pos_y - hd,
        item.pos_x + hw, item.pos_y + hd,
    )
    if item.rotation:
        poly = rotate(poly, item.rotation, origin=(item.pos_x, item.pos_y))
    return poly


def wall_polygon(wall: Wall) -> Polygon:
    """把一段牆轉成有厚度的長方形多邊形"""
    dx, dy = wall.x2 - wall.x1, wall.y2 - wall.y1
    length = math.hypot(dx, dy)
    if length < 1e-4:
        return Polygon()
    angle = math.degrees(math.atan2(dy, dx))
    cx, cy = (wall.x1 + wall.x2) / 2, (wall.y1 + wall.y2) / 2
    poly = box(cx - length / 2, cy - wall.thickness / 2,
               cx + length / 2, cy + wall.thickness / 2)
    return rotate(poly, angle, origin=(cx, cy))


def room_polygon(room: Room) -> Polygon:
    """房間邊界多邊形,用來判斷出界"""
    return box(0, 0, room.width, room.depth)


def hits_wall(item: PlacedFurniture, room: Room) -> bool:
    poly = furniture_polygon(item)
    for wall in room.walls:
        if poly.intersects(wall_polygon(wall)):
            return True
    return False


def hits_furniture(item: PlacedFurniture, others: list[PlacedFurniture]) -> PlacedFurniture | None:
    poly = furniture_polygon(item)
    for other in others:
        if other.id == item.id:
            continue
        if poly.intersects(furniture_polygon(other)):
            return other
    return None


def out_of_bounds(item: PlacedFurniture, room: Room) -> bool:
    poly = furniture_polygon(item)
    return not poly.within(room_polygon(room))


def check_placement(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None:
    """統一檢查入口,回傳 None 表示合法,否則回傳失敗原因(繁中訊息)"""
    if out_of_bounds(item, room):
        return "物件超出空間範圍"
    if hits_wall(item, room):
        return "與牆體穿透"
    other = hits_furniture(item, others)
    if other:
        return f"與「{other.catalog.name}」重疊"
    return None
