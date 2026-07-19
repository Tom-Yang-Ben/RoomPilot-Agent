from __future__ import annotations

import copy
import io
import json
import math
import os
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from ..catalog.style_db import sanitize_size_cm
from ..floorplan.room_analysis import ROOM_TYPE_OPTIONS, attach_room_regions, room_type_option
from ..upgrade3d.dxf_parser import list_plans, parse_dxf_bytes, parse_dxf_file
from ..upgrade3d.wall_openings import build_opening_wall_geometry
from .scene_service import (
    _flip_parsed_z,
    _largest_region_boundary,
    _region_boundary_by_id,
    _regions_boundary,
    build_scene_payload,
    generate_layout,
    get_openrouter_status,
    load_local_env,
    room_from_payload,
    validate_single_placement,
)
from .floorplan_vlm import annotate_floorplan, vlm_enabled
from .intake_service import advance_intake, start_intake
from .project_models import (
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
from .layout_service import build_layout_proposal, build_style_variant, layout_catalog_size_cm
from .project_store import ProjectConflictError, ProjectStore, WorkflowTooLargeError
from .requirements_service import (
    analyze_special_requirements,
    build_local_constraints,
    normalize_requirement_answers,
)
from .runtime_paths import project_runtime_dir
from .style_cards import load_taiwan_style_cards, style_card_render_intent


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
MOODBOARD_DIR = STATIC_DIR / "moodboard_assets"
STYLE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "furniture_catalog_6styles_zh.json"
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
EXTERNAL_IMPORT_PATH = BASE_DIR.parent / "catalog" / "data" / "舊友：12種風格與JSON" / "external_furniture_import_index.json"
DATASET_DIR = PROJECT_DIR / "dataset"
# 樣品平面圖清單:testdata/dxf 含 floor01–21(floor21 = Demo 基準圖);
# 舊值 testdata/pic/temp 只有 7 張外來圖,選單裡挑不到 Demo 基準圖
PLAN_DIR = PROJECT_DIR / "testdata" / "dxf"
SAMPLE_GLB_DIR = PROJECT_DIR / "testdata" / "sample_glb"
FLOORPLAN_EXTENSIONS = (".dxf", ".png", ".jpg", ".jpeg")
MAX_FLOORPLAN_BYTES = 20 * 1024 * 1024
_EXTERNAL_GLB_ZIP_SEARCH_DIRS = (
    DATASET_DIR,
    PROJECT_DIR / "dataset" / "style_rag",
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
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    entry_name = furniture.get("zip_entry")
    if not entry_name:
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
                for variant in _external_zip_entry_variants(entry_name):
                    if variant in names:
                        return archive_path, variant
        except (OSError, zipfile.BadZipFile):
            continue

    lookup = _external_zip_entry_lookup()
    for variant in _external_zip_entry_variants(entry_name):
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
    if furniture.get("zip_entry"):
        if _resolve_external_zip_entry(furniture) is not None:
            return True, "外部 GLB zip 可用"
        return False, "外部家具有 zip_entry，但目前找不到對應 GLB zip 或 zip 內 entry。"

    if not furniture.get("glb_absolute_path") and not furniture.get("glb_relative_path"):
        return False, "這件家具沒有設定 GLB 路徑。"

    if _resolve_glb_path(furniture) is not None:
        return True, "GLB 可用"

    if _remote_glb_url(furniture):
        return False, "遠端 GLB 尚未驗證，暫不提供載入。"

    return False, "資料有記錄，但 dataset/ 中找不到對應的 GLB 檔案(請先從雲端下載 dataset)。"


@lru_cache(maxsize=1)
def load_style_database() -> dict:
    return json.loads(STYLE_DB_PATH.read_text(encoding="utf-8"))


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
    }


@lru_cache(maxsize=1)
def _furniture_payload_cache() -> tuple[dict, ...]:
    return tuple(_furniture_payload_item(item) for item in _merged_furniture_catalog_cached())


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
    if furniture.get("zip_entry"):
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


@app.post("/api/projects", status_code=201, response_model=ProjectResponse)
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


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, request: Request) -> dict:
    return {"project": _stored_project(request, project_id)}


