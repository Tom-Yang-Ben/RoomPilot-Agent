"""第 8 步 AI 寫實生圖 adapter：把專案 scene_json 對應成 Gen_Pic Agent 文件，
逐房視角經 OpenRouter nano banana 生成寫實室內圖（不移動擺設），並提供整批一次改圖。

邊界（見 AGENTS.md / docs/owners/BELLA.md）：

- 本模組是 Bella（`backend/server/`）對 Yen（`backend/agent/` Gen_Pic Agent）的
  adapter：只做「scene_json → agent 文件」的資訊補充與呼叫編排，不重做 agent
  的生圖流程或失敗政策（3 次主模型 → 提示原因 → fallback，均在 GenPicAgent）。
- 座標一律沿用 engine 既有結果；提示詞不含數值與位置措辭（定案），
  畫面位置由逐房 3D 截圖 img2img 鎖定，這裡不產生任何新座標。
- 家電只作為生圖畫面 context（`render_context.appliance_requirements`），
  不進家具清單或配置。
- 未設定 `OPENROUTER_API_KEY` 時明確回報「尚未連接」，不得假成功（第 8 步契約）。

主要進入點：``generate_room_images`` 逐房生圖、``edit_room_image`` 整批一次改圖。
"""
from __future__ import annotations

import os
from typing import Any

from ..agent.documents import (
    ImageLibraryDoc,
    ImageRecord,
    LayoutRoom,
    LockManifestDoc,
    PaletteOption,
    RequirementDoc,
    RequirementItem,
    SceneDoc,
)
from ..agent.llm import (
    DEFAULT_IMAGE_FALLBACK_MODEL,
    DEFAULT_IMAGE_MODEL,
    OpenRouterGateway,
)
from ..agent.subagents import GenPicAgent, GenPicFailure

__all__ = [
    "AiRenderNotConfigured",
    "GenPicFailure",
    "ai_render_status",
    "generate_room_images",
    "edit_room_image",
]

_DEFAULT_ROOM_SIDE_CM = 400.0


class AiRenderNotConfigured(RuntimeError):
    """OpenRouter 生圖金鑰未設定；呼叫端應回 503，不得假成功。"""


def ai_render_status() -> dict[str, Any]:
    """回報生圖服務是否可用與使用的模型（token 不外洩，只回布林與模型 id）。"""
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return {
        "configured": bool(key),
        "provider": "openrouter",
        "model": os.getenv("ROOMPILOT_GENPIC_MODEL", "").strip() or DEFAULT_IMAGE_MODEL,
        "fallback_model": os.getenv("ROOMPILOT_GENPIC_FALLBACK_MODEL", "").strip()
        or DEFAULT_IMAGE_FALLBACK_MODEL,
    }


# --------------------------------------------------------------- data URL 工具


def _strip_data_url(value: Any) -> str:
    """把 ``data:image/png;base64,xxxx`` 取回純 base64；已是純 base64 則原樣回傳。"""
    text = str(value or "").strip()
    if text.startswith("data:") and "," in text:
        return text.split(",", 1)[1]
    return text


def _as_data_url(image_b64: Any) -> str:
    text = str(image_b64 or "")
    if text.startswith("data:"):
        return text
    return f"data:image/png;base64,{text}"


# ----------------------------------------------------------- scene → agent 文件


def _placed_objects(scene: dict, room_id: str) -> list[dict]:
    """取出屬於此房間、且成功擺放的家具（跳過 placement_failed）。"""
    objects = [
        obj
        for obj in (scene.get("scene_objects") or [])
        if isinstance(obj, dict) and not obj.get("placement_failed")
    ]
    room_ids = {
        str(obj.get("placement_room_id"))
        for obj in objects
        if obj.get("placement_room_id")
    }
    if room_id in room_ids:
        return [obj for obj in objects if str(obj.get("placement_room_id")) == room_id]
    if len(room_ids) <= 1:
        # 單房（single_room_mode）或家具未分房：全部家具都屬於這個視角房間。
        return objects
    return [obj for obj in objects if str(obj.get("placement_room_id")) == room_id]


