from __future__ import annotations

import json
from pathlib import Path

from scripts.sql import import_official_catalog_to_postgres as sql_import


ROOT = Path(__file__).resolve().parents[1]


def test_sql_defaults_use_the_portable_official_catalog_handoff() -> None:
    expected_paths = {
        sql_import.DEFAULT_CATALOG: ROOT / "JSON" / "furniture" / "furniture_official_catagory.json",
        sql_import.DEFAULT_GLB_MANIFEST: ROOT / "JSON" / "manifests" / "glb_upload_manifest.csv",
        sql_import.DEFAULT_GLB_RESULT: ROOT / "JSON" / "manifests" / "glb_upload_all_result.csv",
        sql_import.DEFAULT_IMAGE_MANIFEST: ROOT / "JSON" / "manifests" / "image_upload_manifest.csv",
        sql_import.DEFAULT_IMAGE_RESULT: ROOT / "JSON" / "manifests" / "image_upload_all_result.csv",
    }

    for actual, expected in expected_paths.items():
        assert actual == expected
        assert actual.is_file()


def test_sql_dry_run_validates_all_official_assets_without_database(
    tmp_path: Path, capsys
) -> None:
    report_path = tmp_path / "postgres_import_validation.json"

    assert sql_import.main(["--dry-run", "--validation-report", str(report_path)]) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert report["source_counts"] == {
        "catalog_items": 8_557,
        "glb_manifest_rows": 8_557,
        "glb_result_rows": 8_557,
        "image_manifest_rows": 25_671,
        "image_result_rows": 25_671,
    }
    assert report["prepared_counts"]["assets"] == 34_228
    assert report["prepared_counts"]["vlm_annotations"] == 8_557
    assert report["errors"] == []

    output = capsys.readouterr().out
    assert "8,557" in output
    assert "Dry Run" in output


def test_sql_schema_exposes_current_catalog_and_staging_contracts() -> None:
    schema = sql_import.DEFAULT_SCHEMA.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_items" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_assets" in schema
    assert "CREATE TABLE IF NOT EXISTS roompilot.furniture_vlm_annotations" in schema
    assert "CREATE TABLE IF NOT EXISTS staging.stg_furniture_catalog" in schema
    assert "FROM pg_available_extensions" in schema
    assert "WHERE name = 'vector'" in schema
    assert "CREATE EXTENSION IF NOT EXISTS vector" in schema
    assert "DO $furniture_embeddings_table$" in schema
    assert "TO_REGCLASS('roompilot.furniture_embeddings')" in schema
    assert "CREATE OR REPLACE VIEW roompilot.furniture_catalog_current" in schema
    assert "delivery_url" in schema


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
