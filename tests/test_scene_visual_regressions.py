import json
from pathlib import Path

from test_scene_workflow import ROOT, run_workflow_script
from backend.server.main import _merge_furniture_catalog
from backend.server.scene_service import (
    catalog_item_matches_type_semantics,
    choose_furniture_items,
)


VISUAL_MODULE = ROOT / "backend" / "server" / "static" / "scene_visual_contracts.js"
SCENE_HTML = ROOT / "backend" / "server" / "static" / "scene.html"


def test_model_scale_hits_catalog_width_depth_and_height() -> None:
    result = run_workflow_script(
        f"""
        import {{ computeExactModelScale }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify(computeExactModelScale(
          {{ x: 2, y: 1, z: 0.5 }},
          {{ width: 160, depth: 200, height: 82 }}
        )));
        """
    )

    assert result == {"x": 80, "y": 82, "z": 400}


def test_all_confirmed_room_regions_share_the_initial_floor_surface() -> None:
    result = run_workflow_script(
        f"""
        import {{ synchronizedFloorRegions }} from {json.dumps(VISUAL_MODULE.as_uri())};
        const regions = synchronizedFloorRegions({{
          room_regions: [
            {{ room_id: "bedroom", exterior: [[-4, -3], [0, -3], [0, 1], [-4, 1]] }},
            {{ room_id: "living", exterior: [[0, -3], [4, -3], [4, 3], [0, 3]] }},
          ],
        }}, 8, 6);
        console.log(JSON.stringify(regions));
        """
    )

    assert [item["room_id"] for item in result] == ["bedroom", "living"]
    assert all(len(item["exterior"]) == 4 for item in result)