def _room_dims(scene: dict) -> tuple[float, float]:
    # ponytail: 用整體平面圖尺寸當房間長寬。單房為精確值；多房為近似值，
    # 僅影響提示詞的相對位置措辭（真正鎖定擺設的是逐房 3D 截圖 img2img）。
    floor = scene.get("floorplan") or {}
    try:
        width = float(floor.get("width_cm") or 0) or _DEFAULT_ROOM_SIDE_CM
        depth = float(floor.get("depth_cm") or 0) or _DEFAULT_ROOM_SIDE_CM
    except (TypeError, ValueError):
        width, depth = _DEFAULT_ROOM_SIDE_CM, _DEFAULT_ROOM_SIDE_CM
    return width, depth


def _placed_rows(objects: list[dict]) -> list[dict]:
    """取 genpic 畫面描述需要的欄位：名稱、類型與材質（數值與座標不進提示詞）。"""
    return [
        {
            "id": obj.get("id") or obj.get("furniture_id") or "",
            "name": obj.get("name_zh_raw")
            or obj.get("name_en")
            or obj.get("normalized_type")
            or "家具",
            "type": obj.get("normalized_type") or "",
            "material": str(obj.get("material") or "").strip(),
        }
        for obj in objects
    ]


def _surface_text(scene: dict, option_key: str) -> str | None:
    """把 design_choices 的 floor/wall 選擇解析成材質名稱；auto 交給風格預設。"""
    choice = str(((scene.get("design_choices") or {}).get(option_key)) or "").strip()
    if not choice or choice == "auto":
        return None
    for surface in (scene.get("surface_catalog") or {}).get("surfaces") or []:
        if isinstance(surface, dict) and str(surface.get("surface_id")) == choice:
            name = surface.get("name_zh") or surface.get("material_group") or choice
            color = surface.get("color_zh")
            return f"{name}（{color}）" if color else str(name)
    return choice


def _requirement_doc(scene: dict) -> RequirementDoc:
    """組出生圖需求文件：風格、地板/牆面材質、家電 context、色卡、補充需求。"""
    requirement = scene.get("requirement") or {}
    style = str(
        requirement.get("style") or (scene.get("style") or {}).get("style_id") or ""
    ).strip()

    materials: dict[str, Any] = {}
    floor = _surface_text(scene, "floor_option")
    if floor:
        materials["地板"] = floor
    wall = _surface_text(scene, "wall_option")
    if wall:
        materials["牆面"] = wall

    appliances: list[RequirementItem] = []
    for index, item in enumerate(
        (scene.get("render_context") or {}).get("appliance_requirements") or []
    ):
        if not isinstance(item, dict):
            continue
        text = str(item.get("name_zh_raw") or item.get("normalized_type") or "").strip()
        if not text:
            continue
        quantity = item.get("quantity")
        if isinstance(quantity, int) and quantity > 1:
            text = f"{text}×{quantity}"
        appliances.append(
            RequirementItem(
                req_id=str(item.get("appliance_id") or f"appliance_{index}"),
                text=text,
                room_id=None,
                category=None,
                source="render_context",
            )
        )

    palette_options: list[PaletteOption] = []
    card = scene.get("style_card") or {}
    if card.get("card_id") or card.get("palette_hex"):
        palette_options.append(
            PaletteOption(
                palette_id=str(card.get("card_id") or "style_card"),
                name=str(card.get("name_zh") or card.get("card_id") or "色卡"),
                colors=[str(color) for color in (card.get("palette_hex") or [])],
            )
        )

    notes = "；".join(
        str(note).strip()
        for note in (requirement.get("constraints") or {}).get("notes") or []
        if str(note).strip()
    )
    return RequirementDoc(
        styles=[style] if style else [],
        materials=materials,
        appliances=appliances,
        palette_options=palette_options,
        notes=notes,
    )


def _palette_dict(requirements: RequirementDoc) -> dict | None:
    if not requirements.palette_options:
        return None
    option = requirements.palette_options[0]
    return {
        "palette_id": option.palette_id,
        "name": option.name,
        "colors": list(option.colors),
    }


def _viewpoint(room: dict, reference_b64: str, requirements: RequirementDoc) -> dict:
    """逐房視角備註：逐房補充與整體補充需求原文照列（定案：不加前綴標籤；
    房間名已在提示詞開頭，不重複）。"""
    parts = [str(room.get("note") or "").strip(), requirements.notes]
    return {
        "viewpoint_id": str(room.get("room_id") or ""),
        "note": "；".join(part for part in parts if part),
        "image_b64": reference_b64,
    }


