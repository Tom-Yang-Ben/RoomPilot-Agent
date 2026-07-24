import { createSceneViewer } from "./scene_viewer.js?v=sha256-cd1d1c887478";
import { resolveSurfaceOption } from "./scene_surface_materials.js?v=20260719-real3d3";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-3372a900aa79";
import {
  repairLoadedRoomPolygon,
} from "./scene_room_geometry.js?v=sha256-de1617c48879";
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
} from "./scene_calibration.js?v=sha256-66046852b468";
import {
  createFurniture2DItem,
  FURNITURE_2D_LIBRARY,
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  planCmToLayerPixel,
  recommendCompanionFurniture,
  recommendedFurnitureForRoom,
  mergeCatalogFurniture,
  replaceFurniture2DItem,
  toSceneFurniture,
} from "./scene_layout2d.js?v=sha256-35d1bfd9747d";
import {
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-cb53bf0d6e51";
import {
  applyVisualPreferencesToSpecs,
  finishesGate,
  occupantsFromBasicAnswers,
  questionnaireSummary,
  questionsForRooms,
  visualQuestionnaireProgress,
  VISUAL_SPACE_LABELS,
} from "./scene_questionnaire_test2.js?v=20260724-reviewfix1";
import {
  applyStylePack,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=20260719-actual-palettes";
import {
  beamDragGeometry,
  canMarkWallForDemolition,
  dedupeWindowCandidates,
  wallBoundarySide,
  windowsOverlap,
} from "./scene_structure_utils.js?v=sha256-f247d8fca27b";
import { createStructurePreview } from "./scene_structure_preview.js?v=sha256-33fb11f45a21";
import {
  findStructureWallCollision,
  resolveStructureWallCollisions,
  validateColumnDimensionsCm,
} from "./scene_structure_geometry.js?v=sha256-ebc6332ca3c4";
import { buildDimensionedPlanAnnotations } from "./scene_dimensioned_plan.js?v=20260723-dimensioned-plan1";
import {
  applyWindowTypePreset,
  normalizedWindowType,
  WINDOW_TYPES,
} from "./scene_window_types.js?v=sha256-ebe4923f97c0";

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
  questionnaireStage: "profile",
  visualCatalog: null,
  visualCatalogVersion: null,
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
let visualCustomSaveTimer = null;

const panels = new Map(
  $$(".rp-step-panel").map((panel) => [panel.dataset.panel, panel]),
);

const instructions = {
  project: ["步驟 1", "先建立專案，之後每一次確認都會自動保存"],
  upload: ["步驟 2", "選擇 DXF、PNG 或 JPG，並確認圖檔內容"],
  recognition: ["步驟 3", "拖曳尺寸線兩端，只輸入一個實際公分尺寸"],
  calibration: ["步驟 3", "確認尺度後，才會顯示辨識到的房間"],
  space_confirmation: ["步驟 4", "先確認房間，再確認牆、門、窗、樑與柱"],
  requirements: ["步驟 5", "完成基本資料、逐房極與極需求及風格材質"],
  layout_2d: ["步驟 6", "確認家具形式、實際尺寸、位置與淨空"],
  white_model_3d: ["步驟 7", "確認 3D 白模家具可見，再指定模型、顏色與材質"],
  realistic_3d: ["步驟 8", "從 18 張色卡切換完整 PBR StylePack"],
  proposal_review: ["步驟 9", "核對完整方案，最後再鎖定色卡比較視角"],
  ai_render: ["步驟 10", "先比對色卡，再逐房間保存視角並送出渲染"],
};

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
  requirementsProgress: $("#requirements-progress"),
  requirementsError: $("#requirements-error"),
  confirmRequirements: $("#confirm-requirements"),
  questionnaireStageNav: $("#questionnaire-stage-nav"),
  visualSpaceNav: $("#visual-space-nav"),
  visualQuestionProgress: $("#visual-question-progress"),
  visualQuestionCard: $("#visual-question-card"),
  visualCustomAnswer: $("#visual-custom-answer"),
  questionnaireStyleTabs: $("#questionnaire-style-tabs"),
  questionnaireStyleGrid: $("#questionnaire-style-grid"),
  questionnaireWallOptions: $("#questionnaire-wall-options"),
  questionnaireFloorOptions: $("#questionnaire-floor-options"),
  questionnaireWallColor: $("#questionnaire-wall-color"),
  questionnaireFloorColor: $("#questionnaire-floor-color"),
  questionnaireCeilingMaterial: $("#questionnaire-ceiling-material"),
  questionnaireCeilingStyle: $("#questionnaire-ceiling-style"),
  questionnaireLightStyle: $("#questionnaire-light-style"),
  questionnaireCeilingColor: $("#questionnaire-ceiling-color"),
  questionnaireSummary: $("#questionnaire-summary-content"),
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
  const requirementsAreLive = stepIsLive("requirements")
    || WORKFLOW_STEPS.slice(WORKFLOW_STEPS.indexOf("layout_2d"))
      .some((step) => stepIsLive(step));
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
          questionnaireStage: state.questionnaireStage,
          visualCatalogVersion: state.visualCatalogVersion,
          visualAnswers: state.visualAnswers,
          skippedVisualSpaceTypes: state.skippedVisualSpaceTypes,
          finishes: state.questionnaireFinishes,
        }
      : null,
    layout_2d: layoutIsLive ? { furniture: state.furniture2d } : null,
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
      const result = await response.json();
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
    state.sceneData = null;
    state.furniture2d = [];
    state.surfaceState = { wall: {}, floor: {}, furniture: [] };
    state.activeStylePackId = null;
    state.materialBoundary = null;
  } else if (step === "requirements") {
    state.sceneData = null;
    state.furniture2d = [];
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
  $$(".rp-progress button").forEach((button) => {
    const target = button.dataset.step;
    const targetIndex = WORKFLOW_STEPS.indexOf(target);
    const currentIndex = WORKFLOW_STEPS.indexOf(step);
    button.classList.toggle("is-active", activePanelName(target) === panelName);
    button.classList.toggle("is-complete", targetIndex >= 0 && targetIndex < currentIndex);
  });
  requestAnimationFrame(syncAllOverlays);
}

