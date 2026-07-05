import { fetchSiteData, initBackgroundFx } from "./common.js?v=20260704e";
import { createSceneViewer } from "./scene_viewer.js?v=20260705m";

const siteData = await fetchSiteData();
const providerStatus = await fetch("/api/scene/provider-status").then((response) => response.json());

const furnitureOptions = [
  { label: "沙發", value: "sofa" },
  { label: "茶几", value: "coffee-table" },
  { label: "電視櫃", value: "tv-bench" },
  { label: "單椅", value: "armchair" },
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

const wallOptions = [
  { id: "auto", label: "依風格推薦", preview: "linear-gradient(135deg, #f5efe6, #dfd3c4)" },
  { id: "warm_white", label: "暖白礦物漆", preview: "linear-gradient(135deg, #fbf6ef, #ece0d2)" },
  { id: "mineral_beige", label: "礦物米灰牆", preview: "linear-gradient(135deg, #d8c6b2, #bca58a)" },
  { id: "light_gray", label: "霧面冷灰牆", preview: "linear-gradient(135deg, #ececee, #d2d4d8)" },
  { id: "limewash", label: "手刷石灰感牆", preview: "linear-gradient(135deg, #ede3d2, #cdbba4)" },
  { id: "charcoal", label: "深灰微水泥牆", preview: "linear-gradient(135deg, #686159, #3f3a36)" },
];

const floorOptions = [
  { id: "auto", label: "依風格推薦", preview: "linear-gradient(135deg, #eadbc6, #c9a77a)" },
  { id: "light_oak", label: "淺橡木木地板", preview: "linear-gradient(135deg, #ead4af, #d3b07f)" },
  { id: "herringbone_oak", label: "人字拼淺木地板", preview: "linear-gradient(135deg, #efd8b3, #bf9566)" },
  { id: "walnut", label: "深胡桃木地板", preview: "linear-gradient(135deg, #9b7452, #5b3e28)" },
  { id: "stone_gray", label: "霧面石紋灰磚", preview: "linear-gradient(135deg, #ddd7d2, #b7b3b0)" },
  { id: "marble", label: "亮面大理石地磚", preview: "linear-gradient(135deg, #f7f5ef, #cfc8bd 52%, #f4efe7)" },
  { id: "microcement", label: "微水泥無縫地坪", preview: "linear-gradient(135deg, #d1cbc3, #a39c93)" },
];

const DEFAULT_FURNITURE_BY_SPACE = {
  living_room: ["sofa", "coffee-table", "tv-bench", "armchair"],
  bedroom: ["bed", "bedside-table", "bookcase"],
  workspace: ["desk", "office-chair", "bookcase"],
  dining_room: ["dining-table", "dining-chair", "sideboard"],
  studio: ["sofa", "coffee-table", "desk", "bookcase"],
};

const wallOptionLabelMap = new Map(wallOptions.map((option) => [option.id, option.label]));
const floorOptionLabelMap = new Map(floorOptions.map((option) => [option.id, option.label]));
const furnitureLabelMap = new Map(furnitureOptions.map((option) => [option.value, option.label]));

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

const STYLE_SCENE_LOOKS = {
  scandinavian: { wall: "warm_white", floor: "light_oak" },
  modern: { wall: "light_gray", floor: "stone_gray" },
  minimalist_muji: { wall: "warm_white", floor: "light_oak" },
  nordic_modern: { wall: "light_gray", floor: "light_oak" },
  industrial: { wall: "charcoal", floor: "microcement" },
  wabi_sabi: { wall: "limewash", floor: "microcement" },
  melad: { wall: "mineral_beige", floor: "walnut" },
  american: { wall: "warm_white", floor: "walnut" },
  american_country: { wall: "warm_white", floor: "light_oak" },
  light_luxury: { wall: "light_gray", floor: "marble" },
  classical: { wall: "mineral_beige", floor: "walnut" },
  eclectic: { wall: "warm_white", floor: "light_oak" },
};

function renderStyleOptions() {
  elements.stylePreference.innerHTML = siteData.styles
    .map((style) => `<option value="${style.style_id}">${style.style_name_zh}</option>`)
    .join("");

  if (siteData.styles.some((style) => style.style_id === "scandinavian")) {
    elements.stylePreference.value = "scandinavian";
  }
}

function renderToggleOptions(container, options, name) {
  container.innerHTML = options
    .map(
      (option) => `
        <label class="scene-option">
          <input type="checkbox" name="${name}" value="${option.value || option}" />
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

function renderVisualOptions(container, options, name) {
  container.innerHTML = options
    .map(
      (option, index) => `
        <label class="scene-visual-option">
          <input type="radio" name="${name}" value="${option.id}" ${index === 0 ? "checked" : ""} />
          <span class="scene-visual-swatch" style="background:${option.preview}"></span>
          <span class="scene-visual-label">${option.label}</span>
        </label>
      `
    )
    .join("");
}

function selectedValues(container) {
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
}

function selectedRadio(container, name) {
  return container.querySelector(`input[name="${name}"]:checked`)?.value || "auto";
}

function getTypeLabel(type) {
  return furnitureLabelMap.get(type) || type || "家具";
}

function setRadioValue(container, name, value) {
  const target = container.querySelector(`input[name="${name}"][value="${value}"]`);
  if (target) target.checked = true;
}

function getStyleSceneLook(styleId = elements.stylePreference.value) {
  return STYLE_SCENE_LOOKS[styleId] || STYLE_SCENE_LOOKS.scandinavian;
}

function getResolvedSurfaceChoice(container, name, fallbackValue) {
  const value = selectedRadio(container, name);
  return value === "auto" ? fallbackValue : value;
}

function syncSurfaceChoicesToStyle() {
  const sceneLook = getStyleSceneLook();
  setRadioValue(elements.wallOptions, "wall-option", sceneLook.wall);
  setRadioValue(elements.floorOptions, "floor-option", sceneLook.floor);
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

function splitCustomText(value) {
  return value
    .split(/[,\u3001\uff0c]/)
    .map((item) => item.trim())
    .filter(Boolean);
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
    item.style_candidates?.some((style) => style.style_id === styleId)
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

function rotatedFootprint(width, depth, rotation) {
  const radians = Math.abs(rotation % 180) * Math.PI / 180;
  const cosValue = Math.abs(Math.cos(radians));
  const sinValue = Math.abs(Math.sin(radians));
  return {
    width: width * cosValue + depth * sinValue,
    depth: width * sinValue + depth * cosValue,
  };
}

function clampAxis(value, roomMin, roomMax, itemSize, margin = 18) {
  const low = roomMin + itemSize / 2 + margin;
  const high = roomMax - itemSize / 2 - margin;
  if (low > high) return (roomMin + roomMax) / 2;
  return Math.min(Math.max(value, low), high);
}

function boxFor(x, z, width, depth, clearance = 14) {
  return {
    left: x - width / 2 - clearance,
    right: x + width / 2 + clearance,
    top: z - depth / 2 - clearance,
    bottom: z + depth / 2 + clearance,
  };
}

function overlapArea(a, b) {
  const overlapX = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const overlapZ = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return overlapX * overlapZ;
}

function placementCandidates(type, size, room) {
  const left = -room.width / 2;
  const right = room.width / 2;
  const top = -room.depth / 2;
  const bottom = room.depth / 2;
  const candidates = [];
  const width = size.width;
  const depth = size.depth;

  if (type === "tv-bench") candidates.push([0, top + depth / 2 + 24, 0], [-room.width * 0.22, top + depth / 2 + 24, 0]);
  else if (type === "sofa") candidates.push([0, bottom - depth / 2 - 36, 180], [-room.width * 0.18, bottom - depth / 2 - 36, 180]);
  else if (type === "coffee-table") candidates.push([0, 12, 0], [0, -18, 0]);
  else if (type === "armchair") candidates.push([right - width / 2 - 30, 35, -35], [left + width / 2 + 30, 35, 35]);
  else if (type === "bookcase") candidates.push([left + width / 2 + 20, top + depth / 2 + 20, 90], [right - width / 2 - 20, top + depth / 2 + 20, -90]);
  else if (["bed", "bed-frame", "sofa-bed"].includes(type)) candidates.push([0, bottom - depth / 2 - 32, 180], [left + width / 2 + 28, 0, 90]);
  else if (type === "bedside-table") candidates.push([right - width / 2 - 22, bottom - depth / 2 - 34, 0], [left + width / 2 + 22, bottom - depth / 2 - 34, 0]);
  else if (type === "desk") candidates.push([0, top + depth / 2 + 30, 0], [left + width / 2 + 24, 0, 90]);
  else if (type === "office-chair") candidates.push([0, top + depth + 88, 180], [left + width / 2 + 80, 0, 90]);
  else if (type === "dining-table") candidates.push([0, 0, 0], [0, 36, 0]);
  else if (type === "dining-chair") candidates.push([right - width / 2 - 40, 0, 90], [left + width / 2 + 40, 0, -90], [0, 80, 180]);
  else if (type === "sideboard") candidates.push([right - width / 2 - 24, top + depth / 2 + 24, 0], [left + width / 2 + 24, top + depth / 2 + 24, 0]);
  else candidates.push([0, 0, 0]);

  [0.25, 0.5, 0.75].forEach((xRatio) => {
    [0.28, 0.5, 0.72].forEach((zRatio) => {
      candidates.push([left + room.width * xRatio, top + room.depth * zRatio, 0]);
    });
  });

  return candidates;
}

function resolvePlacementForObject(object, placedBoxes, room) {
  const type = object.normalized_type;
  const size = normalizeSizeCm(object.size_cm);
  const ignoresCollision = ["large-medium-rug", "runner-small-rug", "wall-shelf"].includes(type);
  const left = -room.width / 2;
  const right = room.width / 2;
  const top = -room.depth / 2;
  const bottom = room.depth / 2;
  let best = null;

  for (const [rawX, rawZ, rotation] of placementCandidates(type, size, room)) {
    const footprint = rotatedFootprint(size.width, size.depth, rotation);
    const x = clampAxis(rawX, left, right, footprint.width);
    const z = clampAxis(rawZ, top, bottom, footprint.depth);
    const candidateBox = boxFor(x, z, footprint.width, footprint.depth);
    const overlapScore = placedBoxes.reduce((sum, box) => sum + overlapArea(candidateBox, box), 0);

    if (ignoresCollision || overlapScore <= 0) {
      return { x, z, rotation, box: candidateBox };
    }

    if (!best || overlapScore < best.score) {
      best = { x, z, rotation, box: candidateBox, score: overlapScore };
    }
  }

  return best || { x: 0, z: 0, rotation: 0, box: boxFor(0, 0, size.width, size.depth) };
}

function reflowSceneObjects(sceneData) {
  const room = {
    width: Math.max(Number(sceneData.floorplan.width_cm) || 420, 240),
    depth: Math.max(Number(sceneData.floorplan.depth_cm) || 360, 240),
  };
  const placedBoxes = [];

  sceneData.scene_objects.forEach((object) => {
    const placement = resolvePlacementForObject(object, placedBoxes, room);
    object.position_cm = { x: Math.round(placement.x * 100) / 100, z: Math.round(placement.z * 100) / 100 };
    object.rotation_y_deg = placement.rotation;
    object.footprint_cm = {
      width: Math.round((placement.box.right - placement.box.left) * 100) / 100,
      depth: Math.round((placement.box.bottom - placement.box.top) * 100) / 100,
    };

    if (!["large-medium-rug", "runner-small-rug", "wall-shelf"].includes(object.normalized_type)) {
      placedBoxes.push(placement.box);
    }
  });
}

function sceneObjectFromFurniture(item) {
  return {
    furniture_id: item.furniture_id,
    name_zh_raw: item.name_zh_raw,
    normalized_type: item.normalized_type,
    model_url: item.model_url,
    primary_style: item.primary_style,
    size_cm: normalizeSizeCm(item.size_cm),
    position_cm: { x: 0, z: 0 },
    rotation_y_deg: 0,
  };
}

async function refreshCurrentScene(statusMessage = "") {
  if (!currentSceneData) return;
  updateSummary(currentSceneData);
  await viewer.loadScene(currentSceneData);
  if (statusMessage) {
    elements.sceneStatus.textContent = statusMessage;
  }
}

function setGeneratingState(active) {
  elements.generateScene.disabled = active;
  elements.generateScene.textContent = active ? "生成中..." : "直接生成 3D 場景";
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

  const primaryPool = preferredTypes.length
    ? allInputs.filter((input) => preferredTypes.includes(input.value))
    : allInputs;

  const desiredCount = Math.min(Math.max(3, Math.floor(Math.random() * 4) + 3), allInputs.length);
  const picked = sampleRandom(primaryPool, Math.min(desiredCount, primaryPool.length));

  if (picked.length < desiredCount) {
    const remaining = allInputs.filter((input) => !picked.includes(input));
    picked.push(...sampleRandom(remaining, desiredCount - picked.length));
  }

  picked.forEach((input) => {
    input.checked = true;
  });

  const currentStyleName = siteData.styles.find((style) => style.style_id === currentStyleId)?.style_name_zh || "目前風格";
  elements.sceneStatus.textContent = `已在「${currentStyleName}」內隨機挑選 ${picked.length} 項家具。再次生成會更換同風格候選模型。`;
}

function renderSelectedItems(sceneData) {
  elements.sceneSelectedItems.innerHTML = "";
  if (!sceneData.scene_objects.length) {
    elements.sceneSelectedItems.innerHTML = `<p class="scene-selected-empty">目前尚未選入家具。</p>`;
    return;
  }

  sceneData.scene_objects.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "scene-selected-item";
    row.innerHTML = `
      <span class="scene-selected-index">${index + 1}</span>
      <div class="scene-selected-copy">
        <strong>${item.name_zh_raw || item.normalized_type}</strong>
        <small>${getTypeLabel(item.normalized_type)} · ${item.size_cm?.width || "-"} × ${item.size_cm?.depth || "-"} × ${item.size_cm?.height || "-"} cm</small>
      </div>
      <div class="scene-selected-actions">
        <button type="button" data-furniture-action="replace" data-index="${index}">替換</button>
        <button type="button" data-furniture-action="remove" data-index="${index}">移除</button>
      </div>
    `;
    elements.sceneSelectedItems.appendChild(row);
  });
}

function updateSummary(sceneData) {
  elements.sceneStyleName.textContent = sceneData.style.style_name_zh;
  elements.sceneLlmMode.textContent = sceneData.llm_mode === "openrouter" ? "OpenRouter" : "本地規則";
  elements.sceneItemCount.textContent = String(sceneData.scene_objects.length);
  elements.sceneRoomSize.textContent = `${sceneData.floorplan.width_cm} × ${sceneData.floorplan.depth_cm} cm`;

  const background = sceneData.style.scene_background || {};
  const wallChoice = sceneData.design_choices?.wall_option || getResolvedSurfaceChoice(
    elements.wallOptions,
    "wall-option",
    getStyleSceneLook(sceneData.style.style_id).wall
  );
  const floorChoice = sceneData.design_choices?.floor_option || getResolvedSurfaceChoice(
    elements.floorOptions,
    "floor-option",
    getStyleSceneLook(sceneData.style.style_id).floor
  );
  elements.sceneBackground.textContent = [
    `牆面：${wallOptionLabelMap.get(wallChoice) || background.wall_zh || "依風格推薦"}`,
    `地板：${floorOptionLabelMap.get(floorChoice) || background.floor_zh || "依風格推薦"}`,
    background.overall_zh ? `整體：${background.overall_zh}` : "",
  ]
    .filter(Boolean)
    .join(" / ");

  renderSelectedItems(sceneData);
  if (sceneData.floorplan?.source === "dxf") {
    const wallCount = sceneData.floorplan.wall_count || 0;
    const doorCount = sceneData.floorplan.door_count || 0;
    const windowCount = sceneData.floorplan.window_count || 0;
    const rawCount = sceneData.floorplan.raw_segment_count || 0;
    elements.sceneStatus.textContent = `DXF 精準模式：已讀取 ${rawCount} 條 CAD 線段，轉成 ${wallCount} 道牆、${doorCount} 組門線、${windowCount} 組窗線並生成場景。`;
  }
}

function renderInitialProviderStatus() {
  if (providerStatus.enabled) {
    elements.sceneLlmMode.textContent = providerStatus.model
      ? `OpenRouter / ${providerStatus.model}`
      : "OpenRouter";
    elements.sceneStatus.textContent = "已偵測到 OpenRouter 設定，現在會優先使用 LLM 生成場景規劃。";
    return;
  }

  elements.sceneLlmMode.textContent = "本地規則 fallback";
  elements.sceneStatus.textContent = "尚未設定 OpenRouter 金鑰，現在先使用本地規則生成場景。";
}

async function generateScene(event) {
  event.preventDefault();
  setGeneratingState(true);

  try {
    const floorplanFile = elements.floorplan.files?.[0];
    if (floorplanFile && floorplanFile.name.toLowerCase().endsWith(".dxf")) {
      uploadedDxfText = await floorplanFile.text();
    } else {
      uploadedDxfText = null;
    }
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
      wall_option: getResolvedSurfaceChoice(elements.wallOptions, "wall-option", getStyleSceneLook().wall),
      floor_option: getResolvedSurfaceChoice(elements.floorOptions, "floor-option", getStyleSceneLook().floor),
      furniture_random_seed: furnitureRandomSeed,
    };

    const response = await fetch("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const sceneData = await response.json();
    currentSceneData = sceneData;
    reflowSceneObjects(currentSceneData);
    await refreshCurrentScene();
  } catch (error) {
    console.error(error);
    elements.sceneStatus.textContent = "場景生成失敗，請檢查欄位或稍後再試。";
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
    elements.sceneStatus.textContent = `目前找不到可替換的「${getTypeLabel(currentItem.normalized_type)}」模型。`;
    return;
  }

  currentSceneData.scene_objects[index] = sceneObjectFromFurniture(replacement);
  reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已替換第 ${index + 1} 件家具，並重新整理擺放位置避免穿牆或重疊。`);
}

async function removeSceneItem(index) {
  if (!currentSceneData?.scene_objects?.[index]) return;
  const removed = currentSceneData.scene_objects.splice(index, 1)[0];
  reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已移除「${removed.name_zh_raw || getTypeLabel(removed.normalized_type)}」。`);
}

async function addFurnitureToScene() {
  if (!currentSceneData) {
    elements.sceneStatus.textContent = "請先生成一次 3D 場景，再新增家具。";
    return;
  }

  const type = elements.addFurnitureType.value;
  const usedIds = new Set(currentSceneData.scene_objects.map((item) => item.furniture_id));
  const candidate = pickFurnitureCandidate(type, usedIds);

  if (!candidate) {
    elements.sceneStatus.textContent = `目前資料庫找不到可加入的「${getTypeLabel(type)}」模型。`;
    return;
  }

  currentSceneData.scene_objects.push(sceneObjectFromFurniture(candidate));
  reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已加入「${getTypeLabel(type)}」，並重新分配位置。`);
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
  reflowSceneObjects(currentSceneData);
  await refreshCurrentScene("已在目前風格內整組重抽家具，並重新避牆避重疊。");
}

renderStyleOptions();
renderToggleOptions(elements.furnitureOptions, furnitureOptions, "furniture");
renderToggleOptions(elements.colorOptions, colorOptions, "color");
renderVisualOptions(elements.wallOptions, wallOptions, "wall-option");
renderVisualOptions(elements.floorOptions, floorOptions, "floor-option");
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

  if (button.dataset.furnitureAction === "replace") {
    replaceSceneItem(index);
  } else if (button.dataset.furnitureAction === "remove") {
    removeSceneItem(index);
  }
});
elements.stylePreference.addEventListener("change", () => {
  syncSurfaceChoicesToStyle();
  furnitureRandomSeed = Date.now();
  elements.sceneStatus.textContent = `已固定為「${elements.stylePreference.selectedOptions[0]?.textContent || "目前風格"}」，牆面與地板已套用推薦組合。`;
});
elements.spaceType.addEventListener("change", setDefaultFurnitureBySpace);
elements.resetSceneView.addEventListener("click", () => viewer.resetCamera());
elements.viewPresetButtons.forEach((button) => {
  button.addEventListener("click", () => viewer.setCameraPreset(button.dataset.viewPreset));
});

initBackgroundFx();
