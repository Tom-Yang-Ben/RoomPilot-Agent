from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.catalog.surface_visual_profiles import PROFILE_VERSION, image_visual_profile


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "backend" / "catalog" / "data" / "surface_catalog.json"
STATIC_ROOT = ROOT / "backend" / "server" / "static"


def update_catalog(catalog_path: Path = CATALOG_PATH, static_root: Path = STATIC_ROOT) -> tuple[int, int]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    updated = 0
    missing = 0
    for surface in catalog.get("surfaces", []):
        preview_url = str(surface.get("preview_url") or "")
        if not preview_url.startswith("/static/"):
            missing += 1
            continue
        preview_path = static_root / preview_url.removeprefix("/static/")
        if not preview_path.is_file():
            missing += 1
            continue
        surface["visual_profile"] = image_visual_profile(preview_path)
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
            if str(item.get("preview_url") or "").startswith("/static/")
        ]
        valid = bool(profiles) and all(
            profile and profile.get("version") == PROFILE_VERSION
            for profile in profiles
        )
        raise SystemExit(0 if valid else 1)
    updated, missing = update_catalog()
    print(f"updated={updated} missing={missing}")
