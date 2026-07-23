from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from roompilot.server.main import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def _blank_png() -> bytes:
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_floorplan_analyze_then_confirm_http_e2e() -> None:
    geometry = [
        {"kind": "wall", "start_px": [0, 0], "end_px": [600, 0]},
        {"kind": "wall", "start_px": [600, 0], "end_px": [600, 400]},
        {"kind": "wall", "start_px": [600, 400], "end_px": [0, 400]},
        {"kind": "wall", "start_px": [0, 400], "end_px": [0, 0]},
        {"kind": "door", "start_px": [0, 300], "end_px": [0, 210]},
        {"kind": "window", "start_px": [200, 0], "end_px": [320, 0]},
    ]
    response = client.post(
        "/api/floorplan/analyze",
        files={"file": ("builder-plan.png", _blank_png(), "image/png")},
        data={
            "calibration_json": json.dumps(
                {"distance_cm": 600, "start_px": [0, 0], "end_px": [600, 0]}
            ),
            "ocr_json": json.dumps(
                [{"text": "廚房", "bbox": [240, 170, 300, 200], "confidence": 0.99}],
                ensure_ascii=False,
            ),
            "geometry_json": json.dumps(geometry),
            "observed_utilities_json": json.dumps(
                [
                    {
                        "room_id": "kitchen-1",
                        "utility": "water",
                        "code": "sink_fixture_observed",
                        "confidence": 0.93,
                    }
                ]
            ),
            "brief_json": json.dumps(
                {
                    "utilities": [
                        {
                            "room_id": "kitchen-1",
                            "utility": "gas",
                            "code": "cooking_gas",
                            "confirmed": True,
                        }
                    ]
                }
            ),
        },
    )

    assert response.status_code == 200
    analyzed = response.json()
    assert analyzed["analysis"]["scale"]["cm_per_px"] == 1.0
    assert analyzed["requirements"]["rooms"][0]["room_type"] == "kitchen"
    requirements = analyzed["requirements"]["rooms"][0]["requirements"]
    assert next(item for item in requirements if item["code"] == "sink_fixture_observed")["source"] == "floorplan_observation"
    assert next(item for item in requirements if item["code"] == "cooking_gas")["source"] == "user_confirmation"

    confirmed = client.post(
        "/api/floorplan/confirm",
        json={"analysis": analyzed["analysis"]},
    )

    assert confirmed.status_code == 200
    payload = confirmed.json()
    assert payload["ready_for_design"] is True
    assert payload["floorplan"]["width_cm"] == 600.0
    assert payload["floorplan"]["door_segments"]
    assert payload["floorplan"]["window_segments"]
    confirmed_requirements = payload["requirements"]["rooms"][0]["requirements"]
    assert next(item for item in confirmed_requirements if item["code"] == "cooking_gas")["source"] == "user_confirmation"

    scene = client.post(
        "/api/scene/generate",
        json={
            "client_brief": {
                "space": {"type": "kitchen", "width_cm": 600, "depth_cm": 400},
                "style": {"preferred": ["scandinavian"], "colors": [], "materials": []},
                "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
                "needs": [],
                "constraints": ["keep_door_clear", "keep_window_clear"],
            },
            "floorplan_filename": "confirmed-floorplan.dxf",
            "floorplan_dxf_text": payload["dxf_text"],
            "required_furniture": [],
        },
    )

    assert scene.status_code == 200
    scene_payload = scene.json()
    assert scene_payload["floorplan"]["source"] == "dxf"
    # 引擎可擺放寬度扣除預設 18 cm 牆厚；原始確認 DXF 仍保留 600 cm。
    assert scene_payload["floorplan"]["width_cm"] == 582.0
    assert scene_payload["floorplan"]["door_segments"]
    assert scene_payload["floorplan"]["window_segments"]


