// Step 7 proposal review and Step 8 render/delivery workflow controller.
export function createSceneProposalController({
  activeScheme,
  aiRenderViewer,
  api,
  beginPlacementBusy,
  composeSelectedRoomFurniture,
  configurationSnapshot,
  element,
  endPlacementBusy,
  errorMessage,
  escapeHtml,
  finishesGate,
  goTo,
  lockedConfigurationSnapshot,
  pointInPolygonCm,
  proposalRoomPreviewCache,
  proposalRuntimeState,
  proposalViewer,
  refreshConfigurationSnapshot,
  renderSchemeControls,
  scheduleSave,
  setStatus,
  showQuestionnaireStage,
  state,
  STYLE_PACKS,
  visualQuestionnaireProgress,
  WHOLE_HOUSE_QUESTIONS,
}) {
function currentSceneVersion() {
  return [
    state.sceneData?.scene_id || "scene",
    `revision-${Number(state.project?.revision || 0)}`,
    state.activeStylePackId || "no-style",
  ].join(":");
}

function renderProposalPaletteSelection() {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId)
    || STYLE_PACKS[0];
  const options = STYLE_PACKS.filter((item) => item.styleId === activePack.styleId);
  const selectedId = state.proposalReview.confirmedStyleCardId;
  element.proposalPaletteGrid.innerHTML = options.map((pack) => `
    <button type="button" data-proposal-style-card="${escapeHtml(pack.id)}"
      class="${pack.id === selectedId ? "is-active" : ""}"
      aria-pressed="${pack.id === selectedId}">
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}"
        alt="${escapeHtml(`${pack.styleLabel} ${pack.name}色卡預覽`)}" loading="lazy">
      <span class="rp-style-swatches">${pack.palette
        .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
        .join("")}</span>
      <strong>${escapeHtml(pack.name)}</strong>
      <small>${escapeHtml(pack.furniture.displayHighlights.join("、"))}</small>
    </button>
  `).join("");
  element.proposalPaletteStatus.textContent = selectedId
    ? `已選「${STYLE_PACKS.find((item) => item.id === selectedId)?.name || "色卡"}」；第 8 步將以這張色卡送往遠端。`
    : "請選擇一張色卡後，再鎖定生圖視角。";
}

function selectProposalPalette(cardId) {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId)
    || STYLE_PACKS[0];
  const pack = STYLE_PACKS.find((item) => item.id === cardId);
  if (!pack || pack.styleId !== activePack.styleId) return;
  state.proposalReview.confirmedStyleCardId = pack.id;
  renderProposalPaletteSelection();
  renderProposalSummary();
  scheduleSave("proposal_review");
}

function renderProposalSummary() {
  const pack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const selectedPalette = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  const furniture = state.sceneData?.scene_objects || [];
  const customPreferenceCount = Object.values(state.visualAnswers || {}).filter(
    (answer) => String(answer?.custom || "").trim(),
  ).length;
  const rows = [
    ["配置", "已確認家具配置"],
    ["色卡", selectedPalette ? `${selectedPalette.styleLabel}／${selectedPalette.name}` : (pack ? `${pack.styleLabel}／尚未選擇色卡` : "尚未選擇")],
    ["家具", `${furniture.filter((item) => !item.placement_failed).length} 件已配置`],
    ["結構", `牆 ${state.structures.walls.length}、門 ${state.structures.doors.length}、窗 ${state.structures.windows.length}`],
    ["表面", state.surfaceState.wall?.styleLocked && state.surfaceState.floor?.styleLocked ? "牆與地板已鎖定" : "使用目前 StylePack"],
    ["逐房需求", `${state.rooms.length} 個房間／${customPreferenceCount} 項補充條件`],
  ];
  element.proposalReviewSummary.innerHTML = rows.map(([label, value]) => `
    <div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>
  `).join("");
}


function lockMasterRenderView() {
  const contentConfirmed = document.querySelector("#proposal-content-confirmed")?.checked === true;
  if (!contentConfirmed) {
    element.masterViewStatus.textContent = "請先確認家具、結構、材質、色卡與需求。";
    return;
  }
  if (activeScheme()?.stale || !activeScheme()?.sceneData) {
    element.masterViewStatus.textContent =
      "家具配置尚未完成最新的 2D／3D 重算，不能鎖定。";
    return;
  }
  const visualProgress = visualQuestionnaireProgress({
    questions: state.visualQuestions,
    answers: state.visualAnswers,
    skippedSpaceTypes: state.skippedVisualSpaceTypes,
  });
  const confirmedRoomRequirements = state.rooms.every((room) => (
    state.roomRequirementModel.roomRequirements?.[room.id]?.confirmed === true
  ));
  if (!visualProgress.ready && !confirmedRoomRequirements) {
    element.requirementsError.textContent =
      `逐房極與極尚有 ${visualProgress.total - visualProgress.completed} 題未處理。`;
    showQuestionnaireStage("rooms");
    return;
  }
  if (!finishesGate(state.questionnaireFinishes).ready) {
    element.requirementsError.textContent =
      "請先確認風格、牆壁、地板、天花板與照明。";
    showQuestionnaireStage("finishes");
    return;
  }
  if (!state.sceneData || !state.activeStylePackId) {
    element.masterViewStatus.textContent = "缺少已確認的場景或色卡，請返回第 6 步。";
    return;
  }
  if (!state.proposalReview.confirmedStyleCardId) {
    element.masterViewStatus.textContent = "請先選擇一張同風格色卡，作為遠端生圖的色彩基準。";
    return;
  }
  const configurationSnapshotData = refreshConfigurationSnapshot();
  const camera = proposalViewer.getCameraState();
  if (camera.camera_type !== "perspective") {
    element.masterViewStatus.textContent = "遠端室內渲染需要透視視角，請改用「室內環視」或「室內透視」。";
    return;
  }
  const lockedAt = new Date().toISOString();
  state.proposalReview.masterView = {
    camera,
    scene_version: currentSceneVersion(),
    style_card_id: state.proposalReview.confirmedStyleCardId,
    configuration_snapshot_id: configurationSnapshotData.snapshot_id,
    locked_at: lockedAt,
  };
  state.configurationState.locked = true;
  state.proposalReview.roomViews = {};
  proposalRoomPreviewCache.clear();
  state.proposalReview.jobs = [];
  proposalViewer.lockRenderCamera(true);
  const completed = state.workflow.complete("proposal_review", {
    confirmed: true,
    masterView: state.proposalReview.masterView,
  });
  if (!completed) {
    element.masterViewStatus.textContent = "視角資料不完整，尚未鎖定。";
    proposalViewer.lockRenderCamera(false);
    return;
  }
  try {
    renderSchemeControls();
  } catch (error) {
    console.warn("Unable to refresh scheme controls after locking the master view.", error);
  }
  element.masterViewStatus.textContent = "完整方案已鎖定；請繼續逐房選擇渲染視角。";
  scheduleSave("proposal_review");
  state.selectedProposalRoomId = state.rooms[0]?.id || null;
  state.selectedProposalRoomCandidateIndex = 0;
  renderProposalRoomViewPanel();
  if (state.selectedProposalRoomId) selectProposalRoomView(state.selectedProposalRoomId);
}


function roomScenePolygon(room) {
  const center = planCenterCm();
  return (room?.polygon_cm || [])
    .map((point) => ({
      x: Number(point.x) - center.x,
      // scene_viewer flips source Z before rendering; room cameras use world Z.
      z: center.y - Number(point.y),
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.z));
}

function scenePointInsideRoom(room, point) {
  const center = planCenterCm();
  return pointInPolygonCm(
    { x: Number(point.x) + center.x, y: center.y - Number(point.z) },
    room?.polygon_cm || [],
  );
}

function roomSceneTarget(room) {
  const polygon = roomScenePolygon(room);
  if (!polygon.length) return { x: 0, z: 0 };
  const boundsCenter = {
    x: (Math.min(...polygon.map((point) => point.x)) + Math.max(...polygon.map((point) => point.x))) / 2,
    z: (Math.min(...polygon.map((point) => point.z)) + Math.max(...polygon.map((point) => point.z))) / 2,
  };
  const average = polygon.reduce(
    (sum, point) => ({ x: sum.x + point.x / polygon.length, z: sum.z + point.z / polygon.length }),
    { x: 0, z: 0 },
  );
  const interior = [boundsCenter, average]
    .find((candidate) => scenePointInsideRoom(room, candidate))
    || polygon.map((point) => ({
      x: point.x * 0.72 + average.x * 0.28,
      z: point.z * 0.72 + average.z * 0.28,
    })).find((candidate) => scenePointInsideRoom(room, candidate))
    || average;
  const furniture = (state.sceneData?.scene_objects || []).filter(
    (item) => String(item.placement_room_id || item.room_id || "") === String(room?.id),
  );
  if (!furniture.length) return interior;
  const furnitureCenter = furniture.reduce((sum, item) => ({
    x: sum.x + Number(item.position_cm?.x || 0) / furniture.length,
    z: sum.z - Number(item.position_cm?.z || 0) / furniture.length,
  }), { x: 0, z: 0 });
  const weighted = {
    x: interior.x * 0.7 + furnitureCenter.x * 0.3,
    z: interior.z * 0.7 + furnitureCenter.z * 0.3,
  };
  return scenePointInsideRoom(room, weighted) ? weighted : interior;
}

function insetRoomCameraPoint(room, anchorIndex = 0) {
  const target = roomSceneTarget(room);
  const anchors = roomScenePolygon(room)
    .slice()
    .sort((left, right) => (
      Math.atan2(left.z - target.z, left.x - target.x)
      - Math.atan2(right.z - target.z, right.x - target.x)
    ));
  if (!anchors.length) return { x: target.x + 90, z: target.z + 90 };
  const spacedIndex = Math.floor((anchorIndex % 3) * anchors.length / 3) % anchors.length;
  const anchor = anchors[spacedIndex];
  for (const factor of [0.78, 0.68, 0.56, 0.44]) {
    const candidate = {
      x: target.x + (anchor.x - target.x) * factor,
      z: target.z + (anchor.z - target.z) * factor,
    };
    if (scenePointInsideRoom(room, candidate)) return candidate;
  }
  return target;
}

function roomCameraForAnchor(room, anchorIndex = 0) {
  const target = roomSceneTarget(room);
  const position = insetRoomCameraPoint(room, anchorIndex);
  return {
    camera_type: "perspective",
    view_mode: "orbit",
    preset: "full-room-v2",
    room_id: room.id,
    room_label: room.label || "",
    position_cm: [position.x, 145, position.z],
    target_cm: [target.x, 92, target.z],
    up: [0, 1, 0],
    fov_deg: 72,
    zoom: 1,
  };
}

function roomCameraSuggestion(room) {
  return roomCameraForAnchor(room, 0);
}

function roomCameraTargetsRoom(room, camera) {
  const target = camera?.target_cm;
  if (!Array.isArray(target) || target.length < 3) return false;
  const point = { x: Number(target[0]), z: Number(target[2]) };
  if (!Number.isFinite(point.x) || !Number.isFinite(point.z)) return false;
  return scenePointInsideRoom(room, point);
}

function proposalRoomCameraCandidates(room) {
  const labels = [
    ["完整主視角", "從房間內側斜角看向中央，呈現主要家具與完整空間。"],
    ["入口對向視角", "從另一側同時查看家具、門窗與通行範圍。"],
    ["空間側向視角", "從側邊廣角確認整體比例與家具配置。"],
  ];
  return labels.map(([label, note], index) => ({
    label,
    note,
    camera: roomCameraForAnchor(room, index),
  }));
}

function proposalRoomPreviewKey(room) {
  return `${currentSceneVersion()}:full-room-v2:${String(room.id)}`;
}

async function ensureProposalRoomCandidatePreviews(room) {
  if (!room || !state.proposalReview.masterView) return;
  const key = proposalRoomPreviewKey(room);
  if (proposalRoomPreviewCache.has(key)) return;
  proposalRoomPreviewCache.set(key, "loading");
  const previousCamera = proposalViewer.getCameraState();
  try {
    const previews = proposalRoomCameraCandidates(room).map((choice) => {
      proposalViewer.setCameraState(choice.camera);
      return proposalViewer.capturePng();
    });
    proposalRoomPreviewCache.set(key, previews);
  } catch {
    proposalRoomPreviewCache.delete(key);
  } finally {
    proposalViewer.setCameraState(previousCamera);
  }
  if (String(state.selectedProposalRoomId) === String(room.id)) {
    renderProposalRoomViewPanel();
  }
}



function validProposalRoomView(room) {
  const saved = state.proposalReview.roomViews?.[room?.id];
  const camera = saved?.camera;
  return String(saved?.room_id || camera?.room_id || "") === String(room?.id)
    && String(camera?.preset || "").startsWith("full-room-v2")
    && roomCameraTargetsRoom(room, camera)
    ? saved
    : null;
}

function selectProposalRoomView(roomId) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  if (!room) return;
  state.selectedProposalRoomId = room.id;
  const saved = validProposalRoomView(room);
  const savedCamera = saved?.camera;
  const savedMatchesRoom = Boolean(saved);
  const choices = proposalRoomCameraCandidates(room);
  state.selectedProposalRoomCandidateIndex = savedMatchesRoom
    ? Number(saved?.candidate_index ?? 0)
    : 0;
  proposalViewer.lockRenderCamera(false);
  proposalViewer.setCameraState(
    (savedMatchesRoom ? savedCamera : null)
      || choices[state.selectedProposalRoomCandidateIndex]?.camera
      || choices[0].camera,
  );
  renderProposalRoomViewPanel();
}

