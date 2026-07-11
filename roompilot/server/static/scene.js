import { fetchSiteData, initBackgroundFx } from "./common.js?v=20260704e";
import { createSceneViewer } from "./scene_viewer.js?v=20260709a";

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
  multiProposal: document.getElementById("multi-proposal"),
  scaleCalibration: document.getElementById("scale-calibration"),
  calibrationCanvas: document.getElementById("calibration-canvas"),
  calibrationLength: document.getElementById("calibration-length"),
  applyCalibration: document.getElementById("apply-calibration"),
  resetCalibration: document.getElementById("reset-calibration"),
  calibrationStatus: document.getElementById("calibration-status"),
  proposalRow: document.getElementById("proposal-row"),
  proposalTabs: document.getElementById("proposal-tabs"),
  styleChips: document.getElementById("style-chips"),
  keepDoorClear: document.getElementById("keep-door-clear"),
  needStorage: document.getElementById("need-storage"),
  preferLowSaturation: document.getElementById("prefer-low-saturation"),
  generateScene: document.getElementById("generate-scene"),
  randomFurniture: document.getElementById("random-furniture"),
  resetSceneView: document.getElementById("reset-scene-view"),
  openPanorama: document.getElementById("open-panorama"),
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

// ── F2a 手動拉比例(兩點標定)+ 多方案 狀態 ──
let floorplanScaleM = null;      // 校正後的全圖跨距(公尺);null = 交給解析器自動猜
let calibrationParsed = null;    // /api/upload 回來的解析結果(目前比例下的公尺座標)
let calibrationPoints = [];      // 使用者點的兩個世界座標點
let calibrationTransform = null; // 畫布 ↔ 世界座標轉換
let proposals = [];              // 多方案:同條件不同 seed 的場景陣列
let activeProposalIndex = 0;

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

async function reflowSceneObjects(sceneData) {
  // 擺放座標一律由後端 furniture_engine 計算(碰撞 + 淨空,Shapely 驗證)。
  // 失敗時保留原座標,場景仍可顯示。
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
    if (Array.isArray(data.scene_objects)) {
      sceneData.scene_objects = data.scene_objects;
    }
  } catch (error) {
    console.warn("後端擺放引擎呼叫失敗，保留現有座標。", error);
  }
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

// ── F2a 手動拉比例:上傳 DXF → 預覽 → 點兩點 → 輸入實際公分 → 覆寫比例 ──

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

// ── 多方案(方案 A/B/C)與風格套系切換 ──

const PROPOSAL_LABELS = ["方案 A", "方案 B", "方案 C"];

function renderProposalTabs() {
  elements.proposalTabs.innerHTML = "";
  elements.proposalRow.hidden = proposals.length <= 1;
  proposals.forEach((_, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `secondary-action${index === activeProposalIndex ? " prominent" : ""}`;
    button.textContent = PROPOSAL_LABELS[index] || `方案 ${index + 1}`;
    button.addEventListener("click", () => switchProposal(index));
    elements.proposalTabs.appendChild(button);
  });
}

async function switchProposal(index) {
  if (!proposals[index]) return;
  activeProposalIndex = index;
  currentSceneData = proposals[index];
  renderProposalTabs();
  await refreshCurrentScene(`已切換到${PROPOSAL_LABELS[index] || `方案 ${index + 1}`}。`);
}

function renderStyleChips() {
  elements.styleChips.innerHTML = "";
  siteData.styles.forEach((style) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `style-chip${style.style_id === elements.stylePreference.value ? " active" : ""}`;
    button.textContent = style.style_name_zh;
    button.addEventListener("click", () => switchStyle(style.style_id));
    elements.styleChips.appendChild(button);
  });
}

