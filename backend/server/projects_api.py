"""專案 CRUD、平面圖與渲染路由群的 API（佇列 7 巨石拆分第四批）。

自 ``main.py`` 抽出的 router 工廠，仿照 ``build_scene_router`` 的掛載方式。
純搬家：路由路徑、payload 形狀與行為都不變。

被測試 ``monkeypatch.setattr(main, ...)`` 或 conftest 直接替換錨定的符號
（``PROJECT_STORE``、``user_store``、``_floorplan_ocr_provider``）留在 main 的
命名空間，這裡以工廠參數的 getter 延遲解析，補丁語意不變。auth 守衛
（``auth_dependencies.project_reader`` 等）是穩定的模組函式，照原樣掛。
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image

from ..floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)
from .auth import dependencies as auth_dependencies
from .project_store import ProjectVersionConflict, WorkflowTooLargeError
from .render_providers import (
    direct_image_provider_available,
    direct_image_provider_status,
    run_direct_render_jobs,
)
from .render_service import (
    RenderProviderRejected,
    RenderProviderUnavailable,
    render_provider_status,
    submit_render_jobs,
)
from .scene_service import parse_floorplan_with_engine


FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
MAX_RENDER_BYTES = 20 * 1024 * 1024
# 平面圖是 DXF 或掃描圖，正常在數 MB 以內。無界 read() 會把整份檔案讀進記憶體，
# QA 實測 60MB 照收；上限比照最終 PNG，超過就明確回 413 而不是慢慢吃光記憶體。
MAX_FLOORPLAN_BYTES = 20 * 1024 * 1024
MAX_PROJECT_NAME_CHARS = 120
MAX_PROJECT_NOTES_CHARS = 2000
WORKFLOW_STEPS = {
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
    "white_model_3d",
    "realistic_3d",
    "proposal_review",
    "ai_render",
}

# 二進位 DXF 的官方 sentinel（前 18 個位元組即可辨識）。
_BINARY_DXF_SENTINEL = b"AutoCAD Binary DXF"
# 文字 DXF 一定含有「群組碼 0 換行 SECTION」的段落開頭；testdata/dxf 全部 30 檔已驗證通過。
_TEXT_DXF_SECTION_RE = re.compile(r"^[ \t]*0[ \t]*\r?\n[ \t]*SECTION\b", re.MULTILINE)


async def _read_upload(file: UploadFile, limit_bytes: int, label: str) -> bytes:
    """多讀一個 byte 就知道有沒有超標，避免先把超大檔整份讀進記憶體。"""
    content = await file.read(limit_bytes + 1)
    if len(content) > limit_bytes:
        raise HTTPException(
            413,
            {
                "code": "upload_too_large",
                "message": f"{label}不可超過 {limit_bytes // (1024 * 1024)} MB。",
            },
        )
    return content


def _validate_floorplan_bytes(extension: str, content: bytes) -> str:
    if not content:
        raise HTTPException(
            422,
            {
                "code": "empty_floorplan",
                "message": "檔案沒有內容，請重新選擇平面圖。",
                "focus": "floorplan-file",
            },
        )
    if extension == ".dxf":
        if content.startswith(_BINARY_DXF_SENTINEL):
            raise HTTPException(
                415,
                {
                    "code": "binary_dxf_unsupported",
                    "message": "偵測到二進位 DXF；目前僅支援文字（ASCII）DXF，請在 CAD 以 ASCII DXF 另存後重新上傳。",
                    "focus": "floorplan-file",
                },
            )
        head = content[:65536].decode("utf-8", errors="replace")
        if not _TEXT_DXF_SECTION_RE.search(head):
            raise HTTPException(
                422,
                {
                    "code": "invalid_floorplan_dxf",
                    "message": "檔案副檔名是 .dxf，但內容不是可讀取的文字 DXF（開頭找不到 SECTION 結構）。",
                    "focus": "floorplan-file",
                },
            )
        return "application/dxf"
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            422,
            {
                "code": "invalid_floorplan_image",
                "message": "檔案副檔名正確，但內容不是可讀取的 PNG 或 JPG 圖片。",
                "focus": "floorplan-file",
            },
        ) from exc
    return "image/png" if extension == ".png" else "image/jpeg"


def _project_text(payload: dict, key: str, label: str, *, limit: int) -> str:
    """專案文字欄位的共同入口。

    舊版直接 ``str()`` 硬轉：送 dict 進來會把 Python repr 存成專案名稱，等於把
    伺服器內部資料結構回顯給使用者；長度也沒有上限。
    """
    raw = payload.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise HTTPException(
            422,
            {"code": f"invalid_project_{key}", "message": f"{label}必須是文字。"},
        )
    text = raw.strip()
    if len(text) > limit:
        raise HTTPException(
            422,
            {
                "code": f"project_{key}_too_long",
                "message": f"{label}不可超過 {limit} 個字。",
            },
        )
    return text


def _unresolved_recognition_review(workflow: dict) -> list[dict]:
    """宣告空間確認完成、卻仍有辨識複核房間未經人工確認的清單。

    對應 ``confirmation.py`` 的 ``targeted_room_review_required`` 閘門：正式
    前端不走 ``/api/floorplan/confirm``，所以在 workflow 宣告
    ``space_confirmation`` 完成時做等值檢查。房間 id 已不存在視為已處理——
    刪除、合併、切割都是人工介入。已完成的舊專案房間全數 confirmed，不受
    影響。
    """
    flow = workflow.get("_flow")
    completed = flow.get("completed") if isinstance(flow, dict) else None
    if not isinstance(completed, list) or "space_confirmation" not in completed:
        return []
    recognition = workflow.get("recognition")
    spatial = (
        recognition.get("spatial_report") if isinstance(recognition, dict) else None
    )
    items = spatial.get("review_items") if isinstance(spatial, dict) else None
    if not isinstance(items, list) or not items:
        return []
    space = workflow.get("space_confirmation")
    rooms = space.get("rooms") if isinstance(space, dict) else None
    rooms_by_id: dict[str, dict] = {}
    if isinstance(rooms, list):
        for room in rooms:
            if isinstance(room, dict) and room.get("id") is not None:
                rooms_by_id[str(room["id"])] = room
    unresolved: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        room_id = str(item.get("room_id"))
        room = rooms_by_id.get(room_id)
        if room is None or room.get("confirmed") is True or room_id in seen:
            continue
        seen.add(room_id)
        unresolved.append(
            {
                "room_id": room_id,
                "label": room.get("label"),
                "reason": item.get("reason"),
            }
        )
    return unresolved


def _public_render_record(record: dict) -> dict:
    payload = {key: value for key, value in record.items() if key != "path"}
    payload["download_url"] = (
        f"/api/projects/{record['project_id']}/renders/{record['render_id']}/png"
    )
    return payload


def _floorplan_is_confirmed(project: dict) -> bool:
    confirmation = project.get("workflow", {}).get("floorplan_confirmation", {})
    if confirmation.get("confirmed") is True:
        return True

    # Existing projects used the former privacy-shaped confirmation contract.
    privacy = project.get("workflow", {}).get("privacy", {})
    return (
        privacy.get("accepted") is True
        and (privacy.get("project_only") is True or privacy.get("projectOnly") is True)
        and (privacy.get("no_training") is True or privacy.get("noTraining") is True)
    )


def _floorplan_json_field(raw: str | None, field: str, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"invalid_{field}_json") from exc


def _layout_json_from_analysis(analysis: dict) -> dict:
    floorplan = analysis.get("floorplan")
    if isinstance(floorplan, dict):
        return floorplan
    return analysis


def build_projects_router(
    *,
    project_store_getter: Callable[[], Any],
    user_store_getter: Callable[[], Any],
    floorplan_ocr_provider_getter: Callable[[], Any],
    sample_floorplan_630: Path,
) -> APIRouter:
    """組出 /api/projects/*、/api/render-provider/status 與 /api/floorplan/* 的 router。

    getter 參數在 main.py 以 ``lambda: X`` 形式提供：呼叫時才解析 main 的
    模組全域，conftest 與 tests 對 main 的 monkeypatch 才會被路由看見。
    """
    router = APIRouter()

    def _stored_project(project_id: str) -> dict:
        try:
            return project_store_getter().get_project(project_id)
        except KeyError as exc:
            raise HTTPException(
                404,
                {
                    # 產品沒有專案列表頁，也沒有 list/DELETE API。舊訊息把使用者
                    # 指向一個不存在的地方，等於告訴他「去一個沒有的畫面」。
                    "code": "project_not_found",
                    "message": "找不到這個專案，可能已被刪除或連結有誤；請回首頁重新開始設計。",
                },
            ) from exc

    def _stored_floorplan(project_id: str) -> dict:
        _stored_project(project_id)
        try:
            upload = project_store_getter().get_upload(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                409,
                {
                    "code": "floorplan_missing",
                    "message": "尚未上傳平面圖，請先選擇 DXF、PNG、JPG 或 JPEG 檔案。",
                    "focus": "floorplan-file",
                },
            ) from exc
        if not upload["path"].is_file():
            raise HTTPException(
                410,
                {
                    "code": "floorplan_source_missing",
                    "message": "原始平面圖已遺失，請重新上傳。",
                    "focus": "floorplan-file",
                },
            )
        return upload

    @router.post("/api/projects", status_code=201)
    def create_project(
        payload: dict,
        user: dict = Depends(auth_dependencies.require_system_role("designer")),
    ) -> dict:
        name = _project_text(payload, "name", "專案名稱", limit=MAX_PROJECT_NAME_CHARS)
        if not name:
            raise HTTPException(
                422,
                {
                    "code": "project_name_required",
                    "message": "請輸入專案名稱。",
                    "focus": "project-name",
                },
            )
        notes = _project_text(payload, "notes", "備註", limit=MAX_PROJECT_NOTES_CHARS)
        project = project_store_getter().create_project(name=name, notes=notes)
        # 建立者立刻成為 owner，否則專案會是沒人能存取的孤兒。
        user_store_getter().set_project_owner(project["project_id"], user["user_id"])
        return {"project": project}

    @router.get("/api/projects/{project_id}")
    def get_project(
        project_id: str,
        response: Response,
        _user: dict = Depends(auth_dependencies.project_reader),
    ) -> dict:
        response.headers["Cache-Control"] = "no-store"
        return {"project": _stored_project(project_id)}

    @router.put("/api/projects/{project_id}/workflow")
    def save_project_workflow(
        project_id: str,
        payload: dict,
        _user: dict = Depends(auth_dependencies.project_editor),
    ) -> dict:
        _stored_project(project_id)
        current_step = str(payload.get("current_step") or "").strip() or None
        if current_step and current_step not in WORKFLOW_STEPS:
            raise HTTPException(422, "invalid_workflow_step")
        workflow = payload.get("workflow")
        if workflow is not None and not isinstance(workflow, dict):
            raise HTTPException(422, "workflow_must_be_an_object")
        unresolved_review = _unresolved_recognition_review(workflow or {})
        if unresolved_review:
            raise HTTPException(
                422,
                {
                    "code": "recognition_review_unresolved",
                    "message": (
                        "系統標記需人工複核的房間尚未逐一確認，"
                        "無法將空間確認標為完成；請回到第 4 步處理。"
                    ),
                    "rooms": unresolved_review,
                },
            )
        expected_revision = payload.get("expected_revision")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise HTTPException(422, "expected_revision_must_be_a_non_negative_integer")
        expected_updated_at = None
        if payload.get("replay_pending") is True:
            expected_updated_at = str(payload.get("base_updated_at") or "").strip()
            if not expected_updated_at:
                raise HTTPException(422, "pending_save_base_version_required")
        try:
            project = project_store_getter().update_workflow(
                project_id,
                current_step=current_step,
                workflow=workflow or {},
                expected_revision=expected_revision,
                expected_updated_at=expected_updated_at,
            )
        except ProjectVersionConflict as exc:
            if expected_revision is not None:
                raise HTTPException(
                    409,
                    {
                        "code": "project_revision_conflict",
                        "message": "專案已在另一個分頁更新，請載入最新版本後再儲存。",
                        "project": exc.project,
                    },
                ) from exc
            raise HTTPException(409, "project_version_conflict") from exc
        except WorkflowTooLargeError as exc:
            raise HTTPException(
                413,
                {
                    "code": "workflow_too_large",
                    "message": "專案草稿內容超過 2 MB，請移除大型暫存資料後再儲存。",
                },
            ) from exc
        return {"project": project}

    @router.post("/api/projects/{project_id}/floorplan", status_code=201)
    async def save_project_floorplan(
        project_id: str,
        file: UploadFile = File(...),
        expected_revision: int | None = Form(None),
        _user: dict = Depends(auth_dependencies.project_editor),
    ) -> dict:
        _stored_project(project_id)
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()
        if extension not in FLOORPLAN_EXTENSIONS:
            raise HTTPException(
                415,
                {
                    "code": "unsupported_floorplan_type",
                    "message": "只支援 DXF、PNG、JPG 或 JPEG 平面圖。",
                    "allowed_extensions": list(FLOORPLAN_EXTENSIONS),
                },
            )
        content = await _read_upload(file, MAX_FLOORPLAN_BYTES, "平面圖")
        mime_type = _validate_floorplan_bytes(extension, content)
        try:
            upload = project_store_getter().save_upload(
                project_id,
                filename=filename,
                extension=extension,
                mime_type=mime_type,
                content=content,
                expected_revision=expected_revision,
            )
        except ProjectVersionConflict as exc:
            raise HTTPException(
                409,
                {
                    "code": "project_revision_conflict",
                    "message": "專案已在另一個分頁更新，請載入最新版本後再上傳。",
                    "project": exc.project,
                },
            ) from exc
        return {
            "project": project_store_getter().get_project(project_id),
            "upload": {
                "filename": upload["filename"],
                "extension": upload["extension"],
                "mime_type": upload["mime_type"],
                "source_url": f"/api/projects/{project_id}/floorplan/source",
            }
        }

    @router.get("/api/projects/{project_id}/floorplan/source")
    def get_project_floorplan_source(
        project_id: str,
        _user: dict = Depends(auth_dependencies.project_reader),
    ) -> FileResponse:
        upload = _stored_floorplan(project_id)
        return FileResponse(
            upload["path"],
            media_type=upload["mime_type"],
            filename=upload["filename"],
        )

    @router.post("/api/projects/{project_id}/renders", status_code=201)
    async def create_project_render(
        project_id: str,
        file: UploadFile = File(...),
        expected_revision: int = Form(...),
        white_model_version: int = Form(0),
        viewpoint_version: int = Form(0),
        style_version: int = Form(0),
        style_card_id: str = Form("unassigned"),
        provider: str = Form("browser_capture"),
        _user: dict = Depends(auth_dependencies.project_editor),
    ) -> dict:
        _stored_project(project_id)
        if expected_revision < 0:
            raise HTTPException(422, "expected_revision_must_be_a_non_negative_integer")
        if min(white_model_version, viewpoint_version, style_version) < 0:
            raise HTTPException(422, "render_versions_must_be_non_negative")
        if provider != "browser_capture":
            raise HTTPException(
                422,
                {"code": "unsupported_render_provider", "message": "目前只接受瀏覽器場景 PNG。"},
            )
        content = await file.read(MAX_RENDER_BYTES + 1)
        if len(content) > MAX_RENDER_BYTES:
            raise HTTPException(
                413,
                {"code": "render_too_large", "message": "最終 PNG 不可超過 20 MB。"},
            )
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                415,
                {"code": "invalid_render_png", "message": "最終輸出必須是 PNG。"},
            )
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise HTTPException(
                422,
                {"code": "invalid_render_png", "message": "PNG 檔案已損壞。"},
            ) from exc
        try:
            render, project = project_store_getter().save_render(
                project_id,
                expected_revision=expected_revision,
                content=content,
                white_model_version=white_model_version,
                viewpoint_version=viewpoint_version,
                style_version=style_version,
                style_card_id=style_card_id,
                provider=provider,
            )
        except ProjectVersionConflict as exc:
            raise HTTPException(
                409,
                {
                    "code": "project_revision_conflict",
                    "message": "專案已更新，請重新載入後再輸出 PNG。",
                    "project": exc.project,
                },
            ) from exc
        return {"project": project, "render": _public_render_record(render)}

    @router.get("/api/projects/{project_id}/renders")
    def list_project_renders(
        project_id: str,
        _user: dict = Depends(auth_dependencies.project_reader),
    ) -> dict:
        try:
            renders = project_store_getter().list_renders(project_id)
        except KeyError as exc:
            raise HTTPException(
                404, {"code": "project_not_found", "message": "找不到專案。"}
            ) from exc
        return {"renders": [_public_render_record(record) for record in renders]}

    @router.get("/api/projects/{project_id}/renders/{render_id}/png")
    def download_project_render(
        project_id: str,
        render_id: str,
        _user: dict = Depends(auth_dependencies.project_reader),
    ) -> FileResponse:
        try:
            render = project_store_getter().get_render(project_id, render_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                404, {"code": "render_not_found", "message": "找不到這張 PNG。"}
            ) from exc
        path = render["path"]
        if not path.is_file():
            raise HTTPException(
                410,
                {"code": "render_file_missing", "message": "PNG 紀錄存在，但檔案已遺失。"},
            )
        # 產出的 PNG 是不可變的：render_id 換了才會有新內容。沒有 Cache-Control 時
        # 瀏覽器每次都重抓 1.45MB，QA 實測 load 事件被拖到 24 秒。
        return FileResponse(
            path,
            media_type="image/png",
            filename=render["filename"],
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    @router.get("/api/render-provider/status")
    def get_render_provider_status() -> dict:
        # 內建生圖供應者（OpenRouter）啟用時如實回報；舊遠端 URL 設定時維持原契約。
        if direct_image_provider_available():
            return direct_image_provider_status()
        return render_provider_status()

    @router.post("/api/projects/{project_id}/render-jobs", status_code=202)
    async def create_project_render_jobs(
        project_id: str,
        payload: dict,
        _user: dict = Depends(auth_dependencies.project_editor),
    ) -> dict:
        _stored_project(project_id)
        if payload.get("project_id") != project_id:
            raise HTTPException(
                422,
                {"code": "render_project_mismatch", "message": "渲染資料與目前專案不一致。"},
            )
        try:
            if direct_image_provider_available():
                # 2026-07 盤點第 10 項修復：內建轉接層直接叫生圖 API、回圖入庫、
                # 回傳 completed＋圖片網址（前端首回即顯示，不需輪詢）。
                return await run_direct_render_jobs(
                    project_id, payload, project_store_getter()
                )
            return await submit_render_jobs(payload)
        except ValueError as exc:
            raise HTTPException(
                422,
                {"code": str(exc), "message": "渲染資料不完整，請回到第 9 步重新確認。"},
            ) from exc
        except RenderProviderUnavailable as exc:
            raise HTTPException(
                503,
                {"code": str(exc), "message": "遠端渲染服務尚未設定或目前無法連線。"},
            ) from exc
        except RenderProviderRejected as exc:
            raise HTTPException(
                502,
                {"code": str(exc), "message": "遠端渲染服務拒絕了這次任務。"},
            ) from exc

    @router.post("/api/projects/{project_id}/floorplan/analyze")
    def analyze_project_floorplan(
        project_id: str,
        _user: dict = Depends(auth_dependencies.project_editor),
    ) -> dict:
        project = _stored_project(project_id)
        upload = _stored_floorplan(project_id)
        if not _floorplan_is_confirmed(project):
            raise HTTPException(
                409,
                {
                    "code": "floorplan_confirmation_required",
                    "message": "請先確認圖檔內容正確，才能開始辨識。",
                    "focus": "project-floorplan-confirmation",
                },
            )

        content = upload["path"].read_bytes()
        if upload["extension"] == ".dxf":
            try:
                parsed, _ = parse_floorplan_with_engine(
                    content.decode("utf-8", errors="ignore")
                )
                if not parsed:
                    raise ValueError("DXF 中沒有可建立房間的牆體幾何")
            except Exception as exc:
                raise HTTPException(
                    422,
                    {
                        "code": "dxf_parse_failed",
                        "message": f"DXF 無法解析：{exc}",
                        "focus": "floorplan-file",
                    },
                ) from exc
            analysis = {
                "recognition_engine": "dxf",
                "source_type": "dxf",
                "floorplan": parsed,
            }
            geometry_engine = "dxf"
        else:
            try:
                analysis = analyze_floorplan_image(
                    content,
                    filename=upload["filename"],
                    ocr_provider=floorplan_ocr_provider_getter(),
                )
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    422,
                    {
                        "code": "cody_recognition_failed",
                        "message": f"Cody 無法辨識這張平面圖：{exc}",
                        "focus": "floorplan-file",
                    },
                ) from exc
            geometry_engine = "cody"

        project_store_getter().update_workflow(
            project_id,
            current_step="recognition",
            workflow={
                "recognition": analysis,
                "confirmed_floorplan": None,
                "calibration": None,
                "space_confirmation": None,
                "requirements": None,
                "layout_2d": None,
                "white_model_3d": None,
                "realistic_3d": None,
                "_flow": {
                    "currentStep": "recognition",
                    "completed": ["project", "upload", "recognition"],
                    "staleFrom": "calibration",
                    "data": {
                        "recognition": {"engine": geometry_engine},
                        "calibration": None,
                        "space_confirmation": None,
                        "requirements": None,
                        "layout_2d": None,
                        "white_model_3d": None,
                        "realistic_3d": None,
                    },
                },
            },
        )
        layout_json = _layout_json_from_analysis(analysis)
        return {
            "analysis": analysis,
            "layout_json": layout_json,
            "geometry_engine": geometry_engine,
        }

    @router.get("/api/floorplan/sample/630")
    def floorplan_sample_630() -> FileResponse:
        if not sample_floorplan_630.is_file():
            raise HTTPException(404, "sample_floorplan_not_found")
        return FileResponse(
            sample_floorplan_630,
            media_type="image/png",
            filename="builder_plan_630.png",
        )

    @router.post("/api/floorplan/analyze")
    async def floorplan_analyze(
        file: UploadFile = File(...),
        calibration_json: str | None = Form(None),
        ocr_json: str | None = Form(None),
        geometry_json: str | None = Form(None),
        observed_utilities_json: str | None = Form(None),
        brief_json: str | None = Form(None),
    ):
        """PNG/JPG → 尺度、幾何、房間與初步機電需求；不確定時不得進設計。"""
        extension = Path(file.filename or "").suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(415, "floorplan_image_required")
        data = await _read_upload(file, MAX_FLOORPLAN_BYTES, "平面圖")
        calibration = _floorplan_json_field(calibration_json, "calibration", None)
        observations = _floorplan_json_field(ocr_json, "ocr", [])
        geometry = _floorplan_json_field(geometry_json, "geometry", [])
        observed_utilities = _floorplan_json_field(observed_utilities_json, "observed_utilities", [])
        brief = _floorplan_json_field(brief_json, "brief", {})
        provider = floorplan_ocr_provider_getter()
        try:
            analysis = analyze_floorplan_image(
                data,
                filename=file.filename or "floorplan.png",
                calibration_hint=calibration,
                ocr_observations=observations,
                ocr_provider=provider,
                geometry_observations=geometry,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        analysis["observed_utilities"] = observed_utilities
        analysis["requirement_brief"] = brief
        layout_json = _layout_json_from_analysis(analysis)
        return {
            "analysis": analysis,
            "layout_json": layout_json,
            "requirements": infer_room_requirements(analysis, brief),
            "geometry_engine": "cody" if not geometry else "manual",
            "ocr_provider": "provided_or_reference_semantics",
        }

    @router.post("/api/floorplan/confirm")
    def floorplan_confirm(payload: dict):
        """套用使用者確認／修正並輸出可供既有 3D 與家具引擎使用的契約。"""
        analysis = payload.get("analysis") if isinstance(payload, dict) else None
        corrections = payload.get("corrections") if isinstance(payload, dict) else None
        if not isinstance(analysis, dict):
            raise HTTPException(422, "analysis_required")
        try:
            return confirm_floorplan_analysis(analysis, corrections)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return router
