"""Server-only settings for the furniture RAG feature."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ...model_config import model_default


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
    # Local development must use the project .env consistently. A stale parent
    # process environment otherwise changes the RAG model without the project
    # configuration or status page reflecting the intended choice.
    return file_values.get(name, os.getenv(name, default)).strip()


def _truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RagSettings:
    enabled: bool
    parser_provider: str
    openai_api_key: str
    anthropic_api_key: str
    openrouter_api_key: str
    parser_model: str
    parser_reasoning_effort: str
    parser_timeout_seconds: float
    anthropic_max_tokens: int
    model_cache_dir: Path
    model_device: str

    @property
    def parser_api_key(self) -> str:
        if self.parser_provider == "anthropic":
            return self.anthropic_api_key
        if self.parser_provider == "openrouter":
            return self.openrouter_api_key
        return self.openai_api_key


def load_rag_settings(project_dir: Path) -> RagSettings:
    default_cache = Path(os.getenv("HF_HOME") or (Path.home() / ".cache" / "huggingface"))
    cache_setting = _setting(project_dir, "ROOMPILOT_RAG_MODEL_CACHE")
    provider = _setting(project_dir, "ROOMPILOT_RAG_PARSER_PROVIDER", "openai").casefold()
    # 內建預設集中在 backend/model_config.py（哪個功能用哪顆模型的那張表）；
    # 這裡的 _setting 仍是 .env 檔優先（見上方註解），不改既有優先序。
    if provider == "anthropic":
        default_model = _setting(
            project_dir, "ROOMPILOT_RAG_ANTHROPIC_MODEL", model_default("rag_parser_anthropic")
        )
    elif provider == "openrouter":
        configured_models = _setting(project_dir, "OPENROUTER_MODELS")
        default_model = (
            _setting(project_dir, "OPENROUTER_MODEL")
            or (
                configured_models.split(",", 1)[0].strip()
                if configured_models
                else model_default("rag_parser_openrouter")
            )
        )
    else:
        default_model = _setting(
            project_dir, "ROOMPILOT_RAG_OPENAI_MODEL", model_default("rag_parser_openai")
        )
    timeout_default = _setting(
        project_dir, "ROOMPILOT_RAG_OPENAI_TIMEOUT_SECONDS", "30"
    )
    return RagSettings(
        enabled=_truthy(_setting(project_dir, "ROOMPILOT_RAG_ENABLED", "false")),
        parser_provider=provider,
        openai_api_key=_setting(project_dir, "OPENAI_API_KEY"),
        anthropic_api_key=_setting(project_dir, "ANTHROPIC_API_KEY"),
        openrouter_api_key=_setting(project_dir, "OPENROUTER_API_KEY"),
        parser_model=(
            _setting(project_dir, "ROOMPILOT_RAG_PARSER_MODEL", default_model)
            or default_model
        ),
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
        model_cache_dir=Path(cache_setting).expanduser() if cache_setting else default_cache,
        model_device=_setting(project_dir, "ROOMPILOT_RAG_DEVICE", "auto").casefold(),
    )
