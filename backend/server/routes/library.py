"""家具庫端點:型錄清單/明細、GLB 模型與貼圖、示範家具檔。

注意路由順序:/api/furniture/{furniture_id}/model* 必須先於
/api/furniture/{name}(單段萬用,同時服務示範 GLB 與家具明細)。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response

from ..config import SAMPLE_GLB_DIR
from ..services.catalog_service import (
    _category_groups_for,
    _filter_furniture_payload,
    _furniture_card_payload,
    _furniture_detail_payload,
    _furniture_filter_options,
    _get_furniture_by_id,
    _get_merged_furniture_by_id,
    _style_filter_options,
    _type_options_for,
)
from ..services.glb_assets import (
    _get_model_path_for_furniture,
    _gltf_payload_for_web,
    _image_bytes_from_glb,
    _model_response_for_merged_furniture,
    _parse_glb,
)

router = APIRouter()


@router.get("/api/furniture")
def furniture_catalog(
    style: str | None = Query(None),
    group: str | None = Query(None),
    item_type: str | None = Query(None, alias="type"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=80),
    has_model: bool | None = Query(None),
    detail: str = Query("card"),
    color: str | None = None,
    material: str | None = None,
    size: str | None = None,
) -> dict:
    facet_items = _filter_furniture_payload(
        style=style,
        group=group,
        item_type=item_type,
        q=q,
        has_model=has_model,
    )
    filtered = _filter_furniture_payload(
        style=style,
        group=group,
        item_type=item_type,
        q=q,
        has_model=has_model,
        color=color,
        material=material,
        size=size,
    )
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    sample_files = (
        sorted(f.name for f in SAMPLE_GLB_DIR.iterdir() if f.suffix.lower() == ".glb")
        if SAMPLE_GLB_DIR.is_dir()
        else []
    )
    return {
        "items": [
            item if detail == "scene" else _furniture_card_payload(item)
            for item in filtered[start:end]
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next_page": end < total,
        "styles": _style_filter_options(),
        "type_options": _type_options_for(style, group, has_model),
        "category_groups": _category_groups_for(style, has_model),
        "filter_options": _furniture_filter_options(facet_items),
        "furniture": sample_files,
    }


@router.get("/api/furniture/{furniture_id}/model")
def furniture_model(furniture_id: str):
    furniture = _get_merged_furniture_by_id(furniture_id)
    return _model_response_for_merged_furniture(furniture)


@router.get("/api/furniture/{furniture_id}/model.gltf")
def furniture_model_gltf(furniture_id: str) -> JSONResponse:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    return JSONResponse(_gltf_payload_for_web(model_path_text, furniture_id))


@router.get("/api/furniture/{furniture_id}/buffer.bin")
def furniture_model_buffer(furniture_id: str) -> Response:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    _, binary_payload = _parse_glb(model_path_text)
    return Response(content=binary_payload, media_type="application/octet-stream")


@router.get("/api/furniture/{furniture_id}/images/{image_index}")
def furniture_model_image(furniture_id: str, image_index: int) -> Response:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    image_bytes, mime_type = _image_bytes_from_glb(model_path_text, image_index)
    return Response(content=image_bytes, media_type=mime_type)


@router.get("/api/sample-furniture")
def sample_furniture() -> dict:
    files = (
        sorted(f for f in SAMPLE_GLB_DIR.iterdir() if f.suffix.lower() == ".glb")
        if SAMPLE_GLB_DIR.is_dir()
        else []
    )
    return {"furniture": [f.name for f in files]}


@router.get("/api/furniture/{name}")
def sample_furniture_file(name: str):
    if not name.lower().endswith(".glb"):
        return _furniture_detail_payload(name)
    path = SAMPLE_GLB_DIR / Path(name).name
    if not path.is_file():
        raise HTTPException(404, f"furniture not found: {name}")
    return FileResponse(path, media_type="model/gltf-binary")
