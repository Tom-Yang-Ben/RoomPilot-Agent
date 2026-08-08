from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script
from backend.paths import STATIC_DIR


SURFACE_CATALOG = ROOT / "backend" / "catalog" / "data" / "surface_catalog.json"


def test_style_presets_resolve_to_real_catalog_textures() -> None:
    module_uri = (STATIC_DIR / "scene_surface_materials.js").as_uri()
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

    assert result["floorId"] == "wood_cc0_wood_textures_planks039"
    assert result["floorTexture"] == (
        "/static/surface_assets/_import_all/cc0-wood-textures/"
        "ambientcg-Planks039.jpg"
    )
    # 牆 preset 不再解析到「貼圖在遠端」的型錄筆：那些貼圖離線載不到，
    # viewer 會整批退回同一張本機 plaster，十個牆選項就長得一模一樣。
    # 保留選項 id，讓 viewer 走各選項獨立的程序化材質。
    assert result["wallId"] == "limewash"
    assert result["warmWallId"] == "warm_white"
    assert result["sageWallId"] == "sage"
    assert result["wallTexture"] is None
    assert result["warmWallTexture"] is None
    assert result["sageWallTexture"] is None


def test_realtime_surface_recommendations_explain_and_vary_options() -> None:
    source = (STATIC_DIR / "scene_v2.js").read_text(encoding="utf-8")

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


def test_surface_preset_mapping_no_longer_collapses_to_one_wall_material() -> None:
    source = (STATIC_DIR / "scene_surface_materials.js").read_text(encoding="utf-8")

    assert 'warm_white: "wall_json_ambientcg_wall_paint_paintedplaster017"' in source
    assert 'limewash: "wall_json_ambientcg_wall_paint_plaster002"' in source
    assert 'sage: "wall_json_ambientcg_wall_wallpaper_fabric018"' in source
    assert 'greige: "wall_json_ambientcg_wall_paint_concrete008"' in source
    assert source.count('wall_ambientcg_plaster006"') == 0


def test_scene_viewer_uses_image_texture_as_color_and_relief_maps() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "map: colorMap" in source
    assert "bumpMap" in source
    assert "const bumpMap = createImageTexture" in source
    assert "bumpScale: options.bumpScale ?? profile.bumpScale" in source
    assert "colorMap.clone()" not in source
    assert "roompilotImageSurface" in source


def test_floor_texture_repeat_uses_catalog_physical_size() -> None:
    source = (STATIC_DIR / "scene_viewer.js").read_text(encoding="utf-8")

    assert "surface.source_size" in source
    assert "Number(physicalSize[1])" in source
    assert "Number(physicalSize[1]) / 100" not in source
    assert "return { x: 240, y: 240 }" in source
