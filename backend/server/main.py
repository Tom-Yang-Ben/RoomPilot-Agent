from __future__ import annotations

import io
import csv
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
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
from ..agent.select import SelectionParseError, SelectionUnavailableError, parse_selections, request_selections
from .questionnaire_visuals import (
    QuestionnaireVisualStore,
    load_questionnaire_visual_catalog,
)
from ..catalog.style_db import sanitize_size_cm
from ..catalog.cloud_catalog import load_official_catalog
from ..floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)
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
    room_from_payload,
    scene_object_in_boundary,
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


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent


def _project_path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


STATIC_DIR = BASE_DIR / "static"
MOODBOARD_DIR = STATIC_DIR / "moodboard_assets"
STYLE_ENRICHMENT_DB_PATH = (
    BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_6styles_zh.json"
)
CLOUD_CATALOG_PATH = (
    BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_cloud_9350.json"
)
CLOUD_MANIFEST_PATH = _project_path_from_env(
    "ROOMPILOT_GLB_MANIFEST_PATH",
    BASE_DIR.parent
    / "catalog"
    / "data"
    / "manifests"
    / "glb_upload_all_result.csv",
)
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
EXTERNAL_IMPORT_PATH = BASE_DIR.parent / "catalog" / "data" / "舊友：12種風格與JSON" / "external_furniture_import_index.json"
DATASET_DIR = PROJECT_DIR / "dataset"
PLAN_DIR = PROJECT_DIR / "testdata" / "pic" / "temp"
SAMPLE_GLB_DIR = PROJECT_DIR / "testdata" / "sample_glb"
SAMPLE_FLOORPLAN_630 = PROJECT_DIR / "testdata" / "png" / "builder_plan_630.png"
PROJECT_STORE = ProjectStore(project_runtime_dir(PROJECT_DIR))
for legacy_runtime in legacy_runtime_dirs(PROJECT_DIR):
    PROJECT_STORE.import_runtime(legacy_runtime)
QUESTIONNAIRE_VISUAL_CATALOG = load_questionnaire_visual_catalog()
QUESTIONNAIRE_VISUAL_STORE: QuestionnaireVisualStore | None = None
_QUESTIONNAIRE_VISUAL_STORE_LOCK = Lock()
FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
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

# GLB 實檔可能在 dataset/ 的不同層(依組員從雲端下載後的擺法)
_DATASET_GLB_ROOTS = [
    DATASET_DIR,
    DATASET_DIR / "ikea_glb_db" / "ikea抓取家具glb_中文命名版",
]

app = FastAPI(title="AI 室內風格與家具配置展示系統")
app.add_middleware(GZipMiddleware, minimum_size=1024)


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
app.mount("/docs-assets", StaticFiles(directory=MOODBOARD_DIR), name="docs-assets")


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


@lru_cache(maxsize=1)
def _dataset_glb_lookup() -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    conflicts: set[str] = set()
    if not DATASET_DIR.exists():
        return lookup

    def remember(key: str, path: Path) -> None:
        existing = lookup.get(key)
        if existing is not None and existing != path:
            conflicts.add(key)
            return
        lookup[key] = path

    for path in DATASET_DIR.rglob("*.glb"):
        if not path.is_file():
            continue
        for key in _glb_lookup_keys(path.name):
            remember(key, path)
        for root in _DATASET_GLB_ROOTS:
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            for key in _glb_lookup_keys(relative.as_posix()):
                remember(key, path)

    for key in conflicts:
        lookup.pop(key, None)
    return lookup


def _safe_relative_url(path_text: str | None, mount_prefix: str) -> str | None:
    if not path_text:
        return None
    return f"{mount_prefix}/{_normalize_posix_path(path_text)}"


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


def _external_zip_entry_variants(entry_name: object) -> list[str]:
    entry = _normalize_posix_path(str(entry_name or "").strip())
    if not entry:
        return []

    variants = [entry]
    if entry.startswith("downloaded-files/ABO/"):
        variants.append(entry.replace("downloaded-files/ABO/", "downloaded-files(furniture)/ABO/", 1))
    if entry.startswith("downloaded-files/"):
        variants.append(entry.replace("downloaded-files/", "downloaded-files(furniture)/", 1))
        variants.append(entry.replace("downloaded-files/", "downloaded-files(home apppliances)/", 1))
    if entry.startswith("ABO/"):
        variants.append(f"downloaded-files(furniture)/{entry}")
    variants.append(f"downloaded-files(furniture)/{entry}")
    variants.append(f"downloaded-files(home apppliances)/{entry}")
    return list(dict.fromkeys(variants))


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


def _resolve_glb_path(furniture: dict) -> Path | None:
    """依序嘗試:metadata 的絕對路徑 → 專案 dataset/ 下的相對路徑。"""
    absolute_text = furniture.get("glb_absolute_path")
    if absolute_text and Path(absolute_text).exists():
        return Path(absolute_text)

    relative_text = furniture.get("glb_relative_path")
    if relative_text:
        relative = _normalize_posix_path(relative_text)
        for root in _DATASET_GLB_ROOTS:
            candidate = root / relative
            if candidate.exists():
                return candidate
        lookup = _dataset_glb_lookup()
        for key in _glb_lookup_keys(relative):
            candidate = lookup.get(key)
            if candidate is not None and candidate.exists():
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

    return False, "資料有記錄，但 dataset/ 中找不到對應的 GLB 檔案(請先從雲端下載 dataset)。"


@lru_cache(maxsize=1)
def load_style_database() -> dict:
    return load_official_catalog(
        CLOUD_CATALOG_PATH,
        STYLE_ENRICHMENT_DB_PATH,
        CLOUD_MANIFEST_PATH,
    )


