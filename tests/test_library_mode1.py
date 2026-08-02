from pathlib import Path

from backend.server import main
from backend.server.main import furniture_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_catalog_search_interprets_common_chinese_furniture_terms(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "_furniture_payload_cache",
        lambda: (
            {
                "furniture_id": "armchair-1",
                "name_zh": "閱讀椅",
                "name_en": "Reading lounge chair",
                "normalized_type": "armchair",
                "has_model": True,
            },
            {
                "furniture_id": "dining-chair-1",
                "name_zh": "餐椅",
                "name_en": "Dining chair",
                "normalized_type": "dining-chair",
                "has_model": True,
            },
            {
                "furniture_id": "chair-art-1",
                "name_zh": "椅子掛畫",
                "name_en": "Chair wall art",
                "normalized_type": "wall-art",
                "has_model": True,
            },
        ),
    )

    payload = furniture_catalog(
        style=None,
        group=None,
        item_type=None,
        q="椅子",
        page=1,
        page_size=24,
        has_model=True,
        detail="card",
    )

    assert [item["furniture_id"] for item in payload["items"]] == [
        "armchair-1",
        "dining-chair-1",
        "chair-art-1",
    ]


def test_mode_one_catalog_only_returns_loadable_models_and_matching_taxonomy() -> None:
    payload = furniture_catalog(
        style=None,
        group=None,
        item_type=None,
        q=None,
        page=1,
        page_size=80,
        has_model=True,
        detail="card",
    )

    assert payload["items"]
    assert all(item["has_model"] for item in payload["items"])
    assert payload["category_groups"]
    assert all(
        entry["count"] > 0
        for group in payload["category_groups"]
        for entry in group["types"]
    )


def test_mode_one_catalog_exposes_and_applies_visual_filter_facets() -> None:
    bootstrap = furniture_catalog(
        style=None,
        group="living",
        item_type=None,
        q=None,
        page=1,
        page_size=24,
        has_model=True,
        detail="card",
    )

    facets = bootstrap["filter_options"]
    assert facets["sizes"] == [
        {"value": "small", "label": "小型（80 cm 以下）"},
        {"value": "medium", "label": "中型（81–160 cm）"},
        {"value": "large", "label": "大型（161 cm 以上）"},
    ]
    assert facets["colors"]
    assert facets["materials"]

    selected_color = facets["colors"][0]["value"]
    color_filtered = furniture_catalog(
        style=None,
        group="living",
        item_type=None,
        q=None,
        page=1,
        page_size=24,
        has_model=True,
        detail="card",
        color=selected_color,
        material=None,
        size=None,
    )
    assert color_filtered["items"]
    color_aliases = {"grey": "灰色", "gray": "灰色", "white": "白色", "black": "黑色", "beige": "米色"}
    assert all(
        color_aliases.get(str(item["color"]).casefold(), item["color"]) == selected_color
        for item in color_filtered["items"]
    )

    selected_material = facets["materials"][0]["value"]
    material_filtered = furniture_catalog(
        style=None,
        group="living",
        item_type=None,
        q=None,
        page=1,
        page_size=24,
        has_model=True,
        detail="card",
        color=None,
        material=selected_material,
        size=None,
    )
    assert material_filtered["items"]
    material_aliases = {"wood": "木材", "metal": "金屬", "glass": "玻璃", "leather": "皮革"}
    assert all(
        material_aliases.get(str(item["material"]).casefold(), item["material"]) == selected_material
        for item in material_filtered["items"]
    )


def test_library_exposes_mode_one_room_type_and_proposal_contract() -> None:
    html = (ROOT / "backend/server/static/library.html").read_text(encoding="utf-8")
    script = (ROOT / "backend/server/static/library.js").read_text(encoding="utf-8")

    for element_id in (
        "mode1-space-grid",
        "mode1-space-select",
        "style-filter",
        "mode1-type-step",
        "mode1-type-grid",
        "mode1-type-next",
        "mode1-selection-list",
        "toggle-advanced-filters",
        "library-filter-row",
        "size-filter",
        "color-filter",
        "material-filter",
    ):
        assert f'id="{element_id}"' in html

    assert "has_model: true" in script
    assert "addToProposal" in script
    assert "selectDefaultFurnitureForPage" in script
    assert "mode1-card-favorite" in script
    assert "mode1-card-add" in script
    assert "return (group?.types || [])" in script
    assert "groupType.type_name_zh" in script
    assert "MODE_ONE_CATEGORY_DEFS" not in script


def test_library_places_style_next_to_space_selector() -> None:
    html = (ROOT / "backend/server/static/library.html").read_text(encoding="utf-8")

    controls_start = html.index('<div class="mode1-space-controls">')
    controls_end = html.index("</div>", controls_start)
    controls = html[controls_start:controls_end]
    assert 'id="style-filter"' in controls
    assert 'id="mode1-space-select"' in controls
    assert html.count('id="style-filter"') == 1


def test_library_mode_one_handoffs_selected_furniture_to_scene() -> None:
    html = (ROOT / "backend/server/static/library.html").read_text(encoding="utf-8")
    script = (ROOT / "backend/server/static/library.js").read_text(encoding="utf-8")

    assert 'id="enter-scene-with-proposal"' in html
    assert "帶著這些家具進入 3D 場景" in html
    assert "ROOMPILOT_PROPOSAL_STORAGE_KEY" in script
    assert "roompilot:sceneProposal" in script
    assert "enterSceneWithProposal" in script
    assert 'window.location.href = "/scene?source=library"' in script
    assert "本次方案清單" in html
