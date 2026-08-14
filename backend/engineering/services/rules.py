"""Rule Service：優先使用既有 backend.engine（幾何/淨空），
再補上 MEP 需求覆蓋與專業待確認檢查。

既有引擎覆蓋：出界、家具重疊、穿牆、開合淨空。
本服務額外標示（非幾何演算）：
- 設備需要的水電系統目前是否已有點位。
- MEP 點位 pending 專業確認。
"""
from __future__ import annotations

from uuid import uuid4

from ..adapters.rule_engine import ExistingRuleEngineAdapter
from ..contracts import (
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    RiskItem,
    RiskResult,
    RiskSummary,
)


class RuleService:
    def __init__(self, engine_adapter: ExistingRuleEngineAdapter | None = None) -> None:
        self.engine_adapter = engine_adapter or ExistingRuleEngineAdapter()

    def validate(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
    ) -> RiskResult:
        del quantities  # 契約保留；目前規則不需要工程量。
        results: list[RiskItem] = list(self.engine_adapter.validate_rooms(snapshot))
        retrieval_by_room = {item.room_id: item for item in retrieval.rooms}

        for room in snapshot.rooms:
            room_retrieval = retrieval_by_room.get(room.room_id)
            if room_retrieval:
                for suggestion in room_retrieval.mep_suggestions:
                    if suggestion.covered_by_existing_point:
                        results.append(
                            RiskItem(
                                id=f"risk_{uuid4().hex[:10]}",
                                room_id=room.room_id,
                                rule="required_mep_point_present",
                                severity="low",
                                passed=True,
                                message=(
                                    f"{suggestion.related_furniture_name} 的 "
                                    f"{suggestion.system} 需求已有相同系統點位"
                                ),
                                related_items=[suggestion.related_furniture_id],
                            )
                        )
                    else:
                        results.append(
                            RiskItem(
                                id=f"risk_{uuid4().hex[:10]}",
                                room_id=room.room_id,
                                rule="missing_required_mep_point",
                                severity="medium",
                                passed=False,
                                message=(
                                    f"{suggestion.related_furniture_name} 需要 "
                                    f"{suggestion.system}，目前未找到相同系統點位"
                                ),
                                related_items=[suggestion.related_furniture_id],
                                professional_confirmation_required=True,
                            )
                        )

            for point in room.mep_points:
                if point.professional_status == "pending":
                    results.append(
                        RiskItem(
                            id=f"risk_{uuid4().hex[:10]}",
                            room_id=room.room_id,
                            rule="mep_professional_confirmation_pending",
                            severity="medium",
                            passed=False,
                            message=f"點位 {point.point_id} 尚待水電專業確認",
                            related_items=[point.point_id],
                            professional_confirmation_required=True,
                        )
                    )

        risk_count = sum(1 for item in results if not item.passed)
        pass_count = sum(1 for item in results if item.passed)
        return RiskResult(
            summary=RiskSummary(
                risk_count=risk_count,
                pass_count=pass_count,
                status="has_risk" if risk_count else "passed",
            ),
            results=results,
        )
