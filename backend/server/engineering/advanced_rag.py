from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from .knowledge import JsonEngineeringKnowledgeRepository
from .models import (
    ConstructionNote,
    MEPSuggestion,
    ProjectSnapshot,
    QuantityResult,
    RetrievalEvidence,
    RetrievalResult,
    RetrievedWorkItem,
    RetrieverStatus,
    RoomRetrieval,
)


SYSTEM_TO_WORK_CODE = {
    "power": "ELEC-POWER-POINT",
    "lighting": "ELEC-LIGHT-POINT",
    "data": "DATA-POINT",
    "cold_water": "PLUMB-COLD-WATER",
    "hot_water": "PLUMB-HOT-WATER",
    "drain": "PLUMB-DRAIN",
    "hvac": "HVAC-CONNECTION",
}


class EngineeringSemanticRetriever(Protocol):
    def search(
        self, query: str, filters: dict[str, Any], top_k: int = 10
    ) -> list[dict[str, Any]]: ...

    def status(self) -> RetrieverStatus: ...


class NoopEngineeringSemanticRetriever:
    """Explicit Mock/Noop adapter; this is not vector retrieval."""

    def search(
        self, query: str, filters: dict[str, Any], top_k: int = 10
    ) -> list[dict[str, Any]]:
        del query, filters, top_k
        return []

    def status(self) -> RetrieverStatus:
        return RetrieverStatus(
            adapter="NoopEngineeringSemanticRetriever",
            mode="noop",
            is_real_vector_retrieval=False,
            message=(
                "Mock／Noop：尚未連接工程知識 Vector Index；目前只有 Structured Retrieval。"
            ),
        )


@dataclass(frozen=True)
class _EquipmentCandidate:
    item_id: str
    name: str
    category: str
    quantity: int
    needs_power: bool = False
    needs_water: bool = False
    needs_drain: bool = False


