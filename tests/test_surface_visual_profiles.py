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


def test_every_previewable_surface_has_a_current_visual_profile() -> None:
    """曾只檢查 /static/ 的預覽圖，而牆面材質 106/110 的預覽圖在 ambientCG CDN 上，
    產生器跳過它們也不會有測試變紅——第 6 步 89 張可選牆面有 85 張顯示「紋理待確認」。
    有預覽圖就必須有 profile，不分本機或遠端。"""
    catalog = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    previewable = [surface for surface in catalog["surfaces"] if surface.get("preview_url")]
    stale = [
        surface["surface_id"]
        for surface in previewable
        if surface.get("visual_profile", {}).get("version") != PROFILE_VERSION
        or len(surface["visual_profile"].get("tags") or []) != 3
        or not surface["visual_profile"].get("label_zh")
        or not surface["visual_profile"].get("primary_hex", "").startswith("#")
    ]

    assert catalog["visual_profile_version"] == PROFILE_VERSION
    assert previewable
    assert not stale, f"缺少或過期的材質視覺 profile（前端會顯示「紋理待確認」）：{stale[:10]}"


def test_remote_previews_are_profiled_not_skipped() -> None:
    """牆面走遠端 CDN，產生器只讀本機檔案就是這個 bug 的根因。"""
    catalog = json.loads(
        (ROOT / "backend" / "catalog" / "data" / "surface_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    remote = [
        surface
        for surface in catalog["surfaces"]
        if str(surface.get("preview_url") or "").startswith("http")
    ]

    assert remote
    assert all(surface.get("visual_profile", {}).get("label_zh") for surface in remote)