async function renderRestoredStep() {
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
  [element.scaleImage, element.spaceImage, element.layoutImage]
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
  syncLayoutLayer();
  renderCalibration();
  renderSpaceOverlay();
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

const QUESTIONNAIRE_STAGES = Object.freeze([
  "profile",
  "rooms",
  "finishes",
  "summary",
]);

async function prepareQuestionnaireStep() {
  renderWholeHouseQuestionnaire();
  if (state.basicConfirmed) {
    try {
      await ensureVisualQuestionnaireLoaded();
    } catch (error) {
      element.requirementsError.textContent = errorMessage(error);
      state.questionnaireStage = "rooms";
    }
  }
  showQuestionnaireStage(state.questionnaireStage);
}

function questionnaireStageUnlocked(stage) {
  if (stage === "profile") return true;
  if (!state.basicConfirmed) return false;
  if (stage === "rooms") return true;
  const visualProgress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  if (stage === "finishes") return visualProgress.ready;
  return visualProgress.ready && finishesGate(state.questionnaireFinishes).ready;
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
    profile: "基本資料",
    rooms: `逐房極與極 ${visualQuestionnaireProgress({
      questions: state.visualQuestions,
      answers: state.visualAnswers,
      skippedSpaceTypes: state.skippedVisualSpaceTypes,
    }).completed} / ${state.visualQuestions.length}`,
    finishes: "風格與材質",
    summary: "確認摘要",
  };
  element.requirementsProgress.textContent = labels[nextStage];
  element.requirementsError.textContent = "";
  if (nextStage === "rooms") {
    renderVisualQuestionnaire();
  } else if (nextStage === "finishes") {
    renderQuestionnaireFinishes();
  } else if (nextStage === "summary") {
    renderQuestionnaireSummary();
  }
  scheduleSave("requirements");
}

