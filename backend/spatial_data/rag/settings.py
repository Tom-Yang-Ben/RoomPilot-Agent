"""Server-only settings for the furniture RAG feature."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _setting(project_dir: Path, name: str, default: str = "") -> str:
    file_values = _read_env_file(project_dir / ".env")
    return os.getenv(name, file_values.get(name, default)).strip()


def _truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


def _split_models(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class RagSettings:
    enabled: bool
    parser_provider: str
    openai_api_key: str
    anthropic_api_key: str
    openrouter_api_key: str
    parser_model: str
    parser_models: tuple[str, ...]
    parser_reasoning_effort: str
    parser_timeout_seconds: float
    anthropic_max_tokens: int
    openrouter_site_url: str
    openrouter_app_name: str
    model_cache_dir: Path
    model_device: str

    @property
    def parser_api_key(self) -> str:
        if self.parser_provider == "anthropic":
            return self.anthropic_api_key
        if self.parser_provider == "openrouter":
            return self.openrouter_api_key
        return self.openai_api_key

    @property
    def parser_model_candidates(self) -> tuple[str, ...]:
        if self.parser_models:
            return self.parser_models
        if self.parser_model:
            return (self.parser_model,)
        return ()


def load_rag_settings(project_dir: Path) -> RagSettings:
    default_cache = Path(os.getenv("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
    cache_setting = _setting(project_dir, "ROOMPILOT_RAG_MODEL_CACHE")
    provider = _setting(project_dir, "ROOMPILOT_RAG_PARSER_PROVIDER", "openai").casefold()
    openrouter_models = _split_models(_setting(project_dir, "OPENROUTER_MODELS"))
    openrouter_model = _setting(project_dir, "OPENROUTER_MODEL")
    rag_openrouter_models = _split_models(
        _setting(project_dir, "ROOMPILOT_RAG_OPENROUTER_MODELS")
    )
    if provider == "anthropic":
        default_model = _setting(
            project_dir, "ROOMPILOT_RAG_ANTHROPIC_MODEL", "claude-sonnet-4-6"
        )
        model_list: list[str] = []
    elif provider == "openrouter":
        # Prefer RAG-specific model list; scene free-model rotation often 404s on OpenRouter.
        preferred = rag_openrouter_models or [
            "openai/gpt-4o-mini",
            "cohere/north-mini-code:free",
        ]
        default_model = (
            _setting(project_dir, "ROOMPILOT_RAG_PARSER_MODEL")
            or openrouter_model
            or preferred[0]
        )
        model_list = preferred if preferred else ([openrouter_model] if openrouter_model else [])
    else:
        default_model = _setting(project_dir, "ROOMPILOT_RAG_OPENAI_MODEL", "gpt-5.6-sol")
        model_list = []
    timeout_default = _setting(
        project_dir, "ROOMPILOT_RAG_OPENAI_TIMEOUT_SECONDS", "30"
    )
    explicit_model = _setting(project_dir, "ROOMPILOT_RAG_PARSER_MODEL", default_model) or default_model
    if provider == "openrouter" and not model_list:
        model_list = [explicit_model]
    return RagSettings(
        enabled=_truthy(_setting(project_dir, "ROOMPILOT_RAG_ENABLED", "false")),
        parser_provider=provider,
        openai_api_key=_setting(project_dir, "OPENAI_API_KEY"),
        anthropic_api_key=_setting(project_dir, "ANTHROPIC_API_KEY"),
        openrouter_api_key=_setting(project_dir, "OPENROUTER_API_KEY"),
        parser_model=explicit_model,
        parser_models=tuple(model_list),
        parser_reasoning_effort=_setting(
            project_dir, "ROOMPILOT_RAG_REASONING_EFFORT", "low"
        ),
        parser_timeout_seconds=max(
            1.0,
            float(_setting(project_dir, "ROOMPILOT_RAG_TIMEOUT_SECONDS", timeout_default)),
        ),
        anthropic_max_tokens=max(
            1024,
            int(_setting(project_dir, "ROOMPILOT_RAG_ANTHROPIC_MAX_TOKENS", "4096")),
        ),
        openrouter_site_url=_setting(
            project_dir, "OPENROUTER_SITE_URL", "http://127.0.0.1:8002"
        ),
        openrouter_app_name=_setting(project_dir, "OPENROUTER_APP_NAME", "roompilot"),
        model_cache_dir=Path(cache_setting).expanduser() if cache_setting else default_cache,
        model_device=_setting(project_dir, "ROOMPILOT_RAG_DEVICE", "auto").casefold(),
    )
