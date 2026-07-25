from __future__ import annotations

from scripts.sql import import_official_catalog_to_postgres as sql_import
from scripts.sql.import_official_catalog_to_postgres import (
    DEFAULT_CLOUD_CATALOG,
    DEFAULT_MANIFEST,
    DEFAULT_SCHEMA,
    DEFAULT_STYLE_ENRICHMENT,
    _asset_rows,
    _catalog_rows,
    load_import_payload,
    main,
)


def test_sql_dry_run_validates_the_official_9350_without_database(capsys):
    assert main(["--dry-run"]) == 0

    output = capsys.readouterr().out
    assert '"official_items": 9350' in output
    assert '"legacy_rows_excluded": 1514' in output
    assert "PostgreSQL was not modified" in output


def test_sql_records_are_one_to_one_and_cloudfront_ready():
    official, manifest, diagnostics = load_import_payload(
        DEFAULT_CLOUD_CATALOG,
        DEFAULT_STYLE_ENRICHMENT,
        DEFAULT_MANIFEST,
    )

    assert len(_catalog_rows(official["furniture"])) == 9_350
    assert len(_asset_rows(manifest)) == 9_350
    assert diagnostics["style_enriched_items"] == 9_021
    assert all(row["delivery_url"].startswith("https://") for row in manifest)


def test_sql_schema_has_transaction_safe_upsert_targets_and_official_view():
    schema = DEFAULT_SCHEMA.read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS catalog_items" in schema
    assert "CREATE TABLE IF NOT EXISTS glb_assets" in schema
    assert "CREATE OR REPLACE VIEW official_furniture_with_glb" in schema
    assert "delivery_url LIKE 'https://%'" in schema


def test_sql_import_defaults_to_non_destructive_prune(monkeypatch):
    calls = {}

    def fake_import_to_postgres(
        official,
        manifest_rows,
        *,
        schema_path,
        prune_extra,
        catalog_filename,
        manifest_filename,
    ):
        calls["prune_extra"] = prune_extra
        calls["catalog_filename"] = catalog_filename
        calls["manifest_filename"] = manifest_filename
        return len(official["furniture"]), len(manifest_rows), 9_350

    monkeypatch.setattr(sql_import, "import_to_postgres", fake_import_to_postgres)

    assert sql_import.main([]) == 0
    assert calls == {
        "prune_extra": False,
        "catalog_filename": DEFAULT_CLOUD_CATALOG.name,
        "manifest_filename": DEFAULT_MANIFEST.name,
    }

    assert sql_import.main(["--prune-extra"]) == 0
    assert calls["prune_extra"] is True
