from __future__ import annotations

import hashlib
import json
import re

from test_scene_workflow import ROOT, run_workflow_script


STATIC = ROOT / "roompilot" / "server" / "static"


def _space_heading_html(html: str) -> str:
    heading_start = html.index('class="rp-pane-heading"', html.index('id="space-step"'))
    stage_start = html.index('id="space-plan-stage"')
    return html[heading_start:stage_start]


def test_scene_entrypoint_cache_key_matches_bundle_content() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    bundle = (STATIC / "scene_v2.js").read_bytes()
    expected = hashlib.sha256(bundle).hexdigest()[:12]

    assert f'src="/static/scene_v2.js?v=sha256-{expected}"' in html


def test_dimensioned_plan_draws_colored_room_outlines_and_size_lines() -> None:
    module_uri = (STATIC / "scene_dimensioned_plan.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ buildDimensionedPlanAnnotations }} from {json.dumps(module_uri)};
        const plan = buildDimensionedPlanAnnotations([
          {{
            id: "living",
            label: "客廳",
            widthCm: 500,
            depthCm: 400,
            areaM2: 20,
            polygonPx: [{{x: 20, y: 20}}, {{x: 520, y: 20}}, {{x: 520, y: 420}}, {{x: 20, y: 420}}],
          }},
          {{
            id: "bedroom",
            label: "臥室",
            widthCm: 400,
            depthCm: 250,
            areaM2: 10,
            polygonPx: [{{x: 540, y: 20}}, {{x: 940, y: 20}}, {{x: 940, y: 270}}, {{x: 540, y: 270}}],
          }},
        ], {{ imageWidth: 1000, imageHeight: 600 }});
        console.log(JSON.stringify(plan));
        """
    )

    assert result["roomCount"] == 2
    assert result["totalAreaM2"] == 30
    assert result["rooms"][0]["color"] != result["rooms"][1]["color"]
    assert 'data-dimension-room="living"' in result["svg"]
    assert "500 cm" in result["svg"]
    assert "400 cm" in result["svg"]
    assert "20.00 m² · ±5%" in result["svg"]
    assert 'class="rp-plan-dimension"' in result["svg"]


def test_floor_to_ceiling_window_preset_reaches_from_floor_to_ceiling() -> None:
    module_uri = (STATIC / "scene_window_types.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          applyWindowTypePreset,
          windowOpeningMetrics,
          WINDOW_TYPES,
        }} from {json.dumps(module_uri)};
        const floorWindow = applyWindowTypePreset(
          {{ id: "window-1", width_m: 2.4 }},
          WINDOW_TYPES.floorToCeiling,
          2.7,
        );
        const floorMetrics = windowOpeningMetrics(floorWindow, 2.7);
        const standardMetrics = windowOpeningMetrics({{
          window_type: WINDOW_TYPES.standard,
          sill_height_m: 0.9,
          height_m: 1.2,
        }}, 2.7);
        console.log(JSON.stringify({{ floorWindow, floorMetrics, standardMetrics }}));
        """
    )

    assert result["floorWindow"]["window_type"] == "floor_to_ceiling"
    assert result["floorWindow"]["sill_height_m"] == 0
    assert result["floorWindow"]["height_m"] == 2.62
    assert result["floorMetrics"] == {
        "windowType": "floor_to_ceiling",
        "sillHeightM": 0,
        "headHeightM": 2.62,
        "glazingHeightM": 2.62,
    }
    assert result["standardMetrics"] == {
        "windowType": "standard",
        "sillHeightM": 0.9,
        "headHeightM": 2.1,
        "glazingHeightM": 1.2,
    }


def test_window_editor_exposes_floor_to_ceiling_type_and_visual_asset() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="window-type-field"' in html
    assert 'id="selected-window-type"' in html
    assert 'value="floor_to_ceiling"' in html
    assert 'id="window-type-preview"' in html
    assert "黑鋁框左右兩扇玻璃參考" in html
    assert (STATIC / "structure_assets" / "floor-to-ceiling-window.png").is_file()
    assert "function applySelectedWindowType" in controller
    assert "function applyWindowType(windowId, type)" in controller
    assert 'class="rp-window-type-toggle"' in controller
    assert 'data-window-type="${WINDOW_TYPES.standard}"' in controller
    assert 'data-window-type="${WINDOW_TYPES.floorToCeiling}"' in controller
    assert 'aria-pressed="${windowType === WINDOW_TYPES.standard}"' in controller
    assert 'event.target.closest("[data-window-type]")' in controller
    assert "normalizedWindowType(item.window_type) === nextType" in controller
    assert "applyWindowTypePreset" in controller
    assert "windowOpeningMetrics" in viewer
    assert "const mullionPositions = [0];" in viewer


def test_step_four_has_a_dimensioned_floorplan_confirmation_page() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="space-editor-workspace"' in html
    assert 'id="space-dimension-review"' in html
    assert 'id="dimensioned-plan-stage"' in html
    assert 'id="dimensioned-plan-image"' in html
    assert 'id="dimensioned-plan-overlay"' in html
    assert 'id="dimensioned-plan-legend"' in html
    assert 'id="back-to-space-editor"' in html
    assert 'id="recalibrate-space"' in html
    assert 'id="confirm-dimensioned-plan"' in html
    assert "水平線標示寬度，垂直線標示長度" in html
    assert "±5%" in html
    assert "不可取代現場丈量" in html
    assert "rp-proportion-bar" not in html
    assert "function showDimensionedPlanReview" in source
    assert "function confirmDimensionedPlan" in source
    initial_confirmation = source.split("function confirmSpace()", 1)[1].split(
        "function dimensionedPlanRoomInputs", 1
    )[0]
    final_confirmation = source.split("function confirmDimensionedPlan()", 1)[1].split(
        "function renderWholeHouseQuestionnaire", 1
    )[0]
    assert 'showDimensionedPlanReview();' in initial_confirmation
    assert '.complete("space_confirmation"' not in initial_confirmation
    assert '.complete("space_confirmation"' in final_confirmation
    assert "proportionsConfirmed: true" in final_confirmation
    assert "dimensionedPlanConfirmed: true" in final_confirmation


