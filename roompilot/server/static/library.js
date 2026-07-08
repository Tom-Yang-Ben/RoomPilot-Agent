import {
  fetchSiteData,
  formatFurnitureName,
  formatSize,
  formatTypeLabel,
  initBackgroundFx,
  shouldUseDarkFurnitureStage,
  scrollPageTop,
  styleNameMap,
} from "./common.js?v=20260708e";
import { createViewer } from "./viewer.js?v=20260708a";
import { attachLibraryThumbnail } from "./library_thumbnails.js?v=20260708c";

const data = await fetchSiteData();
const styleNames = styleNameMap(data.styles);

const COLOR_LABELS = {
  black: "黑色",
  white: "白色",
  beige: "米色",
  "light beige": "淺米色",
  grey: "灰色",
  gray: "灰色",
  brown: "棕色",
  blue: "藍色",
  green: "綠色",
  red: "紅色",
  yellow: "黃色",
  pink: "粉色",
  natural: "自然色",
  oak: "橡木色",
  walnut: "胡桃色",
  brass: "黃銅色",
};

const state = {
  filteredFurniture: [...data.furniture],
  activeFurnitureId: null,
  spinEnabled: false,
  currentPage: 1,
  itemsPerPage: 21,
};

const libraryTopAnchor = document.querySelector(".page-shell.two-column-shell > section.page-panel");

const elements = {
  searchInput: document.getElementById("search-input"),
  styleFilter: document.getElementById("style-filter"),
  typeFilter: document.getElementById("type-filter"),
  libraryGrid: document.getElementById("library-grid"),
  libraryPagination: document.getElementById("library-pagination"),
  libraryCount: document.getElementById("library-count"),
  missingSummary: document.getElementById("missing-summary"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerStyle: document.getElementById("viewer-style"),
  viewerType: document.getElementById("viewer-type"),
  viewerSize: document.getElementById("viewer-size"),
  viewerStatus: document.getElementById("viewer-status"),
  viewerCanvas: document.getElementById("viewer-canvas"),
  resetViewer: document.getElementById("reset-viewer"),
  spinModel: document.getElementById("spin-model"),
};

const viewer = createViewer(elements.viewerCanvas, elements.viewerStatus);

function scrollLibraryTop() {
  scrollPageTop(libraryTopAnchor, 18);
}

function formatStyleName(styleId) {
  return styleNames.get(styleId) || styleId || "未分類";
}

function formatType(typeName) {
  return formatTypeLabel(typeName);
}

function formatColor(colorText) {
  if (!colorText) return "尚未整理";
  return String(colorText)
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => COLOR_LABELS[token.toLowerCase()] || token)
    .join(" / ");
}

function modelBadge(item) {
  return item.has_model
    ? '<span class="badge success">GLB 可檢視</span>'
    : '<span class="badge warning">缺少 GLB</span>';
}

