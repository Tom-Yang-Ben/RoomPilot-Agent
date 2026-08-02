from __future__ import annotations

import io
import csv
import json
import os
import re
import zipfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any
from weakref import WeakKeyDictionary

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from ..paths import STATIC_DIR
from ..agent.place import resolve_placements
from ..agent.select import (
    SelectionParseError,
    SelectionUnavailableError,
    local_selection_raw,
    parse_selections,
    preselected_from_requirements,
    request_selections,
    requirements_from_context,
)
from ..catalog.style_db import sanitize_size_cm
from ..catalog.cloud_catalog import load_official_catalog
from ..floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)
from ..floorplan.vision.ocr import default_ocr_provider
from ..upgrade3d.dxf_parser import list_plans, parse_dxf_bytes, parse_dxf_file
from .scene_service import (
    _largest_region_boundary,
    _region_boundary_by_id,
    _regions_boundary,
    build_scene_payload,
    curtain_window_hint,
    floorplan_from_editor_payload,
    generate_layout,
    get_openrouter_status,
    parse_floorplan_with_engine,
    resolve_placement_preferences,
    room_from_payload,
    scene_object_in_boundary,
    selection_complete_fn,
    validate_single_placement,
)
from .catalog_admin import router as catalog_admin_router
from .rag_api import router as rag_router
from .engineering.api import build_engineering_router
from .shortlist_api import build_shortlist_router
from ..spatial_data.rag.preload import PRELOADER
from .auth import dependencies as auth_dependencies
from .auth.api import build_auth_router
from .auth.service import AuthService
from .auth.tokens import TokenService
from .auth.user_store import build_user_store
from .project_store import (
    ProjectStoreBusy,
    ProjectStoreUnavailable,
    ProjectVersionConflict,
    WorkflowTooLargeError,
    build_project_store,
)
from .runtime_paths import legacy_runtime_dirs, project_runtime_dir
from .render_service import (
    RenderProviderRejected,
    RenderProviderUnavailable,
    render_provider_status,
    submit_render_jobs,
)
from .render_providers import (
    direct_image_provider_available,
    direct_image_provider_status,
    run_direct_render_jobs,
)
from .style_cards import load_taiwan_style_cards
from .services.cloud_models import (
    cloud_model_status,
    cloud_model_url,
    cloudfront_required,
    manifest_status,
)
from .services.cloud_images import (
    image_manifest_status,
)
from ..catalog.postgres_repository import (
    CatalogPoolTimeout,
    CatalogQuery,
    catalog_provider_mode,
    catalog_provider_status,
    catalog_summary as postgres_catalog_summary,
    close_catalog_pools,
    get_catalog_item as get_postgres_catalog_item,
    load_catalog as load_postgres_catalog,
    postgres_catalog_requested,
    query_catalog_page as query_postgres_catalog,
)
from ..catalog.runtime_catalog_repository import (
    RuntimeCatalogUnavailable,
    load_runtime_design_styles,
    load_runtime_external_import_index,
    load_runtime_surface_catalog,
    runtime_catalog_status,
)
from . import catalog_payloads
from .asset_payloads import (
    DATASET_DIR,
    _DATASET_GLB_ROOTS,
    _dataset_glb_lookup,
    _external_zip_entry_variants,
    _glb_lookup_keys,
    _gltf_payload_for_web,
    _image_bytes_from_glb,
    _is_remote_glb_url,
    _normalize_posix_path,
    _parse_glb,
    _remote_glb_response,
    _remote_glb_url,
    _resolve_glb_path,
    _safe_relative_url,
)
from .catalog_payloads import (
    _candidate_match_reason,
    _candidate_quantity_template,
    _candidate_schema_fields,
    _candidate_score,
    _candidate_style_id,
    _dedupe_style_candidates,
    _furniture_card_payload,
    _furniture_filter_options,
    _furniture_matches_style,
    _furniture_payload_item,
    _furniture_search_text,
    _furniture_size_bucket,
    _implausible_for_type,
    _json_catalog_count_summary,
    _json_furniture_payload_cache,
    _merge_furniture_catalog,
    _merge_key,
    _merge_style_candidates,
    _merged_furniture_catalog_cached,
    _model_priority_ids,
    _model_url_for_merged_item,
    _normalize_catalog_item,
    _normalize_catalog_payload,
    _normalize_furniture_facet_value,
    _rule_based_style_candidates,
    _style_filter_options,
    _style_ids_for_count,
    _text_key,
    _variant_key,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent


def _project_path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


STYLE_PRESENTATION_DB_PATH = (
    BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_6styles_zh.json"
)
OFFICIAL_FURNITURE_CATALOG_PATH = (
    PROJECT_DIR / "JSON" / "furniture" / "furniture_official_catagory.json"
)
CLOUD_CATALOG_PATH = _project_path_from_env(
    "ROOMPILOT_CLOUD_CATALOG_PATH",
    OFFICIAL_FURNITURE_CATALOG_PATH,
)
CLOUD_MANIFEST_PATH = _project_path_from_env(
    "ROOMPILOT_GLB_MANIFEST_PATH",
    PROJECT_DIR / "JSON" / "manifests" / "glb_upload_all_result.csv",
)
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
EXTERNAL_IMPORT_PATH = BASE_DIR.parent / "catalog" / "data" / "舊友：12種風格與JSON" / "external_furniture_import_index.json"
PLAN_DIR = PROJECT_DIR / "testdata" / "pic" / "temp"
SAMPLE_GLB_DIR = PROJECT_DIR / "testdata" / "sample_glb"
SAMPLE_FLOORPLAN_630 = PROJECT_DIR / "testdata" / "png" / "builder_plan_630.png"
PROJECT_STORE = build_project_store(
    PROJECT_DIR,
    project_runtime_dir(PROJECT_DIR),
)
if PROJECT_STORE.imports_legacy_on_startup:
    for legacy_runtime in legacy_runtime_dirs(PROJECT_DIR):
        PROJECT_STORE.import_runtime(legacy_runtime)
_USER_STORE_CACHE: "WeakKeyDictionary[object, object]" = WeakKeyDictionary()
_USER_STORE_LOCK = Lock()


def user_store() -> Any:
    """取得對應目前 PROJECT_STORE 的使用者儲存。

    使用者、成員與專案必須在同一個資料庫，授權查詢才能 JOIN，也才不會出現
    「專案建在 A 庫、擁有者寫進 B 庫」。PROJECT_STORE 可在執行期被替換
    （測試會 monkeypatch，provider 也可能切換），所以這裡依當下的 store 解析
    並以弱參考快取，不做模組級單例。
    """
    store = PROJECT_STORE
    with _USER_STORE_LOCK:
        cached = _USER_STORE_CACHE.get(store)
        if cached is None:
            cached = build_user_store(store)
            _USER_STORE_CACHE[store] = cached
        return cached


AUTH_SERVICE = AuthService(
    user_store,
    TokenService.from_environment(PROJECT_DIR, project_runtime_dir(PROJECT_DIR)),
)
auth_dependencies.configure(auth_service=AUTH_SERVICE, user_store=user_store)


def _adopt_unowned_projects_on_startup() -> None:
    """升級既有部署：帳戶端之前建立的專案沒有 owner，交給最早的 admin。

    best-effort：資料庫暫時不可用或使用者表還沒建立時不能讓服務起不來，
    第一個 admin 註冊時還會再做一次，兩邊都是冪等的。
    """
    try:
        admin = user_store().find_first_admin()
        if admin is not None:
            AUTH_SERVICE.adopt_unowned_projects(admin["user_id"])
    except Exception:  # noqa: BLE001 - 啟動期不可因遷移失敗而中斷服務
        pass


_adopt_unowned_projects_on_startup()
FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")


def _floorplan_ocr_provider():
    """印刷房名與尺寸標註的 OCR 供應者（2026-07 盤點第 3 項「OCR 死碼」接線）。

    paddle 未安裝時回 None，行為與接線前完全一致（比例尺回到手拉）；
    ROOMPILOT_OCR_DISABLED=1 可在演示現場緊急停用。
    實例由 ocr.default_ocr_provider 以 lru_cache 共用，不會每請求重建引擎。
    """
    if os.environ.get("ROOMPILOT_OCR_DISABLED") == "1":
        return None
    return default_ocr_provider()
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
_EXTERNAL_GLB_ZIP_SEARCH_DIRS = (
    DATASET_DIR,
    Path.home() / "Downloads",
)
_EXTERNAL_GLB_ZIP_PATTERNS = (
    "downloaded-files*.zip",
    "ABO*.zip",
    "補缺的GLB*.zip",
    "ikea抓取家具glb_中文命名版*.zip",
    "drive-download-202607*.zip",
)


app = FastAPI(title="AI 室內風格與家具配置展示系統")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(build_auth_router())
app.include_router(catalog_admin_router)
app.include_router(rag_router)
app.include_router(
    build_engineering_router(
        project_store_getter=lambda: PROJECT_STORE,
        project_dir=PROJECT_DIR,
    )
)
app.include_router(
    build_shortlist_router(
        project_store_getter=lambda: PROJECT_STORE,
        project_dir=PROJECT_DIR,
    )
)
# bge-m3 在 CPU 上首次載入約 34 秒。背景載入讓服務立即可用，未就緒時候選集
# 檢索會退成純結構化過濾並標記為過期，模型就緒後下一次送出自動補算語意排序。
PRELOADER.start(PROJECT_DIR)


@app.exception_handler(ProjectStoreUnavailable)
async def project_store_unavailable_handler(_request, exc: ProjectStoreUnavailable):
    busy = isinstance(exc, ProjectStoreBusy)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"} if busy else None,
        content={
            "detail": {
                "code": "project_store_busy" if busy else "project_store_unavailable",
                "message": (
                    "專案資料庫同時處理的請求過多，請稍後再試。"
                    if busy
                    else "PostgreSQL 專案保存目前不可用，請檢查資料庫與 Phase 3 schema。"
                ),
                "reason": str(exc),
            }
        },
    )


