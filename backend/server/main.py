"""RoomPilot FastAPI 組裝點:app、lifespan、CORS、靜態掛載與路由註冊。

功能實作分層(2026-07-21 自單檔 main.py 拆分):
- routes/    HTTP 端點:pages(頁面與整站資料)、projects(五階段 workflow)、
             scene(場景生成/佈局/驗證)、library(家具庫與 GLB)、floorplan(DXF/辨識)
- services/  業務邏輯:catalog_service、glb_assets、floorplan_recognition、
             scene_service、layout_service、requirements_service、intake_service、
             floorplan_vlm、style_cards
- storage/   專案持久化:project_store、project_models、runtime_paths
- config.py  共用路徑與常數

啟動:repo 根目錄 `uv run --extra vision uvicorn backend.server.main:app --port 8002`。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import MOODBOARD_DIR, PROJECT_DIR, STATIC_DIR
from .routes import floorplan, library, pages, projects, scene
from .services.catalog_service import warm_catalog_cache
from .storage.project_store import ProjectStore
from .storage.runtime_paths import project_runtime_dir


@asynccontextmanager
async def app_lifespan(application: FastAPI):
    """Initialize writable runtime services only when the server starts."""
    application.state.project_store = ProjectStore(project_runtime_dir(PROJECT_DIR))
    warm_catalog_cache()
    try:
        yield
    finally:
        application.state.project_store = None


app = FastAPI(title="AI 室內風格與家具配置展示系統", lifespan=app_lifespan)

# 本機開發跨埠存取(復刻原型 :8030、frontend3d dev server 等)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/docs-assets", StaticFiles(directory=MOODBOARD_DIR), name="docs-assets")

# /api/furniture/* 的動態路由順序都收在 library router 內部,跨 router 無路徑重疊。
app.include_router(pages.router)
app.include_router(projects.router)
app.include_router(scene.router)
app.include_router(library.router)
app.include_router(floorplan.router)
