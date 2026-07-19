from __future__ import annotations

import json
import math
import os
import random
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..agent import design_layout_intent, run_recovery
from ..catalog.style_db import CLEARANCE_BY_TYPE, catalog_item_from_scene_object
from ..engine.clearance import check_placement_with_clearance
from ..engine.dxf_room import build_room_from_dxf
from ..engine.geometry import furniture_polygon
from ..engine.models import FurnitureCatalogItem, PlacedFurniture, Room, Wall
from ..engine.placement import place_furniture
from ..floorplan.room_analysis import derive_room_regions
from ..upgrade3d.dxf_parser import parse_dxf_bytes
from .style_cards import find_taiwan_style_card

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_CANDIDATES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "roompilot" / "server" / ".env",
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

    for index, required_type in enumerate(plan.get("required_furniture", [])):
        candidates = [
            item
            for item in furniture
            if item.get("has_model")
            and item.get("furniture_id") not in used_ids
            and item.get("normalized_type") == required_type
        ]

        if not candidates:
            # 型錄沒有這個泛型類型時退到同族系(例:sofa → fabric-sofa/leather-sofa)
            candidates = [
                item
                for item in furniture
                if item.get("has_model")
                and item.get("furniture_id") not in used_ids
                and _TYPE_FAMILY.get(item.get("normalized_type") or "") == required_type
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

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        furniture_id = raw.get("furniture_id")
        if not furniture_id or furniture_id in used_ids:
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

        if not merged["normalized_type"] or not merged["has_model"]:
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


# 家具「族系」:型錄的具體類型 → 擺位語意上的同一種東西
_TYPE_FAMILY = {
    "fabric-sofa": "sofa",
    "leather-sofa": "sofa",
    "sofa-bed": "sofa",
    "bed-frame": "bed",
    "pax-wardrobe": "wardrobe",
    "cabinets-cupboard": "wardrobe",
    "chests-of-drawer": "sideboard",
    "storage-solution-system": "wardrobe",
}


def _facing(rot_deg: float) -> tuple[float, float]:
    """候選旋轉角 → 家具正面朝向單位向量(rot 0=+z、90=+x、180=-z、270=-x)。"""
    rad = math.radians(rot_deg)
    return (math.sin(rad), math.cos(rad))


def _placement_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
    hint: dict[str, Any] | None = None,
    inner: tuple[float, float, float, float] | None = None,
    neighbors: dict[str, dict[str, float]] | None = None,
) -> list[tuple[float, float, float]]:
    """候選試放順序(合法性仍 100% 由引擎把關,這裡只影響「先試哪裡」)。

    inner:實際可擺區域的 (left, top, right, bottom),房間中心原點公分。
    DXF 房間的牆是厚實牆體、邊界又內縮 8cm,靠牆錨點必須以可擺區域邊緣計算;
    用 bbox±固定位移會整組卡進牆裡,全滅後退化成房中央網格(家具漂浮成因)。
    neighbors:已擺好的家具(依族系),用來把「椅子貼書桌、床頭櫃貼床、
    茶几對沙發、電視櫃對沙發」的成組候選排到最前。
    """
    if inner is not None:
        left, top, right, bottom = inner
    else:
        left = -room_width_cm / 2
        top = -room_depth_cm / 2
        right = room_width_cm / 2
        bottom = room_depth_cm / 2
    gap = 2.0                                    # 與可擺邊界的貼牆縫隙
    center_x = (left + right) / 2
    center_z = (top + bottom) / 2
    family = _TYPE_FAMILY.get(item_type or "", item_type)
    neighbors = neighbors or {}
    candidates: list[tuple[float, float, float]] = []

    # ── 成組候選:先貼著已擺好的夥伴家具 ──
    paired: list[tuple[float, float, float]] = []

    def _partner(fam: str) -> dict[str, float] | None:
        return neighbors.get(fam)

    if family == "office-chair":
        desk = _partner("desk")
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
        bed = _partner("bed")
        if bed:
            fx, fz = _facing(bed["rot"])
            px, pz = fz, -fx                     # 床的側向
            ax = bed["x"] - fx * (bed["depth"] / 2 - depth / 2)  # 對齊床頭端
            az = bed["z"] - fz * (bed["depth"] / 2 - depth / 2)
            side = bed["width"] / 2 + width / 2 + 4
            paired.append((ax + px * side, az + pz * side, bed["rot"]))
            paired.append((ax - px * side, az - pz * side, bed["rot"]))
    elif family == "coffee-table":
        sofa = _partner("sofa")
        if sofa:
            fx, fz = _facing(sofa["rot"])
            for knee in (45.0, 65.0):            # 沙發前緣與茶几間留膝蓋活動距
                dist = sofa["depth"] / 2 + depth / 2 + knee
                paired.append((sofa["x"] + fx * dist, sofa["z"] + fz * dist, sofa["rot"]))
    elif family == "tv-bench":
        sofa = _partner("sofa")
        if sofa:                                 # 電視櫃靠沙發正對面的牆
            fx, fz = _facing(sofa["rot"])
            if abs(fx) >= abs(fz):
                x = right - depth / 2 - gap if fx > 0 else left + depth / 2 + gap
                paired.append((x, sofa["z"], 270.0 if fx > 0 else 90.0))
            else:
                z = bottom - depth / 2 - gap if fz > 0 else top + depth / 2 + gap
                paired.append((sofa["x"], z, 180.0 if fz > 0 else 0.0))

    # Agent 3 提示:指定靠牆側時,把一組靠該牆的候選 prepend 到最前面優先試放。
    # 只影響「試放順序」,合法性仍由 check_placement_with_clearance 把關(鐵律不變)。
    anchor = (hint or {}).get("anchor")
    anchored: list[tuple[float, float, float]] = []
    inner_w = right - left
    inner_d = bottom - top
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

    # 靠牆家具的四面牆候選(背貼牆、面向房內;rot 90/270 時佔地寬深互換,
    # 貼牆距離用 depth 旋轉後的實際進深)
    def wall_slots(offsets=(0.0, -0.25, 0.25)) -> list[tuple[float, float, float]]:
        slots = []
        for off in offsets:
            slots.append((center_x + inner_w * off, top + depth / 2 + gap, 0))
            slots.append((center_x + inner_w * off, bottom - depth / 2 - gap, 180))
            slots.append((left + depth / 2 + gap, center_z + inner_d * off, 90))
            slots.append((right - depth / 2 - gap, center_z + inner_d * off, 270))
        return slots

    if family == "tv-bench":
        candidates.extend(wall_slots())
    elif family == "sofa":
        candidates.extend([(center_x, bottom - depth / 2 - gap, 180),
                           (center_x - inner_w * 0.18, bottom - depth / 2 - gap, 180),
                           (left + depth / 2 + gap, center_z, 90),
                           (right - depth / 2 - gap, center_z, 270)])
    elif family == "coffee-table":
        candidates.extend([(center_x, center_z + 12, 0), (center_x, center_z - 18, 0)])
    elif family == "armchair":
        candidates.extend([(right - width / 2 - 30, center_z + 35, -35), (left + width / 2 + 30, center_z + 35, 35)])
    elif family in {"bookcase", "sideboard", "wardrobe"}:
        candidates.extend(wall_slots())
    elif family == "bed":
        candidates.extend([(center_x, bottom - depth / 2 - gap, 180),
                           (center_x, top + depth / 2 + gap, 0),
                           (left + depth / 2 + gap, center_z, 90),
                           (right - depth / 2 - gap, center_z, 270)])
    elif family == "bedside-table":
        candidates.extend([(right - width / 2 - gap, bottom - depth / 2 - gap, 0), (left + width / 2 + gap, bottom - depth / 2 - gap, 0)])
    elif family == "desk":
        candidates.extend(wall_slots(offsets=(0.0, -0.3, 0.3)))
    elif family == "office-chair":
        candidates.extend([(center_x, top + depth + 88, 180), (left + width / 2 + 80, center_z, 90)])
    elif family == "dining-table":
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 36, 0),
                           (center_x + inner_w * 0.25, center_z, 0), (center_x - inner_w * 0.25, center_z, 0)])
    elif family == "dining-chair":
        candidates.extend([(right - width / 2 - 40, center_z, 90), (left + width / 2 + 40, center_z, -90), (center_x, center_z + 80, 180)])
    elif family == "wall-shelf":
        candidates.extend([(left + width / 2 + 15, top + depth / 2 + 12, 0), (right - width / 2 - 15, top + depth / 2 + 12, 0)])
    elif family in {"large-medium-rug", "runner-small-rug"}:
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 24, 0)])
    else:
        candidates.append((center_x, center_z, 0))

    grid_x = [left + inner_w * ratio for ratio in (0.25, 0.5, 0.75)]
    grid_z = [top + inner_d * ratio for ratio in (0.28, 0.5, 0.72)]
    for z in grid_z:
        for x in grid_x:
            candidates.append((x, z, 0))

    return paired + anchored + candidates


