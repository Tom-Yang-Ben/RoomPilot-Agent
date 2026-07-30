from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Iterator

from .models import DocumentManifest, JobStatus, ProjectSnapshot, ReportPayload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LockedRevisionError(RuntimeError):
    pass


class SnapshotSourceConflict(RuntimeError):
    def __init__(self, current_project_revision: int) -> None:
        super().__init__("snapshot source project revision is stale")
        self.current_project_revision = current_project_revision


class EngineeringRepository:
    """Persist engineering artifacts in the configured RoomPilot project database."""

    def __init__(self, project_store_getter: Callable[[], Any]) -> None:
        self._project_store_getter = project_store_getter
        self._initialized_sqlite_paths: set[Path] = set()
        self._initialize_lock = RLock()

    def _store(self):
        return self._project_store_getter()

    @contextmanager
    def _sqlite(self) -> Iterator[sqlite3.Connection]:
        store = self._store()
        database_path = Path(store.database_path).resolve()
        self._initialize_sqlite(database_path)
        connection = sqlite3.connect(database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_sqlite(self, database_path: Path) -> None:
        with self._initialize_lock:
            if database_path in self._initialized_sqlite_paths:
                return
            connection = sqlite3.connect(database_path, timeout=10)
            try:
                connection.executescript(
                    """
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS engineering_snapshots (
                        project_id TEXT NOT NULL,
                        design_revision TEXT NOT NULL,
                        source_project_revision INTEGER NOT NULL,
                        snapshot_json TEXT NOT NULL,
                        approval_status TEXT NOT NULL,
                        locked_by TEXT,
                        locked_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (project_id, design_revision),
                        FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS engineering_jobs (
                        job_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        design_revision TEXT NOT NULL,
                        job_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS engineering_packages (
                        package_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        design_revision TEXT NOT NULL,
                        snapshot_hash TEXT NOT NULL,
                        report_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS engineering_documents (
                        document_id TEXT PRIMARY KEY,
                        package_id TEXT NOT NULL,
                        document_type TEXT NOT NULL,
                        file_name TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        byte_size INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(package_id) REFERENCES engineering_packages(package_id) ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_engineering_jobs_project_revision
                        ON engineering_jobs(project_id, design_revision, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_engineering_documents_package
                        ON engineering_documents(package_id, created_at);
                    """
                )
                connection.commit()
            finally:
                connection.close()
            self._initialized_sqlite_paths.add(database_path)

    @staticmethod
    def _snapshot_json(snapshot: ProjectSnapshot) -> str:
        return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)

    def _assert_current_source(self, snapshot: ProjectSnapshot) -> None:
        project = self._store().get_project(snapshot.project_id)
        if int(project["revision"]) != snapshot.source_project_revision:
            raise SnapshotSourceConflict(int(project["revision"]))

    def save_snapshot(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        if snapshot.approval_status != "draft":
            raise LockedRevisionError("snapshot save only accepts draft")
        self._assert_current_source(snapshot)
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            return self._save_snapshot_postgres(snapshot)
        now = _utc_now().isoformat()
        with self._sqlite() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT approval_status, created_at
                FROM engineering_snapshots
                WHERE project_id = ? AND design_revision = ?
                """,
                (snapshot.project_id, snapshot.revision),
            ).fetchone()
            if row and row["approval_status"] == "designer_confirmed":
                raise LockedRevisionError("LOCKED_REVISION_CANNOT_BE_OVERWRITTEN")
            created_at = row["created_at"] if row else now
            connection.execute(
                """
                INSERT INTO engineering_snapshots (
                    project_id, design_revision, source_project_revision,
                    snapshot_json, approval_status, locked_by, locked_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'draft', NULL, NULL, ?, ?)
                ON CONFLICT(project_id, design_revision) DO UPDATE SET
                    source_project_revision = excluded.source_project_revision,
                    snapshot_json = excluded.snapshot_json,
                    approval_status = 'draft',
                    locked_by = NULL,
                    locked_at = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    snapshot.project_id,
                    snapshot.revision,
                    snapshot.source_project_revision,
                    self._snapshot_json(snapshot),
                    created_at,
                    now,
                ),
            )
        return self.get_snapshot(snapshot.project_id, snapshot.revision) or snapshot

    def _save_snapshot_postgres(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        store = self._store()
        now = _utc_now()
        with store._connection() as connection:  # noqa: SLF001 - provider adapter boundary
            with store._cursor(connection) as cursor:  # noqa: SLF001
                cursor.execute(
                    """
                    SELECT approval_status
                    FROM roompilot.engineering_snapshots
                    WHERE project_id = %s AND design_revision = %s
                    FOR UPDATE
                    """,
                    (snapshot.project_id, snapshot.revision),
                )
                row = cursor.fetchone()
                if row and row["approval_status"] == "designer_confirmed":
                    raise LockedRevisionError("LOCKED_REVISION_CANNOT_BE_OVERWRITTEN")
                cursor.execute(
                    """
                    INSERT INTO roompilot.engineering_snapshots (
                        project_id, design_revision, source_project_revision,
                        snapshot_json, approval_status, locked_by, locked_at,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, 'draft', NULL, NULL, %s, %s)
                    ON CONFLICT(project_id, design_revision) DO UPDATE SET
                        source_project_revision = EXCLUDED.source_project_revision,
                        snapshot_json = EXCLUDED.snapshot_json,
                        approval_status = 'draft',
                        locked_by = NULL,
                        locked_at = NULL,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        snapshot.project_id,
                        snapshot.revision,
                        snapshot.source_project_revision,
                        store._json(snapshot.model_dump(mode="json")),  # noqa: SLF001
                        now,
                        now,
                    ),
                )
        return self.get_snapshot(snapshot.project_id, snapshot.revision) or snapshot

    def get_snapshot(self, project_id: str, revision: str) -> ProjectSnapshot | None:
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        SELECT snapshot_json
                        FROM roompilot.engineering_snapshots
                        WHERE project_id = %s AND design_revision = %s
                        """,
                        (project_id, revision),
                    )
                    row = cursor.fetchone()
            value = row["snapshot_json"] if row else None
        else:
            with self._sqlite() as connection:
                row = connection.execute(
                    """
                    SELECT snapshot_json FROM engineering_snapshots
                    WHERE project_id = ? AND design_revision = ?
                    """,
                    (project_id, revision),
                ).fetchone()
            value = row["snapshot_json"] if row else None
        if value is None:
            return None
        if isinstance(value, str):
            value = json.loads(value)
        return ProjectSnapshot.model_validate(value)

    def lock_revision(
        self, project_id: str, revision: str, confirmed_by: str
    ) -> ProjectSnapshot:
        snapshot = self.get_snapshot(project_id, revision)
        if snapshot is None:
            raise KeyError("SNAPSHOT_NOT_FOUND")
        self._assert_current_source(snapshot)
        if snapshot.approval_status == "designer_confirmed":
            return snapshot
        locked = snapshot.model_copy(
            update={
                "approval_status": "designer_confirmed",
                "confirmed_by": confirmed_by,
                "confirmed_at": _utc_now(),
            },
            deep=True,
        )
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        UPDATE roompilot.engineering_snapshots
                        SET snapshot_json = %s, approval_status = 'designer_confirmed',
                            locked_by = %s, locked_at = %s, updated_at = %s
                        WHERE project_id = %s AND design_revision = %s
                          AND approval_status = 'draft'
                        """,
                        (
                            store._json(locked.model_dump(mode="json")),  # noqa: SLF001
                            confirmed_by,
                            locked.confirmed_at,
                            locked.confirmed_at,
                            project_id,
                            revision,
                        ),
                    )
        else:
            with self._sqlite() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE engineering_snapshots
                    SET snapshot_json = ?, approval_status = 'designer_confirmed',
                        locked_by = ?, locked_at = ?, updated_at = ?
                    WHERE project_id = ? AND design_revision = ?
                      AND approval_status = 'draft'
                    """,
                    (
                        self._snapshot_json(locked),
                        confirmed_by,
                        locked.confirmed_at.isoformat(),
                        locked.confirmed_at.isoformat(),
                        project_id,
                        revision,
                    ),
                )
        return self.get_snapshot(project_id, revision) or locked

    def save_job(self, job: JobStatus) -> None:
        job.updated_at = _utc_now()
        payload = job.model_dump(mode="json")
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        INSERT INTO roompilot.engineering_jobs (
                            job_id, project_id, design_revision, job_json,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT(job_id) DO UPDATE SET
                            job_json = EXCLUDED.job_json,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            job.job_id,
                            job.project_id,
                            job.revision,
                            store._json(payload),  # noqa: SLF001
                            job.created_at,
                            job.updated_at,
                        ),
                    )
            return
        with self._sqlite() as connection:
            connection.execute(
                """
                INSERT INTO engineering_jobs (
                    job_id, project_id, design_revision, job_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    job_json = excluded.job_json,
                    updated_at = excluded.updated_at
                """,
                (
                    job.job_id,
                    job.project_id,
                    job.revision,
                    json.dumps(payload, ensure_ascii=False),
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                ),
            )

    def get_job(self, job_id: str) -> JobStatus | None:
        value = self._read_json_column(
            sqlite_query="SELECT job_json FROM engineering_jobs WHERE job_id = ?",
            postgres_query=(
                "SELECT job_json FROM roompilot.engineering_jobs WHERE job_id = %s"
            ),
            params=(job_id,),
            column="job_json",
        )
        return JobStatus.model_validate(value) if value is not None else None

    def save_package(self, report: ReportPayload) -> None:
        payload = report.model_dump(mode="json")
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        INSERT INTO roompilot.engineering_packages (
                            package_id, project_id, design_revision, snapshot_hash,
                            report_json, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT(package_id) DO UPDATE SET report_json = EXCLUDED.report_json
                        """,
                        (
                            report.package_id,
                            report.project_id,
                            report.revision,
                            report.snapshot_hash,
                            store._json(payload),  # noqa: SLF001
                            report.generated_at,
                        ),
                    )
            return
        with self._sqlite() as connection:
            connection.execute(
                """
                INSERT INTO engineering_packages (
                    package_id, project_id, design_revision, snapshot_hash,
                    report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET report_json = excluded.report_json
                """,
                (
                    report.package_id,
                    report.project_id,
                    report.revision,
                    report.snapshot_hash,
                    json.dumps(payload, ensure_ascii=False),
                    report.generated_at.isoformat(),
                ),
            )

    def get_package(self, package_id: str) -> ReportPayload | None:
        value = self._read_json_column(
            sqlite_query=(
                "SELECT report_json FROM engineering_packages WHERE package_id = ?"
            ),
            postgres_query=(
                "SELECT report_json FROM roompilot.engineering_packages "
                "WHERE package_id = %s"
            ),
            params=(package_id,),
            column="report_json",
        )
        return ReportPayload.model_validate(value) if value is not None else None

    def register_document(
        self, package_id: str, document: DocumentManifest, path: Path
    ) -> None:
        path = path.resolve()
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        INSERT INTO roompilot.engineering_documents (
                            document_id, package_id, document_type, file_name,
                            content_type, file_path, byte_size, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(document_id) DO UPDATE SET
                            file_path = EXCLUDED.file_path,
                            byte_size = EXCLUDED.byte_size
                        """,
                        (
                            document.document_id,
                            package_id,
                            document.document_type,
                            document.file_name,
                            document.content_type,
                            str(path),
                            document.byte_size,
                            _utc_now(),
                        ),
                    )
            return
        with self._sqlite() as connection:
            connection.execute(
                """
                INSERT INTO engineering_documents (
                    document_id, package_id, document_type, file_name,
                    content_type, file_path, byte_size, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    file_path = excluded.file_path,
                    byte_size = excluded.byte_size
                """,
                (
                    document.document_id,
                    package_id,
                    document.document_type,
                    document.file_name,
                    document.content_type,
                    str(path),
                    document.byte_size,
                    _utc_now().isoformat(),
                ),
            )

    def get_document_path(self, document_id: str) -> Path | None:
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(
                        """
                        SELECT file_path FROM roompilot.engineering_documents
                        WHERE document_id = %s
                        """,
                        (document_id,),
                    )
                    row = cursor.fetchone()
        else:
            with self._sqlite() as connection:
                row = connection.execute(
                    "SELECT file_path FROM engineering_documents WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
        return Path(row["file_path"]).resolve() if row else None

    def _read_json_column(
        self,
        *,
        sqlite_query: str,
        postgres_query: str,
        params: tuple[Any, ...],
        column: str,
    ) -> Any | None:
        if getattr(self._store(), "provider", "sqlite") == "postgres":
            store = self._store()
            with store._connection() as connection:  # noqa: SLF001
                with store._cursor(connection) as cursor:  # noqa: SLF001
                    cursor.execute(postgres_query, params)
                    row = cursor.fetchone()
        else:
            with self._sqlite() as connection:
                row = connection.execute(sqlite_query, params).fetchone()
        value = row[column] if row else None
        return json.loads(value) if isinstance(value, str) else value

