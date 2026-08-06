from __future__ import annotations

import os
from copy import deepcopy
from typing import Any
from uuid import uuid4

import httpx


SUPPORTED_RENDER_MODES = {"palette_comparison", "room_final"}
# 每個請求的生圖任務上限（Codex 2026-08-04 開放項：render-jobs 無總量檢查）。
# 每張色卡／每個房間視角各觸發一次付費生圖 API；正式 UI 最多 18 張色卡、
# 房型上限 12 種，這裡取寬鬆上界——擋的是灌爆型 payload，不是正常使用。
MAX_RENDER_STYLE_CARDS = 18
MAX_RENDER_ROOM_VIEWS = 24
PRIVATE_KEYS = {
    "address",
    "email",
    "full_name",
    "fullname",
    "name",
    "phone",
    "phone_number",
    "phonenumber",
    "telephone",
}


class RenderProviderUnavailable(RuntimeError):
    pass


class RenderProviderRejected(RuntimeError):
    pass


def _render_timeout_seconds() -> float:
    raw_value = os.getenv("ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS", "60")
    try:
        return max(5.0, min(float(raw_value), 180.0))
    except (TypeError, ValueError):
        return 60.0


def render_provider_status() -> dict[str, Any]:
    endpoint = os.getenv("ROOMPILOT_RENDER_PROVIDER_URL", "").strip()
    token = os.getenv("ROOMPILOT_RENDER_PROVIDER_TOKEN", "").strip()
    provider = os.getenv("ROOMPILOT_RENDER_PROVIDER_NAME", "remote_renderer").strip()
    return {
        "configured": bool(endpoint),
        "provider": provider or "remote_renderer",
        "has_token": bool(token),
    }


