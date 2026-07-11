from __future__ import annotations

import json
import math
import os
import random
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union

from ..catalog.style_db import catalog_item_from_scene_object
from ..engine.clearance import check_placement_with_clearance
from ..engine.dxf_room import build_room_from_dxf
from ..engine.geometry import furniture_polygon
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


# 這些類型沿用舊行為,不參與碰撞(地毯在家具下方、壁架掛牆面)
_IGNORE_COLLISION_TYPES = {"large-medium-rug", "runner-small-rug", "wall-shelf"}


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
    """非矩形房間的最後防線:沿房間多邊形內部以 0.5m 網格搜尋(由質心向外)。

    錨點與引擎網格都以 bbox 為座標基準,房間只佔 bbox 一角時全會撲空,
    這裡改以房間多邊形自己的範圍掃描。
    """
    from shapely.geometry import Point
    from shapely.prepared import prep

    prepared = prep(boundary)
    minx, miny, maxx, maxy = boundary.bounds
    cx, cy = boundary.centroid.x, boundary.centroid.y
    step = 0.5

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


def room_from_payload(floorplan: dict[str, Any] | None) -> Room:
    """由 payload 的 floorplan 區塊重建引擎 Room(拖曳驗證/重排都是無狀態請求)。

    wall_segments 是房間中心原點、公尺;引擎要角落原點 → 平移 half。
    沒有牆段(手動模式)就退回矩形房。
    """
    floorplan = floorplan or {}
    width = max(float(floorplan.get("width_cm") or 420), 240) / 100
    depth = max(float(floorplan.get("depth_cm") or 360), 240) / 100

    walls: list[Wall] = []
    for seg in floorplan.get("wall_segments") or []:
        try:
            walls.append(
                Wall(
                    float(seg["start"]["x"]) + width / 2,
                    float(seg["start"]["z"]) + depth / 2,
                    float(seg["end"]["x"]) + width / 2,
                    float(seg["end"]["z"]) + depth / 2,
                    thickness=0.06,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    if len(walls) < 3:
        return _four_wall_room(width, depth)
    return Room(width=width, depth=depth, walls=walls)


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
        pos_x=(float(pos.get("x") or 0) + half_w_cm) / 100,
        pos_y=(float(pos.get("z") or 0) + half_d_cm) / 100,
        rotation=(-float(obj.get("rotation_y_deg") or 0)) % 360,
    )


def _shrunk_boundary(room: Room) -> Polygon | None:
    boundary = _room_boundary_polygon(room)
    if boundary is None:
        return None
    shrunk = boundary.buffer(-0.08)
    return boundary if shrunk.is_empty else shrunk


def _regions_boundary(floorplan: dict[str, Any] | None, room: Room) -> Polygon | None:
    """全部房間的聯集多邊形(角落原點)——拖曳可放進任何一間,跨牆自動不合法。

    floorplan["room_regions"] 是房間中心原點的環;沒有(手動矩形模式)回 None。
    """
    polys = _region_polygons(floorplan, room)
    if not polys:
        return None
    union = unary_union(polys)
    shrunk = union.buffer(-0.08)
    return union if shrunk.is_empty else shrunk


def _region_polygons(floorplan: dict[str, Any] | None, room: Room) -> list[Polygon]:
    """payload 的 room_regions({exterior, holes},房間中心原點)→ 角落原點多邊形。"""
    polys: list[Polygon] = []
    for region in (floorplan or {}).get("room_regions") or []:
        try:
            def _shift(ring):
                return [(p[0] + room.width / 2, p[1] + room.depth / 2) for p in ring]

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
    shrunk = best.buffer(-0.08)
    return best if shrunk.is_empty else shrunk


def validate_single_placement(
    floorplan: dict[str, Any] | None,
    item: dict[str, Any],
    others: list[dict[str, Any]],
) -> dict[str, Any]:
    """F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。"""
    room = room_from_payload(floorplan)
    # 拖曳可放進「任何一間房」(聯集);沒有房間資訊才退回最大房間環
    boundary = _regions_boundary(floorplan, room) or _shrunk_boundary(room)
    half_w_cm = room.width * 50
    half_d_cm = room.depth * 50

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
    reason = check_placement_with_clearance(moving, room, placed_others)
    return {"ok": reason is None, "reason": reason}


def generate_layout(
    room_width_cm: float,
    room_depth_cm: float,
    items: list[dict[str, Any]],
    room: Room | None = None,
    regions_boundary: Polygon | None = None,
    place_boundary: Polygon | None = None,
) -> list[dict[str, Any]]:
    """家具座標一律由 furniture_engine 決定(碰撞 + 淨空,Shapely 驗證)。

    類型錨點(_placement_candidates)只提供「視覺上合理」的候選順序;
    合法性由引擎的 check_placement_with_clearance 把關,錨點全數不合法時
    退回引擎的網格搜尋(place_furniture),再不行就標記 placement_failed。

    座標契約(對前端不變):position_cm 為房間中心原點、公分;rotation_y_deg
    為 three.js 的 Y 軸旋轉(與引擎旋轉方向相反,進出引擎時取負號)。
    """
    if room is None:
        room = _four_wall_room(max(room_width_cm, 240) / 100, max(room_depth_cm, 240) / 100)

    # 擺放搜尋邊界(內縮 8cm 邊距):DXF 模式傳入最大自由空間;
    # 矩形房由牆環重建(等價於 bbox)。注意 DXF fallback 模式的 Room.walls
    # 是多個獨立環,不能拿去重建多邊形 —— 所以 DXF 一律走傳入的 place_boundary。
    boundary = place_boundary if place_boundary is not None else _shrunk_boundary(room)

    room_w_cm = room.width * 100
    room_d_cm = room.depth * 100
    half_w_cm = room_w_cm / 2
    half_d_cm = room_d_cm / 2

    placed: list[PlacedFurniture] = []
    results: dict[int, dict[str, Any]] = {}

    # 鎖定位置(使用者拖曳過)的先處理,避免被後放的家具擠掉
    order = sorted(range(len(items)), key=lambda i: 0 if items[i].get("position_locked") else 1)

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
                pos_x=(x_cm + half_w_cm) / 100, pos_y=(z_cm + half_d_cm) / 100,
            )
            if boundary is not None and not _inside_boundary(probe, boundary):
                inner = boundary.representative_point()
                x_cm = inner.x * 100 - half_w_cm
                z_cm = inner.y * 100 - half_d_cm
        else:
            for raw_x, raw_z, rot in _placement_candidates(item_type, width, depth, room_w_cm, room_d_cm):
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
                if (
                    _inside_boundary(candidate, boundary)
                    and check_placement_with_clearance(candidate, room, placed) is None
                ):
                    x_cm, z_cm, rotation = cand_x, cand_z, rot
                    placed.append(candidate)
                    break
            else:
                result = place_furniture(room, catalog, item_id, placed)
                engine_item = result["placed"] if result["success"] else None
                if engine_item is not None and not _inside_boundary(engine_item, boundary):
                    engine_item = None
                if engine_item is None and boundary is not None:
                    engine_item = _grid_place_in_boundary(catalog, item_id, room, placed, boundary)
                if engine_item is not None:
                    placed.append(engine_item)
                    x_cm = engine_item.pos_x * 100 - half_w_cm
                    z_cm = engine_item.pos_y * 100 - half_d_cm
                    rotation = (-engine_item.rotation) % 360
                else:
                    failed_reason = result["reason"] or "找不到落在房間形狀內的合法位置"
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


