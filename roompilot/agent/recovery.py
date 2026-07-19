"""Agent 4 —— 擺放失敗修復(Placement Failure Recovery,鐵律版)。

引擎(generate_layout)放不下家具時會標 placement_failed / placement_reason,但整合前
沒有任何程式消費它 —— 就只是靜靜回報。本模組補上這個缺口:讀失敗清單 →(可選)問 LLM 決定
「換更小同型號 / 移除 / 升級回報」→ 套用 → 交由注入的 place_fn(引擎)重擺,直到收斂或到上限。

鐵律:座標永遠由引擎(place_fn)算。本模組只換/移品項,絕不自行給座標、絕不原地微移。
確定性核心(換小→否則移除)保證即使沒有 LLM 也能修;LLM 只做策略判斷與繁中說明。
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from .prompts import AGENT4_SYSTEM
from .schemas import ACTIONS, AGENT4_OUTPUT_SHAPE

Complete = Callable[[list[dict[str, str]]], Optional[dict[str, Any]]]
PlaceFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def _footprint(size: Any) -> float:
    size = size or {}
    try:
        return float(size.get("width") or 0) * float(size.get("depth") or 0)
    except (TypeError, ValueError):
        return 0.0


def _name(item_or_obj: dict[str, Any]) -> str:
    return item_or_obj.get("name_zh_raw") or str(item_or_obj.get("furniture_id") or "家具")


def pick_smaller_model(
    pool: list[dict[str, Any]],
    normalized_type: str | None,
    footprint_cap: float,
    exclude_ids: set,
) -> Optional[dict[str, Any]]:
    """從型錄池挑「同型、有 3D 模型、footprint 比 cap 小」的最小一款(確定性)。

    挑最小是為了最大化放得下的機率、讓修復迴圈更快收斂;以 footprint 排序,
    furniture_id 作 tie-break 確保結果穩定可測。找不到回 None。
    """
    candidates = [
        p
        for p in pool
        if p.get("has_model")
        and p.get("normalized_type") == normalized_type
        and p.get("furniture_id") not in exclude_ids
        and 0 < _footprint(p.get("size_cm")) < footprint_cap
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (_footprint(p.get("size_cm")), str(p.get("furniture_id"))))


def _default_instruction(
    obj: dict[str, Any],
    item: Optional[dict[str, Any]],
    pool: list[dict[str, Any]],
    used_ids: set,
) -> dict[str, Any]:
    """無 LLM 時的確定性策略:能換更小就 replace,否則 remove。"""
    cap = _footprint(item.get("size_cm")) if item else 0.0
    smaller = pick_smaller_model(pool, obj.get("normalized_type"), cap, used_ids) if cap else None
    if smaller is not None:
        return {
            "action": "replace",
            "reason_zh": f"空間放不下,已換成較小的「{_name(smaller)}」。",
        }
    return {
        "action": "remove",
        "reason_zh": f"空間有限,暫時移除「{_name(obj)}」以維持動線。",
    }


def _llm_instructions(
    failed: list[dict[str, Any]],
    working: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    plan: dict[str, Any],
    complete: Complete,
) -> dict[str, dict[str, Any]]:
    """有 LLM 時,讓 Agent 4 對每件失敗家具決定 action + 繁中理由。回 {fid: instruction}。"""
    by_id = {it.get("furniture_id"): it for it in working}
    used_ids = set(by_id)

    has_smaller: dict[Any, bool] = {}
    for obj in failed:
        item = by_id.get(obj.get("furniture_id"))
        cap = _footprint(item.get("size_cm")) if item else 0.0
        has_smaller[obj.get("furniture_id")] = bool(
            cap and pick_smaller_model(pool, obj.get("normalized_type"), cap, used_ids)
        )

    user_payload = {
        "space_type": plan.get("space_type"),
        "failed": [
            {
                "furniture_id": o.get("furniture_id"),
                "type": o.get("normalized_type"),
                "name": o.get("name_zh_raw"),
                "reason": o.get("placement_reason"),
            }
            for o in failed
        ],
        "has_smaller_same_type": has_smaller,
        "output_shape": AGENT4_OUTPUT_SHAPE,
    }
    messages = [
        {"role": "system", "content": AGENT4_SYSTEM},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    try:
        result = complete(messages)
    except Exception:
        return {}
    if not isinstance(result, dict):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for raw in result.get("instructions") or []:
        if isinstance(raw, dict) and raw.get("action") in ACTIONS:
            out[raw.get("furniture_id")] = {
                "action": raw["action"],
                "reason_zh": raw.get("reason_zh") if isinstance(raw.get("reason_zh"), str) else None,
            }
    return out


def run_recovery(
    objects: list[dict[str, Any]],
    selected_items: list[dict[str, Any]],
    plan: dict[str, Any],
    furniture_pool: list[dict[str, Any]],
    place_fn: PlaceFn,
    complete: Optional[Complete] = None,
    max_iter: int = 3,
    protected_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Agent 4 主入口。讀引擎的 placement_failed → 換小/移除/升級 → 重擺至收斂或到上限。

    回傳 (objects, final_items, report):
    - objects:修復後的擺放結果(座標仍由 place_fn / 引擎算)。
    - final_items:修復後的家具清單(換過/移過),供 payload 的 selected_furniture 對齊。
    - report:每筆修復動作 {furniture_id, type, action, from, to, message_zh}。
    """
    working = [dict(it) for it in selected_items]
    protected_ids = protected_ids or set()
    report: list[dict[str, Any]] = []
    fail_counts: dict[Any, int] = {}

    for _ in range(max_iter):
        failed = [o for o in objects if o.get("placement_failed")]
        if not failed:
            break

        llm = _llm_instructions(failed, working, furniture_pool, plan, complete) if complete else {}
        changed = False

        for obj in failed:
            fid = obj.get("furniture_id")
            item = next((it for it in working if it.get("furniture_id") == fid), None)
            if item is None:
                continue
            if fid in protected_ids:
                report.append({
                    "furniture_id": fid,
                    "type": obj.get("normalized_type"),
                    "action": "escalate",
                    "from": _name(item),
                    "to": None,
                    "message_zh": f"使用者指定的「{_name(item)}」目前放不下，需由使用者調整位置或需求。",
                })
                continue
            fail_counts[fid] = fail_counts.get(fid, 0) + 1
            used_ids = {it.get("furniture_id") for it in working}

            instr = llm.get(fid) or _default_instruction(obj, item, furniture_pool, used_ids)
            action = instr.get("action")

            # 卡住偵測:同一件連兩輪失敗 → 不再換,直接移除(對齊 pipeline.md 防震盪)
            if fail_counts[fid] >= 2 and action == "replace":
                action = "remove"
                instr = {"action": "remove", "reason_zh": f"多次嘗試仍放不下,移除「{_name(obj)}」。"}

            if action == "replace":
                cap = _footprint(item.get("size_cm"))
                smaller = pick_smaller_model(furniture_pool, obj.get("normalized_type"), cap, used_ids)
                if smaller is None:
                    action = "remove"  # 沒有更小款 → 退回移除
                else:
                    working[working.index(item)] = dict(smaller)
                    report.append({
                        "furniture_id": fid,
                        "type": obj.get("normalized_type"),
                        "action": "replace",
                        "from": _name(item),
                        "to": _name(smaller),
                        "message_zh": instr.get("reason_zh") or f"換成較小的「{_name(smaller)}」。",
                    })
                    changed = True

            if action == "remove":
                working = [it for it in working if it.get("furniture_id") != fid]
                report.append({
                    "furniture_id": fid,
                    "type": obj.get("normalized_type"),
                    "action": "remove",
                    "from": _name(item),
                    "to": None,
                    "message_zh": instr.get("reason_zh") or f"移除「{_name(item)}」以維持動線。",
                })
                changed = True
            elif action == "escalate":
                report.append({
                    "furniture_id": fid,
                    "type": obj.get("normalized_type"),
                    "action": "escalate",
                    "from": _name(item),
                    "to": None,
                    "message_zh": instr.get("reason_zh") or f"「{_name(item)}」放不下,建議調整需求或換更大房型。",
                })
                # escalate 不改 working;若全是 escalate,changed 為 False → 下面 break 收尾

        if not changed:
            break  # 沒有任何換/移(全升級或無可動) → 停止,避免空轉
        objects = place_fn(working)

    return objects, working, report
