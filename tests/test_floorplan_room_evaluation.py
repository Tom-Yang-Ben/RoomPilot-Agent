from __future__ import annotations

import numpy as np
import pytest

from backend.floorplan.vision.evaluation import (
    build_room_confusion,
    match_room_masks,
    normalize_room_label,
    summarize_room_recognition,
)


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