@app.exception_handler(RuntimeCatalogUnavailable)
async def runtime_catalog_unavailable_handler(_request, exc: RuntimeCatalogUnavailable):
    # 瞬時滿載與「型錄沒匯入」的處置完全不同，訊息不能混為一談：QA 實測
    # 併發 10 就被導去執行匯入流程，等於把使用者送去修一個沒壞的東西。
    busy = isinstance(exc.reason, CatalogPoolTimeout)
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"} if busy else None,
        content={
            "detail": {
                "code": "catalog_pool_busy" if busy else "runtime_catalog_unavailable",
                "catalog": exc.catalog_key,
                "message": (
                    "型錄資料庫同時處理的查詢過多，請稍後再試。"
                    if busy
                    else "Phase 4 PostgreSQL runtime catalog 目前不可用，請先執行匯入流程。"
                ),
                "reason": str(exc.reason),
            }
        },
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _iter_external_zip_paths() -> list[Path]:
    roots: list[Path] = []
    env_roots = os.environ.get("ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS", "")
    for raw_root in env_roots.split(os.pathsep):
        raw_root = raw_root.strip()
        if raw_root:
            roots.append(Path(raw_root))
    if not roots:
        roots.extend(_EXTERNAL_GLB_ZIP_SEARCH_DIRS)

    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        candidates: list[Path] = []
        if root.is_file() and root.suffix.lower() == ".zip":
            candidates = [root]
        elif root.is_dir():
            for pattern in _EXTERNAL_GLB_ZIP_PATTERNS:
                candidates.extend(root.glob(pattern))

        for candidate in candidates:
            key = str(candidate.resolve()).casefold()
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            found.append(candidate)
    return found


@lru_cache(maxsize=1)
def _external_zip_entry_lookup() -> dict[str, tuple[Path, str]]:
    lookup: dict[str, tuple[Path, str]] = {}
    conflicts: set[str] = set()

    def remember(key: str, archive_path: Path, entry_name: str) -> None:
        existing = lookup.get(key)
        if existing is not None and existing[1] != entry_name:
            conflicts.add(key)
            return
        lookup[key] = (archive_path, entry_name)

    for archive_path in _iter_external_zip_paths():
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for entry_name in archive.namelist():
                    if not entry_name.lower().endswith(".glb"):
                        continue
                    for key in _glb_lookup_keys(entry_name):
                        remember(key, archive_path, entry_name)
        except (OSError, zipfile.BadZipFile):
            continue

    for key in conflicts:
        lookup.pop(key, None)
    return lookup


def _resolve_external_zip_entry(furniture: dict) -> tuple[Path, str] | None:
    entry_names: list[str] = []
    for key in ("zip_entry", "glb_relative_path", "glb_absolute_path", "model_path", "glb_path"):
        value = str(furniture.get(key) or "").strip()
        if value and not _is_remote_glb_url(value):
            entry_names.extend(_external_zip_entry_variants(value))
    entry_names = list(dict.fromkeys(entry_names))
    if not entry_names:
        return None

    direct_archive = Path(str(furniture.get("source_archive_path") or ""))
    direct_candidates = [direct_archive]
    if not direct_archive.is_absolute():
        direct_candidates.extend(
            [
                PROJECT_DIR / direct_archive,
                DATASET_DIR / direct_archive,
                Path.home() / "Downloads" / direct_archive.name,
            ]
        )

    for archive_path in direct_candidates:
        if not (archive_path.is_file() and archive_path.suffix.lower() == ".zip"):
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                for variant in entry_names:
                    if variant in names:
                        return archive_path, variant
        except (OSError, zipfile.BadZipFile):
            continue

    lookup = _external_zip_entry_lookup()
    for variant in entry_names:
        for key in _glb_lookup_keys(variant):
            resolved = lookup.get(key)
            if resolved is not None and resolved[0].exists():
                return resolved
    return None


def _model_status(furniture: dict) -> tuple[bool, str]:
    cloud_url = cloud_model_url(furniture)
    if cloud_url:
        return True, "CloudFront GLB 可用"

    if cloudfront_required():
        return cloud_model_status(furniture)

    if _remote_glb_url(furniture):
        return True, "遠端 GLB 可由伺服器代理載入。"

    if _resolve_external_zip_entry(furniture) is not None:
        return True, "外部 GLB zip 可用"

    if furniture.get("zip_entry"):
        return False, "外部家具有 zip_entry，但目前找不到對應 GLB zip 或 zip 內 entry。"

    if not furniture.get("glb_absolute_path") and not furniture.get("glb_relative_path"):
        return False, "這件家具沒有設定 GLB 路徑。"

    if _resolve_glb_path(furniture) is not None:
        return True, "GLB 可用"

    return False, "資料有記錄，但 dataset/ 中找不到對應的 GLB 檔案(請先從雲端下載 dataset)。"


@lru_cache(maxsize=1)
def load_style_database() -> dict:
    return load_official_catalog(
        CLOUD_CATALOG_PATH,
        STYLE_PRESENTATION_DB_PATH,
        CLOUD_MANIFEST_PATH,
    )


# 佇列 7 拆分：注入 catalog_payloads 需要的 GLB 可用性判定與官方型錄載入器。
# 用 main 的函式物件注入、而非讓 catalog_payloads 反向 import main（會形成循環）；
# 既有測試 monkeypatch main 的模組屬性（_EXTERNAL_GLB_ZIP_SEARCH_DIRS、
# _resolve_external_zip_entry 等）時，判定鏈留在 main 的命名空間才讀得到補丁值。
catalog_payloads._model_status = _model_status
catalog_payloads.load_style_database = load_style_database


def load_surface_catalog() -> dict:
    return load_runtime_surface_catalog(PROJECT_DIR, SURFACE_DB_PATH)


def load_external_import_index() -> dict:
    return load_runtime_external_import_index(PROJECT_DIR, EXTERNAL_IMPORT_PATH)


def _style_surface_profile(surface_catalog: dict, style_id: str | None) -> dict:
    profiles = surface_catalog.get("style_surface_profiles") or {}
    return profiles.get(style_id or "") or profiles.get("scandinavian") or {}


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


def _payload_number(
    payload: dict,
    key: str,
    default: float | None = None,
    *,
    minimum: float | None = None,
) -> float | None:
    """把 payload 的數值欄位轉成 float。

    型別錯誤是呼叫端的問題，要回 422 說清楚哪個欄位錯；直接 float() 讓
    ValueError 冒到 FastAPI 只會變成 500，前端只看得到「操作失敗」。
    """
    raw = payload.get(key)
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise HTTPException(status_code=422, detail=f"{key} 必須是數字。")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"{key} 必須是數字。") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise HTTPException(status_code=422, detail=f"{key} 必須是有限數字。")
    if minimum is not None and value < minimum:
        raise HTTPException(status_code=422, detail=f"{key} 不得小於 {minimum:g}。")
    return value


def _payload_mapping(payload: dict, key: str) -> dict:
    raw = payload.get(key)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail=f"{key} 必須是物件。")
    return raw


def _payload_sequence(payload: dict, key: str) -> list:
    raw = payload.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail=f"{key} 必須是陣列。")
    return raw


def _furniture_payload_cache() -> tuple[dict, ...]:
    """Read SQL every time in formal mode; cache only explicit offline JSON."""
    if catalog_provider_mode(PROJECT_DIR) == "postgres":
        try:
            return _normalize_catalog_payload(load_postgres_catalog(PROJECT_DIR))
        except RuntimeCatalogUnavailable:
            raise
        except Exception as exc:
            raise RuntimeCatalogUnavailable("furniture_catalog", exc) from exc
    return _normalize_catalog_payload(_json_furniture_payload_cache())


def _clear_furniture_payload_cache() -> None:
    _json_furniture_payload_cache.cache_clear()


_furniture_payload_cache.cache_clear = _clear_furniture_payload_cache  # type: ignore[attr-defined]


def _postgres_catalog_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "postgres_catalog_unavailable",
            "message": "正式家具資料庫目前無法使用；請檢查 PostgreSQL 連線與 catalog view。",
            "reason": type(exc).__name__,
        },
    )


@lru_cache(maxsize=1)
def _appliance_payload_cache() -> tuple[dict, ...]:
    return ()
    if not COMBINED_CATALOG_PATH.exists():
        return ()
    raw = json.loads(COMBINED_CATALOG_PATH.read_text(encoding="utf-8"))
    items = []
    manifest = _appliance_manifest_index()
    for source in raw.get("items", []):
        if source.get("role_code") != "appliance":
            continue
        item = {
            **source,
            "furniture_id": source.get("furniture_id") or source.get("id"),
            "normalized_type": (
                source.get("normalized_type")
                or source.get("type_code")
                or source.get("type")
            ),
            "name_zh_raw": source.get("name_zh_raw") or source.get("name_zh"),
            "category_label": source.get("category_label") or source.get("category"),
            "taxonomy_group": "appliance",
            "taxonomy_group_zh": "家電",
            "catalog_scope": "appliance",
        }
        payload = _furniture_payload_item(item)
        verified_url = manifest.get(str(item["furniture_id"]))
        if verified_url:
            payload["has_model"] = True
            payload["missing_model_reason"] = None
            payload["model_url"] = verified_url
            payload["match_reason"] = (
                f"類型為 {payload.get('normalized_type')}，"
                "且已有完整 manifest 驗證的 CloudFront GLB。"
            )
        items.append(payload)
    return tuple(items)


