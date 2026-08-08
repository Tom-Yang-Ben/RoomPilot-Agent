// 必須排在其他 import 之前：這個模組會接管 window.fetch 以附加身分並在
// access token 過期時自動續期，晚載入的話最早幾個請求會漏掉 Authorization。
import { authorizedObjectUrl, requireSignedIn } from "./auth_client.js?v=sha256-b35a4ff11b37";
import { createSceneViewer } from "./scene_viewer.js?v=sha256-2440063ba2ee";
import { repairMojibakeDeep } from "./scene_text_encoding.js?v=sha256-9693c47a7d4c";
import {
  alignOptionWithCatalogSurface,
  resolveSurfaceOption,
} from "./scene_surface_materials.js?v=sha256-76c03a72e265";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-3f3f1160d1ae";
import {
  repairLoadedRoomPolygon,
} from "./scene_room_geometry.js?v=sha256-7f4dd7c4d6d8";
import {
  clipPolygonByLine,
  convexHull,
  nearestPointOnLine,
  nearestPointOnRoomEdge,
  nearestPointOnSegment,
  pointInPolygonCm,
  polygonArea,
  roomCenter,
  roomDimensions,
  roomPolygonsDiffer,
  scenePointCoordinates,
  segmentEndpoint,
  segmentOverlapsBounds,
  shiftFloorplanRegion,
  shiftRoomSurfaceAssignment,
  shiftScenePoint,
  shiftSceneSegment,
} from "./scene_plan_geometry.js?v=sha256-52ddaf293063";
import {
  createWorkflow,
  restoreWorkflow,
  safeStorageGetItem,
  safeStorageRemoveItem,
  safeStorageSetItem,
  shouldReplayPendingSave,
  WORKFLOW_PANEL_BY_STEP,
  WORKFLOW_STEPS,
} from "./scene_workflow.js?v=sha256-13a58f49a774";
import {
  buildScaleCalibration,
  calibrationActionState,
} from "./scene_calibration.js?v=sha256-a1eb97980af1";
import {
  reviewItemsFromAnalysis,
  reviewReasonLabel,
  unresolvedReviewRooms,
} from "./scene_recognition_review.js?v=sha256-14ba9b03b7c5";
import {
  findHostAt,
  hostSurfaceHeightCm,
  isTabletopType,
  pointWithinItemFootprint,
} from "./scene_tabletop_hosts.js?v=sha256-aac5f0a9d335";
import {
  createFurniture2DItem,
  FAMILIES_WITHOUT_CATALOG_MODELS,
  FURNITURE_2D_LIBRARY,
  findFurniture2DVariant,
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  planCmToLayerPixel,
  recommendCompanionFurniture,
  recommendedFurnitureForRoom,
  roomTypeFromName,
  mergeCatalogFurniture,
  replaceFurniture2DItem,
  toSceneFurniture,
} from "./scene_layout2d.js?v=sha256-23d4de37dcfe";
import {
  furniture2dItemForSceneObject,
  removeFurniture2dBySceneObject,
  upsertFurniture2dFromSceneObject,
} from "./scene_configuration_sync.js?v=sha256-579f9d6450b9";
import {
  rankCatalogFurniture,
} from "./scene_furniture_retrieval.js?v=sha256-6772c0c167b3";
import {
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-097f1470f5a3";
import {
  finishesGate,
  occupantsFromBasicAnswers,
  visualQuestionnaireProgress,
} from "./scene_questionnaire_test2.js?v=sha256-8a2cbc61a6b0";
import {
  reloadViewerPreservingState,
} from "./scene_viewer_reload.js?v=sha256-1106dd5bbffb";
import {
  clampRoomCamera,
  roomCameraSuggestion as roomCameraSuggestionCm,
  validateRoomCamera,
} from "./scene_camera.js?v=sha256-e8adcedc1a87";
import {
  buildRoomRequirementsPayload,
  conditionalOptionId,
  normalizeRoomRequirements,
} from "./scene_room_requirements.js?v=sha256-b474fd6b8d20";
import {
  applyStylePack,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_FAMILIES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-fd8fa1eb64b1";
import {
  FIRST_MEETING_STEPS,
  firstMeetingReady,
  firstMeetingStepStatus,
  normalizeFirstMeeting,
} from "./scene_first_meeting.js?v=sha256-ed5e5f907eaa";
import {
  beamDragGeometry,
  canMarkWallForDemolition,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  translateOpeningAlongAxis,
  wallBoundarySide,
  windowsOverlap,
} from "./scene_structure_utils.js?v=sha256-41e8428ea1c8";
import { createStructurePreview } from "./scene_structure_preview.js?v=sha256-6f10ad692850";
import {
  findStructureWallCollision,
  resolveStructureWallCollisions,
  validateColumnDimensionsCm,
} from "./scene_structure_geometry.js?v=sha256-4eacbec619c5";
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
} from "./scene_design_schemes.js?v=sha256-bcbecaeee6d9";
import {
  CATALOG_RETRIEVAL_ROUTES,
  QUESTIONNAIRE_STAGES,
  RENDER_DETAIL_FIELDS,
  REPLACEMENT_TYPE_LABELS,
  ROOM_QUESTIONNAIRE_SECTIONS,
  isCirculationRoom,
  preferenceWeightLabel,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureSelectionItem,
  questionnaireMaterialOptionsForPack,
  questionnaireMaterialPairsForPack,
  randomRoomAxisNote,
  specsAllowedByRoomFeasibility,
  specsFromSelectionResponse,
  styleCatalogLabel,
  surfaceMaterialLabel,
  surfacePhrase,
  uniqueMaterialOptions,
} from "./scene_questionnaire_data.js?v=sha256-17c7e0ecc752";
import {
  createQuestionnaireFlow,
} from "./scene_questionnaire_flow.js?v=sha256-751a71d2e88d";
import {
  createFurnitureOffers,
} from "./scene_furniture_offers.js?v=sha256-c6cab2e6d4cc";

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

// 空間名稱與辨識層的類別集對齊（backend/floorplan/floorplan2room.py 的 ROOM_ZH_EX：
// living / kitchen / bed / bath / balcony / entry / storage / garage / outdoor / stair）。
// 餐廳與書房辨識層本來就標不出來，已移除；書房系詞彙在 2026-07-29 就已併入儲藏室。
// 主臥與次臥合併成單一臥室——辨識層只有一個 bed 類，主次仍由第 5 步問卷依面積推導。
// 走道辨識層沒有對應類別，維持 circulation 型別以沿用「走道跟隨客廳風格」的既有行為。
const ROOM_NAME_OPTIONS = Object.freeze([
  { id: "entryway", label: "玄關", type: "circulation" },
  { id: "living_room", label: "客廳", type: "living_room" },
  { id: "kitchen", label: "廚房", type: "kitchen" },
  { id: "bedroom", label: "臥室", type: "bedroom" },
  { id: "bathroom", label: "浴室", type: "bathroom" },
  { id: "balcony", label: "陽台", type: "balcony" },
  { id: "storage", label: "儲藏室", type: "storage" },
  { id: "hallway", label: "走道", type: "circulation" },
  { id: "stair", label: "樓梯", type: "circulation" },
  { id: "garage", label: "車庫", type: "storage" },
]);

// 7242f0bf 收斂房名時給玄關／樓梯／車庫配了 entry／stair／garage 三個新 type，
// 但正典 vision/analysis.ROOM_LABELS 只有九類，SPACE_DEFAULTS 也沒有這三個鍵
// ——normalize_required_furniture 表外即退成客廳家具，玄關會被塞沙發。
// 這裡把三者併回正典：玄關與樓梯歸 circulation（預設零家具，且沿用「走道跟隨
// 客廳風格」），車庫歸 storage（storage-cabinet）。顯示名稱仍是十類。
const LEGACY_ROOM_TYPES = Object.freeze({
  entry: "circulation",
  stair: "circulation",
  garage: "storage",
});

// 舊專案存下來的 visual_space_type 仍要認得，否則回頭開會掉成預設值。
const LEGACY_ROOM_NAME_IDS = Object.freeze({
  primary_bedroom: "bedroom",
  secondary_bedroom: "bedroom",
  circulation: "hallway",
  dining_room: "living_room",
  study: "storage",
  multi_purpose: "hallway",
});

function roomNameOptionFor(room = {}) {
  const rawSelected = String(room.visual_space_type || "");
  const selected = LEGACY_ROOM_NAME_IDS[rawSelected] || rawSelected;
  const label = String(room.label || room.name || "");
  const type = String(room.type || room.room_type || "");
  return ROOM_NAME_OPTIONS.find((option) => option.id === selected)
    || ROOM_NAME_OPTIONS.find((option) => option.label === label)
    || ROOM_NAME_OPTIONS.find((option) => option.type === type)
    // 辨識層分不出來的空間（它的 room／空間 類）落到走道，會沿用客廳風格。
    || ROOM_NAME_OPTIONS.find((option) => option.id === "hallway");
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
  selectedStructure: null,
  windowNormalizationRemoved: 0,
  basicAnswers: {},
  basicConfirmed: false,
  questionnaireStage: "profile",
  roomRequirementModel: normalizeRoomRequirements(),
  roomFinishDrafts: {},
  roomFurnitureRecommendations: {},
  roomFurnitureRecommendationErrors: {},
  selectedQuestionnaireWallId: null,
  // 圖片式視覺問卷已拆除；以下欄位保留給舊專案 workflow 存檔的相容性
  // （workflowPayload 仍序列化這三個鍵，restore 也會讀回），值恆為空。
  visualCatalogVersion: null,
  visualQuestions: [],
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
  furnitureLedger: { order: [], removed: [] },
  selectedFurniture2dId: null,
  // 第 6 步與 2D 同步平面共用的家具編號；僅第 6 步顯示，第 7 步視角不得出現。
  showFurnitureNumbers: true,
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
  },
  selectedRenderRoomId: null,
  selectedProposalRoomId: null,
  selectedProposalRoomCandidateIndex: 0,
  selectedRoomSchemeId: null,
};
let styleApplyRevision = 0;
const proposalRoomPreviewCache = new Map();
// 逐房方案 3D 預覽快取：鍵為 `${schemeId}:${roomId}`（bella-test1 23de9dda）。
const roomSchemePreviewCache = new Map();
let roomSchemePreviewInFlight = null;
let roomSchemeAlternativeInFlight = null;
let confirmRequirementsInFlight = false;
const apiRequestsInFlight = new Map();
// 問卷家具型錄瀏覽模式（questionnaire-catalog-space-groups）。
let questionnaireCatalogRoomId = null;
let questionnaireCatalogScope = "room";
let questionnaireCatalogSpace = "";
let questionnaireCatalogPurpose = "";
const configurationReflowInFlight = new Set();
let configurationPendingClickToken = 0;
let configurationPendingHandledToken = -1;
let configurationPendingPointerDown = false;
let deferredConfigurationPendingMarkup = null;

const panels = new Map(
  $$(".rp-step-panel").map((panel) => [panel.dataset.panel, panel]),
);

const instructions = {
  project: ["步驟 1", "先建立專案，之後每一次確認都會自動保存"],
  upload: ["步驟 2", "選擇 DXF、PNG 或 JPG，並確認圖檔內容"],
  recognition: ["步驟 3", "確認圖面比例，讓後續房間尺寸更準確"],
  calibration: ["步驟 3", "確認尺度後，才會顯示辨識到的房間"],
  space_confirmation: ["步驟 4", "先確認房間，再確認牆、門、窗、樑與柱"],
  requirements: ["步驟 5", "與客戶完成六題初談，確認設計優先順序與風格方向"],
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
  recognitionReviewSummary: $("#recognition-review-summary"),
  recognitionReviewList: $("#recognition-review-list"),
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
  savedRendersList: $("#saved-renders-list"),
  savedRendersCount: $("#saved-renders-count"),
  roomArea: $("#room-area"),
  roomConfirmationProgress: $("#room-confirmation-progress"),
  currentRoomReview: $("#current-room-review"),
  currentRoomStatus: $("#current-room-status"),
  skipCurrentRoom: $("#skip-current-room"),
  confirmCurrentRoom: $("#confirm-current-room"),
  roomGeometryGuidance: $("#room-geometry-guidance"),
  roomNodeGuidance: $("#room-node-guidance"),
  structureCounts: $("#structure-counts"),
  doorReviewList: $("#structure-review-list"),
  structureEditor: $("#selected-structure-editor"),
  openingWidthSlider: $("#opening-width-slider"),
  openingWidthValue: $("#opening-width-value"),
  spaceError: $("#space-error"),
  spaceCompletionSummary: $("#space-completion-summary"),
  spaceCompletionHint: $("#space-completion-hint"),
  confirmSpace: $("#confirm-space"),
  wholeHouseFields: $("#whole-house-fields"),
  firstMeetingProgress: $("#first-meeting-progress"),
  firstMeetingPanel: $("#first-meeting-panel"),
  firstMeetingBack: $("#first-meeting-back"),
  firstMeetingNext: $("#first-meeting-next"),
  firstMeetingStatus: $("#first-meeting-status"),
  firstMeetingTime: $("#first-meeting-time"),
  firstMeetingGuideText: $("#first-meeting-guide-text"),
  firstMeetingError: $("#first-meeting-error"),
  wholeHouseStyleTabs: $("#whole-house-style-tabs"),
  wholeHouseStyleGrid: $("#whole-house-style-grid"),
  wholeHouseStyleSelection: $("#whole-house-style-selection"),
  renderDetailBox: $("#render-detail-box"),
  renderDetailIndirectLight: $("#render-detail-indirect-light"),
  renderDetailCeilingZoning: $("#render-detail-ceiling-zoning"),
  renderDetailAirflowStrategy: $("#render-detail-airflow-strategy"),
  renderDetailServiceVisibility: $("#render-detail-service-visibility"),
  renderDetailCeilingFan: $("#render-detail-ceiling-fan"),
  renderDetailApplianceVisibility: $("#render-detail-appliance-visibility"),
  requirementsProgress: $("#requirements-progress"),
  requirementsError: $("#requirements-error"),
  randomizeRequirements: $("#randomize-requirements"),
  confirmRequirements: $("#confirm-requirements"),
  questionnaireStageNav: $("#questionnaire-stage-nav"),
  roomQuestionnaireSectionNav: $("#room-questionnaire-section-nav"),
  visualSpaceNav: $("#visual-space-nav"),
  visualQuestionCard: $("#visual-question-card"),
  questionnaireStyleTabs: $("#questionnaire-style-tabs"),
  questionnaireStyleGrid: $("#questionnaire-style-grid"),
  questionnaireMaterialPairs: $("#questionnaire-material-pairs"),
  questionnaireWallOptions: $("#questionnaire-wall-options"),
  questionnaireFloorOptions: $("#questionnaire-floor-options"),
  questionnaireWallColor: $("#questionnaire-wall-color"),
  questionnaireWallPreference: $("#questionnaire-wall-preference"),
  questionnaireFloorPreference: $("#questionnaire-floor-preference"),
  questionnaireCeilingMaterial: $("#questionnaire-ceiling-material"),
  questionnaireCeilingStyle: $("#questionnaire-ceiling-style"),
  questionnaireLightStyle: $("#questionnaire-light-style"),
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
  roomSchemeDialog: $("#room-scheme-selection-dialog"),
  roomSchemeList: $("#room-scheme-list"),
  roomSchemeStatus: $("#room-scheme-status"),
  roomSchemeChoiceGrid: $("#room-scheme-choice-grid"),
  roomSchemeWarning: $("#room-scheme-warning"),
  roomSchemeComplete: $("#room-scheme-complete"),
  roomScheme3dPreviewDialog: $("#room-scheme-3d-preview-dialog"),
  roomScheme3dPreviewTitle: $("#room-scheme-3d-preview-title"),
  roomScheme3dPreviewStatus: $("#room-scheme-3d-status"),
  configurationPlanPanel: $("#configuration-plan-panel"),
  configurationPlanToggle: $("#configuration-plan-toggle"),
  configurationPlanStage: $(".rp-configuration-plan-stage"),
  configurationPlanImage: $("#configuration-plan-image"),
  configurationPlanLayer: $("#configuration-plan-furniture-layer"),
  configurationPlanFurnitureList: $("#configuration-plan-furniture-list"),
  configurationPendingCount: $("#configuration-pending-count"),
  configurationPendingList: $("#configuration-pending-list"),
  objectList: $("#scene-object-list"),
  realisticObjectList: $("#realistic-scene-object-list"),
  glbResults: $("#glb-search-results"),
  questionnaireCatalogControls: $("#questionnaire-catalog-controls"),
  questionnaireCatalogType: $("#questionnaire-catalog-type"),
  questionnaireCatalogColor: $("#questionnaire-catalog-color"),
  questionnaireCatalogMaterial: $("#questionnaire-catalog-material"),
  questionnaireCatalogSpaceGroups: $("#questionnaire-catalog-space-groups"),
  questionnaireCatalogPurposeGroups: $("#questionnaire-catalog-purpose-groups"),
  realisticStatus: $("#realistic-status"),
  styleFamilyNote: $("#style-pack-family"),
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
  aiRenderError: $("#ai-render-error"),
  aiRenderTechnicalDetails: $("#ai-render-technical-details"),
  aiRenderTechnicalError: $("#ai-render-technical-error"),
  proposalReviewError: $("#proposal-review-error"),
  aiRenderViewTitle: $("#ai-render-view-title"),
  aiRenderProviderState: $("#ai-render-provider-state"),
  aiRenderCurrentRoom: $("#ai-render-current-room"),
  aiRenderTaskState: $("#ai-render-task-state"),
  aiRenderRoomProgress: $("#ai-render-room-progress"),
  aiRenderTabs: $(".rp-ai-render-tabs"),
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
  showFurnitureNames: false,
  furnitureAnnotationNumber: (item, index) => configurationSceneObjectNumber(item, index),
});
// 風格、提案、生圖與更換預覽都是給人看成果的，不掛編號與名稱標籤；
// 第 6 步白模只保留編號，名稱由右側清單對照，避免遮住家具與動線。
const realisticViewer = createSceneViewer($("#realistic-viewer"), element.realisticStatus, {
  onSceneChange: () => markRealisticSceneEdited(),
  onObjectSelect: (item) => syncSceneSelectionTo2dFurniture(item),
  showFurnitureAnnotations: false,
});
const proposalViewer = createSceneViewer(
  $("#proposal-review-viewer"),
  element.proposalReviewStatus,
  { showFurnitureAnnotations: false },
);
const aiRenderViewer = createSceneViewer($("#ai-render-viewer"), element.aiRenderStatus, {
  showFurnitureAnnotations: false,
});
const replacementViewer = createSceneViewer(
  $("#replacement-3d-preview"),
  element.replacement3dStatus,
  { showFurnitureAnnotations: false },
);
const glbThumbnailViewer = createSceneViewer(
  $("#glb-thumbnail-viewer"),
  $("#glb-thumbnail-status"),
);
// 逐房方案 3D 預覽彈窗的可旋轉 viewer（room-scheme-3d-preview-dialog）。
const roomSchemePreviewViewer = createSceneViewer(
  $("#room-scheme-3d-preview"),
  element.roomScheme3dPreviewStatus,
  { showFurnitureAnnotations: false },
);
const structurePreview = createStructurePreview($("#structure-3d-preview"));
const styleFurnitureCache = new Map();
const glbThumbnailCache = new Map();
const verifiedCatalogModelUrls = new Set();
const unavailableCatalogModelUrls = new Set();
let glbThumbnailBatch = 0;
let glbThumbnailSequence = Promise.resolve();

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
  const method = String(options.method || "GET").toUpperCase();
  const shouldDedupe = (method === "GET" && (
    url === "/api/scene/bootstrap" || url.startsWith("/api/furniture?")
  )) || (method === "POST" && url === "/api/scene/layout");
  const requestKey = shouldDedupe
    ? `${method}:${url}:${typeof options.body === "string" ? options.body : ""}`
    : "";
  if (requestKey && apiRequestsInFlight.has(requestKey)) {
    return apiRequestsInFlight.get(requestKey);
  }
  const request = (async () => {
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
  })();
  if (requestKey) apiRequestsInFlight.set(requestKey, request);
  try {
    return await request;
  } finally {
    if (requestKey && apiRequestsInFlight.get(requestKey) === request) {
      apiRequestsInFlight.delete(requestKey);
    }
  }
}

function sceneDataFromGenerateResponse(payload) {
  const scene = payload?.scene_json || payload;
  if (!scene || typeof scene !== "object" || !Array.isArray(scene.scene_objects)) {
    throw new Error("場景資料尚未完成，系統不會載入半成品；請稍後重試。");
  }
  return scene;
}

