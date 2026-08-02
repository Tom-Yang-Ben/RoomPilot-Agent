from pathlib import Path
import re

import pytest

from backend.server import intake_service
from backend.server.main import (
    _merged_furniture_catalog_cached,
    _model_response_for_merged_furniture,
    _model_status,
    _resolve_external_zip_entry,
    furniture_catalog,
    load_style_database,
    site_data,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "catalog" / "data"
ARCHIVE_DIR = DATA_DIR / "舊友：12種風格與JSON"
CANONICAL_STYLE_IDS = {
    "scandinavian",
    "modern_minimal",
    "japanese",
    "cream",
    "industrial",
    "american",
}


def test_old_twelve_style_json_is_archived_outside_the_active_catalog():
    assert ARCHIVE_DIR.is_dir()
    assert (ARCHIVE_DIR / "ikea_furniture_style_database.json").is_file()
    assert (ARCHIVE_DIR / "external_furniture_import_index.json").is_file()
    assert (ARCHIVE_DIR / "README.md").is_file()


def test_active_catalog_uses_the_official_cloud_set_and_only_confirmed_styles():
    catalog = load_style_database()
    assert {style["style_id"] for style in catalog["styles"]} == CANONICAL_STYLE_IDS

    furniture = catalog["furniture"]
    assert len(furniture) == 8_675
    assert all(item.get("name_zh") and re.search(r"[\u4e00-\u9fff]", item["name_zh"]) for item in furniture)

    classified = [item for item in furniture if item.get("primary_style")]
    unclassified = [item for item in furniture if not item.get("primary_style")]
    assert len(classified) == 8_675
    assert len(unclassified) == 0
    assert all(item["primary_style"] in CANONICAL_STYLE_IDS for item in classified)
    assert all(
        set(candidate["style_id"] for candidate in item.get("style_candidates", []))
        <= CANONICAL_STYLE_IDS
        for item in classified
    )
    assert all(item.get("style_candidates") == [] for item in unclassified)


def test_library_exposes_hierarchical_category_options():
    payload = furniture_catalog(
        style=None,
        group=None,
        item_type=None,
        q=None,
        page=1,
        page_size=1,
        has_model=None,
        detail="card",
    )
    groups = payload["category_groups"]
    assert {group["group_id"] for group in groups} >= {
        "living",
        "dining_kitchen",
        "bedroom",
        "study",
        "storage",
        "soft_decor",
    }
    assert "equipment" not in {group["group_id"] for group in groups}
    assert all(group["group_name_zh"] and group["types"] for group in groups)


def test_an_available_external_model_resolves_to_a_real_glb_response(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    furniture = next(
        (
        item
        for item in _merged_furniture_catalog_cached()
        if _resolve_external_zip_entry(item) is not None
        ),
        None,
    )
    if furniture is None:
        pytest.skip("未設定外部離線 GLB 備援包")
    response = _model_response_for_merged_furniture(furniture)
    assert response.body[:4] == b"glTF"


def test_site_data_is_a_small_bootstrap_payload_not_the_full_catalog():
    payload = site_data()
    assert payload["furniture"] == []
    assert payload["catalog_merge_summary"]["delivery"] == "請使用 /api/furniture 分頁取得家具資料。"


def test_remote_glb_is_advertised_when_the_server_proxy_can_load_it(monkeypatch):
    monkeypatch.setenv("ROOMPILOT_MODEL_DELIVERY_MODE", "local")
    available, reason = _model_status({"glb_url": "https://example.test/furniture.glb"})

    assert available is True
    assert "代理" in reason


def test_intake_has_a_single_short_default_llm_attempt():
    assert len(intake_service.DEFAULT_MODELS) == 1


def test_intake_service_resolves_repository_root():
    assert Path(intake_service.PROJECT_DIR) == ROOT
