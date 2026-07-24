import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MODULE = ROOT / "backend" / "server" / "static" / "scene_workflow.js"
SCENE_HTML = ROOT / "backend" / "server" / "static" / "scene.html"
STRUCTURE_UTILS_MODULE = ROOT / "backend" / "server" / "static" / "scene_structure_utils.js"
STRUCTURE_GEOMETRY_MODULE = ROOT / "backend" / "server" / "static" / "scene_structure_geometry.js"


def run_workflow_script(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_pending_save_replays_only_against_the_server_version_it_started_from() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ shouldReplayPendingSave }} from {json.dumps(module_uri)};

        const serverProject = {{ updated_at: "2026-07-21T13:16:06Z" }};
        console.log(JSON.stringify({{
          same: shouldReplayPendingSave(JSON.stringify({{
            base_updated_at: "2026-07-21T13:16:06Z",
            current_step: "space_confirmation",
            workflow: {{ space_confirmation: {{ rooms: [{{ id: "room-1" }}] }} }},
          }}), serverProject),
          stale: shouldReplayPendingSave(JSON.stringify({{
            base_updated_at: "2026-07-21T13:12:11Z",
            current_step: "space_confirmation",
            workflow: {{ space_confirmation: {{ rooms: [] }} }},
          }}), serverProject),
          legacy: shouldReplayPendingSave(JSON.stringify({{
            current_step: "space_confirmation",
            workflow: {{ space_confirmation: {{ rooms: [] }} }},
          }}), serverProject),
          invalid: shouldReplayPendingSave("not-json", serverProject),
        }}));
        """
    )

    assert result == {"same": True, "stale": False, "legacy": False, "invalid": False}


def test_overlapping_windows_on_the_same_wall_are_deduplicated() -> None:
    module_uri = STRUCTURE_UTILS_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ dedupeWindowCandidates, windowsOverlap }} from {json.dumps(module_uri)};

        const recognized = {{
          id: "window-5",
          host_wall_id: "wall-14",
          start: {{ x: 620, y: 559 }},
          end: {{ x: 620, y: 500 }},
          confirmed: true,
          confidence: 0.92,
          source: "cody",
        }};
        const manualDuplicate = {{
          id: "window-manual",
          host_wall_id: "wall-14",
          start: {{ x: 620, y: 619 }},
          end: {{ x: 620, y: 499 }},
          confirmed: false,
          source: "manual",
        }};
        const separateWindow = {{
          id: "window-4",
          host_wall_id: "wall-14",
          start: {{ x: 620, y: 200 }},
          end: {{ x: 620, y: 320 }},
          confirmed: true,
          source: "cody",
        }};

        const normalized = dedupeWindowCandidates([
          recognized,
          manualDuplicate,
          separateWindow,
        ]);
        console.log(JSON.stringify({{
          duplicate: windowsOverlap(recognized, manualDuplicate),
          separate: windowsOverlap(recognized, separateWindow),
          ids: normalized.windows.map((item) => item.id),
          removed: normalized.removed,
        }}));
        """
    )

    assert result == {
        "duplicate": True,
        "separate": False,
        "ids": ["window-5", "window-4"],
        "removed": 1,
    }


