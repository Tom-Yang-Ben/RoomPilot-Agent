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


def test_detected_wall_spans_remain_the_only_two_distinct_door_openings() -> None:
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
            confirmed: true,
            host_wall_id: "wall-2",
            width_cm: 113.41,
            start: {{x: -9.94, z: 61.39}},
            end: {{x: -123.35, z: 61.39}},
            swing_end: {{x: -9.94, z: -52.02}},
          }},
          {{
            id: "door-3",
            confirmed: true,
            host_wall_id: "wall-2",
            width_cm: 104.06,
            start: {{x: -19.29, z: 111.67}},
            end: {{x: -123.35, z: 111.67}},
            swing_end: {{x: -19.29, z: 215.73}},
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

    assert result["cutsWrongWall"] == [True, True]
    assert [opening["topology_gap"] for opening in result["openings"]] == [False, False]
    assert [opening["opening_source"] for opening in result["openings"]] == ["recognised_wall_span"] * 2
    assert result["openings"][0]["start"] == {"x": -9.94, "z": 61.39}
    assert result["openings"][0]["end"] == {"x": -123.35, "z": 61.39}
    assert result["openings"][1]["start"] == {"x": -19.29, "z": 111.67}
    assert result["openings"][1]["end"] == {"x": -123.35, "z": 111.67}


def test_swing_arc_never_replaces_the_recognised_wall_span() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{ id: "wall-horizontal", start: {{x: 0, z: 0}}, end: {{x: 420, z: 0}} }},
          {{ id: "wall-left", start: {{x: 500, z: -260}}, end: {{x: 500, z: -120}} }},
          {{ id: "wall-right", start: {{x: 500, z: 0}}, end: {{x: 500, z: 110}} }},
        ];
        const doors = [
          {{
            id: "door-horizontal",
            start: {{x: 120, z: 0}}, end: {{x: 240, z: 0}},
            swing_end: {{x: 120, z: -120}}, width_cm: 120,
          }},
          {{
            id: "door-vertical-gap",
            start: {{x: 500, z: 0}}, end: {{x: 380, z: 0}},
            swing_end: {{x: 500, z: -120}}, width_cm: 120,
          }},
        ];
        const openings = doors.map((door) => doorOpeningForWallTopology(walls, door, 12));
        const summary = openings.map((opening) => ({{
          id: opening.id,
          start: opening.start,
          end: opening.end,
          source: opening.opening_source,
          topologyGap: Boolean(opening.topology_gap),
          host: opening.host_wall_id || null,
        }}));
        console.log(JSON.stringify(summary));
        """
    )

    assert result == [
        {
            "id": "door-horizontal",
            "start": {"x": 120, "z": 0},
            "end": {"x": 240, "z": 0},
            "source": "recognised_wall_span",
            "topologyGap": False,
            "host": "wall-horizontal",
        },
        {
            "id": "door-vertical-gap",
            "start": {"x": 500, "z": 0},
            "end": {"x": 380, "z": 0},
            "source": "recognised_wall_span",
            "topologyGap": False,
            "host": "wall-horizontal",
        },
    ]


def test_step6_closed_leaf_uses_step4_hinge_and_swing_endpoint() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const opening = doorOpeningForWallTopology(
          [{{ id: "wall-1", start: {{x: 0, z: 0}}, end: {{x: 180, z: 0}} }}],
          {{
            id: "door-2",
            start: {{x: 80, z: 0}}, end: {{x: 0, z: 0}},
            swing_end: {{x: 80, z: 80}}, width_cm: 80,
          }},
          12,
        );
        console.log(JSON.stringify({{
          id: opening.id,
          opening: {{ start: opening.start, end: opening.end }},
          openLeaf: opening.door_leaf_segment,
          closedLeaf: opening.closed_leaf_segment,
        }}));
        """
    )

    assert result == {
        "id": "door-2",
        "opening": {"start": {"x": 80, "z": 0}, "end": {"x": 0, "z": 0}},
        "openLeaf": {"start": {"x": 80, "z": 0}, "end": {"x": 0, "z": 0}},
        "closedLeaf": {"start": {"x": 80, "z": 0}, "end": {"x": 80, "z": 80}},
    }