def _get_furniture_by_id(furniture_id: str) -> dict:
    data = load_style_database()
    furniture = next((item for item in data.get("furniture", []) if item.get("furniture_id") == furniture_id), None)
    if not furniture:
        raise HTTPException(status_code=404, detail="找不到這件家具資料。")
    return furniture


def _get_external_furniture_by_id(furniture_id: str) -> dict:
    data = load_external_import_index()
    furniture = next((item for item in data.get("items", []) if item.get("furniture_id") == furniture_id), None)
    if not furniture:
        raise HTTPException(status_code=404, detail="找不到外部匯入家具。")
    return furniture


def _get_json_merged_furniture_by_id(furniture_id: str) -> dict:
    for item in _merged_furniture_catalog_cached():
        aliases = set(item.get("merged_furniture_ids") or [])
        aliases.add(str(item.get("furniture_id")))
        if furniture_id in aliases:
            return item
    raise HTTPException(status_code=404, detail="Furniture not found in merged catalog.")


def _get_merged_furniture_by_id(furniture_id: str) -> dict:
    if postgres_catalog_requested(PROJECT_DIR):
        try:
            item = get_postgres_catalog_item(PROJECT_DIR, furniture_id)
        except Exception as exc:
            raise _postgres_catalog_unavailable(exc) from exc
        if item is not None:
            return _normalize_catalog_item(item)
        raise HTTPException(status_code=404, detail="Furniture not found in official catalog.")
    return _get_json_merged_furniture_by_id(furniture_id)


def _external_glb_bytes(furniture: dict) -> bytes:
    resolved = _resolve_external_zip_entry(furniture)
    if resolved is None:
        raise HTTPException(status_code=404, detail="外部匯入模型來源不存在。")
    archive_path, entry_name = resolved
    try:
        with zipfile.ZipFile(archive_path) as archive:
            return archive.read(entry_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="外部匯入模型在 zip 中不存在。")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="外部匯入 zip 無法讀取。")


def _model_response_for_merged_furniture(furniture: dict):
    cloud_url = cloud_model_url(furniture)
    if cloud_url:
        return RedirectResponse(cloud_url, status_code=307)
    if cloudfront_required():
        raise HTTPException(status_code=404, detail=cloud_model_status(furniture)[1])

    if _resolve_external_zip_entry(furniture) is not None:
        payload = _external_glb_bytes(furniture)
        if payload[:4] == b"glTF":
            return Response(content=payload, media_type="model/gltf-binary")

    model_path_text = _get_model_path_for_furniture(furniture)
    try:
        _parse_glb(model_path_text)
        model_path = Path(model_path_text)
        return FileResponse(model_path, media_type="model/gltf-binary", filename=model_path.name)
    except (HTTPException, ValueError, OSError, json.JSONDecodeError):
        remote_url = _remote_glb_url(furniture)
        if remote_url:
            return _remote_glb_response(remote_url)
        raise HTTPException(status_code=404, detail="找不到可載入的 GLB 模型。")


def _get_model_path_for_furniture(furniture: dict) -> str:
    model_path = _resolve_glb_path(furniture)
    if model_path is None:
        raise HTTPException(status_code=404, detail="找不到這件家具對應的 GLB 檔案(dataset/ 未就緒?)。")

    return str(model_path)


def _style_payloads(raw: dict | None = None, surface_catalog: dict | None = None) -> list[dict]:
    raw = raw or {
        "styles": load_runtime_design_styles(PROJECT_DIR, STYLE_PRESENTATION_DB_PATH)
    }
    surface_catalog = surface_catalog or load_surface_catalog()
    styles = []
    for style in raw.get("styles", []):
        surface_profile = _style_surface_profile(surface_catalog, style.get("style_id"))
        styles.append(
            {
                "style_id": style.get("style_id"),
                "style_name_zh": style.get("style_name_zh"),
                "style_name_en": style.get("style_name_en"),
                "core_description_zh": style.get("core_description_zh"),
                "keywords_zh": style.get("keywords_zh", []),
                "main_colors_zh": style.get("main_colors_zh", []),
                "materials_zh": style.get("materials_zh", []),
                "shape_features_zh": style.get("shape_features_zh", []),
                "avoid_elements_zh": style.get("avoid_elements_zh", []),
                "scene_background": style.get("scene_background", {}),
                "wall_recommendations": style.get("wall_recommendations", []),
                "floor_recommendations": style.get("floor_recommendations", []),
                "recommended_wall_floor_pairs_zh": style.get("recommended_wall_floor_pairs_zh", []),
                "surface_profile": surface_profile,
                "wall_surface_ids": surface_profile.get("wall_surface_ids", []),
                "floor_surface_ids": surface_profile.get("floor_surface_ids", []),
                "surface_pairings": surface_profile.get("surface_pairings", []),
                "visual_theme": style.get("visual_theme", {}),
                "palette_hex": style.get("palette_hex", []),
                "stats": style.get("stats", {}),
            }
        )
    return styles


def _catalog_count_summary() -> dict:
    if catalog_provider_mode(PROJECT_DIR) == "postgres":
        try:
            return postgres_catalog_summary(PROJECT_DIR)
        except Exception as exc:
            raise RuntimeCatalogUnavailable("furniture_catalog_summary", exc) from exc
    return _json_catalog_count_summary()


def _clear_catalog_count_summary() -> None:
    _json_catalog_count_summary.cache_clear()


_catalog_count_summary.cache_clear = _clear_catalog_count_summary  # type: ignore[attr-defined]


def _filter_furniture_payload(
    *,
    style: str | None = None,
    group: str | None = None,
    item_type: str | None = None,
    q: str | None = None,
    has_model: bool | None = None,
    color: str | None = None,
    material: str | None = None,
    size: str | None = None,
) -> list[dict]:
    query = (q or "").strip().casefold()
    color_query = _normalize_furniture_facet_value(color, "color").casefold()
    material_query = _normalize_furniture_facet_value(material, "material").casefold()
    items = []
    for item in _furniture_payload_cache():
        if style and not _furniture_matches_style(item, style):
            continue
        if group and item.get("taxonomy_group") != group:
            continue
        if item_type and item.get("normalized_type") != item_type:
            continue
        if has_model is not None and bool(item.get("has_model")) is not has_model:
            continue
        if color_query and _normalize_furniture_facet_value(item.get("color"), "color").casefold() != color_query:
            continue
        if material_query and _normalize_furniture_facet_value(item.get("material"), "material").casefold() != material_query:
            continue
        if size and _furniture_size_bucket(item) != size:
            continue
        if query and query not in _furniture_search_text(item):
            continue
        items.append(item)
    return items


def _type_options_for(
    style: str | None = None,
    group: str | None = None,
    has_model: bool | None = None,
) -> list[dict]:
    counts: dict[str, int] = {}
    for item in _filter_furniture_payload(style=style, group=group, has_model=has_model):
        item_type = item.get("normalized_type")
        if not item_type:
            continue
        counts[item_type] = counts.get(item_type, 0) + 1
    return [
        {
            "type": item_type,
            "count": count,
            "type_name_zh": next(
                (item.get("taxonomy_type_zh") for item in _furniture_payload_cache() if item.get("normalized_type") == item_type),
                item_type,
            ),
        }
        for item_type, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    ]


def _category_groups_for(style: str | None = None, has_model: bool | None = None) -> list[dict]:
    groups: dict[str, dict] = {}
    for item in _filter_furniture_payload(style=style, has_model=has_model):
        group_id = item.get("taxonomy_group") or "soft_decor"
        group = groups.setdefault(
            group_id,
            {"group_id": group_id, "group_name_zh": item.get("taxonomy_group_zh") or "軟裝配件", "types": {}},
        )
        item_type = item.get("normalized_type")
        if not item_type:
            continue
        current = group["types"].setdefault(
            item_type,
            {"type": item_type, "type_name_zh": item.get("taxonomy_type_zh") or item_type, "count": 0},
        )
        current["count"] += 1
    return [
        {**group, "types": sorted(group["types"].values(), key=lambda entry: entry["type_name_zh"])}
        for group in sorted(groups.values(), key=lambda entry: entry["group_name_zh"])
    ]


