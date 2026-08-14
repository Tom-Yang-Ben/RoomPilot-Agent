"""OpenRouter LLM gateway：文字與生圖統一走同一個 gateway。

依架構提案定案：

- 文字 LLM 與生圖模型都經 OpenRouter 呼叫（單一金鑰與計費入口），但**端點不同**：
  文字走 ``/api/v1/chat/completions``，生圖走 ``/api/v1/images``。
- 生圖主模型與 fallback 由 ``.env`` 決定；重試次數與模型切換不在這裡決定——
  那是 Master 的職責（見 ``subagents/genpic_agent.py``）。
- 本模組不做任何流程控制，只提供「一次呼叫」的薄封裝與可注入的
  ``LLMGateway`` 介面，測試以假件替換、不碰網路。
- HTTP 走 stdlib ``urllib``＋``certifi``（若已安裝）：業務碼禁止 import
  httpx（CLAUDE.md 依賴規範；dev 群組的 httpx2 只供 fastapi.testclient）。

環境變數：

- ``OPENROUTER_API_KEY``（沿用 repo 既有慣例；空值＝離線、走 deterministic fallback）
- ``ROOMPILOT_AGENT_LLM_TIMEOUT``（秒，預設 120）
- ``OPENROUTER_SITE_URL``／``OPENROUTER_APP_NAME``（OpenRouter 歸因標頭）

模型 id 一律走 ``backend/model_config.py``（哪個功能用哪顆、對應哪個 ``.env``
變數都寫在那張表），本模組不再自帶模型設定入口。
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..model_config import model_default, model_id

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# 生圖走 OpenRouter 專用端點，不走 chat/completions＋modalities：後者只餵得動
# output_modalities 含 "text" 的模型（如 google/gemini-2.5-flash-image），純生圖模型
# （x-ai/grok-imagine-image-2.0 等 output_modalities 只有 image）會直接失敗，再被
# genpic_agent 的失敗政策悄悄換成備援模型——看起來就像「換了模型卻沒生效」。
OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images"

# 以下三個常數只是「.env 沒設時的內建預設」，供 genpic_agent／測試對照用；
# 實際生效值一律呼叫 model_id()／default_text_model()，見 backend/model_config.py。
DEFAULT_IMAGE_MODEL = model_default("genpic")
DEFAULT_IMAGE_FALLBACK_MODEL = model_default("genpic_fallback")
DEFAULT_REPORT_MODEL = model_default("report")


def report_model() -> str:
    """第 8 步結案報告（設計手冊／交付提案）用的文字模型。

    刻意與 ``text_model`` 分開：報告文案品質綁在特定一顆模型上，不隨通用文字
    模型的環境設定漂移（``ROOMPILOT_REPORT_MODEL`` 可單獨覆蓋）。
    """
    return model_id("report")

class LLMError(RuntimeError):
    """LLM 呼叫失敗；``reason`` 是要能拿去「提示使用者失敗原因」的可讀訊息。"""

    def __init__(self, reason: str, *, status: int | None = None, model: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.model = model


@dataclass
class ImageResult:
    image_b64: str
    model: str
    raw: dict | None = None


class LLMGateway(Protocol):
    """文字與生圖的抽象介面；skills / subagents 只依賴這個協定。"""

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        force_json: bool = False,
        reasoning: dict | None = None,
    ) -> str: ...

    def generate_image(
        self,
        prompt: str,
        *,
        images: tuple[str, ...] = (),
        model: str | None = None,
    ) -> ImageResult: ...


def default_text_model() -> str:
    return model_id("agent_text")


# 生圖模型**不會**自己跟著參考圖的比例走：實測 bytedance-seed/seedream-5-0-pro 收到
# 16:9 的視角截圖、沒帶 aspect_ratio 時回 2048×2048 正方形——img2img 鎖定的構圖被
# 重新裁框，等於白鎖。這串是 seedream／grok-imagine／gemini image 都支援的交集值，
# 送交集外的值（例如 "auto"）會讓備援模型直接 400。
_ASPECT_RATIOS: tuple[tuple[float, str], ...] = (
    (9 / 16, "9:16"),
    (2 / 3, "2:3"),
    (3 / 4, "3:4"),
    (1.0, "1:1"),
    (4 / 3, "4:3"),
    (3 / 2, "3:2"),
    (16 / 9, "16:9"),
)


def reference_aspect_ratio(image: str) -> str:
    """量參考圖比例並 snap 到支援的 enum；量不到就回空字串（呼叫端不送這個參數）。"""
    try:
        from io import BytesIO

        from PIL import Image

        raw = image.split(",", 1)[1] if image.startswith("data:") else image
        with Image.open(BytesIO(base64.b64decode(raw))) as probe:
            width, height = probe.size
    except Exception:  # 壞 base64／非影像／沒裝 Pillow：維持模型預設，不因此讓生圖失敗
        return ""
    if not width or not height:
        return ""
    ratio = width / height
    return min(_ASPECT_RATIOS, key=lambda item: abs(item[0] - ratio))[1]


def parse_json_block(text: str) -> dict:
    """從 LLM 回覆中抽出第一個 JSON 物件；抽不出來丟 ``LLMError``。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except (ValueError, TypeError):
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        loaded = json.loads(text[start : index + 1])
                        if isinstance(loaded, dict):
                            return loaded
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    raise LLMError("LLM 回覆不含可解析的 JSON 物件")


