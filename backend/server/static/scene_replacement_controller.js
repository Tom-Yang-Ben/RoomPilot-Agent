// Furniture replacement preview and catalog swap controller.
export function createSceneReplacementController({
  $,
  activeQuestionnairePack,
  activeQuestionnaireRoom,
  activeRoomFinishDraft,
  activeRoomRequirement,
  activeScheme,
  api,
  applianceRequirementsForRendering,
  applyVisualPreferencesToSpecs,
  buildRoomRequirementsPayload,
  CATALOG_RETRIEVAL_ROUTES,
  catalogCandidatesForType,
  catalogFurnitureOffer,
  catalogIdFromModelUrl,
  catalogItemRenderable,
  catalogMaterialOptionsForPack,
  configurationReflowInFlight,
  configurationSnapshot,
  confirmedFloorplanEditor,
  createFurniture2DItem,
  element,
  errorMessage,
  escapeHtml,
  findFurniture2DVariant,
  FURNITURE_2D_LIBRARY,
  furniture2dDefaultsForSceneObject,
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  glbThumbnailQueue,
  glbThumbnailScene,
  glbThumbnailViewer,
  goTo,
  imageContentRect,
  invalidateDownstreamFrom,
  isQuestionnaireFallbackTypeMatch,
  knownUnavailableCatalogFurnitureIds,
  loadSelectedSceneAppearance,
  mergeCatalogFurniture,
  normalizedRoomSurfaces,
  occupantsFromBasicAnswers,
  openQuestionnaireFurnitureCatalog,
  persistConfigurationState,
  planCenterCm,
  planCmToLayerPixel,
  planGeometry,
  pointInPolygonCm,
  pruneRetiredAppliances,
  QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS,
  QUESTIONNAIRE_FALLBACK_CATALOG_RULES,
  QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS,
  QUESTIONNAIRE_FURNITURE_SHORT_LABELS,
  QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES,
  QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureInFlight,
  questionnaireFurnitureRequest,
  rankCatalogFurniture,
  recommendedFurnitureForRoom,
  reconcileFurniture2dAfterGeneration,
  removeRetiredAppliancesFromFurniture,
  renderLayoutFurniture,
  renderLayoutRoomFilter,
  renderQuestionnaireRoomSections,
  renderSceneObjectList,
  replaceFurniture2DItem,
  REPLACEMENT_TYPE_LABELS,
  replacementViewer,
  resolvedVisualPreferences,
  resolveFurniturePosition,
  resolveSurfaceOption,
  ROOM_TYPE_EXCLUDED_FURNITURE_TYPES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  roomCenter,
  roomDimensions,
  roomPolygonSvg,
  roomSurfaceAssignments,
  roomUsageVisual,
  sceneDataFromGenerateResponse,
  sceneObjectIndexByFurnitureId,
  scheduleSave,
  setStatus,
  showStep,
  state,
  STYLE_PACKS,
  syncConfigurationConfirmButton,
  syncFurnitureInventoryAcrossSchemes,
  syncOverlayToImage,
  syncSelected2dFurnitureToScene,
  toSceneFurniture,
  unavailableCatalogModelUrls,
  upsertFurniture2dFromSceneObject,
  verifiedCatalogModelUrls,
  visualPreferencesForRoom,
  whiteViewer,
}) {
function replacementCandidateFitsRoom(candidate, room) {
  const dimensions = roomDimensions(room);
  const width = Number(candidate.size_cm?.width || 0);
  const depth = Number(candidate.size_cm?.depth || 0);
  if (!width || !depth) return false;
  const clearance = 20;
  return (
    width + clearance <= dimensions.widthCm
    && depth + clearance <= dimensions.depthCm
  ) || (
    depth + clearance <= dimensions.widthCm
    && width + clearance <= dimensions.depthCm
  );
}

function replacementFurnitureName(item = {}) {
  const type = item.normalized_type || item.type || "";
  const rawName = [item.name_zh, item.name_zh_raw, item.label]
    .filter(Boolean)
    .join(" ");
  const chineseNames = rawName.match(/[\u3400-\u9fff]{2,}/g) || [];
  const nameWithFurnitureNoun = chineseNames.find((name) =>
    /(床|櫃|桌|椅|凳|沙發|架|鏡|燈|毯|盆|櫥|箱|籃)/.test(name));
  return nameWithFurnitureNoun
    || questionnaireFurnitureDisplayLabel({ ...item, normalized_type: type })
    || REPLACEMENT_TYPE_LABELS[type]
    || "家具";
}

function replacementFurnitureSize(item = {}) {
  const width = Number(item.widthCm || item.size_cm?.width || 0).toFixed(0);
  const depth = Number(item.depthCm || item.size_cm?.depth || 0).toFixed(0);
  return `${width} × ${depth} cm`;
}

function replacementCandidateImageUrl(candidate = {}) {
  const cloudImages = candidate.cloud_image_urls || {};
  const previewImages = candidate.preview_images || {};
  const previewImage = Array.isArray(previewImages)
    ? previewImages.find(Boolean)
    : previewImages.front || previewImages.angle || previewImages.main;
  return candidate.image_url
    || candidate.thumbnail_url
    || candidate.preview_url
    || candidate.front_image_url
    || candidate.angle_image_url
    || candidate.main_image_url
    || candidate.primary_image_url
    || candidate.image
    || candidate.imageUrl
    || previewImage
    || cloudImages.front
    || cloudImages.angle
    || Object.values(cloudImages).find(Boolean)
    || "";
}

function replacementRoomBounds(room) {
  if (!room?.polygon_cm?.length) return null;
  const center = planCenterCm();
  const xs = room.polygon_cm.map((point) => Number(point.x || 0) - center.x);
  const zs = room.polygon_cm.map((point) => Number(point.y || 0) - center.y);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minZ: Math.min(...zs),
    maxZ: Math.max(...zs),
    centerX: (Math.min(...xs) + Math.max(...xs)) / 2,
    centerZ: (Math.min(...zs) + Math.max(...zs)) / 2,
  };
}

