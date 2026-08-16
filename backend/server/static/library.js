import {
  fetchFurniturePage,
  formatSize,
  initBackgroundFx,
  scrollPageTop,
  shouldUseDarkFurnitureStage,
  styleNameMap,
} from "./common.js?v=sha256-7df895e56814";
import { createViewer } from "./viewer.js?v=sha256-0dd71c0a4943";
import { attachLibraryThumbnail } from "./library_thumbnails.js?v=sha256-73844ca91311";

const LIBRARY_PROPOSAL_STORAGE_KEY = "roompilot-mode1-proposal-v1";
const LIBRARY_FAVORITES_STORAGE_KEY = "roompilot-mode1-favorites-v1";
const ROOMPILOT_PROPOSAL_STORAGE_KEY = "roompilot:sceneProposal";

const MODE_ONE_SPACES = [
  ["living", "客廳", "沙發、茶几、電視櫃與地毯"],
  ["dining_kitchen", "餐廚", "餐桌椅、收納櫃與小型廚房電器"],
  ["bedroom", "臥室", "床、床頭櫃、衣櫃與燈具"],
  ["study", "書房", "書桌、辦公椅、書櫃與工作燈"],
  ["storage", "收納空間", "櫃體、層架、收納盒與系統家具"],
  ["soft_decor", "軟裝佈置", "燈具、地毯、抱枕與裝飾品"],
  ["kids", "兒童空間", "兒童椅、玩具收納、兒童桌與地毯"],
  ["outdoor", "戶外", "戶外桌椅、戶外地毯與休閒家具"],
];

const COLOR_LABELS = {
  white: "白色",
  black: "黑色",
  grey: "灰色",
  gray: "灰色",
  beige: "米色",
  brown: "棕色",
  green: "綠色",
  blue: "藍色",
  red: "紅色",
  silver: "銀色",
  gold: "金色",
  yellow: "黃色",
  wood: "木色",
  walnut: "胡桃木色",
  navy: "海軍藍",
};

const MATERIAL_LABELS = {
  wood: "木材",
  oak: "橡木",
  metal: "金屬",
  fabric: "布料",
  textile: "織物",
  leather: "皮革",
  glass: "玻璃",
  steel: "鋼材",
  birch: "樺木",
  walnut: "胡桃木",
  "wood veneer": "木皮",
  "solid wood": "實木",
  plywood: "夾板",
  plastic: "塑膠",
};

const TYPE_ICON_PATHS = {
  all: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  sofa: '<path d="M5 11V8.5A2.5 2.5 0 0 1 7.5 6h9A2.5 2.5 0 0 1 19 8.5V11"/><path d="M4 10a2 2 0 0 0-2 2v5h20v-5a2 2 0 0 0-2-2h-1v4H5v-4H4Z"/><path d="M5 17v2m14-2v2"/>',
  table: '<ellipse cx="12" cy="8" rx="8" ry="3.5"/><path d="M7 10.5 5 20m12-9.5 2 9.5M12 11.5V20"/>',
  dining: '<path d="M8 9h8m-7 0-1 10m7-10 1 10M5 13v6m-2-6h4m10 0h4m-2 0v6"/>',
  storage: '<rect x="6" y="3" width="12" height="18" rx="1.5"/><path d="M6 12h12M11 7h2m-2 10h2"/>',
  lamp: '<path d="M9 4h6l3 7H6l3-7Zm3 7v7m-4 2h8"/>',
  rug: '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M7 8c2 0 2 3 4 3s2-3 4-3 2 3 2 3M7 15c2 0 2-2 4-2s2 2 4 2 2-2 2-2"/>',
  decor: '<path d="M8 20h8M9 20l1-9h4l1 9M8 7c0-2 1.8-4 4-4s4 2 4 4c0 1.8-1.3 3.2-4 4-2.7-.8-4-2.2-4-4Z"/>',
  bed: '<path d="M3 18V8m18 10v-7a3 3 0 0 0-3-3h-7v7"/><path d="M3 15h18M6 8h5v7H6a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3Z"/>',
  mattress: '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M3 12h18M7 9h.01m5 0h.01m5 0h.01"/>',
  wardrobe: '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M12 3v18M9 12h.01m6 0h.01"/>',
  desk: '<path d="M4 8h16v5H4zM7 13v8m10-8v8M9 17h6"/>',
  chair: '<path d="M7 4v9h10V7m-10 6v8m10-8v8M7 17h10"/>',
  shelf: '<path d="M5 4h14v16H5zM5 9h14M5 15h14"/>',
  kids: '<circle cx="12" cy="7" r="3"/><path d="M7 21v-4a5 5 0 0 1 10 0v4M9 12l-3 3m9-3 3 3"/>',
  outdoor: '<path d="M3 13h18M6 13l-2 8m14-8 2 8M8 13l1-6h6l1 6M12 7V3"/>',
  appliance: '<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M6 9h12M10 6h.01m4 0h.01"/>',
  mirror: '<ellipse cx="12" cy="10" rx="6" ry="8"/><path d="M12 18v3m-4 0h8"/>',
  fallback: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9z"/>',
};

