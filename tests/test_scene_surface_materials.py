from __future__ import annotations

from scripts.static_source_graph import scene_controller_source, scene_viewer_source

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
SURFACE_CATALOG = ROOT / "backend" / "catalog" / "data" / "surface_catalog.json"


def test_style_presets_resolve_to_procedural_catalog_surfaces() -> None:
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
        const warmWallId = resolveSurfaceOption(catalog, "wall", "warm_white");
        const sageWallId = resolveSurfaceOption(catalog, "wall", "sage");
        const floor = catalog.surfaces.find((item) => item.surface_id === floorId);
        const wall = catalog.surfaces.find((item) => item.surface_id === wallId);
        const warmWall = catalog.surfaces.find((item) => item.surface_id === warmWallId);
        const sageWall = catalog.surfaces.find((item) => item.surface_id === sageWallId);
        console.log(JSON.stringify({{
          floorId,
          wallId,
          warmWallId,
          sageWallId,
          floorTexture: floor?.texture_url || null,
          wallTexture: wall?.texture_url || null,
          warmWallTexture: warmWall?.texture_url || null,
          sageWallTexture: sageWall?.texture_url || null,
        }}));
        """
    )

    assert result["floorId"] == "light_oak"
    assert result["wallId"] == "limewash"
    assert result["warmWallId"] == "warm_white"
    assert result["sageWallId"] == "limewash"
    assert result["floorTexture"] is None
    assert result["wallTexture"] is None
    assert result["warmWallTexture"] is None
    assert result["sageWallTexture"] is None


def test_realtime_surface_recommendations_explain_and_vary_options() -> None:
    source = scene_controller_source(STATIC)

    assert "SURFACE_VARIANT_OPTIONS" in source
    assert "surfaceRecommendationScore" in source
    assert "surfaceRecommendationReason" in source
    assert "materialOptionsForStyle" in source
    assert "title=\"${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}\"" in source
    assert "scoreFor" in source
    assert "scandinavian_2" in source
    assert "modern_minimal_2" in source
    assert "industrial_2" in source
    assert "herringbone_oak" in source
    assert "microcement" in source
    assert "mineral_beige" in source


def test_surface_preset_mapping_uses_only_public_procedural_ids() -> None:
    source = (STATIC / "scene_surface_materials.js").read_text(encoding="utf-8")

    assert 'warm_white: "warm_white"' in source
    assert 'limewash: "limewash"' in source
    assert 'sage: "limewash"' in source
    assert 'greige: "light_gray"' in source
    assert "ambientcg" not in source.casefold()


def test_scene_viewer_uses_image_texture_as_color_and_relief_maps() -> None:
    source = scene_viewer_source(STATIC)

    assert "map: colorMap" in source
    assert "bumpMap" in source
    assert "const bumpMap = createImageTexture" in source
    assert "bumpScale: options.bumpScale ?? profile.bumpScale" in source
    assert "colorMap.clone()" not in source
    assert "roompilotImageSurface" in source


def test_floor_texture_repeat_uses_catalog_physical_size() -> None:
    source = scene_viewer_source(STATIC)

    assert "surface.source_size" in source
    assert "Number(physicalSize[1])" in source
    assert "Number(physicalSize[1]) / 100" not in source
    assert "return { x: 240, y: 240 }" in source