function selectProposalRoomCandidate(index) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedProposalRoomId));
  if (!room || !Number.isInteger(index)) return;
  const choices = proposalRoomCameraCandidates(room);
  const choice = choices[index];
  if (!choice) return;
  state.selectedProposalRoomCandidateIndex = index;
  proposalViewer.lockRenderCamera(false);
  proposalViewer.setCameraState(choice.camera);
  renderProposalRoomViewPanel();
}

function lockSelectedProposalRoomView() {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedProposalRoomId));
  if (!room) return;
  const camera = {
    ...proposalViewer.getCameraState(),
    preset: "full-room-v2-locked",
    room_id: room.id,
    room_label: room.label || "",
  };
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera,
    candidate_index: state.selectedProposalRoomCandidateIndex,
    scene_version: currentSceneVersion(),
    saved_at: new Date().toISOString(),
  };
  refreshConfigurationSnapshot();
  scheduleSave("proposal_review");
  renderProposalRoomViewPanel();
}


function questionnaireContextValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean).join("、");
  if (value && typeof value === "object") return "";
  return String(value || "").trim();
}

function wholeHouseQuestionnaireNeeds() {
  const profile = {
    ...(state.roomRequirementModel?.globalProfile || {}),
    ...(state.basicAnswers || {}),
  };
  return WHOLE_HOUSE_QUESTIONS.map((question) => {
    const value = questionnaireContextValue(profile[question.id]);
    return value ? `${question.label}：${value}` : "";
  }).filter(Boolean);
}

function questionnaireContextLabel(context) {
  return context?.fallbackUsed ? "問卷摘要（已套用全屋需求）" : "問卷摘要";
}

function roomQuestionnaireContext(roomId) {
  const requirement = state.roomRequirementModel?.roomRequirements?.[roomId]
    || state.roomRequirementModel?.[roomId]
    || {};
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  const furniture = requirement.furniture || {};
  const generativeEquipment = requirement.generativeEquipment || {};
  const selected = (furniture.selected || [])
    .filter((item) => Number(item.quantity || 0) > 0)
    .map((item) => item.name_zh || item.name || item.title)
    .filter(Boolean);
  const usageLabels = new Map(roomUsageOptions(room || {}).map((option) => [option.id, option.label]));
  const usage = (requirement.usage || []).map((item) => usageLabels.get(item) || item).filter(Boolean);
  const visualNotes = state.visualQuestions
    .filter((question) => String(question.room_id || "") === String(roomId))
    .map((question) => String(state.visualAnswers?.[question.question_id]?.custom || "").trim())
    .filter(Boolean);
  const roomNotes = [
    furniture.preferenceText,
    ...(furniture.preferenceTags || []),
    generativeEquipment.generationNotes,
    requirement.surfaces?.wallPreference,
    requirement.surfaces?.floorPreference,
    ...visualNotes,
  ].map((item) => String(item || "").trim()).filter(Boolean);
  const roomSummaryParts = [
    usage.length ? `用途：${usage.join("、")}` : "",
    selected.length ? `已選家具：${selected.join("、")}` : "",
    ...roomNotes,
  ].filter(Boolean);
  const wholeHouseNeeds = wholeHouseQuestionnaireNeeds();
  const fallbackUsed = roomSummaryParts.length === 0;
  const note = (fallbackUsed ? wholeHouseNeeds : roomSummaryParts).join("；");
  return {
    note,
    summary: note,
    source: fallbackUsed ? "whole_house_fallback" : "room_questionnaire",
    fallbackUsed,
    fallbackNotice: fallbackUsed ? "本房未填獨立需求，已套用全屋問卷與鎖定配置。" : "",
    wholeHouseNeeds,
    wholeHouseSummary: wholeHouseNeeds.join("；"),
    lockedFurniture: selected,
    usage,
    surfaces: requirement.surfaces || {},
    generativeEquipment,
  };
}



function renderRoomViewList() {
  element.renderRoomList.innerHTML = state.rooms.map((room) => {
    const saved = state.proposalReview.roomViews[room.id];
    return `
      <button type="button" data-render-room="${escapeHtml(room.id)}"
        class="${room.id === state.selectedRenderRoomId ? "is-active" : ""}">
        <span>${escapeHtml(room.label || "未命名空間")}</span>
        <small>${saved ? "視角已保存" : "使用建議視角"}</small>
      </button>
    `;
  }).join("");
}


function saveSelectedRoomView() {
  const room = state.rooms.find((item) => item.id === state.selectedRenderRoomId);
  if (!room) return;
  const camera = aiRenderViewer.getCameraState();
  state.proposalReview.roomViews[room.id] = {
    room_id: room.id,
    room_label: room.label,
    camera,
    scene_version: state.proposalReview.masterView?.scene_version,
    saved_at: new Date().toISOString(),
  };
  refreshConfigurationSnapshot();
  element.aiRenderStatus.textContent = `${room.label || "此房間"}視角已保存。`;
  renderRoomViewList();
  scheduleSave("ai_render");
}

function renderRemoteJobs() {
  element.remoteRenderJobs.innerHTML = state.proposalReview.jobs.map((job) => `
    <article>
      <strong>${escapeHtml(job.label || job.job_id || "渲染任務")}</strong>
      <span>${escapeHtml(job.status || "queued")}</span>
    </article>
  `).join("");
}

