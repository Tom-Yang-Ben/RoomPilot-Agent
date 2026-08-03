"""Room recognition evaluation helpers ported from Cody's v5 scoring flow."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np


ROOM_CLASSES = (
    "kitchen",
    "living",
    "bed",
    "bath",
    "entry",
    "storage",
    "garage",
    "outdoor",
    "space",
)
ROOM_LABEL_ALIASES = {
    "living_room": "living",
    "bathroom": "bath",
    "bedroom": "bed",
    "balcony": "outdoor",
    "room": "space",
    "default": "space",
    "circulation": "entry",
    "dining_room": "living",
    "workspace": "bed",
    # cody 2026-08-01 起的 10 類 CamelCase 詞彙（6300e9e0）——正常路徑會先經
    # CODY_ROOM_TYPE_MAP 轉成主線契約詞彙才進到這裡，此組別名是原字彙直達時
    # 的保險，避免未識別詞彙靜默落入 space。
    "LivingRoom": "living",
    "Kitchen": "kitchen",
    "Bedroom": "bed",
    "Bath": "bath",
    "Balcony": "outdoor",
    "Entry": "entry",
    "Storage": "storage",
    "Garage": "garage",
    "Hallway": "entry",
    "Stair": "space",
}


def normalize_room_label(label: str | None) -> str:
    """Normalize Cody/CubiCasa room labels into the shared scoring classes."""
    if label in (None, ""):
        return "space"
    text = str(label)
    return ROOM_LABEL_ALIASES.get(text, text)


def match_room_masks(
    gt_masks: Sequence[np.ndarray],
    predicted_masks: Sequence[np.ndarray],
    *,
    iou_threshold: float = 0.5,
) -> list[tuple[int, int, float]]:
    """Greedy one-to-one IoU matching for ground-truth and predicted room masks."""
    candidates: list[tuple[float, int, int]] = []
    for gt_index, gt_mask in enumerate(gt_masks):
        gt_area = int(np.asarray(gt_mask, dtype=bool).sum())
        if gt_area <= 0:
            continue
        for predicted_index, predicted_mask in enumerate(predicted_masks):
            predicted = np.asarray(predicted_mask, dtype=bool)
            predicted_area = int(predicted.sum())
            if predicted_area <= 0:
                continue
            intersection = int(np.logical_and(gt_mask, predicted).sum())
            if intersection <= 0:
                continue
            union = gt_area + predicted_area - intersection
            iou = intersection / union if union else 0.0
            if iou >= iou_threshold:
                candidates.append((iou, gt_index, predicted_index))

    matches: list[tuple[int, int, float]] = []
    used_gt: set[int] = set()
    used_predicted: set[int] = set()
    for iou, gt_index, predicted_index in sorted(candidates, reverse=True):
        if gt_index in used_gt or predicted_index in used_predicted:
            continue
        used_gt.add(gt_index)
        used_predicted.add(predicted_index)
        matches.append((gt_index, predicted_index, iou))
    return matches


def build_room_confusion(
    label_pairs: Iterable[tuple[str | None, str | None]],
) -> dict[str, dict[str, int]]:
    """Build a nested confusion matrix for normalized room labels."""
    matrix = {room: {other: 0 for other in ROOM_CLASSES} for room in ROOM_CLASSES}
    for gt_label, predicted_label in label_pairs:
        gt = normalize_room_label(gt_label)
        predicted = normalize_room_label(predicted_label)
        if gt not in matrix:
            gt = "space"
        if predicted not in matrix[gt]:
            predicted = "space"
        matrix[gt][predicted] += 1
    return matrix


def summarize_room_recognition(
    gt_rooms: Sequence[Mapping[str, Any]],
    predicted_rooms: Sequence[Mapping[str, Any]],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Score room segmentation and naming from labelled bool masks."""
    gt_masks = [np.asarray(room["mask"], dtype=bool) for room in gt_rooms]
    predicted_masks = [
        np.asarray(room["mask"], dtype=bool) for room in predicted_rooms
    ]
    matches = match_room_masks(
        gt_masks,
        predicted_masks,
        iou_threshold=iou_threshold,
    )
    pairs = [
        (
            normalize_room_label(gt_rooms[gt_index].get("label")),
            normalize_room_label(
                predicted_rooms[predicted_index].get("label")
            ),
        )
        for gt_index, predicted_index, _ in matches
    ]
    confusion = build_room_confusion(pairs)
    ious = [iou for _, _, iou in matches]
    gt_count = len(gt_rooms)
    predicted_count = len(predicted_rooms)
    per_class: dict[str, dict[str, float | int | None]] = {}
    for room_class in ROOM_CLASSES:
        true_positive = confusion[room_class][room_class]
        gt_class_count = sum(confusion[room_class].values())
        predicted_class_count = sum(
            confusion[other][room_class] for other in ROOM_CLASSES
        )
        per_class[room_class] = {
            "gt": gt_class_count,
            "precision": (
                round(true_positive / predicted_class_count, 3)
                if predicted_class_count
                else None
            ),
            "recall": (
                round(true_positive / gt_class_count, 3)
                if gt_class_count
                else None
            ),
        }

    return {
        "gt_rooms": gt_count,
        "predicted_rooms": predicted_count,
        "matched": len(matches),
        "hit_rate": round(len(matches) / gt_count, 4) if gt_count else 0.0,
        "overseg": round(predicted_count / gt_count, 4) if gt_count else 0.0,
        "mean_iou": round(float(np.mean(ious)), 4) if ious else 0.0,
        "iou_threshold": iou_threshold,
        "confusion": confusion,
        "per_class": per_class,
    }


