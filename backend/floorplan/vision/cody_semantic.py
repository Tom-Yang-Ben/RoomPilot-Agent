"""Optional Cody/CubiCasa semantic room-label availability checks.

Bella can use Django-style icon and zone rules without heavyweight model files.
The Cody semantic path needs CubiCasa weights or precomputed room masks, so this
module reports availability and keeps the production pipeline on a safe fallback
when those assets are absent.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping
import urllib.error
import urllib.request

import numpy as np


DEFAULT_WEIGHTS = Path("backend/floorplan/model_finetuned_v5.pkl")
DEFAULT_CACHE_DIR = Path("cubicasa/room")
DEFAULT_INFER_SCRIPT = Path("backend/floorplan/infer_cubicasa.py")
REQUIRED_MASK_FIELDS = ("room", "wall", "window", "door", "icon")
CODY_V5_WEIGHTS_URL = (
    "https://github.com/Tom-Yang-Ben/RoomPilot-Agent/releases/download/"
    "weights-v5/model_finetuned_v5.pkl"
)
CODY_V5_WEIGHTS_ASSET_API = (
    "https://api.github.com/repos/Tom-Yang-Ben/RoomPilot-Agent/"
    "releases/assets/489011637"
)
CODY_V5_WEIGHTS_SHA256 = (
    "b7a280d2d7cf2dde580a947e1ebc7b4d12e53135c05581babb3b5797a166f4cf"
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D102
        return None


def _semantic_paths(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[Path, Path, Mapping[str, str]]:
    base = root or Path.cwd()
    values = env if env is not None else os.environ
    weights = Path(values.get("CC_WEIGHTS", str(DEFAULT_WEIGHTS)))
    cache_dir = Path(values.get("CC_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    if not weights.is_absolute():
        weights = base / weights
    if not cache_dir.is_absolute():
        cache_dir = base / cache_dir
    return weights, cache_dir, values


def _infer_script_path(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    base = root or Path.cwd()
    values = env if env is not None else os.environ
    script = Path(values.get("CC_INFER_SCRIPT", str(DEFAULT_INFER_SCRIPT)))
    if not script.is_absolute():
        script = base / script
    return script


def _mask_path_for_image(cache_dir: Path, image_path: Path) -> Path:
    return cache_dir / f"{image_path.stem}_mask.npz"


def _has_room_mask(mask_path: Path) -> bool:
    try:
        load_cody_semantic_mask(mask_path)
        return True
    except (OSError, ValueError):
        return False


def load_cody_semantic_mask(mask_path: str | Path) -> dict[str, Any]:
    """Load and validate a Cody/CubiCasa mask cache file.

    Cody's inference output contains boolean wall/window/door masks plus uint8
    room and icon argmax maps. Bella accepts the cache only when all arrays
    share the same 2D shape, so downstream room and opening logic does not mix
    incompatible evidence.
    """
    path = Path(mask_path)
    if not path.is_file():
        raise ValueError(f"semantic mask missing: {path}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            missing = [field for field in REQUIRED_MASK_FIELDS if field not in archive]
            if missing:
                raise ValueError(f"semantic mask missing fields: {', '.join(missing)}")
            arrays = {field: archive[field] for field in REQUIRED_MASK_FIELDS}
    except Exception as exc:
        raise ValueError(f"invalid semantic mask: {path}") from exc

    shapes = {field: array.shape for field, array in arrays.items()}
    if any(len(shape) != 2 for shape in shapes.values()):
        raise ValueError(f"semantic mask arrays must be 2D: {path}")
    if len(set(shapes.values())) != 1:
        raise ValueError(f"semantic mask arrays have inconsistent shapes: {path}")

    for field in ("wall", "window", "door"):
        arrays[field] = arrays[field].astype(bool, copy=False)
    for field in ("room", "icon"):
        arrays[field] = arrays[field].astype(np.uint8, copy=False)
    return {
        "path": str(path),
        "shape": tuple(next(iter(shapes.values()))),
        "arrays": arrays,
    }


def _gh_token(env: Mapping[str, str] | None = None) -> str | None:
    values = env if env is not None else os.environ
    return values.get("GITHUB_TOKEN") or values.get("GH_TOKEN")


def _resolve_weights_url(env: Mapping[str, str] | None = None) -> str | None:
    """Return a downloadable Release asset URL without leaking auth headers.

    Public repositories can use the direct Release URL. Private repositories need
    a token for the asset API, which responds with a short-lived signed URL in a
    redirect location. The signed URL is returned so the download itself does
    not forward the Authorization header to storage.
    """
    try:
        urllib.request.urlopen(
            urllib.request.Request(CODY_V5_WEIGHTS_URL, method="HEAD"),
            timeout=15,
        )
        return CODY_V5_WEIGHTS_URL
    except Exception:
        pass

    token = _gh_token(env)
    if not token:
        return None
    request = urllib.request.Request(
        CODY_V5_WEIGHTS_ASSET_API,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        urllib.request.build_opener(_NoRedirect()).open(request, timeout=30)
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 307, 308):
            return exc.headers.get("Location")
    except Exception:
        pass
    return None


def ensure_cody_semantic_weights(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Ensure Cody v5 semantic weights exist, downloading only the default path.

    A user-provided ``CC_WEIGHTS`` path is never auto-downloaded. That keeps A/B
    tests honest: if an override is missing, callers get a clear failure instead
    of silently falling back to the default model.
    """
    weights, _, values = _semantic_paths(root=root, env=env)
    if weights.is_file():
        return {
            "ok": True,
            "reason": "weights_present",
            "weights_path": str(weights),
            "downloaded": False,
        }
    if values.get("CC_WEIGHTS"):
        return {
            "ok": False,
            "reason": "custom_weights_missing",
            "weights_path": str(weights),
            "downloaded": False,
        }

    url = _resolve_weights_url(values)
    if not url:
        return {
            "ok": False,
            "reason": "weights_download_unavailable",
            "weights_path": str(weights),
            "downloaded": False,
        }

    weights.parent.mkdir(parents=True, exist_ok=True)
    tmp = weights.with_name(weights.name + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)
        digest = hashlib.sha256()
        with tmp.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != CODY_V5_WEIGHTS_SHA256:
            tmp.unlink(missing_ok=True)
            return {
                "ok": False,
                "reason": "weights_checksum_mismatch",
                "weights_path": str(weights),
                "downloaded": False,
            }
        os.replace(tmp, weights)
        return {
            "ok": True,
            "reason": "weights_downloaded",
            "weights_path": str(weights),
            "downloaded": True,
        }
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return {
            "ok": False,
            "reason": "weights_download_failed",
            "weights_path": str(weights),
            "downloaded": False,
            "error": str(exc),
        }


