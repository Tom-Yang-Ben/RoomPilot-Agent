"""OpenAI Structured Outputs adapter for Django's furniture query schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import RagDependencyError, RagUpstreamError
from .models import RagQueryPlan
from .settings import RagSettings
from .vocab import load_vocab


@dataclass(frozen=True)
class ParsedQuery:
    plan: RagQueryPlan
    usage: dict[str, int]


def build_system_prompt() -> str:
    vocab = load_vocab()
    style_lines = "\n".join(
        f"- {key}（{value['zh']}）：{value['definition']}"
        for key, value in vocab["styles"].items()
    )
    group_lines = "\n".join(
        f"- {key}（{value['label_zh']}）：{'、'.join(value['categories'])}"
        for key, value in vocab["groups"].items()
    )
    room_sets = "\n".join(
        f"- {room}: {' + '.join(groups)}"
        for room, groups in vocab["room_default_sets"].items()
    )
    return f"""你是 RoomPilot 的家具需求解析器。只輸出指定的結構化欄位。

風格只能選最多兩個：
{style_lines}

家具群組：
{group_lines}

房型預設組合（只有使用者要整組配置時才能補入，並把補入品項標成 is_inferred=true）：
{room_sets}

硬規則：
1. 使用者沒說的房型、價格、尺寸、材質或顏色必須保持 null，不得臆造。
2. 具體金額才填 price_max 或 budget_total；便宜／中等／高級只填 price_level。
3. max_width_cm 和 max_height_cm 只有使用者明講空間限制才可填。
4. room_type、category_group、price、尺寸、role、size_hint 是硬篩選，必須保守。
5. styles、moods、pattern 是軟排序條件。styles 最多 2 個，moods 最多 3 個。
6. items 必須至少一筆、最多六筆；未知類別使用 category_group=null，不得硬猜。
7. semantic_query 是 30–120 字的家具外觀描述，包含物件、風格、材質、色彩與氛圍，供 BGE-M3 查詢；不得放價格或尺寸。
8. 主家具用 role=anchor，配件用 accent；不確定就填 null。
9. 資訊不足時 needs_clarification=true，同時仍回傳可用的暫定 items、問題與 2–4 個選項。
10. item_id 使用穩定的小寫英文 slug；confidence 為 0 到 1。"""


def _usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def parse_query(
    text: str,
    settings: RagSettings,
    *,
    client: Any | None = None,
) -> ParsedQuery:
    key_name = (
        "OPENROUTER_API_KEY"
        if settings.parser_provider == "openrouter"
        else "OPENAI_API_KEY"
    )
    if not settings.parser_api_key:
        raise RagDependencyError(f"{key_name} is not configured")
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RagDependencyError("openai package is not installed") from exc
        client_options: dict[str, Any] = {
            "api_key": settings.parser_api_key,
            "timeout": settings.parser_timeout_seconds,
        }
        if settings.parser_provider == "openrouter":
            headers = {}
            if settings.openrouter_site_url:
                headers["HTTP-Referer"] = settings.openrouter_site_url
            if settings.openrouter_app_name:
                headers["X-Title"] = settings.openrouter_app_name
            client_options.update(
                base_url=settings.openrouter_base_url,
                default_headers=headers,
            )
        client = OpenAI(**client_options)

    try:
        response = client.responses.parse(
            model=settings.parser_model,
            input=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": text},
            ],
            text_format=RagQueryPlan,
            reasoning={"effort": settings.parser_reasoning_effort},
            store=False,
        )
    except RagDependencyError:
        raise
    except Exception as exc:
        provider_name = (
            "OpenRouter" if settings.parser_provider == "openrouter" else "OpenAI"
        )
        raise RagUpstreamError(f"{provider_name} query parsing failed") from exc

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        provider_name = (
            "OpenRouter" if settings.parser_provider == "openrouter" else "OpenAI"
        )
        raise RagUpstreamError(
            f"{provider_name} returned a refusal or no structured output"
        )
    try:
        plan = parsed if isinstance(parsed, RagQueryPlan) else RagQueryPlan.model_validate(parsed)
    except Exception as exc:
        provider_name = (
            "OpenRouter" if settings.parser_provider == "openrouter" else "OpenAI"
        )
        raise RagUpstreamError(f"{provider_name} returned invalid structured output") from exc
    return ParsedQuery(plan=plan, usage=_usage(response))
