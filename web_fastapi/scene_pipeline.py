from __future__ import annotations

import json
import math
import os
import random
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from furniture_engine.clearance import check_placement_with_clearance
from furniture_engine.models import ClearanceZone, FurnitureCatalogItem, PlacedFurniture, Room, Wall
from furniture_engine.placement import place_furniture

from .dxf_floorplan import parse_dxf_floorplan

PROJECT_DIR = Path(__file__).resolve().parent.parent
DOTENV_CANDIDATES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "web_fastapi" / ".env",
]


def load_local_env() -> None:
    for env_path in DOTENV_CANDIDATES:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_openrouter_status() -> dict[str, Any]:
    load_local_env()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("OPENROUTER_MODEL", "").strip()

    return {
        "enabled": bool(api_key and model),
        "has_api_key": bool(api_key),
        "has_model": bool(model),
        "model": model or None,
        "provider": "openrouter" if api_key and model else "fallback",
    }


STYLE_FALLBACKS = {
    "auto": "scandinavian",
    "unsure": "scandinavian",
    "": "scandinavian",
}

SPACE_DEFAULTS = {
    "living_room": ["sofa", "coffee-table", "tv-bench", "armchair", "bookcase"],
    "bedroom": ["bed", "bedside-table", "bookcase", "runner-small-rug"],
    "workspace": ["desk", "office-chair", "bookcase", "wall-shelf"],
    "dining_room": ["dining-table", "dining-chair", "sideboard"],
    "studio": ["sofa-bed", "coffee-table", "desk", "bookcase"],
}

FURNITURE_ALIASES = {
    "沙發": "sofa",
    "茶几": "coffee-table",
    "電視櫃": "tv-bench",
    "單椅": "armchair",
    "書櫃": "bookcase",
    "地毯": "large-medium-rug",
    "床": "bed",
    "床架": "bed-frame",
    "床頭櫃": "bedside-table",
    "書桌": "desk",
    "辦公椅": "office-chair",
    "餐桌": "dining-table",
    "餐椅": "dining-chair",
    "邊櫃": "sideboard",
    "壁架": "wall-shelf",
    "收納櫃": "cabinets-cupboard",
}

ENGINE_SPECIAL_TYPES = {"large-medium-rug", "runner-small-rug", "wall-shelf"}

CLEARANCE_PRESETS: dict[str, tuple[str, float]] = {
    "cabinets-cupboard": ("front", 0.55),
    "wardrobe": ("front", 0.6),
    "pax-wardrobe": ("front", 0.65),
}


def normalize_style_id(style_id: str | None, styles: list[dict[str, Any]]) -> str:
    if not style_id:
        return "scandinavian"

    normalized = STYLE_FALLBACKS.get(style_id, style_id)
    valid_ids = {style.get("style_id") for style in styles}
    return normalized if normalized in valid_ids else "scandinavian"


def normalize_required_furniture(raw_items: list[str], space_type: str) -> list[str]:
    normalized: list[str] = []

    for item in raw_items:
        if not item:
            continue
        mapped = FURNITURE_ALIASES.get(item, item)
        if mapped not in normalized:
            normalized.append(mapped)

    if normalized:
        return normalized

    return SPACE_DEFAULTS.get(space_type, SPACE_DEFAULTS["living_room"]).copy()


def _candidate_matches_style(item: dict[str, Any], style_id: str) -> bool:
    if item.get("primary_style") == style_id:
        return True
    return any(style.get("style_id") == style_id for style in item.get("style_candidates", []))


def _candidate_style_score(item: dict[str, Any], style_id: str) -> float:
    if item.get("primary_style") == style_id:
        return 120

    for style in item.get("style_candidates", []):
        if style.get("style_id") == style_id:
            try:
                return 76 + float(style.get("score", 0)) * 18
            except (TypeError, ValueError):
                return 76

    return 0


def _candidate_color_score(item: dict[str, Any], preferred_colors: list[str] | None) -> float:
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


def _candidate_scale_score(
    item: dict[str, Any],
    room_width_cm: float | None,
    room_depth_cm: float | None,
) -> float:
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


def _candidate_harmony_penalty(item: dict[str, Any], style_id: str) -> float:
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


