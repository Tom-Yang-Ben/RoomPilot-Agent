"""Optional local reference-plan matcher.

The public repository does not ship a customer or vendor floor plan.  This
module is inactive unless both reference paths are configured explicitly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _configured_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


REFERENCE_IMAGE = _configured_path("ROOMPILOT_REFERENCE_FLOORPLAN")
REFERENCE_ANNOTATIONS = _configured_path("ROOMPILOT_REFERENCE_ANNOTATIONS")

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


def match_configured_reference(image: np.ndarray) -> dict[str, Any] | None:
    """Align an explicitly configured reference; return None when unavailable."""
    if REFERENCE_IMAGE is None or REFERENCE_ANNOTATIONS is None:
        return None
    reference = cv2.imdecode(
        np.frombuffer(REFERENCE_IMAGE.read_bytes(), dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE,
    ) if REFERENCE_IMAGE.is_file() else None
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
    door_relationships = annotations.get("door_relationships") or []
    door_index = 0
    for item in annotations["geometry"]:
        transformed = {
            **item,
            "start_px": _transform_point(matrix, item["start_px"]),
            "end_px": _transform_point(matrix, item["end_px"]),
            "source": "reference_golden_match",
            "confidence": round(min(float(item.get("confidence", 1.0)), inlier_ratio), 3),
        }
        if item.get("kind") == "door" and door_index < len(door_relationships):
            relationship = door_relationships[door_index]
            door_index += 1
            transformed["opening_direction"] = relationship.get("opening_direction")
            transformed["room_ids"] = list(relationship.get("room_ids") or [])
            transformed["swing_confidence"] = round(inlier_ratio * 0.8, 3)
        geometry.append(transformed)
    room_polygons_px = {
        room_id: [_transform_point(matrix, point) for point in polygon]
        for room_id, polygon in (annotations.get("room_polygons_px") or {}).items()
    }
    return {
        "ocr": ocr,
        "geometry": geometry,
        "room_polygons_px": room_polygons_px,
        "match": {"inliers": inliers, "inlier_ratio": round(inlier_ratio, 3)},
    }
