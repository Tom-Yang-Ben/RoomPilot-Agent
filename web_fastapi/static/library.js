import { fetchSiteData, formatSize, initBackgroundFx, styleNameMap } from "./common.js?v=20260703c";
import { createViewer } from "./viewer.js?v=20260703c";

const data = await fetchSiteData();
const styleNames = styleNameMap(data.styles);

const state = {
  filteredFurniture: [...data.furniture],
  activeFurnitureId: null,
  spinEnabled: false,
};

const elements = {
  searchInput: document.getElementById("search-input"),
  styleFilter: document.getElementById("style-filter"),
  typeFilter: document.getElementById("type-filter"),
  libraryGrid: document.getElementById("library-grid"),
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

function modelBadge(item) {
  return item.has_model
    ? '<span class="badge success">GLB 可看</span>'
    : '<span class="badge warning">缺 GLB</span>';
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
    if (item.normalized_type) {
      typeSet.add(item.normalized_type);
    }
  });

  [...typeSet].sort().forEach((typeName) => {
    const option = document.createElement("option");
    option.value = typeName;
    option.textContent = typeName;
    elements.typeFilter.appendChild(option);
  });
}

function syncActiveCard() {
  document.querySelectorAll(".library-card-page").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.furnitureId === state.activeFurnitureId);
  });
}

function setViewerText(item) {
  elements.viewerTitle.textContent = item.name_zh_raw || item.name_en || "未命名家具";
  elements.viewerStyle.textContent = formatStyleName(item.primary_style);
  elements.viewerType.textContent = item.normalized_type ?? "-";
  elements.viewerSize.textContent = formatSize(item.size_cm);
}

function setActiveFurniture(item) {
  state.activeFurnitureId = item.furniture_id;
  syncActiveCard();
  setViewerText(item);

  if (!item.has_model) {
    viewer.clear();
    elements.viewerStatus.textContent = item.missing_model_reason || "這件家具目前沒有可用的 GLB 模型。";
    return;
  }

  viewer.load(item.model_url);
}

function renderLibrary() {
  elements.libraryGrid.innerHTML = "";
  elements.libraryCount.textContent = `${state.filteredFurniture.length} 筆家具`;
  const missingCount = state.filteredFurniture.filter((item) => !item.has_model).length;
  elements.missingSummary.textContent = `其中 ${missingCount} 筆目前缺少可用 GLB`;

  state.filteredFurniture.slice(0, 120).forEach((item) => {
    const card = document.createElement("article");
    card.className = "library-card-page";
    card.dataset.furnitureId = item.furniture_id;
    if (item.furniture_id === state.activeFurnitureId) {
      card.classList.add("is-active");
    }

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
      <h3>${item.name_zh_raw || item.name_en}</h3>
      <p class="muted">${item.name_en || ""}</p>
      <dl>
        <div><dt>類型</dt><dd>${item.normalized_type ?? "-"}</dd></div>
        <div><dt>顏色</dt><dd>${item.color ?? "-"}</dd></div>
        <div><dt>尺寸</dt><dd>${formatSize(item.size_cm)}</dd></div>
        <div><dt>候選風格</dt><dd>${candidateNames || "-"}</dd></div>
      </dl>
      ${item.has_model ? "" : `<p class="muted">${item.missing_model_reason}</p>`}
    `;

    card.addEventListener("click", () => setActiveFurniture(item));
    elements.libraryGrid.appendChild(card);
  });
}

function ensureActiveFurnitureStillVisible() {
  const activeStillExists = state.filteredFurniture.some((item) => item.furniture_id === state.activeFurnitureId);
  if (activeStillExists) {
    const sameItem = state.filteredFurniture.find((item) => item.furniture_id === state.activeFurnitureId);
    if (sameItem) {
      setActiveFurniture(sameItem);
    }
    return;
  }

  const nextAvailable = state.filteredFurniture.find((item) => item.has_model) || state.filteredFurniture[0];
  if (nextAvailable) {
    setActiveFurniture(nextAvailable);
    return;
  }

  state.activeFurnitureId = null;
  viewer.clear();
  elements.viewerTitle.textContent = "目前沒有符合條件的家具";
  elements.viewerStyle.textContent = "-";
  elements.viewerType.textContent = "-";
  elements.viewerSize.textContent = "-";
  elements.viewerStatus.textContent = "請調整搜尋或篩選條件。";
}

function applyLibraryFilters() {
  const query = elements.searchInput.value.trim().toLowerCase();
  const styleFilter = elements.styleFilter.value;
  const typeFilter = elements.typeFilter.value;

  state.filteredFurniture = data.furniture.filter((item) => {
    const haystack = [
      item.name_en,
      item.name_zh_raw,
      item.normalized_type,
      item.color,
      item.material,
      item.category_label,
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

  renderLibrary();
  ensureActiveFurnitureStillVisible();
}

elements.searchInput.addEventListener("input", applyLibraryFilters);
elements.styleFilter.addEventListener("change", applyLibraryFilters);
elements.typeFilter.addEventListener("change", applyLibraryFilters);
elements.resetViewer.addEventListener("click", () => viewer.resetCamera());
elements.spinModel.addEventListener("click", () => {
  state.spinEnabled = viewer.toggleSpin();
  elements.spinModel.textContent = state.spinEnabled ? "停止旋轉" : "模型旋轉展示";
});

populateFilters();
initBackgroundFx();
applyLibraryFilters();