def _candidate_total_score(
    item: dict[str, Any],
    style_id: str,
    preferred_colors: list[str] | None,
    room_width_cm: float | None,
    room_depth_cm: float | None,
    rng: random.Random,
) -> float:
    confidence = item.get("style_confidence") or 0
    try:
        confidence_score = float(confidence) * 12
    except (TypeError, ValueError):
        confidence_score = 0

    return (
        _candidate_style_score(item, style_id)
        + _candidate_color_score(item, preferred_colors)
        + _candidate_scale_score(item, room_width_cm, room_depth_cm)
        + _candidate_harmony_penalty(item, style_id)
        + confidence_score
        + rng.random() * 8
    )


def pick_furniture_candidate(
    furniture: list[dict[str, Any]],
    item_type: str,
    style_id: str,
    used_ids: set[str] | None = None,
    preferred_colors: list[str] | None = None,
    room_width_cm: float | None = None,
    room_depth_cm: float | None = None,
    random_seed: str | int | None = None,
    index_hint: int = 0,
    require_style: bool = False,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    used_ids = used_ids or set()
    exclude_ids = exclude_ids or set()

    candidates = [
        item
        for item in furniture
        if item.get("has_model")
        and item.get("normalized_type") == item_type
        and item.get("furniture_id") not in used_ids
        and item.get("furniture_id") not in exclude_ids
    ]
    if not candidates:
        return None

    scene_style_candidates = [item for item in candidates if _candidate_matches_style(item, style_id)]
    if scene_style_candidates:
        candidates = scene_style_candidates
    elif require_style:
        return None

    seed_prefix = f"{random_seed}:{style_id}:{item_type}:{index_hint}" if random_seed not in (None, "") else f"{style_id}:{item_type}:{index_hint}"
    rng = random.Random(seed_prefix)
    ranked = sorted(
        candidates,
        key=lambda item: _candidate_total_score(
            item,
            style_id,
            preferred_colors,
            room_width_cm,
            room_depth_cm,
            rng,
        ),
        reverse=True,
    )

    if random_seed not in (None, ""):
        top_pool = ranked[: min(len(ranked), 14)]
        return rng.choice(top_pool)
    return ranked[0]


def _openrouter_request(messages: list[dict[str, str]]) -> dict[str, Any] | None:
    status = get_openrouter_status()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = status["model"]
    site_url = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000")
    app_name = os.getenv("OPENROUTER_APP_NAME", "test_furniture scene planner")

    if not api_key or not model:
        return None

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": site_url,
            "X-Title": app_name,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def build_questionnaire_prompt(questionnaire: dict[str, Any], styles: list[dict[str, Any]]) -> list[dict[str, str]]:
    style_summaries = [
        {
            "style_id": style.get("style_id"),
            "style_name_zh": style.get("style_name_zh"),
            "keywords": style.get("keywords_zh", []),
            "main_colors": style.get("main_colors_zh", []),
        }
        for style in styles
    ]

    return [
        {
            "role": "system",
            "content": (
                "你是室內空間配置規劃助手。"
                "請把使用者的問卷整理成單一 JSON。"
                "只能輸出 JSON，不要加 markdown。"
                "JSON 欄位必須包含: "
                "style_id, space_type, preferred_colors, required_furniture, personal_requirements, layout_rules, summary_zh。"
                "required_furniture 只用家具類型英文 id，例如 sofa, coffee-table, tv-bench, bed, desk。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "questionnaire": questionnaire,
                    "available_styles": style_summaries,
                },
                ensure_ascii=False,
            ),
        },
    ]


def fallback_plan(questionnaire: dict[str, Any], styles: list[dict[str, Any]]) -> dict[str, Any]:
    style_id = normalize_style_id(questionnaire.get("style_preference"), styles)
    required = normalize_required_furniture(questionnaire.get("required_furniture", []), questionnaire.get("space_type", "living_room"))
    custom_furniture = normalize_required_furniture(
        questionnaire.get("custom_furniture", []),
        questionnaire.get("space_type", "living_room"),
    )
    notes = questionnaire.get("personal_notes", "").strip()
    all_required = []
    for item in required + custom_furniture:
        if item not in all_required:
            all_required.append(item)

    layout_rules = []
    if questionnaire.get("keep_window_clear"):
        layout_rules.append({"rule": "keep_window_clear", "message": "家具避免遮擋主要採光面。"})
    if questionnaire.get("keep_door_clear"):
        layout_rules.append({"rule": "keep_door_clear", "message": "主要動線與入口前方保持淨空。"})
    if questionnaire.get("need_storage"):
        layout_rules.append({"rule": "need_storage", "message": "優先保留具收納能力的家具。"})
    if questionnaire.get("prefer_low_saturation"):
        layout_rules.append({"rule": "prefer_low_saturation", "message": "優先低彩度與較安定的色彩。"})

    if notes:
        layout_rules.append({"rule": "personal_notes", "message": notes})

    return {
        "style_id": style_id,
        "space_type": questionnaire.get("space_type", "living_room"),
        "preferred_colors": questionnaire.get("preferred_colors", []),
        "required_furniture": all_required,
        "personal_requirements": notes,
        "layout_rules": layout_rules,
        "summary_zh": "已依問卷偏好整理出風格、家具需求與基本配置規則。",
    }


