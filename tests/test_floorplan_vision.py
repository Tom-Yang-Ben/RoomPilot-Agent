from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
import pytest

from roompilot.floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)


def _dimension_image() -> bytes:
    image = np.full((120, 720, 3), 255, dtype=np.uint8)
    cv2.line(image, (140, 32), (555, 32), (0, 0, 0), 1)
    cv2.circle(image, (140, 32), 5, (0, 0, 0), -1)
    cv2.circle(image, (555, 32), 5, (0, 0, 0), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _synthetic_floorplan() -> bytes:
    image = np.full((400, 500, 3), 255, dtype=np.uint8)
    # 四周雙線牆。
    for y in (50, 60):
        cv2.line(image, (50, y), (450, y), (0, 0, 0), 2)
    for y in (340, 350):
        cv2.line(image, (50, y), (110, y), (0, 0, 0), 2)
        cv2.line(image, (220, y), (450, y), (0, 0, 0), 2)
    for x in (50, 60, 440, 450):
        cv2.line(image, (x, 50), (x, 350), (0, 0, 0), 2)
    # 上側四線窗，跨度 100 px。
    for y in (50, 53, 57, 60):
        cv2.line(image, (200, y), (300, y), (0, 0, 0), 1)
    # 90 px 門扇與開啟弧。
    cv2.line(image, (120, 330), (210, 330), (0, 0, 0), 2)
    cv2.line(image, (120, 330), (120, 240), (0, 0, 0), 2)
    cv2.ellipse(image, (120, 330), (90, 90), 0, 270, 360, (0, 0, 0), 2)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_analyze_floorplan_image_calibrates_630_cm_dimension() -> None:
    analysis = analyze_floorplan_image(
        _dimension_image(),
        filename="builder-plan.png",
        ocr_observations=[
            {
                "text": "630",
                "bbox": [325, 4, 371, 27],
                "confidence": 0.99,
            }
        ],
    )

    assert analysis["scale"]["distance_m"] == 6.3
    assert analysis["scale"]["pixel_distance"] == 415
    assert analysis["scale"]["m_per_px"] == 0.015181
    assert analysis["scale"]["source"] == "dimension_ocr"
    assert analysis["coordinate_system"] == {
        "unit": "metre",
        "origin": "plan_bbox_bottom_left",
        "x_axis": "right",
        "y_axis": "up",
    }
    assert analysis["evidence"][0]["text"] == "630"
    assert analysis["requires_scale_confirmation"] is False


def test_analyze_floorplan_image_requires_confirmation_without_scale_anchor() -> None:
    image = np.full((80, 120, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    analysis = analyze_floorplan_image(encoded.tobytes(), filename="unknown.png")

    assert analysis["scale"] is None
    assert analysis["requires_confirmation"] is True
    assert "scale_anchor_missing" in analysis["issues"]


def test_low_confidence_ocr_scale_requires_manual_scale_correction() -> None:
    analysis = analyze_floorplan_image(
        _dimension_image(),
        ocr_observations=[{"text": "630", "bbox": [325, 4, 371, 27], "confidence": 0.4}],
        geometry_observations=[
            {"kind": "wall", "start_px": [0, 0], "end_px": [600, 0]},
            {"kind": "wall", "start_px": [600, 0], "end_px": [600, 100]},
        ],
    )

    assert analysis["requires_scale_confirmation"] is True
    with pytest.raises(ValueError, match="scale_confirmation_required"):
        confirm_floorplan_analysis(analysis)

    corrected_scale = {**analysis["scale"], "distance_m": 6.3, "m_per_px": 0.015181}
    confirmed = confirm_floorplan_analysis(analysis, corrections={"scale": corrected_scale})
    assert confirmed["analysis"]["scale"]["source"] == "manual_confirmation"


def test_analyze_floorplan_image_transforms_confirmed_walls_doors_and_windows() -> None:
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        calibration_hint={"distance_cm": 600, "start_px": [0, 0], "end_px": [600, 0]},
        geometry_observations=[
            {"kind": "wall", "start_px": [0, 400], "end_px": [600, 400], "confidence": 1.0},
            {"kind": "door", "start_px": [100, 400], "end_px": [190, 400], "confidence": 1.0},
            {"kind": "window", "start_px": [300, 0], "end_px": [420, 0], "confidence": 1.0},
        ],
    )

    assert analysis["walls"] == [
        {
            "start": {"x": 0.0, "y": 0.0},
            "end": {"x": 6.0, "y": 0.0},
            "confidence": 1.0,
            "source": "confirmed_geometry",
        }
    ]
    assert analysis["doors"][0]["width_m"] == 0.9
    assert analysis["windows"][0]["width_m"] == 1.2
    assert analysis["requires_confirmation"] is False


def test_analyze_floorplan_image_uses_cody_for_synthetic_geometry() -> None:
    analysis = analyze_floorplan_image(
        _synthetic_floorplan(),
        calibration_hint={"distance_cm": 500, "start_px": [0, 0], "end_px": [500, 0]},
    )

    assert len(analysis["walls"]) >= 4
    assert analysis["recognition_engine"] == "cody"
    assert {wall["source"] for wall in analysis["walls"]} == {"cody_vision"}
    assert all(item["source"] == "cody_vision" for item in analysis["doors"])
    assert all(item["source"] == "cody_vision" for item in analysis["windows"])


def test_cody_geometry_can_be_confirmed_without_roompilot_fallback_corrections() -> None:
    analysis = analyze_floorplan_image(
        _synthetic_floorplan(),
        calibration_hint={"distance_cm": 500, "start_px": [0, 0], "end_px": [500, 0]},
    )

    confirmed = confirm_floorplan_analysis(analysis)

    assert confirmed["ready_for_design"] is True
    assert {item["source"] for item in confirmed["analysis"]["walls"]} == {"cody_vision"}


def test_analyze_floorplan_image_normalizes_room_labels_to_metre_coordinates() -> None:
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        filename="rooms.png",
        calibration_hint={
            "distance_cm": 600,
            "start_px": [0, 0],
            "end_px": [600, 0],
        },
        ocr_observations=[
            {"text": "客廳", "bbox": [60, 250, 120, 280], "confidence": 0.98},
            {"text": "廚房", "bbox": [60, 80, 120, 110], "confidence": 0.97},
            {"text": "浴廁", "bbox": [300, 80, 360, 110], "confidence": 0.96},
            {"text": "主臥室", "bbox": [300, 250, 390, 280], "confidence": 0.99},
        ],
    )

    assert [room["type"] for room in analysis["rooms"]] == [
        "living_room",
        "kitchen",
        "bathroom",
        "bedroom",
    ]
    assert analysis["rooms"][0]["label"] == "客廳"
    assert analysis["rooms"][0]["centroid_m"] == {"x": 0.9, "y": 1.35}


def test_high_confidence_room_has_traceable_inner_dimensions_without_blanket_confirmation() -> None:
    image = np.full((300, 400, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        filename="bedroom.png",
        calibration_hint={"distance_cm": 400, "start_px": [0, 0], "end_px": [400, 0]},
        ocr_observations=[
            {"text": "主臥室", "bbox": [165, 130, 235, 170], "confidence": 0.97},
        ],
        geometry_observations=[
            {"kind": "wall", "start_px": [0, 0], "end_px": [400, 0], "confidence": 0.99},
            {"kind": "wall", "start_px": [400, 0], "end_px": [400, 300], "confidence": 0.99},
            {"kind": "wall", "start_px": [400, 300], "end_px": [0, 300], "confidence": 0.99},
            {"kind": "wall", "start_px": [0, 300], "end_px": [0, 0], "confidence": 0.99},
        ],
    )

    room = analysis["spatial_report"]["rooms"][0]
    assert room["room_id"] == "bedroom-1"
    assert room["inner_dimensions_m"] == {"width": 4.0, "depth": 3.0}
    assert room["net_area_m2"] == 12.0
    assert room["confidence"]["level"] == "high"
    assert room["evidence"][0]["kind"] == "ocr_room_label"
    assert analysis["spatial_report"]["review_items"] == []
    assert analysis["requires_confirmation"] is False


def test_infer_room_requirements_distinguishes_required_and_conditional_utilities() -> None:
    result = infer_room_requirements(
        {
            "rooms": [
                {"id": "living-1", "type": "living_room", "label": "客廳", "confidence": 0.98},
                {"id": "kitchen-1", "type": "kitchen", "label": "廚房", "confidence": 0.97},
                {"id": "bathroom-1", "type": "bathroom", "label": "浴廁", "confidence": 0.96},
                {"id": "bedroom-1", "type": "bedroom", "label": "主臥室", "confidence": 0.99},
            ]
        }
    )

    kitchen = next(room for room in result["rooms"] if room["room_type"] == "kitchen")
    assert {item["utility"] for item in kitchen["requirements"]} >= {"electricity", "water", "drainage", "gas"}
    gas = next(item for item in kitchen["requirements"] if item["utility"] == "gas")
    assert gas["status"] == "conditional"
    assert gas["requires_confirmation"] is True
    assert gas["source"] == "room_type_rule"

    bathroom = next(room for room in result["rooms"] if room["room_type"] == "bathroom")
    assert any(item["code"] == "hot_cold_water" for item in bathroom["requirements"])
    assert any(item["code"] == "leakage_protected_power" for item in bathroom["requirements"])
    living = next(room for room in result["rooms"] if room["room_type"] == "living_room")
    assert not any(item["utility"] == "gas" and item["status"] == "required" for item in living["requirements"])
    assert result["requires_professional_review"] is True


def test_user_can_explicitly_reject_a_room_utility_requirement() -> None:
    result = infer_room_requirements(
        {"rooms": [{"id": "kitchen-1", "type": "kitchen", "label": "廚房"}]},
        {"utilities": [{"room_id": "kitchen-1", "utility": "gas", "code": "cooking_gas", "confirmed": False}]},
    )

    gas = next(item for item in result["rooms"][0]["requirements"] if item["code"] == "cooking_gas")
    assert gas["status"] == "rejected"
    assert gas["source"] == "user_confirmation"
    assert gas["requires_confirmation"] is False

def test_infer_room_requirements_preserves_observed_and_user_confirmed_provenance() -> None:
    result = infer_room_requirements(
        {
            "rooms": [{"id": "kitchen-1", "type": "kitchen", "label": "廚房", "confidence": 0.98}],
            "observed_utilities": [
                {
                    "room_id": "kitchen-1",
                    "utility": "water",
                    "code": "sink_fixture_observed",
                    "confidence": 0.91,
                }
            ],
        },
        brief={
            "utilities": [
                {
                    "room_id": "kitchen-1",
                    "utility": "gas",
                    "code": "cooking_gas",
                    "confirmed": True,
                }
            ]
        },
    )

    requirements = result["rooms"][0]["requirements"]
    observed = next(item for item in requirements if item["code"] == "sink_fixture_observed")
    assert observed["source"] == "floorplan_observation"
    assert observed["status"] == "observed"
    confirmed = next(item for item in requirements if item["code"] == "cooking_gas")
    assert confirmed["source"] == "user_confirmation"
    assert confirmed["status"] == "confirmed"
    assert confirmed["requires_confirmation"] is False


def test_confirm_floorplan_analysis_exports_dxf_and_engine_payload() -> None:
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        calibration_hint={"distance_cm": 600, "start_px": [0, 0], "end_px": [600, 0]},
        ocr_observations=[{"text": "廚房", "bbox": [240, 170, 300, 200], "confidence": 0.99}],
        geometry_observations=[
            {"kind": "wall", "start_px": [0, 0], "end_px": [600, 0]},
            {"kind": "wall", "start_px": [600, 0], "end_px": [600, 400]},
            {"kind": "wall", "start_px": [600, 400], "end_px": [0, 400]},
            {"kind": "wall", "start_px": [0, 400], "end_px": [0, 0]},
            {"kind": "door", "start_px": [0, 300], "end_px": [0, 210]},
            {"kind": "window", "start_px": [200, 0], "end_px": [320, 0]},
        ],
    )

    confirmed = confirm_floorplan_analysis(analysis)

    assert confirmed["ready_for_design"] is True
    assert confirmed["analysis"]["confirmation_status"] == "confirmed"
    assert "SECTION" in confirmed["dxf_text"]
    assert confirmed["floorplan"]["width_cm"] == 600.0
    assert confirmed["floorplan"]["depth_cm"] == 400.0
    assert len(confirmed["floorplan"]["door_segments"]) == 1
    assert len(confirmed["floorplan"]["window_segments"]) == 1
    assert confirmed["requirements"]["rooms"][0]["room_type"] == "kitchen"


def test_builder_plan_630_cody_geometry_keeps_room_semantics_review_separate() -> None:
    image_path = Path(__file__).resolve().parents[1] / "testdata" / "png" / "builder_plan_630.png"
    analysis = analyze_floorplan_image(
        image_path.read_bytes(),
        filename=image_path.name,
        ocr_observations=[
            {"text": "630", "bbox": [325, 0, 371, 28], "confidence": 0.99},
            {"text": "臥室", "bbox": [210, 175, 270, 205], "confidence": 0.95},
            {"text": "主臥室", "bbox": [430, 187, 500, 215], "confidence": 0.95},
            {"text": "臥室", "bbox": [210, 350, 270, 390], "confidence": 0.95},
            {"text": "浴廁", "bbox": [425, 325, 475, 355], "confidence": 0.95},
            {"text": "浴廁", "bbox": [425, 445, 475, 475], "confidence": 0.95},
            {"text": "廚房", "bbox": [185, 490, 245, 520], "confidence": 0.95},
            {"text": "餐廳", "bbox": [185, 635, 245, 670], "confidence": 0.95},
            {"text": "客廳", "bbox": [455, 635, 520, 670], "confidence": 0.95},
        ],
    )

    assert analysis["scale"] == {
        "distance_m": 6.3,
        "pixel_distance": 414.0,
        "m_per_px": 0.015217,
        "source": "dimension_ocr",
        "confidence": 0.99,
    }
    room_types = [room["type"] for room in analysis["rooms"]]
    assert room_types.count("bedroom") == 3
    assert room_types.count("bathroom") == 2
    assert {"kitchen", "dining_room", "living_room"}.issubset(room_types)
    assert analysis["walls"]
    assert analysis["recognition_engine"] == "cody"
    assert analysis["requires_confirmation"] is True
    assert "targeted_room_review_required" in analysis["issues"]


def test_builder_plan_630_is_recognized_end_to_end_without_injected_annotations() -> None:
    image_path = Path(__file__).resolve().parents[1] / "testdata" / "png" / "builder_plan_630.png"

    analysis = analyze_floorplan_image(image_path.read_bytes(), filename=image_path.name)

    assert analysis["recognition_mode"] == "cody_vision"
    assert analysis["recognition_engine"] == "cody"
    assert analysis["scale"]["distance_m"] == 6.3
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
    assert all(0.7 <= door["width_m"] <= 1.2 for door in analysis["doors"])
    assert any(
        wall["bbox_px"][1] >= 700
        and wall["bbox_px"][2] - wall["bbox_px"][0] >= 500
        for wall in analysis["walls"]
    ), "Cody must preserve the long exterior wall along the bottom of the 630 plan"
    assert all(door["host_wall_id"].startswith("wall-") for door in analysis["doors"])
    assert all(door["opening_direction"] == "manual_review" for door in analysis["doors"])
    assert all(door["room_ids"] for door in analysis["doors"])
    assert all(window["host_wall_id"].startswith("wall-") for window in analysis["windows"])
    assert analysis["spatial_report"]["review_items"] == []
    assert analysis["requires_confirmation"] is False

    confirmed = confirm_floorplan_analysis(analysis)
    assert confirmed["ready_for_design"] is True
    assert len(confirmed["floorplan"]["room_regions"]) == 9
    master = next(room for room in confirmed["floorplan"]["room_regions"] if room["label"] == "主臥室")
    assert master["inner_dimensions_m"]["width"] > 0
    assert master["net_area_m2"] > 0
