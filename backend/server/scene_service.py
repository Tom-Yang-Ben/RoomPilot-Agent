from __future__ import annotations

import json
import math
import os
import random
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from shapely.geometry import LineString, Point, Polygon, box as shapely_box
from shapely.ops import unary_union

from ..agent.knowledge import (
    COMPANION_OF,
    FAMILY_ZH,
    FREE_SEATING_FAMILIES,
    ROOM_ESSENTIALS,
    family_of,
    is_outdoor_item,
)
from ..agent.place import placement_hints, resolve_placements
from ..catalog.style_db import CLEARANCE_BY_TYPE, catalog_item_from_scene_object
from ..engine.clearance import check_placement_with_clearance
from ..engine.dxf_room import build_room_from_dxf
from ..engine.layout_model import Placement as RasterPlacement, RoomContext as RasterContext
from ..engine.obb import Obb, obb_blocked, stamp_obb
from ..engine.geometry import furniture_polygon
from ..engine.models import PlacedFurniture, Room, Wall
from ..engine.placement import (
    place_adjacent_to_furniture,
    place_furniture,
    place_overlay_on_furniture,
)
from ..upgrade3d.dxf_parser import parse_dxf_bytes
from .style_cards import find_taiwan_style_card

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_CANDIDATES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "backend" / "server" / ".env",
]

DEFAULT_OPENROUTER_MODELS = [
    "qwen/qwen3-32b:free",
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
            if key and not os.environ.get(key):
                os.environ[key] = value


def get_openrouter_models() -> list[str]:
    load_local_env()

    raw_models = os.getenv("OPENROUTER_MODELS", "").strip()
    if raw_models:
        models = [item.strip() for item in raw_models.split(",") if item.strip()]
        if models:
            return models

    single_model = os.getenv("OPENROUTER_MODEL", "").strip()
    if single_model:
        return [single_model]

    return DEFAULT_OPENROUTER_MODELS.copy()


def get_openrouter_status() -> dict[str, Any]:
    load_local_env()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    models = get_openrouter_models()
    model = models[0] if models else ""

    return {
        "enabled": bool(api_key and models and os.getenv("OPENROUTER_SCENE_PLANNING_ENABLED") == "1"),
        "has_api_key": bool(api_key),
        "has_model": bool(models),
        "model": model or None,
        "models": models,
        "model_count": len(models),
        "provider": "openrouter" if api_key and models else "fallback",
        "scene_planning_enabled": os.getenv("OPENROUTER_SCENE_PLANNING_ENABLED") == "1",
    }


STYLE_FALLBACKS = {
    "auto": "scandinavian",
    "unsure": "scandinavian",
    "": "scandinavian",
}

SPACE_DEFAULTS = {
    "living_room": ["sofa", "coffee-table", "tv-bench", "armchair", "bookcase"],
    "bedroom": ["bed", "bedside-table", "bookcase", "runner-small-rug"],
    "storage": ["desk", "office-chair", "bookcase", "wall-shelf", "storage-cabinet"],
    "kitchen": ["dining-table", "dining-chair", "sideboard", "appliance-cabinet"],
    "bathroom": [],
    "balcony": [],
    "entryway": [],
    "hallway": [],
    "stair": [],
    "garage": ["storage-cabinet", "wall-shelf"],
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
        # 房型基礎家具保底(knowledge.ROOM_ESSENTIALS):臥室床/客廳沙發/
        # 餐廚餐桌,需求清單漏了就補在最前(基礎家具最優先擺);
        # 沙發床視同床,臥室不重複補。
        for essential in ROOM_ESSENTIALS.get(space_type, ()):
            if not any(
                (essential == "bed" and item == "sofa-bed") or family_of(item) == essential
                for item in normalized
            ):
                normalized.insert(0, essential)
        # 有餐桌就要有餐椅(張數保證在選件與 2D 規格層;此處保證型別存在)
        if any(family_of(item) == "dining-table" for item in normalized) and not any(
            family_of(item) == "dining-chair" for item in normalized
        ):
            normalized.append("dining-chair")
        return normalized

    return SPACE_DEFAULTS.get(space_type, SPACE_DEFAULTS["living_room"]).copy()


def _extract_openrouter_message_content(body: dict[str, Any]) -> str | None:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts) if text_parts else None

    return None


def _load_json_response(body: dict[str, Any]) -> dict[str, Any] | None:
    content = _extract_openrouter_message_content(body)
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _normalize_openrouter_plan(
    raw_plan: dict[str, Any] | None,
    questionnaire: dict[str, Any],
    styles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(raw_plan, dict):
        return None

    requested_style = normalize_style_id(questionnaire.get("style_preference"), styles)
    fixed_style_requested = questionnaire.get("style_preference") not in STYLE_FALLBACKS

    normalized_required = normalize_required_furniture(
        raw_plan.get("required_furniture", []),
        raw_plan.get("space_type", questionnaire.get("space_type", "living_room")),
    )
    if not normalized_required:
        return None

    layout_rules = raw_plan.get("layout_rules", [])
    if not isinstance(layout_rules, list):
        layout_rules = []

    preferred_colors = raw_plan.get("preferred_colors", questionnaire.get("preferred_colors", []))
    if not isinstance(preferred_colors, list):
        preferred_colors = questionnaire.get("preferred_colors", [])

    personal_requirements = raw_plan.get("personal_requirements", questionnaire.get("personal_notes", ""))
    if personal_requirements is None:
        personal_requirements = ""

    summary = raw_plan.get("summary_zh")
    if not isinstance(summary, str) or not summary.strip():
        summary = "已依問卷整理風格方向與家具需求。"

    plan = {
        "style_id": requested_style if fixed_style_requested else normalize_style_id(raw_plan.get("style_id"), styles),
        "space_type": raw_plan.get("space_type", questionnaire.get("space_type", "living_room")),
        "preferred_colors": preferred_colors,
        "required_furniture": normalized_required,
        "personal_requirements": str(personal_requirements).strip(),
        "layout_rules": layout_rules,
        "summary_zh": summary.strip(),
    }

    for item in normalize_required_furniture(
        questionnaire.get("custom_furniture", []),
        questionnaire.get("space_type", "living_room"),
    ):
        if item not in plan["required_furniture"]:
            plan["required_furniture"].append(item)

    return plan


def _post_openrouter_chat(payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any] | None:
    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _openrouter_request(
    messages: list[dict[str, str]],
    questionnaire: dict[str, Any],
    styles: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    status = get_openrouter_status()
    api_key = os.getenv("OPENROUTER_API_KEY")
    models = status["models"]
    site_url = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000")
    app_name = os.getenv("OPENROUTER_APP_NAME", "test_furniture scene planner")

    if not api_key or not models or os.getenv("OPENROUTER_SCENE_PLANNING_ENABLED") != "1":
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url,
        "X-Title": app_name,
    }

    for model in models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        body = _post_openrouter_chat(payload, headers)
        parsed = _normalize_openrouter_plan(
            _load_json_response(body) if body else None,
            questionnaire,
            styles,
        ) if body else None
        if parsed:
            return model, parsed

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


def build_scene_plan(
    questionnaire: dict[str, Any],
    styles: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], str | None]:
    openrouter_result = _openrouter_request(
        build_questionnaire_prompt(questionnaire, styles),
        questionnaire,
        styles,
    )
    if openrouter_result:
        model, plan = openrouter_result
        return "openrouter", plan, model

    return "fallback", fallback_plan(questionnaire, styles), None


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

        selected.append(merged)
        used_ids.add(furniture_id)

    return selected


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


_WALL_ANCHORED_TYPES = {
    "appliance-cabinet",
    "bathroom-vanity",
    "bed",
    "bed-frame",
    "bookcase",
    "cabinet",
    "desk",
    "mirror-cabinet",
    "refrigerator",
    "sideboard",
    "sofa",
    "sofa-bed",
    "storage-cabinet",
    "tv-bench",
    "wardrobe",
    "washer",
}


def _facing(rotation: float) -> tuple[float, float]:
    """three.js Y 軸旋轉 → 家具正面的單位向量(場景座標 x, z)。

    本 repo 場景座標的朝向慣例:rot=0 正面朝 +z、rot=90 朝 +x、rot=180 朝 -z
    (與 _placement_candidates 靠牆候選、_scene_rotation_toward 及 3D 渲染鏈一致;
    渲染端 world 對 z 鏡像並以 -rot 套用,GLB 原始朝向 -z,兩次翻轉互相抵銷)。
    舊實作誤用規格 y 軸向上版公式 (sin, -cos),導致成組候選把副件擺到主件背面。
    """
    rad = math.radians(rotation)
    return (round(math.sin(rad), 6), round(math.cos(rad), 6))


def _placement_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
    bounds_cm: tuple[float, float, float, float] | None = None,
    hint: dict[str, Any] | None = None,
    neighbors: dict[str, dict[str, float]] | None = None,
) -> list[tuple[float, float, float]]:
    """候選試放順序(合法性仍 100% 由引擎把關,這裡只影響「先試哪裡」)。

    hint / neighbors 是 2026-08-02 併入 yen agent 擺位紀律時加的**選填**參數;
    兩者皆為 None 時回傳值與併入前位元相同(見 test_engine_no_hint_matches_legacy_behavior)。
    - hint:``{"anchor": "left"|"right"|"top"|"bottom"|"center"}``,把靠該牆的
      候選 prepend 到最前面優先試放。
    - neighbors:族系 → 已擺好的代表家具,用來把「椅子貼書桌、床頭櫃貼床、
      茶几對沙發、電視櫃對沙發」的成組候選排到最前。
    """
    left, right, top, bottom = bounds_cm or (
        -room_width_cm / 2,
        room_width_cm / 2,
        -room_depth_cm / 2,
        room_depth_cm / 2,
    )
    candidate_width_cm = right - left
    candidate_depth_cm = bottom - top
    center_x = (left + right) / 2
    center_z = (top + bottom) / 2
    candidates: list[tuple[float, float, float]] = []
    wall_gap = 0 if bounds_cm is not None else 10

    if item_type == "tv-bench":
        candidates.extend([(center_x, top + depth / 2 + wall_gap, 0), (center_x - candidate_width_cm * 0.22, top + depth / 2 + wall_gap, 0)])
    elif item_type == "sofa":
        # 下牆優先,正中最先、由中心向外滑位(feedback:沙發壓到陽台門時
        # 「往旁邊移一點,盡量在正前方,有一定容錯」——滑位序列就是容錯);
        # 同牆全被門淨空/通行縫壓掉才改試左右牆(面向室內),才不會落到
        # 「長邊優先」掃描的任意牆、讓對面沒有電視櫃的位置。
        sofa_z = bottom - depth / 2 - wall_gap
        candidates.extend(
            (center_x + candidate_width_cm * ratio, sofa_z, 180)
            for ratio in (0.0, -0.09, 0.09, -0.18, 0.18, -0.27, 0.27, -0.36, 0.36)
        )
        candidates.extend([
            (left + depth / 2 + wall_gap, center_z, 90),
            (right - depth / 2 - wall_gap, center_z, 270),
        ])
    elif item_type == "coffee-table":
        candidates.extend([(center_x, center_z + 12, 0), (center_x, center_z - 18, 0)])
    elif item_type == "armchair":
        # 靠右牆面向 -x、靠左牆面向 +x;原本寫死 ±35° 斜角,2D/3D 看起來像擺歪
        candidates.extend([(right - width / 2 - 30, center_z + 35, 270), (left + width / 2 + 30, center_z + 35, 90)])
    elif item_type in {
        "appliance-cabinet", "bathroom-vanity", "bookcase", "cabinet",
        "mirror-cabinet", "refrigerator", "storage-cabinet", "wardrobe", "washer",
    }:
        candidates.extend([
            (left + depth / 2 + wall_gap, center_z, 90),
            (right - depth / 2 - wall_gap, center_z, -90),
            (center_x, top + depth / 2 + wall_gap, 0),
        ])
    elif item_type in {"bed", "bed-frame", "sofa-bed"}:
        candidates.extend([(center_x, bottom - depth / 2 - wall_gap, 180), (left + depth / 2 + wall_gap, center_z, 90)])
    elif item_type == "bedside-table":
        # 位於下牆(+z 側),正面要朝 -z(房內) → 180;rot=0 會臉貼牆
        candidates.extend([(right - width / 2 - 22, bottom - depth / 2 - 34, 180), (left + width / 2 + 22, bottom - depth / 2 - 34, 180)])
    elif item_type == "desk":
        candidates.extend([(center_x, top + depth / 2 + wall_gap, 0), (left + depth / 2 + wall_gap, center_z, 90)])
    elif item_type == "office-chair":
        # 第二候選:書桌貼左牆面向 +x 時,椅子在其正前方要回頭面向 -x → 270
        candidates.extend([(center_x, top + depth + 88, 180), (left + width / 2 + 80, center_z, 270)])
    elif item_type == "dining-table":
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 36, 0)])
    elif item_type == "dining-chair":
        # 靠右側的椅子面向 -x(桌在中央)、靠左側面向 +x;原本左右互換,臉朝牆
        candidates.extend([(right - width / 2 - 40, center_z, 270), (left + width / 2 + 40, center_z, 90), (center_x, center_z + 80, 180)])
    elif item_type == "sideboard":
        candidates.extend([(center_x, top + depth / 2 + wall_gap, 0), (center_x, bottom - depth / 2 - wall_gap, 180)])
    elif item_type == "wall-shelf":
        candidates.extend([(left + width / 2 + 15, top + depth / 2 + 12, 0), (right - width / 2 - 15, top + depth / 2 + 12, 0)])
    elif item_type == "curtain":
        candidates.extend([(center_x, top + depth / 2 + 14, 0), (right - width / 2 - 14, center_z, 90)])
    elif item_type == "flower-pots-planter":
        candidates.extend([
            (right - width / 2 - 24, top + depth / 2 + 24, 0),
            (left + width / 2 + 24, bottom - depth / 2 - 24, 0),
        ])
    elif item_type == "floor-lamp":
        candidates.extend([
            (left + width / 2 + 28, top + depth / 2 + 28, 0),
            (right - width / 2 - 28, bottom - depth / 2 - 28, 0),
        ])
    elif item_type in {"large-medium-rug", "runner-small-rug"}:
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 24, 0)])
    else:
        candidates.append((center_x, center_z, 0))

    grid_x = [left + candidate_width_cm * ratio for ratio in (0.25, 0.5, 0.75)]
    grid_z = [top + candidate_depth_cm * ratio for ratio in (0.28, 0.5, 0.72)]
    for z in grid_z:
        for x in grid_x:
            candidates.append((x, z, 0))

    return _agent_prepend_candidates(
        item_type, width, depth, hint, neighbors,
        left, right, top, bottom, center_x, center_z,
    ) + candidates