def build_scene_plan(questionnaire: dict[str, Any], styles: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    requested_style = normalize_style_id(questionnaire.get("style_preference"), styles)
    fixed_style_requested = questionnaire.get("style_preference") not in STYLE_FALLBACKS
    openrouter_output = _openrouter_request(build_questionnaire_prompt(questionnaire, styles))
    if openrouter_output:
        # The user selects a fixed style in the UI; LLM may explain choices, but should not switch style.
        openrouter_output["style_id"] = requested_style if fixed_style_requested else normalize_style_id(openrouter_output.get("style_id"), styles)
        openrouter_output["required_furniture"] = normalize_required_furniture(
            openrouter_output.get("required_furniture", []),
            openrouter_output.get("space_type", questionnaire.get("space_type", "living_room")),
        )
        for item in normalize_required_furniture(
            questionnaire.get("custom_furniture", []),
            questionnaire.get("space_type", "living_room"),
        ):
            if item not in openrouter_output["required_furniture"]:
                openrouter_output["required_furniture"].append(item)
        return "openrouter", openrouter_output

    return "fallback", fallback_plan(questionnaire, styles)


def choose_furniture_items(
    plan: dict[str, Any],
    furniture: list[dict[str, Any]],
    random_seed: str | int | None = None,
    room_width_cm: float | None = None,
    room_depth_cm: float | None = None,
    preferred_colors: list[str] | None = None,
) -> list[dict[str, Any]]:
    style_id = plan["style_id"]
    chosen: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    preferred_colors = preferred_colors or []

    for index, required_type in enumerate(plan.get("required_furniture", [])):
        selected = pick_furniture_candidate(
            furniture=furniture,
            item_type=required_type,
            style_id=style_id,
            used_ids=used_ids,
            preferred_colors=preferred_colors,
            room_width_cm=room_width_cm,
            room_depth_cm=room_depth_cm,
            random_seed=random_seed,
            index_hint=index,
        )
        if selected:
            used_ids.add(selected["furniture_id"])
            chosen.append(selected)

    return chosen


def _clamp_axis(value: float, room_min: float, room_max: float, item_size: float, margin: float = 18) -> float:
    low = room_min + item_size / 2 + margin
    high = room_max - item_size / 2 - margin
    if low > high:
        return (room_min + room_max) / 2
    return min(max(value, low), high)


def _size_cm(item: dict[str, Any], key: str, fallback: float) -> float:
    size = item.get("size_cm") or {}
    raw = size.get(key)
    if raw in (None, "", "-"):
        return fallback
    try:
        return float(raw)
    except (TypeError, ValueError):
        return fallback


def _rotated_footprint(width: float, depth: float, rotation: float) -> tuple[float, float]:
    radians = abs(rotation % 180) * 3.141592653589793 / 180
    cos_v = abs(math.cos(radians))
    sin_v = abs(math.sin(radians))
    return width * cos_v + depth * sin_v, width * sin_v + depth * cos_v


def _box_for(x: float, z: float, width: float, depth: float, clearance: float = 12) -> dict[str, float]:
    return {
        "left": x - width / 2 - clearance,
        "right": x + width / 2 + clearance,
        "top": z - depth / 2 - clearance,
        "bottom": z + depth / 2 + clearance,
    }


def _boxes_overlap(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (a["right"] <= b["left"] or a["left"] >= b["right"] or a["bottom"] <= b["top"] or a["top"] >= b["bottom"])


def _box_overlap_area(a: dict[str, float], b: dict[str, float]) -> float:
    overlap_x = max(0, min(a["right"], b["right"]) - max(a["left"], b["left"]))
    overlap_z = max(0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    return overlap_x * overlap_z


def _placement_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
) -> list[tuple[float, float, float]]:
    left = -room_width_cm / 2
    right = room_width_cm / 2
    top = -room_depth_cm / 2
    bottom = room_depth_cm / 2
    center_x = 0.0
    center_z = 0.0
    candidates: list[tuple[float, float, float]] = []

    if item_type == "tv-bench":
        candidates.extend([(center_x, top + depth / 2 + 24, 0), (-room_width_cm * 0.22, top + depth / 2 + 24, 0)])
    elif item_type == "sofa":
        candidates.extend([(center_x, bottom - depth / 2 - 36, 180), (-room_width_cm * 0.18, bottom - depth / 2 - 36, 180)])
    elif item_type == "coffee-table":
        candidates.extend([(center_x, center_z + 12, 0), (center_x, center_z - 18, 0)])
    elif item_type == "armchair":
        candidates.extend([(right - width / 2 - 30, center_z + 35, -35), (left + width / 2 + 30, center_z + 35, 35)])
    elif item_type == "bookcase":
        candidates.extend([(left + width / 2 + 20, top + depth / 2 + 20, 90), (right - width / 2 - 20, top + depth / 2 + 20, -90)])
    elif item_type in {"bed", "bed-frame", "sofa-bed"}:
        candidates.extend([(center_x, bottom - depth / 2 - 32, 180), (left + width / 2 + 28, center_z, 90)])
    elif item_type == "bedside-table":
        candidates.extend([(right - width / 2 - 22, bottom - depth / 2 - 34, 0), (left + width / 2 + 22, bottom - depth / 2 - 34, 0)])
    elif item_type == "desk":
        candidates.extend([(center_x, top + depth / 2 + 30, 0), (left + width / 2 + 24, center_z, 90)])
    elif item_type == "office-chair":
        candidates.extend([(center_x, top + depth + 88, 180), (left + width / 2 + 80, center_z, 90)])
    elif item_type == "dining-table":
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 36, 0)])
    elif item_type == "dining-chair":
        candidates.extend([(right - width / 2 - 40, center_z, 90), (left + width / 2 + 40, center_z, -90), (center_x, center_z + 80, 180)])
    elif item_type == "sideboard":
        candidates.extend([(right - width / 2 - 24, top + depth / 2 + 24, 0), (left + width / 2 + 24, top + depth / 2 + 24, 0)])
    elif item_type == "wall-shelf":
        candidates.extend([(left + width / 2 + 15, top + depth / 2 + 12, 0), (right - width / 2 - 15, top + depth / 2 + 12, 0)])
    elif item_type in {"large-medium-rug", "runner-small-rug"}:
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 24, 0)])
    else:
        candidates.append((center_x, center_z, 0))

    grid_x = [left + room_width_cm * ratio for ratio in (0.25, 0.5, 0.75)]
    grid_z = [top + room_depth_cm * ratio for ratio in (0.28, 0.5, 0.72)]
    for z in grid_z:
        for x in grid_x:
            candidates.append((x, z, 0))

    return candidates