function segmentEndpoint(point = {}) {
  return scenePointCoordinates(point);
}

function segmentOverlapsBounds(segment, bounds, padding = 32) {
  if (!segment || !bounds) return false;
  const start = segmentEndpoint(segment.start || segment[0]);
  const end = segmentEndpoint(segment.end || segment[1]);
  const minX = Math.min(start.x, end.x);
  const maxX = Math.max(start.x, end.x);
  const minZ = Math.min(start.z, end.z);
  const maxZ = Math.max(start.z, end.z);
  return (
    maxX >= bounds.minX - padding
    && minX <= bounds.maxX + padding
    && maxZ >= bounds.minZ - padding
    && minZ <= bounds.maxZ + padding
  );
}

function shiftScenePoint(point = {}, offset) {
  if (!offset) return { ...point };
  if (Array.isArray(point)) {
    return [
      Number(point[0] || 0) - offset.x,
      Number(point[1] || 0) - offset.z,
    ];
  }
  const next = { ...point };
  if ("x" in next) next.x = Number(next.x || 0) - offset.x;
  if ("z" in next) next.z = Number(next.z || 0) - offset.z;
  if ("y" in next && !("z" in next)) next.y = Number(next.y || 0) - offset.z;
  return next;
}

function shiftSceneSegment(segment, offset) {
  if (!segment) return segment;
  if (Array.isArray(segment)) {
    return segment.map((point) => shiftScenePoint(point, offset));
  }
  const next = {
    ...segment,
    start: shiftScenePoint(segment.start, offset),
    end: shiftScenePoint(segment.end, offset),
  };
  ["swing_end", "hinge", "pivot", "center"].forEach((key) => {
    if (next[key]) next[key] = shiftScenePoint(next[key], offset);
  });
  ["confirmed_wall_opening", "wall_opening_segment", "closed_leaf_segment"].forEach((key) => {
    if (next[key]) next[key] = shiftSceneSegment(next[key], offset);
  });
  return next;
}

function shiftRoomSurfaceAssignment(assignment, offset) {
  if (!assignment || !offset) return assignment;
  const next = { ...assignment };
  if (next.room_bounds_cm) {
    next.room_bounds_cm = {
      ...next.room_bounds_cm,
      minX: Number(next.room_bounds_cm.minX || 0) - offset.x,
      maxX: Number(next.room_bounds_cm.maxX || 0) - offset.x,
      minZ: Number(next.room_bounds_cm.minZ || 0) - offset.z,
      maxZ: Number(next.room_bounds_cm.maxZ || 0) - offset.z,
    };
  }
  if (Array.isArray(next.room_polygon_cm)) {
    next.room_polygon_cm = next.room_polygon_cm.map((point) => shiftScenePoint(point, offset));
  }
  return next;
}

function scenePointCoordinates(point = {}) {
  if (Array.isArray(point)) {
    return {
      x: Number(point[0] || 0),
      z: Number(point[1] || 0),
    };
  }
  return {
    x: Number(point.x || 0),
    z: Number(point.z ?? point.y ?? 0),
  };
}

function shiftFloorplanRegion(region, offset) {
  if (!region || !offset) return region;
  const next = { ...region };
  ["exterior", "polygon_cm", "room_polygon_cm"].forEach((key) => {
    if (Array.isArray(next[key])) next[key] = next[key].map((point) => shiftScenePoint(point, offset));
  });
  if (Array.isArray(next.holes)) {
    next.holes = next.holes.map((ring) => (
      Array.isArray(ring) ? ring.map((point) => shiftScenePoint(point, offset)) : ring
    ));
  }
  return next;
}

function sceneObjectMatchesLayoutFurniture(sceneObject = {}, layoutItem = {}) {
  const sceneIds = [
    sceneObject.furniture_id,
    sceneObject.catalog_furniture_id,
    sceneObject.catalogFurnitureId,
    sceneObject.layout_furniture_id,
    sceneObject.source_furniture_id,
    sceneObject.id,
  ].filter(Boolean).map(String);
  const layoutIds = [
    layoutItem.id,
    layoutItem.catalogFurnitureId,
    layoutItem.furniture_id,
  ].filter(Boolean).map(String);
  return sceneIds.some((id) => layoutIds.includes(id));
}

function replacementRoomIdForSceneObject(sceneObject = {}) {
  const explicitRoomId = sceneObject.placement_room_id || sceneObject.room_id;
  if (explicitRoomId) return String(explicitRoomId);
  const layoutItem = state.furniture2d.find(
    (item) => sceneObjectMatchesLayoutFurniture(sceneObject, item),
  );
  return layoutItem?.roomId ? String(layoutItem.roomId) : "";
}

