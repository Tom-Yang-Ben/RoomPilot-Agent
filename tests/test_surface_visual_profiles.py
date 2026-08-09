from __future__ import annotations

import json

from PIL import Image

from backend.catalog.surface_visual_profiles import PROFILE_VERSION, image_visual_profile
from test_scene_workflow import ROOT


def test_visual_profile_uses_image_pixels_instead_of_catalog_metadata(tmp_path) -> None:
    sample = tmp_path / "sample.png"
    Image.new("RGB", (80, 80), "#8c5e3c").save(sample)

    profile = image_visual_profile(sample)

    assert profile["version"] == PROFILE_VERSION
    assert profile["primary_hex"] == "#8c5e3c"
    assert profile["tags"] == ["暖棕", "沉穩", "平滑"]
    assert profile["label_zh"] == "暖棕・平滑"


def test_local_catalog_previews_have_a_current_visual_profile() -> None:
    catalog = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    local_surfaces = [
        surface
        for surface in catalog["surfaces"]
        if str(surface.get("preview_url") or "").startswith("/static/")
    ]

    assert catalog["visual_profile_version"] == PROFILE_VERSION
    assert local_surfaces
    assert all(
        surface.get("visual_profile", {}).get("version") == PROFILE_VERSION
        and len(surface["visual_profile"].get("tags") or []) == 3
        and surface["visual_profile"].get("primary_hex", "").startswith("#")
        for surface in local_surfaces
    )