def test_upload_step_does_not_offer_the_internal_630_sample_button() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="load-sample-630"' not in html
    assert "function loadSample630" not in source
    assert '$("#load-sample-630")' not in source


def test_scene_sidebar_numbers_match_viewer_markers() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'class="rp-object-number">#${index + 1}' in source
    assert '"bed-frame": "雙人床"' in source
    assert '"floor-lamp": "落地燈"' in source
    assert '"large-medium-rug": "地毯"' in source
    assert "sceneObjectDisplayName(item, index)" in source


def test_structure_step_explains_pending_manual_door_directions() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "待確認：" in source
    assert "一鍵確認全部門" in html
    assert "confirmAllButton.disabled = !collection.length || allConfirmed" in source
    assert "`一鍵確認全部${meta.label}`" in source
    assert "開門側與鉸鏈端" in source


def test_scene_uses_the_final_eight_step_flow_and_exact_upload_contract() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")

    for label in (
        "1 建立專案",
        "2 上傳平面圖",
        "3 確定尺寸",
        "4 空間與結構",
        "5 需求問卷",
        "6 2D 家具配置",
        "7 3D 白模",
        "8 即時寫實",
    ):
        assert label in html

    assert 'data-workflow-count="8"' in html
    assert "3–4" not in html
    assert 'accept=".dxf,.png,.jpg,.jpeg,image/png,image/jpeg,application/dxf"' in html
    assert 'id="project-step"' in html
    assert 'id="upload-step"' in html
    assert 'id="scale-step"' in html
    assert 'id="space-step"' in html
    assert 'id="requirements-step"' in html
    assert 'id="layout-2d-step"' in html
    assert 'id="white-model-3d-step"' in html
    assert 'id="realistic-3d-step"' in html
    assert 'id="basic-profile-panel"' not in html


def test_2d_furniture_library_has_top_view_icons_and_real_centimetre_sizes() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ FURNITURE_2D_LIBRARY, createFurniture2DItem }} from {json.dumps(module_uri)};
        const variants = FURNITURE_2D_LIBRARY.flatMap((item) => item.variants);
        const roundTable = createFurniture2DItem("dining-table", "round-4");
        const lSofa = createFurniture2DItem("sofa", "l-shape");
        console.log(JSON.stringify({{
          categoryCount: FURNITURE_2D_LIBRARY.length,
          everyVariantHasIcon: variants.every((item) => item.iconPath?.length > 8),
          everyVariantHasCm: variants.every((item) => item.widthCm > 0 && item.depthCm > 0),
          roundTable,
          lSofa,
        }}));
        """
    )

    assert result["categoryCount"] >= 10
    assert result["everyVariantHasIcon"] is True
    assert result["everyVariantHasCm"] is True
    assert result["roundTable"]["widthCm"] == result["roundTable"]["depthCm"]
    assert result["lSofa"]["widthCm"] >= 240


def test_room_name_drives_default_furniture_when_the_type_is_not_available() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ recommendedFurnitureForRoom }} from {json.dumps(module_uri)};
        const samples = {{
          bedroom: recommendedFurnitureForRoom({{ type: "default", label: "DORMITORY" }}),
          kitchen: recommendedFurnitureForRoom({{ type: "default", label: "KITCHEN" }}),
          storage: recommendedFurnitureForRoom({{ type: "default", label: "DEPOSIT" }}),
          bathroom: recommendedFurnitureForRoom({{ type: "default", label: "BATHROOM" }}),
          living: recommendedFurnitureForRoom({{ type: "default", label: "LIVING ROOM" }}),
          balcony: recommendedFurnitureForRoom({{ type: "default", label: "BALCONY" }}),
          circulation: recommendedFurnitureForRoom({{ type: "default", label: "CIRCULATION" }}),
        }};
        console.log(JSON.stringify(samples));
        """
    )

    assert {item[0] for item in result["bedroom"]} >= {"bed", "wardrobe"}
    assert {item[0] for item in result["kitchen"]} >= {"refrigerator", "appliance-cabinet"}
    assert {item[0] for item in result["storage"]} == {"storage-cabinet"}
    assert {item[0] for item in result["bathroom"]} >= {"bathroom-vanity", "mirror-cabinet"}
    assert {item[0] for item in result["living"]} >= {"sofa", "coffee-table", "tv-bench"}
    assert {item[0] for item in result["balcony"]} >= {"washer"}
    assert result["circulation"] == []


def test_2d_furniture_pointer_selection_reads_the_rendered_data_attribute() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    handler = source.split("function layoutPointerDown", 1)[1].split(
        "function layoutPointerMove", 1
    )[0]

    assert 'target.getAttribute("data-furniture-2d-id")' in handler


