from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ..auth.dependencies import (
    current_user,
    get_user_store,
    project_editor,
    project_reader,
)
from .advanced_rag import AdvancedRAGService, NoopEngineeringSemanticRetriever
from .cost import CostService
from .design_knowledge import (
    JsonDesignKnowledgeRepository,
    validate_design_knowledge,
)
from .design_narrative import DesignNarrativeService, StyleCardPaletteRepository
from .documents import DocumentService, WorkbookGenerationUnavailable
from .furniture_cost import (
    FurnitureEstimateService,
    build_furniture_price_provider,
)
from .knowledge import (
    JsonEngineeringKnowledgeRepository,
    validate_engineering_knowledge,
)
from .models import (
    EngineeringPackageRequest,
    JobStatus,
    LockRevisionRequest,
    ProjectSnapshot,
    ReportPayload,
    SnapshotEnvelope,
    snapshot_completeness,
)
from .narrative import TemplateNarrativeService
from .orchestrator import EngineeringOrchestrator
from .quantity import QuantityService
from .repository import (
    EngineeringRepository,
    LockedRevisionError,
    SnapshotSourceConflict,
)
from .rules import ExistingEngineRuleService
from .schedule import ScheduleService


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_engineering_router(
    *, project_store_getter: Callable[[], Any], project_dir: Path
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["engineering-documents"])
    repository = EngineeringRepository(project_store_getter)
    knowledge = JsonEngineeringKnowledgeRepository(
        project_dir / "backend" / "catalog" / "data" / "engineering"
    )
    design_knowledge = JsonDesignKnowledgeRepository(
        project_dir / "backend" / "catalog" / "data" / "design"
    )
    style_palettes = StyleCardPaletteRepository(
        project_dir / "backend" / "catalog" / "data" / "taiwan_style_cards.json"
    )
    generated_dir = project_dir / ".runtime" / "engineering"

    def _require_project_access(project_id: str, user: dict[str, Any]) -> None:
        """job / package / document 只帶自己的 id，授權要回推它所屬的專案。

        少了這一步，任何登入者都能靠 id 取得別人的估價與成果文件。
        """
        if user.get("role") == "admin":
            return
        role = get_user_store().get_project_role(
            project_id=project_id, user_id=user["user_id"]
        )
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROJECT_NOT_FOUND", "message": "找不到專案"},
            )

    def build_orchestrator() -> EngineeringOrchestrator:
        demo_mode = _env_bool("ROOMPILOT_DEMO_MODE", default=False)
        return EngineeringOrchestrator(
            quantity_service=QuantityService(),
            rag_service=AdvancedRAGService(
                knowledge,
                NoopEngineeringSemanticRetriever(),
            ),
            rule_service=ExistingEngineRuleService(),
            cost_service=CostService(knowledge, demo_mode=demo_mode),
            furniture_estimate_service=FurnitureEstimateService(
                build_furniture_price_provider(project_dir)
            ),
            schedule_service=ScheduleService(knowledge, demo_mode=demo_mode),
            narrative_service=TemplateNarrativeService(),
            design_narrative_service=DesignNarrativeService(
                design_knowledge, style_palettes
            ),
            document_service=DocumentService(
                generated_dir=generated_dir,
                repository=repository,
                api_prefix="/api/v1",
            ),
            demo_mode=demo_mode,
        )

    @router.get("/engineering/health")
    def health() -> dict[str, Any]:
        try:
            counts = validate_engineering_knowledge(knowledge)
            knowledge_status = "ready"
        except (OSError, ValueError) as exc:
            counts = {}
            knowledge_status = f"invalid:{type(exc).__name__}"
        try:
            design_counts = validate_design_knowledge(design_knowledge)
            design_status = "ready"
        except (OSError, ValueError) as exc:
            design_counts = {}
            design_status = f"invalid:{type(exc).__name__}"
        return {
            "status": "ok",
            "snapshot_store": getattr(project_store_getter(), "provider", "unknown"),
            "demo_mode": _env_bool("ROOMPILOT_DEMO_MODE", default=False),
            "knowledge": {
                "provider": "versioned_json_seed",
                "status": knowledge_status,
                "counts": counts,
            },
            "design_knowledge": {
                "provider": "versioned_json_seed",
                "status": design_status,
                "counts": design_counts,
                # 設計語彙是團隊編纂，報告會據此標示 medium confidence。
                "authority": "internal_editorial",
            },
            "furniture_pricing": {
                "provider": build_furniture_price_provider(project_dir).provider_name,
            },
            "advanced_rag": {
                "structured_retrieval": "active",
                "semantic_retriever": "noop_not_vector_retrieval",
            },
            "xlsx": {
                "adapter": "@oai/artifact-tool",
                "node": os.getenv("ROOMPILOT_ARTIFACT_NODE", "node"),
                "module_path_configured": bool(
                    os.getenv("ROOMPILOT_ARTIFACT_TOOL_MODULES", "").strip()
                ),
            },
        }

    @router.put(
        "/projects/{project_id}/revisions/{revision}/snapshot",
        response_model=SnapshotEnvelope,
    )
    def save_snapshot(
        project_id: str,
        revision: str,
        snapshot: ProjectSnapshot,
        _user: dict[str, Any] = Depends(project_editor),
    ) -> SnapshotEnvelope:
        if snapshot.project_id != project_id or snapshot.revision != revision:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "PATH_PAYLOAD_MISMATCH",
                    "message": "path 的 project_id / revision 必須與 payload 一致",
                },
            )
        try:
            saved = repository.save_snapshot(snapshot)
        except LockedRevisionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "LOCKED_REVISION_CANNOT_BE_OVERWRITTEN",
                    "message": "已鎖定版本不可覆寫；請建立新 revision",
                },
            ) from exc
        except SnapshotSourceConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "SNAPSHOT_SOURCE_REVISION_STALE",
                    "message": "專案已更新，請由最新 state 建立新 revision",
                    "current_project_revision": exc.current_project_revision,
                },
            ) from exc
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROJECT_NOT_FOUND", "message": "找不到專案"},
            ) from exc
        return SnapshotEnvelope(
            snapshot=saved,
            completeness=snapshot_completeness(saved),
        )

    @router.get(
        "/projects/{project_id}/revisions/{revision}/snapshot",
        response_model=SnapshotEnvelope,
    )
    def get_snapshot(
        project_id: str,
        revision: str,
        _user: dict[str, Any] = Depends(project_reader),
    ) -> SnapshotEnvelope:
        snapshot = repository.get_snapshot(project_id, revision)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "SNAPSHOT_NOT_FOUND",
                    "message": f"找不到 {project_id}/{revision} 的 snapshot",
                },
            )
        return SnapshotEnvelope(
            snapshot=snapshot,
            completeness=snapshot_completeness(snapshot),
        )

    @router.post(
        "/projects/{project_id}/engineering-packages",
        response_model=JobStatus,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_engineering_package(
        project_id: str,
        body: EngineeringPackageRequest,
        background_tasks: BackgroundTasks,
        _user: dict[str, Any] = Depends(project_editor),
    ) -> JobStatus:
        snapshot = repository.get_snapshot(project_id, body.revision)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "SNAPSHOT_NOT_FOUND",
                    "message": f"找不到 {project_id}/{body.revision} 的 snapshot",
                },
            )
        if snapshot.approval_status != "designer_confirmed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "REVISION_NOT_LOCKED",
                    "message": f"{body.revision} 尚未被設計師鎖定",
                },
            )
        job = JobStatus(
            job_id=f"job_{uuid4().hex[:12]}",
            project_id=project_id,
            revision=body.revision,
            status="queued",
            progress=0,
            stage="queued",
        )
        repository.save_job(job)
        background_tasks.add_task(
            run_generation_job,
            job.job_id,
            snapshot,
            body.documents,
        )
        return repository.get_job(job.job_id) or job

    def run_generation_job(
        job_id: str,
        snapshot: ProjectSnapshot,
        requested_documents: list[str],
    ) -> None:
        job = repository.get_job(job_id)
        if job is None:
            return
        job.status = "processing"
        job.progress = 5
        job.stage = "starting"
        repository.save_job(job)

        def update(progress: int, stage_name: str) -> None:
            current = repository.get_job(job_id)
            if current is None:
                return
            current.status = "processing"
            current.progress = progress
            current.stage = stage_name
            repository.save_job(current)

        try:
            report = build_orchestrator().generate(
                snapshot,
                requested_documents,
                progress=update,
            )
            repository.save_package(report)
            job = repository.get_job(job_id) or job
            job.status = report.status
            job.progress = 100
            job.stage = "completed"
            job.package_id = report.package_id
            job.documents = report.documents
            job.error_code = None
            job.error = None
        except WorkbookGenerationUnavailable as exc:
            job = repository.get_job(job_id) or job
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.error_code = "XLSX_ADAPTER_UNAVAILABLE"
            job.error = str(exc)[:1000]
        except Exception as exc:  # noqa: BLE001 - background task boundary
            job = repository.get_job(job_id) or job
            job.status = "failed"
            job.progress = 100
            job.stage = "failed"
            job.error_code = "ENGINEERING_PACKAGE_FAILED"
            job.error = f"{type(exc).__name__}: {exc}"[:1000]
        finally:
            job.updated_at = datetime.now(timezone.utc)
            repository.save_job(job)

    @router.get("/jobs/{job_id}", response_model=JobStatus)
    def get_job(
        job_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> JobStatus:
        job = repository.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "JOB_NOT_FOUND", "message": "找不到 job"},
            )
        _require_project_access(job.project_id, user)
        return job

    @router.get("/packages/{package_id}", response_model=ReportPayload)
    def get_package(
        package_id: str,
        user: dict[str, Any] = Depends(current_user),
    ) -> ReportPayload:
        report = repository.get_package(package_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "PACKAGE_NOT_FOUND",
                    "message": "找不到 engineering package",
                },
            )
        _require_project_access(report.project_id, user)
        return report

    @router.get("/documents/{document_id}/download")
    def download_document(
        document_id: str,
        preview: bool = False,
        user: dict[str, Any] = Depends(current_user),
    ) -> FileResponse:
        owning_project = repository.get_document_project_id(document_id)
        if owning_project is not None:
            _require_project_access(owning_project, user)
        path = repository.get_document_path(document_id)
        root = generated_dir.resolve()
        if (
            path is None
            or not path.is_file()
            or not path.is_relative_to(root)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "DOCUMENT_NOT_FOUND",
                    "message": "找不到文件",
                },
            )
        media_type = {
            ".json": "application/json",
            ".html": "text/html; charset=utf-8",
            ".xlsx": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        }.get(path.suffix.lower(), "application/octet-stream")
        if preview and path.suffix.lower() == ".html":
            return FileResponse(
                path=path,
                media_type=media_type,
                headers={"Content-Disposition": f'inline; filename="{path.name}"'},
            )
        return FileResponse(path=path, filename=path.name, media_type=media_type)

    @router.post(
        "/projects/{project_id}/revisions/{revision}/lock",
        response_model=SnapshotEnvelope,
    )
    def lock_revision(
        project_id: str,
        revision: str,
        body: LockRevisionRequest,
        _user: dict[str, Any] = Depends(project_editor),
    ) -> SnapshotEnvelope:
        try:
            snapshot = repository.lock_revision(project_id, revision, body.confirmed_by)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "SNAPSHOT_NOT_FOUND",
                    "message": f"找不到 {project_id}/{revision} 的 snapshot",
                },
            ) from exc
        except SnapshotSourceConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "SNAPSHOT_SOURCE_REVISION_STALE",
                    "message": "專案在 snapshot 保存後已更新，請建立新 revision",
                    "current_project_revision": exc.current_project_revision,
                },
            ) from exc
        return SnapshotEnvelope(
            snapshot=snapshot,
            completeness=snapshot_completeness(snapshot),
        )

    # Keep the repository on router state so focused tests and later phases can use
    # the same configured persistence adapter without adding a second app.
    router.engineering_repository = repository  # type: ignore[attr-defined]
    return router
