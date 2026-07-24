import { createSceneViewer } from "./scene_viewer.js?v=sha256-abc8ee60ad37";
import { resolveSurfaceOption } from "./scene_surface_materials.js?v=20260719-real3d3";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-73b297a14ce9";
import {
  repairLoadedRoomPolygon,
} from "./scene_room_geometry.js?v=sha256-48e3cd3ec05a";
import {
  createWorkflow,
  mergePendingWorkflowPayload,
  resolveConflictDraftAfterRequest,
  restoreWorkflow,
  shouldReplayPendingSave,
  WORKFLOW_PANEL_BY_STEP,
  WORKFLOW_STEPS,
} from "./scene_workflow.js?v=sha256-d0efd6389df5";
import {
  buildScaleCalibration,
  calibrationActionState,
} from "./scene_calibration.js?v=sha256-175dc2c59c64";
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
} from "./scene_layout2d.js?v=sha256-59d67ea8e479";
import {
  buildClientBrief,
  buildQuestionnaireDocument,
  buildRoomPreferenceSummary,
  cloneRoomAnswer,
  collectQuestionnaireWarnings,
  materialPreferenceOptions,
  normalizeAxisChoice,
  normalizeQuickValues,
  questionnaireCompletion,
  QUESTIONNAIRE_SCHEMA_VERSION,
  questionnaireRoomIdentity,
  reconcileRoomQuestionnaireState,
  requirementsGate,
  roomAnswerIsComplete,
  roomTechnicalAxes,
  roomQuestionTemplate,
  validateCeilingPreference,
  validateQuestionnaireCeilings,
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-0e01ee1db923";
import {
  questionnairePolygonLabelPoint,
  questionnaireRoomAnswerChanged,
  questionnaireRoomAnswerHasDraft,
  hydrateQuestionnaireTechnicalChoices,
  readQuestionnaireTechnicalChoices,
  renderQuestionnaireAxisChoices,
  renderQuestionnaireAxisCustomApproach,
  renderQuestionnaireTechnicalChoices,
  showQuestionnaireStep,
  updateQuestionnaireAxisCustomApproach,
  validateQuestionnaireStage,
  validateQuestionnaireTechnicalCeiling,
  validateQuestionnaireTechnicalChoices,
} from "./questionnaire_wizard.js?v=sha256-c49a7466e396";
import {
  activeScheme,
  buildFallbackSchemeSet,
  DESIGN_STYLES,
  designPreferenceGate,
  isSchemePreviewCurrent,
  normalizeDesignPreferences,
  replaceSchemeFurniture,
  replaceSchemePreferences,
  schemeGenerationContract,
  selectScheme,
} from "./scene_design_workbench.js?v=sha256-3bf404fc1187";
import {
  applyStylePack,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-5f180d95e689";
import {
  applyStylePackPreference,
  applySurfaceSelectionToRooms,
  createMaterialBoundary,
  groupStylePacks,
  isSurfaceEligibleForRoom,
  paginateSurfaceCatalog,
  rankSurfaceCatalog,
  roomMaterialCompletion,
  validateSurfaceSelectionForRooms,
} from "./scene_design_materials.js?v=sha256-dcc1c3050698";
import {
  beamDragGeometry,
  canMarkWallForDemolition,
  dedupeWindowCandidates,
  wallBoundarySide,
  windowsOverlap,
} from "./scene_structure_utils.js?v=sha256-6c5d803a2d30";
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
  activeLayoutRoomId: "all",
  showAllRooms: true,
  spaceReviewMode: "editing",
  spaceMode: "rooms",
  roomGeometryMode: null,
  mergeRoomIds: [],
  splitPoints: [],
  roomNodeMode: null,
  selectedRoomNodeIndices: [],
  structures: { walls: [], doors: [], windows: [], beams: [], columns: [] },
  activeStructureKind: "door",
  structureTool: null,
  structureLineStart: null,
  selectedStructure: null,
  windowNormalizationRemoved: 0,
  basicAnswers: {},
  basicConfirmed: false,
  roomAnswers: {},
  keepExistingRoomIds: [],
  activeQuestionRoomId: null,
  activeBasicQuestionIndex: 0,
  activeRoomQuestionIndex: 0,
  questionnaireMode: "designer_together",
  activeQuestionnaireInviteToken: null,
  conflictedSave: null,
  questionnaireWarnings: [],
  activeQuestionnaireWarningIndex: 0,
  designerQuestionnaireNotes: "",
  minimumFinishedHeightCm: 240,
  designPreferences: normalizeDesignPreferences(),
  activeDesignRoomId: null,
  activeDesignStyleFamily: null,
  activeDesignMaterialTab: "wall",
  activeDesignMaterialTarget: "primary",
  activeDesignMaterialPage: 1,
  designCutSurface: "floor",
  designCutDraftStart: null,
  designCutDraftEnd: null,
  surfaceCatalog: { surfaces: [] },
  layoutSchemeSet: null,
  activeLayoutView: "2d",
  schemePreviewScene: null,
  schemePreviewRevision: 0,
  furniture2d: [],
  selectedFurniture2dId: null,
  sceneData: null,
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
};
let styleApplyRevision = 0;
let schemePreviewLoadQueue = Promise.resolve();

const panels = new Map(
  $$(".rp-step-panel").map((panel) => [panel.dataset.panel, panel]),
);

const instructions = {
  project: ["步驟 1", "先建立專案，之後每一次確認都會自動保存"],
  upload: ["步驟 2", "選擇 DXF、PNG 或 JPG，並確認資料用途"],
  recognition: ["步驟 3–4", "拖曳尺寸線兩端，只輸入一個實際公分尺寸"],
  calibration: ["步驟 3–4", "確認尺度後，才會顯示辨識到的房間"],
  space_confirmation: ["步驟 5", "先確認房間，再確認牆、門、窗、樑與柱"],
  requirements: ["步驟 6", "先完成全屋基本問卷，再逐房間填需求"],
  design_preferences: ["步驟 6", "逐房確認牆面、地板與家具材質，再產生三個方案"],
  layout_2d: ["步驟 7", "比較方案 1／2／3，並在 2D 或 3D 中微調"],
  white_model_3d: ["步驟 8", "確認 3D 白模家具可見，再指定模型、顏色與材質"],
  realistic_3d: ["步驟 9", "從 18 張色卡切換完整 PBR StylePack"],
};

const element = {
  status: $("#global-status"),
  stepNumber: $("#current-step-number"),
  instruction: $("#step-instruction"),
  saveStatus: $("#project-save-status"),
  saveConflict: $("#project-save-conflict"),
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
  requirementsStage: $("#requirements-plan-stage"),
  requirementsImage: $("#requirements-plan-image"),
  requirementsOverlay: $("#requirements-plan-overlay"),
  roomQuestionNav: $("#room-question-nav"),
  roomQuestionTitle: $("#room-question-title"),
  roomUseOptions: $("#room-use-options"),
  roomFurnitureOptions: $("#room-furniture-options"),
  roomUseNote: $("#room-use-note"),
  roomFurnitureNote: $("#room-furniture-note"),
  roomPersonalNeeds: $("#room-personal-needs"),
  roomAxisOptions: $("#room-axis-options"),
  roomWallPreference: $("#room-wall-preference"),
  roomFloorPreference: $("#room-floor-preference"),
  roomFurnitureMaterialPreference: $("#room-furniture-material-preference"),
  roomColorPreference: $("#room-color-preference"),
  roomFinishPreference: $("#room-finish-preference"),
  roomMaterialCuts: $("#room-material-cuts"),
  roomIntegratedSummary: $("#room-integrated-summary"),
  copyRoomSource: $("#copy-room-source"),
  questionnaireMode: $("#questionnaire-mode"),
  questionnaireInviteOutput: $("#questionnaire-invite-output"),
  questionnaireIncompleteList: $("#questionnaire-incomplete-list"),
  questionnaireRoomLocator: $("#questionnaire-room-locator"),
  questionnaireRoomLocatorTitle: $("#questionnaire-room-locator-title"),
  questionnaireWarningCard: $("#questionnaire-warning-card"),
  questionnaireWarningPosition: $("#questionnaire-warning-position"),
  questionnaireWarningRoom: $("#questionnaire-warning-room"),
  questionnaireWarningReason: $("#questionnaire-warning-reason"),
  designerNoteTool: $("#designer-note-tool"),
  designerNoteState: $("#designer-note-state"),
  designerQuestionnaireNotes: $("#designer-questionnaire-notes"),
  minimumFinishedHeightCm: $("#minimum-finished-height-cm"),
  ceilingHeightReference: $("#ceiling-height-reference"),
  clientBriefPreview: $("#client-brief-preview"),
  downloadQuestionnaireJson: $("#download-questionnaire-json"),
  basicQuestionProgress: $("#basic-question-progress"),
  roomQuestionProgress: $("#room-question-progress"),
  requirementsProgress: $("#requirements-progress"),
  requirementsError: $("#requirements-error"),
  confirmRequirements: $("#confirm-requirements"),
  designStyleGrid: $("#design-style-grid"),
  designStatus: $("#design-preferences-status"),
  designWallSurface: $("#design-wall-surface"),
  designFloorSurface: $("#design-floor-surface"),
  designWallColor: $("#design-wall-color"),
  designFloorColor: $("#design-floor-color"),
  designRoomSelector: $("#design-room-selector"),
  designStyleVariantGrid: $("#design-style-variant-grid"),
  designRoomPlanStage: $("#design-room-plan-stage"),
  designRoomPlanImage: $("#design-room-plan-image"),
  designRoomPlanOverlay: $("#design-room-plan-overlay"),
  designRoomProgress: $("#design-room-progress"),
  designRoomNav: $("#design-room-nav"),
  designCurrentRoomName: $("#design-current-room-name"),
  designMaterialTabs: $("#design-material-tabs"),
  designMaterialTarget: $("#design-material-target"),
  designMaterialRecommendation: $("#design-material-recommendation"),
  designMaterialCardGrid: $("#design-material-card-grid"),
  designMaterialPagination: $("#design-material-pagination"),
  previousDesignMaterialPage: $("#previous-design-material-page"),
  designMaterialPageStatus: $("#design-material-page-status"),
  designMaterialPageNumbers: $("#design-material-page-numbers"),
  nextDesignMaterialPage: $("#next-design-material-page"),
  designCutEditor: $("#design-cut-editor"),
  designCutWallFace: $("#design-cut-wall-face"),
  designCutStage: $("#design-cut-stage"),
  designCutFloorImage: $("#design-cut-floor-image"),
  designCutCanvas: $("#design-cut-canvas"),
  designCutSummary: $("#design-cut-summary"),
  designRoomMaterialNote: $("#design-room-material-note"),
  designBaselineSummary: $("#design-baseline-summary"),
  roomTechnicalPreferenceTitle: $("#room-technical-preference-title"),
  roomTechnicalPreferenceOptions: $("#room-technical-preference-options"),
  designNotes: $("#design-preferences-notes"),
  designError: $("#design-preferences-error"),
  layoutSchemeTabs: $("#layout-scheme-tabs"),
  activeSchemeSummary: $("#active-scheme-summary"),
  layout2dView: $("#layout-2d-view"),
  layout3dView: $("#layout-3d-view"),
  layoutGenerationStatus: $("#layout-generation-status"),
  workbenchGlbResults: $("#workbench-glb-results"),
  workbenchWallSurface: $("#workbench-wall-surface"),
  workbenchFloorSurface: $("#workbench-floor-surface"),
  workbenchWallColor: $("#workbench-wall-color"),
  workbenchFloorColor: $("#workbench-floor-color"),
  workbenchCutSurface: $("#workbench-cut-surface"),
  workbenchCutWallFace: $("#workbench-cut-wall-face"),
  workbenchSecondarySurface: $("#workbench-secondary-surface"),
  workbenchSecondaryColor: $("#workbench-secondary-color"),
  layoutImage: $("#layout-plan-image"),
  layoutStage: $("#layout-plan-stage"),
  layoutRoomOverlay: $("#layout-room-overlay"),
  layoutLayer: $("#layout-furniture-layer"),
  layoutRoomFilter: $("#layout-room-filter"),
  furnitureLibrary: $("#furniture-icon-library"),
  furnitureSearch: $("#furniture-icon-search"),
  selectedFurnitureEditor: $("#selected-2d-furniture"),
  selectedFurnitureName: $("#selected-2d-name"),
  selectedFurnitureReason: $("#selected-2d-reason"),
  selectedFurnitureWidth: $("#selected-2d-width"),
  selectedFurnitureDepth: $("#selected-2d-depth"),
  layoutError: $("#layout-error"),
  whiteStatus: $("#white-model-status"),
  whiteError: $("#white-model-error"),
  objectList: $("#scene-object-list"),
  realisticObjectList: $("#realistic-scene-object-list"),
  glbResults: $("#glb-search-results"),
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
  proposalContentConfirmed: $("#proposal-content-confirmed"),
  masterViewStatus: $("#master-view-status"),
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
  onSceneChange: () => scheduleSave("white_model_3d"),
});
const realisticViewer = createSceneViewer($("#realistic-viewer"), element.realisticStatus, {
  onSceneChange: () => markRealisticSceneEdited(),
});
const schemeViewer = createSceneViewer($("#scheme-preview-viewer"), $("#scheme-preview-status"));
const proposalViewer = createSceneViewer(
  $("#proposal-review-viewer"),
  element.proposalReviewStatus,
);
const aiRenderViewer = createSceneViewer($("#ai-render-viewer"), element.aiRenderStatus);
const structurePreview = createStructurePreview($("#structure-3d-preview"));
const styleFurnitureCache = new Map();

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
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const error = new Error(errorMessage(payload));
    Object.assign(error, payload);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function workflowPayload() {
  const stepIsLive = (step) => state.workflow?.currentStep === step
    || state.workflow?.completed.includes(step);
  const calibrationIsLive = stepIsLive("calibration")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("space_confirmation"))
      .some((step) => stepIsLive(step));
  const spaceIsLive = stepIsLive("space_confirmation")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("requirements"))
      .some((step) => stepIsLive(step));
  const requirementsHaveState = state.basicConfirmed
    || Object.keys(state.basicAnswers || {}).length > 0
    || Object.keys(state.roomAnswers || {}).length > 0
    || state.keepExistingRoomIds.length > 0
    || Boolean(state.designerQuestionnaireNotes)
    || state.minimumFinishedHeightCm !== 240;
  const requirementsAreLive = stepIsLive("requirements")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("design_preferences"))
      .some((step) => stepIsLive(step))
    || requirementsHaveState;
  const designPreferencesAreLive = stepIsLive("design_preferences")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("layout_2d"))
      .some((step) => stepIsLive(step))
    || Boolean(state.designPreferences?.styleId);
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
        }
      : null,
    requirements: requirementsAreLive
      ? {
          basic: state.basicAnswers,
          basicConfirmed: state.basicConfirmed,
          rooms: state.roomAnswers,
          keepExistingRoomIds: state.keepExistingRoomIds,
          mode: state.questionnaireMode,
          settings: {
            minimumFinishedHeightCm: state.minimumFinishedHeightCm,
          },
          designerNotes: state.designerQuestionnaireNotes,
          clientBrief: buildClientBrief({
            basicAnswers: state.basicAnswers,
            rooms: state.rooms,
            answers: state.roomAnswers,
            keepExistingRoomIds: state.keepExistingRoomIds,
            designerNotes: state.designerQuestionnaireNotes,
          }),
        }
      : null,
    design_preferences: designPreferencesAreLive
      ? state.designPreferences
      : null,
    layout_2d: layoutIsLive
      ? {
          furniture: state.furniture2d,
          schemeSet: state.layoutSchemeSet
            ? replaceSchemeFurniture(
                state.layoutSchemeSet,
                state.layoutSchemeSet.activeSchemeId,
                state.furniture2d,
              )
            : null,
          activeSchemeId: state.layoutSchemeSet?.activeSchemeId || null,
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

function workflowSectionsForStep(currentStep) {
  const sectionsByStep = {
    upload: ["_flow", "privacy"],
    recognition: ["_flow", "privacy", "recognition"],
    calibration: ["_flow", "recognition", "confirmed_floorplan", "calibration"],
    space_confirmation: [
      "_flow",
      "recognition",
      "confirmed_floorplan",
      "calibration",
      "space_confirmation",
    ],
    requirements: ["_flow", "requirements"],
    design_preferences: ["_flow", "requirements", "design_preferences"],
    layout_2d: ["_flow", "requirements", "design_preferences", "layout_2d"],
    white_model_3d: [
      "_flow",
      "requirements",
      "design_preferences",
      "layout_2d",
      "white_model_3d",
    ],
    realistic_3d: [
      "_flow",
      "requirements",
      "design_preferences",
      "layout_2d",
      "white_model_3d",
      "realistic_3d",
    ],
  };
  return sectionsByStep[currentStep] || null;
}

function scopeWorkflowSections(currentStep, workflow) {
  const sections = workflowSectionsForStep(currentStep) || Object.keys(workflow);
  return Object.fromEntries(
    sections
      .filter((key) => Object.hasOwn(workflow, key))
      .map((key) => [key, workflow[key]])
  );
}

function scopedWorkflowPayload(currentStep) {
  return scopeWorkflowSections(currentStep, workflowPayload());
}

let saveSequence = Promise.resolve();
let pendingSaveCount = 0;
let pendingSaveRevision = 0;
let saveConflictActive = false;
let saveGeneration = 0;
let autoLayoutPending = false;
let autoLayoutRequestRevision = 0;
let layoutConfirmationPending = false;
let layoutConfirmationRequestRevision = 0;
let projectExitConfirmed = false;
let designerDraftSaveTimer = null;

function pendingSaveStorageKey() {
  return state.projectId ? `roompilot.pending-save.${state.projectId}` : "";
}

function conflictedSaveStorageKey() {
  return state.projectId ? `roompilot.conflicted-save.${state.projectId}` : "";
}

function showSaveConflict(serialized) {
  if (!saveConflictActive) saveGeneration += 1;
  saveConflictActive = true;
  state.conflictedSave = serialized;
  localStorage.setItem(conflictedSaveStorageKey(), serialized);
  element.saveConflict.hidden = false;
  element.saveStatus.textContent = "等待處理問卷版本衝突";
}

function clearSaveConflict() {
  if (saveConflictActive || state.conflictedSave) saveGeneration += 1;
  saveConflictActive = false;
  state.conflictedSave = null;
  localStorage.removeItem(conflictedSaveStorageKey());
  element.saveConflict.hidden = true;
}

function capturePendingSave(currentStep = state.workflow?.currentStep) {
  const serialized = JSON.stringify({
    save_id: `${Date.now()}-${pendingSaveRevision += 1}`,
    base_updated_at: state.project?.updated_at || null,
    base_workflow: state.project?.workflow || {},
    current_step: currentStep,
    workflow: scopedWorkflowPayload(currentStep),
  });
  localStorage.setItem(pendingSaveStorageKey(), serialized);
  return serialized;
}

function rebaseSerializedSave(serialized) {
  const payload = JSON.parse(serialized);
  payload.base_updated_at = state.project?.updated_at || payload.base_updated_at || null;
  return JSON.stringify(payload);
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
      const result = await response.json();
      if (!response.ok) {
        const error = new Error(
          result.detail?.message || result.detail || "專案保存失敗。",
        );
        error.status = response.status;
        throw error;
      }
      return result;
    } catch (error) {
      lastError = error;
      if (error.status === 409) throw error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 180 * (attempt + 1)));
    }
  }
  throw lastError;
}

