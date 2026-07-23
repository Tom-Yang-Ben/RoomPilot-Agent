"""五階段專案 workflow API(/api/projects/**)。

上傳 → 辨識 → 校尺 → 空間確認 → 需求問卷 → 2D 配置 → 3D 白模 → 視角 →
色卡 → 提案 PNG;confirm 類端點會使下游結果失效(血統鏈),更新一律帶
expected_revision 防多分頁覆寫。
"""
from __future__ import annotations

import copy
import io
import math
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from ...floorplan.room_analysis import attach_room_regions, room_type_option
from ...upgrade3d.wall_openings import build_opening_wall_geometry
from ..config import FLOORPLAN_EXTENSIONS, MAX_FLOORPLAN_BYTES
from ..services import floorplan_recognition, requirements_service
from ..services.catalog_service import (
    _furniture_payload_cache,
    _merged_furniture_catalog_cached,
    _style_payloads,
)
from ..services.layout_service import build_layout_proposal, build_style_variant, layout_catalog_size_cm
from ..services.scene_service import _region_boundary_by_id, room_from_payload, validate_single_placement
from ..services.style_cards import load_taiwan_style_cards, style_card_render_intent
from ..storage.project_models import (
    ProjectCreateRequest,
    ProjectFloorplanCalibrationRequest,
    ProjectFloorplanCalibrationResponse,
    ProjectFloorplanAnalyzeRequest,
    ProjectFloorplanAnalyzeResponse,
    ProjectRequirementsAnalyzeRequest,
    ProjectRequirementsAnalyzeResponse,
    ProjectRequirementsConfirmationRequest,
    ProjectRequirementsConfirmationResponse,
    ProjectLayoutAnalyzeRequest,
    ProjectLayoutAnalyzeResponse,
    ProjectLayoutConfirmationRequest,
    ProjectLayoutConfirmationResponse,
    ProjectLayoutValidateRequest,
    ProjectLayoutValidateResponse,
    ProjectRenderListResponse,
    ProjectRenderResponse,
    ProjectStyleCardApplyRequest,
    ProjectStyleCardApplyResponse,
    ProjectViewpointConfirmationRequest,
    ProjectViewpointConfirmationResponse,
    ProjectWhiteModelConfirmationRequest,
    ProjectWhiteModelConfirmationResponse,
    ProjectResponse,
    ProjectSpaceConfirmationRequest,
    ProjectSpaceConfirmationResponse,
    ProjectUploadResponse,
    WorkflowUpdateRequest,
)
from ..storage.project_store import ProjectConflictError, ProjectStore, WorkflowTooLargeError

router = APIRouter()


def _project_store(request: Request) -> ProjectStore:
    store = getattr(request.app.state, "project_store", None)
    if not isinstance(store, ProjectStore):
        raise HTTPException(
            503,
            {
                "code": "project_store_unavailable",
                "message": "專案儲存服務尚未就緒，請稍後重試。",
            },
        )
    return store


def _stored_project(request: Request, project_id: str) -> dict:
    try:
        project = _project_store(request).get_project(project_id)
    except KeyError as exc:
        raise HTTPException(
            404,
            {
                "code": "project_not_found",
                "message": "找不到這個專案，請建立新專案或確認連結。",
            },
        ) from exc
    # 舊專案可能在真實窗洞功能加入前已保存。讀取時補算但不偷偷增加 revision；
    # 下一次正式確認空間時會把同一份 canonical geometry 寫回專案。
    confirmation = (
        project.get("workflow", {})
        .get("data", {})
        .get("space_confirmation")
        or {}
    )
    floorplan = confirmation.get("floorplan")
    if isinstance(floorplan, dict) and (
        floorplan.get("wall_polys")
        or floorplan.get("wall_segments")
        or floorplan.get("plan_segments")
    ):
        geometry = floorplan.get("opening_geometry") or {}
        geometry_is_current = (
            bool(floorplan.get("wall_solids"))
            and geometry.get("status") == "opening_aware"
            and geometry.get("window_count") == len(floorplan.get("windows") or [])
            and geometry.get("door_count") == len(floorplan.get("doors") or [])
        )
        if not geometry_is_current:
            floorplan.update(build_opening_wall_geometry(floorplan))
    return project


def _stored_floorplan(request: Request, project_id: str) -> dict:
    store = _project_store(request)
    _stored_project(request, project_id)
    try:
        upload = store.get_upload(project_id)
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


def _validate_project_floorplan(extension: str, content: bytes) -> str:
    if not content:
        raise HTTPException(
            422,
            {
                "code": "empty_floorplan",
                "message": "檔案沒有內容，請重新選擇平面圖。",
                "focus": "floorplan-file",
            },
        )
    if len(content) > MAX_FLOORPLAN_BYTES:
        raise HTTPException(
            413,
            {
                "code": "floorplan_too_large",
                "message": "平面圖檔案不可超過 20 MB。",
            },
        )
    if extension == ".dxf":
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


@router.post("/api/projects", status_code=201, response_model=ProjectResponse)
def create_project(payload: ProjectCreateRequest, request: Request) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            422,
            {
                "code": "project_name_required",
                "message": "請輸入專案名稱。",
                "focus": "project-name",
            },
        )
    return {
        "project": _project_store(request).create_project(
            name=name,
            notes=payload.notes.strip(),
        )
    }


@router.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, request: Request) -> dict:
    return {"project": _stored_project(request, project_id)}


@router.put("/api/projects/{project_id}/workflow", response_model=ProjectResponse)
def save_project_workflow(
    project_id: str,
    payload: WorkflowUpdateRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step=payload.current_step,
            workflow=payload.workflow,
        )
    except KeyError as exc:
        raise HTTPException(
            404,
            {
                "code": "project_not_found",
                "message": "找不到這個專案，請建立新專案或確認連結。",
            },
        ) from exc
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請載入最新版本後再儲存。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(
            413,
            {
                "code": "workflow_too_large",
                "message": "專案草稿內容過大，請移除大型暫存資料後重試。",
            },
        ) from exc
    return {"project": project}


