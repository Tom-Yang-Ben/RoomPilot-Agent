from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
import httpx


PROJECT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_DIR / "backend" / "server" / "static"
GENERATED_DIR = STATIC_DIR / "generated"
LOG_PATH = PROJECT_DIR / ".tmp" / "render-provider.log"


def _build_log_handler(path: Path = LOG_PATH) -> logging.Handler:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return logging.FileHandler(path, encoding="utf-8")
    except OSError:
        return logging.StreamHandler()


logger = logging.getLogger("roompilot.render_provider")
if not logger.handlers:
    handler = _build_log_handler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(title="RoomPilot image render provider")

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GEMINI_IMAGE_MODEL = "google/gemini-3.1-flash-image"


def _openrouter_error_detail(status_code: int) -> str:
    return {
        401: "openrouter_authentication_failed",
        402: "openrouter_payment_required",
        403: "openrouter_model_access_denied",
        429: "openrouter_rate_limited",
    }.get(status_code, f"openrouter_http_{status_code}")


def _first_nonempty_env_value(name: str) -> str:
    deployed = (os.getenv(name) or "").strip()
    if deployed:
        return deployed
    try:
        lines = (PROJECT_DIR / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    prefix = f"{name}="
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        value = stripped[len(prefix) :].strip().strip("\"'")
        if value:
            return value
    return ""


def _decode_reference_image(data_url: Any) -> bytes:
    value = str(data_url or "")
    if not value.startswith("data:image/") or "," not in value:
        raise ValueError("reference_image_required")
    try:
        return base64.b64decode(value.split(",", 1)[1], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("reference_image_invalid") from exc


def _gemini_image_model() -> str:
    model = (
        _first_nonempty_env_value("ROOMPILOT_GEMINI_IMAGE_MODEL")
        or DEFAULT_GEMINI_IMAGE_MODEL
    )
    normalized = model.lower()
    if not normalized.startswith("google/") or "gemini" not in normalized or "image" not in normalized:
        raise ValueError("gemini_image_model_required")
    return model


def _reference_data_url(reference_png: bytes) -> str:
    encoded = base64.b64encode(reference_png).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _openrouter_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    referer = _first_nonempty_env_value("ROOMPILOT_OPENROUTER_HTTP_REFERER")
    app_name = _first_nonempty_env_value("ROOMPILOT_OPENROUTER_APP_NAME") or "RoomPilot"
    if referer:
        headers["HTTP-Referer"] = referer
    if app_name:
        headers["X-Title"] = app_name
    return headers


def _style_pack(payload: dict[str, Any], style_card_id: str) -> dict[str, Any]:
    for item in payload.get("style_packs") or []:
        if str(item.get("card_id") or "") == style_card_id:
            return item
    return {"card_id": style_card_id, "name": style_card_id}


def _room_context(payload: dict[str, Any]) -> str:
    views = payload.get("room_views") or []
    room_ids = {str(item.get("room_id") or "") for item in views if isinstance(item, dict)}
    rooms = []
    for room in (payload.get("agent_generation_handoff") or {}).get("rooms") or []:
        if not room_ids or str(room.get("room_id") or "") in room_ids:
            rooms.append(room)
    return str(rooms)[:12000]


def _prompt(payload: dict[str, Any], style_pack: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "")
    brief = payload.get("render_brief") or {}
    requirements = payload.get("requirements") or {}
    return (
        "Edit the supplied RoomPilot 3D reference into a photorealistic interior design image. "
        "The reference is authoritative: preserve the exact camera, room size, wall geometry, "
        "doors, windows, openings, fixed structures, furniture count, furniture identity and "
        "furniture positions. Never add, remove, move or resize architectural elements. "
        "Never expand the room beyond the visible boundary. Locked furniture must remain visually "
        "recognizable. Replace only the simple preview shading with realistic PBR materials, natural "
        "lighting and detailed finishes. Do not draw labels, numbers, plans, captions or UI. "
        f"Task mode: {mode}. Selected style card: {style_pack}. "
        f"Confirmed room context: {_room_context(payload)}. "
        f"Questionnaire requirements: {str(requirements)[:12000]}. "
        f"User render notes: {str(brief.get('user_notes') or '')[:2000]}."
    )


async def _generate_variant(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    reference_png: bytes,
    style_card_id: str,
) -> dict[str, Any]:
    style_pack = _style_pack(payload, style_card_id)
    job_id = uuid4().hex
    logger.info(
        "generation_started project=%s mode=%s style=%s job=%s",
        payload.get("project_id"),
        payload.get("mode"),
        style_card_id,
        job_id,
    )
    endpoint = (
        _first_nonempty_env_value("ROOMPILOT_OPENROUTER_BASE_URL")
        or DEFAULT_OPENROUTER_BASE_URL
    ).rstrip("/") + "/images"
    result = await client.post(
        endpoint,
        json={
            "model": _gemini_image_model(),
            "prompt": _prompt(payload, style_pack),
            "input_references": [
                {
                    "type": "image_url",
                    "image_url": {"url": _reference_data_url(reference_png)},
                }
            ],
        },
    )
    result.raise_for_status()
    response_payload = result.json()
    images = response_payload.get("data") if isinstance(response_payload, dict) else None
    image_data = images[0].get("b64_json") if isinstance(images, list) and images else None
    if not image_data:
        raise RuntimeError("image_provider_returned_no_image")
    project_id = str(payload.get("project_id") or "project")
    output_dir = GENERATED_DIR / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.png"
    output_path.write_bytes(base64.b64decode(image_data))
    logger.info("generation_completed job=%s bytes=%s", job_id, output_path.stat().st_size)
    public_base = _first_nonempty_env_value("ROOMPILOT_PUBLIC_BASE_URL") or "http://127.0.0.1:8047"
    room_views = payload.get("room_views") or []
    room_id = room_views[0].get("room_id") if len(room_views) == 1 else None
    return {
        "job_id": job_id,
        "mode": payload.get("mode"),
        "status": "completed",
        "style_card_id": style_card_id,
        "label": style_pack.get("name") or style_card_id,
        "room_id": room_id,
        "preview_url": f"{public_base.rstrip('/')}/static/generated/{project_id}/{job_id}.png",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        model = _gemini_image_model()
        model_valid = True
    except ValueError:
        model = _first_nonempty_env_value("ROOMPILOT_GEMINI_IMAGE_MODEL")
        model_valid = False
    return {
        "ok": True,
        "provider": "openrouter_gemini",
        "configured": bool(_first_nonempty_env_value("OPENROUTER_API_KEY")) and model_valid,
        "model": model,
    }


@app.post("/")
async def render(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    expected_token = _first_nonempty_env_value("ROOMPILOT_RENDER_PROVIDER_TOKEN")
    if expected_token and request.headers.get("Authorization") != f"Bearer {expected_token}":
        raise HTTPException(status_code=401, detail="invalid_provider_token")
    api_key = _first_nonempty_env_value("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="openrouter_api_key_not_configured")
    try:
        _gemini_image_model()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        reference_png = _decode_reference_image(payload.get("reference_png_data_url"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    style_card_ids = [str(item) for item in payload.get("style_card_ids") or [] if str(item)]
    if not style_card_ids:
        raise HTTPException(status_code=422, detail="style_card_ids_required")
    try:
        async with httpx.AsyncClient(
            headers=_openrouter_headers(api_key),
            timeout=httpx.Timeout(300.0),
        ) as client:
            # Keep requests sequential so three palette variants do not trip provider rate limits.
            jobs = []
            for style_card_id in style_card_ids:
                jobs.append(
                    await _generate_variant(client, payload, reference_png, style_card_id)
                )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.exception(
            "generation_rejected project=%s mode=%s status=%s",
            payload.get("project_id"),
            payload.get("mode"),
            status_code,
        )
        raise HTTPException(
            status_code=status_code,
            detail=_openrouter_error_detail(status_code),
        ) from exc
    except httpx.RequestError as exc:
        logger.exception(
            "generation_unreachable project=%s mode=%s error_type=%s",
            payload.get("project_id"),
            payload.get("mode"),
            type(exc).__name__,
        )
        raise HTTPException(status_code=503, detail="openrouter_unreachable") from exc
    except Exception as exc:
        logger.exception(
            "generation_failed project=%s mode=%s error_type=%s",
            payload.get("project_id"),
            payload.get("mode"),
            type(exc).__name__,
        )
        raise HTTPException(status_code=502, detail=f"image_generation_failed:{type(exc).__name__}") from exc
    return {
        "request_id": payload.get("request_id") or uuid4().hex,
        "provider": "openrouter_gemini",
        "model": _gemini_image_model(),
        "jobs": jobs,
    }
