from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..contracts import (
    DocumentManifest,
    JobStatus,
    ProjectSnapshot,
    ReportPayload,
)


class ProjectRepository(Protocol):
    def save_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot: ...

    def get_snapshot(self, project_id: str, revision: str) -> ProjectSnapshot | None: ...

    def lock_revision(
        self, project_id: str, revision: str, confirmed_by: str
    ) -> ProjectSnapshot: ...

    def save_job(self, job: JobStatus) -> None: ...

    def get_job(self, job_id: str) -> JobStatus | None: ...

    def save_package(self, report: ReportPayload) -> None: ...

    def get_package(self, package_id: str) -> ReportPayload | None: ...

    def register_document(self, document: DocumentManifest, path: Path) -> None: ...

    def get_document_path(self, document_id: str) -> Path | None: ...


class SemanticRetriever(Protocol):
    """Vector Retrieval Adapter 介面。

    正式接法：以既有 Vector Index（如家具 VLM 描述、工法文件 embedding）
    實作 search()，回傳 [{work_item_code, source_id, source_type, score,
    confidence, reason}]。
    """

    def search(
        self, query: str, filters: dict[str, Any], top_k: int = 10
    ) -> list[dict[str, Any]]: ...


class LLMClient(Protocol):
    def generate_json(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]: ...
