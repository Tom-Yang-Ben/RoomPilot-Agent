"""家具型錄轉接層：把家具資料庫項目轉成擺放引擎的型錄物件。

型錄、Python 引擎與前端 payload 全程使用公分，不在這裡換算單位。
淨空（clearance）依家具類型給預設值，家具資料庫本身沒有這個欄位。
"""
from __future__ import annotations

import re

from ..engine.models import ClearanceZone, FurnitureCatalogItem
from .placement_surface import FLOOR_COVERING, TABLETOP, WALL, placement_surface_for

# IKEA 名稱裡的尺寸,如「90x55 公分」「140x200」「80x30x202 cm」
_NAME_DIMS = re.compile(
    r"(\d{2,3}(?:\.\d)?)\s*(?:cm)?\s*[xX×*]\s*"
    r"(\d{2,3}(?:\.\d)?)\s*(?:cm)?"
    r"(?:\s*[xX×*]\s*(\d{2,3}(?:\.\d)?)\s*(?:cm)?)?"
)
_SINGLE_DIM = re.compile(r"(\d{2,3}(?:\.\d)?)\s*(?:cm|公分)")

# 各類型的合理平面尺寸範圍與預設值(cm):(寬min, 寬max, 深min, 深max, (預設寬, 深, 高))
# 資料庫 620/1509 件缺寬或深、另有 3.5cm 沙發這類鬼值(2026-07-06 統計),
# 名稱內的尺寸反而可靠(894 件有、僅 5 件與 DB 衝突) —— 修補順序:DB 合理值 > 名稱 > 類型預設。
_SIZE_RULES: dict[str, tuple[float, float, float, float, tuple[float, float, float]]] = {
    "sofa": (120, 400, 60, 130, (200, 90, 80)),
    "sofa-bed": (120, 400, 60, 130, (200, 90, 80)),
    "armchair": (55, 120, 55, 110, (80, 80, 90)),
    "coffee-table": (50, 140, 40, 95, (90, 55, 45)),
    "tv-bench": (80, 300, 30, 60, (160, 40, 50)),
    "bookcase": (40, 200, 20, 60, (80, 30, 180)),
    "bed": (80, 220, 170, 230, (160, 200, 50)),
    "bed-frame": (80, 220, 170, 230, (160, 200, 50)),
    "bedside-table": (30, 70, 30, 60, (45, 40, 55)),
    "desk": (80, 200, 50, 90, (120, 60, 75)),
    "office-chair": (50, 90, 50, 90, (65, 65, 100)),
    "dining-table": (60, 250, 60, 110, (140, 80, 75)),
    "dining-chair": (35, 65, 40, 65, (45, 50, 90)),
    "sideboard": (80, 250, 30, 60, (140, 40, 80)),
    "wardrobe": (50, 300, 40, 70, (100, 60, 200)),
    "large-medium-rug": (130, 400, 90, 300, (200, 140, 1)),
    "runner-small-rug": (50, 250, 40, 200, (120, 80, 1)),
    "wall-shelf": (30, 200, 15, 40, (80, 25, 25)),
    "flower-pots-planter": (10, 90, 10, 90, (35, 35, 80)),
    "floor-lamp": (15, 80, 15, 80, (35, 35, 145)),
    "curtain": (80, 500, 5, 30, (240, 12, 240)),
    "mirror": (10, 250, 1, 12, (60, 3, 90)),
    "large-mirror": (20, 250, 1, 12, (78, 3, 196)),
    "standing-mirror": (20, 250, 1, 18, (50, 4, 160)),
    "wall-mirror": (10, 250, 1, 12, (60, 3, 90)),
    "fridge-freezer": (45, 100, 45, 85, (60, 65, 180)),
    "dishwasher": (45, 75, 45, 75, (60, 60, 82)),
    "extractor-hood": (50, 120, 25, 70, (60, 45, 25)),
    "oven": (45, 80, 45, 75, (60, 55, 60)),
    "microwave": (35, 70, 25, 55, (50, 40, 30)),
    "toaster": (20, 55, 15, 45, (36, 28, 24)),
    "small-kitchen-appliance": (12, 80, 10, 70, (32, 28, 25)),
    "electric-fan": (20, 80, 20, 80, (35, 35, 80)),
    "air-conditioner": (50, 120, 15, 40, (80, 25, 30)),
    "air-purifier": (20, 60, 20, 60, (35, 35, 60)),
    "robot-vacuum": (25, 45, 25, 45, (35, 35, 10)),
    "vacuum-cleaner": (20, 80, 15, 60, (30, 25, 100)),
    "washing-machine": (45, 75, 45, 75, (60, 60, 85)),
    "iron": (18, 35, 8, 20, (28, 12, 14)),
    "hair-dryer": (15, 35, 8, 25, (25, 10, 22)),
}