@router.post(
    "/api/projects/{project_id}/floorplan",
    status_code=201,
    response_model=ProjectUploadResponse,
)
async def save_project_floorplan(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    expected_revision: int = Form(..., ge=0),
) -> dict:
    store = _project_store(request)
    _stored_project(request, project_id)
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
    content = await file.read(MAX_FLOORPLAN_BYTES + 1)
    mime_type = _validate_project_floorplan(extension, content)
    try:
        upload, project = store.save_upload(
            project_id,
            expected_revision=expected_revision,
            filename=filename,
            extension=extension,
            mime_type=mime_type,
            content=content,
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請載入最新版本後再上傳。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(
            413,
            {
                "code": "workflow_too_large",
                "message": "專案草稿內容過大，請移除大型暫存資料後重試。",
            },
        ) from exc
    return {
        "project": project,
        "upload": {
            "filename": upload["filename"],
            "extension": upload["extension"],
            "mime_type": upload["mime_type"],
            "source_url": f"/api/projects/{project_id}/floorplan/source",
        },
    }


@router.get("/api/projects/{project_id}/floorplan/source")
def get_project_floorplan_source(project_id: str, request: Request) -> FileResponse:
    upload = _stored_floorplan(request, project_id)
    return FileResponse(
        upload["path"],
        media_type=upload["mime_type"],
        filename=upload["filename"],
    )


def _recognition_workflow_record(analysis: dict, upload: dict) -> dict:
    """Keep canonical geometry in the project without persisting large previews/DXF text."""
    return {
        "filename": upload["filename"],
        "source": analysis.get("source"),
        "floorplan": analysis.get("floorplan") or {},
        "scale": analysis.get("scale"),
        "vlm": analysis.get("vlm"),
        "openrouter": analysis.get("openrouter"),
    }


@router.post(
    "/api/projects/{project_id}/floorplan/analyze",
    response_model=ProjectFloorplanAnalyzeResponse,
)
def analyze_project_floorplan(
    project_id: str,
    payload: ProjectFloorplanAnalyzeRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再辨識。",
                "project": current_project,
            },
        )
    upload = _stored_floorplan(request, project_id)
    analysis = floorplan_recognition.recognize_floorplan_bytes(
        upload["path"].read_bytes(),
        upload["filename"],
        scale_m=payload.scale_m,
        thickness=payload.thickness,
        height=payload.height,
        allow_openrouter=payload.allow_openrouter,
    )
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="recognition",
            workflow={
                "completed": ["project", "upload", "recognition"],
                "data": {
                    "recognition": _recognition_workflow_record(analysis, upload),
                    "calibration": None,
                    "space_confirmation": None,
                    "requirements": None,
                    "layout_2d": None,
                    "white_model_3d": None,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再辨識。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(
            413,
            {
                "code": "recognition_result_too_large",
                "message": "辨識結果過大，請簡化平面圖後重試。",
            },
        ) from exc
    return {"project": project, "analysis": analysis}


def _confirmed_client_segments(segments: list[dict]) -> list[dict]:
    return [
        {
            "start": {"x": round(segment["x1"] * 100, 2), "z": round(segment["z1"] * 100, 2)},
            "end": {"x": round(segment["x2"] * 100, 2), "z": round(segment["z2"] * 100, 2)},
        }
        for segment in segments
    ]


def _validate_confirmed_segments(raw_segments: list, bbox: dict, feature: str) -> list[dict]:
    labels = {"doors": "門", "windows": "窗"}
    label = labels[feature]
    try:
        minx, minz = float(bbox["minx"]), float(bbox["minz"])
        maxx, maxz = float(bbox["maxx"]), float(bbox["maxz"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "辨識結果缺少有效範圍，請重新辨識平面圖。") from exc

    segments = []
    tolerance = 0.5
    for index, item in enumerate(raw_segments, start=1):
        segment = item.model_dump()
        values = tuple(float(segment[key]) for key in ("x1", "z1", "x2", "z2"))
        if not all(math.isfinite(value) for value in values):
            raise HTTPException(422, f"第 {index} 個{label}線段含無效座標。")
        x1, z1, x2, z2 = values
        if math.hypot(x2 - x1, z2 - z1) < 0.05:
            raise HTTPException(422, f"第 {index} 個{label}線段太短，請在 2D 圖上重新標示。")
        if not all(
            (minx - tolerance <= x <= maxx + tolerance)
            and (minz - tolerance <= z <= maxz + tolerance)
            for x, z in ((x1, z1), (x2, z2))
        ):
            raise HTTPException(422, f"第 {index} 個{label}線段超出平面圖範圍。")
        segments.append({key: round(float(value), 3) for key, value in zip(("x1", "z1", "x2", "z2"), values)})
    return segments


def _validate_calibration_reference_cm(reference, bbox_m: dict) -> dict[str, float]:
    """驗證公分比例線；辨識 bbox 仍是 three.js 契約的公尺，在此邊界轉公分。"""
    try:
        minx_cm = float(bbox_m["minx"]) * 100
        minz_cm = float(bbox_m["minz"]) * 100
        maxx_cm = float(bbox_m["maxx"]) * 100
        maxz_cm = float(bbox_m["maxz"]) * 100
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "辨識結果缺少有效範圍，請重新辨識平面圖。") from exc

    values = reference.model_dump()
    coordinates = tuple(
        float(values[key]) for key in ("x1_cm", "z1_cm", "x2_cm", "z2_cm")
    )
    if not all(math.isfinite(value) for value in coordinates):
        raise HTTPException(422, "比例參考線含無效座標。")
    x1_cm, z1_cm, x2_cm, z2_cm = coordinates
    if math.hypot(x2_cm - x1_cm, z2_cm - z1_cm) < 5:
        raise HTTPException(422, "比例參考線短於 5 公分，請沿辨識後牆線重新拉線。")
    tolerance_cm = 50
    if not all(
        (minx_cm - tolerance_cm <= x_cm <= maxx_cm + tolerance_cm)
        and (minz_cm - tolerance_cm <= z_cm <= maxz_cm + tolerance_cm)
        for x_cm, z_cm in ((x1_cm, z1_cm), (x2_cm, z2_cm))
    ):
        raise HTTPException(422, "比例參考線超出平面圖範圍。")
    return {
        key: round(value, 2)
        for key, value in zip(
            ("x1_cm", "z1_cm", "x2_cm", "z2_cm"),
            coordinates,
        )
    }


def _recognized_wall_segments_cm(floorplan: dict) -> list[tuple[float, float, float, float]]:
    raw_segments = floorplan.get("wall_segments") or floorplan.get("plan_segments") or []
    parsed_segments: list[tuple[float, float, float, float]] = []
    for item in raw_segments:
        start = item.get("start") or item
        end = item.get("end") or item
        try:
            coordinates = (
                float(start.get("x", start.get("x1"))),
                float(start.get("z", start.get("z1"))),
                float(end.get("x", end.get("x2"))),
                float(end.get("z", end.get("z2"))),
            )
        except (AttributeError, TypeError, ValueError):
            continue
        parsed_segments.append(coordinates)

    segments: list[tuple[float, float, float, float]] = []
    if parsed_segments:
        bbox = floorplan.get("bbox") or {}
        try:
            plan_span_m = max(
                float(bbox["maxx"]) - float(bbox["minx"]),
                float(bbox["maxz"]) - float(bbox["minz"]),
            )
            xs = [value for segment in parsed_segments for value in (segment[0], segment[2])]
            zs = [value for segment in parsed_segments for value in (segment[1], segment[3])]
            segment_span = max(max(xs) - min(xs), max(zs) - min(zs))
            # dxf_parser 的歷史 start/end 線段是公分；新版與 flat 線段契約是公尺。
            source_is_cm = plan_span_m > 0 and segment_span > plan_span_m * 10
        except (KeyError, TypeError, ValueError):
            source_is_cm = False
        multiplier = 1 if source_is_cm else 100
        for coordinates in parsed_segments:
            converted = tuple(value * multiplier for value in coordinates)
            if math.hypot(converted[2] - converted[0], converted[3] - converted[1]) >= 1:
                segments.append(converted)

    for wall in floorplan.get("wall_polys") or []:
        for ring in [wall.get("exterior"), *(wall.get("holes") or [])]:
            if not isinstance(ring, list) or len(ring) < 2:
                continue
            closed_ring = ring if ring[0] == ring[-1] else [*ring, ring[0]]
            for start, end in zip(closed_ring, closed_ring[1:]):
                try:
                    coordinates = (
                        float(start[0]) * 100,
                        float(start[1]) * 100,
                        float(end[0]) * 100,
                        float(end[1]) * 100,
                    )
                except (IndexError, TypeError, ValueError):
                    continue
                if math.hypot(coordinates[2] - coordinates[0], coordinates[3] - coordinates[1]) >= 1:
                    segments.append(coordinates)
    return segments


def _validate_reference_follows_wall(reference_cm: dict, floorplan: dict) -> None:
    """比例線兩端須貼牆，且線方向須與端點附近的辨識牆線一致。"""
    walls = _recognized_wall_segments_cm(floorplan)
    if not walls:
        raise HTTPException(
            409,
            {
                "code": "recognized_wall_required",
                "message": "辨識結果沒有可吸附的牆線，請先重新辨識平面圖。",
            },
        )
    line_dx = reference_cm["x2_cm"] - reference_cm["x1_cm"]
    line_dz = reference_cm["z2_cm"] - reference_cm["z1_cm"]
    line_length = math.hypot(line_dx, line_dz)

    def point_matches_wall(x_cm: float, z_cm: float) -> bool:
        for x1_cm, z1_cm, x2_cm, z2_cm in walls:
            wall_dx = x2_cm - x1_cm
            wall_dz = z2_cm - z1_cm
            wall_length = math.hypot(wall_dx, wall_dz)
            ratio = max(
                0.0,
                min(
                    1.0,
                    ((x_cm - x1_cm) * wall_dx + (z_cm - z1_cm) * wall_dz)
                    / (wall_length * wall_length),
                ),
            )
            nearest_x = x1_cm + ratio * wall_dx
            nearest_z = z1_cm + ratio * wall_dz
            distance_cm = math.hypot(x_cm - nearest_x, z_cm - nearest_z)
            alignment = abs(line_dx * wall_dx + line_dz * wall_dz) / (
                line_length * wall_length
            )
            if distance_cm <= 15 and alignment >= 0.94:
                return True
        return False

    if not all(
        point_matches_wall(x_cm, z_cm)
        for x_cm, z_cm in (
            (reference_cm["x1_cm"], reference_cm["z1_cm"]),
            (reference_cm["x2_cm"], reference_cm["z2_cm"]),
        )
    ):
        raise HTTPException(
            422,
            {
                "code": "calibration_reference_not_on_wall",
                "message": "比例線必須沿辨識後牆線拉設，兩個端點都要吸附在牆上。",
            },
        )


def _scaled_semantic_suggestions(
    rooms: list[dict],
    scale_factor: float,
) -> list[dict]:
    """中心原點不變，將上一輪 VLM bbox 等比例映射到校正後的公尺座標。"""
    scaled = []
    for room in rooms:
        item = copy.deepcopy(room)
        bbox = item.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                item["bbox"] = [round(float(value) * scale_factor, 3) for value in bbox]
            except (TypeError, ValueError):
                item.pop("bbox", None)
        scaled.append(item)
    return scaled


@router.post(
    "/api/projects/{project_id}/floorplan/calibrate",
    response_model=ProjectFloorplanCalibrationResponse,
)
def calibrate_project_floorplan(
    project_id: str,
    payload: ProjectFloorplanCalibrationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再設定比例。",
                "project": current_project,
            },
        )
    workflow_data = current_project.get("workflow", {}).get("data", {})
    recognition = workflow_data.get("recognition")
    if not recognition:
        raise HTTPException(409, "尚無可校正的辨識結果，請先上傳並完成辨識。")
    old_floorplan = recognition.get("floorplan") or {}
    reference_cm = _validate_calibration_reference_cm(
        payload.reference_cm,
        old_floorplan.get("bbox") or {},
    )
    _validate_reference_follows_wall(reference_cm, old_floorplan)
    measured_length_cm = math.hypot(
        reference_cm["x2_cm"] - reference_cm["x1_cm"],
        reference_cm["z2_cm"] - reference_cm["z1_cm"],
    )
    actual_length_cm = float(payload.actual_length_cm)
    scale_factor = actual_length_cm / measured_length_cm
    if not 0.05 <= scale_factor <= 20:
        raise HTTPException(
            422,
            {
                "code": "calibration_scale_out_of_range",
                "message": "參考線與實際尺寸差距過大，請重新拉線並確認公分數。",
            },
        )
    try:
        previous_scale_cm = float(old_floorplan["scale_m"]) * 100
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "辨識結果缺少比例基準，請重新辨識平面圖。") from exc
    calibrated_scale_cm = previous_scale_cm * scale_factor
    if not 100 <= calibrated_scale_cm <= 50_000:
        raise HTTPException(422, "校正後的平面圖長邊必須介於 100 到 50,000 公分。")

    upload = _stored_floorplan(request, project_id)
    analysis = floorplan_recognition.recognize_floorplan_bytes(
        upload["path"].read_bytes(),
        upload["filename"],
        # dxf_parser 的輸入邊界仍為公尺；專案業務層以上皆使用公分。
        scale_m=calibrated_scale_cm / 100,
        thickness=float(old_floorplan.get("wall_thickness") or 0.18),
        height=float(old_floorplan.get("wall_height") or 2.7),
        allow_openrouter=False,
    )
    old_suggestions = old_floorplan.get("rooms") or []
    if old_suggestions:
        analysis["floorplan"]["rooms"] = _scaled_semantic_suggestions(
            old_suggestions,
            scale_factor,
        )
        attach_room_regions(analysis["floorplan"])
    analysis["vlm"] = recognition.get("vlm")
    previous_openrouter = recognition.get("openrouter")
    if previous_openrouter:
        analysis["openrouter"] = {
            **previous_openrouter,
            "reused_after_calibration": True,
        }
    calibration = {
        "status": "confirmed",
        "method": "reference_line",
        "reference_cm": reference_cm,
        "actual_length_cm": round(actual_length_cm, 2),
        "measured_length_before_cm": round(measured_length_cm, 2),
        "scale_factor": round(scale_factor, 6),
        "previous_scale_cm": round(previous_scale_cm, 2),
        "scale_cm": round(calibrated_scale_cm, 2),
    }
    stored_calibration = {
        **calibration,
        # ProjectStore 會遞迴合併既有專案；明確清空舊公尺欄位，避免其他消費者
        # 在同一筆校正紀錄讀到已過期的 scale_m / reference。
        "reference": None,
        "measured_length_before_m": None,
        "previous_scale_m": None,
        "scale_m": None,
    }
    completed = [
        step
        for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {
            "calibration",
            "space_confirmation",
            "requirements",
            "layout_2d",
            "white_model_3d",
            "viewpoint",
            "style_render",
            "realistic_3d",
        }
    ]
    completed.append("calibration")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="space_confirmation",
            workflow={
                "completed": completed,
                "data": {
                    "recognition": _recognition_workflow_record(analysis, upload),
                    "calibration": stored_calibration,
                    "space_confirmation": None,
                    "requirements": None,
                    "layout_2d": None,
                    "white_model_3d": None,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再設定比例。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "比例校正結果過大，請簡化平面圖後重試。") from exc
    return {"project": project, "analysis": analysis, "calibration": calibration}


def _build_space_confirmation(
    recognition: dict,
    payload: ProjectSpaceConfirmationRequest,
) -> dict:
    suggested_floorplan = recognition.get("floorplan") or {}
    suggested_rooms = suggested_floorplan.get("room_regions") or []
    room_by_id = {
        room.get("room_id"): room
        for room in suggested_rooms
        if room.get("room_id")
    }
    submitted_ids = [room.room_id for room in payload.rooms]
    if len(set(submitted_ids)) != len(submitted_ids):
        raise HTTPException(422, "同一個空間不可重複確認。")
    if set(submitted_ids) != set(room_by_id):
        raise HTTPException(422, "空間清單與最新辨識結果不一致，請重新載入後再確認。")

    confirmed_rooms = []
    for choice in payload.rooms:
        suggestion = room_by_id[choice.room_id]
        option = room_type_option(choice.room_type)
        confirmed = copy.deepcopy(suggestion)
        confirmed.update(
            {
                **option,
                "label": option["label_zh"],
                "label_source": "user_confirmation",
                "suggested_label": suggestion.get("label"),
                "suggested_label_zh": suggestion.get("label_zh"),
                "suggested_room_type": suggestion.get("value", suggestion.get("room_type")),
                "suggested_source": suggestion.get("label_source"),
                "confirmed": True,
                "user_changed": option["value"]
                != suggestion.get("value", suggestion.get("room_type")),
            }
        )
        # ``value`` 是選項表欄位；正式契約使用更明確的 room_type。
        confirmed["room_type"] = confirmed.pop("value")
        confirmed_rooms.append(confirmed)

    bbox = suggested_floorplan.get("bbox") or {}
    doors = _validate_confirmed_segments(payload.doors, bbox, "doors")
    windows = _validate_confirmed_segments(payload.windows, bbox, "windows")
    floorplan = copy.deepcopy(suggested_floorplan)
    floorplan["room_regions"] = confirmed_rooms
    floorplan["doors"] = doors
    floorplan["windows"] = windows
    floorplan["door_segments"] = _confirmed_client_segments(doors)
    floorplan["window_segments"] = _confirmed_client_segments(windows)
    floorplan.update(build_opening_wall_geometry(floorplan))
    stats = floorplan.setdefault("stats", {})
    stats.update({"rooms": len(confirmed_rooms), "doors": len(doors), "windows": len(windows)})
    return {
        "status": "confirmed",
        "confirmed_by": "user",
        "floorplan": floorplan,
        "openrouter": recognition.get("openrouter"),
    }


@router.post(
    "/api/projects/{project_id}/floorplan/confirm",
    response_model=ProjectSpaceConfirmationResponse,
)
def confirm_project_floorplan(
    project_id: str,
    payload: ProjectSpaceConfirmationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再確認空間。",
                "project": current_project,
            },
        )
    recognition = current_project.get("workflow", {}).get("data", {}).get("recognition")
    if not recognition:
        raise HTTPException(409, "尚無可確認的辨識結果，請先上傳並完成辨識。")
    calibration = current_project.get("workflow", {}).get("data", {}).get("calibration")
    if not calibration or calibration.get("status") != "confirmed":
        raise HTTPException(
            409,
            {
                "code": "calibration_required",
                "message": "請先在 2D 圖上拉參考線並確認實際尺寸。",
            },
        )
    confirmation = _build_space_confirmation(recognition, payload)
    completed = list(current_project.get("workflow", {}).get("completed") or [])
    completed = [
        step
        for step in completed
        if step not in {"requirements", "layout_2d", "white_model_3d", "viewpoint", "style_render", "realistic_3d"}
    ]
    if "space_confirmation" not in completed:
        completed.append("space_confirmation")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="requirements",
            workflow={
                "completed": completed,
                "data": {
                    "space_confirmation": confirmation,
                    "requirements": None,
                    "layout_2d": None,
                    "white_model_3d": None,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已在另一個分頁更新，請重新載入後再確認空間。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "確認結果過大，請簡化平面圖後重試。") from exc
    return {"project": project, "confirmation": confirmation}


def _canonical_project_requirements(
    payload: ProjectRequirementsAnalyzeRequest | ProjectRequirementsConfirmationRequest,
    current_project: dict,
) -> tuple[dict, set[str]]:
    workflow_data = current_project.get("workflow", {}).get("data", {})
    confirmation = workflow_data.get("space_confirmation") or {}
    if confirmation.get("status") != "confirmed":
        raise HTTPException(
            409,
            {
                "code": "space_confirmation_required",
                "message": "請先完成比例與空間確認，再填寫需求問卷。",
            },
        )

    confirmed_rooms = confirmation.get("floorplan", {}).get("room_regions") or []
    room_by_id = {
        str(room.get("room_id")): room
        for room in confirmed_rooms
        if room.get("room_id")
    }
    submitted_ids = [room.room_id for room in payload.room_requirements]
    if len(set(submitted_ids)) != len(submitted_ids):
        raise HTTPException(422, "同一個空間不可重複填寫需求。")
    if set(submitted_ids) != set(room_by_id):
        raise HTTPException(
            422,
            {
                "code": "requirements_room_mismatch",
                "message": "問卷空間與最新確認結果不一致，請重新載入。",
            },
        )
    for room in payload.room_requirements:
        confirmed_type = room_by_id[room.room_id].get("room_type")
        if room.room_type != confirmed_type:
            raise HTTPException(
                422,
                {
                    "code": "requirements_room_type_mismatch",
                    "message": f"空間 {room.room_id} 的房型已變更，請重新載入問卷。",
                },
            )

    style_ids = {style.get("style_id") for style in _style_payloads()}
    if payload.style_id not in style_ids:
        raise HTTPException(
            422,
            {
                "code": "unknown_style_id",
                "message": "風格選項不存在，請重新選擇。",
                "valid_style_ids": sorted(style_id for style_id in style_ids if style_id),
            },
        )

    excluded = {"expected_revision", "allow_openrouter", "suggestion"}
    requirements = requirements_service.normalize_requirement_answers(payload.model_dump(exclude=excluded))
    token_pattern = re.compile(r"^[a-z0-9_-]{1,80}$")
    for room in requirements["room_requirements"]:
        for key in ("uses", "special_materials"):
            values = []
            for value in room.get(key) or []:
                token = str(value).strip()
                if not token_pattern.fullmatch(token):
                    raise HTTPException(422, f"{key} 含無效選項。")
                if token not in values:
                    values.append(token)
            room[key] = values
        room["special_notes"] = str(room.get("special_notes") or "").strip()
        room["required_furniture_ids"] = list(dict.fromkeys(
            str(value).strip()
            for value in room.get("required_furniture_ids") or []
            if str(value).strip()
        ))
    requirements["special_notes"] = str(requirements.get("special_notes") or "").strip()

    catalog_by_id = {
        str(item.get("furniture_id")): item
        for item in _merged_furniture_catalog_cached()
        if item.get("furniture_id")
    }
    requested_ids = {
        furniture_id
        for room in requirements["room_requirements"]
        for furniture_id in room["required_furniture_ids"]
    }
    unknown_ids = sorted(requested_ids - set(catalog_by_id))
    if unknown_ids:
        raise HTTPException(
            422,
            {
                "code": "unknown_furniture_id",
                "message": "指定家具不在目前型錄中。",
                "furniture_ids": unknown_ids,
            },
        )
    unavailable_ids = sorted(
        furniture_id
        for furniture_id in requested_ids
        if not catalog_by_id[furniture_id].get("has_model")
    )
    if unavailable_ids:
        raise HTTPException(
            422,
            {
                "code": "furniture_model_unavailable",
                "message": "指定家具目前沒有可用 GLB，無法加入主流程。",
                "furniture_ids": unavailable_ids,
            },
        )
    return requirements, set(room_by_id)


@router.post(
    "/api/projects/{project_id}/requirements/analyze",
    response_model=ProjectRequirementsAnalyzeResponse,
)
def analyze_project_requirements(
    project_id: str,
    payload: ProjectRequirementsAnalyzeRequest,
    request: Request,
) -> dict:
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已更新，請重新載入後再整理需求。",
                "project": current_project,
            },
        )
    requirements, valid_room_ids = _canonical_project_requirements(payload, current_project)
    suggestion = requirements_service.analyze_special_requirements(
        requirements,
        valid_room_ids=valid_room_ids,
        allow_openrouter=payload.allow_openrouter,
    )
    return {"suggestion": suggestion}