def test_catalog_resolution_keeps_each_room_furniture_as_a_unique_scene_instance() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ createFurniture2DItem, mergeCatalogFurniture }} from {json.dumps(module_uri)};
        const first = createFurniture2DItem("flower-pots-planter", "floor", {{
          id: "living-plant",
          roomId: "living",
          xCm: 120,
          yCm: 80,
        }});
        const second = createFurniture2DItem("flower-pots-planter", "floor", {{
          id: "balcony-plant",
          roomId: "balcony",
          xCm: -220,
          yCm: -410,
        }});
        const catalog = {{
          furniture_id: "catalog-plant",
          normalized_type: "flower-pots-planter",
          model_url: "/models/plant.glb",
          size_cm: {{ width: 19, depth: 19, height: 24 }},
        }};
        console.log(JSON.stringify({{
          first: mergeCatalogFurniture(first, catalog),
          second: mergeCatalogFurniture(second, catalog),
        }}));
        """
    )

    assert result["first"]["furniture_id"] == "living-plant"
    assert result["second"]["furniture_id"] == "balcony-plant"
    assert result["first"]["catalog_furniture_id"] == "catalog-plant"
    assert result["second"]["catalog_furniture_id"] == "catalog-plant"
    assert result["first"]["position_cm"] != result["second"]["position_cm"]
    assert result["first"]["size_cm"] == {"width": 35, "depth": 35, "height": 85}


def test_every_room_questionnaire_furniture_choice_has_a_2d_icon_variant() -> None:
    layout_uri = (STATIC / "scene_layout2d.js").as_uri()
    requirements_uri = (STATIC / "scene_requirements.js").as_uri()
    scene_source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    label_map = {
        label: (kind, variant)
        for label, kind, variant in re.findall(
            r'"([^"]+)":\s*\[\s*"([^"]+)",\s*"([^"]+)"\s*\]',
            scene_source,
        )
    }
    result = run_workflow_script(
        f"""
        import {{ FURNITURE_2D_LIBRARY, createFurniture2DItem }} from {json.dumps(layout_uri)};
        import {{ ROOM_QUESTION_TEMPLATES }} from {json.dumps(requirements_uri)};

        const choices = [...new Set(Object.values(ROOM_QUESTION_TEMPLATES).flatMap((template) => template.furniture))];
        const libraryKeys = new Set(FURNITURE_2D_LIBRARY.flatMap((category) =>
          category.variants.map((variant) => `${{category.type}}/${{variant.id}}`)
        ));
        const samples = [
          createFurniture2DItem("bedside-table", "compact"),
          createFurniture2DItem("kitchen-island", "standard"),
          createFurniture2DItem("bathroom-vanity", "standard"),
        ];
        console.log(JSON.stringify({{ choices, libraryKeys: [...libraryKeys], samples }}));
        """
    )

    missing_labels = [label for label in result["choices"] if label not in label_map]
    missing_variants = [
        label for label in result["choices"]
        if label in label_map and f"{label_map[label][0]}/{label_map[label][1]}" not in result["libraryKeys"]
    ]
    assert missing_labels == []
    assert missing_variants == []
    assert {item["label"] for item in result["samples"]} == {"床頭櫃", "廚房中島", "浴櫃"}


def test_2d_form_replacement_preserves_position_and_uses_new_real_size() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          createFurniture2DItem,
          replaceFurniture2DItem,
        }} from {json.dumps(module_uri)};
        const original = createFurniture2DItem("dining-table", "rect-4", {{
          id: "table-1",
          xCm: 135,
          yCm: -80,
          roomId: "dining-room",
        }});
        const replacement = replaceFurniture2DItem(original, "dining-table", "round-4");
        console.log(JSON.stringify(replacement));
        """
    )

    assert result["id"] == "table-1"
    assert result["xCm"] == 135
    assert result["yCm"] == -80
    assert result["roomId"] == "dining-room"
    assert result["label"] == "四人圓桌"
    assert result["widthCm"] == 110
    assert result["depthCm"] == 110


def test_2d_payload_marks_user_required_furniture_for_server_resolution() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          createFurniture2DItem,
          replaceFurniture2DItem,
          toSceneFurniture,
        }} from {json.dumps(module_uri)};
        const original = createFurniture2DItem("sofa", "compact", {{
          id: "living-sofa",
          userRequired: true,
        }});
        const replacement = replaceFurniture2DItem(original, "sofa", "standard");
        const payload = toSceneFurniture(replacement, {{ positionLocked: false }});
        console.log(JSON.stringify({{
          preservedOnReplacement: replacement.userRequired,
          userRequired: payload.user_required,
          userSpecified: payload.user_specified,
          positionLocked: payload.position_locked,
        }}));
        """
    )

    assert result == {
        "preservedOnReplacement": True,
        "userRequired": True,
        "userSpecified": False,
        "positionLocked": False,
    }


def test_room_usage_recommends_visible_appliances_and_decor_without_overriding_empty_rooms() -> None:
    module_uri = (STATIC / "scene_layout2d.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{
          FURNITURE_2D_LIBRARY,
          recommendCompanionFurniture,
        }} from {json.dumps(module_uri)};
        const living = recommendCompanionFurniture("living_room", ["sofa"]);
        const bedroom = recommendCompanionFurniture("bedroom", ["bed"]);
        const kitchen = recommendCompanionFurniture("kitchen", ["dining-table"]);
        const empty = recommendCompanionFurniture("living_room", []);
        const libraryTypes = FURNITURE_2D_LIBRARY.map((item) => item.type);
        console.log(JSON.stringify({{ living, bedroom, kitchen, empty, libraryTypes }}));
        """
    )

    assert "flower-pots-planter" in result["libraryTypes"]
    assert "bedside-table" in result["libraryTypes"]
    assert any(item["type"] == "flower-pots-planter" for item in result["living"])
    assert any(item["type"] == "bedside-table" for item in result["bedroom"])
    assert any(item["type"] == "refrigerator" for item in result["kitchen"])
    assert result["empty"] == []


def test_2d_library_exposes_an_explicit_add_mode_separate_from_replacement() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-2d-furniture-mode"' in html
    assert "state.selectedFurniture2dId = null" in source
    assert "現在是新增模式" in source


def test_space_confirmation_can_add_a_missed_room_and_invalidates_downstream() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-missed-room"' in html
    assert "function addMissedRoom()" in source
    assert "room-manual-" in source
    assert "invalidateDownstreamFrom(\"space_confirmation\"" in source
    assert "請拖曳節點、命名並重新確認空間與結構" in source


