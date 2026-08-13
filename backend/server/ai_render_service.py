"""第 8 步 AI 寫實生圖 adapter：把專案 scene_json 對應成 Gen_Pic Agent 文件，
逐房視角經 OpenRouter nano banana 生成寫實室內圖（不移動擺設），並提供整批一次改圖。

邊界（見 AGENTS.md / docs/owners/BELLA.md）：

- 本模組是 Bella（`backend/server/`）對 Yen（`backend/agent/` Gen_Pic Agent）的
  adapter：只做「scene_json → agent 文件」的資訊補充與呼叫編排，不重做 agent
  的生圖流程或失敗政策（3 次主模型 → 提示原因 → fallback，均在 GenPicAgent）。
- 座標一律沿用 engine 既有結果；提示詞不含數值與位置措辭（定案），
  畫面位置由逐房 3D 截圖 img2img 鎖定，這裡不產生任何新座標。
- 生圖色調權威是 `backend/catalog/data/taiwan_style_cards.json`（以 card_id
  回查）；`scene_json.style_card.palette_hex` 是前端風格包寫入的 3D 場景用色
  （牆/家具主色/地板/點綴），不直接進提示詞。
- 家電只作為生圖畫面 context（`render_context.appliance_requirements`），
  不進家具清單或配置。
- 未設定 `OPENROUTER_API_KEY` 時明確回報「尚未連接」，不得假成功（第 8 步契約）。

主要進入點：``generate_room_images`` 逐房生圖、``edit_room_image`` 整批一次改圖。
"""
from __future__ import annotations

import base64
import binascii
import concurrent.futures
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
from .style_cards import load_taiwan_style_cards

__all__ = [
    "AiRenderNotConfigured",
    "AiRenderReferenceMissing",
    "GenPicFailure",
    "ai_render_status",
    "generate_room_images",
    "generate_palette_images",
    "edit_room_image",
]

_DEFAULT_ROOM_SIDE_CM = 400.0

# Nano Banana Pro（Gemini 3 Pro Image）：第 7 步代表房「三色卡比較」用較高階模型
# (使用者指定)。可用 ROOMPILOT_GENPIC_PALETTE_MODEL 覆蓋;pro 失敗時 fallback
# 回一般 nano banana(DEFAULT_IMAGE_MODEL)。
DEFAULT_PALETTE_IMAGE_MODEL = "google/gemini-3-pro-image-preview"


class AiRenderNotConfigured(RuntimeError):
    """OpenRouter 生圖金鑰未設定；呼叫端應回 503，不得假成功。"""


class AiRenderReferenceMissing(ValueError):
    """視角參考截圖缺漏或無法解碼；呼叫端應回 422。

    參考截圖是 img2img 鎖住家具與格局的唯一手段。少了它，模型只會照文字重畫
    一個房間——畫面看起來仍然「成功」，但已經不是使用者鎖定的那個空間。所以
    這裡寧可整個請求失敗，也不接受靜默降級成純文字生圖（第 8 步契約「不得假
    成功」的同一條原則）。
    """


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


