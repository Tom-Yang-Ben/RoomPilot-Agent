import json

from test_scene_workflow import ROOT, run_workflow_script


REPORT_MODULE = ROOT / "backend" / "server" / "static" / "scene_space_change_report.js"


def test_wall_boxing_report_uses_one_change_for_customer_and_designer_views() -> None:
    module_uri = REPORT_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildEmptyAffected, buildSceneWallSegment, buildWallBoxingComparison, buildSpaceChangeReport }} from {json.dumps(module_uri)};
        const change = {{
          id: "change-wall-01",
          roomId: "bedroom-1",
          title: "主臥樑柱機能包覆",
          kind: "functional_wall_boxing",
          target: "column",
          axis: "width",
          thicknessM: 0.18,
          wallLengthM: 3.6,
          beforeDimensionsM: {{ width: 3.2, depth: 3.6 }},
          affected: {{ doors: [], windows: ["window-1"], furniture: ["wardrobe-1"], mep: ["outlet-3"] }},
          risks: ["須保留檢修能力"],
          costEstimateId: "estimate-wall-01",
          visualRefs: {{ plan: "plan-change-wall-01", section: "section-change-wall-01", model3d: "model-change-wall-01" }},
          evidence: [{{ kind: "column_geometry", ref: "column-1" }}],
          confidence: {{ level: "medium", score: 0.74 }},
          status: "field_measurement_required",
        }};
        const comparison = buildWallBoxingComparison(change);
        const customer = buildSpaceChangeReport([change], {{ audience: "customer" }});
        const designer = buildSpaceChangeReport([change], {{ audience: "designer" }});
        const sceneWall = buildSceneWallSegment(comparison, {{ width_cm: 630, depth_cm: 900 }}, change.id);
        console.log(JSON.stringify({{ comparison, customer, designer, sceneWall, emptyAffected: buildEmptyAffected() }}));
        """
    )

    assert result["comparison"]["afterDimensionsM"] == {"width": 3.02, "depth": 3.6}
    assert result["comparison"]["lostAreaM2"] == 0.648
    assert result["comparison"]["afterPolygonM"] == [
        {"x": 0, "y": 0},
        {"x": 3.02, "y": 0},
        {"x": 3.02, "y": 3.6},
        {"x": 0, "y": 3.6},
    ]
    assert result["customer"]["changes"][0]["id"] == "change-wall-01"
    assert result["designer"]["changes"][0]["id"] == "change-wall-01"
    assert result["customer"]["changes"][0]["visualRefs"]["model3d"] == "model-change-wall-01"
    assert result["designer"]["changes"][0]["affected"]["mep"] == ["outlet-3"]
    assert result["designer"]["changes"][0]["evidence"][0]["ref"] == "column-1"
    assert result["sceneWall"] == {
        "start": {"x": -0.13, "z": -4.5},
        "end": {"x": -0.13, "z": -0.9},
        "change_id": "change-wall-01",
        "source": "wall_boxing_geometry",
    }
    assert result["emptyAffected"] == {"doors": [], "windows": [], "furniture": [], "mep": []}
    assert result["designer"]["disclaimer"] == "概念建議；施工前須現場丈量及專業確認。"
