import { createSceneViewer } from "./scene_viewer.js?v=20260719-real3d5";
import { resolveSurfaceOption } from "./scene_surface_materials.js?v=20260719-real3d3";
import {
  createWorkflow,
  restoreWorkflow,
  WORKFLOW_PANEL_BY_STEP,
  WORKFLOW_STEPS,
} from "./scene_workflow.js?v=20260717-test1b";
import { buildScaleCalibration } from "./scene_calibration.js?v=20260717-test1";
import {
  createFurniture2DItem,
  FURNITURE_2D_LIBRARY,
  furnitureFootprintStyle,
  recommendCompanionFurniture,
  replaceFurniture2DItem,
  toSceneFurniture,
} from "./scene_layout2d.js?v=20260717-test1e";
import {
  requirementsGate,
  roomQuestionTemplate,
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=20260717-test1";
import {
  applyStylePack,
  CEILING_STYLES,
  detectCeilingConflicts,
  LIGHT_STYLES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=20260718-stylelive1";

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
  structures: { walls: [], doors: [], windows: [], beams: [], columns: [] },
  structureTool: null,
  structureLineStart: null,
  selectedStructure: null,
  basicAnswers: {},
  basicConfirmed: false,
  roomAnswers: {},
  keepExistingRoomIds: [],
  activeQuestionRoomId: null,
  furniture2d: [],
  selectedFurniture2dId: null,
  sceneData: null,
  selectedSceneIndex: 0,
  styleHistory: [],
  activeStyleId: "scandinavian",
  activeStylePackId: null,
  surfaceState: { wall: {}, floor: {}, furniture: [] },
  materialBoundary: null,
};
let styleApplyRevision = 0;

const panels = new Map(
  $$(".rp-step-panel").map((panel) => [panel.dataset.panel, panel]),
);

const instructions = {
  project: ["步驟 1", "先建立專案，之後每一次確認都會自動保存"],
  upload: ["步驟 2", "選擇 DXF、PNG 或 JPG，並確認資料用途"],
  recognition: ["步驟 3–4", "拖曳尺寸線兩端，只輸入一個實際公分尺寸"],
  calibration: ["步驟 3–4", "確認尺度後，才會顯示 Cody 辨識的房間"],
  space_confirmation: ["步驟 5", "先確認房間，再確認牆、門、窗、梁與柱"],
  requirements: ["步驟 6", "先完成全屋基本問卷，再逐房間填需求"],
  layout_2d: ["步驟 7", "確認家具形式、實際尺寸、位置與淨空"],
  white_model_3d: ["步驟 8", "確認 3D 白模家具可見，再指定模型、顏色與材質"],
  realistic_3d: ["步驟 9", "從 18 張色卡切換完整 PBR StylePack"],
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
  uploadFileState: $("#upload-file-state"),
  uploadError: $("#upload-error"),
  consent: $("#project-privacy-consent"),
  scaleImage: $("#floorplan-calibration-image"),
  scaleStage: $("#floorplan-calibration-stage"),
  scaleOverlay: $("#floorplan-calibration-overlay"),
  scaleInput: $("#floorplan-scale-cm"),
  calibrationReadout: $("#calibration-readout"),
  scaleError: $("#scale-error"),
  recognitionSummary: $("#recognition-summary"),
  spaceImage: $("#space-plan-image"),
  spaceStage: $("#space-plan-stage"),
  spaceOverlay: $("#space-plan-overlay"),
  roomList: $("#room-list"),
  roomEditor: $("#room-editor"),
  roomName: $("#room-name"),
  roomWidth: $("#room-width-cm"),
  roomDepth: $("#room-depth-cm"),
  roomArea: $("#room-area"),
  structureCounts: $("#structure-counts"),
  structureEditor: $("#selected-structure-editor"),
  spaceError: $("#space-error"),
  requirementsImage: $("#requirements-plan-image"),
  requirementsStage: $("#requirements-plan-stage"),
  requirementsOverlay: $("#requirements-plan-overlay"),
  wholeHouseFields: $("#whole-house-fields"),
  roomQuestionNav: $("#room-question-nav"),
  roomQuestionTitle: $("#room-question-title"),
  roomUseOptions: $("#room-use-options"),
  roomFurnitureOptions: $("#room-furniture-options"),
  roomFurnitureSelect: $("#room-furniture-select"),
  roomPriority: $("#room-priority"),
  roomPersonalNeeds: $("#room-personal-needs"),
  requirementsProgress: $("#requirements-progress"),
  requirementsError: $("#requirements-error"),
  confirmRequirements: $("#confirm-requirements"),
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
};

const whiteViewer = createSceneViewer($("#white-model-viewer"), element.whiteStatus);
const realisticViewer = createSceneViewer($("#realistic-viewer"), element.realisticStatus);
const styleFurnitureCache = new Map();

function setStatus(message, kind = "normal") {
  element.status.textContent = message;
  element.status.dataset.kind = kind;
}

function errorMessage(error) {
  const detail = error?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message || error?.message || "操作失敗，請稍後再試。";
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
    || stepIsLive("realistic_3d");
  const whiteModelIsLive = stepIsLive("white_model_3d")
    || stepIsLive("realistic_3d");
  const realisticIsLive = stepIsLive("realistic_3d");
  return {
    _flow: state.workflow?.toJSON() || null,
    privacy: state.workflow?.data?.privacy || {},
    recognition: stepIsLive("recognition") || calibrationIsLive ? state.analysis : null,
    confirmed_floorplan: calibrationIsLive ? state.confirmedFloorplan : null,
    calibration: calibrationIsLive ? state.workflow?.data?.calibration || null : null,
    space_confirmation: spaceIsLive
      ? {
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
  };
}

let saveSequence = Promise.resolve();
let pendingSaveCount = 0;

function pendingSaveStorageKey() {
  return state.projectId ? `roompilot.pending-save.${state.projectId}` : "";
}

function capturePendingSave(currentStep = state.workflow?.currentStep) {
  const serialized = JSON.stringify({
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
      const result = await saveWorkflowRequest(serialized);
      state.project = result.project;
      if (localStorage.getItem(pendingSaveStorageKey()) === serialized) {
        localStorage.removeItem(pendingSaveStorageKey());
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

function invalidateDownstreamFrom(step, message = "") {
  if (!state.workflow?.invalidateFrom?.(step)) return;
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
    state.activeQuestionRoomId = state.activeQuestionRoomId || state.selectedRoomId;
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
    whiteViewer.setViewMode("dollhouse");
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
    realisticViewer.setViewMode("dollhouse");
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
    recognition: "請先上傳平面圖並同意資料用途。",
    calibration: "請先完成 Cody 辨識。",
    space_confirmation: "請先拖曳兩端並確認公分尺度。",
    requirements: "請先確認房間與牆、門、窗、梁、柱。",
    layout_2d: "請先完成基本問卷與每一個房間需求。",
    white_model_3d: "請先確認 2D 家具尺寸與配置。",
    realistic_3d: "請先確認 3D 家具確實可見，並確認指定家具需求。",
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

function selectFloorplanFile(file) {
  element.uploadError.textContent = "";
  const extension = floorplanExtension(file);
  if (!extension) {
    state.pendingFile = null;
    element.uploadFileState.textContent = "格式不支援";
    element.uploadError.textContent = "只支援 DXF、PNG、JPG 或 JPEG。PDF、WEBP、HEIC 等格式不會上傳。";
    return false;
  }
  state.pendingFile = file;
  state.sourceExtension = extension;
  element.uploadFileState.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
  setStatus("已選擇檔案。勾選資料用途後按「開始 Cody 辨識」。");
  return true;
}

async function loadSample630() {
  element.uploadError.textContent = "";
  try {
    const response = await fetch("/api/floorplan/sample/630");
    if (!response.ok) throw new Error("630 cm 驗收圖不存在。");
    const blob = await response.blob();
    selectFloorplanFile(new File([blob], "builder_plan_630.png", { type: "image/png" }));
  } catch (error) {
    element.uploadError.textContent = errorMessage(error);
  }
}

async function confirmUpload() {
  element.uploadError.textContent = "";
  if (!state.pendingFile) {
    element.uploadError.textContent = "請先選擇 DXF、PNG、JPG 或 JPEG 平面圖。";
    element.file.focus();
    return;
  }
  if (!element.consent.checked) {
    element.uploadError.textContent = "請先勾選資料用途同意，才能開始 Cody 辨識。";
    element.consent.focus();
    return;
  }
  try {
    setStatus("正在保存原圖並執行 Cody 牆、門、窗辨識…");
    const form = new FormData();
    form.append("file", state.pendingFile);
    const uploaded = await api(`/api/projects/${state.projectId}/floorplan`, {
      method: "POST",
      body: form,
    });
    state.sourceUrl = `${uploaded.upload.source_url}?v=${Date.now()}`;
    state.sourceExtension = uploaded.upload.extension;
    state.workflow.setPrivacyConsent({
      accepted: true,
      projectOnly: true,
      noTraining: true,
      termsVersion: "2026-07-17",
    });
    state.workflow.complete("upload", { filename: uploaded.upload.filename });
    await api(`/api/projects/${state.projectId}/workflow`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_step: "upload",
        workflow: {
          privacy: {
            accepted: true,
            project_only: true,
            no_training: true,
            terms_version: "2026-07-17",
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
    element.recognitionSummary.textContent = `Cody：牆 ${count.walls}、門 ${count.doors}、窗 ${count.windows}`;
    if (state.analysis.scale?.distance_m) {
      element.scaleInput.value = Math.round(state.analysis.scale.distance_m * 1000) / 10;
    }
    setStatus(scaleEvidence
      ? "Cody 已標出建議端點。請拖曳確認兩端位置，再確認實際公分尺寸。"
      : "Cody 辨識完成。現在請由使用者拉兩端，確認一段實際公分尺寸。");
    showStep("recognition");
    scheduleSave("recognition");
  } catch (error) {
    element.uploadError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function dxfPreviewDataUrl(floorplan = {}) {
  const segments = floorplan.wall_segments || floorplan.plan_segments || [];
  const width = Math.max(Number(floorplan.width_cm || 600) / 100, 0.01);
  const depth = Math.max(Number(floorplan.depth_cm || 400) / 100, 0.01);
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
  const widthM = Math.max(Number(floorplan.width_cm || 600) / 100, 0.01);
  const depthM = Math.max(Number(floorplan.depth_cm || 400) / 100, 0.01);
  const previewWidth = 1000;
  const previewHeight = Math.max(1, Math.round(previewWidth * depthM / widthM));
  analysis.image_size_px = { width: previewWidth, height: previewHeight };
  analysis.plan_bbox_px = [0, 0, previewWidth, previewHeight];
  analysis.scale = {
    distance_m: widthM,
    m_per_px: widthM / previewWidth,
    source: "dxf_geometry",
  };
  return dxfPreviewDataUrl(floorplan);
}

function setPlanImages(url) {
  [element.scaleImage, element.spaceImage, element.requirementsImage, element.layoutImage]
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
  syncOverlayToImage(element.requirementsStage, element.requirementsImage, element.requirementsOverlay);
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  syncLayoutLayer();
  renderCalibration();
  renderSpaceOverlay();
  renderRequirementsOverlay();
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
  element.scaleError.textContent = "";
  const distanceCm = Number(element.scaleInput.value);
  if (state.calibrationPoints.length !== 2) {
    element.scaleError.textContent = "請先在左圖點出尺寸線的起點與終點。";
    return;
  }
  if (!(distanceCm > 0)) {
    element.scaleError.textContent = "請輸入這一段的實際尺寸，單位是公分。";
    element.scaleInput.focus();
    return;
  }
  try {
    const calibration = buildScaleCalibration(state.calibrationPoints, distanceCm);
    setStatus("正在依使用者確認的公分尺度重新執行 Cody 辨識…");
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
    const confirmPayload = state.sourceExtension === ".dxf"
      ? { floorplan: state.analysis.floorplan, dxf_text: null }
      : await api("/api/floorplan/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis: state.analysis }),
      });
    state.confirmedFloorplan = confirmPayload;
    state.workflow.complete("calibration", { distanceCm, calibration });
    initializeRoomsAndStructures();
    setStatus(`尺度已確認為 ${distanceCm} cm。現在開始確認 ${state.rooms.length} 個房間。`);
    showStep("space_confirmation");
    scheduleSave("calibration");
  } catch (error) {
    element.scaleError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function planGeometry() {
  const imageWidth = state.analysis?.image_size_px?.width || element.spaceImage.naturalWidth || 1000;
  const imageHeight = state.analysis?.image_size_px?.height || element.spaceImage.naturalHeight || 1000;
  const scale = Number(state.analysis?.scale?.m_per_px) || 0.01;
  const bbox = state.analysis?.plan_bbox_px || [0, 0, imageWidth, imageHeight];
  return { imageWidth, imageHeight, scale, bbox };
}

function confirmedFloorplanEditor() {
  const { scale, bbox } = planGeometry();
  const recognizedWidthCm = Math.max(240, (bbox[2] - bbox[0]) * scale * 100);
  const recognizedDepthCm = Math.max(240, (bbox[3] - bbox[1]) * scale * 100);
  return {
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

function meterToPixel(point) {
  const { scale, bbox } = planGeometry();
  return {
    x: bbox[0] + Number(point.x) / scale,
    y: bbox[3] - Number(point.y) / scale,
  };
}

function pixelToMeter(point) {
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

function roomDimensions(room) {
  const xs = room.polygon_m.map((point) => point.x);
  const ys = room.polygon_m.map((point) => point.y);
  return {
    widthCm: (Math.max(...xs) - Math.min(...xs)) * 100,
    depthCm: (Math.max(...ys) - Math.min(...ys)) * 100,
    areaM2: polygonArea(room.polygon_m),
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
  const widthM = Number(floorplan.width_cm || 600) / 100;
  const depthM = Number(floorplan.depth_cm || 400) / 100;
  const normalizePoint = (point, centered = false) => {
    const x = Number(point?.x ?? point?.[0] ?? 0);
    const y = Number(point?.y ?? point?.z ?? point?.[1] ?? 0);
    return {
      x: x + (centered ? widthM / 2 : 0),
      y: y + (centered ? depthM / 2 : 0),
    };
  };
  state.rooms = sourceRooms.map((room, index) => {
    const polygon = room.polygon_m || room.polygon || room.exterior || [];
    return {
      ...room,
      id: room.id || room.room_id || `room-${index + 1}`,
      label: room.label || room.name || `空間 ${index + 1}`,
      type: room.type || room.room_type || "default",
      polygon_m: polygon.map((point) => normalizePoint(point, !hasImageRooms)),
    };
  }).filter((room) => room.polygon_m.length >= 3);
  if (!state.rooms.length) {
    state.rooms = [{
      id: "room-1",
      label: "未命名空間",
      type: "default",
      confidence: 0.4,
      polygon_m: [{ x: 0, y: 0 }, { x: widthM, y: 0 }, { x: widthM, y: depthM }, { x: 0, y: depthM }],
    }];
  }
  const normalizeSegment = (item, index, kind, centered = false) => ({
    ...item,
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
      ...item,
      id: item.id || `column-${index + 1}`,
      center: normalizePoint(item.center, !hasImageRooms),
    })),
  };
  state.selectedRoomId = state.rooms[0]?.id || null;
  state.activeQuestionRoomId = state.selectedRoomId;
  renderRooms();
  renderSpaceOverlay();
  renderStructureCounts();
}

function roomPolygonSvg(room) {
  return room.polygon_m.map(meterToPixel).map((point) => `${point.x},${point.y}`).join(" ");
}

function renderRooms() {
  element.roomList.innerHTML = state.rooms.map((room) => {
    const dimensions = roomDimensions(room);
    return `
      <button type="button" data-room-id="${escapeHtml(room.id)}" class="${room.id === state.selectedRoomId ? "is-active" : ""}">
        <strong>${escapeHtml(room.label)}</strong>
        <span>${dimensions.areaM2.toFixed(2)} m²</span>
        <small>${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm</small>
        <small>信心 ${(Number(room.confidence || room.polygon_confidence || 0.7) * 100).toFixed(0)}%</small>
      </button>
    `;
  }).join("");
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (room) {
    const dimensions = roomDimensions(room);
    element.roomEditor.hidden = false;
    element.roomName.value = room.label;
    element.roomWidth.value = dimensions.widthCm.toFixed(0);
    element.roomDepth.value = dimensions.depthCm.toFixed(0);
    element.roomArea.textContent = `依目前框選計算：${dimensions.areaM2.toFixed(2)} m²`;
  } else {
    element.roomEditor.hidden = true;
  }
}

function addMissedRoom() {
  const center = state.selectedRoomId
    ? roomCenter(state.rooms.find((room) => room.id === state.selectedRoomId))
    : planCenterMeters();
  const widthM = 2.4;
  const depthM = 2.4;
  const room = {
    id: `room-manual-${Date.now()}`,
    label: `新增空間 ${state.rooms.length + 1}`,
    type: "default",
    confidence: 0.35,
    manually_added: true,
    polygon_m: [
      { x: center.x - widthM / 2, y: center.y - depthM / 2 },
      { x: center.x + widthM / 2, y: center.y - depthM / 2 },
      { x: center.x + widthM / 2, y: center.y + depthM / 2 },
      { x: center.x - widthM / 2, y: center.y + depthM / 2 },
    ],
  };
  state.rooms.push(room);
  state.selectedRoomId = room.id;
  state.showAllRooms = false;
  $("#rooms-confirmed").checked = false;
  invalidateDownstreamFrom(
    "space_confirmation",
    "已新增漏辨識空間；請拖曳節點、命名並重新確認空間與結構。",
  );
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
}

function renderSpaceOverlay() {
  if (!element.spaceImage.naturalWidth || !state.rooms.length) return;
  const visibleRooms = state.showAllRooms
    ? state.rooms
    : state.rooms.filter((room) => room.id === state.selectedRoomId);
  const polygons = visibleRooms.map((room) => {
    const active = room.id === state.selectedRoomId;
    const nodes = active
      ? room.polygon_m.map((point, index) => {
        const pixel = meterToPixel(point);
        return `<circle data-room-point="${index}" cx="${pixel.x}" cy="${pixel.y}" r="9" fill="#fff" stroke="#7755a6" stroke-width="5"/>`;
      }).join("")
      : "";
    return `
      <g data-room-shape="${escapeHtml(room.id)}">
        <polygon points="${roomPolygonSvg(room)}" fill="${active ? "rgba(47,111,135,.20)" : "rgba(36,107,85,.10)"}"
          stroke="${active ? "#2f6f87" : "#246b55"}" stroke-width="${active ? 5 : 3}"/>
        ${nodes}
      </g>
    `;
  }).join("");
  const structures = renderStructureSvg();
  element.spaceOverlay.innerHTML = `${polygons}${structures}`;
}

function segmentSvg(item, color, width = 5, dash = "") {
  const start = meterToPixel(item.start);
  const end = meterToPixel(item.end);
  return `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="${color}" stroke-width="${width}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
}

const structureCollections = {
  wall: "walls",
  door: "doors",
  window: "windows",
  beam: "beams",
  column: "columns",
};

function structureGroup(item, kind, markup) {
  const active = state.selectedStructure?.id === item.id
    && state.selectedStructure?.kind === kind;
  return `<g data-structure-id="${escapeHtml(item.id)}" data-structure-kind="${kind}"
    class="${active ? "is-selected-structure" : ""}">${markup}</g>`;
}

function renderStructureSvg() {
  const walls = state.structures.walls.map((item) => structureGroup(
    item,
    "wall",
    segmentSvg(item, "#343434", Math.max(4, Number(item.thickness_m || 0.12) / planGeometry().scale)),
  )).join("");
  const windows = state.structures.windows.map((item) => structureGroup(
    item,
    "window",
    segmentSvg(item, "#2f8ba1", 7),
  )).join("");
  const doors = state.structures.doors.map((item) => {
    const line = segmentSvg(item, "#bd5c36", 7);
    const hinge = meterToPixel(item.start);
    const end = meterToPixel(item.end);
    const radius = Math.hypot(end.x - hinge.x, end.y - hinge.y);
    const sweep = item.opening_direction === "left" ? 0 : 1;
    return structureGroup(
      item,
      "door",
      `${line}<path d="M ${end.x} ${end.y} A ${radius} ${radius} 0 0 ${sweep} ${hinge.x + (end.y - hinge.y)} ${hinge.y - (end.x - hinge.x)}" fill="none" stroke="#bd5c36" stroke-width="3"/>`,
    );
  }).join("");
  const beams = state.structures.beams.map((item) => structureGroup(
    item,
    "beam",
    segmentSvg(item, "#6b4d8a", 11, "12 7"),
  )).join("");
  const columns = state.structures.columns.map((item) => {
    const pixel = meterToPixel(item.center);
    const size = Number(item.size_m || 0.35) / planGeometry().scale;
    return structureGroup(
      item,
      "column",
      `<rect x="${pixel.x - size / 2}" y="${pixel.y - size / 2}" width="${size}" height="${size}" fill="rgba(189,92,54,.32)" stroke="#8e3e23" stroke-width="4"/>`,
    );
  }).join("");
  return `<g>${walls}${windows}${doors}${beams}${columns}</g>`;
}

let draggedRoomPointIndex = null;
let structureDrag = null;
function spacePointerDown(event) {
  const structureNode = event.target.closest("[data-structure-id]");
  if (structureNode) {
    state.selectedStructure = {
      id: structureNode.dataset.structureId,
      kind: structureNode.dataset.structureKind,
    };
    const point = imagePoint(event, element.spaceImage);
    if (point) {
      structureDrag = {
        start: pixelToMeter(point),
        snapshot: JSON.parse(JSON.stringify(selectedStructureItem())),
      };
    }
    renderSpaceOverlay();
    renderSelectedStructureEditor();
    return;
  }
  const node = event.target.closest("[data-room-point]");
  if (node) {
    draggedRoomPointIndex = Number(node.dataset.roomPoint);
    return;
  }
  const roomShape = event.target.closest("[data-room-shape]");
  if (roomShape) {
    selectRoom(roomShape.dataset.roomShape);
    return;
  }
  if (state.structureTool === "wall" || state.structureTool === "beam") {
    const point = imagePoint(event, element.spaceImage);
    if (!point) return;
    const meter = pixelToMeter(point);
    if (!state.structureLineStart) {
      state.structureLineStart = meter;
      setStatus(`已設定${state.structureTool === "wall" ? "牆" : "梁"}起點，請再點終點。`);
    } else {
      const collection = state.structureTool === "wall" ? "walls" : "beams";
      state.structures[collection].push({
        id: `${state.structureTool}-manual-${Date.now()}`,
        start: state.structureLineStart,
        end: meter,
        thickness_m: state.structureTool === "wall" ? 0.12 : 0.3,
        estimated: true,
        source: "manual",
      });
      state.structureLineStart = null;
      renderSpaceOverlay();
      renderStructureCounts();
      invalidateDownstreamFrom("space_confirmation", "已新增牆/梁，後續需求、家具與 3D 需要重新確認。");
      scheduleSave("space_confirmation");
    }
  }
}

function spacePointerMove(event) {
  if (structureDrag && state.selectedStructure) {
    const point = imagePoint(event, element.spaceImage);
    const item = selectedStructureItem();
    if (!point || !item) return;
    const current = pixelToMeter(point);
    const dx = current.x - structureDrag.start.x;
    const dy = current.y - structureDrag.start.y;
    if (state.selectedStructure.kind === "column") {
      item.center = {
        x: structureDrag.snapshot.center.x + dx,
        y: structureDrag.snapshot.center.y + dy,
      };
    } else {
      item.start = {
        x: structureDrag.snapshot.start.x + dx,
        y: structureDrag.snapshot.start.y + dy,
      };
      item.end = {
        x: structureDrag.snapshot.end.x + dx,
        y: structureDrag.snapshot.end.y + dy,
      };
    }
    renderSpaceOverlay();
    return;
  }
  if (draggedRoomPointIndex == null) return;
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  const point = imagePoint(event, element.spaceImage);
  if (!room || !point) return;
  room.polygon_m[draggedRoomPointIndex] = pixelToMeter(point);
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

function renderSelectedStructureEditor() {
  const item = selectedStructureItem();
  element.structureEditor.hidden = !item;
  if (!item) return;
  const labels = {
    wall: "牆",
    door: "門",
    window: "窗",
    beam: "梁",
    column: "柱",
  };
  $("#selected-structure-title").textContent =
    `選取${labels[state.selectedStructure.kind] || "結構"}`;
  const isLineWidth = ["door", "window"].includes(state.selectedStructure.kind);
  $("#selected-structure-size-label").textContent = isLineWidth
    ? "開口寬度（公分）"
    : state.selectedStructure.kind === "column"
      ? "柱寬（公分）"
      : "厚度（公分）";
  const length = item.start && item.end
    ? Math.hypot(item.end.x - item.start.x, item.end.y - item.start.y)
    : 0;
  $("#selected-structure-size-cm").value = Math.round(
    Number(
      isLineWidth
        ? item.width_m || length
        : state.selectedStructure.kind === "column"
          ? item.size_m
          : item.thickness_m,
    ) * 100,
  );
  $("#selected-structure-height-cm").value = Math.round(
    Number(item.height_m || (state.selectedStructure.kind === "beam" ? 0.35 : 2.7)) * 100,
  );
  $("#flip-selected-door").hidden = state.selectedStructure.kind !== "door";
}

function applySelectedStructureSize() {
  const item = selectedStructureItem();
  if (!item) return;
  const sizeM = Math.max(0.01, Number($("#selected-structure-size-cm").value) / 100);
  const heightM = Math.max(0.01, Number($("#selected-structure-height-cm").value) / 100);
  const kind = state.selectedStructure.kind;
  if (kind === "door" || kind === "window") {
    const cx = (item.start.x + item.end.x) / 2;
    const cy = (item.start.y + item.end.y) / 2;
    const angle = Math.atan2(item.end.y - item.start.y, item.end.x - item.start.x);
    item.start = { x: cx - Math.cos(angle) * sizeM / 2, y: cy - Math.sin(angle) * sizeM / 2 };
    item.end = { x: cx + Math.cos(angle) * sizeM / 2, y: cy + Math.sin(angle) * sizeM / 2 };
    item.width_m = sizeM;
  } else if (kind === "column") {
    item.size_m = sizeM;
    item.height_m = heightM;
  } else {
    item.thickness_m = sizeM;
    item.height_m = heightM;
  }
  item.estimated = false;
  renderSpaceOverlay();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構尺寸已修改，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
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
  if (!item || !item.start || !item.end) return;
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
  item.estimated = false;
  renderSpaceOverlay();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構方向已微調，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
}

function deleteSelectedStructure() {
  if (!state.selectedStructure) return;
  const collection = structureCollections[state.selectedStructure.kind];
  state.structures[collection] = state.structures[collection].filter(
    (item) => item.id !== state.selectedStructure.id,
  );
  state.selectedStructure = null;
  renderSpaceOverlay();
  renderStructureCounts();
  renderSelectedStructureEditor();
  invalidateDownstreamFrom("space_confirmation", "結構已刪除，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
}

function selectRoom(roomId) {
  state.selectedRoomId = roomId;
  state.showAllRooms = false;
  renderRooms();
  renderSpaceOverlay();
}

function saveRoom() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const targetWidth = Number(element.roomWidth.value) / 100;
  const targetDepth = Number(element.roomDepth.value) / 100;
  if (!(targetWidth > 0) || !(targetDepth > 0)) {
    element.spaceError.textContent = "房間長寬必須大於 0 公分。";
    return;
  }
  room.label = element.roomName.value.trim() || room.label;
  const xs = room.polygon_m.map((point) => point.x);
  const ys = room.polygon_m.map((point) => point.y);
  const center = {
    x: (Math.min(...xs) + Math.max(...xs)) / 2,
    y: (Math.min(...ys) + Math.max(...ys)) / 2,
  };
  const currentWidth = Math.max(...xs) - Math.min(...xs) || 1;
  const currentDepth = Math.max(...ys) - Math.min(...ys) || 1;
  room.polygon_m = room.polygon_m.map((point) => ({
    x: center.x + (point.x - center.x) * targetWidth / currentWidth,
    y: center.y + (point.y - center.y) * targetDepth / currentDepth,
  }));
  renderRooms();
  renderSpaceOverlay();
  $("#rooms-confirmed").checked = false;
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

function addDroppedStructure(tool, point) {
  const meter = pixelToMeter(point);
  if (tool === "column") {
    state.structures.columns.push({
      id: `column-manual-${Date.now()}`,
      center: meter,
      size_m: 0.35,
      estimated: true,
    });
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
    const widthM = tool === "door" ? 0.9 : 1.2;
    const wallStart = host?.wall.start || { x: meter.x - 1, y: meter.y };
    const wallEnd = host?.wall.end || { x: meter.x + 1, y: meter.y };
    const angle = Math.atan2(wallEnd.y - wallStart.y, wallEnd.x - wallStart.x);
    const center = host?.projected || meter;
    const item = {
      id: `${tool}-manual-${Date.now()}`,
      start: { x: center.x - Math.cos(angle) * widthM / 2, y: center.y - Math.sin(angle) * widthM / 2 },
      end: { x: center.x + Math.cos(angle) * widthM / 2, y: center.y + Math.sin(angle) * widthM / 2 },
      width_m: widthM,
      host_wall_id: host?.wall.id,
      source: "manual",
      opening_direction: "right",
      estimated: true,
    };
    state.structures[tool === "door" ? "doors" : "windows"].push(item);
  }
  renderSpaceOverlay();
  renderStructureCounts();
  scheduleSave("space_confirmation");
}

function renderStructureCounts() {
  const s = state.structures;
  const pendingDoorDirections = s.doors.filter(
    (door) => !["left", "right"].includes(door.opening_direction),
  ).length;
  const doorReview = pendingDoorDirections
    ? `；門向待人工確認 ${pendingDoorDirections} 扇（點門後按「切換門向」）`
    : "；門向皆已確認";
  element.structureCounts.textContent =
    `Cody＋人工：牆 ${s.walls.length}、門 ${s.doors.length}、窗 ${s.windows.length}、梁 ${s.beams.length}、柱 ${s.columns.length}${doorReview}`;
}

function confirmSpace() {
  element.spaceError.textContent = "";
  if (!$("#rooms-confirmed").checked) {
    element.spaceError.textContent = "請先勾選已確認房間名稱、尺寸與面積。";
    $("#rooms-confirmed").focus();
    return;
  }
  if (!$("#structure-confirmed").checked) {
    element.spaceError.textContent = "請切到「牆門窗梁柱」並確認結構。";
    $("[data-space-tab='structure']").focus();
    return;
  }
  if (!$("#estimated-size-ack").checked) {
    element.spaceError.textContent = "請確認已了解圖面估計尺寸可能與現場不同。";
    $("#estimated-size-ack").focus();
    return;
  }
  state.workflow.complete("space_confirmation", {
    roomsConfirmed: true,
    structureConfirmed: true,
  });
  renderWholeHouseQuestionnaire();
  renderQuestionRooms();
  setStatus("空間與結構已保存。現在才開始基本問卷。");
  goTo("requirements");
}

function renderWholeHouseQuestionnaire() {
  element.wholeHouseFields.innerHTML = WHOLE_HOUSE_QUESTIONS.map((question) => {
    if (question.type === "choice") {
      const options = question.options.map((option) => `
        <label><input type="radio" name="basic-${escapeHtml(question.id)}" value="${escapeHtml(option)}"/><span>${escapeHtml(option)}</span></label>
      `).join("");
      return `<fieldset data-basic-question="${escapeHtml(question.id)}"><legend>${escapeHtml(question.label)}</legend><div class="rp-choice-grid">${options}</div></fieldset>`;
    }
    return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><textarea rows="2" placeholder="${escapeHtml(question.placeholder || "")}"></textarea></label>`;
  }).join("");
}

function collectBasicAnswers() {
  const answers = {};
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    answers[question.id] = question.type === "choice"
      ? host?.querySelector("input:checked")?.value || ""
      : host?.querySelector("textarea")?.value.trim() || "";
  });
  return answers;
}

function confirmBasicQuestionnaire() {
  element.requirementsError.textContent = "";
  const answers = collectBasicAnswers();
  const missing = WHOLE_HOUSE_QUESTIONS.find((question) => !answers[question.id]);
  if (missing) {
    element.requirementsError.textContent = `請完成「${missing.label}」。`;
    $(`[data-basic-question="${missing.id}"]`)?.scrollIntoView({ block: "center" });
    return;
  }
  state.basicAnswers = answers;
  state.basicConfirmed = true;
  $("#whole-house-questionnaire").hidden = true;
  $("#room-questionnaire").hidden = false;
  element.confirmRequirements.hidden = false;
  element.requirementsProgress.textContent = `房間需求 0 / ${state.rooms.length}`;
  selectQuestionRoom(state.activeQuestionRoomId || state.rooms[0]?.id);
  scheduleSave("requirements");
}

function renderQuestionRooms() {
  element.roomQuestionNav.innerHTML = state.rooms.map((room) => {
    const resolved = state.roomAnswers[room.id]?.confirmed || state.keepExistingRoomIds.includes(room.id);
    return `<button type="button" data-question-room="${escapeHtml(room.id)}" class="${room.id === state.activeQuestionRoomId ? "is-active" : ""}">${escapeHtml(room.label)}${resolved ? " · 已完成" : ""}</button>`;
  }).join("");
}

function renderRequirementsOverlay() {
  if (!element.requirementsImage || !element.requirementsOverlay || !element.requirementsImage.naturalWidth || !state.rooms.length) return;
  element.requirementsOverlay.innerHTML = state.rooms.map((room) => `
    <polygon data-requirement-room="${escapeHtml(room.id)}" points="${roomPolygonSvg(room)}"
      fill="${room.id === state.activeQuestionRoomId ? "rgba(47,111,135,.24)" : "rgba(36,107,85,.06)"}"
      stroke="${room.id === state.activeQuestionRoomId ? "#2f6f87" : "#7b8f86"}" stroke-width="4"/>
  `).join("");
}

function selectQuestionRoom(roomId) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  state.activeQuestionRoomId = roomId;
  state.selectedRoomId = roomId;
  const template = roomQuestionTemplate(room.type);
  element.roomQuestionTitle.textContent = `${room.label}的使用與家具需求`;
  element.roomUseOptions.innerHTML = template.uses.map((label) =>
    `<label><input type="checkbox" value="${escapeHtml(label)}"/><span>${escapeHtml(label)}</span></label>`
  ).join("");
  element.roomFurnitureOptions.innerHTML = template.furniture.map((label) =>
    `<label><input type="checkbox" value="${escapeHtml(label)}"/><span>${escapeHtml(label)}</span></label>`
  ).join("");
  element.roomFurnitureSelect.innerHTML = template.furniture.map((label) =>
    `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`
  ).join("");
  const existing = state.roomAnswers[roomId];
  if (existing) {
    $$("input", element.roomUseOptions).forEach((input) => { input.checked = existing.uses.includes(input.value); });
    $$("input", element.roomFurnitureOptions).forEach((input) => { input.checked = existing.furniture.includes(input.value); });
    Array.from(element.roomFurnitureSelect.options).forEach((option) => {
      option.selected = existing.furniture.includes(option.value);
    });
    element.roomPriority.value = existing.priority || "";
    element.roomPersonalNeeds.value = existing.personalNeeds || "";
  } else {
    Array.from(element.roomFurnitureSelect.options).forEach((option) => { option.selected = false; });
    element.roomPriority.value = "";
    element.roomPersonalNeeds.value = "";
  }
  renderQuestionRooms();
  renderRequirementsOverlay();
}

function resolveActiveRoomRequirement(keepExisting = false) {
  const roomId = state.activeQuestionRoomId;
  if (!roomId) return;
  if (keepExisting) {
    if (!state.keepExistingRoomIds.includes(roomId)) state.keepExistingRoomIds.push(roomId);
    delete state.roomAnswers[roomId];
  } else {
    const uses = $$("input:checked", element.roomUseOptions).map((input) => input.value);
    if (!uses.length) {
      element.requirementsError.textContent =
        "請先選擇此房間至少一項使用方式；若不規劃，請按「此房間維持現狀不規劃」。";
      return;
    }
    element.requirementsError.textContent = "";
    state.keepExistingRoomIds = state.keepExistingRoomIds.filter((id) => id !== roomId);
    state.roomAnswers[roomId] = {
      confirmed: true,
      uses,
      furniture: [
        ...new Set([
          ...$$("input:checked", element.roomFurnitureOptions).map((input) => input.value),
          ...Array.from(element.roomFurnitureSelect.selectedOptions).map((option) => option.value),
        ]),
      ],
      priority: element.roomPriority.value.trim(),
      personalNeeds: element.roomPersonalNeeds.value.trim(),
    };
  }
  const gate = requirementsGate({
    basic: { confirmed: state.basicConfirmed },
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  const completed = state.rooms.length - gate.unresolvedRoomIds.length;
  element.requirementsProgress.textContent = `房間需求 ${completed} / ${state.rooms.length}`;
  renderQuestionRooms();
  const nextRoom = state.rooms.find((room) => gate.unresolvedRoomIds.includes(room.id));
  if (nextRoom) selectQuestionRoom(nextRoom.id);
  invalidateDownstreamFrom("requirements", "房間需求已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
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
  unresolvedRoomIds.forEach((roomId) => delete state.roomAnswers[roomId]);
  element.requirementsProgress.textContent = `房間需求 ${state.rooms.length} / ${state.rooms.length}`;
  element.requirementsError.textContent = `已將 ${unresolvedRoomIds.length} 個未填寫房間標示為維持現狀。`;
  renderQuestionRooms();
  renderRequirementsOverlay();
  invalidateDownstreamFrom("requirements", "房間需求已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
}

async function confirmRequirements() {
  element.requirementsError.textContent = "";
  const gate = requirementsGate({
    basic: { confirmed: state.basicConfirmed },
    rooms: state.rooms,
    answers: state.roomAnswers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  if (!gate.ready) {
    const labels = gate.unresolvedRoomIds
      .map((id) => state.rooms.find((room) => room.id === id)?.label)
      .filter(Boolean);
    element.requirementsError.textContent = `尚未處理：${labels.join("、")}。請填需求或按「此房間維持現狀不規劃」。`;
    if (gate.unresolvedRoomIds[0]) selectQuestionRoom(gate.unresolvedRoomIds[0]);
    return;
  }
  try {
    setStatus("正在由家具引擎依房間需求計算 2D 合法位置…");
    await autoLayoutFurniture();
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
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
  "洗衣機": ["washer", "front-load"],
  "浴缸": ["bathtub", "standard"],
  "電視櫃": ["tv-bench", "low"],
  "植栽架": ["plant-shelf", "standard"],
  "桌": ["table", "standard"],
  "椅": ["chair", "standard"],
};

function defaultFurnitureForRoom(room) {
  if (room.type === "living_room") return [["sofa", "three-seat"], ["coffee-table", "rect"], ["tv-bench", "low"]];
  if (room.type === "bedroom") return [["bed", "double"], ["wardrobe", "two-door"]];
  if (room.type === "dining_room") return [["dining-table", "round-4"], ["dining-chair", "standard"]];
  if (room.type === "kitchen") return [["refrigerator", "single-door"]];
  if (room.type === "balcony") return [["washer", "front-load"]];
  return [];
}

function roomCenter(room) {
  return room.polygon_m.reduce((sum, point) => ({
    x: sum.x + point.x / room.polygon_m.length,
    y: sum.y + point.y / room.polygon_m.length,
  }), { x: 0, y: 0 });
}

function planCenterMeters() {
  const { bbox, scale } = planGeometry();
  return {
    x: (bbox[2] - bbox[0]) * scale / 2,
    y: (bbox[3] - bbox[1]) * scale / 2,
  };
}

async function autoLayoutFurniture() {
  state.furniture2d = [];
  for (const room of state.rooms) {
    if (state.keepExistingRoomIds.includes(room.id)) continue;
    const requested = state.roomAnswers[room.id]?.furniture || [];
    const roomWasAnswered = state.roomAnswers[room.id]?.confirmed === true;
    const requestedSpecs = roomWasAnswered
      ? requested.map((label) => furnitureLabelMap[label]).filter(Boolean)
      : defaultFurnitureForRoom(room);
    const companionSpecs = recommendCompanionFurniture(
      room.type,
      requestedSpecs.map(([type]) => type),
    ).map((item) => [item.type, item.variantId, item.reason, true]);
    const specs = [...requestedSpecs, ...companionSpecs];
    const roomItems = [];
    specs.forEach(([type, variant, reason, autoAdded], index) => {
      try {
        const item = createFurniture2DItem(type, variant, {
          id: `${room.id}-${type}-${index + 1}`,
          roomId: room.id,
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
      state.furniture2d.push(item);
    });
  }
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  state.activeLayoutRoomId = state.furniture2d[0]?.roomId || "all";
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
  const center = planCenterMeters();
  return meterToPixel({
    x: center.x + item.xCm / 100,
    y: center.y + item.yCm / 100,
  });
}

function layoutPixelsPerCm() {
  const imageRect = element.layoutImage.getBoundingClientRect();
  const naturalRatio = imageRect.width / Math.max(element.layoutImage.naturalWidth, 1);
  return (0.01 / planGeometry().scale) * naturalRatio;
}

function itemCollision(item) {
  const room = state.rooms.find((candidate) => candidate.id === item.roomId);
  if (!room) return true;
  const center = planCenterMeters();
  const x = center.x + item.xCm / 100;
  const y = center.y + item.yCm / 100;
  const xs = room.polygon_m.map((point) => point.x);
  const ys = room.polygon_m.map((point) => point.y);
  const halfWidth = item.widthCm / 200;
  const halfDepth = item.depthCm / 200;
  if (
    x - halfWidth < Math.min(...xs)
    || x + halfWidth > Math.max(...xs)
    || y - halfDepth < Math.min(...ys)
    || y + halfDepth > Math.max(...ys)
  ) return true;
  return state.furniture2d.some((other) => {
    if (other.id === item.id || other.roomId !== item.roomId) return false;
    return Math.abs(other.xCm - item.xCm) < (other.widthCm + item.widthCm) / 2
      && Math.abs(other.yCm - item.yCm) < (other.depthCm + item.depthCm) / 2;
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
  const item = state.furniture2d.find((candidate) => candidate.id === target.dataset.furniture2dId);
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
  const planCenter = planCenterMeters();
  const item = createFurniture2DItem(type, variant, {
    xCm: (center.x - planCenter.x) * 100,
    yCm: (center.y - planCenter.y) * 100,
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
    return {
      ...best,
      ...toSceneFurniture(item),
      furniture_id: best.furniture_id,
      model_url: best.model_url,
      has_model: Boolean(best.model_url),
      size_cm: best.size_cm || toSceneFurniture(item).size_cm,
      requested_size_cm: toSceneFurniture(item).size_cm,
      closest_size_match: true,
    };
  } catch (error) {
    console.warn(error);
    return toSceneFurniture(item);
  }
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
    const payload = await api("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_brief: {
          space: { type: firstRoom.type || "living_room" },
          style: { preferred: ["scandinavian"], colors: [], materials: [] },
          occupants: { adults: 2, children: 0, elderly: 0, pets: 0 },
          needs: [],
          constraints: ["keep_door_clear", "keep_window_clear"],
        },
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
    whiteViewer.setViewMode("dollhouse");
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    const diagnostics = whiteViewer.getDiagnostics();
    const expectedFurnitureCount = state.sceneData.scene_objects.filter(
      (item) => !item.placement_failed,
    ).length;
    if (expectedFurnitureCount === 0) {
      element.whiteError.textContent = "";
      setStatus("純結構 3D 白模已產生；此方案沒有家具需求。");
    } else if (diagnostics.visibleFurnitureCount > 0) {
      element.whiteError.textContent = "";
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
    whiteViewer.setViewMode("dollhouse");
    scheduleSave("white_model_3d");
  } else {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("dollhouse");
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
  state.surfaceState = {
    wall: {},
    floor: {},
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
  realisticViewer.setViewMode("dollhouse");
  applyStylePackToScene(STYLE_PACKS[0]);
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
    ? state.rooms.filter((room) => !state.keepExistingRoomIds.includes(room.id))
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
  realisticViewer.setViewMode("dollhouse");
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
    realisticViewer.setViewMode("dollhouse");
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
    const center = planCenterMeters();
    const override = {
      room_id: room.id,
      room_label: room.label,
      room_bounds_m: {
        minX: Math.min(...room.polygon_m.map((point) => point.x)) - center.x,
        maxX: Math.max(...room.polygon_m.map((point) => point.x)) - center.x,
        minZ: Math.min(...room.polygon_m.map((point) => point.y)) - center.y,
        maxZ: Math.max(...room.polygon_m.map((point) => point.y)) - center.y,
      },
      room_polygon_m: room.polygon_m.map((point) => ({
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
  realisticViewer.setViewMode("dollhouse");
  element.realisticStatus.textContent = `已套用並鎖定${$("#surface-scope option:checked").textContent}的牆面與地板材質。`;
  scheduleSave("realistic_3d");
}

function toggleMaterialBoundary() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId) || state.rooms[0];
  if (!room) return;
  const planCenter = planCenterMeters();
  const bounds = {
    minX: Math.min(...room.polygon_m.map((point) => point.x)) - planCenter.x,
    maxX: Math.max(...room.polygon_m.map((point) => point.x)) - planCenter.x,
    minZ: Math.min(...room.polygon_m.map((point) => point.y)) - planCenter.y,
    maxZ: Math.max(...room.polygon_m.map((point) => point.y)) - planCenter.y,
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
    line_m: direction === "horizontal"
      ? [
          { x: bounds.minX, y: splitZ },
          { x: bounds.maxX, y: splitZ },
        ]
      : [
          { x: splitX, y: bounds.minZ },
          { x: splitX, y: bounds.maxZ },
        ],
    room_bounds_m: bounds,
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
    const xs = candidate.polygon_m.map((vertex) => vertex.x);
    const ys = candidate.polygon_m.map((vertex) => vertex.y);
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
  const planCenter = planCenterMeters();
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
      const topCm = Number(beam.top_cm ?? beam.top_m * 100) || roomHeightCm;
      const heightCm = Number(
        beam.height_cm
        ?? (beam.height_m != null ? beam.height_m * 100 : null)
        ?? (beam.thickness_m != null ? beam.thickness_m * 100 : null),
      ) || 30;
      const midpoint = {
        x: (Number(beam.start?.x || 0) + Number(beam.end?.x || 0)) / 2,
        y: (Number(beam.start?.y || 0) + Number(beam.end?.y || 0)) / 2,
      };
      return {
        id: beam.id,
        kind: "beam",
        label: `梁 ${index + 1}`,
        topCm,
        bottomCm: topCm - heightCm,
        estimated: beam.estimated === true || (beam.top_cm == null && beam.top_m == null),
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
            x: planCenter.x + Number(position.x || 0) / 100,
            y: planCenter.y + Number(position.z || 0) / 100,
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
    : `<p>完成天花高度 ${result.finishedHeightCm} cm，目前未偵測到梁、櫃體或燈具衝突。</p>`;
  if (state.sceneData && state.workflow?.currentStep === "realistic_3d") {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("dollhouse");
  }
}

function bindEvents() {
  element.projectForm.addEventListener("submit", createProject);
  element.file.addEventListener("change", () => selectFloorplanFile(element.file.files[0]));
  $("#load-sample-630").addEventListener("click", loadSample630);
  $("#confirm-upload").addEventListener("click", confirmUpload);
  element.scaleOverlay.addEventListener("pointerdown", calibrationPointerDown);
  element.scaleOverlay.addEventListener("pointermove", calibrationPointerMove);
  window.addEventListener("pointerup", async () => {
    const completedRoomDrag = draggedRoomPointIndex != null;
    state.calibrationDragIndex = null;
    draggedRoomPointIndex = null;
    if (structureDrag) {
      structureDrag = null;
      renderSelectedStructureEditor();
      invalidateDownstreamFrom("space_confirmation", "結構位置已修改，後續需求、家具與 3D 需要重新確認。");
      scheduleSave("space_confirmation");
    }
    if (completedRoomDrag) {
      $("#rooms-confirmed").checked = false;
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
  $("#apply-floorplan-calibration").addEventListener("click", applyCalibration);
  element.roomList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-room-id]");
    if (button) selectRoom(button.dataset.roomId);
  });
  $("#add-missed-room").addEventListener("click", addMissedRoom);
  $("#show-all-rooms").addEventListener("click", () => {
    state.showAllRooms = true;
    renderSpaceOverlay();
  });
  $("#save-room").addEventListener("click", saveRoom);
  element.spaceOverlay.addEventListener("pointerdown", spacePointerDown);
  element.spaceOverlay.addEventListener("pointermove", spacePointerMove);
  $("#apply-structure-size").addEventListener("click", applySelectedStructureSize);
  $("#rotate-selected-structure-left").addEventListener("click", () => rotateSelectedStructure(-15));
  $("#rotate-selected-structure-right").addEventListener("click", () => rotateSelectedStructure(15));
  $("#delete-selected-structure").addEventListener("click", deleteSelectedStructure);
  $("#flip-selected-door").addEventListener("click", () => {
    const door = selectedStructureItem();
    if (!door || state.selectedStructure?.kind !== "door") return;
    door.opening_direction = door.opening_direction === "left" ? "right" : "left";
    renderSpaceOverlay();
    invalidateDownstreamFrom("space_confirmation", "門扇方向已修改，後續需求、家具與 3D 需要重新確認。");
    scheduleSave("space_confirmation");
    setStatus("已切換門扇開啟方向。");
  });
  $$("[data-space-tab]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-space-tab]").forEach((item) => item.classList.toggle("is-active", item === button));
    const rooms = button.dataset.spaceTab === "rooms";
    $("#room-confirmation-panel").hidden = !rooms;
    $("#structure-confirmation-panel").hidden = rooms;
  }));
  $$("[data-structure-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextTool = state.structureTool === button.dataset.structureTool
        ? null
        : button.dataset.structureTool;
      state.structureTool = nextTool;
      $$("[data-structure-tool]").forEach((item) =>
        item.classList.toggle("is-active", item.dataset.structureTool === nextTool)
      );
      if (!nextTool) {
        setStatus("已回到結構選取模式，可點選並拖曳既有牆、門、窗、梁或柱。");
        return;
      }
      setStatus(state.structureTool === "wall" || state.structureTool === "beam"
        ? `請在左圖點${state.structureTool === "wall" ? "牆" : "梁"}的起點與終點。`
        : `請把${button.textContent.trim()}拖到左圖。`);
    });
    button.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/roompilot-structure", button.dataset.structureTool);
    });
  });
  element.spaceStage.addEventListener("dragover", (event) => event.preventDefault());
  element.spaceStage.addEventListener("drop", (event) => {
    event.preventDefault();
    const tool = event.dataTransfer.getData("text/roompilot-structure");
    const point = imagePoint(event, element.spaceImage);
    if (tool && point) addDroppedStructure(tool, point);
  });
  $("#confirm-space").addEventListener("click", confirmSpace);
  $("#confirm-basic-questionnaire").addEventListener("click", confirmBasicQuestionnaire);
  element.roomQuestionNav.addEventListener("click", (event) => {
    const button = event.target.closest("[data-question-room]");
    if (button) selectQuestionRoom(button.dataset.questionRoom);
  });
  element.requirementsOverlay?.addEventListener("click", (event) => {
    const room = event.target.closest("[data-requirement-room]");
    if (room) selectQuestionRoom(room.dataset.requirementRoom);
  });
  $("#confirm-room-requirement").addEventListener("click", () => resolveActiveRoomRequirement(false));
  $("#keep-room-existing").addEventListener("click", () => resolveActiveRoomRequirement(true));
  $("#keep-unfilled-rooms-existing").addEventListener("click", keepUnfilledRoomsExisting);
  element.roomFurnitureOptions.addEventListener("change", syncFurnitureSelectFromCheckboxes);
  element.roomFurnitureSelect.addEventListener("change", syncFurnitureCheckboxesFromSelect);
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
    if (pack) applyStylePackToScene(pack);
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
  $("#apply-surface-colors").addEventListener("click", applySurfaceOverrides);
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
  element.ceilingStyle.addEventListener("change", evaluateCeilingConflicts);
  element.lightStyle.addEventListener("change", evaluateCeilingConflicts);
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
    state.workflow.complete("realistic_3d", { confirmed: true });
    scheduleSave("realistic_3d");
    setStatus("即時寫實方案已保存，家具與材質鎖定也已記錄。");
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
    if (pendingSave) {
      result = await api(`/api/projects/${state.projectId}/workflow`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: pendingSave,
      });
      localStorage.removeItem(pendingSaveStorageKey());
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
    }
    if (Number(savedCalibration?.distanceCm) > 0) {
      element.scaleInput.value = Number(savedCalibration.distanceCm);
    }
    if (state.analysis) {
      element.recognitionSummary.textContent = `Cody：牆 ${state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0}、門 ${state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0}、窗 ${state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0}`;
    }
    state.rooms = serverState.space_confirmation?.rooms || [];
    state.structures = serverState.space_confirmation?.structures || state.structures;
    state.basicAnswers = serverState.requirements?.basic || {};
    state.basicConfirmed = serverState.requirements?.basicConfirmed === true;
    state.roomAnswers = serverState.requirements?.rooms || {};
    state.keepExistingRoomIds = serverState.requirements?.keepExistingRoomIds || [];
    state.furniture2d = serverState.layout_2d?.furniture || [];
    state.sceneData = serverState.white_model_3d?.sceneData || null;
    state.activeStylePackId = serverState.realistic_3d?.activeStylePackId || null;
    state.surfaceState = serverState.realistic_3d?.surfaceState || state.surfaceState;
    state.materialBoundary = serverState.realistic_3d?.materialBoundary || null;
    state.sourceExtension = floorplanExtension({
      name: state.analysis?.filename || state.workflow.data.upload?.filename || "",
    });
    await recoverConfirmedFloorplan();
    state.sourceUrl = state.sourceExtension === ".dxf"
      ? configureDxfPreview(state.analysis)
      : `/api/projects/${state.projectId}/floorplan/source?v=${Date.now()}`;
    if (state.workflow.completed.includes("upload")) setPlanImages(state.sourceUrl);
    showStep(state.workflow.currentStep || "project");
    await renderRestoredStep();
    if (state.confirmedFloorplan && !serverState.confirmed_floorplan) {
      scheduleSave(state.workflow.currentStep);
    }
    setStatus(`已恢復專案「${state.project.name}」。`);
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
  if (state.sourceExtension === ".dxf") {
    state.confirmedFloorplan = {
      floorplan: state.analysis.floorplan || state.analysis,
      dxf_text: null,
    };
    return state.confirmedFloorplan;
  }
  state.confirmedFloorplan = await api("/api/floorplan/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis: state.analysis }),
  });
  return state.confirmedFloorplan;
}

bindEvents();
renderFurnitureLibrary();
renderStyleControls();
evaluateCeilingConflicts();
restoreProject();
