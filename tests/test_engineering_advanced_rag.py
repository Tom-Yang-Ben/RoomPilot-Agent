from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from backend.server.engineering.advanced_rag import AdvancedRAGService
from backend.server.engineering.knowledge import (
    JsonEngineeringKnowledgeRepository,
    validate_engineering_knowledge,
)
from backend.server.engineering.models import ProjectSnapshot, RetrieverStatus
from backend.server.engineering.quantity import QuantityService


KNOWLEDGE_DIR = Path("backend/catalog/data/engineering")


def _snapshot() -> ProjectSnapshot:
    return ProjectSnapshot.model_validate(
        {
            "project_id": "rag-project",
            "project_name": "RAG 測試",
            "revision": "D2",
            "source_project_revision": 2,
            "pricing_basis_date": date.today().isoformat(),
            "rooms": [
                {
                    "room_id": "living-1",
                    "name": "客廳",
                    "room_type": "living_room",
                    "style": "scandinavian",
                    "geometry": {
                        "length_cm": 420,
                        "width_cm": 360,
                        "height_cm": 270,
                    },
                    "materials": [
                        {
                            "material_id": "spc-oak",
                            "part": "floor",
                            "name": "SPC 木紋地板",
                            "waste_rate": 0.08,
                        }
                    ],
                    "furniture": [
                        {
                            "furniture_id": "tv-1",
                            "name": "電視",
                            "category": "television",
                            "width_cm": 120,
                            "depth_cm": 10,
                            "height_cm": 80,
                        }
                    ],
                    "equipment_requirements": [
                        {
                            "equipment_id": "washer-requirement",
                            "name": "洗衣機",
                            "category": "washing_machine",
                            "quantity": 1,
                            "source": "questionnaire",
                        }
                    ],
                    "mep_points": [],
                    "renders": [],
                }
            ],
        }
    )


def test_engineering_knowledge_contract_and_structured_retrieval() -> None:
    repository = JsonEngineeringKnowledgeRepository(KNOWLEDGE_DIR)
    counts = validate_engineering_knowledge(repository)
    assert counts == {
        "materials": 12,
        "work_items": 29,
        "material_mappings": 14,
        "equipment_mappings": 13,
        "price_records": 29,
        "productivity_records": 29,
        "task_dependencies": 45,
        "construction_documents": 10,
        "sources": 4,
        "production_material_templates": 12,
        "production_price_templates": 29,
        "production_productivity_templates": 29,
    }

    assert all(
        item["status"] == "pending_quote"
        and item["is_synthetic"] is False
        and item["material_unit_price"] is None
        and item["labor_unit_price"] is None
        and item["other_unit_price"] is None
        for item in repository.production_price_templates()
    )
    assert all(
        item["is_synthetic"] is False
        and item["daily_productivity"] is None
        and item["crew_count"] is None
        for item in repository.production_productivity_templates()
    )
    with (KNOWLEDGE_DIR / "source_registry.csv").open(
        "r", encoding="utf-8", newline=""
    ) as file:
        csv_source_ids = {row["source_id"] for row in csv.DictReader(file)}
    assert csv_source_ids == {
        item["source_id"] for item in repository.source_registry()
    }

    snapshot = _snapshot()
    result = AdvancedRAGService(repository).retrieve(
        snapshot, QuantityService().calculate(snapshot)
    )
    room = result.rooms[0]
    by_code = {item.work_item_code: item for item in room.work_items}
    assert "FLOOR-SPC" in by_code
    assert by_code["FLOOR-SPC"].waste_rate == 0.08
    assert by_code["FLOOR-SPC"].evidence[0].source_id == "MAP-MAT-001"
    assert {item.system for item in room.mep_suggestions} >= {"power", "data"}
    assert all(item.source_id for item in room.mep_suggestions)
    assert any(item.title == "SPC 地板施工前置條件" for item in room.construction_notes)
    assert result.semantic_retriever.mode == "noop"
    assert result.semantic_retriever.is_real_vector_retrieval is False
    assert "Mock" in result.semantic_retriever.message


class _VectorRetriever:
    def search(self, query, filters, top_k=10):
        assert query
        assert filters == {"room_type": "living_room"}
        assert top_k == 10
        return [
            {
                "work_item_code": "PAINT-WALL",
                "source_id": "vector-doc-42",
                "source_type": "engineering_vector_index",
                "score": 0.91,
                "confidence": "high",
                "reason": "cross-encoder rerank 命中牆面整理語意",
            }
        ]

    def status(self):
        return RetrieverStatus(
            adapter="TestVectorRetriever",
            mode="vector",
            is_real_vector_retrieval=True,
            message="test vector adapter",
        )


def test_vector_adapter_evidence_survives_fusion_and_reranking() -> None:
    repository = JsonEngineeringKnowledgeRepository(KNOWLEDGE_DIR)
    snapshot = _snapshot()
    result = AdvancedRAGService(repository, _VectorRetriever()).retrieve(
        snapshot, QuantityService().calculate(snapshot)
    )
    paint = next(
        item
        for item in result.rooms[0].work_items
        if item.work_item_code == "PAINT-WALL"
    )
    evidence = next(item for item in paint.evidence if "vector" in item.retrieval_modes)
    assert evidence.source_id == "vector-doc-42"
    assert evidence.confidence == "high"
    assert evidence.reason == "cross-encoder rerank 命中牆面整理語意"
    assert result.semantic_retriever.is_real_vector_retrieval is True
