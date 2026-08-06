"""第 8 步收尾設計手冊 adapter：把專案 scene_json 與 AI 生圖成果對應成
Report Agent 文件，輸出八章設計手冊 PDF（正式流程的「成果包」文件）。

邊界（見 AGENTS.md / docs/owners/BELLA.md）：

- 本模組是 Bella（`backend/server/`）對 Yen（`backend/agent/` Report Agent）的
  adapter：只做「scene_json＋生圖成果 → agent 文件」的組裝與保存編排，八章
  組稿、LLM 前言/設計理念與 PDF 排版都在 ReportSkill / RenderPdfTool，不在此
  重做。
- 需求/材質/家電/色卡資訊沿用 `ai_render_service._requirement_doc`，讓手冊描述
  與第 8 步生圖採同一份組裝（色卡以 card_id 回查官方 taiwan_style_cards.json）。
- 未設定 `OPENROUTER_API_KEY` 時照樣輸出：LLM 只潤飾前言與設計理念，離線走
  ReportSkill 的 deterministic 底稿，不阻擋交付。
- 家具合法性由 `backend/engine/` 於第 6 步即時驗證；手冊驗證章如實引用此事實，
  不另行造假驗證輪次。未標價品項不猜價（工程費率章沿用工程文件 MVP 原則）。

主要進入點：``create_design_manual``。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..agent.documents import (
    DesignManualDoc,
    DocKey,
    DocStore,
    ImageLibraryDoc,
    ImageRecord,
    LayoutDoc,
    LayoutRoom,
    SceneDoc,
    ValidationReportDoc,
)
from ..agent.llm import OpenRouterGateway
from ..agent.skills.delivery import delivery_engine_status
from ..agent.subagents import ReportAgent
from ..agent.tools.base import ToolError
from .ai_render_service import (
    _placed_objects,
    _requirement_doc,
    _room_dims,
    _strip_data_url,
)

__all__ = [
    "DeliveryNotConfigured",
    "DesignManualError",
    "create_delivery_proposal",
    "create_design_manual",
    "delivery_proposal_status",
]

_ENGINE_VALIDATION_SUMMARY = (
    "家具位置、碰撞、淨空與邊界合法性由幾何引擎（backend/engine）於第 6 步"
    "配置與編輯時即時驗證；進入第 7 步鎖定方案時沒有未解決的阻擋問題。"
)


class DesignManualError(RuntimeError):
    """成果報告（設計手冊／交付提案）輸出失敗；訊息可直接呈現給使用者。"""


class DeliveryNotConfigured(RuntimeError):
    """交付提案排版引擎（playwright Chromium）未安裝；呼叫端應回 503，不得假成功。"""


def delivery_proposal_status() -> dict:
    """交付提案排版引擎是否可用與原因（供前端預先提示）。"""
    available, reason = delivery_engine_status()
    return {"available": available, "reason": reason}


def _manual_rows(objects: list[dict]) -> list[dict]:
    """取設計手冊需要的家具欄位：名稱、類型、尺寸、風格、參考價與選件理由。

    欄位名對齊 ReportSkill 讀取的 placed row 鍵（name/type/width/depth/style/
    price/reason）；價格優先取台幣欄位，取不到就不列（手冊不猜價）。
    """
    rows: list[dict] = []
    for obj in objects:
        size = obj.get("size_cm") or {}
        price: float | None = None
        for key in ("price_twd", "price_ntd", "price"):
            try:
                value = float(obj.get(key))
            except (TypeError, ValueError):
                continue
            if value > 0:
                price = value
                break
        rows.append(
            {
                "id": obj.get("instance_id") or obj.get("furniture_id") or "",
                "name": obj.get("name_zh_raw")
                or obj.get("name_en")
                or obj.get("normalized_type")
                or "家具",
                "type": obj.get("normalized_type") or "",
                "width": float(size.get("width") or 0),
                "depth": float(size.get("depth") or 0),
                "style": str(obj.get("primary_style") or "").strip(),
                "material": str(obj.get("material") or "").strip(),
                "price": price,
                "reason": str(obj.get("selection_reason") or "").strip(),
            }
        )
    return rows


def _layout_and_scene(
    scene: dict, rooms: list[dict]
) -> tuple[LayoutDoc, SceneDoc]:
    width_cm, depth_cm = _room_dims(scene)
    layout_rooms: list[LayoutRoom] = []
    scene_rooms: dict[str, dict] = {}
    for room in rooms:
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue

        def _dim(key: str, fallback: float) -> float:
            try:
                value = float(room.get(key) or 0)
            except (TypeError, ValueError):
                value = 0.0
            return value if value > 0 else fallback

        layout_rooms.append(
            LayoutRoom(
                room_id=room_id,
                name=str(room.get("room_label") or room_id),
                width_cm=_dim("width_cm", width_cm),
                depth_cm=_dim("depth_cm", depth_cm),
            )
        )
        scene_rooms[room_id] = {
            "placed": _manual_rows(_placed_objects(scene, room_id)),
            "failed": [],
        }
    layout = LayoutDoc(rooms=layout_rooms, source="scene_json")
    scene_doc = SceneDoc(variant="A", rooms=scene_rooms, notes="採用第 7 步鎖定方案")
    return layout, scene_doc


def _image_library(rooms: list[dict]) -> ImageLibraryDoc:
    """把前端持有的逐房生圖（data URL）建成圖庫；改圖後前端已就地更新為最新圖。"""
    images = ImageLibraryDoc()
    for room in rooms:
        room_id = str(room.get("room_id") or "").strip()
        encoded = _strip_data_url(room.get("image_data_url"))
        if not room_id or not encoded:
            continue
        images.records.append(
            ImageRecord(
                image_id=f"img_{room_id}_final",
                room_id=room_id,
                stage="full_render",
                model=str(room.get("model") or ""),
                image_ref=encoded,
                seq=images.next_seq(),
            )
        )
    return images


def _assemble_store(
    scene: dict, rooms: list[dict], design_revision: Any
) -> tuple[DocStore, ImageLibraryDoc]:
    """把 scene_json＋逐房生圖組成 Report Agent 的 DocStore（兩種報告共用）。"""
    requirements = _requirement_doc(scene)
    layout, scene_doc = _layout_and_scene(scene, rooms)
    if not layout.rooms:
        raise DesignManualError("缺少房間資料，無法組成果報告。")

    store = DocStore()
    store.set(DocKey.REQUIREMENTS, requirements)
    store.set(DocKey.LAYOUT, layout)
    store.set(DocKey.variant(DocKey.SCENE, "chosen"), scene_doc)
    store.set(
        DocKey.variant(DocKey.VALIDATION, scene_doc.variant),
        ValidationReportDoc(
            variant=scene_doc.variant,
            round_index=1,
            summary=_ENGINE_VALIDATION_SUMMARY,
        ),
    )
    images = _image_library(rooms)
    store.set(DocKey.IMAGES, images)
    choices: dict[str, Any] = {
        "plan_variant": scene_doc.variant,
        "palette_id": (
            requirements.palette_options[0].palette_id
            if requirements.palette_options
            else None
        ),
    }
    if design_revision is not None:
        choices["design_revision"] = design_revision
    store.set(DocKey.USER_CHOICES, choices)
    return store, images


def _report_gateway(gateway: Any | None) -> Any | None:
    gateway = gateway if gateway is not None else OpenRouterGateway()
    return gateway if getattr(gateway, "available", False) else None


def create_design_manual(
    project_id: str,
    scene: dict,
    rooms: list[dict],
    manuals_dir: Path,
    *,
    design_revision: Any = None,
    gateway: Any | None = None,
) -> tuple[DesignManualDoc, dict]:
    """組 DocStore、呼叫 Report Agent 輸出設計手冊 PDF，回傳（手冊, 保存紀錄）。

    ``rooms`` 每項：``{room_id, room_label, width_cm?, depth_cm?, image_data_url?,
    model?}``。保存紀錄只含中繼資料（檔名、章節、時間），不含圖或 PDF 內容，
    可直接進 project workflow JSONB。
    """
    store, images = _assemble_store(scene, rooms, design_revision)
    filename = f"roompilot-manual-{project_id[:8]}-{uuid4().hex[:8]}.pdf"
    out_path = Path(manuals_dir) / filename
    try:
        manual = ReportAgent(_report_gateway(gateway)).build_manual(store, str(out_path))
    except ToolError as exc:
        raise DesignManualError(exc.reason) from exc
    record = {
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sections": [section.heading for section in manual.sections],
        "rendered_rooms": [row.room_id for row in images.records],
    }
    return manual, record


def create_delivery_proposal(
    project_id: str,
    project_name: str,
    scene: dict,
    rooms: list[dict],
    manuals_dir: Path,
    *,
    design_revision: Any = None,
    gateway: Any | None = None,
) -> tuple[dict, dict]:
    """輸出品牌版交付提案 PDF（roompilot-delivery-pdf 打包 skill 排版）。

    與 ``create_design_manual`` 吃同一份 payload 與 DocStore 組裝，供兩版報告
    比較。排版引擎（playwright Chromium）未安裝時丟 ``DeliveryNotConfigured``。
    """
    available, reason = delivery_engine_status()
    if not available:
        raise DeliveryNotConfigured(reason)
    store, images = _assemble_store(scene, rooms, design_revision)
    filename = f"roompilot-proposal-{project_id[:8]}-{uuid4().hex[:8]}.pdf"
    out_path = Path(manuals_dir) / filename
    try:
        result = ReportAgent(_report_gateway(gateway)).build_delivery(
            store,
            str(out_path),
            project_name=project_name,
            design_revision=design_revision,
        )
    except ToolError as exc:
        if "playwright" in exc.reason.lower() or "chromium" in exc.reason.lower():
            raise DeliveryNotConfigured(exc.reason) from exc
        raise DesignManualError(exc.reason) from exc
    record = {
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "warnings": list(result.get("warnings") or []),
        "rendered_rooms": [row.room_id for row in images.records],
    }
    return result, record
