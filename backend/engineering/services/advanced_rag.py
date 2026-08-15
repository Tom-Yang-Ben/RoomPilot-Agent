"""Advanced RAG（Hybrid Retrieval）：查詢理解 → 路由 → 結構化檢索 →
向量檢索 Adapter → 融合 → 重排 → 證據。

- 精確資料（材料/類別/單位/工項代碼/數量）一律走 structured retrieval。
- 語意描述（工法、注意事項）走 SemanticRetriever Adapter；目前接的是
  NoopSemanticRetriever（未接真實 Vector Index，明確標示為 Mock）。
- 本模組不計算價格、工期、碰撞；工程量只從 QuantityResult 取值。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..adapters.ports import SemanticRetriever
from ..contracts import (
    MEPSuggestion,
    ProjectSnapshot,
    QuantityResult,
    RetrievalEvidence,
    RetrievalResult,
    RetrievedWorkItem,
    RoomRetrieval,
)
from ..knowledge_repo import JsonKnowledgeRepository


PART_QUANTITY_KEY = {
    "floor": "floor_area_m2",
    "wall": "net_wall_area_m2",
    "ceiling": "ceiling_area_m2",
}

PART_ZH = {"floor": "地坪", "wall": "牆面", "ceiling": "天花"}

SYSTEM_TO_WORK_CODE = {
    "power": "ELEC-POWER-POINT",
    "lighting": "ELEC-LIGHT-POINT",
    "data": "DATA-POINT",
    "cold_water": "PLUMB-COLD-WATER",
    "hot_water": "PLUMB-HOT-WATER",
    "drain": "PLUMB-DRAIN",
    "hvac": "HVAC-CONNECTION",
}


class AdvancedRAGService:
    def __init__(
        self,
        knowledge: JsonKnowledgeRepository,
        semantic_retriever: SemanticRetriever,
    ) -> None:
        self.knowledge = knowledge
        self.semantic_retriever = semantic_retriever

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

            # 每個房間都需要的基本工項（保護、完工清潔等）。
            for knowledge_item in work_item_by_code.values():
                if not knowledge_item.get("default_for_room", False):
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

            # Query understanding + structured material retrieval.
            unmapped_materials: list[Any] = []
            for material in room.materials:
                searchable = f"{material.name} {material.description or ''}".lower()
                matched = False
                for mapping in self.knowledge.material_work_mappings():
                    if mapping.get("part") != material.part:
                        continue
                    if not any(
                        keyword.lower() in searchable for keyword in mapping["keywords"]
                    ):
                        continue
                    matched = True
                    for code in mapping["work_item_codes"]:
                        candidate_evidence[code].append(
                            RetrievalEvidence(
                                source_id=mapping["mapping_id"],
                                source_type="material_work_mapping",
                                score=0.95,
                                confidence=mapping.get("confidence", "medium"),
                                reason=f"{room.name} 的 {material.part} 材料包含「{material.name}」",
                                retrieval_modes=["structured"],
                            )
                        )
                        waste_rate_by_code[code] = max(
                            waste_rate_by_code.get(code, 0.0), material.waste_rate
                        )
                if not matched:
                    unmapped_materials.append(material)

            existing_systems = {point.system for point in room.mep_points}

            def add_mep_requirement(
                furniture: Any,
                system: str,
                source_id: str,
                reason: str,
                confidence: str,
            ) -> None:
                pair = (furniture.furniture_id, system)
                if pair in processed_mep_pairs:
                    return
                processed_mep_pairs.add(pair)
                suggested_system_counts[system] += furniture.quantity
                mep_suggestions.append(
                    MEPSuggestion(
                        room_id=room.room_id,
                        related_furniture_id=furniture.furniture_id,
                        related_furniture_name=furniture.name,
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
                            score=0.9,
                            confidence=confidence,
                            reason=f"{furniture.name} 需要 {system} 點位需求",
                            retrieval_modes=["structured"],
                        )
                    )

            # Equipment → MEP needs and direct installation work.
            for furniture in room.furniture:
                category = furniture.category.strip().lower()
                for mapping in self.knowledge.equipment_mep_mappings():
                    categories = {
                        str(item).strip().lower() for item in mapping["categories"]
                    }
                    if category not in categories:
                        continue
                    for system in mapping.get("required_systems", []):
                        add_mep_requirement(
                            furniture=furniture,
                            system=system,
                            source_id=mapping["mapping_id"],
                            reason=mapping["reason"],
                            confidence=mapping.get("confidence", "medium"),
                        )
                    for direct in mapping.get("direct_work_items", []):
                        code = direct["code"]
                        quantity = (
                            furniture.quantity
                            if direct.get("quantity_mode") == "furniture_quantity"
                            else 1
                        )
                        direct_work_counts[code] += quantity
                        candidate_evidence[code].append(
                            RetrievalEvidence(
                                source_id=mapping["mapping_id"],
                                source_type="equipment_work_mapping",
                                score=0.88,
                                confidence=mapping.get("confidence", "medium"),
                                reason=f"{furniture.name} 觸發 {code} 安裝工項",
                                retrieval_modes=["structured"],
                            )
                        )

                # 即使分類字典未命中，也保留前端已標記的基本設備需求。
                if furniture.needs_power:
                    add_mep_requirement(
                        furniture, "power", "FRONTEND-NEEDS-POWER",
                        "前端家具資料標記 needs_power=true", "medium",
                    )
                if furniture.needs_water:
                    add_mep_requirement(
                        furniture, "cold_water", "FRONTEND-NEEDS-WATER",
                        "前端家具資料標記 needs_water=true", "medium",
                    )
                if furniture.needs_drain:
                    add_mep_requirement(
                        furniture, "drain", "FRONTEND-NEEDS-DRAIN",
                        "前端家具資料標記 needs_drain=true", "medium",
                    )

            # Vector retrieval adapter；目前為 Noop（未接真實 Vector Index）。
            semantic_query = self._build_semantic_query(room)
            semantic_hits = self.semantic_retriever.search(
                semantic_query,
                filters={"room_type": room.room_type},
                top_k=10,
            )
            for hit in semantic_hits:
                code = hit.get("work_item_code")
                if code not in work_item_by_code:
                    continue
                score = max(0.0, min(1.0, float(hit.get("score", 0.0))))
                candidate_evidence[code].append(
                    RetrievalEvidence(
                        source_id=str(hit.get("source_id", code)),
                        source_type=str(hit.get("source_type", "vector_index")),
                        score=score,
                        confidence=hit.get("confidence", "medium"),
                        reason=str(hit.get("reason", "語意檢索命中")),
                        retrieval_modes=["vector"],
                    )
                )

            # Fusion + deterministic re-ranking：以最高證據分數排序，
            # 正式環境可換 cross-encoder 而不動 API 契約。
            ranked_codes = sorted(
                candidate_evidence,
                key=lambda code: (
                    -max(item.score for item in candidate_evidence[code]),
                    code,
                ),
            )

            work_items: list[RetrievedWorkItem] = []
            for code in ranked_codes:
                knowledge_item = work_item_by_code.get(code)
                if not knowledge_item:
                    continue
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

            # 對不到工項的材料必須自己列出來。少了這一段，該工種會整批從估價單消失，
            # 而封面照樣印「待詢價工項 0」與一個看起來完整的總價——比報錯更危險。
            work_items.extend(
                self._unmapped_material_items(
                    room, unmapped_materials, room_quantity.model_dump()
                )
            )

            room_results.append(
                RoomRetrieval(
                    room_id=room.room_id,
                    semantic_query=semantic_query,
                    work_items=work_items,
                    mep_suggestions=mep_suggestions,
                )
            )

        return RetrievalResult(rooms=room_results)

    @staticmethod
    def _unmapped_material_items(
        room: Any, materials: list[Any], room_quantity: dict[str, Any]
    ) -> list[RetrievedWorkItem]:
        """材料查無工項對照時，補一列沒有單價的工項。

        cost.py 只要看到 subtotal=None 就會把它算進 pending_quote_count，
        estimated_total 隨之變成 None——漏算因此會出現在文件上，而不是靜靜消失。
        """
        items: list[RetrievedWorkItem] = []
        for material in materials:
            quantity_key = PART_QUANTITY_KEY.get(material.part)
            quantity = float(room_quantity.get(quantity_key) or 0) if quantity_key else 0
            if quantity <= 0:
                continue
            part_zh = PART_ZH.get(material.part, material.part)
            items.append(
                RetrievedWorkItem(
                    room_id=room.room_id,
                    work_item_code=f"UNMAPPED-{material.part.upper()}",
                    trade="待確認",
                    name=f"{part_zh}材料「{material.name}」查無對應工項，未計價",
                    unit="m2",
                    quantity_key=quantity_key,
                    quantity=round(quantity, 4),
                    waste_rate=0.0,
                    description=(
                        "knowledge/material_work_mappings.json 沒有這個材料的工項對照。"
                        "請補上對照，或這一項改由人工詢價後併入。"
                    ),
                    professional_confirmation_required=True,
                    evidence=[
                        RetrievalEvidence(
                            source_id=material.material_id,
                            source_type="unmapped_material",
                            score=0.0,
                            confidence="low",
                            reason=f"{room.name} 的 {material.part} 材料未命中任何 material_work_mapping",
                            retrieval_modes=["structured"],
                        )
                    ],
                )
            )
        return items

    @staticmethod
    def _build_semantic_query(room: Any) -> str:
        materials = "、".join(item.name for item in room.materials) or "未選材料"
        furniture = "、".join(item.name for item in room.furniture) or "未選家具"
        return (
            f"{room.name}；空間類型 {room.room_type}；風格 {room.style or '未指定'}；"
            f"材料 {materials}；家具設備 {furniture}；尋找適用工程工項與施工注意事項"
        )

    @staticmethod
    def _resolve_quantity(
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
            return float(suggested_system_counts.get(system_keys[quantity_key], 0))
        return 0.0