def _agent_prepend_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    hint: dict[str, Any] | None,
    neighbors: dict[str, dict[str, float]] | None,
    left: float,
    right: float,
    top: float,
    bottom: float,
    center_x: float,
    center_z: float,
) -> list[tuple[float, float, float]]:
    """agent 擺位紀律的優先候選:成組(paired)在前、靠牆錨點(anchored)在後。

    自 yen 的 services/scene_service.py 移植。兩個輸入都空時回 []，
    所以 _placement_candidates 的既有行為完全不受影響。
    """
    if not hint and not neighbors:
        return []

    gap = 2.0
    inner_w = right - left
    inner_d = bottom - top
    family = family_of(item_type)
    neighbors = neighbors or {}
    paired: list[tuple[float, float, float]] = []

    if family == "office-chair":
        desk = neighbors.get("desk")
        if desk:
            fx, fz = _facing(desk["rot"])
            # 書桌有前方淨空(抽拉椅子的空間),椅子要放在淨空外緣才過得了引擎檢查
            desk_clear = CLEARANCE_BY_TYPE.get("desk")
            base = (desk_clear.depth if desk_clear else 50.0) + 4.0
            for extra in (base, base + 18.0):
                dist = desk["depth"] / 2 + depth / 2 + extra
                paired.append((desk["x"] + fx * dist, desk["z"] + fz * dist,
                               (desk["rot"] + 180) % 360))
    elif family == "bedside-table":
        bed = neighbors.get("bed")
        if bed:
            fx, fz = _facing(bed["rot"])
            px, pz = fz, -fx                     # 床的側向
            ax = bed["x"] - fx * (bed["depth"] / 2 - depth / 2)  # 對齊床頭端
            az = bed["z"] - fz * (bed["depth"] / 2 - depth / 2)
            side = bed["width"] / 2 + width / 2 + 4
            paired.append((ax + px * side, az + pz * side, bed["rot"]))
            paired.append((ax - px * side, az - pz * side, bed["rot"]))
    elif family == "coffee-table":
        sofa = neighbors.get("sofa")
        if sofa:
            fx, fz = _facing(sofa["rot"])
            for knee in (45.0, 65.0):            # 沙發前緣與茶几間留膝蓋活動距
                dist = sofa["depth"] / 2 + depth / 2 + knee
                paired.append((sofa["x"] + fx * dist, sofa["z"] + fz * dist, sofa["rot"]))
    elif family == "tv-bench":
        sofa = neighbors.get("sofa")
        if sofa:                                 # 電視櫃靠沙發正對面的牆
            fx, fz = _facing(sofa["rot"])
            # 單一定點會被對面牆的門淨空帶/牆段缺口一票否決,整組退回靠牆
            # 掃描而落到隨便一面長牆(與沙發呈 L 型)。沿對面牆多試側移點,
            # 正對位優先、越偏越後,全部仍由柵格合法性把關。
            lateral = (0.0, -80.0, 80.0, -160.0, 160.0)
            if abs(fx) >= abs(fz):
                x = right - depth / 2 - gap if fx > 0 else left + depth / 2 + gap
                rot = 270.0 if fx > 0 else 90.0
                paired.extend((x, sofa["z"] + off, rot) for off in lateral)
            else:
                z = bottom - depth / 2 - gap if fz > 0 else top + depth / 2 + gap
                rot = 180.0 if fz > 0 else 0.0
                paired.extend((sofa["x"] + off, z, rot) for off in lateral)
    elif family in FREE_SEATING_FAMILIES:
        sofa = neighbors.get("sofa")
        if sofa:
            # 客廳休閒椅只准沙發左前/右前(對談 L 型),面向座位區中線;
            # 走廊遮罩已保證這些點在視聽軸線之外。
            fx, fz = _facing(sofa["rot"])
            ux, uz = fz, -fx                     # 沙發側向
            chair_half = max(width, depth) / 2
            side_off = sofa["width"] / 2 + chair_half + 12.0
            for forward in (sofa["depth"] / 2, sofa["depth"] / 2 + 40.0):
                for side in (1.0, -1.0):
                    rot = math.degrees(math.atan2(-ux * side, -uz * side)) % 360
                    paired.append((
                        sofa["x"] + ux * side * side_off + fx * forward,
                        sofa["z"] + uz * side * side_off + fz * forward,
                        rot,
                    ))
    elif family == "dining-chair":
        table = neighbors.get("dining-table")
        if table:
            # 餐椅貼餐桌兩長邊各 2 席、面向餐桌(對齊 engine rules §7.3 的
            # CHAIR_GAP_CM=3);多張椅子依實例序消化席位,佔用由柵格把關。
            fx, fz = _facing(table["rot"])
            px, pz = fz, -fx                     # 桌面寬方向(沿桌緣)
            dist = table["depth"] / 2 + depth / 2 + 3.0
            for side in (1.0, -1.0):
                seat_rot = (table["rot"] + 180.0) % 360 if side > 0 else table["rot"]
                for along in (-table["width"] / 4, table["width"] / 4):
                    paired.append((
                        table["x"] + fx * dist * side + px * along,
                        table["z"] + fz * dist * side + pz * along,
                        seat_rot,
                    ))

    anchor = (hint or {}).get("anchor")
    anchored: list[tuple[float, float, float]] = []
    if anchor == "top":
        z = top + depth / 2 + gap
        anchored = [(center_x, z, 0), (center_x - inner_w * 0.22, z, 0), (center_x + inner_w * 0.22, z, 0)]
    elif anchor == "bottom":
        z = bottom - depth / 2 - gap
        anchored = [(center_x, z, 180), (center_x - inner_w * 0.18, z, 180), (center_x + inner_w * 0.18, z, 180)]
    elif anchor == "left":
        x = left + depth / 2 + gap
        anchored = [(x, center_z, 90), (x, center_z - inner_d * 0.2, 90), (x, center_z + inner_d * 0.2, 90)]
    elif anchor == "right":
        x = right - depth / 2 - gap
        anchored = [(x, center_z, -90), (x, center_z - inner_d * 0.2, -90), (x, center_z + inner_d * 0.2, -90)]
    elif anchor == "center":
        anchored = [(center_x, center_z, 0)]

    return paired + anchored


def _hinted_wall_candidate(
    item_type: str | None,
    width: float,
    depth: float,
    hint_cm: dict[str, Any] | None,
    bounds_cm: tuple[float, float, float, float] | None,
) -> tuple[float, float, float] | None:
    """Convert a user's drag hint into an engine-validated wall candidate."""
    if item_type not in _WALL_ANCHORED_TYPES or not bounds_cm or not isinstance(hint_cm, dict):
        return None
    try:
        hint_x = float(hint_cm["x"])
        hint_z = float(hint_cm["z"])
    except (KeyError, TypeError, ValueError):
        return None

    left, right, top, bottom = bounds_cm
    candidates: list[tuple[float, float, float]] = []
    # 旋轉值 = 背貼該牆、正面朝房內(rot=0 朝 +z):上牆 0、下牆 180、左牆 90、右牆 270
    for rotation, side in ((0.0, "top"), (180.0, "bottom"), (90.0, "left"), (270.0, "right")):
        footprint_width, footprint_depth = _rotated_footprint(width, depth, rotation)
        if side == "top":
            x = _clamp_axis(hint_x, left, right, footprint_width, 0)
            z = top + footprint_depth / 2
        elif side == "bottom":
            x = _clamp_axis(hint_x, left, right, footprint_width, 0)
            z = bottom - footprint_depth / 2
        elif side == "left":
            x = left + footprint_width / 2
            z = _clamp_axis(hint_z, top, bottom, footprint_depth, 0)
        else:
            x = right - footprint_width / 2
            z = _clamp_axis(hint_z, top, bottom, footprint_depth, 0)
        candidates.append((x, z, rotation))

    return min(candidates, key=lambda candidate: math.hypot(candidate[0] - hint_x, candidate[1] - hint_z))


# 地毯可與目標家具重疊，但仍須由引擎驗證牆與房間邊界。
_OVERLAY_TYPES = {"large-medium-rug", "runner-small-rug"}
_IGNORE_COLLISION_TYPES = {"wall-shelf"}

# 允許進入沙發視聽走廊的類型:成組件(茶几/電視櫃)、平面件(地毯)、
# 貼牆件(窗簾/層板)。其餘家具不得卡在沙發與電視櫃之間。
_CORRIDOR_EXEMPT_TYPES = (
    {"coffee-table", "tv-bench", "curtain"} | _OVERLAY_TYPES | _IGNORE_COLLISION_TYPES
)


def curtain_window_hint(
    floorplan: dict[str, Any] | None,
    *,
    room_width_cm: float,
    room_depth_cm: float,
    boundary: Polygon | None = None,
) -> tuple[float, float, float, float] | None:
    windows = (floorplan or {}).get("window_segments") or []
    if not windows:
        return None
    coordinate_scale = _floorplan_coordinate_scale_cm(floorplan)
    selected = None
    for window in windows:
        start = window.get("start") or {}
        end = window.get("end") or {}
        midpoint = Point(
            (float(start.get("x") or 0) + float(end.get("x") or 0)) * coordinate_scale / 2
            + room_width_cm / 2,
            (float(start.get("z") or 0) + float(end.get("z") or 0)) * coordinate_scale / 2
            + room_depth_cm / 2,
        )
        if boundary is None or boundary.buffer(30).contains(midpoint):
            selected = window
            break
    if selected is None:
        return None

    start = selected.get("start") or {}
    end = selected.get("end") or {}
    sx, sz = float(start.get("x") or 0), float(start.get("z") or 0)
    ex, ez = float(end.get("x") or 0), float(end.get("z") or 0)
    dx, dz = ex - sx, ez - sz
    segment_length = math.hypot(dx, dz)
    length_cm = segment_length * coordinate_scale
    if length_cm < 10:
        return None

    midpoint_x, midpoint_z = (sx + ex) / 2, (sz + ez) / 2
    inset_cm = 14.0
    normal_x, normal_z = -dz / segment_length, dx / segment_length
    inward_point = None
    for direction in (1, -1):
        centered_x = midpoint_x * coordinate_scale + normal_x * inset_cm * direction
        centered_z = midpoint_z * coordinate_scale + normal_z * inset_cm * direction
        engine_point = Point(
            centered_x + room_width_cm / 2,
            centered_z + room_depth_cm / 2,
        )
        if boundary is None or boundary.buffer(2).contains(engine_point):
            inward_point = centered_x, centered_z
            break
    if inward_point is None:
        return None
    x_cm, z_cm = inward_point
    rotation = math.degrees(math.atan2(dz, dx))
    width_cm = min(max(length_cm + 30, 80), max(room_width_cm, room_depth_cm), 500)
    return x_cm, z_cm, rotation, width_cm


