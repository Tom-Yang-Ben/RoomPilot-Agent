"""Transactional, reversible migration for persisted project workflows."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_schema import PROJECT_SCHEMA_VERSION, migrate_project_workflow


BACKUP_MANIFEST = "manifest.json"
BACKUP_DATABASE = "projects.sqlite3"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_workflow(raw: str, project_id: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"project {project_id} has invalid workflow JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"project {project_id} workflow must be an object")
    return value


@dataclass(frozen=True)
class RuntimeMigrationSummary:
    runtime_dir: str
    project_count: int
    migrated_count: int
    already_current_count: int
    target_schema_version: int
    dry_run: bool
    backup_dir: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeRestoreSummary:
    runtime_dir: str
    restored_from: str
    safety_backup_dir: str
    restored_database_sha256: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _project_rows(database_path: Path) -> list[sqlite3.Row]:
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'projects'"
        ).fetchone()
        if table is None:
            raise ValueError(f"projects table is missing in {database_path}")
        return connection.execute(
            "SELECT project_id, workflow_json, revision, updated_at FROM projects"
        ).fetchall()


def inspect_runtime_schema(runtime_dir: Path) -> RuntimeMigrationSummary:
    runtime_dir = runtime_dir.resolve()
    rows = _project_rows(runtime_dir / BACKUP_DATABASE)
    migrated_count = 0
    for row in rows:
        workflow = _load_workflow(row["workflow_json"], row["project_id"])
        if migrate_project_workflow(workflow).changed:
            migrated_count += 1
    return RuntimeMigrationSummary(
        runtime_dir=str(runtime_dir),
        project_count=len(rows),
        migrated_count=migrated_count,
        already_current_count=len(rows) - migrated_count,
        target_schema_version=PROJECT_SCHEMA_VERSION,
        dry_run=True,
        backup_dir=None,
    )


def _backup_database(database_path: Path, backup_dir: Path, *, reason: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_database = backup_dir / BACKUP_DATABASE
    with sqlite3.connect(database_path) as source:
        with sqlite3.connect(backup_database) as target:
            source.backup(target)
    manifest = {
        "backup_schema_version": 1,
        "created_at": _utc_now(),
        "reason": reason,
        "source_database": str(database_path.resolve()),
        "database_filename": BACKUP_DATABASE,
        "database_sha256": _sha256(backup_database),
    }
    (backup_dir / BACKUP_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup_database


def migrate_runtime_schema(
    runtime_dir: Path,
    *,
    dry_run: bool = False,
    backup_dir: Path | None = None,
) -> RuntimeMigrationSummary:
    runtime_dir = runtime_dir.resolve()
    database_path = runtime_dir / BACKUP_DATABASE
    rows = _project_rows(database_path)
    migrations = []
    for row in rows:
        workflow = _load_workflow(row["workflow_json"], row["project_id"])
        outcome = migrate_project_workflow(workflow)
        if outcome.changed:
            migrations.append((row, outcome.workflow))

    if dry_run or not migrations:
        return RuntimeMigrationSummary(
            runtime_dir=str(runtime_dir),
            project_count=len(rows),
            migrated_count=len(migrations),
            already_current_count=len(rows) - len(migrations),
            target_schema_version=PROJECT_SCHEMA_VERSION,
            dry_run=dry_run,
            backup_dir=None,
        )

    resolved_backup_dir = (
        backup_dir.resolve()
        if backup_dir is not None
        else runtime_dir / "backups" / f"project-schema-v{PROJECT_SCHEMA_VERSION}-{_timestamp()}"
    )
    _backup_database(
        database_path,
        resolved_backup_dir,
        reason=f"before project schema v{PROJECT_SCHEMA_VERSION} migration",
    )

    migrated_at = _utc_now()
    with sqlite3.connect(database_path, timeout=30) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        for row, workflow in migrations:
            serialized = json.dumps(workflow, ensure_ascii=False, separators=(",", ":"))
            cursor = connection.execute(
                """
                UPDATE projects
                SET workflow_json = ?, revision = revision + 1, updated_at = ?
                WHERE project_id = ? AND revision = ?
                """,
                (
                    serialized,
                    migrated_at,
                    row["project_id"],
                    int(row["revision"]),
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"project {row['project_id']} changed during schema migration"
                )
        connection.commit()

    verification = inspect_runtime_schema(runtime_dir)
    if verification.migrated_count:
        raise RuntimeError(
            f"migration verification failed for {verification.migrated_count} projects"
        )
    manifest_path = resolved_backup_dir / BACKUP_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["migration_completed_at"] = _utc_now()
    manifest["migrated_project_count"] = len(migrations)
    manifest["target_project_schema_version"] = PROJECT_SCHEMA_VERSION
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return RuntimeMigrationSummary(
        runtime_dir=str(runtime_dir),
        project_count=len(rows),
        migrated_count=len(migrations),
        already_current_count=len(rows) - len(migrations),
        target_schema_version=PROJECT_SCHEMA_VERSION,
        dry_run=False,
        backup_dir=str(resolved_backup_dir),
    )


def restore_runtime_backup(
    runtime_dir: Path,
    backup_dir: Path,
) -> RuntimeRestoreSummary:
    runtime_dir = runtime_dir.resolve()
    backup_dir = backup_dir.resolve()
    database_path = runtime_dir / BACKUP_DATABASE
    manifest_path = backup_dir / BACKUP_MANIFEST
    backup_database = backup_dir / BACKUP_DATABASE
    if not manifest_path.is_file() or not backup_database.is_file():
        raise FileNotFoundError("backup manifest or database is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = str(manifest.get("database_sha256") or "")
    actual_hash = _sha256(backup_database)
    if not expected_hash or actual_hash != expected_hash:
        raise ValueError("backup database checksum mismatch")

    safety_backup_dir = (
        runtime_dir / "backups" / f"pre-restore-project-schema-{_timestamp()}"
    )
    _backup_database(
        database_path,
        safety_backup_dir,
        reason=f"before restoring {backup_dir}",
    )
    shutil.copy2(backup_database, database_path)
    for suffix in ("-wal", "-shm"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)
    if _sha256(database_path) != actual_hash:
        raise RuntimeError("restored database checksum verification failed")
    return RuntimeRestoreSummary(
        runtime_dir=str(runtime_dir),
        restored_from=str(backup_dir),
        safety_backup_dir=str(safety_backup_dir),
        restored_database_sha256=actual_hash,
    )
