// Step 6 layout, validation, and configuration workspace controller.
export function createSceneLayoutController({
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
  catalogFurnitureOffer,
  catalogItemRenderable,
  catalogMaterialOptionsForPack,
  catalogOffersForRoomPlans,
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
  questionnaireFurnitureProgram,
  questionnaireFurnitureSelectionItem,
  rankCatalogFurniture,
  recommendedFurnitureForRoom,
  reconcileFurniture2dAfterGeneration,
  removeRetiredAppliancesFromFurniture,
  renderQuestionnaireRoomSections,
  renderSceneObjectList,
  replaceFurniture2DItem,
  REPLACEMENT_TYPE_LABELS,
  replacementCandidateImageUrl,
  replacementViewer,
  resolvedVisualPreferences,
  resolveSurfaceOption,
  ROOM_TYPE_EXCLUDED_FURNITURE_TYPES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  roomDimensions,
  roomFurnitureRequirement,
  roomPolygonSvg,
  roomSurfaceAssignments,
  roomUsageVisual,
  sceneDataFromGenerateResponse,
  sceneObjectIndexByFurnitureId,
  scenePositionInsideRoom,
  scheduleSave,
  setStatus,
  showStep,
  specsAllowedByRoomFeasibility,
  specsFromSelectionResponse,
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
async function autoLayoutFurniture() {
  state.furniture2d = [];
  const roomPlans = state.rooms.map((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const selectedCatalogFurniture = requirement?.furniture?.selected || [];
    const userSelectedSpecs = selectedCatalogFurniture.flatMap((item) => {
      const count = Math.max(1, Math.min(6, Number(item.count) || 1));
      return Array.from({ length: count }, () => [
        item.normalized_type,
        item.variant_id || "standard",
        item.reason || "使用者於逐房問卷勾選",
        false,
        item,
      ]);
    });
    const requestedSpecs = userSelectedSpecs.length
      ? userSelectedSpecs
      : requirement?.furniture?.catalog_only
        ? []
        : recommendedFurnitureForRoom(room);
    const visualPreferences = visualPreferencesForRoom(room);
    const preferredSpecs = userSelectedSpecs.length
      ? requestedSpecs
      : applyVisualPreferencesToSpecs(requestedSpecs, visualPreferences);
    const specs = specsAllowedByRoomFeasibility(
      requirement,
      preferredSpecs,
    );
    const placementPreferences = Object.assign(
      {},
      ...visualPreferences.map((preference) => preference.engine_effects),
    );
    return {
      room,
      specs,
      userSelectedSpecs,
      visualPreferences,
      placementPreferences,
    };
  });
  const requirementsPayload = buildRoomRequirementsPayload(
    state.roomRequirementModel,
    {
      planGeometry: confirmedFloorplanEditor(),
      questionnaireVersion: state.visualCatalogVersion,
    },
  );
  let selection = null;
  try {
    const catalogOffers = await catalogOffersForRoomPlans(roomPlans);
    selection = await api("/api/agent/furniture/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rooms: roomPlans.map(({ room }) => ({
          room_id: room.id,
          room_type: room.type,
          label: room.label,
        })),
        offers: catalogOffers,
        style_id: state.activeStyleId,
        context: {
          questionnaire: requirementsPayload,
          basic_answers: state.basicAnswers,
          room_requirements: state.roomRequirementModel.roomRequirements,
          room_surface_assignments: roomSurfaceAssignments(),
          visual_preferences: Object.fromEntries(roomPlans.map(({ room, visualPreferences }) => [
            room.id,
            visualPreferences,
          ])),
        },
      }),
    });
  } catch (error) {
    console.warn("Furniture selection fallback", error);
  }
  for (const { room, specs, placementPreferences } of roomPlans) {
    // The questionnaire owns the requested type and quantity. RAG may only
    // substitute a catalog model for the same requested entry.
    const selectedSpecs = specsAllowedByRoomFeasibility(
      state.roomRequirementModel.roomRequirements[room.id],
      selection ? specsFromSelectionResponse(room, selection, specs) : specs,
    );
    const roomItems = [];
    selectedSpecs.forEach(([type, variant, reason, autoAdded, catalogItem], index) => {
      try {
        const catalogSize = catalogItem?.size_cm || {};
        const item = createFurniture2DItem(type, variant, {
          id: `${room.id}-${type}-${index + 1}`,
          roomId: room.id,
          userRequired: catalogItem?.user_selected === true,
          widthCm: catalogSize.width,
          depthCm: catalogSize.depth,
          heightCm: catalogSize.height,
        });
        item.roomId = room.id;
        if (catalogItemRenderable(catalogItem)) {
          item.label = catalogItem.name_zh
            || catalogItem.name_zh_raw
            || catalogItem.name_en
            || item.label;
          item.catalogFurnitureId = catalogItem.furniture_id;
          item.model_url = catalogItem.model_url;
          item.renderMode = catalogItem.render_mode || null;
          item.primaryStyle = catalogItem.primary_style || null;
          item.catalogColor = catalogItem.color || null;
          item.catalogMaterial = catalogItem.material || null;
          item.selectionSource =
            catalogItem.selection_source || "questionnaire_catalog_rag";
          item.catalogMatchReason =
            catalogItem.reason || catalogItem.match_reason || reason || "";
          item.questionnaireMatchScore =
            Number(catalogItem.questionnaire_match_score) || 0;
          item.selectionPriority =
            Number(catalogItem.selection_priority) || index + 1;
        }
        item.reason = reason
          || `依「${room.label}」的使用需求與可用空間先配置，可再調整。`;
        item.autoAdded = autoAdded === true;
        roomItems.push(item);
      } catch (error) {
        console.warn(error);
      }
    });
    if (!roomItems.length) continue;
    let layout;
    try {
      layout = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          placement_room_id: room.id,
          placement_preferences: placementPreferences,
          scene_objects: roomItems.map((item) =>
            toSceneFurniture(item, { positionLocked: false })
          ),
        }),
      });
    } catch (error) {
      // A single room can be retried from step 6; it must not block the whole house.
      console.warn("Room furniture layout deferred", room.id, error);
      roomItems.forEach((item) => {
        item.placementFailed = true;
        item.placementReason = errorMessage(error);
        state.furniture2d.push(item);
      });
      continue;
    }
    const placedById = new Map(
      (layout.scene_objects || []).map((item) => [item.furniture_id, item]),
    );
    roomItems.forEach((item) => {
      const placed = placedById.get(item.id);
      if (!placed) return;
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      state.furniture2d.push(item);
    });
  }
  state.selectedFurniture2dId = state.furniture2d[0]?.id || null;
  const scheme = activeScheme();
  scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
  scheme.stale = false;
  scheme.staleReason = "";
  state.activeLayoutRoomId = "all";
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  scheduleSave("layout_2d");
}