def test_room_size_is_computed_from_dragged_polygon_instead_of_typed() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-width-cm"' not in html
    assert 'id="room-depth-cm"' not in html
    assert "拖曳左圖紫色節點後，尺寸與面積會自動重新計算。" in html
    assert "系統依目前框選計算" in source
    assert 'font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>' in source


def test_structure_mode_hides_room_overlays_and_explains_selected_lines() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'spaceMode: "rooms"' in source
    assert 'state.spaceMode === "rooms"' in source
    assert 'state.spaceMode = rooms ? "rooms" : "structure"' in source
    assert "橘黃色線＝目前選取的結構" in html
    assert "橘色門弧＝系統偵測的門候選" in html
    assert '$("#show-all-rooms").hidden = !rooms' in source
    assert "點選牆、門、窗、樑或柱後會以橘黃色標示" in source


def test_door_review_exposes_add_select_edit_rotate_and_delete_controls() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-structure-section="door"' in html
    assert 'id="add-active-structure"' in html
    assert 'id="structure-review-list"' in html
    assert 'id="apply-structure-size"' in html
    assert 'id="flip-selected-door"' in html
    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert 'id="delete-selected-structure"' in html
    assert "function renderStructureReviewList()" in source
    assert 'data-structure-review="${escapeHtml(item.id)}"' in source
    assert '["door", "window", "column"].includes(state.structureTool)' in source
    assert 'state.selectedStructure = { id: item.id, kind: tool }' in source


def test_structure_editor_uses_separate_pages_and_exposes_window_controls() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    for kind in ("door", "window", "wall", "beam", "column"):
        assert f'data-structure-section="{kind}"' in html
    assert 'id="structure-review-title"' in html
    assert 'id="structure-review-progress"' in html
    assert 'id="structure-review-list"' in html
    assert 'id="add-active-structure"' in html
    assert 'id="window-sill-height-field"' in html
    assert 'id="window-sill-height-cm"' in html
    assert 'activeStructureKind: "door"' in source
    assert "function setActiveStructureKind(kind)" in source
    assert "function renderStructureReviewList()" in source
    assert "function confirmStructure(kind, structureId)" in source
    assert 'data-confirm-structure="${escapeHtml(item.id)}"' in source
    assert "item.sill_height_m = sillHeightM" in source
    assert 'state.activeStructureKind = tool' in source


def test_each_door_requires_explicit_confirmation_and_supports_hinge_end_reversal() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="add-active-structure"' in html
    assert 'id="structure-review-progress"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'data-confirm-structure="${escapeHtml(item.id)}"' in source
    assert "function confirmDoor(doorId)" in source
    assert "function rotateSelectedDoor180()" in source
    assert "[item.start, item.end] = [item.end, item.start]" in source
    assert "pendingStructureKind" in source
    assert "一鍵確認全部門" in html
    assert "door.confirmed = false" in source


def test_add_door_mode_takes_priority_over_wall_selection_and_can_be_cancelled() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    pointer_handler = source[source.index("function spacePointerDown"):source.index("function spacePointerMove")]

    assert 'id="cancel-structure-interaction"' in html
    assert "function cancelStructureInteraction()" in source
    assert '["door", "window", "column"].includes(state.structureTool)' in pointer_handler
    assert pointer_handler.index('["door", "window", "column"].includes(state.structureTool)') < pointer_handler.index(
        'const structureNode = event.target.closest("[data-structure-id]")'
    )
    assert "state.selectedStructure = null" in source
    assert "已取消目前操作與結構選取" in source


def test_selected_door_has_large_drag_target_and_resizable_endpoint_handles() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="opening-width-controls"' in html
    assert 'id="opening-width-slider"' in html
    assert 'data-opening-width-step="-5"' in html
    assert 'data-opening-width-step="5"' in html
    assert 'pointer-events="stroke"' in source
    assert 'data-door-handle="start"' in source
    assert 'data-door-handle="end"' in source
    assert "item.swing_end ? meterToPixel(item.swing_end)" in source
    assert "${swingEnd.x} ${swingEnd.y}" in source
    assert "const swingCross =" in source
    assert "swingCross >= 0 ? 1 : 0" in source
    assert 'data-door-move-handle="true"' in source
    assert "let doorResizeDrag = null" in source
    assert "function resizeOpeningFromPointer(" in source
    assert "function snapOpeningToHostWall(" in source
    assert "function setSelectedOpeningWidthCm(" in source
    assert 'openingWidthSlider.addEventListener("input"' in source
    assert "nearestPointOnLine(requested, item.start, item.end)" in source
    assert "item.width_m = Math.hypot(" in source
    assert "item.confirmed = false" in source


def test_selected_window_has_drag_handles_wall_snap_and_live_width_control() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="opening-width-controls"' in html
    assert 'id="opening-width-label"' in html
    assert 'id="opening-width-slider"' in html
    assert 'data-opening-handle="start"' in source
    assert 'data-opening-handle="end"' in source
    assert 'data-opening-move-handle="true"' in source
    assert '["door", "window"].includes(state.selectedStructure.kind)' in source


def test_structure_legend_uses_heading_space_and_window_markers_match_review_numbers() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    stage_start = html.index('id="space-plan-stage"')
    stage_end = html.index('id="space-plan-caption"')
    heading_html = _space_heading_html(html)
    stage_html = html[stage_start:stage_end]

    assert 'id="plan-structure-legend"' in heading_html
    assert "hidden" in heading_html
    assert 'id="plan-structure-legend"' not in stage_html
    assert 'data-window-number="${index + 1}"' in source
    assert '$("#plan-structure-legend").hidden = rooms;' in source