function buildReplacementRoomPreviewScene(baseScene, current, candidate) {
  if (!baseScene?.floorplan || !current) return null;
  const room = state.rooms.find(
    (candidateRoom) => String(candidateRoom.id) === String(current.roomId),
  );
  const bounds = replacementRoomBounds(room);
  if (!room || !bounds) return null;
  const scene = JSON.parse(JSON.stringify(baseScene));
  const floorplan = scene.floorplan || {};
  ["wall_segments", "door_segments", "window_segments", "door_openings", "beam_segments", "column_segments"].forEach((key) => {
    if (!Array.isArray(floorplan[key])) return;
    floorplan[key] = floorplan[key]
      .filter((segment) => segmentOverlapsBounds(segment, bounds));
  });
  if (Array.isArray(floorplan.room_regions)) {
    floorplan.room_regions = floorplan.room_regions.filter(
      (region) => String(region.room_id || region.id || "") === String(room.id),
    );
  }
  if (Array.isArray(floorplan.rooms)) {
    floorplan.rooms = floorplan.rooms.filter(
      (region) => String(region.room_id || region.id || "") === String(room.id),
    );
  }
  if (Array.isArray(floorplan.wall_polys)) {
    floorplan.wall_polys = floorplan.wall_polys.filter(
      (region) => (region.exterior || region.polygon_cm || []).some((point) => {
        const coordinates = scenePointCoordinates(point);
        return (
          coordinates.x >= bounds.minX - 32
          && coordinates.x <= bounds.maxX + 32
          && coordinates.z >= bounds.minZ - 32
          && coordinates.z <= bounds.maxZ + 32
        );
      }),
    );
  }
  if (Array.isArray(floorplan.columns)) {
    floorplan.columns = floorplan.columns.filter((column) => (
      segmentOverlapsBounds({ start: column.center, end: column.center }, bounds)
    ));
  }
  scene.floorplan = floorplan;
  scene.room_surface_assignments = (scene.room_surface_assignments || [])
    .filter((assignment) => String(assignment.room_id || "") === String(room.id));
  scene.surface_overrides = (scene.surface_overrides || [])
    .filter((assignment) => String(assignment.room_id || '') === String(room.id));
  const boundaryRoomId = String(
    scene.material_boundary?.roomId || scene.material_boundary?.room_id || "",
  );
  if (scene.material_boundary && boundaryRoomId && boundaryRoomId !== String(room.id)) {
    scene.material_boundary = null;
  }
  scene.scene_objects = (scene.scene_objects || [])
    .filter((item) => {
      const sameFurniture = sceneObjectMatchesLayoutFurniture(item, current);
      const sameRoom = replacementRoomIdForSceneObject(item) === String(room.id);
      return sameFurniture || sameRoom;
    })
    .map((item) => ({ ...item }));
  const currentIndex = scene.scene_objects.findIndex(
    (item) => sceneObjectMatchesLayoutFurniture(item, current),
  );
  const existing = currentIndex >= 0
    ? scene.scene_objects[currentIndex]
    : {
      position_cm: { x: Number(current.xCm || 0), z: Number(current.yCm || 0) },
      rotation_y_deg: current.rotationDeg,
      placement_room_id: current.roomId,
    };
  // The 2D layout is the source of truth after a user moves furniture.
  const layoutPosition = Number.isFinite(Number(current.xCm))
    && Number.isFinite(Number(current.yCm))
    ? { x: Number(current.xCm), z: Number(current.yCm) }
    : existing.position_cm;
  const layoutRotation = Number.isFinite(Number(current.rotationDeg))
    ? Number(current.rotationDeg)
    : existing.rotation_y_deg;
  const previewFurnitureId = `replacement-preview-${candidate.furniture_id}`;
  const replacement = {
    ...existing,
    ...candidate,
    furniture_id: previewFurnitureId,
    position_cm: layoutPosition,
    rotation_y_deg: layoutRotation,
    placement_room_id: current.roomId || existing.placement_room_id,
    position_locked: true,
    placement_failed: false,
  };
  if (currentIndex >= 0) scene.scene_objects[currentIndex] = replacement;
  else scene.scene_objects.push(replacement);
  return {
    scene,
    previewIndex: currentIndex >= 0 ? currentIndex : scene.scene_objects.length - 1,
  };
}

async function previewReplacementCandidate(candidate) {
  if (!catalogItemRenderable(candidate)) {
    element.replacement3dStatus.textContent = "這件家具沒有可載入的 3D 模型。";
    return;
  }
  const current = state.furniture2d.find(
    (item) => item.id === state.selectedFurniture2dId,
  );
  const baseScene = state.sceneData || activeScheme()?.sceneData;
  const previewFurnitureId = `replacement-preview-${candidate.furniture_id}`;
  let previewIndex = 0;
  let previewScene;
  const roomPreview = buildReplacementRoomPreviewScene(baseScene, current, candidate);
  if (roomPreview) {
    previewScene = roomPreview.scene;
    previewIndex = roomPreview.previewIndex;
  } else {
    previewScene = {
      floorplan: {
        width_cm: 360,
        depth_cm: 360,
        room_height_cm: 270,
        wall_segments: [],
        door_segments: [],
        window_segments: [],
      },
      scene_objects: [{
        ...candidate,
        furniture_id: previewFurnitureId,
        position_cm: { x: 0, z: 0 },
        rotation_y_deg: 0,
        position_locked: true,
        placement_failed: false,
      }],
      style: { style_id: state.activeStyleId || "white_model" },
    };
  }
  await replacementViewer.loadScene(previewScene);
  replacementViewer.selectObjectByIndex(previewIndex, { focus: true });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  replacementViewer.setViewMode("dollhouse");
  replacementViewer.selectObjectByIndex(previewIndex, { focus: false });
}

