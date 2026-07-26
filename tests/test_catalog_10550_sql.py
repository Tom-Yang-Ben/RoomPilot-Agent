from __future__ import annotations

import pytest

from scripts.sql import import_catalog_to_postgres as sql_import


def test_catalog_10550_import_payload_matches_kai_baseline():
    items, metadata = sql_import.load_catalog(sql_import.DEFAULT_CATALOG)
    manifest_rows = sql_import.load_csv(sql_import.DEFAULT_MANIFEST)
    upload_rows = sql_import.load_csv(sql_import.DEFAULT_UPLOAD_RESULT)

    role_rows, type_rows, item_rows, asset_rows, report = sql_import.validate_and_prepare(
        items,
        metadata,
        manifest_rows,
        upload_rows,
        strict=True,
    )

    assert len(items) == 10_550
    assert len(manifest_rows) == 10_550
    assert len(upload_rows) == 10_550
    assert len(role_rows) == 11
    assert len(type_rows) == 87
    assert len(item_rows) == 10_550
    assert len(asset_rows) == 10_550
    assert report["warning_count"] == 0


def test_catalog_10550_schema_exposes_api_and_space_planning_views():
    assert sql_import.parse_args(["--dry-run"]).schema_sql.name == (
        "roompilot_catalog_10550_schema.sql"
    )

    schema = sql_import.parse_args(["--dry-run"]).schema_sql.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS item_roles" in schema
    assert "CREATE TABLE IF NOT EXISTS item_types" in schema
    assert "CREATE TABLE IF NOT EXISTS catalog_items" in schema
    assert "CREATE TABLE IF NOT EXISTS glb_assets" in schema
    assert "CREATE OR REPLACE VIEW catalog_items_with_glb" in schema
    assert "CREATE OR REPLACE VIEW catalog_items_for_space_planning" in schema


def test_catalog_10550_post_import_count_verification():
    class Cursor:
        def __init__(self):
            self._last_query = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, query):
            self._last_query = query

        def fetchone(self):
            query_map = {
                "FROM catalog_items;": 10_550,
                "FROM glb_assets;": 10_550,
                "FROM item_types;": 87,
                "FROM item_roles;": 11,
                "WHERE NOT is_active;": 1,
                "FROM catalog_items_for_space_planning;": 10_542,
            }
            for marker, value in query_map.items():
                if marker in self._last_query:
                    return (value,)
            raise AssertionError(f"unexpected query: {self._last_query}")

    class Connection:
        def cursor(self):
            return Cursor()

    assert sql_import.verify_post_import_counts(Connection()) == {
        "catalog_items": 10_550,
        "glb_assets": 10_550,
        "item_types": 87,
        "item_roles": 11,
        "inactive_items": 1,
        "space_planning_items": 10_542,
    }


def test_catalog_10550_postgres_connection_smoke():
    if not (sql_import.PROJECT_ROOT / ".env").exists():
        pytest.skip("PostgreSQL smoke test needs a local .env with DB_* settings.")

    try:
        conn = sql_import.connect_db(sql_import.PROJECT_ROOT / ".env")
    except Exception as exc:
        pytest.skip(f"PostgreSQL is not reachable in this environment: {exc}")

    try:
        assert sql_import.verify_post_import_counts(conn) == (
            sql_import.EXPECTED_POST_IMPORT_COUNTS
        )
    finally:
        conn.close()