function renderPaletteResults() {
  if (!element.paletteRenderResults) return;
  const paletteJobs = (state.proposalReview.jobs || []).filter(
    (job) => job.mode === "palette_comparison",
  );
  element.paletteRenderResults.innerHTML = paletteJobs.map((job) => {
    const styleCardId = job.style_card_id || job.styleCardId || "";
    // base64 生圖只在記憶體(state.paletteRenderImages);重整後沒有 → 顯示提示。
    const imageUrl = state.paletteRenderImages?.[styleCardId]
      || job.image_url || job.output_url || job.preview_url || "";
    const placeholder = job.status === "failed"
      ? "生成失敗"
      : job.status === "completed"
        ? "已生成（重新整理後不保留預覽）"
        : "等待生成";
    return `
      <label class="rp-render-result">
        ${imageUrl
          ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(job.label || styleCardId)} 色卡渲染" />`
          : `<span class="rp-render-placeholder">${escapeHtml(placeholder)}</span>`}
        <span>
          <input type="radio" name="confirmed-render-style" value="${escapeHtml(styleCardId)}"
            ${styleCardId === state.proposalReview.confirmedStyleCardId ? "checked" : ""} />
          ${escapeHtml(job.label || styleCardId || "色卡任務")}
        </span>
      </label>
    `;
  }).join("");
  if (element.confirmRenderPalette) element.confirmRenderPalette.hidden = paletteJobs.length === 0;
}

function confirmRenderPalette() {
  const selected = element.paletteRenderResults?.querySelector(
    "input[name='confirmed-render-style']:checked",
  ) || $("input[name='confirmed-render-style']:checked");
  if (!selected?.value) {
    const message = "請先從 3 張生圖中選擇 1 張色卡。";
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = message;
    const status = $("#proposal-style-stage-status");
    if (status) status.textContent = message;
    return;
  }

  state.proposalReview.confirmedStyleCardId = selected.value;
  state.proposalReview.styleCardLockedAt = new Date().toISOString();
  state.proposalReview.masterView = {
    ...(state.proposalReview.masterView || {}),
    style_card_id: selected.value,
    configuration_snapshot_id: refreshConfigurationSnapshot().snapshot_id,
  };
  state.selectedRenderRoomId = state.proposalReview.representativeRoomId
    || state.selectedProposalRoomId
    || state.rooms[0]?.id
    || null;
  const completed = state.workflow.complete("proposal_review", {
    confirmed: true,
    masterView: state.proposalReview.masterView,
  });
  if (!completed) {
    const message = "第 7 步視角資料尚未完整，請重新確認逐房視角後再選色卡。";
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = message;
    const status = $("#proposal-style-stage-status");
    if (status) status.textContent = message;
    return;
  }
  seedRepresentativeRoomRenderFromPalette();
  scheduleSave("proposal_review");
  goTo("ai_render");
}

// 少生一張圖:第 7 步選中的那張色卡比較圖,就是「代表房 × 選定色卡」的全房生圖
// (同一鎖定視角截圖、同色卡、同 stage=full_render),等同第 8 步會為代表房生的初稿。
// 確認色卡時直接把它塞進 finalRooms[代表房] 當初稿,第 8 步就不用再為代表房生一次。
// base64 僅在記憶體(state.paletteRenderImages);重載後沒有就照常重生,與其他房一致。
function seedRepresentativeRoomRenderFromPalette() {
  const roomId = state.proposalReview.representativeRoomId;
  const cardId = state.proposalReview.confirmedStyleCardId;
  const image = state.paletteRenderImages?.[cardId];
  if (!roomId || !cardId || !image) return;
  state.proposalReview.finalRooms ||= {};
  if (state.proposalReview.finalRooms[roomId]?.submitted_at) return; // 已重生過就不覆蓋
  state.proposalReview.finalRooms[roomId] = {
    submitted_at: new Date().toISOString(),
    notes: "沿用第 7 步選定色卡的比較圖",
    image_data_url: image,
    model: null,
    notices: [],
    reused_from_palette: true, // 無伺服器端 lock_manifest;要改圖得整房重新生成
  };
  // 第 8 步直接落在還要生的房;若代表房是唯一房(全部已備)則標記此步完成。
  const nextPending = state.rooms.find(
    (item) => !state.proposalReview.finalRooms?.[item.id]?.submitted_at,
  );
  if (nextPending) state.selectedRenderRoomId = nextPending.id;
  else state.workflow.complete("ai_render", { confirmed: true, initial_room_renders: true });
}



function renderBriefSummaryRows(mode) {
  const activePack = STYLE_PACKS.find((item) => item.id === state.activeStylePackId);
  const selectedCard = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  return [
    ["本次任務", mode === "palette_comparison" ? "代表房三張色卡測試" : "全房間最終生圖"],
    ["全屋風格", activePack ? `${activePack.styleLabel} / ${activePack.name}` : "未選擇"],
    ["最終配置", `${state.rooms.length} 個房間，已依問卷確認配置`],
    ["鎖定視角", `${Object.keys(state.proposalReview.roomViews || {}).length} / ${state.rooms.length} 個房間`],
    ["確認色卡", selectedCard ? selectedCard.name : "本次將比較三張同風格色卡"],
    ["問卷資料", "已合併逐房摘要與全屋共用需求"],
  ];
}

function renderBriefHasSpatialConflict(notes) {
  return /移(?:動|到)|搬|拆|打通|開放式|走道|門口|窗邊|牆|改格局|重新擺/.test(String(notes || ""));
}

function renderPromptKeywords(mode, action = "initial") {
  const roomId = mode === "room_final"
    ? state.selectedRenderRoomId
    : state.proposalReview.representativeRoomId;
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  const context = roomQuestionnaireContext(roomId);
  const selectedCard = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  return [...new Set([
    room?.label,
    selectedCard?.name,
    ...(context.usage || []),
    context.note,
    ...(context.wholeHouseNeeds || []),
    ...context.lockedFurniture,
    action === "revision" ? "本房唯一一次圖片修改" : "本房首次生圖",
    "保留已確認空間、結構、家具位置與第 7 步鎖定視角",
  ].filter((item) => String(item || "").trim()).map((item) => String(item).trim()))];
}

function openRenderBriefDialog(mode, action = "initial") {
  if (!element.renderBriefDialog) return;
  proposalRuntimeState.pendingBriefMode = mode;
  proposalRuntimeState.pendingBriefAction = action;
  const summaryRows = [
    ...renderBriefSummaryRows(mode),
    ["生圖動作", action === "revision" ? "使用本房唯一一次修改額度" : "產生本房初稿"],
  ];
  const keywords = renderPromptKeywords(mode, action);
  element.renderBriefSummary.innerHTML = `
    <div class="rp-render-brief-facts">
      ${summaryRows.map(([label, value]) => (
        `<div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`
      )).join("")}
    </div>
    <section class="rp-render-brief-keywords" aria-labelledby="render-brief-keywords-title">
      <h3 id="render-brief-keywords-title">本次生圖重點</h3>
      <div>${keywords.map((keyword) => `<span>${escapeHtml(keyword)}</span>`).join("")}</div>
    </section>
    <p class="rp-render-brief-lock-note"><strong>可修改範圍</strong> 可補充材質、色彩、光線與軟裝；房間尺寸、牆、門、窗、固定家具位置及已確認視角會維持不變。</p>`;
  element.renderBriefNotes.value = "";
  element.renderBriefWarning.hidden = true;
  delete element.renderBriefWarning.dataset.acknowledged;
  if (typeof element.renderBriefDialog.showModal === "function") element.renderBriefDialog.showModal();
  else element.renderBriefDialog.setAttribute("open", "");
}

function closeRenderBriefDialog() {
  if (!element.renderBriefDialog) return;
  if (typeof element.renderBriefDialog.close === "function") element.renderBriefDialog.close();
  else element.renderBriefDialog.removeAttribute("open");
  proposalRuntimeState.pendingBriefMode = null;
  proposalRuntimeState.pendingBriefAction = "initial";
}


async function confirmRenderBriefAndSubmit() {
  const mode = proposalRuntimeState.pendingBriefMode;
  if (!mode) return;
  const notes = element.renderBriefNotes.value;
  if (renderBriefHasSpatialConflict(notes) && !element.renderBriefWarning.dataset.acknowledged) {
    element.renderBriefWarning.hidden = false;
    element.renderBriefWarning.textContent = "偵測到可能改變格局、門窗、家具位置或空間大小的描述。送出後仍會保留第 4 步結構、已鎖定家具與確認視角；系統只會請生圖服務在可行範圍內調整材質、氛圍與軟裝。再次按確認即可送出。";
    element.renderBriefWarning.dataset.acknowledged = "true";
    return;
  }
  const brief = confirmedRenderBrief(mode, notes);
  closeRenderBriefDialog();
  if (mode === "palette_comparison") await requestPaletteRenders(brief);
  else await submitRoomRenders(brief);
  scheduleSave("ai_render");
}





function ensureProposalStyleStage() {
  let panel = $("#proposal-style-stage");
  if (panel) return panel;
  const sidebar = $("#proposal-review-step .rp-control-pane") || $("#proposal-review-step");
  if (!sidebar) return null;
  panel = document.createElement("section");
  panel.id = "proposal-style-stage";
  panel.className = "rp-editor-box rp-proposal-style-stage";
  panel.innerHTML = `
    <span class="eyebrow">\u7b2c 7 \u6b65\uff1a\u4ee3\u8868\u623f\u8272\u5361\u6bd4\u8f03</span>
    <h3>\u9078\u4e00\u9593\u4ee3\u8868\u623f\uff0c\u7522\u751f 3 \u7a2e\u8272\u5361\u65b9\u6848</h3>
    <p class="rp-field-hint">\u6240\u6709\u623f\u9593\u89d2\u5ea6\u5df2\u78ba\u8a8d\u3002\u78ba\u5b9a\u8272\u5361\u5f8c\u7121\u6cd5\u66f4\u6539\uff0c\u7b2c 8 \u6b65\u6703\u4ee5\u540c\u4e00\u8272\u5361\u9010\u623f\u751f\u5716\u3002</p>
    <label>\u4ee3\u8868\u623f<select id="proposal-representative-room"></select></label>
    <div id="proposal-representative-context" class="rp-proposal-context"></div>
    <button id="open-palette-render-brief" type="button" class="secondary-action">\u7522\u751f 3 \u5f35\u8272\u5361\u6bd4\u8f03\u5716</button>
    <div id="proposal-palette-render-options" class="rp-render-palette-options"></div>
    <div id="proposal-palette-render-results" class="rp-render-palette-results"></div>
    <button id="proposal-confirm-render-palette" type="button" class="primary-action" hidden>\u78ba\u5b9a\u8272\u5361\u4e26\u9032\u5165\u7b2c 8 \u6b65</button>
    <p id="proposal-style-stage-status" class="rp-field-hint" aria-live="polite"></p>`;
  sidebar.append(panel);
  element.paletteRenderOptions = panel.querySelector("#proposal-palette-render-options");
  element.paletteRenderResults = panel.querySelector("#proposal-palette-render-results");
  element.confirmRenderPalette = panel.querySelector("#proposal-confirm-render-palette");
  panel.querySelector("#proposal-representative-room")?.addEventListener("change", (event) => {
    state.proposalReview.representativeRoomId = event.target.value || null;
    state.selectedProposalRoomId = state.proposalReview.representativeRoomId;
    selectProposalRoomView(state.selectedProposalRoomId);
    renderProposalStyleStage();
    scheduleSave("proposal_review");
  });
  panel.querySelector("#open-palette-render-brief")?.addEventListener("click", () => openRenderBriefDialog("palette_comparison"));
  panel.querySelector("#proposal-confirm-render-palette")?.addEventListener("click", confirmRenderPalette);
  // 色卡比較縮圖點擊 → 放大到本步(第 7 步)的 3D 疊層。綁在這個動態產生的實際容器上,
  // 不用 element.paletteRenderResults(它會被重指、且 init 綁的是第 8 步靜態容器)。
  panel.querySelector("#proposal-palette-render-results")?.addEventListener("click", (event) => {
    const img = event.target?.closest?.("img");
    if (!img?.getAttribute("src")) return;
    const label = (img.getAttribute("alt") || "").replace(/\s*色卡渲染$/, "").trim();
    showProposalPaletteImageEnlarged(img.src, label || "色卡");
  });
  return panel;
}

function renderProposalStyleStage() {
  const panel = ensureProposalStyleStage();
  if (!panel) return;
  const ready = state.rooms.length > 0 && state.rooms.every((room) => state.proposalReview.roomViews?.[room.id]);
  panel.hidden = !ready;
  if (!ready) return;
  const representativeId = state.proposalReview.representativeRoomId || state.selectedProposalRoomId || state.rooms[0]?.id;
  state.proposalReview.representativeRoomId = representativeId;
  const select = panel.querySelector("#proposal-representative-room");
  select.innerHTML = state.rooms.map((room) => `<option value="${escapeHtml(room.id)}" ${String(room.id) === String(representativeId) ? "selected" : ""}>${escapeHtml(room.label)}</option>`).join("");
  const room = state.rooms.find((item) => String(item.id) === String(representativeId));
  const context = roomQuestionnaireContext(representativeId);
  panel.querySelector("#proposal-representative-context").innerHTML = `<strong>${escapeHtml(room?.label || "")}</strong><span>${escapeHtml(questionnaireContextLabel(context))}：${escapeHtml(context.note || "使用已鎖定配置")}</span>${context.fallbackUsed ? `<span>${escapeHtml(context.fallbackNotice)}</span>` : ""}<span>已鎖定家具：${escapeHtml(context.lockedFurniture.join("、") || "未鎖定")}</span>`;
  renderPaletteOptions();
  renderPaletteResults();
  // 每個專案只能生一次:生成後停用產圖按鈕。
  const paletteGenerateBtn = panel.querySelector("#open-palette-render-brief");
  if (paletteGenerateBtn) {
    paletteGenerateBtn.disabled = state.proposalReview.paletteGenerated === true;
    paletteGenerateBtn.textContent = state.proposalReview.paletteGenerated
      ? "色卡比較圖已生成（每專案限一次）"
      : "產生 3 張色卡比較圖";
  }
  panel.querySelector("#proposal-style-stage-status").textContent = state.proposalReview.confirmedStyleCardId
    ? "\u8272\u5361\u5df2\u9396\u5b9a\uff0c\u5373\u5c07\u9032\u5165\u7b2c 8 \u6b65\u9010\u623f\u751f\u5716\u3002"
    : "\u8acb\u5148\u7522\u751f\u4ee3\u8868\u623f\u7684 3 \u5f35\u8272\u5361\u6bd4\u8f03\u5716\uff0c\u518d\u9078\u4e00\u5f35\u78ba\u5b9a\u3002";
}

// Steps 7 and 8 deliberately have different responsibilities.















function renderPaletteOptions() {
  const host = element.paletteRenderOptions;
  if (!host) return;
  host.innerHTML = paletteChoicesForActiveStyle().map((pack) => {
    const previewImage = pack.sourceImage || pack.referenceImage || pack.image || "";
    const palette = pack.palette || [];
    return `
      <label class="rp-render-palette-card">
        <input type="radio" name="palette-choice" value="${escapeHtml(pack.id)}" />
        <span class="rp-render-palette-media">
          ${previewImage ? `<img class="rp-render-palette-image" src="${escapeHtml(previewImage)}" alt="${escapeHtml(`${pack.name} 空間配色預覽`)}" loading="lazy" />` : ""}
          <span class="rp-style-swatches" aria-hidden="true">${palette.map((color) => `<i style="background:${escapeHtml(color)}"></i>`).join("")}</span>
        </span>
        <span class="rp-render-palette-copy"><strong>${escapeHtml(pack.name)}</strong><small>查看此色卡的空間效果</small></span>
      </label>`;
  }).join("");
}





function renderFinalRoomWorkflow() {
  const host = element.roomRenderSection;
  const card = STYLE_PACKS.find((pack) => pack.id === state.proposalReview.confirmedStyleCardId);
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRenderRoomId)) || state.rooms[0];
  if (!host || !room || !card) return;
  const context = roomQuestionnaireContext(room.id);
  const submitted = state.proposalReview.finalRooms?.[room.id];
  const initialComplete = Boolean(submitted?.submitted_at);
  const revised = Boolean(submitted?.revision_submitted_at);
  const finalImageUrl = submitted?.revision_image_data_url || submitted?.image_data_url || "";
  const nightImageUrl = submitted?.night_image_data_url || "";   // 客廳才有夜間圖
  const allInitialComplete = state.rooms.length > 0
    && state.rooms.every((item) => state.proposalReview.finalRooms?.[item.id]?.submitted_at);
  const anyPending = state.rooms.some((item) => !state.proposalReview.finalRooms?.[item.id]?.submitted_at);
  // 全部初稿都完成、但客廳還缺夜間圖時,一鍵按鈕仍要留著——否則代表房那張夜間圖
  // 永遠沒有觸發點(它不算「未完成房間」)。
  const nightPendingCount = roomsMissingNightRender().length;
  host.hidden = false;
  host.innerHTML = `<section class="rp-final-render-flow">
    <span class="eyebrow">第 8 步：逐房生圖</span>
    <h3>${escapeHtml(room.label)} 以「${escapeHtml(card.name)}」生成</h3>
    <p class="rp-field-hint">初稿會依問卷、已鎖定家具、材質、色卡與第 7 步視角送出。全房初稿完成後，每張圖可再提出一次修改；不能修改空間大小、牆、門窗、固定家具位置或視角。</p>
    <div class="rp-render-room-list">${state.rooms.map((item) => {
      const itemState = state.proposalReview.finalRooms?.[item.id] || {};
      const status = itemState.revision_submitted_at ? "已修改一次" : (itemState.submitted_at ? "初稿完成" : "待初稿");
      return `<button type="button" data-final-render-room="${escapeHtml(item.id)}" class="${String(item.id) === String(room.id) ? "is-active" : ""}">${escapeHtml(item.label)}<small>${status}</small></button>`;
    }).join("")}</div>
    ${anyPending || nightPendingCount ? `<button id="submit-all-room-renders" type="button" class="secondary-action rp-final-render-bulk">${anyPending ? "一鍵生成全部未完成房間" : `補生客廳夜間燈光圖（${nightPendingCount} 張）`}</button>` : ""}
    <div class="rp-final-render-summary">
      <strong>${escapeHtml(questionnaireContextLabel(context))}與生圖詞彙</strong><p>${escapeHtml(renderPromptKeywords("room_final", initialComplete ? "revision" : "initial").join(" / ") || "使用已鎖定配置")}</p>
      ${context.fallbackUsed ? `<p class="rp-context-fallback">${escapeHtml(context.fallbackNotice)}</p>` : ""}
      <strong>已鎖定家具</strong><p>${escapeHtml(context.lockedFurniture.join("、") || "未鎖定")}</p>
    </div>
    ${initialComplete ? `<div class="rp-final-render-thumbs">${finalImageUrl ? `<button type="button" class="rp-final-render-thumb" data-render-thumb="day"><img src="${escapeHtml(finalImageUrl)}" alt="${escapeHtml(room.label)} 生圖" loading="lazy" /><small>${revised ? "已修改" : "日光"}</small></button>` : ""}${nightImageUrl ? `<button type="button" class="rp-final-render-thumb" data-render-thumb="night"><img src="${escapeHtml(nightImageUrl)}" alt="${escapeHtml(room.label)} 夜間生圖" loading="lazy" /><small>夜間</small></button>` : ""}</div>` : ""}
    ${!initialComplete ? `<label>本房初稿補充<textarea id="final-room-adjustment" rows="3" placeholder="例：採光柔和、木質更溫潤、閱讀角更明確。"></textarea></label><button id="submit-final-room-render" type="button" class="primary-action">確認本房並生圖</button>` : ""}
    ${initialComplete && !allInitialComplete ? `<p class="rp-success-message">本房初稿已送出。請完成其他房間初稿後，再回來做每張圖一次修改。</p>` : ""}
    ${initialComplete && allInitialComplete && !revised ? `<label>針對這張圖修改一次<textarea id="final-room-adjustment" rows="3" placeholder="例：讓燈光更暖、減少雜物、窗邊更明亮。不能修改空間、牆、門窗、固定家具或視角。"></textarea></label><button id="request-room-revision" type="button" class="primary-action">確認修改詞彙並重新生圖</button>` : ""}
    ${revised ? `<p class="rp-success-message">本房已使用一次修改額度。</p>` : ""}
    ${allInitialComplete ? `<button id="download-engineering-delivery" type="button" class="secondary-action">建立並查看成果包（含工程報價與預算）</button>` : ""}
  </section>`;
  host.querySelectorAll("[data-final-render-room]").forEach((button) => button.addEventListener("click", () => selectRenderRoom(button.dataset.finalRenderRoom)));
  host.querySelector("#submit-final-room-render")?.addEventListener("click", () => openRenderBriefDialog("room_final", "initial"));
  host.querySelector("#request-room-revision")?.addEventListener("click", () => openRenderBriefDialog("room_final", "revision"));
  host.querySelector("#submit-all-room-renders")?.addEventListener("click", submitAllRoomRenders);
  host.querySelector("#download-engineering-delivery")?.addEventListener("click", downloadEngineeringDelivery);
  // 生圖結果縮圖點擊 → 放大到左側 3D 疊層(日光/夜間各一張);跟著目前選取房間走。
  host.querySelectorAll("[data-render-thumb]").forEach((btn) => btn.addEventListener("click", () => {
    const url = btn.dataset.renderThumb === "night" ? nightImageUrl : finalImageUrl;
    const label = btn.dataset.renderThumb === "night" ? `${room.label}（夜間）` : room.label;
    if (url) showRenderImageEnlarged(url, label);
  }));
  updateAiRenderImageStage();
}

function selectRenderRoom(roomId) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  if (!room) return;
  const view = validProposalRoomView(room);
  state.selectedRenderRoomId = room.id;
  aiRenderViewer.lockRenderCamera(true);
  aiRenderViewer.setCameraState(view?.camera || roomCameraSuggestion(room));
  if (element.aiRenderViewTitle) {
    element.aiRenderViewTitle.textContent = `${room.label || "未命名空間"}｜已確認視角`;
  }
  if (element.aiRenderStatus) {
    element.aiRenderStatus.textContent = view
      ? "已沿用第 7 步確認的視角；請確認本房問卷與生圖詞彙。"
      : "此房尚未確認第 7 步視角。";
  }
  renderFinalRoomWorkflow();
}

async function prepareAiRender() {
  if (!state.sceneData) return;
  const missingViews = state.rooms.filter((room) => !validProposalRoomView(room));
  if (!state.proposalReview.confirmedStyleCardId || missingViews.length) {
    state.selectedProposalRoomId = missingViews[0]?.id || state.selectedProposalRoomId || state.rooms[0]?.id || null;
    if (element.aiRenderStatus) {
      element.aiRenderStatus.textContent = missingViews.length
        ? `請先回第 7 步確認 ${missingViews.map((room) => room.label).join("、")} 的視角。`
        : "請先回第 7 步確認代表房色卡。";
    }
    throw new Error("第 7 步尚有視角或色卡未確認。");
  }

  $("#request-palette-renders")?.closest(".rp-editor-box")?.setAttribute("hidden", "");
  // 第 8 步入口要整場重建（viewer 無 GLB 快取），沒有遮罩會像當機。
  beginPlacementBusy("正在準備第 8 步渲染場景，請稍候…");
  try {
    await aiRenderViewer.loadScene(state.sceneData);
  } finally {
    endPlacementBusy();
  }
  aiRenderViewer.lockRenderCamera(true);
  const selectedRoom = state.rooms.find(
    (room) => String(room.id) === String(state.selectedRenderRoomId),
  );
  const firstPendingRoom = state.rooms.find(
    (room) => !state.proposalReview.finalRooms?.[room.id]?.submitted_at,
  );
  const room = selectedRoom || firstPendingRoom || state.rooms[0];
  if (room) selectRenderRoom(room.id);
  renderRemoteJobs();

  if (!element.aiRenderProviderState) return;
  element.aiRenderProviderState.textContent = "正在檢查生圖服務…";
  try {
    const status = await api("/api/ai-render/status");
    element.aiRenderProviderState.textContent = status.configured
      ? `生圖服務已連接｜${status.model || "目前模型"}`
      : "尚未設定生圖服務";
  } catch (error) {
    element.aiRenderProviderState.textContent = `無法取得生圖服務狀態：${errorMessage(error)}`;
  }
  restoreDeliveryProposalPanel();
  updateAiRenderImageStage();
}



function confirmedRenderBrief(mode, notes) {
  const action = proposalRuntimeState.pendingBriefAction || "initial";
  const brief = {
    version: (state.proposalReview.renderBriefs || []).length + 1,
    mode,
    render_action: action,
    room_id: mode === "room_final" ? state.selectedRenderRoomId : state.proposalReview.representativeRoomId,
    user_notes: String(notes || "").trim(),
    prompt_keywords: renderPromptKeywords(mode, action),
    spatial_override_warning: renderBriefHasSpatialConflict(notes),
    confirmed_at: new Date().toISOString(),
  };
  state.proposalReview.renderBriefs = [...(state.proposalReview.renderBriefs || []), brief];
  return brief;
}

async function requestPaletteRenders(renderBrief = null) {
  const roomId = state.proposalReview.representativeRoomId;
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  const view = state.proposalReview.roomViews?.[roomId];
  const cards = paletteChoicesForActiveStyle();
  const status = $("#proposal-style-stage-status");
  if (!room || !view || !cards.length) {
    if (status) status.textContent = "請先選定代表房並確認視角，再產生色卡比較圖。";
    return;
  }
  // 每個專案只能生一次:已生成就不再送請求(後端亦以 409 把關)。
  if (state.proposalReview.paletteGenerated) {
    if (status) status.textContent = "此專案的色卡比較圖已生成過，每個專案只能生成一次。";
    renderPaletteResults();
    return;
  }
  // 代表房 3D 視角截圖:當 img2img 參考,鎖住家具與格局不動(同第 8 步作法)。
  proposalViewer.setCameraState(view.camera);
  const referencePng = proposalViewer.capturePng();
  // setCameraState() 內部走 setViewMode(),會把 cameraLocked 歸零(scene_viewer.js:3635)。
  // 本步的視角已在「完成全部視角」時鎖定(:17200),截個圖不該順手解鎖,截完鎖回來。
  // 只鎖這裡不改 setCameraState 本身:第 8 步 viewer 沒有解鎖工具列,在那裡收緊會把
  // 使用者卡在完全不能轉、不能縮放的畫面。
  proposalViewer.lockRenderCamera(true);
  if (status) status.textContent = `正在為「${room.label || "代表房"}」一次送出 ${cards.length} 張色卡比較圖…`;
  try {
    const result = await api(`/api/projects/${state.projectId}/palette-renders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        scene: state.sceneData,
        room: {
          room_id: roomId,
          room_label: room.label,
          room_type: room.type || room.room_type || null,   // 後端據此補浴室/廚房/陽台的固定設備提示
          reference_png_data_url: referencePng,
          note: String(renderBrief?.user_notes || "").trim(),
        },
        style_card_ids: cards.map((card) => card.id),
      }),
    });
    applyPaletteRenderResults(result, cards, roomId);
    const done = (result.results || []).filter((item) => item.status === "completed").length;
    if (status) {
      status.textContent = done
        ? `已為代表房一次產生 ${done} 張色卡比較圖；選一張後確定進入第 8 步（每專案只生一次）。`
        : "色卡比較圖生成失敗，請稍後再試。";
    }
  } catch (error) {
    // 已生成過(409):鎖定 UI、不再重送,不視為錯誤。
    if (error?.status === 409 || error?.detail?.code === "palette_already_generated") {
      state.proposalReview.paletteGenerated = true;
      renderProposalStyleStage();
      if (status) status.textContent = "此專案的色卡比較圖已生成過，每個專案只能生成一次。";
      return;
    }
    if (status) status.textContent = `色卡比較圖建立失敗：${errorMessage(error)}`;
  }
}

