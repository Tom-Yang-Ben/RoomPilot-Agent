"""專案級 2D 家具配置：agent LLM 選件 + 潛規則擺位紀律 + 幾何引擎座標。

選件走 ``backend.agent``（room_pilot2 移植版）：OpenRouter 只可從伺服器
提供的各空間候選白名單挑 furniture_id 與件數，輸出經系統邊界驗證與潛規則
過濾（房型適配、成組依賴）；擺位提示與失敗修復（寧缺勿亂、換小、移除）
全程確定性。所有座標、碰撞、淨空與房間邊界仍由 ``backend.engine`` 決定。
無 API、未同意或回應不合法時，確定性降級為本地房型規則，且結果一律等待
使用者確認。
"""

from __future__ import annotations

import os
import re
from typing import Any

from ...agent import (
    SelectionParseError,
    SelectionUnavailableError,
    placement_hints,
    request_selections,
    resolve_placements,
)
from ...catalog.style_db import sanitize_size_cm
from .scene_service import (
    _load_json_response,
    _post_openrouter_chat,
    _region_boundary_by_id,
    generate_layout,
    get_openrouter_models,
    load_local_env,
    room_from_payload,
)

# 每房展開後的家具實例上限(AI 選件與本機規則兩條路共用)。
MAX_ROOM_ITEMS = 20


# 每個 tuple 是一個機能槽，依序列出可接受的型錄 normalized_type。
DEFAULT_TYPE_GROUPS: dict[str, list[tuple[str, ...]]] = {
    "living_room": [
        ("fabric-sofa", "leather-sofa", "modular-sofa", "sofa-bed"),
        ("coffee-table",),
        ("tv-bench", "tv-media-furniture"),
    ],
    "dining_room": [("dining-table", "table"), ("dining-chair",)],
    "bedroom": [
        ("bed-frame", "bed"),
        ("bedside-table",),
        ("pax-wardrobe", "wardrobe"),
    ],
    "study": [("desk",), ("office-chair",), ("bookcase", "shelving-unit")],
    "kitchen": [("cabinets-cupboard", "storage-solution-system", "trolley")],
    "entry": [("clothes-rack", "storage-furniture"), ("door-mat",)],
    "balcony": [("outdoor-seating",), ("outdoor-coffee-side-table",)],
    "storage": [("shelving-unit", "storage-furniture", "storage-solution-system")],
    "laundry": [("storage-furniture", "shelving-unit", "trolley")],
}

_SANITIZE_FAMILY = {
    "fabric-sofa": "sofa",
    "leather-sofa": "sofa",
    "modular-sofa": "sofa",
    "sofa-bed": "sofa",
    "pax-wardrobe": "wardrobe",
    "cabinets-cupboard": "wardrobe",
    "storage-solution-system": "wardrobe",
    "chests-of-drawer": "sideboard",
}


def layout_catalog_size_cm(item: dict[str, Any]) -> dict[str, float]:
    """配置用尺寸清洗；具體型錄類型先映射到引擎的尺寸族系。"""
    item_type = str(item.get("normalized_type") or "")
    return sanitize_size_cm({
        **item,
        "normalized_type": _SANITIZE_FAMILY.get(item_type, item_type),
    })


