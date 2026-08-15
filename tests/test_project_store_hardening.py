from __future__ import annotations

import sqlite3
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.server import main
from backend.server.project_store import (
    MAX_WORKFLOW_BYTES,
    ProjectStore,
    ProjectVersionConflict,
    WorkflowTooLargeError,
)


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


def test_store_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "runtime")

    with store._connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1


def test_expected_revision_rejects_stale_update_without_overwriting(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "runtime")
    project = store.create_project(name="並行編輯驗收")

    saved = store.update_workflow(
        project["project_id"],
        expected_revision=0,
        workflow={"requirements": {"status": "new"}},
    )

    assert saved["revision"] == 1
    with pytest.raises(ProjectVersionConflict) as conflict:
        store.update_workflow(
            project["project_id"],
            expected_revision=0,
            workflow={"requirements": {"status": "stale"}},
        )
    assert conflict.value.project["revision"] == 1
    assert store.get_project(project["project_id"])["workflow"]["requirements"] == {
        "status": "new"
    }


def test_legacy_database_is_migrated_with_revision_zero(tmp_path: Path) -> None:
    runtime = tmp_path / "legacy-runtime"
    runtime.mkdir()
    database = runtime / "projects.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
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
            ) VALUES ('legacy-1', '舊專案', '', 'layout_2d', '{"layout_2d": {"ok": true}}',
                      '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """
        )

    store = ProjectStore(runtime)
    restored = store.get_project("legacy-1")

    assert restored["revision"] == 0
    assert restored["current_step"] == "layout_2d"
    assert restored["workflow"]["layout_2d"]["ok"] is True
    assert store.update_workflow(
        "legacy-1", expected_revision=0, workflow={"restored": True}
    )["revision"] == 1


def test_workflow_payload_over_two_megabytes_is_rejected_atomically(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "runtime")
    project = store.create_project(name="容量驗收")

    with pytest.raises(WorkflowTooLargeError):
        store.update_workflow(
            project["project_id"],
            expected_revision=0,
            workflow={"oversized": "大" * MAX_WORKFLOW_BYTES},
        )

    restored = store.get_project(project["project_id"])
    assert restored["revision"] == 0
    assert "oversized" not in restored["workflow"]


def test_render_history_is_immutable_and_newest_first(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    store = ProjectStore(runtime)
    project = store.create_project(name="渲染歷史驗收")

    first, project = store.save_render(
        project["project_id"],
        expected_revision=0,
        content=_png_bytes(),
        white_model_version=1,
        viewpoint_version=2,
        style_version=3,
        style_card_id="warm-natural-01",
        provider="browser_capture",
    )
    second, project = store.save_render(
        project["project_id"],
        expected_revision=project["revision"],
        content=_png_bytes(),
        white_model_version=1,
        viewpoint_version=2,
        style_version=4,
        style_card_id="bright-clear-01",
        provider="browser_capture",
    )

    restored = ProjectStore(runtime)
    history = restored.list_renders(project["project_id"])
    assert [item["render_id"] for item in history] == [
        second["render_id"],
        first["render_id"],
    ]
    first_path = restored.get_render(
        project["project_id"], first["render_id"]
    )["path"]
    assert first_path.read_bytes() == _png_bytes()
    assert project["revision"] == 2


def test_workflow_api_supports_revision_and_size_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "API 驗收"}).json()["project"]

    saved = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={"expected_revision": 0, "workflow": {"requirements": {"ok": True}}},
    )
    stale = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={"expected_revision": 0, "workflow": {"requirements": {"ok": False}}},
    )
    too_large = client.put(
        f"/api/projects/{project['project_id']}/workflow",
        json={
            "expected_revision": 1,
            "workflow": {"oversized": "大" * MAX_WORKFLOW_BYTES},
        },
    )

    assert saved.status_code == 200
    assert saved.json()["project"]["revision"] == 1
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "project_revision_conflict"
    assert too_large.status_code == 413
    assert too_large.json()["detail"]["code"] == "workflow_too_large"


def test_render_api_saves_lists_and_downloads_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "PROJECT_STORE", ProjectStore(tmp_path / "runtime"))
    client = TestClient(main.app)
    project = client.post("/api/projects", json={"name": "PNG 歷史"}).json()["project"]

    created = client.post(
        f"/api/projects/{project['project_id']}/renders",
        data={
            "expected_revision": 0,
            "white_model_version": 1,
            "viewpoint_version": 1,
            "style_version": 1,
            "style_card_id": "warm-natural-01",
        },
        files={"file": ("proposal.png", _png_bytes(), "image/png")},
    )

    assert created.status_code == 201
    render = created.json()["render"]
    history = client.get(f"/api/projects/{project['project_id']}/renders")
    downloaded = client.get(render["download_url"])
    assert history.status_code == 200
    assert history.json()["renders"][0]["render_id"] == render["render_id"]
    assert downloaded.status_code == 200
    assert downloaded.content == _png_bytes()