def test_room_editor_is_embedded_in_the_plan_heading() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")
    stage_start = html.index('id="space-plan-stage"')
    heading_html = _space_heading_html(html)

    assert 'class="rp-plan-heading-tools"' in heading_html
    assert 'id="room-editor"' in heading_html
    assert 'class="rp-editor-box rp-room-toolbar-editor"' in heading_html
    assert 'id="room-editor"' not in html[stage_start:]
    assert ".rp-room-floating-editor" not in css
    assert "#space-step .rp-plan-heading-tools" in css
    assert "#space-step .rp-room-editor-summary" in css
    assert "display: contents" in css
    assert "#space-step #show-all-rooms" in css
    assert "height: 38px" in css


def test_all_structure_kinds_share_numbering_sizing_and_crud_contract() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-structure-number-kind="${kind}"' in source
    for kind in ("wall", "door", "window", "beam", "column"):
        assert f'structureNumberMarkerSvg("{kind}"' in source
    assert 'id="selected-structure-length-field"' in html
    assert 'id="selected-structure-depth-field"' in html
    assert 'id="structure-3d-preview-panel"' in html
    assert 'id="structure-3d-preview"' in html
    assert "createStructurePreview" in source
    assert "structurePreview.render" in source
    assert "walls: state.structures.walls" in source
    assert "planWidthM" in source
    assert "planDepthM" in source
    assert "deleteSelectedStructure" in source
    assert "confirmStructure" in source
    assert "function resizeOpeningFromPointer(" in source
    assert "function setSelectedOpeningWidthCm(" in source
    assert "snapOpeningToHostWall(item" in source
    assert "拖曳此端調整窗寬" in source


def test_beam_supports_drag_to_draw_true_width_and_3d_ceiling_placement() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="add-white-model-beam"' in html
    assert 'id="white-model-beam-width-cm"' in html
    assert 'id="white-model-beam-drop-cm"' in html
    assert "beamDragGeometry" in source
    assert "let structureCreateDrag = null" in source
    assert "function beamBandSvg(" in source
    assert 'data-beam-handle="start"' in source
    assert 'data-beam-handle="end"' in source
    assert "function finishBeamCreateDrag(" in source
    assert "whiteViewer.beginBeamPlacement" in source
    assert "function beginBeamPlacement(" in viewer
    assert "beamPlacementRequest" in viewer
    assert "beginBeamPlacement," in viewer
    assert '$("#selected-structure-length-cm").readOnly = isBeam' in source
    assert "element.structureLengthInput" not in source


def test_room_confirmation_is_isolated_and_supports_confirm_merge_and_split() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="room-confirmation-progress"' in html
    assert 'data-room-geometry-mode="merge"' in html
    assert 'data-room-geometry-mode="split"' in html
    assert 'id="apply-room-merge"' in html
    assert 'id="cancel-room-geometry"' in html
    assert 'data-confirm-room="${escapeHtml(room.id)}"' in source
    assert 'state.spaceMode === "structure" ? renderStructureSvg() : ""' in source
    assert "function confirmRoom(roomId)" in source
    assert "function mergeSelectedRooms()" in source
    assert "function splitSelectedRoom(start, end)" in source
    assert "state.splitPoints.length === 2" in source
    assert "state.rooms.every((room) => room.confirmed === true)" in source
    assert 'id="rooms-confirmed"' not in html


def test_room_polygon_nodes_can_be_merged_or_split_on_an_edge() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'data-room-node-mode="merge"' in html
    assert 'data-room-node-mode="split"' in html
    assert 'id="apply-node-merge"' in html
    assert 'id="cancel-node-edit"' in html
    assert "function mergeSelectedRoomNodes()" in source
    assert "function insertRoomNodeAt(point)" in source
    assert "function nearestPointOnRoomEdge(" in source
    assert "state.selectedRoomNodeIndices.length === 2" in source
    assert 'data-room-point="${index}"' in source
    assert "room.confirmed = false" in source


def test_manual_upstream_edits_clear_stale_3d_steps_before_saving() -> None:
    workflow_uri = (STATIC / "scene_workflow.js").as_uri()
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    result = run_workflow_script(
        f"""
        import {{ createWorkflow }} from {json.dumps(workflow_uri)};
        const workflow = createWorkflow({{ projectId: "invalidate-project", storage: null }});
        workflow.complete("project", {{ name: "驗收" }});
        workflow.complete("upload", {{ filename: "plan.png" }});
        workflow.complete("recognition", {{ engine: "cody" }});
        workflow.complete("calibration", {{ distanceCm: 630 }});
        workflow.complete("space_confirmation", {{
          roomsConfirmed: true,
          structureConfirmed: true,
          proportionsConfirmed: true,
        }});
        workflow.complete("requirements", {{ basicConfirmed: true, roomsResolved: true }});
        workflow.complete("layout_2d", {{ confirmed: true }});
        workflow.complete("white_model_3d", {{
          confirmed: true,
          expectedFurnitureCount: 1,
          visibleFurnitureCount: 1,
        }});
        workflow.complete("realistic_3d", {{ confirmed: true }});
        const before = workflow.completed;
        workflow.invalidateFrom("layout_2d");
        console.log(JSON.stringify({{ before, after: workflow.completed, canEnter3d: workflow.goTo("white_model_3d") }}));
        """
    )

    assert "realistic_3d" in result["before"]
    assert result["after"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
        "space_confirmation",
        "requirements",
    ]
    assert result["canEnter3d"] is False
    assert "invalidateDownstreamFrom(\"layout_2d\"" in source


