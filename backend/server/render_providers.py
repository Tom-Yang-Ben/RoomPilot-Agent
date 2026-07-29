"""內建生圖供應者：把第 8 步接上真實影像生成 API（2026-07 盤點第 10 項修復）。

盤點結論：遠端渲染契約期待「自訂非同步任務服務」，但真實生圖 API 全是
同步回圖，中間缺一整層轉接——prompt 組裝器、格式轉換、回圖入庫、狀態回讀
四段全空。本模組把轉接層直接內建在 FastAPI：

- 供應者走 OpenRouter（**沿用團隊既有的 OPENROUTER_API_KEY**，不需新金鑰），
  模型預設 ``google/gemini-2.5-flash-image``，可用 ROOMPILOT_RENDER_IMAGE_MODEL
  覆蓋；ROOMPILOT_RENDER_IMAGE_DISABLED=1 可整段停用。
- 同步生成：POST render-jobs 會等生成完成（每張約 10~30 秒）；回圖直接以
  ``provider="openrouter_image"`` 入庫 PROJECT_STORE，與第 9 項瀏覽器截圖共用
  同一條成果清單與下載端點。
- 回傳 jobs 帶 ``status="completed"`` 與 ``preview_url``——前端結果卡片
  （scene_v2.js renderPaletteResults）讀首回網址即顯示，「無輪詢」的既有
  限制對同步完成的任務不構成問題。
- 舊契約完整保留：ROOMPILOT_RENDER_PROVIDER_URL 有值時優先走原轉送路徑。

隱私與鎖定沿用 render_service.prepare_render_payload（去識別化欄位、
相機與模式驗證），不重做。
"""
from __future__ import annotations

import base64
import binascii
import os
from typing import Any

import httpx

from .render_service import (
    RenderProviderRejected,
    RenderProviderUnavailable,
    _render_timeout_seconds,
    prepare_render_payload,
)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"
MAX_REFERENCE_BYTES = 20 * 1024 * 1024


