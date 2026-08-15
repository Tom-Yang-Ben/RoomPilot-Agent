"""預設組裝：把 gateway、檢索器與四個 sub-agent 接成可用的 MasterAgent。

- 文字與生圖統一經 OpenRouter（``OPENROUTER_API_KEY``）；未設定金鑰時
  gateway 為 ``None``，文字 skills 走 deterministic fallback、生圖階段
  會以可讀原因暫停。
- 家具檢索預設接 Django 的 spatial RAG（需 PostgreSQL 與模型快取）；
  離線開發可注入自訂 retriever。
"""
from __future__ import annotations

import os
from pathlib import Path

from .documents import DocStore
from .llm import OpenRouterGateway
from .master import MasterAgent, MasterConfig
from .subagents import FurnitureAgent, GenPicAgent, ReportAgent, ValidationAgent
from .tools.rag_furniture import FurnitureRetriever, SpatialRagRetriever


def build_gateway() -> OpenRouterGateway | None:
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return OpenRouterGateway()
    return None


def build_master(
    *,
    gateway: OpenRouterGateway | None = None,
    retriever: FurnitureRetriever | None = None,
    project_dir: str | Path | None = None,
    store: DocStore | None = None,
    config: MasterConfig | None = None,
) -> MasterAgent:
    if gateway is None:
        gateway = build_gateway()
    if retriever is None and project_dir is not None:
        retriever = SpatialRagRetriever(Path(project_dir))
    return MasterAgent(
        FurnitureAgent(gateway, retriever=retriever),
        ValidationAgent(gateway),
        GenPicAgent(gateway),
        ReportAgent(gateway),
        store=store,
        config=config,
    )