def test_requirements_gate_allows_explicit_keep_existing_for_unfilled_rooms() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ requirementsGate }} from {json.dumps(module_uri)};
        const rooms = [{{ id: "living" }}, {{ id: "bedroom" }}];
        const blocked = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms,
          answers: {{ living: {{ confirmed: true, uses: ["日常休息"] }} }},
          keepExistingRoomIds: [],
        }});
        const allowed = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms,
          answers: {{ living: {{ confirmed: true, uses: ["日常休息"] }} }},
          keepExistingRoomIds: ["bedroom"],
        }});
        console.log(JSON.stringify({{ blocked, allowed }}));
        """
    )

    assert result["blocked"]["ready"] is False
    assert result["blocked"]["unresolvedRoomIds"] == ["bedroom"]
    assert result["allowed"]["ready"] is True


def test_requirements_gate_rejects_a_confirmed_room_without_a_usage_choice() -> None:
    module_uri = (STATIC / "scene_requirements.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ requirementsGate }} from {json.dumps(module_uri)};
        const result = requirementsGate({{
          basic: {{ confirmed: true }},
          rooms: [{{ id: "living" }}],
          answers: {{ living: {{ confirmed: true, uses: [], furniture: [] }} }},
        }});
        console.log(JSON.stringify(result));
        """
    )

    assert result["ready"] is False
    assert result["unresolvedRoomIds"] == ["living"]


def test_scene_does_not_force_placeholder_furniture_for_an_empty_plan() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "目前沒有指定家具，先放入可刪除的雙人沙發" not in source
    assert "selected_furniture_exact: true" in source


def test_confirmed_rooms_and_structures_are_the_only_3d_floorplan_source() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function confirmedFloorplanEditor()" in controller
    assert "floorplan_editor: confirmedFloorplanEditor()" in controller
    assert "floorplan_dxf_text: state.confirmedFloorplan?.dxf_text" not in controller
    assert "floorplan.beam_segments" in viewer
    assert "floorplan.columns" in viewer
    assert 'id="selected-structure-editor"' in (STATIC / "scene.html").read_text(encoding="utf-8")
    assert "function deleteSelectedStructure()" in controller
    assert "function applySelectedStructureSize()" in controller
    assert "structureDrag" in controller


def test_dxf_rooms_and_structures_are_normalized_for_the_corner_origin_editor() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "floorplan.room_regions || []" in controller
    assert "room.polygon_m || room.polygon || room.exterior" in controller
    assert "room.id || room.room_id" in controller
    assert "floorplan.wall_segments || floorplan.plan_segments" in controller
    assert "floorplan.door_segments || []" in controller
    assert "floorplan.window_segments || []" in controller
    assert "x + (centered ? widthM / 2 : 0)" in controller
    assert "y + (centered ? depthM / 2 : 0)" in controller
    assert "configureDxfPreview" in controller


def test_2d_automatic_and_manual_positions_are_validated_by_the_engine() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/layout"' in source
    assert 'api("/api/scene/validate"' in source
    assert "placement_room_id" in source
    assert "floorplan_editor: confirmedFloorplanEditor()" in source