def direct_image_provider_available() -> bool:
    """OPENROUTER_API_KEY 存在、未停用、且沒有設定舊遠端 URL 時啟用。"""
    if os.getenv("ROOMPILOT_RENDER_IMAGE_DISABLED", "").strip() == "1":
        return False
    if os.getenv("ROOMPILOT_RENDER_PROVIDER_URL", "").strip():
        return False  # 舊契約優先，行為向下相容
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def direct_image_provider_status() -> dict[str, Any]:
    model = os.getenv("ROOMPILOT_RENDER_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
    return {
        "configured": True,
        "provider": f"openrouter:{model}",
        "has_token": True,
    }


def _style_pack_for(prepared: dict[str, Any], card_id: str) -> dict[str, Any]:
    for pack in prepared.get("style_packs") or []:
        if isinstance(pack, dict) and str(pack.get("card_id")) == str(card_id):
            return pack
    return {"card_id": card_id}


def build_render_prompt(
    prepared: dict[str, Any],
    style_pack: dict[str, Any],
    room_view: dict[str, Any] | None = None,
) -> str:
    """把結構化渲染請求組成生圖 prompt（盤點指出的「無 prompt 組裝器」缺口）。

    鎖定語言對應契約：家具、牆、地板區域與相機都是鎖定條件，供應者只能
    改材質與光線。
    """
    style_name = str(style_pack.get("name") or style_pack.get("style_label") or "現代風格")
    palette = style_pack.get("palette_hex")
    parts = [
        "你是室內設計渲染引擎。請把參考圖（瀏覽器 3D 場景截圖）重新渲染成照片級室內效果圖。",
        "硬性限制：完全保留參考圖中的房間結構、牆體、門窗開口、家具種類、數量、位置與朝向，"
        "不得新增、刪除或移動任何家具與結構；相機視角必須與參考圖一致。",
        f"設計風格：{style_name}。",
    ]
    if isinstance(palette, list) and palette:
        parts.append("主色調（hex）：" + "、".join(str(color) for color in palette[:6]) + "。")
    for key, label in (("wall", "牆面"), ("floor", "地板"), ("lighting", "燈光"), ("rendering", "渲染語言")):
        value = style_pack.get(key)
        if value:
            parts.append(f"{label}：{value}。")
    requirements = prepared.get("requirements") or {}
    household = (requirements.get("basic") or {}).get("household")
    if household:
        parts.append(f"居住情境：{household}。")
    if room_view is not None:
        room_label = str(room_view.get("room_label") or room_view.get("room_id") or "").strip()
        if room_label:
            parts.append(f"本張聚焦房間：{room_label}，以該房間視角出圖。")
    parts.append(
        "輸出：單張高品質寫實渲染圖，自然光影、真實材質質感，"
        "photorealistic interior rendering, high detail, no text, no watermark."
    )
    return "\n".join(parts)


def _reference_data_url(prepared: dict[str, Any], room_view: dict[str, Any] | None) -> str:
    candidates = []
    if room_view is not None:
        candidates.append(room_view.get("reference_png_data_url"))
    candidates.append(prepared.get("reference_png_data_url"))
    for candidate in candidates:
        value = str(candidate or "")
        if value.startswith("data:image/png;base64,"):
            encoded = value.split(",", 1)[1]
            try:
                raw = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise RenderProviderRejected("render_reference_png_invalid") from exc
            if not raw:
                raise RenderProviderRejected("render_reference_png_invalid")
            if len(raw) > MAX_REFERENCE_BYTES:
                raise RenderProviderRejected("render_reference_png_too_large")
            return value
    raise RenderProviderRejected("render_reference_png_required")


async def _post_openrouter(body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """網路呼叫縫；測試以 monkeypatch 取代，不打真實 API。"""
    timeout = max(_render_timeout_seconds(), 120.0)  # 生圖比一般轉送慢，至少 120 秒
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OPENROUTER_ENDPOINT, json=body, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RenderProviderRejected(
            f"image_provider_http_{exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RenderProviderUnavailable("image_provider_unreachable") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise RenderProviderRejected("image_provider_invalid_json") from exc


def _extract_image_png(result: dict[str, Any]) -> bytes:
    """從 OpenRouter 回應取出圖片位元組；找不到就明話拒絕。"""
    try:
        message = (result.get("choices") or [])[0].get("message") or {}
    except (IndexError, AttributeError):
        raise RenderProviderRejected("image_provider_empty_response")
    candidates: list[str] = []
    for image in message.get("images") or []:
        if isinstance(image, dict):
            url = ((image.get("image_url") or {}).get("url")) or image.get("url")
            if url:
                candidates.append(str(url))
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url")
                if url:
                    candidates.append(str(url))
    for url in candidates:
        if url.startswith("data:image/") and ";base64," in url:
            try:
                raw = base64.b64decode(url.split(",", 1)[1])
            except (binascii.Error, ValueError):
                continue
            if raw.startswith(b"\x89PNG\r\n\x1a\n"):
                return raw
    raise RenderProviderRejected("image_provider_no_image_returned")


async def _generate_one(prompt: str, reference_data_url: str) -> bytes:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    model = os.getenv("ROOMPILOT_RENDER_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    site_url = os.getenv("OPENROUTER_SITE_URL", "").strip()
    app_name = os.getenv("OPENROUTER_APP_NAME", "").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name
    body = {
        "model": model,
        "modalities": ["image", "text"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": reference_data_url}},
                ],
            }
        ],
    }
    result = await _post_openrouter(body, headers)
    return _extract_image_png(result)


async def run_direct_render_jobs(project_id: str, payload: dict[str, Any], store: Any) -> dict[str, Any]:
    """同步生成並入庫，回傳前端可直接顯示的 completed 任務清單。"""
    prepared = prepare_render_payload(payload)
    mode = prepared["mode"] if "mode" in prepared else str(payload.get("mode"))

    tasks: list[dict[str, Any]] = []
    if mode == "room_final":
        confirmed_card = str((prepared.get("locks") or {}).get("style_card_id") or
                             (prepared.get("style_card_ids") or ["unassigned"])[0])
        for room_view in prepared.get("room_views") or []:
            tasks.append({"style_card_id": confirmed_card, "room_view": room_view})
    else:
        for card_id in prepared.get("style_card_ids") or []:
            if str(card_id).strip():
                tasks.append({"style_card_id": str(card_id), "room_view": None})

    jobs: list[dict[str, Any]] = []
    for task in tasks:
        style_pack = _style_pack_for(prepared, task["style_card_id"])
        prompt = build_render_prompt(prepared, style_pack, task["room_view"])
        reference = _reference_data_url(prepared, task["room_view"])
        png = await _generate_one(prompt, reference)

        revision = int(store.get_project(project_id).get("revision") or 0)
        try:
            render, _project = store.save_render(
                project_id,
                expected_revision=revision,
                content=png,
                white_model_version=0,
                viewpoint_version=0,
                style_version=0,
                style_card_id=task["style_card_id"],
                provider="openrouter_image",
            )
        except Exception:
            # 版本競態時取最新 revision 重試一次；再失敗就明話拒絕。
            revision = int(store.get_project(project_id).get("revision") or 0)
            render, _project = store.save_render(
                project_id,
                expected_revision=revision,
                content=png,
                white_model_version=0,
                viewpoint_version=0,
                style_version=0,
                style_card_id=task["style_card_id"],
                provider="openrouter_image",
            )
        room_view = task["room_view"] or {}
        jobs.append(
            {
                "job_id": render["render_id"],
                "style_card_id": task["style_card_id"],
                "room_id": room_view.get("room_id"),
                "status": "completed",
                "preview_url": f"/api/projects/{project_id}/renders/{render['render_id']}/png",
                "image_url": f"/api/projects/{project_id}/renders/{render['render_id']}/png",
                "label": room_view.get("room_label"),
            }
        )
    return {
        "request_id": prepared.get("request_id"),
        "provider": direct_image_provider_status()["provider"],
        "jobs": jobs,
    }
