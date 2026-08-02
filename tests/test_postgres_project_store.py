from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.server import main
from backend.server.postgres_project_store import PostgresProjectStore
from backend.server.project_store import (
    ProjectStore,
    ProjectStoreUnavailable,
    ProjectVersionConflict,
    build_project_store,
    project_store_provider,
)
from scripts.project_store import migrate_sqlite_projects_to_postgres as migration


ROOT = Path(__file__).resolve().parents[1]


def test_project_store_provider_is_explicit_and_has_no_silent_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROOMPILOT_PROJECT_STORE_PROVIDER", raising=False)
    (tmp_path / ".env").write_text(
        "ROOMPILOT_PROJECT_STORE_PROVIDER=postgres\n",
        encoding="utf-8",
    )

    assert project_store_provider(tmp_path) == "postgres"
    assert isinstance(
        build_project_store(tmp_path, tmp_path / "runtime"),
        PostgresProjectStore,
    )

    monkeypatch.setenv("ROOMPILOT_PROJECT_STORE_PROVIDER", "sqlite")
    assert project_store_provider(tmp_path) == "sqlite"
    assert isinstance(
        build_project_store(tmp_path, tmp_path / "sqlite-runtime"),
        ProjectStore,
    )

    monkeypatch.setenv("ROOMPILOT_PROJECT_STORE_PROVIDER", "unexpected")
    with pytest.raises(RuntimeError, match="invalid_project_store_provider"):
        project_store_provider(tmp_path)


def test_phase3_schema_uses_jsonb_revision_and_render_foreign_key() -> None:
    schema = migration.DEFAULT_SCHEMA.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS roompilot.projects" in schema
    assert "workflow_json    JSONB NOT NULL" in schema
    assert "projects_revision_nonnegative" in schema
    assert "projects_workflow_object" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.render_outputs" in schema
    assert "REFERENCES roompilot.projects(project_id) ON DELETE CASCADE" in schema
    assert "idx_render_outputs_project_created" in schema


def test_sqlite_migration_dry_run_reads_legacy_revision_as_zero(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                notes TEXT NOT NULL,
                current_step TEXT NOT NULL,
                workflow_json TEXT NOT NULL,
                upload_filename TEXT,
                upload_extension TEXT,
                upload_mime TEXT,
                upload_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, notes, current_step, workflow_json,
                created_at, updated_at
            ) VALUES (
                'legacy-project', 'Legacy', '', 'layout_2d',
                '{"layout_json": {"coordinate_unit": "cm"}}',
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

    snapshot = migration.load_sqlite_snapshot(database)

    assert snapshot["errors"] == []
    assert snapshot["warnings"] == []
    assert len(snapshot["projects"]) == 1
    assert snapshot["projects"][0]["revision"] == 0
    assert snapshot["projects"][0]["workflow_json"] == {
        "layout_json": {"coordinate_unit": "cm"}
    }
    assert snapshot["renders"] == []
    assert migration.main(["--sqlite-db", str(database)]) == 0


def test_sqlite_migration_rejects_invalid_workflow_without_database_write(
    tmp_path: Path,
) -> None:
    database = tmp_path / "invalid.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                notes TEXT NOT NULL,
                current_step TEXT NOT NULL,
                workflow_json TEXT NOT NULL,
                revision INTEGER NOT NULL,
                upload_filename TEXT,
                upload_extension TEXT,
                upload_mime TEXT,
                upload_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO projects VALUES (
                'invalid-project', 'Invalid', '', 'project', '[1, 2, 3]', 0,
                NULL, NULL, NULL, NULL,
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

    snapshot = migration.load_sqlite_snapshot(database)

    assert snapshot["errors"] == [
        "invalid-project: workflow_json 必須是 object"
    ]
    assert migration.main(["--sqlite-db", str(database)]) == 1


def test_project_store_unavailable_maps_to_explicit_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OfflineStore:
        provider = "sqlite"

        @property
        def database_path(self):
            # 帳戶端上線後，授權會比 get_project 更早碰到儲存層。資料庫不可用
            # 時這裡也必須是同一種失敗，否則會變成 401 而不是 503。
            raise ProjectStoreUnavailable("OperationalError")

        def get_project(self, _project_id: str):
            raise ProjectStoreUnavailable("OperationalError")

    monkeypatch.setattr(main, "PROJECT_STORE", OfflineStore())

    response = TestClient(main.app).get("/api/projects/offline")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "project_store_unavailable",
        "message": "PostgreSQL 專案保存目前不可用，請檢查資料庫與 Phase 3 schema。",
        "reason": "OperationalError",
    }


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_PROJECTS") != "1",
    reason="set ROOMPILOT_TEST_POSTGRES_PROJECTS=1 for the live Phase 3 test",
)
def test_live_postgres_project_jsonb_revision_render_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PostgresProjectStore(project_dir=ROOT, runtime_dir=tmp_path / "runtime")
    project_id: str | None = None
    try:
        monkeypatch.setattr(main, "PROJECT_STORE", store)
        client = TestClient(main.app)
        created_response = client.post(
            "/api/projects",
            json={"name": f"Phase 3 {uuid4().hex}", "notes": "PostgreSQL JSONB"},
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()["project"]
        project_id = created["project_id"]
        assert created["revision"] == 0

        updated_response = client.put(
            f"/api/projects/{project_id}/workflow",
            json={
                "expected_revision": 0,
                "current_step": "space_confirmation",
                "workflow": {
                    "layout_json": {
                        "schema_version": "layout.v1",
                        "coordinate_unit": "cm",
                    }
                },
            },
        )
        assert updated_response.status_code == 200, updated_response.text
        updated = updated_response.json()["project"]
        assert updated["revision"] == 1
        assert updated["workflow"]["layout_json"]["coordinate_unit"] == "cm"

        stale = client.put(
            f"/api/projects/{project_id}/workflow",
            json={"expected_revision": 0, "workflow": {"stale": True}},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "project_revision_conflict"

        upload = store.save_upload(
            project_id,
            filename="plan.png",
            extension=".png",
            mime_type="image/png",
            content=b"phase3-upload",
            expected_revision=1,
        )
        assert upload["path"].read_bytes() == b"phase3-upload"
        after_upload = store.get_project(project_id)
        assert after_upload["revision"] == 2

        render, after_render = store.save_render(
            project_id,
            expected_revision=2,
            content=b"phase3-render",
            white_model_version=1,
            viewpoint_version=2,
            style_version=3,
            style_card_id="phase3-card",
            provider="browser_capture",
        )
        assert render["path"].read_bytes() == b"phase3-render"
        assert after_render["revision"] == 3
        assert store.list_renders(project_id)[0]["render_id"] == render["render_id"]

        with store._connection() as connection:
            with store._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT PG_TYPEOF(workflow_json)::TEXT AS workflow_type,
                           workflow_json -> 'layout_json' ->> 'coordinate_unit' AS unit
                    FROM roompilot.projects
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                row = cursor.fetchone()
                assert row == {"workflow_type": "jsonb", "unit": "cm"}
    finally:
        if project_id is not None:
            with store._connection() as connection:
                with store._cursor(connection) as cursor:
                    cursor.execute(
                        "DELETE FROM roompilot.projects WHERE project_id = %s",
                        (project_id,),
                    )
                    assert cursor.rowcount == 1
        store.close()
