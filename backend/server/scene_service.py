from __future__ import annotations

import json
import math
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from shapely.geometry import LineString, Point, Polygon, box as shapely_box
from shapely.ops import unary_union

from ..agent.place import resolve_placements
from ..catalog.placement_surface import FLOOR_COVERING, TABLETOP, WALL, placement_surface_for
from ..catalog.style_db import allowed_host_types, catalog_item_from_scene_object
from ..engine.clearance import check_placement_with_clearance
from ..engine.dxf_room import build_room_from_dxf
from ..engine.geometry import furniture_polygon, rests_within_host
from ..engine.models import PlacedFurniture, Room, Wall
from ..engine.placement import (
    place_adjacent_to_furniture,
    place_furniture,
    place_overlay_on_furniture,
)
from ..upgrade3d.dxf_parser import parse_dxf_bytes
from .catalog_vocabulary import catalog_types_for_family
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
        "selection_enabled": selection_enabled(),
    }


def selection_enabled() -> bool:
    """選件 agent 是否可呼叫 LLM。

    與第 1 步問卷規劃相反，選件預設隨 ``OPENROUTER_API_KEY`` 啟用：它的
    輸出一律經 Yen 的白名單驗證，失敗會退回本地規則，沒有讓 LLM 決定
    座標的風險。要完全離線時設 ``OPENROUTER_SELECTION_ENABLED=0``。
    """
    load_local_env()
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        return False
    if not get_openrouter_models():
        return False
    return os.getenv("OPENROUTER_SELECTION_ENABLED", "1") != "0"


def selection_complete_fn() -> Callable[[list[dict[str, str]]], tuple[str, dict[str, Any]] | None] | None:
    """回傳選件用的 OpenRouter 呼叫器；停用時回 None 讓呼叫端走本地規則。

    依 ``OPENROUTER_MODELS`` 順序重試，任一模型回出可解析的 JSON 物件就
    採用；全部失敗回 None，由 ``request_selections`` 轉成
    ``SelectionUnavailableError``。
    """
    if not selection_enabled():
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    models = get_openrouter_models()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "RoomPilot furniture selection"),
    }

    def complete(messages: list[dict[str, str]]) -> tuple[str, dict[str, Any]] | None:
        for model in models:
            body = _post_openrouter_chat(
                {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                headers,
            )
            parsed = _load_json_response(body) if body else None
            if isinstance(parsed, dict):
                return model, parsed
        return None

    return complete


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
    # 2026-07 盤點第 5 項修復：前端「空間用途」下拉開放後，使用者會真的選到
    # 廚房／浴廁／儲藏／陽台／走道——這些型別先前不在表內，會一律退成客廳
    # 家具（浴室被塞沙發）。circulation 刻意零家具（動線空間不自動配置）。
    # 詞彙一致性由 tests/test_room_type_vocabulary.py 鎖住。
    "kitchen": ["appliance-cabinet"],
    "bathroom": ["bathroom-vanity", "mirror-cabinet"],
    "storage": ["storage-cabinet"],
    "balcony": ["flower-pots-planter"],
    "circulation": [],
}

FURNITURE_ALIASES = {
    "沙發": "sofa",
    "茶几": "coffee-table",
    "電視櫃": "tv-bench",
    "單椅": "armchair",
    "書櫃": "bookcase",
    "地毯": "large-medium-rug",
    "床": "bed",
    # 型錄沒有 bed-frame／cabinets-cupboard 這兩個分類，別名指過去等於整族落空。
    # 直接指向型錄實際用語，`FAMILY_OF` 才不必反向替問卷做別名正規化。
    "床架": "bed",
    "床頭櫃": "bedside-table",
    "書桌": "desk",
    "辦公椅": "office-chair",
    "餐桌": "dining-table",
    "餐椅": "dining-chair",
    "邊櫃": "sideboard",
    "壁架": "wall-shelf",
    "收納櫃": "cabinet-cupboard",
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

    raw_layout_rules = raw_plan.get("layout_rules", [])
    if not isinstance(raw_layout_rules, list):
        raw_layout_rules = []
    # LLM 常把規則回成字串陣列；下游 must_keep 直接呼叫 rule.get("message")，
    # 在邊界一律轉成 dict，無法取出訊息的項目直接丟棄。
    layout_rules = [
        item if isinstance(item, dict) else {"rule": "llm_rule", "message": item.strip()}
        for item in raw_layout_rules
        if isinstance(item, dict) or (isinstance(item, str) and item.strip())
    ]

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

    def type_candidates(catalog_type: str, requested_type: str) -> list[dict[str, Any]]:
        return [
            item
            for item in furniture
            if item.get("has_model")
            and item.get("furniture_id") not in used_ids
            and item.get("normalized_type") == catalog_type
            # 語意檢查一律用「使用者要的族系」判定：走後備時也不得放寬，
            # 否則 bed-frame 退到 bed 會連衣櫃模型都收下。
            and catalog_item_matches_type_semantics(item, requested_type)
        ]

    for index, required_type in enumerate(plan.get("required_furniture", [])):
        # 先精準比對族系本身；查無候選才用型錄實際存在的同義分類（例如型錄只有
        # cabinet-cupboard，沒有 appliance-cabinet／bathroom-vanity／
        # storage-cabinet）。少了這一步，那些族系會整族落空，2D 有家具、3D 卻
        # 永遠缺席——QA 2026-08-04 第 6 步的三個櫃子就是這樣消失的。
        candidates: list[dict[str, Any]] = []
        for catalog_type in catalog_types_for_family(required_type):
            candidates = type_candidates(catalog_type, required_type)
            if candidates:
                break

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
    # `furniture_id` 是 2D/3D 可編輯實例的身分鍵,`catalog_furniture_id` 指回
    # 型錄來源(契約:BEN_第5第6步整合規格_中文.md「3D 預覽資料要求」)。
    # 舊 payload 沒有拆分時兩者同值,fallback 保住既有存檔。
    used_instance_ids: set[str] = set()

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
        instance_id = str(raw.get("furniture_id") or "")
        catalog_furniture_id = str(
            raw.get("catalog_furniture_id")
            or raw.get("catalogFurnitureId")
            or instance_id
        )
        if not instance_id or instance_id in used_instance_ids:
            continue

        raw_type = str(raw.get("normalized_type") or raw.get("type") or "").casefold()
        raw_model_url = str(raw.get("model_url") or raw.get("glb_url") or "").casefold()
        if raw_type in appliance_types or "/models/ikea/appliance/" in raw_model_url:
            # Appliances remain questionnaire/render context, never 2D/3D objects.
            continue

        catalog_item = catalog_by_id.get(catalog_furniture_id, {})
        merged = {**catalog_item, **raw}
        merged["furniture_id"] = instance_id
        merged["catalog_furniture_id"] = catalog_furniture_id
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
            or catalog_furniture_id
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
        used_instance_ids.add(instance_id)

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


def _placement_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
    bounds_cm: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float, float]]:
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
        candidates.extend([(center_x, bottom - depth / 2 - wall_gap, 180), (center_x - candidate_width_cm * 0.18, bottom - depth / 2 - wall_gap, 180)])
    elif item_type == "coffee-table":
        candidates.extend([(center_x, center_z + 12, 0), (center_x, center_z - 18, 0)])
    elif item_type == "armchair":
        candidates.extend([(right - width / 2 - 30, center_z + 35, -35), (left + width / 2 + 30, center_z + 35, 35)])
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
        candidates.extend([(right - width / 2 - 22, bottom - depth / 2 - 34, 0), (left + width / 2 + 22, bottom - depth / 2 - 34, 0)])
    elif item_type == "desk":
        candidates.extend([(center_x, top + depth / 2 + wall_gap, 0), (left + depth / 2 + wall_gap, center_z, 90)])
    elif item_type == "office-chair":
        candidates.extend([(center_x, top + depth + 88, 180), (left + width / 2 + 80, center_z, 90)])
    elif item_type == "dining-table":
        candidates.extend([(center_x, center_z, 0), (center_x, center_z + 36, 0)])
    elif item_type == "dining-chair":
        candidates.extend([(right - width / 2 - 40, center_z, 90), (left + width / 2 + 40, center_z, -90), (center_x, center_z + 80, 180)])
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

    return candidates


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
    for rotation, side in ((0.0, "top"), (0.0, "bottom"), (90.0, "left"), (90.0, "right")):
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