def test_door_leaf_rotates_from_the_confirmed_hinge_endpoint() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorLeafTransform }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify(doorLeafTransform({{
          start: {{ x: 100, z: 200 }},
          end: {{ x: 200, z: 200 }},
          opening_direction: "right",
        }})));
        """
    )

    assert result["hinge"] == {"x": 100, "z": 200}
    assert result["leafWidthCm"] == 94
    assert result["leafCenterXCm"] == 47
    assert result["closedRotationYRad"] == 0
    assert result["swingRotationYRad"] == 0


def test_closed_door_leaf_lies_flat_inside_the_doorway() -> None:
    result = run_workflow_script(
        f"""
        import {{ doorLeafTransform }} from {json.dumps(VISUAL_MODULE.as_uri())};
        const transform = doorLeafTransform({{
          start: {{ x: 100, z: 200 }},
          end: {{ x: 180, z: 260 }},
          opening_direction: "right",
        }});
        const wallAngle = Math.atan2(-(260 - 200), 180 - 100);
        const closedAngle = transform.closedRotationYRad + transform.swingRotationYRad;
        const wall = {{ x: Math.cos(wallAngle), z: -Math.sin(wallAngle) }};
        const leaf = {{ x: Math.cos(closedAngle), z: -Math.sin(closedAngle) }};
        console.log(JSON.stringify({{
          parallelError: Math.abs(wall.x * leaf.z - wall.z * leaf.x),
          directionDot: wall.x * leaf.x + wall.z * leaf.z,
          swingDegrees: Math.abs(transform.swingRotationYRad) * 180 / Math.PI,
        }}));
        """
    )

    assert result["parallelError"] < 1e-9
    assert result["directionDot"] > 0.999999
    assert result["swingDegrees"] == 0


def test_3d_drag_preserves_the_user_position_after_backend_validation() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert 'fetch("/api/scene/validate"' in source
    assert "item: { ...item, position_cm: positionCm, rotation_y_deg: rotationDeg }" in source
    assert 'fetch("/api/scene/layout"' not in source
    assert "wallFaceSnapOffset" not in source


def test_3d_drag_and_rotation_notify_the_project_autosave_boundary() -> None:
    viewer = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    controller = (ROOT / "backend" / "server" / "static" / "scene_v2.js").read_text(
        encoding="utf-8"
    )

    assert "{ onSceneChange = null, onObjectSelect = null } = {}" in viewer
    assert "notifySceneChange(item)" in viewer
    assert "onSceneChange: (item) => {" in controller
    assert 'scheduleSave("white_model_3d")' in controller
    assert "onSceneChange: () => markRealisticSceneEdited()" in controller
    mark_body = controller.split("function markRealisticSceneEdited()", 1)[1].split(
        "function activePanelName", 1
    )[0]
    assert 'state.workflow.invalidateFrom("realistic_3d")' in mark_body
    assert 'scheduleSave("realistic_3d")' in mark_body


def test_formal_3d_columns_use_confirmed_rectangular_dimensions_and_rotation() -> None:
    viewer = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert 'import { columnGeometryDescriptor } from "./scene_structure_geometry.js' in viewer
    assert "minimumDimensionCm: 10" in viewer
    assert "minimumDimensionCm: 12" not in viewer
    assert "geometry.widthCm, geometry.heightCm, geometry.depthCm" in viewer
    assert "mesh.rotation.y = -THREE.MathUtils.degToRad(geometry.rotationDeg)" in viewer


def test_upholstered_storage_bed_is_still_a_real_bed() -> None:
    assert catalog_item_matches_type_semantics(
        {
            "normalized_type": "bed",
            "name_en": "IDANAS Upholstered storage bed - beige 160x200 cm",
            "size_cm": {"width": 160, "depth": 200, "height": 49},
        },
        "bed",
    ) is True


def test_full_size_loft_bed_is_still_a_real_bed() -> None:
    assert catalog_item_matches_type_semantics(
        {
            "normalized_type": "bed",
            "name_en": "Dcraft Berdine Metal Loft Bed, Full Size",
            "size_cm": {"width": 199.4, "depth": 200, "height": 200},
        },
        "bed",
    ) is True


def test_walk_camera_is_clamped_inside_room_and_topdown_has_plan_labels() -> None:
    result = run_workflow_script(
        f"""
        import {{ clampWalkPosition, viewPresentation }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify({{
          clamped: clampWalkPosition({{ x: 800, y: 400, z: -900 }}, {{ widthCm: 400, depthCm: 300, wallHeight: 270 }}),
          dollhouse: viewPresentation("dollhouse"),
          walk: viewPresentation("walk"),
          topdown: viewPresentation("topdown"),
        }}));
        """
    )

    assert result["clamped"] == {"x": 175, "y": 165, "z": -125}
    assert result["dollhouse"]["hideOccludingWalls"] is False
    assert result["dollhouse"]["fadeExteriorWalls"] is False
    assert result["walk"]["hideOccludingWalls"] is False
    assert result["walk"]["fadeExteriorWalls"] is False
    assert result["topdown"]["hideOccludingWalls"] is False
    assert result["topdown"]["showFurniturePlanLabels"] is True
    assert result["topdown"]["walls"] == "flattened"


def test_walk_camera_finds_a_nearby_valid_spawn_when_the_default_is_on_a_wall() -> None:
    result = run_workflow_script(
        f"""
        import {{ findNearestWalkablePosition }} from {json.dumps(VISUAL_MODULE.as_uri())};
        const spawn = findNearestWalkablePosition(
          {{ x: 0, y: 145, z: 297.68 }},
          {{ widthCm: 966.82, depthCm: 1063.16, wallHeight: 270 }},
          (point) => Math.abs(point.x) >= 20,
        );
        console.log(JSON.stringify(spawn));
        """
    )

    assert result is not None
    assert abs(result["x"]) >= 20
    assert result["z"] == 297.68
    assert result["y"] == 165


def test_walk_view_supports_click_to_move_and_continuous_first_person_navigation() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert "function setWalkDestinationFromPointer" in source
    assert 'viewMode.mode !== "walk"' in source
    assert "walkDestination" in source
    assert "walkMarker.visible = true" in source
    assert "function walkPositionBlocked" in source
    assert "function walkPositionInsideFloor" in source
    assert "anchorPosition: perspectiveCamera.position.clone()" in source
    assert "perspectiveCamera.position.copy(walkLookState.anchorPosition)" in source
    assert "const WALK_MAX_PITCH_RAD = THREE.MathUtils.degToRad(18)" in source
    assert "perspectiveCamera.up.set(0, 1, 0)" in source
    assert "前方是牆面" in source
    assert "controls.enableRotate = true" in source
    assert "walkKeys.add" in source


def test_segment_walls_create_openings_trim_and_real_top_caps() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    wall_builder = source.split("function buildSegmentWalls", 1)[1].split(
        "function buildStructuralMembers", 1
    )[0]

    assert "const openingIntervals" in wall_builder
    assert "addWallSection(cursor, interval.from, 0, wallHeight)" in wall_builder
    assert "buildOpeningAssembly" in wall_builder
    assert 'roompilotArchitecturalDetail = "baseboard"' in wall_builder
    assert "const topCap = new THREE.Mesh(" in wall_builder
    assert "roomGroupRef.add(topCap)" in wall_builder


def test_window_frames_are_flush_and_do_not_zfight_with_wall_sections() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    wall_builder = source.split("function buildSegmentWalls", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]
    opening_builder = source.split("function buildOpeningAssembly", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]
    standalone_builder = source.split("function buildStandaloneOpeningAssemblies", 1)[1].split(
        "function buildStructuralMembers", 1
    )[0]

    assert "const frameAllowanceCm = 0.6" in wall_builder
    assert "Math.max(0, sillHeight - frameAllowanceCm)" in wall_builder
    assert "wallHeight - openingHeight - frameAllowanceCm" in wall_builder
    assert "wallThickness" in wall_builder
    assert "const faceOffset = Math.max(Number(anchor.wallThickness || 12) / 2 + 0.35, 6)" in opening_builder
    assert "glass.position.z = faceOffset - frameDepth / 2 - 0.08" in opening_builder
    assert "frame.position.set(x, y, faceOffset)" in opening_builder
    assert 'roompilotArchitecturalDetail = "flush-window-sill"' in opening_builder
    assert "Math.max(0, sillHeight - frameAllowanceCm)" in standalone_builder


def test_exterior_walls_keep_fixed_material_and_interior_junctions_do_not_protrude() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    wall_builder = source.split("function buildSegmentWalls", 1)[1].split(
        "function buildOpeningAssembly", 1
    )[0]
    resolver = source.split("function wallMaterialResolver", 1)[1].split(
        "function polygonShape", 1
    )[0]
    create_room = source.split("function createRoom", 1)[1].split(
        "function buildFloorPlanOverlay", 1
    )[0]

    assert "isExteriorWallSegment(segment, sceneData.floorplan)" in resolver
    assert "pointInsideAnyFloorplanRoom" in resolver
    assert "leftInside !== rightInside" in resolver
    assert "wallEndpointTouchesExteriorBounds" in resolver
    assert "resolveWallMaterial.exteriorMaterial = exteriorMaterial" in resolver
    assert "roompilotWallSurfaceRole = \"exterior\"" in resolver
    assert "isExteriorWallSegment(segment, floorplan, wallThickness)" in wall_builder
    assert "exteriorWallOutwardSideSign(segment, floorplan, unitX, unitZ)" in wall_builder
    assert "wallSectionFaceMaterials(sectionMaterial, exteriorSurfaceMaterial, exteriorSideSign)" in wall_builder
    assert "interiorWallJunctionInsets(segment, exteriorSegments, wallThickness)" in wall_builder
    assert "const sectionMin" in wall_builder
    assert "const sectionMax" in wall_builder
    assert "new THREE.BoxGeometry(capLength, 2.5, wallThickness)" in wall_builder
    assert "Number(start.x) + unitX * capCenter" in wall_builder
    assert "sceneData.floorplan," in create_room


def test_circulation_route_starts_at_entrance_and_uses_walkable_grid() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert "function buildCirculationRoute" in source
    assert "function findCirculationPath" in source
    assert "function simplifyCirculationPath" in source
    assert 'label: "玄關"' in source
    assert "walkPositionInsideFloor" in source
    assert "walkPositionBlocked" in source
    assert 'roompilotCirculation = true' in source


def test_dollhouse_keeps_all_walls_visible_and_orbit_controls_enabled() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    dollhouse = source.split('} else if (mode === "dollhouse") {', 1)[1].split(
        "} else {", 1
    )[0]
    visibility = source.split("function updateWallVisibility()", 1)[1].split(
        "function onResize()", 1
    )[0]

    assert "controls.enabled = true" in dollhouse
    assert "controls.enableRotate = true" in dollhouse
    assert "controls.enablePan = true" in dollhouse
    assert "controls.enableZoom = true" in dollhouse
    assert "wall.visible = true" in visibility
    assert "wall.visible = !shouldHide" not in visibility
    assert "wallBlocksRoom" not in visibility
    assert "wallTooClose" not in visibility


def test_generic_glb_material_gets_a_safe_furniture_role_fallback() -> None:
    result = run_workflow_script(
        f"""
        import {{ fallbackMaterialRole }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify({{
          bed: fallbackMaterialRole("bed"),
          bookcase: fallbackMaterialRole("bookcase"),
          lamp: fallbackMaterialRole("floor-lamp"),
          unknown: fallbackMaterialRole("sculpture"),
        }}));
        """
    )

    assert result == {"bed": "fabric", "bookcase": "wood", "lamp": "metal", "unknown": None}


def test_style_pack_preserves_real_texture_color_detail_with_subtle_tint() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    room_creation = source.split("function createRoom(sceneData)", 1)[1].split(
        "const wallSegments", 1
    )[0]

    assert "map: colorMap" in source
    assert "!floorMaterial.userData.roompilotImageSurface" not in room_creation
    assert "!wallMaterial.userData.roompilotImageSurface" not in room_creation
    assert "applySurfaceTint(floorMaterial, floorColor)" in room_creation
    assert "applySurfaceTint(wallMaterial, wallColor)" in room_creation
    assert "surfaceTint(" in source


def test_material_schemes_explain_surface_and_furniture_changes() -> None:
    material_module = ROOT / "backend" / "server" / "static" / "scene_material_schemes.js"
    result = run_workflow_script(
        f"""
        import {{ generateMaterialSchemes }} from {json.dumps(material_module.as_uri())};
        const schemes = generateMaterialSchemes({{
          style: {{ style_id: "scandinavian" }},
          style_card: {{ palette_hex: ["#ffffff", "#aa8855", "#333333"] }},
          design_choices: {{ wall_option: "原始白牆", floor_option: "原始地板" }},
          scene_objects: [{{ furniture_id: "bed-1", normalized_type: "bed", material_slots: ["seat_fabric", "wood_frame"] }}],
        }}, {{ surfaces: [{{ surface_id: "oak", category: "wood" }}] }});
        console.log(JSON.stringify(schemes.map((scheme) => scheme.changeSummary)));
        """
    )

    assert len(result) == 3
    assert all(item["wall"]["before"] == "原始白牆" for item in result)
    assert all(item["floor"]["before"] == "原始地板" for item in result)
    assert all(item["furnitureCount"] == 1 for item in result)
    assert all(set(item["furnitureRoles"]) == {"fabric", "wood"} for item in result)


def test_view_mode_hint_is_part_of_viewer_and_adjacent_to_canvas() -> None:
    html = SCENE_HTML.read_text(encoding="utf-8")
    viewer = html.split('id="white-model-3d-step"', 1)[1]
    hint_index = viewer.index('class="rp-viewer-toolbar"')
    canvas_index = viewer.index('id="white-model-viewer"')

    assert hint_index < canvas_index
    assert canvas_index - hint_index < 1200


def test_catalog_does_not_merge_same_named_bed_and_cabinet_models() -> None:
    merged = _merge_furniture_catalog(
        [
            {
                "furniture_id": "bed-model",
                "name_en": "Movian Morava",
                "name_zh_raw": "床 - Movian Morava",
                "normalized_type": "bed",
                "size_cm": {"width": 160, "depth": 200, "height": 82},
            }
        ],
        [
            {
                "furniture_id": "cabinet-model",
                "name_en": "Movian Morava",
                "name_zh_raw": "櫃體 - Movian Morava",
                "normalized_type": "cabinet-cupboard",
                "size_cm": {"width": 94, "depth": 59, "height": 212},
            }
        ],
    )

    assert {item["normalized_type"] for item in merged} == {"bed", "cabinet-cupboard"}
    assert len(merged) == 2


def test_bed_selection_rejects_wardrobe_and_drawer_models() -> None:
    chosen, unavailable = choose_furniture_items(
        {"style_id": "scandinavian", "required_furniture": ["bed"]},
        [
            {
                "furniture_id": "wrong-wardrobe",
                "name_en": "Movian Morava 4-Door Wardrobe with Mirrors",
                "normalized_type": "bed",
                "has_model": True,
                "size_cm": {"width": 200, "depth": 200, "height": 212},
            },
        ],
    )

    assert chosen == []
    assert unavailable == ["bed"]