def test_beam_and_column_preview_geometry_exposes_real_vertical_position() -> None:
    module_uri = STRUCTURE_GEOMETRY_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ structurePreviewDescriptor }} from {json.dumps(module_uri)};

        const beam = structurePreviewDescriptor({{
          start: {{ x: 100, y: 200 }},
          end: {{ x: 400, y: 200 }},
          thickness_cm: 30,
          height_cm: 45,
        }}, "beam", {{ ceilingHeightCm: 270, planWidthCm: 1000, planDepthCm: 800 }});
        const column = structurePreviewDescriptor({{
          center: {{ x: 200, y: 300 }},
          size_cm: 40,
          depth_cm: 55,
          height_cm: 270,
        }}, "column", {{ ceilingHeightCm: 270, planWidthCm: 1000, planDepthCm: 800 }});

        console.log(JSON.stringify({{ beam, column }}));
        """
    )

    assert result == {
        "beam": {
            "kind": "beam",
            "lengthCm": 300,
            "widthCm": 30,
            "heightCm": 45,
            "centerHeightCm": 247.5,
            "centerX": -250,
            "centerZ": -200,
            "rotationDeg": 0,
        },
        "column": {
            "kind": "column",
            "lengthCm": 40,
            "widthCm": 55,
            "heightCm": 270,
            "centerHeightCm": 135,
            "centerX": -300,
            "centerZ": -100,
            "rotationDeg": 0,
        },
    }


def test_column_geometry_preserves_independent_width_depth_height_and_rotation() -> None:
    module_uri = STRUCTURE_GEOMETRY_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ columnGeometryDescriptor }} from {json.dumps(module_uri)};

        console.log(JSON.stringify(columnGeometryDescriptor({{
          center: {{ x: 140, z: -80 }},
          size_cm: 58,
          depth_cm: 35,
          height_cm: 245,
          rotation_deg: 30,
        }})));
        """
    )

    assert result == {
        "widthCm": 58,
        "depthCm": 35,
        "heightCm": 245,
        "centerX": 140,
        "centerZ": -80,
        "centerHeightCm": 122.5,
        "rotationDeg": 30,
    }


def test_column_dimension_validation_rejects_missing_or_unbuildable_values() -> None:
    module_uri = STRUCTURE_GEOMETRY_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ validateColumnDimensionsCm }} from {json.dumps(module_uri)};

        console.log(JSON.stringify({{
          valid: validateColumnDimensionsCm({{ widthCm: 58, depthCm: 35, heightCm: 270 }}),
          missing: validateColumnDimensionsCm({{ widthCm: "", depthCm: 35, heightCm: 270 }}),
          tooSmall: validateColumnDimensionsCm({{ widthCm: 5, depthCm: 35, heightCm: 270 }}),
          tooLarge: validateColumnDimensionsCm({{
            widthCm: 601,
            depthCm: 35,
            heightCm: 270,
            maxWidthCm: 600,
            maxDepthCm: 400,
            maxHeightCm: 280,
          }}),
          rotatedOutside: validateColumnDimensionsCm({{
            widthCm: 600,
            depthCm: 400,
            heightCm: 270,
            maxWidthCm: 600,
            maxDepthCm: 400,
            maxHeightCm: 280,
            centerXcm: 300,
            centerYcm: 200,
            rotationDeg: 30,
          }}),
          edgeOutside: validateColumnDimensionsCm({{
            widthCm: 40,
            depthCm: 35,
            heightCm: 270,
            maxWidthCm: 600,
            maxDepthCm: 400,
            maxHeightCm: 280,
            centerXcm: 10,
            centerYcm: 200,
            rotationDeg: 0,
          }}),
          exactRotatedFit: validateColumnDimensionsCm({{
            widthCm: 400,
            depthCm: 600,
            heightCm: 270,
            maxWidthCm: 600,
            maxDepthCm: 400,
            maxHeightCm: 280,
            centerXcm: 300,
            centerYcm: 200,
            rotationDeg: 90,
          }}),
        }}));
        """
    )

    assert result == {
        "valid": {"valid": True, "values": {"widthCm": 58, "depthCm": 35, "heightCm": 270}},
        "missing": {"valid": False, "message": "請完整輸入柱寬、深度與高度。"},
        "tooSmall": {"valid": False, "message": "柱寬與深度至少 10 公分，高度至少 30 公分。"},
        "tooLarge": {"valid": False, "message": "柱寬不可超過 600 公分、深度不可超過 400 公分、高度不可超過 280 公分。"},
        "rotatedOutside": {"valid": False, "message": "旋轉後柱體超出平面圖範圍，請縮小尺寸、調整方向或移動位置。"},
        "edgeOutside": {"valid": False, "message": "旋轉後柱體超出平面圖範圍，請縮小尺寸、調整方向或移動位置。"},
        "exactRotatedFit": {"valid": True, "values": {"widthCm": 400, "depthCm": 600, "heightCm": 270}},
    }


def test_beam_drag_geometry_snaps_to_axis_and_nearby_structure_points() -> None:
    module_uri = STRUCTURE_UTILS_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ beamDragGeometry }} from {json.dumps(module_uri)};

        const horizontal = beamDragGeometry(
          {{ x: 100, y: 200 }},
          {{ x: 402, y: 209 }},
          [{{ x: 400, y: 200 }}],
        );
        const vertical = beamDragGeometry(
          {{ x: 300, y: 100 }},
          {{ x: 308, y: 410 }},
          [{{ x: 300, y: 400 }}],
        );
        const tooShort = beamDragGeometry(
          {{ x: 200, y: 200 }},
          {{ x: 208, y: 203 }},
          [],
        );

        console.log(JSON.stringify({{ horizontal, vertical, tooShort }}));
        """
    )

    assert result == {
        "horizontal": {
            "start": {"x": 100, "y": 200},
            "end": {"x": 400, "y": 200},
            "lengthCm": 300,
            "valid": True,
            "snapped": True,
        },
        "vertical": {
            "start": {"x": 300, "y": 100},
            "end": {"x": 300, "y": 400},
            "lengthCm": 300,
            "valid": True,
            "snapped": True,
        },
        "tooShort": {
            "start": {"x": 200, "y": 200},
            "end": {"x": 208, "y": 200},
            "lengthCm": 8,
            "valid": False,
            "snapped": False,
        },
    }


