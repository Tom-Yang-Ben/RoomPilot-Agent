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


def test_public_surfaces_are_procedural_and_need_no_image_profile() -> None:
    catalog = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    assert catalog["version"] == "public-portable-v1"
    assert all(surface["preview_url"] is None for surface in catalog["surfaces"])
    assert all(surface["texture_url"] is None for surface in catalog["surfaces"])
    assert all(surface["color_hex"].startswith("#") for surface in catalog["surfaces"])


def test_public_surfaces_have_no_remote_preview_dependency() -> None:
    catalog = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    assert not any(
        str(surface.get("preview_url") or "").startswith("http")
        for surface in catalog["surfaces"]
    )
    assert all(surface["source"] == "AIPE03 第四組" for surface in catalog["surfaces"])
