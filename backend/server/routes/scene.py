"""場景端點:bootstrap、生成、佈局重算、拖曳驗證、provider 狀態與 agent intake。

家具座標一律由 backend.engine 計算(scene_service 轉接),此處不做擺位。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services.catalog_service import _style_payloads, build_site_payload, load_surface_catalog
from ..services.intake_service import advance_intake, start_intake
from ..services.scene_service import (
    _largest_region_boundary,
    _region_boundary_by_id,
    _regions_boundary,
    build_scene_payload,
    generate_layout,
    get_openrouter_status,
    room_from_payload,
    validate_single_placement,
)
from ..services.style_cards import load_taiwan_style_cards

router = APIRouter()


@router.get("/api/scene/bootstrap")
def scene_bootstrap() -> dict:
    return {
        "styles": _style_payloads(),
        "taiwan_style_cards": load_taiwan_style_cards(),
        "surface_catalog": load_surface_catalog(),
    }


@router.get("/api/scene/provider-status")
def scene_provider_status() -> dict:
    return get_openrouter_status()


@router.post("/api/agent/intake/start")
async def agent_intake_start(payload: dict | None = None) -> dict:
    """Start the Agent-ready intake contract without calling an LLM yet."""
    payload = payload or {}
    return start_intake(str(payload.get("session_id") or "roompilot-local"))


@router.post("/api/agent/intake/answer")
async def agent_intake_answer(payload: dict) -> dict:
    """Advance one guided intake turn; future LLM adapters keep this shape."""
    step = str(payload.get("step") or "")
    answer = str(payload.get("answer") or "").strip()
    if not step or not answer:
        raise HTTPException(status_code=422, detail="step 與 answer 皆為必要欄位。")
    return advance_intake(
        session_id=str(payload.get("session_id") or "roompilot-local"),
        step=step,
        answer=answer,
        brief=payload.get("client_brief"),
    )


@router.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    client_brief = payload.get("client_brief") or {}
    brief_space = client_brief.get("space") or {}
    brief_style = client_brief.get("style") or {}
    brief_occupants = client_brief.get("occupants") or {}

    questionnaire = {
        "space_type": payload.get("space_type") or brief_space.get("type") or "living_room",
        "style_preference": payload.get("style_preference") or (brief_style.get("preferred") or ["auto"])[0],
        "style_card_id": payload.get("style_card_id"),
        "required_furniture": payload.get("required_furniture", []),
        "selected_furniture": payload.get("selected_furniture", []),
        "custom_furniture": payload.get("custom_furniture", []),
        "preferred_colors": payload.get("preferred_colors") or brief_style.get("colors", []),
        "custom_colors": payload.get("custom_colors", []),
        "personal_notes": payload.get("personal_notes", ""),
        "keep_window_clear": bool(payload.get("keep_window_clear", "keep_window_clear" in client_brief.get("constraints", []))),
        "keep_door_clear": bool(payload.get("keep_door_clear", "keep_door_clear" in client_brief.get("constraints", []))),
        "need_storage": bool(payload.get("need_storage", "storage" in client_brief.get("needs", []))),
        "prefer_low_saturation": bool(payload.get("prefer_low_saturation", "low_saturation" in brief_style.get("colors", []))),
        "client_brief": client_brief,
        "occupants": brief_occupants,
        "preferred_materials": brief_style.get("materials", []),
        "floorplan_filename": payload.get("floorplan_filename"),
        "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
        "floorplan_scale_m": payload.get("floorplan_scale_m"),
        "floorplan_override": payload.get("floorplan_override"),  # 人工確認修正的窗/門段

        "wall_option": payload.get("wall_option", "auto"),
        "floor_option": payload.get("floor_option", "auto"),
        "furniture_random_seed": payload.get("furniture_random_seed"),
    }

    return build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm") or brief_space.get("width_cm") or 420),
        room_depth_cm=float(payload.get("room_depth_cm") or brief_space.get("depth_cm") or 360),
    )


@router.post("/api/scene/layout")
async def scene_layout(payload: dict) -> dict:
    """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

    傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
    scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
    """
    objects = payload.get("scene_objects", [])
    floorplan = payload.get("floorplan") or {}
    room = room_from_payload(floorplan)
    room_ids = list(dict.fromkeys(
        str(item.get("placement_room_id"))
        for item in objects
        if item.get("placement_room_id")
    ))
    if room_ids:
        by_instance: dict[str, dict] = {}
        for room_id in room_ids:
            room_objects = [item for item in objects if str(item.get("placement_room_id")) == room_id]
            boundary = _region_boundary_by_id(floorplan, room, room_id)
            if boundary is None:
                continue
            for item in generate_layout(
                room.width,
                room.depth,
                room_objects,
                room=room,
                regions_boundary=boundary,
                place_boundary=boundary,
                hints=payload.get("hints"),
                window_segments=floorplan.get("window_segments") or [],
                door_segments=floorplan.get("door_segments") or [],
                floorplan=floorplan,
            ):
                by_instance[str(item.get("instance_id"))] = item
        return {
            "scene_objects": [
                by_instance.get(str(item.get("instance_id")), item)
                for item in objects
            ]
        }
    return {
        "scene_objects": generate_layout(
            room.width,
            room.depth,
            objects,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=_largest_region_boundary(floorplan, room),
            hints=payload.get("hints"),
            window_segments=floorplan.get("window_segments") or [],
            door_segments=floorplan.get("door_segments") or [],
            floorplan=floorplan,
        )
    }


@router.post("/api/scene/validate")
async def scene_validate(payload: dict) -> dict:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    return validate_single_placement(
        payload.get("floorplan"),
        payload.get("item") or {},
        payload.get("others") or [],
        keep_door_clear=bool(payload.get("keep_door_clear")),
    )
