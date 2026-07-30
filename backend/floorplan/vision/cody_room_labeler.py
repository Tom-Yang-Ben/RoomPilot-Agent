"""Adapter for Cody's DINOv2 room naming layer.

The floorplan API already owns wall/door/window geometry through
``cody_adapter``. This module keeps Cody's newer room classifier behind the
same floorplan boundary: it may refine inferred room labels, but it never
changes confirmed geometry or proposal data.
"""

from __future__ import annotations

from collections.abc import Mapping
import importlib
import importlib.util
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np


MIN_ROOM_LABEL_CONFIDENCE = 0.55
ENABLE_ENV_VAR = "ROOMPILOT_CODY_DINOV2"
ROOM_TYPE_BY_CODY_LABEL = {
    "bath": "bathroom",
    "bed": "bedroom",
    "entry": "circulation",
    "garage": "garage",
    "kitchen": "kitchen",
    "living": "living_room",
    "office": "workspace",
    "outdoor": "balcony",
    "stair": "stair",
    "storage": "storage",
}
DISPLAY_LABEL_BY_TYPE = {
    "balcony": "balcony",
    "bathroom": "bathroom",
    "bedroom": "bedroom",
    "circulation": "circulation",
    "garage": "garage",
    "kitchen": "kitchen",
    "living_room": "living room",
    "stair": "stair",
    "storage": "storage",
    "workspace": "workspace",
}


def _room_classifier_module() -> Any | None:
    try:
        return importlib.import_module("backend.floorplan.room_classifier")
    except Exception:
        return None


def cody_room_labeler_status(*, classifier: Any | None = None) -> dict[str, Any]:
    """Return local availability for Cody's DINOv2 room classifier."""
    module = classifier or _room_classifier_module()
    if module is None:
        return {
            "available": False,
            "reason": "missing_cody_room_classifier_module",
            "model_version": "cody_dinov2_room_classifier",
        }
    head_path = Path(getattr(module, "HEAD_PATH", ""))
    asset_ready = head_path.is_file()
    runtime_enabled = classifier is not None or os.environ.get(ENABLE_ENV_VAR) == "1"
    torch_ready = classifier is not None or importlib.util.find_spec("torch") is not None
    runtime_ready = runtime_enabled and torch_ready
    if not asset_ready:
        reason = "missing_cody_room_head"
    elif not runtime_enabled:
        reason = "cody_dinov2_runtime_not_enabled"
    elif not torch_ready:
        reason = "missing_torch_runtime"
    else:
        reason = "cody_dinov2_ready"
    return {
        "available": asset_ready and runtime_ready,
        "asset_ready": asset_ready,
        "runtime_enabled": runtime_enabled,
        "runtime_ready": runtime_ready,
        "reason": reason,
        "model_version": "cody_dinov2_room_classifier",
        "head_path": str(head_path),
        "optional_runtime": "torch_dinov2",
        "enable_env": ENABLE_ENV_VAR,
    }


def _room_point_to_pixel(
    point: Mapping[str, Any],
    *,
    plan_bbox_px: list[float],
    m_per_px: float,
) -> tuple[int, int]:
    bbox_left, _bbox_top, _bbox_right, bbox_bottom = plan_bbox_px
    x_px = bbox_left + float(point["x"]) / m_per_px
    y_px = bbox_bottom - float(point["y"]) / m_per_px
    return int(round(x_px)), int(round(y_px))