const TYPE_LABELS = {
  "all": "全部",
  sofa: "沙發",
  "fabric-sofa": "布沙發",
  "leather-sofa": "皮沙發",
  "modular-sofa": "模組沙發",
  "sofa-bed": "沙發床",
  armchair: "扶手椅",
  "office-chair": "辦公椅",
  "dining-chair": "餐椅",
  "stool-bench": "凳子 / 長凳",
  "coffee-table": "茶几",
  "side-table": "邊桌",
  table: "桌子",
  desk: "書桌",
  "dining-table": "餐桌",
  bed: "床",
  "bed-frame": "床架",
  wardrobe: "衣櫃",
  "pax-wardrobe": "衣櫃系統",
  bookcase: "書櫃",
  "cabinet-cupboard": "櫃子 / 收納",
  "cabinets-cupboard": "櫃子 / 收納",
  "tv-bench": "電視櫃",
  "tv-media-furniture": "電視與影音家具",
  "shelving-unit": "層架",
  lamp: "燈具",
  "floor-lamp": "落地燈",
  "table-lamp": "檯燈",
  rug: "地毯",
  "large-medium-rug": "中大型地毯",
  "runner-small-rug": "走道地毯",
  decoration: "裝飾品",
  "wall-art": "牆面裝飾",
  planter: "盆栽植器",
  "flower-pots-planter": "花器",
  mirror: "鏡子",
  "large-mirror": "大型鏡子",
  "wall-mirror": "壁鏡",
  "small-kitchen-appliance": "小型廚房電器",
  "fridge-freezer": "冰箱 / 冷凍櫃",
  "childrens-furniture": "兒童家具",
};

const STYLE_LABELS = {
  scandinavian: "北歐風",
  japanese: "日式侘寂風",
  modern_minimal: "現代簡約風",
  cream: "奶油風",
  industrial: "工業風",
  american: "美式風",
};

const state = {
  activeFurnitureId: null,
  activeFurniture: null,
  currentPage: 1,
  itemsPerPage: 24,
  totalItems: 0,
  spinEnabled: false,
  proposalItems: new Map(),
  favoriteItems: new Set(),
  filteredFurniture: [],
};

const data = { styles: [], categoryGroups: [], typeOptions: [], allTypeOptions: [] };
let styleNames = styleNameMap(data.styles);
let currentRequestId = 0;
let filterTimer = null;

