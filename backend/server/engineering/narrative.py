from __future__ import annotations

from .models import (
    EstimateResult,
    NarrativeResult,
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    RiskResult,
    ScheduleResult,
)


class TemplateNarrativeService:
    """Deterministic copy only; no LLM calculations or factual invention."""

    def generate(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
        risks: RiskResult,
        estimate: EstimateResult,
        schedule: ScheduleResult,
    ) -> NarrativeResult:
        work_count = sum(len(room.work_items) for room in retrieval.rooms)
        mep_count = sum(len(room.mep_suggestions) for room in retrieval.rooms)
        return NarrativeResult(
            design_summary=(
                f"本提案依設計師鎖定版本 {snapshot.revision} 整理 "
                f"{len(snapshot.rooms)} 個房間；所有尺寸與文件共用同一份 ProjectSnapshot。"
            ),
            construction_summary=(
                f"決定性工程量包含地坪 {quantities.total_floor_area_m2:.2f} m²、"
                f"天花 {quantities.total_ceiling_area_m2:.2f} m²、牆面淨面積 "
                f"{quantities.total_net_wall_area_m2:.2f} m²；Advanced RAG 結構化檢索"
                f"得到 {work_count} 個工項與 {mep_count} 個水電／空調需求建議。"
            ),
            cost_summary=(
                f"已知小計為 TWD {estimate.known_subtotal:,.0f}；"
                f"待詢價工項 {estimate.pending_quote_count} 項。"
            ),
            schedule_summary=(
                f"初步總工期為 {schedule.estimated_total_days} 日；"
                f"缺工率資料 {schedule.unknown_duration_count} 項。"
                if schedule.estimated_total_days is not None
                else f"目前有 {schedule.unknown_duration_count} 項缺少正式工率，不能形成總工期。"
            ),
            risk_summary=(
                f"規則結果有 {risks.summary.risk_count} 項風險／待確認、"
                f"{risks.summary.pass_count} 項通過；承重牆、迴路、線徑、管徑、"
                "排水坡度、防水規格、空調容量與法規核准均未自動判定。"
            ),
        )