def test_all_18_style_cards_build_complete_four_colour_pbr_style_packs() -> None:
    module_uri = (STATIC / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ STYLE_PACKS, applyStylePack }} from {json.dumps(module_uri)};
        const scene = {{
          wall: {{ styleLocked: true, color: "#111111", material: "old-wall" }},
          floor: {{ styleLocked: true, color: "#222222", material: "old-floor" }},
          furniture: [
            {{ id: "locked", styleLocked: true, material: {{ color: "#123456" }} }},
            {{ id: "open", styleLocked: false, material: {{ color: "#ffffff" }} }},
          ],
        }};
        const applied = applyStylePack(scene, STYLE_PACKS[0]);
        console.log(JSON.stringify({{
          count: STYLE_PACKS.length,
          complete: STYLE_PACKS.every((pack) =>
            pack.palette.length === 4
            && pack.sourceImage.startsWith("/static/style_cards/")
            && pack.wall.pbr
            && pack.wall.surfaceOption
            && pack.floor.pbr
            && pack.floor.surfaceOption
            && pack.furniture.materialLanguage.length >= 3
            && Object.keys(pack.furnitureRules).length >= 4
            && pack.decorRules.length >= 3
            && Object.keys(pack.placementRules).length >= 2
            && pack.lighting.hdr
            && pack.lighting.profile
            && pack.lighting.colorTemperatureK > 0
            && pack.rendering.gtao.enabled
          ),
          appliedRules: Boolean(
            applied.furnitureRules
            && applied.decorRules
            && applied.placementRules
            && applied.sourceImage
          ),
          paletteMapped: STYLE_PACKS.every((pack) =>
            pack.furniture.color === pack.palette[1]
            && pack.floor.color === pack.palette[2]
            && pack.furniture.accent === pack.palette[3]
          ),
          uniqueCardRules: ["scandinavian", "japanese", "modern_minimal", "cream", "industrial", "american"]
            .every((styleId) => {{
              const rules = STYLE_PACKS
                .filter((pack) => pack.styleId === styleId)
                .map((pack) => JSON.stringify([pack.furnitureRules.signature, pack.decorRules]));
              return new Set(rules).size === 3;
            }}),
          modernLuxeLighting: STYLE_PACKS.find((pack) => pack.id === "american_3").lighting.profile,
          wall: applied.wall,
          floor: applied.floor,
          lockedColor: applied.furniture[0].material.color,
          openColor: applied.furniture[1].material.color,
        }}));
        """
    )

    assert result["count"] == 18
    assert result["complete"] is True
    assert result["appliedRules"] is True
    assert result["paletteMapped"] is True
    assert result["uniqueCardRules"] is True
    assert result["modernLuxeLighting"] == "gallery_neutral"
    assert result["wall"]["color"] != "#111111"
    assert result["wall"]["material"] != "old-wall"
    assert result["wall"]["styleLocked"] is False
    assert result["floor"]["color"] != "#222222"
    assert result["floor"]["material"] != "old-floor"
    assert result["floor"]["styleLocked"] is False
    assert result["lockedColor"] == "#123456"
    assert result["openColor"] != "#ffffff"


def test_realistic_viewer_uses_a_real_pbr_environment_and_gtao_pipeline() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "RoomEnvironment" in viewer
    assert "PMREMGenerator" in viewer
    assert "scene.environment =" in viewer
    assert "lighting.hdr" in viewer
    assert "generatedHdrEnvironment" in viewer
    assert "pmremGenerator.fromScene(environmentScene" in viewer
    assert "activeHdrProfile" in viewer
    assert "EffectComposer" in viewer
    assert "RenderPass" in viewer
    assert "GTAOPass" in viewer
    assert "OutputPass" in viewer
    assert "composer.render" in viewer
    assert "ACESFilmicToneMapping" in viewer
    assert "render-performance" in viewer
    assert "wall_color_hex" in controller
    assert "floor_color_hex" in controller


def test_style_switch_changes_unlocked_models_and_material_surface_types() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="wall-material"' in html
    assert 'id="floor-material"' in html
    assert "replaceUnlockedFurnitureForStyle" in controller
    assert "style=${encodeURIComponent(pack.styleId)}" in controller
    assert "item.user_specified || item.model_locked" in controller
    assert "design_choices.wall_option = resolveSurfaceOption(" in controller
    assert "design_choices.floor_option = resolveSurfaceOption(" in controller
    assert "selected.material_override" in controller
    assert "createMaterialBoundarySurfaces" in viewer
    assert "createRoomSurfaceOverrides" in viewer
    assert "wallMaterialResolver" in viewer
    assert "sceneData.surface_overrides" in controller
    assert "state.sceneData.surface_overrides = []" in controller
    assert "state.sceneData.material_boundary = null" in controller
    assert "state.materialBoundary = null" in controller
    assert 'option value="surface"' not in html
    assert 'id="material-boundary-position"' in html
    assert 'id="material-boundary-direction"' in html
    assert "function removeMaterialBoundary()" in controller


def test_3d_furniture_can_be_deleted_and_each_item_keeps_its_own_material_override() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'id="delete-white-model-furniture"' in html
    assert 'id="delete-realistic-furniture"' in html
    assert "function deleteSelectedSceneFurniture()" in controller
    assert "objects.splice(state.selectedSceneIndex, 1)" in controller
    assert "function saveSelectedSceneAppearance()" in controller
    assert "function loadSelectedSceneAppearance()" in controller


def test_3d_catalog_supports_engine_validated_replacement_addition_and_final_gate() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'data-replace-furniture-id="' in controller
    assert 'data-add-furniture-id="' in controller
    assert "function addSceneFurniture(" in controller
    assert "whiteViewer.beginPlacement" in controller
    assert 'api("/api/scene/validate"' in controller
    assert 'const finalValidation = await api("/api/scene/layout"' in controller
    assert "item.placement_failed || !item.position_locked" in controller
    assert "function beginPlacement(" in viewer
    assert 'renderer.domElement.style.cursor = "crosshair"' in viewer


def test_ceiling_conflicts_use_real_obstruction_geometry_and_installation_depth() -> None:
    module_uri = (STATIC / "scene_style_packs.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ detectCeilingConflicts }} from {json.dumps(module_uri)};
        const result = detectCeilingConflicts({{
          ceilingStyle: "cove",
          roomHeightCm: 280,
          beams: [{{
            id: "beam-1",
            kind: "beam",
            label: "樑 1",
            topCm: 280,
            bottomCm: 240,
            estimated: true,
          }}],
          cabinets: [{{
            id: "cabinet-1",
            kind: "cabinet",
            label: "高櫃",
            topCm: 265,
          }}],
          lights: [{{
            id: "downlight",
            kind: "light",
            label: "崁燈",
            requiredPlenumCm: 12,
          }}],
        }});
        console.log(JSON.stringify(result));
        """
    )

    assert result["finishedHeightCm"] == 262
    assert [item["objectId"] for item in result["conflicts"]] == [
        "beam-1",
        "cabinet-1",
    ]
    assert "樑底 240 cm" in result["conflicts"][0]["reason"]
    assert "圖面估計" in result["conflicts"][0]["reason"]
    assert result["conflicts"][1]["overlapCm"] == 3


def test_ceiling_and_light_choices_create_distinct_three_geometry() -> None:
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "function createCeilingGeometry(" in viewer
    assert 'ceilingStyle === "cove"' in viewer
    assert 'ceilingStyle === "floating"' in viewer
    assert 'ceilingStyle === "linear"' in viewer
    assert 'ceilingStyle === "wood-grid"' in viewer
    assert "function createStyleLights(" in viewer
    assert 'lightStyle === "track"' in viewer
    assert 'lightStyle === "downlight"' in viewer
    assert 'lightStyle === "paper"' in viewer
    assert "keyLight.shadow.mapSize.set(shadowMapSize, shadowMapSize)" in viewer


def test_viewer_never_silently_drops_missing_furniture_and_lock_keeps_zoom() -> None:
    source = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert "createFallbackFurnitureProxy" in source
    assert "if (item.placement_failed)" in source
    assert "家具位置無法通過碰撞與淨空檢查" in source
    assert "visibleFurnitureCount" in source
    assert "fallbackFurnitureCount" in source
    assert "controls.enableRotate = false" in source
    assert "controls.enablePan = false" in source
    assert "controls.enableZoom = true" in source
    assert "getDiagnostics" in source
    assert "selectObjectByIndex" in source


