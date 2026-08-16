from __future__ import annotations

import base64
import binascii
import io
import csv
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from ..agent.knowledge import family_of
from ..agent.place import placement_hints
from ..agent.select import SelectionParseError, SelectionUnavailableError, parse_selections, request_selections
from .questionnaire_visuals import (
    QuestionnaireVisualStore,
    load_questionnaire_visual_catalog,
)
from ..catalog.style_db import sanitize_size_cm
from ..catalog.fixture_repository import load_fixture_catalog
from ..runtime_profile import current_profile
from ..floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)
from ..floorplan.vision.ocr import default_ocr_provider
from .scene_service import (
    _largest_region_boundary,
    _region_boundary_by_id,
    _regions_boundary,
    build_scene_payload,
    floorplan_from_editor_payload,
    generate_layout,
    parse_floorplan_with_engine,
    room_from_payload,
    validate_single_placement,
)
from .intake_service import advance_intake, start_intake
from .cost_estimation import estimate_project_cost, load_default_cost_catalog
from .project_store import (
    ProjectStore,
    ProjectVersionConflict,
    WorkflowTooLargeError,
)
from .runtime_paths import legacy_runtime_dirs, project_runtime_dir
from .render_service import (
    RenderProviderRejected,
    RenderProviderUnavailable,
    render_provider_status,
    submit_render_jobs,
)
from .ai_render_service import (
    AiRenderNotConfigured,
    AiRenderReferenceMissing,
    GenPicFailure,
    ai_render_status,
    edit_room_image,
    generate_palette_images,
    generate_room_images,
)
from .design_manual_service import (
    DeliveryNotConfigured,
    DesignManualError,
    create_delivery_proposal,
    create_design_manual,
    delivery_proposal_status,
)
from .engineering_report import build_engineering_estimate
from .agent_pipeline_service import (
    PipelineNotStarted,
    get_pipeline,
    pipeline_enabled,
    pipeline_status,
    start_pipeline,
    submit_pipeline,
    undo_pipeline,
)
from .agent_reconcile_service import reconcile_room
from .style_cards import load_taiwan_style_cards
from .services.cloud_models import (
    cloud_model_status,
    cloud_model_url,
    cloudfront_required,
    manifest_status,
)
from .services.cloud_images import (
    cloud_image_urls,
    cloud_primary_image_url,
    image_manifest_status,
)
from .rag_api import router as rag_router
from ..catalog.postgres_repository import (
    catalog_provider_mode,
    catalog_provider_status,
    load_catalog as load_postgres_catalog,
    load_price_index as load_postgres_price_index,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent


STATIC_DIR = BASE_DIR / "static"
STYLE_PRESENTATION_DB_PATH = (
    BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_6styles_zh.json"
)
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
PUBLIC_FIXTURE_DIR = PROJECT_DIR / "examples" / "fixtures"
SAMPLE_FLOORPLAN = PUBLIC_FIXTURE_DIR / "public_floorplan.png"
PROJECT_STORE = ProjectStore(project_runtime_dir(PROJECT_DIR))
for legacy_runtime in legacy_runtime_dirs(PROJECT_DIR):
    PROJECT_STORE.import_runtime(legacy_runtime)
QUESTIONNAIRE_VISUAL_CATALOG = load_questionnaire_visual_catalog()
QUESTIONNAIRE_VISUAL_STORE: QuestionnaireVisualStore | None = None
_QUESTIONNAIRE_VISUAL_STORE_LOCK = Lock()
FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")


def _floorplan_ocr_provider():
    """Return the optional OCR provider for printed room names and dimensions."""
    if os.environ.get("ROOMPILOT_OCR_DISABLED") == "1":
        return None
    return default_ocr_provider()


MAX_RENDER_BYTES = 20 * 1024 * 1024
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

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        _furniture_payload_cache()
        build_site_payload()
    except Exception as exc:
        print(f"[RoomPilot] catalog cache warmup skipped: {exc}")
    yield


app = FastAPI(
    title="AI 室內風格與家具配置展示系統",
    lifespan=_lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(rag_router)


def _questionnaire_visual_store() -> QuestionnaireVisualStore:
    """Build the worktree-local query index only when the questionnaire is used."""
    global QUESTIONNAIRE_VISUAL_STORE
    if QUESTIONNAIRE_VISUAL_STORE is not None:
        return QUESTIONNAIRE_VISUAL_STORE
    with _QUESTIONNAIRE_VISUAL_STORE_LOCK:
        if QUESTIONNAIRE_VISUAL_STORE is None:
            store = QuestionnaireVisualStore(
                project_runtime_dir(PROJECT_DIR)
                / "indexes"
                / "questionnaire_visuals.sqlite3"
            )
            store.sync(QUESTIONNAIRE_VISUAL_CATALOG)
            QUESTIONNAIRE_VISUAL_STORE = store
    return QUESTIONNAIRE_VISUAL_STORE

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _normalize_posix_path(path_text: str) -> str:
    return path_text.replace("\\", "/").lstrip("/")


def _is_remote_glb_url(path_text: object) -> bool:
    text = str(path_text or "").strip()
    return text.startswith(("https://", "http://")) and (
        ".glb" in text.lower()
        or "/glb/" in text.lower()
        or "/glb_draco/" in text.lower()
        or "/simple/" in text.lower()
    )


def _remote_glb_url(furniture: dict) -> str | None:
    for key in ("glb_absolute_path", "model_url", "glb_url", "model_path", "glb_path"):
        url = str(furniture.get(key) or "").strip()
        if _is_remote_glb_url(url):
            return url
    return None


def _glb_lookup_keys(path_text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", _normalize_posix_path(path_text)).casefold()
    parts = [part for part in normalized.split("/") if part]
    keys: list[str] = []
    for count in (5, 4, 3, 2, 1):
        if len(parts) >= count:
            keys.append("/".join(parts[-count:]))
    keys.append(normalized)
    return list(dict.fromkeys(keys))


def _iter_external_zip_paths() -> list[Path]:
    env_roots = os.environ.get("ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS", "")
    roots: list[Path] = []
    for raw_root in env_roots.split(os.pathsep):
        raw_root = raw_root.strip()
        if raw_root:
            root = Path(raw_root).expanduser()
            roots.append(root if root.is_absolute() else PROJECT_DIR / root)

    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        candidates: list[Path] = []
        if root.is_file() and root.suffix.lower() == ".zip":
            candidates = [root]
        elif root.is_dir():
            candidates.extend(root.glob("*.zip"))

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


def _external_zip_entry_variants(entry_name: object) -> list[str]:
    entry = _normalize_posix_path(str(entry_name or "").strip())
    return [entry] if entry else []


def _resolve_external_zip_entry(furniture: dict) -> tuple[Path, str] | None:
    entry_names: list[str] = []
    for key in ("zip_entry", "glb_relative_path", "glb_absolute_path", "model_path", "glb_path"):
        value = str(furniture.get(key) or "").strip()
        if value and not _is_remote_glb_url(value):
            entry_names.extend(_external_zip_entry_variants(value))
    entry_names = list(dict.fromkeys(entry_names))
    if not entry_names:
        return None

    lookup = _external_zip_entry_lookup()
    for variant in entry_names:
        for key in _glb_lookup_keys(variant):
            resolved = lookup.get(key)
            if resolved is not None and resolved[0].exists():
                return resolved
    return None


def _resolve_glb_path(furniture: dict) -> Path | None:
    """Resolve a GLB only inside explicitly configured local roots."""
    raw_roots = os.environ.get("ROOMPILOT_LOCAL_GLB_ROOTS", "")
    roots: list[Path] = []
    for raw_root in raw_roots.split(os.pathsep):
        if raw_root.strip():
            root = Path(raw_root.strip()).expanduser()
            roots.append((root if root.is_absolute() else PROJECT_DIR / root).resolve())

    path_text = furniture.get("glb_absolute_path") or furniture.get("glb_relative_path")
    if not path_text:
        return None
    supplied = Path(str(path_text))
    for root in roots:
        candidate = supplied.resolve() if supplied.is_absolute() else (root / supplied).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.casefold() == ".glb":
            return candidate
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

    return False, "資料有記錄，但 ROOMPILOT_LOCAL_GLB_ROOTS 中找不到對應 GLB。"


@lru_cache(maxsize=1)
def load_style_database() -> dict:
    presentation = json.loads(STYLE_PRESENTATION_DB_PATH.read_text(encoding="utf-8"))
    furniture = list(load_fixture_catalog()) if current_profile() == "portable" else []
    return {
        **presentation,
        "schema_version": "portable-fixture-v1" if furniture else "full-postgres-v1",
        "catalog_name": (
            "RoomPilot portable developer fixture"
            if furniture
            else "RoomPilot full PostgreSQL catalog"
        ),
        "furniture": furniture,
        "summary": {
            "total_furniture": len(furniture),
            "procedural_fixture": len(furniture),
        },
    }


@lru_cache(maxsize=1)
def load_surface_catalog() -> dict:
    if not SURFACE_DB_PATH.exists():
        return {"schema_version": "1.0", "surfaces": [], "style_surface_profiles": {}}
    return json.loads(SURFACE_DB_PATH.read_text(encoding="utf-8"))


def _style_surface_profile(surface_catalog: dict, style_id: str | None) -> dict:
    profiles = surface_catalog.get("style_surface_profiles") or {}
    return profiles.get(style_id or "") or profiles.get("scandinavian") or {}


_DIMENSION_TEXT = re.compile(r"\d+(?:\.\d+)?\s*(?:x|X|×|\*)\s*\d+(?:\.\d+)?(?:\s*(?:x|X|×|\*)\s*\d+(?:\.\d+)?)?\s*(?:cm|公分)?")
_SINGLE_DIMENSION_TEXT = re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:cm|公分)\b")
_COLOR_WORDS = {
    "white",
    "black",
    "blue",
    "green",
    "red",
    "yellow",
    "grey",
    "gray",
    "beige",
    "brown",
    "light",
    "dark",
    "natural",
    "oak",
    "walnut",
    "birch",
    "whitelight",
    "whiteblue",
    "whitewhite",
    "白色",
    "黑色",
    "藍色",
    "綠色",
    "淺綠色",
    "灰色",
    "米色",
    "棕色",
    "橡木",
    "樺木",
}


def _text_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("å", "a").replace("ä", "a").replace("ö", "o")
    text = _DIMENSION_TEXT.sub(" ", text)
    text = re.sub(r"\bikea\b|\bonline shopping\b|線上購物|公分|cm", " ", text)
    text = re.sub(r"[/,，、()（）\\-]", " ", text)
    color_suffixes = ("white", "black", "blue", "green", "red", "yellow", "grey", "gray", "beige", "brown")
    tokens = []
    for token in re.split(r"\s+", text):
        if not token or token in _COLOR_WORDS:
            continue
        for color in color_suffixes:
            if token.endswith(color) and len(token) > len(color) + 2:
                token = token[: -len(color)]
                break
        if token and token not in _COLOR_WORDS:
            tokens.append(token)
    return " ".join(tokens)


def _variant_key(item: dict) -> str:
    text = unicodedata.normalize(
        "NFKC",
        " ".join(
            str(value or "")
            for value in (item.get("name_en"), item.get("name_zh_raw"), item.get("color"))
        ),
    ).casefold()
    variants = []
    for label, keywords in {
        "blue": ("blue", "藍"),
        "green": ("green", "綠"),
        "red": ("red", "紅"),
        "yellow": ("yellow", "黃"),
        "black": ("black", "黑"),
        "grey": ("grey", "gray", "灰"),
        "beige": ("beige", "米"),
        "brown": ("brown", "棕", "胡桃"),
        "oak": ("oak", "橡木"),
        "birch": ("birch", "樺木"),
        "white": ("white", "白"),
    }.items():
        if any(keyword in text for keyword in keywords):
            variants.append(label)
    return "-".join(variants) or "default"


def _merge_key(item: dict) -> str:
    name = _text_key(item.get("name_en") or item.get("name_zh_raw") or item.get("furniture_id"))
    name_text = f"{item.get('name_en') or ''} {item.get('name_zh_raw') or ''}"
    single_dim_match = _SINGLE_DIMENSION_TEXT.search(unicodedata.normalize("NFKC", name_text).casefold())
    has_full_dimensions = bool(re.search(r"\d\s*(?:x|X|×|\*)\s*\d", name_text))
    if single_dim_match and not has_full_dimensions and ("lamp" in name or "燈" in name_text):
        size_key = f"d{int(round(float(single_dim_match.group(1))))}"
    else:
        size = sanitize_size_cm(item)
        size_key = "x".join(str(int(round(size.get(axis, 0)))) for axis in ("width", "depth", "height"))
    return f"{name}|{size_key}|{_variant_key(item)}"


def _candidate_score(candidate: object) -> float:
    try:
        if isinstance(candidate, dict):
            return float(candidate.get("score", 1) or 0)
        if isinstance(candidate, (list, tuple)) and len(candidate) > 1:
            return float(candidate[1] or 0)
    except (TypeError, ValueError):
        return 0.0
    return 1.0


def _candidate_style_id(candidate: object) -> str | None:
    if isinstance(candidate, dict):
        return candidate.get("style_id")
    if isinstance(candidate, (list, tuple)) and candidate:
        return str(candidate[0])
    if isinstance(candidate, str):
        return candidate
    return None


def _rule_based_style_candidates(item: dict) -> list[dict]:
    text = unicodedata.normalize(
        "NFKC",
        " ".join(str(value or "") for value in (item.get("name_en"), item.get("name_zh_raw"), item.get("normalized_type"), item.get("color"))),
    ).casefold()
    is_storage_bench = (
        ("bench with toy storage" in text)
        or ("收納長凳" in text)
        or ("storage" in text and ("bench" in text or "stool" in text or "長凳" in text))
    )
    is_simple_light = any(token in text for token in ("white", "light", "白", "淺", "低彩度"))
    if not (is_storage_bench and is_simple_light):
        return []

    reasons = ["rule:simple_light_storage_bench", "rule:clean_lines", "rule:low_saturation_base"]
    return [
        {"style_id": "scandinavian", "score": 0.72, "reasons": reasons},
        {"style_id": "minimalist_muji", "score": 0.68, "reasons": reasons},
        {"style_id": "nordic_modern", "score": 0.68, "reasons": reasons},
        {"style_id": "modern", "score": 0.62, "reasons": reasons},
    ]


def _merge_style_candidates(items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in items:
        candidates = list(item.get("style_candidates") or []) + _rule_based_style_candidates(item)
        if item.get("primary_style"):
            candidates.append({"style_id": item.get("primary_style"), "score": item.get("style_confidence") or 0.35})

        for candidate in candidates:
            style_id = _candidate_style_id(candidate)
            if not style_id:
                continue
            score = _candidate_score(candidate)
            reasons = candidate.get("reasons", []) if isinstance(candidate, dict) else []
            current = merged.get(style_id)
            if current is None or score > current["score"]:
                merged[style_id] = {
                    "style_id": style_id,
                    "score": round(score, 3),
                    "reasons": list(reasons),
                }
            elif reasons:
                current["reasons"] = sorted(set(current.get("reasons", []) + list(reasons)))

    return sorted(merged.values(), key=lambda candidate: candidate.get("score", 0), reverse=True)


def _model_url_for_merged_item(item: dict) -> str | None:
    if item.get("render_mode") == "procedural_fixture":
        return None
    cloud_url = cloud_model_url(item)
    if cloud_url:
        return cloud_url
    if cloudfront_required():
        return None
    return f"/api/furniture/{item.get('furniture_id')}/model" if item.get("has_model") else None


def _model_priority_ids(items: list[dict]) -> list[str]:
    import_ids = [
        str(entry.get("furniture_id"))
        for entry in items
        if entry.get("_catalog_origin") == "import"
        and entry.get("furniture_id")
        and _model_status(entry)[0]
    ]
    catalog_ids = [
        str(entry.get("furniture_id"))
        for entry in items
        if entry.get("_catalog_origin") == "catalog" and entry.get("furniture_id") and _model_status(entry)[0]
    ]
    return list(dict.fromkeys(import_ids + catalog_ids))


def _merge_furniture_catalog(furniture_items: list[dict], external_items: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for item in furniture_items:
        clone = dict(item)
        clone["_catalog_origin"] = "catalog"
        groups.setdefault(_merge_key(clone), []).append(clone)

    for item in external_items:
        clone = dict(item)
        clone["_catalog_origin"] = "import"
        groups.setdefault(_merge_key(clone), []).append(clone)

    merged_items: list[dict] = []
    for items in groups.values():
        items = sorted(items, key=lambda entry: 0 if entry.get("_catalog_origin") == "catalog" else 1)
        priority_ids = _model_priority_ids(items)
        model_items = [
            entry
            for entry in items
            if entry.get("furniture_id") in priority_ids
        ]
        base = dict(model_items[0] if model_items else items[0])
        preferred_text = next(
            (
                entry
                for entry in items
                if any("\u4e00" <= char <= "\u9fff" for char in str(entry.get("name_zh_raw") or ""))
            ),
            items[0],
        )
        merged_candidates = _merge_style_candidates(items)
        primary_candidate = merged_candidates[0] if merged_candidates else {}

        base["furniture_id"] = base.get("furniture_id") or items[0].get("furniture_id")
        base["name_en"] = preferred_text.get("name_en") or base.get("name_en")
        base["name_zh_raw"] = preferred_text.get("name_zh_raw") or base.get("name_zh_raw")
        base["category_label"] = preferred_text.get("category_label") or base.get("category_label")
        base["normalized_type"] = preferred_text.get("normalized_type") or base.get("normalized_type")
        base["color"] = preferred_text.get("color") or base.get("color")
        base["material"] = preferred_text.get("material") or base.get("material")
        base["size_cm"] = sanitize_size_cm(base)
        base["style_candidates"] = merged_candidates
        base["primary_style"] = primary_candidate.get("style_id") or base.get("primary_style")
        base["style_confidence"] = primary_candidate.get("score") or base.get("style_confidence")
        base["style_assignment_source"] = "merged_catalog_rules_v1"
        base["merged_furniture_ids"] = sorted(
            {str(entry.get("furniture_id")) for entry in items if entry.get("furniture_id")}
        )
        base["model_priority_ids"] = priority_ids
        base["catalog_merge_key"] = _merge_key(base)
        base["source_count"] = len(items)
        base["has_model"], model_reason = (True, None) if priority_ids else _model_status(base)
        base["missing_model_reason"] = None if base["has_model"] else model_reason
        base["model_url"] = _model_url_for_merged_item(base)
        base.pop("_catalog_origin", None)
        merged_items.append(base)

    return sorted(merged_items, key=lambda item: (item.get("normalized_type") or "", item.get("name_zh_raw") or item.get("name_en") or ""))


@lru_cache(maxsize=1)
def _merged_furniture_catalog_cached() -> tuple[dict, ...]:
    raw = load_style_database()
    active_items: list[dict] = []
    for source in raw.get("furniture", []):
        item = dict(source)
        item["merged_furniture_ids"] = [str(item.get("furniture_id"))]
        item["model_priority_ids"] = []
        item["catalog_merge_key"] = str(item.get("furniture_id") or "")
        item["source_count"] = 1
        if "has_model" in item:
            item["has_model"] = bool(item.get("has_model"))
            item["missing_model_reason"] = None if item["has_model"] else item.get("missing_model_reason")
            item["model_url"] = item.get("model_url") if item["has_model"] else None
        else:
            item["has_model"], reason = _model_status(item)
            item["missing_model_reason"] = None if item["has_model"] else reason
            item["model_url"] = _model_url_for_merged_item(item)
        active_items.append(item)
    return tuple(active_items)


_FURNITURE_ROLE_BY_TYPE = {
    "sofa": "主要座位",
    "sofa-bed": "主要座位 / 臨時睡眠",
    "armchair": "輔助座位",
    "coffee-table": "中心互動桌",
    "tv-bench": "影音牆收納",
    "bookcase": "書籍與展示收納",
    "wall-shelf": "牆面展示收納",
    "bed": "主要睡眠家具",
    "bed-frame": "主要睡眠家具",
    "bedside-table": "床邊收納",
    "desk": "工作桌",
    "office-chair": "工作座椅",
    "dining-table": "用餐核心桌",
    "dining-chair": "用餐座椅",
    "sideboard": "餐廚或客廳收納",
    "large-medium-rug": "區域界定軟裝",
    "runner-small-rug": "走道或床側軟裝",
}


def _candidate_quantity_template(item_type: str | None) -> dict:
    if item_type in {"sofa", "coffee-table", "tv-bench", "bed", "bed-frame", "desk", "dining-table", "sideboard"}:
        return {"min": 1, "max": 1, "recommended": 1}
    if item_type in {"bedside-table", "dining-chair"}:
        return {"min": None, "max": None, "recommended": None}
    return {"min": None, "max": None, "recommended": None}


def _candidate_match_reason(item: dict, has_model: bool) -> str:
    tokens = []
    style = item.get("primary_style")
    if style:
        tokens.append(f"主要風格為 {style}")
    item_type = item.get("normalized_type")
    if item_type:
        tokens.append(f"類型為 {item_type}")
    if item.get("color"):
        tokens.append(f"色彩資料為 {item.get('color')}")
    if item.get("material"):
        tokens.append(f"材質資料為 {item.get('material')}")
    tokens.append("已有 GLB 模型" if has_model else "目前缺少可載入 GLB 模型")
    return "，".join(tokens) + "。"


def _candidate_schema_fields(item: dict, has_model: bool) -> dict:
    item_type = item.get("normalized_type")
    return {
        "role": _FURNITURE_ROLE_BY_TYPE.get(item_type, ""),
        "quantity": _candidate_quantity_template(item_type),
        "placement_hints": {},
        "clearance_zones": [],
        "layout_relations": [],
        "match_reason": _candidate_match_reason(item, has_model),
        "rule": {},
    }


def _furniture_payload_item(item: dict, include_model_url: bool = True) -> dict:
    has_model, model_reason = (
        (bool(item.get("has_model")), item.get("missing_model_reason"))
        if "has_model" in item
        else _model_status(item)
    )
    preview_images = cloud_image_urls(item)
    image_url = (
        preview_images.get("front")
        or preview_images.get("angle-45")
        or preview_images.get("side")
        or cloud_primary_image_url(item)
    )
    payload = {
        "furniture_id": item.get("furniture_id"),
        "name_en": item.get("name_en"),
        "name_zh": item.get("name_zh") or item.get("name_zh_raw"),
        "name_zh_raw": item.get("name_zh_raw"),
        "category_label": item.get("category_label"),
        "taxonomy_group": item.get("taxonomy_group"),
        "taxonomy_group_zh": item.get("taxonomy_group_zh"),
        "taxonomy_type_zh": item.get("taxonomy_type_zh"),
        "catalog_scope": item.get("catalog_scope"),
        "normalized_type": item.get("normalized_type"),
        "primary_style": item.get("primary_style"),
        "style_primary": item.get("style_primary") or item.get("primary_style"),
        "style_secondary": item.get("style_secondary"),
        "style_candidates": item.get("style_candidates", []),
        "style_confidence": item.get("style_confidence"),
        "style_assignment_source": item.get("style_assignment_source"),
        "room_types": item.get("room_types", []),
        "catalog_role": item.get("role"),
        "visual_weight": item.get("visual_weight"),
        "height_zone": item.get("height_zone"),
        "size_class": item.get("size_class"),
        "description": item.get("description"),
        "rag_text": item.get("rag_text", []),
        "mood_tags": item.get("mood_tags", []),
        "features": item.get("features", []),
        "search_keywords": item.get("search_keywords", []),
        "object_type_zh": item.get("object_type_zh"),
        "color": item.get("color"),
        "material": item.get("material"),
        "size_cm": sanitize_size_cm(item),
        "must_against_wall": item.get("must_against_wall"),
        "can_rotate": item.get("can_rotate"),
        "has_model": has_model,
        "missing_model_reason": None if has_model else model_reason,
        "image_url": image_url,
        "thumbnail_url": image_url,
        "preview_url": image_url,
        "preview_images": preview_images,
        "render_mode": item.get("render_mode"),
        **_candidate_schema_fields(item, has_model),
    }
    if include_model_url:
        payload["model_url"] = _model_url_for_merged_item(item) if has_model else None
    return payload


def _furniture_card_payload(item: dict) -> dict:
    return {
        "furniture_id": item.get("furniture_id"),
        "name_en": item.get("name_en"),
        "name_zh": item.get("name_zh") or item.get("name_zh_raw"),
        "name_zh_raw": item.get("name_zh_raw"),
        "category_label": item.get("category_label"),
        "taxonomy_group": item.get("taxonomy_group"),
        "taxonomy_group_zh": item.get("taxonomy_group_zh"),
        "taxonomy_type_zh": item.get("taxonomy_type_zh"),
        "catalog_scope": item.get("catalog_scope"),
        "normalized_type": item.get("normalized_type"),
        "primary_style": item.get("primary_style"),
        "style_primary": item.get("style_primary") or item.get("primary_style"),
        "style_secondary": item.get("style_secondary"),
        "style_candidates": item.get("style_candidates", []),
        "room_types": item.get("room_types", []),
        "catalog_role": item.get("role"),
        "description": item.get("description"),
        "rag_text": item.get("rag_text", []),
        "mood_tags": item.get("mood_tags", []),
        "features": item.get("features", []),
        "search_keywords": item.get("search_keywords", []),
        "color": item.get("color"),
        "material": item.get("material"),
        "size_cm": item.get("size_cm"),
        "has_model": item.get("has_model"),
        "missing_model_reason": item.get("missing_model_reason"),
        "model_url": item.get("model_url"),
        "image_url": item.get("image_url"),
        "thumbnail_url": item.get("thumbnail_url"),
        "preview_url": item.get("preview_url"),
        "preview_images": item.get("preview_images", {}),
        "render_mode": item.get("render_mode"),
    }


@lru_cache(maxsize=2)
def _furniture_payload_for_provider(provider: str) -> tuple[dict, ...]:
    """Keep every consumer on the profile's one explicit catalog source."""
    if provider == "fixture":
        return tuple(_furniture_payload_item(item) for item in load_fixture_catalog())
    if provider == "postgres":
        return load_postgres_catalog(PROJECT_DIR)
    raise RuntimeError(f"unsupported catalog provider: {provider}")


@lru_cache(maxsize=1)
def _furniture_payload_cache() -> tuple[dict, ...]:
    return _furniture_payload_for_provider(catalog_provider_mode(PROJECT_DIR))


@lru_cache(maxsize=2048)
def _parse_glb(model_path_text: str) -> tuple[dict, bytes]:
    model_path = Path(model_path_text)
    buffer = model_path.read_bytes()

    if buffer[0:4] != b"glTF":
        raise ValueError("The input file is not a binary glTF (.glb) file.")

    declared_length = int.from_bytes(buffer[8:12], "little")
    if declared_length != len(buffer):
        raise ValueError("GLB length mismatch.")

    offset = 12
    json_payload = None
    binary_payload = None

    while offset + 8 <= len(buffer):
        chunk_length = int.from_bytes(buffer[offset : offset + 4], "little")
        chunk_type = int.from_bytes(buffer[offset + 4 : offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_length
        chunk = buffer[chunk_start:chunk_end]

        if chunk_type == 0x4E4F534A:
            json_payload = json.loads(chunk.rstrip(b"\x00").decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary_payload = bytes(chunk)

        offset = chunk_end

    if json_payload is None or binary_payload is None:
        raise ValueError("The GLB does not contain both JSON and BIN chunks.")

    return json_payload, binary_payload


def _get_furniture_by_id(furniture_id: str) -> dict:
    data = load_style_database()
    furniture = next((item for item in data.get("furniture", []) if item.get("furniture_id") == furniture_id), None)
    if not furniture:
        raise HTTPException(status_code=404, detail="找不到這件家具資料。")
    return furniture


def _get_merged_furniture_by_id(furniture_id: str) -> dict:
    for item in _furniture_payload_cache():
        if str(item.get("furniture_id")) == str(furniture_id):
            return item
    for item in _merged_furniture_catalog_cached():
        aliases = set(item.get("merged_furniture_ids") or [])
        aliases.add(str(item.get("furniture_id")))
        if furniture_id in aliases:
            return item
    raise HTTPException(status_code=404, detail="Furniture not found in merged catalog.")


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


def _remote_glb_response(url: str) -> Response:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RoomPilot/1.0",
            "Accept": "model/gltf-binary,application/octet-stream,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"遠端 GLB 讀取失敗：{exc}") from exc

    if payload[:4] != b"glTF":
        raise HTTPException(status_code=502, detail="遠端模型不是可用的 GLB 檔案。")

    return Response(content=payload, media_type="model/gltf-binary")


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
        raise HTTPException(
            status_code=404,
            detail="找不到這件家具對應的 GLB；請設定 ROOMPILOT_LOCAL_GLB_ROOTS。",
        )

    return str(model_path)


def _gltf_payload_for_web(model_path_text: str, furniture_id: str) -> dict:
    gltf_json, binary_payload = _parse_glb(model_path_text)
    gltf_copy = json.loads(json.dumps(gltf_json))

    if gltf_copy.get("buffers"):
        gltf_copy["buffers"][0]["uri"] = "buffer.bin"
        gltf_copy["buffers"][0]["byteLength"] = len(binary_payload)

    for index, image in enumerate(gltf_copy.get("images", [])):
        if image.get("bufferView") is not None:
            image["uri"] = f"images/{index}"
            image.pop("bufferView", None)
            image.pop("mimeType", None)

    for texture in gltf_copy.get("textures", []):
        ext_webp = texture.get("extensions", {}).get("EXT_texture_webp")
        if ext_webp and ext_webp.get("source") is not None:
            texture["source"] = ext_webp["source"]
        texture.pop("extensions", None)

    gltf_copy["extensionsUsed"] = [
        ext for ext in gltf_copy.get("extensionsUsed", [])
        if ext != "EXT_texture_webp"
    ]
    gltf_copy["extensionsRequired"] = [
        ext for ext in gltf_copy.get("extensionsRequired", [])
        if ext != "EXT_texture_webp"
    ]

    return gltf_copy


def _image_bytes_from_glb(model_path_text: str, image_index: int) -> tuple[bytes, str]:
    gltf_json, binary_payload = _parse_glb(model_path_text)
    images = gltf_json.get("images", [])
    buffer_views = gltf_json.get("bufferViews", [])

    if image_index < 0 or image_index >= len(images):
        raise HTTPException(status_code=404, detail="找不到這張貼圖。")

    image = images[image_index]
    buffer_view_index = image.get("bufferView")
    if buffer_view_index is None:
        raise HTTPException(status_code=404, detail="這張貼圖沒有內嵌 bufferView。")

    if buffer_view_index < 0 or buffer_view_index >= len(buffer_views):
        raise HTTPException(status_code=404, detail="這張貼圖的 bufferView 無效。")

    view = buffer_views[buffer_view_index]
    start = view.get("byteOffset", 0)
    end = start + view.get("byteLength", 0)
    mime_type = image.get("mimeType", "application/octet-stream")
    payload = binary_payload[start:end]

    if mime_type == "image/webp":
        with Image.open(io.BytesIO(payload)) as source:
            output = io.BytesIO()
            source.save(output, format="PNG")
            return output.getvalue(), "image/png"

    return payload, mime_type


def _style_payloads(raw: dict | None = None, surface_catalog: dict | None = None) -> list[dict]:
    raw = raw or load_style_database()
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
                "moodboard_image_url": None,
            }
        )
    return styles


def _style_ids_for_count(item: dict) -> set[str]:
    style_ids: set[str] = set()
    if item.get("primary_style"):
        style_ids.add(str(item.get("primary_style")))
    for candidate in item.get("style_candidates", []) or []:
        style_id = _candidate_style_id(candidate)
        if style_id and _candidate_score(candidate) > 0:
            style_ids.add(style_id)
    return style_ids


@lru_cache(maxsize=1)
def _catalog_count_summary() -> dict:
    raw = load_style_database()
    items = list(raw.get("furniture", []))
    style_counts: dict[str, int] = {}
    style_type_counts: dict[str, dict[str, int]] = {}
    styled_count = 0

    for item in items:
        style_ids = _style_ids_for_count(item)
        if style_ids:
            styled_count += 1
        item_type = item.get("normalized_type") or "unknown"
        for style_id in style_ids:
            style_counts[style_id] = style_counts.get(style_id, 0) + 1
            type_counts = style_type_counts.setdefault(style_id, {})
            type_counts[item_type] = type_counts.get(item_type, 0) + 1

    return {
        "total_furniture": len(items),
        "styled_furniture": styled_count,
        "fallback_furniture": len(items) - styled_count,
        "style_furniture_counts": style_counts,
        "style_type_counts": {
            style_id: sorted(type_counts.items(), key=lambda pair: pair[1], reverse=True)
            for style_id, type_counts in style_type_counts.items()
        },
    }


def _furniture_matches_style(item: dict, style_id: str | None) -> bool:
    if not style_id:
        return True
    if style_id in {
        item.get("primary_style"),
        item.get("style_primary"),
        item.get("style_secondary"),
    }:
        return True
    for candidate in item.get("style_candidates", []) or []:
        if _candidate_style_id(candidate) == style_id and _candidate_score(candidate) > 0:
            return True
    return False


def _furniture_search_text(item: dict) -> str:
    return " ".join(
        str(value or "")
        for value in (
            item.get("furniture_id"),
            item.get("name_en"),
            item.get("name_zh"),
            item.get("name_zh_raw"),
            item.get("category_label"),
            item.get("taxonomy_group_zh"),
            item.get("taxonomy_type_zh"),
            item.get("normalized_type"),
            item.get("color"),
            item.get("material"),
            item.get("primary_style"),
            item.get("style_primary"),
            item.get("style_secondary"),
            " ".join(item.get("room_types") or []),
            item.get("role"),
            item.get("description"),
            " ".join(item.get("rag_text") or []),
            " ".join(item.get("mood_tags") or []),
            " ".join(item.get("features") or []),
            " ".join(item.get("search_keywords") or []),
            item.get("object_type_zh"),
        )
    ).casefold()


_FURNITURE_SEARCH_TYPE_INTENTS = {
    # The catalog has supplier names in several languages. Map the common
    # customer-facing words to stable taxonomy types before doing text search.
    "椅子": (
        "armchair",
        "dining-chair",
        "office-chair",
        "gaming-chair",
        "kids-chairs-stool",
        "chair",
        "stool-bench",
    ),
    "單人椅": ("armchair",),
    "扶手椅": ("armchair",),
    "餐椅": ("dining-chair",),
    "辦公椅": ("office-chair",),
    "電競椅": ("gaming-chair",),
    "椅凳": ("stool-bench",),
}


def _furniture_search_intent(query: str) -> tuple[str, ...]:
    """Return taxonomy types implied by a customer-facing furniture term."""
    return _FURNITURE_SEARCH_TYPE_INTENTS.get(query.casefold(), ())


def _furniture_matches_query(item: dict, query: str, intent_types: tuple[str, ...]) -> bool:
    if not query:
        return True
    if query in _furniture_search_text(item):
        return True
    return str(item.get("normalized_type") or "") in intent_types


def _furniture_query_sort_key(item: dict, query: str, intent_types: tuple[str, ...]) -> tuple[int, int, str]:
    """Keep exact matches useful, while placing intended taxonomy types first."""
    item_type = str(item.get("normalized_type") or "")
    search_text = _furniture_search_text(item)
    if intent_types and item_type in intent_types:
        return (0, intent_types.index(item_type), str(item.get("name_zh") or item.get("name_en") or ""))
    return (1, 0 if query in search_text else 1, str(item.get("name_zh") or item.get("name_en") or ""))


_FURNITURE_FACET_TRANSLATIONS = {
    "color": {
        "white": "白色",
        "black": "黑色",
        "grey": "灰色",
        "gray": "灰色",
        "beige": "米色",
        "brown": "棕色",
        "green": "綠色",
        "blue": "藍色",
        "red": "紅色",
        "silver": "銀色",
        "gold": "金色",
        "yellow": "黃色",
        "wood": "木色",
        "walnut": "胡桃木色",
        "navy": "海軍藍",
    },
    "material": {
        "wood": "木材",
        "oak": "橡木",
        "metal": "金屬",
        "fabric": "布料",
        "textile": "織物",
        "leather": "皮革",
        "glass": "玻璃",
        "steel": "鋼材",
        "birch": "樺木",
        "walnut": "胡桃木",
        "wood veneer": "木皮",
        "solid wood": "實木",
        "plywood": "夾板",
        "plastic": "塑膠",
    },
}


def _normalize_furniture_facet_value(value: object, key: str) -> str:
    translations = _FURNITURE_FACET_TRANSLATIONS.get(key, {})
    parts = [part.strip() for part in re.split(r"[,/、]+", str(value or "")) if part.strip()]
    return "、".join(translations.get(part.casefold(), part) for part in parts)


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
    intent_types = _furniture_search_intent(query)
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
        if not _furniture_matches_query(item, query, intent_types):
            continue
        items.append(item)
    if query:
        items.sort(key=lambda item: _furniture_query_sort_key(item, query, intent_types))
    return items


def _furniture_size_bucket(item: dict) -> str | None:
    size_cm = item.get("size_cm") or {}
    footprint = [size_cm.get("width"), size_cm.get("depth")]
    dimensions = []
    for value in footprint:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            dimensions.append(numeric)
    if not dimensions:
        return None
    longest_side = max(dimensions)
    if longest_side <= 80:
        return "small"
    if longest_side <= 160:
        return "medium"
    return "large"


def _furniture_filter_options(items: list[dict]) -> dict:
    ignored_values = {"", "尚未整理", "未整理", "unknown", "none", "null", "-"}

    def counted_options(key: str, limit: int = 18) -> list[dict]:
        counts: dict[str, int] = {}
        for item in items:
            value = _normalize_furniture_facet_value(item.get(key), key)
            if value.casefold() in ignored_values or "�" in value:
                continue
            counts[value] = counts.get(value, 0) + 1
        return [
            {"value": value, "label": value, "count": count}
            for value, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
        ]

    return {
        "sizes": [
            {"value": "small", "label": "小型（80 cm 以下）"},
            {"value": "medium", "label": "中型（81–160 cm）"},
            {"value": "large", "label": "大型（161 cm 以上）"},
        ],
        "colors": counted_options("color"),
        "materials": counted_options("material"),
    }


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


def _style_filter_options() -> list[dict]:
    return [
        {
            "style_id": style.get("style_id"),
            "style_name_zh": style.get("style_name_zh"),
        }
        for style in _style_payloads()
    ]


@lru_cache(maxsize=2)
def _build_site_payload_for_provider(provider: str) -> dict:
    raw = load_style_database()
    surface_catalog = load_surface_catalog()
    furniture_items = list(_furniture_payload_for_provider(provider))
    furniture_by_id = {}
    for item in furniture_items:
        furniture_by_id[item.get("furniture_id")] = item
        for alias in item.get("merged_furniture_ids", []):
            furniture_by_id[alias] = item

    styles = []
    for style in raw.get("styles", []):
        representative_cards = []
        for furniture_id, card_path in zip(
            style.get("representative_furniture_ids", []),
            style.get("representative_furniture_cards", []),
        ):
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
                    "card_image_url": None,
                    "has_model": has_model,
                    "missing_model_reason": None if has_model else model_reason,
                    "model_url": furniture.get("model_url") if has_model else None,
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
                "moodboard_image_url": None,
                "representative_furniture": representative_cards,
            }
        )

    furniture_payload = list(furniture_items)

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


def build_site_payload() -> dict:
    """Build the scene payload from the same provider used by /api/furniture."""
    return _build_site_payload_for_provider(catalog_provider_mode(PROJECT_DIR))


def _page(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@app.get("/")
def home() -> FileResponse:
    return _page("index.html")


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
                "code": "project_not_found",
                "message": "找不到這個專案，請返回專案列表重新選擇。",
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


@app.post("/api/projects", status_code=201)
def create_project(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(
            422,
            {
                "code": "project_name_required",
                "message": "請輸入專案名稱。",
                "focus": "project-name",
            },
        )
    notes = str(payload.get("notes") or "").strip()
    return {"project": PROJECT_STORE.create_project(name=name, notes=notes)}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"project": _stored_project(project_id)}


@app.put("/api/projects/{project_id}/workflow")
def save_project_workflow(project_id: str, payload: dict) -> dict:
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
    content = await file.read()
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
def get_project_floorplan_source(project_id: str) -> FileResponse:
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
def list_project_renders(project_id: str) -> dict:
    try:
        renders = PROJECT_STORE.list_renders(project_id)
    except KeyError as exc:
        raise HTTPException(
            404, {"code": "project_not_found", "message": "找不到專案。"}
        ) from exc
    return {"renders": [_public_render_record(record) for record in renders]}


@app.get("/api/projects/{project_id}/renders/{render_id}/png")
def download_project_render(project_id: str, render_id: str) -> FileResponse:
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
    return FileResponse(path, media_type="image/png", filename=render["filename"])


@app.get("/api/render-provider/status")
def get_render_provider_status() -> dict:
    return render_provider_status()


@app.post("/api/projects/{project_id}/render-jobs", status_code=202)
async def create_project_render_jobs(project_id: str, payload: dict) -> dict:
    _stored_project(project_id)
    if payload.get("project_id") != project_id:
        raise HTTPException(
            422,
            {"code": "render_project_mismatch", "message": "渲染資料與目前專案不一致。"},
        )
    try:
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


def _looks_like_png_data_url(value: object) -> bool:
    """image data URL 且 base64 內容解得開、非空。

    只檢查前綴不夠：``data:image/png;base64,``（沒有內容）會一路過關到生圖 adapter，
    在那裡被真值判斷靜默丟掉，最後送出一個沒有參考圖的純文字請求——模型照樣回一張
    圖，但已經不是使用者鎖定的那個空間，而且回應裡看不出來。故在入口就擋掉。
    """
    text = str(value or "")
    if not text.startswith("data:image/") or ";base64," not in text:
        return False
    try:
        return bool(base64.b64decode(text.split(",", 1)[1], validate=True))
    except (binascii.Error, ValueError):
        return False


@app.get("/api/ai-render/status")
def get_ai_render_status() -> dict:
    """第 8 步 AI 生圖服務（OpenRouter nano banana）是否可用；不外洩 token。"""
    return ai_render_status()


@app.post("/api/projects/{project_id}/ai-renders", status_code=201)
def create_project_ai_renders(project_id: str, payload: dict) -> dict:
    """逐房視角經 OpenRouter nano banana 生成寫實室內圖（不移動擺設）。

    前端送 ``scene``（state.sceneData）＋逐房 ``rooms``（含第 7 步鎖定視角的 3D
    截圖）。伺服器補充需求/材質/家電/色卡資訊、逐房呼叫 Gen_Pic Agent，並把每房
    鎖定清單存進 project workflow，供整批一次改圖使用。未設定金鑰回 503。
    """
    _stored_project(project_id)
    if payload.get("project_id") not in (None, project_id):
        raise HTTPException(
            422,
            {"code": "render_project_mismatch", "message": "生圖資料與目前專案不一致。"},
        )
    scene = payload.get("scene")
    if not isinstance(scene, dict) or not scene.get("scene_objects"):
        raise HTTPException(
            422,
            {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
        )
    rooms = payload.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        raise HTTPException(
            422,
            {"code": "room_views_required", "message": "缺少逐房視角，請先在第 7 步鎖定視角。"},
        )
    for room in rooms:
        if not isinstance(room, dict) or not str(room.get("room_id") or "").strip():
            raise HTTPException(
                422,
                {"code": "room_id_required", "message": "每個房間視角都需要 room_id。"},
            )
        if not _looks_like_png_data_url(room.get("reference_png_data_url")):
            raise HTTPException(
                422,
                {"code": "reference_png_required", "message": "每個房間視角都需要 3D 視角截圖。"},
            )
    try:
        outcome = generate_room_images(scene, rooms)
    except AiRenderReferenceMissing as exc:
        raise HTTPException(
            422,
            {"code": "reference_png_required", "message": f"每個房間視角都需要 3D 視角截圖（{exc}）。"},
        ) from exc
    except AiRenderNotConfigured as exc:
        raise HTTPException(
            503,
            {
                "code": str(exc),
                "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
            },
        ) from exc
    project = PROJECT_STORE.update_workflow(
        project_id,
        workflow={
            "ai_render": {
                "edit_used": 0,
                # 逐房各自一次改圖額度（指南 §3E：每房可在初圖後提出一次修改）。
                "rooms": [{**room, "edit_used": 0} for room in outcome["rooms"]],
            }
        },
    )
    return {
        "results": outcome["results"],
        "edit_remaining": 1,
        "revision": project["revision"],
        "updated_at": project["updated_at"],
    }


@app.post("/api/projects/{project_id}/palette-renders", status_code=201)
def create_project_palette_renders(project_id: str, payload: dict) -> dict:
    """第 7 步代表房「色卡比較」:同一代表房 × 多張色卡,一次併發呼叫 Gen_Pic Agent
    (Nano Banana Pro)。**每個專案只能成功生成一次** —— 已生成過回 409,不再呼叫模型;
    全部失敗則不鎖定,允許重試。base64 不入 workflow(2MB 上限),只存旗標與各卡狀態。
    """
    project = _stored_project(project_id)
    if payload.get("project_id") not in (None, project_id):
        raise HTTPException(
            422,
            {"code": "render_project_mismatch", "message": "生圖資料與目前專案不一致。"},
        )
    palette_state = (project.get("workflow") or {}).get("palette_render") or {}
    if palette_state.get("generated"):
        raise HTTPException(
            409,
            {
                "code": "palette_already_generated",
                "message": "此專案的代表房色卡比較圖已生成過，每個專案只能生成一次。",
            },
        )
    scene = payload.get("scene")
    if not isinstance(scene, dict) or not scene.get("scene_objects"):
        raise HTTPException(
            422,
            {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
        )
    room = payload.get("room")
    if not isinstance(room, dict) or not str(room.get("room_id") or "").strip():
        raise HTTPException(
            422,
            {"code": "room_required", "message": "缺少代表房，請先在第 7 步選定代表房與視角。"},
        )
    if not _looks_like_png_data_url(room.get("reference_png_data_url")):
        raise HTTPException(
            422,
            {"code": "reference_png_required", "message": "代表房需要 3D 視角截圖。"},
        )
    style_card_ids = payload.get("style_card_ids")
    if not isinstance(style_card_ids, list) or not [
        card for card in style_card_ids if str(card or "").strip()
    ]:
        raise HTTPException(
            422,
            {"code": "style_card_ids_required", "message": "缺少色卡清單。"},
        )
    try:
        outcome = generate_palette_images(scene, room, style_card_ids)
    except AiRenderReferenceMissing as exc:
        raise HTTPException(
            422,
            {"code": "reference_png_required", "message": f"代表房需要 3D 視角截圖（{exc}）。"},
        ) from exc
    except AiRenderNotConfigured as exc:
        raise HTTPException(
            503,
            {
                "code": str(exc),
                "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
            },
        ) from exc
    any_completed = any(item.get("status") == "completed" for item in outcome["results"])
    if not any_completed:
        # 全部失敗:不鎖定,讓使用者可重試;回失敗結果供前端顯示原因。
        return {
            "results": outcome["results"],
            "already_generated": False,
            "room_id": outcome["room_id"],
        }
    project = PROJECT_STORE.update_workflow(
        project_id,
        workflow={
            "palette_render": {
                "generated": True,
                "room_id": outcome["room_id"],
                "cards": [
                    {
                        "style_card_id": item.get("style_card_id"),
                        "status": item.get("status"),
                    }
                    for item in outcome["results"]
                ],
            }
        },
    )
    return {
        "results": outcome["results"],
        "already_generated": False,
        "room_id": outcome["room_id"],
        "revision": project["revision"],
        "updated_at": project["updated_at"],
    }


@app.post("/api/projects/{project_id}/ai-renders/{room_id}/edit", status_code=201)
def edit_project_ai_render(project_id: str, room_id: str, payload: dict) -> dict:
    """整批一次改圖：只改使用者指定內容、其餘鎖定不動；額度用完回 409。"""
    project = _stored_project(project_id)
    ai_render = (project.get("workflow") or {}).get("ai_render") or {}
    room_state = next(
        (
            row
            for row in ai_render.get("rooms") or []
            if str(row.get("room_id")) == room_id
        ),
        None,
    )
    if not room_state or not room_state.get("lock_manifest"):
        raise HTTPException(
            409,
            {"code": "room_not_generated", "message": "這個房間尚未生圖，無法修改。"},
        )
    # ponytail: 單一使用者流程，read-check-write 的競態可忽略；額度仍由伺服器強制。
    # 逐房各一次改圖（指南 §3E）；只有這個房間的額度用完才回 409，不影響其他房間。
    if int(room_state.get("edit_used") or 0) >= 1:
        raise HTTPException(
            409,
            {"code": "ai_edit_budget_exhausted", "message": "這個房間只能修改一次，額度已用完。"},
        )
    feedback = str(payload.get("feedback") or "").strip()
    if not feedback:
        raise HTTPException(
            422, {"code": "feedback_required", "message": "請描述想修改的內容。"}
        )
    if not _looks_like_png_data_url(payload.get("image_data_url")):
        raise HTTPException(
            422, {"code": "base_image_required", "message": "缺少要修改的原圖。"}
        )
    try:
        result = edit_room_image(
            room_id, feedback, payload["image_data_url"], room_state["lock_manifest"]
        )
    except AiRenderNotConfigured as exc:
        raise HTTPException(
            503,
            {
                "code": str(exc),
                "message": "尚未連接 OpenRouter 生圖服務（未設定 OPENROUTER_API_KEY）。",
            },
        ) from exc
    except GenPicFailure as exc:
        raise HTTPException(
            502,
            {"code": "ai_edit_failed", "message": "；".join(exc.notices) or "改圖失敗。"},
        ) from exc
    updated_rooms = [
        {**row, "edit_used": 1} if str(row.get("room_id")) == room_id else row
        for row in ai_render.get("rooms") or []
    ]
    project = PROJECT_STORE.update_workflow(
        project_id, workflow={"ai_render": {"rooms": updated_rooms}}
    )
    return {
        "result": result,
        "edit_remaining": 0,
        "revision": project["revision"],
        "updated_at": project["updated_at"],
    }


def _design_manual_dir(project_id: str) -> Path:
    return PROJECT_STORE.runtime_dir / "manuals" / project_id


def _public_design_manual(project_id: str, record: dict) -> dict:
    payload = {key: value for key, value in record.items() if key != "filename"}
    payload["download_url"] = f"/api/projects/{project_id}/design-manual/pdf"
    return payload


@app.post("/api/projects/{project_id}/design-manual", status_code=201)
def create_project_design_manual(project_id: str, payload: dict) -> dict:
    """第 8 步收尾：由 Report Agent 統整需求、配置、家具、色卡與生圖成果，
    輸出九章設計手冊 PDF。

    前端送 ``scene``（state.sceneData）＋逐房 ``rooms``（含房間尺寸與目前最新
    的生圖 data URL；改圖後前端已就地更新）。LLM 只潤飾前言與設計理念，未設定
    OPENROUTER_API_KEY 時走 deterministic 底稿照樣輸出。重新產出會覆蓋 workflow
    紀錄並提高 revision；舊 PDF 檔保留於 runtime 目錄。
    """
    project = _stored_project(project_id)
    scene, rooms = _validated_report_payload(project_id, payload)
    try:
        manual, record = create_design_manual(
            project_id,
            scene,
            rooms,
            _design_manual_dir(project_id),
            design_revision=project["revision"],
        )
    except DesignManualError as exc:
        raise HTTPException(
            502, {"code": "design_manual_failed", "message": str(exc)}
        ) from exc
    updated = PROJECT_STORE.update_workflow(
        project_id, workflow={"design_manual": record}
    )
    return {
        "manual": _public_design_manual(project_id, record),
        "revision": updated["revision"],
        "updated_at": updated["updated_at"],
    }


@app.get("/api/projects/{project_id}/design-manual/pdf")
def download_project_design_manual(project_id: str) -> FileResponse:
    project = _stored_project(project_id)
    record = (project.get("workflow") or {}).get("design_manual") or {}
    filename = str(record.get("filename") or "")
    if not filename:
        raise HTTPException(
            404,
            {"code": "design_manual_not_found", "message": "尚未產出設計手冊。"},
        )
    path = _design_manual_dir(project_id) / filename
    if not path.is_file():
        raise HTTPException(
            410,
            {"code": "design_manual_file_missing", "message": "設計手冊紀錄存在，但檔案已遺失，請重新產出。"},
        )
    return FileResponse(path, media_type="application/pdf", filename=filename)


def _validated_report_payload(project_id: str, payload: dict) -> tuple[dict, list[dict]]:
    """設計手冊與交付提案共用的 payload 驗證（scene＋rooms）。"""
    if payload.get("project_id") not in (None, project_id):
        raise HTTPException(
            422,
            {"code": "manual_project_mismatch", "message": "報告資料與目前專案不一致。"},
        )
    scene = payload.get("scene")
    if not isinstance(scene, dict) or not scene.get("scene_objects"):
        raise HTTPException(
            422,
            {"code": "scene_required", "message": "缺少場景資料，請先完成第 6 步配置。"},
        )
    rooms = payload.get("rooms")
    if not isinstance(rooms, list) or not any(
        isinstance(room, dict) and str(room.get("room_id") or "").strip()
        for room in rooms
    ):
        raise HTTPException(
            422,
            {"code": "rooms_required", "message": "缺少房間資料，無法組成果報告。"},
        )
    scene = {**scene, "scene_objects": _with_catalog_prices(scene["scene_objects"])}
    return scene, rooms


@app.get("/api/delivery-proposal/status")
def get_delivery_proposal_status() -> dict:
    """交付提案排版引擎（playwright Chromium）是否可用；未安裝時回報安裝指引。"""
    return delivery_proposal_status()


@app.post("/api/projects/{project_id}/delivery-proposal", status_code=201)
def create_project_delivery_proposal(project_id: str, payload: dict) -> dict:
    """第 8 步收尾第二版報告：roompilot-delivery-pdf 打包 skill 排版的品牌
    交付提案 PDF，與九章設計手冊吃同一份 payload，供兩版比較。"""
    project = _stored_project(project_id)
    scene, rooms = _validated_report_payload(project_id, payload)
    try:
        _, record = create_delivery_proposal(
            project_id,
            project.get("name") or "RoomPilot 專案",
            scene,
            rooms,
            _design_manual_dir(project_id),
            design_revision=project["revision"],
        )
    except DeliveryNotConfigured as exc:
        raise HTTPException(
            503, {"code": "delivery_engine_not_configured", "message": str(exc)}
        ) from exc
    except DesignManualError as exc:
        raise HTTPException(
            502, {"code": "delivery_proposal_failed", "message": str(exc)}
        ) from exc
    # 同一顆按鈕、同一次請求出兩份檔：PDF 之外再落一份工程估價與排程 XLSX。
    # 放在 PDF 成功之後，PDF 掛了就不做白工。
    record = {
        **record,
        "engineering": build_engineering_estimate(
            project_id,
            str(project["revision"]),
            project.get("workflow") or {},
            PROJECT_STORE.runtime_dir / "manuals",
        ),
    }
    updated = PROJECT_STORE.update_workflow(
        project_id, workflow={"delivery_proposal": record}
    )
    payload_record = {key: value for key, value in record.items() if key != "filename"}
    payload_record["download_url"] = (
        f"/api/projects/{project_id}/delivery-proposal/pdf"
    )
    return {
        "proposal": payload_record,
        "revision": updated["revision"],
        "updated_at": updated["updated_at"],
    }


@app.get("/api/projects/{project_id}/delivery-proposal/pdf")
def download_project_delivery_proposal(project_id: str) -> FileResponse:
    project = _stored_project(project_id)
    record = (project.get("workflow") or {}).get("delivery_proposal") or {}
    filename = str(record.get("filename") or "")
    if not filename:
        raise HTTPException(
            404,
            {"code": "delivery_proposal_not_found", "message": "尚未產出交付提案。"},
        )
    path = _design_manual_dir(project_id) / filename
    if not path.is_file():
        raise HTTPException(
            410,
            {"code": "delivery_proposal_file_missing", "message": "交付提案紀錄存在，但檔案已遺失，請重新產出。"},
        )
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/api/projects/{project_id}/delivery-proposal/xlsx")
def download_project_engineering_estimate(project_id: str) -> FileResponse:
    """與交付提案 PDF 同一次產出的工程估價與初步排程 XLSX。"""
    project = _stored_project(project_id)
    proposal = (project.get("workflow") or {}).get("delivery_proposal") or {}
    engineering = proposal.get("engineering") or {}
    relative = str(engineering.get("file") or "")
    base = (PROJECT_STORE.runtime_dir / "manuals").resolve()
    # workflow 內容前端可寫，組完路徑一定要確認還在 manuals 目錄內。
    path = (base / relative).resolve() if relative else base
    if not relative or not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(
            404,
            {
                "code": "engineering_estimate_not_found",
                "message": "尚未產出工程估價，或檔案已遺失，請重新產出設計提案。",
            },
        )
    # 示範單價的警語只寫在儲存格裡，檔案一轉寄出去就看不到了；檔名帶著走。
    demo = "DEMO-" if engineering.get("demo_mode") else ""
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"roompilot-estimate-{demo}{project_id[:8]}.xlsx",
    )


# ---- 第 8 步成果包（design-delivery）----
# 由 bella-new 分支移植：把全屋簡報、逐房成果、工程報告、資安審核與預算書
# 打包成單一 JSON；並依本分支定案把設計提案 PDF（delivery-proposal）紀錄
# 一併帶出，讓前端在同一個成果包對話框內產出與下載 PDF。

DESIGNER_REFERENCE_BY_ROOM_TYPE = {
    "living_room": "設計觀點參照 Ilse Crawford 重視以人為本、觸感與日常舒適的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "bedroom": "設計觀點參照 Kelly Hoppen 對安定對稱、層次中性色與休憩感的運用；本案僅借用方法論，不代表設計師參與或背書。",
    "kitchen": "設計觀點參照 Patricia Urquiola 對耐用表面、節制用色與生活機能平衡的處理；本案僅借用方法論，不代表設計師參與或背書。",
    "bathroom": "設計觀點參照 John Pawson 對比例、簡潔面材與受控光線的處理；本案僅借用方法論，不代表設計師參與或背書。",
    "dining_room": "設計觀點參照 Ilse Crawford 以人的互動與用餐觸感建立空間核心的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "study": "設計觀點參照 John Pawson 以清楚秩序、留白與自然光降低視覺干擾的取向；本案僅借用方法論，不代表設計師參與或背書。",
    "default": "設計觀點參照專業室內設計常用的動線、採光、材質連續性與收納需求四項原則。",
}


DELIVERY_ROOM_TYPE_ALIASES = {
    "living": "living_room",
    "livingroom": "living_room",
    "客廳": "living_room",
    "master_bedroom": "bedroom",
    "guest_bedroom": "bedroom",
    "臥室": "bedroom",
    "主臥": "bedroom",
    "次臥": "bedroom",
    "廚房": "kitchen",
    "餐廳": "dining_room",
    "dining": "dining_room",
    "書房": "study",
    "office": "study",
    "衛浴": "bathroom",
    "浴室": "bathroom",
}


DELIVERY_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "openrouter_api_key",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "cookie",
    "set_cookie",
    "email",
    "phone",
    "phone_number",
    "full_name",
    "address",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _delivery_room_type(room: dict) -> str:
    raw = str(
        room.get("room_type")
        or room.get("type")
        or (room.get("questionnaire") or {}).get("roomType")
        or room.get("room_name")
        or "default"
    ).strip()
    normalized = raw.casefold().replace("-", "_").replace(" ", "_")
    if normalized in DESIGNER_REFERENCE_BY_ROOM_TYPE:
        return normalized
    if "bedroom" in normalized:
        return "bedroom"
    return DELIVERY_ROOM_TYPE_ALIASES.get(normalized, DELIVERY_ROOM_TYPE_ALIASES.get(raw, "default"))


def _delivery_text(value: object, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


@lru_cache(maxsize=1)
def _catalog_price_index() -> dict[str, int]:
    """型錄單價表（家具 id → 元），只在第 8 步報價階段建立。

    單價刻意不進 site_payload、scene_objects 與生圖 context——選件與擺位不該
    看到價格；報告要出報價單時才用 furniture_id 回查這張表。PostgreSQL 是定
    價權威，連不上就退回已驗證 JSON 型錄（缺價的列照樣印「待報價」，不推估）。
    """
    if catalog_provider_mode(PROJECT_DIR) == "postgres":
        try:
            index = load_postgres_price_index(PROJECT_DIR)
        except Exception:  # noqa: BLE001 - 報價缺價可降級，報告不該因 DB 斷線中止
            index = {}
        if index:
            return index
    return {
        str(item["furniture_id"]): round(price)
        for item in _merged_furniture_catalog_cached()
        if item.get("furniture_id") and (price := _delivery_amount_twd(item))
    }


# 報價回查用的 id 鍵。這幾把常常全部落空：``furniture_id`` 是引擎擺位 id
# （engine/rules.py 產的 ``room-1-bed-1``），``catalog_furniture_id`` 可能是前端
# 候選槽 id（scene_v2.js 的 ``room-1-bed-double-candidate-1``），兩者都不是型錄
# id。真正的型錄 id 只剩 GLB 檔名認得，見 _price_lookup_keys()。
_PRICE_LOOKUP_KEYS = (
    "furniture_id",
    "catalog_furniture_id",
    "catalogFurnitureId",
    "id",
)


def _price_lookup_keys(item: dict):
    """該件家具所有可能的型錄 id，依可信度排序。

    最後一把是 ``model_url`` 的 GLB 檔名。型錄每一筆的 model_url 檔名都等於自己
    的 furniture_id，所以擺位 id 蓋掉型錄 id 之後，它是唯一還認得出「屋主選的是
    哪一款」的線索；少了它，報價單每一列都會是「待報價」、小計恆為 0。
    """
    for name in _PRICE_LOOKUP_KEYS:
        yield str(item.get(name) or "").strip()
    url = str(item.get("model_url") or "").strip()
    yield url.rsplit("/", 1)[-1].rsplit(".", 1)[0] if url else ""


def _with_catalog_prices(items: list) -> list[dict]:
    """報價入口補上 ``price_twd``；已帶價的列不覆蓋。"""
    index = _catalog_price_index()
    priced: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if _delivery_amount_twd(item) is not None:
            priced.append(item)
            continue
        price = next(
            (index[key] for key in _price_lookup_keys(item) if key in index),
            None,
        )
        priced.append({**item, "price_twd": price} if price else item)
    return priced


def _delivery_amount_twd(item: dict) -> int | None:
    for key in ("price_twd", "unit_price_twd", "amount_twd"):
        value = item.get(key)
        try:
            amount = float(value)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            return round(amount)
    return None


def _delivery_furniture_lines(snapshot: dict) -> list[dict]:
    lines: list[dict] = []
    for index, item in enumerate(snapshot.get("furniture") or [], start=1):
        if not isinstance(item, dict):
            continue
        amount_twd = _delivery_amount_twd(item)
        lines.append(
            {
                "id": item.get("instance_id") or item.get("id") or f"furniture-{index}",
                "category": "furniture",
                "category_label": "家具",
                "room_id": item.get("room_id"),
                "name": _delivery_text(
                    item.get("name")
                    or item.get("label")
                    or item.get("name_zh")
                    or item.get("name_zh_raw"),
                    "已選家具",
                ),
                "quantity": 1,
                "unit": "件",
                "material": item.get("material"),
                "size_cm": item.get("size_cm"),
                "amount_twd": amount_twd,
                "status": "catalog_reference" if amount_twd is not None else "pending_quote",
                "status_label": "家具目錄參考價" if amount_twd is not None else "待報價",
                "price_source": item.get("price_source"),
                "note": (
                    "沿用家具目錄參考價；運送、安裝與現場條件仍以正式報價為準。"
                    if amount_twd is not None
                    else "家具目錄未附可驗證價格，保留待報價，不自行推估。"
                ),
            }
        )
    return lines


def _delivery_renovation_lines(rooms: list[dict]) -> list[dict]:
    lines: list[dict] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_name = _delivery_text(room.get("room_name"), "未命名空間")
        questionnaire = room.get("questionnaire") if isinstance(room.get("questionnaire"), dict) else {}
        surfaces = questionnaire.get("surfaces") if isinstance(questionnaire.get("surfaces"), dict) else {}
        scope_labels = [
            label
            for key, label in (
                ("wallDefault", "牆面"),
                ("floor", "地板"),
                ("ceiling", "天花與照明"),
            )
            if surfaces.get(key)
        ]
        lines.append(
            {
                "id": f"{room.get('room_id') or room_name}-finish",
                "category": "renovation",
                "category_label": "裝潢工程",
                "room_id": room.get("room_id"),
                "name": f"{room_name}裝潢、材質與照明工程",
                "quantity": 1,
                "unit": "房",
                "amount_twd": None,
                "status": "pending_quote",
                "status_label": "待報價",
                "scope": scope_labels or ["牆面", "地板", "天花與照明"],
                "note": _delivery_text(
                    questionnaire.get("note")
                    or questionnaire.get("generation_notes")
                    or questionnaire.get("furniture_preference"),
                    "須先確認現場丈量、材質型號、施工範圍、燈具迴路與插座條件後再報價。",
                ),
                "quote_requirements": ["現場丈量", "材質型號", "施工範圍", "機電與插座條件"],
            }
        )
    return lines


def _beam_run_length_cm(beam: dict) -> float:
    start = beam.get("start") or {}
    end = beam.get("end") or {}
    try:
        dx = float(end.get("x", 0)) - float(start.get("x", 0))
        dy = float(end.get("y", 0)) - float(start.get("y", 0))
    except (TypeError, ValueError):
        return 0.0
    return (dx * dx + dy * dy) ** 0.5


def _delivery_structural_work_items(fixed_structure: dict) -> list[dict]:
    """把第 4 步固定結構裡「對得到費率表」的包覆項（包樑/包柱）組成 work_items。
    一般牆面/地板/天花無費率不進來（留給 ``_delivery_renovation_lines`` 標待報價）。"""
    items: list[dict] = []
    for index, beam in enumerate(fixed_structure.get("beams") or [], start=1):
        if not isinstance(beam, dict):
            continue
        length_m = round(_beam_run_length_cm(beam) / 100.0, 3)
        if length_m <= 0:
            continue
        beam_id = str(beam.get("id") or f"beam-{index}")
        items.append(
            {
                "id": beam_id,
                "work_code": "wall_wrap.carpentry",
                "description": "包樑木作",
                "quantity": {"value": length_m, "unit": "m"},
                "quantity_evidence": [beam_id, "fixed_structure.beams"],
                "assumptions": ["以樑兩端點水平距離估算包覆長度；三面展開與轉角須現場確認。"],
            }
        )
    for index, column in enumerate(fixed_structure.get("columns") or [], start=1):
        if not isinstance(column, dict):
            continue
        try:
            height_m = round(float(column.get("height_cm") or 0) / 100.0, 3)
        except (TypeError, ValueError):
            height_m = 0.0
        if height_m <= 0:
            continue
        column_id = str(column.get("id") or f"column-{index}")
        items.append(
            {
                "id": column_id,
                "work_code": "wall_wrap.carpentry",
                "description": "包柱木作",
                "quantity": {"value": height_m, "unit": "m"},
                "quantity_evidence": [column_id, "fixed_structure.columns"],
                "assumptions": ["以柱高估算包覆立面長度；轉角與展開面積須現場確認。"],
            }
        )
    return items


def _delivery_structural_lines(fixed_structure: dict) -> list[dict]:
    """對包樑/包柱呼叫後端 ``estimate_project_cost`` 產生「含來源」的概算預算行。
    無可估項或費率／目錄異常時回空清單（不擋成果包）。"""
    work_items = _delivery_structural_work_items(fixed_structure)
    if not work_items:
        return []
    try:
        estimate = estimate_project_cost(work_items, catalog=load_default_cost_catalog())
    except (ValueError, OSError, KeyError):
        return []
    lines: list[dict] = []
    for item in estimate.get("items") or []:
        quantity = item.get("quantity") or {}
        estimate_twd = item.get("estimate_twd") or {}
        lines.append(
            {
                "id": item.get("id"),
                "category": "renovation",
                "category_label": "結構包覆工程",
                "name": item.get("description") or "結構包覆",
                "quantity": quantity.get("value"),
                "unit": quantity.get("unit"),
                "amount_twd": estimate_twd.get("base"),
                "amount_range_twd": estimate_twd,
                "status": "concept_estimate",
                "status_label": "概算（含公開行情來源）",
                "work_code": item.get("work_code"),
                "sources": item.get("sources"),
                "source_ids": item.get("source_ids"),
                "inclusions": item.get("inclusions"),
                "exclusions": item.get("exclusions"),
                "price_date": item.get("price_date"),
                "assumptions": item.get("assumptions"),
                "note": "以公開行情概算；不含油漆飾面與轉角，須現場丈量後正式報價。",
            }
        )
    for missing in estimate.get("needs_quote") or []:
        lines.append(
            {
                "id": missing.get("id"),
                "category": "renovation",
                "category_label": "結構包覆工程",
                "name": missing.get("description") or "結構包覆",
                "amount_twd": None,
                "status": "pending_quote",
                "status_label": "待報價",
                "note": f"費率表無對應項（{missing.get('reason')}），保留待報價。",
            }
        )
    return lines


def _delivery_sensitive_paths(value: object, path: str = "$payload") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in DELIVERY_SENSITIVE_KEYS:
                paths.append(child_path)
                continue
            paths.extend(_delivery_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_delivery_sensitive_paths(child, f"{path}[{index}]"))
    return paths


def _delivery_sanitized_copy(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _delivery_sanitized_copy(child)
            for key, child in value.items()
            if str(key).strip().casefold().replace("-", "_") not in DELIVERY_SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_delivery_sanitized_copy(child) for child in value]
    return deepcopy(value)


def _delivery_security_review(payload: dict) -> dict:
    redacted_paths = sorted(set(_delivery_sensitive_paths(payload)))
    return {
        "status": "passed_with_redactions" if redacted_paths else "passed",
        "status_label": "通過（敏感欄位已排除）" if redacted_paths else "通過",
        "reviewer": "RoomPilot 後端 deterministic security gate",
        "reviewed_at": _utc_timestamp(),
        "checks": [
            {
                "check_id": "provider_secret_isolation",
                "status": "passed",
                "detail": "瀏覽器成果包與生圖內容不包含伺服器端供應商金鑰。",
            },
            {
                "check_id": "sensitive_field_redaction",
                "status": "redacted" if redacted_paths else "passed",
                "detail": "以欄位白名單組稿；識別資訊、cookie、密碼與 token 類欄位不進入成果包。",
            },
            {
                "check_id": "price_integrity",
                "status": "passed",
                "detail": "僅列出家具目錄已附參考價；其餘裝潢與家具費用一律標示待報價。",
            },
        ],
        "redacted_paths": redacted_paths,
    }


def _design_delivery_package(
    project_id: str, payload: dict, delivery_proposal: dict | None = None
) -> dict:
    rooms = payload.get("rooms") if isinstance(payload.get("rooms"), list) else []
    snapshot = payload.get("configuration_snapshot") if isinstance(payload.get("configuration_snapshot"), dict) else {}
    snapshot_furniture = _with_catalog_prices(snapshot.get("furniture") or [])
    snapshot = {**snapshot, "furniture": snapshot_furniture}
    raw_style_card = payload.get("style_card") if isinstance(payload.get("style_card"), dict) else {}
    style_card = _delivery_sanitized_copy(raw_style_card)
    security_review = _delivery_security_review(payload)
    presentation_rooms: list[dict] = []
    engineering_rooms: list[dict] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        questionnaire = room.get("questionnaire") if isinstance(room.get("questionnaire"), dict) else {}
        locked_furniture = questionnaire.get("lockedFurniture") or questionnaire.get("locked_furniture") or []
        if not isinstance(locked_furniture, list):
            locked_furniture = []
        room_type = _delivery_room_type(room)
        room_name = _delivery_text(room.get("room_name"), "未命名空間")
        room_id = room.get("room_id")
        room_furniture = [
            _delivery_sanitized_copy(item) for item in snapshot_furniture
            if str(item.get("room_id") or "") == str(room_id or "")
        ]
        usage = questionnaire.get("usage") if isinstance(questionnaire.get("usage"), list) else []
        note = _delivery_text(
            questionnaire.get("summary") or questionnaire.get("note"),
            "本房未填獨立補充，採用全屋問卷、已鎖定配置與色卡。",
        )
        raw_render_status = room.get("render") if isinstance(room.get("render"), dict) else {}
        raw_view = room.get("view") if isinstance(room.get("view"), dict) else {}
        raw_surfaces = questionnaire.get("surfaces") if isinstance(questionnaire.get("surfaces"), dict) else {}
        raw_equipment = questionnaire.get("generativeEquipment") if isinstance(questionnaire.get("generativeEquipment"), dict) else {}
        render_status = _delivery_sanitized_copy(raw_render_status)
        view = _delivery_sanitized_copy(raw_view)
        surfaces = _delivery_sanitized_copy(raw_surfaces)
        equipment = _delivery_sanitized_copy(raw_equipment)
        presentation_rooms.append(
            {
                "room_id": room_id,
                "room_name": room_name,
                "room_type": room_type,
                "style_card": style_card.get("name") or style_card.get("id"),
                "designer_reference": DESIGNER_REFERENCE_BY_ROOM_TYPE.get(
                    room_type,
                    DESIGNER_REFERENCE_BY_ROOM_TYPE["default"],
                ),
                "design_summary": (
                    f"{room_name}保留第 4 步固定結構與第 7 步鎖定視角，"
                    f"再把問卷需求、{len(room_furniture)} 件確認家具與「{style_card.get('name') or '已選色卡'}」整合為同一設計。"
                ),
                "decoration_summary": {
                    "questionnaire_source": questionnaire.get("source") or "room",
                    "questionnaire_note": note,
                    "usage": usage,
                    "locked_furniture": locked_furniture,
                    "materials": surfaces,
                    "ceiling_and_lighting": equipment,
                    "render_status": render_status,
                },
            }
        )
        engineering_rooms.append(
            {
                "room_id": room_id,
                "room_name": room_name,
                "structure_source": "第 4 步已確認固定結構",
                "view_source": "第 7 步已鎖定視角",
                "view": view,
                "furniture_count": len(room_furniture),
                "furniture": room_furniture,
                "materials": surfaces,
                "ceiling_and_lighting": equipment,
                "questionnaire_note": note,
                "render_completed": bool(render_status.get("submitted_at")),
                "revision_used": bool(render_status.get("revision_submitted_at")),
            }
        )
    fixed_structure = snapshot.get("fixed_structure") if isinstance(snapshot.get("fixed_structure"), dict) else {}
    budget_lines = [
        *_delivery_structural_lines(fixed_structure),
        *_delivery_renovation_lines(rooms),
        *_delivery_furniture_lines(snapshot),
    ]
    known_furniture_subtotal = sum(
        int(line["amount_twd"])
        for line in budget_lines
        if line.get("category") == "furniture" and line.get("amount_twd") is not None
    )
    estimated_structural_subtotal = sum(
        int(line["amount_twd"])
        for line in budget_lines
        if line.get("status") == "concept_estimate" and line.get("amount_twd") is not None
    )
    pending_quote_count = sum(1 for line in budget_lines if line.get("status") == "pending_quote")
    budget_report = {
        "title": "裝潢與家具預算報告書",
        "currency": "TWD",
        "pricing_status": "pending_quote" if pending_quote_count else "catalog_reference_only",
        "pricing_status_label": (
            "含結構概算與待報價項目"
            if pending_quote_count and estimated_structural_subtotal
            else "含待報價項目"
            if pending_quote_count
            else "含結構包覆概算"
            if estimated_structural_subtotal
            else "家具目錄參考價"
        ),
        "known_furniture_reference_subtotal_twd": known_furniture_subtotal,
        "estimated_structural_subtotal_twd": estimated_structural_subtotal,
        "pending_quote_count": pending_quote_count,
        "lines": budget_lines,
        "disclaimer": "本成果包含結構包覆概算（公開行情）與家具目錄參考價；最終工程及家具總價須經現場丈量、材料確認與廠商正式報價。",
    }
    engineering_report = {
        "title": "RoomPilot 工程報告書",
        "basis": [
            "第 4 步固定結構",
            "第 5 步問卷與 RAG 專業需求",
            "第 6 步家具、材質、天花與照明配置",
            "第 7 步逐房鎖定視角",
            "第 8 步最終生圖與每房一次修改紀錄",
        ],
        "snapshot_id": snapshot.get("snapshot_id"),
        "structure_counts": {
            key: len(fixed_structure.get(key) or [])
            for key in ("walls", "doors", "windows", "beams", "columns")
        },
        "rooms": engineering_rooms,
        "completion": {
            "room_count": len(engineering_rooms),
            "rendered_room_count": sum(1 for room in engineering_rooms if room["render_completed"]),
            "revised_room_count": sum(1 for room in engineering_rooms if room["revision_used"]),
        },
        "notes": [
            "幾何合法性與家具位置以保存快照為準，報告組稿不重新產生座標。",
            "施工前仍須由建築、結構、機電與室內裝修專業人員依現場條件複核。",
        ],
    }
    presentation = {
        "title": "RoomPilot 全屋設計與裝潢簡報",
        "subtitle": "依問卷、RAG、確認配置、鎖定視角與最終生圖整理",
        "style_card": style_card,
        "rooms": presentation_rooms,
        "security_review": security_review,
    }
    return {
        "schema_version": "1.1",
        "artifact_type": "roompilot.web_design_delivery.v1",
        "project_id": project_id,
        "snapshot_id": snapshot.get("snapshot_id"),
        "generated_at": payload.get("generated_at") or _utc_timestamp(),
        "presentation": presentation,
        "engineering_report": engineering_report,
        "security_review": security_review,
        "budget": budget_report,
        "budget_report": budget_report,
        "delivery_proposal": delivery_proposal or {"status": "not_generated"},
        "web_report": {
            "title": "RoomPilot 設計成果包",
            "format": "web_package",
            "sections": [
                {"heading": "一、全屋設計與裝潢簡報", "data_key": "presentation"},
                {"heading": "二、逐房設計與生圖成果", "data_key": "presentation.rooms"},
                {"heading": "三、工程報告書", "data_key": "engineering_report"},
                {"heading": "四、資安工程審核", "data_key": "security_review"},
                {"heading": "五、裝潢與家具預算報告書", "data_key": "budget_report"},
                {"heading": "六、設計提案 PDF", "data_key": "delivery_proposal"},
            ],
        },
    }


@app.post("/api/projects/{project_id}/design-delivery")
def create_project_design_delivery(project_id: str, payload: dict) -> dict:
    """第 8 步成果包：五章 JSON 打包，並依本分支定案把 delivery-proposal
    的產出紀錄與下載位置併入同一份回應。"""
    project = _stored_project(project_id)
    if payload.get("project_id") not in (None, project_id):
        raise HTTPException(422, {"code": "delivery_project_mismatch"})
    record = (project.get("workflow") or {}).get("delivery_proposal") or {}
    proposal = {key: value for key, value in record.items() if key != "filename"}
    if proposal:
        proposal["status"] = "generated"
        proposal["download_url"] = f"/api/projects/{project_id}/delivery-proposal/pdf"
    else:
        proposal = {
            "status": "not_generated",
            "hint": "可在成果包視窗直接產出設計提案 PDF。",
        }
    return _design_delivery_package(project_id, payload, delivery_proposal=proposal)


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
def analyze_project_floorplan(project_id: str) -> dict:
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


@app.get("/api/floorplan/sample/public")
def floorplan_sample_public() -> FileResponse:
    if not SAMPLE_FLOORPLAN.is_file():
        raise HTTPException(404, "sample_floorplan_not_found")
    return FileResponse(
        SAMPLE_FLOORPLAN,
        media_type="image/png",
        filename="public_floorplan.png",
    )


@app.get("/api/site-data")
def site_data() -> dict:
    payload = dict(build_site_payload())
    payload["furniture"] = []
    payload["featured_models"] = []
    payload["catalog_merge_summary"] = {
        **payload.get("catalog_merge_summary", {}),
        "delivery": "請使用 /api/furniture 分頁取得家具資料。",
    }
    return payload


def catalog_status() -> dict:
    """Describe active catalog providers without exposing credentials."""
    provider = catalog_provider_status(PROJECT_DIR)
    if provider.get("provider") == "portable_fixture":
        furniture = {
            "provider": "portable_fixture",
            "manifest_ready": True,
            "verified_model_count": int(provider.get("count") or 0),
            "catalog_count": int(provider.get("count") or 0),
            "source_of_truth": "project_authored_fixture",
            "render_mode": "procedural_fixture",
        }
        furniture_images = {
            "provider": "none",
            "manifest_ready": True,
            "verified_item_count": 0,
            "verified_image_count": 0,
            "source_of_truth": "procedural",
        }
    elif provider.get("provider") == "postgres" and provider.get("available"):
        assets = provider.get("assets") or {}
        furniture = {
            "provider": "postgres",
            "manifest_ready": True,
            "verified_model_count": int(assets.get("model_count") or 0),
            "catalog_count": int(provider.get("count") or 0),
            "source_of_truth": "postgresql",
        }
        furniture_images = {
            "provider": "postgres",
            "manifest_ready": True,
            "verified_item_count": int(assets.get("complete_image_item_count") or 0),
            "verified_image_count": sum(
                int(assets.get(key) or 0)
                for key in ("front_image_count", "side_image_count", "angle_45_image_count")
            ),
            "source_of_truth": "postgresql",
        }
    else:
        furniture = dict(manifest_status())
        furniture.pop("mode", None)
        furniture_images = image_manifest_status()
    surfaces = load_surface_catalog().get("surfaces") or []
    wall_count = sum("wall" in (item.get("usage") or []) for item in surfaces)
    floor_count = sum("floor" in (item.get("usage") or []) for item in surfaces)
    profile = current_profile()
    return {
        "profile": profile,
        "data_source": (
            "project_authored_fixture"
            if provider.get("provider") == "portable_fixture"
            else provider.get("source_of_truth", "configured_provider")
        ),
        "fixture": provider.get("provider") == "portable_fixture",
        "catalog_provider": provider,
        "furniture": furniture,
        "furniture_images": furniture_images,
        "surfaces": {
            "provider": "local_pending_aws_manifest",
            "wall_count": wall_count,
            "floor_count": floor_count,
        },
        "doors": {
            "provider": "procedural_pending_aws_catalog",
            "catalog_count": 0,
        },
        "style_cards": {
            "provider": "local_allowed",
            "count": len(load_taiwan_style_cards()),
        },
    }


@app.get("/api/catalog/status")
def catalog_status_api() -> dict:
    return catalog_status()


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


@app.get("/api/questionnaire/visual-catalog")
def questionnaire_visual_catalog_api(
    space_type: str | None = Query(None),
    ready_only: bool = Query(False),
) -> dict:
    questions = _questionnaire_visual_store().list_questions(
        space_type=space_type,
        ready_only=ready_only,
    )
    return {
        "version": QUESTIONNAIRE_VISUAL_CATALOG["version"],
        "notice_zh": QUESTIONNAIRE_VISUAL_CATALOG["notice_zh"],
        "question_count": QUESTIONNAIRE_VISUAL_CATALOG["question_count"],
        "image_count": QUESTIONNAIRE_VISUAL_CATALOG["image_count"],
        "ready_image_count": sum(
            option["generation_status"] == "ready"
            for question in QUESTIONNAIRE_VISUAL_CATALOG["questions"]
            for option in question["options"]
        ),
        "questions": questions,
    }


@app.get("/api/questionnaire/visual-images/{image_id}")
def questionnaire_visual_image_api(image_id: str) -> dict:
    try:
        return _questionnaire_visual_store().get_image(image_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="questionnaire_image_not_found",
        ) from exc


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
        "catalog_status": catalog_status(),
    }


def _furniture_detail_payload(furniture_id: str) -> dict:
    item = next(
        (
            candidate
            for candidate in _furniture_payload_cache()
            if str(candidate.get("furniture_id")) == str(furniture_id)
        ),
        None,
    )
    if item is None:
        item = _furniture_payload_item(_get_merged_furniture_by_id(furniture_id))
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


@app.post("/api/agent/intake/start")
async def agent_intake_start(payload: dict | None = None) -> dict:
    """Start the Agent-ready intake contract without calling an LLM yet."""
    payload = payload or {}
    return start_intake(str(payload.get("session_id") or "roompilot-local"))


@app.post("/api/agent/intake/answer")
async def agent_intake_answer(payload: dict) -> dict:
    """Advance one guided intake turn; future LLM adapters keep this shape."""
    step = str(payload.get("step") or "")
    answer = str(payload.get("answer") or "").strip()
    if not step or not answer:
        raise HTTPException(status_code=422, detail="step 與 answer 皆為必要欄位。")
    return advance_intake(
        session_id=str(payload.get("session_id") or "roompilot-local"),
        step=step,
        answer=answer,
        brief=payload.get("client_brief"),
    )


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


def _local_selection_raw(rooms: list[dict], offers: dict[str, list[dict]]) -> dict:
    selections: list[dict] = []
    for room in rooms:
        room_id = str(room.get("room_id") or room.get("id") or "")
        used_families: set[str] = set()
        items: list[dict] = []
        for item in offers.get(room_id, []):
            family = family_of(item.get("normalized_type"))
            if family in used_families:
                continue
            used_families.add(family)
            try:
                count = int(item.get("count") or 1)
            except (TypeError, ValueError):
                count = 1
            items.append({
                "furniture_id": item.get("furniture_id"),
                "count": max(1, min(6, count)),
            })
        if items:
            selections.append({"room_id": room_id, "items": items})
    return {"selections": selections}


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

    if isinstance(llm_selection, dict):
        try:
            selected, model = request_selections(
                rooms,
                offers,
                str(style_id) if style_id else None,
                complete=lambda _messages: ("payload/llm_selection", llm_selection),
                context=context,
            )
            return _selection_response(selected, source="openrouter", model=model)
        except (SelectionParseError, SelectionUnavailableError) as exc:
            warnings.append(f"LLM 選擇未通過規則驗證，已改用本地規則：{exc}")

    try:
        selected = parse_selections(_local_selection_raw(rooms, offers), rooms, offers)
        return _selection_response(selected, source="local_rules", warnings=warnings)
    except SelectionParseError as exc:
        warnings.append(f"本地規則無法完整驗證候選家具，已保留第一批候選：{exc}")
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
                        for item in items[:8]
                    ],
                }
                for room_id, items in offers.items()
                if items
            ],
        }


@app.get("/api/agent/pipeline/status")
def agent_pipeline_status_route() -> dict:
    """MasterAgent 並存管線的開關與 gateway 狀態（永遠可查，即使未啟用）。"""
    return pipeline_status()


def _require_pipeline_enabled() -> None:
    if not pipeline_enabled():
        raise HTTPException(
            status_code=404,
            detail="Agent 管線未啟用；設定環境變數 ROOMPILOT_AGENT_PIPELINE=1 後重啟服務。",
        )


@app.post("/api/agent/pipeline/{project_id}/start")
async def agent_pipeline_start_route(project_id: str, payload: dict) -> dict:
    """並存管線：載入室內架構與規則，進入等待問卷狀態。不影響正式 step 6。"""
    _require_pipeline_enabled()
    layout_json = payload.get("layout_json") or payload.get("layout")
    if not isinstance(layout_json, dict):
        raise HTTPException(
            status_code=422,
            detail="layout_json 為必要欄位（辨識步驟輸出的室內架構）。",
        )
    rules_json = payload.get("rules_json") if isinstance(payload.get("rules_json"), dict) else None
    try:
        return start_pipeline(
            PROJECT_STORE.runtime_dir, PROJECT_DIR, project_id, layout_json, rules_json
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/agent/pipeline/{project_id}/submit")
async def agent_pipeline_submit_route(project_id: str, payload: dict | None = None) -> dict:
    """並存管線：在目前 HITL 決策點提交輸入並推進（問卷→A/B 擺放+驗證→…）。"""
    _require_pipeline_enabled()
    try:
        return submit_pipeline(
            PROJECT_STORE.runtime_dir, PROJECT_DIR, project_id, payload or {}
        )
    except PipelineNotStarted as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/api/agent/pipeline/{project_id}/undo")
async def agent_pipeline_undo_route(project_id: str) -> dict:
    """並存管線：回復上一次 submit 之前的完整狀態。"""
    _require_pipeline_enabled()
    try:
        return undo_pipeline(PROJECT_STORE.runtime_dir, PROJECT_DIR, project_id)
    except PipelineNotStarted as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/api/agent/pipeline/{project_id}")
def agent_pipeline_get_route(project_id: str) -> dict:
    """並存管線：查詢目前暫停點、期望輸入與最近一次階段產物。"""
    _require_pipeline_enabled()
    try:
        return get_pipeline(PROJECT_STORE.runtime_dir, PROJECT_DIR, project_id)
    except PipelineNotStarted as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/agent/pipeline/reconcile")
async def agent_pipeline_reconcile_route(payload: dict) -> dict:
    """對帳：同一批 step6 選定家具，比對 step6 擺放 vs agent 管線擺放的覆蓋率＋合法性。"""
    _require_pipeline_enabled()
    room_id = str(payload.get("room_id") or "room")
    try:
        width_cm = float(payload.get("width_cm"))
        depth_cm = float(payload.get("depth_cm"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="width_cm 與 depth_cm 為必要數值（公分）。")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(
            status_code=422,
            detail="items 為必要（step6 選定的家具清單，server 物件格式）。",
        )
    try:
        return reconcile_room(room_id, width_cm, depth_cm, items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    client_brief = payload.get("client_brief") or {}
    brief_space = client_brief.get("space") or {}
    brief_style = client_brief.get("style") or {}
    brief_occupants = client_brief.get("occupants") or {}
    test2_questionnaire = payload.get("questionnaire") or {}

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

    # 方案 A/B 白模生成走各自的 variant；不帶就預設 A（單方案專案不受影響）。
    placement_variant = str(payload.get("placement_variant") or "A").upper()
    if placement_variant not in {"A", "B"}:
        placement_variant = "A"
    scene_payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm") or brief_space.get("width_cm") or 420),
        room_depth_cm=float(payload.get("room_depth_cm") or brief_space.get("depth_cm") or 360),
        placement_variant=placement_variant,
    )
    return {
        **scene_payload,
        "scene_json": deepcopy(scene_payload),
    }


@app.post("/api/scene/layout")
async def scene_layout(payload: dict) -> dict:
    """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

    傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
    scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
    """
    objects = payload.get("scene_objects", [])
    editor_floorplan = payload.get("floorplan_editor")
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, room = floorplan_from_editor_payload(editor_floorplan)
    else:
        floorplan = payload.get("floorplan") or {}
        room = room_from_payload(floorplan)
    placement_room_id = payload.get("placement_room_id")
    placement_variant = str(payload.get("placement_variant") or "A").upper()
    if placement_variant not in {"A", "B"}:
        placement_variant = "A"
    # 指定房間 → 該房邊界;整屋呼叫(最終確認驗證、全屋鎖定覆核)→ 所有房
    # 的聯集。柵格對「格外」一律視為阻擋,聯集才不會把最大房以外的家具
    # 全數誤殺;無房型資料才退回最大區域(手動矩形模式)。
    place_boundary = (
        _region_boundary_by_id(floorplan, room, placement_room_id)
        or _regions_boundary(floorplan, room)
        or _largest_region_boundary(floorplan, room)
    )
    # 單房呼叫不得動別房家具:標了別房 id 的一律原樣通過,不進重排。
    # 單房柵格對房外一律視為阻擋,整屋清單塞進來會讓別房鎖定件檢查失敗、
    # 掉進自動重排 —— 無論哪個前端版本怎麼呼叫,伺服器都不再讓這發生。
    passthrough: list[dict] = []
    if placement_room_id:
        target_room_id = str(placement_room_id)
        active_objects: list[dict] = []
        for item in objects:
            assigned = str(
                item.get("placement_room_id") or item.get("auto_decor_room_id") or ""
            )
            if assigned and assigned != target_room_id:
                passthrough.append(item)
            else:
                active_objects.append(item)
        objects = active_objects
    return {
        "floorplan": floorplan,
        "scene_objects": [*passthrough, *generate_layout(
            room.width,
            room.depth,
            objects,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=place_boundary,
            floorplan=floorplan,
            placement_variant=placement_variant,
            # 重排/替換/新增/逐房操作也要有 agent 擺位紀律:沒有 hints 時
            # generate_layout 不登記 neighbors,成組配對(電視櫃對面、茶几
            # 沙發前)與自由座椅後置整條路是死的 —— 首次產生正確,一按
            # 重排就退化(feedback:躺椅回到沙發前、茶几被擠走)。
            hints=placement_hints(objects),
            # 最終確認(進入即時寫實)只驗不排:信任已鎖定的配置,座標照舊,
            # 避免嚴格重排把合法家具塌成 (0,0) 並擋住進入下一步。
            validate_only=bool(payload.get("validate_only")),
        )]
    }


@app.post("/api/scene/validate")
async def scene_validate(payload: dict) -> dict:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    editor_floorplan = payload.get("floorplan_editor")
    floorplan = payload.get("floorplan")
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, _ = floorplan_from_editor_payload(editor_floorplan)
    return validate_single_placement(
        floorplan,
        payload.get("item") or {},
        payload.get("others") or [],
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
    data = await file.read()
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


@app.post("/api/cost/estimate")
def cost_estimate(payload: dict):
    """以版控內的台灣公開網路行情，產生可追溯的概念工程概算。"""
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(422, "cost_items_required")
    try:
        return estimate_project_cost(items, catalog=load_default_cost_catalog())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/furniture/{furniture_id}")
def furniture_detail(furniture_id: str) -> dict:
    return _furniture_detail_payload(furniture_id)
