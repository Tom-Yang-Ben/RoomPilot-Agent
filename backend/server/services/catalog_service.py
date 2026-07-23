"""型錄彙整與網站資料 payload(原 main.py 型錄區塊)。

載入風格資料庫/表面材質/外部匯入索引;合併家具型錄(catalog+import 去重、
風格候選合併);產生家具/風格 payload、篩選選項與 build_site_payload 快取。
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache

from fastapi import HTTPException

from ...catalog.style_db import sanitize_size_cm
from ..config import EXTERNAL_IMPORT_PATH, STYLE_DB_PATH, SURFACE_DB_PATH
from .glb_assets import _model_status
from .style_cards import load_taiwan_style_cards


def _safe_relative_url(path_text: str | None, mount_prefix: str) -> str | None:
    if not path_text:
        return None
    return f"{mount_prefix}/{_normalize_posix_path(path_text)}"


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
