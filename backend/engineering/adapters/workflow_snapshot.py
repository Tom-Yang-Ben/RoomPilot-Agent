"""WorkflowSnapshotAdapter：既有 ProjectStore workflow state → ProjectSnapshot(draft)。

資料來源是前端 scene_v2 保存的 workflow_json（欄位對照見
docs/engineering/EXISTING_FIELD_MAPPING.md）。UI 欄位改名時只改這個檔案，
工程契約（contracts.py）不跟著變。

現有欄位 → ProjectSnapshot 對照（重點）：
- space_confirmation.rooms[].id/label/type/polygon_cm → rooms[].room_id/name/room_type + geometry(外接框)
- confirmed_floorplan.floorplan.room_height_cm       → geometry.height_m
- space_confirmation.structures.doors/windows        → geometry.opening_area_m2（段長×高）
- requirements.roomRequirementModel...surfaces       → rooms[].materials（逐房為準，
  查型錄換成受控詞彙；沒有逐房選擇才退回 globalFinishes）
- configuration.furniture[]                         → rooms[].furniture（轉房間座標）
- proposal_review.jobs / ProjectStore renders        → rooms[].renders
"""
from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..contracts import (
    FurniturePlacement,
    MaterialSelection,
    ProjectSnapshot,
    RenderReference,
    RoomGeometry,
    RoomSnapshot,
)


# 依既有 2D 家具 type 推斷基本設備需求；僅為需求草案，實際點位仍由專業確認。
_NEEDS_BY_TYPE: dict[str, dict[str, bool]] = {
    "television": {"power": True},
    "tv-bench": {"power": True},
    "refrigerator": {"power": True},
    "washer": {"power": True, "water": True, "drain": True},
    "dryer": {"power": True},
    "air-conditioner": {"power": True},
    "desk": {"power": True},
    "floor-lamp": {"power": True},
    "table-lamp": {"power": True},
    "appliance-cabinet": {"power": True},
    "bathroom-vanity": {"water": True, "drain": True},
    "water-heater": {"power": True, "water": True},
}

_DEFAULT_DOOR_HEIGHT_CM = 210.0
_DEFAULT_WINDOW_HEIGHT_CM = 120.0
_DEFAULT_ROOM_HEIGHT_CM = 270.0


