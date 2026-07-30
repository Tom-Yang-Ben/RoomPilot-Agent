"""One-time, non-destructive SQLite to PostgreSQL project migration.

Dry-run is the default.  ``--apply`` creates the Phase 3 tables and copies
projects/render metadata in one PostgreSQL transaction.  The SQLite database
and all runtime files remain untouched for rollback.

Keep this module beside its Phase 3 schema under ``scripts/sql`` so repository
root and sibling-schema discovery remain deterministic.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = PROJECT_ROOT / ".runtime" / "projects.sqlite3"
DEFAULT_SCHEMA = Path(__file__).with_name("roompilot_project_store_schema.sql")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.server.project_store import MAX_WORKFLOW_BYTES  # noqa: E402
from scripts.sql.import_official_catalog_to_postgres import db_config  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="將 RoomPilot projects.sqlite3 一次性遷移為 PostgreSQL JSONB。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--schema-sql", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="實際套用 schema 並寫入 PostgreSQL；未指定時只做 dry-run。",
    )
    return parser.parse_args(argv)


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _workflow(row: sqlite3.Row, errors: list[str]) -> dict[str, Any]:
    project_id = str(row["project_id"])
    raw = _row_value(row, "workflow_json", "{}")
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        errors.append(f"{project_id}: workflow_json 不是合法 JSON")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{project_id}: workflow_json 必須是 object")
        return {}
    if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > MAX_WORKFLOW_BYTES:
        errors.append(f"{project_id}: workflow_json 超過 2 MB")
    return value


def load_sqlite_snapshot(database_path: Path) -> dict[str, Any]:
    if not database_path.is_file():
        raise FileNotFoundError(f"找不到 SQLite 專案資料庫：{database_path}")

    source = sqlite3.connect(database_path)
    source.row_factory = sqlite3.Row
    snapshot = sqlite3.connect(":memory:")
    snapshot.row_factory = sqlite3.Row
    try:
        source.backup(snapshot)
    finally:
        source.close()

    errors: list[str] = []
    warnings: list[str] = []
    try:
        project_rows = snapshot.execute("SELECT * FROM projects").fetchall()
    except sqlite3.DatabaseError as exc:
        snapshot.close()
        raise RuntimeError("SQLite 缺少 projects table") from exc
    try:
        render_rows = snapshot.execute("SELECT * FROM render_outputs").fetchall()
    except sqlite3.DatabaseError:
        render_rows = []

    projects: list[dict[str, Any]] = []
    project_ids: set[str] = set()
    for row in project_rows:
        project_id = str(row["project_id"])
        project_ids.add(project_id)
        upload_values = {
            "upload_filename": _row_value(row, "upload_filename"),
            "upload_extension": _row_value(row, "upload_extension"),
            "upload_mime": _row_value(row, "upload_mime"),
            "upload_path": _row_value(row, "upload_path"),
        }
        populated_upload_fields = sum(value is not None for value in upload_values.values())
        if populated_upload_fields not in {0, 4}:
            errors.append(f"{project_id}: upload metadata 不完整")
        upload_path = upload_values["upload_path"]
        if upload_path and not Path(str(upload_path)).is_file():
            warnings.append(f"{project_id}: upload 檔案不存在：{upload_path}")
        projects.append(
            {
                "project_id": project_id,
                "name": str(row["name"]),
                "notes": str(_row_value(row, "notes", "") or ""),
                "current_step": str(row["current_step"]),
                "workflow_json": _workflow(row, errors),
                "revision": int(_row_value(row, "revision", 0) or 0),
                **upload_values,
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
        )
        if projects[-1]["revision"] < 0:
            errors.append(f"{project_id}: revision 不可小於 0")

    renders: list[dict[str, Any]] = []
    for row in render_rows:
        render_id = str(row["render_id"])
        project_id = str(row["project_id"])
        if project_id not in project_ids:
            errors.append(f"{render_id}: render 指向不存在的 project {project_id}")
        file_path = str(row["file_path"])
        if not Path(file_path).is_file():
            warnings.append(f"{render_id}: render 檔案不存在：{file_path}")
        renders.append(
            {
                "render_id": render_id,
                "project_id": project_id,
                "white_model_version": int(row["white_model_version"]),
                "viewpoint_version": int(row["viewpoint_version"]),
                "style_version": int(row["style_version"]),
                "style_card_id": str(row["style_card_id"]),
                "provider": str(row["provider"]),
                "mime_type": str(row["mime_type"]),
                "filename": str(row["filename"]),
                "file_path": file_path,
                "byte_size": int(row["byte_size"]),
                "created_at": str(row["created_at"]),
            }
        )
        if min(
            renders[-1]["white_model_version"],
            renders[-1]["viewpoint_version"],
            renders[-1]["style_version"],
            renders[-1]["byte_size"],
        ) < 0:
            errors.append(f"{render_id}: render version／byte_size 不可小於 0")
    snapshot.close()
    return {
        "database_path": str(database_path.resolve()),
        "projects": projects,
        "renders": renders,
        "errors": errors,
        "warnings": warnings,
    }


def apply_snapshot(
    snapshot: dict[str, Any],
    *,
    schema_path: Path,
    env_path: Path,
) -> dict[str, int]:
    if not schema_path.is_file():
        raise FileNotFoundError(f"找不到 Phase 3 schema：{schema_path}")
    if snapshot["errors"]:
        raise RuntimeError("SQLite preflight 有錯誤，未寫入 PostgreSQL")

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError as exc:
        raise RuntimeError("找不到 psycopg2；請安裝 server/catalog extra") from exc

    config = db_config(env_path)
    config["application_name"] = "roompilot_project_migration"
    project_writes = 0
    render_writes = 0
    with psycopg2.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8-sig"))
            for project in snapshot["projects"]:
                cursor.execute(
                    """
                    INSERT INTO roompilot.projects (
                        project_id, name, notes, current_step, workflow_json,
                        revision, upload_filename, upload_extension, upload_mime,
                        upload_path, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        notes = EXCLUDED.notes,
                        current_step = EXCLUDED.current_step,
                        workflow_json = EXCLUDED.workflow_json,
                        revision = EXCLUDED.revision,
                        upload_filename = EXCLUDED.upload_filename,
                        upload_extension = EXCLUDED.upload_extension,
                        upload_mime = EXCLUDED.upload_mime,
                        upload_path = EXCLUDED.upload_path,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at
                    WHERE EXCLUDED.revision > roompilot.projects.revision
                       OR (
                           EXCLUDED.revision = roompilot.projects.revision
                           AND EXCLUDED.updated_at > roompilot.projects.updated_at
                       )
                    """,
                    (
                        project["project_id"],
                        project["name"],
                        project["notes"],
                        project["current_step"],
                        Json(project["workflow_json"]),
                        project["revision"],
                        project["upload_filename"],
                        project["upload_extension"],
                        project["upload_mime"],
                        project["upload_path"],
                        project["created_at"],
                        project["updated_at"],
                    ),
                )
                project_writes += max(cursor.rowcount, 0)

            for render in snapshot["renders"]:
                cursor.execute(
                    """
                    INSERT INTO roompilot.render_outputs (
                        render_id, project_id, white_model_version,
                        viewpoint_version, style_version, style_card_id,
                        provider, mime_type, filename, file_path, byte_size,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (render_id) DO NOTHING
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
                        render["file_path"],
                        render["byte_size"],
                        render["created_at"],
                    ),
                )
                render_writes += max(cursor.rowcount, 0)

            source_ids = [project["project_id"] for project in snapshot["projects"]]
            if source_ids:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM roompilot.projects
                    WHERE project_id = ANY(%s::TEXT[])
                    """,
                    (source_ids,),
                )
                verified_projects = int(cursor.fetchone()[0])
            else:
                verified_projects = 0
            render_ids = [render["render_id"] for render in snapshot["renders"]]
            if render_ids:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM roompilot.render_outputs
                    WHERE render_id = ANY(%s::TEXT[])
                    """,
                    (render_ids,),
                )
                verified_renders = int(cursor.fetchone()[0])
            else:
                verified_renders = 0

            if verified_projects != len(source_ids) or verified_renders != len(render_ids):
                raise RuntimeError("PostgreSQL 遷移後筆數驗證失敗，transaction 已回滾")

    return {
        "project_writes": project_writes,
        "render_writes": render_writes,
        "verified_projects": verified_projects,
        "verified_renders": verified_renders,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    snapshot = load_sqlite_snapshot(args.sqlite_db)
    print("SQLite Phase 3 preflight 完成")
    print(f"- 專案：{len(snapshot['projects']):,}")
    print(f"- 渲染輸出：{len(snapshot['renders']):,}")
    print(f"- 錯誤：{len(snapshot['errors']):,}")
    print(f"- 遺失檔案警告：{len(snapshot['warnings']):,}")
    for message in snapshot["errors"]:
        print(f"ERROR: {message}")
    for message in snapshot["warnings"][:20]:
        print(f"WARNING: {message}")
    if snapshot["errors"]:
        return 1
    if not args.apply:
        print("Dry Run 完成；未連線 PostgreSQL，SQLite 與 runtime 檔案未變更。")
        return 0
    counts = apply_snapshot(
        snapshot,
        schema_path=args.schema_sql,
        env_path=args.env,
    )
    print("PostgreSQL Phase 3 migration 完成；SQLite 原檔仍保留。")
    print(
        f"- 寫入／驗證專案：{counts['project_writes']:,}／"
        f"{counts['verified_projects']:,}"
    )
    print(
        f"- 寫入／驗證渲染：{counts['render_writes']:,}／"
        f"{counts['verified_renders']:,}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"遷移失敗：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