# 這些類型沿用舊行為,不參與碰撞(地毯在家具下方、壁架掛牆面)
_IGNORE_COLLISION_TYPES = {"large-medium-rug", "runner-small-rug", "wall-shelf"}

# 這些族系「背要貼牆」:沙發/床頭不靠牆、櫃背懸空都是設計錯誤;
# 背後是牆開口(門洞)時更不能擋 —— 用背後探針排除這類槽位
_WALL_BACKED_FAMILIES = {"sofa", "tv-bench", "bed", "wardrobe", "bookcase", "sideboard", "desk"}


def _backed_by_wall(boundary: Polygon | None, cand_x: float, cand_z: float,
                    rot: float, depth: float, half_w: float, half_d: float) -> bool:
    """家具背後(反面向 6cm)是否為牆體/區域外。背後還是自由空間 = 沒靠牆或擋在開口前。"""
    if boundary is None:
        return True
    fx, fz = _facing(rot)
    px = cand_x - fx * (depth / 2 + 6.0) + half_w
    pz = cand_z - fz * (depth / 2 + 6.0) + half_d
    return not boundary.contains(Point(px, pz))


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


def _grid_place_in_boundary(catalog, item_id, room, placed, boundary):
    """非矩形房間的最後防線:沿房間多邊形內部以 50cm 網格搜尋(由質心向外)。

    錨點與引擎網格都以 bbox 為座標基準,房間只佔 bbox 一角時全會撲空,
    這裡改以房間多邊形自己的範圍掃描。
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
            if _inside_boundary(cand, boundary) and check_placement_with_clearance(cand, room, placed) is None:
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


def room_from_payload(floorplan: dict[str, Any] | None) -> Room:
    """由 payload 的 floorplan 區塊重建引擎 Room(拖曳驗證/重排都是無狀態請求)。

    wall_segments 是房間中心原點、公尺(three.js 契約);引擎公分、角落原點
    → ×100 再平移 half。沒有牆段(手動模式)就退回矩形房。
    """
    floorplan = floorplan or {}
    width = max(float(floorplan.get("width_cm") or 420), 240)
    depth = max(float(floorplan.get("depth_cm") or 360), 240)

    raw_walls = floorplan.get("wall_segments") or []
    segment_factor = _segment_coordinate_factor(floorplan, raw_walls)
    walls: list[Wall] = []
    for seg in raw_walls:
        try:
            walls.append(
                Wall(
                    float(seg["start"]["x"]) * segment_factor + width / 2,
                    float(seg["start"]["z"]) * segment_factor + depth / 2,
                    float(seg["end"]["x"]) * segment_factor + width / 2,
                    float(seg["end"]["z"]) * segment_factor + depth / 2,
                    thickness=6.0,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    if len(walls) < 3:
        return _four_wall_room(width, depth)
    return Room(width=width, depth=depth, walls=walls)


def _segment_coordinate_factor(
    floorplan: dict[str, Any] | None,
    segments: list[dict[str, Any]],
) -> float:
    """歷史 client segments 可能是公尺或公分；統一回傳轉成公分的倍率。

    正式契約是公尺（倍率 100）。2026-07 的部分辨識結果曾把同一欄位輸出成
    公分；若座標跨度明顯大於公尺 bbox，就視為相容格式（倍率 1）。判斷集中在
    Python/engine 邊界，避免前端或各功能各自猜單位。
    """
    if not segments:
        return 100.0
    bbox = (floorplan or {}).get("bbox") or {}
    try:
        bbox_span_m = max(
            abs(float(bbox["maxx"]) - float(bbox["minx"])),
            abs(float(bbox["maxz"]) - float(bbox["minz"])),
        )
        coordinates = [
            abs(float(point[axis]))
            for segment in segments
            for point in (segment["start"], segment["end"])
            for axis in ("x", "z")
        ]
        segment_lengths = [
            math.hypot(
                float(segment["end"]["x"]) - float(segment["start"]["x"]),
                float(segment["end"]["z"]) - float(segment["start"]["z"]),
            )
            for segment in segments
        ]
    except (KeyError, TypeError, ValueError):
        return 100.0
    centimetre_shape = (
        max(coordinates, default=0.0) > bbox_span_m * 10
        or max(segment_lengths, default=0.0) > bbox_span_m * 2
    )
    return 1.0 if bbox_span_m > 0 and centimetre_shape else 100.0


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
    """payload 的 room_regions({exterior, holes},房間中心原點、公尺)→ 角落原點公分多邊形。"""
    polys: list[Polygon] = []
    for region in (floorplan or {}).get("room_regions") or []:
        try:
            def _shift(ring):
                return [(p[0] * 100 + room.width / 2, p[1] * 100 + room.depth / 2) for p in ring]

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


def _region_boundary_by_id(
    floorplan: dict[str, Any] | None,
    room: Room,
    room_id: str,
) -> Polygon | None:
    """指定 stable room_id 的可擺區域（引擎角落原點、公分、內縮 8 cm）。"""
    for region in (floorplan or {}).get("room_regions") or []:
        if str(region.get("room_id") or "") != str(room_id):
            continue
        try:
            def _shift(ring):
                return [
                    (float(point[0]) * 100 + room.width / 2, float(point[1]) * 100 + room.depth / 2)
                    for point in ring
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


def _door_clearance_obstacles(
    floorplan: dict[str, Any] | None,
    room: Room,
    door_segments: list[dict[str, Any]] | None,
) -> list[PlacedFurniture]:
    """把門線轉成不輸出的 90 cm 保守淨空障礙，供引擎防止家具擋門。"""
    segments = door_segments or []
    factor = _segment_coordinate_factor(floorplan, segments)
    obstacles: list[PlacedFurniture] = []
    for index, segment in enumerate(segments):
        try:
            x1 = float(segment["start"]["x"]) * factor + room.width / 2
            z1 = float(segment["start"]["z"]) * factor + room.depth / 2
            x2 = float(segment["end"]["x"]) * factor + room.width / 2
            z2 = float(segment["end"]["z"]) * factor + room.depth / 2
        except (KeyError, TypeError, ValueError):
            continue
        length = math.hypot(x2 - x1, z2 - z1)
        if length < 20:
            continue
        obstacles.append(
            PlacedFurniture(
                id=f"__door_clearance_{index}",
                catalog=FurnitureCatalogItem(
                    type="door-clearance",
                    name="門口淨空",
                    width=max(length, 75.0),
                    depth=90.0,
                    height=1.0,
                ),
                pos_x=(x1 + x2) / 2,
                pos_y=(z1 + z2) / 2,
                rotation=math.degrees(math.atan2(z2 - z1, x2 - x1)),
            )
        )
    return obstacles


def validate_single_placement(
    floorplan: dict[str, Any] | None,
    item: dict[str, Any],
    others: list[dict[str, Any]],
    *,
    place_boundary: Polygon | None = None,
    keep_door_clear: bool = False,
) -> dict[str, Any]:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    room = room_from_payload(floorplan)
    # 拖曳可放進「任何一間房」(聯集);沒有房間資訊才退回最大房間環
    boundary = place_boundary or _regions_boundary(floorplan, room) or _shrunk_boundary(room)
    half_w_cm = room.width / 2
    half_d_cm = room.depth / 2

    moving = _scene_object_to_placed(item, half_w_cm, half_d_cm)
    if not _inside_boundary(moving, boundary):
        return {"ok": False, "reason": "超出房間範圍(需完整放在某一間房內,不能跨牆)"}

    if item.get("normalized_type") in _IGNORE_COLLISION_TYPES:
        return {"ok": True, "reason": None}

    placed_others = [
        _scene_object_to_placed(o, half_w_cm, half_d_cm)
        for o in others
        if o.get("normalized_type") not in _IGNORE_COLLISION_TYPES and not o.get("placement_failed")
    ]
    if keep_door_clear:
        placed_others.extend(
            _door_clearance_obstacles(floorplan, room, (floorplan or {}).get("door_segments"))
        )
    reason = check_placement_with_clearance(moving, room, placed_others)
    return {"ok": reason is None, "reason": reason}


def generate_layout(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    room: Room | None = None,
    regions_boundary: Polygon | None = None,
    place_boundary: Polygon | None = None,
    hints: dict[str, dict[str, Any]] | None = None,
    window_segments: list[dict[str, Any]] | None = None,
    door_segments: list[dict[str, Any]] | None = None,
    floorplan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """家具座標一律由 furniture_engine 決定(碰撞 + 淨空,Shapely 驗證)。

    類型錨點(_placement_candidates)只提供「視覺上合理」的候選順序;
    合法性由引擎的 check_placement_with_clearance 把關,錨點全數不合法時
    退回引擎的網格搜尋(place_furniture),再不行就標記 placement_failed。

    hints(選填):Agent 3 的擺放語意提示,以 furniture_id 為鍵。只影響「試放
    順序」——priority 決定先擺誰、anchor 決定優先靠哪面牆;hints=None 時行為與
    整合前完全一致(/api/scene/layout 的呼叫不受影響)。座標仍 100% 由引擎算。

    座標契約(對前端不變):position_cm 為房間中心原點、公分;rotation_y_deg
    為 three.js 的 Y 軸旋轉(與引擎旋轉方向相反,進出引擎時取負號)。
    """
    if room is None:
        room = _four_wall_room(max(room_width_cm, 240), max(room_depth_cm, 240))

    # 擺放搜尋邊界(內縮 8cm 邊距):DXF 模式傳入最大自由空間;
    # 矩形房由牆環重建(等價於 bbox)。注意 DXF fallback 模式的 Room.walls
    # 是多個獨立環,不能拿去重建多邊形 —— 所以 DXF 一律走傳入的 place_boundary。
    boundary = place_boundary if place_boundary is not None else _shrunk_boundary(room)

    room_w_cm = room.width
    room_d_cm = room.depth
    half_w_cm = room_w_cm / 2
    half_d_cm = room_d_cm / 2

    # 實際可擺區域的內接範圍(房間中心原點、公分)—— 靠牆錨點以此計算。
    # DXF 房間的牆是厚實牆體+邊界內縮 8cm,用 bbox 邊緣當牆會整組卡進牆裡。
    inner: tuple[float, float, float, float] | None = None
    if boundary is not None:
        bx0, bz0, bx1, bz1 = boundary.bounds     # 角落原點
        inner = (bx0 - half_w_cm, bz0 - half_d_cm, bx1 - half_w_cm, bz1 - half_d_cm)

    # 擺放順序:鎖定位置(使用者拖曳過)最先,避免被後放的家具擠掉;
    # 其次 Agent priority 提示(升冪);沒有提示的照佔地面積大到小
    # (床/沙發/衣櫃先卡好牆位,小件再見縫插針,而不是反過來把大件擠到房中央)。
    # 輸出仍照原始 items 順序(以 results 對應),不動前端拿到的清單順序。
    def _order_key(i: int) -> tuple:
        locked_rank = 0 if items[i].get("position_locked") else 1
        hint = (
            (hints or {}).get(items[i].get("instance_id"))
            or (hints or {}).get(items[i].get("furniture_id"))
            or {}
        )
        priority = hint.get("priority")
        if isinstance(priority, int):
            return (locked_rank, 0, priority, 0.0, i)
        area = _size_cm(items[i], "width", 120) * _size_cm(items[i], "depth", 60)
        return (locked_rank, 1, 0, -area, i)

    order = sorted(range(len(items)), key=_order_key)

    placed: list[PlacedFurniture] = _door_clearance_obstacles(
        floorplan,
        room,
        door_segments,
    )
    neighbors: dict[str, dict[str, float]] = {}  # 族系 → 已擺好的代表家具(成組用)
    results: dict[int, dict[str, Any]] = {}

    # 窗段(公尺、房間中心原點)→ 角落原點公分 LineString,靠牆家具背貼窗時跳過該槽位
    window_lines: list[LineString] = []
    window_factor = _segment_coordinate_factor(floorplan, window_segments or [])
    for seg in window_segments or []:
        try:
            window_lines.append(LineString([
                (float(seg["start"]["x"]) * window_factor + half_w_cm,
                 float(seg["start"]["z"]) * window_factor + half_d_cm),
                (float(seg["end"]["x"]) * window_factor + half_w_cm,
                 float(seg["end"]["z"]) * window_factor + half_d_cm),
            ]))
        except (KeyError, TypeError, ValueError):
            continue

    for index in order:
        item = items[index]
        item_type = item.get("normalized_type")
        width = _size_cm(item, "width", 120)
        depth = _size_cm(item, "depth", 60)
        height = _size_cm(item, "height", 80)
        catalog = catalog_item_from_scene_object(
            item_type, item.get("name_zh_raw") or item.get("furniture_id"), width, depth, height
        )
        item_id = str(item.get("instance_id") or f"{item_type or 'item'}_{index + 1}")
        hint = (
            (hints or {}).get(item.get("instance_id"))
            or (hints or {}).get(item.get("furniture_id"))
        )

        x_cm: float | None = None
        z_cm: float | None = None
        rotation = 0.0
        failed_reason: str | None = None
        locked = False

        if item.get("position_locked") and item.get("position_cm"):
            # 使用者手動擺過:位置仍合法就保留,不重排。
            # 驗證用「所有房間聯集」—— 使用者可能把家具拖到別的房間,重排不能把它踢掉
            candidate = _scene_object_to_placed(item, half_w_cm, half_d_cm)
            ok = _inside_boundary(candidate, regions_boundary or boundary) and (
                item_type in _IGNORE_COLLISION_TYPES
                or check_placement_with_clearance(candidate, room, placed) is None
            )
            if ok:
                x_cm = float(item["position_cm"].get("x") or 0)
                z_cm = float(item["position_cm"].get("z") or 0)
                rotation = float(item.get("rotation_y_deg") or 0)
                locked = True
                if item_type not in _IGNORE_COLLISION_TYPES:
                    placed.append(candidate)
            elif item.get("mobility") == "fixed":
                # 既有固定家具不能被演算法偷偷移走；保留原位並明確回報衝突。
                x_cm = float(item["position_cm"].get("x") or 0)
                z_cm = float(item["position_cm"].get("z") or 0)
                rotation = float(item.get("rotation_y_deg") or 0)
                locked = True
                failed_reason = "固定家具位置與房間邊界、門口淨空或其他家具衝突"
                if item_type not in _IGNORE_COLLISION_TYPES:
                    placed.append(candidate)

        if locked:
            pass
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
            found = None
            for raw_x, raw_z, rot in _placement_candidates(
                item_type, width, depth, room_w_cm, room_d_cm,
                hint=hint, inner=inner, neighbors=neighbors,
            ):
                fp_w, fp_d = _rotated_footprint(width, depth, rot)
                fx, fz = _facing(rot)
                # 貼牆候選以可擺區域 bounds 計算,但區域有缺角(牆開口)時 bounds
                # 會頂到牆帶上 —— 沿家具面向逐步往房內推,推到剛好落在區域內
                # 為止(= 貼住實際室內邊緣),推太遠就放棄換下一個候選。
                for step in range(0, 13):
                    cand_x = _clamp_axis(raw_x + fx * 4 * step, -half_w_cm, half_w_cm, fp_w, margin=4)
                    cand_z = _clamp_axis(raw_z + fz * 4 * step, -half_d_cm, half_d_cm, fp_d, margin=4)
                    candidate = PlacedFurniture(
                        id=item_id,
                        catalog=catalog,
                        pos_x=cand_x + half_w_cm,
                        pos_y=cand_z + half_d_cm,
                        rotation=(-rot) % 360,
                    )
                    if not _inside_boundary(candidate, boundary):
                        continue                 # 還卡在牆帶/區域外 → 再往房內推
                    fam_ = _TYPE_FAMILY.get(item_type or "", item_type)
                    if fam_ in _WALL_BACKED_FAMILIES:
                        if not _backed_by_wall(
                            boundary, cand_x, cand_z, rot, depth, half_w_cm, half_d_cm
                        ):
                            break                # 背後是開口/自由空間 → 不貼牆不擋門,換候選
                        if window_lines:
                            bp = Point(cand_x - fx * (depth / 2 + 6.0) + half_w_cm,
                                       cand_z - fz * (depth / 2 + 6.0) + half_d_cm)
                            if any(line.distance(bp) <= 15.0 for line in window_lines):
                                break            # 背貼窗 → 擋採光,換下一面牆
                    if check_placement_with_clearance(candidate, room, placed) is None:
                        found = (cand_x, cand_z, rot, candidate)
                    break                        # 已在區域內:合法收下,不合法換候選
                if found:
                    break
            if found:
                x_cm, z_cm, rotation, candidate = found
                placed.append(candidate)
            else:
                result = place_furniture(room, catalog, item_id, placed)
                engine_item = result["placed"] if result["success"] else None
                if engine_item is not None and not _inside_boundary(engine_item, boundary):
                    engine_item = None
                if engine_item is None and boundary is not None:
                    engine_item = _grid_place_in_boundary(catalog, item_id, room, placed, boundary)
                if engine_item is not None:
                    placed.append(engine_item)
                    x_cm = engine_item.pos_x - half_w_cm
                    z_cm = engine_item.pos_y - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    failed_reason = result["reason"] or "找不到落在房間形狀內的合法位置"
                    x_cm, z_cm = 0.0, 0.0

        if failed_reason is None and item_type not in _IGNORE_COLLISION_TYPES:
            fam = _TYPE_FAMILY.get(item_type or "", item_type)
            if fam and fam not in neighbors:     # 同族取第一件當成組定位參考
                neighbors[fam] = {"x": float(x_cm or 0), "z": float(z_cm or 0),
                                  "rot": float(rotation), "width": width, "depth": depth}

        fp_w, fp_d = _rotated_footprint(width, depth, rotation)
        results[index] = {
            "instance_id": item_id,
            "furniture_id": item["furniture_id"],
            "name_zh_raw": item.get("name_zh_raw"),
            "normalized_type": item_type,
            "model_url": item.get("model_url"),
            "primary_style": item.get("primary_style"),
            "placement_room_id": item.get("placement_room_id"),
            "user_required": bool(item.get("user_required")),
            "selection_source": item.get("selection_source") or "rules",
            "mobility": item.get("mobility") or "movable",
            "size_cm": {"width": width, "depth": depth, "height": height},
            "footprint_cm": {"width": round(fp_w, 2), "depth": round(fp_d, 2)},
            "position_cm": {"x": round(x_cm, 2), "z": round(z_cm, 2)},
            "rotation_y_deg": rotation,
            "position_locked": locked,
            "placement_failed": bool(failed_reason),
            "placement_reason": failed_reason,
        }

    return [results[i] for i in range(len(items))]


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
    out["texts"] = [
        {**item, "x": item["x"], "z": -item["z"]}
        for item in parsed.get("texts") or []
        if "x" in item and "z" in item
    ]
    # client 形式的線段({start:{x,z}, end:{x,z}},公分)一併翻轉,
    # /api/floorplan/recognize 直接把 parser 輸出回給前端畫圖時才不會鏡像
    for key in ("wall_segments", "plan_segments", "door_segments", "window_segments"):
        out[key] = [
            {
                "start": {"x": s["start"]["x"], "z": -s["start"]["z"]},
                "end": {"x": s["end"]["x"], "z": -s["end"]["z"]},
            }
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


def _sanitize_override_segs(raw: Any) -> list[dict[str, float]] | None:
    """人工確認修正的窗/門段(辨識框架:牆 bbox 中心原點、公尺、z 已翻轉)。"""
    if not isinstance(raw, list):
        return None
    out = []
    for s in raw:
        try:
            out.append({"x1": float(s["x1"]), "z1": float(s["z1"]),
                        "x2": float(s["x2"]), "z2": float(s["z2"])})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def parse_floorplan_with_engine(
    dxf_text: str,
    scale_m: float | None = None,
    override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, Room | None]:
    """DXF 文字 → (payload 的 floorplan 區塊, 引擎 Room)。

    解析走 upgrade3d.dxf_parser(ezdxf,平面中心原點、公尺),
    再由 engine.dxf_room 取最大封閉房間轉成 Room(角落原點)。
    回傳的線段座標一律換算成「房間中心原點、公尺」,維持前端 viewer 契約。
    scale_m 是 F2a 手動拉比例的校正結果(全圖長邊的實際公尺數),覆寫自動猜測。
    """
    try:
        parsed = _flip_parsed_z(
            parse_dxf_bytes(dxf_text.encode("utf-8", errors="ignore"), "upload.dxf", scale_m=scale_m)
        )
        # 人工確認修正(F2/回到補資料迴圈):使用者在辨識確認畫面改過的窗/門段
        # 覆寫機器判讀。座標框架與 /api/floorplan/recognize 回傳一致(牆 bbox 中心、
        # 公尺、z 已翻轉)= 這裡 parsed 的框架,直接替換再走後續轉換。
        if override:
            for key in ("windows", "doors"):
                segs = _sanitize_override_segs(override.get(key))
                if segs is not None:
                    parsed[key] = segs
        build = build_room_from_dxf(parsed)
    except Exception:
        return None, None

    room = build.room
    ox, oz = build.offset
    # 房間中心(平面座標、公尺)—— room/offset 是公分,parsed 線段與 payload 線段是公尺
    room_center_x = (ox + room.width / 2) / 100
    room_center_z = (oz + room.depth / 2) / 100

    wall_segments = [
        {
            "start": {"x": round((w.x1 - room.width / 2) / 100, 3), "z": round((w.y1 - room.depth / 2) / 100, 3)},
            "end": {"x": round((w.x2 - room.width / 2) / 100, 3), "z": round((w.y2 - room.depth / 2) / 100, 3)},
        }
        for w in room.walls
    ]

    def _convert(segs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "start": {"x": round(s["x1"] - room_center_x, 3), "z": round(s["z1"] - room_center_z, 3)},
                "end": {"x": round(s["x2"] - room_center_x, 3), "z": round(s["z2"] - room_center_z, 3)},
            }
            for s in segs
        ]

    doors = _convert(parsed.get("doors", []))
    windows = _convert(parsed.get("windows", []))
    stats = parsed.get("stats", {})

    # 房間拓樸統一走 floorplan.room_analysis；此處只把 parser 中心原點轉成
    # 引擎選定房間的中心原點，避免辨識 API 與場景生成各算一套結果。
    room_regions = []
    try:
        def _ring_to_payload(coords) -> list:
            return [
                [round(point[0] - room_center_x, 3), round(point[1] - room_center_z, 3)]
                for point in coords
            ]

        for region in derive_room_regions(parsed):
            room_regions.append(
                {
                    **region,
                    "exterior": _ring_to_payload(region.get("exterior") or []),
                    "holes": [
                        _ring_to_payload(ring)
                        for ring in region.get("holes") or []
                    ],
                    "centroid": {
                        "x": round(
                            float(region.get("centroid", {}).get("x", 0))
                            - room_center_x,
                            3,
                        ),
                        "z": round(
                            float(region.get("centroid", {}).get("z", 0))
                            - room_center_z,
                            3,
                        ),
                    },
                }
            )
    except Exception:
        room_regions = []

    floorplan = {
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
    dxf_text = questionnaire.get("floorplan_dxf_text")
    if dxf_text:
        # F2a 手動拉比例:前端兩點標定算出的全圖跨距(公尺),沒有就交給解析器自動猜
        raw_scale = questionnaire.get("floorplan_scale_m")
        try:
            scale_m = float(raw_scale) if raw_scale else None
        except (TypeError, ValueError):
            scale_m = None
        _override = questionnaire.get("floorplan_override")
        parsed_floorplan, engine_room = parse_floorplan_with_engine(
            dxf_text, scale_m=scale_m,
            override=_override if isinstance(_override, dict) else None,
        )

    effective_width_cm = parsed_floorplan["width_cm"] if parsed_floorplan else room_width_cm
    effective_depth_cm = parsed_floorplan["depth_cm"] if parsed_floorplan else room_depth_cm

    llm_mode, plan, llm_model = build_scene_plan(questionnaire, site_payload["styles"])
    selected_items, unavailable_types = choose_furniture_items(
        plan,
        site_payload["furniture"],
        questionnaire.get("furniture_random_seed"),
        effective_width_cm,
        effective_depth_cm,
        plan.get("preferred_colors", []) + questionnaire.get("custom_colors", []),
    )
    # 家具庫精選:使用者在家具庫明確挑過的家具優先進清單,同型別的自動選件讓位
    exact_selected_items = selected_furniture_items_from_questionnaire(
        questionnaire,
        site_payload["furniture"],
    )
    if exact_selected_items:
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

    # Agent 3:擺放語意提示(靠牆側/朝向/成組/優先序,不出座標)。
    # 無 LLM 或呼叫失敗 → 回 {},引擎沿用預設候選順序,行為與整合前一致。
    hints = design_layout_intent(
        plan,
        selected_items,
        {"width_cm": effective_width_cm, "depth_cm": effective_depth_cm},
        {
            "windows": parsed_floorplan.get("window_segments", []) if parsed_floorplan else [],
            "doors": parsed_floorplan.get("door_segments", []) if parsed_floorplan else [],
        },
        complete=_openrouter_request,
    )
    _regions = _regions_boundary(parsed_floorplan, engine_room) if engine_room else None
    _place_bound = _largest_region_boundary(parsed_floorplan, engine_room) if engine_room else None
    _windows = parsed_floorplan.get("window_segments", []) if parsed_floorplan else []
    objects = generate_layout(
        effective_width_cm,
        effective_depth_cm,
        selected_items,
        room=engine_room,
        regions_boundary=_regions,
        place_boundary=_place_bound,
        hints=hints,
        window_segments=_windows if questionnaire.get("keep_window_clear") else None,
        door_segments=(parsed_floorplan or {}).get("door_segments")
        if questionnaire.get("keep_door_clear") else None,
        floorplan=parsed_floorplan,
    )

    # Agent 4:引擎放不下的家具 → 換更小同型號 / 移除 / 升級,重擺至收斂。
    # 座標仍 100% 由引擎(place_fn)算;無 LLM 時走確定性換小/移除。
    def _place(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return generate_layout(
            effective_width_cm,
            effective_depth_cm,
            items,
            room=engine_room,
            regions_boundary=_regions,
            place_boundary=_place_bound,
            hints=hints,
            window_segments=_windows if questionnaire.get("keep_window_clear") else None,
            door_segments=(parsed_floorplan or {}).get("door_segments")
            if questionnaire.get("keep_door_clear") else None,
            floorplan=parsed_floorplan,
        )

    objects, selected_items, recovery = run_recovery(
        objects,
        selected_items,
        plan,
        site_payload["furniture"],
        place_fn=_place,
        complete=_openrouter_request,
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
            "recovery": recovery,
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
