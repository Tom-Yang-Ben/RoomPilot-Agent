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


def test_floor_slab_ring_expands_outward_to_cover_wall_bands_and_thresholds() -> None:
    """基底樓板外擴:兩個相距 26.9cm 的 region 外擴 14cm 後必須交疊,
    蓋住牆帶與門檻(feedback.png 的地板破口);順/逆時針環都要向外。"""
    result = run_workflow_script(
        f"""
        import {{ expandedFloorSlabRing }} from {json.dumps(VISUAL_MODULE.as_uri())};
        const ccw = expandedFloorSlabRing([[0, 0], [100, 0], [100, 80], [0, 80]], 14);
        const cw = expandedFloorSlabRing([[0, 0], [0, 80], [100, 80], [100, 0]], 14);
        const untouched = expandedFloorSlabRing([[0, 0], [100, 0], [100, 80], [0, 80]], 0);
        console.log(JSON.stringify({{ ccw, cw, untouched }}));
        """
    )

    def bounds(ring):
        xs = [p[0] for p in ring]
        zs = [p[1] for p in ring]
        return min(xs), max(xs), min(zs), max(zs)

    for key in ("ccw", "cw"):
        min_x, max_x, min_z, max_z = bounds(result[key])
        assert (min_x, max_x, min_z, max_z) == (-14, 114, -14, 94), key
    assert bounds(result["untouched"]) == (0, 100, 0, 80)
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
    """viewer 內聯 buildSegmentWalls:牆段切分、窗上下補實、踢腳板與每段頂蓋
    直接建 mesh。純函式層(scene_shell_geometry)保留同等行為供 node 單測。"""
    shell_module = ROOT / "backend" / "server" / "static" / "scene_shell_geometry.js"
    result = run_workflow_script(
        f"""
        import {{ buildSceneModel, shellConfig }} from {json.dumps(shell_module.as_uri())};
        const model = buildSceneModel({{
          walls: [{{ id: "wall-1", start: {{x: -200, z: 0}}, end: {{x: 200, z: 0}} }}],
          windows: [{{
            id: "w-1", host_wall_id: "wall-1", width_cm: 100,
            sill_height_cm: 90, height_cm: 120,
            start: {{x: -50, z: 0}}, end: {{x: 50, z: 0}},
          }}],
        }}, shellConfig({{}}));
        const roles = model.boxes.map((box) => box.role);
        const cap = model.boxes.find((box) => box.role === "top-cap");
        console.log(JSON.stringify({{ roles, capSize: cap.size, capCenterY: cap.center[1] }}));
        """
    )
    assert result["roles"].count("wall-section") == 2
    assert "window-glass" in result["roles"]
    assert "window-sill-infill" in result["roles"]
    assert "window-head-infill" in result["roles"]
    assert result["roles"].count("top-cap") == 1
    assert result["capSize"][1] == 2.5
    assert result["capCenterY"] == 281.25

    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    segment_walls = source.split("function buildSegmentWalls", 1)[1].split(
        "function buildConfirmedDoorLeaves", 1
    )[0]
    assert 'roompilotArchitecturalDetail = "baseboard"' in segment_walls
    assert "const topCap = new THREE.Mesh(" in segment_walls
    assert "wallHeight + 1.25" in segment_walls
    assert "roomGroupRef.add(registerWall(wallMesh, { segment, exteriorSideSign }))" in segment_walls


def test_confirmed_step4_wall_junctions_fill_only_micro_gaps_outside_openings() -> None:
    """已確認牆端點間 ≤ max(36, 2·牆厚) 的微縫以橋接牆補上;超過門檻的
    大縫(真實通道)不得補。橋接為 SceneModel 的 junction-fill 盒。"""
    shell_module = ROOT / "backend" / "server" / "static" / "scene_shell_geometry.js"
    result = run_workflow_script(
        f"""
        import {{ buildSceneModel, shellConfig }} from {json.dumps(shell_module.as_uri())};
        const cfg = shellConfig({{}});
        const plan = (gapCm) => ({{
          walls: [
            {{ id: "wall-a", start: {{x: -300, z: 0}}, end: {{x: -gapCm / 2, z: 0}} }},
            {{ id: "wall-b", start: {{x: gapCm / 2, z: 0}}, end: {{x: 300, z: 0}} }},
          ],
        }});
        const fills = (gapCm) => buildSceneModel(plan(gapCm), cfg).boxes
          .filter((box) => box.role === "junction-fill");
        const micro = fills(20);
        console.log(JSON.stringify({{
          micro: micro.length,
          detail: micro[0]?.meta?.detail || null,
          wide: fills(80).length,
        }}));
        """
    )
    assert result["micro"] == 1
    assert result["detail"] == "confirmed-wall-junction-fill"
    assert result["wide"] == 0

    shell = shell_module.read_text(encoding="utf-8")
    assert "junction: Object.freeze({ minGapCm: 0.8, maxGapFactor: 2, maxGapFloorCm: 36 })" in shell
    assert "const touchesOpening" in shell