def test_confirmed_step4_door_keeps_the_wall_gap_and_only_moves_the_leaf() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const opening = doorOpeningForWallTopology(
          [
            {{ id: "top-wall", start: {{x: 0, z: 0}}, end: {{x: 300, z: 0}} }},
            {{ id: "left-wall", start: {{x: 80, z: 0}}, end: {{x: 80, z: 100}} }},
            {{ id: "right-wall", start: {{x: 180, z: 100}}, end: {{x: 180, z: 0}} }},
          ],
          {{
            id: "door-2", step4_confirmed: true, width_cm: 100,
            start: {{x: 80, z: 0}}, end: {{x: 180, z: 0}},
            swing_end: {{x: 80, z: 100}},
          }},
          12,
        );
        console.log(JSON.stringify({{
          cutsWall: !opening.step4_skip_wall_cut,
          closedLeaf: opening.closed_leaf_segment,
          source: opening.opening_source,
        }}));
        """
    )

    assert result == {
        "cutsWall": False,
        "closedLeaf": {"start": {"x": 80, "z": 0}, "end": {"x": 80, "z": 100}},
        "source": "confirmed_wall_gap",
    }


def test_detected_host_span_wins_over_open_leaf_arc() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{ id: "wall-host", start: {{x: -11, z: 517}}, end: {{x: 169, z: 517}} }},
          {{ id: "wall-end", start: {{x: 0, z: 271}}, end: {{x: 0, z: 370}} }},
        ];
        const door = {{
          id: "door-1", width_cm: 128,
          start: {{x: 8.64, z: 489.82}}, end: {{x: 135.38, z: 489.82}},
          swing_end: {{x: 8.64, z: 363.095}},
        }};
        const opening = doorOpeningForWallTopology(walls, door, 12);
        console.log(JSON.stringify({{
          source: opening.opening_source,
          host: opening.host_wall_id,
          start: opening.start,
          end: opening.end,
        }}));
        """
    )

    assert result == {
        "source": "recognised_wall_span",
        "host": "wall-host",
        "start": {"x": 8.64, "z": 489.82},
        "end": {"x": 135.38, "z": 489.82},
    }


def test_unresolved_vision_host_never_cuts_a_second_wrong_wall_opening() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const opening = doorOpeningForWallTopology([
          {{ id: "wall-stale", start: {{x: 0, z: 0}}, end: {{x: 0, z: 320}} }},
        ], {{
          id: "door-1", host_wall_id: "wall-stale", width_cm: 90,
          start: {{x: 180, z: 40}}, end: {{x: 270, z: 40}},
          swing_end: {{x: 180, z: 130}},
        }}, 12);
        console.log(JSON.stringify({{
          host: opening.host_wall_id,
          originalHost: opening.original_host_wall_id,
          topologyGap: opening.topology_gap,
          manual: opening.needs_manual_host_confirmation,
          leaf: opening.door_leaf_segment,
        }}));
        """
    )

    assert result == {
        "originalHost": "wall-stale",
        "topologyGap": True,
        "manual": True,
        "leaf": {
            "start": {"x": 180, "z": 40},
            "end": {"x": 270, "z": 40},
        },
    }


def test_persisted_closed_segment_overrides_open_leaf_and_arc_for_manual_correction() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorOpeningForWallTopology }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{ id: "locked-wall", start: {{x: 0, z: 0}}, end: {{x: 0, z: 260}} }},
          {{ id: "open-leaf-wall", start: {{x: 0, z: 100}}, end: {{x: 160, z: 100}} }},
        ];
        const door = {{
          id: "door-locked",
          host_wall_confirmed: true,
          host_wall_id: "locked-wall",
          start: {{x: 0, z: 100}}, end: {{x: 120, z: 100}},
          swing_end: {{x: 0, z: 220}},
          closed_segment: {{
            start: {{x: 0, z: 90}}, end: {{x: 0, z: 210}}, source: "manual_confirmed",
          }},
          width_cm: 120,
        }};
        const opening = doorOpeningForWallTopology(walls, door, 12);
        console.log(JSON.stringify({{
          start: opening.start,
          end: opening.end,
          host: opening.host_wall_id,
          source: opening.closed_segment.source,
        }}));
        """
    )

    assert result == {
        "start": {"x": 0, "z": 90},
        "end": {"x": 0, "z": 210},
        "host": "locked-wall",
        "source": "manual_confirmed",
    }


