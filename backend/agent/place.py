"""選件結果的擺位紀律：主件先行、副件成組、放不下寧缺勿亂。

``placement_hints`` 只產生順序與成組語意；``resolve_placements`` 讀取
引擎回傳的 ``placement_failed``，再決定換小、移除或升級人工處理。
每次重擺都必須經由呼叫端注入的 ``engine_place_fn``，正式流程必須
使用 :mod:`backend.engine` adapter。本模組本身絕不計算或修改座標。
"""

from __future__ import annotations

from typing import Any, Callable

from .knowledge import ANCHOR_FAMILIES, COMPANION_OF, FAMILY_ZH, GROUP_OF, family_of


EnginePlaceFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _footprint_cm2(item: dict[str, Any]) -> float:
    """只比較型錄邊界的公分尺寸，不做幾何或座標運算。"""
    size = item.get("size_cm") or {}
    try:
        return float(size.get("width") or 0) * float(size.get("depth") or 0)
    except (TypeError, ValueError):
        return 0.0


def _clean_size_cm(item: dict[str, Any]) -> dict[str, float]:
    """防禦性清洗型錄尺寸，避免字串、缺欄或非正值進入替換品項。"""
    size = item.get("size_cm") or {}
    cleaned: dict[str, float] = {}
    for key, fallback in (("width", 120.0), ("depth", 60.0), ("height", 80.0)):
        try:
            value = float(size.get(key))
        except (TypeError, ValueError):
            value = 0.0
        cleaned[key] = value if value > 0 else fallback
    return cleaned


def _name(item: dict[str, Any]) -> str:
    return str(item.get("name_zh_raw") or item.get("name_zh") or item.get("furniture_id") or "家具")


def _key(item: dict[str, Any]) -> str:
    """取得場景品項對位鍵；多實例家具優先使用 instance_id。"""
    return str(item.get("instance_id") or item.get("furniture_id") or "")


def _anchor_names(family: str) -> str:
    return "或".join(FAMILY_ZH.get(anchor, anchor) for anchor in COMPANION_OF.get(family, ()))


