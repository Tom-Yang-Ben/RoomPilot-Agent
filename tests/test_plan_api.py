"""樣品平面圖 API:Demo 基準圖 floor21 必須在清單裡且能解析(見 CLAUDE.md testdata 節)。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roompilot.server.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROOMPILOT_RUNTIME_DIR", str(tmp_path / "runtime"))
    with TestClient(app) as test_client:
        yield test_client


def test_demo_baseline_floor21_is_listed_and_parses(client: TestClient):
    plans = client.get("/api/plans").json()["plans"]
    assert "floor21.dxf" in plans

    response = client.get("/api/plan", params={"name": "floor21.dxf"})
    assert response.status_code == 200
    parsed = response.json()
    assert parsed["wall_segments"]
    assert parsed["width_cm"] > 0
    assert parsed["depth_cm"] > 0


def test_plan_rejects_path_escape_and_unknown_name(client: TestClient):
    assert client.get("/api/plan", params={"name": "../pyproject.toml"}).status_code == 404
    assert client.get("/api/plan", params={"name": "no-such-plan.dxf"}).status_code == 404
