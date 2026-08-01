"""家具擺放面分類：判斷型錄品項是「落地家具」還是桌面／壁掛／地面覆蓋物。

第 6 步的淨空與碰撞只對落地家具有意義。以前型錄沒有這個資訊，18 公分的玻璃花瓶、
抱枕、壁掛層架都會被當成落地家具去算牆界與淨空，然後「放不下」而卡在待處理清單。

這裡只做分類，不做任何幾何決策——合法位置仍然只由 `backend/engine/` 判定。
"""

from __future__ import annotations

FLOOR = "floor"
TABLETOP = "tabletop"
WALL = "wall"
FLOOR_COVERING = "floor_covering"

# 桌面／層板上的擺飾與軟件，沒有自己的落地佔地。
_TABLETOP_TYPES = frozenset(
    {
        "vase",
        "decoration",
        "pillow-cushion",
        "storage-boxes-basket",
        "sheepskins-cowhide",
    }
)

# 壁掛品項，佔的是牆面不是地板。
_WALL_TYPES = frozenset(
    {
        "mirror",
        "large-mirror",
        "mirror-cabinet",
        "wall-shelf",
    }
)

# 鋪在地板上，但不佔用淨空、也不與家具碰撞。
_FLOOR_COVERING_TYPES = frozenset(
    {
        "rug",
        "large-medium-rug",
        "runner-small-rug",
        "handmade-rug",
        "outdoor-rug",
        "round-rug",
        "door-mat",
    }
)

PLACEMENT_SURFACES = (FLOOR, TABLETOP, WALL, FLOOR_COVERING)


def placement_surface_for(normalized_type: str | None) -> str:
    """回傳該 normalized_type 的擺放面；未知型別一律當落地家具（保守）。"""
    key = str(normalized_type or "").strip().lower()
    if key in _TABLETOP_TYPES:
        return TABLETOP
    if key in _WALL_TYPES:
        return WALL
    if key in _FLOOR_COVERING_TYPES:
        return FLOOR_COVERING
    return FLOOR


def is_floor_furniture(normalized_type: str | None) -> bool:
    """只有落地家具才需要走牆界、碰撞與淨空計算。"""
    return placement_surface_for(normalized_type) == FLOOR
