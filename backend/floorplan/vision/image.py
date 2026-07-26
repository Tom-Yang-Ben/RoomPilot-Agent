"""Floor-plan image decoding and lightweight input profiling."""

from __future__ import annotations

import cv2
import numpy as np


def decode_image(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("unsupported_or_corrupt_floorplan_image")
    return image


def profile_floorplan_image(image: np.ndarray) -> dict[str, object]:
    """Classify the uploaded drawing so recognition can choose a safer route.

    The geometry engines still operate on grayscale ink today, but this profile
    preserves whether the source looked like colored line art, clean grayscale
    line art, or a lower-contrast scan. That keeps color handling explicit
    instead of silently discarding useful color cues.
    """
    if image.ndim == 2:
        bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        gray = image
    else:
        bgr = image[:, :, :3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1].astype(np.float32)
    value = hsv[:, :, 2].astype(np.float32)
    b, g, r = cv2.split(bgr.astype(np.float32))
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    colorfulness = float(
        np.sqrt(rg.std() ** 2 + yb.std() ** 2)
        + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    )
    saturation_p90 = float(np.percentile(saturation, 90))
    saturation_mean = float(saturation.mean())
    saturated_ratio = float(((saturation >= 35) & (value < 250)).mean())
    dark_ratio = float((gray < 80).mean())
    midtone_ratio = float(((gray >= 80) & (gray <= 220)).mean())
    contrast_std = float(gray.std())
    _, otsu_ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink_ratio = float((otsu_ink > 0).mean())

    has_color_signal = (saturation_p90 >= 35.0 and colorfulness >= 8.0) or saturated_ratio >= 0.01
    low_contrast_scan = not has_color_signal and midtone_ratio >= 0.18
    if has_color_signal:
        kind = "color_line_art"
        threshold_route = "color_mask_then_otsu"
    elif low_contrast_scan:
        kind = "scanned_grayscale"
        threshold_route = "adaptive_threshold_review"
    else:
        kind = "grayscale_line_art"
        threshold_route = "otsu"

    return {
        "kind": kind,
        "threshold_route": threshold_route,
        "has_color_signal": has_color_signal,
        "metrics": {
            "colorfulness": round(colorfulness, 3),
            "saturation_mean": round(saturation_mean, 3),
            "saturation_p90": round(saturation_p90, 3),
            "saturated_ratio": round(saturated_ratio, 4),
            "dark_ratio": round(dark_ratio, 4),
            "midtone_ratio": round(midtone_ratio, 4),
            "contrast_std": round(contrast_std, 3),
            "otsu_ink_ratio": round(ink_ratio, 4),
        },
    }
