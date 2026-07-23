"""平面圖 VLM 語意標註:房間標籤 + 固定機能空間 + 門窗數交叉檢核 + 印刷尺寸抄錄。

角色是「檢核器/語意層」不是幾何來源:牆/門/窗的精確幾何仍由 floorplan2dxf
(傳統 CV)產出;VLM 只補幾何規則做不到的部分——
- 房間用途標籤(印刷文字 + 設備符號推斷,如馬桶/浴缸=浴室、爐台=廚房)
- fixed_utility 旗標(廚房=瓦斯管線、浴室=給排水——不可移動,擺位要剔除)
- 門窗數第二意見(與 CV 結果不一致 → 該圖信心降級,引導人工確認)
- 印刷尺寸原文(之後比例尺校正用)

用 OpenRouter 免費視覺模型(池會輪替,可用 OPENROUTER_VISION_MODELS 覆寫)。
失敗(無金鑰/限流/壞回應)一律回 None,辨識主流程不受影響。
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.request
from typing import Any

try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # 沒裝 certifi 就用系統預設(Linux 通常可用)
    _SSL_CTX = ssl.create_default_context()

# 2026-07 的免費視覺池;26b 品質已驗證(floor05 廚房/浴室/露台全對)
DEFAULT_VISION_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]

_VALID_KINDS = {"fixed_utility", "outdoor", "living", "circulation"}

_PROMPT = """你是建築平面圖分析師。請分析這張平面圖,只輸出 JSON(不要 markdown、不要說明文字)。

任務:
1. 找出圖中每一個房間/空間,含印刷文字標籤(如 KITCHEN、BEDROOM)與從設備符號推斷的空間(例如有馬桶/浴缸/淋浴間符號=浴室,有爐台/流理台符號=廚房,即使沒有文字標籤也要標出)。
   特別注意:浴室/廁所在平面圖上經常「沒有」文字標籤,只有馬桶、洗手台、浴缸或淋浴間符號——請逐一檢查每個小房間的設備符號,不要漏掉浴室。
2. 每個空間給 bbox,座標用 0~1000 的正規化座標(左上為原點,x 向右、y 向下,[x0,y0,x1,y1])。
3. kind 分類:fixed_utility(廚房/浴室/廁所——瓦斯與給排水管線固定,不可移動)、outdoor(陽台/露台/庭院)、living(臥室/客廳/餐廳/書房等一般室內)、circulation(玄關/走廊/樓梯)。
4. 數整張圖的門數(含門弧符號)與窗數(牆上的多線窗符號)。
5. 若圖上有印刷尺寸文字(如 10'1" x 11'1" 或 3.5m x 4m),抄錄原文並附所屬房間。

JSON 格式:
{
  "rooms": [
    {"label": "原文標籤或推斷名", "label_zh": "中文名", "kind": "fixed_utility|outdoor|living|circulation",
     "evidence": "text|fixtures|both", "bbox": [x0, y0, x1, y1]}
  ],
  "door_count": 0,
  "window_count": 0,
  "printed_dimensions": [{"room": "KITCHEN", "text": "10'1\\" x 10'8\\""}]
}"""


def get_vision_models() -> list[str]:
    raw = os.getenv("OPENROUTER_VISION_MODELS", "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return DEFAULT_VISION_MODELS.copy()


def vlm_enabled() -> bool:
    if os.getenv("OPENROUTER_FLOORPLAN_VLM", "1") == "0":
        return False
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _ask_model(model: str, image_b64: str, mime: str, timeout: float,
               prompt: str | None = None) -> dict[str, Any] | None:
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or _PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            ],
        }],
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8002"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "roompilot floorplan vlm"),
        },
        method="POST",
    )
    try:
        body = json.load(urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_fence(content))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _sanitize(parsed: dict[str, Any], model: str) -> dict[str, Any] | None:
    rooms_out = []
    for room in parsed.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        bbox = room.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in bbox)
        except (TypeError, ValueError):
            continue
        if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
            continue
        kind = room.get("kind")
        rooms_out.append({
            "label": str(room.get("label") or "?")[:40],
            "label_zh": str(room.get("label_zh") or "")[:20],
            "kind": kind if kind in _VALID_KINDS else "living",
            "evidence": str(room.get("evidence") or "")[:16],
            "bbox_norm": [x0, y0, x1, y1],
        })
    if not rooms_out:
        return None

    def _int_or_none(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    dims = []
    for d in parsed.get("printed_dimensions") or []:
        if isinstance(d, dict) and d.get("text"):
            dims.append({"room": str(d.get("room") or "")[:40], "text": str(d["text"])[:60]})
    return {
        "model": model,
        "rooms": rooms_out,
        "door_count": _int_or_none(parsed.get("door_count")),
        "window_count": _int_or_none(parsed.get("window_count")),
        "printed_dimensions": dims,
    }


_BATHROOM_TOKENS = ("bath", "wc", "toilet", "浴", "廁", "衛")


def _has_bathroom(result: dict[str, Any]) -> bool:
    for room in result.get("rooms") or []:
        text = f"{room.get('label', '')} {room.get('label_zh', '')}".lower()
        if any(tok in text for tok in _BATHROOM_TOKENS):
            return True
    return False


def annotate_floorplan(image_bytes: bytes, mime: str = "image/png",
                       timeout_per_model: float = 90.0) -> dict[str, Any] | None:
    """影像 → VLM 語意標註(rooms 用 0~1000 正規化 bbox)。失敗回 None。

    浴室常無文字標籤、只有設備符號,是免費模型最容易漏的——第一輪沒抓到浴室時
    帶提醒重問一次,兩輪擇優(有浴室的優先,否則取房間數多的)。
    """
    if not vlm_enabled():
        return None
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    retry_prompt = _PROMPT + (
        "\n\n提醒:這張圖很可能有浴室/廁所但沒有文字標籤——請再逐一檢查每個小房間"
        "有沒有馬桶、洗手台、浴缸、淋浴間符號,把浴室補進 rooms。"
    )
    for model in get_vision_models():
        parsed = _ask_model(model, image_b64, mime, timeout_per_model)
        result = _sanitize(parsed, model) if parsed else None
        if not result:
            continue
        if _has_bathroom(result):
            return result
        retry = _ask_model(model, image_b64, mime, timeout_per_model, prompt=retry_prompt)
        retry_result = _sanitize(retry, model) if retry else None
        if retry_result and _has_bathroom(retry_result):
            return retry_result
        if retry_result and len(retry_result["rooms"]) > len(result["rooms"]):
            return retry_result
        return result
    return None
