import { fetchSiteData, formatSize, formatTypeLabel, initBackgroundFx } from "./common.js?v=20260707a";
import { createSceneViewer } from "./scene_viewer.js?v=20260707a";

const siteData = await fetchSiteData();
const providerStatus = await fetch("/api/scene/provider-status")
  .then((response) => (response.ok ? response.json() : { enabled: false, model: null }))
  .catch(() => ({ enabled: false, model: null }));

const surfaceCatalog = siteData.surface_catalog || { walls: [], floors: [] };
const wallSurfaces = surfaceCatalog.walls || [];
const floorSurfaces = surfaceCatalog.floors || [];
const wallSurfaceMap = new Map(wallSurfaces.map((item) => [item.surface_id, item]));
const floorSurfaceMap = new Map(floorSurfaces.map((item) => [item.surface_id, item]));

const STYLE_SURFACE_FALLBACKS = {
  scandinavian: { wall: "warm_white", floor: "light_oak" },
  modern: { wall: "light_gray", floor: "stone_gray" },
  minimalist_muji: { wall: "warm_white", floor: "light_oak" },
  nordic_modern: { wall: "light_gray", floor: "light_oak" },
  industrial: { wall: "concrete_gray", floor: "microcement" },
  wabi_sabi: { wall: "mineral_beige", floor: "microcement" },
  japanese: { wall: "warm_white", floor: "light_oak" },
  melad: { wall: "caramel_beige", floor: "walnut" },
  american: { wall: "greige_panel", floor: "medium_oak" },
  american_country: { wall: "warm_white", floor: "light_oak" },
  light_luxury: { wall: "light_gray", floor: "marble" },
  classical: { wall: "greige_panel", floor: "walnut" },
  eclectic: { wall: "warm_white", floor: "medium_oak" },
};

const COLOR_OPTIONS = [
  { value: "auto", label: "依風格自動" },
  { value: "米白", label: "米白" },
  { value: "奶茶色", label: "奶茶色" },
  { value: "淺木色", label: "淺木色" },
  { value: "淺灰", label: "淺灰" },
  { value: "黑色", label: "黑色" },
  { value: "綠色", label: "綠色" },
  { value: "胡桃木", label: "胡桃木" },
  { value: "黃銅", label: "黃銅" },
];

const RULE_PROFILES = {
  balanced: {
    keep_window_clear: true,
    keep_door_clear: true,
    need_storage: false,
    prefer_low_saturation: false,
    helper: "平衡風格、動線與家具數量。",
  },
  storage: {
    keep_window_clear: true,
    keep_door_clear: true,
    need_storage: true,
    prefer_low_saturation: false,
    helper: "提高收納家具優先度。",
  },
  calm: {
    keep_window_clear: true,
    keep_door_clear: true,
    need_storage: false,
    prefer_low_saturation: true,
    helper: "傾向留白、低彩度與較安靜的配置。",
  },
  open: {
    keep_window_clear: true,
    keep_door_clear: true,
    need_storage: false,
    prefer_low_saturation: false,
    helper: "保留更多通道與視覺開闊感。",
  },
};

