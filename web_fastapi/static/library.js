import {
  fetchSiteData,
  formatSize,
  formatTypeLabel,
  initBackgroundFx,
  scrollPageTop,
  styleNameMap,
} from "./common.js?v=20260707a";
import { createViewer } from "./viewer.js?v=20260707a";
import { attachLibraryThumbnail } from "./library_thumbnails.js?v=20260707a";

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
  walnut: "胡桃木色",
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

function scrollLibraryTop() {
  scrollPageTop(libraryTopAnchor, 18);
}

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

function formatStyleName(styleId) {
  return styleNames.get(styleId) || styleId || "未分類";
}

function formatType(typeName) {
  return formatTypeLabel(typeName);
}

function formatColor(colorText) {
  if (!colorText) return "未提供";
  return colorText
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => COLOR_LABELS[token.toLowerCase()] || token)
    .join(" / ");
}

function modelBadge(item) {
  return item.has_model
    ? '<span class="badge success">GLB 可看</span>'
    : '<span class="badge warning">缺 GLB</span>';
}

function isDarkFurniture(item) {
  const tokens = [item.color, item.name_en, item.name_zh_raw, item.material]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return ["black", "dark", "anthracite", "charcoal", "brown", "黑", "深灰", "深色"].some((keyword) =>
    tokens.includes(keyword)
  );
}

function createFallbackSvg(item) {
  const color = formatColor(item.color);
  const type = formatType(item.normalized_type);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320">
      <rect width="480" height="320" rx="28" fill="#fffaf4"/>
      <rect x="24" y="24" width="432" height="272" rx="22" fill="#f7efe6" stroke="#d9cab9"/>
      <text x="36" y="72" fill="#7a6653" font-size="20" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">預覽載入中</text>
      <text x="36" y="120" fill="#4f4439" font-size="34" font-weight="700" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">${type}</text>
      <text x="36" y="164" fill="#725f4e" font-size="24" font-family="Noto Sans TC, Microsoft JhengHei, sans-serif">${color}</text>
    </svg>
  `;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function populateFilters() {
  const typeSet = new Set();

  data.styles.forEach((style) => {
    const option = document.createElement("option");
    option.value = style.style_id;
    option.textContent = style.style_name_zh;
    elements.styleFilter.appendChild(option);
  });

  data.furniture.forEach((item) => {
    if (item.normalized_type) typeSet.add(item.normalized_type);
  });

  [...typeSet].sort().forEach((typeName) => {
    const option = document.createElement("option");
    option.value = typeName;
    option.textContent = formatType(typeName);
    elements.typeFilter.appendChild(option);
  });
}

function syncActiveCard() {
  document.querySelectorAll(".library-card-page").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.furnitureId === state.activeFurnitureId);
  });
}

function setViewerText(item) {
  elements.viewerTitle.textContent = item.name_zh_raw || "未命名家具";
  elements.viewerStyle.textContent = formatStyleName(item.primary_style);
  elements.viewerType.textContent = formatType(item.normalized_type);
  elements.viewerSize.textContent = formatSize(item.size_cm);
}

function setActiveFurniture(item) {
  state.activeFurnitureId = item.furniture_id;
  syncActiveCard();
  setViewerText(item);
  viewer.setTheme(isDarkFurniture(item) ? "light-stage" : "dark-stage");

  if (!item.has_model) {
    viewer.clear();
    elements.viewerStatus.textContent = item.missing_model_reason || "這件家具目前沒有可載入的 GLB。";
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

  addButton(
    "上一頁",
    () => {
      state.currentPage -= 1;
      renderLibrary();
      syncActiveCard();
      scrollLibraryTop();
    },
    state.currentPage === 1
  );

  const visiblePages = buildVisiblePages(totalPages);
  let previousPage = 0;

  visiblePages.forEach((page) => {
    if (previousPage && page - previousPage > 1) {
      addButton("...", () => {}, true, false, true);
    }

    addButton(
      String(page),
      () => {
        state.currentPage = page;
        renderLibrary();
        syncActiveCard();
        scrollLibraryTop();
      },
      false,
      page === state.currentPage
    );

    previousPage = page;
  });

  addButton(
    "下一頁",
    () => {
      state.currentPage += 1;
      renderLibrary();
      syncActiveCard();
      scrollLibraryTop();
    },
    state.currentPage === totalPages
  );
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
      ?.slice(0, 3)
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
        alt="${item.name_zh_raw || "家具"} 預覽圖"
        loading="lazy"
      />
      <h3>${item.name_zh_raw || "未命名家具"}</h3>
      <dl>
        <div><dt>類型</dt><dd>${formatType(item.normalized_type)}</dd></div>
        <div><dt>顏色</dt><dd>${formatColor(item.color)}</dd></div>
        <div><dt>尺寸</dt><dd>${formatSize(item.size_cm)}</dd></div>
        <div><dt>候選風格</dt><dd>${candidateNames || "未提供"}</dd></div>
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
  elements.viewerTitle.textContent = "目前沒有可顯示的家具";
  elements.viewerStyle.textContent = "-";
  elements.viewerType.textContent = "-";
  elements.viewerSize.textContent = "-";
  elements.viewerStatus.textContent = "請重新調整篩選條件。";
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
elements.styleFilter.addEventListener("change", applyLibraryFilters);
elements.typeFilter.addEventListener("change", applyLibraryFilters);
elements.resetViewer.addEventListener("click", () => viewer.resetCamera());
elements.spinModel.addEventListener("click", () => {
  state.spinEnabled = viewer.toggleSpin();
  elements.spinModel.textContent = state.spinEnabled ? "停止旋轉" : "旋轉模型";
});

populateFilters();
initBackgroundFx();
applyLibraryFilters();