def _room_boundary_polygon(room: Room) -> Polygon | None:
    """由 Room.walls(依序的房間邊界環段)重建房間多邊形。

    DXF 房間不是矩形:引擎的 out_of_bounds 只檢查 bbox,細牆段(6cm)又擋不住
    「整件家具落在厚實牆體內部」的候選點 —— 必須額外用這個多邊形做包含檢查,
    否則家具會被放進 bbox 內、實際房間外的區域(視覺上卡在牆裡)。
    """
    if len(room.walls) < 3:
        return None
    points = [(w.x1, w.y1) for w in room.walls]
    try:
        poly = Polygon(points)
        if not poly.is_valid:
            poly = poly.buffer(0)  # 自交環 → 可能拆成 MultiPolygon
        if poly.is_empty:
            return None
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)  # 取主要區域,自交碎片捨棄
        return poly
    except Exception:
        return None


def _inside_boundary(candidate: PlacedFurniture, boundary: Polygon | None) -> bool:
    if boundary is None:
        return True
    return boundary.contains(furniture_polygon(candidate))


def _grid_place_in_boundary(
    catalog,
    item_id,
    room,
    placed,
    boundary,
    forbidden_zones: list[Polygon] | None = None,
    accepts=None,
):
    """非矩形房間的最後防線:沿房間多邊形內部以 50cm 網格搜尋(由質心向外)。

    錨點與引擎網格都以 bbox 為座標基準,房間只佔 bbox 一角時全會撲空,
    這裡改以房間多邊形自己的範圍掃描。

    ``accepts``(選填)是呼叫端的最終裁決(柵格遮罩/視聽走廊):不給則維持
    舊行為。原本只回第一個 Shapely 合格點,再被柵格否決就整條後援作廢 ——
    掃描時就讓裁決參與,側邊還有位就不會誤判成放不下。
    """
    from shapely.geometry import Point
    from shapely.prepared import prep

    prepared = prep(boundary)
    minx, miny, maxx, maxy = boundary.bounds
    cx, cy = boundary.centroid.x, boundary.centroid.y
    step = 50.0

    cands = []
    y = miny + step / 2
    while y < maxy:
        x = minx + step / 2
        while x < maxx:
            if prepared.contains(Point(x, y)):  # 便宜的預篩,只留房間內的點
                cands.append((x, y))
            x += step
        y += step
    cands.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)

    for rotation in (0, 90, 180, 270):
        for x, y in cands:
            cand = PlacedFurniture(id=item_id, catalog=catalog, pos_x=x, pos_y=y, rotation=rotation)
            if (
                _inside_boundary(cand, boundary)
                and not _placement_intersects_zones(cand, forbidden_zones)
                and check_placement_with_clearance(cand, room, placed) is None
                and (accepts is None or accepts(cand))
            ):
                return cand
    return None


def _four_wall_room(width_cm: float, depth_cm: float) -> Room:
    """手動輸入尺寸時的矩形房間(引擎座標:角落原點、公分)。"""
    return Room(
        width=width_cm,
        depth=depth_cm,
        walls=[
            Wall(0, 0, width_cm, 0),
            Wall(width_cm, 0, width_cm, depth_cm),
            Wall(width_cm, depth_cm, 0, depth_cm),
            Wall(0, depth_cm, 0, 0),
        ],
    )


def _floorplan_coordinate_scale_cm(floorplan: dict[str, Any] | None) -> float:
    """Return the scale from stored floorplan coordinates to centimeters."""
    return 1.0 if (floorplan or {}).get("coordinate_unit") == "cm" else 100.0


# 窗簾本來就貼窗;沙發族系允許背靠窗牆(常見客廳格局:沙發背窗、電視對面
# ——feedback 9/10:沙發被窗前帶擋出窗牆,電視櫃的成組候選才落到陽台門側)。
# ponytail: 落地窗與一般窗在 window_segments 無法區分,沙發一律豁免;
# 若日後窗資料帶窗台高,改依高度判。
_WINDOW_CLEARANCE_EXEMPT_TYPES = {
    "curtain", "sofa", "fabric-sofa", "leather-sofa", "modular-sofa", "sofa-bed",
}


def window_clearance_zones(
    floorplan: dict[str, Any] | None,
    room: Room,
    depth_cm: float = 70.0,
    where=None,
) -> list[Polygon]:
    """Build no-furniture bands around confirmed window and balcony openings.

    ``where``(選填)以原始 opening dict 過濾:一般窗與落地窗(出入口)
    的淨空語意不同,拖曳驗證需要分流。
    """
    scale = _floorplan_coordinate_scale_cm(floorplan)
    zones: list[Polygon] = []
    for opening in (floorplan or {}).get("window_segments") or []:
        if where is not None and not where(opening):
            continue
        try:
            start = opening["start"]
            end = opening["end"]
            line = LineString(
                [
                    (
                        float(start["x"]) * scale + room.width / 2,
                        float(start["z"]) * scale + room.depth / 2,
                    ),
                    (
                        float(end["x"]) * scale + room.width / 2,
                        float(end["z"]) * scale + room.depth / 2,
                    ),
                ]
            )
            if line.length >= 4:
                zones.append(line.buffer(depth_cm, cap_style=2))
        except (KeyError, TypeError, ValueError):
            continue
    return zones


def _placement_intersects_zones(
    candidate: PlacedFurniture,
    zones: list[Polygon] | None,
) -> bool:
    if not zones:
        return False
    footprint = furniture_polygon(candidate)
    return any(footprint.intersects(zone) for zone in zones)


# ── 柵格擺位引擎接線(docs/擺位計算邏輯.md)──────────────────────────
# 2026-08-02 起碰撞判定的唯一權威是 backend/engine 的布林網格,不再是 Shapely。
# 邊界(¬room_mask)、門前動線、窗前採光帶全部併進遮罩,因此原本分散在
# _inside_boundary / _placement_intersects_zones / check_placement_with_clearance
# 的三段檢查在此收斂成一次 obb_blocked。


def build_raster_context(
    room: Room,
    boundary: Polygon | None,
    floorplan: dict[str, Any] | None,
) -> RasterContext | None:
    """由房間邊界與門窗建出柵格擺位脈絡(角落原點公分)。

    ``boundary`` 已是「可擺區域」(內縮 8cm 或 DXF 最大自由空間),直接當房間環;
    取不到環時回 None,呼叫端退回舊 Shapely 路徑(手動矩形模式的極端案例)。
    """
    from ..engine.constraints import blocked_masks
    from ..engine.layout_model import RoomContext, polygon_centroid, room_edges
    from ..engine.raster import build_occupancy

    ring: list[tuple[float, float]] = []
    if boundary is not None and not boundary.is_empty:
        geom = max(boundary.geoms, key=lambda g: g.area) if hasattr(boundary, "geoms") else boundary
        ring = [(float(x), float(y)) for x, y in geom.exterior.coords]
    if len(ring) < 4:
        ring = [
            (0.0, 0.0), (room.width, 0.0), (room.width, room.depth), (0.0, room.depth),
        ]
    # 引擎輪廓邊約定「室內恆在邊的左側」(Edge.inward = 左法線),
    # 但 Shapely buffer 的外環是順時針 —— 不翻轉的話 inward 全指向房外,
    # 靠牆錨定掃描會把候選點推出邊界而全數被遮罩否決。
    area2 = sum(
        ring[i][0] * ring[(i + 1) % len(ring)][1]
        - ring[(i + 1) % len(ring)][0] * ring[i][1]
        for i in range(len(ring))
    )
    if area2 < 0:
        ring = ring[::-1]

    doors = _floorplan_segments_cm(floorplan, "door_segments", room)
    windows = _floorplan_segments_cm(floorplan, "window_segments", room)
    # 落地窗(陽台門)是出入動線:當「通行縫」進 low 遮罩(75cm,與門同級),
    # 矮家具與沙發都不得擋;一般窗維持 40cm 採光帶(沙發豁免、矮件可貼)。
    access_windows = _floorplan_segments_cm(
        floorplan, "window_segments", room, where=_is_access_window,
    )
    plain_windows = _floorplan_segments_cm(
        floorplan, "window_segments", room,
        where=lambda opening: not _is_access_window(opening),
    )
    plan = {
        "bbox": [
            min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring),
        ],
        "walls": [(w.x1, w.y1, w.x2, w.y2) for w in room.walls or []],
        "wall_polygons": [],
        "doors": doors,
        "windows": windows,
    }
    grid = build_occupancy(plan)
    # occ 已含牆線;房間環本身就是可擺區域,牆體不再重複扣一次
    grid.occ[:] = False
    masks = blocked_masks(
        grid, ring, doors=doors, windows=plain_windows, passages=access_windows,
    )
    return RoomContext(
        grid=grid,
        masks=masks,
        edges=room_edges(ring),
        centroid=polygon_centroid(ring),
        room_id="scene",
        label="default",
    )


def raster_free(
    ctx: RasterContext | None,
    item_type: str | None,
    width: float,
    depth: float,
    height: float,
    x_cm: float,
    z_cm: float,
    rotation_deg: float,
    half_w_cm: float,
    half_d_cm: float,
    *,
    check_placed: bool = True,
) -> bool:
    """柵格版合法性(`docs/擺位計算邏輯.md` §5.3)。

    一次判完「房外 / 牆體 / 門前動線 / 窗前採光帶 / 已放家具」。
    ``item_type`` 只用來套規格的兩個豁免:``curtain`` 不受窗前帶約束、
    ``wall-shelf`` 掛牆不參與地面碰撞。
    """
    if ctx is None:
        return True                       # 建不出脈絡時交還舊路徑判斷
    # 場景 rotation(three Y 角)與引擎平面角互為鏡像(z 軸同向、握向相反),
    # 進柵格必須取負,否則非 90° 倍數的家具(45° 拖曳)會驗到鏡像後的足跡。
    # 與舊 Shapely 路徑 _scene_object_to_placed 的 (-rot) % 360 同一約定。
    obb = Obb.from_deg(x_cm + half_w_cm, z_cm + half_d_cm, width, depth, -rotation_deg)
    if item_type in _WINDOW_CLEARANCE_EXEMPT_TYPES:
        mask = ctx.masks.low               # 窗簾本來就該貼窗
    else:
        mask = ctx.masks.for_height(height)
    if obb_blocked(mask, ctx.grid, obb):
        return False
    if check_placed and item_type not in _IGNORE_COLLISION_TYPES:
        return not obb_blocked(ctx.placed, ctx.grid, obb)
    return True


def raster_commit(
    ctx: RasterContext | None,
    item_type: str | None,
    width: float,
    depth: float,
    x_cm: float,
    z_cm: float,
    rotation_deg: float,
    half_w_cm: float,
    half_d_cm: float,
) -> None:
    """把已定案的家具烙進累計遮罩。地毯(overlay)與層板不烙印。"""
    if ctx is None or item_type in _OVERLAY_TYPES or item_type in _IGNORE_COLLISION_TYPES:
        return
    stamp_obb(
        ctx.placed,
        ctx.grid,
        # 同 raster_free:場景角進柵格取負(90° 倍數不受影響)
        Obb.from_deg(x_cm + half_w_cm, z_cm + half_d_cm, width, depth, -rotation_deg),
    )


