from __future__ import annotations

import math
from itertools import permutations

import cv2
import numpy as np
from dataclasses import replace
from pathlib import Path
import pytest

from backend.floorplan import floorplan2dxf as cody
from backend.floorplan.vision import (
    analyze_floorplan_image,
    confirm_floorplan_analysis,
    infer_room_requirements,
)
from backend.floorplan.vision.image import decode_image, profile_floorplan_image
from backend.floorplan.vision.units import canonicalize_analysis_cm
from backend.floorplan.cody_adapter import _carve_band_openings, _clean_door_items


def test_cody_cli_loads_floorplan_from_unicode_path(tmp_path: Path) -> None:
    image_path = tmp_path / "中文平面圖.png"
    image_path.write_bytes(_synthetic_floorplan())
    config_path = Path(cody.__file__).with_name("config.ini")
    cfg = replace(cody.load_config(str(config_path)), input=str(image_path))

    gray, bgr = cody.load_gray(cfg)

    assert gray.shape == (400, 500)
    assert bgr.shape == (400, 500, 3)


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


def test_image_profile_detects_colored_floorplan_line_art() -> None:
    image = np.full((160, 220, 3), 255, dtype=np.uint8)
    cv2.line(image, (20, 30), (200, 30), (255, 0, 0), 3)
    cv2.line(image, (20, 80), (200, 80), (0, 0, 255), 3)
    cv2.rectangle(image, (40, 105), (180, 140), (0, 160, 0), 2)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        calibration_hint={"distance_cm": 220, "start_px": [0, 0], "end_px": [220, 0]},
        geometry_observations=[
            {"kind": "wall", "start_px": [20, 30], "end_px": [200, 30]},
            {"kind": "wall", "start_px": [20, 80], "end_px": [200, 80]},
        ],
    )

    assert analysis["image_profile"]["kind"] == "color_line_art"
    assert analysis["image_profile"]["threshold_route"] == "color_mask_then_otsu"
    assert analysis["image_profile"]["has_color_signal"] is True


def test_image_profile_keeps_black_line_art_on_otsu_route() -> None:
    profile = profile_floorplan_image(decode_image(_synthetic_floorplan()))

    assert profile["kind"] == "grayscale_line_art"
    assert profile["threshold_route"] == "otsu"
    assert profile["has_color_signal"] is False


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

    assert analysis["scale"]["distance_cm"] == 630.0
    assert analysis["scale"]["pixel_distance"] == 415
    assert analysis["scale"]["cm_per_px"] == 1.5181
    assert analysis["scale"]["source"] == "dimension_ocr"
    assert analysis["coordinate_system"] == {
        "unit": "centimeter",
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

    corrected_scale = {**analysis["scale"], "distance_cm": 630, "cm_per_px": 1.5181}
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
            "end": {"x": 600.0, "y": 0.0},
            "confidence": 1.0,
            "source": "confirmed_geometry",
        }
    ]
    assert analysis["doors"][0]["width_cm"] == 90.0
    assert analysis["windows"][0]["width_cm"] == 120.0
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


def test_analyze_floorplan_image_reports_cody_room_labeler_status(monkeypatch) -> None:
    def fake_apply(_image, rooms, *, plan_bbox_px, m_per_px):
        assert plan_bbox_px
        assert m_per_px > 0
        assert rooms
        rooms[0]["cody_room_classifier"] = {"label": "living", "confidence": 0.9}
        return {
            "available": True,
            "asset_ready": True,
            "runtime_enabled": True,
            "runtime_ready": True,
            "reason": "cody_dinov2_ready",
            "applied": True,
            "labelled_room_count": 1,
        }

    monkeypatch.setattr(
        "backend.floorplan.vision.analysis.apply_cody_room_labels",
        fake_apply,
    )

    analysis = analyze_floorplan_image(
        _synthetic_floorplan(),
        calibration_hint={"distance_cm": 500, "start_px": [0, 0], "end_px": [500, 0]},
    )

    assert analysis["cody_room_labeler"]["reason"] == "cody_dinov2_ready"
    assert analysis["cody_room_labeler"]["applied"] is True
    assert any("cody_room_classifier" in room for room in analysis["rooms"])


def test_cody_geometry_can_be_confirmed_without_roompilot_fallback_corrections() -> None:
    analysis = analyze_floorplan_image(
        _synthetic_floorplan(),
        calibration_hint={"distance_cm": 500, "start_px": [0, 0], "end_px": [500, 0]},
    )

    confirmed = confirm_floorplan_analysis(analysis)

    assert confirmed["ready_for_design"] is True
    assert {item["source"] for item in confirmed["analysis"]["walls"]} == {"cody_vision"}