def _style_score(item: dict[str, Any], style_id: str) -> float:
    if item.get("primary_style") == style_id:
        return 2.0
    for candidate in item.get("style_candidates") or []:
        if isinstance(candidate, dict) and candidate.get("style_id") == style_id:
            try:
                return float(candidate.get("score") or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _footprint(item: dict[str, Any]) -> float:
    size = layout_catalog_size_cm(item)
    return float(size.get("width") or 120) * float(size.get("depth") or 60)


def _ranked_group_candidates(
    catalog: list[dict[str, Any]],
    group: tuple[str, ...],
    style_id: str,
) -> list[dict[str, Any]]:
    type_rank = {item_type: index for index, item_type in enumerate(group)}
    candidates = [
        item
        for item in catalog
        if item.get("has_model")
        and item.get("model_url")
        and item.get("furniture_id")
        and item.get("normalized_type") in type_rank
    ]
    return sorted(
        candidates,
        key=lambda item: (
            type_rank[str(item.get("normalized_type"))],
            -_style_score(item, style_id),
            _footprint(item),
            str(item.get("furniture_id")),
        ),
    )


def _catalog_scene_item(
    item: dict[str, Any],
    *,
    room_id: str,
    user_required: bool,
    selection_source: str,
    instance_index: int,
) -> dict[str, Any]:
    safe_room = re.sub(r"[^a-zA-Z0-9_-]", "-", room_id)[:48] or "room"
    furniture_id = str(item["furniture_id"])
    return {
        "instance_id": f"{safe_room}-{instance_index + 1}-{furniture_id[:36]}",
        "furniture_id": furniture_id,
        "name_zh_raw": item.get("name_zh_raw") or item.get("name_zh") or furniture_id,
        "normalized_type": item.get("normalized_type"),
        "model_url": item.get("model_url"),
        "primary_style": item.get("primary_style"),
        "size_cm": layout_catalog_size_cm(item),
        "placement_room_id": room_id,
        "user_required": user_required,
        "selection_source": selection_source,
        "mobility": "movable",
    }


def _candidate_payload(
    requirements: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[str]]]:
    style_id = str(requirements.get("style_id") or "scandinavian")
    catalog_by_id = {
        str(item.get("furniture_id")): item
        for item in catalog
        if item.get("furniture_id") and item.get("has_model") and item.get("model_url")
    }
    candidates: dict[str, list[dict[str, Any]]] = {}
    deterministic: dict[str, list[str]] = {}
    for room in requirements.get("room_requirements") or []:
        room_id = str(room.get("room_id") or "")
        exact_ids = [
            furniture_id
            for furniture_id in room.get("required_furniture_ids") or []
            if furniture_id in catalog_by_id
        ]
        room_candidates: list[dict[str, Any]] = []
        local_ids: list[str] = list(exact_ids)
        used_ids = set(exact_ids)
        exact_types = {
            str(catalog_by_id[furniture_id].get("normalized_type"))
            for furniture_id in exact_ids
        }
        for group in DEFAULT_TYPE_GROUPS.get(str(room.get("room_type") or "other"), []):
            ranked = _ranked_group_candidates(catalog, group, style_id)
            for item in ranked[:4]:
                if item["furniture_id"] not in used_ids:
                    room_candidates.append(item)
            selected = None if exact_types.intersection(group) else next(
                (item for item in ranked if item["furniture_id"] not in used_ids),
                None,
            )
            if selected:
                local_ids.append(str(selected["furniture_id"]))
                used_ids.add(str(selected["furniture_id"]))
        for furniture_id in exact_ids:
            item = catalog_by_id[furniture_id]
            if not any(candidate.get("furniture_id") == furniture_id for candidate in room_candidates):
                room_candidates.insert(0, item)
        candidates[room_id] = room_candidates[:20]
        deterministic[room_id] = list(dict.fromkeys(local_ids))
    return candidates, deterministic


def _openrouter_complete(messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]] | None:
    """OpenRouter json_object 通用呼叫器，注入給 ``agent.select`` 用。

    只負責傳輸與 JSON 解析；prompt 內容與輸出驗證都在 agent 端。回
    (model, dict) 或 None（未設定 / 全部模型都失敗）。
    """
    load_local_env()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key or os.getenv("OPENROUTER_LAYOUT_ENABLED", "1") == "0":
        return None
    models = get_openrouter_models()
    if not models:
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8002"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "RoomPilot 2D layout"),
    }
    for model in models:
        body = _post_openrouter_chat(
            {
                "model": model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": messages,
            },
            headers,
            timeout=12,
        )
        if body is None:
            continue
        parsed = _load_json_response(body)
        if parsed is not None:
            return model, parsed
    return None