function scheduleSave(currentStep = state.workflow?.currentStep) {
  if (!state.projectId) return;
  const serialized = capturePendingSave(currentStep);
  const saveToken = saveGeneration;
  pendingSaveCount += 1;
  element.saveStatus.textContent = "正在保存…";
  saveSequence = saveSequence.catch(() => null).then(async () => {
    try {
      if (saveConflictActive || state.conflictedSave) {
        const latestDraft =
          localStorage.getItem(pendingSaveStorageKey()) || serialized;
        showSaveConflict(latestDraft);
        return;
      }
      if (saveToken !== saveGeneration) return;
      const result = await saveWorkflowRequest(rebaseSerializedSave(serialized));
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
      if (error.status === 409) {
        const latest = await api(`/api/projects/${state.projectId}`);
        state.project = latest.project;
        const latestDraft =
          localStorage.getItem(pendingSaveStorageKey()) || serialized;
        showSaveConflict(latestDraft);
        return;
      }
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

async function reapplyConflictedSave() {
  const serialized = state.conflictedSave
    || localStorage.getItem(conflictedSaveStorageKey());
  if (!serialized || !state.project) return;
  const payload = mergePendingWorkflowPayload(serialized, state.project);
  if (!payload) {
    setStatus("無法讀取保留的編輯草稿，草稿仍保留在此瀏覽器。", "error");
    return;
  }
  payload.workflow = scopeWorkflowSections(payload.current_step, payload.workflow);
  const mergedRequirements = payload.workflow?.requirements;
  if (mergedRequirements) {
    mergedRequirements.clientBrief = buildClientBrief({
      basicAnswers: mergedRequirements.basic || {},
      rooms: payload.workflow?.space_confirmation?.rooms || state.rooms,
      answers: mergedRequirements.rooms || {},
      keepExistingRoomIds: mergedRequirements.keepExistingRoomIds || [],
      designerNotes: mergedRequirements.designerNotes || "",
    });
  }
  try {
    element.saveStatus.textContent = "正在合併問卷編輯…";
    const result = await saveWorkflowRequest(JSON.stringify(payload));
    state.project = result.project;
    const draftState = resolveConflictDraftAfterRequest({
      sentDraft: serialized,
      pendingDraft: localStorage.getItem(pendingSaveStorageKey()),
    });
    if (draftState.hasNewerDraft) {
      showSaveConflict(draftState.conflictDraft);
      element.saveStatus.textContent = "合併完成，但仍有較新的本機編輯待處理";
      return;
    }
    localStorage.removeItem(pendingSaveStorageKey());
    clearSaveConflict();
    location.reload();
  } catch (error) {
    if (error.status === 409) {
      const latest = await api(`/api/projects/${state.projectId}`);
      state.project = latest.project;
      const draftState = resolveConflictDraftAfterRequest({
        sentDraft: serialized,
        pendingDraft: localStorage.getItem(pendingSaveStorageKey()),
      });
      showSaveConflict(draftState.conflictDraft);
    }
    setStatus(errorMessage(error), "error");
  }
}

function acceptLatestProjectVersion() {
  localStorage.removeItem(pendingSaveStorageKey());
  clearSaveConflict();
  location.reload();
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
    state.sceneData = null;
    state.furniture2d = [];
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "requirements") {
    state.sceneData = null;
    state.furniture2d = [];
    state.designPreferences = normalizeDesignPreferences();
    state.layoutSchemeSet = null;
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "design_preferences") {
    state.sceneData = null;
    state.furniture2d = [];
    state.layoutSchemeSet = null;
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
  if (autoLayoutPending && step !== "layout_2d") {
    autoLayoutRequestRevision += 1;
  }
  if (layoutConfirmationPending && step !== "layout_2d") {
    layoutConfirmationRequestRevision += 1;
  }
  const panelName = activePanelName(step);
  const progressStep = step === "design_preferences" ? "requirements" : step;
  element.designerNoteTool.hidden = !state.projectId;
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
  $$(".rp-progress button").forEach((button) => {
    const target = button.dataset.step;
    const targetIndex = WORKFLOW_STEPS.indexOf(target);
    const currentIndex = WORKFLOW_STEPS.indexOf(progressStep);
    button.classList.toggle("is-active", target === progressStep);
    button.classList.toggle("is-complete", targetIndex >= 0 && targetIndex < currentIndex);
  });
  requestAnimationFrame(syncAllOverlays);
}

function updateDesignerNoteState() {
  element.designerNoteState.hidden =
    !element.designerQuestionnaireNotes.value.trim();
}

async function renderRestoredStep() {
  if (state.rooms.length) {
    state.selectedRoomId = state.selectedRoomId || state.rooms[0].id;
    renderRooms();
    renderStructureCounts();
    renderWholeHouseQuestionnaire();
    renderQuestionRooms();
    if (state.basicConfirmed) {
      $("#whole-house-questionnaire").hidden = true;
      $("#room-questionnaire").hidden = false;
      element.confirmRequirements.hidden = false;
      selectQuestionRoom(state.activeQuestionRoomId);
    }
    refreshQuestionnaireStatus();
  }
  if (
    state.workflow.currentStep === "design_preferences"
    || state.workflow.completed.includes("design_preferences")
  ) {
    await renderDesignPreferences();
  }
  if (state.layoutSchemeSet) renderLayoutSchemes();
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
  captureActiveDesignerRoomDraft();
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
    design_preferences: "請先完成基本問卷與每一個房間需求。",
    layout_2d: "請先確認整體風格、牆面與地板素材偏好。",
    white_model_3d: "請先確認 2D 家具尺寸與配置。",
    realistic_3d: "請先確認 3D 家具確實可見，並確認指定家具需求。",
    proposal_review: "請先完成並保存即時寫實方案。",
    ai_render: "請先確認完整方案，並在第 9 步最後鎖定色卡比較視角。",
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
  const corePlanImages = [element.scaleImage, element.spaceImage, element.requirementsImage, element.layoutImage];
  [
    ...corePlanImages,
    element.designRoomPlanImage,
    element.designCutFloorImage,
  ]
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
  syncOverlayToImage(element.requirementsStage, element.requirementsImage, element.requirementsOverlay);
  syncOverlayToImage(
    element.designRoomPlanStage,
    element.designRoomPlanImage,
    element.designRoomPlanOverlay,
  );
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  syncLayoutLayer();
  renderCalibration();
  renderSpaceOverlay();
  renderRequirementsOverlay();
  renderDesignRoomLocator();
  renderLayoutFurniture();
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

function confirmedFloorplanEditor() {
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
    structures: JSON.parse(JSON.stringify(state.structures)),
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
    const geometryRepaired = repairedPolygon.length < normalizedPolygon.length;
    if (geometryRepaired) repairedRoomCount += 1;
    return {
      ...room,
      id: room.id || room.room_id || `room-${index + 1}`,
      label: room.label || room.name || `空間 ${index + 1}`,
      type: room.type || room.room_type || "default",
      confirmed: geometryRepaired ? false : room.confirmed === true,
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
  normalizeWallDemolitionCandidates();
  repairLoadedStructureWallCollisions();
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

function renderRooms() {
  element.roomList.innerHTML = state.rooms.map((room) => {
    const dimensions = roomDimensions(room);
    const active = room.id === state.selectedRoomId;
    const merging = state.mergeRoomIds.includes(room.id);
    return `
      <article class="rp-room-item ${active ? "is-active" : ""} ${merging ? "is-merge-selected" : ""}">
        <button type="button" data-room-id="${escapeHtml(room.id)}" class="rp-room-select">
          <strong>${escapeHtml(room.label)}</strong>
          <span>${dimensions.areaM2.toFixed(2)} m²</span>
          <small>${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm</small>
          <small>${room.confirmed ? "已確認" : `信心 ${(Number(room.confidence || room.polygon_confidence || 0.7) * 100).toFixed(0)}%`}</small>
        </button>
        <button type="button" data-confirm-room="${escapeHtml(room.id)}"
          class="rp-room-confirm ${room.confirmed ? "is-confirmed" : ""}">
          ${room.confirmed ? "已確認" : "確認"}
        </button>
      </article>
    `;
  }).join("");
  const confirmedCount = state.rooms.filter((room) => room.confirmed).length;
  element.roomConfirmationProgress.textContent =
    `已確認 ${confirmedCount} / ${state.rooms.length} 個房間`;
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (room) {
    const dimensions = roomDimensions(room);
    element.roomEditor.hidden = false;
    element.roomName.value = room.label;
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
  wall.confirmed = false;
  wall.estimated = false;
  element.spaceError.textContent = "";
  renderSpaceOverlay();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  renderStructureCounts();
  if (!changed) return;
  invalidateDownstreamFrom(
    "space_confirmation",
    "可拆牆方案已修改，後續需求、家具與 3D 需要重新確認。",
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
    return structureGroup(
      item,
      "door",
      `${dragTarget}${line}<path d="M ${end.x} ${end.y} A ${radius} ${radius} 0 0 ${sweep} ${swingEnd.x} ${swingEnd.y}" fill="none" stroke="#bd5c36" stroke-width="3"/>${marker}${handles}`,
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
  };
  if (rejectStructureWallCollision(item, "beam")) {
    renderSpaceOverlay();
    return false;
  }
  state.structures.beams.push(item);
  state.selectedStructure = { id: item.id, kind: "beam" };
  state.structureTool = null;
  $$('[data-structure-tool]').forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "已新增樑，後續需求、家具與 3D 需要重新確認。");
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
        demolition_candidate: false,
      };
      state.structures[collection].push(item);
      state.selectedStructure = { id: item.id, kind };
      state.structureLineStart = null;
      state.structureTool = null;
      $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
      renderSpaceOverlay();
      renderStructureCounts();
      renderStructureReviewList();
      renderSelectedStructureEditor();
      invalidateDownstreamFrom("space_confirmation", "已新增牆/樑，後續需求、家具與 3D 需要重新確認。");
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
      item.start = candidate.start;
      item.end = candidate.end;
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
  Object.assign(item, resolution.item);
  if (kind === "wall") normalizeWallDemolitionCandidates();
  structureSizeDraft = null;
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構尺寸已修改，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  const shiftNote = resolution.moved
    ? `，並向室內避牆位移 ${Math.round(resolution.totalShiftCm)} 公分`
    : "";
  setStatus(kind === "column"
    ? `柱寬深已更新為 ${Math.round(sizeCm)} × ${Math.round(depthCm)} 公分，柱高依樓高固定為 ${Math.round(heightCm)} 公分${shiftNote}。`
    : `樑尺寸已更新${shiftNote}。`);
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
  invalidateDownstreamFrom(
    "space_confirmation",
    "窗戶類型已修改，後續需求、家具與 3D 需要重新確認。",
  );
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
    invalidateDownstreamFrom("space_confirmation", `${label}寬已調整，後續需求、家具與 3D 需要重新確認。`);
    scheduleSave("space_confirmation");
    setStatus(`${label}寬已調整為 ${Math.round(widthCm)} cm；請重新確認此${label}。`);
  }
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
  const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x)
    + (Math.PI / 180) * deltaDeg;
  const length = Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y);
  const center = {
    x: (item.start.x + item.end.x) / 2,
    y: (item.start.y + item.end.y) / 2,
  };
  item.start = {
    x: center.x - Math.cos(angle) * length / 2,
    y: center.y - Math.sin(angle) * length / 2,
  };
  item.end = {
    x: center.x + Math.cos(angle) * length / 2,
    y: center.y + Math.sin(angle) * length / 2,
  };
  if (state.selectedStructure?.kind === "door") delete item.swing_end;
  if (state.selectedStructure?.kind === "wall") normalizeWallDemolitionCandidates();
  item.confirmed = false;
  item.estimated = false;
  renderSpaceOverlay();
  renderDoorReviewList();
  renderDoorReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構方向已微調，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
}

function deleteSelectedStructure() {
  if (!state.selectedStructure) return;
  const deletedKind = state.selectedStructure.kind;
  const collection = structureCollections[state.selectedStructure.kind];
  state.structures[collection] = state.structures[collection].filter(
    (item) => item.id !== state.selectedStructure.id,
  );
  const nextItem = state.structures[collection][0] || null;
  state.selectedStructure = nextItem ? { id: nextItem.id, kind: deletedKind } : null;
  renderSpaceOverlay();
  renderStructureCounts();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構已刪除，後續需求、家具與 3D 需要重新確認。");
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
  const name = element.roomName.value.trim();
  if (!name) {
    element.spaceError.textContent = "請輸入空間名稱。";
    element.roomName.focus();
    return;
  }
  room.label = name;
  room.confirmed = false;
  room.source = "manual_confirmation";
  room.confidence = 1;
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
    state.selectedStructure = { id: item.id, kind: tool };
  }
  state.structureTool = null;
  $$("[data-structure-tool]").forEach((button) => button.classList.remove("is-active"));
  renderSpaceOverlay();
  renderStructureCounts();
  renderStructureReviewList();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "已新增結構，後續需求、家具與 3D 需要重新確認。");
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
  invalidateDownstreamFrom("space_confirmation", "門的鉸鏈端已翻轉，後續需求、家具與 3D 需要重新確認。");
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
  });
  renderWholeHouseQuestionnaire();
  setStatus("尺寸標註平面圖與結構均已確認。現在開始基本問卷。");
  goTo("requirements");
}

function renderWholeHouseQuestionnaire() {
  element.questionnaireRoomLocator.hidden = true;
  element.wholeHouseFields.innerHTML = WHOLE_HOUSE_QUESTIONS.map((question) => {
    const inputType = question.type === "multi" ? "checkbox" : "radio";
    const options = question.options.map((option) => `
        <label>
          <input type="${inputType}" name="basic-${escapeHtml(question.id)}" value="${escapeHtml(option.value)}"/>
          <span><strong>${escapeHtml(option.label)}</strong>${option.description ? `<small>${escapeHtml(option.description)}</small>` : ""}</span>
        </label>
      `).join("");
    return `
      <fieldset data-basic-question="${escapeHtml(question.id)}">
        <legend>${escapeHtml(question.label)}</legend>
        <div class="rp-choice-grid">${options}</div>
        <label class="rp-question-note">
          <span>補充（選填）</span>
          <textarea rows="2" placeholder="${escapeHtml(question.example || "")}"></textarea>
        </label>
      </fieldset>
    `;
  }).join("");
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    const stored = state.basicAnswers[question.id];
    const selectedValues = Array.isArray(stored) ? stored : [stored];
    $$("input", host).forEach((input) => {
      input.checked = selectedValues.includes(input.value);
    });
    const note = host?.querySelector("textarea");
    if (note) note.value = state.basicAnswers.notes?.[question.id] || "";
    if (question.type === "multi" && question.exclusiveValues?.length) {
      host.addEventListener("change", (event) => {
        const changed = event.target.closest("input[type='checkbox']");
        if (!changed?.checked) return;
        const exclusive = new Set(question.exclusiveValues);
        $$("input[type='checkbox']", host).forEach((input) => {
          if (input === changed) return;
          if (exclusive.has(changed.value) || exclusive.has(input.value)) input.checked = false;
        });
      });
    }
  });
  renderBasicQuestionStep();
}

function updateCeilingHeightReference() {
  const roomHeightCm = Number(
    state.confirmedFloorplan?.floorplan?.room_height_cm
    || state.sceneData?.floorplan?.room_height_cm
    || 270
  );
  element.minimumFinishedHeightCm.value = String(state.minimumFinishedHeightCm);
  element.ceilingHeightReference.textContent =
    `目前原始室內高度 ${roomHeightCm} 公分；低於設定值的天花方案會被阻擋。`;
}

function renderBasicQuestionStep(index = state.activeBasicQuestionIndex) {
  const questions = $$("[data-basic-question]", element.wholeHouseFields);
  if (!questions.length) return;
  const step = showQuestionnaireStep(questions, index);
  state.activeBasicQuestionIndex = step.index;
  const current = WHOLE_HOUSE_QUESTIONS[state.activeBasicQuestionIndex];
  element.basicQuestionProgress.textContent =
    `基本資料 ${state.activeBasicQuestionIndex + 1}/${step.total} · ${current.label}`;
  $("#previous-basic-question").disabled = state.activeBasicQuestionIndex === 0;
  $("#next-basic-question").hidden = state.activeBasicQuestionIndex === step.total - 1;
  $("#confirm-basic-questionnaire").hidden =
    state.activeBasicQuestionIndex !== step.total - 1;
}

function advanceBasicQuestion(direction) {
  element.requirementsError.textContent = "";
  if (direction > 0) {
    const question = WHOLE_HOUSE_QUESTIONS[state.activeBasicQuestionIndex];
    const host = $(`[data-basic-question="${question.id}"]`);
    const selected = $$("input:checked", host);
    if (question.required && !selected.length) {
      element.requirementsError.textContent = `請先回答「${question.label}」。`;
      return;
    }
  }
  renderBasicQuestionStep(state.activeBasicQuestionIndex + direction);
}

function prepareQuestionnaireStep() {
  renderWholeHouseQuestionnaire();
  renderQuestionRooms();
  if (state.basicConfirmed) {
    $("#whole-house-questionnaire").hidden = true;
    $("#room-questionnaire").hidden = false;
    element.confirmRequirements.hidden = false;
    selectQuestionRoom(state.activeQuestionRoomId || state.rooms[0]?.id);
  } else {
    $("#whole-house-questionnaire").hidden = false;
    $("#room-questionnaire").hidden = true;
    element.confirmRequirements.hidden = true;
  }
  refreshQuestionnaireStatus();
}

function collectBasicAnswers() {
  const answers = { notes: {} };
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    const selected = $$("input:checked", host).map((input) => input.value);
    answers[question.id] = question.type === "multi"
      ? normalizeQuickValues(question, selected)
      : selected[0] || "";
    answers.notes[question.id] = host?.querySelector("textarea")?.value.trim() || "";
  });
  return answers;
}

function confirmBasicQuestionnaire() {
  element.requirementsError.textContent = "";
  const answers = collectBasicAnswers();
  const missing = WHOLE_HOUSE_QUESTIONS.find((question) => {
    const value = answers[question.id];
    return question.required && (Array.isArray(value) ? !value.length : !value);
  });
  if (missing) {
    element.requirementsError.textContent = `請完成「${missing.label}」。`;
    renderBasicQuestionStep(
      WHOLE_HOUSE_QUESTIONS.findIndex((question) => question.id === missing.id),
    );
    return;
  }
  state.basicAnswers = answers;
  state.basicConfirmed = true;
  $("#whole-house-questionnaire").hidden = true;
  $("#room-questionnaire").hidden = false;
  element.confirmRequirements.hidden = false;
  selectQuestionRoom(state.activeQuestionRoomId || state.rooms[0]?.id);
  refreshQuestionnaireStatus();
  scheduleSave("requirements");
}

function showQuestionnaireStage(stage) {
  goTo(stage === "finishes" ? "design_preferences" : "requirements");
}

function renderQuestionRooms() {
  element.roomQuestionNav.innerHTML = state.rooms.map((room) => {
    const resolved = roomAnswerIsComplete(room, state.roomAnswers[room.id])
      || state.keepExistingRoomIds.includes(room.id);
    return `<button type="button" data-question-room="${escapeHtml(room.id)}" class="${room.id === state.activeQuestionRoomId ? "is-active" : ""}">${escapeHtml(room.label)}${resolved ? " · 已完成" : ""}</button>`;
  }).join("");
}

function selectedSelectValues(select) {
  return Array.from(select?.selectedOptions || []).map((option) => option.value);
}

function setSelectedValues(select, values = []) {
  const selected = new Set(values);
  Array.from(select?.options || []).forEach((option) => {
    option.selected = selected.has(option.value);
  });
}

function readActiveDesignerRoomAnswer({ confirmed = false } = {}) {
  const room = state.rooms.find((item) => item.id === state.activeQuestionRoomId);
  if (!room || !element.roomAxisOptions.children.length) return null;
  const template = roomQuestionTemplate(room.type);
  const existingAnswer = state.roomAnswers[room.id] || {};
  const axes = { ...(existingAnswer.axes || {}) };
  const customNotes = { ...(existingAnswer.customNotes || {}) };
  template.axes.forEach((axisDefinition) => {
    const host = $(`[data-room-axis="${axisDefinition.id}"]`, element.roomAxisOptions);
    axes[axisDefinition.id] = host?.querySelector("input:checked")?.value || "";
    customNotes[axisDefinition.id] = host?.querySelector("textarea")?.value.trim() || "";
  });
  Object.assign(
    axes,
    readQuestionnaireTechnicalChoices({
      container: element.roomTechnicalPreferenceOptions,
      axes: roomTechnicalAxes(room.type),
    }),
  );
  return {
    schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
    roomIdentity: questionnaireRoomIdentity(room),
    confirmed,
    uses: $$("input:checked", element.roomUseOptions).map((input) => input.value),
    axes,
    customNotes,
    stageNotes: {
      uses: element.roomUseNote.value.trim(),
      furniture: element.roomFurnitureNote.value.trim(),
    },
    furniture: $$("input:checked", element.roomFurnitureOptions).map((input) => input.value),
    personalNeeds: element.roomPersonalNeeds.value.trim(),
    materialPreferences: {
      wall: selectedSelectValues(element.roomWallPreference),
      floor: selectedSelectValues(element.roomFloorPreference),
      furniture: selectedSelectValues(element.roomFurnitureMaterialPreference),
      color: selectedSelectValues(element.roomColorPreference),
      finish: selectedSelectValues(element.roomFinishPreference),
      cuts: element.roomMaterialCuts.value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    },
  };
}

function captureActiveDesignerRoomDraft() {
  const roomId = state.activeQuestionRoomId;
  const draft = readActiveDesignerRoomAnswer();
  if (!roomId || !draft || !questionnaireRoomAnswerHasDraft(draft)) return false;
  if (!questionnaireRoomAnswerChanged(draft, state.roomAnswers[roomId])) return false;
  state.roomAnswers[roomId] = draft;
  state.keepExistingRoomIds = state.keepExistingRoomIds.filter((id) => id !== roomId);
  return true;
}

function scheduleDesignerQuestionnaireDraftSave() {
  captureActiveDesignerRoomDraft();
  clearTimeout(designerDraftSaveTimer);
  designerDraftSaveTimer = setTimeout(() => {
    designerDraftSaveTimer = null;
    scheduleSave("requirements");
  }, 500);
}

function renderRoomAxes(room, existing = null) {
  const template = roomQuestionTemplate(room.type);
  element.roomAxisOptions.innerHTML = template.axes.map((axisDefinition) => `
    <fieldset class="rp-room-axis" data-room-axis="${escapeHtml(axisDefinition.id)}">
      <legend>${escapeHtml(axisDefinition.label)}</legend>
      <p>${escapeHtml(axisDefinition.prompt)}</p>
      ${renderQuestionnaireAxisChoices({
        axisDefinition,
        inputName: `room-axis-${axisDefinition.id}`,
      })}
      ${renderQuestionnaireAxisCustomApproach({
        axisLabel: axisDefinition.label,
        customExample: axisDefinition.customExample,
        existingNote: existing?.customNotes?.[axisDefinition.id],
      })}
    </fieldset>
  `).join("");
  template.axes.forEach((axisDefinition) => {
    const host = $(`[data-room-axis="${axisDefinition.id}"]`, element.roomAxisOptions);
    const selected = normalizeAxisChoice(
      axisDefinition,
      existing?.axes?.[axisDefinition.id],
    );
    const input = host?.querySelector(`input[value="${CSS.escape(selected || "")}"]`);
    if (input) input.checked = true;
    const note = host?.querySelector("textarea");
    if (note) note.value = existing?.customNotes?.[axisDefinition.id] || "";
  });
  renderRoomTechnicalPreferences(room);
}

function roomQuestionStages() {
  return [
    ...$$("[data-room-axis]", element.roomAxisOptions),
    ...$$("[data-room-question-stage]", $("#room-questionnaire")),
  ];
}

function roomQuestionStageLabel(stage) {
  return stage.querySelector("legend")?.textContent
    || stage.querySelector("span")?.textContent
    || "整合確認";
}

function renderRoomQuestionStep(index = state.activeRoomQuestionIndex) {
  const stages = roomQuestionStages();
  if (!stages.length) return;
  const step = showQuestionnaireStep(stages, index);
  state.activeRoomQuestionIndex = step.index;
  const room = state.rooms.find((item) => item.id === state.activeQuestionRoomId);
  const currentStage = step.current;
  element.roomQuestionProgress.textContent =
    `${room?.label || "空間"} · ${roomQuestionStageLabel(currentStage)} `
    + `${state.activeRoomQuestionIndex + 1}/${step.total}`;
  $("#previous-room-question").disabled = state.activeRoomQuestionIndex === 0;
  $("#next-room-question").hidden = state.activeRoomQuestionIndex === step.total - 1;
  $("#confirm-room-requirement").hidden = state.activeRoomQuestionIndex !== step.total - 1;
}

function validateCurrentRoomQuestion() {
  const stages = roomQuestionStages();
  const stage = stages[state.activeRoomQuestionIndex];
  if (stage?.dataset.roomQuestionStage === "technical") {
    const technicalValidation = validateQuestionnaireTechnicalChoices({
      container: stage,
    });
    if (!technicalValidation.ready) {
      const label = technicalValidation.missingLabel || "天花、冷氣與燈光";
      element.requirementsError.textContent = `請先完成「${label}」。`;
      return false;
    }
    const room = state.rooms.find((item) => item.id === state.activeQuestionRoomId);
    const ceilingResult = validateQuestionnaireTechnicalCeiling({
      container: stage,
      axes: roomTechnicalAxes(room?.type),
      roomHeightCm: Number(
        state.confirmedFloorplan?.floorplan?.room_height_cm
        || state.sceneData?.floorplan?.room_height_cm
        || 270
      ),
      minimumFinishedHeightCm: state.minimumFinishedHeightCm,
      validatePreference: validateCeilingPreference,
    });
    if (!ceilingResult.ready) {
      element.requirementsError.textContent =
        `此天花方案預估完成淨高 ${ceilingResult.finishedHeightCm} 公分，低於設計師設定的 `
        + `${ceilingResult.minimumFinishedHeightCm} 公分，不能繼續。`;
      return false;
    }
    return true;
  }
  const result = validateQuestionnaireStage(stage, {
    axisDatasetKey: "roomAxis",
    usesDatasetKey: "roomQuestionStage",
  });
  if (result.kind === "axis") {
    element.requirementsError.textContent = `請先完成「${result.label}」。`;
  } else if (result.kind === "uses") {
    element.requirementsError.textContent = "請至少選擇一項空間用途。";
  }
  return result.ready;
}

