import { createSceneViewer } from "./scene_viewer.js?v=sha256-86022d20e78b";
import { confirmedWallGapForDoor } from "./scene_architecture.js?v=sha256-7899eae4c7ba";
import { renderMaterialPairPreviews } from "./scene_material_pair_preview.js?v=sha256-257a140bd340";
import { repairMojibakeDeep } from "./scene_text_encoding.js?v=sha256-9693c47a7d4c";
import { resolveSurfaceOption } from "./scene_surface_materials.js?v=sha256-86c20d96394f";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-65b47a2e253f";
import {
  clipPolygonByLine,
  convexHull,
  pointInPolygonCm,
  polygonArea,
  repairLoadedRoomPolygon,
  roomCenter,
  roomDimensions,
  roomPolygonsDiffer,
} from "./scene_room_geometry.js?v=sha256-53ea68c5106d";
import {
  reviewItemsFromAnalysis,
  reviewReasonLabel,
  unresolvedReviewRooms,
} from "./scene_recognition_review.js?v=sha256-14ba9b03b7c5";
import {
  createWorkflow,
  restoreWorkflow,
  shouldReplayPendingSave,
  WORKFLOW_PANEL_BY_STEP,
  WORKFLOW_STEPS,
} from "./scene_workflow.js?v=sha256-dc5fbb8af9b3";
import {
  buildScaleCalibration,
  calibrationActionState,
} from "./scene_calibration.js?v=sha256-a1eb97980af1";
import {
  createFurniture2DItem,
  FURNITURE_2D_LIBRARY,
  findFurniture2DVariant,
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  planCmToLayerPixel,
  recommendCompanionFurniture,
  recommendedFurnitureForRoom,
  mergeCatalogFurniture,
  replaceFurniture2DItem,
  toSceneFurniture,
} from "./scene_layout2d.js?v=sha256-fc53e4d52dd5";
import {
  reconcileFurniture2dAfterGeneration,
  removeFurniture2dBySceneObject,
  upsertFurniture2dFromSceneObject,
} from "./scene_configuration_sync.js?v=sha256-4bc92d4c915c";
import {
  catalogFurnitureOffer,
  rankCatalogFurniture,
} from "./scene_furniture_retrieval.js?v=sha256-4639ea3888f5";
import {
  CATALOG_FACET_TRADITIONAL_LABELS,
  CATALOG_RETRIEVAL_ROUTES,
  isQuestionnaireFallbackTypeMatch,
  QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS,
  QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS,
  QUESTIONNAIRE_CATALOG_PURPOSE_TYPES,
  QUESTIONNAIRE_CATALOG_PURPOSES,
  QUESTIONNAIRE_CATALOG_SPACES,
  QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS,
  QUESTIONNAIRE_FALLBACK_CATALOG_RULES,
  QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS,
  QUESTIONNAIRE_FURNITURE_SHORT_LABELS,
  QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES,
  QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS,
  REPLACEMENT_TYPE_LABELS,
  ROOM_TYPE_EXCLUDED_FURNITURE_TYPES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  roomUsageVisual,
} from "./scene_questionnaire_catalog.js?v=sha256-5e89e0afa14f";
import {
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-e023af505d8d";
import {
  applyVisualPreferencesToSpecs,
  finishesGate,
  occupantsFromBasicAnswers,
  questionnaireSummary,
  questionsForIndividualRooms,
  questionsForRooms,
  suggestSharedRoomAnswers,
  visualQuestionnaireProgress,
  VISUAL_SPACE_LABELS,
} from "./scene_questionnaire_test2.js?v=sha256-9067e7540e2b";
import {
  reloadViewerPreservingState,
} from "./scene_viewer_reload.js?v=sha256-1106dd5bbffb";
import {
  applyRoomFinishScope,
  buildSpecialRequestAnswer,
  buildRoomRequirementsPayload,
  conditionalOptionId,
  evaluateConditionalOption,
  normalizeRoomRequirements,
} from "./scene_room_requirements.js?v=sha256-b9eff9144dcc";
import {
  applyStylePack,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_FAMILIES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-8b9ab6eaee18";
import {
  beamDragGeometry,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  windowsOverlap,
} from "./scene_structure_utils.js?v=sha256-5242c095ba21";
import { createStructurePreview } from "./scene_structure_preview.js?v=sha256-9d866df171b3";
import {
  findStructureWallCollision,
  resolveStructureWallCollisions,
  validateColumnDimensionsCm,
} from "./scene_structure_geometry.js?v=sha256-041eec531ccf";
import { buildDimensionedPlanAnnotations } from "./scene_dimensioned_plan.js?v=sha256-08fa36a03a66";
import {
  applyWindowTypePreset,
  normalizedWindowType,
  WINDOW_TYPES,
} from "./scene_window_types.js?v=sha256-ebe4923f97c0";
import {
  activateScheme,
  allRoomsHaveSchemeSelections,
  attachedOpenings,
  ensureSchemeB,
  markSchemeLayoutsStale,
  normalizeDesignSchemes,
  persistActiveScheme,
  selectSchemeForRoom,
  selectedSchemeForRoom,
  structuresForScheme,
} from "./scene_design_schemes.js?v=sha256-5cc0b95c4b46";
import { createSceneConfigurationController } from "./scene_configuration_controller.js?v=sha256-7270e214ad40";
import { createSceneProposalController } from "./scene_proposal_controller.js?v=sha256-cd23723e0e1d";
import { createSceneStructureController } from "./scene_structure_controller.js?v=sha256-0a22e5c65260";
import { createSceneQuestionnaireController } from "./scene_questionnaire_controller.js?v=sha256-98be033a14c2";
import { createSceneModelingController } from "./scene_modeling_controller.js?v=sha256-4287354a26dd";
import { createSceneEventBindings } from "./scene_event_bindings.js?v=sha256-a3ed0ba35620";
import { createSceneRestoreController } from "./scene_restore_controller.js?v=sha256-23284a22f25e";
import { createSceneFloorplanController } from "./scene_floorplan_controller.js?v=sha256-fcf5dfb95f00";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character],
);

const STYLE_CARD_STORAGE_KEY = "roompilot:selectedStyleCard";
const PROJECT_SCHEMA_VERSION = 3;

function readStyleCardHandoff() {
  const query = new URLSearchParams(location.search);
  let stored = null;
  try {
    stored = JSON.parse(sessionStorage.getItem(STYLE_CARD_STORAGE_KEY) || "null");
  } catch (error) {
    // sessionStorage can be unavailable or contain stale data; query handoff still works.
  }
  const cardId = query.get("style_card") || stored?.style_card || null;
  if (!cardId) return null;
  return {
    cardId,
    styleId: query.get("style") || stored?.style || stored?.style_id || null,
  };
}

const initialStyleCardHandoff = readStyleCardHandoff();

const ROOM_NAME_OPTIONS = Object.freeze([
  { id: "hallway", label: "走道", type: "hallway", classification: "Hallway" },
  { id: "bathroom", label: "浴室", type: "bathroom", classification: "Bath" },
  { id: "bedroom", label: "臥室", type: "bedroom", classification: "Bedroom" },
  { id: "kitchen", label: "廚房／餐廳", type: "kitchen", classification: "Kitchen" },
  { id: "living_room", label: "客廳", type: "living_room", classification: "LivingRoom" },
  { id: "balcony", label: "陽台", type: "balcony", classification: "Balcony" },
  { id: "entryway", label: "玄關", type: "entryway", classification: "Entry" },
  { id: "storage", label: "書房／儲藏室", type: "storage", classification: "Storage" },
  { id: "stair", label: "樓梯", type: "stair", classification: "Stair" },
  { id: "garage", label: "車庫", type: "garage", classification: "Garage" },
]);

function roomNameOptionFor(room = {}) {
  const selected = String(room.visual_space_type || "");
  const label = String(room.label || room.name || "");
  const type = String(room.type || room.room_type || "");
  return ROOM_NAME_OPTIONS.find((option) => option.id === selected)
    || ROOM_NAME_OPTIONS.find((option) => option.label === label)
    || ROOM_NAME_OPTIONS.find((option) => option.type === type)
    || ROOM_NAME_OPTIONS.find((option) => option.id === "entryway");
}

const state = {
  projectId: new URLSearchParams(location.search).get("project_id"),
  project: null,
  workflow: null,
  pendingFile: null,
  pendingPreviewUrl: null,
  sourceUrl: null,
  sourceExtension: null,
  analysis: null,
  confirmedFloorplan: null,
  confirmedStructureSnapshot: null,
  calibrationPoints: [],
  calibrationDragIndex: null,
  rooms: [],
  selectedRoomId: null,
  selectedWalkRoomId: null,
  activeLayoutRoomId: "all",
  showAllRooms: true,
  spaceReviewMode: "editing",
  spaceMode: "rooms",
  roomGeometryMode: null,
  mergeRoomIds: [],
  splitPoints: [],
  roomNodeMode: null,
  selectedRoomNodeIndices: [],
  dismissedAutoRoomIds: [],
  // 使用者刪除軟裝的意圖記憶:{ roomId: [auto_decor_role, ...] }。
  // 少了它,「沒有軟裝」與「使用者刪光了」在資料上無法區分,重跑會復活。
  dismissedDecorRoles: {},
  lastWhiteModelGenerationError: "",
  requirementsGenerationPending: false,
  stepSixSurfaceKind: "wall",
  stepSixSurfacesReady: false,
  structures: { walls: [], doors: [], windows: [], beams: [], columns: [] },
  designSchemes: normalizeDesignSchemes(),
  activeStructureKind: "door",
  structureTool: null,
  structureLineStart: null,
  structureLinePreviewEnd: null,
  pendingWallDeleteId: null,
  selectedStructure: null,
  windowNormalizationRemoved: 0,
  showFurnitureNumbers: true,
  basicAnswers: {},
  basicConfirmed: false,
  questionnaireStage: "profile",
  roomRequirementModel: normalizeRoomRequirements(),
  roomFinishDrafts: {},
  roomFurnitureRecommendations: {},
  roomFurnitureRecommendationErrors: {},
  roomRagJobs: {},
  selectedQuestionnaireWallId: null,
  visualCatalog: null,
  visualCatalogVersion: null,
  surfaceCatalog: null,
  surfaceCatalogLoadError: null,
  surfaceCatalogProvider: null,
  visualQuestions: [],
  visualQuestionIndex: 0,
  visualAnswers: {},
  skippedVisualSpaceTypes: [],
  questionnaireFinishes: {
    confirmed: false,
    stylePackId: null,
    wallMaterial: null,
    wallColor: null,
    floorMaterial: null,
    floorColor: null,
    ceilingMaterial: null,
    ceilingStyle: null,
    lightStyle: null,
    ceilingColor: "#f4f1eb",
  },
  furniture2d: [],
  selectedFurniture2dId: null,
  sceneData: null,
  autoGeneratingWhiteModel: false,
  selectedSceneIndex: 0,
  styleHistory: [],
  activeStyleId: "scandinavian",
  activeStylePackId: null,
  surfaceState: { wall: {}, floor: {}, furniture: [] },
  materialBoundary: null,
  proposalReview: {
    masterView: null,
    confirmedStyleCardId: null,
    roomViews: {},
    jobs: [],
    renderBriefs: [],
    paletteGenerated: false,
  },
  // 第 7 步代表房三色卡的 base64 生圖:只放記憶體,不進 workflowPayload —— 避免撐爆
  // 2MB workflow 上限(見 project_store.MAX_WORKFLOW_BYTES)。重整後預覽不留,但
  // 後端 palette_render.generated 旗標仍鎖住「只生一次」。
  paletteRenderImages: {},
  selectedRenderRoomId: null,
  selectedProposalRoomId: null,
  selectedProposalRoomCandidateIndex: 0,
  selectedRoomSchemeId: null,
};

