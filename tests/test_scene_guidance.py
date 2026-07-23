import json

from test_scene_workflow import ROOT, run_workflow_script


GUIDANCE_MODULE = ROOT / "roompilot" / "server" / "static" / "scene_guidance.js"


def test_manual_scale_confirmation_replaces_low_confidence_ocr_scale() -> None:
    module_uri = GUIDANCE_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildFloorplanConfirmationCorrections }} from {json.dumps(module_uri)};
        const corrections = buildFloorplanConfirmationCorrections({{
          scale: {{
            distance_cm: 90,
            pixel_distance: 415,
            cm_per_px: 0.2169,
            source: "dimension_ocr",
            confidence: 0.42,
          }},
          spatial_report: {{ review_items: [] }},
        }}, 630, []);
        console.log(JSON.stringify(corrections));
        """
    )

    assert result["scale"]["distance_cm"] == 630
    assert result["scale"]["cm_per_px"] == 630 / 415
    assert result["scale"]["source"] == "manual_confirmation"
    assert result["scale"]["confidence"] == 1


def test_recognition_presentation_summarizes_rooms_and_only_prompts_uncertain_findings() -> None:
    module_uri = GUIDANCE_MODULE.as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildRecognitionPresentation }} from {json.dumps(module_uri)};
        const presentation = buildRecognitionPresentation({{
          spatial_report: {{
            room_counts: {{ bedroom: 3, bathroom: 2, kitchen: 1, dining_room: 1, living_room: 1, balcony: 1 }},
            rooms: [
              {{ room_id: "bedroom-1", room_type: "bedroom", label: "主臥室", confidence: {{ score: 0.95, level: "high" }}, inner_dimensions_cm: {{ width: 320, depth: 360 }}, net_area_m2: 11.52, polygon_cm: [] }},
              {{ room_id: "balcony-1", room_type: "balcony", label: "陽台", confidence: {{ score: 0.62, level: "medium" }}, inner_dimensions_cm: null, net_area_m2: null, polygon_cm: null }},
            ],
            review_items: [{{ id: "room:balcony-1:geometry", room_id: "balcony-1", status: "needs_targeted_review", reason: "room_boundary_unresolved" }}],
          }},
          doors: [{{ confidence: 0.94 }}],
          windows: [{{ confidence: 0.91 }}],
        }});
        console.log(JSON.stringify(presentation));
        """
    )

    assert result["summary"]["bedroom"] == 3
    assert result["summary"]["bathroom"] == 2
    assert result["rooms"][0]["dimensionLabel"] == "320 × 360 cm｜11.52 m²"
    assert result["rooms"][0]["needsReview"] is False
    assert result["rooms"][1]["needsReview"] is True
    assert result["correctionPrompts"] == [
        {
            "findingId": "room:balcony-1:geometry",
            "roomId": "balcony-1",
            "reason": "room_boundary_unresolved",
            "reasonLabel": "房間邊界尚未封閉",
            "maxChoices": 3,
        }
    ]