@router.post(
    "/api/projects/{project_id}/requirements/confirm",
    response_model=ProjectRequirementsConfirmationResponse,
)
def confirm_project_requirements(
    project_id: str,
    payload: ProjectRequirementsConfirmationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已更新，請重新載入後再確認需求。",
                "project": current_project,
            },
        )
    requirements, valid_room_ids = _canonical_project_requirements(payload, current_project)
    suggestion = payload.suggestion.model_dump()
    for constraint in suggestion["constraints"]:
        if constraint.get("room_id") and constraint["room_id"] not in valid_room_ids:
            raise HTTPException(422, "特殊需求引用了不存在的空間。")
    local_constraints = requirements_service.build_local_constraints(requirements)
    combined_constraints = []
    seen = set()
    for constraint in [*local_constraints, *suggestion["constraints"]]:
        key = (
            constraint.get("type"),
            constraint.get("room_id"),
            constraint.get("description_zh"),
        )
        if key not in seen:
            seen.add(key)
            combined_constraints.append(constraint)
    requirements_record = {
        "status": "confirmed",
        "confirmed_by": "user",
        **requirements,
        "special_requirements": {
            **suggestion,
            "status": "confirmed",
            "confirmed_by": "user",
            "constraints": combined_constraints[:50],
        },
    }
    completed = [
        step
        for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {"requirements", "layout_2d", "white_model_3d", "viewpoint", "style_render", "realistic_3d"}
    ]
    completed.append("requirements")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="layout_2d",
            workflow={
                "completed": completed,
                "data": {
                    "requirements": requirements_record,
                    "layout_2d": None,
                    "white_model_3d": None,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已更新，請重新載入後再確認需求。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "需求內容過大，請縮短特殊需求後重試。") from exc
    return {"project": project, "requirements": requirements_record}


def _project_layout_context(current_project: dict) -> tuple[dict, dict, dict[str, dict]]:
    workflow_data = current_project.get("workflow", {}).get("data", {})
    requirements = workflow_data.get("requirements") or {}
    confirmation = workflow_data.get("space_confirmation") or {}
    floorplan = confirmation.get("floorplan") or {}
    if requirements.get("status") != "confirmed":
        raise HTTPException(
            409,
            {"code": "requirements_confirmation_required", "message": "請先完成需求問卷確認，再產生 2D 家具配置。"},
        )
    if confirmation.get("status") != "confirmed" or not floorplan.get("room_regions"):
        raise HTTPException(
            409,
            {"code": "space_confirmation_required", "message": "請先完成空間確認，再產生 2D 家具配置。"},
        )
    room_by_id = {
        str(room.get("room_id")): room
        for room in floorplan.get("room_regions") or []
        if room.get("room_id")
    }
    return requirements, floorplan, room_by_id


def _canonical_layout_objects(
    raw_objects: list,
    requirements: dict,
    room_by_id: dict[str, dict],
) -> list[dict]:
    catalog_by_id = {
        str(item.get("furniture_id")): item
        for item in _furniture_payload_cache()
        if item.get("furniture_id") and item.get("has_model") and item.get("model_url")
    }
    required_by_room = {
        str(room.get("room_id")): set(room.get("required_furniture_ids") or [])
        for room in requirements.get("room_requirements") or []
    }
    canonical: list[dict] = []
    instance_ids: set[str] = set()
    for model in raw_objects:
        item = model.model_dump() if hasattr(model, "model_dump") else dict(model)
        instance_id = str(item.get("instance_id") or "")
        if instance_id in instance_ids:
            raise HTTPException(422, {"code": "duplicate_layout_instance", "message": "配置中出現重複的家具實例。"})
        instance_ids.add(instance_id)
        room_id = str(item.get("placement_room_id") or "")
        if room_id not in room_by_id:
            raise HTTPException(422, {"code": "unknown_layout_room", "message": "家具引用了不存在的空間。"})
        furniture_id = str(item.get("furniture_id") or "")
        catalog_item = catalog_by_id.get(furniture_id)
        if catalog_item is None:
            raise HTTPException(
                422,
                {"code": "layout_furniture_unavailable", "message": "配置含未知或沒有 GLB 的家具。", "furniture_id": furniture_id},
            )
        size = layout_catalog_size_cm(catalog_item)
        item.update({
            "furniture_id": furniture_id,
            "name_zh_raw": catalog_item.get("name_zh_raw") or catalog_item.get("name_zh") or furniture_id,
            "normalized_type": catalog_item.get("normalized_type"),
            "model_url": catalog_item.get("model_url"),
            "primary_style": catalog_item.get("primary_style"),
            "size_cm": size,
            "placement_room_id": room_id,
            "user_required": furniture_id in required_by_room.get(room_id, set()),
            "placement_failed": False,
            "placement_reason": None,
        })
        rotation = float(item.get("rotation_y_deg") or 0) % 360
        item["rotation_y_deg"] = rotation
        if rotation % 180 == 90:
            footprint = {"width": size["depth"], "depth": size["width"]}
        else:
            footprint = {"width": size["width"], "depth": size["depth"]}
        item["footprint_cm"] = footprint
        canonical.append(item)

    for room_id, required_ids in required_by_room.items():
        present = {
            item["furniture_id"]
            for item in canonical
            if item["placement_room_id"] == room_id
        }
        missing = sorted(required_ids - present)
        if missing:
            raise HTTPException(
                422,
                {"code": "required_furniture_missing", "message": "不可移除問卷中指定的家具型號。", "furniture_ids": missing},
            )
    return canonical


def _validate_project_layout_objects(
    floorplan: dict,
    room_by_id: dict[str, dict],
    objects: list[dict],
) -> None:
    room = room_from_payload(floorplan)
    for item in objects:
        boundary = _region_boundary_by_id(floorplan, room, item["placement_room_id"])
        if boundary is None:
            raise HTTPException(422, {"code": "layout_room_boundary_missing", "message": "家具所在空間缺少可驗證的邊界。"})
        others = [other for other in objects if other["instance_id"] != item["instance_id"]]
        result = validate_single_placement(
            floorplan,
            item,
            others,
            place_boundary=boundary,
            keep_door_clear=True,
        )
        if not result["ok"]:
            raise HTTPException(
                422,
                {
                    "code": "invalid_layout_placement",
                    "message": f"「{item.get('name_zh_raw') or item['furniture_id']}」位置不合法：{result['reason']}",
                    "instance_id": item["instance_id"],
                    "reason": result["reason"],
                },
            )


@router.post(
    "/api/projects/{project_id}/layout-2d/analyze",
    response_model=ProjectLayoutAnalyzeResponse,
)
def analyze_project_layout(
    project_id: str,
    payload: ProjectLayoutAnalyzeRequest,
    request: Request,
) -> dict:
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再產生配置。", "project": current_project},
        )
    requirements, floorplan, _room_by_id = _project_layout_context(current_project)
    proposal = build_layout_proposal(
        requirements,
        floorplan,
        list(_furniture_payload_cache()),
        allow_openrouter=payload.allow_openrouter,
    )
    return {"proposal": proposal}