function renderReplacementCandidates(candidates, emptyMessage = "目前沒有可替換的家具。") {
  element.replacementResults.dataset.items = JSON.stringify(candidates);
  element.replacementResults.innerHTML = candidates.map((candidate) => {
    const title = replacementFurnitureName(candidate);
    const imageUrl = replacementCandidateImageUrl(candidate);
    return `
      <article>
        <button type="button" class="rp-replacement-candidate" data-preview-replacement="${escapeHtml(candidate.furniture_id)}">
          <span class="rp-replacement-image${imageUrl ? "" : " is-missing"}">
            ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(`${title} 家具照片`)}"
              loading="lazy" decoding="async" referrerpolicy="no-referrer" data-replacement-image />` : ""}
            <span class="rp-replacement-image-fallback">暫無圖片</span>
          </span>
          <span class="rp-replacement-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(replacementFurnitureSize(candidate))}</small></span>
        </button>
        <button type="button" class="primary-action" data-confirm-replacement="${escapeHtml(candidate.furniture_id)}">以此家具取代</button>
      </article>
    `;
  }).join("") || `<p>${escapeHtml(emptyMessage)}</p>`;
  element.replacementResults.querySelectorAll("[data-replacement-image]").forEach((image) => {
    image.addEventListener("error", () => {
      image.closest(".rp-replacement-image")?.classList.add("is-missing");
      image.remove();
    }, { once: true });
  });
  if (candidates[0]) previewReplacementCandidate(candidates[0]);
}

function replacementCandidateIsSmaller(candidate, current) {
  const candidateSides = [
    Number(candidate.size_cm?.width || 0),
    Number(candidate.size_cm?.depth || 0),
  ].sort((left, right) => left - right);
  const currentSides = [
    Number(current.widthCm || 0),
    Number(current.depthCm || 0),
  ].sort((left, right) => left - right);
  if (!candidateSides.every(Boolean) || !currentSides.every(Boolean)) return false;
  const candidateArea = candidateSides[0] * candidateSides[1];
  const currentArea = currentSides[0] * currentSides[1];
  return candidateSides[0] <= currentSides[0]
    && candidateSides[1] <= currentSides[1]
    && candidateArea <= currentArea * 0.9;
}

function setSmallerReplacementOption(smallerCandidates, { preserveCurrentSelection = false } = {}) {
  const smallerOption = element.replacementSearch.querySelector('option[value="smaller"]');
  if (smallerCandidates.length) {
    if (!smallerOption) {
      const option = document.createElement("option");
      option.value = "smaller";
      option.textContent = "建議：更換更小款";
      element.replacementSearch.insertBefore(option, element.replacementSearch.options[1] || null);
    }
    return;
  }
  if (preserveCurrentSelection && element.replacementSearch.value === "smaller") {
    return;
  }
  if (element.replacementSearch.value === "smaller") {
    element.replacementSearch.value = "same-type";
  }
  smallerOption?.remove();
}

let replacementSearchRequestVersion = 0;
let replacementQueryTimer = null;

async function loadReplacementCandidates() {
  const requestVersion = ++replacementSearchRequestVersion;
  const current = state.furniture2d.find(
    (candidate) => candidate.id === state.selectedFurniture2dId,
  );
  const room = state.rooms.find((candidate) => candidate.id === current?.roomId);
  if (!current || !room) return;
  element.replacementError.textContent = "";
  element.replacementResults.innerHTML = "<p>正在搜尋可放入目前房間的家具...</p>";
  const filterMode = element.replacementSearch.value || "same-type";
  const catalogType = filterMode.startsWith("type:") ? filterMode.slice(5) : "";
  const query = element.replacementQuery?.value?.trim() || "";
  // A text search is intentional exploration, so it must not stay trapped in
  // the type of the furniture currently being replaced. An explicitly chosen
  // category remains a narrow search.
  const queryOverridesRecommendation = Boolean(query) && !catalogType;
  const broadCatalogMode = queryOverridesRecommendation
    || filterMode === "same-style"
    || filterMode === "all";
  const paletteId = state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.paletteId;
  const style = STYLE_PACKS.find((pack) => pack.id === paletteId)?.styleId
    || state.activeStyleId
    || "";
  const request = {
    ...questionnaireFurnitureRequest(room, [current.type, current.variantId]),
    widthCm: current.widthCm,
    depthCm: current.depthCm,
  };
  // The two broad modes deliberately do not carry the current item's type
  // into ranking. Otherwise a user choosing the whole catalog would still
  // receive the old type at the top of every result list.
  const rankingRequest = broadCatalogMode
    ? { ...request, type: "", queryText: query }
    : request;
  const catalogCandidates = await catalogCandidatesForType(current.type, {
    styleId: filterMode === "all" ? "" : style,
    query,
    catalogType,
    searchAll: broadCatalogMode,
  });
  // A user may switch modes before a slower catalog request returns. Do not
  // let that older response overwrite the results for the newly selected mode.
  if (requestVersion !== replacementSearchRequestVersion) return;
  const unavailableCatalogIds = knownUnavailableCatalogFurnitureIds();
  // current.catalogFurnitureId 多半是候選槽 id，比不到真型錄 id，會讓「正在用的
  // 這一件」出現在自己的更換清單裡。GLB 檔名優先。
  const currentCatalogId = catalogIdFromModelUrl(current.model_url)
    || String(current.catalogFurnitureId || "");
  const allCandidates = rankCatalogFurniture(catalogCandidates, rankingRequest)
    .filter((candidate) => !unavailableCatalogIds.has(String(candidate.furniture_id)))
    .filter((candidate) => candidate.furniture_id !== currentCatalogId)
    .filter((candidate) => replacementCandidateFitsRoom(candidate, room));
  const smallerCandidates = allCandidates.filter((candidate) =>
    replacementCandidateIsSmaller(candidate, current),
  );
  setSmallerReplacementOption(smallerCandidates, {
    preserveCurrentSelection: filterMode === "smaller",
  });
  const effectiveFilterMode = element.replacementSearch.value || "same-type";
  if (requestVersion !== replacementSearchRequestVersion || effectiveFilterMode !== filterMode) return;
  const candidates = (effectiveFilterMode === "smaller" ? smallerCandidates : allCandidates).slice(0, 24);
  element.replacementFilterSummary.textContent =
    effectiveFilterMode === "all"
      ? "全部家具資料庫：僅顯示尺寸可放入本房的 3D 家具"
      : effectiveFilterMode === "same-style"
        ? "依本房問卷偏好與目前風格排序的資料庫家具"
      : `${replacementFurnitureName(current)} · ${replacementFurnitureSize(current)}`;
  renderReplacementCandidates(
    candidates,
    effectiveFilterMode === "smaller"
      ? "目前沒有比這件家具更小，且可放入本房的同類 3D 家具。"
      : effectiveFilterMode === "all"
        ? "目前沒有尺寸能放入此房間的 3D 家具。"
        : "目前沒有同類型、同風格且尺寸放得下的 3D 家具。",
  );
}

function renderReplacementTypeOptions(current) {
  const route = CATALOG_RETRIEVAL_ROUTES[current.type]
    || { type: current.type };
  const routeTypes = route.types || [route.type];
  const options = routeTypes.filter(Boolean);
  element.replacementSearch.innerHTML = [
    '<option value="same-type">建議：同類家具</option>',
    '<option value="same-style">依目前風格推薦</option>',
    '<option value="all">瀏覽全部家具資料庫</option>',
    ...(options.length > 1
      ? ['<option value="">瀏覽全部相容類型</option>']
      : []),
    options.length ? '<optgroup label="家具類別">' : '',
    ...options.map((type) => `<option value="type:${escapeHtml(type)}">${escapeHtml(REPLACEMENT_TYPE_LABELS[type] || current.label || type)}</option>`),
    options.length ? '</optgroup>' : '',
  ].join("");
  element.replacementSearch.value = "same-type";
  if (element.replacementQuery) element.replacementQuery.value = "";
}

function setReplacementDrawerOpen(open) {
  if (!element.replacementDrawer) return;
  if (open) {
    if (element.replacementDrawer.open) return;
    try {
      if (typeof element.replacementDrawer.showModal === "function") {
        element.replacementDrawer.showModal();
      } else {
        element.replacementDrawer.setAttribute("open", "");
      }
    } catch (error) {
      element.replacementDrawer.setAttribute("open", "");
      console.error("家具替換面板無法以 modal 開啟，已改用一般 dialog。", error);
    }
    return;
  }
  if (typeof element.replacementDrawer.close === "function") {
    element.replacementDrawer.close();
  } else {
    element.replacementDrawer.removeAttribute("open");
  }
}

async function openFurnitureReplacement({ mode = "same-type", furnitureId = state.selectedFurniture2dId } = {}) {
  if (!furnitureId) {
    element.layoutError.textContent = "請先選取一件要更換的家具。";
    return;
  }
  const current = state.furniture2d.find(
    (candidate) => String(candidate.id) === String(furnitureId),
  );
  if (!current) {
    element.layoutError.textContent = "找不到目前選取的家具，請重新選取後再更換。";
    return;
  }
  state.selectedFurniture2dId = current.id;
  try {
    renderReplacementTypeOptions(current);
    if (mode === "smaller") {
      const option = document.createElement("option");
      option.value = "smaller";
      option.textContent = "更換較小款";
      element.replacementSearch.insertBefore(option, element.replacementSearch.options[1] || null);
    }
    const requestedModeExists = Array.from(element.replacementSearch.options)
      .some((option) => option.value === mode);
    element.replacementSearch.value = requestedModeExists ? mode : "same-type";
    setReplacementDrawerOpen(true);
    await loadReplacementCandidates();
  } catch (error) {
    const message = errorMessage(error);
    element.replacementError.textContent = message;
    element.layoutError.textContent = `家具替換面板載入失敗：${message}`;
    console.error("家具替換面板載入失敗。", error);
  }
}

async function replaceSelectedLayoutFurniture(furnitureId) {
  const candidates = JSON.parse(element.replacementResults.dataset.items || "[]");
  const catalogItem = candidates.find((candidate) => candidate.furniture_id === furnitureId);
  const current = state.furniture2d.find(
    (candidate) => candidate.id === state.selectedFurniture2dId,
  );
  if (!catalogItem || !current) return;
  const size = catalogItem.size_cm || {};
  const candidate = {
    ...current,
    type: catalogItem.normalized_type || current.type,
    label: catalogItem.name_zh || catalogItem.name_zh_raw || catalogItem.name_en || current.label,
    widthCm: Number(size.width) || current.widthCm,
    depthCm: Number(size.depth) || current.depthCm,
    heightCm: Number(size.height) || current.heightCm,
    catalogFurnitureId: catalogItem.furniture_id,
    model_url: catalogItem.model_url,
    renderMode: catalogItem.render_mode || null,
    reason: `使用者從家具資料庫更換，並依「${state.rooms.find((room) => room.id === current.roomId)?.label || "目前房間"}」重新檢查位置。`,
  };
  element.replacementError.textContent = "正在由家具引擎檢查新尺寸、牆界、碰撞與淨空...";
  const resolved = await resolveFurniturePosition(candidate);
  if (!resolved || resolved.placement_failed) {
    element.replacementError.textContent =
      `無法更換：${resolved?.placement_reason || "目前房間沒有合法位置"}。`;
    return;
  }
  candidate.xCm = Number(resolved.position_cm?.x || 0);
  candidate.yCm = Number(resolved.position_cm?.z || 0);
  candidate.rotationDeg = Number(resolved.rotation_y_deg || 0);
  candidate.placementFailed = false;
  candidate.placementReason = "";
  const index = state.furniture2d.findIndex((item) => item.id === current.id);
  state.furniture2d[index] = candidate;
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "家具款式已更換，3D 家具配置與第 6 步預覽需要重新產生。");
  scheduleSave("layout_2d");
  setReplacementDrawerOpen(false);
  setStatus(`已用「${candidate.label}」取代原家具，並通過家具引擎檢查。`);
}

function addFurnitureFromLibrary(type, variant) {
  const currentIndex = state.furniture2d.findIndex(
    (item) => item.id === state.selectedFurniture2dId,
  );
  if (currentIndex >= 0) {
    state.furniture2d[currentIndex] = replaceFurniture2DItem(
      state.furniture2d[currentIndex],
      type,
      variant,
    );
    syncFurnitureInventoryAcrossSchemes();
    renderLayoutFurniture();
    invalidateDownstreamFrom("layout_2d", "2D 家具形式已修改，3D 家具配置與第 6 步預覽需要重新產生。");
    scheduleSave("layout_2d");
    setStatus("已保留原位置並更換家具形式；請確認新尺寸與淨空。");
    return;
  }
  const room = state.rooms.find((item) => item.id === state.activeLayoutRoomId)
    || state.rooms.find((item) => item.id === state.selectedRoomId)
    || state.rooms[0];
  const center = roomCenter(room);
  const planCenter = planCenterCm();
  const item = createFurniture2DItem(type, variant, {
    xCm: center.x - planCenter.x,
    yCm: center.y - planCenter.y,
  });
  item.roomId = room.id;
  item.reason = "使用者從 2D 圖示資料庫加入。";
  state.furniture2d.push(item);
  syncFurnitureInventoryAcrossSchemes();
  state.selectedFurniture2dId = item.id;
  state.activeLayoutRoomId = room.id;
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具已新增，3D 家具配置與第 6 步預覽需要重新產生。");
  scheduleSave("layout_2d");
}

function updateSelectedFurnitureDimensions() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
  if (!item) return;
  item.widthCm = Math.max(1, Number(element.selectedFurnitureWidth.value) || item.widthCm);
  item.depthCm = Math.max(1, Number(element.selectedFurnitureDepth.value) || item.depthCm);
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具尺寸已修改，3D 家具配置與第 6 步預覽需要重新產生。");
  scheduleSave("layout_2d");
}

async function resolveCatalogFurniture(item) {
  // Locked items stay put while the engine validates the configuration.
  const positionLocked = item.locked === true;
  if (catalogItemRenderable(item) && item.catalogFurnitureId) {
    return {
      ...toSceneFurniture(item),
      position_locked: positionLocked,
    };
  }
  try {
    const room = state.rooms.find((candidate) => candidate.id === item.roomId);
    const request = questionnaireFurnitureRequest(
      room || { id: item.roomId },
      [item.type, item.variantId],
    );
    const params = new URLSearchParams({
      type: item.type,
      has_model: "true",
      detail: "scene",
      page_size: "80",
    });
    if (request.styleId) params.set("style", request.styleId);
    let payload = await api(`/api/furniture?${params.toString()}`);
    if (!(payload.items || []).length && request.styleId) {
      params.delete("style");
      payload = await api(`/api/furniture?${params.toString()}`);
    }
    const candidates = rankCatalogFurniture(payload.items || [], request);
    if (!candidates.length) {
      return {
        ...toSceneFurniture(item),
        position_locked: positionLocked,
      };
    }
    return {
      ...mergeCatalogFurniture(item, candidates[0]),
      position_locked: positionLocked,
    };
  } catch (error) {
    console.warn(error);
    return {
      ...toSceneFurniture(item),
      position_locked: positionLocked,
    };
  }
}

function placementResolutionText(report = []) {
  if (!report.length) return "";
  const replaced = report.filter((item) => item.action === "replace").length;
  const removed = report.filter((item) => item.action === "remove").length;
  const needsAttention = report.length - replaced - removed;
  const changes = [
    replaced ? `替換 ${replaced} 件` : "",
    removed ? `移除 ${removed} 件` : "",
  ].filter(Boolean);
  const summary = changes.length
    ? `系統已依空間尺寸調整家具：${changes.join("、")}`
    : "系統已完成家具配置檢查";
  return needsAttention > 0
    ? `${summary}；另有 ${needsAttention} 件需要手動處理，請查看待處理清單。`
    : `${summary}；目前配置已通過檢查。`;
}

async function confirmLayout2d({ allowPendingFurniture = false } = {}) {
  element.layoutError.textContent = "";
  let generationStage = "檢查家具位置";
  try {
    if (state.furniture2d.length) {
      const validation = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          scene_objects: state.furniture2d.map((item) => toSceneFurniture(item)),
        }),
      });
      const invalid = (validation.scene_objects || []).filter(
        (item) => item.placement_failed || !item.position_locked,
      );
      if (invalid.length && !allowPendingFurniture) {
        element.layoutError.textContent = `${invalid
          .map((item) => item.name_zh_raw || item.normalized_type)
          .join("、")}目前位置未通過碰撞、淨空或房間邊界檢查，請移動或更換尺寸。`;
        return false;
      }
    }
    generationStage = "取得資料庫家具模型";
    setStatus(state.furniture2d.length
      ? "正在依問卷、色卡與尺寸載入資料庫 GLB 家具…"
      : "沒有家具需求，正在產生純結構 3D 配置…");
    const applianceRequirements = applianceRequirementsForRendering(state.furniture2d);
    const placeableFurniture = removeRetiredAppliancesFromFurniture(state.furniture2d);
    const selectedFurniture = await Promise.all(
      placeableFurniture.map((item) => resolveCatalogFurniture(item)),
    );
    const missingCatalogModels = selectedFurniture.filter((item) => !catalogItemRenderable(item));
    if (missingCatalogModels.length && !allowPendingFurniture) {
      element.layoutError.textContent =
        `有 ${missingCatalogModels.length} 件家具尚未找到可用的資料庫 GLB：${
          missingCatalogModels
            .map((item) => item.name_zh_raw || item.normalized_type)
            .join("、")
        }。請更換家具或確認型錄模型後再進入配置預覽。`;
      setStatus("資料庫家具尚未完整，已停止產生替代模型。", "error");
      return false;
    }
    if (missingCatalogModels.length) {
      const missingIds = new Set(missingCatalogModels.map((item) => String(item.id)));
      state.furniture2d = state.furniture2d.map((item) => (
        missingIds.has(String(item.id))
          ? {
            ...item,
            placementFailed: true,
            placementReason: "尚未找到可用的資料庫 GLB，請替換為可載入的家具。",
          }
          : item
      ));
    }
    const sceneFurniture = allowPendingFurniture
      ? selectedFurniture.filter(catalogItemRenderable)
      : selectedFurniture;
    const firstRoom = state.rooms.find((room) => room.type === "living_room") || state.rooms[0];
    const dimensions = roomDimensions(firstRoom);
    const preferredPack = activeQuestionnairePack();
    const visualPreferences = resolvedVisualPreferences();
    const roomRequirementsPayload = buildRoomRequirementsPayload(
      state.roomRequirementModel,
      {
        planGeometry: {
          rooms: state.rooms,
          structures: state.structures,
        },
        questionnaireVersion: state.visualCatalogVersion,
      },
    );
    const roomSurfaces = roomSurfaceAssignments();
    generationStage = "產生 2D+3D 場景";
    const payload = await api("/api/scene/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_brief: {
          space: { type: firstRoom.type || "living_room" },
          style: {
            preferred: [preferredPack.styleId],
            colors: [
              state.questionnaireFinishes.wallColor,
              state.questionnaireFinishes.floorColor,
              state.questionnaireFinishes.ceilingColor,
            ].filter(Boolean),
            materials: [
              state.questionnaireFinishes.wallMaterial,
              state.questionnaireFinishes.floorMaterial,
              state.questionnaireFinishes.ceilingMaterial,
            ].filter(Boolean),
          },
          occupants: occupantsFromBasicAnswers(state.basicAnswers),
          constraints: ["keep_door_clear", "keep_window_clear"],
        },
        questionnaire: {
          catalog_version: state.visualCatalogVersion,
          basic: state.basicAnswers,
          visual_preferences: visualPreferences,
          finishes: state.questionnaireFinishes,
          room_requirements: roomRequirementsPayload.roomRequirements,
          rag_jobs: state.roomRagJobs,
          appliance_requirements: applianceRequirements,
        },
        room_surface_assignments: roomSurfaces,
        floorplan_filename: `${state.projectId}-confirmed.dxf`,
        floorplan_editor: confirmedFloorplanEditor(),
        room_width_cm: dimensions.widthCm,
        room_depth_cm: dimensions.depthCm,
        required_furniture: [...new Set(placeableFurniture.map((item) => item.type))],
        selected_furniture: sceneFurniture,
        // When a selected item has no GLB, omit only that item from generation and
        // surface it in step 6. The generator must never add furniture the user did not select.
        selected_furniture_exact: allowPendingFurniture,
      }),
    });
    state.sceneData = sceneDataFromGenerateResponse(payload);
    pruneRetiredAppliances({ notify: true });
    const generatedInvalid = (state.sceneData.scene_objects || []).filter(
      (item) => item.placement_failed || !item.position_cm,
    );
    if (generatedInvalid.length && !allowPendingFurniture) {
      element.layoutError.textContent =
        `系統仍有 ${generatedInvalid.length} 件家具無法合法放置，請先在上方待處理清單更換或調整家具。`;
      setStatus("配置尚未通過門窗淨空、房間邊界與家具碰撞檢查。", "error");
      renderLayoutRoomFilter();
      renderLayoutFurniture();
      return false;
    }
    state.sceneData.questionnaire = {
      catalog_version: state.visualCatalogVersion,
      basic: state.basicAnswers,
      visual_preferences: visualPreferences,
      finishes: state.questionnaireFinishes,
      room_requirements: roomRequirementsPayload.roomRequirements,
      rag_jobs: state.roomRagJobs,
      appliance_requirements: applianceRequirements,
    };
    state.sceneData.room_requirements = roomRequirementsPayload.roomRequirements;
    state.sceneData.surface_overrides = roomSurfaces.map((surface) => ({
      ...surface,
      wall_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "wall",
        surface.wall_material_id,
      ),
      floor_option: resolveSurfaceOption(
        state.sceneData.surface_catalog,
        "floor",
        surface.floor_material_id,
      ),
    }));
    state.sceneData.style = {
      ...(state.sceneData.style || {}),
      style_id: "white_model",
      palette_hex: ["#f4f1ec", "#e9e6e1", "#d8d3cc", "#bcb4aa"],
    };
    state.furniture2d = reconcileFurniture2dAfterGeneration(
      state.furniture2d,
      sceneFurniture,
      state.sceneData.scene_objects,
      furniture2dDefaultsForSceneObject,
    );
    const selectedSceneIndex = sceneObjectIndexByFurnitureId(state.selectedFurniture2dId);
    if (selectedSceneIndex >= 0) state.selectedSceneIndex = selectedSceneIndex;
    const generatedScheme = activeScheme();
    generatedScheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
    generatedScheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
    generatedScheme.stale = false;
    generatedScheme.staleReason = "";
    state.workflow.complete("layout_2d", {
      confirmed: true,
      furnitureCount: state.furniture2d.length,
    });
    state.workflow.goTo("white_model_3d");
    showStep("white_model_3d");
    generationStage = "載入 3D 預覽";
    await whiteViewer.loadScene(state.sceneData);
    whiteViewer.setViewMode("orbit");
    renderSceneObjectList();
    loadSelectedSceneAppearance();
    syncSelected2dFurnitureToScene({ focus: true });
    const diagnostics = whiteViewer.getDiagnostics();
    const expectedFurnitureCount = state.sceneData.scene_objects.filter(
      (item) => !item.placement_failed,
    ).length;
    const resolutionText = placementResolutionText(state.sceneData.placement_resolution_report || []);
    if (expectedFurnitureCount === 0) {
      element.whiteError.textContent = "";
      setStatus("純結構 3D 配置已產生；此方案沒有家具需求。");
    } else if (diagnostics.visibleFurnitureCount > 0) {
      element.whiteError.textContent = resolutionText;
      setStatus(`3D 家具配置已產生，${diagnostics.visibleFurnitureCount} 件資料庫家具可見。`);
    } else {
      element.whiteError.textContent = "3D 中沒有任何可見家具，不能進入下一步。";
    }
    scheduleSave("white_model_3d");
    return true;
  } catch (error) {
    const message = `${generationStage}失敗：${errorMessage(error)}`;
    state.lastWhiteModelGenerationError = message;
    element.layoutError.textContent = message;
    console.error("2D+3D configuration failed", { generationStage, error });
    setStatus(message, "error");
    return false;
  }
}

  return {
    addFurnitureFromLibrary,
    buildReplacementRoomPreviewScene,
    confirmLayout2d,
    loadReplacementCandidates,
    openFurnitureReplacement,
    placementResolutionText,
    previewReplacementCandidate,
    renderReplacementCandidates,
    renderReplacementTypeOptions,
    replacementCandidateFitsRoom,
    replacementCandidateImageUrl,
    replacementCandidateIsSmaller,
    replacementFurnitureName,
    replacementFurnitureSize,
    replacementRoomBounds,
    replacementRoomIdForSceneObject,
    replaceSelectedLayoutFurniture,
    resolveCatalogFurniture,
    sceneObjectMatchesLayoutFurniture,
    scenePointCoordinates,
    segmentEndpoint,
    segmentOverlapsBounds,
    setReplacementDrawerOpen,
    setSmallerReplacementOption,
    shiftFloorplanRegion,
    shiftRoomSurfaceAssignment,
    shiftScenePoint,
    shiftSceneSegment,
    updateSelectedFurnitureDimensions,
  };
}
