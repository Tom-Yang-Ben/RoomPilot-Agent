"""家具本體、開合空間與舒適使用空間的確定性驗證。"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.affinity import rotate
from shapely.geometry import Polygon, box

from backend.engine.geometry import (
    furniture_polygon,
    hits_furniture,
    hits_wall,
    out_of_bounds,
    room_polygon,
    wall_polygon,
)
from backend.engine.models import (
    ClearanceKind,
    ClearanceSpec,
    ClearanceZone,
    IssueSeverity,
    PlacementIssue,
    PlacementValidation,
    PlacedFurniture,
    Room,
    resolved_clearance_spec,
)


CompanionPairs = set[frozenset[str]]
_OVERLAP_EPSILON_CM2 = 1e-6
_SIDE_OFFSETS = {
    "front": (0, 1),
    "back": (0, -1),
    "left": (-1, 0),
    "right": (1, 0),
}


@dataclass(frozen=True)
class _ZoneConflict:
    code: str
    message_zh: str
    related_item_id: str | None = None


def _positive_overlap(first: Polygon, second: Polygon) -> bool:
    """只有正面積重疊才算衝突；邊界剛好相接不算。"""
    return first.intersection(second).area > _OVERLAP_EPSILON_CM2


def _is_companion(
    item_id: str,
    other_id: str,
    companion_pairs: CompanionPairs | None,
) -> bool:
    return bool(companion_pairs and frozenset((item_id, other_id)) in companion_pairs)


def clearance_polygon(
    item: PlacedFurniture,
    *,
    depth_cm: float | None = None,
    zone: ClearanceZone | None = None,
) -> Polygon | None:
    """計算單一淨空矩形；預設使用最低值（相容 v0.1 depth）。"""
    clearance = zone if zone is not None else item.catalog.clearance
    if clearance is None:
        return None

    depth = float(clearance.floor_cm if depth_cm is None else depth_cm)
    hw, hd = item.catalog.width / 2, item.catalog.depth / 2
    dx, dy = _SIDE_OFFSETS[clearance.side]

    if dy:
        inner = item.pos_y + dy * hd
        outer = inner + dy * depth
        polygon = box(
            item.pos_x - hw,
            min(inner, outer),
            item.pos_x + hw,
            max(inner, outer),
        )
    else:
        inner = item.pos_x + dx * hw
        outer = inner + dx * depth
        polygon = box(
            min(inner, outer),
            item.pos_y - hd,
            max(inner, outer),
            item.pos_y + hd,
        )

    if item.rotation:
        polygon = rotate(polygon, item.rotation, origin=(item.pos_x, item.pos_y))
    return polygon


def _operation_zones(item: PlacedFurniture) -> list[ClearanceZone]:
    spec = resolved_clearance_spec(item.catalog)
    if spec is None:
        return []
    return [zone for zone in spec.zones if zone.kind == "operation"]


def _zone_conflict(
    item: PlacedFurniture,
    zone_poly: Polygon,
    room: Room,
    others: list[PlacedFurniture],
    kind: ClearanceKind,
    companion_pairs: CompanionPairs | None,
) -> _ZoneConflict | None:
    noun = "開合空間" if kind == "operation" else "舒適使用空間"
    prefix = "clearance" if kind == "operation" else "access"

    # 保留既有順序：先檢查牆，再補沒有周界牆資料時的房間邊界。
    for wall in room.walls:
        if _positive_overlap(zone_poly, wall_polygon(wall)):
            return _ZoneConflict(
                code=f"{prefix}_wall_conflict",
                message_zh=f"「{item.catalog.name}」的{noun}被牆體阻擋",
            )
    if not room_polygon(room).covers(zone_poly):
        return _ZoneConflict(
            code=f"{prefix}_boundary_conflict",
            message_zh=f"「{item.catalog.name}」的{noun}超出房間範圍",
        )

    for other in others:
        if other.id == item.id:
            continue
        if kind == "access" and _is_companion(item.id, other.id, companion_pairs):
            continue
        if _positive_overlap(zone_poly, furniture_polygon(other)):
            return _ZoneConflict(
                code=f"{prefix}_body_conflict",
                message_zh=f"「{item.catalog.name}」的{noun}與「{other.catalog.name}」衝突",
                related_item_id=other.id,
            )

        # 只有兩個必要開啟空間互撞才硬擋；舒適區可以彼此共用。
        if kind != "operation":
            continue
        for other_zone in _operation_zones(other):
            other_poly = clearance_polygon(other, zone=other_zone)
            if other_poly is not None and _positive_overlap(zone_poly, other_poly):
                return _ZoneConflict(
                    code="clearance_zone_conflict",
                    message_zh=(
                        f"「{item.catalog.name}」與「{other.catalog.name}」的開合空間互相衝突"
                    ),
                    related_item_id=other.id,
                )
    return None


def _available_depth_cm(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    kind: ClearanceKind,
    required_cm: float,
    companion_pairs: CompanionPairs | None,
    zone: ClearanceZone,
) -> float:
    """以固定次數二分搜尋可用深度，讓失敗原因能回報差幾公分。"""
    required = max(0.0, float(required_cm))
    zone_poly = clearance_polygon(item, depth_cm=required, zone=zone)
    if zone_poly is not None and _zone_conflict(
        item, zone_poly, room, others, kind, companion_pairs
    ) is None:
        return required

    low, high = 0.0, required
    for _ in range(24):
        middle = (low + high) / 2
        candidate_zone = clearance_polygon(item, depth_cm=middle, zone=zone)
        if candidate_zone is not None and _zone_conflict(
            item, candidate_zone, room, others, kind, companion_pairs
        ) is None:
            low = middle
        else:
            high = middle
    return round(low, 2)


def _clearance_issue(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    *,
    required_cm: float,
    kind: ClearanceKind,
    severity: IssueSeverity,
    rule: str,
    companion_pairs: CompanionPairs | None,
    zone: ClearanceZone,
) -> PlacementIssue | None:
    zone_poly = clearance_polygon(item, depth_cm=required_cm, zone=zone)
    if zone_poly is None:
        return None
    conflict = _zone_conflict(item, zone_poly, room, others, kind, companion_pairs)
    if conflict is None:
        return None

    available = _available_depth_cm(
        item, room, others, kind, required_cm, companion_pairs, zone
    )
    shortfall = round(max(0.0, required_cm - available), 2)
    return PlacementIssue(
        code=conflict.code,
        message_zh=conflict.message_zh,
        item_id=item.id,
        related_item_id=conflict.related_item_id,
        rule=rule,
        severity=severity,
        required_cm=round(required_cm, 2),
        available_cm=available,
        shortfall_cm=shortfall,
    )


def _zone_ok(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    zone: ClearanceZone,
    required_cm: float,
    kind: ClearanceKind,
    companion_pairs: CompanionPairs | None,
) -> bool:
    zone_poly = clearance_polygon(item, depth_cm=required_cm, zone=zone)
    if zone_poly is None:
        return False
    return _zone_conflict(item, zone_poly, room, others, kind, companion_pairs) is None


def _validate_any_mode(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    spec: ClearanceSpec,
    companion_pairs: CompanionPairs | None,
    result: PlacementValidation,
) -> bool:
    """至少一面滿足。回傳 False 表示已寫入硬錯誤並應提前結束本體淨空檢查。"""
    # any-mode 的硬門檻用 access 語意（可允許配套例外，但床預設不開配套佔側）。
    kind: ClearanceKind = "access" if all(z.kind == "access" for z in spec.zones) else "operation"
    floor_hits: list[tuple[ClearanceZone, PlacementIssue]] = []
    for zone in spec.zones:
        check_kind: ClearanceKind = zone.kind if zone.kind == "operation" else kind
        issue = _clearance_issue(
            item,
            room,
            others,
            required_cm=float(zone.floor_cm),
            kind=check_kind,
            severity="error",
            rule="clearance_floor_any",
            companion_pairs=companion_pairs,
            zone=zone,
        )
        if issue is not None:
            floor_hits.append((zone, issue))

    if len(floor_hits) == len(spec.zones):
        best = min(floor_hits, key=lambda pair: pair[1].available_cm or 0.0)[1]
        result.errors.append(
            PlacementIssue(
                code="access_any_side_unmet",
                message_zh=f"「{item.catalog.name}」未達「至少一面」最低使用空間",
                item_id=item.id,
                related_item_id=best.related_item_id,
                rule="clearance_any_side",
                severity="error",
                required_cm=best.required_cm,
                available_cm=best.available_cm,
                shortfall_cm=best.shortfall_cm,
            )
        )
        return False

    # 至少一面達最低後，若沒有任何一面達理想則警告。
    ideal_needed = any(float(z.ideal_cm) > float(z.floor_cm) for z in spec.zones)
    if ideal_needed:
        any_ideal = False
        best_ideal_issue: PlacementIssue | None = None
        for zone in spec.zones:
            check_kind = zone.kind if zone.kind == "operation" else kind
            if _zone_ok(
                item, room, others, zone, float(zone.ideal_cm), check_kind, companion_pairs
            ):
                any_ideal = True
                break
            issue = _clearance_issue(
                item,
                room,
                others,
                required_cm=float(zone.ideal_cm),
                kind=check_kind,
                severity="warning",
                rule="clearance_ideal_any",
                companion_pairs=companion_pairs,
                zone=zone,
            )
            if issue is not None and (
                best_ideal_issue is None
                or (issue.available_cm or 0) > (best_ideal_issue.available_cm or 0)
            ):
                best_ideal_issue = issue
        if not any_ideal and best_ideal_issue is not None:
            best_ideal_issue.code = "clearance_compressed"
            best_ideal_issue.message_zh = (
                f"「{item.catalog.name}」已滿足最低單側使用空間，"
                f"但距理想值仍差 {best_ideal_issue.shortfall_cm:g} 公分"
            )
            result.warnings.append(best_ideal_issue)
    return True


def _validate_all_mode(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    spec: ClearanceSpec,
    companion_pairs: CompanionPairs | None,
    result: PlacementValidation,
) -> bool:
    """每一面都要滿足。回傳 False 表示已寫入硬錯誤。"""
    for zone in spec.zones:
        hard = zone.kind == "operation" or spec.enforce_floor
        if hard:
            floor_kind: ClearanceKind = (
                "operation" if zone.kind == "operation" else "access"
            )
            floor_issue = _clearance_issue(
                item,
                room,
                others,
                required_cm=float(zone.floor_cm),
                kind=floor_kind,
                severity="error",
                rule="clearance_floor",
                companion_pairs=companion_pairs,
                zone=zone,
            )
            if floor_issue is not None:
                result.errors.append(floor_issue)
                return False

            if float(zone.ideal_cm) > float(zone.floor_cm):
                ideal_issue = _clearance_issue(
                    item,
                    room,
                    others,
                    required_cm=float(zone.ideal_cm),
                    kind=floor_kind,
                    severity="warning",
                    rule="clearance_ideal",
                    companion_pairs=companion_pairs,
                    zone=zone,
                )
                if ideal_issue is not None:
                    ideal_issue.code = "clearance_compressed"
                    noun = "開合空間" if zone.kind == "operation" else "使用空間"
                    ideal_issue.message_zh = (
                        f"「{item.catalog.name}」已滿足最低{noun}，"
                        f"但距理想值仍差 {ideal_issue.shortfall_cm:g} 公分"
                    )
                    result.warnings.append(ideal_issue)
        else:
            access_issue = _clearance_issue(
                item,
                room,
                others,
                required_cm=float(zone.ideal_cm),
                kind="access",
                severity="warning",
                rule="access_clearance",
                companion_pairs=companion_pairs,
                zone=zone,
            )
            if access_issue is not None:
                result.warnings.append(access_issue)
    return True


def clearance_conflict(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    *,
    companion_pairs: CompanionPairs | None = None,
) -> str | None:
    """相容 v0.1：只回第一條必要開啟空間錯誤字串。"""
    clearance = item.catalog.clearance
    if clearance is None or clearance.kind != "operation":
        return None
    issue = _clearance_issue(
        item,
        room,
        others,
        required_cm=float(clearance.floor_cm),
        kind="operation",
        severity="error",
        rule="clearance_floor",
        companion_pairs=companion_pairs,
        zone=clearance,
    )
    return issue.message_zh if issue else None


def _geometry_error(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
) -> PlacementIssue | None:
    if out_of_bounds(item, room):
        min_x, min_y, max_x, max_y = furniture_polygon(item).bounds
        overflow = max(0.0, -min_x, -min_y, max_x - room.width, max_y - room.depth)
        return PlacementIssue(
            code="out_of_bounds",
            message_zh="物件超出空間範圍",
            item_id=item.id,
            rule="room_boundary",
            shortfall_cm=round(overflow, 2),
        )
    if hits_wall(item, room):
        return PlacementIssue(
            code="wall_collision",
            message_zh="與牆體穿透",
            item_id=item.id,
            rule="wall_collision",
        )
    other = hits_furniture(item, others)
    if other is not None:
        return PlacementIssue(
            code="furniture_overlap",
            message_zh=f"與「{other.catalog.name}」重疊",
            item_id=item.id,
            related_item_id=other.id,
            rule="furniture_overlap",
        )
    return None


def _reverse_issues(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    companion_pairs: CompanionPairs | None,
) -> list[PlacementIssue]:
    """新家具本體不可毀掉別人的必要淨空。"""
    issues: list[PlacementIssue] = []
    body = furniture_polygon(item)
    for other in others:
        if other.id == item.id:
            continue
        spec = resolved_clearance_spec(other.catalog)
        if spec is None:
            continue

        if spec.mode == "any" and spec.enforce_floor:
            peers = [peer for peer in others if peer.id != other.id] + [item]
            probe = PlacementValidation()
            ok = _validate_any_mode(other, room, peers, spec, companion_pairs, probe)
            if not ok:
                issues.append(
                    PlacementIssue(
                        code="blocks_clearance",
                        message_zh=f"擋住了「{other.catalog.name}」必要的單側使用空間",
                        item_id=item.id,
                        related_item_id=other.id,
                        rule="reverse_clearance_any",
                    )
                )
                return issues
            continue

        for zone in spec.zones:
            hard = zone.kind == "operation" or spec.enforce_floor
            depth = float(zone.floor_cm) if hard else float(zone.ideal_cm)
            other_zone = clearance_polygon(other, depth_cm=depth, zone=zone)
            if other_zone is None or not _positive_overlap(body, other_zone):
                continue
            if zone.kind == "access" and _is_companion(item.id, other.id, companion_pairs):
                continue
            if hard:
                issues.append(
                    PlacementIssue(
                        code="blocks_clearance",
                        message_zh=f"擋住了「{other.catalog.name}」的開合空間"
                        if zone.kind == "operation"
                        else f"擋住了「{other.catalog.name}」的必要使用空間",
                        item_id=item.id,
                        related_item_id=other.id,
                        rule="reverse_clearance",
                    )
                )
                return issues
            issues.append(
                PlacementIssue(
                    code="blocks_access",
                    message_zh=f"占用了「{other.catalog.name}」的舒適使用空間",
                    item_id=item.id,
                    related_item_id=other.id,
                    rule="reverse_access",
                    severity="warning",
                )
            )
    return issues


def validate_placement_with_clearance(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    *,
    companion_pairs: CompanionPairs | None = None,
) -> PlacementValidation:
    """回傳結構化錯誤與警告；錯誤順序維持既有引擎契約。"""
    result = PlacementValidation()
    geometry_error = _geometry_error(item, room, others)
    if geometry_error is not None:
        result.errors.append(geometry_error)
        return result

    spec = resolved_clearance_spec(item.catalog)
    if spec is not None:
        if spec.mode == "any":
            if not _validate_any_mode(item, room, others, spec, companion_pairs, result):
                return result
        else:
            if not _validate_all_mode(item, room, others, spec, companion_pairs, result):
                return result

    reverse = _reverse_issues(item, room, others, companion_pairs)
    for issue in reverse:
        if issue.severity == "error":
            result.errors.append(issue)
            return result
        result.warnings.append(issue)
    return result


def check_placement_with_clearance(
    item: PlacedFurniture,
    room: Room,
    others: list[PlacedFurniture],
    *,
    companion_pairs: CompanionPairs | None = None,
) -> str | None:
    """相容入口：合法或只有警告時回 None，否則回第一條中文錯誤。"""
    result = validate_placement_with_clearance(
        item, room, others, companion_pairs=companion_pairs
    )
    return result.errors[0].message_zh if result.errors else None
