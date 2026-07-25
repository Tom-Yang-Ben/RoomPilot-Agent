"""Infer room names from furniture symbols drawn on a floor plan.

This is a compact Bella adapter for the rule set proven in Django's
``Final-Project_Version3/furniture_match.py``. It deliberately keeps only the
read-only template matcher and room voting seam. Model retraining, sample
harvesting, open-plan splitting, and filesystem writes remain outside the
production recognition path.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

import cv2
import numpy as np


TEMPLATE_DIR = Path(__file__).with_name("icon_templates")
NORMALIZED_SIZE = 48
MIN_CLASS_MARGIN = 0.025

ICON_RULES: dict[str, dict[str, Any]] = {
    "toilet": {
        "room_type": "bathroom",
        "label": "浴室",
        "weight": 0.98,
        "long_cm": (45, 110),
        "short_cm": 25,
        "threshold": 0.54,
    },
    "shower": {
        "room_type": "bathroom",
        "label": "浴室",
        "weight": 0.90,
        "long_cm": (70, 180),
        "short_cm": 55,
        "threshold": 0.56,
    },
    "stove": {
        "room_type": "kitchen",
        "label": "廚房",
        "weight": 0.98,
        "long_cm": (45, 130),
        "short_cm": 30,
        "threshold": 0.56,
    },
    "sofa": {
        "room_type": "living_room",
        "label": "客廳",
        "weight": 0.95,
        "long_cm": (110, 330),
        "short_cm": 45,
        "threshold": 0.56,
    },
    "bed": {
        "room_type": "bedroom",
        "label": "臥室",
        "weight": 0.98,
        "long_cm": (130, 320),
        "short_cm": 65,
        "threshold": 0.56,
    },
    "dining_set": {
        "room_type": "dining_room",
        "label": "餐廳",
        "weight": 0.90,
        "long_cm": (90, 360),
        "short_cm": 60,
        "threshold": 0.58,
    },
}

COMPATIBLE_ROOM_COMBINATIONS = {
    frozenset({"bathroom"}),
    frozenset({"living_room", "dining_room"}),
    frozenset({"dining_room", "kitchen"}),
    frozenset({"living_room", "dining_room", "kitchen"}),
}

MAX_SINGLE_ICON_ROOM_AREA_M2 = {
    "bathroom": 30.0,
    "bedroom": 80.0,
    "kitchen": 80.0,
}


def _generic_pending_label(room: Mapping[str, Any]) -> str:
    room_id = str(room.get("id") or "").strip()
    suffix = room_id.rsplit("-", 1)[-1] if room_id else ""
    if suffix.isdigit():
        return f"空間 {suffix}（待確認）"
    return "未命名空間（待確認）"


def _review_reasons(
    ranked: list[tuple[str, float]],
    *,
    room: Mapping[str, Any],
    confidence: float,
) -> list[str]:
    reasons: list[str] = []
    room_types = frozenset(room_type for room_type, _ in ranked)
    if len(room_types) > 1 and room_types not in COMPATIBLE_ROOM_COMBINATIONS:
        reasons.append("room_icon_function_conflict")
    if confidence < 0.90:
        reasons.append("room_icon_low_confidence")
    if ranked:
        room_type = ranked[0][0]
        max_area = MAX_SINGLE_ICON_ROOM_AREA_M2.get(room_type)
        try:
            area_m2 = float(room.get("area_m2") or 0)
        except (TypeError, ValueError):
            area_m2 = 0.0
        if max_area is not None and area_m2 > max_area:
            reasons.append("room_icon_area_implausible")
    return reasons


def _to_ink(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        rgb = image[:, :, :3].astype(np.float32)
        image = (rgb * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(
        image,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    return ink


def _tight_crop(ink: np.ndarray) -> np.ndarray | None:
    ys, xs = np.nonzero(ink)
    if xs.size < 20:
        return None
    return ink[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def _normalise(ink: np.ndarray) -> np.ndarray:
    resized = cv2.resize(
        ink,
        (NORMALIZED_SIZE, NORMALIZED_SIZE),
        interpolation=cv2.INTER_AREA,
    )
    _, binary = cv2.threshold(resized, 40, 255, cv2.THRESH_BINARY)
    return binary


def _orientations(template: np.ndarray) -> list[np.ndarray]:
    rotations = [
        template,
        cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(template, cv2.ROTATE_180),
        cv2.rotate(template, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    mirrored = cv2.flip(template, 1)
    rotations.extend(
        [
            mirrored,
            cv2.rotate(mirrored, cv2.ROTATE_90_CLOCKWISE),
            cv2.rotate(mirrored, cv2.ROTATE_180),
            cv2.rotate(mirrored, cv2.ROTATE_90_COUNTERCLOCKWISE),
        ]
    )
    unique: list[np.ndarray] = []
    signatures: set[bytes] = set()
    for candidate in rotations:
        normalised = _normalise(candidate)
        signature = bytes((normalised > 0).astype(np.uint8).ravel())
        if signature in signatures:
            continue
        signatures.add(signature)
        unique.append(normalised)
    return unique


@lru_cache(maxsize=1)
def load_icon_templates() -> dict[str, list[np.ndarray]]:
    """Load curated read-only icon templates shipped with Bella."""
    templates: dict[str, list[np.ndarray]] = {}
    for icon_class in ICON_RULES:
        class_dir = TEMPLATE_DIR / icon_class
        variants: list[np.ndarray] = []
        if not class_dir.is_dir():
            continue
        for path in sorted(class_dir.glob("*.png")):
            raw = cv2.imdecode(
                np.fromfile(str(path), dtype=np.uint8),
                cv2.IMREAD_UNCHANGED,
            )
            if raw is None:
                continue
            crop = _tight_crop(_to_ink(raw))
            if crop is not None:
                variants.extend(_orientations(crop))
        if variants:
            templates[icon_class] = variants
    return templates


def _chamfer_similarity(left: np.ndarray, right: np.ndarray) -> float:
    if not (left > 0).any() or not (right > 0).any():
        return 0.0
    left_distance = cv2.distanceTransform(
        (left == 0).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )
    right_distance = cv2.distanceTransform(
        (right == 0).astype(np.uint8),
        cv2.DIST_L2,
        3,
    )
    distance = max(
        float(left_distance[right > 0].mean()),
        float(right_distance[left > 0].mean()),
    ) / (NORMALIZED_SIZE * 0.5)
    return max(0.0, 1.0 - distance * 4.0)


def _coarse_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left_grid = cv2.resize(left, (12, 12), interpolation=cv2.INTER_AREA).astype(
        np.float32
    )
    right_grid = cv2.resize(right, (12, 12), interpolation=cv2.INTER_AREA).astype(
        np.float32
    )
    left_grid -= left_grid.mean()
    right_grid -= right_grid.mean()
    denominator = float(np.linalg.norm(left_grid) * np.linalg.norm(right_grid))
    if denominator <= 0:
        return 0.0
    return max(0.0, float((left_grid * right_grid).sum()) / denominator)


def _physical_classes(
    shape: tuple[int, int],
    *,
    cm_per_px: float,
) -> set[str]:
    long_cm = max(shape) * cm_per_px
    short_cm = min(shape) * cm_per_px
    return {
        icon_class
        for icon_class, rule in ICON_RULES.items()
        if rule["long_cm"][0] <= long_cm <= rule["long_cm"][1]
        and short_cm >= rule["short_cm"]
    }


def _classify_icon(
    crop: np.ndarray,
    *,
    cm_per_px: float,
) -> tuple[str | None, float]:
    allowed = _physical_classes(crop.shape, cm_per_px=cm_per_px)
    if not allowed:
        return None, 0.0
    normalised = _normalise(crop)
    aspect = crop.shape[1] / max(crop.shape[0], 1)
    class_scores: dict[str, float] = {}
    for icon_class in allowed:
        best_score = 0.0
        for template in load_icon_templates().get(icon_class, []):
            ys, xs = np.nonzero(template)
            template_aspect = (
                (xs.max() - xs.min() + 1) / max(ys.max() - ys.min() + 1, 1)
                if xs.size
                else 1.0
            )
            if not 0.45 <= aspect / template_aspect <= 2.2:
                continue
            score = 0.55 * _chamfer_similarity(
                normalised,
                template,
            ) + 0.45 * _coarse_similarity(normalised, template)
            best_score = max(best_score, score)
        if best_score:
            class_scores[icon_class] = best_score
    if not class_scores:
        return None, 0.0
    ranked = sorted(class_scores.items(), key=lambda item: -item[1])
    best_class, best_score = ranked[0]
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if (
        best_score < ICON_RULES[best_class]["threshold"]
        or best_score - runner_up_score < MIN_CLASS_MARGIN
    ):
        return None, best_score
    return best_class, min(best_score, 0.99)


def _wall_mask(
    shape: tuple[int, int],
    walls: Iterable[Mapping[str, Any]],
    *,
    plan_bbox_px: list[float],
    m_per_px: float,
) -> tuple[np.ndarray, float]:
    mask = np.zeros(shape, dtype=np.uint8)
    bbox_left, _, _, bbox_bottom = (float(value) for value in plan_bbox_px)
    thicknesses: list[float] = []

    def pixel(point: Mapping[str, Any]) -> tuple[int, int]:
        return (
            int(round(bbox_left + float(point.get("x") or 0) / m_per_px)),
            int(round(bbox_bottom - float(point.get("y") or 0) / m_per_px)),
        )

    for wall in walls:
        start = wall.get("start")
        end = wall.get("end")
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            continue
        thickness_px = max(
            3,
            int(round(float(wall.get("thickness_m") or 0.12) / m_per_px)),
        )
        thicknesses.append(float(thickness_px))
        cv2.line(mask, pixel(start), pixel(end), 255, thickness_px)
    wall_thickness = float(np.median(thicknesses)) if thicknesses else 6.0
    return mask, wall_thickness


def _mask_text(
    ink: np.ndarray,
    observations: Iterable[Mapping[str, Any]],
) -> None:
    for observation in observations:
        bbox = observation.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = (int(round(float(value))) for value in bbox)
        cv2.rectangle(
            ink,
            (max(0, x0 - 3), max(0, y0 - 3)),
            (min(ink.shape[1] - 1, x1 + 3), min(ink.shape[0] - 1, y1 + 3)),
            0,
            -1,
        )


def detect_room_icons(
    gray: np.ndarray,
    *,
    walls: Iterable[Mapping[str, Any]],
    plan_bbox_px: list[float] | None,
    m_per_px: float,
    text_observations: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Detect high-confidence furniture symbols without writing training data."""
    if not load_icon_templates() or not plan_bbox_px or m_per_px <= 0:
        return []
    ink = _to_ink(gray)
    _mask_text(ink, text_observations)
    wall_mask, wall_thickness = _wall_mask(
        gray.shape,
        walls,
        plan_bbox_px=plan_bbox_px,
        m_per_px=m_per_px,
    )
    wall_dilation = cv2.dilate(
        wall_mask,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
    )
    furniture = cv2.bitwise_and(ink, cv2.bitwise_not(wall_dilation))
    kernel_size = max(3, int(round(wall_thickness * 0.45))) | 1
    grouped = cv2.dilate(
        furniture,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (kernel_size, kernel_size),
        ),
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (grouped > 0).astype(np.uint8),
        8,
    )
    cm_per_px = m_per_px * 100.0
    detections: list[dict[str, Any]] = []
    for component_id in range(1, count):
        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        width = int(stats[component_id, cv2.CC_STAT_WIDTH])
        height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        if min(width, height) < 12:
            continue
        component = (
            (labels[y : y + height, x : x + width] == component_id)
            & (furniture[y : y + height, x : x + width] > 0)
        )
        crop = _tight_crop(
            np.where(component, np.uint8(255), np.uint8(0)),
        )
        if crop is None:
            continue
        icon_class, score = _classify_icon(crop, cm_per_px=cm_per_px)
        if icon_class is None:
            continue
        detections.append(
            {
                "class": icon_class,
                "label": ICON_RULES[icon_class]["label"],
                "room_type": ICON_RULES[icon_class]["room_type"],
                "score": round(score, 3),
                "bbox_px": [float(x), float(y), float(width), float(height)],
                "centroid_px": [
                    round(x + width / 2.0, 2),
                    round(y + height / 2.0, 2),
                ],
                "source": "django_icon_template",
            }
        )
    return sorted(detections, key=lambda item: -float(item["score"]))


