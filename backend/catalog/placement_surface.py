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

# 型錄裡有一批配件被標成家具型（QA 2026-08-01 #11）：滑鼠墊記成 stool-bench、
# 層板記成 shelving-unit。normalized_type 由 Kai 的匯入層決定，這裡不改它，只
# 用品名把明顯的配件降級到非落地面，讓它們不再帶著 footprint 進碰撞與淨空。
#
# 詞彙刻意收得很緊。實測「坐墊」「椅墊」在型錄裡幾乎都是真家具的配備描述
# （「坐墊餐椅」「茶几配四個坐墊」「超大坐墊辦公椅」共 40 筆），拿來當配件
# 判準會把真家具踢出配置——誤刪一張餐椅比留下一個滑鼠墊糟糕得多。
_TABLETOP_NAME_HINTS = (
    "滑鼠墊",
    "杯墊",
    "桌墊",
    "餐墊",
    "mouse pad",
    "mousepad",
    "place mat",
    "placemat",
    "coaster",
)

_WALL_NAME_HINTS = (
    "層板",
    "壁掛",
    "上牆式",
    "壁櫃",
    "吊櫃",
    "浮動",
    "shelf board",
    "wall panel",
    "floating",
    "wall-mount",
    "wall mount",
)

# 這些型別即使名稱帶壁掛字眼也維持落地：壁掛折疊桌的桌面下要容納椅子
# 與腿部空間，佔用地面使用權才符合實際使用（2026-08-03 Ben 拍板高度表
# 時一併決定）。實測命中：floating desk 1 筆、NORBERG 壁掛折疊桌 1 筆。
_WALL_HINT_EXCLUDED_TYPES = frozenset({"desk", "bar-table"})

# 「附層板電競桌」「床邊桌，附 1 抽屜附層板」的主體是桌子，層板只是配備。
# 出現「附」就代表那個詞在描述配備而不是品項本身。
_ACCESSORY_AS_FEATURE_MARKERS = ("附", "with shelf", "including shelf")


def _name_hint_surface(name: str) -> str | None:
    lowered = name.strip().lower()
    if not lowered:
        return None
    if any(marker in lowered for marker in _ACCESSORY_AS_FEATURE_MARKERS):
        return None
    if any(hint in lowered for hint in _TABLETOP_NAME_HINTS):
        return TABLETOP
    if any(hint in lowered for hint in _WALL_NAME_HINTS):
        return WALL
    return None


def placement_surface_for(normalized_type: str | None, name: str | None = None) -> str:
    """回傳擺放面。

    型別表優先；型別看起來是落地家具、但品名明擺著是配件時才用品名降級。
    未知型別一律當落地家具（保守）。
    """
    key = str(normalized_type or "").strip().lower()
    if key in _TABLETOP_TYPES:
        return TABLETOP
    if key in _WALL_TYPES:
        return WALL
    if key in _FLOOR_COVERING_TYPES:
        return FLOOR_COVERING
    hinted = _name_hint_surface(str(name or ""))
    if hinted == WALL and key in _WALL_HINT_EXCLUDED_TYPES:
        return FLOOR
    return hinted or FLOOR


def is_floor_furniture(normalized_type: str | None, name: str | None = None) -> bool:
    """只有落地家具才需要走牆界、碰撞與淨空計算。"""
    return placement_surface_for(normalized_type, name) == FLOOR
