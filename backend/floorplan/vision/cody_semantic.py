"""Optional Cody/CubiCasa semantic room-label availability checks.

Bella can use Django-style icon and zone rules without heavyweight model files.
The Cody semantic path needs CubiCasa weights or precomputed room masks, so this
module reports availability and keeps the production pipeline on a safe fallback
when those assets are absent.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


DEFAULT_WEIGHTS = Path("training/model_finetuned_v5.pkl")
DEFAULT_CACHE_DIR = Path("cubicasa/room")
CODY_V5_WEIGHTS_URL = (
    "https://github.com/Tom-Yang-Ben/RoomPilot-Agent/releases/download/"
    "weights-v5/model_finetuned_v5.pkl"
)
CODY_V5_WEIGHTS_SHA256 = (
    "b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf"
)


def cody_semantic_room_labeler_status(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return whether Cody's CubiCasa semantic room labeler can run locally."""
    base = root or Path.cwd()
    values = env or os.environ
    weights = Path(values.get("CC_WEIGHTS", str(DEFAULT_WEIGHTS)))
    cache_dir = Path(values.get("CC_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    if not weights.is_absolute():
        weights = base / weights
    if not cache_dir.is_absolute():
        cache_dir = base / cache_dir
    cache_files = sorted(cache_dir.glob("*_mask.npz")) if cache_dir.is_dir() else []
    has_weights = weights.is_file()
    has_cache = bool(cache_files)
    available = has_weights or has_cache
    reason = (
        "cody_semantic_ready"
        if available
        else "missing_cody_cubicasa_weights_or_cache"
    )
    return {
        "available": available,
        "reason": reason,
        "model_version": "cody_cubicasa_v5",
        "weights_path": str(weights),
        "weights_present": has_weights,
        "weights_url": CODY_V5_WEIGHTS_URL,
        "weights_sha256": CODY_V5_WEIGHTS_SHA256,
        "cache_dir": str(cache_dir),
        "cache_count": len(cache_files),
        "fallback": None if available else "django_icon_zone_rules",
    }