def test_confirmed_door_keeps_its_confirmed_host_wall_instead_of_nearby_gap() -> None:
    result = run_workflow_script(
        f"""
        import {{
          doorOpeningForWallTopology,
          openingWallInterval,
        }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        const walls = [
          {{
            id: "wall-host",
            start: {{x: 0, z: 0}},
            end: {{x: 500, z: 0}},
          }},
          {{
            id: "gap-left",
            start: {{x: 260, z: -260}},
            end: {{x: 260, z: -140}},
          }},
          {{
            id: "gap-right",
            start: {{x: 260, z: -40}},
            end: {{x: 260, z: 80}},
          }},
        ];
        const door = {{
          id: "door-confirmed",
          confirmed: true,
          host_wall_confirmed: true,
          host_wall_id: "wall-host",
          width_cm: 100,
          start: {{x: 250, z: 24}},
          end: {{x: 350, z: 24}},
        }};
        const opening = doorOpeningForWallTopology(walls, door, 12);
        console.log(JSON.stringify({{
          topologyGap: Boolean(opening.topology_gap),
          hostWallId: opening.host_wall_id,
          hostInterval: openingWallInterval(walls[0], opening, 12, 68),
        }}));
        """
    )

    assert result["topologyGap"] is False
    assert result["hostWallId"] == "wall-host"
    assert result["hostInterval"] is not None


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
    assert "const missingDoors = doorSegments.filter((opening) =>" in viewer
    assert "!renderedOpenings.has(openingId)" in viewer
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
    assert 'roompilotArchitecturalDetail = "wall-junction-seal"' not in viewer
    assert "new THREE.BoxGeometry(capLength, 2.5, wallThickness)" in viewer
    assert "openingWidth + 1.2" not in viewer
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


def test_gap_window_wall_sections_end_flush_with_the_opening() -> None:
    result = run_workflow_script(
        f"""
        import {{ wallSectionSpan }} from {json.dumps(ARCHITECTURE_MODULE.as_uri())};
        console.log(JSON.stringify({{
          exact: wallSectionSpan(0, 162.52, 162.52),
          internalSeam: wallSectionSpan(0, 50, 100),
        }}));
        """
    )

    assert result == {
        "exact": {"from": 0, "to": 162.52},
        "internalSeam": {"from": 0, "to": 50.6},
    }

    viewer = (
        ROOT / "backend" / "server" / "static" / "scene_viewer.js"
    ).read_text(encoding="utf-8")
    wall_builder = viewer.split("function buildSegmentWalls", 1)[1].split(
        "function buildOpeningAssembly", 1
    )[0]
    standalone = viewer.split("function buildStandaloneOpeningAssemblies", 1)[1].split(
        "function buildStructuralMembers", 1
    )[0]

    assert "const span = wallSectionSpan(from, to, length)" in wall_builder
    assert 'roompilotArchitecturalDetail = "wall-junction-seal"' not in wall_builder
    assert "openingWidth + 1.2" not in standalone


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


def test_architectural_openings_have_dedicated_physical_profiles() -> None:
    result = run_workflow_script(
        f"""
        import {{ architecturalPbrProfile }} from {json.dumps(PBR_MODULE.as_uri())};
        console.log(JSON.stringify({{
          door: architecturalPbrProfile("door_leaf"),
          frame: architecturalPbrProfile("window_frame"),
          glass: architecturalPbrProfile("glass"),
        }}));
        """
    )

    assert result["door"]["roughness"] > result["frame"]["roughness"]
    assert result["frame"]["metalness"] > result["door"]["metalness"]
    assert result["glass"]["transmission"] > 0.7

    source = VIEWER.read_text(encoding="utf-8")
    assert "function createArchitecturalMaterial" in source
    assert "wood_cc0_wood_textures_woodfloor039" in source
    assert 'architecturalPbrProfile("glass")' in source


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