def _room_label(room: Mapping[str, Any]) -> str | None:
    return (
        room.get("room_type")
        or room.get("type")
        or room.get("label")
    )


def _room_polygon(room: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    for key in ("polygon_cm", "polygon_m", "polygon"):
        polygon = room.get(key)
        if isinstance(polygon, list) and len(polygon) >= 3:
            return polygon
    return None


def _polygon_mask(
    polygon: Sequence[Mapping[str, Any]],
    *,
    min_x: float,
    max_y: float,
    pixels_per_unit: float,
    width: int,
    height: int,
) -> np.ndarray:
    points = np.array(
        [
            [
                round((float(point["x"]) - min_x) * pixels_per_unit),
                round((max_y - float(point["y"])) * pixels_per_unit),
            ]
            for point in polygon
        ],
        dtype=np.int32,
    )
    mask = np.zeros((height, width), dtype=np.uint8)
    import cv2

    cv2.fillPoly(mask, [points], 1)
    return mask.astype(bool)


def rooms_with_polygon_masks(
    rooms: Sequence[Mapping[str, Any]],
    *,
    bounds: tuple[float, float, float, float],
    pixels_per_unit: float,
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    """Convert room polygons into labelled masks for Cody-style evaluation."""
    min_x, _min_y, _max_x, max_y = bounds
    masked_rooms: list[dict[str, Any]] = []
    for room in rooms:
        polygon = _room_polygon(room)
        if polygon is None:
            continue
        masked_rooms.append(
            {
                "label": _room_label(room),
                "mask": _polygon_mask(
                    polygon,
                    min_x=min_x,
                    max_y=max_y,
                    pixels_per_unit=pixels_per_unit,
                    width=width,
                    height=height,
                ),
            }
        )
    return masked_rooms


def summarize_room_polygons(
    reference_rooms: Sequence[Mapping[str, Any]],
    predicted_rooms: Sequence[Mapping[str, Any]],
    *,
    iou_threshold: float = 0.5,
) -> dict[str, Any]:
    """Evaluate labelled room polygons without requiring Cody mask artifacts."""
    polygons = [
        polygon
        for room in [*reference_rooms, *predicted_rooms]
        if (polygon := _room_polygon(room)) is not None
    ]
    if not polygons:
        return {
            "available": False,
            "reason": "missing_room_polygons",
        }

    xs = [float(point["x"]) for polygon in polygons for point in polygon]
    ys = [float(point["y"]) for polygon in polygons for point in polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    longest = max(max_x - min_x, max_y - min_y, 1.0)
    pixels_per_unit = min(24.0, max(1.0, 768.0 / longest))
    width = max(8, int(round((max_x - min_x) * pixels_per_unit)) + 3)
    height = max(8, int(round((max_y - min_y) * pixels_per_unit)) + 3)
    bounds = (min_x, min_y, max_x, max_y)
    reference = rooms_with_polygon_masks(
        reference_rooms,
        bounds=bounds,
        pixels_per_unit=pixels_per_unit,
        width=width,
        height=height,
    )
    predicted = rooms_with_polygon_masks(
        predicted_rooms,
        bounds=bounds,
        pixels_per_unit=pixels_per_unit,
        width=width,
        height=height,
    )
    summary = summarize_room_recognition(
        reference,
        predicted,
        iou_threshold=iou_threshold,
    )
    return {
        "available": True,
        "basis": "room_polygon_iou",
        "raster_size_px": {"width": width, "height": height},
        **summary,
    }
