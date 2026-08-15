"""離線房間幾何與語意建議的共用契約。

牆、門、窗仍以 ``upgrade3d.dxf_parser`` 的中心原點公尺座標為準。本模組只做
兩件事：從牆體實心多邊形推導自由空間，以及把 DXF 文字／OpenRouter bbox
對應到房間。所有標籤都只是建議；只有專案確認 API 能把 ``confirmed`` 設為真。
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union


ROOM_TYPE_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "living_room", "label_zh": "客廳", "kind": "living"},
    {"value": "dining_room", "label_zh": "餐廳", "kind": "living"},
    {"value": "bedroom", "label_zh": "臥室", "kind": "living"},
    {"value": "study", "label_zh": "書房", "kind": "living"},
    {"value": "kitchen", "label_zh": "廚房", "kind": "fixed_utility"},
    {"value": "bathroom", "label_zh": "浴室", "kind": "fixed_utility"},
    {"value": "toilet", "label_zh": "廁所", "kind": "fixed_utility"},
    {"value": "entry", "label_zh": "玄關", "kind": "circulation"},
    {"value": "corridor", "label_zh": "走廊", "kind": "circulation"},
    {"value": "balcony", "label_zh": "陽台／露台", "kind": "outdoor"},
    {"value": "storage", "label_zh": "儲藏室", "kind": "living"},
    {"value": "laundry", "label_zh": "洗衣間", "kind": "fixed_utility"},
    {"value": "other", "label_zh": "其他空間", "kind": "living"},
)

_ROOM_TYPE_BY_VALUE = {item["value"]: item for item in ROOM_TYPE_OPTIONS}
_ROOM_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("living_room", ("living", "lounge", "客廳", "起居", "家庭廳")),
    ("dining_room", ("dining", "餐廳", "飯廳")),
    ("bedroom", ("bedroom", "master bed", "bed room", "臥室", "卧室", "主臥", "次臥", "房間")),
    ("study", ("study", "office", "書房", "工作室")),
    ("kitchen", ("kitchen", "廚房", "厨房")),
    ("bathroom", ("bathroom", "bath", "shower", "浴室", "衛浴", "卫浴")),
    ("toilet", ("toilet", "powder", "lavatory", "廁所", "厕所", "wc")),
    ("entry", ("entry", "foyer", "玄關", "入口")),
    ("corridor", ("corridor", "hallway", "走廊", "過道")),
    ("balcony", ("balcony", "terrace", "patio", "陽台", "露台", "庭院")),
    ("storage", ("storage", "closet", "儲藏", "储藏", "庫房")),
    ("laundry", ("laundry", "utility", "洗衣", "家事間")),
)


def room_type_option(room_type: str) -> dict[str, str]:
    """回傳可公開給 API／前端的房型選項；未知值一律退回 other。"""
    return dict(_ROOM_TYPE_BY_VALUE.get(room_type, _ROOM_TYPE_BY_VALUE["other"]))


def normalize_room_type(label: object, kind: object = None) -> dict[str, str]:
    """把中英文自由文字標籤收斂成穩定房型枚舉。"""
    text = re.sub(r"\s+", " ", str(label or "").strip()).casefold()
    for room_type, tokens in _ROOM_TOKENS:
        if any(token.casefold() in text for token in tokens):
            return room_type_option(room_type)
    if str(kind or "") == "outdoor":
        return room_type_option("balcony")
    if str(kind or "") == "circulation":
        return room_type_option("corridor")
    if str(kind or "") == "living":
        return room_type_option("living_room")
    return room_type_option("other")


def _polygon_from_record(record: dict[str, Any]) -> Polygon | None:
    exterior = record.get("exterior") or []
    if len(exterior) < 3:
        return None
    try:
        polygon = Polygon(
            exterior,
            [hole for hole in (record.get("holes") or []) if len(hole) >= 3],
        )
    except (TypeError, ValueError):
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        return None
    if polygon.geom_type != "Polygon":
        polygon = max(polygon.geoms, key=lambda geom: geom.area, default=None)
    return polygon if polygon is not None and not polygon.is_empty else None


def _pieces(geometry, min_area_m2: float) -> list[Polygon]:
    geoms = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    return [
        geom
        for geom in geoms
        if geom.geom_type == "Polygon" and not geom.is_empty and geom.area >= min_area_m2
    ]


def _free_space(floorplan: dict[str, Any], min_area_m2: float) -> list[Polygon]:
    bbox = floorplan.get("bbox") or {}
    try:
        boundary = box(
            float(bbox["minx"]),
            float(bbox["minz"]),
            float(bbox["maxx"]),
            float(bbox["maxz"]),
        )
    except (KeyError, TypeError, ValueError):
        return []
    if boundary.is_empty or boundary.area <= 0:
        return []

    solids = [
        polygon
        for record in (floorplan.get("wall_polys") or [])
        if (polygon := _polygon_from_record(record)) is not None
    ]
    if not solids:
        return []
    wall_mass = unary_union(solids)
    raw_free = boundary.difference(wall_mass)
    raw_pieces = _pieces(raw_free, min_area_m2)

    # CAD 的門洞會讓相鄰房間在拓樸上連成同一塊。用數個保守半徑補上約
    # 0.75~1.3m 的牆端缺口，選出房間數最多且仍保留至少 65% 自由面積的結果。
    # 無 WALL 圖層時 parser 會把家具線也當牆，此時不可閉合，避免把家具切成假房。
    raw_area = sum(piece.area for piece in raw_pieces)
    candidates = [raw_pieces]
    if not floorplan.get("fallback_all_walls"):
        base_radius = max(float(floorplan.get("wall_thickness") or 0.18) * 2.1, 0.38)
        for close_radius in (base_radius, max(base_radius, 0.45), 0.55, 0.65):
            closed_mass = wall_mass.buffer(
                close_radius,
                cap_style=3,
                join_style=2,
            ).buffer(-close_radius, cap_style=3, join_style=2)
            closed_free = boundary.difference(closed_mass)
            closed_pieces = _pieces(closed_free, min_area_m2)
            closed_area = sum(piece.area for piece in closed_pieces)
            if closed_area >= raw_area * 0.65:
                candidates.append(closed_pieces)
    return max(
        candidates,
        key=lambda items: (len(items), sum(piece.area for piece in items)),
    )


def _stable_room_id(polygon: Polygon) -> str:
    centroid = polygon.representative_point()
    signature = f"{centroid.x:.2f}:{centroid.y:.2f}:{polygon.area:.2f}"
    return f"room-{hashlib.sha1(signature.encode('utf-8')).hexdigest()[:10]}"


def _ring(coords) -> list[list[float]]:
    return [[round(float(x), 3), round(float(z), 3)] for x, z in coords]


def _text_suggestion(polygon: Polygon, texts: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = []
    for text in texts:
        try:
            point = Point(float(text["x"]), float(text["z"]))
        except (KeyError, TypeError, ValueError):
            continue
        if polygon.covers(point):
            option = normalize_room_type(text.get("text"))
            if option["value"] != "other":
                matches.append((str(text.get("text") or ""), option))
    if not matches:
        return None
    original, option = max(matches, key=lambda item: len(item[0]))
    return {
        **option,
        "label": original[:80],
        "label_source": "dxf_text",
        "confidence": 0.95,
    }


def _suggestion_polygon(suggestion: dict[str, Any]) -> Polygon | None:
    values = suggestion.get("bbox")
    if not (isinstance(values, list) and len(values) == 4):
        return None
    try:
        x0, z0, x1, z1 = (float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x0, z0, x1, z1)):
        return None
    minx, maxx = sorted((x0, x1))
    minz, maxz = sorted((z0, z1))
    return box(minx, minz, maxx, maxz) if minx < maxx and minz < maxz else None


def _ai_suggestion(
    polygon: Polygon,
    suggestions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for suggestion in suggestions:
        suggested_polygon = _suggestion_polygon(suggestion)
        if suggested_polygon is None:
            continue
        overlap = polygon.intersection(suggested_polygon).area
        score = overlap / min(polygon.area, suggested_polygon.area) if overlap > 0 else 0.0
        if score < 0.15 and not polygon.covers(suggested_polygon.centroid):
            continue
        if best is None or score > best[0]:
            best = (score, suggestion)
    if best is None:
        return None
    score, suggestion = best
    option = normalize_room_type(suggestion.get("label_zh") or suggestion.get("label"), suggestion.get("kind"))
    return {
        **option,
        "label": str(suggestion.get("label") or option["label_zh"])[:80],
        "label_source": "ai_suggestion",
        "confidence": round(min(0.9, max(0.45, 0.55 + score * 0.35)), 2),
        "ai_evidence": str(suggestion.get("evidence") or "")[:32],
    }


def derive_room_regions(
    floorplan: dict[str, Any],
    *,
    min_area_m2: float = 1.0,
) -> list[dict[str, Any]]:
    """從牆體推導房間，並附加可人工確認的語意建議。

    ``floorplan['texts']`` 來自 DXF TEXT/MTEXT；``floorplan['rooms']`` 是
    OpenRouter 的 bbox 建議。DXF 明示文字優先於 AI，未命中的區域保留為 other。
    """
    regions = []
    texts = floorplan.get("texts") or []
    suggestions = floorplan.get("rooms") or []
    for polygon in sorted(_free_space(floorplan, min_area_m2), key=lambda item: (-item.area, item.centroid.x, item.centroid.y)):
        representative = polygon.representative_point()
        semantic = (
            _text_suggestion(polygon, texts)
            or _ai_suggestion(polygon, suggestions)
            or {
                **room_type_option("other"),
                "label": "未分類空間",
                "label_source": "geometry",
                "confidence": 0.35,
            }
        )
        semantic = dict(semantic)
        semantic["room_type"] = semantic.pop("value")
        regions.append(
            {
                "room_id": _stable_room_id(polygon),
                "exterior": _ring(polygon.exterior.coords),
                "holes": [_ring(ring.coords) for ring in polygon.interiors],
                "area_m2": round(polygon.area, 2),
                "centroid": {
                    "x": round(representative.x, 3),
                    "z": round(representative.y, 3),
                },
                **semantic,
                "confirmed": False,
            }
        )
    return regions


def attach_room_regions(floorplan: dict[str, Any]) -> list[dict[str, Any]]:
    """原地附加 room_regions 與 stats，供辨識 API 共用。"""
    regions = derive_room_regions(floorplan)
    floorplan["room_regions"] = regions
    stats = floorplan.setdefault("stats", {})
    stats["rooms"] = len(regions)
    return regions
