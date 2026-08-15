"""RAG 家具 tool：把需求文件轉成檢索查詢，取得候選家具清單。

邊界（AGENTS.md）：家具向量 RAG 只解析需求、檢索與排序 Kai PostgreSQL 家具，
不取代選件決策（skills/furniture）與幾何判定（backend/engine/）。

檢索器以 ``FurnitureRetriever`` 協定注入：

- 正式環境用 ``SpatialRagRetriever``，包 Django 的
  ``backend.spatial_data.rag.FurnitureRagService``（lazy import，重依賴不在
  匯入期載入）。
- 測試與離線開發注入假件。未注入且服務不可用時，回報可讀的 ``ToolError``，
  不悄悄改用未驗證資料（quarantine 資料不得進場景）。
"""
from __future__ import annotations

from typing import Any, Protocol

from ..documents import CandidateItem, CandidateListDoc, LayoutDoc, RequirementDoc
from .base import ToolContract, ToolError

RAG_TOP_K_MAX = 8  # 對齊 RagSearchRequest 的 top_k 上限
RAG_QUERY_MAX_CHARS = 1000


class FurnitureRetriever(Protocol):
    def search(self, query: str, *, top_k: int = RAG_TOP_K_MAX) -> list[dict]: ...


def _first(row: dict, keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _as_price(row: dict) -> float | None:
    value = _first(row, ("price", "price_twd", "price_ntd"))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flatten_rag_payload(payload: dict) -> list[dict]:
    """把 ``roompilot.rag.search.v1`` 的分組結果攤平成候選列。

    service 回傳的頂層鍵是 ``blocks``（每個需求品項一組），價格與尺寸在
    ``block["hits"][n]["furniture"]``、分數在 ``hit["scores"]``。這裡只做形狀
    轉換：把 furniture 欄位攤到同一層，並把 ``scores.final`` 提到 ``score``，
    欄位名的對應交給 :func:`_as_candidate`。

    其他形狀（已攤平的 ``items``／``results``，或測試注入的假件）原樣回傳。
    """
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        rows = payload.get("items") or payload.get("results") or []
        return [row for row in rows if isinstance(row, dict)]
    flat: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for hit in block.get("hits") or []:
            furniture = hit.get("furniture") if isinstance(hit, dict) else None
            if not isinstance(furniture, dict):
                continue
            scores = hit.get("scores") if isinstance(hit.get("scores"), dict) else {}
            flat.append({**furniture, "score": scores.get("final", 0.0)})
    return flat


def _as_candidate(row: dict) -> CandidateItem | None:
    catalog_id = _first(row, ("catalog_id", "item_id", "id", "uid"))
    name = _first(row, ("name", "name_zh", "title"))
    category = _first(row, ("category", "category_group", "normalized_type", "type"))
    width = _first(row, ("width_cm", "width"))
    depth = _first(row, ("depth_cm", "depth"))
    if not catalog_id or not name or not category or width is None or depth is None:
        return None
    clearance = row.get("clearance")
    return CandidateItem(
        catalog_id=str(catalog_id),
        name=str(name),
        category=str(category),
        width_cm=float(width),
        depth_cm=float(depth),
        height_cm=float(_first(row, ("height_cm", "height"), 80.0)),
        style=_first(row, ("style", "style_primary", "style_id")),
        # 正式型錄的價格欄是 price_twd（見 furniture_catalog_current view）。
        price=_as_price(row),
        score=float(_first(row, ("score", "rerank_score", "similarity"), 0.0)),
        reason=str(_first(row, ("reason", "match_reason"), "")),
        clearance=clearance if isinstance(clearance, dict) else None,
        image_url=_first(row, ("image_url", "front_image_url")),
        # 外觀描述只走到生圖提示詞；缺欄位就留空，不猜、不從名稱拼湊。
        description=str(_first(row, ("description", "rag_description"), "")),
        material=str(_first(row, ("material", "primary_material"), "")),
    )


class SpatialRagRetriever:
    """包 Django FurnitureRagService 的正式檢索器（需 DB、模型快取與 API key）。"""

    def __init__(self, project_dir) -> None:
        self._project_dir = project_dir

    def search(self, query: str, *, top_k: int = RAG_TOP_K_MAX) -> list[dict]:
        try:
            from backend.spatial_data.rag.models import RagSearchRequest
            from backend.spatial_data.rag.service import FurnitureRagService
        except ImportError as exc:
            raise ToolError(f"RAG 依賴未安裝：{exc}", tool="rag_furniture") from exc
        service = FurnitureRagService(self._project_dir)
        try:
            result = service.search(
                RagSearchRequest(
                    query=query[:RAG_QUERY_MAX_CHARS],
                    top_k=min(top_k, RAG_TOP_K_MAX),
                )
            )
        except Exception as exc:  # RagError 家族統一轉成可讀 ToolError
            raise ToolError(f"RAG 檢索失敗：{exc}", tool="rag_furniture") from exc
        return flatten_rag_payload(result if isinstance(result, dict) else {})


def build_room_query(
    requirements: RequirementDoc, room_id: str, room_name: str
) -> str:
    """把單一房間的需求組成自然語言查詢（交給 RAG 端的 LLM parser 解析）。"""
    needs = [
        f"{item.text}x{item.quantity}" if item.quantity > 1 else item.text
        for item in requirements.must_have(room_id)
    ]
    prefs = [
        item.text
        for item in requirements.soft
        if item.room_id in (None, room_id)
    ]
    parts = [f"{room_name}需要：{'、'.join(needs) if needs else '基本家具'}"]
    if requirements.styles:
        parts.append(f"風格：{'、'.join(requirements.styles[:2])}")
    if prefs:
        parts.append(f"偏好：{'、'.join(prefs[:6])}")
    if requirements.budget_total:
        parts.append(f"總預算約 {requirements.budget_total} 元")
    return "；".join(parts)[:RAG_QUERY_MAX_CHARS]


class RagFurnitureTool:
    contract = ToolContract(
        name="rag_furniture",
        description="依需求文件對每個房間執行家具 RAG 檢索與排序，產出候選家具清單。",
        input_schema={
            "type": "object",
            "properties": {
                "requirements": {"type": "object"},
                "layout": {"type": "object"},
                "top_k": {"type": "integer", "maximum": RAG_TOP_K_MAX},
            },
            "required": ["requirements", "layout"],
        },
        output_schema={"type": "object", "description": "CandidateListDoc dict"},
    )

    def __init__(self, retriever: FurnitureRetriever | None = None) -> None:
        self._retriever = retriever

    def run(
        self,
        requirements: RequirementDoc,
        layout: LayoutDoc,
        top_k: int = RAG_TOP_K_MAX,
    ) -> CandidateListDoc:
        if self._retriever is None:
            raise ToolError(
                "家具檢索器未接上（正式環境注入 SpatialRagRetriever；"
                "資料庫不可用時依契約回報，不得改用未驗證資料）",
                tool=self.contract.name,
            )
        doc = CandidateListDoc()
        for room in layout.rooms:
            query = build_room_query(requirements, room.room_id, room.name)
            rows = self._retriever.search(query, top_k=min(top_k, RAG_TOP_K_MAX))
            candidates = [c for c in (_as_candidate(row) for row in rows) if c]
            doc.by_room[room.room_id] = candidates
            doc.retrieval[room.room_id] = {
                "query": query,
                "returned": len(candidates),
                "provider": type(self._retriever).__name__,
            }
        return doc