async function ensureVisualQuestionnaireLoaded() {
  if (state.visualCatalog) return;
  const catalog = await api("/api/questionnaire/visual-catalog");
  const restoredCatalogVersion = state.visualCatalogVersion;
  state.visualCatalog = catalog;
  state.visualQuestions = questionsForRooms(catalog.questions || [], state.rooms);
  if (
    restoredCatalogVersion
    && restoredCatalogVersion !== catalog.version
  ) {
    state.visualAnswers = {};
    state.skippedVisualSpaceTypes = [];
    state.questionnaireStage = "rooms";
    invalidateDownstreamFrom(
      "requirements",
      "極與極題庫已更新，後續 2D、3D 與渲染結果需要重新確認。",
    );
    setStatus("極與極題庫已更新，請重新確認視覺偏好。");
  }
  state.visualCatalogVersion = catalog.version;
  const validOptions = new Map(
    state.visualQuestions.map((question) => [
      question.question_id,
      new Set([
        ...question.options.map((option) => option.option_id),
        ...(question.allow_both ? ["both"] : []),
      ]),
    ]),
  );
  state.visualAnswers = Object.fromEntries(
    Object.entries(state.visualAnswers).filter(
      ([questionId, answer]) => validOptions.get(questionId)?.has(answer?.optionId),
    ),
  );
  const validSpaceTypes = new Set(
    state.visualQuestions.map((question) => question.space_type),
  );
  state.skippedVisualSpaceTypes = state.skippedVisualSpaceTypes.filter(
    (spaceType) => validSpaceTypes.has(spaceType),
  );
  state.visualQuestionIndex = Math.min(
    state.visualQuestionIndex,
    Math.max(0, state.visualQuestions.length - 1),
  );
  $("#visual-questionnaire-notice").textContent =
    `${catalog.question_count} 組題目介面已建立；目前 ${catalog.ready_image_count} 張圖片完成，其餘可先依文字作答。`;
}

function visualQuestionAt(index = state.visualQuestionIndex) {
  return state.visualQuestions[index] || null;
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
      engine_effects: option?.engine_effects || {},
    }];
  });
}

