from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


@dataclass(frozen=True)
class EngineeringSettings:
    knowledge_dir: Path
    template_dir: Path
    demo_mode: bool
    default_region: str


def load_engineering_settings() -> EngineeringSettings:
    # 輸出位置與版本鎖定的 SQLite 由呼叫端決定（第 8 步走 .runtime/manuals/，
    # 與交付提案 PDF 同目錄），這裡不再提供 ROOMPILOT_GENERATED_DIR /
    # ROOMPILOT_ENGINEERING_DB——設了也不會有人讀，是純粹的陷阱。
    return EngineeringSettings(
        knowledge_dir=_env_path(
            "ROOMPILOT_KNOWLEDGE_DIR", PROJECT_DIR / "knowledge"
        ),
        template_dir=Path(__file__).resolve().parent / "templates",
        demo_mode=_env_bool("ROOMPILOT_DEMO_MODE", default=True),
        default_region=os.getenv("ROOMPILOT_DEFAULT_REGION", "新北市"),
    )