const elements = {
  searchInput: document.getElementById("search-input"),
  styleFilter: document.getElementById("style-filter"),
  sizeFilter: document.getElementById("size-filter"),
  colorFilter: document.getElementById("color-filter"),
  materialFilter: document.getElementById("material-filter"),
  groupFilter: document.getElementById("group-filter"),
  spaceSelect: document.getElementById("mode1-space-select"),
  typeFilter: document.getElementById("type-filter"),
  advancedFilters: document.getElementById("advanced-filters"),
  toggleAdvancedFilters: document.getElementById("toggle-advanced-filters"),
  spaceGrid: document.getElementById("mode1-space-grid"),
  typeStep: document.getElementById("mode1-type-step"),
  typeGrid: document.getElementById("mode1-type-grid"),
  typeNext: document.getElementById("mode1-type-next"),
  selectionList: document.getElementById("mode1-selection-list"),
  selectionTray: document.getElementById("mode1-selection-tray"),
  selectionCount: document.getElementById("mode1-selection-count"),
  selectionEmpty: document.getElementById("mode1-selection-empty"),
  clearProposal: document.getElementById("clear-proposal"),
  enterSceneWithProposal: document.getElementById("enter-scene-with-proposal"),
  libraryGrid: document.getElementById("library-grid"),
  libraryPagination: document.getElementById("library-pagination"),
  libraryCount: document.getElementById("library-count"),
  missingSummary: document.getElementById("missing-summary"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerStyle: document.getElementById("viewer-style"),
  viewerType: document.getElementById("viewer-type"),
  viewerSize: document.getElementById("viewer-size"),
  viewerMaterial: document.getElementById("viewer-material"),
  viewerColor: document.getElementById("viewer-color"),
  viewerStatus: document.getElementById("viewer-status"),
  viewerCanvas: document.getElementById("viewer-canvas"),
  addActiveToProposal: document.getElementById("add-active-to-proposal"),
  addActiveAndEnterScene: document.getElementById("add-active-and-enter-scene"),
  resetViewer: document.getElementById("reset-viewer"),
  spinModel: document.getElementById("spin-model"),
};

const viewer = createViewer(elements.viewerCanvas, elements.viewerStatus);
const libraryTopAnchor = document.querySelector(".page-shell.two-column-shell > section.page-panel");

function isReadableZh(value) {
  const text = String(value || "");
  return /[\u4e00-\u9fff]/.test(text) && !/[�]/.test(text);
}

function safeText(value, fallback = "尚未整理") {
  const text = String(value || "").trim();
  if (!text || /[�]/.test(text)) return fallback;
  return text;
}

function formatTypeName(type) {
  return TYPE_LABELS[type] || safeText(type, "家具");
}

function formatStyleName(styleId) {
  return STYLE_LABELS[styleId] || styleNames.get(styleId) || safeText(styleId, "尚未標註");
}

function translateFacetValue(value, translations, fallback) {
  const text = safeText(value, fallback);
  return text
    .split(/[,/、]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => translations[part.toLowerCase()] || part)
    .join("、");
}

function formatColorValue(value) {
  return translateFacetValue(value, COLOR_LABELS, "顏色未整理");
}

function formatMaterialValue(value) {
  return translateFacetValue(value, MATERIAL_LABELS, "材質未整理");
}

function formatFurnitureName(item) {
  if (isReadableZh(item?.name_zh)) return item.name_zh;
  if (isReadableZh(item?.name_zh_raw)) return item.name_zh_raw;
  return safeText(item?.name_en || item?.title, formatTypeName(item?.normalized_type));
}

function getCurrentGroup() {
  return elements.groupFilter.value || elements.spaceSelect?.value || "";
}

function getGroup(groupId) {
  return data.categoryGroups.find((group) => group.group_id === groupId);
}

function normalizeProposalItem(item) {
  return {
    furniture_id: item.furniture_id,
    name_zh: formatFurnitureName(item),
    name_en: item.name_en || "",
    normalized_type: item.normalized_type,
    type_label: formatTypeName(item.normalized_type),
    primary_style: item.primary_style,
    style_label: formatStyleName(item.primary_style),
    color: formatColorValue(item.color),
    material: formatMaterialValue(item.material),
    size_cm: item.size_cm || {},
    model_url: item.model_url,
    has_model: Boolean(item.has_model),
  };
}

function saveProposal() {
  try {
    localStorage.setItem(LIBRARY_PROPOSAL_STORAGE_KEY, JSON.stringify([...state.proposalItems.values()]));
  } catch (error) {
    console.warn("無法儲存本次方案清單", error);
  }
}

function restoreProposal() {
  try {
    const saved = JSON.parse(localStorage.getItem(LIBRARY_PROPOSAL_STORAGE_KEY) || "[]");
    if (!Array.isArray(saved)) return;
    saved
      .filter((item) => item?.furniture_id)
      .forEach((item) => state.proposalItems.set(item.furniture_id, item));
  } catch (error) {
    console.warn("無法讀取本次方案清單", error);
  }
}

function saveFavorites() {
  try {
    localStorage.setItem(LIBRARY_FAVORITES_STORAGE_KEY, JSON.stringify([...state.favoriteItems]));
  } catch (error) {
    console.warn("無法儲存收藏家具", error);
  }
}

function restoreFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem(LIBRARY_FAVORITES_STORAGE_KEY) || "[]");
    if (Array.isArray(saved)) state.favoriteItems = new Set(saved.filter(Boolean));
  } catch (error) {
    console.warn("無法讀取收藏家具", error);
  }
}

