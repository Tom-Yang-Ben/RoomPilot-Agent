# -*- coding: utf-8 -*-
"""平面圖尺寸辨識系統：後端進入點。

POST /api/analyze  上傳 .dxf 或 .png/.jpg，回傳元素尺寸、校準資訊與 SVG 標註圖。
GET  /             提供前端上傳頁。
"""
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from dxf_parser import analyze_dxf
from png_pipeline import analyze_png
from svg_render import render_dxf_svg, render_png_svg

app = FastAPI(title="平面圖尺寸辨識")
_FRONTEND = Path(__file__).resolve().parent / "index.html"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_FRONTEND)


@app.post("/api/label")
async def label(file: str = Form(...), target: str = Form(...)) -> JSONResponse:
    """極簡標註：uncertain 裁圖 → 類別資料夾（~10% 分流黃金測試集）／other 負類／刪除。"""
    from furniture_match import label_uncertain
    result = label_uncertain(file, target)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return JSONResponse(result)


@app.post("/api/correct")
async def correct(
    png_b64: str = Form(...),
    target: str = Form(...),
    original: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
) -> JSONResponse:
    """辨識錯誤修正：前端回傳該偵測的裁圖與正確類別，存入訓練庫供重訓。"""
    import base64
    from furniture_match import save_correction
    try:
        png = base64.b64decode(png_b64, validate=True)
    except Exception:
        raise HTTPException(400, "裁圖編碼無效")
    result = save_correction(png, target, from_class=original, source=source)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return JSONResponse(result)


@app.post("/api/rezone")
async def rezone_api(payload: dict = Body(...)) -> JSONResponse:
    """依修正／刪除後的家具定義重算空間名稱與機能分區（不重新辨識影像）。"""
    from furniture_match import rezone
    try:
        mmpp = payload.get("mm_per_px")
        result = rezone(payload.get("furniture") or [], payload.get("rooms") or [],
                        float(mmpp) if mmpp else None)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"重算輸入無效:{exc}")
    return JSONResponse(result)


@app.post("/api/retrain")
def retrain() -> JSONResponse:
    """手動觸發背景重訓（整理完 uncertain 後按）。訓練期間沿用現役模型。"""
    from furniture_ml import request_retrain
    return JSONResponse(request_retrain())


@app.get("/api/ml/status")
def ml_status() -> JSONResponse:
    """模型狀態：版本、驗證分數、黃金集分數、是否重訓中、上次結果。"""
    from furniture_ml import model_info
    return JSONResponse(model_info())


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    ref_x1: Optional[float] = Form(None),
    ref_y1: Optional[float] = Form(None),
    ref_x2: Optional[float] = Form(None),
    ref_y2: Optional[float] = Form(None),
    ref_mm: Optional[float] = Form(None),
    overrides: Optional[str] = Form(None),
) -> JSONResponse:
    name = (file.filename or "").lower()
    data = await file.read()
    if not data:
        raise HTTPException(400, "檔案為空。")
    ov: list = []
    if overrides:
        import json as _json
        try:
            parsed = _json.loads(overrides)
        except ValueError:
            raise HTTPException(400, "使用者定義（overrides）不是有效的 JSON。")
        if not isinstance(parsed, list):
            raise HTTPException(400, "使用者定義（overrides）需為陣列。")
        ov = parsed[:200]  # 上限保護
    try:
        if name.endswith(".dxf"):
            result = analyze_dxf(data)
            result["svg"] = render_dxf_svg(result)
        elif name.endswith((".png", ".jpg", ".jpeg")):
            manual = None
            if None not in (ref_x1, ref_y1, ref_x2, ref_y2, ref_mm) and ref_mm > 0:
                manual = {"x1": ref_x1, "y1": ref_y1, "x2": ref_x2, "y2": ref_y2,
                          "length_mm": ref_mm}
            result = analyze_png(data, manual, source_name=file.filename, overrides=ov)
            result["svg"] = render_png_svg(result)
            # 結構圖同樣套用完整標註（與標註圖相同的尺寸、格線、面積）
            result["svg_struct"] = render_png_svg(result, background="structural")
            result.pop("original_png_b64", None)  # 已內嵌於 SVG，不重複回傳
        else:
            raise HTTPException(400, "僅支援 .dxf 與 .png/.jpg 檔案。")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"辨識失敗：{exc}")
    return JSONResponse(result)