async function relayoutFurnitureForRooms(sourceFurniture, {
  roomIds = null,
  movableFurnitureIds = null,
} = {}) {
  const placedFurniture = [];
  const selectedRooms = roomIds
    ? new Set([...roomIds].map(String))
    : null;
  const movableIds = movableFurnitureIds
    ? new Set([...movableFurnitureIds].map(String))
    : null;
  for (const room of state.rooms) {
    if (selectedRooms && !selectedRooms.has(String(room.id))) continue;
    const roomItems = sourceFurniture
      .filter((item) => String(item.roomId) === String(room.id))
      .map((item) => ({
        ...JSON.parse(JSON.stringify(item)),
        placementFailed: false,
        placementReason: "",
      }));
    if (!roomItems.length) continue;
    const layout = await api("/api/scene/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        floorplan_editor: confirmedFloorplanEditor(),
        placement_room_id: room.id,
        scene_objects: roomItems.map((item) =>
          toSceneFurniture(item, {
            positionLocked: movableIds ? !movableIds.has(String(item.id)) : false,
          })
        ),
      }),
    });
    const placedById = new Map(
      (layout.scene_objects || []).map((item) => [item.furniture_id, item]),
    );
    roomItems.forEach((item) => {
      const placed = placedById.get(item.id);
      if (!placed) return;
      item.xCm = Number(placed.position_cm?.x || 0);
      item.yCm = Number(placed.position_cm?.z || 0);
      item.rotationDeg = Number(placed.rotation_y_deg || 0);
      item.placementFailed = placed.placement_failed === true;
      item.placementReason = placed.placement_reason || "";
      placedFurniture.push(item);
    });
  }
  // 手動修復維持嚴格 null-on-failure，呼叫端依賴此訊號拒絕不完整結果。
  return placedFurniture.some((item) => item.placementFailed) ? null : placedFurniture;
}

function misplacedAssignedRoomFurniture() {
  return state.furniture2d.filter((item) => {
    const sceneIndex = sceneObjectIndexByFurnitureId(item.id);
    const sceneObject = sceneIndex >= 0
      ? state.sceneData.scene_objects[sceneIndex]
      : null;
    if (!item.roomId) return false;
    const itemPosition = { x: item.xCm, z: item.yCm };
    const scenePosition = sceneObject?.position_cm;
    return !scenePositionInsideRoom(itemPosition, item.roomId)
      || (scenePosition && !scenePositionInsideRoom(scenePosition, item.roomId))
      || (
        sceneObject?.placement_room_id
        && String(sceneObject.placement_room_id) !== String(item.roomId)
      );
  });
}

async function repairFurnitureRoomPlacements() {
  if (!state.sceneData?.scene_objects?.length) return 0;
  const misplaced = misplacedAssignedRoomFurniture();
  if (!misplaced.length) return 0;
  const affectedRoomIds = new Set(misplaced.map((item) => String(item.roomId)));
  const misplacedIds = new Set(misplaced.map((item) => String(item.id)));
  const affectedFurniture = state.furniture2d.filter(
    (item) => affectedRoomIds.has(String(item.roomId)),
  );
  const repairedFurniture = await relayoutFurnitureForRooms(
    affectedFurniture,
    { roomIds: affectedRoomIds, movableFurnitureIds: misplacedIds },
  );
  if (!repairedFurniture) {
    throw new Error("家具無法依指定房間重新配置，請在第 6 步逐房調整。");
  }
  if (repairedFurniture.length !== affectedFurniture.length) {
    throw new Error("部分家具缺少有效房間，已保留原配置供使用者確認。");
  }

  const repairedById = new Map(
    repairedFurniture.map((item) => [String(item.id), item]),
  );
  const repairedBySceneIndex = new Map();
  repairedFurniture.forEach((item) => {
    const sceneIndex = sceneObjectIndexByFurnitureId(item.id);
    if (sceneIndex >= 0) repairedBySceneIndex.set(sceneIndex, item);
  });
  state.furniture2d = state.furniture2d.map(
    (item) => repairedById.get(String(item.id)) || item,
  );
  if (state.sceneData?.scene_objects) {
    state.sceneData.scene_objects = state.sceneData.scene_objects.map((sceneObject, index) => {
      const item = repairedBySceneIndex.get(index);
      if (!item) return sceneObject;
      return {
        ...sceneObject,
        position_cm: {
          ...(sceneObject.position_cm || {}),
          x: item.xCm,
          z: item.yCm,
        },
        rotation_y_deg: item.rotationDeg,
        placement_room_id: item.roomId,
        position_locked: true,
        placement_failed: false,
        placement_reason: "",
      };
    });
  }
  persistConfigurationState(state.configurationState, {
    furniture: state.furniture2d,
    sceneData: state.sceneData,
  });
  if (state.configurationState.configuration_snapshot) {
    state.configurationState.configuration_snapshot = configurationSnapshot();
  }
  return misplaced.length;
}

