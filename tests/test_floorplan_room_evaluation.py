from __future__ import annotations

import numpy as np
import pytest

from backend.floorplan.vision.evaluation import (
    build_room_confusion,
    match_room_masks,
    normalize_room_label,
    summarize_room_recognition,
)
from backend.floorplan.vision import analyze_floorplan_image


def _mask(
    height: int,
    width: int,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask


def test_room_mask_matching_uses_greedy_one_to_one_iou():
    gt = [_mask(30, 30, 0, 10, 0, 10), _mask(30, 30, 10, 20, 0, 10)]
    predicted = [
        _mask(30, 30, 0, 11, 0, 10),
        _mask(30, 30, 11, 20, 0, 10),
    ]

    matches = match_room_masks(gt, predicted)

    assert sorted((gt_index, pred_index) for gt_index, pred_index, _ in matches) == [
        (0, 0),
        (1, 1),
    ]
    assert matches[0][2] == pytest.approx(10 / 11)


def test_room_label_confusion_normalizes_cody_labels():
    assert normalize_room_label("balcony") == "outdoor"
    assert normalize_room_label("room") == "space"
    assert normalize_room_label(None) == "space"

    confusion = build_room_confusion(
        [("bed", "bed"), ("bed", "bath"), ("balcony", "room")]
    )

    assert confusion["bed"]["bed"] == 1
    assert confusion["bed"]["bath"] == 1
    assert confusion["outdoor"]["space"] == 1


def test_room_recognition_summary_reports_cody_v5_metrics_shape():
    gt_rooms = [
        {"label": "bed", "mask": _mask(20, 20, 0, 10, 0, 10)},
        {"label": "balcony", "mask": _mask(20, 20, 10, 20, 0, 10)},
    ]
    predicted_rooms = [
        {"label": "bed", "mask": _mask(20, 20, 0, 10, 0, 10)},
        {"label": "room", "mask": _mask(20, 20, 10, 20, 0, 10)},
    ]

    summary = summarize_room_recognition(gt_rooms, predicted_rooms)

    assert summary["gt_rooms"] == 2
    assert summary["predicted_rooms"] == 2
    assert summary["matched"] == 2
    assert summary["hit_rate"] == 1.0
    assert summary["mean_iou"] == 1.0
    assert summary["per_class"]["bed"] == {"gt": 1, "precision": 1.0, "recall": 1.0}
    assert summary["per_class"]["outdoor"]["recall"] == 0.0
    assert summary["confusion"]["outdoor"]["space"] == 1


def test_floorplan_analysis_can_attach_room_evaluation_debug_report():
    image = np.full((120, 160, 3), 255, dtype=np.uint8)
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    assert ok

    reference_rooms = [
        {
            "room_type": "living_room",
            "polygon_cm": [
                {"x": 0, "y": 0},
                {"x": 160, "y": 0},
                {"x": 160, "y": 120},
                {"x": 0, "y": 120},
            ],
        }
    ]
    analysis = analyze_floorplan_image(
        encoded.tobytes(),
        calibration_hint={"distance_cm": 160, "start_px": [0, 0], "end_px": [160, 0]},
        ocr_observations=[
            {"text": "\u5ba2\u5ef3", "bbox": [65, 50, 95, 70], "confidence": 0.99}
        ],
        geometry_observations=[
            {"kind": "wall", "start_px": [0, 0], "end_px": [160, 0], "confidence": 1},
            {"kind": "wall", "start_px": [160, 0], "end_px": [160, 120], "confidence": 1},
            {"kind": "wall", "start_px": [160, 120], "end_px": [0, 120], "confidence": 1},
            {"kind": "wall", "start_px": [0, 120], "end_px": [0, 0], "confidence": 1},
        ],
        evaluation_reference_rooms=reference_rooms,
    )

    assert analysis["room_evaluation"]["available"] is True
    assert analysis["room_evaluation"]["basis"] == "room_polygon_iou"
    assert analysis["room_evaluation"]["matched"] == 1
    assert analysis["room_evaluation"]["per_class"]["living"]["recall"] == 1.0
