// scene_lab.js — 2D+3D 合併工作台實驗（M0：唯讀檢視器）
//
// 定位：feat/scene-2d3d-lab 實驗分支的獨立入口，不改動 scene_v2.js／scene.html。
// M0 僅讀取：GET /api/projects/{id} 與 floorplan/source，不寫入 project store。
// 擺位合法性永遠屬於引擎（/api/scene/layout、/api/scene/validate）；本檔零擺位演算法。
import * as THREE from "three";
import { createSceneViewer } from "./scene_viewer.js?v=sha256-pickfix7-nocolor";

// viewer 沒有單件增刪 API，任何場景變更都得整場 loadScene 重建；
// 開啟 three 的全域檔案快取，讓重載時 GLB 不再重新下載（解析仍會發生）。
THREE.Cache.enabled = true;
import {
  planCmToLayerPixel,
  furnitureFootprintStyle,
  findFurniture2DVariant,
} from "./scene_layout2d.js?v=sha256-1be57ed527b7";
import {
  normalizeSavedSceneData,
  normalizeSavedSpaceConfirmation,
} from "./scene_unit_contracts.js?v=sha256-88f874e652a8";

const FALLBACK_ICON = "M6 6h36v36H6z";

const $ = (selector) => document.querySelector(selector);

const element = {
  projectForm: $("#lab-project-form"),
  projectInput: $("#lab-project-id"),
  projectName: $("#lab-project-name"),
  stepSummary: $("#lab-step-summary"),
  notice: $("#lab-notice"),
  viewer: $("#lab-viewer"),
  viewerStatus: $("#lab-viewer-status"),
  panel: $("#lab-plan-panel"),
  panelToggle: $("#lab-plan-toggle"),
  planImage: $("#lab-plan-image"),
  planLayer: $("#lab-plan-layer"),
  furnitureList: $("#lab-furniture-list"),
  roomList: $("#lab-room-list"),
  viewButtons: document.querySelectorAll("[data-lab-view]"),
  modeButtons: document.querySelectorAll("[data-lab-mode]"),
  libraryForm: $("#lab-library-form"),
  libraryType: $("#lab-library-type"),
  libraryStyle: $("#lab-library-style"),
  libraryQ: $("#lab-library-q"),
  libraryResults: $("#lab-library-results"),
};

const state = {
  projectId: new URLSearchParams(location.search).get("project") || "",
  workflow: null,
  geometry: null,
  rooms: [],
  furniture2d: [],
  sceneData: null,
  selectedId: null,
  libraryResults: [],
};

// 唯一的 viewer 實例：createSceneViewer 沒有 dispose()，整頁只建一次。
// onSceneChange 只在引擎驗證成功的移動/旋轉後觸發；把新座標同步回 2D 面板。
const viewer = createSceneViewer(element.viewer, element.viewerStatus, {
  onSceneChange: (sceneItem) => {
    syncFurnitureFromScene(sceneItem);
    renderPlanFurniture();
  },
});
// 預設編輯模式：拖家具＝移動（引擎驗證），拖空白處＝轉鏡頭。
// 注意：viewer.setViewMode() 會把互動模式重設回 camera，
// 所以每次切視角後都要重新套用（走路視角除外，那是它自己的互動模式）。
state.interactionMode = "edit";

function applyInteractionMode() {
  viewer.setInteractionMode(state.interactionMode);
  // 上游的編輯模式會鎖死鏡頭（只能縮放）；解鎖後拖家具照常、拖空白處轉視角。
  if (state.interactionMode === "edit") viewer.lockRenderCamera(false);
  element.modeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.labMode === state.interactionMode);
  });
}

// 上游微調面板的 15° 旋轉鈕已被 CSS 隱藏（normalizedRotationDeg 吸附 90° 使其無效），
// 補一顆走同一驗證路徑但用 90° 的旋轉鈕。
const adjustGrid = element.viewer.querySelector(".scene-object-controls-grid");
if (adjustGrid) {
  const rotateButton = document.createElement("button");
  rotateButton.type = "button";
  rotateButton.textContent = "旋轉 90°";
  rotateButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    viewer.rotateSelected(90);
  });
  adjustGrid.appendChild(rotateButton);

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.textContent = "移除此件";
  removeButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    removeSelectedFurniture();
  });
  adjustGrid.appendChild(removeButton);
}

