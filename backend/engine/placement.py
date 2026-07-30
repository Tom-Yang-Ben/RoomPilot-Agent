"""確定性家具擺放：候選搜尋後由引擎合法性驗證。"""
from __future__ import annotations

from collections.abc import Iterator

from backend.engine.clearance import (
    CompanionPairs,
    check_placement_with_clearance as check_placement,
    validate_placement_with_clearance,
)
from backend.engine.geometry import check_placement as check_body_placement
from backend.engine.models import FurnitureCatalogItem, PlacedFurniture, Room


_SEARCH_STEP_CM = 15.0


def _axis_points(low: float, high: float, center: float) -> list[float]:
    """由中心向兩側產生固定步距座標，最後補上兩端。"""
    if low > high:
        return []
    middle = min(max(center, low), high)
    values = [middle]
    offset = _SEARCH_STEP_CM
    while middle - offset >= low or middle + offset <= high:
        if middle - offset >= low:
            values.append(middle - offset)
        if middle + offset <= high:
            values.append(middle + offset)
        offset += _SEARCH_STEP_CM
    values.extend((low, high))

    unique: list[float] = []
    seen: set[float] = set()
    for value in values:
        rounded = round(value, 4)
        if rounded not in seen:
            seen.add(rounded)
            unique.append(value)
    return unique


def _candidate_placements(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
) -> Iterator[PlacedFurniture]:
    """中心優先，再掃四面牆與室內 15cm 網格；順序完全確定。"""
    seen: set[tuple[float, float, int]] = set()
    for rotation in (0, 90, 180, 270):
        if rotation in (90, 270):
            footprint_w, footprint_d = catalog_item.depth, catalog_item.width
        else:
            footprint_w, footprint_d = catalog_item.width, catalog_item.depth

        def emit(x: float, y: float) -> Iterator[PlacedFurniture]:
            key = (round(x, 4), round(y, 4), rotation)
            if key in seen:
                return
            seen.add(key)
            yield PlacedFurniture(
                id=item_id,
                catalog=catalog_item,
                pos_x=x,
                pos_y=y,
                rotation=rotation,
            )

        # 即使家具比房間大也試中心，讓失敗原因能明確回報出界。
        yield from emit(room.width / 2, room.depth / 2)

        min_x, max_x = footprint_w / 2, room.width - footprint_w / 2
        min_y, max_y = footprint_d / 2, room.depth - footprint_d / 2
        xs = _axis_points(min_x, max_x, room.width / 2)
        ys = _axis_points(min_y, max_y, room.depth / 2)
        if not xs or not ys:
            continue

        # 四面牆先掃；實際牆厚、內牆、淨空仍由 validator 擋下。
        for x in xs:
            yield from emit(x, min_y)
            yield from emit(x, max_y)
        for y in ys:
            yield from emit(min_x, y)
            yield from emit(max_x, y)

        # 牆邊都不行時補掃室內，解決舊版 95cm 固定點漏掉窄縫的問題。
        for y in ys:
            for x in xs:
                yield from emit(x, y)


def place_furniture(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
    existing: list[PlacedFurniture],
    *,
    companion_pairs: CompanionPairs | None = None,
) -> dict:
    """找到第一個合法候選；保留舊 reason，另提供結構化 reason_detail。"""
    attempted = 0
    last_issue = None
    for candidate in _candidate_placements(room, catalog_item, item_id):
        attempted += 1
        validation = validate_placement_with_clearance(
            candidate,
            room,
            existing,
            companion_pairs=companion_pairs,
        )
        if validation.legal:
            return {
                "success": True,
                "placed": candidate,
                "reason": None,
                "reason_detail": None,
                "warnings": [issue.to_dict() for issue in validation.warnings],
            }
        last_issue = validation.errors[0]

    detail = {
        "code": "no_legal_position",
        "message_zh": "找不到合法擺放位置",
        "item_id": item_id,
        "rule": "placement_search",
        "attempted_candidates": attempted,
    }
    if last_issue is not None:
        detail["last_issue"] = last_issue.to_dict()
    return {
        "success": False,
        "placed": None,
        "reason": "找不到合法擺放位置",
        "reason_detail": detail,
        "warnings": [],
    }


def place_overlay_on_furniture(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
    target: PlacedFurniture,
) -> dict:
    """地毯等覆蓋物與目標同座標，只驗證本體、牆與房間邊界。"""
    candidate = PlacedFurniture(
        id=item_id,
        catalog=catalog_item,
        pos_x=target.pos_x,
        pos_y=target.pos_y,
        rotation=target.rotation,
    )
    reason = check_body_placement(candidate, room, [])
    return {
        "success": reason is None,
        "placed": candidate if reason is None else None,
        "reason": reason,
    }


def place_adjacent_to_furniture(
    room: Room,
    catalog_item: FurnitureCatalogItem,
    item_id: str,
    target: PlacedFurniture,
    existing: list[PlacedFurniture],
    gap: float = 12.0,
    *,
    companion_pairs: CompanionPairs | None = None,
) -> dict:
    """把燈具、植栽等配件放在主家具四周。"""
    target_width = target.catalog.width
    target_depth = target.catalog.depth
    item_width = catalog_item.width
    item_depth = catalog_item.depth
    side_x = target_width / 2 + item_width / 2 + gap
    side_y = target_depth / 2 + item_depth / 2 + gap
    offsets = (
        (side_x, 0),
        (-side_x, 0),
        (side_x, target_depth * 0.32),
        (side_x, -target_depth * 0.32),
        (-side_x, target_depth * 0.32),
        (-side_x, -target_depth * 0.32),
        (0, side_y),
        (0, -side_y),
        (target_width * 0.32, side_y),
        (-target_width * 0.32, side_y),
        (target_width * 0.32, -side_y),
        (-target_width * 0.32, -side_y),
    )
    for dx, dy in offsets:
        candidate = PlacedFurniture(
            id=item_id,
            catalog=catalog_item,
            pos_x=target.pos_x + dx,
            pos_y=target.pos_y + dy,
            rotation=target.rotation,
        )
        reason = check_placement(
            candidate,
            room,
            existing,
            companion_pairs=companion_pairs,
        )
        if reason is None:
            return {"success": True, "placed": candidate, "reason": None}
    return {"success": False, "placed": None, "reason": "主家具周圍沒有合法的軟裝位置"}


def place_furniture_batch(
    room: Room,
    items: list[tuple[FurnitureCatalogItem, str]],
    *,
    companion_pairs: CompanionPairs | None = None,
) -> dict:
    """依序放多件家具；失敗項目同時保留字串與結構化原因。"""
    placed: list[PlacedFurniture] = []
    failed: list[dict] = []

    for catalog_item, item_id in items:
        result = place_furniture(
            room,
            catalog_item,
            item_id,
            placed,
            companion_pairs=companion_pairs,
        )
        if result["success"]:
            placed.append(result["placed"])
        else:
            failed.append(
                {
                    "id": item_id,
                    "reason": result["reason"],
                    "reason_detail": result["reason_detail"],
                }
            )

    return {"placed": placed, "failed": failed}