@router.post(
    "/api/projects/{project_id}/layout-2d/validate",
    response_model=ProjectLayoutValidateResponse,
)
def validate_project_layout(
    project_id: str,
    payload: ProjectLayoutValidateRequest,
    request: Request,
) -> dict:
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(409, {"code": "project_revision_conflict", "message": "專案已更新，請重新載入配置。"})
    requirements, floorplan, room_by_id = _project_layout_context(current_project)
    objects = _canonical_layout_objects([payload.item, *payload.others], requirements, room_by_id)
    item = objects[0]
    room = room_from_payload(floorplan)
    boundary = _region_boundary_by_id(floorplan, room, item["placement_room_id"])
    if boundary is None:
        return {"ok": False, "reason": "家具所在空間缺少可驗證的邊界"}
    return validate_single_placement(
        floorplan,
        item,
        objects[1:],
        place_boundary=boundary,
        keep_door_clear=True,
    )


@router.post(
    "/api/projects/{project_id}/layout-2d/confirm",
    response_model=ProjectLayoutConfirmationResponse,
)
def confirm_project_layout(
    project_id: str,
    payload: ProjectLayoutConfirmationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再確認配置。", "project": current_project},
        )
    requirements, floorplan, room_by_id = _project_layout_context(current_project)
    objects = _canonical_layout_objects(payload.scene_objects, requirements, room_by_id)
    _validate_project_layout_objects(floorplan, room_by_id, objects)
    for item in objects:
        item["position_locked"] = True
    raw_openrouter = payload.openrouter or {}
    openrouter = {
        "provider": "openrouter",
        "requested": bool(raw_openrouter.get("requested")),
        "sent": bool(raw_openrouter.get("sent")),
        "status": str(raw_openrouter.get("status") or "not_requested")[:64],
        "model": str(raw_openrouter.get("model") or "")[:200] or None,
    }
    layout_record = {
        "status": "confirmed",
        "confirmed_by": "user",
        "layout_revision": payload.expected_revision + 1,
        "source": payload.proposal_source,
        "proposal_count": 1,
        "units": "cm",
        "scene_objects": objects,
        "openrouter": openrouter,
    }
    completed = [
        step
        for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {"layout_2d", "white_model_3d", "viewpoint", "style_render", "realistic_3d"}
    ]
    if "requirements" not in completed:
        completed.append("requirements")
    completed.append("layout_2d")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="white_model_3d",
            workflow={
                "completed": completed,
                "data": {
                    "layout_2d": layout_record,
                    "white_model_3d": None,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再確認配置。", "project": exc.project},
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "家具配置內容過大，請減少家具後重試。") from exc
    return {"project": project, "layout": layout_record}


@router.post(
    "/api/projects/{project_id}/white-model-3d/confirm",
    response_model=ProjectWhiteModelConfirmationResponse,
)
def confirm_project_white_model(
    project_id: str,
    payload: ProjectWhiteModelConfirmationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已更新，請重新載入後再確認 3D 白模。",
                "project": current_project,
            },
        )

    requirements, floorplan, room_by_id = _project_layout_context(current_project)
    del requirements  # context validation is intentional; the layout remains the source of truth
    workflow_data = current_project.get("workflow", {}).get("data", {})
    layout_record = workflow_data.get("layout_2d") or {}
    if layout_record.get("status") != "confirmed":
        raise HTTPException(
            409,
            {"code": "layout_confirmation_required", "message": "請先確認 2D 家具配置。"},
        )

    objects = list(layout_record.get("scene_objects") or [])
    _validate_project_layout_objects(floorplan, room_by_id, objects)
    expected_ids = [
        str(item["instance_id"])
        for item in objects
        if not item.get("placement_failed")
    ]
    expected_set = set(expected_ids)
    visible_set = set(payload.visible_instance_ids)
    if visible_set != expected_set:
        raise HTTPException(
            422,
            {
                "code": "white_model_furniture_incomplete",
                "message": "3D 白模必須顯示全部已確認家具，才能完成確認。",
                "missing_instance_ids": sorted(expected_set - visible_set),
                "unexpected_instance_ids": sorted(visible_set - expected_set),
            },
        )

    opening_geometry = floorplan.get("opening_geometry") or {}
    expected_windows = len(floorplan.get("windows") or [])
    if (
        not floorplan.get("wall_solids")
        or opening_geometry.get("status") != "opening_aware"
        or int(opening_geometry.get("window_opening_count") or 0) != expected_windows
    ):
        raise HTTPException(
            422,
            {
                "code": "white_model_window_opening_incomplete",
                "message": "仍有窗未在牆體形成真實開口，請先回到空間確認修正窗線。",
                "expected_window_count": expected_windows,
                "matched_window_count": int(opening_geometry.get("window_opening_count") or 0),
            },
        )

    white_model_record = {
        "status": "confirmed",
        "version": payload.expected_revision + 1,
        "confirmed_by": "user",
        "renderer": payload.renderer,
        "units": "cm",
        "built_from_layout_revision": layout_record.get("layout_revision"),
        "expected_furniture_count": len(expected_ids),
        "visible_furniture_count": len(payload.visible_instance_ids),
        "neutral_furniture_count": len(payload.visible_instance_ids),
        "visible_instance_ids": expected_ids,
        "window_opening_count": expected_windows,
        "wall_geometry": "opening_aware_solids",
    }
    completed = [
        step
        for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {"white_model_3d", "viewpoint", "style_render", "realistic_3d"}
    ]
    if "layout_2d" not in completed:
        completed.append("layout_2d")
    completed.append("white_model_3d")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="viewpoint",
            workflow={
                "completed": completed,
                "data": {
                    "white_model_3d": white_model_record,
                    "viewpoint": None,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            409,
            {
                "code": "project_revision_conflict",
                "message": "專案已更新，請重新載入後再確認 3D 白模。",
                "project": exc.project,
            },
        ) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "3D 白模確認內容過大，請減少家具後重試。") from exc
    return {"project": project, "white_model": white_model_record}


