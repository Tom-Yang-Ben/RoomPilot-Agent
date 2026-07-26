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
from typing import Mapping
import urllib.error
import urllib.request


DEFAULT_WEIGHTS = Path("training/model_finetuned_v5.pkl")
DEFAULT_CACHE_DIR = Path("cubicasa/room")
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
    values = env or os.environ
    weights = Path(values.get("CC_WEIGHTS", str(DEFAULT_WEIGHTS)))
    cache_dir = Path(values.get("CC_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    if not weights.is_absolute():
        weights = base / weights
    if not cache_dir.is_absolute():
        cache_dir = base / cache_dir
    return weights, cache_dir, values


def _gh_token(env: Mapping[str, str] | None = None) -> str | None:
    values = env or os.environ
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


def cody_semantic_room_labeler_status(
    *,
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return whether Cody's CubiCasa semantic room labeler can run locally."""
    weights, cache_dir, _values = _semantic_paths(root=root, env=env)
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
        "weights_asset_api": CODY_V5_WEIGHTS_ASSET_API,
        "weights_sha256": CODY_V5_WEIGHTS_SHA256,
        "cache_dir": str(cache_dir),
        "cache_count": len(cache_files),
        "fallback": None if available else "django_icon_zone_rules",
    }