def _reference_b64(room: dict) -> str:
    """取出該房視角截圖的純 base64，並確認它真的解得開、有內容。

    路由已擋過一次格式，這裡是最後一道：``build_render_request`` 只用真值判斷
    決定要不要附圖（``skills/genpic/__init__.py``），空字串會靜默變成純文字請求，
    沒有例外也沒有 notices。與其讓使用者拿到一張構圖不對的圖，不如在這裡失敗。
    """
    room_id = str(room.get("room_id") or "").strip() or "(未指定房間)"
    reference = _strip_data_url(room.get("reference_png_data_url"))
    if not reference:
        raise AiRenderReferenceMissing(f"{room_id} 缺少 3D 視角截圖")
    try:
        decoded = base64.b64decode(reference, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AiRenderReferenceMissing(f"{room_id} 的 3D 視角截圖不是有效的 base64") from exc
    if not decoded:
        raise AiRenderReferenceMissing(f"{room_id} 的 3D 視角截圖是空的")
    return reference


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
    if not room_ids:
        # 家具完全未分房（單房或未標記 placement_room_id）：全部家具都屬於這個視角房間。
        return objects
    # 家具已分房：嚴格只回傳標記為此 room_id 的家具。此房沒有家具時回空，
    # 不可把別房家具挪用給這個視角房間（指南 §5／§3E，逐房 room_id 分房）。
    return [obj for obj in objects if str(obj.get("placement_room_id")) == room_id]


def _room_dims(scene: dict, room_id: str = "") -> tuple[float, float]:
    """該房長寬（公分）：優先取 ``floorplan.room_regions`` 的外接矩形。

    第 4 步確認過的房間輪廓會以同一組 room_id 寫進 room_regions，逐房生圖因此
    拿得到真正屬於這個房間的尺寸（廚房提示詞要報面積與長寬）。
    ponytail: 查不到（舊 DXF 直讀、單房手動模式）才退回整體平面圖尺寸——單房
    為精確值，多房為近似值。
    """
    ring = _room_ring(scene, room_id)
    if ring:
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        return max(xs) - min(xs), max(ys) - min(ys)
    floor = scene.get("floorplan") or {}
    try:
        width = float(floor.get("width_cm") or 0) or _DEFAULT_ROOM_SIDE_CM
        depth = float(floor.get("depth_cm") or 0) or _DEFAULT_ROOM_SIDE_CM
    except (TypeError, ValueError):
        width, depth = _DEFAULT_ROOM_SIDE_CM, _DEFAULT_ROOM_SIDE_CM
    return width, depth


def _room_ring(scene: dict, room_id: str) -> list[tuple[float, float]]:
    """此房間輪廓的 (x, z) 點列；沒有標 room_id 的 region（DXF 直讀）不採用。"""
    if not room_id:
        return []
    for region in (scene.get("floorplan") or {}).get("room_regions") or []:
        if not isinstance(region, dict) or str(region.get("room_id") or "") != room_id:
            continue
        try:
            ring = [
                (float(point[0]), float(point[1]))
                for point in region.get("exterior") or []
                if len(point) >= 2
            ]
        except (TypeError, ValueError):
            return []
        return ring if len(ring) >= 3 else []
    return []


def _placed_rows(objects: list[dict]) -> list[dict]:
    """取 genpic 畫面描述需要的欄位：名稱、類型、材質與型錄外觀描述
    （數值與座標不進提示詞）。``description`` 是 Kai 型錄的 VLM 描述，
    由 genpic_info 裁成純外觀敘述後入提示詞。"""
    return [
        {
            "id": obj.get("id") or obj.get("furniture_id") or "",
            "name": obj.get("name_zh_raw")
            or obj.get("name_en")
            or obj.get("normalized_type")
            or "家具",
            "type": obj.get("normalized_type") or "",
            "material": str(obj.get("material") or "").strip(),
            "description": str(obj.get("description") or "").strip(),
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


def _official_style_and_card(
    card_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """用 card_id 回查官方色卡與所屬風格（taiwan_style_cards.json）。

    scene_json.style_card.palette_hex 會被前端風格包（scene_style_packs.js）
    蓋成 3D 場景四色（牆/家具主色/地板/點綴），不是生圖用的 60/30/10 色卡；
    查不到官方定義（自訂卡或檔案異常）才沿用 scene 內既有值。
    """
    if not card_id:
        return None
    try:
        groups = load_taiwan_style_cards()
    except (OSError, ValueError):
        return None
    for group in groups:
        for card in group.get("cards") or []:
            if str(card.get("card_id")) == card_id:
                return group, card
    return None


def _requirement_doc(scene: dict, *, style_card_id: str | None = None) -> RequirementDoc:
    """組出生圖需求文件：風格、地板/牆面材質、家電 context、色卡、補充需求。

    ``style_card_id`` 供第 7 步三色卡比較逐張覆寫：不指定時用場景目前選定的色卡
    （第 6 步寫入的 ``scene.style_card``）；指定時整張卡（名稱與 60/30/10 用色）
    都改成那一張，否則三張生圖的提示詞會共用同一個色卡名稱，只有色碼不同。
    """
    requirement = scene.get("requirement") or {}
    style = str(
        requirement.get("style") or (scene.get("style") or {}).get("style_id") or ""
    ).strip()
    style_zh = str((scene.get("style") or {}).get("style_name_zh") or "").strip()

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
    card_id = str(
        style_card_id
        or card.get("card_id")
        or (scene.get("design_choices") or {}).get("style_card_id")
        or ""
    ).strip()
    if style_card_id and str(style_card_id).strip() != str(card.get("card_id") or "").strip():
        # 換卡時不可沿用場景那張卡的名稱與 palette_hex；查得到官方定義才有得填，
        # 查不到（自訂卡）就整張留空，由下面的 official 合併決定最終內容。
        card = {}
    official = _official_style_and_card(card_id)
    if official:
        group, official_card = official
        card = {**card, **official_card}
        style_zh = str(group.get("style_name_zh") or style_zh).strip()
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
    # 風格標籤（2026-08-05 定案）：六風格中文名＋色卡名，如「日式 茶室禪意」；
    # genpic 模板結尾會補「風」，故中文名去尾字「風」避免「北歐風…風」。
    # 查無中文名退回 style_id；無色卡名則只留風格名。
    family = style_zh.removesuffix("風") or style
    card_name = str(card.get("name_zh") or "").strip()
    style_label = f"{family} {card_name}".strip() if card_name else family
    return RequirementDoc(
        styles=[style_label] if style_label else [],
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


def _palette_gateway() -> OpenRouterGateway:
    """代表房色卡比較用 Nano Banana Pro;env 可覆蓋,fallback 回一般 nano banana。"""
    model = os.getenv("ROOMPILOT_GENPIC_PALETTE_MODEL", "").strip() or DEFAULT_PALETTE_IMAGE_MODEL
    fallback = (
        os.getenv("ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL", "").strip()
        or DEFAULT_IMAGE_MODEL
    )
    return OpenRouterGateway(image_model=model, image_fallback_model=fallback)


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
        # 房型是浴室／廚房／陽台專屬提示詞的權威訊號（genpic_info.room_kind）。
        room_type=str(room.get("room_type") or ""),
    )


def _is_living_room(room: dict) -> bool:
    """客廳判定：room_type 權威、中文房名「客廳」後援（對齊 agent 的 _is_living_room）。
    客廳才額外出一張夜間燈光圖（設計手冊日光＋夜間並列）。"""
    return (
        str(room.get("room_type") or "") == "living_room"
        or "客廳" in str(room.get("room_label") or "")
    )


# ------------------------------------------------------------------- 對外流程


def generate_room_images(
    scene: dict, rooms: list[dict], *, gateway: Any | None = None
) -> dict:
    """逐房視角送 Gen_Pic Agent（OpenRouter nano banana）生圖。

    ``rooms`` 每項：``{room_id, room_label, reference_png_data_url, note?,
    night_only?}``。``night_only`` 為真時只生夜間燈光圖（日光初稿已存在），
    結果只帶 ``night_*`` 欄位、不回房間狀態；用於代表房沿用色卡圖當日光初稿、
    以及夜景單獨失敗後的補生。
    回傳 ``{"results": [...], "rooms": [{room_id, room_label, lock_manifest}...]}``；
    ``rooms`` 供整批一次改圖時鎖定「只改指定內容、其餘不動」。單一房間失敗
    （主模型與 fallback 皆失敗）只標記該房 failed，其餘房間照常回傳。
    """
    gateway = gateway or OpenRouterGateway()
    if not getattr(gateway, "available", False):
        raise AiRenderNotConfigured("openrouter_api_key_not_configured")

    requirements = _requirement_doc(scene)
    palette = _palette_dict(requirements)
    # 先一次驗完所有房間的參考截圖：與其讓某一房靜默降級成純文字生圖，不如整批
    # 拒絕、由路由回 422。（生圖本身失敗仍照原政策只標記該房，見下方 GenPicFailure。）
    references = [_reference_b64(room) for room in rooms]

    def _render_one(item: tuple[dict, str]) -> tuple[dict, dict | None]:
        # 每執行緒各自 agent/images/scene_doc,避免共用可變狀態;gateway 無狀態可共用。
        room, reference_b64 = item
        agent = GenPicAgent(gateway)
        images = ImageLibraryDoc()
        room_id = str(room.get("room_id") or "").strip()
        rows = _placed_rows(_placed_objects(scene, room_id))
        scene_doc = SceneDoc(rooms={room_id: {"placed": rows, "failed": []}})
        layout_room = _layout_room(room, room_id, *_room_dims(scene, room_id))
        viewpoint = _viewpoint(room, reference_b64, requirements)

        def _render(stage: str, lighting: str = "day"):
            return agent.render_room(
                requirements,
                scene_doc,
                layout_room,
                images,
                stage=stage,
                palette=palette,
                viewpoint=viewpoint,
                lighting=lighting,
            )

        # night_only：日光初稿已存在（第 7 步代表房沿用色卡圖，或先前已生過），
        # 只補夜間那張，省一次生成。沒有伺服器端日光圖就沒有 lock_manifest，
        # 故不回房間狀態——這條路徑不會讓該房變成可改圖。
        if room.get("night_only"):
            day_b64 = _strip_data_url(room.get("day_image_data_url"))
            if day_b64:
                # 這條路徑的日光圖只在前端（代表房沿用的色卡圖）：先塞進圖庫，
                # GenPicAgent 才抓得到它來重打光，而不是拿白模截圖畫夜景。
                images.records.append(
                    ImageRecord(
                        image_id=f"img_{room_id}_day",
                        room_id=room_id,
                        stage="full_render",
                        image_ref=day_b64,
                        seq=1,
                    )
                )
            try:
                night = _render("full_render_night", "night")
            except GenPicFailure as exc:
                return (
                    {
                        "room_id": room_id,
                        "room_label": layout_room.name,
                        "status": "failed",
                        "night_only": True,
                        "notices": exc.notices,
                    },
                    None,
                )
            return (
                {
                    "room_id": room_id,
                    "room_label": layout_room.name,
                    "status": "completed",
                    "night_only": True,
                    "night_image_id": night.image_id,
                    "night_image_data_url": _as_data_url(night.image_ref),
                    "night_model": night.model,
                    "notices": night.notices,
                },
                None,
            )

        try:
            record = _render("full_render")
            manifest = agent.lock_manifest_for(
                requirements,
                scene_doc,
                layout_room,
                palette=palette,
                viewpoint=viewpoint,
            )
        except GenPicFailure as exc:
            return (
                {
                    "room_id": room_id,
                    "room_label": layout_room.name,
                    "status": "failed",
                    "notices": exc.notices,
                },
                None,
            )
        result = {
            "room_id": room_id,
            "room_label": layout_room.name,
            "status": "completed",
            "image_id": record.image_id,
            "image_data_url": _as_data_url(record.image_ref),
            "model": record.model,
            "notices": record.notices,
        }
        if _is_living_room(room):
            # 客廳額外出一張夜間燈光圖（同鎖定視角/同色卡 img2img，只換光影提示）。
            # 夜間失敗不影響日光初稿，只附提示原因，不擋整批；之後可用 night_only 補。
            try:
                night = _render("full_render_night", "night")
                result["night_image_id"] = night.image_id
                result["night_image_data_url"] = _as_data_url(night.image_ref)
                result["night_model"] = night.model
            except GenPicFailure as exc:
                result["night_notices"] = exc.notices
        return (
            result,
            {
                "room_id": room_id,
                "room_label": layout_room.name,
                "lock_manifest": manifest.to_dict(),
            },
        )

    # 全房生圖:所有房間視角**一次併發**送出(gateway 為 stdlib urllib 阻塞式,用執行緒
    # 池併發);順序對齊輸入 rooms。單一房間失敗只標記該房,其餘照常回傳。
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(rooms))) as pool:
        outcomes = list(pool.map(_render_one, zip(rooms, references)))
    results = [result for result, _ in outcomes]
    room_state = [state for _, state in outcomes if state is not None]
    return {"results": results, "rooms": room_state}


def generate_palette_images(
    scene: dict, room: dict, style_card_ids: list[str], *, gateway: Any | None = None
) -> dict:
    """第 7 步代表房「色卡比較」:同一代表房 × 多張色卡,**一次併發**送 Gen_Pic Agent
    (Nano Banana Pro)生圖。回傳 ``{"results": [{style_card_id, status, image_data_url,
    model, notices}...], "room_id": ...}``,順序對齊 ``style_card_ids``。單張色卡失敗
    只標記該張 failed,其餘照常回傳。gateway 為 stdlib urllib 阻塞式,故用執行緒池併發。
    """
    gateway = gateway or _palette_gateway()
    if not getattr(gateway, "available", False):
        raise AiRenderNotConfigured("openrouter_api_key_not_configured")

    base_requirements = _requirement_doc(scene)
    base_palette = _palette_dict(base_requirements)
    room_id = str(room.get("room_id") or "").strip()
    reference_b64 = _reference_b64(room)
    rows = _placed_rows(_placed_objects(scene, room_id))
    layout_room = _layout_room(room, room_id, *_room_dims(scene, room_id))
    viewpoint = _viewpoint(room, reference_b64, base_requirements)
    ids = [str(card_id).strip() for card_id in style_card_ids if str(card_id).strip()]

    def _render_one(card_id: str) -> dict:
        # 每執行緒各自 agent/images/scene_doc,避免共用可變狀態;gateway 無狀態可共用。
        agent = GenPicAgent(gateway)
        images = ImageLibraryDoc()
        scene_doc = SceneDoc(rooms={room_id: {"placed": rows, "failed": []}})
        # 三張比較圖的差異全在這一行:色卡名稱與 60/30/10 用色都換成這一張的,
        # 否則三張提示詞會共用場景現有色卡的名稱,只有色碼不同(自相矛盾)。
        requirements = _requirement_doc(scene, style_card_id=card_id)
        palette = _palette_dict(requirements) or base_palette
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
        except GenPicFailure as exc:
            return {
                "style_card_id": card_id,
                "status": "failed",
                "notices": exc.notices,
            }
        return {
            "style_card_id": card_id,
            "status": "completed",
            "image_id": record.image_id,
            "image_data_url": _as_data_url(record.image_ref),
            "model": record.model,
            "notices": record.notices,
        }

    # 一次送三個請求出去。
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(ids))) as pool:
        results = list(pool.map(_render_one, ids))
    return {"results": results, "room_id": room_id}


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
