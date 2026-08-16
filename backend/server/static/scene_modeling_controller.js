// White-model generation, furniture catalog drawer, and Step 6 surface styling.
export function createSceneModelingController({
  $,
  $$,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  allRoomsHaveSchemeSelections,
  api,
  applyStylePack,
  CATALOG_FACET_TRADITIONAL_LABELS,
  catalogItemRenderable,
  catalogItemRenderKey,
  catalogMaterialOptionsForPack,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  circulationStyleIsOverridden,
  configurationBlockingFurniture,
  confirmedFloorplanEditor,
  confirmLayout2d,
  detectCeilingConflicts,
  element,
  errorMessage,
  escapeHtml,
  firstWorkflowBlocker,
  focusStepSixRoom,
  furniture2dDefaultsForSceneObject,
  glbThumbnailCache,
  glbThumbnailQueue,
  glbThumbnailViewer,
  goTo,
  invalidateDownstreamFrom,
  isCirculationRoom,
  LIGHT_STYLES,
  livingRoomForCirculation,
  materialPairScore,
  materialVisualTagMarkup,
  openRoomSchemeSelectionDialog,
  planCenterCm,
  pruneAutomaticSoftDecor,
  QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS,
  QUESTIONNAIRE_CATALOG_PURPOSE_TYPES,
  QUESTIONNAIRE_CATALOG_PURPOSES,
  QUESTIONNAIRE_CATALOG_SPACES,
  QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureOffers,
  questionnaireFurnitureSelectionItem,
  realisticViewer,
  refreshConfigurationSnapshot,
  reloadViewerPreservingState,
  removeFurniture2dBySceneObject,
  renderConfigurationPlan,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireFurnitureRecommendations,
  renderSelectedFurnitureWorkspace,
  renderStepSixSurfaceProgress,
  resolveSurfaceOption,
  roomCenter,
  roomFinishDraftFor,
  roomFurnitureRequirement,
  roomQuestionnaireSummary,
  roomSchemeSelectionRequired,
  scheduleSave,
  selectedStepSixRoom,
  selectSceneObjectByFurnitureId,
  setStatus,
  setStepSixSurfaceKind,
  setStepSixSurfaceStatus,
  showStep,
  state,
  STEP_SIX_SURFACE_MATERIAL_LIMIT,
  STEP_SIX_SURFACE_SWATCH_LIMIT,
  stepSixRoomSurfaceConfirmed,
  stepSixSurfacesFinalLocked,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
  styleCompatibleMaterialOptionsForPack,
  styleFurnitureCache,
  switchDesignScheme,
  syncFinalValidationToConfiguration,
  syncFurnitureInventoryAcrossSchemes,
  upsertFurniture2dFromSceneObject,
  whiteViewer,
}) {
let styleApplyRevision = 0;
async function generateWhiteModelFromRequirements({ returnToRequirementsOnFailure = false } = {}) {
  if (state.autoGeneratingWhiteModel) {
    state.lastWhiteModelGenerationError = "配置仍在建立中，請勿重複送出。";
    return false;
  }
  state.autoGeneratingWhiteModel = true;
  state.lastWhiteModelGenerationError = "";
  element.layoutError.textContent = "";
  try {
    if (!state.workflow?.goTo("layout_2d")) {
      const message = firstWorkflowBlocker("layout_2d");
      state.lastWhiteModelGenerationError = message;
      if (returnToRequirementsOnFailure) element.requirementsError.textContent = message;
      setStatus(message, "error");
      return false;
    }
    setStatus("正在依照問卷、色卡與指定家具建立方案 A 的 3D 場景…");
    // Keep the questionnaire moving: items without a usable GLB are deferred to
    // step 6, where the user can replace or reposition them. Never auto-add items.
    const generatedAResult = await confirmLayout2d({ allowPendingFurniture: true });
    const generatedA = generatedAResult && state.workflow.currentStep === "white_model_3d" && Boolean(state.sceneData);
    if (!generatedA) {
      const message = element.layoutError.textContent.trim()
        || "方案 A 無法建立 3D 場景，請檢查問卷需求或資料庫家具模型。";
      state.lastWhiteModelGenerationError = message;
      if (returnToRequirementsOnFailure) {
        state.workflow.goTo("requirements");
        showStep("requirements");
        element.requirementsError.textContent = message;
        scheduleSave("requirements");
      }
      return false;
    }

    if (state.designSchemes.schemes.B && !state.designSchemes.schemes.B.stale) {
      setStatus("正在載入方案 B 的資料庫家具與 3D 場景…");
      await switchDesignScheme("B");
      const generatedBResult = await confirmLayout2d({ allowPendingFurniture: true });
      const generatedB = generatedBResult && state.workflow.currentStep === "white_model_3d" && Boolean(state.sceneData);
      if (!generatedB) {
        const message = element.layoutError.textContent.trim()
          || "方案 B 無法建立 3D 場景，請返回問卷調整需求。";
        state.designSchemes.schemes.B.stale = true;
        state.designSchemes.schemes.B.staleReason = message;
        await switchDesignScheme("A");
        setStatus("方案 A 已建立；方案 B 有待處理家具，請在第 6 步調整。", "warning");
      } else {
        await switchDesignScheme("A");
        setStatus("問卷需求的 2D+3D 配置已建立，可開始調整。", "success");
      }
    } else if (state.designSchemes.schemes.B?.stale) {
      setStatus("方案 A 已建立；方案 B 有待處理家具，請在第 6 步調整。", "warning");
    }
    return true;
  } finally {
    state.autoGeneratingWhiteModel = false;
  }
}



function cancelWhiteModelBeamPlacement() {
  whiteViewer.cancelBeamPlacement();
  $("#add-white-model-beam").hidden = false;
  $("#cancel-white-model-beam").hidden = true;
  $("#white-model-beam-status").textContent = "已取消；樑會自動吸附天花板，不會自由漂浮。";
}

const sceneObjectTypeLabels = {
  "bed-frame": "雙人床",
  bed: "床",
  wardrobe: "衣櫃",
  sofa: "沙發",
  "coffee-table": "茶几",
  "dining-table": "餐桌",
  "dining-chair": "餐椅",
  "floor-lamp": "落地燈",
  "flower-pots-planter": "植栽",
  "large-medium-rug": "地毯",
  rug: "地毯",
  curtain: "窗簾",
};

function sceneObjectDisplayName(item, index) {
  return sceneObjectTypeLabels[item.normalized_type]
    || item.name_zh
    || item.name_zh_raw
    || item.normalized_type
    || `家具 ${index + 1}`;
}

function renderSceneObjectList() {
  const objects = state.sceneData?.scene_objects || [];
  const markup = objects.map((item, index) => `
    <button type="button" data-scene-object-index="${index}" class="${index === state.selectedSceneIndex ? "is-active" : ""}">
      <strong><b class="rp-object-number">#${index + 1}</b>${escapeHtml(sceneObjectDisplayName(item, index))}</strong>
      <span>${item.model_url ? "資料庫 GLB" : "缺少 GLB"}</span>
      <small>${Number(item.size_cm?.width || 0).toFixed(0)} × ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</small>
      <small>${item.user_specified ? "已指定" : "系統選配"}</small>
    </button>
  `).join("");
  if (element.objectList) {
    element.objectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  }
  if (element.realisticObjectList) {
    element.realisticObjectList.innerHTML = markup || "<p>目前為純結構方案，沒有家具。</p>";
  }
  renderConfigurationPlan();
}

function saveSelectedSceneAppearance() {
  const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  if (!selected) return;
  selected.model_locked = $("#lock-specified-model").checked;
  selected.material_locked = $("#lock-specified-material").checked;
  selected.specified_color = $("#specified-furniture-color").value;
  selected.specified_material = $("#specified-furniture-material").value;
  const materialProfiles = {
    wood: { roughness: 0.56, metalness: 0 },
    fabric: { roughness: 0.9, metalness: 0 },
    leather: { roughness: 0.48, metalness: 0 },
    metal: { roughness: 0.3, metalness: 0.78 },
    glass: { roughness: 0.12, metalness: 0.06, opacity: 0.42 },
  };
  selected.material_override = selected.material_locked
    ? {
        color: selected.specified_color,
        kind: selected.specified_material,
        pbr: materialProfiles[selected.specified_material] || {
          roughness: 0.7,
          metalness: 0,
        },
      }
    : null;
}

function loadSelectedSceneAppearance() {
  const selected = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  $("#specified-furniture-color").value = selected?.specified_color || "#f2f0ec";
  $("#specified-furniture-material").value = selected?.specified_material || "";
  $("#lock-specified-model").checked = selected?.model_locked === true;
  $("#lock-specified-material").checked = selected?.material_locked === true;
  const status = $("#specified-furniture-status");
  if (status) {
    status.textContent = selected?.user_specified
      ? "目前選取家具已在 3D 微調面板鎖定為指定需求。"
      : "可在 3D 畫面選取家具後，使用浮動微調面板鎖定指定需求。";
  }
}

function renderWhiteWalkRoomSelector() {
  if (!element.whiteWalkRoom) return;
  const selectedExists = state.rooms.some(
    (room) => String(room.id) === String(state.selectedWalkRoomId),
  );
  if (!selectedExists) {
    state.selectedWalkRoomId = state.selectedRoomId || state.rooms[0]?.id || null;
  }
  element.whiteWalkRoom.innerHTML = state.rooms.map((room) => `
    <option value="${escapeHtml(room.id)}">${escapeHtml(room.label || "未命名空間")}</option>
  `).join("");
  element.whiteWalkRoom.disabled = state.rooms.length === 0;
  if (state.selectedWalkRoomId) element.whiteWalkRoom.value = state.selectedWalkRoomId;
}

function selectedWhiteWalkRoomPayload() {
  const room = state.rooms.find(
    (candidate) => String(candidate.id) === String(state.selectedWalkRoomId),
  ) || state.rooms[0];
  if (!room?.polygon_cm?.length) return null;
  const center = planCenterCm();
  const roomMiddle = roomCenter(room);
  return {
    id: room.id,
    label: room.label || "未命名空間",
    center_cm: {
      x: roomMiddle.x - center.x,
      z: center.y - roomMiddle.y,
    },
    polygon_cm: room.polygon_cm.map((point) => ({
      x: point.x - center.x,
      z: center.y - point.y,
    })),
  };
}

function activateWhiteWalkMode() {
  renderWhiteWalkRoomSelector();
  const room = selectedWhiteWalkRoomPayload();
  if (!room) {
    setStatus("目前沒有可進入的房間，請先回到第 4 步確認空間。", "error");
    return false;
  }
  if (!whiteViewer.setWalkRoom(room)) {
    setStatus("3D 場景尚未就緒，或該空間沒有可安全站立的位置。", "error");
    return false;
  }
  $$("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === "walk");
  });
  $$("[data-white-interaction]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.whiteInteraction === "walk");
  });
  return true;
}