@lru_cache(maxsize=1)
def load_surface_catalog() -> dict:
    if not SURFACE_DB_PATH.exists():
        return {"schema_version": "1.0", "surfaces": [], "style_surface_profiles": {}}
    return json.loads(SURFACE_DB_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_external_import_index() -> dict:
    if not EXTERNAL_IMPORT_PATH.exists():
        return {"schema_version": "1.0", "items": [], "archives": []}
    return json.loads(EXTERNAL_IMPORT_PATH.read_text(encoding="utf-8"))


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
        "style_candidates": item.get("style_candidates", []),
        "style_confidence": item.get("style_confidence"),
        "style_assignment_source": item.get("style_assignment_source"),
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
        "style_candidates": item.get("style_candidates", []),
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
    }


@lru_cache(maxsize=1)
def _furniture_payload_cache() -> tuple[dict, ...]:
    return tuple(_furniture_payload_item(item) for item in _merged_furniture_catalog_cached())


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


def _get_external_furniture_by_id(furniture_id: str) -> dict:
    data = load_external_import_index()
    furniture = next((item for item in data.get("items", []) if item.get("furniture_id") == furniture_id), None)
    if not furniture:
        raise HTTPException(status_code=404, detail="找不到外部匯入家具。")
    return furniture


def _get_merged_furniture_by_id(furniture_id: str) -> dict:
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
        raise HTTPException(status_code=404, detail="找不到這件家具對應的 GLB 檔案(dataset/ 未就緒?)。")

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
                "moodboard_image_url": _safe_relative_url(
                    (style.get("moodboard_card_path") or "").replace("docs/moodboard_assets/", "", 1),
                    "/docs-assets",
                ),
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
    if item.get("primary_style") == style_id:
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
        )
    ).casefold()


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


@lru_cache(maxsize=1)
def build_site_payload() -> dict:
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
                    "card_image_url": _safe_relative_url(
                        card_path.replace("docs/moodboard_assets/", "", 1)
                        if card_path.startswith("docs/moodboard_assets/")
                        else card_path,
                        "/docs-assets",
                    ),
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
                "moodboard_image_url": _safe_relative_url(
                    (style.get("moodboard_card_path") or "").replace("docs/moodboard_assets/", "", 1),
                    "/docs-assets",
                ),
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
    furniture = dict(manifest_status())
    furniture.pop("mode", None)
    surfaces = load_surface_catalog().get("surfaces") or []
    wall_count = sum("wall" in (item.get("usage") or []) for item in surfaces)
    floor_count = sum("floor" in (item.get("usage") or []) for item in surfaces)
    return {
        "furniture": furniture,
        "furniture_images": image_manifest_status(),
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
    item = _get_merged_furniture_by_id(furniture_id)
    payload = _furniture_payload_item(item)
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
        _furniture_payload_cache()
        build_site_payload()
    except Exception as exc:
        print(f"[RoomPilot] catalog cache warmup skipped: {exc}")


@app.get("/api/scene/provider-status")
def scene_provider_status() -> dict:
    return get_openrouter_status()


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

    scene_payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm") or brief_space.get("width_cm") or 420),
        room_depth_cm=float(payload.get("room_depth_cm") or brief_space.get("depth_cm") or 360),
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
    place_boundary = (
        _region_boundary_by_id(floorplan, room, placement_room_id)
        or _largest_region_boundary(floorplan, room)
    )
    return {
        "floorplan": floorplan,
        "scene_objects": generate_layout(
            room.width,
            room.depth,
            objects,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=place_boundary,
            floorplan=floorplan,
            placement_variant=placement_variant,
        )
    }


_AUTO_DECOR_TYPES = {
    "rug": ("large-medium-rug", "runner-small-rug"),
    "plant": ("flower-pots-planter",),
    "light": ("floor-lamp",),
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
    if not candidates:
        raise HTTPException(
            409,
            {
                "code": "decor_model_missing",
                "message": f"型錄中找不到可用的{_AUTO_DECOR_LABELS[role]} GLB，已停止自動配置。",
            },
        )

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


def _curtain_catalog_item() -> dict:
    return {
        "furniture_id": "roompilot-auto-curtain",
        "normalized_type": "curtain",
        "name_zh_raw": "自動配置布簾",
        "size_cm": {"width": 240, "depth": 12, "height": 240},
        "model_url": "/static/models/roompilot-curtain.glb",
        "has_model": True,
        "auto_decor_role": "curtain",
        "position_locked": False,
    }


@app.post("/api/scene/decorate")
async def scene_decorate(payload: dict) -> dict:
    """依風格加入軟裝，所有最終座標仍由家具引擎決定。"""
    editor_floorplan = payload.get("floorplan_editor")
    if isinstance(editor_floorplan, dict) and editor_floorplan:
        floorplan, room = floorplan_from_editor_payload(editor_floorplan)
    else:
        floorplan = payload.get("floorplan") or {}
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
    if "curtain" in requested_roles:
        additions.append(_curtain_catalog_item())
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
            "engine": "furniture_engine",
        },
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
# 以下路由自原 app/backend/main.py 移植,供 frontend3d(React Three Fiber)使用
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
    data = await file.read()
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
    data = await file.read()
    calibration = _floorplan_json_field(calibration_json, "calibration", None)
    observations = _floorplan_json_field(ocr_json, "ocr", [])
    geometry = _floorplan_json_field(geometry_json, "geometry", [])
    observed_utilities = _floorplan_json_field(observed_utilities_json, "observed_utilities", [])
    brief = _floorplan_json_field(brief_json, "brief", {})
    provider = None
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