const FURNITURE_PRESETS_BY_SPACE = {
  living_room: [
    { value: "living_basic", label: "客廳基本組合", items: ["sofa", "coffee-table", "tv-bench", "armchair"] },
    { value: "living_storage", label: "客廳收納組合", items: ["sofa", "coffee-table", "tv-bench", "sideboard", "bookcase"] },
    { value: "living_reading", label: "客廳閱讀角", items: ["sofa", "coffee-table", "armchair", "bookcase"] },
  ],
  bedroom: [
    { value: "bedroom_basic", label: "臥室基本組合", items: ["bed", "bedside-table", "bookcase"] },
    { value: "bedroom_storage", label: "臥室收納組合", items: ["bed", "bedside-table", "sideboard", "bookcase"] },
    { value: "bedroom_work", label: "臥室工作組合", items: ["bed", "bedside-table", "desk", "office-chair"] },
  ],
  workspace: [
    { value: "workspace_basic", label: "工作空間基本組合", items: ["desk", "office-chair", "bookcase"] },
    { value: "workspace_meeting", label: "工作空間會客組合", items: ["desk", "office-chair", "armchair", "coffee-table"] },
    { value: "workspace_storage", label: "工作空間收納組合", items: ["desk", "office-chair", "sideboard", "bookcase"] },
  ],
  dining_room: [
    { value: "dining_basic", label: "餐廳基本組合", items: ["dining-table", "dining-chair", "sideboard"] },
    { value: "dining_light", label: "餐廳輕量組合", items: ["dining-table", "dining-chair"] },
    { value: "dining_storage", label: "餐廳收納組合", items: ["dining-table", "dining-chair", "sideboard", "bookcase"] },
  ],
  studio: [
    { value: "studio_basic", label: "套房基本組合", items: ["sofa", "coffee-table", "desk", "bookcase"] },
    { value: "studio_sleep", label: "套房睡眠組合", items: ["bed", "bedside-table", "desk"] },
    { value: "studio_storage", label: "套房收納組合", items: ["sofa", "coffee-table", "sideboard", "bookcase"] },
  ],
};

function getStyleById(styleId) {
  return siteData.styles.find((style) => style.style_id === styleId) || null;
}

function getSurfaceCatalogList(kind) {
  return kind === "wall" ? wallSurfaces : floorSurfaces;
}

function getSurfaceMap(kind) {
  return kind === "wall" ? wallSurfaceMap : floorSurfaceMap;
}

function getSurfaceById(kind, surfaceId) {
  return getSurfaceMap(kind).get(surfaceId) || null;
}

function formatSurfaceLabel(kind, surface) {
  if (!surface) return "未指定";

  if (surface.surface_id === "auto") {
    return "依風格自動";
  }

  const detail = kind === "wall" ? surface.finish_zh : surface.material_zh || surface.finish_zh;
  return [surface.name_zh, detail].filter(Boolean).join("｜");
}

function buildSurfaceOptions(kind) {
  return getSurfaceCatalogList(kind).map((surface) => ({
    value: surface.surface_id,
    label: formatSurfaceLabel(kind, surface),
  }));
}

function getDefaultSurfaceChoice(styleId, kind) {
  const style = getStyleById(styleId);
  const surfaceIdField = kind === "wall" ? "wall_surface_id" : "floor_surface_id";
  const defaultField = kind === "wall" ? "default_wall_surface_id" : "default_floor_surface_id";
  const fallback = STYLE_SURFACE_FALLBACKS[styleId] || STYLE_SURFACE_FALLBACKS.scandinavian;
  const surfaceId =
    style?.scene_background?.[surfaceIdField] ||
    style?.[defaultField] ||
    fallback?.[kind] ||
    "auto";

  return getSurfaceById(kind, surfaceId) ? surfaceId : "auto";
}

function buildSurfacePreviewStyle(surface) {
  if (!surface) return "";
  const imageUrl = surface.preview_url || surface.texture_url;
  if (imageUrl) {
    return [
      `background-image:url('${imageUrl}')`,
      "background-size:cover",
      "background-position:center",
    ].join(";");
  }

  const base = surface.preview_hex || surface.base_hex || "#e7dccf";
  const accent = surface.accent_hex || base;
  return `background:linear-gradient(135deg, ${base}, ${accent});`;
}

function renderBackgroundSurfaceCard(kind, surface) {
  if (!surface) return "";

  const title = kind === "wall" ? "牆面" : "地板";
  const detail = kind === "wall" ? [surface.tone_zh, surface.finish_zh] : [surface.material_zh, surface.finish_zh];

  return `
    <article class="scene-surface-card">
      <div class="scene-surface-preview" style="${buildSurfacePreviewStyle(surface)}"></div>
      <div class="scene-surface-copy">
        <span>${title}</span>
        <strong>${surface.name_zh || "未指定"}</strong>
        <small>${detail.filter(Boolean).join(" / ") || "依風格推薦"}</small>
      </div>
    </article>
  `;
}

