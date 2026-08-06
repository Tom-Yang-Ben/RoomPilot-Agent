"""PostgreSQL JSONB persistence for RoomPilot projects and render metadata."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore, Lock
from typing import Any, Iterator
from uuid import uuid4

from .project_store import (
    MAX_WORKFLOW_BYTES,
    ProjectStoreBusy,
    ProjectStoreUnavailable,
    ProjectVersionConflict,
    WorkflowTooLargeError,
    _compact_workflow_value,
    _merge_dict,
    _read_project_env,
)


def _timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class PostgresProjectStore:
    """ProjectStore-compatible repository backed by PostgreSQL JSONB."""

    provider = "postgres"
    imports_legacy_on_startup = False

    def __init__(self, *, project_dir: Path, runtime_dir: Path) -> None:
        self.project_dir = project_dir
        self.runtime_dir = runtime_dir
        self.upload_dir = runtime_dir / "uploads"
        self.render_dir = runtime_dir / "renders"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._pool_lock = Lock()
        self._pool_value: Any | None = None
        self._pool_permits: BoundedSemaphore | None = None
        self._pool_timeout_seconds = 10.0
        self._database_error: type[Exception] | None = None

    def _setting(self, name: str, default: str = "") -> str:
        file_values = _read_project_env(self.project_dir / ".env")
        return os.getenv(name, file_values.get(name, default)).strip()

    def _database_config(self) -> dict[str, Any]:
        return {
            "host": self._setting("DB_HOST", "localhost"),
            "port": int(self._setting("DB_PORT", "5432")),
            "dbname": self._setting("DB_NAME", "roompilot_db"),
            "user": self._setting("DB_USER", "postgres"),
            "password": self._setting("DB_PASSWORD"),
            "connect_timeout": int(self._setting("DB_CONNECT_TIMEOUT", "3")),
            "sslmode": self._setting("DB_SSLMODE", "disable"),
            "application_name": self._setting(
                "DB_PROJECT_APPLICATION_NAME", "roompilot_project_store"
            ),
        }

    def _pool(self):
        with self._pool_lock:
            if self._pool_value is not None:
                return self._pool_value
            try:
                import psycopg2
                from psycopg2.pool import ThreadedConnectionPool
            except ImportError as exc:  # pragma: no cover - deployment extra
                raise ProjectStoreUnavailable("postgres_driver_unavailable") from exc
            minimum = max(
                1,
                int(
                    self._setting(
                        "DB_PROJECT_POOL_MIN", self._setting("DB_POOL_MIN", "1")
                    )
                ),
            )
            maximum = max(
                minimum,
                int(
                    self._setting(
                        "DB_PROJECT_POOL_MAX", self._setting("DB_POOL_MAX", "24")
                    )
                ),
            )
            try:
                self._pool_value = ThreadedConnectionPool(
                    minimum,
                    maximum,
                    **self._database_config(),
                )
            except psycopg2.Error as exc:
                raise ProjectStoreUnavailable(type(exc).__name__) from exc
            self._pool_permits = BoundedSemaphore(maximum)
            self._pool_timeout_seconds = max(
                0.0, float(self._setting("DB_POOL_TIMEOUT", "10"))
            )
            self._database_error = psycopg2.Error
            return self._pool_value

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        pool = self._pool()
        permits = self._pool_permits
        # getconn() 在池滿時立刻丟 PoolError 而不排隊；先用號誌排隊，等不到
        # 才回報「忙碌」而不是把瞬時滿載說成資料庫不可用。
        if permits is not None and not permits.acquire(
            timeout=self._pool_timeout_seconds
        ):
            raise ProjectStoreBusy(
                f"等待專案資料庫連線超過 {self._pool_timeout_seconds:.0f} 秒"
            )
        try:
            connection = pool.getconn()
        except Exception as exc:
            if permits is not None:
                permits.release()
            raise ProjectStoreUnavailable(type(exc).__name__) from exc
        try:
            connection.autocommit = False
            yield connection
            connection.commit()
        except Exception as exc:
            if not getattr(connection, "closed", True):
                connection.rollback()
            if self._database_error is not None and isinstance(exc, self._database_error):
                raise ProjectStoreUnavailable(type(exc).__name__) from exc
            raise
        finally:
            try:
                pool.putconn(
                    connection,
                    close=bool(getattr(connection, "closed", False)),
                )
            finally:
                if permits is not None:
                    permits.release()

    @staticmethod
    def _cursor(connection: Any):
        try:
            from psycopg2.extras import RealDictCursor
        except ImportError as exc:  # pragma: no cover - deployment extra
            raise ProjectStoreUnavailable("postgres_driver_unavailable") from exc
        return connection.cursor(cursor_factory=RealDictCursor)

    @staticmethod
    def _json(value: Any):
        try:
            from psycopg2.extras import Json
        except ImportError as exc:  # pragma: no cover - deployment extra
            raise ProjectStoreUnavailable("postgres_driver_unavailable") from exc
        return Json(value)

    @staticmethod
    def _project(row: Any) -> dict[str, Any]:
        workflow = row.get("workflow_json") or {}
        if isinstance(workflow, str):
            try:
                workflow = json.loads(workflow)
            except json.JSONDecodeError:
                workflow = {}
        return {
            "project_id": row["project_id"],
            "name": row["name"],
            "notes": row["notes"],
            "current_step": row["current_step"],
            "workflow": workflow if isinstance(workflow, dict) else {},
            "revision": int(row["revision"]),
            "created_at": _timestamp(row["created_at"]),
            "updated_at": _timestamp(row["updated_at"]),
        }

    @staticmethod
    def _render(row: Any) -> dict[str, Any]:
        # RealDictCursor 回傳 dict；欄位缺席代表資料庫尚未套用
        # scripts/project_store 的加法遷移，這裡不掩蓋、直接 KeyError。
        prompt_text = row["prompt_text"]
        design_context = row["design_context_json"]
        if isinstance(design_context, str):
            try:
                design_context = json.loads(design_context)
            except json.JSONDecodeError:
                design_context = None
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
            "created_at": _timestamp(row["created_at"]),
            "room_id": row["room_id"],
            "prompt_text": prompt_text,
            "prompt_hash": (
                hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                if prompt_text
                else None
            ),
            "design_context": design_context if isinstance(design_context, dict) else None,
        }

    @staticmethod
    def _locked_project(cursor: Any, project_id: str) -> dict[str, Any]:
        cursor.execute(
            "SELECT * FROM roompilot.projects WHERE project_id = %s FOR UPDATE",
            (project_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(project_id)
        return PostgresProjectStore._project(row)

    def create_project(self, *, name: str, notes: str = "") -> dict[str, Any]:
        project_id = uuid4().hex
        now = datetime.now(timezone.utc)
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    INSERT INTO roompilot.projects (
                        project_id, name, notes, current_step, workflow_json,
                        revision, created_at, updated_at
                    ) VALUES (%s, %s, %s, 'project', %s, 0, %s, %s)
                    RETURNING *
                    """,
                    (project_id, name, notes, self._json({}), now, now),
                )
                return self._project(cursor.fetchone())

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    "SELECT * FROM roompilot.projects WHERE project_id = %s",
                    (project_id,),
                )
                row = cursor.fetchone()
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
    ) -> dict[str, Any]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                project = self._locked_project(cursor, project_id)
                if expected_revision is not None and project["revision"] != expected_revision:
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
                next_revision = project["revision"] + 1
                now = datetime.now(timezone.utc)
                cursor.execute(
                    """
                    UPDATE roompilot.projects
                    SET current_step = %s, workflow_json = %s, revision = %s,
                        updated_at = %s
                    WHERE project_id = %s AND revision = %s
                    RETURNING *
                    """,
                    (
                        current_step or project["current_step"],
                        self._json(merged_workflow),
                        next_revision,
                        now,
                        project_id,
                        project["revision"],
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ProjectVersionConflict(self._locked_project(cursor, project_id))
                return self._project(row)

    def save_upload(
        self,
        project_id: str,
        *,
        filename: str,
        extension: str,
        mime_type: str,
        content: bytes,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        project_dir = self.upload_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_path = project_dir / f"floorplan{extension}"
        temporary_path = project_dir / f".{uuid4().hex}.upload.tmp"
        backup_path = project_dir / f".{uuid4().hex}.upload.bak"
        temporary_path.write_bytes(content)
        had_previous = stored_path.is_file()
        if had_previous:
            shutil.copy2(stored_path, backup_path)
        try:
            with self._connection() as connection:
                with self._cursor(connection) as cursor:
                    project = self._locked_project(cursor, project_id)
                    if (
                        expected_revision is not None
                        and project["revision"] != expected_revision
                    ):
                        raise ProjectVersionConflict(project)
                    temporary_path.replace(stored_path)
                    cursor.execute(
                        """
                        UPDATE roompilot.projects
                        SET upload_filename = %s, upload_extension = %s,
                            upload_mime = %s, upload_path = %s,
                            revision = %s, updated_at = %s
                        WHERE project_id = %s AND revision = %s
                        """,
                        (
                            filename,
                            extension,
                            mime_type,
                            str(stored_path),
                            project["revision"] + 1,
                            datetime.now(timezone.utc),
                            project_id,
                            project["revision"],
                        ),
                    )
            backup_path.unlink(missing_ok=True)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            if had_previous and backup_path.is_file():
                backup_path.replace(stored_path)
            elif not had_previous:
                stored_path.unlink(missing_ok=True)
            raise
        finally:
            temporary_path.unlink(missing_ok=True)
            backup_path.unlink(missing_ok=True)
        return self.get_upload(project_id)

    def get_upload(self, project_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT upload_filename, upload_extension, upload_mime, upload_path
                    FROM roompilot.projects
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                row = cursor.fetchone()
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
        room_id: str | None = None,
        prompt_text: str | None = None,
        design_context: dict | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        render_id = uuid4().hex
        filename = f"roompilot-{project_id[:8]}-{render_id[:8]}.png"
        project_dir = self.render_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        stored_path = project_dir / filename
        stored_path.write_bytes(content)
        now = datetime.now(timezone.utc)
        try:
            with self._connection() as connection:
                with self._cursor(connection) as cursor:
                    project = self._locked_project(cursor, project_id)
                    if project["revision"] != expected_revision:
                        raise ProjectVersionConflict(project)
                    cursor.execute(
                        """
                        INSERT INTO roompilot.render_outputs (
                            render_id, project_id, white_model_version,
                            viewpoint_version, style_version, style_card_id,
                            provider, mime_type, filename, file_path, byte_size,
                            created_at, room_id, prompt_text, design_context_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'image/png',
                                  %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            render_id,
                            project_id,
                            white_model_version,
                            viewpoint_version,
                            style_version,
                            style_card_id,
                            provider,
                            filename,
                            str(stored_path),
                            len(content),
                            now,
                            room_id,
                            prompt_text,
                            (
                                json.dumps(design_context, ensure_ascii=False)
                                if design_context
                                else None
                            ),
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE roompilot.projects
                        SET revision = %s, updated_at = %s
                        WHERE project_id = %s AND revision = %s
                        """,
                        (expected_revision + 1, now, project_id, expected_revision),
                    )
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
        return self.get_render(project_id, render_id), self.get_project(project_id)

    def list_renders(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM roompilot.render_outputs
                    WHERE project_id = %s
                    ORDER BY created_at DESC, render_id DESC
                    """,
                    (project_id,),
                )
                rows = cursor.fetchall()
        return [self._render(row) for row in rows]

    def get_render(self, project_id: str, render_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            with self._cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM roompilot.render_outputs
                    WHERE project_id = %s AND render_id = %s
                    """,
                    (project_id, render_id),
                )
                row = cursor.fetchone()
        if row is None:
            raise FileNotFoundError(render_id)
        record = self._render(row)
        record["path"] = Path(row["file_path"])
        return record

    def import_runtime(self, _legacy_runtime_dir: Path) -> int:
        """Legacy SQLite import is explicit through the one-time migration tool."""
        return 0

    def close(self) -> None:
        with self._pool_lock:
            pool = self._pool_value
            self._pool_value = None
        if pool is not None:
            pool.closeall()
