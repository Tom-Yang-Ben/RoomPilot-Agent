from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "roompilot" / "server" / "static"
PBR_MODULE = STATIC / "scene_pbr_contracts.js"
ARCHITECTURE_MODULE = STATIC / "scene_architecture.js"
VIEWER = STATIC / "scene_viewer.js"
STYLE_PACKS_MODULE = STATIC / "scene_style_packs.js"


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


def test_style_card_tints_remain_visibly_distinct_on_photographed_surfaces() -> None:
    result = run_workflow_script(
        f"""
        import {{ surfaceTint }} from {json.dumps(PBR_MODULE.as_uri())};
        const rgb = (hex) => [1, 3, 5].map((index) =>
          Number.parseInt(hex.slice(index, index + 2), 16));
        const distance = (left, right) => Math.hypot(
          ...rgb(left).map((channel, index) => channel - rgb(right)[index])
        );
        const milkWhite = surfaceTint("#F8F0E5", true, "wall");
        const milkTea = surfaceTint("#AA8062", true, "wall");
        const paleOak = surfaceTint("#C3A17F", true, "floor");
        const darkWalnut = surfaceTint("#6F5140", true, "floor");
        console.log(JSON.stringify({{
          wallDistance: distance(milkWhite, milkTea),
          floorDistance: distance(paleOak, darkWalnut),
        }}));
        """
    )

    assert result["wallDistance"] >= 70
    assert result["floorDistance"] >= 70


def test_style_pack_palette_roles_match_the_reference_material_tiles() -> None:
    result = run_workflow_script(
        f"""
        import {{ STYLE_PACKS }} from {json.dumps(STYLE_PACKS_MODULE.as_uri())};
        const card = STYLE_PACKS.find((pack) => pack.id === "cream_3");
        console.log(JSON.stringify({{
          palette: card.palette,
          wall: card.wall.color,
          floor: card.floor.color,
          furniture: card.furniture.color,
          accent: card.furniture.accent,
        }}));
        """
    )

    assert result == {
        "palette": ["#C4AC96", "#E5D9CD", "#B97E44", "#89572A"],
        "wall": "#C4AC96",
        "floor": "#B97E44",
        "furniture": "#E5D9CD",
        "accent": "#89572A",
    }


def test_openings_only_cut_their_confirmed_host_wall() -> None:
    result = run_workflow_script(
        f"""
        import {{ openingBelongsToWall }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const host = {{
          id: "wall-main",
              start: {{ x: 0, z: 0 }},
              end: {{ x: 400, z: 0 }},
        }};
        const adjacent = {{
          id: "wall-adjacent",
              start: {{ x: 200, z: -200 }},
              end: {{ x: 200, z: 200 }},
        }};
        const door = {{
          id: "door-1",
          host_wall_id: "wall-main",
              start: {{ x: 160, z: 0 }},
              end: {{ x: 240, z: 0 }},
        }};
        console.log(JSON.stringify({{
              host: openingBelongsToWall(host, door, 12),
              adjacent: openingBelongsToWall(adjacent, door, 12),
        }}));
        """
    )

    assert result == {"host": True, "adjacent": False}


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
    assert "synchronizedFloorRegions(floorplan, widthCm, depthCm)" in source
    assert ".map((region) => polygonShape(region, true))" in source
    assert "new THREE.ShapeGeometry(shapes)" in source
    assert "createFloorGeometry(sceneData.floorplan, widthCm, depthCm)" in source


def test_dxf_wall_mass_is_extruded_before_segment_fallback() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert "function buildWallMass" in source
    assert "new THREE.ExtrudeGeometry" in source
    assert "floorplan?.wall_polys || []" in source
    assert "const builtWallMass =" in source
    assert "? buildWallMass(" in source
    assert "if (!builtWallMass && !singleRoomMode" in source
    assert 'roompilotWallHeightAxis = "z"' in source
    assert 'heightAxis === "z"' in source
    assert '"door-wall-header"' in source
    assert '"window-wall-sill"' in source
    assert '"window-wall-header"' in source
    assert "function buildWallMassTopCaps" in source
    assert "new THREE.ShapeGeometry(shape)" in source
    assert '"continuous-wall-mass-top-cap"' in source
    assert "buildWallMassTopCaps(" in source
    assert "buildContinuousWallTopCaps(" not in source


def test_orthographic_dollhouse_avoids_gtao_projection_artifacts() -> None:
    source = VIEWER.read_text(encoding="utf-8")

    assert '["walk", "orbit"].includes(mode)' in source
    assert '["walk", "orbit"].includes(viewMode.mode)' in source
    assert "gtaoRequested" in source
    assert "samples: 6" in source
    assert 'gtaoPass?.enabled ? "GTAO" : "接觸陰影"' in source
