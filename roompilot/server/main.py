from __future__ import annotations

import io
import json
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from ..catalog.style_db import sanitize_size_cm
from ..upgrade3d.dxf_parser import list_plans, parse_dxf_bytes, parse_dxf_file
from .scene_service import (
    _largest_region_boundary,
    _regions_boundary,
    build_scene_payload,
    generate_layout,
    get_openrouter_status,
    room_from_payload,
    validate_single_placement,
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
MOODBOARD_DIR = STATIC_DIR / "moodboard_assets"
STYLE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "ikea_furniture_style_database.json"
SURFACE_DB_PATH = BASE_DIR.parent / "catalog" / "data" / "surface_catalog.json"
EXTERNAL_IMPORT_PATH = BASE_DIR.parent / "catalog" / "data" / "external_furniture_import_index.json"
DATASET_DIR = PROJECT_DIR / "dataset"
PLAN_DIR = PROJECT_DIR / "testdata" / "pic" / "temp"
SAMPLE_GLB_DIR = PROJECT_DIR / "testdata" / "sample_glb"

# GLB 實檔可能在 dataset/ 的不同層(依組員從雲端下載後的擺法)
_DATASET_GLB_ROOTS = [
    DATASET_DIR,
    DATASET_DIR / "ikea_glb_db" / "ikea抓取家具glb_中文命名版",
]

app = FastAPI(title="AI 室內風格與家具配置展示系統")

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
    url = str(furniture.get("glb_absolute_path") or "").strip()
    return url if _is_remote_glb_url(url) else None


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
    if not furniture.get("glb_absolute_path") and not furniture.get("glb_relative_path"):
        return False, "這件家具沒有設定 GLB 路徑。"

    if _resolve_glb_path(furniture) is not None:
        return True, "GLB 可用"

    if _remote_glb_url(furniture):
        return True, "遠端 GLB URL 可用"

    return False, "資料有記錄，但 dataset/ 中找不到對應的 GLB 檔案(請先從雲端下載 dataset)。"


def load_style_database() -> dict:
    return json.loads(STYLE_DB_PATH.read_text(encoding="utf-8"))


def load_surface_catalog() -> dict:
    if not SURFACE_DB_PATH.exists():
        return {"schema_version": "1.0", "surfaces": [], "style_surface_profiles": {}}
    return json.loads(SURFACE_DB_PATH.read_text(encoding="utf-8"))


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
        if entry.get("_catalog_origin") == "import" and entry.get("furniture_id")
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
    raw = load_style_database()
    external_import = load_external_import_index()
    merged = _merge_furniture_catalog(raw.get("furniture", []), external_import.get("items", []))
    for item in merged:
        aliases = set(item.get("merged_furniture_ids") or [])
        aliases.add(str(item.get("furniture_id")))
        if furniture_id in aliases:
            return item
    raise HTTPException(status_code=404, detail="Furniture not found in merged catalog.")


def _external_glb_bytes(furniture: dict) -> bytes:
    archive_path = Path(furniture.get("source_archive_path") or "")
    entry_name = furniture.get("zip_entry")
    if not archive_path.exists() or not entry_name:
        raise HTTPException(status_code=404, detail="外部匯入模型來源不存在。")
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
    aliases = list(furniture.get("model_priority_ids") or [])
    aliases.extend(furniture.get("merged_furniture_ids") or [])
    if furniture.get("furniture_id") not in aliases:
        aliases.insert(0, furniture.get("furniture_id"))
    aliases = list(dict.fromkeys(alias for alias in aliases if alias))

    for candidate_id in aliases:
        try:
            external = _get_external_furniture_by_id(candidate_id)
            payload = _external_glb_bytes(external)
            if payload[:4] != b"glTF":
                continue
            return Response(content=payload, media_type="model/gltf-binary")
        except HTTPException:
            pass

    for candidate_id in aliases:
        try:
            catalog_item = _get_furniture_by_id(candidate_id)
            model_path_text = _get_model_path_for_furniture(catalog_item)
            _parse_glb(model_path_text)
            model_path = Path(model_path_text)
            return FileResponse(model_path, media_type="model/gltf-binary", filename=model_path.name)
        except (HTTPException, ValueError, OSError, json.JSONDecodeError):
            pass

    for candidate_id in aliases:
        try:
            catalog_item = _get_furniture_by_id(candidate_id)
            remote_url = _remote_glb_url(catalog_item)
            if remote_url:
                return _remote_glb_response(remote_url)
        except HTTPException:
            pass

    remote_url = _remote_glb_url(furniture)
    if remote_url:
        return _remote_glb_response(remote_url)

    raise HTTPException(status_code=404, detail="Merged furniture has no usable GLB model.")


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


def build_site_payload() -> dict:
    raw = load_style_database()
    surface_catalog = load_surface_catalog()
    external_import = load_external_import_index()
    furniture_items = _merge_furniture_catalog(raw.get("furniture", []), external_import.get("items", []))
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

    furniture_payload = []
    for item in furniture_items:
        has_model, model_reason = (
            (bool(item.get("has_model")), item.get("missing_model_reason"))
            if "has_model" in item
            else _model_status(item)
        )
        furniture_payload.append(
            {
                "furniture_id": item.get("furniture_id"),
                "name_en": item.get("name_en"),
                "name_zh_raw": item.get("name_zh_raw"),
                "category_label": item.get("category_label"),
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
                "model_url": _model_url_for_merged_item(item) if has_model else None,
                **_candidate_schema_fields(item, has_model),
            }
        )

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
        "furniture": furniture_payload,
        "surface_catalog": surface_catalog,
        "catalog_merge_summary": {
            "input_item_count": len(raw.get("furniture", [])) + len(external_import.get("items", [])),
            "merged_count": len(furniture_payload),
            "same_item_merged_count": sum(1 for item in furniture_items if len(item.get("merged_furniture_ids", [])) > 1),
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
    return _page("scene.html")


@app.get("/api/site-data")
def site_data() -> dict:
    return build_site_payload()


@app.get("/api/scene/provider-status")
def scene_provider_status() -> dict:
    return get_openrouter_status()


@app.post("/api/scene/generate")
async def generate_scene(payload: dict) -> dict:
    site_payload = build_site_payload()

    questionnaire = {
        "space_type": payload.get("space_type", "living_room"),
        "style_preference": payload.get("style_preference", "auto"),
        "required_furniture": payload.get("required_furniture", []),
        "custom_furniture": payload.get("custom_furniture", []),
        "preferred_colors": payload.get("preferred_colors", []),
        "custom_colors": payload.get("custom_colors", []),
        "personal_notes": payload.get("personal_notes", ""),
        "keep_window_clear": bool(payload.get("keep_window_clear", False)),
        "keep_door_clear": bool(payload.get("keep_door_clear", False)),
        "need_storage": bool(payload.get("need_storage", False)),
        "prefer_low_saturation": bool(payload.get("prefer_low_saturation", False)),
        "floorplan_filename": payload.get("floorplan_filename"),
        "floorplan_dxf_text": payload.get("floorplan_dxf_text"),
        "wall_option": payload.get("wall_option", "auto"),
        "floor_option": payload.get("floor_option", "auto"),
        "furniture_random_seed": payload.get("furniture_random_seed"),
    }

    return build_scene_payload(
        site_payload=site_payload,
        questionnaire=questionnaire,
        floorplan_path=payload.get("floorplan_filename"),
        room_width_cm=float(payload.get("room_width_cm", 420)),
        room_depth_cm=float(payload.get("room_depth_cm", 360)),
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
    return {
        "scene_objects": generate_layout(
            room.width * 100,
            room.depth * 100,
            objects,
            room=room,
            regions_boundary=_regions_boundary(floorplan, room),
            place_boundary=_largest_region_boundary(floorplan, room),
        )
    }


@app.post("/api/scene/validate")
async def scene_validate(payload: dict) -> dict:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    return validate_single_placement(
        payload.get("floorplan"),
        payload.get("item") or {},
        payload.get("others") or [],
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


@app.get("/api/furniture")
def sample_furniture() -> dict:
    files = (
        sorted(f for f in SAMPLE_GLB_DIR.iterdir() if f.suffix.lower() == ".glb")
        if SAMPLE_GLB_DIR.is_dir()
        else []
    )
    return {"furniture": [f.name for f in files]}


@app.get("/api/furniture/{name}")
def sample_furniture_file(name: str) -> FileResponse:
    if not name.lower().endswith(".glb"):
        raise HTTPException(404, f"not a glb: {name}")
    path = SAMPLE_GLB_DIR / Path(name).name
    if not path.is_file():
        raise HTTPException(404, f"furniture not found: {name}")
    return FileResponse(path, media_type="model/gltf-binary")