def _resolve_collision_safe_position(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
    placed_boxes: list[dict[str, float]],
) -> tuple[float, float, float, dict[str, float]]:
    left = -room_width_cm / 2
    right = room_width_cm / 2
    top = -room_depth_cm / 2
    bottom = room_depth_cm / 2
    wall_margin = 18
    collision_clearance = 14
    ignores_collision = item_type in {"large-medium-rug", "runner-small-rug", "wall-shelf"}
    best: tuple[float, float, float, dict[str, float], float] | None = None

    for raw_x, raw_z, rotation in _placement_candidates(item_type, width, depth, room_width_cm, room_depth_cm):
        footprint_width, footprint_depth = _rotated_footprint(width, depth, rotation)
        x = _clamp_axis(raw_x, left, right, footprint_width, wall_margin)
        z = _clamp_axis(raw_z, top, bottom, footprint_depth, wall_margin)
        candidate_box = _box_for(x, z, footprint_width, footprint_depth, collision_clearance)
        overlap_score = sum(_box_overlap_area(candidate_box, box) for box in placed_boxes)

        if ignores_collision or overlap_score <= 0:
            return x, z, rotation, candidate_box

        if best is None or overlap_score < best[4]:
            best = (x, z, rotation, candidate_box, overlap_score)

    if best:
        return best[0], best[1], best[2], best[3]

    fallback_box = _box_for(0, 0, width, depth, collision_clearance)
    return 0, 0, 0, fallback_box


