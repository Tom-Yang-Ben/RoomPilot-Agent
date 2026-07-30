from __future__ import annotations

import numpy as np

from backend.floorplan.vision.cody_room_labeler import (
    ENABLE_ENV_VAR,
    apply_cody_room_labels,
    cody_room_labeler_status,
)


class FakeClassifier:
    HEAD_PATH = __file__

    @staticmethod
    def classify(_image_bgr, _labels, rooms):
        probabilities = {
            "room-1": {"kitchen": 0.91, "living": 0.05},
            "room-2": {"living": 0.88, "bed": 0.04},
        }
        return [probabilities[room["room_id"]] for room in rooms]


class FakeAssetOnlyClassifier:
    HEAD_PATH = __file__


class FakeMissingAssetClassifier:
    HEAD_PATH = __file__ + ".missing"


def _rooms():
    return [
        {
            "id": "room-1",
            "type": "default",
            "label": "room 1",
            "confidence": 0.82,
            "source": "cody_wall_enclosure",
            "polygon_m": [
                {"x": 0.0, "y": 0.0},
                {"x": 2.0, "y": 0.0},
                {"x": 2.0, "y": 2.0},
                {"x": 0.0, "y": 2.0},
            ],
        },
        {
            "id": "room-2",
            "type": "default",
            "label": "room 2",
            "confidence": 0.82,
            "source": "cody_wall_enclosure",
            "polygon_m": [
                {"x": 2.0, "y": 0.0},
                {"x": 4.0, "y": 0.0},
                {"x": 4.0, "y": 2.0},
                {"x": 2.0, "y": 2.0},
            ],
        },
    ]


def test_cody_room_labeler_applies_dinov2_labels_to_inferred_rooms() -> None:
    rooms = _rooms()
    status = apply_cody_room_labels(
        np.full((240, 440, 3), 255, dtype=np.uint8),
        rooms,
        plan_bbox_px=[20.0, 20.0, 420.0, 220.0],
        m_per_px=0.01,
        classifier=FakeClassifier,
    )

    assert status["applied"] is True
    assert status["labelled_room_count"] == 2
    assert rooms[0]["type"] == "kitchen"
    assert rooms[0]["source"] == "cody_dinov2_room_classifier"
    assert rooms[0]["cody_room_classifier"]["label"] == "kitchen"
    assert rooms[1]["type"] == "living_room"


def test_cody_room_labeler_status_separates_asset_from_runtime(monkeypatch) -> None:
    monkeypatch.delenv(ENABLE_ENV_VAR, raising=False)

    status = cody_room_labeler_status(classifier=FakeAssetOnlyClassifier)

    assert status["asset_ready"] is True
    assert status["runtime_ready"] is True
    assert status["available"] is True

    missing = cody_room_labeler_status(classifier=FakeMissingAssetClassifier)

    assert missing["asset_ready"] is False
    assert missing["available"] is False
    assert missing["reason"] == "missing_cody_room_head"


def test_cody_room_labeler_preserves_user_or_ocr_room_labels() -> None:
    rooms = _rooms()
    rooms[0]["type"] = "bathroom"
    rooms[0]["label"] = "BATHROOM"
    rooms[0]["source"] = "ocr_room_label"

    status = apply_cody_room_labels(
        np.full((240, 440, 3), 255, dtype=np.uint8),
        rooms,
        plan_bbox_px=[20.0, 20.0, 420.0, 220.0],
        m_per_px=0.01,
        classifier=FakeClassifier,
    )

    assert status["applied"] is True
    assert status["labelled_room_count"] == 1
    assert rooms[0]["type"] == "bathroom"
    assert rooms[0]["source"] == "ocr_room_label"
    assert rooms[0]["cody_room_classifier"]["label"] == "kitchen"
    assert rooms[1]["type"] == "living_room"