# 擺放面分類的單一事實在型錄層(backend/catalog/placement_surface.py),第 6 步
# 只把它翻成擺放行為,不再自己維護第二份型別名單。
#
# 以前這裡硬編碼 2 種地毯與 1 種壁掛,型錄實際宣告 7 種與 4 種——rug、
# handmade-rug、round-rug、outdoor-rug、door-mat、mirror、large-mirror、
# mirror-cabinet 全部被當成落地家具去算碰撞與淨空,放不下就卡進待處理清單。
def _is_overlay_item(item_type: str | None, name: str | None = None) -> bool:
    """地面覆蓋物:可與目標家具重疊,但仍要通過牆與房間邊界驗證。"""
    return placement_surface_for(item_type, name) == FLOOR_COVERING


def _is_collision_exempt_item(item_type: str | None, name: str | None = None) -> bool:
    """壁掛品項:佔的是牆面不是地板,不進碰撞與淨空。"""
    return placement_surface_for(item_type, name) == WALL


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
    forbidden_zones: list[PlacementZone] | None = None,
):
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
            if (
                _inside_boundary(cand, boundary)
                and not _placement_intersects_zones(cand, forbidden_zones)
                and check_placement_with_clearance(cand, room, placed) is None
            ):
                return cand
    return None


def _place_wall_mounted(
    catalog,
    item_id: str,
    room: Room,
    placed: list[PlacedFurniture],
    forbidden_zones: list[PlacementZone] | None = None,
) -> PlacedFurniture | None:
    """壁掛品項沿牆面找位置。

    引擎已經豁免壁掛的出界與穿牆(掛在牆上是它的正常狀態),這裡只需要
    避開垂直帶會打架的家具。固定角落座標會讓每一件壁掛都疊在同一點。
    """
    width, depth = catalog.width, catalog.depth
    step = 40.0
    margin_x, margin_y = width / 2 + 15, depth / 2 + 12
    candidates: list[tuple[float, float, float]] = []

    x = margin_x
    while x <= max(margin_x, room.width - margin_x):
        candidates.append((x, margin_y, 0.0))
        candidates.append((x, room.depth - margin_y, 180.0))
        x += step
    y = margin_y
    while y <= max(margin_y, room.depth - margin_y):
        candidates.append((margin_y, y, 90.0))
        candidates.append((room.width - margin_y, y, 270.0))
        y += step

    for pos_x, pos_y, rotation in candidates:
        candidate = PlacedFurniture(
            id=item_id, catalog=catalog, pos_x=pos_x, pos_y=pos_y, rotation=rotation
        )
        if _placement_intersects_zones(candidate, forbidden_zones):
            continue
        if check_placement_with_clearance(candidate, room, placed) is None:
            return candidate
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


_WINDOW_CLEARANCE_EXEMPT_TYPES = frozenset({"curtain"})

# 一般窗前的判斷帶寬度(公分)。帶內只擋「高過窗台」的家具,矮櫃與臥榻可以進;
# 問卷的 window_zone 偏好可以把這條帶整個關掉。
WINDOW_CLEARANCE_DEPTH_CM = 70.0
# 落地窗前的硬淨空(公分):採光與進出動線,任何高度的家具都不能進,不受偏好影響。
FLOOR_WINDOW_CLEARANCE_CM = 50.0
# 窗台離地高的後備值(公分),對齊編輯器 scene_window_types.js 的一般窗預設。
STANDARD_WINDOW_SILL_FALLBACK_CM = 90.0
# 窗台低於此高度就當落地窗處理(編輯器落地窗預設 sill_height_cm = 0)。
FLOOR_WINDOW_SILL_MAX_CM = 30.0
# 門弧離散化段數:12 段足以讓 90 度扇形的弦誤差小於 1 公分。
_DOOR_ARC_SEGMENTS = 12


@dataclass(frozen=True)
class PlacementZone:
    """擺放禁區。

    ``max_height_cm`` 是「這塊區域可以容忍的最大家具高度」:
    ``None`` 代表任何高度都不准進(落地窗、門弧);有值代表只擋高過它的家具
    ——一般窗前的矮櫃、臥榻因此仍然合法,這正是窗台高度規則的表達方式。
    """

    polygon: Polygon
    kind: str
    reason: str
    max_height_cm: float | None = None
    exempt_types: frozenset[str] = field(default_factory=frozenset)


def _opening_line(
    opening: dict[str, Any],
    room: Room,
    scale: float,
    *,
    start_key: str = "start",
    end_key: str = "end",
) -> LineString | None:
    """把 payload 的中心原點線段轉成引擎的角落原點線段。"""
    try:
        start = opening[start_key]
        end = opening[end_key]
    except (KeyError, TypeError):
        return None
    try:
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
    except (KeyError, TypeError, ValueError):
        return None
    return line if line.length >= 4 else None


def _is_floor_to_ceiling(opening: dict[str, Any]) -> bool:
    """落地窗判定。舊資料寫過 ``floor-to-ceiling``,兩種寫法都要認得。"""
    raw = opening.get("window_type")
    return str(raw or "").strip().lower().replace("-", "_") == "floor_to_ceiling"


def _window_sill_height_cm(opening: dict[str, Any]) -> float:
    """窗台離地高。落地窗是 0,一般窗沒填就用編輯器同一個預設值。"""
    if _is_floor_to_ceiling(opening):
        return 0.0
    raw = opening.get("sill_height_cm")
    if raw is None:
        return STANDARD_WINDOW_SILL_FALLBACK_CM
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return STANDARD_WINDOW_SILL_FALLBACK_CM


def window_clearance_zones(
    floorplan: dict[str, Any] | None,
    room: Room,
    depth_cm: float = WINDOW_CLEARANCE_DEPTH_CM,
) -> list[PlacementZone]:
    """窗前禁區:落地窗是硬淨空,一般窗只擋高過窗台的家具。

    ``depth_cm`` 只影響一般窗的判斷帶寬度(問卷 window_zone 偏好可調);
    落地窗固定 ``FLOOR_WINDOW_CLEARANCE_CM``,那是通行與採光的工程值,
    不是使用者偏好可以放寬的東西。
    """
    scale = _floorplan_coordinate_scale_cm(floorplan)
    zones: list[PlacementZone] = []
    for opening in (floorplan or {}).get("window_segments") or []:
        if not isinstance(opening, dict):
            continue
        line = _opening_line(opening, room, scale)
        if line is None:
            continue
        sill_cm = _window_sill_height_cm(opening)
        if sill_cm <= FLOOR_WINDOW_SILL_MAX_CM:
            zones.append(
                PlacementZone(
                    polygon=line.buffer(FLOOR_WINDOW_CLEARANCE_CM, cap_style=2),
                    kind="floor_window",
                    reason=(
                        f"落地窗前需保留 {FLOOR_WINDOW_CLEARANCE_CM:.0f} 公分淨空,不能擺放家具。"
                    ),
                    max_height_cm=None,
                    exempt_types=_WINDOW_CLEARANCE_EXEMPT_TYPES,
                )
            )
        elif depth_cm > 0:
            zones.append(
                PlacementZone(
                    polygon=line.buffer(depth_cm, cap_style=2),
                    kind="window",
                    reason=(
                        f"窗前家具不可高過窗台({sill_cm:.0f} 公分),會擋住窗戶。"
                    ),
                    max_height_cm=sill_cm,
                    exempt_types=_WINDOW_CLEARANCE_EXEMPT_TYPES,
                )
            )
    return zones