def _scene_cm_to_engine_m(
    x_cm: float,
    z_cm: float,
    room_width_cm: float,
    room_depth_cm: float,
) -> tuple[float, float]:
    return x_cm / 100 + room_width_cm / 200, z_cm / 100 + room_depth_cm / 200


def _engine_m_to_scene_cm(
    pos_x_m: float,
    pos_y_m: float,
    room_width_cm: float,
    room_depth_cm: float,
) -> tuple[float, float]:
    return round((pos_x_m - room_width_cm / 200) * 100, 2), round((pos_y_m - room_depth_cm / 200) * 100, 2)


def _build_engine_room(
    room_width_cm: float,
    room_depth_cm: float,
    parsed_floorplan: dict[str, Any] | None,
) -> Room:
    width_m = room_width_cm / 100
    depth_m = room_depth_cm / 100
    walls: list[Wall] = []

    if parsed_floorplan and parsed_floorplan.get("wall_segments"):
        for segment in parsed_floorplan.get("wall_segments", []):
            start = segment.get("start") or {}
            end = segment.get("end") or {}
            try:
                start_x = float(start.get("x", 0.0)) + width_m / 2
                start_y = float(start.get("z", 0.0)) + depth_m / 2
                end_x = float(end.get("x", 0.0)) + width_m / 2
                end_y = float(end.get("z", 0.0)) + depth_m / 2
            except (TypeError, ValueError):
                continue

            walls.append(Wall(start_x, start_y, end_x, end_y, thickness=0.12))

    if len(walls) < 2:
        walls = [
            Wall(0, 0, width_m, 0, thickness=0.12),
            Wall(width_m, 0, width_m, depth_m, thickness=0.12),
            Wall(width_m, depth_m, 0, depth_m, thickness=0.12),
            Wall(0, depth_m, 0, 0, thickness=0.12),
        ]

    return Room(width=width_m, depth=depth_m, walls=walls)


def _clearance_for_type(item_type: str | None) -> ClearanceZone | None:
    if not item_type:
        return None
    preset = CLEARANCE_PRESETS.get(item_type)
    if not preset:
        return None
    side, depth = preset
    return ClearanceZone(side=side, depth=depth)


def _build_catalog_item(item: dict[str, Any]) -> FurnitureCatalogItem:
    item_type = item.get("normalized_type") or "furniture"
    return FurnitureCatalogItem(
        type=item_type,
        name=item.get("name_zh_raw") or item.get("name_en") or item_type,
        width=_size_cm(item, "width", 120) / 100,
        depth=_size_cm(item, "depth", 60) / 100,
        height=_size_cm(item, "height", 80) / 100,
        style=item.get("primary_style"),
        glb_path=item.get("glb_absolute_path"),
        clearance=_clearance_for_type(item_type),
    )


def _scene_object_from_engine(
    source_item: dict[str, Any],
    placed: PlacedFurniture,
    room_width_cm: float,
    room_depth_cm: float,
) -> tuple[dict[str, Any], dict[str, float]]:
    width = _size_cm(source_item, "width", 120)
    depth = _size_cm(source_item, "depth", 60)
    height = _size_cm(source_item, "height", 80)
    scene_x_cm, scene_z_cm = _engine_m_to_scene_cm(
        placed.pos_x,
        placed.pos_y,
        room_width_cm,
        room_depth_cm,
    )
    footprint_width, footprint_depth = _rotated_footprint(width, depth, placed.rotation)
    footprint_box = _box_for(scene_x_cm, scene_z_cm, footprint_width, footprint_depth)

    return (
        {
            "furniture_id": source_item["furniture_id"],
            "name_zh_raw": source_item.get("name_zh_raw"),
            "normalized_type": source_item.get("normalized_type"),
            "model_url": source_item.get("model_url"),
            "primary_style": source_item.get("primary_style"),
            "size_cm": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "footprint_cm": {
                "width": round(footprint_width, 2),
                "depth": round(footprint_depth, 2),
            },
            "position_cm": {"x": scene_x_cm, "z": scene_z_cm},
            "rotation_y_deg": placed.rotation,
            "placement_engine": "furniture_engine",
        },
        footprint_box,
    )