@router.post(
    "/api/projects/{project_id}/viewpoint/confirm",
    response_model=ProjectViewpointConfirmationResponse,
)
def confirm_project_viewpoint(
    project_id: str,
    payload: ProjectViewpointConfirmationRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再鎖定視角。", "project": current_project},
        )
    data = current_project.get("workflow", {}).get("data", {})
    white_model = data.get("white_model_3d") or {}
    if white_model.get("status") != "confirmed":
        raise HTTPException(409, {"code": "white_model_required", "message": "請先確認 3D 白模。"})

    camera = payload.model_dump(exclude={"expected_revision", "user_reviewed"})
    position = camera["position_cm"]
    target = camera["target_cm"]
    distance_cm = math.sqrt(sum((position[key] - target[key]) ** 2 for key in ("x", "y", "z")))
    if distance_cm < 20:
        raise HTTPException(422, {"code": "invalid_viewpoint", "message": "攝影機與觀看目標距離過近，請調整後再鎖定。"})
    previous = data.get("viewpoint") or {}
    viewpoint = {
        "status": "locked",
        "confirmed_by": "user",
        "version": int(previous.get("version") or 0) + 1,
        "units": "cm",
        "built_from_white_model_version": white_model.get("version"),
        **camera,
    }
    completed = [
        step for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {"viewpoint", "style_render", "realistic_3d"}
    ]
    completed.append("viewpoint")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="style_render",
            workflow={
                "completed": completed,
                "data": {
                    "viewpoint": viewpoint,
                    "style_render": None,
                    "realistic_3d": None,
                },
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(409, {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再鎖定視角。", "project": exc.project}) from exc
    return {"project": project, "viewpoint": viewpoint}


@router.post(
    "/api/projects/{project_id}/style-card/apply",
    response_model=ProjectStyleCardApplyResponse,
)
def apply_project_style_card(
    project_id: str,
    payload: ProjectStyleCardApplyRequest,
    request: Request,
) -> dict:
    store = _project_store(request)
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != payload.expected_revision:
        raise HTTPException(
            409,
            {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再套用色卡。", "project": current_project},
        )
    data = current_project.get("workflow", {}).get("data", {})
    viewpoint = data.get("viewpoint") or {}
    white_model = data.get("white_model_3d") or {}
    layout = data.get("layout_2d") or {}
    if viewpoint.get("status") != "locked":
        raise HTTPException(409, {"code": "viewpoint_required", "message": "請先鎖定提案視角。"})
    intent = style_card_render_intent(load_taiwan_style_cards(), payload.card_id)
    if intent is None:
        raise HTTPException(422, {"code": "unknown_style_card", "message": "色卡不存在或缺少完整色票。"})
    requirements, floorplan, room_by_id = _project_layout_context(current_project)
    try:
        variant = build_style_variant(
            list(layout.get("scene_objects") or []),
            floorplan,
            list(_furniture_payload_cache()),
            style_id=str(intent["style_id"]),
        )
    except ValueError as exc:
        raise HTTPException(
            422,
            {"code": "style_variant_unplaceable", "message": str(exc)},
        ) from exc
    objects = _canonical_layout_objects(variant["scene_objects"], requirements, room_by_id)
    _validate_project_layout_objects(floorplan, room_by_id, objects)
    previous = data.get("style_render") or {}
    style_render = {
        "status": "configured",
        "version": int(previous.get("version") or 0) + 1,
        "built_from_white_model_version": white_model.get("version"),
        "built_from_viewpoint_version": viewpoint.get("version"),
        "card_id": payload.card_id,
        "style_id": intent["style_id"],
        "render_intent": intent,
        "scene_objects": objects,
        "replacements": variant["replacements"],
        "protected_instance_ids": variant["protected_instance_ids"],
        "warnings": variant["warnings"],
        "furniture_policy": {
            "protected": "user_required_or_selection_source_user",
            "replace_others_on_card_change": True,
            "placement_authority": "backend.engine",
        },
    }
    completed = [
        step for step in (current_project.get("workflow", {}).get("completed") or [])
        if step not in {"style_render", "realistic_3d"}
    ]
    completed.append("style_render")
    try:
        project = store.update_workflow(
            project_id,
            expected_revision=payload.expected_revision,
            current_step="style_render",
            workflow={
                "completed": completed,
                "data": {"style_render": style_render, "realistic_3d": None},
            },
        )
    except ProjectConflictError as exc:
        raise HTTPException(409, {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再套用色卡。", "project": exc.project}) from exc
    except WorkflowTooLargeError as exc:
        raise HTTPException(413, "色卡場景內容過大，請減少家具後重試。") from exc
    return {"project": project, "style_render": style_render}


def _public_render_record(record: dict) -> dict:
    payload = {key: value for key, value in record.items() if key != "path"}
    payload["download_url"] = (
        f"/api/projects/{record['project_id']}/renders/{record['render_id']}/png"
    )
    return payload


@router.post(
    "/api/projects/{project_id}/renders",
    response_model=ProjectRenderResponse,
    status_code=201,
)
async def create_project_render(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    expected_revision: int = Form(..., ge=0),
    provider: str = Form("browser_capture"),
) -> dict:
    if provider != "browser_capture":
        raise HTTPException(422, {"code": "unsupported_render_provider", "message": "P0 目前只接受瀏覽器場景 PNG。"})
    current_project = _stored_project(request, project_id)
    if current_project["revision"] != expected_revision:
        raise HTTPException(409, {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再輸出 PNG。", "project": current_project})
    data = current_project.get("workflow", {}).get("data", {})
    white_model = data.get("white_model_3d") or {}
    viewpoint = data.get("viewpoint") or {}
    style_render = data.get("style_render") or {}
    if white_model.get("status") != "confirmed" or viewpoint.get("status") != "locked" or style_render.get("status") != "configured":
        raise HTTPException(409, {"code": "render_configuration_incomplete", "message": "請先確認白模、鎖定視角並套用色卡。"})
    content = await file.read(MAX_FLOORPLAN_BYTES + 1)
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(415, {"code": "invalid_render_png", "message": "最終輸出必須是 PNG。"})
    if len(content) > MAX_FLOORPLAN_BYTES:
        raise HTTPException(413, {"code": "render_too_large", "message": "最終 PNG 不可超過 20 MB。"})
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(422, {"code": "invalid_render_png", "message": "PNG 檔案已損壞。"}) from exc
    try:
        render, project = _project_store(request).save_render(
            project_id,
            expected_revision=expected_revision,
            content=content,
            white_model_version=int(white_model.get("version") or 0),
            viewpoint_version=int(viewpoint.get("version") or 0),
            style_version=int(style_render.get("version") or 0),
            style_card_id=str(style_render.get("card_id") or ""),
            provider=provider,
        )
    except ProjectConflictError as exc:
        raise HTTPException(409, {"code": "project_revision_conflict", "message": "專案已更新，請重新載入後再輸出 PNG。", "project": exc.project}) from exc
    return {"project": project, "render": _public_render_record(render)}


@router.get(
    "/api/projects/{project_id}/renders",
    response_model=ProjectRenderListResponse,
)
def list_project_renders(project_id: str, request: Request) -> dict:
    try:
        renders = _project_store(request).list_renders(project_id)
    except KeyError as exc:
        raise HTTPException(404, {"code": "project_not_found", "message": "找不到專案。"}) from exc
    return {"renders": [_public_render_record(record) for record in renders]}


@router.get("/api/projects/{project_id}/renders/{render_id}/png")
def download_project_render(project_id: str, render_id: str, request: Request) -> FileResponse:
    try:
        render = _project_store(request).get_render(project_id, render_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, {"code": "render_not_found", "message": "找不到這張 PNG。"}) from exc
    path = render["path"]
    if not path.is_file():
        raise HTTPException(410, {"code": "render_file_missing", "message": "PNG 紀錄存在，但檔案已遺失。"})
    return FileResponse(path, media_type="image/png", filename=render["filename"])