def build_layout_proposal(
    requirements: dict[str, Any],
    floorplan: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    allow_openrouter: bool,
) -> dict[str, Any]:
    """產生單一、仍待使用者確認的 2D 配置提案。"""
    candidates, deterministic = _candidate_payload(requirements, catalog)
    room_requirements = {
        str(room.get("room_id")): room
        for room in requirements.get("room_requirements") or []
    }
    style_id = str(requirements.get("style_id") or "scandinavian")
    catalog_by_id = {
        str(item.get("furniture_id")): item
        for item in catalog
        if item.get("furniture_id") and item.get("has_model") and item.get("model_url")
    }
    room_engine = room_from_payload(floorplan)
    boundaries = {
        room_id: _region_boundary_by_id(floorplan, room_engine, room_id)
        for room_id in room_requirements
    }

    # agent 選件輸入：各空間候選白名單（尺寸清洗過）、空間摘要、使用者精選
    offers = {
        room_id: [
            {**item, "size_cm": layout_catalog_size_cm(item)}
            for item in room_candidates
        ]
        for room_id, room_candidates in candidates.items()
    }
    rooms_for_agent: list[dict[str, Any]] = []
    for room_id, requirement in room_requirements.items():
        boundary = boundaries.get(room_id)
        if boundary is not None:
            min_x, min_z, max_x, max_z = boundary.bounds
            width_cm, depth_cm = round(max_x - min_x, 1), round(max_z - min_z, 1)
        else:
            width_cm, depth_cm = round(room_engine.width, 1), round(room_engine.depth, 1)
        rooms_for_agent.append({
            "room_id": room_id,
            "room_type": requirement.get("room_type"),
            "uses": requirement.get("uses") or [],
            "width_cm": width_cm,
            "depth_cm": depth_cm,
            "required_furniture_ids": requirement.get("required_furniture_ids") or [],
        })
    preselected: dict[str, list[dict[str, Any]]] = {}
    for room_id, requirement in room_requirements.items():
        exact = [
            catalog_by_id[str(fid)]
            for fid in dict.fromkeys(requirement.get("required_furniture_ids") or [])
            if str(fid) in catalog_by_id
        ]
        if exact:
            preselected[room_id] = exact

    openrouter = {
        "provider": "openrouter",
        "requested": bool(allow_openrouter),
        "sent": False,
        "status": "not_requested",
        "model": None,
    }
    ai_selections: dict[str, list[Any]] = {}
    if allow_openrouter:
        load_local_env()
        enabled = bool(os.getenv("OPENROUTER_API_KEY", "").strip()) and os.getenv(
            "OPENROUTER_LAYOUT_ENABLED", "1"
        ) != "0"
        if enabled:
            openrouter["sent"] = True
            try:
                ai_selections, model = request_selections(
                    rooms_for_agent,
                    offers,
                    style_id,
                    complete=_openrouter_complete,
                    preselected=preselected,
                    context={
                        "occupants": requirements.get("occupants"),
                        "constraints": (requirements.get("special_requirements") or {}).get("constraints") or [],
                    },
                )
                if ai_selections:
                    openrouter.update({"status": "suggested", "model": model})
                else:
                    openrouter["status"] = "unavailable"
            except (SelectionParseError, SelectionUnavailableError):
                ai_selections = {}
                openrouter["status"] = "unavailable"
        else:
            openrouter["status"] = "unavailable"
    all_objects: list[dict[str, Any]] = []
    recovery_report: list[dict[str, Any]] = []
    warnings: list[str] = []
    for room_id, room_requirement in room_requirements.items():
        exact_ids = [
            str(fid)
            for fid in dict.fromkeys(room_requirement.get("required_furniture_ids") or [])
        ]
        selected_items: list[dict[str, Any]] = []
        ai_bucket = ai_selections.get(room_id) or []
        # parse_selections 會把使用者精選種進 LLM 提到的房間;若 LLM 自選的
        # ID 全被驗證濾掉、桶裡只剩種入的精選,視同該房未回答,退回本機規則
        # (否則提案只剩精選那一件的近空房)。
        ai_contributed = any(
            str(selected.item.get("furniture_id")) not in exact_ids
            for selected in ai_bucket
        )
        if ai_bucket and ai_contributed:
            # agent 已驗證的選件（使用者精選先入座）；count>1 展開成多實例
            instance_index = 0
            for selected in ai_bucket:
                if instance_index >= MAX_ROOM_ITEMS:
                    break
                furniture_id = str(selected.item.get("furniture_id"))
                for _ in range(min(selected.count, MAX_ROOM_ITEMS - instance_index)):
                    selected_items.append(_catalog_scene_item(
                        selected.item,
                        room_id=room_id,
                        user_required=furniture_id in exact_ids,
                        selection_source="user" if furniture_id in exact_ids else "openrouter",
                        instance_index=instance_index,
                    ))
                    instance_index += 1
        else:
            proposed_ids = deterministic.get(room_id, [])
            selected_ids = list(dict.fromkeys([*exact_ids, *proposed_ids]))[:MAX_ROOM_ITEMS]
            for index, furniture_id in enumerate(selected_ids):
                item = catalog_by_id.get(str(furniture_id))
                if item is None:
                    continue
                selected_items.append(_catalog_scene_item(
                    item,
                    room_id=room_id,
                    user_required=furniture_id in exact_ids,
                    selection_source="user" if furniture_id in exact_ids else "local_rules",
                    instance_index=index,
                ))
        if not selected_items:
            warnings.append(f"空間 {room_id} 沒有可用且具 GLB 的預設家具，保留空房。")
            continue
        boundary = boundaries.get(room_id)
        if boundary is None:
            warnings.append(f"空間 {room_id} 缺少可用邊界，暫時不自動擺放家具。")
            continue

        def place(items: list[dict[str, Any]], _boundary=boundary) -> list[dict[str, Any]]:
            # 擺位提示每次依潛規則重算（主件先、副件後），換小後順序仍正確
            return generate_layout(
                room_engine.width,
                room_engine.depth,
                items,
                room=room_engine,
                regions_boundary=_boundary,
                place_boundary=_boundary,
                hints=placement_hints(items),
                window_segments=floorplan.get("window_segments") or [],
                door_segments=floorplan.get("door_segments") or [],
                floorplan=floorplan,
            )

        objects = place(selected_items)
        objects, selected_items, room_recovery = resolve_placements(
            objects,
            selected_items,
            list(catalog_by_id.values()),
            place_fn=place,
            protected_ids=set(exact_ids),
        )
        all_objects.extend(objects)
        recovery_report.extend({**entry, "room_id": room_id} for entry in room_recovery)

    failed_count = sum(bool(item.get("placement_failed")) for item in all_objects)
    if failed_count:
        warnings.append(f"有 {failed_count} 件指定家具尚無合法位置，請調整後再確認。")
    return {
        "status": "suggested",
        "source": "openrouter" if ai_selections else "local_rules",
        "proposal_count": 1,
        "scene_objects": all_objects,
        "recovery": recovery_report,
        "warnings": warnings,
        "openrouter": openrouter,
        "summary_zh": f"已依 {len(room_requirements)} 個空間產生單一配置，共 {len(all_objects)} 件家具；請在 2D 畫面確認。",
    }


