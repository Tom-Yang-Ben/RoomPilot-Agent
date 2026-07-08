from __future__ import annotations

import json
import math
import os
import random
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from ..agent import design_layout_intent, run_recovery
from ..catalog.style_db import catalog_item_from_scene_object
from ..engine.clearance import check_placement_with_clearance
from ..engine.dxf_room import build_room_from_dxf
from ..engine.models import PlacedFurniture, Room, Wall
from ..engine.placement import place_furniture
from ..upgrade3d.dxf_parser import parse_dxf_bytes

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_CANDIDATES = [
    PROJECT_DIR / ".env",
    PROJECT_DIR / "roompilot" / "server" / ".env",
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

    def style_score(item: dict[str, Any]) -> float:
        if item.get("primary_style") == style_id:
            return 120

        for style in item.get("style_candidates", []):
            if style.get("style_id") == style_id:
                try:
                    return 76 + float(style.get("score", 0)) * 18
                except (TypeError, ValueError):
                    return 76

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


def _placement_candidates(
    item_type: str | None,
    width: float,
    depth: float,
    room_width_cm: float,
    room_depth_cm: float,
    hint: dict[str, Any] | None = None,
) -> list[tuple[float, float, float]]:
    left = -room_width_cm / 2
    right = room_width_cm / 2
    top = -room_depth_cm / 2
    bottom = room_depth_cm / 2
    center_x = 0.0
    center_z = 0.0
    candidates: list[tuple[float, float, float]] = []

    # Agent 3 提示:指定靠牆側時,把一組靠該牆的候選 prepend 到最前面優先試放。
    # 只影響「試放順序」,合法性仍由 check_placement_with_clearance 把關(鐵律不變)。
    anchor = (hint or {}).get("anchor")
    anchored: list[tuple[float, float, float]] = []
    if anchor == "top":
        z = top + depth / 2 + 24
        anchored = [(center_x, z, 0), (-room_width_cm * 0.22, z, 0), (room_width_cm * 0.22, z, 0)]
    elif anchor == "bottom":
        z = bottom - depth / 2 - 36
        anchored = [(center_x, z, 180), (-room_width_cm * 0.18, z, 180), (room_width_cm * 0.18, z, 180)]
    elif anchor == "left":
        x = left + width / 2 + 20
        anchored = [(x, center_z, 90), (x, -room_depth_cm * 0.2, 90), (x, room_depth_cm * 0.2, 90)]
    elif anchor == "right":
        x = right - width / 2 - 20
        anchored = [(x, center_z, -90), (x, -room_depth_cm * 0.2, -90), (x, room_depth_cm * 0.2, -90)]
    elif anchor == "center":
        anchored = [(center_x, center_z, 0)]

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

    return anchored + candidates


# 這些類型沿用舊行為,不參與碰撞(地毯在家具下方、壁架掛牆面)
_IGNORE_COLLISION_TYPES = {"large-medium-rug", "runner-small-rug", "wall-shelf"}


def _four_wall_room(width_m: float, depth_m: float) -> Room:
    """手動輸入尺寸時的矩形房間(引擎座標:角落原點、公尺)。"""
    return Room(
        width=width_m,
        depth=depth_m,
        walls=[
            Wall(0, 0, width_m, 0),
            Wall(width_m, 0, width_m, depth_m),
            Wall(width_m, depth_m, 0, depth_m),
            Wall(0, depth_m, 0, 0),
        ],
    )


def generate_layout(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    room: Room | None = None,
    hints: dict[str, dict[str, Any]] | None = None,
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
        room = _four_wall_room(max(room_width_cm, 240) / 100, max(room_depth_cm, 240) / 100)

    room_w_cm = room.width * 100
    room_d_cm = room.depth * 100
    half_w_cm = room_w_cm / 2
    half_d_cm = room_d_cm / 2

    # 擺放順序:有 priority 提示的先擺(升冪),其餘維持原始順序;
    # 但輸出仍照原始 items 順序(以 results 對應),不動前端拿到的清單順序。
    if hints:
        def _order_key(i: int) -> tuple:
            hint = hints.get(items[i].get("furniture_id")) or {}
            priority = hint.get("priority")
            return (0, priority, i) if isinstance(priority, int) else (1, i)

        order = sorted(range(len(items)), key=_order_key)
    else:
        order = list(range(len(items)))

    placed: list[PlacedFurniture] = []
    results: dict[int, dict[str, Any]] = {}

    for index in order:
        item = items[index]
        item_type = item.get("normalized_type")
        width = _size_cm(item, "width", 120)
        depth = _size_cm(item, "depth", 60)
        height = _size_cm(item, "height", 80)
        catalog = catalog_item_from_scene_object(
            item_type, item.get("name_zh_raw") or item.get("furniture_id"), width, depth, height
        )
        item_id = f"{item_type or 'item'}_{index + 1}"
        hint = (hints or {}).get(item.get("furniture_id"))

        x_cm: float | None = None
        z_cm: float | None = None
        rotation = 0.0
        failed_reason: str | None = None

        if item_type in _IGNORE_COLLISION_TYPES:
            if item_type == "wall-shelf":
                x_cm = -half_w_cm + width / 2 + 15
                z_cm = -half_d_cm + depth / 2 + 12
            else:
                x_cm, z_cm = 0.0, 0.0
        else:
            for raw_x, raw_z, rot in _placement_candidates(item_type, width, depth, room_w_cm, room_d_cm, hint=hint):
                fp_w, fp_d = _rotated_footprint(width, depth, rot)
                cand_x = _clamp_axis(raw_x, -half_w_cm, half_w_cm, fp_w)
                cand_z = _clamp_axis(raw_z, -half_d_cm, half_d_cm, fp_d)
                candidate = PlacedFurniture(
                    id=item_id,
                    catalog=catalog,
                    pos_x=(cand_x + half_w_cm) / 100,
                    pos_y=(cand_z + half_d_cm) / 100,
                    rotation=(-rot) % 360,
                )
                if check_placement_with_clearance(candidate, room, placed) is None:
                    x_cm, z_cm, rotation = cand_x, cand_z, rot
                    placed.append(candidate)
                    break
            else:
                result = place_furniture(room, catalog, item_id, placed)
                if result["success"]:
                    engine_item = result["placed"]
                    placed.append(engine_item)
                    x_cm = engine_item.pos_x * 100 - half_w_cm
                    z_cm = engine_item.pos_y * 100 - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    failed_reason = result["reason"]
                    x_cm, z_cm = 0.0, 0.0

        fp_w, fp_d = _rotated_footprint(width, depth, rotation)
        results[index] = {
            "furniture_id": item["furniture_id"],
            "name_zh_raw": item.get("name_zh_raw"),
            "normalized_type": item_type,
            "model_url": item.get("model_url"),
            "primary_style": item.get("primary_style"),
            "size_cm": {"width": width, "depth": depth, "height": height},
            "footprint_cm": {"width": round(fp_w, 2), "depth": round(fp_d, 2)},
            "position_cm": {"x": round(x_cm, 2), "z": round(z_cm, 2)},
            "rotation_y_deg": rotation,
            "placement_failed": bool(failed_reason),
            "placement_reason": failed_reason,
        }

    return [results[i] for i in range(len(items))]


def parse_floorplan_with_engine(dxf_text: str) -> tuple[dict[str, Any] | None, Room | None]:
    """DXF 文字 → (payload 的 floorplan 區塊, 引擎 Room)。

    解析走 upgrade3d.dxf_parser(ezdxf,平面中心原點、公尺),
    再由 engine.dxf_room 取最大封閉房間轉成 Room(角落原點)。
    回傳的線段座標一律換算成「房間中心原點、公尺」,維持前端 viewer 契約。
    """
    try:
        parsed = parse_dxf_bytes(dxf_text.encode("utf-8", errors="ignore"), "upload.dxf")
        build = build_room_from_dxf(parsed)
    except Exception:
        return None, None

    room = build.room
    ox, oz = build.offset
    room_center_x = ox + room.width / 2   # 房間中心(平面座標)
    room_center_z = oz + room.depth / 2

    wall_segments = [
        {
            "start": {"x": round(w.x1 - room.width / 2, 3), "z": round(w.y1 - room.depth / 2, 3)},
            "end": {"x": round(w.x2 - room.width / 2, 3), "z": round(w.y2 - room.depth / 2, 3)},
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

    floorplan = {
        "width_cm": round(room.width * 100, 1),
        "depth_cm": round(room.depth * 100, 1),
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
        parsed_floorplan, engine_room = parse_floorplan_with_engine(dxf_text)

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
    objects = generate_layout(
        effective_width_cm, effective_depth_cm, selected_items, room=engine_room, hints=hints
    )

    # Agent 4:引擎放不下的家具 → 換更小同型號 / 移除 / 升級,重擺至收斂。
    # 座標仍 100% 由引擎(place_fn)算;無 LLM 時走確定性換小/移除。
    def _place(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return generate_layout(effective_width_cm, effective_depth_cm, items, room=engine_room, hints=hints)

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
        "selected_furniture": selected_items,
        "scene_objects": objects,
        "placement": {
            "engine": "furniture_engine",
            "failed": [
                {"furniture_id": obj["furniture_id"], "reason": obj["placement_reason"]}
                for obj in objects
                if obj.get("placement_failed")
            ],
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
