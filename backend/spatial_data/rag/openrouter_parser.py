"""OpenRouter chat-completions adapter for furniture query parsing."""

from __future__ import annotations

import json
from typing import Any

from .errors import RagDependencyError, RagUpstreamError
from .models import RagQueryPlan
from .openai_parser import ParsedQuery, build_system_prompt
from .settings import RagSettings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_LIST_FIELDS = ("styles", "moods", "clarify_options", "items")
_ITEM_LIST_FIELDS = ("styles",)


def _usage_from_completion(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    return {
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": total,
    }


def _content_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RagUpstreamError("OpenRouter returned no choices")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or item))
        content = "".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise RagUpstreamError("OpenRouter returned empty content")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _normalize_plan_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RagUpstreamError("OpenRouter returned non-object JSON")
    data = dict(payload)
    for field in _LIST_FIELDS:
        if data.get(field) is None:
            data[field] = []
    items = data.get("items")
    if isinstance(items, list):
        normalized_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            for field in _ITEM_LIST_FIELDS:
                if row.get(field) is None:
                    row[field] = []
            normalized_items.append(row)
        data["items"] = normalized_items
    if data.get("needs_clarification") is None:
        data["needs_clarification"] = False
    if data.get("is_set") is None:
        data["is_set"] = False
    if data.get("confidence") is None:
        data["confidence"] = 0.5
    if data.get("reasoning") in (None, ""):
        data["reasoning"] = "parsed_from_openrouter"
    return data


def _build_client(settings: RagSettings) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RagDependencyError("openai package is not installed") from exc
    headers = {
        "HTTP-Referer": settings.openrouter_site_url or "http://127.0.0.1:8002",
        "X-Title": settings.openrouter_app_name or "roompilot",
    }
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=settings.parser_timeout_seconds,
        default_headers=headers,
    )


def _system_prompt() -> str:
    schema = RagQueryPlan.model_json_schema()
    return (
        build_system_prompt()
        + "\n\n只輸出一個 JSON object，不要 markdown。"
        + " 陣列欄位（styles、moods、clarify_options、items 與 item.styles）"
        + "不可輸出 null，沒有值時請輸出 []。"
        + "\nJSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _parse_with_model(
    text: str,
    settings: RagSettings,
    *,
    client: Any,
    model: str,
) -> ParsedQuery:
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": text},
    ]
    last_error: Exception | None = None
    for use_json_object in (True, False):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
        }
        if use_json_object:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = client.chat.completions.create(**kwargs)
            raw = _content_text(response)
            payload = _normalize_plan_payload(json.loads(raw))
            plan = RagQueryPlan.model_validate(payload)
            return ParsedQuery(plan=plan, usage=_usage_from_completion(response))
        except RagDependencyError:
            raise
        except Exception as exc:
            last_error = exc
            continue
    raise RagUpstreamError(
        f"OpenRouter query parsing failed for model {model}"
    ) from last_error


def parse_query(
    text: str,
    settings: RagSettings,
    *,
    client: Any | None = None,
) -> ParsedQuery:
    if not settings.openrouter_api_key:
        raise RagDependencyError("OPENROUTER_API_KEY is not configured")
    models = settings.parser_model_candidates
    if not models:
        raise RagDependencyError("OpenRouter parser model is not configured")
    if client is None:
        client = _build_client(settings)

    errors: list[str] = []
    for model in models:
        try:
            return _parse_with_model(text, settings, client=client, model=model)
        except RagUpstreamError as exc:
            errors.append(f"{model}: {exc}")
            continue
    raise RagUpstreamError(
        "OpenRouter query parsing failed for all models: " + "; ".join(errors)
    )
