from pathlib import Path

import backend.server.scene_service as scene_service
from backend.server.scene_service import build_scene_payload
from backend.upgrade3d.dxf_parser import parse_dxf_file


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "server" / "static"


def test_scene_starts_with_project_creation_and_exposes_the_strict_upload_contract():
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    javascript = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="project-step" class="rp-step-panel is-active"' in html
    assert 'id="upload-step"' in html
    assert 'id="floorplan-file"' in html
    assert 'accept=".dxf,.png,.jpg,.jpeg,image/png,image/jpeg,application/dxf"' in html
    assert 'id="project-floorplan-confirmation"' in html
    assert "floorplanExtension" in javascript
    assert "selectFloorplanFile" in javascript
    assert "只支援 DXF、PNG、JPG 或 JPEG" in javascript
    assert 'goTo("upload")' in javascript


def test_dxf_parser_exposes_frontend_preview_contract():
    sample = next((ROOT / "testdata" / "dxf").glob("*.dxf"))
    parsed = parse_dxf_file(str(sample))

    assert parsed["width_cm"] > 0
    assert parsed["depth_cm"] > 0
    assert parsed["wall_segments"]
    segment = parsed["wall_segments"][0]
    assert set(segment) == {"start", "end"}
    assert set(segment["start"]) == {"x", "z"}
    assert set(segment["end"]) == {"x", "z"}


def test_scene_exposes_requirements_2d_library_and_visible_furniture_gate():
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    javascript = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="whole-house-fields"' in html
    assert 'data-questionnaire-stage="rooms"' in html
    assert 'id="visual-space-nav"' in html
    assert 'id="room-question-nav"' not in html
    assert 'id="keep-room-existing"' not in html
    assert 'id="keep-unfilled-rooms-existing"' not in html
    assert 'id="furniture-icon-library"' in html
    assert 'id="selected-2d-width"' in html
    assert 'id="selected-2d-depth"' in html
    assert 'id="confirm-layout-2d"' in html
    assert "confirmRequirements" in javascript
    assert "itemCollision" in javascript
    assert "resolveCatalogFurniture" in javascript
    assert "visibleFurnitureCount <= 0" in javascript


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


def test_scene_payload_reports_agent_placement_resolution(monkeypatch):
    selected_sofa = {
        "furniture_id": "huge-sofa",
        "name_zh_raw": "大型沙發",
        "normalized_type": "sofa",
        "has_model": True,
        "model_url": "/models/huge-sofa.glb",
        "primary_style": "scandinavian",
        "size_cm": {"width": 260, "depth": 180, "height": 80},
    }
    smaller_sofa = {
        "furniture_id": "small-sofa",
        "name_zh_raw": "小型沙發",
        "normalized_type": "sofa",
        "has_model": True,
        "model_url": "/models/small-sofa.glb",
        "primary_style": "scandinavian",
        "size_cm": {"width": 160, "depth": 80, "height": 80},
    }
    site_payload = {
        "styles": [{"style_id": "scandinavian", "style_name_zh": "北歐"}],
        "taiwan_style_cards": [],
        "surface_catalog": {},
        "furniture": [selected_sofa, smaller_sofa],
    }
    calls = {"count": 0}

    def fake_generate_layout(_width_cm, _depth_cm, items, **_kwargs):
        calls["count"] += 1
        item = items[0]
        return [{
            "furniture_id": item["furniture_id"],
            "name_zh_raw": item["name_zh_raw"],
            "normalized_type": item["normalized_type"],
            "size_cm": item["size_cm"],
            "position_cm": {"x": 0, "z": 0},
            "rotation_y_deg": 0,
            "position_locked": False,
            "placement_failed": calls["count"] == 1,
            "placement_reason": "too large" if calls["count"] == 1 else None,
        }]

    monkeypatch.setattr(scene_service, "generate_layout", fake_generate_layout)

    payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "required_furniture": ["sofa"],
            "selected_furniture": [selected_sofa],
            "selected_furniture_exact": True,
            "preferred_colors": [],
            "custom_colors": [],
        },
        floorplan_path=None,
        room_width_cm=220,
        room_depth_cm=180,
    )

    assert payload["scene_objects"][0]["furniture_id"] == "small-sofa"
    assert payload["scene_objects"][0]["placement_failed"] is False
    assert payload["placement_resolution_report"]
    assert payload["placement_resolution_report"][0]["action"] == "replace"


def test_scene_payload_keeps_user_required_furniture_when_placement_fails(monkeypatch):
    required_sofa = {
        "furniture_id": "required-sofa",
        "name_zh_raw": "使用者指定沙發",
        "normalized_type": "sofa",
        "has_model": True,
        "model_url": "/models/required-sofa.glb",
        "primary_style": "scandinavian",
        "size_cm": {"width": 260, "depth": 180, "height": 80},
        "user_required": True,
        "position_locked": False,
    }
    smaller_sofa = {
        "furniture_id": "small-sofa",
        "name_zh_raw": "小沙發",
        "normalized_type": "sofa",
        "has_model": True,
        "model_url": "/models/small-sofa.glb",
        "primary_style": "scandinavian",
        "size_cm": {"width": 160, "depth": 80, "height": 80},
    }
    site_payload = {
        "styles": [{"style_id": "scandinavian", "style_name_zh": "北歐"}],
        "taiwan_style_cards": [],
        "surface_catalog": {},
        "furniture": [required_sofa, smaller_sofa],
    }

    def fake_generate_layout(_width_cm, _depth_cm, items, **_kwargs):
        item = items[0]
        return [{
            "furniture_id": item["furniture_id"],
            "name_zh_raw": item["name_zh_raw"],
            "normalized_type": item["normalized_type"],
            "size_cm": item["size_cm"],
            "position_cm": {"x": 0, "z": 0},
            "rotation_y_deg": 0,
            "position_locked": False,
            "placement_failed": True,
            "placement_reason": "too large",
        }]

    monkeypatch.setattr(scene_service, "generate_layout", fake_generate_layout)

    payload = build_scene_payload(
        site_payload=site_payload,
        questionnaire={
            "space_type": "living_room",
            "style_preference": "scandinavian",
            "required_furniture": ["sofa"],
            "selected_furniture": [required_sofa],
            "selected_furniture_exact": True,
            "preferred_colors": [],
            "custom_colors": [],
        },
        floorplan_path=None,
        room_width_cm=220,
        room_depth_cm=180,
    )

    assert payload["selected_furniture"][0]["furniture_id"] == "required-sofa"
    assert payload["scene_objects"][0]["furniture_id"] == "required-sofa"
    assert payload["scene_objects"][0]["placement_failed"] is True
    assert payload["placement_resolution_report"][0]["action"] == "escalate"