const elements = {
  sceneForm: document.getElementById("scene-form"),
  sceneViewerPanel: document.getElementById("scene-viewer-panel"),
  floorplan: document.getElementById("floorplan"),
  spaceType: document.getElementById("space-type"),
  stylePreference: document.getElementById("style-preference"),
  furniturePreset: document.getElementById("furniture-preset"),
  furniturePresetHint: document.getElementById("furniture-preset-hint"),
  colorPreference: document.getElementById("color-preference"),
  wallOptionSelect: document.getElementById("wall-option-select"),
  floorOptionSelect: document.getElementById("floor-option-select"),
  ruleProfile: document.getElementById("rule-profile"),
  roomWidth: document.getElementById("room-width"),
  roomDepth: document.getElementById("room-depth"),
  customFurniture: document.getElementById("custom-furniture"),
  personalNotes: document.getElementById("personal-notes"),
  generateScene: document.getElementById("generate-scene"),
  randomFurniture: document.getElementById("random-furniture"),
  sceneViewerCanvas: document.getElementById("scene-viewer-canvas"),
  sceneStatus: document.getElementById("scene-status"),
  sceneStyleName: document.getElementById("scene-style-name"),
  sceneLlmMode: document.getElementById("scene-llm-mode"),
  sceneItemCount: document.getElementById("scene-item-count"),
  sceneRoomSize: document.getElementById("scene-room-size"),
  resetSceneView: document.getElementById("reset-scene-view"),
  addFurnitureType: document.getElementById("add-furniture-type"),
  addFurniture: document.getElementById("add-furniture"),
  reshuffleScene: document.getElementById("reshuffle-scene"),
  sceneBackground: document.getElementById("scene-background"),
  sceneBackgroundDetail: document.getElementById("scene-background-detail"),
  sceneBackgroundSurfaces: document.getElementById("scene-background-surfaces"),
  sceneSelectedItems: document.getElementById("scene-selected-items"),
  viewPresetButtons: Array.from(document.querySelectorAll("[data-view-preset]")),
};

const viewer = createSceneViewer(elements.sceneViewerCanvas, elements.sceneStatus, {
  surfaceCatalog,
});

let currentSceneData = null;
let uploadedDxfText = null;
let sceneBusy = false;
let furnitureRandomSeed = Date.now();

function populateSelect(select, options, selectedValue = "") {
  select.innerHTML = "";

  options.forEach((option) => {
    const element = document.createElement("option");
    element.value = option.value;
    element.textContent = option.label;
    select.appendChild(element);
  });

  if (selectedValue && options.some((option) => option.value === selectedValue)) {
    select.value = selectedValue;
    return;
  }

  if (options.length) {
    select.value = options[0].value;
  }
}

function getStyleOptions() {
  return siteData.styles.map((style) => ({
    value: style.style_id,
    label: style.style_name_zh,
  }));
}

function getFurnitureTypeOptions() {
  const seen = new Map();
  siteData.furniture.forEach((item) => {
    const type = item.normalized_type;
    if (!type || seen.has(type)) return;
    seen.set(type, {
      value: type,
      label: formatTypeLabel(type),
    });
  });

  return Array.from(seen.values()).sort((left, right) => left.label.localeCompare(right.label, "zh-Hant"));
}

function getDefaultStyleId() {
  return siteData.styles.find((style) => style.style_id === "scandinavian")?.style_id || siteData.styles[0]?.style_id || "";
}

function resolveSurfaceChoice(selectedValue, fallbackValue) {
  return selectedValue === "auto" ? fallbackValue : selectedValue;
}

