from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "backend" / "catalog" / "data"


def test_generated_private_wall_candidate_sets_are_not_distributed() -> None:
    for filename in (
        "wall_material_candidates.json",
        "wall_style_card_variants.json",
        "wall_style_card_accent_variants.json",
    ):
        assert not (DATA / filename).exists()


def test_public_wall_surfaces_are_project_authored_solid_colours() -> None:
    catalog = json.loads((DATA / "surface_catalog.json").read_text(encoding="utf-8"))
    walls = [surface for surface in catalog["surfaces"] if "wall" in surface["usage"]]

    assert len(walls) >= 4
    assert all(surface["texture_url"] is None for surface in walls)
    assert all(surface["preview_url"] is None for surface in walls)
    assert all(surface["color_hex"].startswith("#") for surface in walls)
    assert all(surface["source_license_status"] == "GPL-3.0-only" for surface in walls)


def test_every_style_card_has_a_palette_instead_of_an_image_path() -> None:
    cards = json.loads((DATA / "taiwan_style_cards.json").read_text(encoding="utf-8"))
    flattened = [card for style in cards["styles"] for card in style["cards"]]

    assert len(flattened) == 18
    assert all("image_file" not in card for card in flattened)
    assert all(len(card["palette_hex"]) >= 3 for card in flattened)