function applyPaletteRenderResults(result, cards, roomId) {
  const results = result?.results || [];
  const images = {};
  const jobs = results.map((item) => {
    const cardId = item.style_card_id || "";
    // base64 只放記憶體(state.paletteRenderImages),不進 jobs/持久化,避免撐爆 workflow。
    if (item.image_data_url) images[cardId] = item.image_data_url;
    return {
      mode: "palette_comparison",
      room_id: roomId,
      style_card_id: cardId,
      status: item.status,
      label: cards.find((card) => card.id === cardId)?.name || cardId,
    };
  });
  state.paletteRenderImages = images;
  state.proposalReview.jobs = (state.proposalReview.jobs || [])
    .filter((job) => job.mode !== "palette_comparison")
    .concat(jobs);
  // 有任一張成功就鎖定(後端同步鎖定);全失敗不鎖,允許重試。
  if (result?.already_generated || results.some((item) => item.status === "completed")) {
    state.proposalReview.paletteGenerated = true;
  }
  renderPaletteResults();
  renderProposalStyleStage();
  scheduleSave("proposal_review");
}


/*
 * The live experience follows one path: room views -> representative-room
 * palette -> one-at-a-time final renders.
 */
async function prepareProposalReview() {
  if (!state.sceneData) {
    element.masterViewStatus.textContent = "尚未有可用的 3D 場景，請返回第 6 步確認方案後再進入。";
    return;
  }
  // 只經快取入口載入:同一場景版本切色卡不重載(in-flight 去重),真正需要
  // 載入(6→7 首次、換方案、場景重建)才顯示等待遮罩並重載。
  if (!(await ensureProposalSceneLoaded())) return;
  const masterCamera = state.proposalReview.masterView?.camera;
  if (!String(masterCamera?.preset || "").startsWith("full-room-v2")) {
    const firstRoom = state.rooms[0];
    state.proposalReview.masterView = {
      camera: firstRoom ? roomCameraSuggestion(firstRoom) : proposalViewer.getCameraState(),
      scene_version: currentSceneVersion(),
      locked_at: new Date().toISOString(),
    };
  }
  state.selectedProposalRoomId ||= state.rooms[0]?.id || null;
  state.selectedProposalRoomCandidateIndex ??= 0;
  const selectedRoom = state.rooms.find((room) => String(room.id) === String(state.selectedProposalRoomId));
  if (selectedRoom) {
    const savedView = validProposalRoomView(selectedRoom);
    const candidate = proposalRoomCameraCandidates(selectedRoom)[Number(state.selectedProposalRoomCandidateIndex || 0)];
    proposalViewer.setCameraState(savedView?.camera || candidate?.camera || roomCameraSuggestion(selectedRoom));
  }
  if (state.rooms.some((room) => !validProposalRoomView(room))) {
    state.proposalReview.viewsConfirmedAt = null;
  }
  proposalViewer.lockRenderCamera(Boolean(state.proposalReview.viewsConfirmedAt));
  renderProposalRoomViewPanel();
  renderProposalStyleStage();
  scheduleSave("proposal_review");
}




