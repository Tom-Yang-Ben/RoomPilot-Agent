from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.catalog.postgres_repository import borrow_catalog_connection
from backend.catalog.runtime_catalog_repository import runtime_catalog_provider_mode
from backend.server import main


ROOT = Path(__file__).resolve().parents[1]


def test_provider_defaults_are_strict_without_an_implicit_auto_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ROOMPILOT_CATALOG_PROVIDER", raising=False)
    monkeypatch.delenv("ROOMPILOT_RUNTIME_CATALOG_PROVIDER", raising=False)

    assert main.catalog_provider_mode(tmp_path) == "postgres"
    assert runtime_catalog_provider_mode(tmp_path) == "postgres"


def test_formal_furniture_compatibility_loader_reads_sql_on_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def load_sql(_project: Path):
        nonlocal calls
        calls += 1
        return ({"furniture_id": f"sql-{calls}"},)

    monkeypatch.setattr(main, "catalog_provider_mode", lambda _project: "postgres")
    monkeypatch.setattr(main, "load_postgres_catalog", load_sql)

    assert main._furniture_payload_cache()[0]["furniture_id"] == "sql-1"
    assert main._furniture_payload_cache()[0]["furniture_id"] == "sql-2"
    assert calls == 2


def test_formal_site_payload_never_calls_the_legacy_json_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "catalog_provider_mode", lambda _project: "postgres")
    monkeypatch.setattr(
        main,
        "load_style_database",
        lambda: (_ for _ in ()).throw(AssertionError("legacy JSON must not load")),
    )
    monkeypatch.setattr(
        main,
        "load_surface_catalog",
        lambda: {"surfaces": [], "style_surface_profiles": {}},
    )
    monkeypatch.setattr(
        main,
        "_catalog_count_summary",
        lambda: {
            "total_furniture": 2,
            "styled_furniture": 2,
            "fallback_furniture": 0,
            "style_furniture_counts": {},
            "style_type_counts": {},
        },
    )
    monkeypatch.setattr(main, "_style_payloads", lambda **_kwargs: [{"style_id": "sql"}])
    monkeypatch.setattr(main, "load_taiwan_style_cards", lambda: [])

    payload = main.build_site_payload(include_furniture=False)

    assert payload["styles"] == [{"style_id": "sql"}]
    assert payload["furniture"] == []
    assert payload["summary"]["total_furniture"] == 2


def test_strict_catalog_status_does_not_read_manifest_files_when_sql_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "catalog_provider_mode", lambda _project: "postgres")
    monkeypatch.setattr(
        main,
        "catalog_provider_status",
        lambda _project: {
            "provider": "kai_postgresql",
            "available": False,
            "ready": False,
            "strict": True,
            "source_of_truth": "postgresql",
            "reason": "offline",
        },
    )
    monkeypatch.setattr(
        main,
        "runtime_catalog_status",
        lambda _project: {
            "provider": "kai_postgresql",
            "available": False,
            "ready": False,
            "strict": True,
            "source_of_truth": "postgresql",
            "reason": "offline",
        },
    )
    monkeypatch.setattr(
        main,
        "manifest_status",
        lambda: (_ for _ in ()).throw(AssertionError("GLB CSV must not load")),
    )
    monkeypatch.setattr(
        main,
        "image_manifest_status",
        lambda: (_ for _ in ()).throw(AssertionError("image CSV must not load")),
    )

    status = main.catalog_status()

    assert status["ready"] is False
    assert status["source_of_truth"] == "postgresql"
    assert status["furniture"]["verified_model_count"] == 0
    assert status["furniture"]["manifest_error"] == "offline"


def test_formal_health_is_503_when_required_database_tables_are_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "catalog_provider_mode", lambda _project: "postgres")
    monkeypatch.setattr(main, "PROJECT_STORE", SimpleNamespace(provider="postgres"))
    monkeypatch.setattr(
        main,
        "catalog_status",
        lambda: {
            "ready": False,
            "source_of_truth": "postgresql",
            "catalog_provider": {"database": {"project_table_ready": False}},
        },
    )

    response = main.api_health()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert payload["status"] == "unavailable"
    assert payload["formal"] is True
    assert payload["project_store"]["ready"] is False