function activateWhiteFurnitureEditing() {
  whiteViewer.setInteractionMode("edit");
  $$("[data-white-interaction]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.whiteInteraction === "edit");
  });
}

function deactivateWhiteInteractionMode() {
  whiteViewer.setInteractionMode("camera");
  $$("[data-white-interaction]").forEach((button) => {
    button.classList.remove("is-active");
  });
  $$("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === "orbit");
  });
}

// Catalog edits rebuild the viewer. Keep the user's current framing while doing so.
async function reloadWhiteViewerPreservingCamera() {
  return reloadViewerPreservingState(whiteViewer, state.sceneData, {
    interactionMode: "edit",
  });
}

async function deleteSelectedSceneFurniture() {
  const objects = state.sceneData?.scene_objects || [];
  const selected = objects[state.selectedSceneIndex];
  if (!selected) {
    setStatus("目前沒有可刪除的家具。", "error");
    return;
  }
  objects.splice(state.selectedSceneIndex, 1);
  if (selected.auto_decor_role) {
    // 記住「這個房間不要這類軟裝」——否則下次重跑軟裝時,錨點推導
    // 會以同角色的另一件品項把它補回來。
    const decorRoomId = String(
      selected.auto_decor_room_id || selected.placement_room_id || "default",
    );
    const dismissed = new Set(state.dismissedDecorRoles[decorRoomId] || []);
    dismissed.add(String(selected.auto_decor_role));
    state.dismissedDecorRoles[decorRoomId] = [...dismissed];
  }
  state.furniture2d = removeFurniture2dBySceneObject(
    state.furniture2d,
    selected,
  );
  syncFurnitureInventoryAcrossSchemes();
  state.selectedSceneIndex = Math.max(0, Math.min(state.selectedSceneIndex, objects.length - 1));
  const nextSelected = objects[state.selectedSceneIndex] || null;
  state.selectedFurniture2dId = nextSelected?.furniture_id || null;
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  if (state.workflow.currentStep === "white_model_3d") {
    // 只拆掉被刪的那一件並重編號；viewer 尚未載入場景時才整包重載。
    if (!whiteViewer.removeObject(selected.furniture_id)) {
      await reloadWhiteViewerPreservingCamera();
    }
    renderConfigurationPlan();
    if (nextSelected) {
      selectSceneObjectByFurnitureId(nextSelected.furniture_id, {
        viewer: whiteViewer,
        focus: false,
      });
      activateWhiteFurnitureEditing();
    }
    scheduleSave("white_model_3d");
  } else {
    if (!realisticViewer.removeObject(selected.furniture_id)) {
      await realisticViewer.loadScene(state.sceneData);
      realisticViewer.setViewMode("orbit");
    }
    renderConfigurationPlan();
    scheduleSave("realistic_3d");
  }
  setStatus(
    `已刪除「${selected.name_zh_raw || selected.normalized_type || "家具"}」，其餘家具已重新編號。`,
  );
}

function activeCatalogSearchInput() {
  return element.standardCatalogSearch;
}

function questionnaireCatalogGroup(room) {
  const type = String(room?.visual_space_type || room?.type || "");
  return {
    bedroom: "bedroom",
    living_room: "living",
    kitchen: "dining_kitchen",
    storage: "study",
  }[type] || "storage";
}

function questionnaireCatalogRoomType(room) {
  return String(room?.visual_space_type || room?.type || room?.room_type || "").toLowerCase();
}

function questionnaireCatalogActiveSpace(room) {
  return catalogRuntimeState.scope === "room" ? questionnaireCatalogRoomType(room) : catalogRuntimeState.space;
}

function questionnaireCatalogPurposeDefinition(room) {
  const space = questionnaireCatalogActiveSpace(room);
  const definition = (QUESTIONNAIRE_CATALOG_PURPOSES[space] || [])
    .find(([id]) => id === catalogRuntimeState.purpose);
  if (!definition) return null;
  return [
    definition[0],
    definition[1],
    QUESTIONNAIRE_CATALOG_PURPOSE_TYPES[`${space}:${definition[0]}`] || definition[2],
  ];
}

function questionnaireCatalogBrowsePrompt(room, query = "") {
  if (query) return "";
  const activeSpace = questionnaireCatalogActiveSpace(room);
  if (!activeSpace) return "請先選擇要瀏覽的空間，再挑選用途。";
  if (!catalogRuntimeState.purpose) return "請選擇家具用途，再查看對應的家具選項。";
  return "";
}

function renderQuestionnaireCatalogBrowseChoices(room) {
  if (!room) return;
  const activeSpace = questionnaireCatalogActiveSpace(room);
  if (element.questionnaireCatalogSpaceGroups) {
    element.questionnaireCatalogSpaceGroups.hidden = catalogRuntimeState.scope !== "all";
    element.questionnaireCatalogSpaceGroups.innerHTML = QUESTIONNAIRE_CATALOG_SPACES.map((space) => `
      <button type="button" data-questionnaire-catalog-space="${escapeHtml(space.id)}"
        class="${space.id === activeSpace ? "is-active" : ""}" aria-pressed="${space.id === activeSpace}">${escapeHtml(space.label)}</button>
    `).join("");
  }
  if (element.questionnaireCatalogPurposeGroups) {
    const purposes = QUESTIONNAIRE_CATALOG_PURPOSES[activeSpace] || [];
    element.questionnaireCatalogPurposeGroups.hidden = !purposes.length;
    const spaceLabel = QUESTIONNAIRE_CATALOG_SPACES.find((space) => space.id === activeSpace)?.label || room.label;
    element.questionnaireCatalogPurposeGroups.innerHTML = `
      <span>${escapeHtml(spaceLabel)}用途</span>
      ${purposes.map(([id, label]) => `<button type="button" data-questionnaire-catalog-purpose="${escapeHtml(id)}"
        class="${id === catalogRuntimeState.purpose ? "is-active" : ""}" aria-pressed="${id === catalogRuntimeState.purpose}">${escapeHtml(label)}</button>`).join("")}
    `;
  }
  renderSelectedFurnitureWorkspace();
}

function catalogFacetTraditionalLabel(facet, value) {
  const source = String(value || "").trim();
  if (!source) return source;
  const normalized = source.toLocaleLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  const labels = CATALOG_FACET_TRADITIONAL_LABELS[facet];
  if (!labels) return source;
  if (labels[normalized]) return labels[normalized];
  return source.split(/([、,;/|])/).map((part) => {
    if (/^[、,;/|]$/.test(part)) return part === "," ? "、" : part;
    const key = part.trim().toLocaleLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
    return labels[key] || part;
  }).join("");
}

function setCatalogSelectOptions(select, options, value, labelKey = "label", valueKey = "value", emptyLabel = "全部", labelFormatter = null) {
  if (!select) return;
  const safeValue = String(value || "");
  select.innerHTML = [`<option value="">${escapeHtml(emptyLabel)}</option>`, ...options.map((option) => {
    const optionValue = String(option[valueKey] || option.type || "");
    const sourceLabel = String(option[labelKey] || option.type_name_zh || optionValue);
    const optionLabel = labelFormatter ? labelFormatter(sourceLabel, option) : sourceLabel;
    return `<option value="${escapeHtml(optionValue)}" ${optionValue === safeValue ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`;
  })].join("");
}

function renderQuestionnaireCatalogFilters(payload) {
  if (!catalogRuntimeState.roomId) return;
  const facets = payload.filter_options || {};
  setCatalogSelectOptions(element.questionnaireCatalogColor, facets.colors || [], element.questionnaireCatalogColor?.value || "", "label", "value", "全部顏色", (label) => catalogFacetTraditionalLabel("color", label));
  setCatalogSelectOptions(element.questionnaireCatalogMaterial, facets.materials || [], element.questionnaireCatalogMaterial?.value || "", "label", "value", "全部材質", (label) => catalogFacetTraditionalLabel("material", label));
}

function renderQuestionnaireCatalogBatch() {
  if (!element.questionnaireCatalogBatch) return;
  const count = catalogRuntimeState.selectedFurnitureIds.size;
  element.questionnaireCatalogBatch.hidden = !catalogRuntimeState.roomId;
  if (element.questionnaireCatalogSelectedCount) {
    element.questionnaireCatalogSelectedCount.textContent = count ? `已選擇 ${count} 件家具` : "尚未選擇家具";
  }
  if (element.addSelectedQuestionnaireFurniture) {
    element.addSelectedQuestionnaireFurniture.disabled = count === 0;
  }
}

function setFurnitureCatalogOpen(open) {
  if (open) {
    if (!catalogRuntimeState.roomId) {
      element.catalogDrawer.querySelector("h2").textContent = "新增家具";
      element.catalogDrawer.querySelector("header p").textContent = "搜尋後選擇家具，再回到 3D 房間點選合法擺放位置。";
      if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = true;
      if (element.questionnaireCatalogBatch) element.questionnaireCatalogBatch.hidden = true;
      if (element.standardCatalogSearch) element.standardCatalogSearch.hidden = false;
      const catalogSearchButton = $("#search-glb-furniture");
      if (catalogSearchButton) catalogSearchButton.hidden = false;
      activateWhiteFurnitureEditing();
    }
    if (typeof element.catalogDrawer.showModal === "function" && !element.catalogDrawer.open) {
      element.catalogDrawer.showModal();
    } else if (!element.catalogDrawer.open) {
      element.catalogDrawer.setAttribute("open", "");
    }
    activeCatalogSearchInput()?.focus();
    return;
  }
  if (typeof element.catalogDrawer.close === "function") {
    element.catalogDrawer.close();
  } else {
    element.catalogDrawer.removeAttribute("open");
  }
  catalogRuntimeState.roomId = null;
  catalogRuntimeState.selectedFurnitureIds = new Set();
  catalogRuntimeState.selectedFurniture = new Map();
}