def test_analyze_floorplan_image_normalizes_room_labels_to_centimeter_coordinates() -> None:
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
    assert analysis["rooms"][0]["centroid_cm"] == {"x": 90.0, "y": 135.0}


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
    assert room["inner_dimensions_cm"] == {"width": 400.0, "depth": 300.0}
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
    assert confirmed["floorplan"]["coordinate_unit"] == "cm"
    assert len(confirmed["floorplan"]["door_segments"]) == 1
    assert len(confirmed["floorplan"]["window_segments"]) == 1
    bbox = confirmed["floorplan"]["bbox"]
    assert bbox["maxx"] - bbox["minx"] == pytest.approx(600.0)
    assert bbox["maxz"] - bbox["minz"] == pytest.approx(400.0)
    wall_points = [
        point
        for polygon in confirmed["floorplan"]["wall_polys"]
        for point in polygon["exterior"]
    ]
    assert max(abs(point[0]) for point in wall_points) > 250
    assert max(abs(point[1]) for point in wall_points) > 150
    assert confirmed["floorplan"]["doors"][0]["x1"] == pytest.approx(
        confirmed["floorplan"]["door_segments"][0]["start"]["x"]
    )
    assert confirmed["floorplan"]["doors"][0]["z1"] == pytest.approx(
        confirmed["floorplan"]["door_segments"][0]["start"]["z"]
    )
    assert confirmed["floorplan"]["windows"][0]["x2"] == pytest.approx(
        confirmed["floorplan"]["window_segments"][0]["end"]["x"]
    )
    assert confirmed["floorplan"]["wall_height_cm"] == pytest.approx(270.0)
    assert confirmed["floorplan"]["wall_thickness_cm"] == pytest.approx(18.0)
    assert "wall_height" not in confirmed["floorplan"]
    assert "wall_thickness" not in confirmed["floorplan"]
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
        "distance_cm": 630.0,
        "pixel_distance": 414.0,
        "cm_per_px": 1.5217,
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
    assert all(70 <= door["width_cm"] <= 120 for door in analysis["doors"])
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
    assert master["inner_dimensions_cm"]["width"] > 0
    assert master["net_area_m2"] > 0


def test_floor04_visible_swing_arcs_produce_door_candidates() -> None:
    image_path = Path(__file__).resolve().parents[1] / "testdata" / "png" / "floor04.png"

    analysis = analyze_floorplan_image(
        image_path.read_bytes(),
        filename=image_path.name,
        calibration_hint={
            "distance_cm": 950,
            "start_px": [120.43, 164.92],
            "end_px": [932.51, 164.92],
        },
    )

    assert len(analysis["rooms"]) == 7
    assert all(len(room["polygon_cm"]) >= 3 for room in analysis["rooms"])
    assert max(room["area_m2"] for room in analysis["rooms"]) < 40
    assert {room["type"] for room in analysis["rooms"]} == {
        "bedroom",
        "kitchen",
        "storage",
        "circulation",
        "bathroom",
        "living_room",
        "balcony",
    }
    assert all("待確認" in room["label"] for room in analysis["rooms"])
    expected_hinges_px = [
        (926, 188),  # 廚房外門
        (515, 518),  # 宿舍門
        (518, 563),  # 儲藏室門
        (656, 677),  # 浴室門
        (540, 1040),  # 客廳外門
    ]
    detected_hinges_px = [door.get("hinge_px") for door in analysis["doors"]]

    assert len(analysis["doors"]) == len(expected_hinges_px)
    assert all(hinge is not None for hinge in detected_hinges_px)
    assert any(
        all(math.dist(expected, detected) <= 15 for expected, detected in zip(expected_hinges_px, ordering))
        for ordering in permutations(detected_hinges_px)
    ), "五個門候選必須一對一落在可見門扇弧線的鉸鏈位置，且不可多出中央假門"
    assert all(65 <= door["width_cm"] <= 135 for door in analysis["doors"])
    assert all(door["opening_direction"] == "manual_review" for door in analysis["doors"])
    assert all(door["source"] == "cody_vision" for door in analysis["doors"])
    assert all(door["swing_confidence"] >= 0.85 for door in analysis["doors"])
    assert all("swing_end" in door for door in analysis["doors"])
    assert all(
        math.isclose(
            math.dist(
                (door["start"]["x"], door["start"]["y"]),
                (door["swing_end"]["x"], door["swing_end"]["y"]),
            ),
            door["width_cm"],
            abs_tol=2,
        )
        for door in analysis["doors"]
    )
    assert all(
        abs(
            (door["end"]["x"] - door["start"]["x"])
            * (door["swing_end"]["x"] - door["start"]["x"])
            + (door["end"]["y"] - door["start"]["y"])
            * (door["swing_end"]["y"] - door["start"]["y"])
        )
        <= 200
        for door in analysis["doors"]
    ), "門扇與弧線終點必須以鉸鏈為中心形成 90 度"