function applyStyleCardHandoff(handoff = initialStyleCardHandoff) {
  if (!handoff) return false;
  const pack = STYLE_PACKS.find((candidate) => candidate.id === handoff.cardId);
  if (!pack || (handoff.styleId && handoff.styleId !== pack.styleId)) return false;
  const family = STYLE_FAMILIES.find((candidate) => candidate.id === pack.styleId);
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  state.questionnaireFinishes = {
    ...state.questionnaireFinishes,
    stylePackId: pack.id,
    wallMaterial: state.questionnaireFinishes.wallMaterial || pack.wall.surfaceOption,
    wallColor: state.questionnaireFinishes.wallColor || pack.wall.color,
    floorMaterial: state.questionnaireFinishes.floorMaterial || pack.floor.surfaceOption,
    floorColor: state.questionnaireFinishes.floorColor || pack.floor.color,
  };
  state.basicAnswers = {
    ...state.basicAnswers,
    overallStyle: state.basicAnswers.overallStyle || family?.label || pack.name,
  };
  state.roomRequirementModel.globalProfile = {
    ...(state.roomRequirementModel.globalProfile || {}),
    overallStyle: state.basicAnswers.overallStyle,
  };
  return true;
}
let styleApplyRevision = 0;
const proposalRoomPreviewCache = new Map();
const roomSchemePreviewCache = new Map();
// 第 6 步逐房材質清單顯示上限；未定義會讓
// renderGroupedMaterialOptions 一執行就 ReferenceError，初始化在 renderStyleControls 中斷。
const STEP_SIX_SURFACE_SWATCH_LIMIT = 6;
const STEP_SIX_SURFACE_MATERIAL_LIMIT = 6;
const roomSchemeRuntimeState = {
  previewInFlight: null,
  alternativeInFlight: null,
  previewSchemeId: null,
};
// Proposal/render transient state lives together so the Step 7–8 controller can
// own it without leaking mutable primitive bindings into the entrypoint.
const proposalRuntimeState = {
  sceneVersionLoaded: null,
  sceneLoading: null,
  pendingBriefMode: null,
  pendingBriefAction: "initial",
  latestDesignDelivery: null,
  renderStageView: null,
  aiRenderImageVisible: false,
};
const structureRuntimeState = {
  draggedRoomPointIndex: null,
  structureDrag: null,
  wallResizeDrag: null,
  doorResizeDrag: null,
  beamResizeDrag: null,
  structureCreateDrag: null,
  structureSizeDraft: null,
  lastEditorKey: null,
};
const questionnaireRuntimeState = {
  visualCustomSaveTimer: null,
  ceilingPickerKind: null,
  materialCatalogKind: null,
  materialCatalogSearch: "",
  materialCatalogType: "all",
  materialCatalogColor: "all",
  roomSection: "usage",
  stepSixMaterialCatalogKind: null,
};
const catalogRuntimeState = {
  roomId: null,
  scope: "room",
  space: "",
  purpose: "",
  searchTimer: null,
  selectedFurnitureIds: new Set(),
  selectedFurniture: new Map(),
  thumbnailBatch: 0,
};
const configurationReflowInFlight = new Set();
const questionnaireFurnitureInFlight = new Set();

const panels = new Map(
  $$(".rp-step-panel").map((panel) => [panel.dataset.panel, panel]),
);

const instructions = {
  project: ["步驟 1", "先建立專案，之後每一次確認都會自動保存"],
  upload: ["步驟 2", "選擇 DXF、PNG 或 JPG，並確認圖檔內容"],
  recognition: ["步驟 3", "拖曳尺寸線兩端，只輸入一個實際公分尺寸"],
  calibration: ["步驟 3", "確認尺度後，才會顯示辨識到的房間"],
  space_confirmation: ["步驟 4", "先確認房間，再確認牆、門、窗、樑與柱"],
  requirements: ["步驟 5", "設定全屋風格與逐房需求"],
  layout_2d: ["步驟 6", "確認家具形式、實際尺寸、位置與淨空"],
  white_model_3d: ["步驟 6", "在 3D 主畫面配置家具，並用同步 2D 側欄檢查位置"],
  realistic_3d: ["步驟 6", "即時確認牆面、地板、天花板、燈光與家具材質"],
  proposal_review: ["步驟 7", "檢查完整方案，鎖定色卡與各空間渲染視角"],
  ai_render: ["步驟 8", "依鎖定方案逐空間產生圖片並加入成果包"],
};

const PUBLIC_WORKFLOW_STEPS = Object.freeze([
  "project",
  "upload",
  "recognition",
  "space_confirmation",
  "requirements",
  "layout_2d",
  "proposal_review",
  "ai_render",
]);

function publicWorkflowStep(step) {
  if (step === "calibration") return "recognition";
  if (step === "white_model_3d" || step === "realistic_3d") return "layout_2d";
  return step;
}

const element = {
  status: $("#global-status"),
  stepNumber: $("#current-step-number"),
  instruction: $("#step-instruction"),
  saveStatus: $("#project-save-status"),
  projectForm: $("#project-form"),
  projectName: $("#project-name"),
  projectNotes: $("#project-notes"),
  projectError: $("#project-error"),
  file: $("#floorplan-file"),
  uploadDropZone: $(".rp-drop-zone"),
  uploadPreview: $("#upload-floorplan-preview"),
  uploadPlaceholder: $("#upload-floorplan-placeholder"),
  uploadFileState: $("#upload-file-state"),
  uploadError: $("#upload-error"),
  confirmUpload: $("#confirm-upload"),
  floorplanConfirmation: $("#project-floorplan-confirmation"),
  scaleImage: $("#floorplan-calibration-image"),
  scaleStage: $("#floorplan-calibration-stage"),
  scaleOverlay: $("#floorplan-calibration-overlay"),
  scaleInput: $("#floorplan-scale-cm"),
  calibrationReadout: $("#calibration-readout"),
  scaleError: $("#scale-error"),
  applyCalibration: $("#apply-floorplan-calibration"),
  resetCalibration: $("#reset-floorplan-calibration"),
  calibrationPointTask: $("#calibration-task-points"),
  calibrationMeasureTask: $("#calibration-task-measure"),
  calibrationConfirmTask: $("#calibration-task-confirm"),
  calibrationPointStatus: $("#calibration-task-points-status"),
  calibrationMeasureStatus: $("#calibration-task-measure-status"),
  calibrationConfirmStatus: $("#calibration-task-confirm-status"),
  recognitionSummary: $("#recognition-summary"),
  spaceImage: $("#space-plan-image"),
  spaceStage: $("#space-plan-stage"),
  spaceOverlay: $("#space-plan-overlay"),
  spaceEditorWorkspace: $("#space-editor-workspace"),
  spaceDimensionReview: $("#space-dimension-review"),
  dimensionPlanStage: $("#dimensioned-plan-stage"),
  dimensionPlanImage: $("#dimensioned-plan-image"),
  dimensionPlanOverlay: $("#dimensioned-plan-overlay"),
  dimensionPlanLegend: $("#dimensioned-plan-legend"),
  dimensionTotalArea: $("#dimension-total-area"),
  dimensionRoomCount: $("#dimension-room-count"),
  dimensionCalibrationState: $("#dimension-calibration-state"),
  dimensionReviewError: $("#dimension-review-error"),
  roomList: $("#room-list"),
  roomEditor: $("#room-editor"),
  roomName: $("#room-name"),
  roomArea: $("#room-area"),
  roomConfirmationProgress: $("#room-confirmation-progress"),
  roomGeometryGuidance: $("#room-geometry-guidance"),
  roomNodeGuidance: $("#room-node-guidance"),
  structureCounts: $("#structure-counts"),
  doorReviewList: $("#structure-review-list"),
  structureEditor: $("#selected-structure-editor"),
  openingWidthSlider: $("#opening-width-slider"),
  openingWidthValue: $("#opening-width-value"),
  confirmSpace: $("#confirm-space"),
  spaceError: $("#space-error"),
  wholeHouseFields: $("#whole-house-fields"),
  wholeHouseStyleTabs: $("#whole-house-style-tabs"),
  wholeHouseStyleGrid: $("#whole-house-style-grid"),
  wholeHouseStyleSelection: $("#whole-house-style-selection"),
  requirementsProgress: $("#requirements-progress"),
  requirementsError: $("#requirements-error"),
  requirementsGenerationHelp: $("#requirements-generation-help"),
  requirementsGenerationHelpDetail: $("#requirements-generation-help-detail"),
  randomizeRequirements: $("#randomize-requirements"),
  confirmRequirements: $("#confirm-requirements"),
  placementBusy: $("#placement-busy"),
  placementBusyText: $("#placement-busy-text"),
  questionnaireStageNav: $("#questionnaire-stage-nav"),
  visualSpaceNav: $("#visual-space-nav"),
  visualQuestionProgress: $("#visual-question-progress"),
  roomPreferenceSuggestion: $("#room-preference-suggestion"),
  visualQuestionCard: $("#visual-question-card"),
  visualCustomAnswer: $("#visual-custom-answer"),
  questionnaireStyleTabs: $("#questionnaire-style-tabs"),
  questionnaireStyleGrid: $("#questionnaire-style-grid"),
  questionnaireMaterialGrid: $("#questionnaire-finishes .rp-questionnaire-material-grid"),
  questionnaireMaterialPairs: $("#questionnaire-material-pairs"),
  questionnaireMaterialCatalogDialog: $("#questionnaire-material-catalog-dialog"),
  questionnaireMaterialCatalogSource: $("#questionnaire-material-catalog-source"),
  questionnaireMaterialCatalogTitle: $("#questionnaire-material-catalog-title"),
  questionnaireMaterialCatalogHelp: $("#questionnaire-material-catalog-help"),
  questionnaireMaterialCatalogSearch: $("#questionnaire-material-catalog-search"),
  questionnaireMaterialTypeFilters: $("#questionnaire-material-type-filters"),
  questionnaireMaterialColorFilters: $("#questionnaire-material-color-filters"),
  questionnaireMaterialCatalogResultCount: $("#questionnaire-material-catalog-result-count"),
  questionnaireMaterialCatalogOptions: $("#questionnaire-material-catalog-options"),
  questionnaireWallOptions: $("#questionnaire-wall-options"),
  questionnaireFloorOptions: $("#questionnaire-floor-options"),
  questionnaireWallColor: $("#questionnaire-wall-color"),
  questionnaireFloorColor: $("#questionnaire-floor-color"),
  questionnaireWallPreference: $("#questionnaire-wall-preference"),
  questionnaireFloorPreference: $("#questionnaire-floor-preference"),
  questionnaireCeilingMaterial: $("#questionnaire-ceiling-material"),
  questionnaireCeilingStyle: $("#questionnaire-ceiling-style"),
  questionnaireLightStyle: $("#questionnaire-light-style"),
  questionnaireCeilingQuickChoices: $("#questionnaire-ceiling-quick-choices"),
  questionnaireCeilingPickerDialog: $("#questionnaire-ceiling-picker-dialog"),
  questionnaireCeilingPickerTitle: $("#questionnaire-ceiling-picker-title"),
  questionnaireCeilingPickerHelp: $("#questionnaire-ceiling-picker-help"),
  questionnaireCeilingPickerOptions: $("#questionnaire-ceiling-picker-options"),
  closeQuestionnaireCeilingPicker: $("#close-questionnaire-ceiling-picker"),
  questionnaireCeilingColor: $("#questionnaire-ceiling-color"),
  questionnaireAirConditioning: $("#questionnaire-air-conditioning"),
  questionnaireRoomUsageOptions: $("#questionnaire-room-usage-options"),
  questionnaireGenerativeEquipment: $("#questionnaire-generative-equipment"),
  questionnaireGenerativePrimaryUse: $("#questionnaire-generative-primary-use"),
  questionnaireGenerativeDirections: $("#questionnaire-generative-directions"),
  questionnaireGenerativeExclusions: $("#questionnaire-generative-exclusions"),
  questionnaireGenerationNotes: $("#questionnaire-generation-notes"),
  questionnaireGenerationWarning: $("#questionnaire-generation-warning"),
  questionnaireFurnitureOptions: $("#questionnaire-furniture-options"),
  questionnaireFurnitureStatus: $("#questionnaire-furniture-status"),
  questionnaireFurniturePreference: $("#questionnaire-furniture-preference"),
  questionnaireFurniturePreferenceTags: $("#questionnaire-furniture-preference-tags"),
  refreshQuestionnaireFurniture: $("#refresh-questionnaire-furniture"),
  questionnaireFinishScope: $("#questionnaire-finish-scope"),
  questionnaireFinishRoomTargets: $("#questionnaire-finish-room-targets"),
  circulationStyleNotice: $("#circulation-style-notice"),
  enableCirculationStyleOverride: $("#enable-circulation-style-override"),
  questionnairePlanImage: $("#questionnaire-plan-image"),
  questionnairePlanOverlay: $("#questionnaire-plan-overlay"),
  questionnairePlanStage: $(".rp-questionnaire-plan-stage"),
  selectedWallSurface: $("#selected-wall-surface"),
  roomFeasibilityNotices: $("#room-feasibility-notices"),
  questionnaireSummary: $("#questionnaire-summary-content"),
  layoutImage: $("#layout-plan-image"),
  layoutStage: $("#layout-plan-stage"),
  layoutRoomOverlay: $("#layout-room-overlay"),
  layoutLayer: $("#layout-furniture-layer"),
  layoutRoomFilter: $("#layout-room-filter"),
  layoutRoomMaterials: $("#layout-room-materials"),
  layoutFurnitureList: $("#layout-furniture-list"),
  layoutSchemeStatus: $("#layout-scheme-status"),
  furnitureLibrary: $("#furniture-icon-library"),
  furnitureSearch: $("#furniture-icon-search"),
  selectedFurnitureEditor: $("#selected-2d-furniture"),
  selectedFurnitureName: $("#selected-2d-name"),
  selectedFurnitureReason: $("#selected-2d-reason"),
  selectedFurnitureWidth: $("#selected-2d-width"),
  selectedFurnitureDepth: $("#selected-2d-depth"),
  layoutError: $("#layout-error"),
  replacementDrawer: $("#furniture-replacement-drawer"),
  replacementFilterSummary: $("#replacement-filter-summary"),
  replacementSearch: $("#replacement-furniture-search"),
  replacementQuery: $("#replacement-furniture-query"),
  replacementResults: $("#replacement-furniture-results"),
  replacementError: $("#replacement-furniture-error"),
  replacement3dStatus: $("#replacement-3d-status"),
  catalogDrawer: $("#furniture-catalog-drawer"),
  whiteWalkRoom: $("#white-walk-room"),
  whiteStatus: $("#white-model-status"),
  whiteError: $("#white-model-error"),
  roomSchemeGate: $("#room-scheme-gate"),
  openRoomSchemeSelection: $("#open-room-scheme-selection"),
  roomSchemeGateStatus: $("#room-scheme-gate-status"),
  configurationPlanPanel: $("#configuration-plan-panel"),
  configurationPlanToggle: $("#configuration-plan-toggle"),
  configurationPlanStage: $(".rp-configuration-plan-stage"),
  configurationPlanImage: $("#configuration-plan-image"),
  configurationPlanLayer: $("#configuration-plan-furniture-layer"),
  configurationPlanFurnitureList: $("#configuration-plan-furniture-list"),
  configurationPendingCount: $("#configuration-pending-count"),
  configurationPendingList: $("#configuration-pending-list"),
  roomSchemeDialog: $("#room-scheme-selection-dialog"),
  roomSchemeList: $("#room-scheme-list"),
  roomSchemeStatus: $("#room-scheme-status"),
  roomSchemeChoiceGrid: $("#room-scheme-choice-grid"),
  roomSchemeWarning: $("#room-scheme-warning"),
  roomSchemeComplete: $("#room-scheme-complete"),
  renderBriefDialog: $("#render-brief-dialog"),
  renderBriefSummary: $("#render-brief-summary"),
  renderBriefNotes: $("#render-brief-notes"),
  renderBriefWarning: $("#render-brief-warning"),
  designDeliveryDialog: $("#design-delivery-dialog"),
  designDeliveryContent: $("#design-delivery-content"),
  roomSchemeProgress: $("#room-scheme-progress"),
  objectList: $("#scene-object-list"),
  realisticObjectList: $("#realistic-scene-object-list"),
  glbResults: $("#glb-search-results"),
  questionnaireCatalogControls: $("#questionnaire-catalog-controls"),
  questionnaireCatalogType: $("#questionnaire-catalog-type"),
  questionnaireCatalogSpaceGroups: $("#questionnaire-catalog-space-groups"),
  questionnaireCatalogPurposeGroups: $("#questionnaire-catalog-purpose-groups"),
  questionnaireCatalogColor: $("#questionnaire-catalog-color"),
  questionnaireCatalogMaterial: $("#questionnaire-catalog-material"),
  questionnaireCatalogBatch: $("#questionnaire-catalog-batch"),
  questionnaireCatalogSelectedCount: $("#questionnaire-catalog-selected-count"),
  addSelectedQuestionnaireFurniture: $("#add-selected-questionnaire-furniture"),
  standardCatalogSearch: $("#glb-furniture-search"),
  boundarySecondaryFloor: $("#boundary-secondary-floor"),
  confirmRoomSurfaces: $("#confirm-room-surfaces"),
  lightingFixtureSelect: $("#lighting-fixture-select"),
  lightingRoomQuestionnaire: $("#lighting-room-questionnaire"),
  lightingRoomSelector: $("#lighting-room-selector"),
  randomizeRequirementsSummary: $("#randomize-requirements-summary"),
  roomScheme3dPreviewDialog: $("#room-scheme-3d-preview-dialog"),
  roomScheme3dPreviewStatus: $("#room-scheme-3d-status"),
  roomScheme3dPreviewTitle: $("#room-scheme-3d-preview-title"),
  roomSchemeStructureFix: $("#room-scheme-structure-fix"),
  surfacePreviewStatus: $("#surface-preview-status"),
  surfaceRoomLockState: $("#surface-room-lock-state"),
  surfaceRoomProgress: $("#surface-room-progress"),
  surfaceRoomQuestionnaire: $("#surface-room-questionnaire"),
  surfaceRoomTitle: $("#surface-room-title"),
  surfaceSelectedDescription: $("#surface-selected-description"),
  unlockRoomSurfaces: $("#unlock-room-surfaces"),
  unlockRoomSurfacesSticky: $("#unlock-room-surfaces-sticky"),
  realisticStatus: $("#realistic-status"),
  styleTabs: $("#style-pack-tabs"),
  styleGrid: $("#style-pack-grid"),
  wallMaterialGrouped: $("#wall-material-grouped"),
  floorMaterialGrouped: $("#floor-material-grouped"),
  ceilingStyle: $("#ceiling-style"),
  lightStyle: $("#light-style"),
  ceilingConflicts: $("#ceiling-conflicts"),
  proposalReviewStatus: $("#proposal-review-status"),
  proposalReviewSummary: $("#proposal-review-summary"),
  proposalReviewImageStage: $("#proposal-review-image-stage"),
  proposalReviewImage: $("#proposal-review-image"),
  proposalReviewImageCaption: $("#proposal-review-image-caption"),
  proposalPaletteGrid: $("#proposal-palette-grid"),
  proposalPaletteStatus: $("#proposal-palette-status"),
  proposalContentConfirmed: $("#proposal-content-confirmed"),
  masterViewStatus: $("#master-view-status"),
  lockedSchemeLabel: $("#locked-scheme-label"),
  aiRenderStatus: $("#ai-render-status"),
  aiRenderViewTitle: $("#ai-render-view-title"),
  aiRenderProviderState: $("#ai-render-provider-state"),
  paletteRenderOptions: $("#palette-render-options"),
  paletteRenderResults: $("#palette-render-results"),
  confirmRenderPalette: $("#confirm-render-palette"),
  roomRenderSection: $("#room-render-section"),
  renderRoomList: $("#render-room-list"),
  remoteRenderJobs: $("#remote-render-jobs"),
  aiRenderImageStage: $("#ai-render-image-stage"),
  aiRenderImage: $("#ai-render-image"),
  aiRenderImageCaption: $("#ai-render-image-caption"),
  aiRenderGallery: $("#ai-render-gallery"),
  aiRenderStageClose: $("#ai-render-stage-close"),
  aiRenderImageToggle: $("#ai-render-image-toggle"),
  deliveryProposalStatus: $("#delivery-proposal-status"),
  deliveryProposalGenerate: $("#delivery-proposal-generate"),
  deliveryProposalDownload: $("#delivery-proposal-download"),
  deliveryProposalXlsx: $("#delivery-proposal-xlsx"),
};

