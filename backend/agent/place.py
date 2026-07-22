"""選件 → 擺位紀律:主件先行、副件成組、寧缺勿亂(自 room_pilot2 移植)。

room_pilot2 的 place.py 直接驅動自家柵格引擎;本專案的座標權威是
backend.engine(Shapely、公分),所以移植的是「紀律」而非幾何:
- placement_hints:主件(床/沙發/餐桌/書桌)最先、泛用件居中、副件最後的
  確定性優先序 + 成組標籤,餵給 generate_layout 的 hints —— 只影響試放
  順序,合法性仍由引擎的碰撞/淨空把關。
- resolve_placements:消費引擎的 placement_failed。副件(COMPANION_OF)
  放不下、或主件不在(未選/被移除/放不下)→ 直接移除,絕不換小獨活
  (寧缺勿亂,床頭櫃絕不流落遠牆);主件與泛用件先試換更小同型號,沒有
  更小款才移除;使用者指定的家具只升級回報,不擅動。

全程不呼叫 LLM、不產生座標;重擺一律經注入的 place_fn(= 引擎)。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .knowledge import (
    ANCHOR_FAMILIES,
    COMPANION_OF,
    FAMILY_ZH,
    GROUP_OF,
    family_of,
)

logger = logging.getLogger(__name__)

PlaceFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _footprint(item: dict[str, Any]) -> float:
    size = item.get("size_cm") or {}
    try:
        return float(size.get("width") or 0) * float(size.get("depth") or 0)
    except (TypeError, ValueError):
        return 0.0


def _clean_size_cm(item: dict[str, Any]) -> dict[str, float]:
    """型錄尺寸防禦性清洗(池裡的原始值可能是字串或缺欄)。"""
    size = item.get("size_cm") or {}
    out: dict[str, float] = {}
    for key, fallback in (("width", 120.0), ("depth", 60.0), ("height", 80.0)):
        try:
            value = float(size.get(key))
        except (TypeError, ValueError):
            value = 0.0
        out[key] = value if value > 0 else fallback
    return out


def _name(obj: dict[str, Any]) -> str:
    return obj.get("name_zh_raw") or str(obj.get("furniture_id") or "家具")


def _key(obj: dict[str, Any]) -> str:
    """品項對位鍵:count 展開後同 furniture_id 會有多實例,優先用 instance_id。"""
    return str(obj.get("instance_id") or obj.get("furniture_id") or "")


def _anchors_zh(family: str) -> str:
    return "或".join(FAMILY_ZH.get(a, a) for a in COMPANION_OF.get(family, ()))


def placement_hints(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """確定性擺放提示:回 {instance_id|furniture_id: {"priority", "group"}}。

    優先序:主件(ANCHOR_FAMILIES,面積大到小)→ 泛用件(面積大到小)→
    副件(COMPANION_OF,最後擺 —— 引擎的成組候選要有已就位的主件可貼)。
    只給順序與成組語意,不給座標;無 LLM 參與,結果可重現。
    """
    def _class(item: dict[str, Any]) -> int:
        family = family_of(item.get("normalized_type"))
        if family in COMPANION_OF:
            return 2
        if family in ANCHOR_FAMILIES:
            return 0
        return 1

    order = sorted(items, key=lambda it: (_class(it), -_footprint(it), _key(it)))
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
    exclude_ids: set,
) -> dict[str, Any] | None:
    """從型錄池挑「同型、有 3D 模型、footprint 比 cap 小」的最小一款(確定性)。

    先找同 normalized_type;沒有再放寬到同族系(fabric-sofa ↔ leather-sofa)。
    挑最小是為了最大化放得下的機率、讓修復迴圈更快收斂;footprint 排序、
    furniture_id 作 tie-break 確保結果穩定可測。找不到回 None。
    """
    def _candidates(match) -> list[dict[str, Any]]:
        return [
            p
            for p in pool
            if p.get("has_model")
            and match(p)
            and p.get("furniture_id") not in exclude_ids
            and 0 < _footprint(p) < footprint_cap
        ]

    found = _candidates(lambda p: p.get("normalized_type") == normalized_type)
    if not found:
        family = family_of(normalized_type)
        found = _candidates(lambda p: family_of(p.get("normalized_type")) == family)
    if not found:
        return None
    return min(found, key=lambda p: (_footprint(p), str(p.get("furniture_id"))))


def _replacement_item(item: dict[str, Any], smaller: dict[str, Any]) -> dict[str, Any]:
    """換小款:型錄欄位取新款,場景欄位(instance_id/space 綁定/選件來源)保留。"""
    return {
        **item,
        "furniture_id": smaller.get("furniture_id"),
        "name_zh_raw": smaller.get("name_zh_raw") or smaller.get("name_zh")
        or smaller.get("furniture_id"),
        "normalized_type": smaller.get("normalized_type"),
        "model_url": smaller.get("model_url"),
        "primary_style": smaller.get("primary_style"),
        "size_cm": _clean_size_cm(smaller),
    }


def resolve_placements(
    objects: list[dict[str, Any]],
    items: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    place_fn: PlaceFn,
    protected_ids: set[str] | None = None,
    max_rounds: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """讀引擎的 placement_failed → 寧缺勿亂 / 換小 / 移除 → 重擺至收斂或到上限。

    回傳 (objects, final_items, report):
    - objects:修復後的擺放結果(座標仍 100% 由 place_fn / 引擎算)。
    - final_items:修復後的家具清單(換過/移過),供 payload 對齊。
    - report:每筆動作 {furniture_id, type, action(replace|remove|escalate),
      from, to, message_zh},繁中訊息直接給使用者看。
    """
    working = [dict(item) for item in items]
    protected_ids = protected_ids or set()
    report: list[dict[str, Any]] = []
    fail_counts: dict[str, int] = {}
    escalated: set[str] = set()

    def _find_item(obj: dict[str, Any]) -> dict[str, Any] | None:
        key = _key(obj)
        for candidate in working:
            if _key(candidate) == key:
                return candidate
        fid = str(obj.get("furniture_id") or "")
        return next(
            (c for c in working if str(c.get("furniture_id")) == fid), None
        )

    def _remove(item: dict[str, Any], obj: dict[str, Any], message: str) -> None:
        nonlocal working
        key = _key(item)
        working = [c for c in working if _key(c) != key]
        report.append({
            "furniture_id": obj.get("furniture_id"),
            "type": obj.get("normalized_type"),
            "action": "remove",
            "from": _name(item),
            "to": None,
            "message_zh": message,
        })

    for _ in range(max_rounds):
        failed = [obj for obj in objects if obj.get("placement_failed")]
        changed = False

        for obj in failed:
            item = _find_item(obj)
            if item is None:
                continue
            fid = str(obj.get("furniture_id") or "")
            if fid in protected_ids:
                if fid not in escalated:
                    escalated.add(fid)
                    report.append({
                        "furniture_id": obj.get("furniture_id"),
                        "type": obj.get("normalized_type"),
                        "action": "escalate",
                        "from": _name(item),
                        "to": None,
                        "message_zh": f"使用者指定的「{_name(item)}」目前放不下，需由使用者調整位置或需求。",
                    })
                continue
            family = family_of(obj.get("normalized_type"))
            if family in COMPANION_OF:
                # 寧缺勿亂:副件只准與主件成組,放不下就退場,絕不換小獨活
                _remove(item, obj, f"「{_name(item)}」需與{_anchors_zh(family)}成組擺放，目前放不下，先移除。")
                changed = True
                continue
            key = _key(obj)
            fail_counts[key] = fail_counts.get(key, 0) + 1
            if fail_counts[key] >= 2:
                # 卡住偵測:同一件連兩輪失敗 → 不再換,直接移除(防震盪)
                _remove(item, obj, f"多次嘗試仍放不下，移除「{_name(item)}」。")
                changed = True
                continue
            used_ids = {str(c.get("furniture_id")) for c in working}
            smaller = pick_smaller_model(
                pool, obj.get("normalized_type"), _footprint(item), used_ids
            )
            if smaller is None:
                _remove(item, obj, f"空間有限，暫時移除「{_name(item)}」以維持動線。")
                changed = True
                continue
            working[working.index(item)] = _replacement_item(item, smaller)
            report.append({
                "furniture_id": fid,
                "type": obj.get("normalized_type"),
                "action": "replace",
                "from": _name(item),
                "to": _name(smaller),
                "message_zh": f"空間放不下，已換成較小的「{_name(smaller)}」。",
            })
            changed = True

        # 寧缺勿亂第二式:主件已不在清單(未選/被移除)的副件一併退場,
        # 床頭櫃絕不留在沒有床的房裡。只清 agent 選的件(selection_source
        # 為 openrouter/local_rules);使用者指定或未標記來源的一律不動。
        working_families = {
            family_of(candidate.get("normalized_type")) for candidate in working
        }
        for obj in objects:
            if obj.get("placement_failed"):
                continue  # 失敗件已在上面處理
            family = family_of(obj.get("normalized_type"))
            anchors = COMPANION_OF.get(family)
            if not anchors or working_families.intersection(anchors):
                continue
            fid = str(obj.get("furniture_id") or "")
            if fid in protected_ids:
                continue  # 使用者堅持要的,保留並交由使用者裁決
            item = _find_item(obj)
            if item is None:
                continue
            if item.get("user_required") or item.get("selection_source") not in (
                "openrouter",
                "local_rules",
            ):
                continue
            _remove(item, obj, f"「{_name(item)}」的主件{_anchors_zh(family)}不在配置中，依成組原則一併移除。")
            working_families = {
                family_of(candidate.get("normalized_type")) for candidate in working
            }
            changed = True

        if not changed:
            break  # 無任何換/移(全升級或無可動)→ 停止,避免空轉
        objects = place_fn(working)

    return objects, working, report