@app.put("/api/projects/{project_id}/workflow", response_model=ProjectResponse)
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


@app.post(
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


@app.get("/api/projects/{project_id}/floorplan/source")
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


@app.post(
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
    analysis = _recognize_floorplan_bytes(
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


@app.post(
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
    analysis = _recognize_floorplan_bytes(
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


@app.post(
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
    requirements = normalize_requirement_answers(payload.model_dump(exclude=excluded))
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


@app.post(
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
    suggestion = analyze_special_requirements(
        requirements,
        valid_room_ids=valid_room_ids,
        allow_openrouter=payload.allow_openrouter,
    )
    return {"suggestion": suggestion}


@app.post(
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
    local_constraints = build_local_constraints(requirements)
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


@app.post(
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


@app.post(
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


@app.post(
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


@app.post(
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


@app.post(
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


@app.post(
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
            "placement_authority": "roompilot.engine",
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


@app.post(
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


@app.get(
    "/api/projects/{project_id}/renders",
    response_model=ProjectRenderListResponse,
)
def list_project_renders(project_id: str, request: Request) -> dict:
    try:
        renders = _project_store(request).list_renders(project_id)
    except KeyError as exc:
        raise HTTPException(404, {"code": "project_not_found", "message": "找不到專案。"}) from exc
    return {"renders": [_public_render_record(record) for record in renders]}


@app.get("/api/projects/{project_id}/renders/{render_id}/png")
def download_project_render(project_id: str, render_id: str, request: Request) -> FileResponse:
    try:
        render = _project_store(request).get_render(project_id, render_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, {"code": "render_not_found", "message": "找不到這張 PNG。"}) from exc
    path = render["path"]
    if not path.is_file():
        raise HTTPException(410, {"code": "render_file_missing", "message": "PNG 紀錄存在，但檔案已遺失。"})
    return FileResponse(path, media_type="image/png", filename=render["filename"])


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
    return _page("scene.html")


@app.get("/panorama")
def panorama_page() -> FileResponse:
    return _page("panorama/panorama.html")


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
    }


@app.get("/api/scene/bootstrap")
def scene_bootstrap() -> dict:
    return {
        "styles": _style_payloads(),
        "taiwan_style_cards": load_taiwan_style_cards(),
        "surface_catalog": load_surface_catalog(),
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


@app.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    client_brief = payload.get("client_brief") or {}
    brief_space = client_brief.get("space") or {}
    brief_style = client_brief.get("style") or {}
    brief_occupants = client_brief.get("occupants") or {}

    questionnaire = {
        "space_type": payload.get("space_type") or brief_space.get("type") or "living_room",
        "style_preference": payload.get("style_preference") or (brief_style.get("preferred") or ["auto"])[0],
        "style_card_id": payload.get("style_card_id"),
        "required_furniture": payload.get("required_furniture", []),
        "selected_furniture": payload.get("selected_furniture", []),
        "custom_furniture": payload.get("custom_furniture", []),
        "preferred_colors": payload.get("preferred_colors") or brief_style.get("colors", []),
        "custom_colors": payload.get("custom_colors", []),
        "personal_notes": payload.get("personal_notes", ""),
        "keep_window_clear": bool(payload.get("keep_window_clear", "keep_window_clear" in client_brief.get("constraints", []))),
        "keep_door_clear": bool(payload.get("keep_door_clear", "keep_door_clear" in client_brief.get("constraints", []))),
        "need_storage": bool(payload.get("need_storage", "storage" in client_brief.get("needs", []))),
        "prefer_low_saturation": bool(payload.get("prefer_low_saturation", "low_saturation" in brief_style.get("colors", []))),
        "client_brief": client_brief,
        "occupants": brief_occupants,
        "preferred_materials": brief_style.get("materials", []),
        "floorplan_filename": payload.get("floorplan_filename"),
        "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
        "floorplan_scale_m": payload.get("floorplan_scale_m"),
        "floorplan_override": payload.get("floorplan_override"),  # 人工確認修正的窗/門段

        "wall_option": payload.get("wall_option", "auto"),
        "floor_option": payload.get("floor_option", "auto"),
        "furniture_random_seed": payload.get("furniture_random_seed"),
    }

    return build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm") or brief_space.get("width_cm") or 420),
        room_depth_cm=float(payload.get("room_depth_cm") or brief_space.get("depth_cm") or 360),
    )


@app.post("/api/scene/layout")
async def scene_layout(payload: dict) -> dict:
    """前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。

    傳 floorplan(含 wall_segments)可重建 DXF 房間形狀;
    scene_objects 帶 position_locked 的項目(使用者拖曳過)位置仍合法就不重排。
    """
    objects = payload.get("scene_objects", [])
    floorplan = payload.get("floorplan") or {}
    room = room_from_payload(floorplan)
    room_ids = list(dict.fromkeys(
        str(item.get("placement_room_id"))
        for item in objects
        if item.get("placement_room_id")
    ))
    if room_ids:
        by_instance: dict[str, dict] = {}
        for room_id in room_ids:
            room_objects = [item for item in objects if str(item.get("placement_room_id")) == room_id]
            boundary = _region_boundary_by_id(floorplan, room, room_id)
            if boundary is None:
                continue
            for item in generate_layout(
                room.width,
                room.depth,
                room_objects,
                room=room,
                regions_boundary=boundary,
                place_boundary=boundary,
                hints=payload.get("hints"),
                window_segments=floorplan.get("window_segments") or [],
                door_segments=floorplan.get("door_segments") or [],
                floorplan=floorplan,
            ):
                by_instance[str(item.get("instance_id"))] = item
        return {
            "scene_objects": [
                by_instance.get(str(item.get("instance_id")), item)
                for item in objects
            ]
        }
    return {
        "scene_objects": generate_layout(
            room.width,
            room.depth,
            objects,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=_largest_region_boundary(floorplan, room),
            hints=payload.get("hints"),
            window_segments=floorplan.get("window_segments") or [],
            door_segments=floorplan.get("door_segments") or [],
            floorplan=floorplan,
        )
    }


@app.post("/api/scene/validate")
async def scene_validate(payload: dict) -> dict:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    return validate_single_placement(
        payload.get("floorplan"),
        payload.get("item") or {},
        payload.get("others") or [],
        keep_door_clear=bool(payload.get("keep_door_clear")),
    )


@app.get("/api/furniture/{furniture_id}/model")
def furniture_model(furniture_id: str):
    furniture = _get_merged_furniture_by_id(furniture_id)
    return _model_response_for_merged_furniture(furniture)


@app.get("/api/furniture/{furniture_id}/model.gltf")
def furniture_model_gltf(furniture_id: str) -> JSONResponse:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    return JSONResponse(_gltf_payload_for_web(model_path_text, furniture_id))


@app.get("/api/furniture/{furniture_id}/buffer.bin")
def furniture_model_buffer(furniture_id: str) -> Response:
    furniture = _get_furniture_by_id(furniture_id)
    model_path_text = _get_model_path_for_furniture(furniture)
    _, binary_payload = _parse_glb(model_path_text)
    return Response(content=binary_payload, media_type="application/octet-stream")


@app.get("/api/furniture/{furniture_id}/images/{image_index}")
def furniture_model_image(furniture_id: str, image_index: int) -> Response:
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


def _attach_recognized_doors(floorplan: dict, handoff: dict) -> None:
    """把 floorplan2dxf 交接 JSON 的門(影像管線偵測,DXF 圖層沒有)補進 floorplan。

    交接 cm 座標與 dxf_scale/ 同框(原點左下、y 向上);dxf_parser 把幾何平移到
    平面中心後輸出公尺,所以這裡用「牆 cm bbox 中心」做同一個平移,z 再取負
    (與 _flip_parsed_z 一致)。門只有中心點+寬度,方向取最近牆矩形的長軸。
    """
    # 只收高信心門(≥0.85,同管線交叉檢核門檻)——低分多是家具/淋浴間弧線拼的假門,
    # 顯示假門比漏門更誤導使用者確認流程
    doors_cm = [
        d.get("cm")
        for d in handoff.get("doors") or []
        if d.get("cm") and float(d.get("score") or 0) >= 0.85
    ]
    walls_cm = [w.get("cm") for w in handoff.get("walls") or [] if w.get("cm")]
    if not doors_cm or not walls_cm:
        return
    ccx = (min(w[0] for w in walls_cm) + max(w[2] for w in walls_cm)) / 2.0
    ccy = (min(w[1] for w in walls_cm) + max(w[3] for w in walls_cm)) / 2.0

    def nearest_wall_horizontal(cx: float, cy: float) -> bool:
        best, horiz = None, True
        for x0, y0, x1, y1 in walls_cm:
            dx = max(x0 - cx, 0, cx - x1)
            dy = max(y0 - cy, 0, cy - y1)
            d2 = dx * dx + dy * dy
            if best is None or d2 < best:
                best, horiz = d2, (x1 - x0) >= (y1 - y0)
        return horiz

    doors_m: list[dict] = []
    door_segments: list[dict] = []
    for d in doors_cm:
        cx, cy, width = float(d["cx"]), float(d["cy"]), float(d["width"])
        x_m = (cx - ccx) / 100.0
        z_m = -(cy - ccy) / 100.0          # y 向上 → z 向南(同 _flip_parsed_z)
        half = width / 200.0
        if nearest_wall_horizontal(cx, cy):
            seg = {"x1": x_m - half, "z1": z_m, "x2": x_m + half, "z2": z_m}
        else:
            seg = {"x1": x_m, "z1": z_m - half, "x2": x_m, "z2": z_m + half}
        doors_m.append({k: round(v, 3) for k, v in seg.items()})
        door_segments.append(
            {
                "start": {"x": round(seg["x1"] * 100, 2), "z": round(seg["z1"] * 100, 2)},
                "end": {"x": round(seg["x2"] * 100, 2), "z": round(seg["z2"] * 100, 2)},
            }
        )
    floorplan["doors"] = doors_m
    floorplan["door_segments"] = door_segments
    floorplan.update(build_opening_wall_geometry(floorplan))
    if isinstance(floorplan.get("stats"), dict):
        floorplan["stats"]["doors"] = len(doors_m)


def _attach_vlm_rooms(floorplan: dict, vlm: dict, handoff: dict) -> None:
    """VLM 房間標註(0~1000 正規化 bbox)→ 與牆同框的公尺座標(平面中心原點、z 翻轉)。

    fixed_utility(廚房/浴室)= 管線固定不可移動;outdoor(露台/陽台)不擺室內家具
    ——這兩類之後交給擺位邊界剔除。px bbox 也保留,前端疊回原圖用。
    """
    image = handoff.get("image") or {}
    scale = handoff.get("scale") or {}
    walls_cm = [w.get("cm") for w in handoff.get("walls") or [] if w.get("cm")]
    img_w, img_h = image.get("width_px"), image.get("height_px")
    cm_per_px = scale.get("cm_per_px")
    if not (img_w and img_h and cm_per_px and walls_cm):
        return
    ccx = (min(w[0] for w in walls_cm) + max(w[2] for w in walls_cm)) / 2.0
    ccy = (min(w[1] for w in walls_cm) + max(w[3] for w in walls_cm)) / 2.0

    def to_m(px_x: float, px_y: float) -> tuple[float, float]:
        cm_x = px_x * cm_per_px
        cm_y = (img_h - px_y) * cm_per_px          # 影像 y 向下 → cm 座標 y 向上
        return (cm_x - ccx) / 100.0, -(cm_y - ccy) / 100.0  # z 翻轉,同 _flip_parsed_z

    rooms = []
    for room in vlm.get("rooms") or []:
        n = room["bbox_norm"]
        px = [n[0] / 1000 * img_w, n[1] / 1000 * img_h, n[2] / 1000 * img_w, n[3] / 1000 * img_h]
        x0, z0 = to_m(px[0], px[1])
        x1, z1 = to_m(px[2], px[3])
        rooms.append({
            "label": room["label"],
            "label_zh": room["label_zh"],
            "kind": room["kind"],
            "evidence": room["evidence"],
            "bbox_px": [round(v, 1) for v in px],
            "bbox": [round(x0, 3), round(z0, 3), round(x1, 3), round(z1, 3)],
        })
    floorplan["rooms"] = rooms
    if isinstance(floorplan.get("stats"), dict):
        floorplan["stats"]["rooms"] = len(rooms)


def _recognize_floorplan_bytes(
    raw: bytes,
    name: str,
    scale_m: float | None = None,
    thickness: float = 0.18,
    height: float = 2.7,
    allow_openrouter: bool = False,
) -> dict:
    """平面圖影像(PNG/JPG/BMP)→ 牆/門/窗辨識(floorplan2dxf 管線)→ 3D 樓面 JSON。

    回傳:floorplan(dxf_parser 輸出,公尺、平面中心原點)、dxf_text(可直接餵
    /api/scene/generate 的 floorplan_dxf_text)、scale(比例尺推斷資訊)。
    DXF 檔直接解析不走影像管線。需要 vision extra(cv2);未安裝回 503。
    """
    import tempfile

    suffix = Path(name).suffix.lower()

    if suffix == ".dxf":
        dxf_text = raw.decode("utf-8", errors="ignore")
        try:
            # _flip_parsed_z:DXF y 朝北、three.js +z 朝南,不翻轉畫面會上下鏡像
            floorplan = _flip_parsed_z(
                parse_dxf_bytes(raw, name, scale_m, thickness, height)
            )
        except Exception as e:
            raise HTTPException(422, f"DXF 解析失敗: {e}")
        attach_room_regions(floorplan)
        floorplan["room_type_options"] = [dict(item) for item in ROOM_TYPE_OPTIONS]
        return {
            "floorplan": floorplan,
            "dxf_text": dxf_text,
            "scale": None,
            "source": "dxf",
            "openrouter": {
                "provider": "openrouter",
                "requested": bool(allow_openrouter),
                "sent": False,
                "status": "not_applicable_to_dxf",
            },
        }

    try:
        from ..floorplan import floorplan2dxf as fp
    except Exception:
        raise HTTPException(503, "影像辨識需要 vision 依賴:請以 `uv run --extra vision uvicorn ...` 啟動")

    with tempfile.TemporaryDirectory(prefix="rp_recognize_") as tmp:
        tmp_dir = Path(tmp)
        img_path = tmp_dir / f"input{suffix or '.png'}"
        img_path.write_bytes(raw)
        out_dxf = tmp_dir / "dxf" / "input.dxf"
        out_dxf.parent.mkdir(parents=True)
        cfg = fp.load_config(str(Path(fp.__file__).parent / "config.ini"))
        cfg.input = str(img_path)
        cfg.output = str(out_dxf)
        cfg.preview = str(tmp_dir / "chk.png")
        try:
            fp.run(cfg)
        except SystemExit as e:  # 管線內部以 sys.exit 報錯
            raise HTTPException(422, f"影像辨識失敗: {e}")
        except Exception as e:
            raise HTTPException(422, f"影像辨識失敗: {e}")

        # 優先用 dxf_scale/(牆厚錨定修正比例、公分單位 $INSUNITS=5):
        # dxf/ 是 config 固定比例,遇到需要 wall_min 修正的圖(如 floor08)
        # 尺寸會差到 2 倍;dxf_scale/ 才是交給引擎/前端的真實尺寸。
        scale_dxf = tmp_dir / "dxf_scale" / "input.dxf"
        dxf_source = scale_dxf if scale_dxf.is_file() else out_dxf
        dxf_text = dxf_source.read_text(encoding="utf-8", errors="ignore")

        scale_info = None
        handoff_data: dict | None = None
        handoff = tmp_dir / "json" / "input.json"
        if handoff.is_file():
            try:
                handoff_data = json.loads(handoff.read_text(encoding="utf-8"))
                scale_info = handoff_data.get("scale")
            except Exception:
                handoff_data = None
        preview_b64 = None
        preview_path = Path(cfg.preview)
        if preview_path.is_file():
            import base64
            preview_b64 = base64.b64encode(preview_path.read_bytes()).decode("ascii")
        try:
            # _flip_parsed_z:DXF y 朝北、three.js +z 朝南,不翻轉畫面會上下鏡像
            floorplan = _flip_parsed_z(
                parse_dxf_bytes(
                    dxf_text.encode("utf-8"),
                    "recognized.dxf",
                    scale_m,
                    thickness,
                    height,
                )
            )
        except Exception as e:
            raise HTTPException(422, f"辨識結果升維失敗: {e}")
        if handoff_data and dxf_source is scale_dxf:
            _attach_recognized_doors(floorplan, handoff_data)

        # VLM 語意層(選配):房間標籤/固定機能空間 + 門窗數第二意見。
        # 失敗回 None,不影響幾何辨識結果。
        vlm_info = None
        if allow_openrouter:
            load_local_env()
        provider_ready = bool(allow_openrouter and vlm_enabled())
        image_subtype = "jpeg" if suffix in (".jpg", ".jpeg") else ("bmp" if suffix == ".bmp" else "png")
        vlm = (
            annotate_floorplan(raw, mime=f"image/{image_subtype}")
            if allow_openrouter
            else None
        )
        if vlm:
            if handoff_data:
                _attach_vlm_rooms(floorplan, vlm, handoff_data)
            stats = floorplan.get("stats") or {}
            vlm_info = {
                "model": vlm["model"],
                "door_count": vlm["door_count"],
                "window_count": vlm["window_count"],
                "printed_dimensions": vlm["printed_dimensions"],
                # 交叉檢核:VLM 與 CV 管線的門窗數差距大 → 值得人工確認
                "counts_agree": (
                    vlm["window_count"] is not None
                    and abs(vlm["window_count"] - int(stats.get("windows") or 0)) <= 1
                ),
            }
        attach_room_regions(floorplan)
        floorplan["room_type_options"] = [dict(item) for item in ROOM_TYPE_OPTIONS]
        openrouter_info = {
            "provider": "openrouter",
            "requested": bool(allow_openrouter),
            "sent": provider_ready,
            "status": (
                "suggested"
                if vlm
                else ("unavailable" if allow_openrouter else "not_requested")
            ),
            "model": vlm.get("model") if vlm else None,
        }
        return {
            "floorplan": floorplan,
            "dxf_text": dxf_text,
            "scale": scale_info,
            "source": "image",
            "preview_png_base64": preview_b64,
            "vlm": vlm_info,
            "openrouter": openrouter_info,
        }


@app.post("/api/floorplan/recognize")
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
    return _recognize_floorplan_bytes(
        raw,
        name,
        scale_m,
        thickness,
        height,
        allow_openrouter,
    )


@app.get("/api/sample-furniture")
def sample_furniture() -> dict:
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
    path = SAMPLE_GLB_DIR / Path(name).name
    if not path.is_file():
        raise HTTPException(404, f"furniture not found: {name}")
    return FileResponse(path, media_type="model/gltf-binary")