def _labels_for_rooms(
    rooms: list[Mapping[str, Any]],
    *,
    image_shape: tuple[int, int],
    plan_bbox_px: list[float],
    m_per_px: float,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    labels = np.zeros(image_shape, dtype=np.int32)
    classifier_rooms: list[dict[str, Any]] = []
    for index, room in enumerate(rooms, start=1):
        polygon = room.get("polygon_m")
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        points = [
            _room_point_to_pixel(point, plan_bbox_px=plan_bbox_px, m_per_px=m_per_px)
            for point in polygon
            if isinstance(point, Mapping) and "x" in point and "y" in point
        ]
        if len(points) < 3:
            continue
        cv2.fillPoly(labels, [np.asarray(points, dtype=np.int32)], index)
        classifier_rooms.append({"id": index, "room_id": room.get("id")})
    return labels, classifier_rooms


def _best_label(probs: Mapping[str, Any]) -> tuple[str, float] | None:
    scored = [
        (str(label), float(score))
        for label, score in probs.items()
        if str(label) in ROOM_TYPE_BY_CODY_LABEL
    ]
    if not scored:
        return None
    label, confidence = max(scored, key=lambda item: item[1])
    if confidence < MIN_ROOM_LABEL_CONFIDENCE:
        return None
    return label, confidence


def _room_is_user_labelled(room: Mapping[str, Any]) -> bool:
    source = str(room.get("source") or "")
    evidence = room.get("evidence") or []
    return source == "ocr_room_label" or any(
        isinstance(item, Mapping) and item.get("kind") == "ocr_room_label"
        for item in evidence
    )


def apply_cody_room_labels(
    image_bgr: np.ndarray,
    rooms: list[dict[str, Any]],
    *,
    plan_bbox_px: list[float] | None,
    m_per_px: float,
    classifier: Any | None = None,
) -> dict[str, Any]:
    """Refine unconfirmed inferred room labels with Cody's DINOv2 classifier.

    The classifier is optional. Missing torch, missing hub cache, or missing
    model assets simply returns a clear status and leaves rooms unchanged.
    """
    status = cody_room_labeler_status(classifier=classifier)
    if not status["available"] or not plan_bbox_px or m_per_px <= 0 or not rooms:
        return {**status, "applied": False, "labelled_room_count": 0}

    module = classifier or _room_classifier_module()
    if module is None:
        return {**status, "available": False, "applied": False, "labelled_room_count": 0}

    labels, classifier_rooms = _labels_for_rooms(
        rooms,
        image_shape=image_bgr.shape[:2],
        plan_bbox_px=plan_bbox_px,
        m_per_px=m_per_px,
    )
    if not classifier_rooms or not labels.any():
        return {**status, "applied": False, "labelled_room_count": 0}

    probabilities = module.classify(image_bgr, labels, classifier_rooms)
    if probabilities is None:
        return {
            **status,
            "available": False,
            "reason": "cody_dinov2_runtime_unavailable",
            "applied": False,
            "labelled_room_count": 0,
        }

    labelled_count = 0
    room_by_id = {room.get("id"): room for room in rooms}
    for classifier_room, room_probs in zip(classifier_rooms, probabilities):
        room = room_by_id.get(classifier_room["room_id"])
        if room is None:
            continue
        best = _best_label(room_probs)
        if best is None:
            continue
        cody_label, confidence = best
        room_type = ROOM_TYPE_BY_CODY_LABEL[cody_label]
        room.setdefault("cody_room_classifier", {})["probabilities"] = {
            str(label): round(float(score), 4)
            for label, score in sorted(room_probs.items())
        }
        room["cody_room_classifier"]["label"] = cody_label
        room["cody_room_classifier"]["confidence"] = round(confidence, 4)
        if _room_is_user_labelled(room):
            continue
        room["type"] = room_type
        room["label"] = DISPLAY_LABEL_BY_TYPE.get(room_type, room_type)
        room["source"] = "cody_dinov2_room_classifier"
        room["confidence"] = max(float(room.get("confidence", 0.0)), round(confidence, 3))
        evidence = list(room.get("evidence") or [])
        evidence.append(
            {
                "kind": "cody_dinov2_room_classifier",
                "label": cody_label,
                "confidence": round(confidence, 4),
            }
        )
        room["evidence"] = evidence
        labelled_count += 1

    return {
        **status,
        "applied": labelled_count > 0,
        "labelled_room_count": labelled_count,
    }