def test_floor04_swing_detector_supplements_a_partial_legacy_result(monkeypatch) -> None:
    image_path = Path(__file__).resolve().parents[1] / "testdata" / "png" / "floor04.png"
    monkeypatch.setattr(
        cody,
        "detect_doors",
        lambda _thin, _thickness, _arc_pct: [(535.0, 1038.0, 110.0, 1.0)],
    )

    analysis = analyze_floorplan_image(
        image_path.read_bytes(),
        filename=image_path.name,
        calibration_hint={
            "distance_cm": 950,
            "start_px": [120.43, 164.92],
            "end_px": [932.51, 164.92],
        },
    )

    assert len(analysis["doors"]) == 5
    assert all("swing_end" in door for door in analysis["doors"])


def test_cody_door_cleanup_rejects_low_confidence_wide_and_duplicate_candidates() -> None:
    doors = _clean_door_items([
        {
            "start": {"x": 0, "y": 0},
            "end": {"x": 1.86, "y": 0},
            "width_m": 1.86,
            "confidence": 1,
            "source": "cody_vision",
        },
        {
            "start": {"x": 2.0, "y": 0},
            "end": {"x": 2.9, "y": 0},
            "width_m": 0.9,
            "confidence": 0.59,
            "source": "cody_vision",
        },
        {
            "start": {"x": 0, "y": 0.4},
            "end": {"x": 0.9, "y": 0.4},
            "width_m": 0.9,
            "confidence": 0.91,
            "source": "cody_vision",
        },
        {
            "start": {"x": 0.1, "y": 0.45},
            "end": {"x": 1.02, "y": 0.45},
            "width_m": 0.92,
            "confidence": 0.96,
            "swing_end": {"x": 0.1, "y": 1.35},
            "source": "cody_vision",
        },
    ])

    assert len(doors) == 1
    assert doors[0]["confidence"] == 0.96
    assert doors[0]["width_m"] == 0.92


def test_django_band_carve_cuts_embedded_window_lines_out_of_wall_band() -> None:
    wall = np.zeros((80, 220), dtype=np.uint8)
    ink = np.zeros_like(wall)
    cv2.rectangle(wall, (20, 34), (200, 46), 255, -1)
    cv2.rectangle(ink, (20, 34), (80, 46), 255, -1)
    cv2.rectangle(ink, (140, 34), (200, 46), 255, -1)
    cv2.line(ink, (82, 37), (138, 37), 255, 1)
    cv2.line(ink, (82, 43), (138, 43), 255, 1)

    carved, log = _carve_band_openings(wall, ink, 12)

    assert log
    assert log[0]["source"] == "django_band_carve"
    assert log[0]["axis"] == "h"
    assert 45 <= log[0]["width_px"] <= 70
    assert carved[40, 100] == 0
    assert carved[40, 50] == 255
    assert carved[40, 170] == 255


def test_django_band_carve_keeps_plain_solid_wall_intact() -> None:
    wall = np.zeros((80, 220), dtype=np.uint8)
    cv2.rectangle(wall, (20, 34), (200, 46), 255, -1)

    carved, log = _carve_band_openings(wall, wall, 12)

    assert log == []
    assert np.array_equal(carved, wall)


def test_legacy_meter_analysis_is_migrated_to_centimeters_only_once() -> None:
    legacy = {
        "coordinate_system": {"unit": "metre"},
        "scale": {"distance_m": 6.3, "m_per_px": 0.01},
        "walls": [{"start": {"x": 0, "y": 0}, "end": {"x": 6.3, "y": 0}}],
        "rooms": [{
            "id": "room-1",
            "centroid_m": {"x": 3.15, "y": 2},
            "polygon_m": [
                {"x": 0, "y": 0},
                {"x": 6.3, "y": 0},
                {"x": 6.3, "y": 4},
                {"x": 0, "y": 4},
            ],
        }],
    }

    first = canonicalize_analysis_cm(legacy)
    second = canonicalize_analysis_cm(first)

    assert first == second
    assert second["scale"] == {"distance_cm": 630.0, "cm_per_px": 1.0}
    assert second["walls"][0]["end"] == {"x": 630.0, "y": 0.0}
    assert second["rooms"][0]["centroid_cm"] == {"x": 315.0, "y": 200.0}
