"""Anthropic Structured Outputs adapter for Django's furniture query schema."""

from __future__ import annotations

from typing import Any

from .errors import RagDependencyError, RagUpstreamError
from .models import RagQueryPlan
from .openai_parser import ParsedQuery, build_system_prompt
from .settings import RagSettings


def _usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def parse_query(
    text: str,
    settings: RagSettings,
    *,
    client: Any | None = None,
) -> ParsedQuery:
    if not settings.anthropic_api_key:
        raise RagDependencyError("ANTHROPIC_API_KEY is not configured")
    if client is None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RagDependencyError("anthropic package is not installed") from exc
        client = Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.parser_timeout_seconds,
        )

    try:
        response = client.messages.parse(
            model=settings.parser_model,
            max_tokens=settings.anthropic_max_tokens,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": text}],
            output_format=RagQueryPlan,
        )
    except RagDependencyError:
        raise
    except Exception as exc:
        raise RagUpstreamError("Anthropic query parsing failed") from exc

    if getattr(response, "stop_reason", None) == "refusal":
        raise RagUpstreamError("Anthropic returned a refusal")
    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        raise RagUpstreamError("Anthropic returned no structured output")
    try:
        plan = parsed if isinstance(parsed, RagQueryPlan) else RagQueryPlan.model_validate(parsed)
    except Exception as exc:
        raise RagUpstreamError("Anthropic returned invalid structured output") from exc
    return ParsedQuery(plan=plan, usage=_usage(response))
