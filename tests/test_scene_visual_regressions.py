import json
from pathlib import Path

from test_scene_workflow import ROOT, run_workflow_script
from roompilot.server.main import _merge_furniture_catalog
from roompilot.server.scene_service import (
    catalog_item_matches_type_semantics,
    choose_furniture_items,
)


VISUAL_MODULE = ROOT / "roompilot" / "server" / "static" / "scene_visual_contracts.js"
SCENE_HTML = ROOT / "roompilot" / "server" / "static" / "scene.html"


def test_model_scale_hits_catalog_width_depth_and_height() -> None:
    result = run_workflow_script(
        f"""
        import {{ computeExactModelScale }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify(computeExactModelScale(
          {{ x: 2, y: 1, z: 0.5 }},
          {{ width: 1.6, depth: 2, height: 0.82 }}
        )));
        """
    )

    assert result == {"x": 0.8, "y": 0.82, "z": 4}


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
          start: {{ x: 1, z: 2 }},
          end: {{ x: 2, z: 2 }},
          opening_direction: "right",
        }})));
        """
    )

    assert result["hinge"] == {"x": 1, "z": 2}
    assert result["leafWidthM"] == 0.94
    assert result["leafCenterXM"] == 0.47
    assert result["closedRotationYRad"] == 0
    assert result["swingRotationYRad"] < 0


def test_3d_wall_snap_commits_the_backend_layout_result() -> None:
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert 'fetch("/api/scene/layout"' in source
    assert "placement_hint_cm" in source
    assert "resolved.position_cm" in source
    assert "wallFaceSnapOffset" not in source


def test_3d_drag_and_rotation_notify_the_project_autosave_boundary() -> None:
    viewer = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    controller = (ROOT / "roompilot" / "server" / "static" / "scene_v2.js").read_text(
        encoding="utf-8"
    )

    assert "{ onSceneChange = null } = {}" in viewer
    assert "notifySceneChange(item)" in viewer
    assert 'onSceneChange: () => scheduleSave("white_model_3d")' in controller
    assert 'onSceneChange: () => scheduleSave("realistic_3d")' in controller


def test_formal_3d_columns_use_confirmed_rectangular_dimensions_and_rotation() -> None:
    viewer = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert 'import { columnGeometryDescriptor } from "./scene_structure_geometry.js' in viewer
    assert "minimumDimensionM: 0.1" in viewer
    assert "minimumDimensionM: 0.12" not in viewer
    assert "geometry.widthM, geometry.heightM, geometry.depthM" in viewer
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


def test_walk_camera_is_clamped_inside_room_and_topdown_has_plan_labels() -> None:
    result = run_workflow_script(
        f"""
        import {{ clampWalkPosition, viewPresentation }} from {json.dumps(VISUAL_MODULE.as_uri())};
        console.log(JSON.stringify({{
          clamped: clampWalkPosition({{ x: 8, y: 4, z: -9 }}, {{ widthM: 4, depthM: 3, wallHeight: 2.7 }}),
          dollhouse: viewPresentation("dollhouse"),
          walk: viewPresentation("walk"),
          topdown: viewPresentation("topdown"),
        }}));
        """
    )

    assert result["clamped"] == {"x": 1.75, "y": 1.65, "z": -1.25}
    assert result["dollhouse"]["hideOccludingWalls"] is False
    assert result["dollhouse"]["fadeExteriorWalls"] is False
    assert result["walk"]["hideOccludingWalls"] is False
    assert result["walk"]["fadeExteriorWalls"] is False
    assert result["topdown"]["hideOccludingWalls"] is False
    assert result["topdown"]["showFurniturePlanLabels"] is True
    assert result["topdown"]["walls"] == "flattened"


def test_walk_view_supports_click_to_move_and_continuous_first_person_navigation() -> None:
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
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
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
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


def test_circulation_route_starts_at_entrance_and_uses_walkable_grid() -> None:
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
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
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
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
    source = (ROOT / "roompilot" / "server" / "static" / "scene_viewer.js").read_text(
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
    material_module = ROOT / "roompilot" / "server" / "static" / "scene_material_schemes.js"
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
    assert canvas_index - hint_index < 900


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