function renderProposal() {
  const items = [...state.proposalItems.values()];
  elements.selectionCount.textContent = String(items.length);
  elements.selectionEmpty.hidden = items.length > 0;
  elements.clearProposal.disabled = items.length === 0;
  elements.enterSceneWithProposal.disabled = items.length === 0;
  elements.selectionTray.classList.toggle("has-items", items.length > 0);
  elements.selectionList.innerHTML = "";

  items.forEach((item) => {
    const row = document.createElement("li");
    row.innerHTML = `
      <span>
        <strong>${formatFurnitureName(item)}</strong>
        <small>${formatTypeName(item.normalized_type)} / ${formatSize(item.size_cm, item)}</small>
      </span>
    `;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "text-button";
    remove.textContent = "移除";
    remove.addEventListener("click", () => {
      state.proposalItems.delete(item.furniture_id);
      saveProposal();
      renderProposal();
      renderLibrary();
      syncActiveButtons();
    });
    row.appendChild(remove);
    elements.selectionList.appendChild(row);
  });
}

function syncActiveButtons() {
  const active = state.activeFurniture;
  const alreadyAdded = active ? state.proposalItems.has(active.furniture_id) : false;
  elements.addActiveToProposal.disabled = !active || alreadyAdded;
  elements.addActiveAndEnterScene.disabled = !active;
  elements.addActiveToProposal.textContent = alreadyAdded ? "已加入本次方案" : "加入本次方案清單 ＋";
}

function addToProposal(item) {
  const normalized = normalizeProposalItem(item);
  state.proposalItems.set(normalized.furniture_id, normalized);
  saveProposal();
  renderProposal();
  renderLibrary();
  syncActiveButtons();
}

function buildSceneHandoffPayload() {
  const group = getGroup(getCurrentGroup());
  return {
    source: "library",
    created_at: new Date().toISOString(),
    selected_space_group: getCurrentGroup() || null,
    selected_space_name_zh: group?.group_name_zh || null,
    furniture: [...state.proposalItems.values()],
  };
}

function enterSceneWithProposal() {
  if (!state.proposalItems.size) {
    elements.viewerStatus.textContent = "請先加入至少一件家具，再進入 3D 場景。";
    return;
  }
  sessionStorage.setItem(ROOMPILOT_PROPOSAL_STORAGE_KEY, JSON.stringify(buildSceneHandoffPayload()));
  window.location.href = "/scene?source=library";
}

function renderSpaceChoices() {
  if (elements.spaceGrid) elements.spaceGrid.innerHTML = "";
  const previous = getCurrentGroup() || "living";
  elements.spaceSelect.innerHTML = "";
  MODE_ONE_SPACES.forEach(([groupId, fallbackName]) => {
    const group = getGroup(groupId);
    if (!group || !group.types?.length) return;
    const option = document.createElement("option");
    option.value = groupId;
    option.textContent = safeText(group.group_name_zh, fallbackName);
    elements.spaceSelect.appendChild(option);
  });
  const fallbackGroup = getGroup("living") ? "living" : data.categoryGroups[0]?.group_id || "";
  const nextGroup = getGroup(previous) ? previous : fallbackGroup;
  elements.groupFilter.value = nextGroup;
  elements.spaceSelect.value = nextGroup;
}