async function reloadViewerPreservingCamera() {
  const cameraState = viewer.getCameraState();
  await viewer.loadScene(state.sceneData);
  viewer.setCameraState(cameraState);
  applyInteractionMode();
}

function selectedPair() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedId);
  if (!item) return null;
  const sceneObject = (state.sceneData?.scene_objects || []).find(
    (candidate) => candidate.furniture_id === item.sceneObjectId,
  );
  return sceneObject ? { item, sceneObject } : null;
}

async function validateCandidate(candidate, excludeId) {
  const response = await fetch("/api/scene/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan: state.sceneData?.floorplan || null,
      item: candidate,
      others: (state.sceneData?.scene_objects || []).filter(
        (other) => other.furniture_id !== excludeId,
      ),
    }),
  });
  if (!response.ok) return { ok: false, reason: `驗證服務錯誤 HTTP ${response.status}` };
  return response.json();
}

async function removeSelectedFurniture() {
  const pair = selectedPair();
  if (!pair) { setNotice("請先選取一件家具。", "warn"); return; }
  state.sceneData.scene_objects = state.sceneData.scene_objects.filter(
    (candidate) => candidate.furniture_id !== pair.sceneObject.furniture_id,
  );
  state.furniture2d = state.furniture2d.filter((candidate) => candidate.id !== pair.item.id);
  state.selectedId = null;
  await reloadViewerPreservingCamera();
  renderPlanFurniture();
  setNotice(`已移除「${pair.item.label}」（僅本頁，不寫回專案）。`);
}

function syncFurnitureFromScene(sceneItem) {
  if (!sceneItem) return;
  const match = state.furniture2d.find(
    (candidate) => candidate.sceneObjectId === sceneItem.furniture_id,
  );
  if (!match) return;
  match.xCm = Number(sceneItem.position_cm?.x) || 0;
  match.yCm = Number(sceneItem.position_cm?.z) || 0;
  match.rotationDeg = Number(sceneItem.rotation_y_deg) || 0;
  match.placementFailed = sceneItem.placement_failed === true;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function setNotice(message, tone = "info") {
  element.notice.textContent = message || "";
  element.notice.dataset.tone = tone;
  element.notice.hidden = !message;
}

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      detail = body?.detail?.message || body?.detail || detail;
    } catch { /* 非 JSON 回應時保留狀態碼 */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json();
}

// 對齊 scene_v2.js planGeometry()/planCenterCm()：以辨識結果的 bbox 與比例為準。
function planGeometryFrom(analysis, image) {
  const imageWidth = analysis?.image_size_px?.width || image.naturalWidth || 1000;
  const imageHeight = analysis?.image_size_px?.height || image.naturalHeight || 1000;
  const scale = Number(analysis?.scale?.cm_per_px)
    || Number(analysis?.scale?.m_per_px) * 100
    || 1;
  const bbox = analysis?.plan_bbox_px || [0, 0, imageWidth, imageHeight];
  return { imageWidth, imageHeight, scale, bbox };
}

function planCenterCm(geometry) {
  return {
    x: (geometry.bbox[2] - geometry.bbox[0]) * geometry.scale / 2,
    y: (geometry.bbox[3] - geometry.bbox[1]) * geometry.scale / 2,
  };
}

function planPixelsPerCm() {
  const image = element.planImage;
  if (!image.naturalWidth) return 0;
  return (1 / state.geometry.scale) * (image.clientWidth / image.naturalWidth);
}

function iconPathFor(item) {
  if (item.iconPath) return item.iconPath;
  const match = findFurniture2DVariant(item.type, item.variantId);
  if (match) return match.selected.iconPath;
  const alias = ["sofa", "bed", "desk", "chair", "table", "wardrobe", "cabinet", "tv-bench"]
    .find((keyword) => String(item.type || "").includes(keyword));
  return findFurniture2DVariant(alias, null)?.selected?.iconPath || FALLBACK_ICON;
}

function activeSchemeFurniture(workflow) {
  const layout = workflow.layout_2d || {};
  const activeId = workflow.space_confirmation?.design_schemes?.active_scheme_id
    || workflow.design_schemes?.active_scheme_id
    || "A";
  const schemeFurniture = layout.schemes?.[activeId]?.furniture;
  if (Array.isArray(schemeFurniture) && schemeFurniture.length) return schemeFurniture;
  return Array.isArray(layout.furniture) ? layout.furniture : [];
}