async function switchStyle(styleId) {
  elements.stylePreference.value = styleId;
  syncSurfaceChoicesToStyle();
  renderStyleChips();
  if (!currentSceneData) {
    elements.sceneStatus.textContent = `已選「${siteData.styles.find((style) => style.style_id === styleId)?.style_name_zh || styleId}」,按生成即可看擺位。`;
    return;
  }
  // 同一張戶型、同一組 seed,只換風格 → 展示「不同風格、不同擺位」
  await runGenerate({ keepSeed: true });
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

async function collectGeneratePayload() {
  const floorplanFile = elements.floorplan.files?.[0];
  if (floorplanFile && floorplanFile.name.toLowerCase().endsWith(".dxf")) {
    if (!uploadedDxfText) uploadedDxfText = await floorplanFile.text();
  } else {
    uploadedDxfText = null;
  }
  return {
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
    floorplan_scale_m: floorplanScaleM,
    wall_option: getResolvedSurfaceChoice(elements.wallOptions, "wall-option", getStyleSceneLook().wall),
    floor_option: getResolvedSurfaceChoice(elements.floorOptions, "floor-option", getStyleSceneLook().floor),
    furniture_random_seed: furnitureRandomSeed,
  };
}

async function fetchScene(payload) {
  const response = await fetch("/api/scene/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function runGenerate({ keepSeed = false } = {}) {
  setGeneratingState(true);
  try {
    if (!keepSeed) furnitureRandomSeed = furnitureRandomSeed || Date.now();
    const basePayload = await collectGeneratePayload();

    // 多方案:同條件不同 seed,對標 AiHouse「AI 佈局候選」;關掉就是單方案
    const seeds = elements.multiProposal.checked
      ? [furnitureRandomSeed, furnitureRandomSeed + 1, furnitureRandomSeed + 2]
      : [furnitureRandomSeed];
    const results = await Promise.all(
      seeds.map((seed) => fetchScene({ ...basePayload, furniture_random_seed: seed }))
    );

    proposals = results;
    activeProposalIndex = 0;
    currentSceneData = proposals[0];
    renderProposalTabs();
    renderStyleChips();
    await refreshCurrentScene();

    // 勾了卻沒出現的家具要說清楚:型號缺貨(該風格無模型)或空間放不下
    const placement = currentSceneData.placement || {};
    const notes = [];
    if (placement.unavailable_types?.length) {
      notes.push(`此風格找不到可用模型：${placement.unavailable_types.map(getTypeLabel).join("、")}`);
    }
    if (placement.failed?.length) {
      notes.push(`空間放不下：${placement.failed.map((f) => f.name || getTypeLabel(f.type)).join("、")}`);
    }
    if (proposals.length > 1) {
      notes.unshift(`已生成 ${proposals.length} 個佈局方案,上方分頁可切換比較`);
    }
    if (notes.length) {
      elements.sceneStatus.textContent = `${elements.sceneStatus.textContent} ${notes.join("；")}`;
    }
  } catch (error) {
    console.error(error);
    elements.sceneStatus.textContent = "場景生成失敗，請檢查欄位或稍後再試。";
  } finally {
    setGeneratingState(false);
  }
}

async function generateScene(event) {
  event.preventDefault();
  await runGenerate();
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
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene(`已替換第 ${index + 1} 件家具，並重新整理擺放位置避免穿牆或重疊。`);
}

async function removeSceneItem(index) {
  if (!currentSceneData?.scene_objects?.[index]) return;
  const removed = currentSceneData.scene_objects.splice(index, 1)[0];
  await reflowSceneObjects(currentSceneData);
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
  await reflowSceneObjects(currentSceneData);
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
  await reflowSceneObjects(currentSceneData);
  await refreshCurrentScene("已在目前風格內整組重抽家具，並重新避牆避重疊。");
}

renderStyleOptions();
renderStyleChips();
renderToggleOptions(elements.furnitureOptions, furnitureOptions, "furniture");
renderToggleOptions(elements.colorOptions, colorOptions, "color");
renderVisualOptions(elements.wallOptions, wallOptions, "wall-option");
renderVisualOptions(elements.floorOptions, floorOptions, "floor-option");
renderAddFurnitureSelect();
syncSurfaceChoicesToStyle();
setDefaultFurnitureBySpace();
renderInitialProviderStatus();

elements.sceneForm.addEventListener("submit", generateScene);
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
  renderStyleChips();
  furnitureRandomSeed = Date.now();
  elements.sceneStatus.textContent = `已固定為「${elements.stylePreference.selectedOptions[0]?.textContent || "目前風格"}」，牆面與地板已套用推薦組合。`;
});
elements.spaceType.addEventListener("change", setDefaultFurnitureBySpace);
elements.resetSceneView.addEventListener("click", () => viewer.resetCamera());
elements.openPanorama.addEventListener("click", () => {
  // 交棒目前場景給環景頁;沒生成過就讓環景頁自己做示範場景
  if (currentSceneData) {
    sessionStorage.setItem("roompilot.panorama.scene", JSON.stringify(currentSceneData));
  } else {
    sessionStorage.removeItem("roompilot.panorama.scene");
  }
  window.open("/panorama", "_blank");
});
elements.viewPresetButtons.forEach((button) => {
  button.addEventListener("click", () => viewer.setCameraPreset(button.dataset.viewPreset));
});

initBackgroundFx();
