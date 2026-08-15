"""Engineering Orchestrator：鎖定 Snapshot → 各 deterministic service →
ReportPayload → 文件。所有文件都由同一份 ReportPayload 產生。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from ..contracts import ProjectSnapshot, ReportPayload
from .advanced_rag import AdvancedRAGService
from .cost import CostService
from .documents import DocumentService
from .narrative import TemplateNarrativeService
from .quantity import QuantityService
from .rules import RuleService
from .schedule import ScheduleService


class EngineeringOrchestrator:
    def __init__(
        self,
        quantity_service: QuantityService,
        rag_service: AdvancedRAGService,
        rule_service: RuleService,
        cost_service: CostService,
        schedule_service: ScheduleService,
        narrative_service: TemplateNarrativeService,
        document_service: DocumentService,
    ) -> None:
        self.quantity_service = quantity_service
        self.rag_service = rag_service
        self.rule_service = rule_service
        self.cost_service = cost_service
        self.schedule_service = schedule_service
        self.narrative_service = narrative_service
        self.document_service = document_service

    def generate(
        self,
        snapshot: ProjectSnapshot,
        requested_documents: list[str],
        on_progress=None,
    ) -> ReportPayload:
        if snapshot.approval_status != "designer_confirmed":
            raise ValueError("REVISION_NOT_LOCKED")

        def progress(value: int) -> None:
            if on_progress:
                on_progress(value)

        quantities = self.quantity_service.calculate(snapshot)
        progress(25)
        retrieval = self.rag_service.retrieve(snapshot, quantities)
        progress(45)
        risks = self.rule_service.validate(snapshot, quantities, retrieval)
        progress(60)
        estimate = self.cost_service.estimate(snapshot, quantities, retrieval)
        progress(70)
        schedule = self.schedule_service.plan(snapshot, quantities, retrieval)
        progress(80)
        narratives = self.narrative_service.generate(
            snapshot,
            quantities,
            retrieval,
            risks,
            estimate,
            schedule,
        )
        progress(90)

        has_warning = (
            risks.summary.risk_count > 0
            or estimate.pending_quote_count > 0
            or schedule.unknown_duration_count > 0
        )
        package_id = f"pkg_{uuid4().hex[:12]}"
        snapshot_json = json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()

        assumptions = list(snapshot.assumptions)
        standard_assumptions = [
            "本文件為設計與詢價前的初步資料，不是正式施工圖或承攬報價。",
            "水電迴路、線徑、管徑、容量、排水坡度與施工路徑由專業人員確認。",
            "生圖僅表達設計意圖；工程量以鎖定版幾何資料計算。",
            "承重牆、結構補強、防水規格與法規核准不在本系統自動判定範圍。",
        ]
        for item in standard_assumptions:
            if item not in assumptions:
                assumptions.append(item)

        report = ReportPayload(
            package_id=package_id,
            project_id=snapshot.project_id,
            revision=snapshot.revision,
            generated_at=datetime.now(timezone.utc),
            status="completed_with_warnings" if has_warning else "completed",
            snapshot_hash=snapshot_hash,
            snapshot=snapshot,
            quantities=quantities,
            retrieval=retrieval,
            risks=risks,
            estimate=estimate,
            schedule=schedule,
            narratives=narratives,
            assumptions=assumptions,
            documents=[],
        )
        return self.document_service.render(report, requested_documents)
