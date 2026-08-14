from __future__ import annotations

from typing import Any


class NoopSemanticRetriever:
    """【MOCK／NOOP】尚未接上真實 Vector Index 的占位 Adapter。

    - 本功能目前「沒有」接上可用的工法文件向量索引，因此 search() 永遠回傳空清單。
    - 這不是真正的 Vector Retrieval；對外文件與 API 中 retrieval_modes 只會
      出現 structured，不得宣稱語意檢索已上線。
    - 正式化：以 knowledge/construction_knowledge.jsonl 與家具 VLM 描述建立
      embedding index，實作 ports.SemanticRetriever 後在 container 替換本類別。
    """

    is_noop = True

    def search(
        self, query: str, filters: dict[str, Any], top_k: int = 10
    ) -> list[dict[str, Any]]:
        del query, filters, top_k
        return []
