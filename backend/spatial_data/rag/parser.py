"""Configured LLM parser dispatch for furniture RAG."""

from __future__ import annotations

from typing import Any

from .anthropic_parser import parse_query as parse_anthropic_query
from .errors import RagDependencyError
from .openai_parser import ParsedQuery, parse_query as parse_openai_query
from .openrouter_parser import parse_query as parse_openrouter_query
from .settings import RagSettings


def parse_query(
    text: str,
    settings: RagSettings,
    *,
    client: Any | None = None,
) -> ParsedQuery:
    if settings.parser_provider == "openai":
        return parse_openai_query(text, settings, client=client)
    if settings.parser_provider == "anthropic":
        return parse_anthropic_query(text, settings, client=client)
    if settings.parser_provider == "openrouter":
        return parse_openrouter_query(text, settings, client=client)
    raise RagDependencyError(
        "ROOMPILOT_RAG_PARSER_PROVIDER must be openai, anthropic, or openrouter"
    )