function createFallbackSvg(item) {
  const color = formatColor(item.color);
  const type = formatType(item.normalized_type);
  const isLight = shouldUseDarkFurnitureStage(item);
  const bg = isLight ? "#171311" : "#fffaf4";
  const panel = isLight ? "#241f1b" : "#f7efe6";
  const stroke = isLight ? "#5d5147" : "#d9cab9";
  const title = isLight ? "#fff7ef" : "#4f4439";
  const meta = isLight ? "#d6c6b7" : "#725f4e";
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320">
      <rect width="480" height="320" rx="28" fill="${bg}"/>
      <rect x="24" y="24" width="432" height="272" rx="22" fill="${panel}" stroke="${stroke}"/>
      <text x="36" y="72" fill="${meta}" font-size="20" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">資料庫模型預覽</text>
      <text x="36" y="120" fill="${title}" font-size="34" font-weight="700" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">${type}</text>
      <text x="36" y="164" fill="${meta}" font-size="24" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">${color}</text>
    </svg>
  `;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function populateFilters() {
  data.styles.forEach((style) => {
    const option = document.createElement("option");
    option.value = style.style_id;
    option.textContent = style.style_name_zh;
    elements.styleFilter.appendChild(option);
  });

  refreshTypeOptions();
}

function refreshTypeOptions() {
  const styleId = elements.styleFilter.value;
  const available = new Set();
  data.furniture.forEach((item) => {
    if (!item.normalized_type) return;
    if (!styleId || item.primary_style === styleId) available.add(item.normalized_type);
  });

  const previous = elements.typeFilter.value;
  const allOption = elements.typeFilter.querySelector('option[value=""]');
  elements.typeFilter.innerHTML = "";
  if (allOption) elements.typeFilter.appendChild(allOption);

  [...available].sort((a, b) => formatType(a).localeCompare(formatType(b), "zh-Hant")).forEach((typeName) => {
    const option = document.createElement("option");
    option.value = typeName;
    option.textContent = formatType(typeName);
    elements.typeFilter.appendChild(option);
  });

  elements.typeFilter.value = available.has(previous) ? previous : "";
}

function syncActiveCard() {
  document.querySelectorAll(".library-card-page").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.furnitureId === state.activeFurnitureId);
  });
}

function setViewerText(item) {
  elements.viewerTitle.textContent = formatFurnitureName(item);
  elements.viewerStyle.textContent = formatStyleName(item.primary_style);
  elements.viewerType.textContent = formatType(item.normalized_type);
  elements.viewerSize.textContent = formatSize(item.size_cm, item);
}

function setActiveFurniture(item) {
  state.activeFurnitureId = item.furniture_id;
  syncActiveCard();
  setViewerText(item);
  viewer.setTheme(shouldUseDarkFurnitureStage(item) ? "dark-stage" : "light-stage");

  if (!item.has_model) {
    viewer.clear();
    elements.viewerStatus.textContent = item.missing_model_reason || "這筆家具目前沒有可檢視的 GLB 模型。";
    return;
  }

  viewer.load(item.model_url);
}

function buildVisiblePages(totalPages) {
  if (totalPages <= 8) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const visible = new Set([1, 2, 3, 4, 5, totalPages - 2, totalPages - 1, totalPages]);
  return [...visible].filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
}

function renderPagination(totalPages) {
  elements.libraryPagination.innerHTML = "";
  if (totalPages <= 1) return;

  const addButton = (label, onClick, disabled = false, active = false, isGap = false) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pagination-button";
    button.textContent = label;
    if (isGap) button.classList.add("is-gap");
    if (active) button.classList.add("is-active");
    button.disabled = disabled || isGap;
    if (!isGap) button.addEventListener("click", onClick);
    elements.libraryPagination.appendChild(button);
  };

  addButton("上一頁", () => {
    state.currentPage -= 1;
    renderLibrary();
    syncActiveCard();
    scrollLibraryTop();
  }, state.currentPage === 1);

  const visiblePages = buildVisiblePages(totalPages);
  let previousPage = 0;

  visiblePages.forEach((page) => {
    if (previousPage && page - previousPage > 1) {
      addButton("...", () => {}, true, false, true);
    }

    addButton(String(page), () => {
      state.currentPage = page;
      renderLibrary();
      syncActiveCard();
      scrollLibraryTop();
    }, false, page === state.currentPage);

    previousPage = page;
  });

  addButton("下一頁", () => {
    state.currentPage += 1;
    renderLibrary();
    syncActiveCard();
    scrollLibraryTop();
  }, state.currentPage === totalPages);
}

function renderLibrary() {
  elements.libraryGrid.innerHTML = "";
  elements.libraryCount.textContent = `${state.filteredFurniture.length} 筆家具`;
  elements.missingSummary.textContent = "";

  const totalPages = Math.max(1, Math.ceil(state.filteredFurniture.length / state.itemsPerPage));
  state.currentPage = Math.min(state.currentPage, totalPages);

  const startIndex = (state.currentPage - 1) * state.itemsPerPage;
  const pageItems = state.filteredFurniture.slice(startIndex, startIndex + state.itemsPerPage);

  pageItems.forEach((item) => {
    const card = document.createElement("article");
    card.className = "library-card-page";
    card.dataset.furnitureId = item.furniture_id;
    if (item.furniture_id === state.activeFurnitureId) card.classList.add("is-active");

    const candidateNames = item.style_candidates
      ?.filter((candidate) => {
        const score = Array.isArray(candidate) ? Number(candidate[1] ?? 1) : Number(candidate?.score ?? 1);
        return score > 0;
      })
      .slice(0, 3)
      .map((candidate) => {
        const styleId = Array.isArray(candidate) ? candidate[0] : candidate.style_id ?? candidate;
        return formatStyleName(styleId);
      })
      .join(" / ");

    card.innerHTML = `
      <div class="badge-row">
        ${modelBadge(item)}
        <span class="badge">${formatStyleName(item.primary_style)}</span>
      </div>
      <img
        class="library-preview-image"
        src="${createFallbackSvg(item)}"
        alt="${item.name_zh_raw || item.name_en || "家具"} 模型預覽"
        loading="lazy"
      />
      <h3>${formatFurnitureName(item)}</h3>
      <dl>
        <div><dt>類型</dt><dd>${formatType(item.normalized_type)}</dd></div>
        <div><dt>顏色</dt><dd>${formatColor(item.color)}</dd></div>
        <div><dt>尺寸</dt><dd>${formatSize(item.size_cm, item)}</dd></div>
        <div><dt>風格候選</dt><dd>${candidateNames || "尚未整理"}</dd></div>
      </dl>
    `;

    card.addEventListener("click", () => setActiveFurniture(item));
    elements.libraryGrid.appendChild(card);

    const image = card.querySelector(".library-preview-image");
    if (item.has_model && item.model_url) {
      attachLibraryThumbnail(image, item);
    }
  });

  renderPagination(totalPages);
}

function ensureActiveFurnitureStillVisible() {
  const activeStillExists = state.filteredFurniture.some((item) => item.furniture_id === state.activeFurnitureId);
  if (activeStillExists) {
    const sameItem = state.filteredFurniture.find((item) => item.furniture_id === state.activeFurnitureId);
    if (sameItem) setActiveFurniture(sameItem);
    return;
  }

  const nextAvailable = state.filteredFurniture.find((item) => item.has_model) || state.filteredFurniture[0];
  if (nextAvailable) {
    setActiveFurniture(nextAvailable);
    return;
  }

  state.activeFurnitureId = null;
  viewer.clear();
  elements.viewerTitle.textContent = "沒有符合篩選的家具";
  elements.viewerStyle.textContent = "-";
  elements.viewerType.textContent = "-";
  elements.viewerSize.textContent = "-";
  elements.viewerStatus.textContent = "請調整搜尋、風格或類型篩選。";
}

function applyLibraryFilters() {
  const query = elements.searchInput.value.trim().toLowerCase();
  const styleFilter = elements.styleFilter.value;
  const typeFilter = elements.typeFilter.value;

  state.filteredFurniture = data.furniture.filter((item) => {
    const haystack = [
      item.name_zh_raw,
      item.name_en,
      formatType(item.normalized_type),
      formatColor(item.color),
      formatStyleName(item.primary_style),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    const queryMatch = !query || haystack.includes(query);
    const styleMatch = !styleFilter || item.primary_style === styleFilter;
    const typeMatch = !typeFilter || item.normalized_type === typeFilter;
    return queryMatch && styleMatch && typeMatch;
  });

  state.currentPage = 1;
  renderLibrary();
  ensureActiveFurnitureStillVisible();
}

elements.searchInput.addEventListener("input", applyLibraryFilters);
elements.styleFilter.addEventListener("change", () => {
  refreshTypeOptions();
  applyLibraryFilters();
});
elements.typeFilter.addEventListener("change", applyLibraryFilters);
elements.resetViewer.addEventListener("click", () => viewer.resetCamera());
elements.spinModel.addEventListener("click", () => {
  state.spinEnabled = viewer.toggleSpin();
  elements.spinModel.textContent = state.spinEnabled ? "停止旋轉" : "旋轉模型";
});

populateFilters();
initBackgroundFx();
renderLibrary();
ensureActiveFurnitureStillVisible();