def build_site_payload(*, include_furniture: bool = True) -> dict:
    if catalog_provider_mode(PROJECT_DIR) == "postgres":
        surface_catalog = load_surface_catalog()
        summary = _catalog_count_summary()
        furniture_payload = list(_furniture_payload_cache()) if include_furniture else []
        return {
            "project": {
                "title": "AI 室內風格與家具配置展示系統",
                "subtitle": "以平面圖、風格條件與既有 GLB 家具資料庫，自動配置並展示 3D 室內場景。",
                "scope": [
                    "上傳平面圖與需求文字",
                    "由風格規則與家具資料庫挑選合適模型",
                    "輸出可在網頁瀏覽的 Three.js 3D 室內場景",
                ],
                "not_scope": "本專題不是直接生成全新 3D 家具模型，而是用既有 GLB 資料庫做風格化配置。",
            },
            "summary": summary,
            "styles": _style_payloads(surface_catalog=surface_catalog),
            "taiwan_style_cards": load_taiwan_style_cards(),
            "furniture": furniture_payload,
            "surface_catalog": surface_catalog,
            "catalog_merge_summary": {
                "input_item_count": summary.get("total_furniture", 0),
                "merged_count": len(furniture_payload),
                "same_item_merged_count": 0,
            },
            "featured_models": [
                item for item in furniture_payload if item["has_model"]
            ][:24],
            "missing_model_count": sum(
                1 for item in furniture_payload if not item["has_model"]
            ),
        }
    raw = load_style_database()
    surface_catalog = load_surface_catalog()
    furniture_items = list(_merged_furniture_catalog_cached())
    furniture_by_id = {}
    for item in furniture_items:
        furniture_by_id[item.get("furniture_id")] = item
        for alias in item.get("merged_furniture_ids", []):
            furniture_by_id[alias] = item

    styles = []
    for style in raw.get("styles", []):
        representative_cards = []
        for furniture_id in style.get("representative_furniture_ids", []):
            furniture = furniture_by_id.get(furniture_id)
            if not furniture:
                continue

            has_model, model_reason = (
                (bool(furniture.get("has_model")), furniture.get("missing_model_reason"))
                if "has_model" in furniture
                else _model_status(furniture)
            )
            representative_cards.append(
                {
                    "furniture_id": furniture_id,
                    "name_en": furniture.get("name_en"),
                    "name_zh_raw": furniture.get("name_zh_raw"),
                    "normalized_type": furniture.get("normalized_type"),
                    "primary_style": furniture.get("primary_style"),
                    "color": furniture.get("color"),
                    "material": furniture.get("material"),
                    "size_cm": sanitize_size_cm(furniture),
                    "has_model": has_model,
                    "missing_model_reason": None if has_model else model_reason,
                    "model_url": _model_url_for_merged_item(furniture) if has_model else None,
                    **_candidate_schema_fields(furniture, has_model),
                }
            )

        surface_profile = _style_surface_profile(surface_catalog, style.get("style_id"))
        styles.append(
            {
                "style_id": style.get("style_id"),
                "style_name_zh": style.get("style_name_zh"),
                "style_name_en": style.get("style_name_en"),
                "core_description_zh": style.get("core_description_zh"),
                "keywords_zh": style.get("keywords_zh", []),
                "main_colors_zh": style.get("main_colors_zh", []),
                "materials_zh": style.get("materials_zh", []),
                "shape_features_zh": style.get("shape_features_zh", []),
                "avoid_elements_zh": style.get("avoid_elements_zh", []),
                "scene_background": style.get("scene_background", {}),
                "wall_recommendations": style.get("wall_recommendations", []),
                "floor_recommendations": style.get("floor_recommendations", []),
                "recommended_wall_floor_pairs_zh": style.get("recommended_wall_floor_pairs_zh", []),
                "surface_profile": surface_profile,
                "wall_surface_ids": surface_profile.get("wall_surface_ids", []),
                "floor_surface_ids": surface_profile.get("floor_surface_ids", []),
                "surface_pairings": surface_profile.get("surface_pairings", []),
                "visual_theme": style.get("visual_theme", {}),
                "palette_hex": style.get("palette_hex", []),
                "stats": style.get("stats", {}),
                "representative_furniture": representative_cards,
            }
        )

    furniture_payload = list(_furniture_payload_cache())

    featured_models = [item for item in furniture_payload if item["has_model"]][:24]
    type_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    styled_count = 0
    for item in furniture_payload:
        item_type = item.get("normalized_type") or "unknown"
        category = item.get("category_label") or item_type
        type_counts[item_type] = type_counts.get(item_type, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        if item.get("style_candidates"):
            styled_count += 1
    summary = {
        **(raw.get("summary", {}) or {}),
        "total_furniture": len(furniture_payload),
        "styled_furniture": styled_count,
        "fallback_furniture": sum(1 for item in furniture_payload if not item.get("style_candidates")),
        "top_types": sorted(type_counts.items(), key=lambda pair: pair[1], reverse=True)[:25],
        "top_categories": sorted(category_counts.items(), key=lambda pair: pair[1], reverse=True)[:25],
    }

    return {
        "project": {
            "title": "AI 室內風格與家具配置展示系統",
            "subtitle": "以平面圖、風格條件與既有 GLB 家具資料庫，自動配置並展示 3D 室內場景。",
            "scope": [
                "上傳平面圖與需求文字",
                "由風格規則與家具資料庫挑選合適模型",
                "輸出可在網頁瀏覽的 Three.js 3D 場景",
            ],
            "not_scope": "本專題不是直接生成全新 3D 家具模型，而是用既有 GLB 資料庫做風格化配置。",
        },
        "summary": summary,
        "styles": styles,
        "taiwan_style_cards": load_taiwan_style_cards(),
        "furniture": furniture_payload,
        "surface_catalog": surface_catalog,
        "catalog_merge_summary": {
            "input_item_count": len(raw.get("furniture", [])),
            "merged_count": len(furniture_payload),
            "same_item_merged_count": 0,
        },
        "featured_models": featured_models,
        "missing_model_count": sum(1 for item in furniture_payload if not item["has_model"]),
    }


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@app.get("/")
def home() -> FileResponse:
    return _page("index.html")


@app.get("/login")
def login_page() -> FileResponse:
    # 頁面本身公開；沒有身分就沒有專案可看，授權由 API 端點負責。
    return FileResponse(
        STATIC_DIR / "login.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/projects")
def projects_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "projects.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/styles")
def styles_page() -> FileResponse:
    return _page("styles.html")


@app.get("/library")
def library_page() -> FileResponse:
    return _page("library.html")


@app.get("/scene")
def scene_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "scene.html",
        headers={"Cache-Control": "no-store"},
    )


def _stored_project(project_id: str) -> dict:
    try:
        return PROJECT_STORE.get_project(project_id)
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
        upload = PROJECT_STORE.get_upload(project_id)
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


# 二進位 DXF 的官方 sentinel（前 18 個位元組即可辨識）。
_BINARY_DXF_SENTINEL = b"AutoCAD Binary DXF"
# 文字 DXF 一定含有「群組碼 0 換行 SECTION」的段落開頭；testdata/dxf 全部 30 檔已驗證通過。
_TEXT_DXF_SECTION_RE = re.compile(r"^[ \t]*0[ \t]*\r?\n[ \t]*SECTION\b", re.MULTILINE)


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


@app.post("/api/projects", status_code=201)
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
    project = PROJECT_STORE.create_project(name=name, notes=notes)
    # 建立者立刻成為 owner，否則專案會是沒人能存取的孤兒。
    user_store().set_project_owner(project["project_id"], user["user_id"])
    return {"project": project}


@app.get("/api/projects/{project_id}")
def get_project(
    project_id: str,
    response: Response,
    _user: dict = Depends(auth_dependencies.project_reader),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"project": _stored_project(project_id)}


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


