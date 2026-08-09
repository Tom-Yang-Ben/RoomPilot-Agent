from __future__ import annotations

import colorsys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


PROFILE_VERSION = "2026-08-09-image-derived-v1"


def _trimmed_pixels(image: Image.Image) -> np.ndarray:
    """Return the image centre without transparent or preview-frame pixels."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    inset_x = max(1, round(width * 0.06))
    inset_y = max(1, round(height * 0.06))
    cropped = rgb.crop((inset_x, inset_y, width - inset_x, height - inset_y))
    return np.asarray(cropped.resize((128, 128), Image.Resampling.LANCZOS), dtype=np.float32)


def _tone_label(rgb: np.ndarray) -> str:
    red, green, blue = rgb / 255
    hue, saturation, value = colorsys.rgb_to_hsv(float(red), float(green), float(blue))
    warm_bias = float(rgb[0] - rgb[2])
    if saturation < 0.13:
        if value >= 0.78:
            return "暖白" if warm_bias > 5 else "冷白" if warm_bias < -5 else "中性白"
        if value <= 0.32:
            return "深暖灰" if warm_bias > 5 else "深冷灰" if warm_bias < -5 else "深灰"
        return "暖灰" if warm_bias > 5 else "冷灰" if warm_bias < -5 else "中性灰"
    hue_degrees = hue * 360
    if hue_degrees < 18 or hue_degrees >= 345:
        return "磚紅"
    if hue_degrees < 45:
        return "暖棕"
    if hue_degrees < 70:
        return "土黃"
    if hue_degrees < 170:
        return "自然綠"
    if hue_degrees < 250:
        return "藍灰"
    if hue_degrees < 320:
        return "紫灰"
    return "玫瑰棕"


def _brightness_label(luminance: float) -> str:
    if luminance >= 205:
        return "明亮"
    if luminance >= 145:
        return "中明"
    if luminance >= 85:
        return "沉穩"
    return "深色"


def _texture_label(gray: np.ndarray) -> str:
    # The local-detail standard deviation distinguishes smooth paint from visible grain.
    blur = np.asarray(
        Image.fromarray(gray.astype(np.uint8)).filter(ImageFilter.BoxBlur(3)),
        dtype=np.float32,
    )
    local_detail = float(np.std(gray - blur))
    if local_detail < 7:
        return "平滑"
    if local_detail < 16:
        return "細紋"
    if local_detail < 29:
        return "明顯紋理"
    return "強烈紋理"


def image_visual_profile(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as image:
        pixels = _trimmed_pixels(image)
    median = np.median(pixels.reshape(-1, 3), axis=0)
    rgb = np.round(median).astype(int)
    luminance = float(np.dot(rgb, [0.2126, 0.7152, 0.0722]))
    gray = np.dot(pixels, [0.2126, 0.7152, 0.0722])
    tone = _tone_label(rgb)
    brightness = _brightness_label(luminance)
    texture = _texture_label(gray)
    return {
        "version": PROFILE_VERSION,
        "primary_hex": "#{:02x}{:02x}{:02x}".format(*rgb),
        "tags": [tone, brightness, texture],
        "label_zh": f"{tone}・{texture}",
    }