function openQuestionnaireFurnitureCatalog(roomId = activeQuestionnaireRoom()?.id) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId))
    || activeQuestionnaireRoom();
  if (!room || !element.catalogDrawer) {
    if (element.questionnaireFurnitureStatus) {
      element.questionnaireFurnitureStatus.textContent = "目前找不到可加入家具的房間，請先選擇房間後再試一次。";
    }
    return;
  }
  catalogRuntimeState.roomId = room.id;
  catalogRuntimeState.selectedFurnitureIds = new Set();
  catalogRuntimeState.selectedFurniture = new Map();
  element.catalogDrawer.querySelector("h2").textContent = `加入${room.label}的家具`;
  element.catalogDrawer.querySelector("header p").textContent = "先瀏覽適合本房的家具；也可用搜尋、類別、顏色或材質快速篩選。加入後會直接勾選到此房。";
  catalogRuntimeState.scope = "room";
  catalogRuntimeState.space = "";
  catalogRuntimeState.purpose = "";
  if (element.questionnaireCatalogControls) element.questionnaireCatalogControls.hidden = false;
  if (element.standardCatalogSearch) element.standardCatalogSearch.hidden = false;
  const catalogSearchButton = $("#search-glb-furniture");
  if (catalogSearchButton) catalogSearchButton.hidden = true;
  const catalogSearchInput = $("#glb-furniture-search");
  if (catalogSearchInput) catalogSearchInput.value = "";
  if (element.questionnaireCatalogType) element.questionnaireCatalogType.value = "";
  if (element.questionnaireCatalogColor) element.questionnaireCatalogColor.value = "";
  if (element.questionnaireCatalogMaterial) element.questionnaireCatalogMaterial.value = "";
  renderQuestionnaireCatalogBrowseChoices(room);
  element.glbResults.innerHTML = "<p>正在載入適合本房的家具…</p>";
  renderQuestionnaireCatalogBatch();
  setFurnitureCatalogOpen(true);
  void searchGlbFurniture();
}

async function searchGlbFurniture() {
  const query = activeCatalogSearchInput()?.value.trim() || "";
  const thumbnailBatch = ++catalogRuntimeState.thumbnailBatch;
  try {
    const room = state.rooms.find((item) => String(item.id) === String(catalogRuntimeState.roomId));
    const params = new URLSearchParams({ has_model: "true", detail: "scene", page_size: catalogRuntimeState.roomId ? "48" : "24" });
    if (query) params.set("q", query);
    // 搜尋文字可跨用途找同類家具；未搜尋時才依空間與用途收斂。
    const activeSpace = questionnaireCatalogActiveSpace(room);
    const activeSpaceDefinition = QUESTIONNAIRE_CATALOG_SPACES.find((space) => space.id === activeSpace);
    const activePurpose = questionnaireCatalogPurposeDefinition(room);
    const browsePrompt = catalogRuntimeState.roomId
      ? questionnaireCatalogBrowsePrompt(room, query)
      : "";
    if (browsePrompt) {
      element.glbResults.innerHTML = `<p class="rp-catalog-browse-prompt">${escapeHtml(browsePrompt)}</p>`;
      element.glbResults.dataset.items = "[]";
      renderQuestionnaireCatalogBatch();
      return;
    }
    if (!query && catalogRuntimeState.roomId && activeSpace) {
      if (activePurpose?.[2]?.length) {
        params.set("types", activePurpose[2].join(","));
      } else {
        params.set("group", activeSpaceDefinition?.group || questionnaireCatalogGroup(room));
      }
    }
    if (catalogRuntimeState.roomId) {
      const type = element.questionnaireCatalogType?.value || "";
      const color = element.questionnaireCatalogColor?.value || "";
      const material = element.questionnaireCatalogMaterial?.value || "";
      if (type) params.set("type", type);
      if (color) params.set("color", color);
      if (material) params.set("material", material);
    }
    const payload = await api(`/api/furniture?${params.toString()}`);
    const questionnaireMode = Boolean(catalogRuntimeState.roomId);
    renderQuestionnaireCatalogFilters(payload);
    const catalogItems = questionnaireMode
      ? [...new Map((payload.items || []).map((item) => {
        const normalizedType = item.normalized_type || item.category || item.taxonomy_type || "other";
        const label = questionnaireFurnitureDisplayLabel({ ...item, normalized_type: normalizedType }) || "其他家具";
        return [`${normalizedType}:${label}`, item];
      })).values()].slice(0, 18)
      : (payload.items || []);
    element.glbResults.innerHTML = catalogItems.map((item) => {
      const preview = item.image_url
        || item.thumbnail_url
        || item.preview_url
        || item.main_image_url
        || item.image
        || "";
      const title = item.name_zh || item.name_zh_raw || item.name_en || "GLB 家具";
      if (questionnaireMode) {
        const optionLabel = questionnaireFurnitureDisplayLabel(item) || "其他家具";
        const purposeLabel = QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS[item.normalized_type]
          || QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS[item.normalized_type]
          || "可加入配置";
        return `
          <article class="rp-glb-result rp-questionnaire-catalog-option">
            <label class="rp-catalog-select-item">
              <input type="checkbox" data-questionnaire-catalog-select="${escapeHtml(item.furniture_id)}" ${catalogRuntimeState.selectedFurnitureIds.has(String(item.furniture_id)) ? "checked" : ""} />
              <span><strong>${escapeHtml(optionLabel)}</strong><small>適合：${escapeHtml(purposeLabel)}</small></span>
            </label>
          </article>
        `;
      }
      return `
      <article class="rp-glb-result has-preview">
        <div class="rp-glb-thumb">
          <img
            class="${preview ? "" : "is-loading"}"
            src="${escapeHtml(preview || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")}"
            alt="${escapeHtml(title)} PNG 預覽"
            data-glb-thumbnail="${escapeHtml(item.furniture_id)}"
            loading="lazy"
          />
        </div>
        <strong>${escapeHtml(title)}</strong>
        <span>${Number(item.size_cm?.width || 0).toFixed(0)} x ${Number(item.size_cm?.depth || 0).toFixed(0)} cm</span>
        <div class="rp-inline-actions">
          <button type="button" data-replace-furniture-id="${escapeHtml(item.furniture_id)}">替換選取家具</button>
          <button type="button" data-add-furniture-id="${escapeHtml(item.furniture_id)}">新增到 3D</button>
        </div>
      </article>
    `;
    }).join("") || "<p>找不到適合 GLB 的家具。</p>";
    element.glbResults.dataset.items = JSON.stringify(catalogItems);
    catalogItems.forEach((item) => {
      if (catalogRuntimeState.selectedFurnitureIds.has(String(item.furniture_id))) {
        catalogRuntimeState.selectedFurniture.set(String(item.furniture_id), item);
      }
    });
    renderQuestionnaireCatalogBatch();
    const itemsNeedingGeneratedThumbnails = questionnaireMode ? [] : catalogItems.filter(
      (item) => !(item.image_url || item.thumbnail_url || item.preview_url || item.main_image_url || item.image),
    );
    if (itemsNeedingGeneratedThumbnails.length) {
      glbThumbnailQueue.sequence = glbThumbnailQueue.sequence
        .catch(() => null)
        .then(() => populateGlbSearchThumbnails(itemsNeedingGeneratedThumbnails, thumbnailBatch));
    }
  } catch (error) {
    element.glbResults.innerHTML = `<p>${escapeHtml(errorMessage(error))}</p>`;
  }
}

function glbThumbnailScene(item) {
  return {
    floorplan: {
      width_cm: 360,
      depth_cm: 360,
      room_height_cm: 270,
      wall_segments: [],
      door_segments: [],
      window_segments: [],
    },
    scene_objects: [{
      ...item,
      furniture_id: `glb-thumbnail-${item.furniture_id}`,
      position_cm: { x: 0, z: 0 },
      rotation_y_deg: 0,
      position_locked: true,
      placement_failed: false,
    }],
    style: { style_id: state.activeStyleId || "white_model" },
    design_choices: { catalog_thumbnail_mode: true },
  };
}

async function populateGlbSearchThumbnails(items, batchId) {
  for (const item of items) {
    if (batchId !== catalogRuntimeState.thumbnailBatch) return;
    const furnitureId = String(item.furniture_id || "");
    if (!furnitureId || !catalogItemRenderable(item)) continue;
    const nativePreview = item.image_url
      || item.thumbnail_url
      || item.preview_url
      || item.main_image_url
      || item.image;
    if (nativePreview) continue;
    const renderKey = catalogItemRenderKey(item);
    let png = glbThumbnailCache.get(renderKey);
    if (!png) {
      try {
        await glbThumbnailViewer.loadScene(glbThumbnailScene(item));
        if (glbThumbnailViewer.getDiagnostics()?.failedFurniture?.length) continue;
        glbThumbnailViewer.selectObjectByIndex(0, {
          focus: true,
          showGuide: false,
        });
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        png = glbThumbnailViewer.capturePng();
        glbThumbnailCache.set(renderKey, png);
      } catch (error) {
        console.warn("GLB thumbnail generation failed", item.model_url, error);
        continue;
      }
    }
    if (batchId !== catalogRuntimeState.thumbnailBatch) return;
    document.querySelectorAll(
      `[data-glb-thumbnail="${CSS.escape(furnitureId)}"]`,
    ).forEach((image) => {
      image.src = png;
      image.classList.remove("is-loading");
    });
  }
}


async function styleFurnitureCandidate(item, pack) {
  const cacheKey = `${pack.styleId}:${item.normalized_type}`;
  if (!styleFurnitureCache.has(cacheKey)) {
    const payload = await api(
      `/api/furniture?type=${encodeURIComponent(item.normalized_type)}`
      + `&style=${encodeURIComponent(pack.styleId)}`
      + "&has_model=true&detail=scene&page_size=24",
    );
    styleFurnitureCache.set(cacheKey, payload.items || []);
  }
  const candidates = styleFurnitureCache.get(cacheKey);
  const currentSize = item.size_cm || {};
  return candidates.toSorted((a, b) => {
    const aSize = a.size_cm || {};
    const bSize = b.size_cm || {};
    const aDelta = Math.abs(Number(aSize.width || 0) - Number(currentSize.width || 0))
      + Math.abs(Number(aSize.depth || 0) - Number(currentSize.depth || 0));
    const bDelta = Math.abs(Number(bSize.width || 0) - Number(currentSize.width || 0))
      + Math.abs(Number(bSize.depth || 0) - Number(currentSize.depth || 0));
    return aDelta - bDelta;
  })[0] || null;
}

async function replaceUnlockedFurnitureForStyle(pack) {
  await Promise.all((state.sceneData?.scene_objects || []).map(async (item) => {
    if (item.user_specified || item.model_locked) return;
    try {
      const candidate = await styleFurnitureCandidate(item, pack);
      if (!catalogItemRenderable(candidate)) return;
      item.catalog_furniture_id = candidate.furniture_id;
      item.model_url = candidate.model_url;
      item.render_mode = candidate.render_mode || null;
      item.name_zh_raw = candidate.name_zh || candidate.name_zh_raw || item.name_zh_raw;
      item.primary_style = candidate.primary_style || pack.styleId;
    } catch (error) {
      console.warn(error);
    }
  }));
}