def _raster_wall_anchor(
    ctx: RasterContext | None,
    item_type: str | None,
    width: float,
    depth: float,
    height: float,
    half_w_cm: float,
    half_d_cm: float,
) -> tuple[float, float, float] | None:
    """靠牆錨定掃描(docs/擺位計算邏輯.md §6 的場景座標版)。

    沿房間輪廓邊(長邊優先)跑完整錨點序列,背面貼齊可放邊界、正面朝室內;
    合法性由同一套柵格遮罩(含已放家具)判定。輪廓環已內縮 8cm,故不再疊加
    規格的 WALL_GAP_CM。回傳 ``(x_cm, z_cm, rotation_y_deg)``(房間中心原點、
    場景旋轉);所有邊都放不下回 None,由呼叫端續走網格散點與引擎後援。
    """
    if ctx is None:
        return None
    from ..engine.rules import anchor_ts, candidate_edges

    # 與 raster_free 同一豁免:沙發族系可背靠窗牆,掃描後援不得比候選嚴
    if item_type in _WINDOW_CLEARANCE_EXEMPT_TYPES:
        mask = ctx.masks.low
    else:
        mask = ctx.masks.for_height(height)
    for edge in candidate_edges(ctx.edges, width):
        nx, nz = edge.inward()
        # 場景朝向慣例 rot=0 → +z(見 _facing),面向室內法線 n 的角度 = atan2(nx, nz)
        rotation = math.degrees(math.atan2(nx + 0.0, nz + 0.0)) % 360
        off = depth / 2
        for t in anchor_ts(edge.length, width):
            px, pz = edge.point_at(t)
            cx = px + nx * off
            cz = pz + nz * off
            # 場景角進柵格取負(同 raster_free);斜牆邊的非 90° 角也因此驗到
            # 與渲染一致的足跡
            obb = Obb.from_deg(cx, cz, width, depth, -rotation)
            if obb_blocked(mask, ctx.grid, obb):
                continue
            if obb_blocked(ctx.placed, ctx.grid, obb):
                continue
            return (cx - half_w_cm, cz - half_d_cm, round(rotation, 2))
    return None


def _is_access_window(opening: dict[str, Any]) -> bool:
    """落地窗(window_type=floor_to_ceiling 或窗台 ≤15cm)視為出入口。

    陽台門常以落地窗身分存在於 window_segments;它是動線,不是採光帶,
    沙發豁免與矮家具(電視櫃)通行都不適用。無型別資料(DXF 舊圖)一律
    當一般窗,行為與過去相同。
    """
    if opening.get("window_type") == "floor_to_ceiling":
        return True
    try:
        return float(opening["sill_height_cm"]) <= 15.0
    except (KeyError, TypeError, ValueError):
        return False


