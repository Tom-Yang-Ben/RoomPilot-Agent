from __future__ import annotations

from time import sleep

import pytest
from fastapi.testclient import TestClient

from backend.server import rag_api
from backend.server.main import app
from backend.spatial_data.rag.errors import RagDisabledError, RagUpstreamError


class _FakeService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def status(self) -> dict:
        return {
            "schema_version": "roompilot.rag.status.v1",
            "enabled": True,
            "ready": True,
            "blockers": [],
            "parser": {"key_configured": True},
            "database": {"current_embeddings": 7_958},
        }

    def search(self, request: object, progress=None) -> dict:
        if self.error:
            raise self.error
        if progress:
            progress(28, "embedding", "embedding")
            progress(62, "reranking", "reranking")
            progress(100, "completed", "completed")
        return {
            "schema_version": "roompilot.rag.search.v1",
            "query": request.query,
            "blocks": [],
        }


def test_rag_page_status_success_and_validation(monkeypatch) -> None:
    monkeypatch.setattr(rag_api, "RAG_SERVICE", _FakeService())
    client = TestClient(app)

    page = client.get("/rag")
    assert page.status_code == 200
    assert "家具 RAG 測試台" in page.text

    status = client.get("/api/rag/status")
    assert status.status_code == 200
    assert status.json()["database"]["current_embeddings"] == 7_958
    assert "server-secret" not in status.text

    response = client.post("/api/rag/search", json={"query": "米色沙發", "top_k": 3})
    assert response.status_code == 200
    assert response.json()["schema_version"] == "roompilot.rag.search.v1"

    assert client.post("/api/rag/search", json={"query": "", "top_k": 3}).status_code == 422
    assert client.post("/api/rag/search", json={"query": "沙發", "top_k": 9}).status_code == 422
    assert client.post("/api/rag/search", json={"query": "沙發", "extra": True}).status_code == 422


def test_rag_api_requires_signed_in_user(monkeypatch, anonymous_client) -> None:
    """五條路由裡只有 `/rag` 頁面公開，資料與執行一律需要身分。

    頁面刻意不掛守衛：瀏覽器導覽不會帶 Authorization，擋在這裡只會變成裸 401，
    使用者到不了登入頁（比照 `/projects`、`/scene`）。rag.js 的 requireSignedIn()
    負責導向。
    """
    monkeypatch.setattr(rag_api, "RAG_SERVICE", _FakeService())
    with rag_api.RAG_JOBS_LOCK:
        jobs_before = len(rag_api.RAG_JOBS)

    assert anonymous_client.get("/rag").status_code == 200
    assert anonymous_client.get("/api/rag/status").status_code == 401
    assert (
        anonymous_client.post("/api/rag/search", json={"query": "沙發", "top_k": 3})
        .status_code
        == 401
    )
    assert (
        anonymous_client.post(
            "/api/rag/search/jobs", json={"query": "沙發", "top_k": 3}
        ).status_code
        == 401
    )
    assert anonymous_client.get("/api/rag/search/jobs/any").status_code == 401
    # 未登入不得建立背景工作，否則單一工作名額仍會被匿名請求佔死。
    with rag_api.RAG_JOBS_LOCK:
        assert len(rag_api.RAG_JOBS) == jobs_before


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (RagDisabledError("disabled"), 503, "rag_disabled"),
        (RagUpstreamError("timeout"), 502, "rag_parser_unavailable"),
    ],
)
def test_rag_api_maps_failures(monkeypatch, error, expected_status, expected_code) -> None:
    monkeypatch.setattr(rag_api, "RAG_SERVICE", _FakeService(error))
    response = TestClient(app).post(
        "/api/rag/search", json={"query": "米色沙發", "top_k": 3}
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert "timeout" not in response.text


def _clear_rag_jobs() -> None:
    with rag_api.RAG_JOBS_LOCK:
        rag_api.RAG_JOBS.clear()


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        payload = client.get(f"/api/rag/search/jobs/{job_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        sleep(0.01)
    raise AssertionError("RAG job did not finish")


def test_rag_job_api_reports_progress_and_result(monkeypatch) -> None:
    _clear_rag_jobs()
    monkeypatch.setattr(rag_api, "RAG_SERVICE", _FakeService())
    client = TestClient(app)

    created = client.post(
        "/api/rag/search/jobs", json={"query": "米色沙發", "top_k": 3}
    )

    assert created.status_code == 202
    assert created.json()["schema_version"] == "roompilot.rag.job.v1"
    completed = _wait_for_job(client, created.json()["job_id"])
    assert completed["status"] == "completed"
    assert completed["progress"] == 100
    assert completed["stage"] == "completed"
    assert completed["elapsed_ms"] >= 0
    assert completed["result"]["schema_version"] == "roompilot.rag.search.v1"
    assert client.get("/api/rag/search/jobs/not-found").status_code == 404


def test_rag_job_api_hides_upstream_failure_detail(monkeypatch) -> None:
    _clear_rag_jobs()
    monkeypatch.setattr(
        rag_api, "RAG_SERVICE", _FakeService(RagUpstreamError("private timeout"))
    )
    client = TestClient(app)

    created = client.post(
        "/api/rag/search/jobs", json={"query": "米色沙發", "top_k": 3}
    )
    failed = _wait_for_job(client, created.json()["job_id"])

    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "rag_parser_unavailable"
    assert "private timeout" not in str(failed)