def _polygon_bbox(polygon: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs = [float(point.get("x", 0)) for point in polygon]
    ys = [float(point.get("y", 0)) for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _point_in_polygon(x: float, y: float, polygon: list[dict[str, Any]]) -> bool:
    inside = False
    count = len(polygon)
    for index in range(count):
        x1 = float(polygon[index].get("x", 0))
        y1 = float(polygon[index].get("y", 0))
        x2 = float(polygon[(index + 1) % count].get("x", 0))
        y2 = float(polygon[(index + 1) % count].get("y", 0))
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def _segment_length_cm(item: dict[str, Any]) -> float:
    start = item.get("start") or {}
    end = item.get("end") or {}
    return math.hypot(
        float(end.get("x", 0)) - float(start.get("x", 0)),
        float(end.get("y", 0)) - float(start.get("y", 0)),
    )


def _segment_midpoint(item: dict[str, Any]) -> tuple[float, float]:
    start = item.get("start") or {}
    end = item.get("end") or {}
    return (
        (float(start.get("x", 0)) + float(end.get("x", 0))) / 2,
        (float(start.get("y", 0)) + float(end.get("y", 0))) / 2,
    )


def _opening_area_m2(room_polygon: list[dict[str, Any]], structures: dict[str, Any]) -> float:
    total_cm2 = 0.0
    for kind, default_height in (
        ("doors", _DEFAULT_DOOR_HEIGHT_CM),
        ("windows", _DEFAULT_WINDOW_HEIGHT_CM),
    ):
        for item in structures.get(kind) or []:
            mid_x, mid_y = _segment_midpoint(item)
            if not _point_in_polygon(mid_x, mid_y, room_polygon):
                # 開口常落在房間邊線上；用小幅膨脹的外接框做第二次判斷。
                min_x, min_y, max_x, max_y = _polygon_bbox(room_polygon)
                margin = 20.0
                if not (
                    min_x - margin <= mid_x <= max_x + margin
                    and min_y - margin <= mid_y <= max_y + margin
                ):
                    continue
            length_cm = _segment_length_cm(item)
            height_cm = float(item.get("height_cm") or default_height)
            total_cm2 += length_cm * height_cm
    return round(total_cm2 / 10000.0, 4)


@lru_cache(maxsize=1)
def _surface_vocabulary() -> dict[str, str]:
    """型錄 surface_id → 受控詞彙（``category`` + ``material_group``）。

    工項對照吃的是子字串比對，直接拿 surface_id 去比對會出事：
    ``wall_json_ambientcg_wall_wood_wall_paintedwood007c`` 是木質牆板，卻因為 id 裡
    有 "paint" 而被算成油漆（單價差三倍以上）。型錄自己有受控詞彙，改比對它。
    """
    path = Path(__file__).resolve().parents[2] / "catalog" / "data" / "surface_catalog.json"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        str(item["surface_id"]): f"{item.get('category') or ''} {item.get('material_group') or ''}".strip()
        for item in catalog.get("surfaces") or []
        if item.get("surface_id")
    }


def _room_surfaces(room_id: str, requirements: dict[str, Any]) -> dict[str, Any]:
    """第 6 步逐房材質；問卷的全域選擇只是它的預設值。"""
    model = requirements.get("roomRequirementModel") or {}
    entry = (model.get("roomRequirements") or {}).get(room_id) or {}
    return entry.get("surfaces") or {}


def _materials_for_room(
    room_id: str, finishes: dict[str, Any], requirements: dict[str, Any]
) -> tuple[list[MaterialSelection], bool]:
    """回傳該房材料與「是否退回全屋選項」。"""
    surfaces = _room_surfaces(room_id, requirements)
    specs = (
        ("floor", "floor", "floorMaterial", "floorColor"),
        ("wall", "wallDefault", "wallMaterial", "wallColor"),
        ("ceiling", "ceiling", "ceilingMaterial", "ceilingColor"),
    )
    vocabulary = _surface_vocabulary()
    materials: list[MaterialSelection] = []
    used_fallback = False
    for part, surface_key, finish_key, color_key in specs:
        selection = surfaces.get(surface_key) or {}
        surface_id = str(selection.get("materialId") or "").strip()
        color = selection.get("color")
        if not surface_id:
            surface_id = str(finishes.get(finish_key) or "").strip()
            color = finishes.get(color_key)
            used_fallback = used_fallback or bool(surface_id)
        if not surface_id:
            continue
        materials.append(
            MaterialSelection(
                material_id=surface_id,
                part=part,  # type: ignore[arg-type]
                # 比對用受控詞彙；查不到型錄（例如天花的 flat-paint）才退回 id 本身。
                name=vocabulary.get(surface_id) or surface_id,
                description=str(color) if color else None,
                waste_rate=0.05,
            )
        )
    return materials, used_fallback


def _needs_flags(furniture_type: str) -> dict[str, bool]:
    needs = _NEEDS_BY_TYPE.get(str(furniture_type).strip().lower(), {})
    return {
        "needs_power": bool(needs.get("power")),
        "needs_water": bool(needs.get("water")),
        "needs_drain": bool(needs.get("drain")),
    }


def _plan_center(rooms: list[dict[str, Any]]) -> tuple[float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for room in rooms:
        for point in room.get("polygon_cm") or []:
            xs.append(float(point.get("x", 0)))
            ys.append(float(point.get("y", 0)))
    if not xs:
        return 0.0, 0.0
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _furniture_for_room(
    room: dict[str, Any],
    furniture_items: list[dict[str, Any]],
    plan_center: tuple[float, float],
) -> list[FurniturePlacement]:
    polygon = room.get("polygon_cm") or []
    if not polygon:
        return []
    min_x, min_y, _, _ = _polygon_bbox(polygon)
    placements: list[FurniturePlacement] = []
    for item in furniture_items:
        if item.get("roomId") != room.get("id"):
            continue
        width = float(item.get("widthCm") or 0)
        depth = float(item.get("depthCm") or 0)
        height = float(item.get("heightCm") or 0)
        if width <= 0 or depth <= 0:
            continue
        # 前端 configuration furniture 座標以整張平面圖中心為原點；轉回平面座標後，
        # 再換成房間外接框左下角原點（與 backend.engine 一致）。
        plan_x = float(item.get("xCm") or 0) + plan_center[0]
        plan_y = float(item.get("yCm") or 0) + plan_center[1]
        placements.append(
            FurniturePlacement(
                furniture_id=str(item.get("id") or f"{room.get('id')}-item-{len(placements)+1}"),
                name=str(item.get("label") or item.get("type") or "未命名家具"),
                category=str(item.get("type") or "unknown"),
                width_cm=width,
                depth_cm=depth,
                height_cm=height if height > 0 else 80.0,
                quantity=1,
                x_cm=round(plan_x - min_x, 2),
                y_cm=round(plan_y - min_y, 2),
                rotation_deg=float(item.get("rotationDeg") or 0),
                unit_price=None,
                asset_url=str(item.get("iconPath")) if item.get("iconPath") else None,
                **_needs_flags(str(item.get("type") or "")),
            )
        )
    return placements


def _renders_for_room(
    room: dict[str, Any],
    jobs: list[dict[str, Any]],
    store_renders: list[dict[str, Any]],
    single_room: bool,
) -> list[RenderReference]:
    renders: list[RenderReference] = []
    room_id = str(room.get("id") or "")
    room_label = str(room.get("label") or "")
    for job in jobs:
        image_url = job.get("image_url") or job.get("output_url") or job.get("preview_url")
        if not image_url:
            continue
        bound = str(job.get("room_id") or "") == room_id or (
            room_label and str(job.get("room_label") or "") == room_label
        )
        if bound or single_room:
            renders.append(
                RenderReference(
                    render_url=str(image_url),
                    view_name=str(job.get("label") or job.get("mode") or "AI 渲染"),
                    prompt_hash=str(job.get("job_id")) if job.get("job_id") else None,
                )
            )
    if single_room:
        for record in store_renders:
            url = record.get("download_url")
            if not url:
                continue
            renders.append(
                RenderReference(
                    render_url=str(url),
                    view_name=str(record.get("style_card_id") or record.get("filename") or "專案渲染"),
                    prompt_hash=str(record.get("render_id")) if record.get("render_id") else None,
                )
            )
    # 去重
    unique: dict[str, RenderReference] = {}
    for render in renders:
        unique.setdefault(render.render_url, render)
    return list(unique.values())


def snapshot_draft_from_workflow(
    project_id: str,
    revision: str,
    workflow: dict[str, Any],
    *,
    region: str,
    pricing_basis_date: date,
    store_renders: list[dict[str, Any]] | None = None,
) -> ProjectSnapshot:
    """把既有 workflow state 轉成 draft ProjectSnapshot。

    只讀取欄位，不修改 workflow；資料缺漏時記入 assumptions 而不是猜數字。
    """
    store_renders = store_renders or []
    assumptions: list[str] = []

    space = workflow.get("space_confirmation") or {}
    rooms_raw = [
        room for room in (space.get("rooms") or []) if room.get("polygon_cm")
    ]
    if not rooms_raw:
        raise ValueError("WORKFLOW_HAS_NO_ROOMS")

    confirmed_rooms = [room for room in rooms_raw if room.get("confirmed")]
    if confirmed_rooms:
        rooms_raw = confirmed_rooms
    else:
        assumptions.append("空間尚未全部確認，Snapshot 以目前辨識結果為準。")

    structures = space.get("structures") or {}
    floorplan = (workflow.get("confirmed_floorplan") or {}).get("floorplan") or {}
    room_height_cm = float(floorplan.get("room_height_cm") or 0)
    if room_height_cm <= 0:
        room_height_cm = _DEFAULT_ROOM_HEIGHT_CM
        assumptions.append("尚未確認樓高，暫以 270 cm 計算；現場複丈後請更新。")

    requirements = workflow.get("requirements") or {}
    requirement_model = requirements.get("roomRequirementModel") or {}
    finishes = requirement_model.get("globalFinishes") or {}

    configuration = workflow.get("configuration") or {}
    furniture_items = list(configuration.get("furniture") or [])
    proposal = workflow.get("proposal_review") or {}
    jobs = list(proposal.get("jobs") or [])
    plan_center = _plan_center(rooms_raw)
    single_room = len(rooms_raw) == 1
    if not single_room and store_renders:
        assumptions.append("專案渲染圖未綁定房間，僅列出已綁定房間的生圖。")

    style = finishes.get("stylePackId") or None

    rooms: list[RoomSnapshot] = []
    finishes_fallback = False
    for room in rooms_raw:
        polygon = room.get("polygon_cm") or []
        min_x, min_y, max_x, max_y = _polygon_bbox(polygon)
        length_m = round((max_x - min_x) / 100.0, 4)
        width_m = round((max_y - min_y) / 100.0, 4)
        if length_m <= 0 or width_m <= 0:
            continue
        room_id = str(room.get("id"))
        materials, used_fallback = _materials_for_room(room_id, finishes, requirements)
        finishes_fallback = finishes_fallback or used_fallback
        rooms.append(
            RoomSnapshot(
                room_id=room_id,
                name=str(room.get("label") or room_id),
                room_type=str(room.get("type") or "default"),
                style=str(style) if style else None,
                geometry=RoomGeometry(
                    length_m=length_m,
                    width_m=width_m,
                    height_m=round(room_height_cm / 100.0, 4),
                    opening_area_m2=_opening_area_m2(polygon, structures),
                ),
                layout_json={
                    "polygon_cm": polygon,
                    "coordinate_unit": "cm",
                    "source": "scene_v2.space_confirmation",
                },
                materials=materials,
                furniture=_furniture_for_room(room, furniture_items, plan_center),
                mep_points=[],
                renders=_renders_for_room(room, jobs, store_renders, single_room),
            )
        )

    if not rooms:
        raise ValueError("WORKFLOW_HAS_NO_ROOMS")

    if not any(room.materials for room in rooms):
        assumptions.append("尚未選擇牆/地/天花材料，估價將缺少對應裝修工項。")
    elif finishes_fallback:
        assumptions.append("部分房間沒有逐房材質選擇，已沿用問卷的全屋選項。")
    assumptions.append("房間幾何以確認多邊形的外接矩形計算，非矩形空間會高估面積。")
    assumptions.append("水電點位為需求草案；迴路、線徑、管徑與容量需由專業確認。")

    return ProjectSnapshot(
        project_id=project_id,
        revision=revision,
        approval_status="draft",
        region=region,
        pricing_basis_date=pricing_basis_date,
        rooms=rooms,
        assumptions=assumptions,
    )
