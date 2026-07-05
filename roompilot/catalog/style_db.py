"""家具型錄轉接層:把 sf3d 風格資料庫的家具項目轉成 furniture_engine 的型錄物件。

公分 → 公尺的換算只發生在這裡(引擎內部一律公尺)。
淨空(clearance)依家具類型給預設值 —— 風格資料庫本身沒有這個欄位。
"""
from __future__ import annotations

from ..engine.models import ClearanceZone, FurnitureCatalogItem

# 開合淨空的類型預設(公尺)——語意是「開門/抽拉需要的空間」,只給收納類。
# 沙發/床/電視櫃刻意不設:茶几本來就該放在沙發前、床頭櫃貼床,
# 設了前方淨空會把正常配置誤判成違規(2026-07-06 實測踩過這個坑)。
CLEARANCE_BY_TYPE: dict[str, ClearanceZone] = {
    "bookcase": ClearanceZone(side="front", depth=0.4),
    "sideboard": ClearanceZone(side="front", depth=0.4),
    "wardrobe": ClearanceZone(side="front", depth=0.5),
    "desk": ClearanceZone(side="front", depth=0.5),
}


def catalog_item_from_scene_object(
    item_type: str | None,
    name: str | None,
    width_cm: float,
    depth_cm: float,
    height_cm: float,
) -> FurnitureCatalogItem:
    """場景物件(公分) → 引擎型錄物件(公尺,含類型預設淨空)。"""
    return FurnitureCatalogItem(
        type=item_type or "furniture",
        name=name or item_type or "家具",
        width=width_cm / 100,
        depth=depth_cm / 100,
        height=height_cm / 100,
        clearance=CLEARANCE_BY_TYPE.get(item_type or ""),
    )
