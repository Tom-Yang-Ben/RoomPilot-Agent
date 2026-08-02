from pathlib import Path

from backend.paths import STATIC_DIR
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
    html = (STATIC_DIR / "styles.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "styles.js").read_text(encoding="utf-8")
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
    """交接必須實作在正式頁面 scene_v2.js。

    這個斷言原本指著已停用的 scene.js，所以「風格頁挑的色卡進不了設計流程」
    在 QA 前一直是綠燈——測試盯著一份沒有人載入的檔案。
    """
    javascript = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")
    styles = (STATIC_DIR / "styles.js").read_text(encoding="utf-8")
    # /api/scene/generate 於佇列 7 拆分第三批自 main.py 搬進 scene_api.py。
    scene_api = (ROOT / "backend" / "server" / "scene_api.py").read_text(encoding="utf-8")
    service = (ROOT / "backend" / "server" / "scene_service.py").read_text(encoding="utf-8")

    # 產生端：風格頁確實會帶 style_card 參數過去。
    assert "style_card: card.card_id" in styles
    # 消費端：正式頁面要讀得到，並把它套成目前的色卡。
    assert 'sceneQuery.get("style_card")' in javascript
    assert "function applyStyleCardFromQuery" in javascript
    assert "state.activeStylePackId = pack.id" in javascript
    assert '"style_card_id": payload.get("style_card_id")' in scene_api
    assert 'questionnaire.get("style_card_id")' in service


def test_style_pack_ids_match_the_taiwan_style_card_ids():
    """兩邊的 id 空間必須一致，色卡交接才有意義。"""
    import json
    import subprocess

    from backend.server.style_cards import load_taiwan_style_cards

    module = (STATIC_DIR / "scene_style_packs.js").as_uri()
    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            f'import {{ STYLE_PACKS }} from {json.dumps(module)};'
            " console.log(JSON.stringify(STYLE_PACKS.map((pack) => pack.id)));",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    pack_ids = set(json.loads(completed.stdout))

    card_ids = set()

    def walk(node):
        if isinstance(node, dict):
            if "card_id" in node:
                card_ids.add(node["card_id"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(load_taiwan_style_cards())

    assert pack_ids == card_ids


def test_scene_viewer_exposes_skin_lighting_and_interior_rotation_contract():
    viewer = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")
    assert "applyStyleSkin" in viewer
    assert "style_card" in viewer
    assert "createStyleLights" in viewer
    assert "PointLight" in viewer
    assert "ceilingGroup.visible = false" in viewer
    assert "controls.enableRotate = true" in viewer