function getPreferredTypesForGroup(group) {
  const availableTypes = new Map(data.allTypeOptions.map((item) => [item.type, item]));
  const seen = new Set();
  return (group?.types || []).flatMap((groupType) => {
    const type = groupType?.type;
    if (!type || seen.has(type) || !availableTypes.has(type)) return [];
    seen.add(type);
    return [{
      ...availableTypes.get(type),
      ...groupType,
      displayLabel: safeText(groupType.type_name_zh, formatTypeName(type)),
    }];
  });
}

function typeIconKey(type) {
  if (!type) return "all";
  if (/sofa/.test(type)) return "sofa";
  if (/mattress/.test(type)) return "mattress";
  if (/bed/.test(type)) return "bed";
  if (/wardrobe|clothes-rack/.test(type)) return "wardrobe";
  if (/desk/.test(type)) return "desk";
  if (/chair|stool|bench/.test(type)) return "chair";
  if (/coffee-table|side-table/.test(type)) return "table";
  if (/dining|table$/.test(type)) return "dining";
  if (/shelf|bookcase/.test(type)) return "shelf";
  if (/cabinet|cupboard|drawer|storage|tv-bench|sideboard/.test(type)) return "storage";
  if (/lamp/.test(type)) return "lamp";
  if (/rug|mat/.test(type)) return "rug";
  if (/mirror/.test(type)) return "mirror";
  if (/child|kids/.test(type)) return "kids";
  if (/outdoor|sun-lounger|hammock/.test(type)) return "outdoor";
  if (/appliance|fridge|oven|hood/.test(type)) return "appliance";
  if (/decor|wall-art|planter|flower/.test(type)) return "decor";
  return "fallback";
}

function makeTypeChoiceButton({ type, label, count }) {
  const selectedType = elements.typeFilter.value;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "mode1-type-choice";
  button.classList.toggle("is-active", selectedType === type);
  button.innerHTML = `
    <span class="mode1-type-icon" aria-hidden="true"><svg viewBox="0 0 24 24">${TYPE_ICON_PATHS[typeIconKey(type)]}</svg></span>
    <strong>${label}</strong>
    ${count ? `<small>${count} 件</small>` : ""}
  `;
  button.addEventListener("click", () => {
    elements.typeFilter.value = type;
    state.currentPage = 1;
    loadLibraryPage();
  });
  return button;
}

function renderTypeChoices() {
  const group = getGroup(getCurrentGroup());
  elements.typeGrid.innerHTML = "";
  elements.typeStep.hidden = !group;
  if (!group) return;

  elements.typeGrid.appendChild(makeTypeChoiceButton({ type: "", label: "全部" }));
  getPreferredTypesForGroup(group).forEach((item) => {
    elements.typeGrid.appendChild(
      makeTypeChoiceButton({
        type: item.type,
        label: item.displayLabel || formatTypeName(item.type),
      }),
    );
  });
}

function selectSpace(groupId) {
  elements.groupFilter.value = groupId;
  elements.spaceSelect.value = groupId;
  elements.typeFilter.value = "";
  state.currentPage = 1;
  renderSpaceChoices();
  renderTypeChoices();
  loadLibraryPage();
}

function populateFilters() {
  elements.styleFilter.innerHTML = '<option value="">全部風格</option>';
  data.styles.forEach((style) => {
    const option = document.createElement("option");
    option.value = style.style_id;
    option.textContent = formatStyleName(style.style_id);
    elements.styleFilter.appendChild(option);
  });
  refreshCategoryOptions();
  refreshTypeOptions();
}

function populateFacetSelect(select, options, emptyLabel, labelMap = {}) {
  const previous = select.value;
  select.innerHTML = `<option value="">${emptyLabel}</option>`;
  const usedLabels = new Set();
  (options || []).forEach((item) => {
    const label = labelMap[String(item.label || "").trim().toLowerCase()] || item.label;
    if (usedLabels.has(label)) return;
    usedLabels.add(label);
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = label;
    select.appendChild(option);
  });
  select.value = [...select.options].some((option) => option.value === previous) ? previous : "";
}

