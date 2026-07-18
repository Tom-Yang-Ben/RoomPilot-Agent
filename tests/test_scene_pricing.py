from roompilot.server.scene_service import generate_layout


def test_layout_preserves_known_catalog_price_and_material_for_bom() -> None:
    result = generate_layout(
        420,
        360,
        [
            {
                "furniture_id": "priced-chair",
                "name_zh_raw": "單椅",
                "normalized_type": "chair",
                "model_url": "/chair.glb",
                "size_cm": {"width": 60, "depth": 60, "height": 80},
                "price_twd": 6800,
                "material": "橡木與布料",
            }
        ],
    )

    assert result[0]["price_twd"] == 6800
    assert result[0]["material"] == "橡木與布料"
