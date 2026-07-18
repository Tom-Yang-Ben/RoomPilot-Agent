from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


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
        self.database_path = runtime_dir / "projects.sqlite3"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
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
                    upload_filename TEXT,
                    upload_extension TEXT,
                    upload_mime TEXT,
                    upload_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
            "workflow": json.loads(row["workflow_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

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
    ) -> dict:
        project = self.get_project(project_id)
        merged_workflow = _compact_workflow_value(
            _merge_dict(project["workflow"], workflow or {})
        )
        next_step = current_step or project["current_step"]
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE projects
                SET current_step = ?, workflow_json = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    next_step,
                    json.dumps(merged_workflow, ensure_ascii=False),
                    now,
                    project_id,
                ),
            )
        return self.get_project(project_id)

    def save_upload(
        self,
        project_id: str,
        *,
        filename: str,
        extension: str,
        mime_type: str,
        content: bytes,
    ) -> dict:
        self.get_project(project_id)
        project_dir = self.upload_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_path = project_dir / f"floorplan{extension}"
        stored_path.write_bytes(content)
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE projects
                SET upload_filename = ?, upload_extension = ?, upload_mime = ?,
                    upload_path = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    filename,
                    extension,
                    mime_type,
                    str(stored_path),
                    now,
                    project_id,
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

        imported = 0
        with self._connect() as connection:
            for row in rows:
                current = connection.execute(
                    """
                    SELECT updated_at, upload_filename, upload_extension,
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
                    INSERT OR REPLACE INTO projects (
                        project_id, name, notes, current_step, workflow_json,
                        upload_filename, upload_extension, upload_mime, upload_path,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
                imported += 1
        return imported