def _point_in_polygon(
    point: tuple[float, float],
    polygon: list[Mapping[str, Any]],
) -> bool:
    contour = np.asarray(
        [[float(item["x"]), float(item["y"])] for item in polygon],
        dtype=np.float32,
    )
    return len(contour) >= 3 and cv2.pointPolygonTest(contour, point, False) >= 0


def apply_icon_room_labels(
    rooms: list[dict[str, Any]],
    detections: list[dict[str, Any]],
    *,
    plan_bbox_px: list[float] | None,
    m_per_px: float,
) -> None:
    """Apply icon votes only to unnamed rooms and keep conflicts reviewable."""
    if not plan_bbox_px or m_per_px <= 0:
        return
    bbox_left, _, _, bbox_bottom = (float(value) for value in plan_bbox_px)
    votes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for detection in detections:
        cx, cy = detection["centroid_px"]
        point_m = (
            (float(cx) - bbox_left) * m_per_px,
            (bbox_bottom - float(cy)) * m_per_px,
        )
        candidates = [
            room
            for room in rooms
            if room.get("polygon_m")
            and _point_in_polygon(point_m, room["polygon_m"])
        ]
        if not candidates:
            continue
        room = min(
            candidates,
            key=lambda item: float(item.get("area_m2") or float("inf")),
        )
        detection["room_id"] = room["id"]
        votes[str(room["id"])].append(detection)

    for room in rooms:
        room_votes = votes.get(str(room.get("id")), [])
        if not room_votes:
            continue
        room["icon_evidence"] = [
            {
                "class": item["class"],
                "score": item["score"],
                "bbox_px": item["bbox_px"],
            }
            for item in room_votes
        ]
        if room.get("type") not in {None, "", "default", "unknown"}:
            continue
        scores: dict[str, float] = defaultdict(float)
        labels: dict[str, str] = {}
        for item in room_votes:
            room_type = str(item["room_type"])
            scores[room_type] += (
                float(item["score"]) * float(ICON_RULES[item["class"]]["weight"])
            )
            labels[room_type] = str(item["label"])
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        room_type, score = ranked[0]
        competing = len(ranked) > 1 and ranked[1][1] >= score * 0.75
        confidence = min(0.96, score)
        reasons = _review_reasons(ranked, room=room, confidence=confidence)
        needs_review = competing or bool(reasons)
        if (
            "room_icon_function_conflict" in reasons
            or "room_icon_area_implausible" in reasons
        ):
            room["type"] = "default"
            room["label"] = _generic_pending_label(room)
        else:
            room["type"] = room_type
            room["label"] = (
                f"{labels[room_type]}（待確認）"
                if needs_review
                else labels[room_type]
            )
        room["source"] = "furniture_icon_inference"
        room["confidence"] = round(confidence, 3)
        room["room_review"] = needs_review
        room["room_review_reasons"] = reasons
        room["icon_suggested_room_types"] = [
            {"room_type": item[0], "score": round(item[1], 3)}
            for item in ranked
        ]
