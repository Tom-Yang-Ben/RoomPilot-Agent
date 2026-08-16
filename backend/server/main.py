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
from .project_schema import ProjectSchemaUpgradeRequired
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
from .delivery_package import (
    _delivery_amount_twd,
    _delivery_structural_lines,
    _price_lookup_keys,
    build_design_delivery_package,
)
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
from .project_routes import create_project_router
from .public_routes import create_public_router
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

# Build the public router first so its helper exports (notably
# _layout_json_from_analysis) are available to project routes. Include routers
# in the original URL-resolution order.
_public_router, _public_route_exports = create_public_router(globals())
globals().update(_public_route_exports)
_project_router, _project_route_exports = create_project_router(globals())
globals().update(_project_route_exports)
app.include_router(_project_router)
app.include_router(_public_router)
