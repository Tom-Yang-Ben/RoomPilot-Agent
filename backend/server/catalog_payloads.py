"""型錄 payload 組裝（佇列 7 巨石拆分第一批，2026-08-03）。

內容全部自 backend/server/main.py 原樣搬入（純搬家、零行為改變）：
型錄合併鍵與變體判定、風格候選合併與去重、payload 欄位組裝
（scene／card 兩種形狀）、讀取邊界正規化（placement_surface、
style_candidates 去重、尺寸合理性標記）、JSON 離線快取與 facet 選項計算。

依賴注入：``_model_status`` 與 ``load_style_database`` 由 main.py 在 import
完成後注入（``catalog_payloads._model_status = _model_status``），不在這裡
import main——
1. main.py 已 import 本模組，反向 import 會形成循環。
2. 注入的是 main 的函式物件，globals 仍是 main 的命名空間；多支測試
   monkeypatch main 的模組屬性（_EXTERNAL_GLB_ZIP_SEARCH_DIRS、
   _resolve_external_zip_entry 等），GLB 可用性判定留在 main 才讀得到補丁值。
單獨 import 本模組（不經 main）時這兩個名稱不存在，呼叫會 NameError；
正式產品唯一進入點是 backend.server.main，不受影響。

provider 分派器（_furniture_payload_cache、_catalog_count_summary、
build_site_payload、_get_merged_furniture_by_id 等）刻意留在 main.py：
tests/test_postgres_single_source_phase5.py 與
test_furniture_api_normalization.py 直接 monkeypatch
main.catalog_provider_mode、main.load_postgres_catalog、main._style_payloads
等屬性，分派器必須從 main 的命名空間讀取這些名稱，測試檔才能一行不改。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Callable

from ..catalog.placement_surface import FLOOR, placement_surface_for
from ..catalog.style_db import sanitize_size_cm
from .services.cloud_models import cloud_model_url, cloudfront_required
from .services.cloud_images import cloud_image_urls, cloud_primary_image_url


# 由 main.py 於 import 完成後注入（見檔頭說明）。
_model_status: Callable[[dict], tuple[bool, str]]
load_style_database: Callable[[], dict]


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
    }


@lru_cache(maxsize=1)
def _json_furniture_payload_cache() -> tuple[dict, ...]:
    return tuple(_furniture_payload_item(item) for item in _merged_furniture_catalog_cached())


def _dedupe_style_candidates(candidates: object) -> list[dict]:
    """同一個 style_id 只留分數最高的一筆。

    JSON 路徑走 _merge_style_candidates 已經去重，PostgreSQL 路徑沒有——實測 7958 筆
    裡有 781 筆帶著重複的 style_id，排序與信心值都會被灌水（QA 型錄項）。
    """
    if not isinstance(candidates, list):
        return []
    best: dict[str, dict] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        style_id = str(candidate.get("style_id") or "").strip()
        if not style_id:
            continue
        current = best.get(style_id)
        if current is None or _candidate_score(candidate) > _candidate_score(current):
            best[style_id] = candidate
    return sorted(best.values(), key=_candidate_score, reverse=True)


def _normalize_catalog_payload(items: tuple[dict, ...]) -> tuple[dict, ...]:
    """PostgreSQL 與離線 JSON 的共同出口，統一補上兩件事。

    1. placement_surface：第 6 步的牆界、碰撞與淨空只對落地家具有意義；花瓶、抱枕、
       壁掛層架帶著 footprint 進去算就會「放不下」而卡在待處理清單（QA #7）。
       分類規則由 backend/catalog/placement_surface.py 定義，這裡只負責標記。
    2. style_candidates 去重，避免同一個 style_id 重複灌高排序。
    """
    normalized = []
    for item in items:
        entry = dict(item)
        entry.setdefault(
            "placement_surface",
            placement_surface_for(
                entry.get("normalized_type"),
                entry.get("name_zh_raw") or entry.get("name_zh") or entry.get("name_en"),
            ),
        )
        if entry.get("style_candidates"):
            entry["style_candidates"] = _dedupe_style_candidates(entry["style_candidates"])
        if isinstance(entry.get("style_codes"), list):
            # 來源 view 有 781 筆 style_codes 內部重複，會讓同一個風格被重複灌高排序。
            entry["style_codes"] = list(dict.fromkeys(entry["style_codes"]))
        if _implausible_for_type(entry):
            # 468cm 寬的「床」其實是斗櫃。留在型錄可查，但不參與自動選件與擺放，
            # 否則整間臥室會被一件標錯的家具吃掉。
            entry["size_is_implausible"] = True
            entry["placement_surface"] = entry.get("placement_surface") or FLOOR
        normalized.append(entry)
    return tuple(normalized)


# 各族系的合理最大邊長（公分）。超過就代表這一列的型別標錯了——QA 實測
# abo-beds-19 是一個 468cm 寬的六斗櫃，卻被標成 bed。
_MAX_PLAUSIBLE_WIDTH_CM = {
    "bed": 260.0,
    "bed-frame": 260.0,
    "bedside-table": 120.0,
    "dining-chair": 90.0,
    "office-chair": 100.0,
    "coffee-table": 200.0,
    "tv-bench": 320.0,
    "desk": 320.0,
}


def _implausible_for_type(item: dict) -> bool:
    limit = _MAX_PLAUSIBLE_WIDTH_CM.get(str(item.get("normalized_type") or ""))
    if limit is None:
        return False
    size = item.get("size_cm") or {}
    try:
        width = float(size.get("width") or item.get("width_cm") or 0)
    except (TypeError, ValueError):
        return False
    return width > limit


def _normalize_catalog_item(item: dict) -> dict:
    """單筆版的 :func:`_normalize_catalog_payload`。

    單品查詢也必須走同一道正規化，否則第 6 步從清單點進詳情時，同一件家具的
    placement_surface 與 style_candidates 會前後不一致。
    """
    return _normalize_catalog_payload((item,))[0]


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
def _json_catalog_count_summary() -> dict:
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


_FURNITURE_STYLE_FILTER_OPTIONS = (
    {"style_id": "scandinavian", "style_name_zh": "北歐風"},
    {"style_id": "japanese", "style_name_zh": "日式"},
    {"style_id": "modern_minimal", "style_name_zh": "現代簡約"},
    {"style_id": "cream", "style_name_zh": "奶油風"},
    {"style_id": "industrial", "style_name_zh": "工業風"},
    {"style_id": "american", "style_name_zh": "美式"},
)


def _style_filter_options() -> list[dict]:
    # The furniture endpoint must not load the full catalog JSON merely to label
    # the six stable UI filters.  Full style presentation remains /api/styles.
    return [dict(style) for style in _FURNITURE_STYLE_FILTER_OPTIONS]
