import numpy as np

from backend.floorplan.vision.room_icons import (
    apply_icon_room_labels,
    detect_room_icons,
    load_icon_templates,
)
from backend.floorplan.vision.spatial_report import build_spatial_report


def _room_walls() -> list[dict]:
    return [
        {
            "start": {"x": 0, "y": 0},
            "end": {"x": 6, "y": 0},
            "thickness_m": 0.12,
        },
        {
            "start": {"x": 6, "y": 0},
            "end": {"x": 6, "y": 4},
            "thickness_m": 0.12,
        },
        {
            "start": {"x": 6, "y": 4},
            "end": {"x": 0, "y": 4},
            "thickness_m": 0.12,
        },
        {
            "start": {"x": 0, "y": 4},
            "end": {"x": 0, "y": 0},
            "thickness_m": 0.12,
        },
    ]


def test_portable_profile_does_not_bundle_unverified_icon_templates() -> None:
    load_icon_templates.cache_clear()
    templates = load_icon_templates()

    assert templates == {}


def test_missing_icon_templates_disable_detection_without_fabricating_labels() -> None:
    canvas = np.full((600, 800), 255, dtype=np.uint8)

    detections = detect_room_icons(
        canvas,
        walls=_room_walls(),
        plan_bbox_px=[100, 100, 700, 500],
        m_per_px=0.01,
    )
    assert detections == []


def test_icon_inference_never_overwrites_ocr_room_name() -> None:
    rooms = [
        {
            "id": "room-1",
            "type": "workspace",
            "label": "書房",
            "source": "ocr_room_label",
            "area_m2": 12.0,
            "polygon_m": [
                {"x": 0, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 3},
                {"x": 0, "y": 3},
            ],
        }
    ]
    detections = [
        {
            "class": "bed",
            "label": "臥室",
            "room_type": "bedroom",
            "score": 0.99,
            "bbox_px": [150.0, 150.0, 160.0, 220.0],
            "centroid_px": [230.0, 260.0],
        }
    ]

    apply_icon_room_labels(
        rooms,
        detections,
        plan_bbox_px=[100, 100, 500, 400],
        m_per_px=0.01,
    )

    assert rooms[0]["type"] == "workspace"
    assert rooms[0]["label"] == "書房"
    assert rooms[0]["source"] == "ocr_room_label"
    assert rooms[0]["icon_evidence"][0]["class"] == "bed"


def test_competing_icon_types_require_room_confirmation() -> None:
    rooms = [
        {
            "id": "room-1",
            "type": "default",
            "label": "空間 1",
            "area_m2": 12.0,
            "polygon_m": [
                {"x": 0, "y": 0},
                {"x": 4, "y": 0},
                {"x": 4, "y": 3},
                {"x": 0, "y": 3},
            ],
        }
    ]
    detections = [
        {
            "class": "bed",
            "label": "臥室",
            "room_type": "bedroom",
            "score": 0.95,
            "bbox_px": [150.0, 150.0, 80.0, 100.0],
            "centroid_px": [190.0, 200.0],
        },
        {
            "class": "sofa",
            "label": "客廳",
            "room_type": "living_room",
            "score": 0.94,
            "bbox_px": [250.0, 150.0, 100.0, 80.0],
            "centroid_px": [300.0, 190.0],
        },
    ]

    apply_icon_room_labels(
        rooms,
        detections,
        plan_bbox_px=[100, 100, 500, 400],
        m_per_px=0.01,
    )

    assert rooms[0]["room_review"] is True
    assert rooms[0]["type"] == "default"
    assert "room_icon_function_conflict" in rooms[0]["room_review_reasons"]
    assert rooms[0]["label"].endswith("（待確認）")

    report = build_spatial_report(
        {
            "coordinate_system": {"unit": "metre"},
            "walls": [],
            "rooms": rooms,
        }
    )
    assert any(
        item["reason"] == "room_label_icon_evidence_conflict"
        for item in report["review_items"]
    )
    assert (
        report["rooms"][0]["evidence"][0]["kind"]
        == "furniture_icon_room_label"
    )


def test_single_icon_does_not_name_an_implausibly_large_room() -> None:
    rooms = [
        {
            "id": "room-1",
            "type": "default",
            "label": "空間 1",
            "area_m2": 265.0,
            "polygon_m": [
                {"x": 0, "y": 0},
                {"x": 18, "y": 0},
                {"x": 18, "y": 15},
                {"x": 0, "y": 15},
            ],
        }
    ]
    detections = [
        {
            "class": "bed",
            "label": "臥室",
            "room_type": "bedroom",
            "score": 0.96,
            "bbox_px": [240.0, 200.0, 120.0, 150.0],
            "centroid_px": [300.0, 275.0],
        },
    ]

    apply_icon_room_labels(
        rooms,
        detections,
        plan_bbox_px=[100, 100, 2000, 1700],
        m_per_px=0.01,
    )

    assert rooms[0]["type"] == "default"
    assert rooms[0]["label"] == "空間 1（待確認）"
    assert rooms[0]["room_review"] is True
    assert "room_icon_area_implausible" in rooms[0]["room_review_reasons"]
    assert rooms[0]["icon_suggested_room_types"][0]["room_type"] == "bedroom"