const whiteViewer = createSceneViewer($("#white-model-viewer"), element.whiteStatus, {
  onSceneChange: (item) => {
    syncMovedSceneFurnitureTo2d(item);
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    renderConfigurationPlan();
    scheduleSave("white_model_3d");
  },
  onObjectSelect: (item) => syncSceneSelectionTo2dFurniture(item),
});
$("#white-model-viewer")?.addEventListener("roompilot-door-diagnostics", (event) => {
  const diagnostics = event.detail || {};
  const matched = (diagnostics.comparisons || []).filter((item) => item.status === "matched").length;
  const expected = Number(diagnostics.expected) || 0;
  const mismatch = expected - matched;
  const merged = (diagnostics.mergedDoorIds || []).length;
  element.whiteStatus.dataset.doorAlignment = mismatch ? "mismatch" : "matched";
  element.whiteStatus.textContent = mismatch
    ? `門位對照：${matched}/${expected} 扇與第 4 步不一致，未確認前不會額外切出牆洞。`
    : merged
      ? `門位對照完成：${matched}/${expected} 扇門洞與第 4 步位置一致；已合併 ${merged} 筆重複辨識。`
      : `門位對照完成：${matched}/${expected} 扇門洞與第 4 步位置一致。`;
});
const realisticViewer = createSceneViewer($("#realistic-viewer"), element.realisticStatus, {
  onSceneChange: () => markRealisticSceneEdited(),
  onObjectSelect: (item) => syncSceneSelectionTo2dFurniture(item),
});
const proposalViewer = createSceneViewer(
  $("#proposal-review-viewer"),
  element.proposalReviewStatus,
);
const aiRenderViewer = createSceneViewer($("#ai-render-viewer"), element.aiRenderStatus);
const replacementViewer = createSceneViewer(
  $("#replacement-3d-preview"),
  element.replacement3dStatus,
);
const glbThumbnailViewer = createSceneViewer(
  $("#glb-thumbnail-viewer"),
  $("#glb-thumbnail-status"),
);
// 逐房 A/B 點擊放大的可旋轉 3D 預覽 viewer。
// 未定義時 openRoomScheme3dPreview 在 4156 傳入即 ReferenceError。
const roomSchemePreviewViewer = createSceneViewer(
  $("#room-scheme-3d-preview"),
  element.roomScheme3dPreviewStatus,
);
const structurePreview = createStructurePreview($("#structure-3d-preview"));
const styleFurnitureCache = new Map();
const glbThumbnailCache = new Map();
const verifiedCatalogModelUrls = new Set();
const unavailableCatalogModelUrls = new Set();
const glbThumbnailQueue = { sequence: Promise.resolve() };

function setStatus(message, kind = "normal") {
  element.status.textContent = message;
  element.status.dataset.kind = kind;
}

