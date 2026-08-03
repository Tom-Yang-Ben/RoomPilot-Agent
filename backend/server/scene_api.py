"""第 6 步場景生成／編輯與選件 agent 的 API（佇列 7 巨石拆分第三批）。

自 ``main.py`` 抽出的 router 工廠，仿照 ``build_shortlist_router`` 與
``build_engineering_router`` 的掛載方式。純搬家：路由路徑、payload 形狀與
行為都不變。

被測試 ``monkeypatch.setattr(main, ...)`` 錨定的符號（``selection_complete_fn``、
``_furniture_payload_cache``、``_auto_decor_catalog_item`` 等）留在 main 的
命名空間，這裡以工廠參數的 getter 延遲解析，補丁語意不變。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from fastapi import APIRouter, HTTPException

from ..paths import STATIC_DIR
from ..agent.place import resolve_placements
from ..agent.select import (
    SelectionParseError,
    SelectionUnavailableError,
    local_selection_raw,
    parse_selections,
    preselected_from_requirements,
    request_selections,
    requirements_from_context,
)
from ..catalog.runtime_catalog_repository import RuntimeCatalogUnavailable
from .scene_service import (
    _largest_region_boundary,
    _region_boundary_by_id,
    _regions_boundary,
    build_scene_payload,
    curtain_window_hint,
    door_openings_from_segments,
    floorplan_from_editor_payload,
    generate_layout,
    get_openrouter_status,
    resolve_placement_preferences,
    room_from_payload,
    scene_object_in_boundary,
    validate_single_placement,
)


def _floorplan_with_openings(floorplan: dict | None) -> dict | None:
    """補上牆上的門洞，讓 layout 與 generate 兩條路徑回傳同一份契約。

    少了這個鍵，前端還原時用 layout 的 floorplan 覆蓋場景，牆上的開口就
    整批消失——門片還在原位，牆卻是實的，走動視角也走不過去。
    """
    if not isinstance(floorplan, dict):
        return floorplan
    if floorplan.get("door_openings"):
        return floorplan
    return {**floorplan, "door_openings": door_openings_from_segments(floorplan)}


def _payload_number(
    payload: dict,
    key: str,
    default: float | None = None,
    *,
    minimum: float | None = None,
) -> float | None:
    """把 payload 的數值欄位轉成 float。

    型別錯誤是呼叫端的問題，要回 422 說清楚哪個欄位錯；直接 float() 讓
    ValueError 冒到 FastAPI 只會變成 500，前端只看得到「操作失敗」。
    """
    raw = payload.get(key)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise HTTPException(status_code=422, detail=f"{key} 必須是數字。")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{key} 必須是數字。") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise HTTPException(status_code=422, detail=f"{key} 必須是有限數字。")
    if minimum is not None and value < minimum:
        raise HTTPException(status_code=422, detail=f"{key} 不得小於 {minimum:g}。")
    return value


def _payload_mapping(payload: dict, key: str) -> dict:
    raw = payload.get(key)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail=f"{key} 必須是物件。")
    return raw


def _payload_sequence(payload: dict, key: str) -> list:
    raw = payload.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail=f"{key} 必須是陣列。")
    return raw


def _normalize_selection_offers(raw_offers: object) -> dict[str, list[dict]]:
    if not isinstance(raw_offers, dict):
        return {}
    offers: dict[str, list[dict]] = {}
    for room_id, raw_items in raw_offers.items():
        if not isinstance(raw_items, list):
            continue
        normalized_items: list[dict] = []
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            item_type = str(raw_item.get("normalized_type") or raw_item.get("type") or "")
            variant_id = str(raw_item.get("variant_id") or raw_item.get("variantId") or "standard")
            furniture_id = str(
                raw_item.get("furniture_id")
                or raw_item.get("id")
                or f"{room_id}:{item_type}:{variant_id}:{index + 1}"
            )
            if not item_type or not furniture_id:
                continue
            item = dict(raw_item)
            item["furniture_id"] = furniture_id
            item["normalized_type"] = item_type
            item["variant_id"] = variant_id
            item["selection_source"] = str(item.get("selection_source") or "local_rules")
            normalized_items.append(item)
        offers[str(room_id)] = normalized_items
    return offers


def _without_deferred(room_id: str, items: list[dict], requirements: dict) -> list[dict]:
    """濾掉使用者在第 4 步按過暫緩的家具。"""
    requirement = requirements.get(room_id)
    if requirement is None or not requirement.deferred_furniture_ids:
        return items
    return [
        item
        for item in items
        if str(item.get("furniture_id") or "") not in requirement.deferred_furniture_ids
    ]


def _selection_llm_context(context: dict | None) -> dict | None:
    """只把與選件有關的問卷結論送進提示。

    完整 ``room_requirements`` 含牆面、色票與逐面材質，動輒數十 KB；逐房
    需求已由 ``requirements_from_context`` 收斂後隨房間送出，這裡再塞一次
    只會稀釋規則並拖慢呼叫。
    """
    if not isinstance(context, dict):
        return None
    keep = ("basic_answers", "visual_preferences")
    trimmed = {key: context[key] for key in keep if context.get(key)}
    return trimmed or None


def _selection_response(
    selected: dict[str, list],
    *,
    source: str,
    model: str | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "source": source,
        "model": model,
        "warnings": warnings or [],
        "rooms": [
            {
                "room_id": room_id,
                "items": [
                    {
                        **entry.item,
                        "count": entry.count,
                        "selection_source": entry.item.get("selection_source") or source,
                    }
                    for entry in entries
                ],
            }
            for room_id, entries in selected.items()
        ],
    }


def _repair_ready_items(objects: list) -> tuple[list[dict], dict[str, str | None]]:
    """把前端場景物件轉成擺放紀律看得懂的形狀。

    第 6 步的 scene_objects 用 ``furniture_id`` 當「這一件」的身分，型錄 id 放在
    ``catalog_furniture_id``；Yen 的 ``resolve_placements`` 反過來——``instance_id``
    是身分，``furniture_id`` 要能和候選池比對才換得了小款。這裡換過去，修完再換
    回來，前端拿到的身分才不會在換小款時整個換掉。
    """
    original_catalog: dict[str, str | None] = {}
    items: list[dict] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        instance_id = str(obj.get("furniture_id") or "")
        catalog_id = obj.get("catalog_furniture_id")
        original_catalog[instance_id] = str(catalog_id) if catalog_id else None
        items.append({
            **obj,
            "instance_id": instance_id,
            "furniture_id": str(catalog_id or instance_id),
        })
    return items, original_catalog


def _restore_scene_identity(objects: list, original_catalog: dict[str, str | None]) -> list[dict]:
    """把 instance_id 換回 furniture_id，換過小款的則帶上新的型錄 id。"""
    restored: list[dict] = []
    for obj in objects:
        instance_id = str(obj.get("instance_id") or "")
        if not instance_id:
            restored.append(obj)
            continue
        catalog_id = str(obj.get("furniture_id") or "")
        item = dict(obj)
        item.pop("instance_id", None)
        item["furniture_id"] = instance_id
        item["catalog_furniture_id"] = (
            catalog_id if catalog_id and catalog_id != instance_id
            else original_catalog.get(instance_id)
        )
        restored.append(item)
    return restored


_AUTO_DECOR_LABELS = {
    "rug": "地毯",
    "plant": "植栽",
    "light": "燈具",
}


_CURTAIN_MODEL_PATH = "models/roompilot-curtain.glb"


def _curtain_catalog_item() -> dict | None:
    """布簾是固定假想品項，不走型錄查找。

    以前它無條件宣告 model_url 指向 /static/models/roompilot-curtain.glb，但那個檔案
    不在 repo 裡（static/ 底下沒有任何 .glb），所以每次自動軟裝都保證產生一個 404，
    3D 只能靠白色替代物兜底。與其硬塞一個壞掉的品項，不如照其他軟裝角色的作法：
    檔案不存在就回 None，由呼叫端列進 decor_summary.skipped 說明原因。
    """
    if not (STATIC_DIR / _CURTAIN_MODEL_PATH).is_file():
        return None
    return {
        "furniture_id": "roompilot-auto-curtain",
        "normalized_type": "curtain",
        "name_zh_raw": "自動配置布簾",
        "size_cm": {"width": 240, "depth": 12, "height": 240},
        "model_url": f"/static/{_CURTAIN_MODEL_PATH}",
        "has_model": True,
        "auto_decor_role": "curtain",
        "position_locked": False,
    }


def build_scene_router(
    *,
    site_payload_getter: Callable[[], dict],
    catalog_status_getter: Callable[[], dict],
    style_payloads_getter: Callable[[], list],
    surface_catalog_getter: Callable[[], dict],
    taiwan_style_cards_getter: Callable[[], list],
    furniture_pool_getter: Callable[[], tuple],
    selection_complete_getter: Callable[[], Callable | None],
    auto_decor_item_fn: Callable[..., dict | None],
) -> APIRouter:
    """組出 /api/scene/* 與 /api/agent/furniture/select 的 router。

    getter 參數在 main.py 以 ``lambda: X()`` 形式提供：呼叫時才解析 main 的
    模組全域，tests 對 main 的 monkeypatch 才會被路由看見。
    """
    router = APIRouter()

    @router.get("/api/scene/bootstrap")
    def scene_bootstrap() -> dict:
        return {
            "styles": style_payloads_getter(),
            "taiwan_style_cards": taiwan_style_cards_getter(),
            "surface_catalog": surface_catalog_getter(),
            "catalog_status": catalog_status_getter(),
        }

    @router.get("/api/scene/provider-status")
    def scene_provider_status() -> dict:
        return get_openrouter_status()

    @router.post("/api/agent/furniture/select")
    async def agent_furniture_select(payload: dict) -> dict:
        """Server-side furniture selection gate for Yen selection discipline."""
        raw_rooms = payload.get("rooms") or []
        if not isinstance(raw_rooms, list):
            raise HTTPException(status_code=422, detail="rooms must be a list")
        rooms = []
        for room in raw_rooms:
            if not isinstance(room, dict):
                continue
            room_type = str(room.get("room_type") or room.get("type") or "")
            if room_type in {"default", "unknown", "other"}:
                room_type = ""
            rooms.append({
                **room,
                "room_id": str(room.get("room_id") or room.get("id") or ""),
                "room_type": room_type,
            })
        offers = _normalize_selection_offers(payload.get("offers"))
        style_id = payload.get("style_id")
        context = payload.get("context") if isinstance(payload.get("context"), dict) else None
        llm_selection = payload.get("llm_selection")
        warnings: list[str] = []

        # 逐房問卷需求是兩條路徑共用的輸入：LLM 走提示，本地規則走確定性挑選。
        requirements = requirements_from_context(context)
        preselected = preselected_from_requirements(rooms, offers, requirements)

        # payload 帶 llm_selection 時視為外部已算好的結果，只做驗證；否則由
        # 伺服器自己呼叫 OpenRouter，前端不需要也不應該持有 API 金鑰。
        complete = (
            (lambda _messages: ("payload/llm_selection", llm_selection))
            if isinstance(llm_selection, dict)
            else selection_complete_getter()
        )

        if complete is not None:
            try:
                selected, model = request_selections(
                    rooms,
                    offers,
                    str(style_id) if style_id else None,
                    complete=complete,
                    preselected=preselected,
                    context=_selection_llm_context(context),
                    requirements=requirements,
                )
                return _selection_response(selected, source="openrouter", model=model)
            except (SelectionParseError, SelectionUnavailableError) as exc:
                warnings.append(f"LLM 選擇未通過規則驗證，已改用本地規則：{exc}")

        try:
            selected = parse_selections(
                local_selection_raw(rooms, offers, requirements),
                rooms,
                offers,
                preselected=preselected,
                requirements=requirements,
            )
            return _selection_response(selected, source="local_rules", warnings=warnings)
        except SelectionParseError as exc:
            warnings.append(f"本地規則無法完整驗證候選家具，已保留第一批候選：{exc}")
            # 連驗證都過不了時仍守住一條線：使用者暫緩的家具在任何路徑都不回填。
            return {
                "source": "local_rules_unvalidated",
                "model": None,
                "warnings": warnings,
                "rooms": [
                    {
                        "room_id": room_id,
                        "items": [
                            {
                                **item,
                                "count": int(item.get("count") or 1),
                                "selection_source": item.get("selection_source") or "local_rules_unvalidated",
                            }
                            for item in _without_deferred(room_id, items, requirements)[:8]
                        ],
                    }
                    for room_id, items in offers.items()
                    if items
                ],
            }

    @router.post("/api/scene/generate")
    async def generate_scene(payload: dict) -> dict:
        site_payload = site_payload_getter()

        client_brief = _payload_mapping(payload, "client_brief")
        brief_space = _payload_mapping(client_brief, "space")
        brief_style = _payload_mapping(client_brief, "style")
        brief_occupants = _payload_mapping(client_brief, "occupants")
        test2_questionnaire = _payload_mapping(payload, "questionnaire")

        questionnaire = {
            "space_type": payload.get("space_type") or brief_space.get("type") or "living_room",
            "style_preference": payload.get("style_preference") or (brief_style.get("preferred") or ["auto"])[0],
            "style_card_id": payload.get("style_card_id"),
            "required_furniture": payload.get("required_furniture", []),
            "selected_furniture": payload.get("selected_furniture", []),
            "selected_furniture_exact": payload.get("selected_furniture_exact") is True,
            "custom_furniture": payload.get("custom_furniture", []),
            "preferred_colors": payload.get("preferred_colors") or brief_style.get("colors", []),
            "custom_colors": payload.get("custom_colors", []),
            "personal_notes": payload.get("personal_notes", ""),
            "test2_questionnaire": test2_questionnaire,
            "keep_window_clear": bool(payload.get("keep_window_clear", "keep_window_clear" in client_brief.get("constraints", []))),
            "keep_door_clear": bool(payload.get("keep_door_clear", "keep_door_clear" in client_brief.get("constraints", []))),
            "need_storage": bool(payload.get("need_storage", "storage" in client_brief.get("needs", []))),
            "prefer_low_saturation": bool(payload.get("prefer_low_saturation", "low_saturation" in brief_style.get("colors", []))),
            "client_brief": client_brief,
            "occupants": brief_occupants,
            "preferred_materials": brief_style.get("materials", []),
            "floorplan_filename": payload.get("floorplan_filename"),
            "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
            "layout_json": payload.get("layout_json"),
            "floorplan_editor": payload.get("floorplan_editor"),
            "wall_option": payload.get("wall_option", "auto"),
            "floor_option": payload.get("floor_option", "auto"),
            "furniture_random_seed": payload.get("furniture_random_seed"),
        }

        scene_payload = build_scene_payload(
            site_payload=site_payload,
            questionnaire=questionnaire,
            floorplan_path=payload.get("floorplan_filename"),
            room_width_cm=(
                _payload_number(payload, "room_width_cm", minimum=0)
                or _payload_number(brief_space, "width_cm", minimum=0)
                or 420
            ),
            room_depth_cm=(
                _payload_number(payload, "room_depth_cm", minimum=0)
                or _payload_number(brief_space, "depth_cm", minimum=0)
                or 360
            ),
        )
        return {
            **scene_payload,
            "scene_json": deepcopy(scene_payload),
        }

    @router.post("/api/scene/layout")
    async def scene_layout(payload: dict) -> dict:
        """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

        傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
        scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
        放不下的家具走與 /api/scene/generate 相同的擺放紀律:換小、移除或升級人工。
        """
        objects = _payload_sequence(payload, "scene_objects")
        editor_floorplan = payload.get("floorplan_editor")
        if isinstance(editor_floorplan, dict) and editor_floorplan:
            floorplan, room = floorplan_from_editor_payload(editor_floorplan)
        else:
            floorplan = _payload_mapping(payload, "floorplan")
            room = room_from_payload(floorplan)
        placement_room_id = payload.get("placement_room_id")
        placement_variant = str(payload.get("placement_variant") or "A").upper()
        if placement_variant not in {"A", "B"}:
            placement_variant = "A"
        place_boundary = (
            _region_boundary_by_id(floorplan, room, placement_room_id)
            or _largest_region_boundary(floorplan, room)
        )
        placement_preferences = _payload_mapping(payload, "placement_preferences")
        _margin, _clearance, applied_preferences, ignored_preferences = (
            resolve_placement_preferences(placement_preferences)
        )

        items, original_catalog = _repair_ready_items(objects)

        def place(working_items: list[dict]) -> list[dict]:
            return generate_layout(
                room.width,
                room.depth,
                working_items,
                room=room,
                regions_boundary=_regions_boundary(floorplan, room),
                place_boundary=place_boundary,
                floorplan=floorplan,
                placement_variant=placement_variant,
                placement_preferences=placement_preferences,
            )

        scene_objects = place(items)
        report: list[dict] = []
        if any(obj.get("placement_failed") for obj in scene_objects):
            # 第一次擺放失敗時才付出重算成本。這裡不修的話,第 6 步換上放不下的
            # 家具只會留下一張紅色待處理卡,永遠等不到自動換小款。
            protected_ids = {
                str(item.get("furniture_id"))
                for item in items
                if item.get("furniture_id")
                and (
                    item.get("user_specified")
                    or item.get("user_required")
                    or item.get("position_locked")
                )
            }
            try:
                pool = [
                    candidate
                    for candidate in furniture_pool_getter()
                    if not candidate.get("size_is_implausible")
                ]
            except RuntimeCatalogUnavailable:
                # 型錄暫時讀不到就只回報,不要因為換小款失敗而擋掉整次重排。
                pool = []
            scene_objects, _items, report = resolve_placements(
                scene_objects,
                items,
                pool,
                engine_place_fn=place,
                protected_ids=protected_ids,
            )

        return {
            # door_openings 必須與 /api/scene/generate 同形狀：場景還原與重算
            # 都走這條，回傳少了門洞就會把牆上的開口洗掉，門變成實牆
            # （2026-08-03 Ben 實走發現，第 4 步確認的門位置其實是對的）。
            "floorplan": _floorplan_with_openings(floorplan),
            "scene_objects": _restore_scene_identity(scene_objects, original_catalog),
            "placement_resolution_report": report,
            # 明說哪些偏好真的進了引擎、哪些還沒有對應動作，避免整條 no-op 又沒人發現。
            "placement_preferences_applied": applied_preferences,
            "placement_preferences_ignored": ignored_preferences,
        }

    @router.post("/api/scene/decorate")
    async def scene_decorate(payload: dict) -> dict:
        """依風格加入軟裝，所有最終座標仍由家具引擎決定。"""
        _payload_sequence(payload, "scene_objects")
        editor_floorplan = payload.get("floorplan_editor")
        if isinstance(editor_floorplan, dict) and editor_floorplan:
            floorplan, room = floorplan_from_editor_payload(editor_floorplan)
        else:
            floorplan = _payload_mapping(payload, "floorplan")
            room = room_from_payload(floorplan)

        placement_room_id = payload.get("placement_room_id")
        place_boundary = (
            _region_boundary_by_id(floorplan, room, placement_room_id)
            or _largest_region_boundary(floorplan, room)
        )
        region = next(
            (
                item
                for item in floorplan.get("room_regions", [])
                if str(item.get("room_id")) == str(placement_room_id)
            ),
            {},
        )
        confirmed_room = payload.get("room") if isinstance(payload.get("room"), dict) else {}
        room_type = str(
            region.get("room_type")
            or confirmed_room.get("type")
            or confirmed_room.get("room_type")
            or "default"
        )
        existing = [dict(item) for item in payload.get("scene_objects", [])]
        room_id = str(placement_room_id or "default")
        # 舊版本的 default 軟裝與目前房間的軟裝都先移除，確保每次重跑是重算而非累加。
        existing = [
            item
            for item in existing
            if not item.get("auto_decor_role")
            or str(item.get("auto_decor_room_id") or "default") not in {room_id, "default"}
        ]
        room_items = []
        for item in existing:
            assigned_room_id = item.get("placement_room_id") or item.get("auto_decor_room_id")
            if assigned_room_id:
                if str(assigned_room_id) == room_id:
                    room_items.append(item)
                continue
            if scene_object_in_boundary(item, room, place_boundary):
                room_items.append(item)
        room_types = {
            str(item.get("normalized_type") or "")
            for item in room_items
        }
        rug_anchors = {"sofa", "sofa-bed", "bed", "bed-frame", "dining-table"}
        companion_anchors = rug_anchors | {"desk", "armchair"}
        requested_roles = []
        if room_types & companion_anchors:
            requested_roles.append("light")
        if room_types & rug_anchors:
            requested_roles.append("rug")
        if room_type == "balcony" or (
            room_type in {"living_room", "dining_room", "default"}
            and room_types & companion_anchors
        ):
            requested_roles.append("plant")
        if curtain_window_hint(
            floorplan,
            room_width_cm=room.width,
            room_depth_cm=room.depth,
            boundary=place_boundary,
        ) and room_type in {"living_room", "bedroom", "dining_room", "default"}:
            requested_roles.append("curtain")

        additions: list[dict] = []
        skipped_roles: list[dict] = []
        if "curtain" in requested_roles:
            curtain = _curtain_catalog_item()
            if curtain is None:
                skipped_roles.append(
                    {
                        "role": "curtain",
                        "label": "布簾",
                        "reason": "布簾模型檔尚未進版控，本次略過（3D 不會出現缺檔的替代方塊）。",
                    }
                )
            else:
                additions.append(curtain)
        used_ids = {str(item.get("furniture_id")) for item in existing}
        boundary_width_cm = boundary_depth_cm = 0.0
        if place_boundary is not None:
            min_x, min_y, max_x, max_y = place_boundary.bounds
            boundary_width_cm = max((max_x - min_x) - 20, 0)
            boundary_depth_cm = max((max_y - min_y) - 20, 0)
        rug_anchor = next(
            (
                item
                for item in room_items
                if str(item.get("normalized_type") or "") in rug_anchors
            ),
            None,
        )
        rug_anchor_size = (rug_anchor or {}).get("size_cm") or {}
        rug_max_footprint = (
            min(boundary_width_cm, float(rug_anchor_size.get("width") or boundary_width_cm)),
            min(boundary_depth_cm, float(rug_anchor_size.get("depth") or boundary_depth_cm)),
        )
        for role in ("rug", "plant", "light"):
            if role in requested_roles:
                addition = auto_decor_item_fn(
                    role,
                    payload.get("style"),
                    used_ids,
                    rug_max_footprint if role == "rug" else None,
                )
                if addition is None:
                    skipped_roles.append(
                        {
                            "role": role,
                            "label": _AUTO_DECOR_LABELS[role],
                            "reason": f"型錄中沒有可用的{_AUTO_DECOR_LABELS[role]} GLB，本次略過。",
                        }
                    )
                    continue
                additions.append(addition)
                used_ids.add(str(addition.get("furniture_id")))
        for item in additions:
            item["auto_decor_room_id"] = room_id
        rug = next((item for item in additions if item["auto_decor_role"] == "rug"), None)
        if rug is not None:
            rug["placement_relation"] = {
                "kind": "under",
                "target_types": ["sofa", "sofa-bed", "bed", "bed-frame", "dining-table"],
            }
        for item in additions:
            if item["auto_decor_role"] in {"plant", "light"} and not (
                room_type == "balcony" and item["auto_decor_role"] == "plant"
            ):
                item["placement_relation"] = {
                    "kind": "adjacent",
                    "target_types": [
                        "sofa", "sofa-bed", "bed", "bed-frame", "desk",
                        "dining-table", "armchair",
                    ],
                }

        scene_objects = generate_layout(
            room.width,
            room.depth,
            [*existing, *additions],
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=place_boundary,
            floorplan=floorplan,
            preserve_existing_count=len(existing),
        )
        # 自動軟裝放不下就不硬塞，也不把失敗標記留在 3D 場景裡。
        scene_objects = [
            item
            for item in scene_objects
            if not (item.get("auto_decor_role") and item.get("placement_failed"))
        ]
        return {
            "scene_objects": scene_objects,
            "decor_summary": {
                "requested": requested_roles,
                "placed": [
                    item["auto_decor_role"]
                    for item in scene_objects
                    if item.get("auto_decor_role") and not item.get("placement_failed")
                ],
                "skipped": skipped_roles,
                "engine": "furniture_engine",
            },
        }

    @router.post("/api/scene/validate")
    async def scene_validate(payload: dict) -> dict:
        """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
        editor_floorplan = payload.get("floorplan_editor")
        floorplan = _payload_mapping(payload, "floorplan") or None
        if isinstance(editor_floorplan, dict) and editor_floorplan:
            floorplan, _ = floorplan_from_editor_payload(editor_floorplan)
        # 帶上偏好,拖曳驗證才會和 /api/scene/layout 用同一份禁區規則。
        return validate_single_placement(
            floorplan,
            _payload_mapping(payload, "item"),
            _payload_sequence(payload, "others"),
            _payload_mapping(payload, "placement_preferences"),
        )

    return router
