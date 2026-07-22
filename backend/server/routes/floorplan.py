"""平面圖端點:示範 DXF 清單/解析、DXF 上傳升維、PNG/JPG 影像辨識。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ...upgrade3d.dxf_parser import list_plans, parse_dxf_bytes, parse_dxf_file
from ..config import MAX_FLOORPLAN_BYTES, PLAN_DIR
from ..services import floorplan_recognition

router = APIRouter()


# ---------------------------------------------------------------------------
# 以下路由自原 app/backend/main.py 移植,供 frontend3d(React Three Fiber)使用
# ---------------------------------------------------------------------------


@router.get("/api/plans")
def plans() -> dict:
    return {"plans": list_plans(str(PLAN_DIR))}


@router.get("/api/plan")
def plan(
    name: str,
    scale_m: float | None = Query(None, gt=0, le=500),
    thickness: float = Query(0.18, gt=0, le=2),
    height: float = Query(2.7, gt=0, le=10),
):
    path = PLAN_DIR / Path(name).name  # basename: 防路徑跳脫
    if not path.is_file():
        raise HTTPException(404, f"plan not found: {name}")
    try:
        return parse_dxf_file(str(path), scale_m, thickness, height)
    except Exception as e:
        raise HTTPException(422, f"parse failed: {e}")


@router.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    scale_m: float | None = Query(None, gt=0, le=500),
    thickness: float = Query(0.18, gt=0, le=2),
    height: float = Query(2.7, gt=0, le=10),
):
    data = await file.read()
    try:
        return parse_dxf_bytes(data, file.filename or "upload.dxf", scale_m, thickness, height)
    except Exception as e:
        raise HTTPException(422, f"parse failed: {e}")


@router.post("/api/floorplan/recognize")
async def recognize_floorplan(
    file: UploadFile = File(...),
    scale_m: float | None = Query(None, gt=0, le=500),
    thickness: float = Query(0.18, gt=0, le=2),
    height: float = Query(2.7, gt=0, le=10),
    allow_openrouter: bool = Query(False),
):
    raw = await file.read(MAX_FLOORPLAN_BYTES + 1)
    if not raw:
        raise HTTPException(422, "平面圖是空檔案，請重新選擇。")
    if len(raw) > MAX_FLOORPLAN_BYTES:
        raise HTTPException(413, "平面圖檔案不可超過 20 MB。")
    name = Path(file.filename or "upload.png").name
    suffix = Path(name).suffix.lower()
    if suffix not in {".dxf", ".png", ".jpg", ".jpeg", ".bmp"}:
        raise HTTPException(415, "只支援 DXF、PNG、JPG、JPEG 或 BMP 平面圖。")
    return floorplan_recognition.recognize_floorplan_bytes(
        raw,
        name,
        scale_m,
        thickness,
        height,
        allow_openrouter,
    )
