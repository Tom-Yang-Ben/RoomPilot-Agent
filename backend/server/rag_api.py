"""Bella-owned FastAPI adapter for Django's furniture RAG service."""

from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..paths import STATIC_DIR
from ..spatial_data.rag.errors import (
    RagDatabaseError,
    RagDependencyError,
    RagDisabledError,
    RagUpstreamError,
)
from ..spatial_data.rag.models import RagSearchRequest
from ..spatial_data.rag.service import FurnitureRagService
from .auth.dependencies import current_user


PROJECT_DIR = Path(__file__).resolve().parents[2]
RAG_SERVICE = FurnitureRagService(PROJECT_DIR)
# `/rag` 頁面與 `/api/rag/*` 分成兩個 router：瀏覽器導覽不會帶 Authorization，
# 頁面本身掛守衛只會變成裸 401，使用者永遠到不了登入頁。所以頁面比照
# `/projects`、`/scene` 保持公開（HTML 本身沒有資料），身分由 rag.js 的
# requireSignedIn() 導向登入，實際的資料與 RAG 執行則全部擋在 api_router。
router = APIRouter()
api_router = APIRouter(dependencies=[Depends(current_user)])
RAG_JOBS: dict[str, dict] = {}
RAG_JOBS_LOCK = Lock()
RAG_JOB_TTL_SECONDS = 60 * 60
RAG_JOB_MAX_ACTIVE = 1


def _service_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "retryable": status_code in {502, 503},
        },
    )


def _error_details(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, RagDisabledError):
        return 503, exc.code, "RAG 功能目前未啟用。"
    if isinstance(exc, RagDependencyError):
        return 503, exc.code, "RAG 必要套件、模型或設定尚未就緒。"
    if isinstance(exc, RagDatabaseError):
        return 503, exc.code, "PostgreSQL 家具向量目前無法使用。"
    if isinstance(exc, RagUpstreamError):
        return 502, exc.code, "RAG 查詢解析服務目前失敗，請稍後再試。"
    return 500, "rag_internal_error", "RAG 搜尋發生未預期錯誤。"


def _cleanup_jobs(now: float) -> None:
    expired = [
        job_id
        for job_id, job in RAG_JOBS.items()
        if job["status"] in {"completed", "failed"}
        and now - float(job.get("finished_at") or job["created_at"])
        > RAG_JOB_TTL_SECONDS
    ]
    for job_id in expired:
        RAG_JOBS.pop(job_id, None)


def _update_job(job_id: str, **changes: object) -> None:
    with RAG_JOBS_LOCK:
        job = RAG_JOBS.get(job_id)
        if job is not None:
            job.update(changes)


def _run_job(job_id: str, request: RagSearchRequest) -> None:
    _update_job(
        job_id,
        status="running",
        progress=1,
        stage="starting",
        message="RAG 工作已啟動。",
        started_at=monotonic(),
    )

    def report(percent: int, stage: str, message: str) -> None:
        _update_job(
            job_id,
            progress=percent,
            stage=stage,
            message=message,
        )

    try:
        result = RAG_SERVICE.search(request, progress=report)
    except Exception as exc:
        status_code, code, message = _error_details(exc)
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            message=message,
            error={"code": code, "message": message, "http_status": status_code},
            finished_at=monotonic(),
        )
    else:
        _update_job(
            job_id,
            status="completed",
            progress=100,
            stage="completed",
            message="RAG 檢索完成。",
            result=result,
            finished_at=monotonic(),
        )


def _job_snapshot(job: dict) -> dict:
    started_at = float(job.get("started_at") or job["created_at"])
    ended_at = float(job.get("finished_at") or monotonic())
    payload = {
        "schema_version": "roompilot.rag.job.v1",
        "job_id": job["job_id"],
        "status": job["status"],
        "progress": int(job["progress"]),
        "stage": job["stage"],
        "message": job["message"],
        "elapsed_ms": round(max(0.0, ended_at - started_at) * 1000, 1),
    }
    if job.get("result") is not None:
        payload["result"] = job["result"]
    if job.get("error") is not None:
        payload["error"] = job["error"]
    return payload


@router.get("/rag")
def rag_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "rag.html", headers={"Cache-Control": "no-store"})


@api_router.get("/api/rag/status")
def rag_status() -> dict:
    return RAG_SERVICE.status()


@api_router.post("/api/rag/search")
def rag_search(request: RagSearchRequest) -> dict:
    try:
        return RAG_SERVICE.search(request)
    except (RagDisabledError, RagDependencyError, RagDatabaseError, RagUpstreamError) as exc:
        status_code, code, message = _error_details(exc)
        raise _service_error(status_code, code, message) from exc


@api_router.post("/api/rag/search/jobs", status_code=202)
def create_rag_search_job(request: RagSearchRequest) -> dict:
    now = monotonic()
    with RAG_JOBS_LOCK:
        _cleanup_jobs(now)
        active_jobs = sum(
            job["status"] in {"queued", "running"} for job in RAG_JOBS.values()
        )
        if active_jobs >= RAG_JOB_MAX_ACTIVE:
            raise _service_error(
                429,
                "rag_job_capacity_reached",
                "已有 RAG 搜尋正在執行，請等待目前工作完成。",
            )
        job_id = uuid4().hex
        RAG_JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "queued",
            "message": "已排入 RAG 搜尋佇列。",
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
        snapshot = _job_snapshot(RAG_JOBS[job_id])
    Thread(target=_run_job, args=(job_id, request), daemon=True).start()
    return snapshot


@api_router.get("/api/rag/search/jobs/{job_id}")
def get_rag_search_job(job_id: str) -> dict:
    with RAG_JOBS_LOCK:
        job = RAG_JOBS.get(job_id)
        if job is None:
            raise _service_error(
                404,
                "rag_job_not_found",
                "RAG 搜尋工作不存在或已過期。",
            )
        return _job_snapshot(dict(job))


# 守衛過的路由必須在頁面 router 之後併入，main.py 的 include_router(rag_router)
# 語意不變。
router.include_router(api_router)
