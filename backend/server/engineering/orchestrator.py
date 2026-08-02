from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from .advanced_rag import AdvancedRAGService
from .cost import CostService
from .design_narrative import DesignNarrativeService
from .documents import DocumentService
from .furniture_cost import FurnitureEstimateService
from .models import ProjectSnapshot, ReportPayload
from .narrative import TemplateNarrativeService
from .quantity import QuantityService
from .rules import ExistingEngineRuleService
from .schedule import ScheduleService


ProgressCallback = Callable[[int, str], None]


class EngineeringOrchestrator:
    def __init__(
        self,
        *,
        quantity_service: QuantityService,
        rag_service: AdvancedRAGService,
        rule_service: ExistingEngineRuleService,
        cost_service: CostService,
        furniture_estimate_service: FurnitureEstimateService,
        schedule_service: ScheduleService,
        narrative_service: TemplateNarrativeService,
        design_narrative_service: DesignNarrativeService,
        document_service: DocumentService,
        demo_mode: bool,
    ) -> None:
        self.quantity_service = quantity_service
        self.rag_service = rag_service
        self.rule_service = rule_service
        self.cost_service = cost_service
        self.furniture_estimate_service = furniture_estimate_service
        self.schedule_service = schedule_service
        self.narrative_service = narrative_service
        self.design_narrative_service = design_narrative_service
        self.document_service = document_service
        self.demo_mode = demo_mode

    def generate(
        self,
        snapshot: ProjectSnapshot,
        requested_documents: list[str],
        progress: ProgressCallback | None = None,
    ) -> ReportPayload:
        if snapshot.approval_status != "designer_confirmed":
            raise ValueError("REVISION_NOT_LOCKED")

        update = progress or (lambda _value, _stage: None)
        update(10, "quantity")
        quantities = self.quantity_service.calculate(snapshot)
        update(25, "advanced_rag")
        retrieval = self.rag_service.retrieve(snapshot, quantities)
        update(45, "rules")
        risks = self.rule_service.validate(snapshot, quantities, retrieval)
        update(58, "cost")
        estimate = self.cost_service.estimate(snapshot, quantities, retrieval)
        update(66, "furniture_cost")
        furniture_estimate = self.furniture_estimate_service.estimate(snapshot)
        update(74, "schedule")
        schedule = self.schedule_service.plan(snapshot, quantities, retrieval)
        update(80, "narrative")
        narratives = self.narrative_service.generate(
            snapshot,
            quantities,
            retrieval,
            risks,
            estimate,
            schedule,
        )
        update(86, "design_narrative")
        design_narrative = self.design_narrative_service.generate(snapshot)

        snapshot_json = json.dumps(
            snapshot.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        assumptions = list(snapshot.assumptions)
        for item in (
            "本文件為設計與詢價前的初步資料，不是正式施工圖或承攬報價。",
            "生圖只表達設計意圖；工程量以鎖定版幾何資料決定性計算。",
            "未提供的門窗開口尺寸不會自動從影像猜測。",
        ):
            if item not in assumptions:
                assumptions.append(item)
        exclusions = [
            "家具採購金額與工程施工費分開列示，兩者都不含設計監造費與稅金。",
            "不自動判定承重牆或可拆除結構。",
            "不自動決定電力迴路、線徑、管徑與設備負載。",
            "不自動決定排水坡度、防水層規格與試水標準。",
            "不自動決定空調容量、室內外機與冷媒管正式規格。",
            "不取代建築師、室內裝修專業人員、技師、承包商或主管機關核准。",
        ]
        has_warning = (
            risks.summary.risk_count > 0
            or estimate.pending_quote_count > 0
            or furniture_estimate.unpriced_count > 0
            or schedule.unknown_duration_count > 0
        )
        report = ReportPayload(
            package_id=f"pkg_{uuid4().hex[:12]}",
            project_id=snapshot.project_id,
            revision=snapshot.revision,
            generated_at=datetime.now(timezone.utc),
            status="completed_with_warnings" if has_warning else "completed",
            snapshot_hash=snapshot_hash,
            demo_mode=self.demo_mode,
            demo_disclaimer=(
                "示範資料，非正式報價。價格與工率為 DEMO_ONLY 合成資料。"
                if self.demo_mode
                else None
            ),
            snapshot=snapshot,
            quantities=quantities,
            retrieval=retrieval,
            risks=risks,
            estimate=estimate,
            furniture_estimate=furniture_estimate,
            schedule=schedule,
            narratives=narratives,
            design_narrative=design_narrative,
            assumptions=assumptions,
            exclusions=exclusions,
            documents=[],
        )
        update(90, "documents")
        return self.document_service.render(report, requested_documents)