def test_window_frames_are_flush_and_do_not_zfight_with_wall_sections() -> None:
    """補實件以 frameAllowance 讓出框位、厚度內縮 2·epsilon 防 z-fighting;
    框件貼齊牆面(faceOffset 0),玻璃盒由 SceneModel 置中於開口線。"""
    shell_module = ROOT / "backend" / "server" / "static" / "scene_shell_geometry.js"
    result = run_workflow_script(
        f"""
        import {{ windowPieces, shellConfig }} from {json.dumps(shell_module.as_uri())};
        const pieces = windowPieces({{
          id: "w-1", sill_height_cm: 90, height_cm: 120,
          start: {{x: 0, z: 0}}, end: {{x: 150, z: 0}},
        }}, shellConfig({{}}), {{ kind: "window" }});
        console.log(JSON.stringify(pieces));
        """
    )
    by_role = {piece["role"]: piece for piece in result}
    sill = by_role["window-sill-infill"]
    head = by_role["window-head-infill"]
    glass = by_role["window-glass"]
    assert sill["size"][1] == 89.4  # 90 - frameAllowance 0.6
    assert head["center"][1] == 245.3  # (210 + 0.6 + 280) / 2
    assert sill["size"][2] == 11.6  # 12 - 2·epsilon
    assert glass["center"] == [75, 150, 0]
    assert glass["size"][2] == 2

    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    opening_builder = source.split("function buildOpeningAssembly", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]
    assert "const frameDepth = Math.max(Number(anchor.wallThickness || 12) + 0.4, 4.2)" in opening_builder
    assert "const faceOffset = 0" in opening_builder
    assert "frame.position.set(x, y, faceOffset)" in opening_builder
    assert 'roompilotArchitecturalDetail = "flush-window-sill"' in opening_builder


def test_all_confirmed_walls_use_room_materials_without_an_exterior_override() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    wall_builder = source.split("function buildSegmentWalls", 1)[1].split(
        "function buildConfirmedDoorLeaves", 1
    )[0]
    resolver = source.split("function wallMaterialResolver", 1)[1].split(
        "function polygonShape", 1
    )[0]
    create_room = source.split("function createRoom", 1)[1].split(
        "function buildFloorPlanOverlay", 1
    )[0]

    assert "pointInsideAnyFloorplanRoom" in resolver
    assert "leftInside !== rightInside" in resolver
    assert "wallEndpointTouchesExteriorBounds" in resolver
    assert "function roomOverrideForInteriorPoint" in resolver
    assert "resolveWallMaterial.faceMaterials" in resolver
    assert "const materialForSide = (side)" in resolver
    assert "const adjacentInteriorMaterial = materialForSide(-exteriorSideSign);" in resolver
    assert "positiveSide = adjacentInteriorMaterial;" in resolver
    assert "negativeSide = adjacentInteriorMaterial;" in resolver
    assert "if (exterior && side === exteriorSideSign) return exteriorMaterial;" not in resolver
    assert "return materialForOverride(roomOverrideForInteriorPoint(sample));" in resolver
    assert "resolveWallMaterial.exteriorMaterial" not in resolver
    assert "isExteriorWallSegment(segment, floorplan, wallThickness)" in wall_builder
    assert "exteriorWallOutwardSideSign(segment, floorplan, unitX, unitZ)" in wall_builder
    assert "wallMaterial.faceMaterials(segment, exteriorSideSign)" in wall_builder
    assert "const wallSegments = sceneData.floorplan?.wall_segments || [];" in create_room


def test_room_wall_finish_is_canonical_and_door_headers_share_wall_faces() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    resolver = source.split("function wallMaterialResolver", 1)[1].split(
        "function wallSegmentPoint", 1
    )[0]
    door_leaves = source.split("function buildConfirmedDoorLeaves", 1)[1].split(
        "function buildOpeningAssembly", 1
    )[0]

    assert "const canonicalOverrides = new Map()" in resolver
    assert "const roomOverrides = [...canonicalOverrides.values()]" in resolver
    assert "function roomOverrideForInteriorPoint" in resolver
    assert "roomOverrideForInteriorPoint(sample)" in resolver
    # 門楣(door-header-wall)沿第 4 步牆縫線段建盒:材質經 resolver 的
    # faceMaterials 依線段中點採樣同房間牆面,與相鄰牆共用面材。
    assert "wallMaterial.faceMaterials({ start, end }, 0)" in door_leaves
    assert '"door-header-wall"' in door_leaves