def _floorplan_segments_cm(
    floorplan: dict[str, Any] | None,
    key: str,
    room: Room,
    where=None,
) -> list[tuple[float, float, float, float]]:
    """payload 的門/窗段 → 角落原點公分線段(與 window_clearance_zones 同一換算)。

    ``where``(選填)以原始 opening dict 過濾,供門窗依型別分流。
    """
    scale = _floorplan_coordinate_scale_cm(floorplan)
    out: list[tuple[float, float, float, float]] = []
    for opening in (floorplan or {}).get(key) or []:
        if where is not None and not where(opening):
            continue
        try:
            start, end = opening["start"], opening["end"]
            out.append((
                float(start["x"]) * scale + room.width / 2,
                float(start["z"]) * scale + room.depth / 2,
                float(end["x"]) * scale + room.width / 2,
                float(end["z"]) * scale + room.depth / 2,
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _scene_rotation_toward(
    source: dict[str, float],
    target: dict[str, float],
) -> float:
    dx = float(target.get("x") or 0) - float(source.get("x") or 0)
    dz = float(target.get("z") or 0) - float(source.get("z") or 0)
    if math.hypot(dx, dz) < 1:
        return 0.0
    return round(math.degrees(math.atan2(dx, dz)) % 360, 2)


def orient_layout_toward_targets(
    scene_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """自由座椅類轉向最近的目標家具;角度貼齊 90° 倍數。

    只轉「不靠牆」的座椅 —— 沙發/沙發床/書桌屬 _WALL_ANCHORED_TYPES,朝向
    由所靠的牆決定;原本也把它們轉向最近的茶几,會產生斜角且脫離牆面,
    而且轉完不再驗證合法性(feedback.png 中斜擺的沙發即由此而來)。
    貼齊 90° 讓椅子與其他家具同為軸對齊,旋轉後足跡不變、無需重新驗證。
    """
    target_types = {
        "office-chair": ("desk",),
        "dining-chair": ("dining-table",),
        "armchair": ("coffee-table", "sofa", "sofa-bed"),
        # lounge-chair 原本不在名單:泛用候選給 rot=0 後就永遠面向 +z,
        # 在客廳常變成面對牆或背對沙發組(feedback.png)。與 armchair 同規則。
        "lounge-chair": ("coffee-table", "sofa", "sofa-bed"),
    }
    valid = [
        item for item in scene_objects
        if not item.get("placement_failed") and item.get("position_cm")
    ]
    for item in valid:
        if item.get("position_locked"):
            continue
        preferred = target_types.get(item.get("normalized_type"))
        if not preferred:
            continue
        targets = [candidate for candidate in valid if candidate.get("normalized_type") in preferred]
        if not targets:
            continue
        source = item["position_cm"]
        target = min(
            targets,
            key=lambda candidate: (
                float(candidate["position_cm"].get("x") or 0) - float(source.get("x") or 0)
            ) ** 2 + (
                float(candidate["position_cm"].get("z") or 0) - float(source.get("z") or 0)
            ) ** 2,
        )
        toward = _scene_rotation_toward(source, target["position_cm"])
        item["rotation_y_deg"] = round(toward / 90.0) * 90.0 % 360
        item["facing_target_id"] = target.get("furniture_id")
    return scene_objects


def room_from_payload(floorplan: dict[str, Any] | None) -> Room:
    """由 payload 的 floorplan 區塊重建引擎 Room(拖曳驗證/重排都是無狀態請求)。

    新資料使用公分；沒有 coordinate_unit 的舊專案視為公尺並在讀取時轉一次。
    沒有牆段(手動模式)就退回矩形房。
    """
    floorplan = floorplan or {}
    width = max(float(floorplan.get("width_cm") or 420), 240)
    depth = max(float(floorplan.get("depth_cm") or 360), 240)
    coordinate_scale = _floorplan_coordinate_scale_cm(floorplan)

    walls: list[Wall] = []
    for seg in floorplan.get("wall_segments") or []:
        try:
            walls.append(
                Wall(
                    float(seg["start"]["x"]) * coordinate_scale + width / 2,
                    float(seg["start"]["z"]) * coordinate_scale + depth / 2,
                    float(seg["end"]["x"]) * coordinate_scale + width / 2,
                    float(seg["end"]["z"]) * coordinate_scale + depth / 2,
                    thickness=6.0,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    if len(walls) < 3:
        return _four_wall_room(width, depth)
    return Room(width=width, depth=depth, walls=walls)


def floorplan_from_editor_payload(editor: dict[str, Any]) -> tuple[dict[str, Any], Room]:
    """Convert the corner-origin centimeter editor state into the 3D contract."""
    width_cm = max(float(editor.get("width_cm") or 420), 240)
    depth_cm = max(float(editor.get("depth_cm") or 360), 240)
    half_width = width_cm / 2
    half_depth = depth_cm / 2
    editor_scale = 1.0 if editor.get("coordinate_unit") == "cm" else 100.0
    structures = editor.get("structures") or {}

    def centered_point(point: dict[str, Any] | None) -> dict[str, float]:
        point = point or {}
        return {
            "x": round(float(point.get("x") or 0) * editor_scale - half_width, 2),
            "z": round(float(point.get("y") or 0) * editor_scale - half_depth, 2),
        }

    def segment(item: dict[str, Any]) -> dict[str, Any]:
        converted = {
            **{
                key: value
                for key, value in item.items()
                if key not in {"start", "end", "swing_end"}
            },
            "start": centered_point(item.get("start")),
            "end": centered_point(item.get("end")),
        }
        # 開合門的 swing_end 與門片端點必須在同一個場景座標系，否則
        # 第 6 步會把關門洞口推到另一面牆上。
        if item.get("swing_end"):
            converted["swing_end"] = centered_point(item.get("swing_end"))
            # 開合門的 start → end 是打開後的門片；牆洞與關門門片
            # 必須使用鉸鏈 start 指向弧線另一端 swing_end 的線段。
        confirmed_opening = item.get("confirmed_wall_opening")
        if isinstance(confirmed_opening, dict):
            opening_start = confirmed_opening.get("start")
            opening_end = confirmed_opening.get("end")
            if isinstance(opening_start, dict) and isinstance(opening_end, dict):
                converted["confirmed_wall_opening"] = {
                    "start": centered_point(opening_start),
                    "end": centered_point(opening_end),
                }
        return converted

    def identified_segments(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        """Preserve editor ids and create stable ids for older saved projects."""
        return [
            segment({
                **item,
                "id": str(item.get("id") or f"{kind}-{index}"),
                # Wall demolition is no longer a RoomPilot structure mode.
                **({"demolition_candidate": False} if kind == "wall" else {}),
            })
            for index, item in enumerate(items or [], start=1)
        ]

    wall_segments = identified_segments(structures.get("walls") or [], "wall")
    door_segments = identified_segments(structures.get("doors") or [], "door")
    window_segments = identified_segments(structures.get("windows") or [], "window")
    beam_segments = identified_segments(structures.get("beams") or [], "beam")
    columns = [
        {
            **{
                key: value
                for key, value in item.items()
                if key != "center"
            },
            "center": centered_point(item.get("center")),
        }
        for item in structures.get("columns") or []
    ]
    room_regions = []
    for room_data in editor.get("rooms") or []:
        ring = []
        for point in room_data.get("polygon_cm") or room_data.get("polygon_m") or []:
            centered = centered_point(point)
            ring.append([centered["x"], centered["z"]])
        if len(ring) < 3:
            continue
        room_regions.append(
            {
                "room_id": str(room_data.get("id") or f"room-{len(room_regions) + 1}"),
                "label": str(room_data.get("label") or "未命名空間"),
                "room_type": str(room_data.get("type") or "default"),
                "exterior": ring,
                "holes": [],
            }
        )

    floorplan = {
        "coordinate_unit": "cm",
        "width_cm": round(width_cm, 2),
        "depth_cm": round(depth_cm, 2),
        "room_height_cm": round(float(editor.get("room_height_cm") or 270), 2),
        "source": "user_confirmed",
        "wall_count": len(wall_segments),
        "door_count": len(door_segments),
        "window_count": len(window_segments),
        "raw_segment_count": len(wall_segments),
        "layers": [],
        "wall_layers": [],
        "door_layers": [],
        "window_layers": [],
        "wall_segments": wall_segments,
        "plan_segments": wall_segments,
        "door_segments": door_segments,
        "window_segments": window_segments,
        "beam_segments": beam_segments,
        "columns": columns,
        "room_regions": room_regions,
    }
    return floorplan, room_from_payload(floorplan)


def _scene_object_to_placed(obj: dict[str, Any], half_w_cm: float, half_d_cm: float) -> PlacedFurniture:
    """payload 場景物件(公分、中心原點、three 旋轉) → 引擎 PlacedFurniture。"""
    size = obj.get("size_cm") or {}
    catalog = catalog_item_from_scene_object(
        obj.get("normalized_type"),
        obj.get("name_zh_raw") or obj.get("furniture_id"),
        float(size.get("width") or 120),
        float(size.get("depth") or 60),
        float(size.get("height") or 80),
    )
    pos = obj.get("position_cm") or {}
    return PlacedFurniture(
        id=str(obj.get("furniture_id") or "item"),
        catalog=catalog,
        pos_x=float(pos.get("x") or 0) + half_w_cm,
        pos_y=float(pos.get("z") or 0) + half_d_cm,
        rotation=(-float(obj.get("rotation_y_deg") or 0)) % 360,
    )


def _shrunk_boundary(room: Room) -> Polygon | None:
    boundary = _room_boundary_polygon(room)
    if boundary is None:
        return None
    shrunk = boundary.buffer(-8.0)
    return boundary if shrunk.is_empty else shrunk


def _regions_boundary(floorplan: dict[str, Any] | None, room: Room) -> Polygon | None:
    """全部房間的聯集多邊形(角落原點)——拖曳可放進任何一間,跨牆自動不合法。

    floorplan["room_regions"] 是房間中心原點的環;沒有(手動矩形模式)回 None。
    """
    polys = _region_polygons(floorplan, room)
    if not polys:
        return None
    union = unary_union(polys)
    shrunk = union.buffer(-8.0)
    return union if shrunk.is_empty else shrunk


def _region_polygons(floorplan: dict[str, Any] | None, room: Room) -> list[Polygon]:
    """Convert canonical centimeter or legacy meter room regions to engine polygons."""
    polys: list[Polygon] = []
    coordinate_scale = _floorplan_coordinate_scale_cm(floorplan)
    for region in (floorplan or {}).get("room_regions") or []:
        try:
            def _shift(ring):
                return [
                    (
                        p[0] * coordinate_scale + room.width / 2,
                        p[1] * coordinate_scale + room.depth / 2,
                    )
                    for p in ring
                ]

            poly = Polygon(_shift(region["exterior"]), [_shift(h) for h in region.get("holes") or []])
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                polys.append(poly)
        except Exception:
            continue
    return polys


def _largest_region_boundary(floorplan: dict[str, Any] | None, room: Room) -> Polygon | None:
    """最大一塊自由空間(角落原點,內縮 8cm)——自動配置集中在主要區域用。"""
    polys = _region_polygons(floorplan, room)
    if not polys:
        return None
    best = max(polys, key=lambda p: p.area)
    shrunk = best.buffer(-8.0)
    return best if shrunk.is_empty else shrunk


def _affinity_room_id(
    floorplan: dict[str, Any] | None,
    normalized_type: str | None,
) -> str | None:
    """沒有指定房間的品項:依 ``knowledge.ROOM_AFFINITY`` 找房型相符的房間。

    沙發、茶几、電視櫃屬 living_room;床、床頭櫃屬 bedroom…。找不到相符房型
    (例如平面圖沒有餐廳)回 None,由呼叫端退回最大區域。
    同一房型有多間時取面積最大的那間,結果具決定性。
    """
    from ..agent.knowledge import ROOM_AFFINITY

    wanted = ROOM_AFFINITY.get(family_of(normalized_type))
    if not wanted:
        return None
    candidates = [
        region
        for region in (floorplan or {}).get("room_regions") or []
        if str(region.get("room_type") or "") in wanted
    ]
    if not candidates:
        return None

    def _area(region: dict[str, Any]) -> float:
        ring = region.get("exterior") or []
        total = 0.0
        for i in range(len(ring)):
            x0, z0 = ring[i][0], ring[i][1]
            x1, z1 = ring[(i + 1) % len(ring)][0], ring[(i + 1) % len(ring)][1]
            total += x0 * z1 - x1 * z0
        return abs(total) / 2

    best = max(candidates, key=lambda region: (_area(region), str(region.get("room_id"))))
    return str(best.get("room_id"))


def generate_layout_by_room(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    *,
    room: Room | None,
    floorplan: dict[str, Any] | None,
    regions_boundary: Polygon | None = None,
    preserve_existing_count: int = 0,
    placement_variant: str = "A",
    hints: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """依 ``placement_room_id`` 分組,**每間房各自在自己的邊界內**擺位。

    原本 build_scene_payload 只呼叫一次 generate_layout,且 place_boundary 固定是
    ``_largest_region_boundary`` —— 整層樓共用「最大那一間」的邊界,遮罩把其餘房間
    全部視為房外,於是所有家具不分房型都被擠進最大的房間(floor04 實測:13 件全部
    落在只比臥室大 0.04 m² 的廚房)。這與 docs/擺位計算邏輯.md §1.2 的「逐房 →
    禁放遮罩 → 房型規則」管線相違。

    沒有 ``placement_room_id`` 的品項改依 ``knowledge.ROOM_AFFINITY`` 找房型相符的
    房間(沙發/茶几/電視櫃 → living_room…);找不到相符房型才退回最大區域。
    回傳順序與 ``items`` 相同,payload 契約不變。
    """
    if room is None or not items:
        return generate_layout(
            room_width_cm, room_depth_cm, items, room=room,
            regions_boundary=regions_boundary,
            place_boundary=_largest_region_boundary(floorplan, room) if room else None,
            floorplan=floorplan, preserve_existing_count=preserve_existing_count,
            placement_variant=placement_variant, hints=hints,
        )

    groups: dict[str, list[int]] = {}
    affinity_assigned: dict[int, str] = {}
    for index, item in enumerate(items):
        key = str(item.get("placement_room_id") or item.get("auto_decor_room_id") or "")
        if not key:
            routed = _affinity_room_id(floorplan, item.get("normalized_type"))
            if routed:
                key = routed
                affinity_assigned[index] = routed
        groups.setdefault(key, []).append(index)

    fallback = _largest_region_boundary(floorplan, room)
    results: dict[int, dict[str, Any]] = {}
    for room_id, indexes in groups.items():
        boundary = _region_boundary_by_id(floorplan, room, room_id) or fallback
        subset = [items[i] for i in indexes]
        # preserve_existing_count 是「原始清單前 N 筆」的語意;分組保持相對順序,
        # 所以該組的保留筆數 = 該組中原始索引 < N 的數量。
        subset_preserve = sum(1 for i in indexes if i < preserve_existing_count)
        placed = generate_layout(
            room_width_cm,
            room_depth_cm,
            subset,
            room=room,
            regions_boundary=regions_boundary,
            place_boundary=boundary,
            floorplan=floorplan,
            preserve_existing_count=subset_preserve,
            placement_variant=placement_variant,
            hints=hints,
        )
        for original_index, obj in zip(indexes, placed):
            # 由適配表決定的房間要寫回 payload,否則前端會照空的 placement_room_id
            # 把它們歸進「未指定空間」,與實際落點不符。
            routed = affinity_assigned.get(original_index)
            if routed and not obj.get("placement_room_id"):
                obj = {**obj, "placement_room_id": routed}
            results[original_index] = obj
    return [results[i] for i in range(len(items))]


def _region_boundary_by_id(
    floorplan: dict[str, Any] | None,
    room: Room,
    room_id: str | None,
) -> Polygon | None:
    """取得指定房間的可擺放邊界，避免修改小房間時誤用最大房間。"""
    if not room_id:
        return None
    coordinate_scale = _floorplan_coordinate_scale_cm(floorplan)
    for region in (floorplan or {}).get("room_regions") or []:
        if str(region.get("room_id")) != str(room_id):
            continue
        try:
            def _shift(ring):
                return [
                    (
                        p[0] * coordinate_scale + room.width / 2,
                        p[1] * coordinate_scale + room.depth / 2,
                    )
                    for p in ring
                ]

            polygon = Polygon(
                _shift(region["exterior"]),
                [_shift(hole) for hole in region.get("holes") or []],
            )
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty:
                return None
            shrunk = polygon.buffer(-8.0)
            return polygon if shrunk.is_empty else shrunk
        except (KeyError, TypeError, ValueError):
            return None
    return None


def scene_object_in_boundary(
    item: dict[str, Any],
    room: Room,
    boundary: Polygon | None,
) -> bool:
    """以家具中心判斷所屬房間；貼牆家具可略跨內縮後的房間邊界。"""
    if not item.get("position_cm") or item.get("placement_failed"):
        return False
    if boundary is None:
        return True
    position = item.get("position_cm") or {}
    return boundary.buffer(12).contains(
        Point(
            float(position.get("x") or 0) + room.width / 2,
            float(position.get("z") or 0) + room.depth / 2,
        )
    )


def validate_single_placement(
    floorplan: dict[str, Any] | None,
    item: dict[str, Any],
    others: list[dict[str, Any]],
) -> dict[str, Any]:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    room = room_from_payload(floorplan)
    # 拖曳可放進「任何一間房」(聯集);沒有房間資訊才退回最大房間環
    boundary = _regions_boundary(floorplan, room) or _shrunk_boundary(room)
    half_w_cm = room.width / 2
    half_d_cm = room.depth / 2

    moving = _scene_object_to_placed(item, half_w_cm, half_d_cm)
    if not _inside_boundary(moving, boundary):
        return {"ok": False, "reason": "超出房間範圍(需完整放在某一間房內,不能跨牆)"}

    if item.get("normalized_type") in _OVERLAY_TYPES:
        reason = check_placement_with_clearance(moving, room, [])
        return {"ok": reason is None, "reason": reason}
    if item.get("normalized_type") in _IGNORE_COLLISION_TYPES:
        return {"ok": True, "reason": None}
    if item.get("normalized_type") != "curtain" and _placement_intersects_zones(
        moving,
        window_clearance_zones(floorplan, room, depth_cm=75.0, where=_is_access_window),
    ):
        return {"ok": False, "reason": "落地窗是陽台出入動線，家具不可擋在前方。"}
    if (
        item.get("normalized_type") not in _WINDOW_CLEARANCE_EXEMPT_TYPES
        and _placement_intersects_zones(
            moving,
            window_clearance_zones(
                floorplan, room,
                where=lambda opening: not _is_access_window(opening),
            ),
        )
    ):
        return {"ok": False, "reason": "家具不可遮擋窗戶前方採光淨空。"}

    placed_others = [
        _scene_object_to_placed(o, half_w_cm, half_d_cm)
        for o in others
        if o.get("normalized_type") not in _IGNORE_COLLISION_TYPES and not o.get("placement_failed")
    ]
    reason = check_placement_with_clearance(moving, room, placed_others)
    return {"ok": reason is None, "reason": reason}


def generate_layout(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    room: Room | None = None,
    regions_boundary: Polygon | None = None,
    place_boundary: Polygon | None = None,
    floorplan: dict[str, Any] | None = None,
    preserve_existing_count: int = 0,
    placement_variant: str = "A",
    hints: dict[str, dict[str, Any]] | None = None,
    validate_only: bool = False,
) -> list[dict[str, Any]]:
    """家具座標一律由 furniture_engine 決定(柵格碰撞 + 淨空裁決)。

    擺放邏輯(hints 啟用時,每件依序走第一個命中的路徑):

    1. 鎖定/保留件:使用者擺過的位置仍合法就照舊,並登記進柵格。
    2. 擺放順序:基礎家具(床/沙發/餐桌/書桌/衣櫃,knowledge.ESSENTIAL_
       FAMILIES)最先卡位 → 泛用件 → 副件貼主件 → 自由座椅撿剩餘空間
       (順序由 agent 的 placement_hints 提供,其他物件都依基礎家具的
       位置再配置)。
    3. 合法性三種遮罩一次判:房間邊界+門前動線+落地窗通行縫(low)、
       窗前採光帶(band,沙發族系豁免)、沙發視聽走廊(corridor,
       茶几/電視櫃/地毯豁免)。
    4. 副件與休閒椅嚴格成組:只試主件旁的成組候選,貼不上標
       placement_failed 交 resolve_placements 寧缺勿亂;不退泛用亂放。
    5. 泛用件:類型錨點 → 靠牆錨定掃描 → 網格散點 → 引擎後援;全數
       不合法才標 placement_failed。

    ``validate_only``:進入即時寫實前的最終確認用。信任使用者已鎖定的配置,
    每件座標一律照舊、**絕不重排**,只回報是否合法(房間邊界 + 門窗淨空;家具間
    碰撞由前端 config 檢查把關)。避免嚴格重排把合法配置塌成 (0,0) 疊在原點、
    並把「確認」擋在原步驟(見 scene_v2.confirmWhiteModel)。

    座標契約(對前端不變):position_cm 為房間中心原點、公分;rotation_y_deg
    為 three.js 的 Y 軸旋轉(與引擎旋轉方向相反,進出引擎時取負號)。

    hints(選填,2026-08-02 併入 yen agent 擺位紀律):以 instance_id 或
    furniture_id 為鍵的 ``{"priority", "group", "anchor"}``。只影響「試放順序」
    與嚴格成組的啟用;hints=None 時維持 bella 流程的舊行為(泛用候選、無
    走廊、無嚴格成組),合法性一律仍由柵格把關。
    """
    if room is None:
        room = _four_wall_room(max(room_width_cm, 240), max(room_depth_cm, 240))

    # 擺放搜尋邊界(內縮 8cm 邊距):DXF 模式傳入最大自由空間;
    # 矩形房由牆環重建(等價於 bbox)。注意 DXF fallback 模式的 Room.walls
    # 是多個獨立環,不能拿去重建多邊形 —— 所以 DXF 一律走傳入的 place_boundary。
    boundary = place_boundary if place_boundary is not None else _shrunk_boundary(room)
    forbidden_zones = window_clearance_zones(floorplan, room)

    room_w_cm = room.width
    room_d_cm = room.depth
    half_w_cm = room_w_cm / 2
    half_d_cm = room_d_cm / 2
    placement_bounds_cm: tuple[float, float, float, float] | None = None
    if boundary is not None:
        min_x, min_y, max_x, max_y = boundary.bounds
        placement_bounds_cm = (
            min_x - half_w_cm,
            max_x - half_w_cm,
            min_y - half_d_cm,
            max_y - half_d_cm,
        )

    placed: list[PlacedFurniture] = []
    placed_by_type: dict[str, list[PlacedFurniture]] = {}
    results: dict[int, dict[str, Any]] = {}

    # 碰撞判定的唯一權威(docs/擺位計算邏輯.md §3、§5):房間環、門前動線與
    # 窗前採光帶全部烘進布林網格,取代原本 Shapely 的三段分散檢查。
    raster = build_raster_context(room, boundary, floorplan)

    # 視聽走廊:沙發正前到對面牆的帶狀區,只留給茶几/電視櫃/地毯(成組件),
    # 其他家具不得插進沙發與電視櫃之間(feedback:躺椅/櫃體卡在觀影軸線)。
    # 僅 agent 紀律(hints)啟用;寬 = 沙發寬,深 = 沙發前緣到可擺邊界。
    corridor_mask = raster.grid.blank() if raster is not None and hints else None
    corridor_stamped = False

    def _corridor_blocks(kind: str | None, w: float, d: float, x_cm: float, z_cm: float, rot: float) -> bool:
        if corridor_mask is None or not corridor_stamped or kind in _CORRIDOR_EXEMPT_TYPES:
            return False
        obb = Obb.from_deg(x_cm + half_w_cm, z_cm + half_d_cm, w, d, -rot)
        return obb_blocked(corridor_mask, raster.grid, obb)

    def _stamp_corridor(x_cm: float, z_cm: float, rot: float, w: float, d: float) -> None:
        nonlocal corridor_stamped
        if corridor_mask is None or corridor_stamped:
            return                       # ponytail: 只護第一張沙發的軸線,多沙發房再說
        fx, fz = _facing(rot)
        b_left, b_right, b_top, b_bottom = (
            placement_bounds_cm or (-half_w_cm, half_w_cm, -half_d_cm, half_d_cm)
        )
        front_x = x_cm + fx * d / 2
        front_z = z_cm + fz * d / 2
        # 斜擺沙發取主軸近似距離即可,合法性仍由柵格判
        if abs(fx) >= abs(fz):
            dist = (b_right - front_x) if fx > 0 else (front_x - b_left)
        else:
            dist = (b_bottom - front_z) if fz > 0 else (front_z - b_top)
        if dist <= 0:
            return
        cx = front_x + fx * dist / 2
        cz = front_z + fz * dist / 2
        stamp_obb(
            corridor_mask, raster.grid,
            Obb.from_deg(cx + half_w_cm, cz + half_d_cm, w, dist, -rot),
        )
        corridor_stamped = True

    def _raster_accepts(engine_item: PlacedFurniture | None, kind: str | None) -> bool:
        """Shapely 提議、柵格裁決:引擎回的候選仍須通過布林網格才算合法。"""
        if engine_item is None:
            return False
        x_rel = engine_item.pos_x - half_w_cm
        z_rel = engine_item.pos_y - half_d_cm
        rot_scene = (-engine_item.rotation) % 360
        if _corridor_blocks(
            kind, engine_item.catalog.width, engine_item.catalog.depth, x_rel, z_rel, rot_scene
        ):
            return False
        return raster_free(
            raster, kind,
            engine_item.catalog.width, engine_item.catalog.depth, engine_item.catalog.height,
            x_rel, z_rel,
            rot_scene, half_w_cm, half_d_cm,
            check_placed=kind not in _OVERLAY_TYPES,
        )

    def _hint_for(item: dict[str, Any]) -> dict[str, Any] | None:
        if not hints:
            return None
        return hints.get(item.get("instance_id")) or hints.get(item.get("furniture_id"))

    # 鎖定位置(使用者拖曳過)的先處理,避免被後放的家具擠掉;其次照 agent
    # priority 提示(升冪),沒有提示的照佔地面積大到小(床/沙發/衣櫃先卡好牆位,
    # 小件再見縫插針)。輸出仍照原始 items 順序,不動前端拿到的清單順序。
    def _order_key(i: int) -> tuple[Any, ...]:
        locked_rank = 0 if items[i].get("position_locked") else 1
        priority = (_hint_for(items[i]) or {}).get("priority")
        if isinstance(priority, int):
            return (locked_rank, 0, priority, 0.0, i)
        area = _size_cm(items[i], "width", 120) * _size_cm(items[i], "depth", 60)
        return (locked_rank, 1, 0, -area, i)

    order = sorted(range(len(items)), key=_order_key)
    # 族系 → 已擺好的代表家具(成組候選用:床頭櫃貼床、椅子貼書桌…)
    neighbors: dict[str, dict[str, float]] = {}

    for index in order:
        item = items[index]
        item_type = item.get("normalized_type")
        width = _size_cm(item, "width", 120)
        depth = _size_cm(item, "depth", 60)
        height = _size_cm(item, "height", 80)
        curtain_hint = None
        if item_type == "curtain":
            curtain_hint = curtain_window_hint(
                floorplan,
                room_width_cm=room_w_cm,
                room_depth_cm=room_d_cm,
                boundary=boundary,
            )
            if curtain_hint:
                width = curtain_hint[3]
        catalog = catalog_item_from_scene_object(
            item_type, item.get("name_zh_raw") or item.get("furniture_id"), width, depth, height
        )
        # agent 的 count 展開會給 instance_id(同型多件),沒有才退回合成 id。
        # bella 流程不設 instance_id,故此處對既有行為為 no-op。
        item_id = str(item.get("instance_id") or f"{item_type or 'item'}_{index + 1}")

        x_cm: float | None = None
        z_cm: float | None = None
        rotation = 0.0
        failed_reason: str | None = None
        locked = False
        kept_position = False

        preserve_position = index < preserve_existing_count and item.get("position_cm")
        if validate_only and item.get("position_cm"):
            # 檢驗專用:座標照舊、絕不重排,只回報合法與否。房間邊界用聯集 + 12cm
            # 容差(跨房拖曳、換 GLB 尺寸微變不誤殺);家具間碰撞前端已把關,故
            # check_placed=False —— 嚴格累計碰撞正是把合法配置塌成 (0,0) 的元凶。
            candidate = _scene_object_to_placed(item, half_w_cm, half_d_cm)
            lenient_boundary = regions_boundary or boundary
            if lenient_boundary is not None:
                lenient_boundary = lenient_boundary.buffer(12)
            lock_rot = float(item.get("rotation_y_deg") or 0)
            legal = _inside_boundary(candidate, lenient_boundary) and raster_free(
                raster, item_type, width, depth, height,
                float(item["position_cm"].get("x") or 0),
                float(item["position_cm"].get("z") or 0),
                lock_rot, half_w_cm, half_d_cm,
                check_placed=False,
            )
            x_cm = float(item["position_cm"].get("x") or 0)
            z_cm = float(item["position_cm"].get("z") or 0)
            rotation = lock_rot
            locked = bool(item.get("position_locked"))
            kept_position = True
            if not legal:
                failed_reason = "位置超出房間或壓到門窗淨空,請調整後再確認。"
        elif (item.get("position_locked") or preserve_position) and item.get("position_cm"):
            # 使用者手動擺過:位置仍合法就保留,不重排。
            # 驗證用「所有房間聯集」—— 使用者可能把家具拖到別的房間,重排不能把它踢掉
            candidate = _scene_object_to_placed(item, half_w_cm, half_d_cm)
            locked_boundary = regions_boundary or boundary
            # 2D 貼牆家具允許落在房間內縮邊界的 12cm 容差內，否則換 GLB
            # 後會被誤判超界並跳到其他房間。
            if locked_boundary is not None:
                locked_boundary = locked_boundary.buffer(12)
            # 使用者拖曳過的位置改用柵格覆核;跨房間容差仍由 locked_boundary
            # 的 12cm 緩衝表達(換 GLB 後尺寸微變不該被踢掉)。
            lock_rot = float(item.get("rotation_y_deg") or 0)
            ok = _inside_boundary(candidate, locked_boundary) and raster_free(
                raster, item_type, width, depth, height,
                float(item["position_cm"].get("x") or 0),
                float(item["position_cm"].get("z") or 0),
                lock_rot, half_w_cm, half_d_cm,
                check_placed=item_type not in _OVERLAY_TYPES,
            )
            if ok:
                x_cm = float(item["position_cm"].get("x") or 0)
                z_cm = float(item["position_cm"].get("z") or 0)
                rotation = float(item.get("rotation_y_deg") or 0)
                locked = bool(item.get("position_locked"))
                kept_position = True
                if item_type not in _IGNORE_COLLISION_TYPES and item_type not in _OVERLAY_TYPES:
                    placed.append(candidate)
                    placed_by_type.setdefault(item_type or "furniture", []).append(candidate)
                    raster_commit(
                        raster, item_type, width, depth,
                        x_cm, z_cm, rotation, half_w_cm, half_d_cm,
                    )

        if kept_position:
            pass
        elif item_type in _OVERLAY_TYPES:
            relation = item.get("placement_relation") or {}
            target_types = relation.get("target_types") or ["sofa", "sofa-bed", "bed", "bed-frame"]
            target = next(
                (
                    placed_by_type[target_type][-1]
                    for target_type in target_types
                    if placed_by_type.get(target_type)
                    and _inside_boundary(
                        placed_by_type[target_type][-1],
                        boundary.buffer(12) if boundary is not None else None,
                    )
                ),
                None,
            )
            if target is not None:
                overlay = place_overlay_on_furniture(room, catalog, item_id, target)
                engine_item = overlay["placed"] if overlay["success"] else None
                if _raster_accepts(engine_item, item_type):
                    x_cm = engine_item.pos_x - half_w_cm
                    z_cm = engine_item.pos_y - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    failed_reason = overlay["reason"] or "地毯超出房間或碰到牆面"
                    x_cm, z_cm = 0.0, 0.0
            else:
                overlay = place_furniture(room, catalog, item_id, [])
                engine_item = overlay["placed"] if overlay["success"] else None
                if _raster_accepts(engine_item, item_type):
                    x_cm = engine_item.pos_x - half_w_cm
                    z_cm = engine_item.pos_y - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    engine_item = _grid_place_in_boundary(
                        catalog, item_id, room, [], boundary, forbidden_zones
                    )
                    if engine_item is not None:
                        x_cm = engine_item.pos_x - half_w_cm
                        z_cm = engine_item.pos_y - half_d_cm
                        rotation = (-engine_item.rotation) % 360
                    else:
                        failed_reason = overlay["reason"] or "地毯找不到合法位置"
                        x_cm, z_cm = 0.0, 0.0
        elif (item.get("placement_relation") or {}).get("kind") == "adjacent":
            relation = item.get("placement_relation") or {}
            target_types = relation.get("target_types") or [
                "sofa", "sofa-bed", "bed", "bed-frame", "desk", "dining-table",
            ]
            target = next(
                (
                    placed_by_type[target_type][-1]
                    for target_type in target_types
                    if placed_by_type.get(target_type)
                    and _inside_boundary(
                        placed_by_type[target_type][-1],
                        boundary.buffer(12) if boundary is not None else None,
                    )
                ),
                None,
            )
            adjacent = (
                place_adjacent_to_furniture(room, catalog, item_id, target, placed)
                if target is not None
                else {"success": False, "placed": None, "reason": "房間內沒有可依附的主家具"}
            )
            engine_item = adjacent["placed"] if adjacent["success"] else None
            if _raster_accepts(engine_item, item_type):
                placed.append(engine_item)
                placed_by_type.setdefault(item_type or "furniture", []).append(engine_item)
                x_cm = engine_item.pos_x - half_w_cm
                z_cm = engine_item.pos_y - half_d_cm
                rotation = (-engine_item.rotation) % 360
                raster_commit(
                    raster, item_type, catalog.width, catalog.depth,
                    x_cm, z_cm, rotation, half_w_cm, half_d_cm,
                )
            else:
                failed_reason = adjacent["reason"] or "主家具旁沒有合法位置"
                x_cm, z_cm = 0.0, 0.0
        elif item_type in _IGNORE_COLLISION_TYPES:
            if item_type == "wall-shelf":
                x_cm = -half_w_cm + width / 2 + 15
                z_cm = -half_d_cm + depth / 2 + 12
            else:
                x_cm, z_cm = 0.0, 0.0
            # 非矩形房間:固定點可能落在房間多邊形外(牆體裡),退到多邊形內部代表點
            probe = PlacedFurniture(
                id=item_id, catalog=catalog,
                pos_x=x_cm + half_w_cm, pos_y=z_cm + half_d_cm,
            )
            if boundary is not None and not _inside_boundary(probe, boundary):
                inner = boundary.representative_point()
                x_cm = inner.x - half_w_cm
                z_cm = inner.y - half_d_cm
        else:
            # 副件嚴格成組(agent 紀律,hints 時啟用):床頭櫃/茶几/電視櫃/餐椅/
            # 辦公椅只准貼各自主件的成組候選 —— 原本成組位失敗會退到泛用候選
            # 「亂放成功」,床頭櫃流落遠牆、引擎又不標失敗,寧缺勿亂永遠不觸發。
            # 休閒椅(armchair/lounge)在沙發已就位的房間同樣嚴格:只准沙發
            # 左前/右前;沒有沙發的房間(書房閱讀椅)維持自由擺放。
            # 主件不在或成組位全被佔 → 標 placement_failed,交 resolve_placements
            # 移除。使用者拖曳(placement_hint_cm)不受限,尊重手動意圖。
            item_family = family_of(item_type)
            strict_pair = (
                bool(hints)
                and not item.get("placement_hint_cm")
                and (
                    item_family in COMPANION_OF
                    or (item_family in FREE_SEATING_FAMILIES and "sofa" in neighbors)
                )
            )
            if strict_pair:
                b_left, b_right, b_top, b_bottom = (
                    placement_bounds_cm
                    or (-half_w_cm, half_w_cm, -half_d_cm, half_d_cm)
                )
                candidates = _agent_prepend_candidates(
                    item_type, width, depth, None, neighbors,
                    b_left, b_right, b_top, b_bottom,
                    (b_left + b_right) / 2, (b_top + b_bottom) / 2,
                )
            else:
                candidates = _placement_candidates(
                    item_type,
                    width,
                    depth,
                    room_w_cm,
                    room_d_cm,
                    placement_bounds_cm,
                    hint=_hint_for(item),
                    neighbors=neighbors,
                )
                if placement_variant == "B" and len(candidates) > 9:
                    # 方案 B 仍走相同碰撞/淨空驗證,只反轉「類型錨點」的嘗試順序
                    # (換一面牆開始)。3×3 網格散點維持在最後 —— 原本整串反轉會讓
                    # B 案的靠牆家具從房間中央的網格點開始試,永遠貼不了牆。
                    candidates = list(reversed(candidates[:-9])) + candidates[-9:]
                elif placement_variant == "B" and len(candidates) > 1:
                    candidates = list(reversed(candidates))
                hinted_wall_candidate = _hinted_wall_candidate(
                    item_type,
                    width,
                    depth,
                    item.get("placement_hint_cm"),
                    placement_bounds_cm,
                )
                if hinted_wall_candidate is not None:
                    candidates.insert(0, hinted_wall_candidate)
                if curtain_hint:
                    candidates.insert(0, curtain_hint[:3])
            def _try_candidate(raw_x: float, raw_z: float, rot: float, *, clamp: bool = True) -> tuple[float, float] | None:
                fp_w, fp_d = _rotated_footprint(width, depth, rot)
                clamp_margin = 0 if item_type in _WALL_ANCHORED_TYPES else 18
                candidate_left, candidate_right, candidate_top, candidate_bottom = (
                    placement_bounds_cm
                    or (-half_w_cm, half_w_cm, -half_d_cm, half_d_cm)
                )
                cand_x = _clamp_axis(raw_x, candidate_left, candidate_right, fp_w, clamp_margin) if clamp else raw_x
                cand_z = _clamp_axis(raw_z, candidate_top, candidate_bottom, fp_d, clamp_margin) if clamp else raw_z
                if _corridor_blocks(item_type, width, depth, cand_x, cand_z, rot):
                    return None
                if raster_free(
                    raster, item_type, width, depth, height,
                    cand_x, cand_z, rot, half_w_cm, half_d_cm,
                ):
                    return cand_x, cand_z
                return None

            # 嘗試順序:類型錨點 → 靠牆錨定掃描(僅靠牆類)→ 3×3 網格散點。
            # 網格散點原本緊接在類型錨點之後 —— 門前動線帶恰好壓掉每面牆僅有的
            # 2-3 個錨點時,靠牆家具就直接落在房間中央的網格點(floor04 客廳實測:
            # 沙發/電視櫃/茶几全數散落網格點)。掃描沿輪廓邊補完整錨點序列。
            # 嚴格成組件只有成組候選,無網格散點、無靠牆掃描、無引擎後援。
            anchor_list = candidates
            grid_list: list[tuple[float, float, float]] = []
            if not strict_pair and item_type in _WALL_ANCHORED_TYPES and len(candidates) > 9:
                anchor_list, grid_list = candidates[:-9], candidates[-9:]

            chosen: tuple[float, float, float] | None = None
            for raw_x, raw_z, rot in anchor_list:
                accepted = _try_candidate(raw_x, raw_z, rot)
                if accepted is not None:
                    chosen = (accepted[0], accepted[1], rot)
                    break
            if chosen is None and not strict_pair and item_type in _WALL_ANCHORED_TYPES:
                chosen = _raster_wall_anchor(
                    raster, item_type, width, depth, height, half_w_cm, half_d_cm,
                )
                if chosen is not None and _corridor_blocks(
                    item_type, width, depth, chosen[0], chosen[1], chosen[2]
                ):
                    chosen = None        # 靠牆掃描不認得走廊,事後覆核
            if chosen is None:
                for raw_x, raw_z, rot in grid_list:
                    accepted = _try_candidate(raw_x, raw_z, rot)
                    if accepted is not None:
                        chosen = (accepted[0], accepted[1], rot)
                        break

            if strict_pair and chosen is None:
                if item_family in FREE_SEATING_FAMILIES:
                    failed_reason = "休閒椅僅能擺在沙發左前或右前，目前沒有合法位置。"
                else:
                    anchors_zh = "、".join(
                        FAMILY_ZH.get(a, a) for a in COMPANION_OF[item_family]
                    )
                    failed_reason = f"需與{anchors_zh}成組擺放，主件不在或旁邊沒有合法位置。"
                x_cm, z_cm = 0.0, 0.0
            elif chosen is not None:
                x_cm, z_cm, rotation = chosen
                candidate = PlacedFurniture(
                    id=item_id,
                    catalog=catalog,
                    pos_x=x_cm + half_w_cm,
                    pos_y=z_cm + half_d_cm,
                    rotation=(-rotation) % 360,
                )
                placed.append(candidate)
                placed_by_type.setdefault(item_type or "furniture", []).append(candidate)
                raster_commit(
                    raster, item_type, width, depth,
                    x_cm, z_cm, rotation, half_w_cm, half_d_cm,
                )
            else:
                result = place_furniture(room, catalog, item_id, placed)
                engine_item = result["placed"] if result["success"] else None
                if not _raster_accepts(engine_item, item_type):
                    engine_item = None
                if engine_item is None and boundary is not None:
                    # 柵格/走廊裁決參與掃描:第一個合格點被走廊否決時繼續找側位
                    engine_item = _grid_place_in_boundary(
                        catalog, item_id, room, placed, boundary, forbidden_zones,
                        accepts=lambda cand: _raster_accepts(cand, item_type),
                    )
                if engine_item is not None:
                    placed.append(engine_item)
                    placed_by_type.setdefault(item_type or "furniture", []).append(engine_item)
                    x_cm = engine_item.pos_x - half_w_cm
                    z_cm = engine_item.pos_y - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                    raster_commit(
                        raster, item_type, catalog.width, catalog.depth,
                        x_cm, z_cm, rotation, half_w_cm, half_d_cm,
                    )
                else:
                    failed_reason = result["reason"] or "找不到落在房間形狀內的合法位置"
                    x_cm, z_cm = 0.0, 0.0

        fp_w, fp_d = _rotated_footprint(width, depth, rotation)
        results[index] = {
            "furniture_id": item["furniture_id"],
            # 同型多件時前端/agent 靠 instance_id 分辨(例:床頭櫃 ×2)
            "instance_id": item_id,
            "catalog_furniture_id": item.get("catalog_furniture_id"),
            "name_zh_raw": item.get("name_zh_raw"),
            "normalized_type": item_type,
            "model_url": item.get("model_url"),
            "primary_style": item.get("primary_style"),
            "material": item.get("material"),
            "price": item.get("price"),
            "price_twd": item.get("price_twd"),
            "price_ntd": item.get("price_ntd"),
            "size_cm": {"width": width, "depth": depth, "height": height},
            "catalog_size_cm": item.get("catalog_size_cm"),
            "footprint_cm": {"width": round(fp_w, 2), "depth": round(fp_d, 2)},
            "position_cm": {"x": round(x_cm, 2), "z": round(z_cm, 2)},
            # 契約:0 ≤ rotation_y_deg < 360(候選表沿用 -90 慣寫,出口正規化)
            "rotation_y_deg": rotation % 360,
            "position_locked": locked,
            "placement_failed": bool(failed_reason),
            "placement_reason": failed_reason,
            "placement_engine": (
                "boundary_rule"
                if item_type in _IGNORE_COLLISION_TYPES
                else "furniture_engine"
            ),
            "auto_decor_role": item.get("auto_decor_role"),
            "auto_decor_room_id": item.get("auto_decor_room_id"),
            "placement_relation": item.get("placement_relation"),
            "placement_room_id": item.get("placement_room_id"),
        }

        # 成組候選要有已就位的主件可貼:每擺好一件就登記該族系的代表家具。
        # 只登記成功擺放的,失敗的不能當錨(否則副件會貼到不存在的位置)。
        if hints and not failed_reason:
            family = family_of(item_type)
            if family not in neighbors:
                neighbors[family] = {
                    "x": x_cm, "z": z_cm, "rot": rotation,
                    "width": width, "depth": depth,
                }
            if family == "sofa" and not validate_only:
                # 沙發定位後保留正前視聽走廊,後續泛用件/自由座椅不得插入
                _stamp_corridor(x_cm, z_cm, rotation, width, depth)

    return orient_layout_toward_targets([results[i] for i in range(len(items))])


def _flip_parsed_z(parsed: dict[str, Any]) -> dict[str, Any]:
    """把 dxf_parser 輸出的 z 軸取負。

    DXF 的 y 軸朝北(俯視圖),three.js 的 +z 軸朝向觀察者(南)——
    不翻轉的話畫面等於從地板下方往上看(鏡像/下視圖)。
    在來源處翻轉一次,下游(Room/引擎/payload)全部同一座標框。
    """
    def flip_ring(ring: list) -> list:
        return [[p[0], -p[1]] for p in ring]

    out = dict(parsed)
    out["wall_polys"] = [
        {
            "exterior": flip_ring(poly.get("exterior") or []),
            "holes": [flip_ring(hole) for hole in poly.get("holes") or []],
        }
        for poly in parsed.get("wall_polys") or []
    ]
    # 含門窗開口的牆體(upgrade3d/wall_openings.py 產出)必須跟 wall_polys 同框,
    # 否則有開口的牆會相對其他幾何鏡像。parsed 沒有這個鍵時本段為 no-op。
    if parsed.get("wall_solids") is not None:
        out["wall_solids"] = [
            {
                **solid,
                "polys": [
                    {
                        "exterior": flip_ring(poly.get("exterior") or []),
                        "holes": [flip_ring(hole) for hole in poly.get("holes") or []],
                    }
                    for poly in solid.get("polys") or []
                ],
            }
            for solid in parsed.get("wall_solids") or []
        ]
    for key in ("windows", "doors"):
        out[key] = [
            {"x1": s["x1"], "z1": -s["z1"], "x2": s["x2"], "z2": -s["z2"]}
            for s in parsed.get(key) or []
        ]
    bbox = parsed.get("bbox") or {}
    if bbox:
        out["bbox"] = {
            "minx": bbox["minx"],
            "maxx": bbox["maxx"],
            "minz": -bbox["maxz"],
            "maxz": -bbox["minz"],
        }
    return out


def parse_floorplan_with_engine(dxf_text: str) -> tuple[dict[str, Any] | None, Room | None]:
    """DXF 文字 → (payload 的 floorplan 區塊, 引擎 Room)。

    解析走 upgrade3d.dxf_parser(ezdxf,平面中心原點、公尺),
    再由 engine.dxf_room 取最大封閉房間轉成 Room(角落原點)。
    回傳的線段座標一律換算成「房間中心原點、公分」。
    """
    try:
        parsed = _flip_parsed_z(parse_dxf_bytes(dxf_text.encode("utf-8", errors="ignore"), "upload.dxf"))
        build = build_room_from_dxf(parsed)
        bbox = parsed.get("bbox") or {}
        plan_area = max(
            (float(bbox.get("maxx", 0)) - float(bbox.get("minx", 0)))
            * (float(bbox.get("maxz", 0)) - float(bbox.get("minz", 0))),
            0.0,
        )
        selected_area = build.room.width * build.room.depth / 10_000
        if build.mode == "largest" and plan_area and selected_area / plan_area < 0.25:
            build = build_room_from_dxf(parsed, mode="plan")
    except Exception:
        return None, None

    room = build.room
    ox, oz = build.offset
    room_center_x_cm = ox + room.width / 2
    room_center_z_cm = oz + room.depth / 2

    wall_segments = [
        {
            "start": {"x": round(w.x1 - room.width / 2, 1), "z": round(w.y1 - room.depth / 2, 1)},
            "end": {"x": round(w.x2 - room.width / 2, 1), "z": round(w.y2 - room.depth / 2, 1)},
        }
        for w in room.walls
    ]

    def _convert(segs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "start": {
                    "x": round(s["x1"] * 100 - room_center_x_cm, 1),
                    "z": round(s["z1"] * 100 - room_center_z_cm, 1),
                },
                "end": {
                    "x": round(s["x2"] * 100 - room_center_x_cm, 1),
                    "z": round(s["z2"] * 100 - room_center_z_cm, 1),
                },
            }
            for s in segs
        ]

    doors = _convert(parsed.get("doors", []))
    windows = _convert(parsed.get("windows", []))
    stats = parsed.get("stats", {})

    def _ring_to_payload(coords) -> list:
        return [
            [
                round(point[0] * 100 - room_center_x_cm, 1),
                round(point[1] * 100 - room_center_z_cm, 1),
            ]
            for point in coords
        ]

    wall_polys = [
        {
            "exterior": _ring_to_payload(poly.get("exterior") or []),
            "holes": [
                _ring_to_payload(hole)
                for hole in poly.get("holes") or []
                if len(hole) >= 3
            ],
        }
        for poly in parsed.get("wall_polys") or []
        if len(poly.get("exterior") or []) >= 3
    ]

    # 可擺放區域 = bbox 減去牆體實心區(自由空間),面積 ≥1m² 的每一塊當一個 region。
    # 這對「有封閉房間」與「開放式牆線(如 floor01,沒有 holes)」兩種 DXF 都成立;
    # 不能用 Room.walls 重建多邊形 —— fallback 模式下那是多個獨立環串接,會得到垃圾幾何。
    room_regions = []
    try:
        solids = []
        for poly in parsed.get("wall_polys") or []:
            shell = poly.get("exterior") or []
            if len(shell) < 3:
                continue
            solid = Polygon(shell, [h for h in (poly.get("holes") or []) if len(h) >= 3])
            if not solid.is_valid:
                solid = solid.buffer(0)
            if not solid.is_empty:
                solids.append(solid)
        bb = parsed["bbox"]
        free = shapely_box(bb["minx"], bb["minz"], bb["maxx"], bb["maxz"]).difference(unary_union(solids))
        pieces = list(free.geoms) if free.geom_type == "MultiPolygon" else [free]
        for piece in pieces:
            if piece.is_empty or piece.area < 1.0:
                continue
            # 必須保留 interiors:牆體在自由空間裡是「洞」,丟掉洞家具就能疊在牆上
            room_regions.append(
                {
                    "exterior": _ring_to_payload(piece.exterior.coords),
                    "holes": [_ring_to_payload(ring.coords) for ring in piece.interiors],
                }
            )
    except Exception:
        room_regions = []

    floorplan = {
        "coordinate_unit": "cm",
        "width_cm": round(room.width, 1),
        "depth_cm": round(room.depth, 1),
        "source": "dxf",
        "wall_count": len(room.walls),
        "door_count": len(doors),
        "window_count": len(windows),
        "raw_segment_count": int(stats.get("wall_segments", 0)),
        "layers": [],
        "wall_layers": [],
        "door_layers": [],
        "window_layers": [],
        "wall_segments": wall_segments,
        "wall_polys": wall_polys,
        "plan_segments": wall_segments,
        "door_segments": doors,
        "window_segments": windows,
        "room_regions": room_regions,
    }
    return floorplan, room


def build_scene_payload(
    site_payload: dict[str, Any],
    questionnaire: dict[str, Any],
    floorplan_path: str | None,
    room_width_cm: float,
    room_depth_cm: float,
) -> dict[str, Any]:
    parsed_floorplan = None
    engine_room = None
    editor_floorplan = questionnaire.get("floorplan_editor")
    layout_json = questionnaire.get("layout_json")
    dxf_text = questionnaire.get("floorplan_dxf_text")
    if isinstance(layout_json, dict) and isinstance(layout_json.get("floorplan"), dict):
        parsed_floorplan = layout_json["floorplan"]
        engine_room = room_from_payload(parsed_floorplan)
    elif isinstance(layout_json, dict) and layout_json.get("wall_segments"):
        parsed_floorplan = layout_json
        engine_room = room_from_payload(parsed_floorplan)
    elif isinstance(editor_floorplan, dict) and editor_floorplan:
        parsed_floorplan, engine_room = floorplan_from_editor_payload(editor_floorplan)
    elif dxf_text:
        parsed_floorplan, engine_room = parse_floorplan_with_engine(dxf_text)

    effective_width_cm = parsed_floorplan["width_cm"] if parsed_floorplan else room_width_cm
    effective_depth_cm = parsed_floorplan["depth_cm"] if parsed_floorplan else room_depth_cm

    llm_mode, plan, llm_model = build_scene_plan(questionnaire, site_payload["styles"])
    appliance_requirements = questionnaire.get("appliance_requirements") or []
    selected_items, unavailable_types = choose_furniture_items(
        plan,
        site_payload["furniture"],
        questionnaire.get("furniture_random_seed"),
        effective_width_cm,
        effective_depth_cm,
        plan.get("preferred_colors", []) + questionnaire.get("custom_colors", []),
    )
    exact_selected_items = selected_furniture_items_from_questionnaire(
        questionnaire,
        site_payload["furniture"],
    )
    if questionnaire.get("selected_furniture_exact") is True:
        selected_items = exact_selected_items
        unavailable_types = []
    elif exact_selected_items:
        exact_ids = {item.get("furniture_id") for item in exact_selected_items}
        exact_types = {item.get("normalized_type") for item in exact_selected_items}
        selected_items = [
            *exact_selected_items,
            *[
                item
                for item in selected_items
                if item.get("furniture_id") not in exact_ids
                and item.get("normalized_type") not in exact_types
            ],
        ]
    objects = generate_layout_by_room(
        effective_width_cm,
        effective_depth_cm,
        selected_items,
        room=engine_room,
        floorplan=parsed_floorplan,
        regions_boundary=_regions_boundary(parsed_floorplan, engine_room) if engine_room else None,
        # agent 的擺位紀律(主件先、成組語意)必須從第一次擺位就生效:
        # 沒有 hints 時 generate_layout 不登記 neighbors,成組候選
        # (電視櫃在沙發對面牆、茶几在沙發正前)整條路是死的,電視櫃
        # 會被靠牆掃描放到任一面長牆,與沙發呈 L 型(feedback.png)。
        hints=placement_hints(selected_items),
    )
    placement_resolution_report: list[dict[str, Any]] = []
    if any(obj.get("placement_failed") for obj in objects):
        protected_ids = {
            str(item.get("furniture_id"))
            for item in selected_items
            if item.get("furniture_id")
            and (
                item.get("user_specified")
                or item.get("user_required")
                or item.get("position_locked")
            )
        }

        def replace_and_place(working_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return generate_layout_by_room(
                effective_width_cm,
                effective_depth_cm,
                working_items,
                room=engine_room,
                floorplan=parsed_floorplan,
                regions_boundary=_regions_boundary(parsed_floorplan, engine_room) if engine_room else None,
                # 提示每次依潛規則重算,換小/移除後主副件順序仍正確
                hints=placement_hints(working_items),
            )

        objects, selected_items, placement_resolution_report = resolve_placements(
            objects,
            selected_items,
            site_payload["furniture"],
            engine_place_fn=replace_and_place,
            protected_ids=protected_ids,
        )

    style = next(
        (style for style in site_payload["styles"] if style.get("style_id") == plan["style_id"]),
        site_payload["styles"][0],
    )
    style_card = find_taiwan_style_card(
        site_payload.get("taiwan_style_cards", []),
        questionnaire.get("style_card_id"),
    )
    surface_catalog = site_payload.get("surface_catalog", {})

    return {
        "scene_id": f"scene_{uuid.uuid4().hex[:10]}",
        "llm_mode": llm_mode,
        "llm_model": llm_model,
        "questionnaire": questionnaire,
        "requirement": {
            "schema_version": "1.0",
            "room_type": plan.get("space_type"),
            "style": plan.get("style_id"),
            "prefer_color": plan.get("preferred_colors", []),
            "requirements": plan.get("required_furniture", []),
            "constraints": {
                "must_keep": [
                    rule.get("message")
                    for rule in plan.get("layout_rules", [])
                    if rule.get("message")
                ],
                "priority_order": [],
                "preferred_layout_pattern": "",
                "style_strictness": "high",
                "notes": [plan.get("personal_requirements")] if plan.get("personal_requirements") else [],
            },
        },
        "plan_json": plan,
        "floorplan": {
            "coordinate_unit": "cm",
            "image_path": floorplan_path,
            "width_cm": effective_width_cm,
            "depth_cm": effective_depth_cm,
            "room_height_cm": parsed_floorplan.get("room_height_cm", 270) if parsed_floorplan else 270,
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
            "wall_polys": parsed_floorplan.get("wall_polys", []) if parsed_floorplan else [],
            "plan_segments": parsed_floorplan.get("plan_segments", []) if parsed_floorplan else [],
            "door_segments": parsed_floorplan.get("door_segments", []) if parsed_floorplan else [],
            "window_segments": parsed_floorplan["window_segments"] if parsed_floorplan else [],
            "beam_segments": parsed_floorplan.get("beam_segments", []) if parsed_floorplan else [],
            "columns": parsed_floorplan.get("columns", []) if parsed_floorplan else [],
            "room_regions": parsed_floorplan.get("room_regions", []) if parsed_floorplan else [],
        },
        "style": {
            "style_id": style.get("style_id"),
            "style_name_zh": style.get("style_name_zh"),
            "scene_background": style.get("scene_background", {}),
            "palette_hex": style.get("palette_hex", []),
            "surface_profile": style.get("surface_profile", {}),
        },
        "style_card": style_card or {},
        "design_choices": {
            "style_card_id": questionnaire.get("style_card_id"),
            "wall_option": questionnaire.get("wall_option", "auto"),
            "floor_option": questionnaire.get("floor_option", "auto"),
            "single_room_mode": not bool(parsed_floorplan),
            "accurate_dxf_mode": bool(parsed_floorplan),
        },
        "render_context": {
            "appliance_requirements": appliance_requirements
            if isinstance(appliance_requirements, list)
            else [],
        },
        "surface_catalog": surface_catalog,
        "furniture_candidates": {
            "schema_version": "1.0",
            "room_type": plan.get("space_type"),
            "style": plan.get("style_id"),
            "candidates": selected_items,
            "layout_relations": [],
        },
        "selected_furniture": selected_items,
        "scene_objects": objects,
        "placement_resolution_report": placement_resolution_report,
        "placement": {
            "engine": "furniture_engine",
            "failed": [
                {
                    "furniture_id": obj["furniture_id"],
                    "type": obj.get("normalized_type"),
                    "name": obj.get("name_zh_raw"),
                    "reason": obj["placement_reason"],
                }
                for obj in objects
                if obj.get("placement_failed")
            ],
            "unavailable_types": unavailable_types,
        },
    }


def save_uploaded_floorplan(upload_dir: Path, upload) -> str | None:
    if not upload or not getattr(upload, "filename", ""):
        return None

    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(upload.filename).name}"
    target = upload_dir / safe_name

    with target.open("wb") as output:
        output.write(upload.file.read())

    return str(target)