def test_floor01_repair_controls_cover_openings_questionnaire_layout_and_3d_editing() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    viewer = (STATIC / "scene_viewer.js").read_text(encoding="utf-8")

    assert 'id="rotate-selected-structure-left"' in html
    assert 'id="rotate-selected-structure-right"' in html
    assert "rotateSelectedStructure(-15)" in controller
    assert "rotateSelectedStructure(15)" in controller
    assert 'id="flip-selected-door"' in html
    assert 'id="rotate-selected-door-180"' in html
    assert 'class="rp-questionnaire-workspace"' in html
    assert 'id="requirements-plan-stage"' not in html
    assert 'id="room-furniture-select"' in html
    assert "selectedOptions" in controller
    assert 'id="layout-room-filter"' in html
    assert "state.activeLayoutRoomId" in controller
    assert "placement_room_id: room.id" in controller
    assert 'data-object-rotate="-15"' in viewer
    assert 'data-object-rotate="15"' in viewer
    assert "Shift+R 反向 15 度" in viewer


def test_realtime_style_material_choices_are_grouped_by_style_with_previews() -> None:
    html = (STATIC / "scene.html").read_text(encoding="utf-8")
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    packs = (STATIC / "scene_style_packs.js").read_text(encoding="utf-8")

    assert "STYLE_MATERIAL_OPTIONS" in packs
    assert "materialPreview" in packs
    assert 'id="wall-material-grouped"' in html
    assert 'id="floor-material-grouped"' in html
    assert "renderGroupedMaterialOptions" in controller
    assert "data-material-preview" in controller
    assert "3D 上即時預覽此風格的牆面、地板與燈光" in html


def test_realtime_style_cards_show_reference_images_and_sync_full_scene_rules() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    css = (STATIC / "site.css").read_text(encoding="utf-8")

    assert 'class="rp-style-card-preview"' in controller
    assert 'src="${escapeHtml(pack.sourceImage)}"' in controller
    assert "furniture_rules: pack.furnitureRules" in controller
    assert "decor_rules: pack.decorRules" in controller
    assert "placement_rules: pack.placementRules" in controller
    assert "source_image: pack.sourceImage" in controller
    assert "軟裝與擺放規則已載入" in controller
    assert "data-style-card-recommended" in controller
    assert ".rp-style-card-preview" in css


def test_removed_questionnaire_floorplan_overlay_does_not_break_event_binding() -> None:
    controller = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert "element.requirementsOverlay?.addEventListener" in controller


def test_project_resume_restores_flow_rooms_and_generated_scene() -> None:
    workflow_uri = (STATIC / "scene_workflow.js").as_uri()
    result = run_workflow_script(
        f"""
        import {{ createWorkflow, restoreWorkflow }} from {json.dumps(workflow_uri)};
        const storage = {{
          values: new Map(),
          getItem(key) {{ return this.values.get(key) ?? null; }},
          setItem(key, value) {{ this.values.set(key, value); }},
          removeItem(key) {{ this.values.delete(key); }},
        }};
        const original = createWorkflow({{ projectId: "resume-project", storage }});
        original.complete("project", {{ name: "續作專案" }});
        original.complete("upload", {{ filename: "plan.png" }});
        original.complete("recognition", {{ engine: "cody" }});
        original.complete("calibration", {{ distanceCm: 630 }});
        original.goTo("space_confirmation");
        const restored = restoreWorkflow({{
          projectId: "resume-project",
          storage: null,
          snapshot: original.toJSON(),
        }});
        console.log(JSON.stringify({{
          currentStep: restored.currentStep,
          completed: restored.completed,
          canEnterSpace: restored.canEnter("space_confirmation"),
        }}));
        """
    )

    assert result["currentStep"] == "space_confirmation"
    assert result["completed"] == [
        "project",
        "upload",
        "recognition",
        "calibration",
    ]
    assert result["canEnterSpace"] is True

    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")
    assert "_flow: state.workflow?.toJSON()" in source
    assert "confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null" in source
    assert "layout_2d: layoutIsLive ? { furniture: state.furniture2d } : null" in source
    assert "realistic_3d: realisticIsLive" in source
    assert "sceneData: state.sceneData" in source
    assert "renderRestoredStep()" in source
    assert "recoverConfirmedFloorplan" in source
    assert "await whiteViewer.loadScene(state.sceneData)" in source
    assert "await realisticViewer.loadScene(state.sceneData)" in source


def test_realtime_style_step_adds_soft_decor_and_flushes_persistence() -> None:
    source = (STATIC / "scene_v2.js").read_text(encoding="utf-8")

    assert 'api("/api/scene/decorate"' in source
    assert "for (const room of targetRooms)" in source
    assert "placement_room_id: room.id" in source
    assert "!state.keepExistingRoomIds.includes(room.id)" in source
    assert "await ensureAutomaticSoftDecor(pack)" in source
    assert "item.auto_decor_role && item.placement_failed" in source
    assert "saveSequence = saveSequence.catch" in source
    assert "roompilot.pending-save." in source
    assert "for (let attempt = 0; attempt < 3; attempt += 1)" in source
    assert "const pendingSave = localStorage.getItem(pendingSaveStorageKey())" in source
    assert "base_updated_at: state.project?.updated_at || null" in source
    assert "shouldReplayPendingSave(pendingSave, result.project)" in source
    assert "replay_pending: true" in source
    assert "error.status !== 409" in source
    assert "result = await api(`/api/projects/${state.projectId}`)" in source
    assert "較舊的離線暫存未覆蓋目前版本" in source
    assert 'window.addEventListener("beforeunload"' in source
    assert "pendingSaveCount === 0" in source
    assert "[element.scaleImage, element.spaceImage, element.requirementsImage, element.layoutImage]" in source
    assert ".filter(Boolean)" in source
