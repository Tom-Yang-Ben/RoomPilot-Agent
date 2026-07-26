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


def normalize_room_label(label: str | None) -> str:
    """Normalize Cody/CubiCasa room labels into the shared scoring classes."""
    if label in (None, "", "room", "default"):
        return "space"
    if label == "balcony":
        return "outdoor"
    return str(label)


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