function advanceRoomQuestion(direction) {
  element.requirementsError.textContent = "";
  if (direction > 0 && !validateCurrentRoomQuestion()) return;
  renderRoomIntegratedSummary();
  renderRoomQuestionStep(state.activeRoomQuestionIndex + direction);
}

function renderRoomIntegratedSummary() {
  const room = state.rooms.find((item) => item.id === state.activeQuestionRoomId);
  if (!room) return;
  const draft = readActiveDesignerRoomAnswer()
    || state.roomAnswers[room.id]
    || {};
  const summary = buildRoomPreferenceSummary(room, draft);
  element.roomIntegratedSummary.innerHTML = `
    <strong>${escapeHtml(summary.headline)}</strong>
    ${summary.basis.length
      ? `<ul>${summary.basis.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "<p>請從 A／B 對照題開始選擇，系統會說明家具與材質檢索依據。</p>"}
    ${summary.other_approaches.length
      ? `<p><strong>補充想法：</strong>${escapeHtml(summary.other_approaches.join("；"))}</p>`
      : ""}
    ${summary.warnings.length
      ? `<p><strong>需設計師確認：</strong>${escapeHtml(summary.warnings.map((item) => item.reason).join("；"))}</p>`
      : ""}
  `;
}

function renderRequirementsOverlay() {
  if (!element.requirementsImage || !element.requirementsOverlay || !element.requirementsImage.naturalWidth || !state.rooms.length) return;
  element.requirementsOverlay.innerHTML = state.rooms.map((room) => {
    const points = (room.polygon_cm || []).map(cmToPixel);
    if (points.length < 3) return "";
    const center = questionnairePolygonLabelPoint(points);
    const active = room.id === state.activeQuestionRoomId;
    return `
      <g data-requirement-room="${escapeHtml(room.id)}" role="button" tabindex="0"
        aria-label="切換到${escapeHtml(room.label)}">
        <polygon points="${roomPolygonSvg(room)}"
          fill="${active ? "rgba(47,111,135,.3)" : "rgba(36,107,85,.08)"}"
          stroke="${active ? "#2f6f87" : "#7b8f86"}" stroke-width="${active ? 6 : 3}"/>
        <text x="${center.x}" y="${center.y}" text-anchor="middle" dominant-baseline="central"
          class="${active ? "is-active" : ""}">${escapeHtml(room.label)}</text>
      </g>
    `;
  }).join("");
}

function syncRequirementsLocator() {
  syncOverlayToImage(
    element.requirementsStage,
    element.requirementsImage,
    element.requirementsOverlay,
  );
  renderRequirementsOverlay();
}

function selectQuestionRoom(roomId, {
  captureDraft = true,
  forceReload = false,
} = {}) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  if (
    !forceReload
    && state.activeQuestionRoomId === roomId
    && element.roomAxisOptions.children.length
  ) return;
  clearTimeout(designerDraftSaveTimer);
  designerDraftSaveTimer = null;
  const draftCaptured = captureDraft
    && Boolean(state.activeQuestionRoomId)
    && state.activeQuestionRoomId !== roomId
    && captureActiveDesignerRoomDraft();
  state.activeQuestionRoomId = roomId;
  state.selectedRoomId = roomId;
  element.questionnaireRoomLocator.hidden = false;
  element.questionnaireRoomLocatorTitle.textContent = room.label;
  requestAnimationFrame(syncRequirementsLocator);
  const template = roomQuestionTemplate(room.type);
  const materialOptions = materialPreferenceOptions(room.type);
  element.roomQuestionTitle.textContent = `${room.label}的使用與家具需求`;
  element.copyRoomSource.innerHTML = [
    '<option value="">選擇已填寫空間</option>',
    ...state.rooms
      .filter((item) => item.id !== room.id && state.roomAnswers[item.id]?.confirmed)
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`),
  ].join("");
  element.roomUseOptions.innerHTML = template.uses.map((label) =>
    `<label><input type="checkbox" value="${escapeHtml(label)}"/><span>${escapeHtml(label)}</span></label>`
  ).join("");
  element.roomFurnitureOptions.innerHTML = template.furniture.map((label) =>
    `<label><input type="checkbox" value="${escapeHtml(label)}"/><span>${escapeHtml(label)}</span></label>`
  ).join("");
  [
    [element.roomWallPreference, materialOptions.wall],
    [element.roomFloorPreference, materialOptions.floor],
    [element.roomFurnitureMaterialPreference, materialOptions.furniture],
    [element.roomColorPreference, materialOptions.color],
    [element.roomFinishPreference, materialOptions.finish],
  ].forEach(([select, options]) => {
    select.innerHTML = options.map((option) =>
      `<option value="${escapeHtml(option.value)}" data-image-key="${escapeHtml(option.imageKey)}">${escapeHtml(option.label)}</option>`
    ).join("");
  });
  const existing = state.roomAnswers[roomId];
  renderRoomAxes(room, existing);
  if (existing) {
    $$("input", element.roomUseOptions).forEach((input) => { input.checked = (existing.uses || []).includes(input.value); });
    if (!(existing.uses || []).length) {
      const firstUse = $("input", element.roomUseOptions);
      if (firstUse) firstUse.checked = true;
    }
    $$("input", element.roomFurnitureOptions).forEach((input) => { input.checked = (existing.furniture || []).includes(input.value); });
    element.roomUseNote.value = existing.stageNotes?.uses || "";
    element.roomFurnitureNote.value = existing.stageNotes?.furniture || "";
    element.roomPersonalNeeds.value =
      existing?.personalNeeds === "無" ? "" : (existing?.personalNeeds || "");
    setSelectedValues(element.roomWallPreference, existing.materialPreferences?.wall);
    setSelectedValues(element.roomFloorPreference, existing.materialPreferences?.floor);
    setSelectedValues(element.roomFurnitureMaterialPreference, existing.materialPreferences?.furniture);
    setSelectedValues(element.roomColorPreference, existing.materialPreferences?.color);
    setSelectedValues(element.roomFinishPreference, existing.materialPreferences?.finish);
    element.roomMaterialCuts.value = (existing.materialPreferences?.cuts || []).join("\n");
  } else {
    const firstUse = $("input", element.roomUseOptions);
    if (firstUse) firstUse.checked = true;
    element.roomUseNote.value = "";
    element.roomFurnitureNote.value = "";
    element.roomPersonalNeeds.value = "";
    setSelectedValues(element.roomWallPreference, []);
    setSelectedValues(element.roomFloorPreference, []);
    setSelectedValues(element.roomFurnitureMaterialPreference, []);
    setSelectedValues(element.roomColorPreference, []);
    setSelectedValues(element.roomFinishPreference, []);
    element.roomMaterialCuts.value = "";
  }
  state.activeRoomQuestionIndex = 0;
  renderQuestionRooms();
  renderRequirementsOverlay();
  renderRoomIntegratedSummary();
  renderRoomQuestionStep();
  if (draftCaptured) scheduleSave("requirements");
}