_THIN_MIRROR_TYPES = {"mirror", "large-mirror", "standing-mirror", "wall-mirror"}
_APPLIANCE_HEIGHT_LIMITS = {
    "small-kitchen-appliance": 55,
    "toaster": 45,
    "microwave": 55,
    "oven": 75,
    "extractor-hood": 70,
    "dishwasher": 95,
    "washing-machine": 100,
    "robot-vacuum": 20,
    "iron": 22,
    "hair-dryer": 35,
}
_SMALL_APPLIANCE_DEFAULTS: list[tuple[tuple[str, ...], tuple[float, float, float]]] = [
    (("induction hob", "cooktop", "matmassig", "vilsta", "blixtsnabb", "kolstan"), (59, 52, 6)),
    (("rice cooker", "multicooker", "cooker"), (28, 28, 25)),
    (("kettle", "electric hot water", "stagg ekg"), (22, 18, 24)),
    (("toaster",), (32, 22, 22)),
    (("coffee maker", "espresso", "coffee machine"), (25, 30, 35)),
    (("blender", "mixer"), (18, 18, 38)),
    (("air fryer",), (32, 32, 36)),
    (("utensil", "kitchen utensils"), (35, 25, 18)),
]


def _small_appliance_size(name: str, dims: list[float]) -> tuple[float, float, float] | None:
    lowered = name.lower()
    single_match = _SINGLE_DIM.search(lowered)
    single_dim = float(single_match.group(1)) if single_match else None

    if "induction hob" in lowered or "cooktop" in lowered or " hob" in lowered:
        width = single_dim or (dims[0] if dims else 59.0)
        return (width, 52.0, 6.0)

    for keywords, default_size in _SMALL_APPLIANCE_DEFAULTS:
        if any(keyword in lowered for keyword in keywords):
            return default_size

    if len(dims) >= 3:
        return (dims[0], dims[1], dims[2])
    if len(dims) >= 2:
        return (dims[0], dims[1], 25.0)
    return None


def _positive(value) -> float | None:
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def sanitize_size_cm(item: dict) -> dict:
    """修補一件家具的尺寸(cm)。DB 值合理就用;否則依序用名稱尺寸、類型預設。"""
    item_type = item.get("normalized_type") or ""
    rule = _SIZE_RULES.get(item_type)
    raw = item.get("size_cm") or {}
    width = _positive(raw.get("width"))
    depth = _positive(raw.get("depth"))
    height = _positive(raw.get("height"))
    name = f"{item.get('name_zh_raw') or ''} {item.get('name_en') or ''}"
    match = _NAME_DIMS.search(name)
    dims = [float(g) for g in match.groups() if g] if match else []

    if item_type == "small-kitchen-appliance":
        appliance_size = _small_appliance_size(name, dims)
        if appliance_size:
            width, depth, height = appliance_size
            return {"width": round(width, 1), "depth": round(depth, 1), "height": round(height, 1)}

    if item_type in _THIN_MIRROR_TYPES:
        default_w, default_d, default_h = rule[4] if rule else (60.0, 3.0, 90.0)
        if len(dims) >= 3:
            width, depth, height = dims[0], dims[1], dims[2]
        elif len(dims) >= 2:
            width, height = dims[0], dims[1]
            depth = depth if depth and depth <= 12 else default_d
        else:
            width = width or default_w
            depth = depth if depth and depth <= 12 else default_d
            if not height or height <= 5:
                height = width if width else default_h
        return {"width": round(width, 1), "depth": round(depth, 1), "height": round(height, 1)}

    def plausible(w: float | None, d: float | None) -> bool:
        if not w or not d:
            return False
        if rule is None:
            return True
        return rule[0] <= w <= rule[1] and rule[2] <= d <= rule[3]

    if not plausible(width, depth):
        if len(dims) >= 2 and plausible(dims[0], dims[1]):
            width, depth = dims[0], dims[1]
            if len(dims) >= 3 and not height:
                height = dims[2]
        elif len(dims) >= 2 and plausible(dims[1], dims[0]):
            width, depth = dims[1], dims[0]
        elif rule is not None:
            default_w, default_d, _ = rule[4]
            width = width if (width and rule[0] <= width <= rule[1]) else default_w
            depth = depth if (depth and rule[2] <= depth <= rule[3]) else default_d
        else:
            width = width or 120.0
            depth = depth or 60.0

    height_limit = _APPLIANCE_HEIGHT_LIMITS.get(item_type)
    if height_limit and (not height or height <= 2 or height > height_limit):
        height = rule[4][2] if rule else height_limit

    if not height or height <= 2:
        height = rule[4][2] if rule else 80.0

    return {"width": round(width, 1), "depth": round(depth, 1), "height": round(height, 1)}