def test_phase5_schema_versions_design_profiles_and_no_cache_health_contract() -> None:
    schema = (
        ROOT / "scripts" / "runtime_catalog" / "roompilot_runtime_catalog_schema.sql"
    ).read_text(encoding="utf-8")
    source = (ROOT / "backend" / "server" / "main.py").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS roompilot.design_style_profiles" in schema
    assert "roompilot.design_style_profiles_current" in schema
    assert "database_read_through_no_runtime_file_cache" in source
    assert "build_site_payload(*, include_furniture: bool = True)" in source


@pytest.mark.skipif(
    os.getenv("ROOMPILOT_TEST_POSTGRES_CATALOGS") != "1",
    reason="set ROOMPILOT_TEST_POSTGRES_CATALOGS=1 for live Phase 5 PostgreSQL",
)
def test_live_postgres_updates_are_visible_without_restart_or_cache_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = f"phase5-{uuid4().hex}"
    monkeypatch.setenv("ROOMPILOT_CATALOG_PROVIDER", "postgres")
    monkeypatch.setenv("ROOMPILOT_RUNTIME_CATALOG_PROVIDER", "postgres")

    with borrow_catalog_connection(ROOT) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT style_id, payload
                FROM roompilot.design_style_profiles_current
                ORDER BY style_order LIMIT 1
                """
            )
            style_id, original_style = cursor.fetchone()
            cursor.execute(
                """
                SELECT surface_id, name_zh, payload
                FROM roompilot.surface_materials_current
                ORDER BY surface_id LIMIT 1
                """
            )
            surface_id, original_surface_name, original_surface = cursor.fetchone()
            cursor.execute(
                """
                SELECT item_id, name_zh
                FROM roompilot.furniture_catalog_api_current
                WHERE kind = 'furniture'
                ORDER BY item_id LIMIT 1
                """
            )
            item_id, original_furniture_name = cursor.fetchone()

    try:
        with borrow_catalog_connection(ROOT) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE roompilot.design_style_profiles
                    SET payload = JSONB_SET(payload, '{core_description_zh}', TO_JSONB(%s::TEXT)),
                        updated_at = NOW()
                    WHERE style_id = %s
                    """,
                    (marker, style_id),
                )
                cursor.execute(
                    """
                    UPDATE roompilot.surface_materials
                    SET name_zh = %s,
                        payload = JSONB_SET(payload, '{name_zh}', TO_JSONB(%s::TEXT)),
                        updated_at = NOW()
                    WHERE surface_id = %s
                    """,
                    (marker, marker, surface_id),
                )
                cursor.execute(
                    "UPDATE roompilot.furniture_items SET name_zh = %s WHERE item_id = %s",
                    (marker, item_id),
                )

        styles = main._style_payloads(
            surface_catalog={"surfaces": [], "style_surface_profiles": {}}
        )
        surfaces = main.load_surface_catalog()["surfaces"]
        furniture = main._furniture_payload_cache()

        assert next(item for item in styles if item["style_id"] == style_id)[
            "core_description_zh"
        ] == marker
        assert next(item for item in surfaces if item["surface_id"] == surface_id)[
            "name_zh"
        ] == marker
        assert next(item for item in furniture if item["furniture_id"] == item_id)[
            "name_zh"
        ] == marker
    finally:
        with borrow_catalog_connection(ROOT) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE roompilot.design_style_profiles
                    SET payload = %s::JSONB, updated_at = NOW()
                    WHERE style_id = %s
                    """,
                    (json.dumps(original_style, ensure_ascii=False), style_id),
                )
                cursor.execute(
                    """
                    UPDATE roompilot.surface_materials
                    SET name_zh = %s, payload = %s::JSONB, updated_at = NOW()
                    WHERE surface_id = %s
                    """,
                    (
                        original_surface_name,
                        json.dumps(original_surface, ensure_ascii=False),
                        surface_id,
                    ),
                )
                cursor.execute(
                    "UPDATE roompilot.furniture_items SET name_zh = %s WHERE item_id = %s",
                    (original_furniture_name, item_id),
                )