// 與後端 `backend/server/catalog_vocabulary.py` 的 `APPLIANCE_TYPES` 同一份，
// 由 tests/test_appliance_boundary_contract.py 綁住。前 15 個是型錄實際用語
// （`kind == "appliance"` 的 type ＋ style_db 的 microwave/iron），後 6 個是舊
// payload 仍帶得出來的舊名字。先前這裡只有舊名字那半邊。
const RETIRED_APPLIANCE_TYPES = new Set([
  "air-conditioner",
  "air-purifier",
  "dishwasher",
  "electric-fan",
  "extractor-hood",
  "fridge-freezer",
  "hair-dryer",
  "iron",
  "microwave",
  "oven",
  "robot-vacuum",
  "small-kitchen-appliance",
  "toaster",
  "vacuum-cleaner",
  "washing-machine",
  "appliance",
  "ceiling-cassette",
  "dryer",
  "range-hood",
  "refrigerator",
  "washer",
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

function restoreDoorSwingEndpointsFromConfirmedStructures(sceneData) {
  const floorplan = sceneData?.floorplan;
  const sceneDoors = floorplan?.door_segments || [];
  const confirmedDoors = state.structures?.doors || [];
  if (!sceneDoors.length || !confirmedDoors.length) return 0;

  const halfWidth = Number(floorplan.width_cm) / 2;
  const halfDepth = Number(floorplan.depth_cm) / 2;
  if (!Number.isFinite(halfWidth) || !Number.isFinite(halfDepth)) return 0;
  const sourceById = new Map(confirmedDoors.map((door) => [String(door.id), door]));
  let repaired = 0;

  sceneDoors.forEach((door) => {
    const source = sourceById.get(String(door.id));
    if (!source?.swing_end) return;
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

// catalogFurnitureId 是型錄產品編號，不是實例識別碼：兩個房間放同一款床就會共用。
// 以前把它和實例 id 混在同一組比對，兩件家具會指到同一個 scene object——側欄編號
// 重複，「定位」與「移除此家具」也會選到別間房的那件。實例 id 優先，型錄編號只在
// 唯一命中時才採信。
function sceneObjectIndexByFurnitureId(furnitureId) {
  if (!furnitureId || !state.sceneData?.scene_objects?.length) return -1;
  const id = String(furnitureId);
  const objects = state.sceneData.scene_objects;
  const layoutItem = state.furniture2d.find(
    (item) => String(item.id) === id,
  );
  const instanceIds = new Set(
    [id, layoutItem?.furniture_id].filter(Boolean).map(String),
  );
  const sceneInstanceIds = (item) => [
    item.furniture_id,
    item.layout_furniture_id,
    item.source_furniture_id,
    item.id,
  ].filter(Boolean).map(String);
  const exact = objects.findIndex(
    (item) => sceneInstanceIds(item).some((candidate) => instanceIds.has(candidate)),
  );
  if (exact >= 0) return exact;
  const catalogId = layoutItem?.catalogFurnitureId
    ? String(layoutItem.catalogFurnitureId)
    : "";
  if (!catalogId) return -1;
  const catalogMatches = objects.reduce((found, item, index) => {
    const ids = [item.catalog_furniture_id, item.catalogFurnitureId]
      .filter(Boolean)
      .map(String);
    return ids.includes(catalogId) ? [...found, index] : found;
  }, []);
  return catalogMatches.length === 1 ? catalogMatches[0] : -1;
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

// ── 第 6 步側欄分頁與家具編號開關（bella-test1 23de9dda UI 部分移植）────────
function setSceneSidebarTab(tab = "plan") {
  const sidebar = $(".rp-3d-sidebar", panels.get("white-model-3d") || document);
  if (!sidebar) return;
  const nextTab = ["plan", "issues", "selection"].includes(tab) ? tab : "plan";
  sidebar.dataset.sceneSidebarMode = nextTab;
  $$("[data-scene-sidebar-tab]", sidebar).forEach((button) => {
    const selected = button.dataset.sceneSidebarTab === nextTab;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
}

function syncFurnitureNumberVisibility() {
  const button = $("#toggle-furniture-numbers");
  if (button) {
    button.classList.toggle("is-active", state.showFurnitureNumbers);
    button.setAttribute("aria-pressed", String(state.showFurnitureNumbers));
    button.textContent = state.showFurnitureNumbers ? "隱藏編號" : "顯示編號";
  }
  // 第 6 步是全屋總覽：走動房間選單不過濾編號（roomId 可能與 scene 物件不同）。
  // 編號僅第 6 步的 whiteViewer 開啟；第 7 步 proposalViewer 從不呼叫，維持乾淨視角。
  whiteViewer?.setFurnitureNumberMarkersVisible?.(state.showFurnitureNumbers);
  renderConfigurationPlan();
}

function syncSceneSelectionTo2dFurniture(sceneObject) {
  const item = furniture2dItemForSceneObject(state.furniture2d, sceneObject);
  if (!item) return false;
  state.selectedFurniture2dId = item.id;
  renderLayoutFurniture();
  renderConfigurationPlan();
  if (state.workflow?.currentStep === "white_model_3d") {
    setSceneSidebarTab("selection");
  }
  return true;
}

function syncMovedSceneFurnitureTo2d(sceneObject) {
  if (!furniture2dItemForSceneObject(state.furniture2d, sceneObject)) return false;
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
    || state.firstMeeting?.started === true
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
          dismissed_auto_room_ids: state.dismissedAutoRoomIds,
          design_schemes: compactDesignSchemesForSpace(state.designSchemes),
        }
      : null,
    requirements: requirementsAreLive
      ? {
          basic: state.basicAnswers,
          basicConfirmed: state.basicConfirmed,
          firstMeetingStep: state.firstMeetingStep,
          firstMeeting: state.firstMeeting,
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
          furniture: state.furniture2d,
          furniture_ledger: state.furnitureLedger,
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
  safeStorageSetItem(localStorage, pendingSaveStorageKey(), serialized);
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
      const latestPending = safeStorageGetItem(localStorage, pendingKey);
      const latestPayload = latestPending ? JSON.parse(latestPending) : null;
      const savedPayload = JSON.parse(serialized);
      const savedLatest = latestPayload?.save_id
        ? latestPayload.save_id === savedPayload.save_id
        : latestPending === serialized;
      if (savedLatest) {
        safeStorageRemoveItem(localStorage, pendingKey);
      } else if (latestPending) {
        latestPayload.base_updated_at = state.project.updated_at;
        safeStorageSetItem(localStorage, pendingKey, JSON.stringify(latestPayload));
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
  if (pendingKey && safeStorageGetItem(localStorage, pendingKey)) {
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
  persistActiveScheme(state.designSchemes, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  const schemeB = ensureSchemeB(state.designSchemes, { reason: "structure_edit" });
  schemeB.stale = true;
  schemeB.staleReason = message || "方案 B 結構已變更，請重新配置家具。";
  schemeB.sceneData = null;
  if (activeSchemeId() === "B") state.sceneData = null;
  if (state.designSchemes.locked_scheme_id === "B") {
    state.designSchemes.locked_scheme_id = null;
    state.proposalReview = {
      masterView: null,
      confirmedStyleCardId: null,
      roomViews: {},
      jobs: [],
    };
    state.selectedRenderRoomId = null;
  }
  state.workflow?.invalidateFrom?.("space_confirmation");
  renderSchemeControls();
  if (message) setStatus(message);
}

function ensureRenovationScheme(reason = "structure_edit") {
  const scheme = ensureSchemeB(state.designSchemes, { reason });
  renderSchemeControls();
  renderSchemeComparison();
  return scheme;
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
  // 已載入專案時第 1 步的按鈕語意是「繼續」不是「再建一個」。
  const createProjectButton = $("#create-project");
  if (createProjectButton) {
    createProjectButton.textContent = state.projectId ? "繼續此專案" : "建立專案並繼續";
  }
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
    // 第 6 步入口：先逐房確認已保存的 A/B 方案選擇（規格 §進入順序）。
    queueMicrotask(promptRoomSchemeSelection);
  }
  if (step === "proposal_review") void prepareProposalReview();
  if (step === "ai_render") void prepareAiRender();
  if (step === "white_model_3d") {
    renderWhiteWalkRoomSelector();
    renderConfigurationPlan();
    setSceneSidebarTab("plan");
    syncFurnitureNumberVisibility();
    // 專案復原可能直接落在 white_model_3d：這裡再確認一次，逐房比較不會被略過。
    queueMicrotask(promptRoomSchemeSelection);
  }
  const currentPublicStep = publicWorkflowStep(step);
  document.body.dataset.workflowStep = currentPublicStep;
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
  }
  renderRooms();
  renderStructureCounts();
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
    if (state.surfaceState.wall?.material) $("#wall-material").value = state.surfaceState.wall.material;
    if (state.surfaceState.floor?.material) $("#floor-material").value = state.surfaceState.floor.material;
    // 套用範圍跟著存檔走：不還原的話重載後會退回「選取房間」，
    // 使用者以為改全屋，實際只改到第一個房間。
    const savedSurfaceScope = state.surfaceState.floor?.scope || state.surfaceState.wall?.scope;
    if (savedSurfaceScope) $("#surface-scope").value = savedSurfaceScope;
    if (state.materialBoundary) {
      const boundaryRoom = state.rooms.find((room) => room.id === state.materialBoundary.roomId);
      $("#material-boundary-direction").value = state.materialBoundary.direction || "vertical";
      $("#material-boundary-position").value = Math.round(
        Number(state.materialBoundary.ratio ?? 0.5) * 100,
      );
      if (state.materialBoundary.secondary_floor_id) {
        $("#material-boundary-secondary").value = state.materialBoundary.secondary_floor_id;
      }
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
  // URL 已帶專案時這顆按鈕是「繼續」，不是再建一個——2026-08-03 QA 實測
  // 每按一次就多一個同名專案。要開新專案請走「我的專案」。
  if (state.projectId && state.project) {
    // 從「我的專案」建立的專案會停在第 1 步且未標記完成；不補完成就
    // goTo("upload") 會被工作流的前置檢查默默拒絕（2026-08-03 實走發現）。
    if (!state.workflow.completed.includes("project")) {
      state.workflow.complete("project", { name: state.project.name });
      scheduleSave("upload");
    }
    setStatus(`繼續專案「${state.project.name}」；要開新專案請回「我的專案」。`);
    goTo(state.workflow.currentStep === "project" ? "upload" : state.workflow.currentStep);
    return;
  }
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
    // 平面圖端點需要身分，而 <img src> 由瀏覽器直接發請求不會帶 token；
    // 先用帶身分的 fetch 取回再轉 blob URL。
    state.sourceUrl = await authorizedObjectUrl(
      `${uploaded.upload.source_url}?v=${Date.now()}`,
      { cacheKey: `floorplan:${state.projectId}` },
    );
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
    const scaleEvidence = (state.analysis.evidence || []).find(
      (item) => Array.isArray(item.start_px) && Array.isArray(item.end_px),
    );
    if (scaleEvidence) {
      state.calibrationPoints = [
        { x: Number(scaleEvidence.start_px[0]), y: Number(scaleEvidence.start_px[1]) },
        { x: Number(scaleEvidence.end_px[0]), y: Number(scaleEvidence.end_px[1]) },
      ];
    } else {
      state.calibrationPoints = [];
    }
    if (state.sourceExtension === ".dxf") {
      state.sourceUrl = configureDxfPreview(state.analysis);
    }
    setPlanImages(state.sourceUrl);
    const count = {
      walls: state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0,
      doors: state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0,
      windows: state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0,
    };
    element.recognitionSummary.textContent = `辨識結果：牆 ${count.walls}、門 ${count.doors}、窗 ${count.windows}${recognitionReviewSuffix()}`;
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
  const altById = {
    "floorplan-calibration-image": "待標示比例的平面圖",
    "space-plan-image": "待確認空間範圍的平面圖",
    "layout-plan-image": "2D 家具配置平面圖",
    "questionnaire-plan-image": "逐房需求平面圖",
  };
  [element.scaleImage, element.spaceImage, element.layoutImage]
    .concat(element.questionnairePlanImage)
    .filter(Boolean)
    .forEach((image) => {
      image.src = url;
      image.alt = altById[image.id] || "專案平面圖";
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

let overlaySyncFrame = null;
let planStageResizeObserver = null;

function scheduleOverlaySync() {
  if (overlaySyncFrame != null) return;
  overlaySyncFrame = requestAnimationFrame(() => {
    overlaySyncFrame = null;
    syncAllOverlays();
  });
}

function observePlanStageResizes() {
  if (typeof ResizeObserver !== "function" || planStageResizeObserver) return;
  planStageResizeObserver = new ResizeObserver(scheduleOverlaySync);
  [
    element.scaleStage,
    element.spaceStage,
    element.dimensionPlanStage,
    element.layoutStage,
    element.questionnairePlanStage,
  ].filter(Boolean).forEach((stage) => planStageResizeObserver.observe(stage));
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
    ? `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="#806958" stroke-width="5" stroke-dasharray="12 7"/>`
    : "";
  const points = state.calibrationPoints.map((point, index) => `
    <circle data-calibration-point="${index}" cx="${point.x}" cy="${point.y}" r="12"
      fill="#fffdf9" stroke="${index ? "#806958" : "#2b2927"}" stroke-width="6"/>
  `).join("");
  element.scaleOverlay.innerHTML = `${line}${points}`;
  if (start && end) {
    const pixels = Math.hypot(end.x - start.x, end.y - start.y);
    element.calibrationReadout.textContent = pixels > 0
      ? `兩個端點已選好，圖上距離 ${pixels.toFixed(1)} px；仍可拖曳微調。`
      : "兩個端點重疊，請拖曳其中一點。";
  } else if (start) {
    element.calibrationReadout.textContent = "起點已選好，請再點一下終點。";
  } else {
    element.calibrationReadout.textContent = "請先在圖面點選起點。";
  }
  updateCalibrationAction();
}

function setCalibrationTaskState(task, status, stateName, label) {
  task.classList.toggle("is-active", stateName === "active");
  task.classList.toggle("is-complete", stateName === "complete");
  task.classList.toggle("is-pending", stateName === "pending");
  if (stateName === "active") task.setAttribute("aria-current", "step");
  else task.removeAttribute("aria-current");
  status.textContent = label;
}

function updateCalibrationAction({ showMessage = true } = {}) {
  const action = calibrationActionState(
    state.calibrationPoints,
    element.scaleInput.value,
  );
  const [start, end] = state.calibrationPoints;
  const pixelDistance = start && end
    ? Math.hypot(end.x - start.x, end.y - start.y)
    : 0;
  const pointsReady = state.calibrationPoints.length === 2 && pixelDistance > 0;
  const measurementReady = pointsReady && Number(element.scaleInput.value) > 0;

  element.scaleInput.disabled = !pointsReady;
  element.resetCalibration.hidden = state.calibrationPoints.length === 0;
  setCalibrationTaskState(
    element.calibrationPointTask,
    element.calibrationPointStatus,
    pointsReady ? "complete" : "active",
    pointsReady ? "完成" : "進行中",
  );
  setCalibrationTaskState(
    element.calibrationMeasureTask,
    element.calibrationMeasureStatus,
    measurementReady ? "complete" : pointsReady ? "active" : "pending",
    measurementReady ? "完成" : pointsReady ? "進行中" : "待選點",
  );
  setCalibrationTaskState(
    element.calibrationConfirmTask,
    element.calibrationConfirmStatus,
    action.ready ? "active" : "pending",
    action.ready ? "可確認" : "待完成",
  );
  element.applyCalibration.disabled = !action.ready;
  if (showMessage) {
    element.scaleError.textContent = pointsReady ? action.message : "";
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

async function applyCalibration() {
  const action = updateCalibrationAction();
  if (!action.ready) {
    if (state.calibrationPoints.length === 2) element.scaleInput.focus();
    return;
  }
  const distanceCm = Number(element.scaleInput.value);
  try {
    const calibration = buildScaleCalibration(state.calibrationPoints, distanceCm);
    setStatus("正在依確認的公分尺度重新計算房間與結構…");
    if (state.sourceExtension !== ".dxf") {
      const sourceResponse = await fetch(`/api/projects/${state.projectId}/floorplan/source`);
      const sourceBlob = await sourceResponse.blob();
      const form = new FormData();
      form.append("file", new File([sourceBlob], state.pendingFile?.name || "floorplan.png", {
        type: sourceBlob.type || "image/png",
      }));
      form.append("calibration_json", JSON.stringify(calibration));
      const analyzed = await api("/api/floorplan/analyze", { method: "POST", body: form });
      state.analysis = analyzed.analysis;
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
    structures: structuresForScheme(state.structures, schemeId),
  };
}

function confirmedRoomHeightCm() {
  return Math.max(210, Number(confirmedFloorplanEditor().room_height_cm) || 270);
}

async function refreshRestoredFloorplanStructure() {
  const floorplan = state.sceneData?.floorplan;
  if (!floorplan) return false;
  if (floorplan.wall_polys_openings_cut === true) return false;
  const confirmedPolys = state.confirmedFloorplan?.floorplan?.wall_polys || [];
  if (!floorplan.wall_polys?.length && confirmedPolys.length) {
    // DXF 舊存檔：confirmed_floorplan 已帶（未開槽的）wall_polys，直接回填。
    floorplan.wall_polys = JSON.parse(JSON.stringify(confirmedPolys));
  }
  // 第 6 步結構一律以第 4 步確認資料重建：存檔的 scene_json 是產生當下的
  // 快照，後端幾何修正（如 wall_polys 開槽）到不了舊專案，牆會退回逐段
  // 板片（2026-08-03 QA）。只刷新 floorplan 結構——scene_objects 傳空陣列，
  // 家具座標維持存檔原樣、不重排。
  if (floorplan.source !== "user_confirmed") return false;
  if (!state.workflow?.completed?.includes("space_confirmation")) return false;
  if (!(state.structures.walls || []).length) return false;
  try {
    const layout = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        scene_objects: [],
      }),
    });
    if (!layout?.floorplan?.wall_polys?.length) return false;
    state.sceneData.floorplan = { ...floorplan, ...layout.floorplan };
    persistActiveScheme(state.designSchemes, {
      furniture: state.furniture2d,
      sceneData: state.sceneData,
    });
    return true;
  } catch (error) {
    console.warn("Unable to refresh restored floorplan structure.", error);
    return false;
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
  state.rooms = preparedAutoRoomLabels(state.rooms, state.structures.walls);
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
  // 統一複核清單（spatial_report.review_items）的理由。圖示層的提示比較具體
  // 所以在前面優先；沒有圖示提示時退到這裡，幾何信心與不規則形狀只有這一層。
  const reviewReasons = reviewReasonsForRoom(room.id);
  if (reviewReasons.length) return reviewReasonLabel(reviewReasons[0]);
  return "";
}

function analysisReviewItems() {
  return reviewItemsFromAnalysis(state.analysis);
}

function reviewReasonsForRoom(roomId) {
  const key = String(roomId);
  const reasons = [];
  for (const item of analysisReviewItems()) {
    if (String(item.room_id) !== key) continue;
    if (!reasons.includes(item.reason)) reasons.push(item.reason);
  }
  return reasons;
}

function unresolvedRecognitionReviewRooms() {
  return unresolvedReviewRooms(analysisReviewItems(), state.rooms);
}

function recognitionReviewSuffix() {
  const items = analysisReviewItems();
  if (!items.length) return "";
  // 第 3 步時 state.rooms 尚未 ingestion，以房間清單為基準會算成 0；
  // 房間還沒進來就直接數被標記的房間數。
  const flagged = state.rooms.length
    ? unresolvedReviewRooms(items, state.rooms).length
    : new Set(items.map((item) => String(item.room_id))).size;
  return flagged ? `；系統標記 ${flagged} 間房需人工複核` : "";
}

function renderRecognitionReviewSummary() {
  if (!element.recognitionReviewSummary || !element.recognitionReviewList) return;
  const pending = unresolvedRecognitionReviewRooms();
  element.recognitionReviewSummary.hidden = pending.length === 0;
  if (!pending.length) {
    element.recognitionReviewList.innerHTML = "";
    return;
  }
  element.recognitionReviewList.innerHTML = pending.map(({ room, reasons }) => `
    <li class="rp-review-summary-item">
      <button type="button" data-review-room-id="${escapeHtml(room.id)}" class="rp-review-room-jump">
        <strong>${escapeHtml(room.label || "未命名空間")}</strong>
        ${reasons.map((reason) => `<small>${escapeHtml(reviewReasonLabel(reason))}</small>`).join("")}
      </button>
    </li>
  `).join("");
}

// 標題列與畫布工具列各有一顆「查看全部空間」。以前兩顆共用同一個 id，
// $() 只會抓到第一顆，第二顆完全沒有綁定也不會更新狀態。
const SHOW_ALL_ROOMS_BUTTONS = ["#show-all-rooms", "#show-all-rooms-canvas"];

function updateShowAllRoomsButton() {
  const hasMultipleRooms = state.rooms.length > 1;
  SHOW_ALL_ROOMS_BUTTONS.map((selector) => $(selector)).filter(Boolean).forEach((button) => {
    button.disabled = !hasMultipleRooms;
    button.setAttribute(
      "aria-disabled",
      hasMultipleRooms ? "false" : "true",
    );
    button.title = hasMultipleRooms
      ? "顯示所有已框選的空間"
      : "目前只有一個空間，沒有其他框選可顯示";
  });
}

function roomsAfter(roomId) {
  const currentIndex = state.rooms.findIndex((room) => room.id === roomId);
  if (currentIndex < 0) return [...state.rooms];
  return [
    ...state.rooms.slice(currentIndex + 1),
    ...state.rooms.slice(0, currentIndex),
  ];
}

function nextRoomForReview(roomId) {
  return roomsAfter(roomId).find((room) => room.confirmed !== true) || null;
}

function nextRoomInQueue(roomId) {
  return roomsAfter(roomId)[0] || null;
}

function renderRooms() {
  if (!state.rooms.some((room) => room.id === state.selectedRoomId)) {
    state.selectedRoomId = state.rooms[0]?.id || null;
  }
  const selectedRoom = state.rooms.find((room) => room.id === state.selectedRoomId) || null;
  const currentIndex = selectedRoom
    ? state.rooms.findIndex((room) => room.id === selectedRoom.id)
    : -1;
  const queuedRooms = state.rooms.filter((room) => room.id !== state.selectedRoomId);
  element.roomList.innerHTML = queuedRooms.length ? queuedRooms.map((room) => {
    const dimensions = roomDimensions(room);
    const merging = state.mergeRoomIds.includes(room.id);
    const reviewHint = roomReviewHint(room);
    const roomIndex = state.rooms.findIndex((item) => item.id === room.id);
    return `
      <article class="rp-room-item rp-room-queue-item ${merging ? "is-merge-selected" : ""}">
        <button type="button" data-room-id="${escapeHtml(room.id)}" class="rp-room-select">
          <span class="rp-room-queue-index">${roomIndex + 1}</span>
          <span class="rp-room-queue-copy">
            <strong>${escapeHtml(room.label)}</strong>
            <small>${dimensions.areaM2.toFixed(2)} m² · ${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm</small>
          </span>
          <span class="rp-room-queue-status ${room.confirmed ? "is-confirmed" : ""}">
            ${room.confirmed ? "已確認" : "待確認"}
          </span>
          ${reviewHint ? `<small class="rp-room-review-hint">${escapeHtml(reviewHint)}</small>` : ""}
        </button>
      </article>
    `;
  }).join("") : '<p class="rp-room-queue-empty">沒有其他房間。</p>';
  const confirmedCount = state.rooms.filter((room) => room.confirmed).length;
  element.roomConfirmationProgress.textContent =
    `${currentIndex + 1} / ${state.rooms.length}`;
  element.roomConfirmationProgress.setAttribute(
    "aria-label",
    `目前第 ${Math.max(0, currentIndex + 1)} 個房間，已確認 ${confirmedCount} / ${state.rooms.length} 個房間`,
  );
  const confirmAllRoomsButton = $("#confirm-all-rooms");
  if (confirmAllRoomsButton) {
    const allConfirmed = state.rooms.length > 0 && confirmedCount === state.rooms.length;
    confirmAllRoomsButton.disabled = !state.rooms.length || allConfirmed;
    confirmAllRoomsButton.textContent = allConfirmed
      ? "全部房間已確認"
      : "一鍵確認全部房間";
  }
  const deleteCurrentRoomButton = $("#delete-current-room");
  if (deleteCurrentRoomButton) deleteCurrentRoomButton.disabled = state.rooms.length <= 1;
  renderRecognitionReviewSummary();
  updateShowAllRoomsButton();
  element.currentRoomReview.hidden = !selectedRoom;
  if (selectedRoom) {
    const dimensions = roomDimensions(selectedRoom);
    const reviewHint = roomReviewHint(selectedRoom);
    element.roomEditor.hidden = false;
    // disabled 是閂鎖：else 分支鎖上後，沒有這兩行就永遠不會解鎖——任何
    // 一次無選中房間的渲染（如還原時的輪廓修復重算）都會把按鈕鎖死。
    element.skipCurrentRoom.disabled = false;
    element.confirmCurrentRoom.disabled = false;
    renderRoomNameSelect(selectedRoom);
    element.roomArea.textContent =
      `系統依目前框選計算：${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm，${dimensions.areaM2.toFixed(2)} m²`;
  } else {
    element.roomEditor.hidden = true;
    element.skipCurrentRoom.disabled = true;
    element.confirmCurrentRoom.disabled = true;
  }
  updateSpaceCompletionState();
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

function openStructureReview() {
  const structureTab = $("[data-space-tab='structure']");
  if (structureTab && !structureTab.classList.contains("is-active")) structureTab.click();
}

function confirmCurrentRoomAndAdvance() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  if (room.confirmed !== true) confirmRoom(room.id);
  const nextRoom = nextRoomForReview(room.id);
  if (nextRoom) {
    selectRoom(nextRoom.id);
    setStatus(`已確認「${room.label}」；接著檢查「${nextRoom.label}」。`);
    return;
  }
  openStructureReview();
  setStatus("所有房間都已確認；接著檢查牆、門、窗、樑與柱。");
}

function skipCurrentRoomReview() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const nextRoom = nextRoomForReview(room.id) || nextRoomInQueue(room.id);
  if (!nextRoom) {
    setStatus("目前只有這一個房間，請確認名稱與範圍後繼續。");
    return;
  }
  selectRoom(nextRoom.id);
  setStatus(`已暫時略過「${room.label}」；目前檢查「${nextRoom.label}」。`);
}

function confirmAllRooms() {
  if (!state.rooms.length) return;
  // 系統標記需複核的房間不吃一鍵確認：複核訊號的意義就是「這幾間要人看過」，
  // 讓它們留在待確認狀態，逐一經 confirmRoom 才算數。
  const flaggedIds = new Set(
    unresolvedRecognitionReviewRooms().map(({ room }) => String(room.id)),
  );
  const confirmable = state.rooms.filter((room) => !flaggedIds.has(String(room.id)));
  confirmable.forEach((room) => {
    room.confirmed = true;
    room.confidence = 1;
    room.source = "manual_confirmation";
    room.label = room.label.replace(/\s*（待確認）\s*/g, "").trim() || "未命名空間";
  });
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
  setStatus(
    flaggedIds.size
      ? `已確認 ${confirmable.length} 個房間；另有 ${flaggedIds.size} 間被系統標記需逐一檢查，清單見「系統標記需人工複核」。`
      : `已一次確認 ${state.rooms.length} 個房間；仍可逐房修改名稱或框選。`,
  );
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

function updateSpaceCompletionState() {
  if (!element.confirmSpace) return;
  const confirmedRooms = state.rooms.filter((room) => room.confirmed === true).length;
  const pendingRooms = Math.max(0, state.rooms.length - confirmedRooms);
  const pendingStructures = Object.values(structureCollections).reduce(
    (total, collection) => total + (state.structures[collection] || [])
      .filter((item) => item.confirmed !== true).length,
    0,
  );
  const structuresAcknowledged = $("#structure-confirmed")?.checked === true;
  const estimatedSizeAcknowledged = $("#estimated-size-ack")?.checked === true;
  const ready = state.rooms.length > 0
    && pendingRooms === 0
    && pendingStructures === 0
    && structuresAcknowledged
    && estimatedSizeAcknowledged;

  element.spaceCompletionSummary.textContent =
    `已確認 ${confirmedRooms} / ${state.rooms.length} 個房間`;
  if (!state.rooms.length) {
    element.spaceCompletionHint.textContent = "目前沒有可確認的房間，請先新增或重新辨識空間。";
  } else if (pendingRooms > 0) {
    element.spaceCompletionHint.textContent = `尚有 ${pendingRooms} 個房間待確認。`;
  } else if (pendingStructures > 0) {
    element.spaceCompletionHint.textContent = `房間已完成，尚有 ${pendingStructures} 個結構項目待確認。`;
  } else if (!structuresAcknowledged || !estimatedSizeAcknowledged) {
    element.spaceCompletionHint.textContent = "結構項目已完成，請勾選結構與估計尺寸確認。";
  } else {
    element.spaceCompletionHint.textContent = "房間與結構皆已確認，可以檢查尺寸標註。";
  }
  element.confirmSpace.disabled = !ready;
  element.confirmSpace.setAttribute("aria-disabled", ready ? "false" : "true");
}

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
    guidance: "內牆可標記為可拆牆候選；最外圍牆會鎖定。此標記僅供方案比較，是否能拆仍須由專業人員確認。",
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
  const floorplan = wallBoundaryContext();
  let lockedCandidates = 0;
  state.structures.walls.forEach((wall) => {
    const boundary = wallBoundarySide(wall, {
      widthCm: floorplan.width_cm,
      depthCm: floorplan.depth_cm,
    });
    wall.boundary_side = boundary;
    if (boundary && wall.demolition_candidate === true) lockedCandidates += 1;
    if (boundary) wall.demolition_candidate = false;
    else wall.demolition_candidate = wall.demolition_candidate === true;
  });
  return lockedCandidates;
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

function renderWallRemovalPreviews() {
  const panel = $("#wall-removal-preview");
  if (!panel) return;
  const wallPage = state.activeStructureKind === "wall";
  panel.hidden = !wallPage;
  if (!wallPage) return;
  normalizeWallDemolitionCandidates();
  const floorplan = wallBoundaryContext();
  const width = Math.max(1, floorplan.width_cm);
  const depth = Math.max(1, floorplan.depth_cm);
  const padding = Math.max(24, Math.min(width, depth) * 0.04);
  const viewBox = `${-padding} ${-padding} ${width + padding * 2} ${depth + padding * 2}`;
  const retained = $("#wall-retained-preview-svg");
  const demolished = $("#wall-demolished-preview-svg");
  [retained, demolished].forEach((svg) => {
    svg.setAttribute("viewBox", viewBox);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  });
  retained.innerHTML = wallPreviewMarkup();
  demolished.innerHTML = wallPreviewMarkup({ simulateDemolition: true });
  const candidateCount = state.structures.walls.filter(
    (wall) => wall.demolition_candidate === true,
  ).length;
  $("#wall-removal-preview-summary").textContent = candidateCount
    ? `已標記 ${candidateCount} 面可拆牆候選；右圖以淡紅虛線保留原位置提示。`
    : "尚未標記可拆牆；兩個預覽目前相同。";
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

// ── 逐房方案 A/B 選擇（bella-test1 fd0cee11＋23de9dda UI 部分移植）──────────
// 結構是全案共用基準：兩個方案的牆、門、窗、樑、柱完全相同（同一 baseScene），
// 方案卡只呈現家具的選擇、位置與朝向差異。

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
  // 已完成合成（快照存在且逐房都選過）就不再自動彈窗，避免每次進出第 6 步
  // 都被擋一次；「逐房確認方案」側欄按鈕永遠可以再開。
  if (
    state.designSchemes.configuration_snapshot
    && allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)
  ) {
    renderRoomSchemeGate();
    return;
  }
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

// 只顯示中文名稱與尺寸；不顯示原始型錄長名或英文材質碼。
function roomSchemeFurnitureLabel(item = {}) {
  const label = String(item.label || "").trim();
  if (label && /[㐀-鿿]/.test(label)) return label;
  return REPLACEMENT_TYPE_LABELS[item.type || item.normalized_type] || label || "家具";
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
    y: ((point.y - minY) / height) * 300,
  });
  const roomPath = points.map((point, index) => {
    const projected = project(point);
    return `${index ? "L" : "M"} ${projected.x.toFixed(1)} ${projected.y.toFixed(1)}`;
  }).join(" ") + " Z";
  const furnitureMarkup = furniture.slice(0, 12).map((item) => {
    const location = project({ x: center.x + Number(item.xCm || 0), y: center.y + Number(item.yCm || 0) });
    const itemWidth = Math.max(22, (Number(item.widthCm || 60) / width) * 440);
    const itemHeight = Math.max(18, (Number(item.depthCm || 60) / height) * 300);
    const label = roomSchemeFurnitureLabel(item);
    return `<g class="rp-room-scheme-furniture" transform="translate(${location.x.toFixed(1)} ${location.y.toFixed(1)}) rotate(${Number(item.rotationDeg || 0)})">
      <rect x="${(-itemWidth / 2).toFixed(1)}" y="${(-itemHeight / 2).toFixed(1)}" width="${itemWidth.toFixed(1)}" height="${itemHeight.toFixed(1)}" rx="3" />
      ${itemWidth > 62 && itemHeight > 30 ? `<text text-anchor="middle" dominant-baseline="middle">${escapeHtml(label.slice(0, 8))}</text>` : ""}
    </g>`;
  }).join("");
  return `<svg class="rp-room-scheme-plan" viewBox="0 0 440 300" role="img" aria-label="${escapeHtml(room.label || "房間")}的家具平面配置">
    <path class="rp-room-scheme-outline" d="${roomPath}" />
    ${furnitureMarkup || '<text class="rp-room-scheme-empty" x="220" y="150" text-anchor="middle">尚未配置家具</text>'}
  </svg>`;
}

function roomSchemeFurnitureLegend(furniture = []) {
  if (!furniture.length) return '<p class="rp-room-scheme-legend-empty">尚未配置家具</p>';
  return `<ul class="rp-room-scheme-legend">${furniture.slice(0, 6).map((item) => (
    `<li>${escapeHtml(roomSchemeFurnitureLabel(item))}，${Number(item.widthCm || 0).toFixed(0)} × ${Number(item.depthCm || 0).toFixed(0)} cm</li>`
  )).join("")}</ul>`;
}

// 單房比較：同一份確認結構（baseScene）裁切＋平移到本房，再放入該方案家具。
// 陣列 [x, y] 與物件 {x, y} 座標都要處理（scene_plan_geometry 的 shift 系列）。
function buildRoomSchemePreviewScene(baseScene, room, furniture = []) {
  if (!baseScene?.floorplan || !room) return null;
  const bounds = replacementRoomBounds(room);
  if (!bounds) return null;
  const offset = { x: bounds.centerX, z: bounds.centerZ };
  const scene = JSON.parse(JSON.stringify(baseScene));
  const floorplan = scene.floorplan || {};
  [
    "wall_segments",
    "door_segments",
    "door_openings",
    "window_segments",
    "beam_segments",
    "column_segments",
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
    .filter((region) => String(region.room_id || region.id || "") === String(room.id))
    .map((region) => shiftFloorplanRegion(region, offset));
  if (Array.isArray(floorplan.rooms)) {
    floorplan.rooms = floorplan.rooms
      .filter((region) => String(region.room_id || region.id || "") === String(room.id))
      .map((region) => shiftFloorplanRegion(region, offset));
  }
  floorplan.width_cm = Math.max(240, (bounds.maxX - bounds.minX) + 120);
  floorplan.depth_cm = Math.max(240, (bounds.maxZ - bounds.minZ) + 120);
  scene.floorplan = floorplan;
  scene.room_surface_assignments = (scene.room_surface_assignments || [])
    .filter((assignment) => String(assignment.room_id || "") === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  scene.surface_overrides = (scene.surface_overrides || [])
    .filter((assignment) => String(assignment.room_id || "") === String(room.id))
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

// 方案 B 缺席時的規格明定路徑：明確顯示原因，並預設選用 A（規格 §進入順序 2）。
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
  if (typeof element.roomSchemeDialog.showModal === "function" && !element.roomSchemeDialog.open) {
    element.roomSchemeDialog.showModal();
  } else if (!element.roomSchemeDialog.open) {
    element.roomSchemeDialog.setAttribute("open", "");
  }
  void ensureRoomScheme3dPreviews();
}

function closeRoomSchemeSelectionDialog() {
  if (!element.roomSchemeDialog) return;
  if (typeof element.roomSchemeDialog.close === "function") element.roomSchemeDialog.close();
  else element.roomSchemeDialog.removeAttribute("open");
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
  // 3D 預覽的結構一律取方案 A 的 baseScene：A/B 牆門窗樑柱必須完全相同。
  const baseScene = state.designSchemes.schemes.A?.sceneData || state.sceneData;
  const previewScene = buildRoomSchemePreviewScene(
    baseScene,
    room,
    schemeFurnitureForRoom(resolvedSchemeId, room.id),
  );
  if (!previewScene) {
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
            : '<span class="rp-render-placeholder">正在建立此房間的 3D 預覽…</span>'}
        </button>
      </div>
      <p class="rp-task-dialog-note">${unavailable ? escapeHtml(scheme?.staleReason || "方案尚未可用") : `本房共 ${furniture.length} 件家具`}</p>
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
        syncFurnitureNumberVisibility();
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
    const verification = configurationLedgerSummary();
    if (verification.pending || verification.deferred) {
      setStatus(
        `房間方案已合成；目前仍有 ${verification.pending} 件待處理、${verification.deferred} 件已暫緩，請依右側對帳清單確認。`,
        "warning",
      );
    } else {
      setStatus("所有房間方案已合成為唯一配置，2D 與 3D 場景驗證均已通過。", "success");
    }
  } catch (error) {
    schemeA.furniture = originalFurniture;
    schemeA.sceneData = originalScene;
    state.furniture2d = originalFurniture;
    state.sceneData = originalScene;
    element.roomSchemeWarning.hidden = false;
    element.roomSchemeWarning.textContent = `無法合成最終配置：${errorMessage(error)}`;
  } finally {
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
  const show = Boolean(state.designSchemes.schemes.B)
    && hasRenovationChanges(state.structures);
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
    ...state.structures.walls.flatMap((item) => [item.start, item.end]),
    ...state.structures.beams
      .filter((item) => item.id !== excludeId)
      .flatMap((item) => [item.start, item.end]),
    ...state.structures.columns.map((item) => item.center),
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
      ${structureNumberMarkerSvg("wall", index, midpoint, { selected })}`,
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
    const closedLine = item.swing_end
      ? `<line x1="${hinge.x}" y1="${hinge.y}" x2="${swingEnd.x}" y2="${swingEnd.y}"
          stroke="#1598dc" stroke-width="5" stroke-linecap="round" pointer-events="none"/>`
      : "";
    return structureGroup(
      item,
      "door",
      `${dragTarget}${line}${closedLine}<path d="M ${end.x} ${end.y} A ${radius} ${radius} 0 0 ${sweep} ${swingEnd.x} ${swingEnd.y}" fill="none" stroke="#bd5c36" stroke-width="3"/>${marker}${handles}`,
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
  return `<g>${walls}${windows}${doors}${beams}${columns}${beamDraft}</g>`;
}

let draggedRoomPointIndex = null;
let structureDrag = null;
let doorResizeDrag = null;
let beamResizeDrag = null;
let structureCreateDrag = null;
let structureSizeDraft = null;
let lastStructureEditorKey = null;

function cancelStructureInteraction() {
  state.structureTool = null;
  state.structureLineStart = null;
  state.selectedStructure = null;
  structureDrag = null;
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
        scheme_id: "B",
        demolition_candidate: false,
      };
      state.structures[collection].push(item);
      ensureRenovationScheme("added_structure");
      state.selectedStructure = { id: item.id, kind };
      state.structureLineStart = null;
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
      const translated = translateOpeningAlongAxis(
        structureDrag.snapshot,
        { x: dx, y: dy },
      );
      if (!translated) return;
      item.start = translated.start;
      item.end = translated.end;
      item.width_cm = Number(
        structureDrag.snapshot.width_cm
        || Math.hypot(
          structureDrag.snapshot.end.x - structureDrag.snapshot.start.x,
          structureDrag.snapshot.end.y - structureDrag.snapshot.start.y,
        ),
      );
      item.host_wall_id = structureDrag.snapshot.host_wall_id || item.host_wall_id;
      structureDrag.changed = true;
      item.confirmed = false;
      if (state.selectedStructure.kind === "door") delete item.swing_end;
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
    return;
  }
  const editorKey = `${state.selectedStructure.kind}:${item.id}`;
  if (lastStructureEditorKey !== editorKey) {
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
  renderWallRemovalPreviews();
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
    const perimeterWall = kind === "wall" && Boolean(wallBoundary(item));
    const wallTypeToggle = kind === "wall"
      ? `<div class="rp-window-type-toggle rp-wall-type-toggle" role="group" aria-label="牆 ${index + 1} 類型">
          <button type="button" class="${item.demolition_candidate !== true ? "is-active" : ""}"
            aria-pressed="${item.demolition_candidate !== true}"
            data-wall-demolition="retained" data-wall-id="${escapeHtml(item.id)}">一般牆</button>
          <button type="button" class="${item.demolition_candidate === true ? "is-active" : ""}"
            aria-pressed="${item.demolition_candidate === true}"
            data-wall-demolition="candidate" data-wall-id="${escapeHtml(item.id)}"
            ${perimeterWall ? 'disabled title="最外圍牆不可標記為可拆牆"' : ""}>
            ${perimeterWall ? "外圍鎖定" : "可拆牆"}
          </button>
        </div>`
      : "";
    const wallState = kind === "wall"
      ? perimeterWall
        ? " · 最外圍牆已鎖定"
        : item.demolition_candidate === true
          ? " · 可拆牆候選"
          : " · 一般牆"
      : "";
    return `<article class="rp-door-review-item ${selected ? "is-active" : ""}">
      <button type="button" class="rp-door-review-select"
        data-structure-review="${escapeHtml(item.id)}" data-structure-kind="${kind}">
        <strong>${kind === "window" && normalizedWindowType(item.window_type) === WINDOW_TYPES.floorToCeiling ? "落地窗" : meta.label} ${index + 1}</strong>
        <span>${structureMeasurement(item, kind)}${wallState} · ${item.confirmed ? "已確認" : "待人工確認"}</span>
      </button>
      <button type="button" class="rp-door-confirm ${item.confirmed ? "is-confirmed" : ""}"
        data-confirm-structure="${escapeHtml(item.id)}" data-structure-kind="${kind}">${item.confirmed ? "已確認" : "確認"}</button>
      ${windowTypeToggle}
      ${wallTypeToggle}
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
  if (deletedKind === "wall" && selected?.scheme_id === "B") {
    const children = attachedOpenings(state.structures, selected.id);
    if (children.length && !confirm(
      `此牆連帶 ${children.length} 扇新增門窗。刪除牆時會一併刪除，確定繼續？`,
    )) return;
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

// 前端房型正規化清單：空間名稱會直接寫入機器房型 room.type，並與後端
// ROOM_LABELS／SPACE_DEFAULTS 使用同一套詞彙；一致性由
// tests/test_room_type_vocabulary.py 契約測試鎖住。
const ROOM_TYPE_OPTIONS = [
  ["living_room", "客廳"],
  ["bedroom", "臥室"],
  ["kitchen", "廚房"],
  ["dining_room", "餐廳"],
  ["bathroom", "浴廁"],
  ["balcony", "陽台"],
  ["workspace", "書房"],
  ["storage", "儲藏"],
  ["circulation", "走道／玄關"],
  ["default", "其他／未指定"],
];
const ROOM_TYPE_LABELS = new Map(ROOM_TYPE_OPTIONS);

function normalizedRoomTypeValue(type) {
  // 舊專案存了 entry／stair／garage，直接查表會落到 default，回頭開啟時用途
  // 會顯示「其他／未指定」並拿到客廳家具。先過一次遷移表再判定。
  const raw = String(type || "");
  const migrated = LEGACY_ROOM_TYPES[raw] || raw;
  return ROOM_TYPE_LABELS.has(migrated) ? migrated : "default";
}

function renderRoomNameSelect(room) {
  // 選項一律由 ROOM_NAME_OPTIONS 生成。寫死在 scene.html 的舊 12 類會與這張表
  // 脫鉤：臥室選不到、主臥／次臥等舊值按套用時被判成「請選擇空間名稱」。
  if (!element.roomName) return;
  const current = roomNameOptionFor(room || {}).id;
  element.roomName.innerHTML = ROOM_NAME_OPTIONS.map(
    (option) =>
      `<option value="${escapeHtml(option.id)}" ${option.id === current ? "selected" : ""}>`
      + `${escapeHtml(option.label)}</option>`,
  ).join("");
  element.roomName.value = current;
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
  // 2026-07 盤點第 5 項修復：改名不再只是字串——名稱可推斷房型且目前尚未
  // 指定時，同步回寫 room.type，讓後端與 agent 拿到真用途而非 default。
  if (normalizedRoomTypeValue(room.type) === "default") {
    const derived = roomTypeFromName({ label: option.label });
    if (derived && derived !== "default") room.type = normalizedRoomTypeValue(derived);
  }
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間資料已修改，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
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
  updateSpaceCompletionState();
}

function confirmSpace() {
  element.spaceError.textContent = "";
  if (!state.rooms.every((room) => room.confirmed === true)) {
    const pendingCount = state.rooms.filter((room) => !room.confirmed).length;
    element.spaceError.textContent =
      `尚有 ${pendingCount} 個房間未確認，請依序檢查目前房間。`;
    element.confirmCurrentRoom?.focus();
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
    element.dimensionPlanImage.addEventListener("load", () => {
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
  state.workflow.complete("space_confirmation", {
    roomsConfirmed: true,
    structureConfirmed: true,
    proportionsConfirmed: true,
    dimensionedPlanConfirmed: true,
    totalAreaM2: annotation.totalAreaM2,
    // 完成當下不可能還有未複核房間（未確認的房間到不了這裡），記數字供
    // 伺服器端 recognition_review_unresolved 閘門與之後追溯。
    recognitionReviewItemCount: analysisReviewItems().length,
    recognitionReviewResolved: true,
  });
  renderWholeHouseQuestionnaire();
  setStatus("尺寸標註平面圖與結構均已確認。現在開始基本問卷。");
  goTo("requirements");
}

// 佇列 7 第六批：四群碰 state 的問卷流程（全屋表面一致性、初談流程、材質
// 草稿層、renderDetailChoices）純搬家到 scene_questionnaire_flow.js 的
// createQuestionnaireFlow 工廠。參數依原名注入模組作用域依賴，解構回同名
// const，呼叫端零改動；只有工廠內部互相呼叫的函式不解構。
const {
  livingRoomForCirculation,
  circulationStyleIsOverridden,
  copyLivingRoomStyleToCirculation,
  normalizedRoomSurfaces,
  applyWholeHouseSurfaceConsistency,
  normalizeSavedSceneWallSurfaces,
  firstMeetingStepIndex,
  markFirstMeetingChanged,
  renderFirstMeeting,
  applyFirstMeetingToRequirements,
  randomizeRequirementsForTesting,
  activeQuestionnairePack,
  activeRoomFinishDraft,
  confirmQuestionnaireFinishes,
  renderDetailChoices,
  wholeHouseFinishDraft,
} = createQuestionnaireFlow({
  state,
  element,
  $$,
  escapeHtml,
  setStatus,
  scheduleSave,
  invalidateDownstreamFrom,
  renderVisualQuestionnaire,
  showQuestionnaireStage,
  activeQuestionnaireRoom,
  activeRoomRequirement,
});

function applyRandomRoomRequirement(room, draft) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return;
  const axisNotes = randomRoomAxisNote(room);
  // 視覺問卷已拆除：axisAnswers 只剩舊專案還原時才會有內容。
  requirement.axisAnswers = {};
  requirement.furniture = {
    required: axisNotes,
    optional: [],
  };
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
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

async function prepareQuestionnaireStep() {
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
  renderFirstMeeting();
}

function roomQuestionnaireProgress() {
  const rooms = Object.values(state.roomRequirementModel?.roomRequirements || {});
  const completed = rooms.filter((room) => room.confirmed === true).length;
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
    profile: "全屋風格與設備",
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

function roomQuestionnaireSectionProgress(room) {
  const requirement = state.roomRequirementModel?.roomRequirements?.[room.id] || {};
  const questions = state.visualQuestions.filter(
    (question) => String(question.room_id) === String(room.id),
  );
  const preferenceCompleted = questions.filter(
    (question) => state.visualAnswers[question.question_id]?.optionId,
  ).length;
  const furnitureTotal = questionnaireFurnitureSpecsForRoom(room).length;
  const furnitureSelected = requirement.furniture?.selected?.length || 0;
  const equipmentCompleted = Math.min(furnitureSelected, furnitureTotal)
    + (requirement.climate?.airConditioning ? 1 : 0);
  const equipmentTotal = furnitureTotal + 1;
  const surfaces = requirement.surfaces || {};
  const materialChecks = [
    surfaces.paletteId,
    surfaces.wallDefault?.materialId,
    surfaces.floor?.materialId,
    surfaces.ceiling?.materialId,
  ];
  const materialCompleted = materialChecks.filter(Boolean).length;
  return {
    preferences: { completed: preferenceCompleted, total: questions.length },
    equipment: { completed: equipmentCompleted, total: equipmentTotal },
    materials: { completed: materialCompleted, total: materialChecks.length },
    confirmed: requirement.confirmed === true,
  };
}

function renderRoomQuestionnaireSection() {
  // 2026-07-30 合併 bella-test2：第 5 步改為「逐房用途＋家具 → 全屋風格」，
  // 分段導覽與題目快轉塢已退場；保留空函式讓殘餘呼叫點安全通過。
}

function showRoomQuestionnaireSection(section) {
  state.roomQuestionnaireSection = ROOM_QUESTIONNAIRE_SECTIONS.includes(section)
    ? section
    : "preferences";
  if (state.roomQuestionnaireSection !== "preferences") renderQuestionnaireFinishes();
  renderRoomQuestionnaireSection();
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
    const confirmed = state.roomRequirementModel?.roomRequirements?.[room.id]?.confirmed === true;
    const furnitureCount = roomFurnitureRequirement(room.id)?.selected?.length || 0;
    return `
      <button type="button" data-visual-room="${escapeHtml(room.id)}"
        class="${room.id === currentRoomId ? "is-active" : ""}"
        aria-current="${room.id === currentRoomId ? "true" : "false"}">
        <strong>${escapeHtml(room.label)}</strong>
        <small>${confirmed ? "已確認" : `已選 ${furnitureCount} 件家具`}</small>
      </button>
    `;
  }).join("");
}

function renderVisualQuestionnaire() {
  const room = activeQuestionnaireRoom();
  if (!room) return;
  element.visualQuestionCard.innerHTML = `
    <span class="eyebrow">${escapeHtml(room.label)}</span>
    <h3>這個空間想放什麼？</h3>
    <p>勾選下方資料庫家具即可。沒有想指定的家具可直接確認，系統會在建立方案時依房間用途與尺寸補足基本配置。</p>
  `;
  renderVisualSpaceNav();
  state.roomRequirementModel.activeRoomId = room.id;
  renderQuestionnairePlan();
  renderQuestionnaireFinishes();
  renderRoomQuestionnaireSection();
}

function renderQuestionnaireSummary() {
  const basicRows = WHOLE_HOUSE_QUESTIONS.map((question) =>
    `<div><span>${escapeHtml(question.label)}</span><strong>${escapeHtml(state.basicAnswers[question.id] || "未填")}</strong></div>`
  ).join("");
  if (!state.expandedQuestionnaireSummaryRoomId && state.rooms.length) {
    state.expandedQuestionnaireSummaryRoomId = state.rooms[0].id;
  }
  const roomRows = state.rooms.map((room, index) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id] || {};
    const expanded = String(state.expandedQuestionnaireSummaryRoomId) === String(room.id);
    const progress = roomQuestionnaireSectionProgress(room);
    const axisRows = Object.entries(requirement?.axisAnswers || {}).map(([questionId, answer]) => {
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
    });
    const visibleAxes = axisRows.slice(0, 4).join("");
    const remainingAxes = axisRows.slice(4);
    const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {});
    const selectedFurniture = requirement?.furniture?.selected || [];
    const deferredFurniture = requirement?.furniture?.deferred || [];
    const notices = (requirement?.feasibility || []).map(
      (item) => `<li>${escapeHtml(item.message || item)}</li>`,
    ).join("");
    const statusItems = [
      ["需求", progress.preferences],
      ["家具設備", progress.equipment],
      ["材質風格", progress.materials],
    ].map(([label, item]) => `
      <span class="rp-summary-progress-item ${item.completed >= item.total && item.total > 0 ? "is-complete" : ""}">
        <i aria-hidden="true"></i>${label} ${item.completed}/${item.total}
      </span>
    `).join("");
    return `
      <details class="rp-room-summary" ${index === 0 ? "open" : ""}>
        <summary><strong>${escapeHtml(room.label)}</strong><span>${requirement?.confirmed ? "已確認" : "待確認"}</span></summary>
        <div class="rp-room-summary-body">
          <section><h4>空間需求</h4><p>本流程不要求生活情境二選一；第 6 步仍可調整家具、材質與配置。</p></section>
          <section><h4>家具</h4>
            <p>已選：${escapeHtml(selectedFurniture.map((item) => item.name_zh || item.name_zh_raw || item.normalized_type).join("、") || "由問卷與 RAG 產生")}</p>
            ${deferredFurniture.length ? `<p>暫不放入：${escapeHtml(deferredFurniture.map((item) => item.label || item.name_zh || item.normalized_type).join("、"))}</p>` : ""}
          </section>
          <section><h4>材質與風格</h4><p>牆面：${escapeHtml(surfaces.wallDefault?.materialId || "未填")}；逐面指定 ${Object.keys(surfaces.wallOverrides || {}).length} 面</p><p>地板：${escapeHtml(surfaces.floor?.materialId || "未填")}</p></section>
          <section><h4>天花板與照明</h4><p>${escapeHtml(surfaces.ceiling?.materialId || "未填")}／${escapeHtml(surfaces.ceiling?.styleId || "未填")}／${escapeHtml(surfaces.ceiling?.lightingId || "未填")}</p></section>
          ${notices ? `<section class="needs-review"><h4>需要確認</h4><ul>${notices}</ul></section>` : ""}
          <div class="rp-room-summary-actions">
            <button type="button" class="secondary-action" data-edit-questionnaire-room="${escapeHtml(room.id)}">返回修改此房</button>
          </div>
        </div>
      </details>
    `;
  }).join("");
  element.questionnaireSummary.innerHTML = `
    <section class="rp-whole-house-summary"><div><span class="eyebrow">全屋共用資料</span><h4>已確認的專案條件</h4></div><div class="rp-questionnaire-summary-grid">${basicRows}</div></section>
    <section class="rp-room-summary-list"><div class="rp-summary-list-heading"><span class="eyebrow">逐房摘要</span><h4>一次只展開一個房間，快速檢查重點</h4></div>${roomRows}</section>
  `;
}

function renderWholeHouseQuestionnaire() {
  element.wholeHouseFields.innerHTML = WHOLE_HOUSE_QUESTIONS.map((question) => {
    if (question.type === "select") {
      const options = question.options.map((option) =>
        `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`
      ).join("");
      return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><select><option value="">請選擇</option>${options}</select></label>`;
    }
    return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><textarea rows="2" placeholder="${escapeHtml(question.placeholder || "")}"></textarea></label>`;
  }).join("");
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    const control = host?.querySelector("select, textarea");
    if (control) control.value = state.basicAnswers[question.id] || "";
  });
  renderWholeHouseStyleEditor();
}

function renderDetailInputs() {
  return Object.fromEntries(RENDER_DETAIL_FIELDS.map(
    ({ key, element: name }) => [key, element[name]?.value || ""],
  ));
}

// 控制項放在第 8 步側欄：第 5 步的初談問卷刻意把「家具、材質與設備留到方案
// 階段再談」，而這幾項只有生圖用得到，放在按下生圖之前才符合那條界線。
function renderRenderDetailControls() {
  const finishes = state.questionnaireFinishes || {};
  RENDER_DETAIL_FIELDS.forEach(({ key, element: name }) => {
    if (element[name]) element[name].value = finishes[key] || "";
  });
}

function saveRenderDetailInputs() {
  state.questionnaireFinishes = {
    ...(state.questionnaireFinishes || {}),
    ...renderDetailInputs(),
  };
  scheduleSave("ai_render");
}

// ── 全屋主風格與逐房材質分離（bella-test1 24c4f0ca 移植）─────────────────
// 全屋只選一次「主風格」；牆面、地板、天花與照明改由逐房問卷依風格推薦、
// 逐房覆寫。同風格三張色卡留到第 7 步 proposal-palette-grid 統一選擇。

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
        alt="${escapeHtml(`${family.label} 住宅風格參考圖`)}" loading="lazy">
      <strong>${escapeHtml(family.label)}</strong>
      <small>${escapeHtml(family.selectionCue || "")}</small>
      <em>${family.id === pack.styleId ? "已選擇此全屋風格" : "點選設為全屋風格"}</em>
    </button>
  `).join("");
  if (element.wholeHouseStyleSelection) {
    element.wholeHouseStyleSelection.textContent = `已選全屋主風格：${STYLE_FAMILIES.find((family) => family.id === pack.styleId)?.label || pack.name}。牆面、地板、天花與照明將在逐房問卷設定。`;
  }
}

function roomFinishDraftForStyleChange(room, requirement) {
  const existing = state.roomFinishDrafts[room.id];
  if (existing) return existing;
  const surfaces = requirement.surfaces || {};
  return {
    confirmed: requirement.confirmed === true,
    materialSelectionMode: surfaces.materialSelectionMode || "auto",
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
      // 已確認或自選過材質的房間只換 paletteId，不覆寫使用者的選擇。
      Object.assign(draft, { stylePackId: pack.id, confirmed: false });
      requirement.surfaces = { ...surfaces, paletteId: pack.id, materialSelectionMode: "custom" };
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
        });
        requirement.surfaces = {
          ...surfaces,
          paletteId: pack.id,
          materialSelectionMode: "auto",
          wallDefault: { materialId: recommendation.wall.id, color: recommendation.wall.color },
          wallOverrides: {},
          floor: { materialId: recommendation.floor.id, color: recommendation.floor.color },
          ceiling: {
            materialId: draft.ceilingMaterial || "flat-paint",
            styleId: recommendedCeilingStyleForPack(pack),
            lightingId: recommendedLightStyleForPack(pack),
            color: draft.ceilingColor || "#f4f1eb",
          },
        };
        requirement.confirmed = false;
      }
    }
    state.roomFinishDrafts[room.id] = { ...draft };
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
  // 存檔的全屋 profile 與風格編輯器同步：重載會還原，也會進 RAG／生圖請求。
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
      ceilingStyle: preserveCustomChoice ? roomDraft.ceilingStyle : recommendedCeilingStyleForPack(pack),
      lightStyle: preserveCustomChoice ? roomDraft.lightStyle : recommendedLightStyleForPack(pack),
      airConditioning: requirement.climate.airConditioning,
      confirmed: preserveCustomChoice ? roomDraft.confirmed : false,
    };
  });
  applyWholeHouseSurfaceConsistency();
}

function collectBasicAnswers() {
  const answers = {};
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    answers[question.id] = host?.querySelector("select, textarea")?.value.trim() || "";
  });
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

async function confirmRequirements() {
  if (confirmRequirementsInFlight) return;
  element.requirementsError.textContent = "";
  element.firstMeetingError.textContent = "";
  const interviewStatus = firstMeetingReady(state.firstMeeting, state.rooms);
  if (!interviewStatus.ready) {
    element.firstMeetingError.textContent = interviewStatus.message;
    return;
  }
  applyFirstMeetingToRequirements();
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
    element.firstMeetingError.textContent = "初談摘要尚未完整，請返回前面確認答案。";
    return;
  }
  confirmRequirementsInFlight = true;
  const originalLabel = element.confirmRequirements.textContent;
  element.confirmRequirements.disabled = true;
  element.confirmRequirements.textContent = "正在建立 2D 與 3D 配置…";
  try {
    setStatus("正在檢查空間規則並建立方案 A、B…");
    ensureSchemeB(state.designSchemes, { reason: "questionnaire_alternative" });
    switchDesignScheme("A");
    await autoLayoutFurniture();
    // 2026-07 盤點方案 B 修復：放不下的家具改列「暫不放入」，流程不再中止。
    // 方案 A 先清一次失敗件，方案 B 只重擺可用件。
    state.furniture2d = deferFailedPlacements(state.furniture2d, "A");
    state.designSchemes.schemes.A.furniture = JSON.parse(JSON.stringify(state.furniture2d));
    scheduleSave("layout_2d");
    const schemeAFurniture = state.designSchemes.schemes.A.furniture;
    const schemeBFurniture = await relayoutFurnitureForScheme(schemeAFurniture, "B");
    const schemeB = state.designSchemes.schemes.B;
    const schemeBKept = deferFailedPlacements(schemeBFurniture, "B");
    schemeB.furniture = JSON.parse(JSON.stringify(schemeBKept));
    schemeB.stale = false;
    schemeB.staleReason = "";
    if (schemeBFurniture.length !== schemeBKept.length) {
      setStatus(
        `方案 B 有 ${schemeBFurniture.length - schemeBKept.length} 件家具在此格局放不下，已列入「暫不放入」，其餘照常配置。`,
      );
    }
    switchDesignScheme("A");
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
      visualPreferencesResolved: true,
      finishesConfirmed: true,
      firstMeetingConfirmed: true,
      interviewSchemaVersion: state.firstMeeting.schemaVersion,
    });
    renderFurnitureLibrary();
    // 問卷送出後先建候選集：把全型錄縮成每房數十筆，第 6 步的選件與擺放
    // 都只在這個子集上跑。失敗不擋流程，catalogOffersForSpec 會退回全庫。
    setStatus("正在依你的需求檢索適合的家具…");
    await ensureFurnitureShortlist();
    setStatus("正在載入方案 A 的資料庫家具與 3D 場景…");
    const generated = await generateWhiteModelFromRequirements({
      returnToRequirementsOnFailure: true,
    });
    if (!generated && !element.requirementsError.textContent.trim()) {
      element.requirementsError.textContent =
        "無法建立 2D+3D 配置，請檢查待處理家具或稍後再試。";
    }
  } catch (error) {
    element.firstMeetingError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  } finally {
    confirmRequirementsInFlight = false;
    element.confirmRequirements.disabled = false;
    element.confirmRequirements.textContent = originalLabel;
  }
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

// 只收「3D 場景表現不出來、因此不可能與參考截圖打架」的需求：材質、天花、
// 燈具、冷氣與氛圍描述。家具品項與數量一律不進這裡——那條由後端直接讀
// scene_json 鎖定，兩邊各自負責才不會出現互相矛盾的敘述。
// overallStyle 也刻意排除：第 9 步確認的色卡才是風格依據，重述問卷初選會
// 與 style_pack 打架。
function renderRequirementsDigest() {
  const finishes = state.questionnaireFinishes || {};
  const basic = state.basicAnswers || {};
  const rooms = roomSurfaceAssignments().map((assignment) => ({
    room_id: assignment.room_id,
    room_label: assignment.room_label,
    wall: surfacePhrase(
      surfaceMaterialLabel("wall", assignment.wall_material_id),
      assignment.wall_color_hex,
    ),
    floor: surfacePhrase(
      surfaceMaterialLabel("floor", assignment.floor_material_id),
      assignment.floor_color_hex,
    ),
    ceiling: surfacePhrase(
      styleCatalogLabel(CEILING_STYLES, assignment.ceiling_style_id),
      assignment.ceiling_color_hex,
    ),
    lighting: styleCatalogLabel(LIGHT_STYLES, assignment.lighting_id),
    air_conditioning: assignment.air_conditioning || "",
  }));
  return {
    schema_version: "1.0",
    whole_house: {
      household: basic.household || "",
      members_and_pets: basic.membersAndPets || "",
      lifestyle: basic.lifestyle || "",
      immutable_needs: basic.immutableNeeds || "",
      wall: surfacePhrase(
        surfaceMaterialLabel("wall", finishes.wallMaterial),
        finishes.wallColor,
      ),
      floor: surfacePhrase(
        surfaceMaterialLabel("floor", finishes.floorMaterial),
        finishes.floorColor,
      ),
      ceiling: surfacePhrase(
        styleCatalogLabel(CEILING_STYLES, finishes.ceilingStyle),
        finishes.ceilingColor,
      ),
      lighting: styleCatalogLabel(LIGHT_STYLES, finishes.lightStyle),
      render_details: renderDetailChoices(finishes),
    },
    rooms,
  };
}

function planCenterCm() {
  const { bbox, scale } = planGeometry();
  return {
    x: (bbox[2] - bbox[0]) * scale / 2,
    y: (bbox[3] - bbox[1]) * scale / 2,
  };
}

// 佇列 7 第六批（6B）：候選集/檢索群與家具推薦 UI 群（含 6A 點名的糾纏對
// renderQuestionnaireFinishes / selectQuestionnaireStylePack）純搬家到
// scene_furniture_offers.js 的 createFurnitureOffers 工廠。參數依原名注入
// 模組作用域依賴，解構回同名 const，呼叫端零改動；只有工廠內部互相呼叫的
// 函式不解構。shortlistState 與 questionnaireFurnitureInFlight 單例隨函式
// 一起搬到新模組模組層。
const {
  renderQuestionnaireFinishes,
  questionnaireMaterialPairCards,
  selectQuestionnaireMaterialPair,
  selectQuestionnaireStylePack,
  questionnaireFurnitureRequest,
  catalogCandidatesForType,
  ensureFurnitureShortlist,
  catalogOffersForRoomPlans,
  toggleQuestionnaireFurniturePreferenceTag,
  occupancyForRoom,
  questionnaireFurnitureSpecsForRoom,
  ensureRoomUsage,
  renderQuestionnaireRoomUsage,
  renderGenerativeEquipment,
  updateGenerativeEquipment,
  updateGenerativeEquipmentNotes,
  roomFurnitureRequirement,
  renderQuestionnaireFurnitureRecommendations,
  ensureQuestionnaireFurnitureRecommendations,
  updateQuestionnaireFurnitureSelection,
  updateQuestionnaireFurnitureVariant,
  updateQuestionnaireFurnitureQuantity,
  refreshQuestionnaireFurnitureRecommendations,
} = createFurnitureOffers({
  state,
  element,
  $,
  escapeHtml,
  api,
  errorMessage,
  setStatus,
  scheduleSave,
  invalidateDownstreamFrom,
  normalizedRoomTypeValue,
  activeQuestionnaireRoom,
  activeQuestionnairePack,
  activeRoomFinishDraft,
  wholeHouseFinishDraft,
  livingRoomForCirculation,
  circulationStyleIsOverridden,
  copyLivingRoomStyleToCirculation,
  knownUnavailableCatalogFurnitureIds,
  replacementCandidateFitsRoom,
  unavailableCatalogModelUrls,
  verifiedCatalogModelUrls,
});

function ragJobsFromShortlist() {
  // 把已保存的候選集收斂成逐房 RAG 工作紀錄(終態+原因+指紋)。舊存檔的
  // 候選集沒有 status 欄位時就地推導,不強迫使用者重建。
  const shortlist = state.project?.workflow?.furniture_shortlist;
  if (!shortlist || !Array.isArray(shortlist.rooms)) return {};
  const jobs = {};
  shortlist.rooms.forEach((room) => {
    const roomId = String(room.room_id || "");
    if (!roomId) return;
    const itemCount = Array.isArray(room.items) ? room.items.length : 0;
    jobs[roomId] = {
      status: room.status || (itemCount ? "completed" : "unavailable"),
      reason: room.status_reason || (itemCount ? "" : "型錄查無符合此房需求的候選"),
      fingerprint: String(shortlist.fingerprint || ""),
      item_count: itemCount,
      semantic: Boolean(shortlist.semantic),
      generated_at: shortlist.generated_at || null,
    };
  });
  return jobs;
}

function knownUnavailableCatalogFurnitureIds() {
  const failedInstanceIds = new Set(
    (whiteViewer.getDiagnostics()?.failedFurniture || [])
      .map((item) => String(item.id)),
  );
  return new Set(
    (state.sceneData?.scene_objects || [])
      .filter((sceneObject) => {
        const item = furniture2dItemForSceneObject(state.furniture2d, sceneObject);
        return item && failedInstanceIds.has(String(item.id));
      })
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

async function autoLayoutFurniture() {
  state.furniture2d = [];
  const placementResolutions = [];
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
      : recommendedFurnitureForRoom(room, occupancyForRoom(room));
    // 視覺問卷已拆除：偏好清單恆為空，僅保留欄位形狀給選件 context 與引擎 payload。
    const visualPreferences = [];
    const preferredSpecs = requestedSpecs;
    const companionSpecs = userSelectedSpecs.length
      ? []
      : recommendCompanionFurniture(
        room.type,
        preferredSpecs.map(([type]) => type),
      ).map((item) => [item.type, item.variantId, item.reason, true]);
    const feasibleSpecs = specsAllowedByRoomFeasibility(
      requirement,
      [...preferredSpecs, ...companionSpecs],
    );
    // 自動推薦走尺寸預檢；使用者親自勾選的清單不過濾（引擎實擺、失敗再降級）。
    const specs = userSelectedSpecs.length
      ? feasibleSpecs
      : feasibleSpecs.filter((spec) => specFitsRoomDimensions(spec, room));
    const placementPreferences = {};
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
    placementResolutions.push(...(layout.placement_resolution_report || []));
    const placedById = new Map(
      (layout.scene_objects || []).map((item) => [item.furniture_id, item]),
    );
    roomItems.forEach((item) => {
      const placed = placedById.get(item.id);
      // 沒回來的是被擺放紀律移除的家具，報告會說明原因，這裡不要偷偷留著。
      if (!placed) return;
      applyPlacedCatalogSwap(item, placed);
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      state.furniture2d.push(item);
    });
  }
  const resolutionText = placementResolutionText(placementResolutions);
  if (resolutionText) {
    element.layoutError.textContent = resolutionText;
    setStatus(resolutionText, "warn");
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
      applyPlacedCatalogSwap(item, placed);
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      placedFurniture.push(item);
    });
  }
  // 2026-07 盤點修復：不再「任一件失敗即整包 null」（floor01 曾因此在第 5 步
  // 卡死）。失敗件帶 placementFailed 標記回傳，由呼叫端以 deferFailedPlacements
  // 列入「暫不放入」，其餘照常成案。
  return placedFurniture;
}

function specFitsRoomDimensions(spec, room) {
  // 推薦前尺寸預檢（2026-07 盤點方案 B 修復的治本半）：以變體預設尺寸對房間
  // 外框加 20 公分餘裕粗檢，小房間從源頭就不會被推薦塞不下的床與衣櫃。
  // 使用者親自勾選的家具不走此檢查——交給引擎實擺，失敗再列暫不放入。
  const match = findFurniture2DVariant(spec[0], spec[1]);
  const width = Number(match?.selected?.widthCm || 0);
  const depth = Number(match?.selected?.depthCm || 0);
  if (!width || !depth || !room?.polygon_cm?.length) return true;
  const dimensions = roomDimensions(room);
  const clearance = 20;
  return (
    width + clearance <= dimensions.widthCm
    && depth + clearance <= dimensions.depthCm
  ) || (
    depth + clearance <= dimensions.widthCm
    && width + clearance <= dimensions.depthCm
  );
}

function deferFailedPlacements(furnitureList, schemeLabel) {
  // 擺放失敗的家具移入該房「暫不放入」清單（沿用問卷 deferred 機制與
  // 第 6 步既有 UI），回傳可用件。方案生成從「全有或全無」改為逐件降級。
  const kept = [];
  for (const item of furnitureList || []) {
    if (item.placementFailed !== true) {
      kept.push(item);
      continue;
    }
    const furniture = roomFurnitureRequirement(item.roomId)?.furniture;
    if (furniture && !furniture.deferred.some(
      (entry) => String(entry.id) === String(item.id),
    )) {
      furniture.deferred.push({
        id: item.id,
        furniture_id: item.catalogFurnitureId || item.id,
        normalized_type: item.type,
        label: item.label,
        reason: `此格局放不下（方案 ${schemeLabel} 自動配置：${item.placementReason || "空間不足"}），本次暫不放入`,
      });
    }
  }
  return kept;
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
  return uniqueMaterialOptions(kind).find((option) => option.id === materialId)?.materialPreview || "";
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
  element.furnitureLibrary.innerHTML = variants.map(({ category, variant }) => {
    // 型錄沒有這族系的模型：2D 放得下，第 6 步一定選不到件、3D 一定缺席。
    // 標在按鈕上，使用者才不會擺完才發現東西不見了。
    const noModel = FAMILIES_WITHOUT_CATALOG_MODELS.includes(category.type);
    return `
    <button type="button" data-add-furniture-type="${escapeHtml(category.type)}" data-add-furniture-variant="${escapeHtml(variant.id)}"${
      noModel ? ' class="is-no-catalog-model" title="型錄目前沒有這類 3D 模型，可用於 2D 平面配置，但第 6 步不會產生 3D 家具。"' : ""
    }>
      <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(variant.iconPath)}"/></svg>
      <strong>${escapeHtml(variant.label)}</strong>
      <small>${variant.widthCm} × ${variant.depthCm} cm</small>
    </button>
  `;
  }).join("");
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

// ── 檯面小物宿主（2026-08-03 方案 B：檯面吸附最小模型）─────────────────

/** 小物目前的有效宿主；宿主不存在或小物已滑出宿主腳印時回 null。 */
function tabletopHostFor(item) {
  if (!item?.hostObjectId) return null;
  const host = state.furniture2d.find(
    (candidate) => String(candidate.id) === String(item.hostObjectId),
  );
  if (!host || host.placementFailed === true) return null;
  return pointWithinItemFootprint(item.xCm, item.yCm, host) ? host : null;
}

/** 放下／新增小物時嘗試吸附宿主；回傳是否有宿主。 */
function snapTabletopItem(item, { announce = true } = {}) {
  const host = findHostAt(
    item.xCm,
    item.yCm,
    item.type,
    state.furniture2d.filter(
      (candidate) => candidate.id !== item.id
        && candidate.roomId === item.roomId
        && candidate.placementFailed !== true,
    ),
  );
  if (host) {
    item.hostObjectId = host.id;
    item.hostSurfaceHeightCm = hostSurfaceHeightCm(host.type, host.heightCm);
    item.placementFailed = false;
    item.placementReason = "";
    if (announce) setStatus(`已把「${item.label}」放上「${host.label}」的檯面。`);
  } else {
    item.hostObjectId = null;
    item.hostSurfaceHeightCm = 0;
    item.placementReason = "請放到相容家具的檯面上（例如餐桌、茶几或層架）。";
    if (announce) setStatus(`「${item.label}」${item.placementReason}`, "error");
  }
  return Boolean(host);
}

/** 宿主被刪除時，站在它上面的小物全部落單並標待處理。 */
function orphanTabletopDependents(hostIds) {
  const ids = new Set([...hostIds].map(String));
  state.furniture2d.forEach((item) => {
    if (!item.hostObjectId || !ids.has(String(item.hostObjectId))) return;
    item.hostObjectId = null;
    item.hostSurfaceHeightCm = 0;
    item.placementReason = "宿主家具已刪除，請把它放到其他相容檯面上。";
  });
}

function itemCollision(item) {
  // 檯面小物不算落地碰撞；它的合法性只看「有沒有站在有效宿主上」。
  if (isTabletopType(item.type)) return tabletopHostFor(item) === null;
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
    // 與伺服器的 placed_others 同一套標準（scene_service.py）：放不下的家具
    // 停在 (0,0) 當佔位，拿它去比對會把房間中央附近所有合法家具打成待處理。
    if (other.placementFailed === true) return false;
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
      <span class="rp-model-state">${item.catalogFurnitureId || item.model_url ? "3D 家具" : "示意圖"}</span>
      <span aria-hidden="true">›</span>
    </button>
  `).join("");
  renderSelectedFurnitureEditor();
}

function configurationSceneObjectsByFurnitureId() {
  const sceneById = new Map();
  (state.sceneData?.scene_objects || []).forEach((sceneObject) => {
    const item = furniture2dItemForSceneObject(state.furniture2d, sceneObject);
    if (item) sceneById.set(String(item.id), sceneObject);
  });
  return sceneById;
}

// 2D 有、3D 沒有的家具。scene_objects 才是 3D 的唯一來源，被後端修復迴圈移除或
// 因缺 GLB 被濾掉的家具只會從 scene_objects 消失，2D 這側必須自己對帳補標，
// 否則清單會寫「合法」而 3D 一片空白（QA 2026-08-04 的電器櫃／浴櫃／收納櫃）。
function configurationFurnitureMissingFromScene(
  sceneById = configurationSceneObjectsByFurnitureId(),
) {
  const missing = new Map();
  // 場景還沒產生時不能判定缺件，否則第 5 步的 2D 會整批變成待處理。
  if (!Array.isArray(state.sceneData?.scene_objects)) return missing;
  const resolutionById = new Map(
    (state.sceneData?.placement_resolution_report || [])
      .filter((entry) => entry?.furniture_id)
      .map((entry) => [String(entry.furniture_id), String(entry.message_zh || "")]),
  );
  state.furniture2d.forEach((item) => {
    const key = String(item.id);
    if (sceneById.has(key)) return;
    missing.set(
      key,
      resolutionById.get(key)
        || (item.model_url
          ? "3D 場景沒有這件家具，請重新配置、更換或暫緩。"
          : "尚未找到可用的資料庫 3D 模型，請替換為可載入的家具。"),
    );
  });
  return missing;
}

function configurationBlockingFurniture() {
  const sceneById = configurationSceneObjectsByFurnitureId();
  const missingFromScene = configurationFurnitureMissingFromScene(sceneById);
  const modelFailureIds = new Set(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => String(item.id))
      : [],
  );
  return state.furniture2d.filter((item) => {
    const sceneObject = sceneById.get(String(item.id));
    return item.placementFailed === true
      || missingFromScene.has(String(item.id))
      || sceneObject?.placement_failed === true
      || modelFailureIds.has(String(item.id))
      || itemCollision(item);
  });
}

function configurationBlockingFurnitureByRoom(blocking = configurationBlockingFurniture()) {
  const groups = new Map();
  blocking.forEach((item) => {
    const room = state.rooms.find(
      (candidate) => String(candidate.id) === String(item.roomId),
    );
    const roomId = String(room?.id || item.roomId || "unassigned");
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
  return state.rooms.flatMap((room) => {
    const deferred =
      state.roomRequirementModel.roomRequirements[room.id]?.furniture?.deferred || [];
    return deferred.length
      ? [{ roomId: room.id, roomLabel: room.label, items: deferred }]
      : [];
  });
}

function configurationModelFailures() {
  return new Map(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => [String(item.id), item.reason])
      : [],
  );
}

// dataset 讀出來的 id 一律是字串，state.furniture2d 的 id 不一定是；用嚴格相等比對會靜默找不到。
function furniture2dById(furnitureId) {
  return state.furniture2d.find(
    (candidate) => String(candidate.id) === String(furnitureId),
  ) || null;
}

function configurationErrorSlot() {
  return state.workflow?.currentStep === "white_model_3d"
    ? element.whiteError
    : element.layoutError;
}

// 第 6 步的修復動作只要靜默 return，使用者看到的就是「按了沒反應」。所有失敗路徑都必須
// 走這裡，訊息才會同時落在目前步驟的錯誤欄位與狀態列，不會被寫進看不到的第 5 步欄位。
function reportConfigurationActionError(message) {
  const slot = configurationErrorSlot();
  if (slot) slot.textContent = message;
  setStatus(message, "error");
}

function clearConfigurationActionError() {
  const slot = configurationErrorSlot();
  if (slot) slot.textContent = "";
}

const CONFIGURATION_PENDING_LIST_SELECTOR = "#configuration-pending-list";
const CONFIGURATION_PENDING_ACTION_ATTRIBUTES = [
  "data-prioritize-configuration-room",
  "data-replace-configuration-furniture",
  "data-reflow-configuration-furniture",
  "data-remove-configuration-furniture",
  "data-defer-all-configuration-furniture",
];
const CONFIGURATION_PENDING_ACTION_SELECTOR = CONFIGURATION_PENDING_ACTION_ATTRIBUTES
  .map((name) => `[${name}]`)
  .join(",");

// 待處理清單是 innerHTML 全量重繪。若在使用者按住按鈕時換掉節點，瀏覽器就不會送出
// click（mousedown 與 mouseup 落在不同節點），整段修復動作會靜默消失。按住期間先把
// 新畫面存起來，等 pointerup 之後再補畫。
function writeConfigurationPendingList(markup) {
  if (configurationPendingPointerDown) {
    deferredConfigurationPendingMarkup = markup;
    return;
  }
  deferredConfigurationPendingMarkup = null;
  element.configurationPendingList.innerHTML = markup;
}

function flushDeferredConfigurationPendingList() {
  if (deferredConfigurationPendingMarkup == null) return;
  const markup = deferredConfigurationPendingMarkup;
  deferredConfigurationPendingMarkup = null;
  element.configurationPendingList.innerHTML = markup;
}

function configurationPendingActionKey(node) {
  if (!(node instanceof Element)) return "";
  const action = node.closest(CONFIGURATION_PENDING_ACTION_SELECTOR);
  if (!action || !action.closest(CONFIGURATION_PENDING_LIST_SELECTOR)) return "";
  const attribute = CONFIGURATION_PENDING_ACTION_ATTRIBUTES.find(
    (name) => action.hasAttribute(name),
  );
  return attribute ? `${attribute}=${action.getAttribute(attribute)}` : "";
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

function furnitureLedgerId(item = {}) {
  return String(
    item.id || item.layout_furniture_id || item.source_furniture_id
    || item.furniture_id || item.catalogFurnitureId || item.catalog_furniture_id || "",
  );
}

function configurationLedgerItems() {
  const deferred = configurationDeferredFurnitureByRoom().flatMap((group) => group.items);
  const removed = state.furnitureLedger?.removed || [];
  const unique = new Map();
  [...state.furniture2d, ...deferred, ...removed].forEach((item) => {
    const id = furnitureLedgerId(item);
    if (id && !unique.has(id)) unique.set(id, item);
  });
  const savedOrder = Array.isArray(state.furnitureLedger?.order)
    ? state.furnitureLedger.order.map(String)
    : [];
  const order = [...new Set(savedOrder.filter((id) => unique.has(id)))];
  unique.forEach((_item, id) => {
    if (!order.includes(id)) order.push(id);
  });
  state.furnitureLedger = { ...state.furnitureLedger, order, removed };
  return order.map((id) => unique.get(id));
}

function configurationLedgerSummary(blocking = configurationBlockingFurniture()) {
  const removedIds = new Set((state.furnitureLedger?.removed || []).map(furnitureLedgerId));
  const deferredIds = new Set(
    configurationDeferredFurnitureByRoom().flatMap((group) => group.items).map(furnitureLedgerId),
  );
  const pendingIds = new Set(blocking.map(furnitureLedgerId));
  const placedIds = new Set(state.furniture2d.map(furnitureLedgerId));
  removedIds.forEach((id) => {
    deferredIds.delete(id);
    pendingIds.delete(id);
    placedIds.delete(id);
  });
  deferredIds.forEach((id) => {
    pendingIds.delete(id);
    placedIds.delete(id);
  });
  pendingIds.forEach((id) => placedIds.delete(id));
  const placed = [...placedIds].filter(Boolean).length;
  const pending = [...pendingIds].filter(Boolean).length;
  const deferred = [...deferredIds].filter(Boolean).length;
  const removed = [...removedIds].filter(Boolean).length;
  return {
    placed,
    pending,
    deferred,
    removed,
    total: placed + pending + deferred + removed,
  };
}

function recordRemovedFurniture(item, reason = "使用者移除") {
  const id = furnitureLedgerId(item);
  if (!id) return;
  const removed = state.furnitureLedger?.removed || [];
  const order = Array.isArray(state.furnitureLedger?.order)
    ? state.furnitureLedger.order.map(String)
    : [];
  state.furnitureLedger = {
    order: order.includes(id) ? order : [...order, id],
    removed: [
      ...removed.filter((entry) => furnitureLedgerId(entry) !== id),
      { ...item, id, ledger_status: "removed", ledger_reason: reason },
    ],
  };
}

function configurationFurnitureNumber(item, fallbackIndex = state.furniture2d.indexOf(item)) {
  const id = furnitureLedgerId(item);
  const index = configurationLedgerItems().findIndex(
    (candidate) => furnitureLedgerId(candidate) === id,
  );
  return index >= 0 ? index + 1 : Math.max(0, fallbackIndex) + 1;
}

function configurationSceneObjectNumber(sceneObject, fallbackIndex = 0) {
  const item = furniture2dItemForSceneObject(state.furniture2d, sceneObject);
  return item ? configurationFurnitureNumber(item) : fallbackIndex + 1;
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
  if (scale > 0 && !state.showFurnitureNumbers) {
    element.configurationPlanLayer.innerHTML = "";
  }
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
  const ledger = configurationLedgerSummary(blocking);
  const ledgerMarkup = `<p class="rp-configuration-ledger" aria-live="polite">
    對帳：已配置 ${ledger.placed} · 待處理 ${ledger.pending} · 已暫緩 ${ledger.deferred} · 已移除 ${ledger.removed} · 合計 ${ledger.total}
  </p>`;
  const missingFromScene = configurationFurnitureMissingFromScene();
  const blockingMarkup = blockingRooms.map((group) => {
    const placementFailures = group.items.filter(
      (item) => !modelFailures.has(String(item.id))
        && !missingFromScene.has(String(item.id)),
    );
    // 沒有歸屬房間的家具算不出房間尺寸：重排、換小、擇優三個動作都必然失敗。
    // 照樣把按鈕畫出來只會讓使用者一直按一直失敗（QA 2026-08-01 #6 的死路）。
    const unassigned = group.roomId === "unassigned";
    const summary = unassigned
      ? "沒有對應的房間，無法用房間尺寸配置；請移除或暫緩"
      : placementFailures.length
        ? `${placementFailures.length} 件因碰撞、淨空或房間尺寸無法放入`
        : "資料庫模型無法載入，可更換或同意本次暫緩";
    const items = group.items.map((item) => {
      const furnitureNumber = configurationFurnitureNumber(item);
      const furnitureKey = String(item.id);
      const reason = unassigned
        ? "這件家具沒有歸屬房間，無法計算可用尺寸；請移除或暫緩後再從房間內重新加入。"
        : modelFailures.get(furnitureKey)
          || missingFromScene.get(furnitureKey)
          || item.placementReason
          || "家具碰撞、超出房間或淨空不足。";
      // 缺 GLB 的家具重排幾次都不會出現在 3D：只給「更換家具」，不給必然失敗的重排。
      const modelFailed = modelFailures.has(furnitureKey)
        || (missingFromScene.has(furnitureKey) && !item.model_url);
      // 重排的鎖必須是單件的：用全域 size > 0 會讓任何一件卡住就停掉整份清單的按鈕。
      const reflowing = configurationReflowInFlight.has(furnitureKey);
      const repairAction = unassigned
        ? ""
        : modelFailed
          ? `<button type="button" data-replace-configuration-furniture="${escapeHtml(item.id)}">更換家具</button>`
          : `<button type="button" data-reflow-configuration-furniture="${escapeHtml(item.id)}"
              ${reflowing ? "disabled" : ""}>${reflowing ? "重新配置中…" : "只重排此家具"}</button>
            <button type="button" data-replace-configuration-furniture="${escapeHtml(item.id)}">更換較小款</button>`;
      return `
        <div class="rp-configuration-pending-item">
          <b>${furnitureNumber}</b>
          <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(reason)}</small></span>
          <div>
            <button type="button" data-select-configuration-furniture="${escapeHtml(item.id)}">定位</button>
            ${repairAction}
            <button type="button" class="danger-action"
              data-remove-configuration-furniture="${escapeHtml(item.id)}">移除此家具</button>
          </div>
        </div>
      `;
    }).join("");
    return `
      <section class="rp-configuration-pending-room">
        <header>
          <div><strong>${escapeHtml(group.roomLabel)}</strong><small>${escapeHtml(summary)}</small></div>
          ${group.items.length && !unassigned ? `<button type="button"
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
  // 逃生口：家具引擎判定不合法的家具永遠不會進場景，但使用者也不能被永久卡在第 6 步。
  // 暫緩會把它們移出本次配置並記進 deferred，之後仍可回來重新加入。
  const escapeHatchMarkup = blocking.length
    ? `
      <div class="rp-configuration-pending-escape">
        <button type="button" data-defer-all-configuration-furniture>暫緩全部待處理家具並繼續</button>
        <small>放不下的家具會移出本次配置並記錄在「已暫緩」，第 6 步就不會被卡住。</small>
      </div>
    `
    : "";
  writeConfigurationPendingList(
    ledgerMarkup + (blockingMarkup
      || deferredMarkup
      || "<p class=\"rp-configuration-clear\">目前沒有待處理家具。</p>")
    + (blockingMarkup && deferredMarkup ? deferredMarkup : "")
    + escapeHatchMarkup,
  );

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
  if (configurationReflowInFlight.has(furnitureKey)) return;
  const item = state.furniture2d.find(
    (candidate) => String(candidate.id) === furnitureKey,
  );
  if (!item) {
    reportConfigurationActionError("找不到這件家具，請重新整理第 6 步後再試一次。");
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

async function removeConfigurationFurniture(furnitureId) {
  const furnitureKey = String(furnitureId);
  try {
    const removedItem = furniture2dById(furnitureKey);
    const sceneIndex = sceneObjectIndexByFurnitureId(furnitureKey);
    if (sceneIndex >= 0) {
      if (removedItem) recordRemovedFurniture(removedItem);
      state.selectedSceneIndex = sceneIndex;
      await deleteSelectedSceneFurniture();
      return;
    }
    // 只存在於 2D 清單、還沒進場景的家具沒有 scene_object 可刪，直接從 2D 移除。
    const remaining = state.furniture2d.filter(
      (item) => String(item.id) !== furnitureKey,
    );
    if (remaining.length === state.furniture2d.length) {
      reportConfigurationActionError("找不到這件家具，請重新整理第 6 步後再試一次。");
      return;
    }
    state.furniture2d = remaining;
    if (removedItem) recordRemovedFurniture(removedItem);
    syncFurnitureInventoryAcrossSchemes();
    if (String(state.selectedFurniture2dId) === furnitureKey) {
      state.selectedFurniture2dId = null;
    }
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    renderConfigurationPlan();
    scheduleSave("white_model_3d");
    setStatus("已移除這件家具，其餘家具位置保持不變。");
  } catch (error) {
    reportConfigurationActionError(errorMessage(error));
  }
}

// 家具引擎判定不合法的家具不會被塞進場景；這裡只是把它們記進 deferred 並移出本次配置，
// 讓第 6 步的確認閘門可以通過，而不是放寬幾何合法性。
async function deferAllBlockingConfigurationFurniture() {
  try {
    const blocking = configurationBlockingFurniture();
    if (!blocking.length) {
      reportConfigurationActionError("目前沒有待處理家具需要暫緩。");
      return;
    }
    // 3D 重載要好幾秒；先把「正在做」說出來，不然按鈕看起來又是沒反應。
    setStatus(`正在暫緩 ${blocking.length} 件放不下的家具…`);
    const modelFailures = configurationModelFailures();
    const blockingIds = new Set(blocking.map((item) => String(item.id)));
    blocking.forEach((item) => {
      const furniture = roomFurnitureRequirement(item.roomId);
      if (!furniture) return;
      furniture.deferred = [
        ...(furniture.deferred || []).filter(
          (entry) => String(entry.id) !== String(item.id),
        ),
        {
          id: item.id,
          furniture_id: item.catalogFurnitureId || item.id,
          normalized_type: item.type,
          label: item.label,
          reason: modelFailures.has(String(item.id))
            ? "資料庫模型無法載入，使用者同意本次暫不放入"
            : "空間放不下，使用者同意本次暫不放入",
        },
      ];
    });
    orphanTabletopDependents(blockingIds);
    state.furniture2d = state.furniture2d.filter(
      (item) => !blockingIds.has(String(item.id)),
    );
    if (state.sceneData) {
      state.sceneData.scene_objects = (state.sceneData.scene_objects || []).filter(
        (item) => !blockingIds.has(String(item.furniture_id)),
      );
    }
    syncFurnitureInventoryAcrossSchemes();
    const scheme = activeScheme();
    if (scheme) {
      scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
      if (state.sceneData) {
        scheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
      }
    }
    state.selectedFurniture2dId = null;
    state.selectedSceneIndex = 0;
    // 先更新 2D 與待處理清單再等 3D 重載，讓清單立刻清空而不是等好幾秒。
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    renderConfigurationPlan();
    scheduleSave("white_model_3d");
    if (state.sceneData) await whiteViewer.loadScene(state.sceneData);
    renderSceneObjectList();
    setStatus(
      `已暫緩 ${blocking.length} 件放不下的家具，現在可以進入第 7 步；暫緩清單留在待處理面板下方。`,
    );
  } catch (error) {
    reportConfigurationActionError(errorMessage(error));
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

async function prioritizeConfigurationRoomFurniture(roomId) {
  const room = state.rooms.find(
    (candidate) => String(candidate.id) === String(roomId),
  );
  if (!room) {
    reportConfigurationActionError(
      `這組待處理家具沒有對應的房間（${roomId}），無法擇優配置；請改用「移除此家具」或「暫緩全部待處理家具並繼續」。`,
    );
    return;
  }
  if (!state.sceneData) {
    reportConfigurationActionError("目前沒有可調整的 3D 場景，請先重新產生第 6 步配置。");
    return;
  }
  const originalItems = state.furniture2d
    .filter((item) => String(item.roomId) === String(roomId))
    .sort(compareConfigurationFurniturePriority);
  if (!originalItems.length) {
    reportConfigurationActionError(`「${room.label}」目前沒有可重新配置的家具。`);
    return;
  }
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
    if (furniture) {
      furniture.deferred = deferred.map((item) => ({
        id: item.id,
        furniture_id: item.catalogFurnitureId || item.id,
        normalized_type: item.type,
        label: item.label,
        reason: modelFailureIds.has(String(item.id))
          ? "資料庫模型無法載入，使用者同意本次暫不放入"
          : "使用者同意依空間尺寸擇優配置，本次暫不放入",
      }));
    }
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
  // 3D 主畫面與 2D 配置是互斥的 step panel：更換入口只放在 2D 那側時，
  // 走 3D 主畫面的使用者永遠看不到它（2026-08-03 Ben 實走發現）。
  // 這裡同步 3D 側的精簡版選取面板，兩條路都能更換。
  const whitePanel = $("#white-model-selected-furniture");
  const whiteName = $("#white-model-selected-name");
  if (!item) {
    element.selectedFurnitureEditor.hidden = true;
    if (whitePanel) whitePanel.hidden = true;
    return;
  }
  element.selectedFurnitureEditor.hidden = false;
  element.selectedFurnitureName.textContent = item.label;
  element.selectedFurnitureReason.textContent = `配置原因：${item.reason || "使用者手動加入，可調整實際尺寸。"}`;
  element.selectedFurnitureWidth.value = item.widthCm;
  element.selectedFurnitureDepth.value = item.depthCm;
  if (whitePanel && whiteName) {
    whitePanel.hidden = false;
    whiteName.textContent = item.label;
  }
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
  // 檯面小物不走引擎佈局（引擎管落地家具），放下時做宿主吸附。
  if (isTabletopType(drag.item.type)) {
    snapTabletopItem(drag.item);
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具位置已修改，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
    return;
  }
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
      // 宿主移動時，站在它檯面上的小物跟著走同樣的位移。
      const deltaX = drag.item.xCm - drag.originalX;
      const deltaY = drag.item.yCm - drag.originalY;
      if (deltaX || deltaY) {
        state.furniture2d.forEach((candidate) => {
          if (String(candidate.hostObjectId || "") !== String(drag.item.id)) return;
          candidate.xCm += deltaX;
          candidate.yCm += deltaY;
        });
      }
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
  const current = furniture2dById(state.selectedFurniture2dId);
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

function showReplacementEmptyState(message) {
  element.replacementError.textContent = message;
  element.replacementResults.dataset.items = "[]";
  element.replacementResults.innerHTML = `<p>${escapeHtml(message)}</p>`;
}

// 候選為空時要說清楚是哪一關擋掉的：型錄沒回、沒有可用模型、還是放不進房間。
// 只丟一句「沒有符合的家具」等於讓使用者自己猜。
function replacementEmptyStateMarkup({ room, catalogCount = 0, availableCount = 0 } = {}) {
  if (!catalogCount) {
    return "<p>家具資料庫沒有回傳這個類型的候選。請改選「瀏覽全部家具資料庫」，或換個關鍵字搜尋。</p>";
  }
  if (!availableCount) {
    return `<p>找到 ${catalogCount} 筆候選，但都沒有可用的 3D 模型。請改選「瀏覽全部家具資料庫」。</p>`;
  }
  const dimensions = room ? roomDimensions(room) : null;
  if (!dimensions?.widthCm || !dimensions?.depthCm) {
    return `<p>「${escapeHtml(room?.label || "目前房間")}」沒有可用的房間尺寸，無法判斷哪些家具放得下；請回第 4 步確認房間邊界。</p>`;
  }
  return `<p>找到 ${availableCount} 筆候選，但都放不進「${escapeHtml(room.label)}」`
    + `（可用 ${Math.round(dimensions.widthCm)} × ${Math.round(dimensions.depthCm)} cm，另需 20 cm 淨空）。`
    + "請改選「瀏覽全部家具資料庫」或挑更小的類型。</p>";
}

function renderReplacementCandidates(candidates, context = {}) {
  element.replacementResults.dataset.items = JSON.stringify(candidates);
  element.replacementResults.innerHTML = candidates.map((candidate, index) => {
    const title = candidate.name_zh || candidate.name_zh_raw || candidate.name_en || "家具";
    const image = replacementCandidateImageUrl(candidate);
    const materialLabel = candidate.material
      || (Array.isArray(candidate.materials) ? candidate.materials.join("、") : "")
      || "材質未標示";
    return `
      <article>
        <button type="button" class="rp-replacement-candidate" data-preview-replacement="${escapeHtml(candidate.furniture_id)}">
          <span class="rp-replacement-thumb">
            <img
              class="${image ? "" : "rp-fallback-thumbnail"}"
              src="${escapeHtml(image || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")}"
              alt="${escapeHtml(title)} 預覽圖"
              loading="lazy"
            >
          </span>
          <span><strong>${escapeHtml(title)}</strong>
            <small>${Number(candidate.size_cm?.width || 0).toFixed(0)} × ${Number(candidate.size_cm?.depth || 0).toFixed(0)} × ${Number(candidate.size_cm?.height || 0).toFixed(0)} cm</small>
            <small>${escapeHtml(candidate.primary_style || state.activeStyleId || "符合目前風格")} · ${escapeHtml(materialLabel)}</small>
          </span>
        </button>
        <button type="button" class="primary-action" data-confirm-replacement="${escapeHtml(candidate.furniture_id)}">以此家具取代</button>
      </article>
    `;
  }).join("") || replacementEmptyStateMarkup(context);
  if (candidates[0]) previewReplacementCandidate(candidates[0]);
}

async function loadReplacementCandidates() {
  const current = furniture2dById(state.selectedFurniture2dId);
  if (!current) {
    // 原本這裡是裸 return，候選區會停在前一次的內容或整片空白，使用者看不到任何原因。
    showReplacementEmptyState(
      "找不到目前選取的家具，請關閉視窗後重新選取再更換。",
    );
    return;
  }
  const room = state.rooms.find(
    (candidate) => String(candidate.id) === String(current.roomId),
  );
  if (!room) {
    showReplacementEmptyState(
      `「${current.label}」沒有對應的房間，無法用房間尺寸挑選候選家具；請回第 4 步確認房間後再試。`,
    );
    return;
  }
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
  const available = rankCatalogFurniture(catalogCandidates, request).filter(
    (candidate) => !knownUnavailableCatalogFurnitureIds().has(
      String(candidate.furniture_id),
    ),
  );
  const candidates = available
    .filter((candidate) => replacementCandidateFitsRoom(candidate, room))
    .slice(0, 24);
  element.replacementFilterSummary.textContent =
    `${room.label} · ${current.label} · ${style || "目前風格"} · 房間內可配置尺寸`;
  renderReplacementCandidates(candidates, {
    room,
    catalogCount: catalogCandidates.length,
    availableCount: available.length,
  });
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

async function openFurnitureReplacement() {
  if (!state.selectedFurniture2dId) {
    reportConfigurationActionError("請先選取一件要更換的家具。");
    return;
  }
  const current = furniture2dById(state.selectedFurniture2dId);
  if (!current) {
    reportConfigurationActionError("找不到目前選取的家具，請重新選取後再更換。");
    return;
  }
  renderReplacementTypeOptions(current);
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
  const current = furniture2dById(state.selectedFurniture2dId);
  if (!catalogItem || !current) {
    element.replacementError.textContent = catalogItem
      ? "找不到目前選取的家具，請關閉視窗後重新選取。"
      : "找不到這個候選款式，請重新搜尋家具資料庫。";
    return;
  }
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
  // 3D 主畫面也能叫出更換抽屜（2026-08-03 起），所以換完必須同步 scene_objects
  // 並重載 viewer——只更新 2D 的話，使用者在 3D 看到的還是舊床架。
  const sceneObjects = state.sceneData?.scene_objects;
  const sceneIndex = sceneObjectIndexByFurnitureId(current.id);
  if (sceneIndex >= 0) {
    sceneObjects[sceneIndex] = {
      ...sceneObjects[sceneIndex],
      ...toSceneFurniture(candidate),
      furniture_id: sceneObjects[sceneIndex].furniture_id,
    };
    renderConfigurationPlan();
    try {
      await whiteViewer.loadScene(state.sceneData);
      renderSceneObjectList();
    } catch (error) {
      console.warn("更換家具後 3D 重載失敗", error);
    }
  }
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
  // 檯面小物新增在房間中心通常沒有宿主：吸附失敗會標紅並提示拖到檯面上。
  if (isTabletopType(item.type)) snapTabletopItem(item, { announce: false });
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
    // 型錄沒有 storage-cabinet／appliance-cabinet／bathroom-vanity 這三個名字，
    // 櫃體一律存成 cabinet-cupboard（146 筆）。這裡原本直接把 item.type 丟給
    // /api/furniture，那三族系一律查到 0 筆 → 沒有 model_url → 標成
    // placementFailed，於是「2D 放得下、3D 永遠缺席」。更換家具那條路
    // （renderReplacementTypeOptions）與後端 scene_service 的
    // catalog_types_for_family 都早就繞過同義分類，只有自動配置這條漏掉。
    // catalogCandidatesForType 會套用 CATALOG_RETRIEVAL_ROUTES 的同義分類與
    // 關鍵字，並保留「先帶風格、查不到再拿掉風格重試」的既有行為。
    const items = await catalogCandidatesForType(item.type, { styleId: request.styleId });
    const candidates = rankCatalogFurniture(items, request);
    if (!candidates.length) return toSceneFurniture(item);
    return mergeCatalogFurniture(item, candidates[0]);
  } catch (error) {
    console.warn(error);
    return toSceneFurniture(item);
  }
}

function applyPlacedCatalogSwap(item, placed) {
  // 後端換小款之後，2D 卡片與 3D 都必須跟著換型號；只更新座標的話畫面上還是
  // 那件放不下的家具，使用者會以為系統騙他。
  const swappedId = String(placed?.catalog_furniture_id || "");
  if (!swappedId || swappedId === String(item.catalogFurnitureId || "")) return false;
  item.catalogFurnitureId = swappedId;
  if (placed.name_zh_raw) item.label = placed.name_zh_raw;
  if (placed.model_url) item.model_url = placed.model_url;
  const size = placed.size_cm || {};
  if (Number(size.width) > 0) item.widthCm = Number(size.width);
  if (Number(size.depth) > 0) item.depthCm = Number(size.depth);
  if (Number(size.height) > 0) item.heightCm = Number(size.height);
  return true;
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
    setStatus(state.furniture2d.length
      ? "正在依問卷、色卡與尺寸載入資料庫 3D 家具…"
      : "沒有家具需求，正在產生純結構 3D 配置…");
    const applianceRequirements = applianceRequirementsForRendering(state.furniture2d);
    const placeableFurniture = removeRetiredAppliancesFromFurniture(state.furniture2d);
    const selectedFurniture = await Promise.all(placeableFurniture.map(resolveCatalogFurniture));
    const missingCatalogModels = selectedFurniture.filter((item) => !item.model_url);
    if (missingCatalogModels.length && !allowPendingFurniture) {
      element.layoutError.textContent =
        `有 ${missingCatalogModels.length} 件家具尚未找到可用的資料庫 3D 模型：${
          missingCatalogModels
            .map((item) => item.name_zh_raw || item.normalized_type)
            .join("、")
        }。請更換家具或確認型錄模型後再進入配置預覽。`;
      setStatus("資料庫家具尚未完整，已停止產生替代模型。", "error");
      return;
    }
    if (missingCatalogModels.length) {
      // resolveCatalogFurniture 回的是 scene 形狀（toSceneFurniture 把 item.id 寫進
      // furniture_id），沒有 id 欄位。用 item.id 取鍵會全部變成 "undefined"，
      // 這裡就一件也標不到，缺 GLB 的家具會頂著「合法」被濾出 3D。
      const missingIds = new Set(
        missingCatalogModels.map((item) => String(item.furniture_id || item.id || "")),
      );
      state.furniture2d = state.furniture2d.map((item) => (
        missingIds.has(String(item.id))
          ? {
            ...item,
            placementFailed: true,
            placementReason: "尚未找到可用的資料庫 3D 模型，請替換為可載入的家具。",
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
    // 視覺問卷已拆除：保留 visual_preferences 鍵形狀，值恆為空陣列。
    const visualPreferences = [];
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
          needs: [state.basicAnswers.lifestyle].filter(Boolean),
          constraints: ["keep_door_clear", "keep_window_clear"],
        },
        questionnaire: {
          catalog_version: state.visualCatalogVersion,
          basic: state.basicAnswers,
          visual_preferences: visualPreferences,
          finishes: state.questionnaireFinishes,
          room_requirements: roomRequirementsPayload.roomRequirements,
          appliance_requirements: applianceRequirements,
          // 逐房 RAG 終態隨問卷送進 scene_json,生圖交接檔(agent_generation_
          // handoff)靠它說明每房候選是怎麼來的、失敗原因是什麼。
          rag_jobs: ragJobsFromShortlist(),
        },
        room_surface_assignments: roomSurfaces,
        personal_notes: state.basicAnswers.immutableNeeds || "",
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
    // 對帳：3D 只畫 scene_objects。後端修復迴圈換小/移除、或前端缺 GLB 濾掉的家具
    // 都只會在 scene_objects 消失，furniture2d 這側不會自己少一件。不補標的話
    // 2D 清單會繼續寫「合法」，使用者看到的是 2D 有、3D 沒有卻沒有任何說明。
    const missingFromScene = configurationFurnitureMissingFromScene();
    if (missingFromScene.size) {
      state.furniture2d = state.furniture2d.map((item) => (
        missingFromScene.has(String(item.id))
          ? {
            ...item,
            placementFailed: true,
            placementReason: item.placementReason
              || missingFromScene.get(String(item.id)),
          }
          : item
      ));
    }
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
    element.layoutError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

async function generateWhiteModelFromRequirements({ returnToRequirementsOnFailure = false } = {}) {
  if (state.autoGeneratingWhiteModel) return false;
  state.autoGeneratingWhiteModel = true;
  element.layoutError.textContent = "";
  try {
    if (!state.workflow?.goTo("layout_2d")) {
      const message = firstWorkflowBlocker("layout_2d");
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
  const markup = objects.map((item, index) => {
    const furnitureNumber = configurationFurnitureNumber(item, index);
    return `
    <button type="button" data-scene-object-index="${index}" class="${index === state.selectedSceneIndex ? "is-active" : ""}">
      <strong><b class="rp-object-number">#${furnitureNumber}</b>${escapeHtml(sceneObjectDisplayName(item, index))}</strong>
      <span>${item.model_url ? "資料庫 3D 家具" : "缺少 3D 模型"}</span>
      <small>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</small>
      <small>${item.user_specified ? "已指定" : "系統選配"}</small>
    </button>
  `;
  }).join("");
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
  recordRemovedFurniture(selected);
  objects.splice(state.selectedSceneIndex, 1);
  state.furniture2d = removeFurniture2dBySceneObject(
    state.furniture2d,
    selected,
  );
  orphanTabletopDependents([selected.furniture_id]);
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
    `已刪除「${selected.name_zh_raw || selected.normalized_type || "家具"}」，原編號已保留在對帳紀錄。`,
  );
}

// ── 問卷家具型錄瀏覽模式（bella-test1 fd0cee11＋23de9dda questionnaire-catalog-space-groups）──
// 第 5 步「新增家具」改開瀏覽模式：先選空間（可切「全部空間」）、再選用途，
// 只顯示中文名稱與對應用途；同一個型錄 dialog 在第 6 步仍是原本的搜尋模式。

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

// 第三欄是 QUESTIONNAIRE_CATALOG_PURPOSE_TYPES 缺項時的後備型別清單，會直接
// 拿去比對 normalized_type，所以只能放型錄實際存在的分類名（型錄沒有
// storage-cabinet／appliance-cabinet／bathroom-vanity／lounge-chair／shelf，
// 一律用 cabinet-cupboard／armchair／shelving-unit）。
const QUESTIONNAIRE_CATALOG_PURPOSES = Object.freeze({
  bedroom: [
    ["sleep", "睡眠", ["bed", "bedside-table"]],
    ["storage", "收納", ["wardrobe", "cabinet-cupboard"]],
    ["dress", "更衣", ["wardrobe", "mirror", "stool-bench"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair"]],
    ["vanity", "梳妝", ["mirror", "desk", "stool-bench"]],
  ],
  living_room: [
    ["rest", "休息聊天", ["sofa", "coffee-table", "armchair"]],
    ["media", "影音", ["tv-bench", "sofa", "armchair"]],
    ["dining", "用餐", ["dining-table", "dining-chair", "cabinet-cupboard"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "cabinet-cupboard", "stool-bench"]],
  ],
  kitchen: [
    ["dining", "用餐", ["dining-table", "dining-chair"]],
    ["prep", "備餐收納", ["cabinet-cupboard", "storage-furniture"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "dining-chair"]],
  ],
  storage: [
    ["storage", "收納整理", ["cabinet-cupboard", "wardrobe", "shelving-unit"]],
    ["work", "閱讀工作", ["desk", "office-chair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "cabinet-cupboard"]],
  ],
  entryway: [["entry", "出門整理", ["mirror", "cabinet-cupboard", "stool-bench"]]],
  hallway: [["passage", "走道收納", ["mirror", "cabinet-cupboard"]]],
  circulation: [["passage", "走道收納", ["mirror", "cabinet-cupboard"]]],
  bathroom: [["wash", "盥洗收納", ["cabinet-cupboard", "mirror-cabinet"]]],
  balcony: [["relax", "休憩植栽", ["armchair", "flower-pots-planter", "stool-bench"]]],
  garage: [["garage", "工具收納", ["cabinet-cupboard", "shelving-unit"]]],
});

const QUESTIONNAIRE_CATALOG_PURPOSE_TYPES = Object.freeze({
  "bedroom:sleep": ["bed", "mattress"],
  "bedroom:storage": ["pax-wardrobe", "wardrobe", "chests-of-drawer"],
  "bedroom:dress": ["pax-wardrobe", "wardrobe", "mirror", "stool-bench"],
  "bedroom:work": ["desk", "office-chair", "armchair"],
  "bedroom:vanity": ["mirror", "desk", "stool-bench"],
  "living_room:rest": ["fabric-sofa", "sofa", "leather-sofa", "modular-sofa", "coffee-table", "armchair"],
  "living_room:media": ["tv-bench", "tv-media-furniture", "sofa", "armchair"],
  "living_room:dining": ["dining-table", "dining-chair", "bar-table"],
  "living_room:work": ["desk", "office-chair", "armchair"],
  "living_room:kids": [
    "kids-chairs-stool", "childrens-table", "childrens-furniture",
    "childrens-stools-benche", "storage-boxes-basket", "stool-bench",
  ],
  "kitchen:dining": ["dining-table", "dining-chair", "bar-table"],
  "kitchen:prep": ["table", "bar-table", "stool-bench"],
  "kitchen:kids": [
    "dining-chair", "kids-chairs-stool", "childrens-table",
    "childrens-stools-benche", "stool-bench",
  ],
  "storage:storage": [
    "cabinet-cupboard", "shelving-unit", "bookcase", "display-cabinet",
    "storage-boxes-basket",
  ],
  "storage:work": ["desk", "office-chair", "gaming-chair"],
  "storage:kids": [
    "storage-boxes-basket", "kids-chairs-stool", "childrens-furniture",
    "childrens-stools-benche", "stool-bench",
  ],
  "entryway:entry": ["shoe-cabinet", "mirror", "stool-bench", "clothes-rack"],
  "hallway:passage": ["wall-shelf", "mirror", "shoe-cabinet"],
  "circulation:passage": ["wall-shelf", "mirror", "shoe-cabinet"],
  "bathroom:wash": ["mirror-cabinet", "cabinet-cupboard"],
  "balcony:relax": ["armchair", "flower-pots-planter", "stool-bench"],
  "garage:garage": ["cabinet-cupboard", "shelving-unit", "storage-solution-system"],
});

const QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS = Object.freeze({
  "office-chair": "閱讀工作", "gaming-chair": "閱讀工作", armchair: "閱讀休憩",
  "lounge-chair": "閱讀休憩", "dining-chair": "用餐", "stool-bench": "梳妝／臨時座位",
  "kids-chairs-stool": "兒童使用", bed: "睡眠", wardrobe: "收納更衣", desk: "閱讀工作",
  "dining-table": "用餐", sofa: "休息聊天", "coffee-table": "客廳置物", "tv-bench": "影音",
  "storage-cabinet": "收納整理", "pax-wardrobe": "收納更衣", "fabric-sofa": "休息招待",
  "leather-sofa": "休息招待", "modular-sofa": "休息招待", table: "備餐整理",
  "bar-table": "用餐備餐", "cabinet-cupboard": "收納整理", "shelving-unit": "收納整理",
  "storage-boxes-basket": "收納整理", "storage-solution-system": "收納整理",
  "wall-shelf": "走道收納", "shoe-cabinet": "玄關整理", "clothes-rack": "玄關整理",
  "tv-media-furniture": "影音設備", "chests-of-drawer": "收納整理", mirror: "更衣梳妝",
  shelf: "收納整理", bookcase: "閱讀工作", lighting: "照明安全",
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
  if (!questionnaireCatalogPurpose && (QUESTIONNAIRE_CATALOG_PURPOSES[activeSpace] || []).length) {
    return "請選擇家具用途，再查看對應的家具選項。";
  }
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
}

function questionnaireCatalogGroup(room) {
  const type = questionnaireCatalogRoomType(room);
  return {
    bedroom: "bedroom",
    living_room: "living",
    kitchen: "dining_kitchen",
    storage: "study",
    bathroom: "bathroom",
    balcony: "outdoor",
  }[type] || "storage";
}

function setCatalogSelectOptions(select, options, value, labelKey = "label", valueKey = "value", emptyLabel = "全部") {
  if (!select) return;
  const safeValue = String(value || "");
  select.innerHTML = [`<option value="">${escapeHtml(emptyLabel)}</option>`, ...options.map((option) => {
    const optionValue = String(option[valueKey] || option.type || "");
    const optionLabel = String(option[labelKey] || option.type_name_zh || optionValue);
    return `<option value="${escapeHtml(optionValue)}" ${optionValue === safeValue ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
  })].join("");
}

function renderQuestionnaireCatalogFilters(payload) {
  if (!questionnaireCatalogRoomId) return;
  const facets = payload.filter_options || {};
  setCatalogSelectOptions(element.questionnaireCatalogColor, facets.colors || [], element.questionnaireCatalogColor?.value || "", "label", "value", "全部顏色");
  setCatalogSelectOptions(element.questionnaireCatalogMaterial, facets.materials || [], element.questionnaireCatalogMaterial?.value || "", "label", "value", "全部材質");
}

function openQuestionnaireFurnitureCatalog(roomId = activeQuestionnaireRoom()?.id) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  if (!room) return;
  questionnaireCatalogRoomId = room.id;
  questionnaireCatalogScope = "room";
  questionnaireCatalogSpace = "";
  questionnaireCatalogPurpose = "";
  element.catalogDrawer.querySelector("h2").textContent = `加入${room.label}的家具`;
  element.catalogDrawer.querySelector("header p").textContent = "先選空間與用途瀏覽適合的家具；也可直接搜尋（例如「椅子」會涵蓋工作椅、閱讀椅與椅凳）。";
  if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = false;
  element.questionnaireCatalogControls?.querySelectorAll("[data-questionnaire-catalog-scope]")
    .forEach((item) => item.classList.toggle("is-active", item.dataset.questionnaireCatalogScope === "room"));
  $("#glb-furniture-search").value = "";
  if (element.questionnaireCatalogType) element.questionnaireCatalogType.value = "";
  if (element.questionnaireCatalogColor) element.questionnaireCatalogColor.value = "";
  if (element.questionnaireCatalogMaterial) element.questionnaireCatalogMaterial.value = "";
  element.glbResults.innerHTML = "<p>正在載入適合本房的家具…</p>";
  renderQuestionnaireCatalogBrowseChoices(room);
  setFurnitureCatalogOpen(true);
  void searchGlbFurniture();
}

function addQuestionnaireCatalogFurniture(furnitureId) {
  const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
  const furniture = roomFurnitureRequirement(room?.id);
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const offer = items.find((item) => String(item.furniture_id) === String(furnitureId));
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
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已將家具加入「${room.label}」，第 6 步需要重新產生。`);
  scheduleSave("requirements");
  setStatus(`已將家具加入「${room.label}」。`, "success");
}

function setFurnitureCatalogOpen(open) {
  if (open) {
    if (!questionnaireCatalogRoomId) {
      element.catalogDrawer.querySelector("h2").textContent = "新增家具";
      element.catalogDrawer.querySelector("header p").textContent = "搜尋後選擇家具，再回到 3D 房間點選合法擺放位置。";
      if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = true;
      activateWhiteFurnitureEditing();
    }
    if (typeof element.catalogDrawer.showModal === "function" && !element.catalogDrawer.open) {
      element.catalogDrawer.showModal();
    } else if (!element.catalogDrawer.open) {
      element.catalogDrawer.setAttribute("open", "");
    }
    $("#glb-furniture-search").focus();
    return;
  }
  if (typeof element.catalogDrawer.close === "function") {
    element.catalogDrawer.close();
  } else {
    element.catalogDrawer.removeAttribute("open");
  }
  questionnaireCatalogRoomId = null;
}

async function searchGlbFurniture() {
  const query = $("#glb-furniture-search").value.trim();
  const questionnaireMode = Boolean(questionnaireCatalogRoomId);
  if (!query && !questionnaireMode) {
    element.glbResults.innerHTML = "<p>請輸入家具名稱。</p>";
    return;
  }
  const thumbnailBatch = ++glbThumbnailBatch;
  try {
    const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
    const params = new URLSearchParams({ has_model: "true", detail: "scene", page_size: questionnaireMode ? "48" : "12" });
    if (query) params.set("q", query);
    // 搜尋文字可跨用途找同類家具；未搜尋時才依空間與用途收斂。
    const activeSpaceDefinition = QUESTIONNAIRE_CATALOG_SPACES.find(
      (space) => space.id === questionnaireCatalogActiveSpace(room),
    );
    const activePurpose = questionnaireMode ? questionnaireCatalogPurposeDefinition(room) : null;
    const browsePrompt = questionnaireMode
      ? questionnaireCatalogBrowsePrompt(room, query)
      : "";
    if (browsePrompt) {
      element.glbResults.innerHTML = `<p class="rp-catalog-browse-prompt">${escapeHtml(browsePrompt)}</p>`;
      element.glbResults.dataset.items = "[]";
      return;
    }
    if (!query && questionnaireMode) {
      params.set("group", activeSpaceDefinition?.group || questionnaireCatalogGroup(room));
    }
    if (questionnaireMode) {
      const color = element.questionnaireCatalogColor?.value || "";
      const material = element.questionnaireCatalogMaterial?.value || "";
      if (color) params.set("color", color);
      if (material) params.set("material", material);
    }
    const payload = await api(`/api/furniture?${params.toString()}`);
    renderQuestionnaireCatalogFilters(payload);
    // 本機 /api/furniture 沒有 types 多值參數：用途型別在前端收斂。
    const purposeTypes = new Set(activePurpose?.[2] || []);
    const purposeFiltered = questionnaireMode && !query && purposeTypes.size
      ? (payload.items || []).filter((item) => purposeTypes.has(
        String(item.normalized_type || item.category || item.taxonomy_type || ""),
      ))
      : (payload.items || []);
    const catalogItems = questionnaireMode
      ? [...new Map(purposeFiltered.map((item) => {
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
      const title = item.name_zh || item.name_zh_raw || item.name_en || "3D 家具";
      if (questionnaireMode) {
        // 問卷瀏覽模式只顯示中文名稱與對應用途，不露原始型錄長名。
        const optionLabel = questionnaireFurnitureDisplayLabel(item) || "其他家具";
        const purposeLabel = QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS[item.normalized_type]
          || "可加入配置";
        return `
          <article class="rp-glb-result rp-questionnaire-catalog-option">
            <span><strong>${escapeHtml(optionLabel)}</strong><small>適合：${escapeHtml(purposeLabel)}</small>
            <small>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</small></span>
            <div class="rp-inline-actions">
              <button type="button" data-add-questionnaire-furniture-id="${escapeHtml(item.furniture_id)}">加入此房</button>
            </div>
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
    }).join("") || "<p>找不到適合的 3D 家具。</p>";
    element.glbResults.dataset.items = JSON.stringify(catalogItems);
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
  setStatus("已更換 3D 家具，新尺寸與原位置已通過配置檢查。");
}

function addSceneFurniture(furnitureId) {
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const replacement = items.find((item) => item.furniture_id === furnitureId);
  if (!replacement || !state.sceneData) return;
  const started = whiteViewer.beginPlacement(async (positionCm) => {
    // 用落點反推房間歸屬：少了 placement_room_id，2D 同步會拿到 roomId=null，
    // 家具直接變成「未指定空間」的孤兒卡在待處理清單（2026-08-03 Ben 實走發現）。
    const center = planCenterCm();
    const dropPoint = {
      x: center.x + Number(positionCm?.x || 0),
      y: center.y + Number(positionCm?.z || 0),
    };
    const hostRoom = state.rooms.find(
      (room) => Array.isArray(room.polygon_cm) && pointInPolygonCm(dropPoint, room.polygon_cm),
    );
    const candidate = {
      ...replacement,
      furniture_id: `${replacement.furniture_id}-user-${Date.now()}`,
      catalog_furniture_id: replacement.furniture_id,
      name_zh_raw: replacement.name_zh || replacement.name_zh_raw || replacement.name_en,
      placement_room_id: hostRoom?.id || null,
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
      if (!hostRoom) {
        // 落在房間之外就別讓它進場：沒有歸屬房間就無法計算可用尺寸，
        // 進去也只會變成待處理清單裡無解的孤兒。
        element.whiteError.textContent = "請放在某個房間範圍內：這個位置不屬於任何房間，無法計算可用尺寸。";
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
      `有 ${diagnostics.failedFurniture.length} 件資料庫 3D 家具無法載入，請先修正型錄權限或更換家具，才能進入下一步。`;
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
      // 地板不開放手動調色，染色一律取材質代表色，材質更換才看得出差異。
      color: surfaceOptionColor(
        "floor",
        state.questionnaireFinishes.floorMaterial || preferredPack.floor.surfaceOption,
      ) || preferredPack.floor.color,
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
    ? "家具可見性已通過。現在可即時切換問卷主風格的 3 張色卡。"
    : "純結構配置已確認。現在可即時切換問卷主風格的 3 張色卡。");
  scheduleSave("realistic_3d");
}

function renderStyleControls() {
  // 主風格已在第 5 步問卷選定，這裡不再提供跨風格切換，只保留同風格三張色卡。
  const questionnairePack = STYLE_PACKS.find(
    (pack) => pack.id === state.questionnaireFinishes.stylePackId,
  );
  if (questionnairePack) state.activeStyleId = questionnairePack.styleId;
  const familyLabel =
    STYLE_FAMILIES.find((item) => item.id === state.activeStyleId)?.label
    || questionnairePack?.styleLabel
    || "";
  element.styleFamilyNote.textContent = questionnairePack
    ? `已依需求問卷鎖定「${familyLabel}」，以下為同風格的 3 張色卡。`
    : `尚未在第 5 步問卷選定全屋主風格，先以「${familyLabel}」示範；回問卷選定後這裡只保留該風格的色卡。`;
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
      $("#floor-material").value = activePack.floor.surfaceOption;
    }
    renderGroupedMaterialOptions(activePack);
  }
}

function syncSurfaceMaterialSelect(kind, items, current) {
  const select = $(`#${kind}-material`);
  if (!select) return "";
  // 使用者已選的材質不因風格清單過濾而被丟棄：清單裡沒有就以「自選」保留，
  // 否則 change 事件裡先重建清單會把選擇還原成推薦值，套用的不是使用者挑的。
  const listed = !current || items.some((item) => item.id === current)
    ? items
    : [...items, { id: current, label: `${surfaceMaterialLabel(kind, current)}（自選）` }];
  select.innerHTML = listed.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  const materialId = current && listed.some((item) => item.id === current)
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
  const options = [...merged.values()];
  if (kind !== "floor") return options;
  // 地板卡縮圖對齊 3D 實際載入的貼圖，卡片與 3D 才是同一張圖（bella-test1 不變式）。
  return options.map((option) =>
    alignOptionWithCatalogSurface(state.sceneData?.surface_catalog, "floor", option),
  );
}

function surfaceOptionColor(kind, materialId) {
  if (!materialId) return null;
  const styleOptions = materialOptionsForStyle(
    state.activeStyleId,
    kind,
    (STYLE_MATERIAL_OPTIONS[state.activeStyleId] || {})[kind],
  );
  const styled = styleOptions.find((item) => item.id === materialId);
  if (styled?.color) return styled.color;
  const resolved = resolveSurfaceOption(state.sceneData?.surface_catalog, kind, materialId);
  const surface = (state.sceneData?.surface_catalog?.surfaces || [])
    .find((item) => item.surface_id === resolved);
  return surface?.color_hex || null;
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
    const listedItems = !selectedMaterial || items.some((item) => item.id === selectedMaterial)
      ? items
      : [...items, { id: selectedMaterial, label: `${surfaceMaterialLabel(kind, selectedMaterial)}（自選）` }];
    host.innerHTML = listedItems.map((item) => {
      const isActive = item.id === selectedMaterial;
      const isRecommended = item.id === recommendedId;
      return `
      <button type="button"
        data-surface-kind="${escapeHtml(kind)}"
        data-surface-material="${escapeHtml(item.id)}"
        data-surface-color="${escapeHtml(item.color || "")}"
        data-material-preview="${escapeHtml(item.materialPreview || "")}"
        data-style-card-recommended="${isRecommended ? "true" : "false"}"
        aria-pressed="${isActive ? "true" : "false"}"
        title="${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}"
        class="${isActive ? "is-active" : ""}">
        <span class="rp-material-preview" style="background:${escapeHtml(item.color || "#ddd")};${item.materialPreview ? `background-image:url('${escapeHtml(item.materialPreview)}')` : ""}"></span>
        <span class="rp-material-card-copy">
          <span class="rp-material-card-title">
            <strong>${escapeHtml(item.label)}</strong>
            ${isActive || isRecommended ? `<span class="rp-material-badge">${isActive ? "目前選取" : "風格推薦"}</span>` : ""}
          </span>
          <small>${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}</small>
        </span>
      </button>
    `;
    }).join("");
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
  const skippedDecor = new Map();
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
    (result.decor_summary?.skipped || []).forEach((entry) => {
      skippedDecor.set(entry.role, entry);
    });
  }
  if (skippedDecor.size) {
    // 型錄缺某個角色的 GLB 不再中止整間房的軟裝，但也不能默默略過。
    setStatus(
      `軟裝已完成，但略過：${[...skippedDecor.values()]
        .map((entry) => entry.reason || entry.label)
        .join("；")}`,
      "warning",
    );
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
  realisticViewer.setViewMode(currentRealViewMode());
  element.realisticStatus.textContent = `已套用「${pack.styleLabel}／${pack.name}」的牆面、地板、寫實材質與燈光；家具搭配更新中。`;
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
    realisticViewer.setViewMode(currentRealViewMode());
  } catch (error) {
    console.warn(error);
    element.realisticStatus.textContent = `牆面、地板與燈光已套用；家具或軟裝更新失敗：${errorMessage(error)}`;
    scheduleSave("realistic_3d");
    return;
  }
  await evaluateCeilingConflicts();
  element.realisticStatus.textContent = `${pack.styleLabel}／${pack.name}：牆、地板、未鎖定家具與環境光已同步；軟裝與擺放規則已載入，新增物件仍須通過家具引擎配置。`;
  element.realisticStatus.textContent = `已完成「${pack.styleLabel}／${pack.name}」：牆面、地板、寫實材質、燈光與未鎖定家具均已同步。`;
  scheduleSave("realistic_3d");
}

// 套用材質、色卡或天花方案會重載場景；鏡頭要停在使用者目前的視角，
// 不硬跳回自由旋轉，否則工具列高亮與實際鏡頭會不一致。
function currentRealViewMode() {
  return $$("[data-real-view-mode]").find(
    (button) => button.classList.contains("is-active"),
  )?.dataset.realViewMode || "orbit";
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
  // 地板不開放手動調色：染色一律採用所選材質的代表色，換材質才看得出差異。
  const floorMaterialId = $("#floor-material").value;
  state.surfaceState.floor = {
    ...(state.surfaceState.floor || {}),
    color: surfaceOptionColor("floor", floorMaterialId)
      || stylePackByIdSafe(state.activeStylePackId)?.floor.color
      || "#ffffff",
    material: floorMaterialId,
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
  realisticViewer.setViewMode(currentRealViewMode());
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
  // 兩側各帶實際地材與其代表色（bella-test1 作法）；viewer 據此各建材質，
  // 不再只用 palette 染色。地板不開放手動調色，色一律取材質代表色。
  const primaryFloorId = $("#floor-material").value;
  const secondaryFloorId = $("#material-boundary-secondary")?.value || primaryFloorId;
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
    secondary_floor_id: secondaryFloorId,
    primary_floor_option: resolveSurfaceOption(
      state.sceneData?.surface_catalog,
      "floor",
      primaryFloorId,
    ),
    secondary_floor_option: resolveSurfaceOption(
      state.sceneData?.surface_catalog,
      "floor",
      secondaryFloorId,
    ),
    primary_floor_color_hex: surfaceOptionColor("floor", primaryFloorId) || null,
    secondary_floor_color_hex: surfaceOptionColor("floor", secondaryFloorId) || null,
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
    realisticViewer.setViewMode(currentRealViewMode());
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

// 第 7 步同風格色卡選擇（proposal-palette-grid，bella-test1 fd0cee11 移植）。
// 只列全屋主風格的三張色卡；選定的色卡與鎖定視角一起交給第 8 步遠端生圖。
function syncProposalReviewStages() {
  const paletteStage = $("#proposal-stage-palette");
  const viewStage = $("#proposal-stage-view");
  const paletteState = paletteStage?.querySelector(".rp-proposal-stage-state");
  const viewState = viewStage?.querySelector(".rp-proposal-stage-state");
  const hasPalette = Boolean(state.proposalReview.confirmedStyleCardId);
  const hasLockedView = Boolean(state.proposalReview.masterView);

  paletteStage?.classList.toggle("is-active", !hasPalette);
  paletteStage?.classList.toggle("is-complete", hasPalette);
  viewStage?.classList.toggle("is-active", hasPalette && !hasLockedView);
  viewStage?.classList.toggle("is-complete", hasLockedView);
  viewStage?.classList.toggle("is-confirmed", Boolean(element.proposalContentConfirmed?.checked));
  if (paletteState) paletteState.textContent = hasPalette ? "已選擇" : "待選擇";
  if (viewState) viewState.textContent = hasLockedView ? "已鎖定" : "尚未鎖定";
}

function renderProposalPaletteSelection() {
  if (!element.proposalPaletteGrid) return;
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId)
    || STYLE_PACKS[0];
  const options = STYLE_PACKS.filter((item) => item.styleId === activePack.styleId);
  const selectedId = state.proposalReview.confirmedStyleCardId;
  element.proposalPaletteGrid.innerHTML = options.map((pack) => `
    <button type="button" data-proposal-style-card="${escapeHtml(pack.id)}"
      class="${pack.id === selectedId ? "is-active" : ""}"
      role="radio" aria-checked="${pack.id === selectedId}"
      aria-pressed="${pack.id === selectedId}">
      <span class="rp-proposal-palette-radio" aria-hidden="true"></span>
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}"
        alt="${escapeHtml(`${pack.styleLabel} ${pack.name}色卡預覽`)}" loading="lazy">
      <span class="rp-proposal-palette-copy">
        <span class="rp-style-swatches">${pack.palette
          .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
          .join("")}</span>
        <strong>${escapeHtml(pack.name)}</strong>
        <small>${escapeHtml(`${pack.styleLabel} · ${pack.furnitureRules.signature.slice(0, 2).join("、")}`)}</small>
      </span>
    </button>
  `).join("");
  element.proposalPaletteStatus.textContent = selectedId
    ? `已選「${STYLE_PACKS.find((item) => item.id === selectedId)?.name || "色卡"}」；第 8 步將以這張色卡送往遠端。`
    : "請選擇一張色卡後，再鎖定生圖視角。";
  syncProposalReviewStages();
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
    ["色卡", selectedPalette
      ? `${selectedPalette.styleLabel}／${selectedPalette.name}`
      : (pack ? `${pack.styleLabel}／尚未選擇色卡` : "尚未選擇")],
    ["家具", `${furniture.filter((item) => !item.placement_failed).length} 件已配置`],
    ["結構", `牆 ${state.structures.walls.length}、門 ${state.structures.doors.length}、窗 ${state.structures.windows.length}`],
    ["表面", state.surfaceState.wall?.styleLocked && state.surfaceState.floor?.styleLocked ? "牆與地板已鎖定" : "使用目前風格方案"],
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
  // 自動保存重繪同一頁時，保留使用者已勾的內容確認。
  element.proposalContentConfirmed.checked = element.proposalContentConfirmed.checked || Boolean(saved);
  element.masterViewStatus.textContent = saved
    ? "已載入上次鎖定視角；調整後請重新鎖定。"
    : "尚未鎖定比較視角。";
  syncProposalReviewStages();
  if (saved) renderProposalRoomViewPanel();
}

function lockMasterRenderView() {
  if (!element.proposalContentConfirmed.checked) {
    element.masterViewStatus.textContent = "請先確認家具、結構、材質、色卡與需求。";
    return;
  }
  if (activeScheme()?.stale || !activeScheme()?.sceneData) {
    element.masterViewStatus.textContent =
      `方案 ${activeSchemeId()} 尚未完成最新的 2D／3D 重算，不能鎖定。`;
    return;
  }
  if (state.firstMeeting?.confirmed !== true) {
    const visualProgress = visualQuestionnaireProgress({
      questions: state.visualQuestions,
      answers: state.visualAnswers,
      skippedSpaceTypes: state.skippedVisualSpaceTypes,
    });
    if (!visualProgress.ready) {
      element.requirementsError.textContent =
        `舊版逐房問卷尚有 ${visualProgress.total - visualProgress.completed} 題未處理。`;
      showQuestionnaireStage("rooms");
      return;
    }
    if (!finishesGate(state.questionnaireFinishes).ready) {
      element.requirementsError.textContent = "舊版專案尚未確認風格與材質。";
      showQuestionnaireStage("finishes");
      return;
    }
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
  renderSchemeControls();
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
  element.masterViewStatus.textContent = "完整方案已鎖定；請繼續逐房選擇渲染視角。";
  syncProposalReviewStages();
  scheduleSave("proposal_review");
  state.selectedProposalRoomId = state.rooms[0]?.id || null;
  state.selectedProposalRoomCandidateIndex = 0;
  renderProposalRoomViewPanel();
  if (state.selectedProposalRoomId) selectProposalRoomView(state.selectedProposalRoomId);
}

function renderPaletteOptions() {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const options = STYLE_PACKS.filter((item) => item.styleId === activePack?.styleId);
  element.paletteRenderOptions.innerHTML = options.map((pack) => `
    <label class="rp-render-palette-option">
      <input type="checkbox" value="${escapeHtml(pack.id)}" data-render-style-card
        ${pack.id === state.activeStylePackId ? "checked" : ""} />
      <span class="rp-render-palette-copy">
        <strong>${escapeHtml(pack.name)}</strong>
        <span class="rp-render-palette-swatches" aria-hidden="true">${pack.palette
          .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
          .join("")}</span>
        <small>${pack.palette.map(escapeHtml).join(" · ")}</small>
      </span>
    </label>
  `).join("");
}

function roomCameraSuggestion(room) {
  return roomCameraSuggestionCm(room, state.sceneData?.floorplan);
}

function roomDisplayLabel(room) {
  const base = String(room?.label || "未命名空間");
  const matches = state.rooms.filter(
    (item) => String(item.label || "未命名空間") === base,
  );
  if (matches.length <= 1) return base;
  const index = matches.findIndex((item) => String(item.id) === String(room?.id));
  const dimensions = roomDimensions(room);
  const size = dimensions.widthCm > 0 && dimensions.depthCm > 0
    ? `，${Math.round(dimensions.widthCm)} × ${Math.round(dimensions.depthCm)} 公分`
    : "";
  return `${base} ${Math.max(0, index) + 1}${size}`;
}

function proposalRoomCameraCandidates(room) {
  const base = roomCameraSuggestion(room);
  const [x, y, z] = base.position_cm;
  const [targetX, targetY, targetZ] = base.target_cm;
  // 外接框比例推的鏡頭在窄房間（走道、陽台）會貼牆或出牆，三個候選一起
  // 死在 validateRoomCamera，第 7 步就過不去；夾回房內合法區再交給使用者微調。
  const clamp = (camera) => clampRoomCamera(camera, room, state.sceneData?.floorplan);
  return [
    { label: "入口視角", note: "從主要進入方向觀看", camera: clamp(base) },
    {
      label: "對角視角",
      note: "完整呈現空間深度",
      camera: clamp({ ...base, position_cm: [targetX - (x - targetX), y, targetZ - (z - targetZ)] }),
    },
    {
      label: "活動視角",
      note: "聚焦主要使用區域",
      camera: clamp({ ...base, position_cm: [targetX + (z - targetZ), y, targetZ - (x - targetX)] }),
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
  const slot = $("#proposal-room-views-slot");
  if (!slot) return null;
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
  slot.append(panel);
  panel.addEventListener("click", (event) => {
    const roomButton = event.target.closest("[data-proposal-room]");
    if (roomButton) selectProposalRoomView(roomButton.dataset.proposalRoom);
    const candidateButton = event.target.closest("[data-proposal-room-candidate]");
    if (candidateButton) selectProposalRoomCandidate(Number(candidateButton.dataset.proposalRoomCandidate));
  });
  $("#lock-proposal-room-view").addEventListener("click", lockSelectedProposalRoomView);
  $("#confirm-proposal-room-views").addEventListener("click", confirmProposalRoomViews);
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
      <span>${escapeHtml(roomDisplayLabel(item))}</span>
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
  status.textContent = `${roomDisplayLabel(room)}：選一個候選視角後可在左側微調。已鎖定 ${completed} / ${state.rooms.length} 個房間。`;
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
  const camera = proposalViewer.getCameraState();
  const validation = validateRoomCamera(camera, room, state.sceneData?.floorplan);
  if (!validation.valid) {
    const messages = {
      camera_requires_perspective: "請改用室內透視視角後再鎖定。",
      camera_coordinates_invalid: "目前視角資料不完整，請重新套用建議視角。",
      camera_distance_too_short: "鏡頭與觀看目標太近，請稍微拉遠。",
      camera_target_outside_room: "觀看目標不在此房間內，請重新選擇建議視角。",
      camera_position_outside_room: "鏡頭位於房間牆面外，請移回房間內再鎖定。",
      camera_too_close_to_wall: "鏡頭太靠近牆面，請往房間中央移動。",
    };
    $("#proposal-room-view-status").textContent = messages[validation.code] || "目前視角不適合渲染，請重新調整。";
    return;
  }
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera,
    candidate_index: state.selectedProposalRoomCandidateIndex,
    scene_version: state.proposalReview.masterView?.scene_version,
    saved_at: new Date().toISOString(),
  };
  scheduleSave("proposal_review");
  const nextRoom = state.rooms.find((item) => !state.proposalReview.roomViews[item.id]);
  if (nextRoom) selectProposalRoomView(nextRoom.id);
  else renderProposalRoomViewPanel();
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
        <span>${escapeHtml(roomDisplayLabel(room))}</span>
        <small>${saved ? "視角已保存" : "使用建議視角"}</small>
      </button>
    `;
  }).join("");
  syncAiRenderWorkbenchStatus();
}

function syncAiRenderWorkbenchStatus() {
  const room = state.rooms.find((item) => item.id === state.selectedRenderRoomId);
  if (element.aiRenderCurrentRoom) {
    element.aiRenderCurrentRoom.textContent = room ? roomDisplayLabel(room) : "色卡比較";
  }
  if (element.aiRenderRoomProgress) {
    const saved = state.rooms.filter((item) => state.proposalReview.roomViews?.[item.id]).length;
    element.aiRenderRoomProgress.textContent = `${saved} / ${state.rooms.length}`;
  }
  if (element.aiRenderTaskState) {
    const jobs = state.proposalReview.jobs || [];
    const hasActiveJob = jobs.some((job) => ["queued", "running"].includes(String(job.status || "queued")));
    const hasCompletedJob = jobs.some((job) => String(job.status || "") === "completed");
    element.aiRenderTaskState.textContent = hasActiveJob
      ? "任務進行中"
      : hasCompletedJob
        ? "已有成果"
        : "任務就緒";
  }
}

function setAiRenderWorkbenchStage(stageId, focus = false) {
  const activeId = ["palette", "rooms", "results"].includes(stageId) ? stageId : "palette";
  $$('[data-ai-render-tab]').forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.aiRenderTab === activeId));
  });
  $$('[data-ai-render-stage]').forEach((stage) => {
    const active = stage.dataset.aiRenderStage === activeId;
    stage.classList.toggle("is-active", active);
    if (active && focus) {
      stage.scrollIntoView({ behavior: "smooth", block: "start" });
      stage.focus({ preventScroll: true });
    }
  });
}

function selectRenderRoom(roomId) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  state.selectedRenderRoomId = room.id;
  const saved = state.proposalReview.roomViews[room.id]?.camera;
  aiRenderViewer.lockRenderCamera(false);
  aiRenderViewer.setCameraState(saved || roomCameraSuggestion(room));
  element.aiRenderViewTitle.textContent = `${roomDisplayLabel(room)} · 渲染視角`;
  element.aiRenderStatus.textContent = saved
    ? "已載入保存視角；可以小幅調整後重新保存。"
    : "已套用房間建議視角；請確認主要家具與布局清楚可見。";
  renderRoomViewList();
  syncAiRenderWorkbenchStatus();
}

function saveSelectedRoomView() {
  const room = state.rooms.find((item) => item.id === state.selectedRenderRoomId);
  if (!room) return;
  const camera = aiRenderViewer.getCameraState();
  const validation = validateRoomCamera(camera, room, state.sceneData?.floorplan);
  if (!validation.valid) {
    element.aiRenderStatus.textContent = "目前鏡頭不在房間的可用觀看區域，請重新套用建議視角或移回房間內。";
    return;
  }
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera,
    scene_version: state.proposalReview.masterView?.scene_version,
    saved_at: new Date().toISOString(),
    // 內建生圖供應者需要逐房參考截圖（room_final 模式逐房出圖的底圖）；
    // 缺這張時後端會退用主視角參考圖。
    reference_png_data_url: aiRenderViewer.capturePng(),
  };
  element.aiRenderStatus.textContent = `${room.label || "此房間"}視角已保存。`;
  renderRoomViewList();
  scheduleSave("ai_render");
  const nextRoom = state.rooms.find((item) => !state.proposalReview.roomViews[item.id]);
  if (nextRoom) selectRenderRoom(nextRoom.id);
}

async function downloadViewerGlb(viewer, prefix) {
  try {
    setStatus("正在匯出 GLB……");
    const buffer = await viewer.exportGlb();
    const blob = new Blob([buffer], { type: "model/gltf-binary" });
    const url = URL.createObjectURL(blob);
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const link = document.createElement("a");
    link.href = url;
    link.download = `${prefix}-${stamp}.glb`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // 不 revoke：大場景寫盤可能超過任何固定秒數，提前 revoke 會讓下載斷在
    // .tmp（實測 254MB 場景卡死）。Blob 記憶體本來就存在，頁面卸載時自動回收。
    setStatus("已匯出目前 3D 場景 GLB。");
  } catch (error) {
    setStatus(errorMessage(error), "error");
  }
}

function downloadViewerPng(viewer, prefix) {
  // 2026-07 盤點第 9 項修復（其一）：鎖定視角後，使用者第一次拿得到圖。
  try {
    const dataUrl = viewer.capturePng();
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = `${prefix}-${stamp}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setStatus("已下載目前視角 PNG。");
  } catch (error) {
    setStatus(errorMessage(error), "error");
  }
}

// 第 7、8 步的 #*-status 是交給 createSceneViewer 的檢視器狀態列，檢視器每次載入場景或
// 換視角都會覆寫它——把遠端渲染的失敗寫進去，訊息會在下一則檢視器訊息時消失，使用者
// 看到的就是「按了像沒事發生」。這裡給渲染動作一個檢視器不會碰的錯誤欄位。
function renderStepErrorSlot() {
  return state.workflow?.currentStep === "proposal_review"
    ? element.proposalReviewError
    : element.aiRenderError;
}

function reportRenderActionError(error) {
  const message = errorMessage(error);
  const code = typeof error?.detail === "object" ? error.detail?.code || "" : "";
  const detail = [error?.status ? `HTTP ${error.status}` : "", code].filter(Boolean).join(" · ");
  const text = message;
  const slot = renderStepErrorSlot();
  if (slot) slot.textContent = text;
  if (element.aiRenderTechnicalDetails && element.aiRenderTechnicalError) {
    element.aiRenderTechnicalDetails.hidden = !detail;
    element.aiRenderTechnicalError.textContent = detail;
  }
  if (detail) console.error("Render request failed", detail, error);
  setStatus(text, "error");
  return text;
}

function clearRenderActionError() {
  if (element.aiRenderError) element.aiRenderError.textContent = "";
  if (element.proposalReviewError) element.proposalReviewError.textContent = "";
  if (element.aiRenderTechnicalDetails) element.aiRenderTechnicalDetails.hidden = true;
  if (element.aiRenderTechnicalError) element.aiRenderTechnicalError.textContent = "";
}

async function saveViewerPngToProject(viewer) {
  // 2026-07 盤點第 9 項修復（其二）：capturePng 與後端 browser_capture 入庫
  // 端點（tests/test_project_store_hardening.py 已覆蓋）早已各自完工，
  // 缺的只是這條接線。POST 帶 expected_revision 樂觀鎖，衝突回 409 明話。
  const dataUrl = viewer.capturePng();
  const blob = await (await fetch(dataUrl)).blob();
  const send = () => {
    const form = new FormData();
    form.append("file", blob, "roompilot-view.png");
    form.append("expected_revision", String(Number(state.project?.revision ?? 0)));
    form.append(
      "style_card_id",
      String(state.proposalReview?.confirmedStyleCardId || state.activeStylePackId || "unassigned"),
    );
    return api(`/api/projects/${state.projectId}/renders`, { method: "POST", body: form });
  };
  let result;
  try {
    result = await send();
  } catch (error) {
    // 409 幾乎都是 expected_revision 落後：背景的工作流保存剛寫入，state.project 還是舊版。
    // 這不是使用者能自己解的衝突，重新取一次版本再送一次。
    if (error?.status !== 409) throw error;
    const latest = await api(`/api/projects/${state.projectId}`);
    if (latest?.project) state.project = latest.project;
    result = await send();
  }
  if (result?.project) state.project = result.project;
  await refreshSavedRenders();
  setStatus("截圖已保存到專案成果清單。");
  return result;
}

async function refreshSavedRenders() {
  if (!element.savedRendersList || !state.projectId) return;
  try {
    const payload = await api(`/api/projects/${state.projectId}/renders`);
    const renders = payload.renders || [];
    if (element.savedRendersCount) {
      element.savedRendersCount.textContent = renders.length ? `${renders.length} 張` : "尚無";
    }
    // download_url 需要身分，而 <img src> 與 <a download> 由瀏覽器直接發請求、
    // 不經 fetch 攔截器、不帶 token，直接塞網址會整排 401 破圖。先逐筆取成
    // 帶身分的 blob URL；PNG 端點有 immutable Cache-Control，重複整理清單
    // 走瀏覽器快取不會重下載。單筆失敗只影響那一張，不殺整排清單。
    const entries = await Promise.all(renders.map(async (record) => {
      try {
        const objectUrl = record.download_url
          ? await authorizedObjectUrl(record.download_url, {
              cacheKey: `render:${record.render_id || record.download_url}`,
            })
          : "";
        return { record, objectUrl };
      } catch {
        return { record, objectUrl: "" };
      }
    }));
    element.savedRendersList.innerHTML = entries.map(({ record, objectUrl }) => (objectUrl ? `
      <a class="rp-render-result" href="${escapeHtml(objectUrl)}"
        download="${escapeHtml(`${record.render_id || "render"}.png`)}">
        <img src="${escapeHtml(objectUrl)}" alt="已保存的截圖成果" loading="lazy" />
        <span>${escapeHtml(record.created_at || record.render_id || "截圖")}</span>
      </a>
    ` : `
      <span class="rp-render-result">
        <span>${escapeHtml(record.created_at || record.render_id || "截圖")}（載入失敗，重新整理清單再試）</span>
      </span>
    `)).join("") || '<p class="rp-control-hint">尚未保存任何截圖。</p>';
  } catch {
    // 清單載入失敗不得阻擋渲染流程；下次進入第 8 步會再試。
  }
}

const RENDER_JOB_STATUS_LABELS = {
  completed: "已完成",
  failed: "失敗",
  queued: "排隊中",
  running: "生成中",
};

function renderRemoteJobs() {
  element.remoteRenderJobs.innerHTML = state.proposalReview.jobs.map((job) => {
    const status = String(job.status || "queued");
    const failed = status === "failed";
    // 失敗的房間留成可單獨重試的卡片：舊版整批中止，使用者只看得到一片空白。
    return `
      <article class="${failed ? "is-failed" : ""}">
        <strong>${escapeHtml(job.label || job.job_id || "渲染任務")}</strong>
        <span>${escapeHtml(RENDER_JOB_STATUS_LABELS[status] || status)}</span>
        ${failed ? `<small>${escapeHtml(job.message_zh || "這個房間的生圖失敗。")}</small>
          <button type="button" data-retry-room-render="${escapeHtml(job.room_id || "")}">
            重試這個房間</button>` : ""}
      </article>
    `;
  }).join("");
  syncAiRenderWorkbenchStatus();
}

async function retryRoomRender(roomId) {
  const roomView = state.proposalReview.roomViews?.[roomId];
  if (!roomView) {
    reportRenderActionError(new Error("找不到這個房間已保存的視角，請回第 7 步重新保存。"));
    return;
  }
  clearRenderActionError();
  element.aiRenderStatus.textContent = `正在重試「${roomView.room_label || roomId}」…`;
  try {
    const result = await api(`/api/projects/${state.projectId}/render-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload(
        "room_final",
        [state.proposalReview.confirmedStyleCardId],
        [roomView],
      )),
    });
    const retried = (result.jobs || [result.job]).filter(Boolean);
    // 用新結果換掉這個房間的舊任務，避免同一間房留下兩張卡。
    state.proposalReview.jobs = [
      ...state.proposalReview.jobs.filter(
        (job) => String(job.room_id || "") !== String(roomId),
      ),
      ...retried,
    ];
    renderRemoteJobs();
    refreshSavedRenders();
    scheduleSave("ai_render");
    element.aiRenderStatus.textContent = retried.some((job) => job.status === "completed")
      ? `「${roomView.room_label || roomId}」已重新生成。`
      : `「${roomView.room_label || roomId}」重試後仍未成功。`;
  } catch (error) {
    reportRenderActionError(error);
  }
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
  setRoomRenderSectionLocked(false);
  state.selectedRenderRoomId = state.selectedProposalRoomId || state.rooms[0]?.id || null;
  if (state.selectedRenderRoomId) selectRenderRoom(state.selectedRenderRoomId);
  setAiRenderWorkbenchStage("rooms", true);
  scheduleSave("ai_render");
  element.aiRenderStatus.textContent = "色卡已確認；將沿用第 7 步鎖定的逐房視角。";
}

// 第 2 段以前用 hidden 藏起來，面板編號就會從「1. 色卡比較」直接跳「3. 截圖成果」。
// 改成一直看得見，未確認色卡時鎖住操作並說明原因。
function setRoomRenderSectionLocked(locked) {
  element.roomRenderSection.hidden = false;
  element.roomRenderSection.classList.toggle("is-locked", locked);
  const hint = $("#room-render-lock-hint");
  if (hint) hint.hidden = !locked;
  ["#save-room-view", "#submit-room-renders"].forEach((selector) => {
    const button = $(selector);
    if (button) button.disabled = locked;
  });
}

async function prepareAiRender() {
  if (!state.sceneData || !state.proposalReview.masterView) {
    reportRenderActionError(new Error(
      "尚未鎖定第 7 步的色卡比較視角，無法準備渲染；請先回第 7 步鎖定視角。",
    ));
    return;
  }
  // 控制項不能排在 3D 載入的 await 後面：這個場景的 shader 編譯要好幾秒，
  // 期間色卡區是一整片空白，使用者按下去只會得到「至少選擇一張色卡」。
  renderRenderDetailControls();
  renderPaletteOptions();
  renderRemoteJobs();
  renderPaletteResults();
  refreshSavedRenders();
  setAiRenderWorkbenchStage("palette");
  syncAiRenderWorkbenchStatus();
  setRoomRenderSectionLocked(!state.proposalReview.confirmedStyleCardId);
  await aiRenderViewer.loadScene(state.sceneData);
  aiRenderViewer.setCameraState(state.proposalReview.masterView.camera);
  aiRenderViewer.lockRenderCamera(true);
  element.aiRenderProviderState.textContent = "正在檢查遠端服務…";
  try {
    const status = await api("/api/render-provider/status");
    element.aiRenderProviderState.textContent = status.configured
      ? "已連接生圖服務"
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

function renderRequestPayload(mode, styleCardIds, roomViews = []) {
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
    locks: {
      furniture: true,
      structure: true,
      surface_regions: true,
      style_card_id: mode === "room_final"
        ? state.proposalReview.confirmedStyleCardId
        : state.activeStylePackId,
    },
    requirements: {
      basic: state.basicAnswers,
      visual_preferences: state.visualAnswers,
      finishes: state.questionnaireFinishes,
      room_requirements: roomRequirementsPayload.roomRequirements,
      ready_for_rag: roomRequirementsPayload.readyForRag,
      // 已解析成中文的需求摘要，供生圖 prompt 直接引用（見 REMOTE_RENDER_CONTRACT）。
      digest: renderRequirementsDigest(),
    },
    room_surface_assignments: roomSurfaceAssignments(),
    master_view: state.proposalReview.masterView,
    room_views: roomViews,
    reference_png_data_url: aiRenderViewer.capturePng(),
  };
}

async function requestPaletteRenders() {
  const styleCardIds = $$("[data-render-style-card]:checked").map((input) => input.value);
  clearRenderActionError();
  if (!styleCardIds.length) {
    reportRenderActionError(new Error("至少選擇一張色卡。"));
    return;
  }
  const button = $("#request-palette-renders");
  button.disabled = true;
  button.textContent = "正在建立色卡比較…";
  try {
    element.aiRenderStatus.textContent =
      `正在生成 ${styleCardIds.length} 張色卡比較圖…每張約 10~30 秒，請勿離開此頁。`;
    const result = await api(`/api/projects/${state.projectId}/render-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload("palette_comparison", styleCardIds)),
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
    const completed = jobs.filter((job) => job.status === "completed").length;
    element.aiRenderStatus.textContent = completed
      ? `已完成 ${completed} 張色卡比較圖，請選擇一張確認。`
      : "任務已送出，等待遠端渲染回圖。";
    refreshSavedRenders();
  } catch (error) {
    reportRenderActionError(error);
    element.aiRenderStatus.textContent = "生成失敗；設定已保留，可直接重試。";
    button.textContent = "重試建立色卡比較";
  } finally {
    button.disabled = false;
    if (button.textContent === "正在建立色卡比較…") {
      button.textContent = "建立色卡比較任務";
    }
  }
}

async function submitRoomRenders() {
  const roomViews = Object.values(state.proposalReview.roomViews);
  clearRenderActionError();
  if (!roomViews.length) {
    reportRenderActionError(new Error("請至少保存一個房間視角。"));
    return;
  }
  const button = $("#submit-room-renders");
  button.disabled = true;
  button.textContent = "正在送出房間渲染…";
  try {
    const result = await api(`/api/projects/${state.projectId}/render-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload(
        "room_final",
        [state.proposalReview.confirmedStyleCardId],
        roomViews,
      )),
    });
    const roomJobs = (result.jobs || [result.job]).filter(Boolean);
    state.proposalReview.jobs.push(...roomJobs);
    state.workflow.complete("ai_render", { confirmed: true });
    renderRemoteJobs();
    scheduleSave("ai_render");
    const completedRooms = roomJobs.filter((job) => job.status === "completed").length;
    const failedRooms = roomJobs.filter((job) => job.status === "failed").length;
    element.aiRenderStatus.textContent = completedRooms
      ? `已完成 ${completedRooms} 張房間渲染圖${
        failedRooms ? `，${failedRooms} 間失敗可單獨重試` : ""}，成果已入專案清單。`
      : `已送出 ${roomViews.length} 個房間渲染任務。`;
    if (failedRooms) {
      reportRenderActionError(new Error(
        `有 ${failedRooms} 個房間生圖失敗，其餘已完成；可在任務清單單獨重試。`,
      ));
    }
    refreshSavedRenders();
  } catch (error) {
    reportRenderActionError(error);
    element.aiRenderStatus.textContent = "房間渲染送出失敗；已保存的視角仍保留，可直接重試。";
    button.textContent = "重試送出房間渲染";
  } finally {
    button.disabled = false;
    if (button.textContent === "正在送出房間渲染…") {
      button.textContent = "送出已保存的房間渲染";
    }
  }
}

function bindEvents() {
  $("#exit-project").addEventListener("click", confirmProjectExit);
  element.projectForm.addEventListener("submit", createProject);
  element.file.addEventListener("change", () => selectFloorplanFile(element.file.files[0]));
  element.floorplanConfirmation.addEventListener("change", updateUploadConfirmationState);
  element.confirmUpload.addEventListener("click", confirmUpload);
  element.scaleOverlay.addEventListener("pointerdown", calibrationPointerDown);
  element.scaleOverlay.addEventListener("pointermove", calibrationPointerMove);
  element.scaleInput.addEventListener("input", () => updateCalibrationAction());
  window.addEventListener("pointerup", async () => {
    if (structureCreateDrag) finishBeamCreateDrag();
    const completedRoomDrag = draggedRoomPointIndex != null;
    state.calibrationDragIndex = null;
    draggedRoomPointIndex = null;
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
  $("#reset-floorplan-calibration").addEventListener("click", () => {
    state.calibrationPoints = [];
    renderCalibration();
  });
  element.applyCalibration.addEventListener("click", applyCalibration);
  element.roomList.addEventListener("click", (event) => {
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
  element.recognitionReviewList?.addEventListener("click", (event) => {
    const jump = event.target.closest("[data-review-room-id]");
    if (!jump) return;
    selectRoom(jump.dataset.reviewRoomId);
    element.currentRoomReview?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  element.skipCurrentRoom.addEventListener("click", skipCurrentRoomReview);
  element.confirmCurrentRoom.addEventListener("click", confirmCurrentRoomAndAdvance);
  $("#delete-current-room").addEventListener("click", () => deleteRoom());
  $$("[data-room-geometry-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomGeometryMode(button.dataset.roomGeometryMode));
  });
  $("#apply-room-merge").addEventListener("click", mergeSelectedRooms);
  $("#cancel-room-geometry").addEventListener("click", () => setRoomGeometryMode(null));
  $$("[data-room-node-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomNodeMode(button.dataset.roomNodeMode));
  });
  $("#apply-node-merge").addEventListener("click", mergeSelectedRoomNodes);
  $("#cancel-node-edit").addEventListener("click", () => setRoomNodeMode(null));
  $("#add-missed-room").addEventListener("click", addMissedRoom);
  $("#confirm-all-rooms").addEventListener("click", confirmAllRooms);
  ["#structure-confirmed", "#estimated-size-ack"].forEach((selector) => {
    $(selector).addEventListener("change", updateSpaceCompletionState);
  });
  SHOW_ALL_ROOMS_BUTTONS.map((selector) => $(selector)).filter(Boolean).forEach((button) => {
    button.addEventListener("click", () => {
      if (state.rooms.length <= 1) {
        setStatus("目前只有一個空間，沒有其他框選可顯示。");
        updateShowAllRoomsButton();
        return;
      }
      state.showAllRooms = true;
      renderSpaceOverlay();
      setStatus("已顯示全部空間框選。");
    });
  });
  $("#save-room").addEventListener("click", saveRoom);
  element.spaceOverlay.addEventListener("pointerdown", spacePointerDown);
  element.spaceOverlay.addEventListener("pointermove", spacePointerMove);
  $("#apply-structure-size").addEventListener("click", applySelectedStructureSize);
  $("#lock-selected-door-opening").addEventListener("click", lockSelectedDoorOpening);
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
  $("#selected-window-type").addEventListener("change", applySelectedWindowType);
  element.openingWidthSlider.addEventListener("input", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, false);
  });
  element.openingWidthSlider.addEventListener("change", () => {
    setSelectedOpeningWidthCm(element.openingWidthSlider.value, true);
  });
  $$("[data-opening-width-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextWidth = Number(element.openingWidthSlider.value)
        + Number(button.dataset.openingWidthStep);
      setSelectedOpeningWidthCm(nextWidth, true);
    });
  });
  $("#rotate-selected-structure-left").addEventListener("click", () => rotateSelectedStructure(-15));
  $("#rotate-selected-structure-right").addEventListener("click", () => rotateSelectedStructure(15));
  $("#rotate-selected-door-180").addEventListener("click", rotateSelectedDoor180);
  $("#delete-selected-structure").addEventListener("click", deleteSelectedStructure);
  $("#flip-selected-door").addEventListener("click", () => {
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
  $("#confirm-all-visible-structures").addEventListener("click", () => {
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
  $("#cancel-structure-interaction").addEventListener("click", cancelStructureInteraction);
  element.spaceStage.addEventListener("dragover", (event) => event.preventDefault());
  element.spaceStage.addEventListener("drop", (event) => {
    event.preventDefault();
    const tool = event.dataTransfer.getData("text/roompilot-structure");
    const point = imagePoint(event, element.spaceImage);
    if (tool && point) addDroppedStructure(tool, point);
  });
  $("#confirm-space").addEventListener("click", confirmSpace);
  $("#back-to-space-editor").addEventListener("click", () => {
    setSpaceReviewMode("editing");
    setStatus("可繼續調整房間與結構；完成後再確認尺寸標註平面圖。");
  });
  $("#recalibrate-space").addEventListener("click", () => {
    setSpaceReviewMode("editing");
    if (goTo("calibration")) {
      setStatus("請重新選取兩點並輸入實際尺寸；套用後會重新計算空間面積。");
    }
  });
  $("#confirm-dimensioned-plan").addEventListener("click", confirmDimensionedPlan);
  $("#confirm-basic-questionnaire").addEventListener("click", confirmBasicQuestionnaire);
  // 2026-08-05 Ben 指示常駐：逐題點過去太慢，這顆是日常測試的主要入口。
  // 原本擋在 ?demo=1 後面（0169abda），實務上等於每次都要手動改網址。
  // 覆寫風險由下面的 confirm 把關，不再用網址參數當開關。
  element.randomizeRequirements.hidden = false;
  element.randomizeRequirements.addEventListener("click", () => {
    if (!window.confirm("測試範例會覆寫目前尚未確認的面談答案，確定要繼續嗎？")) return;
    randomizeRequirementsForTesting();
  });
  element.firstMeetingProgress.addEventListener("click", (event) => {
    const button = event.target.closest("[data-first-meeting-step]");
    if (!button || button.disabled) return;
    state.firstMeetingStep = button.dataset.firstMeetingStep;
    renderFirstMeeting();
    scheduleSave("requirements");
  });
  element.firstMeetingBack.addEventListener("click", () => {
    const previous = FIRST_MEETING_STEPS[firstMeetingStepIndex() - 1];
    if (!previous) return;
    state.firstMeetingStep = previous.id;
    renderFirstMeeting();
    scheduleSave("requirements");
  });
  element.firstMeetingNext.addEventListener("click", async () => {
    const currentIndex = firstMeetingStepIndex();
    const current = FIRST_MEETING_STEPS[currentIndex];
    if (current.id === "summary") {
      await confirmRequirements();
      return;
    }
    const status = firstMeetingStepStatus(state.firstMeeting, current.id, state.rooms);
    if (!status.ready) {
      element.firstMeetingError.textContent = status.message;
      return;
    }
    state.firstMeetingStep = FIRST_MEETING_STEPS[currentIndex + 1].id;
    renderFirstMeeting();
    element.firstMeetingPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    scheduleSave("requirements");
  });
  element.firstMeetingPanel.addEventListener("click", (event) => {
    const goalButton = event.target.closest("[data-first-meeting-goal]");
    if (goalButton) {
      const goalId = goalButton.dataset.firstMeetingGoal;
      const selected = state.firstMeeting.goalIds.includes(goalId);
      if (!selected && state.firstMeeting.goalIds.length >= 3) {
        element.firstMeetingError.textContent = "已選三項；請先取消一項再更換。";
        return;
      }
      state.firstMeeting.goalIds = selected
        ? state.firstMeeting.goalIds.filter((id) => id !== goalId)
        : [...state.firstMeeting.goalIds, goalId];
      markFirstMeetingChanged({ rerender: true });
      return;
    }
    const roomButton = event.target.closest("[data-first-meeting-room]");
    if (roomButton) {
      const roomId = roomButton.dataset.firstMeetingRoom;
      const selected = state.firstMeeting.priorityRoomIds.includes(roomId);
      if (!selected && state.firstMeeting.priorityRoomIds.length >= 3) {
        element.firstMeetingError.textContent = "最多選三個優先空間。";
        return;
      }
      state.firstMeeting.priorityRoomIds = selected
        ? state.firstMeeting.priorityRoomIds.filter((id) => id !== roomId)
        : [...state.firstMeeting.priorityRoomIds, roomId];
      if (!selected) state.firstMeeting.roomNotes[roomId] ||= "";
      markFirstMeetingChanged({ rerender: true });
      return;
    }
    const likeButton = event.target.closest("[data-first-meeting-style-like]");
    if (likeButton) {
      const packId = likeButton.dataset.firstMeetingStyleLike;
      const liked = state.firstMeeting.likedStylePackIds.includes(packId);
      if (!liked && state.firstMeeting.likedStylePackIds.length >= 2) {
        element.firstMeetingError.textContent = "已選兩張喜歡的圖；請先取消一張再更換。";
        return;
      }
      state.firstMeeting.likedStylePackIds = liked
        ? state.firstMeeting.likedStylePackIds.filter((id) => id !== packId)
        : [...state.firstMeeting.likedStylePackIds, packId];
      if (!liked && state.firstMeeting.dislikedStylePackId === packId) {
        state.firstMeeting.dislikedStylePackId = "";
      }
      markFirstMeetingChanged({ rerender: true });
      return;
    }
    const dislikeButton = event.target.closest("[data-first-meeting-style-dislike]");
    if (dislikeButton) {
      const packId = dislikeButton.dataset.firstMeetingStyleDislike;
      state.firstMeeting.dislikedStylePackId = state.firstMeeting.dislikedStylePackId === packId
        ? ""
        : packId;
      state.firstMeeting.likedStylePackIds = state.firstMeeting.likedStylePackIds
        .filter((id) => id !== packId);
      markFirstMeetingChanged({ rerender: true });
    }
  });
  element.firstMeetingPanel.addEventListener("change", (event) => {
    const resident = event.target.closest("[data-first-meeting-resident]");
    if (resident) {
      state.firstMeeting.residents[resident.dataset.firstMeetingResident] = Number(resident.value);
    } else if (event.target.matches("[data-first-meeting-budget]")) {
      state.firstMeeting.budgetRange = event.target.value;
    } else if (event.target.matches("[data-first-meeting-timeline]")) {
      state.firstMeeting.targetTimeline = event.target.value;
    } else {
      return;
    }
    markFirstMeetingChanged();
  });
  element.firstMeetingPanel.addEventListener("input", (event) => {
    if (event.target.matches("[data-first-meeting-special-needs]")) {
      state.firstMeeting.residents.specialNeeds = event.target.value;
    } else if (event.target.matches("[data-first-meeting-constraints]")) {
      state.firstMeeting.constraints = event.target.value;
    } else if (event.target.matches("[data-first-meeting-style-note]")) {
      state.firstMeeting.styleNote = event.target.value;
    } else if (event.target.matches("[data-first-meeting-room-note]")) {
      state.firstMeeting.roomNotes[event.target.dataset.firstMeetingRoomNote] = event.target.value;
    } else {
      return;
    }
    markFirstMeetingChanged();
  });
  element.questionnaireStageNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-stage]");
    if (button && !button.disabled) showQuestionnaireStage(button.dataset.questionnaireStage);
  });
  element.roomQuestionnaireSectionNav?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-room-questionnaire-section]");
    if (!button) return;
    element.requirementsError.textContent = "";
    showRoomQuestionnaireSection(button.dataset.roomQuestionnaireSection);
  });
  element.visualSpaceNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-visual-room]");
    if (!button) return;
    state.roomRequirementModel.activeRoomId = button.dataset.visualRoom;
    state.selectedQuestionnaireWallId = null;
    renderVisualQuestionnaire();
  });
  $("#back-to-room-questionnaire")?.addEventListener("click", () => showQuestionnaireStage("rooms"));
  $("#questionnaire-summary-back")?.addEventListener("click", () => showQuestionnaireStage("profile"));
  element.wholeHouseStyleTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-whole-house-style]");
    if (!button) return;
    const firstPack = STYLE_PACKS.find(
      (pack) => pack.styleId === button.dataset.wholeHouseStyle,
    );
    if (firstPack) selectWholeHouseStylePack(firstPack.id);
  });
  element.wholeHouseStyleGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-whole-house-style-pack]");
    if (!button) return;
    event.preventDefault();
    selectWholeHouseStylePack(button.dataset.wholeHouseStylePack);
  });
  RENDER_DETAIL_FIELDS.forEach(({ element: name }) => {
    element[name]?.addEventListener("change", saveRenderDetailInputs);
  });
  element.questionnaireFurniturePreferenceTags.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-furniture-tag]");
    if (button) toggleQuestionnaireFurniturePreferenceTag(button.dataset.questionnaireFurnitureTag);
  });
  element.questionnaireStyleTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style]");
    if (!button) return;
    state.activeStyleId = button.dataset.questionnaireStyle;
    const firstPack = STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId);
    if (firstPack) selectQuestionnaireStylePack(firstPack.id);
  });
  element.questionnaireStyleGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-style-pack]");
    if (button) selectQuestionnaireStylePack(button.dataset.questionnaireStylePack);
  });
  element.questionnaireRoomUsageOptions.addEventListener("change", (event) => {
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
    void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
    invalidateDownstreamFrom(
      "requirements",
      `${room.label}的使用功能已更新，後續配置需要重新產生。`,
    );
    scheduleSave("requirements");
  });
  // 家電生圖題組：select 與兩組 checkbox 走 change，補充文字走 input。
  // 這些答案只影響第 8 步生圖，不動 2D/3D 家具，所以不呼叫
  // invalidateDownstreamFrom，也不清掉 roomFurnitureRecommendations。
  element.questionnaireGenerativeEquipment?.addEventListener("change", (event) => {
    if (!event.target.closest(
      "[data-generative-direction], [data-generative-exclusion], #questionnaire-generative-primary-use",
    )) return;
    updateGenerativeEquipment();
  });
  element.questionnaireGenerationNotes?.addEventListener(
    "input",
    () => updateGenerativeEquipmentNotes(),
  );
  element.questionnaireFurnitureOptions.addEventListener("change", (event) => {
    const variant = event.target.closest("select[data-questionnaire-furniture-variant-type]");
    if (variant) {
      updateQuestionnaireFurnitureVariant(
        variant.dataset.questionnaireFurnitureVariantType,
        variant.value,
      );
      return;
    }
    const input = event.target.closest("[data-questionnaire-furniture-id]");
    if (!input) return;
    updateQuestionnaireFurnitureSelection(
      input.dataset.questionnaireFurnitureId,
      input.checked,
    );
  });
  element.questionnaireFurnitureOptions.addEventListener("click", (event) => {
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
    const catalog = event.target.closest("[data-open-questionnaire-furniture-catalog]");
    if (!catalog) return;
    openQuestionnaireFurnitureCatalog(catalog.dataset.openQuestionnaireFurnitureCatalog);
  });
  // The furniture cards are redrawn after every selection.  Capture these
  // events at the document root so a refreshed card cannot lose its controls.
  document.addEventListener("click", (event) => {
    const quantity = event.target.closest("[data-questionnaire-furniture-quantity]");
    if (!quantity || !element.questionnaireFurnitureOptions.contains(quantity)) return;
    event.preventDefault();
    event.stopPropagation();
    updateQuestionnaireFurnitureQuantity(
      quantity.dataset.questionnaireFurnitureId,
      Number(quantity.dataset.questionnaireFurnitureQuantity),
    );
  }, true);
  document.addEventListener("change", (event) => {
    const variant = event.target.closest("select[data-questionnaire-furniture-variant-type]");
    if (variant && element.questionnaireFurnitureOptions.contains(variant)) {
      event.stopPropagation();
      updateQuestionnaireFurnitureVariant(
        variant.dataset.questionnaireFurnitureVariantType,
        variant.value,
      );
      return;
    }
    const input = event.target.closest('input[data-questionnaire-furniture-id]');
    if (!input || !element.questionnaireFurnitureOptions.contains(input)) return;
    event.stopPropagation();
    updateQuestionnaireFurnitureSelection(
      input.dataset.questionnaireFurnitureId,
      input.checked,
    );
  }, true);
  element.refreshQuestionnaireFurniture.addEventListener(
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
  [
    [element.questionnaireWallPreference, "wallPreference"],
    [element.questionnaireFloorPreference, "floorPreference"],
  ].forEach(([control, key]) => {
    control?.addEventListener("input", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value.trim();
      draft.confirmed = false;
      const requirement = activeRoomRequirement();
      if (requirement?.surfaces) requirement.surfaces[key] = draft[key];
      scheduleSave("requirements");
    });
  });
  [element.questionnaireWallOptions, element.questionnaireFloorOptions].forEach((host) => {
    host.addEventListener("click", (event) => {
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
    [element.questionnaireCeilingMaterial, "ceilingMaterial"],
    [element.questionnaireCeilingStyle, "ceilingStyle"],
    [element.questionnaireLightStyle, "lightStyle"],
    [element.questionnaireCeilingColor, "ceilingColor"],
    [element.questionnaireAirConditioning, "airConditioning"],
  ].forEach(([control, key]) => {
    control.addEventListener("change", () => {
      const draft = activeRoomFinishDraft();
      draft[key] = control.value;
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
  element.questionnaireFinishScope.addEventListener("change", () => {
    element.questionnaireFinishRoomTargets.hidden =
      element.questionnaireFinishScope.value !== "selected";
  });
  element.enableCirculationStyleOverride.addEventListener("click", () => {
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
  $("#apply-air-conditioning-all").addEventListener("click", () => {
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
  element.questionnairePlanOverlay.addEventListener("click", (event) => {
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
  element.questionnaireSummary.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-questionnaire-summary-room]");
    if (toggle) {
      const roomId = toggle.dataset.questionnaireSummaryRoom;
      state.expandedQuestionnaireSummaryRoomId =
        String(state.expandedQuestionnaireSummaryRoomId) === String(roomId) ? null : roomId;
      renderQuestionnaireSummary();
      return;
    }
    const edit = event.target.closest("[data-edit-questionnaire-room]");
    if (!edit) return;
    state.roomQuestionnaireSection = "preferences";
    state.selectedQuestionnaireWallId = null;
    showQuestionnaireStage("rooms");
  });
  $("#confirm-questionnaire-finishes").addEventListener("click", confirmQuestionnaireFinishes);
  element.confirmRequirements.addEventListener("click", confirmRequirements);
  $$("[data-design-scheme]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!switchDesignScheme(button.dataset.designScheme)) return;
      setStatus(`已切換至方案 ${button.dataset.designScheme}；家具座標與 3D 場景彼此獨立。`);
    });
  });
  $("#delete-scheme-b").addEventListener("click", () => {
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
  $("#auto-layout-furniture").addEventListener("click", async () => {
    element.layoutError.textContent = "";
    try {
      setStatus("正在由家具引擎重新配置合法位置…");
      if (activeSchemeId() === "B" && state.designSchemes.schemes.A.furniture.length) {
        const furniture = await relayoutFurnitureForScheme(
          state.designSchemes.schemes.A.furniture,
          "B",
        );
        const kept = deferFailedPlacements(furniture, "B");
        if (furniture.length !== kept.length) {
          setStatus(`方案 B 有 ${furniture.length - kept.length} 件家具放不下，已列入「暫不放入」。`);
        }
        state.furniture2d = kept;
        const schemeB = state.designSchemes.schemes.B;
        schemeB.furniture = JSON.parse(JSON.stringify(kept));
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
  element.furnitureSearch.addEventListener("input", () => renderFurnitureLibrary(element.furnitureSearch.value));
  element.layoutRoomFilter.addEventListener("change", () => {
    state.activeLayoutRoomId = element.layoutRoomFilter.value || "all";
    renderLayoutFurniture();
  });
  $("#add-2d-furniture-mode").addEventListener("click", () => {
    state.selectedFurniture2dId = null;
    renderLayoutFurniture();
    setStatus("現在是新增模式：請從右側選一個 2D 家具圖示，系統會放進目前房間。");
  });
  element.furnitureLibrary.addEventListener("click", (event) => {
    const button = event.target.closest("[data-add-furniture-type]");
    if (button) addFurnitureFromLibrary(button.dataset.addFurnitureType, button.dataset.addFurnitureVariant);
  });
  element.layoutLayer.addEventListener("pointerdown", layoutPointerDown);
  element.layoutLayer.addEventListener("pointermove", layoutPointerMove);
  element.selectedFurnitureWidth.addEventListener("change", updateSelectedFurnitureDimensions);
  element.selectedFurnitureDepth.addEventListener("change", updateSelectedFurnitureDimensions);
  $("#rotate-2d-furniture").addEventListener("click", () => {
    const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
    if (item) item.rotationDeg = (item.rotationDeg + 90) % 360;
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具旋轉已修改，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#delete-2d-furniture").addEventListener("click", () => {
    orphanTabletopDependents([state.selectedFurniture2dId]);
    state.furniture2d = state.furniture2d.filter((item) => item.id !== state.selectedFurniture2dId);
    syncFurnitureInventoryAcrossSchemes();
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具已刪除，3D 家具配置與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#confirm-layout-2d").addEventListener("click", confirmLayout2d);
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
  element.whiteWalkRoom.addEventListener("change", () => {
    state.selectedWalkRoomId = element.whiteWalkRoom.value;
    activateWhiteWalkMode();
  });
  $("#add-white-model-beam").addEventListener("click", () => {
    if (!goTo("space_confirmation")) return;
    showStep("space_confirmation");
    setSpaceReviewMode("editing");
    state.spaceMode = "structure";
    setActiveStructureKind("beam");
    setStatus("已返回第 4 步樑頁；修改結構後，問卷保留並重新計算家具與 3D。");
  });
  element.layoutFurnitureList.addEventListener("click", (event) => {
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
    // 存回型錄上的 id 而不是 dataset 字串，下游的嚴格相等比對才不會靜默失配。
    state.selectedFurniture2dId =
      furniture2dById(button.dataset.selectConfigurationFurniture)?.id
      ?? button.dataset.selectConfigurationFurniture;
    if (fromFurnitureList) void openFurnitureReplacement();
    renderLayoutFurniture();
    renderConfigurationPlan();
    const focused = fromFurnitureList
      ? syncSelected2dFurnitureToScene({ focus: false })
      : syncSelected2dFurnitureToScene({ focus: true });
    if (fromPlan) {
      const item = furniture2dById(state.selectedFurniture2dId);
      setStatus(
        focused && item
          ? `已在 3D 定位家具 ${configurationFurnitureNumber(item)}「${item.label}」。`
          : "已選取家具；目前尚無可定位的 3D 模型。",
      );
    }
  };
  element.configurationPlanLayer.addEventListener("click", selectConfigurationFurniture);
  element.configurationPlanFurnitureList.addEventListener(
    "click",
    selectConfigurationFurniture,
  );
  // 待處理清單每次重繪都會整段換掉 innerHTML。把委派掛在清單節點上，只要清單或它的
  // 祖先被換掉，監聽就跟著消失；問卷家具卡片早先踩過同一個坑（見下方 document 捕獲的
  // 註解），這裡套同一個模式：在 document root 捕獲，再自行判斷事件是否落在清單裡。
  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    // 用選擇器判斷歸屬，不用啟動時抓到的節點：清單節點若被重繪換掉，快取的參照會失效。
    if (!event.target.closest(CONFIGURATION_PENDING_LIST_SELECTOR)) return;
    configurationPendingHandledToken = configurationPendingClickToken;
    clearConfigurationActionError();
    try {
      const prioritizeButton = event.target.closest("[data-prioritize-configuration-room]");
      if (prioritizeButton) {
        void prioritizeConfigurationRoomFurniture(
          prioritizeButton.dataset.prioritizeConfigurationRoom,
        );
        return;
      }
      const replaceButton = event.target.closest("[data-replace-configuration-furniture]");
      if (replaceButton) {
        state.selectedFurniture2dId =
          furniture2dById(replaceButton.dataset.replaceConfigurationFurniture)?.id
          ?? replaceButton.dataset.replaceConfigurationFurniture;
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
      const removeButton = event.target.closest("[data-remove-configuration-furniture]");
      if (removeButton) {
        void removeConfigurationFurniture(
          removeButton.dataset.removeConfigurationFurniture,
        );
        return;
      }
      if (event.target.closest("[data-defer-all-configuration-furniture]")) {
        void deferAllBlockingConfigurationFurniture();
        return;
      }
      selectConfigurationFurniture(event);
    } catch (error) {
      reportConfigurationActionError(errorMessage(error));
    }
  }, true);
  // 捕獲階段的委派解決「監聽跟著節點消失」，但解決不了「按住期間重繪、瀏覽器根本不送
  // click」。按住時凍結清單重繪（writeConfigurationPendingList），放開後補畫；並在事件
  // 派送結束後確認委派真的跑過，沒跑過就把失敗說出來，不再是一片沉默。
  let pressedConfigurationPendingAction = "";
  document.addEventListener("pointerdown", (event) => {
    pressedConfigurationPendingAction = configurationPendingActionKey(event.target);
    configurationPendingPointerDown = Boolean(pressedConfigurationPendingAction);
    if (pressedConfigurationPendingAction) configurationPendingClickToken += 1;
  }, true);
  const releaseConfigurationPendingPointer = (event) => {
    const pressed = pressedConfigurationPendingAction;
    pressedConfigurationPendingAction = "";
    configurationPendingPointerDown = false;
    const token = configurationPendingClickToken;
    const matched = pressed
      && event.type === "pointerup"
      && configurationPendingActionKey(event.target) === pressed;
    setTimeout(() => {
      flushDeferredConfigurationPendingList();
      if (!matched || configurationPendingHandledToken === token) return;
      reportConfigurationActionError(
        "待處理家具的操作沒有送達（畫面在點擊過程中重繪）。請再按一次；若持續發生請回報。",
      );
    }, matched ? 250 : 0);
  };
  document.addEventListener("pointerup", releaseConfigurationPendingPointer, true);
  document.addEventListener("pointercancel", releaseConfigurationPendingPointer, true);
  element.configurationPlanImage.addEventListener("load", renderConfigurationPlan);
  element.configurationPlanToggle.addEventListener("click", () => {
    const collapsed = element.configurationPlanPanel.classList.toggle("is-collapsed");
    element.configurationPlanToggle.textContent = collapsed ? "+" : "−";
    element.configurationPlanToggle.title = collapsed ? "展開 2D 平面" : "收合 2D 平面";
    element.configurationPlanToggle.setAttribute(
      "aria-label",
      collapsed ? "展開 2D 平面" : "收合 2D 平面",
    );
    if (!collapsed) requestAnimationFrame(renderConfigurationPlan);
  });
  $("#replace-2d-furniture").addEventListener("click", openFurnitureReplacement);
  $("#replace-white-model-furniture")?.addEventListener("click", openFurnitureReplacement);
  $("#close-furniture-replacement").addEventListener("click", () => {
    setReplacementDrawerOpen(false);
  });
  element.replacementSearch.addEventListener("change", () => {
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
  element.replacementResults.addEventListener("click", (event) => {
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
  $("#cancel-white-model-beam").addEventListener("click", cancelWhiteModelBeamPlacement);
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
  $("#delete-replacement-furniture").addEventListener("click", async () => {
    await deleteSelectedSceneFurniture();
    if (element.replacementDrawer.open) setReplacementDrawerOpen(false);
  });
  $("#delete-realistic-furniture").addEventListener("click", deleteSelectedSceneFurniture);
  [
    "#specified-furniture-color",
    "#specified-furniture-material",
    "#lock-specified-model",
    "#lock-specified-material",
  ].forEach((selector) => $(selector).addEventListener("change", () => {
    saveSelectedSceneAppearance();
    scheduleSave("white_model_3d");
  }));
  $("#open-furniture-catalog").addEventListener("click", () => setFurnitureCatalogOpen(true));
  $("#close-furniture-catalog").addEventListener("click", () => setFurnitureCatalogOpen(false));
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
  $("#toggle-furniture-numbers")?.addEventListener("click", () => {
    state.showFurnitureNumbers = !state.showFurnitureNumbers;
    syncFurnitureNumberVisibility();
  });
  $("#export-scene-glb")?.addEventListener("click", () => {
    void downloadViewerGlb(whiteViewer, "RoomPilot-3D場景");
  });
  $$("[data-scene-sidebar-tab]").forEach((button) => {
    button.addEventListener("click", () => setSceneSidebarTab(button.dataset.sceneSidebarTab));
  });
  element.proposalPaletteGrid?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-proposal-style-card]");
    if (button) selectProposalPalette(button.dataset.proposalStyleCard);
  });
  element.proposalContentConfirmed?.addEventListener("change", syncProposalReviewStages);
  $("#search-glb-furniture").addEventListener("click", searchGlbFurniture);
  $("#glb-furniture-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchGlbFurniture();
    }
  });
  element.glbResults.addEventListener("click", (event) => {
    const questionnaireAddButton = event.target.closest("[data-add-questionnaire-furniture-id]");
    if (questionnaireAddButton) {
      addQuestionnaireCatalogFurniture(questionnaireAddButton.dataset.addQuestionnaireFurnitureId);
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
  element.questionnaireCatalogControls?.addEventListener("click", (event) => {
    const room = state.rooms.find((item) => String(item.id) === String(questionnaireCatalogRoomId));
    const scopeButton = event.target.closest("[data-questionnaire-catalog-scope]");
    if (scopeButton) {
      questionnaireCatalogScope = scopeButton.dataset.questionnaireCatalogScope;
      questionnaireCatalogPurpose = "";
      if (questionnaireCatalogScope === "all") questionnaireCatalogSpace = "";
      element.questionnaireCatalogControls
        .querySelectorAll("[data-questionnaire-catalog-scope]")
        .forEach((item) => item.classList.toggle("is-active", item === scopeButton));
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
  [element.questionnaireCatalogColor, element.questionnaireCatalogMaterial].forEach((control) => {
    control?.addEventListener("change", () => {
      if (questionnaireCatalogRoomId) void searchGlbFurniture();
    });
  });
  $("#confirm-white-model").addEventListener("click", confirmWhiteModel);
  element.styleGrid.addEventListener("click", (event) => {
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
  $("#lock-real-view-for-edit").addEventListener("click", (event) => {
    const locked = realisticViewer.toggleCameraLock();
    event.currentTarget.textContent = locked ? "結束家具編輯" : "鎖定視角並編輯家具";
  });
  $$("[data-proposal-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-proposal-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode(button.dataset.proposalViewMode);
  }));
  $("#suggest-master-view").addEventListener("click", () => {
    proposalViewer.lockRenderCamera(false);
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
    $$("[data-proposal-view-mode]").forEach((item) => {
      item.classList.toggle("is-active", item.dataset.proposalViewMode === "orbit");
    });
    element.masterViewStatus.textContent = "已套用建議透視視角；可以繼續微調。";
  });
  $("#lock-master-view").addEventListener("click", lockMasterRenderView);
  $("#return-to-realistic").addEventListener("click", () => goTo("realistic_3d"));
  $("#request-palette-renders").addEventListener("click", requestPaletteRenders);
  element.confirmRenderPalette.addEventListener("click", confirmRenderPalette);
  element.aiRenderTabs?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-ai-render-tab]");
    if (button) setAiRenderWorkbenchStage(button.dataset.aiRenderTab, true);
  });
  element.renderRoomList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-render-room]");
    if (button) selectRenderRoom(button.dataset.renderRoom);
  });
  $("#save-room-view").addEventListener("click", saveSelectedRoomView);
  $("#download-proposal-view")?.addEventListener("click", () => downloadViewerPng(proposalViewer, "RoomPilot-方案視角"));
  $("#save-proposal-view-png")?.addEventListener("click", async () => {
    clearRenderActionError();
    try {
      await saveViewerPngToProject(proposalViewer);
    } catch (error) {
      reportRenderActionError(error);
    }
  });
  $("#download-render-view")?.addEventListener("click", () => downloadViewerPng(aiRenderViewer, "RoomPilot-渲染視角"));
  $("#save-render-view-png")?.addEventListener("click", async () => {
    clearRenderActionError();
    try {
      await saveViewerPngToProject(aiRenderViewer);
    } catch (error) {
      reportRenderActionError(error);
    }
  });
  $("#submit-room-renders").addEventListener("click", submitRoomRenders);
  element.remoteRenderJobs.addEventListener("click", (event) => {
    const retry = event.target.closest("[data-retry-room-render]");
    if (!retry) return;
    retryRoomRender(retry.dataset.retryRoomRender);
  });
  $("#apply-surface-colors").addEventListener("click", () => {
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
  ["wall-color", "wall-material", "floor-material"].forEach((id) => {
    $(`#${id}`)?.addEventListener("change", async () => {
      // 快速選單與材質卡片同一套行為：換材質時色彩欄位跟著換成該材質原色，
      // 否則舊 tint 會把新貼圖染回原本的色調，看起來像沒換材質。
      // 地板沒有色彩欄位，染色在 applySurfaceOverrides 直接取材質代表色。
      const kindMatch = id.match(/^(wall|floor)-material$/);
      if (kindMatch) {
        const colorInput = $(`#${kindMatch[1]}-color`);
        const color = surfaceOptionColor(kindMatch[1], $(`#${id}`).value);
        if (color && colorInput) colorInput.value = color;
      }
      renderGroupedMaterialOptions(stylePackByIdSafe(state.activeStylePackId));
      markRealisticSceneEdited();
      await applySurfaceOverrides({ userInitiated: true });
    });
  });
  $("#draw-material-boundary").addEventListener("click", toggleMaterialBoundary);
  $("#remove-material-boundary").addEventListener("click", removeMaterialBoundary);
  $("#material-boundary-position").addEventListener("input", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  $("#material-boundary-direction").addEventListener("change", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  $("#material-boundary-secondary").addEventListener("change", () => {
    if (state.materialBoundary) toggleMaterialBoundary();
  });
  element.ceilingStyle.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  element.lightStyle.addEventListener("change", () => {
    markRealisticSceneEdited();
    evaluateCeilingConflicts();
  });
  $("#undo-style-change").addEventListener("click", async () => {
    const previous = state.styleHistory.pop();
    if (!previous) return;
    state.surfaceState = previous.surfaceState;
    const pack = STYLE_PACKS.find((item) => item.id === previous.packId);
    if (pack) {
      state.activeStylePackId = null;
      await applyStylePackToScene(pack);
    }
  });
  $("#save-realistic-scene").addEventListener("click", () => {
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
    // 第 6 步的導覽鍵標的是 layout_2d，但使用者要的是「2D＋3D 一起看」的
    // 3D 主畫面；純 2D 那個子畫面只在需要細調平面座標時才進（2026-08-03
    // Ben 實走：從問卷進第 6 步不該落在只有 2D 的頁面）。
    const target = step === "layout_2d" && state.workflow?.canEnter("white_model_3d")
      ? "white_model_3d"
      : step;
    if (state.workflow?.canEnter(target)) goTo(target);
    else setStatus(firstWorkflowBlocker(target), "error");
  }));
  $("#reset-project").addEventListener("click", () => {
    if (!confirm("要重新開始此專案嗎？目前頁面的本機流程狀態會清除。")) return;
    state.workflow?.reset();
    history.replaceState({}, "", "/scene");
    location.reload();
  });
  observePlanStageResizes();
  window.addEventListener("resize", scheduleOverlaySync);
  window.addEventListener("beforeunload", (event) => {
    if (projectExitConfirmed) return;
    if (pendingSaveCount === 0
      && !safeStorageGetItem(localStorage, pendingSaveStorageKey())) return;
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
      visual_preferences: [],
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
      light_style: state.questionnaireFinishes.lightStyle || "",
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
    const pendingSave = safeStorageGetItem(localStorage, pendingSaveStorageKey());
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
      if (removePendingSave) {
        safeStorageRemoveItem(localStorage, pendingSaveStorageKey());
      }
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
    if (Array.isArray(calibrationGeometry?.start_px) && Array.isArray(calibrationGeometry?.end_px)) {
      state.calibrationPoints = [
        { x: Number(calibrationGeometry.start_px[0]), y: Number(calibrationGeometry.start_px[1]) },
        { x: Number(calibrationGeometry.end_px[0]), y: Number(calibrationGeometry.end_px[1]) },
      ];
    } else {
      const scaleEvidence = (state.analysis?.evidence || []).find(
        (item) => Array.isArray(item.start_px) && Array.isArray(item.end_px),
      );
      if (scaleEvidence) {
        state.calibrationPoints = [
          { x: Number(scaleEvidence.start_px[0]), y: Number(scaleEvidence.start_px[1]) },
          { x: Number(scaleEvidence.end_px[0]), y: Number(scaleEvidence.end_px[1]) },
        ];
      }
    }
    if (Number(savedCalibration?.distanceCm) > 0) {
      element.scaleInput.value = Number(savedCalibration.distanceCm);
    } else if (Number(state.analysis?.scale?.distance_cm) > 0) {
      element.scaleInput.value = Number(state.analysis.scale.distance_cm);
    } else if (Number(state.analysis?.scale?.distance_m) > 0) {
      element.scaleInput.value = Math.round(Number(state.analysis.scale.distance_m) * 1000) / 10;
    }
    if (state.analysis) {
      element.recognitionSummary.textContent = `辨識結果：牆 ${state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0}、門 ${state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0}、窗 ${state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0}${recognitionReviewSuffix()}`;
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
    state.rooms = preparedAutoRoomLabels(state.rooms, state.structures.walls || []);
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
    state.firstMeeting = normalizeFirstMeeting(
      serverState.requirements?.firstMeeting || {},
      state.rooms,
    );
    const savedFirstMeetingStep = serverState.requirements?.firstMeetingStep;
    state.firstMeetingStep = FIRST_MEETING_STEPS.some(
      (step) => step.id === savedFirstMeetingStep,
    ) ? savedFirstMeetingStep : "residents";
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
    Object.entries(savedLayoutSchemes).forEach(([schemeId, layout]) => {
      const scheme = state.designSchemes.schemes[schemeId];
      if (!scheme) return;
      scheme.furniture = layout.furniture || scheme.furniture || [];
      scheme.stale = layout.stale === true;
      scheme.staleReason = layout.staleReason || "";
    });
    // 逐房方案選擇與配置快照以 layout_2d 存檔為準（space_confirmation 的
    // design_schemes 只是壓縮副本，normalizeDesignSchemes 已先帶入舊值）。
    if (serverState.layout_2d?.room_selections) {
      state.designSchemes.room_selections = normalizeDesignSchemes({
        room_selections: serverState.layout_2d.room_selections,
      }).room_selections;
    }
    if (serverState.layout_2d?.configuration_snapshot) {
      state.designSchemes.configuration_snapshot = serverState.layout_2d.configuration_snapshot;
    }
    const restoredSchemeB = state.designSchemes.schemes.B;
    const emptySchemeB = restoredSchemeB
      && !hasRenovationChanges(state.structures)
      && !(restoredSchemeB.furniture || []).length
      && !restoredSchemeB.sceneData;
    if (emptySchemeB) deleteSchemeB(state.designSchemes);
    const restoredScheme = activeScheme();
    state.furniture2d = restoredScheme?.furniture || legacyFurniture;
    state.furnitureLedger = {
      order: serverState.layout_2d?.furniture_ledger?.order || [],
      removed: serverState.layout_2d?.furniture_ledger?.removed || [],
    };
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
    const restoredFloorplanRefreshed = await refreshRestoredFloorplanStructure();
    // 還沒上傳過平面圖的專案不能去抓 source——端點會回 409，整段還原會被
    // 誤判為失敗（2026-08-03 QA：新專案一進來就顯示「畫面還原失敗：HTTP 409」）。
    if (state.workflow.completed.includes("upload")) {
      state.sourceUrl = state.sourceExtension === ".dxf"
        ? configureDxfPreview(state.analysis)
        // DXF 走 data URL；影像平面圖要帶身分取回再轉 blob，直接指向 API 會 401。
        : await authorizedObjectUrl(
          `/api/projects/${state.projectId}/floorplan/source?v=${Date.now()}`,
          { cacheKey: `floorplan:${state.projectId}` },
        );
      setPlanImages(state.sourceUrl);
      showUploadedPreview(state.sourceUrl, state.sourceExtension);
    } else {
      state.sourceUrl = null;
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
      || restoredFloorplanRefreshed
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

/**
 * 從風格頁帶進來的色卡。
 *
 * styles.js 產生的連結是 `/scene?style=<風格>&style_card=<色卡>`，並把同一份
 * 選擇寫進 localStorage。這段交接原本只實作在已停用的 scene.js 裡，正式頁面
 * 完全沒接——使用者在風格頁挑的色卡，一進設計流程就被丟掉。
 */
function applyStyleCardFromQuery() {
  const sceneQuery = new URLSearchParams(window.location.search);
  let stored = null;
  try {
    stored = JSON.parse(localStorage.getItem("roompilot:selectedStyleCard") || "null");
  } catch {
    stored = null;
  }
  const requestedCardId = sceneQuery.get("style_card") || stored?.style_card || null;
  const requestedStyleId = sceneQuery.get("style") || stored?.style || stored?.style_id || null;

  const pack = requestedCardId
    ? STYLE_PACKS.find((candidate) => candidate.id === requestedCardId)
    : null;
  if (pack) {
    state.activeStyleId = pack.styleId;
    state.activeStylePackId = pack.id;
    return;
  }
  if (requestedStyleId && STYLE_PACKS.some((candidate) => candidate.styleId === requestedStyleId)) {
    state.activeStyleId = requestedStyleId;
  }
}

bindEvents();
renderFurnitureLibrary();
applyStyleCardFromQuery();
renderStyleControls();
evaluateCeilingConflicts();
// 未登入就沒有專案可還原，直接導向登入頁；畫面已經先組好，登入回來即可續作。
if (requireSignedIn()) {
  restoreProject();
}