function sceneObjectIndexFor(item) {
  const objects = state.sceneData?.scene_objects || [];
  const byId = objects.findIndex(
    (candidate) => candidate.furniture_id === item.id
      || candidate.furniture_id === item.catalogFurnitureId,
  );
  if (byId >= 0) return byId;
  return objects.findIndex(
    (candidate) => candidate.normalized_type === item.type
      && Math.abs(Number(candidate.position_cm?.x) - item.xCm) < 1
      && Math.abs(Number(candidate.position_cm?.z) - item.yCm) < 1,
  );
}

function selectFurniture(id, { focus = false } = {}) {
  state.selectedId = id;
  renderPlanFurniture();
  const item = state.furniture2d.find((candidate) => candidate.id === id);
  if (!item) return;
  const index = sceneObjectIndexFor(item);
  if (index >= 0) viewer.selectObjectByIndex(index, { focus });
}

function renderPlanFurniture() {
  if (!element.planImage.naturalWidth || !state.geometry) return;
  const pixelsPerCm = planPixelsPerCm();
  const center = planCenterCm(state.geometry);
  element.planLayer.innerHTML = state.furniture2d.map((item) => {
    const pixel = planCmToLayerPixel(
      { x: center.x + item.xCm, y: center.y + item.yCm },
      state.geometry,
      pixelsPerCm,
    );
    const style = furnitureFootprintStyle(item, pixelsPerCm);
    const classes = [
      "lab-furniture",
      item.id === state.selectedId ? "is-active" : "",
      item.placementFailed === true ? "is-invalid" : "",
    ].join(" ");
    return `
      <button type="button" class="${classes}" data-lab-furniture="${escapeHtml(item.id)}"
        title="${escapeHtml(item.label)} ${item.widthCm}×${item.depthCm}cm"
        style="left:${pixel.x}px;top:${pixel.y}px;width:${style.width};height:${style.height};transform:${style.transform}">
        <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(iconPathFor(item))}"/></svg>
      </button>
    `;
  }).join("");
  element.furnitureList.innerHTML = state.furniture2d.map((item) => `
    <button type="button" class="${item.id === state.selectedId ? "is-active" : ""}"
      data-lab-furniture="${escapeHtml(item.id)}">
      <strong>${escapeHtml(item.label)}</strong>
      <small>${item.widthCm} × ${item.depthCm} cm${item.placementFailed ? "・未合法" : ""}</small>
    </button>
  `).join("");
}

function renderRooms() {
  element.roomList.innerHTML = state.rooms.map((room) => `
    <li><strong>${escapeHtml(room.label || room.id)}</strong>
      <small>${escapeHtml(room.type || "")}</small></li>
  `).join("");
}

function renderStepSummary(workflow) {
  const completed = workflow._flow?.completed || {};
  const doneSteps = Array.isArray(completed) ? completed : Object.keys(completed);
  element.stepSummary.textContent = doneSteps.length
    ? `已完成步驟：${doneSteps.join("、")}`
    : "此專案尚未完成任何步驟";
}

async function loadProject(projectId) {
  setNotice("");
  const result = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  const workflow = result.project.workflow || {};
  state.workflow = workflow;
  element.projectName.textContent = result.project.name || projectId;
  renderStepSummary(workflow);

  const savedSpace = normalizeSavedSpaceConfirmation(workflow.space_confirmation || {});
  state.rooms = savedSpace.rooms;
  renderRooms();

  state.furniture2d = activeSchemeFurniture(workflow);
  state.selectedId = null;

  state.sceneData = normalizeSavedSceneData(workflow.white_model_3d?.sceneData) || null;
  if (state.sceneData) {
    state.furniture2d.forEach((item) => {
      const index = sceneObjectIndexFor(item);
      item.sceneObjectId = index >= 0
        ? state.sceneData.scene_objects[index].furniture_id
        : null;
    });
    await viewer.loadScene(state.sceneData);
    viewer.setViewMode("dollhouse");
    viewer.setCameraPreset("overview");
    applyInteractionMode();
  } else {
    setNotice("此專案還沒有 3D 白模資料（尚未完成第 6 步確認）。3D 舞台為空，僅顯示 2D 平面。", "warn");
  }

  element.planImage.onload = () => {
    state.geometry = planGeometryFrom(workflow.recognition, element.planImage);
    renderPlanFurniture();
  };
  element.planImage.onerror = () => {
    element.panel.dataset.empty = "true";
    setNotice("此專案沒有可用的平面圖底圖。", "warn");
  };
  element.planImage.src = `/api/projects/${encodeURIComponent(projectId)}/floorplan/source`;

  if (!state.furniture2d.length) {
    setNotice(
      state.sceneData
        ? "此專案沒有 2D 家具配置資料。"
        : "此專案尚未完成 2D 家具配置與白模，僅能檢視平面圖。",
      "warn",
    );
  }
}