def test_confirmed_step4_door_gap_is_the_single_source_for_step6_wall_and_leaf() -> None:
    architecture = (ROOT / "backend" / "server" / "static" / "scene_architecture.js").read_text(
        encoding="utf-8"
    )
    viewer = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )
    door_leaves = viewer.split("function buildConfirmedDoorLeaves", 1)[1].split(
        "function buildOpeningAssembly", 1
    )[0]

    assert "function confirmedWallGapForDoor" in architecture
    assert "const wallGap = confirmedWallGapForDoor" in architecture
    assert "wall_opening_segment" in architecture
    assert "start: closedLeaf.start" in architecture
    assert "end: closedLeaf.end" in architecture
    assert "closed_leaf_segment: closedLeafSegment" in architecture
    # 門楣與門葉組件優先以第 4 步牆縫線段(wall_opening_segment)定位;
    # 若該門在第 4 步已確認卻無法解析牆縫,退回不可變的 closed_leaf_segment
    # 讓門仍然渲染,不得再整扇門消失。
    assert "const headerSegment = door?.wall_opening_segment || door?.closed_leaf_segment;" in door_leaves
    assert "if (!start || !end) return;" in door_leaves
    # 回歸守門:舊寫法對「step4 已確認但無牆縫」的門直接 return,造成第 6 步門
    # 消失(feedback.png 的 door-1/4/5)。此守衛不得再出現。
    assert (
        "if (door?.step4_confirmed === true && !door?.wall_opening_segment) return;"
        not in door_leaves
    )
    # 但 closed_leaf 退路只建門楣+門葉,永不自行切牆(牆縫仍由第 4 步 wall_segments
    # 決定),否則會與既有牆縫重疊成雙洞。
    assert "openingWallInterval" not in door_leaves

    # 門片本體置於呼叫端給的牆縫錨點;寬=縫寬−0.6cm 門縫、厚=牆厚−1.2cm
    # 且封頂 5cm,不與牆面共面。
    opening_builder = viewer.split("function buildOpeningAssembly", 1)[1].split(
        "function buildStandaloneOpeningAssemblies", 1
    )[0]
    assert "const doorLeafInsetCm = 0.6;" in opening_builder
    assert "Math.max(interval.width - doorLeafInsetCm, 60)" in opening_builder
    assert "Math.min(Number(anchor.wallThickness || 12) - 1.2, 5)" in opening_builder
    assert "* 0.94" not in opening_builder


def test_walk_camera_looks_toward_open_walkable_space_instead_of_a_wall() -> None:
    source = (ROOT / "backend" / "server" / "static" / "scene_viewer.js").read_text(
        encoding="utf-8"
    )

    assert "function findWalkLookTarget" in source
    assert "const target = findWalkLookTarget(spawn, polygon);" in source
    assert "walkPositionBlockedByFurniture(point)" in source


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
    # 工具列保留了依檢視與操作分組的語意結構，仍必須緊鄰主畫布。
    assert canvas_index - hint_index < 1400


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


def test_furniture_selection_skips_lounge_seating_for_kitchen() -> None:
    """扶手椅/躺椅屬起居空間;需求清單夾帶時,廚房選件必須整型別濾掉。"""
    armchair = {
        "furniture_id": "indoor-armchair",
        "name_zh_raw": "布面扶手椅",
        "name_en": "EKTORP armchair",
        "normalized_type": "armchair",
        "has_model": True,
        "size_cm": {"width": 80, "depth": 75, "height": 80},
    }
    chosen, unavailable = choose_furniture_items(
        {"style_id": "scandinavian", "required_furniture": ["armchair"], "space_type": "kitchen"},
        [armchair],
    )

    assert chosen == []
    assert unavailable == []          # 型別在源頭被濾,不是「缺型號」


def test_furniture_selection_rejects_outdoor_models_for_indoor_space() -> None:
    """型錄把庭院躺椅歸在 armchair/sofa 等室內類型;自動選件必須靠名稱記號
    擋下,否則客廳會出現戶外椅。"""
    outdoor = {
        "furniture_id": "outdoor-chaise",
        "name_zh_raw": "全天候可調節戶外露臺泳池躺椅",
        "name_en": "All-weather adjustable outdoor patio pool chaise lounge",
        "normalized_type": "armchair",
        "has_model": True,
        "size_cm": {"width": 90, "depth": 80, "height": 80},
    }
    chosen, unavailable = choose_furniture_items(
        {"style_id": "scandinavian", "required_furniture": ["armchair"], "space_type": "living_room"},
        [outdoor],
    )

    assert chosen == []
    assert unavailable == ["armchair"]


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
