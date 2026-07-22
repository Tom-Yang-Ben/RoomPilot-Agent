from pathlib import Path
import re

import pytest

from backend.server.services import intake_service
from backend.server.routes.library import furniture_catalog
from backend.server.routes.pages import site_data
from backend.server.services.catalog_service import _get_merged_furniture_by_id, load_style_database
from backend.server.services.glb_assets import _model_response_for_merged_furniture, _model_status, _resolve_external_zip_entry


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


def test_active_catalog_uses_only_the_confirmed_six_styles_and_chinese_names():
    catalog = load_style_database()
    assert {style["style_id"] for style in catalog["styles"]} == CANONICAL_STYLE_IDS

    furniture = catalog["furniture"]
    assert furniture
    assert all(item.get("name_zh") and re.search(r"[\u4e00-\u9fff]", item["name_zh"]) for item in furniture)

    non_equipment = [item for item in furniture if item.get("catalog_scope") == "furniture"]
    assert non_equipment
    assert all(item.get("primary_style") in CANONICAL_STYLE_IDS for item in non_equipment)
    assert all(1 <= len(item.get("style_candidates", [])) <= 2 for item in non_equipment)

    equipment = [item for item in furniture if item.get("catalog_scope") == "equipment"]
    assert equipment
    assert all(item.get("primary_style") is None for item in equipment)
    assert all(item.get("style_candidates") == [] for item in equipment)


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
    assert {group["group_id"] for group in groups} >= {"living", "dining_kitchen", "bedroom", "study", "storage", "soft_decor", "equipment"}
    assert all(group["group_name_zh"] and group["types"] for group in groups)


def test_known_external_model_resolves_to_a_real_glb_response():
    furniture = _get_merged_furniture_by_id("ext_ae38fbb0527bdf")
    # 外部 GLB zip 是機器本地資源(不進版控);找不到就 skip,不算失敗 —— 系統
    # 對缺檔的正確行為由 test_unverified_remote_glb_is_not_advertised_as_available 把關。
    if _resolve_external_zip_entry(furniture) is None:
        pytest.skip("外部 GLB zip 不在本機(ROOMPILOT_EXTERNAL_GLB_ZIP_DIRS 未配置),略過實體解析驗證")
    response = _model_response_for_merged_furniture(furniture)
    assert response.body[:4] == b"glTF"


def test_site_data_is_a_small_bootstrap_payload_not_the_full_catalog():
    payload = site_data()
    assert payload["furniture"] == []
    assert payload["catalog_merge_summary"]["delivery"] == "請使用 /api/furniture 分頁取得家具資料。"


def test_unverified_remote_glb_is_not_advertised_as_available():
    assert _model_status({"glb_url": "https://example.test/furniture.glb"})[0] is False


def test_intake_has_a_single_short_default_llm_attempt():
    # intake 的模型清單已與 scene_service 共用;預設池必須維持單一模型,
    # 對話式 intake 才不會因多模型輪詢拖長首問延遲。
    from backend.server.services.scene_service import DEFAULT_OPENROUTER_MODELS

    assert len(DEFAULT_OPENROUTER_MODELS) == 1
