import json

from fastapi.testclient import TestClient

from backend.server.main import app
from test_scene_workflow import ROOT, run_workflow_script


CALIBRATION_MODULE = ROOT / "backend" / "server" / "static" / "scene_calibration.js"
client = TestClient(app)


def test_scene_page_exposes_two_point_scale_calibration_controls() -> None:
    response = client.get("/scene")

    assert response.status_code == 200
    assert 'id="floorplan-calibration-stage"' in response.text
    assert 'id="floorplan-calibration-overlay"' in response.text
    assert 'id="apply-floorplan-calibration"' in response.text
    assert "拖曳兩個端點，再輸入這段的實際公分" in response.text
    assert "單位固定為公分" in response.text


def test_upload_step_has_immediate_preview_and_plain_recognition_label() -> None:
    response = client.get("/scene")

    assert response.status_code == 200
    assert 'id="upload-floorplan-preview"' in response.text
    assert 'id="upload-floorplan-placeholder"' in response.text
    assert 'id="confirm-upload" type="button" class="primary-action" disabled' in response.text
    assert ">確認並開始辨識</button>" in response.text
    assert "開始 Cody 辨識" not in response.text


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
        "cm_per_px": 630 / 415,
    }


def test_cody_scale_without_anchor_receives_a_visible_default_baseline() -> None:
    module_uri = CALIBRATION_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ calibrationPointsFromAnalysis }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(calibrationPointsFromAnalysis({{
          image_size_px: {{ width: 1079, height: 1173 }},
          scale: {{ pixel_distance: 1079, distance_cm: 949.52, cm_per_px: 0.88 }},
        }})));
        """
    )

    assert result == [{"x": 0, "y": 0}, {"x": 1079, "y": 0}]


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


def test_calibration_action_is_ready_after_two_points_and_centimeter_value() -> None:
    module_uri = CALIBRATION_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ calibrationActionState }} from {json.dumps(module_uri)};
        console.log(JSON.stringify(calibrationActionState(
          [{{ x: 100, y: 50 }}, {{ x: 918.1, y: 50 }}],
          950,
        )));
        """
    )

    assert result == {
        "ready": True,
        "message": "尺寸資料已完成，可以確認並顯示房間。",
    }


def test_calibration_action_explains_what_is_missing() -> None:
    module_uri = CALIBRATION_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ calibrationActionState }} from {json.dumps(module_uri)};
        console.log(JSON.stringify([
          calibrationActionState([{{ x: 100, y: 50 }}], 950),
          calibrationActionState(
            [{{ x: 100, y: 50 }}, {{ x: 918.1, y: 50 }}],
            "",
          ),
        ]));
        """
    )

    assert result == [
        {"ready": False, "message": "請先在平面圖上定位兩個端點。"},
        {"ready": False, "message": "請輸入大於 0 的實際公分尺寸。"},
    ]
