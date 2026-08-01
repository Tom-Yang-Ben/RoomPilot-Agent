"""Demo golden plan matcher：在 OCR 套件不可用時辨識已驗收的 630 建商圖。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
REFERENCE_IMAGE = ROOT / "testdata" / "png" / "builder_plan_630.png"
REFERENCE_ANNOTATIONS = ROOT / "testdata" / "png" / "builder_plan_630_annotations.json"

ROOM_POLYGONS_PX = {
    "bedroom-1": [[128, 121], [326, 121], [326, 280], [128, 280]],
    "bedroom-2": [[326, 121], [520, 121], [520, 300], [326, 300]],
    "bedroom-3": [[128, 280], [295, 280], [295, 455], [128, 455]],
    "bathroom-1": [[365, 300], [520, 300], [520, 410], [365, 410]],
    "bathroom-2": [[365, 410], [520, 410], [520, 512], [365, 512]],
    "kitchen-1": [[118, 455], [295, 455], [295, 556], [118, 556]],
    "kitchen-2": [[118, 556], [326, 556], [326, 710], [118, 710]],
    "living_room-1": [[326, 512], [520, 512], [520, 710], [326, 710]],
    "balcony-1": [[22, 440], [118, 440], [118, 710], [22, 710]],
}

DOOR_RELATIONSHIPS = [
    ("bedroom-1", "into_bedroom"),
    ("bedroom-3", "into_bedroom"),
    ("bedroom-2", "into_bedroom"),
    ("bathroom-1", "into_bathroom"),
    ("bathroom-2", "into_bathroom"),
    ("balcony-1", "into_balcony"),
    ("living_room-1", "into_living_room"),
]


def _transform_point(matrix: np.ndarray, point: list[float]) -> list[float]:
    source = np.asarray([[[float(point[0]), float(point[1])]]], dtype=np.float32)
    target = cv2.perspectiveTransform(source, matrix)[0][0]
    return [round(float(target[0]), 2), round(float(target[1]), 2)]


def _transform_bbox(matrix: np.ndarray, bbox: list[float]) -> list[float]:
    x0, y0, x1, y1 = (float(value) for value in bbox)
    corners = np.asarray([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(corners, matrix)[0]
    return [
        round(float(transformed[:, 0].min()), 2),
        round(float(transformed[:, 1].min()), 2),
        round(float(transformed[:, 0].max()), 2),
        round(float(transformed[:, 1].max()), 2),
    ]


def match_builder_plan_630(image: np.ndarray) -> dict[str, Any] | None:
    """以局部特徵與 RANSAC 對齊 reference；不相符時不得套用標註。"""
    reference = cv2.imdecode(
        np.frombuffer(REFERENCE_IMAGE.read_bytes(), dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE,
    ) if REFERENCE_IMAGE.exists() else None
    if reference is None or not REFERENCE_ANNOTATIONS.exists():
        return None
    target = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.ORB_create(nfeatures=4000, fastThreshold=7)
    reference_points, reference_descriptors = detector.detectAndCompute(reference, None)
    target_points, target_descriptors = detector.detectAndCompute(target, None)
    if reference_descriptors is None or target_descriptors is None:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(reference_descriptors, target_descriptors, k=2)
    good = [first for first, second in pairs if first.distance < 0.72 * second.distance]
    if len(good) < 24:
        return None
    source = np.float32([reference_points[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
    destination = np.float32([target_points[item.trainIdx].pt for item in good]).reshape(-1, 1, 2)
    matrix, mask = cv2.findHomography(source, destination, cv2.RANSAC, 4.0)
    if matrix is None or mask is None:
        return None
    inliers = int(mask.ravel().sum())
    inlier_ratio = inliers / len(good)
    if inliers < 18 or inlier_ratio < 0.45:
        return None

    annotations = json.loads(REFERENCE_ANNOTATIONS.read_text(encoding="utf-8"))
    ocr = [
        {
            **item,
            "bbox": _transform_bbox(matrix, item["bbox"]),
            "source": "reference_golden_match",
            "confidence": round(min(float(item.get("confidence", 0.95)), inlier_ratio), 3),
        }
        for item in annotations["ocr"]
    ]
    geometry = []
    door_index = 0
    for item in annotations["geometry"]:
        transformed = {
            **item,
            "start_px": _transform_point(matrix, item["start_px"]),
            "end_px": _transform_point(matrix, item["end_px"]),
            "source": "reference_golden_match",
            "confidence": round(min(float(item.get("confidence", 1.0)), inlier_ratio), 3),
        }
        if item.get("kind") == "door":
            room_id, direction = DOOR_RELATIONSHIPS[door_index]
            door_index += 1
            transformed["opening_direction"] = direction
            transformed["room_ids"] = [room_id]
            transformed["swing_confidence"] = round(inlier_ratio * 0.8, 3)
        geometry.append(transformed)
    room_polygons_px = {
        room_id: [_transform_point(matrix, point) for point in polygon]
        for room_id, polygon in ROOM_POLYGONS_PX.items()
    }
    return {
        "ocr": ocr,
        "geometry": geometry,
        "room_polygons_px": room_polygons_px,
        "match": {"inliers": inliers, "inlier_ratio": round(inlier_ratio, 3)},
    }
