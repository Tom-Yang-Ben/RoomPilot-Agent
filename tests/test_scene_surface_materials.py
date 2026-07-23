from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
SURFACE_CATALOG = ROOT / "backend" / "catalog" / "data" / "surface_catalog.json"


def test_style_presets_resolve_to_real_catalog_textures() -> None:
    module_uri = (STATIC / "scene_surface_materials.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ readFileSync }} from "node:fs";
        import {{ resolveSurfaceOption }} from {json.dumps(module_uri)};
        const catalog = JSON.parse(readFileSync(
          {json.dumps(str(SURFACE_CATALOG))},
          "utf8",
        ));
        const floorId = resolveSurfaceOption(catalog, "floor", "light_oak");
        const wallId = resolveSurfaceOption(catalog, "wall", "limewash");
        const floor = catalog.surfaces.find((item) => item.surface_id === floorId);
        const wall = catalog.surfaces.find((item) => item.surface_id === wallId);
        console.log(JSON.stringify({{
          floorId,
          wallId,
          floorTexture: floor?.texture_url || null,
          wallTexture: wall?.texture_url || null,
        }}));
        """
    )

    assert result == {
        "floorId": "wood_cc0_wood_textures_woodfloor051",
        "wallId": "wall_ambientcg_plaster006",
        "floorTexture": (
            "/static/surface_assets/_import_all/cc0-wood-textures/"
            "ambientcg-WoodFloor051.jpg"
        ),
        "wallTexture": (
            "/static/surface_assets/wall_materials_20260708/"
            "ambientcg-wall-clean-Plaster006.jpg"
        ),
    }


def test_scene_viewer_uses_image_texture_as_color_and_relief_maps() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "map: colorMap" in source
    assert "bumpMap" in source
    assert "const bumpMap = createImageTexture" in source
    assert "bumpScale: options.bumpScale ?? profile.bumpScale" in source
    assert "colorMap.clone()" not in source
    assert "roompilotImageSurface" in source


def test_floor_texture_repeat_uses_catalog_physical_size() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "surface.source_size" in source
    assert "Number(physicalSize[1])" in source
    assert "Number(physicalSize[1]) / 100" not in source
    assert "return { x: 240, y: 240 }" in source
