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


def vertical_overlap(a: PlacedFurniture, b: PlacedFurniture) -> bool:
    """兩件家具的垂直佔用帶是否重疊。

    地毯與桌面擺飾沒有垂直佔用帶,永遠不衝突——沙發腳踩在地毯上是正常的。
    壁架(120–150)與矮櫃(0–80)不重疊;與 200 公分高衣櫃重疊,就該擋。
    """
    span_a = a.catalog.vertical_span()
    span_b = b.catalog.vertical_span()
    if span_a is None or span_b is None:
        return False
    return span_a[0] < span_b[1] and span_b[0] < span_a[1]


def may_share_floor_space(a: PlacedFurniture, b: PlacedFurniture) -> bool:
    """這兩件家具是否被允許共用同一塊平面空間。

    先看垂直帶——不重疊就本來不會撞。垂直帶重疊時再查成對例外:
    餐椅推進餐桌下、辦公椅推進書桌下是正常配置,不是違規。
    """
    if not vertical_overlap(a, b):
        return True
    return (
        b.catalog.type in a.catalog.overlap_allowed_types
        or a.catalog.type in b.catalog.overlap_allowed_types
    )


def hits_furniture(item: PlacedFurniture, others: list[PlacedFurniture]) -> PlacedFurniture | None:
    poly = furniture_polygon(item)
    for other in others:
        if other.id == item.id:
            continue
        if may_share_floor_space(item, other):
            continue
        if poly.intersects(furniture_polygon(other)):
            return other
    return None


def out_of_bounds(item: PlacedFurniture, room: Room) -> bool:
    poly = furniture_polygon(item)
    return not poly.within(room_polygon(room))


def check_placement(item: PlacedFurniture, room: Room, others: list[PlacedFurniture]) -> str | None:
    """統一檢查入口,回傳 None 表示合法,否則回傳失敗原因(繁中訊息)"""
    # 壁掛品項掛在牆面上:穿牆與探出房間邊界是它的正常狀態,只檢查與
    # 垂直帶重疊的家具有沒有撞在一起。
    if not item.catalog.is_wall_mounted():
        if out_of_bounds(item, room):
            return "物件超出空間範圍"
        if hits_wall(item, room):
            return "與牆體穿透"
    other = hits_furniture(item, others)
    if other:
        return f"與「{other.catalog.name}」重疊"
    return None
