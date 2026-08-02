"""場景 payload ↔ 柵格擺位引擎的轉接層。

新引擎(`docs/擺位計算邏輯.md`)用自己的 kind 語彙與世界座標;本 repo 的 payload
用 ``normalized_type`` 與「房間中心原點」。轉換全部集中在這裡,兩邊各自不必知道
對方的慣例。

單位:兩邊都是**公分**,只差原點(引擎角落原點 / payload 房間中心原點)。
"""
from __future__ import annotations

from typing import Any, Sequence

from ..agent.knowledge import family_of
from .layout_model import Placement, RoomContext, Template, polygon_centroid, room_edges
from .raster import build_occupancy

Point = tuple[float, float]

# ── 族系(repo,連字號)→ 規格 kind(底線)────────────────────────────
KIND_OF_FAMILY: dict[str, str] = {
    "sofa": "sofa",
    "bed": "bed",
    "bedside-table": "nightstand",
    "coffee-table": "coffee_table",
    "tv-bench": "tv",
    "dining-table": "dining_table",
    "dining-chair": "dining_chair",
    "office-chair": "office_chair",
    "desk": "desk",
    "wardrobe": "wardrobe",
    "dressing-table": "dressing_table",
    "large-medium-rug": "rug",
    "runner-small-rug": "rug",
    "storage-cabinet": "cabinet_low",
    "cabinet": "cabinet_low",
    "sideboard": "cabinet_low",
    "chests-of-drawer": "cabinet_low",
    "appliance-cabinet": "cabinet_low",
    "bathroom-vanity": "cabinet_low",
    "mirror-cabinet": "cabinet_low",
}

# ── 房型標籤 → 規格 RULES 的鍵 ──────────────────────────────────────
LABEL_OF_ROOM_TYPE: dict[str, str] = {
    "living_room": "living",
    "living": "living",
    "客廳": "living",
    "bedroom": "bedroom",
    "臥室": "bedroom",
    "主臥": "bedroom",
    "次臥": "bedroom",
    "dining": "dining",
    "dining_room": "dining",
    "餐廳": "dining",
}


def kind_of(normalized_type: str | None) -> str:
    """``normalized_type`` → 規格 kind;未知類型走泛用件(原樣返回族系)。"""
    family = family_of(normalized_type)
    return KIND_OF_FAMILY.get(family, family)


def rule_label(room_type: str | None, label: str | None = None) -> str:
    """房型 → 規格 RULES 的鍵;對不上就回 ``default``(無房型規則,全走剩件分流)。"""
    for value in (room_type, label):
        key = str(value or "").strip()
        if key in LABEL_OF_ROOM_TYPE:
            return LABEL_OF_ROOM_TYPE[key]
    return "default"


def templates_from_items(items: Sequence[dict[str, Any]]) -> tuple[list[Template], dict[str, list[int]]]:
    """payload items → 規格 Template(同 kind 合併為一筆 count)。

    回傳 ``(templates, kind → 原始 items 索引清單)``,索引清單供擺位結果對位回填。
    順序即 items 首次出現順序 —— 規格 §12 第 3 點:選件順序即擺放順序。
    """
    order: list[str] = []
    by_kind: dict[str, list[int]] = {}
    spec: dict[str, dict[str, float | str]] = {}
    for index, item in enumerate(items):
        kind = kind_of(item.get("normalized_type"))
        if kind not in by_kind:
            by_kind[kind] = []
            order.append(kind)
            size = item.get("size_cm") or {}
            spec[kind] = {
                "w": float(size.get("width") or 120.0),
                "d": float(size.get("depth") or 60.0),
                "height": float(size.get("height") or 0.0),
                "name": str(item.get("name_zh_raw") or item.get("furniture_id") or kind),
            }
        by_kind[kind].append(index)

    templates = [
        Template(
            kind=kind,
            w=float(spec[kind]["w"]),
            d=float(spec[kind]["d"]),
            height=float(spec[kind]["height"]),
            count=len(by_kind[kind]),
            name=str(spec[kind]["name"]),
        )
        for kind in order
    ]
    return templates, by_kind


def _segments(raw: Sequence[Any], half_w: float, half_d: float) -> list[tuple[float, float, float, float]]:
    """payload 的 ``{"start": {...}, "end": {...}}`` 或 4-tuple → 角落原點線段。"""
    out: list[tuple[float, float, float, float]] = []
    for seg in raw or ():
        if isinstance(seg, dict):
            start, end = seg.get("start") or {}, seg.get("end") or {}
            try:
                out.append((
                    float(start["x"]) + half_w, float(start["z"]) + half_d,
                    float(end["x"]) + half_w, float(end["z"]) + half_d,
                ))
            except (KeyError, TypeError, ValueError):
                continue
        elif len(seg) >= 4:
            out.append((float(seg[0]), float(seg[1]), float(seg[2]), float(seg[3])))
    return out


def build_context(
    room_width_cm: float,
    room_depth_cm: float,
    *,
    polygon: Sequence[Point] | None = None,
    wall_polygons: Sequence[Sequence[Point]] = (),
    doors: Sequence[Any] = (),
    windows: Sequence[Any] = (),
    room_type: str | None = None,
    room_id: str = "room",
    passages: Sequence[Any] = (),
) -> RoomContext:
    """組出一間房的 :class:`RoomContext`(角落原點公分)。

    ``polygon`` 缺席時退回房間矩形 —— 手動矩形模式沒有房間環。
    """
    from .constraints import blocked_masks

    half_w, half_d = room_width_cm / 2, room_depth_cm / 2
    ring = list(polygon) if polygon else [
        (0.0, 0.0), (room_width_cm, 0.0), (room_width_cm, room_depth_cm), (0.0, room_depth_cm),
    ]
    plan = {
        "bbox": [
            min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring),
        ],
        "wall_polygons": [list(w) for w in wall_polygons],
        "walls": [],
        "doors": _segments(doors, half_w, half_d),
        "windows": _segments(windows, half_w, half_d),
    }
    grid = build_occupancy(plan)
    masks = blocked_masks(
        grid,
        ring,
        doors=plan["doors"],
        windows=plan["windows"],
        passages=_segments(passages, half_w, half_d),
    )
    return RoomContext(
        grid=grid,
        masks=masks,
        edges=room_edges(ring),
        centroid=polygon_centroid(ring),
        room_id=room_id,
        label=rule_label(room_type),
    )


def placement_to_payload(
    placement: Placement,
    room_width_cm: float,
    room_depth_cm: float,
) -> dict[str, float]:
    """引擎角落原點 → payload 房間中心原點(公分)。"""
    return {
        "x": round(placement.cx - room_width_cm / 2, 2),
        "z": round(placement.cy - room_depth_cm / 2, 2),
        "rotation_y_deg": round(placement.rotation_deg % 360, 2),
    }
