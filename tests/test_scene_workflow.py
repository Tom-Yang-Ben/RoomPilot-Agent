import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MODULE = ROOT / "roompilot" / "server" / "static" / "scene_workflow.js"
SCENE_HTML = ROOT / "roompilot" / "server" / "static" / "scene.html"


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
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
        }});
        const questionnaireAfterSpace = workflow.goTo("requirements");

        console.log(JSON.stringify({{
          steps: WORKFLOW_STEPS,
          recognitionPanel: WORKFLOW_PANEL_BY_STEP.recognition,
          calibrationPanel: WORKFLOW_PANEL_BY_STEP.calibration,
          questionnaireBeforeScale,
          questionnaireBeforeSpace,
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
        ],
        "recognitionPanel": "scale",
        "calibrationPanel": "scale",
        "questionnaireBeforeScale": False,
        "questionnaireBeforeSpace": False,
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
    ]

    for panel_id in expected_panel_ids:
        assert f'id="{panel_id}"' in html
    assert 'id="reset-project"' in html
    assert 'id="project-privacy-notice"' in html
    assert 'id="basic-profile-panel"' not in html
    assert 'id="room-list"' in html
    assert 'id="structure-confirmation-panel"' in html
    assert 'id="whole-house-fields"' in html
    assert 'id="room-question-nav"' in html
    assert 'id="furniture-icon-library"' in html
    assert "確認未填寫房間維持現狀不做規劃" in html
    assert "我已確認是否有指定家具需求" in html


def test_scene_exposes_the_final_nine_step_workflow() -> None:
    html = SCENE_HTML.read_text(encoding="utf-8")
    labels = [
        "1 建立專案",
        "2 上傳平面圖",
        "3–4 確定尺寸",
        "5 空間與結構",
        "6 需求問卷",
        "7 2D 家具配置",
        "8 3D 白模",
        "9 即時寫實",
    ]

    assert 'data-workflow-count="9"' in html
    for label in labels:
        assert label in html
    assert "進入 RoomPilot" not in html


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


def test_privacy_consent_and_completed_upload_are_required_before_analysis() -> None:
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
        const workflow = createWorkflow({{ projectId: "privacy", storage }});
        workflow.complete("project", {{ name: "梁宅專案" }});
        workflow.complete("upload", {{ filename: "plan.dxf" }});
        const beforeConsent = workflow.canAnalyzeFloorplan();
        workflow.setPrivacyConsent({{
          accepted: true,
          projectOnly: true,
          noTraining: true,
        }});
        const afterConsent = workflow.canAnalyzeFloorplan();
        const restored = restoreWorkflow({{ projectId: "privacy", storage }});

        console.log(JSON.stringify({{
          beforeConsent,
          afterConsent,
          restoredReady: restored.canAnalyzeFloorplan(),
        }}));
        """
    )

    assert result == {
        "beforeConsent": False,
        "afterConsent": True,
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