def _manual_scene_object(
    item: dict[str, Any],
    room_width_cm: float,
    room_depth_cm: float,
    placed_boxes: list[dict[str, float]],
    warning: str | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    item_type = item.get("normalized_type")
    width = _size_cm(item, "width", 120)
    depth = _size_cm(item, "depth", 60)
    height = _size_cm(item, "height", 80)
    x, z, rotation, footprint_box = _resolve_collision_safe_position(
        item_type,
        width,
        depth,
        room_width_cm,
        room_depth_cm,
        placed_boxes,
    )

    return (
        {
            "furniture_id": item["furniture_id"],
            "name_zh_raw": item.get("name_zh_raw"),
            "normalized_type": item_type,
            "model_url": item.get("model_url"),
            "primary_style": item.get("primary_style"),
            "size_cm": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "footprint_cm": {
                "width": round(footprint_box["right"] - footprint_box["left"], 2),
                "depth": round(footprint_box["bottom"] - footprint_box["top"], 2),
            },
            "position_cm": {"x": round(x, 2), "z": round(z, 2)},
            "rotation_y_deg": rotation,
            "placement_engine": "manual_fallback",
            "placement_warning": warning,
        },
        footprint_box,
    )


def _place_with_engine(
    item: dict[str, Any],
    engine_room: Room,
    room_width_cm: float,
    room_depth_cm: float,
    existing: list[PlacedFurniture],
) -> tuple[PlacedFurniture | None, str | None]:
    item_type = item.get("normalized_type")
    width = _size_cm(item, "width", 120)
    depth = _size_cm(item, "depth", 60)
    catalog_item = _build_catalog_item(item)

    for raw_x, raw_z, rotation in _placement_candidates(
        item_type,
        width,
        depth,
        room_width_cm,
        room_depth_cm,
    ):
        footprint_width, footprint_depth = _rotated_footprint(width, depth, rotation)
        x_cm = _clamp_axis(raw_x, -room_width_cm / 2, room_width_cm / 2, footprint_width)
        z_cm = _clamp_axis(raw_z, -room_depth_cm / 2, room_depth_cm / 2, footprint_depth)
        pos_x_m, pos_y_m = _scene_cm_to_engine_m(x_cm, z_cm, room_width_cm, room_depth_cm)
        candidate = PlacedFurniture(
            id=item["furniture_id"],
            catalog=catalog_item,
            pos_x=pos_x_m,
            pos_y=pos_y_m,
            rotation=rotation,
        )
        reason = check_placement_with_clearance(candidate, engine_room, existing)
        if reason is None:
            return candidate, None

    fallback = place_furniture(
        engine_room,
        catalog_item,
        item["furniture_id"],
        existing,
    )
    return fallback["placed"], fallback["reason"]


def generate_layout(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    parsed_floorplan: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    placements: list[dict[str, Any]] = []
    warnings: list[str] = []
    placed_boxes: list[dict[str, float]] = []
    engine_room = _build_engine_room(room_width_cm, room_depth_cm, parsed_floorplan)
    engine_placed: list[PlacedFurniture] = []

    for item in items:
        item_type = item.get("normalized_type")
        if item_type in ENGINE_SPECIAL_TYPES:
            scene_object, footprint_box = _manual_scene_object(
                item,
                room_width_cm,
                room_depth_cm,
                placed_boxes,
            )
            placements.append(scene_object)
            continue

        placed, reason = _place_with_engine(
            item,
            engine_room,
            room_width_cm,
            room_depth_cm,
            engine_placed,
        )
        if placed is not None:
            scene_object, footprint_box = _scene_object_from_engine(
                item,
                placed,
                room_width_cm,
                room_depth_cm,
            )
            placements.append(scene_object)
            engine_placed.append(placed)
            placed_boxes.append(footprint_box)
            continue

        scene_object, footprint_box = _manual_scene_object(
            item,
            room_width_cm,
            room_depth_cm,
            placed_boxes,
            warning=reason or "furniture_engine 無法找到合法位置，已退回簡化擺位",
        )
        placements.append(scene_object)
        placed_boxes.append(footprint_box)
        warnings.append(
            f"{item.get('name_zh_raw') or item_type or '家具'}：{scene_object.get('placement_warning')}"
        )

    return placements, warnings


def build_scene_payload(
    site_payload: dict[str, Any],
    questionnaire: dict[str, Any],
    floorplan_path: str | None,
    room_width_cm: float,
    room_depth_cm: float,
) -> dict[str, Any]:
    parsed_floorplan = None
    dxf_text = questionnaire.get("floorplan_dxf_text")
    if dxf_text:
        try:
            parsed_floorplan = parse_dxf_floorplan(dxf_text)
        except Exception:
            parsed_floorplan = None

    effective_width_cm = parsed_floorplan["width_cm"] if parsed_floorplan else room_width_cm
    effective_depth_cm = parsed_floorplan["depth_cm"] if parsed_floorplan else room_depth_cm

    llm_mode, plan = build_scene_plan(questionnaire, site_payload["styles"])
    selected_items = choose_furniture_items(
        plan,
        site_payload["furniture"],
        questionnaire.get("furniture_random_seed"),
        effective_width_cm,
        effective_depth_cm,
        plan.get("preferred_colors", []) + questionnaire.get("custom_colors", []),
    )
    objects, layout_warnings = generate_layout(
        effective_width_cm,
        effective_depth_cm,
        selected_items,
        parsed_floorplan,
    )

    style = next(
        (style for style in site_payload["styles"] if style.get("style_id") == plan["style_id"]),
        site_payload["styles"][0],
    )

    return {
        "scene_id": f"scene_{uuid.uuid4().hex[:10]}",
        "llm_mode": llm_mode,
        "questionnaire": questionnaire,
        "plan_json": plan,
        "floorplan": {
            "image_path": floorplan_path,
            "width_cm": effective_width_cm,
            "depth_cm": effective_depth_cm,
            "source": parsed_floorplan["source"] if parsed_floorplan else "manual",
            "wall_count": parsed_floorplan["wall_count"] if parsed_floorplan else 0,
            "door_count": parsed_floorplan.get("door_count", 0) if parsed_floorplan else 0,
            "window_count": parsed_floorplan["window_count"] if parsed_floorplan else 0,
            "raw_segment_count": parsed_floorplan.get("raw_segment_count", 0) if parsed_floorplan else 0,
            "layers": parsed_floorplan.get("layers", []) if parsed_floorplan else [],
            "wall_layers": parsed_floorplan.get("wall_layers", []) if parsed_floorplan else [],
            "door_layers": parsed_floorplan.get("door_layers", []) if parsed_floorplan else [],
            "window_layers": parsed_floorplan.get("window_layers", []) if parsed_floorplan else [],
            "wall_segments": parsed_floorplan["wall_segments"] if parsed_floorplan else [],
            "plan_segments": parsed_floorplan.get("plan_segments", []) if parsed_floorplan else [],
            "door_segments": parsed_floorplan.get("door_segments", []) if parsed_floorplan else [],
            "window_segments": parsed_floorplan["window_segments"] if parsed_floorplan else [],
        },
        "style": {
            "style_id": style.get("style_id"),
            "style_name_zh": style.get("style_name_zh"),
            "scene_background": style.get("scene_background", {}),
            "palette_hex": style.get("palette_hex", []),
        },
        "design_choices": {
            "wall_option": questionnaire.get("wall_option", "auto"),
            "floor_option": questionnaire.get("floor_option", "auto"),
            "single_room_mode": not bool(parsed_floorplan),
            "accurate_dxf_mode": bool(parsed_floorplan),
        },
        "placement_engine": "furniture_engine",
        "layout_warnings": layout_warnings,
        "selected_furniture": selected_items,
        "scene_objects": objects,
    }


def mutate_scene_payload(
    site_payload: dict[str, Any],
    scene_data: dict[str, Any],
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    selected_items = [dict(item) for item in scene_data.get("selected_furniture", [])]
    style_id = (
        scene_data.get("style", {}).get("style_id")
        or scene_data.get("plan_json", {}).get("style_id")
        or "scandinavian"
    )
    room_width_cm = float(scene_data.get("floorplan", {}).get("width_cm") or 420)
    room_depth_cm = float(scene_data.get("floorplan", {}).get("depth_cm") or 360)
    preferred_colors = (
        list(scene_data.get("plan_json", {}).get("preferred_colors") or [])
        + list(scene_data.get("questionnaire", {}).get("custom_colors") or [])
    )
    furniture_db = site_payload["furniture"]
    scene_floorplan = scene_data.get("floorplan", {})
    parsed_floorplan = scene_floorplan if scene_floorplan.get("source") == "dxf" else None
    random_seed = payload.get("random_seed", payload.get("furniture_random_seed", random.randint(1, 10_000_000)))
    used_ids = {item.get("furniture_id") for item in selected_items if item.get("furniture_id")}
    mutation_message = ""

    if action == "replace":
        index = int(payload.get("index", -1))
        if index < 0 or index >= len(selected_items):
            raise ValueError("找不到要替換的家具編號。")
        current_item = selected_items[index]
        replacement = pick_furniture_candidate(
            furniture=furniture_db,
            item_type=current_item.get("normalized_type"),
            style_id=style_id,
            used_ids={item.get("furniture_id") for i, item in enumerate(selected_items) if i != index},
            preferred_colors=preferred_colors,
            room_width_cm=room_width_cm,
            room_depth_cm=room_depth_cm,
            random_seed=random_seed,
            index_hint=index,
            require_style=True,
            exclude_ids={current_item.get("furniture_id")},
        )
        if replacement is None:
            raise ValueError("目前找不到同風格、同類型可替換的家具。")
        selected_items[index] = replacement
        mutation_message = f"已替換家具編號 {index + 1}，並重新套用正式配置引擎。"

    elif action == "remove":
        index = int(payload.get("index", -1))
        if index < 0 or index >= len(selected_items):
            raise ValueError("找不到要移除的家具編號。")
        removed = selected_items.pop(index)
        mutation_message = f"已移除「{removed.get('name_zh_raw') or removed.get('normalized_type') or '家具'}」，並重新配置場景。"

    elif action == "add":
        item_type = str(payload.get("item_type") or "").strip()
        if not item_type:
            raise ValueError("缺少要新增的家具類型。")
        candidate = pick_furniture_candidate(
            furniture=furniture_db,
            item_type=item_type,
            style_id=style_id,
            used_ids=used_ids,
            preferred_colors=preferred_colors,
            room_width_cm=room_width_cm,
            room_depth_cm=room_depth_cm,
            random_seed=random_seed,
            index_hint=len(selected_items),
            require_style=True,
        )
        if candidate is None:
            raise ValueError("目前資料庫找不到同風格可加入的家具。")
        selected_items.append(candidate)
        mutation_message = f"已新增「{candidate.get('name_zh_raw') or item_type}」，並重新配置場景。"

    elif action == "reshuffle":
        reshuffled: list[dict[str, Any]] = []
        used_ids = set()
        for index, current_item in enumerate(selected_items):
            replacement = pick_furniture_candidate(
                furniture=furniture_db,
                item_type=current_item.get("normalized_type"),
                style_id=style_id,
                used_ids=used_ids,
                preferred_colors=preferred_colors,
                room_width_cm=room_width_cm,
                room_depth_cm=room_depth_cm,
                random_seed=random_seed,
                index_hint=index,
                require_style=True,
                exclude_ids={current_item.get("furniture_id")},
            )
            if replacement is None:
                replacement = current_item
            reshuffled.append(replacement)
            if replacement.get("furniture_id"):
                used_ids.add(replacement["furniture_id"])
        selected_items = reshuffled
        mutation_message = "已依目前風格重新抽換家具，並重新配置整個房間。"

    else:
        raise ValueError(f"不支援的場景動作：{action}")

    objects, layout_warnings = generate_layout(
        room_width_cm,
        room_depth_cm,
        selected_items,
        parsed_floorplan,
    )

    updated = {
        **scene_data,
        "scene_id": f"scene_{uuid.uuid4().hex[:10]}",
        "placement_engine": "furniture_engine",
        "layout_warnings": layout_warnings,
        "selected_furniture": selected_items,
        "scene_objects": objects,
        "mutation_message": mutation_message,
    }

    questionnaire = dict(updated.get("questionnaire") or {})
    questionnaire["required_furniture"] = list(
        dict.fromkeys(
            item.get("normalized_type")
            for item in selected_items
            if item.get("normalized_type")
        )
    )
    updated["questionnaire"] = questionnaire

    plan_json = dict(updated.get("plan_json") or {})
    plan_json["required_furniture"] = questionnaire["required_furniture"]
    updated["plan_json"] = plan_json

    return updated


def save_uploaded_floorplan(upload_dir: Path, upload) -> str | None:
    if not upload or not getattr(upload, "filename", ""):
        return None

    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(upload.filename).name}"
    target = upload_dir / safe_name

    with target.open("wb") as output:
        output.write(upload.file.read())

    return str(target)
