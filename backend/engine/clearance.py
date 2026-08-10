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

from backend.engine.models import Room, PlacedFurniture, ClearanceZone
from backend.engine.geometry import furniture_polygon, wall_polygon


# 有櫃家具正面預設淨空(公分):型錄沒宣告淨空區時,收納類家具(衣櫃/收納櫃/
# 邊櫃/五斗櫃/電視櫃/書櫃/鞋櫃…)一律在正面保留這段開合＋站立/行走空間。
# 正式 Kai 型錄每件 clearance_zones 都是空的(postgres_repository),否則收納櫃會
# 被緊貼別的家具擺放,門打不開也沒走道。ponytail: 常數即校準旋鈕,要分型再拆表。
CABINET_FRONT_CLEARANCE_CM = 50.0

# 以 normalized_type 子字串判「有櫃家具」(= 需要正面 50cm 開合＋站立淨空的收納類)。
# 刻意不含:
#   - bedside-table:床頭櫃是成組副件,本該貼床,給正面淨空會拆散床組。
#   - tv-bench / tv-media:電視櫃正面正對沙發＋茶几(視聽軸線),那 50cm 正是茶几/座位
#     該在的位置,不是門開空間;當成有櫃件會反把唯一的中央後援位讓茶几擋掉,使電視櫃
#     在牆位被門淨空吃光時放不下(feedback:客廳總是擺不進電視櫃、但視覺上放得下)。
# engine 層不反向 import agent.knowledge,自持一份記號即可。
_CABINET_TOKENS = (
    "wardrobe", "cabinet", "cupboard", "sideboard", "drawer",
    "bookcase", "bookshelf", "shelving", "storage", "shoe",
    "chest",
)


def is_cabinet_type(type_name: str | None) -> bool:
    """該家具是否為「有櫃」收納類(用 normalized_type 記號判定)。"""
    text = str(type_name or "").casefold()
    return any(token in text for token in _CABINET_TOKENS)


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
        # 型錄沒宣告淨空:有櫃家具仍補上正面 50cm(門開＋站立);其餘無淨空需求。
        if not is_cabinet_type(item.catalog.type):
            return None
        cz = ClearanceZone(side="front", depth=CABINET_FRONT_CLEARANCE_CM)

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
        other_zone = clearance_polygon(other)
        if other_zone is not None and body.intersects(other_zone):
            return f"擋住了「{other.catalog.name}」的開合空間"

    return None