@app.put("/api/projects/{project_id}/workflow")
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
        project = PROJECT_STORE.update_workflow(
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


@app.post("/api/projects/{project_id}/floorplan", status_code=201)
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
        upload = PROJECT_STORE.save_upload(
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
        "project": PROJECT_STORE.get_project(project_id),
        "upload": {
            "filename": upload["filename"],
            "extension": upload["extension"],
            "mime_type": upload["mime_type"],
            "source_url": f"/api/projects/{project_id}/floorplan/source",
        }
    }


@app.get("/api/projects/{project_id}/floorplan/source")
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


def _public_render_record(record: dict) -> dict:
    payload = {key: value for key, value in record.items() if key != "path"}
    payload["download_url"] = (
        f"/api/projects/{record['project_id']}/renders/{record['render_id']}/png"
    )
    return payload


@app.post("/api/projects/{project_id}/renders", status_code=201)
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
        render, project = PROJECT_STORE.save_render(
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


@app.get("/api/projects/{project_id}/renders")
def list_project_renders(
    project_id: str,
    _user: dict = Depends(auth_dependencies.project_reader),
) -> dict:
    try:
        renders = PROJECT_STORE.list_renders(project_id)
    except KeyError as exc:
        raise HTTPException(
            404, {"code": "project_not_found", "message": "找不到專案。"}
        ) from exc
    return {"renders": [_public_render_record(record) for record in renders]}


@app.get("/api/projects/{project_id}/renders/{render_id}/png")
def download_project_render(
    project_id: str,
    render_id: str,
    _user: dict = Depends(auth_dependencies.project_reader),
) -> FileResponse:
    try:
        render = PROJECT_STORE.get_render(project_id, render_id)
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


@app.get("/api/render-provider/status")
def get_render_provider_status() -> dict:
    # 內建生圖供應者（OpenRouter）啟用時如實回報；舊遠端 URL 設定時維持原契約。
    if direct_image_provider_available():
        return direct_image_provider_status()
    return render_provider_status()


@app.post("/api/projects/{project_id}/render-jobs", status_code=202)
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
            return await run_direct_render_jobs(project_id, payload, PROJECT_STORE)
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


@app.post("/api/projects/{project_id}/floorplan/analyze")
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
                ocr_provider=_floorplan_ocr_provider(),
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

    PROJECT_STORE.update_workflow(
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


@app.get("/api/floorplan/sample/630")
def floorplan_sample_630() -> FileResponse:
    if not SAMPLE_FLOORPLAN_630.is_file():
        raise HTTPException(404, "sample_floorplan_not_found")
    return FileResponse(
        SAMPLE_FLOORPLAN_630,
        media_type="image/png",
        filename="builder_plan_630.png",
    )


@app.get("/api/site-data")
def site_data() -> dict:
    payload = dict(build_site_payload(include_furniture=False))
    payload["furniture"] = []
    payload["featured_models"] = []
    payload["catalog_merge_summary"] = {
        **payload.get("catalog_merge_summary", {}),
        "delivery": "請使用 /api/furniture 分頁取得家具資料。",
    }
    return payload


def catalog_status() -> dict:
    """Describe active catalog providers without exposing credentials."""
    provider_mode = catalog_provider_mode(PROJECT_DIR)
    provider_status = catalog_provider_status(PROJECT_DIR)
    phase4_status = runtime_catalog_status(PROJECT_DIR)
    if provider_mode == "postgres":
        assets = provider_status.get("assets") or {}
        item_count = int(provider_status.get("count") or 0)
        model_count = int(assets.get("model_count") or 0)
        complete_image_item_count = int(assets.get("complete_image_item_count") or 0)
        verified_image_count = sum(
            int(assets.get(key) or 0)
            for key in ("front_image_count", "side_image_count", "angle_45_image_count")
        )
        cloudfront_base_url = os.getenv(
            "ROOMPILOT_CLOUDFRONT_BASE_URL",
            "https://ddgsm1yg3xikc.cloudfront.net",
        ).strip()
        furniture = {
            "provider": "aws_cloudfront",
            "metadata_provider": "kai_postgresql",
            "manifest_ready": (
                bool(provider_status.get("available"))
                and item_count > 0
                and model_count == item_count
            ),
            "manifest_error": (
                None
                if provider_status.get("available") and model_count == item_count
                else provider_status.get("reason") or "postgres_asset_incomplete"
            ),
            "verified_model_count": model_count,
            "cloudfront_base_url": cloudfront_base_url,
        }
        furniture_images = {
            "metadata_provider": "kai_postgresql",
            "manifest_ready": (
                bool(provider_status.get("available"))
                and item_count > 0
                and complete_image_item_count == item_count
            ),
            "manifest_error": (
                None
                if provider_status.get("available")
                and complete_image_item_count == item_count
                else provider_status.get("reason") or "postgres_image_asset_incomplete"
            ),
            "verified_item_count": complete_image_item_count,
            "verified_image_count": verified_image_count,
            "cloudfront_base_url": cloudfront_base_url,
        }
        wall_count = int(phase4_status.get("wall_surface_count") or 0)
        floor_count = int(phase4_status.get("floor_surface_count") or 0)
        style_card_count = int(phase4_status.get("style_card_count") or 0)
    else:
        furniture = dict(manifest_status())
        furniture.pop("mode", None)
        furniture_images = image_manifest_status()
        surfaces = load_surface_catalog().get("surfaces") or []
        wall_count = sum("wall" in (item.get("usage") or []) for item in surfaces)
        floor_count = sum("floor" in (item.get("usage") or []) for item in surfaces)
        style_card_count = len(load_taiwan_style_cards())
    ready = bool(provider_status.get("ready")) and bool(phase4_status.get("ready"))
    return {
        "ready": ready,
        "source_of_truth": "postgresql" if provider_mode == "postgres" else "versioned_files",
        "cache_policy": (
            "database_read_through_no_runtime_file_cache"
            if provider_mode == "postgres"
            else "explicit_offline_file_cache"
        ),
        "catalog_provider": provider_status,
        "runtime_catalogs": phase4_status,
        "furniture": furniture,
        "furniture_images": furniture_images,
        "surfaces": {
            "provider": (
                "local_pending_aws_manifest"
                if provider_mode == "json"
                else phase4_status["provider"]
            ),
            "wall_count": wall_count,
            "floor_count": floor_count,
        },
        "doors": {
            "provider": "procedural_pending_aws_catalog",
            "catalog_count": 0,
        },
        "style_cards": {
            "provider": (
                "local_allowed"
                if provider_mode == "json"
                else phase4_status["provider"]
            ),
            "count": style_card_count,
        },
    }


@app.get("/api/catalog/status")
def catalog_status_api() -> dict:
    return catalog_status()


@app.get("/api/health")
def api_health() -> JSONResponse:
    catalog = catalog_status()
    project_provider = str(getattr(PROJECT_STORE, "provider", "unknown"))
    database = catalog.get("catalog_provider", {}).get("database") or {}
    project_ready = project_provider == "postgres" and bool(
        database.get("project_table_ready")
    )
    formal = (
        catalog_provider_mode(PROJECT_DIR) == "postgres"
        and project_provider == "postgres"
    )
    ready = bool(catalog.get("ready")) and project_ready
    payload = {
        "status": "ready" if ready else ("unavailable" if formal else "offline"),
        "ready": ready,
        "formal": formal,
        "source_of_truth": catalog.get("source_of_truth"),
        "catalog": catalog,
        "project_store": {
            "provider": project_provider,
            "ready": project_ready,
            "table": "roompilot.projects" if project_provider == "postgres" else None,
        },
    }
    return JSONResponse(
        status_code=200 if ready or not formal else 503,
        content=payload,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/engineering")
def engineering_page() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "engineering.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/home-data")
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
        "catalog_status": catalog_status(),
    }


@app.get("/api/styles")
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
        "catalog_status": catalog_status(),
    }


@app.get("/api/scene/bootstrap")
def scene_bootstrap() -> dict:
    return {
        "styles": _style_payloads(),
        "taiwan_style_cards": load_taiwan_style_cards(),
        "surface_catalog": load_surface_catalog(),
        "catalog_status": catalog_status(),
    }


def _json_furniture_catalog_response(
    *,
    style: str | None,
    group: str | None,
    item_type: str | None,
    q: str | None,
    page: int,
    page_size: int,
    has_model: bool | None,
    detail: str,
    color: str | None,
    material: str | None,
    size: str | None,
) -> dict:
    """Explicit/offline JSON implementation kept as a controlled fallback."""
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
    sample_files = _legacy_viewer_models(filtered)
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
        "catalog_status": catalog_status(),
    }


@app.post("/api/furniture/by-ids")
def furniture_by_ids(payload: dict) -> dict:
    """依 item_id 批次取家具，供第 6 步從候選集還原完整資料。

    候選集（``scene_json.furniture_shortlist``）只存 id 與排序分數，圖片、GLB
    與擺放屬性仍在型錄。沒有這條路徑的話前端得對每個房間每個家具類型各打一次
    ``/api/furniture`` 分頁掃描——那正是候選集要消除的成本。

    回傳沿用 ``/api/furniture`` 的正規化與卡片格式，前端不必分兩套解析。
    """
    raw_ids = payload.get("item_ids")
    if not isinstance(raw_ids, list):
        raise HTTPException(422, "item_ids must be a list")
    # 在去重前先擋：去重後才檢查的話，送一百萬個重複 id 仍會先付完整個
    # 正規化成本才被擋下。候選集實測 7 房約 260 筆，1000 已有充足餘裕。
    if len(raw_ids) > 1000:
        raise HTTPException(422, "item_ids exceeds 1000 entries")
    item_ids = list(
        dict.fromkeys(str(value).strip() for value in raw_ids if str(value or "").strip())
    )
    if not item_ids:
        return {"items": [], "missing": [], "catalog_status": catalog_status()}

    detail = str(payload.get("detail") or "card")
    if catalog_provider_mode(PROJECT_DIR) == "postgres":
        try:
            from ..catalog.postgres_repository import get_catalog_items_by_ids

            found = get_catalog_items_by_ids(PROJECT_DIR, item_ids)
        except Exception as exc:
            raise _postgres_catalog_unavailable(exc) from exc
        ordered = [found[item_id] for item_id in item_ids if item_id in found]
    else:
        lookup = {
            str(item.get("furniture_id") or item.get("id")): item
            for item in _furniture_payload_cache()
        }
        ordered = [lookup[item_id] for item_id in item_ids if item_id in lookup]

    items = list(_normalize_catalog_payload(tuple(ordered)))
    resolved = {
        str(item.get("furniture_id") or item.get("id")) for item in items
    }
    return {
        "items": [
            item if detail == "scene" else _furniture_card_payload(item)
            for item in items
        ],
        # 型錄下架或 id 過期時要讓呼叫端知道，而不是靜默少幾筆。
        "missing": [item_id for item_id in item_ids if item_id not in resolved],
        "catalog_status": catalog_status(),
    }


@app.get("/api/furniture")
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
    if postgres_catalog_requested(PROJECT_DIR):
        try:
            result = query_postgres_catalog(
                PROJECT_DIR,
                CatalogQuery(
                    style=style,
                    group=group,
                    item_type=item_type,
                    q=q,
                    page=page,
                    page_size=page_size,
                    has_model=has_model,
                    color=color,
                    material=material,
                    size=size,
                ),
            )
        except Exception as exc:
            raise _postgres_catalog_unavailable(exc) from exc
        # 這條 REST 路徑原本直接吐 SQL 列，繞過 scene/agent/site 都會走的正規化：
        # placement_surface 全缺（第 6 步把壁掛與擺飾當落地家具算碰撞），
        # style_candidates 也沒去重（同一個 style_id 重複灌高排序）。
        items = list(_normalize_catalog_payload(tuple(result.items)))
        sample_files = (
            list(result.model_urls)
            if cloudfront_required()
            else _legacy_viewer_models(items)
        )
        return {
            "items": [
                item if detail == "scene" else _furniture_card_payload(item)
                for item in items
            ],
            "page": result.page,
            "page_size": result.page_size,
            "total": result.total,
            "has_next_page": result.has_next_page,
            "styles": _style_filter_options(),
            "type_options": list(result.type_options),
            "category_groups": list(result.category_groups),
            "filter_options": result.filter_options,
            "furniture": sample_files,
            "catalog_status": catalog_status(),
        }

    return _json_furniture_catalog_response(
        style=style,
        group=group,
        item_type=item_type,
        q=q,
        page=page,
        page_size=page_size,
        has_model=has_model,
        detail=detail,
        color=color,
        material=material,
        size=size,
    )


