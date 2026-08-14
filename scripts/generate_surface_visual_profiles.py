from __future__ import annotations

import argparse
import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, BinaryIO

from backend.catalog.surface_visual_profiles import PROFILE_VERSION, image_visual_profile


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "backend" / "catalog" / "data" / "surface_catalog.json"
STATIC_ROOT = ROOT / "backend" / "server" / "static"


def _preview_source(preview_url: str, static_root: Path) -> Path | BinaryIO | None:
    """Return an image PIL can open, or None when the surface has no usable preview.

    Wall materials live on the ambientCG CDN rather than under /static/, so skipping
    remote previews left every wall card without a visual profile — the UI then fell
    back to "紋理待確認".
    """
    if preview_url.startswith("/static/"):
        path = static_root / preview_url.removeprefix("/static/")
        return path if path.is_file() else None
    if preview_url.startswith(("http://", "https://")):
        # ponytail: no on-disk cache, this is a one-off regeneration and not a hot path.
        with urllib.request.urlopen(preview_url, timeout=30) as response:
            return io.BytesIO(response.read())
    return None


def _profile_for(surface: dict[str, Any], static_root: Path) -> dict[str, Any] | None:
    try:
        source = _preview_source(str(surface.get("preview_url") or ""), static_root)
    except Exception as error:  # one dead or throttled preview must not abort the run
        print(f"skip {surface.get('surface_id')}: {error}")
        return None
    return image_visual_profile(source) if source is not None else None


def update_catalog(catalog_path: Path = CATALOG_PATH, static_root: Path = STATIC_ROOT) -> tuple[int, int]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    surfaces = catalog.get("surfaces", [])
    with ThreadPoolExecutor(max_workers=8) as pool:
        profiles = list(pool.map(lambda surface: _profile_for(surface, static_root), surfaces))
    updated = 0
    missing = 0
    for surface, profile in zip(surfaces, profiles):
        if profile is None:
            missing += 1
            continue
        surface["visual_profile"] = profile
        updated += 1
    catalog["visual_profile_version"] = PROFILE_VERSION
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return updated, missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate image-derived RoomPilot material visual profiles.")
    parser.add_argument("--check", action="store_true", help="Fail if profiles are missing or stale.")
    args = parser.parse_args()
    if args.check:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        profiles = [
            item.get("visual_profile")
            for item in catalog.get("surfaces", [])
            if item.get("preview_url")
        ]
        valid = bool(profiles) and all(
            profile and profile.get("version") == PROFILE_VERSION
            for profile in profiles
        )
        raise SystemExit(0 if valid else 1)
    updated, missing = update_catalog()
    print(f"updated={updated} missing={missing}")
