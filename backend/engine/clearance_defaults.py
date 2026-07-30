"""家具詳細類型的預設淨空規則。

此模組提供 opt-in API；正式第 6 步 adapter 已明確呼叫
``catalog_with_default_clearance`` 補預設。單品已帶 clearance / clearance_spec 時永遠優先。
"""
from dataclasses import replace

from backend.engine.models import ClearanceSpec, ClearanceZone, FurnitureCatalogItem


def _operation(ideal: float, floor: float, reason: str) -> ClearanceZone:
    return ClearanceZone(
        side="front",
        kind="operation",
        ideal_cm=ideal,
        floor_cm=floor,
        reason=reason,
    )


def _access(ideal: float, floor: float, reason: str) -> ClearanceZone:
    return ClearanceZone(
        side="front",
        kind="access",
        ideal_cm=ideal,
        floor_cm=floor,
        reason=reason,
    )


def _bed_side_spec() -> ClearanceSpec:
    """床左右長側：至少一側達最低；床尾不算側。"""
    return ClearanceSpec(
        mode="any",
        enforce_floor=True,
        zones=[
            ClearanceZone(side="left", kind="access", ideal_cm=75, floor_cm=60, reason="上下床"),
            ClearanceZone(side="right", kind="access", ideal_cm=75, floor_cm=60, reason="上下床"),
        ],
    )


def _dining_seating_spec(
    sides: tuple[str, ...] = ("front", "back", "left", "right"),
) -> ClearanceSpec:
    """餐桌預設四面皆可能有椅；呼叫端可改傳較少面以排除靠牆無椅側。"""
    return ClearanceSpec(
        mode="all",
        enforce_floor=True,
        zones=[
            ClearanceZone(side=side, kind="access", ideal_cm=75, floor_cm=60, reason="拉椅入座")
            for side in sides
        ],
    )


# 鍵使用原始 normalized_type，不先經 family_of() 合併。
DEFAULT_CLEARANCE_BY_TYPE: dict[str, ClearanceZone] = {
    "wardrobe": _operation(90, 50, "門扇開啟"),
    "pax-wardrobe": _operation(90, 50, "門扇開啟"),
    "cabinet-cupboard": _operation(90, 50, "門扇開啟"),
    "cabinets-cupboard": _operation(90, 50, "門扇開啟"),
    "storage-solution-system": _operation(90, 50, "門扇開啟"),
    "chests-of-drawer": _operation(90, 60, "抽屜拉出"),
    "sideboard": _operation(90, 60, "門片或抽屜開啟"),
    "tv-bench": _operation(60, 45, "門片或抽屜開啟"),
    "tv-media-furniture": _operation(60, 45, "門片或抽屜開啟"),
    "display-cabinet": _operation(60, 45, "玻璃門開啟"),
    "shoe-cabinet": _operation(75, 50, "翻斗門開啟"),
    "mirror-cabinet": _operation(60, 45, "鏡門開啟"),
    "storage-furniture": _operation(60, 45, "收納門片開啟"),
    "bookcase": _access(75, 40, "站立取物"),
    "shelving-unit": _access(75, 40, "站立取物"),
    "desk": _access(105, 75, "拉椅入座"),
    "clothes-rack": _access(45, 30, "取掛衣物"),
}

DEFAULT_CLEARANCE_SPEC_BY_TYPE: dict[str, ClearanceSpec] = {
    "bed": _bed_side_spec(),
    "bed-frame": _bed_side_spec(),
    "mattress": _bed_side_spec(),
    "dining-table": _dining_seating_spec(),
    "table": _dining_seating_spec(),
    "bar-table": _dining_seating_spec(("front", "back")),
}


def default_clearance_for_type(normalized_type: str | None) -> ClearanceZone | None:
    """依家具原始詳細類型回傳一份獨立預設；未知類型回 None。"""
    default = DEFAULT_CLEARANCE_BY_TYPE.get(str(normalized_type or ""))
    return replace(default) if default is not None else None


def default_clearance_spec_for_type(normalized_type: str | None) -> ClearanceSpec | None:
    """多面規則預設；sofa-bed 等故意不列入。"""
    default = DEFAULT_CLEARANCE_SPEC_BY_TYPE.get(str(normalized_type or ""))
    if default is None:
        return None
    return ClearanceSpec(
        mode=default.mode,
        enforce_floor=default.enforce_floor,
        zones=[replace(zone) for zone in default.zones],
    )


def catalog_with_default_clearance(
    catalog: FurnitureCatalogItem,
) -> FurnitureCatalogItem:
    """單品指定優先；沒有單品值時才補類型預設，且不修改原物件。"""
    if catalog.clearance_spec is not None or catalog.clearance is not None:
        return catalog
    spec = default_clearance_spec_for_type(catalog.type)
    if spec is not None:
        return replace(catalog, clearance_spec=spec)
    default = default_clearance_for_type(catalog.type)
    return replace(catalog, clearance=default) if default is not None else catalog
