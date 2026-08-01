# Graph Report - C:/RoomPilot-Agent  (2026-07-31)

## Corpus Check
- Large corpus: 1478 files · ~18,753,400 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 4121 nodes · 10148 edges · 196 communities (182 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 481 edges (avg confidence: 0.66)
- Token cost: 546,226 input · 0 output

## Community Hubs (Navigation)
- Questionnaire Answer Logic
- Agent Placement Knowledge Rules
- Scene Structure Editing Actions
- Scene V2 Contract Tests
- Cody Floorplan Adapter
- Wall and Opening Architecture
- GLB Model Downloader Scripts
- Style Card Presentation
- Style Pack and Furniture Ranking
- Catalog Connection and RAG Repository
- Scene Configuration Sync
- Scene Service Layout Planning
- Draco WASM Wrapper
- Catalog Manager CLI
- Furniture Size Sanitization
- Scene Guidance Tests
- S3 GLB Uploader
- Embedding Import to PostgreSQL
- Catalog Provider Mode and Health
- Room Geometry Repair
- Furniture Adjustment Engine
- Engineering Cost Service
- Scene Color Options
- Engineering Document Rendering
- Cloud Model Delivery
- 2D Layout Rendering Helpers
- PostgreSQL Catalog Repository
- Cody Semantic Room Labeler
- Catalog Admin Repository
- Clearance and Collision Checking
- GLB Asset Lookup and Style DB
- Draco Decoder Runtime
- Model Delivery and Quarantine Contracts
- Engineering Document MVP Contract
- Clearance Zone Domain
- Project and Render API Routes
- Questionnaire Visual Catalog
- Library Page Filters
- Catalog Admin Auth and Writes
- React R3F Prototype App
- Floorplan Image Analysis
- Room Icon Classification
- Engineering Knowledge Repository
- SQLite Project Store
- Integration Log and Ownership
- Style DB Catalog Adapter
- Demo App Stubs
- Confirmation Gate and DXF Payload
- Room Recognition Evaluation
- PostgreSQL Project Store
- Runtime Paths and Workflow API
- RAG LLM Query Parsers
- RAG Vocabulary Domain
- Advanced RAG Fusion Service
- Project Store Factory
- RAG Model Runtime Cache
- Furniture Catalog Endpoints
- frontend3d Dependencies
- Scene Visual Regression Tests
- Surface Material Processing
- Furniture RAG Models
- Remote Render Service
- Furniture Naming and Scene Add
- RAG Testbed Frontend
- Draco Attribute Decoding
- Catalog CRUD Tests
- Engineering Frontend Snapshot
- Scene Chat and Style Picker
- Scene Intake and Proposals
- Agent Frontend Backend Contract
- Engineering Data Models
- Engineering Workbook Builder
- Official Cloud Catalog
- RAG Search Job API
- Cloud Image Previews
- Design Scheme Collections
- DXF Room Building
- Intake Service and OpenRouter
- Layout Region Placement
- PBR Realism Tests
- Architecture Module Map
- Surface Style Resolution
- 2D Furniture Library
- Room Requirement Options
- Draco Exception Handling
- Workflow Gate Sequence
- API Design and Security Scenarios
- Engineering Data Dictionary
- Room Inference From Walls
- Scene Guidance and Change Report
- Scene Unit Contracts
- Furniture RAG Service
- Step 6-8 Condensed Flow
- Owner Geometry Boundaries
- Skill Pack Invocation Rules
- Vision Line Analysis
- Furniture Model File Serving
- Frontend Common Fetch Helpers
- RAG API Tests
- Project Store Hardening
- Library Formatting Helpers
- Library Thumbnail Rendering
- Material Scheme Generation
- Scene Workflow State Machine
- RAG Retrieval Orchestration Docs
- Brief PRD and BDD Guides
- Quarantine Data Exclusion
- Catalog Pagination Contract
- Vision Geometry Detection
- Engineering Contract Exports
- Engineering Quantity Service
- DXF Parser Upgrade3D
- Floorplan Calibration
- Requirements and Validation Order
- Frontend Architecture Docs
- Owner Routing and Contradictions
- Engine Adjust API Docs
- Centimeter Coordinate Contract
- Home Landing Page
- Delivery Manifest and Recommendations
- Furniture Retrieval Scoring
- Layout Scene Boundary Contract
- Image Manifest Contract Tests
- Deployment Gates and Status Codes
- Cloud Catalog Bridge Tests
- Furniture Embeddings Contract
- Kai and Bella Persistence Duties
- Field Naming and Unit Rules
- Reporting and Parallel Work Rules
- Demo Skeleton and GLB Validation
- Room Requirement Tests
- OCR Provider
- Centimeter Canonicalization
- Bella Frontend Ownership
- Cody Recognition Pipeline Docs
- Floorplan Vision API Tests
- Official Catalog SQL Tests
- Product Step Routing
- LLM Prompt Contract
- Skill Pack Validator
- Room Icon Templates and Server Rules
- Reference Plan Matcher
- RAG Status Page Contract
- Dimensioned Plan Annotations
- Text Encoding Repair
- Draco Binary Loading
- Engineering Documents API Tests
- Adoption and Merge Prohibitions
- Source Manifest Builder
- Engine and RAG Boundaries
- Library Proposal List
- Window Type Presets
- Draco Runtime Callbacks
- RAG Settings Loader
- StylePack Rendering Contract
- Engineering Snapshot Tests
- RAG Frontend Tests
- Calibration Tests
- Furniture Retrieval Tests
- Code Review Method
- Engineering Page Boundaries
- Evaluation Evidence Chain
- Uploader Script Rules
- Engineering Frontend Tests
- Scene Delivery Tests
- Surface Material Tests
- Furniture Picker Clearance
- Window Evaluation Script
- Cross-Folder Change Protocol
- Engineering Router Wiring
- Engineering Link Widget
- Three.js Draco Loader Setup
- Scene Requirements Gate
- Draco Memory Management
- Env Example Contract Test
- ADR and Work Decomposition
- Agent Package Init
- Price Type Separation
- Engineering Package Init
- Services Package Init
- Spatial Data Package Init
- L1 Static Checks
- Project Metadata

## God Nodes (most connected - your core abstractions)
1. `bindEvents()` - 139 edges
2. `run_workflow_script()` - 91 edges
3. `scheduleSave()` - 67 edges
4. `PlacedFurniture` - 53 edges
5. `setStatus()` - 53 edges
6. `Room` - 49 edges
7. `ProjectSnapshot` - 47 edges
8. `renderSpaceOverlay()` - 40 edges
9. `analyze_floorplan_image()` - 39 edges
10. `restoreProject()` - 38 edges

## Surprising Connections (you probably didn't know these)
- `Structured Data vs RAG Document Split` --semantically_similar_to--> `Graph RAG Retrieval-Only Boundary`  [INFERRED] [semantically similar]
  backend/catalog/data/engineering/README.md → AGENTS.md
- `EquipmentMEPMapping` --conceptually_related_to--> `Appliance Questionnaire / render_context Boundary`  [AMBIGUOUS]
  backend/catalog/data/engineering/DATA_DICTIONARY.md → AGENTS.md
- `Cross-Owner Handoff Template` --semantically_similar_to--> `跨資料夾修改 Cross-Folder Change Protocol`  [INFERRED] [semantically similar]
  .agents/skills/roompilot-workflow-max/references/context-and-handoffs.md → AGENTS.md
- `L2 Owner-Focused Behavior Evidence` --semantically_similar_to--> `AGENTS.md 驗證矩陣 Validation Matrix`  [INFERRED] [semantically similar]
  .agents/skills/roompilot-workflow-max/references/validation-matrix.md → AGENTS.md
- `L4 Workflow and Real Environment` --semantically_similar_to--> `OpenRouter Failure and Deterministic Fallback`  [INFERRED] [semantically similar]
  .agents/skills/roompilot-workflow-max/references/validation-matrix.md → backend/agent/prompts/ROOMPILOT_LLM.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Full Workflow Gate Sequence (Gate 0-5)** — _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_0_evidence, _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_1_contract_trace, _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_2_acceptance_and_design, _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_3_implementation, _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_4_integration, _agents_skills_roompilot_workflow_max_references_01_workflow_manual_gate_5_delivery [EXTRACTED 1.00]
- **Non-Negotiable RoomPilot Boundaries** — _agents_skills_roompilot_workflow_max_skill_centimetre_unit_rule, _agents_skills_roompilot_workflow_max_skill_layout_json, _agents_skills_roompilot_workflow_max_skill_scene_json, _agents_skills_roompilot_workflow_max_skill_graph_rag_boundary, _agents_skills_roompilot_workflow_max_skill_vector_rag_boundary, _agents_skills_roompilot_workflow_max_skill_engine_geometry_authority, _agents_skills_roompilot_workflow_max_skill_postgresql_catalog_provider, _agents_skills_roompilot_workflow_max_skill_appliance_context_rule, _agents_skills_roompilot_workflow_max_skill_quarantine_exclusion_rule, _agents_skills_roompilot_workflow_max_skill_production_ui_boundary, _agents_skills_roompilot_workflow_max_skill_secrets_exclusion_rule [EXTRACTED 1.00]
- **Step 6-8 Catalog, Lock, and Render Flow** — _agents_skills_roompilot_workflow_max_references_17_frontend_information_architecture_step_6_catalog_coordination, _agents_skills_roompilot_workflow_max_references_17_frontend_information_architecture_step_7_lock_gate, _agents_skills_roompilot_workflow_max_references_17_frontend_information_architecture_step_8_render_context, _agents_skills_roompilot_workflow_max_references_03_bdd_guide_lock_and_render_scenario, _agents_skills_roompilot_workflow_max_references_13_security_and_readiness_render_privacy, _agents_skills_roompilot_workflow_max_skill_scene_json [INFERRED 0.85]
- **Eight-Step Product Flow and Its Data Boundaries** — readme_eight_step_workflow, readme_system_architecture, agents_layout_json, agents_scene_json, agents_engine_geometry_authority, agents_furniture_catalog_current_view, _agents_skills_roompilot_workflow_max_references_contract_routing_product_step_routing [EXTRACTED 1.00]
- **Engineering Document MVP Knowledge Pipeline** — readme_engineering_document_mvp, backend_catalog_data_engineering_data_dictionary_workitem, backend_catalog_data_engineering_data_dictionary_pricerecord, backend_catalog_data_engineering_data_dictionary_productivityrecord, backend_catalog_data_engineering_data_dictionary_constructionknowledge, backend_catalog_data_engineering_readme_structured_vs_rag_split, readme_advanced_rag_vector_adapter, readme_demo_mode [INFERRED 0.95]
- **L0-L5 Validation Escalation Ladder** — _agents_skills_roompilot_workflow_max_references_validation_matrix_l0_governance_and_trace, _agents_skills_roompilot_workflow_max_references_validation_matrix_l1_static_checks, _agents_skills_roompilot_workflow_max_references_validation_matrix_l2_owner_focused_behavior, _agents_skills_roompilot_workflow_max_references_validation_matrix_l3_contract_producer_and_consumer, _agents_skills_roompilot_workflow_max_references_validation_matrix_l4_workflow_and_real_environment, _agents_skills_roompilot_workflow_max_references_validation_matrix_l5_final_integration [EXTRACTED 1.00]
- **Owner Module Boundary Rules Across backend/** — backend_engine_agents_geometry_placement_engine, backend_floorplan_agents_floorplan_recognition, backend_server_agents_production_app, backend_spatial_data_agents_spatial_data_boundary, backend_upgrade3d_agents_confirmed_layout_to_3d [INFERRED 0.85]
- **Placement Legality Validation Flow** — backend_engine_readme_check_placement_with_clearance, backend_engine_readme_validation_order, backend_engine_readme_clearancezone, backend_engine_readme_failure_vocabulary, backend_engine_readme_place_furniture [EXTRACTED 1.00]
- **Production Web Page Set (single FastAPI frontend)** — backend_server_static_index_home_landing, backend_server_static_styles_style_selector, backend_server_static_library_furniture_picker, backend_server_static_scene_eight_step_workflow, backend_server_static_engineering_engineering_page, backend_server_static_rag_rag_testbed [EXTRACTED 1.00]
- **PostgreSQL Phased Migration to a Single Source of Truth** — docs_contracts_postgresql_catalog_read_phase1, docs_contracts_postgresql_catalog_crud_phase2, docs_contracts_postgresql_project_store_phase3, docs_contracts_postgresql_runtime_catalog_phase4, docs_contracts_postgresql_single_source_phase5, docs_contracts_postgresql_furniture_embeddings [EXTRACTED 1.00]
- **Locked-Snapshot Engineering Document Pipeline** — docs_contracts_engineering_document_mvp_projectsnapshot, docs_contracts_engineering_document_mvp_revision_lock, docs_contracts_engineering_document_mvp_quantity_service, docs_contracts_engineering_document_mvp_rule_service, docs_contracts_engineering_document_mvp_advanced_rag, docs_contracts_engineering_document_mvp_cost_service, docs_contracts_engineering_document_mvp_schedule_service, docs_contracts_engineering_document_mvp_reportpayload [EXTRACTED 1.00]
- **layout_json to scene_json to Render Ownership Chain** — docs_contracts_layout_scene_boundary_contract_layout_json, docs_contracts_layout_scene_boundary_contract_scene_json, docs_contracts_layout_scene_boundary_contract_graph_rag_boundary, docs_team_ai_ownership_ancai, docs_contracts_remote_render_contract_render_jobs_api, docs_roompilot________pipeline_ownership [INFERRED 0.85]
- **RoomPilot Seven-Owner Responsibility Matrix** — docs_owners_ancai_ancai_ai_profile, docs_owners_bella_bella_ai_profile, docs_owners_ben_ben_ai_profile, docs_owners_cody_cody_ai_profile, docs_owners_django_django_ai_profile, docs_owners_kai_kai_ai_profile, docs_owners_yen_yen_ai_profile [EXTRACTED 1.00]
- **Furniture Catalog and Vector Delivery Flow** — docs_owners_kai_catalog_import_pipeline, scripts_readme_roompilot_s3_glb_uploader, scripts_readme_roompilot_s3_image_uploader, scripts_sql_readme_import_official_catalog_to_postgres, scripts_sql_readme_import_furniture_embeddings_to_postgres, docs_owners_kai_furniture_catalog_api_current_view [EXTRACTED 1.00]
- **demo_app Skeleton Pipeline (stub-real-stub)** — examples_demo_app_readme_agent_stub, examples_demo_app_readme_furniture_engine, examples_demo_app_readme_render_style_stub, examples_demo_app_static_index_sendchat, examples_demo_app_static_index_applystyle [EXTRACTED 1.00]

## Communities (196 total, 14 thin omitted)

### Community 0 - "Questionnaire Answer Logic"
Cohesion: 0.03
Nodes (121): finishesGate(), occupantsFromBasicAnswers(), questionnaireSummary(), questionsForIndividualRooms(), questionsForRooms(), ROOM_TO_VISUAL_SPACES, suggestSharedRoomAnswers(), VISUAL_SPACE_LABELS (+113 more)

### Community 1 - "Agent Placement Knowledge Rules"
Cohesion: 0.06
Nodes (82): family_of(), prompt_rules(), 家具擺放規則：Agent 選件與擺位紀律共用的單一事實來源。 兩個消費端共用同一份資料： - ``select.py`` 透過…, 從知識表生成 LLM 選件必須遵守的繁中條文。, 把型錄類型摺疊成擺位族系；未知類型原樣返回。, _zh(), _anchor_names(), _clean_size_cm() (+74 more)

### Community 2 - "Scene Structure Editing Actions"
Cohesion: 0.09
Nodes (88): calibrationActionState(), attachedOpenings(), addDroppedStructure(), addFurnitureFromLibrary(), addMissedRoom(), applyAttachedOpeningUpdates(), applyCalibration(), applySelectedStructureSize() (+80 more)

### Community 3 - "Scene V2 Contract Tests"
Cohesion: 0.02
Nodes (3): _space_heading_html(), test_room_editor_is_embedded_in_the_plan_heading(), test_structure_legend_uses_heading_space_and_window_markers_match_review_numbers()

### Community 4 - "Cody Floorplan Adapter"
Cohesion: 0.05
Nodes (78): _axis_segment(), _carve_band_openings(), _clean_door_items(), _decode_image(), _dedupe_rects(), _door_axis(), _door_candidates_from_wall_gaps(), _door_score() (+70 more)

### Community 5 - "Wall and Opening Architecture"
Cohesion: 0.05
Nodes (67): doorOpeningForWallTopology(), openingBelongsToWall(), openingWallInterval(), point(), segmentId(), segmentVector(), wallEndpointBordersOpening(), wallSectionSpan() (+59 more)

### Community 6 - "GLB Model Downloader Scripts"
Cohesion: 0.05
Nodes (72): ArgumentParser, abo_help(), add_model_source_arguments(), build_abo_furniture_args(), build_abo_home_args(), build_model_parser(), common_spec_value(), download_main() (+64 more)

### Community 7 - "Style Card Presentation"
Cohesion: 0.05
Nodes (69): formatList(), formatTypeLabel(), allFloorSurfaces(), allWallSurfaces(), cardToneDescription(), CLEAN_FURNITURE_GROUPS, countFurnitureForStyle(), countFurnitureGroups() (+61 more)

### Community 8 - "Style Pack and Furniture Ranking"
Cohesion: 0.05
Nodes (68): catalogFurnitureOffer(), rankCatalogFurniture(), applyStylePack(), buildPack(), CEILING_STYLES, DEFAULT_RENDERING, detectCeilingConflicts(), LIGHT_STYLES (+60 more)

### Community 9 - "Catalog Connection and RAG Repository"
Cohesion: 0.08
Nodes (57): borrow_catalog_connection(), catalog_dict_cursor(), Share the catalog pool with other Kai-owned PostgreSQL repositories., Return a RealDictCursor without duplicating psycopg2 setup code., embedding_status(), load_group_price_stats(), Any, Path (+49 more)

### Community 10 - "Scene Configuration Sync"
Cohesion: 0.07
Nodes (65): numeric(), removeFurniture2dBySceneObject(), sceneObjectId(), upsertFurniture2dFromSceneObject(), mergeCatalogFurniture(), toSceneFurniture(), buildRoomRequirementsPayload(), PRESET_SURFACE_IDS (+57 more)

### Community 11 - "Scene Service Layout Planning"
Cohesion: 0.07
Nodes (61): 前端本地操作(替換/移除/新增/重抽)後,由 furniture_engine 重算全場座標。 傳 floorplan(含 wall_segments)可重建…, 依風格加入軟裝，所有最終座標仍由家具引擎決定。, scene_decorate(), scene_layout(), build_questionnaire_prompt(), build_scene_payload(), build_scene_plan(), catalog_item_matches_type_semantics() (+53 more)

### Community 12 - "Draco WASM Wrapper"
Cohesion: 0.07
Nodes (25): c(), A(), ba(), C(), D(), E(), f(), G() (+17 more)

### Community 13 - "Catalog Manager CLI"
Cohesion: 0.07
Nodes (61): CatalogToolError, check_glb_action(), common_value(), dimension_value(), extract_items(), glb_scan(), interactive_main(), interactive_merge() (+53 more)

### Community 14 - "Furniture Size Sanitization"
Cohesion: 0.08
Nodes (52): _positive(), 修補一件家具的尺寸(cm)。DB 值合理就用;否則依序用名稱尺寸、類型預設。, sanitize_size_cm(), _small_appliance_size(), agent_furniture_select(), _appliance_payload_cache(), _candidate_match_reason(), _candidate_quantity_template() (+44 more)

### Community 15 - "Scene Guidance Tests"
Cohesion: 0.05
Nodes (50): test_manual_scale_confirmation_replaces_low_confidence_ocr_scale(), test_recognition_presentation_summarizes_rooms_and_only_prompts_uncertain_findings(), test_three_material_schemes_preserve_layout_and_only_override_compatible_slots(), test_wall_boxing_report_uses_one_change_for_customer_and_designer_views(), test_api_payload_repair_handles_nested_saved_project_data(), test_mojibake_repair_restores_traditional_chinese_without_changing_valid_text(), test_2d_collision_footprint_respects_furniture_rotation(), test_2d_form_replacement_preserves_position_and_uses_new_real_size() (+42 more)

### Community 16 - "S3 GLB Uploader"
Cohesion: 0.07
Nodes (52): add_result_columns(), clean_text(), create_aws_clients(), fill_presigned_url(), fill_s3_result(), find_s3_object(), get_paths(), main() (+44 more)

### Community 17 - "Embedding Import to PostgreSQL"
Cohesion: 0.12
Nodes (50): EmbeddingRow, EmbeddingSource, load_catalog(), load_records(), main(), parse_args(), prepare_embedding_rows(), Any (+42 more)

### Community 18 - "Catalog Provider Mode and Health"
Cohesion: 0.07
Nodes (40): catalog_provider_mode(), Return strict ``postgres`` by default or explicit offline ``json``., api_health(), _auto_decor_catalog_item(), build_site_payload(), _catalog_count_summary(), catalog_status(), catalog_status_api() (+32 more)

### Community 19 - "Room Geometry Repair"
Cohesion: 0.08
Nodes (44): deleteSchemeB(), orthogonalizeNearAxisEdges(), polygonArea(), repairLoadedRoomPolygon(), beamDragGeometry(), canMarkWallForDemolition(), dedupeDoorCandidates(), dedupeWindowCandidates() (+36 more)

### Community 20 - "Furniture Adjustment Engine"
Cohesion: 0.08
Nodes (39): adjust_furniture(), move_furniture(), adjust_furniture:依 Agent 已拆解好的結構化指令,調整家具位置/角度。 對應 SSOT 文件 F6:「自然語言調家具位置/數量,重繪」…, 嘗試移動家具,採用軸分離策略(對應原型的 moveTo): X 軸跟 Y 軸分開檢查,能走多少走多少,而不是全有全無。, 統一入口,吃 Agent 拆解好的結構化指令。 command 範例: {"action": "move", "dx": 50, "dy": 0}…, PlacedFurniture, 擺放屬性:place_furniture / adjust_furniture 的輸出結果 這正是 SSOT 文件第 8…, 回傳未旋轉時的邊界 (min_x, min_y, max_x, max_y),旋轉版在 geometry.py 處理 (+31 more)

### Community 21 - "Engineering Cost Service"
Cohesion: 0.15
Nodes (29): CostService, Calculate from structured PriceRecord only; never ask an LLM for prices., EstimateResult, NarrativeResult, ProjectSnapshot, QuantityResult, RetrievalResult, RiskItem (+21 more)

### Community 22 - "Scene Color Options"
Cohesion: 0.05
Nodes (36): buildColorOptions(), COLOR_OPTION_PRESETS, colorOptionMatches(), colorOptions, DEFAULT_FURNITURE_BY_SPACE, elements, fallbackSurfaces, floorOptionLabelMap (+28 more)

### Community 23 - "Engineering Document Rendering"
Cohesion: 0.14
Nodes (17): DocumentService, Path, RuntimeError, WorkbookGenerationUnavailable, DocumentManifest, JobStatus, ReportPayload, EngineeringRepository (+9 more)

### Community 24 - "Cloud Model Delivery"
Cohesion: 0.10
Nodes (38): _candidate_ids(), clear_cloud_model_caches(), cloud_model_status(), cloud_model_url(), _cloudfront_base_url(), _current_manifest_index(), _delivery_url_from_row(), _https_url() (+30 more)

### Community 25 - "2D Layout Rendering Helpers"
Cohesion: 0.08
Nodes (41): furnitureCollisionFootprintCm(), activateWhiteWalkMode(), activePanelName(), applySurfaceOverrides(), beamBandSvg(), cmToPixel(), configurationBlockingFurnitureByRoom(), configurationDeferredFurnitureByRoom() (+33 more)

### Community 26 - "PostgreSQL Catalog Repository"
Cohesion: 0.15
Nodes (38): _as_list(), _as_number(), _as_numbers(), _borrow_connection(), _catalog_group(), catalog_provider_status(), catalog_summary(), CatalogQuery (+30 more)

### Community 27 - "Cody Semantic Room Labeler"
Cohesion: 0.11
Nodes (36): cody_semantic_room_labeler_status(), ensure_cody_semantic_masks(), ensure_cody_semantic_weights(), _gh_token(), _has_room_mask(), _infer_script_path(), load_cody_semantic_mask(), _mask_path_for_image() (+28 more)

### Community 28 - "Catalog Admin Repository"
Cohesion: 0.18
Nodes (33): _activation_gaps(), _as_utc(), CatalogAdminConflict, CatalogAdminError, CatalogAdminNotFound, CatalogAdminReferenceError, _category_id(), _check_revision() (+25 more)

### Community 29 - "Clearance and Collision Checking"
Cohesion: 0.13
Nodes (31): rotate_furniture(), check_placement_with_clearance(), clearance.py — 開合淨空運算(F3/F6 分工範圍:碰撞/淨空運算) 處理:衣櫃門、冰箱門、抽屜等開合時所需的額外空間,…, 本體碰撞 + 淨空檢查的總入口(之後 placement/adjustment 可改用這個), check_placement(), furniture_polygon(), hits_furniture(), hits_wall() (+23 more)

### Community 30 - "GLB Asset Lookup and Style DB"
Cohesion: 0.11
Nodes (30): _dataset_glb_lookup(), _external_glb_bytes(), _external_zip_entry_lookup(), _external_zip_entry_variants(), _glb_lookup_keys(), _is_remote_glb_url(), _iter_external_zip_paths(), load_style_database() (+22 more)

### Community 31 - "Draco Decoder Runtime"
Cohesion: 0.07
Nodes (10): addRunDependency(), createWasm(), ensureString(), intArrayFromString(), l(), lengthBytesUTF8(), ma(), p() (+2 more)

### Community 32 - "Model Delivery and Quarantine Contracts"
Cohesion: 0.09
Nodes (34): Kai PostgreSQL Catalog Import Flow, Whole-House Floor and Accent Wall Consistency, Furniture Model Delivery Contract, CloudFront Delivery Mode, GLB Upload Manifest, Manual Offline ZIP Fallback, Unmatched Cloud Furniture Quarantine, Graph RAG Evidence-Only Boundary (+26 more)

### Community 33 - "Engineering Document MVP Contract"
Cohesion: 0.12
Nodes (34): Designer-Locked Engineering Document MVP Contract, Advanced Structured RAG, Cost Service and PriceRecord Formula, ROOMPILOT_DEMO_MODE Synthetic Pricing, Machine-Readable Contracts Generated From Code, ProjectSnapshot (roompilot.project-snapshot.v1), Quantity Service, Single ReportPayload for Three Outputs (+26 more)

### Community 34 - "Clearance Zone Domain"
Cohesion: 0.11
Nodes (32): clearance_conflict(), clearance_polygon(), Polygon, 算出這件家具的淨空範圍多邊形(不含本體),無淨空需求時回傳 None, 檢查這件家具的淨空範圍是否有衝突,回傳 None 表示無衝突。 檢查順序:淨空撞牆 → 淨空撞其他家具本體 → 淨空撞其他家具的淨空, ClearanceZone, FurnitureCatalogItem, 開合淨空需求:家具的哪一面需要保留多少空間 side 以「未旋轉時家具自己的方向」為準: front = +y 方向(面向房間)、back = -y、left… (+24 more)

### Community 35 - "Project and Render API Routes"
Cohesion: 0.11
Nodes (32): agent_intake_answer(), agent_intake_start(), analyze_project_floorplan(), cost_estimate(), create_project(), create_project_render(), create_project_render_jobs(), floorplan_analyze() (+24 more)

### Community 36 - "Questionnaire Visual Catalog"
Cohesion: 0.11
Nodes (21): load_questionnaire_visual_catalog(), _normalized_option(), Connection, Path, ValueError, QuestionnaireCatalogError, QuestionnaireVisualStore, SQLite query index generated from the versioned questionnaire JSON. (+13 more)

### Community 37 - "Library Page Filters"
Cohesion: 0.11
Nodes (31): scrollPageTop(), styleNameMap(), applyLibraryFilters(), buildSceneHandoffPayload(), COLOR_LABELS, data, elements, enterSceneWithProposal() (+23 more)

### Community 38 - "Catalog Admin Auth and Writes"
Cohesion: 0.10
Nodes (26): catalog_admin_token(), catalog_admin_writes_enabled(), Read the admin token from process environment or the ignored .env file., Writes are deliberately disabled in JSON and implicit auto modes., _admin_principal(), AnnotationInput, create_catalog_furniture(), delete_catalog_furniture() (+18 more)

### Community 39 - "React R3F Prototype App"
Cohesion: 0.09
Nodes (24): App(), DEFAULTS, FurnitureLayer(), furnitureUrl(), Ghost(), GHOST_FREE, GHOST_SNAP, Item (+16 more)

### Community 40 - "Floorplan Image Analysis"
Cohesion: 0.15
Nodes (28): analyze_floorplan_image(), 分析建商平面圖；不確定的尺度必須透過 confirmation seam 補齊。, confirm_floorplan_analysis(), 套用使用者修正並產生可進入 RoomPilot 引擎的唯一確認版本。, decode_image(), profile_floorplan_image(), ndarray, Floor-plan image decoding and lightweight input profiling. (+20 more)

### Community 41 - "Room Icon Classification"
Cohesion: 0.17
Nodes (28): apply_icon_room_labels(), _chamfer_similarity(), _classify_icon(), _coarse_similarity(), detect_room_icons(), _generic_pending_label(), load_icon_templates(), _mask_text() (+20 more)

### Community 42 - "Engineering Knowledge Repository"
Cohesion: 0.18
Nodes (9): JsonEngineeringKnowledgeRepository, Any, Path, Versioned MVP engineering seed repository. This repository is separate from the…, validate_engineering_knowledge(), _snapshot(), test_engineering_knowledge_contract_and_structured_retrieval(), test_vector_adapter_evidence_survives_fusion_and_reranking() (+1 more)

### Community 43 - "SQLite Project Store"
Cohesion: 0.15
Nodes (12): ProjectStore, Path, Persist a versioned PNG without replacing earlier proposal history., 將舊 worktree 的專案與原圖合併到目前的共用資料庫。, Match the PostgreSQL store lifecycle; SQLite opens per operation., Small SQLite-backed project store used by the browser workflow., _utc_now(), Row (+4 more)

### Community 44 - "Integration Log and Ownership"
Cohesion: 0.09
Nodes (29): Floorplan Dataset Tuning Backlog, Low-Confidence Human Confirmation Gate, Recognition Evaluation Metrics, Shared 2D/3D Furniture Identity, Bella Test1 Integration Log, Two-Way 2D/3D Furniture Selection Sync, Ancai-dev 3D Selection Backport, Appliance Catalog Flow Retirement (+21 more)

### Community 45 - "Style DB Catalog Adapter"
Cohesion: 0.11
Nodes (23): catalog_item_from_scene_object(), 家具型錄轉接層：把家具資料庫項目轉成擺放引擎的型錄物件。 型錄、Python 引擎與前端 payload 全程使用公分，不在這裡換算單位。…, 場景物件轉為公分引擎型錄物件，不做單位換算。, place_overlay_on_furniture(), 將地毯等地面覆蓋物置於目標家具下，並由引擎驗證牆與房間邊界。, _clamp_axis(), generate_layout(), _hinted_wall_candidate() (+15 more)

### Community 46 - "Demo App Stubs"
Cohesion: 0.10
Nodes (23): place_furniture_batch(), 批次放置多件家具(依序放,後放的要避開先放好的)。 items: [(catalog_item, item_id), ...] 回傳: {"placed":…, parse_command(), agent_stub.py — 「Agent 核心」的假實作佔位(柏彥之後把這裡換成真 LLM function-calling) 現在(P0…, 一句自然語言 → 結構化意圖(這就是 Agent 目前『假裝理解』的部分) 回傳: { intent: "place_furniture" |…, chat(), demo_room(), health() (+15 more)

### Community 47 - "Confirmation Gate and DXF Payload"
Cohesion: 0.12
Nodes (22): _canonicalize_floorplan_cm(), _dxf_text(), Any, 人工確認閘門與 DXF／引擎 payload 邊界。, Convert the metres-based DXF parser geometry into the public cm contract., 建商平面圖的尺度、幾何、空間語意與設備需求分析。, infer_room_requirements(), _item() (+14 more)

### Community 48 - "Room Recognition Evaluation"
Cohesion: 0.16
Nodes (24): build_room_confusion(), match_room_masks(), normalize_room_label(), _polygon_mask(), Any, ndarray, Room recognition evaluation helpers ported from Cody's v5 scoring flow., Score room segmentation and naming from labelled bool masks. (+16 more)

### Community 49 - "PostgreSQL Project Store"
Cohesion: 0.24
Nodes (6): PostgresProjectStore, Any, Path, ProjectStore-compatible repository backed by PostgreSQL JSONB., Legacy SQLite import is explicit through the one-time migration tool., _timestamp()

### Community 50 - "Runtime Paths and Workflow API"
Cohesion: 0.15
Nodes (21): legacy_runtime_dirs(), project_runtime_dir(), Path, 回傳所有 worktree 共用且可長期保存的執行資料目錄。, 找出需要合併至共用資料庫的舊 worktree 執行資料目錄。, _repository_root(), _create_project(), _png_bytes() (+13 more)

### Community 51 - "RAG LLM Query Parsers"
Cohesion: 0.21
Nodes (22): parse_query(), Any, Anthropic Structured Outputs adapter for Django's furniture query schema., _usage(), RuntimeError, RagDependencyError, RagDisabledError, RagError (+14 more)

### Community 52 - "RAG Vocabulary Domain"
Cohesion: 0.16
Nodes (19): load_vocab(), Any, Small, versioned vocabulary extracted from Django's RAG handoff., _FakeMessages, _FakeResponses, _item(), _plan(), Exception (+11 more)

### Community 53 - "Advanced RAG Fusion Service"
Cohesion: 0.22
Nodes (14): AdvancedRAGService, EngineeringSemanticRetriever, _EquipmentCandidate, NoopEngineeringSemanticRetriever, Any, Explicit Mock/Noop adapter; this is not vector retrieval., Structured + pluggable vector retrieval, fusion, reranking and evidence., ConstructionNote (+6 more)

### Community 54 - "Project Store Factory"
Cohesion: 0.15
Nodes (20): PostgreSQL JSONB persistence for RoomPilot projects and render metadata., build_project_store(), _compact_workflow_value(), _merge_dict(), project_store_provider(), ProjectStoreUnavailable, ProjectVersionConflict, RuntimeError (+12 more)

### Community 55 - "RAG Model Runtime Cache"
Cohesion: 0.16
Nodes (10): model_cache_status(), Any, Path, RagModelRuntime, Thread-safe, lazy, offline-only BGE-M3 model runtime., _repo_cache_path(), _repo_is_cached(), RagSettings (+2 more)

### Community 56 - "Furniture Catalog Endpoints"
Cohesion: 0.11
Nodes (20): postgres_catalog_requested(), _furniture_card_payload(), furniture_catalog(), _furniture_detail_payload(), _furniture_filter_options(), furniture_model(), _get_json_merged_furniture_by_id(), _get_merged_furniture_by_id() (+12 more)

### Community 57 - "frontend3d Dependencies"
Cohesion: 0.08
Nodes (23): dependencies, react, react-dom, @react-three/drei, @react-three/fiber, three, devDependencies, vite (+15 more)

### Community 58 - "Scene Visual Regression Tests"
Cohesion: 0.08
Nodes (12): test_all_confirmed_room_regions_share_the_initial_floor_surface(), test_bed_selection_rejects_wardrobe_and_drawer_models(), test_catalog_does_not_merge_same_named_bed_and_cabinet_models(), test_closed_door_leaf_lies_flat_inside_the_doorway(), test_door_leaf_rotates_from_the_confirmed_hinge_endpoint(), test_full_size_loft_bed_is_still_a_real_bed(), test_generic_glb_material_gets_a_safe_furniture_role_fallback(), test_material_schemes_explain_surface_and_furniture_changes() (+4 more)

### Community 59 - "Surface Material Processing"
Cohesion: 0.20
Nodes (19): _average_grout_color(), build_processed_surface_materials(), _hex_color(), installation_spec_for_surface(), _promote_generation(), Path, ValueError, _remove_path() (+11 more)

### Community 60 - "Furniture RAG Models"
Cohesion: 0.22
Nodes (17): Furniture RAG runtime backed by Kai's PostgreSQL pgvector catalog., BaseModel, model_validator, RagQueryItem, RagQueryPlan, Pydantic contracts for LLM parsing and the public RAG search API., allocate_budget(), build_filters() (+9 more)

### Community 61 - "Remote Render Service"
Cohesion: 0.22
Nodes (19): _is_number_triplet(), prepare_render_payload(), Any, RuntimeError, render_provider_status(), _render_timeout_seconds(), RenderProviderRejected, RenderProviderUnavailable (+11 more)

### Community 62 - "Furniture Naming and Scene Add"
Cohesion: 0.15
Nodes (22): formatFurnitureName(), NAME_TOKEN_ZH, addFurnitureToScene(), applySelectedMaterialScheme(), compactFurnitureName(), fetchStyledFurnitureCandidate(), getTypeLabel(), handleFurnitureMaterialEdit() (+14 more)

### Community 63 - "RAG Testbed Frontend"
Cohesion: 0.22
Nodes (21): appendChip(), createElement(), elements, filterLabel(), formatCurrency(), formatElapsed(), formatMilliseconds(), furnitureCard() (+13 more)

### Community 64 - "Draco Attribute Decoding"
Cohesion: 0.09
Nodes (22): AttributeOctahedronTransform(), AttributeQuantizationTransform(), AttributeTransformData(), castObject(), Decoder(), DecoderBuffer(), destroy(), DracoFloat32Array() (+14 more)

### Community 65 - "Catalog CRUD Tests"
Cohesion: 0.21
Nodes (19): CatalogAdminActivationError, _create_payload(), _enable_admin(), MonkeyPatch, skipif, Exercise the real API/DB contract and remove only the row created here., test_admin_api_disables_writes_outside_strict_postgres_mode(), test_admin_api_fails_closed_when_token_is_not_configured() (+11 more)

### Community 66 - "Engineering Frontend Snapshot"
Cohesion: 0.21
Nodes (19): api(), APPLIANCE_TYPES, buildProjectSnapshot(), clone(), errorMessage(), explicitOpeningAreaM2(), finite(), generatePackage() (+11 more)

### Community 67 - "Scene Chat and Style Picker"
Cohesion: 0.14
Nodes (21): appendChatMessage(), applyPendingStyleCard(), applySelectedStyleToBrief(), closeStylePicker(), confirmClientBrief(), confirmFloorplanAndContinue(), enterGuidedChat(), buildFloorplanConfirmationCorrections() (+13 more)

### Community 68 - "Scene Intake and Proposals"
Cohesion: 0.17
Nodes (21): applyDefaultRoomIfRequested(), applyLibraryProposalDefaults(), configureSceneIntakeControls(), estimateProposalFootprintCm2(), explainEmptyScene(), filterProposalForRoom(), formatProposalItemName(), generateScene() (+13 more)

### Community 69 - "Agent Frontend Backend Contract"
Cohesion: 0.15
Nodes (21): Pending Invalid Furniture List, Per-Room Questionnaire Furniture Selection, Agent Frontend/Backend Contract, client_brief Schema, Furniture Selection API with offers Whitelist, Deterministic guided_fallback Mode, Agent Intake API, LLM May Choose Furniture but Never Coordinates (+13 more)

### Community 70 - "Engineering Data Models"
Cohesion: 0.17
Nodes (17): EngineeringPackageRequest, EquipmentRequirement, EstimateLine, FurniturePlacement, LockRevisionRequest, MaterialSelection, MEPPoint, PointCm (+9 more)

### Community 71 - "Engineering Workbook Builder"
Cohesion: 0.11
Nodes (15): columnName(), estimate, estimateEnd, estimateHeaders, estimateRows, [inputPath, outputPath, ...flags], inspectFlag, previewFlag (+7 more)

### Community 72 - "Official Cloud Catalog"
Cohesion: 0.23
Nodes (17): build_official_catalog(), _load_json(), _load_manifest(), load_official_catalog(), official_catalog_diagnostics(), _official_style_candidates(), Any, Path (+9 more)

### Community 73 - "RAG Search Job API"
Cohesion: 0.21
Nodes (18): _cleanup_jobs(), create_rag_search_job(), _error_details(), get_rag_search_job(), _job_snapshot(), Exception, FileResponse, get (+10 more)

### Community 74 - "Cloud Image Previews"
Cohesion: 0.23
Nodes (16): _candidate_ids(), cloud_image_urls(), cloud_primary_image_url(), _cloudfront_base_url(), _current_manifest_index(), _delivery_url_from_row(), _https_url(), image_manifest_status() (+8 more)

### Community 75 - "Design Scheme Collections"
Cohesion: 0.17
Nodes (18): activateScheme(), clone(), COLLECTIONS, compactDesignSchemesForSpace(), emptyScheme(), ensureSchemeB(), hasRenovationChanges(), markSchemeLayoutsStale() (+10 more)

### Community 76 - "DXF Room Building"
Cohesion: 0.17
Nodes (16): build_room_from_dxf(), DxfRoomBuild, dxf_room.py — 把 app/backend/dxf_parser 產生的樓面 JSON 轉成 furniture_engine 的 Room。…, 便捷版:只回 Room(demo_app / 引擎直接用)。需要座標映射時改用 build_room_from_dxf。, dxf_parser 的公尺環轉為公分環。, 多邊形面積(shoelace,絕對值,cm²)。ring 為 [[x,z],...],首尾是否重複皆可。, 把一個環(閉合折線)的每條邊變成一段 Wall,並平移 (ox,oz) 到角落原點。, 轉換結果。room 與 offset 都使用公分。 (+8 more)

### Community 77 - "Intake Service and OpenRouter"
Cohesion: 0.27
Nodes (17): advance_intake(), _api_key(), _brief_copy(), _call_openrouter(), _count(), _fallback_extract(), _llm_messages(), _load_local_env() (+9 more)

### Community 78 - "Layout Region Placement"
Cohesion: 0.13
Nodes (11): _grid_place_in_boundary(), _inside_boundary(), orient_layout_toward_targets(), _placement_intersects_zones(), Orient automatically placed seating and work furniture toward useful targets., F6 拖曳落點驗證:單件家具在指定位置/角度是否合法(引擎檢查)。, 非矩形房間的最後防線:沿房間多邊形內部以 50cm 網格搜尋(由質心向外)。 錨點與引擎網格都以 bbox 為座標基準,房間只佔 bbox 一角時全會撲空,…, _scene_rotation_toward() (+3 more)

### Community 79 - "PBR Realism Tests"
Cohesion: 0.11
Nodes (11): test_architectural_openings_have_dedicated_physical_profiles(), test_furniture_roles_receive_distinct_realistic_pbr_parameters(), test_gap_window_has_no_usable_span_inside_the_split_host_wall(), test_gap_window_uses_its_own_host_wall_for_surface_material(), test_gap_window_wall_sections_end_flush_with_the_opening(), test_image_surfaces_keep_texture_detail_and_use_physical_profiles(), test_open_door_leaves_snap_to_two_distinct_existing_wall_gaps(), test_opening_edges_do_not_receive_wall_junction_caps() (+3 more)

### Community 80 - "Architecture Module Map"
Cohesion: 0.14
Nodes (17): 05 Architecture and Design, backend/agent Requirement and Repair Explanation, backend/catalog PostgreSQL Catalog Assets, backend/floorplan Recognition Module, backend/spatial_data Retrieval and Ranking, backend/upgrade3d Confirmed-Layout 3D Structure, Input to Persistence Data Flow View, Catalog PostgreSQL Views to Yen/Django to Engine Chain (+9 more)

### Community 81 - "Surface Style Resolution"
Cohesion: 0.15
Nodes (17): applySurfaceChoiceToCurrentScene(), buildSurfaceOptions(), getResolvedSurfaceChoice(), getStyleSceneLook(), getStyleSurfaceProfile(), handleSurfaceFilterClick(), handleSurfaceSearchInput(), normalizeSearchText() (+9 more)

### Community 82 - "2D Furniture Library"
Cohesion: 0.15
Nodes (15): createFurniture2DItem(), findFurniture2DVariant(), FURNITURE_2D_LIBRARY, furnitureFootprintStyle(), ICONS, planCmToLayerPixel(), recommendCompanionFurniture(), recommendedFurnitureForRoom() (+7 more)

### Community 83 - "Room Requirement Options"
Cohesion: 0.21
Nodes (16): applyRoomFinishScope(), buildSpecialRequestAnswer(), clone(), CONDITIONAL_OPTIONS, conditionalOptionId(), emptyRoomRequirement(), evaluateConditionalOption(), migrateLegacyFinishes() (+8 more)

### Community 85 - "Workflow Gate Sequence"
Cohesion: 0.14
Nodes (16): Gate 0 — Evidence, Gate 1 — Contract Trace, Gate 2 — Acceptance and Design, Gate 3 — Implementation, 01 RoomPilot Workflow Manual, Serialized Contract and Integration Decisions, 16 Work Breakdown Structure Plan, Non-Overlapping Work Packages (+8 more)

### Community 86 - "API Design and Security Scenarios"
Cohesion: 0.16
Nodes (16): Calibration Scenario, Lock and Render Blocking Scenario, ADR Decision Drivers, 06 API Design Specification, Catalog Admin Bearer-Token Contract, Catalog Soft Deletion (is_active=false), Allowlisted Response Fields Rule, Data and Access Checklist (+8 more)

### Community 87 - "Engineering Data Dictionary"
Cohesion: 0.18
Nodes (16): ConstructionKnowledge, EquipmentMEPMapping, MaterialWorkMapping, PriceRecord, ProductivityRecord, WorkItem, Price Source Priority Order, Productivity Record Requirements (+8 more)

### Community 88 - "Room Inference From Walls"
Cohesion: 0.23
Nodes (14): _apply_layout_label_suggestions(), infer_rooms_from_walls(), _polygon_area(), Any, 從 Cody 牆體幾何推導可人工確認的房間多邊形。, 將牆中心線光柵化，封閉門洞後取不接觸外框的空間。, Remove thin raster-closure needles without flattening normal room corners., 在沒有 OCR 房名時，對常見七區住宅格局提供低信心候選名稱。 (+6 more)

### Community 89 - "Scene Guidance and Change Report"
Cohesion: 0.18
Nodes (14): buildExplainableRecommendation(), buildRecognitionPresentation(), dimensionLabel(), EVIDENCE_KIND_LABELS, localizeEvidence(), REVIEW_REASON_LABELS, ROOM_LABELS, renderSpaceChangeReport() (+6 more)

### Community 90 - "Scene Unit Contracts"
Cohesion: 0.28
Nodes (15): centimeterDimensions(), editorPoint(), inferredGeometryScale(), normalizePolygon(), normalizeRing(), normalizeSavedSceneData(), normalizeSavedSpaceConfirmation(), normalizeSceneSegment() (+7 more)

### Community 91 - "Furniture RAG Service"
Cohesion: 0.29
Nodes (7): RagDatabaseError, FurnitureRagService, Any, Path, CatalogLoader, Parser, ProgressReporter

### Community 92 - "Step 6-8 Condensed Flow"
Cohesion: 0.21
Nodes (16): Bella Step 6-8 Condensed Flow Spec, Eight-Step Condensed Workflow, Indoor Walk Inspection Mode, Locked Proposal Snapshot, Step 7 Proposal Locking and Camera Selection, Step 8 AI Rendering and Proposal Package, Structure Change Returns to Step 4, Three Locked Candidate Palettes (+8 more)

### Community 93 - "Owner Geometry Boundaries"
Cohesion: 0.13
Nodes (16): Ancai AI Profile, Centimeter and Explicit Rotation Units, Deterministic Furniture Geometry Ownership, Centimeter Normalization of Cross-Module Output, layout_json Recognition Boundary, Django AI Profile, Graph RAG Spatial Relationships, RAG Retrieves Only, Ancai Decides Geometry Legality (+8 more)

### Community 94 - "Skill Pack Invocation Rules"
Cohesion: 0.17
Nodes (15): Default Prompt Invocation of roompilot-workflow-max, OpenAI Agent Interface Manifest, 04 Architecture Decision Record Template, No Duplicate Sources of Truth, Owner-Boundary Placement Checklist, 08 Project Structure Guide, Windows PowerShell / Uvicorn / PostgreSQL Local Baseline, 15 Documentation and Maintenance (+7 more)

### Community 95 - "Vision Line Analysis"
Cohesion: 0.25
Nodes (13): _clusters(), _dimension_evidence(), _dot_endpoints(), _lines(), _number_m(), Any, ndarray, 平面圖分析公開入口。 座標輸出遵守 RoomPilot 的跨模組公分契約；影像像素只保留在 evidence， 不會流入家具配置引擎。 (+5 more)

### Community 96 - "Furniture Model File Serving"
Cohesion: 0.19
Nodes (15): furniture_model_buffer(), furniture_model_gltf(), furniture_model_image(), _get_furniture_by_id(), _get_model_path_for_furniture(), get_project(), _gltf_payload_for_web(), _image_bytes_from_glb() (+7 more)

### Community 97 - "Frontend Common Fetch Helpers"
Cohesion: 0.23
Nodes (14): extractNameDimensions(), fetchFurniturePage(), fetchHomeData(), fetchJson(), fetchSceneBootstrap(), fetchSiteData(), fetchStylesData(), formatSize() (+6 more)

### Community 98 - "RAG API Tests"
Cohesion: 0.25
Nodes (11): TestClient, _clear_rag_jobs(), _FakeService, Exception, parametrize, test_rag_api_maps_failures(), test_rag_job_api_hides_upstream_failure_detail(), test_rag_job_api_reports_progress_and_result() (+3 more)

### Community 99 - "Project Store Hardening"
Cohesion: 0.24
Nodes (13): ValueError, The canonical workflow would exceed the persistence size budget., WorkflowTooLargeError, _png_bytes(), MonkeyPatch, Path, test_expected_revision_rejects_stale_update_without_overwriting(), test_legacy_database_is_migrated_with_revision_zero() (+5 more)

### Community 100 - "Library Formatting Helpers"
Cohesion: 0.32
Nodes (14): formatColorValue(), formatFurnitureName(), formatMaterialValue(), formatStyleName(), formatTypeName(), getPreferredTypesForGroup(), normalizeProposalItem(), populateFilters() (+6 more)

### Community 101 - "Library Thumbnail Rendering"
Cohesion: 0.19
Nodes (11): attachLibraryThumbnail(), cache, createStage(), disposeObject(), dracoLoader, fitModel(), loader, renderer (+3 more)

### Community 102 - "Material Scheme Generation"
Cohesion: 0.22
Nodes (13): classifyMaterialSlot(), COMPATIBLE_FINISHES, generateMaterialSchemes(), overrideForSlot(), paletteFor(), restoreOriginalMaterials(), ROLE_PATTERNS, SCHEME_NAMES (+5 more)

### Community 103 - "Scene Workflow State Machine"
Cohesion: 0.25
Nodes (12): canEnter(), clone(), createController(), createWorkflow(), initialState(), REQUIRED_COMPLETIONS, restoreWorkflow(), storageKey() (+4 more)

### Community 104 - "RAG Retrieval Orchestration Docs"
Cohesion: 0.18
Nodes (14): BGE Reranking and Style/Mood Scoring, Furniture RAG Retrieval Orchestration, OpenAI Structured Query Plan, Kai Stores Vectors, RAG Team Produces Them, Django RAG Runtime Dependencies, .env Local Secret Rule, PostgreSQL 17.10 Install and Data Import Guide, Orphan and Stale Embedding SQL Checks (+6 more)

### Community 105 - "Brief PRD and BDD Guides"
Cohesion: 0.21
Nodes (13): Observable Acceptance Criteria, Copy-Ready Brief Template, 02 Project Brief and PRD, 03 Behavior-Driven Development Guide, Placement Refusal Scenario, Required BDD Coverage Set, backend/engine Legal Geometry Module, Versioned layout_json/scene_json Test Fixtures (+5 more)

### Community 106 - "Quarantine Data Exclusion"
Cohesion: 0.22
Nodes (13): Quarantine and Unmatched Data Exclusion, Catalog and Materials Ownership (Kai), 舊友 12-Style Legacy Compatibility Entry, SF3D Legacy Empty Compatibility Source, Unmatched Cloud Furniture Empty Compatibility Source, 7,958 Active vs 599 Quarantined Split, Manifest SHA-256 Mirror Requirement, Official Furniture Set Definition (+5 more)

### Community 107 - "Catalog Pagination Contract"
Cohesion: 0.24
Nodes (11): CatalogPage, _postgres_page(), MonkeyPatch, Path, test_catalog_status_uses_postgres_asset_counts_without_manifest_csv(), test_furniture_api_uses_sql_page_without_loading_full_json_catalog(), test_furniture_detail_uses_postgres_primary_key_lookup(), test_kai_postgres_row_keeps_vlm_fields_needed_by_the_api() (+3 more)

### Community 108 - "Vision Geometry Detection"
Cohesion: 0.38
Nodes (12): _arc_score(), _dedupe(), detect_geometry(), _door_observations(), _hough_segments(), _overlap(), Any, ndarray (+4 more)

### Community 109 - "Engineering Contract Exports"
Cohesion: 0.32
Nodes (11): _engineering_openapi(), export_contracts(), main(), Any, Path, _schema_names(), _write_json(), _json() (+3 more)

### Community 110 - "Engineering Quantity Service"
Cohesion: 0.32
Nodes (10): RoomQuantity, _polygon_area_perimeter_cm(), QuantityService, Deterministic centimeter geometry only; never calls an LLM., _round(), _furniture(), _snapshot(), test_existing_placement_failure_is_not_silently_accepted() (+2 more)

### Community 111 - "DXF Parser Upgrade3D"
Cohesion: 0.19
Nodes (11): plan(), _collect(), _entity_segments(), _hatch_rings(), parse_dxf_bytes(), parse_dxf_file(), _process(), DXF -> 3D floor-plan JSON. ezdxf flattens CAD entities into 2D segments tagged… (+3 more)

### Community 112 - "Floorplan Calibration"
Cohesion: 0.22
Nodes (12): acceptDroppedFloorplan(), applyFloorplanCalibration(), buildScaleCalibration(), pointerToImagePoint(), drawDxfPreview(), floorplanNeedsCalibration(), prepareFloorplanCalibration(), previewFloorplan() (+4 more)

### Community 113 - "Requirements and Validation Order"
Cohesion: 0.19
Nodes (13): Placement Validation Order (boundary/wall/overlap/clearance), Furniture Selection and Repair Intent Policy, Structured requirements_json, Every Decision Traceable to Questionnaire or Catalog Evidence, Yen AI Profile, agent_stub.parse_command, furniture_engine Placement (real component), render_style_stub.render_style (+5 more)

### Community 114 - "Frontend Architecture Docs"
Cohesion: 0.21
Nodes (12): Workflow Is Not a Ninth Product Step, frontend3d React/R3F Prototype, Component Lifecycle and Teardown Sequence, 12 Frontend Architecture, Production Static UI Path (Three.js + FastAPI), React 18/R3F Prototype Path, Three.js Renderer and Resource Disposal Discipline, 17 Frontend Information Architecture (+4 more)

### Community 115 - "Owner Routing and Contradictions"
Cohesion: 0.30
Nodes (12): Known Live Contract Contradictions, Owner Routing Table, Ancai (Owner: backend/engine, geometry and legality), Bella (Owner: backend/server, production UI, integration), Ben (QA: testdata, evaluation and version evidence), Cody (Owner: backend/floorplan, backend/upgrade3d, testdata), Django (Owner: backend/spatial_data, evaluation, furniture RAG), roompilot.furniture_catalog_current PostgreSQL View (+4 more)

### Community 116 - "Engine Adjust API Docs"
Cohesion: 0.18
Nodes (12): Structured Failure Reasons for UI, adjust_furniture (move / rotate), ADJUST_FURNITURE_TOOL (LLM function-calling schema), Axis-Separated Move Semantics, check_placement_with_clearance, Failure Message Vocabulary, First-Fit Placement Limitation (no scoring), furniture_engine Module (F3/F6) (+4 more)

### Community 117 - "Centimeter Coordinate Contract"
Cohesion: 0.23
Nodes (12): Centimeter Coordinate System (pos_y maps to three.js z), placed_to_dict persistence payload, Separate Image Evidence, Confidence and Confirmed Geometry, Floorplan Recognition (Cody), Explicit Image Profile Route, layout_json (recognition output), Scheme A/B Layout Comparison, Eight-Step Space Planning Workflow (+4 more)

### Community 118 - "Home Landing Page"
Cohesion: 0.20
Nodes (11): initBackgroundFx(), clearLinkedStep(), featureCards, flowCards, flowSection, furnitureMetric, openFlowPanel(), scheduleCloseFlowPanel() (+3 more)

### Community 119 - "Delivery Manifest and Recommendations"
Cohesion: 0.21
Nodes (12): applyDelegatedRoomRecommendations(), applyStyleCardFromQuery(), completeRoomBrief(), buildDeliveryManifest(), escapeForHtml(), findSelectedStyleCardContext(), openRoomInterview(), openStylePicker() (+4 more)

### Community 120 - "Furniture Retrieval Scoring"
Cohesion: 0.33
Nodes (11): catalogFurnitureScore(), colorScore(), hexRgb(), materialScore(), normalizedTokens(), PRODUCT_NAME_RULES, productNameScore(), roleScore() (+3 more)

### Community 121 - "Layout Scene Boundary Contract"
Cohesion: 0.29
Nodes (12): Step 6 Configuration and Preview Workbench, Layout and Scene Boundary Contract, Worker Split: floorplan-vision / proposal-agent / render-export, layout_json, scene_json, expected_updated_at Version Conflict (409), PostgreSQL Project Store Phase 3, No Separate scene_objects Tables Yet (+4 more)

### Community 122 - "Image Manifest Contract Tests"
Cohesion: 0.24
Nodes (8): image_rows(), _load_csv(), fixture, Path, _sha256(), test_glb_manifest_and_upload_result_match_the_official_catalog(), test_json_handoff_manifests_match_the_backend_official_manifests(), test_json_official_catalog_contains_vlm_enrichment_and_matching_assets()

### Community 123 - "Deployment Gates and Status Codes"
Cohesion: 0.20
Nodes (11): Gate 4 — Integration, Gate 5 — Delivery, Gherkin Scenario Form (Given/When/Then), 409/422/503 Failure Status Contract, Completion Gate, Mandatory Browser QA for Edited Flows, 14 Deployment and Operations, Dry-Run and Explicit Authority Safety Rule (+3 more)

### Community 124 - "Cloud Catalog Bridge Tests"
Cohesion: 0.25
Nodes (9): _model_url_for_merged_item(), sample_furniture(), _manifest(), parametrize, test_catalog_status_exposes_provider_and_verified_count(), test_cloudfront_mode_never_falls_back_to_local_model(), test_main_catalog_item_uses_cloudfront_model_url(), test_strict_cloudfront_blocks_legacy_local_model_endpoints() (+1 more)

### Community 125 - "Furniture Embeddings Contract"
Cohesion: 0.33
Nodes (11): PostgreSQL Furniture Embeddings Contract, BAAI/bge-m3 1024-d Cosine Normalized Target, Deferred Fixed Dimension and HNSW Index, roompilot.furniture_embeddings, embedded_text SHA-256 Hash Validation, PostgreSQL Furniture RAG Runtime Contract, CPU Model Load Dominates Latency, SQL Hard Filters vs Ranking-Only Signals (+3 more)

### Community 126 - "Kai and Bella Persistence Duties"
Cohesion: 0.20
Nodes (11): Step 5 Appliance Requirements For AI Rendering Only, SQLite Offline-Only Fallback Ban, Phase 3 workflow_json JSONB Persistence, Official Catalog to PostgreSQL Import Pipeline, roompilot.furniture_catalog_api_current, roompilot.furniture_catalog_current, Kai AI Responsibility Profile, Unmatched Data Quarantine Policy (+3 more)

### Community 127 - "Field Naming and Unit Rules"
Cohesion: 0.29
Nodes (10): Derived Geometry Field Naming Rules, Seven Field-Change Questions, L3 Producer and Consumer Contract Validation, Centimetre Unit Contract (_cm / _m2), backend/engine/ as Sole Geometry Authority, Furniture Vector RAG Boundary, Graph RAG Retrieval-Only Boundary, 不可違反的契約 Inviolable Contracts (+2 more)

### Community 128 - "Reporting and Parallel Work Rules"
Cohesion: 0.22
Nodes (10): Evidence-First Reporting Rules, Implementation Handoff Format, Integrator Duties, Parallel Worker Brief Template, Safe Adoption Principle, source-manifest.csv Provenance Inventory, VibeCoding 01-17 Template Adoption Matrix, L2 Owner-Focused Behavior Evidence (+2 more)

### Community 129 - "Demo Skeleton and GLB Validation"
Cohesion: 0.20
Nodes (10): RoomPilot Skeleton Demo (demo_app), Wire First, Fill In Later (fixed stub interfaces), Real-vs-Stub Pipeline Status UI, GLB glTF Magic Header Validation, roompilot_glb_downloader.py, Scripts Usage Guide, Dry-Run Before Any Database Write, Furniture and Vector PostgreSQL Import Entry Point (+2 more)

### Community 130 - "Room Requirement Tests"
Cohesion: 0.24
Nodes (3): _run_room_requirement_helper(), test_conditional_option_detection_uses_structured_catalog_fields(), test_special_request_is_a_complete_non_forced_answer()

### Community 131 - "OCR Provider"
Cohesion: 0.36
Nodes (6): _bbox(), default_ocr_provider(), _normalise_paddle_result(), PaddleOCRProvider, Any, 可選的 PaddleOCR adapter；核心管線可用測試或人工 observations 取代。

### Community 132 - "Centimeter Canonicalization"
Cohesion: 0.42
Nodes (8): canonicalize_analysis_cm(), _dimensions_cm(), _point_cm(), _polygon_cm(), Any, Centimeter contract adapters for floor-plan recognition payloads., Return one canonical centimeter payload without mutating the source., test_legacy_meter_analysis_is_migrated_to_centimeters_only_once()

### Community 133 - "Bella Frontend Ownership"
Cohesion: 0.28
Nodes (9): Scene-Lab Interaction Prototype (origin/ancai-dev), Bella AI Responsibility Profile, Eight-Step Product Integration, Production Frontend backend/server/static, furniture_admin_audit and Soft-Delete-Only Admin, No Competing Workflow or Persistence Layer, React 3D Prototype Ownership Rules, Known Broken Import in tests/test_official_catalog_sql.py (+1 more)

### Community 134 - "Cody Recognition Pipeline Docs"
Cohesion: 0.25
Nodes (9): Preserve Raw Evidence and Confidence, Floorplan Recognition Pipeline, demo_room hardcoded 5x4 room, dxf_parser.py Self-Check Over 7 DXF Files, Leaf-Node Layer Classification for INSERT Blocks, Wall Extraction via shapely buffer + HATCH union, Optional PaddleOCR Stack, RoomPilot Team Requirements Baseline (+1 more)

### Community 136 - "Official Catalog SQL Tests"
Cohesion: 0.25
Nodes (3): Path, test_sql_database_config_reads_the_repo_env_contract(), test_sql_dry_run_validates_all_official_assets_without_database()

### Community 137 - "Product Step Routing"
Cohesion: 0.36
Nodes (8): Product-Step Routing (8 Steps), Appliance Questionnaire / render_context Boundary, layout_json Recognition Output, scene_json Plan and Edit Output, Current Product Boundary, Legacy Payload and Appliance Exclusion Policy, 現行八步流程 Eight-Step Product Workflow, RoomPilot System Architecture Pipeline

### Community 138 - "LLM Prompt Contract"
Cohesion: 0.32
Nodes (8): L4 Workflow and Real Environment, Requirement and Selection Agent (Yen), OpenRouter Failure and Deterministic Fallback, Material Edit and UV/GLB Rules, Required LLM JSON Contract, 0-100 Component Scoring Model, Prompt Spec Is Not Runtime Truth, LLM Intake-to-Scene-Handoff Workflow

### Community 139 - "Skill Pack Validator"
Cohesion: 0.68
Nodes (7): error(), forbidden_files(), frontmatter(), links(), main(), manifest(), Path

### Community 140 - "Room Icon Templates and Server Rules"
Cohesion: 0.29
Nodes (8): Room Icon Templates (golden furniture symbols), Symbol-Based Room Name Suggestion (read-only), Adapt Owner Modules, Never Copy Algorithms into main.py or JS, Server and Production UI (Bella), RoomPilot Home Landing Page, Shared Top Navigation (/, /styles, /library, /scene), 6 Styles x 18 Interior Color Cards, Taiwan Residential Style Selector Page

### Community 141 - "Reference Plan Matcher"
Cohesion: 0.39
Nodes (7): match_builder_plan_630(), Any, ndarray, Demo golden plan matcher：在 OCR 套件不可用時辨識已驗收的 630 建商圖。, 以局部特徵與 RANSAC 對齊 reference；不相符時不得套用標註。, _transform_bbox(), _transform_point()

### Community 142 - "RAG Status Page Contract"
Cohesion: 0.29
Nodes (8): Static Asset Content-Hash Versioning Policy, Advanced RAG Adapter Status Banner, BGE-M3 + pgvector + Django Reranker Pipeline, RAG Pipeline Status Card, Furniture RAG Testbed Page, retrieval_only_no_geometry_legality Boundary, Furniture RAG Runtime (parse/retrieve/rank only), docs/contracts/POSTGRESQL_FURNITURE_RAG_RUNTIME.md

### Community 143 - "Dimensioned Plan Annotations"
Cohesion: 0.43
Nodes (6): buildDimensionedPlanAnnotations(), clamp(), dimensionLine(), escapeXml(), ROOM_DIMENSION_COLORS, validPoint()

### Community 144 - "Text Encoding Repair"
Cohesion: 0.29
Nodes (7): cjkCount(), repairMojibake(), utf8Decoder, _fd_write(), printChar(), UTF8ArrayToString(), UTF8ToString()

### Community 145 - "Draco Binary Loading"
Cohesion: 0.25
Nodes (8): abort(), assert(), getBinary(), getBinaryPromise(), intArrayFromBase64(), isDataURI(), isFileURI(), tryParseAsDataURI()

### Community 146 - "Engineering Documents API Tests"
Cohesion: 0.54
Nodes (7): _project(), MonkeyPatch, _save_and_lock(), _snapshot(), test_demo_e2e_generates_html_json_and_two_sheet_artifact_xlsx(), test_production_report_has_pending_quotes_and_no_fake_total(), test_unlocked_revision_returns_required_409()

### Community 147 - "Adoption and Merge Prohibitions"
Cohesion: 0.29
Nodes (7): No Automatic Agent Transcript Persistence, Runtime Import Exclusion List, .claude Core and Skills Adoption Policy, No Wholesale Member-Branch Merge, RoomPilot Collaboration Prohibitions, frontend3d React/R3F Prototype, Branch Integration and Commit Exclusion Policy

### Community 148 - "Source Manifest Builder"
Cohesion: 0.57
Nodes (6): classify_claude(), main(), Path, render(), rows(), sha256()

### Community 149 - "Engine and RAG Boundaries"
Cohesion: 0.33
Nodes (7): Centimeter Contract, Engine Boundary: No Catalog Fetch, No External API, No Persistence, Geometry and Placement Engine (Ancai), Normalize External Output to Centimeters, Graph RAG (retrieves relationships, cannot decide geometry), Spatial Data Boundary (Django), Coordinates in cm, Area in m2

### Community 150 - "Library Proposal List"
Cohesion: 0.43
Nodes (7): addToProposal(), bootstrapModeOne(), renderProposal(), restoreFavorites(), restoreProposal(), saveProposal(), syncActiveButtons()

### Community 151 - "Window Type Presets"
Cohesion: 0.43
Nodes (6): structureMeasurement(), applyWindowTypePreset(), normalizedWindowType(), roundCentimeters(), WINDOW_TYPES, windowOpeningMetrics()

### Community 152 - "Draco Runtime Callbacks"
Cohesion: 0.29
Nodes (7): addOnPostRun(), addOnPreRun(), callRuntimeCallbacks(), initRuntime(), postRun(), preRun(), run()

### Community 153 - "RAG Settings Loader"
Cohesion: 0.52
Nodes (6): load_rag_settings(), Path, Server-only settings for the furniture RAG feature., _read_env_file(), _setting(), _truthy()

### Community 154 - "StylePack Rendering Contract"
Cohesion: 0.43
Nodes (7): Automatic Relayout Touches Only Invalid Furniture, StylePack Rendering Contract, Four Lighting Profiles, Palette Switching Never Changes Geometry, Four Fixed Palette Slot Semantics, StylePack Fields, User Lock Flags Override StylePack

### Community 155 - "Engineering Snapshot Tests"
Cohesion: 0.57
Nodes (5): _create_project(), _snapshot(), test_snapshot_cannot_lock_after_source_project_revision_changes(), test_snapshot_rejects_meter_contract_and_path_mismatch(), test_snapshot_save_lock_and_locked_revision_is_immutable()

### Community 156 - "RAG Frontend Tests"
Cohesion: 0.33
Nodes (3): Path, _sha256(), test_rag_page_assets_have_matching_content_hashes()

### Community 157 - "Calibration Tests"
Cohesion: 0.29
Nodes (4): test_calibration_action_explains_what_is_missing(), test_calibration_action_is_ready_after_two_points_and_centimeter_value(), test_pointer_position_maps_from_displayed_preview_to_original_image_pixels(), test_two_image_points_and_known_length_create_scale_calibration()

### Community 158 - "Furniture Retrieval Tests"
Cohesion: 0.29
Nodes (3): test_questionnaire_matching_catalog_glb_wins_over_size_only_candidate(), test_room_role_and_rag_text_influence_questionnaire_catalog_ranking(), test_semantic_product_name_rejects_wrongly_classified_catalog_rows()

### Community 159 - "Code Review Method"
Cohesion: 0.33
Nodes (6): backend/server FastAPI Composition Layer, Bella Orchestrates Without Reimplementing Owner Logic, P0-P3 Finding Form, Refactoring Rules, 11 Code Review Method, Review Only Mode

### Community 160 - "Engineering Page Boundaries"
Cohesion: 0.33
Nodes (6): scene_json (proposal output), Browser Computes No Price, Schedule, Collision or Legal Coordinate, Demo Data Banner (not a formal quote), Engineering Estimation and Document Page, Locked Engineering Revision, ProjectSnapshot

### Community 161 - "Evaluation Evidence Chain"
Cohesion: 0.47
Nodes (6): Ben AI Profile, Dataset Provenance and Model Version Recording, Recognition Evaluation Evidence Chain, Cody AI Profile, Separate Source Image, Ground Truth, Generated Result, Recognition Test Data Rules

### Community 162 - "Uploader Script Rules"
Cohesion: 0.47
Nodes (6): Dry-Run Default and Explicit --execute/--apply, Shared Uploader Path/AWS/Resume/CSV Helpers, roompilot_s3_glb_uploader.py, roompilot_s3_image_uploader.py, GLB and Image Upload CSV Manifests, Producer and Consumer Tests for Contract Changes

### Community 163 - "Engineering Frontend Tests"
Cohesion: 0.40
Nodes (3): _hash(), Path, test_static_module_hashes_are_current_and_scene_links_to_engineering()

### Community 165 - "Scene Delivery Tests"
Cohesion: 0.33
Nodes (5): test_delivery_keeps_furniture_and_sourced_engineering_estimates_separate(), test_delivery_manifest_has_four_views_four_outputs_and_truthful_bom(), test_dxf_white_model_does_not_duplicate_walls_as_floor_overlay_lines(), test_locked_camera_is_preserved_when_style_reload_rebuilds_the_room(), test_scene_page_exposes_real_viewer_and_delivery_controls_without_image_generation()

### Community 169 - "Furniture Picker Clearance"
Cohesion: 0.40
Nodes (5): Catalog Must Carry clearance Field, ClearanceZone (opening space), Furniture Picker Page (Mode 1), Only Confirmed-Loadable GLB Models Are Listed, This-Session Proposal List

### Community 170 - "Window Evaluation Script"
Cohesion: 0.60
Nodes (4): green_boxes(), main(), matched(), 抽出圖中所有綠色框的 bbox 清單 [(x0,y0,x1,y1)]。 同時吃程式畫的 (0,170,0) 與小畫家綠 (34,177,76)，含反鋸齒容差。

### Community 172 - "Cross-Folder Change Protocol"
Cohesion: 0.50
Nodes (4): Cross-Owner Handoff Template, L0 Governance and Trace, 跨資料夾修改 Cross-Folder Change Protocol, Mandatory Reading Order

### Community 173 - "Engineering Router Wiring"
Cohesion: 0.50
Nodes (4): APIRouter, build_engineering_router(), Any, Path

### Community 175 - "Three.js Draco Loader Setup"
Cohesion: 0.67
Nodes (4): Three.js Furniture Model Viewer, three@0.165.0 Import Map (scene), Draco 3D Data Compression, DRACOLoader decoder path setup

### Community 177 - "Draco Memory Management"
Cohesion: 0.50
Nodes (4): emscripten_realloc_buffer(), _emscripten_resize_heap(), getHeapMax(), updateMemoryViews()

## Ambiguous Edges - Review These
- `Appliance Questionnaire / render_context Boundary` → `EquipmentMEPMapping`  [AMBIGUOUS]
  backend/catalog/data/engineering/DATA_DICTIONARY.md · relation: conceptually_related_to
- `Eight-Step Condensed Workflow` → `Remote Interior Render Contract`  [AMBIGUOUS]
  docs/contracts/REMOTE_RENDER_CONTRACT.md · relation: conceptually_related_to

## Knowledge Gaps
- **210 isolated node(s):** `[inputPath, outputPath, ...flags]`, `previewFlag`, `inspectFlag`, `report`, `workbook` (+205 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Appliance Questionnaire / render_context Boundary` and `EquipmentMEPMapping`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Eight-Step Condensed Workflow` and `Remote Interior Render Contract`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `analyze_floorplan_image()` connect `Floorplan Image Analysis` to `Project and Render API Routes`, `Cody Floorplan Adapter`, `Centimeter Canonicalization`, `Room Icon Classification`, `Vision Geometry Detection`, `Reference Plan Matcher`, `Furniture Size Sanitization`, `Confirmation Gate and DXF Payload`, `Room Recognition Evaluation`, `Room Inference From Walls`, `Cody Semantic Room Labeler`, `Vision Line Analysis`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `run_workflow_script()` connect `Scene Guidance Tests` to `Scene V2 Contract Tests`, `Scene Delivery Tests`, `Surface Material Tests`, `PBR Realism Tests`, `Scene Visual Regression Tests`, `Calibration Tests`, `Furniture Retrieval Tests`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `repairMojibakeDeep()` connect `Questionnaire Answer Logic` to `Text Encoding Repair`, `Scene Configuration Sync`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `bindEvents()` (e.g. with `addMissedRoom()` and `applyCalibration()`) actually correct?**
  _`bindEvents()` has 40 INFERRED edges - model-reasoned connections that need verification._
- **What connects `[inputPath, outputPath, ...flags]`, `previewFlag`, `inspectFlag` to the rest of the system?**
  _210 weakly-connected nodes found - possible documentation gaps or missing edges._