# 開合淨空的類型預設(公分)——語意是「開門/抽拉需要的空間」,只給收納類。
# 沙發/床/電視櫃刻意不設:茶几本來就該放在沙發前、床頭櫃貼床,
# 設了前方淨空會把正常配置誤判成違規(2026-07-06 實測踩過這個坑)。
CLEARANCE_BY_TYPE: dict[str, ClearanceZone] = {
    "bookcase": ClearanceZone(side="front", depth=40.0),
    "sideboard": ClearanceZone(side="front", depth=40.0),
    "wardrobe": ClearanceZone(side="front", depth=50.0),
    "desk": ClearanceZone(side="front", depth=50.0),
}


# 壁掛品項的離地高度(公分)——引擎用它算垂直佔用帶,判斷平面重疊時
# 兩件家具是不是真的會撞在一起。型錄沒有逐筆的安裝高度，這裡給類型預設值。
#
# 數值取自台灣常見安裝慣例:層架掛在視線上方、掛鏡中心對齊站立視高、
# 浴櫃鏡櫃接在檯面上方。沒有把握的型別不要進表——留空就是落地家具(0)，
# 那是保守的一邊(會多擋，不會漏擋)。
# 注意：型別在這張表裡不代表「這個型別都是壁掛」——高度只作用在
# placement_surface_for() 判定為壁掛的品項（多數靠名稱判準的子集，例如
# cabinet-cupboard 146 筆裡只有 BESTÅ 上牆式那 10 筆吃得到 130）。
# 2026-08-03 Ben 拍板全套。
MOUNT_HEIGHT_BY_TYPE: dict[str, float] = {
    "wall-shelf": 120.0,
    "mirror": 100.0,
    "large-mirror": 90.0,
    "mirror-cabinet": 85.0,
    # 上牆式收納櫃：慣例頂緣 ≤200、櫃體多 64 高 → 底緣 130；沙發背、
    # 餐邊櫃（~85）上方可共存。
    "cabinet-cupboard": 130.0,
    # 浮動牆架與名稱命中層板的層架單元，與 wall-shelf 同慣例。
    "bookcase": 120.0,
    "shelving-unit": 120.0,
    # 壁掛花盆掛視線高度，沙發與矮櫃上方可共存。
    "planter": 120.0,
    # 壁掛床邊桌對齊床墊面（台灣床架＋床墊約 45–55）。
    "bedside-table": 45.0,
    # 壁掛衣帽架：大衣下襬要離地。
    "clothes-rack": 150.0,
}


# 垂直帶重疊、但實務上本來就該塞在一起的成對例外。只放高度表達不了的關係。
#
# 「成組」不等於「可重疊」:backend/agent/knowledge.py 的 COMPANION_OF 也把
# 床頭櫃配床、茶几配沙發列為成組,但那是選件關係——它們該並排,不該疊在
# 一起。這裡只收真的推得進去的那兩對。
#
# 表刻意收得很緊。多放一對就是多開一個重疊漏洞,而漏擋比多擋難發現。
_OVERLAP_ALLOWED_PAIRS: tuple[tuple[str, str], ...] = (
    ("dining-chair", "dining-table"),
    ("office-chair", "desk"),
)


def _build_overlap_allowed() -> dict[str, frozenset[str]]:
    """把配對展開成雙向查表,避免只寫單向造成 A 查得到 B、B 查不到 A。"""
    pairs: dict[str, set[str]] = {}
    for left, right in _OVERLAP_ALLOWED_PAIRS:
        pairs.setdefault(left, set()).add(right)
        pairs.setdefault(right, set()).add(left)
    return {key: frozenset(value) for key, value in pairs.items()}


OVERLAP_ALLOWED_BY_TYPE: dict[str, frozenset[str]] = _build_overlap_allowed()


def catalog_item_from_scene_object(
    item_type: str | None,
    name: str | None,
    width_cm: float,
    depth_cm: float,
    height_cm: float,
) -> FurnitureCatalogItem:
    """場景物件轉為公分引擎型錄物件，不做單位換算。"""
    key = item_type or ""
    surface = placement_surface_for(item_type, name)
    return FurnitureCatalogItem(
        type=item_type or "furniture",
        name=name or item_type or "家具",
        width=width_cm,
        depth=depth_cm,
        height=height_cm,
        clearance=CLEARANCE_BY_TYPE.get(key),
        mount_height_cm=MOUNT_HEIGHT_BY_TYPE.get(key, 0.0) if surface == WALL else 0.0,
        # 地毯與桌面擺飾不佔垂直空間:家具站在它們上面是正常的。
        occupies_floor_space=surface not in (FLOOR_COVERING, TABLETOP),
        overlap_allowed_types=OVERLAP_ALLOWED_BY_TYPE.get(key, frozenset()),
    )
