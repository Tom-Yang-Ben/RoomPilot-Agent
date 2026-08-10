# Graph Report - .  (2026-08-10)

## Corpus Check
- Large corpus: 2038 files · ~31,343,326 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 7315 nodes · 19731 edges · 304 communities (252 shown, 52 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 1181 edges (avg confidence: 0.66)
- Token cost: 739,070 input · 82,116 output

## Community Hubs (Navigation)
- Three.js Scene Bundle (minified)
- Frontend3D Vendor Bundle (minified)
- Scene V2 Room & Furniture UI
- Three.js Vector Math (minified)
- FastAPI Agent Endpoints
- Vendored JS (minified)
- Scene V2 Contract Tests
- Agent Furniture Doc Models
- Three.js Geometry (minified)
- Scene Calibration & Structure UI
- Furniture 2D Sync
- Room Questionnaire & Finishes UI
- Vendored JS (minified)
- Catalog Loading
- Scene Styling Helpers
- Calibration Tests
- Design Manual & LLM
- Layout & Scene Doc Models
- Delivery PDF Builder
- Surface & Color Options UI
- Floorplan to DXF
- 2D Plan Rendering
- GLB Asset Lookup
- Floorplan Vision Analysis
- Draco Decoder (vendored)
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201
- Community 202
- Community 203
- Community 204
- Community 205
- Community 206
- Community 208
- Community 209
- Community 210
- Community 211
- Community 212
- Community 213
- Community 215
- Community 216
- Community 218
- Community 219
- Community 220
- Community 221
- Community 222
- Community 223
- Community 224
- Community 229
- Community 230
- Community 231
- Community 232
- Community 233
- Community 234
- Community 235
- Community 236
- Community 237
- Community 238
- Community 239
- Community 240
- Community 241
- Community 242
- Community 244
- Community 245
- Community 246
- Community 248
- Community 250
- Community 251
- Community 252
- Community 253
- Community 254
- Community 255
- Community 256
- Community 257
- Community 258
- Community 259
- Community 260
- Community 261
- Community 262
- Community 263
- Community 264
- Community 265
- Community 266
- Community 267
- Community 268
- Community 269
- Community 270
- Community 271
- Community 272
- Community 273
- Community 274
- Community 275
- Community 276
- Community 277
- Community 278
- Community 279
- Community 280
- Community 281
- Community 282
- Community 283
- Community 284
- Community 285
- Community 286
- Community 291
- Community 293
- Community 296
- Community 297
- Community 298
- Community 299
- Community 300
- Community 301
- Community 303

## God Nodes (most connected - your core abstractions)
1. `bindEvents()` - 197 edges
2. `constructor()` - 193 edges
3. `r()` - 127 edges
4. `run_workflow_script()` - 116 edges
5. `scheduleSave()` - 111 edges
6. `t()` - 99 edges
7. `push()` - 98 edges
8. `ma()` - 94 edges
9. `n()` - 81 edges
10. `generate_layout()` - 78 edges

## Surprising Connections (you probably didn't know these)
- `資訊架構 (IA) 模板` --semantically_similar_to--> `Master 主流程 state machine`  [INFERRED] [semantically similar]
  VibeCoding_Workflow_Templates/02_ux_ui/information_architecture.md → agent-design-proposal.html
- `Scene handoff: engine owns geometry` --conceptually_related_to--> `Ancai geometry engine (authoritative)`  [INFERRED]
  backend/skills/roompilot-llm/SKILL.md → docs/使用者流程與系統架構圖.md
- `_apply_layout_label_suggestions()` --calls--> `center()`  [INFERRED]
  backend/floorplan/vision/rooms.py → VibeCoding_Workflow_Templates/03_architecture/diagrams/_tools/analyze_layout.py
- `test_family_of_folds_catalog_specific_types()` --calls--> `family_of()`  [EXTRACTED]
  tests/test_agent_knowledge.py → backend/agent/knowledge.py
- `_rect_room()` --calls--> `Wall`  [INFERRED]
  tests/test_generate_layout_characterization.py → backend/engine/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Owner Module Boundary Rules Across backend/** — backend_engine_agents_geometry_placement_engine, backend_floorplan_agents_floorplan_recognition, backend_server_agents_production_app, backend_upgrade3d_agents_confirmed_layout_to_3d [INFERRED 0.85]
- **RoomPilot 資料管線 (辨識→layout_json→選件→引擎→scene_json)** — readme_floorplan, readme_layout_json, readme_agent_module, readme_engine, readme_scene_json [EXTRACTED 1.00]
- **Master + 四個 Sub-agent 架構** — agent_design_proposal_master_state_machine, agent_design_proposal_furniture_agent, agent_design_proposal_validation_agent, agent_design_proposal_gen_pic_agent, agent_design_proposal_report_agent [EXTRACTED 1.00]
- **需求文件追溯鏈 (BRD→PRD→SRS→SAD)** — vibecoding_workflow_templates_01_requirements_brd, vibecoding_workflow_templates_01_requirements_prd, vibecoding_workflow_templates_01_requirements_srs, vibecoding_workflow_templates_03_architecture_sad [EXTRACTED 1.00]
- **C4 溝通級 drawio 圖規格族 (context/container/deployment/overview)** — vibecoding_workflow_templates_03_architecture_diagrams_c4_context_c4_system_context, vibecoding_workflow_templates_03_architecture_diagrams_c4_container_c4_container, vibecoding_workflow_templates_03_architecture_diagrams_deployment_topology_deployment_topology, vibecoding_workflow_templates_03_architecture_diagrams_solution_overview_solution_architecture_overview [EXTRACTED 0.75]
- **契約 SSOT 對齊 (api_spec/openapi/db_design/lld 狀態機)** — vibecoding_workflow_templates_04_design_api_spec_api_design_spec, vibecoding_workflow_templates_04_design_openapi_openapi_contract_skeleton, vibecoding_workflow_templates_04_design_db_design_db_design, vibecoding_workflow_templates_04_design_lld_state_machine_design_contract [EXTRACTED 0.75]
- **交付提案 PDF 生成鏈 (delivery skill → build_pdf → 打包 skill)** — backend_agent_skills_delivery_skill_delivery_proposal_skill, backend_agent_skills_delivery_skill_build_pdf_playwright, backend_agent_skills_roompilot_delivery_pdf_skill_delivery_pdf_package [EXTRACTED 0.75]
- **家具 Agent 選件→擺放→驗證→修復迴圈** — backend_agent_skills_requirements_skill_requirement_doc, backend_agent_skills_furniture_skill_select_prompt, backend_engine_readme_place_adjust_furniture, backend_agent_skills_validation_skill_engine_validate_tool, backend_agent_skills_furniture_skill_repair_prompt [INFERRED 0.75]
- **交付 PDF 三段流程 (蒐集→content.json→排版檢查)** — backend_agent_skills_roompilot_delivery_pdf_skill_collect_context, backend_agent_skills_roompilot_delivery_pdf_skill_content_json, backend_agent_skills_roompilot_delivery_pdf_skill_build_pdf, backend_agent_skills_roompilot_delivery_pdf_skill_preflight_check [EXTRACTED 0.75]
- **窗辨識三路 (純規則基準 vs 分割融合 vs VLM/SVM 否決)** — backend_floorplan_readme_rule_baseline, backend_floorplan_readme_seg_fusion, backend_floorplan_readme_vlm_svm_rejected [EXTRACTED 0.75]
- **Eight-step /scene workflow across UI, spec and overview** — backend_server_static_scene_workflow_page, docs_eight_step_workflow, docs_roompilot_6_8_agent_render_spec, docs_roompilot_current_version_overview, docs_user_flow_system_architecture [EXTRACTED 0.85]
- **Agent layered stack: Master, DocStore, Gateway, deterministic fallback** — docs_agent_master_state_machine, docs_agent_docstore_blackboard, docs_agent_openrouter_gateway, docs_agent_deterministic_fallback [EXTRACTED 0.75]
- **Deterministic placement engine: grid, OBB, clearance** — docs_placement_occupancy_grid, docs_placement_obb_collision, docs_placement_clearance_zone, docs_placement_determinism [EXTRACTED 0.85]
- **ben-dev 由多分支選擇性整合(Ancai引擎+Yen R3F+Cody辨識+Bella色卡儲存)** — docs_01_zhuanti_jindu_roompilot_ben_dev_gongneng_zhenghe_laiyuan_baogao_2026_07_19_ben_dev_branch, docs_01_zhuanti_jindu_roompilot_ben_dev_gongneng_zhenghe_laiyuan_baogao_2026_07_19_ancai_engine, docs_01_zhuanti_jindu_roompilot_ben_dev_gongneng_zhenghe_laiyuan_baogao_2026_07_19_yen_r3f_agent, docs_01_zhuanti_jindu_roompilot_ben_dev_gongneng_zhenghe_laiyuan_baogao_2026_07_19_cody_floorplan, docs_01_zhuanti_jindu_roompilot_ben_dev_gongneng_zhenghe_laiyuan_baogao_2026_07_19_bella_style_cards [EXTRACTED 0.75]
- **Agent選件→engine座標→前端顯示的權責邊界流程** — docs_contracts_agent_frontend_backend_contract_backend_agent, docs_contracts_agent_frontend_backend_contract_backend_engine, docs_contracts_agent_frontend_backend_contract_placement_resolution [EXTRACTED 0.75]
- **verified 型錄資料由 furniture_catalog_current 交付給 RAG/材質/落地燈流程** — docs_contracts_lighting_ceiling_catalog_contract_furniture_catalog_current, docs_contracts_floor_lamp_catalog_mapping_handoff_postgres_repo, docs_contracts_material_ceiling_reference_experience_contract_kai_postgres, docs_contracts_furniture_engine_room_requirements_contract_rag_contract [INFERRED 0.75]
- **PostgreSQL 分階段成為唯一資料來源** — docs_contracts_postgresql_catalog_read_phase1_catalog_read_phase1, docs_contracts_postgresql_project_store_phase3_project_store_phase3, docs_contracts_postgresql_runtime_catalog_phase4_runtime_catalog_phase4, docs_contracts_postgresql_single_source_phase5_single_source_phase5 [EXTRACTED 1.00]
- **家具 RAG 檢索管線 (embedding→search→rerank)** — docs_contracts_postgresql_furniture_embeddings_bge_m3, docs_contracts_postgresql_furniture_rag_runtime_search_filtered, docs_contracts_postgresql_furniture_rag_runtime_bge_reranker, docs_contracts_questionnaire_rag_handoff_rag_api [EXTRACTED 1.00]
- **placement_hints 貫穿首次擺位與所有重排端點的成組配對** — fix_2026_08_03_orientation_window_wall_placement_hints, fix_2026_08_02_floor_gap_orientation_wall_scene_service, fix_2026_08_03_reorder_hints_door_gap_main [EXTRACTED 1.00]
- **3D 場景增量更新與 GPU 記憶體邊界修復** — fix_2026_08_04_3d_scene_lifecycle_loadscene, fix_2026_08_04_3d_scene_lifecycle_glb_cache, fix_2026_08_04_3d_scene_lifecycle_incremental_ops, fix_2026_08_04_3d_scene_lifecycle_lru, fix_2026_08_04_3d_scene_lifecycle_context_loss [EXTRACTED 0.95]
- **官方 catalog 與 BGE-M3 向量 PostgreSQL 匯入流程** — scripts_sql_readme_import_official_catalog, scripts_sql_readme_import_embeddings, scripts_sql_readme_roompilot_schema, scripts_sql_readme_bge_m3_contract, scripts_sql_postgresql_17_10_guide_catalog_8675 [EXTRACTED 0.95]

## Communities (304 total, 52 thin omitted)

### Community 0 - "Three.js Scene Bundle (minified)"
Cohesion: 0.01
Nodes (261): absarc(), absellipse(), accumulate(), accumulateAdditive(), _activateAction(), ad(), _addInactiveAction(), _addInactiveBinding() (+253 more)

### Community 1 - "Frontend3D Vendor Bundle (minified)"
Cohesion: 0.03
Nodes (242): A(), Ac(), ae(), ai(), Al(), an(), ao(), ar() (+234 more)

### Community 2 - "Scene V2 Room & Furniture UI"
Cohesion: 0.02
Nodes (188): suggestSharedRoomAnswers(), validateColumnDimensionsCm(), activateWhiteFurnitureEditing(), activeCatalogSearchInput(), activeRoomPreferenceSuggestion(), addWhiteModelBeamFromWorld(), aiRenderRoomPayload(), aiRenderSceneForBrief() (+180 more)

### Community 3 - "Three.js Vector Math (minified)"
Cohesion: 0.03
Nodes (182): ie(), addScaledVector(), addVectors(), angleTo(), Ao(), applyAxisAngle(), applyBoneTransform(), applyEuler() (+174 more)

### Community 4 - "FastAPI Agent Endpoints"
Cohesion: 0.04
Nodes (137): agent_furniture_select(), agent_intake_answer(), agent_intake_start(), agent_pipeline_get_route(), agent_pipeline_reconcile_route(), agent_pipeline_start_route(), agent_pipeline_submit_route(), agent_pipeline_undo_route() (+129 more)

### Community 5 - "Vendored JS (minified)"
Cohesion: 0.04
Nodes (126): es(), g(), h(), Ir(), ja(), Ko(), Mr(), ne() (+118 more)

### Community 6 - "Scene V2 Contract Tests"
Cohesion: 0.02
Nodes (14): 逐房 A/B 合成:引擎因空間/門窗淨空自動移位、換小或移除個別家具,不該擋住 使用者。strict…, 房間編輯器只有一份，且掛在圖面標題工具列（backup/yen-2026-08-06 第 4 步）。…, 客廳選件(預設 + 一鍵測試隨機)要用 isQuestionnaireFallbackTypeMatch 比對, 否則電視櫃候選常是 tv-media-…, Keep a browser-breaking syntax error from hiding behind API-only tests., 修復換款或移除後 2D 清單與 3D 不得對不上(廚房鬼影)。bella 逐件增量 架構天生無鬼影:換款保持同一 furniture_id(只換…, 第 7 步色卡切換要有暫存記憶:同一場景版本只載一次(切色卡不重載、 不白屏),真的需要載入(換方案/場景重建)才重載並顯示請稍候; 並發載入以 in-…, _space_heading_html(), test_furniture_selection_matches_by_family_not_exact_type() (+6 more)

### Community 7 - "Agent Furniture Doc Models"
Cohesion: 0.04
Nodes (77): CandidateItem, CandidateListDoc, ChosenItem, FurnitureListDoc, HardViolation, LayoutDoc, PlacementHint, Docs 層（blackboard）：agent 流程共享文件的資料契約與文件庫。 對應架構提案的 Docs 層。每份文件都有… (+69 more)

### Community 8 - "Three.js Geometry (minified)"
Cohesion: 0.04
Nodes (117): add(), addGeometry(), addGroup(), addLevel(), am(), an(), apply(), assignFinalMaterial() (+109 more)

### Community 9 - "Scene Calibration & Structure UI"
Cohesion: 0.07
Nodes (106): calibrationActionState(), attachedOpenings(), activateWhiteWalkMode(), addDroppedStructure(), addFurnitureFromLibrary(), addMissedRoom(), applyAttachedOpeningUpdates(), applyCalibration() (+98 more)

### Community 10 - "Furniture 2D Sync"
Cohesion: 0.05
Nodes (99): numeric(), reconcileFurniture2dAfterGeneration(), removeFurniture2dBySceneObject(), sceneObjectId(), upsertFurniture2dFromSceneObject(), ensureSchemeB(), persistActiveScheme(), mergeCatalogFurniture() (+91 more)

### Community 11 - "Room Questionnaire & Finishes UI"
Cohesion: 0.04
Nodes (97): activeQuestionnairePack(), activeRoomFinishDraft(), activeRoomRequirement(), addMaterialDisplayOrdinals(), applyStyleChangeToRooms(), applyWholeHouseFinishes(), applyWholeHouseSurfaceConsistency(), catalogMaterialOptionsForPack() (+89 more)

### Community 12 - "Vendored JS (minified)"
Cohesion: 0.05
Nodes (91): hi(), jr(), me(), pe(), s(), t(), xc(), zc() (+83 more)

### Community 13 - "Catalog Loading"
Cohesion: 0.07
Nodes (67): build_official_catalog(), _load_json(), _load_manifest(), load_official_catalog(), official_catalog_diagnostics(), _official_style_candidates(), Any, Path (+59 more)

### Community 14 - "Scene Styling Helpers"
Cohesion: 0.05
Nodes (69): formatList(), formatTypeLabel(), allFloorSurfaces(), allWallSurfaces(), cardToneDescription(), CLEAN_FURNITURE_GROUPS, countFurnitureForStyle(), countFurnitureGroups() (+61 more)

### Community 15 - "Calibration Tests"
Cohesion: 0.04
Nodes (62): test_calibration_action_explains_what_is_missing(), test_calibration_action_is_ready_after_two_points_and_centimeter_value(), test_pointer_position_maps_from_displayed_preview_to_original_image_pixels(), test_two_image_points_and_known_length_create_scale_calibration(), test_manual_scale_confirmation_replaces_low_confidence_ocr_scale(), test_recognition_presentation_summarizes_rooms_and_only_prompts_uncertain_findings(), test_three_material_schemes_preserve_layout_and_only_override_compatible_slots(), test_wall_boxing_report_uses_one_change_for_customer_and_designer_views() (+54 more)

### Community 16 - "Design Manual & LLM"
Cohesion: 0.06
Nodes (33): DesignManualDoc, ManualSection, LLMGateway, parse_json_block(), Protocol, OpenRouter LLM gateway：文字與生圖統一走同一個 gateway。 依架構提案定案： - 文字 LLM 與生圖模型都經…, 文字與生圖的抽象介面；skills / subagents 只依賴這個協定。, 從 LLM 回覆中抽出第一個 JSON 物件；抽不出來丟 ``LLMError``。 (+25 more)

### Community 17 - "Layout & Scene Doc Models"
Cohesion: 0.07
Nodes (50): LayoutRoom, LockManifestDoc, SceneDoc, 回傳 {"prompt", "images", "stage"}；images 只含要被編輯的舊圖。, GenPicSkill, 生圖 skill：流程層。兩階段流程說明見同資料夾 ``SKILL.md``（無文字 LLM）。, 回傳 {"prompt", "lock_manifest", "images", "stage"}。, 知識型 skill（interior_designer / interior_design_principles）與 design_knowledge… (+42 more)

### Community 18 - "Delivery PDF Builder"
Cohesion: 0.06
Nodes (55): build_content(), _chapter_summaries(), _color_name_zh(), _dedupe_rows(), DeliverySkill, _furniture_phrase(), _hex_to_hls(), _material_zh() (+47 more)

### Community 19 - "Surface & Color Options UI"
Cohesion: 0.05
Nodes (55): applySurfaceChoiceToCurrentScene(), buildColorOptions(), buildSurfaceOptions(), COLOR_OPTION_PRESETS, colorOptionMatches(), colorOptions, confirmClientBrief(), DEFAULT_FURNITURE_BY_SPACE (+47 more)

### Community 20 - "Floorplan to DXF"
Cohesion: 0.06
Nodes (61): 執行 origin/cody 的牆、門、窗演算法並轉成 RoomPilot 公分契約。, recognize_cody_geometry(), _arc_crisp(), _arc_run(), binarize(), cluster_const(), Config, derive_door_scale() (+53 more)

### Community 21 - "2D Plan Rendering"
Cohesion: 0.06
Nodes (61): planCmToLayerPixel(), activePanelName(), activeSceneViewerForStep(), beamBandSvg(), captureConfirmedStructureSnapshot(), cmToPixel(), compareConfigurationFurniturePriority(), configurationBlockingFurniture() (+53 more)

### Community 22 - "GLB Asset Lookup"
Cohesion: 0.06
Nodes (51): _auto_decor_catalog_item(), _dataset_glb_lookup(), _external_glb_bytes(), _external_zip_entry_lookup(), _external_zip_entry_variants(), _furniture_detail_payload(), furniture_model(), _furniture_payload_cache() (+43 more)

### Community 23 - "Floorplan Vision Analysis"
Cohesion: 0.07
Nodes (54): analyze_floorplan_image(), 分析建商平面圖；不確定的尺度必須透過 confirmation seam 補齊。, _canonicalize_floorplan_cm(), confirm_floorplan_analysis(), _dxf_text(), Any, 人工確認閘門與 DXF／引擎 payload 邊界。, Convert the metres-based DXF parser geometry into the public cm contract. (+46 more)

### Community 24 - "Draco Decoder (vendored)"
Cohesion: 0.07
Nodes (23): w(), A(), ba(), C(), D(), E(), G(), h() (+15 more)

### Community 25 - "Community 25"
Cohesion: 0.09
Nodes (47): AdjustResult, apply_command(), _conflict(), _find(), move_placement(), 擺位微調 —— 依 `docs/擺位計算邏輯.md` §10(公分版)。 只吃**拆解好的結構化指令**,自然語言理解不在此層: {"action":…, §10.3 旋轉:角度正規化 ``rotation % 360``;不合法就**保持原角度**並回失敗原因。, 結構化指令派發(§10)。``add`` / ``remove`` 與相對方位指令未實作。 (+39 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (40): ImageResult, LLMError, OpenRouterGateway, RuntimeError, OpenRouter chat completions 薄封裝（文字＋圖像 modalities）。, LLM 呼叫失敗；``reason`` 是要能拿去「提示使用者失敗原因」的可讀訊息。, FakeChatGateway, 依序回覆腳本化 JSON 的文字假件（生圖不支援）。 (+32 more)

### Community 27 - "Community 27"
Cohesion: 0.07
Nodes (57): catalogFurnitureOffer(), rankCatalogFurniture(), applyVisualPreferencesToSpecs(), activeQuestionnaireRoom(), addQuestionnaireCatalogFurniture(), applyDefaultQuestionnaireFurnitureSelections(), applyVerifiedRandomQuestionnaireFurniture(), captureQuestionnaireFurniturePreference() (+49 more)

### Community 28 - "Community 28"
Cohesion: 0.07
Nodes (52): _curtain_catalog_item(), 前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。 傳 floorplan(含 wall_segments)可重建…, 依風格加入軟裝，所有最終座標仍由家具引擎決定。, scene_decorate(), scene_layout(), scene_provider_status(), build_questionnaire_prompt(), build_scene_payload() (+44 more)

### Community 29 - "Community 29"
Cohesion: 0.07
Nodes (39): ImageLibraryDoc, ImageRecord, PaletteOption, GenPicAgent, GenPicFailure, ImagePolicy, RuntimeError, Gen_Pic Agent：兩階段生圖與一次改圖（任務 5–6），含失敗政策執行。 失敗政策（定案，計數與切換由程式強制、不交給 LLM）： -… (+31 more)

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (52): scrollPageTop(), styleNameMap(), addToProposal(), applyLibraryFilters(), bootstrapModeOne(), buildSceneHandoffPayload(), COLOR_LABELS, data (+44 more)

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (52): PRESET_SURFACE_IDS, resolveSurfaceOption(), allowedLightsForCeiling(), allStepSixMaterialOptions(), allStepSixRoomSurfacesConfirmed(), applyLegacySurfaceOverrides(), applyQuestionnaireSurfaceOverridesToScene(), applyStylePackToScene() (+44 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (42): clearance_conflict_for(), _free_with_clearance(), _place_companion(), _place_generic(), 逐房擺位主流程 —— 依 `docs/擺位計算邏輯.md` §6.2、§8、§9.4(公分版)。 核心紀律:**LLM…, §8.1 副件:只准相對主件擺,三種情形一律略過並記 log,**寧缺勿亂**。 絕不退回泛用靠牆 —— 這是「床頭櫃不該流落到離床很遠的牆邊」的根治點。…, §8.2 泛用件:逐件靠牆(含淨空)×count,**放不下即止**。 主件放不下時,自足泛用件仍獨立擺出 —— 整房清空對使用者更差。, §9.4 房型規則產物的淨空覆核(``reverse=False``)。 房型規則層不認得淨空,由本層收尾。回傳「被移除、需退回剩件分流」的 template。 (+34 more)

### Community 33 - "Community 33"
Cohesion: 0.12
Nodes (50): EmbeddingRow, EmbeddingSource, load_catalog(), load_records(), main(), parse_args(), prepare_embedding_rows(), Any (+42 more)

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (49): 走 cody floorplan2room 全鏈路取房型語意，結果留在記憶體。 `docs/CODY_MAIN_SYNC_TODO.md` 第 2…, recognize_cody_rooms(), _apply_evidence(), _axis_segments(), _bridge_has_door_ink(), _bridge_zone(), build_rooms(), classify_rooms_dino() (+41 more)

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (45): _flip_parsed_z(), 把 dxf_parser 輸出的 z 軸取負。 DXF 的 y 軸朝北(俯視圖),three.js 的 +z 軸朝向觀察者(南)——…, _cluster_seg_groups(), _collect(), _collect_texts(), _entity_segments(), _hatch_rings(), _merge_window_segs() (+37 more)

### Community 36 - "Community 36"
Cohesion: 0.11
Nodes (46): placement_hints(), 讀引擎的 placement_failed → 寧缺勿亂 / 換小 / 移除 → 重擺至收斂。…, 確定性擺放提示:回 {instance_id|furniture_id: {"priority", "group"}}。…, resolve_placements(), generate_layout(), 家具座標一律由 furniture_engine 決定(柵格碰撞 + 淨空裁決)。 擺放邏輯(hints 啟用時,每件依序走第一個命中的路徑): 1.…, _size_cm(), PlaceFn (+38 more)

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (40): ambientLight, bounds, camera, chipNodes, chipsBox, dimCanvas, dimContext, dracoLoader (+32 more)

### Community 38 - "Community 38"
Cohesion: 0.08
Nodes (43): is_cabinet_type(), 該家具是否為「有櫃」收納類(用 normalized_type 記號判定)。, anchor_ts(), 沿邊錨點參數序列(§6.1)。 五定點是**歷史前綴**:先試它們,既有擺位的選點不變。定點全被踩掉才進…, build_raster_context(), _cabinet_front_strip(), _clamp_axis(), _floorplan_segments_cm() (+35 more)

### Community 39 - "Community 39"
Cohesion: 0.12
Nodes (44): generate_layout_by_room(), 依 ``placement_room_id`` 分組,**每間房各自在自己的邊界內**擺位。 原本 build_scene_payload 只呼叫一次…, _by_id(), _item(), _nearest_wall_gap(), _overlaps(), generate_layout 產品分支的特徵測試(characterization tests)。 用途:`docs/擺位計算邏輯.md`…, 最終確認(進入即時寫實):validate_only 一律照舊座標、絕不重排。合法件回報 合法;越界件回報失敗但位置**仍照舊,不塌成… (+36 more)

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (44): activateScheme(), allRoomsHaveSchemeSelections(), clone(), COLLECTIONS, compactDesignSchemesForSpace(), deleteSchemeB(), emptyScheme(), hasRenovationChanges() (+36 more)

### Community 41 - "Community 41"
Cohesion: 0.10
Nodes (31): DocKey, DocStore 的固定鍵。場景與家具清單以 ``:A`` / ``:B`` 帶變體。, RoomPilot Agent：Master state machine ＋ 四個 sub-agent（skills / tools 分層）。…, MasterConfig, MasterState, Master Agent：程式固定流程的 state machine（非 LLM）。 依架構提案定案，Master 的職責是流程控制而非智慧： -…, build_master(), Path (+23 more)

### Community 42 - "Community 42"
Cohesion: 0.11
Nodes (26): _compact_workflow_value(), _merge_dict(), ProjectStore, ProjectVersionConflict, Connection, Path, RuntimeError, ValueError (+18 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (41): REVIEW_REASON_LABELS, reviewItemsFromAnalysis(), reviewReasonLabel(), unresolvedReviewRooms(), orthogonalizeNearAxisEdges(), polygonArea(), repairLoadedRoomPolygon(), beamDragGeometry() (+33 more)

### Community 44 - "Community 44"
Cohesion: 0.07
Nodes (26): A(), AttributeOctahedronTransform(), AttributeQuantizationTransform(), AttributeTransformData(), B(), castObject(), Decoder(), DecoderBuffer() (+18 more)

### Community 45 - "Community 45"
Cohesion: 0.10
Nodes (41): finishesGate(), occupantsFromBasicAnswers(), questionnaireSummary(), questionsForIndividualRooms(), questionsForRooms(), ROOM_TO_VISUAL_SPACES, VISUAL_SPACE_LABELS, visualQuestionnaireProgress() (+33 more)

### Community 46 - "Community 46"
Cohesion: 0.12
Nodes (27): parse_query(), Any, Anthropic Structured Outputs adapter for Django's furniture query schema., _usage(), RagDependencyError, RagUpstreamError, build_system_prompt(), parse_query() (+19 more)

### Community 47 - "Community 47"
Cohesion: 0.09
Nodes (40): delivery_engine_status(), 排版引擎是否可用；不可用時回報可讀原因（不得假成功）。, _placed_objects(), 取出屬於此房間、且成功擺放的家具（跳過 placement_failed）。, _room_dims(), _assemble_store(), create_delivery_proposal(), create_design_manual() (+32 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (41): apply_floorplan2room_labels(), Any, 取房間在原圖像素空間的中心點。 三種房間各帶不同座標：OCR 標籤房間有 `bbox_px`（原圖像素）； `infer_rooms_from_walls`…, 把 cody floorplan2room 的房型語意套到 rooms[]，回傳實際套用筆數。 `docs/CODY_MAIN_SYNC_TODO.md` 第…, _room_centre_px(), fixture, cody floorplan2room 房型語意的記憶體橋接測試。 `docs/CODY_MAIN_SYNC_TODO.md` 第 2 點要求辨識預設走…, cody 的 room=「空間」代表證據不足，不該蓋掉既有判斷。 (+33 more)

### Community 49 - "Community 49"
Cohesion: 0.10
Nodes (38): _candidate_ids(), clear_cloud_model_caches(), cloud_model_status(), cloud_model_url(), _cloudfront_base_url(), _current_manifest_index(), _delivery_url_from_row(), _https_url() (+30 more)

### Community 50 - "Community 50"
Cohesion: 0.06
Nodes (27): catalog_item_matches_type_semantics(), choose_furniture_items(), 回傳 (選中的家具, 找不到可用型號的類型清單)。 找不到型號的類型必須回報 —— 使用者勾了「已選」卻默默消失,體驗上像 bug。, 阻擋型錄分類與模型語意明顯矛盾的候選，避免櫃體被當成床。, viewer 內聯 buildSegmentWalls:牆段切分、窗上下補實、踢腳板與每段頂蓋 直接建…, 已確認牆端點間 ≤ max(36, 2·牆厚) 的微縫以橋接牆補上;超過門檻的 大縫(真實通道)不得補。橋接為 SceneModel 的 junction-…, 補實件以 frameAllowance 讓出框位、厚度內縮 2·epsilon 防 z-fighting; 框件貼齊牆面(faceOffset 0),玻璃盒由…, 基底樓板外擴:兩個相距 26.9cm 的 region 外擴 14cm 後必須交疊, 蓋住牆帶與門檻(feedback.png… (+19 more)

### Community 51 - "Community 51"
Cohesion: 0.11
Nodes (38): 淨空區幾何(§9.2):指定面外緣往外延伸 ``depth`` 的 OBB,與家具同角度。 front／back…, zone_obb(), furnish_room(), 一間房的完整擺位(規格 §1.2 的 ⑤⑥⑦ 步)。 ``templates`` 的順序即擺放順序(規格 §12 第 3 點:選件順序即擺放順序)。, front_vector(), Point, 該角度下家具正面的世界方向 f = (sin r, −cos r)。 與 :func:`facing_deg`…, 家具本地 +w(右)方向 s = (−f_y, f_x) = (cos r, sin r)。 (+30 more)

### Community 52 - "Community 52"
Cohesion: 0.11
Nodes (24): 單一需求條目；``category`` 對應 RAG 的 category_group（可為 None）。, 三分流需求：硬約束 / 軟偏好 / 家電（家電只給生圖）。, 回傳需要對應到實體家具的硬需求（有 category 者）。, RequirementDoc, RequirementItem, guess_category(), is_appliance(), 需求整理 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。 (+16 more)

### Community 53 - "Community 53"
Cohesion: 0.15
Nodes (6): RulesDoc, MasterAgent, PauseInfo, 載入室內架構與規則文件，進入等待問卷狀態。, 在目前的人為決策點提交輸入並推進流程；每次提交前自動 checkpoint。, 可恢復上一動：回復到上一次 submit 之前的完整狀態。

### Community 54 - "Community 54"
Cohesion: 0.07
Nodes (29): Scene, FurnitureLayer(), FurnitureModelBoundary, furnitureUrl(), Ghost(), GHOST_FREE, GHOST_SNAP, Item (+21 more)

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (36): wallSectionSpan(), architecturalPbrProfile(), furniturePbrProfile(), surfacePbrProfile(), columnGeometryDescriptor(), normalizedPlanarUvs(), createViewModeState(), architecturalOpeningScore() (+28 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (35): applyStylePack(), buildPack(), CEILING_DESIGN_PACKS, CEILING_STYLES, DEFAULT_RENDERING, detectCeilingConflicts(), LIGHT_STYLES, LIGHTING_PROFILES (+27 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (33): App(), analyzeServerFloorplan(), analyzeServerLayout(), analyzeServerRequirements(), applyServerStyleCard(), cacheKey(), cacheProject(), calibrateServerFloorplan() (+25 more)

### Community 58 - "Community 58"
Cohesion: 0.15
Nodes (36): build_search_text(), clean_text(), compare_field(), connect_db(), connection_kwargs(), ensure_database_exists(), execute_schema(), index_unique() (+28 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (21): load_questionnaire_visual_catalog(), _normalized_option(), Connection, Path, ValueError, QuestionnaireCatalogError, QuestionnaireVisualStore, SQLite query index generated from the versioned questionnaire JSON. (+13 more)

### Community 60 - "Community 60"
Cohesion: 0.11
Nodes (33): catalog_item_from_scene_object(), 場景物件(公分) → 引擎型錄物件(公分,含類型預設淨空)。引擎已公分化,不再換算。, check_placement(), 統一檢查入口,回傳 None 表示合法,否則回傳失敗原因(繁中訊息), FurnitureCatalogItem, place_adjacent_to_furniture(), place_furniture(), place_furniture_batch() (+25 more)

### Community 61 - "Community 61"
Cohesion: 0.11
Nodes (31): _axis_segment(), _carve_band_openings(), _clean_door_items(), _decode_image(), _dedupe_rects(), _door_axis(), _door_candidates_from_wall_gaps(), _door_score() (+23 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (26): _drop_duplicate_ocr_label_rooms(), 開放式空間常在同一牆體圈圍裡印多塊房名（LIVING ROOM 與 KITCHEN 同室），…, _bbox(), default_ocr_provider(), _normalise_paddle_result(), PaddleOCRProvider, Any, 可選的 PaddleOCR adapter；核心管線可用測試或人工 observations 取代。 (+18 more)

### Community 63 - "Community 63"
Cohesion: 0.12
Nodes (28): build_room_confusion(), match_room_masks(), normalize_room_label(), _polygon_mask(), Any, ndarray, Room recognition evaluation helpers ported from Cody's v5 scoring flow., Score room segmentation and naming from labelled bool masks. (+20 more)

### Community 64 - "Community 64"
Cohesion: 0.11
Nodes (27): build_site_payload(), _build_site_payload_for_provider(), _catalog_count_summary(), catalog_status(), catalog_status_api(), generate_scene(), home_data(), load_style_database() (+19 more)

### Community 65 - "Community 65"
Cohesion: 0.17
Nodes (31): _cand(), _kitchen_offers(), _kitchen_rooms(), _offers(), LLM 選件 agent 測試 —— 全離線,注入 stub complete(自 room_pilot2 測試移植)。 驗證重點(系統邊界永不信任…, 客廳基礎家具保底:LLM 漏選沙發 → 自動補第一張有模型的沙發, 茶几/電視櫃因此有主件可貼,不再被整批丟棄。, 候選裡連沙發都沒有 → 無從補,寧缺勿亂仍然生效:副件整批退場。, 使用者精選:先佔族系名額(LLM 同族讓位),且不受潛規則否決。 (+23 more)

### Community 66 - "Community 66"
Cohesion: 0.10
Nodes (23): overview(), actor(), container(), edge(), esc(), free_edge(), legend(), node() (+15 more)

### Community 67 - "Community 67"
Cohesion: 0.17
Nodes (30): build_html(), esc(), figure(), html_to_pdf(), img_src(), layout_report(), main(), normalize_cjk_codepoints() (+22 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (30): check_placement_with_clearance(), clearance_conflict(), clearance_polygon(), Polygon, 本體碰撞 + 淨空檢查的總入口(之後 placement/adjustment 可改用這個), 算出這件家具的淨空範圍多邊形(不含本體),無淨空需求時回傳 None, 檢查這件家具的淨空範圍是否有衝突,回傳 None 表示無衝突。 檢查順序:淨空撞牆 → 淨空撞其他家具本體 → 淨空撞其他家具的淨空, ClearanceZone (+22 more)

### Community 69 - "Community 69"
Cohesion: 0.11
Nodes (30): _agent_prepend_candidates(), _expand_dining_seats(), _facing(), _merge_exact_and_chosen(), normalize_required_furniture(), _occupant_headcount(), 入住人數 = 大人 + 小孩 + 長輩(寵物不算)。缺資料回 0。, 精選件優先入座,自動選的同 id 或**同族**讓位。 同族去重(非 normalized_type 字串)是防「臥室兩張床」的根治點:精選床可能是 bed-… (+22 more)

### Community 70 - "Community 70"
Cohesion: 0.09
Nodes (29): acceptDroppedFloorplan(), applyDelegatedRoomRecommendations(), applyFloorplanCalibration(), applySelectedMaterialScheme(), buildScaleCalibration(), pointerToImagePoint(), completeRoomBrief(), confirmFloorplanAndContinue() (+21 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (27): box(), boxAlongSegment(), buildSceneModel(), clusterOpeningSegments(), DEFAULT_SCENE_CONFIG, doorHeadCm(), doorWallSegment(), estimateProfile() (+19 more)

### Community 72 - "Community 72"
Cohesion: 0.12
Nodes (16): _PageWriter, Image, 逐頁往下寫的簡單排版器；空間不足自動換頁。, _brightness_label(), image_visual_profile(), Any, Image, ndarray (+8 more)

### Community 73 - "Community 73"
Cohesion: 0.17
Nodes (28): apply_icon_room_labels(), _chamfer_similarity(), _classify_icon(), _coarse_similarity(), detect_room_icons(), _generic_pending_label(), load_icon_templates(), _mask_text() (+20 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (25): blocked_masks(), clearance_mask(), ndarray, Point, Segment, 淨空帶:對線段**雙側描粗**,不判法線方向(§4)。 門/窗的另一側必在房間外,已被 ``¬room_mask`` 蓋掉,因此結構上不可能畫錯側。, 逐房計算兩層禁放遮罩(§4)。 ``¬room_mask`` 讓「房間外」一律禁放 —— 這是家具不會被移出自己房間的根本原因。…, build_occupancy() (+17 more)

### Community 75 - "Community 75"
Cohesion: 0.07
Nodes (24): step4 已確認、無牆縫的門(位於牆段末端,無對向牆可成 gap)過去只能停在偏離…, test_architectural_openings_have_dedicated_physical_profiles(), test_confirmed_door_at_wall_end_snaps_leaf_onto_the_wall_line(), test_confirmed_door_keeps_its_confirmed_host_wall_instead_of_nearby_gap(), test_confirmed_step4_door_keeps_the_wall_gap_and_only_moves_the_leaf(), test_confirmed_step4_door_never_moves_to_a_nearby_parallel_wall_gap(), test_confirmed_step4_door_uses_its_persisted_wall_opening_without_reinferring(), test_detected_host_span_wins_over_open_leaf_arc() (+16 more)

### Community 76 - "Community 76"
Cohesion: 0.10
Nodes (23): build_context(), kind_of(), placement_to_payload(), Any, Point, 場景 payload ↔ 柵格擺位引擎的轉接層。 新引擎(`docs/擺位計算邏輯.md`)用自己的 kind 語彙與世界座標;本 repo 的…, payload 的 ``{"start": {...}, "end": {...}}`` 或 4-tuple → 角落原點線段。, 組出一間房的 :class:`RoomContext`(角落原點公分)。 ``polygon`` 缺席時退回房間矩形 —— 手動矩形模式沒有房間環。 (+15 more)

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (23): affinity_permits(), dining_chair_target(), prompt_rules(), 家具擺放潛規則 —— agent 的領域知識單一事實源(自 room_pilot2 移植)。 擺放邏輯的完整敘事(選件 → 擺位 →…, 依餐桌寬度決定成套餐椅數:≥140cm 四人桌配 4 張,其餘至少 2 張。, 該家具是否適合放進此房型(§潛規則房型適配)。 先看 ``ROOM_FAMILY_DENYLIST``(房型明確禁用),再看…, 由知識庫資料生成選件 prompt 的潛規則條文(資料改、條文跟著改)。, _zh() (+15 more)

### Community 78 - "Community 78"
Cohesion: 0.10
Nodes (23): _positive(), 家具型錄轉接層：把家具資料庫項目轉成擺放引擎的型錄物件。 尺寸一律公分(2026-07-11 全案公分化後,此層不再做 cm↔m 換算)。…, 修補一件家具的尺寸(cm)。DB 值合理就用;否則依序用名稱尺寸、類型預設。, sanitize_size_cm(), _small_appliance_size(), F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。, scene_validate(), floorplan_from_editor_payload() (+15 more)

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (27): Floorplan Dataset Tuning Backlog, Low-Confidence Human Confirmation Gate, Recognition Evaluation Metrics, Bella Step 6-8 Condensed Flow Spec, Eight-Step Condensed Workflow, Indoor Walk Inspection Mode, Locked Proposal Snapshot, Pending Invalid Furniture List (+19 more)

### Community 80 - "Community 80"
Cohesion: 0.09
Nodes (27): PostgreSQL Catalog Read Phase 1, roompilot.furniture_catalog_api_current, roompilot.furniture_catalog_current, 家具總表 8,675 / active 8,076 / inactive 599, scripts/sql/import_official_catalog_to_postgres.py, backend/catalog/postgres_repository.py, BAAI/bge-m3 (1024-d cosine normalized), PostgreSQL 家具向量契約 (+19 more)

### Community 81 - "Community 81"
Cohesion: 0.10
Nodes (8): DocStore, Any, 共享文件庫。內部一律存 plain dict，checkpoint 用 deepcopy。, 回復到最近一個 checkpoint 的內容，回傳該 checkpoint 標籤。, _rebuild(), 輸出交付提案 PDF；排版引擎未安裝時丟 ToolError（可讀原因）。, test_docstore_checkpoint_undo_roundtrip(), test_docstore_serialization_keeps_checkpoints()

### Community 82 - "Community 82"
Cohesion: 0.14
Nodes (23): build_gateway(), _build(), get_pipeline(), _load(), pipeline_enabled(), pipeline_status(), PipelineNotStarted, Path (+15 more)

### Community 83 - "Community 83"
Cohesion: 0.09
Nodes (26): AI 寫作特徵模式清單, humanizer-zh-tw Skill, Wikipedia: Signs of AI writing, DesignManualDoc (含 pdf_path), 八章設計手冊 deterministic 組稿, render_pdf tool (Pillow A4 排版), 報告整理輸出 Skill (Report Agent), 交付前檢查清單 (人工判斷項) (+18 more)

### Community 84 - "Community 84"
Cohesion: 0.11
Nodes (25): chamfer_dt(), chamfer_score(), collect_primitives(), crop_to_canvas(), dist_transform(), hu_dist(), hu_of(), _in_text_box() (+17 more)

### Community 85 - "Community 85"
Cohesion: 0.15
Nodes (21): legacy_runtime_dirs(), project_runtime_dir(), Path, 回傳所有 worktree 共用且可長期保存的執行資料目錄。, 找出需要合併至共用資料庫的舊 worktree 執行資料目錄。, _repository_root(), _create_project(), _png_bytes() (+13 more)

### Community 86 - "Community 86"
Cohesion: 0.12
Nodes (26): Aa(), Fa(), ka(), Kn(), aa(), _allocateTargets(), _applyPMREM(), _blur() (+18 more)

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (24): dependencies, react, react-dom, @react-three/drei, @react-three/fiber, three, devDependencies, vite (+16 more)

### Community 88 - "Community 88"
Cohesion: 0.16
Nodes (9): 軟規則警告不阻擋；硬違規與硬需求缺口才算未通過。, RepairSuggestion, RequirementGap, SoftWarning, ValidationReportDoc, _facing(), 驗證 skill：流程層。提示詞與 schema 見同資料夾 ``SKILL.md``。, ValidationSkill (+1 more)

### Community 89 - "Community 89"
Cohesion: 0.18
Nodes (19): _average_grout_color(), build_processed_surface_materials(), _hex_color(), installation_spec_for_surface(), _promote_generation(), Image, Path, ValueError (+11 more)

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (22): build_room_from_dxf(), DxfRoomBuild, dxf_room.py — 把 app/backend/dxf_parser 產生的樓面 JSON 轉成 furniture_engine 的 Room。…, 便捷版:只回 Room(引擎直接用)。需要座標映射時改用 build_room_from_dxf。, dxf_parser 的公尺環 → 公分環。, 多邊形面積(shoelace,絕對值,cm²)。ring 為 [[x,z],...],首尾是否重複皆可。, 把一個環(閉合折線)的每條邊變成一段 Wall,並平移 (ox,oz) 到角落原點。, 轉換結果。room 給引擎用(公分);offset 讓你把家具座標映射回平面座標: plan_x_cm = pos_x +… (+14 more)

### Community 91 - "Community 91"
Cohesion: 0.13
Nodes (22): cody_semantic_room_labeler_status(), _head_path(), Path, 房型語意標註層的可用性檢查（DINOv2 路徑）。 Bella 的 Django 式 icon／zone 規則不需要任何模型檔就能跑，所以這個模組的職責是…, 線性頭實際路徑。`ROOM_HEAD` 環境變數可覆寫（A/B 驗收用）。 `root` 只在測試裡指定；產品走 repo 根的相對路徑，與…, torch 是否可匯入。 用 `find_spec` 而非真的 import：這個函式會被 API 的狀態端點呼叫，import torch 要數秒並吃掉數百…, 回報 DINOv2 房型標註層能否在本機執行。 `available` 為 False 時房型會退回面積規則（純幾何），品質明顯下降但不會中斷 ——呼叫端可依…, _torch_present() (+14 more)

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (24): scripts AGENTS 指引, 腳本冪等/dry-run 與交易安全規則, roompilot_catalog_manager.py, Scripts 使用說明, roompilot_glb_downloader.py, roompilot-rag normalized v1 格式, roompilot_s3_glb_uploader.py, roompilot_s3_image_uploader.py (+16 more)

### Community 93 - "Community 93"
Cohesion: 0.15
Nodes (20): _clusters(), _dimension_evidence(), _dot_endpoints(), _lines(), _number_m(), ndarray, 平面圖分析公開入口。 座標輸出遵守 RoomPilot 的跨模組公分契約；影像像素只保留在 evidence， 不會流入家具配置引擎。, _room_observations() (+12 more)

### Community 94 - "Community 94"
Cohesion: 0.20
Nodes (20): get_render_provider_status(), _is_number_triplet(), prepare_render_payload(), Any, RuntimeError, render_provider_status(), _render_timeout_seconds(), RenderProviderRejected (+12 more)

### Community 95 - "Community 95"
Cohesion: 0.22
Nodes (17): Furniture RAG runtime backed by Kai's PostgreSQL pgvector catalog., RagQueryItem, RagQueryPlan, Pydantic contracts for LLM parsing and the public RAG search API., allocate_budget(), build_filters(), mood_score(), normalize_rerank_score() (+9 more)

### Community 96 - "Community 96"
Cohesion: 0.16
Nodes (21): family_of(), is_outdoor_item(), 名稱/分類字串含戶外記號即視為戶外家具(型錄類型與 room_types 不可信)。, normalized_type → 擺位族系;未知類型原樣返回(泛用件)。, _add_missing_essentials(), _apply_conventions(), _clamp_count(), _ensure_dining_chair_sets() (+13 more)

### Community 97 - "Community 97"
Cohesion: 0.15
Nodes (21): _arc_run(), available(), _door_arc_features(), extract(), judge_openings(), _load(), ndarray, 一維剖面重取樣到固定 n 格(尺寸不變性)。 (+13 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (22): ee(), Er(), et(), Tr(), wr(), compose(), dr(), fr() (+14 more)

### Community 99 - "Community 99"
Cohesion: 0.22
Nodes (21): appendChip(), createElement(), elements, filterLabel(), formatCurrency(), formatElapsed(), formatMilliseconds(), furnitureCard() (+13 more)

### Community 100 - "Community 100"
Cohesion: 0.19
Nodes (21): axisAlignedRegionBounds(), centimeterDimensions(), editorPoint(), inferredGeometryScale(), legacyWallGapPosition(), normalizePolygon(), normalizeRing(), normalizeSavedSceneData() (+13 more)

### Community 101 - "Community 101"
Cohesion: 0.13
Nodes (12): DEFAULTS, floorplanExtension(), P0_FLOORPLAN_EXTENSIONS, projectSnapshot(), SHOW_DEFAULTS, WORKFLOW_STEPS, flattenStyleCards(), isUserSelectedFurniture() (+4 more)

### Community 102 - "Community 102"
Cohesion: 0.23
Nodes (18): FloorplanReview(), polygonPath(), SOURCE_LABELS, sourceLabel(), addDraftSegment(), calibrationPayload(), canonicalSegments(), canonicalWallSegments() (+10 more)

### Community 103 - "Community 103"
Cohesion: 0.13
Nodes (20): _anchors_zh(), _clean_size_cm(), _footprint(), _key(), _name(), pick_smaller_model(), Any, 選件 → 擺位紀律:基礎家具先行、副件成組、寧缺勿亂(自 room_pilot2 移植)。 room_pilot2 的 place.py… (+12 more)

### Community 104 - "Community 104"
Cohesion: 0.15
Nodes (19): adjust_furniture(), move_furniture(), adjust_furniture:依 Agent 已拆解好的結構化指令,調整家具位置/角度。 對應 SSOT 文件 F6:「自然語言調家具位置/數量,重繪」…, 嘗試移動家具,採用軸分離策略(對應原型的 moveTo): X 軸跟 Y 軸分開檢查,能走多少走多少,而不是全有全無。, 統一入口,吃 Agent 拆解好的結構化指令。 command 範例: {"action": "move", "dx": 50, "dy": 0}…, rotate_furniture(), PlacedFurniture, 擺放屬性:place_furniture / adjust_furniture 的輸出結果 這正是 SSOT 文件第 8… (+11 more)

### Community 105 - "Community 105"
Cohesion: 0.20
Nodes (18): _appliance_payload_cache(), _furniture_payload_item(), _candidate_ids(), cloud_image_urls(), cloud_primary_image_url(), _cloudfront_base_url(), _current_manifest_index(), _delivery_url_from_row() (+10 more)

### Community 106 - "Community 106"
Cohesion: 0.19
Nodes (20): _cleanup_jobs(), create_rag_search_job(), _ensure_job_worker(), _error_details(), get_rag_search_job(), _job_snapshot(), Exception, FileResponse (+12 more)

### Community 107 - "Community 107"
Cohesion: 0.17
Nodes (21): applyDefaultRoomIfRequested(), applyLibraryProposalDefaults(), configureSceneIntakeControls(), estimateProposalFootprintCm2(), explainEmptyScene(), filterProposalForRoom(), formatProposalItemName(), generateScene() (+13 more)

### Community 108 - "Community 108"
Cohesion: 0.21
Nodes (11): RuntimeError, RagDatabaseError, RagDisabledError, RagError, Typed failures shared by the Django RAG runtime and Bella's HTTP adapter., FurnitureRagService, Any, Path (+3 more)

### Community 109 - "Community 109"
Cohesion: 0.19
Nodes (19): build_fast_plan(), _content(), _decode_hint(), _explicit_intent_items(), _fallback_plan(), _fast_room_type(), _fast_styles(), _matches_hints() (+11 more)

### Community 110 - "Community 110"
Cohesion: 0.23
Nodes (16): ChoicePills(), RequirementsQuestionnaire(), basePayload(), clone(), DEFAULT_USES_BY_ROOM, integer(), makeRequirementsDraft(), MATERIAL_OPTIONS (+8 more)

### Community 111 - "Community 111"
Cohesion: 0.25
Nodes (18): check(), check_ai_tells(), check_meta(), check_numbers(), check_pdf(), check_placeholders(), check_process_talk(), check_repetition() (+10 more)

### Community 112 - "Community 112"
Cohesion: 0.17
Nodes (19): binarize(), Config, deskew(), detect_hough(), detect_morph(), detect_solid(), detect_walls(), load_config() (+11 more)

### Community 113 - "Community 113"
Cohesion: 0.25
Nodes (18): _ai_suggestion(), attach_room_regions(), derive_room_regions(), _free_space(), normalize_room_type(), _pieces(), _polygon_from_record(), Any (+10 more)

### Community 114 - "Community 114"
Cohesion: 0.25
Nodes (18): advance_intake(), _api_key(), _brief_copy(), _call_openrouter(), _count(), _fallback_extract(), _llm_messages(), _load_local_env() (+10 more)

### Community 115 - "Community 115"
Cohesion: 0.21
Nodes (17): beamEndpointSupportedByWall(), findStructureWallCollision(), pointToSegmentDistance(), polygonAxes(), polygonCenter(), polygonPenetration(), projectionRange(), rectangleFootprint() (+9 more)

### Community 116 - "Community 116"
Cohesion: 0.15
Nodes (19): Scene 生成系統狀態(archive), furniture_engine 接入 /scene, Agent 前後端契約, backend/agent(需求理解與選件), backend/engine(座標/碰撞/淨空權威), 設計提案PDF Report Agent(Playwright), resolve_placements 擺放修復報告, 第8步 AI 寫實生圖契約(OpenRouter nano banana) (+11 more)

### Community 117 - "Community 117"
Cohesion: 0.14
Nodes (17): _arc_run(), classify_rooms(), cluster_const(), _has_door_swing(), merge_spans(), _near_door(), nearest(), outer_wall_thickness() (+9 more)

### Community 118 - "Community 118"
Cohesion: 0.12
Nodes (11): orient_layout_toward_targets(), 自由座椅類轉向最近的目標家具;角度貼齊 90° 倍數。 只轉「不靠牆」的座椅 —— 沙發/沙發床/書桌屬 _WALL_ANCHORED_TYPES,朝向…, _scene_rotation_toward(), 沙發朝向由所靠的牆決定,orientation pass 不得再把它轉向最近的茶几; 自由座椅(扶手椅)轉向目標時角度貼齊 90°,不產生斜角足跡。, 單房呼叫不得動別房家具:進即時寫實的逐房軟裝/重排把整屋清單塞進 單房請求時,別房鎖定件曾被該房柵格(房外即阻擋)誤殺、重排進本房或標…, 重排端點(替換/移除/逐房操作)也必須有 agent 擺位紀律: 原本不帶 hints → neighbors 永遠空、成組配對死,首次產生正確、…, test_automatic_chair_faces_the_nearest_desk(), test_orientation_pass_keeps_wall_anchored_sofa_and_snaps_chairs_to_axis() (+3 more)

### Community 119 - "Community 119"
Cohesion: 0.19
Nodes (18): formatFurnitureName(), addFurnitureToScene(), compactFurnitureName(), fetchStyledFurnitureCandidate(), getTypeLabel(), handleFurnitureMaterialEdit(), normalizeSizeCm(), pickFurnitureCandidate() (+10 more)

### Community 120 - "Community 120"
Cohesion: 0.11
Nodes (18): ROOMPILOT_CATALOG_PROVIDER=postgres (strict mode), 503 postgres_catalog_unavailable, roompilot.engineering_snapshots (待恢復), revision + updated_at optimistic concurrency, backend/server/postgres_project_store.py, PostgreSQL 專案保存 Phase 3, roompilot.projects (workflow_json JSONB), SQLite → PostgreSQL 一次性 migration (缺失) (+10 more)

### Community 121 - "Community 121"
Cohesion: 0.15
Nodes (17): fixture, Path, 辨識期資產的預設路徑必須脫離 current working directory。 原本這支測的是 `CC_WEIGHTS` 與…, `ROOM_HEAD` 覆蓋機制是 A/B 驗收的入口，錨定不得吃掉它。, 線性頭與 room_classifier.py 同層，路徑由模組位置推導而非 cwd。, 缺檔時 DINOv2 分類靜默停用（只印警告），故以測試釘住檔案真的在版控裡。, 模板庫與消費它的 symbol_match.py 同目錄（2026-07-29 由 repo 根移入）。 舊寫法由模組位置往上三層推導，只搬…, `load_lib()` 找不到檔時回 None、`match_symbols()` 回空清單，不報錯。 (+9 more)

### Community 122 - "Community 122"
Cohesion: 0.25
Nodes (13): clearance.py — 開合淨空運算(F3/F6 分工範圍:碰撞/淨空運算) 處理:衣櫃門、冰箱門、抽屜等開合時所需的額外空間,…, furniture_polygon(), hits_furniture(), hits_wall(), out_of_bounds(), Polygon, 幾何運算工具:用 Shapely 判斷家具碰撞(穿牆 / 重疊 / 出界) 對應 2Dto3D.html 裡的 hitsWall /…, 把一件家具轉成旋轉後的多邊形(以 pos_x, pos_y 為中心) (+5 more)

### Community 123 - "Community 123"
Cohesion: 0.26
Nodes (15): _as_list(), _as_number(), _catalog_group(), catalog_provider_status(), _database_config(), load_catalog(), _payload_from_row(), Any (+7 more)

### Community 125 - "Community 125"
Cohesion: 0.23
Nodes (9): model_cache_status(), Any, Path, RagModelRuntime, Thread-safe, lazy, offline-only BGE-M3 model runtime., Resolve the same Hub directory used by the cache readiness check., _repo_cache_path(), _repo_is_cached() (+1 more)

### Community 126 - "Community 126"
Cohesion: 0.15
Nodes (17): WebGL context 遺失/Shader Error 1282, 3D 場景常駐與增量更新修復, GLB 頁面級快取 gltfPromiseCache, 增量家具操作 addObject/removeObject/updateObject, test_scene_3d_lifecycle_contract.py, loadScene 唯一內容 API, GLTF LRU 上限與 unloadScene, scene_v2.js (+9 more)

### Community 127 - "Community 127"
Cohesion: 0.27
Nodes (14): Layout2DReview(), ROOM_LABELS, roomLabel(), segmentLine(), clientPointToLayout(), clone(), layoutConfirmationPayload(), layoutObjectsToThreeItems() (+6 more)

### Community 128 - "Community 128"
Cohesion: 0.15
Nodes (16): Centimeter Contract, Engine Boundary: No Catalog Fetch, No External API, No Persistence, Geometry and Placement Engine (Ancai), Structured Failure Reasons for UI, Normalize External Output to Centimeters, Separate Image Evidence, Confidence and Confirmed Geometry, Floorplan Recognition (Cody), Explicit Image Profile Route (+8 more)

### Community 129 - "Community 129"
Cohesion: 0.14
Nodes (16): _door_geometry(), door_zones(), _host_wall_for_window(), _nearest_wall(), 窗吸附的牆：同方向、跨牆範圍有重疊、沿牆軸最貼近的那段。 窗是牆上的開口，兩側必貼牆——取沿牆軸間距最小者(重疊算負距離)。, 由鉸鏈位置、L 形兩自由端方向與最近的牆，決定門的沿牆方向與開門側。 回傳 (host牆索引|None, 門洞中心, 沿牆方向, 開門側方向)，皆影像座標。, 房間可用區域外框(px)：牆+窗+門洞畫成實心遮罩 → 膨脹把沒偵測到的門洞封起來 → 從影像邊界灌水,灌不進的區域=建物(含牆) →…, 把牆(方塊)圍出的內部切成一間間空間：牆+窗+門洞畫實 → 閉運算封小縫 → 影像邊界灌水分內外 → 室內扣掉牆 = 各房間連通塊。封口核逐步放大，… (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.23
Nodes (14): _apply_layout_label_suggestions(), infer_rooms_from_walls(), _polygon_area(), Any, 從 Cody 牆體幾何推導可人工確認的房間多邊形。, 將牆中心線光柵化，封閉門洞後取不接觸外框的空間。, Remove thin raster-closure needles without flattening normal room corners., 在沒有 OCR 房名時，對常見七區住宅格局提供低信心候選名稱。 (+6 more)

### Community 131 - "Community 131"
Cohesion: 0.20
Nodes (15): extractNameDimensions(), fetchFurniturePage(), fetchHomeData(), fetchJson(), fetchSceneBootstrap(), fetchSiteData(), fetchStylesData(), formatSize() (+7 more)

### Community 132 - "Community 132"
Cohesion: 0.26
Nodes (14): buildRoom(), computeBounds(), buildFloorPlanOverlay(), buildSegmentWalls(), buildWindowBoxes(), createFloorMaterial(), createHerringboneTexture(), createMarbleTexture() (+6 more)

### Community 133 - "Community 133"
Cohesion: 0.38
Nodes (15): candidateGapForDoor(), closedDoorSegment(), closedLeafProjectedOntoWall(), confirmedWallGapForDoor(), doorOpeningForWallTopology(), geometricOpeningWallInterval(), openingBelongsToWall(), openingWallInterval() (+7 more)

### Community 134 - "Community 134"
Cohesion: 0.23
Nodes (15): applyRoomFinishScope(), buildSpecialRequestAnswer(), clone(), CONDITIONAL_OPTIONS, conditionalOptionId(), emptyRoomRequirement(), evaluateConditionalOption(), migrateLegacyFinishes() (+7 more)

### Community 135 - "Community 135"
Cohesion: 0.23
Nodes (13): axisAlignedSpan(), computeExactModelScale(), finishedSurfaceSpans(), floorplanPoint(), furnitureHalfExtents(), inferredWallThicknessCm(), median(), normalizedDegrees() (+5 more)

### Community 136 - "Community 136"
Cohesion: 0.12
Nodes (16): roompilot.external_import_quarantine (不進 API/RAG), roompilot.runtime_catalog_rag_documents, PostgreSQL Runtime Catalog Phase 4, backend/catalog/runtime_catalog_repository.py, roompilot.style_cards_current (18 張), roompilot.surface_materials_current (571 筆), feasible/tradeoff_required/infeasible/size_recommended, generative_equipment (廚浴陽台設備) (+8 more)

### Community 137 - "Community 137"
Cohesion: 0.13
Nodes (16): Ancai AI Profile, Centimeter and Explicit Rotation Units, Deterministic Furniture Geometry Ownership, Placement Validation Order (boundary/wall/overlap/clearance), Ben AI Profile, Dataset Provenance and Model Version Recording, Recognition Evaluation Evidence Chain, Centimeter Normalization of Cross-Module Output (+8 more)

### Community 138 - "Community 138"
Cohesion: 0.26
Nodes (12): _clear_rag_jobs(), _FakeService, Exception, parametrize, TestClient, Later rooms must queue behind local embedding work instead of receiving 429., test_rag_api_maps_failures(), test_rag_job_api_hides_upstream_failure_detail() (+4 more)

### Community 139 - "Community 139"
Cohesion: 0.33
Nodes (15): _item(), _plan(), MonkeyPatch, parametrize, Path, _settings(), test_anthropic_parser_uses_structured_outputs_without_fallback(), test_configured_parser_rejects_unknown_provider() (+7 more)

### Community 140 - "Community 140"
Cohesion: 0.18
Nodes (15): applyStyleCardFromQuery(), buildDeliveryManifest(), escapeForHtml(), findSelectedStyleCardContext(), materialSlotsForFurniture(), openStylePicker(), prepareMaterialSchemes(), readLibraryProposal() (+7 more)

### Community 141 - "Community 141"
Cohesion: 0.25
Nodes (14): catalogFurnitureScore(), colorScore(), hexRgb(), materialScore(), normalizedTokens(), OUTDOOR_NAME_TOKENS, OUTDOOR_ROOM_TYPES, outdoorPenalty() (+6 more)

### Community 142 - "Community 142"
Cohesion: 0.16
Nodes (13): createFurniture2DItem(), findFurniture2DVariant(), FURNITURE_2D_LIBRARY, furnitureCollisionFootprintCm(), furnitureFootprintStyle(), ICONS, recommendCompanionFurniture(), recommendedFurnitureForRoom() (+5 more)

### Community 143 - "Community 143"
Cohesion: 0.19
Nodes (9): excluded_item_ids(), matching_line_count(), Path, Verify excluded catalog items are absent from upload manifests., sha256(), Path, test_excluded_furniture_is_absent_from_both_manifest_copies(), test_sql_database_config_reads_the_repo_env_contract() (+1 more)

### Community 144 - "Community 144"
Cohesion: 0.17
Nodes (7): 逐房 A/B 的方案 B 是同一批家具的替代排法。舊版 relayoutFurnitureForScheme 只要 有一件家具擺不下就整組回 null（→…, _run_room_requirement_helper(), test_conditional_option_detection_uses_structured_catalog_fields(), test_generation_space_requirements_are_versioned_and_preserved(), test_normalize_preserves_unassigned_deferred_furniture(), test_scheme_b_alternative_tolerates_pending_furniture_so_ab_gate_can_appear(), test_special_request_is_a_complete_non_forced_answer()

### Community 145 - "Community 145"
Cohesion: 0.19
Nodes (14): Validation Agent (任務4 修復/報告), 公分制座標契約 (_cm/_m2/coordinate_unit), RoomPilot AI 協作守則, 跨資料夾修改規則, 目錄責任與資料邊界矩陣, 不可違反的契約, 驗證矩陣, 平面圖→3D 場景外殼管線差異評估 (+6 more)

### Community 146 - "Community 146"
Cohesion: 0.19
Nodes (11): catalog_from_dict(), placed_from_dict(), placed_to_dict(), schema.py — furniture_engine 對外介面定義(v0.1 提案) 用途: 1. 定義 Agent(LLM function-…, PlacedFurniture -> JSON dict(後端存 DB、前端渲染、回給 Agent 都吃這個), JSON dict -> FurnitureCatalogItem(Agent 丟進來的家具描述), JSON dict -> PlacedFurniture(從 DB/前端還原目前場景狀態用), demo_agent_flow.py — 模擬 Agent 呼叫 furniture_engine 的完整流程 用途:跟 Agent… (+3 more)

### Community 147 - "Community 147"
Cohesion: 0.20
Nodes (13): available(), classify(), crop_room(), letterbox(), _load(), room_classifier.py — DINOv2 房間裁切分類（去 CubiCasa 路線的房型命名層）。 凍結 DINOv2 ViT-S/14 取…, [room] → [{label: 機率}]（順序同 rooms）；停用時回 None。 每間房以 bbox＋邊距裁切、8 視角 TTA 平均特徵後過線性頭…, 等比縮放＋白底填滿（平面圖底色白）到 SIZE×SIZE。同訓練側 letterbox。 (+5 more)

### Community 148 - "Community 148"
Cohesion: 0.16
Nodes (12): 上傳檔名主幹 → `recognize_cody_rooms` 的 `cache_key`。 2026-07-30 CubiCasa…, _semantic_cache_key(), needs_floor01_cache, needs_floor01, Path, 語意層鍵傳遞與房型對照（2026-07 盤點「房型語意斷鏈」的修復測試）。 守住三件事： 1. `analyze_floorplan_image`…, test_analyze_floor01_lands_kitchen_and_entry_types(), test_analyze_passes_filename_stem_to_semantic_layer() (+4 more)

### Community 149 - "Community 149"
Cohesion: 0.24
Nodes (13): _ask(), _cache_path(), _crop_with_context(), get_vision_models(), judge_openings(), _load_cache(), _montage(), ndarray (+5 more)

### Community 150 - "Community 150"
Cohesion: 0.23
Nodes (11): clone(), createController(), createWorkflow(), initialState(), REQUIRED_COMPLETIONS, restoreWorkflow(), storageKey(), WORKFLOW_PANEL_BY_STEP (+3 more)

### Community 151 - "Community 151"
Cohesion: 0.30
Nodes (13): _backend_reasons(), _create_project(), _frontend_labels(), _put_workflow(), 辨識複核（review_items）必須有前端消費端與伺服器閘門。 背景：`spatial_report.py`…, 第 4 步採 backup/yen-2026-08-06 版後，複核清單區塊與逐間引導卡不存在。 仍必須保留的最小消費端：第 3…, test_deleted_flagged_room_counts_as_human_intervention(), test_every_backend_review_reason_has_a_frontend_label() (+5 more)

### Community 152 - "Community 152"
Cohesion: 0.36
Nodes (13): module_import(), 房屋 3D 外殼純函式幾何層（scene_shell_geometry.js）單元測試。 對映 docs/3D房屋場景建置流程.md 的關鍵不變式：窗群聚…, run_shell_script(), test_build_scene_model_uses_infill_switch(), test_distinct_ids_never_merge_and_symbol_lines_do(), test_door_lintel_sits_on_the_wall_gap_not_the_leaf_symbol(), test_empty_plan_builds_empty_model(), test_estimate_profile_reads_wall_cross_section() (+5 more)

### Community 153 - "Community 153"
Cohesion: 0.26
Nodes (12): _close(), _dilate8(), _erode8(), label_regions(), passage_segments(), ndarray, Segment, 通行段(牆縫式開口)—— 依 `docs/擺位計算邏輯.md` §4.2(公分版)。 沒有 door… (+4 more)

### Community 154 - "Community 154"
Cohesion: 0.38
Nodes (12): _arc_score(), _dedupe(), detect_geometry(), _door_observations(), _hough_segments(), _overlap(), Any, ndarray (+4 more)

### Community 155 - "Community 155"
Cohesion: 0.21
Nodes (13): Ci(), Po(), un(), ai(), bo(), ei(), G(), ii() (+5 more)

### Community 156 - "Community 156"
Cohesion: 0.17
Nodes (13): cn(), convertSRGBToLinear(), copySRGBToLinear(), En(), getContext(), getDataURL(), hn(), mn() (+5 more)

### Community 157 - "Community 157"
Cohesion: 0.23
Nodes (13): appendChatMessage(), applyPendingStyleCard(), applySelectedStyleToBrief(), closeStylePicker(), mergeUserAnswerIntoBrief(), rememberSceneStyleCard(), removeLibraryProposalItem(), renderClientBrief() (+5 more)

### Community 158 - "Community 158"
Cohesion: 0.23
Nodes (13): POST /api/agent/furniture/select, RoomPilot API Overview, POST /api/scene/generate, Layout/Scene boundary contract, Retire appliance catalog flow, Bella Test1 Integration Log, Folder Function Overview, layout_json (+5 more)

### Community 159 - "Community 159"
Cohesion: 0.19
Nodes (8): _function_body(), 3D 場景生命週期契約：viewer 常駐、家具增刪走增量操作、GLB 只載一次。 背景：六個 viewer 只在頁面載入時建一次，但過去唯一的內容 API…, Shader Error 1282／白畫面的根因是 WebGL context 遺失：GPU 用量必須有上界。 - GLB 快取有 LRU…, 第 6→7 步材質狀態機呼叫 whiteViewer.updateRoomSurfaces()（bella-new 拼接帶入）。 viewer…, test_furniture_edits_use_incremental_operations_not_full_reload(), test_gpu_memory_stays_bounded_against_context_loss(), test_room_scheme_previews_build_offscreen_and_get_cleaned_up(), test_viewer_exposes_update_room_surfaces_used_by_material_flow()

### Community 160 - "Community 160"
Cohesion: 0.26
Nodes (13): 商業需求文件 (BRD) 模板, 產品需求文件 (PRD) 模板, 軟體需求規格書 (SRS) 模板, 資訊架構 (IA) 模板, UI 規格書 (UI Spec) 模板, UX 研究與使用者旅程 模板, 架構決策紀錄 (ADR) 模板, 軟體架構文件 (SAD) 模板 (+5 more)

### Community 161 - "Community 161"
Cohesion: 0.18
Nodes (13): API 設計規範 (api_spec), 資料庫設計 (DB Design), 低階設計與程式碼地圖 (LLD / Code Map), 狀態機設計契約 (屬於 Aggregate), OpenAPI 契約骨架 (openapi.yaml), WorkOrderStatus enum, 實例化規則 (穩定錨點非 feature), 模板六要素解剖結構 (+5 more)

### Community 162 - "Community 162"
Cohesion: 0.20
Nodes (12): 座標與幾何合法性只由 backend/engine 判定, Master state machine 編排, room_pilot2 re-export (parse_selections/resolve_placements), RoomPilot Agent (Master + 4 Sub-agents), 提示詞與 schema 只寫在 SKILL.md, Agent 架構實作報告 (2026-07-31), 所有文字 skill 具 deterministic fallback, build_pdf.py (Playwright Chromium 排版擁有者) (+4 more)

### Community 163 - "Community 163"
Cohesion: 0.20
Nodes (11): initBackgroundFx(), clearLinkedStep(), featureCards, flowCards, flowSection, furnitureMetric, openFlowPanel(), scheduleCloseFlowPanel() (+3 more)

### Community 164 - "Community 164"
Cohesion: 0.23
Nodes (10): attachLibraryThumbnail(), cache, createStage(), disposeObject(), dracoLoader, fitModel(), loader, renderer (+2 more)

### Community 165 - "Community 165"
Cohesion: 0.17
Nodes (12): buildChips(), buildPlanLabels(), buildRoomThumbnails(), glideTo(), goToViewpoint(), markInteraction(), nearestViewpointIndex(), ringCentroid() (+4 more)

### Community 166 - "Community 166"
Cohesion: 0.21
Nodes (12): abort(), addOnInit(), addRunDependency(), assert(), createWasm(), getBinary(), getBinaryPromise(), intArrayFromBase64() (+4 more)

### Community 167 - "Community 167"
Cohesion: 0.21
Nodes (12): 開口雙路徑 (infill = wallPolygons.length > 0), scene_shell_geometry.js (純函式幾何層), Union-Find 開口群聚 (clusterOpeningSegments), 躺椅搶沙發前位/門上懸空牆塊, 門楣掛 wall_opening_segment/closed_leaf_segment (nearAnyWallLine 防呆), FREE_SEATING_FAMILIES 自由座椅最後擺, 家具朝向不對/有窗的牆比左右稍矮, placement_hints (backend/agent/place.py) 首次擺位未消費 (+4 more)

### Community 168 - "Community 168"
Cohesion: 0.18
Nodes (8): _fallback_query_for(), 讀 scene_v2.js 的 QUESTIONNAIRE_FALLBACK_CATALOG_RULES[type].query(單一事實源)。, 回歸(feedback floor04:電視櫃完全不在清單):電視櫃 fallback rule.query 必須是 「會逐字命中型錄名稱的詞」。伺服器…, test_outdoor_named_rows_rank_below_indoor_for_indoor_rooms(), test_questionnaire_matching_catalog_glb_wins_over_size_only_candidate(), test_room_role_and_rag_text_influence_questionnaire_catalog_ranking(), test_semantic_product_name_rejects_wrongly_classified_catalog_rows(), test_tv_bench_fallback_query_retrieves_a_tv_bench_in_first_page()

### Community 169 - "Community 169"
Cohesion: 0.21
Nodes (12): ACME Field Service 填好版生成 prompt (Worked Example), 容器圖 (C4 Container), 系統情境圖 (C4 System Context), 部署拓撲圖 (Deployment Topology), 架構圖模板手冊 (Diagram Templates Manual), drawio vs mermaid 載體分工, drawio 三步生成管線 (spec→generate→layout verify), 語意化配色與線型規範 (+4 more)

### Community 170 - "Community 170"
Cohesion: 0.24
Nodes (7): _furniture_card_payload(), furniture_catalog(), _furniture_filter_options(), _style_filter_options(), test_catalog_search_interprets_common_chinese_furniture_terms(), test_mode_one_catalog_exposes_and_applies_visual_filter_facets(), test_mode_one_catalog_only_returns_loadable_models_and_matching_taxonomy()

### Community 171 - "Community 171"
Cohesion: 0.31
Nodes (10): classifyMaterialSlot(), COMPATIBLE_FINISHES, generateMaterialSchemes(), overrideForSlot(), paletteFor(), restoreOriginalMaterials(), ROLE_PATTERNS, SCHEME_NAMES (+2 more)

### Community 172 - "Community 172"
Cohesion: 0.24
Nodes (6): image_rows(), _load_csv(), fixture, Path, test_glb_manifest_and_upload_result_match_the_official_catalog(), test_json_official_catalog_contains_vlm_enrichment_and_matching_assets()

### Community 173 - "Community 173"
Cohesion: 0.20
Nodes (10): A/B 策略 (動線優先/收納優先), 家具 Skill (Furniture Agent), 擺位意圖 method (free/adjacent/overlay), rag_furniture tool (RAG 檢索排序), repair 提示詞 (swap/remove), select 提示詞與 schema, 白名單選件約束 (不發明家具、不輸出座標), 雙軌驗證 (硬規則擋/軟潛規則 advisory) (+2 more)

### Community 174 - "Community 174"
Cohesion: 0.24
Nodes (10): 60-30-10 色彩比例規則, 焦點原則 (單一 focal point), interior-design-principles Skill, 尺度與比例規則 (家具對牆比), 三層照明 (ambient/task/accent), 窗向決定色彩 (光物理), 預算購物層級, command position (主座朝門) (+2 more)

### Community 175 - "Community 175"
Cohesion: 0.36
Nodes (8): estimate_project_cost(), load_default_cost_catalog(), Any, 讀取已人工核對、可離線重現的台灣公開網路行情種子。, 計算低／基準／高區間；缺少數量證據或費率時保留待詢價。, _validate_catalog(), test_default_online_price_seed_keeps_source_links_and_explicit_exclusions(), test_sourced_rates_produce_traceable_low_base_high_concept_estimate()

### Community 176 - "Community 176"
Cohesion: 0.22
Nodes (10): Furniture RAG Test Bench Page, rag.js module, RAG retrieval-only no-geometry boundary, Spatial Data Boundary (Django owner), Open/close clearance zones, Placement Computation Logic Spec, Deterministic reproducibility of placement, OBB collision (obb_blocked) (+2 more)

### Community 177 - "Community 177"
Cohesion: 0.22
Nodes (10): 家具引擎12種空間標準(space_kind), space_kind(12碼) vs room_type(粗分類), 家具引擎逐房需求契約(schema 1.0), furniture_slots(slot_id/selected_size/catalog_item_id), never_fallback_to_white_model 引擎不可違反規則, RAG 回覆契約(catalog_type須等於slot_id), 逐房/slot 狀態機(pending_rag..placement_failed), 燈具天花冷氣資料契約(草案) (+2 more)

### Community 178 - "Community 178"
Cohesion: 0.36
Nodes (8): main(), _normalized_basename(), Path, 驗證 IKEA 離線備援 zip 是否完整覆蓋隔離家具清單。, verify_backup(), test_backup_verifier_reports_ambiguous_catalog_models(), test_backup_verifier_reports_unique_catalog_matches(), _write_catalog()

### Community 179 - "Community 179"
Cohesion: 0.22
Nodes (9): build_select_messages(), RuntimeError, 候選白名單 → LLM 選件 → (已驗證 {room_id: [SelectedItem]}, 模型 id)。 無任何有候選的空間回 ({},…, LLM 不可用(未注入/未啟用/呼叫失敗),呼叫端應降級本機規則。, 純函式(可單測):空間摘要 + 各空間候選白名單 + 選件潛規則。 rooms 每項:{room_id, room_type, width_cm,…, request_selections(), SelectionUnavailableError, Complete (+1 more)

### Community 180 - "Community 180"
Cohesion: 0.22
Nodes (9): 家電只作畫面元素不影響配置, 階段二 full_render (全房逐房生圖+鎖定清單), 生圖 Skill (Gen_Pic Agent), nano banana 渲染請求, 階段一 palette_compare (色卡比對成本漏斗), 家電只進生圖 context 不進 2D/3D 擺設, RequirementDoc (req_id H/S/A 前綴), 需求整理 Skill (Furniture Agent) (+1 more)

### Community 181 - "Community 181"
Cohesion: 0.33
Nodes (7): green_boxes(), main(), matched(), 抽出圖中所有綠色框的 bbox 清單 [(x0,y0,x1,y1)]。 同時吃程式畫的 (0,170,0) 與小畫家綠 (34,177,76)，含反鋸齒容差。…, build_mask(), main(), ndarray

### Community 182 - "Community 182"
Cohesion: 0.28
Nodes (9): applyMinimapSize(), boot(), buildMinimapBase(), getSceneData(), loadFurniture(), setProgress(), showToast(), fitToTargetSize() (+1 more)

### Community 183 - "Community 183"
Cohesion: 0.39
Nodes (8): ARCHITECTURAL_PROFILES, clamp01(), distanceFromWhite(), FURNITURE_PROFILES, mixHex(), parseHex(), surfaceTint(), toHex()

### Community 184 - "Community 184"
Cohesion: 0.25
Nodes (9): Step 4 Space and Structure Editor, Step 5 Requirements Questionnaire, Step 6 White Model 3D Workspace, RoomPilot Scene 8-Step Workflow Page, configuration_snapshot as version baseline, No backtrack past Step 7 lock, Eight-Step /scene Workflow, Step 6-8 Agent and Render Spec (+1 more)

### Community 185 - "Community 185"
Cohesion: 0.25
Nodes (9): ben-dev 功能整合來源報告, 單位遷移四處(公尺/異座標未外洩), 新五階段主線流程, Agent 提示鏈 layout_intent/recovery, 渲染履歷(白模+取景+色卡版本), RoomPilot 現行版本總覽 SSOT v4.0, 18色卡(6風格×3色系), #3 引擎公分化後邊界層雙重換算 (+1 more)

### Community 186 - "Community 186"
Cohesion: 0.25
Nodes (9): 地板破口/家具朝向/靠牆家具不貼牆, expandedFloorSlabRing (14cm miter offset), 場景朝向慣例 rot=0 正面朝 +z, _raster_wall_anchor (靠牆錨定掃描接線), backend/server/scene_service.py, backend/engine/rules.py try_against_wall (未接上), 家具全部擠進同一間房, generate_layout_by_room (逐房分組擺位) (+1 more)

### Community 188 - "Community 188"
Cohesion: 0.44
Nodes (8): abs_geom(), analyze(), center(), collect(), main(), 回傳節點絕對 (x,y,w,h)；沿 parent 鏈累加位移。, seg_intersect(), seg_rect()

### Community 189 - "Community 189"
Cohesion: 0.25
Nodes (8): Furniture Agent (任務1-3 選件), 家具型錄分類瀏覽器 (空間/用途/批次多選), RoomPilot Official Catalog and Vector Handoff, BGE-M3 向量 (8,076 active), 官方 8,675 筆家具 catalog, RAG 責任邊界 (Django 擁有向量, Kai 持久化), backend/agent 需求與選件, PostgreSQL 家具 catalog 資料來源

### Community 190 - "Community 190"
Cohesion: 0.25
Nodes (8): Gen_Pic Agent (任務5-6 生圖), bella-new 第5-8步前端對照 (HTML), bella-new 第5-8步前端排版功能對照, 第6步逐房 A/B 關卡刻意保留, OpenRouter 一鍵生圖與設計提案 PDF 全鏈, 逐房材質草稿→鎖定→確認狀態機, submitRoomRenders 同名不同義合併風險, Copywriting Skill

### Community 191 - "Community 191"
Cohesion: 0.32
Nodes (8): 動線與淨空 clearance 規則, engine_validate tool (check_placement_with_clearance 重驗), check_placement_with_clearance 檢查順序, ClearanceZone 開合空間淨空, 公分制座標系 (X 右 Y 上,家具中心點), furniture_engine 家具邏輯引擎, place_furniture / adjust_furniture (軸分離 move), 外圍牆厚錨定比例尺 (wall_min ≥15cm)

### Community 192 - "Community 192"
Cohesion: 0.39
Nodes (7): classify_image(), collect_rooms(), deep_find(), load_json(), main(), 在巢狀結構裡找出 key 符合 pattern 的值，回傳 [(路徑, 值)]。 schema 會演進，寫死路徑很快就會壞掉；用模糊搜尋比較耐用。, 優先讀 rooms/<房名>/ 結構；沒有就退而求其次掃全資料夾的圖。

### Community 193 - "Community 193"
Cohesion: 0.39
Nodes (7): available(), detect_windows(), _load(), _predict(), ndarray, 整張圖 → (逐像素類別遮罩, 窗類 softmax 機率圖),皆原圖尺寸。失敗回 None。, 模型偵測到的窗 → [(orient, x0, y0, x1, y1, conf)](影像 px)。 conf = 該窗塊內窗類 softmax…

### Community 194 - "Community 194"
Cohesion: 0.32
Nodes (8): applyCamera(), clampToRoom(), computeViewpoints(), findFreeNear(), furnitureCentroid(), furnitureRects(), isFreeSpot(), roomCenter()

### Community 195 - "Community 195"
Cohesion: 0.43
Nodes (6): buildDimensionedPlanAnnotations(), clamp(), dimensionLine(), escapeXml(), ROOM_DIMENSION_COLORS, validPoint()

### Community 196 - "Community 196"
Cohesion: 0.36
Nodes (8): LLM Required JSON Contract, Scene handoff: engine owns geometry, RoomPilot LLM Prompt Specification, RoomPilot Agent Architecture Diagram, Deterministic fallback for LLM skills, DocStore blackboard, MasterAgent state machine, OpenRouterGateway (llm.py)

### Community 197 - "Community 197"
Cohesion: 0.25
Nodes (8): Ancai roompilot/engine 家具幾何引擎, Bella project_store SQLite 專案儲存骨架, Bella 六風格與18色卡資產, ben-dev 整合分支, layout_service 專案協調層, 外部 room_pilot2 儲存庫, 真窗洞 wall_openings 契約(ben-dev 新寫), Yen R3F 前端與 Agent 提示鏈

### Community 198 - "Community 198"
Cohesion: 0.32
Nodes (8): 實作品質防呆規範 GUARDRAILS, 功能四要件(畫面/互動/資料/驗收), Definition of Done 逐層驗收條件, 測試通過≠符合需求 通用判準, 三套座標系並存陷阱(角落/中心/左下), RoomPilot 失敗帳本 FAILURE_LOG, #1 引擎25測試全過但擺放全錯(尺寸鏈未通), 任務交辦範本 TASK_TEMPLATES

### Community 199 - "Community 199"
Cohesion: 0.29
Nodes (8): 工程文件 Advanced RAG (Structured Retrieval + Mock Vector Adapter), 設計師鎖定後的工程文件 MVP, frontend3d React/R3F 原型, Graph RAG 邊界, RoomPilot-Agent 專案概觀, requirements.txt team baseline 依賴, requirements-delivery.txt (PDF 排版引擎依賴), Playwright Chromium print-to-PDF

### Community 200 - "Community 200"
Cohesion: 0.52
Nodes (6): buildEmptyAffected(), buildSceneWallSegment(), buildSpaceChangeReport(), buildWallBoxingComparison(), rounded(), validateChange()

### Community 201 - "Community 201"
Cohesion: 0.38
Nodes (7): addOnPostRun(), addOnPreRun(), callRuntimeCallbacks(), initRuntime(), postRun(), preRun(), run()

### Community 202 - "Community 202"
Cohesion: 0.52
Nodes (6): load_rag_settings(), Path, Server-only settings for the furniture RAG feature., _read_env_file(), _setting(), _truthy()

### Community 203 - "Community 203"
Cohesion: 0.29
Nodes (7): Cody floorplan2dxf 辨識管線, Cody Full Pipeline 整合計畫, floorplan2room 語意管線(房型79.2%→90.3%), 定向整合cody-dev而非整包merge ben(rationale), 落地燈型錄對應交接(decor_model_missing), postgres_repository 落地燈 normalized_type 對應, cloud JSON 遺失 type_code 導致落地燈誤分類

### Community 204 - "Community 204"
Cohesion: 0.43
Nodes (7): Automatic Relayout Touches Only Invalid Furniture, StylePack Rendering Contract, Four Lighting Profiles, Palette Switching Never Changes Geometry, Four Fixed Palette Slot Semantics, StylePack Fields, User Lock Flags Override StylePack

### Community 205 - "Community 205"
Cohesion: 0.29
Nodes (7): RAG 失敗不阻塞問卷 (非阻塞規則), 問卷與 RAG 串接契約, backend/server/rag_api.py, backend/server/static/scene_v2.js, 逐房問卷兩處死結, finishesGate confirmed 循環死結, roomFurnitureRequirement 每次重建物件失效

### Community 206 - "Community 206"
Cohesion: 0.33
Nodes (6): parametrize, cody 管線模組的可載入性冒煙測試。 `docs/CODY_MAIN_SYNC_TODO.md` 第 2 點要求預設入口改走…, cody_adapter 會用到的公開函式，鎖住名稱避免上游改名無聲失聯。 2026-07-30 起…, test_floorplan2room_exposes_the_entry_points_the_adapter_will_need(), test_pipeline_config_is_present_and_parsable(), test_pipeline_module_imports_as_package_member()

### Community 208 - "Community 208"
Cohesion: 0.33
Nodes (3): Path, _sha256(), test_rag_page_assets_have_matching_content_hashes()

### Community 209 - "Community 209"
Cohesion: 0.40
Nodes (6): Catalog 與材質資料 AGENTS (Owner: Kai), lighting_assets_manifest.csv, 正式 ID/尺寸/URL 只來自已驗證 catalog, furniture_catalog_6styles_zh.json (僅風格展示,空 furniture array), RoomPilot 家具資料邊界 (8675 件正式), furniture_official_catagory.json + GLB/image manifest

### Community 210 - "Community 210"
Cohesion: 0.53
Nodes (5): createPreview(), disposePreview(), materialFor(), previewsByHost, renderMaterialPairPreviews()

### Community 211 - "Community 211"
Cohesion: 0.47
Nodes (5): cjkCount(), repairMojibake(), repairMojibakeDeep(), utf8Decoder, saveWorkflowRequest()

### Community 212 - "Community 212"
Cohesion: 0.33
Nodes (6): 以 ben 步驟1-4 替換 yen 步驟1-4 整合計畫, 步驟3校正採 ben 後端重算 (D4), ben vs yen 步驟1-4 排版/功能/產出比對, Yen 整合 Bella 第4至第8步指南, scene_v2.js 唯一前端修改位置, 分階段移植順序 (A-E)

### Community 216 - "Community 216"
Cohesion: 0.20
Nodes (6): 對抗式審查抓到的三個執行期缺陷（字串契約測抓不到，特此鎖定）： 1) 快取鍵讀寫兩端都要用 room.id——傳 room 物件會變 "[object…, 流程規範:方案 A/B 於第 6 步選定;第 7 步依選定方案比較三張色卡、 第 8 步依選定色卡逐房生圖 —— 第 7 步面板不再出現 A/B 切換鈕,…, 第 8 步版面:生圖完成後取代左側 3D 場景(圖疊在 viewer 容器上), 點圖切回 3D、點「查看生圖」隨時切回,且左側的圖跟著選取房間連動。, test_room_scheme_3d_preview_key_and_lifecycle_are_correct(), test_scheme_choice_is_fixed_after_entering_step_seven(), test_step_eight_render_image_replaces_viewer_and_toggles()

### Community 218 - "Community 218"
Cohesion: 0.40
Nodes (5): RoomPilot Agent 架構提案, Master 主流程 state machine, Report Agent (任務7 統整輸出), Current Product Boundary, 八步產品流程

### Community 219 - "Community 219"
Cohesion: 0.60
Nodes (5): CubiCasa5k 資料集, floorplan 辨識管線變更日誌, 純規則基準 (94%/92% 安全網), 分割模型融合 (U-Net onnx,只增不減,94%/95%), VLM/本地分類器仲裁 (評測否決)

### Community 220 - "Community 220"
Cohesion: 0.40
Nodes (5): home.js entry module, RoomPilot Home Landing Page, Furniture Library Picker Page, library.js module, Library Three.js Model Viewer

### Community 222 - "Community 222"
Cohesion: 0.50
Nodes (5): 室內設計判斷尺 clearance 規則與 eval, clearance_rules JSON schema(applies_when), 門開合迴轉區 90°扇形檢查, engine CLEARANCE_BY_TYPE 收納淨空語意, 硬約束(fail)/軟約束(扣分)/drift 分類

### Community 223 - "Community 223"
Cohesion: 0.40
Nodes (5): 3D House Scene Build Pipeline, buildSceneModel pure geometry function, DXF to FloorPlan(mm) parse pipeline, mm to cm conversion at API boundary, Window clustering (Union-Find)

### Community 224 - "Community 224"
Cohesion: 0.50
Nodes (5): roompilot.furniture_catalog_current 只公開 verified, 材質天花燈光參考體驗契約, front-cut half-cube 材質預覽, KAI PostgreSQL 優先/示意備援標示, 逐房優先(room-first)完稿決策

### Community 229 - "Community 229"
Cohesion: 0.50
Nodes (4): 執行期不得載入 quarantine 檔案, SF3D 舊型錄隔離資料, tests/test_cloud_quarantine.py 守門, 未對應雲端家具隔離區

### Community 230 - "Community 230"
Cohesion: 0.67
Nodes (3): detect_on(), main(), 對單張樣式圖執行與 run() 相同的窗偵測流程，回傳 wins。

### Community 231 - "Community 231"
Cohesion: 0.50
Nodes (4): detect_windows(), _infer_lines(), 在牆的開口偵測窗:開口長度被細線高度覆蓋=窗(玻璃線沿牆跨整段)； 空的=門/通道，留開；落在偵測到的門附近=門，留開。回傳 [(orient, x0,…, 找「兩個垂直牆端點對齊、但那條線上沒有任何牆塊」的候選牆線 [(orient, c, lo, hi)]。 整條用細線畫的牆(如圖框邊的窗牆)會被 solid…

### Community 232 - "Community 232"
Cohesion: 0.50
Nodes (4): gap_openings(), 牆端沿軸射線找最近的任何牆(厚度帶重疊≥50%)，中間 lo~hi cm 的空縫 (無牆無窗)＝開口。涵蓋 牆端↔牆端 與 牆端↔牆面(T字門洞)。 回傳…, 牆縫開口＝門位（不靠弧偵測）：40~150cm 的牆縫 → 門洞/出入口。 回傳與 door_zones 同格式的 [(四角px, 合成door)]。, _wall_gaps()

### Community 233 - "Community 233"
Cohesion: 0.50
Nodes (4): 把非矩形實心塊遞迴切成貼形矩形(KD 式)：先縮緊 bbox，fill≥0.8 就收； 否則沿長邊在像素數最少的欄/列切開(中央 60%…, 建築基柱：厚度遠大於牆厚(>2×牆厚)的實心塊。黑色實心務必 100% 判出—— 基柱要當牆輸出給後端生成 3D 空間。先從 bw 切出來、再以自己的…, _split_blob(), split_pillars()

### Community 234 - "Community 234"
Cohesion: 0.50
Nodes (4): _placement_candidates(), 候選試放順序(合法性仍 100% 由引擎把關,這裡只影響「先試哪裡」)。 hint / neighbors 是 2026-08-02 併入 yen agent…, test_engine_anchor_hint_prepends_left_wall_candidate(), test_engine_no_hint_matches_legacy_behavior()

### Community 236 - "Community 236"
Cohesion: 0.50
Nodes (4): emscripten_realloc_buffer(), _emscripten_resize_heap(), getHeapMax(), updateMemoryViews()

### Community 237 - "Community 237"
Cohesion: 0.50
Nodes (4): ensureString(), intArrayFromString(), lengthBytesUTF8(), stringToUTF8Array()

### Community 238 - "Community 238"
Cohesion: 0.50
Nodes (4): _fd_write(), printChar(), UTF8ArrayToString(), UTF8ToString()

### Community 239 - "Community 239"
Cohesion: 0.67
Nodes (4): RoomPilot pgvector docker-compose, PostgreSQL One-Click Docker Setup, pgvector/pgvector:pg17 image, roompilot_db_dump.sql.gz DB dump

### Community 240 - "Community 240"
Cohesion: 0.50
Nodes (4): 三條鐵律(座標唯engine/唯一FastAPI/全鏈公分), #11 前端覆寫後端座標(升級為第一鐵律), 3D/GLB 管線狀態(archive), IKEA GLB 相容處理(draco/webp/texture_transform)

### Community 241 - "Community 241"
Cohesion: 0.67
Nodes (4): 家具模型交付契約(CloudFront Manifest), AWS CloudFront GLB 交付(cloudfront 模式), 官方 furniture_official_catagory.json(8675 ID), quarantine 隔離家具規則

### Community 242 - "Community 242"
Cohesion: 0.50
Nodes (4): Optional PaddleOCR Stack, Producer and Consumer Tests for Contract Changes, Deterministic Offline-By-Default Tests, Test Suite Ownership and Gates

### Community 244 - "Community 244"
Cohesion: 0.67
Nodes (3): _draw_room_text(), preview_solid(), 房名標到預覽圖。有 PIL+中文字型用中文，否則退英文 putText。

### Community 245 - "Community 245"
Cohesion: 0.67
Nodes (3): 近景穿牆 X-ray Walls 修改歷程, 逐片元 shader onBeforeCompile 穿牆機制, dxf_parser unary_union 合併單一牆 mesh

### Community 246 - "Community 246"
Cohesion: 0.67
Nodes (3): 專題定義釐清(不生成新家具/以GLB庫配置), 風格生成交接摘要(8風格 style_moodboard), furniture_mapping_zh 風格↔家具橋樑欄位

### Community 250 - "Community 250"
Cohesion: 1.00
Nodes (3): AI 邊界紅線圖 (AI Guardrails Boundary), 測試計畫與測試案例 (Test Plan / Test Cases), 使用者驗收測試計畫 (UAT Plan)

## Ambiguous Edges - Review These
- `Eight-Step Condensed Workflow` → `Remote Interior Render Contract`  [AMBIGUOUS]
  docs/contracts/REMOTE_RENDER_CONTRACT.md · relation: conceptually_related_to
- `OpenRouter 一鍵生圖與設計提案 PDF 全鏈` → `Copywriting Skill`  [AMBIGUOUS]
  copywriting_SKILL.md · relation: conceptually_related_to

## Knowledge Gaps
- **389 isolated node(s):** `THIN_MIRROR_TYPES`, `TYPE_LABELS`, `NAME_TOKEN_ZH`, `workflowMeta`, `furnitureMetric` (+384 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Eight-Step Condensed Workflow` and `Remote Interior Render Contract`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `OpenRouter 一鍵生圖與設計提案 PDF 全鏈` and `Copywriting Skill`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `createSceneViewer()` connect `Community 55` to `Scene V2 Room & Furniture UI`, `Community 133`, `Community 135`, `Three.js Geometry (minified)`, `Community 71`, `Community 171`, `Surface & Color Options UI`, `Community 183`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `loadScene()` connect `Three.js Geometry (minified)` to `Three.js Scene Bundle (minified)`, `Community 55`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `analyze_floorplan_image()` connect `Floorplan Vision Analysis` to `Community 34`, `Community 130`, `FastAPI Agent Endpoints`, `Community 73`, `Community 48`, `Floorplan to DXF`, `Community 148`, `Community 154`, `Community 91`, `Community 93`, `Community 62`, `Community 63`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 47 inferred relationships involving `bindEvents()` (e.g. with `addMissedRoom()` and `applyCalibration()`) actually correct?**
  _`bindEvents()` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `constructor()` (e.g. with `A()` and `be()`) actually correct?**
  _`constructor()` has 44 INFERRED edges - model-reasoned connections that need verification._