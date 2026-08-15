from __future__ import annotations

from pathlib import Path

import pytest

from scripts.sql import import_official_catalog_to_postgres as sql_import
from scripts.catalog import remove_excluded_catalog_assets_from_manifests as manifest_cleanup


ROOT = Path(__file__).resolve().parents[1]


def test_full_import_defaults_are_documented_but_not_bundled() -> None:
    expected_paths = {
        sql_import.DEFAULT_CATALOG: ROOT
        / "JSON"
        / "furniture"
        / "furniture_official_catagory.json",
        sql_import.DEFAULT_GLB_MANIFEST: ROOT
        / "JSON"
        / "manifests"
        / "glb_upload_manifest.csv",
        sql_import.DEFAULT_GLB_RESULT: ROOT
        / "JSON"
        / "manifests"
        / "glb_upload_all_result.csv",
        sql_import.DEFAULT_IMAGE_MANIFEST: ROOT
        / "JSON"
        / "manifests"
        / "image_upload_manifest.csv",
        sql_import.DEFAULT_IMAGE_RESULT: ROOT
        / "JSON"
        / "manifests"
        / "image_upload_all_result.csv",
    }

    for actual, expected in expected_paths.items():
        assert actual == expected
        assert not actual.exists()


def test_sql_dry_run_does_not_persist_validation_report_by_default() -> None:
    args = sql_import.parse_args(["--dry-run"])

    assert args.validation_report is None


def test_sql_dry_run_requires_operator_supplied_full_profile_assets() -> None:
    with pytest.raises(FileNotFoundError, match="找不到輸入檔"):
        sql_import.main(["--dry-run"])


def test_replace_existing_is_atomic_and_keeps_non_catalog_tables_out_of_scope() -> None:
    reset_sql = sql_import.RESET_CATALOG_SQL

    assert "DROP TABLE IF EXISTS roompilot.furniture_items" in reset_sql
    assert "DROP TABLE IF EXISTS roompilot.styles" in reset_sql
    assert "DROP TABLE IF EXISTS staging.stg_furniture_catalog" in reset_sql
    assert "roompilot.projects" not in reset_sql
    assert "roompilot.render_outputs" not in reset_sql
    assert "roompilot.style_cards" not in reset_sql


def test_legacy_manifest_cleanup_has_no_public_inputs() -> None:
    assert not manifest_cleanup.DEFAULT_CATALOG.exists()
    assert all(not root.exists() for root in manifest_cleanup.MANIFEST_ROOTS)


def test_sql_schema_exposes_current_catalog_and_staging_contracts() -> None:
    schema = sql_import.DEFAULT_SCHEMA.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_items" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_assets" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_vlm_annotations" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_admin_audit" in schema
    assert "CREATE TABLE IF NOT EXISTS staging.stg_furniture_catalog" in schema
    assert "FROM pg_available_extensions" in schema
    assert "WHERE name = 'vector'" in schema
    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "DO $furniture_embeddings_table$" in schema
    assert "TO_REGCLASS('roompilot.furniture_embeddings')" in schema
    assert "CREATE OR REPLACE VIEW roompilot.furniture_catalog_current" in schema
    assert "CREATE OR REPLACE VIEW roompilot.furniture_catalog_api_current" in schema
    assert "taxonomy_group" in schema
    assert "LOWER(COALESCE(a.upload_status, ''))" in schema
    assert "delivery_url" in schema
    assert "furniture_admin_audit_action_valid" in schema


def test_sql_database_config_reads_the_repo_env_contract(
    tmp_path: Path, monkeypatch
) -> None:
    keys = (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSLMODE",
        "DB_CONNECT_TIMEOUT",
        "DB_APPLICATION_NAME",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            (
                "DB_HOST=localhost",
                "DB_PORT=5432",
                "DB_NAME=roompilot_db",
                "DB_USER=postgres",
                "DB_PASSWORD=secret",
                "DB_SSLMODE=disable",
                "DB_CONNECT_TIMEOUT=10",
                "DB_APPLICATION_NAME=roompilot_catalog_import",
            )
        ),
        encoding="utf-8",
    )

    assert sql_import.db_config(env_path) == {
        "host": "localhost",
        "port": 5432,
        "dbname": "roompilot_db",
        "user": "postgres",
        "password": "secret",
        "connect_timeout": 10,
        "application_name": "roompilot_catalog_import",
        "sslmode": "disable",
    }