def test_confirmed_scale_unlocks_space_confirmation_and_state_can_be_restored() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow, restoreWorkflow }} from {json.dumps(module_uri)};

        const writes = new Map();
        const storage = {{
          getItem: (key) => writes.get(key) ?? null,
          setItem: (key, value) => writes.set(key, value),
          removeItem: (key) => writes.delete(key),
        }};
        const workflow = createWorkflow({{ projectId: "project-630", storage }});
        const blocked = workflow.goTo("space_confirmation");
        workflow.complete("project", {{ name: "630 驗收圖" }});
        workflow.complete("upload", {{ filename: "B1.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        const stillBlocked = workflow.goTo("space_confirmation");
        workflow.complete("calibration", {{ distanceCm: 630 }});
        const allowed = workflow.goTo("space_confirmation");
        const restored = restoreWorkflow({{ projectId: "project-630", storage }});

        console.log(JSON.stringify({{
          blocked,
          stillBlocked,
          allowed,
          step: restored.currentStep,
          distanceCm: restored.data.calibration.distanceCm,
          schemaVersion: restored.schemaVersion,
        }}));
        """
    )

    assert result == {
        "blocked": False,
        "stillBlocked": False,
        "allowed": True,
        "step": "space_confirmation",
        "distanceCm": 630,
        "schemaVersion": 2,
    }


def test_nine_step_workflow_uses_one_panel_for_recognition_and_calibration() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{
          WORKFLOW_STEPS,
          WORKFLOW_PANEL_BY_STEP,
          createWorkflow,
        }} from {json.dumps(module_uri)};

        const workflow = createWorkflow({{
          projectId: "nine-step-project",
          storage: null,
        }});
        workflow.complete("project", {{ name: "測試專案" }});
        workflow.complete("upload", {{ filename: "plan.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        const questionnaireBeforeScale = workflow.goTo("requirements");
        workflow.complete("calibration", {{ distanceCm: 630 }});
        const questionnaireBeforeSpace = workflow.goTo("requirements");
        const legacySpaceCompletion = workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
        }});
        const questionnaireBeforeProportions = workflow.goTo("requirements");
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        const questionnaireAfterSpace = workflow.goTo("requirements");

        console.log(JSON.stringify({{
          steps: WORKFLOW_STEPS,
          recognitionPanel: WORKFLOW_PANEL_BY_STEP.recognition,
          calibrationPanel: WORKFLOW_PANEL_BY_STEP.calibration,
          questionnaireBeforeScale,
          questionnaireBeforeSpace,
          legacySpaceCompletion,
          questionnaireBeforeProportions,
          questionnaireAfterSpace,
        }}));
        """
    )

    assert result == {
        "steps": [
            "project",
            "upload",
            "recognition",
            "calibration",
            "space_confirmation",
            "requirements",
            "layout_2d",
            "white_model_3d",
            "realistic_3d",
            "proposal_review",
            "ai_render",
        ],
        "recognitionPanel": "scale",
        "calibrationPanel": "scale",
        "questionnaireBeforeScale": False,
        "questionnaireBeforeSpace": False,
        "legacySpaceCompletion": False,
        "questionnaireBeforeProportions": False,
        "questionnaireAfterSpace": True,
    }


def test_scene_wizard_exposes_one_panel_for_each_confirmed_step() -> None:
    html = SCENE_HTML.read_text(encoding="utf-8")
    expected_panel_ids = [
        "project-step",
        "upload-step",
        "scale-step",
        "space-step",
        "requirements-step",
        "layout-2d-step",
        "white-model-3d-step",
        "realistic-3d-step",
        "proposal-review-step",
        "ai-render-step",
    ]

    for panel_id in expected_panel_ids:
        assert f'id="{panel_id}"' in html
    assert 'id="reset-project"' in html
    assert 'id="project-floorplan-confirmation-notice"' in html
    assert 'id="confirm-upload" type="button" class="primary-action" disabled' in html
    assert 'id="basic-profile-panel"' not in html
    assert 'id="room-list"' in html
    assert 'id="structure-confirmation-panel"' in html
    assert 'id="whole-house-fields"' in html
    assert 'id="visual-space-nav"' in html
    assert 'id="room-question-nav"' not in html
    assert 'id="furniture-icon-library"' in html
    assert "此空間暫不作答" in html
    assert "我已確認是否有指定家具需求" in html


def test_scene_exposes_the_final_ten_step_workflow() -> None:
    html = SCENE_HTML.read_text(encoding="utf-8")
    labels = [
        "1 建立專案",
        "2 上傳平面圖",
        "3 確定尺寸",
        "4 空間與結構",
        "5 需求問卷",
        "6 2D 家具配置",
        "7 3D 白模",
        "8 即時寫實",
        "9 方案鎖定",
        "10 AI 渲染",
    ]

    assert 'data-workflow-count="10"' in html
    for label in labels:
        assert label in html
    assert "進入 RoomPilot" not in html


def test_render_review_steps_require_a_locked_master_camera() -> None:
    result = run_workflow_script(
        """
        import { createWorkflow } from "__WORKFLOW_MODULE__";
        const workflow = createWorkflow({ projectId: "render-gates", storage: null });
        workflow.complete("project", { name: "渲染驗收" });
        workflow.complete("upload", { filename: "plan.png" });
        workflow.complete("recognition", { engine: "cody" });
        workflow.complete("calibration", { distanceCm: 630 });
        workflow.complete("space_confirmation", {
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        });
        workflow.complete("requirements", { basicConfirmed: true, roomsResolved: true });
        workflow.complete("layout_2d", { confirmed: true });
        workflow.complete("white_model_3d", {
          confirmed: true,
          expectedFurnitureCount: 1,
          visibleFurnitureCount: 1,
        });
        workflow.complete("realistic_3d", { confirmed: true });
        const beforeLock = workflow.goTo("ai_render");
        const invalidReview = workflow.complete("proposal_review", { confirmed: true });
        const validReview = workflow.complete("proposal_review", {
          confirmed: true,
          masterView: {
            camera: {
              position_cm: [420, 165, 380],
              target_cm: [210, 120, 190],
              fov_deg: 52,
            },
          },
        });
        const afterLock = workflow.goTo("ai_render");
        console.log(JSON.stringify({ beforeLock, invalidReview, validReview, afterLock }));
        """.replace("__WORKFLOW_MODULE__", WORKFLOW_MODULE.as_uri())
    )

    assert result == {
        "beforeLock": False,
        "invalidReview": False,
        "validReview": True,
        "afterLock": True,
    }


def test_each_gate_blocks_the_next_stage_until_confirmation_is_valid() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(module_uri)};

        const workflow = createWorkflow({{ projectId: "gates", storage: null }});
        workflow.complete("project", {{ name: "驗收專案" }});
        workflow.complete("upload", {{ filename: "plan.jpg" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        const layoutBeforeRequirements = workflow.goTo("layout_2d");
        workflow.complete("requirements", {{
          basicConfirmed: true,
          roomsResolved: true,
        }});
        const layoutAfterRequirements = workflow.goTo("layout_2d");
        const whiteBeforeLayout = workflow.goTo("white_model_3d");
        workflow.complete("layout_2d", {{ confirmed: true }});
        const whiteAfterLayout = workflow.goTo("white_model_3d");
        workflow.complete("white_model_3d", {{
          confirmed: true,
          visibleFurnitureCount: 0,
        }});
        const realBeforeVisibleFurniture = workflow.goTo("realistic_3d");
        workflow.complete("white_model_3d", {{
          confirmed: true,
          visibleFurnitureCount: 2,
          expectedFurnitureCount: 2,
        }});
        const realAfterVisibleFurniture = workflow.goTo("realistic_3d");

        console.log(JSON.stringify({{
          layoutBeforeRequirements,
          layoutAfterRequirements,
          whiteBeforeLayout,
          whiteAfterLayout,
          realBeforeVisibleFurniture,
          realAfterVisibleFurniture,
        }}));
        """
    )

    assert result == {
        "layoutBeforeRequirements": False,
        "layoutAfterRequirements": True,
        "whiteBeforeLayout": False,
        "whiteAfterLayout": True,
        "realBeforeVisibleFurniture": False,
        "realAfterVisibleFurniture": True,
    }


def test_floorplan_confirmation_and_completed_upload_are_required_before_analysis() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow, restoreWorkflow }} from {json.dumps(module_uri)};

        const writes = new Map();
        const storage = {{
          getItem: (key) => writes.get(key) ?? null,
          setItem: (key, value) => writes.set(key, value),
          removeItem: (key) => writes.delete(key),
        }};
        const workflow = createWorkflow({{ projectId: "floorplan-confirmation", storage }});
        workflow.complete("project", {{ name: "梁宅專案" }});
        workflow.complete("upload", {{ filename: "plan.dxf" }});
        const beforeConfirmation = workflow.canAnalyzeFloorplan();
        workflow.setFloorplanConfirmation({{ confirmed: true }});
        const afterConfirmation = workflow.canAnalyzeFloorplan();
        const restored = restoreWorkflow({{ projectId: "floorplan-confirmation", storage }});

        console.log(JSON.stringify({{
          beforeConfirmation,
          afterConfirmation,
          restoredReady: restored.canAnalyzeFloorplan(),
        }}));
        """
    )

    assert result == {
        "beforeConfirmation": False,
        "afterConfirmation": True,
        "restoredReady": True,
    }


def test_editing_upstream_confirmation_invalidates_downstream_results() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(module_uri)};

        const workflow = createWorkflow({{ projectId: "stale", storage: null }});
        workflow.complete("project", {{ name: "住宅專案" }});
        workflow.complete("upload", {{ filename: "plan.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        workflow.complete("requirements", {{
          basicConfirmed: true,
          roomsResolved: true,
        }});
        workflow.complete("layout_2d", {{ confirmed: true }});
        workflow.complete("white_model_3d", {{
          confirmed: true,
          visibleFurnitureCount: 2,
          expectedFurnitureCount: 2,
        }});
        workflow.complete("realistic_3d", {{ confirmed: true }});
        workflow.complete("calibration", {{ distanceCm: 620 }});

        console.log(JSON.stringify({{
          staleFrom: workflow.staleFrom,
          completed: workflow.completed,
          canEnterRealistic: workflow.canEnter("realistic_3d"),
        }}));
        """
    )

    assert result["staleFrom"] == "calibration"
    assert result["completed"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
    ]
    assert result["canEnterRealistic"] is False


def test_white_model_allows_an_explicit_zero_furniture_plan() -> None:
    module_uri = WORKFLOW_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(module_uri)};

        const workflow = createWorkflow({{ projectId: "empty-plan", storage: null }});
        workflow.complete("project", {{ name: "純結構專案" }});
        workflow.complete("upload", {{ filename: "plan.dxf" }});
        workflow.complete("recognition", {{ engine: "dxf" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        workflow.complete("requirements", {{
          basicConfirmed: true,
          roomsResolved: true,
        }});
        workflow.complete("layout_2d", {{ confirmed: true }});
        const completed = workflow.complete("white_model_3d", {{
          confirmed: true,
          visibleFurnitureCount: 0,
          expectedFurnitureCount: 0,
        }});
        console.log(JSON.stringify({{
          completed,
          canEnterRealistic: workflow.canEnter("realistic_3d"),
        }}));
        """
    )

    assert result == {"completed": True, "canEnterRealistic": True}