function errorMessage(error) {
  const detail = error?.detail;
  const message = typeof detail === "string"
    ? detail
    : detail?.message || error?.message || "操作失敗，請稍後再試。";
  const messages = {
    targeted_room_review_required: "尺寸已確認；請在下一步逐一檢查房間範圍與名稱。",
    geometry_confirmation_required: "請在下一步確認牆、門、窗的位置後再繼續。",
    scale_confirmation_required: "請重新定位兩個端點並輸入實際公分尺寸。",
  };
  return messages[message] || message;
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? repairMojibakeDeep(await response.json())
    : await response.text();
  if (!response.ok) {
    const error = new Error(errorMessage(payload));
    Object.assign(error, payload);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function sceneDataFromGenerateResponse(payload) {
  if (!payload?.scene_json) throw new Error("scene_json_missing");
  return payload.scene_json;
}

const RETIRED_APPLIANCE_TYPES = new Set([
  "refrigerator",
  "washer",
  "washing-machine",
  "dishwasher",
  "dryer",
  "oven",
  "microwave",
  "range-hood",
  "air-conditioner",
  "ceiling-cassette",
  "appliance",
]);
const RETIRED_APPLIANCE_MODEL_MARKERS = [
  "/models/ikea/appliance/",
  "/fi-fridges-freezers-",
  "/fi-washing-machines-",
];

function isRetiredApplianceItem(item = {}) {
  const type = String(item.type || item.normalized_type || "").toLowerCase();
  if (RETIRED_APPLIANCE_TYPES.has(type)) return true;
  const modelUrl = String(item.model_url || item.glb_url || "").toLowerCase();
  if (!modelUrl) return false;
  return RETIRED_APPLIANCE_MODEL_MARKERS.some((marker) => modelUrl.includes(marker));
}

function removeRetiredAppliancesFromSceneData(sceneData) {
  if (!sceneData?.scene_objects?.length) return 0;
  const before = sceneData.scene_objects.length;
  sceneData.scene_objects = sceneData.scene_objects.filter(
    (item) => !isRetiredApplianceItem(item),
  );
  return before - sceneData.scene_objects.length;
}

function removeRetiredAppliancesFromFurniture(furniture = []) {
  return furniture.filter((item) => !isRetiredApplianceItem(item));
}

function isAutomaticSoftDecorItem(item = {}) {
  return Boolean(item?.auto_decor_role);
}

function removeAutomaticSoftDecorFromSceneData(sceneData) {
  if (!sceneData?.scene_objects?.length) return 0;
  const before = sceneData.scene_objects.length;
  sceneData.scene_objects = sceneData.scene_objects.filter(
    (item) => !isAutomaticSoftDecorItem(item),
  );
  return before - sceneData.scene_objects.length;
}

function removeAutomaticSoftDecorFromFurniture(furniture = []) {
  return furniture.filter((item) => !isAutomaticSoftDecorItem(item));
}

function pruneAutomaticSoftDecor() {
  let removed = 0;
  const beforeFurniture = state.furniture2d.length;
  state.furniture2d = removeAutomaticSoftDecorFromFurniture(state.furniture2d);
  removed += beforeFurniture - state.furniture2d.length;
  removed += removeAutomaticSoftDecorFromSceneData(state.sceneData);

  Object.values(state.designSchemes?.schemes || {}).forEach((scheme) => {
    const beforeSchemeFurniture = (scheme.furniture || []).length;
    scheme.furniture = removeAutomaticSoftDecorFromFurniture(scheme.furniture || []);
    removed += beforeSchemeFurniture - scheme.furniture.length;
    removed += removeAutomaticSoftDecorFromSceneData(scheme.sceneData);
  });

  if (
    state.selectedFurniture2dId
    && !state.furniture2d.some((item) => String(item.id) === String(state.selectedFurniture2dId))
  ) {
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  }
  if (state.sceneData?.scene_objects?.length) {
    state.selectedSceneIndex = Math.min(
      Math.max(Number(state.selectedSceneIndex) || 0, 0),
      state.sceneData.scene_objects.length - 1,
    );
  } else {
    state.selectedSceneIndex = -1;
  }
  return removed;
}

function applianceRequirementsForRendering(furniture = []) {
  return furniture
    .filter((item) => isRetiredApplianceItem(item))
    .map((item) => ({
      furniture_id: item.furniture_id || item.catalogFurnitureId || item.id || null,
      normalized_type: item.type || item.normalized_type || "appliance",
      name_zh: item.name_zh || item.name_zh_raw || item.label || "",
      room_id: item.roomId || item.room_id || null,
      room_type: item.roomType || item.room_type || null,
      selected_by_user: Boolean(item.user_selected || item.userSpecified),
    }));
}

function pruneRetiredAppliances({ notify = false } = {}) {
  let removed = 0;
  const beforeFurniture = state.furniture2d.length;
  state.furniture2d = removeRetiredAppliancesFromFurniture(state.furniture2d);
  removed += beforeFurniture - state.furniture2d.length;
  removed += removeRetiredAppliancesFromSceneData(state.sceneData);

  Object.values(state.designSchemes?.schemes || {}).forEach((scheme) => {
    const beforeSchemeFurniture = (scheme.furniture || []).length;
    scheme.furniture = removeRetiredAppliancesFromFurniture(scheme.furniture || []);
    removed += beforeSchemeFurniture - scheme.furniture.length;
    removed += removeRetiredAppliancesFromSceneData(scheme.sceneData);
  });

  if (
    state.selectedFurniture2dId
    && !state.furniture2d.some((item) => String(item.id) === String(state.selectedFurniture2dId))
  ) {
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  }
  if (state.sceneData?.scene_objects?.length) {
    state.selectedSceneIndex = Math.min(
      Math.max(Number(state.selectedSceneIndex) || 0, 0),
      state.sceneData.scene_objects.length - 1,
    );
  } else {
    state.selectedSceneIndex = -1;
  }
  if (removed > 0 && notify) {
    setStatus(`已移除 ${removed} 件舊版家電項目；冰箱與洗衣機已改由一般家具與櫃體流程處理。`);
  }
  return removed;
}

function normalizeSceneDoorSegments(sceneData) {
  if (!sceneData?.floorplan?.door_segments?.length) return 0;
  const normalized = dedupeDoorCandidates(sceneData.floorplan.door_segments);
  sceneData.floorplan.door_segments = normalized.doors;
  return normalized.removed;
}

function questionnaireRagQuery(room) {
  const requirement = state.roomRequirementModel?.roomRequirements?.[room.id] || {};
  const furniture = requirement.furniture || {};
  const generativeEquipment = requirement.generativeEquipment || {};
  const usage = (requirement.usage || []).join("、");
  const selected = (furniture.selected || [])
    .map((item) => item.name_zh || item.normalized_type)
    .filter(Boolean)
    .join("、");
  const preferenceTags = Array.isArray(furniture.preferenceTags)
    ? furniture.preferenceTags.filter(Boolean).join("、")
    : "";
  let preference = [String(furniture.preferenceText || "").trim(), preferenceTags]
    .filter(Boolean)
    .join("、");
  const paletteId = requirement.surfaces?.paletteId || wholeHouseFinishDraft().stylePackId;
  const styleId = STYLE_PACKS.find((pack) => pack.id === paletteId)?.styleId || "";
  preference = `${preference} style:${styleId}`.trim();
  const equipmentDirection = [
    generativeEquipment.primaryUse,
    ...(generativeEquipment.equipmentDirection || []),
  ].filter(Boolean).join("、");
  const excludedEquipment = (generativeEquipment.mustNotHave || []).join("、");
  const generationNotes = String(generativeEquipment.generationNotes || "").trim();
  const wallPreference = String(requirement.surfaces?.wallPreference || "").trim();
  const floorPreference = String(requirement.surfaces?.floorPreference || "").trim();
  return [
    `${room.label}，${room.type || room.room_type || "default"} 空間`,
    usage && `用途：${usage}`,
    selected && `已選家具：${selected}`,
    preference && `家具偏好：${preference}`,
    equipmentDirection && `生圖設備方向：${equipmentDirection}`,
    excludedEquipment && `不需要設備：${excludedEquipment}`,
    wallPreference && `牆面生圖偏好：${wallPreference}`,
    floorPreference && `地板生圖偏好：${floorPreference}`,
    generationNotes && `生圖補充：${generationNotes}`,
    generativeEquipment.required && "固定限制：不得擴建、移動牆門窗、樑或柱，設備必須符合既有房間尺寸。",
  ].filter(Boolean).join("；");
}

async function startQuestionnaireRag(room) {
  if (!room) return;
  const selected = roomFurnitureRequirement(room.id)?.selected || [];
  if (String(room.type || room.room_type || "") === "stair" && !selected.length) {
    state.roomRagJobs[room.id] = {
      status: "no_furniture_rag_required",
      query: "",
      reason: "stair_has_no_movable_furniture",
    };
    scheduleSave("requirements");
    return;
  }
  const query = questionnaireRagQuery(room);
  if (!query) return;
  try {
    const job = await api("/api/rag/search/jobs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, top_k: 6, fast: true }),
    });
    state.roomRagJobs[room.id] = { jobId: job.job_id, status: job.status, query };
    setStatus(`${room.label} 的家具偏好已送交 RAG 排序，您可繼續填下一個空間。`);
    const poll = async () => {
      const snapshot = await api(`/api/rag/search/jobs/${job.job_id}`);
      state.roomRagJobs[room.id] = { ...state.roomRagJobs[room.id], ...snapshot };
      if (snapshot.status === "completed") {
        const ids = new Set((snapshot.result?.blocks || []).flatMap((block) =>
          (block.hits || []).map((hit) => String(hit.furniture?.item_id || "")),
        ));
        const offers = state.roomFurnitureRecommendations[room.id] || [];
        state.roomFurnitureRecommendations[room.id] = [...offers].sort((left, right) =>
          Number(ids.has(String(right.furniture_id))) - Number(ids.has(String(left.furniture_id))),
        );
        if (String(activeQuestionnaireRoom()?.id) === String(room.id)) {
          renderQuestionnaireFurnitureRecommendations(room);
        }
        scheduleSave("requirements");
        return;
      }
      if (snapshot.status === "failed") {
        state.roomRagJobs[room.id] = {
          ...state.roomRagJobs[room.id],
          status: "unavailable",
          error: snapshot.error?.message || "RAG 排序暫時無法完成",
        };
        setStatus(`${room.label} 目前保留原本的推薦順序；RAG 排序暫時無法完成，但不影響繼續填寫。`);
        scheduleSave("requirements");
        return;
      }
      if (snapshot.status === "queued" || snapshot.status === "running") {
        window.setTimeout(() => { void poll(); }, 900);
      }
    };
    window.setTimeout(() => { void poll(); }, 500);
  } catch (error) {
    // RAG is an enhancement to ranking; questionnaire completion never blocks on it.
    state.roomRagJobs[room.id] = { status: "unavailable", error: errorMessage(error), query };
    setStatus(`${room.label} 目前使用基本推薦；RAG 服務尚未就緒，不影響繼續填寫。`);
    scheduleSave("requirements");
  }
}

async function settleQuestionnaireRagForLayout() {
  const confirmedRooms = state.rooms.filter(
    (room) => state.roomRequirementModel.roomRequirements[room.id]?.confirmed,
  );
  if (!confirmedRooms.length) return true;
  const jobs = confirmedRooms.map((room) => startQuestionnaireRag(room));
  let timeoutId;
  const completed = await Promise.race([
    Promise.all(jobs).then(() => true),
    new Promise((resolve) => {
      timeoutId = window.setTimeout(() => resolve(false), 12000);
    }),
  ]);
  window.clearTimeout(timeoutId);
  if (!completed) {
    setStatus("RAG 尚在整理部分家具；本次先保留可用的推薦，完成後會同步更新。", "error");
  }
  return completed;
}

function restoreDoorSwingEndpointsFromConfirmedStructures(sceneData) {
  const floorplan = sceneData?.floorplan;
  const sceneDoors = floorplan?.door_segments || [];
  const confirmedDoors = state.structures?.doors || [];
  if (!sceneDoors.length || !confirmedDoors.length) return 0;

  const halfWidth = Number(floorplan.width_cm) / 2;
  const halfDepth = Number(floorplan.depth_cm) / 2;
  if (!Number.isFinite(halfWidth) || !Number.isFinite(halfDepth)) return 0;
  const sourceById = new Map(
    confirmedDoors
      .filter((door) => String(door?.id || "").trim())
      .map((door) => [String(door.id), door]),
  );
  let repaired = 0;

  sceneDoors.forEach((door, index) => {
    const doorId = String(door?.id || "").trim();
    const source = (doorId && sourceById.get(doorId)) || confirmedDoors[index];
    if (!source?.swing_end) return;
    if (!doorId && source.id) door.id = source.id;
    const swingEnd = {
      x: Number(source.swing_end.x) - halfWidth,
      z: Number(source.swing_end.y) - halfDepth,
    };
    if (!Number.isFinite(swingEnd.x) || !Number.isFinite(swingEnd.z)) return;
    if (
      Math.abs(Number(door.swing_end?.x) - swingEnd.x) > 0.01
      || Math.abs(Number(door.swing_end?.z) - swingEnd.z) > 0.01
    ) {
      door.swing_end = swingEnd;
      repaired += 1;
    }
  });
  return repaired;
}

function furnitureIdentifiers(item, fallbackId = null) {
  return new Set([
    fallbackId,
    item?.id,
    item?.furniture_id,
    item?.catalog_furniture_id,
    item?.catalogFurnitureId,
    item?.layout_furniture_id,
    item?.source_furniture_id,
  ].filter(Boolean).map(String));
}

function sceneObjectIndexMapByFurnitureId() {
  const sceneObjects = state.sceneData?.scene_objects || [];
  const layoutItems = state.furniture2d || [];
  const mapped = new Map();
  const usedSceneIndices = new Set();

  layoutItems.forEach((layoutItem) => {
    const id = String(layoutItem?.id || "");
    if (!id) return;
    const exactIndex = sceneObjects.findIndex((sceneObject, index) => (
      !usedSceneIndices.has(index)
      && String(sceneObject.furniture_id || "") === id
    ));
    if (exactIndex < 0) return;
    mapped.set(id, exactIndex);
    usedSceneIndices.add(exactIndex);
  });

  layoutItems.forEach((layoutItem) => {
    const id = String(layoutItem?.id || "");
    if (!id || mapped.has(id)) return;
    const layoutIdentifiers = furnitureIdentifiers(layoutItem, id);
    const fallbackIndex = sceneObjects.findIndex((sceneObject, index) => {
      if (usedSceneIndices.has(index)) return false;
      return [...furnitureIdentifiers(sceneObject)].some(
        (candidate) => layoutIdentifiers.has(candidate),
      );
    });
    if (fallbackIndex < 0) return;
    mapped.set(id, fallbackIndex);
    usedSceneIndices.add(fallbackIndex);
  });
  return mapped;
}

function sceneObjectIndexByFurnitureId(furnitureId) {
  if (!furnitureId || !state.sceneData?.scene_objects?.length) return -1;
  const id = String(furnitureId);
  const mappedIndex = sceneObjectIndexMapByFurnitureId().get(id);
  if (mappedIndex != null) return mappedIndex;
  return state.sceneData.scene_objects.findIndex(
    (item) => String(item.furniture_id || "") === id,
  );
}

function setSceneSidebarTab(tab = "plan") {
  const sidebar = $(".rp-3d-sidebar");
  if (!sidebar) return;
  const nextTab = ["plan", "issues", "surfaces"].includes(tab) ? tab : "plan";
  sidebar.dataset.sceneSidebarMode = nextTab;
  $$('[data-scene-sidebar-tab]').forEach((button) => {
    const selected = button.dataset.sceneSidebarTab === nextTab;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  const surfaceEntry = $("#white-model-surface-entry");
  if (surfaceEntry) surfaceEntry.hidden = nextTab !== "surfaces";
  if (nextTab === "plan") requestAnimationFrame(renderConfigurationPlan);
}

function selectedLayoutFurniture() {
  return state.furniture2d.find(
    (item) => String(item.id) === String(state.selectedFurniture2dId),
  ) || null;
}

function renderSelectedFurnitureWorkspace() {
  const panel = $("#furniture-property-locks");
  if (!panel) return;
  const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  const layoutItem = selectedLayoutFurniture();
  const current = layoutItem || selected;
  panel.querySelector("[data-selected-furniture-context]")?.remove();
  if (!current) return;

  const room = state.rooms.find((item) => String(item.id) === String(current.roomId || current.placement_room_id));
  const name = current.label || current.name_zh || current.name_zh_raw || current.name_en || "家具";
  const width = Number(current.widthCm || current.size_cm?.width || 0).toFixed(0);
  const depth = Number(current.depthCm || current.size_cm?.depth || 0).toFixed(0);
  const context = document.createElement("section");
  context.className = "rp-selected-furniture-context";
  context.dataset.selectedFurnitureContext = "true";
  context.innerHTML = `
    <div class="rp-selected-furniture-heading">
      <div>
        <span class="eyebrow">目前選取</span>
        <strong>${escapeHtml(name)}</strong>
        <small>${escapeHtml(room?.label || "目前房間")} · ${width} × ${depth} cm</small>
      </div>
      <span class="rp-selected-furniture-state">${selected?.model_locked ? "已鎖定" : "可調整"}</span>
    </div>
    <div class="rp-selected-furniture-actions">
      <button type="button" class="primary-action" data-open-same-type-replacement>更換同類家具</button>
      <button type="button" class="secondary-action" data-open-all-type-replacement>改選其他類型</button>
      <button type="button" class="secondary-action" data-lock-current-furniture>${selected?.model_locked ? "解除鎖定" : "鎖定此家具"}</button>
      <button type="button" class="danger-action" data-delete-current-furniture>刪除</button>
    </div>
    <p class="rp-field-hint">替換時會先保留原家具，僅列出可放入此房間的候選；確認後才套用。</p>
  `;
  panel.querySelector("h3")?.insertAdjacentElement("afterend", context);
}

function syncFurnitureNumberVisibility() {
  const button = $("#toggle-furniture-numbers");
  if (button) {
    button.classList.toggle("is-active", state.showFurnitureNumbers);
    button.setAttribute("aria-pressed", String(state.showFurnitureNumbers));
    button.textContent = state.showFurnitureNumbers ? "隱藏編號" : "顯示編號";
  }
  // Step 6 is a whole-home overview. The walk-room selector must not filter
  // numbered furniture markers, because its ID can differ from scene objects.
  whiteViewer?.setFurnitureNumberMarkersVisible?.(state.showFurnitureNumbers);
  renderConfigurationPlan();
}

function selectSceneObjectByFurnitureId(furnitureId, {
  viewer = null,
  focus = true,
  renderList = true,
} = {}) {
  const index = sceneObjectIndexByFurnitureId(furnitureId);
  if (index < 0) return false;
  state.selectedSceneIndex = index;
  if (renderList) {
    renderSceneObjectList();
    loadSelectedSceneAppearance();
  }
  viewer?.selectObjectByIndex?.(index, { focus });
  if (focus) {
    const host = viewer?.getCanvasHost?.();
    host?.classList.add("rp-scene-selection-flash");
    window.setTimeout(() => host?.classList.remove("rp-scene-selection-flash"), 700);
  }
  return true;
}

function activeSceneViewerForStep() {
  if (["white_model_3d", "realistic_3d"].includes(state.workflow?.currentStep)) {
    return whiteViewer;
  }
  return null;
}

function syncSelected2dFurnitureToScene({ focus = false } = {}) {
  const viewer = activeSceneViewerForStep();
  if (!viewer || !state.selectedFurniture2dId) return false;
  return selectSceneObjectByFurnitureId(state.selectedFurniture2dId, { viewer, focus });
}

function syncSceneSelectionTo2dFurniture(sceneObject) {
  const furnitureId = sceneObject?.furniture_id;
  if (!furnitureId) return false;
  const item = state.furniture2d.find(
    (candidate) => String(candidate.id) === String(furnitureId),
  );
  if (!item) return false;
  state.selectedFurniture2dId = item.id;
  renderLayoutFurniture();
  renderConfigurationPlan();
  if (state.workflow?.currentStep === "white_model_3d") {
    setSceneSidebarTab("selection");
    renderSelectedFurnitureWorkspace();
  }
  return true;
}

function syncMovedSceneFurnitureTo2d(sceneObject) {
  const index = sceneObjectIndexByFurnitureId(sceneObject?.furniture_id);
  if (index < 0) return false;
  const roomId = roomIdForScenePosition(sceneObject.position_cm || {});
  const synchronized = {
    ...sceneObject,
    placement_room_id: roomId,
    placement_failed: false,
    placement_reason: "",
  };
  state.sceneData.scene_objects[index] = synchronized;
  state.furniture2d = upsertFurniture2dFromSceneObject(
    state.furniture2d,
    synchronized,
    { roomId },
  );
  return true;
}

function workflowPayload() {
  pruneRetiredAppliances();
  applyWholeHouseSurfaceConsistency();
  persistActiveScheme(state.designSchemes, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  const stepIsLive = (step) => state.workflow?.currentStep === step
    || state.workflow?.completed.includes(step);
  const calibrationIsLive = stepIsLive("calibration")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("space_confirmation"))
      .some((step) => stepIsLive(step));
  const spaceIsLive = stepIsLive("space_confirmation")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("requirements"))
      .some((step) => stepIsLive(step));
  const requirementsAreLive = stepIsLive("requirements")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("layout_2d"))
      .some((step) => stepIsLive(step))
    || state.basicConfirmed
    || Object.keys(state.basicAnswers || {}).length > 0
    || Object.keys(state.visualAnswers || {}).length > 0;
  const layoutIsLive = stepIsLive("layout_2d")
    || stepIsLive("white_model_3d")
    || stepIsLive("realistic_3d")
    || stepIsLive("proposal_review")
    || stepIsLive("ai_render");
  const whiteModelIsLive = stepIsLive("white_model_3d")
    || stepIsLive("realistic_3d")
    || stepIsLive("proposal_review")
    || stepIsLive("ai_render");
  const realisticIsLive = stepIsLive("realistic_3d")
    || stepIsLive("proposal_review")
    || stepIsLive("ai_render");
  const proposalIsLive = stepIsLive("proposal_review") || stepIsLive("ai_render");
  const hasSchemeLayoutState = Boolean(state.designSchemes.schemes.B)
    || Object.values(state.designSchemes.schemes).some(
      (scheme) => (scheme.furniture || []).length > 0
        || Boolean(scheme.sceneData)
        || Boolean(scheme.stale),
    );
  return {
    project_schema_version: PROJECT_SCHEMA_VERSION,
    _flow: state.workflow?.toJSON() || null,
    floorplan_confirmation: state.workflow?.data?.floorplan_confirmation || {},
    recognition: stepIsLive("recognition") || calibrationIsLive ? state.analysis : null,
    confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null,
    calibration: calibrationIsLive ? state.workflow?.data?.calibration || null : null,
    space_confirmation: spaceIsLive
      ? {
          coordinate_unit: "cm",
          schema_version: "2.0",
          rooms: state.rooms,
          structures: state.structures,
          confirmed_structure_snapshot: state.confirmedStructureSnapshot,
          dismissed_auto_room_ids: state.dismissedAutoRoomIds,
        }
      : null,
    requirements: requirementsAreLive
      ? {
          basic: state.basicAnswers,
          basicConfirmed: state.basicConfirmed,
          questionnaireStage: state.questionnaireStage,
          visualCatalogVersion: state.visualCatalogVersion,
          visualAnswers: state.visualAnswers,
          skippedVisualSpaceTypes: state.skippedVisualSpaceTypes,
          finishes: state.questionnaireFinishes,
          roomRequirementModel: state.roomRequirementModel,
        }
      : null,
    layout_2d: layoutIsLive || hasSchemeLayoutState
      ? {
          schema_version: PROJECT_SCHEMA_VERSION,
        }
      : null,
    configuration: layoutIsLive || hasSchemeLayoutState
      ? {
          schema_version: PROJECT_SCHEMA_VERSION,
          active_scheme_id: state.designSchemes.active_scheme_id,
          locked_scheme_id: state.designSchemes.locked_scheme_id,
          room_selections: state.designSchemes.room_selections,
          configuration_snapshot: state.designSchemes.configuration_snapshot,
          schemes: Object.fromEntries(
            Object.entries(state.designSchemes.schemes).map(([id, scheme]) => [
              id,
              {
                ...scheme,
                furniture: scheme.furniture,
                sceneData: scheme.sceneData,
              },
            ]),
          ),
        }
      : null,
    white_model_3d: whiteModelIsLive && state.sceneData
      ? {
          schema_version: PROJECT_SCHEMA_VERSION,
          sceneId: state.sceneData.scene_id,
          diagnostics: whiteViewer.getDiagnostics(),
        }
      : null,
    realistic_3d: realisticIsLive
      ? {
          activeStylePackId: state.activeStylePackId,
          surfaceState: state.surfaceState,
          materialBoundary: state.materialBoundary,
          dismissedDecorRoles: state.dismissedDecorRoles,
        }
      : null,
    proposal_review: proposalIsLive
      ? {
          masterView: state.proposalReview.masterView,
          confirmedStyleCardId: state.proposalReview.confirmedStyleCardId,
          roomViews: state.proposalReview.roomViews,
          jobs: state.proposalReview.jobs,
          renderBriefs: state.proposalReview.renderBriefs || [],
        }
      : null,
  };
}

let saveSequence = Promise.resolve();
let pendingSaveCount = 0;
let pendingSaveRevision = 0;
let projectExitConfirmed = false;

function pendingSaveStorageKey() {
  return state.projectId ? `roompilot.pending-save.${state.projectId}` : "";
}

function capturePendingSave(currentStep = state.workflow?.currentStep) {
  const serialized = JSON.stringify({
    save_id: `${Date.now()}-${pendingSaveRevision += 1}`,
    base_updated_at: state.project?.updated_at || null,
    current_step: currentStep,
    workflow: workflowPayload(),
  });
  localStorage.setItem(pendingSaveStorageKey(), serialized);
  return serialized;
}

async function saveWorkflowRequest(serialized) {
  if (!state.projectId) return null;
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch(`/api/projects/${state.projectId}/workflow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: serialized,
      });
      const result = repairMojibakeDeep(await response.json());
      if (!response.ok) {
        throw new Error(result.detail?.message || result.detail || "專案保存失敗。");
      }
      return result;
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 180 * (attempt + 1)));
    }
  }
  throw lastError;
}

function scheduleSave(currentStep = state.workflow?.currentStep) {
  if (!state.projectId) return;
  const serialized = capturePendingSave(currentStep);
  pendingSaveCount += 1;
  element.saveStatus.textContent = "正在保存…";
  saveSequence = saveSequence.catch(() => null).then(async () => {
    try {
      const requestPayload = JSON.parse(serialized);
      requestPayload.base_updated_at = state.project?.updated_at
        || requestPayload.base_updated_at;
      const result = await saveWorkflowRequest(JSON.stringify(requestPayload));
      state.project = result.project;
      const pendingKey = pendingSaveStorageKey();
      const latestPending = localStorage.getItem(pendingKey);
      const latestPayload = latestPending ? JSON.parse(latestPending) : null;
      const savedPayload = JSON.parse(serialized);
      const savedLatest = latestPayload?.save_id
        ? latestPayload.save_id === savedPayload.save_id
        : latestPending === serialized;
      if (savedLatest) {
        localStorage.removeItem(pendingKey);
      } else if (latestPending) {
        latestPayload.base_updated_at = state.project.updated_at;
        localStorage.setItem(pendingKey, JSON.stringify(latestPayload));
      }
      element.saveStatus.textContent = `已自動保存 · ${state.project.name}`;
    } catch (error) {
      element.saveStatus.textContent = "保存失敗";
      setStatus(errorMessage(error), "error");
    } finally {
      pendingSaveCount -= 1;
    }
  });
}

async function confirmProjectExit(event) {
  event.preventDefault();
  if (!confirm("要離開目前專案並返回首頁嗎？系統會先完成目前的自動儲存。")) return;

  if (pendingSaveCount > 0) {
    element.saveStatus.textContent = "正在完成儲存…";
  }
  await saveSequence.catch(() => null);

  const pendingKey = pendingSaveStorageKey();
  if (pendingKey && localStorage.getItem(pendingKey)) {
    setStatus("專案尚未完成保存，請稍後再試。", "error");
    return;
  }
  projectExitConfirmed = true;
  location.assign("/");
}

function invalidateDownstreamFrom(step, message = "") {
  if (!state.workflow?.invalidateFrom?.(step)) return;
  if (step !== "proposal_review" && step !== "ai_render") {
    state.proposalReview = {
      masterView: null,
      confirmedStyleCardId: null,
      roomViews: {},
      jobs: [],
    };
    state.selectedRenderRoomId = null;
  }
  if (step === "space_confirmation") {
    state.confirmedStructureSnapshot = null;
    persistActiveScheme(state.designSchemes, {
      furniture: state.furniture2d,
      sceneData: state.sceneData,
    });
    markSchemeLayoutsStale(state.designSchemes, message);
    state.sceneData = null;
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "requirements") {
    persistActiveScheme(state.designSchemes, {
      furniture: state.furniture2d,
      sceneData: state.sceneData,
    });
    markSchemeLayoutsStale(state.designSchemes, message);
    state.sceneData = null;
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "layout_2d") {
    state.sceneData = null;
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "white_model_3d") {
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  }
  if (message) setStatus(message);
}

function activeSchemeId() {
  return state.designSchemes.active_scheme_id || "A";
}

function activeScheme() {
  return state.designSchemes.schemes[activeSchemeId()];
}

function syncFurnitureInventoryAcrossSchemes() {
  persistActiveScheme(state.designSchemes, { furniture: state.furniture2d });
  const source = state.furniture2d;
  Object.entries(state.designSchemes.schemes).forEach(([schemeId, scheme]) => {
    if (schemeId === activeSchemeId()) return;
    const existingById = new Map((scheme.furniture || []).map((item) => [item.id, item]));
    scheme.furniture = source.map((item) => {
      const existing = existingById.get(item.id);
      if (!existing) {
        return {
          ...JSON.parse(JSON.stringify(item)),
          placementFailed: true,
          placementReason: "家具清單已同步，請由引擎重新計算此方案的位置。",
        };
      }
      return {
        ...JSON.parse(JSON.stringify(item)),
        xCm: existing.xCm,
        yCm: existing.yCm,
        rotationDeg: existing.rotationDeg,
        placementFailed: existing.placementFailed,
        placementReason: existing.placementReason,
      };
    });
    scheme.sceneData = null;
    scheme.stale = true;
    scheme.staleReason = "共用家具清單已變更，請重新配置此方案。";
  });
  roomSchemePreviewCache.clear();   // 方案內容已變，舊 3D 預覽作廢
  renderSchemeControls();
}

async function switchDesignScheme(schemeId) {
  persistActiveScheme(state.designSchemes, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  const scheme = activateScheme(state.designSchemes, schemeId);
  if (!scheme) return false;
  state.furniture2d = scheme.furniture || [];
  state.sceneData = scheme.sceneData || null;
  proposalRuntimeState.sceneVersionLoaded = null;   // 換方案是整場重建,第 7 步快取失效
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  renderSchemeControls();
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  const step = state.workflow?.currentStep;
  if (state.sceneData && step === "white_model_3d") {
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    renderSceneObjectList();
    syncSelected2dFurnitureToScene({ focus: true });
  } else if (state.sceneData && step === "realistic_3d") {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
    renderSceneObjectList();
    syncSelected2dFurnitureToScene({ focus: true });
  } else if (state.sceneData && step === "proposal_review") {
    await proposalViewer.loadScene(state.sceneData);
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
    element.proposalContentConfirmed.checked = false;
    state.proposalReview.masterView = null;
    state.designSchemes.locked_scheme_id = null;
    renderProposalSummary();
  } else if (["white_model_3d", "realistic_3d"].includes(step)) {
    setStatus(`方案 ${schemeId} 尚未產生 3D 場景，請回第 6 步確認此方案。`);
  }
  scheduleSave(state.workflow?.currentStep || "space_confirmation");
  return true;
}

function markRealisticSceneEdited() {
  proposalRuntimeState.sceneVersionLoaded = null;   // 場景內容變了,第 7 步快取失效
  if (state.workflow?.completed.includes("realistic_3d")) {
    state.workflow.invalidateFrom("realistic_3d");
    state.proposalReview = {
      masterView: null,
      confirmedStyleCardId: null,
      roomViews: {},
      jobs: [],
    };
    state.selectedRenderRoomId = null;
    setStatus("即時寫實方案已修改；請重新保存並鎖定渲染視角。");
  }
  scheduleSave("realistic_3d");
}

function activePanelName(step) {
  return WORKFLOW_PANEL_BY_STEP[step] || step;
}

// 擺放/生成期間的全畫面等待提示:agent 還在算就明確告訴使用者要等,
// 深度計數讓巢狀流程(確認問卷 → 逐房擺位 → 生成 3D)只在全部結束後才收。
let placementBusyDepth = 0;
function beginPlacementBusy(text) {
  placementBusyDepth += 1;
  if (!element.placementBusy) return;
  if (text && element.placementBusyText) element.placementBusyText.textContent = text;
  element.placementBusy.hidden = false;
}

function endPlacementBusy() {
  placementBusyDepth = Math.max(0, placementBusyDepth - 1);
  if (placementBusyDepth === 0 && element.placementBusy) {
    element.placementBusy.hidden = true;
  }
}

function showStep(step) {
  const panelName = activePanelName(step);
  panels.forEach((panel, name) => {
    const visible = name === panelName;
    panel.hidden = !visible;
    panel.classList.toggle("is-active", visible);
    if (visible) {
      panel.querySelectorAll(".rp-control-pane").forEach((pane) => {
        pane.scrollTop = 0;
      });
    }
  });
  const [number, text] = instructions[step] || instructions.project;
  element.stepNumber.textContent = number;
  element.instruction.textContent = text;
  if (step === "space_confirmation") {
    setSpaceReviewMode(state.spaceReviewMode);
  }
  if (step === "requirements") void prepareQuestionnaireStep();
  if (step === "proposal_review") void prepareProposalReview();
  if (step === "ai_render") void prepareAiRender();
  if (["white_model_3d", "realistic_3d"].includes(step)) {
    renderWhiteWalkRoomSelector();
    renderConfigurationPlan();
    setSceneSidebarTab(step === "realistic_3d" ? "surfaces" : "plan");
    syncFurnitureNumberVisibility();
    const confirmConfiguration = $("#confirm-white-model");
    if (confirmConfiguration) confirmConfiguration.hidden = step === "realistic_3d";
    if (step === "realistic_3d") {
      focusStepSixRoom(state.selectedRoomId || state.selectedWalkRoomId || state.rooms[0]?.id);
    }
    if (step === "white_model_3d") {
      // 進第 6 步工作台的第一件事是選方案，選定後才拿該方案的擺設去微調。
      renderRoomSchemeGate();
      if (roomSchemeGateBlocking()) requestAnimationFrame(promptRoomSchemeSelection);
    }
  }
  const currentPublicStep = publicWorkflowStep(step);
  const currentPublicIndex = PUBLIC_WORKFLOW_STEPS.indexOf(currentPublicStep);
  $$(".rp-progress button").forEach((button) => {
    const targetIndex = PUBLIC_WORKFLOW_STEPS.indexOf(button.dataset.step);
    button.classList.toggle("is-active", button.dataset.step === currentPublicStep);
    button.classList.toggle(
      "is-complete",
      targetIndex >= 0 && targetIndex < currentPublicIndex,
    );
  });
  requestAnimationFrame(syncAllOverlays);
}

async function renderRestoredStep() {
  renderSchemeControls();
  if (state.rooms.length) {
    state.selectedRoomId = state.selectedRoomId || state.rooms[0].id;
    renderRooms();
    renderStructureCounts();
  }
  if (state.furniture2d.length) {
    state.selectedFurniture2dId = state.selectedFurniture2dId || state.furniture2d[0].id;
    state.activeLayoutRoomId = state.activeLayoutRoomId || state.furniture2d[0].roomId || "all";
    renderLayoutRoomFilter();
    renderLayoutFurniture();
  }
  if (state.sceneData && state.workflow.currentStep === "white_model_3d") {
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    const diagnostics = whiteViewer.getDiagnostics();
    const expectedFurnitureCount = state.sceneData.scene_objects?.filter(
      (item) => !item.placement_failed,
    ).length || 0;
    element.whiteError.textContent = expectedFurnitureCount === 0
      || diagnostics.visibleFurnitureCount > 0
      ? ""
      : "3D 中沒有任何可見家具，不能進入下一步。";
  }
  if (state.sceneData && state.workflow.currentStep === "realistic_3d") {
    const activePack = STYLE_PACKS.find((pack) => pack.id === state.activeStylePackId);
    if (activePack) state.activeStyleId = activePack.styleId;
    if (activePack) {
      state.sceneData.design_choices = state.sceneData.design_choices || {};
      state.sceneData.design_choices.wall_option = resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "wall",
        state.surfaceState.wall?.material || activePack.wall.surfaceOption,
      );
      state.sceneData.design_choices.floor_option = resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "floor",
        state.surfaceState.floor?.material || activePack.floor.surfaceOption,
      );
    }
    renderStyleControls();
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    if (state.surfaceState.wall?.color) $("#wall-color").value = state.surfaceState.wall.color;
    if (state.surfaceState.floor?.color) $("#floor-color").value = state.surfaceState.floor.color;
    if (state.surfaceState.wall?.material) $("#wall-material").value = state.surfaceState.wall.material;
    if (state.surfaceState.floor?.material) $("#floor-material").value = state.surfaceState.floor.material;
    if (state.materialBoundary) {
      const boundaryRoom = state.rooms.find((room) => room.id === state.materialBoundary.roomId);
      $("#material-boundary-direction").value = state.materialBoundary.direction || "vertical";
      $("#material-boundary-position").value = Math.round(
        Number(state.materialBoundary.ratio ?? 0.5) * 100,
      );
      $("#material-boundary-status").textContent =
        `已在${boundaryRoom?.label || "目前房間"}建立可調整的兩材質界線。`;
    }
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
    scheduleSave("realistic_3d");
  }
  requestAnimationFrame(syncAllOverlays);
}

function goTo(step) {
  if (!state.workflow?.goTo(step)) {
    const blocker = firstWorkflowBlocker(step);
    setStatus(blocker, "error");
    return false;
  }
  showStep(step);
  scheduleSave(step);
  return true;
}

function firstWorkflowBlocker(step) {
  const requiredByStep = {
    upload: "請先建立專案。",
    recognition: "請先上傳平面圖並確認圖檔內容。",
    calibration: "請先完成平面圖辨識。",
    space_confirmation: "請先拖曳兩端並確認公分尺度。",
    requirements: "請先確認房間與牆、門、窗、樑、柱。",
    layout_2d: "請先完成基本問卷與每一個房間需求。",
    white_model_3d: "請先確認 2D 家具尺寸與配置。",
    realistic_3d: "請先確認 3D 家具確實可見，並確認指定家具需求。",
    proposal_review: "請先完成並保存即時寫實方案。",
    ai_render: "請先在第 7 步確認完整方案、三種候選色卡與比較視角。",
  };
  return requiredByStep[step] || "前一步尚未完成。";
}

const {
  applyCalibration,
  calibrationPointerDown,
  calibrationPointerMove,
  configureDxfPreview,
  confirmUpload,
  createProject,
  floorplanExtension,
  imageContentRect,
  imagePoint,
  renderCalibration,
  selectFloorplanFile,
  setPlanImages,
  showUploadedPreview,
  syncAllOverlays,
  syncOverlayToImage,
  updateCalibrationAction,
  updateUploadConfirmationState,
} = createSceneFloorplanController({
  $,
  api,
  buildScaleCalibration,
  calibrationActionState,
  createWorkflow,
  element,
  errorMessage,
  goTo,
  initializeRoomsAndStructures: (...args) => initializeRoomsAndStructures(...args),
  recognitionReviewSuffix: (...args) => recognitionReviewSuffix(...args),
  renderConfigurationPlan: (...args) => renderConfigurationPlan(...args),
  renderLayoutFurniture: (...args) => renderLayoutFurniture(...args),
  renderSpaceOverlay: (...args) => renderSpaceOverlay(...args),
  scheduleSave,
  setStatus,
  showStep,
  state,
});

const {
  addDroppedStructure,
  addMissedRoom,
  allStepSixRoomSurfacesConfirmed,
  applyCanonicalRoomLabels,
  applySelectedStructureSize,
  applySelectedWindowType,
  applyWindowType,
  cancelStructureInteraction,
  chooseRoomScheme,
  closeRoomSchemeSelectionDialog,
  cmToPixel,
  completeRoomSchemeSelection,
  composeSelectedRoomFurniture,
  configurationSnapshot,
  confirmAllRooms,
  confirmDimensionedPlan,
  confirmedFloorplanEditor,
  confirmRoom,
  confirmSpace,
  confirmStructure,
  deleteRoom,
  deleteSelectedStructure,
  ensureRoomScheme3dPreviews,
  finishBeamCreateDrag,
  focusStepSixRoom,
  hydrateConfirmedStructureSnapshot,
  hydrateSceneWallMass,
  initializeRoomsAndStructures,
  lockedConfigurationSnapshot,
  lockSelectedDoorOpening,
  mergeSelectedRoomNodes,
  mergeSelectedRooms,
  navigateRoomScheme3dPreview,
  normalizeIconInferredRoomReview,
  openRoomScheme3dPreview,
  openRoomSchemeSelectionDialog,
  planGeometry,
  preparedAutoRoomLabels,
  previewSelectedStructureDraft,
  promptRoomSchemeSelection,
  recognitionReviewSuffix,
  refreshConfigurationSnapshot,
  renderDoorReviewList,
  renderRooms,
  renderRoomSchemeGate,
  renderRoomSchemeSelectionDialog,
  renderSchemeControls,
  renderSelectedStructureEditor,
  renderSpaceOverlay,
  renderStepSixSurfaceProgress,
  renderStructureCounts,
  renderStructureReviewList,
  repairLoadedStructureWallCollisions,
  roomFinishDraftFor,
  roomPolygonSvg,
  roomQuestionnaireSummary,
  roomSchemeGateBlocking,
  roomSchemeSelectionRequired,
  rotateSelectedDoor180,
  rotateSelectedStructure,
  saveRoom,
  selectedSchemeMismatchNotice,
  selectedStepSixRoom,
  selectedStructureItem,
  selectRoom,
  selectStructureForReview,
  setActiveStructureKind,
  setRoomGeometryMode,
  setRoomNodeMode,
  setSelectedOpeningWidthCm,
  setSpaceReviewMode,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  setTaskDialogOpen,
  SHOW_ALL_ROOMS_BUTTONS,
  spacePointerDown,
  spacePointerMove,
  stepSixRoomSurfaceConfirmed,
  stepSixSurfacesFinalLocked,
  stepSixSurfaceUnlockButtons,
  structureCollections,
  structureSectionMeta,
  structureWallCollision,
  syncConfigurationConfirmButton,
  updateShowAllRoomsButton,
} = createSceneStructureController({
  $,
  $$,
  activePanelName,
  activeScheme,
  activeSchemeId,
  allRoomsHaveSchemeSelections,
  applyWindowTypePreset,
  attachedOpenings,
  beamDragGeometry,
  buildDimensionedPlanAnnotations,
  clipPolygonByLine,
  configurationBlockingFurniture: (...args) => configurationBlockingFurniture(...args),
  confirmedWallGapForDoor,
  convexHull,
  deactivateWhiteInteractionMode: (...args) => deactivateWhiteInteractionMode(...args),
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  element,
  ensureSchemeB,
  errorMessage,
  escapeHtml,
  findStructureWallCollision,
  glbThumbnailQueue,
  glbThumbnailViewer,
  goTo,
  imagePoint,
  instructions,
  invalidateDownstreamFrom,
  materialOptionsForStyle: (...args) => materialOptionsForStyle(...args),
  normalizedWindowType,
  pointInPolygonCm,
  polygonArea,
  previewStepSixRoomSurfaces: (...args) => previewStepSixRoomSurfaces(...args),
  renderStyleControls: (...args) => renderStyleControls(...args),
  renderWhiteWalkRoomSelector: (...args) => renderWhiteWalkRoomSelector(...args),
  renderWholeHouseQuestionnaire: (...args) => renderWholeHouseQuestionnaire(...args),
  repairLoadedRoomPolygon,
  resolveStructureWallCollisions,
  resolveSurfaceOption,
  reviewItemsFromAnalysis,
  ROOM_NAME_OPTIONS,
  roomCenter,
  roomDimensions,
  roomNameOptionFor,
  roomPolygonsDiffer,
  roomSchemePreviewCache,
  roomSchemePreviewViewer,
  roomSchemeRuntimeState,
  scheduleSave,
  selectedSchemeForRoom,
  selectSchemeForRoom,
  setStatus,
  showStep,
  state,
  structurePreview,
  structureRuntimeState,
  structuresForScheme,
  STYLE_MATERIAL_OPTIONS,
  syncOverlayToImage,
  unresolvedReviewRooms,
  userFacingMaterialLabel: (...args) => userFacingMaterialLabel(...args),
  validateColumnDimensionsCm,
  whiteViewer,
  WINDOW_TYPES,
  windowsOverlap,
});

const {
  activeQuestionnairePack,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  activeRoomRequirement,
  applyWholeHouseSurfaceConsistency,
  catalogMaterialOptionsForPack,
  circulationStyleIsOverridden,
  clearRequirementsGenerationHelp,
  confirmBasicQuestionnaire,
  confirmQuestionnaireFinishes,
  confirmRequirements,
  copyLivingRoomStyleToCirculation,
  isCirculationRoom,
  livingRoomForCirculation,
  materialCatalogColor,
  materialCatalogType,
  materialPairScore,
  materialVisualTagMarkup,
  moveVisualQuestion,
  normalizedRoomSurfaces,
  normalizeSavedSceneWallSurfaces,
  openQuestionnaireCeilingDesignStyle,
  openQuestionnaireCeilingPicker,
  prepareQuestionnaireStep,
  QUESTIONNAIRE_ROOM_SECTIONS,
  questionnaireMaterialOptionsForPack,
  questionnaireMaterialPairCards,
  renderQuestionnaireFinishes,
  renderQuestionnaireMaterialCatalog,
  renderQuestionnairePlan,
  renderQuestionnaireRoomSections,
  renderVisualQuestionnaire,
  renderWholeHouseQuestionnaire,
  resolvedVisualPreferences,
  saveVisualCustomAnswer,
  selectPreferenceWeight,
  selectQuestionnaireCeilingDesignPack,
  selectQuestionnaireCeilingPickerItem,
  selectQuestionnaireMaterial,
  selectQuestionnaireMaterialPair,
  selectQuestionnaireStylePack,
  selectStepSixCatalogMaterial,
  selectVisualOption,
  selectWholeHouseStylePack,
  showQuestionnaireStage,
  skipQuestionnaireWithDefaults,
  styleCompatibleMaterialOptionsForPack,
  userFacingMaterialLabel,
  visualPreferencesForRoom,
  wholeHouseFinishDraft,
  wholeHouseStylePack,
} = createSceneQuestionnaireController({
  $,
  $$,
  api,
  applyRoomFinishScope,
  applyVerifiedRandomQuestionnaireFurniture: (...args) => applyVerifiedRandomQuestionnaireFurniture(...args),
  autoLayoutFurniture: (...args) => autoLayoutFurniture(...args),
  beginPlacementBusy,
  buildRoomRequirementsPayload,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  cmToPixel,
  element,
  endPlacementBusy,
  ensureQuestionnaireFurnitureRecommendations: (...args) => ensureQuestionnaireFurnitureRecommendations(...args),
  ensureRoomUsage: (...args) => ensureRoomUsage(...args),
  ensureSchemeB,
  errorMessage,
  escapeHtml,
  evaluateConditionalOption,
  finishesGate,
  generateWhiteModelFromRequirements: (...args) => generateWhiteModelFromRequirements(...args),
  invalidateDownstreamFrom,
  LIGHT_STYLES,
  normalizeRoomRequirements,
  planGeometry,
  previewStepSixRoomSurfaces: (...args) => previewStepSixRoomSurfaces(...args),
  promptRoomSchemeSelection,
  questionnaireFurnitureDisplayLabel: (...args) => questionnaireFurnitureDisplayLabel(...args),
  questionnaireFurnitureProgram: (...args) => questionnaireFurnitureProgram(...args),
  questionnaireRuntimeState,
  questionnaireSummary,
  relayoutFurnitureForScheme: (...args) => relayoutFurnitureForScheme(...args),
  renderFurnitureLibrary: (...args) => renderFurnitureLibrary(...args),
  renderGenerativeEquipment: (...args) => renderGenerativeEquipment(...args),
  renderMaterialPairPreviews,
  renderQuestionnaireFurnitureRecommendations: (...args) => renderQuestionnaireFurnitureRecommendations(...args),
  renderQuestionnaireRoomUsage: (...args) => renderQuestionnaireRoomUsage(...args),
  roomCenter: (...args) => roomCenter(...args),
  roomFurnitureRequirement: (...args) => roomFurnitureRequirement(...args),
  roomPolygonSvg,
  roomUsageOptions: (...args) => roomUsageOptions(...args),
  scheduleSave,
  setStatus,
  settleQuestionnaireRagForLayout,
  startQuestionnaireRag,
  state,
  STYLE_FAMILIES,
  STYLE_PACKS,
  stylePackByIdSafe: (...args) => stylePackByIdSafe(...args),
  switchDesignScheme,
  syncOverlayToImage,
  WHOLE_HOUSE_QUESTIONS,
});

const {
  addFurnitureFromLibrary,
  applyVerifiedRandomQuestionnaireFurniture,
  autoLayoutFurniture,
  catalogItemRenderable,
  catalogItemRenderKey,
  configurationBlockingFurniture,
  configurationFurnitureNumber,
  confirmLayout2d,
  ensureQuestionnaireFurnitureRecommendations,
  ensureRoomUsage,
  finishActiveFurnitureDrag,
  furniture2dDefaultsForSceneObject,
  layoutPointerDown,
  layoutPointerMove,
  loadReplacementCandidates,
  openFurnitureReplacement,
  planCenterCm,
  previewReplacementCandidate,
  prioritizeConfigurationRoomFurniture,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureOffers,
  questionnaireFurniturePreferenceTags,
  questionnaireFurnitureProgram,
  questionnaireFurnitureSelectionItem,
  reflowSingleConfigurationFurniture,
  refreshQuestionnaireFurnitureRecommendations,
  relayoutFurnitureForScheme,
  renderConfigurationPlan,
  renderFurnitureLibrary,
  renderGenerativeEquipment,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireFurnitureRecommendations,
  renderQuestionnaireRoomUsage,
  repairFurnitureRoomPlacements,
  replacementFurnitureName,
  replacementRoomBounds,
  replaceSelectedLayoutFurniture,
  roomFurnitureRequirement,
  roomIdForScenePosition,
  roomSurfaceAssignments,
  roomUsageOptions,
  sceneObjectMatchesLayoutFurniture,
  scenePointCoordinates,
  segmentOverlapsBounds,
  setReplacementDrawerOpen,
  shiftFloorplanRegion,
  shiftRoomSurfaceAssignment,
  shiftScenePoint,
  shiftSceneSegment,
  syncFinalValidationToConfiguration,
  toggleQuestionnaireFurniturePreferenceTag,
  updateGenerativeEquipment,
  updateGenerativeEquipmentNotes,
  updateQuestionnaireFurnitureQuantity,
  updateQuestionnaireFurnitureSelection,
  updateQuestionnaireFurnitureVariant,
  updateSelectedFurnitureDimensions,
} = createSceneConfigurationController({
  $,
  $$,
  activeQuestionnairePack,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  activeRoomRequirement,
  activeScheme,
  activeSchemeId,
  api,
  applianceRequirementsForRendering,
  applyVisualPreferencesToSpecs,
  buildRoomRequirementsPayload,
  CATALOG_RETRIEVAL_ROUTES,
  catalogFurnitureOffer,
  catalogMaterialOptionsForPack,
  completeRoomSchemeSelection,
  configurationReflowInFlight,
  configurationSnapshot,
  confirmedFloorplanEditor,
  createFurniture2DItem,
  element,
  errorMessage,
  escapeHtml,
  findFurniture2DVariant,
  FURNITURE_2D_LIBRARY,
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  glbThumbnailQueue,
  glbThumbnailScene: (...args) => glbThumbnailScene(...args),
  glbThumbnailViewer,
  goTo,
  imageContentRect,
  invalidateDownstreamFrom,
  isQuestionnaireFallbackTypeMatch,
  loadSelectedSceneAppearance: (...args) => loadSelectedSceneAppearance(...args),
  mergeCatalogFurniture,
  normalizedRoomSurfaces,
  occupantsFromBasicAnswers,
  openQuestionnaireFurnitureCatalog: (...args) => openQuestionnaireFurnitureCatalog(...args),
  persistActiveScheme,
  planCmToLayerPixel,
  planGeometry,
  pointInPolygonCm,
  pruneRetiredAppliances,
  QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS,
  QUESTIONNAIRE_FALLBACK_CATALOG_RULES,
  QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS,
  QUESTIONNAIRE_FURNITURE_SHORT_LABELS,
  QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES,
  QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS,
  questionnaireFurnitureInFlight,
  rankCatalogFurniture,
  recommendedFurnitureForRoom,
  reconcileFurniture2dAfterGeneration,
  removeRetiredAppliancesFromFurniture,
  renderQuestionnaireRoomSections,
  renderSceneObjectList: (...args) => renderSceneObjectList(...args),
  replaceFurniture2DItem,
  REPLACEMENT_TYPE_LABELS,
  replacementViewer,
  resolvedVisualPreferences,
  resolveSurfaceOption,
  ROOM_TYPE_EXCLUDED_FURNITURE_TYPES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  roomCenter,
  roomDimensions,
  roomPolygonSvg,
  roomUsageVisual,
  sceneDataFromGenerateResponse,
  sceneObjectIndexByFurnitureId,
  scheduleSave,
  selectedSchemeMismatchNotice,
  setStatus,
  showStep,
  state,
  STYLE_PACKS,
  syncConfigurationConfirmButton,
  syncFurnitureInventoryAcrossSchemes,
  syncOverlayToImage,
  syncSelected2dFurnitureToScene,
  toSceneFurniture,
  unavailableCatalogModelUrls,
  upsertFurniture2dFromSceneObject,
  verifiedCatalogModelUrls,
  visualPreferencesForRoom,
  whiteViewer,
});

const {
  activateWhiteFurnitureEditing,
  activateWhiteWalkMode,
  addQuestionnaireCatalogFurniture,
  addSceneFurniture,
  applyStylePackToScene,
  cancelWhiteModelBeamPlacement,
  confirmStepSixRoomSurfaces,
  confirmWhiteModel,
  deactivateWhiteInteractionMode,
  deleteSelectedSceneFurniture,
  evaluateCeilingConflicts,
  firstUnconfirmedStepSixRoom,
  generateWhiteModelFromRequirements,
  glbThumbnailScene,
  loadSelectedSceneAppearance,
  materialOptionsForStyle,
  openQuestionnaireFurnitureCatalog,
  previewStepSixRoomSurfaces,
  removeMaterialBoundary,
  renderGroupedMaterialOptions,
  renderQuestionnaireCatalogBatch,
  renderQuestionnaireCatalogBrowseChoices,
  renderSceneObjectList,
  renderStyleControls,
  renderWhiteWalkRoomSelector,
  replaceSceneFurniture,
  saveSelectedSceneAppearance,
  searchGlbFurniture,
  setFurnitureCatalogOpen,
  stylePackByIdSafe,
  toggleMaterialBoundary,
  unlockStepSixRoomSurfaces,
} = createSceneModelingController({
  $,
  $$,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  allRoomsHaveSchemeSelections,
  api,
  applyStylePack,
  CATALOG_FACET_TRADITIONAL_LABELS,
  catalogItemRenderable,
  catalogItemRenderKey,
  catalogMaterialOptionsForPack,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  circulationStyleIsOverridden,
  configurationBlockingFurniture,
  confirmedFloorplanEditor,
  confirmLayout2d,
  detectCeilingConflicts,
  element,
  errorMessage,
  escapeHtml,
  firstWorkflowBlocker,
  focusStepSixRoom,
  furniture2dDefaultsForSceneObject,
  glbThumbnailCache,
  glbThumbnailQueue,
  glbThumbnailViewer,
  goTo,
  invalidateDownstreamFrom,
  isCirculationRoom,
  LIGHT_STYLES,
  livingRoomForCirculation,
  materialPairScore,
  materialVisualTagMarkup,
  openRoomSchemeSelectionDialog,
  planCenterCm,
  pruneAutomaticSoftDecor,
  QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS,
  QUESTIONNAIRE_CATALOG_PURPOSE_TYPES,
  QUESTIONNAIRE_CATALOG_PURPOSES,
  QUESTIONNAIRE_CATALOG_SPACES,
  QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureOffers,
  questionnaireFurnitureSelectionItem,
  realisticViewer,
  refreshConfigurationSnapshot,
  reloadViewerPreservingState,
  removeFurniture2dBySceneObject,
  renderConfigurationPlan,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireFurnitureRecommendations,
  renderSelectedFurnitureWorkspace,
  renderStepSixSurfaceProgress,
  resolveSurfaceOption,
  roomCenter,
  roomFinishDraftFor,
  roomFurnitureRequirement,
  roomQuestionnaireSummary,
  roomSchemeSelectionRequired,
  scheduleSave,
  selectedStepSixRoom,
  selectSceneObjectByFurnitureId,
  setStatus,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  showStep,
  state,
  STEP_SIX_SURFACE_MATERIAL_LIMIT,
  STEP_SIX_SURFACE_SWATCH_LIMIT,
  stepSixRoomSurfaceConfirmed,
  stepSixSurfacesFinalLocked,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
  styleCompatibleMaterialOptionsForPack,
  styleFurnitureCache,
  switchDesignScheme,
  syncFinalValidationToConfiguration,
  syncFurnitureInventoryAcrossSchemes,
  upsertFurniture2dFromSceneObject,
  whiteViewer,
});

const {
  closeDesignDelivery,
  closeProposalPaletteImageStage,
  closeRenderBriefDialog,
  closeRenderImageStage,
  completedOpenrouterRows,
  confirmRenderBriefAndSubmit,
  confirmRenderPalette,
  currentSceneVersion,
  downloadDesignDeliveryJson,
  downloadEngineeringDelivery,
  generateDeliveryProposal,
  generateDesignDelivery,
  lockMasterRenderView,
  openRenderBriefDialog,
  prepareAiRender,
  prepareProposalReview,
  renderProposalSummary,
  roomCameraSuggestion,
  roomWalkPayload,
  saveSelectedRoomView,
  selectProposalPalette,
  selectRenderRoom,
  showRenderImageEnlarged,
  updateAiRenderImageStage,
} = createSceneProposalController({
  activeScheme,
  activeSchemeId,
  aiRenderViewer,
  allRoomsHaveSchemeSelections,
  api,
  beginPlacementBusy,
  composeSelectedRoomFurniture,
  configurationSnapshot,
  element,
  endPlacementBusy,
  errorMessage,
  escapeHtml,
  finishesGate,
  goTo,
  lockedConfigurationSnapshot,
  pointInPolygonCm,
  proposalRoomPreviewCache,
  proposalRuntimeState,
  proposalViewer,
  refreshConfigurationSnapshot,
  renderSchemeControls,
  roomSchemeSelectionRequired,
  scheduleSave,
  setStatus,
  showQuestionnaireStage,
  state,
  STYLE_PACKS,
  visualQuestionnaireProgress,
  WHOLE_HOUSE_QUESTIONS,
});

const bindEvents = createSceneEventBindings({
  $,
  $$,
  activateWhiteFurnitureEditing,
  activateWhiteWalkMode,
  activeQuestionnairePack,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  activeRoomRequirement,
  activeSchemeId,
  addDroppedStructure,
  addFurnitureFromLibrary,
  addMissedRoom,
  addQuestionnaireCatalogFurniture,
  addSceneFurniture,
  allStepSixRoomSurfacesConfirmed,
  applyCalibration,
  applySelectedStructureSize,
  applySelectedWindowType,
  applyStylePackToScene,
  applyWindowType,
  autoLayoutFurniture,
  beginPlacementBusy,
  buildSpecialRequestAnswer,
  calibrationPointerDown,
  calibrationPointerMove,
  cancelStructureInteraction,
  cancelWhiteModelBeamPlacement,
  capturePendingSave,
  catalogRuntimeState,
  chooseRoomScheme,
  clearRequirementsGenerationHelp,
  closeDesignDelivery,
  closeProposalPaletteImageStage,
  closeRenderBriefDialog,
  closeRenderImageStage,
  closeRoomSchemeSelectionDialog,
  completedOpenrouterRows,
  completeRoomSchemeSelection,
  configurationFurnitureNumber,
  confirmAllRooms,
  confirmBasicQuestionnaire,
  confirmDimensionedPlan,
  confirmLayout2d,
  confirmProjectExit,
  confirmQuestionnaireFinishes,
  confirmRenderBriefAndSubmit,
  confirmRenderPalette,
  confirmRequirements,
  confirmRoom,
  confirmSpace,
  confirmStepSixRoomSurfaces,
  confirmStructure,
  confirmUpload,
  confirmWhiteModel,
  copyLivingRoomStyleToCirculation,
  createProject,
  deleteRoom,
  deleteSelectedSceneFurniture,
  deleteSelectedStructure,
  downloadDesignDeliveryJson,
  element,
  endPlacementBusy,
  ensureQuestionnaireFurnitureRecommendations,
  ensureRoomScheme3dPreviews,
  ensureRoomUsage,
  errorMessage,
  evaluateCeilingConflicts,
  finishActiveFurnitureDrag,
  finishBeamCreateDrag,
  firstUnconfirmedStepSixRoom,
  firstWorkflowBlocker,
  focusStepSixRoom,
  generateDeliveryProposal,
  generateDesignDelivery,
  goTo,
  imagePoint,
  invalidateDownstreamFrom,
  isCirculationRoom,
  layoutPointerDown,
  layoutPointerMove,
  livingRoomForCirculation,
  loadReplacementCandidates,
  loadSelectedSceneAppearance,
  lockMasterRenderView,
  lockSelectedDoorOpening,
  markRealisticSceneEdited,
  materialCatalogColor,
  materialCatalogType,
  mergeSelectedRoomNodes,
  mergeSelectedRooms,
  moveVisualQuestion,
  navigateRoomScheme3dPreview,
  openFurnitureReplacement,
  openQuestionnaireCeilingDesignStyle,
  openQuestionnaireCeilingPicker,
  openQuestionnaireFurnitureCatalog,
  openRenderBriefDialog,
  openRoomScheme3dPreview,
  openRoomSchemeSelectionDialog,
  pendingSaveCount,
  pendingSaveStorageKey,
  previewReplacementCandidate,
  previewSelectedStructureDraft,
  previewStepSixRoomSurfaces,
  prioritizeConfigurationRoomFurniture,
  projectExitConfirmed,
  proposalRuntimeState,
  proposalViewer,
  QUESTIONNAIRE_ROOM_SECTIONS,
  questionnaireFurniturePreferenceTags,
  questionnaireMaterialOptionsForPack,
  questionnaireMaterialPairCards,
  questionnaireRuntimeState,
  realisticViewer,
  reflowSingleConfigurationFurniture,
  refreshQuestionnaireFurnitureRecommendations,
  relayoutFurnitureForScheme,
  removeMaterialBoundary,
  renderCalibration,
  renderConfigurationPlan,
  renderDoorReviewList,
  renderFurnitureLibrary,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireCatalogBatch,
  renderQuestionnaireCatalogBrowseChoices,
  renderQuestionnaireFinishes,
  renderQuestionnaireFurnitureRecommendations,
  renderQuestionnaireMaterialCatalog,
  renderQuestionnairePlan,
  renderQuestionnaireRoomSections,
  renderQuestionnaireRoomUsage,
  renderRooms,
  renderRoomSchemeSelectionDialog,
  renderSceneObjectList,
  renderSchemeControls,
  renderSelectedStructureEditor,
  renderSpaceOverlay,
  renderStructureCounts,
  renderStructureReviewList,
  renderStyleControls,
  renderVisualQuestionnaire,
  replaceSceneFurniture,
  replaceSelectedLayoutFurniture,
  rotateSelectedDoor180,
  rotateSelectedStructure,
  saveRoom,
  saveSelectedRoomView,
  saveSelectedSceneAppearance,
  saveVisualCustomAnswer,
  scheduleSave,
  searchGlbFurniture,
  selectedStructureItem,
  selectFloorplanFile,
  selectPreferenceWeight,
  selectProposalPalette,
  selectQuestionnaireCeilingDesignPack,
  selectQuestionnaireCeilingPickerItem,
  selectQuestionnaireMaterial,
  selectQuestionnaireMaterialPair,
  selectQuestionnaireStylePack,
  selectRenderRoom,
  selectRoom,
  selectStepSixCatalogMaterial,
  selectStructureForReview,
  selectVisualOption,
  selectWholeHouseStylePack,
  setActiveStructureKind,
  setFurnitureCatalogOpen,
  setReplacementDrawerOpen,
  setRoomGeometryMode,
  setRoomNodeMode,
  setSceneSidebarTab,
  setSelectedOpeningWidthCm,
  setSpaceReviewMode,
  setStatus,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  setTaskDialogOpen,
  SHOW_ALL_ROOMS_BUTTONS,
  showQuestionnaireStage,
  showRenderImageEnlarged,
  showStep,
  skipQuestionnaireWithDefaults,
  spacePointerDown,
  spacePointerMove,
  state,
  stepSixSurfaceUnlockButtons,
  structureCollections,
  structurePreview,
  structureRuntimeState,
  structureSectionMeta,
  structureWallCollision,
  STYLE_PACKS,
  switchDesignScheme,
  syncAllOverlays,
  syncFurnitureInventoryAcrossSchemes,
  syncFurnitureNumberVisibility,
  syncSceneSelectionTo2dFurniture,
  syncSelected2dFurnitureToScene,
  toggleMaterialBoundary,
  toggleQuestionnaireFurniturePreferenceTag,
  unlockStepSixRoomSurfaces,
  updateAiRenderImageStage,
  updateCalibrationAction,
  updateGenerativeEquipment,
  updateGenerativeEquipmentNotes,
  updateQuestionnaireFurnitureQuantity,
  updateQuestionnaireFurnitureSelection,
  updateQuestionnaireFurnitureVariant,
  updateSelectedFurnitureDimensions,
  updateShowAllRoomsButton,
  updateUploadConfirmationState,
  whiteViewer,
  wholeHouseStylePack,
});

const {
  recoverConfirmedFloorplan,
  restoreProject,
} = createSceneRestoreController({
  $,
  activeScheme,
  activeSchemeId,
  api,
  applyCanonicalRoomLabels,
  applyStyleCardHandoff,
  applyWholeHouseSurfaceConsistency,
  configureDxfPreview,
  confirmedFloorplanEditor,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  element,
  errorMessage,
  floorplanExtension,
  furniture2dDefaultsForSceneObject,
  generateWhiteModelFromRequirements,
  hydrateConfirmedStructureSnapshot,
  hydrateSceneWallMass,
  normalizeDesignSchemes,
  normalizeIconInferredRoomReview,
  normalizeRoomRequirements,
  normalizeSavedSceneData,
  normalizeSavedSceneWallSurfaces,
  normalizeSavedSpaceConfirmation,
  normalizeSceneDoorSegments,
  pendingSaveStorageKey,
  persistActiveScheme,
  preparedAutoRoomLabels,
  pruneRetiredAppliances,
  recognitionReviewSuffix,
  renderRestoredStep,
  repairFurnitureRoomPlacements,
  repairLoadedRoomPolygon,
  repairLoadedStructureWallCollisions,
  resolvedVisualPreferences,
  restoreDoorSwingEndpointsFromConfirmedStructures,
  restoreWorkflow,
  roomPolygonsDiffer,
  roomSurfaceAssignments,
  scheduleSave,
  setPlanImages,
  setStatus,
  shouldReplayPendingSave,
  showStep,
  showUploadedPreview,
  state,
  STYLE_PACKS,
  toSceneFurniture,
  upsertFurniture2dFromSceneObject,
});

bindEvents();
renderFurnitureLibrary();
applyStyleCardHandoff();
renderStyleControls();
evaluateCeilingConflicts();
restoreProject();
