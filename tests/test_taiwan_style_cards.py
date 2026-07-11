from pathlib import Path

from roompilot.server.main import _model_priority_ids, build_site_payload
from roompilot.server.style_cards import find_taiwan_style_card


ROOT = Path(__file__).resolve().parents[1]


def test_site_payload_exposes_six_taiwan_style_groups_with_three_cards_each():
    cards = build_site_payload()["taiwan_style_cards"]
    assert len(cards) == 6
    assert [item["style_id"] for item in cards] == [
        "scandinavian", "japanese", "modern_minimal", "cream", "industrial", "american",
    ]
    assert all(len(item["cards"]) == 3 for item in cards)
    assert all(card["image_url"].startswith("/static/style_cards/") for item in cards for card in item["cards"])


def test_taiwan_style_card_ids_are_unique_and_have_scene_mapping():
    cards = build_site_payload()["taiwan_style_cards"]
    card_ids = [card["card_id"] for item in cards for card in item["cards"]]
    assert len(card_ids) == len(set(card_ids))
    assert all(item["scene_style_id"] for item in cards)
    assert all(card["palette_hex"] for item in cards for card in item["cards"])


def test_style_card_lookup_is_safe_for_scene_handoff():
    cards = build_site_payload()["taiwan_style_cards"]
    selected = find_taiwan_style_card(cards, "scandinavian_1")
    assert selected and len(selected["palette_hex"]) == 3
    assert find_taiwan_style_card(cards, "missing-card") is None


def test_styles_page_is_the_six_style_gallery():
    html = (ROOT / "roompilot" / "server" / "static" / "styles.html").read_text(encoding="utf-8")
    javascript = (ROOT / "roompilot" / "server" / "static" / "styles.js").read_text(encoding="utf-8")
    assert 'id="taiwan-style-gallery"' in html
    assert "renderTaiwanStyleGallery" in javascript
    assert "style_card" in javascript
    assert 'id="style-detail-panel"' not in html
    assert "renderActiveStyle();" not in javascript


def test_unresolvable_external_furniture_does_not_steal_glb_priority():
    items = [{
        "_catalog_origin": "import",
        "furniture_id": "external-without-path",
        "has_model": True,
        "glb_absolute_path": None,
        "glb_relative_path": None,
    }]
    assert "external-without-path" not in _model_priority_ids(items)


def test_scene_accepts_style_card_handoff_from_styles_page():
    javascript = (ROOT / "roompilot" / "server" / "static" / "scene.js").read_text(encoding="utf-8")
    main = (ROOT / "roompilot" / "server" / "main.py").read_text(encoding="utf-8")
    service = (ROOT / "roompilot" / "server" / "scene_service.py").read_text(encoding="utf-8")
    assert 'sceneQuery.get("style_card")' in javascript
    assert "applyStyleCardFromQuery" in javascript
    assert "style_card_id: requestedStyleCardId" in javascript
    assert '"style_card_id": payload.get("style_card_id")' in main
    assert 'questionnaire.get("style_card_id")' in service


def test_scene_viewer_exposes_skin_lighting_and_interior_rotation_contract():
    viewer = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(encoding="utf-8")
    assert "applyStyleSkin" in viewer
    assert "style_card" in viewer
    assert "createHangingLights" in viewer
    assert "PointLight" in viewer
    assert "ceilingGroup.visible = false" in viewer
    assert "controls.enableRotate = true" in viewer
