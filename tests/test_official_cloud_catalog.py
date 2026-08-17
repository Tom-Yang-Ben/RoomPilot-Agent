from __future__ import annotations

from backend.catalog.fixture_repository import load_fixture_catalog
from backend.server import main


def _clear_catalog_caches() -> None:
    main.load_style_database.cache_clear()
    main._merged_furniture_catalog_cached.cache_clear()
    main._furniture_payload_cache.cache_clear()
    main._catalog_count_summary.cache_clear()


def test_portable_catalog_is_small_project_authored_fixture() -> None:
    _clear_catalog_caches()
    items = main.load_style_database()["furniture"]

    assert items == list(load_fixture_catalog())
    assert len(items) == 16
    assert len({item["furniture_id"] for item in items}) == len(items)
    assert all(item["catalog_scope"] == "portable_fixture" for item in items)
    assert all(item["render_mode"] == "procedural_fixture" for item in items)


def test_portable_catalog_does_not_claim_remote_assets() -> None:
    _clear_catalog_caches()
    items = main._furniture_payload_cache()

    assert len(items) == 16
    assert all(item["has_model"] is True for item in items)
    assert all(item["model_url"] is None for item in items)
    assert all(not item.get("image_url") for item in items)


def test_portable_catalog_preserves_room_and_rag_metadata() -> None:
    _clear_catalog_caches()
    items = main._furniture_payload_cache()

    assert all(item.get("room_types") for item in items)
    assert all(item.get("catalog_role") for item in items)
    assert all(item.get("description") for item in items)
    assert all(item.get("rag_text") for item in items)
    assert any("bedroom" in item["room_types"] for item in items)


def test_catalog_summary_uses_the_active_furniture_provider() -> None:
    _clear_catalog_caches()
    items = main._furniture_payload_cache()
    summary = main._catalog_count_summary()

    assert summary["total_furniture"] == len(items)
    assert summary["styled_furniture"] + summary["fallback_furniture"] == len(items)


def test_style_presentation_is_metadata_only_in_full_profile(monkeypatch) -> None:
    monkeypatch.setenv("ROOMPILOT_PROFILE", "full")
    main.load_style_database.cache_clear()
    try:
        catalog = main.load_style_database()
        assert catalog["furniture"] == []
        assert catalog["schema_version"] == "full-postgres-v1"
        assert len(catalog["styles"]) == 6
    finally:
        monkeypatch.setenv("ROOMPILOT_PROFILE", "portable")
        main.load_style_database.cache_clear()
