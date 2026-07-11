"""家具型錄轉接層:把 sf3d 風格資料庫的家具項目轉成 furniture_engine 的型錄物件。

公分 → 公尺的換算只發生在這裡(引擎內部一律公尺)。
淨空(clearance)依家具類型給預設值 —— 風格資料庫本身沒有這個欄位。
"""
from __future__ import annotations

import re

from ..engine.models import ClearanceZone, FurnitureCatalogItem

# IKEA 名稱裡的尺寸,如「90x55 公分」「140x200」「80x30x202 cm」
_NAME_DIMS = re.compile(r"(\d{2,3}(?:\.\d)?)\s*[xX×]\s*(\d{2,3}(?:\.\d)?)(?:\s*[xX×]\s*(\d{2,3}(?:\.\d)?))?")

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
}


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

    def plausible(w: float | None, d: float | None) -> bool:
        if not w or not d:
            return False
        if rule is None:
            return True
        return rule[0] <= w <= rule[1] and rule[2] <= d <= rule[3]

    if not plausible(width, depth):
        name = f"{item.get('name_zh_raw') or ''} {item.get('name_en') or ''}"
        match = _NAME_DIMS.search(name)
        dims = [float(g) for g in match.groups() if g] if match else []
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

    if not height or height <= 2:
        height = rule[4][2] if rule else 80.0

    return {"width": round(width, 1), "depth": round(depth, 1), "height": round(height, 1)}

# 開合淨空的類型預設(公分,2026-07-11 隨引擎公分化)——語意是「開門/抽拉需要的空間」,只給收納類。
# 沙發/床/電視櫃刻意不設:茶几本來就該放在沙發前、床頭櫃貼床,
# 設了前方淨空會把正常配置誤判成違規(2026-07-06 實測踩過這個坑)。
CLEARANCE_BY_TYPE: dict[str, ClearanceZone] = {
    "bookcase": ClearanceZone(side="front", depth=40.0),
    "sideboard": ClearanceZone(side="front", depth=40.0),
    "wardrobe": ClearanceZone(side="front", depth=50.0),
    "desk": ClearanceZone(side="front", depth=50.0),
}


def catalog_item_from_scene_object(
    item_type: str | None,
    name: str | None,
    width_cm: float,
    depth_cm: float,
    height_cm: float,
) -> FurnitureCatalogItem:
    """場景物件(公分) → 引擎型錄物件(公分,含類型預設淨空)。引擎已公分化,不再換算。"""
    return FurnitureCatalogItem(
        type=item_type or "furniture",
        name=name or item_type or "家具",
        width=width_cm,
        depth=depth_cm,
        height=height_cm,
        clearance=CLEARANCE_BY_TYPE.get(item_type or ""),
    )