async function loadLibraryFilters() {
  try {
    const result = await api("/api/furniture?has_model=true&page_size=1");
    element.libraryType.innerHTML = '<option value="">全部類型</option>'
      + (result.type_options || []).map((option) => `
        <option value="${escapeHtml(option.type)}">
          ${escapeHtml(option.type_name_zh || option.type)}（${option.count}）
        </option>`).join("");
    element.libraryStyle.innerHTML = '<option value="">全部風格</option>'
      + (result.styles || []).map((option) => `
        <option value="${escapeHtml(option.style_id)}">
          ${escapeHtml(option.style_name_zh || option.style_id)}
        </option>`).join("");
  } catch { /* 型錄離線時保留預設選項 */ }
}

async function searchLibrary() {
  const params = new URLSearchParams({
    has_model: "true", detail: "scene", page_size: "12",
  });
  if (element.libraryType.value) params.set("type", element.libraryType.value);
  if (element.libraryStyle.value) params.set("style", element.libraryStyle.value);
  if (element.libraryQ.value.trim()) params.set("q", element.libraryQ.value.trim());
  const result = await api(`/api/furniture?${params}`);
  state.libraryResults = (result.items || []).filter((item) => item.model_url);
  element.libraryResults.innerHTML = state.libraryResults.map((item, index) => `
    <div class="lab-lib-item">
      <strong>${escapeHtml(item.name_zh || item.name_zh_raw || item.furniture_id)}</strong>
      <small>${escapeHtml(item.category_label || item.normalized_type)}
        ・${Math.round(item.size_cm?.width || 0)} × ${Math.round(item.size_cm?.depth || 0)}
        × ${Math.round(item.size_cm?.height || 0)} cm</small>
      <div class="lab-lib-actions">
        <button type="button" data-lib-replace="${index}">替換選中家具</button>
        <button type="button" data-lib-add="${index}">新增（點地板）</button>
      </div>
    </div>
  `).join("") || '<p style="font-size:12px;color:#8a939d">沒有符合條件且有 GLB 的家具。</p>';
}

async function replaceWithCatalog(catalogItem) {
  const pair = selectedPair();
  if (!pair) { setNotice("請先選取要被替換的家具（點 2D 圖標或清單）。", "warn"); return; }
  const candidate = {
    ...pair.sceneObject,
    normalized_type: catalogItem.normalized_type,
    size_cm: catalogItem.size_cm,
  };
  const verdict = await validateCandidate(candidate, pair.sceneObject.furniture_id);
  if (!verdict.ok) {
    setNotice(`引擎拒絕替換：${verdict.reason || "新尺寸在此位置不合法"}`, "error");
    return;
  }
  Object.assign(pair.sceneObject, {
    normalized_type: catalogItem.normalized_type,
    name_zh_raw: catalogItem.name_zh || catalogItem.name_zh_raw,
    size_cm: catalogItem.size_cm,
    model_url: catalogItem.model_url,
    catalog_furniture_id: catalogItem.furniture_id,
    has_model: true,
  });
  Object.assign(pair.item, {
    type: catalogItem.normalized_type,
    label: catalogItem.name_zh || catalogItem.name_zh_raw,
    widthCm: catalogItem.size_cm.width,
    depthCm: catalogItem.size_cm.depth,
    heightCm: catalogItem.size_cm.height,
    catalogFurnitureId: catalogItem.furniture_id,
    iconPath: null,
  });
  await reloadViewerPreservingCamera();
  renderPlanFurniture();
  setNotice(`已替換為「${pair.item.label}」（僅本頁，不寫回專案）。`);
}

