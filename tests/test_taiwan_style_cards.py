from scripts.static_source_graph import scene_controller_source, scene_viewer_source

import re
from pathlib import Path

from backend.server.main import _model_priority_ids, build_site_payload
from backend.server.style_cards import find_taiwan_style_card


ROOT = Path(__file__).resolve().parents[1]


def test_site_payload_exposes_six_taiwan_style_groups_with_three_cards_each():
    cards = build_site_payload()["taiwan_style_cards"]
    assert len(cards) == 6
    assert [item["style_id"] for item in cards] == [
        "scandinavian", "japanese", "modern_minimal", "cream", "industrial", "american",
    ]
    assert all(len(item["cards"]) == 3 for item in cards)
    assert all(
        card["image_url"].startswith("data:image/svg+xml,")
        and card["image_kind"] == "project_authored_palette"
        for item in cards
        for card in item["cards"]
    )


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
    html = (ROOT / "backend" / "server" / "static" / "styles.html").read_text(encoding="utf-8")
    javascript = (ROOT / "backend" / "server" / "static" / "styles.js").read_text(encoding="utf-8")
    assert 'id="taiwan-style-gallery"' in html
    assert "renderTaiwanStyleGallery" in javascript
    assert "style_card" in javascript
    assert 'id="style-detail-panel"' not in html
    assert "renderActiveStyle();" not in javascript


def test_styles_page_copy_uses_current_catalog_card_ids():
    javascript = (ROOT / "backend" / "server" / "static" / "styles.js").read_text(encoding="utf-8")
    cards = build_site_payload()["taiwan_style_cards"]
    card_ids = {card["card_id"] for group in cards for card in group["cards"]}
    copy_block = javascript.split("const STYLE_CARD_COPY = {", 1)[1].split("\n};", 1)[0]
    copy_ids = set(re.findall(r"^  ([a-z0-9_]+):", copy_block, re.MULTILINE))

    assert copy_ids == card_ids
    assert "japanese_minimal_" not in javascript
    assert "nordic_modern_" not in javascript
    assert "wabi_sabi_" not in javascript


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
    static = ROOT / "backend" / "server" / "static"
    javascript = scene_controller_source(static)
    styles = (static / "styles.js").read_text(encoding="utf-8")
    main = "\n".join(
        (ROOT / "backend" / "server" / name).read_text(encoding="utf-8")
        for name in ("main.py", "project_routes.py", "public_routes.py")
    )
    service = (ROOT / "backend" / "server" / "scene_service.py").read_text(encoding="utf-8")
    assert 'const STYLE_CARD_STORAGE_KEY = "roompilot:selectedStyleCard"' in styles
    assert 'new URLSearchParams({ style: group.scene_style_id, style_card: card.card_id })' in styles
    assert 'query.get("style_card") || stored?.style_card' in javascript
    assert "function applyStyleCardHandoff" in javascript
    assert "candidate.id === handoff.cardId" in javascript
    assert "stylePackId: pack.id" in javascript
    assert "projectQuery.set(\"project_id\", state.projectId)" in javascript
    assert not (static / "scene.js").exists()
    assert '"style_card_id": payload.get("style_card_id")' in main
    assert 'questionnaire.get("style_card_id")' in service


def test_scene_viewer_exposes_skin_lighting_and_interior_rotation_contract():
    viewer = scene_viewer_source(ROOT / "backend" / "server" / "static")
    assert "applyStyleSkin" in viewer
    assert "style_card" in viewer
    assert "keyLight.intensity = Math.max(1.2, Number(lighting.keyLightLux" in viewer
    assert "ceilingGroup.visible = false" in viewer
    assert "controls.enableRotate = true" in viewer