async function replaceSceneFurniture(furnitureId) {
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const replacement = items.find((item) => item.furniture_id === furnitureId);
  const current = state.sceneData?.scene_objects?.[state.selectedSceneIndex];
  if (!replacement || !current) return;
  const originalSize = current.size_cm;
  const candidate = {
    ...current,
    ...replacement,
    furniture_id: current.furniture_id,
    catalog_furniture_id: replacement.furniture_id,
    position_cm: current.position_cm,
    rotation_y_deg: current.rotation_y_deg,
    position_locked: true,
    user_specified: true,
    model_locked: true,
    requested_size_cm: originalSize,
    size_cm: replacement.size_cm || originalSize,
  };
  try {
    const verdict = await api("/api/scene/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        item: candidate,
        others: state.sceneData.scene_objects.filter((item) => item !== current),
      }),
    });
    if (!verdict.ok) {
      element.whiteError.textContent = `無法替換：新家具尺寸在原位置${verdict.reason || "會碰撞、穿牆或超出房間"}。`;
      setStatus(element.whiteError.textContent, "error");
      return;
    }
  } catch (error) {
    element.whiteError.textContent = errorMessage(error);
    setStatus(element.whiteError.textContent, "error");
    return;
  }
  Object.assign(current, candidate);
  state.furniture2d = upsertFurniture2dFromSceneObject(
    state.furniture2d,
    current,
    furniture2dDefaultsForSceneObject(current),
  );
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  await whiteViewer.updateObject(current);   // 只換這一件的模型，其餘不動
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  scheduleSave("white_model_3d");
  element.whiteError.textContent = "";
  setStatus("已更換實際 GLB，新尺寸與原位置已通過家具引擎檢查。");
}

function addQuestionnaireCatalogFurniture(furnitureId, catalogOffer = null) {
  const room = state.rooms.find((item) => String(item.id) === String(catalogRuntimeState.roomId));
  const furniture = roomFurnitureRequirement(room?.id);
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const offer = catalogOffer || items.find((item) => String(item.furniture_id) === String(furnitureId));
  if (!room || !furniture || !offer) return;
  const normalizedOffer = {
    ...offer,
    normalized_type: offer.normalized_type || offer.category || offer.taxonomy_type || "other",
    reason: "使用者從家具庫加入",
  };
  const known = state.roomFurnitureRecommendations[room.id] || [];
  if (!known.some((item) => String(item.furniture_id) === String(normalizedOffer.furniture_id))) {
    state.roomFurnitureRecommendations[room.id] = [...known, normalizedOffer];
  }
  const selected = (furniture.selected || []).filter(
    (item) => String(item.furniture_id) !== String(normalizedOffer.furniture_id),
  );
  selected.push({
    ...questionnaireFurnitureSelectionItem(normalizedOffer, selected.length + 1),
    selection_source: "questionnaire_catalog_add",
  });
  furniture.selected = selected.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some(
      (selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id),
    ))
    .map((item) => item.normalized_type);
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已將家具加入「${room.label}」，第 6 步需要重新產生。`);
  scheduleSave("requirements");
}

function addSceneFurniture(furnitureId) {
  const items = JSON.parse(element.glbResults.dataset.items || "[]");
  const replacement = items.find((item) => item.furniture_id === furnitureId);
  if (!replacement || !state.sceneData) return;
  const started = whiteViewer.beginPlacement(async (positionCm) => {
    const candidate = {
      ...replacement,
      furniture_id: `${replacement.furniture_id}-user-${Date.now()}`,
      catalog_furniture_id: replacement.furniture_id,
      name_zh_raw: replacement.name_zh || replacement.name_zh_raw || replacement.name_en,
      position_cm: positionCm,
      rotation_y_deg: 0,
      position_locked: true,
      user_specified: true,
      model_locked: true,
      placement_failed: false,
      size_cm: replacement.size_cm,
      requested_size_cm: replacement.size_cm,
    };
    try {
      const verdict = await api("/api/scene/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          item: candidate,
          others: state.sceneData.scene_objects,
        }),
      });
      if (!verdict.ok) {
        element.whiteError.textContent = `無法新增在該位置：${verdict.reason || "會碰撞、穿牆或超出房間"}。`;
        setStatus(element.whiteError.textContent, "error");
        return;
      }
      state.sceneData.scene_objects.push(candidate);
      state.furniture2d = upsertFurniture2dFromSceneObject(
        state.furniture2d,
        candidate,
        furniture2dDefaultsForSceneObject(candidate),
      );
      syncFurnitureInventoryAcrossSchemes();
      renderLayoutRoomFilter();
      renderLayoutFurniture();
      state.selectedSceneIndex = state.sceneData.scene_objects.length - 1;
      state.selectedFurniture2dId = candidate.furniture_id;
      await whiteViewer.addObject(candidate);   // 只加這一件，場景與其他家具不動
      renderSceneObjectList();
      renderConfigurationPlan();
      loadSelectedSceneAppearance();
      whiteViewer.selectObjectByIndex(state.selectedSceneIndex);
      activateWhiteFurnitureEditing();
      element.whiteError.textContent = "";
      scheduleSave("white_model_3d");
      const furnitureNumber = state.selectedSceneIndex + 1;
      setStatus(
        `家具 ${furnitureNumber} 已新增到指定位置，可直接拖曳或旋轉，並已通過碰撞、淨空與房間邊界檢查。`,
      );
    } catch (error) {
      element.whiteError.textContent = errorMessage(error);
      setStatus(element.whiteError.textContent, "error");
    }
  });
  if (!started) {
    element.whiteError.textContent = "3D 場景尚未準備完成，請稍候再新增家具。";
  }
}

async function confirmWhiteModel() {
  element.whiteError.textContent = "";
  if (roomSchemeSelectionRequired() && !allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) {
    element.whiteError.textContent = "請先完成所有房間的 A/B 方案選擇，才能開始微調與確認最終配置。";
    setStatus(element.whiteError.textContent, "error");
    openRoomSchemeSelectionDialog();
    return;
  }
  const blockingFurniture = configurationBlockingFurniture();
  if (blockingFurniture.length) {
    element.whiteError.textContent =
      `目前還有 ${blockingFurniture.length} 件家具位置不合法，請先從 2D 待處理清單定位修正。`;
    setStatus(element.whiteError.textContent, "error");
    renderConfigurationPlan();
    return;
  }
  const diagnostics = whiteViewer.getDiagnostics();
  const expectedFurnitureCount = state.sceneData?.scene_objects?.filter(
    (item) => !item.placement_failed,
  ).length || 0;
  if (expectedFurnitureCount > 0 && diagnostics.visibleFurnitureCount <= 0) {
    element.whiteError.textContent = "3D 中看不到家具，必須先修正載入、比例或相機框景。";
    return;
  }
  if (diagnostics.failedFurniture.length > 0) {
    element.whiteError.textContent =
      `有 ${diagnostics.failedFurniture.length} 件資料庫 GLB 無法載入，請先修正型錄權限或更換家具，才能進入下一步。`;
    setStatus(element.whiteError.textContent, "error");
    renderConfigurationPlan();
    return;
  }
  saveSelectedSceneAppearance();
  try {
    const finalValidation = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        // 只驗不排:進入即時寫實前的最終確認,信任使用者已鎖定的配置,座標照舊,
        // 只回報是否合法。少了這個旗標,伺服器會對「整屋聯集邊界」重排,把靠陽台
        // 牆、在聯集柵格裡變不合法的家具(如電視櫃)沿「沙發對面牆」推到對面 ——
        // 也就是陽台,使用者一進第 7 步就看到電視櫃跑到陽台。改用只驗不排後,
        // 真的不合法的家具會被標記交回 2D 待處理清單,而非被搬走。
        validate_only: true,
        floorplan_editor: confirmedFloorplanEditor(),
        scene_objects: (state.sceneData?.scene_objects || []).map((item) => ({
          ...item,
          position_locked: true,
        })),
      }),
    });
    const invalid = syncFinalValidationToConfiguration(finalValidation.scene_objects || []);
    if (invalid.length) {
      element.whiteError.textContent = `${invalid
        .map((item) => item.name_zh_raw || item.normalized_type || "家具")
        .join("、")}未通過最終碰撞、淨空或房間邊界檢查，請先調整。`;
      setStatus(element.whiteError.textContent, "error");
      return;
    }
  } catch (error) {
    element.whiteError.textContent = errorMessage(error);
    setStatus(element.whiteError.textContent, "error");
    return;
  }
  state.workflow.complete("white_model_3d", {
    confirmed: true,
    visibleFurnitureCount: diagnostics.visibleFurnitureCount,
    expectedFurnitureCount,
  });
  const preferredPack = STYLE_PACKS.find(
    (pack) => pack.id === state.questionnaireFinishes.stylePackId,
  ) || STYLE_PACKS[0];
  state.activeStyleId = preferredPack.styleId;
  state.activeStylePackId = preferredPack.id;
  state.surfaceState = state.stepSixSurfacesReady ? state.surfaceState : {
    wall: {
      material: state.questionnaireFinishes.wallMaterial || preferredPack.wall.surfaceOption,
      color: state.questionnaireFinishes.wallColor || preferredPack.wall.color,
    },
    floor: {
      material: state.questionnaireFinishes.floorMaterial || preferredPack.floor.surfaceOption,
      color: state.questionnaireFinishes.floorColor || preferredPack.floor.color,
    },
    furniture: state.sceneData.scene_objects.map((item) => ({
      id: item.furniture_id,
      styleLocked: item.user_specified || item.model_locked || item.material_locked,
      material: {
        color: item.specified_color || "#f2f0ec",
        kind: item.specified_material || "",
      },
    })),
  };
  state.sceneData.style = {
    ...(state.sceneData.style || {}),
    style_id: preferredPack.styleId,
    style_name_zh: preferredPack.styleLabel,
    palette_hex: preferredPack.palette,
    pbr: {
      wall: preferredPack.wall.pbr,
      floor: preferredPack.floor.pbr,
      furniture: preferredPack.furniture.pbr,
    },
  };
  state.sceneData.style_card = {
    card_id: preferredPack.id,
    name_zh: preferredPack.name,
    palette_hex: preferredPack.palette,
    source_image: preferredPack.sourceImage,
  };
  state.sceneData.design_choices = state.sceneData.design_choices || {};
  state.sceneData.design_choices.ceiling_material = state.questionnaireFinishes.ceilingMaterial;
  state.sceneData.design_choices.ceiling_color_hex = state.questionnaireFinishes.ceilingColor;
  state.sceneData.design_choices.ceiling_style = state.questionnaireFinishes.ceilingStyle;
  state.sceneData.design_choices.light_style = state.questionnaireFinishes.lightStyle;
  state.roomFinishDrafts = state.roomFinishDrafts || {};
  state.rooms.forEach((room) => {
    const existing = state.roomFinishDrafts?.[String(room.id)] || {};
    state.roomFinishDrafts[String(room.id)] = {
      ...roomFinishDraftFor(room),
      ...existing,
      stepSixSurfaceConfirmed: existing.stepSixSurfaceConfirmed === true,
      stepSixSurfaceConfirmedAt: existing.stepSixSurfaceConfirmedAt || null,
    };
  });
  applyQuestionnaireSurfaceOverridesToScene();
  state.stepSixSurfacesReady = true;
  await whiteViewer.updateRoomSurfaces(state.sceneData);
  if (!state.workflow.goTo("realistic_3d")) {
    throw new Error(firstWorkflowBlocker("realistic_3d"));
  }
  showStep("realistic_3d", { preparePanel: false });
  focusStepSixRoom(state.selectedRoomId || state.rooms[0]?.id);
  const ceilingLabel = ceilingStyleLabel(state.questionnaireFinishes.ceilingStyle || "flat");
  setStatus(expectedFurnitureCount
    ? `家具可見性已通過。可逐房微調牆面與地面；天花以統一預覽層顯示，最終生圖會依問卷呈現「${ceilingLabel}」。`
    : `純結構配置已確認。可逐房微調牆面與地面；最終生圖會依問卷呈現「${ceilingLabel}」天花。`);
  scheduleSave("realistic_3d");
}


function ceilingStyleLabel(id) {
  return CEILING_STYLES.find((item) => item.id === id)?.label || id;
}


function allowedLightsForCeiling(ceilingId) {
  const ceiling = CEILING_STYLES.find((item) => item.id === ceilingId);
  const allowed = new Set(ceiling?.compatibleLightIds || CEILING_DESIGN_PACKS
    .filter((item) => item.ceilingStyle === ceilingId)
    .map((item) => item.lightStyle));
  return LIGHT_STYLES.filter((item) => !allowed.size || allowed.has(item.id));
}

function renderStyleControls() {
  const packs = STYLE_PACKS.filter((pack) => pack.styleId === state.activeStyleId);
  const activePack = stylePackByIdSafe(state.activeStylePackId) || packs[0];
  if (element.styleTabs) {
    const styles = [...new Map(STYLE_PACKS.map((pack) => [pack.styleId, pack.styleLabel])).entries()];
    element.styleTabs.innerHTML = styles.map(([id, label]) =>
      '<button type="button" data-style-tab="' + escapeHtml(id) + '" class="' + (id === state.activeStyleId ? "is-active" : "") + '">' + escapeHtml(label) + "</button>"
    ).join("");
  }
  if (element.styleGrid) {
    element.styleGrid.innerHTML = packs.map((pack) =>
      '<button type="button" data-style-pack="' + escapeHtml(pack.id) + '" class="' + (pack.id === state.activeStylePackId ? "is-active" : "") + '">' +
      '<img class="rp-style-card-preview" src="' + escapeHtml(pack.sourceImage) + '" alt="' + escapeHtml(pack.name) + '" loading="lazy">' +
      "<strong>" + escapeHtml(pack.name) + "</strong></button>"
    ).join("");
  }
  if (!activePack) return;
  const room = selectedStepSixRoom();
  const draft = roomFinishDraftFor(room);
  renderGroupedMaterialOptions(activePack);
  const wallOption = resolveSurfaceOption(state.sceneData?.surface_catalog, "wall", draft.wallMaterial);
  const floorOption = resolveSurfaceOption(state.sceneData?.surface_catalog, "floor", draft.floorMaterial);
  if ($("#wall-color")) $("#wall-color").value = draft.wallColor || wallOption?.color || activePack.wall.color;
  if ($("#floor-color")) $("#floor-color").value = draft.floorColor || floorOption?.color || activePack.floor.color;
  renderStepSixColorSwatches("wall", activePack);
  renderStepSixColorSwatches("floor", activePack);

  element.ceilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(item.label) + "</option>"
  ).join("");
  const fallbackCeiling = CEILING_STYLES.find((item) => item.styles.includes(state.activeStyleId)) || CEILING_STYLES[0];
  element.ceilingStyle.value = CEILING_STYLES.some((item) => item.id === draft.ceilingStyle)
    ? draft.ceilingStyle
    : fallbackCeiling.id;
  const lightOptions = allowedLightsForCeiling(element.ceilingStyle.value);
  element.lightStyle.innerHTML = lightOptions.map((item) =>
    '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(item.label) + "</option>"
  ).join("");
  const fallbackLight = lightOptions.find((item) => item.styles.includes(state.activeStyleId)) || lightOptions[0];
  element.lightStyle.value = lightOptions.some((item) => item.id === draft.lightStyle)
    ? draft.lightStyle
    : fallbackLight.id;
  if (element.boundarySecondaryFloor) {
    element.boundarySecondaryFloor.innerHTML = $("#floor-material").innerHTML;
    element.boundarySecondaryFloor.value = draft.boundarySecondaryFloor || $("#floor-material").value;
  }
  const roomOverride = (state.sceneData?.surface_overrides || []).find(
    (item) => String(item.room_id) === String(room?.id),
  );
  const boundary = draft.materialBoundary || roomOverride?.material_boundary || null;
  state.materialBoundary = boundary;
  if (boundary) {
    if ($("#material-boundary-direction")) $("#material-boundary-direction").value = boundary.direction || "vertical";
    if ($("#material-boundary-position")) {
      $("#material-boundary-position").value = Math.round(Number(boundary.ratio ?? 0.5) * 100);
    }
    if ($("#material-boundary-status")) {
      $("#material-boundary-status").textContent = `已建立${boundary.direction === "horizontal" ? "水平" : "垂直"}界線。`;
    }
  } else if ($("#material-boundary-status")) {
    $("#material-boundary-status").textContent = "尚未建立混搭界線。";
  }
  if (element.surfaceRoomQuestionnaire) {
    element.surfaceRoomQuestionnaire.textContent = roomQuestionnaireSummary(room);
  }
  setStepSixSurfaceKind(state.stepSixSurfaceKind);
}

function syncSurfaceMaterialSelect(kind, items, current) {
  const select = $(`#${kind}-material`);
  if (!select) return "";
  select.innerHTML = items.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  const materialId = items.some((item) => item.id === current)
    ? current
    : items[0]?.id || "";
  select.value = materialId;
  return materialId;
}