function refreshFacetOptions(filterOptions = {}) {
  populateFacetSelect(elements.sizeFilter, filterOptions.sizes, "全部尺寸");
  populateFacetSelect(elements.colorFilter, filterOptions.colors, "全部顏色", COLOR_LABELS);
  populateFacetSelect(elements.materialFilter, filterOptions.materials, "全部材質", MATERIAL_LABELS);
}

function refreshCategoryOptions() {
  const previous = elements.groupFilter.value;
  elements.groupFilter.innerHTML = '<option value="">全部空間</option>';
  data.categoryGroups.forEach((group) => {
    const option = document.createElement("option");
    option.value = group.group_id;
    option.textContent = safeText(group.group_name_zh, group.group_id);
    elements.groupFilter.appendChild(option);
  });
  elements.groupFilter.value = data.categoryGroups.some((group) => group.group_id === previous) ? previous : "";
}

function refreshTypeOptions() {
  const previous = elements.typeFilter.value;
  elements.typeFilter.innerHTML = '<option value="">全部類型</option>';
  data.typeOptions
    .slice()
    .sort((left, right) => formatTypeName(left.type).localeCompare(formatTypeName(right.type), "zh-Hant"))
    .forEach((item) => {
      const option = document.createElement("option");
      option.value = item.type;
      option.textContent = formatTypeName(item.type);
      elements.typeFilter.appendChild(option);
    });
  elements.typeFilter.value = data.typeOptions.some((item) => item.type === previous) ? previous : "";
}

function setActiveFurniture(item) {
  state.activeFurnitureId = item.furniture_id;
  state.activeFurniture = item;
  document.querySelectorAll(".library-card-page").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.furnitureId === state.activeFurnitureId);
  });
  elements.viewerTitle.textContent = formatFurnitureName(item);
  elements.viewerStyle.textContent = formatStyleName(item.primary_style);
  elements.viewerType.textContent = formatTypeName(item.normalized_type);
  elements.viewerSize.textContent = formatSize(item.size_cm, item);
  elements.viewerMaterial.textContent = formatMaterialValue(item.material);
  elements.viewerColor.textContent = formatColorValue(item.color);
  viewer.setTheme(shouldUseDarkFurnitureStage(item) ? "dark-stage" : "light-stage");
  if (item.model_url) {
    viewer.load(item.model_url);
  } else {
    viewer.clear();
    elements.viewerStatus.textContent = "此離線型錄項目沒有可用的 GLB 模型；尺寸與材質資料仍可正常瀏覽。";
  }
  syncActiveButtons();
}

function renderPagination() {
  elements.libraryPagination.innerHTML = "";
  const totalPages = Math.ceil(state.totalItems / state.itemsPerPage);
  if (totalPages <= 1) return;
  const addButton = (label, page, disabled = false) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pagination-button";
    button.textContent = label;
    button.disabled = disabled;
    button.classList.toggle("is-active", page === state.currentPage);
    button.addEventListener("click", () => {
      state.currentPage = page;
      loadLibraryPage().then(() => scrollPageTop(libraryTopAnchor, 18));
    });
    elements.libraryPagination.appendChild(button);
  };
  addButton("上一頁", Math.max(1, state.currentPage - 1), state.currentPage === 1);
  for (let page = 1; page <= Math.min(totalPages, 7); page += 1) addButton(String(page), page);
  if (totalPages > 7) {
    const last = document.createElement("span");
    last.textContent = "...";
    elements.libraryPagination.appendChild(last);
    addButton(String(totalPages), totalPages);
  }
  addButton("下一頁", Math.min(totalPages, state.currentPage + 1), state.currentPage === totalPages);
}

