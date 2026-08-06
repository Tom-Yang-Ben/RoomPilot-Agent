from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - the server can still run without dotenv
    load_dotenv = None


PROJECT_DIR = Path(__file__).resolve().parents[2]
RENDER_ENV_KEYS = (
    "ROOMPILOT_RENDER_PROVIDER_URL",
    "ROOMPILOT_RENDER_PROVIDER_TOKEN",
    "ROOMPILOT_RENDER_PROVIDER_NAME",
    "ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS",
)
# Capture deployment-provided settings before reading a local .env file.
DEPLOY_RENDER_ENV = {key: os.getenv(key) for key in RENDER_ENV_KEYS}
if load_dotenv is not None:
    # Deployed environment values take precedence over the local development file.
    load_dotenv(PROJECT_DIR / ".env", override=False)


SUPPORTED_RENDER_MODES = {"palette_comparison", "room_final"}
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


def _first_nonempty_local_env_value(name: str) -> str:
    """Read the first usable local setting when a merged .env repeats a key.

    Environment variables supplied by deployment are handled separately and always
    win. This fallback only prevents a later blank template value in a local
    `.env` from disabling an earlier configured render provider.
    """
    env_path = PROJECT_DIR / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    prefix = f"{name}="
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix):].strip().strip('"\'')
        if value:
            return value
    return ""


def _render_setting(name: str, default: str = "") -> str:
    deployed = (DEPLOY_RENDER_ENV.get(name) or "").strip()
    if deployed:
        return deployed
    local_value = _first_nonempty_local_env_value(name)
    if local_value:
        return local_value
    return (os.getenv(name) or default).strip()


def _render_timeout_seconds() -> float:
    raw_value = _render_setting("ROOMPILOT_RENDER_PROVIDER_TIMEOUT_SECONDS", "300")
    try:
        return max(5.0, min(float(raw_value), 600.0))
    except (TypeError, ValueError):
        return 300.0


def render_provider_status() -> dict[str, Any]:
    endpoint = _render_setting("ROOMPILOT_RENDER_PROVIDER_URL")
    token = _render_setting("ROOMPILOT_RENDER_PROVIDER_TOKEN")
    provider = _render_setting("ROOMPILOT_RENDER_PROVIDER_NAME", "remote_renderer")
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


def _validate_room_views(room_views: Any) -> None:
    if not isinstance(room_views, list) or not room_views:
        raise ValueError("room_views_required")
    for item in room_views:
        if not isinstance(item, dict) or not str(item.get("room_id") or "").strip():
            raise ValueError("room_view_room_id_required")
        if not _valid_camera(item.get("camera")):
            raise ValueError("room_view_camera_required")


def _validate_configuration_snapshot(payload: dict[str, Any]) -> None:
    snapshot = payload.get("configuration_snapshot")
    if snapshot is None:
        return
    if not isinstance(snapshot, dict) or not str(snapshot.get("snapshot_id") or "").strip():
        raise ValueError("configuration_snapshot_required")
    if snapshot.get("schema_version") != 2:
        raise ValueError("configuration_snapshot_version_invalid")
    if str(snapshot.get("scene_version") or "").strip() != str(
        payload.get("scene_version") or ""
    ).strip():
        raise ValueError("configuration_snapshot_scene_version_mismatch")
    fixed_structure = snapshot.get("fixed_structure")
    if not isinstance(fixed_structure, dict):
        raise ValueError("configuration_fixed_structure_required")
    required_structure_keys = {"walls", "doors", "windows", "beams", "columns"}
    if not required_structure_keys.issubset(fixed_structure):
        raise ValueError("configuration_fixed_structure_incomplete")
    rooms = snapshot.get("rooms")
    furniture = snapshot.get("furniture")
    if not isinstance(rooms, list) or not isinstance(furniture, list):
        raise ValueError("configuration_snapshot_rooms_required")
    if payload.get("mode") == "room_final":
        master_snapshot_id = str(
            (payload.get("master_view") or {}).get("configuration_snapshot_id") or ""
        ).strip()
        if master_snapshot_id and master_snapshot_id != str(snapshot["snapshot_id"]):
            raise ValueError("configuration_snapshot_master_view_mismatch")
        expected_room_ids = {str(room.get("room_id")) for room in rooms if room.get("room_id")}
        supplied_room_ids = {
            str(view.get("room_id"))
            for view in payload.get("room_views") or []
            if isinstance(view, dict) and view.get("room_id")
        }
        if not supplied_room_ids:
            raise ValueError("room_views_required")
        if supplied_room_ids - expected_room_ids:
            raise ValueError("room_views_unknown_room")


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
    master_camera = payload.get("master_view", {}).get("camera", {})
    if not _valid_camera(master_camera):
        raise ValueError("locked_master_camera_required")
    _validate_configuration_snapshot(payload)
    if mode == "room_final":
        _validate_room_views(payload.get("room_views"))

    prepared = deepcopy(payload)
    prepared["request_id"] = str(payload.get("request_id") or uuid4().hex)
    prepared["requirements"] = _strip_private_fields(prepared.get("requirements") or {})
    prepared["render_brief"] = _strip_private_fields(prepared.get("render_brief") or {})
    prepared["agent_generation_handoff"] = _strip_private_fields(
        prepared.get("agent_generation_handoff") or {}
    )
    return prepared


async def submit_render_jobs(payload: dict[str, Any]) -> dict[str, Any]:
    status = render_provider_status()
    endpoint = _render_setting("ROOMPILOT_RENDER_PROVIDER_URL")
    if not status["configured"] or not endpoint:
        raise RenderProviderUnavailable("render_provider_not_configured")

    prepared = prepare_render_payload(payload)
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": prepared["request_id"],
        "X-RoomPilot-Scene-Version": prepared["scene_version"],
    }
    token = _render_setting("ROOMPILOT_RENDER_PROVIDER_TOKEN")
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
