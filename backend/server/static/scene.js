import { fetchFurniturePage, fetchSceneBootstrap, formatFurnitureName, formatSize, formatTypeLabel, initBackgroundFx } from "./common.js?v=20260711g";
import { createSceneViewer } from "./scene_viewer.js?v=20260711n";

const siteData = await fetchSceneBootstrap();
const providerStatus = await fetch("/api/scene/provider-status").then((response) => response.json());
const sceneQuery = new URLSearchParams(window.location.search);
const STYLE_CARD_STORAGE_KEY = "roompilot:selectedStyleCard";
const ROOMPILOT_PROPOSAL_STORAGE_KEY = "roompilot:sceneProposal";

function readStoredStyleCardSelection() {
  try {
    const raw = sessionStorage.getItem(STYLE_CARD_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

const storedStyleCardSelection = readStoredStyleCardSelection();
const requestedStyleId = sceneQuery.get("style") || storedStyleCardSelection?.style || storedStyleCardSelection?.style_id || null;
const requestedStyleCardId = sceneQuery.get("style_card") || storedStyleCardSelection?.style_card || null;
const surfaceCatalog = siteData.surface_catalog || { surfaces: [], style_surface_profiles: {} };
const surfaceById = new Map((surfaceCatalog.surfaces || []).map((surface) => [surface.surface_id, surface]));

const furnitureOptions = [
  { label: "沙發", value: "sofa" },
  { label: "茶几", value: "coffee-table" },
  { label: "電視櫃", value: "tv-bench" },
  { label: "扶手椅", value: "armchair" },
  { label: "書櫃", value: "bookcase" },
  { label: "床", value: "bed" },
  { label: "床頭櫃", value: "bedside-table" },
  { label: "書桌", value: "desk" },
  { label: "辦公椅", value: "office-chair" },
  { label: "餐桌", value: "dining-table" },
  { label: "餐椅", value: "dining-chair" },
  { label: "邊櫃", value: "sideboard" },
];

const colorOptions = ["米白", "奶茶色", "淺木色", "淺灰", "黑色", "綠色", "胡桃木", "黃銅"];

const COLOR_OPTION_PRESETS = [
  { label: "白色", value: "白色", colorHex: "#f8f5ef", aliases: ["white", "off-white"] },
  { label: "米白", value: "米白", colorHex: "#efe6d6", aliases: ["cream", "ivory"] },
  { label: "奶油白", value: "奶油白", colorHex: "#f3eadc", aliases: ["light beige"] },
  { label: "米色", value: "米色", colorHex: "#d8c2a2", aliases: ["beige"] },
  { label: "奶茶色", value: "奶茶色", colorHex: "#c8a98a", aliases: ["taupe"] },
  { label: "淺木色", value: "淺木色", colorHex: "#d9b981", aliases: ["light wood", "oak", "birch", "pine"] },
  { label: "原木色", value: "原木色", colorHex: "#b9824f", aliases: ["natural", "wood"] },
  { label: "胡桃木", value: "胡桃木", colorHex: "#6f4d34", aliases: ["walnut"] },
  { label: "棕色", value: "棕色", colorHex: "#8a5d3d", aliases: ["brown"] },
  { label: "淺灰", value: "淺灰", colorHex: "#d4d2cd", aliases: ["light grey", "light gray"] },
  { label: "灰色", value: "灰色", colorHex: "#8f8d88", aliases: ["grey", "gray"] },
  { label: "黑色", value: "黑色", colorHex: "#252321", aliases: ["black"] },
  { label: "綠色", value: "綠色", colorHex: "#6f8f72", aliases: ["green", "sage"] },
  { label: "藍色", value: "藍色", colorHex: "#6f94ad", aliases: ["blue"] },
  { label: "紅色", value: "紅色", colorHex: "#b85c4d", aliases: ["red"] },
  { label: "黃色", value: "黃色", colorHex: "#d6b54d", aliases: ["yellow"] },
  { label: "黃銅", value: "黃銅", colorHex: "#c09a52", aliases: ["brass", "gold"] },
  { label: "銀色", value: "銀色", colorHex: "#c4c8c9", aliases: ["silver", "stainless steel", "steel"] },
  { label: "透明玻璃", value: "透明玻璃", colorHex: "#cfe1e6", aliases: ["glass", "transparent", "clear"] },
];

const fallbackSurfaces = {
  wall: [
    { id: "warm_white", label: "暖白牆面", colorZh: "暖白", colorHex: "#f3eadf", preview: "linear-gradient(135deg, #fbf6ef, #ece0d2)" },
    { id: "mineral_beige", label: "礦物米色牆", colorZh: "米灰", colorHex: "#c9b49c", preview: "linear-gradient(135deg, #d8c6b2, #bca58a)" },
    { id: "light_gray", label: "淺灰牆面", colorZh: "淺灰", colorHex: "#d9dce0", preview: "linear-gradient(135deg, #ececee, #d2d4d8)" },
    { id: "limewash", label: "石灰刷紋牆", colorZh: "暖灰米", colorHex: "#ded1bd", preview: "linear-gradient(135deg, #e6dac8, #bfa98e)" },
    { id: "sage", label: "鼠尾草綠牆", colorZh: "低彩綠", colorHex: "#c5d0c0", preview: "linear-gradient(135deg, #d9e1d5, #aebca8)" },
    { id: "sand", label: "砂岩米牆", colorZh: "砂岩米", colorHex: "#d3bea2", preview: "linear-gradient(135deg, #e4d1b8, #b99f7d)" },
    { id: "greige", label: "暖灰米牆", colorZh: "灰米", colorHex: "#c8c1b7", preview: "linear-gradient(135deg, #ded8d0, #aaa197)" },
    { id: "clay", label: "陶土暖牆", colorZh: "陶土", colorHex: "#b88972", preview: "linear-gradient(135deg, #caa18d, #926553)" },
    { id: "charcoal", label: "炭灰重點牆", colorZh: "炭灰", colorHex: "#514b46", preview: "linear-gradient(135deg, #686159, #3f3a36)" },
  ],
  floor: [
    { id: "light_oak", label: "淺橡木地板", colorZh: "淺橡木", colorHex: "#d7b58c", preview: "linear-gradient(135deg, #ead4af, #d3b07f)" },
    { id: "walnut", label: "深胡桃木地板", colorZh: "胡桃木", colorHex: "#6f4d34", preview: "linear-gradient(135deg, #9b7452, #5b3e28)" },
    { id: "stone_gray", label: "灰石紋地坪", colorZh: "石灰", colorHex: "#b7b3b0", preview: "linear-gradient(135deg, #ddd7d2, #b7b3b0)" },
    { id: "marble", label: "米白大理石磚", colorZh: "米白", colorHex: "#e8dfd2", preview: "linear-gradient(135deg, #f7f5ef, #cfc8bd 52%, #f4efe7)" },
  ],
};

const DEFAULT_FURNITURE_BY_SPACE = {
  living_room: ["sofa", "coffee-table", "tv-bench", "armchair"],
  bedroom: ["bed", "bedside-table", "bookcase"],
  workspace: ["desk", "office-chair", "bookcase"],
  dining_room: ["dining-table", "dining-chair", "sideboard"],
  studio: ["sofa", "coffee-table", "desk", "bookcase"],
};

const LIBRARY_GROUP_TO_SPACE_TYPE = {
  living: "living_room",
  dining_kitchen: "dining_room",
  bedroom: "bedroom",
  study: "workspace",
  storage: "living_room",
  soft_decor: "living_room",
  kids: "bedroom",
  outdoor: "studio",
};

const elements = {
  sceneForm: document.getElementById("scene-form"),
  formPanel: document.querySelector(".scene-form-panel"),
  welcomePanel: document.getElementById("scene-welcome-panel"),
  startFlow: document.getElementById("scene-start-flow"),
  floorplanStep: document.getElementById("scene-floorplan-step"),
  floorplanPreview: document.getElementById("floorplan-preview"),
  floorplanPreviewContent: document.getElementById("floorplan-preview-content"),
  floorplanFilename: document.getElementById("floorplan-filename"),
  floorplanStatus: document.getElementById("floorplan-status"),
  continueToChat: document.getElementById("continue-to-chat"),
  chatPanel: document.getElementById("scene-chat-panel"),
  viewerSide: document.getElementById("scene-viewer-side"),
  stylePreference: document.getElementById("style-preference"),
  furnitureOptions: document.getElementById("furniture-options"),
  colorOptions: document.getElementById("color-options"),
  wallOptions: document.getElementById("wall-options"),
  floorOptions: document.getElementById("floor-options"),
  customFurniture: document.getElementById("custom-furniture"),
  customColors: document.getElementById("custom-colors"),
  roomWidth: document.getElementById("room-width"),
  roomDepth: document.getElementById("room-depth"),
  spaceType: document.getElementById("space-type"),
  floorplan: document.getElementById("floorplan"),
  pickFloorplan: document.getElementById("pick-floorplan"),
  personalNotes: document.getElementById("personal-notes"),
  keepWindowClear: document.getElementById("keep-window-clear"),
  keepDoorClear: document.getElementById("keep-door-clear"),
  needStorage: document.getElementById("need-storage"),
  preferLowSaturation: document.getElementById("prefer-low-saturation"),
  generateScene: document.getElementById("generate-scene"),
  scaleCalibration: document.getElementById("scale-calibration"),
  calibrationCanvas: document.getElementById("calibration-canvas"),
  calibrationLength: document.getElementById("calibration-length"),
  applyCalibration: document.getElementById("apply-calibration"),
  resetCalibration: document.getElementById("reset-calibration"),
  calibrationStatus: document.getElementById("calibration-status"),
  openPanorama: document.getElementById("open-panorama"),
  randomFurniture: document.getElementById("random-furniture"),
  resetSceneView: document.getElementById("reset-scene-view"),
  rotateFurnitureLeft: document.getElementById("rotate-furniture-left"),
  rotateFurnitureRight: document.getElementById("rotate-furniture-right"),
  addFurnitureType: document.getElementById("add-furniture-type"),
  addFurniture: document.getElementById("add-furniture"),
  reshuffleScene: document.getElementById("reshuffle-scene"),
  viewPresetButtons: document.querySelectorAll("[data-view-preset]"),
  sceneStyleName: document.getElementById("scene-style-name"),
  sceneLlmMode: document.getElementById("scene-llm-mode"),
  sceneItemCount: document.getElementById("scene-item-count"),
  sceneRoomSize: document.getElementById("scene-room-size"),
  sceneBackground: document.getElementById("scene-background"),
  sceneSelectedItems: document.getElementById("scene-selected-items"),
  sceneStatus: document.getElementById("scene-status"),
  sceneViewerCanvas: document.getElementById("scene-viewer-canvas"),
  selectedStyleCard: document.getElementById("scene-selected-style-card"),
  proposalCard: document.getElementById("scene-proposal-card"),
  proposalSummary: document.getElementById("scene-proposal-summary"),
  proposalList: document.getElementById("scene-proposal-list"),
  filterProposal: document.getElementById("scene-filter-proposal"),
  proposalFitWarning: document.getElementById("scene-proposal-fit-warning"),
  intakePanel: document.getElementById("scene-intake-panel"),
  roomTypeQuestion: document.getElementById("scene-room-type-question"),
  roomSizeQuestion: document.getElementById("scene-room-size-question"),
  intakeWidth: document.getElementById("scene-intake-width"),
  intakeDepth: document.getElementById("scene-intake-depth"),
  useDefaultRoom: document.getElementById("scene-use-default-room"),
  chatMessages: document.getElementById("scene-chat-messages"),
  chatInput: document.getElementById("scene-chat-input"),
  chatSend: document.getElementById("scene-chat-send"),
  chatHint: document.getElementById("scene-chat-hint"),
  chatBack: document.getElementById("scene-chat-back"),
  chatConfirm: document.getElementById("scene-chat-confirm"),
  briefPanel: document.getElementById("scene-brief-panel"),
  briefSummary: document.getElementById("scene-brief-summary"),
  styleCardPanel: document.getElementById("style-card-panel"),
  styleCardGrid: document.getElementById("style-card-grid"),
  confirmStyleCard: document.getElementById("confirm-style-card"),
  toggleCeiling: document.getElementById("toggle-ceiling"),
  toggleWalkMode: document.getElementById("toggle-walk-mode"),
};

const viewer = createSceneViewer(elements.sceneViewerCanvas, elements.sceneStatus);
let uploadedDxfText = null;
let furnitureRandomSeed = Date.now();
let currentSceneData = null;
let floorplanScaleM = null;      // F2a 校正後的全圖跨距(公尺);null = 交給解析器自動猜
let calibrationParsed = null;    // /api/upload 回來的解析結果(目前比例下的公尺座標)
let calibrationPoints = [];      // 使用者點的兩個世界座標點
let calibrationTransform = null; // 畫布 ↔ 世界座標轉換
let intakeState = { sessionId: null, step: null, clientBrief: null, confirmed: false };
let wallOptionLabelMap = new Map();
let floorOptionLabelMap = new Map();
const surfaceFilters = { wall: "all", floor: "all" };
const surfaceSearchQueries = { wall: "", floor: "" };
const surfaceStyleOnly = { wall: false, floor: false };
const surfaceVisibleLimits = { wall: 12, floor: 12 };
const styleNameById = new Map((siteData.styles || []).map((style) => [style.style_id, style.style_name_zh]));
const STYLE_CARD_TO_INTAKE_STYLE = {
  scandinavian: "scandinavian",
  japanese: "japanese",
  modern_minimal: "modern",
  cream: "warm_neutral",
  industrial: "industrial",
  american: "american",
};
let selectedStyleCardContext = null;
let libraryProposal = null;

function escapeForHtml(value) {
  return String(value ?? "").replace(/[&<>\"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function readLibraryProposal() {
  try {
    const raw = sessionStorage.getItem(ROOMPILOT_PROPOSAL_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.furniture) ? parsed : null;
  } catch (error) {
    console.warn("無法讀取家具資料庫帶入的方案", error);
    return null;
  }
}

function getLibraryProposalFurniture() {
  return Array.isArray(libraryProposal?.furniture) ? libraryProposal.furniture : [];
}

function saveLibraryProposal() {
  if (!libraryProposal) return;
  try {
    sessionStorage.setItem(ROOMPILOT_PROPOSAL_STORAGE_KEY, JSON.stringify(libraryProposal));
  } catch (error) {
    console.warn("無法更新家具資料庫帶入的方案", error);
  }
}

function removeLibraryProposalItem(furnitureId) {
  if (!libraryProposal?.furniture?.length) return;
  libraryProposal.furniture = libraryProposal.furniture.filter((item) => item.furniture_id !== furnitureId);
  saveLibraryProposal();
  renderLibraryProposalSummary();
  intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
  renderClientBrief();
}

function getProposalFurnitureTypes() {
  return Array.from(new Set(
    getLibraryProposalFurniture()
      .map((item) => item.normalized_type || item.type || item.category)
      .filter(Boolean),
  ));
}

function proposalItemPriority(item) {
  const order = [
    "sofa",
    "bed",
    "dining-table",
    "desk",
    "tv-bench",
    "coffee-table",
    "armchair",
    "bookcase",
    "cabinet-cupboard",
    "cabinets-cupboard",
    "wardrobe",
    "rug",
    "lamp",
    "decoration",
  ];
  const index = order.indexOf(item.normalized_type);
  return index === -1 ? 99 : index;
}

function itemFootprintCm2(item) {
  const size = item.size_cm || item.dimensions || {};
  const width = Number(size.width || size.w || 0);
  const depth = Number(size.depth || size.d || 0);
  return width > 0 && depth > 0 ? width * depth : 0;
}

function filterProposalForRoom() {
  const items = getLibraryProposalFurniture();
  if (!items.length) return;
  syncIntakeSizeToLegacyFields();
  applyDefaultRoomIfRequested();
  const { width, depth } = getRoomDimensionsFromInputs();
  if (!width || !depth) {
    elements.chatHint.textContent = "請先填房間寬度與深度，或勾選使用預設客廳，系統才能判斷要保留哪些家具。";
    return;
  }
  const roomAreaLimit = width * depth * 0.58;
  const sorted = [...items].sort((a, b) => proposalItemPriority(a) - proposalItemPriority(b));
  const kept = [];
  let usedArea = 0;
  for (const item of sorted) {
    const footprint = itemFootprintCm2(item);
    if (!kept.length || usedArea + footprint <= roomAreaLimit) {
      kept.push(item);
      usedArea += footprint;
    }
  }
  libraryProposal.furniture = kept;
  saveLibraryProposal();
  renderLibraryProposalSummary();
  elements.sceneStatus.textContent = `已依房間尺寸優先保留 ${kept.length} 件主家具；其餘家具先從本次生成移除。`;
}

function formatProposalItemName(item) {
  return item?.name_zh || item?.name_en || item?.title || item?.type_label || item?.normalized_type || "未命名家具";
}

function getRoomDimensionsFromInputs() {
  return {
    width: Number(elements.roomWidth?.value || elements.intakeWidth?.value || 0),
    depth: Number(elements.roomDepth?.value || elements.intakeDepth?.value || 0),
  };
}

function estimateProposalFootprintCm2() {
  return getLibraryProposalFurniture().reduce((sum, item) => {
    const size = item.size_cm || item.dimensions || {};
    const width = Number(size.width || size.w || 0);
    const depth = Number(size.depth || size.d || 0);
    return sum + (width > 0 && depth > 0 ? width * depth : 0);
  }, 0);
}

function updateProposalFitWarning() {
  if (!elements.proposalFitWarning) return;
  const items = getLibraryProposalFurniture();
  const { width, depth } = getRoomDimensionsFromInputs();
  if (!items.length || !width || !depth) {
    elements.proposalFitWarning.textContent = "";
    return;
  }
  const roomArea = width * depth;
  const furnitureArea = estimateProposalFootprintCm2();
  if (roomArea > 0 && furnitureArea > roomArea * 0.72) {
    elements.proposalFitWarning.textContent = "這批家具的占地偏大，若生成時放不下，請先刪除部分家具，或讓系統優先保留主家具後再渲染。";
    return;
  }
  elements.proposalFitWarning.textContent = "目前尺寸看起來可先嘗試配置；生成時仍會由擺放引擎檢查是否放得下。";
}

function renderLibraryProposalSummary() {
  const items = getLibraryProposalFurniture();
  if (!elements.proposalCard || !elements.proposalList) return;
  if (!items.length) {
    elements.proposalCard.hidden = true;
    elements.proposalList.innerHTML = "";
    return;
  }
  elements.proposalCard.hidden = false;
  elements.proposalSummary.textContent = `已從家具資料庫帶入 ${items.length} 件家具，下一步會補空間類型與房間尺寸。`;
  elements.proposalList.innerHTML = items.map((item, index) => `
    <li>
      <span class="scene-proposal-index">${index + 1}</span>
      <span>
        <strong>${escapeForHtml(formatProposalItemName(item))}</strong>
        <small>${escapeForHtml(item.type_label || item.normalized_type || "家具")} / ${escapeForHtml(formatSize(item.size_cm || item.dimensions || {}, item))}</small>
      </span>
      <button type="button" data-proposal-remove="${escapeForHtml(item.furniture_id)}">移除</button>
    </li>
  `).join("");
  updateProposalFitWarning();
}

function setSpaceTypeFromIntake(value) {
  if (!value || !elements.spaceType) return;
  elements.spaceType.value = value;
  elements.roomTypeQuestion?.querySelectorAll("[data-space-type]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.spaceType === value);
  });
  setDefaultFurnitureBySpace();
}

function syncIntakeSizeToLegacyFields() {
  if (elements.intakeWidth?.value) elements.roomWidth.value = elements.intakeWidth.value;
  if (elements.intakeDepth?.value) elements.roomDepth.value = elements.intakeDepth.value;
  updateProposalFitWarning();
}

function applyDefaultRoomIfRequested() {
  if (!elements.useDefaultRoom?.checked) return false;
  if (!elements.spaceType?.value) setSpaceTypeFromIntake("living_room");
  if (!elements.roomWidth?.value) elements.roomWidth.value = "420";
  if (!elements.roomDepth?.value) elements.roomDepth.value = "360";
  if (elements.intakeWidth && !elements.intakeWidth.value) elements.intakeWidth.value = "420";
  if (elements.intakeDepth && !elements.intakeDepth.value) elements.intakeDepth.value = "360";
  updateProposalFitWarning();
  return true;
}

function validateScenePrerequisites() {
  syncIntakeSizeToLegacyFields();
  applyDefaultRoomIfRequested();
  const missing = [];
  if (!elements.spaceType?.value) missing.push("空間類型");
  if (!Number(elements.roomWidth?.value)) missing.push("房間寬度");
  if (!Number(elements.roomDepth?.value)) missing.push("房間深度");
  const hasFurnitureNeed = selectedValues(elements.furnitureOptions).length > 0
    || splitCustomText(elements.customFurniture.value).length > 0
    || getLibraryProposalFurniture().length > 0;
  if (!hasFurnitureNeed) missing.push("家具需求或已選家具");
  if (missing.length) {
    return {
      ok: false,
      message: `請先補齊：${missing.join("、")}。如果暫時不知道尺寸，可以勾選「使用預設客廳 420 x 360 cm」。`,
    };
  }
  return { ok: true, message: "" };
}

function applyLibraryProposalDefaults() {
  if (!libraryProposal) return;
  const mappedSpace = LIBRARY_GROUP_TO_SPACE_TYPE[libraryProposal.selected_space_group];
  if (mappedSpace && !elements.spaceType?.value) {
    setSpaceTypeFromIntake(mappedSpace);
  }
  const proposalTypes = new Set(getProposalFurnitureTypes());
  elements.furnitureOptions?.querySelectorAll("input").forEach((input) => {
    if (proposalTypes.has(input.value)) input.checked = true;
  });
}

function configureSceneIntakeControls() {
  elements.roomTypeQuestion?.querySelectorAll("[data-space-type]").forEach((button) => {
    button.addEventListener("click", () => {
      setSpaceTypeFromIntake(button.dataset.spaceType);
      intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
      renderClientBrief();
      validateScenePrerequisites();
    });
  });
  elements.intakeWidth?.addEventListener("input", () => {
    syncIntakeSizeToLegacyFields();
    intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
    renderClientBrief();
  });
  elements.intakeDepth?.addEventListener("input", () => {
    syncIntakeSizeToLegacyFields();
    intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
    renderClientBrief();
  });
  elements.useDefaultRoom?.addEventListener("change", () => {
    applyDefaultRoomIfRequested();
    intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
    renderClientBrief();
  });
}

function startSceneFromEntryState() {
  libraryProposal = readLibraryProposal();
  renderLibraryProposalSummary();
  applyLibraryProposalDefaults();
  if (libraryProposal?.furniture?.length) {
    showWizardSection("chat");
    startGuidedIntake();
    elements.sceneStatus.textContent = "已帶入家具資料庫清單，請先補空間類型與房間尺寸。";
    return;
  }
  if (selectedStyleCardContext || requestedStyleId || requestedStyleCardId) {
    showWizardSection("chat");
    startGuidedIntake();
    return;
  }
  showWizardSection("floorplan");
}

function explainEmptyScene(sceneData) {
  if (!Array.isArray(sceneData.scene_objects)) sceneData.scene_objects = [];
  if (sceneData.scene_objects.length === 0) {
    return sceneData.reason || sceneData.warning || "沒有可放入家具。可能是家具尺寸超過房間、牆/門/窗淨空不足，或目前篩選條件找不到可用模型。請刪除部分家具，或讓系統改以主家具優先配置。";
  }
  return "";
}

function findSelectedStyleCardContext() {
  const group = (siteData.taiwan_style_cards || []).find((item) => item.cards?.some((card) => card.card_id === requestedStyleCardId));
  const card = group?.cards?.find((item) => item.card_id === requestedStyleCardId);
  return group && card ? { group, card } : null;
}

function renderSelectedStyleCard() {
  if (!elements.selectedStyleCard) return;
  const context = selectedStyleCardContext || findSelectedStyleCardContext();
  selectedStyleCardContext = context;
  if (!context) {
    elements.selectedStyleCard.hidden = true;
    elements.selectedStyleCard.innerHTML = "";
    return;
  }
  const palette = (context.card.palette_hex || [])
    .map((color) => `<span style="--swatch:${escapeForHtml(color)}"></span>`)
    .join("");
  elements.selectedStyleCard.hidden = false;
  elements.selectedStyleCard.innerHTML = `
    <div>
      <span>已選風格</span>
      <strong>${escapeForHtml(context.group.style_name_zh)}｜${escapeForHtml(context.card.name_zh)}</strong>
    </div>
    <div class="scene-selected-style-palette" aria-label="已選色票">${palette}</div>
  `;
}

function applySelectedStyleToBrief(brief) {
  const context = selectedStyleCardContext || findSelectedStyleCardContext();
  selectedStyleCardContext = context;
  if (!context || !brief) return brief;
  brief.style = brief.style || {};
  const intakeStyle = STYLE_CARD_TO_INTAKE_STYLE[context.group.scene_style_id] || context.group.scene_style_id;
  brief.style.preferred = Array.from(new Set([...(brief.style.preferred || []), intakeStyle].filter(Boolean)));
  brief.style.selected_card_id = context.card.card_id;
  brief.style.selected_card_name_zh = context.card.name_zh;
  brief.style.selected_style_name_zh = context.group.style_name_zh;
  brief.style.selected_palette_hex = context.card.palette_hex || [];
  return brief;
}

function seedClientBriefFromCurrentForm(brief = null) {
  const next = brief || {
    schema_version: "1.1",
    created_at: new Date().toISOString(),
    space: {},
    occupants: {},
    needs: [],
    style: {},
    constraints: [],
    notes: "",
    confirmation: { status: "draft", confirmed_at: null },
    evidence: [],
  };
  next.space = next.space || {};
  const formSpaceType = elements.spaceType?.value || "";
  const formWidth = Number(elements.roomWidth?.value || elements.intakeWidth?.value || 0);
  const formDepth = Number(elements.roomDepth?.value || elements.intakeDepth?.value || 0);
  if (!next.space.type && formSpaceType) next.space.type = formSpaceType;
  if (formWidth > 0) next.space.width_cm = formWidth;
  if (formDepth > 0) next.space.depth_cm = formDepth;
  next.constraints = Array.from(new Set([
    ...(next.constraints || []),
    elements.keepWindowClear?.checked ? "keep_window_clear" : "",
    elements.keepDoorClear?.checked ? "keep_door_clear" : "",
  ].filter(Boolean)));
  return applySelectedStyleToBrief(next);
}

function mergeUserAnswerIntoBrief(answer) {
  const brief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
  brief.notes = [brief.notes, answer].filter(Boolean).join("\n").trim();
  brief.evidence = [...(brief.evidence || []), answer];
  const lowered = answer.toLowerCase();
  const inferredNeeds = [];
  if (/收納|櫃|storage/i.test(answer)) inferredNeeds.push("storage");
  if (/工作|書桌|辦公|office|work/i.test(answer)) inferredNeeds.push("work");
  if (/閱讀|書|reading/i.test(answer)) inferredNeeds.push("reading");
  if (/休息|睡|躺|放鬆|rest/i.test(answer)) inferredNeeds.push("rest");
  if (/朋友|聚會|接待|客人|entertain/i.test(answer)) inferredNeeds.push("entertaining");
  if (inferredNeeds.length) {
    brief.needs = Array.from(new Set([...(brief.needs || []), ...inferredNeeds]));
  }
  if (/兩位|2人|2 人|夫妻|大人/i.test(answer)) brief.occupants = { ...(brief.occupants || {}), adults: 2 };
  if (/一位|1人|1 人|單人/i.test(answer)) brief.occupants = { ...(brief.occupants || {}), adults: 1 };
  if (/小孩|孩子|兒童/i.test(answer)) brief.occupants = { ...(brief.occupants || {}), children: Math.max(1, Number(brief.occupants?.children || 0)) };
  if (/長輩|老人|高齡/i.test(answer)) brief.occupants = { ...(brief.occupants || {}), elderly: Math.max(1, Number(brief.occupants?.elderly || 0)) };
  if (/採光|窗|window/i.test(answer)) brief.constraints = Array.from(new Set([...(brief.constraints || []), "keep_window_clear"]));
  if (/門|出入口|動線|走道/i.test(answer)) brief.constraints = Array.from(new Set([...(brief.constraints || []), "keep_door_clear", "keep_wide_walkway"]));
  return brief;
}

function showWizardSection(section) {
  const sections = {
    welcome: elements.welcomePanel,
    floorplan: elements.floorplanStep,
    chat: elements.chatPanel,
    brief: elements.briefPanel,
    style: elements.styleCardPanel,
  };
  Object.entries(sections).forEach(([key, element]) => {
    if (element) {
      element.hidden = key !== section;
      if (key === section) {
        element.classList.remove("wizard-enter");
        void element.offsetWidth;
        element.classList.add("wizard-enter");
      }
    }
  });
  const isFinal = section === "final";
  if (elements.formPanel) elements.formPanel.hidden = isFinal;
  if (elements.viewerSide) elements.viewerSide.hidden = !isFinal;
  document.body.dataset.sceneStage = section;
  document.querySelectorAll("[data-wizard-step]").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.wizardStep === section);
    item.classList.toggle("is-complete", ["chat", "brief", "final"].includes(section) && item.dataset.wizardStep === "floorplan");
  });
}

const SURFACE_DISPLAY = {
  wood_light_oak_floor_039: {
    label: "淺橡木木地板",
    materialGroup: "木地板",
    category: "wood",
    colorZh: "淺橡木色",
    description: "明亮自然的真木紋，適合北歐、無印與清爽住宅基底。",
  },
  wood_warm_floor_051: {
    label: "溫潤橡木木地板",
    materialGroup: "木地板",
    category: "wood",
    colorZh: "暖橡木色",
    description: "木節與色差更明顯，適合美式、鄉村與混搭暖調空間。",
  },
  wood_deep_floor_064: {
    label: "深胡桃木木地板",
    materialGroup: "木地板",
    category: "wood",
    colorZh: "深胡桃木色",
    description: "深色木紋讓空間更沉穩，適合美拉德、美式與古典調性。",
  },
  wood_dark_panel_093: {
    label: "深色木紋牆板",
    materialGroup: "木紋牆板",
    category: "wood",
    colorZh: "深木色",
    description: "適合重點牆或局部包覆，能增加空間層次與深度。",
  },
  woodtile_light_cci212048: {
    label: "淺木紋磚",
    materialGroup: "木紋磚",
    category: "wood_tile",
    colorZh: "淺木色",
    description: "保留木紋溫度但更耐磨，適合牆面與地坪一起使用。",
  },
  woodtile_warm_cal288017: {
    label: "暖木紋磚",
    materialGroup: "木紋磚",
    category: "wood_tile",
    colorZh: "暖木色",
    description: "帶橘棕調的木紋磚，適合鄉村、美式與侘寂混搭。",
  },
  woodtile_gray_cdg212132: {
    label: "灰木紋磚",
    materialGroup: "木紋磚",
    category: "wood_tile",
    colorZh: "灰木色",
    description: "比木地板更俐落，適合現代、工業與冷調空間。",
  },
  woodtile_clean_cal160101: {
    label: "淨灰木紋磚",
    materialGroup: "木紋磚",
    category: "wood_tile",
    colorZh: "淺灰木色",
    description: "紋理較低調，適合無印、北歐現代與低彩度空間。",
  },
  tile_marble_cal330121: {
    label: "米白大理石磚",
    materialGroup: "磁磚 / 石材",
    category: "tile",
    colorZh: "米白色",
    description: "亮面石紋更精緻，適合現代、輕奢與古典局部牆面。",
  },
  tile_gray_cdg212132: {
    label: "灰石紋磁磚",
    materialGroup: "磁磚 / 石材",
    category: "tile",
    colorZh: "石灰色",
    description: "霧面灰石紋，適合工業、現代與侘寂風格。",
  },
  tile_warm_ced360298: {
    label: "暖灰霧面磁磚",
    materialGroup: "磁磚 / 石材",
    category: "tile",
    colorZh: "暖灰色",
    description: "柔和霧面質感，適合作為安靜、低彩度的牆地基底。",
  },
  tile_pattern_cal288001: {
    label: "花磚 / 圖紋磚",
    materialGroup: "磁磚 / 石材",
    category: "tile",
    colorZh: "圖紋暖色",
    description: "視覺重點較強，適合玄關、局部牆面或混搭風地坪。",
  },
};

const SURFACE_FILTER_LABELS = {
  all: "全部資料庫推薦",
  wood: "木地板 / 木紋",
  wood_tile: "木紋磚",
  tile: "磁磚 / 石材",
};

Object.assign(SURFACE_FILTER_LABELS, {
  paint: "塗料牆",
  wall_tile: "壁磚",
  wallpaper: "壁紙 / 織物",
  wood_wall: "木質牆板",
  generated: "程式生成",
});

function getStyleSurfaceProfile(styleId = elements.stylePreference?.value || "scandinavian") {
  return surfaceCatalog.style_surface_profiles?.[styleId] || surfaceCatalog.style_surface_profiles?.scandinavian || null;
}

function surfaceToOption(surface, usage) {
  const display = SURFACE_DISPLAY[surface.surface_id] || {};
  return {
    id: surface.surface_id,
    label: display.label || surface.name_zh || surface.surface_id,
    colorZh: display.colorZh || surface.color_zh || surface.material_group,
    colorHex: surface.color_hex || "#d8c8b5",
    materialGroup: display.materialGroup || surface.material_group || "材質",
    category: display.category || surface.category || "tile",
    description: display.description || surface.style_notes_zh || "資料庫材質，可依目前風格套用到牆面或地板。",
    preview: surface.preview_url || "",
    previewUrl: surface.preview_url,
    suitableStyles: surface.suitable_styles || [],
    usage,
  };
}

function buildSurfaceOptions(usage, styleId = elements.stylePreference?.value || "scandinavian") {
  const profile = getStyleSurfaceProfile(styleId);
  const ids = usage === "wall" ? profile?.wall_surface_ids : profile?.floor_surface_ids;
  const surfaces = (ids || [])
    .map((surfaceId) => surfaceById.get(surfaceId))
    .filter((surface) => surface?.usage?.includes(usage))
    .map((surface) => surfaceToOption(surface, usage));
  const allSurfaces = (surfaceCatalog.surfaces || [])
    .filter((surface) => surface?.usage?.includes(usage))
    .map((surface) => surfaceToOption(surface, usage));
  const seen = new Set(surfaces.map((surface) => surface.id));
  const rest = allSurfaces.filter((surface) => !seen.has(surface.id));
  const generatedWalls = fallbackSurfaces.wall.map((option) => ({
    ...option,
    category: "generated",
    materialGroup: option.materialGroup || "程式生成",
    suitableStyles: [styleId],
    usage: "wall",
  }));
  const pool = usage === "wall"
    ? (surfaces.length || allSurfaces.length ? [...surfaces, ...rest, ...generatedWalls] : generatedWalls)
    : surfaces.length
      ? [...surfaces, ...rest]
      : (allSurfaces.length ? allSurfaces : fallbackSurfaces.floor);
  return [
    {
      id: "auto",
      label: usage === "wall" ? "依風格自動牆面" : "依風格自動地板",
      colorZh: pool[0]?.colorZh || "依風格",
      colorHex: pool[0]?.colorHex || "#d8c8b5",
      materialGroup: pool[0]?.materialGroup || "自動",
      category: "all",
      description: "由目前風格的資料庫材質池自動挑選預設搭配。",
      preview: pool[0]?.preview || "",
    },
    ...pool,
  ];
}

function surfacePreviewCss(option) {
  const preview = option.preview || "";
  const previewValue = preview.startsWith("linear-gradient") || preview.startsWith("radial-gradient")
    ? preview
    : `url('${preview}')`;
  return `--surface-preview:${previewValue}; --surface-color:${option.colorHex || "#d8c8b5"}`;
}

function refreshSurfaceLabelMaps(styleId = elements.stylePreference?.value || "scandinavian") {
  wallOptionLabelMap = new Map(buildSurfaceOptions("wall", styleId).map((option) => [option.id, option.label]));
  floorOptionLabelMap = new Map(buildSurfaceOptions("floor", styleId).map((option) => [option.id, option.label]));
}

function getStyleSceneLook(styleId = elements.stylePreference.value) {
  const profile = getStyleSurfaceProfile(styleId);
  return {
    wall: profile?.default_wall_surface_id || "auto",
    floor: profile?.default_floor_surface_id || "auto",
  };
}

function renderStyleOptions() {
  elements.stylePreference.innerHTML = siteData.styles
    .map((style) => `<option value="${style.style_id}">${style.style_name_zh}</option>`)
    .join("");
  if (siteData.styles.some((style) => style.style_id === "scandinavian")) {
    elements.stylePreference.value = "scandinavian";
  }
}

function normalizeColorText(value) {
  return String(value || "").trim().toLowerCase();
}

function colorOptionMatches(option, token) {
  const normalized = normalizeColorText(token);
  return normalizeColorText(option.label) === normalized ||
    normalizeColorText(option.value) === normalized ||
    option.aliases?.some((alias) => normalized.includes(normalizeColorText(alias)));
}

function splitFurnitureColor(value) {
  return String(value || "")
    .replace(/[，、/]/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildColorOptions() {
  const options = [...COLOR_OPTION_PRESETS];
  const seen = new Set(options.map((option) => option.value));
  const colorCounts = new Map();
  (siteData.furniture || []).forEach((item) => {
    splitFurnitureColor(item.color).forEach((token) => {
      const option = options.find((candidate) => colorOptionMatches(candidate, token));
      if (!option) return;
      colorCounts.set(option.value, (colorCounts.get(option.value) || 0) + 1);
    });
  });
  return options
    .filter((option) => {
      if (["白色", "米白", "奶油白", "米色", "淺木色", "淺灰", "黑色", "胡桃木"].includes(option.value)) return true;
      return colorCounts.has(option.value);
    })
    .filter((option) => {
      if (seen.has(option.value)) return true;
      seen.add(option.value);
      return true;
    })
    .sort((a, b) => (colorCounts.get(b.value) || 0) - (colorCounts.get(a.value) || 0));
}

function renderToggleOptions(container, options, name) {
  container.innerHTML = options
    .map(
      (option) => `
        <label class="scene-option ${option.colorHex ? "has-color-swatch" : ""}">
          <input type="checkbox" name="${name}" value="${option.value || option}" />
          ${option.colorHex ? `<i class="scene-color-swatch" style="background:${option.colorHex}"></i>` : ""}
          <span>${option.label || option}</span>
        </label>
      `
    )
    .join("");
}

function renderAddFurnitureSelect() {
  elements.addFurnitureType.innerHTML = furnitureOptions
    .map((option) => `<option value="${option.value}">${option.label}</option>`)
    .join("");
}

function normalizeSearchText(value) {
  return String(value || "").trim().toLowerCase();
}

function surfaceOptionText(option) {
  return [option.label, option.colorZh, option.materialGroup, option.id, option.category]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function compactFurnitureName(item) {
  const name = formatFurnitureName(item);
  if (name.length <= 28) return name;
  const parts = name.split(/[，,]/).map((part) => part.trim()).filter(Boolean);
  if (parts.length >= 2) {
    const compact = `${parts[0]}，${parts[parts.length - 1]}`;
    if (compact.length <= 32) return compact;
  }
  return `${name.slice(0, 24)}...`;
}

function renderVisualOptions(container, options, name, usage) {
  const selectedValue = selectedRadio(container, name);
  const activeFilter = surfaceFilters[usage] || "all";
  const currentStyleId = elements.stylePreference.value;
  const currentStyleName = styleNameById.get(currentStyleId) || "目前風格";
  const categories = [...new Set(options.filter((option) => option.id !== "auto").map((option) => option.category))];
  const query = normalizeSearchText(surfaceSearchQueries[usage]);
  const matchedOptions = options.filter((option) => {
    const categoryMatch = activeFilter === "all" || option.category === activeFilter;
    const queryMatch = !query || surfaceOptionText(option).includes(query);
    const styleMatch = !surfaceStyleOnly[usage] || option.id === "auto" || option.suitableStyles?.includes(currentStyleId);
    return categoryMatch && queryMatch && styleMatch;
  });
  const isSearchableSurface = usage === "floor" || usage === "wall";
  const visibleLimit = surfaceVisibleLimits[usage] || matchedOptions.length;
  const visibleOptions = isSearchableSurface ? matchedOptions.slice(0, visibleLimit) : matchedOptions;
  const hasMore = isSearchableSurface && matchedOptions.length > visibleOptions.length;
  const surfaceNoun = usage === "wall" ? "牆面材質" : "地板材質";
  const searchPlaceholder = usage === "wall" ? "搜尋牆面：塗料、壁磚、木牆板..." : "搜尋地板：木地板、木紋磚、磁磚、ID...";
  const nextChecked = matchedOptions.some((option) => option.id === selectedValue) ? selectedValue : matchedOptions[0]?.id;
  container.innerHTML = options
    ? `
      <div class="scene-surface-filter-row">
        ${usage === "floor" ? `
          <input class="scene-surface-search" type="search" value="${surfaceSearchQueries.floor}" placeholder="搜尋地板：木紋、磁磚、灰色、ID..." data-surface-search="floor" />
          <button type="button" class="scene-surface-filter ${surfaceStyleOnly.floor ? "active" : ""}" data-surface-style-only="floor">
            只看目前風格
          </button>
        ` : ""}
        ${["all", ...categories]
          .map(
            (category) => `
              <button type="button" class="scene-surface-filter ${activeFilter === category ? "active" : ""}" data-surface-usage="${usage}" data-surface-filter="${category}">
                ${SURFACE_FILTER_LABELS[category] || category}
              </button>
            `
          )
          .join("")}
        ${usage === "floor" ? `<span class="scene-surface-count">${matchedOptions.length} 筆結果</span>` : ""}
      </div>
      ${visibleOptions
    .map(
      (option) => `
        <label class="scene-visual-option">
          <input type="radio" name="${name}" value="${option.id}" ${option.id === nextChecked ? "checked" : ""} />
          <span class="scene-visual-swatch" style="${surfacePreviewCss(option)}"></span>
          <span class="scene-visual-label">${option.label}</span>
          <span class="scene-visual-meta">
            <i style="background:${option.colorHex || "#d8c8b5"}"></i>
            ${option.colorZh || "材質色"} / ${option.materialGroup || "材質"}
          </span>
          <span class="scene-visual-description">
            <b>適合風格</b>
            <em>${currentStyleName}</em>
          </span>
        </label>
      `
    )
    .join("")}
      ${hasMore ? `
        <button type="button" class="scene-surface-more" data-surface-more="${usage}">
          顯示更多地板材質
        </button>
      ` : ""}
    `
    : "";
  container.querySelectorAll('[data-surface-filter="all"]').forEach((button) => {
    button.textContent = `全部${surfaceNoun}`;
  });
  container.querySelectorAll("[data-surface-more]").forEach((button) => {
    button.textContent = `顯示更多${surfaceNoun}`;
  });
  container.querySelectorAll(".scene-surface-count").forEach((label) => {
    label.textContent = `${matchedOptions.length} 筆${surfaceNoun}`;
  });
}

function setRadioValue(container, name, value) {
  const target = container.querySelector(`input[name="${name}"][value="${value}"]`);
  if (target) target.checked = true;
}

function syncSurfaceChoicesToStyle() {
  const styleId = elements.stylePreference.value;
  renderVisualOptions(elements.wallOptions, buildSurfaceOptions("wall", styleId), "wall-option", "wall");
  renderVisualOptions(elements.floorOptions, buildSurfaceOptions("floor", styleId), "floor-option", "floor");
  refreshSurfaceLabelMaps(styleId);
  const sceneLook = getStyleSceneLook(styleId);
  setRadioValue(elements.wallOptions, "wall-option", sceneLook.wall);
  setRadioValue(elements.floorOptions, "floor-option", sceneLook.floor);
}

function selectedValues(container) {
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
}

function selectedRadio(container, name) {
  return container.querySelector(`input[name="${name}"]:checked`)?.value || "auto";
}

function handleSurfaceFilterClick(event) {
  const styleOnlyButton = event.target.closest("[data-surface-style-only]");
  if (styleOnlyButton) {
    event.preventDefault();
    const usage = styleOnlyButton.dataset.surfaceStyleOnly;
    surfaceStyleOnly[usage] = !surfaceStyleOnly[usage];
    surfaceVisibleLimits[usage] = 12;
    if (usage === "wall") {
      renderVisualOptions(elements.wallOptions, buildSurfaceOptions("wall", elements.stylePreference.value), "wall-option", "wall");
    } else {
      renderVisualOptions(elements.floorOptions, buildSurfaceOptions("floor", elements.stylePreference.value), "floor-option", "floor");
    }
    return;
  }

  const moreButton = event.target.closest("[data-surface-more]");
  if (moreButton) {
    event.preventDefault();
    const usage = moreButton.dataset.surfaceMore;
    surfaceVisibleLimits[usage] = (surfaceVisibleLimits[usage] || 12) + 12;
    if (usage === "wall") {
      renderVisualOptions(elements.wallOptions, buildSurfaceOptions("wall", elements.stylePreference.value), "wall-option", "wall");
    } else {
      renderVisualOptions(elements.floorOptions, buildSurfaceOptions("floor", elements.stylePreference.value), "floor-option", "floor");
    }
    return;
  }

  const button = event.target.closest("[data-surface-filter]");
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  const usage = button.dataset.surfaceUsage;
  if (!usage) return;
  surfaceFilters[usage] = button.dataset.surfaceFilter || "all";
  const styleId = elements.stylePreference.value;
  if (usage === "wall") {
    renderVisualOptions(elements.wallOptions, buildSurfaceOptions("wall", styleId), "wall-option", "wall");
  }
  if (usage === "floor") {
    renderVisualOptions(elements.floorOptions, buildSurfaceOptions("floor", styleId), "floor-option", "floor");
  }
}

function handleSurfaceSearchInput(event) {
  const input = event.target.closest("[data-surface-search]");
  if (!input) return;
  const usage = input.dataset.surfaceSearch;
  surfaceSearchQueries[usage] = input.value;
  surfaceVisibleLimits[usage] = 12;
  if (usage === "wall") {
    renderVisualOptions(elements.wallOptions, buildSurfaceOptions("wall", elements.stylePreference.value), "wall-option", "wall");
  } else {
    renderVisualOptions(elements.floorOptions, buildSurfaceOptions("floor", elements.stylePreference.value), "floor-option", "floor");
  }
  const nextInput = (usage === "wall" ? elements.wallOptions : elements.floorOptions).querySelector("[data-surface-search]");
  nextInput?.focus();
  if (nextInput) nextInput.selectionStart = nextInput.selectionEnd = nextInput.value.length;
}

function getResolvedSurfaceChoice(container, name, fallbackValue) {
  const value = selectedRadio(container, name);
  return value === "auto" ? fallbackValue : value;
}

function splitCustomText(value) {
  return value
    .split(/[,\u3001\uff0c]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function setFurnitureSelection(values) {
  const wanted = new Set(values);
  elements.furnitureOptions.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    input.checked = wanted.has(input.value);
  });
}

function setDefaultFurnitureBySpace() {
  if (!elements.spaceType.value) {
    setFurnitureSelection([]);
    return;
  }
  setFurnitureSelection(DEFAULT_FURNITURE_BY_SPACE[elements.spaceType.value] || []);
}

function sampleRandom(items, count) {
  const pool = [...items];
  const picked = [];
  while (pool.length && picked.length < count) {
    const index = Math.floor(Math.random() * pool.length);
    picked.push(pool.splice(index, 1)[0]);
  }
  return picked;
}

function randomizeFurnitureSelection() {
  furnitureRandomSeed = Date.now();
  const allInputs = Array.from(elements.furnitureOptions.querySelectorAll('input[type="checkbox"]'));
  allInputs.forEach((input) => {
    input.checked = false;
  });
  const currentStyleId = elements.stylePreference.value;
  const currentStyle = siteData.styles.find((style) => style.style_id === currentStyleId);
  const preferredTypes = (currentStyle?.stats?.top_types ?? [])
    .map(([typeName]) => typeName)
    .filter((typeName) => allInputs.some((input) => input.value === typeName));
  const primaryPool = preferredTypes.length ? allInputs.filter((input) => preferredTypes.includes(input.value)) : allInputs;
  const desiredCount = Math.min(Math.max(3, Math.floor(Math.random() * 4) + 3), allInputs.length);
  const picked = sampleRandom(primaryPool, Math.min(desiredCount, primaryPool.length));
  if (picked.length < desiredCount) {
    picked.push(...sampleRandom(allInputs.filter((input) => !picked.includes(input)), desiredCount - picked.length));
  }
  picked.forEach((input) => {
    input.checked = true;
  });
  elements.sceneStatus.textContent = `已依 ${currentStyle?.style_name_zh || "目前風格"} 重抽 ${picked.length} 種家具類型。`;
}

function getTypeLabel(type) {
  return furnitureOptions.find((option) => option.value === type)?.label || formatTypeLabel(type);
}

function sizeValue(size, key, fallback) {
  const value = Number(size?.[key]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function normalizeSizeCm(size = {}) {
  return {
    width: sizeValue(size, "width", 120),
    depth: sizeValue(size, "depth", 60),
    height: sizeValue(size, "height", 80),
  };
}

function styleMatchesFurniture(item, styleId) {
  return (
    item.primary_style === styleId ||
    item.style_candidates?.some((style) => {
      const candidateStyleId = Array.isArray(style) ? style[0] : style?.style_id ?? style;
      const score = Array.isArray(style) ? Number(style[1] ?? 1) : Number(style?.score ?? 1);
      return candidateStyleId === styleId && score > 0;
    })
  );
}

async function pickFurnitureCandidate(type, usedIds = new Set()) {
  if (!currentSceneData) return null;
  const styleId = currentSceneData.style.style_id;
  const styledResult = await fetchFurniturePage({ style: styleId, type, page: 1, page_size: 80, has_model: true, detail: "scene" });
  let pool = (styledResult.items || []).filter((item) => !usedIds.has(item.furniture_id));
  if (!pool.length) {
    const fallbackResult = await fetchFurniturePage({ type, page: 1, page_size: 80, has_model: true, detail: "scene" });
    pool = (fallbackResult.items || []).filter((item) => !usedIds.has(item.furniture_id));
  }
  if (!pool.length) return null;
  const topPool = pool.slice(0, Math.min(pool.length, 28));
  return topPool[Math.floor(Math.random() * topPool.length)];
}

function sceneObjectFromFurniture(item) {
  return {
    furniture_id: item.furniture_id,
    name_zh_raw: formatFurnitureName(item),
    normalized_type: item.normalized_type,
    model_url: item.model_url,
    primary_style: item.primary_style,
    size_cm: normalizeSizeCm(item.size_cm),
    role: item.role || "",
    quantity: item.quantity || { min: null, max: null, recommended: null },
    placement_hints: item.placement_hints || {},
    clearance_zones: item.clearance_zones || [],
    layout_relations: item.layout_relations || [],
    match_reason: item.match_reason || "",
    rule: item.rule || {},
    position_cm: { x: 0, z: 0 },
    rotation_y_deg: 0,
  };
}

async function reflowSceneObjects(sceneData) {
  try {
    const response = await fetch("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_width_cm: Number(sceneData.floorplan?.width_cm) || 420,
        room_depth_cm: Number(sceneData.floorplan?.depth_cm) || 360,
        floorplan: sceneData.floorplan || null,
        scene_objects: sceneData.scene_objects,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (Array.isArray(data.scene_objects)) sceneData.scene_objects = data.scene_objects;
  } catch (error) {
    console.warn("重新配置家具失敗，保留目前位置。", error);
  }
}

async function refreshCurrentScene(statusMessage = "") {
  if (!currentSceneData) return;
  updateSummary(currentSceneData);
  await viewer.loadScene(currentSceneData);
  if (statusMessage) elements.sceneStatus.textContent = statusMessage;
}

async function applySurfaceChoiceToCurrentScene(event = null) {
  if (event && !event.target?.matches('input[type="radio"]')) return;
  const styleId = elements.stylePreference.value;
  const sceneLook = getStyleSceneLook(styleId);
  const wallOption = getResolvedSurfaceChoice(elements.wallOptions, "wall-option", sceneLook.wall);
  const floorOption = getResolvedSurfaceChoice(elements.floorOptions, "floor-option", sceneLook.floor);

  if (!currentSceneData) {
    elements.sceneStatus.textContent = "牆面與地板選擇已更新，生成 3D 場景後會套用。";
    return;
  }

  currentSceneData.design_choices = {
    ...(currentSceneData.design_choices || {}),
    wall_option: wallOption,
    floor_option: floorOption,
  };
  await refreshCurrentScene("已套用目前選擇的牆面與地板材質。");
}

function setGeneratingState(active) {
  elements.generateScene.disabled = active;
  elements.generateScene.textContent = active ? "生成中..." : "生成 3D 場景";
}

function renderSelectedItems(sceneData) {
  elements.sceneSelectedItems.innerHTML = "";
  if (!sceneData.scene_objects.length) {
    elements.sceneSelectedItems.innerHTML = `<p class="scene-selected-empty">目前尚未加入家具。</p>`;
    return;
  }
  sceneData.scene_objects.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "scene-selected-item";
    row.innerHTML = `
      <span class="scene-selected-index">${index + 1}</span>
      <div class="scene-selected-copy">
        <strong title="${formatFurnitureName(item)}">${compactFurnitureName(item)}</strong>
        <small>${getTypeLabel(item.normalized_type)} / ${formatSize(item.size_cm, item)}</small>
      </div>
      <div class="scene-selected-actions">
        <button type="button" data-furniture-action="replace" data-index="${index}">同風格替換</button>
        <button type="button" data-furniture-action="remove" data-index="${index}">移除</button>
      </div>
    `;
    elements.sceneSelectedItems.appendChild(row);
  });
}

function updateSummary(sceneData) {
  elements.sceneStyleName.textContent = sceneData.style.style_name_zh;
  elements.sceneLlmMode.textContent = sceneData.llm_mode === "openrouter" ? "OpenRouter" : "規則 fallback";
  elements.sceneItemCount.textContent = String(sceneData.scene_objects.length);
  elements.sceneRoomSize.textContent = `${sceneData.floorplan.width_cm} x ${sceneData.floorplan.depth_cm} cm`;
  const background = sceneData.style.scene_background || {};
  const sceneLook = getStyleSceneLook(sceneData.style.style_id);
  const wallChoice = sceneData.design_choices?.wall_option || sceneLook.wall;
  const floorChoice = sceneData.design_choices?.floor_option || sceneLook.floor;
  elements.sceneBackground.textContent = [
    `牆面：${wallOptionLabelMap.get(wallChoice) || background.wall_zh || "依風格自動"}`,
    `地板：${floorOptionLabelMap.get(floorChoice) || background.floor_zh || "依風格自動"}`,
    background.overall_zh ? `整體：${background.overall_zh}` : "",
  ]
    .filter(Boolean)
    .join(" / ");
  renderSelectedItems(sceneData);
}

function renderInitialProviderStatus() {
  if (providerStatus.enabled) {
    elements.sceneLlmMode.textContent = providerStatus.model ? `OpenRouter / ${providerStatus.model}` : "OpenRouter";
    elements.sceneStatus.textContent = "OpenRouter 已啟用，可使用 LLM 生成場景配置。";
    return;
  }
  elements.sceneLlmMode.textContent = "規則 fallback";
  elements.sceneStatus.textContent = "OpenRouter 尚未啟用，目前使用規則版配置流程。";
}

function applyStyleCardFromQuery() {
  const requestedStyle = (siteData.styles || []).find((style) => style.style_id === requestedStyleId);
  if (requestedStyle) {
    elements.stylePreference.value = requestedStyle.style_id;
  }
  const styleGroup = (siteData.taiwan_style_cards || []).find((group) => group.cards?.some((card) => card.card_id === requestedStyleCardId));
  const card = styleGroup?.cards?.find((item) => item.card_id === requestedStyleCardId);
  if (!card) return;
  elements.customColors.value = card.palette_hex.join(", ");
  elements.sceneStatus.textContent = `已帶入「${styleGroup.style_name_zh}｜${card.name_zh}」色卡，生成時會同步套用。`;
}

function appendChatMessage(role, text) {
  if (!elements.chatMessages || !text) return;
  const message = document.createElement("div");
  message.className = `scene-chat-message ${role === "user" ? "is-user" : "is-ai"}`;
  message.innerHTML = `<span class="scene-chat-role">${role === "user" ? "你" : "RoomPilot AI"}</span><p></p>`;
  message.querySelector("p").textContent = text;
  elements.chatMessages.appendChild(message);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function renderClientBrief() {
  if (!elements.briefSummary || !intakeState.clientBrief) return;
  const brief = intakeState.clientBrief;
  const spaceLabels = {
    living_room: "客廳",
    bedroom: "臥室",
    workspace: "書房 / 工作空間",
    dining_room: "餐廳",
    studio: "套房",
  };
  const styleLabels = {
    japanese: "日式 / 無印",
    scandinavian: "北歐",
    modern: "現代簡約",
    industrial: "工業風",
    american: "美式",
    light_luxury: "輕奢",
    warm_neutral: "溫暖中性色",
  };
  const needLabels = {
    storage: "收納",
    work: "工作",
    reading: "閱讀",
    display: "展示",
    entertaining: "接待 / 聚會",
    rest: "休息",
  };
  const materialLabels = { wood: "木質", stone: "石材", fabric: "布料", metal: "金屬", glass: "玻璃" };
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const labels = (values, dictionary) => (values || []).map((value) => dictionary[value] || value).filter(Boolean);
  const occupants = brief.occupants || {};
  const people = [
    occupants.adults ? `${occupants.adults} 位成人` : "",
    occupants.children ? `${occupants.children} 位小孩` : "",
    occupants.elderly ? `${occupants.elderly} 位長輩` : "",
    occupants.pets ? `${occupants.pets} 隻寵物` : "",
  ].filter(Boolean);
  const cards = [
    ["規劃空間", spaceLabels[brief.space?.type] || "尚未指定"],
    ["使用者", people.join("、") || "一般居住使用"],
    ["生活需求", labels(brief.needs, needLabels).join("、") || "依空間功能配置"],
    ["風格方向", labels(brief.style?.preferred, styleLabels).join("、") || "由系統推薦"],
    ["偏好材質", labels(brief.style?.materials, materialLabels).join("、") || "依風格搭配"],
    ["空間限制", labels(brief.constraints, {
      keep_window_clear: "保留窗邊採光",
      keep_door_clear: "保持出入口動線",
      keep_wide_walkway: "保留寬走道",
      keep_existing: "保留既有設備",
    }).join("、") || "無特別限制"],
  ];
  elements.briefSummary.innerHTML = cards.map(([label, value]) => `
    <div class="scene-brief-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join("");
  elements.chatConfirm.disabled = !intakeState.clientBrief || Boolean(intakeState.step);
}

function syncClientBriefToLegacyFields() {
  const brief = intakeState.clientBrief;
  if (!brief) return;
  const space = brief.space || {};
  const style = brief.style || {};
  if (space.type && [...elements.spaceType.options].some((option) => option.value === space.type)) {
    elements.spaceType.value = space.type;
  }
  if (space.width_cm) elements.roomWidth.value = space.width_cm;
  if (space.depth_cm) elements.roomDepth.value = space.depth_cm;
  const preferredStyle = style.preferred?.find((id) => [...elements.stylePreference.options].some((option) => option.value === id));
  if (preferredStyle) elements.stylePreference.value = preferredStyle;
  elements.keepWindowClear.checked = brief.constraints?.includes("keep_window_clear") ?? true;
  elements.keepDoorClear.checked = brief.constraints?.includes("keep_door_clear") ?? true;
  elements.needStorage.checked = brief.needs?.includes("storage") ?? false;
  elements.preferLowSaturation.checked = style.colors?.includes("low_saturation") ?? false;
  setDefaultFurnitureBySpace();
  syncSurfaceChoicesToStyle();
}

async function startGuidedIntake() {
  if (!elements.chatMessages) return;
  const sessionId = `roompilot-${Date.now()}`;
  try {
    const response = await fetch("/api/agent/intake/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    intakeState = { sessionId: result.session_id, step: result.step, clientBrief: result.client_brief, confirmed: false };
    appendChatMessage("ai", result.question);
    renderClientBrief();
  } catch (error) {
    console.error(error);
    appendChatMessage("ai", "目前無法連線到需求訪談服務，請稍後再試。");
    elements.sceneStatus.textContent = "需求訪談 API 連線失敗。";
  }
}

function drawDxfPreview(plan) {
  const canvas = document.createElement("canvas");
  canvas.width = 720;
  canvas.height = 420;
  canvas.className = "floorplan-preview-canvas";
  const context = canvas.getContext("2d");
  const bbox = plan?.bbox || {};
  const width = Number(plan?.width_cm || ((Number(bbox.maxx) - Number(bbox.minx)) * 100) || 420);
  const depth = Number(plan?.depth_cm || ((Number(bbox.maxz) - Number(bbox.minz)) * 100) || 360);
  context.fillStyle = "#faf7f2";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = "#775c46";
  context.lineWidth = 5;
  const normalizeSegments = (rawSegments) => (Array.isArray(rawSegments) ? rawSegments : []).flatMap((segment) => {
    if (segment?.start && segment?.end) {
      return [{
        start: { x: Number(segment.start.x || 0), z: Number(segment.start.z ?? segment.start.y ?? 0) },
        end: { x: Number(segment.end.x || 0), z: Number(segment.end.z ?? segment.end.y ?? 0) },
      }];
    }
    if (segment && [segment.x1, segment.z1, segment.x2, segment.z2].every((value) => Number.isFinite(Number(value)))) {
      return [{
        start: { x: Number(segment.x1) * 100, z: Number(segment.z1) * 100 },
        end: { x: Number(segment.x2) * 100, z: Number(segment.z2) * 100 },
      }];
    }
    return [];
  });
  let segments = normalizeSegments(plan?.wall_segments || plan?.plan_segments);
  // Older `/api/upload` responses expose wall_polys in metres. Convert their
  // polygon edges to the same centimetre segment shape used by the current API.
  if (!segments.length && Array.isArray(plan?.wall_polys)) {
    segments = plan.wall_polys.flatMap((polygon) => {
      const ring = Array.isArray(polygon?.exterior) ? polygon.exterior : [];
      return ring.map((point, index) => {
        const next = ring[(index + 1) % ring.length] || point;
        return {
          start: { x: Number(point?.[0] || 0) * 100, z: Number(point?.[1] || 0) * 100 },
          end: { x: Number(next?.[0] || 0) * 100, z: Number(next?.[1] || 0) * 100 },
        };
      });
    });
  }
  const doorSegments = normalizeSegments(plan?.door_segments || plan?.doors);
  const windowSegments = normalizeSegments(plan?.window_segments || plan?.windows);
  const points = [...segments, ...doorSegments, ...windowSegments].flatMap((segment) => [segment.start, segment.end]).map((point) => ({
    x: Number(point?.x || 0),
    z: Number(point?.z ?? point?.y ?? 0),
  }));
  const xs = points.map((point) => point.x);
  const zs = points.map((point) => point.z);
  const minX = xs.length ? Math.min(...xs) : -width / 2;
  const maxX = xs.length ? Math.max(...xs) : width / 2;
  const minZ = zs.length ? Math.min(...zs) : -depth / 2;
  const maxZ = zs.length ? Math.max(...zs) : depth / 2;
  const contentWidth = Math.max(maxX - minX, 1);
  const contentDepth = Math.max(maxZ - minZ, 1);
  const padding = 28;
  const scale = Math.min((canvas.width - padding * 2) / contentWidth, (canvas.height - padding * 2) / contentDepth);
  const drawnWidth = contentWidth * scale;
  const drawnDepth = contentDepth * scale;
  const originX = (canvas.width - drawnWidth) / 2;
  const originY = (canvas.height - drawnDepth) / 2;
  const point = (value, axis) => {
    const numeric = Number(value || 0);
    return axis === "x"
      ? originX + (numeric - minX) * scale
      : originY + (numeric - minZ) * scale;
  };
  const drawSegments = (items, color, lineWidth) => {
    context.strokeStyle = color;
    context.lineWidth = lineWidth;
    items.forEach((segment) => {
      const start = segment.start || {};
      const end = segment.end || {};
      context.beginPath();
      context.moveTo(point(start.x, "x"), point(start.z ?? start.y, "y"));
      context.lineTo(point(end.x, "x"), point(end.z ?? end.y, "y"));
      context.stroke();
    });
  };
  drawSegments(segments, "#775c46", 5);
  drawSegments(doorSegments, "#bf6c45", 8);
  drawSegments(windowSegments, "#4c8a9b", 7);
  /* Keep the old wall loop out of the drawing path; all three categories use
     the same coordinate transform above so their proportions stay aligned. */
  /* segments.forEach((segment) => {
    const start = segment.start || {};
    const end = segment.end || {};
    context.beginPath();
    context.moveTo(point(start.x, "x"), point(start.z ?? start.y, "y"));
    context.lineTo(point(end.x, "x"), point(end.z ?? end.y, "y"));
    context.stroke();
  }); */
  if (!segments.length) {
    context.strokeRect(originX, originY, drawnWidth, drawnDepth);
  }
  return canvas;
}

async function previewFloorplan() {
  const file = elements.floorplan.files?.[0];
  if (!file) return;
  elements.floorplanPreview.hidden = false;
  elements.continueToChat.disabled = true;
  elements.floorplanPreviewContent.replaceChildren();
  if (elements.floorplanFilename) elements.floorplanFilename.textContent = file.name;
  if (elements.pickFloorplan) elements.pickFloorplan.textContent = "再次上傳";
  elements.floorplanStatus.textContent = "正在讀取空間...";
    try {
    const extension = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (extension === ".dwg") {
      throw new Error("DWG_UNSUPPORTED");
    }
    if (extension === ".dxf") {
      uploadedDxfText = await file.text();
      const response = await fetch("/api/upload", {
        method: "POST",
        body: (() => { const data = new FormData(); data.append("file", file); return data; })(),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const plan = await response.json();
      elements.floorplanPreviewContent.appendChild(drawDxfPreview(plan));
      const widthCm = Number(plan.width_cm || ((Number(plan.bbox?.maxx) - Number(plan.bbox?.minx)) * 100) || 0);
      const depthCm = Number(plan.depth_cm || ((Number(plan.bbox?.maxz) - Number(plan.bbox?.minz)) * 100) || 0);
      const segmentCount = (plan.wall_segments || plan.plan_segments || []).length || (plan.wall_polys || []).length;
      const doorCount = (plan.door_segments || plan.doors || []).length;
      const windowCount = (plan.window_segments || plan.windows || []).length;
      elements.floorplanStatus.textContent = `${widthCm.toFixed(1)} × ${depthCm.toFixed(1)} cm｜牆 ${segmentCount} · 門 ${doorCount} · 窗 ${windowCount}`;
    } else {
      const image = document.createElement("img");
      image.src = URL.createObjectURL(file);
      image.alt = "已上傳的平面圖預覽";
      image.onload = () => URL.revokeObjectURL(image.src);
      elements.floorplanPreviewContent.appendChild(image);
      elements.floorplanStatus.textContent = "平面圖已載入";
    }
    elements.continueToChat.disabled = false;
    elements.sceneStatus.textContent = "空間預覽完成，接下來一起整理你的需求。";
  } catch (error) {
    console.error(error);
    elements.floorplanStatus.textContent = error.message === "DWG_UNSUPPORTED"
      ? "DWG 目前請先轉存為 DXF"
      : "讀取失敗，請重新選擇檔案";
  }
}

function acceptDroppedFloorplan(event) {
  event.preventDefault();
  const file = event.dataTransfer?.files?.[0];
  if (!file || !elements.floorplan) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  elements.floorplan.files = transfer.files;
  previewFloorplan();
}

function enterGuidedChat() {
  showWizardSection("chat");
  elements.chatInput?.focus();
  startGuidedIntake();
}

async function sendGuidedAnswer() {
  const answer = elements.chatInput?.value.trim();
  if (!answer || !intakeState.step) return;
  elements.chatInput.value = "";
  elements.chatSend.disabled = true;
  try {
    const response = await fetch("/api/agent/intake/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: intakeState.sessionId,
        step: intakeState.step,
        answer,
        client_brief: intakeState.clientBrief,
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    intakeState.clientBrief = result.client_brief;
    intakeState.step = result.step;
    elements.chatMessages.replaceChildren();
    appendChatMessage("ai", result.question || result.reply);
    renderClientBrief();
    if (result.ready_for_confirmation) {
      showWizardSection("brief");
      elements.chatConfirm.disabled = false;
      elements.sceneStatus.textContent = "需求已整理完成，請先確認 JSON。";
    }
  } catch (error) {
    console.error(error);
    appendChatMessage("ai", "這次回答沒有成功送出，請再試一次。");
  } finally {
    elements.chatSend.disabled = false;
  }
}

function confirmClientBrief() {
  if (!intakeState.clientBrief || intakeState.step) return;
  intakeState.clientBrief.confirmation = {
    status: "confirmed",
    confirmed_at: new Date().toISOString(),
  };
  intakeState.confirmed = true;
  syncClientBriefToLegacyFields();
  renderClientBrief();
  elements.generateScene.disabled = false;
  elements.generateScene.textContent = "生成 3D 場景";
  elements.sceneStatus.textContent = "需求 JSON 已確認，可以生成 3D 場景。";
}

async function generateScene(event) {
  event.preventDefault();
  if (!intakeState.confirmed || !intakeState.clientBrief) {
    elements.sceneStatus.textContent = "請先完成並確認需求 JSON。";
    return;
  }
  showWizardSection("final");
  setGeneratingState(true);
  try {
    const floorplanFile = elements.floorplan.files?.[0];
    uploadedDxfText = floorplanFile && floorplanFile.name.toLowerCase().endsWith(".dxf")
      ? await floorplanFile.text()
      : null;
    const sceneLook = getStyleSceneLook();
    const payload = {
      client_brief: intakeState.clientBrief,
      room_width_cm: Number(elements.roomWidth.value),
      room_depth_cm: Number(elements.roomDepth.value),
      space_type: elements.spaceType.value,
      style_preference: elements.stylePreference.value,
      style_card_id: requestedStyleCardId,
      required_furniture: Array.from(new Set([...selectedValues(elements.furnitureOptions), ...getProposalFurnitureTypes()])),
      selected_furniture: getLibraryProposalFurniture(),
      library_proposal: libraryProposal,
      custom_furniture: splitCustomText(elements.customFurniture.value),
      preferred_colors: selectedValues(elements.colorOptions),
      custom_colors: splitCustomText(elements.customColors.value),
      personal_notes: elements.personalNotes.value,
      keep_window_clear: elements.keepWindowClear.checked,
      keep_door_clear: elements.keepDoorClear.checked,
      need_storage: elements.needStorage.checked,
      prefer_low_saturation: elements.preferLowSaturation.checked,
      floorplan_filename: floorplanFile ? floorplanFile.name : null,
      floorplan_dxf_text: uploadedDxfText,
      floorplan_scale_m: floorplanScaleM,
      wall_option: getResolvedSurfaceChoice(elements.wallOptions, "wall-option", sceneLook.wall),
      floor_option: getResolvedSurfaceChoice(elements.floorOptions, "floor-option", sceneLook.floor),
      furniture_random_seed: furnitureRandomSeed,
    };
    const response = await fetch("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    currentSceneData = await response.json();
    const emptySceneReason = explainEmptyScene(currentSceneData);
    if (emptySceneReason) {
      elements.sceneStatus.textContent = emptySceneReason;
      await refreshCurrentScene(emptySceneReason);
      return;
    }
    await refreshCurrentScene("場景已生成，可在右側清單替換或移除家具。");
  } catch (error) {
    console.error(error);
    elements.sceneStatus.textContent = "場景生成失敗，請檢查條件或稍後再試。";
  } finally {
    setGeneratingState(false);
  }
}

async function replaceSceneItem(index) {
  if (!currentSceneData?.scene_objects?.[index]) return;
  const currentItem = currentSceneData.scene_objects[index];
  const usedIds = new Set(currentSceneData.scene_objects.map((item, itemIndex) => itemIndex === index ? null : item.furniture_id).filter(Boolean));
  const replacement = await pickFurnitureCandidate(currentItem.normalized_type, usedIds);
  if (!replacement) {
    elements.sceneStatus.textContent = `目前找不到可替換的 ${getTypeLabel(currentItem.normalized_type)}。`;
    return;
  }
  currentSceneData.scene_objects[index] = sceneObjectFromFurniture(replacement);
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已替換第 ${index + 1} 件家具。`);
}

async function removeSceneItem(index) {
  if (!currentSceneData?.scene_objects?.[index]) return;
  const removed = currentSceneData.scene_objects.splice(index, 1)[0];
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已移除 ${formatFurnitureName(removed)}。`);
}

async function addFurnitureToScene() {
  if (!currentSceneData) {
    elements.sceneStatus.textContent = "請先生成一個 3D 場景，再加入家具。";
    return;
  }
  const type = elements.addFurnitureType.value;
  const usedIds = new Set(currentSceneData.scene_objects.map((item) => item.furniture_id));
  const candidate = await pickFurnitureCandidate(type, usedIds);
  if (!candidate) {
    elements.sceneStatus.textContent = `資料庫裡找不到可加入的 ${getTypeLabel(type)}。`;
    return;
  }
  currentSceneData.scene_objects.push(sceneObjectFromFurniture(candidate));
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已加入 ${getTypeLabel(type)}。`);
}

async function reshuffleCurrentScene() {
  if (!currentSceneData?.scene_objects?.length) {
    randomizeFurnitureSelection();
    return;
  }
  const usedIds = new Set();
  const nextObjects = [];
  for (const item of currentSceneData.scene_objects) {
    const candidate = await pickFurnitureCandidate(item.normalized_type, usedIds);
    if (!candidate) {
      nextObjects.push(item);
      continue;
    }
    usedIds.add(candidate.furniture_id);
    nextObjects.push(sceneObjectFromFurniture(candidate));
  }
  currentSceneData.scene_objects = nextObjects;
  furnitureRandomSeed = Date.now();
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene("已依目前風格重抽整組家具。");
}

const originalSeedClientBriefFromCurrentForm = seedClientBriefFromCurrentForm;
const originalGenerateScene = generateScene;

seedClientBriefFromCurrentForm = function seedClientBriefFromCurrentFormFixed(brief = null) {
  const next = originalSeedClientBriefFromCurrentForm(brief);
  const selectedStyleId = elements.stylePreference?.value;
  if (selectedStyleId) {
    next.style = next.style || {};
    next.style.preferred = Array.from(new Set([...(next.style.preferred || []), selectedStyleId]));
  }
  return next;
};

renderSelectedStyleCard = function renderSelectedStyleCardFixed() {
  if (!elements.selectedStyleCard) return;
  const context = selectedStyleCardContext || findSelectedStyleCardContext();
  selectedStyleCardContext = context;
  if (context) {
    const palette = (context.card.palette_hex || [])
      .map((color) => `<span style="--swatch:${escapeForHtml(color)}"></span>`)
      .join("");
    elements.selectedStyleCard.hidden = false;
    elements.selectedStyleCard.innerHTML = `
      <div>
        <span>已選風格</span>
        <strong>${escapeForHtml(context.group.style_name_zh)}｜${escapeForHtml(context.card.name_zh)}</strong>
      </div>
      <div class="scene-selected-style-palette" aria-label="已選色票">${palette}</div>
    `;
    return;
  }
  const selectedStyleId = requestedStyleId || elements.stylePreference?.value;
  const style = (siteData.styles || []).find((item) => item.style_id === selectedStyleId);
  if (!style) {
    elements.selectedStyleCard.hidden = true;
    elements.selectedStyleCard.innerHTML = "";
    return;
  }
  elements.selectedStyleCard.hidden = false;
  elements.selectedStyleCard.innerHTML = `
    <div>
      <span>已選風格</span>
      <strong>${escapeForHtml(style.style_name_zh || selectedStyleId)}</strong>
    </div>
    <small>尚未指定生活色調，將依目前風格自動搭配牆面、地板與家具。</small>
  `;
};

applyStyleCardFromQuery = function applyStyleCardFromQueryFixed() {
  selectedStyleCardContext = findSelectedStyleCardContext();
  renderSelectedStyleCard();
  const requestedStyle = (siteData.styles || []).find((style) => style.style_id === requestedStyleId);
  if (requestedStyle) {
    elements.stylePreference.value = requestedStyle.style_id;
  }
  if (!selectedStyleCardContext) return;
  elements.customColors.value = (selectedStyleCardContext.card.palette_hex || []).join(", ");
  elements.sceneStatus.textContent = `已帶入「${selectedStyleCardContext.group.style_name_zh}｜${selectedStyleCardContext.card.name_zh}」色卡，生成時會同步套用。`;
};

renderClientBrief = function renderClientBriefFixed() {
  if (!elements.briefSummary || !intakeState.clientBrief) return;
  const brief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
  intakeState.clientBrief = brief;
  const spaceLabels = {
    living_room: "客廳",
    bedroom: "臥室",
    workspace: "書房 / 工作空間",
    dining_room: "餐廳",
    studio: "套房",
  };
  const styleLabels = {
    japanese: "日式 / 無印",
    scandinavian: "北歐",
    modern: "現代簡約",
    industrial: "工業風",
    american: "美式",
    light_luxury: "輕奢",
    warm_neutral: "溫暖中性色",
  };
  const needLabels = {
    storage: "收納",
    work: "工作",
    reading: "閱讀",
    display: "展示",
    entertaining: "接待 / 聚會",
    rest: "休息",
  };
  const materialLabels = { wood: "木質", stone: "石材", fabric: "布料", metal: "金屬", glass: "玻璃" };
  const labels = (values, dictionary) => (values || []).map((value) => dictionary[value] || value).filter(Boolean);
  const occupants = brief.occupants || {};
  const people = [
    occupants.adults ? `${occupants.adults} 位成人` : "",
    occupants.children ? `${occupants.children} 位小孩` : "",
    occupants.elderly ? `${occupants.elderly} 位長輩` : "",
    occupants.pets ? `${occupants.pets} 隻寵物` : "",
  ].filter(Boolean);
  const selectedCardLabel = brief.style?.selected_card_name_zh
    ? `${brief.style.selected_style_name_zh || "風格"}｜${brief.style.selected_card_name_zh}`
    : "尚未選擇";
  const cards = [
    ["空間", `${spaceLabels[brief.space?.type] || brief.space?.type || "未指定"}｜${brief.space?.width_cm || "?"} × ${brief.space?.depth_cm || "?"} cm`],
    ["使用者", people.join("、") || "尚未指定"],
    ["需求", labels(brief.needs, needLabels).join("、") || "尚未指定"],
    ["風格方向", labels(brief.style?.preferred, styleLabels).join("、") || "由系統推薦"],
    ["已選色調", selectedCardLabel],
    ["偏好材質", labels(brief.style?.materials, materialLabels).join("、") || "依風格搭配"],
    ["空間限制", labels(brief.constraints, {
      keep_window_clear: "保留窗邊採光",
      keep_door_clear: "保持出入口動線",
      keep_wide_walkway: "保留寬走道",
      keep_existing: "保留既有設備",
    }).join("、") || "無特別限制"],
  ];
  elements.briefSummary.innerHTML = cards.map(([label, value]) => `
    <div class="scene-brief-card"><span>${escapeForHtml(label)}</span><strong>${escapeForHtml(value)}</strong></div>
  `).join("");
  if (elements.chatConfirm) {
    const canConfirm = Boolean(intakeState.clientBrief && !intakeState.step);
    elements.chatConfirm.hidden = !canConfirm;
    elements.chatConfirm.disabled = !canConfirm;
  }
};

startGuidedIntake = async function startGuidedIntakeFixed() {
  if (!elements.chatMessages) return;
  const sessionId = `roompilot-${Date.now()}`;
  elements.chatMessages.replaceChildren();
  if (elements.chatHint) elements.chatHint.textContent = "";
  if (elements.chatConfirm) {
    elements.chatConfirm.hidden = true;
    elements.chatConfirm.disabled = true;
  }
  elements.generateScene.disabled = true;
  elements.generateScene.textContent = "確認需求，開始生成";
  renderSelectedStyleCard();
  try {
    const response = await fetch("/api/agent/intake/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    intakeState = {
      sessionId: result.session_id,
      step: result.step || "needs",
      clientBrief: seedClientBriefFromCurrentForm(result.client_brief),
      confirmed: false,
    };
    const selected = selectedStyleCardContext || findSelectedStyleCardContext();
    appendChatMessage("ai", selected
      ? `已套用「${selected.group.style_name_zh}｜${selected.card.name_zh}」。請補充：這個空間主要給誰使用、想放哪些家具、需要哪些生活功能？`
      : result.question);
    renderClientBrief();
  } catch (error) {
    console.error(error);
    intakeState = {
      sessionId,
      step: "needs",
      clientBrief: seedClientBriefFromCurrentForm(),
      confirmed: false,
    };
    const selected = selectedStyleCardContext || findSelectedStyleCardContext();
    appendChatMessage("ai", selected
      ? `已套用「${selected.group.style_name_zh}｜${selected.card.name_zh}」。目前訪談服務暫時無法連線，先用快速模式整理需求：請用一句話說明使用者、家具與生活功能。`
      : "目前訪談服務暫時無法連線，先用快速模式整理需求：請用一句話說明使用者、家具與生活功能。");
    elements.sceneStatus.textContent = "已改用本機快速需求整理模式，可以繼續下一步。";
    renderClientBrief();
  }
};

sendGuidedAnswer = async function sendGuidedAnswerFixed() {
  const answer = elements.chatInput?.value.trim();
  if (!answer) {
    if (elements.chatHint) elements.chatHint.textContent = "請先輸入一句需求，例如：兩位大人，需要收納，也希望保留窗邊動線。";
    elements.chatInput?.focus();
    return;
  }
  if (!intakeState.sessionId) intakeState.sessionId = `roompilot-${Date.now()}`;
  if (!intakeState.step) intakeState.step = "needs";
  elements.chatInput.value = "";
  elements.chatSend.disabled = true;
  if (elements.chatHint) elements.chatHint.textContent = "正在整理你的需求...";
  appendChatMessage("user", answer);
  try {
    const response = await fetch("/api/agent/intake/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: intakeState.sessionId,
        step: intakeState.step,
        answer,
        client_brief: seedClientBriefFromCurrentForm(intakeState.clientBrief),
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    intakeState.clientBrief = seedClientBriefFromCurrentForm(result.client_brief || intakeState.clientBrief);
    intakeState.step = result.ready_for_confirmation ? null : result.step;
    renderClientBrief();
    if (result.ready_for_confirmation) {
      showWizardSection("brief");
      elements.generateScene.disabled = false;
      elements.sceneStatus.textContent = "需求已整理完成，確認後即可生成 3D 場景。";
    } else {
      appendChatMessage("ai", result.question || result.reply || "我已記下，請再補充一點你希望的使用方式。");
    }
    if (elements.chatHint) elements.chatHint.textContent = "";
  } catch (error) {
    console.error(error);
    intakeState.clientBrief = mergeUserAnswerIntoBrief(answer);
    intakeState.step = null;
    intakeState.confirmed = false;
    renderClientBrief();
    showWizardSection("brief");
    elements.generateScene.disabled = false;
    elements.sceneStatus.textContent = "已用本機快速模式整理需求，確認後即可生成 3D 場景。";
    if (elements.chatHint) elements.chatHint.textContent = "";
  } finally {
    elements.chatSend.disabled = false;
  }
};

confirmClientBrief = function confirmClientBriefFixed() {
  if (!intakeState.clientBrief || intakeState.step) return;
  intakeState.clientBrief = seedClientBriefFromCurrentForm(intakeState.clientBrief);
  intakeState.clientBrief.confirmation = {
    status: "confirmed",
    confirmed_at: new Date().toISOString(),
  };
  intakeState.confirmed = true;
  syncClientBriefToLegacyFields();
  renderClientBrief();
  if (elements.chatConfirm) {
    elements.chatConfirm.hidden = true;
    elements.chatConfirm.disabled = true;
  }
  elements.generateScene.disabled = false;
  elements.generateScene.textContent = "生成 3D 場景";
  elements.sceneStatus.textContent = "需求已確認，可以生成 3D 場景。";
};

generateScene = async function generateSceneFixed(event) {
  const validation = validateScenePrerequisites();
  if (!validation.ok) {
    event?.preventDefault?.();
    showWizardSection("chat");
    if (elements.chatHint) elements.chatHint.textContent = validation.message;
    elements.sceneStatus.textContent = validation.message;
    return;
  }
  if (!intakeState.clientBrief) {
    intakeState.clientBrief = seedClientBriefFromCurrentForm();
    intakeState.step = null;
  }
  if (!intakeState.confirmed && intakeState.clientBrief && !intakeState.step) {
    confirmClientBrief();
  }
  return originalGenerateScene(event);
};

renderStyleOptions();
applyStyleCardFromQuery();
renderToggleOptions(elements.furnitureOptions, furnitureOptions, "furniture");
renderToggleOptions(elements.colorOptions, buildColorOptions(), "color");
renderAddFurnitureSelect();
syncSurfaceChoicesToStyle();
setDefaultFurnitureBySpace();
renderInitialProviderStatus();
configureSceneIntakeControls();

elements.sceneForm.addEventListener("submit", generateScene);
elements.startFlow?.addEventListener("click", () => {
  showWizardSection("floorplan");
  elements.floorplan?.focus();
});
elements.floorplan?.addEventListener("change", previewFloorplan);
elements.pickFloorplan?.addEventListener("click", (event) => {
  event.preventDefault();
  elements.floorplan?.click();
});
elements.floorplan?.closest(".scene-upload-zone")?.addEventListener("dragover", (event) => {
  event.preventDefault();
  event.currentTarget.classList.add("is-dragging");
});
elements.floorplan?.closest(".scene-upload-zone")?.addEventListener("dragleave", (event) => {
  event.currentTarget.classList.remove("is-dragging");
});
elements.floorplan?.closest(".scene-upload-zone")?.addEventListener("drop", (event) => {
  event.currentTarget.classList.remove("is-dragging");
  acceptDroppedFloorplan(event);
});
elements.continueToChat?.addEventListener("click", enterGuidedChat);
elements.proposalList?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-proposal-remove]");
  if (!button) return;
  removeLibraryProposalItem(button.dataset.proposalRemove);
});
elements.filterProposal?.addEventListener("click", filterProposalForRoom);
elements.chatSend?.addEventListener("click", sendGuidedAnswer);
elements.chatConfirm?.addEventListener("click", confirmClientBrief);
elements.chatBack?.addEventListener("click", () => {
  elements.sceneStatus.textContent = "目前需求 JSON 已保留；若要修改，請直接在聊天框補充或重新整理開始新的訪談。";
});
elements.chatBack?.addEventListener("click", () => {
  showWizardSection("floorplan");
  if (elements.chatHint) elements.chatHint.textContent = "";
  elements.sceneStatus.textContent = "已回到平面圖步驟；已選風格與目前需求會先保留。";
});
elements.randomFurniture.addEventListener("click", randomizeFurnitureSelection);
elements.addFurniture.addEventListener("click", addFurnitureToScene);
elements.reshuffleScene.addEventListener("click", reshuffleCurrentScene);
elements.sceneSelectedItems.addEventListener("click", (event) => {
  const button = event.target.closest("[data-furniture-action]");
  if (!button) return;
  const index = Number(button.dataset.index);
  if (!Number.isInteger(index)) return;
  if (button.dataset.furnitureAction === "replace") replaceSceneItem(index);
  if (button.dataset.furnitureAction === "remove") removeSceneItem(index);
});
elements.stylePreference.addEventListener("change", async () => {
  surfaceSearchQueries.floor = "";
  surfaceStyleOnly.floor = false;
  surfaceVisibleLimits.floor = 12;
  syncSurfaceChoicesToStyle();
  furnitureRandomSeed = Date.now();
  elements.sceneStatus.textContent = `已切換為 ${elements.stylePreference.selectedOptions[0]?.textContent || "目前風格"}，牆面與地板材質也已同步更新。`;
  await applySurfaceChoiceToCurrentScene();
});
elements.wallOptions.addEventListener("click", handleSurfaceFilterClick);
elements.floorOptions.addEventListener("click", handleSurfaceFilterClick);
elements.wallOptions.addEventListener("pointerdown", handleSurfaceFilterClick);
elements.floorOptions.addEventListener("pointerdown", handleSurfaceFilterClick);
elements.floorOptions.addEventListener("input", handleSurfaceSearchInput);
elements.wallOptions.addEventListener("change", applySurfaceChoiceToCurrentScene);
elements.floorOptions.addEventListener("change", applySurfaceChoiceToCurrentScene);
elements.spaceType.addEventListener("change", setDefaultFurnitureBySpace);
elements.resetSceneView.addEventListener("click", () => viewer.resetCamera());
elements.rotateFurnitureLeft?.addEventListener("click", () => viewer.rotateSelected(-90));
elements.rotateFurnitureRight?.addEventListener("click", () => viewer.rotateSelected(90));
elements.toggleCeiling?.addEventListener("click", () => {
  const visible = viewer.toggleCeiling();
  elements.toggleCeiling.textContent = visible ? "隱藏天花板" : "顯示天花板";
});
elements.toggleWalkMode?.addEventListener("click", () => {
  viewer.setCameraPreset("inside");
  elements.toggleWalkMode.textContent = "已進入室內觀看";
  elements.sceneStatus.textContent = "目前為室內觀看視角；可用滑鼠檢視空間，室內行走控制列入下一階段。";
});
elements.viewPresetButtons.forEach((button) => {
  button.addEventListener("click", () => viewer.setCameraPreset(button.dataset.viewPreset));
});

initBackgroundFx();
startSceneFromEntryState();

// ── F2a 手動拉比例(兩點標定,main 主線功能移植)──
function drawCalibrationPreview() {
  const canvas = elements.calibrationCanvas;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!calibrationParsed) return;

  const bbox = calibrationParsed.bbox;
  const pad = 30;
  const spanX = Math.max(bbox.maxx - bbox.minx, 0.01);
  const spanZ = Math.max(bbox.maxz - bbox.minz, 0.01);
  const scale = Math.min((canvas.width - pad * 2) / spanX, (canvas.height - pad * 2) / spanZ);
  const originX = (canvas.width - spanX * scale) / 2;
  const originY = (canvas.height - spanZ * scale) / 2;
  calibrationTransform = {
    toCanvas(x, z) {
      return [originX + (x - bbox.minx) * scale, originY + (bbox.maxz - z) * scale];
    },
    toWorld(canvasX, canvasY) {
      return {
        x: bbox.minx + (canvasX - originX) / scale,
        z: bbox.maxz - (canvasY - originY) / scale,
      };
    },
  };

  // 牆體(多邊形外環+洞)
  context.strokeStyle = "#6b513b";
  context.lineWidth = 1.6;
  (calibrationParsed.wall_polys || []).forEach((poly) => {
    [poly.exterior, ...(poly.holes || [])].filter(Boolean).forEach((ring) => {
      if (ring.length < 2) return;
      context.beginPath();
      ring.forEach(([x, z], index) => {
        const [cx, cy] = calibrationTransform.toCanvas(x, z);
        if (index === 0) context.moveTo(cx, cy);
        else context.lineTo(cx, cy);
      });
      context.closePath();
      context.stroke();
    });
  });

  const drawSegments = (segments, color) => {
    context.strokeStyle = color;
    context.lineWidth = 2.4;
    (segments || []).forEach((segment) => {
      context.beginPath();
      context.moveTo(...calibrationTransform.toCanvas(segment.x1, segment.z1));
      context.lineTo(...calibrationTransform.toCanvas(segment.x2, segment.z2));
      context.stroke();
    });
  };
  drawSegments(calibrationParsed.doors, "#b9773f");
  drawSegments(calibrationParsed.windows, "#5b8aa6");

  // 標定點與連線
  calibrationPoints.forEach((point, index) => {
    const [cx, cy] = calibrationTransform.toCanvas(point.x, point.z);
    context.beginPath();
    context.arc(cx, cy, 6, 0, Math.PI * 2);
    context.fillStyle = "#b9773f";
    context.fill();
    context.strokeStyle = "#fff";
    context.lineWidth = 2;
    context.stroke();
    context.fillStyle = "#3a2c22";
    context.font = "bold 12px 'Noto Sans TC', sans-serif";
    context.fillText(String(index + 1), cx + 9, cy - 8);
  });
  if (calibrationPoints.length === 2) {
    const [a, b] = calibrationPoints;
    context.beginPath();
    context.moveTo(...calibrationTransform.toCanvas(a.x, a.z));
    context.lineTo(...calibrationTransform.toCanvas(b.x, b.z));
    context.strokeStyle = "#b9773f";
    context.lineWidth = 2;
    context.setLineDash([6, 4]);
    context.stroke();
    context.setLineDash([]);
  }
}

function calibrationMeasuredMeters() {
  if (calibrationPoints.length !== 2) return null;
  const [a, b] = calibrationPoints;
  return Math.hypot(a.x - b.x, a.z - b.z);
}

function updateCalibrationStatus() {
  const stats = calibrationParsed?.stats;
  const measured = calibrationMeasuredMeters();
  const dims = stats ? `目前解析寬 ${stats.width_m} m × 深 ${stats.depth_m} m(${calibrationParsed.scale_basis === "manual" ? "已手動校正" : "自動推測"})。` : "";
  if (measured) {
    elements.calibrationStatus.textContent =
      `${dims} 兩點在目前比例下距離 ${(measured * 100).toFixed(1)} 公分 — 輸入實際公分後按「套用比例」。`;
  } else {
    elements.calibrationStatus.textContent =
      `${dims} 請在圖上點兩個點(已點 ${calibrationPoints.length}/2)。`;
  }
}

async function parseFloorplanPreview(file, scaleM = null) {
  const formData = new FormData();
  formData.append("file", file);
  const query = scaleM ? `?scale_m=${encodeURIComponent(scaleM)}` : "";
  const response = await fetch(`/api/upload${query}`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function onFloorplanFileChanged() {
  const file = elements.floorplan.files?.[0];
  calibrationPoints = [];
  floorplanScaleM = null;
  calibrationParsed = null;

  if (!file || !file.name.toLowerCase().endsWith(".dxf")) {
    elements.scaleCalibration.hidden = true;
    return;
  }

  try {
    uploadedDxfText = await file.text();
    calibrationParsed = await parseFloorplanPreview(file);
    elements.scaleCalibration.hidden = false;
    drawCalibrationPreview();
    updateCalibrationStatus();
  } catch (error) {
    console.error(error);
    elements.scaleCalibration.hidden = true;
    elements.sceneStatus.textContent = "DXF 預覽解析失敗,仍可直接生成(比例採自動推測)。";
  }
}

async function applyCalibrationScale() {
  const measured = calibrationMeasuredMeters();
  const realCm = Number(elements.calibrationLength.value);
  if (!calibrationParsed || !measured) {
    elements.calibrationStatus.textContent = "請先在圖上點兩個點。";
    return;
  }
  if (!Number.isFinite(realCm) || realCm < 10) {
    elements.calibrationStatus.textContent = "請輸入合理的實際距離(至少 10 公分)。";
    return;
  }

  // 距離校正因子 → 換算全圖長邊跨距,交給解析器的 scale_m 覆寫
  const factor = realCm / 100 / measured;
  floorplanScaleM = Math.round(calibrationParsed.scale_m * factor * 1000) / 1000;

  try {
    const file = elements.floorplan.files?.[0];
    calibrationParsed = await parseFloorplanPreview(file, floorplanScaleM);
    calibrationPoints = calibrationPoints.map((point) => ({ x: point.x * factor, z: point.z * factor }));
    drawCalibrationPreview();
    const stats = calibrationParsed.stats;
    elements.calibrationStatus.textContent =
      `✅ 已套用比例:全圖跨距 ${floorplanScaleM} m,寬 ${stats.width_m} m × 深 ${stats.depth_m} m。生成 3D 場景會用這個尺寸。`;
  } catch (error) {
    console.error(error);
    elements.calibrationStatus.textContent = "套用比例後重新解析失敗,請重試。";
  }
}

function resetCalibrationState() {
  calibrationPoints = [];
  floorplanScaleM = null;
  elements.calibrationLength.value = "";
  onFloorplanFileChanged();
}

elements.floorplan.addEventListener("change", onFloorplanFileChanged);
elements.applyCalibration.addEventListener("click", applyCalibrationScale);
elements.resetCalibration.addEventListener("click", resetCalibrationState);
elements.calibrationCanvas.addEventListener("click", (event) => {
  if (!calibrationTransform) return;
  const rect = elements.calibrationCanvas.getBoundingClientRect();
  const canvasX = ((event.clientX - rect.left) / rect.width) * elements.calibrationCanvas.width;
  const canvasY = ((event.clientY - rect.top) / rect.height) * elements.calibrationCanvas.height;
  if (calibrationPoints.length >= 2) calibrationPoints = [];
  calibrationPoints.push(calibrationTransform.toWorld(canvasX, canvasY));
  drawCalibrationPreview();
  updateCalibrationStatus();
});

// ── 720° 環景漫遊(main 主線功能移植)──
elements.openPanorama.addEventListener("click", () => {
  // 交棒目前場景給環景頁;沒生成過就讓環景頁自己做示範場景
  if (currentSceneData) {
    sessionStorage.setItem("roompilot.panorama.scene", JSON.stringify(currentSceneData));
  } else {
    sessionStorage.removeItem("roompilot.panorama.scene");
  }
  window.open("/panorama", "_blank");
});