def _door_swing_polygon(
    hinge: tuple[float, float],
    open_end: tuple[float, float],
    closed_end: tuple[float, float],
) -> Polygon | None:
    """門片從開到關掃過的扇形(圓心 = 鉸鏈,半徑 = 門片長)。

    走兩個端點之間的短弧——門扇是 90 度上下,短弧才是真正掃過的那一邊。
    """
    radius = math.dist(hinge, open_end)
    if radius < 1:
        return None
    start_angle = math.atan2(open_end[1] - hinge[1], open_end[0] - hinge[0])
    end_angle = math.atan2(closed_end[1] - hinge[1], closed_end[0] - hinge[0])
    sweep = (end_angle - start_angle + math.pi) % (2 * math.pi) - math.pi
    if abs(sweep) < math.radians(5):
        return None
    points = [hinge]
    for step in range(_DOOR_ARC_SEGMENTS + 1):
        angle = start_angle + sweep * step / _DOOR_ARC_SEGMENTS
        points.append((hinge[0] + radius * math.cos(angle), hinge[1] + radius * math.sin(angle)))
    polygon = Polygon(points)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon if not polygon.is_empty else None


def door_swing_zones(
    floorplan: dict[str, Any] | None,
    room: Room,
) -> list[PlacementZone]:
    """門扇開闔弧掃過的地面禁區——第 4 步畫的那個扇形,任何家具都不能進。

    payload 的 ``start`` 是鉸鏈、``end`` 是打開後的門片端點、``swing_end`` 是
    關門後的門片端點(``floorplan_from_editor_payload`` 建立)。沒有 ``swing_end``
    的舊資料與 DXF 匯入門,退回和前端同一條後備規則:門片繞鉸鏈轉 90 度。
    """
    scale = _floorplan_coordinate_scale_cm(floorplan)
    zones: list[PlacementZone] = []
    for door in (floorplan or {}).get("door_segments") or []:
        if not isinstance(door, dict):
            continue
        line = _opening_line(door, room, scale)
        if line is None:
            continue
        hinge, open_end = line.coords[0], line.coords[-1]
        swing_line = _opening_line(
            door, room, scale, start_key="start", end_key="swing_end"
        )
        if swing_line is not None:
            closed_end = swing_line.coords[-1]
        else:
            # 前端 scene_v2.js 沒有 swing_end 時畫的也是這個垂直後備,兩邊要一致。
            closed_end = (
                hinge[0] + (open_end[1] - hinge[1]),
                hinge[1] - (open_end[0] - hinge[0]),
            )
        polygon = _door_swing_polygon(tuple(hinge), tuple(open_end), tuple(closed_end))
        if polygon is None:
            continue
        zones.append(
            PlacementZone(
                polygon=polygon,
                kind="door_swing",
                reason="門的開闔範圍必須淨空,不能擺放家具。",
                max_height_cm=None,
            )
        )
    return zones


def placement_forbidden_zones(
    floorplan: dict[str, Any] | None,
    room: Room,
    window_clearance_cm: float = WINDOW_CLEARANCE_DEPTH_CM,
) -> list[PlacementZone]:
    """自動配置與拖曳驗證共用的禁區清單,兩邊必須看到同一份規則。"""
    return door_swing_zones(floorplan, room) + window_clearance_zones(
        floorplan, room, window_clearance_cm
    )


def _blocking_zone(
    candidate: PlacedFurniture,
    zones: list[PlacementZone] | None,
) -> PlacementZone | None:
    """回傳第一個擋住這件家具的禁區,沒有就回 None。

    型別與高度都從 ``candidate.catalog`` 取,呼叫端不必再自己判斷豁免——
    以前豁免寫在呼叫端,窗簾會連門弧一起被放行。
    """
    if not zones:
        return None
    item_type = candidate.catalog.type
    height_cm = float(candidate.catalog.height or 0)
    footprint = furniture_polygon(candidate)
    for zone in zones:
        if item_type in zone.exempt_types:
            continue
        if zone.max_height_cm is not None and height_cm <= zone.max_height_cm:
            continue
        if footprint.intersects(zone.polygon):
            return zone
    return None


