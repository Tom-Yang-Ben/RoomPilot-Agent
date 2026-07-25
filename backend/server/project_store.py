from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


MAX_WORKFLOW_BYTES = 2 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_dict(base: dict, update: dict) -> dict:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class ProjectVersionConflict(RuntimeError):
    """呼叫端嘗試把變更重播到較舊的專案版本。"""

    def __init__(self, project: dict) -> None:
        super().__init__("project version conflict")
        self.project = project


class WorkflowTooLargeError(ValueError):
    """The canonical workflow would exceed the persistence size budget."""


_DISPLAY_TEXT_KEYS = {
    "name",
    "name_en",
    "name_zh",
    "name_zh_raw",
    "label",
    "title",
}
_MAX_DISPLAY_TEXT_LENGTH = 512


def _compact_workflow_value(value):
    """Keep corrupted display labels from expanding a persisted project indefinitely."""
    if isinstance(value, list):
        return [_compact_workflow_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    fallback = str(
        value.get("normalized_type")
        or value.get("furniture_id")
        or value.get("id")
        or "未命名項目"
    )
    compacted = {}
    for key, item in value.items():
        if (
            key in _DISPLAY_TEXT_KEYS
            and isinstance(item, str)
            and len(item) > _MAX_DISPLAY_TEXT_LENGTH
        ):
            compacted[key] = fallback[:_MAX_DISPLAY_TEXT_LENGTH]
        else:
            compacted[key] = _compact_workflow_value(item)
    return compacted


class ProjectStore:
    """Small SQLite-backed project store used by the browser workflow."""

    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir
        self.upload_dir = runtime_dir / "uploads"
        self.render_dir = runtime_dir / "renders"
        self.database_path = runtime_dir / "projects.sqlite3"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    current_step TEXT NOT NULL,
                    workflow_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    upload_filename TEXT,
                    upload_extension TEXT,
                    upload_mime TEXT,
                    upload_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "revision" not in columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN revision INTEGER NOT NULL DEFAULT 0"
                )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS render_outputs (
                    render_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    white_model_version INTEGER NOT NULL,
                    viewpoint_version INTEGER NOT NULL,
                    style_version INTEGER NOT NULL,
                    style_card_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                )
                """
            )

    @staticmethod
    def _project(row: sqlite3.Row) -> dict:
        return {
            "project_id": row["project_id"],
            "name": row["name"],
            "notes": row["notes"],
            "current_step": row["current_step"],
            "workflow": ProjectStore._workflow(row["workflow_json"]),
            "revision": int(row["revision"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _workflow(raw: str | None) -> dict:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def create_project(self, *, name: str, notes: str = "") -> dict:
        project_id = uuid4().hex
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, name, notes, current_step, workflow_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, notes, "project", "{}", now, now),
            )
        return self.get_project(project_id)

    def import_project(
        self,
        *,
        name: str,
        notes: str,
        current_step: str,
        workflow: dict,
        upload: dict | None = None,
    ) -> dict:
        project = self.create_project(name=name, notes=notes)
        project_id = project["project_id"]
        try:
            if upload is not None:
                self.save_upload(
                    project_id,
                    filename=upload["filename"],
                    extension=upload["extension"],
                    mime_type=upload["mime_type"],
                    content=upload["content"],
                )
            return self.update_workflow(
                project_id,
                current_step=current_step,
                workflow=workflow,
            )
        except Exception:
            self.delete_project(project_id)
            raise

    def delete_project(self, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM render_outputs WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM projects WHERE project_id = ?",
                (project_id,),
            )
        shutil.rmtree(self.upload_dir / project_id, ignore_errors=True)
        shutil.rmtree(self.render_dir / project_id, ignore_errors=True)

    def get_project(self, project_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        return self._project(row)

    def update_workflow(
        self,
        project_id: str,
        *,
        current_step: str | None = None,
        workflow: dict | None = None,
        expected_revision: int | None = None,
        expected_updated_at: str | None = None,
    ) -> dict:
        with self._connect() as connection:
            # 先取得寫入鎖，再讀取版本，使版本比對與更新成為原子操作。
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            project = self._project(row)
            if (
                expected_revision is not None
                and project["revision"] != expected_revision
            ):
                raise ProjectVersionConflict(project)
            if (
                expected_updated_at is not None
                and project["updated_at"] != expected_updated_at
            ):
                raise ProjectVersionConflict(project)

            merged_workflow = _compact_workflow_value(
                _merge_dict(project["workflow"], workflow or {})
            )
            serialized = json.dumps(merged_workflow, ensure_ascii=False)
            if len(serialized.encode("utf-8")) > MAX_WORKFLOW_BYTES:
                raise WorkflowTooLargeError("workflow exceeds size limit")
            next_step = current_step or project["current_step"]
            now = _utc_now()
            next_revision = project["revision"] + 1
            connection.execute(
                """
                UPDATE projects
                SET current_step = ?, workflow_json = ?, revision = ?, updated_at = ?
                WHERE project_id = ? AND revision = ?
                """,
                (
                    next_step,
                    serialized,
                    next_revision,
                    now,
                    project_id,
                    project["revision"],
                ),
            )
            updated = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return self._project(updated)

    def save_upload(
        self,
        project_id: str,
        *,
        filename: str,
        extension: str,
        mime_type: str,
        content: bytes,
        expected_revision: int | None = None,
    ) -> dict:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise KeyError(project_id)
            project = self._project(row)
            if (
                expected_revision is not None
                and project["revision"] != expected_revision
            ):
                raise ProjectVersionConflict(project)

            project_dir = self.upload_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            stored_path = project_dir / f"floorplan{extension}"
            stored_path.write_bytes(content)
            now = _utc_now()
            connection.execute(
                """
                UPDATE projects
                SET upload_filename = ?, upload_extension = ?, upload_mime = ?,
                    upload_path = ?, revision = ?, updated_at = ?
                WHERE project_id = ? AND revision = ?
                """,
                (
                    filename,
                    extension,
                    mime_type,
                    str(stored_path),
                    project["revision"] + 1,
                    now,
                    project_id,
                    project["revision"],
                ),
            )
        return self.get_upload(project_id)

    def get_upload(self, project_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT upload_filename, upload_extension, upload_mime, upload_path
                FROM projects
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            raise KeyError(project_id)
        if not row["upload_path"]:
            raise FileNotFoundError(project_id)
        return {
            "filename": row["upload_filename"],
            "extension": row["upload_extension"],
            "mime_type": row["upload_mime"],
            "path": Path(row["upload_path"]),
        }

    @staticmethod
    def _render(row: sqlite3.Row) -> dict:
        return {
            "render_id": row["render_id"],
            "project_id": row["project_id"],
            "white_model_version": int(row["white_model_version"]),
            "viewpoint_version": int(row["viewpoint_version"]),
            "style_version": int(row["style_version"]),
            "style_card_id": row["style_card_id"],
            "provider": row["provider"],
            "mime_type": row["mime_type"],
            "filename": row["filename"],
            "byte_size": int(row["byte_size"]),
            "created_at": row["created_at"],
        }

    def save_render(
        self,
        project_id: str,
        *,
        expected_revision: int,
        content: bytes,
        white_model_version: int,
        viewpoint_version: int,
        style_version: int,
        style_card_id: str,
        provider: str,
    ) -> tuple[dict, dict]:
        """Persist a versioned PNG without replacing earlier proposal history."""
        render_id = uuid4().hex
        filename = f"roompilot-{project_id[:8]}-{render_id[:8]}.png"
        project_dir = self.render_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_path = project_dir / filename
        stored_path.write_bytes(content)
        now = _utc_now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM projects WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(project_id)
                project = self._project(row)
                if project["revision"] != expected_revision:
                    raise ProjectVersionConflict(project)
                connection.execute(
                    """
                    INSERT INTO render_outputs (
                        render_id, project_id, white_model_version,
                        viewpoint_version, style_version, style_card_id,
                        provider, mime_type, filename, file_path, byte_size, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        render_id,
                        project_id,
                        white_model_version,
                        viewpoint_version,
                        style_version,
                        style_card_id,
                        provider,
                        "image/png",
                        filename,
                        str(stored_path),
                        len(content),
                        now,
                    ),
                )
                connection.execute(
                    """
                    UPDATE projects
                    SET revision = ?, updated_at = ?
                    WHERE project_id = ? AND revision = ?
                    """,
                    (expected_revision + 1, now, project_id, expected_revision),
                )
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
        return self.get_render(project_id, render_id), self.get_project(project_id)

    def list_renders(self, project_id: str) -> list[dict]:
        self.get_project(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM render_outputs
                WHERE project_id = ?
                ORDER BY created_at DESC, render_id DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._render(row) for row in rows]

    def get_render(self, project_id: str, render_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM render_outputs
                WHERE project_id = ? AND render_id = ?
                """,
                (project_id, render_id),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(render_id)
        record = self._render(row)
        record["path"] = Path(row["file_path"])
        return record

    def import_runtime(self, legacy_runtime_dir: Path) -> int:
        """將舊 worktree 的專案與原圖合併到目前的共用資料庫。"""
        legacy_database = legacy_runtime_dir / "projects.sqlite3"
        if (
            not legacy_database.is_file()
            or legacy_database.resolve() == self.database_path.resolve()
        ):
            return 0

        with sqlite3.connect(legacy_database) as legacy_connection:
            legacy_connection.row_factory = sqlite3.Row
            try:
                rows = legacy_connection.execute("SELECT * FROM projects").fetchall()
            except sqlite3.DatabaseError:
                return 0
            try:
                render_rows = legacy_connection.execute(
                    "SELECT * FROM render_outputs"
                ).fetchall()
            except sqlite3.DatabaseError:
                render_rows = []

        imported = 0
        with self._connect() as connection:
            for row in rows:
                current = connection.execute(
                    """
                    SELECT updated_at, revision, upload_filename, upload_extension,
                           upload_mime, upload_path
                    FROM projects WHERE project_id = ?
                    """,
                    (row["project_id"],),
                ).fetchone()
                if current is not None and current["updated_at"] >= row["updated_at"]:
                    continue

                upload_filename = row["upload_filename"]
                upload_extension = row["upload_extension"]
                upload_mime = row["upload_mime"]
                upload_path = row["upload_path"]
                source_upload = Path(upload_path) if upload_path else None
                if source_upload and source_upload.is_file():
                    target_dir = self.upload_dir / row["project_id"]
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_upload = target_dir / f"floorplan{row['upload_extension']}"
                    shutil.copy2(source_upload, target_upload)
                    upload_path = str(target_upload)
                elif source_upload:
                    upload_filename = current["upload_filename"] if current else None
                    upload_extension = current["upload_extension"] if current else None
                    upload_mime = current["upload_mime"] if current else None
                    upload_path = current["upload_path"] if current else None

                connection.execute(
                    """
                    INSERT INTO projects (
                        project_id, name, notes, current_step, workflow_json,
                        upload_filename, upload_extension, upload_mime, upload_path,
                        revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        name = excluded.name,
                        notes = excluded.notes,
                        current_step = excluded.current_step,
                        workflow_json = excluded.workflow_json,
                        upload_filename = excluded.upload_filename,
                        upload_extension = excluded.upload_extension,
                        upload_mime = excluded.upload_mime,
                        upload_path = excluded.upload_path,
                        revision = excluded.revision,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        row["project_id"],
                        row["name"],
                        row["notes"],
                        row["current_step"],
                        row["workflow_json"],
                        upload_filename,
                        upload_extension,
                        upload_mime,
                        upload_path,
                        int(row["revision"]) if "revision" in row.keys() else 0,
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
                imported += 1

            for render in render_rows:
                project_exists = connection.execute(
                    "SELECT 1 FROM projects WHERE project_id = ?",
                    (render["project_id"],),
                ).fetchone()
                if project_exists is None:
                    continue
                source_render = Path(render["file_path"])
                if not source_render.is_file():
                    continue
                target_dir = self.render_dir / render["project_id"]
                target_dir.mkdir(parents=True, exist_ok=True)
                target_render = target_dir / render["filename"]
                if source_render.resolve() != target_render.resolve():
                    shutil.copy2(source_render, target_render)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO render_outputs (
                        render_id, project_id, white_model_version,
                        viewpoint_version, style_version, style_card_id,
                        provider, mime_type, filename, file_path, byte_size, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        render["render_id"],
                        render["project_id"],
                        render["white_model_version"],
                        render["viewpoint_version"],
                        render["style_version"],
                        render["style_card_id"],
                        render["provider"],
                        render["mime_type"],
                        render["filename"],
                        str(target_render),
                        render["byte_size"],
                        render["created_at"],
                    ),
                )
        return imported
