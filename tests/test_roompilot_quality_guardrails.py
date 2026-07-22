from pathlib import Path

from backend.server.services.scene_service import build_scene_payload
from backend.upgrade3d.dxf_parser import parse_dxf_file


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_scene_starts_on_real_floorplan_step_with_visible_upload_contract():
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    javascript = (STATIC / "scene.js").read_text(encoding="utf-8")

    assert 'id="scene-floorplan-step" class="scene-floorplan-step" aria-label="上傳平面圖"' in html
    assert 'id="scene-welcome-panel" class="scene-welcome-panel" hidden' in html
    assert 'id="pick-floorplan"' in html
    assert 'id="floorplan"' in html
    assert 'id="floorplan-filename"' in html
    assert 'floorplan-legend' in html
    assert 'acceptDroppedFloorplan' in javascript
    assert 'elements.pickFloorplan?.addEventListener("click"' in javascript
    assert 'elements.floorplanFilename' in javascript
    assert 'wall_polys' in javascript
    assert 'doorSegments' in javascript
    assert 'windowSegments' in javascript
    assert 'showWizardSection("floorplan")' in javascript


def test_dxf_parser_exposes_frontend_preview_contract():
    sample = next((ROOT / "data" / "testdata" / "dxf").glob("*.dxf"))
    parsed = parse_dxf_file(str(sample))

    assert parsed["width_cm"] > 0
    assert parsed["depth_cm"] > 0
    assert parsed["wall_segments"]
    segment = parsed["wall_segments"][0]
    assert set(segment) == {"start", "end"}
    assert set(segment["start"]) == {"x", "z"}
    assert set(segment["end"]) == {"x", "z"}


def test_scene_accepts_library_proposal_and_requires_room_inputs_before_generation():
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    javascript = (STATIC / "scene.js").read_text(encoding="utf-8")

    assert 'id="scene-proposal-card"' in html
    assert 'id="scene-intake-panel"' in html
    assert 'id="scene-room-type-question"' in html
    assert 'id="scene-room-size-question"' in html
    assert 'id="scene-use-default-room"' in html
    assert "ROOMPILOT_PROPOSAL_STORAGE_KEY" in javascript
    assert "readLibraryProposal" in javascript
    assert "renderLibraryProposalSummary" in javascript
    assert "validateScenePrerequisites" in javascript
    assert "sceneData.scene_objects.length === 0" in javascript


def test_scene_payload_prioritizes_library_selected_furniture():
    selected_sofa = {
        "furniture_id": "chosen-sofa",
        "name_zh_raw": "已選沙發",
        "normalized_type": "sofa",
        "has_model": True,
        "model_url": "/models/chosen-sofa.glb",
        "primary_style": "scandinavian",
        "size_cm": {"width": 120, "depth": 70, "height": 80},
    }
    site_payload = {
        "styles": [{"style_id": "scandinavian", "style_name_zh": "北歐風"}],
        "taiwan_style_cards": [],
        "surface_catalog": {},
        "furniture": [
            selected_sofa,
            {
                "furniture_id": "auto-sofa",
                "name_zh_raw": "自動沙發",
                "normalized_type": "sofa",
                "has_model": True,
                "model_url": "/models/auto-sofa.glb",
                "primary_style": "scandinavian",
                "size_cm": {"width": 130, "depth": 70, "height": 80},
            },
            {
                "furniture_id": "auto-table",
                "name_zh_raw": "自動茶几",
                "normalized_type": "coffee-table",
                "has_model": True,
                "model_url": "/models/auto-table.glb",
                "primary_style": "scandinavian",
                "size_cm": {"width": 70, "depth": 45, "height": 40},
            },
        ],
    }

    payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "required_furniture": ["sofa", "coffee-table"],
            "selected_furniture": [selected_sofa],
            "preferred_colors": [],
            "custom_colors": [],
        },
        floorplan_path=None,
        room_width_cm=420,
        room_depth_cm=360,
    )

    furniture_ids = [item["furniture_id"] for item in payload["selected_furniture"]]
    assert furniture_ids[0] == "chosen-sofa"
    assert "auto-sofa" not in furniture_ids
    assert "auto-table" in furniture_ids