function renderLibrary() {
  elements.libraryGrid.innerHTML = "";
  const groupSelected = Boolean(getCurrentGroup());
  if (!groupSelected) {
    elements.libraryCount.textContent = "先選擇空間";
    elements.libraryGrid.innerHTML = '<p class="scene-selected-empty">先從上方選擇空間與家具類型，候選家具才會出現。</p>';
    elements.libraryPagination.innerHTML = "";
    return;
  }

  elements.libraryCount.textContent = `共 ${state.totalItems} 件可加入方案的模型`;
  if (!state.filteredFurniture.length) {
    elements.libraryGrid.innerHTML = '<p class="scene-selected-empty">找不到符合條件的可載入模型，請改選類型或清除進階篩選。</p>';
    elements.libraryPagination.innerHTML = "";
    return;
  }

  state.filteredFurniture.forEach((item) => {
    const card = document.createElement("article");
    card.className = "library-card-page";
    card.dataset.furnitureId = item.furniture_id;
    card.classList.toggle("is-active", item.furniture_id === state.activeFurnitureId);
    const added = state.proposalItems.has(item.furniture_id);
    const favorite = state.favoriteItems.has(item.furniture_id);
    const addLabel = added ? "已加入方案" : `加入 ${formatFurnitureName(item)} 至方案`;
    card.innerHTML = `
      <button type="button" class="mode1-card-favorite" data-favorite aria-label="${favorite ? "取消收藏" : "收藏"} ${formatFurnitureName(item)}" aria-pressed="${favorite}">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 5.7a5.2 5.2 0 0 0-7.4 0L12 7.1l-1.4-1.4a5.2 5.2 0 1 0-7.4 7.4L12 21l8.8-7.9a5.2 5.2 0 0 0 0-7.4Z" /></svg>
      </button>
      <img class="library-preview-image" alt="${formatFurnitureName(item)} 3D 預覽" loading="lazy" />
      <div class="mode1-card-copy">
        <h3>${formatFurnitureName(item)}</h3>
        <p class="mode1-card-size">${formatSize(item.size_cm, item)}</p>
        <div class="mode1-card-tags">
          <span>${formatStyleName(item.primary_style)}</span>
          <span>${formatMaterialValue(item.material)}</span>
          <span>${formatColorValue(item.color)}</span>
        </div>
      </div>
      <div class="mode1-card-actions">
        <span class="mode1-card-model-state">3D</span>
        <button type="button" class="mode1-card-add" data-add ${added ? "disabled" : ""} aria-label="${addLabel}">${added ? "✓" : "＋"}</button>
      </div>`;
    card.addEventListener("click", () => setActiveFurniture(item));
    card.querySelector("[data-favorite]").addEventListener("click", (event) => {
      event.stopPropagation();
      if (state.favoriteItems.has(item.furniture_id)) state.favoriteItems.delete(item.furniture_id);
      else state.favoriteItems.add(item.furniture_id);
      saveFavorites();
      renderLibrary();
    });
    card.querySelector("[data-add]").addEventListener("click", (event) => {
      event.stopPropagation();
      addToProposal(item);
    });
    elements.libraryGrid.appendChild(card);
    attachLibraryThumbnail(card.querySelector(".library-preview-image"), item);
  });
  renderPagination();
}

function selectDefaultFurnitureForPage() {
  if (!state.filteredFurniture.length) return;
  const activeStillVisible = state.filteredFurniture.some((item) => item.furniture_id === state.activeFurnitureId);
  if (!state.activeFurniture || !activeStillVisible) setActiveFurniture(state.filteredFurniture[0]);
}

