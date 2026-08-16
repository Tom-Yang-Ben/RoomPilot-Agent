from __future__ import annotations

import random
from typing import Any

from ..agent.knowledge import affinity_permits, family_of, is_outdoor_item


def choose_furniture_items(
    plan: dict[str, Any],
    furniture: list[dict[str, Any]],
    random_seed: str | int | None = None,
    room_width_cm: float | None = None,
    room_depth_cm: float | None = None,
    preferred_colors: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """回傳 (選中的家具, 找不到可用型號的類型清單)。

    找不到型號的類型必須回報 —— 使用者勾了「已選」卻默默消失,體驗上像 bug。
    """
    style_id = plan["style_id"]
    chosen: list[dict[str, Any]] = []
    unavailable: list[str] = []
    used_ids: set[str] = set()
    preferred_colors = preferred_colors or []

    def style_score(item: dict[str, Any]) -> float:
        if item.get("primary_style") == style_id:
            return 120

        for style in item.get("style_candidates", []):
            if style.get("style_id") == style_id:
                try:
                    score = float(style.get("score", 0))
                except (TypeError, ValueError):
                    score = 0
                if score <= 0:
                    return 0
                return 76 + score * 18

        return 0

    def color_score(item: dict[str, Any]) -> float:
        if not preferred_colors:
            return 0

        color_text = str(item.get("color") or "").lower()
        name_text = f"{item.get('name_zh_raw') or ''} {item.get('name_en') or ''}".lower()
        score = 0.0
        for color in preferred_colors:
            token = str(color).lower()
            if token and (token in color_text or token in name_text):
                score += 12
        return score

    def scale_score(item: dict[str, Any]) -> float:
        if not room_width_cm or not room_depth_cm:
            return 0

        width = _size_cm(item, "width", 120)
        depth = _size_cm(item, "depth", 60)
        largest_room_side = max(room_width_cm, room_depth_cm)
        shortest_room_side = min(room_width_cm, room_depth_cm)

        if width > largest_room_side * 0.92 or depth > largest_room_side * 0.92:
            return -48
        if max(width, depth) > shortest_room_side * 0.82:
            return -18
        return 8

    def harmony_penalty(item: dict[str, Any]) -> float:
        text = f"{item.get('color') or ''} {item.get('name_zh_raw') or ''} {item.get('name_en') or ''}".lower()
        loud_tokens = {
            "multicolour",
            "multi-colour",
            "red",
            "orange",
            "yellow",
            "pink",
            "turquoise",
            "pattern",
            "stripe",
            "animal",
        }
        calm_styles = {"scandinavian", "minimalist_muji", "wabi_sabi", "nordic_modern"}
        if style_id in calm_styles and any(token in text for token in loud_tokens):
            return -36
        return 0

    def total_score(item: dict[str, Any], rng: random.Random) -> float:
        confidence = item.get("style_confidence") or 0
        try:
            confidence_score = float(confidence) * 12
        except (TypeError, ValueError):
            confidence_score = 0

        return (
            style_score(item)
            + color_score(item)
            + scale_score(item)
            + harmony_penalty(item)
            + confidence_score
            + rng.random() * 8
        )

    # 單房選件的房型適配:LLM/需求清單可能夾帶不合房型的家具(客廳點名雙人床、
    # 電競椅)。單房沒有 room_regions,_affinity_room_id 使不上力,故在選件源頭
    # 依 space_type 濾掉房型不符者;泛用件(未列 ROOM_AFFINITY)一律保留。
    # space_type 未給時不套房型過濾(affinity_permits 對空房型一律放行)——
    # 直接呼叫者(測試/舊路徑)無房型脈絡,不能拿預設 living_room 誤殺床。
    from ..agent.knowledge import affinity_permits

    space_type = plan.get("space_type")
    required_types = [
        required_type
        for required_type in plan.get("required_furniture", [])
        if affinity_permits(required_type, space_type)
    ]

    for index, required_type in enumerate(required_types):
        candidates = [
            item
            for item in furniture
            if item.get("has_model")
            and item.get("furniture_id") not in used_ids
            and item.get("normalized_type") == required_type
            and catalog_item_matches_type_semantics(item, required_type)
            # 自動選件不挑戶外家具:型錄把庭院躺椅歸在 sofa/armchair 等室內
            # 類型,不濾就會出現「客廳戶外椅」。使用者精選路徑不經此處。
            and not is_outdoor_item(item)
        ]

        if not candidates:
            unavailable.append(required_type)
            continue

        rng = random.Random(f"{random_seed}:{style_id}:{required_type}:{index}") if random_seed not in (None, "") else random.Random(f"{style_id}:{required_type}:{index}")
        ranked = sorted(candidates, key=lambda item: total_score(item, rng), reverse=True)
        if random_seed not in (None, ""):
            top_pool = ranked[: min(len(ranked), 14)]
            selected = rng.choice(top_pool)
        else:
            selected = ranked[0]

        used_ids.add(selected["furniture_id"])
        chosen.append(selected)

    return chosen, unavailable


_BED_CONFLICT_TOKENS = (
    "wardrobe",
    "chest of",
    "drawer",
    "cabinet",
    "cupboard",
    "tv stand",
    "bookcase",
    "shelving",
    "mirror",
    "table",
    "chair",
    "sofa",
    "stool",
    "lamp",
    "衣櫃",
    "抽屜",
    "櫃體",
    "書櫃",
)
_BED_IDENTITY_TOKENS = (
    "bed frame",
    "loft bed",
    "day-bed",
    "daybed",
    "upholstered bed",
    "storage bed",
    "double bed",
    "single bed",
    "king size bed",
    "queen size bed",
    "base para cama",
    "床架",
)


def catalog_item_matches_type_semantics(item: dict[str, Any], requested_type: str) -> bool:
    """阻擋型錄分類與模型語意明顯矛盾的候選，避免櫃體被當成床。"""
    if requested_type not in {"bed", "bed-frame"}:
        return True
    name_text = " ".join(str(item.get(key) or "") for key in ("name_en", "name_zh_raw")).casefold()
    evidence_text = " ".join(
        str(item.get(key) or "")
        for key in ("name_en", "name_zh_raw", "category_label", "source_archive", "source_archive_path", "zip_entry")
    ).casefold()
    has_conflict = any(token in evidence_text for token in _BED_CONFLICT_TOKENS)
    has_bed_identity = any(token in name_text for token in _BED_IDENTITY_TOKENS)
    if has_conflict and not has_bed_identity:
        return False
    if not has_bed_identity:
        return False
    size = item.get("size_cm") or {}
    try:
        height = float(size.get("height") or 0)
    except (TypeError, ValueError):
        height = 0
    maximum_height = 240 if "loft bed" in name_text else 150
    return height <= maximum_height


def selected_furniture_items_from_questionnaire(
    questionnaire: dict[str, Any],
    furniture: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return exact furniture chosen in /library, using catalog data when available."""
    raw_items = questionnaire.get("selected_furniture") or []
    if not isinstance(raw_items, list):
        return []

    catalog_by_id = {
        item.get("furniture_id"): item
        for item in furniture
        if item.get("furniture_id")
    }
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    bed_selected = False

    appliance_types = {
        "refrigerator",
        "washer",
        "washing-machine",
        "dishwasher",
        "dryer",
        "oven",
        "microwave",
        "range-hood",
        "air-conditioner",
        "ceiling-cassette",
        "appliance",
    }

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        furniture_id = raw.get("furniture_id")
        if not furniture_id or furniture_id in used_ids:
            continue

        raw_type = str(raw.get("normalized_type") or raw.get("type") or "").casefold()
        raw_model_url = str(raw.get("model_url") or raw.get("glb_url") or "").casefold()
        if raw_type in appliance_types or "/models/ikea/appliance/" in raw_model_url:
            # Appliances remain questionnaire/render context, never 2D/3D objects.
            continue

        catalog_item = catalog_by_id.get(furniture_id, {})
        merged = {**catalog_item, **raw}
        size = raw.get("size_cm") or raw.get("dimensions") or catalog_item.get("size_cm") or {}
        merged["size_cm"] = {
            "width": size.get("width") or size.get("w"),
            "depth": size.get("depth") or size.get("d"),
            "height": size.get("height") or size.get("h"),
        }
        merged["name_zh_raw"] = (
            raw.get("name_zh_raw")
            or raw.get("name_zh")
            or catalog_item.get("name_zh_raw")
            or catalog_item.get("name_zh")
            or catalog_item.get("name_en")
            or furniture_id
        )
        merged["normalized_type"] = raw.get("normalized_type") or catalog_item.get("normalized_type")
        merged["model_url"] = raw.get("model_url") or catalog_item.get("model_url")
        merged["primary_style"] = raw.get("primary_style") or catalog_item.get("primary_style")
        merged["has_model"] = bool(raw.get("has_model") or catalog_item.get("has_model") or merged.get("model_url"))

        user_confirmed_without_model = bool(
            raw.get("position_locked")
            or raw.get("user_specified")
            or raw.get("source") == "roompilot_2d"
        )
        if (
            not merged["normalized_type"]
            or (not merged["has_model"] and not user_confirmed_without_model)
            or (
                merged["has_model"]
                and not catalog_item_matches_type_semantics(merged, merged["normalized_type"])
            )
        ):
            continue

        # ponytail: 同房只留一張床。exact 選件原本只比 furniture_id(上面 used_ids),
        # 兩件床族商品(bed + bed-frame,或兩張不同床)都會留 → 擺位端把兩床相貼、
        # 無走道、壓住房門(feedback floor04 臥室)。臥室房型皆單床(DORMITORY→bed,
        # 入住人數只展開餐椅不展開床),故只折 bed 家族;床頭櫃/餐椅/沙發等可複數,
        # 不在此去重。與 _merge_exact_and_chosen 的 family_of 摺疊同語意——exact 路徑
        # (selected_furniture_exact=True)繞過該摺疊,漏套於此補上。
        if family_of(merged["normalized_type"]) == "bed":
            if bed_selected:
                continue
            bed_selected = True

        selected.append(merged)
        used_ids.add(furniture_id)

    return selected

def _size_cm(item: dict[str, Any], key: str, fallback: float) -> float:
    size = item.get("size_cm") or {}
    raw = size.get(key)
    if raw in (None, "", "-"):
        return fallback
    try:
        return float(raw)
    except (TypeError, ValueError):
        return fallback