function splitCustomList(rawValue) {
  return String(rawValue || "")
    .split(/[,\n，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function furniturePresetsForSpace(spaceType) {
  return FURNITURE_PRESETS_BY_SPACE[spaceType] || FURNITURE_PRESETS_BY_SPACE.living_room;
}

function getCurrentFurniturePreset() {
  return furniturePresetsForSpace(elements.spaceType.value).find((preset) => preset.value === elements.furniturePreset.value) || null;
}

function getStyleName(styleId) {
  return getStyleById(styleId)?.style_name_zh || styleId || "未指定";
}

function setStatus(message) {
  elements.sceneStatus.textContent = message;
}

function setBusyState(nextBusy, buttonText = "直接生成 3D 場景") {
  sceneBusy = nextBusy;

  elements.generateScene.disabled = nextBusy;
  elements.randomFurniture.disabled = nextBusy;
  elements.addFurniture.disabled = nextBusy;
  elements.reshuffleScene.disabled = nextBusy;
  elements.resetSceneView.disabled = nextBusy;
  elements.viewPresetButtons.forEach((button) => {
    button.disabled = nextBusy;
  });

  elements.generateScene.textContent = nextBusy ? buttonText : "直接生成 3D 場景";

  elements.sceneSelectedItems.querySelectorAll("button").forEach((button) => {
    button.disabled = nextBusy;
  });
}

function renderStyleSelect() {
  populateSelect(elements.stylePreference, getStyleOptions(), getDefaultStyleId());
}

function renderColorSelect() {
  populateSelect(elements.colorPreference, COLOR_OPTIONS, "auto");
}

function renderWallSelect() {
  populateSelect(elements.wallOptionSelect, buildSurfaceOptions("wall"), "auto");
}

function renderFloorSelect() {
  populateSelect(elements.floorOptionSelect, buildSurfaceOptions("floor"), "auto");
}

function renderAddFurnitureSelect() {
  populateSelect(elements.addFurnitureType, getFurnitureTypeOptions());
}

function updateFurniturePresetHint() {
  const preset = getCurrentFurniturePreset();
  if (!preset) {
    elements.furniturePresetHint.textContent = "目前空間類型尚未設定家具組合。";
    return;
  }

  const labels = preset.items.map((item) => formatTypeLabel(item)).join("、");
  elements.furniturePresetHint.textContent = `目前組合：${labels}`;
}

function renderFurniturePresetSelect() {
  const presets = furniturePresetsForSpace(elements.spaceType.value);
  const currentValue = elements.furniturePreset.value;
  const selectedValue = presets.some((preset) => preset.value === currentValue) ? currentValue : presets[0]?.value || "";

  populateSelect(
    elements.furniturePreset,
    presets.map((preset) => ({ value: preset.value, label: preset.label })),
    selectedValue
  );

  updateFurniturePresetHint();
}

function renderProviderStatus() {
  if (providerStatus.enabled) {
    elements.sceneLlmMode.textContent = providerStatus.model ? `OpenRouter / ${providerStatus.model}` : "OpenRouter";
    setStatus("目前可使用 OpenRouter；生成時會先嘗試 LLM，再回退到本地規則。");
    return;
  }

  elements.sceneLlmMode.textContent = "本地規則 fallback";
  setStatus("目前未接上 OpenRouter，會以本地規則先完成家具配置。");
}

function updateRandomButtonLabel() {
  elements.randomFurniture.textContent = currentSceneData?.scene_objects?.length ? "同風格替換全部" : "重抽家具組合";
}

function renderSelectedItems(sceneData) {
  const items = sceneData?.selected_furniture || [];
  if (!items.length) {
    elements.sceneSelectedItems.innerHTML = `
      <div class="scene-selected-empty">
        <strong>尚未生成家具配置</strong>
        <p>請先在上方選好條件，再按「直接生成 3D 場景」。</p>
      </div>
    `;
    return;
  }

  elements.sceneSelectedItems.innerHTML = items
    .map((item, index) => {
      const displayName = item.name_zh_raw || formatTypeLabel(item.normalized_type);
      const typeLabel = formatTypeLabel(item.normalized_type);
      const itemCode = String(index + 1).padStart(2, "0");

      return `
        <article class="scene-selected-item">
          <span class="scene-selected-index">${index + 1}</span>
          <div class="scene-selected-copy">
            <strong>${displayName}</strong>
            <small>家具編號 ${itemCode} ・ ${typeLabel} ・ ${formatSize(item.size_cm)}</small>
          </div>
          <div class="scene-selected-actions">
            <button type="button" class="scene-item-btn scene-item-btn-primary" data-scene-item-action="replace" data-index="${index}">
              同風格替換
            </button>
            <button type="button" class="scene-item-btn" data-scene-item-action="remove" data-index="${index}">
              移除
            </button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSummary(sceneData) {
  if (!sceneData) {
    elements.sceneStyleName.textContent = "-";
    elements.sceneItemCount.textContent = "0";
    elements.sceneRoomSize.textContent = "-";
    return;
  }

  elements.sceneStyleName.textContent = sceneData.style?.style_name_zh || getStyleName(sceneData.plan_json?.style_id);
  elements.sceneItemCount.textContent = String(sceneData.scene_objects?.length || 0);
  elements.sceneRoomSize.textContent = `${sceneData.floorplan?.width_cm || "-"} × ${sceneData.floorplan?.depth_cm || "-"} cm`;
}

function renderBackground(sceneData) {
  if (!sceneData) {
    elements.sceneBackground.textContent = "-";
    elements.sceneBackgroundDetail.textContent = "生成後會在這裡顯示目前牆面、地板與整體氛圍。";
    elements.sceneBackgroundSurfaces.innerHTML = "";
    return;
  }

  const styleId = sceneData.style?.style_id || elements.stylePreference.value || getDefaultStyleId();
  const wallChoice =
    sceneData.design_choices?.wall_option ||
    resolveSurfaceChoice(elements.wallOptionSelect.value, getDefaultSurfaceChoice(styleId, "wall"));
  const floorChoice =
    sceneData.design_choices?.floor_option ||
    resolveSurfaceChoice(elements.floorOptionSelect.value, getDefaultSurfaceChoice(styleId, "floor"));
  const background = sceneData.style?.scene_background || {};
  const wallSurface = getSurfaceById("wall", wallChoice) || getSurfaceById("wall", background.wall_surface_id);
  const floorSurface = getSurfaceById("floor", floorChoice) || getSurfaceById("floor", background.floor_surface_id);

  elements.sceneBackground.textContent = `牆面：${wallSurface?.name_zh || "未指定"} / 地板：${floorSurface?.name_zh || "未指定"} / 整體：${background.overall_zh || "未指定"}`;
  elements.sceneBackgroundDetail.textContent = background.overall_zh
    ? `整體氛圍：${background.overall_zh}`
    : "會依照你選的風格與用材，套用到目前 3D 預覽。";
  elements.sceneBackgroundSurfaces.innerHTML = [renderBackgroundSurfaceCard("wall", wallSurface), renderBackgroundSurfaceCard("floor", floorSurface)].join("");
}

function buildSuccessMessage(sceneData) {
  if (!sceneData) return "已更新 3D 場景。";

  if (sceneData.floorplan?.source === "dxf") {
    const wallCount = sceneData.floorplan.wall_count || 0;
    const doorCount = sceneData.floorplan.door_count || 0;
    const windowCount = sceneData.floorplan.window_count || 0;
    return `DXF 已解析：${wallCount} 面牆、${doorCount} 道門、${windowCount} 扇窗，並完成 3D 場景生成。`;
  }

  return `已生成 ${sceneData.scene_objects?.length || 0} 件家具的 3D 場景。`;
}

async function syncScene(sceneData, statusMessage = "") {
  currentSceneData = sceneData;
  updateRandomButtonLabel();
  renderSummary(sceneData);
  renderBackground(sceneData);
  renderSelectedItems(sceneData);
  await viewer.loadScene(sceneData);
  setStatus(statusMessage || buildSuccessMessage(sceneData));
}

function buildQuestionnairePayload() {
  const styleId = elements.stylePreference.value || getDefaultStyleId();
  const defaultWall = getDefaultSurfaceChoice(styleId, "wall");
  const defaultFloor = getDefaultSurfaceChoice(styleId, "floor");
  const ruleProfile = RULE_PROFILES[elements.ruleProfile.value] || RULE_PROFILES.balanced;
  const presetItems = getCurrentFurniturePreset()?.items || [];
  const preferredColor = elements.colorPreference.value;

  return {
    room_width_cm: Number(elements.roomWidth.value),
    room_depth_cm: Number(elements.roomDepth.value),
    space_type: elements.spaceType.value,
    style_preference: styleId,
    required_furniture: presetItems,
    custom_furniture: splitCustomList(elements.customFurniture.value),
    preferred_colors: preferredColor === "auto" ? [] : [preferredColor],
    custom_colors: [],
    personal_notes: elements.personalNotes.value.trim(),
    keep_window_clear: ruleProfile.keep_window_clear,
    keep_door_clear: ruleProfile.keep_door_clear,
    need_storage: ruleProfile.need_storage,
    prefer_low_saturation: ruleProfile.prefer_low_saturation,
    wall_option: resolveSurfaceChoice(elements.wallOptionSelect.value, defaultWall),
    floor_option: resolveSurfaceChoice(elements.floorOptionSelect.value, defaultFloor),
    furniture_random_seed: furnitureRandomSeed,
    floorplan_filename: elements.floorplan.files?.[0]?.name || null,
    floorplan_dxf_text: uploadedDxfText,
  };
}

async function generateScene(event) {
  event.preventDefault();
  if (sceneBusy) return;

  setBusyState(true, "生成中...");

  try {
    const floorplanFile = elements.floorplan.files?.[0];
    uploadedDxfText = floorplanFile && floorplanFile.name.toLowerCase().endsWith(".dxf")
      ? await floorplanFile.text()
      : null;

    const response = await fetch("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildQuestionnairePayload()),
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result?.detail || `HTTP ${response.status}`);
    }

    await syncScene(result, buildSuccessMessage(result));
    elements.sceneViewerPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    console.error(error);
    setStatus(`生成失敗：${error.message || "請稍後再試。"}`);
  } finally {
    setBusyState(false);
  }
}

async function mutateScene(action, payload = {}, successMessage = "") {
  if (sceneBusy) return false;

  if (!currentSceneData) {
    setStatus("請先生成 3D 場景，再進行家具替換或移除。");
    return false;
  }

  setBusyState(true, "更新中...");

  try {
    const response = await fetch("/api/scene/mutate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        scene_data: currentSceneData,
        random_seed: Date.now(),
        ...payload,
      }),
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result?.detail || `HTTP ${response.status}`);
    }

    await syncScene(result, successMessage || buildSuccessMessage(result));
    return true;
  } catch (error) {
    console.error(error);
    setStatus(`更新失敗：${error.message || "請稍後再試。"}`);
    return false;
  } finally {
    setBusyState(false);
  }
}

function randomizeFurniturePreset() {
  const presets = furniturePresetsForSpace(elements.spaceType.value);
  if (presets.length <= 1) {
    setStatus("目前只有一組可用家具組合。");
    return;
  }

  const currentIndex = presets.findIndex((preset) => preset.value === elements.furniturePreset.value);
  const candidates = presets.filter((_, index) => index !== currentIndex);
  const nextPreset = candidates[Math.floor(Math.random() * candidates.length)];
  if (!nextPreset) return;

  furnitureRandomSeed = Date.now();
  elements.furniturePreset.value = nextPreset.value;
  updateFurniturePresetHint();
  setStatus(`已切換為「${nextPreset.label}」，按下生成後會重新配置家具。`);
}

async function replaceSceneItem(index) {
  const item = currentSceneData?.selected_furniture?.[index];
  if (!item) return;

  await mutateScene(
    "replace",
    { index },
    `已替換家具編號 ${String(index + 1).padStart(2, "0")}，並更新 3D 場景。`
  );
}

async function removeSceneItem(index) {
  const item = currentSceneData?.selected_furniture?.[index];
  if (!item) return;

  await mutateScene(
    "remove",
    { index },
    `已移除「${item.name_zh_raw || formatTypeLabel(item.normalized_type)}」，並重新更新場景。`
  );
}

async function addFurnitureToScene() {
  const selectedType = elements.addFurnitureType.value;
  if (!selectedType) {
    setStatus("請先選擇要加入的家具類型。");
    return;
  }

  await mutateScene(
    "add",
    { item_type: selectedType },
    `已加入 ${formatTypeLabel(selectedType)}，並重新更新 3D 場景。`
  );
}

async function reshuffleCurrentScene() {
  if (currentSceneData?.scene_objects?.length) {
    furnitureRandomSeed = Date.now();
    await mutateScene(
      "reshuffle",
      { random_seed: furnitureRandomSeed },
      `已依 ${getStyleName(currentSceneData.style?.style_id)} 重新抽換同風格家具。`
    );
    return;
  }

  randomizeFurniturePreset();
}

function handleStyleChange() {
  const styleId = elements.stylePreference.value;
  const styleName = getStyleName(styleId);
  const wallSurface = getSurfaceById("wall", getDefaultSurfaceChoice(styleId, "wall"));
  const floorSurface = getSurfaceById("floor", getDefaultSurfaceChoice(styleId, "floor"));
  setStatus(`已切換為 ${styleName}。目前預設牆面為 ${wallSurface?.name_zh || "未指定"}，地板為 ${floorSurface?.name_zh || "未指定"}。`);
}

function handleRuleProfileChange() {
  const ruleProfile = RULE_PROFILES[elements.ruleProfile.value] || RULE_PROFILES.balanced;
  setStatus(ruleProfile.helper);
}

function bindEvents() {
  elements.sceneForm.addEventListener("submit", generateScene);
  elements.spaceType.addEventListener("change", () => {
    renderFurniturePresetSelect();
    setStatus("已切換空間類型，請確認新的家具組合。");
  });
  elements.stylePreference.addEventListener("change", handleStyleChange);
  elements.ruleProfile.addEventListener("change", handleRuleProfileChange);
  elements.furniturePreset.addEventListener("change", () => {
    updateFurniturePresetHint();
    setStatus("已更新家具組合，按下生成後會套用到場景。");
  });

  elements.randomFurniture.addEventListener("click", reshuffleCurrentScene);
  elements.addFurniture.addEventListener("click", addFurnitureToScene);
  elements.reshuffleScene.addEventListener("click", reshuffleCurrentScene);
  elements.resetSceneView.addEventListener("click", () => viewer.resetCamera());

  elements.viewPresetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      viewer.setCameraPreset(button.dataset.viewPreset);
    });
  });

  elements.sceneSelectedItems.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-scene-item-action]");
    if (!button) return;

    const index = Number(button.dataset.index);
    if (!Number.isInteger(index)) return;

    if (button.dataset.sceneItemAction === "replace") {
      await replaceSceneItem(index);
      return;
    }

    if (button.dataset.sceneItemAction === "remove") {
      await removeSceneItem(index);
    }
  });
}

function init() {
  renderStyleSelect();
  renderColorSelect();
  renderWallSelect();
  renderFloorSelect();
  renderAddFurnitureSelect();
  renderFurniturePresetSelect();
  renderProviderStatus();
  renderSelectedItems(null);
  renderBackground(null);
  updateRandomButtonLabel();
  bindEvents();
  initBackgroundFx();
}

init();
