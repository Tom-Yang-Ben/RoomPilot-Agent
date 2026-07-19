from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "roompilot" / "server" / "static"
PBR_MODULE = STATIC / "scene_pbr_contracts.js"
VIEWER = STATIC / "scene_viewer.js"


def test_image_surfaces_keep_texture_detail_and_use_physical_profiles() -> None:
    result = run_workflow_script(
        f"""
        import {{
          surfacePbrProfile,
          surfaceTint,
        }} from {json.dumps(PBR_MODULE.as_uri())};
        console.log(JSON.stringify({{
          wood: surfacePbrProfile({{ category: "wood" }}, "floor"),
          tile: surfacePbrProfile({{ category: "tile" }}, "floor"),
          plaster: surfacePbrProfile({{ category: "wall" }}, "wall"),
          tinted: surfaceTint("#8B684B", true),
          procedural: surfaceTint("#8B684B", false),
        }}));
        """
    )

    assert result["wood"]["roughness"] < result["plaster"]["roughness"]
    assert result["tile"]["clearcoat"] > result["wood"]["clearcoat"]
    assert result["wood"]["bumpScale"] > result["plaster"]["bumpScale"]
    assert result["tinted"].upper() != "#8B684B"
    assert result["procedural"].upper() == "#8B684B"


def test_furniture_roles_receive_distinct_realistic_pbr_parameters() -> None:
    result = run_workflow_script(
        f"""
        import {{ furniturePbrProfile }} from {json.dumps(PBR_MODULE.as_uri())};
        console.log(JSON.stringify({{
          fabric: furniturePbrProfile("fabric"),
          wood: furniturePbrProfile("wood"),
          metal: furniturePbrProfile("metal"),
          glass: furniturePbrProfile("glass"),
        }}));
        """
    )

    assert result["fabric"]["roughness"] > result["wood"]["roughness"]
    assert result["metal"]["metalness"] > 0.7
    assert result["glass"]["transmission"] > 0.7
    assert result["glass"]["transparent"] is True


def test_viewer_uses_physical_materials_relief_and_contact_shadows() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert "new THREE.MeshPhysicalMaterial" in source
    assert "surfacePbrProfile" in source
    assert "surfaceTint" in source
    assert "const bumpMap = createImageTexture" in source
    assert "function addFurnitureContactShadow" in source
    assert "roompilotContactShadow" in source
    assert "applyPhysicalFurnitureProfile" in source


def test_realistic_views_hide_planning_circulation_overlay() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert "function configureCirculationForView" in source
    assert 'object.visible = mode === "topdown"' in source
    assert "configureCirculationForView(mode)" in source


def test_floor_is_clipped_to_cody_floorplan_exterior() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert "function createFloorGeometry" in source
    assert "floorplan?.room_regions?.[0]?.exterior" in source
    assert "new THREE.ShapeGeometry(shape)" in source
    assert "createFloorGeometry(sceneData.floorplan, widthM, depthM)" in source


def test_orthographic_dollhouse_avoids_gtao_projection_artifacts() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert '["walk", "orbit"].includes(mode)' in source
    assert '["walk", "orbit"].includes(viewMode.mode)' in source
    assert "gtaoRequested" in source
    assert "samples: 6" in source
    assert 'gtaoPass?.enabled ? "GTAO" : "接觸陰影"' in source
