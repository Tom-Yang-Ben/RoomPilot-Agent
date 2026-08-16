from scripts.static_source_graph import scene_controller_source, scene_viewer_source

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "backend/server/static/scene_room_requirements.js").read_text(
    encoding="utf-8"
)
SCENE = scene_controller_source(ROOT / "backend/server/static")
VIEWER = scene_viewer_source(ROOT / "backend/server/static")
ROOM_REQUIREMENTS = ROOT / "backend/server/static/scene_room_requirements.js"


def _run_room_requirement_helper(script: str) -> dict:
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            f"""
              import {{
                buildSpecialRequestAnswer,
                conditionalOptionId,
                normalizeRoomRequirements,
              }} from {json.dumps(ROOM_REQUIREMENTS.resolve().as_uri())};
              {script}
            """,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_room_requirement_contract_is_room_scoped_and_versioned() -> None:
    assert "ROOM_REQUIREMENTS_SCHEMA_VERSION" in SOURCE
    assert "normalizeRoomRequirements" in SOURCE
    assert "roomRequirements" in SOURCE
    assert "wallOverrides" in SOURCE
    assert "wallSurfaceIds" in SOURCE
    assert "ceiling" in SOURCE
    assert "airConditioning" in SOURCE
    assert "generativeEquipment" in SOURCE
    assert "structuralIntentAcknowledged" in SOURCE


def test_generation_space_requirements_are_versioned_and_preserved() -> None:
    result = _run_room_requirement_helper(
        """
          const model = normalizeRoomRequirements({}, [{
            id: "bath-1", type: "bathroom", label: "Bathroom",
          }]);
          console.log(JSON.stringify(model.roomRequirements["bath-1"].generativeEquipment));
        """
    )

    assert result["required"] is True
    assert result["primaryUse"] is None
    assert result["equipmentDirection"] == []
    assert result["fitStatus"] == "pending"


def test_apply_scope_keeps_independent_room_copies() -> None:
    assert "applyRoomFinishScope" in SOURCE
    assert "structuredClone" in SOURCE or "JSON.parse(JSON.stringify" in SOURCE
    assert "same-type" in SOURCE
    assert "selected" in SOURCE
    assert "all" in SOURCE


def test_normalize_preserves_unassigned_deferred_furniture() -> None:
    result = _run_room_requirement_helper(
        """
          const model = normalizeRoomRequirements({
            unassignedDeferredFurniture: [{
              furniture_id: "loose-chair-1",
              normalized_type: "chair",
              label: "Loose chair",
            }],
          }, [{ id: "room-1", type: "bedroom", label: "Bedroom" }]);
          console.log(JSON.stringify({
            count: model.unassignedDeferredFurniture.length,
            label: model.unassignedDeferredFurniture[0].label,
          }));
        """
    )

    assert result == {"count": 1, "label": "Loose chair"}


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


def test_conditional_option_detection_uses_structured_catalog_fields() -> None:
    result = _run_room_requirement_helper(
        """
          console.log(JSON.stringify({
            tub: conditionalOptionId({
              option_id: "tub",
              label_zh: "保留浴缸",
              rag_tags: ["bathroom", "bathtub"],
              engine_effects: { bath_fixture: "tub" },
            }),
            shower: conditionalOptionId({
              option_id: "shower",
              label_zh: "放大淋浴",
              visual_brief_zh: "取消浴缸並形成寬敞淋浴區",
              rag_tags: ["bathroom", "large_shower"],
              engine_effects: { bath_fixture: "shower" },
            }),
          }));
        """
    )

    assert result == {"tub": "bathtub", "shower": None}


def test_special_request_is_a_complete_non_forced_answer() -> None:
    result = _run_room_requirement_helper(
        """
          console.log(JSON.stringify(
            buildSpecialRequestAnswer("tub", "保留浴缸", "需要扶手")
          ));
        """
    )

    assert result == {
        "optionId": "tub",
        "custom": "需要扶手；保留浴缸（尺寸可能無法配置）",
        "specialRequest": True,
        "forcePlacement": False,
    }


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
    assert "resolveWallMaterial.faceMaterials" in VIEWER
    # Surface overrides are now canonicalized per room before wall geometry is built.
    assert "const canonicalOverrides = new Map();" in VIEWER
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


def test_questionnaire_enters_step_six_when_scheme_b_needs_adjustment() -> None:
    assert 'ensureSchemeB(state.designSchemes, { reason: "questionnaire_alternative" })' in SCENE
    assert "目前格局無法在保留問卷需求下產生方案 B 的合法配置" in SCENE
    generation = SCENE.split("async function generateWhiteModelFromRequirements", 1)[1].split(
        "function cancelWhiteModelBeamPlacement", 1
    )[0]
    assert generation.count("await confirmLayout2d({ allowPendingFurniture: true })") == 2
    assert 'state.designSchemes.schemes.B.staleReason = message;' in generation
    assert '方案 A 已建立；方案 B 有待處理家具，請在第 6 步調整。' in generation
    assert "問卷需求的 2D+3D 配置已建立，可開始調整。" in generation


def test_scheme_b_alternative_tolerates_pending_furniture_so_ab_gate_can_appear() -> None:
    """逐房 A/B 的方案 B 是同一批家具的替代排法。舊版 relayoutFurnitureForScheme 只要
    有一件家具擺不下就整組回 null（→ schemeB.stale），逐房 A/B 關卡因此在多房真實格局
    下幾乎永不出現。B 生成要容忍部分待處理家具（與方案 A 的 allowPendingFurniture 對稱）；
    repair／手動重排等嚴格情境維持 null-on-failure。"""
    relayout = SCENE.split("async function relayoutFurnitureForScheme", 1)[1].split(
        "\nfunction misplacedAssignedRoomFurniture", 1
    )[0]
    # 新增 allowPending 選項；允許時保留部分擺放，不因單件失敗整組作廢
    assert "allowPending = false," in relayout
    assert "if (allowPending) return placedFurniture;" in relayout
    # 嚴格情境（repair／手動）仍維持原本的 null-on-failure
    assert (
        "placedFurniture.some((item) => item.placementFailed) ? null : placedFurniture"
        in relayout
    )

    # 問卷 A/B 生成與對話框懶生成都要帶 allowPending，方案 B 才不會被整組丟掉
    assert (
        SCENE.count(
            'relayoutFurnitureForScheme(schemeAFurniture, "B", { allowPending: true })'
        )
        == 1
    )
    assert (
        SCENE.count(
            'relayoutFurnitureForScheme(schemeA.furniture, "B", { allowPending: true })'
        )
        == 1
    )

    # repair 路徑仍嚴格：relayout 回 null 就丟錯，不得靜默套用失敗擺放
    repair = SCENE.split("async function repairFurnitureRoomPlacements", 1)[1].split(
        "\nasync function ", 1
    )[0]
    assert "if (!repairedFurniture) {" in repair