def _legacy_viewer_models(items: list[dict]) -> list[str]:
    """Feed the retired R3F viewer without advertising blocked local GLBs."""
    if cloudfront_required():
        urls = [
            str(item.get("model_url"))
            for item in items
            if item.get("has_model")
            and str(item.get("model_url") or "").startswith("https://")
        ]
        return list(dict.fromkeys(urls))[:24]
    return (
        sorted(f.name for f in SAMPLE_GLB_DIR.iterdir() if f.suffix.lower() == ".glb")
        if SAMPLE_GLB_DIR.is_dir()
        else []
    )


def _furniture_detail_payload(furniture_id: str) -> dict:
    if postgres_catalog_requested(PROJECT_DIR):
        try:
            item = get_postgres_catalog_item(PROJECT_DIR, furniture_id)
        except Exception as exc:
            raise _postgres_catalog_unavailable(exc) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="Furniture not found in official catalog.")
        item = _normalize_catalog_item(item)
    else:
        item = _furniture_payload_item(_get_json_merged_furniture_by_id(furniture_id))
    payload = dict(item)
    payload.update(
        {
            "merged_furniture_ids": item.get("merged_furniture_ids", []),
            "model_priority_ids": item.get("model_priority_ids", []),
            "catalog_merge_key": item.get("catalog_merge_key"),
            "source_count": item.get("source_count"),
        }
    )
    return payload


@app.on_event("startup")
def warm_catalog_cache() -> None:
    try:
        if catalog_provider_mode(PROJECT_DIR) == "json":
            _furniture_payload_cache()
            build_site_payload()
    except Exception as exc:
        print(f"[RoomPilot] catalog cache warmup skipped: {exc}")


@app.on_event("shutdown")
def close_catalog_connections() -> None:
    close_catalog_pools()
    PROJECT_STORE.close()


@app.get("/api/scene/provider-status")
def scene_provider_status() -> dict:
    return get_openrouter_status()


def _normalize_selection_offers(raw_offers: object) -> dict[str, list[dict]]:
    if not isinstance(raw_offers, dict):
        return {}
    offers: dict[str, list[dict]] = {}
    for room_id, raw_items in raw_offers.items():
        if not isinstance(raw_items, list):
            continue
        normalized_items: list[dict] = []
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            item_type = str(raw_item.get("normalized_type") or raw_item.get("type") or "")
            variant_id = str(raw_item.get("variant_id") or raw_item.get("variantId") or "standard")
            furniture_id = str(
                raw_item.get("furniture_id")
                or raw_item.get("id")
                or f"{room_id}:{item_type}:{variant_id}:{index + 1}"
            )
            if not item_type or not furniture_id:
                continue
            item = dict(raw_item)
            item["furniture_id"] = furniture_id
            item["normalized_type"] = item_type
            item["variant_id"] = variant_id
            item["selection_source"] = str(item.get("selection_source") or "local_rules")
            normalized_items.append(item)
        offers[str(room_id)] = normalized_items
    return offers


def _without_deferred(room_id: str, items: list[dict], requirements: dict) -> list[dict]:
    """濾掉使用者在第 4 步按過暫緩的家具。"""
    requirement = requirements.get(room_id)
    if requirement is None or not requirement.deferred_furniture_ids:
        return items
    return [
        item
        for item in items
        if str(item.get("furniture_id") or "") not in requirement.deferred_furniture_ids
    ]


def _selection_llm_context(context: dict | None) -> dict | None:
    """只把與選件有關的問卷結論送進提示。

    完整 ``room_requirements`` 含牆面、色票與逐面材質，動輒數十 KB；逐房
    需求已由 ``requirements_from_context`` 收斂後隨房間送出，這裡再塞一次
    只會稀釋規則並拖慢呼叫。
    """
    if not isinstance(context, dict):
        return None
    keep = ("basic_answers", "visual_preferences")
    trimmed = {key: context[key] for key in keep if context.get(key)}
    return trimmed or None


def _selection_response(
    selected: dict[str, list],
    *,
    source: str,
    model: str | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "source": source,
        "model": model,
        "warnings": warnings or [],
        "rooms": [
            {
                "room_id": room_id,
                "items": [
                    {
                        **entry.item,
                        "count": entry.count,
                        "selection_source": entry.item.get("selection_source") or source,
                    }
                    for entry in entries
                ],
            }
            for room_id, entries in selected.items()
        ],
    }


@app.post("/api/agent/furniture/select")
async def agent_furniture_select(payload: dict) -> dict:
    """Server-side furniture selection gate for Yen selection discipline."""
    raw_rooms = payload.get("rooms") or []
    if not isinstance(raw_rooms, list):
        raise HTTPException(status_code=422, detail="rooms must be a list")
    rooms = []
    for room in raw_rooms:
        if not isinstance(room, dict):
            continue
        room_type = str(room.get("room_type") or room.get("type") or "")
        if room_type in {"default", "unknown", "other"}:
            room_type = ""
        rooms.append({
            **room,
            "room_id": str(room.get("room_id") or room.get("id") or ""),
            "room_type": room_type,
        })
    offers = _normalize_selection_offers(payload.get("offers"))
    style_id = payload.get("style_id")
    context = payload.get("context") if isinstance(payload.get("context"), dict) else None
    llm_selection = payload.get("llm_selection")
    warnings: list[str] = []

    # 逐房問卷需求是兩條路徑共用的輸入：LLM 走提示，本地規則走確定性挑選。
    requirements = requirements_from_context(context)
    preselected = preselected_from_requirements(rooms, offers, requirements)

    # payload 帶 llm_selection 時視為外部已算好的結果，只做驗證；否則由
    # 伺服器自己呼叫 OpenRouter，前端不需要也不應該持有 API 金鑰。
    complete = (
        (lambda _messages: ("payload/llm_selection", llm_selection))
        if isinstance(llm_selection, dict)
        else selection_complete_fn()
    )

    if complete is not None:
        try:
            selected, model = request_selections(
                rooms,
                offers,
                str(style_id) if style_id else None,
                complete=complete,
                preselected=preselected,
                context=_selection_llm_context(context),
                requirements=requirements,
            )
            return _selection_response(selected, source="openrouter", model=model)
        except (SelectionParseError, SelectionUnavailableError) as exc:
            warnings.append(f"LLM 選擇未通過規則驗證，已改用本地規則：{exc}")

    try:
        selected = parse_selections(
            local_selection_raw(rooms, offers, requirements),
            rooms,
            offers,
            preselected=preselected,
            requirements=requirements,
        )
        return _selection_response(selected, source="local_rules", warnings=warnings)
    except SelectionParseError as exc:
        warnings.append(f"本地規則無法完整驗證候選家具，已保留第一批候選：{exc}")
        # 連驗證都過不了時仍守住一條線：使用者暫緩的家具在任何路徑都不回填。
        return {
            "source": "local_rules_unvalidated",
            "model": None,
            "warnings": warnings,
            "rooms": [
                {
                    "room_id": room_id,
                    "items": [
                        {
                            **item,
                            "count": int(item.get("count") or 1),
                            "selection_source": item.get("selection_source") or "local_rules_unvalidated",
                        }
                        for item in _without_deferred(room_id, items, requirements)[:8]
                    ],
                }
                for room_id, items in offers.items()
                if items
            ],
        }


@app.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    client_brief = _payload_mapping(payload, "client_brief")
    brief_space = _payload_mapping(client_brief, "space")
    brief_style = _payload_mapping(client_brief, "style")
    brief_occupants = _payload_mapping(client_brief, "occupants")
    test2_questionnaire = _payload_mapping(payload, "questionnaire")

    questionnaire = {
        "space_type": payload.get("space_type") or brief_space.get("type") or "living_room",
        "style_preference": payload.get("style_preference") or (brief_style.get("preferred") or ["auto"])[0],
        "style_card_id": payload.get("style_card_id"),
        "required_furniture": payload.get("required_furniture", []),
        "selected_furniture": payload.get("selected_furniture", []),
        "selected_furniture_exact": payload.get("selected_furniture_exact") is True,
        "custom_furniture": payload.get("custom_furniture", []),
        "preferred_colors": payload.get("preferred_colors") or brief_style.get("colors", []),
        "custom_colors": payload.get("custom_colors", []),
        "personal_notes": payload.get("personal_notes", ""),
        "test2_questionnaire": test2_questionnaire,
        "keep_window_clear": bool(payload.get("keep_window_clear", "keep_window_clear" in client_brief.get("constraints", []))),
        "keep_door_clear": bool(payload.get("keep_door_clear", "keep_door_clear" in client_brief.get("constraints", []))),
        "need_storage": bool(payload.get("need_storage", "storage" in client_brief.get("needs", []))),
        "prefer_low_saturation": bool(payload.get("prefer_low_saturation", "low_saturation" in brief_style.get("colors", []))),
        "client_brief": client_brief,
        "occupants": brief_occupants,
        "preferred_materials": brief_style.get("materials", []),
        "floorplan_filename": payload.get("floorplan_filename"),
        "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
        "layout_json": payload.get("layout_json"),
        "floorplan_editor": payload.get("floorplan_editor"),
        "wall_option": payload.get("wall_option", "auto"),
        "floor_option": payload.get("floor_option", "auto"),
        "furniture_random_seed": payload.get("furniture_random_seed"),
    }

    scene_payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=(
            _payload_number(payload, "room_width_cm", minimum=0)
            or _payload_number(brief_space, "width_cm", minimum=0)
            or 420
        ),
        room_depth_cm=(
            _payload_number(payload, "room_depth_cm", minimum=0)
            or _payload_number(brief_space, "depth_cm", minimum=0)
            or 360
        ),
    )
    return {
        **scene_payload,
        "scene_json": deepcopy(scene_payload),
    }


