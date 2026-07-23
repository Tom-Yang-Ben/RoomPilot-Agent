from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


WORKFLOW_SCHEMA_VERSION = 1
MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
_DISPLAY_TEXT_KEYS = {"name", "name_en", "name_zh", "name_zh_raw", "label", "title"}
_MAX_DISPLAY_TEXT_LENGTH = 512


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


def _compact_workflow_value(value):
    """Prevent corrupted display labels from inflating persisted workflows."""
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


class ProjectConflictError(RuntimeError):
    def __init__(self, project: dict) -> None:
        super().__init__("project revision conflict")
        self.project = project


class WorkflowTooLargeError(ValueError):
    pass


class ProjectStore:
    """SQLite-backed canonical store for RoomPilot browser projects."""

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
        try:
            workflow = json.loads(row["workflow_json"] or "{}")
        except json.JSONDecodeError:
            workflow = {}
        return {
            "project_id": row["project_id"],
            "name": row["name"],
            "notes": row["notes"],
            "current_step": row["current_step"],
            "workflow": workflow,
            "revision": int(row["revision"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _initial_workflow(name: str) -> dict:
        return {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "completed": ["project"],
            "data": {"project": {"name": name}},
        }

    def create_project(self, *, name: str, notes: str = "") -> dict:
        project_id = uuid4().hex
        now = _utc_now()
        workflow = self._initial_workflow(name)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    project_id, name, notes, current_step, workflow_json,
                    revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    notes,
                    "upload",
                    json.dumps(workflow, ensure_ascii=False),
                    0,
                    now,
                    now,
                ),
            )
        return self.get_project(project_id)

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
        expected_revision: int,
        current_step: str | None = None,
        workflow: dict | None = None,
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
            if project["revision"] != expected_revision:
                raise ProjectConflictError(project)

            merged_workflow = _compact_workflow_value(
                _merge_dict(project["workflow"], workflow or {})
            )
            serialized = json.dumps(merged_workflow, ensure_ascii=False)
            if len(serialized.encode("utf-8")) > MAX_WORKFLOW_BYTES:
                raise WorkflowTooLargeError("workflow exceeds size limit")

            now = _utc_now()
            next_step = current_step or project["current_step"]
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
                    expected_revision,
                ),
            )
        return self.get_project(project_id)

    def save_upload(
        self,
        project_id: str,
        *,
        expected_revision: int,
        filename: str,
        extension: str,
        mime_type: str,
        content: bytes,
    ) -> tuple[dict, dict]:
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
                raise ProjectConflictError(project)

            project_dir = self.upload_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            stored_path = project_dir / f"floorplan{extension}"
            stored_path.write_bytes(content)

            workflow = dict(project["workflow"])
            data = dict(workflow.get("data") or {})
            for key in (
                "recognition",
                "calibration",
                "space_confirmation",
                "requirements",
                "layout_2d",
                "white_model_3d",
                "viewpoint",
                "style_render",
                "realistic_3d",
            ):
                data.pop(key, None)
                workflow.pop(key, None)
            data["upload"] = {"filename": filename, "extension": extension}
            frontend = dict(workflow.get("frontend3d") or {})
            frontend["source"] = {"kind": "upload", "fileName": filename}
            frontend["furnitureItems"] = []
            workflow.update(
                {
                    "completed": ["project", "upload"],
                    "data": data,
                    "frontend3d": frontend,
                }
            )
            serialized = json.dumps(_compact_workflow_value(workflow), ensure_ascii=False)
            if len(serialized.encode("utf-8")) > MAX_WORKFLOW_BYTES:
                raise WorkflowTooLargeError("workflow exceeds size limit")

            now = _utc_now()
            next_revision = project["revision"] + 1
            connection.execute(
                """
                UPDATE projects
                SET upload_filename = ?, upload_extension = ?, upload_mime = ?,
                    upload_path = ?, current_step = 'upload', workflow_json = ?,
                    revision = ?, updated_at = ?
                WHERE project_id = ? AND revision = ?
                """,
                (
                    filename,
                    extension,
                    mime_type,
                    str(stored_path),
                    serialized,
                    next_revision,
                    now,
                    project_id,
                    expected_revision,
                ),
            )
        return self.get_upload(project_id), self.get_project(project_id)

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
        """原子登記 PNG 與專案 revision；歷史輸出不會被後續重算覆蓋。"""
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
                    raise ProjectConflictError(project)

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
        # 先確認專案存在，避免「不存在」與「尚無輸出」混為同一個回應。
        self.get_project(project_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM render_outputs
                WHERE project_id = ?
                ORDER BY created_at DESC
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
