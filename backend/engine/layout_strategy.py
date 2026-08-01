"""擺放策略層：決定家具「貼哪面牆、正面朝哪、貼著誰的哪一端、誰先擺」。

與 `placement.py` 的分工：

- `placement.py` 回答「這個位置合不合法」，搜尋順序是中心 → 四面牆 → 網格，first-fit。
- 本模組回答「這個位置好不好」，只產生**符合設計意圖**的候選，再交給既有的
  淨空／碰撞驗證把關。合法性判定仍然只有一份，沒有第二套規則。

座標約定同 `models.py`：原點在房間左下角，x 向右、y 向上，單位公分；
rotation 為逆時針角度，0 度時家具正面朝 +Y。

規則表 `ROOM_RULES` 是**資料**：房型定義改變時改這張表，不必動演算法。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from backend.engine.clearance import (
    CompanionPairs,
    validate_placement_with_clearance,
)
from backend.engine.models import FurnitureCatalogItem, Opening, PlacedFurniture, Room


WALL_SIDES: tuple[str, ...] = ("south", "north", "west", "east")

# 家具背貼該牆時的 rotation，使正面朝向房間內側。
_WALL_ROTATION: dict[str, int] = {"south": 0, "north": 180, "west": 270, "east": 90}

# 牆的走向軸：南北牆沿 x 延伸，東西牆沿 y 延伸。
_WALL_AXIS: dict[str, str] = {"south": "x", "north": "x", "west": "y", "east": "y"}

_OPPOSITE_SIDE: dict[str, str] = {
    "south": "north",
    "north": "south",
    "west": "east",
    "east": "west",
}

# 判斷開口落在哪面牆時容許的誤差；辨識管線的座標會有幾公分浮動。
_WALL_TOLERANCE_CM = 8.0

# 沿牆嘗試位置的步距，與 placement.py 一致，避免兩邊搜尋密度不同。
_SEARCH_STEP_CM = 15.0

# 判定「有沒有貼到牆」的容差。
_TOUCH_TOLERANCE_CM = 1.0


def wall_rotation(side: str) -> int:
    """家具背貼 ``side`` 這面牆時應有的 rotation。"""
    try:
        return _WALL_ROTATION[side]
    except KeyError:
        raise ValueError(f"不支援的牆面: {side}") from None


def side_for_rotation(rotation: float) -> str | None:
    """由家具的 rotation 反推它背貼哪一面牆；不是四個正角就回 None。"""
    for side, value in _WALL_ROTATION.items():
        if int(rotation) % 360 == value:
            return side
    return None


def opposite_side(side: str) -> str:
    """回傳正對面那面牆。"""
    return _OPPOSITE_SIDE[side]


def wall_length(room: Room, side: str) -> float:
    """牆的總長度（公分）。"""
    return room.width if _WALL_AXIS[side] == "x" else room.depth


def _wall_coordinate(room: Room, side: str) -> float:
    """牆在其法線軸上的座標。"""
    return {
        "south": 0.0,
        "north": room.depth,
        "west": 0.0,
        "east": room.width,
    }[side]


def openings_on_wall(
    room: Room,
    side: str,
    tolerance: float = _WALL_TOLERANCE_CM,
) -> list[Opening]:
    """回傳落在 ``side`` 這面牆上的門窗。"""
    axis = _WALL_AXIS[side]
    normal = "y" if axis == "x" else "x"
    coordinate = _wall_coordinate(room, side)
    found: list[Opening] = []
    for opening in room.openings:
        low, high = opening.span_along(normal)
        if abs(low - coordinate) <= tolerance and abs(high - coordinate) <= tolerance:
            found.append(opening)
    return found


def _blocks_height(opening: Opening, item_height_cm: float | None) -> bool:
    """這個開口會不會擋住指定高度的家具。

    ``item_height_cm`` 為 None 時一律視為會擋（保守）。高度低於窗台的家具
    （床頭櫃、五斗櫃、書桌）可以擺在一般窗下；落地窗窗台為 0，任何家具都擋。
    """
    if item_height_cm is None:
        return True
    return float(item_height_cm) > opening.sill_cm


def _subtract_spans(
    length: float,
    blocked: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """從 ``[0, length]`` 扣掉所有被佔用的區間，回傳剩餘可用區段。"""
    if not blocked:
        return [(0.0, length)]

    merged: list[list[float]] = []
    for low, high in sorted(blocked):
        low = max(0.0, low)
        high = min(length, high)
        if high <= low:
            continue
        if merged and low <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])

    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for low, high in merged:
        if low - cursor > 1e-6:
            spans.append((cursor, low))
        cursor = max(cursor, high)
    if length - cursor > 1e-6:
        spans.append((cursor, length))
    return spans


def free_spans(
    room: Room,
    side: str,
    *,
    item_height_cm: float | None = None,
) -> list[tuple[float, float]]:
    """牆上未被門窗佔用的區段，沿牆軸表示。

    門扇掃過的範圍也會投影到牆軸上一併扣除。
    """
    axis = _WALL_AXIS[side]
    blocked: list[tuple[float, float]] = []
    for opening in openings_on_wall(room, side):
        if not _blocks_height(opening, item_height_cm):
            continue
        low, high = opening.span_along(axis)
        if opening.kind == "door" and opening.swing_x is not None and opening.swing_y is not None:
            swing = opening.swing_x if axis == "x" else opening.swing_y
            low = min(low, swing)
            high = max(high, swing)
        blocked.append((low, high))
    return _subtract_spans(wall_length(room, side), blocked)


def door_swing_boxes(room: Room) -> list[tuple[float, float, float, float]]:
    """門扇掃過區域的外接矩形；家具不可佔用。

    用外接矩形而非扇形是刻意保守：寧可少放一件，也不要擺出擋門的結果。
    """
    boxes: list[tuple[float, float, float, float]] = []
    for opening in room.doors():
        if opening.swing_x is None or opening.swing_y is None:
            continue
        xs = (opening.x1, opening.x2, opening.swing_x)
        ys = (opening.y1, opening.y2, opening.swing_y)
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


@dataclass(frozen=True)
class WallCandidate:
    """一面牆上的一段可用區間。"""

    side: str
    start: float
    end: float
    has_door: bool = False
    has_window: bool = False

    @property
    def length(self) -> float:
        return self.end - self.start

    @property
    def center(self) -> float:
        return (self.start + self.end) / 2


def rank_wall_candidates(
    room: Room,
    needed_cm: float,
    *,
    item_height_cm: float | None = None,
    sides: list[str] | tuple[str, ...] | None = None,
) -> list[WallCandidate]:
    """挑牆並排序：無門優先 → 無窗優先 → 區段長者優先。

    這是**暫定的預設規則**，寫在這裡是為了讓結果可預期；房型定義確立後
    可改由 `ROOM_RULES` 指定各家具的牆面偏好，不需要改動演算法。
    """
    allowed = tuple(sides) if sides else WALL_SIDES
    candidates: list[WallCandidate] = []
    for side in WALL_SIDES:
        if side not in allowed:
            continue
        openings = openings_on_wall(room, side)
        blocking = [item for item in openings if _blocks_height(item, item_height_cm)]
        has_door = any(item.kind == "door" for item in blocking)
        has_window = any(item.kind == "window" for item in blocking)
        for start, end in free_spans(room, side, item_height_cm=item_height_cm):
            if end - start + 1e-6 < needed_cm:
                continue
            candidates.append(
                WallCandidate(
                    side=side,
                    start=start,
                    end=end,
                    has_door=has_door,
                    has_window=has_window,
                )
            )

    candidates.sort(key=lambda c: (int(c.has_door), int(c.has_window), -c.length))
    return candidates


def _footprint(catalog: FurnitureCatalogItem, rotation: int) -> tuple[float, float]:
    if rotation in (90, 270):
        return catalog.depth, catalog.width
    return catalog.width, catalog.depth


def _bounds(placed: PlacedFurniture) -> tuple[float, float, float, float]:
    width, depth = _footprint(placed.catalog, int(placed.rotation) % 360)
    return (
        placed.pos_x - width / 2,
        placed.pos_y - depth / 2,
        placed.pos_x + width / 2,
        placed.pos_y + depth / 2,
    )


def _intersects_any_box(
    placed: PlacedFurniture,
    boxes: list[tuple[float, float, float, float]],
) -> bool:
    left, bottom, right, top = _bounds(placed)
    for box_left, box_bottom, box_right, box_top in boxes:
        if left < box_right and right > box_left and bottom < box_top and top > box_bottom:
            return True
    return False


def _positions_along(span_start: float, span_end: float, half_extent: float) -> list[float]:
    """沿區段產生候選座標：**置中優先，其次貼齊兩端，最後才是中間的偏移量**。

    順序很重要。若把兩端擺到最後（早期版本的做法），小房間會出現「床離牆
    10 公分」這種死縫——因為置中被淨空擋掉之後，往外掃到某個中間位置就先
    合法了，永遠掃不到真正貼齊牆角的那個點。人在小房間本來就會把床推到底，
    所以貼齊要排在中間偏移之前。
    """
    low = span_start + half_extent
    high = span_end - half_extent
    if low > high + 1e-6:
        return []
    center = (span_start + span_end) / 2
    center = min(max(center, low), high)

    values = [center, low, high]
    offset = _SEARCH_STEP_CM
    while center - offset >= low or center + offset <= high:
        if center - offset >= low:
            values.append(center - offset)
        if center + offset <= high:
            values.append(center + offset)
        offset += _SEARCH_STEP_CM

    unique: list[float] = []
    seen: set[float] = set()
    for value in values:
        key = round(value, 4)
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def _wall_placement(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    side: str,
    along: float,
    *,
    margin_cm: float = 0.0,
) -> PlacedFurniture:
    """把家具背貼 ``side`` 這面牆，沿牆位置為 ``along``。"""
    rotation = wall_rotation(side)
    offset = catalog.depth / 2 + margin_cm
    if side == "south":
        pos_x, pos_y = along, offset
    elif side == "north":
        pos_x, pos_y = along, room.depth - offset
    elif side == "west":
        pos_x, pos_y = offset, along
    else:
        pos_x, pos_y = room.width - offset, along
    return PlacedFurniture(
        id=item_id,
        catalog=catalog,
        pos_x=pos_x,
        pos_y=pos_y,
        rotation=rotation,
    )


# 呼叫端可額外否決一個候選位置（例如房間多邊形邊界、窗前禁放帶）。
# 回傳 True 表示允許。放在搜尋迴圈裡而不是事後檢查，否則被否決時
# 就直接放棄了，不會去試同一面牆的其他位置或別面牆。
ExtraCheck = Callable[[PlacedFurniture], bool]


def _is_legal(
    candidate: PlacedFurniture,
    room: Room,
    existing: list[PlacedFurniture],
    swing_boxes: list[tuple[float, float, float, float]],
    companion_pairs: CompanionPairs | None,
    extra_check: ExtraCheck | None = None,
) -> bool:
    if _intersects_any_box(candidate, swing_boxes):
        return False
    if extra_check is not None and not extra_check(candidate):
        return False
    validation = validate_placement_with_clearance(
        candidate,
        room,
        existing,
        companion_pairs=companion_pairs,
    )
    return validation.legal


def place_against_wall(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    existing: list[PlacedFurniture],
    *,
    sides: list[str] | tuple[str, ...] | None = None,
    margin_cm: float = 0.0,
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """把家具背貼牆放置，正面朝房間內；找不到就誠實回報失敗。

    ``margin_cm`` 是離牆的視覺留白。引擎預設 0（真正貼齊），但呼叫端若本來
    就有內縮邊距（例如第 6 步的 8 公分），要傳進來，否則家具會比現行行為更
    貼牆，3D 有機會與牆面互相穿透。
    """
    swing_boxes = door_swing_boxes(room)
    candidates = rank_wall_candidates(
        room,
        needed_cm=catalog.width,
        item_height_cm=catalog.height,
        sides=sides,
    )
    attempted = 0
    for candidate in candidates:
        # 邊距只在「房間兩端」生效。牆中間被門窗切出來的區段，家具可以緊鄰
        # 窗框擺放——那不是牆，不會穿模，硬留 8 公分只會白白放不下。
        wall_extent = wall_length(room, candidate.side)
        positions = _positions_along(
            max(candidate.start, margin_cm),
            min(candidate.end, wall_extent - margin_cm),
            catalog.width / 2,
        )
        for along in positions:
            attempted += 1
            placed = _wall_placement(
                room, catalog, item_id, candidate.side, along, margin_cm=margin_cm
            )
            if _is_legal(placed, room, existing, swing_boxes, companion_pairs, extra_check):
                return {
                    "success": True,
                    "placed": placed,
                    "side": candidate.side,
                    "reason": None,
                }
    reason = "沒有可用的牆面" if not candidates else "牆面都放不下這件家具"
    return {
        "success": False,
        "placed": None,
        "side": None,
        "reason": reason,
        "reason_detail": {
            "code": "no_legal_wall_position",
            "message_zh": reason,
            "item_id": item_id,
            "rule": "wall_anchor",
            "attempted_candidates": attempted,
        },
    }


def _front_direction(rotation: int) -> tuple[int, int]:
    """家具「正面」的方向。rotation 0 時正面朝 +Y。"""
    return {0: (0, 1), 90: (-1, 0), 180: (0, -1), 270: (1, 0)}[int(rotation) % 360]


def place_in_front_of(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    target: PlacedFurniture,
    existing: list[PlacedFurniture],
    *,
    gap: float = 45.0,
    face: str = "same",
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """把家具放在主家具的正前方並對齊中線——茶几對沙發就是這個關係。

    這是少數**刻意不貼牆**的擺法：茶几貼牆就失去它存在的意義。
    ``gap`` 是與主家具的距離，放不下時會逐步縮短，但不會貼上去。
    """
    rotation = int(target.rotation) % 360
    direction = _front_direction(rotation)
    target_left, target_bottom, target_right, target_top = _bounds(target)
    item_width, item_depth = _footprint(catalog, rotation)
    swing_boxes = door_swing_boxes(room)

    # 配套關係：茶几可以進入主家具的舒適使用空間。
    pairs: CompanionPairs = set(companion_pairs or set())
    pairs.add(frozenset((target.id, item_id)))

    center_x = (target_left + target_right) / 2
    center_y = (target_bottom + target_top) / 2

    for attempt in (gap, gap * 0.75, gap * 0.5):
        # 下限 2 公分：茶几類 gap 45 有退讓空間；辦公椅類 gap 8 也要試得到
        #（原本寫 10 導致 gap<10 的貼附一次都沒試就放棄）。
        if attempt < 2.0:
            continue
        if direction == (0, 1):
            pos_x, pos_y = center_x, target_top + attempt + item_depth / 2
        elif direction == (0, -1):
            pos_x, pos_y = center_x, target_bottom - attempt - item_depth / 2
        elif direction == (1, 0):
            pos_x, pos_y = target_right + attempt + item_width / 2, center_y
        else:
            pos_x, pos_y = target_left - attempt - item_width / 2, center_y

        # face="target"（辦公椅面向書桌）＝與主件反向 180 度。
        own_rotation = rotation if face == "same" else (rotation + 180) % 360
        placed = PlacedFurniture(
            id=item_id,
            catalog=catalog,
            pos_x=pos_x,
            pos_y=pos_y,
            rotation=own_rotation,
        )
        if _is_legal(placed, room, existing, swing_boxes, pairs, extra_check):
            return {
                "success": True,
                "placed": placed,
                "companion_pair": frozenset((target.id, item_id)),
                "reason": None,
            }

    reason = f"「{catalog.name}」在主家具正前方放不下"
    return {
        "success": False,
        "placed": None,
        "companion_pair": None,
        "reason": reason,
        "reason_detail": {
            "code": "no_legal_front_position",
            "message_zh": reason,
            "item_id": item_id,
            "rule": "attach_front",
            "related_item_id": target.id,
        },
    }


def place_at_center(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    existing: list[PlacedFurniture],
    *,
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """把家具擺在房間中央——餐桌專用的「刻意不貼牆」。

    先試正中，再試 90 度與少量偏移；引擎的四面入座淨空（餐桌 spec）會
    自動保證桌邊留得出椅子與走位空間。
    """
    swing_boxes = door_swing_boxes(room)
    center_x, center_y = room.width / 2, room.depth / 2
    offsets = (
        (0.0, 0.0), (0.0, 30.0), (0.0, -30.0), (30.0, 0.0), (-30.0, 0.0),
        (0.0, 60.0), (0.0, -60.0), (60.0, 0.0), (-60.0, 0.0),
    )
    attempted = 0
    for rotation in (0, 90):
        for dx, dy in offsets:
            attempted += 1
            placed = PlacedFurniture(
                id=item_id,
                catalog=catalog,
                pos_x=center_x + dx,
                pos_y=center_y + dy,
                rotation=rotation,
            )
            if _is_legal(placed, room, existing, swing_boxes, companion_pairs, extra_check):
                return {"success": True, "placed": placed, "reason": None}
    reason = f"「{catalog.name}」在房間中央附近放不下"
    return {
        "success": False,
        "placed": None,
        "reason": reason,
        "reason_detail": {
            "code": "no_legal_center_position",
            "message_zh": reason,
            "item_id": item_id,
            "rule": "attach_center",
            "attempted_candidates": attempted,
        },
    }


def _seat_spots(
    target: PlacedFurniture,
    seat: FurnitureCatalogItem,
    gap: float,
) -> list[tuple[float, float, int]]:
    """主家具（餐桌）四邊的入座點：先每邊中點，長邊夠長再加兩側座位。

    回傳 (x, y, 自身 rotation)，rotation 使椅子正面朝向桌心。
    """
    left, bottom, right, top = _bounds(target)
    width = right - left
    depth = top - bottom
    center_x = (left + right) / 2
    center_y = (bottom + top) / 2
    seat_w, seat_d = seat.width, seat.depth

    spots: list[tuple[float, float, int]] = []

    # rotation 0 時正面朝 +Y：南側椅面北=0、北側面南=180、
    # 西側要面東=270、東側要面西=90（_WALL_ROTATION 同一套語意）。
    def south(x): spots.append((x, bottom - gap - seat_d / 2, 0))
    def north(x): spots.append((x, top + gap + seat_d / 2, 180))
    def west(y): spots.append((left - gap - seat_d / 2, y, 270))
    def east(y): spots.append((right + gap + seat_d / 2, y, 90))

    # 長邊坐得下兩張（含椅距）就直接 2+2——六人桌的現實配置；
    # 坐不下才回到每邊置中一張。座位順序＝長邊優先，先湊滿對坐。
    def side_positions(length: float, center: float) -> list[float]:
        if length >= seat_w * 2 + 3 * 12:
            return [center - length / 4, center + length / 4]
        return [center]

    for x in side_positions(width, center_x):
        south(x)
    for x in side_positions(width, center_x):
        north(x)
    for y in side_positions(depth, center_y):
        west(y)
    for y in side_positions(depth, center_y):
        east(y)
    return spots


def place_around(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    target: PlacedFurniture,
    existing: list[PlacedFurniture],
    *,
    gap: float = 6.0,
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """餐椅環繞餐桌：依序試四邊入座點，正面一律朝桌心。

    多張椅子逐一呼叫本函式即可——已被前一張佔走的座位，會因本體重疊
    被合法性檢查自然跳過。椅子與桌子自動建立配套（可進桌子的入座淨空）。
    """
    pairs: CompanionPairs = set(companion_pairs or set())
    pairs.add(frozenset((target.id, item_id)))
    swing_boxes = door_swing_boxes(room)
    for pos_x, pos_y, rotation in _seat_spots(target, catalog, gap):
        placed = PlacedFurniture(
            id=item_id,
            catalog=catalog,
            pos_x=pos_x,
            pos_y=pos_y,
            rotation=rotation,
        )
        if _is_legal(placed, room, existing, swing_boxes, pairs, extra_check):
            return {
                "success": True,
                "placed": placed,
                "companion_pair": frozenset((target.id, item_id)),
                "reason": None,
            }
    reason = f"「{catalog.name}」在餐桌四周已無座位"
    return {
        "success": False,
        "placed": None,
        "companion_pair": None,
        "reason": reason,
        "reason_detail": {
            "code": "no_legal_seat_position",
            "message_zh": reason,
            "item_id": item_id,
            "rule": "attach_around",
            "related_item_id": target.id,
        },
    }


def _head_direction(rotation: int) -> tuple[int, int]:
    """家具「背面」的方向；床的床頭就在這一端。

    rotation 0 時正面朝 +Y，背面朝 -Y。
    """
    return {0: (0, -1), 90: (1, 0), 180: (0, 1), 270: (-1, 0)}[int(rotation) % 360]


def place_beside(
    room: Room,
    catalog: FurnitureCatalogItem,
    item_id: str,
    target: PlacedFurniture,
    existing: list[PlacedFurniture],
    *,
    end: str = "head",
    gap: float = 5.0,
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """把家具貼在主家具的側邊，並對齊指定的那一端。

    ``end="head"`` 對齊背面那端（床頭），``end="foot"`` 對齊正面那端（床尾）。
    這是床頭櫃該貼床頭、不該貼床尾的實作。
    """
    if end not in {"head", "foot"}:
        raise ValueError(f"不支援的對齊端: {end}")

    rotation = int(target.rotation) % 360
    direction = _head_direction(rotation)
    if end == "foot":
        direction = (-direction[0], -direction[1])

    target_left, target_bottom, target_right, target_top = _bounds(target)
    item_width, item_depth = _footprint(catalog, rotation)
    swing_boxes = door_swing_boxes(room)

    # 貼附本身就是「配套」關係：床頭櫃可以進入床側的舒適使用空間（access），
    # 但門片／抽屜的必要開啟空間（operation）仍然擋得下來。
    pairs: CompanionPairs = set(companion_pairs or set())
    pairs.add(frozenset((target.id, item_id)))

    candidates: list[tuple[float, float]] = []
    if direction == (0, 1):
        pos_y = target_top - item_depth / 2
        candidates = [
            (target_left - gap - item_width / 2, pos_y),
            (target_right + gap + item_width / 2, pos_y),
        ]
    elif direction == (0, -1):
        pos_y = target_bottom + item_depth / 2
        candidates = [
            (target_left - gap - item_width / 2, pos_y),
            (target_right + gap + item_width / 2, pos_y),
        ]
    elif direction == (1, 0):
        pos_x = target_right - item_width / 2
        candidates = [
            (pos_x, target_bottom - gap - item_depth / 2),
            (pos_x, target_top + gap + item_depth / 2),
        ]
    else:
        pos_x = target_left + item_width / 2
        candidates = [
            (pos_x, target_bottom - gap - item_depth / 2),
            (pos_x, target_top + gap + item_depth / 2),
        ]

    for pos_x, pos_y in candidates:
        placed = PlacedFurniture(
            id=item_id,
            catalog=catalog,
            pos_x=pos_x,
            pos_y=pos_y,
            rotation=rotation,
        )
        if _is_legal(placed, room, existing, swing_boxes, pairs, extra_check):
            return {
                "success": True,
                "placed": placed,
                "companion_pair": frozenset((target.id, item_id)),
                "reason": None,
            }

    reason = f"「{catalog.name}」在主家具的{'床頭' if end == 'head' else '床尾'}兩側都放不下"
    return {
        "success": False,
        "placed": None,
        "companion_pair": None,
        "reason": reason,
        "reason_detail": {
            "code": "no_legal_adjacent_position",
            "message_zh": reason,
            "item_id": item_id,
            "rule": "attach_end",
            "related_item_id": target.id,
        },
    }


# --- 規則表（資料；房型定義改變時改這裡） -----------------------------------


@dataclass(frozen=True)
class PlacementRule:
    """一個房型裡，一種家具該怎麼擺。

    - ``anchor``：是不是該房型的錨點，錨點先擺。
    - ``attach``：``wall`` 背貼牆／``beside`` 貼另一件家具／``opposite`` 貼對面牆。
    - ``attach_to``：貼附對象的 normalized_type，依序嘗試。
    - ``attach_end``：貼到對象的哪一端（``head`` 床頭／``foot`` 床尾）。
    - ``gap_cm``：與貼附對象之間的縫隙。
    - ``order``：同一階段內的先後，數字小的先擺。
    """

    anchor: bool = False
    attach: str = "wall"
    attach_to: tuple[str, ...] = ()
    attach_end: str = "head"
    gap_cm: float = 5.0
    order: int = 50
    # 貼附時自身朝向："same"＝與主件同向（茶几）；"target"＝面向主件（辦公椅面桌）。
    face: str = "same"


_WALL_ITEM = PlacementRule()

# 鍵一律使用 **擺位族系**（`backend.agent.knowledge.family_of` 摺疊後的值），
# 不是型錄的原始 normalized_type。否則 `fabric-sofa`／`leather-sofa` 這類
# 具體型別會查不到規則，連帶讓電視櫃找不到要對望的沙發。
#
# `order` 對齊 `agent/knowledge.py` 的宣告：**錨點（ANCHOR_FAMILIES）先拿牆位
# → 泛用件其次 → COMPANION_OF 副件最後**。錨點 0–9、泛用 10–19、副件 20+。
ROOM_RULES: dict[str, dict[str, PlacementRule]] = {
    "bedroom": {
        "bed": PlacementRule(anchor=True, order=0),
        "wardrobe": PlacementRule(anchor=True, order=5),
        "chests-of-drawer": PlacementRule(order=10),
        "desk": PlacementRule(order=12),
        "bookcase": PlacementRule(order=15),
        "bedside-table": PlacementRule(
            attach="beside", attach_to=("bed",), attach_end="head", gap_cm=5.0, order=20
        ),
        "office-chair": PlacementRule(
            attach="front", attach_to=("desk",), gap_cm=8.0, face="target", order=25
        ),
    },
    "living_room": {
        "sofa": PlacementRule(anchor=True, order=0),
        "bookcase": PlacementRule(order=10),
        "armchair": PlacementRule(order=15),
        "tv-bench": PlacementRule(attach="opposite", attach_to=("sofa",), order=20),
        "coffee-table": PlacementRule(
            attach="front", attach_to=("sofa",), gap_cm=45.0, order=25
        ),
    },
    "storage": {
        "shelving-unit": PlacementRule(anchor=True, order=0),
        "cabinet-cupboard": PlacementRule(order=10),
    },
    "dining_room": {
        # 餐桌是全系統唯一「刻意置中」的錨點；椅子環繞、收納靠牆。
        "dining-table": PlacementRule(anchor=True, attach="center", order=0),
        "sideboard": PlacementRule(order=10),
        "display-cabinet": PlacementRule(order=12),
        "dining-chair": PlacementRule(
            attach="around", attach_to=("dining-table",), gap_cm=6.0, order=20
        ),
    },
    "workspace": {
        "desk": PlacementRule(anchor=True, order=0),
        "bookcase": PlacementRule(order=10),
        "shelving-unit": PlacementRule(order=12),
        "office-chair": PlacementRule(
            attach="front", attach_to=("desk",), gap_cm=8.0, face="target", order=20
        ),
    },
    "entry": {
        "shoe-cabinet": PlacementRule(anchor=True, order=0),
        "clothes-rack": PlacementRule(order=10),
    },
}


def rule_for(room_type: str, furniture_family: str) -> PlacementRule:
    """查規則；沒登記的家具一律當「背貼牆」處理。

    兩個參數都必須是**已正規化**的鍵：房型經 `normalize_room_type()`、家具經
    `family_of()`（皆在 `backend.agent.knowledge`）。引擎本身不做這層摺疊，
    是為了不讓幾何模組反向相依 Agent 模組；由整合端負責換算。
    """
    return ROOM_RULES.get(room_type, {}).get(furniture_family, _WALL_ITEM)


@dataclass
class _Pending:
    catalog: FurnitureCatalogItem
    item_id: str
    rule: PlacementRule
    index: int


def place_room(
    room: Room,
    room_type: str,
    items: list[tuple[FurnitureCatalogItem, str]],
    *,
    margin_cm: float = 0.0,
    companion_pairs: CompanionPairs | None = None,
    extra_check: ExtraCheck | None = None,
) -> dict:
    """依房型規則擺一整間房：錨點先、跟隨件後，全部貼牆或貼人。

    回傳 ``{"placed": [...], "failed": [...]}``；失敗一律保留結構化原因，
    不做換小或砍件——那是 Agent 的職責。
    """
    pending = [
        _Pending(
            catalog=catalog,
            item_id=item_id,
            rule=rule_for(room_type, catalog.type),
            index=index,
        )
        for index, (catalog, item_id) in enumerate(items)
    ]
    pending.sort(key=lambda entry: (entry.rule.order, entry.index))

    placed: list[PlacedFurniture] = []
    placed_by_type: dict[str, list[PlacedFurniture]] = {}
    side_by_id: dict[str, str] = {}
    failed: list[dict] = []
    # 貼附成功後產生的配套關係要一路帶下去，否則後面的家具驗證時
    # 會把已經合法的床頭櫃重新判成侵入床側淨空。
    pairs: CompanionPairs = set(companion_pairs or set())

    def remember(item: PlacedFurniture, side: str | None) -> None:
        placed.append(item)
        placed_by_type.setdefault(item.catalog.type, []).append(item)
        if side is not None:
            side_by_id[item.id] = side

    def find_target(types: tuple[str, ...]) -> PlacedFurniture | None:
        for wanted in types:
            found = placed_by_type.get(wanted)
            if found:
                return found[0]
        return None

    for entry in pending:
        rule = entry.rule
        result: dict

        if rule.attach == "center":
            result = place_at_center(
                room, entry.catalog, entry.item_id, placed,
                companion_pairs=pairs, extra_check=extra_check,
            )
            if result["success"]:
                remember(result["placed"], None)
            else:
                failed.append(_failure(entry, result))
            continue

        if rule.attach in {"beside", "front", "around"}:
            target = find_target(rule.attach_to)
            if target is None:
                result = {
                    "success": False,
                    "placed": None,
                    "reason": f"找不到要貼附的主家具（{'／'.join(rule.attach_to)}）",
                }
            elif rule.attach == "front":
                result = place_in_front_of(
                    room,
                    entry.catalog,
                    entry.item_id,
                    target,
                    placed,
                    gap=rule.gap_cm,
                    face=rule.face,
                    companion_pairs=pairs,
                    extra_check=extra_check,
                )
            elif rule.attach == "around":
                result = place_around(
                    room,
                    entry.catalog,
                    entry.item_id,
                    target,
                    placed,
                    gap=rule.gap_cm,
                    companion_pairs=pairs,
                    extra_check=extra_check,
                )
            else:
                result = place_beside(
                    room,
                    entry.catalog,
                    entry.item_id,
                    target,
                    placed,
                    end=rule.attach_end,
                    gap=rule.gap_cm,
                    companion_pairs=pairs,
                    extra_check=extra_check,
                )
            if result["success"]:
                remember(result["placed"], None)
                if result.get("companion_pair"):
                    pairs.add(result["companion_pair"])
            else:
                failed.append(_failure(entry, result))
            continue

        sides: list[str] | None = None
        if rule.attach == "opposite":
            target = find_target(rule.attach_to)
            target_side = side_by_id.get(target.id) if target is not None else None
            if target_side is not None:
                sides = [_OPPOSITE_SIDE[target_side]]

        result = place_against_wall(
            room,
            entry.catalog,
            entry.item_id,
            placed,
            sides=sides,
            margin_cm=margin_cm,
            companion_pairs=pairs,
            extra_check=extra_check,
        )
        if not result["success"] and sides is not None:
            # 對面牆放不下時退回一般貼牆，但仍然不允許浮在房間中央。
            result = place_against_wall(
                room,
                entry.catalog,
                entry.item_id,
                placed,
                margin_cm=margin_cm,
                companion_pairs=pairs,
                extra_check=extra_check,
            )
        if result["success"]:
            remember(result["placed"], result.get("side"))
        else:
            failed.append(_failure(entry, result))

    return {"placed": placed, "failed": failed}


def _failure(entry: _Pending, result: dict) -> dict:
    return {
        "id": entry.item_id,
        "type": entry.catalog.type,
        "reason": result.get("reason") or "找不到合法擺放位置",
        "reason_detail": result.get("reason_detail"),
    }


__all__ = [
    "PlacementRule",
    "ROOM_RULES",
    "WALL_SIDES",
    "ExtraCheck",
    "WallCandidate",
    "door_swing_boxes",
    "free_spans",
    "openings_on_wall",
    "place_against_wall",
    "place_beside",
    "place_in_front_of",
    "place_at_center",
    "place_around",
    "place_room",
    "rank_wall_candidates",
    "rule_for",
    "opposite_side",
    "side_for_rotation",
    "wall_length",
    "wall_rotation",
]
