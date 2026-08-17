#!/usr/bin/env python3
"""Install or roll back RoomPilot's fail-closed catalog visibility boundary.

The migration never deletes catalog rows.  On the legacy local schema it
restores the pre-quarantine activation flags from the latest licensing backup,
then lets the PostgreSQL session setting decide whether permission-pending rows
are visible.  Public remains the database default when the setting is absent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sql.import_public_catalog_to_postgres import connect_db  # noqa: E402


PRIVATE_VIEW = "roompilot.furniture_catalog_private_current"
CURRENT_VIEW = "roompilot.furniture_catalog_current"
PRIVATE_EMBEDDING_SOURCE_VIEW = (
    "roompilot.furniture_embedding_source_private_current"
)
CURRENT_EMBEDDING_SOURCE_VIEW = "roompilot.furniture_embedding_source_current"
BACKUP_TABLE = "roompilot.catalog_visibility_migration_backup"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add public/private visibility to an existing local catalog."
    )
    parser.add_argument("--env", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    return parser.parse_args(argv)


def _relation_exists(cursor: Any, relation: str) -> bool:
    cursor.execute("SELECT TO_REGCLASS(%s) IS NOT NULL", (relation,))
    return bool(cursor.fetchone()[0])


def _replace_named_view(cursor: Any, view_name: str, definition: str) -> None:
    from psycopg2 import sql

    schema_name, relation_name = view_name.split(".", 1)
    cursor.execute(
        sql.SQL("CREATE OR REPLACE VIEW {} AS ").format(
            sql.Identifier(schema_name, relation_name)
        )
        + sql.SQL(definition)
    )


def _replace_view(cursor: Any, definition: str) -> None:
    _replace_named_view(cursor, CURRENT_VIEW, definition)


def _capture_private_view(cursor: Any, *, generic: bool) -> None:
    from psycopg2 import sql

    if _relation_exists(cursor, PRIVATE_VIEW):
        return
    if generic:
        # An older generic view expanded SELECT * before license_status existed.
        cursor.execute(
            "CREATE OR REPLACE VIEW roompilot.furniture_catalog_current AS "
            "SELECT * FROM roompilot.furniture_catalog WHERE is_active"
        )
    cursor.execute("SELECT PG_GET_VIEWDEF(%s::REGCLASS, true)", (CURRENT_VIEW,))
    definition = str(cursor.fetchone()[0])
    cursor.execute(
        sql.SQL("CREATE VIEW {} AS ").format(
            sql.Identifier("roompilot", "furniture_catalog_private_current")
        )
        + sql.SQL(definition)
    )


def _capture_private_embedding_source_view(cursor: Any) -> bool:
    from psycopg2 import sql

    if not _relation_exists(cursor, CURRENT_EMBEDDING_SOURCE_VIEW):
        return False
    if _relation_exists(cursor, PRIVATE_EMBEDDING_SOURCE_VIEW):
        return True
    cursor.execute(
        "SELECT PG_GET_VIEWDEF(%s::REGCLASS, true)",
        (CURRENT_EMBEDDING_SOURCE_VIEW,),
    )
    definition = str(cursor.fetchone()[0])
    cursor.execute(
        sql.SQL("CREATE VIEW {} AS ").format(
            sql.Identifier(
                "roompilot", "furniture_embedding_source_private_current"
            )
        )
        + sql.SQL(definition)
    )
    return True


def _latest_license_backup(cursor: Any) -> str | None:
    cursor.execute(
        """
        SELECT namespace.nspname || '.' || class.relname
        FROM pg_class AS class
        JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
        WHERE namespace.nspname = 'roompilot'
          AND class.relkind = 'r'
          AND class.relname LIKE 'catalog_license_migration_backup_%'
        ORDER BY class.relname DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return str(row[0]) if row else None


