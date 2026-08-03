import { createSceneViewer } from "./scene_viewer.js?v=sha256-2af33fe35ac8";
import { confirmedWallGapForDoor } from "./scene_architecture.js?v=sha256-25568bdd96c1";
import { renderMaterialPairPreviews } from "./scene_material_pair_preview.js?v=sha256-257a140bd340";
import { repairMojibakeDeep } from "./scene_text_encoding.js?v=sha256-9693c47a7d4c";
import { resolveSurfaceOption } from "./scene_surface_materials.js?v=sha256-21fd27184d7e";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-66d8d568f445";
import {
  repairLoadedRoomPolygon,
} from "./scene_room_geometry.js?v=sha256-d863939b9c06";
import {
  createWorkflow,
  restoreWorkflow,
  shouldReplayPendingSave,
  WORKFLOW_PANEL_BY_STEP,
  WORKFLOW_STEPS,
} from "./scene_workflow.js?v=20260723-proportion-gate1";
import {
  buildScaleCalibration,
  calibrationActionState,
  calibrationPointsFromAnalysis,
} from "./scene_calibration.js?v=sha256-0247aea142bf";
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
} from "./scene_layout2d.js?v=sha256-b6f034658424";
import {
  removeFurniture2dBySceneObject,
  upsertFurniture2dFromSceneObject,
} from "./scene_configuration_sync.js?v=sha256-4229260e286c";
import {
  catalogFurnitureOffer,
  rankCatalogFurniture,
} from "./scene_furniture_retrieval.js?v=sha256-735762d2e6ca";
import {
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-b4b03dbe76aa";
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
} from "./scene_questionnaire_test2.js?v=sha256-e474d1b8c555";
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
} from "./scene_room_requirements.js?v=sha256-d07a1e5499ca";
import {
  applyStylePack,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_FAMILIES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-e8e4ed1badaf";
import {
  beamDragGeometry,
  canMarkWallForDemolition,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  wallBoundarySide,
  windowsOverlap,
} from "./scene_structure_utils.js?v=sha256-d56a61642343";
import { createStructurePreview } from "./scene_structure_preview.js?v=sha256-2e7650196b86";
import {
  findStructureWallCollision,
  resolveStructureWallCollisions,
  validateColumnDimensionsCm,
} from "./scene_structure_geometry.js?v=sha256-4a2bf6282bb0";
import { buildDimensionedPlanAnnotations } from "./scene_dimensioned_plan.js?v=20260723-dimensioned-plan1";
import {
  applyWindowTypePreset,
  normalizedWindowType,
  WINDOW_TYPES,
} from "./scene_window_types.js?v=sha256-990e2abb3240";
import {
  activateScheme,
  allRoomsHaveSchemeSelections,
  attachedOpenings,
  compactDesignSchemesForSpace,
  deleteSchemeB,
  ensureSchemeB,
  hasRenovationChanges,
  markSchemeLayoutsStale,
  normalizeDesignSchemes,
  persistActiveScheme,
  selectSchemeForRoom,
  selectedSchemeForRoom,
  structuresForScheme,
} from "./scene_design_schemes.js?v=sha256-07e6d0f65dce";

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

const ROOM_NAME_OPTIONS = Object.freeze([
  { id: "hallway", label: "走道／動線", type: "hallway", classification: "Hallway" },
  { id: "bathroom", label: "浴室", type: "bathroom", classification: "Bath" },
  { id: "bedroom", label: "臥室", type: "bedroom", classification: "Bedroom" },
  { id: "kitchen", label: "廚房", type: "kitchen", classification: "Kitchen" },
  { id: "living_room", label: "客廳", type: "living_room", classification: "LivingRoom" },
  { id: "balcony", label: "陽台", type: "balcony", classification: "Balcony" },
  { id: "entryway", label: "玄關", type: "entryway", classification: "Entry" },
  { id: "storage", label: "儲藏室", type: "storage", classification: "Storage" },
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
  structures: { walls: [], doors: [], windows: [], beams: [], columns: [] },
  designSchemes: normalizeDesignSchemes(),
  activeStructureKind: "door",
  structureTool: null,
  structureLineStart: null,
  structureLinePreviewEnd: null,
  pendingWallDeleteId: null,
  selectedStructure: null,
  windowNormalizationRemoved: 0,
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
  // Step 6 uses the same visible numbering as the 2D configuration plan.
  showFurnitureNumbers: true,
  sceneData: null,
  autoGeneratingWhiteModel: false,
  requirementsGenerationPending: false,
  lastWhiteModelGenerationError: "",
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
  },
  selectedRenderRoomId: null,
  selectedProposalRoomId: null,
  selectedProposalRoomCandidateIndex: 0,
  selectedRoomSchemeId: null,
};
let styleApplyRevision = 0;
const proposalRoomPreviewCache = new Map();
const roomSchemePreviewCache = new Map();
let roomSchemePreviewInFlight = null;
let roomSchemeAlternativeInFlight = null;
let pendingRenderBriefMode = null;
let visualCustomSaveTimer = null;
let questionnaireCatalogRoomId = null;
let questionnaireCatalogScope = "room";
let questionnaireCatalogSpace = "";
let questionnaireCatalogPurpose = "";
let questionnaireCatalogSearchTimer = null;
let questionnaireCatalogSelectedFurnitureIds = new Set();
let questionnaireCatalogSelectedFurniture = new Map();
let questionnaireCeilingPickerKind = null;
let questionnaireMaterialCatalogKind = null;
let questionnaireMaterialCatalogSearch = "";
let questionnaireMaterialCatalogType = "all";
let questionnaireMaterialCatalogColor = "all";
const configurationReflowInFlight = new Set();
let questionnaireRoomSection = "usage";
const questionnaireFurnitureInFlight = new Set();
const questionnaireRagPending = new Map();

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
  recognitionSummary: $("#recognition-summary"),
  spaceImage: $("#space-plan-image"),
  spaceStage: $("#space-plan-stage"),
  spaceOverlay: $("#space-plan-overlay"),
  schemeCompare: $("#design-scheme-compare"),
  schemeAImage: $("#scheme-a-plan-image"),
  schemeAOverlay: $("#scheme-a-plan-overlay"),
  schemeBImage: $("#scheme-b-plan-image"),
  schemeBOverlay: $("#scheme-b-plan-overlay"),
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
  randomizeRequirementsSummary: $("#randomize-requirements-summary"),
  confirmRequirements: $("#confirm-requirements"),
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
  roomScheme3dPreviewDialog: $("#room-scheme-3d-preview-dialog"),
  roomScheme3dPreviewTitle: $("#room-scheme-3d-preview-title"),
  roomScheme3dPreviewStatus: $("#room-scheme-3d-status"),
  roomSchemeWarning: $("#room-scheme-warning"),
  roomSchemeComplete: $("#room-scheme-complete"),
  openSurfaceAdjustment: $("#open-surface-adjustment"),
  openLightingAdjustment: $("#open-lighting-adjustment"),
  surfaceAdjustmentDialog: $("#surface-adjustment-dialog"),
  lightingAdjustmentDialog: $("#lighting-adjustment-dialog"),
  surfaceAdjustmentContent: $("#surface-adjustment-content"),
  lightingAdjustmentContent: $("#lighting-adjustment-content"),
  renderBriefDialog: $("#render-brief-dialog"),
  renderBriefSummary: $("#render-brief-summary"),
  renderBriefNotes: $("#render-brief-notes"),
  renderBriefWarning: $("#render-brief-warning"),
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
  openQuestionnaireFurnitureCatalog: $("#open-questionnaire-furniture-catalog"),
  standardCatalogSearch: $("#glb-furniture-search"),
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
const roomSchemePreviewViewer = createSceneViewer(
  $("#room-scheme-3d-preview"),
  element.roomScheme3dPreviewStatus,
);
const structurePreview = createStructurePreview($("#structure-3d-preview"));
const styleFurnitureCache = new Map();
const glbThumbnailCache = new Map();
const verifiedCatalogModelUrls = new Set();
const unavailableCatalogModelUrls = new Set();
let glbThumbnailBatch = 0;
let glbThumbnailSequence = Promise.resolve();
let questionnaireFurnitureThumbnailRevision = 0;

function setStatus(message, kind = "normal") {
  element.status.textContent = message;
  element.status.dataset.kind = kind;
}

function errorMessage(error) {
  if (typeof error === "string" && error.trim()) return error.trim();
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
    if (payload && typeof payload === "object") Object.assign(error, payload);
    error.status = response.status;
    error.endpoint = url;
    error.responseBody = payload;
    throw error;
  }
  return payload;
}

function sceneDataFromGenerateResponse(payload) {
  return payload?.scene_json || payload;
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

function applyRagFurnitureHitsToDefaultSelection(room, hitIds) {
  const furniture = roomFurnitureRequirement(room?.id);
  const offers = state.roomFurnitureRecommendations[room?.id] || [];
  if (!furniture?.selected?.length || !hitIds.size || !offers.length) return;
  furniture.selected = furniture.selected.map((selected, index) => {
    if (selected.user_selected === true) return selected;
    const replacement = offers.find((offer) => (
      offer.normalized_type === selected.normalized_type
      && hitIds.has(String(offer.furniture_id))
      && Boolean(offer.model_url)
    ));
    if (!replacement) return selected;
    return {
      ...questionnaireFurnitureSelectionItem(replacement, index + 1),
      count: Math.max(1, Number(selected.count) || 1),
      default_recommendation: true,
      selection_source: "questionnaire_rag_hit",
      rag_baseline: selected.rag_baseline || { ...selected },
    };
  });
}

function restoreRagFurnitureDefaults(room) {
  const furniture = roomFurnitureRequirement(room?.id);
  if (!furniture?.selected?.length) return;
  furniture.selected = furniture.selected.map((item) => (
    item.selection_source === "questionnaire_rag_hit" && item.rag_baseline
      ? { ...item.rag_baseline, count: item.count, selection_priority: item.selection_priority }
      : item
  ));
}

async function hydrateRagFurnitureHits(room, hitIds) {
  const known = state.roomFurnitureRecommendations[room.id] || [];
  const knownIds = new Set(known.map((item) => String(item.furniture_id)));
  const missingIds = [...hitIds].filter((id) => id && !knownIds.has(id));
  if (!missingIds.length) return known;
  let resolved = [];
  try {
    const payload = await api(`/api/furniture?has_model=true&detail=scene&page_size=80&ids=${encodeURIComponent(missingIds.join(","))}`);
    resolved = payload.items || [];
  } catch {
    resolved = [];
  }
  const additions = resolved.filter((item) => item?.model_url).map((item) => ({
    ...item,
    room_fit_checked: false,
    reason: "RAG 推薦，待第 6 步位置驗證",
  }));
  state.roomFurnitureRecommendations[room.id] = [...known, ...additions];
  return state.roomFurnitureRecommendations[room.id];
}

async function startQuestionnaireRag(room) {
  if (!room) return;
  const roomId = String(room.id);
  const query = questionnaireRagQuery(room);
  const pending = questionnaireRagPending.get(roomId);
  if (pending?.query === query) return pending.promise;
  const existingJob = state.roomRagJobs[room.id];
  if (
    ["completed", "unavailable", "no_furniture_rag_required"].includes(existingJob?.status)
    && existingJob.query === query
  ) {
    return existingJob;
  }
  restoreRagFurnitureDefaults(room);
  let resolvePending;
  const pendingTask = new Promise((resolve) => { resolvePending = resolve; });
  const finishPending = (result) => {
    if (questionnaireRagPending.get(roomId)?.promise === pendingTask) {
      questionnaireRagPending.delete(roomId);
    }
    resolvePending(result);
  };
  questionnaireRagPending.set(roomId, { query, promise: pendingTask });
  const isCurrentRagRequest = () => (
    questionnaireRagPending.get(roomId)?.promise === pendingTask
    && questionnaireRagQuery(room) === query
  );
  const markRagUnavailable = (message) => {
    if (!isCurrentRagRequest()) {
      finishPending({ status: "superseded", query });
      return;
    }
    state.roomRagJobs[room.id] = {
      ...state.roomRagJobs[room.id],
      status: "unavailable",
      error: message || "RAG 搜尋未完成",
      query,
    };
    scheduleSave("requirements");
    finishPending(state.roomRagJobs[room.id]);
  };
  const selected = roomFurnitureRequirement(room.id)?.selected || [];
  if (String(room.type || room.room_type || "") === "stair" && !selected.length) {
    state.roomRagJobs[room.id] = {
      status: "no_furniture_rag_required",
      query: "",
      reason: "stair_has_no_movable_furniture",
    };
    scheduleSave("requirements");
    finishPending(state.roomRagJobs[room.id]);
    return pendingTask;
  }
  if (!query) {
    finishPending(null);
    return pendingTask;
  }
  try {
    const job = await api("/api/rag/search/jobs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, top_k: 6, fast: true }),
    });
    state.roomRagJobs[room.id] = { jobId: job.job_id, status: job.status, query };
    // Persist immediately so a reload does not discard a queued room job.
    scheduleSave("requirements");
    renderVisualSpaceNav();
    setStatus(`${room.label} 的家具偏好已送交 RAG 排序，您可繼續填下一個空間。`);
    const poll = async () => {
      try {
        const snapshot = await api(`/api/rag/search/jobs/${job.job_id}`);
        if (!isCurrentRagRequest()) {
          finishPending({ status: "superseded", query });
          return;
        }
        state.roomRagJobs[room.id] = { ...state.roomRagJobs[room.id], ...snapshot };
        renderVisualSpaceNav();
        if (snapshot.status === "completed") {
        const ids = new Set((snapshot.result?.blocks || []).flatMap((block) =>
          (block.hits || []).map((hit) => String(hit.furniture?.item_id || "")),
        ));
        const offers = await hydrateRagFurnitureHits(room, ids);
        state.roomFurnitureRecommendations[room.id] = [...offers].sort((left, right) =>
          Number(ids.has(String(right.furniture_id))) - Number(ids.has(String(left.furniture_id))),
        );
        applyRagFurnitureHitsToDefaultSelection(room, ids);
        if (String(activeQuestionnaireRoom()?.id) === String(room.id)) {
          renderQuestionnaireFurnitureRecommendations(room);
        }
        scheduleSave("requirements");
        finishPending(state.roomRagJobs[room.id]);
        return;
      }
        if (snapshot.status === "failed") {
          markRagUnavailable(snapshot.error?.message || "RAG 排序暫時無法完成");
          return;
        }
        if (snapshot.status === "queued" || snapshot.status === "running") {
          window.setTimeout(() => { void poll(); }, 900);
          return;
        }
        markRagUnavailable(`RAG 工作狀態：${snapshot.status || "unknown"}`);
      } catch (error) {
        markRagUnavailable(errorMessage(error));
      }
    };
    window.setTimeout(() => { void poll(); }, 500);
  } catch (error) {
    // RAG is an enhancement to ranking; questionnaire completion never blocks on it.
    markRagUnavailable(errorMessage(error));
  }
  return pendingTask;
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

function sceneObjectIndexByFurnitureId(furnitureId) {
  if (!furnitureId || !state.sceneData?.scene_objects?.length) return -1;
  const id = String(furnitureId);
  const layoutItem = state.furniture2d.find(
    (item) => String(item.id) === id,
  );
  const identifiers = new Set([
    id,
    layoutItem?.catalogFurnitureId,
    layoutItem?.furniture_id,
  ].filter(Boolean).map(String));
  return state.sceneData.scene_objects.findIndex((item) => {
    const sceneIdentifiers = [
      item.furniture_id,
      item.catalog_furniture_id,
      item.catalogFurnitureId,
      item.layout_furniture_id,
      item.source_furniture_id,
      item.id,
    ].filter(Boolean).map(String);
    return sceneIdentifiers.some((candidate) => identifiers.has(candidate));
  });
}

function setSceneSidebarTab(tab = "plan") {
  const sidebar = $(".rp-3d-sidebar");
  if (!sidebar) return;
  const nextTab = ["plan", "issues", "selection"].includes(tab) ? tab : "plan";
  sidebar.dataset.sceneSidebarMode = nextTab;
  $$('[data-scene-sidebar-tab]').forEach((button) => {
    const selected = button.dataset.sceneSidebarTab === nextTab;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  const locks = $("#furniture-property-locks");
  if (locks) locks.hidden = nextTab !== "selection" || !state.selectedFurniture2dId;
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
  if (state.workflow?.currentStep === "realistic_3d") return realisticViewer;
  if (state.workflow?.currentStep === "white_model_3d") return whiteViewer;
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
  if (sceneObjectIndexByFurnitureId(sceneObject?.furniture_id) < 0) return false;
  state.furniture2d = upsertFurniture2dFromSceneObject(
    state.furniture2d,
    sceneObject,
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
    _flow: state.workflow?.toJSON() || null,
    floorplan_confirmation: state.workflow?.data?.floorplan_confirmation || {},
    recognition: stepIsLive("recognition") || calibrationIsLive ? state.analysis : null,
    confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null,
    calibration: calibrationIsLive ? state.workflow?.data?.calibration || null : null,
    space_confirmation: spaceIsLive
      ? {
          coordinate_unit: "cm",
          rooms: state.rooms,
          structures: state.structures,
          confirmed_structure_snapshot: state.confirmedStructureSnapshot,
          dismissed_auto_room_ids: state.dismissedAutoRoomIds,
          design_schemes: compactDesignSchemesForSpace(state.designSchemes),
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
          ragJobs: state.roomRagJobs,
        }
      : null,
    layout_2d: layoutIsLive || hasSchemeLayoutState
      ? {
          furniture: state.furniture2d,
          active_scheme_id: state.designSchemes.active_scheme_id,
          room_selections: state.designSchemes.room_selections,
          configuration_snapshot: state.designSchemes.configuration_snapshot,
          schemes: Object.fromEntries(
            Object.entries(state.designSchemes.schemes).map(([id, scheme]) => [
              id,
              {
                furniture: scheme.furniture,
                stale: scheme.stale,
                staleReason: scheme.staleReason,
              },
            ]),
          ),
        }
      : null,
    white_model_3d: whiteModelIsLive && state.sceneData
      ? {
          sceneId: state.sceneData.scene_id,
          sceneData: state.sceneData,
          diagnostics: whiteViewer.getDiagnostics(),
        }
      : null,
    realistic_3d: realisticIsLive
      ? {
          activeStylePackId: state.activeStylePackId,
          surfaceState: state.surfaceState,
          materialBoundary: state.materialBoundary,
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

function invalidateRenovationScheme(message) {
  // 結構是所有方案共用的基準，不允許只修改方案 B。任何第 4 步結構改動
  // 都必須讓 A、B 一起回到待重新配置狀態。
  invalidateDownstreamFrom(
    "space_confirmation",
    message || "結構已修改，方案 A、B 都需要重新確認家具配置。",
  );
}

function ensureRenovationScheme(reason = "structure_edit") {
  // 舊版把方案 B 當成改造結構方案。保留函式名稱以相容既有事件，
  // 但不再建立結構差異方案。
  void reason;
  return null;
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
    renderSchemeComparison();
  }
  if (step === "requirements") void prepareQuestionnaireStep();
  if (step === "layout_2d") {
    // Step 6 starts by reconfirming the saved per-room A/B plan choices.
    queueMicrotask(promptRoomSchemeSelection);
  }
  if (step === "proposal_review") void prepareProposalReview();
  if (step === "ai_render") void prepareAiRender();
  if (step === "white_model_3d") {
    renderWhiteWalkRoomSelector();
    renderConfigurationPlan();
    setSceneSidebarTab("plan");
    syncFurnitureNumberVisibility();
    // Project recovery can generate the white model immediately after layout_2d.
    // Prompt again here so the required comparison cannot be hidden by that transition.
    queueMicrotask(promptRoomSchemeSelection);
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
  renderSchemeComparison();
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

async function createProject(event) {
  event.preventDefault();
  element.projectError.textContent = "";
  const name = element.projectName.value.trim();
  if (!name) {
    element.projectError.textContent = "請輸入專案名稱，才能建立專案。";
    element.projectName.focus();
    return;
  }
  try {
    const result = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, notes: element.projectNotes.value.trim() }),
    });
    state.project = result.project;
    state.projectId = state.project.project_id;
    state.workflow = createWorkflow({ projectId: state.projectId });
    state.workflow.complete("project", { name });
    history.replaceState({}, "", `/scene?project_id=${encodeURIComponent(state.projectId)}`);
    element.saveStatus.textContent = `已建立 · ${name}`;
    setStatus("專案已建立。下一步只需要上傳平面圖，不會先問需求問卷。");
    scheduleSave("upload");
    goTo("upload");
  } catch (error) {
    element.projectError.textContent = errorMessage(error);
  }
}

function floorplanExtension(file) {
  const name = String(file?.name || "").toLowerCase();
  return [".dxf", ".png", ".jpg", ".jpeg"].find((extension) => name.endsWith(extension)) || "";
}

function clearPendingPreview() {
  if (state.pendingPreviewUrl) URL.revokeObjectURL(state.pendingPreviewUrl);
  state.pendingPreviewUrl = null;
  element.uploadPreview.removeAttribute("src");
  element.uploadPreview.hidden = true;
  element.uploadDropZone.classList.remove("has-preview");
}

function showPendingPreview(file, extension) {
  clearPendingPreview();
  if (!file || extension === ".dxf") return;
  state.pendingPreviewUrl = URL.createObjectURL(file);
  element.uploadPreview.src = state.pendingPreviewUrl;
  element.uploadPreview.hidden = false;
  element.uploadDropZone.classList.add("has-preview");
}

function showUploadedPreview(url, extension) {
  clearPendingPreview();
  if (!url || extension === ".dxf") return;
  element.uploadPreview.src = url;
  element.uploadPreview.hidden = false;
  element.uploadDropZone.classList.add("has-preview");
}

function updateUploadConfirmationState() {
  element.confirmUpload.disabled = !(
    state.pendingFile
    && element.floorplanConfirmation.checked
  );
}

function selectFloorplanFile(file) {
  element.uploadError.textContent = "";
  const extension = floorplanExtension(file);
  if (!extension) {
    state.pendingFile = null;
    clearPendingPreview();
    element.uploadFileState.textContent = "格式不支援";
    element.uploadError.textContent = "只支援 DXF、PNG、JPG 或 JPEG。PDF、WEBP、HEIC 等格式不會上傳。";
    updateUploadConfirmationState();
    return false;
  }
  state.pendingFile = file;
  state.sourceExtension = extension;
  showPendingPreview(file, extension);
  element.uploadFileState.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
  setStatus(extension === ".dxf"
    ? "已選擇 DXF。確認檔案正確並勾選後，系統會產生圖面預覽。"
    : "平面圖已顯示。請確認圖檔內容正確並勾選後繼續。");
  updateUploadConfirmationState();
  return true;
}

async function confirmUpload() {
  element.uploadError.textContent = "";
  if (!state.pendingFile) {
    element.uploadError.textContent = "請先選擇 DXF、PNG、JPG 或 JPEG 平面圖。";
    element.file.focus();
    return;
  }
  if (!element.floorplanConfirmation.checked) {
    element.uploadError.textContent = "請先勾選確認圖檔內容正確，才能進入下一步。";
    element.floorplanConfirmation.focus();
    return;
  }
  try {
    setStatus("正在保存原圖並辨識牆、門、窗…");
    const form = new FormData();
    form.append("file", state.pendingFile);
    const uploaded = await api(`/api/projects/${state.projectId}/floorplan`, {
      method: "POST",
      body: form,
    });
    state.sourceUrl = `${uploaded.upload.source_url}?v=${Date.now()}`;
    state.sourceExtension = uploaded.upload.extension;
    showUploadedPreview(state.sourceUrl, state.sourceExtension);
    state.workflow.setFloorplanConfirmation({ confirmed: true });
    state.workflow.complete("upload", { filename: uploaded.upload.filename });
    await api(`/api/projects/${state.projectId}/workflow`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_step: "upload",
        workflow: {
          floorplan_confirmation: {
            confirmed: true,
          },
        },
      }),
    });
    const result = await api(`/api/projects/${state.projectId}/floorplan/analyze`, {
      method: "POST",
    });
    state.analysis = result.analysis;
    state.workflow.complete("recognition", { engine: result.geometry_engine });
    state.calibrationPoints = calibrationPointsFromAnalysis(state.analysis);
    if (state.sourceExtension === ".dxf") {
      state.sourceUrl = configureDxfPreview(state.analysis);
    }
    setPlanImages(state.sourceUrl);
    const count = {
      walls: state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0,
      doors: state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0,
      windows: state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0,
    };
    element.recognitionSummary.textContent = `辨識結果：牆 ${count.walls}、門 ${count.doors}、窗 ${count.windows}`;
    if (Number(state.analysis.scale?.distance_cm) > 0) {
      element.scaleInput.value = Number(state.analysis.scale.distance_cm);
    } else if (Number(state.analysis.scale?.distance_m) > 0) {
      element.scaleInput.value = Math.round(state.analysis.scale.distance_m * 1000) / 10;
    }
    setStatus(scaleEvidence
      ? "已標出建議端點。請拖曳確認兩端位置，再輸入實際公分尺寸。"
      : "辨識完成。現在請在圖上拉兩端，並輸入這一段的實際公分尺寸。");
    showStep("recognition");
    scheduleSave("recognition");
  } catch (error) {
    element.uploadError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function dxfPreviewDataUrl(floorplan = {}) {
  const segments = floorplan.wall_segments || floorplan.plan_segments || [];
  const width = Math.max(Number(floorplan.width_cm || 600), 1);
  const depth = Math.max(Number(floorplan.depth_cm || 400), 1);
  const pixelWidth = 1000;
  const pixelHeight = Math.max(1, Math.round(pixelWidth * depth / width));
  const lines = segments.map((segment) => {
    const start = segment.start || segment[0] || { x: 0, z: 0 };
    const end = segment.end || segment[1] || { x: 0, z: 0 };
    const x1 = Number(start.x ?? start[0]) + width / 2;
    const y1 = depth / 2 - Number(start.z ?? start.y ?? start[1]);
    const x2 = Number(end.x ?? end[0]) + width / 2;
    const y2 = depth / 2 - Number(end.z ?? end.y ?? end[1]);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" />`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${pixelWidth}" height="${pixelHeight}" viewBox="0 0 ${width} ${depth}"><rect width="${width}" height="${depth}" fill="white"/><g stroke="#222" stroke-width="${Math.max(width, depth) / 500}">${lines}</g></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function configureDxfPreview(analysis) {
  const floorplan = analysis?.floorplan || {};
  const widthCm = Math.max(Number(floorplan.width_cm || 600), 1);
  const depthCm = Math.max(Number(floorplan.depth_cm || 400), 1);
  const previewWidth = 1000;
  const previewHeight = Math.max(1, Math.round(previewWidth * depthCm / widthCm));
  analysis.image_size_px = { width: previewWidth, height: previewHeight };
  analysis.plan_bbox_px = [0, 0, previewWidth, previewHeight];
  analysis.scale = {
    distance_cm: widthCm,
    cm_per_px: widthCm / previewWidth,
    source: "dxf_geometry",
  };
  return dxfPreviewDataUrl(floorplan);
}

function setPlanImages(url) {
  [element.scaleImage, element.spaceImage, element.layoutImage]
    .concat(element.questionnairePlanImage)
    .filter(Boolean)
    .forEach((image) => {
      image.src = url;
      image.addEventListener("load", syncAllOverlays, { once: true });
    });
}

function imageContentRect(image) {
  const box = image.getBoundingClientRect();
  if (!image.naturalWidth || !image.naturalHeight || !box.width || !box.height) return box;
  const scale = Math.min(
    box.width / image.naturalWidth,
    box.height / image.naturalHeight,
  );
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  return {
    left: box.left + (box.width - width) / 2,
    top: box.top + (box.height - height) / 2,
    right: box.left + (box.width + width) / 2,
    bottom: box.top + (box.height + height) / 2,
    width,
    height,
  };
}

function syncOverlayToImage(stage, image, overlay) {
  if (!stage || !image || !overlay || !image.naturalWidth) return;
  const stageRect = stage.getBoundingClientRect();
  const imageRect = imageContentRect(image);
  overlay.style.left = `${imageRect.left - stageRect.left}px`;
  overlay.style.top = `${imageRect.top - stageRect.top}px`;
  overlay.style.width = `${imageRect.width}px`;
  overlay.style.height = `${imageRect.height}px`;
  overlay.style.right = "auto";
  overlay.style.bottom = "auto";
  overlay.setAttribute("viewBox", `0 0 ${image.naturalWidth} ${image.naturalHeight}`);
}

function syncLayoutLayer() {
  if (!element.layoutImage.naturalWidth) return;
  const stageRect = element.layoutStage.getBoundingClientRect();
  const imageRect = imageContentRect(element.layoutImage);
  Object.assign(element.layoutLayer.style, {
    left: `${imageRect.left - stageRect.left}px`,
    top: `${imageRect.top - stageRect.top}px`,
    width: `${imageRect.width}px`,
    height: `${imageRect.height}px`,
    right: "auto",
    bottom: "auto",
  });
}

function syncAllOverlays() {
  syncOverlayToImage(element.scaleStage, element.scaleImage, element.scaleOverlay);
  syncOverlayToImage(element.spaceStage, element.spaceImage, element.spaceOverlay);
  syncOverlayToImage(
    element.dimensionPlanStage,
    element.dimensionPlanImage,
    element.dimensionPlanOverlay,
  );
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  syncOverlayToImage(
    element.questionnairePlanStage,
    element.questionnairePlanImage,
    element.questionnairePlanOverlay,
  );
  syncLayoutLayer();
  renderCalibration();
  renderSpaceOverlay();
  renderLayoutFurniture();
  renderConfigurationPlan();
}

function imagePoint(event, image) {
  const rect = imageContentRect(image);
  if (!rect.width || !rect.height || !image.naturalWidth) return null;
  const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
  const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
  return {
    x: x * image.naturalWidth / rect.width,
    y: y * image.naturalHeight / rect.height,
  };
}

function renderCalibration() {
  const [start, end] = state.calibrationPoints;
  const line = start && end
    ? `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="#bd5c36" stroke-width="5" stroke-dasharray="12 7"/>`
    : "";
  const points = state.calibrationPoints.map((point, index) => `
    <circle data-calibration-point="${index}" cx="${point.x}" cy="${point.y}" r="12"
      fill="#fff" stroke="${index ? "#bd5c36" : "#2f6f87"}" stroke-width="6"/>
  `).join("");
  element.scaleOverlay.innerHTML = `${line}${points}`;
  if (start && end) {
    const pixels = Math.hypot(end.x - start.x, end.y - start.y);
    element.calibrationReadout.textContent = `已定位兩點，圖上距離 ${pixels.toFixed(1)} px。可拖曳圓點微調。`;
  } else if (start) {
    element.calibrationReadout.textContent = "已定位起點，請再點一下終點。";
  } else {
    element.calibrationReadout.textContent = "尚未定位兩點，請先點起點。";
  }
  updateCalibrationAction();
}

function updateCalibrationAction({ showMessage = true } = {}) {
  const action = calibrationActionState(
    state.calibrationPoints,
    element.scaleInput.value,
  );
  element.applyCalibration.disabled = !action.ready;
  if (showMessage) {
    element.scaleError.textContent = action.message;
    element.scaleError.dataset.kind = action.ready ? "ready" : "instruction";
  }
  return action;
}

function calibrationPointerDown(event) {
  const circle = event.target.closest("[data-calibration-point]");
  if (circle) {
    state.calibrationDragIndex = Number(circle.dataset.calibrationPoint);
    circle.setPointerCapture?.(event.pointerId);
    return;
  }
  const point = imagePoint(event, element.scaleImage);
  if (!point) return;
  if (state.calibrationPoints.length >= 2) {
    const distances = state.calibrationPoints.map((candidate) =>
      Math.hypot(candidate.x - point.x, candidate.y - point.y)
    );
    state.calibrationPoints[distances[0] <= distances[1] ? 0 : 1] = point;
  } else {
    state.calibrationPoints.push(point);
  }
  renderCalibration();
}

function calibrationPointerMove(event) {
  if (state.calibrationDragIndex == null) return;
  const point = imagePoint(event, element.scaleImage);
  if (!point) return;
  state.calibrationPoints[state.calibrationDragIndex] = point;
  renderCalibration();
}

function applyCalibrationToAnalysis(analysis, calibration) {
  if (!analysis || typeof analysis !== "object") throw new Error("recognition_result_missing");
  const next = JSON.parse(JSON.stringify(analysis));
  const previousScale = next.scale || {};
  const previousCmPerPx = Number(previousScale.cm_per_px)
    || Number(previousScale.m_per_px) * 100;
  const nextCmPerPx = Number(calibration.cm_per_px);
  if (!(nextCmPerPx > 0)) throw new Error("calibration_measurement_invalid");
  const factor = previousCmPerPx > 0 ? nextCmPerPx / previousCmPerPx : 1;
  const scalePoint = (point) => {
    if (!point || typeof point !== "object") return;
    ["x", "y", "z"].forEach((key) => {
      if (Number.isFinite(Number(point[key]))) point[key] = Number(point[key]) * factor;
    });
  };
  const scalePointList = (points) => {
    if (!Array.isArray(points)) return;
    points.forEach((point) => {
      if (Array.isArray(point)) {
        point.forEach((value, index) => {
          if (Number.isFinite(Number(value))) point[index] = Number(value) * factor;
        });
      } else {
        scalePoint(point);
      }
    });
  };
  const scaleLengthFields = (item) => {
    ["width_cm", "height_cm", "depth_cm", "thickness_cm", "clearance_radius_cm", "width_m", "height_m", "depth_m", "thickness_m", "clearance_radius_m"].forEach((key) => {
      if (Number.isFinite(Number(item?.[key]))) item[key] = Number(item[key]) * factor;
    });
  };
  ["walls", "doors", "windows"].forEach((kind) => {
    (next[kind] || []).forEach((item) => {
      scalePoint(item.start);
      scalePoint(item.end);
      scalePoint(item.swing_end);
      scaleLengthFields(item);
    });
  });
  (next.rooms || []).forEach((room) => {
    ["polygon_cm", "polygon_m", "polygon", "exterior"].forEach((key) => scalePointList(room[key]));
    scalePoint(room.centroid_cm);
    scalePoint(room.centroid_m);
    ["area_cm2", "area_m2"].forEach((key) => {
      if (Number.isFinite(Number(room[key]))) room[key] = Number(room[key]) * factor * factor;
    });
    scaleLengthFields(room);
  });
  const geometryUsesCentimeters = Number(previousScale.cm_per_px) > 0
    || ["cm", "centimeter", "centimetre"].includes(String(next.coordinate_system?.unit || "").toLowerCase());
  next.scale = {
    ...previousScale,
    pixel_distance: Number(calibration.pixel_distance),
    source: "manual_confirmation",
    confidence: 1,
  };
  if (geometryUsesCentimeters) {
    next.scale.distance_cm = Number(calibration.distance_cm);
    next.scale.cm_per_px = nextCmPerPx;
    delete next.scale.distance_m;
    delete next.scale.m_per_px;
  } else {
    next.scale.distance_m = Number(calibration.distance_cm) / 100;
    next.scale.m_per_px = nextCmPerPx / 100;
    delete next.scale.distance_cm;
    delete next.scale.cm_per_px;
  }
  next.evidence = [{
    text: `${Number(calibration.distance_cm)} cm`,
    confidence: 1,
    distance_cm: Number(calibration.distance_cm),
    start_px: calibration.start_px,
    end_px: calibration.end_px,
    pixel_distance: Number(calibration.pixel_distance),
  }];
  next.issues = (next.issues || []).filter((issue) => issue !== "scale_anchor_missing" && issue !== "scale_confirmation_required");
  next.requires_scale_confirmation = false;
  return next;
}

async function applyCalibration() {
  const action = updateCalibrationAction();
  if (!action.ready) {
    if (state.calibrationPoints.length === 2) element.scaleInput.focus();
    return;
  }
  const distanceCm = Number(element.scaleInput.value);
  try {
    const calibration = buildScaleCalibration(state.calibrationPoints, distanceCm);
    setStatus("正在套用確認的公分尺度…");
    if (state.sourceExtension !== ".dxf") {
      state.analysis = applyCalibrationToAnalysis(state.analysis, calibration);
    }
    state.confirmedFloorplan = {
      floorplan: state.analysis.floorplan || state.analysis,
      dxf_text: null,
      confirmation_status: "room_review_pending",
    };
    state.spaceReviewMode = "editing";
    state.workflow.complete("calibration", { distanceCm, calibration });
    initializeRoomsAndStructures();
    state.workflow.goTo("space_confirmation");
    setStatus(`尺度已確認為 ${distanceCm} cm。現在開始確認 ${state.rooms.length} 個房間。`);
    showStep("space_confirmation");
    scheduleSave("space_confirmation");
  } catch (error) {
    element.scaleError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function planGeometry() {
  const imageWidth = state.analysis?.image_size_px?.width || element.spaceImage.naturalWidth || 1000;
  const imageHeight = state.analysis?.image_size_px?.height || element.spaceImage.naturalHeight || 1000;
  const scale = Number(state.analysis?.scale?.cm_per_px)
    || Number(state.analysis?.scale?.m_per_px) * 100
    || 1;
  const bbox = state.analysis?.plan_bbox_px || [0, 0, imageWidth, imageHeight];
  return { imageWidth, imageHeight, scale, bbox };
}

function confirmedFloorplanEditor(schemeId = activeSchemeId()) {
  if (
    !state.confirmedStructureSnapshot
    && state.workflow?.completed.includes("space_confirmation")
  ) {
    // Old saved projects did not persist this snapshot. Build it once from
    // their already-confirmed Step 4 structures, then keep it authoritative.
    state.confirmedStructureSnapshot = captureConfirmedStructureSnapshot();
  }
  const { scale, bbox } = planGeometry();
  const recognizedWidthCm = Math.max(240, (bbox[2] - bbox[0]) * scale);
  const recognizedDepthCm = Math.max(240, (bbox[3] - bbox[1]) * scale);
  return {
    coordinate_unit: "cm",
    width_cm: Number(
      state.confirmedFloorplan?.floorplan?.width_cm || recognizedWidthCm,
    ),
    depth_cm: Number(
      state.confirmedFloorplan?.floorplan?.depth_cm || recognizedDepthCm,
    ),
    room_height_cm: Number(
      state.confirmedFloorplan?.floorplan?.room_height_cm || 270,
    ),
    rooms: JSON.parse(JSON.stringify(state.rooms)),
    structures: structuresForScheme(
      state.confirmedStructureSnapshot || state.structures,
      schemeId,
    ),
  };
}

function captureConfirmedStructureSnapshot() {
  const snapshot = JSON.parse(JSON.stringify(state.structures));
  // Step 4 wall segments are the sole source of door apertures.  A door's
  // visible blue leaf is its open position, so it must never select or split
  // a host wall in Step 6.  The green swing radius is used only to render the
  // closed leaf inside the existing gap between confirmed wall segments.
  snapshot.doors = (snapshot.doors || []).map((door) => ({
    ...door,
    host_wall_id: null,
    host_wall_confirmed: false,
    step4_confirmed: true,
    step4_skip_wall_cut: true,
    doorway_source: "confirmed_wall_gap",
    confirmed_wall_opening: confirmedWallOpeningForSnapshot(
      door,
      snapshot.walls || [],
    ),
  }));
  // Windows are actual wall apertures, so they retain their confirmed host
  // wall and may cut that wall in the Step 6 model.
  snapshot.windows = (snapshot.windows || []).map((window) => {
    const liveWindow = state.structures.windows?.find((item) => item.id === window.id) || window;
    const host = openingHostWall(liveWindow);
    return {
      ...window,
      host_wall_id: host?.id || null,
      host_wall_confirmed: Boolean(host),
      step4_confirmed: true,
      step4_skip_wall_cut: !host,
    };
  });
  return snapshot;
}

function structuralSnapshotPoint(point = {}) {
  return {
    x: Number(point.x),
    z: Number(point.y),
  };
}

function isStructuralSnapshotPoint(point = {}) {
  return Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y));
}

function confirmedWallOpeningForSnapshot(door = {}, walls = []) {
  const persisted = door.confirmed_wall_opening;
  if (
    isStructuralSnapshotPoint(persisted?.start)
    && isStructuralSnapshotPoint(persisted?.end)
  ) {
    return {
      start: { ...persisted.start },
      end: { ...persisted.end },
    };
  }

  const sceneWalls = walls
    .filter((wall) => isStructuralSnapshotPoint(wall.start) && isStructuralSnapshotPoint(wall.end))
    .map((wall) => ({
      ...wall,
      start: structuralSnapshotPoint(wall.start),
      end: structuralSnapshotPoint(wall.end),
    }));
  const sceneDoor = (
    isStructuralSnapshotPoint(door.start)
    && isStructuralSnapshotPoint(door.end)
    && isStructuralSnapshotPoint(door.swing_end)
  )
    ? {
      ...door,
      start: structuralSnapshotPoint(door.start),
      end: structuralSnapshotPoint(door.end),
      swing_end: structuralSnapshotPoint(door.swing_end),
    }
    : null;
  const gap = sceneDoor
    ? confirmedWallGapForDoor(sceneWalls, sceneDoor, 12)
    : null;
  return gap
    ? {
      start: { x: gap.start.x, y: gap.start.z },
      end: { x: gap.end.x, y: gap.end.z },
    }
    : null;
}

function hydrateConfirmedStructureSnapshot(snapshot, fallbackStructures = state.structures) {
  if (!snapshot) return null;
  const walls = snapshot.walls?.length
    ? snapshot.walls
    : (fallbackStructures?.walls || []);
  return {
    ...snapshot,
    doors: (snapshot.doors || []).map((door) => ({
      ...door,
      confirmed_wall_opening: confirmedWallOpeningForSnapshot(door, walls),
    })),
  };
}

function confirmedRoomHeightCm() {
  return Math.max(210, Number(confirmedFloorplanEditor().room_height_cm) || 270);
}

function hydrateSceneWallMass() {
  if (!state.sceneData?.floorplan) return;
  const confirmedPolys = state.confirmedFloorplan?.floorplan?.wall_polys || [];
  if (!state.sceneData.floorplan.wall_polys?.length && confirmedPolys.length) {
    state.sceneData.floorplan.wall_polys = JSON.parse(JSON.stringify(confirmedPolys));
  }
}

function cmToPixel(point) {
  const { scale, bbox } = planGeometry();
  return {
    x: bbox[0] + Number(point.x) / scale,
    y: bbox[3] - Number(point.y) / scale,
  };
}

function pixelToCm(point) {
  const { scale, bbox } = planGeometry();
  return {
    x: (point.x - bbox[0]) * scale,
    y: (bbox[3] - point.y) * scale,
  };
}

function polygonArea(points) {
  if (!points?.length) return 0;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0) / 2);
}

function roomPolygonsDiffer(first, second, toleranceCm = 0.01) {
  if ((first?.length || 0) !== (second?.length || 0)) return true;
  return (first || []).some((point, index) => (
    Math.abs(Number(point.x) - Number(second[index]?.x)) > toleranceCm
    || Math.abs(Number(point.y) - Number(second[index]?.y)) > toleranceCm
  ));
}

function pointInPolygonCm(point, polygon) {
  if (!point || !Array.isArray(polygon) || polygon.length < 3) return false;
  let inside = false;
  for (let index = 0, previousIndex = polygon.length - 1; index < polygon.length; previousIndex = index, index += 1) {
    const current = polygon[index];
    const previous = polygon[previousIndex];
    const intersects = (
      (Number(current.y) > point.y) !== (Number(previous.y) > point.y)
      && point.x < (
        ((Number(previous.x) - Number(current.x)) * (point.y - Number(current.y)))
        / ((Number(previous.y) - Number(current.y)) || 1e-9)
        + Number(current.x)
      )
    );
    if (intersects) inside = !inside;
  }
  return inside;
}

function convexHull(points) {
  const unique = [...new Map(
    points.map((point) => [`${point.x.toFixed(5)}:${point.y.toFixed(5)}`, point]),
  ).values()].sort((a, b) => a.x - b.x || a.y - b.y);
  if (unique.length <= 3) return unique;
  const cross = (origin, a, b) =>
    (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x);
  const lower = [];
  for (const point of unique) {
    while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), point) <= 0) lower.pop();
    lower.push(point);
  }
  const upper = [];
  for (const point of [...unique].reverse()) {
    while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), point) <= 0) upper.pop();
    upper.push(point);
  }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)];
}

function clipPolygonByLine(points, start, end, keepPositive) {
  const side = (point) =>
    (end.x - start.x) * (point.y - start.y) - (end.y - start.y) * (point.x - start.x);
  const inside = (point) => keepPositive ? side(point) >= -1e-6 : side(point) <= 1e-6;
  const intersection = (a, b) => {
    const sideA = side(a);
    const sideB = side(b);
    const denominator = sideA - sideB;
    const t = Math.abs(denominator) < 1e-9 ? 0 : sideA / denominator;
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
    };
  };
  const result = [];
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const previous = points[(index + points.length - 1) % points.length];
    if (inside(current)) {
      if (!inside(previous)) result.push(intersection(previous, current));
      result.push(current);
    } else if (inside(previous)) {
      result.push(intersection(previous, current));
    }
  }
  return result;
}

function roomDimensions(room) {
  const polygon = room.polygon_cm || [];
  const xs = polygon.map((point) => point.x);
  const ys = polygon.map((point) => point.y);
  if (polygon.length < 3) return { widthCm: 0, depthCm: 0, areaM2: 0 };
  return {
    widthCm: Math.max(...xs) - Math.min(...xs),
    depthCm: Math.max(...ys) - Math.min(...ys),
    areaM2: polygonArea(polygon) / 10_000,
  };
}

const ICON_INFERENCE_MAX_ROOM_AREA_M2 = {
  bathroom: 30,
  bedroom: 80,
  kitchen: 80,
};
const STORAGE_INFERENCE_MAX_AREA_CM2 = 500_000;

function genericPendingRoomLabel(room, index) {
  const id = String(room?.id || room?.room_id || "");
  const suffix = id.split("-").at(-1);
  if (/^\d+$/.test(suffix)) return `空間 ${suffix}（待確認）`;
  return `空間 ${index + 1}（待確認）`;
}

function normalizeIconInferredRoomReview(room, polygonCm, index) {
  const next = { ...room };
  const roomType = next.type || next.room_type;
  const maxAreaM2 = ICON_INFERENCE_MAX_ROOM_AREA_M2[roomType];
  const areaM2 = polygonCm.length >= 3
    ? polygonArea(polygonCm) / 10_000
    : Number(next.area_m2 || next.net_area_m2 || 0);
  const reasons = Array.isArray(next.room_review_reasons)
    ? [...next.room_review_reasons]
    : [];
  if (
    next.source === "furniture_icon_inference"
    && maxAreaM2
    && areaM2 > maxAreaM2
  ) {
    next.type = "default";
    next.room_type = "default";
    next.label = genericPendingRoomLabel(next, index);
    next.room_review = true;
    next.confirmed = false;
    if (!reasons.includes("room_icon_area_implausible")) {
      reasons.push("room_icon_area_implausible");
    }
  }
  if (reasons.length) next.room_review_reasons = reasons;
  return next;
}

function pendingRoomBaseLabel(room, fallbackIndex) {
  const label = String(room?.label || room?.name || genericPendingRoomLabel(room, fallbackIndex));
  return label.replace(/\s*（待確認）\s*/g, "").trim() || `空間 ${fallbackIndex + 1}`;
}

function splitImplausibleIconRoomsByInteriorWalls(rooms, walls) {
  const result = [];
  let splitCount = 0;
  const icons = (state.analysis?.room_icon_evidence || [])
    .map((icon) => ({ ...icon, centroid_cm: roomIconCentroidCm(icon) }))
    .filter((icon) => icon.centroid_cm);
  rooms.forEach((room, index) => {
    const reasons = Array.isArray(room.room_review_reasons) ? room.room_review_reasons : [];
    const polygon = room.polygon_cm || [];
    const area = polygonArea(polygon);
    const iconsInRoom = icons.filter((icon) => pointInPolygonCm(icon.centroid_cm, polygon));
    const hasBedIcon = iconsInRoom.some((icon) => icon.class === "bed" && Number(icon.score || 0) >= 0.55);
    const splitDepth = Number(room.auto_split_depth || 0);
    const canContinueSplit = (
      room.auto_split_reason === "room_icon_area_implausible"
      && splitDepth < 2
      && !hasBedIcon
      && area > STORAGE_INFERENCE_MAX_AREA_CM2
    );
    if (
      !reasons.includes("room_icon_area_implausible")
      || polygon.length < 4
      || (room.auto_split_reason && !canContinueSplit)
    ) {
      result.push(room);
      return;
    }
    const xs = polygon.map((point) => Number(point.x || 0));
    const ys = polygon.map((point) => Number(point.y || 0));
    const bounds = {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;
    const candidates = (walls || [])
      .map((wall) => {
        const start = wall.start || {};
        const end = wall.end || {};
        const x0 = Number(start.x || 0);
        const y0 = Number(start.y || 0);
        const x1 = Number(end.x || 0);
        const y1 = Number(end.y || 0);
        const dx = Math.abs(x1 - x0);
        const dy = Math.abs(y1 - y0);
        const length = Math.hypot(dx, dy);
        if (length < 250) return null;
        const vertical = dy > dx * 3;
        const horizontal = dx > dy * 3;
        if (!vertical && !horizontal) return null;
        const midX = (x0 + x1) / 2;
        const midY = (y0 + y1) / 2;
        if (vertical && (midX <= bounds.minX + 60 || midX >= bounds.maxX - 60)) return null;
        if (horizontal && (midY <= bounds.minY + 60 || midY >= bounds.maxY - 60)) return null;
        const startPoint = vertical
          ? { x: midX, y: bounds.minY - 20 }
          : { x: bounds.minX - 20, y: midY };
        const endPoint = vertical
          ? { x: midX, y: bounds.maxY + 20 }
          : { x: bounds.maxX + 20, y: midY };
        const firstPolygon = clipPolygonByLine(polygon, startPoint, endPoint, true);
        const secondPolygon = clipPolygonByLine(polygon, startPoint, endPoint, false);
        const firstArea = polygonArea(firstPolygon);
        const secondArea = polygonArea(secondPolygon);
        const minArea = Math.min(firstArea, secondArea);
        if (
          firstPolygon.length < 3
          || secondPolygon.length < 3
          || minArea < 80_000
        ) return null;
        const spanRatio = vertical ? length / Math.max(height, 1) : length / Math.max(width, 1);
        return {
          firstPolygon,
          secondPolygon,
          score: (spanRatio * 100) + (minArea / Math.max(firstArea + secondArea, 1) * 40),
        };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score);
    const best = candidates[0];
    if (!best) {
      result.push(room);
      return;
    }
    const baseLabel = pendingRoomBaseLabel(room, index);
    [best.firstPolygon, best.secondPolygon].forEach((splitPolygon, splitIndex) => {
      result.push({
        ...room,
        id: `${room.id || `room-${index + 1}`}-auto-split-${splitIndex + 1}`,
        label: `${baseLabel}${splitIndex === 0 ? "A" : "B"}（待確認）`,
        type: "default",
        room_type: "default",
        confidence: Math.min(Number(room.confidence || 0.5), 0.62),
        confirmed: false,
        source: "auto_wall_split_review",
        split_from: room.id,
        root_split_from: room.root_split_from || room.split_from || room.id,
        auto_split_reason: "room_icon_area_implausible",
        auto_split_depth: splitDepth + 1,
        polygon_cm: splitPolygon,
      });
    });
    splitCount += 1;
  });
  if (splitCount > 0) {
    state.roomAutoSplitCount = (state.roomAutoSplitCount || 0) + splitCount;
    return splitImplausibleIconRoomsByInteriorWalls(result, walls);
  }
  return result;
}

function roomIconCentroidCm(icon) {
  const centroid = icon?.centroid_px;
  const bbox = state.analysis?.plan_bbox_px;
  const cmPerPx = Number(state.analysis?.scale?.cm_per_px)
    || Number(state.analysis?.scale?.m_per_px) * 100;
  if (!Array.isArray(centroid) || centroid.length < 2 || !Array.isArray(bbox) || bbox.length < 4 || !cmPerPx) {
    return null;
  }
  return {
    x: (Number(centroid[0]) - Number(bbox[0])) * cmPerPx,
    y: (Number(bbox[3]) - Number(centroid[1])) * cmPerPx,
  };
}

function addRoomReviewReason(room, reason) {
  const reasons = Array.isArray(room.room_review_reasons) ? [...room.room_review_reasons] : [];
  if (!reasons.includes(reason)) reasons.push(reason);
  room.room_review_reasons = reasons;
}

function isDismissedAutoRoom(room) {
  if (!room) return false;
  const dismissed = new Set(state.dismissedAutoRoomIds || []);
  return dismissed.has(room.id)
    || dismissed.has(room.split_from)
    || dismissed.has(room.root_split_from);
}

function applyDjangoZoneRoomLabels(rooms) {
  const icons = (state.analysis?.room_icon_evidence || [])
    .map((icon) => ({ ...icon, centroid_cm: roomIconCentroidCm(icon) }))
    .filter((icon) => icon.centroid_cm);
  if (!icons.length) return rooms;
  const groups = new Map();
  rooms.forEach((room) => {
    if (!room.split_from || room.auto_split_reason !== "room_icon_area_implausible") return;
    const groupKey = room.root_split_from || room.split_from;
    const siblings = groups.get(groupKey) || [];
    siblings.push(room);
    groups.set(groupKey, siblings);
  });
  groups.forEach((siblings) => {
    if (siblings.length < 2) return;
    const iconsByRoom = new Map(siblings.map((room) => [room.id, []]));
    icons.forEach((icon) => {
      const room = siblings.find((candidate) => pointInPolygonCm(icon.centroid_cm, candidate.polygon_cm));
      if (room) iconsByRoom.get(room.id)?.push(icon);
    });
    const bedroomRooms = siblings.filter((room) => (
      iconsByRoom.get(room.id)?.some((icon) => icon.class === "bed" && Number(icon.score || 0) >= 0.55)
    ));
    if (bedroomRooms.length !== 1) return;
    const bedroom = bedroomRooms[0];
    bedroom.type = "bedroom";
    bedroom.room_type = "bedroom";
    bedroom.label = "臥室（待確認）";
    bedroom.source = "django_zone_inference";
    bedroom.confirmed = false;
    bedroom.room_review = true;
    bedroom.confidence = Math.max(Number(bedroom.confidence || 0), 0.62);
    addRoomReviewReason(bedroom, "django_zone_bed_anchor");

    const bedroomArea = polygonArea(bedroom.polygon_cm || []);
    const storageCandidates = siblings
      .filter((room) => room.id !== bedroom.id && !(iconsByRoom.get(room.id) || []).length)
      .map((room) => ({ room, area: polygonArea(room.polygon_cm || []) }))
      .filter(({ area }) => area > 0 && area <= STORAGE_INFERENCE_MAX_AREA_CM2 && area <= Math.max(120_000, bedroomArea * 0.75))
      .sort((a, b) => a.area - b.area);
    const storage = storageCandidates[0]?.room;
    if (!storage) return;
    storage.type = "storage";
    storage.room_type = "storage";
    storage.label = "儲藏室（待確認）";
    storage.source = "django_zone_inference";
    storage.confirmed = false;
    storage.room_review = true;
    storage.confidence = Math.max(Number(storage.confidence || 0), 0.58);
    addRoomReviewReason(storage, "django_zone_storage_candidate");
    let pendingIndex = 2;
    siblings.forEach((room) => {
      if (room.id === bedroom.id || room.id === storage.id) return;
      if ((room.type || room.room_type) !== "default") return;
      room.label = `空間 ${pendingIndex}（待確認）`;
      pendingIndex += 1;
    });
  });
  return rooms;
}

function preparedAutoRoomLabels(rooms, walls) {
  return applyDjangoZoneRoomLabels(
    splitImplausibleIconRoomsByInteriorWalls(rooms, walls),
  ).filter((room) => !isDismissedAutoRoom(room));
}

const CANONICAL_ROOM_LABELS = Object.freeze({
  entryway: "玄關",
  living_room: "客廳",
  kitchen: "廚房",
  bedroom: "臥室",
  bathroom: "浴室",
  storage: "書房／儲藏室",
  balcony: "陽台",
  hallway: "走道／動線",
  stair: "樓梯",
  garage: "車庫",
});
const CIRCLED_ROOM_ORDINALS = Object.freeze(["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]);

function applyCanonicalRoomLabels(rooms) {
  const counts = new Map();
  rooms.forEach((room) => {
    const type = String(room.type || room.room_type || "");
    if (CANONICAL_ROOM_LABELS[type]) counts.set(type, (counts.get(type) || 0) + 1);
  });
  const seen = new Map();
  rooms.forEach((room, roomIndex) => {
    const type = String(room.type || room.room_type || "");
    const baseLabel = CANONICAL_ROOM_LABELS[type];
    if (!baseLabel) {
      if (type && type !== "default") {
        room.type = "default";
        room.room_type = "default";
        room.visual_space_type = "";
        room.label = genericPendingRoomLabel(room, roomIndex);
        room.confirmed = false;
      }
      return;
    }
    const index = (seen.get(type) || 0) + 1;
    seen.set(type, index);
    room.label = counts.get(type) > 1
      ? `${baseLabel}（${CIRCLED_ROOM_ORDINALS[index - 1] || index}）`
      : baseLabel;
    room.visual_space_type = type;
    room.type = type;
    room.room_type = type;
  });
  return rooms;
}

function initializeRoomsAndStructures() {
  const floorplan = state.analysis?.floorplan
    || state.confirmedFloorplan?.floorplan
    || {};
  const hasImageRooms = Boolean(state.analysis?.rooms?.length);
  const sourceRooms = hasImageRooms
    ? state.analysis.rooms
    : floorplan.room_regions || [];
  const widthCm = Number(floorplan.width_cm || 600);
  const depthCm = Number(floorplan.depth_cm || 400);
  const analysisUnit = String(state.analysis?.coordinate_system?.unit || "").toLowerCase();
  const analysisIsCm = ["cm", "centimeter", "centimetre"].includes(analysisUnit)
    || Number(state.analysis?.scale?.cm_per_px) > 0
    || sourceRooms.some((room) => Array.isArray(room?.polygon_cm));
  const sourceScale = hasImageRooms
    ? (analysisIsCm ? 1 : 100)
    : (floorplan.coordinate_unit === "cm" ? 1 : 100);
  const normalizePoint = (point, centered = false) => {
    const x = Number(point?.x ?? point?.[0] ?? 0) * sourceScale;
    const y = Number(point?.y ?? point?.z ?? point?.[1] ?? 0) * sourceScale;
    return {
      x: x + (centered ? widthCm / 2 : 0),
      y: y + (centered ? depthCm / 2 : 0),
    };
  };
  const canonicalStructure = (item = {}) => {
    const result = Object.fromEntries(
      Object.entries(item).filter(([key]) => !key.endsWith("_m") && key !== "size_m"),
    );
    const dimension = (cmKey, legacyKey, fallback) => {
      if (Number.isFinite(Number(item[cmKey]))) return Number(item[cmKey]);
      if (Number.isFinite(Number(item[legacyKey]))) return Number(item[legacyKey]) * 100;
      return fallback;
    };
    return {
      ...result,
      width_cm: dimension("width_cm", "width_m", undefined),
      thickness_cm: dimension("thickness_cm", "thickness_m", undefined),
      height_cm: dimension("height_cm", "height_m", undefined),
      top_cm: dimension("top_cm", "top_m", undefined),
      depth_cm: dimension("depth_cm", "depth_m", undefined),
      size_cm: dimension("size_cm", "size_m", undefined),
      sill_height_cm: dimension("sill_height_cm", "sill_height_m", undefined),
      head_height_cm: dimension("head_height_cm", "head_height_m", undefined),
    };
  };
  let repairedRoomCount = 0;
  state.rooms = sourceRooms.map((room, index) => {
    const polygon = room.polygon_cm || room.polygon_m || room.polygon || room.exterior || [];
    const normalizedPolygon = polygon.map((point) => normalizePoint(point, !hasImageRooms));
    const shouldRepair = (
      room.polygon_source === "cody_wall_enclosure"
      && room.confirmed !== true
    );
    const repairedPolygon = shouldRepair
      ? repairLoadedRoomPolygon(normalizedPolygon)
      : normalizedPolygon;
    const geometryRepaired = roomPolygonsDiffer(repairedPolygon, normalizedPolygon);
    if (geometryRepaired) repairedRoomCount += 1;
    const normalizedRoom = normalizeIconInferredRoomReview(room, repairedPolygon, index);
    return {
      ...normalizedRoom,
      id: room.id || room.room_id || `room-${index + 1}`,
      label: normalizedRoom.label || normalizedRoom.name || `空間 ${index + 1}`,
      type: normalizedRoom.type || normalizedRoom.room_type || "default",
      confirmed: geometryRepaired ? false : normalizedRoom.confirmed === true,
      geometry_repaired: geometryRepaired || room.geometry_repaired === true,
      polygon_cm: repairedPolygon,
    };
  }).filter((room) => room.polygon_cm.length >= 3);
  if (!state.rooms.length) {
    state.rooms = [{
      id: "room-1",
      label: "未命名空間",
      type: "default",
      confidence: 0.4,
      confirmed: false,
      polygon_cm: [{ x: 0, y: 0 }, { x: widthCm, y: 0 }, { x: widthCm, y: depthCm }, { x: 0, y: depthCm }],
    }];
  }
  const normalizeSegment = (item, index, kind, centered = false) => ({
    ...canonicalStructure(item),
    id: item.id || `${kind}-${index + 1}`,
    start: normalizePoint(item.start, centered),
    end: normalizePoint(item.end, centered),
  });
  const imageStructures = {
    walls: state.analysis?.walls || [],
    doors: state.analysis?.doors || [],
    windows: state.analysis?.windows || [],
    beams: state.analysis?.beams || [],
    columns: state.analysis?.columns || [],
  };
  const floorplanStructures = {
    walls: floorplan.wall_segments || floorplan.plan_segments || [],
    doors: floorplan.door_segments || [],
    windows: floorplan.window_segments || [],
    beams: floorplan.beam_segments || [],
    columns: floorplan.columns || [],
  };
  const sourceStructures = hasImageRooms ? imageStructures : floorplanStructures;
  state.structures = {
    walls: sourceStructures.walls.map((item, index) =>
      normalizeSegment(item, index, "wall", !hasImageRooms)),
    doors: sourceStructures.doors.map((item, index) =>
      normalizeSegment(item, index, "door", !hasImageRooms)),
    windows: sourceStructures.windows.map((item, index) =>
      normalizeSegment(item, index, "window", !hasImageRooms)),
    beams: sourceStructures.beams.map((item, index) =>
      normalizeSegment(item, index, "beam", !hasImageRooms)),
    columns: sourceStructures.columns.map((item, index) => ({
      ...canonicalStructure(item),
      id: item.id || `column-${index + 1}`,
      center: normalizePoint(item.center, !hasImageRooms),
    })),
  };
  state.rooms = applyCanonicalRoomLabels(preparedAutoRoomLabels(state.rooms, state.structures.walls));
  normalizeWallDemolitionCandidates();
  repairLoadedStructureWallCollisions();
  const normalizedDoors = dedupeDoorCandidates(state.structures.doors);
  state.structures.doors = normalizedDoors.doors;
  state.doorNormalizationRemoved = normalizedDoors.removed;
  const normalizedWindows = dedupeWindowCandidates(state.structures.windows);
  state.structures.windows = normalizedWindows.windows;
  state.windowNormalizationRemoved = normalizedWindows.removed;
  state.selectedRoomId = state.rooms[0]?.id || null;
  renderRooms();
  renderSpaceOverlay();
  renderStructureCounts();
  if (repairedRoomCount > 0) {
    element.spaceError.textContent =
      `已修復 ${repairedRoomCount} 個房間的異常岔出節點，請重新確認房間輪廓。`;
  }
}

function roomPolygonSvg(room) {
  return room.polygon_cm.map(cmToPixel).map((point) => `${point.x},${point.y}`).join(" ");
}

function roomReviewHint(room) {
  const reasons = Array.isArray(room.room_review_reasons) ? room.room_review_reasons : [];
  if (reasons.includes("room_icon_function_conflict")) {
    return "偵測到不同功能圖示，可能是多個空間，請切割或改名後再確認。";
  }
  if (reasons.includes("django_zone_storage_candidate")) {
    return "依家具圖示與分區推測可能為儲藏室，仍需人工確認。";
  }
  if (reasons.includes("django_zone_bed_anchor")) {
    return "依床的位置推測為臥室，仍需人工確認。";
  }
  if (reasons.includes("room_icon_area_implausible")) {
    return "圖示與房間面積不合理，請檢查是否需要切割空間。";
  }
  if (reasons.includes("room_icon_low_confidence")) {
    return "圖示辨識信心不足，請確認空間名稱。";
  }
  return "";
}

function updateShowAllRoomsButton() {
  const button = $("#show-all-rooms");
  if (!button) return;
  const hasMultipleRooms = state.rooms.length > 1;
  button.disabled = !hasMultipleRooms;
  button.setAttribute(
    "aria-disabled",
    hasMultipleRooms ? "false" : "true",
  );
  button.title = hasMultipleRooms
    ? "顯示所有已框選的空間"
    : "目前只有一個空間，沒有其他框選可顯示";
}

function renderRooms() {
  element.roomList.innerHTML = state.rooms.map((room) => {
    const dimensions = roomDimensions(room);
    const active = room.id === state.selectedRoomId;
    const merging = state.mergeRoomIds.includes(room.id);
    const reviewHint = roomReviewHint(room);
    return `
      <article class="rp-room-item ${active ? "is-active" : ""} ${merging ? "is-merge-selected" : ""}">
        <button type="button" data-room-id="${escapeHtml(room.id)}" class="rp-room-select">
          <strong>${escapeHtml(room.label)}</strong>
          <span>${dimensions.areaM2.toFixed(2)} m²</span>
          <small>${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm</small>
          <small>${room.confirmed ? "已確認" : `信心 ${(Number(room.confidence || room.polygon_confidence || 0.7) * 100).toFixed(0)}%`}</small>
          ${reviewHint ? `<small class="rp-room-review-hint">${escapeHtml(reviewHint)}</small>` : ""}
        </button>
        <button type="button" data-confirm-room="${escapeHtml(room.id)}"
          class="rp-room-confirm ${room.confirmed ? "is-confirmed" : ""}">
          ${room.confirmed ? "已確認" : "確認"}
        </button>
        <button type="button" data-delete-room="${escapeHtml(room.id)}" class="rp-room-delete danger-action">
          刪除
        </button>
      </article>
    `;
  }).join("");
  const confirmedCount = state.rooms.filter((room) => room.confirmed).length;
  element.roomConfirmationProgress.textContent =
    `已確認 ${confirmedCount} / ${state.rooms.length} 個房間`;
  const confirmAllRoomsButton = $("#confirm-all-rooms");
  if (confirmAllRoomsButton) {
    const allConfirmed = state.rooms.length > 0 && confirmedCount === state.rooms.length;
    confirmAllRoomsButton.disabled = !state.rooms.length || allConfirmed;
    confirmAllRoomsButton.textContent = allConfirmed
      ? "全部房間已確認"
      : "一鍵確認全部房間";
  }
  updateShowAllRoomsButton();
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (room) {
    const dimensions = roomDimensions(room);
    element.roomEditor.hidden = false;
    element.roomName.value = roomNameOptionFor(room).id;
    element.roomArea.textContent =
      `系統依目前框選計算：${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm，${dimensions.areaM2.toFixed(2)} m²`;
  } else {
    element.roomEditor.hidden = true;
  }
}

function confirmRoom(roomId) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  room.confirmed = true;
  room.confidence = 1;
  room.source = "manual_confirmation";
  room.label = room.label.replace(/\s*（待確認）\s*/g, "").trim() || "未命名空間";
  state.selectedRoomId = room.id;
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
  setStatus(`已確認「${room.label}」；請繼續確認其他房間。`);
}

function confirmAllRooms() {
  if (!state.rooms.length) return;
  state.rooms.forEach((room) => {
    room.confirmed = true;
    room.confidence = 1;
    room.source = "manual_confirmation";
    room.label = room.label.replace(/\s*（待確認）\s*/g, "").trim() || "未命名空間";
  });
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
  setStatus(`已一次確認 ${state.rooms.length} 個房間；仍可逐房修改名稱或框選。`);
}

function deleteRoom(roomId = state.selectedRoomId) {
  const roomIndex = state.rooms.findIndex((item) => item.id === roomId);
  if (roomIndex < 0) return;
  if (state.rooms.length <= 1) {
    element.spaceError.textContent = "至少需要保留一個空間，無法刪除最後一個空間。";
    return;
  }
  const room = state.rooms[roomIndex];
  const message = room.confirmed
    ? `「${room.label}」已確認。確定要刪除此空間嗎？`
    : `確定要刪除「${room.label}」嗎？`;
  if (!confirm(message)) return;
  if (room.source === "auto_wall_split_review" || room.source === "django_zone_inference" || room.split_from) {
    state.dismissedAutoRoomIds = [
      ...new Set([
        ...(state.dismissedAutoRoomIds || []),
        room.id,
      ]),
    ];
  }
  state.rooms.splice(roomIndex, 1);
  const nextRoom = state.rooms[Math.min(roomIndex, state.rooms.length - 1)] || state.rooms[0] || null;
  state.selectedRoomId = nextRoom?.id || null;
  state.mergeRoomIds = state.mergeRoomIds.filter((id) => id !== room.id);
  state.roomGeometryMode = null;
  state.splitPoints = [];
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  state.showAllRooms = true;
  element.spaceError.textContent = "";
  updateRoomGeometryControls();
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已刪除，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus(`已刪除「${room.label}」。`);
}

function addMissedRoom() {
  const center = state.selectedRoomId
    ? roomCenter(state.rooms.find((room) => room.id === state.selectedRoomId))
    : planCenterCm();
  const widthCm = 240;
  const depthCm = 240;
  const room = {
    id: `room-manual-${Date.now()}`,
    label: `新增空間 ${state.rooms.length + 1}`,
    type: "default",
    confidence: 0.35,
    confirmed: false,
    manually_added: true,
    polygon_cm: [
      { x: center.x - widthCm / 2, y: center.y - depthCm / 2 },
      { x: center.x + widthCm / 2, y: center.y - depthCm / 2 },
      { x: center.x + widthCm / 2, y: center.y + depthCm / 2 },
      { x: center.x - widthCm / 2, y: center.y + depthCm / 2 },
    ],
  };
  state.rooms.push(room);
  state.selectedRoomId = room.id;
  state.showAllRooms = false;
  invalidateDownstreamFrom(
    "space_confirmation",
    "已新增漏辨識空間；請拖曳節點、命名並重新確認空間與結構。",
  );
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
}

function updateRoomGeometryControls() {
  $$("[data-room-geometry-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.roomGeometryMode === state.roomGeometryMode);
  });
  $("#apply-room-merge").hidden =
    state.roomGeometryMode !== "merge" || state.mergeRoomIds.length !== 2;
  $("#cancel-room-geometry").hidden = !state.roomGeometryMode;
  if (state.roomGeometryMode === "merge") {
    element.roomGeometryGuidance.textContent = state.mergeRoomIds.length === 2
      ? "已選兩個房間。確認左圖範圍後，按「合併所選兩個房間」。"
      : `請在左圖或清單點選兩個相鄰房間，目前已選 ${state.mergeRoomIds.length} 個。`;
  } else if (state.roomGeometryMode === "split") {
    element.roomGeometryGuidance.textContent = state.splitPoints.length === 1
      ? "已設定切割線起點，請在左圖點第二點。"
      : "請先選取要切割的房間，再在左圖點兩點定義切割線。";
  } else {
    element.roomGeometryGuidance.textContent =
      "先逐一確認右側房間；需要時可合併或以兩點切割。";
  }
}

function setRoomGeometryMode(mode) {
  state.roomGeometryMode = state.roomGeometryMode === mode ? null : mode;
  state.mergeRoomIds = [];
  state.splitPoints = [];
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  state.showAllRooms = true;
  element.spaceError.textContent = "";
  updateRoomNodeControls();
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
}

function updateRoomNodeControls() {
  $$("[data-room-node-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.roomNodeMode === state.roomNodeMode);
  });
  $("#apply-node-merge").hidden =
    state.roomNodeMode !== "merge" || state.selectedRoomNodeIndices.length !== 2;
  $("#cancel-node-edit").hidden = !state.roomNodeMode;
  if (state.roomNodeMode === "merge") {
    element.roomNodeGuidance.textContent = state.selectedRoomNodeIndices.length === 2
      ? "已選兩點。確認是相鄰節點後，按「合併所選兩個節點」。"
      : `請在左圖點選兩個相鄰紫色節點，目前已選 ${state.selectedRoomNodeIndices.length} 個。`;
  } else if (state.roomNodeMode === "split") {
    element.roomNodeGuidance.textContent = "請直接點房間框的邊線，系統會在最近位置新增一個可拖曳節點。";
  } else {
    element.roomNodeGuidance.textContent = "需要微調輪廓時，可合併相鄰節點或在邊線新增節點。";
  }
}

function setRoomNodeMode(mode) {
  state.roomNodeMode = state.roomNodeMode === mode ? null : mode;
  state.selectedRoomNodeIndices = [];
  state.roomGeometryMode = null;
  state.mergeRoomIds = [];
  state.splitPoints = [];
  state.showAllRooms = false;
  element.spaceError.textContent = "";
  updateRoomGeometryControls();
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
}

function mergeSelectedRoomNodes() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room || state.selectedRoomNodeIndices.length !== 2) return;
  const polygon = room.polygon_cm;
  const [first, second] = [...state.selectedRoomNodeIndices].sort((a, b) => a - b);
  const adjacent = second - first === 1 || (first === 0 && second === polygon.length - 1);
  if (!adjacent) {
    element.spaceError.textContent = "只能合併同一條邊上的兩個相鄰節點，請重新選擇。";
    return;
  }
  if (polygon.length <= 3) {
    element.spaceError.textContent = "房間至少需要三個節點，這兩點不能再合併。";
    return;
  }
  const midpoint = {
    x: (polygon[first].x + polygon[second].x) / 2,
    y: (polygon[first].y + polygon[second].y) / 2,
  };
  const mergedPolygon = polygon.map((point) => ({ ...point }));
  if (first === 0 && second === polygon.length - 1) {
    mergedPolygon[0] = midpoint;
    mergedPolygon.pop();
  } else {
    mergedPolygon[first] = midpoint;
    mergedPolygon.splice(second, 1);
  }
  if (polygonArea(mergedPolygon) < 5_000) {
    element.spaceError.textContent = "合併後房間面積會小於 0.5 m²，請保留這兩個節點。";
    return;
  }
  room.polygon_cm = mergedPolygon;
  room.confirmed = false;
  room.source = "manual_node_merge";
  element.spaceError.textContent = "";
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間節點已合併，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("兩個相鄰節點已合併；房間尺寸與面積已重新計算。");
}

function nearestPointOnRoomEdge(point, polygon) {
  let closest = null;
  polygon.forEach((start, edgeIndex) => {
    const end = polygon[(edgeIndex + 1) % polygon.length];
    const projected = nearestPointOnSegment(point, start, end);
    const distance = Math.hypot(point.x - projected.x, point.y - projected.y);
    if (!closest || distance < closest.distance) {
      closest = { edgeIndex, projected, distance };
    }
  });
  return closest;
}

function insertRoomNodeAt(point) {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const closest = nearestPointOnRoomEdge(point, room.polygon_cm);
  if (!closest || closest.distance > 35) {
    element.spaceError.textContent = "請點在房間框邊線附近，系統才可新增節點。";
    return;
  }
  const start = room.polygon_cm[closest.edgeIndex];
  const end = room.polygon_cm[(closest.edgeIndex + 1) % room.polygon_cm.length];
  if (
    Math.hypot(closest.projected.x - start.x, closest.projected.y - start.y) < 8
    || Math.hypot(closest.projected.x - end.x, closest.projected.y - end.y) < 8
  ) {
    element.spaceError.textContent = "新節點離既有節點太近，請改點邊線中間的位置。";
    return;
  }
  room.polygon_cm.splice(closest.edgeIndex + 1, 0, closest.projected);
  room.confirmed = false;
  room.source = "manual_node_split";
  element.spaceError.textContent = "";
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間邊線已新增節點，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("已在房間邊線新增節點；可直接拖曳紫色節點調整輪廓。");
}

function mergeSelectedRooms() {
  if (state.mergeRoomIds.length !== 2) {
    element.spaceError.textContent = "請先選取兩個相鄰房間。";
    return;
  }
  const selected = state.mergeRoomIds
    .map((roomId) => state.rooms.find((room) => room.id === roomId))
    .filter(Boolean);
  if (selected.length !== 2) return;
  const polygon = convexHull(selected.flatMap((room) => room.polygon_cm));
  const originalArea = selected.reduce((sum, room) => sum + polygonArea(room.polygon_cm), 0);
  const mergedArea = polygonArea(polygon);
  if (polygon.length < 3 || mergedArea > originalArea * 1.2) {
    element.spaceError.textContent =
      "這兩個房間不相鄰，或合併後會涵蓋過多其他區域，請重新選擇。";
    return;
  }
  const cleanLabel = (label) => label.replace(/\s*（待確認）\s*/g, "").trim();
  const merged = {
    id: `room-merged-${Date.now()}`,
    label: `${cleanLabel(selected[0].label)}＋${cleanLabel(selected[1].label)}（待確認）`,
    type: selected[0].type === selected[1].type ? selected[0].type : "default",
    confidence: Math.min(...selected.map((room) => Number(room.confidence || 0.5))),
    confirmed: false,
    source: "manual_merge",
    merged_from: selected.map((room) => room.id),
    polygon_cm: polygon,
  };
  const selectedIds = new Set(state.mergeRoomIds);
  state.rooms = [...state.rooms.filter((room) => !selectedIds.has(room.id)), merged];
  state.selectedRoomId = merged.id;
  state.roomGeometryMode = null;
  state.mergeRoomIds = [];
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已合併，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("已合併兩個房間；請修改名稱並按房間確認鍵。");
}

function splitSelectedRoom(start, end) {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room || Math.hypot(end.x - start.x, end.y - start.y) < 10) {
    element.spaceError.textContent = "切割線太短，請重新點兩個不同位置。";
    state.splitPoints = [];
    updateRoomGeometryControls();
    return;
  }
  const firstPolygon = clipPolygonByLine(room.polygon_cm, start, end, true);
  const secondPolygon = clipPolygonByLine(room.polygon_cm, start, end, false);
  if (
    firstPolygon.length < 3
    || secondPolygon.length < 3
    || polygonArea(firstPolygon) < 5_000
    || polygonArea(secondPolygon) < 5_000
  ) {
    element.spaceError.textContent =
      "切割線沒有完整穿過房間，或切出的空間小於 0.5 m²，請重新畫線。";
    state.splitPoints = [];
    updateRoomGeometryControls();
    renderSpaceOverlay();
    return;
  }
  const baseLabel = room.label.replace(/\s*（待確認）\s*/g, "").trim();
  const roomIndex = state.rooms.findIndex((item) => item.id === room.id);
  const splitRooms = [firstPolygon, secondPolygon].map((polygon, index) => ({
    ...room,
    id: `room-split-${Date.now()}-${index + 1}`,
    label: `${baseLabel} ${index === 0 ? "A" : "B"}（待確認）`,
    confidence: Math.min(Number(room.confidence || 0.5), 0.7),
    confirmed: false,
    source: "manual_split",
    split_from: room.id,
    polygon_cm: polygon,
  }));
  state.rooms.splice(roomIndex, 1, ...splitRooms);
  state.selectedRoomId = splitRooms[0].id;
  state.roomGeometryMode = null;
  state.splitPoints = [];
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已切割，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("房間已切成兩個範圍；請逐一命名並確認。");
}

function renderSpaceOverlay() {
  if (!element.spaceImage.naturalWidth || !state.rooms.length) return;
  const visibleRooms = state.spaceMode === "rooms"
    ? (state.showAllRooms
      ? state.rooms
      : state.rooms.filter((room) => room.id === state.selectedRoomId))
    : [];
  const polygons = visibleRooms.map((room) => {
    const active = room.id === state.selectedRoomId || state.mergeRoomIds.includes(room.id);
    const dimensions = roomDimensions(room);
    const center = cmToPixel(roomCenter(room));
    const nodes = active
      ? room.polygon_cm.map((point, index) => {
        const pixel = cmToPixel(point);
        const selected = state.roomNodeMode === "merge"
          && state.selectedRoomNodeIndices.includes(index);
        return `<circle data-room-point="${index}" cx="${pixel.x}" cy="${pixel.y}" r="${selected ? 12 : 9}"
          fill="${selected ? "#fff1e9" : "#fff"}" stroke="${selected ? "#bd5c36" : "#7755a6"}"
          stroke-width="${selected ? 7 : 5}"/>`;
      }).join("")
      : "";
    return `
      <g data-room-shape="${escapeHtml(room.id)}">
        <polygon points="${roomPolygonSvg(room)}" fill="${active ? "rgba(47,111,135,.20)" : "rgba(36,107,85,.10)"}"
          stroke="${active ? "#2f6f87" : "#246b55"}" stroke-width="${active ? 5 : 3}"/>
        <text x="${center.x}" y="${center.y - 8}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="8" paint-order="stroke"
          font-size="24" font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>
        <text x="${center.x}" y="${center.y + 22}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="7" paint-order="stroke"
          font-size="18" font-weight="700" pointer-events="none">${dimensions.areaM2.toFixed(2)} m²</text>
        ${nodes}
      </g>
    `;
  }).join("");
  const structures = state.spaceMode === "structure" ? renderStructureSvg() : "";
  const splitGuide = state.roomGeometryMode === "split" && state.splitPoints[0]
    ? (() => {
      const point = cmToPixel(state.splitPoints[0]);
      return `<circle cx="${point.x}" cy="${point.y}" r="10" fill="#fff" stroke="#bd5c36" stroke-width="5"/>`;
    })()
    : "";
  element.spaceOverlay.innerHTML = `${polygons}${structures}${splitGuide}`;
  renderSchemeComparison();
}

function segmentSvg(item, color, width = 5, dash = "") {
  const start = cmToPixel(item.start);
  const end = cmToPixel(item.end);
  return `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="${color}" stroke-width="${width}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
}

const structureCollections = {
  door: "doors",
  window: "windows",
  wall: "walls",
  beam: "beams",
  column: "columns",
};

function attachedOpeningUpdates(oldWall, newWall, openingSnapshots) {
  const oldDx = oldWall.end.x - oldWall.start.x;
  const oldDy = oldWall.end.y - oldWall.start.y;
  const oldLengthSquared = oldDx * oldDx + oldDy * oldDy || 1;
  const newDx = newWall.end.x - newWall.start.x;
  const newDy = newWall.end.y - newWall.start.y;
  const newLength = Math.hypot(newDx, newDy);
  if (newLength < 1) return null;
  const axis = { x: newDx / newLength, y: newDy / newLength };
  const updates = [];
  for (const { collection, item } of openingSnapshots) {
    const center = {
      x: (item.start.x + item.end.x) / 2,
      y: (item.start.y + item.end.y) / 2,
    };
    const t = Math.max(0, Math.min(1, (
      (center.x - oldWall.start.x) * oldDx
      + (center.y - oldWall.start.y) * oldDy
    ) / oldLengthSquared));
    const width = Math.max(
      30,
      Number(item.width_cm || Math.hypot(
        item.end.x - item.start.x,
        item.end.y - item.start.y,
      )),
    );
    const margin = 5;
    if (newLength < width + margin * 2) return null;
    const halfT = width / newLength / 2;
    const clampedT = Math.max(halfT + margin / newLength, Math.min(
      1 - halfT - margin / newLength,
      t,
    ));
    const nextCenter = {
      x: newWall.start.x + newDx * clampedT,
      y: newWall.start.y + newDy * clampedT,
    };
    updates.push({
      collection,
      id: item.id,
      start: {
        x: nextCenter.x - axis.x * width / 2,
        y: nextCenter.y - axis.y * width / 2,
      },
      end: {
        x: nextCenter.x + axis.x * width / 2,
        y: nextCenter.y + axis.y * width / 2,
      },
    });
  }
  return updates;
}

function applyAttachedOpeningUpdates(updates) {
  (updates || []).forEach((update) => {
    const opening = state.structures[update.collection].find(
      (item) => item.id === update.id,
    );
    if (!opening) return;
    opening.start = update.start;
    opening.end = update.end;
    opening.confirmed = false;
    delete opening.swing_end;
  });
}

const structureSectionMeta = {
  door: {
    label: "門",
    listTitle: "門候選清單",
    addLabel: "＋ 新增門",
    unit: "扇門",
    guidance: "新增門後會磁吸最近牆；可拖曳、調整寬度、門向與鉸鏈端，再逐扇確認。",
  },
  window: {
    label: "窗",
    listTitle: "窗候選清單",
    addLabel: "＋ 新增窗",
    unit: "扇窗",
    guidance: "新增窗後會磁吸最近牆；可拖曳並調整窗寬、窗高與窗台離地高度，再逐扇確認。左圖只有帶編號的藍線是窗候選；未帶編號的原圖細線可能是門扇符號。",
  },
  wall: {
    label: "牆",
    listTitle: "牆體清單",
    addLabel: "＋ 畫牆",
    unit: "面牆",
    guidance: "畫牆後可拖曳端點或在選取牆段後調整尺寸。牆體會作為後續門、窗、家具配置的固定結構基準。",
  },
  beam: {
    label: "樑",
    listTitle: "樑體清單",
    addLabel: "＋ 畫樑",
    unit: "道樑",
    guidance: "按住左圖拖曳樑的起點至終點，放開即完成；端點會自動對齊水平或垂直並磁吸附近結構。",
  },
  column: {
    label: "柱",
    listTitle: "柱體清單",
    addLabel: "＋ 新增柱",
    unit: "根柱",
    guidance: "點左圖放置柱；可拖曳並調整柱寬與柱深，柱高會跟隨樓高。",
  },
};

function wallBoundaryContext() {
  const floorplan = confirmedFloorplanEditor();
  return {
    width_cm: Number(floorplan.width_cm || 0),
    depth_cm: Number(floorplan.depth_cm || 0),
  };
}

function wallBoundary(item) {
  const floorplan = wallBoundaryContext();
  return wallBoundarySide(item, {
    widthCm: floorplan.width_cm,
    depthCm: floorplan.depth_cm,
  });
}

function normalizeWallDemolitionCandidates() {
  state.structures.walls.forEach((wall) => {
    wall.demolition_candidate = false;
  });
  return 0;
}

function wallPreviewMarkup({ simulateDemolition = false } = {}) {
  return state.structures.walls.map((wall) => {
    const candidate = wall.demolition_candidate === true;
    const thickness = Math.max(7, Number(wall.thickness_cm || 12));
    if (simulateDemolition && candidate) {
      return `<line x1="${Number(wall.start?.x || 0)}" y1="${Number(wall.start?.y || 0)}"
        x2="${Number(wall.end?.x || 0)}" y2="${Number(wall.end?.y || 0)}"
        stroke="#c54c4c" stroke-width="3" stroke-dasharray="18 12"
        vector-effect="non-scaling-stroke" opacity=".45"/>`;
    }
    return `<line x1="${Number(wall.start?.x || 0)}" y1="${Number(wall.start?.y || 0)}"
      x2="${Number(wall.end?.x || 0)}" y2="${Number(wall.end?.y || 0)}"
      stroke="${candidate ? "#c54c4c" : "#343434"}" stroke-width="${thickness}"
      ${candidate ? 'stroke-dasharray="18 12"' : ""}
      stroke-linecap="square" vector-effect="non-scaling-stroke"/>`;
  }).join("");
}

function schemeStructureMarkup(schemeId) {
  const structures = structuresForScheme(state.structures, schemeId);
  const lines = (items, color, width) => items.map((item) => {
    if (!item.start || !item.end) return "";
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const uncertain = schemeId === "B"
      && item.host_wall_relation_uncertain === true
      && state.structures.walls.some(
        (wall) => wall.id === item.host_wall_id && wall.demolition_candidate === true,
      );
    return `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="${uncertain ? "#ef9f19" : color}" stroke-width="${width}"
      ${uncertain ? 'stroke-dasharray="12 8"' : ""}
      vector-effect="non-scaling-stroke">
      ${uncertain ? "<title>此門窗與可拆牆的關聯不確定，方案 B 暫時保留。</title>" : ""}
    </line>`;
  }).join("");
  return [
    lines(structures.walls, "#343434", 7),
    lines(structures.doors, "#bd5c36", 5),
    lines(structures.windows, "#2f8ba1", 5),
    lines(structures.beams, "#6b4d8a", 5),
  ].join("");
}

function schemeFurnitureForRoom(schemeId, roomId) {
  const resolvedSchemeId = String(
    schemeId
      || state.designSchemes.room_selections?.[String(roomId)]
      || state.designSchemes.active_scheme_id
      || "A",
  ).toUpperCase();
  const scheme = state.designSchemes.schemes[resolvedSchemeId] || state.designSchemes.schemes.A;
  return (scheme?.furniture || []).filter((item) => String(item.roomId || item.room_id || "") === String(roomId));
}

function roomSchemeSelectionRequired() {
  return Boolean(state.designSchemes.schemes.B) && state.rooms.length > 0;
}

function promptRoomSchemeSelection() {
  if (!state.rooms.length) return;
  openRoomSchemeSelectionDialog();
  void ensureRoomSchemeAlternative();
}

async function ensureRoomSchemeAlternative() {
  if (roomSchemeAlternativeInFlight) return roomSchemeAlternativeInFlight;
  const schemeA = state.designSchemes.schemes.A;
  const schemeB = ensureSchemeB(state.designSchemes, { reason: "step_six_room_comparison" });
  if (schemeB.stale || (schemeB.furniture || []).length || !(schemeA?.furniture || []).length) {
    if (element.roomSchemeDialog?.open) renderRoomSchemeSelectionDialog();
    return schemeB;
  }
  roomSchemeAlternativeInFlight = (async () => {
    try {
      const alternativeFurniture = await relayoutFurnitureForScheme(schemeA.furniture, "B");
      if (!alternativeFurniture?.length) {
        schemeB.stale = true;
        schemeB.staleReason = "無法產生不同的家具擺設。";
        return schemeB;
      }
      schemeB.furniture = alternativeFurniture;
      schemeB.stale = false;
      schemeB.staleReason = "";
      roomSchemePreviewCache.clear();
      scheduleSave("layout_2d");
      return schemeB;
    } catch (error) {
      schemeB.stale = true;
      schemeB.staleReason = `無法產生替代擺設：${errorMessage(error)}`;
      return schemeB;
    } finally {
      roomSchemeAlternativeInFlight = null;
      if (element.roomSchemeDialog?.open) renderRoomSchemeSelectionDialog();
    }
  })();
  return roomSchemeAlternativeInFlight;
}

function configurationSnapshot() {
  return {
    schema_version: 1,
    created_at: new Date().toISOString(),
    scene_version: currentSceneVersion(),
    room_selections: { ...(state.designSchemes.room_selections || {}) },
    rooms: state.rooms.map((room) => ({
      room_id: room.id,
      room_label: room.label,
      selected_scheme_id: selectedSchemeForRoom(state.designSchemes, room.id),
      furniture_count: schemeFurnitureForRoom(
        selectedSchemeForRoom(state.designSchemes, room.id),
        room.id,
      ).length,
    })),
  };
}

function composeSelectedRoomFurniture() {
  const baselineFurniture = state.designSchemes.schemes.A?.furniture || [];
  const composite = [];
  const usedFurnitureIds = new Set();
  const roomIds = new Set(state.rooms.map((room) => String(room.id)));
  state.rooms.forEach((room) => {
    const schemeId = selectedSchemeForRoom(state.designSchemes, room.id);
    schemeFurnitureForRoom(schemeId, room.id).forEach((item) => {
      const key = String(item.id || item.furniture_id || "");
      if (!key || usedFurnitureIds.has(key)) return;
      usedFurnitureIds.add(key);
      composite.push(JSON.parse(JSON.stringify(item)));
    });
  });
  baselineFurniture.forEach((item) => {
    const roomId = String(item.roomId || item.room_id || "");
    const key = String(item.id || item.furniture_id || "");
    if (roomIds.has(roomId) || !key || usedFurnitureIds.has(key)) return;
    usedFurnitureIds.add(key);
    composite.push(JSON.parse(JSON.stringify(item)));
  });
  return composite;
}

function renderRoomSchemeGate() {
  if (!element.roomSchemeGateStatus || !element.openRoomSchemeSelection) return;
  if (!roomSchemeSelectionRequired()) {
    element.roomSchemeGateStatus.textContent = "目前只有方案 A；可直接進行家具微調。";
    element.openRoomSchemeSelection.hidden = true;
    return;
  }
  const autoSelected = applyUnavailableRoomSchemeDefaults();
  const selectedCount = state.rooms.filter((room) => (
    ["A", "B"].includes(state.designSchemes.room_selections?.[String(room.id)])
  )).length;
  const ready = allRoomsHaveSchemeSelections(state.designSchemes, state.rooms);
  element.roomSchemeGateStatus.textContent = ready
    ? `已完成 ${selectedCount}/${state.rooms.length} 間房的方案選擇；${autoSelected ? "沒有完整方案 B 的房間已自動採用方案 A。" : ""}現在可以微調。`
    : `已選 ${selectedCount}/${state.rooms.length} 間。請先完成所有房間的 A/B 選擇，才可微調。`;
  element.openRoomSchemeSelection.hidden = false;
  element.openRoomSchemeSelection.textContent = ready ? "檢視逐房方案選擇" : "逐房比較並選擇方案";
}

function roomHasComparableSchemeB(room) {
  const schemeB = state.designSchemes.schemes.B;
  return Boolean(
    room
    && schemeB
    && !schemeB.stale
    && schemeFurnitureForRoom("B", room.id).length,
  );
}

function roomSchemePreviewKey(schemeId, roomId) {
  return `${schemeId}:${roomId}`;
}

function roomSchemeFurnitureLabel(item = {}) {
  return replacementFurnitureName({
    ...item,
    name_zh_raw: item.label || item.name_zh_raw,
    normalized_type: item.type || item.normalized_type,
  });
}

function roomSchemePlanMarkup(room, furniture = []) {
  const polygon = room?.polygon_cm || [];
  if (polygon.length < 3) {
    return '<span class="rp-render-placeholder">沒有可用的房間平面資料</span>';
  }
  const center = planCenterCm();
  const points = polygon.map((point) => ({ x: Number(point.x || 0), y: Number(point.y || 0) }));
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const padding = 38;
  const minX = Math.min(...xs) - padding;
  const maxX = Math.max(...xs) + padding;
  const minY = Math.min(...ys) - padding;
  const maxY = Math.max(...ys) + padding;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const project = (point) => ({
    x: ((point.x - minX) / width) * 440,
    y: 300 - ((point.y - minY) / height) * 300,
  });
  const roomPath = points.map((point, index) => {
    const projected = project(point);
    return `${index ? 'L' : 'M'} ${projected.x.toFixed(1)} ${projected.y.toFixed(1)}`;
  }).join(' ') + ' Z';
  const furnitureMarkup = furniture.slice(0, 12).map((item) => {
    const location = project({ x: center.x + Number(item.xCm || 0), y: center.y + Number(item.yCm || 0) });
    const itemWidth = Math.max(22, (Number(item.widthCm || 60) / width) * 440);
    const itemHeight = Math.max(18, (Number(item.depthCm || 60) / height) * 300);
    const label = roomSchemeFurnitureLabel(item);
    return `<g class="rp-room-scheme-furniture" transform="translate(${location.x.toFixed(1)} ${location.y.toFixed(1)}) rotate(${-Number(item.rotationDeg || 0)})">
      <rect x="${(-itemWidth / 2).toFixed(1)}" y="${(-itemHeight / 2).toFixed(1)}" width="${itemWidth.toFixed(1)}" height="${itemHeight.toFixed(1)}" rx="3" />
      ${itemWidth > 62 && itemHeight > 30 ? `<text text-anchor="middle" dominant-baseline="middle">${escapeHtml(label.slice(0, 8))}</text>` : ''}
    </g>`;
  }).join('');
  return `<svg class="rp-room-scheme-plan" viewBox="0 0 440 300" role="img" aria-label="${escapeHtml(room.label || '房間')}的家具平面配置">
    <path class="rp-room-scheme-outline" d="${roomPath}" />
    ${furnitureMarkup || '<text class="rp-room-scheme-empty" x="200" y="130" text-anchor="middle">尚未配置家具</text>'}
  </svg>`;
}

function roomSchemeFurnitureLegend(furniture = []) {
  if (!furniture.length) return '<p class="rp-room-scheme-legend-empty">尚未配置家具</p>';
  return `<ul class="rp-room-scheme-legend">${furniture.slice(0, 6).map((item) => (
    `<li>${escapeHtml(roomSchemeFurnitureLabel(item))}</li>`
  )).join('')}</ul>`;
}

function buildRoomSchemePreviewScene(baseScene, room, furniture = []) {
  if (!baseScene?.floorplan || !room) return null;
  const bounds = replacementRoomBounds(room);
  if (!bounds) return null;
  const offset = { x: bounds.centerX, z: bounds.centerZ };
  const scene = JSON.parse(JSON.stringify(baseScene));
  const floorplan = scene.floorplan || {};
  [
    'wall_segments',
    'door_segments',
    'door_openings',
    'window_segments',
    'beam_segments',
    'column_segments',
  ].forEach((key) => {
    if (!Array.isArray(floorplan[key])) return;
    floorplan[key] = floorplan[key]
      .filter((segment) => segmentOverlapsBounds(segment, bounds))
      .map((segment) => shiftSceneSegment(segment, offset));
  });
  if (Array.isArray(floorplan.wall_polys)) {
    floorplan.wall_polys = floorplan.wall_polys
      .filter((region) => (region.exterior || region.polygon_cm || []).some((point) => {
        const coordinates = scenePointCoordinates(point);
        return (
          coordinates.x >= bounds.minX - 32
          && coordinates.x <= bounds.maxX + 32
          && coordinates.z >= bounds.minZ - 32
          && coordinates.z <= bounds.maxZ + 32
        );
      }))
      .map((region) => shiftFloorplanRegion(region, offset));
  }
  if (Array.isArray(floorplan.columns)) {
    floorplan.columns = floorplan.columns
      .filter((column) => segmentOverlapsBounds({ start: column.center, end: column.center }, bounds))
      .map((column) => ({ ...column, center: shiftScenePoint(column.center, offset) }));
  }
  floorplan.room_regions = (floorplan.room_regions || [])
    .filter((region) => String(region.room_id || region.id || '') === String(room.id))
    .map((region) => shiftFloorplanRegion(region, offset));
  if (Array.isArray(floorplan.rooms)) {
    floorplan.rooms = floorplan.rooms
      .filter((region) => String(region.room_id || region.id || '') === String(room.id))
      .map((region) => shiftFloorplanRegion(region, offset));
  }
  floorplan.width_cm = Math.max(240, (bounds.maxX - bounds.minX) + 120);
  floorplan.depth_cm = Math.max(240, (bounds.maxZ - bounds.minZ) + 120);
  scene.floorplan = floorplan;
  scene.room_surface_assignments = (scene.room_surface_assignments || [])
    .filter((assignment) => String(assignment.room_id || '') === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  scene.surface_overrides = (scene.surface_overrides || [])
    .filter((assignment) => String(assignment.room_id || '') === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  const sourceObjects = scene.scene_objects || [];
  scene.scene_objects = furniture.map((item) => {
    const existing = sourceObjects.find((sceneObject) => sceneObjectMatchesLayoutFurniture(sceneObject, item)) || {};
    const fallbackSize = {
      width: Number(item.widthCm || item.size_cm?.width || 60),
      depth: Number(item.depthCm || item.size_cm?.depth || 60),
      height: Number(item.heightCm || item.size_cm?.height || 80),
    };
    return {
      ...existing,
      furniture_id: item.id,
      catalog_furniture_id: item.catalogFurnitureId || item.catalog_furniture_id || existing.catalog_furniture_id,
      name_zh_raw: item.label || existing.name_zh_raw,
      normalized_type: item.type || existing.normalized_type,
      model_url: item.model_url || existing.model_url,
      size_cm: {
        width: Number(existing.size_cm?.width || fallbackSize.width),
        depth: Number(existing.size_cm?.depth || fallbackSize.depth),
        height: Number(existing.size_cm?.height || fallbackSize.height),
      },
      position_cm: shiftScenePoint({ x: Number(item.xCm || 0), z: Number(item.yCm || 0) }, offset),
      rotation_y_deg: Number(item.rotationDeg || 0),
      placement_room_id: room.id,
      position_locked: true,
      placement_failed: item.placementFailed === true,
    };
  });
  return { scene, bounds };
}

function applyUnavailableRoomSchemeDefaults() {
  if (!roomSchemeSelectionRequired()) return false;
  let changed = false;
  state.rooms.forEach((room) => {
    if (roomHasComparableSchemeB(room)) return;
    if (state.designSchemes.room_selections?.[String(room.id)] === "A") return;
    changed = selectSchemeForRoom(state.designSchemes, room.id, "A") || changed;
  });
  return changed;
}

function openRoomSchemeSelectionDialog() {
  if (!element.roomSchemeDialog) return;
  if (applyUnavailableRoomSchemeDefaults()) scheduleSave("white_model_3d");
  state.selectedRoomSchemeId = state.selectedRoomSchemeId || state.rooms.find((room) => (
    !state.designSchemes.room_selections?.[String(room.id)]
  ))?.id || state.rooms[0]?.id || null;
  renderRoomSchemeSelectionDialog();
  if (typeof element.roomSchemeDialog.showModal === "function") element.roomSchemeDialog.showModal();
  else element.roomSchemeDialog.setAttribute("open", "");
  void ensureRoomScheme3dPreviews();
}

function closeRoomSchemeSelectionDialog() {
  if (!element.roomSchemeDialog) return;
  if (typeof element.roomSchemeDialog.close === "function") element.roomSchemeDialog.close();
  else element.roomSchemeDialog.removeAttribute("open");
}

async function openRoomScheme3dPreview(schemeId) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId));
  if (!room) {
    setStatus("找不到要預覽的房間。", "warning");
    return;
  }
  const resolvedSchemeId = String(
    schemeId
      || state.designSchemes.room_selections?.[String(room.id)]
      || state.designSchemes.active_scheme_id
      || "A",
  ).toUpperCase();
  const scheme = state.designSchemes.schemes[resolvedSchemeId] || state.designSchemes.schemes.A;
  const baseScene = scheme?.sceneData || state.designSchemes.schemes.A?.sceneData || state.sceneData;
  const previewScene = buildRoomSchemePreviewScene(
    baseScene,
    room,
    schemeFurnitureForRoom(resolvedSchemeId, room.id),
  );
  if (!room || !previewScene) {
    setStatus("無法建立此房間的 3D 預覽。", "warning");
    return;
  }
  element.roomScheme3dPreviewTitle.textContent = `${room.label || "房間"}・方案 ${resolvedSchemeId}`;
  setTaskDialogOpen(element.roomScheme3dPreviewDialog, true);
  try {
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await roomSchemePreviewViewer.loadScene(previewScene.scene);
    roomSchemePreviewViewer.setViewMode("orbit");
    roomSchemePreviewViewer.setCameraPreset("inside");
    element.roomScheme3dPreviewStatus.textContent = "拖曳可旋轉，滾輪可縮放。";
  } catch (error) {
    element.roomScheme3dPreviewStatus.textContent = `3D 預覽載入失敗：${errorMessage(error)}`;
  }
}

function setTaskDialogOpen(dialog, isOpen) {
  if (!dialog) return;
  if (isOpen) {
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  } else if (typeof dialog.close === "function") {
    dialog.close();
  } else {
    dialog.removeAttribute("open");
  }
}

function restoreStepSixTaskControls() {
  const transfers = [
    ["#style-pack-tabs", "#style-pack-dialog-origin"],
    ["#style-pack-grid", "#style-pack-dialog-origin"],
    ["#surface-editor", "#surface-editor-origin"],
    ["#lighting-editor", "#lighting-editor-origin"],
  ];
  transfers.forEach(([sourceSelector, originSelector]) => {
    const source = $(sourceSelector);
    const origin = $(originSelector);
    if (source && origin && source.parentElement !== origin) origin.appendChild(source);
  });
}

function openStepSixTaskDialog(kind) {
  if (!state.sceneData?.scene_objects) {
    setStatus("請先完成 2D 與 3D 配置，才能調整材質與燈光。", "warning");
    return;
  }
  goTo("realistic_3d");
  const isSurface = kind === "surface";
  const dialog = isSurface ? element.surfaceAdjustmentDialog : element.lightingAdjustmentDialog;
  const target = isSurface ? element.surfaceAdjustmentContent : element.lightingAdjustmentContent;
  if (!dialog || !target) return;
  restoreStepSixTaskControls();
  if (isSurface) {
    [element.styleTabs, element.styleGrid, $("#surface-editor")].forEach((node) => node && target.appendChild(node));
  } else {
    const lightingEditor = $("#lighting-editor");
    if (lightingEditor) target.appendChild(lightingEditor);
  }
  setTaskDialogOpen(dialog, true);
}

function closeStepSixTaskDialog(dialog) {
  restoreStepSixTaskControls();
  setTaskDialogOpen(dialog, false);
  renderStyleControls();
  scheduleSave("realistic_3d");
}

function renderRoomSchemeSelectionDialog() {
  applyUnavailableRoomSchemeDefaults();
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId)) || state.rooms[0];
  if (!room || !element.roomSchemeList) return;
  const selected = selectedSchemeForRoom(state.designSchemes, room.id);
  element.roomSchemeList.innerHTML = state.rooms.map((item) => {
    const selectedScheme = state.designSchemes.room_selections?.[String(item.id)];
    const isAutoSelected = selectedScheme === "A" && !roomHasComparableSchemeB(item);
    return `<button type="button" data-room-scheme-room="${escapeHtml(item.id)}"
      class="${String(item.id) === String(room.id) ? "is-active" : ""}">
      <strong>${escapeHtml(item.label || "未命名空間")}</strong>
      <small>${isAutoSelected ? "方案 A（無完整 B 可比較）" : (selectedScheme ? `已選方案 ${selectedScheme}` : "尚未選擇")}</small>
    </button>`;
  }).join("");
  const hasComparableB = roomHasComparableSchemeB(room);
  element.roomSchemeStatus.textContent = hasComparableB
    ? `${room.label || "此房間"}：比較 2D 家具配置與 3D 場景後，選擇要帶入最終方案的版本。`
    : `${room.label || "此房間"}：目前沒有完整的方案 B 3D 場景可比較，已先採用方案 A；進入配置後仍可挑選、替換與鎖定家具。`;
  element.roomSchemeChoiceGrid.innerHTML = ["A", ...(hasComparableB ? ["B"] : [])].map((schemeId) => {
    const scheme = state.designSchemes.schemes[schemeId];
    const furniture = schemeFurnitureForRoom(schemeId, room.id);
    const unavailable = !scheme || scheme.stale;
    const preview = roomSchemePreviewCache.get(roomSchemePreviewKey(schemeId, room.id));
    return `<article class="rp-scheme-choice-card ${selected === schemeId ? "is-selected" : ""}">
      <header><strong>方案 ${schemeId}</strong><span>${unavailable ? "需要重新配置" : `${furniture.length} 件家具`}</span></header>
      <div class="rp-scheme-preview-grid">
        <section class="rp-scheme-preview">
          <h4>2D 家具配置</h4>
          ${roomSchemePlanMarkup(room, furniture)}
          ${roomSchemeFurnitureLegend(furniture)}
        </section>
        <button type="button" class="rp-scheme-preview rp-scheme-preview--interactive" data-room-scheme-preview-3d="${schemeId}" aria-label="查看方案 ${schemeId} 的可旋轉 3D 預覽">
          <h4>3D 房間預覽 <span>點擊旋轉查看</span></h4>
          ${preview
            ? `<img src="${escapeHtml(preview)}" alt="方案 ${schemeId} 的 ${escapeHtml(room.label || "房間")} 3D 預覽" />`
            : `<span class="rp-render-placeholder">正在建立此房間的 3D 預覽…</span>`}
        </button>
      </div>
      <p class="rp-task-dialog-note">${unavailable ? (escapeHtml(scheme?.staleReason || "方案尚未可用") ) : `本房共 ${furniture.length} 件家具`}</p>
      <button type="button" class="${selected === schemeId ? "secondary-action" : "primary-action"}" data-room-scheme-choice="${schemeId}" ${unavailable ? "disabled" : ""}>${selected === schemeId ? "已選此方案" : `選擇方案 ${schemeId}`}</button>
    </article>`;
  }).join("");
  const missing = state.rooms.filter((item) => !state.designSchemes.room_selections?.[String(item.id)]);
  const ready = allRoomsHaveSchemeSelections(state.designSchemes, state.rooms);
  element.roomSchemeComplete.disabled = !ready;
  element.roomSchemeWarning.hidden = ready;
  element.roomSchemeWarning.textContent = ready
    ? ""
    : `尚有 ${missing.map((item) => item.label || "未命名空間").join("、")} 未選擇方案；家具微調仍會保持鎖定。`;
}

async function ensureRoomScheme3dPreviews() {
  if (roomSchemePreviewInFlight || !element.roomSchemeDialog?.open) return roomSchemePreviewInFlight;
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId)) || state.rooms[0];
  const baseScene = state.designSchemes.schemes.A?.sceneData || state.sceneData;
  if (!room || !baseScene?.scene_objects) return null;
  const candidates = ["A", "B"].filter((schemeId) => (
    state.designSchemes.schemes[schemeId]
    && !state.designSchemes.schemes[schemeId].stale
    && schemeFurnitureForRoom(schemeId, room.id).length
    && !roomSchemePreviewCache.has(roomSchemePreviewKey(schemeId, room.id))
  ));
  if (!candidates.length) return null;
  roomSchemePreviewInFlight = (async () => {
    const activeScene = state.sceneData;
    const activeCamera = whiteViewer.getCameraState();
    try {
      for (const schemeId of candidates) {
        const previewScene = buildRoomSchemePreviewScene(
          baseScene,
          room,
          schemeFurnitureForRoom(schemeId, room.id),
        );
        if (!previewScene) continue;
        await whiteViewer.loadScene(previewScene.scene);
        whiteViewer.setCameraState({
          camera_type: "perspective",
          view_mode: "orbit",
          position_cm: [100, 160, 140],
          target_cm: [0, 55, 0],
          up: [0, 1, 0],
          fov_deg: 58,
          zoom: 1,
        });
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        roomSchemePreviewCache.set(roomSchemePreviewKey(schemeId, room.id), whiteViewer.capturePng());
      }
    } catch (error) {
      setStatus(`無法建立候選 3D 預覽：${errorMessage(error)}`, "warning");
    } finally {
      if (activeScene?.scene_objects) {
        await whiteViewer.loadScene(activeScene);
        whiteViewer.setCameraState(activeCamera);
      }
      roomSchemePreviewInFlight = null;
      if (element.roomSchemeDialog?.open) renderRoomSchemeSelectionDialog();
    }
  })();
  return roomSchemePreviewInFlight;
}

function chooseRoomScheme(schemeId) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId));
  if (!room || !selectSchemeForRoom(state.designSchemes, room.id, schemeId)) return;
  state.designSchemes.configuration_snapshot = null;
  renderRoomSchemeGate();
  renderRoomSchemeSelectionDialog();
  scheduleSave("white_model_3d");
}

async function completeRoomSchemeSelection() {
  applyUnavailableRoomSchemeDefaults();
  if (!allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) return;
  const compositeFurniture = composeSelectedRoomFurniture();
  if (!compositeFurniture.length && state.rooms.length) {
    element.roomSchemeWarning.hidden = false;
    element.roomSchemeWarning.textContent = "無法組合逐房方案：選定方案沒有可用家具資料。請重新產生 A/B 配置後再試。";
    return;
  }
  const schemeA = state.designSchemes.schemes.A;
  const originalFurniture = JSON.parse(JSON.stringify(schemeA.furniture || []));
  const originalScene = state.sceneData ? JSON.parse(JSON.stringify(state.sceneData)) : null;
  state.designSchemes.active_scheme_id = "A";
  state.furniture2d = compositeFurniture;
  state.sceneData = null;
  schemeA.furniture = JSON.parse(JSON.stringify(compositeFurniture));
  schemeA.sceneData = null;
  schemeA.stale = false;
  schemeA.staleReason = "";
  element.roomSchemeComplete.disabled = true;
  element.roomSchemeComplete.textContent = "正在合成並驗證最終配置…";
  try {
    await confirmLayout2d({ allowPendingFurniture: true });
    if (!state.sceneData?.scene_objects) {
      throw new Error("configuration_scene_generation_failed");
    }
    state.designSchemes.configuration_snapshot = configurationSnapshot();
    renderRoomSchemeGate();
    closeRoomSchemeSelectionDialog();
    scheduleSave("white_model_3d");
    setStatus("所有房間方案已合成為唯一配置，並已重新驗證 2D 與 3D 場景。", "success");
  } catch (error) {
    schemeA.furniture = originalFurniture;
    schemeA.sceneData = originalScene;
    state.furniture2d = originalFurniture;
    state.sceneData = originalScene;
    element.roomSchemeWarning.hidden = false;
    element.roomSchemeWarning.textContent = `無法合成最終配置：${errorMessage(error)}`;
    element.roomSchemeComplete.disabled = false;
    element.roomSchemeComplete.textContent = "完成選擇並開始微調";
  }
}

function renderSchemeControls() {
  const hasB = Boolean(state.designSchemes.schemes.B);
  $$("[data-design-scheme]").forEach((button) => {
    const schemeId = button.dataset.designScheme;
    button.hidden = schemeId === "B" && !hasB;
    button.classList.toggle("is-active", schemeId === activeSchemeId());
    button.setAttribute("aria-selected", String(schemeId === activeSchemeId()));
  });
  if (element.layoutSchemeStatus) {
    const scheme = activeScheme();
    element.layoutSchemeStatus.textContent = scheme?.stale
      ? `方案 ${activeSchemeId()} 的結構已變更，請依問卷重新配置`
      : `目前編輯方案 ${activeSchemeId()}`;
  }
  if (element.lockedSchemeLabel) {
    element.lockedSchemeLabel.textContent = state.designSchemes.locked_scheme_id
      ? `已鎖定方案 ${state.designSchemes.locked_scheme_id}`
      : "尚未鎖定方案";
  }
  renderRoomSchemeGate();
}

function renderSchemeComparison() {
  if (!element.schemeCompare) return;
  // 第 4 步只確認唯一結構基準；家具方案比較留在第 6 步。
  const show = false;
  element.schemeCompare.hidden = !show;
  if (!show || !element.spaceImage?.src) return;
  element.schemeAImage.src = element.spaceImage.src;
  element.schemeBImage.src = element.spaceImage.src;
  const { imageWidth, imageHeight } = planGeometry();
  const aspectRatio = `${Math.max(1, element.spaceImage.naturalWidth || imageWidth)}
    / ${Math.max(1, element.spaceImage.naturalHeight || imageHeight)}`;
  [element.schemeAImage, element.schemeBImage].forEach((image) => {
    image.closest(".rp-scheme-plan-stage").style.aspectRatio = aspectRatio;
  });
  [element.schemeAOverlay, element.schemeBOverlay].forEach((overlay) => {
    overlay.setAttribute("viewBox", `0 0 ${imageWidth} ${imageHeight}`);
    overlay.setAttribute("preserveAspectRatio", "none");
  });
  element.schemeAOverlay.innerHTML = schemeStructureMarkup("A");
  element.schemeBOverlay.innerHTML = schemeStructureMarkup("B");
}

function applyWallDemolitionType(wallId, demolitionCandidate) {
  const wall = state.structures.walls.find((item) => item.id === wallId);
  if (!wall) return;
  if (demolitionCandidate) {
    setStatus("牆體已在第 4 步作為全案基準鎖定；方案 A、B 僅比較家具配置。", "warning");
    return;
  }
  const floorplan = wallBoundaryContext();
  if (
    demolitionCandidate
    && !canMarkWallForDemolition(wall, floorplan)
  ) {
    wall.demolition_candidate = false;
    const message = "最外圍牆不可標記為可拆牆。若圖面邊界有誤，請先修正牆的位置。";
    element.spaceError.textContent = message;
    setStatus(message, "error");
    renderStructureReviewList();
    return;
  }
  const changed = wall.demolition_candidate !== demolitionCandidate;
  wall.demolition_candidate = demolitionCandidate;
  if (demolitionCandidate) ensureRenovationScheme("demolished_wall");
  wall.confirmed = false;
  wall.estimated = false;
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  if (!changed) return;
  invalidateRenovationScheme(
    "方案 B 的可拆牆已修改；問卷與方案 A 保留，方案 B 家具需重新計算。",
  );
  scheduleSave("space_confirmation");
  setStatus(demolitionCandidate
    ? "已標記為可拆牆候選；這只是格局模擬，施工前仍須由專業人員確認。"
    : "已改回一般牆，格局預覽會保留此牆。");
}

function structureGroup(item, kind, markup) {
  const active = state.selectedStructure?.id === item.id
    && state.selectedStructure?.kind === kind;
  return `<g data-structure-id="${escapeHtml(item.id)}" data-structure-kind="${kind}"
    class="${active ? "is-selected-structure" : ""}">${markup}</g>`;
}

function beamBandSvg(item, { selected = false, draft = false } = {}) {
  const start = cmToPixel(item.start);
  const end = cmToPixel(item.end);
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy);
  if (length < 50) return "";
  const halfWidth = Math.max(7, Number(item.thickness_cm || 30) / planGeometry().scale / 2);
  const nx = -dy / length * halfWidth;
  const ny = dx / length * halfWidth;
  const points = [
    `${start.x + nx},${start.y + ny}`,
    `${end.x + nx},${end.y + ny}`,
    `${end.x - nx},${end.y - ny}`,
    `${start.x - nx},${start.y - ny}`,
  ].join(" ");
  const color = selected || draft ? "#ef9f19" : "#6b4d8a";
  return `<polygon points="${points}" fill="${color}" fill-opacity="${draft ? 0.28 : 0.42}"
    stroke="${color}" stroke-width="${selected ? 5 : 3}" ${draft ? 'stroke-dasharray="14 9"' : ""}
    style="cursor:${draft ? "crosshair" : "move"}"/>`;
}

function beamSnapCandidates(excludeId = null) {
  return [
    ...state.structures.walls
      .filter((item) => item.id !== excludeId)
      .flatMap((item) => [item.start, item.end]),
    ...state.structures.beams
      .filter((item) => item.id !== excludeId)
      .flatMap((item) => [item.start, item.end]),
    ...state.structures.columns.map((item) => item.center),
  ].filter(Boolean);
}

function wallEndpointSnapCandidates(excludeId = null) {
  return [
    ...beamSnapCandidates(excludeId),
    ...state.structures.doors.flatMap((item) => [item.start, item.end]),
    ...state.structures.windows.flatMap((item) => [item.start, item.end]),
  ].filter(Boolean);
}

function structureNumberMarkerSvg(kind, index, point, {
  selected = false,
  moveHandle = "",
} = {}) {
  const colors = {
    wall: "#343434",
    door: "#bd5c36",
    window: "#2f8ba1",
    beam: "#6b4d8a",
    column: "#8e3e23",
  };
  return `<g data-structure-number-kind="${kind}" data-structure-number="${index + 1}"
    ${moveHandle} style="cursor:${selected ? "grab" : "pointer"}">
    <circle cx="${point.x}" cy="${point.y}" r="18" fill="#fff"
      stroke="${selected ? "#ef9f19" : colors[kind]}" stroke-width="6"/>
    <text x="${point.x}" y="${point.y + 7}" text-anchor="middle"
      fill="${colors[kind]}" font-size="20" font-weight="800"
      pointer-events="none">${index + 1}</text>
    <title>${structureSectionMeta[kind].label} ${index + 1}${selected ? "，拖曳可移動" : ""}</title>
  </g>`;
}

function renderStructureSvg() {
  const walls = state.activeStructureKind === "wall" ? state.structures.walls.map((item, index) => {
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    const selected = state.selectedStructure?.kind === "wall"
      && state.selectedStructure?.id === item.id;
    const demolitionCandidate = item.demolition_candidate === true;
    return structureGroup(
      item,
      "wall",
      `${segmentSvg(
        item,
        demolitionCandidate ? "#c54c4c" : "#343434",
        Math.max(4, Number(item.thickness_cm || 12) / planGeometry().scale),
        demolitionCandidate ? 'stroke-dasharray="14 9"' : "",
      )}
      ${structureNumberMarkerSvg("wall", index, midpoint, { selected })}
      ${selected ? `<circle data-wall-handle="start" cx="${start.x}" cy="${start.y}" r="17"
        fill="#fff" stroke="#bd5c36" stroke-width="6" style="cursor:crosshair"><title>拖曳微調牆起點</title></circle>
      <circle data-wall-handle="end" cx="${end.x}" cy="${end.y}" r="17"
        fill="#fff" stroke="#ef9f19" stroke-width="6" style="cursor:crosshair"><title>拖曳微調牆終點</title></circle>` : ""}`,
    );
  }).join("") : "";
  const windows = state.activeStructureKind === "window" ? state.structures.windows.map((item, index) => {
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const selected = state.selectedStructure?.kind === "window"
      && state.selectedStructure?.id === item.id;
    const midpoint = {
      x: (start.x + end.x) / 2,
      y: (start.y + end.y) / 2,
    };
    const dragTarget = `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="transparent" stroke-width="34" pointer-events="stroke"/>`;
    const marker = structureNumberMarkerSvg("window", index, midpoint, {
      selected,
      moveHandle: selected ? 'data-opening-move-handle="true"' : "",
    }).replace(`data-structure-number="${index + 1}"`, `data-structure-number="${index + 1}" data-window-number="${index + 1}"`);
    const handles = selected
      ? `<circle data-opening-handle="start" cx="${start.x}" cy="${start.y}" r="18"
          fill="#fff" stroke="#2f8ba1" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整窗寬</title>
        </circle>
        <circle data-opening-handle="end" cx="${end.x}" cy="${end.y}" r="18"
          fill="#fff" stroke="#7755a6" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整窗寬</title>
        </circle>`
      : "";
    return structureGroup(
      item,
      "window",
      `${dragTarget}${segmentSvg(item, "#2f8ba1", 7)}${marker}${handles}`,
    );
  }).join("") : "";
  const doors = state.activeStructureKind === "door" ? state.structures.doors.map((item, index) => {
    const line = segmentSvg(item, "#bd5c36", 7);
    const hinge = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const radius = Math.hypot(end.x - hinge.x, end.y - hinge.y);
    const swingEnd = item.swing_end ? cmToPixel(item.swing_end) : {
      x: hinge.x + (end.y - hinge.y),
      y: hinge.y - (end.x - hinge.x),
    };
    const swingCross = (end.x - hinge.x) * (swingEnd.y - hinge.y)
      - (end.y - hinge.y) * (swingEnd.x - hinge.x);
    const sweep = item.swing_end
      ? (swingCross >= 0 ? 1 : 0)
      : (item.opening_direction === "left" ? 0 : 1);
    const selected = state.selectedStructure?.kind === "door"
      && state.selectedStructure?.id === item.id;
    const midpoint = {
      x: (hinge.x + end.x) / 2,
      y: (hinge.y + end.y) / 2,
    };
    const dragTarget = `<line x1="${hinge.x}" y1="${hinge.y}" x2="${end.x}" y2="${end.y}"
      stroke="transparent" stroke-width="34" pointer-events="stroke"/>`;
    const marker = structureNumberMarkerSvg("door", index, midpoint, {
      selected,
      moveHandle: selected ? 'data-door-move-handle="true"' : "",
    });
    const handles = selected
      ? `<circle data-door-handle="start" cx="${hinge.x}" cy="${hinge.y}" r="18"
          fill="#fff" stroke="#bd5c36" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整門寬</title>
        </circle>
        <circle data-door-handle="end" cx="${end.x}" cy="${end.y}" r="18"
          fill="#fff" stroke="#7755a6" stroke-width="7" style="cursor:ew-resize">
          <title>拖曳此端調整門寬</title>
        </circle>`
      : "";
    // Blue is the Step 4 open leaf. Green is the Step 6 closed leaf, both sharing one hinge.
    const openLeafLine = `<line x1="${hinge.x}" y1="${hinge.y}" x2="${end.x}" y2="${end.y}"
      stroke="#1598dc" stroke-width="5" stroke-linecap="round" pointer-events="none"/>`;
    const closedLeafLine = item.swing_end ? `<line x1="${hinge.x}" y1="${hinge.y}" x2="${swingEnd.x}" y2="${swingEnd.y}"
      stroke="#258b45" stroke-width="5" stroke-linecap="round" pointer-events="none"/>` : "";
    return structureGroup(
      item,
      "door",
      `${dragTarget}${line}${openLeafLine}${closedLeafLine}<path d="M ${end.x} ${end.y} A ${radius} ${radius} 0 0 ${sweep} ${swingEnd.x} ${swingEnd.y}" fill="none" stroke="#bd5c36" stroke-width="3"/>${marker}${handles}`,
    );
  }).join("") : "";
  const beams = state.activeStructureKind === "beam" ? state.structures.beams.map((item, index) => {
    const displayItem = structureSizeDraft?.kind === "beam"
      && structureSizeDraft.id === item.id
      ? structureSizeDraft.item
      : item;
    const start = cmToPixel(displayItem.start);
    const end = cmToPixel(displayItem.end);
    const midpoint = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
    const selected = state.selectedStructure?.kind === "beam"
      && state.selectedStructure?.id === item.id;
    return structureGroup(
      item,
      "beam",
      `${beamBandSvg(displayItem, { selected })}
      ${structureNumberMarkerSvg("beam", index, midpoint, { selected })}
      ${selected ? `<circle data-beam-handle="start" cx="${start.x}" cy="${start.y}" r="17"
        fill="#fff" stroke="#6b4d8a" stroke-width="6" style="cursor:crosshair"/>
      <circle data-beam-handle="end" cx="${end.x}" cy="${end.y}" r="17"
        fill="#fff" stroke="#ef9f19" stroke-width="6" style="cursor:crosshair"/>` : ""}`,
    );
  }).join("") : "";
  const columns = state.activeStructureKind === "column" ? state.structures.columns.map((item, index) => {
    const displayItem = structureSizeDraft?.kind === "column"
      && structureSizeDraft.id === item.id
      ? structureSizeDraft.item
      : item;
    const pixel = cmToPixel(displayItem.center);
    const width = Number(displayItem.size_cm || 35) / planGeometry().scale;
    const depth = Number(displayItem.depth_cm || displayItem.size_cm || 35) / planGeometry().scale;
    const selected = state.selectedStructure?.kind === "column"
      && state.selectedStructure?.id === item.id;
    return structureGroup(
      item,
      "column",
      `<rect x="${pixel.x - width / 2}" y="${pixel.y - depth / 2}" width="${width}" height="${depth}"
        transform="rotate(${Number(displayItem.rotation_deg || 0)} ${pixel.x} ${pixel.y})"
        fill="rgba(189,92,54,.32)" stroke="#8e3e23" stroke-width="4"/>
      ${structureNumberMarkerSvg("column", index, pixel, { selected })}`,
    );
  }).join("") : "";
  const beamDraft = state.activeStructureKind === "beam" && structureCreateDrag
    ? beamBandSvg({
      start: structureCreateDrag.geometry.start,
      end: structureCreateDrag.geometry.end,
      thickness_cm: structureCreateDrag.thicknessCm,
    }, { selected: true, draft: true })
    : "";
  const wallDraft = state.activeStructureKind === "wall" && state.structureTool === "wall"
    && state.structureLineStart
    ? (() => {
      const start = cmToPixel(state.structureLineStart);
      const previewEnd = state.structureLinePreviewEnd
        ? cmToPixel(state.structureLinePreviewEnd)
        : null;
      const previewLine = previewEnd
        ? `<line x1="${start.x}" y1="${start.y}" x2="${previewEnd.x}" y2="${previewEnd.y}"
            stroke="#bd5c36" stroke-width="8" stroke-linecap="round" stroke-dasharray="14 10"/>`
        : "";
      return `<g class="rp-wall-draft" pointer-events="none">
        ${previewLine}
        <circle cx="${start.x}" cy="${start.y}" r="12" fill="#fff" stroke="#bd5c36" stroke-width="6"/>
        <circle cx="${start.x}" cy="${start.y}" r="4" fill="#bd5c36"/>
        <text x="${start.x + 16}" y="${start.y - 14}" fill="#8e3e23" font-size="16" font-weight="700">起點已設定，請點終點</text>
      </g>`;
    })()
    : "";
  return `<g>${walls}${windows}${doors}${beams}${columns}${beamDraft}${wallDraft}</g>`;
}

function snapPoint(point, candidates = [], toleranceCm = 16) {
  const nearest = candidates
    .filter(Boolean)
    .map((candidate) => ({
      candidate,
      distance: Math.hypot(point.x - candidate.x, point.y - candidate.y),
    }))
    .sort((left, right) => left.distance - right.distance)[0];
  return nearest && nearest.distance <= toleranceCm
    ? { x: nearest.candidate.x, y: nearest.candidate.y }
    : point;
}

let draggedRoomPointIndex = null;
let structureDrag = null;
let wallResizeDrag = null;
let doorResizeDrag = null;
let beamResizeDrag = null;
let structureCreateDrag = null;
let structureSizeDraft = null;
let lastStructureEditorKey = null;

function cancelStructureInteraction() {
  state.structureTool = null;
  state.structureLineStart = null;
  state.structureLinePreviewEnd = null;
  state.pendingWallDeleteId = null;
  state.selectedStructure = null;
  structureDrag = null;
  wallResizeDrag = null;
  doorResizeDrag = null;
  beamResizeDrag = null;
  structureCreateDrag = null;
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  setStatus("已取消目前操作與結構選取。");
}

function structureWallCollision(item, kind) {
  if (!["beam", "column"].includes(kind)) return null;
  return findStructureWallCollision(item, kind, state.structures.walls);
}

function structurePreferredPoint() {
  const floorplan = confirmedFloorplanEditor();
  return {
    x: Number(floorplan.width_cm || 0) / 2,
    y: Number(floorplan.depth_cm || 0) / 2,
  };
}

function resolveStructureSizeDraft(item, kind) {
  if (!["beam", "column"].includes(kind)) {
    return { item, resolved: true, moved: false, totalShiftCm: 0 };
  }
  return resolveStructureWallCollisions(item, kind, state.structures.walls, {
    preferredPoint: structurePreferredPoint(),
    maxAutoShiftCm: 75,
  });
}

function repairLoadedStructureWallCollisions() {
  const preferredPoint = structurePreferredPoint();
  let moved = 0;
  let unresolved = 0;
  for (const [kind, collection] of [["beam", "beams"], ["column", "columns"]]) {
    state.structures[collection] = (state.structures[collection] || []).map((item) => {
      const normalizedItem = kind === "column"
        ? { ...item, height_cm: confirmedRoomHeightCm() }
        : item;
      const result = resolveStructureWallCollisions(
        normalizedItem,
        kind,
        state.structures.walls,
        { preferredPoint, maxAutoShiftCm: 75 },
      );
      if (result.resolved && result.moved) {
        moved += 1;
        return {
          ...result.item,
          confirmed: false,
          estimated: false,
          wall_collision_repaired: true,
        };
      }
      if (!result.resolved) {
        unresolved += 1;
        return { ...normalizedItem, confirmed: false };
      }
      return normalizedItem;
    });
  }
  state.structureCollisionRepairs = { moved, unresolved };
  return state.structureCollisionRepairs;
}

function structureWallCollisionMessage(kind) {
  const label = kind === "beam" ? "樑" : "柱";
  return `樑柱不可穿過牆體；請移動或縮小${label}，也可以貼齊牆面。`;
}

function rejectStructureWallCollision(item, kind) {
  const collision = structureWallCollision(item, kind);
  if (!collision) {
    element.spaceError.textContent = "";
    $("#structure-wall-collision-error").textContent = "";
    return false;
  }
  const message = structureWallCollisionMessage(kind);
  element.spaceError.textContent = message;
  $("#structure-wall-collision-error").textContent = message;
  setStatus(message, "error");
  return true;
}

function finishBeamCreateDrag() {
  if (!structureCreateDrag) return false;
  const draft = structureCreateDrag;
  structureCreateDrag = null;
  if (!draft.geometry.valid) {
    renderSpaceOverlay();
    setStatus("樑長至少需要 25 公分，請重新拖曳起點與終點。", "error");
    return false;
  }
  const item = {
    id: `beam-manual-${Date.now()}`,
    start: draft.geometry.start,
    end: draft.geometry.end,
    thickness_cm: draft.thicknessCm,
    height_cm: draft.heightCm,
    top_cm: Number(state.sceneData?.floorplan?.room_height_cm || 270),
    confirmed: false,
    estimated: true,
    source: "manual",
    scheme_id: "B",
  };
  if (rejectStructureWallCollision(item, "beam")) {
    renderSpaceOverlay();
    return false;
  }
  state.structures.beams.push(item);
  ensureRenovationScheme("added_structure");
  state.selectedStructure = { id: item.id, kind: "beam" };
  state.structureTool = null;
  $$('[data-structure-tool]').forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateRenovationScheme(
    "方案 B 已新增樑；問卷與方案 A 保留，方案 B 家具需重新計算。",
  );
  scheduleSave("space_confirmation");
  setStatus(`已新增樑 ${state.structures.beams.length}，長度 ${Math.round(draft.geometry.lengthCm)} 公分。`);
  return true;
}

function spacePointerDown(event) {
  if (state.spaceMode === "rooms" && state.roomGeometryMode === "split") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    state.splitPoints.push(pixelToCm(point));
    updateRoomGeometryControls();
    renderSpaceOverlay();
    if (state.splitPoints.length === 2) {
      splitSelectedRoom(state.splitPoints[0], state.splitPoints[1]);
    }
    return;
  }
  if (state.spaceMode === "rooms" && state.roomNodeMode === "split") {
    const point = imagePoint(event, element.spaceImage);
    if (point) insertRoomNodeAt(pixelToCm(point));
    return;
  }
  if (
    state.spaceMode === "structure"
    && ["door", "window", "column"].includes(state.structureTool)
  ) {
    const point = imagePoint(event, element.spaceImage);
    if (point) addDroppedStructure(state.structureTool, point);
    return;
  }
  if (state.spaceMode === "structure" && state.structureTool === "beam") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    const meter = pixelToCm(point);
    structureCreateDrag = {
      geometry: beamDragGeometry(meter, meter, beamSnapCandidates()),
      thicknessCm: 30,
      heightCm: 35,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    renderSpaceOverlay();
    setStatus("按住並拖曳到樑的終點；系統會自動對齊水平、垂直並磁吸牆柱端點。");
    return;
  }
  if (state.structureTool === "wall") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    const meter = pixelToCm(point);
    if (!state.structureLineStart) {
      state.structureLineStart = meter;
      state.structureLinePreviewEnd = null;
      renderSpaceOverlay();
      setStatus(`已設定${state.structureTool === "wall" ? "牆" : "樑"}起點，請再點終點。`);
    } else {
      const kind = state.structureTool;
      const collection = kind === "wall" ? "walls" : "beams";
      const item = {
        id: `${kind}-manual-${Date.now()}`,
        start: state.structureLineStart,
        end: meter,
        thickness_cm: kind === "wall" ? 12 : 30,
        height_cm: kind === "wall" ? 270 : 35,
        confirmed: false,
        estimated: true,
        source: "manual",
        scheme_id: "baseline",
        demolition_candidate: false,
      };
      const lengthCm = Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y);
      if (lengthCm < 25) {
        renderSpaceOverlay();
        setStatus("牆長至少需 25 公分。起點已保留，請重新點選終點。", "error");
        return;
      }
      state.structures[collection].push(item);
      ensureRenovationScheme("added_structure");
      state.selectedStructure = { id: item.id, kind };
      state.structureLineStart = null;
      state.structureLinePreviewEnd = null;
      state.structureTool = null;
      $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
      renderSpaceOverlay();
      renderStructureCounts();
      renderStructureReviewList();
      renderSelectedStructureEditor();
      invalidateRenovationScheme(
        "方案 B 已新增結構；問卷與方案 A 保留，方案 B 家具需重新計算。",
      );
      scheduleSave("space_confirmation");
      setStatus(`已新增${structureSectionMeta[kind].label} ${state.structures[collection].length}，可拖曳、調整尺寸、刪除或確認。`);
    }
    return;
  }
  const wallHandle = event.target.closest("[data-wall-handle]");
  if (wallHandle) {
    const structureNode = wallHandle.closest("[data-structure-id]");
    state.selectedStructure = { id: structureNode.dataset.structureId, kind: "wall" };
    wallResizeDrag = {
      handle: wallHandle.dataset.wallHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
      attachedOpenings: JSON.parse(JSON.stringify(attachedOpenings(
        state.structures,
        structureNode.dataset.structureId,
      ))),
      changed: false,
      blocked: false,
    };
    renderSelectedStructureEditor();
    return;
  }
  const beamHandle = event.target.closest("[data-beam-handle]");
  if (beamHandle) {
    const structureNode = beamHandle.closest("[data-structure-id]");
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: "beam",
    };
    beamResizeDrag = {
      handle: beamHandle.dataset.beamHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
      changed: false,
      blocked: false,
    };
    renderStructureReviewList();
    renderSelectedStructureEditor();
    return;
  }
  const openingHandle = event.target.closest("[data-door-handle], [data-opening-handle]");
  if (openingHandle) {
    const structureNode = openingHandle.closest("[data-structure-id]");
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: structureNode.dataset.structureKind,
    };
    doorResizeDrag = {
      handle: openingHandle.dataset.doorHandle || openingHandle.dataset.openingHandle,
      snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
    };
    renderDoorReviewList();
    renderSelectedStructureEditor();
    return;
  }
  const structureNode = event.target.closest("[data-structure-id]");
  if (structureNode) {
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: structureNode.dataset.structureKind,
    };
    const point = imagePoint(event, element.spaceImage);
    if (point) {
      structureDrag = {
        start: pixelToCm(point),
        snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
        attachedOpenings: state.selectedStructure.kind === "wall"
          ? JSON.parse(JSON.stringify(attachedOpenings(
              state.structures,
              state.selectedStructure.id,
            )))
          : [],
        changed: false,
        blocked: false,
      };
    }
    renderSpaceOverlay();
    renderDoorReviewList();
    renderSelectedStructureEditor();
    return;
  }
  if (state.spaceMode === "structure" && !state.structureTool) {
    if (state.selectedStructure) {
      state.selectedStructure = null;
      renderSpaceOverlay();
      renderDoorReviewList();
      renderSelectedStructureEditor();
      setStatus("已取消結構選取。");
    }
    return;
  }
  const node = event.target.closest("[data-room-point]");
  if (node) {
    if (state.roomNodeMode === "merge") {
      const index = Number(node.dataset.roomPoint);
      state.selectedRoomNodeIndices = state.selectedRoomNodeIndices.includes(index)
        ? state.selectedRoomNodeIndices.filter((item) => item !== index)
        : [...state.selectedRoomNodeIndices.slice(-1), index];
      element.spaceError.textContent = "";
      updateRoomNodeControls();
      renderSpaceOverlay();
      return;
    }
    draggedRoomPointIndex = Number(node.dataset.roomPoint);
    return;
  }
  const roomShape = event.target.closest("[data-room-shape]");
  if (roomShape) {
    selectRoom(roomShape.dataset.roomShape);
    return;
  }
}

function spacePointerMove(event) {
  if (state.structureTool === "wall" && state.structureLineStart) {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    state.structureLinePreviewEnd = pixelToCm(point);
    renderSpaceOverlay();
    return;
  }
  if (structureCreateDrag) {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    structureCreateDrag.geometry = beamDragGeometry(
      structureCreateDrag.geometry.start,
      pixelToCm(point),
      beamSnapCandidates(),
    );
    renderSpaceOverlay();
    return;
  }
  if (beamResizeDrag) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const fixed = beamResizeDrag.handle === "start"
      ? beamResizeDrag.snapshot.end
      : beamResizeDrag.snapshot.start;
    const geometry = beamDragGeometry(
      fixed,
      pixelToCm(point),
      beamSnapCandidates(item.id),
    );
    const candidate = {
      ...item,
      start: beamResizeDrag.handle === "start" ? geometry.end : fixed,
      end: beamResizeDrag.handle === "start" ? fixed : geometry.end,
    };
    if (rejectStructureWallCollision(candidate, "beam")) {
      beamResizeDrag.blocked = true;
      return;
    }
    if (beamResizeDrag.handle === "start") {
      item.start = geometry.end;
      item.end = fixed;
    } else {
      item.start = fixed;
      item.end = geometry.end;
    }
    beamResizeDrag.changed = true;
    beamResizeDrag.blocked = false;
    item.confirmed = false;
    renderSpaceOverlay();
    return;
  }
  if (doorResizeDrag) {
    resizeOpeningFromPointer(event);
    return;
  }
  if (wallResizeDrag) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const endpoint = snapPoint(pixelToCm(point), wallEndpointSnapCandidates(item.id), 16);
    const candidate = {
      ...item,
      start: wallResizeDrag.handle === "start" ? endpoint : wallResizeDrag.snapshot.start,
      end: wallResizeDrag.handle === "end" ? endpoint : wallResizeDrag.snapshot.end,
    };
    const lengthCm = Math.hypot(
      candidate.end.x - candidate.start.x,
      candidate.end.y - candidate.start.y,
    );
    if (lengthCm < 25) {
      wallResizeDrag.blocked = true;
      element.spaceError.textContent = "牆長至少需 25 公分。";
      return;
    }
    const attachedUpdates = attachedOpeningUpdates(
      wallResizeDrag.snapshot,
      candidate,
      wallResizeDrag.attachedOpenings,
    );
    if (attachedUpdates == null) {
      wallResizeDrag.blocked = true;
      element.spaceError.textContent = "調整會讓附著的門窗離開牆面或與洞口衝突。";
      return;
    }
    item.start = candidate.start;
    item.end = candidate.end;
    item.confirmed = false;
    applyAttachedOpeningUpdates(attachedUpdates);
    wallResizeDrag.changed = true;
    wallResizeDrag.blocked = false;
    element.spaceError.textContent = "";
    renderSpaceOverlay();
    return;
  }
  if (structureDrag && state.selectedStructure) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const current = pixelToCm(point);
    const dx = current.x - structureDrag.start.x;
    const dy = current.y - structureDrag.start.y;
    if (state.selectedStructure.kind === "column") {
      const candidate = {
        ...item,
        center: {
          x: structureDrag.snapshot.center.x + dx,
          y: structureDrag.snapshot.center.y + dy,
        },
      };
      if (rejectStructureWallCollision(candidate, "column")) {
        structureDrag.blocked = true;
        return;
      }
      item.center = candidate.center;
      structureDrag.changed = true;
      structureDrag.blocked = false;
    } else if (["door", "window"].includes(state.selectedStructure.kind)) {
      const snapshotCenter = {
        x: (structureDrag.snapshot.start.x + structureDrag.snapshot.end.x) / 2,
        y: (structureDrag.snapshot.start.y + structureDrag.snapshot.end.y) / 2,
      };
      item.start = { ...structureDrag.snapshot.start };
      item.end = { ...structureDrag.snapshot.end };
      item.width_cm = Number(
        structureDrag.snapshot.width_cm
        || Math.hypot(
          structureDrag.snapshot.end.x - structureDrag.snapshot.start.x,
          structureDrag.snapshot.end.y - structureDrag.snapshot.start.y,
        ),
      );
      snapOpeningToHostWall(item, {
        x: snapshotCenter.x + dx,
        y: snapshotCenter.y + dy,
      });
      structureDrag.changed = true;
      item.confirmed = false;
    } else {
      const candidate = {
        ...item,
        start: {
          x: structureDrag.snapshot.start.x + dx,
          y: structureDrag.snapshot.start.y + dy,
        },
        end: {
          x: structureDrag.snapshot.end.x + dx,
          y: structureDrag.snapshot.end.y + dy,
        },
      };
      if (state.selectedStructure.kind === "beam"
        && rejectStructureWallCollision(candidate, "beam")) {
        structureDrag.blocked = true;
        return;
      }
      const attachedUpdates = state.selectedStructure.kind === "wall"
        ? attachedOpeningUpdates(
            structureDrag.snapshot,
            candidate,
            structureDrag.attachedOpenings,
          )
        : [];
      if (state.selectedStructure.kind === "wall" && attachedUpdates == null) {
        structureDrag.blocked = true;
        element.spaceError.textContent =
          "牆長不足以容納附著的門窗，已保留修改前尺寸。請先調整或刪除門窗。";
        return;
      }
      item.start = candidate.start;
      item.end = candidate.end;
      applyAttachedOpeningUpdates(attachedUpdates);
      structureDrag.changed = true;
      structureDrag.blocked = false;
    }
    item.confirmed = false;
    renderSpaceOverlay();
    return;
  }
  if (draggedRoomPointIndex == null) return;
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  const point = imagePoint(event, element.spaceImage);
  if (!room || !point) return;
  room.polygon_cm[draggedRoomPointIndex] = pixelToCm(point);
  renderSpaceOverlay();
  renderRooms();
}

function selectedStructureItem() {
  if (!state.selectedStructure) return null;
  const collection = structureCollections[state.selectedStructure.kind];
  return state.structures[collection]?.find(
    (item) => item.id === state.selectedStructure.id,
  ) || null;
}

function selectedStructureIndex() {
  if (!state.selectedStructure) return -1;
  const collection = structureCollections[state.selectedStructure.kind];
  return state.structures[collection]?.findIndex(
    (item) => item.id === state.selectedStructure.id,
  ) ?? -1;
}

function selectedStructurePreviewContext() {
  const floorplan = confirmedFloorplanEditor();
  return {
    walls: state.structures.walls,
    planWidthCm: floorplan.width_cm,
    planDepthCm: floorplan.depth_cm,
    ceilingHeightCm: floorplan.room_height_cm,
  };
}

function renderStructurePreview(item, kind, index, { draft = false } = {}) {
  structurePreview.render(item, kind, index, selectedStructurePreviewContext());
  if (kind === "beam") {
    const lengthCm = Math.hypot(
      Number(item.end?.x || 0) - Number(item.start?.x || 0),
      Number(item.end?.y || 0) - Number(item.start?.y || 0),
    );
    $("#structure-3d-preview-status").textContent =
      `紫色樑位於天花板下方；長 ${Math.round(lengthCm)} cm、寬 ${Math.round(Number(item.thickness_cm || 30))} cm、下垂 ${Math.round(Number(item.height_cm || 35))} cm${draft ? "（尚未套用）" : "。"}`;
    return;
  }
  $("#structure-3d-preview-status").textContent =
    `棕色柱從地板立起；寬 ${Math.round(Number(item.size_cm || 35))} cm、深 ${Math.round(Number(item.depth_cm || item.size_cm || 35))} cm、高 ${Math.round(Number(item.height_cm || 270))} cm${draft ? "（尚未套用）" : "。"}`;
}

function updateStructureDimensionHint(inputId, kind, valueCm, shiftCm = 0) {
  const hint = $("#structure-preview-dimension-hint");
  const definitions = {
    beam: {
      "selected-structure-size-cm": {
        dimension: "width",
        label: "目前調整：樑寬",
        direction: "前後方向",
        axis: "↔",
      },
      "selected-structure-height-cm": {
        dimension: "height",
        label: "目前調整：下垂深度",
        direction: "上下方向",
        axis: "↕",
      },
    },
    column: {
      "selected-structure-size-cm": {
        dimension: "length",
        label: "目前調整：柱寬",
        direction: "左右方向",
        axis: "↔",
      },
      "selected-structure-depth-cm": {
        dimension: "width",
        label: "目前調整：柱深",
        direction: "前後方向",
        axis: "↔",
      },
    },
  };
  const definition = definitions[kind]?.[inputId];
  if (!definition) return;
  hint.hidden = false;
  $("#structure-preview-dimension-axis").textContent = definition.axis;
  $("#structure-preview-dimension-label").textContent = definition.label;
  $("#structure-preview-dimension-value").textContent =
    `${definition.direction} · ${Math.round(valueCm)} cm${shiftCm > 0 ? ` · 避牆位移 ${Math.round(shiftCm)} cm` : ""}`;
  structurePreview.setActiveDimension(definition.dimension);
}

function previewSelectedStructureDraft(event) {
  const item = selectedStructureItem();
  const kind = state.selectedStructure?.kind;
  if (!item || !["beam", "column"].includes(kind)) return;
  const sizeCm = Number($("#selected-structure-size-cm").value);
  const depthCm = Number($("#selected-structure-depth-cm").value);
  const heightCm = kind === "column"
    ? confirmedRoomHeightCm()
    : Number($("#selected-structure-height-cm").value);
  if (!Number.isFinite(sizeCm) || sizeCm <= 0 || !Number.isFinite(heightCm) || heightCm <= 0) {
    return;
  }
  if (kind === "column" && (!Number.isFinite(depthCm) || depthCm <= 0)) return;
  const draft = {
    ...item,
    height_cm: heightCm,
    ...(kind === "beam"
      ? { thickness_cm: sizeCm }
      : { size_cm: sizeCm, depth_cm: depthCm }),
  };
  const resolution = resolveStructureSizeDraft(draft, kind);
  const inputId = event?.target?.id || "selected-structure-size-cm";
  const inputValue = Number(event?.target?.value) || sizeCm;
  if (!resolution.resolved) {
    structureSizeDraft = null;
    $("#structure-wall-collision-error").textContent = structureWallCollisionMessage(kind);
    updateStructureDimensionHint(inputId, kind, inputValue);
    renderSpaceOverlay();
    renderStructurePreview(item, kind, selectedStructureIndex());
    return;
  }
  structureSizeDraft = {
    id: item.id,
    kind,
    item: resolution.item,
  };
  $("#structure-wall-collision-error").textContent = "";
  updateStructureDimensionHint(
    inputId,
    kind,
    inputValue,
    resolution.totalShiftCm,
  );
  renderSpaceOverlay();
  renderStructurePreview(
    resolution.item,
    kind,
    selectedStructureIndex(),
    { draft: true },
  );
}

function renderSelectedStructureEditor() {
  const item = selectedStructureItem();
  element.structureEditor.hidden = !item;
  if (!item) {
    structureSizeDraft = null;
    lastStructureEditorKey = null;
    $("#structure-preview-dimension-hint").hidden = true;
    structurePreview.setActiveDimension(null);
    $("#delete-selected-structure").textContent = "刪除此結構";
    return;
  }
  const editorKey = `${state.selectedStructure.kind}:${item.id}`;
  if (lastStructureEditorKey !== editorKey) {
    state.pendingWallDeleteId = null;
    structureSizeDraft = null;
    lastStructureEditorKey = editorKey;
    $("#structure-preview-dimension-hint").hidden = true;
    structurePreview.setActiveDimension(null);
  }
  const labels = {
    wall: "牆",
    door: "門",
    window: "窗",
    beam: "樑",
    column: "柱",
  };
  const selectedIndex = selectedStructureIndex();
  const isLineWidth = ["door", "window"].includes(state.selectedStructure.kind);
  const isDoor = state.selectedStructure.kind === "door";
  const isWindow = state.selectedStructure.kind === "window";
  const windowType = isWindow ? normalizedWindowType(item.window_type) : WINDOW_TYPES.standard;
  const isFloorToCeilingWindow = windowType === WINDOW_TYPES.floorToCeiling;
  const isBeam = state.selectedStructure.kind === "beam";
  const isColumn = state.selectedStructure.kind === "column";
  const deleteButton = $("#delete-selected-structure");
  deleteButton.textContent = state.selectedStructure.kind === "wall"
    && state.pendingWallDeleteId === item.id
    ? "再次點擊確認刪除牆"
    : "刪除此結構";
  const heightInput = $("#selected-structure-height-cm");
  $("#structure-wall-collision-error").textContent =
    structureWallCollision(item, state.selectedStructure.kind)
      ? structureWallCollisionMessage(state.selectedStructure.kind)
      : "";
  const hasLength = ["wall", "beam"].includes(state.selectedStructure.kind);
  $("#selected-structure-title").textContent =
    `選取${isFloorToCeilingWindow ? "落地窗" : labels[state.selectedStructure.kind] || "結構"} ${selectedIndex + 1}`;
  $("#selected-structure-length-cm").readOnly = isBeam;
  $("#selected-structure-size-label").textContent = isLineWidth
    ? "開口寬度（公分）"
    : isColumn
      ? "柱寬（公分）"
      : isBeam
        ? "樑寬（公分）"
      : "厚度（公分）";
  const length = item.start && item.end
    ? Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y)
    : 0;
  $("#selected-structure-size-cm").value = Math.round(
    Number(
      isLineWidth
        ? item.width_cm || length
        : state.selectedStructure.kind === "column"
          ? item.size_cm
          : item.thickness_cm,
    ),
  );
  heightInput.value = isColumn
    ? String(Math.round(confirmedRoomHeightCm()))
    : String(Math.round(
      Number(item.height_cm || (isWindow ? 120 : isBeam ? 35 : 270)),
    ));
  heightInput.readOnly = isColumn;
  $("#selected-structure-length-field").hidden = !hasLength;
  $("#selected-structure-depth-field").hidden = !isColumn;
  if (hasLength) {
    $("#selected-structure-length-cm").value = Math.round(length);
    $("#selected-structure-length-label").textContent =
      isBeam ? "樑長（公分）" : "牆長（公分）";
  }
  if (isColumn) {
    $("#selected-structure-depth-cm").value =
      Math.round(Number(item.depth_cm || item.size_cm || 35));
  }
  $("#selected-structure-size-cm").min = isColumn ? "10" : "1";
  $("#selected-structure-depth-cm").min = isColumn ? "10" : "1";
  heightInput.min = isColumn ? String(Math.round(confirmedRoomHeightCm())) : "1";
  if (isColumn) {
    const columnLimits = confirmedFloorplanEditor();
    $("#selected-structure-size-cm").max = String(Math.round(columnLimits.width_cm));
    $("#selected-structure-depth-cm").max = String(Math.round(columnLimits.depth_cm));
    heightInput.max = String(Math.round(columnLimits.room_height_cm));
  } else {
    $("#selected-structure-size-cm").removeAttribute("max");
    $("#selected-structure-depth-cm").removeAttribute("max");
    heightInput.removeAttribute("max");
  }
  $("#selected-structure-height-label").textContent =
    isBeam ? "下垂深度（公分）" : isColumn ? "柱高（依樓高，公分）" : "高度（公分）";
  $("#window-type-field").hidden = !isWindow;
  $("#selected-window-type").value = windowType;
  $("#selected-structure-size-field").hidden = isLineWidth;
  $("#opening-width-controls").hidden = !isLineWidth;
  $("#window-sill-height-field").hidden = !isWindow;
  $("#window-type-preview").hidden = !isFloorToCeilingWindow;
  $("#window-sill-height-cm").disabled = isFloorToCeilingWindow;
  if (isWindow) {
    $("#window-sill-height-cm").value = isFloorToCeilingWindow
      ? "0"
      : String(Math.round(Number(item.sill_height_cm ?? 90)));
  }
  $("#apply-structure-size").textContent = isDoor ? "套用高度" : "套用尺寸";
  if (isLineWidth) {
    const widthCm = Math.round(Number(item.width_cm || length || (isDoor ? 90 : 120)));
    $("#opening-width-label").textContent = isDoor ? "門寬" : "窗寬";
    element.openingWidthSlider.value = String(widthCm);
    element.openingWidthValue.textContent = `${widthCm} cm`;
  }
  $("#flip-selected-door").hidden = !isDoor;
  $("#rotate-selected-door-180").hidden = !isDoor;
  $("#lock-selected-door-opening").hidden = !isDoor;
  $("#lock-selected-door-opening").textContent = item.host_wall_confirmed === true
    ? "已鎖定門洞"
    : "鎖定目前門洞";
  const canRotateStructure = ["door", "window", "wall"].includes(state.selectedStructure.kind);
  $("#rotate-selected-structure-left").hidden = !canRotateStructure;
  $("#rotate-selected-structure-right").hidden = !canRotateStructure;
  $("#structure-editor-guidance").textContent = isDoor
    ? "拖曳左圖門弧可沿牆移動；可調整門寬、門高、開門側與鉸鏈端。"
    : isWindow
      ? "拖曳左圖藍色窗線可移動；可調整窗寬、窗高與窗台離地高度。"
      : isBeam
        ? "拖曳左圖樑帶可移動；拖曳兩端圓點可改變長度，並在下方調整樑寬與下垂深度。"
        : isColumn
          ? "左圖調整柱的位置；下方室內 3D 預覽顯示柱從地板到天花板的寬、深與高度。"
      : "可直接在左圖拖曳移動，並在下方調整尺寸。";
  const showStructurePreview = isBeam || isColumn;
  $("#structure-3d-preview-panel").hidden = !showStructurePreview;
  if (showStructurePreview) {
    const index = selectedIndex;
    renderStructurePreview(item, state.selectedStructure.kind, index);
    $("#structure-3d-preview-title").textContent =
      `${labels[state.selectedStructure.kind]} ${index + 1} · 室內 3D 預覽`;
  }
  $("#structure-editor-hint").textContent =
    `修改${labels[state.selectedStructure.kind]}的位置或尺寸後，會回到待確認狀態。`;
}

function structureMeasurement(item, kind) {
  if (kind === "door" || kind === "window") {
    const widthCm = Number(
      item.width_cm
      || Math.hypot(item.end?.x - item.start?.x, item.end?.y - item.start?.y)
      || (kind === "door" ? 90 : 120),
    );
    const heightCm = Number(item.height_cm || (kind === "door" ? 210 : 120));
    const typeLabel = kind === "window"
      && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling
      ? "落地窗 · "
      : "";
    return `${typeLabel}寬 ${Math.round(widthCm)} × 高 ${Math.round(heightCm)} cm`;
  }
  if (kind === "column") {
    return `寬 ${Math.round(Number(item.size_cm || 35))} × 深 ${Math.round(Number(item.depth_cm || item.size_cm || 35))} × 高 ${Math.round(Number(item.height_cm || 270))} cm`;
  }
  const lengthCm = Math.hypot(
    Number(item.end?.x || 0) - Number(item.start?.x || 0),
    Number(item.end?.y || 0) - Number(item.start?.y || 0),
  );
  const widthCm = Number(item.thickness_cm || (kind === "beam" ? 30 : 12));
  const heightCm = Number(item.height_cm || (kind === "beam" ? 35 : 270));
  return `長 ${Math.round(lengthCm)} × ${kind === "beam" ? "寬" : "厚"} ${Math.round(widthCm)} × 高 ${Math.round(heightCm)} cm`;
}

function renderStructureReviewList() {
  if (!element.doorReviewList) return;
  const kind = state.activeStructureKind;
  const meta = structureSectionMeta[kind];
  const collection = state.structures[structureCollections[kind]] || [];
  const confirmedCount = collection.filter((item) => item.confirmed === true).length;
  $("#structure-review-title").textContent = meta.listTitle;
  const reviewGuidance = $("#structure-review-guidance");
  reviewGuidance.textContent = meta.guidance;
  reviewGuidance.hidden = kind === "beam" && state.structureTool !== "beam";
  $("#structure-review-progress").textContent =
    `已確認 ${confirmedCount} / ${collection.length} ${meta.unit}`;
  const confirmAllButton = $("#confirm-all-visible-structures");
  const allConfirmed = collection.length > 0 && confirmedCount === collection.length;
  confirmAllButton.disabled = !collection.length || allConfirmed;
  confirmAllButton.textContent = allConfirmed
    ? `此頁${meta.label}已全部確認`
    : `一鍵確認全部${meta.label}`;
  const addButton = $("#add-active-structure");
  addButton.dataset.structureTool = kind;
  addButton.textContent = meta.addLabel;
  if (!collection.length) {
    element.doorReviewList.innerHTML =
      `<p class="rp-control-hint">尚未辨識到${meta.label}。請按「${meta.addLabel}」，再到左側圖面指定位置。</p>`;
    return;
  }
  element.doorReviewList.innerHTML = collection.map((item, index) => {
    const selected = state.selectedStructure?.kind === kind
      && state.selectedStructure?.id === item.id;
    const windowType = kind === "window"
      ? normalizedWindowType(item.window_type)
      : null;
    const windowTypeToggle = kind === "window"
      ? `<div class="rp-window-type-toggle" role="group" aria-label="窗 ${index + 1} 類型">
          <button type="button" class="${windowType === WINDOW_TYPES.standard ? "is-active" : ""}"
            aria-pressed="${windowType === WINDOW_TYPES.standard}"
            data-window-type="${WINDOW_TYPES.standard}" data-window-id="${escapeHtml(item.id)}">一般窗</button>
          <button type="button" class="${windowType === WINDOW_TYPES.floorToCeiling ? "is-active" : ""}"
            aria-pressed="${windowType === WINDOW_TYPES.floorToCeiling}"
            data-window-type="${WINDOW_TYPES.floorToCeiling}" data-window-id="${escapeHtml(item.id)}">落地窗</button>
        </div>`
      : "";
    return `<article class="rp-door-review-item ${selected ? "is-active" : ""}">
      <button type="button" class="rp-door-review-select"
        data-structure-review="${escapeHtml(item.id)}" data-structure-kind="${kind}">
        <strong>${kind === "window" && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling ? "落地窗" : meta.label} ${index + 1}</strong>
        <span>${structureMeasurement(item, kind)} · ${item.confirmed ? "已確認" : "待人工確認"}</span>
      </button>
      <button type="button" class="rp-door-confirm ${item.confirmed ? "is-confirmed" : ""}"
        data-confirm-structure="${escapeHtml(item.id)}" data-structure-kind="${kind}">${item.confirmed ? "已確認" : "確認"}</button>
      ${windowTypeToggle}
    </article>`;
  }).join("");
}

function renderDoorReviewList() {
  renderStructureReviewList();
}

function confirmStructure(kind, structureId) {
  const collection = state.structures[structureCollections[kind]] || [];
  const item = collection.find((candidate) => candidate.id === structureId);
  if (!item) return;
  if (rejectStructureWallCollision(item, kind)) {
    state.selectedStructure = { id: item.id, kind };
    renderSelectedStructureEditor();
    return;
  }
  item.confirmed = true;
  item.estimated = false;
  state.selectedStructure = { id: item.id, kind };
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  scheduleSave("space_confirmation");
  setStatus(`此${structureSectionMeta[kind].label}的位置與尺寸已確認。`);
}

function confirmDoor(doorId) {
  confirmStructure("door", doorId);
}

function lockSelectedDoorOpening() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "door") return;
  const center = {
    x: (Number(item.start?.x || 0) + Number(item.end?.x || 0)) / 2,
    y: (Number(item.start?.y || 0) + Number(item.end?.y || 0)) / 2,
  };
  if (!snapOpeningToHostWall(item, center)) {
    const message = "找不到可對應的牆體，請先確認門洞位置。";
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  item.confirmed = true;
  item.estimated = false;
  item.opening_source = "manual_confirmed";
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom(
    "space_confirmation",
    "門洞位置已鎖定，請重新生成第 6 步的 2D+3D 場景。",
  );
  scheduleSave("space_confirmation");
  setStatus("門洞已鎖定為關門位置，後續 3D 會以這個洞口生成。");
}

function applySelectedStructureSize() {
  const item = selectedStructureItem();
  if (!item) return;
  const kind = state.selectedStructure.kind;
  const columnLimits = kind === "column" ? confirmedFloorplanEditor() : null;
  const columnDimensions = kind === "column"
    ? validateColumnDimensionsCm({
      widthCm: $("#selected-structure-size-cm").value,
      depthCm: $("#selected-structure-depth-cm").value,
      heightCm: confirmedRoomHeightCm(),
      maxWidthCm: columnLimits.width_cm,
      maxDepthCm: columnLimits.depth_cm,
      maxHeightCm: columnLimits.room_height_cm,
      centerXcm: Number(item.center?.x || 0),
      centerYcm: Number(item.center?.y ?? item.center?.z ?? 0),
      rotationDeg: Number(item.rotation_deg || 0),
    })
    : null;
  if (columnDimensions && !columnDimensions.valid) {
    element.spaceError.textContent = columnDimensions.message;
    setStatus(columnDimensions.message);
    return;
  }
  element.spaceError.textContent = "";
  const sizeCm = columnDimensions
    ? columnDimensions.values.widthCm
    : Math.max(1, Number($("#selected-structure-size-cm").value));
  const heightCm = columnDimensions
    ? confirmedRoomHeightCm()
    : Math.max(1, Number($("#selected-structure-height-cm").value));
  const lengthCm = Math.max(10, Number($("#selected-structure-length-cm").value));
  const depthCm = columnDimensions
    ? columnDimensions.values.depthCm
    : Math.max(10, Number($("#selected-structure-depth-cm").value));
  const floorToCeiling = kind === "window"
    && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling;
  const sillHeightCm = floorToCeiling
    ? 0
    : Math.max(0, Number($("#window-sill-height-cm").value));
  const nextItem = { ...item };
  if (kind === "window") {
    const cx = (item.start.x + item.end.x) / 2;
    const cy = (item.start.y + item.end.y) / 2;
    const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x);
    nextItem.start = { x: cx - Math.cos(angle) * sizeCm / 2, y: cy - Math.sin(angle) * sizeCm / 2 };
    nextItem.end = { x: cx + Math.cos(angle) * sizeCm / 2, y: cy + Math.sin(angle) * sizeCm / 2 };
    nextItem.width_cm = sizeCm;
    nextItem.sill_height_cm = sillHeightCm;
    nextItem.height_cm = heightCm;
    nextItem.head_height_cm = sillHeightCm + heightCm;
  } else if (kind === "door") {
    nextItem.height_cm = heightCm;
  } else if (kind === "column") {
    nextItem.size_cm = sizeCm;
    nextItem.depth_cm = depthCm;
    nextItem.height_cm = heightCm;
  } else {
    nextItem.thickness_cm = sizeCm;
    nextItem.height_cm = heightCm;
    if (item.start && item.end) {
      const center = {
        x: (item.start.x + item.end.x) / 2,
        y: (item.start.y + item.end.y) / 2,
      };
      const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x);
      nextItem.start = {
        x: center.x - Math.cos(angle) * lengthCm / 2,
        y: center.y - Math.sin(angle) * lengthCm / 2,
      };
      nextItem.end = {
        x: center.x + Math.cos(angle) * lengthCm / 2,
        y: center.y + Math.sin(angle) * lengthCm / 2,
      };
    }
  }
  const resolution = resolveStructureSizeDraft(nextItem, kind);
  if (!resolution.resolved) {
    rejectStructureWallCollision(nextItem, kind);
    return;
  }
  const attachedUpdates = kind === "wall"
    ? attachedOpeningUpdates(
        item,
        resolution.item,
        JSON.parse(JSON.stringify(attachedOpenings(state.structures, item.id))),
      )
    : [];
  if (kind === "wall" && attachedUpdates == null) {
    const message = "牆長不足以容納附著門窗，尺寸未套用。請先調整或刪除門窗。";
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  Object.assign(item, resolution.item);
  applyAttachedOpeningUpdates(attachedUpdates);
  if (kind === "wall") normalizeWallDemolitionCandidates();
  structureSizeDraft = null;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  if (item.scheme_id === "B") {
    invalidateRenovationScheme("方案 B 結構尺寸已修改；方案 A 與問卷保留。");
  } else {
    invalidateDownstreamFrom("space_confirmation", "結構尺寸已修改，後續需求、家具與 3D 需要重新確認。");
  }
  scheduleSave("space_confirmation");
  const shiftNote = resolution.moved
    ? `，並向室內避牆位移 ${Math.round(resolution.totalShiftCm)} 公分`
    : "";
  setStatus(kind === "column"
    ? `柱寬深已更新為 ${Math.round(sizeCm)} × ${Math.round(depthCm)} 公分，柱高依樓高固定為 ${Math.round(heightCm)} 公分${shiftNote}。`
    : `${structureSectionMeta[kind].label}尺寸已更新${shiftNote}。`);
}

function applyWindowType(windowId, type) {
  const item = state.structures.windows.find((candidate) => candidate.id === windowId);
  if (!item) return;
  const nextType = normalizedWindowType(type);
  if (normalizedWindowType(item.window_type) === nextType) return;
  const ceilingHeightCm = confirmedFloorplanEditor().room_height_cm;
  Object.assign(
    item,
    applyWindowTypePreset(item, nextType, ceilingHeightCm),
  );
  item.confirmed = false;
  item.estimated = false;
  state.selectedStructure = { id: item.id, kind: "window" };
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  if (item.scheme_id === "B") {
    invalidateRenovationScheme("方案 B 窗戶類型已修改；方案 A 與問卷保留。");
  } else {
    invalidateDownstreamFrom(
      "space_confirmation",
      "窗戶類型已修改，後續需求、家具與 3D 需要重新確認。",
    );
  }
  scheduleSave("space_confirmation");
  setStatus(item.window_type === WINDOW_TYPES.floorToCeiling
    ? "已改為落地窗，窗台設為 0 cm，3D 會依樓高生成玻璃與框架。"
    : "已改為一般窗，請確認窗高與窗台高度。");
}

function applySelectedWindowType() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "window") return;
  applyWindowType(item.id, $("#selected-window-type").value);
}

function setSelectedOpeningWidthCm(requestedWidthCm, persist = false) {
  const item = selectedStructureItem();
  if (!item || !["door", "window"].includes(state.selectedStructure?.kind)) return;
  const kind = state.selectedStructure.kind;
  const widthCm = Math.max(30, Math.min(400, Number(requestedWidthCm)));
  const hostWall = openingHostWall(item);
  const hostLengthCm = hostWall
    ? Math.hypot(
        hostWall.end.x - hostWall.start.x,
        hostWall.end.y - hostWall.start.y,
      )
    : Infinity;
  if (widthCm > hostLengthCm - 10) {
    const message = `${structureSectionMeta[kind].label}寬不可超過附著牆長；請縮小開口或先調整方案 B 的牆。`;
    element.spaceError.textContent = message;
    setStatus(message, "error");
    return;
  }
  const dx = item.end.x - item.start.x;
  const dy = item.end.y - item.start.y;
  const length = Math.hypot(dx, dy) || 1;
  item.end = {
    x: item.start.x + dx / length * widthCm,
    y: item.start.y + dy / length * widthCm,
  };
  if (kind === "door") delete item.swing_end;
  item.width_cm = widthCm;
  item.confirmed = false;
  item.estimated = false;
  element.openingWidthSlider.value = String(Math.round(widthCm));
  element.openingWidthValue.textContent = `${Math.round(widthCm)} cm`;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  if (persist) {
    const label = structureSectionMeta[kind].label;
    if (item.scheme_id === "B") {
      invalidateRenovationScheme(`方案 B 的${label}寬已調整；方案 A 與問卷保留。`);
    } else {
      invalidateDownstreamFrom("space_confirmation", `${label}寬已調整，後續需求、家具與 3D 需要重新確認。`);
    }
    scheduleSave("space_confirmation");
    setStatus(`${label}寬已調整為 ${Math.round(widthCm)} cm；請重新確認此${label}。`);
  }
}

function syncFurnitureSelectFromCheckboxes() {
  if (!element.roomFurnitureSelect) return;
  const checked = new Set($$("input:checked", element.roomFurnitureOptions).map((input) => input.value));
  Array.from(element.roomFurnitureSelect.options).forEach((option) => {
    option.selected = checked.has(option.value);
  });
}

function syncFurnitureCheckboxesFromSelect() {
  if (!element.roomFurnitureSelect) return;
  const selected = new Set(
    Array.from(element.roomFurnitureSelect.selectedOptions).map((option) => option.value),
  );
  $$("input", element.roomFurnitureOptions).forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function rotateSelectedStructure(deltaDeg) {
  const item = selectedStructureItem();
  if (!item) return;
  if (state.selectedStructure?.kind === "column") {
    const candidate = {
      ...item,
      rotation_deg: (Number(item.rotation_deg) || 0) + deltaDeg,
    };
    if (rejectStructureWallCollision(candidate, "column")) return;
    item.rotation_deg = candidate.rotation_deg;
    item.confirmed = false;
    item.estimated = false;
    renderSpaceOverlay();
    renderStructureReviewList();
    renderSelectedStructureEditor();
    invalidateDownstreamFrom("space_confirmation", "柱的方向已微調，後續需求、家具與 3D 需要重新確認。");
    scheduleSave("space_confirmation");
    return;
  }
  if (!item.start || !item.end) return;
  const snapshot = JSON.parse(JSON.stringify(item));
  const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x)
    + (Math.PI / 180) * deltaDeg;
  const length = Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y);
  const center = {
    x: (item.start.x + item.end.x) / 2,
    y: (item.start.y + item.end.y) / 2,
  };
  const nextWall = {
    ...item,
    start: {
    x: center.x - Math.cos(angle) * length / 2,
    y: center.y - Math.sin(angle) * length / 2,
    },
    end: {
    x: center.x + Math.cos(angle) * length / 2,
    y: center.y + Math.sin(angle) * length / 2,
    },
  };
  const attachedUpdates = state.selectedStructure?.kind === "wall"
    ? attachedOpeningUpdates(
        snapshot,
        nextWall,
        JSON.parse(JSON.stringify(attachedOpenings(state.structures, item.id))),
      )
    : [];
  if (state.selectedStructure?.kind === "wall" && attachedUpdates == null) {
    element.spaceError.textContent =
      "旋轉後牆長不足以容納附著門窗，已取消這次修改。";
    return;
  }
  item.start = nextWall.start;
  item.end = nextWall.end;
  applyAttachedOpeningUpdates(attachedUpdates);
  if (state.selectedStructure?.kind === "door") delete item.swing_end;
  if (state.selectedStructure?.kind === "wall") normalizeWallDemolitionCandidates();
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  if (item.scheme_id === "B") {
    invalidateRenovationScheme("方案 B 結構方向已修改；方案 A 與問卷保留。");
  } else {
    invalidateDownstreamFrom("space_confirmation", "結構方向已微調，後續需求、家具與 3D 需要重新確認。");
  }
  scheduleSave("space_confirmation");
}

function deleteSelectedStructure() {
  if (!state.selectedStructure) return;
  const deletedKind = state.selectedStructure.kind;
  const collection = structureCollections[state.selectedStructure.kind];
  const selected = selectedStructureItem();
  if (deletedKind === "wall" && state.pendingWallDeleteId !== selected?.id) {
    const children = attachedOpenings(state.structures, selected?.id || "");
    state.pendingWallDeleteId = selected?.id || null;
    renderSelectedStructureEditor();
    setStatus(
      children.length
        ? `再次點擊「確認刪除牆」會一併刪除這面牆與附著的 ${children.length} 個門窗；刪除牆時會一併刪除附著門窗。`
        : "請再次點擊「確認刪除牆」完成刪除；切換選取或取消操作可放棄。",
      "error",
    );
    return;
  }
  if (deletedKind === "wall" && selected?.scheme_id === "B") {
    const children = attachedOpenings(state.structures, selected.id);
    children.forEach(({ collection: childCollection, item }) => {
      state.structures[childCollection] = state.structures[childCollection].filter(
        (candidate) => candidate.id !== item.id,
      );
    });
  }
  state.structures[collection] = state.structures[collection].filter(
    (item) => item.id !== state.selectedStructure.id,
  );
  const nextItem = state.structures[collection][0] || null;
  state.pendingWallDeleteId = null;
  state.selectedStructure = nextItem ? { id: nextItem.id, kind: deletedKind } : null;
  renderSpaceOverlay();
  renderStructureCounts();
  renderSelectedStructureEditor();
  if (selected?.scheme_id === "B") {
    invalidateRenovationScheme("方案 B 結構已刪除；方案 A 與問卷保留。");
  } else {
    invalidateDownstreamFrom("space_confirmation", "結構已刪除，後續需求、家具與 3D 需要重新確認。");
  }
  scheduleSave("space_confirmation");
}

function selectRoom(roomId) {
  if (state.selectedRoomId !== roomId) {
    state.roomNodeMode = null;
    state.selectedRoomNodeIndices = [];
    updateRoomNodeControls();
  }
  state.selectedRoomId = roomId;
  if (state.roomGeometryMode === "merge") {
    state.showAllRooms = true;
    state.mergeRoomIds = state.mergeRoomIds.includes(roomId)
      ? state.mergeRoomIds.filter((id) => id !== roomId)
      : [...state.mergeRoomIds.slice(-1), roomId];
    updateRoomGeometryControls();
  } else {
    state.showAllRooms = false;
    if (state.roomGeometryMode === "split") {
      state.splitPoints = [];
      updateRoomGeometryControls();
    }
  }
  renderRooms();
  renderSpaceOverlay();
}

function saveRoom() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const option = ROOM_NAME_OPTIONS.find((item) => item.id === element.roomName.value);
  if (!option) {
    element.spaceError.textContent = "請選擇空間名稱。";
    element.roomName.focus();
    return;
  }
  room.label = option.label;
  room.type = option.type;
  room.room_type = option.type;
  room.visual_space_type = option.id;
  room.confirmed = false;
  room.source = "manual_confirmation";
  room.confidence = 1;
  applyCanonicalRoomLabels(state.rooms);
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間資料已修改，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
}

function nearestPointOnSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function nearestPointOnLine(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared;
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function openingHostWall(item) {
  const center = {
    x: (item.start.x + item.end.x) / 2,
    y: (item.start.y + item.end.y) / 2,
  };
  const doorDx = item.end.x - item.start.x;
  const doorDy = item.end.y - item.start.y;
  const doorLength = Math.hypot(doorDx, doorDy) || 1;
  return state.structures.walls
    .map((wall) => {
      const wallDx = wall.end.x - wall.start.x;
      const wallDy = wall.end.y - wall.start.y;
      const wallLength = Math.hypot(wallDx, wallDy) || 1;
      const alignment = Math.abs(
        (doorDx / doorLength) * (wallDx / wallLength)
        + (doorDy / doorLength) * (wallDy / wallLength),
      );
      const projected = nearestPointOnLine(center, wall.start, wall.end);
      const segmentProjection = nearestPointOnSegment(center, wall.start, wall.end);
      const perpendicularDistance = Math.hypot(projected.x - center.x, projected.y - center.y);
      const extensionDistance = Math.hypot(
        projected.x - segmentProjection.x,
        projected.y - segmentProjection.y,
      );
      const recognizedHostBonus = wall.id === item.host_wall_id && alignment > 0.92 ? -8 : 0;
      return {
        wall,
        score: perpendicularDistance
          + (1 - alignment) * 300
          + extensionDistance * 0.12
          + recognizedHostBonus,
      };
    })
    .sort((a, b) => a.score - b.score)[0]?.wall || null;
}

function snapOpeningToHostWall(item, targetCenter) {
  const wall = openingHostWall(item);
  if (!wall) return false;
  const center = nearestPointOnLine(targetCenter, wall.start, wall.end);
  const wallDx = wall.end.x - wall.start.x;
  const wallDy = wall.end.y - wall.start.y;
  const wallLength = Math.hypot(wallDx, wallDy) || 1;
  const axis = { x: wallDx / wallLength, y: wallDy / wallLength };
  const currentDx = item.end.x - item.start.x;
  const currentDy = item.end.y - item.start.y;
  const direction = currentDx * axis.x + currentDy * axis.y < 0 ? -1 : 1;
  const halfWidth = Math.max(
    20,
    Number(item.width_cm || Math.hypot(currentDx, currentDy) || 90) / 2,
  );
  item.start = {
    x: center.x - axis.x * halfWidth * direction,
    y: center.y - axis.y * halfWidth * direction,
  };
  item.end = {
    x: center.x + axis.x * halfWidth * direction,
    y: center.y + axis.y * halfWidth * direction,
  };
  delete item.swing_end;
  item.host_wall_id = wall.id;
  return true;
}

function resizeOpeningFromPointer(event) {
  const item = selectedStructureItem();
  const point = imagePoint(event, element.spaceImage);
  if (!item || !point || !["door", "window"].includes(state.selectedStructure?.kind)) return;
  const requested = pixelToCm(point);
  const wall = openingHostWall(item);
  const projected = nearestPointOnLine(requested, item.start, item.end);
  const movingKey = doorResizeDrag.handle;
  const fixedKey = movingKey === "start" ? "end" : "start";
  const fixed = item[fixedKey];
  const snapshotMoving = doorResizeDrag.snapshot[movingKey];
  let dx = projected.x - fixed.x;
  let dy = projected.y - fixed.y;
  let length = Math.hypot(dx, dy);
  if (length < 0.1) {
    dx = snapshotMoving.x - fixed.x;
    dy = snapshotMoving.y - fixed.y;
    length = Math.hypot(dx, dy) || 1;
  }
  const width = Math.max(30, Math.min(400, length));
  item[movingKey] = {
    x: fixed.x + dx / length * width,
    y: fixed.y + dy / length * width,
  };
  if (state.selectedStructure?.kind === "door") delete item.swing_end;
  item.width_cm = Math.hypot(
    item.end.x - item.start.x,
    item.end.y - item.start.y,
  );
  item.host_wall_id = wall?.id || item.host_wall_id;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
}

function addDroppedStructure(tool, point) {
  state.activeStructureKind = tool;
  const meter = pixelToCm(point);
  let item = null;
  if (tool === "column") {
    item = {
      id: `column-manual-${Date.now()}`,
      center: meter,
      size_cm: 35,
      depth_cm: 35,
      height_cm: confirmedRoomHeightCm(),
      confirmed: false,
      estimated: true,
      source: "manual",
      scheme_id: "B",
    };
    if (rejectStructureWallCollision(item, "column")) return;
    state.structures.columns.push(item);
  } else if (tool === "door" || tool === "window") {
    const candidates = state.structures.walls.map((wall) => ({
      wall,
      projected: nearestPointOnSegment(meter, wall.start, wall.end),
    }));
    candidates.sort((a, b) => {
      const da = Math.hypot(a.projected.x - meter.x, a.projected.y - meter.y);
      const db = Math.hypot(b.projected.x - meter.x, b.projected.y - meter.y);
      return da - db;
    });
    const host = candidates[0];
    const widthCm = tool === "door" ? 90 : 120;
    const wallStart = host?.wall.start || { x: meter.x - 100, y: meter.y };
    const wallEnd = host?.wall.end || { x: meter.x + 100, y: meter.y };
    const angle = Math.atan2(wallEnd.y - wallStart.y, wallEnd.x - wallStart.x);
    const center = host?.projected || meter;
    item = {
      id: `${tool}-manual-${Date.now()}`,
      start: { x: center.x - Math.cos(angle) * widthCm / 2, y: center.y - Math.sin(angle) * widthCm / 2 },
      end: { x: center.x + Math.cos(angle) * widthCm / 2, y: center.y + Math.sin(angle) * widthCm / 2 },
      width_cm: widthCm,
      height_cm: tool === "window" ? 120 : 210,
      sill_height_cm: tool === "window" ? 90 : 0,
      window_type: tool === "window" ? WINDOW_TYPES.standard : undefined,
      host_wall_id: host?.wall.id,
      source: "manual",
      scheme_id: "B",
      opening_direction: "right",
      confirmed: false,
      estimated: true,
    };
    if (tool === "window") {
      const duplicate = state.structures.windows.find((candidate) => windowsOverlap(candidate, item));
      if (duplicate) {
        state.selectedStructure = { id: duplicate.id, kind: "window" };
        state.structureTool = null;
        $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
        renderSpaceOverlay();
        renderStructureReviewList();
        renderSelectedStructureEditor();
        setStatus("此位置已有窗，已選取既有窗，不重複新增。");
        return;
      }
    }
    state.structures[tool === "door" ? "doors" : "windows"].push(item);
  }
  if (item) {
    ensureRenovationScheme("added_structure");
    state.selectedStructure = { id: item.id, kind: tool };
  }
  state.structureTool = null;
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateRenovationScheme(
    "方案 B 已新增結構；問卷與方案 A 保留，方案 B 家具需重新計算。",
  );
  scheduleSave("space_confirmation");
  setStatus(`已新增${tool === "door" ? "門" : tool === "window" ? "窗" : "柱"}，可在右側繼續修改。`);
}

function setActiveStructureKind(kind) {
  if (!structureCollections[kind]) return;
  state.activeStructureKind = kind;
  state.structureTool = null;
  state.structureLineStart = null;
  state.structureLinePreviewEnd = null;
  structureDrag = null;
  doorResizeDrag = null;
  const firstItem = state.structures[structureCollections[kind]]?.[0] || null;
  state.selectedStructure = firstItem ? { id: firstItem.id, kind } : null;
  $$("[data-structure-section]").forEach((button) => {
    const active = button.dataset.structureSection === kind;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  setStatus(`已切換到${structureSectionMeta[kind].label}頁；左圖只顯示此類結構的可編輯標記。`);
}

function selectStructureForReview(kind, structureId) {
  const item = state.structures[structureCollections[kind]]?.find(
    (candidate) => candidate.id === structureId,
  );
  if (!item) return;
  state.activeStructureKind = kind;
  state.selectedStructure = { id: item.id, kind };
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  setStatus(`已選取${structureSectionMeta[kind].label}，可拖曳、修改尺寸、旋轉或刪除。`);
}

function selectDoorForReview(doorId) {
  selectStructureForReview("door", doorId);
}

function rotateSelectedDoor180() {
  const item = selectedStructureItem();
  if (!item || state.selectedStructure?.kind !== "door") return;
  [item.start, item.end] = [item.end, item.start];
  delete item.swing_end;
  item.confirmed = false;
  item.estimated = false;
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  if (item.scheme_id === "B") {
    invalidateRenovationScheme("方案 B 門的鉸鏈端已翻轉；方案 A 與問卷保留。");
  } else {
    invalidateDownstreamFrom("space_confirmation", "門的鉸鏈端已翻轉，後續需求、家具與 3D 需要重新確認。");
  }
  scheduleSave("space_confirmation");
  setStatus("已將鉸鏈端翻轉 180°；請檢查門弧後重新確認此扇門。");
}

function renderStructureCounts() {
  const s = state.structures;
  const pendingSummary = Object.entries(structureCollections)
    .map(([kind, collection]) => ({
      label: structureSectionMeta[kind].label,
      count: s[collection].filter((item) => item.confirmed !== true).length,
    }))
    .filter((item) => item.count > 0)
    .map((item) => `${item.label} ${item.count}`)
    .join("、");
  const review = pendingSummary
    ? `；待確認：${pendingSummary}`
    : "；所有結構皆已確認";
  element.structureCounts.textContent =
    `辨識＋人工修正：牆 ${s.walls.length}、門 ${s.doors.length}、窗 ${s.windows.length}、樑 ${s.beams.length}、柱 ${s.columns.length}${review}`;
  renderDoorReviewList();
}

function confirmSpace() {
  element.spaceError.textContent = "";
  if (!state.rooms.every((room) => room.confirmed === true)) {
    const pendingCount = state.rooms.filter((room) => !room.confirmed).length;
    element.spaceError.textContent =
      `尚有 ${pendingCount} 個房間未確認，請逐一按右側房間的「確認」鍵。`;
    element.roomList.querySelector("[data-confirm-room]:not(.is-confirmed)")?.focus();
    return;
  }
  const pendingStructureKind = Object.keys(structureCollections).find((kind) => {
    const collection = state.structures[structureCollections[kind]];
    return collection.some((item) => item.confirmed !== true);
  });
  if (pendingStructureKind) {
    const collection = state.structures[structureCollections[pendingStructureKind]];
    const pendingCount = collection.filter((item) => item.confirmed !== true).length;
    const meta = structureSectionMeta[pendingStructureKind];
    element.spaceError.textContent =
      `尚有 ${pendingCount} 個${meta.label}項目未確認，已為你切到「${meta.label}」頁。請逐項確認或按「確認此頁全部項目」。`;
    $("[data-space-tab='structure']").click();
    setActiveStructureKind(pendingStructureKind);
    $("#structure-review-list [data-confirm-structure]")?.focus();
    return;
  }
  if (!$("#structure-confirmed").checked) {
    element.spaceError.textContent = "請切到「牆門窗樑柱」並確認結構。";
    $("[data-space-tab='structure']").focus();
    return;
  }
  if (!$("#estimated-size-ack").checked) {
    element.spaceError.textContent = "請確認已了解圖面估計尺寸可能與現場不同。";
    $("#estimated-size-ack").focus();
    return;
  }
  showDimensionedPlanReview();
}

function dimensionedPlanRoomInputs() {
  return state.rooms.map((room) => ({
    id: room.id,
    label: room.label || "未命名空間",
    polygonPx: room.polygon_cm.map(cmToPixel),
    ...roomDimensions(room),
  }));
}

function renderDimensionedPlanReview() {
  const { imageWidth, imageHeight } = planGeometry();
  const annotation = buildDimensionedPlanAnnotations(
    dimensionedPlanRoomInputs(),
    { imageWidth, imageHeight },
  );
  element.dimensionTotalArea.textContent = `${annotation.totalAreaM2.toFixed(2)} m²`;
  element.dimensionRoomCount.textContent = `${annotation.roomCount} 個`;
  const distanceCm = Number(state.workflow?.data?.calibration?.distanceCm);
  element.dimensionCalibrationState.textContent = distanceCm > 0
    ? `已用 ${Math.round(distanceCm)} cm 已知尺寸校正`
    : "已套用比例尺校正";
  element.dimensionPlanOverlay.setAttribute("viewBox", `0 0 ${imageWidth} ${imageHeight}`);
  element.dimensionPlanOverlay.innerHTML = annotation.svg;
  element.dimensionPlanLegend.innerHTML = annotation.rooms.map((room) => `
    <span><i style="background:${room.color}"></i><strong>${escapeHtml(room.label)}</strong>
      ${Math.round(room.widthCm)} × ${Math.round(room.depthCm)} cm</span>
  `).join("");
  const source = element.spaceImage.currentSrc || element.spaceImage.src;
  if (source && element.dimensionPlanImage.src !== source) {
    element.dimensionPlanImage.src = source;
    element.dimensionPlanImage?.addEventListener("load", () => {
      syncOverlayToImage(
        element.dimensionPlanStage,
        element.dimensionPlanImage,
        element.dimensionPlanOverlay,
      );
    }, { once: true });
  }
  requestAnimationFrame(() => syncOverlayToImage(
    element.dimensionPlanStage,
    element.dimensionPlanImage,
    element.dimensionPlanOverlay,
  ));
}

function setSpaceReviewMode(mode) {
  state.spaceReviewMode = ["dimensions", "proportion"].includes(mode) ? "dimensions" : "editing";
  const reviewing = state.spaceReviewMode === "dimensions";
  element.spaceEditorWorkspace.hidden = reviewing;
  element.spaceDimensionReview.hidden = !reviewing;
  if (activePanelName(state.workflow?.currentStep) === "space") {
    element.instruction.textContent = reviewing
      ? "最後確認平面圖上的房間輪廓、長寬尺寸與估算面積"
      : instructions.space_confirmation[1];
  }
  if (reviewing) renderDimensionedPlanReview();
}

function showDimensionedPlanReview() {
  element.dimensionReviewError.textContent = "";
  setSpaceReviewMode("dimensions");
  element.spaceDimensionReview.scrollIntoView({ behavior: "smooth", block: "start" });
  $("#back-to-space-editor").focus({ preventScroll: true });
  setStatus("請確認平面圖上的彩色房間輪廓、水平寬度與垂直長度標註。");
}

function confirmDimensionedPlan() {
  const { imageWidth, imageHeight } = planGeometry();
  const annotation = buildDimensionedPlanAnnotations(
    dimensionedPlanRoomInputs(),
    { imageWidth, imageHeight },
  );
  if (!annotation.roomCount || annotation.totalAreaM2 <= 0) {
    element.dimensionReviewError.textContent = "目前沒有可確認的空間尺寸，請返回調整空間或重新校正比例尺。";
    return;
  }
  state.confirmedStructureSnapshot = captureConfirmedStructureSnapshot();
  state.workflow.complete("space_confirmation", {
    roomsConfirmed: true,
    structureConfirmed: true,
    proportionsConfirmed: true,
    dimensionedPlanConfirmed: true,
    totalAreaM2: annotation.totalAreaM2,
  });
  renderWholeHouseQuestionnaire();
  setStatus("尺寸標註平面圖與結構均已確認。現在開始基本問卷。");
  goTo("requirements");
}

const QUESTIONNAIRE_STAGES = Object.freeze([
  "profile",
  "rooms",
  "summary",
]);

const ROOM_REQUIREMENT_POLAR_AXES = Object.freeze({
  living_room: [
    { axis: "use", left: "獨處放鬆", right: "多人社交" },
    { axis: "lighting", left: "柔和間接光", right: "明亮主燈" },
  ],
  bedroom: [
    { axis: "use", left: "深度睡眠", right: "工作收納" },
    { axis: "atmosphere", left: "安靜包覆", right: "清爽明亮" },
  ],
  kitchen: [
    { axis: "use", left: "快速備餐", right: "聚餐烹飪" },
    { axis: "lighting", left: "餐吊燈", right: "均勻工作光" },
  ],
  bathroom: [
    { axis: "use", left: "快速乾濕分離", right: "泡澡放鬆" },
    { axis: "maintenance", left: "低維護", right: "飯店感" },
  ],
  storage: [
    { axis: "use", left: "專注工作", right: "彈性閱讀" },
    { axis: "lighting", left: "防眩任務光", right: "展示氛圍光" },
  ],
  balcony: [
    { axis: "use", left: "洗曬機能", right: "休憩植栽" },
    { axis: "storage", left: "完全收納", right: "開放展示" },
  ],
  entryway: [
    { axis: "use", left: "快速出入", right: "完整落塵收納" },
    { axis: "lighting", left: "感應安全光", right: "端景展示光" },
  ],
  hallway: [
    { axis: "use", left: "保持通行", right: "增加收納" },
    { axis: "lighting", left: "感應安全光", right: "端景展示光" },
  ],
  garage: [
    { axis: "use", left: "停車淨空", right: "工具收納" },
    { axis: "lighting", left: "安全照明", right: "工作照明" },
  ],
  default: [
    { axis: "use", left: "極簡留白", right: "高機能收納" },
    { axis: "atmosphere", left: "安靜低調", right: "明亮展示" },
  ],
});

const TEST_REQUIREMENT_PROFILE_NOTES = Object.freeze([
  "測試需求：偏低維護、好整理、保留寬走道。",
  "測試需求：偏展示感、材質層次明顯、照明要有重點。",
  "測試需求：偏高收納、家具要實用、動線不能被堵住。",
  "測試需求：偏放鬆舒適、光線柔和、少尖角。",
]);

const TEST_AIR_CONDITIONING_OPTIONS = Object.freeze([
  "wall-split",
  "ceiling-cassette",
  "ducted",
  "none",
]);

const QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT = 4;
const INDEPENDENT_FLOOR_ROOM_TYPES = new Set([
  "bathroom",
  "kitchen",
  "entryway",
  "balcony",
  "laundry",
  "utility",
]);
const INDEPENDENT_FLOOR_LABEL_PATTERNS = [
  "浴",
  "廁",
  "衛",
  "廚",
  "玄關",
  "陽台",
  "洗衣",
  "家務",
];

const PREFERENCE_WEIGHT_OPTIONS = Object.freeze([
  { value: -2, label: "強偏 A" },
  { value: -1, label: "偏 A" },
  { value: 0, label: "平衡" },
  { value: 1, label: "偏 B" },
  { value: 2, label: "強偏 B" },
]);

function randomItem(items, fallback = null) {
  const candidates = (items || []).filter(Boolean);
  if (!candidates.length) return fallback;
  return candidates[Math.floor(Math.random() * candidates.length)];
}

function roomAllowsIndependentFloor(room = {}) {
  const type = String(room.type || room.room_type || "").toLowerCase();
  const label = String(room.label || room.name || "");
  return INDEPENDENT_FLOOR_ROOM_TYPES.has(type)
    || INDEPENDENT_FLOOR_LABEL_PATTERNS.some((pattern) => label.includes(pattern));
}

function trimAccentWallSurfaces(surfaces = {}) {
  return {
    ...surfaces,
    // Step 5 provides a whole-house wall finish.  Per-wall accents are not
    // carried into Step 6 unless a future explicit room override is added.
    wallSurfaceIds: [],
    wallOverrides: {},
  };
}

function isCirculationRoom(room = {}) {
  const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
  const label = String(room.label || room.name || "");
  return type === "hallway" || /走道|動線/.test(label);
}

function livingRoomForCirculation() {
  return state.rooms.find((room) => {
    const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
    return type === "living_room" || /客廳/.test(String(room.label || room.name || ""));
  }) || null;
}

function circulationStyleIsOverridden(room = {}) {
  return Boolean(
    state.roomRequirementModel?.roomRequirements?.[room.id]?.circulationStyleOverrideApproved,
  );
}

function copyLivingRoomStyleToCirculation(room, { force = false } = {}) {
  if (!isCirculationRoom(room)) return false;
  const livingRoom = livingRoomForCirculation();
  if (!livingRoom || livingRoom.id === room.id) return false;
  const requirements = state.roomRequirementModel?.roomRequirements || {};
  const requirement = requirements[room.id];
  const livingRequirement = requirements[livingRoom.id];
  if (!requirement || !livingRequirement || (!force && circulationStyleIsOverridden(room))) return false;
  const livingDraft = state.roomFinishDrafts?.[livingRoom.id];
  if (livingDraft) {
    state.roomFinishDrafts[room.id] = {
      ...livingDraft,
      wallOverrides: {},
      confirmed: state.roomFinishDrafts?.[room.id]?.confirmed || false,
    };
  }
  requirement.surfaces = trimAccentWallSurfaces({
    ...(livingRequirement.surfaces || {}),
  });
  requirement.climate = { ...(livingRequirement.climate || {}) };
  requirement.circulationStyleSourceRoomId = livingRoom.id;
  return true;
}

function synchronizeCirculationStyles() {
  state.rooms.filter(isCirculationRoom).forEach((room) => {
    copyLivingRoomStyleToCirculation(room);
  });
}

function wholeHouseMainFloorSurface() {
  const dryRoomFloor = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) =>
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.floor
    )
    .find((floor) => floor?.materialId || floor?.color);
  if (dryRoomFloor) return { ...dryRoomFloor };
  if (state.questionnaireFinishes.floorMaterial || state.questionnaireFinishes.floorColor) {
    return {
      materialId: state.questionnaireFinishes.floorMaterial || null,
      color: state.questionnaireFinishes.floorColor || null,
    };
  }
  return null;
}

function wholeHouseMainWallSurface() {
  const configured = state.questionnaireFinishes || {};
  if (configured.wallMaterial || configured.wallColor) {
    return {
      materialId: configured.wallMaterial || configured.defaultWallMaterial || null,
      color: configured.wallColor || configured.defaultWallColor || null,
    };
  }
  const dryRoomWall = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) => state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.wallDefault)
    .find((wall) => wall?.materialId || wall?.color);
  return dryRoomWall ? { ...dryRoomWall } : null;
}

function roomKeepsExplicitWallOverride(room, surfaces = {}) {
  return roomAllowsIndependentFloor(room) && surfaces.wallOverrideExplicit === true;
}

function normalizedRoomSurfaces(room, surfaces = {}) {
  const next = trimAccentWallSurfaces(surfaces);
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  if (mainWall && !roomKeepsExplicitWallOverride(room, next)) {
    next.wallDefault = { ...mainWall };
  }
  if (!roomAllowsIndependentFloor(room) && mainFloor) {
    next.floor = { ...mainFloor };
  }
  return next;
}

function applyWholeHouseSurfaceConsistency() {
  synchronizeCirculationStyles();
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  Object.entries(state.roomRequirementModel?.roomRequirements || {}).forEach(([roomId, requirement]) => {
    const room = state.rooms.find((candidate) => String(candidate.id) === String(roomId));
    requirement.surfaces = trimAccentWallSurfaces(requirement.surfaces || {});
    if (room && mainWall && !roomKeepsExplicitWallOverride(room, requirement.surfaces)) {
      requirement.surfaces.wallDefault = { ...mainWall };
    }
    if (room && !roomAllowsIndependentFloor(room) && mainFloor) {
      requirement.surfaces.floor = { ...mainFloor };
    }
  });
}

function normalizeSavedSceneWallSurfaces(sceneData) {
  if (!sceneData?.surface_overrides?.length) return 0;
  const mainWall = wholeHouseMainWallSurface();
  if (!mainWall?.materialId && !mainWall?.color) return 0;

  const resolvedOption = mainWall.materialId
    ? resolveSurfaceOption(sceneData.surface_catalog, "wall", mainWall.materialId)
    : null;
  let repaired = 0;
  sceneData.surface_overrides.forEach((override) => {
    const room = state.rooms.find((candidate) => String(candidate.id) === String(override.room_id));
    if (roomKeepsExplicitWallOverride(room, override)) return;
    const nextOption = resolvedOption || mainWall.materialId || override.wall_option || "auto";
    const nextColor = mainWall.color || override.wall_color_hex || null;
    if (
      override.wall_option !== nextOption
      || override.wall_color_hex !== nextColor
      || (override.wall_surface_ids || []).length
      || Object.keys(override.wall_overrides || {}).length
    ) {
      override.wall_option = nextOption;
      override.wall_color_hex = nextColor;
      override.wall_surface_ids = [];
      override.wall_overrides = {};
      repaired += 1;
    }
  });
  return repaired;
}

function stableStringNumber(value = "") {
  return String(value).split("").reduce(
    (total, char, index) => total + char.charCodeAt(0) * (index + 1),
    0,
  );
}

function materialOptionForPack(option, pack) {
  return {
    ...option,
    // The catalog record owns the swatch, color, and material wording.
    note: option.note,
    recommendation: pack.name,
  };
}

function materialCatalogText(surface) {
  return [
    surface.surface_id,
    surface.name_zh,
    surface.preview_url,
    surface.texture_url,
  ].filter(Boolean).join(" ").toLowerCase();
}

function catalogSurfaceIsUsableInRoom(kind, surface) {
  const text = materialCatalogText(surface);
  if (kind === "floor") {
    // Import folders contain bark, wallpaper, wicker, and ground studies. They are
    // legitimate textures, but not products that can honestly be offered as floors.
    return !/(?:bark|wallpaper|wicker|ground)/.test(text);
  }
  return !/(?:bark|wallpaper|wicker|ground)/.test(text);
}

function userFacingMaterialLabel(surface) {
  const raw = String(surface.name_zh || surface.material_group || surface.category || "材質").trim();
  return raw
    .replace(/\s+(?:bamboo|bark|concrete|ground|paintedbricks|paintedplaster|paintedwood|planks|tiles|wallpaper|wicker|wood)\d+[a-z]*$/i, "")
    .replace(/\s{2,}/g, " ")
    .trim() || "材質";
}

function addMaterialDisplayOrdinals(options) {
  const totals = options.reduce((counts, option) => {
    counts[option.label] = (counts[option.label] || 0) + 1;
    return counts;
  }, {});
  const seen = {};
  const numerals = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];
  return options.map((option) => {
    if (totals[option.label] <= 1) return option;
    seen[option.label] = (seen[option.label] || 0) + 1;
    return { ...option, label: `${option.label}（${numerals[seen[option.label] - 1] || seen[option.label]}）` };
  });
}

function catalogMaterialOptionsForPack(kind, pack) {
  const usage = kind === "wall" ? "wall" : "floor";
  const catalog = state.surfaceCatalog || state.sceneData?.surface_catalog || {};
  const surfaces = (catalog.surfaces || [])
    .filter((surface) => Array.isArray(surface.usage) && surface.usage.includes(usage))
    .filter((surface) => surface.surface_id && surface.preview_url && surface.texture_url)
    .filter((surface) => catalogSurfaceIsUsableInRoom(kind, surface))
    .map((surface) => ({
      id: surface.surface_id,
      label: userFacingMaterialLabel(surface),
      color: surface.color_hex || "#d5d0c7",
      materialPreview: surface.preview_url,
      textureUrl: surface.texture_url,
      materialGroup: surface.material_group || surface.category || "材質",
      searchText: [
        surface.surface_id,
        surface.name_zh,
        surface.material_group,
        surface.category,
      ].filter(Boolean).join(" ").toLowerCase(),
      source: "catalog",
      suitable: (surface.suitable_styles || []).includes(pack.styleId),
    }));
  const sorted = surfaces.sort((left, right) => {
    if (left.suitable !== right.suitable) return left.suitable ? -1 : 1;
    return stableStringNumber(`${pack.id}:${left.id}`) - stableStringNumber(`${pack.id}:${right.id}`);
  });
  return addMaterialDisplayOrdinals(sorted).map((option) => materialOptionForPack({
    ...option,
    note: option.materialGroup,
  }, pack));
}

function questionnaireMaterialOptionsForPack(kind, pack) {
  return styleCompatibleMaterialOptionsForPack(kind, pack)
    .slice(0, QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT);
}

function materialCatalogType(option) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  if (/木|wood|oak|walnut|plank/.test(text)) return "wood";
  if (/磚|tile|marble|stone|石/.test(text)) return "stone";
  if (/水泥|cement|concrete/.test(text)) return "cement";
  return "paint";
}

function materialCatalogColor(option) {
  const hex = String(option.color || "#d5d0c7").replace("#", "");
  const value = Number.parseInt(hex.length === 3 ? hex.split("").map((part) => part + part).join("") : hex, 16);
  const red = value >> 16;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  const lightness = (red + green + blue) / 3;
  if (lightness < 105) return "dark";
  if (Math.max(red, green, blue) - Math.min(red, green, blue) < 24) return "gray";
  if (red > blue + 14) return "warm";
  return "light";
}

function materialCatalogChroma(option) {
  const hex = String(option.color || "#d5d0c7").replace("#", "");
  const value = Number.parseInt(hex.length === 3 ? hex.split("").map((part) => part + part).join("") : hex, 16);
  const red = value >> 16;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return Math.max(red, green, blue) - Math.min(red, green, blue);
}

function isHighChromaMaterial(option) {
  return materialCatalogChroma(option) >= 52;
}

const MATERIAL_TYPE_LABELS = Object.freeze({ all: "全部", wood: "木質", stone: "石材／磁磚", cement: "水泥", paint: "塗料" });
const MATERIAL_COLOR_LABELS = Object.freeze({ all: "全部", light: "淺色", warm: "暖色", gray: "灰色", dark: "深色" });

// Automatic recommendations are style-aware. The full catalog is still
// available for deliberate custom choices in the material picker.
const STYLE_MATERIAL_RULES = Object.freeze({
  scandinavian: { wall: ["paint", "cement"], floor: ["wood"], colors: ["light", "warm"] },
  japanese: { wall: ["paint", "cement"], floor: ["wood"], colors: ["light", "warm"] },
  modern_minimal: { wall: ["paint", "cement"], floor: ["wood", "stone", "cement"], colors: ["light", "gray"] },
  cream: { wall: ["paint", "cement"], floor: ["wood", "stone"], colors: ["light", "warm"] },
  industrial: { wall: ["paint", "cement"], floor: ["wood", "stone", "cement"], colors: ["gray", "dark"] },
  american: { wall: ["paint", "cement"], floor: ["wood"], colors: ["warm", "dark"] },
});

function isWetAreaRoom(room) {
  return ["bath", "bathroom", "kitchen"].includes(String(room?.type || room?.room_type || "").toLowerCase());
}

function isPoolOrMosaicSurface(option) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  return /pool|swimming|mosaic|泳池|馬賽克/.test(text);
}

function styleCompatibleMaterialOptionsForPack(kind, pack, room = activeQuestionnaireRoom()) {
  const all = catalogMaterialOptionsForPack(kind, pack);
  const rule = STYLE_MATERIAL_RULES[pack.styleId];
  const wetArea = isWetAreaRoom(room);
  const compatible = all.filter((option) => {
    if (isPoolOrMosaicSurface(option) && !wetArea) return false;
    if (isHighChromaMaterial(option)) return false;
    const type = materialCatalogType(option);
    const color = materialCatalogColor(option);
    if (!wetArea && kind === "wall" && type === "stone") return false;
    if (!rule) return true;
    if (!rule[kind].includes(type)) return false;
    return rule.colors.includes(color);
  });
  const fallback = all.filter((option) =>
    (!isPoolOrMosaicSurface(option) || wetArea) && !isHighChromaMaterial(option),
  );
  return (compatible.length ? compatible : fallback)
    .sort((left, right) => materialPairScore(kind, right, pack, room) - materialPairScore(kind, left, pack, room));
}

function renderMaterialFilterChips(host, labels, selected, countById, dataset) {
  host.innerHTML = Object.entries(labels).filter(([id]) => id === "all" || countById[id]).map(([id, label]) => `
    <button type="button" class="rp-filter-chip ${selected === id ? "is-active" : ""}" data-${dataset}="${id}" aria-pressed="${selected === id}">${label}${id === "all" ? "" : ` (${countById[id]})`}</button>
  `).join("");
}

function materialPairScore(kind, option, pack, room) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  let score = option.suitable ? 18 : 0;
  if (isHighChromaMaterial(option)) score -= 180;
  const rule = STYLE_MATERIAL_RULES[pack.styleId];
  if (rule?.colors.includes(materialCatalogColor(option))) score += 24;
  if (kind === "wall" && !["kitchen", "bathroom"].includes(room?.type) && /磚|tile|brick/.test(text)) score -= 100;
  if (kind === "wall" && /塗料|漆|plaster|limewash|礦物/.test(text)) score += 12;
  if (kind === "floor" && /木|wood|oak|walnut|石|stone|microcement|水泥/.test(text)) score += 10;
  score += stableStringNumber(`${pack.id}:${kind}:${option.id}`) / 100000;
  return score;
}

function questionnaireMaterialPairsForPack(pack, room = activeQuestionnaireRoom()) {
  const walls = styleCompatibleMaterialOptionsForPack("wall", pack, room)
    .slice(0, 4);
  const floors = styleCompatibleMaterialOptionsForPack("floor", pack, room)
    .slice(0, 4);
  return walls.flatMap((wall) => floors.map((floor) => ({
    wall,
    floor,
    score: materialPairScore("wall", wall, pack, room) + materialPairScore("floor", floor, pack, room),
  }))).sort((left, right) => right.score - left.score)
    .slice(0, 1);
}

function repairAutomaticMaterialRecommendation(room, draft, pack) {
  if (!room || !draft || draft.materialSelectionMode === "custom") return false;
  const compatibleWalls = styleCompatibleMaterialOptionsForPack("wall", pack, room);
  const compatibleFloors = styleCompatibleMaterialOptionsForPack("floor", pack, room);
  const wallIsCompatible = compatibleWalls.some((option) => option.id === draft.wallMaterial);
  const floorIsCompatible = compatibleFloors.some((option) => option.id === draft.floorMaterial);
  if (wallIsCompatible && floorIsCompatible) return false;
  const pair = questionnaireMaterialPairsForPack(pack, room)[0];
  if (!pair) return false;
  Object.assign(draft, {
    wallMaterial: pair.wall.id,
    wallColor: pair.wall.color,
    defaultWallMaterial: pair.wall.id,
    defaultWallColor: pair.wall.color,
    wallOverrides: {},
    floorMaterial: pair.floor.id,
    floorColor: pair.floor.color,
    materialSelectionMode: "auto",
    confirmed: false,
  });
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (requirement) {
    requirement.confirmed = false;
    requirement.surfaces = {
      ...requirement.surfaces,
      paletteId: pack.id,
      materialSelectionMode: "auto",
      wallDefault: { materialId: pair.wall.id, color: pair.wall.color },
      wallOverrides: {},
      floor: { materialId: pair.floor.id, color: pair.floor.color },
    };
  }
  return true;
}

function questionnaireMaterialPairCards(pack) {
  const draft = activeRoomFinishDraft();
  const selectedWall = catalogMaterialOptionsForPack("wall", pack)
    .find((option) => option.id === draft.wallMaterial);
  const selectedFloor = catalogMaterialOptionsForPack("floor", pack)
    .find((option) => option.id === draft.floorMaterial);
  const recommendations = questionnaireMaterialPairsForPack(pack);
  if (!selectedWall || !selectedFloor) return recommendations;
  const current = {
    wall: { ...selectedWall, color: draft.wallColor || selectedWall.color },
    floor: { ...selectedFloor, color: draft.floorColor || selectedFloor.color },
    isCurrentSelection: true,
  };
  const currentIsRecommended = recommendations.some((pair) => (
    pair.wall.id === current.wall.id && pair.floor.id === current.floor.id
  ));
  if (currentIsRecommended) {
    return [current, ...recommendations.filter((pair) => (
      pair.wall.id !== current.wall.id || pair.floor.id !== current.floor.id
    ))].slice(0, 1);
  }
  return [...recommendations, { ...current, isCustomSelection: true }].slice(0, 1);
}

function renderQuestionnaireMaterialPairs(pack) {
  const draft = activeRoomFinishDraft();
  const pairs = questionnaireMaterialPairCards(pack);
  const host = element.questionnaireMaterialPairs;
  if (!host) return pairs;
  host.hidden = false;
  host.innerHTML = `
    <div class="rp-questionnaire-section-heading"><div><span class="eyebrow">本房推薦</span><h3>牆與地板搭配</h3></div><p>這是依房型與全屋風格產生的一組預設搭配；需要調整時，再從下方材質庫選擇。</p></div>
    <div class="rp-material-pair-grid">${pairs.map((pair, index) => `
      <button type="button" class="rp-material-pair-card ${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id ? "is-active" : ""}"
        data-questionnaire-material-pair="${index}" aria-pressed="${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id}">
        <canvas data-material-pair-preview aria-label="${escapeHtml(`${pair.wall.label} 與 ${pair.floor.label} 的立體搭配預覽`)}"></canvas>
        <span><strong>牆：${escapeHtml(pair.wall.label)}</strong><small>地：${escapeHtml(pair.floor.label)}</small>${pair.isCurrentSelection ? "<em>目前選擇</em>" : ""}${pair.isCustomSelection ? "<em>自訂選擇</em>" : ""}</span>
      </button>
    `).join("") || "<p class=\"rp-field-error\">找不到可搭配的牆面與地板材質，可改用下方自訂選擇。</p>"}</div>`;
  if (pairs.length) requestAnimationFrame(() => renderMaterialPairPreviews(host, pairs));
  return pairs;
}

function selectQuestionnaireMaterialPair(pair) {
  const draft = activeRoomFinishDraft();
  draft.wallMaterial = pair.wall.id;
  draft.wallColor = pair.wall.color;
  draft.floorMaterial = pair.floor.id;
  draft.floorColor = pair.floor.color;
  if (state.selectedQuestionnaireWallId) {
    draft.wallOverrides[state.selectedQuestionnaireWallId] = { materialId: draft.wallMaterial, color: draft.wallColor };
  } else {
    draft.defaultWallMaterial = draft.wallMaterial;
    draft.defaultWallColor = draft.wallColor;
  }
  draft.confirmed = false;
  draft.materialSelectionMode = "custom";
  draft.styleReviewRequired = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function renderQuestionnaireMaterialCatalog(kind, search = questionnaireMaterialCatalogSearch) {
  questionnaireMaterialCatalogKind = kind;
  questionnaireMaterialCatalogSearch = String(search || "").trim();
  const pack = activeQuestionnairePack();
  const allOptions = catalogMaterialOptionsForPack(kind, pack);
  const searchTerm = questionnaireMaterialCatalogSearch.toLowerCase();
  const typeCounts = allOptions.reduce((counts, option) => ({ ...counts, [materialCatalogType(option)]: (counts[materialCatalogType(option)] || 0) + 1 }), {});
  const colorCounts = allOptions.reduce((counts, option) => ({ ...counts, [materialCatalogColor(option)]: (counts[materialCatalogColor(option)] || 0) + 1 }), {});
  const options = allOptions.filter((option) =>
    (questionnaireMaterialCatalogType === "all" || materialCatalogType(option) === questionnaireMaterialCatalogType)
    && (questionnaireMaterialCatalogColor === "all" || materialCatalogColor(option) === questionnaireMaterialCatalogColor)
    && (!searchTerm || `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase().includes(searchTerm)),
  );
  const title = kind === "wall" ? "選擇本房牆面材質" : "選擇本房地板材質";
  element.questionnaireMaterialCatalogSource.hidden = true;
  element.questionnaireMaterialCatalogTitle.textContent = title;
  element.questionnaireMaterialCatalogHelp.textContent = "選取後先更新此房草稿；按確認此房才會寫入並套用到本房預覽。";
  element.questionnaireMaterialCatalogSearch.value = questionnaireMaterialCatalogSearch;
  renderMaterialFilterChips(element.questionnaireMaterialTypeFilters, MATERIAL_TYPE_LABELS, questionnaireMaterialCatalogType, typeCounts, "questionnaire-material-type");
  renderMaterialFilterChips(element.questionnaireMaterialColorFilters, MATERIAL_COLOR_LABELS, questionnaireMaterialCatalogColor, colorCounts, "questionnaire-material-color");
  element.questionnaireMaterialCatalogResultCount.textContent = searchTerm
    ? `找到 ${options.length} 項符合「${questionnaireMaterialCatalogSearch}」的材質`
    : `共 ${allOptions.length} 項材質，可用關鍵字縮小範圍`;
  element.questionnaireMaterialCatalogOptions.innerHTML = options.map((option) => `
    <button type="button" data-questionnaire-catalog-material="${escapeHtml(kind)}"
      data-questionnaire-catalog-material-id="${escapeHtml(option.id)}">
      <img src="${escapeHtml(option.materialPreview)}" alt="${escapeHtml(`${option.label} 材質樣本`)}" loading="lazy">
      <span><strong>${escapeHtml(option.label)}</strong><small>${escapeHtml(option.note)}</small></span>
    </button>
  `).join("") || "<p class=\"rp-field-error\">找不到符合的材質。請換個關鍵字，或回到推薦項目。</p>";
  if (!element.questionnaireMaterialCatalogDialog.open) {
    element.questionnaireMaterialCatalogDialog.showModal();
  }
}

function randomWholeHouseAnswers() {
  const note = randomItem(TEST_REQUIREMENT_PROFILE_NOTES, TEST_REQUIREMENT_PROFILE_NOTES[0]);
  return Object.fromEntries(WHOLE_HOUSE_QUESTIONS.map((question) => {
    if (question.type === "select") return [question.id, randomItem(question.options, "")];
    return [question.id, note];
  }));
}

function randomAnswerForQuestion(question) {
  const useBalanced = question.allow_both === true && Math.random() < 0.18;
  if (useBalanced) {
    return {
      optionId: "both",
      custom: "測試隨機：兩端需求都要保留，交給配置時依房間尺寸取捨。",
      preferenceWeight: 0,
      preferenceDirection: "balanced",
    };
  }
  const option = randomItem(question.options, question.options?.[0]);
  const optionIndex = Math.max(0, question.options?.indexOf(option) ?? 0);
  const preferenceWeight = optionIndex === 0 ? randomItem([-2, -1], -2) : randomItem([1, 2], 2);
  return {
    optionId: option?.option_id || "",
    custom: randomItem(TEST_REQUIREMENT_PROFILE_NOTES, ""),
    forcePlacement: true,
    preferenceWeight,
    preferenceDirection: preferenceWeight < 0 ? "a" : "b",
  };
}

function randomRoomAxisNote(room) {
  const axes = ROOM_REQUIREMENT_POLAR_AXES[room.type]
    || ROOM_REQUIREMENT_POLAR_AXES.default;
  return axes.map((axis) => {
    const side = Math.random() < 0.5 ? axis.left : axis.right;
    return `${axis.axis}:${side}`;
  });
}

function randomRoomFinishDraft() {
  const pack = randomItem(STYLE_PACKS, STYLE_PACKS[0]);
  const wallOption = randomItem(questionnaireMaterialOptionsForPack("wall", pack), null);
  const floorOption = randomItem(questionnaireMaterialOptionsForPack("floor", pack), null);
  const wallMaterial = wallOption?.id || pack.wall.surfaceOption;
  const wallColor = wallOption?.color || pack.wall.color;
  const floorMaterial = floorOption?.id || pack.floor.surfaceOption;
  const floorColor = floorOption?.color || pack.floor.color;
  const ceilingStyle = randomItem(
    CEILING_STYLES.filter((item) => item.styles.includes(pack.styleId)),
    CEILING_STYLES[0],
  );
  const lightStyle = randomItem(
    LIGHT_STYLES.filter((item) => item.styles.includes(pack.styleId)),
    LIGHT_STYLES[0],
  );
  return {
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial,
    wallColor,
    defaultWallMaterial: wallMaterial,
    defaultWallColor: wallColor,
    wallOverrides: {},
    floorMaterial,
    floorColor,
    ceilingMaterial: randomItem(["flat-paint", "mineral-paint", "wood-veneer", "exposed-concrete"], "flat-paint"),
    ceilingStyle: ceilingStyle.id,
    lightStyle: lightStyle.id,
    ceilingColor: randomItem(pack.palette, "#f4f1eb"),
    airConditioning: randomItem(TEST_AIR_CONDITIONING_OPTIONS, "wall-split"),
  };
}

function applyRandomRoomRequirement(room, draft) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return;
  const roomQuestions = state.visualQuestions.filter(
    (question) => String(question.room_id) === String(room.id),
  );
  const axisAnswers = Object.fromEntries(roomQuestions.map((question) => {
    const answer = randomAnswerForQuestion(question);
    state.visualAnswers[question.question_id] = answer;
    return [
      question.source_question_id || question.question_id,
      { ...answer },
    ];
  }));
  const axisNotes = randomRoomAxisNote(room);
  requirement.axisAnswers = axisAnswers;
  requirement.usage = roomUsageOptions(room)
    .slice(0, 1)
    .map((option) => option.id)
    .filter(Boolean);
  requirement.furniture = {
    required: axisNotes,
    optional: [],
  };
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
    materialSelectionMode: draft.materialSelectionMode || "auto",
    styleReviewRequired: false,
    wallPreference: draft.wallPreference || "",
    floorPreference: draft.floorPreference || "",
    wallDefault: {
      materialId: draft.defaultWallMaterial || draft.wallMaterial,
      color: draft.defaultWallColor || draft.wallColor,
    },
    wallOverrides: {},
    wallSurfaceIds: [],
    floor: {
      materialId: draft.floorMaterial,
      color: draft.floorColor,
    },
    ceiling: {
      materialId: draft.ceilingMaterial,
      styleId: draft.ceilingStyle,
      lightingId: draft.lightStyle,
      color: draft.ceilingColor,
    },
  };
  requirement.specialRequests = axisNotes;
  requirement.feasibility = [];
  requirement.confirmed = true;
}

async function randomizeRequirementsForTesting() {
  element.requirementsError.textContent = "";
  if (!state.rooms.length) {
    throw new Error("請先完成空間確認，才能帶入預設需求。");
  }
  try {
    await ensureVisualQuestionnaireLoaded();
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    throw error;
  }
  state.roomRequirementModel = normalizeRoomRequirements(
    state.roomRequirementModel,
    state.rooms,
    {
      basic: state.basicAnswers,
      basicConfirmed: state.basicConfirmed,
      finishes: state.questionnaireFinishes,
    },
  );
  state.basicAnswers = randomWholeHouseAnswers();
  state.basicConfirmed = true;
  state.roomRequirementModel.globalProfile = { ...state.basicAnswers };
  state.roomRequirementModel.globalConfirmed = true;
  state.visualAnswers = {};
  state.skippedVisualSpaceTypes = [];
  state.roomFinishDrafts = {};
  state.rooms.forEach((room) => {
    const draft = randomRoomFinishDraft();
    state.roomFinishDrafts[room.id] = { ...draft };
    applyRandomRoomRequirement(room, draft);
  });
  await Promise.all(state.rooms.map((room) => (
    ensureQuestionnaireFurnitureRecommendations(room, { force: true })
  )));
  // A test fill must reach the summary even if a room has no compatible GLB.
  // The missing-model reason is handled in Step 6 without blocking all rooms.
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (requirement) requirement.confirmed = true;
    if (state.roomFinishDrafts[room.id]) state.roomFinishDrafts[room.id].confirmed = true;
  });
  const firstRoomId = state.rooms[0]?.id;
  state.roomRequirementModel.activeRoomId = firstRoomId || null;
  state.questionnaireFinishes = {
    ...(state.roomFinishDrafts[firstRoomId] || randomRoomFinishDraft()),
    confirmed: true,
  };
  applyWholeHouseSurfaceConsistency();
  state.visualQuestionIndex = 0;
  state.selectedQuestionnaireWallId = null;
  state.questionnaireStage = "summary";
  invalidateDownstreamFrom("requirements", "已隨機產生測試需求，後續配置已標記需重新生成。");
  const firstPack = STYLE_PACKS.find((pack) => pack.id === state.questionnaireFinishes.stylePackId);
  if (firstPack) {
    state.activeStyleId = firstPack.styleId;
    state.activeStylePackId = firstPack.id;
  }
  renderWholeHouseQuestionnaire();
  renderVisualQuestionnaire();
  renderQuestionnaireFinishes();
  renderQuestionnaireSummary();
  showQuestionnaireStage("summary");
  setStatus("已隨機完成逐房需求、全屋資料、天花板、照明、冷氣與材質。");
  scheduleSave("requirements");
}

async function skipQuestionnaireWithDefaults() {
  const buttons = [
    element.randomizeRequirements,
    element.randomizeRequirementsSummary,
  ].filter(Boolean);
  if (!buttons.length || buttons.some((button) => button.disabled)) return;
  buttons.forEach((button) => {
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  });
  element.requirementsError.textContent = "";
  setStatus("正在帶入系統預設需求…");
  try {
    await randomizeRequirementsForTesting();
    setStatus("已帶入系統預設需求；可在摘要檢查或返回逐房修改。", "success");
  } catch (error) {
    const message = `無法帶入預設需求：${errorMessage(error)}`;
    element.requirementsError.textContent = message;
    setStatus(message, "error");
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    });
  }
}

async function prepareQuestionnaireStep() {
  if (!state.surfaceCatalog) {
    try {
      const bootstrap = await api("/api/scene/bootstrap");
      state.surfaceCatalog = bootstrap.surface_catalog || { surfaces: [] };
      state.surfaceCatalogProvider = bootstrap.catalog_status?.surfaces?.provider || "unknown";
      state.surfaceCatalogLoadError = null;
    } catch (error) {
      state.surfaceCatalog = { surfaces: [] };
      state.surfaceCatalogProvider = "unavailable";
      state.surfaceCatalogLoadError = errorMessage(error);
    }
  }
  state.roomRequirementModel = normalizeRoomRequirements(
    state.roomRequirementModel,
    state.rooms,
    {
      basic: state.basicAnswers,
      basicConfirmed: state.basicConfirmed,
      finishes: state.questionnaireFinishes,
    },
  );
  renderWholeHouseQuestionnaire();
  try {
    await ensureVisualQuestionnaireLoaded();
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    state.questionnaireStage = "profile";
  }
  showQuestionnaireStage(state.questionnaireStage);
}

function roomQuestionnaireProgress() {
  const rooms = state.rooms || [];
  const completed = rooms.filter((room) => roomQuestionnaireSectionProgress(room).confirmed).length;
  return {
    completed,
    total: rooms.length,
    ready: rooms.length > 0 && completed === rooms.length,
  };
}

function questionnaireStageUnlocked(stage) {
  if (stage === "profile") return true;
  if (stage === "rooms") return state.basicConfirmed;
  return roomQuestionnaireProgress().ready && state.basicConfirmed;
}

function showQuestionnaireStage(stage) {
  const requested = QUESTIONNAIRE_STAGES.includes(stage) ? stage : "profile";
  const nextStage = questionnaireStageUnlocked(requested) ? requested : "profile";
  state.questionnaireStage = nextStage;
  $$("[data-questionnaire-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.questionnairePanel !== nextStage;
  });
  $$("[data-questionnaire-stage]", element.questionnaireStageNav).forEach((button) => {
    const target = button.dataset.questionnaireStage;
    button.disabled = !questionnaireStageUnlocked(target);
    button.classList.toggle("is-active", target === nextStage);
    button.classList.toggle(
      "is-complete",
      QUESTIONNAIRE_STAGES.indexOf(target) < QUESTIONNAIRE_STAGES.indexOf(nextStage),
    );
  });
  const labels = {
    rooms: `逐房需求 ${roomQuestionnaireProgress().completed} / ${roomQuestionnaireProgress().total}`,
    profile: "全屋條件與主風格",
    summary: "確認方案",
  };
  element.requirementsProgress.textContent = labels[nextStage];
  element.requirementsError.textContent = "";
  if (nextStage === "rooms") {
    renderVisualQuestionnaire();
  } else if (nextStage === "profile") {
    renderWholeHouseQuestionnaire();
  } else if (nextStage === "summary") {
    renderQuestionnaireSummary();
  }
  scheduleSave("requirements");
}

async function ensureVisualQuestionnaireLoaded() {
  if (state.visualCatalog) {
    state.visualQuestions = [];
    state.visualAnswers = {};
    state.skippedVisualSpaceTypes = [];
    return;
  }
  const catalog = await api("/api/questionnaire/visual-catalog");
  const restoredCatalogVersion = state.visualCatalogVersion;
  state.visualCatalog = catalog;
  // The visual catalog remains available to RAG, but it is no longer a required
  // question-by-question user flow. Step 5 asks only for furniture and finishes.
  state.visualQuestions = [];
  if (
    restoredCatalogVersion
    && restoredCatalogVersion !== catalog.version
  ) {
    state.visualAnswers = {};
    state.skippedVisualSpaceTypes = [];
    state.questionnaireStage = "rooms";
    invalidateDownstreamFrom(
      "requirements",
      "推薦題庫已更新，後續 2D、3D 與渲染結果需要重新確認。",
    );
    setStatus("推薦題庫已更新，請重新確認家具與材質。");
  }
  state.visualCatalogVersion = catalog.version;
  state.visualAnswers = {};
  state.skippedVisualSpaceTypes = [];
  state.visualQuestionIndex = 0;
  $("#visual-questionnaire-notice").textContent = "";
}

function visualQuestionAt(index = state.visualQuestionIndex) {
  return state.visualQuestions[index] || null;
}

function answerWeightDirection(weight) {
  if (Number(weight) < 0) return "a";
  if (Number(weight) > 0) return "b";
  return "balanced";
}

function weightedOptionId(question, weight, currentOptionId = "") {
  if (!question?.options?.length) return currentOptionId;
  if (Number(weight) < 0) return question.options[0]?.option_id || currentOptionId;
  if (Number(weight) > 0) return question.options[1]?.option_id || currentOptionId;
  return question.allow_both ? "both" : (currentOptionId || question.options[0]?.option_id || "");
}

function preferenceWeightFromOption(question, optionId, fallback = null) {
  if (Number.isFinite(Number(fallback))) return Number(fallback);
  if (!question?.options?.length) return 0;
  if (optionId === "both") return 0;
  const index = question.options.findIndex((option) => option.option_id === optionId);
  if (index === 0) return -2;
  if (index === 1) return 2;
  return 0;
}

function preferenceWeightLabel(weight) {
  return PREFERENCE_WEIGHT_OPTIONS.find((item) => item.value === Number(weight))?.label || "";
}

function firstPendingQuestionIndex(roomId) {
  const roomQuestionIndexes = state.visualQuestions
    .map((question, index) => ({ question, index }))
    .filter(({ question }) => String(question.room_id) === String(roomId));
  return roomQuestionIndexes.find(
    ({ question }) => !state.visualAnswers[question.question_id]?.optionId,
  )?.index ?? roomQuestionIndexes[0]?.index ?? -1;
}

function resolvedVisualPreferences(questions = state.visualQuestions) {
  return questions.flatMap((question) => {
    if (state.skippedVisualSpaceTypes.includes(question.space_type)) return [];
    const answer = state.visualAnswers[question.question_id];
    if (!answer?.optionId) return [];
    const option = question.options.find(
      (candidate) => candidate.option_id === answer.optionId,
    );
    return [{
      question_id: question.question_id,
      space_type: question.space_type,
      option_id: answer.optionId,
      custom: answer.custom || "",
      special_request: answer.specialRequest === true,
      force_placement: answer.forcePlacement !== false,
      preference_weight: Number(answer.preferenceWeight ?? 0),
      preference_direction: answer.preferenceDirection
        || answerWeightDirection(answer.preferenceWeight),
      engine_effects: answer.forcePlacement === false ? {} : (option?.engine_effects || {}),
    }];
  });
}

function visualPreferencesForRoom(room) {
  return resolvedVisualPreferences(
    state.visualQuestions.filter(
      (question) => String(question.room_id) === String(room.id),
    ),
  );
}

function saveVisualCustomAnswer() {
  const question = visualQuestionAt();
  if (!question) return false;
  const custom = element.visualCustomAnswer.value.trim();
  const previous = state.visualAnswers[question.question_id];
  if (!custom && !previous) return false;
  if ((previous?.custom || "") === custom) return false;
  state.visualAnswers[question.question_id] = {
    ...(previous || {}),
    custom,
  };
  return true;
}

function activeQuestionnaireRoom() {
  const roomId = state.roomRequirementModel?.activeRoomId
    || state.rooms[0]?.id;
  return state.rooms.find((room) => String(room.id) === String(roomId)) || state.rooms[0] || null;
}

function activeRoomRequirement() {
  const room = activeQuestionnaireRoom();
  return room
    ? state.roomRequirementModel?.roomRequirements?.[room.id]
    : null;
}

function renderQuestionnairePlan() {
  if (!element.questionnairePlanImage?.naturalWidth) return;
  syncOverlayToImage(
    element.questionnairePlanStage,
    element.questionnairePlanImage,
    element.questionnairePlanOverlay,
  );
  const activeRoom = activeQuestionnaireRoom();
  const polygons = state.rooms.map((room) => {
    const active = room.id === activeRoom?.id;
    const center = cmToPixel(roomCenter(room));
    return `
      <g data-questionnaire-room="${escapeHtml(room.id)}">
        <polygon points="${roomPolygonSvg(room)}"
          fill="${active ? "rgba(47,111,135,.24)" : "rgba(36,107,85,.08)"}"
          stroke="${active ? "#2f6f87" : "#5b786d"}" stroke-width="${active ? 6 : 3}"/>
        <text x="${center.x}" y="${center.y}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="7" paint-order="stroke"
          font-size="22" font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>
      </g>
    `;
  }).join("");
  const wallSegments = activeRoom?.polygon_cm?.map((point, index, polygon) => {
    const start = cmToPixel(point);
    const end = cmToPixel(polygon[(index + 1) % polygon.length]);
    const wallId = `${activeRoom.id}:wall:${index}`;
    const selected = state.selectedQuestionnaireWallId === wallId;
    return `<line data-questionnaire-wall="${escapeHtml(wallId)}"
      x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="${selected ? "#bd5c36" : "transparent"}" stroke-width="16"
      class="rp-questionnaire-wall-hit"/>`;
  }).join("") || "";
  element.questionnairePlanOverlay.innerHTML = `${polygons}${wallSegments}`;
}

function renderVisualSpaceNav() {
  const currentRoomId = activeQuestionnaireRoom()?.id;
  element.visualSpaceNav.innerHTML = state.rooms.map((room) => {
    const progress = roomQuestionnaireSectionProgress(room);
    const furnitureCount = roomFurnitureRequirement(room.id)?.selected?.length || 0;
    const ragStatus = state.roomRagJobs?.[room.id]?.status || "";
    const roomState = progress.confirmed
      ? (ragStatus === "queued" || ragStatus === "running" ? "rag-pending" : "confirmed")
      : (progress.complete ? "ready" : "draft");
    return `
      <button type="button" data-visual-room="${escapeHtml(room.id)}"
        class="${room.id === currentRoomId ? "is-active" : ""} is-${roomState}"
        aria-current="${room.id === currentRoomId ? "true" : "false"}">
        <strong>${escapeHtml(room.label)}</strong>
        <i class="rp-room-nav-state" aria-hidden="true"></i>
        <small>${progress.confirmed ? "本房需求已確認" : (progress.complete ? "待使用者確認" : `需求填寫中・${furnitureCount} 件家具`)}</small>
      </button>
    `;
  }).join("");
}

function activeRoomPreferenceSuggestion() {
  const room = activeQuestionnaireRoom();
  const requirement = room
    ? state.roomRequirementModel?.roomRequirements?.[room.id]
    : null;
  const suggestedQuestions = state.visualQuestions.filter(
    (question) => String(question.room_id) === String(room?.id)
      && state.visualAnswers[question.question_id]?.suggested === true,
  );
  if (!requirement?.preferenceSuggestion || suggestedQuestions.length === 0) return null;
  return {
    ...requirement.preferenceSuggestion,
    count: suggestedQuestions.length,
    firstQuestionIndex: state.visualQuestions.indexOf(suggestedQuestions[0]),
  };
}

function renderRoomPreferenceSuggestion() {
  const suggestion = activeRoomPreferenceSuggestion();
  element.roomPreferenceSuggestion.hidden = !suggestion;
  if (!suggestion) {
    element.roomPreferenceSuggestion.innerHTML = "";
    return;
  }
  element.roomPreferenceSuggestion.innerHTML = `
    <div>
      <strong>已依「${escapeHtml(suggestion.sourceRoomLabel)}」預選 ${suggestion.count} 題</strong>
      <p>共通偏好與風格材質已先帶入；房間專屬需求仍需由你確認。</p>
    </div>
    <button type="button" class="secondary-action" data-review-suggested-preferences
      data-question-index="${suggestion.firstQuestionIndex}">查看預選</button>
  `;
}

function renderVisualQuestionnaire() {
  const room = activeQuestionnaireRoom();
  if (!room) return;
  element.visualQuestionCard.hidden = true;
  element.visualQuestionCard.replaceChildren();
  renderVisualSpaceNav();
  state.roomRequirementModel.activeRoomId = room.id;
  renderQuestionnairePlan();
  renderQuestionnaireFinishes();
}

function selectVisualOption(optionId, {
  specialRequest = false,
  forcePlacement = true,
  custom = element.visualCustomAnswer.value.trim(),
  preferenceWeight = null,
} = {}) {
  const question = visualQuestionAt();
  if (!question) return;
  const weight = preferenceWeightFromOption(question, optionId, preferenceWeight);
  state.skippedVisualSpaceTypes = state.skippedVisualSpaceTypes.filter(
    (spaceType) => spaceType !== question.space_type,
  );
  state.visualAnswers[question.question_id] = {
    optionId,
    custom,
    specialRequest,
    forcePlacement,
    preferenceWeight: weight,
    preferenceDirection: answerWeightDirection(weight),
  };
  renderVisualQuestionnaire();
  invalidateDownstreamFrom("requirements", "視覺偏好已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
}

function selectPreferenceWeight(weight) {
  const question = visualQuestionAt();
  if (!question) return;
  const parsed = Number(weight);
  if (!Number.isFinite(parsed)) return;
  const previous = state.visualAnswers[question.question_id] || {};
  const optionId = weightedOptionId(question, parsed, previous.optionId);
  selectVisualOption(optionId, {
    ...previous,
    custom: element.visualCustomAnswer.value.trim(),
    preferenceWeight: parsed,
  });
}

function moveVisualQuestion(offset) {
  if (saveVisualCustomAnswer()) scheduleSave("requirements");
  const question = visualQuestionAt();
  const skipped = state.skippedVisualSpaceTypes.includes(question?.space_type);
  if (offset > 0 && !state.visualAnswers[question?.question_id]?.optionId && !skipped) {
    element.requirementsError.textContent = "請先選擇一個方向，或將這個空間標示為暫不作答。";
    return;
  }
  element.requirementsError.textContent = "";
  const roomId = question?.room_id;
  const roomQuestionIndexes = state.visualQuestions
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => String(candidate.room_id) === String(roomId))
    .map(({ index }) => index);
  const roomPosition = roomQuestionIndexes.indexOf(state.visualQuestionIndex);
  const nextIndex = offset > 0
    ? roomQuestionIndexes
      .slice(roomPosition + 1)
      .find((index) => !state.visualAnswers[state.visualQuestions[index].question_id]?.optionId)
    : roomQuestionIndexes[roomPosition + offset];
  if (Number.isInteger(nextIndex)) {
    state.visualQuestionIndex = nextIndex;
    renderVisualQuestionnaire();
    return;
  }
  if (offset > 0) {
    $("#questionnaire-finishes").scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function prefillRemainingRoomPreferences(sourceRoom) {
  const sourceRequirement =
    state.roomRequirementModel?.roomRequirements?.[sourceRoom.id];
  if (!sourceRequirement) return 0;
  let totalSuggested = 0;
  state.rooms
    .filter(
      (room) => room.id !== sourceRoom.id
        && state.roomRequirementModel.roomRequirements[room.id]?.confirmed !== true,
    )
    .forEach((targetRoom) => {
      const suggestions = suggestSharedRoomAnswers({
        questions: state.visualQuestions,
        answers: state.visualAnswers,
        sourceRoomId: sourceRoom.id,
        targetRoomId: targetRoom.id,
      });
      const suggestionCount = Object.keys(suggestions).length;
      if (suggestionCount === 0) return;
      Object.assign(state.visualAnswers, suggestions);
      totalSuggested += suggestionCount;

      const targetRequirement =
        state.roomRequirementModel.roomRequirements[targetRoom.id];
      if (!targetRequirement.surfaces?.paletteId && sourceRequirement.surfaces?.paletteId) {
        targetRequirement.surfaces = {
          ...structuredClone(sourceRequirement.surfaces),
          wallSurfaceIds: [],
          wallOverrides: {},
        };
        delete state.roomFinishDrafts[targetRoom.id];
      }
      targetRequirement.preferenceSuggestion = {
        sourceRoomId: String(sourceRoom.id),
        sourceRoomLabel: sourceRoom.label,
      };
    });
  return totalSuggested;
}

function skipCurrentVisualSpace() {
  const question = visualQuestionAt();
  if (!question) return;
  state.visualQuestions
    .filter((candidate) => candidate.space_type === question.space_type)
    .forEach((candidate) => delete state.visualAnswers[candidate.question_id]);
  if (!state.skippedVisualSpaceTypes.includes(question.space_type)) {
    state.skippedVisualSpaceTypes.push(question.space_type);
  }
  const nextIndex = state.visualQuestions.findIndex(
    (candidate, index) => index > state.visualQuestionIndex
      && candidate.space_type !== question.space_type,
  );
  state.visualQuestionIndex = nextIndex >= 0
    ? nextIndex
    : state.visualQuestions.length - 1;
  renderVisualQuestionnaire();
  scheduleSave("requirements");
}

function wholeHouseStylePack() {
  return STYLE_PACKS.find((pack) => pack.id === state.questionnaireFinishes?.stylePackId)
    || STYLE_PACKS.find((pack) => pack.id === state.activeStylePackId)
    || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
}

function activeQuestionnairePack() {
  return wholeHouseStylePack();
}

function activeRoomFinishDraft() {
  const requirement = activeRoomRequirement();
  const roomId = requirement?.roomId;
  if (!roomId) return state.questionnaireFinishes;
  if (!state.roomFinishDrafts[roomId]) {
    const surfaces = requirement.surfaces || {};
    state.roomFinishDrafts[roomId] = {
      confirmed: requirement.confirmed === true,
      materialSelectionMode: surfaces.materialSelectionMode || "auto",
      styleReviewRequired: surfaces.styleReviewRequired === true,
      stylePackId: surfaces.paletteId || null,
      wallMaterial: surfaces.wallDefault?.materialId || null,
      wallColor: surfaces.wallDefault?.color || null,
      defaultWallMaterial: surfaces.wallDefault?.materialId || null,
      defaultWallColor: surfaces.wallDefault?.color || null,
      wallOverrides: { ...(surfaces.wallOverrides || {}) },
      wallPreference: surfaces.wallPreference || "",
      floorMaterial: surfaces.floor?.materialId || null,
      floorColor: surfaces.floor?.color || null,
      floorPreference: surfaces.floorPreference || "",
      ceilingMaterial: surfaces.ceiling?.materialId || null,
      ceilingStyle: surfaces.ceiling?.styleId || null,
      lightStyle: surfaces.ceiling?.lightingId || null,
      ceilingColor: surfaces.ceiling?.color || "#f4f1eb",
      airConditioning: requirement.climate?.airConditioning || "",
    };
  }
  // Style identity is global. A room may vary its compatible finishes, never
  // its style pack.
  const draft = state.roomFinishDrafts[roomId];
  const pack = wholeHouseStylePack();
  draft.stylePackId = pack.id;
  // Existing projects can have drafts created before ceiling defaults were
  // persisted. Treat the compatible global defaults as selected instead of
  // blocking the user on a field that already has a visible recommendation.
  draft.ceilingMaterial ||= "flat-paint";
  draft.ceilingStyle ||= recommendedCeilingStyleForPack(pack);
  draft.lightStyle ||= recommendedLightStyleForPack(pack);
  return draft;
}

function renderQuestionnaireMaterialOptions(kind, pack) {
  const draft = activeRoomFinishDraft();
  const host = kind === "wall"
    ? element.questionnaireWallOptions
    : element.questionnaireFloorOptions;
  const selectedKey = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const options = questionnaireMaterialOptionsForPack(kind, pack);
  host.innerHTML = options.map((option) => `
    <button type="button" data-questionnaire-material="${escapeHtml(kind)}"
      data-questionnaire-material-id="${escapeHtml(option.id)}"
      class="${draft[selectedKey] === option.id ? "is-active" : ""}"
      aria-pressed="${draft[selectedKey] === option.id}">
      <span class="rp-material-preview" style="background-color:${escapeHtml(option.color)};background-image:url('${escapeHtml(option.materialPreview)}')"></span>
      <strong>${escapeHtml(option.label)}</strong>
       <small>${escapeHtml(option.note)}<em>推薦</em></small>
    </button>
  `).join("") || `<p class="rp-field-error">找不到符合目前條件的${kind === "wall" ? "牆面" : "地板"}材質，可調整需求後重試。</p>`;
}

function roomQuestionnaireSectionProgress(room) {
  const requirement = state.roomRequirementModel?.roomRequirements?.[room?.id] || {};
  const surfaces = requirement.surfaces || {};
  const ceiling = surfaces.ceiling || {};
  const usage = room ? ensureRoomUsage(room) : [];
  const furnitureCount = roomFurnitureRequirement(room?.id)?.selected?.length || 0;
  const furnitureRequired = questionnaireFurnitureProgram(room).required.length > 0;
  const sections = {
    usage: usage.length > 0,
    furniture: !furnitureRequired || furnitureCount > 0,
    surfaces: Boolean(surfaces.wallDefault?.materialId && surfaces.floor?.materialId),
    ceiling: Boolean(ceiling.styleId && ceiling.lightingId),
  };
  const complete = Object.values(sections).every(Boolean);
  return {
    sections,
    complete,
    confirmed: complete && requirement.confirmed === true,
  };
}

function questionnaireUsageSummary(room) {
  const selected = new Set(ensureRoomUsage(room));
  return roomUsageOptions(room)
    .filter((option) => selected.has(option.id))
    .map((option) => option.label)
    .join("、") || "待設定";
}

const QUESTIONNAIRE_ROOM_SECTIONS = Object.freeze([
  { id: "usage", label: "房間用途", summary: questionnaireUsageSummary },
  { id: "furniture", label: "家具配置", summary: (room) => `${roomFurnitureRequirement(room?.roomId)?.selected?.length || 0} 件家具` },
  { id: "surfaces", label: "牆面與地板", summary: (room) => room?.surfaces?.wallDefault?.materialId && room?.surfaces?.floor?.materialId ? "已選搭配" : "待設定" },
  { id: "ceiling", label: "天花與照明", summary: (room) => room?.surfaces?.ceiling?.styleId && room?.surfaces?.ceiling?.lightingId ? "已選搭配" : "待設定" },
  { id: "review", label: "檢查並確認", summary: (room) => room?.confirmed ? "本房已確認" : "確認後儲存" },
]);

function questionnaireRoomEditorElements() {
  return {
    editor: $(".rp-room-questionnaire-editor"),
    nav: $("#questionnaire-room-section-nav"),
    title: $("#questionnaire-active-room-title"),
    saveState: $("#questionnaire-room-save-state"),
  };
}

function ensureQuestionnaireRoomActionBar() {
  const editor = questionnaireRoomEditorElements().editor;
  if (!editor) return null;
  let bar = $("#questionnaire-room-action-bar", editor);
  if (bar) return bar;
  bar = document.createElement("footer");
  bar.id = "questionnaire-room-action-bar";
  bar.className = "rp-questionnaire-room-action-bar";
  bar.innerHTML = `<p id="questionnaire-room-action-status"></p><div><button id="questionnaire-room-section-back" type="button" class="secondary-action">上一區</button><button id="questionnaire-room-section-next" type="button" class="primary-action">下一區</button></div>`;
  editor.append(bar);
  $("#questionnaire-room-section-back", bar).addEventListener("click", () => moveQuestionnaireRoomSection(-1));
  $("#questionnaire-room-section-next", bar).addEventListener("click", () => moveQuestionnaireRoomSection(1));
  return bar;
}

function renderQuestionnaireRoomReview(room, requirement) {
  let review = $("#questionnaire-room-review");
  if (!review) {
    review = document.createElement("section");
    review.id = "questionnaire-room-review";
    review.className = "rp-questionnaire-room-review";
    review.dataset.roomSectionPanel = "review";
    $("#questionnaire-finishes")?.append(review);
  }
  const draft = activeRoomFinishDraft();
  const furniture = roomFurnitureRequirement(room?.id)?.selected || [];
  const lines = [
    ["用途", questionnaireUsageSummary(room), "usage"],
    ["家具", furniture.length ? `${furniture.length} 件已加入配置` : "尚未選擇", "furniture"],
    ["牆面與地板", draft.wallMaterial && draft.floorMaterial ? `已選牆地搭配${draft.wallPreference || draft.floorPreference ? "，含生圖偏好" : ""}` : "尚未選擇", "surfaces"],
    ["天花與照明", draft.ceilingStyle && draft.lightStyle ? "已選相容搭配" : "尚未選擇", "ceiling"],
  ];
  const pack = activeQuestionnairePack();
  const wall = catalogMaterialOptionsForPack("wall", pack).find((item) => item.id === draft.wallMaterial);
  const floor = catalogMaterialOptionsForPack("floor", pack).find((item) => item.id === draft.floorMaterial);
  const ceiling = CEILING_STYLES.find((item) => item.id === draft.ceilingStyle);
  const lighting = LIGHT_STYLES.find((item) => item.id === draft.lightStyle);
  const furnitureImages = furniture
    .map((item) => ({
      label: item.name_zh || item.name_zh_raw || item.name_en || "家具",
      url: item.image_url || item.thumbnail_url || item.preview_url || "",
    }))
    .filter((item) => item.url)
    .slice(0, 3);
  const visualSummary = `<section class="rp-room-review-preview" aria-label="本房已選項目預覽">
    <article class="rp-room-review-finish"><span class="rp-room-review-material" style="background-color:${escapeHtml(wall?.color || draft.wallColor || "#f4f1eb")};background-image:url('${escapeHtml(wall?.materialPreview || "")}')"></span><div><small>牆面</small><strong>${escapeHtml(wall?.label || "尚未選擇")}</strong></div></article>
    <article class="rp-room-review-finish"><span class="rp-room-review-material" style="background-color:${escapeHtml(floor?.color || draft.floorColor || "#d5d0c7")};background-image:url('${escapeHtml(floor?.materialPreview || "")}')"></span><div><small>地板</small><strong>${escapeHtml(floor?.label || "尚未選擇")}</strong></div></article>
    <article class="rp-room-review-ceiling"><span class="rp-ceiling-choice-visual" data-ceiling-style-visual="${escapeHtml(ceiling?.id || "flat")}"></span><div><small>天花／照明</small><strong>${escapeHtml(`${ceiling?.label || "尚未選擇"}／${lighting?.label || "尚未選擇"}`)}</strong></div></article>
    <article class="rp-room-review-furniture"><div class="rp-room-review-furniture-images">${furnitureImages.map((item) => `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.label)}">`).join("") || "<span>尚無商品圖片</span>"}</div><div><small>已選家具</small><strong>${furniture.length ? `${furniture.length} 件加入配置` : "尚未選擇"}</strong></div></article>
  </section>`;
  review.innerHTML = `<div class="rp-questionnaire-section-heading"><div><span class="eyebrow">最後檢查</span><h3>確認${escapeHtml(room?.label || "本房")}需求</h3></div><p>確認後會儲存本房需求；第 6 步才會統一產生 A／B 的 2D＋3D 配置，並驗證家具碰撞、門片與走道淨空。</p></div>${visualSummary}<div class="rp-room-review-list">${lines.map(([label, value, target]) => `<button type="button" data-questionnaire-room-section="${target}"><span>${label}</span><strong>${escapeHtml(value)}</strong><em>編輯</em></button>`).join("")}</div>`;
}

function renderQuestionnaireRoomSections() {
  const room = activeQuestionnaireRoom();
  const requirement = activeRoomRequirement();
  const { editor, nav, title, saveState } = questionnaireRoomEditorElements();
  if (!room || !requirement || !editor || !nav) return;
  const validSection = QUESTIONNAIRE_ROOM_SECTIONS.some((section) => section.id === questionnaireRoomSection);
  if (!validSection) questionnaireRoomSection = "usage";
  const currentIndex = QUESTIONNAIRE_ROOM_SECTIONS.findIndex((section) => section.id === questionnaireRoomSection);
  const progress = roomQuestionnaireSectionProgress(room);
  const confirmed = progress.confirmed;
  title.textContent = `${room.label}需求`;
  saveState.textContent = confirmed
    ? "本房需求已確認"
    : (progress.complete ? "資料完整，尚待確認" : "自動暫存，需求未完成");
  editor.dataset.roomSection = questionnaireRoomSection;
  nav.innerHTML = QUESTIONNAIRE_ROOM_SECTIONS.map((section, index) => {
    const complete = section.id === "review"
      ? confirmed
      : progress.sections[section.id] === true;
    const active = section.id === questionnaireRoomSection;
    return `<button type="button" data-questionnaire-room-section="${section.id}" class="${active ? "is-active" : ""} ${complete ? "is-complete" : ""}" aria-current="${active ? "step" : "false"}"><b>${complete ? "✓" : index + 1}</b><span><strong>${section.label}</strong><small>${escapeHtml(section.summary(requirement))}</small></span></button>`;
  }).join("");
  renderQuestionnaireRoomReview(room, requirement);
  const bar = ensureQuestionnaireRoomActionBar();
  const actionStatus = $("#questionnaire-room-action-status", bar);
  const back = $("#questionnaire-room-section-back", bar);
  const next = $("#questionnaire-room-section-next", bar);
  actionStatus.textContent = confirmed
    ? "本房資料已確認"
    : (progress.complete ? "資料完整，等待使用者確認" : "自動暫存，尚未完成");
  back.hidden = currentIndex === 0;
  next.hidden = questionnaireRoomSection === "review";
  const nextSection = QUESTIONNAIRE_ROOM_SECTIONS[currentIndex + 1];
  next.textContent = nextSection ? `下一步：${nextSection.label}` : "下一區";
  const confirm = $("#confirm-questionnaire-finishes");
  if (confirm) {
    bar.querySelector("div")?.append(confirm);
    confirm.hidden = questionnaireRoomSection !== "review";
    confirm.textContent = confirmed ? "更新本房確認" : `確認${room.label}並前往下一房`;
  }
}

function moveQuestionnaireRoomSection(offset) {
  const index = QUESTIONNAIRE_ROOM_SECTIONS.findIndex((section) => section.id === questionnaireRoomSection);
  const next = QUESTIONNAIRE_ROOM_SECTIONS[index + offset];
  if (!next) return;
  questionnaireRoomSection = next.id;
  renderQuestionnaireRoomSections();
  $(".rp-room-questionnaire-editor")?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function selectQuestionnaireMaterial(kind, materialId) {
  const key = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const colorKey = kind === "wall" ? "wallColor" : "floorColor";
  const draft = activeRoomFinishDraft();
  draft[key] = materialId;
  const option = catalogMaterialOptionsForPack(kind, activeQuestionnairePack())
    .find((candidate) => candidate.id === materialId);
  if (option?.color) draft[colorKey] = option.color;
  if (kind === "wall") {
    if (state.selectedQuestionnaireWallId) {
      draft.wallOverrides[state.selectedQuestionnaireWallId] = {
        materialId: draft.wallMaterial,
        color: draft.wallColor,
      };
    } else {
      draft.defaultWallMaterial = draft.wallMaterial;
      draft.defaultWallColor = draft.wallColor;
    }
  }
  draft.confirmed = false;
  draft.materialSelectionMode = "custom";
  draft.styleReviewRequired = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function ceilingPickerItems(kind) {
  return kind === "style" ? CEILING_STYLES : LIGHT_STYLES;
}

function renderQuestionnaireCeilingQuickChoices(draft) {
  const pack = activeQuestionnairePack();
  const options = [...CEILING_DESIGN_PACKS].sort((left, right) => {
    const leftPreferred = left.styles.includes(pack.styleId) ? 1 : 0;
    const rightPreferred = right.styles.includes(pack.styleId) ? 1 : 0;
    return rightPreferred - leftPreferred;
  });
  const groups = CEILING_STYLES.map((ceiling) => ({
    ceiling,
    designs: options.filter((option) => option.ceilingStyle === ceiling.id),
  })).filter((group) => group.designs.length);
  element.questionnaireCeilingQuickChoices.innerHTML = `
    <div class="rp-questionnaire-section-heading"><div><h3>天花施工形式</h3></div><p>先選施工形式；再於下一個視窗選相容的材質與照明搭配。</p></div>
    <div class="rp-ceiling-design-packs">${groups.map(({ ceiling, designs }) => {
      const active = draft.ceilingStyle === ceiling.id;
      return `<button type="button" class="rp-ceiling-design-pack ${active ? "is-active" : ""}" data-open-questionnaire-ceiling-design-style="${escapeHtml(ceiling.id)}" aria-pressed="${active}">
        <span class="rp-ceiling-choice-visual" data-ceiling-style-visual="${escapeHtml(ceiling.id)}"></span>
        <span><strong>${escapeHtml(ceiling.label)}</strong><small>${designs.length} 組相容材質與照明搭配</small><em>選擇搭配</em></span>
      </button>`;
    }).join("")}</div>
  `;
}

function openQuestionnaireCeilingDesignStyle(styleId) {
  const ceiling = CEILING_STYLES.find((item) => item.id === styleId);
  const designs = CEILING_DESIGN_PACKS.filter((item) => item.ceilingStyle === styleId);
  const draft = activeRoomFinishDraft();
  element.questionnaireCeilingPickerTitle.textContent = `${ceiling?.label || "天花"}搭配`;
  element.questionnaireCeilingPickerHelp.textContent = "每張卡的材質、天花形式與照明已經過相容檢查，選取後一次套用三項。";
  element.questionnaireCeilingPickerOptions.innerHTML = designs.map((design) => {
    const active = draft.ceilingMaterial === design.material && draft.ceilingStyle === design.ceilingStyle && draft.lightStyle === design.lightStyle;
    const lighting = LIGHT_STYLES.find((item) => item.id === design.lightStyle);
    return `<button type="button" class="rp-ceiling-picker-card ${active ? "is-active" : ""}" data-questionnaire-ceiling-design-pack="${escapeHtml(design.id)}" aria-pressed="${active}">
      <span class="rp-ceiling-choice-visual" data-ceiling-style-visual="${escapeHtml(design.ceilingStyle)}"></span>
      <strong>${escapeHtml(design.label)}</strong><small>照明：${escapeHtml(lighting?.label || "未指定")}</small>
    </button>`;
  }).join("");
  element.questionnaireCeilingPickerDialog.showModal();
}

function selectQuestionnaireCeilingDesignPack(packId) {
  const design = CEILING_DESIGN_PACKS.find((item) => item.id === packId);
  if (!design) return;
  const draft = activeRoomFinishDraft();
  draft.ceilingMaterial = design.material;
  draft.ceilingStyle = design.ceilingStyle;
  draft.lightStyle = design.lightStyle;
  draft.confirmed = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function openQuestionnaireCeilingPicker(kind) {
  questionnaireCeilingPickerKind = kind;
  const isCeiling = kind === "style";
  const selectedId = isCeiling
    ? activeRoomFinishDraft().ceilingStyle
    : activeRoomFinishDraft().lightStyle;
  const items = ceilingPickerItems(kind);
  element.questionnaireCeilingPickerTitle.textContent = isCeiling
    ? "選擇天花板形式"
    : "選擇照明形式";
  element.questionnaireCeilingPickerHelp.textContent = isCeiling
    ? "照片用來比較施工形式；選取後會保留在本房草稿，確認本房才會套用。"
    : "照片用來比較光感與燈具形式；選取後會保留在本房草稿，確認本房才會套用。";
  element.questionnaireCeilingPickerOptions.innerHTML = items.map((item) => `
    <button type="button" class="rp-ceiling-picker-card ${item.id === selectedId ? "is-active" : ""}"
      data-questionnaire-ceiling-picker-item="${escapeHtml(item.id)}" aria-pressed="${item.id === selectedId}">
      <span class="${isCeiling ? "rp-ceiling-choice-visual" : "rp-light-choice-visual"}"
        data-${isCeiling ? "ceiling" : "light"}-style-visual="${escapeHtml(item.id)}"></span>
      <strong>${escapeHtml(item.label)}</strong>
    </button>
  `).join("");
  element.questionnaireCeilingPickerDialog.showModal();
}

function selectQuestionnaireCeilingPickerItem(itemId) {
  if (!questionnaireCeilingPickerKind) return;
  const key = questionnaireCeilingPickerKind === "style" ? "ceilingStyle" : "lightStyle";
  const draft = activeRoomFinishDraft();
  draft[key] = itemId;
  draft.confirmed = false;
  element.questionnaireCeilingPickerDialog.close();
  questionnaireCeilingPickerKind = null;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function renderQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  if (room && isCirculationRoom(room)) copyLivingRoomStyleToCirculation(room);
  const draft = activeRoomFinishDraft();
  if (!room || !draft) return;
  const legacyFinishShell = [
    $("#questionnaire-finishes"),
    $("#room-finish-title"),
    $("#confirm-questionnaire-finishes"),
    element.questionnaireStyleTabs,
    element.questionnaireStyleGrid,
    element.questionnaireMaterialGrid,
    element.questionnaireWallColor,
    element.questionnaireFloorColor,
    element.questionnaireWallPreference,
    element.questionnaireFloorPreference,
    element.questionnaireCeilingMaterial,
    element.questionnaireCeilingStyle,
    element.questionnaireLightStyle,
    element.questionnaireCeilingColor,
    element.questionnaireAirConditioning,
    element.questionnaireFinishScope,
    element.questionnaireFinishRoomTargets,
    element.selectedWallSurface,
  ];
  if (legacyFinishShell.some((control) => !control)) return;
  const pack = activeQuestionnairePack();
  if (repairAutomaticMaterialRecommendation(room, draft, pack)) {
    scheduleSave("requirements");
  }
  const roomNeedsOnly = false;
  const circulationLocked = isCirculationRoom(room) && !circulationStyleIsOverridden(room);
  $("#questionnaire-finishes").classList.toggle("is-room-needs-only", roomNeedsOnly);
  $("#room-finish-title").textContent = `${room.label}規劃`;
  $("#questionnaire-finishes .rp-questionnaire-section-heading > p").textContent = "選用途與家具；材質和照明在下方調整。";
  element.circulationStyleNotice.hidden = !isCirculationRoom(room) || roomNeedsOnly;
  if (isCirculationRoom(room) && !roomNeedsOnly) {
    const livingRoom = livingRoomForCirculation();
    element.circulationStyleNotice.querySelector("strong").textContent = circulationLocked
      ? `走道沿用${livingRoom?.label || "客廳"}風格`
      : "走道使用獨立風格";
    element.circulationStyleNotice.querySelector("p").textContent = circulationLocked
      ? `走道會同步${livingRoom?.label || "客廳"}的牆面、地板、天花板與照明，讓全屋動線保持連續。`
      : "你已選擇走道獨立風格；第 6 步會保留這項設定並重新檢查銜接。";
    element.enableCirculationStyleOverride.hidden = !circulationLocked;
  }
  $("#confirm-questionnaire-finishes").textContent = `確認${room.label}的用途、家具與材質`;
  element.questionnaireStyleTabs.hidden = true;
  element.questionnaireStyleGrid.hidden = false;
  element.questionnaireStyleGrid.classList.add("is-fixed-style");
  element.questionnaireMaterialGrid.hidden = false;
  renderQuestionnaireRoomUsage(room);
  renderGenerativeEquipment(room);
  renderQuestionnaireFurnitureRecommendations(room);
  void ensureQuestionnaireFurnitureRecommendations(room);
  const stylePreview = roomNeedsOnly ? wholeHouseFinishDraft() : draft;
  const previewPack = STYLE_PACKS.find((candidate) => candidate.id === stylePreview.stylePackId)
    || STYLE_PACKS.find((candidate) => candidate.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
  const family = STYLE_FAMILIES.find((item) => item.id === previewPack.styleId) || STYLE_FAMILIES[0];
  element.questionnaireStyleTabs.replaceChildren();
  element.questionnaireStyleGrid.innerHTML = `
    <article class="rp-fixed-style-reference">
      <img class="rp-style-card-preview" src="${escapeHtml(family.referenceImage)}"
        alt="${escapeHtml(`${family.label} 台灣住宅風格參考圖`)}" loading="lazy">
      <div><span class="eyebrow">已選全屋主風格</span><strong>${escapeHtml(family.label)}</strong><small>逐房僅調整相容的牆面、地板、天花與照明；色卡將在第 7 步統一選擇。</small></div>
    </article>
  `;
  renderQuestionnaireMaterialOptions("wall", pack);
  renderQuestionnaireMaterialOptions("floor", pack);
  renderQuestionnaireMaterialPairs(pack);
  element.questionnaireWallColor.value =
    draft.wallColor || pack.wall.color;
  element.questionnaireFloorColor.value =
    draft.floorColor || pack.floor.color;
  element.questionnaireWallPreference.value = draft.wallPreference || "";
  element.questionnaireFloorPreference.value = draft.floorPreference || "";
  element.questionnaireCeilingMaterial.value =
    draft.ceilingMaterial || "flat-paint";
  element.questionnaireCeilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireLightStyle.innerHTML = LIGHT_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireCeilingStyle.value =
    draft.ceilingStyle
    || CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || CEILING_STYLES[0].id;
  element.questionnaireLightStyle.value =
    draft.lightStyle
    || LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || LIGHT_STYLES[0].id;
  element.questionnaireCeilingColor.value =
    draft.ceilingColor || "#f4f1eb";
  element.questionnaireAirConditioning.value = draft.airConditioning || "";
  renderQuestionnaireCeilingQuickChoices(draft);
  element.selectedWallSurface.hidden = true;
  element.selectedWallSurface.textContent = "";
  element.questionnaireFinishRoomTargets.innerHTML = state.rooms
    .filter((candidate) => candidate.id !== room.id)
    .map((candidate) => `<label><input type="checkbox" value="${escapeHtml(candidate.id)}"> ${escapeHtml(candidate.label)}</label>`)
    .join("");
  element.questionnaireFinishRoomTargets.hidden =
    element.questionnaireFinishScope.value !== "selected";
  const finishControls = [
    element.questionnaireStyleTabs,
    element.questionnaireStyleGrid,
    element.questionnaireWallOptions,
    element.questionnaireFloorOptions,
    element.questionnaireWallColor,
    element.questionnaireFloorColor,
    element.questionnaireWallPreference,
    element.questionnaireFloorPreference,
    element.questionnaireCeilingMaterial,
    element.questionnaireCeilingStyle,
    element.questionnaireLightStyle,
    element.questionnaireCeilingColor,
    element.questionnaireAirConditioning,
    element.questionnaireFinishScope,
  ];
  finishControls.forEach((control) => {
    if (!control) return;
    control.classList.toggle("is-locked", circulationLocked);
    if ("disabled" in control) control.disabled = circulationLocked;
    control.querySelectorAll?.("button, input, select").forEach((input) => {
      input.disabled = circulationLocked;
    });
  });
  renderConditionalFeasibility(room);
  renderQuestionnaireRoomSections();
}

function renderConditionalFeasibility(room) {
  const options = [
    ["bathtub", "浴缸"],
    ["double_vanity", "雙洗手台"],
    ["large_dining_table", "大型餐桌"],
  ];
  const relevant = room.type === "bathroom"
    ? options.slice(0, 2)
    : (room.type === "kitchen"
      ? options.slice(2)
      : []);
  if (!relevant.length) {
    element.roomFeasibilityNotices.innerHTML = "";
    return;
  }
  element.roomFeasibilityNotices.innerHTML = relevant.map(([optionId, label]) => {
    const result = evaluateConditionalOption(room, optionId, state.structures.doors);
    return `
      <article class="${result.feasible ? "is-feasible" : "needs-review"}">
        <strong>${escapeHtml(label)}</strong>
        <span>${result.feasible ? "目前尺寸可列為一般選項" : "目前尺寸可能無法配置"}</span>
        ${result.feasible ? "" : `<small>${escapeHtml(result.warnings[0])}</small>`}
      </article>
    `;
  }).join("");
}

function selectQuestionnaireStylePack(packId) {
  const wholeHousePack = wholeHouseStylePack();
  if (packId !== wholeHousePack.id) {
    setStatus("風格由全屋設定統一管理；請回全屋設定變更。", "error");
  }
}

function confirmQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  const requirement = activeRoomRequirement();
  const draft = activeRoomFinishDraft();
  if (!room || !requirement) return;
  if (state.questionnaireStage === "rooms") {
    // `confirmed` is written just below. Validate the selected values first;
    // otherwise every new room draft fails before it can ever be confirmed.
    const finishGate = finishesGate({ ...draft, confirmed: true });
    if (!finishGate.ready) {
      element.requirementsError.textContent = `請完成本房材質：${finishGate.missing.join("、")}`;
      setStatus(element.requirementsError.textContent, "error");
      return;
    }
  }
  const pack = wholeHouseStylePack();
  Object.assign(draft, {
    ...draft,
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial: draft.wallMaterial || pack.wall.surfaceOption,
    wallColor: element.questionnaireWallColor.value,
    floorMaterial: draft.floorMaterial || pack.floor.surfaceOption,
    floorColor: element.questionnaireFloorColor.value,
    ceilingMaterial: element.questionnaireCeilingMaterial.value,
    ceilingStyle: element.questionnaireCeilingStyle.value,
    lightStyle: element.questionnaireLightStyle.value,
    ceilingColor: element.questionnaireCeilingColor.value,
    airConditioning: element.questionnaireAirConditioning.value || "auto",
  });
  delete requirement.preferenceSuggestion;
  requirement.axisAnswers = {};
  const conditionalOptionIds = room.type === "bathroom"
    ? ["bathtub", "double_vanity"]
    : (room.type === "kitchen"
      ? ["large_dining_table"]
      : []);
  requirement.feasibility = conditionalOptionIds
    .map((optionId) => evaluateConditionalOption(room, optionId, state.structures.doors))
    .filter((result) => !result.feasible)
    .map((result) => ({
      optionId: result.optionId,
      forcePlacement: false,
      message: result.warnings[0],
    }));
  requirement.specialRequests = [];
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
    wallDefault: {
      materialId: draft.defaultWallMaterial || draft.wallMaterial,
      color: draft.defaultWallColor || draft.wallColor,
    },
    wallOverrides: { ...(requirement.surfaces.wallOverrides || {}), ...(draft.wallOverrides || {}) },
    floor: { materialId: draft.floorMaterial, color: draft.floorColor },
    ceiling: {
      materialId: draft.ceilingMaterial,
      styleId: draft.ceilingStyle,
      lightingId: draft.lightStyle,
      color: draft.ceilingColor,
    },
  };
  if (state.selectedQuestionnaireWallId) {
    requirement.surfaces.wallSurfaceIds = [
      ...new Set([
        ...(requirement.surfaces.wallSurfaceIds || []),
        state.selectedQuestionnaireWallId,
      ]),
    ];
  }
  requirement.confirmed = true;
  // This is intentionally non-blocking: RAG changes ranking, never room completion.
  if (state.questionnaireStage === "rooms") void startQuestionnaireRag(room);
  state.questionnaireFinishes = { ...draft };
  const scope = element.questionnaireFinishScope.value;
  const selectedRoomIds = $$("input:checked", element.questionnaireFinishRoomTargets)
    .map((input) => input.value);
  state.roomRequirementModel = applyRoomFinishScope(
    state.roomRequirementModel,
    room.id,
    scope,
    selectedRoomIds,
  );
  applyWholeHouseSurfaceConsistency();
  state.roomRequirementModel.roomRequirements[room.id].confirmed = true;
  if (scope !== "room") {
    state.roomFinishDrafts = {};
  }
  element.requirementsError.textContent = "";
  invalidateDownstreamFrom("requirements", "風格與材質偏好已修改，後續配置需要重新產生。");
  state.activeStylePackId = pack.id;
  const nextRoom = state.rooms.find(
    (candidate) => !state.roomRequirementModel.roomRequirements[candidate.id]?.confirmed,
  );
  if (nextRoom) {
    state.roomRequirementModel.activeRoomId = nextRoom.id;
    state.selectedQuestionnaireWallId = null;
    questionnaireRoomSection = "usage";
    renderVisualQuestionnaire();
    setStatus(
      `已確認「${room.label}」；接著確認「${nextRoom.label}」。`,
    );
    scheduleSave("requirements");
  } else {
    showQuestionnaireStage(state.questionnaireStage === "rooms" ? "summary" : "profile");
  }
}

const QUESTIONNAIRE_SUMMARY_AIR_CONDITIONING_LABELS = Object.freeze({
  auto: "依房間條件建議",
  "wall-split": "壁掛式冷氣",
  "ceiling-cassette": "嵌入式冷氣",
  ducted: "隱藏式冷氣",
  none: "暫不規劃冷氣",
});

const QUESTIONNAIRE_SUMMARY_CEILING_MATERIAL_LABELS = Object.freeze({
  "flat-paint": "平光乳膠漆",
  "mineral-paint": "礦物塗料",
  "wood-veneer": "木質飾面",
  "exposed-concrete": "清水混凝土",
});

function questionnaireSummarySurfaceLabel(kind, materialId) {
  if (!materialId) return "未選擇";
  const catalog = state.surfaceCatalog || state.sceneData?.surface_catalog || {};
  const surface = (catalog.surfaces || []).find(
    (candidate) => candidate.surface_id === materialId,
  );
  if (surface) return userFacingMaterialLabel(surface);

  const fallback = String(materialId)
    .replace(/^wall_json_ambientcg_wall_paint_/i, "")
    .replace(/^(?:wood|tile)_ccity_tile_flooring_/i, "")
    .replace(/_/g, " ")
    .trim();
  if (!fallback || fallback === "auto") return kind === "wall" ? "依風格建議" : "依風格建議";
  return kind === "wall" ? "已選牆面材質" : "已選地板材質";
}

function questionnaireSummaryFurnitureLabel(item) {
  const label = questionnaireFurnitureDisplayLabel(item);
  return label && !/[A-Za-z]/.test(label) ? label : "其他家具";
}

function questionnaireSummaryRoomUses(room, requirement) {
  const labels = new Map(roomUsageOptions(room).map((option) => [option.id, option.label]));
  return (requirement?.usage || [])
    .map((usage) => labels.get(usage))
    .filter(Boolean)
    .join("、") || "尚未設定";
}

function renderQuestionnaireSummary() {
  const basicRows = WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle").map((question) =>
    `<article class="rp-questionnaire-summary-card"><span>${escapeHtml(question.label)}</span><strong>${escapeHtml(state.basicAnswers[question.id] || "未填")}</strong></article>`
  ).join("");
  const wholeHouseNotes = WHOLE_HOUSE_QUESTIONS
    .filter((question) => question.type === "textarea")
    .map((question) => ({
      label: question.label,
      value: String(state.basicAnswers[question.id] || "").trim(),
    }))
    .filter((item) => item.value)
    .map((item) => `<li><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></li>`)
    .join("");
  const roomRows = state.rooms.map((room, index) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const axes = Object.entries(requirement?.axisAnswers || {}).map(([questionId, answer]) => {
      const question = state.visualQuestions.find(
        (candidate) => candidate.source_question_id === questionId
          && String(candidate.room_id) === String(room.id),
      );
      const option = question?.options.find(
        (candidate) => candidate.option_id === answer.optionId,
      );
      const weightLabel = preferenceWeightLabel(answer.preferenceWeight);
      const answerLabel = [
        option?.label_zh || answer.optionId || "未填",
        weightLabel,
      ].filter(Boolean).join(" / ");
      return `<li><span>${escapeHtml(question?.title_zh || questionId)}</span><strong>${escapeHtml(answerLabel)}</strong></li>`;
    }).join("");
    const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {});
    const selectedFurniture = requirement?.furniture?.selected || [];
    const deferredFurniture = requirement?.furniture?.deferred || [];
    const furniturePreference = String(requirement?.furniture?.preferenceText || "").trim();
    const furnitureTags = (requirement?.furniture?.preferenceTags || [])
      .map((tag) => String(tag).trim())
      .filter(Boolean)
      .join("、");
    const generationNotes = String(requirement?.generativeEquipment?.generationNotes || "").trim();
    const wallPreference = String(surfaces.wallPreference || "").trim();
    const floorPreference = String(surfaces.floorPreference || "").trim();
    const noteRows = [
      furniturePreference && ["家具偏好", furniturePreference],
      furnitureTags && ["偏好標籤", furnitureTags],
      wallPreference && ["牆面補充", wallPreference],
      floorPreference && ["地板補充", floorPreference],
      generationNotes && ["設計與生圖補充", generationNotes],
    ].filter(Boolean).map(([label, value]) => (
      `<li><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></li>`
    )).join("");
    const notices = (requirement?.feasibility || []).map(
      (item) => `<li>${escapeHtml(item.message || item)}</li>`,
    ).join("");
    return `
      <details class="rp-room-summary" ${index === 0 ? "open" : ""}>
        <summary>
          <span class="rp-room-summary-title"><strong>${escapeHtml(room.label)}</strong></span>
          <span class="rp-room-summary-status ${requirement?.confirmed ? "is-confirmed" : ""}">${requirement?.confirmed ? "已確認" : "待確認"}</span>
        </summary>
        <div class="rp-room-summary-body">
          <section class="rp-room-summary-item"><h4>空間用途</h4><p>${escapeHtml(questionnaireSummaryRoomUses(room, requirement))}</p></section>
          <section class="rp-room-summary-item"><h4>已選家具</h4>
            <p>${escapeHtml(selectedFurniture.map(questionnaireSummaryFurnitureLabel).join("、") || "將依需求推薦")}</p>
            ${deferredFurniture.length ? `<p>暫不放入：${escapeHtml(deferredFurniture.map(questionnaireSummaryFurnitureLabel).join("、"))}</p>` : ""}
          </section>
          <section class="rp-room-summary-item"><h4>冷氣與天花</h4>
            <p>冷氣：${escapeHtml(QUESTIONNAIRE_SUMMARY_AIR_CONDITIONING_LABELS[requirement?.climate?.airConditioning] || "依房間條件建議")}</p>
            <p>天花：${escapeHtml(QUESTIONNAIRE_SUMMARY_CEILING_MATERIAL_LABELS[surfaces.ceiling?.materialId] || "已選天花材質")}、${escapeHtml(CEILING_STYLES.find((item) => item.id === surfaces.ceiling?.styleId)?.label || "依風格建議")}、${escapeHtml(LIGHT_STYLES.find((item) => item.id === surfaces.ceiling?.lightingId)?.label || "依風格建議")}</p>
          </section>
          <section class="rp-room-summary-item"><h4>牆面與地板</h4><p>牆面：${escapeHtml(questionnaireSummarySurfaceLabel("wall", surfaces.wallDefault?.materialId))}</p><p>地板：${escapeHtml(questionnaireSummarySurfaceLabel("floor", surfaces.floor?.materialId))}</p></section>
          ${noteRows ? `<section class="rp-room-summary-notes"><h4>文字補充</h4><ul>${noteRows}</ul></section>` : ""}
          ${notices ? `<section class="needs-review"><h4>需要確認</h4><ul>${notices}</ul></section>` : ""}
        </div>
      </details>
    `;
  }).join("");
  element.questionnaireSummary.innerHTML = `
    <section class="rp-questionnaire-summary-section rp-questionnaire-summary-overview">
      <div class="rp-questionnaire-summary-heading"><h3>全屋需求</h3></div>
      <div class="rp-questionnaire-summary-grid">${basicRows}</div>
      ${wholeHouseNotes ? `<div class="rp-questionnaire-summary-notes"><h4>文字補充</h4><ul>${wholeHouseNotes}</ul></div>` : ""}
    </section>
    <section class="rp-questionnaire-summary-section"><div class="rp-questionnaire-summary-heading"><h3>各房間摘要</h3></div>${roomRows}</section>
  `;
}

function renderWholeHouseQuestionnaire() {
  const profileQuestions = WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle");
  element.wholeHouseFields.innerHTML = profileQuestions.map((question) => {
    if (question.type === "select") {
      const options = question.options.map((option) =>
        `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`
      ).join("");
      return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><select><option value="">請選擇</option>${options}</select></label>`;
    }
    return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><textarea rows="2" placeholder="${escapeHtml(question.placeholder || "")}"></textarea></label>`;
  }).join("");
  profileQuestions.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    const control = host?.querySelector("select, textarea");
    if (control) control.value = state.basicAnswers[question.id] || "";
  });
  renderWholeHouseStyleEditor();
}

function wholeHouseFinishDraft() {
  const fallbackPack = STYLE_PACKS.find(
    (pack) => pack.id === state.activeStylePackId,
  ) || STYLE_PACKS[0];
  const draft = state.questionnaireFinishes || {};
  return {
    stylePackId: draft.stylePackId || fallbackPack.id,
    wallMaterial: draft.wallMaterial || fallbackPack.wall.surfaceOption,
    wallColor: draft.wallColor || fallbackPack.wall.color,
    floorMaterial: draft.floorMaterial || fallbackPack.floor.surfaceOption,
    floorColor: draft.floorColor || fallbackPack.floor.color,
    ceilingMaterial: draft.ceilingMaterial || "flat-paint",
    ceilingStyle: CEILING_STYLES.some((item) => item.id === draft.ceilingStyle)
      ? draft.ceilingStyle
      : CEILING_STYLES[0].id,
    lightStyle: draft.lightStyle || LIGHT_STYLES[0].id,
    ceilingColor: draft.ceilingColor || "#f4f1eb",
    ceilingDesignStep: Number(draft.ceilingDesignStep || 1),
    airConditioning: draft.airConditioning || "auto",
    applyStyleToAllRooms: true,
    applyAirConditioningToEligibleRooms: draft.applyAirConditioningToEligibleRooms !== false,
  };
}

function renderWholeHouseStyleEditor() {
  const draft = wholeHouseFinishDraft();
  const pack = STYLE_PACKS.find((candidate) => candidate.id === draft.stylePackId) || STYLE_PACKS[0];
  state.questionnaireFinishes = { ...state.questionnaireFinishes, ...draft };
  state.activeStyleId = pack.styleId;
  element.wholeHouseStyleTabs.replaceChildren();
  element.wholeHouseStyleGrid.innerHTML = STYLE_FAMILIES.map((family) => `
    <button type="button" data-whole-house-style="${escapeHtml(family.id)}"
      data-whole-house-style-pack="${escapeHtml(family.defaultPackId)}"
      class="${family.id === pack.styleId ? "is-active" : ""}"
      aria-pressed="${family.id === pack.styleId}">
      <img class="rp-style-card-preview" src="${escapeHtml(family.referenceImage)}"
        alt="${escapeHtml(`${family.label} 台灣住宅風格參考圖`)}" loading="lazy">
      <strong>${escapeHtml(family.label)}</strong>
      <small>${escapeHtml(family.selectionCue || "")}</small>
      <em>${family.id === pack.styleId ? "已選擇此全屋風格" : "點選設為全屋風格"}</em>
    </button>
  `).join("");
  element.wholeHouseStyleSelection.textContent = `已選全屋主風格：${STYLE_FAMILIES.find((family) => family.id === pack.styleId)?.label || pack.name}。牆面、地板、天花與照明將在逐房問卷設定。`;
}

function roomFinishDraftForStyleChange(room, requirement) {
  const existing = state.roomFinishDrafts[room.id];
  if (existing) return existing;
  const surfaces = requirement.surfaces || {};
  return {
    confirmed: requirement.confirmed === true,
    materialSelectionMode: surfaces.materialSelectionMode || "auto",
    styleReviewRequired: surfaces.styleReviewRequired === true,
    stylePackId: surfaces.paletteId || null,
    wallMaterial: surfaces.wallDefault?.materialId || null,
    wallColor: surfaces.wallDefault?.color || null,
    defaultWallMaterial: surfaces.wallDefault?.materialId || null,
    defaultWallColor: surfaces.wallDefault?.color || null,
    wallOverrides: { ...(surfaces.wallOverrides || {}) },
    floorMaterial: surfaces.floor?.materialId || null,
    floorColor: surfaces.floor?.color || null,
    ceilingMaterial: surfaces.ceiling?.materialId || null,
    ceilingStyle: surfaces.ceiling?.styleId || null,
    lightStyle: surfaces.ceiling?.lightingId || null,
    ceilingColor: surfaces.ceiling?.color || "#f4f1eb",
    airConditioning: requirement.climate?.airConditioning || "auto",
  };
}

function recommendedCeilingStyleForPack(pack) {
  return CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id || CEILING_STYLES[0].id;
}

function recommendedLightStyleForPack(pack) {
  return LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id || LIGHT_STYLES[0].id;
}

function applyStyleChangeToRooms(pack) {
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (!requirement) return;
    const draft = roomFinishDraftForStyleChange(room, requirement);
    const preserveMaterials = draft.confirmed || draft.materialSelectionMode === "custom";
    const surfaces = requirement.surfaces || {};
    if (preserveMaterials) {
      Object.assign(draft, {
        stylePackId: pack.id,
        confirmed: false,
        styleReviewRequired: true,
      });
      requirement.surfaces = {
        ...surfaces,
        paletteId: pack.id,
        materialSelectionMode: "custom",
        styleReviewRequired: true,
      };
    } else {
      const recommendation = questionnaireMaterialPairsForPack(pack, room)[0];
      if (recommendation) {
        Object.assign(draft, {
          stylePackId: pack.id,
          wallMaterial: recommendation.wall.id,
          wallColor: recommendation.wall.color,
          defaultWallMaterial: recommendation.wall.id,
          defaultWallColor: recommendation.wall.color,
          wallOverrides: {},
          floorMaterial: recommendation.floor.id,
          floorColor: recommendation.floor.color,
          ceilingMaterial: draft.ceilingMaterial || "flat-paint",
          ceilingStyle: recommendedCeilingStyleForPack(pack),
          lightStyle: recommendedLightStyleForPack(pack),
          materialSelectionMode: "auto",
          confirmed: false,
          styleReviewRequired: false,
        });
        requirement.surfaces = {
          ...surfaces,
          paletteId: pack.id,
          materialSelectionMode: "auto",
          styleReviewRequired: false,
          wallDefault: { materialId: draft.wallMaterial, color: draft.wallColor },
          wallOverrides: {},
          floor: { materialId: draft.floorMaterial, color: draft.floorColor },
          ceiling: {
            ...(surfaces.ceiling || {}),
            styleId: draft.ceilingStyle,
            lightingId: draft.lightStyle,
          },
        };
      }
    }
    requirement.confirmed = false;
    state.roomFinishDrafts[room.id] = draft;
  });
}

function selectWholeHouseStylePack(packId) {
  const pack = STYLE_PACKS.find((candidate) => candidate.id === packId);
  if (!pack) return;
  const previousPackId = wholeHouseFinishDraft().stylePackId;
  const family = STYLE_FAMILIES.find((item) => item.id === pack.styleId);
  const wallOption = questionnaireMaterialOptionsForPack("wall", pack)[0];
  const floorOption = questionnaireMaterialOptionsForPack("floor", pack)[0];
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  state.questionnaireFinishes = {
    ...wholeHouseFinishDraft(),
    stylePackId: pack.id,
    wallMaterial: wallOption?.id || pack.wall.surfaceOption,
    wallColor: wallOption?.color || pack.wall.color,
    floorMaterial: floorOption?.id || pack.floor.surfaceOption,
    floorColor: floorOption?.color || pack.floor.color,
    ceilingMaterial: wholeHouseFinishDraft().ceilingMaterial || "flat-paint",
    ceilingStyle: recommendedCeilingStyleForPack(pack),
    lightStyle: recommendedLightStyleForPack(pack),
  };
  // Keep the persisted profile and the style editor in lockstep. The profile
  // is restored on reload and is also part of the RAG/render request.
  state.basicAnswers = {
    ...state.basicAnswers,
    overallStyle: family?.label || pack.name,
  };
  state.roomRequirementModel.globalProfile = {
    ...(state.roomRequirementModel.globalProfile || {}),
    overallStyle: state.basicAnswers.overallStyle,
  };
  if (previousPackId && previousPackId !== pack.id) {
    applyStyleChangeToRooms(pack);
  }
  renderWholeHouseStyleEditor();
  setStatus(`已選擇全屋主風格：${family?.label || pack.name}。`);
  scheduleSave("requirements");
}

function applyWholeHouseFinishes() {
  const draft = wholeHouseFinishDraft();
  const pack = STYLE_PACKS.find((candidate) => candidate.id === draft.stylePackId) || STYLE_PACKS[0];
  state.questionnaireFinishes = draft;
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (!requirement) return;
    const recommendation = questionnaireMaterialPairsForPack(pack, room)[0];
    const roomDraft = roomFinishDraftForStyleChange(room, requirement);
    const preserveCustomChoice = roomDraft.materialSelectionMode === "custom";
    const existing = requirement.surfaces || {};
    requirement.surfaces = {
      ...existing,
      paletteId: draft.stylePackId,
      ...(preserveCustomChoice || !recommendation ? {} : {
        wallDefault: { materialId: recommendation.wall.id, color: recommendation.wall.color },
        floor: { materialId: recommendation.floor.id, color: recommendation.floor.color },
        ceiling: {
          materialId: roomDraft.ceilingMaterial || "flat-paint",
          styleId: recommendedCeilingStyleForPack(pack),
          lightingId: recommendedLightStyleForPack(pack),
          color: roomDraft.ceilingColor || "#f4f1eb",
        },
      }),
    };
    requirement.climate = {
      ...(requirement.climate || {}),
      airConditioning: requirement.climate?.airConditioning || "auto",
    };
    state.roomFinishDrafts[room.id] = {
      ...roomDraft,
      stylePackId: draft.stylePackId,
      wallMaterial: preserveCustomChoice ? roomDraft.wallMaterial : recommendation?.wall.id,
      wallColor: preserveCustomChoice ? roomDraft.wallColor : recommendation?.wall.color,
      floorMaterial: preserveCustomChoice ? roomDraft.floorMaterial : recommendation?.floor.id,
      floorColor: preserveCustomChoice ? roomDraft.floorColor : recommendation?.floor.color,
      ceilingMaterial: preserveCustomChoice ? roomDraft.ceilingMaterial : (roomDraft.ceilingMaterial || "flat-paint"),
      ceilingStyle: preserveCustomChoice ? roomDraft.ceilingStyle : recommendedCeilingStyleForPack(pack),
      lightStyle: preserveCustomChoice ? roomDraft.lightStyle : recommendedLightStyleForPack(pack),
      airConditioning: requirement.climate.airConditioning,
      confirmed: preserveCustomChoice ? roomDraft.confirmed : false,
    };
  });
}

function collectBasicAnswers() {
  const answers = {};
  WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle").forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    answers[question.id] = host?.querySelector("select, textarea")?.value.trim() || "";
  });
  const selectedFamily = STYLE_FAMILIES.find((family) => family.id === state.activeStyleId);
  answers.overallStyle = selectedFamily?.label || "";
  return answers;
}

async function confirmBasicQuestionnaire() {
  element.requirementsError.textContent = "";
  const answers = collectBasicAnswers();
  state.basicAnswers = answers;
  state.basicConfirmed = true;
  state.roomRequirementModel.globalProfile = { ...answers };
  state.roomRequirementModel.globalConfirmed = true;
  applyWholeHouseFinishes();
  invalidateDownstreamFrom(
    "requirements",
    "全屋風格與材質已確認，後續配置需要依完整需求重新產生。",
  );
  showQuestionnaireStage("rooms");
  scheduleSave("requirements");
}

function clearRequirementsGenerationHelp() {
  element.requirementsGenerationHelp?.setAttribute("hidden", "");
  if (element.requirementsGenerationHelpDetail) {
    element.requirementsGenerationHelpDetail.textContent = "";
  }
}

function showRequirementsGenerationHelp(detail) {
  if (!element.requirementsGenerationHelp || !element.requirementsGenerationHelpDetail) return;
  element.requirementsGenerationHelpDetail.textContent = detail;
  element.requirementsGenerationHelp.removeAttribute("hidden");
}

async function configurationCatalogReadiness() {
  try {
    const status = await api("/api/catalog/status");
    const catalog = status.catalog_provider || {};
    if (catalog.ready === false || catalog.available === false) {
      return {
        ready: false,
        reason: String(catalog.reason || "catalog_unavailable"),
      };
    }
    return { ready: true };
  } catch (error) {
    return { ready: false, reason: errorMessage(error) };
  }
}

async function confirmRequirements() {
  if (state.requirementsGenerationPending) {
    const message = "配置仍在建立中，請稍候。";
    element.requirementsError.textContent = message;
    setStatus(message, "warning");
    return;
  }
  state.requirementsGenerationPending = true;
  state.lastWhiteModelGenerationError = "";
  element.confirmRequirements?.setAttribute("aria-busy", "true");
  element.confirmRequirements?.setAttribute("disabled", "disabled");
  try {
    await confirmRequirementsInternal();
  } catch (error) {
    const message = errorMessage(error);
    element.requirementsError.textContent = message;
    showRequirementsGenerationHelp(`建立配置時發生錯誤：${message}`);
    setStatus(message, "error");
  } finally {
    state.requirementsGenerationPending = false;
    element.confirmRequirements?.removeAttribute("aria-busy");
    element.confirmRequirements?.removeAttribute("disabled");
  }
}

async function confirmRequirementsInternal() {
  element.requirementsError.textContent = "";
  clearRequirementsGenerationHelp();
  setStatus("正在依每個房間的需求搜尋可配置家具…");
  await settleQuestionnaireRagForLayout();
  const requirementsPayload = buildRoomRequirementsPayload(
    state.roomRequirementModel,
    {
      planGeometry: {
        rooms: state.rooms,
        structures: state.structures,
      },
      questionnaireVersion: state.visualCatalogVersion,
    },
  );
  if (!requirementsPayload.readyForRag) {
    element.requirementsError.textContent = "請先完成所有房間需求與材質，再確認全屋資料。";
    return;
  }
  const catalogReadiness = await configurationCatalogReadiness();
  if (!catalogReadiness.ready) {
    const message = "目前無法連線 Kai 家具型錄，尚未取得所選家具的可用 GLB，因此不能建立可靠的 2D+3D 配置。";
    element.requirementsError.textContent = message;
    showRequirementsGenerationHelp(`${message} 系統回報：${catalogReadiness.reason}。`);
    setStatus("Kai 家具型錄尚未就緒，已保留問卷答案並停止建立配置。", "error");
    return;
  }
  try {
    setStatus("正在檢查空間規則並建立方案 A、B…");
    ensureSchemeB(state.designSchemes, { reason: "questionnaire_alternative" });
    await switchDesignScheme("A");
    await autoLayoutFurniture();
    const schemeAFurniture = state.designSchemes.schemes.A.furniture;
    let schemeBFurniture = null;
    let schemeBError = null;
    try {
      schemeBFurniture = await relayoutFurnitureForScheme(schemeAFurniture, "B");
    } catch (error) {
      schemeBError = error;
      console.warn("Unable to create the alternative layout; continuing with scheme A.", error);
    }
    const schemeB = state.designSchemes.schemes.B;
    if (!schemeBFurniture) {
      schemeB.furniture = [];
      schemeB.stale = true;
      schemeB.staleReason = schemeBError
        ? `方案 B 暫時無法建立：${errorMessage(schemeBError)}`
        : "目前格局無法在保留問卷需求下產生方案 B 的合法配置。";
    } else {
      schemeB.furniture = schemeBFurniture;
      schemeB.stale = false;
      schemeB.staleReason = "";
    }
    await switchDesignScheme("A");
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
      visualPreferencesResolved: true,
      finishesConfirmed: true,
    });
    renderFurnitureLibrary();
    setStatus("正在載入方案 A 的資料庫家具與 3D 場景…");
    const generated = await generateWhiteModelFromRequirements({
      returnToRequirementsOnFailure: true,
    });
    if (!generated && !element.requirementsError.textContent.trim()) {
      const message = state.lastWhiteModelGenerationError
        || element.layoutError.textContent.trim()
        || "第 6 步沒有產生場景資料。請重新檢查型錄與平面圖後再試。";
      element.requirementsError.textContent = message;
      showRequirementsGenerationHelp(`建立配置未完成：${message}`);
    }
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    showRequirementsGenerationHelp(`系統回報：${errorMessage(error)}。`);
    setStatus(errorMessage(error), "error");
  }
}

function roomCenter(room) {
  return room.polygon_cm.reduce((sum, point) => ({
    x: sum.x + point.x / room.polygon_cm.length,
    y: sum.y + point.y / room.polygon_cm.length,
  }), { x: 0, y: 0 });
}

function roomIdForScenePosition(positionCm = {}) {
  const center = planCenterCm();
  const planPoint = {
    x: center.x + Number(positionCm.x || 0),
    y: center.y + Number(positionCm.z || 0),
  };
  return state.rooms.find(
    (room) => pointInPolygonCm(planPoint, room.polygon_cm || []),
  )?.id || state.selectedRoomId || state.rooms[0]?.id || null;
}

function furniture2dDefaultsForSceneObject(sceneObject) {
  const match = findFurniture2DVariant(
    sceneObject?.normalized_type,
    sceneObject?.variant_id,
  );
  return {
    roomId: sceneObject?.placement_room_id
      || roomIdForScenePosition(sceneObject?.position_cm),
    type: sceneObject?.normalized_type || match?.category?.type || "furniture",
    variantId: match?.selected?.id || sceneObject?.variant_id || "standard",
    iconPath: match?.selected?.iconPath || "",
    label: sceneObject?.name_zh
      || sceneObject?.name_zh_raw
      || match?.selected?.label
      || "家具",
    reason: "使用者在 3D 配置與預覽工作台中新增或替換。",
    userRequired: true,
  };
}

function roomSurfaceAssignments() {
  const center = planCenterCm();
  return state.rooms.map((room) => {
    const requirement = state.roomRequirementModel?.roomRequirements?.[room.id];
    const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {});
    return {
      room_id: room.id,
      room_label: room.label,
      palette_id: surfaces.paletteId || null,
      wall_surface_ids: [...(surfaces.wallSurfaceIds || [])],
      wall_overrides: { ...(surfaces.wallOverrides || {}) },
      room_bounds_cm: {
        minX: Math.min(...room.polygon_cm.map((point) => point.x)) - center.x,
        maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - center.x,
        minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - center.y,
        maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - center.y,
      },
      room_polygon_cm: room.polygon_cm.map((point) => ({
        x: point.x - center.x,
        z: point.y - center.y,
      })),
      wall_material_id: surfaces.wallDefault?.materialId || null,
      wall_color_hex: surfaces.wallDefault?.color || null,
      floor_material_id: surfaces.floor?.materialId || null,
      floor_color_hex: surfaces.floor?.color || null,
      ceiling_material_id: surfaces.ceiling?.materialId || null,
      ceiling_style_id: surfaces.ceiling?.styleId || null,
      ceiling_color_hex: surfaces.ceiling?.color || null,
      lighting_id: surfaces.ceiling?.lightingId || null,
      air_conditioning: requirement?.climate?.airConditioning || null,
    };
  });
}

function planCenterCm() {
  const { bbox, scale } = planGeometry();
  return {
    x: (bbox[2] - bbox[0]) * scale / 2,
    y: (bbox[3] - bbox[1]) * scale / 2,
  };
}

function furnitureOfferFromSpec(room, spec, index) {
  const [type, variant, reason, autoAdded] = spec;
  const item = createFurniture2DItem(type, variant, {
    id: `${room.id}-${type}-${variant || "standard"}-candidate-${index + 1}`,
    roomId: room.id,
  });
  return {
    furniture_id: item.id,
    normalized_type: item.type,
    variant_id: item.variantId,
    name_zh_raw: item.label,
    size_cm: {
      width: item.widthCm,
      depth: item.depthCm,
      height: item.heightCm,
    },
    reason,
    auto_added: autoAdded === true,
    selection_source: "local_rules",
  };
}

function questionnairePackForRoom(room) {
  const paletteId =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.paletteId;
  return STYLE_PACKS.find((pack) => pack.id === paletteId)
    || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
}

function questionnaireFurnitureRequest(room, spec) {
  const [type, variant] = spec;
  const template = createFurniture2DItem(type, variant, { roomId: room.id });
  const pack = questionnairePackForRoom(room);
  const surfaces =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {};
  const requirement = state.roomRequirementModel?.roomRequirements?.[room.id] || {};
  const visualPreferenceText = visualPreferencesForRoom(room)
    .flatMap((preference) => [
      preference.option_id,
      preference.custom,
      preference.preference_direction,
    ])
    .filter(Boolean)
    .join(" ");
  return {
    type,
    roomType: room.type || room.room_type || "",
    roomLabel: room.label || room.name || "",
    styleId: pack.styleId,
    palette: pack.palette,
    queryText: [
      room.label,
      room.type,
      requirement.summary,
      requirement.notes,
      requirement.usage,
      requirement.furniture?.selected?.map((item) => item.label || item.type).join(" "),
      visualPreferenceText,
    ].filter(Boolean).join(" "),
    preferAnchor: ["bed", "sofa", "dining-table", "storage-cabinet", "appliance-cabinet"].includes(type),
    materials: [
      ...(pack.furniture?.materialLanguage || []),
      surfaces.wallDefault?.materialId,
      surfaces.floor?.materialId,
    ].filter(Boolean),
    widthCm: template.widthCm,
    depthCm: template.depthCm,
  };
}

const CATALOG_RETRIEVAL_ROUTES = {
  "sofa": {
    endpoint: "/api/furniture",
    types: ["fabric-sofa", "leather-sofa", "modular-sofa", "sofa"],
  },
  "storage-cabinet": { endpoint: "/api/furniture", type: "cabinet-cupboard" },
  "appliance-cabinet": { endpoint: "/api/furniture", type: "cabinet-cupboard" },
  "bathroom-vanity": {
    endpoint: "/api/furniture",
    type: "cabinet-cupboard",
    query: "bathroom storage",
  },
  "mirror-cabinet": {
    endpoint: "/api/furniture",
    type: "mirror-cabinet",
    query: "mirror cabinet",
  },
};

const REPLACEMENT_TYPE_LABELS = {
  bed: "床",
  wardrobe: "衣櫃",
  "bedside-table": "床邊桌",
  "fabric-sofa": "布沙發",
  "leather-sofa": "皮沙發",
  "modular-sofa": "模組沙發",
  "sofa": "一般沙發",
  "fridge-freezer": "冰箱",
  "washing-machine": "洗衣機／洗脫烘",
  "cabinet-cupboard": "收納櫃",
  "mirror-cabinet": "鏡櫃",
};

const QUESTIONNAIRE_FALLBACK_CATALOG_RULES = Object.freeze({
  bed: { query: "bed frame", types: ["bed"], keywords: ["bed", "床架", "床"] },
  wardrobe: { query: "wardrobe", types: ["wardrobe"], keywords: ["wardrobe", "衣櫃"] },
  "bedside-table": { query: "bedside table", keywords: ["bedside", "床頭"] },
  desk: { query: "desk", types: ["desk"], keywords: ["desk", "書桌"] },
  "office-chair": { query: "office chair", keywords: ["chair", "椅"] },
  "lounge-chair": { query: "lounge chair", keywords: ["chair", "椅"] },
  "dining-chair": { query: "dining chair", keywords: ["chair", "椅"] },
  "dining-table": { query: "dining table", keywords: ["table", "餐桌"] },
  "tv-bench": { query: "tv stand", keywords: ["tv", "television", "電視"] },
  "storage-cabinet": { query: "storage cabinet", keywords: ["cabinet", "storage", "收納", "櫃"] },
});

function isQuestionnaireFallbackTypeMatch(candidate, type) {
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[type];
  if (!rule) return candidate.normalized_type === type;
  const description = [
    candidate.name_zh,
    candidate.name_zh_raw,
    candidate.name_en,
    candidate.category_label,
    candidate.taxonomy_type_zh,
  ].filter(Boolean).join(" ").toLowerCase();
  const keywordMatches = (rule.keywords || []).some((keyword) =>
    description.includes(keyword.toLowerCase()));
  if (!keywordMatches) return false;
  return !rule.types?.length || rule.types.includes(candidate.normalized_type);
}

async function catalogCandidatesForType(
  type,
  { styleId = "", query = "", catalogType = "", searchAll = false } = {},
) {
  const route = CATALOG_RETRIEVAL_ROUTES[type]
    || { endpoint: "/api/furniture", type };
  const canSearchAll = searchAll && route.endpoint === "/api/furniture";
  const routeTypes = canSearchAll
    ? [""]
    : (catalogType ? [catalogType] : (route.types || [route.type]));
  const candidateGroups = await Promise.all(routeTypes.map(async (routeType) => {
    const params = new URLSearchParams({
      detail: "scene",
      page_size: "80",
    });
    if (routeType) params.set("type", routeType);
    if (route.endpoint === "/api/furniture") params.set("has_model", "true");
    const searchQuery = [route.query, query].filter(Boolean).join(" ");
    if (searchQuery) params.set("q", searchQuery);
    if (styleId && route.endpoint === "/api/furniture") {
      params.set("style", styleId);
    }
    let payload = await api(`${route.endpoint}?${params.toString()}`);
    if (!(payload.items || []).length && params.has("style")) {
      params.delete("style");
      payload = await api(`${route.endpoint}?${params.toString()}`);
    }
    return payload.items || [];
  }));
  return candidateGroups.flat();
}

async function catalogOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  const candidates = await catalogCandidatesForType(spec[0], {
    styleId: request.styleId,
    query: request.queryText,
  });
  const matchingCandidates = candidates.filter((candidate) =>
    isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => catalogFurnitureOffer(candidate, {
    roomId: room.id,
    requestedType: spec[0],
    requestedVariant: spec[1],
    reason: spec[2]
      || `${room.label}的問卷風格、色卡、材質與實際尺寸綜合匹配`,
  }));
}

async function catalogFallbackOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[spec[0]] || {};
  const label = rule.query || REPLACEMENT_TYPE_LABELS[spec[0]] || spec[0];
  let candidates = await catalogCandidatesForType(spec[0], {
    query: label,
    searchAll: true,
  });
  if (!candidates.length) {
    candidates = await catalogCandidatesForType(spec[0], { searchAll: true });
  }
  const matchingCandidates = candidates.filter((candidate) =>
    isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => ({
    ...catalogFurnitureOffer(candidate, {
      roomId: room.id,
      requestedType: spec[0],
      requestedVariant: spec[1],
      reason: `${room.label}未取得精準風格結果，改以同類可配置家具推薦`,
    }),
    recommendation_tier: "similar",
  }));
}

async function catalogOffersForRoomPlans(roomPlans) {
  return Object.fromEntries(await Promise.all(roomPlans.map(async ({ room, specs }) => {
    const groups = await Promise.all(specs.map(async (spec, index) => {
      try {
        return await catalogOffersForSpec(room, spec, index);
      } catch (error) {
        console.warn("Catalog RAG retrieval fallback", error);
        return [];
      }
    }));
    return [room.id, groups.flatMap((offers, index) => (
      offers.length
        ? offers
        : [furnitureOfferFromSpec(room, specs[index], index)]
    ))];
  })));
}

const QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS = Object.freeze({
  bedroom: {
    defaults: ["bed", "wardrobe"],
    required: [],
    labels: { bed: "睡眠的基本配置", wardrobe: "日常衣物收納", "bedside-table": "床邊置物" },
  },
  living_room: {
    defaults: ["sofa"],
    fallbackDefaults: ["lounge-chair"],
    required: [],
    labels: { sofa: "休息與招待的基本配置", "coffee-table": "客廳置物與活動中心", "tv-bench": "影音設備收納", "lounge-chair": "閱讀或獨立休息" },
  },
  kitchen: {
    defaults: ["dining-table", "dining-chair"],
    required: [],
    labels: { "dining-table": "用餐的基本配置", "dining-chair": "搭配餐桌的座位", "appliance-cabinet": "備餐與廚房收納", "storage-cabinet": "補充收納" },
  },
  storage: {
    defaults: ["storage-cabinet"],
    required: [],
    labels: { desk: "工作或閱讀的基本配置", "office-chair": "搭配書桌的座位", "storage-cabinet": "文件與用品收納" },
  },
  bathroom: {
    defaults: [],
    required: [],
    labels: { "bathroom-vanity": "盥洗與收納的基本配置", "mirror-cabinet": "鏡面與用品收納" },
  },
  balcony: {
    defaults: [],
    required: [],
    labels: { "flower-pots-planter": "陽台綠化", "lounge-chair": "短暫休憩" },
  },
  entryway: { defaults: [], required: [], labels: { mirror: "玄關整理與出門前使用" } },
  hallway: { defaults: [], required: [], labels: { mirror: "保留走道淨寬；只建議薄型靠牆物件" } },
  stair: { defaults: [], required: [], labels: { lighting: "樓梯僅提供照明；不配置可移動家具" } },
  garage: { defaults: [], required: [], labels: { "storage-cabinet": "工具與用品收納" } },
  default: { defaults: [], required: [], labels: {} },
});

const QUESTIONNAIRE_FURNITURE_SHORT_LABELS = Object.freeze({
  bed: "床",
  wardrobe: "衣櫃",
  "bedside-table": "床邊桌",
  chair: "椅子",
  armchair: "扶手椅",
  "lounge-chair": "休閒椅",
  "dining-chair": "餐椅",
  "office-chair": "辦公椅",
  "gaming-chair": "電競椅",
  "kids-chairs-stool": "兒童椅／凳",
  "stool-bench": "椅凳",
  sofa: "沙發",
  "coffee-table": "茶几",
  "tv-bench": "電視櫃",
  "lounge-chair": "單椅",
  desk: "書桌",
  "office-chair": "工作椅",
  "dining-table": "餐桌",
  "dining-chair": "餐椅",
  "appliance-cabinet": "廚房收納櫃",
  "storage-cabinet": "收納櫃",
  "bathroom-vanity": "浴櫃",
  "mirror-cabinet": "鏡櫃",
  "flower-pots-planter": "植栽",
});

const QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS = Object.freeze({
  scandinavian: ["淺木色", "圓角", "自然布料", "可收納", "輕盈"],
  japanese: ["淺木色", "低矮", "留白", "藤編", "自然材質"],
  modern_minimal: ["霧面", "俐落線條", "隱藏收納", "低彩度", "金屬"],
  industrial: ["黑色金屬", "木紋", "耐用", "開放層架", "皮革"],
  american: ["厚實", "布料", "溫暖木色", "大尺寸", "舒適"],
  creamy: ["圓弧", "奶油色", "柔軟布料", "淺色木紋", "收納"],
  default: ["淺木色", "圓角", "可收納", "耐用", "金屬"],
});

function questionnaireFurniturePreferenceTags(room) {
  const styleId = questionnairePackForRoom(room)?.styleId || "default";
  return QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS[styleId]
    || QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS.default;
}

function renderQuestionnaireFurniturePreferenceTags(room = activeQuestionnaireRoom()) {
  if (!element.questionnaireFurniturePreferenceTags || !room) return;
  const selected = new Set(roomFurnitureRequirement(room.id)?.preferenceTags || []);
  element.questionnaireFurniturePreferenceTags.innerHTML = questionnaireFurniturePreferenceTags(room)
    .map((tag) => `<button type="button" data-questionnaire-furniture-tag="${escapeHtml(tag)}"
      class="${selected.has(tag) ? "is-active" : ""}" aria-pressed="${selected.has(tag)}">${escapeHtml(tag)}</button>`)
    .join("");
}

function toggleQuestionnaireFurniturePreferenceTag(tag) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !tag) return;
  const tags = new Set(furniture.preferenceTags || []);
  if (tags.has(tag)) tags.delete(tag);
  else tags.add(tag);
  furniture.preferenceTags = [...tags];
  const text = element.questionnaireFurniturePreference?.value.trim() || "";
  const values = new Set(text.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean));
  furniture.preferenceTags.forEach((value) => values.add(value));
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = [...values].join("、");
  }
  furniture.preferenceText = element.questionnaireFurniturePreference?.value.trim() || "";
  renderQuestionnaireFurniturePreferenceTags(room);
  scheduleSave("requirements");
}

function questionnaireBedSizeFamily(offer) {
  const source = [offer?.name_zh, offer?.name_zh_raw, offer?.name_en]
    .filter(Boolean)
    .join(" ");
  const namedSize = [...source.matchAll(/(\d{2,3})\s*[x×]\s*(\d{2,3})/gi)]
    .map((match) => ({ width: Number(match[1]), depth: Number(match[2]) }))
    .find((size) => size.width >= 70 && size.width <= 220 && size.depth >= 180 && size.depth <= 230);
  const width = namedSize?.width || Number(offer?.size_cm?.width || 0);
  if (width <= 100) return "單人床";
  if (width <= 140) return "小雙人床";
  if (width <= 165) return "標準雙人床";
  if (width <= 195) return "加大雙人床";
  return "特大雙人床";
}

const QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS = Object.freeze({
  "pax-wardrobe": "系統衣櫃",
  "fabric-sofa": "布沙發",
  "leather-sofa": "皮沙發",
  "modular-sofa": "模組沙發",
  table: "多用途桌",
  "bar-table": "吧檯桌",
  "cabinets-cupboard": "收納櫃",
  "cabinet-cupboard": "收納櫃",
  "shelving-unit": "層架組",
  "storage-boxes-basket": "收納盒籃",
  "storage-solution-system": "收納系統",
  "wall-shelf": "壁掛層架",
  "shoe-cabinet": "鞋櫃",
  "clothes-rack": "衣帽架",
  "tv-media-furniture": "影音櫃",
  "chests-of-drawer": "抽屜櫃",
  mirror: "鏡子",
  "large-medium-rug": "地毯",
  "runner-small-rug": "走道地毯",
  "floor-lamp": "立燈",
  planter: "植栽盆器",
  decoration: "裝飾擺件",
  "pillow-cushion": "抱枕",
  shelf: "層架",
  bookcase: "書櫃",
  "storage-bench": "收納椅凳",
  "storage-box": "收納盒",
  lighting: "照明燈具",
});

function questionnaireFurnitureDisplayLabel(offer) {
  const type = String(offer?.normalized_type || "");
  const width = Number(offer?.size_cm?.width || 0);
  if (type === "bed") return questionnaireBedSizeFamily(offer);
  if (type === "wardrobe") {
    if (width <= 80) return "單門衣櫃";
    if (width <= 125) return "雙門衣櫃";
    if (width <= 185) return "三門衣櫃";
    return "大容量衣櫃";
  }
  if (type === "desk") {
    if (width <= 100) return "小型書桌";
    if (width <= 150) return "書桌";
    return "大書桌";
  }
  return QUESTIONNAIRE_FURNITURE_SHORT_LABELS[type]
    || QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS[type]
    || REPLACEMENT_TYPE_LABELS[type]
    || type;
}

function questionnaireOffersWithSizeChoices(type, candidates) {
  if (type !== "bed") {
    const byFamily = new Map();
    candidates.forEach((candidate) => {
      const family = questionnaireFurnitureDisplayLabel(candidate);
      if (!byFamily.has(family)) byFamily.set(family, candidate);
    });
    return [...byFamily.values()].slice(0, 4);
  }
  const byFamily = new Map();
  candidates.forEach((candidate) => {
    const family = questionnaireBedSizeFamily(candidate);
    if (!byFamily.has(family)) byFamily.set(family, candidate);
  });
  return [...byFamily.values()].slice(0, 4);
}

function questionnaireFurnitureProgram(room) {
  const type = String(room?.type || room?.room_type || "default").toLowerCase();
  return QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS[type]
    || QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS.default;
}

function questionnaireFurnitureRole(room, offer) {
  const program = questionnaireFurnitureProgram(room);
  const type = String(offer?.normalized_type || "");
  if (program.required.includes(type)) return { rank: 0, label: "基本配置", reason: program.labels[type] || "本房的基本配置" };
  if (program.defaults.includes(type)) return { rank: 1, label: "建議配置", reason: program.labels[type] || "依房間用途建議" };
  return { rank: 2, label: "可選配置", reason: program.labels[type] || "依用途與偏好推薦" };
}

const QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES = Object.freeze({
  chair: { kitchen: ["dining-chair"], storage: ["office-chair"], living_room: ["lounge-chair"], bedroom: ["lounge-chair"], balcony: ["lounge-chair"], default: ["lounge-chair"] },
  desk: { default: ["desk"] },
  table: { kitchen: ["dining-table"], living_room: ["coffee-table"], default: ["desk"] },
  sofa: { default: ["sofa"] },
  wardrobe: { default: ["wardrobe"] },
  storage: { default: ["storage-cabinet"] },
});

function questionnairePreferenceFurnitureSpecs(room) {
  const furniture = roomFurnitureRequirement(room.id) || {};
  const text = [furniture.preferenceText, ...(furniture.preferenceTags || [])].join(" ").toLowerCase();
  if (!text) return [];
  const matches = [
    ["chair", /椅|chair|單椅|休閒椅|餐椅|工作椅|辦公椅/],
    ["desk", /書桌|工作桌|desk|workstation/],
    ["table", /茶几|餐桌|table/],
    ["sofa", /沙發|sofa/],
    ["wardrobe", /衣櫃|衣柜|wardrobe/],
    ["storage", /收納|櫃|柜|storage|cabinet/],
  ];
  return matches.flatMap(([key, pattern]) => {
    if (!pattern.test(text)) return [];
    const types = QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES[key][room.type]
      || QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES[key].default || [];
    return types.map((type) => [type, "standard", `依「${furniture.preferenceText}」補充`, false]);
  });
}

function questionnaireFurnitureSpecsForRoom(room) {
  const recommended = applyVisualPreferencesToSpecs(
    recommendedFurnitureForRoom(room),
    visualPreferencesForRoom(room),
  );
  const usageSpecs = ensureRoomUsage(room).flatMap(
    (usage) => ROOM_USAGE_FURNITURE_SPECS[usage] || [],
  );
  const companions = recommendCompanionFurniture(
    room.type,
    [...recommended, ...usageSpecs].map(([type]) => type),
  ).map((item) => [item.type, item.variantId, item.reason, true]);
  const preferenceSpecs = questionnairePreferenceFurnitureSpecs(room);
  const seen = new Set();
  return [...recommended, ...usageSpecs, ...companions, ...preferenceSpecs].filter(([type, variant]) => {
    const key = `${type}:${variant || "standard"}`;
    if (!type || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const ROOM_USAGE_OPTIONS = Object.freeze({
  living_room: [
    { id: "rest", label: "休息聊天" },
    { id: "watch", label: "看電視／影音" },
    { id: "host", label: "接待客人" },
    { id: "read", label: "閱讀休息" },
    { id: "work", label: "閱讀／工作" },
    { id: "shared_dining", label: "客餐廳共用" },
    { id: "kids", label: "兒童使用" },
  ],
  bedroom: [
    { id: "sleep", label: "睡眠休息" },
    { id: "work", label: "閱讀／工作" },
    { id: "dressing", label: "收納更衣" },
    { id: "kids", label: "兒童使用" },
  ],
  kitchen: [
    { id: "cook", label: "日常下廚" },
    { id: "prep", label: "備料收納" },
    { id: "dine", label: "簡單用餐" },
    { id: "host", label: "招待聚餐" },
  ],
  storage: [
    { id: "store", label: "集中收納" },
    { id: "laundry", label: "洗衣整理" },
    { id: "work", label: "閱讀／工作" },
    { id: "kids", label: "兒童使用" },
  ],
  bathroom: [
    { id: "bathe", label: "盥洗淋浴" },
    { id: "store", label: "衛浴收納" },
  ],
  balcony: [
    { id: "laundry", label: "洗曬衣物" },
    { id: "rest", label: "休憩植栽" },
  ],
  garage: [
    { id: "store", label: "工具與用品收納" },
    { id: "flex", label: "保留停車淨空" },
  ],
  entryway: [
    { id: "arrival", label: "出入整理" },
    { id: "store", label: "鞋物收納" },
  ],
  hallway: [
    { id: "passage", label: "通行動線" },
    { id: "store", label: "薄型收納" },
  ],
  stair: [
    { id: "passage", label: "上下通行" },
  ],
  default: [
    { id: "flex", label: "彈性使用" },
    { id: "store", label: "收納整理" },
  ],
});

const ROOM_USAGE_FURNITURE_SPECS = Object.freeze({
  watch: [["tv-bench", "low"]],
  read: [["desk", "compact"], ["office-chair", "task"]],
  work: [["desk", "compact"], ["office-chair", "task"]],
  dressing: [["wardrobe", "two-door"], ["vanity-table", "standard"]],
  host: [["lounge-chair", "accent"]],
  dine: [["dining-table", "round-4"], ["dining-chair", "standard"]],
  prep: [["storage-cabinet", "low"]],
  store: [["storage-cabinet", "tall"]],
  laundry: [["storage-cabinet", "low"]],
  shared_dining: [["dining-table", "round-4"], ["dining-chair", "standard"]],
  arrival: [["mirror", "wall"]],
  // Corridors and stairs need clear circulation. Lighting belongs to the
  // ceiling/equipment flow, not the movable-furniture catalog.
  passage: [],
  kids: [["storage-cabinet", "low"]],
});

// 第 5 步只用用途情境幫使用者快速理解選擇；實際家具仍由既有
// 型錄、RAG 與第 6 步配置流程決定。用途不使用容易誤導的風格照片，
// 改以一致的空間用途圖示呈現，讓每個房型都有可辨識的視覺提示。
const ROOM_USAGE_VISUALS = Object.freeze({
  sleep: { symbol: "床", tone: "rest", caption: "以睡眠與放鬆為主" },
  rest: { symbol: "休", tone: "rest", caption: "保留舒適的休息留白" },
  watch: { symbol: "影", tone: "social", caption: "影音與日常休憩" },
  host: { symbol: "客", tone: "social", caption: "方便聊天與招待" },
  read: { symbol: "讀", tone: "focus", caption: "閱讀與安靜停留" },
  work: { symbol: "桌", tone: "focus", caption: "專注工作與收納" },
  dressing: { symbol: "衣", tone: "care", caption: "更衣與梳妝收納" },
  kids: { symbol: "童", tone: "play", caption: "保留安全活動範圍" },
  cook: { symbol: "爐", tone: "kitchen", caption: "以烹飪動線為主" },
  prep: { symbol: "檯", tone: "kitchen", caption: "備料與收納更順手" },
  dine: { symbol: "餐", tone: "social", caption: "規劃日常用餐位置" },
  shared_dining: { symbol: "餐", tone: "social", caption: "兼顧用餐與交流" },
  store: { symbol: "櫃", tone: "storage", caption: "提高收納與分類效率" },
  laundry: { symbol: "洗", tone: "service", caption: "保留洗曬與家事動線" },
  bathe: { symbol: "浴", tone: "care", caption: "以清潔與安全為主" },
  arrival: { symbol: "玄", tone: "arrival", caption: "進出、落塵與隨手收納" },
  passage: { symbol: "路", tone: "service", caption: "保留清楚通行寬度" },
  flex: { symbol: "多", tone: "flex", caption: "保留可調整的多用途空間" },
});

function roomUsageVisual(optionId) {
  return ROOM_USAGE_VISUALS[optionId] || ROOM_USAGE_VISUALS.flex;
}

function roomUsageOptions(room) {
  return ROOM_USAGE_OPTIONS[room?.type] || ROOM_USAGE_OPTIONS.default;
}

function ensureRoomUsage(room) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return [];
  const available = roomUsageOptions(room);
  const availableIds = new Set(available.map((item) => item.id));
  const existing = Array.isArray(requirement.usage)
    ? requirement.usage.filter((item) => availableIds.has(item))
    : [];
  requirement.usage = existing.length ? existing : [available[0]?.id].filter(Boolean);
  return requirement.usage;
}

function renderQuestionnaireRoomUsage(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireRoomUsageOptions) return;
  const selected = new Set(ensureRoomUsage(room));
  const selectedCount = selected.size;
  element.questionnaireRoomUsageOptions.innerHTML = roomUsageOptions(room).map((option) => {
    const visual = roomUsageVisual(option.id);
    const isSelected = selected.has(option.id);
    const isPrimary = isSelected && [...selected][0] === option.id;
    return `
    <label class="rp-room-usage-card ${isSelected ? "is-selected" : ""} ${isPrimary ? "is-primary" : ""}" data-usage-tone="${escapeHtml(visual.tone)}">
      <input type="checkbox" data-questionnaire-room-usage="${escapeHtml(option.id)}"
        ${isSelected ? "checked" : ""}>
      <span class="rp-room-usage-card-media rp-room-usage-card-schematic" aria-hidden="true">
        <span class="rp-room-usage-card-schematic-grid"><i></i><i></i><i></i><i></i></span>
        <b>${escapeHtml(visual.symbol)}</b>
      </span>
      <span class="rp-room-usage-card-copy"><strong>${escapeHtml(option.label)}</strong><small>${escapeHtml(visual.caption)}</small></span>
      <span class="rp-room-usage-card-state" aria-hidden="true">${isSelected ? '<span class="rp-room-usage-card-check">✓</span>' : ""}${isPrimary ? '<span class="rp-room-usage-card-label">主要</span>' : ""}</span>
    </label>`;
  }).join("");
  element.questionnaireRoomUsageOptions.dataset.selectionCount = String(selectedCount);
}

function roomFurnitureRequirement(roomId) {
  const requirement = state.roomRequirementModel.roomRequirements[roomId];
  if (!requirement) return null;
  requirement.furniture = {
    required: [],
    optional: [],
    selected: [],
    deferred: [],
    ...(requirement.furniture || {}),
  };
  return requirement.furniture;
}

function questionnaireFurnitureSelectionItem(offer, selectionPriority) {
  return {
    furniture_id: offer.furniture_id,
    normalized_type: offer.normalized_type,
    variant_id: offer.variant_id || "standard",
    name_zh: offer.name_zh || offer.name_zh_raw || offer.name_en,
    name_zh_raw: offer.name_zh_raw || offer.name_zh || offer.name_en,
    name_en: offer.name_en || "",
    model_url: offer.model_url,
    image_url: offer.image_url || offer.thumbnail_url || offer.preview_url || offer.main_image_url || offer.image || null,
    thumbnail_url: offer.thumbnail_url || null,
    preview_url: offer.preview_url || null,
    size_cm: { ...(offer.size_cm || {}) },
    primary_style: offer.primary_style || null,
    color: offer.color || null,
    material: offer.material || null,
    reason: offer.reason || "使用者於逐房問卷勾選",
    selection_source: "questionnaire_user_selection",
    user_selected: true,
    selection_priority: selectionPriority,
    count: 1,
  };
}

function questionnaireOfferMatchesRequestedType(offer) {
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[offer?.normalized_type];
  if (!rule?.keywords?.length) return true;
  const description = [
    offer.name_zh,
    offer.name_zh_raw,
    offer.name_en,
    offer.category_label,
    offer.taxonomy_type_zh,
  ].filter(Boolean).join(" ").toLowerCase();
  return rule.keywords.some((keyword) => description.includes(keyword.toLowerCase()));
}

function questionnaireFurnitureDisplayName(offer) {
  const name = offer.name_zh || offer.name_zh_raw || offer.name_en || offer.normalized_type;
  const typeLabel = REPLACEMENT_TYPE_LABELS[offer.normalized_type];
  if (!typeLabel) return name;
  return name.replace(/^(床|桌子與書桌|椅子與長凳)\s*-\s*/, `${typeLabel} - `);
}

function questionnaireFurnitureOffers(room) {
  const recommended = state.roomFurnitureRecommendations[room.id] || [];
  const selected = roomFurnitureRequirement(room.id)?.selected || [];
  const byId = new Map(
    [...selected, ...recommended]
      .filter((item) => item?.furniture_id && questionnaireOfferMatchesRequestedType(item))
      .map((item) => [String(item.furniture_id), item]),
  );
  return [...byId.values()];
}

function questionnaireFurnitureSizeLabel(offer) {
  const size = offer?.size_cm || {};
  const width = Math.round(Number(size.width || 0));
  const depth = Math.round(Number(size.depth || 0));
  return width && depth ? `${width} × ${depth} cm` : "尺寸待確認";
}

function questionnaireFurnitureGroups(room, offers) {
  const selectedItems = roomFurnitureRequirement(room.id)?.selected || [];
  const groups = new Map();
  offers.forEach((offer) => {
    const type = String(offer.normalized_type || "other");
    const group = groups.get(type) || { type, offers: [] };
    group.offers.push(offer);
    groups.set(type, group);
  });
  return [...groups.values()].map((group) => {
    // The catalog and RAG may use different type labels for the same item.
    // Preserve the user's choice by the catalog's stable furniture_id instead.
    const selected = selectedItems.find((item) => group.offers.some(
      (offer) => String(offer.furniture_id) === String(item?.furniture_id),
    ));
    const active = group.offers.find((offer) => (
      String(offer.furniture_id) === String(selected?.furniture_id)
    )) || group.offers[0];
    return {
      ...group,
      active,
      selected,
      role: questionnaireFurnitureRole(room, active),
    };
  }).sort((left, right) => left.role.rank - right.role.rank || left.type.localeCompare(right.type));
}

function knownUnavailableCatalogFurnitureIds() {
  const failedInstanceIds = new Set(
    (whiteViewer.getDiagnostics()?.failedFurniture || [])
      .map((item) => String(item.id)),
  );
  return new Set(
    (state.sceneData?.scene_objects || [])
      .filter((item) => failedInstanceIds.has(String(item.furniture_id)))
      .map((item) => String(item.catalog_furniture_id || ""))
      .filter(Boolean),
  );
}

async function verifyQuestionnaireCatalogModel(offer) {
  const modelUrl = String(offer?.model_url || "");
  if (!modelUrl || unavailableCatalogModelUrls.has(modelUrl)) return false;
  if (verifiedCatalogModelUrls.has(modelUrl)) return true;
  let available = false;
  glbThumbnailSequence = glbThumbnailSequence
    .catch(() => null)
    .then(async () => {
      await glbThumbnailViewer.loadScene(glbThumbnailScene(offer));
      available = !(glbThumbnailViewer.getDiagnostics()?.failedFurniture || []).length;
      if (available) {
        verifiedCatalogModelUrls.add(modelUrl);
      } else {
        unavailableCatalogModelUrls.add(modelUrl);
      }
    });
  await glbThumbnailSequence;
  return available;
}

function renderQuestionnaireFurnitureRecommendations(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireFurnitureOptions) return;
  const furniture = roomFurnitureRequirement(room.id);
  const offers = questionnaireFurnitureOffers(room);
  const groups = questionnaireFurnitureGroups(room, offers);
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = furniture?.preferenceText || "";
  }
  renderQuestionnaireFurniturePreferenceTags(room);
  document.querySelectorAll("[data-open-questionnaire-furniture-catalog]").forEach((button) => {
    if (!button.closest(".rp-questionnaire-furniture")) return;
    button.dataset.openQuestionnaireFurnitureCatalog = String(room.id);
  });
  const loading = questionnaireFurnitureInFlight.has(String(room.id));
  const error = state.roomFurnitureRecommendationErrors[room.id];
  const expectedTypes = questionnaireFurnitureSpecsForRoom(room);
  if (loading && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      `正在從資料庫取得「${room.label}」適用家具…`;
    element.questionnaireFurnitureOptions.innerHTML =
      '<p class="rp-control-hint">正在比對房間用途、色卡、材質與尺寸。</p>';
    return;
  }
  if (error && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      "資料庫推薦暫時無法載入，請稍後重試。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<button type="button" class="secondary-action" data-retry-questionnaire-furniture="${escapeHtml(room.id)}">重新取得推薦</button>`;
    return;
  }
  if (!offers.length) {
    element.questionnaireFurnitureStatus.textContent = expectedTypes.length
      ? "暫時找不到可直接配置的 GLB；此需求會在第 6 步列為待處理，現在仍可繼續。"
      : "這個空間沒有預設家具需求，可直接確認其他設定。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<div class="rp-questionnaire-furniture-empty">
        <p class="rp-control-hint">此需求不會卡住問卷。第 6 步會說明缺少 GLB 或配置風險，並提供替代、替換或刪除選項。</p>
        <button type="button" class="secondary-action" data-open-questionnaire-furniture-catalog="${escapeHtml(room.id)}">開啟家具資料庫</button>
      </div>`;
    return;
  }
  const similarCount = offers.filter((offer) => offer.recommendation_tier === "similar").length;
  element.questionnaireFurnitureStatus.textContent =
    similarCount
      ? `已依需求預選家具；另有 ${similarCount} 件相近推薦可自行調整。`
      : `已依「${room.label}」預選推薦家具；可取消、換款或從家具庫增加。`;
  element.questionnaireFurnitureOptions.innerHTML = groups.map((group) => {
    const offer = group.active;
    const furnitureId = String(offer.furniture_id);
    const selected = Boolean(group.selected);
    const quantity = Math.max(1, Math.min(6, Number(group.selected?.count) || 1));
    const selectedQuantity = selected ? quantity : 0;
    const roomDimensionsValue = roomDimensions(room);
    const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
    const maximumQuantity = Math.max(1, Math.min(6, Math.floor(
      (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
    ) || 1));
    const shortLabel = questionnaireFurnitureDisplayLabel(offer);
    return `
      <article class="${selected ? "is-selected" : ""}">
        <label class="rp-questionnaire-furniture-select">
          <input type="checkbox" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}"
            ${selected ? "checked" : ""}>
          <span>
            ${group.role?.label ? `<small class="rp-questionnaire-furniture-purpose">對應用途：${escapeHtml(group.role.label)}</small>` : ""}
            <strong>${escapeHtml(shortLabel)}</strong>
            <small>${escapeHtml(questionnaireFurnitureSizeLabel(offer))}</small>
            <small class="rp-questionnaire-furniture-reason">${escapeHtml(offer.reason || group.role?.label || "依本房用途與尺寸建議")}</small>
          </span>
        </label>
        <div class="rp-questionnaire-furniture-card-actions">
          <label class="rp-questionnaire-furniture-size">
            <span>尺寸</span>
            <select data-questionnaire-furniture-variant-type="${escapeHtml(group.type)}">
              ${group.offers.map((candidate, index) => `
                <option value="${escapeHtml(candidate.furniture_id)}" ${String(candidate.furniture_id) === furnitureId ? "selected" : ""}>
                  ${escapeHtml(questionnaireFurnitureDisplayLabel(candidate))} · ${escapeHtml(questionnaireFurnitureSizeLabel(candidate))}${index ? `（款式 ${index + 1}）` : ""}
                </option>
              `).join("")}
            </select>
          </label>
          <div class="rp-furniture-quantity" aria-label="${escapeHtml(questionnaireFurnitureDisplayName(offer))} 數量">
            <button type="button" data-questionnaire-furniture-quantity="-1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${selectedQuantity > 0 ? "" : "disabled"} aria-label="減少數量">−</button>
            <output>${selectedQuantity}</output>
            <button type="button" data-questionnaire-furniture-quantity="1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${selectedQuantity < maximumQuantity ? "" : "disabled"} aria-label="增加數量">＋</button>
          </div>
          <small class="rp-furniture-quantity-limit">最多 ${maximumQuantity} 件</small>
          ${offer.room_fit_checked === false ? '<small class="rp-questionnaire-fit-risk">尺寸僅為初步估計，第 6 步將檢查實際 GLB、門窗與走道。</small>' : ''}
        </div>
      </article>
    `;
  }).join("");
  element.questionnaireFurnitureOptions.dataset.furnitureControlsBound = "true";
}

function applyDefaultQuestionnaireFurnitureSelections(room, offers) {
  const furniture = roomFurnitureRequirement(room.id);
  if (!furniture || furniture.selected?.length || !offers.length) return;
  const program = questionnaireFurnitureProgram(room);
  const preferredDefaults = program.defaults.map((type) => offers.find((offer) => (
    offer.normalized_type === type
  ))).filter(Boolean);
  const defaults = preferredDefaults.length
    ? preferredDefaults
    : (program.fallbackDefaults || []).map((type) => offers.find((offer) => (
      offer.normalized_type === type && offer.room_fit_checked !== false
    ))).filter(Boolean);
  if (!defaults.length) return;
  furniture.selected = defaults.map((offer, index) => ({
    ...questionnaireFurnitureSelectionItem(offer, index + 1),
    default_recommendation: true,
    selection_source: preferredDefaults.length
      ? "questionnaire_rag_recommendation"
      : "questionnaire_catalog_fallback",
  }));
  furniture.required = [...new Set(defaults.map((offer) => offer.normalized_type))];
  furniture.optional = offers
    .filter((offer) => !defaults.some((selected) => String(selected.furniture_id) === String(offer.furniture_id)))
    .map((offer) => offer.normalized_type);
}

async function ensureQuestionnaireFurnitureRecommendations(
  room = activeQuestionnaireRoom(),
  { force = false } = {},
) {
  if (!room) return;
  const roomId = String(room.id);
  if (!force && state.roomFurnitureRecommendations[room.id]) return;
  if (questionnaireFurnitureInFlight.has(roomId)) return;
  questionnaireFurnitureInFlight.add(roomId);
  delete state.roomFurnitureRecommendationErrors[room.id];
  renderQuestionnaireFurnitureRecommendations(room);
  try {
    const specs = questionnaireFurnitureSpecsForRoom(room);
    const remembered = roomFurnitureRequirement(room.id);
    if (remembered?.selected?.length) {
      remembered.selected = remembered.selected.filter(questionnaireOfferMatchesRequestedType);
      remembered.required = [...new Set(
        remembered.selected.map((item) => item.normalized_type),
      )];
    }
    const unavailableCatalogIds = knownUnavailableCatalogFurnitureIds();
    const groups = await Promise.all(specs.map(async (spec, index) => {
      let offers = await catalogOffersForSpec(room, spec, index);
      if (!offers.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
      }
      let candidates = offers.filter((offer) =>
        !unavailableCatalogIds.has(String(offer.furniture_id))
        && Boolean(offer.model_url)
        && !unavailableCatalogModelUrls.has(String(offer.model_url)),
      );
      if (!candidates.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
        candidates = offers.filter((offer) =>
          !unavailableCatalogIds.has(String(offer.furniture_id))
          && Boolean(offer.model_url)
          && !unavailableCatalogModelUrls.has(String(offer.model_url)),
        );
      }
      const fittingCandidates = candidates.filter((offer) => replacementCandidateFitsRoom(offer, room));
      return questionnaireOffersWithSizeChoices(spec[0], candidates).map((offer) => ({
        ...offer,
        room_fit_checked: fittingCandidates.includes(offer),
        model_load_verified: verifiedCatalogModelUrls.has(String(offer.model_url)),
        model_load_verification: "deferred",
      }));
    }));
    let recommendedOffers = groups.flat();
    const program = questionnaireFurnitureProgram(room);
    const hasPreferredDefault = program.defaults.some((type) => (
      recommendedOffers.some((offer) => offer.normalized_type === type && offer.room_fit_checked !== false)
    ));
    if (!hasPreferredDefault && (program.fallbackDefaults || []).length) {
      const fallbackGroups = await Promise.all(program.fallbackDefaults.map(async (type, index) => {
        let offers = await catalogOffersForSpec(room, [type, "standard"], specs.length + index);
        if (!offers.length) {
          offers = await catalogFallbackOffersForSpec(room, [type, "standard"], specs.length + index);
        }
        const candidates = offers.filter((offer) =>
          !unavailableCatalogIds.has(String(offer.furniture_id))
          && Boolean(offer.model_url)
          && !unavailableCatalogModelUrls.has(String(offer.model_url))
          && replacementCandidateFitsRoom(offer, room),
        );
        return questionnaireOffersWithSizeChoices(type, candidates).map((offer) => ({
          ...offer,
          room_fit_checked: true,
          model_load_verified: verifiedCatalogModelUrls.has(String(offer.model_url)),
          model_load_verification: "deferred",
        }));
      }));
      recommendedOffers = [...recommendedOffers, ...fallbackGroups.flat()];
    }
    state.roomFurnitureRecommendations[room.id] = recommendedOffers;
    applyDefaultQuestionnaireFurnitureSelections(
      room,
      state.roomFurnitureRecommendations[room.id],
    );
  } catch (error) {
    console.warn("Questionnaire furniture recommendations", error);
    state.roomFurnitureRecommendationErrors[room.id] = errorMessage(error);
  } finally {
    questionnaireFurnitureInFlight.delete(roomId);
    if (String(activeQuestionnaireRoom()?.id) === roomId) {
      renderQuestionnaireFurnitureRecommendations(room);
    }
  }
}

function captureQuestionnaireFurniturePreference(room = activeQuestionnaireRoom()) {
  const furniture = roomFurnitureRequirement(room?.id);
  if (!furniture || !element.questionnaireFurniturePreference) return;
  furniture.preferenceText = element.questionnaireFurniturePreference.value.trim();
}

function updateQuestionnaireFurnitureSelection(furnitureId, selected) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const next = (furniture.selected || []).filter(
    (item) => String(item.furniture_id) !== String(furnitureId),
  );
  if (selected) {
    next.push(questionnaireFurnitureSelectionItem(offer, next.length + 1));
  }
  furniture.selected = next.map((item, index) => ({
    ...item,
    user_selected: true,
    selection_priority: index + 1,
  }));
  furniture.required = [...new Set(
    furniture.selected.map((item) => item.normalized_type),
  )];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some(
      (selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id),
    ))
    .map((item) => item.normalized_type);
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  requirement.confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  invalidateDownstreamFrom(
    "requirements",
    `「${room.label}」的家具需求已修改，第 6 步需要重新產生。`,
  );
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureVariant(normalizedType, furnitureId) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const previous = (furniture.selected || []).find(
    (item) => String(item.normalized_type) === String(normalizedType),
  );
  const next = (furniture.selected || []).filter(
    (item) => String(item.normalized_type) !== String(normalizedType),
  );
  next.push({
    ...questionnaireFurnitureSelectionItem(offer, next.length + 1),
    count: Math.max(1, Number(previous?.count) || 1),
    user_selected: true,
  });
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已更新 ${room.label} 的家具尺寸，第 6 步需要重新建立配置。`);
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureQuantity(furnitureId, delta) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !delta) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const selected = furniture.selected || [];
  const existing = selected.find((item) => String(item.furniture_id) === String(furnitureId));
  // Older saved questionnaire selections predate the count field.  A selected
  // item without it is one item, rather than an empty selection.
  const current = existing ? Math.max(1, Number(existing.count) || 1) : 0;
  const roomDimensionsValue = roomDimensions(room);
  const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
  const maximum = Math.max(1, Math.min(6, Math.floor(
    (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
  ) || 1));
  const nextCount = Math.max(0, Math.min(maximum, current + Number(delta)));
  if (nextCount === current) {
    setStatus(`「${questionnaireFurnitureDisplayName(offer)}」依本房可用面積最多可先選 ${maximum} 件。`);
    return;
  }
  const next = selected.filter((item) => String(item.furniture_id) !== String(furnitureId));
  if (nextCount > 0) {
    next.push({
      ...(existing || questionnaireFurnitureSelectionItem(offer, next.length + 1)),
      count: nextCount,
      user_selected: true,
    });
  }
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some((selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id)))
    .map((item) => item.normalized_type);
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `「${room.label}」的家具數量已修改，第 6 步需要重新產生。`);
  scheduleSave("requirements");
}

function refreshQuestionnaireFurnitureRecommendations() {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  delete state.roomFurnitureRecommendations[room.id];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  invalidateDownstreamFrom("requirements", `已更新「${room.label}」的家具偏好，第 6 步需要重新產生。`);
  scheduleSave("requirements");
  void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
}

function specsFromSelectionResponse(room, response, fallbackSpecs) {
  const selectedRoom = (response.rooms || []).find((item) => item.room_id === room.id);
  if (!selectedRoom?.items?.length) return fallbackSpecs;
  const specs = [];
  selectedRoom.items.forEach((item) => {
    const count = Math.max(1, Math.min(6, Number(item.count) || 1));
    for (let index = 0; index < count; index += 1) {
      specs.push([
        item.normalized_type,
        item.variant_id || item.variantId || "standard",
        item.reason || item.match_reason || item.selection_source || response.source,
        item.auto_added === true,
        item,
      ]);
    }
  });
  return specs.length ? specs : fallbackSpecs;
}

function specsAllowedByRoomFeasibility(requirement, specs) {
  const blocked = new Set(
    (requirement?.feasibility || [])
      .filter((item) => item.forcePlacement === false)
      .map((item) => item.optionId),
  );
  return specs.filter(([type, variant]) => {
    const normalized = `${type} ${variant}`.toLowerCase();
    if (blocked.has("bathtub") && normalized.includes("bathtub")) return false;
    if (blocked.has("double_vanity") && (
      normalized.includes("double-vanity")
      || normalized.includes("double_vanity")
    )) return false;
    if (blocked.has("large_dining_table") && (
      normalized.includes("large-dining")
      || normalized.includes("large_dining")
      || normalized.includes("rect-6")
      || normalized.includes("six-seat")
    )) return false;
    return true;
  });
}

async function autoLayoutFurniture() {
  state.furniture2d = [];
  const roomPlans = state.rooms.map((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const selectedCatalogFurniture = requirement?.furniture?.selected || [];
    const userSelectedSpecs = selectedCatalogFurniture.flatMap((item) => {
      const count = Math.max(1, Math.min(6, Number(item.count) || 1));
      return Array.from({ length: count }, () => [
        item.normalized_type,
        item.variant_id || "standard",
        item.reason || "使用者於逐房問卷勾選",
        false,
        item,
      ]);
    });
    const requestedSpecs = userSelectedSpecs.length
      ? userSelectedSpecs
      : recommendedFurnitureForRoom(room);
    const visualPreferences = visualPreferencesForRoom(room);
    const preferredSpecs = userSelectedSpecs.length
      ? requestedSpecs
      : applyVisualPreferencesToSpecs(requestedSpecs, visualPreferences);
    const companionSpecs = userSelectedSpecs.length
      ? []
      : recommendCompanionFurniture(
        room.type,
        preferredSpecs.map(([type]) => type),
      ).map((item) => [item.type, item.variantId, item.reason, true]);
    const specs = specsAllowedByRoomFeasibility(
      requirement,
      [...preferredSpecs, ...companionSpecs],
    );
    const placementPreferences = Object.assign(
      {},
      ...visualPreferences.map((preference) => preference.engine_effects),
    );
    return {
      room,
      specs,
      userSelectedSpecs,
      visualPreferences,
      placementPreferences,
    };
  });
  const requirementsPayload = buildRoomRequirementsPayload(
    state.roomRequirementModel,
    {
      planGeometry: confirmedFloorplanEditor(),
      questionnaireVersion: state.visualCatalogVersion,
    },
  );
  let selection = null;
  try {
    const catalogOffers = await catalogOffersForRoomPlans(roomPlans);
    selection = await api("/api/agent/furniture/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rooms: roomPlans.map(({ room }) => ({
          room_id: room.id,
          room_type: room.type,
          label: room.label,
        })),
        offers: catalogOffers,
        style_id: state.activeStyleId,
        context: {
          questionnaire: requirementsPayload,
          basic_answers: state.basicAnswers,
          room_requirements: state.roomRequirementModel.roomRequirements,
          room_surface_assignments: roomSurfaceAssignments(),
          visual_preferences: Object.fromEntries(roomPlans.map(({ room, visualPreferences }) => [
            room.id,
            visualPreferences,
          ])),
        },
      }),
    });
  } catch (error) {
    console.warn("Yen furniture selection fallback", error);
  }
  for (const { room, specs, userSelectedSpecs, placementPreferences } of roomPlans) {
    const selectedSpecs = userSelectedSpecs.length
      ? specs
      : selection
      ? specsAllowedByRoomFeasibility(
        state.roomRequirementModel.roomRequirements[room.id],
        specsFromSelectionResponse(room, selection, specs),
      )
      : specs;
    const roomItems = [];
    selectedSpecs.forEach(([type, variant, reason, autoAdded, catalogItem], index) => {
      try {
        const catalogSize = catalogItem?.size_cm || {};
        const item = createFurniture2DItem(type, variant, {
          id: `${room.id}-${type}-${index + 1}`,
          roomId: room.id,
          userRequired: catalogItem?.user_selected === true,
          widthCm: catalogSize.width,
          depthCm: catalogSize.depth,
          heightCm: catalogSize.height,
        });
        item.roomId = room.id;
        if (catalogItem?.model_url) {
          item.label = catalogItem.name_zh
            || catalogItem.name_zh_raw
            || catalogItem.name_en
            || item.label;
          item.catalogFurnitureId = catalogItem.furniture_id;
          item.model_url = catalogItem.model_url;
          item.primaryStyle = catalogItem.primary_style || null;
          item.catalogColor = catalogItem.color || null;
          item.catalogMaterial = catalogItem.material || null;
          item.selectionSource =
            catalogItem.selection_source || "questionnaire_catalog_rag";
          item.catalogMatchReason =
            catalogItem.reason || catalogItem.match_reason || reason || "";
          item.questionnaireMatchScore =
            Number(catalogItem.questionnaire_match_score) || 0;
          item.selectionPriority =
            Number(catalogItem.selection_priority) || index + 1;
        }
        item.reason = reason
          || `依「${room.label}」的使用需求與可用空間先配置，可再調整。`;
        item.autoAdded = autoAdded === true;
        roomItems.push(item);
      } catch (error) {
        console.warn(error);
      }
    });
    if (!roomItems.length) continue;
    let layout;
    try {
      layout = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          placement_room_id: room.id,
          placement_variant: activeSchemeId(),
          placement_preferences: placementPreferences,
          scene_objects: roomItems.map((item) =>
            toSceneFurniture(item, { positionLocked: false })
          ),
        }),
      });
    } catch (error) {
      // A single room can be retried from step 6; it must not block the whole house.
      console.warn("Room furniture layout deferred", room.id, error);
      roomItems.forEach((item) => {
        item.placementFailed = true;
        item.placementReason = errorMessage(error);
        state.furniture2d.push(item);
      });
      continue;
    }
    const placedById = new Map(
      (layout.scene_objects || []).map((item) => [item.furniture_id, item]),
    );
    roomItems.forEach((item) => {
      const placed = placedById.get(item.id);
      if (!placed) return;
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      state.furniture2d.push(item);
    });
  }
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  const scheme = activeScheme();
  scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
  scheme.stale = false;
  scheme.staleReason = "";
  state.activeLayoutRoomId = "all";
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  scheduleSave("layout_2d");
}

async function relayoutFurnitureForScheme(sourceFurniture, schemeId) {
  const placedFurniture = [];
  for (const room of state.rooms) {
    const roomItems = sourceFurniture
      .filter((item) => item.roomId === room.id)
      .map((item) => ({
        ...JSON.parse(JSON.stringify(item)),
        placementFailed: false,
        placementReason: "",
      }));
    if (!roomItems.length) continue;
    const layout = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(schemeId),
        placement_room_id: room.id,
        placement_variant: schemeId,
        scene_objects: roomItems.map((item) =>
          toSceneFurniture(item, { positionLocked: false })
        ),
      }),
    });
    const placedById = new Map(
      (layout.scene_objects || []).map((item) => [item.furniture_id, item]),
    );
    roomItems.forEach((item) => {
      const placed = placedById.get(item.id);
      if (!placed) return;
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      placedFurniture.push(item);
    });
  }
  return placedFurniture.some((item) => item.placementFailed) ? null : placedFurniture;
}

function renderLayoutRoomFilter() {
  if (!element.layoutRoomFilter) return;
  const roomsWithFurniture = new Set(state.furniture2d.map((item) => item.roomId));
  const roomOptions = state.rooms
    .filter((room) => roomsWithFurniture.has(room.id))
    .map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`)
    .join("");
  element.layoutRoomFilter.innerHTML = `<option value="all">全屋</option>${roomOptions}`;
  if (
    state.activeLayoutRoomId !== "all"
    && !state.rooms.some((room) => room.id === state.activeLayoutRoomId)
  ) {
    state.activeLayoutRoomId = "all";
  }
  element.layoutRoomFilter.value = state.activeLayoutRoomId || "all";
  renderLayoutRoomMaterials();
}

function renderLayoutRoomMaterials() {
  if (!element.layoutRoomMaterials) return;
  const rooms = state.activeLayoutRoomId === "all"
    ? state.rooms
    : state.rooms.filter((room) => room.id === state.activeLayoutRoomId);
  element.layoutRoomMaterials.innerHTML = rooms.map((room) => {
    const rawSurfaces = state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces;
    if (!rawSurfaces) return "";
    const surfaces = normalizedRoomSurfaces(room, rawSurfaces || {});
    return `
      <span class="rp-layout-room-material">
        <strong>${escapeHtml(room.label)}</strong>
        <i style="--surface-swatch:${escapeHtml(surfaces.wallDefault?.color || "#f2f0ec")}"></i>
        <small>牆 ${escapeHtml(surfaces.wallDefault?.materialId || "未設定")}</small>
        <i style="--surface-swatch:${escapeHtml(surfaces.floor?.color || "#b99b78")}"></i>
        <small>地 ${escapeHtml(surfaces.floor?.materialId || "未設定")}</small>
      </span>
    `;
  }).join("");
  renderLayoutSurfaceOverlay(rooms);
}

function materialPreviewForLayout(kind, materialId) {
  return catalogMaterialOptionsForPack(kind, activeQuestionnairePack())
    .find((option) => option.id === materialId)?.materialPreview || "";
}

function renderLayoutSurfaceOverlay(rooms) {
  if (!element.layoutRoomOverlay || !element.layoutImage?.naturalWidth) return;
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  const patterns = rooms.map((room, index) => {
    const surfaces = normalizedRoomSurfaces(
      room,
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {},
    );
    const preview = materialPreviewForLayout("floor", surfaces.floor?.materialId);
    if (!preview) return "";
    const patternId = `layout-floor-${index}`;
    return `<pattern id="${patternId}" width="100" height="100" patternUnits="userSpaceOnUse">
      <image href="${escapeHtml(preview)}" width="100" height="100" preserveAspectRatio="xMidYMid slice"/>
    </pattern>`;
  }).join("");
  const polygons = rooms.map((room, index) => {
    const surfaces = normalizedRoomSurfaces(
      room,
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {},
    );
    const preview = materialPreviewForLayout("floor", surfaces.floor?.materialId);
    if (!preview) return "";
    return `<polygon points="${roomPolygonSvg(room)}" fill="url(#layout-floor-${index})"
      fill-opacity="0.28" pointer-events="none"/>`;
  }).join("");
  element.layoutRoomOverlay.innerHTML = patterns ? `<defs>${patterns}</defs>${polygons}` : "";
}

function renderFurnitureLibrary(filterText = "") {
  const term = filterText.trim().toLowerCase();
  const variants = FURNITURE_2D_LIBRARY.flatMap((category) =>
    category.variants.map((variant) => ({ category, variant }))
  ).filter(({ category, variant }) =>
    !term || `${category.label}${variant.label}${category.type}`.toLowerCase().includes(term)
  );
  element.furnitureLibrary.innerHTML = variants.map(({ category, variant }) => `
    <button type="button" data-add-furniture-type="${escapeHtml(category.type)}" data-add-furniture-variant="${escapeHtml(variant.id)}">
      <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(variant.iconPath)}"/></svg>
      <strong>${escapeHtml(variant.label)}</strong>
      <small>${variant.widthCm} × ${variant.depthCm} cm</small>
    </button>
  `).join("");
}

function furniturePixelPosition(item) {
  const center = planCenterCm();
  return planCmToLayerPixel(
    {
      x: center.x + item.xCm,
      y: center.y + item.yCm,
    },
    planGeometry(),
    layoutPixelsPerCm(),
  );
}

function layoutPixelsPerCm() {
  const imageRect = imageContentRect(element.layoutImage);
  const naturalRatio = imageRect.width / Math.max(element.layoutImage.naturalWidth, 1);
  return (1 / planGeometry().scale) * naturalRatio;
}

function itemCollision(item) {
  const room = state.rooms.find((candidate) => candidate.id === item.roomId);
  if (!room) return true;
  const center = planCenterCm();
  const x = center.x + item.xCm;
  const y = center.y + item.yCm;
  const xs = room.polygon_cm.map((point) => point.x);
  const ys = room.polygon_cm.map((point) => point.y);
  const footprint = furnitureCollisionFootprintCm(item);
  const halfWidth = footprint.width / 2;
  const halfDepth = footprint.depth / 2;
  if (
    x - halfWidth < Math.min(...xs)
    || x + halfWidth > Math.max(...xs)
    || y - halfDepth < Math.min(...ys)
    || y + halfDepth > Math.max(...ys)
  ) return true;
  return state.furniture2d.some((other) => {
    if (other.id === item.id || other.roomId !== item.roomId) return false;
    const otherFootprint = furnitureCollisionFootprintCm(other);
    return Math.abs(other.xCm - item.xCm) < (otherFootprint.width + footprint.width) / 2
      && Math.abs(other.yCm - item.yCm) < (otherFootprint.depth + footprint.depth) / 2;
  });
}

function renderLayoutFurniture() {
  if (!element.layoutImage.naturalWidth) return;
  const scale = layoutPixelsPerCm();
  const visibleFurniture = state.activeLayoutRoomId === "all"
    ? state.furniture2d
    : state.furniture2d.filter((item) => item.roomId === state.activeLayoutRoomId);
  if (
    state.selectedFurniture2dId
    && !visibleFurniture.some((item) => item.id === state.selectedFurniture2dId)
  ) {
    state.selectedFurniture2dId = visibleFurniture[0]?.id || null;
  }
  element.layoutLayer.innerHTML = visibleFurniture.map((item) => {
    const pixel = furniturePixelPosition(item);
    const style = furnitureFootprintStyle(item, scale);
    const invalid = item.placementFailed === true || itemCollision(item);
    item.invalid = invalid;
    return `
      <button type="button" class="rp-2d-furniture ${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${invalid ? "is-invalid" : ""}"
        data-furniture-2d-id="${escapeHtml(item.id)}"
        style="left:${pixel.x}px;top:${pixel.y}px;width:${style.width};height:${style.height};transform:${style.transform}">
        <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(item.iconPath)}"/></svg>
        <span>${escapeHtml(item.label)}<br>${item.widthCm} × ${item.depthCm} cm</span>
      </button>
    `;
  }).join("");
  element.layoutFurnitureList.innerHTML = visibleFurniture.map((item) => `
    <button type="button"
      class="${item.id === state.selectedFurniture2dId ? "is-active" : ""}"
      data-select-layout-furniture="${escapeHtml(item.id)}">
      <span><strong>${escapeHtml(item.label)}</strong><small>${item.widthCm} × ${item.depthCm} cm</small></span>
      <span class="rp-model-state">${item.catalogFurnitureId || item.model_url ? "GLB" : "圖示"}</span>
      <span aria-hidden="true">›</span>
    </button>
  `).join("");
  renderSelectedFurnitureEditor();
}

function configurationBlockingFurniture() {
  const deferredIds = configurationDeferredFurnitureIds();
  const sceneById = new Map(
    (state.sceneData?.scene_objects || []).map((item) => [String(item.furniture_id), item]),
  );
  const modelFailureIds = new Set(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => String(item.id))
      : [],
  );
  return state.furniture2d.filter((item) => {
    if (deferredIds.has(String(item.id))) return false;
    const sceneObject = sceneById.get(String(item.id));
    return item.placementFailed === true
      || sceneObject?.placement_failed === true
      || modelFailureIds.has(String(item.id))
      || itemCollision(item);
  });
}

function configurationDeferredFurnitureIds() {
  const deferred = state.rooms.flatMap((room) =>
    state.roomRequirementModel.roomRequirements[room.id]?.furniture?.deferred || [],
  );
  return new Set([
    ...deferred,
    ...(state.roomRequirementModel.unassignedDeferredFurniture || []),
  ].map((item) => String(item.id)));
}

const GENERATIVE_EQUIPMENT_OPTIONS = Object.freeze({
  kitchen: {
    primary: [["cook", "日常烹飪"], ["light_meals", "輕食備餐"], ["storage", "收納為主"]],
    directions: [["base_cabinet", "基本櫥櫃"], ["tall_pantry", "高櫃／食品儲藏"], ["island", "中島或吧台"], ["dishwasher", "洗碗設備"]],
    exclusions: [["island", "不要中島"], ["open_shelves", "不要開放層架"]],
  },
  bathroom: {
    primary: [["shower", "淋浴為主"], ["bathe", "希望浴缸"], ["storage", "收納為主"]],
    directions: [["walk_in_shower", "乾濕分離淋浴"], ["single_vanity", "單人洗手台"], ["double_vanity", "雙人洗手台"], ["bathtub", "浴缸"]],
    exclusions: [["bathtub", "不要浴缸"], ["glass_partition", "不要玻璃隔間"]],
  },
  balcony: {
    primary: [["laundry", "洗曬衣物"], ["rest", "休閒植栽"], ["storage", "儲藏為主"]],
    directions: [["laundry_zone", "洗衣與曬衣區"], ["planters", "植栽區"], ["folding_table", "折疊桌"], ["storage_cabinet", "防潮收納"]],
    exclusions: [["planters", "不要植栽"], ["laundry_zone", "不要洗曬區"]],
  },
});

function isGenerativeEquipmentRoom(room = activeQuestionnaireRoom()) {
  return Boolean(GENERATIVE_EQUIPMENT_OPTIONS[room?.type || room?.room_type]);
}

function structuralIntentInText(value = "") {
  return /擴建|延伸|移牆|拆牆|加房間|隔間|改門|改窗|打掉牆/.test(String(value));
}

function renderGenerativeEquipment(room = activeQuestionnaireRoom()) {
  const host = element.questionnaireGenerativeEquipment;
  if (!host || !room) return;
  const definition = GENERATIVE_EQUIPMENT_OPTIONS[room.type || room.room_type];
  host.hidden = !definition;
  if (!definition) return;
  const requirement = activeRoomRequirement();
  const equipment = requirement.generativeEquipment || {};
  element.questionnaireGenerativePrimaryUse.innerHTML = [
    '<option value="">請選擇</option>',
    ...definition.primary.map(([id, label]) => `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`),
  ].join("");
  element.questionnaireGenerativePrimaryUse.value = equipment.primaryUse || "";
  const selected = new Set(equipment.equipmentDirection || []);
  const excluded = new Set(equipment.mustNotHave || []);
  element.questionnaireGenerativeDirections.innerHTML = definition.directions.map(([id, label]) => `
    <label class="${selected.has(id) ? "is-selected" : ""}"><input type="checkbox" data-generative-direction="${escapeHtml(id)}" ${selected.has(id) ? "checked" : ""}><span>${escapeHtml(label)}</span></label>
  `).join("");
  element.questionnaireGenerativeExclusions.innerHTML = definition.exclusions.map(([id, label]) => `
    <label class="${excluded.has(id) ? "is-selected" : ""}"><input type="checkbox" data-generative-exclusion="${escapeHtml(id)}" ${excluded.has(id) ? "checked" : ""}><span>${escapeHtml(label)}</span></label>
  `).join("");
  element.questionnaireGenerationNotes.value = equipment.generationNotes || "";
  element.questionnaireGenerationWarning.textContent = structuralIntentInText(equipment.generationNotes)
    ? "偵測到可能影響結構或面積的描述。系統會維持現有牆、門、窗、樑、柱與房間大小，請確認需求會在現有空間內取捨。"
    : "此說明會一起送入 RAG 與最終生圖；系統不會擴建空間或移動固定結構。";
}

function updateGenerativeEquipment(room = activeQuestionnaireRoom()) {
  const requirement = activeRoomRequirement();
  if (!room || !requirement || !isGenerativeEquipmentRoom(room)) return;
  const directions = $$('[data-generative-direction]:checked', element.questionnaireGenerativeDirections)
    .map((input) => input.dataset.generativeDirection);
  const exclusions = $$('[data-generative-exclusion]:checked', element.questionnaireGenerativeExclusions)
    .map((input) => input.dataset.generativeExclusion);
  const notes = element.questionnaireGenerationNotes.value.trim();
  requirement.generativeEquipment = {
    ...(requirement.generativeEquipment || {}),
    required: true,
    primaryUse: element.questionnaireGenerativePrimaryUse.value || null,
    equipmentDirection: directions,
    mustNotHave: exclusions,
    priority: directions[0] || null,
    fitStatus: directions.some((id) => exclusions.includes(id)) ? "tradeoff_required" : "pending",
    generationNotes: notes,
    structuralIntentAcknowledged: structuralIntentInText(notes),
  };
  requirement.confirmed = false;
  renderGenerativeEquipment(room);
  renderQuestionnaireRoomSections();
  scheduleSave("requirements");
}

function updateGenerativeEquipmentNotes(room = activeQuestionnaireRoom()) {
  const requirement = activeRoomRequirement();
  if (!room || !requirement || !isGenerativeEquipmentRoom(room)) return;
  const notes = element.questionnaireGenerationNotes.value.trim();
  requirement.generativeEquipment = {
    ...(requirement.generativeEquipment || {}),
    required: true,
    generationNotes: notes,
    structuralIntentAcknowledged: structuralIntentInText(notes),
  };
  requirement.confirmed = false;
  element.questionnaireGenerationWarning.textContent = structuralIntentInText(notes)
    ? "偵測到可能影響固定結構或空間大小的描述。生圖仍會遵守已確認的牆、門、窗與房間尺寸，請確認這是風格想像而非施工指示。"
    : "補充會一併送給 RAG 與生圖流程；系統會依已確認的房間尺寸與固定結構保留可行的配置。";
  scheduleSave("requirements");
}

function generativeEquipmentGate(room = activeQuestionnaireRoom()) {
  if (!isGenerativeEquipmentRoom(room)) return { ready: true };
  const equipment = activeRoomRequirement()?.generativeEquipment || {};
  if (!equipment.primaryUse || !(equipment.equipmentDirection || []).length) {
    return { ready: false, message: "請選擇主要使用方式與至少一項設備方向，才能讓生圖遵守此房尺寸與動線。" };
  }
  if ((equipment.equipmentDirection || []).some((id) => (equipment.mustNotHave || []).includes(id))) {
    return { ready: false, message: "同一設備同時被選擇與排除，請保留其中一種需求或改選依尺寸推薦。" };
  }
  return { ready: true };
}

const UNASSIGNED_CONFIGURATION_ROOM_ID = "unassigned";

function configurationRoomById(roomId) {
  return state.rooms.find((candidate) => String(candidate.id) === String(roomId)) || null;
}

function configurationFurnitureBelongsToRoom(item, roomId) {
  const key = String(roomId || UNASSIGNED_CONFIGURATION_ROOM_ID);
  const itemRoom = configurationRoomById(item.roomId);
  if (key === UNASSIGNED_CONFIGURATION_ROOM_ID) {
    return !itemRoom;
  }
  return String(item.roomId) === key;
}

function configurationFurnitureForRoom(roomId, items = state.furniture2d) {
  return items.filter((item) => configurationFurnitureBelongsToRoom(item, roomId));
}

function unassignedDeferredFurniture() {
  state.roomRequirementModel.unassignedDeferredFurniture =
    state.roomRequirementModel.unassignedDeferredFurniture || [];
  return state.roomRequirementModel.unassignedDeferredFurniture;
}

function deferredFurnitureRecord(item, reason) {
  return {
    id: item.id,
    furniture_id: item.catalogFurnitureId || item.id,
    normalized_type: item.type,
    label: item.label,
    reason,
  };
}

function questionnaireFurniturePreviewUrl(offer = {}) {
  return replacementCandidateImageUrl(offer);
}

function questionnaireFurniturePreviewMarkup(offer = {}) {
  const preview = questionnaireFurniturePreviewUrl(offer);
  const label = questionnaireFurnitureDisplayLabel(offer);
  return `
    <div class="rp-questionnaire-furniture-preview">
      <img
        class="${preview ? "" : "is-loading"}"
        src="${escapeHtml(preview || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")}"
        alt="${escapeHtml(label)} 商品預覽"
        data-questionnaire-furniture-thumbnail="${escapeHtml(offer.furniture_id || "")}"
        loading="lazy"
      />
      <span aria-hidden="true">家具預覽</span>
    </div>
  `;
}

function configurationBlockingFurnitureByRoom(blocking = configurationBlockingFurniture()) {
  const groups = new Map();
  blocking.forEach((item) => {
    const room = configurationRoomById(item.roomId);
    const roomId = String(room?.id || UNASSIGNED_CONFIGURATION_ROOM_ID);
    if (!groups.has(roomId)) {
      groups.set(roomId, {
        roomId,
        roomLabel: room?.label || room?.name || "未指定空間",
        items: [],
      });
    }
    groups.get(roomId).items.push(item);
  });
  return [...groups.values()];
}

function configurationDeferredFurnitureByRoom() {
  const rooms = state.rooms.flatMap((room) => {
    const deferred =
      state.roomRequirementModel.roomRequirements[room.id]?.furniture?.deferred || [];
    return deferred.length
      ? [{ roomId: room.id, roomLabel: room.label, items: deferred }]
      : [];
  });
  const unassigned = state.roomRequirementModel.unassignedDeferredFurniture || [];
  if (unassigned.length) {
    rooms.push({
      roomId: UNASSIGNED_CONFIGURATION_ROOM_ID,
      roomLabel: "未指定空間",
      items: unassigned,
    });
  }
  return rooms;
}

function configurationModelFailures() {
  return new Map(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => [String(item.id), item.reason])
      : [],
  );
}

function syncFinalValidationToConfiguration(validatedObjects = []) {
  if (!state.sceneData || !Array.isArray(validatedObjects) || !validatedObjects.length) {
    return configurationBlockingFurniture();
  }
  const validatedById = new Map(
    validatedObjects.map((item) => [String(item.furniture_id), item]),
  );
  state.sceneData.scene_objects = (state.sceneData.scene_objects || []).map((item) => {
    const validated = validatedById.get(String(item.furniture_id));
    if (!validated) return item;
    return {
      ...item,
      ...validated,
      position_cm: { ...(item.position_cm || {}), ...(validated.position_cm || {}) },
      size_cm: { ...(item.size_cm || {}), ...(validated.size_cm || {}) },
    };
  });
  state.sceneData.scene_objects.forEach((item) => {
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      item,
      furniture2dDefaultsForSceneObject(item),
    );
  });
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  renderConfigurationPlan();
  return configurationBlockingFurniture();
}

function configurationPlanPixelsPerCm() {
  if (!element.configurationPlanImage?.naturalWidth) return 0;
  const imageRect = imageContentRect(element.configurationPlanImage);
  const naturalRatio = imageRect.width
    / Math.max(element.configurationPlanImage.naturalWidth, 1);
  return (1 / planGeometry().scale) * naturalRatio;
}

function configurationFurniturePixelPosition(item) {
  const center = planCenterCm();
  return planCmToLayerPixel(
    {
      x: center.x + item.xCm,
      y: center.y + item.yCm,
    },
    planGeometry(),
    configurationPlanPixelsPerCm(),
  );
}

function configurationFurnitureNumber(item, fallbackIndex = state.furniture2d.indexOf(item)) {
  const sceneIndex = sceneObjectIndexByFurnitureId(item.id);
  return sceneIndex >= 0 ? sceneIndex + 1 : fallbackIndex + 1;
}

function renderConfigurationPlan() {
  if (!element.configurationPlanImage) return;
  pruneRetiredAppliances();
  const planSource = element.layoutImage.currentSrc || element.layoutImage.src;
  if (planSource && element.configurationPlanImage.src !== planSource) {
    element.configurationPlanImage.src = planSource;
  }
  syncOverlayToImage(
    element.configurationPlanStage,
    element.configurationPlanImage,
    element.configurationPlanLayer,
  );

  const blocking = configurationBlockingFurniture();
  const blockingIds = new Set(blocking.map((item) => String(item.id)));
  const modelFailures = configurationModelFailures();
  const scale = configurationPlanPixelsPerCm();
  if (scale > 0 && state.showFurnitureNumbers) {
    element.configurationPlanLayer.innerHTML = state.furniture2d.map((item, index) => {
      const pixel = configurationFurniturePixelPosition(item);
      const style = furnitureFootprintStyle(item, scale);
      const invalid = blockingIds.has(String(item.id));
      const furnitureNumber = configurationFurnitureNumber(item, index);
      return `
        <button type="button"
          class="rp-configuration-furniture ${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${invalid ? "is-invalid" : ""}"
          data-select-configuration-furniture="${escapeHtml(item.id)}"
          aria-label="家具 ${furnitureNumber} ${escapeHtml(item.label)}"
          style="left:${pixel.x}px;top:${pixel.y}px;width:${style.width};height:${style.height};transform:${style.transform}">
          <b>${furnitureNumber}</b>
        </button>
      `;
    }).join("");
  }

  element.configurationPlanFurnitureList.innerHTML = state.furniture2d.map((item, index) => {
    const furnitureNumber = configurationFurnitureNumber(item, index);
    return `
      <button type="button"
        class="${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${blockingIds.has(String(item.id)) ? "is-invalid" : ""}"
        data-select-configuration-furniture="${escapeHtml(item.id)}">
        <b>${furnitureNumber}</b>
        <span><strong>${escapeHtml(item.label)}</strong><small>${item.widthCm} × ${item.depthCm} cm</small></span>
        <span>${blockingIds.has(String(item.id)) ? "待處理" : "合法"}</span>
      </button>
    `;
  }).join("") || "<p class=\"rp-control-hint\">目前沒有家具。</p>";

  element.configurationPendingCount.textContent = String(blocking.length);
  const issueBadge = $("#scene-sidebar-issue-badge");
  if (issueBadge) {
    issueBadge.hidden = blocking.length === 0;
    issueBadge.textContent = String(blocking.length);
  }
  const blockingRooms = configurationBlockingFurnitureByRoom(blocking);
  const deferredRooms = configurationDeferredFurnitureByRoom();
  const blockingMarkup = blockingRooms.map((group) => {
    const placementFailures = group.items.filter(
      (item) => !modelFailures.has(String(item.id)),
    );
    const summary = placementFailures.length
      ? `${placementFailures.length} 件因碰撞、淨空或房間尺寸無法放入`
      : "資料庫模型無法載入，可更換或同意本次暫緩";
    const items = group.items.map((item) => {
      const furnitureNumber = configurationFurnitureNumber(item);
      const furnitureKey = String(item.id);
      const reason = modelFailures.get(furnitureKey)
        || item.placementReason
        || "家具碰撞、超出房間或淨空不足。";
      const modelFailed = modelFailures.has(furnitureKey);
      const reflowing = configurationReflowInFlight.has(furnitureKey);
      const reflowLocked = configurationReflowInFlight.size > 0;
      const repairAction = modelFailed
        ? `<button type="button" data-replace-configuration-furniture="${escapeHtml(item.id)}">更換家具</button>`
        : `<button type="button" data-reflow-configuration-furniture="${escapeHtml(item.id)}"
            ${reflowLocked ? "disabled" : ""}>${reflowing ? "重新配置中…" : "只重排此家具"}</button>
          <button type="button" data-replace-configuration-furniture="${escapeHtml(item.id)}">更換較小款</button>`;
      return `
        <div class="rp-configuration-pending-item">
          <b>${furnitureNumber}</b>
          <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(reason)}</small></span>
          <div>
            <button type="button" data-select-configuration-furniture="${escapeHtml(item.id)}">定位</button>
            ${repairAction}
          </div>
        </div>
      `;
    }).join("");
    return `
      <section class="rp-configuration-pending-room">
        <header>
          <div><strong>${escapeHtml(group.roomLabel)}</strong><small>${escapeHtml(summary)}</small></div>
          ${group.items.length ? `<button type="button"
            data-prioritize-configuration-room="${escapeHtml(group.roomId)}">同意擇優配置</button>` : ""}
        </header>
        ${items}
      </section>
    `;
  }).join("");
  const deferredMarkup = deferredRooms.map((group) => `
    <section class="rp-configuration-pending-room is-deferred">
      <header><div><strong>${escapeHtml(group.roomLabel)} · 已暫緩</strong>
        <small>你已同意擇優配置，下列家具本次不放入。</small></div></header>
      <ul>${group.items.map((item) =>
        `<li>${escapeHtml(item.label || item.name_zh || item.normalized_type)}</li>`
      ).join("")}</ul>
    </section>
  `).join("");
  element.configurationPendingList.innerHTML = blockingMarkup
    || deferredMarkup
    || "<p class=\"rp-configuration-clear\">目前沒有待處理家具。</p>";
  if (blockingMarkup && deferredMarkup) {
    element.configurationPendingList.insertAdjacentHTML("beforeend", deferredMarkup);
  }

  const confirmButton = $("#confirm-white-model");
  if (confirmButton) {
    confirmButton.disabled = blocking.length > 0;
    confirmButton.title = blocking.length
      ? `尚有 ${blocking.length} 件家具位置不合法，請先修正。`
      : "";
  }
}

async function reflowSingleConfigurationFurniture(furnitureId) {
  const furnitureKey = String(furnitureId);
  if (configurationReflowInFlight.has(furnitureKey) || configurationReflowInFlight.size > 0) {
    return;
  }
  const item = state.furniture2d.find(
    (candidate) => String(candidate.id) === furnitureKey,
  );
  if (!item) return;
  const room = configurationRoomById(item.roomId);
  if (!room) {
    setStatus(
      `${item.label} 目前未指定空間；請先回第 5 步指定房間，或按「同意擇優配置」先略過。`,
      "error",
    );
    return;
  }
  configurationReflowInFlight.add(furnitureKey);
  renderConfigurationPlan();
  setStatus(`正在只重新配置「${item.label}」…`);
  try {
    const resolved = await resolveFurniturePosition(item);
    if (!resolved || resolved.placement_failed) {
      item.placementFailed = true;
      item.placementReason = resolved?.placement_reason || "目前房間沒有合法位置。";
      renderConfigurationPlan();
      setStatus(`無法重新配置「${item.label}」：${item.placementReason}`, "error");
      return;
    }
    let sceneIndex = sceneObjectIndexByFurnitureId(item.id);
    if (sceneIndex < 0) {
      state.sceneData.scene_objects.push(resolved);
      sceneIndex = state.sceneData.scene_objects.length - 1;
    }
    const sceneObject = state.sceneData.scene_objects[sceneIndex];
    Object.assign(sceneObject, resolved, {
      position_locked: true,
      placement_failed: false,
      placement_reason: "",
    });
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      sceneObject,
    );
    state.selectedFurniture2dId = item.id;
    state.selectedSceneIndex = sceneIndex;
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    renderLayoutFurniture();
    renderSceneObjectList();
    whiteViewer.selectObjectByIndex(sceneIndex);
    scheduleSave("white_model_3d");
    setStatus(`已只重新配置「${item.label}」，其他合法家具位置保持不變。`);
  } catch (error) {
    setStatus(errorMessage(error), "error");
  } finally {
    configurationReflowInFlight.delete(furnitureKey);
    renderConfigurationPlan();
  }
}

function configurationFurniturePriority(item) {
  const essentialTypes = new Set([
    "bed",
    "sofa",
    "dining-table",
    "bathroom-vanity",
  ]);
  return [
    item.userRequired === true ? 0 : 1,
    essentialTypes.has(item.type) ? 0 : 1,
    Number(item.selectionPriority) || 999,
    item.autoAdded === true ? 1 : 0,
    Math.max(Number(item.widthCm) || 0, 1) * Math.max(Number(item.depthCm) || 0, 1),
  ];
}

function compareConfigurationFurniturePriority(left, right) {
  const leftPriority = configurationFurniturePriority(left);
  const rightPriority = configurationFurniturePriority(right);
  for (let index = 0; index < leftPriority.length; index += 1) {
    if (leftPriority[index] !== rightPriority[index]) {
      return leftPriority[index] - rightPriority[index];
    }
  }
  return String(left.id).localeCompare(String(right.id));
}

async function prioritizeUnassignedConfigurationFurniture() {
  if (!state.sceneData) return;
  const originalItems = configurationFurnitureForRoom(
    UNASSIGNED_CONFIGURATION_ROOM_ID,
    configurationBlockingFurniture(),
  ).sort(compareConfigurationFurniturePriority);
  if (!originalItems.length) return;
  const itemIds = new Set(originalItems.map((item) => String(item.id)));
  state.furniture2d = state.furniture2d.filter(
    (item) => !itemIds.has(String(item.id)),
  );
  state.sceneData.scene_objects = (state.sceneData.scene_objects || []).filter(
    (item) => !itemIds.has(String(item.furniture_id)),
  );
  // The A/B chooser later recomposes the active scene from both scheme sources.
  // Remove deferred furniture there as well so completed choices cannot resurrect it.
  Object.values(state.designSchemes.schemes).forEach((scheme) => {
    scheme.furniture = (scheme.furniture || []).filter(
      (item) => !itemIds.has(String(item.id)),
    );
    if (scheme.sceneData?.scene_objects) {
      scheme.sceneData.scene_objects = (scheme.sceneData.scene_objects || []).filter(
        (item) => !itemIds.has(String(item.furniture_id)),
      );
    }
  });
  state.selectedFurniture2dId = itemIds.has(String(state.selectedFurniture2dId))
    ? null
    : state.selectedFurniture2dId;
  state.selectedSceneIndex = null;
  const existingDeferred = unassignedDeferredFurniture().filter(
    (item) => !itemIds.has(String(item.id || item.furniture_id)),
  );
  state.roomRequirementModel.unassignedDeferredFurniture = [
    ...existingDeferred,
    ...originalItems.map((item) =>
      deferredFurnitureRecord(
        item,
        item.placementReason || "未指定空間，已同意先略過避免阻擋方案確認。",
      )
    ),
  ];
  const scheme = activeScheme();
  scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
  scheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
  await whiteViewer.loadScene(state.sceneData);
  renderLayoutFurniture();
  renderSceneObjectList();
  renderConfigurationPlan();
  scheduleSave("white_model_3d");
  setStatus(
    `未指定空間已先略過 ${originalItems.length} 件無法配置家具，方案可以繼續確認。`,
  );
}

async function prioritizeConfigurationRoomFurniture(roomId) {
  const room = configurationRoomById(roomId);
  if (!state.sceneData) return;
  if (!room && String(roomId) === UNASSIGNED_CONFIGURATION_ROOM_ID) {
    await prioritizeUnassignedConfigurationFurniture();
    return;
  }
  if (!room) return;
  const originalItems = state.furniture2d
    .filter((item) => configurationFurnitureBelongsToRoom(item, roomId))
    .sort(compareConfigurationFurniturePriority);
  if (!originalItems.length) return;
  const modelFailureIds = new Set(configurationModelFailures().keys());
  const retained = originalItems.filter(
    (item) => !modelFailureIds.has(String(item.id)),
  );
  const deferred = originalItems.filter(
    (item) => modelFailureIds.has(String(item.id)),
  );
  let placedObjects = [];
  setStatus(`正在為「${room.label}」擇優配置，會保留優先家具並記錄未放入項目…`);
  try {
    while (retained.length) {
      const layout = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          placement_room_id: room.id,
          placement_variant: activeSchemeId(),
          scene_objects: retained.map((item) =>
            toSceneFurniture(item, { positionLocked: false })
          ),
        }),
      });
      placedObjects = layout.scene_objects || [];
      const failedIds = new Set(
        placedObjects
          .filter((item) => item.placement_failed)
          .map((item) => String(item.furniture_id)),
      );
      if (!failedIds.size) break;
      const removableIndex = [...retained]
        .map((item, index) => ({ item, index }))
        .filter(({ item }) => failedIds.has(String(item.id)))
        .at(-1)?.index ?? retained.length - 1;
      deferred.unshift(retained.splice(removableIndex, 1)[0]);
    }
    const placedById = new Map(
      placedObjects
        .filter((item) => !item.placement_failed)
        .map((item) => [String(item.furniture_id), item]),
    );
    const retainedItems = retained.flatMap((item) => {
      const placed = placedById.get(String(item.id));
      if (!placed) return [];
      return [{
        ...item,
        xCm: Number(placed.position_cm?.x || 0),
        yCm: Number(placed.position_cm?.z || 0),
        rotationDeg: Number(placed.rotation_y_deg || 0),
        placementFailed: false,
        placementReason: "",
      }];
    });
    const roomFurnitureIds = new Set(originalItems.map((item) => String(item.id)));
    state.furniture2d = [
      ...state.furniture2d.filter((item) => !roomFurnitureIds.has(String(item.id))),
      ...retainedItems,
    ];
    const originalSceneById = new Map(
      (state.sceneData.scene_objects || []).map((item) => [String(item.furniture_id), item]),
    );
    state.sceneData.scene_objects = [
      ...(state.sceneData.scene_objects || []).filter(
        (item) => !roomFurnitureIds.has(String(item.furniture_id)),
      ),
      ...retainedItems.map((item) => ({
        ...(originalSceneById.get(String(item.id)) || toSceneFurniture(item)),
        ...(placedById.get(String(item.id)) || {}),
        placement_failed: false,
        placement_reason: "",
      })),
    ];
    const furniture = roomFurnitureRequirement(room.id);
    furniture.deferred = deferred.map((item) => ({
      id: item.id,
      furniture_id: item.catalogFurnitureId || item.id,
      normalized_type: item.type,
      label: item.label,
      reason: modelFailureIds.has(String(item.id))
        ? "資料庫模型無法載入，使用者同意本次暫不放入"
        : "使用者同意依空間尺寸擇優配置，本次暫不放入",
    }));
    const scheme = activeScheme();
    scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
    scheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
    await whiteViewer.loadScene(state.sceneData);
    renderLayoutFurniture();
    renderSceneObjectList();
    renderConfigurationPlan();
    scheduleSave("white_model_3d");
    setStatus(
      `「${room.label}」已保留 ${retainedItems.length} 件，暫緩 ${deferred.length} 件；未放入項目已留在右側紀錄。`,
    );
  } catch (error) {
    setStatus(errorMessage(error), "error");
  }
}

function renderSelectedFurnitureEditor() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
  if (!item) {
    element.selectedFurnitureEditor.hidden = true;
    return;
  }
  element.selectedFurnitureEditor.hidden = false;
  element.selectedFurnitureName.textContent = item.label;
  element.selectedFurnitureReason.textContent = `配置原因：${item.reason || "使用者手動加入，可調整實際尺寸。"}`;
  element.selectedFurnitureWidth.value = item.widthCm;
  element.selectedFurnitureDepth.value = item.depthCm;
}

let furnitureDrag = null;
function layoutPointerDown(event) {
  const target = event.target.closest("[data-furniture-2d-id]");
  if (!target) return;
  const furnitureId = target.getAttribute("data-furniture-2d-id");
  const item = state.furniture2d.find((candidate) => candidate.id === furnitureId);
  if (!item) return;
  state.selectedFurniture2dId = item.id;
  furnitureDrag = {
    item,
    startX: event.clientX,
    startY: event.clientY,
    originalX: item.xCm,
    originalY: item.yCm,
  };
  target.setPointerCapture?.(event.pointerId);
  renderLayoutFurniture();
  syncSelected2dFurnitureToScene({ focus: false });
}

function layoutPointerMove(event) {
  if (!furnitureDrag) return;
  const scale = layoutPixelsPerCm();
  furnitureDrag.item.xCm = furnitureDrag.originalX + (event.clientX - furnitureDrag.startX) / scale;
  furnitureDrag.item.yCm = furnitureDrag.originalY - (event.clientY - furnitureDrag.startY) / scale;
  renderLayoutFurniture();
}

async function validateFurniturePosition(item) {
  const others = state.furniture2d
    .filter((candidate) => candidate.id !== item.id)
    .map((candidate) => toSceneFurniture(candidate));
  return api("/api/scene/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan_editor: confirmedFloorplanEditor(),
      item: toSceneFurniture(item),
      others,
    }),
  });
}

async function resolveFurniturePosition(item) {
  const otherObjects = state.furniture2d
    .filter((candidate) => candidate.id !== item.id)
    .map((candidate) => ({
      ...toSceneFurniture(candidate),
      position_locked: true,
    }));
  const layout = await api("/api/scene/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan_editor: confirmedFloorplanEditor(),
      placement_room_id: item.roomId,
      placement_variant: activeSchemeId(),
      scene_objects: [
        ...otherObjects,
        {
          ...toSceneFurniture(item, { positionLocked: false }),
          furniture_id: item.id,
          catalog_furniture_id: item.catalogFurnitureId || null,
          position_locked: false,
          placement_hint_cm: { x: item.xCm, z: item.yCm },
        },
      ],
    }),
  });
  return (layout.scene_objects || []).find(
    (candidate) => candidate.furniture_id === item.id,
  );
}

async function finishFurnitureDrag(drag) {
  if (!drag) return;
  try {
    const resolved = await resolveFurniturePosition(drag.item);
    if (!resolved || resolved.placement_failed) {
      drag.item.xCm = drag.originalX;
      drag.item.yCm = drag.originalY;
      drag.item.placementFailed = true;
      drag.item.placementReason = resolved?.placement_reason || "位置未通過家具引擎檢查";
      element.layoutError.textContent = `${drag.item.label}：${drag.item.placementReason}`;
    } else {
      drag.item.xCm = Number(resolved.position_cm?.x || 0);
      drag.item.yCm = Number(resolved.position_cm?.z || 0);
      drag.item.rotationDeg = Number(resolved.rotation_y_deg || 0);
      drag.item.placementFailed = false;
      drag.item.placementReason = "";
      element.layoutError.textContent = "";
      const room = state.rooms.find((candidate) => candidate.id === drag.item.roomId);
      setStatus(`已在「${room?.label || "目前房間"}」內貼齊最近有效牆面。`);
    }
  } catch (error) {
    drag.item.xCm = drag.originalX;
    drag.item.yCm = drag.originalY;
    element.layoutError.textContent = errorMessage(error);
  }
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具位置已修改，3D 家具配置與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
}

function replacementCandidateFitsRoom(candidate, room) {
  const dimensions = roomDimensions(room);
  const width = Number(candidate.size_cm?.width || 0);
  const depth = Number(candidate.size_cm?.depth || 0);
  if (!width || !depth) return false;
  const clearance = 20;
  return (
    width + clearance <= dimensions.widthCm
    && depth + clearance <= dimensions.depthCm
  ) || (
    depth + clearance <= dimensions.widthCm
    && width + clearance <= dimensions.depthCm
  );
}

function replacementFurnitureName(item = {}) {
  const type = item.normalized_type || item.type || "";
  const rawName = [item.name_zh, item.name_zh_raw, item.label]
    .filter(Boolean)
    .join(" ");
  const chineseNames = rawName.match(/[\u3400-\u9fff]{2,}/g) || [];
  const nameWithFurnitureNoun = chineseNames.find((name) =>
    /(床|櫃|桌|椅|凳|沙發|架|鏡|燈|毯|盆|櫥|箱|籃)/.test(name));
  return nameWithFurnitureNoun
    || questionnaireFurnitureDisplayLabel({ ...item, normalized_type: type })
    || REPLACEMENT_TYPE_LABELS[type]
    || "家具";
}

function replacementFurnitureSize(item = {}) {
  const width = Number(item.widthCm || item.size_cm?.width || 0).toFixed(0);
  const depth = Number(item.depthCm || item.size_cm?.depth || 0).toFixed(0);
  return `${width} × ${depth} cm`;
}

function replacementCandidateImageUrl(candidate = {}) {
  const cloudImages = candidate.cloud_image_urls || {};
  return candidate.image_url
    || candidate.thumbnail_url
    || candidate.preview_url
    || candidate.main_image_url
    || candidate.primary_image_url
    || candidate.image
    || candidate.imageUrl
    || cloudImages.front
    || cloudImages.angle
    || Object.values(cloudImages).find(Boolean)
    || "";
}

function replacementRoomBounds(room) {
  if (!room?.polygon_cm?.length) return null;
  const center = planCenterCm();
  const xs = room.polygon_cm.map((point) => Number(point.x || 0) - center.x);
  const zs = room.polygon_cm.map((point) => Number(point.y || 0) - center.y);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minZ: Math.min(...zs),
    maxZ: Math.max(...zs),
    centerX: (Math.min(...xs) + Math.max(...xs)) / 2,
    centerZ: (Math.min(...zs) + Math.max(...zs)) / 2,
  };
}

function segmentEndpoint(point = {}) {
  return scenePointCoordinates(point);
}

function segmentOverlapsBounds(segment, bounds, padding = 32) {
  if (!segment || !bounds) return false;
  const start = segmentEndpoint(segment.start || segment[0]);
  const end = segmentEndpoint(segment.end || segment[1]);
  const minX = Math.min(start.x, end.x);
  const maxX = Math.max(start.x, end.x);
  const minZ = Math.min(start.z, end.z);
  const maxZ = Math.max(start.z, end.z);
  return (
    maxX >= bounds.minX - padding
    && minX <= bounds.maxX + padding
    && maxZ >= bounds.minZ - padding
    && minZ <= bounds.maxZ + padding
  );
}

function shiftScenePoint(point = {}, offset) {
  if (!offset) return { ...point };
  if (Array.isArray(point)) {
    return [
      Number(point[0] || 0) - offset.x,
      Number(point[1] || 0) - offset.z,
    ];
  }
  const next = { ...point };
  if ("x" in next) next.x = Number(next.x || 0) - offset.x;
  if ("z" in next) next.z = Number(next.z || 0) - offset.z;
  if ("y" in next && !("z" in next)) next.y = Number(next.y || 0) - offset.z;
  return next;
}

function shiftSceneSegment(segment, offset) {
  if (!segment) return segment;
  if (Array.isArray(segment)) {
    return segment.map((point) => shiftScenePoint(point, offset));
  }
  return {
    ...segment,
    start: shiftScenePoint(segment.start, offset),
    end: shiftScenePoint(segment.end, offset),
  };
}

function shiftRoomSurfaceAssignment(assignment, offset) {
  if (!assignment || !offset) return assignment;
  const next = { ...assignment };
  if (next.room_bounds_cm) {
    next.room_bounds_cm = {
      ...next.room_bounds_cm,
      minX: Number(next.room_bounds_cm.minX || 0) - offset.x,
      maxX: Number(next.room_bounds_cm.maxX || 0) - offset.x,
      minZ: Number(next.room_bounds_cm.minZ || 0) - offset.z,
      maxZ: Number(next.room_bounds_cm.maxZ || 0) - offset.z,
    };
  }
  if (Array.isArray(next.room_polygon_cm)) {
    next.room_polygon_cm = next.room_polygon_cm.map((point) => shiftScenePoint(point, offset));
  }
  return next;
}

function scenePointCoordinates(point = {}) {
  if (Array.isArray(point)) {
    return {
      x: Number(point[0] || 0),
      z: Number(point[1] || 0),
    };
  }
  return {
    x: Number(point.x || 0),
    z: Number(point.z ?? point.y ?? 0),
  };
}

function shiftFloorplanRegion(region, offset) {
  if (!region || !offset) return region;
  const next = { ...region };
  ["exterior", "polygon_cm", "polygon_m", "room_polygon_cm"].forEach((key) => {
    if (Array.isArray(next[key])) next[key] = next[key].map((point) => shiftScenePoint(point, offset));
  });
  if (Array.isArray(next.holes)) {
    next.holes = next.holes.map((ring) => (
      Array.isArray(ring) ? ring.map((point) => shiftScenePoint(point, offset)) : ring
    ));
  }
  return next;
}

function sceneObjectMatchesLayoutFurniture(sceneObject = {}, layoutItem = {}) {
  const sceneIds = [
    sceneObject.furniture_id,
    sceneObject.catalog_furniture_id,
    sceneObject.catalogFurnitureId,
    sceneObject.layout_furniture_id,
    sceneObject.source_furniture_id,
    sceneObject.id,
  ].filter(Boolean).map(String);
  const layoutIds = [
    layoutItem.id,
    layoutItem.catalogFurnitureId,
    layoutItem.furniture_id,
  ].filter(Boolean).map(String);
  return sceneIds.some((id) => layoutIds.includes(id));
}

function replacementRoomIdForSceneObject(sceneObject = {}) {
  const explicitRoomId = sceneObject.placement_room_id || sceneObject.room_id;
  if (explicitRoomId) return String(explicitRoomId);
  const layoutItem = state.furniture2d.find(
    (item) => sceneObjectMatchesLayoutFurniture(sceneObject, item),
  );
  return layoutItem?.roomId ? String(layoutItem.roomId) : "";
}

function buildReplacementRoomPreviewScene(baseScene, current, candidate) {
  if (!baseScene?.floorplan || !current) return null;
  const room = state.rooms.find(
    (candidateRoom) => String(candidateRoom.id) === String(current.roomId),
  );
  const bounds = replacementRoomBounds(room);
  if (!room || !bounds) return null;
  const offset = { x: bounds.centerX, z: bounds.centerZ };
  const scene = JSON.parse(JSON.stringify(baseScene));
  const floorplan = scene.floorplan || {};
  ["wall_segments", "door_segments", "window_segments", "beam_segments", "column_segments"].forEach((key) => {
    if (!Array.isArray(floorplan[key])) return;
    floorplan[key] = floorplan[key]
      .filter((segment) => segmentOverlapsBounds(segment, bounds))
      .map((segment) => shiftSceneSegment(segment, offset));
  });
  if (Array.isArray(floorplan.room_regions)) {
    floorplan.room_regions = floorplan.room_regions.filter(
      (region) => String(region.room_id || region.id || "") === String(room.id),
    );
  }
  floorplan.width_cm = Math.max(240, (bounds.maxX - bounds.minX) + 120);
  floorplan.depth_cm = Math.max(240, (bounds.maxZ - bounds.minZ) + 120);
  scene.floorplan = floorplan;
  scene.room_surface_assignments = (scene.room_surface_assignments || [])
    .filter((assignment) => String(assignment.room_id || "") === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  scene.scene_objects = (scene.scene_objects || [])
    .filter((item) => {
      const sameFurniture = sceneObjectMatchesLayoutFurniture(item, current);
      const sameRoom = replacementRoomIdForSceneObject(item) === String(room.id);
      return sameFurniture || sameRoom;
    })
    .map((item) => ({
      ...item,
      position_cm: shiftScenePoint(item.position_cm, offset),
    }));
  const currentIndex = scene.scene_objects.findIndex(
    (item) => sceneObjectMatchesLayoutFurniture(item, current),
  );
  const existing = currentIndex >= 0
    ? scene.scene_objects[currentIndex]
    : {
      position_cm: shiftScenePoint({ x: current.xCm, z: current.yCm }, offset),
      rotation_y_deg: current.rotationDeg,
      placement_room_id: current.roomId,
    };
  const previewFurnitureId = `replacement-preview-${candidate.furniture_id}`;
  const replacement = {
    ...existing,
    ...candidate,
    furniture_id: previewFurnitureId,
    position_cm: existing.position_cm,
    rotation_y_deg: existing.rotation_y_deg,
    placement_room_id: existing.placement_room_id || current.roomId,
    position_locked: true,
    placement_failed: false,
  };
  if (currentIndex >= 0) scene.scene_objects[currentIndex] = replacement;
  else scene.scene_objects.push(replacement);
  return {
    scene,
    previewIndex: currentIndex >= 0 ? currentIndex : scene.scene_objects.length - 1,
  };
}

async function previewReplacementCandidate(candidate) {
  if (!candidate?.model_url) {
    element.replacement3dStatus.textContent = "這件家具沒有可載入的 3D 模型。";
    return;
  }
  const current = state.furniture2d.find(
    (item) => item.id === state.selectedFurniture2dId,
  );
  const baseScene = state.sceneData || activeScheme()?.sceneData;
  const previewFurnitureId = `replacement-preview-${candidate.furniture_id}`;
  let previewIndex = 0;
  let previewScene;
  const roomPreview = buildReplacementRoomPreviewScene(baseScene, current, candidate);
  if (roomPreview) {
    previewScene = roomPreview.scene;
    previewIndex = roomPreview.previewIndex;
  } else {
    previewScene = {
      floorplan: {
        width_cm: 360,
        depth_cm: 360,
        room_height_cm: 270,
        wall_segments: [],
        door_segments: [],
        window_segments: [],
      },
      scene_objects: [{
        ...candidate,
        furniture_id: previewFurnitureId,
        position_cm: { x: 0, z: 0 },
        rotation_y_deg: 0,
        position_locked: true,
        placement_failed: false,
      }],
      style: { style_id: state.activeStyleId || "white_model" },
    };
  }
  await replacementViewer.loadScene(previewScene);
  replacementViewer.selectObjectByIndex(previewIndex, { focus: true });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  replacementViewer.setViewMode("dollhouse");
  replacementViewer.selectObjectByIndex(previewIndex, { focus: false });
}

function renderReplacementCandidates(candidates, emptyMessage = "目前沒有可替換的家具。") {
  element.replacementResults.dataset.items = JSON.stringify(candidates);
  element.replacementResults.innerHTML = candidates.map((candidate) => {
    const title = replacementFurnitureName(candidate);
    return `
      <article>
        <button type="button" class="rp-replacement-candidate" data-preview-replacement="${escapeHtml(candidate.furniture_id)}">
          <span><strong>${escapeHtml(title)}</strong><small>${replacementFurnitureSize(candidate)}</small></span>
        </button>
        <button type="button" class="primary-action" data-confirm-replacement="${escapeHtml(candidate.furniture_id)}">以此家具取代</button>
      </article>
    `;
  }).join("") || `<p>${escapeHtml(emptyMessage)}</p>`;
  if (candidates[0]) previewReplacementCandidate(candidates[0]);
}

function replacementCandidateIsSmaller(candidate, current) {
  const candidateSides = [
    Number(candidate.size_cm?.width || 0),
    Number(candidate.size_cm?.depth || 0),
  ].sort((left, right) => left - right);
  const currentSides = [
    Number(current.widthCm || 0),
    Number(current.depthCm || 0),
  ].sort((left, right) => left - right);
  if (!candidateSides.every(Boolean) || !currentSides.every(Boolean)) return false;
  const candidateArea = candidateSides[0] * candidateSides[1];
  const currentArea = currentSides[0] * currentSides[1];
  return candidateSides[0] <= currentSides[0]
    && candidateSides[1] <= currentSides[1]
    && candidateArea <= currentArea * 0.9;
}

function setSmallerReplacementOption(smallerCandidates) {
  const smallerOption = element.replacementSearch.querySelector('option[value="smaller"]');
  if (smallerCandidates.length) {
    if (!smallerOption) {
      const option = document.createElement("option");
      option.value = "smaller";
      option.textContent = "建議：更換更小款";
      element.replacementSearch.insertBefore(option, element.replacementSearch.options[1] || null);
    }
    return;
  }
  if (element.replacementSearch.value === "smaller") {
    element.replacementSearch.value = "same-type";
  }
  smallerOption?.remove();
}

async function loadReplacementCandidates() {
  const current = state.furniture2d.find(
    (candidate) => candidate.id === state.selectedFurniture2dId,
  );
  const room = state.rooms.find((candidate) => candidate.id === current?.roomId);
  if (!current || !room) return;
  element.replacementError.textContent = "";
  element.replacementResults.innerHTML = "<p>正在搜尋可放入目前房間的家具...</p>";
  const filterMode = element.replacementSearch.value || "same-type";
  const catalogType = filterMode.startsWith("type:") ? filterMode.slice(5) : "";
  const query = element.replacementQuery?.value?.trim() || "";
  const paletteId = state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.paletteId;
  const style = STYLE_PACKS.find((pack) => pack.id === paletteId)?.styleId
    || state.activeStyleId
    || "";
  const request = {
    ...questionnaireFurnitureRequest(room, [current.type, current.variantId]),
    widthCm: current.widthCm,
    depthCm: current.depthCm,
  };
  const catalogCandidates = await catalogCandidatesForType(current.type, {
    styleId: filterMode === "all" ? "" : style,
    query,
    catalogType,
    searchAll: filterMode === "same-style" || filterMode === "all",
  });
  const allCandidates = rankCatalogFurniture(catalogCandidates, request)
    .filter(
      (candidate) => !knownUnavailableCatalogFurnitureIds().has(
        String(candidate.furniture_id),
      ),
    )
    .filter((candidate) => candidate.furniture_id !== current.catalogFurnitureId)
    .filter((candidate) => replacementCandidateFitsRoom(candidate, room));
  const smallerCandidates = allCandidates.filter((candidate) =>
    replacementCandidateIsSmaller(candidate, current),
  );
  setSmallerReplacementOption(smallerCandidates);
  const effectiveFilterMode = element.replacementSearch.value || "same-type";
  const candidates = (effectiveFilterMode === "smaller" ? smallerCandidates : allCandidates).slice(0, 24);
  element.replacementFilterSummary.textContent =
    `${replacementFurnitureName(current)} · ${replacementFurnitureSize(current)}`;
  renderReplacementCandidates(
    candidates,
    effectiveFilterMode === "smaller"
      ? "目前沒有比這件家具更小，且可放入本房的同類 3D 家具。"
      : "目前沒有同類型、同風格且尺寸放得下的 3D 家具。",
  );
}

function renderReplacementTypeOptions(current) {
  const route = CATALOG_RETRIEVAL_ROUTES[current.type]
    || { type: current.type };
  const routeTypes = route.types || [route.type];
  const options = routeTypes.filter(Boolean);
  element.replacementSearch.innerHTML = [
    '<option value="same-type">建議：同類家具</option>',
    '<option value="same-style">依目前風格推薦</option>',
    '<option value="all">瀏覽全部家具資料庫</option>',
    ...(options.length > 1
      ? ['<option value="">瀏覽全部相容類型</option>']
      : []),
    options.length ? '<optgroup label="家具類別">' : '',
    ...options.map((type) => `<option value="type:${escapeHtml(type)}">${escapeHtml(REPLACEMENT_TYPE_LABELS[type] || current.label || type)}</option>`),
    options.length ? '</optgroup>' : '',
  ].join("");
  element.replacementSearch.value = "same-type";
  if (element.replacementQuery) element.replacementQuery.value = "";
}

function setReplacementDrawerOpen(open) {
  if (open) {
    if (typeof element.replacementDrawer.showModal === "function") {
      element.replacementDrawer.showModal();
    } else {
      element.replacementDrawer.setAttribute("open", "");
    }
    return;
  }
  if (typeof element.replacementDrawer.close === "function") {
    element.replacementDrawer.close();
  } else {
    element.replacementDrawer.removeAttribute("open");
  }
}

async function openFurnitureReplacement({ mode = "same-type" } = {}) {
  if (!state.selectedFurniture2dId) {
    element.layoutError.textContent = "請先選取一件要更換的家具。";
    return;
  }
  const current = state.furniture2d.find(
    (candidate) => candidate.id === state.selectedFurniture2dId,
  );
  if (!current) {
    element.layoutError.textContent = "找不到目前選取的家具，請重新選取後再更換。";
    return;
  }
  renderReplacementTypeOptions(current);
  element.replacementSearch.value = mode;
  setReplacementDrawerOpen(true);
  try {
    await loadReplacementCandidates();
  } catch (error) {
    element.replacementError.textContent = errorMessage(error);
  }
}

async function replaceSelectedLayoutFurniture(furnitureId) {
  const candidates = JSON.parse(element.replacementResults.dataset.items || "[]");
  const catalogItem = candidates.find((candidate) => candidate.furniture_id === furnitureId);
  const current = state.furniture2d.find(
    (candidate) => candidate.id === state.selectedFurniture2dId,
  );
  if (!catalogItem || !current) return;
  const size = catalogItem.size_cm || {};
  const candidate = {
    ...current,
    type: catalogItem.normalized_type || current.type,
    label: catalogItem.name_zh || catalogItem.name_zh_raw || catalogItem.name_en || current.label,
    widthCm: Number(size.width) || current.widthCm,
    depthCm: Number(size.depth) || current.depthCm,
    heightCm: Number(size.height) || current.heightCm,
    catalogFurnitureId: catalogItem.furniture_id,
    model_url: catalogItem.model_url,
    reason: `使用者從家具資料庫更換，並依「${state.rooms.find((room) => room.id === current.roomId)?.label || "目前房間"}」重新檢查位置。`,
  };
  element.replacementError.textContent = "正在由家具引擎檢查新尺寸、牆界、碰撞與淨空...";
  const resolved = await resolveFurniturePosition(candidate);
  if (!resolved || resolved.placement_failed) {
    element.replacementError.textContent =
      `無法更換：${resolved?.placement_reason || "目前房間沒有合法位置"}。`;
    return;
  }
  candidate.xCm = Number(resolved.position_cm?.x || 0);
  candidate.yCm = Number(resolved.position_cm?.z || 0);
  candidate.rotationDeg = Number(resolved.rotation_y_deg || 0);
  candidate.placementFailed = false;
  candidate.placementReason = "";
  const index = state.furniture2d.findIndex((item) => item.id === current.id);
  state.furniture2d[index] = candidate;
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "家具款式已更換，3D 家具配置與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
  setReplacementDrawerOpen(false);
  setStatus(`已用「${candidate.label}」取代原家具，並通過家具引擎檢查。`);
}

function addFurnitureFromLibrary(type, variant) {
  const currentIndex = state.furniture2d.findIndex(
    (item) => item.id === state.selectedFurniture2dId,
  );
  if (currentIndex >= 0) {
    state.furniture2d[currentIndex] = replaceFurniture2DItem(
      state.furniture2d[currentIndex],
      type,
      variant,
    );
    syncFurnitureInventoryAcrossSchemes();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具形式已修改，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
    setStatus("已保留原位置並更換家具形式；請確認新尺寸與淨空。");
    return;
  }
  const room = state.rooms.find((item) => item.id === state.activeLayoutRoomId)
    || state.rooms.find((item) => item.id === state.selectedRoomId)
    || state.rooms[0];
  const center = roomCenter(room);
  const planCenter = planCenterCm();
  const item = createFurniture2DItem(type, variant, {
    xCm: center.x - planCenter.x,
    yCm: center.y - planCenter.y,
  });
  item.roomId = room.id;
  item.reason = "使用者從 2D 圖示資料庫加入。";
  state.furniture2d.push(item);
  syncFurnitureInventoryAcrossSchemes();
  state.selectedFurniture2dId = item.id;
  state.activeLayoutRoomId = room.id;
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具已新增，3D 家具配置與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
}

function updateSelectedFurnitureDimensions() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
  if (!item) return;
  item.widthCm = Math.max(1, Number(element.selectedFurnitureWidth.value) || item.widthCm);
  item.depthCm = Math.max(1, Number(element.selectedFurnitureDepth.value) || item.depthCm);
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具尺寸已修改，3D 家具配置與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
}

async function resolveCatalogFurniture(item) {
  if (item.model_url && item.catalogFurnitureId) {
    return toSceneFurniture(item);
  }
  try {
    const room = state.rooms.find((candidate) => candidate.id === item.roomId);
    const request = questionnaireFurnitureRequest(
      room || { id: item.roomId },
      [item.type, item.variantId],
    );
    const params = new URLSearchParams({
      type: item.type,
      has_model: "true",
      detail: "scene",
      page_size: "80",
    });
    if (request.styleId) params.set("style", request.styleId);
    let payload = await api(`/api/furniture?${params.toString()}`);
    if (!(payload.items || []).length && request.styleId) {
      params.delete("style");
      payload = await api(`/api/furniture?${params.toString()}`);
    }
    const candidates = rankCatalogFurniture(payload.items || [], request);
    if (!candidates.length) return toSceneFurniture(item);
    return mergeCatalogFurniture(item, candidates[0]);
  } catch (error) {
    console.warn(error);
    return toSceneFurniture(item);
  }
}

function placementResolutionText(report = []) {
  if (!report.length) return "";
  return report
    .map((item) => item.message_zh || `${item.action || "adjust"}：${item.from || item.furniture_id || item.type || ""}`)
    .filter(Boolean)
    .join("；");
}

async function confirmLayout2d({ allowPendingFurniture = false } = {}) {
  element.layoutError.textContent = "";
  let generationStage = "檢查家具位置";
  if (
    activeSchemeId() === "B"
    && activeScheme()?.stale
    && state.designSchemes.schemes.A.furniture.length
    && !state.furniture2d.length
  ) {
    element.layoutError.textContent =
      activeScheme().staleReason || "方案 B 尚未產生合法家具配置。";
    return;
  }
  try {
    if (state.furniture2d.length) {
      const validation = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          scene_objects: state.furniture2d.map((item) => toSceneFurniture(item)),
        }),
      });
      const invalid = (validation.scene_objects || []).filter(
        (item) => item.placement_failed || !item.position_locked,
      );
      if (invalid.length && !allowPendingFurniture) {
        element.layoutError.textContent = `${invalid
          .map((item) => item.name_zh_raw || item.normalized_type)
          .join("、")}目前位置未通過碰撞、淨空或房間邊界檢查，請移動或更換尺寸。`;
        return;
      }
    }
    generationStage = "取得資料庫家具模型";
    setStatus(state.furniture2d.length
      ? "正在依問卷、色卡與尺寸載入資料庫 GLB 家具…"
      : "沒有家具需求，正在產生純結構 3D 配置…");
    const applianceRequirements = applianceRequirementsForRendering(state.furniture2d);
    const placeableFurniture = removeRetiredAppliancesFromFurniture(state.furniture2d);
    const selectedFurniture = await Promise.all(placeableFurniture.map(resolveCatalogFurniture));
    const missingCatalogModels = selectedFurniture.filter((item) => !item.model_url);
    if (missingCatalogModels.length && !allowPendingFurniture) {
      element.layoutError.textContent =
        `有 ${missingCatalogModels.length} 件家具尚未找到可用的資料庫 GLB：${
          missingCatalogModels
            .map((item) => item.name_zh_raw || item.normalized_type)
            .join("、")
        }。請更換家具或確認型錄模型後再進入配置預覽。`;
      setStatus("資料庫家具尚未完整，已停止產生替代模型。", "error");
      return;
    }
    if (missingCatalogModels.length) {
      const missingIds = new Set(missingCatalogModels.map((item) => String(item.id)));
      state.furniture2d = state.furniture2d.map((item) => (
        missingIds.has(String(item.id))
          ? {
            ...item,
            placementFailed: true,
            placementReason: "尚未找到可用的資料庫 GLB，請替換為可載入的家具。",
          }
          : item
      ));
    }
    const sceneFurniture = allowPendingFurniture
      ? selectedFurniture.filter((item) => item.model_url)
      : selectedFurniture;
    const firstRoom = state.rooms.find((room) => room.type === "living_room") || state.rooms[0];
    const dimensions = roomDimensions(firstRoom);
    const preferredPack = activeQuestionnairePack();
    const visualPreferences = resolvedVisualPreferences();
    const roomRequirementsPayload = buildRoomRequirementsPayload(
      state.roomRequirementModel,
      {
        planGeometry: {
          rooms: state.rooms,
          structures: state.structures,
        },
        questionnaireVersion: state.visualCatalogVersion,
      },
    );
    const roomSurfaces = roomSurfaceAssignments();
    generationStage = "產生 2D+3D 場景";
    const payload = await api("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_brief: {
          space: { type: firstRoom.type || "living_room" },
          style: {
            preferred: [preferredPack.styleId],
            colors: [
              state.questionnaireFinishes.wallColor,
              state.questionnaireFinishes.floorColor,
              state.questionnaireFinishes.ceilingColor,
            ].filter(Boolean),
            materials: [
              state.questionnaireFinishes.wallMaterial,
              state.questionnaireFinishes.floorMaterial,
              state.questionnaireFinishes.ceilingMaterial,
            ].filter(Boolean),
          },
          occupants: occupantsFromBasicAnswers(state.basicAnswers),
          constraints: ["keep_door_clear", "keep_window_clear"],
        },
        questionnaire: {
          catalog_version: state.visualCatalogVersion,
          basic: state.basicAnswers,
          visual_preferences: visualPreferences,
          finishes: state.questionnaireFinishes,
          room_requirements: roomRequirementsPayload.roomRequirements,
          rag_jobs: state.roomRagJobs,
          appliance_requirements: applianceRequirements,
        },
        room_surface_assignments: roomSurfaces,
        floorplan_filename: `${state.projectId}-confirmed.dxf`,
        floorplan_editor: confirmedFloorplanEditor(),
        room_width_cm: dimensions.widthCm,
        room_depth_cm: dimensions.depthCm,
        required_furniture: [...new Set(placeableFurniture.map((item) => item.type))],
        selected_furniture: sceneFurniture,
        selected_furniture_exact: !allowPendingFurniture,
      }),
    });
    state.sceneData = sceneDataFromGenerateResponse(payload);
    pruneRetiredAppliances({ notify: true });
    const generatedInvalid = (state.sceneData.scene_objects || []).filter(
      (item) => item.placement_failed || !item.position_cm,
    );
    if (generatedInvalid.length && !allowPendingFurniture) {
      element.layoutError.textContent =
        `系統仍有 ${generatedInvalid.length} 件家具無法合法放置，請先在上方待處理清單更換或調整家具。`;
      setStatus("配置尚未通過門窗淨空、房間邊界與家具碰撞檢查。", "error");
      renderLayoutRoomFilter();
      renderLayoutFurniture();
      return;
    }
    state.sceneData.questionnaire = {
      catalog_version: state.visualCatalogVersion,
      basic: state.basicAnswers,
      visual_preferences: visualPreferences,
      finishes: state.questionnaireFinishes,
      room_requirements: roomRequirementsPayload.roomRequirements,
      rag_jobs: state.roomRagJobs,
      appliance_requirements: applianceRequirements,
    };
    state.sceneData.room_requirements = roomRequirementsPayload.roomRequirements;
    state.sceneData.surface_overrides = roomSurfaces.map((surface) => ({
      ...surface,
      wall_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "wall",
        surface.wall_material_id,
      ),
      floor_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "floor",
        surface.floor_material_id,
      ),
    }));
    state.sceneData.style = {
      ...(state.sceneData.style || {}),
      style_id: "white_model",
      palette_hex: ["#f4f1ec", "#e9e6e1", "#d8d3cc", "#bcb4aa"],
    };
    state.sceneData.scene_objects.forEach((sceneObject) => {
      state.furniture2d = upsertFurniture2dFromSceneObject(
        state.furniture2d,
        sceneObject,
      );
    });
    const selectedSceneIndex = sceneObjectIndexByFurnitureId(state.selectedFurniture2dId);
    if (selectedSceneIndex >= 0) state.selectedSceneIndex = selectedSceneIndex;
    const generatedScheme = activeScheme();
    generatedScheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
    generatedScheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
    generatedScheme.stale = false;
    generatedScheme.staleReason = "";
    state.workflow.complete("layout_2d", {
      confirmed: true,
      furnitureCount: state.furniture2d.length,
    });
    state.workflow.goTo("white_model_3d");
    showStep("white_model_3d");
    generationStage = "載入 3D 預覽";
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    syncSelected2dFurnitureToScene({ focus: true });
    const diagnostics = whiteViewer.getDiagnostics();
    const expectedFurnitureCount = state.sceneData.scene_objects.filter(
      (item) => !item.placement_failed,
    ).length;
    const resolutionText = placementResolutionText(state.sceneData.placement_resolution_report || []);
    if (expectedFurnitureCount === 0) {
      element.whiteError.textContent = "";
      setStatus("純結構 3D 配置已產生；此方案沒有家具需求。");
    } else if (diagnostics.visibleFurnitureCount > 0) {
      element.whiteError.textContent = resolutionText;
      setStatus(`3D 家具配置已產生，${diagnostics.visibleFurnitureCount} 件資料庫家具可見。`);
    } else {
      element.whiteError.textContent = "3D 中沒有任何可見家具，不能進入下一步。";
    }
    scheduleSave("white_model_3d");
  } catch (error) {
    const message = `${generationStage}失敗：${errorMessage(error)}`;
    state.lastWhiteModelGenerationError = message;
    element.layoutError.textContent = message;
    console.error("2D+3D configuration failed", { generationStage, error });
    setStatus(message, "error");
  }
}

async function generateWhiteModelFromRequirements({ returnToRequirementsOnFailure = false } = {}) {
  if (state.autoGeneratingWhiteModel) {
    state.lastWhiteModelGenerationError = "配置仍在建立中，請勿重複送出。";
    return false;
  }
  state.autoGeneratingWhiteModel = true;
  state.lastWhiteModelGenerationError = "";
  element.layoutError.textContent = "";
  try {
    if (!state.workflow?.goTo("layout_2d")) {
      const message = firstWorkflowBlocker("layout_2d");
      state.lastWhiteModelGenerationError = message;
      if (returnToRequirementsOnFailure) element.requirementsError.textContent = message;
      setStatus(message, "error");
      return false;
    }
    setStatus("正在依照問卷、色卡與指定家具建立方案 A 的 3D 場景…");
    // 問卷候選家具的 GLB 可能仍在驗證，先進入第 6 步處理可用項目。
    // 尚未載入的候選會保留為待處理，不應阻擋整體 2D+3D 場景。
    await confirmLayout2d({ allowPendingFurniture: true });
    const generatedA = state.workflow.currentStep === "white_model_3d" && Boolean(state.sceneData);
    if (!generatedA) {
      const message = element.layoutError.textContent.trim()
        || "方案 A 無法建立 3D 場景，請檢查問卷需求或資料庫家具模型。";
      state.lastWhiteModelGenerationError = message;
      if (returnToRequirementsOnFailure) {
        state.workflow.goTo("requirements");
        showStep("requirements");
        element.requirementsError.textContent = message;
        scheduleSave("requirements");
      }
      return false;
    }

    if (state.designSchemes.schemes.B && !state.designSchemes.schemes.B.stale) {
      setStatus("正在載入方案 B 的資料庫家具與 3D 場景…");
      await switchDesignScheme("B");
      await confirmLayout2d({ allowPendingFurniture: true });
      const generatedB = state.workflow.currentStep === "white_model_3d" && Boolean(state.sceneData);
      if (!generatedB) {
        const message = element.layoutError.textContent.trim()
          || "方案 B 無法建立 3D 場景，請返回問卷調整需求。";
        state.designSchemes.schemes.B.stale = true;
        state.designSchemes.schemes.B.staleReason = message;
        await switchDesignScheme("A");
        setStatus("方案 A 已建立；方案 B 有待處理家具，請在第 6 步調整。", "warning");
      } else {
        await switchDesignScheme("A");
        setStatus("方案 A、B 的 2D+3D 配置已建立，可開始比較與調整。", "success");
      }
    } else if (state.designSchemes.schemes.B?.stale) {
      setStatus("方案 A 已建立；方案 B 有待處理家具，請在第 6 步調整。", "warning");
    }
    return true;
  } finally {
    state.autoGeneratingWhiteModel = false;
  }
}

async function addWhiteModelBeamFromWorld({ start, end }) {
  const lengthCm = Math.hypot(end.x - start.x, end.z - start.z);
  const status = $("#white-model-beam-status");
  if (lengthCm < 25) {
    status.textContent = "樑長至少需要 25 公分，請重新選取兩點。";
    status.classList.add("is-error");
    return;
  }
  const widthCm = Math.min(120, Math.max(10, Number($("#white-model-beam-width-cm").value) || 30));
  const dropCm = Math.min(120, Math.max(10, Number($("#white-model-beam-drop-cm").value) || 35));
  const floorplan = state.sceneData?.floorplan;
  if (!floorplan) return;
  const halfWidthCm = Number(floorplan.width_cm || 600) / 2;
  const halfDepthCm = Number(floorplan.depth_cm || 400) / 2;
  const id = `beam-manual-${Date.now()}`;
  const editorBeam = {
    id,
    start: { x: start.x + halfWidthCm, y: start.z + halfDepthCm },
    end: { x: end.x + halfWidthCm, y: end.z + halfDepthCm },
    thickness_cm: widthCm,
    height_cm: dropCm,
    top_cm: Number(floorplan.room_height_cm || 270),
    confirmed: false,
    estimated: true,
    source: "manual_3d",
  };
  state.structures.beams.push(editorBeam);
  floorplan.beam_segments ||= [];
  floorplan.beam_segments.push({
    ...editorBeam,
    start: { x: start.x, z: start.z },
    end: { x: end.x, z: end.z },
  });
  state.selectedStructure = { id, kind: "beam" };
  await whiteViewer.loadScene(state.sceneData);
  whiteViewer.setViewMode("orbit");
  $("#add-white-model-beam").hidden = false;
  $("#cancel-white-model-beam").hidden = true;
  status.classList.remove("is-error");
  status.textContent = `已新增樑 ${state.structures.beams.length}，長 ${Math.round(lengthCm)}、寬 ${widthCm}、下垂 ${dropCm} 公分。`;
  invalidateDownstreamFrom("space_confirmation", "3D 已新增樑，後續寫實結果需要重新確認。");
  scheduleSave("white_model_3d");
}

function beginWhiteModelBeamPlacement() {
  const started = whiteViewer.beginBeamPlacement(addWhiteModelBeamFromWorld);
  if (!started) return;
  $("#add-white-model-beam").hidden = true;
  $("#cancel-white-model-beam").hidden = false;
  $("#white-model-beam-status").textContent = "請在 3D 室內依序點選樑的起點與終點。";
}

function cancelWhiteModelBeamPlacement() {
  whiteViewer.cancelBeamPlacement();
  $("#add-white-model-beam").hidden = false;
  $("#cancel-white-model-beam").hidden = true;
  $("#white-model-beam-status").textContent = "已取消；樑會自動吸附天花板，不會自由漂浮。";
}

const sceneObjectTypeLabels = {
  "bed-frame": "雙人床",
  bed: "床",
  wardrobe: "衣櫃",
  sofa: "沙發",
  "coffee-table": "茶几",
  "dining-table": "餐桌",
  "dining-chair": "餐椅",
  "floor-lamp": "落地燈",
  "flower-pots-planter": "植栽",
  "large-medium-rug": "地毯",
  rug: "地毯",
  curtain: "窗簾",
};

function sceneObjectDisplayName(item, index) {
  return sceneObjectTypeLabels[item.normalized_type]
    || item.name_zh
    || item.name_zh_raw
    || item.normalized_type
    || `家具 ${index + 1}`;
}

function renderSceneObjectList() {
  const objects = state.sceneData?.scene_objects || [];
  const markup = objects.map((item, index) => `
    <button type="button" data-scene-object-index="${index}" class="${index === state.selectedSceneIndex ? "is-active" : ""}">
      <strong><b class="rp-object-number">#${index + 1}</b>${escapeHtml(sceneObjectDisplayName(item, index))}</strong>
      <span>${item.model_url ? "資料庫 GLB" : "缺少 GLB"}</span>
      <small>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</small>
      <small>${item.user_specified ? "已指定" : "系統選配"}</small>
    </button>
  `).join("");
  if (element.objectList) {
    element.objectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  }
  if (element.realisticObjectList) {
    element.realisticObjectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  }
  renderConfigurationPlan();
}

function saveSelectedSceneAppearance() {
  const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  if (!selected) return;
  selected.model_locked = $("#lock-specified-model").checked;
  selected.material_locked = $("#lock-specified-material").checked;
  selected.specified_color = $("#specified-furniture-color").value;
  selected.specified_material = $("#specified-furniture-material").value;
  const materialProfiles = {
    wood: { roughness: 0.56, metalness: 0 },
    fabric: { roughness: 0.9, metalness: 0 },
    leather: { roughness: 0.48, metalness: 0 },
    metal: { roughness: 0.3, metalness: 0.78 },
    glass: { roughness: 0.12, metalness: 0.06, opacity: 0.42 },
  };
  selected.material_override = selected.material_locked
    ? {
        color: selected.specified_color,
        kind: selected.specified_material,
        pbr: materialProfiles[selected.specified_material] || {
          roughness: 0.7,
          metalness: 0,
        },
      }
    : null;
}

function loadSelectedSceneAppearance() {
  const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  $("#specified-furniture-color").value = selected?.specified_color || "#f2f0ec";
  $("#specified-furniture-material").value = selected?.specified_material || "";
  $("#lock-specified-model").checked = selected?.model_locked === true;
  $("#lock-specified-material").checked = selected?.material_locked === true;
  const status = $("#specified-furniture-status");
  if (status) {
    status.textContent = selected?.user_specified
      ? "目前選取家具已在 3D 微調面板鎖定為指定需求。"
      : "可在 3D 畫面選取家具後，使用浮動微調面板鎖定指定需求。";
  }
}

function renderWhiteWalkRoomSelector() {
  if (!element.whiteWalkRoom) return;
  const selectedExists = state.rooms.some(
    (room) => String(room.id) === String(state.selectedWalkRoomId),
  );
  if (!selectedExists) {
    state.selectedWalkRoomId = state.selectedRoomId || state.rooms[0]?.id || null;
  }
  element.whiteWalkRoom.innerHTML = state.rooms.map((room) => `
    <option value="${escapeHtml(room.id)}">${escapeHtml(room.label || "未命名空間")}</option>
  `).join("");
  element.whiteWalkRoom.disabled = state.rooms.length === 0;
  if (state.selectedWalkRoomId) element.whiteWalkRoom.value = state.selectedWalkRoomId;
}

function selectedWhiteWalkRoomPayload() {
  const room = state.rooms.find(
    (candidate) => String(candidate.id) === String(state.selectedWalkRoomId),
  ) || state.rooms[0];
  if (!room?.polygon_cm?.length) return null;
  const center = planCenterCm();
  const roomMiddle = roomCenter(room);
  return {
    id: room.id,
    label: room.label || "未命名空間",
    center_cm: {
      x: roomMiddle.x - center.x,
      z: roomMiddle.y - center.y,
    },
    polygon_cm: room.polygon_cm.map((point) => ({
      x: point.x - center.x,
      z: point.y - center.y,
    })),
  };
}

function activateWhiteWalkMode() {
  renderWhiteWalkRoomSelector();
  const room = selectedWhiteWalkRoomPayload();
  if (!room) {
    setStatus("目前沒有可進入的房間，請先回到第 4 步確認空間。", "error");
    return false;
  }
  if (!whiteViewer.setWalkRoom(room)) {
    setStatus("3D 場景尚未就緒，或該空間沒有可安全站立的位置。", "error");
    return false;
  }
  $$("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === "walk");
  });
  $$("[data-white-interaction]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.whiteInteraction === "walk");
  });
  return true;
}

function activateWhiteFurnitureEditing() {
  whiteViewer.setInteractionMode("edit");
  $$("[data-white-interaction]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.whiteInteraction === "edit");
  });
}

// Catalog edits rebuild the viewer. Keep the user's current framing while doing so.
async function reloadWhiteViewerPreservingCamera() {
  return reloadViewerPreservingState(whiteViewer, state.sceneData, {
    interactionMode: "edit",
  });
}

async function deleteSelectedSceneFurniture() {
  const objects = state.sceneData?.scene_objects || [];
  const selected = objects[state.selectedSceneIndex];
  if (!selected) {
    setStatus("目前沒有可刪除的家具。", "error");
    return;
  }
  objects.splice(state.selectedSceneIndex, 1);
  state.furniture2d = removeFurniture2dBySceneObject(
    state.furniture2d,
    selected,
  );
  syncFurnitureInventoryAcrossSchemes();
  state.selectedSceneIndex = Math.max(0, Math.min(state.selectedSceneIndex, objects.length - 1));
  const nextSelected = objects[state.selectedSceneIndex] || null;
  state.selectedFurniture2dId = nextSelected?.furniture_id || null;
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  if (state.workflow.currentStep === "white_model_3d") {
    await reloadWhiteViewerPreservingCamera();
    renderConfigurationPlan();
    if (nextSelected) {
      selectSceneObjectByFurnitureId(nextSelected.furniture_id, {
        viewer: whiteViewer,
        focus: false,
      });
      activateWhiteFurnitureEditing();
    }
    scheduleSave("white_model_3d");
  } else {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
    renderConfigurationPlan();
    scheduleSave("realistic_3d");
  }
  setStatus(
    `已刪除「${selected.name_zh_raw || selected.normalized_type || "家具"}」，其餘家具已重新編號。`,
  );
}

function activeCatalogSearchInput() {
  return element.standardCatalogSearch;
}

function questionnaireCatalogGroup(room) {
  const type = String(room?.visual_space_type || room?.type || "");
  return {
    bedroom: "bedroom",
    living_room: "living",
    kitchen: "dining_kitchen",
    storage: "study",
  }[type] || "storage";
}

const QUESTIONNAIRE_CATALOG_SPACES = Object.freeze([
  { id: "entryway", label: "玄關", group: "storage" },
  { id: "hallway", label: "走道", group: "storage" },
  { id: "living_room", label: "客廳", group: "living" },
  { id: "kitchen", label: "廚房", group: "dining_kitchen" },
  { id: "bedroom", label: "臥室", group: "bedroom" },
  { id: "bathroom", label: "浴室", group: "bathroom" },
  { id: "balcony", label: "陽台", group: "outdoor" },
  { id: "storage", label: "儲藏室", group: "study" },
  { id: "garage", label: "車庫", group: "storage" },
]);

const QUESTIONNAIRE_CATALOG_PURPOSES = Object.freeze({
  bedroom: [
    ["sleep", "睡眠", ["bed", "bedside-table"]],
    ["storage", "收納", ["wardrobe", "storage-cabinet"]],
    ["dress", "更衣", ["wardrobe", "mirror", "stool-bench"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair", "lounge-chair"]],
    ["vanity", "梳妝", ["mirror", "desk", "stool-bench"]],
  ],
  living_room: [
    ["rest", "休息聊天", ["sofa", "coffee-table", "lounge-chair"]],
    ["media", "影音", ["tv-bench", "sofa", "lounge-chair"]],
    ["dining", "用餐", ["dining-table", "dining-chair", "storage-cabinet"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair", "lounge-chair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "storage-cabinet", "stool-bench"]],
  ],
  kitchen: [
    ["dining", "用餐", ["dining-table", "dining-chair"]],
    ["prep", "備餐收納", ["appliance-cabinet", "storage-cabinet"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "dining-chair"]],
  ],
  storage: [
    ["storage", "收納整理", ["storage-cabinet", "wardrobe", "shelf"]],
    ["work", "閱讀工作", ["desk", "office-chair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "storage-cabinet"]],
  ],
  entryway: [["entry", "出門整理", ["mirror", "storage-cabinet", "stool-bench"]]],
  hallway: [["passage", "走道收納", ["mirror", "storage-cabinet"]]],
  bathroom: [["wash", "盥洗收納", ["bathroom-vanity", "mirror-cabinet", "storage-cabinet"]]],
  balcony: [["relax", "休憩植栽", ["lounge-chair", "flower-pots-planter", "stool-bench"]]],
  garage: [["garage", "工具收納", ["storage-cabinet", "shelf"]]],
});

const QUESTIONNAIRE_CATALOG_PURPOSE_TYPES = Object.freeze({
  "bedroom:sleep": ["bed", "mattress"],
  "bedroom:storage": ["pax-wardrobe", "wardrobe", "chests-of-drawer"],
  "bedroom:dress": ["pax-wardrobe", "wardrobe", "mirror", "stool-bench"],
  "bedroom:work": ["desk", "office-chair", "armchair", "lounge-chair"],
  "bedroom:vanity": ["mirror", "desk", "stool-bench"],
  "living_room:rest": ["fabric-sofa", "sofa", "leather-sofa", "modular-sofa", "coffee-table", "armchair"],
  "living_room:media": ["tv-bench", "tv-media-furniture", "sofa", "armchair"],
  "living_room:dining": ["dining-table", "dining-chair", "bar-table"],
  "living_room:work": ["desk", "office-chair", "armchair", "lounge-chair"],
  "living_room:kids": ["kids-chairs-stool", "storage-boxes-basket", "stool-bench"],
  "kitchen:dining": ["dining-table", "dining-chair", "bar-table"],
  "kitchen:prep": ["table", "bar-table", "stool-bench"],
  "kitchen:kids": ["dining-chair", "kids-chairs-stool", "stool-bench"],
  "storage:storage": ["cabinet-cupboard", "shelving-unit", "bookcase", "storage-boxes-basket"],
  "storage:work": ["desk", "office-chair", "gaming-chair"],
  "storage:kids": ["storage-boxes-basket", "kids-chairs-stool", "stool-bench"],
  "entryway:entry": ["shoe-cabinet", "mirror", "stool-bench", "clothes-rack"],
  "hallway:passage": ["wall-shelf", "mirror", "shoe-cabinet"],
  "bathroom:wash": ["mirror-cabinet", "bathroom-vanity", "storage-cabinet"],
  "balcony:relax": ["lounge-chair", "flower-pots-planter", "stool-bench"],
  "garage:garage": ["cabinet-cupboard", "shelving-unit", "storage-solution-system"],
});

const QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS = Object.freeze({
  "office-chair": "閱讀工作", "gaming-chair": "閱讀工作", armchair: "閱讀休憩",
  "lounge-chair": "閱讀休憩", "dining-chair": "用餐", "stool-bench": "梳妝／臨時座位",
  "kids-chairs-stool": "兒童使用", bed: "睡眠", wardrobe: "收納更衣", desk: "閱讀工作",
  "dining-table": "用餐", sofa: "休息聊天", "coffee-table": "客廳置物", "tv-bench": "影音",
  "storage-cabinet": "收納整理",
});

const QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS = Object.freeze({
  "pax-wardrobe": "收納更衣",
  "fabric-sofa": "休息招待",
  "leather-sofa": "休息招待",
  "modular-sofa": "休息招待",
  table: "備餐整理",
  "bar-table": "用餐備餐",
  "cabinets-cupboard": "收納整理",
  "cabinet-cupboard": "收納整理",
  "shelving-unit": "收納整理",
  "storage-boxes-basket": "收納整理",
  "storage-solution-system": "收納整理",
  "wall-shelf": "走道收納",
  "shoe-cabinet": "玄關整理",
  "clothes-rack": "玄關整理",
  "tv-media-furniture": "影音設備",
  "chests-of-drawer": "收納整理",
  mirror: "更衣梳妝",
  "large-medium-rug": "休息活動區",
  "runner-small-rug": "走道鋪設",
  "floor-lamp": "閱讀照明",
  planter: "陽台休憩",
  decoration: "空間點綴",
  "pillow-cushion": "休息舒適",
  shelf: "收納整理",
  bookcase: "閱讀工作",
  "storage-bench": "收納整理",
  "storage-box": "收納整理",
  lighting: "照明安全",
});

function questionnaireCatalogRoomType(room) {
  return String(room?.visual_space_type || room?.type || room?.room_type || "").toLowerCase();
}

function questionnaireCatalogActiveSpace(room) {
  return questionnaireCatalogScope === "room" ? questionnaireCatalogRoomType(room) : questionnaireCatalogSpace;
}

function questionnaireCatalogPurposeDefinition(room) {
  const space = questionnaireCatalogActiveSpace(room);
  const definition = (QUESTIONNAIRE_CATALOG_PURPOSES[space] || [])
    .find(([id]) => id === questionnaireCatalogPurpose);
  if (!definition) return null;
  return [
    definition[0],
    definition[1],
    QUESTIONNAIRE_CATALOG_PURPOSE_TYPES[`${space}:${definition[0]}`] || definition[2],
  ];
}

function questionnaireCatalogBrowsePrompt(room, query = "") {
  if (query) return "";
  const activeSpace = questionnaireCatalogActiveSpace(room);
  if (!activeSpace) return "請先選擇要瀏覽的空間，再挑選用途。";
  if (!questionnaireCatalogPurpose) return "請選擇家具用途，再查看對應的家具選項。";
  return "";
}

function renderQuestionnaireCatalogBrowseChoices(room) {
  if (!room) return;
  const activeSpace = questionnaireCatalogActiveSpace(room);
  if (element.questionnaireCatalogSpaceGroups) {
    element.questionnaireCatalogSpaceGroups.hidden = questionnaireCatalogScope !== "all";
    element.questionnaireCatalogSpaceGroups.innerHTML = QUESTIONNAIRE_CATALOG_SPACES.map((space) => `
      <button type="button" data-questionnaire-catalog-space="${escapeHtml(space.id)}"
        class="${space.id === activeSpace ? "is-active" : ""}" aria-pressed="${space.id === activeSpace}">${escapeHtml(space.label)}</button>
    `).join("");
  }
  if (element.questionnaireCatalogPurposeGroups) {
    const purposes = QUESTIONNAIRE_CATALOG_PURPOSES[activeSpace] || [];
    element.questionnaireCatalogPurposeGroups.hidden = !purposes.length;
    const spaceLabel = QUESTIONNAIRE_CATALOG_SPACES.find((space) => space.id === activeSpace)?.label || room.label;
    element.questionnaireCatalogPurposeGroups.innerHTML = `
      <span>${escapeHtml(spaceLabel)}用途</span>
      ${purposes.map(([id, label]) => `<button type="button" data-questionnaire-catalog-purpose="${escapeHtml(id)}"
        class="${id === questionnaireCatalogPurpose ? "is-active" : ""}" aria-pressed="${id === questionnaireCatalogPurpose}">${escapeHtml(label)}</button>`).join("")}
    `;
  }
  renderSelectedFurnitureWorkspace();
}

const CATALOG_FACET_TRADITIONAL_LABELS = Object.freeze({
  color: Object.freeze({
    "dark grey": "深灰色",
    "dark gray": "深灰色",
    oak: "橡木色",
    anthracite: "煤灰色",
    bamboo: "竹色",
    birch: "樺木色",
    white: "白色",
    ivory: "象牙白",
    cream: "奶油色",
    beige: "米色",
    grey: "灰色",
    gray: "灰色",
    black: "黑色",
    brown: "棕色",
    blue: "藍色",
    green: "綠色",
    yellow: "黃色",
    red: "紅色",
    natural: "自然原木色",
    wood: "木色",
    walnut: "胡桃木色",
    pine: "松木色",
  }),
  material: Object.freeze({
    "glb材質（未標示）": "模型材質（未標示）",
    acacia: "相思木",
    aluminium: "鋁",
    aluminum: "鋁",
    wood: "木材",
    metal: "金屬",
    steel: "鋼材",
    "stainless steel": "不鏽鋼",
    iron: "鐵材",
    plastic: "塑膠",
    "polystyrene plastic": "聚苯乙烯塑膠",
    fabric: "布料",
    textile: "織物",
    leather: "皮革",
    "faux fur": "仿毛皮",
    sheepskin: "羊皮",
    glass: "玻璃",
    rattan: "藤編",
    bamboo: "竹材",
    beech: "櫸木",
    birch: "樺木",
    brass: "黃銅",
    chrome: "鍍鉻",
    cork: "軟木",
    nickel: "鎳",
    pine: "松木",
    foam: "泡棉",
    cotton: "棉",
    "pu皮革": "人造皮革",
    pvc: "聚氯乙烯塑膠",
    ceramic: "陶瓷",
    marble: "大理石",
    stone: "石材",
    concrete: "混凝土",
    terracotta: "赤陶",
    velvet: "絲絨",
    seagrass: "海草",
    "water hyacinth": "水葫蘆纖維",
    plywood: "夾板",
    veneer: "木皮",
    "wood veneer": "木皮",
    "solid wood": "實木",
    mdf: "密集板",
    particleboard: "塑合板",
    walnut: "胡桃木",
    oak: "橡木",
  }),
});

function catalogFacetTraditionalLabel(facet, value) {
  const source = String(value || "").trim();
  if (!source) return source;
  const normalized = source.toLocaleLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  const labels = CATALOG_FACET_TRADITIONAL_LABELS[facet];
  if (!labels) return source;
  if (labels[normalized]) return labels[normalized];
  return source.split(/([、,;/|])/).map((part) => {
    if (/^[、,;/|]$/.test(part)) return part === "," ? "、" : part;
    const key = part.trim().toLocaleLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
    return labels[key] || part;
  }).join("");
}

function setCatalogSelectOptions(select, options, value, labelKey = "label", valueKey = "value", emptyLabel = "全部", labelFormatter = null) {
  if (!select) return;
  const safeValue = String(value || "");
  select.innerHTML = [`<option value="">${escapeHtml(emptyLabel)}</option>`, ...options.map((option) => {
    const optionValue = String(option[valueKey] || option.type || "");
    const sourceLabel = String(option[labelKey] || option.type_name_zh || optionValue);
    const optionLabel = labelFormatter ? labelFormatter(sourceLabel, option) : sourceLabel;
    return `<option value="${escapeHtml(optionValue)}" ${optionValue === safeValue ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
  })].join("");
}

function renderQuestionnaireCatalogFilters(payload) {
  if (!questionnaireCatalogRoomId) return;
  const facets = payload.filter_options || {};
  setCatalogSelectOptions(element.questionnaireCatalogColor, facets.colors || [], element.questionnaireCatalogColor?.value || "", "label", "value", "全部顏色", (label) => catalogFacetTraditionalLabel("color", label));
  setCatalogSelectOptions(element.questionnaireCatalogMaterial, facets.materials || [], element.questionnaireCatalogMaterial?.value || "", "label", "value", "全部材質", (label) => catalogFacetTraditionalLabel("material", label));
}

function renderQuestionnaireCatalogBatch() {
  if (!element.questionnaireCatalogBatch) return;
  const count = questionnaireCatalogSelectedFurnitureIds.size;
  element.questionnaireCatalogBatch.hidden = !questionnaireCatalogRoomId;
  if (element.questionnaireCatalogSelectedCount) {
    element.questionnaireCatalogSelectedCount.textContent = count ? `已選擇 ${count} 件家具` : "尚未選擇家具";
  }
  if (element.addSelectedQuestionnaireFurniture) {
    element.addSelectedQuestionnaireFurniture.disabled = count === 0;
  }
}

function setFurnitureCatalogOpen(open) {
  if (open) {
    if (!questionnaireCatalogRoomId) {
      element.catalogDrawer.querySelector("h2").textContent = "新增家具";
      element.catalogDrawer.querySelector("header p").textContent = "搜尋後選擇家具，再回到 3D 房間點選合法擺放位置。";
      if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = true;
      if (element.questionnaireCatalogBatch) element.questionnaireCatalogBatch.hidden = true;
      if (element.standardCatalogSearch) element.standardCatalogSearch.hidden = false;
      const catalogSearchButton = $("#search-glb-furniture");
      if (catalogSearchButton) catalogSearchButton.hidden = false;
      activateWhiteFurnitureEditing();
    }
    if (typeof element.catalogDrawer.showModal === "function" && !element.catalogDrawer.open) {
      element.catalogDrawer.showModal();
    } else if (!element.catalogDrawer.open) {
      element.catalogDrawer.setAttribute("open", "");
    }
    activeCatalogSearchInput()?.focus();
    return;
  }
  if (typeof element.catalogDrawer.close === "function") {
    element.catalogDrawer.close();
  } else {
    element.catalogDrawer.removeAttribute("open");
  }
  questionnaireCatalogRoomId = null;
  questionnaireCatalogSelectedFurnitureIds = new Set();
  questionnaireCatalogSelectedFurniture = new Map();
}

function openQuestionnaireFurnitureCatalog(roomId = activeQuestionnaireRoom()?.id) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId))
    || activeQuestionnaireRoom();
  if (!room || !element.catalogDrawer) {
    if (element.questionnaireFurnitureStatus) {
      element.questionnaireFurnitureStatus.textContent = "目前找不到可加入家具的房間，請先選擇房間後再試一次。";
    }
    return;
  }
  questionnaireCatalogRoomId = room.id;
  questionnaireCatalogSelectedFurnitureIds = new Set();
  questionnaireCatalogSelectedFurniture = new Map();
  element.catalogDrawer.querySelector("h2").textContent = `加入${room.label}的家具`;
  element.catalogDrawer.querySelector("header p").textContent = "先瀏覽適合本房的家具；也可用搜尋、類別、顏色或材質快速篩選。加入後會直接勾選到此房。";
  questionnaireCatalogScope = "room";
  questionnaireCatalogSpace = "";
  questionnaireCatalogPurpose = "";
  if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = false;
  if (element.standardCatalogSearch) element.standardCatalogSearch.hidden = false;
  const catalogSearchButton = $("#search-glb-furniture");
  if (catalogSearchButton) catalogSearchButton.hidden = true;
  const catalogSearchInput = $("#glb-furniture-search");
  if (catalogSearchInput) catalogSearchInput.value = "";
  if (element.questionnaireCatalogType) element.questionnaireCatalogType.value = "";
  if (element.questionnaireCatalogColor) element.questionnaireCatalogColor.value = "";
  if (element.questionnaireCatalogMaterial) element.questionnaireCatalogMaterial.value = "";
  renderQuestionnaireCatalogBrowseChoices(room);
  element.glbResults.innerHTML = "<p>正在載入適合本房的家具…</p>";
  renderQuestionnaireCatalogBatch();
  setFurnitureCatalogOpen(true);
  void searchGlbFurniture();
}

async function searchGlbFurniture() {
  const query = activeCatalogSearchInput()?.value.trim() || "";
  const thumbnailBatch = ++glbThumbnailBatch;
  try {
    const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
    const params = new URLSearchParams({ has_model: "true", detail: "scene", page_size: questionnaireCatalogRoomId ? "48" : "24" });
    if (query) params.set("q", query);
    // 搜尋文字可跨用途找同類家具；未搜尋時才依空間與用途收斂。
    const activeSpace = questionnaireCatalogActiveSpace(room);
    const activeSpaceDefinition = QUESTIONNAIRE_CATALOG_SPACES.find((space) => space.id === activeSpace);
    const activePurpose = questionnaireCatalogPurposeDefinition(room);
    const browsePrompt = questionnaireCatalogRoomId
      ? questionnaireCatalogBrowsePrompt(room, query)
      : "";
    if (browsePrompt) {
      element.glbResults.innerHTML = `<p class="rp-catalog-browse-prompt">${escapeHtml(browsePrompt)}</p>`;
      element.glbResults.dataset.items = "[]";
      renderQuestionnaireCatalogBatch();
      return;
    }
    if (!query && questionnaireCatalogRoomId && activeSpace) {
      if (activePurpose?.[2]?.length) {
        params.set("types", activePurpose[2].join(","));
      } else {
        params.set("group", activeSpaceDefinition?.group || questionnaireCatalogGroup(room));
      }
    }
    if (questionnaireCatalogRoomId) {
      const type = element.questionnaireCatalogType?.value || "";
      const color = element.questionnaireCatalogColor?.value || "";
      const material = element.questionnaireCatalogMaterial?.value || "";
      if (type) params.set("type", type);
      if (color) params.set("color", color);
      if (material) params.set("material", material);
    }
    const payload = await api(`/api/furniture?${params.toString()}`);
    const questionnaireMode = Boolean(questionnaireCatalogRoomId);
    renderQuestionnaireCatalogFilters(payload);
    const catalogItems = questionnaireMode
      ? [...new Map((payload.items || []).map((item) => {
        const normalizedType = item.normalized_type || item.category || item.taxonomy_type || "other";
        const label = questionnaireFurnitureDisplayLabel({ ...item, normalized_type: normalizedType }) || "其他家具";
        return [`${normalizedType}:${label}`, item];
      })).values()].slice(0, 18)
      : (payload.items || []);
    element.glbResults.innerHTML = catalogItems.map((item) => {
      const preview = item.image_url
        || item.thumbnail_url
        || item.preview_url
        || item.main_image_url
        || item.image
        || "";
      const title = item.name_zh || item.name_zh_raw || item.name_en || "GLB 家具";
      if (questionnaireMode) {
        const optionLabel = questionnaireFurnitureDisplayLabel(item) || "其他家具";
        const purposeLabel = QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS[item.normalized_type]
          || QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS[item.normalized_type]
          || "可加入配置";
        return `
          <article class="rp-glb-result rp-questionnaire-catalog-option">
            <label class="rp-catalog-select-item">
              <input type="checkbox" data-questionnaire-catalog-select="${escapeHtml(item.furniture_id)}" ${questionnaireCatalogSelectedFurnitureIds.has(String(item.furniture_id)) ? "checked" : ""} />
              <span><strong>${escapeHtml(optionLabel)}</strong><small>適合：${escapeHtml(purposeLabel)}</small></span>
            </label>
          </article>
        `;
      }
      return `
      <article class="rp-glb-result has-preview">
        <div class="rp-glb-thumb">
          <img
            class="${preview ? "" : "is-loading"}"
            src="${escapeHtml(preview || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")}"
            alt="${escapeHtml(title)} PNG 預覽"
            data-glb-thumbnail="${escapeHtml(item.furniture_id)}"
            loading="lazy"
          />
        </div>
        <strong>${escapeHtml(title)}</strong>
        <span>${Number(item.size_cm?.width || 0).toFixed(0)} x ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</span>
        <div class="rp-inline-actions">
          <button type="button" data-replace-furniture-id="${escapeHtml(item.furniture_id)}">替換選取家具</button>
          <button type="button" data-add-furniture-id="${escapeHtml(item.furniture_id)}">新增到 3D</button>
        </div>
      </article>
    `;
    }).join("") || "<p>找不到適合 GLB 的家具。</p>";
    element.glbResults.dataset.items = JSON.stringify(catalogItems);
    catalogItems.forEach((item) => {
      if (questionnaireCatalogSelectedFurnitureIds.has(String(item.furniture_id))) {
        questionnaireCatalogSelectedFurniture.set(String(item.furniture_id), item);
      }
    });
    renderQuestionnaireCatalogBatch();
    const itemsNeedingGeneratedThumbnails = questionnaireMode ? [] : catalogItems.filter(
      (item) => !(item.image_url || item.thumbnail_url || item.preview_url || item.main_image_url || item.image),
    );
    if (itemsNeedingGeneratedThumbnails.length) {
      glbThumbnailSequence = glbThumbnailSequence
        .catch(() => null)
        .then(() => populateGlbSearchThumbnails(itemsNeedingGeneratedThumbnails, thumbnailBatch));
    }
  } catch (error) {
    element.glbResults.innerHTML = `<p>${escapeHtml(errorMessage(error))}</p>`;
  }
}

function glbThumbnailScene(item) {
  return {
    floorplan: {
      width_cm: 360,
      depth_cm: 360,
      room_height_cm: 270,
      wall_segments: [],
      door_segments: [],
      window_segments: [],
    },
    scene_objects: [{
      ...item,
      furniture_id: `glb-thumbnail-${item.furniture_id}`,
      position_cm: { x: 0, z: 0 },
      rotation_y_deg: 0,
      position_locked: true,
      placement_failed: false,
    }],
    style: { style_id: state.activeStyleId || "white_model" },
    design_choices: { catalog_thumbnail_mode: true },
  };
}

async function populateGlbSearchThumbnails(items, batchId) {
  for (const item of items) {
    if (batchId !== glbThumbnailBatch) return;
    const furnitureId = String(item.furniture_id || "");
    if (!furnitureId || !item.model_url) continue;
    const nativePreview = item.image_url
      || item.thumbnail_url
      || item.preview_url
      || item.main_image_url
      || item.image;
    if (nativePreview) continue;
    let png = glbThumbnailCache.get(item.model_url);
    if (!png) {
      try {
        await glbThumbnailViewer.loadScene(glbThumbnailScene(item));
        if (glbThumbnailViewer.getDiagnostics()?.failedFurniture?.length) continue;
        glbThumbnailViewer.selectObjectByIndex(0, {
          focus: true,
          showGuide: false,
        });
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        png = glbThumbnailViewer.capturePng();
        glbThumbnailCache.set(item.model_url, png);
      } catch (error) {
        console.warn("GLB thumbnail generation failed", item.model_url, error);
        continue;
      }
    }
    if (batchId !== glbThumbnailBatch) return;
    document.querySelectorAll(
      `[data-glb-thumbnail="${CSS.escape(furnitureId)}"]`,
    ).forEach((image) => {
      image.src = png;
      image.classList.remove("is-loading");
    });
  }
}

async function populateQuestionnaireFurnitureThumbnails(items, revision) {
  for (const item of items) {
    if (revision !== questionnaireFurnitureThumbnailRevision) return;
    if (!item?.furniture_id || !item?.model_url || questionnaireFurniturePreviewUrl(item)) continue;
    let png = glbThumbnailCache.get(item.model_url);
    if (!png) {
      try {
        await glbThumbnailViewer.loadScene(glbThumbnailScene(item));
        if (glbThumbnailViewer.getDiagnostics()?.failedFurniture?.length) continue;
        glbThumbnailViewer.selectObjectByIndex(0, {
          focus: true,
          showGuide: false,
        });
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        png = glbThumbnailViewer.capturePng();
        glbThumbnailCache.set(item.model_url, png);
      } catch (error) {
        console.warn("Questionnaire furniture thumbnail generation failed", item.model_url, error);
        continue;
      }
    }
    if (revision !== questionnaireFurnitureThumbnailRevision) return;
    document.querySelectorAll(
      `[data-questionnaire-furniture-thumbnail="${CSS.escape(String(item.furniture_id))}"]`,
    ).forEach((image) => {
      image.src = png;
      image.classList.remove("is-loading");
    });
  }
}

async function styleFurnitureCandidate(item, pack) {
  const cacheKey = `${pack.styleId}:${item.normalized_type}`;
  if (!styleFurnitureCache.has(cacheKey)) {
    const payload = await api(
      `/api/furniture?type=${encodeURIComponent(item.normalized_type)}`
      + `&style=${encodeURIComponent(pack.styleId)}`
      + "&has_model=true&detail=scene&page_size=24",
    );
    styleFurnitureCache.set(cacheKey, payload.items || []);
  }
  const candidates = styleFurnitureCache.get(cacheKey);
  const currentSize = item.size_cm || {};
  return candidates.toSorted((a, b) => {
    const aSize = a.size_cm || {};
    const bSize = b.size_cm || {};
    const aDelta = Math.abs(Number(aSize.width || 0) - Number(currentSize.width || 0))
      + Math.abs(Number(aSize.depth || 0) - Number(currentSize.depth || 0));
    const bDelta = Math.abs(Number(bSize.width || 0) - Number(currentSize.width || 0))
      + Math.abs(Number(bSize.depth || 0) - Number(currentSize.depth || 0));
    return aDelta - bDelta;
  })[0] || null;
}

async function replaceUnlockedFurnitureForStyle(pack) {
  await Promise.all((state.sceneData?.scene_objects || []).map(async (item) => {
    if (item.user_specified || item.model_locked) return;
    try {
      const candidate = await styleFurnitureCandidate(item, pack);
      if (!candidate?.model_url) return;
      item.catalog_furniture_id = candidate.furniture_id;
      item.model_url = candidate.model_url;
      item.name_zh_raw = candidate.name_zh || candidate.name_zh_raw || item.name_zh_raw;
      item.primary_style = candidate.primary_style || pack.styleId;
    } catch (error) {
      console.warn(error);
    }
  }));
}

async function replaceSceneFurniture(furnitureId) {
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const replacement = items.find((item) => item.furniture_id === furnitureId);
  const current = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  if (!replacement || !current) return;
  const originalSize = current.size_cm;
  const candidate = {
    ...current,
    ...replacement,
    furniture_id: current.furniture_id,
    catalog_furniture_id: replacement.furniture_id,
    position_cm: current.position_cm,
    rotation_y_deg: current.rotation_y_deg,
    position_locked: true,
    user_specified: true,
    model_locked: true,
    requested_size_cm: originalSize,
    size_cm: replacement.size_cm || originalSize,
  };
  try {
    const verdict = await api("/api/scene/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        item: candidate,
        others: state.sceneData.scene_objects.filter((item) => item !== current),
      }),
    });
    if (!verdict.ok) {
      element.whiteError.textContent = `無法替換：新家具尺寸在原位置${verdict.reason || "會碰撞、穿牆或超出房間"}。`;
      setStatus(element.whiteError.textContent, "error");
      return;
    }
  } catch (error) {
    element.whiteError.textContent = errorMessage(error);
    setStatus(element.whiteError.textContent, "error");
    return;
  }
  Object.assign(current, candidate);
  state.furniture2d = upsertFurniture2dFromSceneObject(
    state.furniture2d,
    current,
    furniture2dDefaultsForSceneObject(current),
  );
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  await reloadWhiteViewerPreservingCamera();
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  scheduleSave("white_model_3d");
  element.whiteError.textContent = "";
  setStatus("已更換實際 GLB，新尺寸與原位置已通過家具引擎檢查。");
}

function addQuestionnaireCatalogFurniture(furnitureId, catalogOffer = null) {
  const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
  const furniture = roomFurnitureRequirement(room?.id);
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const offer = catalogOffer || items.find((item) => String(item.furniture_id) === String(furnitureId));
  if (!room || !furniture || !offer) return;
  const normalizedOffer = {
    ...offer,
    normalized_type: offer.normalized_type || offer.category || offer.taxonomy_type || "other",
    reason: "使用者從家具庫加入",
  };
  const known = state.roomFurnitureRecommendations[room.id] || [];
  if (!known.some((item) => String(item.furniture_id) === String(normalizedOffer.furniture_id))) {
    state.roomFurnitureRecommendations[room.id] = [...known, normalizedOffer];
  }
  const selected = (furniture.selected || []).filter(
    (item) => String(item.furniture_id) !== String(normalizedOffer.furniture_id),
  );
  selected.push({
    ...questionnaireFurnitureSelectionItem(normalizedOffer, selected.length + 1),
    selection_source: "questionnaire_catalog_add",
  });
  furniture.selected = selected.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some(
      (selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id),
    ))
    .map((item) => item.normalized_type);
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已將家具加入「${room.label}」，第 6 步需要重新產生。`);
  scheduleSave("requirements");
}

function addSceneFurniture(furnitureId) {
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const replacement = items.find((item) => item.furniture_id === furnitureId);
  if (!replacement || !state.sceneData) return;
  const started = whiteViewer.beginPlacement(async (positionCm) => {
    const candidate = {
      ...replacement,
      furniture_id: `${replacement.furniture_id}-user-${Date.now()}`,
      catalog_furniture_id: replacement.furniture_id,
      name_zh_raw: replacement.name_zh || replacement.name_zh_raw || replacement.name_en,
      position_cm: positionCm,
      rotation_y_deg: 0,
      position_locked: true,
      user_specified: true,
      model_locked: true,
      placement_failed: false,
      size_cm: replacement.size_cm,
      requested_size_cm: replacement.size_cm,
    };
    try {
      const verdict = await api("/api/scene/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          item: candidate,
          others: state.sceneData.scene_objects,
        }),
      });
      if (!verdict.ok) {
        element.whiteError.textContent = `無法新增在該位置：${verdict.reason || "會碰撞、穿牆或超出房間"}。`;
        setStatus(element.whiteError.textContent, "error");
        return;
      }
      state.sceneData.scene_objects.push(candidate);
      state.furniture2d = upsertFurniture2dFromSceneObject(
        state.furniture2d,
        candidate,
        furniture2dDefaultsForSceneObject(candidate),
      );
      syncFurnitureInventoryAcrossSchemes();
      renderLayoutRoomFilter();
      renderLayoutFurniture();
      state.selectedSceneIndex = state.sceneData.scene_objects.length - 1;
      state.selectedFurniture2dId = candidate.furniture_id;
      await reloadWhiteViewerPreservingCamera();
      renderSceneObjectList();
      renderConfigurationPlan();
      loadSelectedSceneAppearance();
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
      activateWhiteFurnitureEditing();
      element.whiteError.textContent = "";
      scheduleSave("white_model_3d");
      const furnitureNumber = state.selectedSceneIndex + 1;
      setStatus(
        `家具 ${furnitureNumber} 已新增到指定位置，可直接拖曳或旋轉，並已通過碰撞、淨空與房間邊界檢查。`,
      );
    } catch (error) {
      element.whiteError.textContent = errorMessage(error);
      setStatus(element.whiteError.textContent, "error");
    }
  });
  if (!started) {
    element.whiteError.textContent = "3D 場景尚未準備完成，請稍候再新增家具。";
  }
}

async function confirmWhiteModel() {
  element.whiteError.textContent = "";
  if (roomSchemeSelectionRequired() && !allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) {
    element.whiteError.textContent = "請先完成所有房間的 A/B 方案選擇，才能開始微調與確認最終配置。";
    setStatus(element.whiteError.textContent, "error");
    openRoomSchemeSelectionDialog();
    return;
  }
  const blockingFurniture = configurationBlockingFurniture();
  if (blockingFurniture.length) {
    element.whiteError.textContent =
      `目前還有 ${blockingFurniture.length} 件家具位置不合法，請先從 2D 待處理清單定位修正。`;
    setStatus(element.whiteError.textContent, "error");
    renderConfigurationPlan();
    return;
  }
  const diagnostics = whiteViewer.getDiagnostics();
  const expectedFurnitureCount = state.sceneData?.scene_objects?.filter(
    (item) => !item.placement_failed,
  ).length || 0;
  if (expectedFurnitureCount > 0 && diagnostics.visibleFurnitureCount <= 0) {
    element.whiteError.textContent = "3D 中看不到家具，必須先修正載入、比例或相機框景。";
    return;
  }
  if (diagnostics.failedFurniture.length > 0) {
    element.whiteError.textContent =
      `有 ${diagnostics.failedFurniture.length} 件資料庫 GLB 無法載入，請先修正型錄權限或更換家具，才能進入下一步。`;
    setStatus(element.whiteError.textContent, "error");
    renderConfigurationPlan();
    return;
  }
  saveSelectedSceneAppearance();
  try {
    const finalValidation = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        scene_objects: (state.sceneData?.scene_objects || []).map((item) => ({
          ...item,
          position_locked: true,
        })),
      }),
    });
    const invalid = syncFinalValidationToConfiguration(finalValidation.scene_objects || []);
    if (invalid.length) {
      element.whiteError.textContent = `${invalid
        .map((item) => item.name_zh_raw || item.normalized_type || "家具")
        .join("、")}未通過最終碰撞、淨空或房間邊界檢查，請先調整。`;
      setStatus(element.whiteError.textContent, "error");
      return;
    }
  } catch (error) {
    element.whiteError.textContent = errorMessage(error);
    setStatus(element.whiteError.textContent, "error");
    return;
  }
  state.workflow.complete("white_model_3d", {
    confirmed: true,
    visibleFurnitureCount: diagnostics.visibleFurnitureCount,
    expectedFurnitureCount,
  });
  const preferredPack = STYLE_PACKS.find(
    (pack) => pack.id === state.questionnaireFinishes.stylePackId,
  ) || STYLE_PACKS[0];
  state.activeStyleId = preferredPack.styleId;
  state.activeStylePackId = preferredPack.id;
  state.surfaceState = {
    wall: {
      material: state.questionnaireFinishes.wallMaterial || preferredPack.wall.surfaceOption,
      color: state.questionnaireFinishes.wallColor || preferredPack.wall.color,
    },
    floor: {
      material: state.questionnaireFinishes.floorMaterial || preferredPack.floor.surfaceOption,
      color: state.questionnaireFinishes.floorColor || preferredPack.floor.color,
    },
    furniture: state.sceneData.scene_objects.map((item) => ({
      id: item.furniture_id,
      styleLocked: item.user_specified || item.model_locked || item.material_locked,
      material: {
        color: item.specified_color || "#f2f0ec",
        kind: item.specified_material || "",
      },
    })),
  };
  renderStyleControls();
  state.workflow.goTo("realistic_3d");
  showStep("realistic_3d");
  await realisticViewer.loadScene(state.sceneData);
  realisticViewer.setViewMode("orbit");
  await applyStylePackToScene(preferredPack);
  const finishOptions = STYLE_MATERIAL_OPTIONS[preferredPack.styleId] || {};
  const wallFinish = finishOptions.wall?.find(
    (option) => option.id === state.questionnaireFinishes.wallMaterial,
  );
  const floorFinish = finishOptions.floor?.find(
    (option) => option.id === state.questionnaireFinishes.floorMaterial,
  );
  $("#wall-color").value =
    state.questionnaireFinishes.wallColor || wallFinish?.color || preferredPack.wall.color;
  $("#wall-material").value =
    state.questionnaireFinishes.wallMaterial || wallFinish?.id || preferredPack.wall.surfaceOption;
  $("#floor-color").value =
    state.questionnaireFinishes.floorColor || floorFinish?.color || preferredPack.floor.color;
  $("#floor-material").value =
    state.questionnaireFinishes.floorMaterial || floorFinish?.id || preferredPack.floor.surfaceOption;
  await applySurfaceOverrides();
  element.ceilingStyle.value =
    state.questionnaireFinishes.ceilingStyle || element.ceilingStyle.value;
  element.lightStyle.value =
    state.questionnaireFinishes.lightStyle || element.lightStyle.value;
  state.sceneData.design_choices.ceiling_material =
    state.questionnaireFinishes.ceilingMaterial;
  state.sceneData.design_choices.ceiling_color_hex =
    state.questionnaireFinishes.ceilingColor;
  await evaluateCeilingConflicts();
  setStatus(expectedFurnitureCount
    ? "家具可見性已通過。現在可即時切換 18 個完整 PBR StylePack。"
    : "純結構配置已確認。現在可即時切換 18 個完整 PBR StylePack。");
  scheduleSave("realistic_3d");
}

function renderStyleControls() {
  const styles = [...new Map(STYLE_PACKS.map((pack) => [pack.styleId, pack.styleLabel])).entries()];
  element.styleTabs.innerHTML = styles.map(([id, label]) =>
    `<button type="button" data-style-tab="${escapeHtml(id)}" class="${id === state.activeStyleId ? "is-active" : ""}">${escapeHtml(label)}</button>`
  ).join("");
  const packs = STYLE_PACKS.filter((pack) => pack.styleId === state.activeStyleId);
  element.styleGrid.innerHTML = packs.map((pack) => `
    <button type="button" data-style-pack="${escapeHtml(pack.id)}" class="${pack.id === state.activeStylePackId ? "is-active" : ""}">
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}" alt="${escapeHtml(`${pack.styleLabel} ${pack.name}參考圖`)}" loading="lazy">
      <span class="rp-style-swatches">${pack.palette.map((color) => `<i style="background:${escapeHtml(color)}"></i>`).join("")}</span>
      <strong>${escapeHtml(pack.name)}</strong>
      <small>材質：${escapeHtml(pack.furniture.displayHighlights.join("、"))}</small>
      <small>家具：${escapeHtml(pack.furnitureRules.signature.join("、"))}</small>
    </button>
  `).join("");
  element.ceilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.lightStyle.innerHTML = LIGHT_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${item.lumens} lm</option>`
  ).join("");
  const recommendedCeiling = CEILING_STYLES.find((item) =>
    item.styles.includes(state.activeStyleId)
  );
  const recommendedLight = LIGHT_STYLES.find((item) =>
    item.styles.includes(state.activeStyleId)
  );
  if (recommendedCeiling) element.ceilingStyle.value = recommendedCeiling.id;
  if (recommendedLight) element.lightStyle.value = recommendedLight.id;
  const activePack = stylePackByIdSafe(state.activeStylePackId) || packs[0];
  if (activePack) {
    if (!state.surfaceState.wall?.styleLocked) {
      $("#wall-color").value = activePack.wall.color;
      $("#wall-material").value = activePack.wall.surfaceOption;
    }
    if (!state.surfaceState.floor?.styleLocked) {
      $("#floor-color").value = activePack.floor.color;
      $("#floor-material").value = activePack.floor.surfaceOption;
    }
    renderGroupedMaterialOptions(activePack);
  }
}

function syncSurfaceMaterialSelect(kind, items, current) {
  const select = $(`#${kind}-material`);
  if (!select) return "";
  select.innerHTML = items.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  const materialId = items.some((item) => item.id === current)
    ? current
    : items[0]?.id || "";
  select.value = materialId;
  return materialId;
}

function surfaceRecommendationScore(item, recommendedId, activePack) {
  const scoreFor = item.scoreFor || {};
  const packScore = Number(scoreFor[activePack?.id] || 0);
  const styleScore = Number(scoreFor[activePack?.styleId] || 0);
  const directScore = item.id === recommendedId ? 100 : 0;
  return directScore + packScore + styleScore + Number(item.baseScore || 0);
}

function surfaceRecommendationReason(item, activePack, kind) {
  if (item.reason) return item.reason;
  const styleName = activePack?.styleLabel || "目前風格";
  const packName = activePack?.name || "";
  const source = packName ? `${styleName}「${packName}」` : styleName;
  return kind === "wall"
    ? `${source}先用牆面控制明度與背景份量，再讓家具成為主角。`
    : `${source}以地面決定主調，這個材質能接住家具色與採光。`;
}

const SURFACE_VARIANT_OPTIONS = Object.freeze({
  scandinavian: {
    wall: [
      { id: "sage", label: "鼠尾草礦物漆", color: "#D8DDCF", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", reason: "北歐風如果家具偏淺木，低彩度綠牆能增加層次，不會只剩白牆。", scoreFor: { scandinavian_2: 55 } },
      { id: "mineral_beige", label: "米灰礦物塗料", color: "#DDD2C1", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", reason: "用米灰牆降低白牆冷感，適合小坪數與自然光不足的房間。", scoreFor: { scandinavian: 18 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "人字拼橡木", color: "#C8A16F", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks033B.jpg", reason: "想讓北歐不那麼制式時，人字拼能保留木質溫度並增加精緻度。", scoreFor: { scandinavian_3: 65 } },
    ],
  },
  japanese: {
    wall: [
      { id: "sand", label: "砂岩感塗料", color: "#D8C6A9", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", reason: "砂岩色能接住榻榻米、藤編與紙燈，不會像純白牆那麼硬。", scoreFor: { japanese: 40 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "細拼淺木地板", color: "#D2B889", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks033B.jpg", reason: "細拼木紋讓日系空間比較有手作感，適合想要溫潤但不厚重的配置。", scoreFor: { japanese_1: 45 } },
    ],
  },
  modern_minimal: {
    wall: [
      { id: "greige", label: "灰米微水泥牆", color: "#BEB8AF", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Tiles008.jpg", reason: "現代簡約需要乾淨背景，灰米牆比白牆更能襯出黑金屬與石材。", scoreFor: { modern_minimal_2: 70 } },
    ],
    floor: [
      { id: "microcement", label: "霧面微水泥地坪", color: "#9B9992", materialPreview: "/static/surface_assets/tile/ccity-CAL288001.png", reason: "微水泥適合俐落線條與低彩度家具，比木地板更有都會感。", scoreFor: { modern_minimal: 35, modern_minimal_2: 60 } },
    ],
  },
  cream: {
    wall: [
      { id: "mineral_beige", label: "奶茶礦物塗料", color: "#E7D8C3", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", reason: "奶油風需要暖底但不能太黃，奶茶礦物牆能讓白色家具有陰影層次。", scoreFor: { cream: 45 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "柔光人字木地板", color: "#DEC393", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-Planks033B.jpg", reason: "柔光人字拼比一般淺橡木更有精緻感，適合奶油風的圓角家具。", scoreFor: { cream_3: 55 } },
    ],
  },
  industrial: {
    wall: [
      { id: "greige", label: "斑駁灰泥牆", color: "#8E8A82", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Tiles009.jpg", reason: "工業風不一定要全黑，灰泥牆能保留粗獷但讓空間不壓迫。", scoreFor: { industrial_1: 50 } },
    ],
    floor: [
      { id: "walnut", label: "深胡桃木地板", color: "#76583E", materialPreview: "/static/surface_assets/_import_all/cc0-wood-textures/ambientcg-WoodFloor039.jpg", reason: "深木地板能平衡鐵件與水泥，讓工業風比較像住宅而不是展場。", scoreFor: { industrial_2: 48 } },
    ],
  },
  american: {
    wall: [
      { id: "mineral_beige", label: "暖米礦物漆", color: "#E5D8C4", materialPreview: "/static/surface_assets/wall_materials_20260708/ambientcg-wall-clean-Plaster006.jpg", reason: "美式家具份量較重，暖米牆能柔化線板與深木色。", scoreFor: { american: 30 } },
    ],
    floor: [
      { id: "marble", label: "柔紋石材地坪", color: "#DDD2BF", materialPreview: "/static/surface_assets/tile/ccity-CAL330121.png", reason: "想做輕奢美式時，柔紋石材比固定木地板更有正式感。", scoreFor: { american_3: 52 } },
    ],
  },
});

function materialOptionsForStyle(styleId, kind, baseOptions) {
  const merged = new Map((baseOptions || []).map((item) => [item.id, item]));
  for (const item of SURFACE_VARIANT_OPTIONS[styleId]?.[kind] || []) {
    merged.set(item.id, { ...(merged.get(item.id) || {}), ...item });
  }
  return [...merged.values()];
}

function renderGroupedMaterialOptions(activePack) {
  const options = STYLE_MATERIAL_OPTIONS[state.activeStyleId]
    || STYLE_MATERIAL_OPTIONS[activePack?.styleId]
    || {};
  const render = (kind, host) => {
    if (!host) return;
    const recommendedId = activePack?.[kind]?.surfaceOption;
    const items = materialOptionsForStyle(activePack?.styleId || state.activeStyleId, kind, options[kind]).sort((left, right) =>
      surfaceRecommendationScore(right, recommendedId, activePack)
      - surfaceRecommendationScore(left, recommendedId, activePack)
    );
    const current = $(`#${kind}-material`)?.value;
    const selectedMaterial = syncSurfaceMaterialSelect(kind, items, current);
    host.innerHTML = items.map((item) => `
      <button type="button"
        data-surface-kind="${escapeHtml(kind)}"
        data-surface-material="${escapeHtml(item.id)}"
        data-surface-color="${escapeHtml(item.color || "")}"
        data-material-preview="${escapeHtml(item.materialPreview || "")}"
        data-style-card-recommended="${item.id === recommendedId ? "true" : "false"}"
        title="${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}"
        class="${item.id === selectedMaterial ? "is-active" : ""}">
        <span class="rp-material-preview" style="background:${escapeHtml(item.color || "#ddd")};${item.materialPreview ? `background-image:url('${escapeHtml(item.materialPreview)}')` : ""}"></span>
        <strong>${escapeHtml(item.label)}${item.id === recommendedId ? " · 此色卡推薦" : ""}</strong>
        <small>${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}</small>
      </button>
    `).join("");
  };
  render("wall", element.wallMaterialGrouped);
  render("floor", element.floorMaterialGrouped);
}

function stylePackByIdSafe(packId) {
  return STYLE_PACKS.find((pack) => pack.id === packId) || null;
}

async function ensureAutomaticSoftDecor(pack) {
  const targetRooms = state.rooms.length
    ? state.rooms
    : [{ id: state.selectedRoomId || "default" }];
  for (const room of targetRooms) {
    const result = await api("/api/scene/decorate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        style: pack.styleId,
        floorplan_editor: confirmedFloorplanEditor(),
        placement_room_id: room.id,
        scene_objects: state.sceneData.scene_objects || [],
      }),
    });
    state.sceneData.scene_objects = result.scene_objects;
  }
  const failed = (state.sceneData.scene_objects || []).filter(
    (item) => item.auto_decor_role && item.placement_failed,
  );
  if (failed.length) {
    throw new Error(`軟裝配置未通過家具引擎：${failed
      .map((item) => item.name_zh_raw || item.auto_decor_role)
      .join("、")}`);
  }
}

async function applyStylePackToScene(pack) {
  if (!pack || !state.sceneData) return;
  const revision = ++styleApplyRevision;
  const roomSurfaceOverrides = JSON.parse(JSON.stringify(
    state.sceneData.surface_overrides || [],
  ));
  const existingMaterialBoundary = state.sceneData.material_boundary || null;
  if (state.activeStylePackId) {
    state.styleHistory.push({
      packId: state.activeStylePackId,
      surfaceState: JSON.parse(JSON.stringify(state.surfaceState)),
    });
  }
  const previousSceneStyle = state.sceneData.style?.style_id;
  state.activeStylePackId = pack.id;
  state.activeStyleId = pack.styleId;
  state.surfaceState = applyStylePack(state.surfaceState, pack);
  state.sceneData.surface_overrides = roomSurfaceOverrides;
  state.sceneData.material_boundary = existingMaterialBoundary;
  state.materialBoundary = existingMaterialBoundary;
  const scopeControl = $("#surface-scope");
  if (scopeControl) scopeControl.value = "house";
  state.sceneData.style = {
    ...(state.sceneData.style || {}),
    style_id: pack.styleId,
    style_name_zh: pack.styleLabel,
    palette_hex: pack.palette,
    pbr: {
      wall: pack.wall.pbr,
      floor: pack.floor.pbr,
      furniture: pack.furniture.pbr,
    },
    furniture_rules: pack.furnitureRules,
    decor_rules: pack.decorRules,
    placement_rules: pack.placementRules,
    lighting: pack.lighting,
    rendering: pack.rendering,
  };
  state.sceneData.style_card = {
    card_id: pack.id,
    name_zh: pack.name,
    palette_hex: pack.palette,
    source_image: pack.sourceImage,
  };
  state.sceneData.design_choices = state.sceneData.design_choices || {};
  state.sceneData.design_choices.wall_color_hex = pack.wall.color;
  state.sceneData.design_choices.wall_option = resolveSurfaceOption(
    state.sceneData.surface_catalog,
    "wall",
    pack.wall.surfaceOption,
  );
  state.sceneData.design_choices.floor_color_hex = pack.floor.color;
  state.sceneData.design_choices.floor_option = resolveSurfaceOption(
    state.sceneData.surface_catalog,
    "floor",
    pack.floor.surfaceOption,
  );
  const applyFurnitureMaterials = () => state.sceneData.scene_objects.forEach((item) => {
    const locks = state.surfaceState.furniture.find((candidate) => candidate.id === item.furniture_id);
    if (locks?.styleLocked) return;
    item.material_override = {
      color: pack.furniture.color,
      accent: pack.furniture.accent,
      pbr: pack.furniture.pbr,
    };
  });
  applyFurnitureMaterials();
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  renderStyleControls();
  element.realisticStatus.textContent = `正在套用「${pack.styleLabel}／${pack.name}」的牆面、地板與燈光…`;
  await realisticViewer.loadScene(state.sceneData);
  if (revision !== styleApplyRevision) return;
  realisticViewer.setViewMode("orbit");
  element.realisticStatus.textContent = `已套用「${pack.styleLabel}／${pack.name}」的牆面、地板、PBR 與燈光；家具搭配更新中。`;
  scheduleSave("realistic_3d");

  try {
    await ensureAutomaticSoftDecor(pack);
    if (revision !== styleApplyRevision) return;
    if (previousSceneStyle !== pack.styleId) {
      await replaceUnlockedFurnitureForStyle(pack);
    }
    if (revision !== styleApplyRevision) return;
    applyFurnitureMaterials();
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    await realisticViewer.loadScene(state.sceneData);
    if (revision !== styleApplyRevision) return;
    realisticViewer.setViewMode("orbit");
  } catch (error) {
    console.warn(error);
    element.realisticStatus.textContent = `牆面、地板與燈光已套用；家具或軟裝更新失敗：${errorMessage(error)}`;
    scheduleSave("realistic_3d");
    return;
  }
  await evaluateCeilingConflicts();
  element.realisticStatus.textContent = `${pack.styleLabel}／${pack.name}：牆、地板、未鎖定家具與環境光已同步；軟裝與擺放規則已載入，新增物件仍須通過家具引擎配置。`;
  element.realisticStatus.textContent = `已完成「${pack.styleLabel}／${pack.name}」：牆面、地板、PBR、燈光與未鎖定家具均已同步。`;
  scheduleSave("realistic_3d");
}

async function applySurfaceOverrides({ userInitiated = false } = {}) {
  const scope = $("#surface-scope").value;
  const selectedRoom = state.rooms.find((item) => item.id === state.selectedRoomId) || state.rooms[0];
  if (userInitiated && scope !== "house" && selectedRoom && isCirculationRoom(selectedRoom)
    && !circulationStyleIsOverridden(selectedRoom)) {
    const livingRoom = livingRoomForCirculation();
    const approved = window.confirm(
      `走道目前沿用「${livingRoom?.label || "客廳"}」的風格與材質。改為獨立風格會讓動線出現視覺差異，並在第 6 步重新檢查銜接。要繼續嗎？`,
    );
    if (!approved) {
      element.realisticStatus.textContent = "已保留走道與客廳一致的風格與材質。";
      return;
    }
    const requirement = state.roomRequirementModel?.roomRequirements?.[selectedRoom.id];
    if (requirement) requirement.circulationStyleOverrideApproved = true;
  }
  state.surfaceState.wall = {
    ...(state.surfaceState.wall || {}),
    color: $("#wall-color").value,
    material: $("#wall-material").value,
    styleLocked: true,
    scope,
  };
  state.surfaceState.floor = {
    ...(state.surfaceState.floor || {}),
    color: $("#floor-color").value,
    material: $("#floor-material").value,
    styleLocked: true,
    scope,
  };
  if (scope === "house") {
    state.sceneData.design_choices.wall_color_hex = state.surfaceState.wall.color;
    state.sceneData.design_choices.floor_color_hex = state.surfaceState.floor.color;
    state.sceneData.design_choices.wall_option = resolveSurfaceOption(
      state.sceneData.surface_catalog,
      "wall",
      state.surfaceState.wall.material,
    );
    state.sceneData.design_choices.floor_option = resolveSurfaceOption(
      state.sceneData.surface_catalog,
      "floor",
      state.surfaceState.floor.material,
    );
    state.sceneData.surface_overrides = [];
  } else {
    const room = selectedRoom;
    if (!room) {
      element.realisticStatus.textContent = "請先選取要套用材質的房間。";
      return;
    }
    const center = planCenterCm();
    const override = {
      room_id: room.id,
      room_label: room.label,
      room_bounds_cm: {
        minX: Math.min(...room.polygon_cm.map((point) => point.x)) - center.x,
        maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - center.x,
        minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - center.y,
        maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - center.y,
      },
      room_polygon_cm: room.polygon_cm.map((point) => ({
        x: point.x - center.x,
        z: point.y - center.y,
      })),
      wall_color_hex: state.surfaceState.wall.color,
      floor_color_hex: state.surfaceState.floor.color,
      wall_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "wall",
        state.surfaceState.wall.material,
      ),
      floor_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "floor",
        state.surfaceState.floor.material,
      ),
    };
    state.sceneData.surface_overrides = [
      ...(state.sceneData.surface_overrides || [])
        .filter((item) => item.room_id !== room.id),
      override,
    ];
  }
  await realisticViewer.loadScene(state.sceneData);
  realisticViewer.setViewMode("orbit");
  element.realisticStatus.textContent = `已套用並鎖定${$("#surface-scope option:checked").textContent}的牆面與地板材質。`;
  scheduleSave("realistic_3d");
}

function toggleMaterialBoundary() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId) || state.rooms[0];
  if (!room) return;
  const planCenter = planCenterCm();
  const bounds = {
    minX: Math.min(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
    maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
    minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
    maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
  };
  const direction = $("#material-boundary-direction").value;
  const ratio = Number($("#material-boundary-position").value) / 100;
  const splitX = bounds.minX + (bounds.maxX - bounds.minX) * ratio;
  const splitZ = bounds.minZ + (bounds.maxZ - bounds.minZ) * ratio;
  state.materialBoundary = {
    surface: "floor",
    roomId: room.id,
    direction,
    ratio,
    line_cm: direction === "horizontal"
      ? [
          { x: bounds.minX, y: splitZ },
          { x: bounds.maxX, y: splitZ },
        ]
      : [
          { x: splitX, y: bounds.minZ },
          { x: splitX, y: bounds.maxZ },
        ],
    room_bounds_cm: bounds,
    materials: ["current-floor", "secondary-floor"],
  };
  if (state.sceneData) state.sceneData.material_boundary = state.materialBoundary;
  $("#material-boundary-status").textContent =
    `已在${room.label}建立${direction === "horizontal" ? "水平" : "垂直"}界線，位置 ${Math.round(ratio * 100)}%。`;
  if (state.sceneData) realisticViewer.loadScene(state.sceneData);
  scheduleSave("realistic_3d");
}

function removeMaterialBoundary() {
  state.materialBoundary = null;
  if (state.sceneData) {
    state.sceneData.material_boundary = null;
    realisticViewer.loadScene(state.sceneData);
  }
  $("#material-boundary-status").textContent = "已移除混搭材質界線。";
  scheduleSave("realistic_3d");
}

function roomLabelAtPlanPoint(point) {
  const room = state.rooms.find((candidate) => {
    const xs = candidate.polygon_cm.map((vertex) => vertex.x);
    const ys = candidate.polygon_cm.map((vertex) => vertex.y);
    return point.x >= Math.min(...xs)
      && point.x <= Math.max(...xs)
      && point.y >= Math.min(...ys)
      && point.y <= Math.max(...ys);
  });
  return room?.label || "全屋";
}

async function evaluateCeilingConflicts() {
  const ceiling = CEILING_STYLES.find((item) => item.id === element.ceilingStyle.value)
    || CEILING_STYLES[0];
  const light = LIGHT_STYLES.find((item) => item.id === element.lightStyle.value)
    || LIGHT_STYLES[0];
  const roomHeightCm = Number(
    state.sceneData?.floorplan?.room_height_cm
    || state.confirmedFloorplan?.floorplan?.room_height_cm
    || 270,
  );
  const planCenter = planCenterCm();
  if (state.sceneData) {
    state.sceneData.design_choices = state.sceneData.design_choices || {};
    state.sceneData.design_choices.ceiling_style = ceiling.id;
    state.sceneData.design_choices.ceiling_drop_cm = ceiling.dropCm;
    state.sceneData.design_choices.light_style = light.id;
  }
  const result = detectCeilingConflicts({
    ceilingStyle: ceiling.id,
    roomHeightCm,
    beams: state.structures.beams.map((beam, index) => {
      const topCm = Number(beam.top_cm) || roomHeightCm;
      const heightCm = Number(beam.height_cm ?? beam.thickness_cm) || 30;
      const midpoint = {
        x: (Number(beam.start?.x || 0) + Number(beam.end?.x || 0)) / 2,
        y: (Number(beam.start?.y || 0) + Number(beam.end?.y || 0)) / 2,
      };
      return {
        id: beam.id,
        kind: "beam",
        label: `樑 ${index + 1}`,
        topCm,
        bottomCm: topCm - heightCm,
        estimated: beam.estimated === true || beam.top_cm == null,
        roomLabel: roomLabelAtPlanPoint(midpoint),
      };
    }),
    cabinets: state.sceneData?.scene_objects
      ?.filter((item) => ["wardrobe", "cabinet", "bookcase"].includes(item.normalized_type))
      .map((item) => {
        const position = item.position_cm || {};
        return {
          id: item.furniture_id,
          kind: "cabinet",
          label: item.name_zh_raw || "櫃體",
          topCm: Number(item.size_cm?.height || 0),
          roomLabel: roomLabelAtPlanPoint({
            x: planCenter.x + Number(position.x || 0),
            y: planCenter.y + Number(position.z || 0),
          }),
        };
      }) || [],
    lights: [{
      id: light.id,
      kind: "light",
      label: light.label,
      requiredPlenumCm: light.installationDepthCm,
      roomLabel: "全屋",
    }],
  });
  element.ceilingConflicts.innerHTML = result.conflicts.length
    ? result.conflicts.map((conflict) => `
      <article class="rp-conflict-item">
        <strong>${escapeHtml(conflict.location)}：${escapeHtml(conflict.objectLabel)}</strong>
        <p>${escapeHtml(conflict.reason)} ${escapeHtml(conflict.impact)}</p>
        <p>AI 建議：${escapeHtml(conflict.recommendations.join("；"))}。套用前會再次做幾何驗證。</p>
      </article>
    `).join("")
    : `<p>完成天花高度 ${result.finishedHeightCm} cm，目前未偵測到樑、櫃體或燈具衝突。</p>`;
  if (state.sceneData && state.workflow?.currentStep === "realistic_3d") {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
  }
}

function currentSceneVersion() {
  return [
    state.sceneData?.scene_id || "scene",
    `scheme-${activeSchemeId()}`,
    `revision-${Number(state.project?.revision || 0)}`,
    state.activeStylePackId || "no-style",
  ].join(":");
}

function renderProposalPaletteSelection() {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId)
    || STYLE_PACKS[0];
  const options = STYLE_PACKS.filter((item) => item.styleId === activePack.styleId);
  const selectedId = state.proposalReview.confirmedStyleCardId;
  element.proposalPaletteGrid.innerHTML = options.map((pack) => `
    <button type="button" data-proposal-style-card="${escapeHtml(pack.id)}"
      class="${pack.id === selectedId ? "is-active" : ""}"
      aria-pressed="${pack.id === selectedId}">
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}"
        alt="${escapeHtml(`${pack.styleLabel} ${pack.name}色卡預覽`)}" loading="lazy">
      <span class="rp-style-swatches">${pack.palette
        .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
        .join("")}</span>
      <strong>${escapeHtml(pack.name)}</strong>
      <small>${escapeHtml(pack.furniture.displayHighlights.join("、"))}</small>
    </button>
  `).join("");
  element.proposalPaletteStatus.textContent = selectedId
    ? `已選「${STYLE_PACKS.find((item) => item.id === selectedId)?.name || "色卡"}」；第 8 步將以這張色卡送往遠端。`
    : "請選擇一張色卡後，再鎖定生圖視角。";
}

function selectProposalPalette(cardId) {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId)
    || STYLE_PACKS[0];
  const pack = STYLE_PACKS.find((item) => item.id === cardId);
  if (!pack || pack.styleId !== activePack.styleId) return;
  state.proposalReview.confirmedStyleCardId = pack.id;
  renderProposalPaletteSelection();
  renderProposalSummary();
  scheduleSave("proposal_review");
}

function renderProposalSummary() {
  const pack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const selectedPalette = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  const furniture = state.sceneData?.scene_objects || [];
  const customPreferenceCount = Object.values(state.visualAnswers || {}).filter(
    (answer) => String(answer?.custom || "").trim(),
  ).length;
  const rows = [
    ["方案", `方案 ${activeSchemeId()}`],
    ["色卡", selectedPalette ? `${selectedPalette.styleLabel}／${selectedPalette.name}` : (pack ? `${pack.styleLabel}／尚未選擇色卡` : "尚未選擇")],
    ["家具", `${furniture.filter((item) => !item.placement_failed).length} 件已配置`],
    ["結構", `牆 ${state.structures.walls.length}、門 ${state.structures.doors.length}、窗 ${state.structures.windows.length}`],
    ["表面", state.surfaceState.wall?.styleLocked && state.surfaceState.floor?.styleLocked ? "牆與地板已鎖定" : "使用目前 StylePack"],
    ["逐房需求", `${state.rooms.length} 個房間／${customPreferenceCount} 項補充條件`],
  ];
  element.proposalReviewSummary.innerHTML = rows.map(([label, value]) => `
    <div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>
  `).join("");
}

async function prepareProposalReview() {
  if (!state.sceneData) return;
  renderProposalSummary();
  renderProposalPaletteSelection();
  await proposalViewer.loadScene(state.sceneData);
  const saved = state.proposalReview.masterView?.camera;
  if (saved) proposalViewer.setCameraState(saved);
  else {
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
  }
  proposalViewer.lockRenderCamera(false);
  // Preserve the user's acknowledgement when autosave redraws the same review.
  const contentConfirmed = element.proposalContentConfirmed.checked || Boolean(saved);
  element.proposalContentConfirmed.checked = contentConfirmed;
  element.masterViewStatus.textContent = saved
    ? "已載入上次鎖定視角；調整後請重新鎖定。"
    : "尚未鎖定比較視角。";
  if (saved) renderProposalRoomViewPanel();
}

function lockMasterRenderView() {
  const contentConfirmed = document.querySelector("#proposal-content-confirmed")?.checked === true;
  if (!contentConfirmed) {
    element.masterViewStatus.textContent = "請先確認家具、結構、材質、色卡與需求。";
    return;
  }
  if (activeScheme()?.stale || !activeScheme()?.sceneData) {
    element.masterViewStatus.textContent =
      `方案 ${activeSchemeId()} 尚未完成最新的 2D／3D 重算，不能鎖定。`;
    return;
  }
  const visualProgress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  const confirmedRoomRequirements = state.rooms.every((room) => (
    state.roomRequirementModel.roomRequirements?.[room.id]?.confirmed === true
  ));
  if (!visualProgress.ready && !confirmedRoomRequirements) {
    element.requirementsError.textContent =
      `逐房極與極尚有 ${visualProgress.total - visualProgress.completed} 題未處理。`;
    showQuestionnaireStage("rooms");
    return;
  }
  if (!finishesGate(state.questionnaireFinishes).ready) {
    element.requirementsError.textContent =
      "請先確認風格、牆壁、地板、天花板與照明。";
    showQuestionnaireStage("finishes");
    return;
  }
  if (!state.sceneData || !state.activeStylePackId) {
    element.masterViewStatus.textContent = "缺少已確認的場景或色卡，請返回第 6 步。";
    return;
  }
  if (!state.proposalReview.confirmedStyleCardId) {
    element.masterViewStatus.textContent = "請先選擇一張同風格色卡，作為遠端生圖的色彩基準。";
    return;
  }
  if (roomSchemeSelectionRequired() && !allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) {
    element.masterViewStatus.textContent = "請先回第 6 步完成每個房間的 A/B 方案選擇。";
    return;
  }
  state.designSchemes.configuration_snapshot = state.designSchemes.configuration_snapshot
    || configurationSnapshot();
  const camera = proposalViewer.getCameraState();
  if (camera.camera_type !== "perspective") {
    element.masterViewStatus.textContent = "遠端室內渲染需要透視視角，請改用「室內環視」或「室內透視」。";
    return;
  }
  const lockedAt = new Date().toISOString();
  state.proposalReview.masterView = {
    camera,
    scheme_id: activeSchemeId(),
    scene_version: currentSceneVersion(),
    style_card_id: state.proposalReview.confirmedStyleCardId,
    configuration_snapshot_id: state.designSchemes.configuration_snapshot.created_at,
    locked_at: lockedAt,
  };
  state.designSchemes.locked_scheme_id = activeSchemeId();
  state.proposalReview.roomViews = {};
  proposalRoomPreviewCache.clear();
  state.proposalReview.jobs = [];
  proposalViewer.lockRenderCamera(true);
  const completed = state.workflow.complete("proposal_review", {
    confirmed: true,
    masterView: state.proposalReview.masterView,
  });
  if (!completed) {
    element.masterViewStatus.textContent = "視角資料不完整，尚未鎖定。";
    proposalViewer.lockRenderCamera(false);
    return;
  }
  try {
    renderSchemeControls();
  } catch (error) {
    console.warn("Unable to refresh scheme controls after locking the master view.", error);
  }
  element.masterViewStatus.textContent = "完整方案已鎖定；請繼續逐房選擇渲染視角。";
  scheduleSave("proposal_review");
  state.selectedProposalRoomId = state.rooms[0]?.id || null;
  state.selectedProposalRoomCandidateIndex = 0;
  renderProposalRoomViewPanel();
  if (state.selectedProposalRoomId) selectProposalRoomView(state.selectedProposalRoomId);
}

function renderPaletteOptions() {
  const selectedPack = STYLE_PACKS.find(
    (item) => item.id === state.proposalReview.confirmedStyleCardId,
  );
  if (!selectedPack) {
    element.paletteRenderOptions.innerHTML = "<p class=\"rp-field-hint\">請返回第 7 步選擇色卡。</p>";
    return;
  }
  element.paletteRenderOptions.innerHTML = [selectedPack].map((pack) => `
    <label>
      <input type="checkbox" value="${escapeHtml(pack.id)}" data-render-style-card
        checked disabled />
      <span><strong>${escapeHtml(pack.name)}</strong><br><small>${pack.palette.map(escapeHtml).join(" · ")}</small></span>
    </label>
  `).join("");
}

function roomCameraSuggestion(room) {
  const polygon = room?.polygon_cm || [];
  const planWidth = Number(state.sceneData?.floorplan?.width_cm || 420);
  const planDepth = Number(state.sceneData?.floorplan?.depth_cm || 360);
  const xs = polygon.map((point) => Number(point.x));
  const zs = polygon.map((point) => Number(point.y));
  const centerX = (xs.reduce((sum, value) => sum + value, 0) / Math.max(xs.length, 1)) - planWidth / 2;
  const centerZ = (zs.reduce((sum, value) => sum + value, 0) / Math.max(zs.length, 1)) - planDepth / 2;
  const width = xs.length ? Math.max(...xs) - Math.min(...xs) : 320;
  const depth = zs.length ? Math.max(...zs) - Math.min(...zs) : 280;
  return {
    camera_type: "perspective",
    view_mode: "orbit",
    preset: "room",
    position_cm: [centerX + width * 0.28, 145, centerZ + depth * 0.28],
    target_cm: [centerX, 82, centerZ],
    up: [0, 1, 0],
    fov_deg: 58,
    zoom: 1,
  };
}

function proposalRoomCameraCandidates(room) {
  const base = roomCameraSuggestion(room);
  const [x, y, z] = base.position_cm;
  const [targetX, targetY, targetZ] = base.target_cm;
  return [
    { label: "入口視角", note: "從主要進入方向觀看", camera: base },
    {
      label: "對角視角",
      note: "完整呈現空間深度",
      camera: { ...base, position_cm: [targetX - (x - targetX), y, targetZ - (z - targetZ)] },
    },
    {
      label: "活動視角",
      note: "聚焦主要使用區域",
      camera: { ...base, position_cm: [targetX + (z - targetZ), y, targetZ - (x - targetX)] },
    },
  ];
}

function proposalRoomPreviewKey(room) {
  return `${currentSceneVersion()}:${room.id}`;
}

async function ensureProposalRoomCandidatePreviews(room) {
  if (!room || !state.proposalReview.masterView) return;
  const key = proposalRoomPreviewKey(room);
  if (proposalRoomPreviewCache.has(key)) return;
  proposalRoomPreviewCache.set(key, "loading");
  const previousCamera = proposalViewer.getCameraState();
  try {
    const previews = proposalRoomCameraCandidates(room).map((choice) => {
      proposalViewer.setCameraState(choice.camera);
      return proposalViewer.capturePng();
    });
    proposalRoomPreviewCache.set(key, previews);
  } catch {
    proposalRoomPreviewCache.delete(key);
  } finally {
    proposalViewer.setCameraState(previousCamera);
  }
  if (String(state.selectedProposalRoomId) === String(room.id)) {
    renderProposalRoomViewPanel();
  }
}

function ensureProposalRoomViewPanel() {
  let panel = $("#proposal-room-view-lock");
  if (panel) return panel;
  const sidebar = $("#proposal-review-step .rp-control-pane") || $("#proposal-review-step");
  if (!sidebar) return null;
  panel = document.createElement("section");
  panel.id = "proposal-room-view-lock";
  panel.className = "rp-editor-box rp-render-view-lock";
  panel.innerHTML = `
    <span class="eyebrow">ROOM VIEWS</span>
    <h3>逐房選擇渲染視角</h3>
    <p>每個空間先提供 3 個候選視角。選一個後可在左側微調，再鎖定為該房唯一的生圖視角。</p>
    <div id="proposal-room-view-list" class="rp-render-room-list"></div>
    <div id="proposal-room-view-candidates" class="rp-view-candidate-list" aria-live="polite"></div>
    <button id="lock-proposal-room-view" type="button" class="secondary-action">鎖定目前房間視角</button>
    <button id="confirm-proposal-room-views" type="button" class="primary-action">確認所有房間視角並進入第 8 步</button>
    <p id="proposal-room-view-status" class="rp-field-hint" aria-live="polite"></p>
  `;
  sidebar.append(panel);
  panel.addEventListener("click", (event) => {
    const roomButton = event.target.closest("[data-proposal-room]");
    if (roomButton) selectProposalRoomView(roomButton.dataset.proposalRoom);
    const candidateButton = event.target.closest("[data-proposal-room-candidate]");
    if (candidateButton) selectProposalRoomCandidate(Number(candidateButton.dataset.proposalRoomCandidate));
  });
  $("#lock-proposal-room-view")?.addEventListener("click", lockSelectedProposalRoomView);
  $("#confirm-proposal-room-views")?.addEventListener("click", confirmProposalRoomViews);
  return panel;
}

function renderProposalRoomViewPanel() {
  const panel = ensureProposalRoomViewPanel();
  if (!panel) return;
  panel.hidden = !state.proposalReview.masterView;
  if (panel.hidden) return;
  const roomId = state.selectedProposalRoomId || state.rooms[0]?.id || null;
  state.selectedProposalRoomId = roomId;
  const list = $("#proposal-room-view-list");
  const candidates = $("#proposal-room-view-candidates");
  const status = $("#proposal-room-view-status");
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  list.innerHTML = state.rooms.map((item) => {
    const saved = state.proposalReview.roomViews[item.id];
    return `<button type="button" data-proposal-room="${escapeHtml(item.id)}"
      class="${String(item.id) === String(roomId) ? "is-active" : ""}">
      <span>${escapeHtml(item.label || "未命名空間")}</span>
      <small>${saved ? "視角已鎖定" : "尚未鎖定"}</small>
    </button>`;
  }).join("");
  if (!room) {
    candidates.innerHTML = "";
    status.textContent = "尚無可選擇的房間。";
    return;
  }
  const choices = proposalRoomCameraCandidates(room);
  const previewState = proposalRoomPreviewCache.get(proposalRoomPreviewKey(room));
  const activeIndex = state.selectedProposalRoomCandidateIndex || 0;
  candidates.innerHTML = choices.map((choice, index) => `<button type="button"
    data-proposal-room-candidate="${index}" class="${index === activeIndex ? "is-active" : ""}">
    ${Array.isArray(previewState) && previewState[index]
      ? `<img src="${previewState[index]}" alt="${escapeHtml(`${room.label} ${choice.label}`)}" loading="lazy">`
      : `<span class="rp-view-candidate-placeholder">正在建立 3D 構圖</span>`}
    <strong>${escapeHtml(choice.label)}</strong><small>${escapeHtml(choice.note)}</small>
  </button>`).join("");
  const completed = Object.keys(state.proposalReview.roomViews).length;
  status.textContent = `${room.label}：選一個候選視角後可在左側微調。已鎖定 ${completed} / ${state.rooms.length} 個房間。`;
  if (!Array.isArray(previewState) && previewState !== "loading") {
    void ensureProposalRoomCandidatePreviews(room);
  }
}

function selectProposalRoomView(roomId) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  if (!room) return;
  state.selectedProposalRoomId = room.id;
  const saved = state.proposalReview.roomViews[room.id];
  const choices = proposalRoomCameraCandidates(room);
  state.selectedProposalRoomCandidateIndex = Number(saved?.candidate_index ?? 0);
  proposalViewer.lockRenderCamera(false);
  proposalViewer.setCameraState(saved?.camera || choices[state.selectedProposalRoomCandidateIndex]?.camera || choices[0].camera);
  renderProposalRoomViewPanel();
}

function selectProposalRoomCandidate(index) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedProposalRoomId));
  if (!room || !Number.isInteger(index)) return;
  const choices = proposalRoomCameraCandidates(room);
  const choice = choices[index];
  if (!choice) return;
  state.selectedProposalRoomCandidateIndex = index;
  proposalViewer.lockRenderCamera(false);
  proposalViewer.setCameraState(choice.camera);
  renderProposalRoomViewPanel();
}

function lockSelectedProposalRoomView() {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedProposalRoomId));
  if (!room) return;
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera: proposalViewer.getCameraState(),
    candidate_index: state.selectedProposalRoomCandidateIndex,
    scene_version: state.proposalReview.masterView?.scene_version,
    saved_at: new Date().toISOString(),
  };
  scheduleSave("proposal_review");
  renderProposalRoomViewPanel();
}

function confirmProposalRoomViews() {
  const missing = state.rooms.filter((room) => !state.proposalReview.roomViews[room.id]);
  const status = $("#proposal-room-view-status");
  if (missing.length) {
    status.textContent = `尚有 ${missing.map((room) => room.label).join("、")} 未鎖定視角。`;
    selectProposalRoomView(missing[0].id);
    return;
  }
  proposalViewer.lockRenderCamera(true);
  scheduleSave("proposal_review");
  goTo("ai_render");
}

function renderRoomViewList() {
  element.renderRoomList.innerHTML = state.rooms.map((room) => {
    const saved = state.proposalReview.roomViews[room.id];
    return `
      <button type="button" data-render-room="${escapeHtml(room.id)}"
        class="${room.id === state.selectedRenderRoomId ? "is-active" : ""}">
        <span>${escapeHtml(room.label || "未命名空間")}</span>
        <small>${saved ? "視角已保存" : "使用建議視角"}</small>
      </button>
    `;
  }).join("");
}

function selectRenderRoom(roomId) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  state.selectedRenderRoomId = room.id;
  const saved = state.proposalReview.roomViews[room.id]?.camera;
  aiRenderViewer.lockRenderCamera(false);
  aiRenderViewer.setCameraState(saved || roomCameraSuggestion(room));
  element.aiRenderViewTitle.textContent = `${room.label || "未命名空間"} · 渲染視角`;
  element.aiRenderStatus.textContent = saved
    ? "已載入保存視角；可以小幅調整後重新保存。"
    : "已套用房間建議視角；請確認主要家具與布局清楚可見。";
  renderRoomViewList();
}

function saveSelectedRoomView() {
  const room = state.rooms.find((item) => item.id === state.selectedRenderRoomId);
  if (!room) return;
  const camera = aiRenderViewer.getCameraState();
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera,
    scene_version: state.proposalReview.masterView?.scene_version,
    saved_at: new Date().toISOString(),
  };
  element.aiRenderStatus.textContent = `${room.label || "此房間"}視角已保存。`;
  renderRoomViewList();
  scheduleSave("ai_render");
}

function renderRemoteJobs() {
  element.remoteRenderJobs.innerHTML = state.proposalReview.jobs.map((job) => `
    <article>
      <strong>${escapeHtml(job.label || job.job_id || "渲染任務")}</strong>
      <span>${escapeHtml(job.status || "queued")}</span>
    </article>
  `).join("");
}

function renderPaletteResults() {
  const paletteJobs = state.proposalReview.jobs.filter(
    (job) => job.mode === "palette_comparison",
  );
  element.paletteRenderResults.innerHTML = paletteJobs.map((job) => {
    const imageUrl = job.image_url || job.output_url || job.preview_url;
    const styleCardId = job.style_card_id || job.styleCardId || "";
    return `
      <label class="rp-render-result">
        ${imageUrl
          ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(job.label || styleCardId)} 色卡渲染" />`
          : `<span class="rp-render-placeholder">${escapeHtml(job.status || "等待遠端渲染")}</span>`}
        <span>
          <input type="radio" name="confirmed-render-style" value="${escapeHtml(styleCardId)}"
            ${styleCardId === state.proposalReview.confirmedStyleCardId ? "checked" : ""} />
          ${escapeHtml(job.label || styleCardId || "色卡任務")}
        </span>
      </label>
    `;
  }).join("");
  element.confirmRenderPalette.hidden = paletteJobs.length === 0;
}

function confirmRenderPalette() {
  const selected = $('input[name="confirmed-render-style"]:checked');
  if (!selected?.value) {
    element.aiRenderStatus.textContent = "請先在比較結果中選擇一張色卡。";
    return;
  }
  state.proposalReview.confirmedStyleCardId = selected.value;
  element.roomRenderSection.hidden = false;
  state.selectedRenderRoomId = state.selectedProposalRoomId || state.rooms[0]?.id || null;
  if (state.selectedRenderRoomId) selectRenderRoom(state.selectedRenderRoomId);
  scheduleSave("ai_render");
  element.aiRenderStatus.textContent = "色卡已確認；將沿用第 7 步鎖定的逐房視角。";
}

async function prepareAiRender() {
  if (!state.sceneData || !state.proposalReview.masterView) return;
  await aiRenderViewer.loadScene(state.sceneData);
  aiRenderViewer.setCameraState(state.proposalReview.masterView.camera);
  aiRenderViewer.lockRenderCamera(true);
  renderPaletteOptions();
  renderRemoteJobs();
  renderPaletteResults();
  element.roomRenderSection.hidden = !state.proposalReview.confirmedStyleCardId;
  element.aiRenderProviderState.textContent = "正在檢查遠端服務…";
  try {
    const status = await api("/api/render-provider/status");
    element.aiRenderProviderState.textContent = status.configured
      ? `已連接 ${status.provider}`
      : "尚未設定遠端渲染服務";
  } catch {
    element.aiRenderProviderState.textContent = "無法取得遠端服務狀態";
  }
  if (state.selectedRenderRoomId) selectRenderRoom(state.selectedRenderRoomId);
  else {
    element.aiRenderViewTitle.textContent = "色卡比較視角";
    element.aiRenderStatus.textContent = "先建立色卡比較任務，確認後再逐房間保存視角。";
  }
}

function renderBriefSummaryRows(mode) {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const selectedCard = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  return [
    ["本次任務", mode === "palette_comparison" ? "代表房三張色卡測試" : "全房間最終生圖"],
    ["全屋風格", activePack ? `${activePack.styleLabel} / ${activePack.name}` : "未選擇"],
    ["最終配置", `${state.rooms.length} 個房間，${Object.keys(state.designSchemes.room_selections || {}).length} 個逐房方案選擇`],
    ["鎖定視角", `${Object.keys(state.proposalReview.roomViews || {}).length} / ${state.rooms.length} 個房間`],
    ["確認色卡", selectedCard ? selectedCard.name : "本次將比較三張同風格色卡"],
    ["問卷補充", Object.values(state.visualAnswers || {}).filter((answer) => String(answer?.custom || "").trim()).length
      ? "包含逐房使用者補充" : "沒有額外逐房文字"],
  ];
}

function renderBriefHasSpatialConflict(notes) {
  return /移(?:動|到)|搬|拆|打通|開放式|走道|門口|窗邊|牆|改格局|重新擺/.test(String(notes || ""));
}

function openRenderBriefDialog(mode) {
  if (!element.renderBriefDialog) return;
  pendingRenderBriefMode = mode;
  element.renderBriefSummary.innerHTML = renderBriefSummaryRows(mode).map(([label, value]) => (
    `<div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`
  )).join("");
  element.renderBriefNotes.value = "";
  element.renderBriefWarning.hidden = true;
  delete element.renderBriefWarning.dataset.acknowledged;
  if (typeof element.renderBriefDialog.showModal === "function") element.renderBriefDialog.showModal();
  else element.renderBriefDialog.setAttribute("open", "");
}

function closeRenderBriefDialog() {
  if (!element.renderBriefDialog) return;
  if (typeof element.renderBriefDialog.close === "function") element.renderBriefDialog.close();
  else element.renderBriefDialog.removeAttribute("open");
  pendingRenderBriefMode = null;
}

function confirmedRenderBrief(mode, notes) {
  const brief = {
    version: (state.proposalReview.renderBriefs || []).length + 1,
    mode,
    confirmed_at: new Date().toISOString(),
    user_notes: String(notes || "").trim(),
    spatial_override_warning: renderBriefHasSpatialConflict(notes),
    sources: {
      questionnaire: true,
      configuration_snapshot_id: state.designSchemes.configuration_snapshot?.created_at || null,
      room_views: Object.keys(state.proposalReview.roomViews || {}),
    },
  };
  state.proposalReview.renderBriefs = [...(state.proposalReview.renderBriefs || []), brief];
  return brief;
}

async function confirmRenderBriefAndSubmit() {
  const mode = pendingRenderBriefMode;
  if (!mode) return;
  const notes = element.renderBriefNotes.value;
  if (renderBriefHasSpatialConflict(notes) && !element.renderBriefWarning.dataset.acknowledged) {
    element.renderBriefWarning.hidden = false;
    element.renderBriefWarning.textContent = "這段文字可能與已鎖定的格局、家具或視角不一致，外部模型可能畫錯、遺漏家具或改變動線。再次按確認才會以使用者覆寫描述送出。";
    element.renderBriefWarning.dataset.acknowledged = "true";
    return;
  }
  const brief = confirmedRenderBrief(mode, notes);
  closeRenderBriefDialog();
  if (mode === "palette_comparison") await requestPaletteRenders(brief);
  else await submitRoomRenders(brief);
  scheduleSave("ai_render");
}

function renderRequestPayload(mode, styleCardIds, roomViews = [], renderBrief = null) {
  const roomRequirementsPayload = buildRoomRequirementsPayload(
    state.roomRequirementModel,
    {
      planGeometry: {
        rooms: state.rooms,
        structures: state.structures,
      },
      questionnaireVersion: state.visualCatalogVersion,
    },
  );
  return {
    schema_version: "1.0",
    mode,
    project_id: state.projectId,
    scheme_id: state.designSchemes.locked_scheme_id || activeSchemeId(),
    room_scheme_selections: state.designSchemes.room_selections || {},
    configuration_snapshot: state.designSchemes.configuration_snapshot,
    render_brief: renderBrief,
    scene_version: state.proposalReview.masterView?.scene_version,
    style_card_ids: styleCardIds,
    style_packs: styleCardIds.map((cardId) => {
      const pack = STYLE_PACKS.find((item) => item.id === cardId);
      return pack ? {
        card_id: pack.id,
        style_id: pack.styleId,
        style_label: pack.styleLabel,
        name: pack.name,
        palette_hex: pack.palette,
        wall: pack.wall,
        floor: pack.floor,
        furniture: pack.furniture,
        lighting: pack.lighting,
        rendering: pack.rendering,
      } : { card_id: cardId };
    }),
    scene: state.sceneData,
    agent_generation_handoff: refreshedAgentGenerationHandoff(roomRequirementsPayload),
    locks: {
      furniture: true,
      structure: true,
      surface_regions: true,
      style_card_id: mode === "room_final"
        ? state.proposalReview.confirmedStyleCardId
        : state.proposalReview.confirmedStyleCardId,
    },
    requirements: {
      basic: state.basicAnswers,
      visual_preferences: state.visualAnswers,
      finishes: state.questionnaireFinishes,
      room_requirements: roomRequirementsPayload.roomRequirements,
      ready_for_rag: roomRequirementsPayload.readyForRag,
    },
    room_surface_assignments: roomSurfaceAssignments(),
    master_view: state.proposalReview.masterView,
    room_views: roomViews,
    reference_png_data_url: aiRenderViewer.capturePng(),
  };
}

function refreshedAgentGenerationHandoff(roomRequirementsPayload) {
  const previous = state.sceneData?.agent_generation_handoff || {};
  const roomsById = new Map((previous.rooms || []).map((room) => [String(room.room_id), room]));
  const sceneObjectsByRoom = new Map();
  (state.sceneData?.scene_objects || []).forEach((item) => {
    const roomId = String(item.room_id || item.roomId || "");
    if (!sceneObjectsByRoom.has(roomId)) sceneObjectsByRoom.set(roomId, []);
    sceneObjectsByRoom.get(roomId).push({
      instance_id: item.id || item.furniture_id,
      catalog_item_id: item.catalog_furniture_id || item.furniture_id,
      normalized_type: item.normalized_type || item.type,
      name_zh: item.name_zh_raw || item.name_zh || item.name_en || "",
      position_cm: item.position_cm || item.position || null,
      rotation_deg: item.rotation_y_deg ?? item.rotation_deg ?? item.rotation ?? 0,
      size_cm: item.size_cm || item.dimensions || null,
      position_locked: Boolean(item.position_locked),
    });
  });
  const roomRequirements = roomRequirementsPayload.roomRequirements || {};
  const rooms = Object.entries(roomRequirements).map(([roomId, requirement]) => {
    const prior = roomsById.get(String(roomId)) || {};
    const furniture = requirement.furniture || {};
    return {
      ...prior,
      room_id: String(roomId),
      room_type: requirement.roomType,
      room_label: requirement.roomLabel,
      usage: requirement.usage || [],
      furniture_preference: {
        tags: furniture.preferenceTags || [],
        description: furniture.preferenceText || "",
      },
      selected_catalog_furniture: furniture.selected || [],
      final_step6_furniture: sceneObjectsByRoom.get(String(roomId)) || [],
      generative_equipment: requirement.generativeEquipment || {},
      surfaces: requirement.surfaces || {},
      rag: state.roomRagJobs?.[roomId] || {},
    };
  });
  return {
    ...previous,
    schema_version: "1.0",
    purpose: "external_image_generation_after_step6",
    space_constraints_are_fixed: true,
    generated_at: new Date().toISOString(),
    global_profile: state.basicAnswers || previous.global_profile || {},
    style: state.questionnaireFinishes || previous.style || {},
    rooms,
  };
}

async function requestPaletteRenders(renderBrief = null) {
  const styleCardIds = $$("[data-render-style-card]:checked").map((input) => input.value);
  if (!styleCardIds.length) {
    element.aiRenderStatus.textContent = "至少選擇一張色卡。";
    return;
  }
  try {
    const result = await api(`/api/projects/${state.projectId}/render-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload("palette_comparison", styleCardIds, [], renderBrief)),
    });
    const jobs = (result.jobs || [result.job]).filter(Boolean).map((job, index) => ({
      ...job,
      mode: "palette_comparison",
      style_card_id: job.style_card_id || styleCardIds[index] || styleCardIds[0],
      label: job.label || STYLE_PACKS.find(
        (pack) => pack.id === (job.style_card_id || styleCardIds[index]),
      )?.name,
    }));
    state.proposalReview.jobs = state.proposalReview.jobs
      .filter((job) => job.mode !== "palette_comparison")
      .concat(jobs);
    renderRemoteJobs();
    renderPaletteResults();
    scheduleSave("ai_render");
  } catch (error) {
    element.aiRenderStatus.textContent = errorMessage(error);
  }
}

async function submitRoomRenders(renderBrief = null) {
  const roomViews = Object.values(state.proposalReview.roomViews);
  if (!roomViews.length) {
    element.aiRenderStatus.textContent = "請至少保存一個房間視角。";
    return;
  }
  try {
    const result = await api(`/api/projects/${state.projectId}/render-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload(
        "room_final",
        [state.proposalReview.confirmedStyleCardId],
        roomViews,
        renderBrief,
      )),
    });
    state.proposalReview.jobs.push(...(result.jobs || [result.job]).filter(Boolean));
    state.workflow.complete("ai_render", { confirmed: true });
    renderRemoteJobs();
    scheduleSave("ai_render");
    element.aiRenderStatus.textContent = `已送出 ${roomViews.length} 個房間渲染任務。`;
  } catch (error) {
    element.aiRenderStatus.textContent = errorMessage(error);
  }
}

function bindEvents() {
  $("#exit-project")?.addEventListener("click", confirmProjectExit);
  element.projectForm?.addEventListener("submit", createProject);
  element.file?.addEventListener("change", () => selectFloorplanFile(element.file.files[0]));
  element.floorplanConfirmation?.addEventListener("change", updateUploadConfirmationState);
  element.confirmUpload?.addEventListener("click", confirmUpload);
  element.scaleOverlay?.addEventListener("pointerdown", calibrationPointerDown);
  element.scaleOverlay?.addEventListener("pointermove", calibrationPointerMove);
  element.scaleInput?.addEventListener("input", () => updateCalibrationAction());
  window.addEventListener("pointerup", async () => {
    if (structureCreateDrag) finishBeamCreateDrag();
    const completedRoomDrag = draggedRoomPointIndex != null;
    state.calibrationDragIndex = null;
    draggedRoomPointIndex = null;
    if (wallResizeDrag) {
      const completedWallResize = wallResizeDrag.changed;
      const blockedWallResize = wallResizeDrag.blocked;
      wallResizeDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      if (completedWallResize) {
        normalizeWallDemolitionCandidates();
        invalidateDownstreamFrom(
          "space_confirmation",
          "牆端點已調整，請重新確認結構後再產生 2D+3D 場景。",
        );
        scheduleSave("space_confirmation");
      } else if (blockedWallResize) {
        setStatus("牆端點未變更：請避開過短牆段與附著門窗洞口。", "error");
      }
    }
    if (structureDrag) {
      const completedStructureDrag = structureDrag.changed;
      const blockedStructureDrag = structureDrag.blocked;
      const draggedStructureKind = state.selectedStructure?.kind;
      const draggedStructure = selectedStructureItem();
      if (completedStructureDrag && draggedStructureKind === "door" && draggedStructure) {
        draggedStructure.confirmed = false;
      }
      if (completedStructureDrag && draggedStructureKind === "wall") {
        normalizeWallDemolitionCandidates();
      }
      structureDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      if (completedStructureDrag) {
        if (selectedStructureItem()?.scheme_id === "B") {
          invalidateRenovationScheme("方案 B 結構位置已修改；方案 A 與問卷保留。");
        } else {
          invalidateDownstreamFrom("space_confirmation", "結構位置已修改，後續需求、家具與 3D 需要重新確認。");
        }
        scheduleSave("space_confirmation");
      } else if (blockedStructureDrag) {
        setStatus("樑柱不可穿過牆體；位置未變更。", "error");
      }
    }
    if (doorResizeDrag) {
      const resizedKind = state.selectedStructure?.kind || "door";
      const resizedLabel = structureSectionMeta[resizedKind]?.label || "開口";
      doorResizeDrag = null;
      renderDoorReviewList();
      renderSelectedStructureEditor();
      if (selectedStructureItem()?.scheme_id === "B") {
        invalidateRenovationScheme(`方案 B 的${resizedLabel}寬已調整；方案 A 與問卷保留。`);
      } else {
        invalidateDownstreamFrom("space_confirmation", `${resizedLabel}寬已直接調整，後續需求、家具與 3D 需要重新確認。`);
      }
      scheduleSave("space_confirmation");
      setStatus(`${resizedLabel}寬已更新並保持吸附在牆上；請重新確認此${resizedLabel}。`);
    }
    if (beamResizeDrag) {
      const completedBeamResize = beamResizeDrag.changed;
      const blockedBeamResize = beamResizeDrag.blocked;
      beamResizeDrag = null;
      renderStructureReviewList();
      renderSelectedStructureEditor();
      if (completedBeamResize) {
        if (selectedStructureItem()?.scheme_id === "B") {
          invalidateRenovationScheme("方案 B 樑長已調整；方案 A 與問卷保留。");
        } else {
          invalidateDownstreamFrom("space_confirmation", "樑長已調整，後續需求、家具與 3D 需要重新確認。");
        }
        scheduleSave("space_confirmation");
        setStatus("樑長已更新，樑仍固定於天花板下方。");
      } else if (blockedBeamResize) {
        setStatus("樑柱不可穿過牆體；樑長未變更。", "error");
      }
    }
    if (completedRoomDrag) {
      const room = state.rooms.find((item) => item.id === state.selectedRoomId);
      if (room) room.confirmed = false;
      renderRooms();
      invalidateDownstreamFrom("space_confirmation", "房間框選已修改，後續需求、家具與 3D 需要重新確認。");
      scheduleSave("space_confirmation");
    }
    const completedDrag = furnitureDrag;
    furnitureDrag = null;
    if (completedDrag) await finishFurnitureDrag(completedDrag);
  });
  $("#reset-floorplan-calibration")?.addEventListener("click", () => {
    state.calibrationPoints = [];
    renderCalibration();
  });
  element.applyCalibration?.addEventListener("click", applyCalibration);
  element.roomList?.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-room]");
    if (deleteButton) {
      deleteRoom(deleteButton.dataset.deleteRoom);
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-room]");
    if (confirmButton) {
      confirmRoom(confirmButton.dataset.confirmRoom);
      return;
    }
    const button = event.target.closest("[data-room-id]");
    if (button) selectRoom(button.dataset.roomId);
  });
  $$("[data-room-geometry-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomGeometryMode(button.dataset.roomGeometryMode));
  });
  $("#apply-room-merge")?.addEventListener("click", mergeSelectedRooms);
  $("#cancel-room-geometry")?.addEventListener("click", () => setRoomGeometryMode(null));
  $$("[data-room-node-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomNodeMode(button.dataset.roomNodeMode));
  });
  $("#apply-node-merge")?.addEventListener("click", mergeSelectedRoomNodes);
  $("#cancel-node-edit")?.addEventListener("click", () => setRoomNodeMode(null));
  $("#add-missed-room")?.addEventListener("click", addMissedRoom);
  $("#confirm-all-rooms")?.addEventListener("click", confirmAllRooms);
  $("#show-all-rooms")?.addEventListener("click", () => {
    if (state.rooms.length <= 1) {
      setStatus("目前只有一個空間，沒有其他框選可顯示。");
      updateShowAllRoomsButton();
      return;
    }
    state.showAllRooms = true;
    renderSpaceOverlay();
    setStatus("已顯示全部空間框選。");
  });
  $("#save-room")?.addEventListener("click", saveRoom);
  element.spaceOverlay?.addEventListener("pointerdown", spacePointerDown);
  element.spaceOverlay?.addEventListener("pointermove", spacePointerMove);
  $("#apply-structure-size")?.addEventListener("click", applySelectedStructureSize);
  $("#lock-selected-door-opening")?.addEventListener("click", lockSelectedDoorOpening);
  [
    "#selected-structure-size-cm",
    "#selected-structure-depth-cm",
    "#selected-structure-height-cm",
  ].forEach((selector) => {
    $(selector).addEventListener("input", previewSelectedStructureDraft);
    $(selector).addEventListener("focus", previewSelectedStructureDraft);
  });
  $$("[data-structure-preview-view]").forEach((button) => {
    button.addEventListener("click", () => {
      structurePreview.setView(button.dataset.structurePreviewView);
      $$("[data-structure-preview-view]").forEach((candidate) => {
        candidate.classList.toggle("is-active", candidate === button);
      });
    });
  });
  $("#selected-window-type")?.addEventListener("change", applySelectedWindowType);
  element.openingWidthSlider?.addEventListener("input", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, false);
  });
  element.openingWidthSlider?.addEventListener("change", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, true);
  });
  $$("[data-opening-width-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextWidth = Number(element.openingWidthSlider.value)
        + Number(button.dataset.openingWidthStep);
      setSelectedOpeningWidthCm(nextWidth, true);
    });
  });
  $("#rotate-selected-structure-left")?.addEventListener("click", () => rotateSelectedStructure(-15));
  $("#rotate-selected-structure-right")?.addEventListener("click", () => rotateSelectedStructure(15));
  $("#rotate-selected-door-180")?.addEventListener("click", rotateSelectedDoor180);
  $("#delete-selected-structure")?.addEventListener("click", deleteSelectedStructure);
  $("#flip-selected-door")?.addEventListener("click", () => {
    const door = selectedStructureItem();
    if (!door || state.selectedStructure?.kind !== "door") return;
    door.opening_direction = door.opening_direction === "left" ? "right" : "left";
    delete door.swing_end;
    door.confirmed = false;
    renderSpaceOverlay();
    renderStructureCounts();
    renderSelectedStructureEditor();
    if (door.scheme_id === "B") {
      invalidateRenovationScheme("方案 B 門扇方向已修改；方案 A 與問卷保留。");
    } else {
      invalidateDownstreamFrom("space_confirmation", "門扇方向已修改，後續需求、家具與 3D 需要重新確認。");
    }
    scheduleSave("space_confirmation");
    setStatus("已切換門扇開啟方向。");
  });
  $$("[data-space-tab]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-space-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
    const rooms = button.dataset.spaceTab === "rooms";
    state.spaceMode = rooms ? "rooms" : "structure";
    $("#room-confirmation-panel").hidden = !rooms;
    $("#structure-confirmation-panel").hidden = rooms;
    $("#show-all-rooms").hidden = !rooms;
    $("#plan-structure-legend").hidden = rooms;
    $("#space-plan-caption").textContent = rooms
      ? "點房間框或右側名稱可定位；紫色節點可拖曳調整範圍。"
      : "點選牆、門、窗、樑或柱後會以橘黃色標示；可直接拖曳或在右側修改。";
    if (!rooms) setActiveStructureKind(state.activeStructureKind);
    renderSpaceOverlay();
    renderStructureReviewList();
    renderSelectedStructureEditor();
  }));
  $$("[data-structure-section]").forEach((button) => {
    button.addEventListener("click", () => setActiveStructureKind(button.dataset.structureSection));
  });
  element.doorReviewList?.addEventListener("click", (event) => {
    const wallTypeButton = event.target.closest("[data-wall-demolition]");
    if (wallTypeButton) {
      applyWallDemolitionType(
        wallTypeButton.dataset.wallId,
        wallTypeButton.dataset.wallDemolition === "candidate",
      );
      return;
    }
    const windowTypeButton = event.target.closest("[data-window-type]");
    if (windowTypeButton) {
      applyWindowType(
        windowTypeButton.dataset.windowId,
        windowTypeButton.dataset.windowType,
      );
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-structure]");
    if (confirmButton) {
      confirmStructure(
        confirmButton.dataset.structureKind,
        confirmButton.dataset.confirmStructure,
      );
      return;
    }
    const button = event.target.closest("[data-structure-review]");
    if (button) {
      selectStructureForReview(
        button.dataset.structureKind,
        button.dataset.structureReview,
      );
    }
  });
  $("#confirm-all-visible-structures")?.addEventListener("click", () => {
    const kind = state.activeStructureKind;
    const collection = state.structures[structureCollections[kind]] || [];
    let blockedCount = 0;
    collection.forEach((item) => {
      if (structureWallCollision(item, kind)) {
        blockedCount += 1;
        item.confirmed = false;
        return;
      }
      item.confirmed = true;
      item.estimated = false;
    });
    renderStructureReviewList();
    renderStructureCounts();
    scheduleSave("space_confirmation");
    if (blockedCount) {
      const message = `樑柱不可穿過牆體；${blockedCount} 個項目尚未確認，請先移動或縮小。`;
      element.spaceError.textContent = message;
      setStatus(message, "error");
    } else {
      element.spaceError.textContent = "";
      setStatus(`已確認此頁全部 ${collection.length} 個${structureSectionMeta[kind].label}項目。`);
    }
  });
  $$("[data-structure-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTool = state.structureTool === button.dataset.structureTool
        ? null
        : button.dataset.structureTool;
      if (!nextTool) {
        cancelStructureInteraction();
        return;
      }
      state.structureTool = nextTool;
      state.structureLineStart = null;
      state.structureLinePreviewEnd = null;
      state.selectedStructure = null;
      structureDrag = null;
      doorResizeDrag = null;
      beamResizeDrag = null;
      structureCreateDrag = null;
      $$("[data-structure-tool]").forEach((item) =>
        item.classList.toggle("is-active", item.dataset.structureTool === nextTool)
      );
      renderSpaceOverlay();
      renderDoorReviewList();
      renderSelectedStructureEditor();
      const structureLabel = {
        door: "門",
        window: "窗",
        column: "柱",
      }[state.structureTool];
      setStatus(state.structureTool === "wall" || state.structureTool === "beam"
        ? `請在左圖點${state.structureTool === "wall" ? "牆" : "樑"}的起點與終點。`
        : `請在左圖點選要放置${structureLabel}的位置，系統會自動磁吸。`);
    });
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/roompilot-structure", button.dataset.structureTool);
    });
  });
  $("#cancel-structure-interaction")?.addEventListener("click", cancelStructureInteraction);
  element.spaceStage?.addEventListener("dragover", (event) => event.preventDefault());
  element.spaceStage?.addEventListener("drop", (event) => {
    event.preventDefault();
    const tool = event.dataTransfer.getData("text/roompilot-structure");
    const point = imagePoint(event, element.spaceImage);
    if (tool && point) addDroppedStructure(tool, point);
  });
  $("#confirm-space")?.addEventListener("click", confirmSpace);
  $("#back-to-space-editor")?.addEventListener("click", () => {
    setSpaceReviewMode("editing");
    setStatus("可繼續調整房間與結構；完成後再確認尺寸標註平面圖。");
  });
  $("#recalibrate-space")?.addEventListener("click", () => {
    setSpaceReviewMode("editing");
    if (goTo("calibration")) {
      setStatus("請重新選取兩點並輸入實際尺寸；套用後會重新計算空間面積。");
    }
  });
  $("#confirm-dimensioned-plan")?.addEventListener("click", confirmDimensionedPlan);
  $("#confirm-basic-questionnaire")?.addEventListener("click", confirmBasicQuestionnaire);
  element.randomizeRequirements?.addEventListener("click", () => {
    void skipQuestionnaireWithDefaults();
  });
  element.randomizeRequirementsSummary?.addEventListener("click", () => {
    void skipQuestionnaireWithDefaults();
  });
  element.questionnaireStageNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-stage]");
    if (button && !button.disabled) showQuestionnaireStage(button.dataset.questionnaireStage);
  });
  element.visualSpaceNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-visual-room]");
    if (!button) return;
    state.roomRequirementModel.activeRoomId = button.dataset.visualRoom;
    state.selectedQuestionnaireWallId = null;
    renderVisualQuestionnaire();
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-room-section]");
    if (!button) return;
    const section = button.dataset.questionnaireRoomSection;
    if (!QUESTIONNAIRE_ROOM_SECTIONS.some((item) => item.id === section)) return;
    questionnaireRoomSection = section;
    renderQuestionnaireRoomSections();
  });
  element.openQuestionnaireFurnitureCatalog?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openQuestionnaireFurnitureCatalog(activeQuestionnaireRoom()?.id);
  });
  element.visualQuestionCard?.addEventListener("click", (event) => {
    const preferenceWeight = event.target.closest("[data-preference-weight]");
    if (preferenceWeight) {
      selectPreferenceWeight(preferenceWeight.dataset.preferenceWeight);
      return;
    }
    const special = event.target.closest("[data-keep-special-request]");
    if (special) {
      const label = special.dataset.keepSpecialRequest;
      const current = element.visualCustomAnswer.value.trim();
      const specialAnswer = buildSpecialRequestAnswer(
        special.dataset.specialOptionId,
        label,
        current,
      );
      element.visualCustomAnswer.value = specialAnswer.custom;
      selectVisualOption(special.dataset.specialOptionId, {
        ...specialAnswer,
      });
      element.requirementsError.textContent = "";
      return;
    }
    const option = event.target.closest("[data-visual-option]");
    if (option) selectVisualOption(option.dataset.visualOption);
  });
  element.roomPreferenceSuggestion?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-review-suggested-preferences]");
    const index = Number(button?.dataset.questionIndex);
    if (!button || !Number.isInteger(index) || index < 0) return;
    state.visualQuestionIndex = index;
    renderVisualQuestionnaire();
  });
  element.visualCustomAnswer?.addEventListener("input", () => {
    if (!saveVisualCustomAnswer()) return;
    capturePendingSave("requirements");
    clearTimeout(visualCustomSaveTimer);
    visualCustomSaveTimer = setTimeout(() => {
      visualCustomSaveTimer = null;
      scheduleSave("requirements");
    }, 450);
  });
  $("#visual-question-back")?.addEventListener("click", () => moveVisualQuestion(-1));
  $("#visual-question-next")?.addEventListener("click", () => moveVisualQuestion(1));
  $("#back-to-room-questionnaire")?.addEventListener("click", () => showQuestionnaireStage("rooms"));
  $("#questionnaire-summary-back")?.addEventListener("click", () => showQuestionnaireStage("profile"));
  element.wholeHouseStyleTabs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-whole-house-style]");
    if (!button) return;
    const firstPack = STYLE_PACKS.find(
      (pack) => pack.styleId === button.dataset.wholeHouseStyle,
    );
    if (firstPack) selectWholeHouseStylePack(firstPack.id);
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("#whole-house-style-grid [data-whole-house-style-pack]");
    if (!button) return;
    event.preventDefault();
    selectWholeHouseStylePack(button.dataset.wholeHouseStylePack);
  });
  element.questionnaireFurniturePreferenceTags?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-furniture-tag]");
    if (button) toggleQuestionnaireFurniturePreferenceTag(button.dataset.questionnaireFurnitureTag);
  });
  element.questionnaireStyleTabs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style]");
    if (!button) return;
    state.activeStyleId = button.dataset.questionnaireStyle;
    const firstPack = STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId);
    if (firstPack) selectQuestionnaireStylePack(firstPack.id);
  });
  element.questionnaireStyleGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style-pack]");
    if (button) selectQuestionnaireStylePack(button.dataset.questionnaireStylePack);
  });
  element.questionnaireRoomUsageOptions?.addEventListener("change", (event) => {
    const input = event.target.closest("[data-questionnaire-room-usage]");
    const room = activeQuestionnaireRoom();
    if (!input || !room) return;
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const selected = new Set(ensureRoomUsage(room));
    if (input.checked) selected.add(input.dataset.questionnaireRoomUsage);
    else selected.delete(input.dataset.questionnaireRoomUsage);
    requirement.usage = [...selected];
    requirement.confirmed = false;
    activeRoomFinishDraft().confirmed = false;
    delete state.roomFurnitureRecommendations[room.id];
    renderQuestionnaireRoomUsage(room);
    renderQuestionnaireFurnitureRecommendations(room);
    renderQuestionnaireRoomSections();
    void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
    invalidateDownstreamFrom(
      "requirements",
      `${room.label}的使用功能已更新，後續配置需要重新產生。`,
    );
    scheduleSave("requirements");
  });
  element.questionnaireGenerativeEquipment?.addEventListener("change", (event) => {
    if (event.target.matches("select, input[data-generative-direction], input[data-generative-exclusion]")) {
      updateGenerativeEquipment();
    }
  });
  element.questionnaireGenerationNotes?.addEventListener("input", () => updateGenerativeEquipmentNotes());
  element.questionnaireFurnitureOptions?.addEventListener("change", (event) => {
    const variant = event.target.closest("select[data-questionnaire-furniture-variant-type]");
    if (variant) {
      updateQuestionnaireFurnitureVariant(
        variant.dataset.questionnaireFurnitureVariantType,
        variant.value,
      );
      return;
    }
  });
  element.questionnaireFurnitureOptions?.addEventListener("click", (event) => {
    const quantity = event.target.closest("[data-questionnaire-furniture-quantity]");
    if (quantity) {
      event.preventDefault();
      event.stopPropagation();
      updateQuestionnaireFurnitureQuantity(
        quantity.dataset.questionnaireFurnitureId,
        Number(quantity.dataset.questionnaireFurnitureQuantity),
      );
      return;
    }
    const retry = event.target.closest("[data-retry-questionnaire-furniture]");
    if (retry) {
      const room = state.rooms.find(
        (candidate) => String(candidate.id) === String(retry.dataset.retryQuestionnaireFurniture),
      );
      if (room) void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
      return;
    }
  });
  document.addEventListener("click", (event) => {
    const furnitureInput = event.target.closest(
      "#questionnaire-furniture-options input[data-questionnaire-furniture-id]",
    );
    if (furnitureInput) {
      // The native input toggles after click dispatch. Persist its settled value.
      window.setTimeout(() => {
        updateQuestionnaireFurnitureSelection(
          furnitureInput.dataset.questionnaireFurnitureId,
          furnitureInput.checked,
        );
      }, 0);
      return;
    }
    const button = event.target.closest("[data-open-questionnaire-furniture-catalog]");
    if (button) {
      openQuestionnaireFurnitureCatalog(
        button.dataset.openQuestionnaireFurnitureCatalog || activeQuestionnaireRoom()?.id,
      );
    }
  });
  $$("#questionnaire-finishes .rp-questionnaire-furniture > .rp-action-row [data-open-questionnaire-furniture-catalog]")
    .forEach((button) => button.addEventListener("click", (event) => {
      event.preventDefault();
      openQuestionnaireFurnitureCatalog();
    }));
  element.refreshQuestionnaireFurniture?.addEventListener(
    "click",
    refreshQuestionnaireFurnitureRecommendations,
  );
  element.questionnaireMaterialPairs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-pair]");
    if (!button) return;
    const pairs = questionnaireMaterialPairCards(activeQuestionnairePack());
    const pair = pairs[Number(button.dataset.questionnaireMaterialPair)];
    if (pair) selectQuestionnaireMaterialPair(pair);
  });
  [element.questionnaireWallOptions, element.questionnaireFloorOptions].forEach((host) => {
    host?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-questionnaire-material]");
      if (!button) return;
      const key = button.dataset.questionnaireMaterial === "wall"
        ? "wallMaterial"
        : "floorMaterial";
      const colorKey = button.dataset.questionnaireMaterial === "wall"
        ? "wallColor"
        : "floorColor";
      const draft = activeRoomFinishDraft();
      draft[key] = button.dataset.questionnaireMaterialId;
      const pack = activeQuestionnairePack();
      const option = questionnaireMaterialOptionsForPack(
        button.dataset.questionnaireMaterial,
        pack,
      ).find((candidate) => candidate.id === button.dataset.questionnaireMaterialId);
      if (option?.color) draft[colorKey] = option.color;
      if (button.dataset.questionnaireMaterial === "wall") {
        if (state.selectedQuestionnaireWallId) {
          draft.wallOverrides[state.selectedQuestionnaireWallId] = {
            materialId: draft.wallMaterial,
            color: draft.wallColor,
          };
        } else {
          draft.defaultWallMaterial = draft.wallMaterial;
          draft.defaultWallColor = draft.wallColor;
        }
      }
      draft.confirmed = false;
      renderQuestionnaireFinishes();
      scheduleSave("requirements");
    });
  });
  [
    [element.questionnaireWallColor, "wallColor"],
    [element.questionnaireFloorColor, "floorColor"],
    [element.questionnaireCeilingMaterial, "ceilingMaterial"],
    [element.questionnaireCeilingStyle, "ceilingStyle"],
    [element.questionnaireLightStyle, "lightStyle"],
    [element.questionnaireCeilingColor, "ceilingColor"],
    [element.questionnaireAirConditioning, "airConditioning"],
  ].forEach(([control, key]) => {
    control?.addEventListener("change", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value;
      if (["wallColor", "floorColor"].includes(key)) {
        draft.materialSelectionMode = "custom";
        draft.styleReviewRequired = false;
      }
      if (key === "wallColor") {
        if (state.selectedQuestionnaireWallId) {
          draft.wallOverrides[state.selectedQuestionnaireWallId] = {
            materialId: draft.wallMaterial,
            color: draft.wallColor,
          };
        } else {
          draft.defaultWallColor = draft.wallColor;
        }
      }
      draft.confirmed = false;
      scheduleSave("requirements");
    });
  });
  [
    [element.questionnaireWallPreference, "wallPreference"],
    [element.questionnaireFloorPreference, "floorPreference"],
  ].forEach(([control, key]) => {
    control?.addEventListener("input", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value.trim();
      draft.materialSelectionMode = "custom";
      draft.styleReviewRequired = false;
      draft.confirmed = false;
      const requirement = activeRoomRequirement();
      if (requirement?.surfaces) requirement.surfaces[key] = draft[key];
      scheduleSave("requirements");
    });
  });
  element.questionnaireCeilingQuickChoices?.addEventListener("click", (event) => {
    const designStyle = event.target.closest("[data-open-questionnaire-ceiling-design-style]");
    if (designStyle) {
      openQuestionnaireCeilingDesignStyle(designStyle.dataset.openQuestionnaireCeilingDesignStyle);
      return;
    }
    const designPack = event.target.closest("[data-questionnaire-ceiling-design-pack]");
    if (designPack) {
      selectQuestionnaireCeilingDesignPack(designPack.dataset.questionnaireCeilingDesignPack);
      return;
    }
    const button = event.target.closest("[data-open-questionnaire-ceiling-picker]");
    if (!button) return;
    openQuestionnaireCeilingPicker(button.dataset.openQuestionnaireCeilingPicker);
  });
  element.questionnaireCeilingPickerOptions?.addEventListener("click", (event) => {
    const designPack = event.target.closest("[data-questionnaire-ceiling-design-pack]");
    if (designPack) {
      element.questionnaireCeilingPickerDialog.close();
      selectQuestionnaireCeilingDesignPack(designPack.dataset.questionnaireCeilingDesignPack);
      return;
    }
    const button = event.target.closest("[data-questionnaire-ceiling-picker-item]");
    if (!button) return;
    selectQuestionnaireCeilingPickerItem(button.dataset.questionnaireCeilingPickerItem);
  });
  element.closeQuestionnaireCeilingPicker?.addEventListener("click", () => {
    element.questionnaireCeilingPickerDialog?.close();
    questionnaireCeilingPickerKind = null;
  });
  element.questionnaireFinishScope?.addEventListener("change", () => {
    element.questionnaireFinishRoomTargets.hidden =
      element.questionnaireFinishScope.value !== "selected";
  });
  element.enableCirculationStyleOverride?.addEventListener("click", () => {
    const room = activeQuestionnaireRoom();
    const requirement = activeRoomRequirement();
    const livingRoom = livingRoomForCirculation();
    if (!room || !requirement || !isCirculationRoom(room)) return;
    const approved = window.confirm(
      `走道目前沿用「${livingRoom?.label || "客廳"}」的風格與材質。改為獨立風格會讓動線出現視覺差異，並在第 6 步重新檢查銜接。要繼續嗎？`,
    );
    if (!approved) return;
    copyLivingRoomStyleToCirculation(room, { force: true });
    requirement.circulationStyleOverrideApproved = true;
    activeRoomFinishDraft().confirmed = false;
    renderQuestionnaireFinishes();
    invalidateDownstreamFrom("requirements", "走道已改為獨立風格，後續配置需要重新產生。");
    scheduleSave("requirements");
  });
  $("#apply-air-conditioning-all")?.addEventListener("click", () => {
    const airConditioning = element.questionnaireAirConditioning.value || "auto";
    Object.values(state.roomRequirementModel.roomRequirements || {}).forEach((requirement) => {
      requirement.climate = {
        ...(requirement.climate || {}),
        airConditioning,
      };
      const draft = state.roomFinishDrafts[requirement.roomId];
      if (draft) draft.airConditioning = airConditioning;
    });
    state.questionnaireFinishes = {
      ...state.questionnaireFinishes,
      airConditioning,
    };
    setStatus("冷氣設定已套用至全部房間；仍可在個別房間覆寫。", "success");
    scheduleSave("requirements");
  });
  element.questionnairePlanOverlay?.addEventListener("click", (event) => {
    const wall = event.target.closest("[data-questionnaire-wall]");
    if (wall) {
      state.selectedQuestionnaireWallId = wall.dataset.questionnaireWall;
      const draft = activeRoomFinishDraft();
      const override = draft.wallOverrides?.[state.selectedQuestionnaireWallId];
      draft.wallMaterial = override?.materialId || draft.defaultWallMaterial;
      draft.wallColor = override?.color || draft.defaultWallColor;
      renderQuestionnairePlan();
      renderQuestionnaireFinishes();
      return;
    }
    const room = event.target.closest("[data-questionnaire-room]");
    if (!room) return;
    state.roomRequirementModel.activeRoomId = room.dataset.questionnaireRoom;
    state.selectedQuestionnaireWallId = null;
    const draft = activeRoomFinishDraft();
    draft.wallMaterial = draft.defaultWallMaterial;
    draft.wallColor = draft.defaultWallColor;
    renderVisualQuestionnaire();
  });
  $("#confirm-questionnaire-finishes")?.addEventListener("click", confirmQuestionnaireFinishes);
  element.confirmRequirements?.addEventListener("click", confirmRequirements);
  $("#retry-configuration-catalog-check")?.addEventListener("click", () => {
    void confirmRequirements();
  });
  document.addEventListener("click", (event) => {
    const openCatalog = event.target.closest("[data-open-material-catalog]");
    if (openCatalog) {
      questionnaireMaterialCatalogType = "all";
      questionnaireMaterialCatalogColor = "all";
      renderQuestionnaireMaterialCatalog(openCatalog.dataset.openMaterialCatalog, "");
      return;
    }
    const catalogMaterial = event.target.closest("[data-questionnaire-catalog-material]");
    if (!catalogMaterial) return;
    selectQuestionnaireMaterial(
      catalogMaterial.dataset.questionnaireCatalogMaterial,
      catalogMaterial.dataset.questionnaireCatalogMaterialId,
    );
    element.questionnaireMaterialCatalogDialog.close();
  });
  element.questionnaireMaterialCatalogSearch?.addEventListener("input", () => {
    if (!questionnaireMaterialCatalogKind) return;
    renderQuestionnaireMaterialCatalog(
      questionnaireMaterialCatalogKind,
      element.questionnaireMaterialCatalogSearch.value,
    );
  });
  element.questionnaireMaterialTypeFilters?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-type]");
    if (!button || !questionnaireMaterialCatalogKind) return;
    questionnaireMaterialCatalogType = button.dataset.questionnaireMaterialType;
    renderQuestionnaireMaterialCatalog(questionnaireMaterialCatalogKind);
  });
  element.questionnaireMaterialColorFilters?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-material-color]");
    if (!button || !questionnaireMaterialCatalogKind) return;
    questionnaireMaterialCatalogColor = button.dataset.questionnaireMaterialColor;
    renderQuestionnaireMaterialCatalog(questionnaireMaterialCatalogKind);
  });
  $("#return-to-room-requirements")?.addEventListener("click", () => {
    clearRequirementsGenerationHelp();
    showQuestionnaireStage("rooms");
  });
  $$("[data-design-scheme]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!switchDesignScheme(button.dataset.designScheme)) return;
      setStatus(`已切換至方案 ${button.dataset.designScheme}；家具座標與 3D 場景彼此獨立。`);
    });
  });
  $("#delete-scheme-b")?.addEventListener("click", () => {
    if (!state.designSchemes.schemes.B) return;
    if (!confirm("刪除方案 B 會移除其改造結構、家具配置、3D、視角與渲染結果。方案 A 與問卷會保留。")) {
      return;
    }
    switchDesignScheme("A");
    Object.keys(state.structures).forEach((collection) => {
      state.structures[collection] = (state.structures[collection] || []).filter(
        (item) => item.scheme_id !== "B",
      );
    });
    state.structures.walls.forEach((wall) => {
      wall.demolition_candidate = false;
    });
    const proposalUsesSchemeB = state.designSchemes.locked_scheme_id === "B"
      || state.proposalReview.masterView?.scheme_id === "B";
    if (proposalUsesSchemeB) {
      state.designSchemes.locked_scheme_id = null;
      state.proposalReview = {
        masterView: null,
        confirmedStyleCardId: null,
        roomViews: {},
        jobs: [],
      };
      state.selectedRenderRoomId = null;
      state.workflow?.invalidateFrom?.("proposal_review");
    }
    deleteSchemeB(state.designSchemes);
    renderSchemeControls();
    renderSchemeComparison();
    renderSpaceOverlay();
    renderStructureReviewList();
    scheduleSave("space_confirmation");
    setStatus("方案 B 已刪除；方案 A、問卷與家具需求均已保留。");
  });
  $("#auto-layout-furniture")?.addEventListener("click", async () => {
    element.layoutError.textContent = "";
    try {
      setStatus("正在由家具引擎重新配置合法位置…");
      if (activeSchemeId() === "B" && state.designSchemes.schemes.A.furniture.length) {
        const furniture = await relayoutFurnitureForScheme(
          state.designSchemes.schemes.A.furniture,
          "B",
        );
        if (!furniture) {
          throw new Error("方案 B 無法在保留問卷家具需求下產生合法配置。");
        }
        state.furniture2d = furniture;
        const schemeB = state.designSchemes.schemes.B;
        schemeB.furniture = JSON.parse(JSON.stringify(furniture));
        schemeB.stale = false;
        schemeB.staleReason = "";
        renderLayoutRoomFilter();
        renderLayoutFurniture();
        scheduleSave("layout_2d");
      } else {
        await autoLayoutFurniture();
      }
      setStatus(`家具引擎已重新配置 ${state.furniture2d.length} 件家具。`);
    } catch (error) {
      element.layoutError.textContent = errorMessage(error);
      setStatus(errorMessage(error), "error");
    }
  });
  element.furnitureSearch?.addEventListener("input", () => renderFurnitureLibrary(element.furnitureSearch.value));
  element.layoutRoomFilter?.addEventListener("change", () => {
    state.activeLayoutRoomId = element.layoutRoomFilter.value || "all";
    renderLayoutFurniture();
  });
  $("#add-2d-furniture-mode")?.addEventListener("click", () => {
    state.selectedFurniture2dId = null;
    renderLayoutFurniture();
    setStatus("現在是新增模式：請從右側選一個 2D 家具圖示，系統會放進目前房間。");
  });
  element.furnitureLibrary?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-furniture-type]");
    if (button) addFurnitureFromLibrary(button.dataset.addFurnitureType, button.dataset.addFurnitureVariant);
  });
  element.layoutLayer?.addEventListener("pointerdown", layoutPointerDown);
  element.layoutLayer?.addEventListener("pointermove", layoutPointerMove);
  element.selectedFurnitureWidth?.addEventListener("change", updateSelectedFurnitureDimensions);
  element.selectedFurnitureDepth?.addEventListener("change", updateSelectedFurnitureDimensions);
  $("#rotate-2d-furniture")?.addEventListener("click", () => {
    const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
    if (item) item.rotationDeg = (item.rotationDeg + 90) % 360;
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具旋轉已修改，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#delete-2d-furniture")?.addEventListener("click", () => {
    state.furniture2d = state.furniture2d.filter((item) => item.id !== state.selectedFurniture2dId);
    syncFurnitureInventoryAcrossSchemes();
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具已刪除，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#confirm-layout-2d")?.addEventListener("click", confirmLayout2d);
  $$("[data-view-mode]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.viewMode === "walk") {
      activateWhiteWalkMode();
      return;
    }
    $$("[data-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    whiteViewer.setViewMode(button.dataset.viewMode);
    $$("[data-white-interaction]").forEach((item) => {
      item.classList.toggle(
        "is-active",
        button.dataset.viewMode === "walk" && item.dataset.whiteInteraction === "walk",
      );
    });
  }));
  $$("[data-white-interaction]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.whiteInteraction === "walk") {
        activateWhiteWalkMode();
      } else {
        activateWhiteFurnitureEditing();
      }
    });
  });
  $("#toggle-furniture-numbers")?.addEventListener("click", () => {
    state.showFurnitureNumbers = !state.showFurnitureNumbers;
    syncFurnitureNumberVisibility();
  });
  $$('[data-scene-sidebar-tab]').forEach((button) => {
    button.addEventListener("click", () => setSceneSidebarTab(button.dataset.sceneSidebarTab));
  });
  element.whiteWalkRoom?.addEventListener("change", () => {
    state.selectedWalkRoomId = element.whiteWalkRoom.value;
    activateWhiteWalkMode();
  });
  $("#add-white-model-beam")?.addEventListener("click", () => {
    if (!goTo("space_confirmation")) return;
    showStep("space_confirmation");
    setSpaceReviewMode("editing");
    state.spaceMode = "structure";
    setActiveStructureKind("beam");
    setStatus("已返回第 4 步樑頁；修改結構後，問卷保留並重新計算家具與 3D。");
  });
  element.layoutFurnitureList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-select-layout-furniture]");
    if (!button) return;
    state.selectedFurniture2dId = button.dataset.selectLayoutFurniture;
    renderLayoutFurniture();
    syncSelected2dFurnitureToScene({ focus: false });
  });
  const selectConfigurationFurniture = (event) => {
    const button = event.target.closest("[data-select-configuration-furniture]");
    if (!button) return;
    const fromPlan = event.currentTarget === element.configurationPlanLayer;
    const fromFurnitureList = event.currentTarget === element.configurationPlanFurnitureList;
    state.selectedFurniture2dId = button.dataset.selectConfigurationFurniture;
    if (fromFurnitureList) void openFurnitureReplacement();
    renderLayoutFurniture();
    renderConfigurationPlan();
    const focused = syncSelected2dFurnitureToScene({ focus: false });
    if (fromPlan) {
      const item = state.furniture2d.find(
        (candidate) => candidate.id === state.selectedFurniture2dId,
      );
      setStatus(
        focused && item
          ? `已在 3D 定位家具 ${configurationFurnitureNumber(item)}「${item.label}」。`
          : "已選取家具；目前尚無可定位的 3D 模型。",
      );
    }
  };
  element.configurationPlanLayer?.addEventListener("click", selectConfigurationFurniture);
  element.configurationPlanFurnitureList?.addEventListener(
    "click",
    selectConfigurationFurniture,
  );
  element.configurationPendingList?.addEventListener("click", (event) => {
    const prioritizeButton = event.target.closest("[data-prioritize-configuration-room]");
    if (prioritizeButton) {
      void prioritizeConfigurationRoomFurniture(
        prioritizeButton.dataset.prioritizeConfigurationRoom,
      );
      return;
    }
    const replaceButton = event.target.closest("[data-replace-configuration-furniture]");
    if (replaceButton) {
      state.selectedFurniture2dId = replaceButton.dataset.replaceConfigurationFurniture;
      renderLayoutFurniture();
      renderConfigurationPlan();
      syncSelected2dFurnitureToScene({ focus: true });
      void openFurnitureReplacement();
      return;
    }
    const reflowButton = event.target.closest("[data-reflow-configuration-furniture]");
    if (reflowButton) {
      void reflowSingleConfigurationFurniture(
        reflowButton.dataset.reflowConfigurationFurniture,
      );
      return;
    }
    selectConfigurationFurniture(event);
  });
  element.configurationPlanImage?.addEventListener("load", renderConfigurationPlan);
  element.configurationPlanToggle?.addEventListener("click", () => {
    const collapsed = element.configurationPlanPanel.classList.toggle("is-collapsed");
    element.configurationPlanToggle.textContent = collapsed ? "+" : "−";
    element.configurationPlanToggle.title = collapsed ? "展開 2D 平面" : "收合 2D 平面";
    element.configurationPlanToggle.setAttribute(
      "aria-label",
      collapsed ? "展開 2D 平面" : "收合 2D 平面",
    );
    if (!collapsed) requestAnimationFrame(renderConfigurationPlan);
  });
  $("#replace-2d-furniture")?.addEventListener("click", openFurnitureReplacement);
  $("#furniture-property-locks")?.addEventListener("click", (event) => {
    const sameType = event.target.closest("[data-open-same-type-replacement]");
    if (sameType) {
      void openFurnitureReplacement({ mode: "same-type" });
      return;
    }
    const allTypes = event.target.closest("[data-open-all-type-replacement]");
    if (allTypes) {
      void openFurnitureReplacement({ mode: "all" });
      return;
    }
    const lockButton = event.target.closest("[data-lock-current-furniture]");
    if (lockButton) {
      const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
      if (!selected) return;
      selected.model_locked = !selected.model_locked;
      $("#lock-specified-model").checked = selected.model_locked;
      scheduleSave("white_model_3d");
      renderSelectedFurnitureWorkspace();
      setStatus(selected.model_locked ? "已鎖定此家具，之後切換風格不會替換模型。" : "已解除家具鎖定，之後可隨風格調整。");
      return;
    }
    const deleteButton = event.target.closest("[data-delete-current-furniture]");
    if (deleteButton) {
      if (!confirm("要刪除目前選取的家具嗎？")) return;
      void deleteSelectedSceneFurniture();
    }
  });
  $("#close-furniture-replacement")?.addEventListener("click", () => {
    setReplacementDrawerOpen(false);
  });
  element.replacementSearch?.addEventListener("change", () => {
    loadReplacementCandidates().catch((error) => {
      element.replacementError.textContent = errorMessage(error);
    });
  });
  element.replacementQuery?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    loadReplacementCandidates().catch((error) => {
      element.replacementError.textContent = errorMessage(error);
    });
  });
  element.replacementResults?.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-preview-replacement]");
    if (preview) {
      const candidates = JSON.parse(element.replacementResults.dataset.items || "[]");
      const candidate = candidates.find(
        (item) => item.furniture_id === preview.dataset.previewReplacement,
      );
      previewReplacementCandidate(candidate);
      return;
    }
    const confirmButton = event.target.closest("[data-confirm-replacement]");
    if (confirmButton) {
      replaceSelectedLayoutFurniture(confirmButton.dataset.confirmReplacement).catch((error) => {
        element.replacementError.textContent = errorMessage(error);
      });
    }
  });
  $("#cancel-white-model-beam")?.addEventListener("click", cancelWhiteModelBeamPlacement);
  const selectSceneObject = (event) => {
    const button = event.target.closest("[data-scene-object-index]");
    if (!button) return;
    saveSelectedSceneAppearance();
    state.selectedSceneIndex = Number(button.dataset.sceneObjectIndex);
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    syncSceneSelectionTo2dFurniture(
      state.sceneData?.scene_objects?.[state.selectedSceneIndex],
    );
    if (state.workflow.currentStep === "realistic_3d") {
      realisticViewer.selectObjectByIndex(state.selectedSceneIndex);
    } else {
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
    }
    scheduleSave(state.workflow.currentStep);
  };
  element.objectList?.addEventListener("click", selectSceneObject);
  element.realisticObjectList?.addEventListener("click", selectSceneObject);
  $("#delete-replacement-furniture")?.addEventListener("click", async () => {
    await deleteSelectedSceneFurniture();
    if (element.replacementDrawer.open) setReplacementDrawerOpen(false);
  });
  $("#delete-realistic-furniture")?.addEventListener("click", deleteSelectedSceneFurniture);
  [
    "#specified-furniture-color",
    "#specified-furniture-material",
    "#lock-specified-model",
    "#lock-specified-material",
  ].forEach((selector) => $(selector).addEventListener("change", () => {
    saveSelectedSceneAppearance();
    scheduleSave("white_model_3d");
  }));
  $("#open-furniture-catalog")?.addEventListener("click", () => setFurnitureCatalogOpen(true));
  element.openRoomSchemeSelection?.addEventListener("click", openRoomSchemeSelectionDialog);
  $("#close-room-scheme-selection")?.addEventListener("click", closeRoomSchemeSelectionDialog);
  $("#room-scheme-cancel")?.addEventListener("click", closeRoomSchemeSelectionDialog);
  element.roomSchemeList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-room-scheme-room]");
    if (!button) return;
    state.selectedRoomSchemeId = button.dataset.roomSchemeRoom;
    renderRoomSchemeSelectionDialog();
    void ensureRoomScheme3dPreviews();
  });
  element.roomSchemeChoiceGrid?.addEventListener("click", (event) => {
    const preview = event.target.closest("[data-room-scheme-preview-3d]");
    if (preview) {
      void openRoomScheme3dPreview(preview.dataset.roomSchemePreview3d);
      return;
    }
    const button = event.target.closest("[data-room-scheme-choice]");
    if (!button) return;
    chooseRoomScheme(button.dataset.roomSchemeChoice);
  });
  $("#close-room-scheme-3d-preview")?.addEventListener("click", () => {
    setTaskDialogOpen(element.roomScheme3dPreviewDialog, false);
  });
  element.roomSchemeComplete?.addEventListener("click", () => {
    void completeRoomSchemeSelection();
  });
  element.openSurfaceAdjustment?.addEventListener("click", () => openStepSixTaskDialog("surface"));
  element.openLightingAdjustment?.addEventListener("click", () => openStepSixTaskDialog("lighting"));
  [
    ["#close-surface-adjustment", "#surface-adjustment-done", element.surfaceAdjustmentDialog],
    ["#close-lighting-adjustment", "#lighting-adjustment-done", element.lightingAdjustmentDialog],
  ].forEach(([closeSelector, doneSelector, dialog]) => {
    $(closeSelector)?.addEventListener("click", () => closeStepSixTaskDialog(dialog));
    $(doneSelector)?.addEventListener("click", () => closeStepSixTaskDialog(dialog));
    dialog?.addEventListener("close", restoreStepSixTaskControls);
  });
  $("#close-furniture-catalog")?.addEventListener("click", () => setFurnitureCatalogOpen(false));
  $("#search-glb-furniture")?.addEventListener("click", searchGlbFurniture);
  $("#glb-furniture-search")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchGlbFurniture();
    }
  });
  if (element.standardCatalogSearch && element.standardCatalogSearch !== $("#glb-furniture-search")) {
    element.standardCatalogSearch.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchGlbFurniture();
      }
    });
  }
  $("#glb-furniture-search")?.addEventListener("input", () => {
    clearTimeout(questionnaireCatalogSearchTimer);
    questionnaireCatalogSearchTimer = setTimeout(searchGlbFurniture, 180);
  });
  element.questionnaireCatalogControls?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-catalog-scope]");
    const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
    if (button) {
      questionnaireCatalogScope = button.dataset.questionnaireCatalogScope;
      questionnaireCatalogPurpose = "";
      if (questionnaireCatalogScope === "all") questionnaireCatalogSpace = "";
      element.questionnaireCatalogControls
        .querySelectorAll("[data-questionnaire-catalog-scope]")
        .forEach((item) => item.classList.toggle("is-active", item === button));
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
      return;
    }
    const spaceButton = event.target.closest("[data-questionnaire-catalog-space]");
    if (spaceButton) {
      questionnaireCatalogSpace = spaceButton.dataset.questionnaireCatalogSpace;
      questionnaireCatalogPurpose = "";
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
      return;
    }
    const purposeButton = event.target.closest("[data-questionnaire-catalog-purpose]");
    if (purposeButton) {
      questionnaireCatalogPurpose = purposeButton.dataset.questionnaireCatalogPurpose;
      renderQuestionnaireCatalogBrowseChoices(room);
      void searchGlbFurniture();
    }
  });
  [
    element.questionnaireCatalogType,
    element.questionnaireCatalogColor,
    element.questionnaireCatalogMaterial,
  ].forEach((control) => control?.addEventListener("change", () => void searchGlbFurniture()));
  element.glbResults?.addEventListener("click", (event) => {
    const questionnaireAddButton = event.target.closest("[data-add-questionnaire-furniture-id]");
    if (questionnaireAddButton) {
      addQuestionnaireCatalogFurniture(questionnaireAddButton.dataset.addQuestionnaireFurnitureId);
      questionnaireAddButton.textContent = "已加入本房";
      questionnaireAddButton.disabled = true;
      return;
    }
    const replacementButton = event.target.closest("[data-replace-furniture-id]");
    if (replacementButton) {
      setFurnitureCatalogOpen(false);
      replaceSceneFurniture(replacementButton.dataset.replaceFurnitureId);
      return;
    }
    const addButton = event.target.closest("[data-add-furniture-id]");
    if (addButton) {
      setFurnitureCatalogOpen(false);
      addSceneFurniture(addButton.dataset.addFurnitureId);
    }
  });
  $("#confirm-white-model")?.addEventListener("click", confirmWhiteModel);
  element.styleTabs?.addEventListener("pointerdown", (event) => {
    const button = event.target.closest("[data-style-tab]");
    if (!button) return;
    state.activeStyleId = button.dataset.styleTab;
    renderStyleControls();
  });
  element.styleGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-style-pack]");
    const pack = STYLE_PACKS.find((item) => item.id === button?.dataset.stylePack);
    if (pack) {
      markRealisticSceneEdited();
      applyStylePackToScene(pack);
    }
  });
  $$("[data-real-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-real-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    realisticViewer.setViewMode(button.dataset.realViewMode);
    $("#lock-real-view-for-edit").textContent = "鎖定視角並編輯家具";
  }));
  $("#lock-real-view-for-edit")?.addEventListener("click", (event) => {
    const locked = realisticViewer.toggleCameraLock();
    event.currentTarget.textContent = locked ? "結束家具編輯" : "鎖定視角並編輯家具";
  });
  $$("[data-proposal-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-proposal-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode(button.dataset.proposalViewMode);
  }));
  $("#suggest-master-view")?.addEventListener("click", () => {
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
    $$("[data-proposal-view-mode]").forEach((item) => {
      item.classList.toggle("is-active", item.dataset.proposalViewMode === "orbit");
    });
    element.masterViewStatus.textContent = "已套用建議透視視角；可以繼續微調。";
  });
  $("#lock-master-view")?.addEventListener("click", () => {
    try {
      lockMasterRenderView();
    } catch (error) {
      element.masterViewStatus.textContent = `無法鎖定視角：${errorMessage(error)}`;
    }
  });
  element.glbResults?.addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-questionnaire-catalog-select]");
    if (!checkbox) return;
    const id = String(checkbox.dataset.questionnaireCatalogSelect);
    const items = JSON.parse(element.glbResults.dataset.items || "[]");
    if (checkbox.checked) {
      questionnaireCatalogSelectedFurnitureIds.add(id);
      const item = items.find((candidate) => String(candidate.furniture_id) === id);
      if (item) questionnaireCatalogSelectedFurniture.set(id, item);
    } else {
      questionnaireCatalogSelectedFurnitureIds.delete(id);
      questionnaireCatalogSelectedFurniture.delete(id);
    }
    renderQuestionnaireCatalogBatch();
  });
  element.addSelectedQuestionnaireFurniture?.addEventListener("click", () => {
    [...questionnaireCatalogSelectedFurniture.values()].forEach((item) => addQuestionnaireCatalogFurniture(item.furniture_id, item));
    questionnaireCatalogSelectedFurnitureIds = new Set();
    questionnaireCatalogSelectedFurniture = new Map();
    renderQuestionnaireCatalogBatch();
    void searchGlbFurniture();
  });
  $("#return-to-realistic")?.addEventListener("click", () => goTo("realistic_3d"));
  element.proposalPaletteGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-proposal-style-card]");
    if (button) selectProposalPalette(button.dataset.proposalStyleCard);
  });
  $("#request-palette-renders")?.addEventListener("click", () => openRenderBriefDialog("palette_comparison"));
  element.confirmRenderPalette?.addEventListener("click", confirmRenderPalette);
  element.renderRoomList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-render-room]");
    if (button) selectRenderRoom(button.dataset.renderRoom);
  });
  $("#save-room-view")?.addEventListener("click", saveSelectedRoomView);
  $("#submit-room-renders")?.addEventListener("click", () => openRenderBriefDialog("room_final"));
  $("#close-render-brief")?.addEventListener("click", closeRenderBriefDialog);
  $("#render-brief-cancel")?.addEventListener("click", closeRenderBriefDialog);
  $("#render-brief-confirm")?.addEventListener("click", () => {
    void confirmRenderBriefAndSubmit();
  });
  $("#apply-surface-colors")?.addEventListener("click", () => {
    markRealisticSceneEdited();
    applySurfaceOverrides({ userInitiated: true });
  });
  [element.wallMaterialGrouped, element.floorMaterialGrouped].forEach((host) => {
    host?.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-surface-material]");
      if (!button) return;
      const kind = button.dataset.surfaceKind;
      const select = $(`#${kind}-material`);
      const color = $(`#${kind}-color`);
      const materialId = button.dataset.surfaceMaterial;
      if (select) select.value = materialId;
      if (!select || select.value !== materialId) {
        element.realisticStatus.textContent = "材質選項尚未載入完成，請重新選擇。";
        return;
      }
      if (color && button.dataset.surfaceColor) color.value = button.dataset.surfaceColor;
      renderGroupedMaterialOptions(stylePackByIdSafe(state.activeStylePackId));
      markRealisticSceneEdited();
      await applySurfaceOverrides({ userInitiated: true });
    });
  });
  ["wall-color", "floor-color", "wall-material", "floor-material"].forEach((id) => {
    $(`#${id}`)?.addEventListener("change", async () => {
      renderGroupedMaterialOptions(stylePackByIdSafe(state.activeStylePackId));
      markRealisticSceneEdited();
      await applySurfaceOverrides({ userInitiated: true });
    });
  });
  $("#draw-material-boundary")?.addEventListener("click", toggleMaterialBoundary);
  $("#remove-material-boundary")?.addEventListener("click", removeMaterialBoundary);
  $("#material-boundary-position")?.addEventListener("input", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  $("#material-boundary-direction")?.addEventListener("change", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  element.ceilingStyle?.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  element.lightStyle?.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  $("#undo-style-change")?.addEventListener("click", async () => {
    const previous = state.styleHistory.pop();
    if (!previous) return;
    state.surfaceState = previous.surfaceState;
    const pack = STYLE_PACKS.find((item) => item.id === previous.packId);
    if (pack) {
      state.activeStylePackId = null;
      await applyStylePackToScene(pack);
    }
  });
  $("#save-realistic-scene")?.addEventListener("click", () => {
    const completed = state.workflow.complete("realistic_3d", { confirmed: true });
    if (!completed) return;
    scheduleSave("realistic_3d");
    setStatus("即時寫實方案已保存；請在第 7 步核對並鎖定比較視角。");
    goTo("proposal_review");
  });
  $$(".rp-progress button").forEach((button) => button.addEventListener("click", () => {
    const step = button.dataset.step;
    if (step === "recognition" && state.workflow?.canEnter("recognition")) {
      goTo(state.workflow.completed.includes("calibration") ? "calibration" : "recognition");
      return;
    }
    if (step === "layout_2d" && state.workflow?.canEnter("white_model_3d")) {
      goTo("white_model_3d");
      return;
    }
    if (state.workflow?.canEnter(step)) goTo(step);
    else setStatus(firstWorkflowBlocker(step), "error");
  }));
  $("#reset-project")?.addEventListener("click", () => {
    if (!confirm("要重新開始此專案嗎？目前頁面的本機流程狀態會清除。")) return;
    state.workflow?.reset();
    history.replaceState({}, "", "/scene");
    location.reload();
  });
  window.addEventListener("resize", syncAllOverlays);
  window.addEventListener("beforeunload", (event) => {
    if (projectExitConfirmed) return;
    if (pendingSaveCount === 0 && !localStorage.getItem(pendingSaveStorageKey())) return;
    event.preventDefault();
    event.returnValue = "";
  });
}

async function recoverSceneDataFromSavedLayout() {
  const sceneSteps = new Set([
    "white_model_3d",
    "realistic_3d",
    "proposal_review",
    "ai_render",
  ]);
  if (
    state.sceneData
    || !sceneSteps.has(state.workflow?.currentStep)
  ) return false;
  const layout = await api("/api/scene/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan_editor: confirmedFloorplanEditor(),
      placement_variant: activeSchemeId(),
      scene_objects: state.furniture2d.map((item) => toSceneFurniture(item)),
    }),
  });
  const roomSurfaces = roomSurfaceAssignments();
  state.sceneData = {
    scene_id: `${state.projectId}-restored-${activeSchemeId()}`,
    floorplan: layout.floorplan,
    scene_objects: layout.scene_objects || [],
    questionnaire: {
      catalog_version: state.visualCatalogVersion,
      basic: state.basicAnswers,
      visual_preferences: resolvedVisualPreferences(),
      finishes: state.questionnaireFinishes,
      room_requirements: state.roomRequirementModel.roomRequirements,
    },
    room_requirements: state.roomRequirementModel.roomRequirements,
    surface_overrides: roomSurfaces.map((surface) => ({
      ...surface,
      wall_option: surface.wall_material_id || "auto",
      floor_option: surface.floor_material_id || "auto",
    })),
    design_choices: {
      single_room_mode: false,
      wall_option: state.questionnaireFinishes.wallMaterial || "auto",
      wall_color_hex: state.questionnaireFinishes.wallColor || "#f2f0ec",
      floor_option: state.questionnaireFinishes.floorMaterial || "auto",
      floor_color_hex: state.questionnaireFinishes.floorColor || "#b99b78",
      ceiling_material: state.questionnaireFinishes.ceilingMaterial || "flat-paint",
      ceiling_style: state.questionnaireFinishes.ceilingStyle || "exposed",
      ceiling_color_hex: state.questionnaireFinishes.ceilingColor || "#f4f1eb",
      exterior_wall_option: "auto",
      exterior_wall_color_hex: "#e7e3dc",
    },
    style: {
      style_id: "white_model",
      palette_hex: ["#f4f1ec", "#e9e6e1", "#d8d3cc", "#bcb4aa"],
    },
    placement_resolution_report: [],
  };
  state.sceneData.scene_objects.forEach((item) => {
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      item,
      furniture2dDefaultsForSceneObject(item),
    );
  });
  persistActiveScheme(state.designSchemes, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  return true;
}

async function restoreProject() {
  if (!state.projectId) {
    state.workflow = null;
    showStep("project");
    return;
  }
  try {
    let sceneRecoveryError = null;
    let result = await api(`/api/projects/${state.projectId}`);
    const pendingSave = localStorage.getItem(pendingSaveStorageKey());
    let pendingSaveDiscarded = false;
    if (pendingSave) {
      let removePendingSave = false;
      if (shouldReplayPendingSave(pendingSave, result.project)) {
        const replayPayload = {
          ...JSON.parse(pendingSave),
          replay_pending: true,
        };
        try {
          result = await api(`/api/projects/${state.projectId}/workflow`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(replayPayload),
          });
          removePendingSave = true;
        } catch (error) {
          if (error.status !== 409) throw error;
          pendingSaveDiscarded = true;
          removePendingSave = true;
          result = await api(`/api/projects/${state.projectId}`);
        }
      } else {
        pendingSaveDiscarded = true;
        removePendingSave = true;
      }
      if (removePendingSave) localStorage.removeItem(pendingSaveStorageKey());
    }
    state.project = result.project;
    const serverState = state.project.workflow || {};
    state.workflow = restoreWorkflow({
      projectId: state.projectId,
      snapshot: serverState._flow || null,
    });
    element.projectName.value = state.project.name;
    element.projectNotes.value = state.project.notes || "";
    element.saveStatus.textContent = `已載入 · ${state.project.name}`;
    state.analysis = serverState.recognition || state.workflow.data.recognition || null;
    state.confirmedFloorplan = serverState.confirmed_floorplan || null;
    const savedCalibration = serverState.calibration || state.workflow.data.calibration || null;
    const calibrationGeometry = savedCalibration?.calibration || savedCalibration;
    state.calibrationPoints = calibrationPointsFromAnalysis(
      state.analysis,
      calibrationGeometry,
    );
    if (Number(savedCalibration?.distanceCm) > 0) {
      element.scaleInput.value = Number(savedCalibration.distanceCm);
    } else if (Number(state.analysis?.scale?.distance_cm) > 0) {
      element.scaleInput.value = Number(state.analysis.scale.distance_cm);
    } else if (Number(state.analysis?.scale?.distance_m) > 0) {
      element.scaleInput.value = Math.round(Number(state.analysis.scale.distance_m) * 1000) / 10;
    }
    if (state.analysis) {
      element.recognitionSummary.textContent = `辨識結果：牆 ${state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0}、門 ${state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0}、窗 ${state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0}`;
      element.uploadFileState.textContent =
        state.analysis.filename || state.workflow.data.upload?.filename || "已上傳平面圖";
    }
    const savedSpace = normalizeSavedSpaceConfirmation(serverState.space_confirmation || {});
    state.dismissedAutoRoomIds = Array.isArray(savedSpace.dismissed_auto_room_ids)
      ? savedSpace.dismissed_auto_room_ids
      : [];
    state.rooms = savedSpace.rooms.map((room, index) => {
      const polygon = room.polygon_cm || [];
      const shouldRepair = (
        room.polygon_source === "cody_wall_enclosure"
        && room.confirmed !== true
      );
      const repairedPolygon = shouldRepair
        ? repairLoadedRoomPolygon(polygon)
        : polygon;
      const geometryRepaired = roomPolygonsDiffer(repairedPolygon, polygon);
      const normalizedRoom = normalizeIconInferredRoomReview(room, repairedPolygon, index);
      return {
        ...normalizedRoom,
        confirmed: geometryRepaired ? false : normalizedRoom.confirmed === true,
        geometry_repaired: geometryRepaired || room.geometry_repaired === true,
        polygon_cm: repairedPolygon,
      };
    });
    state.structures = serverState.space_confirmation
      ? savedSpace.structures
      : state.structures;
    state.confirmedStructureSnapshot = hydrateConfirmedStructureSnapshot(
      serverState.space_confirmation?.confirmed_structure_snapshot || null,
      state.structures,
    );
    state.rooms = applyCanonicalRoomLabels(preparedAutoRoomLabels(state.rooms, state.structures.walls || []));
    const lockedWallCandidates = normalizeWallDemolitionCandidates();
    repairLoadedStructureWallCollisions();
    const normalizedDoors = dedupeDoorCandidates(state.structures.doors || []);
    state.structures.doors = normalizedDoors.doors;
    state.doorNormalizationRemoved = normalizedDoors.removed;
    const normalizedWindows = dedupeWindowCandidates(state.structures.windows || []);
    state.structures.windows = normalizedWindows.windows;
    state.windowNormalizationRemoved = normalizedWindows.removed;
    state.basicAnswers = serverState.requirements?.basic || {};
    state.basicConfirmed = serverState.requirements?.basicConfirmed === true;
    const savedQuestionnaireStage = serverState.requirements?.questionnaireStage;
    state.questionnaireStage = (savedQuestionnaireStage === "visual"
      ? "rooms"
      : savedQuestionnaireStage) || (
      "profile"
    );
    state.visualCatalogVersion =
      serverState.requirements?.visualCatalogVersion || null;
    state.visualAnswers = serverState.requirements?.visualAnswers || {};
    state.skippedVisualSpaceTypes =
      serverState.requirements?.skippedVisualSpaceTypes || [];
    state.roomRagJobs = serverState.requirements?.ragJobs || {};
    state.questionnaireFinishes = {
      ...state.questionnaireFinishes,
      ...(serverState.requirements?.finishes || {}),
    };
    state.roomRequirementModel = normalizeRoomRequirements(
      serverState.requirements?.roomRequirementModel || {},
      state.rooms,
      {
        basic: state.basicAnswers,
        basicConfirmed: state.basicConfirmed,
        finishes: state.questionnaireFinishes,
      },
    );
    state.roomFinishDrafts = {};
    const questionnairePack = STYLE_PACKS.find(
      (pack) => pack.id === state.questionnaireFinishes.stylePackId,
    );
    if (questionnairePack) state.activeStyleId = questionnairePack.styleId;
    const legacyFurniture = serverState.layout_2d?.furniture || [];
    const legacySceneData = normalizeSavedSceneData(serverState.white_model_3d?.sceneData);
    state.designSchemes = normalizeDesignSchemes(
      savedSpace.design_schemes || serverState.design_schemes || {},
      {
        furniture: legacyFurniture,
        sceneData: legacySceneData,
      },
    );
    if (hasRenovationChanges(state.structures) && !state.designSchemes.schemes.B) {
      ensureSchemeB(state.designSchemes, { reason: "restored_renovation" });
    }
    const savedLayoutSchemes = serverState.layout_2d?.schemes || {};
    state.designSchemes.room_selections = serverState.layout_2d?.room_selections
      || state.designSchemes.room_selections
      || {};
    state.designSchemes.configuration_snapshot = serverState.layout_2d?.configuration_snapshot
      || state.designSchemes.configuration_snapshot
      || null;
    Object.entries(savedLayoutSchemes).forEach(([schemeId, layout]) => {
      const scheme = state.designSchemes.schemes[schemeId];
      if (!scheme) return;
      scheme.furniture = layout.furniture || scheme.furniture || [];
      scheme.stale = layout.stale === true;
      scheme.staleReason = layout.staleReason || "";
    });
    const restoredSchemeB = state.designSchemes.schemes.B;
    const emptySchemeB = restoredSchemeB
      && !hasRenovationChanges(state.structures)
      && !(restoredSchemeB.furniture || []).length
      && !restoredSchemeB.sceneData;
    if (emptySchemeB) deleteSchemeB(state.designSchemes);
    const restoredScheme = activeScheme();
    state.furniture2d = restoredScheme?.furniture || legacyFurniture;
    state.sceneData = normalizeSavedSceneData(restoredScheme?.sceneData) || legacySceneData;
    applyWholeHouseSurfaceConsistency();
    const restoredWallSurfaceRepairs = Object.values(state.designSchemes.schemes || {})
      .reduce(
        (total, scheme) => total + normalizeSavedSceneWallSurfaces(scheme?.sceneData),
        0,
      ) + normalizeSavedSceneWallSurfaces(state.sceneData);
    const restoredRetiredAppliancesRemoved = pruneRetiredAppliances({ notify: true });
    const restoredSceneDoorsRemoved = normalizeSceneDoorSegments(state.sceneData);
    const restoredDoorSwingEndpoints = restoreDoorSwingEndpointsFromConfirmedStructures(
      state.sceneData,
    );
    state.doorNormalizationRemoved += restoredSceneDoorsRemoved;
    state.activeStylePackId = serverState.realistic_3d?.activeStylePackId || null;
    state.surfaceState = serverState.realistic_3d?.surfaceState || state.surfaceState;
    state.materialBoundary = serverState.realistic_3d?.materialBoundary || null;
    const savedProposal = serverState.proposal_review
      || state.workflow.data.proposal_review
      || {};
    state.proposalReview = {
      masterView: savedProposal.masterView || null,
      confirmedStyleCardId: savedProposal.confirmedStyleCardId || null,
      roomViews: savedProposal.roomViews || {},
      jobs: savedProposal.jobs || [],
      renderBriefs: savedProposal.renderBriefs || [],
    };
    state.sourceExtension = floorplanExtension({
      name: state.analysis?.filename || state.workflow.data.upload?.filename || "",
    });
    await recoverConfirmedFloorplan();
    let sceneRecoveredFromLayout = false;
    try {
      sceneRecoveredFromLayout = await recoverSceneDataFromSavedLayout();
    } catch (error) {
      sceneRecoveryError = error;
      console.warn("Unable to rebuild saved 3D scene from layout.", error);
    }
    hydrateSceneWallMass();
    state.sourceUrl = state.sourceExtension === ".dxf"
      ? configureDxfPreview(state.analysis)
      : `/api/projects/${state.projectId}/floorplan/source?v=${Date.now()}`;
    if (state.workflow.completed.includes("upload")) {
      setPlanImages(state.sourceUrl);
      showUploadedPreview(state.sourceUrl, state.sourceExtension);
    }
    showStep(state.workflow.currentStep || "project");
    await renderRestoredStep();
    if (
      state.workflow.currentStep === "layout_2d"
      && state.workflow.completed.includes("requirements")
      && !state.sceneData
    ) {
      await generateWhiteModelFromRequirements({ returnToRequirementsOnFailure: true });
    }
    if (state.confirmedFloorplan && !serverState.confirmed_floorplan) {
      scheduleSave(state.workflow.currentStep);
    }
    if (
      sceneRecoveredFromLayout
      || restoredRetiredAppliancesRemoved > 0
      || restoredWallSurfaceRepairs > 0
      || restoredDoorSwingEndpoints > 0
    ) {
      scheduleSave(state.workflow.currentStep);
    }
    if (state.structureCollisionRepairs?.moved > 0) {
      scheduleSave("space_confirmation");
      setStatus(
        `已將 ${state.structureCollisionRepairs.moved} 個貼牆的樑柱自動移至牆體內側，請重新確認。`,
      );
    }
    if (lockedWallCandidates > 0) {
      scheduleSave("space_confirmation");
      setStatus(`已自動移除 ${lockedWallCandidates} 個位於最外圍牆的可拆候選標記。`);
    }
    if (state.windowNormalizationRemoved > 0) {
      scheduleSave(state.workflow.currentStep);
    }
    if (sceneRecoveryError) {
      setStatus(
        `已恢復專案「${state.project.name}」，但 3D 場景暫時無法重建：${errorMessage(sceneRecoveryError)}`,
        "error",
      );
    } else {
      setStatus(pendingSaveDiscarded
        ? `已恢復專案「${state.project.name}」；較舊的離線暫存未覆蓋目前版本。`
        : `已恢復專案「${state.project.name}」。`);
    }
  } catch (error) {
    if (state.project && state.workflow) {
      showStep(state.workflow.currentStep || state.project.current_step || "project");
      setStatus(`專案資料已載入，但畫面還原失敗：${errorMessage(error)}`, "error");
      return;
    }
    state.projectId = null;
    state.workflow = null;
    history.replaceState({}, "", "/scene");
    showStep("project");
    setStatus(`原網址的專案無法載入：${errorMessage(error)}`, "error");
  }
}

async function recoverConfirmedFloorplan() {
  if (state.confirmedFloorplan || !state.analysis) return state.confirmedFloorplan;
  state.confirmedFloorplan = {
    floorplan: state.analysis.floorplan || state.analysis,
    dxf_text: null,
    confirmation_status: state.workflow?.completed.includes("space_confirmation")
      ? "space_reviewed"
      : "room_review_pending",
  };
  return state.confirmedFloorplan;
}

bindEvents();
renderFurnitureLibrary();
renderStyleControls();
evaluateCeilingConflicts();
restoreProject();
