from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.catalog import runtime_catalog_repository as repository
from backend.catalog.postgres_repository import borrow_catalog_connection
from scripts.runtime_catalog import import_runtime_catalogs_to_postgres as importer


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / "catalog" / "data"


def _sources() -> dict[str, importer.SourcePayload]:
    return {
        "style_cards": importer._load_source("style_cards", importer.DEFAULT_STYLE_CARDS),
        "design_style_profiles": importer._load_source(
            "design_style_profiles", importer.DEFAULT_DESIGN_STYLES
        ),
        "surface_materials": importer._load_source(
            "surface_materials", importer.DEFAULT_SURFACES
        ),
        "renovation_costs": importer._load_source(
            "renovation_costs", importer.DEFAULT_COSTS
        ),
        "external_import": importer._load_source(
            "external_import", importer.DEFAULT_EXTERNAL_IMPORT
        ),
        "unmatched_cloud": importer._load_source(
            "unmatched_cloud", importer.DEFAULT_UNMATCHED
        ),
        "sf3d_legacy": importer._load_source("sf3d_legacy", importer.DEFAULT_LEGACY),
    }


def test_phase4_dry_run_sources_have_expected_runtime_and_quarantine_counts() -> None:
    report = importer.validate_sources(_sources())

    assert report["status"] == "valid"
    assert report["errors"] == []
    assert report["counts"] == {
        "style_groups": 6,
        "style_cards": 18,
        "design_style_profiles": 6,
        "surface_materials": 571,
        "style_surface_profiles": 12,
        "renovation_cost_rates": 6,
        "renovation_cost_sources": 4,
        "external_import_quarantine": 7495,
        "unmatched_cloud_quarantine": 1514,
        "sf3d_legacy_quarantine": 1509,
        "sf3d_legacy_duplicate_ids": 1,
        "quarantine_total": 10518,
        "rag_documents": 595,
    }


def test_explicit_json_mode_preserves_versioned_style_surface_and_cost_seeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROOMPILOT_RUNTIME_CATALOG_PROVIDER", "json")

    styles = repository.load_runtime_style_cards(ROOT, importer.DEFAULT_STYLE_CARDS)
    design_styles = repository.load_runtime_design_styles(
        ROOT, importer.DEFAULT_DESIGN_STYLES
    )
    surfaces = repository.load_runtime_surface_catalog(ROOT, importer.DEFAULT_SURFACES)
    costs = repository.load_runtime_cost_catalog(ROOT, importer.DEFAULT_COSTS)

    assert len(styles) == 6
    assert sum(len(style["cards"]) for style in styles) == 18
    assert len(design_styles) == 6
    assert styles[0]["cards"][0]["image_url"].startswith("/static/style_cards/")
    assert len(surfaces["surfaces"]) == 571
    assert len(costs["rates"]) == 6
    assert len(costs["sources"]) == 4


def test_strict_postgres_runtime_does_not_silently_scan_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROOMPILOT_RUNTIME_CATALOG_PROVIDER", "postgres")
    monkeypatch.setattr(
        repository,
        "_postgres_style_cards",
        lambda _project: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    with pytest.raises(repository.RuntimeCatalogUnavailable) as exc_info:
        repository.load_runtime_style_cards(ROOT, DATA / "missing-style-seed.json")

    assert exc_info.value.catalog_key == "style_cards"
    assert isinstance(exc_info.value.reason, ConnectionError)


def test_phase4_sql_rag_view_excludes_quarantine_by_contract() -> None:
    schema = importer.DEFAULT_SCHEMA.read_text(encoding="utf-8")
    rag_view = schema.split(
        "CREATE OR REPLACE VIEW roompilot.runtime_catalog_rag_documents AS", 1
    )[1]

    assert "FROM roompilot.style_cards_current" in rag_view
    assert "FROM roompilot.surface_materials_current" in rag_view
    assert "FROM roompilot.renovation_cost_catalog_current" in rag_view
    assert "external_import_quarantine" not in rag_view
    assert "eligible_for_api  BOOLEAN NOT NULL DEFAULT FALSE" in schema
    assert "eligible_for_rag  BOOLEAN NOT NULL DEFAULT FALSE" in schema
    assert "external_quarantine_never_api CHECK (NOT eligible_for_api)" in schema
    assert "external_quarantine_never_rag CHECK (NOT eligible_for_rag)" in schema


def test_fastapi_phase4_loaders_delegate_to_catalog_repository() -> None:
    main_source = (ROOT / "backend" / "server" / "main.py").read_text(encoding="utf-8")
    style_source = (ROOT / "backend" / "server" / "style_cards.py").read_text(
        encoding="utf-8"
    )
    cost_source = (ROOT / "backend" / "server" / "cost_estimation.py").read_text(
        encoding="utf-8"
    )

    assert "return load_runtime_surface_catalog(PROJECT_DIR, SURFACE_DB_PATH)" in main_source
    assert "return load_runtime_external_import_index(PROJECT_DIR, EXTERNAL_IMPORT_PATH)" in main_source
    assert "load_runtime_style_cards(PROJECT_DIR, STYLE_CARDS_PATH)" in style_source
    assert "load_runtime_cost_catalog(PROJECT_DIR, DEFAULT_CATALOG_PATH)" in cost_source


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS") != "1",
    reason="set ROOMPILOT_TEST_POSTGRES_RUNTIME_CATALOGS=1 for live Phase 4 PostgreSQL",
)
def test_live_phase4_postgres_counts_and_quarantine_boundary() -> None:
    status = repository.runtime_catalog_status(ROOT)
    assert status["provider"] == "kai_postgresql"
    assert status["available"] is True
    assert status["ready"] is True
    assert status["strict"] is True
    assert status["source_of_truth"] == "postgresql"
    assert status["style_card_count"] == 18
    assert status["design_style_count"] == 6
    assert status["surface_count"] == 571
    assert status["wall_surface_count"] == 110
    assert status["floor_surface_count"] == 299
    assert status["cost_rate_count"] == 6
    assert status["quarantine_count"] == 10518
    assert status["rag_count"] == 595
    assert {item["catalog_key"] for item in status["imports"]} >= {
        "design_style_profiles",
        "style_cards",
        "surface_materials",
        "renovation_costs",
    }

    with borrow_catalog_connection(ROOT) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM roompilot.external_import_quarantine
                WHERE eligible_for_api OR eligible_for_rag
                """
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                """
                SELECT ARRAY_AGG(DISTINCT document_type ORDER BY document_type)
                FROM roompilot.runtime_catalog_rag_documents
                """
            )
            assert cursor.fetchone()[0] == [
                "renovation_cost",
                "style_card",
                "surface_material",
            ]

    documents = repository.search_runtime_rag_documents(
        ROOT,
        "木地板",
        document_types=("surface_material",),
        limit=5,
    )
    assert documents
    assert all(item["document_type"] == "surface_material" for item in documents)