function addFromCatalog(catalogItem) {
  if (!state.sceneData) { setNotice("尚未載入 3D 場景。", "warn"); return; }
  setNotice("新增模式：請在 3D 地板上點選擺放位置。");
  viewer.beginPlacement(async (point) => {
    setNotice("正在請引擎驗證擺放位置…");
    const furnitureId = `lab-add-${Date.now().toString(36)}`;
    const candidate = {
      furniture_id: furnitureId,
      normalized_type: catalogItem.normalized_type,
      name_zh_raw: catalogItem.name_zh || catalogItem.name_zh_raw,
      size_cm: catalogItem.size_cm,
      position_cm: { x: point.x, z: point.z },
      rotation_y_deg: 0,
      position_locked: true,
      model_url: catalogItem.model_url,
      catalog_furniture_id: catalogItem.furniture_id,
      has_model: true,
    };
    const verdict = await validateCandidate(candidate, furnitureId);
    if (!verdict.ok) {
      setNotice(`引擎拒絕擺放：${verdict.reason || "位置不合法"}`, "error");
      return;
    }
    state.sceneData.scene_objects.push(candidate);
    state.furniture2d.push({
      id: furnitureId,
      sceneObjectId: furnitureId,
      type: catalogItem.normalized_type,
      variantId: null,
      label: candidate.name_zh_raw,
      widthCm: catalogItem.size_cm.width,
      depthCm: catalogItem.size_cm.depth,
      heightCm: catalogItem.size_cm.height,
      xCm: point.x,
      yCm: point.z,
      rotationDeg: 0,
      roomId: null,
      locked: false,
      userRequired: false,
      placementFailed: false,
    });
    await reloadViewerPreservingCamera();
    renderPlanFurniture();
    selectFurniture(furnitureId);
    setNotice(`已新增「${candidate.name_zh_raw}」（僅本頁，不寫回專案）。`);
  });
}

element.libraryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchLibrary().catch((error) => setNotice(`型錄查詢失敗：${error.message}`, "error"));
});

element.libraryResults.addEventListener("click", (event) => {
  const replaceButton = event.target.closest("[data-lib-replace]");
  if (replaceButton) {
    const item = state.libraryResults[Number(replaceButton.dataset.libReplace)];
    if (item) replaceWithCatalog(item).catch((error) => setNotice(`替換失敗：${error.message}`, "error"));
    return;
  }
  const addButton = event.target.closest("[data-lib-add]");
  if (addButton) {
    const item = state.libraryResults[Number(addButton.dataset.libAdd)];
    if (item) addFromCatalog(item);
  }
});

element.projectForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const projectId = element.projectInput.value.trim();
  if (!projectId) return;
  const params = new URLSearchParams(location.search);
  params.set("project", projectId);
  history.replaceState(null, "", `?${params}`);
  state.projectId = projectId;
  loadProject(projectId).catch((error) => setNotice(`載入失敗：${error.message}`, "error"));
});

element.panelToggle.addEventListener("click", () => {
  element.panel.classList.toggle("is-collapsed");
});

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-lab-furniture]");
  if (target) selectFurniture(target.dataset.labFurniture);
});

// 雙擊才把 3D 相機聚焦到該家具（單擊只同步選取，避免視角大跳）。
document.addEventListener("dblclick", (event) => {
  const target = event.target.closest("[data-lab-furniture]");
  if (target) selectFurniture(target.dataset.labFurniture, { focus: true });
});

element.viewButtons.forEach((button) => {
  button.addEventListener("click", () => {
    viewer.setViewMode(button.dataset.labView);
    element.viewButtons.forEach((candidate) => {
      candidate.classList.toggle("is-active", candidate === button);
    });
    if (button.dataset.labView !== "walk") applyInteractionMode();
  });
});

element.modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    // setInteractionMode("camera") 內部會 setViewMode 重設視角，先存後還原。
    const cameraState = viewer.getCameraState();
    state.interactionMode = button.dataset.labMode;
    applyInteractionMode();
    if (state.interactionMode === "camera") viewer.setCameraState(cameraState);
    setNotice(button.dataset.labMode === "edit"
      ? "編輯模式：拖家具＝移動（引擎驗證）、拖空白處＝轉視角，左下面板可微調與旋轉。變更不寫回專案。"
      : "");
  });
});

// lab 測試／除錯掛鉤（僅實驗頁使用）
globalThis.__sceneLab = { viewer, state };

window.addEventListener("resize", () => renderPlanFurniture());

loadLibraryFilters();
if (state.projectId) {
  element.projectInput.value = state.projectId;
  loadProject(state.projectId).catch((error) => setNotice(`載入失敗：${error.message}`, "error"));
} else {
  setNotice("輸入專案 ID 後載入。編輯僅在本頁生效，不會寫回專案資料。");
}
