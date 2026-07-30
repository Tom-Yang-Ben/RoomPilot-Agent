from __future__ import annotations

import json
from pathlib import Path

from scripts.sql import import_official_catalog_to_postgres as sql_import
from scripts.catalog import remove_excluded_catalog_assets_from_manifests as manifest_cleanup


ROOT = Path(__file__).resolve().parents[1]


def test_sql_defaults_use_the_portable_official_catalog_handoff() -> None:
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
        assert actual.is_file()


def test_sql_dry_run_does_not_persist_validation_report_by_default() -> None:
    args = sql_import.parse_args(["--dry-run"])

    assert args.validation_report is None


def test_sql_dry_run_validates_all_official_assets_without_database(
    tmp_path: Path, capsys
) -> None:
    report_path = tmp_path / "postgres_import_validation.json"

    assert (
        sql_import.main(
            ["--dry-run", "--validation-report", str(report_path)]
        )
        == 0
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["source_counts"] == {
        "catalog_items": 8_675,
        "glb_manifest_rows": 8_675,
        "glb_result_rows": 8_675,
        "image_manifest_rows": 26_025,
        "image_result_rows": 26_025,
    }
    assert report["prepared_counts"]["assets"] == 34_700
    assert report["prepared_counts"]["styles"] == 6
    assert report["prepared_counts"]["vlm_annotations"] == 8_675
    assert report["excluded_item_ids"] == [
        "jp-armchairs-01-underl-tta-vacuum-flask-black-1-2-l"
    ]
    assert report["errors"] == []

    output = capsys.readouterr().out
    assert "家具：8,675" in output
    assert "分類／風格／房間：56／6／9" in output
    assert "Dry Run 完成；未連線 PostgreSQL，也未寫入資料庫。" in output


def test_replace_existing_is_atomic_and_keeps_non_catalog_tables_out_of_scope() -> None:
    reset_sql = sql_import.RESET_CATALOG_SQL

    assert "DROP TABLE IF EXISTS roompilot.furniture_items" in reset_sql
    assert "DROP TABLE IF EXISTS roompilot.styles" in reset_sql
    assert "DROP TABLE IF EXISTS staging.stg_furniture_catalog" in reset_sql
    assert "roompilot.projects" not in reset_sql
    assert "roompilot.render_outputs" not in reset_sql
    assert "roompilot.style_cards" not in reset_sql


def test_excluded_furniture_is_absent_from_both_manifest_copies() -> None:
    item_ids = manifest_cleanup.excluded_item_ids(manifest_cleanup.DEFAULT_CATALOG)

    assert item_ids == ("jp-armchairs-01-underl-tta-vacuum-flask-black-1-2-l",)
    for filename in manifest_cleanup.MANIFEST_FILES:
        left = manifest_cleanup.MANIFEST_ROOTS[0] / filename
        right = manifest_cleanup.MANIFEST_ROOTS[1] / filename
        assert manifest_cleanup.matching_line_count(left, item_ids) == 0
        assert manifest_cleanup.matching_line_count(right, item_ids) == 0
        assert manifest_cleanup.sha256(left) == manifest_cleanup.sha256(right)


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