def _placement_intersects_zones(
    candidate: PlacedFurniture,
    zones: list[PlacementZone] | None,
) -> bool:
    return _blocking_zone(candidate, zones) is not None


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
    """Orient automatically placed seating and work furniture toward useful targets."""
    target_types = {
        "office-chair": ("desk",),
        "dining-chair": ("dining-table",),
        "armchair": ("coffee-table", "sofa", "sofa-bed"),
        "sofa": ("tv-bench", "coffee-table"),
        "sofa-bed": ("tv-bench", "coffee-table"),
        "desk": ("office-chair",),
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
        item["rotation_y_deg"] = _scene_rotation_toward(source, target["position_cm"])
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


EDITOR_WALL_THICKNESS_CM = 12.0
WALL_POLY_OPENING_PIERCE_CM = 1.0


def _wall_polys_from_editor_segments(
    walls: list[dict[str, Any]],
    doors: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """牆中線 buffer 成連續實心牆團，門窗洞直接從牆身開槽。

    dxf_parser 對 DXF 用同一套 shapely 作法（方形端帽讓相交牆在轉角重疊、
    斜接讓外角保持直角）；第 4 步確認走的 editor 路徑過去完全沒有產
    ``wall_polys``，第 6 步 3D 拿不到就退回逐段板片（2026-08-03 Ben 實走：
    19 面牆不成面、門片站在空地上）。

    門洞用 ``closed_segment``（鉸鏈→swing_end 的關門線，不是打開的門片），
    窗洞用線段本身；兩者都已先貼回牆線。開槽是全高的，牆在開口上下的部分
    由前端 wall-mass 路徑以 door-wall-header／window-wall-sill 補回。
    """

    def _pt(value: Any) -> tuple[float, float] | None:
        if not isinstance(value, dict):
            return None
        try:
            return float(value.get("x", 0.0)), float(value.get("z", 0.0))
        except (TypeError, ValueError):
            return None

    solids = []
    wall_lines: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    max_half = 0.0
    for wall in walls:
        start, end = _pt(wall.get("start")), _pt(wall.get("end"))
        if start is None or end is None:
            continue
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-6:
            continue
        try:
            thickness = float(wall.get("thickness_cm") or EDITOR_WALL_THICKNESS_CM)
        except (TypeError, ValueError):
            thickness = EDITOR_WALL_THICKNESS_CM
        half = min(max(thickness, 4.0), 60.0) / 2.0
        max_half = max(max_half, half)
        wall_lines.append((start, end, half))
        solids.append(
            LineString([start, end]).buffer(
                half, cap_style=3, join_style=2, mitre_limit=5.0
            )
        )
    if not solids:
        return []
    mass = unary_union(solids)
    if not mass.is_valid:
        mass = mass.buffer(0)

    def _host_half(start: tuple[float, float], end: tuple[float, float]) -> float:
        # 開槽半寬取宿主牆厚。門位在兩段牆之間的缺口，垂直距離要量到牆的
        # 延伸線，量線段端點會得到假距離（同 _align_doors_to_wall_lines）。
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        dx, dz = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dz)
        ux, uz = dx / length, dz / length
        best: tuple[float, float] | None = None
        for wall_start, wall_end, half in wall_lines:
            wx, wz = wall_end[0] - wall_start[0], wall_end[1] - wall_start[1]
            wall_length = math.hypot(wx, wz)
            wx, wz = wx / wall_length, wz / wall_length
            if abs(ux * wx + uz * wz) < 0.96:
                continue
            offset_x, offset_z = mid[0] - wall_start[0], mid[1] - wall_start[1]
            along = offset_x * wx + offset_z * wz
            gap = math.hypot(offset_x - along * wx, offset_z - along * wz)
            if best is None or gap < best[0]:
                best = (gap, half)
        return best[1] if best is not None else max_half

    cuts = []
    for opening in [*doors, *windows]:
        if not isinstance(opening, dict):
            continue
        closed = opening.get("closed_segment")
        hole = closed if isinstance(closed, dict) else opening
        start, end = _pt(hole.get("start")), _pt(hole.get("end"))
        if start is None or end is None:
            continue
        if math.hypot(end[0] - start[0], end[1] - start[1]) <= 1e-6:
            continue
        # 平端帽：槽只存在於開口跨距內，不吃掉兩旁的牆。
        cuts.append(
            LineString([start, end]).buffer(
                _host_half(start, end) + WALL_POLY_OPENING_PIERCE_CM,
                cap_style=2,
                join_style=2,
            )
        )
    if cuts:
        mass = mass.difference(unary_union(cuts))
        if not mass.is_valid:
            mass = mass.buffer(0)

    geoms = (
        list(mass.geoms)
        if mass.geom_type == "MultiPolygon"
        else ([] if mass.is_empty else [mass])
    )

    def _ring(coords) -> list[list[float]]:
        return [[round(x, 1), round(z, 1)] for x, z in coords]

    return [
        {
            "exterior": _ring(geom.exterior.coords),
            "holes": [_ring(ring.coords) for ring in geom.interiors],
        }
        for geom in geoms
        if not geom.is_empty and geom.area >= 5.0
    ]


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
            converted["closed_segment"] = {
                "start": dict(converted["start"]),
                "end": dict(converted["swing_end"]),
                "source": "swing_arc",
            }
        return converted

    wall_segments = [segment(item) for item in structures.get("walls") or []]
    door_segments = _align_doors_to_wall_lines(
        [segment(item) for item in structures.get("doors") or []], wall_segments
    )
    # 窗沒有開合語意，線段就是開口本身，貼回宿主牆是安全的。
    window_segments = _snap_openings_to_walls(
        [segment(item) for item in structures.get("windows") or []], wall_segments
    )
    beam_segments = [segment(item) for item in structures.get("beams") or []]
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
    wall_polys = _wall_polys_from_editor_segments(
        wall_segments, door_segments, window_segments
    )
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
        "geometry_rev": FLOORPLAN_GEOMETRY_REV,
        "wall_count": len(wall_segments),
        "door_count": len(door_segments),
        "window_count": len(window_segments),
        "raw_segment_count": len(wall_segments),
        "layers": [],
        "wall_layers": [],
        "door_layers": [],
        "window_layers": [],
        "wall_segments": wall_segments,
        "wall_polys": wall_polys,
        # 這批 wall_polys 已把門窗洞開槽；前端據此決定帶著開口也走連續
        # 牆體（DXF 產的 wall_polys 沒開槽，仍是無開口才走 mass）。
        "wall_polys_openings_cut": bool(wall_polys),
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


DEFAULT_WALK_MARGIN_CM = 8.0
WIDE_WALK_MARGIN_CM = 20.0
# WINDOW_CLEARANCE_DEPTH_CM 移到禁區常數區(與落地窗、窗台高度的值放在一起)。


SNAP_OPENING_TO_WALL_MAX_CM = 150.0

# 幾何產生規則的版本。修正會改變既有專案輸出幾何時遞增；前端復原時發現
# 存檔的 floorplan 版本較舊，就以第 4 步確認資料重新產生（rev 2：窗不再
# 被 clamp 拖離兩段牆之間的缺口）。
FLOORPLAN_GEOMETRY_REV = 2
ALIGN_DOOR_TO_WALL_LINE_MAX_CM = 60.0


def _align_doors_to_wall_lines(
    doors: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    max_gap_cm: float = ALIGN_DOOR_TO_WALL_LINE_MAX_CM,
) -> list[dict[str, Any]]:
    """把門對齊到它所屬牆線上，用的是關閉門洞而不是打開的門片。

    門在平面圖上是「鉸鏈 + 打開的門片 + 四分之一弧」：``start``→``end`` 是
    打開後的門片，``start``→``swing_end`` 才是關起來時佔的那段牆洞。門本來
    就坐落在兩段牆之間的缺口裡，所以要比對的是牆所在的**直線**（延伸線），
    不是牆線段本身——量到線段端點會得到 50~70cm 的假距離，把門判成不屬於
    那面牆（2026-08-03 Ben 實走，door-1 的真實偏移只有 10cm，約半個牆厚）。

    只做垂直於牆的平移，沿牆方向的位置與門寬、門弧形狀全部保留。
    """
    if not doors or not walls:
        return doors

    def _pt(value: Any) -> tuple[float, float] | None:
        if not isinstance(value, dict):
            return None
        try:
            return float(value.get("x", 0.0)), float(value.get("z", 0.0))
        except (TypeError, ValueError):
            return None

    aligned: list[dict[str, Any]] = []
    for door in doors:
        hinge = _pt(door.get("start"))
        swing = _pt(door.get("swing_end"))
        leaf_end = _pt(door.get("end"))
        # 有門弧就用關閉門洞；沒有的話退回門片本身（直接開口的門）。
        opening_a, opening_b = (hinge, swing) if hinge and swing else (hinge, leaf_end)
        if opening_a is None or opening_b is None:
            aligned.append(door)
            continue
        mid = ((opening_a[0] + opening_b[0]) / 2, (opening_a[1] + opening_b[1]) / 2)
        dir_x, dir_z = opening_b[0] - opening_a[0], opening_b[1] - opening_a[1]
        length = math.hypot(dir_x, dir_z)
        if length <= 1e-6:
            aligned.append(door)
            continue
        dir_x, dir_z = dir_x / length, dir_z / length

        best: tuple[float, tuple[float, float]] | None = None
        for wall in walls:
            start, end = _pt(wall.get("start")), _pt(wall.get("end"))
            if start is None or end is None:
                continue
            wx, wz = end[0] - start[0], end[1] - start[1]
            wall_length = math.hypot(wx, wz)
            if wall_length <= 1e-6:
                continue
            wx, wz = wx / wall_length, wz / wall_length
            # 門洞必須與牆平行才可能屬於它（容許 ~15 度誤差）。
            if abs(dir_x * wx + dir_z * wz) < 0.96:
                continue
            # 垂直距離量到牆的延伸線，門位在兩段牆之間的缺口也量得準。
            offset_x, offset_z = mid[0] - start[0], mid[1] - start[1]
            along = offset_x * wx + offset_z * wz
            perp_x = offset_x - along * wx
            perp_z = offset_z - along * wz
            gap = math.hypot(perp_x, perp_z)
            if best is None or gap < best[0]:
                best = (gap, (-perp_x, -perp_z))
        if best is None or best[0] > max_gap_cm or best[0] < 1e-6:
            aligned.append(door)
            continue
        shift_x, shift_z = best[1]

        def _moved(value: Any) -> Any:
            point = _pt(value)
            if point is None:
                return value
            return {**value, "x": point[0] + shift_x, "z": point[1] + shift_z}

        moved = {
            **door,
            "start": _moved(door.get("start")),
            "end": _moved(door.get("end")),
        }
        if isinstance(door.get("swing_end"), dict):
            moved["swing_end"] = _moved(door["swing_end"])
        closed = door.get("closed_segment")
        if isinstance(closed, dict):
            moved["closed_segment"] = {
                **closed,
                "start": _moved(closed.get("start")),
                "end": _moved(closed.get("end")),
            }
        aligned.append(moved)
    return aligned


def _snap_openings_to_walls(
    openings: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    max_gap_cm: float = SNAP_OPENING_TO_WALL_MAX_CM,
) -> list[dict[str, Any]]:
    """把門窗平移到宿主牆的中心線上。

    平面圖裡門弧與窗線本來就畫在牆「旁邊」，辨識照實記錄，第 4 步確認時
    在 2D 圖上看也正常——但轉成 3D 之後那條線不在牆身上，門片浮在離牆
    20~70 公分的空中，牆上也挖不出洞（2026-08-03 Ben 實走發現）。

    用平移而不是把端點各自投影：平移保住開口的長度與門弧形狀，只把它
    整個貼回牆面。超過 ``max_gap_cm`` 的不動——那種距離已經不是繪圖偏移，
    硬拉過去只會把開口塞進不相干的牆。
    """
    if not openings or not walls:
        return openings

    def _point(value: Any) -> tuple[float, float] | None:
        if not isinstance(value, dict):
            return None
        try:
            return float(value.get("x", 0.0)), float(value.get("z", 0.0))
        except (TypeError, ValueError):
            return None

    def _offset_to_wall(
        mid: tuple[float, float],
        wall: dict[str, Any],
        along_slack_cm: float,
    ):
        start, end = _point(wall.get("start")), _point(wall.get("end"))
        if start is None or end is None:
            return None
        dx, dz = end[0] - start[0], end[1] - start[1]
        length_sq = dx * dx + dz * dz
        if length_sq <= 0:
            return None
        t = ((mid[0] - start[0]) * dx + (mid[1] - start[1]) * dz) / length_sq
        # 投影到牆的「延伸線」，不 clamp 進線段——窗跟門一樣常佔在兩段共線
        # 牆的缺口裡，夾到端點會把整扇窗沿牆拖走，變成半截在牆上半截懸空
        # （2026-08-03：window-2 的中心被拖到 wall-12 的端點）。沿牆超出量
        # 以開口半長加餘裕為限，再遠就是同一條線上不相干的牆。
        overshoot = max(-t, t - 1.0, 0.0) * math.sqrt(length_sq)
        if overshoot > along_slack_cm:
            return None
        foot = (start[0] + t * dx, start[1] + t * dz)
        return foot[0] - mid[0], foot[1] - mid[1]

    walls_by_id = {str(wall.get("id")): wall for wall in walls if wall.get("id")}
    snapped: list[dict[str, Any]] = []
    for opening in openings:
        start, end = _point(opening.get("start")), _point(opening.get("end"))
        if start is None or end is None:
            snapped.append(opening)
            continue
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        half_length_cm = math.hypot(end[0] - start[0], end[1] - start[1]) / 2
        along_slack_cm = half_length_cm + 30.0
        host = walls_by_id.get(str(opening.get("host_wall_id")))
        candidates = [host] if host else list(walls)
        best: tuple[float, tuple[float, float]] | None = None
        for wall in candidates:
            if not isinstance(wall, dict):
                continue
            offset = _offset_to_wall(mid, wall, along_slack_cm)
            if offset is None:
                continue
            gap = math.hypot(offset[0], offset[1])
            if best is None or gap < best[0]:
                best = (gap, offset)
        if best is None or best[0] > max_gap_cm or best[0] < 1e-6:
            snapped.append(opening)
            continue
        shift_x, shift_z = best[1]

        def _moved(value: Any) -> Any:
            point = _point(value)
            if point is None:
                return value
            return {**value, "x": point[0] + shift_x, "z": point[1] + shift_z}

        moved = {
            **opening,
            "start": _moved(opening.get("start")),
            "end": _moved(opening.get("end")),
        }
        if isinstance(opening.get("swing_end"), dict):
            moved["swing_end"] = _moved(opening["swing_end"])
        closed = opening.get("closed_segment")
        if isinstance(closed, dict):
            moved["closed_segment"] = {
                **closed,
                "start": _moved(closed.get("start")),
                "end": _moved(closed.get("end")),
            }
        snapped.append(moved)
    return _dedupe_wall_openings(snapped)


def _dedupe_wall_openings(
    openings: list[dict[str, Any]],
    overlap_ratio: float = 0.6,
) -> list[dict[str, Any]]:
    """合併貼牆後重疊的開口。

    平面圖的一個門洞常被畫成牆兩側各一條門框線，辨識端照實記成兩扇門；
    貼回牆面之後它們會疊在同一段牆上，看起來就是「門的數量與樣子都不對」
    （2026-08-03 Ben 實走發現）。重疊超過 ``overlap_ratio`` 的視為同一個
    開口，保留較寬的那個——寬度取自實際量測，窄的那條通常是內側門框。
    """
    kept: list[dict[str, Any]] = []
    for opening in openings:
        start, end = opening.get("start"), opening.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            kept.append(opening)
            continue
        span = math.hypot(
            float(end.get("x", 0)) - float(start.get("x", 0)),
            float(end.get("z", 0)) - float(start.get("z", 0)),
        )
        duplicate_index = None
        for index, existing in enumerate(kept):
            if str(existing.get("host_wall_id") or "") != str(opening.get("host_wall_id") or ""):
                continue
            other_start, other_end = existing.get("start"), existing.get("end")
            if not isinstance(other_start, dict) or not isinstance(other_end, dict):
                continue
            other_span = math.hypot(
                float(other_end.get("x", 0)) - float(other_start.get("x", 0)),
                float(other_end.get("z", 0)) - float(other_start.get("z", 0)),
            )
            gap = math.hypot(
                (float(start.get("x", 0)) + float(end.get("x", 0))) / 2
                - (float(other_start.get("x", 0)) + float(other_end.get("x", 0))) / 2,
                (float(start.get("z", 0)) + float(end.get("z", 0))) / 2
                - (float(other_start.get("z", 0)) + float(other_end.get("z", 0))) / 2,
            )
            # 兩個開口的中心距離小於半長之和的一定比例＝實質重疊。
            if gap <= (span + other_span) / 2 * (1 - overlap_ratio):
                duplicate_index = index
                break
        if duplicate_index is None:
            kept.append(opening)
            continue
        existing = kept[duplicate_index]
        existing_span = math.hypot(
            float(existing["end"].get("x", 0)) - float(existing["start"].get("x", 0)),
            float(existing["end"].get("z", 0)) - float(existing["start"].get("z", 0)),
        )
        if span > existing_span:
            kept[duplicate_index] = opening
    return kept


def door_openings_from_segments(
    parsed_floorplan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """門在牆上的開口。

    走動視角靠這份清單豁免門洞；``scene_json`` 少了它，每一扇門在第 7 步都是
    實牆，人走到門口就被擋住。開合門要用 hinge → swing_end 的
    ``closed_segment``——``start`` → ``end`` 是打開後的門片，不是牆洞。
    """
    openings: list[dict[str, Any]] = []
    for door in (parsed_floorplan or {}).get("door_segments") or []:
        if not isinstance(door, dict):
            continue
        closed = door.get("closed_segment")
        hole = closed if isinstance(closed, dict) else door
        start = hole.get("start") if isinstance(hole.get("start"), dict) else None
        end = hole.get("end") if isinstance(hole.get("end"), dict) else None
        if not start or not end:
            continue
        try:
            start_x, start_z = float(start.get("x", 0)), float(start.get("z", 0))
            end_x, end_z = float(end.get("x", 0)), float(end.get("z", 0))
        except (TypeError, ValueError):
            continue
        measured_cm = math.hypot(end_x - start_x, end_z - start_z)
        try:
            declared_cm = float(door.get("width_cm") or 0)
        except (TypeError, ValueError):
            declared_cm = 0.0
        openings.append(
            {
                "start": {"x": start_x, "z": start_z},
                "end": {"x": end_x, "z": end_z},
                "width_cm": round(declared_cm or measured_cm, 2),
                "kind": "door",
            }
        )
    return openings


def _shrunk_boundary(room: Room, margin_cm: float = DEFAULT_WALK_MARGIN_CM) -> Polygon | None:
    boundary = _room_boundary_polygon(room)
    if boundary is None:
        return None
    shrunk = boundary.buffer(-abs(margin_cm))
    return boundary if shrunk.is_empty else shrunk


# 問卷擺位偏好 → 引擎真的做得到的動作。表以外的 key 一律回報成「未套用」，
# 不要讓前端以為送出去就會生效（QA 2026-08-01 #10：整條 no-op）。
PLACEMENT_PREFERENCE_EFFECTS: dict[str, dict[str, str]] = {
    "circulation_priority": {"wide": "walk_margin", "storage": "walk_margin"},
    "bed_priority": {"clearance": "walk_margin", "large": "walk_margin"},
    "window_zone": {"clear": "window_clearance", "seat_storage": "window_clearance"},
}


def resolve_placement_preferences(
    preferences: dict[str, Any] | None,
) -> tuple[float, float, list[str], list[str]]:
    """把問卷偏好翻成引擎參數。

    回傳 ``(走道邊距, 窗前淨空深度, 已套用的 key, 未套用的 key)``。未套用清單
    會回到 API 回應，讓「送了但沒生效」看得見而不是靜默。
    """
    preferences = preferences if isinstance(preferences, dict) else {}
    walk_margin_cm = DEFAULT_WALK_MARGIN_CM
    window_clearance_cm = WINDOW_CLEARANCE_DEPTH_CM
    applied: list[str] = []
    ignored: list[str] = []

    for key, raw_value in preferences.items():
        value = raw_value if isinstance(raw_value, str) else str(raw_value).lower()
        known_values = PLACEMENT_PREFERENCE_EFFECTS.get(str(key))
        if not known_values or value not in known_values:
            ignored.append(str(key))
            continue
        if key == "circulation_priority":
            walk_margin_cm = (
                WIDE_WALK_MARGIN_CM if value == "wide" else DEFAULT_WALK_MARGIN_CM
            )
        elif key == "bed_priority":
            walk_margin_cm = max(
                walk_margin_cm,
                WIDE_WALK_MARGIN_CM if value == "clearance" else DEFAULT_WALK_MARGIN_CM,
            )
        elif key == "window_zone":
            # 使用者要窗邊臥榻／收納時，窗前淨空帶就是障礙而不是保護。
            window_clearance_cm = 0.0 if value == "seat_storage" else WINDOW_CLEARANCE_DEPTH_CM
        applied.append(str(key))

    return walk_margin_cm, window_clearance_cm, applied, ignored


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
    placement_preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。

    禁區必須跟 ``generate_layout`` 走同一份 ``placement_forbidden_zones``,
    否則自動配置放得下的位置,使用者手動拖過去會被判違規。
    """
    room = room_from_payload(floorplan)
    # 拖曳可放進「任何一間房」(聯集);沒有房間資訊才退回最大房間環
    boundary = _regions_boundary(floorplan, room) or _shrunk_boundary(room)
    half_w_cm = room.width / 2
    half_d_cm = room.depth / 2

    moving = _scene_object_to_placed(item, half_w_cm, half_d_cm)

    # 檯面小物（2026-08-03 方案 B）：帶宿主時驗證「型別相容＋腳印落在宿主
    # 檯面內」，通過即合法——它站在宿主上，邊界與門窗約束由宿主承擔。
    # 未帶宿主維持舊行為（不擋），吸附與待處理提示由前端負責。
    if placement_surface_for(item.get("normalized_type"), item.get("name_zh_raw")) == TABLETOP:
        host_id = str(item.get("host_object_id") or "")
        if host_id:
            host_obj = next(
                (o for o in others if str(o.get("furniture_id")) == host_id),
                None,
            )
            if host_obj is None:
                return {"ok": False, "reason": "宿主家具不存在，請重新放置這件擺飾"}
            host_type = str(host_obj.get("normalized_type") or "").strip().lower()
            if host_type not in allowed_host_types(item.get("normalized_type")):
                return {"ok": False, "reason": "這類擺飾不能放在該家具的檯面上"}
            host_placed = _scene_object_to_placed(host_obj, half_w_cm, half_d_cm)
            if not rests_within_host(moving, host_placed):
                return {"ok": False, "reason": "擺飾超出了宿主家具的檯面範圍"}
            return {"ok": True, "reason": None}

    if not _inside_boundary(moving, boundary):
        return {"ok": False, "reason": "超出房間範圍(需完整放在某一間房內,不能跨牆)"}

    # 門弧與窗前禁區對所有型別一律適用——地毯與壁架也不能卡住門扇。
    _, window_clearance_cm, _applied, _ignored = resolve_placement_preferences(
        placement_preferences
    )
    blocking = _blocking_zone(
        moving, placement_forbidden_zones(floorplan, room, window_clearance_cm)
    )
    if blocking is not None:
        return {"ok": False, "reason": blocking.reason}

    # 誰能和誰重疊由引擎的垂直佔用帶判定(backend/engine/geometry.py),
    # 這裡不再用型別名單先把地毯與壁掛挑出來繞過碰撞。
    placed_others = [
        _scene_object_to_placed(o, half_w_cm, half_d_cm)
        for o in others
        if not o.get("placement_failed")
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
    placement_preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """家具座標一律由 furniture_engine 決定(碰撞 + 淨空,Shapely 驗證)。

    類型錨點(_placement_candidates)只提供「視覺上合理」的候選順序;
    合法性由引擎的 check_placement_with_clearance 把關,錨點全數不合法時
    退回引擎的網格搜尋(place_furniture),再不行就標記 placement_failed。

    座標契約(對前端不變):position_cm 為房間中心原點、公分;rotation_y_deg
    為 three.js 的 Y 軸旋轉(與引擎旋轉方向相反,進出引擎時取負號)。
    """
    if room is None:
        room = _four_wall_room(max(room_width_cm, 240), max(room_depth_cm, 240))

    # 擺放搜尋邊界(內縮 8cm 邊距):DXF 模式傳入最大自由空間;
    # 矩形房由牆環重建(等價於 bbox)。注意 DXF fallback 模式的 Room.walls
    # 是多個獨立環,不能拿去重建多邊形 —— 所以 DXF 一律走傳入的 place_boundary。
    walk_margin_cm, window_clearance_cm, _applied, _ignored = resolve_placement_preferences(
        placement_preferences
    )
    if place_boundary is not None:
        boundary = place_boundary
        # DXF／多房路徑的邊界由呼叫端算好，這裡只補上偏好要的額外走道寬度。
        extra_margin_cm = walk_margin_cm - DEFAULT_WALK_MARGIN_CM
        if extra_margin_cm > 0:
            widened = place_boundary.buffer(-extra_margin_cm)
            if not widened.is_empty:
                boundary = widened
    else:
        boundary = _shrunk_boundary(room, walk_margin_cm)
    # window_clearance_cm = 0(問卷選窗邊臥榻)只關掉一般窗的判斷帶;
    # 門弧與落地窗淨空是安全與動線,不受偏好影響。
    forbidden_zones = placement_forbidden_zones(floorplan, room, window_clearance_cm)

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

    # 鎖定位置(使用者拖曳過)的先處理,避免被後放的家具擠掉
    order = sorted(range(len(items)), key=lambda i: 0 if items[i].get("position_locked") else 1)

    for index in order:
        item = items[index]
        item_type = item.get("normalized_type")
        item_name = item.get("name_zh_raw")
        is_overlay = _is_overlay_item(item_type, item_name)
        collision_exempt = _is_collision_exempt_item(item_type, item_name)
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
        item_id = f"{item_type or 'item'}_{index + 1}"

        x_cm: float | None = None
        z_cm: float | None = None
        rotation = 0.0
        failed_reason: str | None = None
        locked = False
        kept_position = False

        preserve_position = index < preserve_existing_count and item.get("position_cm")
        if (item.get("position_locked") or preserve_position) and item.get("position_cm"):
            # 使用者手動擺過:位置仍合法就保留,不重排。
            # 驗證用「所有房間聯集」—— 使用者可能把家具拖到別的房間,重排不能把它踢掉
            candidate = _scene_object_to_placed(item, half_w_cm, half_d_cm)
            locked_boundary = regions_boundary or boundary
            # 2D 貼牆家具允許落在房間內縮邊界的 12cm 容差內，否則換 GLB
            # 後會被誤判超界並跳到其他房間。
            if locked_boundary is not None:
                locked_boundary = locked_boundary.buffer(12)
            ok = _inside_boundary(candidate, locked_boundary) and (
                collision_exempt
                or (
                    is_overlay
                    and check_placement_with_clearance(candidate, room, []) is None
                )
                or check_placement_with_clearance(candidate, room, placed) is None
            ) and not _placement_intersects_zones(candidate, forbidden_zones)
            if ok:
                x_cm = float(item["position_cm"].get("x") or 0)
                z_cm = float(item["position_cm"].get("z") or 0)
                rotation = float(item.get("rotation_y_deg") or 0)
                locked = bool(item.get("position_locked"))
                kept_position = True
                if not collision_exempt and not is_overlay:
                    placed.append(candidate)
                    placed_by_type.setdefault(item_type or "furniture", []).append(candidate)

        if kept_position:
            pass
        elif is_overlay:
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
            engine_item = None
            overlay_reason: str | None = None
            if target is not None:
                # 鋪在主家具下是首選,但主家具貼牆時大尺寸地毯會探出房間。
                # 鋪不下就退回自由擺放——地毯放房間中央仍然合理,直接判失敗
                # 會讓修復層一路換小到整件移除,使用者看到的是「沒有地毯」。
                overlay = place_overlay_on_furniture(room, catalog, item_id, target)
                candidate = overlay["placed"] if overlay["success"] else None
                if candidate is not None and _inside_boundary(candidate, boundary):
                    engine_item = candidate
                else:
                    overlay_reason = overlay["reason"]
            if engine_item is None:
                overlay = place_furniture(room, catalog, item_id, [])
                candidate = overlay["placed"] if overlay["success"] else None
                if candidate is not None and _inside_boundary(candidate, boundary):
                    engine_item = candidate
                else:
                    overlay_reason = overlay["reason"] or overlay_reason
                    engine_item = _grid_place_in_boundary(
                        catalog, item_id, room, [], boundary, forbidden_zones
                    )
            if engine_item is not None:
                x_cm = engine_item.pos_x - half_w_cm
                z_cm = engine_item.pos_y - half_d_cm
                rotation = (-engine_item.rotation) % 360
            else:
                failed_reason = overlay_reason or "地毯找不到合法位置"
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
            if (
                engine_item is not None
                and _inside_boundary(engine_item, boundary)
                and not _placement_intersects_zones(engine_item, forbidden_zones)
            ):
                placed.append(engine_item)
                placed_by_type.setdefault(item_type or "furniture", []).append(engine_item)
                x_cm = engine_item.pos_x - half_w_cm
                z_cm = engine_item.pos_y - half_d_cm
                rotation = (-engine_item.rotation) % 360
            else:
                failed_reason = adjacent["reason"] or "主家具旁沒有合法位置"
                x_cm, z_cm = 0.0, 0.0
        elif collision_exempt:
            # 壁掛品項掛在牆上,不是站在房間中央。沿牆找第一個不與既有家具
            # 打架的位置——固定角落會讓層架與掛鏡疊在同一點。
            engine_item = _place_wall_mounted(
                catalog, item_id, room, placed, forbidden_zones
            )
            if engine_item is not None:
                x_cm = engine_item.pos_x - half_w_cm
                z_cm = engine_item.pos_y - half_d_cm
                rotation = (-engine_item.rotation) % 360
                placed.append(engine_item)
                placed_by_type.setdefault(item_type or "furniture", []).append(engine_item)
            else:
                x_cm = -half_w_cm + width / 2 + 15
                z_cm = -half_d_cm + depth / 2 + 12
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
            candidates = _placement_candidates(
                item_type,
                width,
                depth,
                room_w_cm,
                room_d_cm,
                placement_bounds_cm,
            )
            if placement_variant == "B" and len(candidates) > 1:
                # 方案 B 仍走相同碰撞/淨空驗證，只改由另一端開始搜尋合法解。
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
            for raw_x, raw_z, rot in candidates:
                fp_w, fp_d = _rotated_footprint(width, depth, rot)
                wall_anchored = item_type in _WALL_ANCHORED_TYPES
                clamp_margin = 0 if wall_anchored else 18
                candidate_left, candidate_right, candidate_top, candidate_bottom = (
                    placement_bounds_cm
                    or (-half_w_cm, half_w_cm, -half_d_cm, half_d_cm)
                )
                cand_x = _clamp_axis(raw_x, candidate_left, candidate_right, fp_w, clamp_margin)
                cand_z = _clamp_axis(raw_z, candidate_top, candidate_bottom, fp_d, clamp_margin)
                candidate = PlacedFurniture(
                    id=item_id,
                    catalog=catalog,
                    pos_x=cand_x + half_w_cm,
                    pos_y=cand_z + half_d_cm,
                    rotation=(-rot) % 360,
                )
                if (
                    _inside_boundary(candidate, boundary)
                    and not _placement_intersects_zones(candidate, forbidden_zones)
                    and check_placement_with_clearance(candidate, room, placed) is None
                ):
                    x_cm, z_cm, rotation = cand_x, cand_z, rot
                    placed.append(candidate)
                    placed_by_type.setdefault(item_type or "furniture", []).append(candidate)
                    break
            else:
                result = place_furniture(room, catalog, item_id, placed)
                engine_item = result["placed"] if result["success"] else None
                if engine_item is not None and not _inside_boundary(engine_item, boundary):
                    engine_item = None
                if engine_item is not None and _placement_intersects_zones(
                    engine_item, forbidden_zones
                ):
                    engine_item = None
                if engine_item is None and boundary is not None:
                    engine_item = _grid_place_in_boundary(
                        catalog, item_id, room, placed, boundary, forbidden_zones
                    )
                if engine_item is not None:
                    placed.append(engine_item)
                    placed_by_type.setdefault(item_type or "furniture", []).append(engine_item)
                    x_cm = engine_item.pos_x - half_w_cm
                    z_cm = engine_item.pos_y - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    failed_reason = result["reason"] or "找不到落在房間形狀內的合法位置"
                    x_cm, z_cm = 0.0, 0.0

        fp_w, fp_d = _rotated_footprint(width, depth, rotation)
        results[index] = {
            "furniture_id": item["furniture_id"],
            # 多實例家具的身分鍵。擺放紀律用它對位物件與品項，沒有它就只能
            # 退回 furniture_id，同型號的第二件會被誤認成第一件。
            "instance_id": item.get("instance_id"),
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
            "rotation_y_deg": rotation,
            "position_locked": locked,
            "placement_failed": bool(failed_reason),
            "placement_reason": failed_reason,
            "placement_engine": "boundary_rule" if collision_exempt else "furniture_engine",
            "auto_decor_role": item.get("auto_decor_role"),
            "auto_decor_room_id": item.get("auto_decor_room_id"),
            "placement_relation": item.get("placement_relation"),
            "placement_room_id": item.get("placement_room_id"),
        }

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


def build_agent_generation_handoff(
    questionnaire: dict[str, Any],
    floorplan: dict[str, Any],
    scene_objects: list[dict[str, Any]],
) -> dict[str, Any]:
    """組出交給外部生圖 Agent 的持久 payload。

    契約:docs/BEN_第5第6步整合規格_中文.md「提供給最終生圖 Agent 的交付檔」。
    生圖設備(廚浴陽台)與第 6 步可拖拉家具刻意分開:前者只是生圖語境,
    後者帶著使用者調整後的最終 2D/3D 位置,生圖不得移動或重擺。
    """
    # 逐房需求容忍 dict-by-room_id 與 list 兩種形狀,與 select.py 的
    # _requirement_entries 同一條紀律:問卷 schema 由 Bella 擁有且持續增欄,
    # 讀不懂的欄位略過而不整批失敗。/api/scene/generate 把前端問卷掛在
    # test2_questionnaire 底下,巢狀來源要先查。
    test2 = (
        questionnaire.get("test2_questionnaire")
        if isinstance(questionnaire.get("test2_questionnaire"), dict)
        else {}
    )
    raw_requirements = (
        test2.get("room_requirements")
        or test2.get("roomRequirements")
        or questionnaire.get("roomRequirements")
        or questionnaire.get("room_requirements")
        or {}
    )
    if isinstance(raw_requirements, dict):
        requirement_pairs = [
            (str(key), entry)
            for key, entry in raw_requirements.items()
            if isinstance(entry, dict)
        ]
    elif isinstance(raw_requirements, list):
        requirement_pairs = [
            (str(entry.get("roomId") or entry.get("room_id") or ""), entry)
            for entry in raw_requirements
            if isinstance(entry, dict)
        ]
    else:
        requirement_pairs = []

    raw_rag_jobs = test2.get("rag_jobs") or questionnaire.get("rag_jobs")
    rag_jobs = raw_rag_jobs if isinstance(raw_rag_jobs, dict) else {}
    regions = {
        str(region.get("id") or region.get("room_id")): region
        for region in floorplan.get("room_regions", [])
        if isinstance(region, dict)
    }
    objects_by_room: dict[str, list[dict[str, Any]]] = {}
    for scene_object in scene_objects:
        room_id = str(
            scene_object.get("placement_room_id")
            or scene_object.get("auto_decor_room_id")
            or scene_object.get("room_id")
            or ""
        )
        objects_by_room.setdefault(room_id, []).append({
            "instance_id": scene_object.get("instance_id") or scene_object.get("id"),
            "catalog_item_id": scene_object.get("catalog_furniture_id") or scene_object.get("furniture_id"),
            "normalized_type": scene_object.get("normalized_type") or scene_object.get("type"),
            "name_zh": scene_object.get("name_zh_raw") or scene_object.get("name_zh"),
            "position_cm": scene_object.get("position_cm") or scene_object.get("position"),
            "rotation_deg": (
                scene_object.get("rotation_y_deg")
                if scene_object.get("rotation_y_deg") is not None
                else scene_object.get("rotation_deg", scene_object.get("rotation"))
            ),
            "size_cm": scene_object.get("size_cm") or scene_object.get("dimensions"),
            "position_locked": bool(scene_object.get("position_locked")),
        })

    rooms: list[dict[str, Any]] = []
    for room_id, requirement in requirement_pairs:
        if not room_id:
            continue
        furniture = requirement.get("furniture") if isinstance(requirement.get("furniture"), dict) else {}
        equipment = (
            requirement.get("generativeEquipment")
            or requirement.get("generative_equipment")
            or {}
        )
        surfaces = requirement.get("surfaces") if isinstance(requirement.get("surfaces"), dict) else {}
        rooms.append({
            "room_id": room_id,
            "room_type": requirement.get("roomType") or requirement.get("room_type"),
            "room_label": requirement.get("roomLabel") or requirement.get("room_label"),
            "geometry": regions.get(room_id, {}),
            "usage": requirement.get("usage") or [],
            "furniture_preference": {
                "tags": furniture.get("preferenceTags") or furniture.get("preference_tags") or [],
                "description": furniture.get("preferenceText") or furniture.get("preference_text") or "",
            },
            "selected_catalog_furniture": furniture.get("selected") or [],
            "final_step6_furniture": objects_by_room.get(room_id, []),
            "generative_equipment": equipment,
            "surfaces": surfaces,
            "rag": rag_jobs.get(room_id, {}),
        })

    global_profile = {
        key: questionnaire.get(key)
        for key in ("space_type", "style_preference", "personal_notes")
        if questionnaire.get(key) not in (None, "", [])
    }
    basic = test2.get("basic") or questionnaire.get("basic")
    if isinstance(basic, dict):
        global_profile = {**basic, **global_profile}

    return {
        "schema_version": "1.0",
        "purpose": "external_image_generation_after_step6",
        "space_constraints_are_fixed": True,
        "floorplan": {
            "coordinate_unit": floorplan.get("coordinate_unit", "cm"),
            "width_cm": floorplan.get("width_cm"),
            "depth_cm": floorplan.get("depth_cm"),
            "room_height_cm": floorplan.get("room_height_cm"),
            "door_segments": floorplan.get("door_segments", []),
            "window_segments": floorplan.get("window_segments", []),
            "wall_segments": floorplan.get("wall_segments", []),
        },
        "global_profile": global_profile,
        "style": {
            **(test2.get("finishes") if isinstance(test2.get("finishes"), dict) else {}),
            **{
                key: questionnaire.get(key)
                for key in ("style_card_id", "wall_option", "floor_option")
                if questionnaire.get(key) is not None
            },
        },
        "rooms": rooms,
    }


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
    objects = generate_layout(
        effective_width_cm,
        effective_depth_cm,
        selected_items,
        room=engine_room,
        regions_boundary=_regions_boundary(parsed_floorplan, engine_room) if engine_room else None,
        place_boundary=_largest_region_boundary(parsed_floorplan, engine_room) if engine_room else None,
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
            return generate_layout(
                effective_width_cm,
                effective_depth_cm,
                working_items,
                room=engine_room,
                regions_boundary=_regions_boundary(parsed_floorplan, engine_room) if engine_room else None,
                place_boundary=_largest_region_boundary(parsed_floorplan, engine_room) if engine_room else None,
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

    agent_generation_handoff = build_agent_generation_handoff(
        questionnaire,
        {
            "coordinate_unit": "cm",
            "width_cm": effective_width_cm,
            "depth_cm": effective_depth_cm,
            "room_height_cm": parsed_floorplan.get("room_height_cm", 270) if parsed_floorplan else 270,
            "door_segments": parsed_floorplan.get("door_segments", []) if parsed_floorplan else [],
            "window_segments": parsed_floorplan.get("window_segments", []) if parsed_floorplan else [],
            "wall_segments": parsed_floorplan.get("wall_segments", []) if parsed_floorplan else [],
            "room_regions": parsed_floorplan.get("room_regions", []) if parsed_floorplan else [],
        },
        objects,
    )
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
            "wall_polys_openings_cut": bool(parsed_floorplan.get("wall_polys_openings_cut"))
            if parsed_floorplan
            else False,
            "plan_segments": parsed_floorplan.get("plan_segments", []) if parsed_floorplan else [],
            "door_segments": parsed_floorplan.get("door_segments", []) if parsed_floorplan else [],
            "door_openings": door_openings_from_segments(parsed_floorplan),
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
        "agent_generation_handoff": agent_generation_handoff,
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
