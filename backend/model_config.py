"""外接模型註冊表：**哪個功能用哪顆模型**，模型 id 一律從 repo 根 `.env` 讀。

改模型只改 `.env`，不改程式碼。`REGISTRY` 的內建預設只是「`.env` 沒設時仍能跑」
的離線值，不是設定入口。

| 功能（哪一步／哪個能力） | `.env` 變數（由左至右取第一個有值的） | 內建預設 |
| :--- | :--- | :--- |
| 第 1 步 問卷需求抽取（`intake_service`） | `ROOMPILOT_INTAKE_MODEL` → `OPENROUTER_MODELS` → `OPENROUTER_MODEL` | `openrouter/free` |
| 第 6 步 LLM 場景規劃（`scene_service`，預設關閉） | `ROOMPILOT_SCENE_MODEL` → `OPENROUTER_MODELS` → `OPENROUTER_MODEL` | `openrouter/free` |
| Agent 通用文字（選件、修復意圖、說明） | `ROOMPILOT_AGENT_TEXT_MODEL` → `OPENROUTER_MODEL` → `OPENROUTER_MODELS` | `openrouter/auto` |
| 第 8 步 設計手冊／交付提案文案 | `ROOMPILOT_REPORT_MODEL` | `openai/gpt-5.6-luna` |
| 第 7 步 代表房三色卡比較圖（主） | `ROOMPILOT_GENPIC_PALETTE_MODEL` | `google/gemini-3-pro-image-preview` |
| 第 7 步 色卡比較圖（備援） | `ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL` | 空＝退回第 8 步生圖主模型 |
| 第 8 步 逐房寫實生圖／改圖（主） | `ROOMPILOT_GENPIC_MODEL` | `google/gemini-3.1-flash-image`（Nano Banana 2） |
| 第 8 步 逐房寫實生圖／改圖（備援） | `ROOMPILOT_GENPIC_FALLBACK_MODEL` | `google/gemini-2.5-flash-image` |
| 家具檢索 query parser（`ROOMPILOT_RAG_PARSER_PROVIDER` 決定用哪列） | `ROOMPILOT_RAG_PARSER_MODEL` → `ROOMPILOT_RAG_{OPENAI,ANTHROPIC}_MODEL` | 見 `rag_parser_*` |

金鑰不在這裡：`OPENROUTER_API_KEY`／`OPENAI_API_KEY`／`ANTHROPIC_API_KEY` 由各呼叫端
讀取，本模組只決定模型 id。完整環境變數表見
`RoomPilot_Docs/06_ops/deployment_and_operations.md` §3。

家具向量的 `BAAI/bge-m3`／`BAAI/bge-reranker-v2-m3` **不在此表**：那是本機執行的
權重，且 model id 是 PostgreSQL 內嵌向量的查詢鍵（`catalog/rag_repository.py:67`），
用 `.env` 換掉會讓檢索靜默查不到列，只能連同重算向量一起改。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - requirements.txt 已含 python-dotenv
    dotenv_values = None

PROJECT_DIR = Path(__file__).resolve().parents[1]

# key: (env 變數鏈, 內建預設, 用在哪個功能)
REGISTRY: dict[str, tuple[tuple[str, ...], str, str]] = {
    "intake": (
        ("ROOMPILOT_INTAKE_MODEL", "OPENROUTER_MODELS", "OPENROUTER_MODEL"),
        "openrouter/free",
        "第 1 步 問卷需求抽取",
    ),
    "scene_planning": (
        ("ROOMPILOT_SCENE_MODEL", "OPENROUTER_MODELS", "OPENROUTER_MODEL"),
        "openrouter/free",
        "第 6 步 LLM 場景規劃（預設關閉）",
    ),
    "agent_text": (
        ("ROOMPILOT_AGENT_TEXT_MODEL", "OPENROUTER_MODEL", "OPENROUTER_MODELS"),
        "openrouter/auto",
        "Agent 通用文字（選件、修復意圖、說明）",
    ),
    "report": (
        ("ROOMPILOT_REPORT_MODEL",),
        "openai/gpt-5.6-luna",
        "第 8 步 設計手冊／交付提案文案",
    ),
    "palette": (
        ("ROOMPILOT_GENPIC_PALETTE_MODEL",),
        "google/gemini-3-pro-image-preview",
        "第 7 步 代表房三色卡比較圖（主）",
    ),
    "palette_fallback": (
        ("ROOMPILOT_GENPIC_PALETTE_FALLBACK_MODEL",),
        "",  # 空＝呼叫端退回 genpic 主模型
        "第 7 步 色卡比較圖（備援）",
    ),
    "genpic": (
        ("ROOMPILOT_GENPIC_MODEL",),
        # Nano Banana 2；與本機 .env 的 ROOMPILOT_GENPIC_MODEL 同值，這樣沒有 .env
        # 的機器（.env 被 gitignore）第 8 步顯示與實際送出的模型才不會跟開發機不同。
        "google/gemini-3.1-flash-image",
        "第 8 步 逐房寫實生圖／改圖（主）",
    ),
    "genpic_fallback": (
        ("ROOMPILOT_GENPIC_FALLBACK_MODEL",),
        "google/gemini-2.5-flash-image",
        "第 8 步 逐房寫實生圖／改圖（備援）",
    ),
    "rag_parser_openai": (
        ("ROOMPILOT_RAG_OPENAI_MODEL",),
        "gpt-5.6-sol",
        "家具檢索 query parser（provider=openai）",
    ),
    "rag_parser_anthropic": (
        ("ROOMPILOT_RAG_ANTHROPIC_MODEL",),
        "claude-sonnet-4-6",
        "家具檢索 query parser（provider=anthropic）",
    ),
    "rag_parser_openrouter": (
        ("OPENROUTER_MODEL", "OPENROUTER_MODELS"),
        "openrouter/free",
        "家具檢索 query parser（provider=openrouter）",
    ),
}


@lru_cache(maxsize=1)
def _env_file() -> dict[str, str]:
    """讀 repo 根 `.env`，**不寫回 `os.environ`**。

    刻意不用 ``load_dotenv``：那會把整份 `.env`（含 `OPENROUTER_API_KEY` 等秘密）
    灌進行程環境，讓「刪掉金鑰應該回 503」這類測試與離線模式被 `.env` 悄悄復活。
    這裡只回字典，由 ``model_list`` 挑它要的那個變數。
    """
    if dotenv_values is None:  # pragma: no cover
        return {}
    return {k: v for k, v in dotenv_values(PROJECT_DIR / ".env").items() if v is not None}


def model_default(key: str) -> str:
    """`.env` 沒設時的內建預設；設定入口仍是 `.env`。"""
    return REGISTRY[key][1]


def model_list(key: str) -> list[str]:
    """該功能設定的模型清單（`.env` 可用逗號給多顆，用法由呼叫端決定）。

    行程環境優先於 `.env` 檔，與 `postgres_repository.py` 的既有慣例一致。
    """
    file_values = _env_file()
    env_names, default, _ = REGISTRY[key]
    raw = default
    for name in env_names:
        value = os.getenv(name, file_values.get(name, "")).strip()
        if value:
            raw = value
            break
    return [item.strip() for item in raw.split(",") if item.strip()]


def model_id(key: str) -> str:
    """該功能實際要用的模型 id；設定成清單時取第一顆。未設定且無預設時回空字串。"""
    models = model_list(key)
    return models[0] if models else ""
