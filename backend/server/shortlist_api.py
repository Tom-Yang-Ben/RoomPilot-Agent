"""第 6 步之前的家具候選集 API。

問卷送出時呼叫一次：把逐房需求轉成語意查詢，檢索出候選家具，寫進專案
workflow（``scene_json``）。之後選件與擺放 agent 只讀這份候選集，不再掃全庫。

需求指紋沒變就直接沿用既有候選集，使用者在第 5、6 步之間來回微調不會每次
重等檢索。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status

from ..paths import REPO_ROOT
from ..spatial_data.rag.preload import PRELOADER
from ..spatial_data.rag.shortlist import (
    DEFAULT_PER_FAMILY,
    SHORTLIST_SCHEMA_VERSION,
    FurnitureShortlistService,
    RoomNeed,
    ShortlistResult,
    clean_families,
    needs_fingerprint,
    shortlist_is_current,
)
from .auth.dependencies import project_editor, project_reader
from .project_store import MAX_WORKFLOW_BYTES, ProjectVersionConflict


WORKFLOW_KEY = "furniture_shortlist"
# 候選集寫進 workflow 前的體積上限。實測 5 房 264 筆約 92KB，而既有專案的
# workflow 已經可以到 1MB，所以留 25% 給候選集，超過就降低每族系筆數重算，
# 避免把整份 workflow 推過 MAX_WORKFLOW_BYTES 而讓使用者連問卷都存不了。
MAX_SHORTLIST_BYTES = MAX_WORKFLOW_BYTES // 4

# specialRequests 是 ["use:工作收納", "atmosphere:安靜包覆"] 這種帶前綴的字串，
# 前綴是 UI 分組用的，不該進語意查詢。
_REQUEST_PREFIXES = ("use:", "atmosphere:", "style:", "note:")


def _strip_prefix(value: str) -> str:
    text = str(value or "").strip()
    for prefix in _REQUEST_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _text_items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_strip_prefix(value)] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [_strip_prefix(item) for item in value if str(item or "").strip()]
    return []


def _polygon_bounds(polygon: Any) -> tuple[float, float]:
    """由房間多邊形算出外接矩形，作為家具尺寸上限。"""
    xs: list[float] = []
    ys: list[float] = []
    for point in polygon or []:
        if not isinstance(point, dict):
            continue
        try:
            xs.append(float(point.get("x", point.get("x_cm", 0))))
            ys.append(float(point.get("y", point.get("y_cm", 0))))
        except (TypeError, ValueError):
            continue
    if len(xs) < 3:
        return 0.0, 0.0
    return max(xs) - min(xs), max(ys) - min(ys)


def _style_lookup() -> dict[str, str]:
    """中文風格名 → style_id。

    問卷的 ``overallStyle`` 存的是「北歐風」這種顯示名稱，而型錄的
    ``style_codes`` 是 ``scandinavian``。對照表直接取自既有色卡資料，
    不另外硬編一份。
    """
    path = REPO_ROOT / "backend" / "catalog" / "data" / "taiwan_style_cards.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    lookup: dict[str, str] = {}
    for style in payload.get("styles") or []:
        style_id = str(style.get("style_id") or "").strip()
        name_zh = str(style.get("style_name_zh") or "").strip()
        if style_id and name_zh:
            lookup[name_zh] = style_id
            lookup[style_id] = style_id
    return lookup


def build_needs_from_workflow(workflow: dict[str, Any]) -> list[RoomNeed]:
    """把第 4 步的房間幾何與第 5 步的需求問卷合併成檢索輸入。"""
    rooms = ((workflow.get("space_confirmation") or {}).get("rooms")) or []
    model = (workflow.get("requirements") or {}).get("roomRequirementModel") or {}
    requirements = model.get("roomRequirements") or {}
    profile = model.get("globalProfile") or {}
    styles = _style_lookup()
    global_style = styles.get(str(profile.get("overallStyle") or "").strip())

    needs: list[RoomNeed] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("id") or room.get("room_id") or "").strip()
        if not room_id:
            continue
        requirement = requirements.get(room_id) or {}
        furniture = requirement.get("furniture") or {}
        width_cm, depth_cm = _polygon_bounds(room.get("polygon_cm"))

        raw_required = furniture.get("required") or []
        parts: list[str] = [
            str(requirement.get("roomLabel") or room.get("label") or ""),
            *_text_items(requirement.get("usage")),
            *_text_items(requirement.get("specialRequests")),
            str(furniture.get("preferenceText") or ""),
            *_text_items(furniture.get("preferenceTags")),
            # required 裡混進的問卷標籤（"use:保持通行"）不是族系，但去掉前綴
            # 後是有用的語意線索，留給向量排序用。
            *[
                _strip_prefix(item)
                for item in raw_required
                if ":" in str(item) or "：" in str(item)
            ],
        ]
        # required 有時混進問卷標籤（"use:保持通行"），clean_families 會濾掉；
        # 那些字串仍留在 query_text 裡當語意線索，只是不當成必要族系。
        required = clean_families(furniture.get("required") or [])
        needs.append(
            RoomNeed(
                room_id=room_id,
                room_type=str(
                    requirement.get("roomType") or room.get("type") or "living_room"
                ),
                width_cm=width_cm,
                depth_cm=depth_cm,
                # 去重：specialRequests 與 required 的標籤常常重複，重複詞會
                # 稀釋向量而不是強化它。
                query_text=" ".join(
                    dict.fromkeys(word for part in parts if part for word in part.split())
                ).strip(),
                required_families=required,
                style_id=global_style,
            )
        )
    return needs


def _questionnaire_version(workflow: dict[str, Any]) -> int:
    """問卷 schema 改版記號。前端還沒送版本欄位的舊 workflow 一律視為 1。"""
    requirements = workflow.get("requirements") or {}
    model = requirements.get("roomRequirementModel") or {}
    for candidate in (
        model.get("questionnaireVersion"),
        requirements.get("questionnaireVersion"),
        requirements.get("questionnaire_version"),
    ):
        try:
            value = int(candidate)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 1


def _fit_within_budget(
    service: FurnitureShortlistService,
    needs: list[RoomNeed],
    *,
    per_family: int,
    questionnaire_version: int | None = None,
) -> tuple[ShortlistResult, dict[str, Any]]:
    """在體積上限內產生候選集，必要時降低每族系筆數重算。

    房間數多的案子可能一次就撐爆 workflow。與其讓保存失敗，不如少留幾個
    候選——回傳的 meta 會註明實際使用的 per_family，讓前端能說明原因。
    """
    attempts: list[dict[str, Any]] = []
    current = per_family
    while True:
        result = service.build(
            needs,
            per_family=current,
            questionnaire_version=questionnaire_version,
        )
        payload = result.as_dict()
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        attempts.append({"per_family": current, "bytes": size})
        if size <= MAX_SHORTLIST_BYTES or current <= 3:
            return result, {
                "per_family": current,
                "bytes": size,
                "trimmed": current < per_family,
                "attempts": attempts,
            }
        current = max(3, current // 2)


def build_shortlist_router(
    *,
    project_store_getter: Callable[[], Any],
    project_dir: Path,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["furniture-shortlist"])
    service = FurnitureShortlistService(project_dir)

    @router.get("/rag/embedding-status")
    def embedding_status() -> dict[str, Any]:
        """語意檢索是否可用。前端據此決定要不要顯示『正在準備檢索』。"""
        return PRELOADER.status()

    @router.get("/projects/{project_id}/furniture-shortlist")
    def get_shortlist(
        project_id: str,
        _user: dict[str, Any] = Depends(project_reader),
    ) -> dict[str, Any]:
        project = _load_project(project_store_getter, project_id)
        stored = (project.get("workflow") or {}).get(WORKFLOW_KEY)
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "SHORTLIST_NOT_BUILT",
                    "message": "尚未建立家具候選集，請先送出需求問卷。",
                },
            )
        return {"shortlist": stored}

    @router.post(
        "/projects/{project_id}/furniture-shortlist",
        status_code=status.HTTP_201_CREATED,
    )
    def create_shortlist(
        project_id: str,
        payload: dict[str, Any] | None = None,
        _user: dict[str, Any] = Depends(project_editor),
    ) -> dict[str, Any]:
        body = payload or {}
        force = bool(body.get("force"))
        per_family = int(body.get("per_family") or DEFAULT_PER_FAMILY)
        per_family = max(3, min(per_family, 24))

        project = _load_project(project_store_getter, project_id)
        workflow = project.get("workflow") or {}
        needs = build_needs_from_workflow(workflow)
        if not needs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "ROOMS_NOT_CONFIRMED",
                    "message": "尚未確認任何空間，無法建立候選集。",
                },
            )

        questionnaire_version = _questionnaire_version(workflow)
        stored = workflow.get(WORKFLOW_KEY)
        if not force and shortlist_is_current(
            stored,
            needs,
            per_family=per_family,
            questionnaire_version=questionnaire_version,
        ):
            return {
                "reused": True,
                "shortlist": stored,
                "summary": _summary(stored),
            }

        result, meta = _fit_within_budget(
            service,
            needs,
            per_family=per_family,
            questionnaire_version=questionnaire_version,
        )
        document = result.as_dict()
        # 檢索要跑數百毫秒到數秒，而前端問卷送出的同時就在自動存檔——用一開始
        # 讀到的 revision 寫回，幾乎必然撞上使用者自己的存檔而 409（2026-08-03
        # Ben 實走：整輪候選集因此沒建立，選件靜默退回全型錄）。
        # 這裡只合併 furniture_shortlist 單一鍵、內容由需求指紋決定，衝突時
        # 取最新版本重試一次即可；仍衝突才是真的多人同時編輯。
        try:
            updated = project_store_getter().update_workflow(
                project_id,
                workflow={WORKFLOW_KEY: document},
                expected_revision=project.get("revision"),
            )
        except ProjectVersionConflict:
            latest = _load_project(project_store_getter, project_id)
            try:
                updated = project_store_getter().update_workflow(
                    project_id,
                    workflow={WORKFLOW_KEY: document},
                    expected_revision=latest.get("revision"),
                )
            except ProjectVersionConflict as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "PROJECT_REVISION_CONFLICT",
                        "message": "專案已在其他分頁更新，請重新載入後再送出。",
                        "project": exc.project,
                    },
                ) from exc

        return {
            "reused": False,
            "shortlist": document,
            "summary": _summary(document),
            "storage": meta,
            "revision": updated.get("revision"),
        }

    return router


def _load_project(project_store_getter: Callable[[], Any], project_id: str) -> dict:
    try:
        return project_store_getter().get_project(project_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROJECT_NOT_FOUND", "message": "找不到專案"},
        ) from exc


def _summary(document: dict[str, Any] | None) -> dict[str, Any]:
    """回給前端的輕量摘要；完整候選集已在 workflow 裡，不必重複傳。"""
    rooms = (document or {}).get("rooms") or []
    return {
        "schema_version": (document or {}).get("schema_version", SHORTLIST_SCHEMA_VERSION),
        "semantic": bool((document or {}).get("semantic")),
        "generated_at": (document or {}).get("generated_at"),
        "rooms": [
            {
                "room_id": room.get("room_id"),
                "room_type": room.get("room_type"),
                "item_count": len(room.get("items") or []),
                "missing_families": room.get("missing_families") or [],
            }
            for room in rooms
        ],
        "total_items": sum(len(room.get("items") or []) for room in rooms),
    }
