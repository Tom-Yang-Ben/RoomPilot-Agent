"""Agent 3 —— 版面語意提示(Layout Intent Designer,鐵律版)。

原版 for_agent 的 Agent 3 會輸出每件家具的 position/rotation;這裡改寫成【不出座標】:
只讀房間尺寸、門窗牆側、風格與已選家具,輸出「擺放語意提示」(靠牆側/朝向/成組/優先序),
交給引擎的 _placement_candidates 當試放順序。座標與合法性仍 100% 由引擎決定。

無 LLM(或呼叫失敗)時回傳 {} —— 引擎沿用預設候選順序,行為與整合前完全一致。
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from .prompts import AGENT3_SYSTEM
from .schemas import AGENT3_OUTPUT_SHAPE, ANCHORS, FACES

# complete: 注入的 LLM 呼叫器(= scene_service._openrouter_request),吃 messages 回 dict|None
Complete = Callable[[list[dict[str, str]]], Optional[dict[str, Any]]]


def _opening_sides(segments: Any, half_w_cm: float, half_d_cm: float) -> list[str]:
    """把門/窗線段(公尺、房間中心原點)歸類到最近的牆側(top/bottom/left/right)。

    座標軸與 _placement_candidates 一致:top = -depth/2、bottom = +depth/2、
    left = -width/2、right = +width/2。無法解析的線段略過。
    """
    sides: list[str] = []
    for seg in segments or []:
        try:
            start, end = seg["start"], seg["end"]
            mx = (float(start["x"]) + float(end["x"])) / 2 * 100
            mz = (float(start["z"]) + float(end["z"])) / 2 * 100
        except (KeyError, TypeError, ValueError):
            continue
        dist = {
            "top": abs(mz - (-half_d_cm)),
            "bottom": abs(mz - half_d_cm),
            "left": abs(mx - (-half_w_cm)),
            "right": abs(mx - half_w_cm),
        }
        side = min(dist, key=dist.get)
        if side not in sides:
            sides.append(side)
    return sides


def _parse_hints(result: Any, valid_ids: set) -> dict[str, dict[str, Any]]:
    """把 LLM 回應解析成 {furniture_id: hint};非法欄位一律丟棄(絕不硬吃)。"""
    if not isinstance(result, dict):
        return {}

    hints: dict[str, dict[str, Any]] = {}
    for raw in result.get("hints") or []:
        if not isinstance(raw, dict):
            continue
        fid = raw.get("furniture_id")
        if fid not in valid_ids:
            continue

        anchor = raw.get("anchor")
        anchor = anchor if anchor in ANCHORS else None
        face = raw.get("face")
        face = face if face in FACES else None
        group = raw.get("group") if isinstance(raw.get("group"), str) else None
        note = raw.get("note") if isinstance(raw.get("note"), str) else None
        try:
            priority: Optional[int] = int(raw.get("priority"))
        except (TypeError, ValueError):
            priority = None

        # 至少要有一項對引擎/前端有用的資訊才收
        if anchor or priority is not None or group:
            hints[fid] = {
                "anchor": anchor,
                "face": face,
                "group": group,
                "priority": priority,
                "note": note,
            }
    return hints


def design_layout_intent(
    plan: dict[str, Any],
    selected_items: list[dict[str, Any]],
    room_dims: dict[str, Any],
    openings: dict[str, Any] | None,
    complete: Optional[Complete],
) -> dict[str, dict[str, Any]]:
    """Agent 3 主入口。回傳以 furniture_id 為鍵的擺放提示,不含座標。

    參數
    - plan:build_scene_plan 的結果(style_id / space_type / personal_requirements…)。
    - selected_items:choose_furniture_items 選出的家具(含 furniture_id / normalized_type / size_cm)。
    - room_dims:{"width_cm", "depth_cm"}。
    - openings:{"windows": [...線段...], "doors": [...線段...]}(可為 None / 空)。
    - complete:注入的 LLM 呼叫器;None 或呼叫失敗 → 回 {}。
    """
    if complete is None or not selected_items:
        return {}

    half_w = float(room_dims.get("width_cm") or 0) / 2
    half_d = float(room_dims.get("depth_cm") or 0) / 2
    openings = openings or {}

    user_payload = {
        "room": {
            "width_cm": room_dims.get("width_cm"),
            "depth_cm": room_dims.get("depth_cm"),
            "window_sides": _opening_sides(openings.get("windows"), half_w, half_d),
            "door_sides": _opening_sides(openings.get("doors"), half_w, half_d),
        },
        "style": plan.get("style_id"),
        "space_type": plan.get("space_type"),
        "personal_requirements": plan.get("personal_requirements") or "",
        "furniture": [
            {
                "furniture_id": it.get("furniture_id"),
                "type": it.get("normalized_type"),
                "name": it.get("name_zh_raw"),
                "size_cm": it.get("size_cm"),
            }
            for it in selected_items
        ],
        "output_shape": AGENT3_OUTPUT_SHAPE,
    }
    messages = [
        {"role": "system", "content": AGENT3_SYSTEM},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    try:
        result = complete(messages)
    except Exception:
        return {}

    return _parse_hints(result, {it.get("furniture_id") for it in selected_items})
