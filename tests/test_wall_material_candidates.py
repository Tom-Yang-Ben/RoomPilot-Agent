from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generated_wall_materials_remain_validated_candidates_only():
    manifest = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "wall_material_candidates.json"
        ).read_text(encoding="utf-8")
    )
    production = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "surface_catalog.json"
        ).read_text(encoding="utf-8")
    )
    production_ids = {item["surface_id"] for item in production["surfaces"]}

    assert manifest["catalog_status"] == "generated_candidates_not_for_production_selection"
    assert manifest["chemistry_rule"]["water_based_or_oil_based"] == (
        "metadata_not_visually_identifiable"
    )
    assert set(manifest["finish_presets"]) == {"matte", "semi_gloss", "high_gloss"}
    assert set(manifest["classification_groups"]) == {
        "paint",
        "mineral_plaster",
        "decorative_effect",
        "functional",
    }
    assert len(manifest["items"]) == 18
    for item in manifest["items"]:
        assert item["allowed_usage"] == ["wall"]
        assert item["designer_confirmation_required"] is True
        assert item["prompt_summary_zh"]
        assert item["category_id"] in manifest["classification_groups"]
        assert item["subtype_id"]
        assert item["color_family"]
        assert item["material_id"] not in production_ids
        texture = (
            PROJECT_ROOT
            / "backend"
            / "server"
            / "static"
            / item["texture_url"].removeprefix("/static/")
        )
        assert texture.is_file()
        with Image.open(texture) as image:
            assert image.format == "PNG"
            assert image.width >= 1024
            assert image.height >= 1024


def test_every_taiwan_style_card_has_one_wall_texture_candidate():
    style_catalog = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "taiwan_style_cards.json"
        ).read_text(encoding="utf-8")
    )
    variants = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "wall_style_card_variants.json"
        ).read_text(encoding="utf-8")
    )
    expected_cards = {
        card["card_id"]
        for style in style_catalog["styles"]
        for card in style["cards"]
    }
    actual_cards = {item["style_card_id"] for item in variants["items"]}

    assert variants["catalog_status"] == (
        "generated_candidates_not_for_production_selection"
    )
    assert variants["variant_count"] == 18
    assert actual_cards == expected_cards
    for item in variants["items"]:
        assert item["wall_hex"].startswith("#")
        assert item["wall_material"]
        assert item["keywords"]
        texture = (
            PROJECT_ROOT
            / "backend"
            / "server"
            / "static"
            / item["texture_url"].removeprefix("/static/")
        )
        assert texture.is_file()
        with Image.open(texture) as image:
            assert image.format == "PNG"
            assert image.width >= 1024
            assert image.height >= 1024


def test_every_taiwan_style_card_has_one_accent_wall_candidate():
    style_catalog = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "taiwan_style_cards.json"
        ).read_text(encoding="utf-8")
    )
    variants = json.loads(
        (
            PROJECT_ROOT
            / "backend"
            / "catalog"
            / "data"
            / "wall_style_card_accent_variants.json"
        ).read_text(encoding="utf-8")
    )
    expected_cards = {
        card["card_id"]
        for style in style_catalog["styles"]
        for card in style["cards"]
    }
    actual_cards = {item["style_card_id"] for item in variants["items"]}

    assert variants["catalog_status"] == (
        "generated_candidates_not_for_production_selection"
    )
    assert variants["role"] == "accent_wall"
    assert variants["variant_count"] == 18
    assert actual_cards == expected_cards
    for item in variants["items"]:
        assert item["accent_hex"].startswith("#")
        assert item["wall_material"]
        assert item["keywords"]
        texture = (
            PROJECT_ROOT
            / "backend"
            / "server"
            / "static"
            / item["texture_url"].removeprefix("/static/")
        )
        assert texture.is_file()
        with Image.open(texture) as image:
            assert image.format == "PNG"
            assert image.width >= 1024
            assert image.height >= 1024
