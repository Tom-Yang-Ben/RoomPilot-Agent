from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from ..agent.knowledge import (
    ROOM_COMPANION_ESSENTIALS,
    ROOM_ESSENTIALS,
    dining_chair_target,
    family_of,
)
from ..model_config import model_list


PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_CANDIDATES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "backend" / "server" / ".env",
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
    """第 6 步 LLM 場景規劃的模型清單（設定見 backend/model_config.py 的 `scene_planning`）。"""
    load_local_env()
    return model_list("scene_planning")


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
        # 客廳基本組:沙發之外,茶几與電視櫃也是必備(至少沙發+茶几+電視櫃);
        # 缺了就補進 required,否則它們是 companion,不在清單就不會被 choose 挑到。
        for companion in ROOM_COMPANION_ESSENTIALS.get(space_type, ()):
            if not any(family_of(item) == companion for item in normalized):
                normalized.append(companion)
        # 有餐桌就要有餐椅(張數保證在選件與 2D 規格層;此處保證型別存在)
        if any(family_of(item) == "dining-table" for item in normalized) and not any(
            family_of(item) == "dining-chair" for item in normalized
        ):
            normalized.append("dining-chair")
        return normalized

    return SPACE_DEFAULTS.get(space_type, SPACE_DEFAULTS["living_room"]).copy()


def _occupant_headcount(questionnaire: dict[str, Any]) -> int:
    """入住人數 = 大人 + 小孩 + 長輩(寵物不算)。缺資料回 0。"""
    occ = questionnaire.get("occupants")
    if not isinstance(occ, dict):
        return 0
    total = 0
    for key in ("adults", "children", "elderly"):
        try:
            total += max(0, int(occ.get(key) or 0))
        except (TypeError, ValueError):
            continue
    return total


def _merge_exact_and_chosen(
    exact: list[dict[str, Any]], chosen: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """精選件優先入座,自動選的同 id 或**同族**讓位。

    同族去重(非 normalized_type 字串)是防「臥室兩張床」的根治點:精選床可能是
    bed-frame、自動選的是 bed,字串不等會兩張都留;family_of 摺疊後同族只保留精選。
    """
    exact_ids = {item.get("furniture_id") for item in exact}
    exact_families = {family_of(item.get("normalized_type")) for item in exact}
    return [
        *exact,
        *[
            item
            for item in chosen
            if item.get("furniture_id") not in exact_ids
            and family_of(item.get("normalized_type")) not in exact_families
        ],
    ]


def _expand_dining_seats(
    items: list[dict[str, Any]], questionnaire: dict[str, Any]
) -> list[dict[str, Any]]:
    """有餐桌就把餐椅補到「依入住人數,至少 2、不超過桌子可坐數」的張數。

    choose_furniture_items 只挑一張餐椅、bella 流程也不展開 count,廚房因此常只有
    一張椅子。桌子可坐數沿用 dining_chair_target(桌寬 ≥140cm→4、否則 2)。多張同款
    餐椅給不同 instance_id,generate_layout 才會逐一擺到餐桌四周。
    """
    table = next(
        (it for it in items if family_of(it.get("normalized_type")) == "dining-table"),
        None,
    )
    if table is None:
        return items
    chairs = [it for it in items if family_of(it.get("normalized_type")) == "dining-chair"]
    if not chairs:
        return items                       # 沒有餐椅可補(選件層應已補一張)
    seats_cap = dining_chair_target((table.get("size_cm") or {}).get("width"))
    target = min(max(2, _occupant_headcount(questionnaire) or 2), seats_cap)
    if len(chairs) >= target:
        return items                       # 已足量(例如精選多張)不動
    base = chairs[0]
    # 去掉既有的 #seatN:換寬桌後二次展開(2→4 張)不該疊成 c#seat1#seat1。
    base_fid = str(base.get("furniture_id") or "dining-chair").split("#seat")[0]
    expanded: list[dict[str, Any]] = []
    filled = False
    for it in items:
        if family_of(it.get("normalized_type")) == "dining-chair":
            if filled:
                continue                   # 其餘餐椅併入下面的展開
            filled = True
            for seat in range(target):
                seat_id = f"{base_fid}#seat{seat + 1}"
                # furniture_id 必須逐張唯一:前端 2D 清單(scene_configuration_sync.
                # upsertFurniture2dFromSceneObject)與後端 exact 去重(selected_furniture_
                # items_from_questionnaire)都只認 furniture_id,同 id 的多張椅會被壓回
                # 一張 —— 展開了也只有一張進得了第 6 步。catalog_furniture_id 保留原
                # 型錄 id,第 8 步報價回查(main._price_lookup_keys)不受影響。
                expanded.append({
                    **base,
                    "furniture_id": seat_id,
                    "instance_id": seat_id,
                    "catalog_furniture_id": base.get("catalog_furniture_id") or base_fid,
                })
        else:
            expanded.append(it)
    return expanded


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