class AdvancedRAGService:
    """Structured + pluggable vector retrieval, fusion, reranking and evidence."""

    def __init__(
        self,
        knowledge: JsonEngineeringKnowledgeRepository,
        semantic_retriever: EngineeringSemanticRetriever | None = None,
    ) -> None:
        self.knowledge = knowledge
        self.semantic_retriever = (
            semantic_retriever or NoopEngineeringSemanticRetriever()
        )

    def retrieve(
        self, snapshot: ProjectSnapshot, quantities: QuantityResult
    ) -> RetrievalResult:
        quantity_by_room = {item.room_id: item for item in quantities.rooms}
        work_item_by_code = {
            item["work_item_code"]: item for item in self.knowledge.work_items()
        }
        room_results: list[RoomRetrieval] = []

        for room in snapshot.rooms:
            room_quantity = quantity_by_room[room.room_id]
            candidate_evidence: dict[str, list[RetrievalEvidence]] = defaultdict(list)
            waste_rate_by_code: dict[str, float] = {}
            mep_suggestions: list[MEPSuggestion] = []
            suggested_system_counts: dict[str, int] = defaultdict(int)
            direct_work_counts: dict[str, int] = defaultdict(int)
            processed_mep_pairs: set[tuple[str, str]] = set()

            for knowledge_item in work_item_by_code.values():
                if knowledge_item.get("default_for_room") is not True:
                    continue
                code = knowledge_item["work_item_code"]
                candidate_evidence[code].append(
                    RetrievalEvidence(
                        source_id=knowledge_item.get("source_id", code),
                        source_type="default_room_work",
                        score=0.65,
                        confidence=knowledge_item.get("confidence", "medium"),
                        reason=f"{room.name} 的基本進場／完工作業",
                        retrieval_modes=["structured"],
                    )
                )

            for material in room.materials:
                searchable = f"{material.name} {material.description or ''}".lower()
                for mapping in self.knowledge.material_work_mappings():
                    if mapping.get("part") != material.part:
                        continue
                    if not any(
                        str(keyword).lower() in searchable
                        for keyword in mapping.get("keywords") or []
                    ):
                        continue
                    for code in mapping.get("work_item_codes") or []:
                        candidate_evidence[code].append(
                            RetrievalEvidence(
                                source_id=mapping["mapping_id"],
                                source_type="material_work_mapping",
                                score=0.95,
                                confidence=mapping.get("confidence", "medium"),
                                reason=(
                                    f"{room.name} 的 {material.part} 材料包含「{material.name}」"
                                ),
                                retrieval_modes=["structured"],
                            )
                        )
                        waste_rate_by_code[code] = max(
                            waste_rate_by_code.get(code, 0.0), material.waste_rate
                        )

            existing_systems = {point.system for point in room.mep_points}

            def add_mep_requirement(
                equipment: _EquipmentCandidate,
                system: str,
                source_id: str,
                reason: str,
                confidence: str,
            ) -> None:
                pair = (equipment.item_id, system)
                if pair in processed_mep_pairs:
                    return
                processed_mep_pairs.add(pair)
                suggested_system_counts[system] += equipment.quantity
                mep_suggestions.append(
                    MEPSuggestion(
                        room_id=room.room_id,
                        related_item_id=equipment.item_id,
                        related_item_name=equipment.name,
                        system=system,
                        reason=reason,
                        covered_by_existing_point=system in existing_systems,
                        source_id=source_id,
                        confidence=confidence,
                    )
                )
                code = SYSTEM_TO_WORK_CODE.get(system)
                if code:
                    candidate_evidence[code].append(
                        RetrievalEvidence(
                            source_id=source_id,
                            source_type="equipment_mep_mapping",
                            score=0.90,
                            confidence=confidence,
                            reason=f"{equipment.name} 需要 {system} 點位需求",
                            retrieval_modes=["structured"],
                        )
                    )

            candidates = [
                _EquipmentCandidate(
                    item_id=item.furniture_id,
                    name=item.name,
                    category=item.category,
                    quantity=item.quantity,
                    needs_power=item.needs_power,
                    needs_water=item.needs_water,
                    needs_drain=item.needs_drain,
                )
                for item in room.furniture
            ] + [
                _EquipmentCandidate(
                    item_id=item.equipment_id,
                    name=item.name,
                    category=item.category,
                    quantity=item.quantity,
                )
                for item in room.equipment_requirements
            ]

            for equipment in candidates:
                category = equipment.category.strip().lower()
                for mapping in self.knowledge.equipment_mep_mappings():
                    categories = {
                        str(item).strip().lower()
                        for item in mapping.get("categories") or []
                    }
                    if category not in categories:
                        continue
                    for system in mapping.get("required_systems") or []:
                        add_mep_requirement(
                            equipment,
                            system,
                            mapping["mapping_id"],
                            mapping["reason"],
                            mapping.get("confidence", "medium"),
                        )
                    for direct in mapping.get("direct_work_items") or []:
                        code = direct["code"]
                        direct_work_counts[code] += (
                            equipment.quantity
                            if direct.get("quantity_mode") == "furniture_quantity"
                            else 1
                        )
                        candidate_evidence[code].append(
                            RetrievalEvidence(
                                source_id=mapping["mapping_id"],
                                source_type="equipment_work_mapping",
                                score=0.88,
                                confidence=mapping.get("confidence", "medium"),
                                reason=f"{equipment.name} 觸發 {code} 工項",
                                retrieval_modes=["structured"],
                            )
                        )
                if equipment.needs_power:
                    add_mep_requirement(
                        equipment,
                        "power",
                        "FRONTEND-NEEDS-POWER",
                        "前端家具資料標記 needs_power=true",
                        "medium",
                    )
                if equipment.needs_water:
                    add_mep_requirement(
                        equipment,
                        "cold_water",
                        "FRONTEND-NEEDS-WATER",
                        "前端家具資料標記 needs_water=true",
                        "medium",
                    )
                if equipment.needs_drain:
                    add_mep_requirement(
                        equipment,
                        "drain",
                        "FRONTEND-NEEDS-DRAIN",
                        "前端家具資料標記 needs_drain=true",
                        "medium",
                    )

            semantic_query = self._build_semantic_query(room)
            for hit in self.semantic_retriever.search(
                semantic_query,
                filters={"room_type": room.room_type},
                top_k=10,
            ):
                code = hit.get("work_item_code")
                if code not in work_item_by_code:
                    continue
                candidate_evidence[code].append(
                    RetrievalEvidence(
                        source_id=str(hit.get("source_id") or code),
                        source_type=str(hit.get("source_type") or "vector_index"),
                        score=max(0.0, min(1.0, float(hit.get("score") or 0))),
                        confidence=hit.get("confidence", "medium"),
                        reason=str(hit.get("reason") or "工程語意檢索命中"),
                        retrieval_modes=["vector"],
                    )
                )

            ranked_codes = sorted(
                candidate_evidence,
                key=lambda code: (
                    -self._fusion_score(candidate_evidence[code]),
                    code,
                ),
            )
            work_items: list[RetrievedWorkItem] = []
            for code in ranked_codes:
                knowledge_item = work_item_by_code[code]
                quantity = self._resolve_quantity(
                    code=code,
                    quantity_key=knowledge_item["quantity_key"],
                    room_quantity=room_quantity.model_dump(),
                    suggested_system_counts=suggested_system_counts,
                    direct_work_counts=direct_work_counts,
                )
                if quantity <= 0:
                    continue
                work_items.append(
                    RetrievedWorkItem(
                        room_id=room.room_id,
                        work_item_code=code,
                        trade=knowledge_item["trade"],
                        name=knowledge_item["name"],
                        unit=knowledge_item["unit"],
                        quantity_key=knowledge_item["quantity_key"],
                        quantity=round(quantity, 4),
                        waste_rate=waste_rate_by_code.get(code, 0.0),
                        description=knowledge_item["description"],
                        professional_confirmation_required=knowledge_item.get(
                            "professional_confirmation_required", False
                        ),
                        evidence=candidate_evidence[code],
                    )
                )

            room_results.append(
                RoomRetrieval(
                    room_id=room.room_id,
                    semantic_query=semantic_query,
                    work_items=work_items,
                    mep_suggestions=mep_suggestions,
                    construction_notes=self._construction_notes(room),
                )
            )

        return RetrievalResult(
            rooms=room_results,
            semantic_retriever=self.semantic_retriever.status(),
        )

    @staticmethod
    def _fusion_score(evidence: list[RetrievalEvidence]) -> float:
        modes = {mode for item in evidence for mode in item.retrieval_modes}
        return min(
            1.0,
            max(item.score for item in evidence)
            + 0.03 * (len(evidence) - 1)
            + 0.02 * (len(modes) - 1),
        )

    def _construction_notes(self, room) -> list[ConstructionNote]:
        material_text = " ".join(item.name.lower() for item in room.materials)
        notes: list[ConstructionNote] = []
        for item in self.knowledge.construction_knowledge():
            room_types = {str(value) for value in item.get("room_types") or []}
            if "all" not in room_types and room.room_type not in room_types:
                continue
            material = str(item.get("material") or "").lower()
            if material and material not in material_text:
                continue
            notes.append(
                ConstructionNote(
                    room_id=room.room_id,
                    title=item["title"],
                    content=item["content"],
                    source_id=item["source_id"],
                    confidence=item.get("confidence", "medium"),
                    professional_confirmation_required=item.get(
                        "professional_confirmation_required", False
                    ),
                )
            )
        return notes

    @staticmethod
    def _build_semantic_query(room) -> str:
        materials = "、".join(item.name for item in room.materials) or "未選材料"
        equipment = "、".join(
            [item.name for item in room.furniture]
            + [item.name for item in room.equipment_requirements]
        ) or "未選家具設備"
        return (
            f"{room.name}；空間類型 {room.room_type}；風格 {room.style or '未指定'}；"
            f"材料 {materials}；家具設備 {equipment}；尋找適用工程工項與施工注意事項"
        )

    @staticmethod
    def _resolve_quantity(
        *,
        code: str,
        quantity_key: str,
        room_quantity: dict[str, Any],
        suggested_system_counts: dict[str, int],
        direct_work_counts: dict[str, int],
    ) -> float:
        if code in direct_work_counts:
            return float(direct_work_counts[code])
        if quantity_key in room_quantity:
            return float(room_quantity[quantity_key])
        system_keys = {
            "suggested_power_point_count": "power",
            "suggested_lighting_point_count": "lighting",
            "suggested_data_point_count": "data",
            "suggested_cold_water_point_count": "cold_water",
            "suggested_hot_water_point_count": "hot_water",
            "suggested_drain_point_count": "drain",
            "suggested_hvac_point_count": "hvac",
        }
        if quantity_key in system_keys:
            return float(
                suggested_system_counts.get(system_keys[quantity_key], 0)
            )
        return 0.0

