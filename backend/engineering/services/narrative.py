"""Narrative Service：只寫白話摘要，不計算任何數字。

【MOCK／模板版】目前是無外部 API 也能跑的模板實作；之後可換成 LLM Adapter
（ports.LLMClient），但 LLM 也只能改寫文字，所有數字一律引用計算結果。
"""
from __future__ import annotations

from ..contracts import (
    EstimateResult,
    NarrativeResult,
    ProjectSnapshot,
    QuantityResult,
    RetrievalResult,
    RiskResult,
    ScheduleResult,
)


class TemplateNarrativeService:
    def generate(
        self,
        snapshot: ProjectSnapshot,
        quantities: QuantityResult,
        retrieval: RetrievalResult,
        risks: RiskResult,
        estimate: EstimateResult,
        schedule: ScheduleResult,
    ) -> NarrativeResult:
        work_item_count = sum(len(room.work_items) for room in retrieval.rooms)
        return NarrativeResult(
            design_summary=(
                f"本次以 {snapshot.revision} 設計版本為基準，共整理 "
                f"{len(snapshot.rooms)} 個房間，總淨地坪約 "
                f"{quantities.total_floor_area_m2:.2f} m²。"
            ),
            construction_summary=(
                f"依材料、家具設備與房間條件檢索出 {work_item_count} 筆初步工程工項。"
                "工項仍需依現場複丈、材料規格與施工方式確認。"
            ),
            cost_summary=(
                f"目前有 {estimate.pending_quote_count} 筆工項缺少可用單價，"
                "因此系統不虛構總價，並標示為待廠商詢價。"
                if estimate.pending_quote_count
                else f"依已確認單價計算的初步總額為 {estimate.estimated_total:.0f} TWD。"
            ),
            schedule_summary=(
                f"依現有工率與依賴資料，初步工期約 {schedule.estimated_total_days} 天；"
                "此結果尚需考量材料交期、社區時段及實際工班。"
                if schedule.estimated_total_days is not None
                else "目前工率資料不足，尚不能形成完整工期。"
            ),
            risk_summary=(
                f"風險檢查發現 {risks.summary.risk_count} 筆待確認事項，"
                "文件中已保留房間、關聯家具與專業確認狀態。"
                if risks.summary.risk_count
                else "目前規則檢查未發現待確認風險。"
            ),
        )