async function loadLibraryPage() {
  const requestId = ++currentRequestId;
  if (getCurrentGroup()) elements.libraryCount.textContent = "載入候選家具中...";
  try {
    const result = await fetchFurniturePage({
      q: elements.searchInput.value.trim(),
      style: elements.styleFilter.value,
      group: elements.typeFilter.value ? "" : getCurrentGroup(),
      type: elements.typeFilter.value,
      size: elements.sizeFilter.value,
      color: elements.colorFilter.value,
      material: elements.materialFilter.value,
      page: state.currentPage,
      page_size: state.itemsPerPage,
      has_model: true,
    });
    if (requestId !== currentRequestId) return;
    data.styles = result.styles || data.styles;
    data.categoryGroups = result.category_groups || data.categoryGroups;
    data.typeOptions = result.type_options || data.typeOptions;
    refreshFacetOptions(result.filter_options || {});
    styleNames = styleNameMap(data.styles);
    refreshCategoryOptions();
    refreshTypeOptions();
    state.filteredFurniture = result.items || [];
    state.totalItems = Number(result.total || 0);
    renderSpaceChoices();
    renderTypeChoices();
    renderLibrary();
    selectDefaultFurnitureForPage();
  } catch (error) {
    if (requestId !== currentRequestId) return;
    console.error("家具候選載入失敗", error);
    elements.libraryCount.textContent = "家具候選載入失敗";
    elements.libraryGrid.innerHTML = '<p class="scene-selected-empty">請確認伺服器已啟動後再試一次。</p>';
    elements.libraryPagination.innerHTML = "";
  }
}

async function bootstrapModeOne() {
  restoreProposal();
  restoreFavorites();
  renderProposal();
  syncActiveButtons();
  const result = await fetchFurniturePage({ page: 1, page_size: 1, has_model: true });
  data.styles = result.styles || [];
  data.categoryGroups = result.category_groups || [];
  data.typeOptions = result.type_options || [];
  data.allTypeOptions = result.type_options || [];
  styleNames = styleNameMap(data.styles);
  populateFilters();
  refreshFacetOptions(result.filter_options || {});
  renderSpaceChoices();
  const initialGroup = getGroup("living") ? "living" : data.categoryGroups[0]?.group_id || "";
  if (initialGroup) {
    elements.groupFilter.value = initialGroup;
    elements.spaceSelect.value = initialGroup;
    renderTypeChoices();
    await loadLibraryPage();
  }
}

function applyLibraryFilters() {
  state.currentPage = 1;
  window.clearTimeout(filterTimer);
  filterTimer = window.setTimeout(loadLibraryPage, 180);
}

elements.searchInput.addEventListener("input", applyLibraryFilters);
elements.styleFilter.addEventListener("change", applyLibraryFilters);
elements.sizeFilter.addEventListener("change", applyLibraryFilters);
elements.colorFilter.addEventListener("change", applyLibraryFilters);
elements.materialFilter.addEventListener("change", applyLibraryFilters);
elements.groupFilter.addEventListener("change", () => {
  selectSpace(elements.groupFilter.value);
});
elements.spaceSelect.addEventListener("change", () => selectSpace(elements.spaceSelect.value));
elements.typeFilter.addEventListener("change", applyLibraryFilters);
elements.typeNext.addEventListener("click", () => {
  elements.typeGrid.scrollBy({ left: 280, behavior: "smooth" });
});
elements.toggleAdvancedFilters.addEventListener("click", () => {
  const opening = elements.advancedFilters.hidden;
  elements.advancedFilters.hidden = !opening;
  elements.toggleAdvancedFilters.setAttribute("aria-expanded", String(opening));
  elements.toggleAdvancedFilters.textContent = opening ? "收起進階篩選" : "進階篩選 ✦";
});
elements.clearProposal.addEventListener("click", () => {
  state.proposalItems.clear();
  saveProposal();
  renderProposal();
  renderLibrary();
  syncActiveButtons();
});
elements.enterSceneWithProposal.addEventListener("click", enterSceneWithProposal);
elements.addActiveToProposal.addEventListener("click", () => {
  if (state.activeFurniture) addToProposal(state.activeFurniture);
});
elements.addActiveAndEnterScene.addEventListener("click", () => {
  if (state.activeFurniture) addToProposal(state.activeFurniture);
  enterSceneWithProposal();
});
elements.resetViewer.addEventListener("click", () => viewer.resetCamera());
elements.spinModel.addEventListener("click", () => {
  state.spinEnabled = viewer.toggleSpin();
  elements.spinModel.textContent = state.spinEnabled ? "停止旋轉" : "自動旋轉";
});

initBackgroundFx();
await bootstrapModeOne();