function renderLayoutRoomFilter() {
  if (!element.layoutRoomFilter) return;
  const roomsWithFurniture = new Set(state.furniture2d.map((item) => item.roomId));
  const roomOptions = state.rooms
    .filter((room) => roomsWithFurniture.has(room.id))
    .map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`)
    .join("");
  element.layoutRoomFilter.innerHTML = `<option value="all">全屋</option>${roomOptions}`;
  if (
    state.activeLayoutRoomId !== "all"
    && !state.rooms.some((room) => room.id === state.activeLayoutRoomId)
  ) {
    state.activeLayoutRoomId = "all";
  }
  element.layoutRoomFilter.value = state.activeLayoutRoomId || "all";
  renderLayoutRoomMaterials();
}

function renderLayoutRoomMaterials() {
  if (!element.layoutRoomMaterials) return;
  const rooms = state.activeLayoutRoomId === "all"
    ? state.rooms
    : state.rooms.filter((room) => room.id === state.activeLayoutRoomId);
  element.layoutRoomMaterials.innerHTML = rooms.map((room) => {
    const rawSurfaces = state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces;
    if (!rawSurfaces) return "";
    const surfaces = normalizedRoomSurfaces(room, rawSurfaces || {});
    return `
      <span class="rp-layout-room-material">
        <strong>${escapeHtml(room.label)}</strong>
        <i style="--surface-swatch:${escapeHtml(surfaces.wallDefault?.color || "#f2f0ec")}"></i>
        <small>牆 ${escapeHtml(surfaces.wallDefault?.materialId || "未設定")}</small>
        <i style="--surface-swatch:${escapeHtml(surfaces.floor?.color || "#b99b78")}"></i>
        <small>地 ${escapeHtml(surfaces.floor?.materialId || "未設定")}</small>
      </span>
    `;
  }).join("");
  renderLayoutSurfaceOverlay(rooms);
}

function materialPreviewForLayout(kind, materialId) {
  return catalogMaterialOptionsForPack(kind, activeQuestionnairePack())
    .find((option) => option.id === materialId)?.materialPreview || "";
}

function renderLayoutSurfaceOverlay(rooms) {
  if (!element.layoutRoomOverlay || !element.layoutImage?.naturalWidth) return;
  syncOverlayToImage(element.layoutStage, element.layoutImage, element.layoutRoomOverlay);
  const patterns = rooms.map((room, index) => {
    const surfaces = normalizedRoomSurfaces(
      room,
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {},
    );
    const preview = materialPreviewForLayout("floor", surfaces.floor?.materialId);
    if (!preview) return "";
    const patternId = `layout-floor-${index}`;
    return `<pattern id="${patternId}" width="100" height="100" patternUnits="userSpaceOnUse">
      <image href="${escapeHtml(preview)}" width="100" height="100" preserveAspectRatio="xMidYMid slice"/>
    </pattern>`;
  }).join("");
  const polygons = rooms.map((room, index) => {
    const surfaces = normalizedRoomSurfaces(
      room,
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {},
    );
    const preview = materialPreviewForLayout("floor", surfaces.floor?.materialId);
    if (!preview) return "";
    return `<polygon points="${roomPolygonSvg(room)}" fill="url(#layout-floor-${index})"
      fill-opacity="0.28" pointer-events="none"/>`;
  }).join("");
  element.layoutRoomOverlay.innerHTML = patterns ? `<defs>${patterns}</defs>${polygons}` : "";
}

function renderFurnitureLibrary(filterText = "") {
  const term = filterText.trim().toLowerCase();
  const variants = FURNITURE_2D_LIBRARY.flatMap((category) =>
    category.variants.map((variant) => ({ category, variant }))
  ).filter(({ category, variant }) =>
    !term || `${category.label}${variant.label}${category.type}`.toLowerCase().includes(term)
  );
  element.furnitureLibrary.innerHTML = variants.map(({ category, variant }) => `
    <button type="button" data-add-furniture-type="${escapeHtml(category.type)}" data-add-furniture-variant="${escapeHtml(variant.id)}">
      <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(variant.iconPath)}"/></svg>
      <strong>${escapeHtml(variant.label)}</strong>
      <small>${variant.widthCm} × ${variant.depthCm} cm</small>
    </button>
  `).join("");
}

function furniturePixelPosition(item) {
  const center = planCenterCm();
  return planCmToLayerPixel(
    {
      x: center.x + item.xCm,
      y: center.y + item.yCm,
    },
    planGeometry(),
    layoutPixelsPerCm(),
  );
}

function layoutPixelsPerCm() {
  const imageRect = imageContentRect(element.layoutImage);
  const naturalRatio = imageRect.width / Math.max(element.layoutImage.naturalWidth, 1);
  return (1 / planGeometry().scale) * naturalRatio;
}

function itemCollision(item) {
  const room = state.rooms.find((candidate) => candidate.id === item.roomId);
  if (!room) return true;
  const center = planCenterCm();
  const x = center.x + item.xCm;
  const y = center.y + item.yCm;
  const xs = room.polygon_cm.map((point) => point.x);
  const ys = room.polygon_cm.map((point) => point.y);
  const footprint = furnitureCollisionFootprintCm(item);
  const halfWidth = footprint.width / 2;
  const halfDepth = footprint.depth / 2;
  if (
    x - halfWidth < Math.min(...xs)
    || x + halfWidth > Math.max(...xs)
    || y - halfDepth < Math.min(...ys)
    || y + halfDepth > Math.max(...ys)
  ) return true;
  return state.furniture2d.some((other) => {
    if (other.id === item.id || other.roomId !== item.roomId) return false;
    const otherFootprint = furnitureCollisionFootprintCm(other);
    return Math.abs(other.xCm - item.xCm) < (otherFootprint.width + footprint.width) / 2
      && Math.abs(other.yCm - item.yCm) < (otherFootprint.depth + footprint.depth) / 2;
  });
}

function hasAuthoritativeScenePlacement(item, sceneObject) {
  if (!sceneObject || sceneObject.placement_failed === true) return false;
  const position = sceneObject.position_cm || {};
  const sameCoordinate = Math.abs(Number(position.x) - Number(item.xCm)) < 0.25
    && Math.abs(Number(position.z) - Number(item.yCm)) < 0.25;
  const sceneRotation = ((Number(sceneObject.rotation_y_deg) % 360) + 360) % 360;
  const itemRotation = ((Number(item.rotationDeg) % 360) + 360) % 360;
  const sameRotation = Math.min(
    Math.abs(sceneRotation - itemRotation),
    360 - Math.abs(sceneRotation - itemRotation),
  ) < 0.25;
  const roomId = sceneObject.placement_room_id;
  return sameCoordinate
    && sameRotation
    && String(roomId) === String(item.roomId);
}

function furniturePlacementInvalid(item, sceneObject) {
  if (item.placementFailed === true || sceneObject?.placement_failed === true) {
    return true;
  }
  // The server validates actual 3D geometry. Do not override a synchronized
  // server result with the 2D rectangle approximation.
  return !hasAuthoritativeScenePlacement(item, sceneObject) && itemCollision(item);
}

function renderLayoutFurniture() {
  if (!element.layoutImage.naturalWidth) return;
  const scale = layoutPixelsPerCm();
  const visibleFurniture = state.activeLayoutRoomId === "all"
    ? state.furniture2d
    : state.furniture2d.filter((item) => item.roomId === state.activeLayoutRoomId);
  if (
    state.selectedFurniture2dId
    && !visibleFurniture.some((item) => item.id === state.selectedFurniture2dId)
  ) {
    state.selectedFurniture2dId = visibleFurniture[0]?.id || null;
  }
  const sceneById = new Map(
    (state.sceneData?.scene_objects || []).map((item) => [String(item.furniture_id), item]),
  );
  element.layoutLayer.innerHTML = visibleFurniture.map((item) => {
    const pixel = furniturePixelPosition(item);
    const style = furnitureFootprintStyle(item, scale);
    const invalid = furniturePlacementInvalid(item, sceneById.get(String(item.id)));
    item.invalid = invalid;
    return `
      <button type="button" class="rp-2d-furniture ${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${invalid ? "is-invalid" : ""}"
        data-furniture-2d-id="${escapeHtml(item.id)}"
        style="left:${pixel.x}px;top:${pixel.y}px;width:${style.width};height:${style.height};transform:${style.transform}">
        <svg viewBox="0 0 48 48" aria-hidden="true"><path d="${escapeHtml(item.iconPath)}"/></svg>
        <span>${escapeHtml(item.label)}<br>${item.widthCm} × ${item.depthCm} cm</span>
      </button>
    `;
  }).join("");
  element.layoutFurnitureList.innerHTML = visibleFurniture.map((item) => `
    <button type="button"
      class="${item.id === state.selectedFurniture2dId ? "is-active" : ""}"
      data-select-layout-furniture="${escapeHtml(item.id)}">
      <span><strong>${escapeHtml(item.label)}</strong><small>${item.widthCm} × ${item.depthCm} cm</small></span>
      <span class="rp-model-state">${item.catalogFurnitureId || item.model_url ? "GLB" : "圖示"}</span>
      <span aria-hidden="true">›</span>
    </button>
  `).join("");
  renderSelectedFurnitureEditor();
}

function configurationBlockingFurniture() {
  const deferredIds = configurationDeferredFurnitureIds();
  const sceneById = new Map(
    (state.sceneData?.scene_objects || []).map((item) => [String(item.furniture_id), item]),
  );
  const modelFailureIds = new Set(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => String(item.id))
      : [],
  );
  return state.furniture2d.filter((item) => {
    if (deferredIds.has(String(item.id))) return false;
    const sceneObject = sceneById.get(String(item.id));
    return furniturePlacementInvalid(item, sceneObject)
      || modelFailureIds.has(String(item.id));
  });
}

function configurationDeferredFurnitureIds() {
  const deferred = state.rooms.flatMap((room) =>
    state.roomRequirementModel.roomRequirements[room.id]?.furniture?.deferred || [],
  );
  return new Set([
    ...deferred,
    ...(state.roomRequirementModel.unassignedDeferredFurniture || []),
  ].map((item) => String(item.id)));
}

const GENERATIVE_EQUIPMENT_OPTIONS = Object.freeze({
  kitchen: {
    primary: [["cook", "日常烹飪"], ["light_meals", "輕食備餐"], ["storage", "收納為主"]],
    directions: [["base_cabinet", "基本櫥櫃"], ["tall_pantry", "高櫃／食品儲藏"], ["island", "中島或吧台"], ["dishwasher", "洗碗設備"]],
    exclusions: [["island", "不要中島"], ["open_shelves", "不要開放層架"]],
  },
  bathroom: {
    primary: [["shower", "淋浴為主"], ["bathe", "希望浴缸"], ["storage", "收納為主"]],
    directions: [["walk_in_shower", "乾濕分離淋浴"], ["single_vanity", "單人洗手台"], ["double_vanity", "雙人洗手台"], ["bathtub", "浴缸"]],
    exclusions: [["bathtub", "不要浴缸"], ["glass_partition", "不要玻璃隔間"]],
  },
  balcony: {
    primary: [["laundry", "洗曬衣物"], ["rest", "休閒植栽"], ["storage", "儲藏為主"]],
    directions: [["laundry_zone", "洗衣與曬衣區"], ["planters", "植栽區"], ["folding_table", "折疊桌"], ["storage_cabinet", "防潮收納"]],
    exclusions: [["planters", "不要植栽"], ["laundry_zone", "不要洗曬區"]],
  },
});

function isGenerativeEquipmentRoom(room = activeQuestionnaireRoom()) {
  return Boolean(GENERATIVE_EQUIPMENT_OPTIONS[room?.type || room?.room_type]);
}

function structuralIntentInText(value = "") {
  return /擴建|延伸|移牆|拆牆|加房間|隔間|改門|改窗|打掉牆/.test(String(value));
}

function renderGenerativeEquipment(room = activeQuestionnaireRoom()) {
  const host = element.questionnaireGenerativeEquipment;
  if (!host || !room) return;
  const definition = GENERATIVE_EQUIPMENT_OPTIONS[room.type || room.room_type];
  host.hidden = !definition;
  if (!definition) return;
  const requirement = activeRoomRequirement();
  const equipment = requirement.generativeEquipment || {};
  element.questionnaireGenerativePrimaryUse.innerHTML = [
    '<option value="">請選擇</option>',
    ...definition.primary.map(([id, label]) => `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`),
  ].join("");
  element.questionnaireGenerativePrimaryUse.value = equipment.primaryUse || "";
  const selected = new Set(equipment.equipmentDirection || []);
  const excluded = new Set(equipment.mustNotHave || []);
  element.questionnaireGenerativeDirections.innerHTML = definition.directions.map(([id, label]) => `
    <label class="${selected.has(id) ? "is-selected" : ""}"><input type="checkbox" data-generative-direction="${escapeHtml(id)}" ${selected.has(id) ? "checked" : ""}><span>${escapeHtml(label)}</span></label>
  `).join("");
  element.questionnaireGenerativeExclusions.innerHTML = definition.exclusions.map(([id, label]) => `
    <label class="${excluded.has(id) ? "is-selected" : ""}"><input type="checkbox" data-generative-exclusion="${escapeHtml(id)}" ${excluded.has(id) ? "checked" : ""}><span>${escapeHtml(label)}</span></label>
  `).join("");
  element.questionnaireGenerationNotes.value = equipment.generationNotes || "";
  element.questionnaireGenerationWarning.textContent = structuralIntentInText(equipment.generationNotes)
    ? "偵測到可能影響結構或面積的描述。系統會維持現有牆、門、窗、樑、柱與房間大小，請確認需求會在現有空間內取捨。"
    : "此說明會一起送入 RAG 與最終生圖；系統不會擴建空間或移動固定結構。";
}

function updateGenerativeEquipment(room = activeQuestionnaireRoom()) {
  const requirement = activeRoomRequirement();
  if (!room || !requirement || !isGenerativeEquipmentRoom(room)) return;
  const directions = $$('[data-generative-direction]:checked', element.questionnaireGenerativeDirections)
    .map((input) => input.dataset.generativeDirection);
  const exclusions = $$('[data-generative-exclusion]:checked', element.questionnaireGenerativeExclusions)
    .map((input) => input.dataset.generativeExclusion);
  const notes = element.questionnaireGenerationNotes.value.trim();
  requirement.generativeEquipment = {
    ...(requirement.generativeEquipment || {}),
    required: true,
    primaryUse: element.questionnaireGenerativePrimaryUse.value || null,
    equipmentDirection: directions,
    mustNotHave: exclusions,
    priority: directions[0] || null,
    fitStatus: directions.some((id) => exclusions.includes(id)) ? "tradeoff_required" : "pending",
    generationNotes: notes,
    structuralIntentAcknowledged: structuralIntentInText(notes),
  };
  requirement.confirmed = false;
  renderGenerativeEquipment(room);
  renderQuestionnaireRoomSections();
  scheduleSave("requirements");
}

function updateGenerativeEquipmentNotes(room = activeQuestionnaireRoom()) {
  const requirement = activeRoomRequirement();
  if (!room || !requirement || !isGenerativeEquipmentRoom(room)) return;
  const notes = element.questionnaireGenerationNotes.value.trim();
  requirement.generativeEquipment = {
    ...(requirement.generativeEquipment || {}),
    required: true,
    generationNotes: notes,
    structuralIntentAcknowledged: structuralIntentInText(notes),
  };
  requirement.confirmed = false;
  element.questionnaireGenerationWarning.textContent = structuralIntentInText(notes)
    ? "偵測到可能影響固定結構或空間大小的描述。生圖仍會遵守已確認的牆、門、窗與房間尺寸，請確認這是風格想像而非施工指示。"
    : "補充會一併送給 RAG 與生圖流程；系統會依已確認的房間尺寸與固定結構保留可行的配置。";
  scheduleSave("requirements");
}


const UNASSIGNED_CONFIGURATION_ROOM_ID = "unassigned";

function configurationRoomById(roomId) {
  return state.rooms.find((candidate) => String(candidate.id) === String(roomId)) || null;
}

function configurationFurnitureBelongsToRoom(item, roomId) {
  const key = String(roomId || UNASSIGNED_CONFIGURATION_ROOM_ID);
  const itemRoom = configurationRoomById(item.roomId);
  if (key === UNASSIGNED_CONFIGURATION_ROOM_ID) {
    return !itemRoom;
  }
  return String(item.roomId) === key;
}

function configurationFurnitureForRoom(roomId, items = state.furniture2d) {
  return items.filter((item) => configurationFurnitureBelongsToRoom(item, roomId));
}

function unassignedDeferredFurniture() {
  state.roomRequirementModel.unassignedDeferredFurniture =
    state.roomRequirementModel.unassignedDeferredFurniture || [];
  return state.roomRequirementModel.unassignedDeferredFurniture;
}


function isVerifiedQuestionnaireFurnitureOffer(offer) {
  return Boolean(
    offer?.furniture_id
    && catalogItemRenderable(offer)
    && offer?.model_load_verified === true
    && offer?.room_fit_checked !== false
    && !knownUnavailableCatalogFurnitureIds().has(String(offer.furniture_id)),
  );
}

function applyVerifiedRandomQuestionnaireFurniture(room) {
  const furniture = roomFurnitureRequirement(room.id);
  const offers = (state.roomFurnitureRecommendations?.[room.id] || [])
    .filter(isVerifiedQuestionnaireFurnitureOffer);
  const selected = [];
  const selectedIds = new Set();
  const preferredTypes = questionnaireFurnitureProgram(room).defaults || [];

  for (const type of preferredTypes) {
    const offer = offers.find((candidate) => (
      // 同 applyDefault:電視櫃候選常非精確 tv-bench,改走 keyword/family 比對。
      (candidate.normalized_type === type || isQuestionnaireFallbackTypeMatch(candidate, type))
      && !selectedIds.has(String(candidate.furniture_id))
    ));
    if (!offer) continue;
    selected.push(offer);
    selectedIds.add(String(offer.furniture_id));
  }

  // Some small rooms do not have every preferred type in the catalog. Use a
  // verified alternative rather than silently reintroducing an unsupported type.
  for (const offer of offers) {
    if (selected.length >= 3) break;
    if (selectedIds.has(String(offer.furniture_id))) continue;
    selected.push(offer);
    selectedIds.add(String(offer.furniture_id));
  }

  furniture.selected = selected.map((offer, index) => ({
    ...questionnaireFurnitureSelectionItem(offer, index + 1),
    default_recommendation: true,
    selection_source: "test_random_verified_catalog",
    user_selected: false,
  }));
  furniture.required = furniture.selected.map((item) => item.normalized_type).filter(Boolean);
  furniture.optional = [];
  furniture.deferred = [];
  furniture.catalog_only = true;
}

function questionnaireFurniturePreviewUrl(offer = {}) {
  return replacementCandidateImageUrl(offer);
}

function questionnaireFurniturePreviewMarkup(offer = {}) {
  const preview = questionnaireFurniturePreviewUrl(offer);
  const label = questionnaireFurnitureDisplayLabel(offer);
  return `
    <div class="rp-questionnaire-furniture-preview">
      <img
        class="${preview ? "" : "is-loading"}"
        src="${escapeHtml(preview || "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")}"
        alt="${escapeHtml(label)} 商品預覽"
        data-questionnaire-furniture-thumbnail="${escapeHtml(offer.furniture_id || "")}"
        loading="lazy"
      />
      <span aria-hidden="true">家具預覽</span>
    </div>
  `;
}

function configurationBlockingFurnitureByRoom(blocking = configurationBlockingFurniture()) {
  const groups = new Map();
  blocking.forEach((item) => {
    const room = configurationRoomById(item.roomId);
    const roomId = String(room?.id || UNASSIGNED_CONFIGURATION_ROOM_ID);
    if (!groups.has(roomId)) {
      groups.set(roomId, {
        roomId,
        roomLabel: room?.label || room?.name || "未指定空間",
        items: [],
      });
    }
    groups.get(roomId).items.push(item);
  });
  return [...groups.values()];
}

function configurationDeferredFurnitureByRoom() {
  const rooms = state.rooms.flatMap((room) => {
    const deferred =
      state.roomRequirementModel.roomRequirements[room.id]?.furniture?.deferred || [];
    return deferred.length
      ? [{ roomId: room.id, roomLabel: room.label, items: deferred }]
      : [];
  });
  const unassigned = state.roomRequirementModel.unassignedDeferredFurniture || [];
  if (unassigned.length) {
    rooms.push({
      roomId: UNASSIGNED_CONFIGURATION_ROOM_ID,
      roomLabel: "未指定空間",
      items: unassigned,
    });
  }
  return rooms;
}

function configurationModelFailures() {
  return new Map(
    state.workflow?.currentStep === "white_model_3d"
      ? (whiteViewer.getDiagnostics()?.failedFurniture || [])
        .map((item) => [String(item.id), item.reason])
      : [],
  );
}

function syncFinalValidationToConfiguration(validatedObjects = []) {
  if (!state.sceneData || !Array.isArray(validatedObjects) || !validatedObjects.length) {
    return configurationBlockingFurniture();
  }
  const validatedById = new Map(
    validatedObjects.map((item) => [String(item.furniture_id), item]),
  );
  state.sceneData.scene_objects = (state.sceneData.scene_objects || []).map((item) => {
    const validated = validatedById.get(String(item.furniture_id));
    if (!validated) return item;
    return {
      ...item,
      ...validated,
      position_cm: { ...(item.position_cm || {}), ...(validated.position_cm || {}) },
      size_cm: { ...(item.size_cm || {}), ...(validated.size_cm || {}) },
    };
  });
  state.sceneData.scene_objects.forEach((item) => {
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      item,
      furniture2dDefaultsForSceneObject(item),
    );
  });
  syncFurnitureInventoryAcrossSchemes();
  renderLayoutRoomFilter();
  renderLayoutFurniture();
  renderConfigurationPlan();
  return configurationBlockingFurniture();
}

function configurationPlanPixelsPerCm() {
  if (!element.configurationPlanImage?.naturalWidth) return 0;
  const imageRect = imageContentRect(element.configurationPlanImage);
  const naturalRatio = imageRect.width
    / Math.max(element.configurationPlanImage.naturalWidth, 1);
  return (1 / planGeometry().scale) * naturalRatio;
}

function configurationFurniturePixelPosition(item) {
  const center = planCenterCm();
  return planCmToLayerPixel(
    {
      x: center.x + item.xCm,
      y: center.y + item.yCm,
    },
    planGeometry(),
    configurationPlanPixelsPerCm(),
  );
}

function configurationFurnitureNumber(item, fallbackIndex = state.furniture2d.indexOf(item)) {
  const sceneIndex = sceneObjectIndexByFurnitureId(item.id);
  return sceneIndex >= 0 ? sceneIndex + 1 : fallbackIndex + 1;
}

function renderConfigurationPlan() {
  if (!element.configurationPlanImage) return;
  pruneRetiredAppliances();
  const planSource = element.layoutImage.currentSrc || element.layoutImage.src;
  if (planSource && element.configurationPlanImage.src !== planSource) {
    element.configurationPlanImage.src = planSource;
  }
  syncOverlayToImage(
    element.configurationPlanStage,
    element.configurationPlanImage,
    element.configurationPlanLayer,
  );

  const blocking = configurationBlockingFurniture();
  const blockingIds = new Set(blocking.map((item) => String(item.id)));
  const modelFailures = configurationModelFailures();
  const scale = configurationPlanPixelsPerCm();
  element.configurationPlanLayer.innerHTML = "";
  if (scale > 0 && state.showFurnitureNumbers) {
    element.configurationPlanLayer.innerHTML = state.furniture2d.map((item, index) => {
      const pixel = configurationFurniturePixelPosition(item);
      const style = furnitureFootprintStyle(item, scale);
      const invalid = blockingIds.has(String(item.id));
      const furnitureNumber = configurationFurnitureNumber(item, index);
      return `
        <button type="button"
          class="rp-configuration-furniture ${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${invalid ? "is-invalid" : ""}"
          data-select-configuration-furniture="${escapeHtml(item.id)}"
          aria-label="家具 ${furnitureNumber} ${escapeHtml(item.label)}"
          style="left:${pixel.x}px;top:${pixel.y}px;width:${style.width};height:${style.height};transform:${style.transform}">
          <b>${furnitureNumber}</b>
        </button>
      `;
    }).join("");
  }

  element.configurationPlanFurnitureList.innerHTML = state.furniture2d.map((item, index) => {
    const furnitureNumber = configurationFurnitureNumber(item, index);
    return `
      <button type="button"
        class="${item.id === state.selectedFurniture2dId ? "is-active" : ""} ${blockingIds.has(String(item.id)) ? "is-invalid" : ""}"
        data-select-configuration-furniture="${escapeHtml(item.id)}">
        <b>${furnitureNumber}</b>
        <span><strong>${escapeHtml(item.label)}</strong><small>${item.widthCm} × ${item.depthCm} cm</small></span>
        <span>${blockingIds.has(String(item.id)) ? "待處理" : "合法"}</span>
      </button>
    `;
  }).join("") || "<p class=\"rp-control-hint\">目前沒有家具。</p>";

  element.configurationPendingCount.textContent = String(blocking.length);
  const issueBadge = $("#scene-sidebar-issue-badge");
  if (issueBadge) {
    issueBadge.hidden = blocking.length === 0;
    issueBadge.textContent = String(blocking.length);
  }
  const blockingRooms = configurationBlockingFurnitureByRoom(blocking);
  const deferredRooms = configurationDeferredFurnitureByRoom();
  const blockingMarkup = blockingRooms.map((group) => {
    const placementFailures = group.items.filter(
      (item) => !modelFailures.has(String(item.id)),
    );
    const summary = placementFailures.length
      ? `${placementFailures.length} 件因碰撞、淨空或房間尺寸無法放入`
      : "資料庫模型無法載入，可更換或同意本次暫緩";
    const items = group.items.map((item) => {
      const furnitureNumber = configurationFurnitureNumber(item);
      const furnitureKey = String(item.id);
      const reason = modelFailures.get(furnitureKey)
        || item.placementReason
        || "家具碰撞、超出房間或淨空不足。";
      const modelFailed = modelFailures.has(furnitureKey);
      const reflowing = configurationReflowInFlight.has(furnitureKey);
      const reflowLocked = configurationReflowInFlight.size > 0;
      const repairAction = modelFailed
        ? `<button type="button" data-replace-configuration-furniture="${escapeHtml(item.id)}">更換家具</button>`
        : `<button type="button" data-reflow-configuration-furniture="${escapeHtml(item.id)}"
            ${reflowLocked ? "disabled" : ""}>${reflowing ? "重新配置中…" : "只重排此家具"}</button>
          <button type="button" data-replace-smaller-configuration-furniture="${escapeHtml(item.id)}">更換較小款</button>`;
      return `
        <div class="rp-configuration-pending-item">
          <b>${furnitureNumber}</b>
          <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(reason)}</small></span>
          <div>
            <button type="button" data-select-configuration-furniture="${escapeHtml(item.id)}">定位</button>
            ${repairAction}
          </div>
        </div>
      `;
    }).join("");
    return `
      <section class="rp-configuration-pending-room">
        <header>
          <div><strong>${escapeHtml(group.roomLabel)}</strong><small>${escapeHtml(summary)}</small></div>
          ${group.items.length ? `<button type="button"
            data-prioritize-configuration-room="${escapeHtml(group.roomId)}">保留全部並重新擺位</button>` : ""}
        </header>
        ${items}
      </section>
    `;
  }).join("");
  const deferredMarkup = deferredRooms.map((group) => `
    <section class="rp-configuration-pending-room is-deferred">
      <header><div><strong>${escapeHtml(group.roomLabel)} · 已暫緩</strong>
        <small>這是舊版流程留下的暫緩紀錄；新版不會因重新擺位而移除家具。</small></div>
        <button type="button" data-return-deferred-configuration-room="${escapeHtml(group.roomId)}">返回逐房需求</button></header>
      <ul>${group.items.map((item) =>
        `<li>${escapeHtml(item.label || item.name_zh || item.normalized_type)}</li>`
      ).join("")}</ul>
    </section>
  `).join("");
  element.configurationPendingList.innerHTML = blockingMarkup
    || deferredMarkup
    || "<p class=\"rp-configuration-clear\">目前沒有待處理家具。</p>";
  if (blockingMarkup && deferredMarkup) {
    element.configurationPendingList.insertAdjacentHTML("beforeend", deferredMarkup);
  }

  // 待處理家具與逐房方案關卡共用同一顆確認鈕，交給同一個函式決定，
  // 避免兩邊各自寫 disabled 後互相蓋掉。
  syncConfigurationConfirmButton();
}

async function reflowSingleConfigurationFurniture(furnitureId) {
  const furnitureKey = String(furnitureId);
  if (configurationReflowInFlight.has(furnitureKey) || configurationReflowInFlight.size > 0) {
    return;
  }
  const item = state.furniture2d.find(
    (candidate) => String(candidate.id) === furnitureKey,
  );
  if (!item) return;
  const room = configurationRoomById(item.roomId);
  if (!room) {
    setStatus(
      `${item.label} 目前未指定空間；請先回第 5 步指定房間，或按「同意擇優配置」先略過。`,
      "error",
    );
    return;
  }
  configurationReflowInFlight.add(furnitureKey);
  renderConfigurationPlan();
  setStatus(`正在只重新配置「${item.label}」…`);
  try {
    const resolved = await resolveFurniturePosition(item);
    if (!resolved || resolved.placement_failed) {
      item.placementFailed = true;
      item.placementReason = resolved?.placement_reason || "目前房間沒有合法位置。";
      renderConfigurationPlan();
      setStatus(`無法重新配置「${item.label}」：${item.placementReason}`, "error");
      return;
    }
    let sceneIndex = sceneObjectIndexByFurnitureId(item.id);
    if (sceneIndex < 0) {
      state.sceneData.scene_objects.push(resolved);
      sceneIndex = state.sceneData.scene_objects.length - 1;
    }
    const sceneObject = state.sceneData.scene_objects[sceneIndex];
    Object.assign(sceneObject, resolved, {
      position_locked: true,
      placement_failed: false,
      placement_reason: "",
    });
    state.furniture2d = upsertFurniture2dFromSceneObject(
      state.furniture2d,
      sceneObject,
    );
    state.selectedFurniture2dId = item.id;
    state.selectedSceneIndex = sceneIndex;
    await whiteViewer.updateObject(sceneObject);   // 只重擺這一件，其餘家具與房殼不動
    whiteViewer.setViewMode("orbit");
    renderLayoutFurniture();
    renderSceneObjectList();
    whiteViewer.selectObjectByIndex(sceneIndex);
    scheduleSave("white_model_3d");
    setStatus(`已只重新配置「${item.label}」，其他合法家具位置保持不變。`);
  } catch (error) {
    setStatus(errorMessage(error), "error");
  } finally {
    configurationReflowInFlight.delete(furnitureKey);
    renderConfigurationPlan();
  }
}

function configurationFurniturePriority(item) {
  const essentialTypes = new Set([
    "bed",
    "sofa",
    "dining-table",
    "bathroom-vanity",
  ]);
  return [
    item.userRequired === true ? 0 : 1,
    essentialTypes.has(item.type) ? 0 : 1,
    Number(item.selectionPriority) || 999,
    item.autoAdded === true ? 1 : 0,
    Math.max(Number(item.widthCm) || 0, 1) * Math.max(Number(item.depthCm) || 0, 1),
  ];
}

function compareConfigurationFurniturePriority(left, right) {
  const leftPriority = configurationFurniturePriority(left);
  const rightPriority = configurationFurniturePriority(right);
  for (let index = 0; index < leftPriority.length; index += 1) {
    if (leftPriority[index] !== rightPriority[index]) {
      return leftPriority[index] - rightPriority[index];
    }
  }
  return String(left.id).localeCompare(String(right.id));
}

async function prioritizeUnassignedConfigurationFurniture() {
  if (!state.sceneData) return;
  const originalItems = configurationFurnitureForRoom(
    UNASSIGNED_CONFIGURATION_ROOM_ID,
    configurationBlockingFurniture(),
  ).sort(compareConfigurationFurniturePriority);
  if (!originalItems.length) return;
  renderConfigurationPlan();
  setStatus(
    `有 ${originalItems.length} 件家具尚未指定房間；家具已保留，請先定位或回到逐房需求指定空間。`,
    "error",
  );
}

async function prioritizeConfigurationRoomFurniture(roomId) {
  const room = configurationRoomById(roomId);
  if (!state.sceneData) return;
  if (!room && String(roomId) === UNASSIGNED_CONFIGURATION_ROOM_ID) {
    await prioritizeUnassignedConfigurationFurniture();
    return;
  }
  if (!room) return;
  const originalItems = state.furniture2d
    .filter((item) => configurationFurnitureBelongsToRoom(item, roomId))
    .sort(compareConfigurationFurniturePriority);
  if (!originalItems.length) return;
  const modelFailureIds = new Set(configurationModelFailures().keys());
  const validItems = originalItems.filter(
    (item) => !modelFailureIds.has(String(item.id)),
  );
  let placedObjects = [];
  setStatus(`正在為「${room.label}」保留全部家具並重新擺位…`);
  try {
    if (validItems.length) {
      const layout = await api("/api/scene/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          floorplan_editor: confirmedFloorplanEditor(),
          placement_room_id: room.id,
          scene_objects: validItems.map((item) =>
            toSceneFurniture(item, { positionLocked: false })
          ),
        }),
      });
      placedObjects = layout.scene_objects || [];
    }
    const placedById = new Map(placedObjects.map((item) => [String(item.furniture_id), item]));
    const updatedItems = originalItems.map((item) => {
      const placed = placedById.get(String(item.id));
      const modelFailed = modelFailureIds.has(String(item.id));
      const placementFailed = modelFailed || !placed || Boolean(placed.placement_failed);
      return {
        ...item,
        xCm: placementFailed ? item.xCm : Number(placed.position_cm?.x || item.xCm || 0),
        yCm: placementFailed ? item.yCm : Number(placed.position_cm?.z || item.yCm || 0),
        rotationDeg: placementFailed ? item.rotationDeg : Number(placed.rotation_y_deg || item.rotationDeg || 0),
        placementFailed,
        placementReason: placementFailed
          ? (modelFailureIds.get(String(item.id)) || placed?.placement_reason || "目前房間沒有可放入的合法位置。")
          : "",
      };
    });
    const roomFurnitureIds = new Set(originalItems.map((item) => String(item.id)));
    state.furniture2d = [
      ...state.furniture2d.filter((item) => !roomFurnitureIds.has(String(item.id))),
      ...updatedItems,
    ];
    const originalSceneById = new Map(
      (state.sceneData.scene_objects || []).map((item) => [String(item.furniture_id), item]),
    );
    state.sceneData.scene_objects = [
      ...(state.sceneData.scene_objects || []).filter(
        (item) => !roomFurnitureIds.has(String(item.furniture_id)),
      ),
      ...updatedItems.map((item) => ({
        ...(originalSceneById.get(String(item.id)) || toSceneFurniture(item)),
        ...(placedById.get(String(item.id)) || {}),
        placement_failed: item.placementFailed,
        placement_reason: item.placementReason,
      })),
    ];
    const furniture = roomFurnitureRequirement(room.id);
    furniture.deferred = [];
    const scheme = activeScheme();
    scheme.furniture = JSON.parse(JSON.stringify(state.furniture2d));
    scheme.sceneData = JSON.parse(JSON.stringify(state.sceneData));
    await whiteViewer.loadScene(state.sceneData);
    renderLayoutFurniture();
    renderSceneObjectList();
    renderConfigurationPlan();
    scheduleSave("white_model_3d");
    const unresolved = updatedItems.filter((item) => item.placementFailed).length;
    setStatus(
      `「${room.label}」已保留全部 ${updatedItems.length} 件家具並重新擺位；${unresolved ? `仍有 ${unresolved} 件需要你決定位置或更換款式。` : "全部家具皆已找到合法位置。"}`,
    );
  } catch (error) {
    setStatus(errorMessage(error), "error");
  }
}

function renderSelectedFurnitureEditor() {
  const item = state.furniture2d.find((candidate) => candidate.id === state.selectedFurniture2dId);
  if (!item) {
    element.selectedFurnitureEditor.hidden = true;
    return;
  }
  element.selectedFurnitureEditor.hidden = false;
  element.selectedFurnitureName.textContent = item.label;
  element.selectedFurnitureReason.textContent = `配置原因：${item.reason || "使用者手動加入，可調整實際尺寸。"}`;
  element.selectedFurnitureWidth.value = item.widthCm;
  element.selectedFurnitureDepth.value = item.depthCm;
}

let furnitureDrag = null;
function layoutPointerDown(event) {
  const target = event.target.closest("[data-furniture-2d-id]");
  if (!target) return;
  const furnitureId = target.getAttribute("data-furniture-2d-id");
  const item = state.furniture2d.find((candidate) => candidate.id === furnitureId);
  if (!item) return;
  state.selectedFurniture2dId = item.id;
  furnitureDrag = {
    item,
    startX: event.clientX,
    startY: event.clientY,
    originalX: item.xCm,
    originalY: item.yCm,
  };
  target.setPointerCapture?.(event.pointerId);
  renderLayoutFurniture();
  syncSelected2dFurnitureToScene({ focus: false });
}

function layoutPointerMove(event) {
  if (!furnitureDrag) return;
  const scale = layoutPixelsPerCm();
  furnitureDrag.item.xCm = furnitureDrag.originalX + (event.clientX - furnitureDrag.startX) / scale;
  furnitureDrag.item.yCm = furnitureDrag.originalY - (event.clientY - furnitureDrag.startY) / scale;
  renderLayoutFurniture();
}


async function resolveFurniturePosition(item) {
  // A single-item repair must not send furniture from other rooms to the
  // selected room's layout boundary. Keep peers in the same room fixed and
  // give the engine only the requested item as movable.
  const otherObjects = state.furniture2d
    .filter(
      (candidate) => candidate.id !== item.id && candidate.roomId === item.roomId,
    )
    .map((candidate) => ({
      ...toSceneFurniture(candidate),
      position_locked: true,
    }));
  const layout = await api("/api/scene/layout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      floorplan_editor: confirmedFloorplanEditor(),
      placement_room_id: item.roomId,
      scene_objects: [
        ...otherObjects,
        {
          ...toSceneFurniture(item, { positionLocked: false }),
          furniture_id: item.id,
          catalog_furniture_id: item.catalogFurnitureId || null,
          position_locked: false,
          placement_hint_cm: { x: item.xCm, z: item.yCm },
        },
      ],
    }),
  });
  return (layout.scene_objects || []).find(
    (candidate) => String(candidate.furniture_id || "") === String(item.id),
  );
}

async function finishFurnitureDrag(drag) {
  if (!drag) return;
  try {
    const resolved = await resolveFurniturePosition(drag.item);
    if (!resolved || resolved.placement_failed) {
      drag.item.xCm = drag.originalX;
      drag.item.yCm = drag.originalY;
      drag.item.placementFailed = true;
      drag.item.placementReason = resolved?.placement_reason || "位置未通過家具引擎檢查";
      element.layoutError.textContent = `${drag.item.label}：${drag.item.placementReason}`;
    } else {
      drag.item.xCm = Number(resolved.position_cm?.x || 0);
      drag.item.yCm = Number(resolved.position_cm?.z || 0);
      drag.item.rotationDeg = Number(resolved.rotation_y_deg || 0);
      drag.item.placementFailed = false;
      drag.item.placementReason = "";
      element.layoutError.textContent = "";
      const room = state.rooms.find((candidate) => candidate.id === drag.item.roomId);
      setStatus(`已在「${room?.label || "目前房間"}」內貼齊最近有效牆面。`);
    }
  } catch (error) {
    drag.item.xCm = drag.originalX;
    drag.item.yCm = drag.originalY;
    element.layoutError.textContent = errorMessage(error);
  }
  renderLayoutFurniture();
  invalidateDownstreamFrom("layout_2d", "2D 家具位置已修改，3D 家具配置與第 6 步預覽需要重新產生。");
  scheduleSave("layout_2d");
}
async function finishActiveFurnitureDrag() {
  const completedDrag = furnitureDrag;
  furnitureDrag = null;
  if (completedDrag) await finishFurnitureDrag(completedDrag);
}

  return {
    applyVerifiedRandomQuestionnaireFurniture,
    autoLayoutFurniture,
    compareConfigurationFurniturePriority,
    configurationBlockingFurniture,
    configurationBlockingFurnitureByRoom,
    configurationDeferredFurnitureByRoom,
    configurationDeferredFurnitureIds,
    configurationFurnitureBelongsToRoom,
    configurationFurnitureForRoom,
    configurationFurnitureNumber,
    configurationFurniturePixelPosition,
    configurationFurniturePriority,
    configurationModelFailures,
    configurationPlanPixelsPerCm,
    configurationRoomById,
    finishActiveFurnitureDrag,
    finishFurnitureDrag,
    furniturePixelPosition,
    furniturePlacementInvalid,
    GENERATIVE_EQUIPMENT_OPTIONS,
    hasAuthoritativeScenePlacement,
    isGenerativeEquipmentRoom,
    isVerifiedQuestionnaireFurnitureOffer,
    itemCollision,
    layoutPixelsPerCm,
    layoutPointerDown,
    layoutPointerMove,
    materialPreviewForLayout,
    misplacedAssignedRoomFurniture,
    prioritizeConfigurationRoomFurniture,
    prioritizeUnassignedConfigurationFurniture,
    questionnaireFurniturePreviewMarkup,
    questionnaireFurniturePreviewUrl,
    reflowSingleConfigurationFurniture,
    renderConfigurationPlan,
    renderFurnitureLibrary,
    renderGenerativeEquipment,
    renderLayoutFurniture,
    renderLayoutRoomFilter,
    renderLayoutRoomMaterials,
    renderLayoutSurfaceOverlay,
    renderSelectedFurnitureEditor,
    repairFurnitureRoomPlacements,
    resolveFurniturePosition,
    structuralIntentInText,
    syncFinalValidationToConfiguration,
    UNASSIGNED_CONFIGURATION_ROOM_ID,
    unassignedDeferredFurniture,
    updateGenerativeEquipment,
    updateGenerativeEquipmentNotes,
  };
}