def _repair_ready_items(objects: list) -> tuple[list[dict], dict[str, str | None]]:
    """把前端場景物件轉成擺放紀律看得懂的形狀。

    第 6 步的 scene_objects 用 ``furniture_id`` 當「這一件」的身分，型錄 id 放在
    ``catalog_furniture_id``；Yen 的 ``resolve_placements`` 反過來——``instance_id``
    是身分，``furniture_id`` 要能和候選池比對才換得了小款。這裡換過去，修完再換
    回來，前端拿到的身分才不會在換小款時整個換掉。
    """
    original_catalog: dict[str, str | None] = {}
    items: list[dict] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        instance_id = str(obj.get("furniture_id") or "")
        catalog_id = obj.get("catalog_furniture_id")
        original_catalog[instance_id] = str(catalog_id) if catalog_id else None
        items.append({
            **obj,
            "instance_id": instance_id,
            "furniture_id": str(catalog_id or instance_id),
        })
    return items, original_catalog


def _restore_scene_identity(objects: list, original_catalog: dict[str, str | None]) -> list[dict]:
    """把 instance_id 換回 furniture_id，換過小款的則帶上新的型錄 id。"""
    restored: list[dict] = []
    for obj in objects:
        instance_id = str(obj.get("instance_id") or "")
        if not instance_id:
            restored.append(obj)
            continue
        catalog_id = str(obj.get("furniture_id") or "")
        item = dict(obj)
        item.pop("instance_id", None)
        item["furniture_id"] = instance_id
        item["catalog_furniture_id"] = (
            catalog_id if catalog_id and catalog_id != instance_id
            else original_catalog.get(instance_id)
        )
        restored.append(item)
    return restored


@app.post("/api/scene/layout")
async def scene_layout(payload: dict) -> dict:
    """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

    傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
    scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
    放不下的家具走與 /api/scene/generate 相同的擺放紀律:換小、移除或升級人工。
    """
    objects = _payload_sequence(payload, "scene_objects")
    editor_floorplan = payload.get("floorplan_editor")
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, room = floorplan_from_editor_payload(editor_floorplan)
    else:
        floorplan = _payload_mapping(payload, "floorplan")
        room = room_from_payload(floorplan)
    placement_room_id = payload.get("placement_room_id")
    placement_variant = str(payload.get("placement_variant") or "A").upper()
    if placement_variant not in {"A", "B"}:
        placement_variant = "A"
    place_boundary = (
        _region_boundary_by_id(floorplan, room, placement_room_id)
        or _largest_region_boundary(floorplan, room)
    )
    placement_preferences = _payload_mapping(payload, "placement_preferences")
    _margin, _clearance, applied_preferences, ignored_preferences = (
        resolve_placement_preferences(placement_preferences)
    )

    items, original_catalog = _repair_ready_items(objects)

    def place(working_items: list[dict]) -> list[dict]:
        return generate_layout(
            room.width,
            room.depth,
            working_items,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=place_boundary,
            floorplan=floorplan,
            placement_variant=placement_variant,
            placement_preferences=placement_preferences,
        )

    scene_objects = place(items)
    report: list[dict] = []
    if any(obj.get("placement_failed") for obj in scene_objects):
        # 第一次擺放失敗時才付出重算成本。這裡不修的話,第 6 步換上放不下的
        # 家具只會留下一張紅色待處理卡,永遠等不到自動換小款。
        protected_ids = {
            str(item.get("furniture_id"))
            for item in items
            if item.get("furniture_id")
            and (
                item.get("user_specified")
                or item.get("user_required")
                or item.get("position_locked")
            )
        }
        try:
            pool = [
                candidate
                for candidate in _furniture_payload_cache()
                if not candidate.get("size_is_implausible")
            ]
        except RuntimeCatalogUnavailable:
            # 型錄暫時讀不到就只回報,不要因為換小款失敗而擋掉整次重排。
            pool = []
        scene_objects, _items, report = resolve_placements(
            scene_objects,
            items,
            pool,
            engine_place_fn=place,
            protected_ids=protected_ids,
        )

    return {
        "floorplan": floorplan,
        "scene_objects": _restore_scene_identity(scene_objects, original_catalog),
        "placement_resolution_report": report,
        # 明說哪些偏好真的進了引擎、哪些還沒有對應動作，避免整條 no-op 又沒人發現。
        "placement_preferences_applied": applied_preferences,
        "placement_preferences_ignored": ignored_preferences,
    }


# 自動軟裝的候選型別。地毯原本只認 large-medium-rug 與 runner-small-rug，
# 型錄實際有 7 種地面覆蓋物，另外 3 種室內地毯一直選不到。
# outdoor-rug 與 door-mat 刻意排除：戶外地毯與門口踏墊不是室內軟裝，
# 自動配置把踏墊放進臥室比少放一張地毯糟糕。
_AUTO_DECOR_TYPES = {
    "rug": (
        "rug",
        "large-medium-rug",
        "runner-small-rug",
        "handmade-rug",
        "round-rug",
    ),
    "plant": ("flower-pots-planter",),
    "light": ("floor-lamp", "lamp"),
}


_AUTO_DECOR_LABELS = {
    "rug": "地毯",
    "plant": "植栽",
    "light": "燈具",
}


def _auto_decor_catalog_item(
    role: str,
    style_id: str | None,
    excluded_ids: set[str] | None = None,
    max_footprint_cm: tuple[float, float] | None = None,
) -> dict:
    requested_types = _AUTO_DECOR_TYPES[role]
    excluded_ids = excluded_ids or set()
    candidates = [
        item
        for item in _furniture_payload_cache()
        if item.get("normalized_type") in requested_types
        and item.get("has_model")
        and item.get("model_url")
        and str(item.get("furniture_id")) not in excluded_ids
    ]
    if role == "rug" and max_footprint_cm:
        max_width, max_depth = sorted(max_footprint_cm, reverse=True)
        fitting = []
        for item in candidates:
            size = item.get("size_cm") or {}
            item_width, item_depth = sorted(
                (float(size.get("width") or 0), float(size.get("depth") or 0)),
                reverse=True,
            )
            if item_width <= max_width and item_depth <= max_depth:
                fitting.append(item)
        if fitting:
            candidates = fitting
    # 少一個角色的 GLB 不該讓整間房的軟裝一起中止：地毯、植栽照樣放得下就該放。
    # 回 None 由呼叫端跳過並記進 decor_summary.skipped，前端再據此告知使用者。
    if not candidates:
        return None

    def score(item: dict) -> tuple[int, float]:
        style_match = item.get("primary_style") == style_id or any(
            candidate.get("style_id") == style_id
            for candidate in item.get("style_candidates", [])
            if isinstance(candidate, dict)
        )
        return (1 if style_match else 0, float(item.get("style_confidence") or 0))

    selected = dict(
        max(
            candidates,
            key=lambda item: (
                *score(item),
                str(item.get("furniture_id") or ""),
            ),
        )
    )
    selected["auto_decor_role"] = role
    selected["position_locked"] = False
    return selected


_CURTAIN_MODEL_PATH = "models/roompilot-curtain.glb"


def _curtain_catalog_item() -> dict | None:
    """布簾是固定假想品項，不走型錄查找。

    以前它無條件宣告 model_url 指向 /static/models/roompilot-curtain.glb，但那個檔案
    不在 repo 裡（static/ 底下沒有任何 .glb），所以每次自動軟裝都保證產生一個 404，
    3D 只能靠白色替代物兜底。與其硬塞一個壞掉的品項，不如照其他軟裝角色的作法：
    檔案不存在就回 None，由呼叫端列進 decor_summary.skipped 說明原因。
    """
    if not (STATIC_DIR / _CURTAIN_MODEL_PATH).is_file():
        return None
    return {
        "furniture_id": "roompilot-auto-curtain",
        "normalized_type": "curtain",
        "name_zh_raw": "自動配置布簾",
        "size_cm": {"width": 240, "depth": 12, "height": 240},
        "model_url": f"/static/{_CURTAIN_MODEL_PATH}",
        "has_model": True,
        "auto_decor_role": "curtain",
        "position_locked": False,
    }