function visualPreferencesForRoom(room) {
  if (room.type === "bedroom") {
    const bedroomIndex = state.rooms
      .filter((candidate) => candidate.type === "bedroom")
      .findIndex((candidate) => candidate.id === room.id);
    const bedroomSpace = bedroomIndex <= 0
      ? "primary_bedroom"
      : "secondary_bedroom";
    return resolvedVisualPreferences(
      state.visualQuestions.filter(
        (question) => question.space_type === bedroomSpace
          || question.space_type === "all_rooms"
          || question.space_type === "circulation",
      ),
    );
  }
  return resolvedVisualPreferences(questionsForRooms(state.visualQuestions, [room]));
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

function renderVisualSpaceNav() {
  const spaces = [...new Set(state.visualQuestions.map((question) => question.space_type))];
  const current = visualQuestionAt();
  element.visualSpaceNav.innerHTML = spaces.map((spaceType) => {
    const questions = state.visualQuestions.filter(
      (question) => question.space_type === spaceType,
    );
    const completed = questions.filter(
      (question) => state.visualAnswers[question.question_id]?.optionId,
    ).length;
    const skipped = state.skippedVisualSpaceTypes.includes(spaceType);
    return `
      <button type="button" data-visual-space="${escapeHtml(spaceType)}"
        class="${spaceType === current?.space_type ? "is-active" : ""}"
        aria-current="${spaceType === current?.space_type ? "true" : "false"}">
        <strong>${escapeHtml(VISUAL_SPACE_LABELS[spaceType] || spaceType)}</strong>
        <small>${skipped ? "暫不作答" : `${completed} / ${questions.length}`}</small>
      </button>
    `;
  }).join("");
}

function renderVisualQuestionnaire() {
  const question = visualQuestionAt();
  if (!question) {
    element.visualQuestionCard.innerHTML = "<p>目前辨識到的空間沒有對應題目。</p>";
    element.visualQuestionProgress.textContent = "0 / 0";
    return;
  }
  const answer = state.visualAnswers[question.question_id] || {};
  const optionMarkup = question.options.map((option) => {
    const hasImage = option.generation_status === "ready";
    return `
      <button type="button" class="rp-visual-option ${answer.optionId === option.option_id ? "is-selected" : ""}"
        data-visual-option="${escapeHtml(option.option_id)}"
        aria-pressed="${answer.optionId === option.option_id}">
        <span class="rp-visual-option-media">
          ${hasImage
            ? `<img src="${escapeHtml(option.image_url)}" alt="${escapeHtml(option.label_zh)}" loading="lazy">`
            : `<span class="rp-visual-image-pending">圖片待補<br><small>先依文字選擇</small></span>`}
        </span>
        <strong>${escapeHtml(option.label_zh)}</strong>
        <small>${escapeHtml(option.visual_brief_zh)}</small>
      </button>
    `;
  }).join("");
  element.visualQuestionCard.innerHTML = `
    <span class="eyebrow">${escapeHtml(VISUAL_SPACE_LABELS[question.space_type] || question.space_type)}</span>
    <h3>${escapeHtml(question.title_zh)}</h3>
    <p>${escapeHtml(question.purpose_zh)}</p>
    <div class="rp-visual-options">${optionMarkup}</div>
    ${question.allow_both ? `
      <button type="button" class="rp-visual-balance ${answer.optionId === "both" ? "is-selected" : ""}"
        data-visual-option="both" aria-pressed="${answer.optionId === "both"}">兩者平衡／依補充條件調整</button>
    ` : ""}
  `;
  element.visualCustomAnswer.placeholder = question.custom_input_example_zh || "";
  element.visualCustomAnswer.value = answer.custom || "";
  element.visualQuestionProgress.textContent =
    `第 ${state.visualQuestionIndex + 1} 題，共 ${state.visualQuestions.length} 題`;
  $("#visual-question-back").disabled = state.visualQuestionIndex === 0;
  $("#visual-question-next").textContent =
    state.visualQuestionIndex === state.visualQuestions.length - 1
      ? "完成極與極偏好"
      : "下一題";
  renderVisualSpaceNav();
}

function selectVisualOption(optionId) {
  const question = visualQuestionAt();
  if (!question) return;
  state.skippedVisualSpaceTypes = state.skippedVisualSpaceTypes.filter(
    (spaceType) => spaceType !== question.space_type,
  );
  state.visualAnswers[question.question_id] = {
    optionId,
    custom: element.visualCustomAnswer.value.trim(),
  };
  renderVisualQuestionnaire();
  invalidateDownstreamFrom("requirements", "視覺偏好已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
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
  const nextIndex = state.visualQuestionIndex + offset;
  if (nextIndex >= 0 && nextIndex < state.visualQuestions.length) {
    state.visualQuestionIndex = nextIndex;
    renderVisualQuestionnaire();
    return;
  }
  const progress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  if (progress.ready) {
    showQuestionnaireStage("finishes");
  }
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

function activeQuestionnairePack() {
  return STYLE_PACKS.find(
    (pack) => pack.id === state.questionnaireFinishes.stylePackId,
  ) || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId) || STYLE_PACKS[0];
}

function renderQuestionnaireMaterialOptions(kind, pack) {
  const host = kind === "wall"
    ? element.questionnaireWallOptions
    : element.questionnaireFloorOptions;
  const selectedKey = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const options = STYLE_MATERIAL_OPTIONS[pack.styleId]?.[kind] || [];
  host.innerHTML = options.map((option) => `
    <button type="button" data-questionnaire-material="${escapeHtml(kind)}"
      data-questionnaire-material-id="${escapeHtml(option.id)}"
      class="${state.questionnaireFinishes[selectedKey] === option.id ? "is-active" : ""}"
      aria-pressed="${state.questionnaireFinishes[selectedKey] === option.id}">
      <span class="rp-material-preview" style="background:${escapeHtml(option.color)};background-image:url('${escapeHtml(option.materialPreview)}')"></span>
      <strong>${escapeHtml(option.label)}</strong>
      <small>${escapeHtml(option.note)}</small>
    </button>
  `).join("");
}

function renderQuestionnaireFinishes() {
  const styles = [...new Map(
    STYLE_PACKS.map((pack) => [pack.styleId, pack.styleLabel]),
  ).entries()];
  element.questionnaireStyleTabs.innerHTML = styles.map(([styleId, label]) => `
    <button type="button" data-questionnaire-style="${escapeHtml(styleId)}"
      class="${styleId === state.activeStyleId ? "is-active" : ""}"
      aria-pressed="${styleId === state.activeStyleId}">${escapeHtml(label)}</button>
  `).join("");
  const packs = STYLE_PACKS.filter((pack) => pack.styleId === state.activeStyleId);
  element.questionnaireStyleGrid.innerHTML = packs.map((pack) => `
    <button type="button" data-questionnaire-style-pack="${escapeHtml(pack.id)}"
      class="${pack.id === state.questionnaireFinishes.stylePackId ? "is-active" : ""}"
      aria-pressed="${pack.id === state.questionnaireFinishes.stylePackId}">
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}"
        alt="${escapeHtml(`${pack.styleLabel} ${pack.name}參考圖`)}" loading="lazy">
      <span class="rp-style-swatches">${pack.palette
        .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
        .join("")}</span>
      <strong>${escapeHtml(pack.name)}</strong>
    </button>
  `).join("");
  const pack = activeQuestionnairePack();
  renderQuestionnaireMaterialOptions("wall", pack);
  renderQuestionnaireMaterialOptions("floor", pack);
  element.questionnaireWallColor.value =
    state.questionnaireFinishes.wallColor || pack.wall.color;
  element.questionnaireFloorColor.value =
    state.questionnaireFinishes.floorColor || pack.floor.color;
  element.questionnaireCeilingMaterial.value =
    state.questionnaireFinishes.ceilingMaterial || "flat-paint";
  element.questionnaireCeilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireLightStyle.innerHTML = LIGHT_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireCeilingStyle.value =
    state.questionnaireFinishes.ceilingStyle
    || CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || CEILING_STYLES[0].id;
  element.questionnaireLightStyle.value =
    state.questionnaireFinishes.lightStyle
    || LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || LIGHT_STYLES[0].id;
  element.questionnaireCeilingColor.value =
    state.questionnaireFinishes.ceilingColor || "#f4f1eb";
}

function selectQuestionnaireStylePack(packId) {
  const pack = STYLE_PACKS.find((candidate) => candidate.id === packId);
  if (!pack) return;
  state.activeStyleId = pack.styleId;
  state.questionnaireFinishes = {
    ...state.questionnaireFinishes,
    confirmed: false,
    stylePackId: pack.id,
    wallMaterial: pack.wall.surfaceOption,
    wallColor: pack.wall.color,
    floorMaterial: pack.floor.surfaceOption,
    floorColor: pack.floor.color,
    ceilingMaterial: "flat-paint",
    ceilingStyle: CEILING_STYLES.find(
      (item) => item.styles.includes(pack.styleId),
    )?.id || CEILING_STYLES[0].id,
    lightStyle: LIGHT_STYLES.find(
      (item) => item.styles.includes(pack.styleId),
    )?.id || LIGHT_STYLES[0].id,
  };
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function confirmQuestionnaireFinishes() {
  if (!state.questionnaireFinishes.stylePackId) {
    element.requirementsError.textContent = "請先選擇一張風格色卡，再確認牆壁、地板與天花板設定。";
    element.questionnaireStyleGrid.scrollIntoView({ block: "center" });
    return;
  }
  const pack = activeQuestionnairePack();
  state.questionnaireFinishes = {
    ...state.questionnaireFinishes,
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial: state.questionnaireFinishes.wallMaterial || pack.wall.surfaceOption,
    wallColor: element.questionnaireWallColor.value,
    floorMaterial: state.questionnaireFinishes.floorMaterial || pack.floor.surfaceOption,
    floorColor: element.questionnaireFloorColor.value,
    ceilingMaterial: element.questionnaireCeilingMaterial.value,
    ceilingStyle: element.questionnaireCeilingStyle.value,
    lightStyle: element.questionnaireLightStyle.value,
    ceilingColor: element.questionnaireCeilingColor.value,
  };
  element.requirementsError.textContent = "";
  invalidateDownstreamFrom("requirements", "風格與材質偏好已修改，後續配置需要重新產生。");
  state.activeStylePackId = pack.id;
  showQuestionnaireStage("summary");
}

function renderQuestionnaireSummary() {
  const summary = questionnaireSummary({
    basic: state.basicAnswers,
    visualQuestions: state.visualQuestions,
    visualAnswers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
    finishes: state.questionnaireFinishes,
    stylePacks: STYLE_PACKS,
  });
  const basicRows = WHOLE_HOUSE_QUESTIONS.map((question) =>
    `<div><span>${escapeHtml(question.label)}</span><strong>${escapeHtml(summary.basic[question.id] || "未填")}</strong></div>`
  ).join("");
  const visualRows = summary.visualSelections.map((item) =>
    `<li><span>${escapeHtml(item.question)}</span><strong>${escapeHtml(item.answer)}</strong>${item.custom ? `<small>${escapeHtml(item.custom)}</small>` : ""}</li>`
  ).join("");
  element.questionnaireSummary.innerHTML = `
    <section><h4>全屋基本資料</h4><div class="rp-questionnaire-summary-grid">${basicRows}</div></section>
    <section><h4>逐房極與極需求</h4><p>已回答 ${summary.answeredSpaceCount} 類空間；${summary.skippedSpaceCount} 類空間暫不規劃。</p><ul>${visualRows || "<li>本案沒有對應的極與極題目。</li>"}</ul></section>
    <section><h4>風格與材質</h4>
      <p><strong>${escapeHtml(summary.finishes.style)}</strong></p>
      <p>牆壁 ${escapeHtml(summary.finishes.wallMaterial)} ${escapeHtml(summary.finishes.wallColor)}／地板 ${escapeHtml(summary.finishes.floorMaterial)} ${escapeHtml(summary.finishes.floorColor)}／天花板 ${escapeHtml(summary.finishes.ceilingMaterial)}、${escapeHtml(summary.finishes.ceilingStyle)}／照明 ${escapeHtml(summary.finishes.lightStyle)}</p>
    </section>
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
  const missing = WHOLE_HOUSE_QUESTIONS.find(
    (question) => question.required !== false && !answers[question.id],
  );
  if (missing) {
    element.requirementsError.textContent = `請完成「${missing.label}」。`;
    $(`[data-basic-question="${missing.id}"]`)?.scrollIntoView({ block: "center" });
    return;
  }
  state.basicAnswers = answers;
  state.basicConfirmed = true;
  try {
    await ensureVisualQuestionnaireLoaded();
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    return;
  }
  showQuestionnaireStage("rooms");
  scheduleSave("requirements");
}

async function confirmRequirements() {
  element.requirementsError.textContent = "";
  const visualProgress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  if (!state.basicConfirmed || !visualProgress.ready
      || !finishesGate(state.questionnaireFinishes).ready) {
    element.requirementsError.textContent = "請先完成基本資料、逐房極與極需求，以及風格材質確認。";
    return;
  }
  try {
    setStatus("正在由家具引擎依房間需求計算 2D 合法位置…");
    await autoLayoutFurniture();
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
      visualPreferencesResolved: true,
      finishesConfirmed: true,
    });
    renderFurnitureLibrary();
    setStatus(state.furniture2d.length
      ? `需求已完成，家具引擎已配置 ${state.furniture2d.length} 件 2D 家具。`
      : "需求已完成，所有房間都選擇無家具或維持現狀。");
    goTo("layout_2d");
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

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

async function autoLayoutFurniture() {
  state.furniture2d = [];
  for (const room of state.rooms) {
    const requestedSpecs = recommendedFurnitureForRoom(room);
    const visualPreferences = visualPreferencesForRoom(room);
    const preferredSpecs = applyVisualPreferencesToSpecs(
      requestedSpecs,
      visualPreferences,
    );
    const companionSpecs = recommendCompanionFurniture(
      room.type,
      preferredSpecs.map(([type]) => type),
    ).map((item) => [item.type, item.variantId, item.reason, true]);
    const specs = [...preferredSpecs, ...companionSpecs];
    const placementPreferences = Object.assign(
      {},
      ...visualPreferences.map((preference) => preference.engine_effects),
    );
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
            basic_answers: state.basicAnswers,
            visual_preferences: visualPreferences,
            finishes: state.questionnaireFinishes,
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
          userRequired: false,
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
        placement_preferences: placementPreferences,
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
      state.furniture2d.push(item);
    });
  }
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  state.activeLayoutRoomId = "all";
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  scheduleSave("layout_2d");
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
    const selectedFurniture = await Promise.all(state.furniture2d.map(resolveCatalogFurniture));
    const firstRoom = state.rooms.find((room) => room.type === "living_room") || state.rooms[0];
    const dimensions = roomDimensions(firstRoom);
    const preferredPack = activeQuestionnairePack();
    const visualPreferences = resolvedVisualPreferences();
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
        },
        personal_notes: state.basicAnswers.immutableNeeds || "",
        floorplan_filename: `${state.projectId}-confirmed.dxf`,
        floorplan_editor: confirmedFloorplanEditor(),
        room_width_cm: dimensions.widthCm,
        room_depth_cm: dimensions.depthCm,
        required_furniture: [...new Set(state.furniture2d.map((item) => item.type))],
        selected_furniture: selectedFurniture,
        selected_furniture_exact: true,
      }),
    });
    state.sceneData = payload;
    state.sceneData.questionnaire = {
      catalog_version: state.visualCatalogVersion,
      basic: state.basicAnswers,
      visual_preferences: visualPreferences,
      finishes: state.questionnaireFinishes,
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
  const customPreferenceCount = Object.values(state.visualAnswers || {}).filter(
    (answer) => String(answer?.custom || "").trim(),
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
  const visualProgress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  if (!visualProgress.ready) {
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
      visual_preferences: state.visualAnswers,
      finishes: state.questionnaireFinishes,
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
  element.questionnaireStageNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-questionnaire-stage]");
    if (button && !button.disabled) showQuestionnaireStage(button.dataset.questionnaireStage);
  });
  element.visualSpaceNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-visual-space]");
    if (!button) return;
    if (saveVisualCustomAnswer()) scheduleSave("requirements");
    const index = state.visualQuestions.findIndex(
      (question) => question.space_type === button.dataset.visualSpace,
    );
    if (index >= 0) {
      state.visualQuestionIndex = index;
      renderVisualQuestionnaire();
    }
  });
  element.visualQuestionCard.addEventListener("click", (event) => {
    const option = event.target.closest("[data-visual-option]");
    if (option) selectVisualOption(option.dataset.visualOption);
  });
  element.visualCustomAnswer.addEventListener("input", () => {
    if (!saveVisualCustomAnswer()) return;
    capturePendingSave("requirements");
    clearTimeout(visualCustomSaveTimer);
    visualCustomSaveTimer = setTimeout(() => {
      visualCustomSaveTimer = null;
      scheduleSave("requirements");
    }, 450);
  });
  $("#visual-question-back").addEventListener("click", () => moveVisualQuestion(-1));
  $("#visual-question-next").addEventListener("click", () => moveVisualQuestion(1));
  $("#skip-visual-space").addEventListener("click", skipCurrentVisualSpace);
  $("#questionnaire-finishes-back").addEventListener("click", () => showQuestionnaireStage("rooms"));
  $("#questionnaire-summary-back").addEventListener("click", () => showQuestionnaireStage("finishes"));
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
      state.questionnaireFinishes[key] = button.dataset.questionnaireMaterialId;
      const pack = activeQuestionnairePack();
      const option = STYLE_MATERIAL_OPTIONS[pack.styleId]?.[
        button.dataset.questionnaireMaterial
      ]?.find((candidate) => candidate.id === button.dataset.questionnaireMaterialId);
      if (option?.color) state.questionnaireFinishes[colorKey] = option.color;
      state.questionnaireFinishes.confirmed = false;
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
  ].forEach(([control, key]) => {
    control.addEventListener("change", () => {
      state.questionnaireFinishes[key] = control.value;
      state.questionnaireFinishes.confirmed = false;
      scheduleSave("requirements");
    });
  });
  $("#confirm-questionnaire-finishes").addEventListener("click", confirmQuestionnaireFinishes);
  element.confirmRequirements.addEventListener("click", confirmRequirements);
  $("#auto-layout-furniture").addEventListener("click", async () => {
    element.layoutError.textContent = "";
    try {
      setStatus("正在由家具引擎重新配置合法位置…");
      await autoLayoutFurniture();
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
    const savedQuestionnaireStage = serverState.requirements?.questionnaireStage;
    state.questionnaireStage = (savedQuestionnaireStage === "visual"
      ? "rooms"
      : savedQuestionnaireStage) || (
      state.basicConfirmed ? "rooms" : "profile"
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
    const questionnairePack = STYLE_PACKS.find(
      (pack) => pack.id === state.questionnaireFinishes.stylePackId,
    );
    if (questionnairePack) state.activeStyleId = questionnairePack.styleId;
    state.furniture2d = serverState.layout_2d?.furniture || [];
    state.sceneData = normalizeSavedSceneData(serverState.white_model_3d?.sceneData);
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
      ? `已恢復專案「${state.project.name}」；較舊的離線暫存未覆蓋目前版本。`
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