def parse_floorplan_with_engine(
    dxf_text: str,
    scale_m: float | None = None,
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
        def _ring_to_payload(coords) -> list:
            return [[round(p[0] - room_center_x, 3), round(p[1] - room_center_z, 3)] for p in coords]

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
        parsed_floorplan, engine_room = parse_floorplan_with_engine(dxf_text, scale_m=scale_m)

    effective_width_cm = parsed_floorplan["width_cm"] if parsed_floorplan else room_width_cm
    effective_depth_cm = parsed_floorplan["depth_cm"] if parsed_floorplan else room_depth_cm

    llm_mode, plan = build_scene_plan(questionnaire, site_payload["styles"])
    selected_items, unavailable_types = choose_furniture_items(
        plan,
        site_payload["furniture"],
        questionnaire.get("furniture_random_seed"),
        effective_width_cm,
        effective_depth_cm,
        plan.get("preferred_colors", []) + questionnaire.get("custom_colors", []),
    )
    objects = generate_layout(
        effective_width_cm,
        effective_depth_cm,
        selected_items,
        room=engine_room,
        regions_boundary=_regions_boundary(parsed_floorplan, engine_room) if engine_room else None,
        place_boundary=_largest_region_boundary(parsed_floorplan, engine_room) if engine_room else None,
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
            "room_regions": parsed_floorplan.get("room_regions", []) if parsed_floorplan else [],
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
