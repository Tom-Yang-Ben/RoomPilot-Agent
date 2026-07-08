import { fetchSiteData, formatFurnitureName, formatSize, formatTypeLabel, initBackgroundFx } from "./common.js?v=20260708d";
import { createSceneViewer } from "./scene_viewer.js?v=20260708n";

const siteData = await fetchSiteData();
const providerStatus = await fetch("/api/scene/provider-status").then((response) => response.json());
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

const elements = {
  sceneForm: document.getElementById("scene-form"),
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
  personalNotes: document.getElementById("personal-notes"),
  keepWindowClear: document.getElementById("keep-window-clear"),
  keepDoorClear: document.getElementById("keep-door-clear"),
  needStorage: document.getElementById("need-storage"),
  preferLowSaturation: document.getElementById("prefer-low-saturation"),
  generateScene: document.getElementById("generate-scene"),
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
};

const viewer = createSceneViewer(elements.sceneViewerCanvas, elements.sceneStatus);
let uploadedDxfText = null;
let furnitureRandomSeed = Date.now();
let currentSceneData = null;
let wallOptionLabelMap = new Map();
let floorOptionLabelMap = new Map();
const surfaceFilters = { wall: "all", floor: "all" };
const surfaceSearchQueries = { wall: "", floor: "" };
const surfaceStyleOnly = { wall: false, floor: false };
const surfaceVisibleLimits = { wall: 12, floor: 12 };
const styleNameById = new Map((siteData.styles || []).map((style) => [style.style_id, style.style_name_zh]));

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
  setFurnitureSelection(DEFAULT_FURNITURE_BY_SPACE[elements.spaceType.value] || DEFAULT_FURNITURE_BY_SPACE.living_room);
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

function pickFurnitureCandidate(type, usedIds = new Set()) {
  if (!currentSceneData) return null;
  const styleId = currentSceneData.style.style_id;
  const sameType = siteData.furniture.filter(
    (item) => item.has_model && item.normalized_type === type && !usedIds.has(item.furniture_id)
  );
  const stylePool = sameType.filter((item) => styleMatchesFurniture(item, styleId));
  const pool = stylePool.length ? stylePool : sameType;
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

async function generateScene(event) {
  event.preventDefault();
  setGeneratingState(true);
  try {
    const floorplanFile = elements.floorplan.files?.[0];
    uploadedDxfText = floorplanFile && floorplanFile.name.toLowerCase().endsWith(".dxf")
      ? await floorplanFile.text()
      : null;
    const sceneLook = getStyleSceneLook();
    const payload = {
      room_width_cm: Number(elements.roomWidth.value),
      room_depth_cm: Number(elements.roomDepth.value),
      space_type: elements.spaceType.value,
      style_preference: elements.stylePreference.value,
      required_furniture: selectedValues(elements.furnitureOptions),
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
  const replacement = pickFurnitureCandidate(currentItem.normalized_type, usedIds);
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
  const candidate = pickFurnitureCandidate(type, usedIds);
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
  currentSceneData.scene_objects = currentSceneData.scene_objects.map((item) => {
    const candidate = pickFurnitureCandidate(item.normalized_type, usedIds);
    if (!candidate) return item;
    usedIds.add(candidate.furniture_id);
    return sceneObjectFromFurniture(candidate);
  });
  furnitureRandomSeed = Date.now();
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene("已依目前風格重抽整組家具。");
}

renderStyleOptions();
renderToggleOptions(elements.furnitureOptions, furnitureOptions, "furniture");
renderToggleOptions(elements.colorOptions, buildColorOptions(), "color");
renderAddFurnitureSelect();
syncSurfaceChoicesToStyle();
setDefaultFurnitureBySpace();
renderInitialProviderStatus();

elements.sceneForm.addEventListener("submit", generateScene);
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
elements.viewPresetButtons.forEach((button) => {
  button.addEventListener("click", () => viewer.setCameraPreset(button.dataset.viewPreset));
});

initBackgroundFx();