def ensure_cody_semantic_masks(
    image_paths: list[str | Path],
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
    runner: Any | None = None,
) -> dict[str, object]:
    """Ensure CubiCasa semantic mask cache files exist for uploaded images.

    This is intentionally a thin adapter around Cody's heavyweight inference
    script. Bella can verify orchestration without importing torch/cv2 at API
    import time, and production gets a clear fallback reason when model assets
    are absent.
    """
    weights, cache_dir, values = _semantic_paths(root=root, env=env)
    base = root or Path.cwd()
    images = [Path(path) for path in image_paths]
    absolute_images = [path if path.is_absolute() else base / path for path in images]
    mask_paths = [_mask_path_for_image(cache_dir, image) for image in absolute_images]
    missing = [
        image
        for image, mask_path in zip(absolute_images, mask_paths)
        if not _has_room_mask(mask_path)
    ]
    if not missing:
        return {
            "ok": True,
            "reason": "semantic_masks_cached",
            "cache_dir": str(cache_dir),
            "cached": [str(path) for path in mask_paths],
            "generated": [],
        }

    weight_result = ensure_cody_semantic_weights(root=root, env=values)
    if not weight_result["ok"]:
        return {
            "ok": False,
            "reason": weight_result["reason"],
            "cache_dir": str(cache_dir),
            "weights_path": str(weights),
            "missing_images": [str(path) for path in missing],
        }

    script = _infer_script_path(root=root, env=values)
    if not script.is_file():
        return {
            "ok": False,
            "reason": "inference_script_missing",
            "cache_dir": str(cache_dir),
            "weights_path": str(weights),
            "script_path": str(script),
            "missing_images": [str(path) for path in missing],
        }

    cache_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script),
        str(weights),
        str(cache_dir),
        *[str(path) for path in missing],
    ]
    try:
        if runner is None:
            subprocess.run(command, check=True, capture_output=True, text=True)
        else:
            runner(command)
    except Exception as exc:
        return {
            "ok": False,
            "reason": "inference_failed",
            "cache_dir": str(cache_dir),
            "weights_path": str(weights),
            "script_path": str(script),
            "missing_images": [str(path) for path in missing],
            "error": str(exc),
        }

    generated = [_mask_path_for_image(cache_dir, image) for image in missing]
    invalid = [path for path in generated if not _has_room_mask(path)]
    if invalid:
        return {
            "ok": False,
            "reason": "inference_output_missing",
            "cache_dir": str(cache_dir),
            "weights_path": str(weights),
            "script_path": str(script),
            "invalid_outputs": [str(path) for path in invalid],
        }
    return {
        "ok": True,
        "reason": "semantic_masks_generated",
        "cache_dir": str(cache_dir),
        "weights_path": str(weights),
        "script_path": str(script),
        "cached": [str(path) for path in mask_paths],
        "generated": [str(path) for path in generated],
    }


def cody_semantic_room_labeler_status(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return whether Cody's CubiCasa semantic room labeler can run locally."""
    weights, cache_dir, _values = _semantic_paths(root=root, env=env)
    cache_files = []
    if cache_dir.is_dir():
        cache_files = [
            path for path in sorted(cache_dir.glob("*_mask.npz")) if _has_room_mask(path)
        ]
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
        "inference_script_path": str(_infer_script_path(root=root, env=env)),
        "weights_url": CODY_V5_WEIGHTS_URL,
        "weights_asset_api": CODY_V5_WEIGHTS_ASSET_API,
        "weights_sha256": CODY_V5_WEIGHTS_SHA256,
        "cache_dir": str(cache_dir),
        "cache_count": len(cache_files),
        "fallback": None if available else "django_icon_zone_rules",
    }