@app.post("/api/scene/decorate")
async def scene_decorate(payload: dict) -> dict:
    """依風格加入軟裝，所有最終座標仍由家具引擎決定。"""
    _payload_sequence(payload, "scene_objects")
    editor_floorplan = payload.get("floorplan_editor")
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, room = floorplan_from_editor_payload(editor_floorplan)
    else:
        floorplan = _payload_mapping(payload, "floorplan")
        room = room_from_payload(floorplan)

    placement_room_id = payload.get("placement_room_id")
    place_boundary = (
        _region_boundary_by_id(floorplan, room, placement_room_id)
        or _largest_region_boundary(floorplan, room)
    )
    region = next(
        (
            item
            for item in floorplan.get("room_regions", [])
            if str(item.get("room_id")) == str(placement_room_id)
        ),
        {},
    )
    confirmed_room = payload.get("room") if isinstance(payload.get("room"), dict) else {}
    room_type = str(
        region.get("room_type")
        or confirmed_room.get("type")
        or confirmed_room.get("room_type")
        or "default"
    )
    existing = [dict(item) for item in payload.get("scene_objects", [])]
    room_id = str(placement_room_id or "default")
    # 舊版本的 default 軟裝與目前房間的軟裝都先移除，確保每次重跑是重算而非累加。
    existing = [
        item
        for item in existing
        if not item.get("auto_decor_role")
        or str(item.get("auto_decor_room_id") or "default") not in {room_id, "default"}
    ]
    room_items = []
    for item in existing:
        assigned_room_id = item.get("placement_room_id") or item.get("auto_decor_room_id")
        if assigned_room_id:
            if str(assigned_room_id) == room_id:
                room_items.append(item)
            continue
        if scene_object_in_boundary(item, room, place_boundary):
            room_items.append(item)
    room_types = {
        str(item.get("normalized_type") or "")
        for item in room_items
    }
    rug_anchors = {"sofa", "sofa-bed", "bed", "bed-frame", "dining-table"}
    companion_anchors = rug_anchors | {"desk", "armchair"}
    requested_roles = []
    if room_types & companion_anchors:
        requested_roles.append("light")
    if room_types & rug_anchors:
        requested_roles.append("rug")
    if room_type == "balcony" or (
        room_type in {"living_room", "dining_room", "default"}
        and room_types & companion_anchors
    ):
        requested_roles.append("plant")
    if curtain_window_hint(
        floorplan,
        room_width_cm=room.width,
        room_depth_cm=room.depth,
        boundary=place_boundary,
    ) and room_type in {"living_room", "bedroom", "dining_room", "default"}:
        requested_roles.append("curtain")

    additions: list[dict] = []
    skipped_roles: list[dict] = []
    if "curtain" in requested_roles:
        curtain = _curtain_catalog_item()
        if curtain is None:
            skipped_roles.append(
                {
                    "role": "curtain",
                    "label": "布簾",
                    "reason": "布簾模型檔尚未進版控，本次略過（3D 不會出現缺檔的替代方塊）。",
                }
            )
        else:
            additions.append(curtain)
    used_ids = {str(item.get("furniture_id")) for item in existing}
    boundary_width_cm = boundary_depth_cm = 0.0
    if place_boundary is not None:
        min_x, min_y, max_x, max_y = place_boundary.bounds
        boundary_width_cm = max((max_x - min_x) - 20, 0)
        boundary_depth_cm = max((max_y - min_y) - 20, 0)
    rug_anchor = next(
        (
            item
            for item in room_items
            if str(item.get("normalized_type") or "") in rug_anchors
        ),
        None,
    )
    rug_anchor_size = (rug_anchor or {}).get("size_cm") or {}
    rug_max_footprint = (
        min(boundary_width_cm, float(rug_anchor_size.get("width") or boundary_width_cm)),
        min(boundary_depth_cm, float(rug_anchor_size.get("depth") or boundary_depth_cm)),
    )
    for role in ("rug", "plant", "light"):
        if role in requested_roles:
            addition = _auto_decor_catalog_item(
                role,
                payload.get("style"),
                used_ids,
                rug_max_footprint if role == "rug" else None,
            )
            if addition is None:
                skipped_roles.append(
                    {
                        "role": role,
                        "label": _AUTO_DECOR_LABELS[role],
                        "reason": f"型錄中沒有可用的{_AUTO_DECOR_LABELS[role]} GLB，本次略過。",
                    }
                )
                continue
            additions.append(addition)
            used_ids.add(str(addition.get("furniture_id")))
    for item in additions:
        item["auto_decor_room_id"] = room_id
    rug = next((item for item in additions if item["auto_decor_role"] == "rug"), None)
    if rug is not None:
        rug["placement_relation"] = {
            "kind": "under",
            "target_types": ["sofa", "sofa-bed", "bed", "bed-frame", "dining-table"],
        }
    for item in additions:
        if item["auto_decor_role"] in {"plant", "light"} and not (
            room_type == "balcony" and item["auto_decor_role"] == "plant"
        ):
            item["placement_relation"] = {
                "kind": "adjacent",
                "target_types": [
                    "sofa", "sofa-bed", "bed", "bed-frame", "desk",
                    "dining-table", "armchair",
                ],
            }

    scene_objects = generate_layout(
        room.width,
        room.depth,
        [*existing, *additions],
        room=room,
        regions_boundary=_regions_boundary(floorplan, room),
        place_boundary=place_boundary,
        floorplan=floorplan,
        preserve_existing_count=len(existing),
    )
    # 自動軟裝放不下就不硬塞，也不把失敗標記留在 3D 場景裡。
    scene_objects = [
        item
        for item in scene_objects
        if not (item.get("auto_decor_role") and item.get("placement_failed"))
    ]
    return {
        "scene_objects": scene_objects,
        "decor_summary": {
            "requested": requested_roles,
            "placed": [
                item["auto_decor_role"]
                for item in scene_objects
                if item.get("auto_decor_role") and not item.get("placement_failed")
            ],
            "skipped": skipped_roles,
            "engine": "furniture_engine",
        },
    }


@app.post("/api/scene/validate")
async def scene_validate(payload: dict) -> dict:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    editor_floorplan = payload.get("floorplan_editor")
    floorplan = _payload_mapping(payload, "floorplan") or None
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, _ = floorplan_from_editor_payload(editor_floorplan)
    # 帶上偏好,拖曳驗證才會和 /api/scene/layout 用同一份禁區規則。
    return validate_single_placement(
        floorplan,
        _payload_mapping(payload, "item"),
        _payload_sequence(payload, "others"),
        _payload_mapping(payload, "placement_preferences"),
    )


@app.get("/api/furniture/{furniture_id}/model")
def furniture_model(furniture_id: str):
    furniture = _get_merged_furniture_by_id(furniture_id)
    direct_url = str(furniture.get("model_url") or "").strip()
    if direct_url.startswith(("https://", "http://")):
        return RedirectResponse(direct_url, status_code=307)
    return _model_response_for_merged_furniture(furniture)


@app.get("/api/furniture/{furniture_id}/model.gltf")
def furniture_model_gltf(furniture_id: str) -> JSONResponse:
    if cloudfront_required():
        raise HTTPException(410, "CloudFront 模式不提供本機 glTF 拆解端點。")
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    return JSONResponse(_gltf_payload_for_web(model_path_text, furniture_id))


@app.get("/api/furniture/{furniture_id}/buffer.bin")
def furniture_model_buffer(furniture_id: str) -> Response:
    if cloudfront_required():
        raise HTTPException(410, "CloudFront 模式不提供本機 GLB buffer。")
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    _, binary_payload = _parse_glb(model_path_text)
    return Response(content=binary_payload, media_type="application/octet-stream")


@app.get("/api/furniture/{furniture_id}/images/{image_index}")
def furniture_model_image(furniture_id: str, image_index: int) -> Response:
    if cloudfront_required():
        raise HTTPException(410, "CloudFront 模式不提供本機 GLB 圖片。")
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    image_bytes, mime_type = _image_bytes_from_glb(model_path_text, image_index)
    return Response(content=image_bytes, media_type=mime_type)


# ---------------------------------------------------------------------------
# 以下路由自原 app/backend/main.py 移植,原本供已移除的 frontend3d 原型使用。
# /api/floorplan/analyze 仍由 frontend/ 呼叫;其餘只剩測試在用,
# 待確認無外部消費者後可一併移除。
# ---------------------------------------------------------------------------


@app.get("/api/plans")
def plans() -> dict:
    return {"plans": list_plans(str(PLAN_DIR))}


@app.get("/api/plan")
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


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    scale_m: float | None = Query(None, gt=0, le=500),
    thickness: float = Query(0.18, gt=0, le=2),
    height: float = Query(2.7, gt=0, le=10),
):
    data = await _read_upload(file, MAX_FLOORPLAN_BYTES, "平面圖")
    try:
        return parse_dxf_bytes(data, file.filename or "upload.dxf", scale_m, thickness, height)
    except Exception as e:
        raise HTTPException(422, f"parse failed: {e}")


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


@app.post("/api/floorplan/analyze")
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
    provider = _floorplan_ocr_provider()
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


@app.post("/api/floorplan/confirm")
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


@app.get("/api/sample-furniture")
def sample_furniture() -> dict:
    if cloudfront_required():
        return {
            "furniture": [],
            "provider": "aws_cloudfront",
            "message": "請由家具型錄取得已驗證的 CloudFront model_url。",
        }
    files = (
        sorted(f for f in SAMPLE_GLB_DIR.iterdir() if f.suffix.lower() == ".glb")
        if SAMPLE_GLB_DIR.is_dir()
        else []
    )
    return {"furniture": [f.name for f in files]}


@app.get("/api/furniture/{name}")
def sample_furniture_file(name: str):
    if not name.lower().endswith(".glb"):
        return _furniture_detail_payload(name)
    if cloudfront_required():
        raise HTTPException(410, "CloudFront 模式不提供本機範例 GLB。")
    path = SAMPLE_GLB_DIR / Path(name).name
    if not path.is_file():
        raise HTTPException(404, f"furniture not found: {name}")
    return FileResponse(path, media_type="model/gltf-binary")