def _layout_room(room: dict, room_id: str, width_cm: float, depth_cm: float) -> LayoutRoom:
    return LayoutRoom(
        room_id=room_id,
        name=str(room.get("room_label") or room_id),
        width_cm=width_cm,
        depth_cm=depth_cm,
    )


# ------------------------------------------------------------------- 對外流程


def generate_room_images(
    scene: dict, rooms: list[dict], *, gateway: Any | None = None
) -> dict:
    """逐房視角送 Gen_Pic Agent（OpenRouter nano banana）生圖。

    ``rooms`` 每項：``{room_id, room_label, reference_png_data_url, note?}``。
    回傳 ``{"results": [...], "rooms": [{room_id, room_label, lock_manifest}...]}``；
    ``rooms`` 供整批一次改圖時鎖定「只改指定內容、其餘不動」。單一房間失敗
    （主模型與 fallback 皆失敗）只標記該房 failed，其餘房間照常回傳。
    """
    gateway = gateway or OpenRouterGateway()
    if not getattr(gateway, "available", False):
        raise AiRenderNotConfigured("openrouter_api_key_not_configured")

    requirements = _requirement_doc(scene)
    palette = _palette_dict(requirements)
    width_cm, depth_cm = _room_dims(scene)
    agent = GenPicAgent(gateway)
    images = ImageLibraryDoc()

    results: list[dict] = []
    room_state: list[dict] = []
    for room in rooms:
        room_id = str(room.get("room_id") or "").strip()
        reference_b64 = _strip_data_url(room.get("reference_png_data_url"))
        rows = _placed_rows(_placed_objects(scene, room_id))
        scene_doc = SceneDoc(rooms={room_id: {"placed": rows, "failed": []}})
        layout_room = _layout_room(room, room_id, width_cm, depth_cm)
        viewpoint = _viewpoint(room, reference_b64, requirements)
        try:
            record = agent.render_room(
                requirements,
                scene_doc,
                layout_room,
                images,
                stage="full_render",
                palette=palette,
                viewpoint=viewpoint,
            )
            manifest = agent.lock_manifest_for(
                requirements,
                scene_doc,
                layout_room,
                palette=palette,
                viewpoint=viewpoint,
            )
        except GenPicFailure as exc:
            results.append(
                {
                    "room_id": room_id,
                    "room_label": layout_room.name,
                    "status": "failed",
                    "notices": exc.notices,
                }
            )
            continue
        results.append(
            {
                "room_id": room_id,
                "room_label": layout_room.name,
                "status": "completed",
                "image_id": record.image_id,
                "image_data_url": _as_data_url(record.image_ref),
                "model": record.model,
                "notices": record.notices,
            }
        )
        room_state.append(
            {
                "room_id": room_id,
                "room_label": layout_room.name,
                "lock_manifest": manifest.to_dict(),
            }
        )
    return {"results": results, "rooms": room_state}


def edit_room_image(
    room_id: str,
    feedback: str,
    base_image_data_url: str,
    lock_manifest: dict,
    *,
    gateway: Any | None = None,
) -> dict:
    """整批一次改圖：以鎖定清單約束「只改使用者指定內容、其餘與原圖一致」。

    ``base_image_data_url`` 是要修改的當前圖（前端持有並回傳）；額度計數由呼叫端
    （route）在 project workflow 強制，此處只執行一次編輯請求。
    """
    gateway = gateway or OpenRouterGateway()
    if not getattr(gateway, "available", False):
        raise AiRenderNotConfigured("openrouter_api_key_not_configured")

    agent = GenPicAgent(gateway)
    images = ImageLibraryDoc()
    images.records.append(
        ImageRecord(
            image_id=f"img_{room_id}_base",
            room_id=room_id,
            stage="full_render",
            image_ref=_strip_data_url(base_image_data_url),
            seq=1,
        )
    )
    record = agent.edit_room(
        LockManifestDoc.from_dict(lock_manifest), feedback, images, room_id
    )
    return {
        "room_id": room_id,
        "status": "completed",
        "image_id": record.image_id,
        "image_data_url": _as_data_url(record.image_ref),
        "model": record.model,
        "notices": record.notices,
    }
