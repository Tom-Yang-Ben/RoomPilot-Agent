// Project creation, floor-plan upload, overlay synchronization, and scale calibration.
export function createSceneFloorplanController({
  $,
  api,
  buildScaleCalibration,
  calibrationActionState,
  createWorkflow,
  element,
  errorMessage,
  goTo,
  initializeRoomsAndStructures,
  recognitionReviewSuffix,
  renderConfigurationPlan,
  renderLayoutFurniture,
  renderSpaceOverlay,
  scheduleSave,
  setStatus,
  showStep,
  state,
}) {
async function createProject(event) {
  event.preventDefault();
  element.projectError.textContent = "";
  const name = element.projectName.value.trim();
  if (!name) {
    element.projectError.textContent = "請輸入專案名稱，才能建立專案。";
    element.projectName.focus();
    return;
  }
  try {
    const result = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, notes: element.projectNotes.value.trim() }),
    });
    state.project = result.project;
    state.projectId = state.project.project_id;
    state.workflow = createWorkflow({ projectId: state.projectId });
    state.workflow.complete("project", { name });
    const projectQuery = new URLSearchParams(location.search);
    projectQuery.set("project_id", state.projectId);
    history.replaceState({}, "", `/scene?${projectQuery.toString()}`);
    element.saveStatus.textContent = `已建立 · ${name}`;
    setStatus("專案已建立。下一步只需要上傳平面圖，不會先問需求問卷。");
    scheduleSave("upload");
    goTo("upload");
  } catch (error) {
    element.projectError.textContent = errorMessage(error);
  }
}

function floorplanExtension(file) {
  const name = String(file?.name || "").toLowerCase();
  return [".dxf", ".png", ".jpg", ".jpeg"].find((extension) => name.endsWith(extension)) || "";
}

function clearPendingPreview() {
  if (state.pendingPreviewUrl) URL.revokeObjectURL(state.pendingPreviewUrl);
  state.pendingPreviewUrl = null;
  element.uploadPreview.removeAttribute("src");
  element.uploadPreview.hidden = true;
  element.uploadDropZone.classList.remove("has-preview");
}

function showPendingPreview(file, extension) {
  clearPendingPreview();
  if (!file || extension === ".dxf") return;
  state.pendingPreviewUrl = URL.createObjectURL(file);
  element.uploadPreview.src = state.pendingPreviewUrl;
  element.uploadPreview.hidden = false;
  element.uploadDropZone.classList.add("has-preview");
}

function showUploadedPreview(url, extension) {
  clearPendingPreview();
  if (!url || extension === ".dxf") return;
  element.uploadPreview.src = url;
  element.uploadPreview.hidden = false;
  element.uploadDropZone.classList.add("has-preview");
}

function updateUploadConfirmationState() {
  element.confirmUpload.disabled = !(
    state.pendingFile
    && element.floorplanConfirmation.checked
  );
}

function selectFloorplanFile(file) {
  element.uploadError.textContent = "";
  const extension = floorplanExtension(file);
  if (!extension) {
    state.pendingFile = null;
    clearPendingPreview();
    element.uploadFileState.textContent = "格式不支援";
    element.uploadError.textContent = "只支援 DXF、PNG、JPG 或 JPEG。PDF、WEBP、HEIC 等格式不會上傳。";
    updateUploadConfirmationState();
    return false;
  }
  state.pendingFile = file;
  state.sourceExtension = extension;
  showPendingPreview(file, extension);
  element.uploadFileState.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
  setStatus(extension === ".dxf"
    ? "已選擇 DXF。確認檔案正確並勾選後，系統會產生圖面預覽。"
    : "平面圖已顯示。請確認圖檔內容正確並勾選後繼續。");
  updateUploadConfirmationState();
  return true;
}

