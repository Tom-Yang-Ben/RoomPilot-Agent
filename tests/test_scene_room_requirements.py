from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/server/static/scene_room_requirements.js").read_text(
    encoding="utf-8"
)
SCENE = (ROOT / "backend/server/static/scene_v2.js").read_text(encoding="utf-8")
VIEWER = (ROOT / "backend/server/static/scene_viewer.js").read_text(encoding="utf-8")


def test_room_requirement_contract_is_room_scoped_and_versioned() -> None:
    assert "ROOM_REQUIREMENTS_SCHEMA_VERSION" in SOURCE
    assert "normalizeRoomRequirements" in SOURCE
    assert "roomRequirements" in SOURCE
    assert "wallOverrides" in SOURCE
    assert "wallSurfaceIds" in SOURCE
    assert "ceiling" in SOURCE
    assert "airConditioning" in SOURCE


def test_apply_scope_keeps_independent_room_copies() -> None:
    assert "applyRoomFinishScope" in SOURCE
    assert "structuredClone" in SOURCE or "JSON.parse(JSON.stringify" in SOURCE
    assert "same-type" in SOURCE
    assert "selected" in SOURCE
    assert "all" in SOURCE


def test_feasibility_checks_room_geometry_and_openings() -> None:
    assert "evaluateConditionalOption" in SOURCE
    assert "shortSideCm" in SOURCE
    assert "doorClearanceCm" in SOURCE
    assert "doorSwingAreaM2" in SOURCE
    assert "effectiveAreaM2" in SOURCE
    assert "doorPositionConflict" in SOURCE
    assert "opening.room_ids" in SOURCE
    assert "目前尺寸可能無法配置" in SOURCE
    assert "forcePlacement: false" in SOURCE


def test_rag_payload_waits_for_all_room_and_global_confirmations() -> None:
    assert "buildRoomRequirementsPayload" in SOURCE
    assert "allRoomsConfirmed" in SOURCE
    assert "globalConfirmed" in SOURCE
    assert "readyForRag" in SOURCE
    assert "planGeometry" in SOURCE


def test_room_surfaces_flow_into_2d_3d_and_render_payloads() -> None:
    assert "roomSurfaceAssignments" in SCENE
    assert "room_surface_assignments: roomSurfaces" in SCENE
    assert "state.sceneData.surface_overrides = roomSurfaces.map" in SCENE
    assert "room_surface_assignments: roomSurfaceAssignments()" in SCENE
    assert 'id="layout-room-materials"' in (
        ROOT / "backend/server/static/scene.html"
    ).read_text(encoding="utf-8")
    assert "createRoomCeilingOverrides" in VIEWER
    assert "roompilotCeilingOverride" in VIEWER
    assert "override.wall_overrides?.[surfaceId]" in VIEWER
    apply_style = SCENE.split("async function applyStylePackToScene", 1)[1].split(
        "async function applySurfaceOverrides", 1
    )[0]
    assert "roomSurfaceOverrides" in apply_style
    assert "state.sceneData.surface_overrides = roomSurfaceOverrides" in apply_style


def test_agent_selection_receives_all_rooms_in_one_request() -> None:
    auto_layout = SCENE.split("async function autoLayoutFurniture()", 1)[1].split(
        "async function relayoutFurnitureForScheme", 1
    )[0]

    assert auto_layout.count('api("/api/agent/furniture/select"') == 1
    assert "rooms: roomPlans.map" in auto_layout
    assert "questionnaire: requirementsPayload" in auto_layout
    assert "specsAllowedByRoomFeasibility" in auto_layout