def placement_hints(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """產生主件 → 泛用件 → 副件的確定性順序，不含座標或旋轉。"""

    def item_class(item: dict[str, Any]) -> int:
        family = family_of(item.get("normalized_type"))
        if family in COMPANION_OF:
            return 2
        if family in ANCHOR_FAMILIES:
            return 0
        return 1

    order = sorted(items, key=lambda item: (item_class(item), -_footprint_cm2(item), _key(item)))
    hints: dict[str, dict[str, Any]] = {}
    for priority, item in enumerate(order):
        hint: dict[str, Any] = {"priority": priority}
        group = GROUP_OF.get(family_of(item.get("normalized_type")))
        if group:
            hint["group"] = group
        hints[_key(item)] = hint
    return hints


def pick_smaller_model(
    pool: list[dict[str, Any]],
    normalized_type: str | None,
    footprint_cap: float,
    exclude_ids: set[str],
) -> dict[str, Any] | None:
    """挑選同型、有 3D 模型且 footprint 更小的確定性替代品。

    找不到相同 ``normalized_type`` 時，才放寬到相同擺位族系。
    """

    def candidates(predicate: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
        return [
            item
            for item in pool
            if item.get("has_model")
            and predicate(item)
            and str(item.get("furniture_id") or "") not in exclude_ids
            and 0 < _footprint_cm2(item) < footprint_cap
        ]

    found = candidates(lambda item: item.get("normalized_type") == normalized_type)
    if not found:
        family = family_of(normalized_type)
        found = candidates(lambda item: family_of(item.get("normalized_type")) == family)
    if not found:
        return None
    return min(found, key=lambda item: (_footprint_cm2(item), str(item.get("furniture_id"))))


def _replacement_item(item: dict[str, Any], smaller: dict[str, Any]) -> dict[str, Any]:
    """以新型錄品項換小，並只保留白名單中的場景綁定資料。"""
    # 以新型錄品項為主，只白名單保留場景綁定資料，避免產生
    # 「新 ID／新模型＋舊顏色／舊價格」的混合品項。
    replacement = dict(smaller)
    for key in (
        "instance_id",
        "space_id",
        "room_id",
        "selection_source",
        "user_required",
        "quantity_index",
        "auto_decor_role",
        "decor_anchor_role",
    ):
        if key in item:
            replacement[key] = item[key]
    replacement["size_cm"] = _clean_size_cm(smaller)
    replacement["name_zh_raw"] = (
        smaller.get("name_zh_raw") or smaller.get("name_zh") or smaller.get("furniture_id")
    )
    return replacement


def resolve_placements(
    objects: list[dict[str, Any]],
    items: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    *,
    engine_place_fn: EnginePlaceFn,
    protected_ids: set[str] | None = None,
    max_rounds: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """依引擎 ``placement_failed`` 結果換小、移除或升級人工處理。

    返回 ``(engine_objects, final_items, report)``。本函式不讀寫座標；
    ``engine_objects`` 內的座標只可由 ``engine_place_fn`` 產生。使用者
    指定家具放不下時只升級人工處理，不得自動替換或刪除。
    """
    working = [dict(item) for item in items]
    protected_ids = protected_ids or set()
    report: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}
    escalated: set[str] = set()

    def find_item(obj: dict[str, Any]) -> dict[str, Any] | None:
        key = _key(obj)
        for candidate in working:
            if _key(candidate) == key:
                return candidate
        furniture_id = str(obj.get("furniture_id") or "")
        return next(
            (candidate for candidate in working if str(candidate.get("furniture_id") or "") == furniture_id),
            None,
        )

    def remove(item: dict[str, Any], obj: dict[str, Any], message: str) -> None:
        nonlocal working
        key = _key(item)
        working = [candidate for candidate in working if _key(candidate) != key]
        report.append(
            {
                "furniture_id": obj.get("furniture_id"),
                "type": obj.get("normalized_type"),
                "action": "remove",
                "from": _name(item),
                "to": None,
                "message_zh": message,
            }
        )

    for _round in range(max_rounds):
        changed = False
        for obj in [candidate for candidate in objects if candidate.get("placement_failed")]:
            item = find_item(obj)
            if item is None:
                continue
            furniture_id = str(obj.get("furniture_id") or "")
            if furniture_id in protected_ids:
                if furniture_id not in escalated:
                    escalated.add(furniture_id)
                    report.append(
                        {
                            "furniture_id": furniture_id,
                            "type": obj.get("normalized_type"),
                            "action": "escalate",
                            "from": _name(item),
                            "to": None,
                            "message_zh": f"使用者指定的「{_name(item)}」目前放不下，需人工調整位置或需求。",
                        }
                    )
                continue

            family = family_of(obj.get("normalized_type"))
            if family in COMPANION_OF:
                # 副件只准與主件成組；副件本身放不下就直接退場，不換小獨活。
                remove(
                    item,
                    obj,
                    f"「{_name(item)}」需與{_anchor_names(family)}成組擺放，目前放不下，先移除。",
                )
                changed = True
                continue

            key = _key(obj)
            failure_counts[key] = failure_counts.get(key, 0) + 1
            if failure_counts[key] >= 2:
                # 同一品項連續兩輪失敗後停止替換，避免在候選間反覆震盪。
                remove(item, obj, f"多次嘗試仍放不下，移除「{_name(item)}」。")
                changed = True
                continue

            used_ids = {str(candidate.get("furniture_id") or "") for candidate in working}
            smaller = pick_smaller_model(
                pool,
                obj.get("normalized_type"),
                _footprint_cm2(item),
                used_ids,
            )
            if smaller is None:
                remove(item, obj, f"空間有限，暫時移除「{_name(item)}」以維持動線。")
                changed = True
                continue

            working[working.index(item)] = _replacement_item(item, smaller)
            report.append(
                {
                    "furniture_id": furniture_id,
                    "type": obj.get("normalized_type"),
                    "action": "replace",
                    "from": _name(item),
                    "to": _name(smaller),
                    "message_zh": f"空間放不下，已換成較小的「{_name(smaller)}」。",
                }
            )
            changed = True

        # 主件已不在工作清單時，Agent 自選的副件也一併退場；使用者指定
        # 或來源未標記的家具不在此自動清理範圍。
        working_families = {
            family_of(candidate.get("normalized_type")) for candidate in working
        }
        for obj in objects:
            if obj.get("placement_failed"):
                continue
            family = family_of(obj.get("normalized_type"))
            anchors = COMPANION_OF.get(family)
            if not anchors or working_families.intersection(anchors):
                continue
            furniture_id = str(obj.get("furniture_id") or "")
            if furniture_id in protected_ids:
                continue
            item = find_item(obj)
            if item is None:
                continue
            if item.get("user_required") or item.get("selection_source") not in (
                "openrouter",
                "local_rules",
            ):
                continue
            remove(
                item,
                obj,
                f"「{_name(item)}」的主件{_anchor_names(family)}不在配置中，依成組原則一併移除。",
            )
            working_families = {
                family_of(candidate.get("normalized_type")) for candidate in working
            }
            changed = True

        if not changed:
            break
        objects = engine_place_fn(working)

    return objects, working, report
