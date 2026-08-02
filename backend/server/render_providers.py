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
import json
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

# 單張圖的家具鎖定上限。實測案子單房最多 18 件，40 件已留足餘裕；
# 真的超過時 prompt 會明寫截斷數量，不做無聲截斷。
MAX_LOCKED_FURNITURE = 40
# 家具中心距房間外框多近才算「貼牆」。
WALL_SNAP_CM = 30.0
# 價格是報價資料，不是視覺條件，不進 prompt。
_EXCLUDED_ITEM_KEYS = frozenset({"price", "price_twd", "price_ntd"})


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


def _scene_objects(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    objects = (prepared.get("scene") or {}).get("scene_objects")
    return [item for item in objects or [] if isinstance(item, dict)]


def _object_room_id(item: dict[str, Any]) -> str:
    return str(item.get("placement_room_id") or item.get("auto_decor_room_id") or "")


def _room_region(prepared: dict[str, Any], room_id: str) -> dict[str, Any] | None:
    regions = ((prepared.get("scene") or {}).get("floorplan") or {}).get("room_regions")
    for region in regions or []:
        if isinstance(region, dict) and str(region.get("room_id")) == str(room_id):
            return region
    return None


def _wall_hint(item: dict[str, Any], region: dict[str, Any] | None) -> str:
    """描述家具貼哪一面牆。

    只是把 backend/engine/ 已定案的座標翻成文字，不做任何幾何判定——
    生圖端不得成為第二套幾何來源。座標框沿用 scene_service._flip_parsed_z：
    +z 朝南、+x 朝東。
    """
    ring = (region or {}).get("exterior") or []
    position = item.get("position_cm") or {}
    try:
        x = float(position["x"])
        z = float(position["z"])
        xs = [float(point[0]) for point in ring]
        zs = [float(point[1]) for point in ring]
    except (KeyError, TypeError, ValueError, IndexError):
        return ""
    if not xs or not zs:
        return ""
    sides = (
        ("西側牆", x - min(xs)),
        ("東側牆", max(xs) - x),
        ("北側牆", z - min(zs)),
        ("南側牆", max(zs) - z),
    )
    nearest, distance = min(sides, key=lambda pair: pair[1])
    if distance > WALL_SNAP_CM:
        return "位於房間中央區域"
    return f"貼{nearest}"


def locked_furniture(
    prepared: dict[str, Any],
    room_view: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """把 scene_json 已定案的家具整理成生圖鎖定清單，回傳（清單, 被截斷件數）。

    這是「參考截圖 + 一句請保留家具」以外的第二層保險：模型看圖猜家具會產生
    幻覺（換型號、多一張椅子、沙發換位），明文列出身分與座標才鎖得住。

    兩個排除規則：
    - ``placement_failed`` 的項目沒有進場景，參考截圖裡也看不到，列進 prompt
      等於要求模型畫出畫面上不存在的東西。
    - 價格欄位與生圖無關（見 ``_EXCLUDED_ITEM_KEYS``）。

    家具身分一律取自 ``prepared["scene"]``，不繞 ``requirements``——後者會過
    ``render_service._strip_private_fields``，而 ``name`` 在 PRIVATE_KEYS 裡，
    繞過去家具名稱會被整個剝掉。
    """
    room_id = str((room_view or {}).get("room_id") or "")
    region = _room_region(prepared, room_id) if room_id else None
    items: list[dict[str, Any]] = []
    for item in _scene_objects(prepared):
        if item.get("placement_failed"):
            continue
        if room_id and _object_room_id(item) != room_id:
            continue
        size = item.get("size_cm") or {}
        position = item.get("position_cm") or {}
        entry = {
            "catalog_id": str(
                item.get("catalog_furniture_id") or item.get("furniture_id") or ""
            ),
            "name": str(item.get("name_zh_raw") or ""),
            "type": str(item.get("normalized_type") or ""),
            "material": item.get("material"),
            "style": item.get("primary_style"),
            "size_cm": {
                "width": size.get("width"),
                "depth": size.get("depth"),
                "height": size.get("height"),
            },
            "position_cm": {"x": position.get("x"), "z": position.get("z")},
            "rotation_deg": item.get("rotation_y_deg"),
            "wall_hint": _wall_hint(item, region),
        }
        items.append({key: value for key, value in entry.items() if value not in (None, "")})

    truncated = max(0, len(items) - MAX_LOCKED_FURNITURE)
    return items[:MAX_LOCKED_FURNITURE], truncated


def _furniture_lock_sections(
    prepared: dict[str, Any],
    room_view: dict[str, Any] | None,
) -> tuple[str, str]:
    """回傳（清單摘要, JSON 附錄）。兩者都空字串代表場景沒有可鎖定的家具。"""
    items, truncated = locked_furniture(prepared, room_view)
    if not items:
        return "", ""

    lines = [f"畫面中的家具共 {len(items)} 件，逐件如下（數量與品項不得增減）："]
    for index, item in enumerate(items, start=1):
        size = item.get("size_cm") or {}
        descriptors = [
            item.get("name") or item.get("type") or f"家具{index}",
            f"型號 {item['catalog_id']}" if item.get("catalog_id") else "",
            "×".join(
                str(size[key]) for key in ("width", "depth", "height") if size.get(key)
            ),
            f"材質 {item['material']}" if item.get("material") else "",
            item.get("wall_hint") or "",
        ]
        lines.append(f"{index}. " + "、".join(part for part in descriptors if part))
    if truncated:
        lines.append(f"（另有 {truncated} 件未列出，同樣不得增減或移動。）")

    appendix = (
        "以下 JSON 是上述家具的精確定位（單位公分，座標與角度均已定案，"
        "僅供你確認位置，不得依此重新排列）：\n"
        + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )
    return "\n".join(lines), appendix


def _digest_lines(source: dict[str, Any], fields: tuple[tuple[str, str], ...]) -> list[str]:
    lines = []
    for key, label in fields:
        value = str(source.get(key) or "").strip()
        if value:
            lines.append(f"{label}：{value}")
    return lines


def requirement_notes(
    prepared: dict[str, Any],
    room_view: dict[str, Any] | None = None,
) -> list[str]:
    """把問卷摘要翻成 prompt 段落。

    只收 ``requirements.digest``——那是前端已經解析成中文標籤的視覺需求
    （材質、天花、燈具、冷氣與氛圍）。家具品項與數量刻意不走這條，改由
    ``locked_furniture`` 直接讀 scene_json：問卷是「想要什麼」，scene 是
    「實際擺了什麼」，兩者可能不一致，把後者當唯一畫面依據才不會自相矛盾。

    逐房出圖時只帶該房間那筆，避免整份摘要稀釋掉本張要聚焦的資訊。
    """
    digest = ((prepared.get("requirements") or {}).get("digest")) or {}
    if not isinstance(digest, dict):
        return []

    notes: list[str] = []
    whole_house = digest.get("whole_house")
    if isinstance(whole_house, dict):
        notes.extend(_digest_lines(whole_house, (
            ("members_and_pets", "成員與寵物"),
            ("lifestyle", "生活型態"),
            ("wall", "全屋牆面"),
            ("floor", "全屋地板"),
            ("ceiling", "全屋天花"),
            ("lighting", "全屋燈具"),
        )))
        # 生圖細節：3D 場景沒有對應物件，模型本來就得自行補完；使用者留白
        # 的項目前端不會送過來，這裡也就不會出現在 prompt。
        for detail in whole_house.get("render_details") or []:
            text = str(detail).strip()
            if text:
                notes.append(text)
        immutable = str(whole_house.get("immutable_needs") or "").strip()
        if immutable:
            notes.append(f"不可變更的條件：{immutable}")

    room_id = str((room_view or {}).get("room_id") or "")
    for room in digest.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        if room_id and str(room.get("room_id")) != room_id:
            continue
        detail = _digest_lines(room, (
            ("wall", "牆面"),
            ("floor", "地板"),
            ("ceiling", "天花"),
            ("lighting", "燈具"),
            ("air_conditioning", "空調"),
        ))
        if detail:
            label = str(room.get("room_label") or room.get("room_id") or "此空間")
            notes.append(f"{label}——" + "、".join(detail))
    return notes


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
    # 家具清單緊接在鎖定語句之後：模型對 prompt 前段的指令權重最高，而
    # 「畫面上有哪些家具」正是最容易被幻覺改寫的部分。
    inventory, furniture_appendix = _furniture_lock_sections(prepared, room_view)
    if inventory:
        parts.append(inventory)
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
    # 問卷的視覺需求：材質、天花、燈具與空調在 3D 場景裡沒有對應物件，模型
    # 本來就得自行補完。給了答案是把「亂補」變成「照需求補」，不會與家具鎖
    # 定衝突。
    notes = requirement_notes(prepared, room_view)
    if notes:
        parts.append("使用者的需求問卷重點（必須反映在畫面上）：\n" + "\n".join(
            f"- {note}" for note in notes
        ))
    if room_view is not None:
        room_label = str(room_view.get("room_label") or room_view.get("room_id") or "").strip()
        if room_label:
            parts.append(f"本張聚焦房間：{room_label}，以該房間視角出圖。")
    if furniture_appendix:
        parts.append(furniture_appendix)
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
    failures = 0
    last_failure: Exception | None = None
    for task in tasks:
        style_pack = _style_pack_for(prepared, task["style_card_id"])
        prompt = build_render_prompt(prepared, style_pack, task["room_view"])
        reference = _reference_data_url(prepared, task["room_view"])
        try:
            png = await _generate_one(prompt, reference)
        except (RenderProviderRejected, RenderProviderUnavailable) as exc:
            # 一間房失敗不該讓整批消失：其餘房間照樣產出，失敗的留成可重試的
            # 任務卡（QA 2026-08-01 #7：遇首個 502 即整批中止）。
            failures += 1
            last_failure = exc
            room_view = task["room_view"] or {}
            jobs.append(
                {
                    "job_id": None,
                    "style_card_id": task["style_card_id"],
                    "room_id": room_view.get("room_id"),
                    "status": "failed",
                    "error_code": str(exc),
                    "message_zh": "這個房間的生圖失敗，可單獨重試。",
                    "label": room_view.get("room_label"),
                }
            )
            continue

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
    if tasks and failures == len(tasks) and last_failure is not None:
        # 全軍覆沒才算整批失敗。原樣拋回最後一個原因，錯誤碼才不會被泛用碼
        # 蓋掉——呼叫端與既有 502／503 契約都靠那個碼判斷發生了什麼。
        raise last_failure

    return {
        "request_id": prepared.get("request_id"),
        "provider": direct_image_provider_status()["provider"],
        "jobs": jobs,
        "failed_count": failures,
    }