@dataclass
class OpenRouterGateway:
    """OpenRouter chat completions 薄封裝（文字＋圖像 modalities）。"""

    api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())
    text_model: str = field(default_factory=default_text_model)
    image_model: str = field(default_factory=lambda: model_id("genpic"))
    image_fallback_model: str = field(default_factory=lambda: model_id("genpic_fallback"))
    site_url: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:8002")
    )
    app_name: str = field(default_factory=lambda: os.getenv("OPENROUTER_APP_NAME", "roompilot"))
    timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("ROOMPILOT_AGENT_LLM_TIMEOUT", "120"))
    )

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    # -- 內部：一次 HTTP 呼叫（stdlib urllib；業務碼禁 httpx，見 CLAUDE.md） --

    def _ssl_context(self):
        try:
            import ssl

            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            return None  # 系統憑證鏈可用時退回預設

    def _post(self, payload: dict, *, model: str, url: str = OPENROUTER_URL) -> dict:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY 未設定", model=model)
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.site_url,
                "X-Title": self.app_name,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds, context=self._ssl_context()
            ) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                detail = ""
            raise LLMError(
                f"OpenRouter 回應 {exc.code}：{detail}", status=exc.code, model=model
            ) from exc
        except Exception as exc:
            raise LLMError(f"OpenRouter 連線失敗：{exc}", model=model) from exc
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise LLMError(f"OpenRouter 回應非 JSON：{exc}", model=model) from exc
        if isinstance(data, dict) and data.get("error"):
            raise LLMError(f"OpenRouter 錯誤：{data['error']}", model=model)
        if not isinstance(data, dict):
            raise LLMError("OpenRouter 回應格式異常", model=model)
        return data

    # -- 文字 --

    def chat(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        force_json: bool = False,
        reasoning: dict | None = None,
    ) -> str:
        used_model = model or self.text_model
        payload: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "temperature": temperature,
        }
        if force_json:
            payload["response_format"] = {"type": "json_object"}
        if reasoning is not None:
            payload["reasoning"] = reasoning
        data = self._post(payload, model=used_model)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"OpenRouter 回應缺少 message content：{exc}", model=used_model) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("OpenRouter 回覆內容為空", model=used_model)
        return content

    # -- 生圖（OpenRouter /api/v1/images；img2img 參考圖走 input_references） --

    def generate_image(
        self,
        prompt: str,
        *,
        images: tuple[str, ...] = (),
        model: str | None = None,
    ) -> ImageResult:
        used_model = model or self.image_model
        payload: dict[str, Any] = {"model": used_model, "prompt": prompt}
        references = [
            {
                "type": "image_url",
                "image_url": {
                    "url": img if img.startswith("data:") else f"data:image/png;base64,{img}"
                },
            }
            for img in images
        ]
        if references:
            payload["input_references"] = references
            aspect_ratio = reference_aspect_ratio(images[0])
            if aspect_ratio:
                payload["aspect_ratio"] = aspect_ratio
        data = self._post(payload, model=used_model, url=OPENROUTER_IMAGE_URL)
        for row in data.get("data") or []:
            image_b64 = (row or {}).get("b64_json") or ""
            if not image_b64:
                # 部分 provider 回 url 欄位；只有 data URL 能直接進 image_ref。
                url = (row or {}).get("url") or ""
                image_b64 = url.split(",", 1)[-1] if url.startswith("data:") else ""
            if image_b64:
                return ImageResult(image_b64=image_b64, model=used_model, raw=None)
        raise LLMError("生圖模型未回傳影像內容", model=used_model)