def migrate(cursor: Any) -> dict[str, Any]:
    from psycopg2 import sql

    legacy = _relation_exists(cursor, "roompilot.furniture_items")
    generic = _relation_exists(cursor, "roompilot.furniture_catalog")
    if legacy == generic:
        raise RuntimeError("expected exactly one supported RoomPilot catalog schema")

    base_table = "furniture_items" if legacy else "furniture_catalog"
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
            item_id text PRIMARY KEY,
            is_active boolean NOT NULL,
            captured_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        f"""
        INSERT INTO {BACKUP_TABLE} (item_id, is_active)
        SELECT item_id, is_active FROM roompilot.{base_table}
        ON CONFLICT (item_id) DO NOTHING
        """
    )

    if generic:
        cursor.execute(
            "ALTER TABLE roompilot.furniture_catalog "
            "ADD COLUMN IF NOT EXISTS license_status text NOT NULL DEFAULT 'verified'"
        )

    _capture_private_view(cursor, generic=generic)

    restored_count = 0
    license_backup = None
    if legacy:
        license_backup = _latest_license_backup(cursor)
        if not license_backup:
            raise RuntimeError("legacy catalog licensing backup is required")
        schema_name, table_name = license_backup.split(".", 1)
        cursor.execute(
            sql.SQL(
                """
                UPDATE roompilot.furniture_items AS item
                SET is_active = backup.is_active
                FROM {} AS backup
                WHERE backup.item_id = item.item_id
                  AND item.is_active IS DISTINCT FROM backup.is_active
                """
            ).format(sql.Identifier(schema_name, table_name))
        )
        restored_count = int(cursor.rowcount)
        _replace_view(
            cursor,
            """
            SELECT catalog.*
            FROM roompilot.furniture_catalog_private_current AS catalog
            WHERE COALESCE(
                    current_setting('roompilot.catalog_visibility', true),
                    'public'
                  ) = 'private'
               OR EXISTS (
                    SELECT 1
                    FROM roompilot.furniture_items AS item
                    WHERE item.item_id = catalog.item_id
                      AND item.raw_data->>'license_status' = 'verified'
               )
            """,
        )
        if _capture_private_embedding_source_view(cursor):
            _replace_named_view(
                cursor,
                CURRENT_EMBEDDING_SOURCE_VIEW,
                """
                SELECT source.*
                FROM roompilot.furniture_embedding_source_private_current AS source
                INNER JOIN roompilot.furniture_catalog_current AS catalog
                    ON catalog.item_id = source.item_id
                """,
            )
    else:
        _replace_view(
            cursor,
            """
            SELECT catalog.*
            FROM roompilot.furniture_catalog_private_current AS catalog
            WHERE COALESCE(
                    current_setting('roompilot.catalog_visibility', true),
                    'public'
                  ) = 'private'
               OR catalog.license_status = 'verified'
            """,
        )

    cursor.execute(
        "SELECT set_config('roompilot.catalog_visibility', 'public', false)"
    )
    cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_VIEW}")
    public_count = int(cursor.fetchone()[0])
    public_embedding_source_count = None
    if _relation_exists(cursor, CURRENT_EMBEDDING_SOURCE_VIEW):
        cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_EMBEDDING_SOURCE_VIEW}")
        public_embedding_source_count = int(cursor.fetchone()[0])
    cursor.execute(
        "SELECT set_config('roompilot.catalog_visibility', 'private', false)"
    )
    cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_VIEW}")
    private_count = int(cursor.fetchone()[0])
    private_embedding_source_count = None
    if _relation_exists(cursor, CURRENT_EMBEDDING_SOURCE_VIEW):
        cursor.execute(f"SELECT COUNT(*) FROM {CURRENT_EMBEDDING_SOURCE_VIEW}")
        private_embedding_source_count = int(cursor.fetchone()[0])
    return {
        "schema": "legacy" if legacy else "generic",
        "public_count": public_count,
        "private_count": private_count,
        "public_embedding_source_count": public_embedding_source_count,
        "private_embedding_source_count": private_embedding_source_count,
        "restored_activation_count": restored_count,
        "license_backup": license_backup,
        "visibility_backup": BACKUP_TABLE,
    }


def rollback(cursor: Any) -> dict[str, Any]:
    from psycopg2 import sql

    legacy = _relation_exists(cursor, "roompilot.furniture_items")
    generic = _relation_exists(cursor, "roompilot.furniture_catalog")
    if not _relation_exists(cursor, BACKUP_TABLE):
        raise RuntimeError("catalog visibility backup does not exist")
    if not _relation_exists(cursor, PRIVATE_VIEW):
        raise RuntimeError("private catalog view does not exist")

    base_table = "furniture_items" if legacy else "furniture_catalog"
    cursor.execute(
        f"""
        UPDATE roompilot.{base_table} AS item
        SET is_active = backup.is_active
        FROM {BACKUP_TABLE} AS backup
        WHERE backup.item_id = item.item_id
          AND item.is_active IS DISTINCT FROM backup.is_active
        """
    )
    restored_count = int(cursor.rowcount)
    if _relation_exists(cursor, PRIVATE_EMBEDDING_SOURCE_VIEW):
        cursor.execute(
            "SELECT PG_GET_VIEWDEF(%s::REGCLASS, true)",
            (PRIVATE_EMBEDDING_SOURCE_VIEW,),
        )
        embedding_definition = str(cursor.fetchone()[0])
        _replace_named_view(
            cursor, CURRENT_EMBEDDING_SOURCE_VIEW, embedding_definition
        )
        cursor.execute(
            sql.SQL("DROP VIEW {}").format(
                sql.Identifier(
                    "roompilot", "furniture_embedding_source_private_current"
                )
            )
        )

    cursor.execute("SELECT PG_GET_VIEWDEF(%s::REGCLASS, true)", (PRIVATE_VIEW,))
    definition = str(cursor.fetchone()[0])
    _replace_view(cursor, definition)
    cursor.execute(
        sql.SQL("DROP VIEW {}").format(
            sql.Identifier("roompilot", "furniture_catalog_private_current")
        )
    )
    return {
        "schema": "legacy" if legacy else "generic",
        "restored_activation_count": restored_count,
        "visibility_backup": BACKUP_TABLE,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    connection = connect_db(args.env)
    connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            result = rollback(cursor) if args.rollback else migrate(cursor)
        result["rollback"] = bool(args.rollback)
        result["dry_run"] = bool(args.dry_run)
        if args.dry_run:
            connection.rollback()
        else:
            connection.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
