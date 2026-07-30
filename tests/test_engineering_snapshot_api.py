from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from backend.server.main import app


client = TestClient(app)


def _create_project(name: str) -> dict:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]


def _snapshot(project: dict, revision: str) -> dict:
    return {
        "schema_version": "roompilot.project-snapshot.v1",
        "coordinate_unit": "cm",
        "project_id": project["project_id"],
        "project_name": project["name"],
        "revision": revision,
        "source_project_revision": project["revision"],
        "approval_status": "draft",
        "region": "Taiwan",
        "pricing_basis_date": date.today().isoformat(),
        "rooms": [
            {
                "room_id": "living-1",
                "name": "客廳",
                "room_type": "living_room",
                "geometry": {
                    "length_cm": 420,
                    "width_cm": 360,
                    "height_cm": 270,
                    "opening_area_m2": 2.1,
                    "polygon_cm": [
                        {"x_cm": 0, "y_cm": 0},
                        {"x_cm": 420, "y_cm": 0},
                        {"x_cm": 420, "y_cm": 360},
                        {"x_cm": 0, "y_cm": 360},
                    ],
                },
                "materials": [
                    {
                        "material_id": "spc-oak",
                        "part": "floor",
                        "name": "SPC 木紋地板",
                        "waste_rate": 0.05,
                    }
                ],
                "furniture": [],
                "equipment_requirements": [],
                "mep_points": [],
                "renders": [],
            }
        ],
        "assumptions": [],
    }


def test_snapshot_save_lock_and_locked_revision_is_immutable() -> None:
    project = _create_project("工程文件鎖定測試")
    revision = f"D{project['revision']}"
    payload = _snapshot(project, revision)
    url = f"/api/v1/projects/{project['project_id']}/revisions/{revision}/snapshot"

    saved = client.put(url, json=payload)
    assert saved.status_code == 200
    assert saved.json()["snapshot"]["approval_status"] == "draft"
    assert saved.json()["completeness"]["score"] == 100

    locked = client.post(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/lock",
        json={"confirmed_by": "王設計師"},
    )
    assert locked.status_code == 200
    assert locked.json()["snapshot"]["approval_status"] == "designer_confirmed"
    assert locked.json()["snapshot"]["confirmed_by"] == "王設計師"

    overwritten = client.put(url, json=payload)
    assert overwritten.status_code == 409
    assert (
        overwritten.json()["detail"]["error_code"]
        == "LOCKED_REVISION_CANNOT_BE_OVERWRITTEN"
    )


def test_snapshot_cannot_lock_after_source_project_revision_changes() -> None:
    project = _create_project("工程 snapshot stale 測試")
    revision = f"D{project['revision']}"
    payload = _snapshot(project, revision)
    url = f"/api/v1/projects/{project['project_id']}/revisions/{revision}/snapshot"
    assert client.put(url, json=payload).status_code == 200

    updated = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={
            "expected_revision": project["revision"],
            "current_step": "project",
            "workflow": {"phase1_test": True},
        },
    )
    assert updated.status_code == 200

    locked = client.post(
        f"/api/v1/projects/{project['project_id']}/revisions/{revision}/lock",
        json={"confirmed_by": "王設計師"},
    )
    assert locked.status_code == 409
    assert locked.json()["detail"]["error_code"] == "SNAPSHOT_SOURCE_REVISION_STALE"
    assert locked.json()["detail"]["current_project_revision"] == 1


def test_snapshot_rejects_meter_contract_and_path_mismatch() -> None:
    project = _create_project("工程契約測試")
    payload = _snapshot(project, "D0")
    payload["coordinate_unit"] = "m"
    response = client.put(
        f"/api/v1/projects/{project['project_id']}/revisions/D0/snapshot",
        json=payload,
    )
    assert response.status_code == 422

    payload["coordinate_unit"] = "cm"
    response = client.put(
        f"/api/v1/projects/{project['project_id']}/revisions/D1/snapshot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "PATH_PAYLOAD_MISMATCH"


def test_postgres_schema_contains_engineering_persistence_tables() -> None:
    sql = Path("scripts/project_store/roompilot_project_store_schema.sql").read_text(
        encoding="utf-8"
    )
    for table in (
        "roompilot.engineering_snapshots",
        "roompilot.engineering_jobs",
        "roompilot.engineering_packages",
        "roompilot.engineering_documents",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "designer_confirmed" in sql
    assert "snapshot_hash" in sql