function surfaceRecommendationScore(item, recommendedId, activePack) {
  const scoreFor = item.scoreFor || {};
  const packScore = Number(scoreFor[activePack?.id] || 0);
  const styleScore = Number(scoreFor[activePack?.styleId] || 0);
  const directScore = item.id === recommendedId ? 100 : 0;
  return directScore + packScore + styleScore + Number(item.baseScore || 0);
}

function surfaceRecommendationReason(item, activePack, kind) {
  if (item.reason) return item.reason;
  const styleName = activePack?.styleLabel || "目前風格";
  const packName = activePack?.name || "";
  const source = packName ? `${styleName}「${packName}」` : styleName;
  return kind === "wall"
    ? `${source}先用牆面控制明度與背景份量，再讓家具成為主角。`
    : `${source}以地面決定主調，這個材質能接住家具色與採光。`;
}

const SURFACE_VARIANT_OPTIONS = Object.freeze({
  scandinavian: {
    wall: [
      { id: "sage", label: "鼠尾草礦物漆", color: "#D8DDCF", materialPreview: "", reason: "北歐風如果家具偏淺木，低彩度綠牆能增加層次，不會只剩白牆。", scoreFor: { scandinavian_2: 55 } },
      { id: "mineral_beige", label: "米灰礦物塗料", color: "#DDD2C1", materialPreview: "", reason: "用米灰牆降低白牆冷感，適合小坪數與自然光不足的房間。", scoreFor: { scandinavian: 18 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "人字拼橡木", color: "#C8A16F", materialPreview: "", reason: "想讓北歐不那麼制式時，人字拼能保留木質溫度並增加精緻度。", scoreFor: { scandinavian_3: 65 } },
    ],
  },
  japanese: {
    wall: [
      { id: "sand", label: "砂岩感塗料", color: "#D8C6A9", materialPreview: "", reason: "砂岩色能接住榻榻米、藤編與紙燈，不會像純白牆那麼硬。", scoreFor: { japanese: 40 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "細拼淺木地板", color: "#D2B889", materialPreview: "", reason: "細拼木紋讓日系空間比較有手作感，適合想要溫潤但不厚重的配置。", scoreFor: { japanese_1: 45 } },
    ],
  },
  modern_minimal: {
    wall: [
      { id: "greige", label: "灰米微水泥牆", color: "#BEB8AF", materialPreview: "", reason: "現代簡約需要乾淨背景，灰米牆比白牆更能襯出黑金屬與石材。", scoreFor: { modern_minimal_2: 70 } },
    ],
    floor: [
      { id: "microcement", label: "霧面微水泥地坪", color: "#9B9992", materialPreview: "", reason: "微水泥適合俐落線條與低彩度家具，比木地板更有都會感。", scoreFor: { modern_minimal: 35, modern_minimal_2: 60 } },
    ],
  },
  cream: {
    wall: [
      { id: "mineral_beige", label: "奶茶礦物塗料", color: "#E7D8C3", materialPreview: "", reason: "奶油風需要暖底但不能太黃，奶茶礦物牆能讓白色家具有陰影層次。", scoreFor: { cream: 45 } },
    ],
    floor: [
      { id: "herringbone_oak", label: "柔光人字木地板", color: "#DEC393", materialPreview: "", reason: "柔光人字拼比一般淺橡木更有精緻感，適合奶油風的圓角家具。", scoreFor: { cream_3: 55 } },
    ],
  },
  industrial: {
    wall: [
      { id: "greige", label: "斑駁灰泥牆", color: "#8E8A82", materialPreview: "", reason: "工業風不一定要全黑，灰泥牆能保留粗獷但讓空間不壓迫。", scoreFor: { industrial_1: 50 } },
    ],
    floor: [
      { id: "walnut", label: "深胡桃木地板", color: "#76583E", materialPreview: "", reason: "深木地板能平衡鐵件與水泥，讓工業風比較像住宅而不是展場。", scoreFor: { industrial_2: 48 } },
    ],
  },
  american: {
    wall: [
      { id: "mineral_beige", label: "暖米礦物漆", color: "#E5D8C4", materialPreview: "", reason: "美式家具份量較重，暖米牆能柔化線板與深木色。", scoreFor: { american: 30 } },
    ],
    floor: [
      { id: "marble", label: "柔紋石材地坪", color: "#DDD2BF", materialPreview: "", reason: "想做輕奢美式時，柔紋石材比固定木地板更有正式感。", scoreFor: { american_3: 52 } },
    ],
  },
});

function materialOptionsForStyle(styleId, kind, baseOptions) {
  const merged = new Map((baseOptions || []).map((item) => [item.id, item]));
  for (const item of SURFACE_VARIANT_OPTIONS[styleId]?.[kind] || []) {
    merged.set(item.id, { ...(merged.get(item.id) || {}), ...item });
  }
  return [...merged.values()];
}

function recommendedStepSixMaterialOptions(
  kind,
  activePack,
  room = selectedStepSixRoom(),
) {
  const merged = new Map();
  const styleId = activePack?.styleId || state.activeStyleId;
  const styleOptions = STYLE_MATERIAL_OPTIONS[styleId] || {};
  materialOptionsForStyle(styleId, kind, styleOptions[kind])
    .forEach((item) => merged.set(item.id, item));
  styleCompatibleMaterialOptionsForPack(kind, activePack, room)
    .forEach((item) => merged.set(item.id, { ...(merged.get(item.id) || {}), ...item }));
  return [...merged.values()].sort((left, right) => {
    const pairDifference = materialPairScore(kind, right, activePack, room)
      - materialPairScore(kind, left, activePack, room);
    if (pairDifference) return pairDifference;
    return surfaceRecommendationScore(right, activePack?.[kind]?.surfaceOption, activePack)
      - surfaceRecommendationScore(left, activePack?.[kind]?.surfaceOption, activePack);
  });
}

function allStepSixMaterialOptions(
  kind,
  activePack,
  room = selectedStepSixRoom(),
  catalogOptions = catalogMaterialOptionsForPack(kind, activePack),
) {
  const merged = new Map();
  const styleOptions = STYLE_MATERIAL_OPTIONS[state.activeStyleId]
    || STYLE_MATERIAL_OPTIONS[activePack?.styleId]
    || {};
  materialOptionsForStyle(activePack?.styleId || state.activeStyleId, kind, styleOptions[kind])
    .forEach((item) => merged.set(item.id, item));
  styleCompatibleMaterialOptionsForPack(kind, activePack, room)
    .forEach((item) => merged.set(item.id, { ...(merged.get(item.id) || {}), ...item }));
  catalogOptions.forEach((item) => {
    if (!merged.has(item.id)) merged.set(item.id, item);
  });
  Object.entries(STYLE_MATERIAL_OPTIONS).forEach(([styleId, options]) => {
    materialOptionsForStyle(styleId, kind, options[kind])
      .forEach((item) => {
        if (!merged.has(item.id)) merged.set(item.id, item);
      });
  });
  return [...merged.values()].sort((left, right) =>
    surfaceRecommendationScore(right, activePack?.[kind]?.surfaceOption, activePack)
      - surfaceRecommendationScore(left, activePack?.[kind]?.surfaceOption, activePack)
  );
}

function stepSixSurfaceSelection(kind) {
  const room = selectedStepSixRoom();
  const draft = roomFinishDraftFor(room);
  const material = $("#" + kind + "-material")?.value
    || draft[kind + "Material"]
    || "";
  const color = $("#" + kind + "-color")?.value
    || draft[kind + "Color"]
    || "";
  return { material, color };
}

function renderStepSixColorSwatches(kind, activePack) {
  const host = $("#" + kind + "-color-swatches");
  if (!host) return;
  const current = stepSixSurfaceSelection(kind).color;
  const options = recommendedStepSixMaterialOptions(kind, activePack)
    .slice(0, STEP_SIX_SURFACE_MATERIAL_LIMIT);
  const fallback = kind === "wall"
    ? ["#f4efe4", "#ded7ca", "#c7c6c0", "#a8b3a5", "#8b8780", "#4d4c48"]
    : ["#d8bd92", "#b89469", "#927252", "#b9b7b0", "#8f8c86", "#ded5c8"];
  const colors = [...new Set([
    current,
    ...(activePack?.palette || []),
    ...options.map((item) => item.color),
    ...fallback,
  ].filter((color) => /^#[0-9a-f]{6}$/i.test(String(color))))]
    .slice(0, STEP_SIX_SURFACE_SWATCH_LIMIT);
  host.innerHTML = colors.map((color) => `
    <button type="button" data-surface-color-swatch data-surface-color-kind="${escapeHtml(kind)}"
      data-surface-color-value="${escapeHtml(color)}"
      class="${String(color).toLowerCase() === String(current).toLowerCase() ? "is-active" : ""}"
      style="--surface-swatch:${escapeHtml(color)}"
      aria-label="使用 ${escapeHtml(color)}" title="${escapeHtml(color)}"></button>
  `).join("");
}

function renderGroupedMaterialOptions(activePack) {
  const render = (kind, host) => {
    if (!host) return;
    const recommendedId = activePack?.[kind]?.surfaceOption;
    const room = selectedStepSixRoom();
    const draft = roomFinishDraftFor(room);
    const catalogItems = catalogMaterialOptionsForPack(kind, activePack);
    const items = allStepSixMaterialOptions(kind, activePack, room, catalogItems);
    const recommendedItems = recommendedStepSixMaterialOptions(kind, activePack, room);
    const current = draft[kind + "Material"] || $(`#${kind}-material`)?.value;
    const selectedMaterial = syncSurfaceMaterialSelect(kind, items, current);
    const visibleItems = recommendedItems.slice(0, STEP_SIX_SURFACE_MATERIAL_LIMIT);
    host.innerHTML = visibleItems.map((item) => `
      <button type="button"
        data-surface-material-card
        data-surface-kind="${escapeHtml(kind)}"
        data-surface-material="${escapeHtml(item.id)}"
        data-surface-color="${escapeHtml(item.color || "")}"
        data-material-preview="${escapeHtml(item.materialPreview || "")}"
        data-style-card-recommended="${item.id === recommendedId ? "true" : "false"}"
        title="${escapeHtml(surfaceRecommendationReason(item, activePack, kind))}"
        class="${item.id === selectedMaterial ? "is-active" : ""}">
        <span class="rp-material-preview" style="background:${escapeHtml(item.color || "#ddd")};${item.materialPreview ? `background-image:url('${escapeHtml(item.materialPreview)}')` : ""}"></span>
        <span class="rp-material-copy">
          <strong>${escapeHtml(item.label)}${item.id === recommendedId ? " · 推薦" : ""}</strong>
          ${materialVisualTagMarkup(item.visualTags)}
          <small>${escapeHtml(item.materialGroup || item.note || surfaceRecommendationReason(item, activePack, kind))}</small>
        </span>
      </button>
    `).join("");
    if (kind === state.stepSixSurfaceKind && element.surfaceSelectedDescription) {
      const selected = items.find((item) => item.id === selectedMaterial) || visibleItems[0];
      element.surfaceSelectedDescription.textContent = selected
        ? `${selected.label}：${surfaceRecommendationReason(selected, activePack, kind)}`
        : "尚未選擇材質。";
    }
  };
  render("wall", element.wallMaterialGrouped);
  render("floor", element.floorMaterialGrouped);
}

function stylePackByIdSafe(packId) {
  return STYLE_PACKS.find((pack) => pack.id === packId) || null;
}


async function applyStylePackToScene(pack) {
  if (!pack || !state.sceneData) return;
  pruneAutomaticSoftDecor();
  const revision = ++styleApplyRevision;
  const roomSurfaceOverrides = JSON.parse(JSON.stringify(
    state.sceneData.surface_overrides || [],
  ));
  const existingMaterialBoundary = state.sceneData.material_boundary || null;
  if (state.activeStylePackId) {
    state.styleHistory.push({
      packId: state.activeStylePackId,
      surfaceState: JSON.parse(JSON.stringify(state.surfaceState)),
    });
  }
  const previousSceneStyle = state.sceneData.style?.style_id;
  state.activeStylePackId = pack.id;
  state.activeStyleId = pack.styleId;
  state.surfaceState = applyStylePack(state.surfaceState, pack);
  state.sceneData.surface_overrides = roomSurfaceOverrides;
  state.sceneData.material_boundary = existingMaterialBoundary;
  state.materialBoundary = existingMaterialBoundary;
  const scopeControl = $("#surface-scope");
  if (scopeControl) scopeControl.value = "house";
  state.sceneData.style = {
    ...(state.sceneData.style || {}),
    style_id: pack.styleId,
    style_name_zh: pack.styleLabel,
    palette_hex: pack.palette,
    pbr: {
      wall: pack.wall.pbr,
      floor: pack.floor.pbr,
      furniture: pack.furniture.pbr,
    },
    furniture_rules: pack.furnitureRules,
    decor_rules: pack.decorRules,
    placement_rules: pack.placementRules,
    lighting: pack.lighting,
    rendering: pack.rendering,
  };
  state.sceneData.style_card = {
    card_id: pack.id,
    name_zh: pack.name,
    palette_hex: pack.palette,
    source_image: pack.sourceImage,
  };
  state.sceneData.design_choices = state.sceneData.design_choices || {};
  state.sceneData.design_choices.wall_color_hex = pack.wall.color;
  state.sceneData.design_choices.wall_option = resolveSurfaceOption(
    state.sceneData.surface_catalog,
    "wall",
    pack.wall.surfaceOption,
  );
  state.sceneData.design_choices.floor_color_hex = pack.floor.color;
  state.sceneData.design_choices.floor_option = resolveSurfaceOption(
    state.sceneData.surface_catalog,
    "floor",
    pack.floor.surfaceOption,
  );
  // 房間問卷的材質選擇優先於全屋風格預設，避免第 6 步回到風格的卡通底色。
  applyQuestionnaireSurfaceOverridesToScene();
  const applyFurnitureMaterials = () => state.sceneData.scene_objects.forEach((item) => {
    const locks = state.surfaceState.furniture.find((candidate) => candidate.id === item.furniture_id);
    if (locks?.styleLocked) return;
    item.material_override = {
      color: pack.furniture.color,
      accent: pack.furniture.accent,
      pbr: pack.furniture.pbr,
    };
  });
  applyFurnitureMaterials();
  renderSceneObjectList();
  loadSelectedSceneAppearance();
  renderStyleControls();
  element.realisticStatus.textContent = `正在套用「${pack.styleLabel}／${pack.name}」的牆面、地板與燈光…`;
  await realisticViewer.loadScene(state.sceneData);
  if (revision !== styleApplyRevision) return;
  realisticViewer.setViewMode("orbit");
  element.realisticStatus.textContent = `已套用「${pack.styleLabel}／${pack.name}」的牆面、地板、PBR 與燈光；家具搭配更新中。`;
  scheduleSave("realistic_3d");

  try {
    if (previousSceneStyle !== pack.styleId) {
      await replaceUnlockedFurnitureForStyle(pack);
    }
    if (revision !== styleApplyRevision) return;
    applyFurnitureMaterials();
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    await realisticViewer.loadScene(state.sceneData);
    if (revision !== styleApplyRevision) return;
    realisticViewer.setViewMode("orbit");
  } catch (error) {
    console.warn(error);
    element.realisticStatus.textContent = `牆面、地板與燈光已套用；家具或軟裝更新失敗：${errorMessage(error)}`;
    scheduleSave("realistic_3d");
    return;
  }
  await evaluateCeilingConflicts();
  element.realisticStatus.textContent = `${pack.styleLabel}／${pack.name}：牆、地板、未鎖定家具與環境光已同步；軟裝與擺放規則已載入，新增物件仍須通過家具引擎配置。`;
  element.realisticStatus.textContent = `已完成「${pack.styleLabel}／${pack.name}」：牆面、地板、PBR、燈光與未鎖定家具均已同步。`;
  scheduleSave("realistic_3d");
}

async function applySurfaceOverrides({ userInitiated = false, markDirty = true } = {}) {
  const scope = "room";
  const selectedRoom = state.rooms.find(
    (item) => String(item.id) === String(state.selectedRoomId),
  ) || state.rooms[0];
  if (!selectedRoom || !state.sceneData) return null;
  if (markDirty && stepSixRoomSurfaceConfirmed(selectedRoom)) {
    setStepSixSurfaceStatus("此房間材質已鎖定；請先按「重新修改此房間」。");
    return null;
  }
  if (userInitiated && scope !== "house" && selectedRoom && isCirculationRoom(selectedRoom)
    && !circulationStyleIsOverridden(selectedRoom)) {
    const livingRoom = livingRoomForCirculation();
    const approved = window.confirm(
      `走道目前沿用「${livingRoom?.label || "客廳"}」的風格與材質。改為獨立風格會讓動線出現視覺差異，並在第 6 步重新檢查銜接。要繼續嗎？`,
    );
    if (!approved) {
      element.realisticStatus.textContent = "已保留走道與客廳一致的風格與材質。";
      return;
    }
    const requirement = state.roomRequirementModel?.roomRequirements?.[selectedRoom.id];
    if (requirement) requirement.circulationStyleOverrideApproved = true;
  }
  state.surfaceState.wall = {
    ...(state.surfaceState.wall || {}),
    color: $("#wall-color").value,
    material: $("#wall-material").value,
    styleLocked: true,
    scope,
  };
  state.surfaceState.floor = {
    ...(state.surfaceState.floor || {}),
    color: $("#floor-color").value,
    material: $("#floor-material").value,
    styleLocked: true,
    scope,
  };
  const room = selectedRoom;
  const previousOverride = (state.sceneData.surface_overrides || [])
    .find((item) => String(item.room_id) === String(room.id)) || {};
  const wallMaterial = state.surfaceState.wall.material;
  const floorMaterial = state.surfaceState.floor.material;
  const previousDraft = state.roomFinishDrafts?.[String(room.id)] || {};
  state.roomFinishDrafts = state.roomFinishDrafts || {};
  state.roomFinishDrafts[String(room.id)] = {
    ...roomFinishDraftFor(room),
    wallMaterial,
    wallColor: state.surfaceState.wall.color,
    floorMaterial,
    floorColor: state.surfaceState.floor.color,
    wallOverrideExplicit: true,
    floorOverrideExplicit: true,
    stepSixSurfaceConfirmed: markDirty ? false : previousDraft.stepSixSurfaceConfirmed === true,
    stepSixSurfaceConfirmedAt: markDirty ? null : previousDraft.stepSixSurfaceConfirmedAt || null,
  };
  const center = planCenterCm();
  const override = {
    ...previousOverride,
    room_id: room.id,
    room_label: room.label,
    room_bounds_cm: {
      minX: Math.min(...room.polygon_cm.map((point) => point.x)) - center.x,
      maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - center.x,
      minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - center.y,
      maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - center.y,
    },
    room_polygon_cm: room.polygon_cm.map((point) => ({
      x: point.x - center.x,
      z: point.y - center.y,
    })),
    wall_color_hex: state.surfaceState.wall.color,
    floor_color_hex: state.surfaceState.floor.color,
    wallOverrideExplicit: true,
    floorOverrideExplicit: true,
    wall_option: resolveSurfaceOption(
      state.sceneData.surface_catalog,
      "wall",
      state.surfaceState.wall.material,
    ),
    floor_option: resolveSurfaceOption(
      state.sceneData.surface_catalog,
      "floor",
      state.surfaceState.floor.material,
    ),
  };
  state.sceneData.surface_overrides = [
    ...(state.sceneData.surface_overrides || [])
      .filter((item) => String(item.room_id) !== String(room.id)),
    override,
  ];
  const scopeLabel = $("#surface-scope option:checked")?.textContent?.trim()
    || selectedRoom?.label
    || "目前房間";
  if (userInitiated) setStepSixSurfaceStatus(`已更新${scopeLabel}草稿；其他空間不受影響。`);
  return { room, draft: state.roomFinishDrafts[String(room.id)], override };
}

async function previewStepSixRoomSurfaces({ userInitiated = false, markDirty = true, preserveCamera = true } = {}) {
  void preserveCamera;
  const applied = await applySurfaceOverrides({ userInitiated, markDirty });
  if (!applied) return false;
  await whiteViewer.updateRoomSurfaces(state.sceneData, applied.room.id);
  renderStyleControls();
  renderStepSixSurfaceProgress();
  if (markDirty) scheduleSave("realistic_3d");
  return true;
}

function firstUnconfirmedStepSixRoom() {
  return state.rooms.find((room) => !stepSixRoomSurfaceConfirmed(room)) || null;
}

function nextUnconfirmedStepSixRoom(currentRoomId) {
  const currentIndex = state.rooms.findIndex(
    (room) => String(room.id) === String(currentRoomId),
  );
  const ordered = [
    ...state.rooms.slice(currentIndex + 1),
    ...state.rooms.slice(0, Math.max(0, currentIndex + 1)),
  ];
  return ordered.find((room) => !stepSixRoomSurfaceConfirmed(room)) || null;
}

async function confirmStepSixRoomSurfaces() {
  const room = selectedStepSixRoom();
  if (!room || !state.sceneData) return false;
  await previewStepSixRoomSurfaces({ userInitiated: false, markDirty: false });
  const draft = roomFinishDraftFor(room);
  state.roomFinishDrafts[String(room.id)] = {
    ...draft,
    stepSixSurfaceConfirmed: true,
    stepSixSurfaceConfirmedAt: new Date().toISOString(),
  };
  const requirement = state.roomRequirementModel?.roomRequirements?.[String(room.id)];
  if (requirement) {
    requirement.surfaces = {
      ...(requirement.surfaces || {}),
      wallDefault: { materialId: draft.wallMaterial, color: draft.wallColor },
      floor: { materialId: draft.floorMaterial, color: draft.floorColor },
      wallOverrideExplicit: true,
      floorOverrideExplicit: true,
    };
  }
  refreshConfigurationSnapshot();
  renderStepSixSurfaceProgress();
  scheduleSave("realistic_3d");
  const nextRoom = nextUnconfirmedStepSixRoom(room.id);
  if (nextRoom) {
    focusStepSixRoom(nextRoom.id);
    setStepSixSurfaceStatus(`「${room.label}」材質已確認；接著確認「${nextRoom.label}」。`);
  } else {
    setStepSixSurfaceStatus("所有房間材質皆已確認，可前往第 7 步。");
  }
  return true;
}

function unlockStepSixRoomSurfaces() {
  const room = selectedStepSixRoom();
  if (!room) return;
  if (stepSixSurfacesFinalLocked()) {
    setStepSixSurfaceStatus("已進入第 7 步，房間材質已正式鎖定。若要重做，需先重開第 6 步流程。");
    return;
  }
  state.roomFinishDrafts[String(room.id)] = {
    ...roomFinishDraftFor(room),
    stepSixSurfaceConfirmed: false,
    stepSixSurfaceConfirmedAt: null,
  };
  renderStyleControls();
  renderStepSixSurfaceProgress();
  setStepSixSurfaceStatus(`「${room.label}」已解除鎖定，可繼續修改草稿。`);
  scheduleSave("realistic_3d");
}

function toggleMaterialBoundary() {
  const room = state.rooms.find(
    (item) => String(item.id) === String(state.selectedRoomId),
  ) || state.rooms[0];
  if (!room) return;
  const planCenter = planCenterCm();
  const bounds = {
    minX: Math.min(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
    maxX: Math.max(...room.polygon_cm.map((point) => point.x)) - planCenter.x,
    minZ: Math.min(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
    maxZ: Math.max(...room.polygon_cm.map((point) => point.y)) - planCenter.y,
  };
  const direction = $("#material-boundary-direction").value;
  const ratio = Number($("#material-boundary-position").value) / 100;
  const secondaryFloor = element.boundarySecondaryFloor?.value
    || $("#floor-material").value;
  const splitX = bounds.minX + (bounds.maxX - bounds.minX) * ratio;
  const splitZ = bounds.minZ + (bounds.maxZ - bounds.minZ) * ratio;
  state.materialBoundary = {
    surface: "floor",
    roomId: room.id,
    direction,
    ratio,
    line_cm: direction === "horizontal"
      ? [
          { x: bounds.minX, y: splitZ },
          { x: bounds.maxX, y: splitZ },
        ]
      : [
          { x: splitX, y: bounds.minZ },
          { x: splitX, y: bounds.maxZ },
        ],
    room_bounds_cm: bounds,
    materials: ["current-floor", "secondary-floor"],
    primary_floor_option: resolveSurfaceOption(
      state.sceneData?.surface_catalog,
      "floor",
      $("#floor-material").value,
    ),
    secondary_floor_option: resolveSurfaceOption(
      state.sceneData?.surface_catalog,
      "floor",
      secondaryFloor,
    ),
    primary_floor_color_hex: $("#floor-color").value,
    secondary_floor_color_hex: $("#floor-color").value,
  };
  if (state.sceneData) {
    state.sceneData.material_boundary = state.materialBoundary;
    upsertRoomSurfaceOverride(room, { material_boundary: state.materialBoundary });
    void whiteViewer.updateRoomSurfaces(state.sceneData, room.id);
  }
  state.roomFinishDrafts[String(room.id)] = {
    ...roomFinishDraftFor(room),
    materialBoundary: state.materialBoundary,
    stepSixSurfaceConfirmed: false,
    stepSixSurfaceConfirmedAt: null,
  };
  $("#material-boundary-status").textContent =
    `已在${room.label}建立${direction === "horizontal" ? "水平" : "垂直"}界線，位置 ${Math.round(ratio * 100)}%。`;
  renderStepSixSurfaceProgress();
  scheduleSave("realistic_3d");
}

function removeMaterialBoundary() {
  const room = selectedStepSixRoom();
  state.materialBoundary = null;
  if (state.sceneData) {
    state.sceneData.material_boundary = null;
    if (room) upsertRoomSurfaceOverride(room, { material_boundary: null });
    void whiteViewer.updateRoomSurfaces(state.sceneData, room?.id);
  }
  if (room) {
    state.roomFinishDrafts[String(room.id)] = {
      ...roomFinishDraftFor(room),
      materialBoundary: null,
      stepSixSurfaceConfirmed: false,
      stepSixSurfaceConfirmedAt: null,
    };
  }
  $("#material-boundary-status").textContent = "已移除混搭材質界線。";
  renderStepSixSurfaceProgress();
  scheduleSave("realistic_3d");
}

function roomLabelAtPlanPoint(point) {
  const room = state.rooms.find((candidate) => {
    const xs = candidate.polygon_cm.map((vertex) => vertex.x);
    const ys = candidate.polygon_cm.map((vertex) => vertex.y);
    return point.x >= Math.min(...xs)
      && point.x <= Math.max(...xs)
      && point.y >= Math.min(...ys)
      && point.y <= Math.max(...ys);
  });
  return room?.label || "全屋";
}

async function evaluateCeilingConflicts() {
  const ceiling = CEILING_STYLES.find((item) => item.id === element.ceilingStyle.value)
    || CEILING_STYLES[0];
  const light = LIGHT_STYLES.find((item) => item.id === element.lightStyle.value)
    || LIGHT_STYLES[0];
  const roomHeightCm = Number(
    state.sceneData?.floorplan?.room_height_cm
    || state.confirmedFloorplan?.floorplan?.room_height_cm
    || 270,
  );
  const planCenter = planCenterCm();
  if (state.sceneData) {
    state.sceneData.design_choices = state.sceneData.design_choices || {};
    state.sceneData.design_choices.ceiling_style = ceiling.id;
    state.sceneData.design_choices.ceiling_drop_cm = ceiling.dropCm;
    state.sceneData.design_choices.light_style = light.id;
  }
  const result = detectCeilingConflicts({
    ceilingStyle: ceiling.id,
    roomHeightCm,
    beams: state.structures.beams.map((beam, index) => {
      const topCm = Number(beam.top_cm) || roomHeightCm;
      const heightCm = Number(beam.height_cm ?? beam.thickness_cm) || 30;
      const midpoint = {
        x: (Number(beam.start?.x || 0) + Number(beam.end?.x || 0)) / 2,
        y: (Number(beam.start?.y || 0) + Number(beam.end?.y || 0)) / 2,
      };
      return {
        id: beam.id,
        kind: "beam",
        label: `樑 ${index + 1}`,
        topCm,
        bottomCm: topCm - heightCm,
        estimated: beam.estimated === true || beam.top_cm == null,
        roomLabel: roomLabelAtPlanPoint(midpoint),
      };
    }),
    cabinets: state.sceneData?.scene_objects
      ?.filter((item) => ["wardrobe", "cabinet", "bookcase"].includes(item.normalized_type))
      .map((item) => {
        const position = item.position_cm || {};
        return {
          id: item.furniture_id,
          kind: "cabinet",
          label: item.name_zh_raw || "櫃體",
          topCm: Number(item.size_cm?.height || 0),
          roomLabel: roomLabelAtPlanPoint({
            x: planCenter.x + Number(position.x || 0),
            y: planCenter.y + Number(position.z || 0),
          }),
        };
      }) || [],
    lights: [{
      id: light.id,
      kind: "light",
      label: light.label,
      requiredPlenumCm: light.installationDepthCm,
      roomLabel: "全屋",
    }],
  });
  element.ceilingConflicts.innerHTML = result.conflicts.length
    ? result.conflicts.map((conflict) => `
      <article class="rp-conflict-item">
        <strong>${escapeHtml(conflict.location)}：${escapeHtml(conflict.objectLabel)}</strong>
        <p>${escapeHtml(conflict.reason)} ${escapeHtml(conflict.impact)}</p>
        <p>AI 建議：${escapeHtml(conflict.recommendations.join("；"))}。套用前會再次做幾何驗證。</p>
      </article>
    `).join("")
    : `<p>完成天花高度 ${result.finishedHeightCm} cm，目前未偵測到樑、櫃體或燈具衝突。</p>`;
  if (state.sceneData && state.workflow?.currentStep === "realistic_3d") {
    await realisticViewer.loadScene(state.sceneData);
    realisticViewer.setViewMode("orbit");
  }
}

// Step 6 stores finishes per room.  Keep the questionnaire as the source of
// truth, then materialize a viewer-friendly override only when rendering.
function roomSurfaceBounds(room) {
  const center = planCenterCm();
  const polygon = Array.isArray(room?.polygon_cm) ? room.polygon_cm : [];
  if (!polygon.length) return null;
  const xs = polygon.map((point) => Number(point.x) - center.x);
  const zs = polygon.map((point) => Number(point.y) - center.y);
  return {
    room_bounds_cm: {
      minX: Math.min(...xs), maxX: Math.max(...xs),
      minZ: Math.min(...zs), maxZ: Math.max(...zs),
    },
    room_polygon_cm: polygon.map((point) => ({
      x: Number(point.x) - center.x,
      z: Number(point.y) - center.y,
    })),
  };
}

function upsertRoomSurfaceOverride(room, patch = {}) {
  if (!room || !state.sceneData) return null;
  const geometry = roomSurfaceBounds(room);
  if (!geometry) return null;
  const overrides = Array.isArray(state.sceneData.surface_overrides)
    ? [...state.sceneData.surface_overrides]
    : [];
  const index = overrides.findIndex((item) => String(item.room_id) === String(room.id));
  const next = {
    ...(index >= 0 ? overrides[index] : {}),
    room_id: room.id,
    room_label: room.label,
    ...geometry,
    ...patch,
  };
  if (index >= 0) overrides[index] = next;
  else overrides.push(next);
  state.sceneData.surface_overrides = overrides;
  return next;
}

function questionnaireFinishValue(draft, camelKey, snakeKey) {
  return draft?.[camelKey] || draft?.[snakeKey] || "";
}

function applyQuestionnaireSurfaceOverridesToScene() {
  if (!state.sceneData) return;
  state.rooms.forEach((room) => {
    const draft = roomFinishDraftFor(room);
    const wallMaterial = questionnaireFinishValue(draft, "wallMaterial", "wall_material");
    const floorMaterial = questionnaireFinishValue(draft, "floorMaterial", "floor_material");
    const ceilingStyle = questionnaireFinishValue(draft, "ceilingStyle", "ceiling_style");
    const lightStyle = questionnaireFinishValue(draft, "lightStyle", "light_style");
    const wallOption = wallMaterial
      ? resolveSurfaceOption(state.sceneData.surface_catalog, "wall", wallMaterial)
      : null;
    const floorOption = floorMaterial
      ? resolveSurfaceOption(state.sceneData.surface_catalog, "floor", floorMaterial)
      : null;
    if (!wallOption && !floorOption && !ceilingStyle && !lightStyle) return;
    const ceiling = CEILING_STYLES.find((item) => item.id === ceilingStyle);
    upsertRoomSurfaceOverride(room, {
      wall_option: wallOption,
      floor_option: floorOption,
      wall_material_id: wallMaterial || null,
      floor_material_id: floorMaterial || null,
      wall_color_hex: questionnaireFinishValue(draft, "wallColor", "wall_color") || wallOption?.color || null,
      floor_color_hex: questionnaireFinishValue(draft, "floorColor", "floor_color") || floorOption?.color || null,
      ceiling_style_id: ceilingStyle || null,
      ceiling_drop_cm: ceiling?.dropCm || 0,
      light_style_id: lightStyle || null,
      lighting_id: draft.lightFixtureId || draft.light_fixture_id || null,
    });
  });
}

  return {
    activateWhiteFurnitureEditing,
    activateWhiteWalkMode,
    activeCatalogSearchInput,
    addQuestionnaireCatalogFurniture,
    addSceneFurniture,
    allowedLightsForCeiling,
    allStepSixMaterialOptions,
    applyQuestionnaireSurfaceOverridesToScene,
    applyStylePackToScene,
    applySurfaceOverrides,
    cancelWhiteModelBeamPlacement,
    catalogFacetTraditionalLabel,
    ceilingStyleLabel,
    confirmStepSixRoomSurfaces,
    confirmWhiteModel,
    deactivateWhiteInteractionMode,
    deleteSelectedSceneFurniture,
    evaluateCeilingConflicts,
    firstUnconfirmedStepSixRoom,
    generateWhiteModelFromRequirements,
    glbThumbnailScene,
    loadSelectedSceneAppearance,
    materialOptionsForStyle,
    nextUnconfirmedStepSixRoom,
    openQuestionnaireFurnitureCatalog,
    populateGlbSearchThumbnails,
    previewStepSixRoomSurfaces,
    questionnaireCatalogActiveSpace,
    questionnaireCatalogBrowsePrompt,
    questionnaireCatalogGroup,
    questionnaireCatalogRoomType,
    questionnaireFinishValue,
    recommendedStepSixMaterialOptions,
    reloadWhiteViewerPreservingCamera,
    removeMaterialBoundary,
    renderGroupedMaterialOptions,
    renderQuestionnaireCatalogBatch,
    renderQuestionnaireCatalogBrowseChoices,
    renderQuestionnaireCatalogFilters,
    renderSceneObjectList,
    renderStepSixColorSwatches,
    renderStyleControls,
    renderWhiteWalkRoomSelector,
    replaceSceneFurniture,
    replaceUnlockedFurnitureForStyle,
    roomLabelAtPlanPoint,
    roomSurfaceBounds,
    saveSelectedSceneAppearance,
    sceneObjectDisplayName,
    sceneObjectTypeLabels,
    searchGlbFurniture,
    selectedWhiteWalkRoomPayload,
    setCatalogSelectOptions,
    setFurnitureCatalogOpen,
    stepSixSurfaceSelection,
    styleFurnitureCandidate,
    stylePackByIdSafe,
    SURFACE_VARIANT_OPTIONS,
    surfaceRecommendationReason,
    surfaceRecommendationScore,
    syncSurfaceMaterialSelect,
    toggleMaterialBoundary,
    unlockStepSixRoomSurfaces,
    upsertRoomSurfaceOverride,
  };
}
