from __future__ import annotations

import json

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "backend" / "server" / "static"
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


def test_open_door_leaves_snap_to_two_distinct_existing_wall_gaps() -> None:
    result = run_workflow_script(
        f"""
        import {{
          doorOpeningForWallTopology,
          openingWallInterval,
        }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{
            id: "wall-2",
            start: {{x: -486.99, z: 87.11}},
            end: {{x: 11.11, z: 87.11}},
            thickness_cm: 22.22,
          }},
          {{
            id: "wall-11",
            start: {{x: 0, z: 333.24}},
            end: {{x: 0, z: 222.16}},
            thickness_cm: 22.22,
          }},
          {{
            id: "wall-15",
            start: {{x: 0, z: 112.25}},
            end: {{x: 0, z: 63.14}},
            thickness_cm: 19.88,
          }},
          {{
            id: "wall-17",
            start: {{x: 0, z: -47.93}},
            end: {{x: 0, z: -274.77}},
            thickness_cm: 22.22,
          }},
        ];
        const doors = [
          {{
            id: "door-2",
            host_wall_id: "wall-2",
            width_cm: 113.41,
            start: {{x: -9.94, z: 61.39}},
            end: {{x: -123.35, z: 61.39}},
          }},
          {{
            id: "door-3",
            host_wall_id: "wall-2",
            width_cm: 104.06,
            start: {{x: -19.29, z: 111.67}},
            end: {{x: -123.35, z: 111.67}},
          }},
        ];
        const openings = doors.map((door) => doorOpeningForWallTopology(walls, door, 22));
        console.log(JSON.stringify({{
          openings,
          cutsWrongWall: openings.map(
            (opening) => Boolean(openingWallInterval(walls[0], opening, 22, 68)),
          ),
        }}));
        """
    )

    assert result["cutsWrongWall"] == [False, False]
    assert result["openings"][0]["topology_gap"] is True
    assert result["openings"][1]["topology_gap"] is True
    assert result["openings"][0]["start"] == {"x": 0, "z": 63.14}
    assert result["openings"][0]["end"] == {"x": 0, "z": -47.93}
    assert result["openings"][1]["start"] == {"x": 0, "z": 222.16}
    assert result["openings"][1]["end"] == {"x": 0, "z": 112.25}


def test_gap_window_has_no_usable_span_inside_the_split_host_wall() -> None:
    result = run_workflow_script(
        f"""
        import {{ openingWallInterval }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const splitHostWall = {{
          id: "wall-6",
          start: {{ x: -11.11, z: -524.4 }},
          end: {{ x: 171.3, z: -524.4 }},
        }};
        const floorWindow = {{
          id: "window-1",
          host_wall_id: "wall-6",
          start: {{ x: 171.3, z: -524.4 }},
          end: {{ x: 308.1, z: -524.4 }},
          width_cm: 136.8,
          sill_height_cm: 0,
          height_cm: 262,
        }};
        const embeddedWindow = {{
          id: "window-embedded",
          host_wall_id: "wall-6",
          start: {{ x: 20, z: -524.4 }},
          end: {{ x: 120, z: -524.4 }},
          width_cm: 100,
        }};
        console.log(JSON.stringify({{
          gap: openingWallInterval(splitHostWall, floorWindow, 12, 50),
          embedded: openingWallInterval(splitHostWall, embeddedWindow, 12, 50),
        }}));
        """
    )

    assert result["gap"] is None
    assert abs(result["embedded"]["to"] - result["embedded"]["from"] - 100) < 1e-9


def test_split_wall_openings_use_the_standalone_3d_assembly_fallback() -> None:
    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")

    assert "const missingWindows = windowSegments.filter" in viewer
    assert "openingWallInterval(segment, opening, wallThickness, 50)" in viewer
    assert "missingDoors,\n        missingWindows," in viewer


def test_opening_edges_do_not_receive_wall_junction_caps() -> None:
    result = run_workflow_script(
        f"""
        import {{ wallEndpointBordersOpening }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const window = {{
          start: {{ x: 171.3, z: -524.4 }},
          end: {{ x: 308.1, z: -524.4 }},
        }};
        console.log(JSON.stringify({{
          openingEdge: wallEndpointBordersOpening(
            {{ x: 171.3, z: -524.4 }},
            [window],
            12,
          ),
          realCorner: wallEndpointBordersOpening(
            {{ x: -11.11, z: -524.4 }},
            [window],
            12,
          ),
        }}));
        """
    )

    assert result == {"openingEdge": True, "realCorner": False}

    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    assert "wallEndpointBordersOpening(endpoint, allOpenings, wallThickness)" in viewer
    assert "new THREE.BoxGeometry(length, 2.5, wallThickness)" in viewer
    assert "openingWidth + 1.2" in viewer
    assert "openingWidth + wallThickness * 2.1" not in viewer


def test_gap_window_uses_its_own_host_wall_for_surface_material() -> None:
    result = run_workflow_script(
        f"""
        import {{ wallSegmentForOpening }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{
            id: "wall-6",
            start: {{ x: -11.11, z: -524.4 }},
            end: {{ x: 171.3, z: -524.4 }},
            material_id: "dark-wall",
          }},
          {{
            id: "wall-14",
            start: {{ x: 475.88, z: 190.59 }},
            end: {{ x: 475.88, z: 28.07 }},
            material_id: "white-wall",
          }},
        ];
        const window = {{
          id: "window-5",
          host_wall_id: "wall-14",
          start: {{ x: 475.88, z: 28.07 }},
          end: {{ x: 475.88, z: -40.92 }},
        }};
        console.log(JSON.stringify(wallSegmentForOpening(walls, window, 12)));
        """
    )

    assert result["id"] == "wall-14"
    assert result["material_id"] == "white-wall"

    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    assert "wallSegmentForOpening(segments, opening, wallThickness)" in viewer
    assert "wallMaterial(hostSegment || segments[0] || {})" in viewer
    assert "wallMaterial(segments[0] || {})" not in viewer


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