def _is_user_selected(item: dict[str, Any]) -> bool:
    """問卷指定與人工選型都是產品承諾，換色卡時不可偷換型號。"""
    return bool(
        item.get("user_required")
        or item.get("selection_source") == "user"
        or item.get("user_selected_model")
    )


def build_style_variant(
    scene_objects: list[dict[str, Any]],
    floorplan: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    style_id: str,
) -> dict[str, Any]:
    """依色卡風格換選非使用者指定家具，最後仍由引擎重算合法座標。"""
    catalog_by_id = {
        str(item.get("furniture_id")): item
        for item in catalog
        if item.get("furniture_id") and item.get("has_model") and item.get("model_url")
    }
    room_engine = room_from_payload(floorplan)
    room_ids = list(dict.fromkeys(
        str(item.get("placement_room_id") or "") for item in scene_objects
    ))
    all_objects: list[dict[str, Any]] = []
    replacements: list[dict[str, str]] = []
    warnings: list[str] = []

    for room_id in room_ids:
        current_items = [
            dict(item) for item in scene_objects
            if str(item.get("placement_room_id") or "") == room_id
        ]
        used_ids = {
            str(item.get("furniture_id")) for item in current_items if _is_user_selected(item)
        }
        prepared: list[dict[str, Any]] = []
        for item in current_items:
            if _is_user_selected(item):
                prepared.append({
                    **item,
                    "position_locked": True,
                    "placement_failed": False,
                    "placement_reason": None,
                })
                continue

            old_id = str(item.get("furniture_id") or "")
            item_type = str(item.get("normalized_type") or "")
            ranked = [
                candidate
                for candidate in _ranked_group_candidates(catalog, (item_type,), style_id)
                if _style_score(candidate, style_id) > 0
                and str(candidate.get("furniture_id")) not in used_ids
            ]
            replacement = next(
                (candidate for candidate in ranked if str(candidate.get("furniture_id")) != old_id),
                ranked[0] if ranked else None,
            )
            if replacement is None:
                prepared.append({
                    **item,
                    "position_locked": False,
                    "placement_failed": False,
                    "placement_reason": None,
                })
                warnings.append(f"{item_type or old_id} 找不到 {style_id} 且具模型的替代品，暫時保留原型號。")
                used_ids.add(old_id)
                continue

            replacement_id = str(replacement["furniture_id"])
            size = layout_catalog_size_cm(replacement)
            next_item = {
                **item,
                "furniture_id": replacement_id,
                "name_zh_raw": replacement.get("name_zh_raw") or replacement.get("name_zh") or replacement_id,
                "normalized_type": replacement.get("normalized_type"),
                "model_url": replacement.get("model_url"),
                "primary_style": replacement.get("primary_style"),
                "size_cm": size,
                "footprint_cm": {"width": size["width"], "depth": size["depth"]},
                "selection_source": "style_card",
                "position_locked": False,
                "placement_failed": False,
                "placement_reason": None,
            }
            prepared.append(next_item)
            used_ids.add(replacement_id)
            if replacement_id != old_id:
                replacements.append({
                    "instance_id": str(item.get("instance_id")),
                    "from_furniture_id": old_id,
                    "to_furniture_id": replacement_id,
                })

        boundary = _region_boundary_by_id(floorplan, room_engine, room_id)
        if boundary is None:
            raise ValueError(f"空間 {room_id} 缺少可用邊界。")
        placed = generate_layout(
            room_engine.width,
            room_engine.depth,
            prepared,
            room=room_engine,
            regions_boundary=boundary,
            place_boundary=boundary,
            window_segments=floorplan.get("window_segments") or [],
            door_segments=floorplan.get("door_segments") or [],
            floorplan=floorplan,
        )
        failed = [item for item in placed if item.get("placement_failed")]
        if failed:
            labels = "、".join(str(item.get("name_zh_raw") or item.get("furniture_id")) for item in failed)
            raise ValueError(f"套用色卡後無法合法擺放：{labels}")
        all_objects.extend(placed)

    return {
        "scene_objects": all_objects,
        "replacements": replacements,
        "protected_instance_ids": [
            str(item.get("instance_id")) for item in scene_objects if _is_user_selected(item)
        ],
        "warnings": list(dict.fromkeys(warnings)),
    }
