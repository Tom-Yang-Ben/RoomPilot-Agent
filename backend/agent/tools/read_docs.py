"""讀全部文件 tool：取 DocStore 快照，作為設計手冊的統整素材。"""
from __future__ import annotations

from ..documents import DocStore
from .base import ToolContract


class ReadDocsTool:
    contract = ToolContract(
        name="read_docs",
        description="取得 Docs 層全部文件快照（需求、清單、場景、驗證、生圖、決策歷程）。",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "description": "key -> doc dict"},
    )

    def run(self, store: DocStore) -> dict:
        return store.snapshot()
