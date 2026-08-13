"""OpenRouter LLM gateway：文字與生圖統一走同一個 gateway。

依架構提案定案：

- 文字 LLM 與生圖模型都經 OpenRouter 呼叫（單一金鑰與計費入口）。
- 生圖主模型為 nano banana，失敗 fallback 為 nano banana 2；重試次數與
  模型切換不在這裡決定——那是 Master 的職責（見 ``subagents/genpic_agent.py``）。
- 本模組不做任何流程控制，只提供「一次呼叫」的薄封裝與可注入的
  ``LLMGateway`` 介面，測試以假件替換、不碰網路。
- HTTP 走 stdlib ``urllib``＋``certifi``（若已安裝）：業務碼禁止 import
  httpx（CLAUDE.md 依賴規範；dev 群組的 httpx2 只供 fastapi.testclient）。

環境變數：

- ``OPENROUTER_API_KEY``（沿用 repo 既有慣例；空值＝離線、走 deterministic fallback）
- ``ROOMPILOT_AGENT_TEXT_MODEL`` > ``OPENROUTER_MODEL`` > ``OPENROUTER_MODELS`` 第一個
- ``ROOMPILOT_GENPIC_MODEL``（預設 nano banana）
- ``ROOMPILOT_GENPIC_FALLBACK_MODEL``（預設 nano banana 2）
- ``ROOMPILOT_AGENT_LLM_TIMEOUT``（秒，預設 120）

模型 id 依 OpenRouter 目錄而定，部署時可用環境變數覆蓋。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# nano banana / nano banana 2 在 OpenRouter 的預設型號 id；以 .env 覆蓋為準。

# DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image"
# DEFAULT_IMAGE_FALLBACK_MODEL = "google/gemini-3.1-flash-image"

DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image"
DEFAULT_IMAGE_FALLBACK_MODEL = "google/gemini-2.5-flash-image"

# 結案報告（設計手冊／交付提案）固定用這顆，不隨 text_model 環境設定漂移
# （使用者定案：不管是不是測試都用它）。見 skills/report、skills/delivery。
DEFAULT_REPORT_MODEL = "openai/gpt-5.6-luna"

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
    explicit = os.getenv("ROOMPILOT_AGENT_TEXT_MODEL", "").strip()
    if explicit:
        return explicit
    single = os.getenv("OPENROUTER_MODEL", "").strip()
    if single:
        return single
    multi = os.getenv("OPENROUTER_MODELS", "").strip()
    if multi:
        return multi.split(",")[0].strip()
    return "openrouter/auto"


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
    image_model: str = field(
        default_factory=lambda: os.getenv("ROOMPILOT_GENPIC_MODEL", "").strip()
        or DEFAULT_IMAGE_MODEL
    )
    image_fallback_model: str = field(
        default_factory=lambda: os.getenv("ROOMPILOT_GENPIC_FALLBACK_MODEL", "").strip()
        or DEFAULT_IMAGE_FALLBACK_MODEL
    )
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

    def _post(self, payload: dict, *, model: str) -> dict:
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY 未設定", model=model)
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            OPENROUTER_URL,
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

    # -- 生圖（nano banana 系列走 chat completions 的 image modality） --

    def generate_image(
        self,
        prompt: str,
        *,
        images: tuple[str, ...] = (),
        model: str | None = None,
    ) -> ImageResult:
        used_model = model or self.image_model
        content: list[dict] = [{"type": "text", "text": prompt}]

        for image_b64 in images:
            url = image_b64
            if not url.startswith("data:"):
                url = f"data:image/png;base64,{image_b64}"
            content.append({"type": "image_url", "image_url": {"url": url}})
        payload = {
            "model": used_model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
        }
        data = self._post(payload, model=used_model)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"OpenRouter 回應缺少 message：{exc}", model=used_model) from exc
        for row in message.get("images") or []:
            url = ((row or {}).get("image_url") or {}).get("url", "")
            if url.startswith("data:"):
                url = url.split(",", 1)[-1]
            if url:
                return ImageResult(image_b64=url, model=used_model, raw=None)
        raise LLMError("生圖模型未回傳影像內容", model=used_model)
