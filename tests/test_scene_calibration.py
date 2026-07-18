import json

from fastapi.testclient import TestClient

from roompilot.server.main import app
from test_scene_workflow import ROOT, run_workflow_script


CALIBRATION_MODULE = ROOT / "roompilot" / "server" / "static" / "scene_calibration.js"
client = TestClient(app)


def test_scene_page_exposes_two_point_scale_calibration_controls() -> None:
    response = client.get("/scene")

    assert response.status_code == 200
    assert 'id="floorplan-calibration-stage"' in response.text
    assert 'id="floorplan-calibration-overlay"' in response.text
    assert 'id="apply-floorplan-calibration"' in response.text
    assert "拖曳兩個端點，再輸入這段的實際公分" in response.text
    assert "單位固定為公分" in response.text


def test_two_image_points_and_known_length_create_scale_calibration() -> None:
    module_uri = CALIBRATION_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildScaleCalibration }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(buildScaleCalibration(
          [{{ x: 100, y: 50 }}, {{ x: 515, y: 50 }}],
          630,
        )));
        """
    )

    assert result == {
        "distance_cm": 630,
        "start_px": [100, 50],
        "end_px": [515, 50],
        "pixel_distance": 415,
        "m_per_px": 6.3 / 415,
    }


def test_pointer_position_maps_from_displayed_preview_to_original_image_pixels() -> None:
    module_uri = CALIBRATION_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ pointerToImagePoint }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(pointerToImagePoint(
          {{ clientX: 600, clientY: 350 }},
          {{ left: 100, top: 100, width: 1000, height: 500 }},
          {{ width: 2000, height: 1000 }},
        )));
        """
    )

    assert result == {"x": 1000, "y": 500}