function paletteChoicesForActiveStyle() {
  const current = STYLE_PACKS.find((pack) => pack.id === state.activeStylePackId) || STYLE_PACKS[0];
  const family = STYLE_PACKS.filter((pack) => pack.styleId === current?.styleId);
  const choices = family.length >= 3 ? family : [current, ...STYLE_PACKS.filter((pack) => pack.id !== current?.id)];
  return choices.filter(Boolean).slice(0, 3);
}

function syncProjectRevision(result) {
  if (!state.project || !result?.updated_at) return;
  state.project = {
    ...state.project,
    revision: result.revision ?? state.project.revision,
    updated_at: result.updated_at,
  };
}

function aiRenderSceneForBrief(renderBrief = null) {
  const stylePack = STYLE_PACKS.find((pack) => pack.id === state.proposalReview.confirmedStyleCardId);
  const scene = state.sceneData || {};
  const requirement = scene.requirement || {};
  const constraints = requirement.constraints || {};
  const notes = [
    ...(Array.isArray(constraints.notes) ? constraints.notes : []),
    renderBrief?.user_notes,
  ].filter((item) => String(item || "").trim());
  return {
    ...scene,
    design_choices: {
      ...(scene.design_choices || {}),
      style_card_id: stylePack?.id || state.proposalReview.confirmedStyleCardId,
    },
    style: {
      ...(scene.style || {}),
      style_id: stylePack?.styleId || scene.style?.style_id || requirement.style || "",
      style_name_zh: stylePack?.styleLabel || scene.style?.style_name_zh || "",
    },
    style_card: stylePack ? {
      ...(scene.style_card || {}),
      card_id: stylePack.id,
      name_zh: stylePack.name,
      palette_hex: stylePack.palette,
    } : scene.style_card,
    requirement: {
      ...requirement,
      style: stylePack?.styleId || requirement.style || "",
      constraints: {
        ...constraints,
        notes,
      },
    },
  };
}

function aiRenderRoomPayload(room, view, renderBrief = null) {
  aiRenderViewer.setCameraState(view.camera || view);
  const context = roomQuestionnaireContext(room.id);
  const note = [
    context.note,
    renderBrief?.user_notes,
    ...(renderBrief?.prompt_keywords || []),
  ].filter((item) => String(item || "").trim()).join("；");
  return {
    room_id: room.id,
    room_label: room.label,
    room_type: room.type || room.room_type || null,   // 後端據此判客廳→多出夜間圖
    camera: view.camera || view,
    note,
    reference_png_data_url: aiRenderViewer.capturePng(),
  };
}

function aiRenderSubmissionPayload(room, view, renderBrief = null) {
  const configuration = lockedConfigurationSnapshot();
  return {
    project_id: state.projectId,
    configuration_snapshot: configuration,
    render_brief: renderBrief,
    scene: aiRenderSceneForBrief(renderBrief),
    rooms: [aiRenderRoomPayload(room, view, renderBrief)],
  };
}

async function submitRoomRenders(renderBrief = null) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRenderRoomId));
  const view = room && state.proposalReview.roomViews?.[room.id];
  if (!room || !view) return;
  let action = renderBrief?.render_action === "revision" ? "revision" : "initial";
  const currentRoomState = state.proposalReview.finalRooms?.[room.id] || {};
  // 沿用色卡圖的代表房沒有伺服器端 lock_manifest,改圖無圖可改;要改就整房重新生成
  // (此時才真的消耗一次生成),之後就有 lock_manifest 可正常改圖。
  if (action === "revision" && currentRoomState.reused_from_palette && !currentRoomState.image_id) {
    action = "initial";
  }
  if (action === "revision" && currentRoomState.revision_submitted_at) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "此房已使用一次修改額度。";
    return;
  }
  if (action === "revision" && !currentRoomState.image_data_url) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "請先完成此房初稿，再提出一次修改。";
    return;
  }
  // 一張一張生不用全螢幕過場動畫(使用者定案);只給文字狀態,一鍵全生才用等待遮罩。
  if (element.aiRenderStatus) element.aiRenderStatus.textContent = "生圖中，請稍候…";
  try {
    state.proposalReview.finalRooms ||= {};
    if (action === "revision") {
      const result = await api(`/api/projects/${state.projectId}/ai-renders/${encodeURIComponent(room.id)}/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback: renderBrief?.user_notes || renderBrief?.prompt_keywords?.join("；") || "請依確認詞彙微調此張圖。",
          image_data_url: currentRoomState.revision_image_data_url || currentRoomState.image_data_url,
        }),
      });
      syncProjectRevision(result);
      state.proposalReview.finalRooms[room.id] = {
        ...currentRoomState,
        revision_submitted_at: new Date().toISOString(),
        revision_notes: renderBrief?.user_notes || "",
        revision_image_id: result.result?.image_id || null,
        revision_image_data_url: result.result?.image_data_url || currentRoomState.image_data_url,
        revision_model: result.result?.model || null,
        revision_notices: result.result?.notices || [],
        revision_brief_version: renderBrief?.version || null,
      };
    } else {
      const result = await api(`/api/projects/${state.projectId}/ai-renders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(aiRenderSubmissionPayload(room, view, renderBrief)),
      });
      syncProjectRevision(result);
      const renderResult = (result.results || []).find((item) => String(item.room_id) === String(room.id)) || result.results?.[0] || {};
      if (renderResult.status !== "completed" || !renderResult.image_data_url) {
        throw new Error((renderResult.notices || []).join("；") || "AI render failed.");
      }
      state.proposalReview.finalRooms[room.id] = {
        ...currentRoomState,
        submitted_at: currentRoomState.submitted_at || new Date().toISOString(),
        notes: renderBrief?.user_notes || "",
        image_id: renderResult.image_id || null,
        image_data_url: renderResult.image_data_url,
        model: renderResult.model || null,
        notices: renderResult.notices || [],
        night_image_id: renderResult.night_image_id || null,
        night_image_data_url: renderResult.night_image_data_url || null,
        night_model: renderResult.night_model || null,
        brief_version: renderBrief?.version || null,
      };
    }
    const nextRoom = state.rooms.find((item) => !state.proposalReview.finalRooms?.[item.id]?.submitted_at);
    if (nextRoom) state.selectedRenderRoomId = nextRoom.id;
    else state.workflow.complete("ai_render", { confirmed: true, initial_room_renders: true });
    renderFinalRoomWorkflow();
    // 生圖完成即把這張圖放到左側 3D 疊層呈現(取代舊的面板內嵌,避免排版跑掉)。
    const renderedImage = state.proposalReview.finalRooms?.[room.id]?.revision_image_data_url
      || state.proposalReview.finalRooms?.[room.id]?.image_data_url;
    if (renderedImage) showRenderImageEnlarged(renderedImage, room.label);
    scheduleSave("ai_render");
  } catch (error) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = `生圖失敗：${errorMessage(error)}`;
  }
}

// 一鍵全部生圖:對所有已鎖視角但還沒生的房(代表房若已沿用色卡圖則跳過)一次併發送出。
// 一次全生才顯示全螢幕等待動畫(單張生圖不顯示,使用者定案)。客廳會多回一張夜間圖。
//
// 判客廳的規則要跟後端 ai_render_service._is_living_room 一致:room_type 權威、
// 中文房名「客廳」後援。兩邊不一致會出現「後端生了夜間圖但前端不去拿」之類的落差。
function isLivingRoomForRender(room = {}) {
  const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
  return type === "living_room" || /客廳/.test(String(room.label || room.name || ""));
}