def _strip_private_fields(value: Any) -> Any:
    if isinstance(value, list):
        return [_strip_private_fields(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: _strip_private_fields(item)
        for key, item in value.items()
        if str(key).strip().lower() not in PRIVATE_KEYS
    }


def _is_number_triplet(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(
            isinstance(item, int | float) and not isinstance(item, bool)
            for item in value
        )
    )


def _valid_camera(camera: Any) -> bool:
    if not isinstance(camera, dict):
        return False
    if not _is_number_triplet(camera.get("position_cm")):
        return False
    if not _is_number_triplet(camera.get("target_cm")):
        return False
    fov = camera.get("fov_deg")
    if fov is not None and (
        not isinstance(fov, int | float) or isinstance(fov, bool) or fov <= 0
    ):
        return False
    return True


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    tolerance: float = 0.01,
) -> bool:
    cross = (point[1] - start[1]) * (end[0] - start[0]) - (
        point[0] - start[0]
    ) * (end[1] - start[1])
    if abs(cross) > tolerance:
        return False
    dot = (point[0] - start[0]) * (end[0] - start[0]) + (
        point[1] - start[1]
    ) * (end[1] - start[1])
    if dot < -tolerance:
        return False
    length_squared = (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2
    return dot <= length_squared + tolerance


def _point_in_polygon(
    point: tuple[float, float], polygon: list[tuple[float, float]]
) -> bool:
    inside = False
    previous = len(polygon) - 1
    for index, end in enumerate(polygon):
        start = polygon[previous]
        if _point_on_segment(point, start, end):
            return True
        if (end[1] > point[1]) != (start[1] > point[1]):
            crossing_x = (start[0] - end[0]) * (point[1] - end[1]) / (
                start[1] - end[1]
            ) + end[0]
            if point[0] < crossing_x:
                inside = not inside
        previous = index
    return inside


def _room_view_polygon(
    scene: Any, room_id: str
) -> list[tuple[float, float]] | None:
    floorplan = scene.get("floorplan") if isinstance(scene, dict) else None
    regions = floorplan.get("room_regions") if isinstance(floorplan, dict) else None
    for region in regions or []:
        if str(region.get("room_id") or "") != room_id:
            continue
        points: list[tuple[float, float]] = []
        for point in region.get("exterior") or []:
            if isinstance(point, list | tuple) and len(point) >= 2:
                x_value, z_value = point[0], point[1]
            elif isinstance(point, dict):
                x_value, z_value = point.get("x"), point.get("z", point.get("y"))
            else:
                continue
            if isinstance(x_value, int | float) and isinstance(z_value, int | float):
                # room_regions use centered scene z; camera snapshots use world z.
                points.append((float(x_value), -float(z_value)))
        return points if len(points) >= 3 else None
    return None


def _validate_room_views(room_views: Any, scene: Any = None) -> None:
    if not isinstance(room_views, list) or not room_views:
        raise ValueError("room_views_required")
    for item in room_views:
        if not isinstance(item, dict) or not str(item.get("room_id") or "").strip():
            raise ValueError("room_view_room_id_required")
        if not _valid_camera(item.get("camera")):
            raise ValueError("room_view_camera_required")
        camera = item["camera"]
        position = camera["position_cm"]
        target = camera["target_cm"]
        if ((position[0] - target[0]) ** 2 + (position[2] - target[2]) ** 2) ** 0.5 < 40:
            raise ValueError("room_view_camera_distance_invalid")
        polygon = _room_view_polygon(scene, str(item["room_id"]))
        if polygon is None:
            continue
        if not _point_in_polygon((float(target[0]), float(target[2])), polygon):
            raise ValueError("room_view_target_outside_room")
        if not _point_in_polygon((float(position[0]), float(position[2])), polygon):
            raise ValueError("room_view_camera_outside_room")


def prepare_render_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "")
    if mode not in SUPPORTED_RENDER_MODES:
        raise ValueError("unsupported_render_mode")
    scene_version = str(payload.get("scene_version") or "").strip()
    if not scene_version:
        raise ValueError("scene_version_required")
    style_card_ids = payload.get("style_card_ids")
    if not isinstance(style_card_ids, list) or not any(
        str(item).strip() for item in style_card_ids
    ):
        raise ValueError("style_card_ids_required")
    if len([item for item in style_card_ids if str(item).strip()]) > MAX_RENDER_STYLE_CARDS:
        raise ValueError("render_style_cards_exceed_limit")
    master_camera = payload.get("master_view", {}).get("camera", {})
    if not _valid_camera(master_camera):
        raise ValueError("locked_master_camera_required")
    if mode == "room_final":
        room_views = payload.get("room_views")
        if isinstance(room_views, list) and len(room_views) > MAX_RENDER_ROOM_VIEWS:
            raise ValueError("render_room_views_exceed_limit")
        _validate_room_views(room_views, payload.get("scene"))

    prepared = deepcopy(payload)
    prepared["request_id"] = str(payload.get("request_id") or uuid4().hex)
    prepared["requirements"] = _strip_private_fields(prepared.get("requirements") or {})
    prepared["agent_generation_handoff"] = _strip_private_fields(
        prepared.get("agent_generation_handoff") or {}
    )
    return prepared


async def submit_render_jobs(payload: dict[str, Any]) -> dict[str, Any]:
    status = render_provider_status()
    endpoint = os.getenv("ROOMPILOT_RENDER_PROVIDER_URL", "").strip()
    if not status["configured"] or not endpoint:
        raise RenderProviderUnavailable("render_provider_not_configured")

    prepared = prepare_render_payload(payload)
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": prepared["request_id"],
        "X-RoomPilot-Scene-Version": prepared["scene_version"],
    }
    token = os.getenv("ROOMPILOT_RENDER_PROVIDER_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=_render_timeout_seconds()) as client:
            response = await client.post(endpoint, json=prepared, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RenderProviderRejected(
            f"render_provider_http_{exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RenderProviderUnavailable("render_provider_unreachable") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RenderProviderRejected("render_provider_invalid_json") from exc
    if not isinstance(result, dict):
        raise RenderProviderRejected("render_provider_invalid_response")
    result.setdefault("request_id", prepared["request_id"])
    result.setdefault("provider", status["provider"])
    return result