def test_floorplan_confirm_rejects_unscaled_analysis() -> None:
    response = client.post(
        "/api/floorplan/confirm",
        json={"analysis": {"scale": None, "walls": []}},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "scale_confirmation_required"


def test_builder_plan_630_confirmed_annotations_reach_scene_e2e() -> None:
    image_path = ROOT / "testdata" / "png" / "builder_plan_630.png"
    annotations = json.loads(
        (ROOT / "testdata" / "png" / "builder_plan_630_annotations.json").read_text(encoding="utf-8")
    )
    analyzed_response = client.post(
        "/api/floorplan/analyze",
        files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
        data={
            "ocr_json": json.dumps(annotations["ocr"], ensure_ascii=False),
            "geometry_json": json.dumps(annotations["geometry"]),
        },
    )

    assert analyzed_response.status_code == 200
    analysis = analyzed_response.json()["analysis"]
    assert analysis["scale"]["distance_cm"] == 630.0
    assert analysis["requires_confirmation"] is False
    assert len(analysis["doors"]) == 7
    assert len(analysis["windows"]) == 5

    confirmed = client.post("/api/floorplan/confirm", json={"analysis": analysis})
    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()
    scene = client.post(
        "/api/scene/generate",
        json={
            "client_brief": {
                "space": {"type": "living_room"},
                "style": {"preferred": ["scandinavian"], "colors": [], "materials": []},
                "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
                "needs": [],
                "constraints": ["keep_door_clear", "keep_window_clear"],
            },
            "floorplan_filename": "builder-plan-630-confirmed.dxf",
            "floorplan_dxf_text": confirmed_payload["dxf_text"],
            "required_furniture": [],
        },
    )

    assert scene.status_code == 200
    floorplan = scene.json()["floorplan"]
    assert floorplan["source"] == "dxf"
    assert floorplan["door_count"] == 7
    assert floorplan["window_count"] == 5


def test_builder_plan_630_upload_is_automatically_recognized_without_annotation_fields() -> None:
    image_path = ROOT / "testdata" / "png" / "builder_plan_630.png"

    response = client.post(
        "/api/floorplan/analyze",
        files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
    )

    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["recognition_mode"] == "cody_vision"
    assert analysis["recognition_engine"] == "cody"
    assert analysis["scale"]["distance_cm"] == 630.0
    assert analysis["spatial_report"]["room_counts"] == {
        "bedroom": 3,
        "bathroom": 2,
        "kitchen": 1,
        "dining_room": 1,
        "living_room": 1,
        "balcony": 1,
    }
    assert len(analysis["doors"]) == 7
    assert len(analysis["windows"]) == 3
    assert analysis["spatial_report"]["review_items"] == []


def test_builder_plan_630_cody_dimensions_survive_confirm_and_scene_generation() -> None:
    image_path = ROOT / "testdata" / "png" / "builder_plan_630.png"
    analyzed = client.post(
        "/api/floorplan/analyze",
        files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
    )
    assert analyzed.status_code == 200

    confirmed = client.post(
        "/api/floorplan/confirm",
        json={"analysis": analyzed.json()["analysis"]},
    )
    assert confirmed.status_code == 200
    confirmed_payload = confirmed.json()

    scene = client.post(
        "/api/scene/generate",
        json={
            "client_brief": {
                "space": {"type": "living_room"},
                "style": {"preferred": ["scandinavian"], "colors": [], "materials": []},
                "occupants": {"adults": 2, "children": 0, "elderly": 0, "pets": 0},
                "needs": [],
                "constraints": ["keep_door_clear", "keep_window_clear"],
            },
            "floorplan_filename": "builder-plan-630-cody.dxf",
            "floorplan_dxf_text": confirmed_payload["dxf_text"],
            "required_furniture": [],
        },
    )
    assert scene.status_code == 200

    confirmed_floorplan = confirmed_payload["floorplan"]
    scene_floorplan = scene.json()["floorplan"]
    assert scene_floorplan["width_cm"] == confirmed_floorplan["width_cm"]
    assert scene_floorplan["depth_cm"] == confirmed_floorplan["depth_cm"]
    assert scene_floorplan["wall_count"] >= len(analyzed.json()["analysis"]["walls"])


def test_builder_plan_630_uses_cody_as_the_only_geometry_engine() -> None:
    image_path = ROOT / "testdata" / "png" / "builder_plan_630.png"

    response = client.post(
        "/api/floorplan/analyze",
        files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
        data={
            "calibration_json": json.dumps(
                {"distance_cm": 630, "start_px": [112, 27], "end_px": [456, 27]}
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    analysis = payload["analysis"]
    assert payload["geometry_engine"] == "cody"
    assert analysis["recognition_engine"] == "cody"
    assert analysis["recognition_mode"] == "cody_vision"
    for key in ("walls", "doors", "windows"):
        assert analysis[key], f"Cody must detect at least one {key} item"
        assert {item["source"] for item in analysis[key]} == {"cody_vision"}


def test_builder_plan_630_two_point_calibration_can_be_confirmed() -> None:
    image_path = ROOT / "testdata" / "png" / "builder_plan_630.png"
    response = client.post(
        "/api/floorplan/analyze",
        files={"file": (image_path.name, image_path.read_bytes(), "image/png")},
        data={
            "calibration_json": json.dumps(
                {"distance_cm": 630, "start_px": [112, 27], "end_px": [456, 27]}
            )
        },
    )

    assert response.status_code == 200
    analysis = response.json()["analysis"]
    assert analysis["scale"]["distance_cm"] == 630.0
    assert analysis["scale"]["pixel_distance"] == 344
    assert analysis["scale"]["source"] == "manual_confirmation"
    assert len(analysis["walls"]) > 0

    confirmed = client.post(
        "/api/floorplan/confirm",
        json={
            "analysis": analysis,
            "corrections": {
                "scale": analysis["scale"],
                "walls": analysis["walls"],
                "doors": analysis["doors"],
                "windows": analysis["windows"],
            },
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["ready_for_design"] is True