// 有日光初稿、卻還沒有夜間圖的客廳。兩種來源:(a) 代表房沿用第 7 步色卡圖當初稿,
// 從沒進過全房生圖;(b) 先前整房生過但夜景那次失敗(只回 night_notices)。
function roomsMissingNightRender() {
  return state.rooms.filter((room) => {
    const final = state.proposalReview.finalRooms?.[room.id];
    if (!final?.submitted_at || final.night_image_data_url) return false;
    return isLivingRoomForRender(room) && Boolean(validProposalRoomView(room));
  });
}

async function submitAllRoomRenders() {
  const pending = state.rooms.filter(
    (item) => validProposalRoomView(item) && !state.proposalReview.finalRooms?.[item.id]?.submitted_at,
  );
  const nightPending = roomsMissingNightRender();
  if (!pending.length && !nightPending.length) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "所有已鎖視角的房間都已生圖。";
    return;
  }
  const rooms = [
    ...pending.map((item) => aiRenderRoomPayload(item, state.proposalReview.roomViews[item.id])),
    // 代表房的日光初稿沿用第 7 步色卡圖,不會再進上面的 pending;夜間圖沒人生過,
    // 用 night_only 只補那一張(省一次生成)。夜景先前失敗的房也走同一條補生路徑。
    ...nightPending.map((item) => ({
      ...aiRenderRoomPayload(item, state.proposalReview.roomViews[item.id]),
      night_only: true,
      // 夜景是日光成圖的重打光,不是重畫:這條路徑的日光圖只在前端(代表房沿用的
      // 色卡圖),要一起送後端才有圖可打光;缺圖時後端退回 3D 截圖。
      day_image_data_url: state.proposalReview.finalRooms?.[item.id]?.image_data_url || null,
    })),
  ];
  beginPlacementBusy(`正在一次生成 ${rooms.length} 個房間的寫實圖，請稍候…（依房間數與模型速度可能需一至數分鐘）`);
  if (element.aiRenderStatus) element.aiRenderStatus.textContent = `一鍵生圖中（${rooms.length} 房），請稍候…`;
  try {
    const result = await api(`/api/projects/${state.projectId}/ai-renders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: state.projectId,
        configuration_snapshot: lockedConfigurationSnapshot(),
        scene: aiRenderSceneForBrief(null),
        rooms,
      }),
    });
    syncProjectRevision(result);
    state.proposalReview.finalRooms ||= {};
    let done = 0;
    let nightDone = 0;
    for (const row of result.results || []) {
      if (row.status !== "completed") continue;
      if (row.night_only) {
        // 只補夜間圖:保留既有日光初稿(代表房那張色卡圖)，不覆蓋 submitted_at。
        if (!row.night_image_data_url) continue;
        const current = state.proposalReview.finalRooms[row.room_id];
        if (!current) continue;
        nightDone += 1;
        state.proposalReview.finalRooms[row.room_id] = {
          ...current,
          night_image_id: row.night_image_id || null,
          night_image_data_url: row.night_image_data_url,
          night_model: row.night_model || null,
        };
        continue;
      }
      if (!row.image_data_url) continue;
      done += 1;
      state.proposalReview.finalRooms[row.room_id] = {
        ...(state.proposalReview.finalRooms[row.room_id] || {}),
        submitted_at: new Date().toISOString(),
        image_id: row.image_id || null,
        image_data_url: row.image_data_url,
        model: row.model || null,
        notices: row.notices || [],
        night_image_id: row.night_image_id || null,
        night_image_data_url: row.night_image_data_url || null,
        night_model: row.night_model || null,
      };
    }
    const failed = (result.results || []).length - done - nightDone;
    const nextRoom = state.rooms.find((item) => !state.proposalReview.finalRooms?.[item.id]?.submitted_at);
    if (nextRoom) state.selectedRenderRoomId = nextRoom.id;
    else state.workflow.complete("ai_render", { confirmed: true, initial_room_renders: true });
    renderFinalRoomWorkflow();
    if (element.aiRenderStatus) {
      const nightNote = nightDone ? `，並補上 ${nightDone} 張客廳夜間圖` : "";
      element.aiRenderStatus.textContent = failed
        ? `一鍵生圖完成 ${done} 房、失敗 ${failed} 房${nightNote}；失敗的可單獨重試。`
        : `已一次完成 ${done} 個房間的生圖${nightNote}；點縮圖可放大到左側 3D 區。`;
    }
    scheduleSave("ai_render");
  } catch (error) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = `一鍵生圖失敗：${errorMessage(error)}`;
  } finally {
    endPlacementBusy();
  }
}

// Step 7 locks one verified full-room camera for each room before rendering.
function ensureProposalRoomViewPanel() {
  let panel = $("#proposal-room-view-lock");
  if (panel) return panel;
  const sidebar = $("#proposal-review-step .rp-control-pane") || $("#proposal-review-step");
  if (!sidebar) return null;
  panel = document.createElement("section");
  panel.id = "proposal-room-view-lock";
  panel.className = "rp-editor-box rp-render-view-lock";
  panel.innerHTML = `
    <span class="eyebrow">第 7 步｜逐房視角</span>
    <h3>確認每個空間的生圖構圖</h3>
    <p class="rp-field-hint">選擇房間與完整空間視角，確認主要家具、門窗與通行範圍都在畫面內。</p>
    <div id="proposal-room-view-list" class="rp-render-room-list"></div>
    <div id="proposal-room-view-candidates" class="rp-view-candidate-list" aria-live="polite"></div>
    <button id="lock-proposal-room-view" type="button" class="secondary-action">確認此空間視角</button>
    <button id="confirm-proposal-room-views" type="button" class="primary-action">完成全部視角，進入色卡比較</button>
    <p id="proposal-room-view-status" class="rp-field-hint" aria-live="polite"></p>`;
  sidebar.append(panel);
  panel.addEventListener("click", (event) => {
    const roomButton = event.target.closest("[data-proposal-room]");
    if (roomButton) selectProposalRoomView(roomButton.dataset.proposalRoom);
    const candidateButton = event.target.closest("[data-proposal-room-candidate]");
    if (candidateButton) selectProposalRoomCandidate(Number(candidateButton.dataset.proposalRoomCandidate));
  });
  panel.querySelector("#lock-proposal-room-view")?.addEventListener("click", lockSelectedProposalRoomView);
  panel.querySelector("#confirm-proposal-room-views")?.addEventListener("click", confirmProposalRoomViews);
  return panel;
}

function renderProposalRoomViewPanel() {
  const panel = ensureProposalRoomViewPanel();
  if (!panel) return;
  panel.hidden = !state.sceneData || state.rooms.length === 0;
  if (panel.hidden) return;
  const roomId = state.selectedProposalRoomId || state.rooms[0]?.id;
  state.selectedProposalRoomId = roomId;
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  const list = panel.querySelector("#proposal-room-view-list");
  const candidates = panel.querySelector("#proposal-room-view-candidates");
  const status = panel.querySelector("#proposal-room-view-status");
  list.innerHTML = state.rooms.map((item) => {
    const saved = validProposalRoomView(item);
    return `<button type="button" data-proposal-room="${escapeHtml(item.id)}" class="${String(item.id) === String(roomId) ? "is-active" : ""}"><span>${escapeHtml(item.label || "未命名空間")}</span><small>${saved ? "已鎖定" : "待確認"}</small></button>`;
  }).join("");
  if (!room) return;
  const choices = proposalRoomCameraCandidates(room);
  const previewState = proposalRoomPreviewCache.get(proposalRoomPreviewKey(room));
  const activeIndex = Number(state.selectedProposalRoomCandidateIndex || 0);
  candidates.innerHTML = choices.map((choice, index) => `<button type="button" data-proposal-room-candidate="${index}" class="${index === activeIndex ? "is-active" : ""}">${Array.isArray(previewState) && previewState[index] ? `<img src="${previewState[index]}" alt="${escapeHtml(`${room.label} ${choice.label}`)}">` : `<span class="rp-view-candidate-placeholder">正在建立 3D 預覽</span>`}<strong>${escapeHtml(choice.label)}</strong><small>${escapeHtml(choice.note)}</small></button>`).join("");
  const completed = state.rooms.filter((item) => validProposalRoomView(item)).length;
  status.textContent = `${room.label}：確認畫面能看見完整空間後儲存。已完成 ${completed} / ${state.rooms.length} 間。`;
  if (!Array.isArray(previewState) && previewState !== "loading") void ensureProposalRoomCandidatePreviews(room);
}

function confirmProposalRoomViews() {
  const missing = state.rooms.filter((room) => !validProposalRoomView(room));
  if (missing.length) {
    selectProposalRoomView(missing[0].id);
    const status = $("#proposal-room-view-status");
    if (status) status.textContent = `請先確認 ${missing.map((room) => room.label).join("、")} 的視角。`;
    return;
  }
  state.proposalReview.viewsConfirmedAt = new Date().toISOString();
  state.proposalReview.representativeRoomId ||= state.selectedProposalRoomId || state.rooms[0]?.id || null;
  proposalViewer.lockRenderCamera(true);
  refreshConfigurationSnapshot();
  renderProposalStyleStage();
  scheduleSave("proposal_review");
}

function deliveryReadableValues(value) {
  if (Array.isArray(value)) return value.flatMap((item) => deliveryReadableValues(item));
  if (value && typeof value === "object") return Object.values(value).flatMap((item) => deliveryReadableValues(item));
  const text = String(value ?? "").trim();
  return text ? [text] : [];
}

function deliveryAmountLabel(line) {
  const amount = Number(line?.amount_twd);
  if (Number.isFinite(amount) && amount > 0) {
    return new Intl.NumberFormat("zh-TW", { style: "currency", currency: "TWD", maximumFractionDigits: 0 }).format(amount);
  }
  return line?.status_label || "待報價";
}

function renderDesignDeliveryPackage(delivery) {
  if (!element.designDeliveryContent) return;
  const presentation = delivery?.presentation || {};
  const engineering = delivery?.engineering_report || {};
  const security = delivery?.security_review || presentation.security_review || {};
  const budget = delivery?.budget_report || delivery?.budget || {};
  const proposal = delivery?.delivery_proposal || {};
  const rooms = Array.isArray(presentation.rooms) ? presentation.rooms : [];
  const roomMarkup = rooms.map((room) => {
    const decoration = room.decoration_summary || {};
    const render = decoration.render_status || {};
    const imageUrl = render.revision_image_data_url || render.image_data_url || "";
    const materials = [...new Set(deliveryReadableValues(decoration.materials))].slice(0, 12).join("、") || "依第 6 步鎖定材質";
    return `<article class="rp-delivery-room">
      <header><div><span>${escapeHtml(room.room_type || "空間")}</span><h3>${escapeHtml(room.room_name || "未命名空間")}</h3></div><strong>${escapeHtml(room.style_card || "已選色卡")}</strong></header>
      ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(`${room.room_name || "房間"}最終設計圖`)}">` : ""}
      <p class="rp-delivery-designer-reference"><strong>設計師觀點參照</strong>${escapeHtml(room.designer_reference || "依專業室內設計原則整理。")}</p>
      <p>${escapeHtml(room.design_summary || "")}</p>
      <dl>
        <div><dt>問卷需求</dt><dd>${escapeHtml(decoration.questionnaire_note || "採用全屋問卷與已鎖定配置")}</dd></div>
        <div><dt>空間用途</dt><dd>${escapeHtml((decoration.usage || []).join("、") || "依已確認用途")}</dd></div>
        <div><dt>家具</dt><dd>${escapeHtml((decoration.locked_furniture || []).join("、") || "依配置快照")}</dd></div>
        <div><dt>材質與裝潢</dt><dd>${escapeHtml(materials)}</dd></div>
      </dl>
    </article>`;
  }).join("");
  const structureLabels = { walls: "牆", doors: "門", windows: "窗", beams: "樑", columns: "柱" };
  const structureSummary = Object.entries(engineering.structure_counts || {})
    .map(([key, value]) => `${structureLabels[key] || key} ${value}`)
    .join("、") || "依第 4 步固定結構";
  const securityChecks = (security.checks || []).map((check) => (
    `<li><strong>${escapeHtml(check.status === "passed" ? "通過" : "已處理")}</strong><span>${escapeHtml(check.detail || "")}</span></li>`
  )).join("");
  const budgetRows = (budget.lines || []).map((line) => `<tr>
    <td>${escapeHtml(line.category_label || line.category || "項目")}</td>
    <td>${escapeHtml(line.name || "未命名項目")}</td>
    <td>${escapeHtml(line.unit || "")}</td>
    <td>${escapeHtml(deliveryAmountLabel(line))}</td>
  </tr>`).join("");
  const knownSubtotal = Number(budget.known_furniture_reference_subtotal_twd || 0);
  element.designDeliveryContent.innerHTML = `
    <section class="rp-delivery-hero">
      <span class="eyebrow">WEB DESIGN DELIVERY</span>
      <h2>${escapeHtml(presentation.title || "RoomPilot 全屋設計與裝潢簡報")}</h2>
      <p>${escapeHtml(presentation.subtitle || "依最終設定快照組稿")}</p>
      <div><span>房間 ${rooms.length}</span><span>快照 ${escapeHtml(delivery.snapshot_id || "已建立")}</span><span>資安 ${escapeHtml(security.status_label || "待審核")}</span></div>
    </section>
    <section class="rp-delivery-section"><header><span>01</span><div><h2>逐房設計與裝潢</h2><p>每間房均沿用同一份已確認的結構、家具、材質、色卡與視角。</p></div></header><div class="rp-delivery-room-grid">${roomMarkup || "<p>尚無房間成果。</p>"}</div></section>
    <section class="rp-delivery-section"><header><span>02</span><div><h2>${escapeHtml(engineering.title || "工程報告書")}</h2><p>${escapeHtml(structureSummary)}</p></div></header><div class="rp-delivery-engineering-summary"><strong>生圖完成 ${escapeHtml(engineering.completion?.rendered_room_count ?? 0)} / ${escapeHtml(engineering.completion?.room_count ?? rooms.length)} 房</strong><span>已使用一次修改：${escapeHtml(engineering.completion?.revised_room_count ?? 0)} 房</span></div><ul>${(engineering.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul></section>
    <section class="rp-delivery-section"><header><span>03</span><div><h2>資安工程審核</h2><p>${escapeHtml(security.status_label || "待審核")}</p></div></header><ul class="rp-delivery-security">${securityChecks || "<li>尚無審核紀錄。</li>"}</ul></section>
    <section class="rp-delivery-section"><header><span>04</span><div><h2>${escapeHtml(budget.title || "裝潢與家具預算報告書")}</h2><p>家具已知參考小計：${escapeHtml(new Intl.NumberFormat("zh-TW").format(knownSubtotal))} 元；待報價 ${escapeHtml(budget.pending_quote_count ?? 0)} 項。</p></div></header><div class="rp-delivery-table-wrap"><table><thead><tr><th>類別</th><th>項目</th><th>單位</th><th>金額狀態</th></tr></thead><tbody>${budgetRows || '<tr><td colspan="4">尚無明細</td></tr>'}</tbody></table></div><p class="rp-field-hint">${escapeHtml(budget.disclaimer || "正式價格以現場丈量與廠商報價為準。")}</p></section>
    <section class="rp-delivery-section"><header><span>05</span><div><h2>設計提案 PDF</h2><p>${escapeHtml(proposal.status === "generated" ? "已產出設計提案，可用下方按鈕下載或重新產出取代。" : "尚未產出；可用下方按鈕由 Report Agent 以 roompilot-delivery-pdf 品牌排版產出。")}</p></div></header></section>`;
}

function closeDesignDelivery() {
  if (!element.designDeliveryDialog) return;
  if (typeof element.designDeliveryDialog.close === "function") element.designDeliveryDialog.close();
  else element.designDeliveryDialog.removeAttribute("open");
}

function downloadDesignDeliveryJson() {
  if (!proposalRuntimeState.latestDesignDelivery) return;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([JSON.stringify(proposalRuntimeState.latestDesignDelivery, null, 2)], { type: "application/json" }));
  link.download = `roompilot-design-delivery-${state.projectId || "project"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function downloadEngineeringDelivery() {
  const configuration = lockedConfigurationSnapshot();
  const stylePack = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  const rooms = state.rooms.map((room) => ({
    room_id: room.id,
    room_name: room.label,
    room_type: room.type || room.room_type || room.visual_space_type || null,
    questionnaire: roomQuestionnaireContext(room.id),
    view: state.proposalReview.roomViews?.[room.id] || null,
    render: state.proposalReview.finalRooms?.[room.id] || null,
  }));
  const payload = {
    project_id: state.projectId,
    style_card: stylePack ? {
      id: stylePack.id,
      name: stylePack.name,
      style_id: stylePack.styleId,
      palette_hex: stylePack.palette,
    } : { id: state.proposalReview.confirmedStyleCardId },
    generated_at: new Date().toISOString(),
    configuration_snapshot: configuration,
    rooms,
    engineering_brief: {
      scope: "第 8 步最終生圖、每房一次修改、裝潢簡報、工程報告與家具／裝潢預算明細。",
      structure_locked: true,
      notes: rooms.map((room) => ({
        room_id: room.room_id,
        room_name: room.room_name,
        notes: room.questionnaire?.note || "",
      })),
    },
  };
  const trigger = element.roomRenderSection?.querySelector("#download-engineering-delivery");
  if (trigger) trigger.disabled = true;
  if (element.aiRenderStatus) element.aiRenderStatus.textContent = "正在建立裝潢簡報、工程報告、資安審核與預算明細…";
  try {
    proposalRuntimeState.latestDesignDelivery = await api(`/api/projects/${state.projectId}/design-delivery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderDesignDeliveryPackage(proposalRuntimeState.latestDesignDelivery);
    if (typeof element.designDeliveryDialog?.showModal === "function") element.designDeliveryDialog.showModal();
    else element.designDeliveryDialog?.setAttribute("open", "");
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "成果包已完成，並已通過後端資安工程審核。";
  } catch (error) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = `成果包建立失敗：${errorMessage(error)}`;
  } finally {
    if (trigger) trigger.disabled = false;
  }
}

async function ensureProposalSceneLoaded() {
  const version = currentSceneVersion();
  if (proposalRuntimeState.sceneVersionLoaded === version) return true;   // 暫存記憶:直接呼叫出來
  if (proposalRuntimeState.sceneLoading) {
    await proposalRuntimeState.sceneLoading;
    if (proposalRuntimeState.sceneVersionLoaded === currentSceneVersion()) return true;
  }
  // 真的需要載入(6→7 首次進入、換方案、場景重建)才會走到這裡:
  // 全畫面等待遮罩明確告知「還在準備」,載完一次呈現;快取命中不閃遮罩。
  element.masterViewStatus.textContent = "場景還在準備中，請稍候…";
  beginPlacementBusy("正在準備第 7 步 3D 場景，請稍候…");
  proposalRuntimeState.sceneLoading = proposalViewer.loadScene(state.sceneData)
    .then(async () => {
      // loadScene resolve 時首幀還沒畫出來(寫實材質在首次 render 才編譯
      // shader),先收遮罩會露出空白 canvas —— 等兩個動畫幀確保已呈現。
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      proposalRuntimeState.sceneVersionLoaded = version;
      element.masterViewStatus.textContent = "場景已就緒；請核對方案並鎖定比較視角。";
      return true;
    })
    .catch((error) => {
      // 絕不靜默空白:載入失敗要明說,並指回可修復的第 6 步。
      element.masterViewStatus.textContent =
        `3D 場景載入失敗：${errorMessage(error)}。請返回第 6 步重新確認方案後再進入。`;
      setStatus("第 7 步 3D 場景載入失敗，請返回第 6 步重新確認。", "error");
      return false;
    })
    .finally(() => {
      proposalRuntimeState.sceneLoading = null;
      endPlacementBusy();
    });
  return proposalRuntimeState.sceneLoading;
}

function roomWalkPayload(room) {
  if (!room?.polygon_cm?.length) return null;
  const center = planCenterCm();
  const roomMiddle = roomCenter(room);
  return {
    id: room.id,
    label: room.label || "未命名空間",
    center_cm: {
      x: roomMiddle.x - center.x,
      z: roomMiddle.y - center.y,
    },
    polygon_cm: room.polygon_cm.map((point) => ({
      x: point.x - center.x,
      z: point.y - center.y,
    })),
  };
}

// 第 8 步版面:生圖可放大蓋住左側 3D 場景,點空白/關閉鈕回 3D。
// proposalRuntimeState.renderStageView 決定疊層內容:single=單張放大(色卡或某房)、gallery=已生成圖片牆;
// 為 null 時回退到「目前選取房間」的生圖,維持生圖完成即自動預覽的舊行為。
function completedOpenrouterRows() {
  // 逐房生圖結果來源：finalRooms。沿用 {room_id, room_label,
  // image_data_url} 形狀供左側疊層/圖片牆共用;修圖後優先取 revision 圖。
  const finals = state.proposalReview.finalRooms || {};
  return state.rooms
    .map((room) => {
      const final = finals[String(room.id)];
      const image = final?.revision_image_data_url || final?.image_data_url;
      return image
        ? { room_id: room.id, room_label: room.label, image_data_url: image }
        : null;
    })
    .filter(Boolean);
}

function currentAiRenderImage() {
  const completed = completedOpenrouterRows();
  if (!completed.length) return null;
  return completed.find((row) => row.room_id === state.selectedRenderRoomId)
    || completed[0];
}

// 第 7 步色卡比較圖:點縮圖放大到 #proposal-review-viewer 的疊層(該步自己的 3D 區),
// 點空白/關閉鈕切回 3D。與第 8 步 #ai-render-image-stage 同款但各自獨立(不同 viewer/panel)。
function showProposalPaletteImageEnlarged(src, label) {
  const stage = element.proposalReviewImageStage;
  if (!stage || !src) return;
  if (element.proposalReviewImage) {
    element.proposalReviewImage.src = src;
    element.proposalReviewImage.alt = label ? `${label} 色卡比較圖` : "色卡比較圖";
  }
  if (element.proposalReviewImageCaption) element.proposalReviewImageCaption.textContent = label || "";
  stage.hidden = false;
}

function closeProposalPaletteImageStage() {
  if (element.proposalReviewImageStage) element.proposalReviewImageStage.hidden = true;
}

// 把一張圖放大到左側 3D 疊層;label 會印在圖上,標明是哪張色卡/哪個房間。
function showRenderImageEnlarged(src, label) {
  if (!src) return;
  proposalRuntimeState.renderStageView = { mode: "single", src, label: label || "" };
  proposalRuntimeState.aiRenderImageVisible = true;
  updateAiRenderImageStage();
}

function closeRenderImageStage() {
  proposalRuntimeState.aiRenderImageVisible = false;
  proposalRuntimeState.renderStageView = null;
  updateAiRenderImageStage();
}

function updateAiRenderImageStage() {
  const stage = element.aiRenderImageStage;
  const toggle = element.aiRenderImageToggle;
  if (!stage || !toggle) return;
  const fallback = currentAiRenderImage();

  if (!proposalRuntimeState.aiRenderImageVisible) {
    stage.hidden = true;
    proposalRuntimeState.renderStageView = null;
    toggle.hidden = !fallback;
    if (fallback) {
      toggle.textContent = `查看生圖（${fallback.room_label || fallback.room_id}）`;
    }
    return;
  }

  const view = proposalRuntimeState.renderStageView
    || (fallback
      ? { mode: "single", src: fallback.image_data_url, label: fallback.room_label || fallback.room_id }
      : null);
  if (!view) {
    proposalRuntimeState.aiRenderImageVisible = false;
    stage.hidden = true;
    toggle.hidden = true;
    return;
  }

  stage.hidden = false;
  toggle.hidden = true;
  const galleryMode = view.mode === "gallery";
  if (element.aiRenderGallery) element.aiRenderGallery.hidden = !galleryMode;
  if (element.aiRenderImage) element.aiRenderImage.hidden = galleryMode;
  if (element.aiRenderImageCaption) element.aiRenderImageCaption.hidden = galleryMode;

  if (galleryMode) {
    if (element.aiRenderGallery) {
      element.aiRenderGallery.innerHTML = completedOpenrouterRows().map((row) => `
        <figure class="rp-render-gallery-item" data-gallery-room="${escapeHtml(String(row.room_id))}" role="button" tabindex="0">
          <img src="${escapeHtml(row.image_data_url)}" alt="${escapeHtml(row.room_label || row.room_id)} 寫實生圖" />
          <figcaption>${escapeHtml(row.room_label || row.room_id)}</figcaption>
        </figure>`).join("");
    }
  } else {
    element.aiRenderImage.src = view.src;
    element.aiRenderImage.alt = view.label ? `${view.label} 生圖` : "生圖";
    if (element.aiRenderImageCaption) element.aiRenderImageCaption.textContent = view.label || "";
  }
}

// ---- 第 8 步收尾：Report Agent 設計手冊（PDF）產出與下載 ----

function roomBoundsCm(room) {
  const points = room?.polygon_cm || [];
  if (!points.length) return { width_cm: 0, depth_cm: 0 };
  const xs = points.map((point) => Number(point.x) || 0);
  const ys = points.map((point) => Number(point.y) || 0);
  return {
    width_cm: Math.round(Math.max(...xs) - Math.min(...xs)),
    depth_cm: Math.round(Math.max(...ys) - Math.min(...ys)),
  };
}

function deliveryRoomsPayload() {
  return state.rooms.map((room) => {
    // 生圖結果統一來自逐房生圖 finalRooms(修圖後優先取 revision 圖)。
    const finalRoom = state.proposalReview.finalRooms?.[room.id];
    return {
      room_id: room.id,
      room_label: room.label,
      ...roomBoundsCm(room),
      image_data_url: finalRoom?.revision_image_data_url || finalRoom?.image_data_url || null,
      model: finalRoom?.model || "",
      // 客廳夜間燈光圖(只有客廳有);沒帶出去的話後端圖庫建不出 full_render_night,
      // 設計手冊的「日光/夜間並列」與交付提案的夜間附圖都會靜默少一張。
      night_image_data_url: finalRoom?.night_image_data_url || null,
      night_model: finalRoom?.night_model || "",
    };
  });
}

function showDeliveryProposalDownload(record) {
  // 工程估價 XLSX 與 PDF 同一次產出；估價失敗時 record.engineering.status 為
  // skipped、沒有 file，連結就維持隱藏，PDF 照常可下載。
  if (element.deliveryProposalXlsx) {
    element.deliveryProposalXlsx.href = `/api/projects/${state.projectId}/delivery-proposal/xlsx`;
    element.deliveryProposalXlsx.hidden = !record?.engineering?.file;
  }
  if (!element.deliveryProposalDownload) return;
  if (!record) {
    element.deliveryProposalDownload.hidden = true;
    return;
  }
  element.deliveryProposalDownload.href = `/api/projects/${state.projectId}/delivery-proposal/pdf`;
  element.deliveryProposalDownload.textContent = "下載設計提案 PDF";
  element.deliveryProposalDownload.hidden = false;
}

function setDeliveryProposalStatus(text) {
  if (!element.deliveryProposalStatus) return;
  element.deliveryProposalStatus.textContent = text || "";
  element.deliveryProposalStatus.hidden = !text;
}

function restoreDeliveryProposalPanel() {
  const record = state.project?.workflow?.delivery_proposal;
  showDeliveryProposalDownload(record);
  setDeliveryProposalStatus(record
    ? "已有先前產出的設計提案，可直接下載或重新產出取代紀錄。"
    : "完成上方生圖後產出效果最好；未生圖也可先輸出文字版。");
  void checkDeliveryEngine();
}

function rememberReportRecord(key, record) {
  if (!state.project) return;
  state.project = {
    ...state.project,
    workflow: { ...(state.project.workflow || {}), [key]: record },
  };
}

async function checkDeliveryEngine() {
  try {
    const status = await api("/api/delivery-proposal/status");
    if (!status.available) setDeliveryProposalStatus(status.reason || "設計提案排版引擎尚未安裝。");
  } catch {
    /* 狀態查不到不擋操作，錯誤會在實際產出時回報 */
  }
}

async function generateDeliveryProposal() {
  if (!state.sceneData || !state.projectId) {
    setDeliveryProposalStatus("請先完成第 6 步配置，才能產出設計提案。");
    return;
  }
  const rooms = deliveryRoomsPayload();
  const renderedCount = rooms.filter((room) => room.image_data_url).length;
  element.deliveryProposalGenerate.disabled = true;
  setDeliveryProposalStatus(renderedCount
    ? `正在排版設計提案（含 ${renderedCount} 個房間的生圖成果）…`
    : "正在排版設計提案（尚無生圖，圖面標記待補）…");
  try {
    const result = await api(`/api/projects/${state.projectId}/delivery-proposal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: state.projectId, scene: state.sceneData, rooms }),
    });
    syncProjectRevision(result);
    rememberReportRecord("delivery_proposal", result.proposal);
    showDeliveryProposalDownload(result.proposal);
    const warnings = result.proposal.warnings || [];
    const estimate = result.proposal.engineering || {};
    // 只報數量的話，「文案走離線底稿」這種會影響交付品質的提醒等於沒說；
    // 第一則直接顯示出來，其餘才用數量帶過。
    setDeliveryProposalStatus(
      (renderedCount ? `設計提案完成（含 ${renderedCount} 房生圖）` : "設計提案完成（未含生圖）")
      + (warnings.length
        ? `。${warnings[0]}${warnings.length > 1 ? `（另有 ${warnings.length - 1} 項提醒）` : ""}`
        : "。")
      // 估價是 PDF 的附掛品，成敗都要講；demo 單價更不能讓人拿去對客戶報價。
      // 單價／工率資料不足時工期會是 null，不能就這樣印出「null 天」。
      + (estimate.file
        ? `另產出工程估價 ${estimate.line_count} 項、預估工期 ${estimate.estimated_total_days ?? "待確認"} 天${estimate.demo_mode ? "（示範單價，非正式報價）" : ""}。`
        : `工程估價未產出（${estimate.reason || "資料不足"}）。`),
    );
  } catch (error) {
    setDeliveryProposalStatus(errorMessage(error));
  } finally {
    element.deliveryProposalGenerate.disabled = false;
  }
}

// ---- 第 8 步成果包（design-delivery）：五章 JSON 與設計提案 PDF 同一視窗 ----

async function generateDesignDelivery() {
  if (!state.sceneData || !state.projectId) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "請先完成第 6 步配置，才能產出成果包。";
    return;
  }
  const trigger = $("#design-delivery-generate");
  if (trigger) trigger.disabled = true;
  if (element.aiRenderStatus) element.aiRenderStatus.textContent = "正在建立裝潢簡報、工程報告、資安審核與預算明細…";
  state.configurationState.configuration_snapshot = state.configurationState.configuration_snapshot
    || configurationSnapshot();
  const baseSnapshot = state.configurationState.configuration_snapshot;
  const configuration = {
    ...baseSnapshot,
    snapshot_id: baseSnapshot.snapshot_id || baseSnapshot.created_at,
    furniture: composeSelectedRoomFurniture().map((item) => ({
      ...item,
      room_id: item.room_id || item.roomId || null,
    })),
    fixed_structure: {
      walls: state.structures?.walls || [],
      doors: state.structures?.doors || [],
      windows: state.structures?.windows || [],
      beams: state.structures?.beams || [],
      columns: state.structures?.columns || [],
    },
  };
  const stylePack = STYLE_PACKS.find((item) => item.id === state.proposalReview.confirmedStyleCardId);
  const rooms = state.rooms.map((room) => {
    // 生圖結果統一來自逐房生圖 finalRooms。
    const final = state.proposalReview.finalRooms?.[room.id];
    const row = final?.image_data_url ? { ...final, room_id: room.id } : null;
    return {
      room_id: room.id,
      room_name: room.label,
      room_type: room.type || room.room_type || room.visual_space_type || null,
      questionnaire: roomQuestionnaireContext(room.id),
      view: state.proposalReview.roomViews?.[room.id] || null,
      render: row ? {
        image_data_url: row.revision_image_data_url || row.image_data_url,
        model: row.model || "",
        submitted_at: row.submitted_at || new Date().toISOString(),
        revision_image_data_url: row.revision_image_data_url || null,
        revision_submitted_at: row.revision_submitted_at || null,
      } : null,
    };
  });
  const payload = {
    project_id: state.projectId,
    style_card: stylePack ? {
      id: stylePack.id,
      name: stylePack.name,
      style_id: stylePack.styleId,
      palette_hex: stylePack.palette,
    } : { id: state.proposalReview.confirmedStyleCardId },
    generated_at: new Date().toISOString(),
    configuration_snapshot: configuration,
    rooms,
  };
  try {
    proposalRuntimeState.latestDesignDelivery = await api(`/api/projects/${state.projectId}/design-delivery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderDesignDeliveryPackage(proposalRuntimeState.latestDesignDelivery);
    showDeliveryProposalDownload(
      proposalRuntimeState.latestDesignDelivery.delivery_proposal?.status === "generated"
        ? proposalRuntimeState.latestDesignDelivery.delivery_proposal
        : state.project?.workflow?.delivery_proposal,
    );
    if (typeof element.designDeliveryDialog?.showModal === "function") element.designDeliveryDialog.showModal();
    else element.designDeliveryDialog?.setAttribute("open", "");
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = "成果包已完成並通過後端資安審核；設計提案 PDF 可在同一視窗產出。";
  } catch (error) {
    if (element.aiRenderStatus) element.aiRenderStatus.textContent = `成果包建立失敗：${errorMessage(error)}`;
  } finally {
    if (trigger) trigger.disabled = false;
  }
}

  return {
    closeDesignDelivery,
    closeProposalPaletteImageStage,
    closeRenderBriefDialog,
    closeRenderImageStage,
    completedOpenrouterRows,
    confirmRenderBriefAndSubmit,
    confirmRenderPalette,
    currentSceneVersion,
    downloadDesignDeliveryJson,
    downloadEngineeringDelivery,
    generateDeliveryProposal,
    generateDesignDelivery,
    lockMasterRenderView,
    openRenderBriefDialog,
    prepareAiRender,
    prepareProposalReview,
    renderProposalSummary,
    roomCameraSuggestion,
    roomWalkPayload,
    saveSelectedRoomView,
    selectProposalPalette,
    selectRenderRoom,
    showRenderImageEnlarged,
    updateAiRenderImageStage,
  };
}
