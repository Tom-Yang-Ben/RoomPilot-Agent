"""網站頁面與整站資料端點:/、/styles、/library、/scene、/panorama 與 /api/site-data 等。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import STATIC_DIR
from ..services.catalog_service import (
    _catalog_count_summary,
    _style_payloads,
    build_site_payload,
    load_surface_catalog,
)
from ..services.style_cards import load_taiwan_style_cards

router = APIRouter()


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@router.get("/")
def home() -> FileResponse:
    return _page("index.html")


@router.get("/styles")
def styles_page() -> FileResponse:
    return _page("styles.html")


@router.get("/library")
def library_page() -> FileResponse:
    return _page("library.html")


@router.get("/scene")
def scene_page() -> FileResponse:
    # 單一入口：FastAPI 直接交付已建置的 React/R3F 完整工作流。
    return _page("frontend3d/index.html")


@router.get("/panorama")
def panorama_page() -> FileResponse:
    return _page("panorama/panorama.html")


@router.get("/api/site-data")
def site_data() -> dict:
    payload = dict(build_site_payload())
    payload["furniture"] = []
    payload["featured_models"] = []
    payload["catalog_merge_summary"] = {
        **payload.get("catalog_merge_summary", {}),
        "delivery": "請使用 /api/furniture 分頁取得家具資料。",
    }
    return payload


@router.get("/api/home-data")
def home_data() -> dict:
    summary = _catalog_count_summary()
    return {
        "project": {
            "title": "RoomPilot",
            "subtitle": "AI 室內配置與 3D 場景提案",
        },
        "summary": {
            "total_furniture": summary.get("total_furniture", 0),
            "styled_furniture": summary.get("styled_furniture", 0),
        },
        "styles": _style_payloads()[:6],
        "taiwan_style_cards": load_taiwan_style_cards()[:6],
    }


@router.get("/api/styles")
def styles_data() -> dict:
    summary = _catalog_count_summary()
    return {
        "styles": _style_payloads(),
        "taiwan_style_cards": load_taiwan_style_cards(),
        "surface_catalog": load_surface_catalog(),
        "summary": {
            "total_furniture": summary.get("total_furniture", 0),
            "styled_furniture": summary.get("styled_furniture", 0),
            "fallback_furniture": summary.get("fallback_furniture", 0),
        },
        "style_furniture_counts": summary.get("style_furniture_counts", {}),
        "style_type_counts": summary.get("style_type_counts", {}),
    }