async function confirmUpload() {
  element.uploadError.textContent = "";
  if (!state.pendingFile) {
    element.uploadError.textContent = "請先選擇 DXF、PNG、JPG 或 JPEG 平面圖。";
    element.file.focus();
    return;
  }
  if (!element.floorplanConfirmation.checked) {
    element.uploadError.textContent = "請先勾選確認圖檔內容正確，才能進入下一步。";
    element.floorplanConfirmation.focus();
    return;
  }
  try {
    setStatus("正在保存原圖並辨識牆、門、窗…");
    const form = new FormData();
    form.append("file", state.pendingFile);
    const uploaded = await api(`/api/projects/${state.projectId}/floorplan`, {
      method: "POST",
      body: form,
    });
    state.sourceUrl = `${uploaded.upload.source_url}?v=${Date.now()}`;
    state.sourceExtension = uploaded.upload.extension;
    showUploadedPreview(state.sourceUrl, state.sourceExtension);
    state.workflow.setFloorplanConfirmation({ confirmed: true });
    state.workflow.complete("upload", { filename: uploaded.upload.filename });
    await api(`/api/projects/${state.projectId}/workflow`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_step: "upload",
        workflow: {
          floorplan_confirmation: {
            confirmed: true,
          },
        },
      }),
    });
    const result = await api(`/api/projects/${state.projectId}/floorplan/analyze`, {
      method: "POST",
    });
    state.analysis = result.analysis;
    state.workflow.complete("recognition", { engine: result.geometry_engine });
    const scaleEvidence = (state.analysis.evidence || []).find(
      (item) => Array.isArray(item.start_px) && Array.isArray(item.end_px),
    );
    if (scaleEvidence) {
      state.calibrationPoints = [
        { x: Number(scaleEvidence.start_px[0]), y: Number(scaleEvidence.start_px[1]) },
        { x: Number(scaleEvidence.end_px[0]), y: Number(scaleEvidence.end_px[1]) },
      ];
    } else {
      state.calibrationPoints = [];
    }
    if (state.sourceExtension === ".dxf") {
      state.sourceUrl = configureDxfPreview(state.analysis);
    }
    setPlanImages(state.sourceUrl);
    const count = {
      walls: state.analysis.walls?.length || state.analysis.floorplan?.wall_count || 0,
      doors: state.analysis.doors?.length || state.analysis.floorplan?.door_count || 0,
      windows: state.analysis.windows?.length || state.analysis.floorplan?.window_count || 0,
    };
    element.recognitionSummary.textContent = `辨識結果：牆 ${count.walls}、門 ${count.doors}、窗 ${count.windows}${recognitionReviewSuffix()}`;
    if (Number(state.analysis.scale?.distance_cm) > 0) {
      element.scaleInput.value = Number(state.analysis.scale.distance_cm);
    } else if (Number(state.analysis.scale?.distance_m) > 0) {
      element.scaleInput.value = Math.round(state.analysis.scale.distance_m * 1000) / 10;
    }
    setStatus(scaleEvidence
      ? "已標出建議端點。請拖曳確認兩端位置，再輸入實際公分尺寸。"
      : "辨識完成。現在請在圖上拉兩端，並輸入這一段的實際公分尺寸。");
    showStep("recognition");
    scheduleSave("recognition");
  } catch (error) {
    element.uploadError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

function dxfPreviewDataUrl(floorplan = {}) {
  const segments = floorplan.wall_segments || floorplan.plan_segments || [];
  const width = Math.max(Number(floorplan.width_cm || 600), 1);
  const depth = Math.max(Number(floorplan.depth_cm || 400), 1);
  const pixelWidth = 1000;
  const pixelHeight = Math.max(1, Math.round(pixelWidth * depth / width));
  const lines = segments.map((segment) => {
    const start = segment.start || segment[0] || { x: 0, z: 0 };
    const end = segment.end || segment[1] || { x: 0, z: 0 };
    const x1 = Number(start.x ?? start[0]) + width / 2;
    const y1 = depth / 2 - Number(start.z ?? start.y ?? start[1]);
    const x2 = Number(end.x ?? end[0]) + width / 2;
    const y2 = depth / 2 - Number(end.z ?? end.y ?? end[1]);
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" />`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${pixelWidth}" height="${pixelHeight}" viewBox="0 0 ${width} ${depth}"><rect width="${width}" height="${depth}" fill="white"/><g stroke="#222" stroke-width="${Math.max(width, depth) / 500}">${lines}</g></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function configureDxfPreview(analysis) {
  const floorplan = analysis?.floorplan || {};
  const widthCm = Math.max(Number(floorplan.width_cm || 600), 1);
  const depthCm = Math.max(Number(floorplan.depth_cm || 400), 1);
  const previewWidth = 1000;
  const previewHeight = Math.max(1, Math.round(previewWidth * depthCm / widthCm));
  analysis.image_size_px = { width: previewWidth, height: previewHeight };
  analysis.plan_bbox_px = [0, 0, previewWidth, previewHeight];
  analysis.scale = {
    distance_cm: widthCm,
    cm_per_px: widthCm / previewWidth,
    source: "dxf_geometry",
  };
  return dxfPreviewDataUrl(floorplan);
}

function setPlanImages(url) {
  [element.scaleImage, element.spaceImage, element.layoutImage]
    .concat(element.questionnairePlanImage)
    .filter(Boolean)
    .forEach((image) => {
      image.src = url;
      image.addEventListener("load", syncAllOverlays, { once: true });
    });
}

function imageContentRect(image) {
  const box = image.getBoundingClientRect();
  if (!image.naturalWidth || !image.naturalHeight || !box.width || !box.height) return box;
  const scale = Math.min(
    box.width / image.naturalWidth,
    box.height / image.naturalHeight,
  );
  const width = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  return {
    left: box.left + (box.width - width) / 2,
    top: box.top + (box.height - height) / 2,
    right: box.left + (box.width + width) / 2,
    bottom: box.top + (box.height + height) / 2,
    width,
    height,
  };
}

function syncOverlayToImage(stage, image, overlay) {
  if (!stage || !image || !overlay || !image.naturalWidth) return;
  const stageRect = stage.getBoundingClientRect();
  const imageRect = imageContentRect(image);
  overlay.style.left = `${imageRect.left - stageRect.left}px`;
  overlay.style.top = `${imageRect.top - stageRect.top}px`;
  overlay.style.width = `${imageRect.width}px`;
  overlay.style.height = `${imageRect.height}px`;
  overlay.style.right = "auto";
  overlay.style.bottom = "auto";
  overlay.setAttribute("viewBox", `0 0 ${image.naturalWidth} ${image.naturalHeight}`);
}

function syncLayoutLayer() {
  if (!element.layoutImage.naturalWidth) return;
  const stageRect = element.layoutStage.getBoundingClientRect();
  const imageRect = imageContentRect(element.layoutImage);
  Object.assign(element.layoutLayer.style, {
    left: `${imageRect.left - stageRect.left}px`,
    top: `${imageRect.top - stageRect.top}px`,
    width: `${imageRect.width}px`,
    height: `${imageRect.height}px`,
    right: "auto",
    bottom: "auto",
  });
}

function syncAllOverlays() {
  syncOverlayToImage(element.scaleStage, element.scaleImage, element.scaleOverlay);
  syncOverlayToImage(element.spaceStage, element.spaceImage, element.spaceOverlay);
  syncOverlayToImage(
    element.dimensionPlanStage,
    element.dimensionPlanImage,
    element.dimensionPlanOverlay,
  );
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  syncOverlayToImage(
    element.questionnairePlanStage,
    element.questionnairePlanImage,
    element.questionnairePlanOverlay,
  );
  syncLayoutLayer();
  renderCalibration();
  renderSpaceOverlay();
  renderLayoutFurniture();
  renderConfigurationPlan();
}

function imagePoint(event, image) {
  const rect = imageContentRect(image);
  if (!rect.width || !rect.height || !image.naturalWidth) return null;
  const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
  const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
  return {
    x: x * image.naturalWidth / rect.width,
    y: y * image.naturalHeight / rect.height,
  };
}

function renderCalibration() {
  const [start, end] = state.calibrationPoints;
  const line = start && end
    ? `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="#bd5c36" stroke-width="5" stroke-dasharray="12 7"/>`
    : "";
  const points = state.calibrationPoints.map((point, index) => `
    <circle data-calibration-point="${index}" cx="${point.x}" cy="${point.y}" r="12"
      fill="#fff" stroke="${index ? "#bd5c36" : "#2f6f87"}" stroke-width="6"/>
  `).join("");
  element.scaleOverlay.innerHTML = `${line}${points}`;
  if (start && end) {
    const pixels = Math.hypot(end.x - start.x, end.y - start.y);
    element.calibrationReadout.textContent = pixels > 0
      ? `兩個端點已選好，圖上距離 ${pixels.toFixed(1)} px；仍可拖曳微調。`
      : "兩個端點重疊，請拖曳其中一點。";
  } else if (start) {
    element.calibrationReadout.textContent = "起點已選好，請再點一下終點。";
  } else {
    element.calibrationReadout.textContent = "請先在圖面點選起點。";
  }
  updateCalibrationAction();
}

function setCalibrationTaskState(task, status, stateName, label) {
  task.classList.toggle("is-active", stateName === "active");
  task.classList.toggle("is-complete", stateName === "complete");
  task.classList.toggle("is-pending", stateName === "pending");
  if (stateName === "active") task.setAttribute("aria-current", "step");
  else task.removeAttribute("aria-current");
  status.textContent = label;
}

function updateCalibrationAction({ showMessage = true } = {}) {
  const action = calibrationActionState(
    state.calibrationPoints,
    element.scaleInput.value,
  );
  const [start, end] = state.calibrationPoints;
  const pixelDistance = start && end
    ? Math.hypot(end.x - start.x, end.y - start.y)
    : 0;
  const pointsReady = state.calibrationPoints.length === 2 && pixelDistance > 0;
  const measurementReady = pointsReady && Number(element.scaleInput.value) > 0;

  element.scaleInput.disabled = !pointsReady;
  element.resetCalibration.hidden = state.calibrationPoints.length === 0;
  setCalibrationTaskState(
    element.calibrationPointTask,
    element.calibrationPointStatus,
    pointsReady ? "complete" : "active",
    pointsReady ? "完成" : "進行中",
  );
  setCalibrationTaskState(
    element.calibrationMeasureTask,
    element.calibrationMeasureStatus,
    measurementReady ? "complete" : pointsReady ? "active" : "pending",
    measurementReady ? "完成" : pointsReady ? "進行中" : "待選點",
  );
  setCalibrationTaskState(
    element.calibrationConfirmTask,
    element.calibrationConfirmStatus,
    action.ready ? "active" : "pending",
    action.ready ? "可確認" : "待完成",
  );
  element.applyCalibration.disabled = !action.ready;
  if (showMessage) {
    element.scaleError.textContent = pointsReady ? action.message : "";
    element.scaleError.dataset.kind = action.ready ? "ready" : "instruction";
  }
  return action;
}

function calibrationPointerDown(event) {
  const circle = event.target.closest("[data-calibration-point]");
  if (circle) {
    state.calibrationDragIndex = Number(circle.dataset.calibrationPoint);
    circle.setPointerCapture?.(event.pointerId);
    return;
  }
  const point = imagePoint(event, element.scaleImage);
  if (!point) return;
  if (state.calibrationPoints.length >= 2) {
    const distances = state.calibrationPoints.map((candidate) =>
      Math.hypot(candidate.x - point.x, candidate.y - point.y)
    );
    state.calibrationPoints[distances[0] <= distances[1] ? 0 : 1] = point;
  } else {
    state.calibrationPoints.push(point);
  }
  renderCalibration();
}

function calibrationPointerMove(event) {
  if (state.calibrationDragIndex == null) return;
  const point = imagePoint(event, element.scaleImage);
  if (!point) return;
  state.calibrationPoints[state.calibrationDragIndex] = point;
  renderCalibration();
}

function applyCalibrationToAnalysis(analysis, calibration) {
  if (!analysis || typeof analysis !== "object") throw new Error("recognition_result_missing");
  const next = JSON.parse(JSON.stringify(analysis));
  const previousScale = next.scale || {};
  const previousCmPerPx = Number(previousScale.cm_per_px)
    || Number(previousScale.m_per_px) * 100;
  const nextCmPerPx = Number(calibration.cm_per_px);
  if (!(nextCmPerPx > 0)) throw new Error("calibration_measurement_invalid");
  const factor = previousCmPerPx > 0 ? nextCmPerPx / previousCmPerPx : 1;
  const scalePoint = (point) => {
    if (!point || typeof point !== "object") return;
    ["x", "y", "z"].forEach((key) => {
      if (Number.isFinite(Number(point[key]))) point[key] = Number(point[key]) * factor;
    });
  };
  const scalePointList = (points) => {
    if (!Array.isArray(points)) return;
    points.forEach((point) => {
      if (Array.isArray(point)) {
        point.forEach((value, index) => {
          if (Number.isFinite(Number(value))) point[index] = Number(value) * factor;
        });
      } else {
        scalePoint(point);
      }
    });
  };
  const scaleLengthFields = (item) => {
    ["width_cm", "height_cm", "depth_cm", "thickness_cm", "clearance_radius_cm", "width_m", "height_m", "depth_m", "thickness_m", "clearance_radius_m"].forEach((key) => {
      if (Number.isFinite(Number(item?.[key]))) item[key] = Number(item[key]) * factor;
    });
  };
  ["walls", "doors", "windows"].forEach((kind) => {
    (next[kind] || []).forEach((item) => {
      scalePoint(item.start);
      scalePoint(item.end);
      scalePoint(item.swing_end);
      scaleLengthFields(item);
    });
  });
  (next.rooms || []).forEach((room) => {
    ["polygon_cm", "polygon_m", "polygon", "exterior"].forEach((key) => scalePointList(room[key]));
    scalePoint(room.centroid_cm);
    scalePoint(room.centroid_m);
    ["area_cm2", "area_m2"].forEach((key) => {
      if (Number.isFinite(Number(room[key]))) room[key] = Number(room[key]) * factor * factor;
    });
    scaleLengthFields(room);
  });
  const geometryUsesCentimeters = Number(previousScale.cm_per_px) > 0
    || ["cm", "centimeter", "centimetre"].includes(String(next.coordinate_system?.unit || "").toLowerCase());
  next.scale = {
    ...previousScale,
    pixel_distance: Number(calibration.pixel_distance),
    source: "manual_confirmation",
    confidence: 1,
  };
  if (geometryUsesCentimeters) {
    next.scale.distance_cm = Number(calibration.distance_cm);
    next.scale.cm_per_px = nextCmPerPx;
    delete next.scale.distance_m;
    delete next.scale.m_per_px;
  } else {
    next.scale.distance_m = Number(calibration.distance_cm) / 100;
    next.scale.m_per_px = nextCmPerPx / 100;
    delete next.scale.distance_cm;
    delete next.scale.cm_per_px;
  }
  next.evidence = [{
    text: `${Number(calibration.distance_cm)} cm`,
    confidence: 1,
    distance_cm: Number(calibration.distance_cm),
    start_px: calibration.start_px,
    end_px: calibration.end_px,
    pixel_distance: Number(calibration.pixel_distance),
  }];
  next.issues = (next.issues || []).filter((issue) => issue !== "scale_anchor_missing" && issue !== "scale_confirmation_required");
  next.requires_scale_confirmation = false;
  return next;
}

async function applyCalibration() {
  const action = updateCalibrationAction();
  if (!action.ready) {
    if (state.calibrationPoints.length === 2) element.scaleInput.focus();
    return;
  }
  const distanceCm = Number(element.scaleInput.value);
  try {
    const calibration = buildScaleCalibration(state.calibrationPoints, distanceCm);
    setStatus("正在套用確認的公分尺度…");
    if (state.sourceExtension !== ".dxf") {
      state.analysis = applyCalibrationToAnalysis(state.analysis, calibration);
    }
    state.confirmedFloorplan = {
      floorplan: state.analysis.floorplan || state.analysis,
      dxf_text: null,
      confirmation_status: "room_review_pending",
    };
    state.spaceReviewMode = "editing";
    state.workflow.complete("calibration", { distanceCm, calibration });
    initializeRoomsAndStructures();
    state.workflow.goTo("space_confirmation");
    setStatus(`尺度已確認為 ${distanceCm} cm。現在開始確認 ${state.rooms.length} 個房間。`);
    showStep("space_confirmation");
    scheduleSave("space_confirmation");
  } catch (error) {
    element.scaleError.textContent = errorMessage(error);
    setStatus(errorMessage(error), "error");
  }
}

  return {
    applyCalibration,
    applyCalibrationToAnalysis,
    calibrationPointerDown,
    calibrationPointerMove,
    clearPendingPreview,
    configureDxfPreview,
    confirmUpload,
    createProject,
    dxfPreviewDataUrl,
    floorplanExtension,
    imageContentRect,
    imagePoint,
    renderCalibration,
    selectFloorplanFile,
    setCalibrationTaskState,
    setPlanImages,
    showPendingPreview,
    showUploadedPreview,
    syncAllOverlays,
    syncLayoutLayer,
    syncOverlayToImage,
    updateCalibrationAction,
    updateUploadConfirmationState,
  };
}
