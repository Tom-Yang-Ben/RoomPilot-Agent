"""第 8 步交付提案：出 PDF 的同時，順手產一份工程估價與排程 XLSX。

只借用 ``backend/engineering`` 的 orchestrator 與 workflow adapter，不走它
原本那套獨立 FastAPI router、SQLite 鎖版與背景工作——本分支的「鎖定」就是
使用者按下「產出設計提案 PDF」那一刻，不需要第二套版本控管。

估價數字來自 ``knowledge/`` 的工項單價與產能表，與家具報價（型錄單價，見
main.py 的 ``_delivery_furniture_lines``）是兩件事，不互相取代。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

FILE_NAME = "estimate_and_schedule.xlsx"

# adapter 丟的是裸錯誤碼，直接印給設計師看沒有意義。
_SKIP_REASONS = {"WORKFLOW_HAS_NO_ROOMS": "第 4 步尚未確認任何房間，無法計算工程量。"}


class _NullDocumentRepo:
    # ponytail: 檔案位置記在 workflow.delivery_proposal，不另開一張 documents 表
    def register_document(self, document, path) -> None:
        pass


@lru_cache(maxsize=1)
def _orchestrator(generated_root: Path):
    from ..engineering.adapters.rule_engine import ExistingRuleEngineAdapter
    from ..engineering.adapters.semantic_retriever import NoopSemanticRetriever
    from ..engineering.config import load_engineering_settings
    from ..engineering.knowledge_repo import JsonKnowledgeRepository
    from ..engineering.services.advanced_rag import AdvancedRAGService
    from ..engineering.services.cost import CostService
    from ..engineering.services.documents import DocumentService
    from ..engineering.services.narrative import TemplateNarrativeService
    from ..engineering.services.orchestrator import EngineeringOrchestrator
    from ..engineering.services.quantity import QuantityService
    from ..engineering.services.rules import RuleService
    from ..engineering.services.schedule import ScheduleService

    settings = load_engineering_settings()
    knowledge = JsonKnowledgeRepository(settings.knowledge_dir)
    return settings, EngineeringOrchestrator(
        quantity_service=QuantityService(),
        rag_service=AdvancedRAGService(knowledge, NoopSemanticRetriever()),
        rule_service=RuleService(ExistingRuleEngineAdapter()),
        cost_service=CostService(knowledge, demo_mode=settings.demo_mode),
        schedule_service=ScheduleService(knowledge, demo_mode=settings.demo_mode),
        narrative_service=TemplateNarrativeService(),
        document_service=DocumentService(
            generated_dir=generated_root,
            template_dir=settings.template_dir,
            repository=_NullDocumentRepo(),
            api_prefix="",
        ),
    )


def build_engineering_estimate(
    project_id: str,
    revision: str,
    workflow: dict[str, Any],
    generated_root: Path,
) -> dict[str, Any]:
    """算出工程估價與排程並寫成 XLSX，回傳可直接存進 workflow 的紀錄。

    任何失敗都降級成 ``status="skipped"``：估價是 PDF 的附加品，不能反過來
    把已經排好版的交付提案一起拖下水。
    """
    try:
        from ..engineering.adapters.workflow_snapshot import snapshot_draft_from_workflow

        settings, orchestrator = _orchestrator(generated_root)
        snapshot = snapshot_draft_from_workflow(
            project_id,
            revision,
            workflow,
            region=settings.default_region,
            pricing_basis_date=date.today(),
        ).model_copy(
            update={
                # 本分支沒有鎖版流程；按下「產出設計提案」即視為設計師確認當下配置。
                "approval_status": "designer_confirmed",
                "confirmed_by": "step8_delivery_proposal",
                "confirmed_at": datetime.now(timezone.utc),
            }
        )
        report = orchestrator.generate(snapshot, ["estimate_xlsx", "report_json"])
        return {
            "status": report.status,
            "file": f"{project_id}/{revision}/{report.package_id}/{FILE_NAME}",
            "package_id": report.package_id,
            "line_count": len(report.estimate.lines),
            "known_subtotal": report.estimate.known_subtotal,
            "estimated_total": report.estimate.estimated_total,
            "estimated_total_days": report.schedule.estimated_total_days,
            "demo_mode": settings.demo_mode,
        }
    except Exception as exc:  # noqa: BLE001 - 估價失敗不該連累 PDF
        logging.getLogger(__name__).exception(
            "engineering estimate failed for project %s", project_id
        )
        # 每個成功時會寫的鍵都要給值：workflow 是深合併，只回兩個鍵的話上一次成功的
        # file 與金額會原封留著，下次重整頁面就會拿舊估價配新 PDF。
        return {
            "status": "skipped",
            "reason": _SKIP_REASONS.get(str(exc), f"{type(exc).__name__}: {exc}"),
            "file": None,
            "package_id": None,
            "line_count": 0,
            "known_subtotal": None,
            "estimated_total": None,
            "estimated_total_days": None,
            "demo_mode": None,
        }