function resolveActiveRoomRequirement(keepExisting = false) {
  const roomId = state.activeQuestionRoomId;
  if (!roomId) return;
  if (keepExisting) {
    if (!state.keepExistingRoomIds.includes(roomId)) state.keepExistingRoomIds.push(roomId);
    const room = state.rooms.find((item) => item.id === roomId);
    state.roomAnswers[roomId] = {
      schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
      confirmed: false,
      keepExisting: true,
      roomIdentity: questionnaireRoomIdentity(room),
    };
  } else {
    const answer = readActiveDesignerRoomAnswer({ confirmed: true });
    const room = state.rooms.find((item) => item.id === roomId);
    const template = roomQuestionTemplate(room?.type);
    const questionnaireAxes = [
      ...template.axes,
      ...roomTechnicalAxes(room?.type),
    ];
    const missingAxis = questionnaireAxes.find((axisDefinition) => {
      return axisDefinition.required && !answer.axes[axisDefinition.id];
    });
    if (missingAxis) {
      element.requirementsError.textContent = `請完成「${missingAxis.label}」，或選擇跳過此房間。`;
      const missingIndex = roomQuestionStages().findIndex(
        (stage) => (
          stage.dataset.roomAxis === missingAxis.id
          || (
            stage.dataset.roomQuestionStage === "technical"
            && roomTechnicalAxes(room?.type)
              .some((axisDefinition) => axisDefinition.id === missingAxis.id)
          )
        )
      );
      renderRoomQuestionStep(missingIndex);
      return;
    }
    const ceilingResult = validateCeilingPreference({
      axisDefinition: roomTechnicalAxes(room?.type)
        .find((axisDefinition) => axisDefinition.id === "ceiling"),
      value: answer.axes.ceiling,
      roomHeightCm: Number(
        state.confirmedFloorplan?.floorplan?.room_height_cm
        || state.sceneData?.floorplan?.room_height_cm
        || 270
      ),
      minimumFinishedHeightCm: state.minimumFinishedHeightCm,
    });
    if (!ceilingResult.ready) {
      element.requirementsError.textContent =
        `此天花方案預估完成淨高 ${ceilingResult.finishedHeightCm} 公分，低於設計師設定的 `
        + `${ceilingResult.minimumFinishedHeightCm} 公分，不能確認此房間。`;
      const technicalIndex = roomQuestionStages().findIndex(
        (stage) => stage.dataset.roomQuestionStage === "technical"
      );
      renderRoomQuestionStep(technicalIndex);
      return;
    }
    element.requirementsError.textContent = "";
    state.keepExistingRoomIds = state.keepExistingRoomIds.filter((id) => id !== roomId);
    state.roomAnswers[roomId] = answer;
  }
  const gate = requirementsGate({
    basic: { confirmed: state.basicConfirmed },
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  refreshQuestionnaireStatus();
  renderQuestionRooms();
  const nextRoom = state.rooms.find((room) => gate.unresolvedRoomIds.includes(room.id));
  if (nextRoom) selectQuestionRoom(nextRoom.id, { captureDraft: false });
  invalidateDownstreamFrom("requirements", "房間需求已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
}

function currentClientBrief() {
  return buildClientBrief({
    basicAnswers: state.basicAnswers,
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    designerNotes: state.designerQuestionnaireNotes,
  });
}

function currentQuestionnaireDocument() {
  return buildQuestionnaireDocument({
    projectId: state.projectId || "",
    basicAnswers: state.basicAnswers,
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    designerNotes: state.designerQuestionnaireNotes,
  });
}

function downloadQuestionnaireJson() {
  const documentPayload = currentQuestionnaireDocument();
  const blob = new Blob(
    [JSON.stringify(documentPayload, null, 2)],
    { type: "application/json;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `roompilot-questionnaire-${state.projectId || "project"}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

async function createQuestionnaireInvite() {
  if (!state.projectId) {
    element.questionnaireInviteOutput.textContent = "請先建立專案。";
    return;
  }
  try {
    const result = await api(`/api/projects/${state.projectId}/questionnaire-invite`, {
      method: "POST",
    });
    const absoluteUrl = new URL(result.questionnaire_url, location.origin).href;
    state.activeQuestionnaireInviteToken = result.invite_token;
    const expiresAt = new Date(result.expires_at).toLocaleString("zh-TW");
    element.questionnaireInviteOutput.innerHTML =
      `<a href="${escapeHtml(absoluteUrl)}" target="_blank" rel="noopener">${escapeHtml(absoluteUrl)}</a>`
      + `<small>有效至 ${escapeHtml(expiresAt)}</small>`
      + '<button type="button" class="secondary-action" data-revoke-questionnaire-invite>撤銷此連結</button>';
  } catch (error) {
    element.questionnaireInviteOutput.textContent = errorMessage(error);
  }
}

async function revokeActiveQuestionnaireInvite() {
  const inviteToken = state.activeQuestionnaireInviteToken;
  if (!state.projectId || !inviteToken) return;
  try {
    await api(
      `/api/projects/${state.projectId}/questionnaire-invite/${inviteToken}`,
      { method: "DELETE" },
    );
    state.activeQuestionnaireInviteToken = null;
    element.questionnaireInviteOutput.textContent = "客戶問卷連結已撤銷。";
  } catch (error) {
    element.questionnaireInviteOutput.textContent = errorMessage(error);
  }
}

async function revokeAllQuestionnaireInvites() {
  if (!state.projectId) return;
  try {
    const result = await api(
      `/api/projects/${state.projectId}/questionnaire-invites`,
      { method: "DELETE" },
    );
    state.activeQuestionnaireInviteToken = null;
    element.questionnaireInviteOutput.textContent =
      result.revoked > 0
        ? `已撤銷 ${result.revoked} 個客戶問卷連結。`
        : "目前沒有可撤銷的客戶問卷連結。";
  } catch (error) {
    element.questionnaireInviteOutput.textContent = errorMessage(error);
  }
}

function renderQuestionnaireWarning() {
  state.questionnaireWarnings = collectQuestionnaireWarnings({
    rooms: state.rooms,
    answers: state.roomAnswers,
  });
  state.activeQuestionnaireWarningIndex = Math.min(
    Math.max(0, state.activeQuestionnaireWarningIndex),
    Math.max(0, state.questionnaireWarnings.length - 1),
  );
  const warning = state.questionnaireWarnings[state.activeQuestionnaireWarningIndex];
  element.questionnaireWarningCard.hidden = !warning;
  if (!warning) return;
  element.questionnaireWarningPosition.textContent = warning.position;
  element.questionnaireWarningRoom.textContent = warning.roomLabel;
  element.questionnaireWarningReason.textContent = warning.reason;
  $("#previous-questionnaire-warning").disabled = state.activeQuestionnaireWarningIndex <= 0;
  $("#next-questionnaire-warning").disabled =
    state.activeQuestionnaireWarningIndex >= state.questionnaireWarnings.length - 1;
}

function refreshQuestionnaireStatus() {
  const completion = questionnaireCompletion({
    basicAnswers: state.basicAnswers,
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  element.requirementsProgress.textContent = state.basicConfirmed
    ? `房間需求 ${completion.completedRooms} / ${completion.totalRooms}`
    : "基本問卷";
  element.questionnaireIncompleteList.innerHTML = completion.incomplete.length
    ? completion.incomplete.map((item) => `
        <button type="button"
          data-incomplete-kind="${escapeHtml(item.kind)}"
          data-incomplete-id="${escapeHtml(item.roomId || item.questionId)}">
          ${escapeHtml(item.label)}
        </button>
      `).join("")
    : "<span>全部完成</span>";
  $("#jump-next-incomplete").hidden = completion.incomplete.length === 0;
  $("#keep-unfilled-rooms-existing").hidden =
    !state.basicConfirmed
    || !completion.incomplete.some((item) => item.kind === "room");
  element.clientBriefPreview.textContent =
    JSON.stringify(currentQuestionnaireDocument(), null, 2);
  renderQuestionnaireWarning();
}

function jumpToNextIncomplete() {
  const completion = questionnaireCompletion({
    basicAnswers: state.basicAnswers,
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  const next = completion.nextIncomplete;
  if (!next) {
    element.requirementsError.textContent = "問卷已全部完成，可以產生 2D 配置。";
    return;
  }
  if (next.kind === "basic") {
    element.questionnaireRoomLocator.hidden = true;
    $("#whole-house-questionnaire").hidden = false;
    $("#room-questionnaire").hidden = true;
    renderBasicQuestionStep(
      WHOLE_HOUSE_QUESTIONS.findIndex((question) => question.id === next.questionId)
    );
    return;
  }
  $("#whole-house-questionnaire").hidden = true;
  $("#room-questionnaire").hidden = false;
  selectQuestionRoom(next.roomId);
}

function copySelectedRoomAnswer() {
  const sourceRoomId = element.copyRoomSource.value;
  const copied = cloneRoomAnswer(state.roomAnswers[sourceRoomId], { sourceRoomId });
  if (!copied || !state.activeQuestionRoomId) {
    element.requirementsError.textContent = "請先選擇一個已完成的空間。";
    return;
  }
  state.roomAnswers[state.activeQuestionRoomId] = copied;
  selectQuestionRoom(state.activeQuestionRoomId, {
    captureDraft: false,
    forceReload: true,
  });
  element.requirementsError.textContent = "已複製選項，請修改差異並按「確認此房間」才會寫入正式需求。";
}

function randomizeRoomInspiration() {
  $$("[data-room-axis]", element.roomAxisOptions).forEach((host) => {
    const choices = $$("input", host);
    const choice = choices[Math.floor(Math.random() * choices.length)];
    if (choice) choice.checked = true;
  });
  renderRoomIntegratedSummary();
  element.requirementsError.textContent = "這只是隨機靈感；按「確認此房間」後才會寫入正式需求。";
}

function keepUnfilledRoomsExisting() {
  const unresolvedRoomIds = requirementsGate({
    basic: { confirmed: state.basicConfirmed },
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  }).unresolvedRoomIds;
  if (!unresolvedRoomIds.length) {
    element.requirementsError.textContent = "所有房間都已處理。";
    return;
  }
  state.keepExistingRoomIds = [
    ...new Set([...state.keepExistingRoomIds, ...unresolvedRoomIds]),
  ];
  unresolvedRoomIds.forEach((roomId) => {
    const room = state.rooms.find((candidate) => candidate.id === roomId);
    if (!room) return;
    state.roomAnswers[roomId] = {
      schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
      confirmed: false,
      keepExisting: true,
      roomIdentity: questionnaireRoomIdentity(room),
      axes: {},
    };
  });
  element.requirementsError.textContent = `已將 ${unresolvedRoomIds.length} 個未填寫房間標示為維持現狀。`;
  renderQuestionRooms();
  renderRequirementsOverlay();
  refreshQuestionnaireStatus();
  invalidateDownstreamFrom("requirements", "房間需求已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
}

function surfaceLabel(surface) {
  return surface.name_zh
    || surface.display_name_zh
    || surface.material_group
    || surface.surface_id;
}

function surfaceOptions(usage) {
  return (state.surfaceCatalog?.surfaces || []).filter(
    (surface) => surface.surface_id
      && surface.texture_url
      && Array.isArray(surface.usage)
      && surface.usage.includes(usage),
  );
}

function renderSurfaceSelect(select, usage, selectedId = "", roomType = "") {
  if (!select) return;
  const options = surfaceOptions(usage).filter((surface) => (
    !roomType || isSurfaceEligibleForRoom(surface, usage, roomType)
  ));
  select.innerHTML = options.map((surface) => (
    `<option value="${escapeHtml(surface.surface_id)}">${escapeHtml(surfaceLabel(surface))}</option>`
  )).join("");
  if (options.some((surface) => surface.surface_id === selectedId)) {
    select.value = selectedId;
  }
}

function renderWorkbenchMaterialControls() {
  const activeRoom = state.activeLayoutRoomId !== "all"
    ? state.rooms.find((room) => room.id === state.activeLayoutRoomId)
    : null;
  const roomPreferences = state.activeLayoutRoomId !== "all"
    ? state.designPreferences.rooms?.[state.activeLayoutRoomId]?.surfaceOverride
    : null;
  const selectedPreferences = {
    ...state.designPreferences.wholeHouse,
    ...(roomPreferences || {}),
  };
  renderSurfaceSelect(
    element.workbenchWallSurface,
    "wall",
    selectedPreferences.wallSurfaceId,
    activeRoom?.type,
  );
  renderSurfaceSelect(
    element.workbenchFloorSurface,
    "floor",
    selectedPreferences.floorSurfaceId,
    activeRoom?.type,
  );
  element.workbenchWallColor.value =
    selectedPreferences.wallColor || "#f4efe4";
  element.workbenchFloorColor.value =
    selectedPreferences.floorColor || "#c9a77d";
  const boundary = state.activeLayoutRoomId !== "all"
    ? state.designPreferences.rooms?.[state.activeLayoutRoomId]?.materialBoundary
    : null;
  element.workbenchCutSurface.value = boundary?.surface || "floor";
  element.workbenchCutWallFace.value = boundary?.wallFace || "north";
  element.workbenchCutWallFace.closest("label").hidden =
    element.workbenchCutSurface.value !== "wall";
  $("#workbench-cut-direction").value = boundary?.direction || "vertical";
  $("#workbench-cut-position").value = String(
    Math.round(materialBoundaryRatio(boundary) * 100),
  );
  renderSurfaceSelect(
    element.workbenchSecondarySurface,
    element.workbenchCutSurface.value,
    boundary?.secondarySurfaceId,
    activeRoom?.type,
  );
  element.workbenchSecondaryColor.value = boundary?.secondaryColor || "#8b684b";
  $("#workbench-cut-status").textContent = state.activeLayoutRoomId === "all"
    ? "先在上方選一個房間；全屋模式不建立切割。"
    : boundary
      ? `此房間已有${boundary.surface === "wall" ? "牆面" : "地板"}`
        + `${boundary.direction === "horizontal" ? "前後" : "左右"}切割，位置 ${Math.round(materialBoundaryRatio(boundary) * 100)}%。`
      : "此房間尚未建立材質切割。";
}

async function ensureDesignAssets() {
  if ((state.surfaceCatalog?.surfaces || []).length) return;
  try {
    const payload = await api("/api/scene/bootstrap");
    state.surfaceCatalog = payload.surface_catalog || { surfaces: [] };
  } catch (error) {
    console.warn(error);
    state.surfaceCatalog = { surfaces: [] };
  }
}

function selectedStylePack() {
  return STYLE_PACKS.find((pack) => pack.id === state.designPreferences.styleId) || null;
}

function surfacePreviewUrl(surface) {
  return String(surface?.preview_url || surface?.texture_url || "");
}

function surfaceById(surfaceId) {
  return (state.surfaceCatalog?.surfaces || []).find(
    (surface) => surface.surface_id === surfaceId,
  ) || null;
}

function roomDesignPreferences(roomId = state.activeDesignRoomId) {
  const saved = state.designPreferences.rooms?.[roomId] || {};
  const legacyMaterialPreferences = saved.materialPreferences || (
    saved.wall || saved.floor || saved.furniture || saved.color || saved.finish
      ? saved
      : null
  );
  return {
    ...saved,
    materialPreferences: legacyMaterialPreferences || {},
    surfaceOverride: {
      wallSurfaceId: saved.surfaceOverride?.wallSurfaceId
        || state.designPreferences.wholeHouse?.wallSurfaceId
        || "",
      floorSurfaceId: saved.surfaceOverride?.floorSurfaceId
        || state.designPreferences.wholeHouse?.floorSurfaceId
        || "",
      wallColor: saved.surfaceOverride?.wallColor
        || state.designPreferences.wholeHouse?.wallColor
        || "#f4efe4",
      floorColor: saved.surfaceOverride?.floorColor
        || state.designPreferences.wholeHouse?.floorColor
        || "#c9a77d",
    },
  };
}

function designRoomMaterialCompletion(room, preferences = null) {
  if (!room) return roomMaterialCompletion(preferences || {});
  return roomMaterialCompletion(
    preferences || roomDesignPreferences(room.id),
    {
      roomType: room.type,
      surfaceLookup: surfaceById,
    },
  );
}

function updateRoomDesignPreferences(roomId, updater) {
  if (!roomId) return;
  const current = roomDesignPreferences(roomId);
  const updated = typeof updater === "function" ? updater(current) : updater;
  state.designPreferences = normalizeDesignPreferences({
    ...state.designPreferences,
    rooms: {
      ...(state.designPreferences.rooms || {}),
      [roomId]: updated,
    },
  });
}

function invalidateGeneratedSchemesAfterDesignChange() {
  const hadGeneratedOutput = Boolean(
    state.layoutSchemeSet
    || state.sceneData
    || state.workflow?.toJSON?.().completed?.includes("design_preferences"),
  );
  state.designPreferences = normalizeDesignPreferences({
    ...state.designPreferences,
    confirmed: false,
    materialsConfirmed: false,
  });
  invalidateDownstreamFrom(
    "design_preferences",
    hadGeneratedOutput
      ? "材質或房間偏好已修改；原方案已失效，請重新完成 Step 6 產生方案。"
      : "",
  );
}

function stylePaletteMarkup(colors = []) {
  return `
    <span class="rp-style-swatches rp-style-palette" aria-label="色彩方向">
      ${colors.map((color) => (
        `<i style="--swatch:${escapeHtml(color)}" title="${escapeHtml(color)}"></i>`
      )).join("")}
    </span>
  `;
}

function renderDesignStyleCards() {
  if (!element.designStyleGrid || !element.designStyleVariantGrid) return;
  const groups = groupStylePacks(STYLE_PACKS);
  const selectedPack = selectedStylePack();
  const selectedFamily = state.activeDesignStyleFamily
    || selectedPack?.styleId
    || groups[0]?.id
    || "";
  state.activeDesignStyleFamily = selectedFamily;
  element.designStyleGrid.innerHTML = groups.map((group) => {
    const representative = group.packs.find((pack) => pack.id === selectedPack?.id)
      || group.packs[0];
    const active = group.id === selectedFamily;
    return `
      <button type="button" data-design-style-family="${escapeHtml(group.id)}"
        data-testid="material-style-card" aria-pressed="${active}"
        class="${active ? "is-active" : ""}">
        <img src="${escapeHtml(representative.sourceImage)}"
          alt="${escapeHtml(group.label)}空間參考" loading="lazy" />
        <strong>${escapeHtml(group.label)}</strong>
        <small>${active ? "正在比較這個方向" : "查看 3 組色彩"}</small>
        ${stylePaletteMarkup(representative.palette)}
      </button>
    `;
  }).join("");
  const variants = groups.find((group) => group.id === selectedFamily)?.packs || [];
  element.designStyleVariantGrid.innerHTML = variants.map((pack) => {
    const active = pack.id === selectedPack?.id;
    return `
      <button type="button" data-design-style="${escapeHtml(pack.id)}"
        data-testid="material-colorway-card" aria-pressed="${active}"
        class="${active ? "is-active" : ""}">
        <img src="${escapeHtml(pack.sourceImage)}"
          alt="${escapeHtml(pack.styleLabel)}${escapeHtml(pack.name)}空間參考" loading="lazy" />
        <strong>${escapeHtml(pack.name)}</strong>
        <small>${active ? "目前色彩方向" : "套用這組方向"}</small>
        ${stylePaletteMarkup(pack.palette)}
      </button>
    `;
  }).join("");
}

function rankedSurfaces(
  usage,
  roomType = "living_room",
  limit = 36,
  styleId = selectedStylePack()?.id || state.designPreferences.styleId,
) {
  const stylePack = STYLE_PACKS.find((pack) => pack.id === styleId)
    || selectedStylePack();
  return rankSurfaceCatalog({
    surfaces: state.surfaceCatalog?.surfaces || [],
    usage,
    roomType,
    styleId,
    stylePack,
    styleProfiles: state.surfaceCatalog?.style_surface_profiles || {},
    limit,
  });
}

function defaultSurfaceFor(usage, styleId) {
  return rankedSurfaces(usage, "living_room", 200, styleId)[0]
    || surfaceOptions(usage)[0]
    || null;
}

function applyDesignStylePack(pack) {
  if (!pack) return;
  state.activeDesignMaterialTarget = "primary";
  state.activeDesignMaterialPage = 1;
  state.designPreferences = normalizeDesignPreferences(applyStylePackPreference({
    preferences: state.designPreferences,
    stylePack: pack,
  }));
  const wholeHouse = state.designPreferences.wholeHouse;
  state.activeDesignStyleFamily = pack.styleId;
  renderSurfaceSelect(element.designWallSurface, "wall", wholeHouse.wallSurfaceId);
  renderSurfaceSelect(element.designFloorSurface, "floor", wholeHouse.floorSurfaceId);
  element.designWallColor.value = wholeHouse.wallColor;
  element.designFloorColor.value = wholeHouse.floorColor;
  renderDesignStyleCards();
  renderDesignBaselineSummary();
  renderDesignRoomLocator();
  renderDesignMaterialControls();
  renderDesignMaterialCards();
  renderDesignCutEditor();
  invalidateGeneratedSchemesAfterDesignChange();
  scheduleSave("design_preferences");
}

function renderDesignBaselineSummary() {
  if (!element.designBaselineSummary) return;
  const pack = selectedStylePack();
  const wall = surfaceById(state.designPreferences.wholeHouse?.wallSurfaceId);
  const floor = surfaceById(state.designPreferences.wholeHouse?.floorSurfaceId);
  if (!pack) {
    element.designBaselineSummary.textContent = "先選一張風格色彩圖，系統才會建立全屋材質基準。";
    return;
  }
  element.designBaselineSummary.innerHTML = `
    <strong>${escapeHtml(pack.styleLabel)} · ${escapeHtml(pack.name)}</strong>
    <span>牆面：${escapeHtml(surfaceLabel(wall || {}) || "待選")}</span>
    <span>地板：${escapeHtml(surfaceLabel(floor || {}) || "待選")}</span>
    <small>此處是未確認房間的起點；每個房間仍可改成不同材質。</small>
  `;
}

function renderDesignRoomLocator() {
  if (!element.designRoomNav || !element.designRoomProgress) return;
  const completed = state.rooms.filter((room) => (
    designRoomMaterialCompletion(room).complete
  )).length;
  element.designRoomProgress.textContent = `${completed} / ${state.rooms.length}`;
  element.designRoomNav.innerHTML = state.rooms.map((room) => {
    const active = room.id === state.activeDesignRoomId;
    const complete = designRoomMaterialCompletion(room).complete;
    return `
      <button type="button" data-design-room="${escapeHtml(room.id)}"
        data-complete="${complete}" aria-pressed="${active}"
        class="${active ? "is-active" : ""} ${complete ? "is-complete" : ""}">
        <span>${escapeHtml(room.label)}</span>
        <small>${complete ? "已確認" : "待確認"}</small>
      </button>
    `;
  }).join("");
  if (!element.designRoomPlanOverlay || !element.designRoomPlanImage?.naturalWidth) return;
  element.designRoomPlanOverlay.innerHTML = state.rooms.map((room) => {
    const points = (room.polygon_cm || []).map(cmToPixel);
    if (points.length < 3) return "";
    const center = questionnairePolygonLabelPoint(points);
    const active = room.id === state.activeDesignRoomId;
    const complete = designRoomMaterialCompletion(room).complete;
    return `
      <g data-design-room="${escapeHtml(room.id)}" role="button" tabindex="0"
        aria-label="選擇${escapeHtml(room.label)}，${complete ? "已確認" : "待確認"}">
        <polygon points="${roomPolygonSvg(room)}"
          fill="${active ? "rgba(47,111,135,.30)" : complete ? "rgba(36,107,85,.18)" : "rgba(36,107,85,.06)"}"
          stroke="${active ? "#2f6f87" : complete ? "#246b55" : "#87938d"}"
          stroke-width="${active ? 6 : 3}"/>
        <text x="${center.x}" y="${center.y}" text-anchor="middle"
          dominant-baseline="central">${escapeHtml(room.label)}</text>
      </g>
    `;
  }).join("");
}

function selectedMaterialId(roomPreferences, usage) {
  if (state.activeDesignMaterialTarget === "secondary") {
    return roomPreferences.materialBoundary?.surface === usage
      ? roomPreferences.materialBoundary.secondarySurfaceId
      : "";
  }
  return usage === "wall"
    ? roomPreferences.surfaceOverride?.wallSurfaceId
    : roomPreferences.surfaceOverride?.floorSurfaceId;
}

function renderFurnitureMaterialCards(room) {
  const options = materialPreferenceOptions(room.type).furniture || [];
  const selected = new Set(
    state.roomAnswers[room.id]?.materialPreferences?.furniture || [],
  );
  renderDesignMaterialPagination(null);
  element.designMaterialRecommendation.innerHTML =
    "<strong>家具材質方向</strong>會轉成 RAG 篩選條件；目前圖樣為方向示意，正式家具仍以可用 GLB 為準。";
  element.designMaterialCardGrid.innerHTML = options.map((option) => `
    <button type="button" data-furniture-material="${escapeHtml(option.value)}"
      data-testid="material-card" aria-pressed="${selected.has(option.value)}"
      class="${selected.has(option.value) ? "is-selected" : ""}">
      <span class="rp-furniture-material-sample" data-material-sample="${escapeHtml(option.value)}"
        aria-hidden="true"></span>
      <strong>${escapeHtml(option.label)}</strong>
      <small>材質方向示意 · RAG 待接上</small>
    </button>
  `).join("");
}

function renderDesignMaterialPagination(pagination) {
  if (!element.designMaterialPagination) return;
  const visible = Boolean(pagination);
  element.designMaterialPagination.hidden = !visible;
  if (!visible) return;
  state.activeDesignMaterialPage = pagination.page;
  element.previousDesignMaterialPage.disabled = !pagination.hasPrevious;
  element.nextDesignMaterialPage.disabled = !pagination.hasNext;
  element.designMaterialPageStatus.textContent =
    `第 ${pagination.page} / ${pagination.totalPages} 頁 · 共 ${pagination.totalItems} 款`;
  element.designMaterialPageNumbers.innerHTML = Array.from(
    { length: pagination.totalPages },
    (_, index) => index + 1,
  ).map((page) => `
    <button type="button" data-design-material-page="${page}"
      aria-label="前往第 ${page} 頁" aria-current="${page === pagination.page ? "page" : "false"}"
      class="${page === pagination.page ? "is-active" : ""}">${page}</button>
  `).join("");
}

function renderDesignMaterialCards() {
  if (!element.designMaterialCardGrid || !element.designMaterialRecommendation) return;
  const room = state.rooms.find((item) => item.id === state.activeDesignRoomId);
  if (!room) {
    element.designMaterialCardGrid.innerHTML = "";
    return;
  }
  const furnitureMode = state.activeDesignMaterialTab === "furniture";
  element.designMaterialTarget.closest(".rp-material-target-row").hidden = furnitureMode;
  if (furnitureMode) {
    renderFurnitureMaterialCards(room);
    return;
  }
  const usage = state.activeDesignMaterialTab === "wall" ? "wall" : "floor";
  const roomPreferences = roomDesignPreferences(room.id);
  const selectedId = selectedMaterialId(roomPreferences, usage);
  let surfaces = rankedSurfaces(usage, room.type, 36);
  const selectedSurface = surfaceById(selectedId);
  const selectedSurfaceEligible = isSurfaceEligibleForRoom(
    selectedSurface,
    usage,
    room.type,
  );
  if (
    selectedSurface
    && selectedSurfaceEligible
    && !surfaces.some((surface) => surface.surface_id === selectedSurface.surface_id)
  ) {
    surfaces = [selectedSurface, ...surfaces].slice(0, 36);
  }
  const pagination = paginateSurfaceCatalog(surfaces, {
    page: state.activeDesignMaterialPage,
    pageSize: 6,
  });
  renderDesignMaterialPagination(pagination);
  const recommended = surfaces.find((surface) => surface.recommended) || surfaces[0];
  const pack = selectedStylePack();
  const ineligibleSelectionMessage = selectedId && !selectedSurfaceEligible
    ? `<strong>需重新選擇：</strong>${escapeHtml(surfaceLabel(selectedSurface || {}) || selectedId)}
       不適用於${escapeHtml(room.label)}的${usage === "floor" ? "地板" : "牆面"}，
       已從清單排除。請改選下方可用材質。`
    : "";
  const recommendationMessage = recommended
    ? `<strong>${escapeHtml(pack?.styleLabel || "目前風格")}・${escapeHtml(pack?.name || "目前色卡")}推薦：</strong>
       已依色卡的色調、材質方向與${escapeHtml(room.label)}用途排序。
       ${escapeHtml(recommended.recommendationReason)}
       <small>這是風格與空間類型排序，不代表產品性能；施工前須查實品規格。</small>`
    : "目前沒有可顯示的材質資料。";
  element.designMaterialRecommendation.innerHTML = [
    ineligibleSelectionMessage,
    recommendationMessage,
  ].filter(Boolean).join("<br />");
  element.designMaterialCardGrid.innerHTML = pagination.items.map((surface) => {
    const preview = surfacePreviewUrl(surface);
    const selected = selectedId === surface.surface_id;
    const local = preview.startsWith("/static/");
    return `
      <button type="button" data-design-surface-id="${escapeHtml(surface.surface_id)}"
        data-testid="material-card" data-recommended="${surface.recommended === true}"
        aria-pressed="${selected}" class="${selected ? "is-selected" : ""} ${surface.recommended ? "is-recommended" : ""}">
        <span class="rp-material-preview-wrap">
          <img src="${escapeHtml(preview)}" alt="${escapeHtml(surfaceLabel(surface))}材質圖"
            loading="lazy" data-material-preview />
          <span class="rp-material-image-state">${local ? "本機材質圖" : "需連網載入"}</span>
        </span>
        <strong>${escapeHtml(surfaceLabel(surface))}</strong>
        <span class="rp-material-card-meta">
          ${escapeHtml(surface.material_group || surface.category || "")}
          ${surface.color_zh ? ` · ${escapeHtml(surface.color_zh)}` : ""}
        </span>
        <small>${surface.recommended ? escapeHtml(surface.recommendationReason) : "可選用；請再核對實品。"}</small>
      </button>
    `;
  }).join("");
  $$("img[data-material-preview]", element.designMaterialCardGrid).forEach((image) => {
    image.addEventListener("error", () => {
      const card = image.closest("button");
      card.disabled = true;
      card.dataset.imageUnavailable = "true";
      card.querySelector(".rp-material-image-state").textContent = "圖片目前無法載入";
      image.alt = "材質圖片載入失敗";
    }, { once: true });
  });
}

function materialBoundaryDisplayPoint(point, room, surface) {
  if (surface === "wall") {
    return { x: point.x * 1000, y: point.y * 600 };
  }
  const pixels = room.polygon_cm.map(cmToPixel);
  const minX = Math.min(...pixels.map((item) => item.x));
  const maxX = Math.max(...pixels.map((item) => item.x));
  const minY = Math.min(...pixels.map((item) => item.y));
  const maxY = Math.max(...pixels.map((item) => item.y));
  return {
    x: minX + point.x * (maxX - minX),
    y: minY + point.y * (maxY - minY),
  };
}

function materialBoundaryRatio(boundary) {
  return Math.max(
    0,
    Math.min(1, Number(boundary?.splitRatio ?? boundary?.ratio ?? 0.5)),
  );
}

function materialBoundaryNormalizedPoints(boundary) {
  if (Array.isArray(boundary?.points) && boundary.points.length >= 2) {
    return boundary.points.slice(0, 2);
  }
  const ratio = materialBoundaryRatio(boundary);
  const displayRatio = boundary?.direction === "horizontal"
    ? 1 - ratio
    : ratio;
  return boundary?.direction === "horizontal"
    ? [{ x: 0.05, y: displayRatio }, { x: 0.95, y: displayRatio }]
    : [{ x: displayRatio, y: 0.05 }, { x: displayRatio, y: 0.95 }];
}

function renderDesignCutEditor() {
  if (!element.designCutCanvas || !element.designCutSummary) return;
  const room = state.rooms.find((item) => item.id === state.activeDesignRoomId);
  if (!room) return;
  const roomPreferences = roomDesignPreferences(room.id);
  const boundary = roomPreferences.materialBoundary;
  const surface = state.designCutSurface === "wall" ? "wall" : "floor";
  const floorMode = surface === "floor";
  element.designCutFloorImage.hidden = !floorMode;
  $("#design-cut-wall-face-label").hidden = floorMode;
  $$("[data-design-cut-surface]").forEach((button) => {
    const active = button.dataset.designCutSurface === surface;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const { imageWidth, imageHeight } = planGeometry();
  element.designCutCanvas.setAttribute(
    "viewBox",
    floorMode ? `0 0 ${imageWidth} ${imageHeight}` : "0 0 1000 600",
  );
  element.designCutCanvas.setAttribute(
    "aria-label",
    `${room.label}${floorMode ? "地板平面" : "牆面正視圖"}材質分界線繪製區`,
  );
  element.designCutCanvas.setAttribute("preserveAspectRatio", floorMode ? "xMidYMid meet" : "none");
  const activeBoundary = boundary?.surface === surface ? boundary : null;
  const points = state.designCutDraftStart && state.designCutDraftEnd
    ? [state.designCutDraftStart, state.designCutDraftEnd]
    : activeBoundary && activeBoundary.mode !== "pending"
      ? materialBoundaryNormalizedPoints(activeBoundary)
      : null;
  const line = points?.length === 2
    ? points.map((point) => materialBoundaryDisplayPoint(point, room, surface))
    : null;
  const roomPolygon = floorMode
    ? `<polygon class="rp-cut-room-outline" points="${roomPolygonSvg(room)}" />`
    : `
      <rect class="rp-wall-elevation" x="45" y="45" width="910" height="510" rx="4" />
      <text x="500" y="82" text-anchor="middle" class="rp-wall-face-label">
        ${escapeHtml(room.label)} · ${escapeHtml(element.designCutWallFace.selectedOptions[0]?.textContent || "牆面")}正視圖
      </text>
    `;
  element.designCutCanvas.innerHTML = `
    ${roomPolygon}
    ${line ? `
      <line class="rp-cut-boundary-line" x1="${line[0].x}" y1="${line[0].y}"
        x2="${line[1].x}" y2="${line[1].y}" />
      <circle class="rp-cut-boundary-handle" cx="${line[0].x}" cy="${line[0].y}" r="9" />
      <circle class="rp-cut-boundary-handle" cx="${line[1].x}" cy="${line[1].y}" r="9" />
    ` : ""}
  `;
  if (!activeBoundary || activeBoundary.mode === "pending") {
    element.designCutSummary.textContent =
      activeBoundary?.secondarySurfaceId
        ? `第二材質已選好；請在${floorMode ? "地板平面" : "牆面正視圖"}拖曳一條分界線。`
        : `尚未建立${floorMode ? "地板" : "牆面"}分界；先選第二材質，再在圖面拖曳。`;
    return;
  }
  const primary = surfaceById(activeBoundary.primarySurfaceId);
  const secondary = surfaceById(activeBoundary.secondarySurfaceId);
  element.designCutSummary.textContent =
    `${floorMode ? "地板" : `${element.designCutWallFace.selectedOptions[0]?.textContent || "牆面"}`}：`
    + `${surfaceLabel(primary || {}) || "主要材質"}／${surfaceLabel(secondary || {}) || "第二材質"}；`
    + "分界可重新拖曳。";
}

function designCutPoint(event) {
  const room = state.rooms.find((item) => item.id === state.activeDesignRoomId);
  if (!room) return null;
  if (state.designCutSurface === "wall") {
    const rect = element.designCutCanvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }
  const imageRect = imageContentRect(element.designCutFloorImage);
  if (!imageRect.width || !imageRect.height) return null;
  const imagePointPx = {
    x: Math.max(0, Math.min(imageRect.width, event.clientX - imageRect.left))
      * element.designCutFloorImage.naturalWidth / imageRect.width,
    y: Math.max(0, Math.min(imageRect.height, event.clientY - imageRect.top))
      * element.designCutFloorImage.naturalHeight / imageRect.height,
  };
  const pixels = room.polygon_cm.map(cmToPixel);
  const minX = Math.min(...pixels.map((point) => point.x));
  const maxX = Math.max(...pixels.map((point) => point.x));
  const minY = Math.min(...pixels.map((point) => point.y));
  const maxY = Math.max(...pixels.map((point) => point.y));
  return {
    x: Math.max(0, Math.min(1, (imagePointPx.x - minX) / Math.max(1, maxX - minX))),
    y: Math.max(0, Math.min(1, (imagePointPx.y - minY) / Math.max(1, maxY - minY))),
  };
}

function handleDesignCutPointerDown(event) {
  const point = designCutPoint(event);
  if (!point) return;
  element.designCutCanvas.setPointerCapture?.(event.pointerId);
  state.designCutDraftStart = point;
  state.designCutDraftEnd = point;
  renderDesignCutEditor();
}

function handleDesignCutPointerMove(event) {
  if (!state.designCutDraftStart) return;
  state.designCutDraftEnd = designCutPoint(event) || state.designCutDraftEnd;
  renderDesignCutEditor();
}

function commitDesignCutBoundary(start, end) {
  const room = state.rooms.find((item) => item.id === state.activeDesignRoomId);
  if (!room) return false;
  const roomPreferences = roomDesignPreferences(room?.id);
  const surface = state.designCutSurface === "wall" ? "wall" : "floor";
  const primarySurfaceId = surface === "wall"
    ? roomPreferences.surfaceOverride.wallSurfaceId
    : roomPreferences.surfaceOverride.floorSurfaceId;
  const primaryColor = surface === "wall"
    ? roomPreferences.surfaceOverride.wallColor
    : roomPreferences.surfaceOverride.floorColor;
  const secondarySurfaceId = roomPreferences.materialBoundary?.surface === surface
    ? roomPreferences.materialBoundary.secondarySurfaceId
    : "";
  if (!secondarySurfaceId) {
    state.activeDesignMaterialTab = surface;
    state.activeDesignMaterialTarget = "secondary";
    element.designError.textContent = "請先在材質卡選擇「切割後第二材質」，再畫分界線。";
    return false;
  }
  const secondarySurface = surfaceById(secondarySurfaceId);
  const boundary = createMaterialBoundary({
    surface,
    wallFace: element.designCutWallFace.value,
    start,
    end,
    primarySurfaceId,
    primaryColor,
    secondarySurfaceId,
    secondaryColor: secondarySurface?.color_hex
      || roomPreferences.materialBoundary?.secondaryColor
      || primaryColor,
  });
  updateRoomDesignPreferences(room.id, (current) => ({
    ...current,
    confirmed: false,
    materialBoundary: boundary,
  }));
  element.designError.textContent = "";
  invalidateGeneratedSchemesAfterDesignChange();
  scheduleSave("design_preferences");
  return true;
}

function refreshDesignCutInteraction() {
  state.designCutDraftStart = null;
  state.designCutDraftEnd = null;
  renderDesignMaterialControls();
  renderDesignMaterialCards();
  renderDesignRoomLocator();
  renderDesignCutEditor();
}

function handleDesignCutPointerUp(event) {
  if (!state.designCutDraftStart) return;
  commitDesignCutBoundary(
    state.designCutDraftStart,
    designCutPoint(event) || state.designCutDraftEnd,
  );
  refreshDesignCutInteraction();
}

function handleDesignCutKeyDown(event) {
  const supportedKeys = ["Enter", " ", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"];
  if (!supportedKeys.includes(event.key)) return;
  event.preventDefault();
  const roomPreferences = roomDesignPreferences(state.activeDesignRoomId);
  const surface = state.designCutSurface === "wall" ? "wall" : "floor";
  const boundary = roomPreferences.materialBoundary?.surface === surface
    ? roomPreferences.materialBoundary
    : null;
  const direction = boundary?.direction === "horizontal" ? "horizontal" : "vertical";
  const movingAlongBoundaryAxis = direction === "horizontal"
    ? ["ArrowUp", "ArrowDown"]
    : ["ArrowLeft", "ArrowRight"];
  if (event.key.startsWith("Arrow") && !movingAlongBoundaryAxis.includes(event.key)) return;
  const step = direction === "horizontal"
    ? event.key === "ArrowUp"
      ? 0.02
      : event.key === "ArrowDown"
        ? -0.02
        : 0
    : event.key === "ArrowLeft"
      ? -0.02
      : event.key === "ArrowRight"
        ? 0.02
        : 0;
  const splitRatio = Math.max(
    0.02,
    Math.min(0.98, materialBoundaryRatio(boundary) + step),
  );
  const displayRatio = direction === "horizontal"
    ? 1 - splitRatio
    : splitRatio;
  const [start, end] = direction === "horizontal"
    ? [{ x: 0.05, y: displayRatio }, { x: 0.95, y: displayRatio }]
    : [{ x: splitRatio, y: 0.05 }, { x: splitRatio, y: 0.95 }];
  commitDesignCutBoundary(start, end);
  refreshDesignCutInteraction();
}

function renderDesignMaterialControls() {
  $$("[data-design-material-tab]").forEach((button) => {
    const active = button.dataset.designMaterialTab === state.activeDesignMaterialTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  $$("[data-design-material-target]").forEach((button) => {
    const active = button.dataset.designMaterialTarget === state.activeDesignMaterialTarget;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function selectDesignSurface(surfaceId) {
  const room = state.rooms.find((item) => item.id === state.activeDesignRoomId);
  const surface = surfaceById(surfaceId);
  const usage = state.activeDesignMaterialTab === "wall" ? "wall" : "floor";
  if (!room || !surface || state.activeDesignMaterialTab === "furniture") return;
  if (!isSurfaceEligibleForRoom(surface, usage, room.type)) {
    element.designError.textContent =
      `這款材質不適用於${room.label}的${usage === "floor" ? "地板" : "牆面"}，請改選其他款式。`;
    return;
  }
  updateRoomDesignPreferences(room.id, (current) => {
    if (state.activeDesignMaterialTarget === "secondary") {
      const existingBoundary = current.materialBoundary?.surface === usage
        ? current.materialBoundary
        : {
          ...createMaterialBoundary({
            surface: usage,
            wallFace: element.designCutWallFace.value,
            primarySurfaceId: usage === "wall"
              ? current.surfaceOverride.wallSurfaceId
              : current.surfaceOverride.floorSurfaceId,
            primaryColor: usage === "wall"
              ? current.surfaceOverride.wallColor
              : current.surfaceOverride.floorColor,
          }),
          mode: "pending",
        };
      state.designCutSurface = usage;
      return {
        ...current,
        confirmed: false,
        materialBoundary: {
          ...existingBoundary,
          secondarySurfaceId: surface.surface_id,
          secondaryColor: surface.color_hex || existingBoundary.primaryColor,
        },
      };
    }
    const nextOverride = { ...current.surfaceOverride };
    if (usage === "wall") {
      nextOverride.wallSurfaceId = surface.surface_id;
      nextOverride.wallColor = surface.color_hex || nextOverride.wallColor;
    } else {
      nextOverride.floorSurfaceId = surface.surface_id;
      nextOverride.floorColor = surface.color_hex || nextOverride.floorColor;
    }
    const materialBoundary = current.materialBoundary?.surface === usage
      ? {
        ...current.materialBoundary,
        primarySurfaceId: surface.surface_id,
        primaryColor: surface.color_hex || (
          usage === "wall" ? nextOverride.wallColor : nextOverride.floorColor
        ),
      }
      : current.materialBoundary;
    return {
      ...current,
      confirmed: false,
      surfaceOverride: nextOverride,
      materialBoundary,
    };
  });
  element.designError.textContent = "";
  renderDesignRoomLocator();
  renderDesignMaterialCards();
  renderDesignCutEditor();
  invalidateGeneratedSchemesAfterDesignChange();
  scheduleSave("design_preferences");
}

function captureDesignRoomMaterials() {
  const roomId = state.activeDesignRoomId;
  if (!roomId) return;
  const existing = state.roomAnswers[roomId] || {};
  const savedMaterials = existing.materialPreferences || {};
  const preservedOrLegacy = (key, select) => (
    Array.isArray(savedMaterials[key])
      ? savedMaterials[key]
      : selectedSelectValues(select)
  );
  const materialPreferences = {
    ...savedMaterials,
    wall: preservedOrLegacy("wall", element.roomWallPreference),
    floor: preservedOrLegacy("floor", element.roomFloorPreference),
    furniture: preservedOrLegacy("furniture", element.roomFurnitureMaterialPreference),
    color: preservedOrLegacy("color", element.roomColorPreference),
    finish: preservedOrLegacy("finish", element.roomFinishPreference),
    cuts: Array.isArray(savedMaterials.cuts)
      ? savedMaterials.cuts
      : element.roomMaterialCuts.value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
  };
  state.roomAnswers[roomId] = { ...existing, materialPreferences };
  updateRoomDesignPreferences(roomId, (current) => ({
    ...current,
    materialPreferences,
    note: element.designRoomMaterialNote?.value.trim() || "",
  }));
}

function renderRoomTechnicalPreferences(room) {
  const existingAxes = state.roomAnswers[room.id]?.axes || {};
  const technicalAxes = roomTechnicalAxes(room.type);
  element.roomTechnicalPreferenceTitle.textContent = technicalAxes
    .map((axisDefinition) => axisDefinition.label)
    .join("、");
  element.roomTechnicalPreferenceOptions.innerHTML =
    renderQuestionnaireTechnicalChoices({
      axes: technicalAxes,
      inputPrefix: "room-technical",
      dataAttribute: "data-technical-axis",
    });
  hydrateQuestionnaireTechnicalChoices({
    container: element.roomTechnicalPreferenceOptions,
    axes: technicalAxes,
    values: existingAxes,
    normalizeChoice: normalizeAxisChoice,
  });
}

function selectDesignRoom(roomId, { capture = true } = {}) {
  if (capture) captureDesignRoomMaterials();
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  state.activeDesignRoomId = room.id;
  state.activeDesignMaterialTarget = "primary";
  state.activeDesignMaterialPage = 1;
  element.designRoomSelector.value = room.id;
  element.designCurrentRoomName.textContent = room.label;
  const options = materialPreferenceOptions(room.type);
  [
    [element.roomWallPreference, options.wall],
    [element.roomFloorPreference, options.floor],
    [element.roomFurnitureMaterialPreference, options.furniture],
    [element.roomColorPreference, options.color],
    [element.roomFinishPreference, options.finish],
  ].forEach(([select, entries]) => {
    select.innerHTML = entries.map((entry) => (
      `<option value="${escapeHtml(entry.value)}">${escapeHtml(entry.label)}</option>`
    )).join("");
  });
  const preferences = state.roomAnswers[room.id]?.materialPreferences || {};
  setSelectedValues(element.roomWallPreference, preferences.wall);
  setSelectedValues(element.roomFloorPreference, preferences.floor);
  setSelectedValues(element.roomFurnitureMaterialPreference, preferences.furniture);
  setSelectedValues(element.roomColorPreference, preferences.color);
  setSelectedValues(element.roomFinishPreference, preferences.finish);
  element.roomMaterialCuts.value = (preferences.cuts || []).join("\n");
  const designRoomPreferences = roomDesignPreferences(room.id);
  element.designRoomMaterialNote.value = designRoomPreferences.note || "";
  if (designRoomPreferences.materialBoundary?.wallFace) {
    element.designCutWallFace.value = designRoomPreferences.materialBoundary.wallFace;
  }
  if (
    designRoomPreferences.materialBoundary?.surface
    && state.activeDesignMaterialTab !== "furniture"
  ) {
    state.designCutSurface = designRoomPreferences.materialBoundary.surface;
    state.activeDesignMaterialTab = designRoomPreferences.materialBoundary.surface;
  }
  renderDesignRoomLocator();
  renderDesignMaterialControls();
  renderDesignMaterialCards();
  renderDesignCutEditor();
}

async function renderDesignPreferences() {
  await ensureDesignAssets();
  const wholeHouse = { ...(state.designPreferences.wholeHouse || {}) };
  if (!surfaceById(wholeHouse.wallSurfaceId)) {
    wholeHouse.wallSurfaceId = defaultSurfaceFor("wall", state.designPreferences.styleId)?.surface_id || "";
  }
  if (!surfaceById(wholeHouse.floorSurfaceId)) {
    wholeHouse.floorSurfaceId = defaultSurfaceFor("floor", state.designPreferences.styleId)?.surface_id || "";
  }
  state.designPreferences = normalizeDesignPreferences({
    ...state.designPreferences,
    wholeHouse,
  });
  renderDesignStyleCards();
  renderSurfaceSelect(
    element.designWallSurface,
    "wall",
    state.designPreferences.wholeHouse?.wallSurfaceId,
  );
  renderSurfaceSelect(
    element.designFloorSurface,
    "floor",
    state.designPreferences.wholeHouse?.floorSurfaceId,
  );
  if (!state.designPreferences.wholeHouse?.wallSurfaceId) {
    state.designPreferences.wholeHouse.wallSurfaceId = element.designWallSurface.value || "";
  }
  if (!state.designPreferences.wholeHouse?.floorSurfaceId) {
    state.designPreferences.wholeHouse.floorSurfaceId = element.designFloorSurface.value || "";
  }
  element.designWallColor.value = state.designPreferences.wholeHouse?.wallColor || "#f4efe4";
  element.designFloorColor.value = state.designPreferences.wholeHouse?.floorColor || "#c9a77d";
  element.designNotes.value = state.designPreferences.notes || "";
  element.designRoomSelector.innerHTML = state.rooms.map((room) => (
    `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`
  )).join("");
  selectDesignRoom(
    state.activeDesignRoomId || state.rooms[0]?.id,
    { capture: false },
  );
  renderDesignBaselineSummary();
  renderWorkbenchMaterialControls();
  const completeRooms = state.rooms.filter((room) => (
    designRoomMaterialCompletion(room).complete
  )).length;
  element.designStatus.textContent = designPreferenceGate(state.designPreferences).ready
    ? `全屋基準已建立 · 房間 ${completeRooms}/${state.rooms.length}`
    : "請先用圖片選風格與色彩方向";
}

function collectDesignPreferences() {
  captureDesignRoomMaterials();
  return normalizeDesignPreferences({
    ...state.designPreferences,
    wholeHouse: {
      wallSurfaceId: element.designWallSurface.value
        || state.designPreferences.wholeHouse?.wallSurfaceId,
      floorSurfaceId: element.designFloorSurface.value
        || state.designPreferences.wholeHouse?.floorSurfaceId,
      wallColor: element.designWallColor.value
        || state.designPreferences.wholeHouse?.wallColor,
      floorColor: element.designFloorColor.value
        || state.designPreferences.wholeHouse?.floorColor,
    },
    rooms: Object.fromEntries(state.rooms.map((room) => [
      room.id,
      {
        ...roomDesignPreferences(room.id),
        materialPreferences: state.roomAnswers[room.id]?.materialPreferences
          || roomDesignPreferences(room.id).materialPreferences
          || {},
      },
    ])),
    notes: element.designNotes.value.trim(),
  });
}

function confirmActiveDesignRoom() {
  captureDesignRoomMaterials();
  const roomId = state.activeDesignRoomId;
  const room = state.rooms.find((item) => item.id === roomId);
  const roomPreferences = roomDesignPreferences(roomId);
  const missing = designRoomMaterialCompletion(room, {
    ...roomPreferences,
    confirmed: true,
  }).missing.filter((item) => item !== "confirmation");
  if (missing.length) {
    const hasIneligibleMaterial = missing.some((item) => item.includes("ineligible"));
    element.designError.textContent = hasIneligibleMaterial
      ? "目前選定材質不適用於此空間，請依上方提示重新選擇後再確認。"
      : "請先替這個空間選好牆面與地板材質。";
    return;
  }
  if (roomPreferences.materialBoundary?.mode === "pending") {
    element.designError.textContent =
      "已選擇第二材質，但尚未在圖面畫出分界；請完成切割或按「清除切割」。";
    element.designCutEditor.open = true;
    return;
  }
  updateRoomDesignPreferences(roomId, (current) => ({ ...current, confirmed: true }));
  element.designError.textContent = "";
  renderDesignRoomLocator();
  const next = state.rooms.find((room) => (
    !designRoomMaterialCompletion(room).complete
  ));
  if (next) selectDesignRoom(next.id, { capture: false });
  else renderDesignPreferences();
  scheduleSave("design_preferences");
}

function applyActiveDesignRoomToUnconfirmed() {
  captureDesignRoomMaterials();
  const source = roomDesignPreferences(state.activeDesignRoomId);
  state.designPreferences = normalizeDesignPreferences({
    ...state.designPreferences,
    rooms: Object.fromEntries(state.rooms.map((room) => {
      const current = roomDesignPreferences(room.id);
      if (current.confirmed || room.id === state.activeDesignRoomId) {
        return [room.id, current];
      }
      return [room.id, {
        ...current,
        surfaceOverride: { ...source.surfaceOverride },
        confirmed: false,
      }];
    })),
  });
  renderDesignRoomLocator();
  renderDesignMaterialCards();
  invalidateGeneratedSchemesAfterDesignChange();
  scheduleSave("design_preferences");
}

function resetUnconfirmedDesignRoomsToBaseline() {
  const baseline = state.designPreferences.wholeHouse || {};
  state.designPreferences = normalizeDesignPreferences({
    ...state.designPreferences,
    rooms: Object.fromEntries(state.rooms.map((room) => {
      const current = roomDesignPreferences(room.id);
      if (current.confirmed) return [room.id, current];
      return [room.id, {
        ...current,
        surfaceOverride: { ...baseline },
        materialBoundary: null,
        confirmed: false,
      }];
    })),
  });
  renderDesignRoomLocator();
  renderDesignMaterialCards();
  renderDesignCutEditor();
  invalidateGeneratedSchemesAfterDesignChange();
  scheduleSave("design_preferences");
}

async function confirmRequirements() {
  element.requirementsError.textContent = "";
  const completion = questionnaireCompletion({
    basicAnswers: state.basicAnswers,
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  if (!completion.ready) {
    element.requirementsError.textContent =
      `尚有 ${completion.incomplete.length} 個項目未完成，已跳到第一個未完成項目。`;
    jumpToNextIncomplete();
    return;
  }
  const ceilingGate = validateQuestionnaireCeilings({
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    roomHeightCm: Number(
      state.confirmedFloorplan?.floorplan?.room_height_cm
      || state.sceneData?.floorplan?.room_height_cm
      || 270
    ),
    minimumFinishedHeightCm: state.minimumFinishedHeightCm,
  });
  if (!ceilingGate.ready) {
    const invalid = ceilingGate.firstInvalid;
    selectQuestionRoom(invalid.roomId, { captureDraft: false, forceReload: true });
    const technicalIndex = roomQuestionStages().findIndex(
      (stage) => stage.dataset.roomQuestionStage === "technical"
    );
    renderRoomQuestionStep(technicalIndex);
    element.requirementsError.textContent =
      `${invalid.roomLabel}的天花方案完成淨高為 ${invalid.finishedHeightCm} 公分，低於最低`
      + `${invalid.minimumFinishedHeightCm} 公分；請先調整天花選項。`;
    return;
  }
  try {
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
      questionnaireSchemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
      clientBrief: currentClientBrief(),
    });
    await renderDesignPreferences();
    setStatus("需求已保存。請先確認材質與風格，再產生三個方案。");
    goTo("design_preferences");
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

const furnitureLabelMap = {
  "沙發": ["sofa", "three-seat"],
  "L 型沙發": ["sofa", "l-shape"],
  "茶几": ["coffee-table", "rect"],
  "圓形茶几": ["coffee-table", "round"],
  "圓桌": ["dining-table", "round-4"],
  "長桌": ["dining-table", "rect-6"],
  "餐椅": ["dining-chair", "standard"],
  "床": ["bed", "double"],
  "床頭櫃": ["bedside-table", "compact"],
  "衣櫃": ["wardrobe", "two-door"],
  "書桌": ["desk", "standard"],
  "工作桌": ["desk", "standard"],
  "工作椅": ["office-chair", "task"],
  "單椅": ["lounge-chair", "accent"],
  "戶外椅": ["lounge-chair", "outdoor"],
  "收納櫃": ["storage-cabinet", "low"],
  "梳妝台": ["vanity-table", "standard"],
  "餐邊櫃": ["sideboard", "standard"],
  "冰箱": ["refrigerator", "single-door"],
  "電器櫃": ["appliance-cabinet", "standard"],
  "中島": ["kitchen-island", "standard"],
  "餐櫃": ["sideboard", "standard"],
  "浴櫃": ["bathroom-vanity", "standard"],
  "鏡櫃": ["mirror-cabinet", "standard"],
  "收納架": ["storage-cabinet", "tall"],
  "層架": ["storage-cabinet", "tall"],
  "鞋櫃": ["storage-cabinet", "low"],
  "穿鞋椅": ["lounge-chair", "accent"],
  "展示架": ["storage-cabinet", "tall"],
  "洗衣機": ["washer", "front-load"],
  "浴缸": ["bathtub", "standard"],
  "電視櫃": ["tv-bench", "low"],
  "植栽架": ["plant-shelf", "standard"],
  "桌": ["table", "standard"],
  "椅": ["chair", "standard"],
};

function roomCenter(room) {
  return room.polygon_cm.reduce((sum, point) => ({
    x: sum.x + point.x / room.polygon_cm.length,
    y: sum.y + point.y / room.polygon_cm.length,
  }), { x: 0, y: 0 });
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
      ]);
    }
  });
  return specs.length ? specs : fallbackSpecs;
}

function setLayoutControlsPending(pending) {
  const layoutPanel = $("#layout-2d-step");
  layoutPanel?.setAttribute("aria-busy", String(pending));
  layoutPanel?.querySelectorAll("button, input, select, textarea").forEach((control) => {
    if (pending) {
      if (!Object.hasOwn(control.dataset, "layoutOperationWasDisabled")) {
        control.dataset.layoutOperationWasDisabled = String(control.disabled);
      }
      control.disabled = true;
      return;
    }
    if (Object.hasOwn(control.dataset, "layoutOperationWasDisabled")) {
      control.disabled = control.dataset.layoutOperationWasDisabled === "true";
      delete control.dataset.layoutOperationWasDisabled;
    }
  });
}

function setAutoLayoutPending(pending) {
  autoLayoutPending = pending;
  setLayoutControlsPending(pending);
  const autoLayoutButton = $("#auto-layout-furniture");
  if (autoLayoutButton) {
    autoLayoutButton.setAttribute("aria-busy", String(pending));
  }
}

function setLayoutConfirmationPending(pending) {
  layoutConfirmationPending = pending;
  setLayoutControlsPending(pending);
  $("#confirm-layout-2d")?.setAttribute("aria-busy", String(pending));
}

function commitAutoLayoutFurniture(generatedFurniture, targetSchemeId) {
  const targetSchemeExists = Boolean(
    targetSchemeId
    && state.layoutSchemeSet?.schemes?.some((scheme) => scheme.id === targetSchemeId),
  );
  if (targetSchemeExists) {
    state.layoutSchemeSet = replaceSchemeFurniture(
      state.layoutSchemeSet,
      targetSchemeId,
      generatedFurniture,
    );
  }
  const targetSchemeStillActive =
    !targetSchemeId || state.layoutSchemeSet?.activeSchemeId === targetSchemeId;
  if (targetSchemeStillActive) {
    state.furniture2d = generatedFurniture;
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    state.activeLayoutRoomId = "all";
    invalidateDownstreamFrom("layout_2d", "家具方案已重新配置，3D 白模與即時寫實需要重新產生。");
    renderLayoutRoomFilter();
    renderLayoutFurniture();
  }
  renderLayoutSchemes();
  scheduleSave("layout_2d");
  return targetSchemeStillActive;
}

async function autoLayoutFurniture(
  policy = "balanced",
  {
    persist = true,
    targetSchemeId = state.layoutSchemeSet?.activeSchemeId || null,
  } = {},
) {
  const generatedFurniture = [];
  for (const room of state.rooms) {
    if (state.keepExistingRoomIds.includes(room.id)) continue;
    const requested = state.roomAnswers[room.id]?.furniture || [];
    const roomWasAnswered = state.roomAnswers[room.id]?.confirmed === true;
    const answerSpecs = requested.map((label) => furnitureLabelMap[label]).filter(Boolean);
    const recommendedSpecs = recommendedFurnitureForRoom(room);
    const requestedSpecs = answerSpecs.length
      ? answerSpecs
      : (policy === "preserve" ? recommendedSpecs.slice(0, 1) : recommendedSpecs);
    const companionSpecs = policy === "preserve"
      ? []
      : recommendCompanionFurniture(
          room.type,
          requestedSpecs.map(([type]) => type),
        ).map((item) => [item.type, item.variantId, item.reason, true]);
    const functionalSpecs = [];
    const currentTypes = new Set(
      [...requestedSpecs, ...companionSpecs].map(([type]) => type),
    );
    if (policy === "functional") {
      const storageByRoom = {
        living_room: ["storage-cabinet", "low", "機能加強案增加靠牆收納。", true],
        bedroom: ["wardrobe", "two-door", "機能加強案補足衣物收納。", true],
        dining_room: ["sideboard", "standard", "機能加強案補足餐廚收納。", true],
      };
      const addition = storageByRoom[room.type];
      if (addition && !currentTypes.has(addition[0])) functionalSpecs.push(addition);
    }
    const specs = [...requestedSpecs, ...companionSpecs, ...functionalSpecs];
    let selectedSpecs = specs;
    try {
      const selection = await api("/api/agent/furniture/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rooms: [{
            room_id: room.id,
            room_type: room.type,
            label: room.label,
          }],
          offers: {
            [room.id]: specs.map((spec, index) => furnitureOfferFromSpec(room, spec, index)),
          },
          context: {
            room_answers: state.roomAnswers[room.id] || {},
            basic_answers: state.basicAnswers,
            scheme_policy: policy,
          },
        }),
      });
      selectedSpecs = specsFromSelectionResponse(room, selection, specs);
    } catch (error) {
      console.warn("Yen furniture selection fallback", error);
    }
    const roomItems = [];
    selectedSpecs.forEach(([type, variant, reason, autoAdded], index) => {
      try {
        const item = createFurniture2DItem(type, variant, {
          id: `${room.id}-${type}-${index + 1}`,
          roomId: room.id,
          userRequired: roomWasAnswered && answerSpecs.length > 0 && autoAdded !== true,
        });
        item.roomId = room.id;
        item.reason = reason
          || `依「${room.label}」的使用需求與可用空間先配置，可再調整。`;
        item.autoAdded = autoAdded === true;
        roomItems.push(item);
      } catch (error) {
        console.warn(error);
      }
    });
    if (!roomItems.length) continue;
    const layout = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        placement_room_id: room.id,
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
      generatedFurniture.push(item);
    });
  }
  if (persist) {
    commitAutoLayoutFurniture(generatedFurniture, targetSchemeId);
  }
  return generatedFurniture;
}

function syncActiveSchemeFurniture() {
  if (!state.layoutSchemeSet?.activeSchemeId) return;
  state.layoutSchemeSet = replaceSchemeFurniture(
    state.layoutSchemeSet,
    state.layoutSchemeSet.activeSchemeId,
    state.furniture2d,
  );
}

function renderLayoutSchemes() {
  const schemes = state.layoutSchemeSet?.schemes || [];
  element.layoutSchemeTabs.innerHTML = schemes.map((scheme) => `
    <button type="button" data-layout-scheme="${escapeHtml(scheme.id)}"
      class="${scheme.id === state.layoutSchemeSet.activeSchemeId ? "is-active" : ""}">
      <strong>${escapeHtml(scheme.title)}</strong>
      <span>${scheme.furniture.length} 件家具</span>
    </button>
  `).join("");
  const selected = activeScheme(state.layoutSchemeSet);
  element.activeSchemeSummary.innerHTML = selected
    ? `
      <span class="eyebrow">${selected.generation.source === "rule_fallback" ? "規則備援" : "Agent 方案"}</span>
      <h3>${escapeHtml(selected.title)}</h3>
      <p>${escapeHtml(selected.summary)}</p>
      <small>三案共用已確認問卷；各案材質可獨立調整，座標只由 roompilot.engine 計算。</small>
    `
    : "<p>尚未產生方案。</p>";
  const contract = schemeGenerationContract(state.layoutSchemeSet);
  const connectionLabel = (status) => ({
    connected: "已連接",
    partial: "部分方案已連接",
    pending: "待接上",
  }[status] || "待接上");
  element.layoutGenerationStatus.textContent =
    `RAG ${connectionLabel(contract.ragStatus)} · `
    + `Agent ${connectionLabel(contract.agentStatus)} · `
    + `家具位置由 ${contract.placementEngine} 驗證`;
}

function activateLayoutScheme(schemeId) {
  syncActiveSchemeFurniture();
  state.layoutSchemeSet = replaceSchemePreferences(
    state.layoutSchemeSet,
    state.layoutSchemeSet?.activeSchemeId,
    state.designPreferences,
  );
  state.layoutSchemeSet = selectScheme(state.layoutSchemeSet, schemeId);
  const selected = activeScheme(state.layoutSchemeSet);
  if (!selected) return;
  state.designPreferences = normalizeDesignPreferences(selected.preferences);
  state.furniture2d = JSON.parse(JSON.stringify(selected.furniture || []));
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  state.activeLayoutRoomId = "all";
  state.schemePreviewScene = null;
  invalidateDownstreamFrom("layout_2d", "已切換家具方案，3D 白模與即時寫實需要重新產生。");
  renderLayoutSchemes();
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  renderWorkbenchMaterialControls();
  setLayoutView("2d");
  scheduleSave("layout_2d");
}

async function confirmDesignPreferences() {
  element.designError.textContent = "";
  state.designPreferences = collectDesignPreferences();
  const ceilingGate = validateQuestionnaireCeilings({
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    roomHeightCm: Number(
      state.confirmedFloorplan?.floorplan?.room_height_cm
      || state.sceneData?.floorplan?.room_height_cm
      || 270
    ),
    minimumFinishedHeightCm: state.minimumFinishedHeightCm,
  });
  if (!ceilingGate.ready) {
    const invalid = ceilingGate.firstInvalid;
    goTo("requirements");
    selectQuestionRoom(invalid.roomId, { captureDraft: false, forceReload: true });
    const technicalIndex = roomQuestionStages().findIndex(
      (stage) => stage.dataset.roomQuestionStage === "technical"
    );
    renderRoomQuestionStep(technicalIndex);
    element.requirementsError.textContent =
      `${invalid.roomLabel}的天花方案預估完成淨高 ${invalid.finishedHeightCm} 公分，低於 `
      + `${invalid.minimumFinishedHeightCm} 公分；請在逐房問卷調整天花選項。`;
    return;
  }
  const gate = designPreferenceGate(state.designPreferences);
  if (!gate.ready) {
    const missingLabels = {
      style: "整體風格",
      wall_surface: "全屋牆面材質",
      floor_surface: "全屋地板材質",
    };
    element.designError.textContent =
      `請先確認：${gate.missing.map((item) => missingLabels[item]).join("、")}。`;
    return;
  }
  const firstIncompleteRoom = state.rooms.find((room) => (
    !designRoomMaterialCompletion(room).complete
  ));
  if (firstIncompleteRoom) {
    selectDesignRoom(firstIncompleteRoom.id, { capture: false });
    element.designError.textContent =
      `請先確認「${firstIncompleteRoom.label}」的牆面與地板；`
      + "完成數會顯示在平面圖上方。";
    return;
  }
  const postMaterialCeilingGate = validateQuestionnaireCeilings({
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    roomHeightCm: Number(
      state.confirmedFloorplan?.floorplan?.room_height_cm
      || state.sceneData?.floorplan?.room_height_cm
      || 270
    ),
    minimumFinishedHeightCm: state.minimumFinishedHeightCm,
  });
  if (!postMaterialCeilingGate.ready) {
    const invalid = postMaterialCeilingGate.firstInvalid;
    selectQuestionRoom(invalid.roomId, { captureDraft: false, forceReload: true });
    const technicalIndex = roomQuestionStages().findIndex(
      (stage) => stage.dataset.roomQuestionStage === "technical"
    );
    renderRoomQuestionStep(technicalIndex);
    element.requirementsError.textContent =
      `${invalid.roomLabel}的天花方案完成淨高為 ${invalid.finishedHeightCm} 公分，低於最低`
      + `${invalid.minimumFinishedHeightCm} 公分；請先調整天花選項。`;
    return;
  }
  try {
    setStatus("正在用既有規則建立三案，所有家具位置都交由家具引擎驗證…");
    state.designPreferences = normalizeDesignPreferences({
      ...state.designPreferences,
      confirmed: true,
      styleConfirmed: true,
      materialsConfirmed: true,
    });
    const [preserve, balanced, functional] = await Promise.all([
      autoLayoutFurniture("preserve", { persist: false }),
      autoLayoutFurniture("balanced", { persist: false }),
      autoLayoutFurniture("functional", { persist: false }),
    ]);
    state.layoutSchemeSet = buildFallbackSchemeSet({
      furnitureByPolicy: { preserve, balanced, functional },
      preferences: state.designPreferences,
    });
    state.furniture2d = JSON.parse(JSON.stringify(
      activeScheme(state.layoutSchemeSet)?.furniture || [],
    ));
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    state.activeLayoutRoomId = "all";
    state.workflow.complete("design_preferences", {
      confirmed: true,
      styleConfirmed: true,
      materialsConfirmed: true,
    });
    state.workflow.goTo("layout_2d");
    renderFurnitureLibrary();
    renderLayoutSchemes();
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    showStep("layout_2d");
    scheduleSave("layout_2d");
    setStatus("三個可微調方案已建立；目前為方案 2。RAG 與 Agent 尚待接上。");
  } catch (error) {
    element.designError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

async function generateSceneForFurniture(
  furniture,
  preferences = state.designPreferences,
) {
  const selectedFurniture = await Promise.all(furniture.map(resolveCatalogFurniture));
  const firstRoom = state.rooms.find((room) => room.type === "living_room") || state.rooms[0];
  const dimensions = roomDimensions(firstRoom);
  const styleChoice = STYLE_PACKS.find(
    (item) => item.id === preferences.styleId,
  );
  const brief = currentClientBrief();
  brief.style = {
    ...(brief.style || {}),
    preferred: styleChoice ? [styleChoice.styleId] : [],
    colors: [
      preferences.wholeHouse?.wallColor,
      preferences.wholeHouse?.floorColor,
    ].filter(Boolean),
    materials: [
      preferences.wholeHouse?.wallSurfaceId,
      preferences.wholeHouse?.floorSurfaceId,
    ].filter(Boolean),
  };
  const scene = await api("/api/scene/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_brief: brief,
      floorplan_filename: `${state.projectId}-confirmed.dxf`,
      floorplan_editor: confirmedFloorplanEditor(),
      room_width_cm: dimensions.widthCm,
      room_depth_cm: dimensions.depthCm,
      required_furniture: [...new Set(furniture.map((item) => item.type))],
      selected_furniture: selectedFurniture,
      selected_furniture_exact: true,
      wall_option: preferences.wholeHouse?.wallSurfaceId || "auto",
      floor_option: preferences.wholeHouse?.floorSurfaceId || "auto",
      wall_color_hex: preferences.wholeHouse?.wallColor || "#f4efe4",
      floor_color_hex: preferences.wholeHouse?.floorColor || "#c9a77d",
    }),
  });
  const planCenter = planCenterCm();
  scene.surface_overrides = state.rooms.flatMap((room) => {
    const override = preferences.rooms?.[room.id]?.surfaceOverride;
    if (!override || !Array.isArray(room.polygon_cm) || room.polygon_cm.length < 3) {
      return [];
    }
    return [{
      room_id: room.id,
      room_label: room.label,
      room_bounds_cm: {
        minX: Math.min(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
        maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
        minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
        maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
      },
      room_polygon_cm: room.polygon_cm.map((point) => ({
        x: point.x - planCenter.x,
        z: point.y - planCenter.y,
      })),
      wall_option: override.wallSurfaceId || preferences.wholeHouse?.wallSurfaceId || "auto",
      floor_option: override.floorSurfaceId || preferences.wholeHouse?.floorSurfaceId || "auto",
      wall_color_hex: override.wallColor || preferences.wholeHouse?.wallColor || "#f4efe4",
      floor_color_hex: override.floorColor || preferences.wholeHouse?.floorColor || "#c9a77d",
    }];
  });
  scene.material_boundaries = state.rooms.flatMap((boundaryRoom) => {
    const boundary = preferences.rooms?.[boundaryRoom.id]?.materialBoundary;
    if (
      !boundary
      || boundary.mode === "pending"
      || !Array.isArray(boundaryRoom.polygon_cm)
    ) return [];
    const bounds = {
      minX: Math.min(...boundaryRoom.polygon_cm.map((point) => point.x)) - planCenter.x,
      maxX: Math.max(...boundaryRoom.polygon_cm.map((point) => point.x)) - planCenter.x,
      minZ: Math.min(...boundaryRoom.polygon_cm.map((point) => point.y)) - planCenter.y,
      maxZ: Math.max(...boundaryRoom.polygon_cm.map((point) => point.y)) - planCenter.y,
    };
    const splitRatio = materialBoundaryRatio(boundary);
    const splitX = bounds.minX + (bounds.maxX - bounds.minX) * splitRatio;
    const splitZ = bounds.minZ + (bounds.maxZ - bounds.minZ) * splitRatio;
    const override = preferences.rooms?.[boundaryRoom.id]?.surfaceOverride || {};
    const surface = boundary.surface === "wall" ? "wall" : "floor";
    const primarySurfaceId = surface === "wall"
      ? override.wallSurfaceId || preferences.wholeHouse?.wallSurfaceId || "auto"
      : override.floorSurfaceId || preferences.wholeHouse?.floorSurfaceId || "auto";
    const primaryColor = surface === "wall"
      ? override.wallColor || preferences.wholeHouse?.wallColor || "#f4efe4"
      : override.floorColor || preferences.wholeHouse?.floorColor || "#c9a77d";
    return [{
      schema_version: "1.1",
      coordinate_unit: "cm",
      surface,
      roomId: boundaryRoom.id,
      direction: boundary.direction,
      split_ratio: splitRatio,
      wallFace: surface === "wall" ? boundary.wallFace || "north" : null,
      line_cm: boundary.direction === "horizontal"
        ? [{ x: bounds.minX, y: splitZ }, { x: bounds.maxX, y: splitZ }]
        : [{ x: splitX, y: bounds.minZ }, { x: splitX, y: bounds.maxZ }],
      room_bounds_cm: bounds,
      room_polygon_cm: boundaryRoom.polygon_cm.map((point) => ({
        x: point.x - planCenter.x,
        z: point.y - planCenter.y,
      })),
      materials: [
        { surface_id: primarySurfaceId, color_hex: primaryColor },
        {
          surface_id: boundary.secondarySurfaceId || primarySurfaceId,
          color_hex: boundary.secondaryColor || primaryColor,
        },
      ],
    }];
  });
  scene.material_boundary = scene.material_boundaries[0] || null;
  return scene;
}

async function previewActiveScheme3d(requestRevision) {
  const status = $("#scheme-preview-status");
  const requestedScheme = activeScheme(state.layoutSchemeSet);
  const requestedSchemeId = requestedScheme?.id;
  const requestedPreferences = normalizeDesignPreferences(
    requestedScheme?.preferences || state.designPreferences,
  );
  const requestIsCurrent = () => isSchemePreviewCurrent({
    requestRevision,
    currentRevision: state.schemePreviewRevision,
    requestedSchemeId,
    activeSchemeId: state.layoutSchemeSet?.activeSchemeId,
    activeView: state.activeLayoutView,
  });
  try {
    status.textContent = "正在建立目前方案的 3D 預覽…";
    const scene = await generateSceneForFurniture(
      state.furniture2d,
      requestedPreferences,
    );
    if (!requestIsCurrent()) return;
    schemePreviewLoadQueue = schemePreviewLoadQueue
      .catch(() => undefined)
      .then(async () => {
        if (!requestIsCurrent()) return;
        state.schemePreviewScene = scene;
        await schemeViewer.loadScene(state.schemePreviewScene);
        if (!requestIsCurrent()) return;
        schemeViewer.setViewMode("dollhouse");
        status.textContent = "3D 預覽與目前 2D 方案使用同一份 Scene JSON。";
      });
    await schemePreviewLoadQueue;
  } catch (error) {
    if (!requestIsCurrent()) return;
    status.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function setLayoutView(mode) {
  state.schemePreviewRevision += 1;
  state.activeLayoutView = mode === "3d" ? "3d" : "2d";
  element.layout2dView.hidden = state.activeLayoutView !== "2d";
  element.layout3dView.hidden = state.activeLayoutView !== "3d";
  $$("[data-layout-view]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.layoutView === state.activeLayoutView);
  });
  if (state.activeLayoutView === "3d") {
    previewActiveScheme3d(state.schemePreviewRevision);
  }
}

async function searchWorkbenchGlb() {
  const query = $("#workbench-glb-search").value.trim();
  if (!query) {
    element.workbenchGlbResults.innerHTML = "<p>請先輸入家具名稱。</p>";
    return;
  }
  try {
    const payload = await api(
      `/api/furniture?q=${encodeURIComponent(query)}&has_model=true&detail=scene&page_size=12`,
    );
    element.workbenchGlbResults.dataset.items = JSON.stringify(payload.items || []);
    element.workbenchGlbResults.innerHTML = (payload.items || []).map((item) => {
      const title = item.name_zh || item.name_zh_raw || item.name_en || "GLB 家具";
      const preview = item.image_url || item.thumbnail_url || item.preview_url || "";
      return `
        <article class="rp-glb-result ${preview ? "has-preview" : ""}">
          <div class="rp-glb-thumb">${preview
            ? `<img src="${escapeHtml(preview)}" alt="${escapeHtml(title)}" loading="lazy"/>`
            : "<span>GLB</span>"}</div>
          <strong>${escapeHtml(title)}</strong>
          <span>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</span>
          <button type="button" data-workbench-furniture-id="${escapeHtml(item.furniture_id)}">替換選取家具</button>
        </article>
      `;
    }).join("") || "<p>找不到有 GLB 的家具。</p>";
  } catch (error) {
    element.workbenchGlbResults.innerHTML = `<p>${escapeHtml(errorMessage(error))}</p>`;
  }
}

function replaceSelectedWorkbenchFurniture(furnitureId) {
  const selected = state.furniture2d.find(
    (item) => item.id === state.selectedFurniture2dId,
  );
  const items = JSON.parse(element.workbenchGlbResults.dataset.items || "[]");
  const catalogItem = items.find((item) => item.furniture_id === furnitureId);
  if (!selected || !catalogItem) {
    element.layoutError.textContent = "請先在平面圖選取要替換的家具。";
    return;
  }
  const catalogType = String(catalogItem.normalized_type || selected.type);
  const footprint = findFurniture2DVariant(catalogType);
  if (!footprint) {
    element.layoutError.textContent =
      `「${catalogItem.name_zh || catalogItem.name_zh_raw || catalogType}」尚無對應的 2D 圖示與家具引擎類型，暫不能替換。`;
    return;
  }
  selected.catalogFurnitureId = catalogItem.furniture_id;
  selected.type = catalogType;
  selected.variantId = footprint.selected.id;
  selected.iconPath = footprint.selected.iconPath;
  selected.categoryLabel = footprint.category.label;
  selected.label = catalogItem.name_zh || catalogItem.name_zh_raw || selected.label;
  selected.widthCm = Number(catalogItem.size_cm?.width || selected.widthCm);
  selected.depthCm = Number(catalogItem.size_cm?.depth || selected.depthCm);
  selected.heightCm = Number(catalogItem.size_cm?.height || selected.heightCm);
  selected.reason = "設計師從資料庫選定 GLB；尺寸已更新，位置仍需通過家具引擎。";
  selected.locked = true;
  state.schemePreviewScene = null;
  renderLayoutFurniture();
  syncActiveSchemeFurniture();
  invalidateDownstreamFrom("layout_2d", "家具模型與尺寸已修改，3D 需要重新產生。");
  scheduleSave("layout_2d");
}

function applyWorkbenchMaterials() {
  const selected = {
    wallSurfaceId: element.workbenchWallSurface.value,
    floorSurfaceId: element.workbenchFloorSurface.value,
    wallColor: element.workbenchWallColor.value,
    floorColor: element.workbenchFloorColor.value,
  };
  const validation = validateSurfaceSelectionForRooms({
    rooms: state.rooms,
    targetRoomId: state.activeLayoutRoomId,
    selection: selected,
    surfaceLookup: surfaceById,
  });
  if (!validation.valid) {
    const labels = [...new Set(validation.invalid.map((item) => item.roomLabel))];
    element.layoutError.textContent =
      `${labels.join("、")}的地板或牆面不適用目前材質；`
      + "請切換到該房間改選，或改用可套用到所有房間的材質。";
    setStatus("材質尚未套用：有空間未通過材質適用性檢查。", "error");
    return;
  }
  const nextPreferences = applySurfaceSelectionToRooms({
    preferences: JSON.parse(JSON.stringify(state.designPreferences)),
    roomIds: state.rooms.map((room) => room.id),
    targetRoomId: state.activeLayoutRoomId,
    selection: selected,
  });
  state.designPreferences = normalizeDesignPreferences(nextPreferences);
  state.layoutSchemeSet = replaceSchemePreferences(
    state.layoutSchemeSet,
    state.layoutSchemeSet?.activeSchemeId,
    state.designPreferences,
  );
  state.schemePreviewScene = null;
  element.layoutError.textContent = "";
  invalidateDownstreamFrom(
    "layout_2d",
    "方案材質已修改；既有 3D 已失效，切換 3D 時會重新產生。",
  );
  scheduleSave("layout_2d");
  const scopeLabel = state.activeLayoutRoomId === "all"
    ? "全屋"
    : state.rooms.find((room) => room.id === state.activeLayoutRoomId)?.label || "目前房間";
  setStatus(`${scopeLabel}的牆面與地板材質已套用到目前方案；切換 3D 可重新預覽。`);
}

function updateWorkbenchMaterialBoundary(remove = false) {
  if (state.activeLayoutRoomId === "all") {
    element.layoutError.textContent = "請先在上方選擇要切割材質的房間。";
    return;
  }
  const nextPreferences = JSON.parse(JSON.stringify(state.designPreferences));
  const current = nextPreferences.rooms?.[state.activeLayoutRoomId] || {};
  const nextRoomPreferences = { ...current };
  if (remove) {
    delete nextRoomPreferences.materialBoundary;
  } else {
    if (!element.workbenchSecondarySurface.value) {
      element.layoutError.textContent = "請先選擇切割後的第二材質。";
      return;
    }
    const surface = element.workbenchCutSurface.value === "wall" ? "wall" : "floor";
    const activeRoom = state.rooms.find(
      (room) => room.id === state.activeLayoutRoomId,
    );
    const override = current.surfaceOverride || nextPreferences.wholeHouse || {};
    const primaryValidation = validateSurfaceSelectionForRooms({
      rooms: state.rooms,
      targetRoomId: state.activeLayoutRoomId,
      selection: {
        wallSurfaceId: override.wallSurfaceId,
        floorSurfaceId: override.floorSurfaceId,
      },
      surfaceLookup: surfaceById,
    });
    if (!primaryValidation.valid) {
      element.layoutError.textContent =
        "目前房間原有材質不適用，請先在上方改選並按「套用材質」，再建立切割。";
      return;
    }
    const secondarySurface = surfaceById(element.workbenchSecondarySurface.value);
    if (!isSurfaceEligibleForRoom(secondarySurface, surface, activeRoom?.type)) {
      element.layoutError.textContent =
        `第二材質不適用於${activeRoom?.label || "目前房間"}的`
        + `${surface === "floor" ? "地板" : "牆面"}，請改選其他款式。`;
      return;
    }
    const direction = $("#workbench-cut-direction").value === "horizontal"
      ? "horizontal"
      : "vertical";
    const splitRatio = Number($("#workbench-cut-position").value) / 100;
    const displayRatio = direction === "horizontal"
      ? 1 - splitRatio
      : splitRatio;
    const [start, end] = direction === "horizontal"
      ? [{ x: 0.05, y: displayRatio }, { x: 0.95, y: displayRatio }]
      : [{ x: splitRatio, y: 0.05 }, { x: splitRatio, y: 0.95 }];
    nextRoomPreferences.materialBoundary = createMaterialBoundary({
      surface,
      wallFace: element.workbenchCutWallFace.value,
      start,
      end,
      primarySurfaceId: surface === "wall"
        ? override.wallSurfaceId
        : override.floorSurfaceId,
      primaryColor: surface === "wall"
        ? override.wallColor
        : override.floorColor,
      secondarySurfaceId: element.workbenchSecondarySurface.value,
      secondaryColor: element.workbenchSecondaryColor.value,
    });
  }
  nextPreferences.rooms = {
    ...(nextPreferences.rooms || {}),
    [state.activeLayoutRoomId]: nextRoomPreferences,
  };
  state.designPreferences = normalizeDesignPreferences(nextPreferences);
  state.layoutSchemeSet = replaceSchemePreferences(
    state.layoutSchemeSet,
    state.layoutSchemeSet?.activeSchemeId,
    state.designPreferences,
  );
  state.schemePreviewScene = null;
  invalidateDownstreamFrom(
    "layout_2d",
    "方案材質切割已修改；既有 3D 已失效，切換 3D 時會重新產生。",
  );
  element.layoutError.textContent = "";
  renderWorkbenchMaterialControls();
  scheduleSave("layout_2d");
}

function renderLayoutRoomFilter() {
  if (!element.layoutRoomFilter) return;
  const roomOptions = state.rooms
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
  renderSelectedFurnitureEditor();
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

async function finishFurnitureDrag(drag) {
  if (!drag) return;
  try {
    const result = await validateFurniturePosition(drag.item);
    if (!result.ok) {
      drag.item.xCm = drag.originalX;
      drag.item.yCm = drag.originalY;
      drag.item.placementFailed = true;
      drag.item.placementReason = result.reason || "位置未通過家具引擎檢查";
      element.layoutError.textContent = `${drag.item.label}：${drag.item.placementReason}`;
    } else {
      drag.item.placementFailed = false;
      drag.item.placementReason = "";
      element.layoutError.textContent = "";
    }
  } catch (error) {
    drag.item.xCm = drag.originalX;
    drag.item.yCm = drag.originalY;
    element.layoutError.textContent = errorMessage(error);
  }
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具位置已修改，3D 白模與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
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
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具形式已修改，3D 白模與即時寫實需要重新產生。");
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
  state.selectedFurniture2dId = item.id;
  state.activeLayoutRoomId = room.id;
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具已新增，3D 白模與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
}

function updateSelectedFurnitureDimensions() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
  if (!item) return;
  item.widthCm = Math.max(1, Number(element.selectedFurnitureWidth.value) || item.widthCm);
  item.depthCm = Math.max(1, Number(element.selectedFurnitureDepth.value) || item.depthCm);
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具尺寸已修改，3D 白模與即時寫實需要重新產生。");
  scheduleSave("layout_2d");
}

async function resolveCatalogFurniture(item) {
  try {
    if (item.catalogFurnitureId) {
      const exact = await api(
        `/api/furniture/${encodeURIComponent(item.catalogFurnitureId)}`,
      );
      return mergeCatalogFurniture(item, exact);
    }
    const payload = await api(`/api/furniture?type=${encodeURIComponent(item.type)}&has_model=true&detail=scene&page_size=8`);
    const candidates = payload.items || [];
    if (!candidates.length) return toSceneFurniture(item);
    const best = candidates.toSorted((a, b) => {
      const aSize = a.size_cm || {};
      const bSize = b.size_cm || {};
      const aDelta = Math.abs(Number(aSize.width || 0) - item.widthCm) + Math.abs(Number(aSize.depth || 0) - item.depthCm);
      const bDelta = Math.abs(Number(bSize.width || 0) - item.widthCm) + Math.abs(Number(bSize.depth || 0) - item.depthCm);
      return aDelta - bDelta;
    })[0];
    return mergeCatalogFurniture(item, best);
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

async function confirmLayout2d() {
  element.layoutError.textContent = "";
  if (autoLayoutPending) {
    element.layoutError.textContent = "家具仍在重新配置，完成後才能進入 3D。";
    return;
  }
  if (layoutConfirmationPending) return;
  const confirmationRevision = ++layoutConfirmationRequestRevision;
  setLayoutConfirmationPending(true);
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
      if (
        confirmationRevision !== layoutConfirmationRequestRevision
        || state.workflow?.currentStep !== "layout_2d"
      ) {
        setStatus("已離開方案工作台，本次 3D 生成未套用。");
        return;
      }
      const invalid = (validation.scene_objects || []).filter(
        (item) => item.placement_failed || !item.position_locked,
      );
      if (invalid.length) {
        element.layoutError.textContent = `${invalid
          .map((item) => item.name_zh_raw || item.normalized_type)
          .join("、")}目前位置未通過碰撞、淨空或房間邊界檢查，請移動或更換尺寸。`;
        return;
      }
    }
    setStatus(state.furniture2d.length
      ? "正在用 2D 尺寸選擇最接近的 GLB，並產生 3D 白模…"
      : "沒有家具需求，正在產生純結構 3D 白模…");
    const payload = await generateSceneForFurniture(state.furniture2d);
    if (
      confirmationRevision !== layoutConfirmationRequestRevision
      || state.workflow?.currentStep !== "layout_2d"
    ) {
      setStatus("已離開方案工作台，本次 3D 生成未套用。");
      return;
    }
    syncActiveSchemeFurniture();
    state.sceneData = payload;
    state.sceneData.questionnaire = {
      schema_version: QUESTIONNAIRE_SCHEMA_VERSION,
      basic: state.basicAnswers,
      rooms: state.roomAnswers,
      keep_existing_room_ids: state.keepExistingRoomIds,
      design_preferences: state.designPreferences,
    };
    state.sceneData.style = {
      ...(state.sceneData.style || {}),
      style_id: "white_model",
      palette_hex: ["#f4f1ec", "#e9e6e1", "#d8d3cc", "#bcb4aa"],
    };
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
    const diagnostics = whiteViewer.getDiagnostics();
    const expectedFurnitureCount = state.sceneData.scene_objects.filter(
      (item) => !item.placement_failed,
    ).length;
    const resolutionText = placementResolutionText(state.sceneData.placement_resolution_report || []);
    if (expectedFurnitureCount === 0) {
      element.whiteError.textContent = "";
      setStatus("純結構 3D 白模已產生；此方案沒有家具需求。");
    } else if (diagnostics.visibleFurnitureCount > 0) {
      element.whiteError.textContent = resolutionText;
      setStatus(`3D 白模已產生，${diagnostics.visibleFurnitureCount} 件家具可見。`);
    } else {
      element.whiteError.textContent = "3D 中沒有任何可見家具，不能進入下一步。";
    }
    scheduleSave("white_model_3d");
  } catch (error) {
    element.layoutError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  } finally {
    setLayoutConfirmationPending(false);
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
      <span>${item.model_url ? "GLB" : "白色替代物"}</span>
      <small>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</small>
      <small>${item.user_specified ? "已指定" : "系統選配"}</small>
    </button>
  `).join("");
  element.objectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  if (element.realisticObjectList) {
    element.realisticObjectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  }
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
}

async function deleteSelectedSceneFurniture() {
  const objects = state.sceneData?.scene_objects || [];
  const selected = objects[state.selectedSceneIndex];
  if (!selected) {
    setStatus("目前沒有可刪除的家具。", "error");
    return;
  }
  objects.splice(state.selectedSceneIndex, 1);
  state.selectedSceneIndex = Math.max(0, Math.min(state.selectedSceneIndex, objects.length - 1));
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  if (state.workflow.currentStep === "white_model_3d") {
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    scheduleSave("white_model_3d");
  } else {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
    scheduleSave("realistic_3d");
  }
  setStatus(`已刪除「${selected.name_zh_raw || selected.normalized_type || "家具"}」。`);
}

async function searchGlbFurniture() {
  const query = $("#glb-furniture-search").value.trim();
  if (!query) {
    element.glbResults.innerHTML = "<p>請輸入家具名稱。</p>";
    return;
  }
  try {
    const payload = await api(`/api/furniture?q=${encodeURIComponent(query)}&has_model=true&detail=scene&page_size=12`);
    element.glbResults.innerHTML = (payload.items || []).map((item) => {
      const preview = item.image_url
        || item.thumbnail_url
        || item.preview_url
        || item.main_image_url
        || item.image
        || "";
      const title = item.name_zh || item.name_zh_raw || item.name_en || "GLB 家具";
      return `
      <article class="rp-glb-result ${preview ? "has-preview" : ""}">
        <div class="rp-glb-thumb">
          ${preview
            ? `<img src="${escapeHtml(preview)}" alt="${escapeHtml(title)}" loading="lazy"/>`
            : "<span>GLB</span>"}
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
    element.glbResults.dataset.items = JSON.stringify(payload.items || []);
  } catch (error) {
    element.glbResults.innerHTML = `<p>${escapeHtml(errorMessage(error))}</p>`;
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
  await whiteViewer.loadScene(state.sceneData);
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  scheduleSave("white_model_3d");
  element.whiteError.textContent = "";
  setStatus("已更換實際 GLB，新尺寸與原位置已通過家具引擎檢查。");
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
      state.selectedSceneIndex = state.sceneData.scene_objects.length - 1;
      await whiteViewer.loadScene(state.sceneData);
      renderSceneObjectList();
      loadSelectedSceneAppearance();
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
      element.whiteError.textContent = "";
      scheduleSave("white_model_3d");
      setStatus("家具已新增到指定位置，並通過碰撞、淨空與房間邊界檢查。");
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
  const diagnostics = whiteViewer.getDiagnostics();
  const expectedFurnitureCount = state.sceneData?.scene_objects?.filter(
    (item) => !item.placement_failed,
  ).length || 0;
  if (expectedFurnitureCount > 0 && diagnostics.visibleFurnitureCount <= 0) {
    element.whiteError.textContent = "3D 中看不到家具，必須先修正載入、比例或相機框景。";
    return;
  }
  if (!$("#specified-furniture-reviewed").checked) {
    element.whiteError.textContent = "請先確認是否有指定家具需求。";
    $("#specified-furniture-reviewed").focus();
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
    const invalid = (finalValidation.scene_objects || []).filter(
      (item) => item.placement_failed || !item.position_locked,
    );
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
  const preferredPack = selectedStylePack() || STYLE_PACKS[0];
  const wholeHouseFinishes = state.designPreferences.wholeHouse || {};
  state.activeStyleId = preferredPack.styleId;
  state.activeStylePackId = preferredPack.id;
  state.surfaceState = {
    wall: {
      material: wholeHouseFinishes.wallSurfaceId || preferredPack.wall.surfaceOption,
      color: wholeHouseFinishes.wallColor || preferredPack.wall.color,
    },
    floor: {
      material: wholeHouseFinishes.floorSurfaceId || preferredPack.floor.surfaceOption,
      color: wholeHouseFinishes.floorColor || preferredPack.floor.color,
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
  $("#wall-color").value = wholeHouseFinishes.wallColor || preferredPack.wall.color;
  $("#wall-material").value =
    wholeHouseFinishes.wallSurfaceId || preferredPack.wall.surfaceOption;
  $("#floor-color").value = wholeHouseFinishes.floorColor || preferredPack.floor.color;
  $("#floor-material").value =
    wholeHouseFinishes.floorSurfaceId || preferredPack.floor.surfaceOption;
  await applySurfaceOverrides();
  await evaluateCeilingConflicts();
  setStatus(expectedFurnitureCount
    ? "家具可見性已通過。現在可即時切換 18 個完整 PBR StylePack。"
    : "純結構白模已確認。現在可即時切換 18 個完整 PBR StylePack。");
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

function renderGroupedMaterialOptions(activePack) {
  const options = STYLE_MATERIAL_OPTIONS[state.activeStyleId]
    || STYLE_MATERIAL_OPTIONS[activePack?.styleId]
    || {};
  const render = (kind, host) => {
    if (!host) return;
    const recommendedId = activePack?.[kind]?.surfaceOption;
    const items = [...(options[kind] || [])].sort((left, right) =>
      Number(right.id === recommendedId) - Number(left.id === recommendedId)
    );
    const current = $(`#${kind}-material`)?.value;
    host.innerHTML = items.map((item) => `
      <button type="button"
        data-surface-kind="${escapeHtml(kind)}"
        data-surface-material="${escapeHtml(item.id)}"
        data-surface-color="${escapeHtml(item.color || "")}"
        data-material-preview="${escapeHtml(item.materialPreview || "")}"
        data-style-card-recommended="${item.id === recommendedId ? "true" : "false"}"
        class="${item.id === current ? "is-active" : ""}">
        <span class="rp-material-preview" style="background:${escapeHtml(item.color || "#ddd")};${item.materialPreview ? `background-image:url('${escapeHtml(item.materialPreview)}')` : ""}"></span>
        <strong>${escapeHtml(item.label)}${item.id === recommendedId ? " · 此色卡推薦" : ""}</strong>
        <small>${escapeHtml(item.note || "")}</small>
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
  state.sceneData.surface_overrides = [];
  state.sceneData.material_boundary = null;
  state.materialBoundary = null;
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

async function applySurfaceOverrides() {
  const scope = $("#surface-scope").value;
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
    const room = state.rooms.find((item) => item.id === state.selectedRoomId) || state.rooms[0];
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
    `revision-${Number(state.project?.revision || 0)}`,
    state.activeStylePackId || "no-style",
  ].join(":");
}

function renderProposalSummary() {
  const pack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const furniture = state.sceneData?.scene_objects || [];
  const customPreferenceCount = Object.values(state.roomAnswers || {}).filter(
    (answer) =>
      String(answer?.personalNeeds || "").trim()
      || Object.values(answer?.customNotes || {}).some((note) => String(note).trim()),
  ).length;
  const rows = [
    ["色卡", pack ? `${pack.styleLabel}／${pack.name}` : "尚未選擇"],
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
  await proposalViewer.loadScene(state.sceneData);
  const saved = state.proposalReview.masterView?.camera;
  if (saved) proposalViewer.setCameraState(saved);
  else {
    proposalViewer.setViewMode("orbit");
    proposalViewer.setCameraPreset("corner");
  }
  proposalViewer.lockRenderCamera(false);
  element.proposalContentConfirmed.checked = Boolean(saved);
  element.masterViewStatus.textContent = saved
    ? "已載入上次鎖定視角；調整後請重新鎖定。"
    : "尚未鎖定比較視角。";
}

function lockMasterRenderView() {
  if (!element.proposalContentConfirmed.checked) {
    element.masterViewStatus.textContent = "請先確認家具、結構、材質、色卡與需求。";
    return;
  }
  if (!state.workflow.completed.includes("requirements")) {
    element.requirementsError.textContent = "請先完成基本資料與逐房需求。";
    showQuestionnaireStage("rooms");
    return;
  }
  if (
    !state.workflow.completed.includes("design_preferences")
    || state.designPreferences.confirmed !== true
  ) {
    element.requirementsError.textContent =
      "請先確認整體風格，以及各房間的牆面、地板與家具材質。";
    showQuestionnaireStage("finishes");
    return;
  }
  if (!state.sceneData || !state.activeStylePackId) {
    element.masterViewStatus.textContent = "缺少已確認的場景或色卡，請返回第 8 步。";
    return;
  }
  const camera = proposalViewer.getCameraState();
  if (camera.camera_type !== "perspective") {
    element.masterViewStatus.textContent = "遠端室內渲染需要透視視角，請改用「室內環視」或「室內透視」。";
    return;
  }
  const lockedAt = new Date().toISOString();
  state.proposalReview.masterView = {
    camera,
    scene_version: currentSceneVersion(),
    style_card_id: state.activeStylePackId,
    locked_at: lockedAt,
  };
  state.proposalReview.confirmedStyleCardId = null;
  state.proposalReview.roomViews = {};
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
  element.masterViewStatus.textContent = "比較視角與場景版本已鎖定。";
  scheduleSave("proposal_review");
  goTo("ai_render");
}

function renderPaletteOptions() {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const options = STYLE_PACKS.filter((item) => item.styleId === activePack?.styleId);
  element.paletteRenderOptions.innerHTML = options.map((pack) => `
    <label>
      <input type="checkbox" value="${escapeHtml(pack.id)}" data-render-style-card
        ${pack.id === state.activeStylePackId ? "checked" : ""} />
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
  state.proposalReview.roomViews = {};
  element.roomRenderSection.hidden = false;
  state.selectedRenderRoomId = state.rooms[0]?.id || null;
  if (state.selectedRenderRoomId) selectRenderRoom(state.selectedRenderRoomId);
  scheduleSave("ai_render");
  element.aiRenderStatus.textContent = "色卡已確認；請逐房間調整並保存視角。";
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

function renderRequestPayload(mode, styleCardIds, roomViews = []) {
  return {
    schema_version: "1.0",
    mode,
    project_id: state.projectId,
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
      rooms: state.roomAnswers,
      keep_existing_room_ids: state.keepExistingRoomIds,
      design_preferences: state.designPreferences,
    },
    master_view: state.proposalReview.masterView,
    room_views: roomViews,
    reference_png_data_url: aiRenderViewer.capturePng(),
  };
}

async function requestPaletteRenders() {
  const styleCardIds = $$("[data-render-style-card]:checked").map((input) => input.value);
  if (!styleCardIds.length) {
    element.aiRenderStatus.textContent = "至少選擇一張色卡。";
    return;
  }
  try {
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
  } catch (error) {
    element.aiRenderStatus.textContent = errorMessage(error);
  }
}

async function submitRoomRenders() {
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
        invalidateDownstreamFrom("space_confirmation", "結構位置已修改，後續需求、家具與 3D 需要重新確認。");
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
      invalidateDownstreamFrom("space_confirmation", `${resizedLabel}寬已直接調整，後續需求、家具與 3D 需要重新確認。`);
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
        invalidateDownstreamFrom("space_confirmation", "樑長已調整，後續需求、家具與 3D 需要重新確認。");
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
  $("#apply-room-merge").addEventListener("click", mergeSelectedRooms);
  $("#cancel-room-geometry").addEventListener("click", () => setRoomGeometryMode(null));
  $$("[data-room-node-mode]").forEach((button) => {
    button.addEventListener("click", () => setRoomNodeMode(button.dataset.roomNodeMode));
  });
  $("#apply-node-merge").addEventListener("click", mergeSelectedRoomNodes);
  $("#cancel-node-edit").addEventListener("click", () => setRoomNodeMode(null));
  $("#add-missed-room").addEventListener("click", addMissedRoom);
  $("#show-all-rooms").addEventListener("click", () => {
    state.showAllRooms = true;
    renderSpaceOverlay();
  });
  $("#save-room").addEventListener("click", saveRoom);
  element.spaceOverlay.addEventListener("pointerdown", spacePointerDown);
  element.spaceOverlay.addEventListener("pointermove", spacePointerMove);
  $("#apply-structure-size").addEventListener("click", applySelectedStructureSize);
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
    invalidateDownstreamFrom("space_confirmation", "門扇方向已修改，後續需求、家具與 3D 需要重新確認。");
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
  $("#previous-basic-question").addEventListener("click", () => advanceBasicQuestion(-1));
  $("#next-basic-question").addEventListener("click", () => advanceBasicQuestion(1));
  $("#jump-next-incomplete").addEventListener("click", jumpToNextIncomplete);
  $("#previous-question-room").addEventListener("click", () => {
    const index = state.rooms.findIndex((room) => room.id === state.activeQuestionRoomId);
    if (index > 0) selectQuestionRoom(state.rooms[index - 1].id);
  });
  $("#copy-room-answer").addEventListener("click", copySelectedRoomAnswer);
  $("#random-room-inspiration").addEventListener("click", randomizeRoomInspiration);
  $("#previous-questionnaire-warning").addEventListener("click", () => {
    state.activeQuestionnaireWarningIndex = Math.max(0, state.activeQuestionnaireWarningIndex - 1);
    renderQuestionnaireWarning();
  });
  $("#next-questionnaire-warning").addEventListener("click", () => {
    state.activeQuestionnaireWarningIndex = Math.min(
      state.questionnaireWarnings.length - 1,
      state.activeQuestionnaireWarningIndex + 1,
    );
    renderQuestionnaireWarning();
  });
  element.questionnaireIncompleteList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-incomplete-kind]");
    if (!button) return;
    if (button.dataset.incompleteKind === "basic") {
      element.questionnaireRoomLocator.hidden = true;
      $("#whole-house-questionnaire").hidden = false;
      $("#room-questionnaire").hidden = true;
      renderBasicQuestionStep(
        WHOLE_HOUSE_QUESTIONS.findIndex(
          (question) => question.id === button.dataset.incompleteId
        )
      );
    } else {
      $("#whole-house-questionnaire").hidden = true;
      $("#room-questionnaire").hidden = false;
      selectQuestionRoom(button.dataset.incompleteId);
    }
  });
  element.roomAxisOptions.addEventListener("change", () => {
    captureActiveDesignerRoomDraft();
    renderRoomIntegratedSummary();
    renderQuestionnaireWarning();
  });
  element.roomUseOptions.addEventListener("change", () => {
    captureActiveDesignerRoomDraft();
    renderRoomIntegratedSummary();
    renderQuestionnaireWarning();
  });
  $("#room-questionnaire").addEventListener("input", (event) => {
    updateQuestionnaireAxisCustomApproach(
      event.target.closest(".rp-axis-custom-approach"),
    );
    captureActiveDesignerRoomDraft();
    renderRoomIntegratedSummary();
    renderQuestionnaireWarning();
    scheduleDesignerQuestionnaireDraftSave();
  });
  $("#room-questionnaire").addEventListener("change", () => {
    scheduleDesignerQuestionnaireDraftSave();
  });
  element.questionnaireMode.addEventListener("change", () => {
    state.questionnaireMode = element.questionnaireMode.value;
    scheduleSave("requirements");
  });
  element.designerQuestionnaireNotes.addEventListener("input", () => {
    state.designerQuestionnaireNotes = element.designerQuestionnaireNotes.value;
    updateDesignerNoteState();
    element.clientBriefPreview.textContent =
      JSON.stringify(currentQuestionnaireDocument(), null, 2);
  });
  element.designerQuestionnaireNotes.addEventListener("change", () => scheduleSave("requirements"));
  element.minimumFinishedHeightCm.addEventListener("change", () => {
    state.minimumFinishedHeightCm = Math.min(
      300,
      Math.max(210, Number(element.minimumFinishedHeightCm.value) || 240),
    );
    updateCeilingHeightReference();
    scheduleSave("requirements");
  });
  $("#create-questionnaire-invite").addEventListener("click", createQuestionnaireInvite);
  $("#revoke-all-questionnaire-invites").addEventListener(
    "click",
    revokeAllQuestionnaireInvites,
  );
  element.questionnaireInviteOutput.addEventListener("click", (event) => {
    if (event.target.closest("[data-revoke-questionnaire-invite]")) {
      revokeActiveQuestionnaireInvite();
    }
  });
  element.downloadQuestionnaireJson.addEventListener("click", downloadQuestionnaireJson);
  $("#reapply-conflicted-save").addEventListener("click", reapplyConflictedSave);
  $("#accept-latest-project").addEventListener("click", acceptLatestProjectVersion);
  element.roomQuestionNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-question-room]");
    if (button) selectQuestionRoom(button.dataset.questionRoom);
  });
  element.requirementsOverlay?.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    const room = event.target.closest("[data-requirement-room]");
    if (!room) return;
    event.preventDefault();
    selectQuestionRoom(room.dataset.requirementRoom);
  });
  $("#confirm-room-requirement").addEventListener("click", () => resolveActiveRoomRequirement(false));
  $("#previous-room-question").addEventListener("click", () => advanceRoomQuestion(-1));
  $("#next-room-question").addEventListener("click", () => advanceRoomQuestion(1));
  $("#keep-room-existing").addEventListener("click", () => resolveActiveRoomRequirement(true));
  $("#keep-unfilled-rooms-existing").addEventListener("click", keepUnfilledRoomsExisting);
  element.confirmRequirements.addEventListener("click", confirmRequirements);
  element.designStyleGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-design-style-family]");
    if (!button) return;
    state.activeDesignStyleFamily = button.dataset.designStyleFamily;
    renderDesignStyleCards();
  });
  element.designStyleVariantGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-design-style]");
    const pack = STYLE_PACKS.find((item) => item.id === button?.dataset.designStyle);
    if (pack) applyDesignStylePack(pack);
  });
  element.designRoomSelector.addEventListener("change", () => {
    selectDesignRoom(element.designRoomSelector.value);
    scheduleSave("design_preferences");
  });
  const selectDesignRoomFromEvent = (event) => {
    const button = event.target.closest("[data-design-room]");
    if (button) {
      selectDesignRoom(button.dataset.designRoom);
      scheduleSave("design_preferences");
    }
  };
  element.designRoomNav.addEventListener("click", selectDesignRoomFromEvent);
  element.designRoomPlanOverlay.addEventListener("click", selectDesignRoomFromEvent);
  element.designRoomPlanOverlay.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    selectDesignRoomFromEvent(event);
  });
  element.designMaterialTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-design-material-tab]");
    if (!button) return;
    state.activeDesignMaterialTab = button.dataset.designMaterialTab;
    state.activeDesignMaterialPage = 1;
    if (state.activeDesignMaterialTab !== "furniture") {
      state.designCutSurface = state.activeDesignMaterialTab;
    }
    renderDesignMaterialControls();
    renderDesignMaterialCards();
    renderDesignCutEditor();
  });
  element.designMaterialTabs.addEventListener("keydown", (event) => {
    const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const buttons = [
      ...element.designMaterialTabs.querySelectorAll("[data-design-material-tab]"),
    ];
    const current = event.target.closest("[data-design-material-tab]");
    const currentIndex = buttons.indexOf(current);
    if (currentIndex < 0) return;
    let nextIndex = currentIndex;
    if (["ArrowRight", "ArrowDown"].includes(event.key)) {
      nextIndex = (currentIndex + 1) % buttons.length;
    } else if (["ArrowLeft", "ArrowUp"].includes(event.key)) {
      nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = buttons.length - 1;
    }
    event.preventDefault();
    buttons[nextIndex].focus();
    buttons[nextIndex].click();
  });
  element.designMaterialTarget.addEventListener("click", (event) => {
    const button = event.target.closest("[data-design-material-target]");
    if (!button) return;
    state.activeDesignMaterialTarget = button.dataset.designMaterialTarget;
    state.activeDesignMaterialPage = 1;
    renderDesignMaterialControls();
    renderDesignMaterialCards();
  });
  element.designMaterialPagination.addEventListener("click", (event) => {
    const pageButton = event.target.closest("[data-design-material-page]");
    if (pageButton) {
      state.activeDesignMaterialPage = Number(pageButton.dataset.designMaterialPage) || 1;
      renderDesignMaterialCards();
      return;
    }
    if (event.target.closest("#previous-design-material-page")) {
      state.activeDesignMaterialPage -= 1;
      renderDesignMaterialCards();
      return;
    }
    if (event.target.closest("#next-design-material-page")) {
      state.activeDesignMaterialPage += 1;
      renderDesignMaterialCards();
    }
  });
  element.designMaterialCardGrid.addEventListener("click", (event) => {
    const materialButton = event.target.closest("[data-design-surface-id]");
    if (materialButton) {
      selectDesignSurface(materialButton.dataset.designSurfaceId);
      return;
    }
    const furnitureButton = event.target.closest("[data-furniture-material]");
    if (!furnitureButton) return;
    const roomId = state.activeDesignRoomId;
    const answer = state.roomAnswers[roomId] || {};
    const preferences = { ...(answer.materialPreferences || {}) };
    const selected = new Set(preferences.furniture || []);
    if (selected.has(furnitureButton.dataset.furnitureMaterial)) {
      selected.delete(furnitureButton.dataset.furnitureMaterial);
    } else {
      selected.add(furnitureButton.dataset.furnitureMaterial);
    }
    preferences.furniture = [...selected];
    state.roomAnswers[roomId] = { ...answer, materialPreferences: preferences };
    updateRoomDesignPreferences(roomId, (current) => ({
      ...current,
      confirmed: false,
      materialPreferences: preferences,
    }));
    renderDesignRoomLocator();
    renderDesignMaterialCards();
    invalidateGeneratedSchemesAfterDesignChange();
    scheduleSave("design_preferences");
  });
  $$("[data-design-cut-surface]").forEach((button) => {
    button.addEventListener("click", () => {
      state.designCutSurface = button.dataset.designCutSurface;
      state.activeDesignMaterialTab = state.designCutSurface;
      state.designCutDraftStart = null;
      state.designCutDraftEnd = null;
      renderDesignMaterialControls();
      renderDesignMaterialCards();
      renderDesignCutEditor();
    });
  });
  element.designCutWallFace.addEventListener("change", () => {
    const roomPreferences = roomDesignPreferences();
    if (roomPreferences.materialBoundary?.surface === "wall") {
      updateRoomDesignPreferences(state.activeDesignRoomId, (current) => ({
        ...current,
        confirmed: false,
        materialBoundary: {
          ...current.materialBoundary,
          wallFace: element.designCutWallFace.value,
        },
      }));
      renderDesignRoomLocator();
      invalidateGeneratedSchemesAfterDesignChange();
    }
    renderDesignCutEditor();
    scheduleSave("design_preferences");
  });
  element.designCutCanvas.addEventListener("pointerdown", handleDesignCutPointerDown);
  element.designCutCanvas.addEventListener("pointermove", handleDesignCutPointerMove);
  element.designCutCanvas.addEventListener("pointerup", handleDesignCutPointerUp);
  element.designCutCanvas.addEventListener("keydown", handleDesignCutKeyDown);
  element.designCutCanvas.addEventListener("pointercancel", () => {
    state.designCutDraftStart = null;
    state.designCutDraftEnd = null;
    renderDesignCutEditor();
  });
  $("#clear-design-cut").addEventListener("click", () => {
    updateRoomDesignPreferences(state.activeDesignRoomId, (current) => ({
      ...current,
      confirmed: false,
      materialBoundary: null,
    }));
    state.designCutDraftStart = null;
    state.designCutDraftEnd = null;
    renderDesignRoomLocator();
    renderDesignMaterialCards();
    renderDesignCutEditor();
    invalidateGeneratedSchemesAfterDesignChange();
    scheduleSave("design_preferences");
  });
  $("#confirm-design-room").addEventListener("click", confirmActiveDesignRoom);
  $("#apply-design-room-to-all").addEventListener("click", applyActiveDesignRoomToUnconfirmed);
  $("#reset-rooms-to-baseline").addEventListener("click", resetUnconfirmedDesignRoomsToBaseline);
  element.designRoomMaterialNote.addEventListener("change", () => {
    captureDesignRoomMaterials();
    invalidateGeneratedSchemesAfterDesignChange();
    scheduleSave("design_preferences");
  });
  element.roomTechnicalPreferenceOptions.addEventListener("change", () => {
    renderRoomIntegratedSummary();
    scheduleDesignerQuestionnaireDraftSave();
  });
  $("#room-material-preferences").addEventListener("change", () => {
    captureDesignRoomMaterials();
    state.designPreferences = collectDesignPreferences();
    invalidateGeneratedSchemesAfterDesignChange();
    scheduleSave("design_preferences");
  });
  [
    element.designNotes,
    element.designWallSurface,
    element.designFloorSurface,
    element.designWallColor,
    element.designFloorColor,
  ].forEach((input) => input.addEventListener("change", () => {
    state.designPreferences = collectDesignPreferences();
    invalidateGeneratedSchemesAfterDesignChange();
    scheduleSave("design_preferences");
  }));
  $("#confirm-design-preferences").addEventListener("click", confirmDesignPreferences);
  element.layoutSchemeTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-layout-scheme]");
    if (button) activateLayoutScheme(button.dataset.layoutScheme);
  });
  $$("[data-layout-view]").forEach((button) => {
    button.addEventListener("click", () => setLayoutView(button.dataset.layoutView));
  });
  $("#search-workbench-glb").addEventListener("click", searchWorkbenchGlb);
  element.workbenchGlbResults.addEventListener("click", (event) => {
    const button = event.target.closest("[data-workbench-furniture-id]");
    if (button) replaceSelectedWorkbenchFurniture(button.dataset.workbenchFurnitureId);
  });
  $("#apply-workbench-materials").addEventListener("click", applyWorkbenchMaterials);
  $("#apply-workbench-cut").addEventListener(
    "click",
    () => updateWorkbenchMaterialBoundary(false),
  );
  $("#remove-workbench-cut").addEventListener(
    "click",
    () => updateWorkbenchMaterialBoundary(true),
  );
  element.workbenchCutSurface.addEventListener("change", () => {
    element.workbenchCutWallFace.closest("label").hidden =
      element.workbenchCutSurface.value !== "wall";
    renderSurfaceSelect(
      element.workbenchSecondarySurface,
      element.workbenchCutSurface.value,
      "",
      state.rooms.find((room) => room.id === state.activeLayoutRoomId)?.type,
    );
  });
  $("#auto-layout-furniture").addEventListener("click", async () => {
    if (autoLayoutPending || layoutConfirmationPending) return;
    const requestRevision = ++autoLayoutRequestRevision;
    setAutoLayoutPending(true);
    element.layoutError.textContent = "";
    try {
      setStatus("正在由家具引擎重新配置合法位置…");
      const requestedSchemeId = state.layoutSchemeSet?.activeSchemeId || null;
      const requestedScheme = activeScheme(state.layoutSchemeSet);
      const policy = requestedScheme?.policy || "balanced";
      const generatedFurniture = await autoLayoutFurniture(policy, {
        persist: false,
        targetSchemeId: requestedSchemeId,
      });
      if (
        requestRevision !== autoLayoutRequestRevision
        || state.workflow?.currentStep !== "layout_2d"
      ) {
        setStatus("已離開方案工作台，本次背景配置未套用。");
        return;
      }
      commitAutoLayoutFurniture(generatedFurniture, requestedSchemeId);
      const switchedDuringRequest =
        requestedSchemeId
        && state.layoutSchemeSet?.activeSchemeId !== requestedSchemeId;
      if (switchedDuringRequest) {
        setStatus(`${requestedScheme?.title || "原方案"}已在背景更新；目前方案不受影響。`);
        return;
      }
      setStatus(`家具引擎已重新配置 ${state.furniture2d.length} 件家具。`);
    } catch (error) {
      element.layoutError.textContent = errorMessage(error);
      setStatus(errorMessage(error), "error");
    } finally {
      setAutoLayoutPending(false);
    }
  });
  element.furnitureSearch.addEventListener("input", () => renderFurnitureLibrary(element.furnitureSearch.value));
  element.layoutRoomFilter.addEventListener("change", () => {
    state.activeLayoutRoomId = element.layoutRoomFilter.value || "all";
    renderLayoutFurniture();
    renderWorkbenchMaterialControls();
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
    invalidateDownstreamFrom("layout_2d", "2D 家具旋轉已修改，3D 白模與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#delete-2d-furniture").addEventListener("click", () => {
    state.furniture2d = state.furniture2d.filter((item) => item.id !== state.selectedFurniture2dId);
    state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
    renderLayoutRoomFilter();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具已刪除，3D 白模與即時寫實需要重新產生。");
    scheduleSave("layout_2d");
  });
  $("#confirm-layout-2d").addEventListener("click", confirmLayout2d);
  $$("[data-view-mode]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-view-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    whiteViewer.setViewMode(button.dataset.viewMode);
    $("#lock-view-for-edit").textContent = "鎖定視角並編輯家具";
  }));
  $("#lock-view-for-edit").addEventListener("click", (event) => {
    const locked = whiteViewer.toggleCameraLock();
    event.currentTarget.textContent = locked ? "結束家具編輯" : "鎖定視角並編輯家具";
  });
  $("#add-white-model-beam").addEventListener("click", beginWhiteModelBeamPlacement);
  $("#cancel-white-model-beam").addEventListener("click", cancelWhiteModelBeamPlacement);
  const selectSceneObject = (event) => {
    const button = event.target.closest("[data-scene-object-index]");
    if (!button) return;
    saveSelectedSceneAppearance();
    state.selectedSceneIndex = Number(button.dataset.sceneObjectIndex);
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    if (state.workflow.currentStep === "realistic_3d") {
      realisticViewer.selectObjectByIndex(state.selectedSceneIndex);
    } else {
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
    }
    scheduleSave(state.workflow.currentStep);
  };
  element.objectList.addEventListener("click", selectSceneObject);
  element.realisticObjectList?.addEventListener("click", selectSceneObject);
  $("#delete-white-model-furniture").addEventListener("click", deleteSelectedSceneFurniture);
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
  $("#search-glb-furniture").addEventListener("click", searchGlbFurniture);
  element.glbResults.addEventListener("click", (event) => {
    const replacementButton = event.target.closest("[data-replace-furniture-id]");
    if (replacementButton) {
      replaceSceneFurniture(replacementButton.dataset.replaceFurnitureId);
      return;
    }
    const addButton = event.target.closest("[data-add-furniture-id]");
    if (addButton) addSceneFurniture(addButton.dataset.addFurnitureId);
  });
  $("#confirm-white-model").addEventListener("click", confirmWhiteModel);
  element.styleTabs.addEventListener("pointerdown", (event) => {
    const button = event.target.closest("[data-style-tab]");
    if (!button) return;
    state.activeStyleId = button.dataset.styleTab;
    renderStyleControls();
  });
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
  element.renderRoomList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-render-room]");
    if (button) selectRenderRoom(button.dataset.renderRoom);
  });
  $("#save-room-view").addEventListener("click", saveSelectedRoomView);
  $("#submit-room-renders").addEventListener("click", submitRoomRenders);
  $("#apply-surface-colors").addEventListener("click", () => {
    markRealisticSceneEdited();
    applySurfaceOverrides();
  });
  [element.wallMaterialGrouped, element.floorMaterialGrouped].forEach((host) => {
    host?.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-surface-material]");
      if (!button) return;
      const kind = button.dataset.surfaceKind;
      const select = $(`#${kind}-material`);
      const color = $(`#${kind}-color`);
      if (select) select.value = button.dataset.surfaceMaterial;
      if (color && button.dataset.surfaceColor) color.value = button.dataset.surfaceColor;
      renderGroupedMaterialOptions(stylePackByIdSafe(state.activeStylePackId));
      await applySurfaceOverrides();
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
    setStatus("即時寫實方案已保存；請在第 9 步核對並鎖定比較視角。");
    goTo("proposal_review");
  });
  $$(".rp-progress button").forEach((button) => button.addEventListener("click", () => {
    const step = button.dataset.step;
    if (step === "recognition" && state.workflow?.canEnter("recognition")) {
      goTo(state.workflow.completed.includes("calibration") ? "calibration" : "recognition");
      return;
    }
    if (state.workflow?.canEnter(step)) goTo(step);
    else setStatus(firstWorkflowBlocker(step), "error");
  }));
  $("#reset-project").addEventListener("click", () => {
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

async function restoreProject() {
  if (!state.projectId) {
    state.workflow = null;
    showStep("project");
    return;
  }
  try {
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
          localStorage.setItem(conflictedSaveStorageKey(), pendingSave);
          result = await api(`/api/projects/${state.projectId}`);
        }
      } else {
        pendingSaveDiscarded = true;
        removePendingSave = true;
        localStorage.setItem(conflictedSaveStorageKey(), pendingSave);
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
      element.recognitionSummary.textContent = `辨識結果：牆 ${state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0}、門 ${state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0}、窗 ${state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0}`;
      element.uploadFileState.textContent =
        state.analysis.filename || state.workflow.data.upload?.filename || "已上傳平面圖";
    }
    const savedSpace = normalizeSavedSpaceConfirmation(serverState.space_confirmation || {});
    state.rooms = savedSpace.rooms;
    state.structures = serverState.space_confirmation
      ? savedSpace.structures
      : state.structures;
    const lockedWallCandidates = normalizeWallDemolitionCandidates();
    repairLoadedStructureWallCollisions();
    const normalizedWindows = dedupeWindowCandidates(state.structures.windows || []);
    state.structures.windows = normalizedWindows.windows;
    state.windowNormalizationRemoved = normalizedWindows.removed;
    state.basicAnswers = serverState.requirements?.basic || {};
    state.basicConfirmed = serverState.requirements?.basicConfirmed === true;
    const reconciledQuestionnaire = reconcileRoomQuestionnaireState({
      rooms: state.rooms,
      answers: serverState.requirements?.rooms || {},
      keepExistingRoomIds: serverState.requirements?.keepExistingRoomIds || [],
    });
    state.roomAnswers = reconciledQuestionnaire.answers;
    state.keepExistingRoomIds = reconciledQuestionnaire.keepExistingRoomIds;
    state.questionnaireMode = serverState.requirements?.mode || "designer_together";
    state.minimumFinishedHeightCm = Number(
      serverState.requirements?.settings?.minimumFinishedHeightCm || 240
    );
    state.designerQuestionnaireNotes = serverState.requirements?.designerNotes || "";
    element.questionnaireMode.value = state.questionnaireMode;
    element.designerQuestionnaireNotes.value = state.designerQuestionnaireNotes;
    updateDesignerNoteState();
    state.designPreferences = normalizeDesignPreferences(
      serverState.design_preferences || {},
    );
    state.layoutSchemeSet = serverState.layout_2d?.schemeSet || null;
    if (
      state.layoutSchemeSet
      && serverState.layout_2d?.activeSchemeId
      && state.layoutSchemeSet.schemes?.some(
        (scheme) => scheme.id === serverState.layout_2d.activeSchemeId,
      )
    ) {
      state.layoutSchemeSet.activeSchemeId = serverState.layout_2d.activeSchemeId;
    }
    state.furniture2d = serverState.layout_2d?.furniture || [];
    state.sceneData = normalizeSavedSceneData(serverState.white_model_3d?.sceneData);
    state.activeStylePackId = serverState.realistic_3d?.activeStylePackId || null;
    state.surfaceState = serverState.realistic_3d?.surfaceState || state.surfaceState;
    state.materialBoundary = serverState.realistic_3d?.materialBoundary || null;
    const legacyDownstreamWithoutPreferences = !state.designPreferences.styleId
      && ["layout_2d", "white_model_3d", "realistic_3d"].includes(
        state.workflow.currentStep,
      );
    if (legacyDownstreamWithoutPreferences) {
      const moved = state.workflow.goTo("design_preferences");
      if (!moved) state.workflow.goTo("requirements");
    }
    state.sourceExtension = floorplanExtension({
      name: state.analysis?.filename || state.workflow.data.upload?.filename || "",
    });
    await recoverConfirmedFloorplan();
    updateCeilingHeightReference();
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
    if (legacyDownstreamWithoutPreferences) {
      scheduleSave(state.workflow.currentStep);
      setStatus("此專案建立於材質偏好加入前；請在步驟 6 最後確認材質，再重新產生三案。");
    }
    const conflictedSave = localStorage.getItem(conflictedSaveStorageKey());
    if (conflictedSave) showSaveConflict(conflictedSave);
    if (state.confirmedFloorplan && !serverState.confirmed_floorplan) {
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
    setStatus(pendingSaveDiscarded
      ? `已恢復專案「${state.project.name}」；離線編輯已保留，請選擇是否合併。`
      : `已恢復專案「${state.project.name}」。`);
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
