// Questionnaire furniture program and catalog recommendation controller.
export function createQuestionnaireFurnitureController({
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
  furnitureCollisionFootprintCm,
  furnitureFootprintStyle,
  glbThumbnailQueue,
  glbThumbnailScene,
  glbThumbnailViewer,
  goTo,
  imageContentRect,
  invalidateDownstreamFrom,
  isQuestionnaireFallbackTypeMatch,
  loadSelectedSceneAppearance,
  mergeCatalogFurniture,
  normalizedRoomSurfaces,
  occupantsFromBasicAnswers,
  openQuestionnaireFurnitureCatalog,
  persistConfigurationState,
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
  questionnaireFurnitureInFlight,
  questionnaireFurniturePreviewMarkup,
  rankCatalogFurniture,
  recommendedFurnitureForRoom,
  reconcileFurniture2dAfterGeneration,
  removeRetiredAppliancesFromFurniture,
  renderQuestionnaireRoomSections,
  renderSceneObjectList,
  replaceFurniture2DItem,
  REPLACEMENT_TYPE_LABELS,
  replacementCandidateFitsRoom,
  replacementViewer,
  resolvedVisualPreferences,
  resolveSurfaceOption,
  ROOM_TYPE_EXCLUDED_FURNITURE_TYPES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  roomCenter,
  roomDimensions,
  roomPolygonSvg,
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
function roomIdForScenePosition(positionCm = {}) {
  const center = planCenterCm();
  const planPoint = {
    x: center.x + Number(positionCm.x || 0),
    y: center.y + Number(positionCm.z || 0),
  };
  return state.rooms.find(
    (room) => pointInPolygonCm(planPoint, room.polygon_cm || []),
  )?.id || state.selectedRoomId || state.rooms[0]?.id || null;
}

function scenePositionInsideRoom(positionCm = {}, roomId = null) {
  const room = state.rooms.find((candidate) => String(candidate.id) === String(roomId));
  const x = Number(positionCm.x);
  const z = Number(positionCm.z);
  if (!room || !Number.isFinite(x) || !Number.isFinite(z)) return false;
  const center = planCenterCm();
  return pointInPolygonCm(
    { x: center.x + x, y: center.y + z },
    room.polygon_cm || [],
  );
}

function furniture2dDefaultsForSceneObject(sceneObject) {
  const match = findFurniture2DVariant(
    sceneObject?.normalized_type,
    sceneObject?.variant_id,
  );
  return {
    roomId: sceneObject?.placement_room_id
      || roomIdForScenePosition(sceneObject?.position_cm),
    type: sceneObject?.normalized_type || match?.category?.type || "furniture",
    variantId: match?.selected?.id || sceneObject?.variant_id || "standard",
    iconPath: match?.selected?.iconPath || "",
    label: sceneObject?.name_zh
      || sceneObject?.name_zh_raw
      || match?.selected?.label
      || "家具",
    reason: "使用者在 3D 配置與預覽工作台中新增或替換。",
    userRequired: true,
  };
}

function roomSurfaceAssignments() {
  const center = planCenterCm();
  return state.rooms.map((room) => {
    const requirement = state.roomRequirementModel?.roomRequirements?.[room.id];
    const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {});
    const surfaceDraft = state.roomFinishDrafts?.[String(room.id)] || {};
    return {
      room_id: room.id,
      room_label: room.label,
      palette_id: surfaces.paletteId || null,
      wall_surface_ids: [...(surfaces.wallSurfaceIds || [])],
      wall_overrides: { ...(surfaces.wallOverrides || {}) },
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
      wall_material_id: surfaces.wallDefault?.materialId || null,
      wall_color_hex: surfaces.wallDefault?.color || null,
      floor_material_id: surfaces.floor?.materialId || null,
      floor_color_hex: surfaces.floor?.color || null,
      ceiling_material_id: surfaces.ceiling?.materialId || null,
      ceiling_style_id: surfaces.ceiling?.styleId || null,
      ceiling_color_hex: surfaces.ceiling?.color || null,
      lighting_id: surfaces.ceiling?.lightingId || null,
      air_conditioning: requirement?.climate?.airConditioning || null,
      step_six_surface_confirmed: surfaceDraft.stepSixSurfaceConfirmed === true,
      step_six_surface_confirmed_at: surfaceDraft.stepSixSurfaceConfirmedAt || null,
    };
  });
}

function planCenterCm() {
  const { bbox, scale } = planGeometry();
  return {
    x: (bbox[2] - bbox[0]) * scale / 2,
    y: (bbox[3] - bbox[1]) * scale / 2,
  };
}

function furnitureOfferFromSpec(room, spec, index) {
  const [type, variant, reason, autoAdded] = spec;
  const item = createFurniture2DItem(type, variant, {
    id: `${room.id}-${type}-${variant || "standard"}-candidate-${index + 1}`,
    roomId: room.id,
  });
  return {
    furniture_id: item.id,
    normalized_type: item.type,
    variant_id: item.variantId,
    name_zh_raw: item.label,
    size_cm: {
      width: item.widthCm,
      depth: item.depthCm,
      height: item.heightCm,
    },
    reason,
    auto_added: autoAdded === true,
    selection_source: "local_rules",
  };
}

function questionnairePackForRoom(room) {
  const paletteId =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.paletteId;
  return STYLE_PACKS.find((pack) => pack.id === paletteId)
    || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
}

function questionnaireFurnitureRequest(room, spec) {
  const [type, variant] = spec;
  const template = createFurniture2DItem(type, variant, { roomId: room.id });
  const pack = questionnairePackForRoom(room);
  const surfaces =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {};
  const requirement = state.roomRequirementModel?.roomRequirements?.[room.id] || {};
  const visualPreferenceText = visualPreferencesForRoom(room)
    .flatMap((preference) => [
      preference.option_id,
      preference.custom,
      preference.preference_direction,
    ])
    .filter(Boolean)
    .join(" ");
  return {
    type,
    roomType: room.type || room.room_type || "",
    roomLabel: room.label || room.name || "",
    styleId: pack.styleId,
    palette: pack.palette,
    queryText: [
      room.label,
      room.type,
      requirement.summary,
      requirement.notes,
      requirement.usage,
      requirement.furniture?.selected?.map((item) => item.label || item.type).join(" "),
      visualPreferenceText,
    ].filter(Boolean).join(" "),
    preferAnchor: ["bed", "sofa", "dining-table", "storage-cabinet", "appliance-cabinet"].includes(type),
    materials: [
      ...(pack.furniture?.materialLanguage || []),
      surfaces.wallDefault?.materialId,
      surfaces.floor?.materialId,
    ].filter(Boolean),
    widthCm: template.widthCm,
    depthCm: template.depthCm,
  };
}

async function catalogCandidatesForType(
  type,
  { styleId = "", query = "", catalogType = "", searchAll = false } = {},
) {
  const route = CATALOG_RETRIEVAL_ROUTES[type]
    || { endpoint: "/api/furniture", type };
  const canSearchAll = searchAll && route.endpoint === "/api/furniture";
  const routeTypes = canSearchAll
    ? [""]
    : (catalogType ? [catalogType] : (route.types || [route.type]));
  const candidateGroups = await Promise.all(routeTypes.map(async (routeType) => {
    const params = new URLSearchParams({
      detail: "scene",
      page_size: "80",
    });
    if (routeType) params.set("type", routeType);
    if (route.endpoint === "/api/furniture") params.set("has_model", "true");
    // "瀏覽全部家具資料庫" must not inherit the current item's type-specific
    // search term (for example, a mirror cabinet would otherwise only find mirrors).
    const searchQuery = [canSearchAll ? "" : route.query, query]
      .filter(Boolean)
      .join(" ");
    if (searchQuery) params.set("q", searchQuery);
    if (styleId && route.endpoint === "/api/furniture") {
      params.set("style", styleId);
    }
    let payload = await api(`${route.endpoint}?${params.toString()}`);
    if (!(payload.items || []).length && params.has("style")) {
      params.delete("style");
      payload = await api(`${route.endpoint}?${params.toString()}`);
    }
    return payload.items || [];
  }));
  return candidateGroups.flat();
}

async function catalogOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  const candidates = await catalogCandidatesForType(spec[0], {
    styleId: request.styleId,
    query: request.queryText,
  });
  const matchingCandidates = candidates.filter((candidate) =>
    isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => catalogFurnitureOffer(candidate, {
    roomId: room.id,
    requestedType: spec[0],
    requestedVariant: spec[1],
    reason: spec[2]
      || `${room.label}的問卷風格、色卡、材質與實際尺寸綜合匹配`,
  }));
}

async function catalogFallbackOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[spec[0]] || {};
  const label = rule.query || REPLACEMENT_TYPE_LABELS[spec[0]] || spec[0];
  let candidates = await catalogCandidatesForType(spec[0], {
    query: label,
    searchAll: true,
  });
  if (!candidates.length) {
    candidates = await catalogCandidatesForType(spec[0], { searchAll: true });
  }
  const matchingCandidates = candidates.filter((candidate) =>
    isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => ({
    ...catalogFurnitureOffer(candidate, {
      roomId: room.id,
      requestedType: spec[0],
      requestedVariant: spec[1],
      reason: `${room.label}未取得精準風格結果，改以同類可配置家具推薦`,
    }),
    recommendation_tier: "similar",
  }));
}

async function catalogOffersForRoomPlans(roomPlans) {
  return Object.fromEntries(await Promise.all(roomPlans.map(async ({ room, specs }) => {
    const groups = await Promise.all(specs.map(async (spec, index) => {
      try {
        return await catalogOffersForSpec(room, spec, index);
      } catch (error) {
        console.warn("Catalog RAG retrieval fallback", error);
        return [];
      }
    }));
    return [room.id, groups.flatMap((offers, index) => (
      offers.length
        ? offers
        : [furnitureOfferFromSpec(room, specs[index], index)]
    ))];
  })));
}

function questionnaireFurniturePreferenceTags(room) {
  const styleId = questionnairePackForRoom(room)?.styleId || "default";
  return QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS[styleId]
    || QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS.default;
}

function renderQuestionnaireFurniturePreferenceTags(room = activeQuestionnaireRoom()) {
  if (!element.questionnaireFurniturePreferenceTags || !room) return;
  const selected = new Set(roomFurnitureRequirement(room.id)?.preferenceTags || []);
  element.questionnaireFurniturePreferenceTags.innerHTML = questionnaireFurniturePreferenceTags(room)
    .map((tag) => `<button type="button" data-questionnaire-furniture-tag="${escapeHtml(tag)}"
      class="${selected.has(tag) ? "is-active" : ""}" aria-pressed="${selected.has(tag)}">${escapeHtml(tag)}</button>`)
    .join("");
}

function toggleQuestionnaireFurniturePreferenceTag(tag) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !tag) return;
  const tags = new Set(furniture.preferenceTags || []);
  if (tags.has(tag)) tags.delete(tag);
  else tags.add(tag);
  furniture.preferenceTags = [...tags];
  const text = element.questionnaireFurniturePreference?.value.trim() || "";
  const values = new Set(text.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean));
  furniture.preferenceTags.forEach((value) => values.add(value));
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = [...values].join("、");
  }
  furniture.preferenceText = element.questionnaireFurniturePreference?.value.trim() || "";
  renderQuestionnaireFurniturePreferenceTags(room);
  scheduleSave("requirements");
}

function questionnaireBedSizeFamily(offer) {
  const source = [offer?.name_zh, offer?.name_zh_raw, offer?.name_en]
    .filter(Boolean)
    .join(" ");
  const namedSize = [...source.matchAll(/(\d{2,3})\s*[x×]\s*(\d{2,3})/gi)]
    .map((match) => ({ width: Number(match[1]), depth: Number(match[2]) }))
    .find((size) => size.width >= 70 && size.width <= 220 && size.depth >= 180 && size.depth <= 230);
  const width = namedSize?.width || Number(offer?.size_cm?.width || 0);
  if (width <= 100) return "單人床";
  if (width <= 140) return "小雙人床";
  if (width <= 165) return "標準雙人床";
  if (width <= 195) return "加大雙人床";
  return "特大雙人床";
}

function questionnaireFurnitureDisplayLabel(offer) {
  const type = String(offer?.normalized_type || "");
  const width = Number(offer?.size_cm?.width || 0);
  if (type === "bed") return questionnaireBedSizeFamily(offer);
  if (type === "wardrobe") {
    if (width <= 80) return "單門衣櫃";
    if (width <= 125) return "雙門衣櫃";
    if (width <= 185) return "三門衣櫃";
    return "大容量衣櫃";
  }
  if (type === "desk") {
    if (width <= 100) return "小型書桌";
    if (width <= 150) return "書桌";
    return "大書桌";
  }
  return QUESTIONNAIRE_FURNITURE_SHORT_LABELS[type]
    || QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS[type]
    || REPLACEMENT_TYPE_LABELS[type]
    || type;
}

function questionnaireOffersWithSizeChoices(type, candidates) {
  if (type !== "bed") {
    const byFamily = new Map();
    candidates.forEach((candidate) => {
      const family = questionnaireFurnitureDisplayLabel(candidate);
      if (!byFamily.has(family)) byFamily.set(family, candidate);
    });
    return [...byFamily.values()].slice(0, 4);
  }
  const byFamily = new Map();
  candidates.forEach((candidate) => {
    const family = questionnaireBedSizeFamily(candidate);
    if (!byFamily.has(family)) byFamily.set(family, candidate);
  });
  return [...byFamily.values()].slice(0, 4);
}

function questionnaireFurnitureProgram(room) {
  const type = String(room?.type || room?.room_type || "default").toLowerCase();
  return QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS[type]
    || QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS.default;
}

function questionnaireFurnitureRole(room, offer) {
  const program = questionnaireFurnitureProgram(room);
  const type = String(offer?.normalized_type || "");
  if (program.required.includes(type)) return { rank: 0, label: "基本配置", reason: program.labels[type] || "本房的基本配置" };
  if (program.defaults.includes(type)) return { rank: 1, label: "建議配置", reason: program.labels[type] || "依房間用途建議" };
  return { rank: 2, label: "可選配置", reason: program.labels[type] || "依用途與偏好推薦" };
}

function questionnairePreferenceFurnitureSpecs(room) {
  const furniture = roomFurnitureRequirement(room.id) || {};
  const text = [furniture.preferenceText, ...(furniture.preferenceTags || [])].join(" ").toLowerCase();
  if (!text) return [];
  const matches = [
    ["chair", /椅|chair|單椅|休閒椅|餐椅|工作椅|辦公椅/],
    ["desk", /書桌|工作桌|desk|workstation/],
    ["table", /茶几|餐桌|table/],
    ["sofa", /沙發|sofa/],
    ["wardrobe", /衣櫃|衣柜|wardrobe/],
    ["storage", /收納|櫃|柜|storage|cabinet/],
  ];
  return matches.flatMap(([key, pattern]) => {
    if (!pattern.test(text)) return [];
    const types = QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES[key][room.type]
      || QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES[key].default || [];
    return types.map((type) => [type, "standard", `依「${furniture.preferenceText}」補充`, false]);
  });
}

// ROOM_USAGE_FURNITURE_SPECS 只依「用途」對應家具,QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES
// 只依偏好關鍵字對應,兩張表都沒有房型概念。陽台的預設用途是「洗曬衣物」(laundry),
// 而 laundry 對到 storage-cabinet,於是陽台一開始就被塞進收納櫃並在第 6 步擺出來;
// 打「收納」「衣櫃」之類偏好也會再補一次。後端 affinity_permits 對未列族系一律放行
// (backend/agent/knowledge.py 刻意不限 wardrobe 族系),擋不住這條,所以在需求端擋。
// 這裡只擋自動推薦;使用者仍可從家具資料庫手動加入。
function questionnaireFurnitureSpecsForRoom(room) {
  // 浴室一律不推薦家具:房型推薦表已清空,但用途「衛浴收納」仍會經 store →
  // 收納櫃、偏好打「收納」也會再補一次,勾了就會在第 6 步擺進浴室。
  // 這裡只擋自動推薦;使用者仍可從家具資料庫手動加入。
  if ((room?.type || room?.room_type) === "bathroom") return [];
  const recommended = applyVisualPreferencesToSpecs(
    recommendedFurnitureForRoom(room),
    visualPreferencesForRoom(room),
  );
  const usageSpecs = ensureRoomUsage(room).flatMap(
    (usage) => ROOM_USAGE_FURNITURE_SPECS[usage] || [],
  );
  const preferenceSpecs = questionnairePreferenceFurnitureSpecs(room);
  const excluded = ROOM_TYPE_EXCLUDED_FURNITURE_TYPES[room?.type || room?.room_type] || [];
  const seen = new Set();
  return [...recommended, ...usageSpecs, ...preferenceSpecs].filter(([type, variant]) => {
    const key = `${type}:${variant || "standard"}`;
    if (!type || seen.has(key)) return false;
    if (excluded.includes(type)) return false;
    seen.add(key);
    return true;
  });
}

function roomUsageOptions(room) {
  return ROOM_USAGE_OPTIONS[room?.type] || ROOM_USAGE_OPTIONS.default;
}

function ensureRoomUsage(room) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return [];
  const available = roomUsageOptions(room);
  const availableIds = new Set(available.map((item) => item.id));
  const existing = Array.isArray(requirement.usage)
    ? requirement.usage.filter((item) => availableIds.has(item))
    : [];
  requirement.usage = existing.length ? existing : [available[0]?.id].filter(Boolean);
  return requirement.usage;
}

function renderQuestionnaireRoomUsage(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireRoomUsageOptions) return;
  const selected = new Set(ensureRoomUsage(room));
  const selectedCount = selected.size;
  element.questionnaireRoomUsageOptions.innerHTML = roomUsageOptions(room).map((option) => {
    const visual = roomUsageVisual(option.id);
    const isSelected = selected.has(option.id);
    const isPrimary = isSelected && [...selected][0] === option.id;
    return `
    <label class="rp-room-usage-card ${isSelected ? "is-selected" : ""} ${isPrimary ? "is-primary" : ""}" data-usage-tone="${escapeHtml(visual.tone)}">
      <input type="checkbox" data-questionnaire-room-usage="${escapeHtml(option.id)}"
        ${isSelected ? "checked" : ""}>
      <span class="rp-room-usage-card-media rp-room-usage-card-schematic" aria-hidden="true">
        <span class="rp-room-usage-card-schematic-grid"><i></i><i></i><i></i><i></i></span>
        <b>${escapeHtml(visual.symbol)}</b>
      </span>
      <span class="rp-room-usage-card-copy"><strong>${escapeHtml(option.label)}</strong><small>${escapeHtml(visual.caption)}</small></span>
      <span class="rp-room-usage-card-state" aria-hidden="true">${isSelected ? '<span class="rp-room-usage-card-check">✓</span>' : ""}${isPrimary ? '<span class="rp-room-usage-card-label">主要</span>' : ""}</span>
    </label>`;
  }).join("");
  element.questionnaireRoomUsageOptions.dataset.selectionCount = String(selectedCount);
}

function roomFurnitureRequirement(roomId) {
  const requirement = state.roomRequirementModel.roomRequirements[roomId];
  if (!requirement) return null;
  requirement.furniture = {
    required: [],
    optional: [],
    selected: [],
    deferred: [],
    ...(requirement.furniture || {}),
  };
  return requirement.furniture;
}

function questionnaireFurnitureSelectionItem(offer, selectionPriority) {
  return {
    furniture_id: offer.furniture_id,
    normalized_type: offer.normalized_type,
    variant_id: offer.variant_id || "standard",
    name_zh: offer.name_zh || offer.name_zh_raw || offer.name_en,
    name_zh_raw: offer.name_zh_raw || offer.name_zh || offer.name_en,
    name_en: offer.name_en || "",
    model_url: offer.model_url,
    image_url: offer.image_url || offer.thumbnail_url || offer.preview_url || offer.main_image_url || offer.image || null,
    thumbnail_url: offer.thumbnail_url || null,
    preview_url: offer.preview_url || null,
    size_cm: { ...(offer.size_cm || {}) },
    primary_style: offer.primary_style || null,
    color: offer.color || null,
    material: offer.material || null,
    reason: offer.reason || "使用者於逐房問卷勾選",
    selection_source: "questionnaire_user_selection",
    user_selected: true,
    selection_priority: selectionPriority,
    count: 1,
  };
}

function questionnaireOfferMatchesRequestedType(offer) {
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[offer?.normalized_type];
  if (!rule?.keywords?.length) return true;
  const description = [
    offer.name_zh,
    offer.name_zh_raw,
    offer.name_en,
    offer.category_label,
    offer.taxonomy_type_zh,
  ].filter(Boolean).join(" ").toLowerCase();
  return rule.keywords.some((keyword) => description.includes(keyword.toLowerCase()));
}

function questionnaireFurnitureDisplayName(offer) {
  const name = offer.name_zh || offer.name_zh_raw || offer.name_en || offer.normalized_type;
  const typeLabel = REPLACEMENT_TYPE_LABELS[offer.normalized_type];
  if (!typeLabel) return name;
  return name.replace(/^(床|桌子與書桌|椅子與長凳)\s*-\s*/, `${typeLabel} - `);
}

function questionnaireFurnitureOffers(room) {
  const recommended = state.roomFurnitureRecommendations[room.id] || [];
  const selected = roomFurnitureRequirement(room.id)?.selected || [];
  const byId = new Map(
    [...selected, ...recommended]
      .filter((item) => item?.furniture_id && questionnaireOfferMatchesRequestedType(item))
      .map((item) => [String(item.furniture_id), item]),
  );
  return [...byId.values()];
}

function questionnaireFurnitureSizeLabel(offer) {
  const size = offer?.size_cm || {};
  const width = Math.round(Number(size.width || 0));
  const depth = Math.round(Number(size.depth || 0));
  return width && depth ? `${width} × ${depth} cm` : "尺寸待確認";
}

function questionnaireFurnitureGroups(room, offers) {
  const selectedItems = roomFurnitureRequirement(room.id)?.selected || [];
  const groups = new Map();
  offers.forEach((offer) => {
    const type = String(offer.normalized_type || "other");
    const group = groups.get(type) || { type, offers: [] };
    group.offers.push(offer);
    groups.set(type, group);
  });
  return [...groups.values()].map((group) => {
    // The catalog and RAG may use different type labels for the same item.
    // Preserve the user's choice by the catalog's stable furniture_id instead.
    const selected = selectedItems.find((item) => group.offers.some(
      (offer) => String(offer.furniture_id) === String(item?.furniture_id),
    ));
    const active = group.offers.find((offer) => (
      String(offer.furniture_id) === String(selected?.furniture_id)
    )) || group.offers[0];
    return {
      ...group,
      active,
      selected,
      role: questionnaireFurnitureRole(room, active),
    };
  }).sort((left, right) => left.role.rank - right.role.rank || left.type.localeCompare(right.type));
}

// 型錄每一筆的 model_url 檔名都等於自己的 furniture_id，所以擺位 id／候選槽 id
// 蓋掉型錄 id 之後，GLB 檔名是唯一還認得出「這是哪一款」的線索。與後端
// main._price_lookup_keys() 同一套約定。
function catalogIdFromModelUrl(modelUrl) {
  const file = String(modelUrl || "").split(/[?#]/)[0].split("/").pop() || "";
  return file.replace(/\.(glb|gltf)$/i, "");
}

function catalogItemRenderable(item) {
  return Boolean(
    item?.model_url || item?.render_mode === "procedural_fixture" || item?.renderMode === "procedural_fixture"
  );
}

function catalogItemRenderKey(item) {
  return String(item?.model_url || `procedural:${item?.furniture_id || item?.id || "unknown"}`);
}

function knownUnavailableCatalogFurnitureIds() {
  const failedInstanceIds = new Set(
    (whiteViewer.getDiagnostics()?.failedFurniture || [])
      .map((item) => String(item.id)),
  );
  return new Set(
    (state.sceneData?.scene_objects || [])
      .filter((item) => failedInstanceIds.has(String(item.furniture_id)))
      // 只收 catalog_furniture_id 會整組空轉：它常是候選槽 id
      // （room-1-bed-double-candidate-1），與候選清單的真型錄 id 不同命名空間，
      // 載入失敗的 GLB 因此永遠排不掉、換幾次都被選回來。兩種都收才擋得住。
      .flatMap((item) => [
        item.catalog_furniture_id,
        catalogIdFromModelUrl(item.model_url),
      ])
      .map((value) => String(value || ""))
      .filter(Boolean),
  );
}

async function verifyQuestionnaireCatalogModel(offer) {
  if (offer?.render_mode === "procedural_fixture") return true;
  const modelUrl = String(offer?.model_url || "");
  if (!modelUrl || unavailableCatalogModelUrls.has(modelUrl)) return false;
  if (verifiedCatalogModelUrls.has(modelUrl)) return true;
  let available = false;
  glbThumbnailQueue.sequence = glbThumbnailQueue.sequence
    .catch(() => null)
    .then(async () => {
      try {
        await glbThumbnailViewer.loadScene(glbThumbnailScene(offer));
        available = !(glbThumbnailViewer.getDiagnostics()?.failedFurniture || []).length;
      } catch (error) {
        console.warn("Questionnaire GLB verification failed", error);
        available = false;
      }
      if (available) {
        verifiedCatalogModelUrls.add(modelUrl);
      } else {
        unavailableCatalogModelUrls.add(modelUrl);
      }
    });
  await glbThumbnailQueue.sequence;
  return available;
}

async function verifiedQuestionnaireCatalogOffers(offers, unavailableCatalogIds = new Set()) {
  const candidates = (offers || []).filter((offer) => (
    !unavailableCatalogIds.has(String(offer.furniture_id))
    && catalogItemRenderable(offer)
    && !unavailableCatalogModelUrls.has(catalogItemRenderKey(offer))
  ));
  const verified = [];
  for (const offer of candidates) {
    if (await verifyQuestionnaireCatalogModel(offer)) {
      verified.push(offer);
    }
  }
  return verified;
}

function renderQuestionnaireFurnitureRecommendations(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireFurnitureOptions) return;
  const furniture = roomFurnitureRequirement(room.id);
  const offers = questionnaireFurnitureOffers(room);
  const groups = questionnaireFurnitureGroups(room, offers);
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = furniture?.preferenceText || "";
  }
  renderQuestionnaireFurniturePreferenceTags(room);
  document.querySelectorAll("[data-open-questionnaire-furniture-catalog]").forEach((button) => {
    if (!button.closest(".rp-questionnaire-furniture")) return;
    button.dataset.openQuestionnaireFurnitureCatalog = String(room.id);
  });
  const loading = questionnaireFurnitureInFlight.has(String(room.id));
  const error = state.roomFurnitureRecommendationErrors[room.id];
  const expectedTypes = questionnaireFurnitureSpecsForRoom(room);
  if (loading && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      `正在從資料庫取得「${room.label}」適用家具…`;
    element.questionnaireFurnitureOptions.innerHTML =
      '<p class="rp-control-hint">正在比對房間用途、色卡、材質與尺寸。</p>';
    return;
  }
  if (error && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      "資料庫推薦暫時無法載入，請稍後重試。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<button type="button" class="secondary-action" data-retry-questionnaire-furniture="${escapeHtml(room.id)}">重新取得推薦</button>`;
    return;
  }
  if (!offers.length) {
    element.questionnaireFurnitureStatus.textContent = expectedTypes.length
      ? "暫時找不到可直接配置的 GLB；此需求會在第 6 步列為待處理，現在仍可繼續。"
      : "這個空間沒有預設家具需求，可直接確認其他設定。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<div class="rp-questionnaire-furniture-empty">
        <p class="rp-control-hint">此需求不會卡住問卷。第 6 步會說明缺少 GLB 或配置風險，並提供替代、替換或刪除選項。</p>
        <button type="button" class="secondary-action" data-open-questionnaire-furniture-catalog="${escapeHtml(room.id)}">開啟家具資料庫</button>
      </div>`;
    return;
  }
  const similarCount = offers.filter((offer) => offer.recommendation_tier === "similar").length;
  element.questionnaireFurnitureStatus.textContent =
    similarCount
      ? `已依需求預選家具；另有 ${similarCount} 件相近推薦可自行調整。`
      : `已依「${room.label}」預選推薦家具；可取消、換款或從家具庫增加。`;
  element.questionnaireFurnitureOptions.innerHTML = groups.map((group) => {
    const offer = group.active;
    const furnitureId = String(offer.furniture_id);
    const selected = Boolean(group.selected);
    const quantity = selected ? Math.max(1, Number(group.selected.count) || 1) : 0;
    const roomDimensionsValue = roomDimensions(room);
    const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
    const maximumQuantity = Math.max(1, Math.min(6, Math.floor(
      (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
    ) || 1));
    const shortLabel = questionnaireFurnitureDisplayLabel(offer);
    return `
      <article class="${selected ? "is-selected" : ""}">
        <label class="rp-questionnaire-furniture-select">
          <input type="checkbox" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}"
            ${selected ? "checked" : ""}>
          ${questionnaireFurniturePreviewMarkup(offer)}
          <span>
            ${group.role?.label ? `<small class="rp-questionnaire-furniture-purpose">對應用途：${escapeHtml(group.role.label)}</small>` : ""}
            <strong>${escapeHtml(shortLabel)}</strong>
            <small>${escapeHtml(questionnaireFurnitureSizeLabel(offer))}</small>
            <small class="rp-questionnaire-furniture-reason">${escapeHtml(offer.reason || group.role?.label || "依本房用途與尺寸建議")}</small>
          </span>
        </label>
        <div class="rp-questionnaire-furniture-card-actions">
          <label class="rp-questionnaire-furniture-size">
            <span>尺寸</span>
            <select data-questionnaire-furniture-variant-type="${escapeHtml(group.type)}">
              ${group.offers.map((candidate, index) => `
                <option value="${escapeHtml(candidate.furniture_id)}" ${String(candidate.furniture_id) === furnitureId ? "selected" : ""}>
                  ${escapeHtml(questionnaireFurnitureDisplayLabel(candidate))} · ${escapeHtml(questionnaireFurnitureSizeLabel(candidate))}${index ? `（款式 ${index + 1}）` : ""}
                </option>
              `).join("")}
            </select>
          </label>
          <div class="rp-furniture-quantity" aria-label="${escapeHtml(shortLabel)} 數量">
            <button type="button" data-questionnaire-furniture-quantity="-1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${quantity === 0 ? "disabled" : ""} aria-label="減少 ${escapeHtml(shortLabel)} 數量">-</button>
            <output aria-live="polite">${quantity}</output>
            <button type="button" data-questionnaire-furniture-quantity="1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${quantity >= maximumQuantity ? "disabled" : ""} aria-label="增加 ${escapeHtml(shortLabel)} 數量">+</button>
          </div>
          <small class="rp-furniture-quantity-limit">最多 ${maximumQuantity} 件</small>
          ${offer.room_fit_checked === false ? '<small class="rp-questionnaire-fit-risk">尺寸僅為初步估計，第 6 步將檢查實際 GLB、門窗與走道。</small>' : ''}
        </div>
      </article>
    `;
  }).join("");
  // The option cards are rebuilt after every selection. Bind the steppers to
  // these fresh controls instead of relying only on the page-level delegate.
  // This keeps + / - usable after a room switch or recommendation refresh.
  element.questionnaireFurnitureOptions
    .querySelectorAll("button[data-questionnaire-furniture-quantity]")
    .forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        updateQuestionnaireFurnitureQuantity(
          button.dataset.questionnaireFurnitureId,
          Number(button.dataset.questionnaireFurnitureQuantity),
          room.id,
        );
      });
    });
  element.questionnaireFurnitureOptions.dataset.furnitureControlsBound = "true";
}

function applyDefaultQuestionnaireFurnitureSelections(room, offers) {
  const furniture = roomFurnitureRequirement(room.id);
  if (!furniture || furniture.selected?.length || !offers.length) return;
  const program = questionnaireFurnitureProgram(room);
  const preferredDefaults = program.defaults.map((type) => offers.find((offer) => (
    // 用 keyword/family 比對而非精確 normalized_type:電視櫃的候選常是 tv-media-furniture
    // 等(family=tv-bench),精確比對會漏掉 → 客廳選不到電視櫃。
    offer.normalized_type === type || isQuestionnaireFallbackTypeMatch(offer, type)
  ))).filter(Boolean);
  const defaults = preferredDefaults.length
    ? preferredDefaults
    : (program.fallbackDefaults || []).map((type) => offers.find((offer) => (
      offer.normalized_type === type && offer.room_fit_checked !== false
    ))).filter(Boolean);
  if (!defaults.length) return;
  furniture.selected = defaults.map((offer, index) => ({
    ...questionnaireFurnitureSelectionItem(offer, index + 1),
    default_recommendation: true,
    selection_source: preferredDefaults.length
      ? "questionnaire_rag_recommendation"
      : "questionnaire_catalog_fallback",
  }));
  furniture.required = [...new Set(defaults.map((offer) => offer.normalized_type))];
  furniture.optional = offers
    .filter((offer) => !defaults.some((selected) => String(selected.furniture_id) === String(offer.furniture_id)))
    .map((offer) => offer.normalized_type);
}

async function ensureQuestionnaireFurnitureRecommendations(
  room = activeQuestionnaireRoom(),
  { force = false } = {},
) {
  if (!room) return;
  const roomId = String(room.id);
  if (!force && state.roomFurnitureRecommendations[room.id]) return;
  if (questionnaireFurnitureInFlight.has(roomId)) return;
  questionnaireFurnitureInFlight.add(roomId);
  delete state.roomFurnitureRecommendationErrors[room.id];
  renderQuestionnaireFurnitureRecommendations(room);
  try {
    const specs = questionnaireFurnitureSpecsForRoom(room);
    const remembered = roomFurnitureRequirement(room.id);
    if (remembered?.selected?.length) {
      remembered.selected = remembered.selected.filter(questionnaireOfferMatchesRequestedType);
      remembered.required = [...new Set(
        remembered.selected.map((item) => item.normalized_type),
      )];
    }
    const unavailableCatalogIds = knownUnavailableCatalogFurnitureIds();
    const groups = await Promise.all(specs.map(async (spec, index) => {
      let offers = await catalogOffersForSpec(room, spec, index);
      if (!offers.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
      }
      let candidates = await verifiedQuestionnaireCatalogOffers(offers, unavailableCatalogIds);
      if (!candidates.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
        candidates = await verifiedQuestionnaireCatalogOffers(offers, unavailableCatalogIds);
      }
      const fittingCandidates = candidates.filter((offer) => replacementCandidateFitsRoom(offer, room));
      return questionnaireOffersWithSizeChoices(spec[0], candidates).map((offer) => ({
        ...offer,
        room_fit_checked: fittingCandidates.includes(offer),
        model_load_verified: true,
        model_load_verification: "verified",
      }));
    }));
    let recommendedOffers = groups.flat();
    const program = questionnaireFurnitureProgram(room);
    // 基礎件保證有候選:客廳沙發組的茶几/電視櫃是「用途相依」specs(沒勾「看電視」
    // 就不產生電視櫃 offer),導致基礎件缺候選、applyDefaults 選不到 → 只剩單椅。
    // 這裡為每個缺候選的基礎件補建(與下方 fallback 同法、同樣經房型尺寸過濾,
    // 放不下就不補,不會硬塞小房)。以基礎件優先。
    const missingDefaults = (program.defaults || []).filter((type) => (
      !recommendedOffers.some((offer) => offer.normalized_type === type && offer.room_fit_checked !== false)
    ));
    if (missingDefaults.length) {
      const defaultGroups = await Promise.all(missingDefaults.map(async (type, index) => {
        let offers = await catalogOffersForSpec(room, [type, "standard"], specs.length + index);
        if (!offers.length) {
          offers = await catalogFallbackOffersForSpec(room, [type, "standard"], specs.length + index);
        }
        const candidates = (await verifiedQuestionnaireCatalogOffers(
          offers,
          unavailableCatalogIds,
        )).filter((offer) => replacementCandidateFitsRoom(offer, room));
        return questionnaireOffersWithSizeChoices(type, candidates).map((offer) => ({
          ...offer,
          room_fit_checked: true,
          model_load_verified: true,
          model_load_verification: "verified",
        }));
      }));
      recommendedOffers = [...recommendedOffers, ...defaultGroups.flat()];
    }
    const hasPreferredDefault = program.defaults.some((type) => (
      recommendedOffers.some((offer) => offer.normalized_type === type && offer.room_fit_checked !== false)
    ));
    if (!hasPreferredDefault && (program.fallbackDefaults || []).length) {
      const fallbackGroups = await Promise.all(program.fallbackDefaults.map(async (type, index) => {
        let offers = await catalogOffersForSpec(room, [type, "standard"], specs.length + index);
        if (!offers.length) {
          offers = await catalogFallbackOffersForSpec(room, [type, "standard"], specs.length + index);
        }
        const candidates = (await verifiedQuestionnaireCatalogOffers(
          offers,
          unavailableCatalogIds,
        )).filter((offer) => replacementCandidateFitsRoom(offer, room));
        return questionnaireOffersWithSizeChoices(type, candidates).map((offer) => ({
          ...offer,
          room_fit_checked: true,
          model_load_verified: true,
          model_load_verification: "verified",
        }));
      }));
      recommendedOffers = [...recommendedOffers, ...fallbackGroups.flat()];
    }
    state.roomFurnitureRecommendations[room.id] = recommendedOffers;
    applyDefaultQuestionnaireFurnitureSelections(
      room,
      state.roomFurnitureRecommendations[room.id],
    );
  } catch (error) {
    console.warn("Questionnaire furniture recommendations", error);
    state.roomFurnitureRecommendationErrors[room.id] = errorMessage(error);
  } finally {
    questionnaireFurnitureInFlight.delete(roomId);
    if (String(activeQuestionnaireRoom()?.id) === roomId) {
      renderQuestionnaireFurnitureRecommendations(room);
    }
  }
}

function captureQuestionnaireFurniturePreference(room = activeQuestionnaireRoom()) {
  const furniture = roomFurnitureRequirement(room?.id);
  if (!furniture || !element.questionnaireFurniturePreference) return;
  furniture.preferenceText = element.questionnaireFurniturePreference.value.trim();
}

function updateQuestionnaireFurnitureSelection(furnitureId, selected) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const next = (furniture.selected || []).filter(
    (item) => String(item.furniture_id) !== String(furnitureId),
  );
  if (selected) {
    next.push(questionnaireFurnitureSelectionItem(offer, next.length + 1));
  }
  furniture.selected = next.map((item, index) => ({
    ...item,
    user_selected: true,
    selection_priority: index + 1,
  }));
  furniture.required = [...new Set(
    furniture.selected.map((item) => item.normalized_type),
  )];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some(
      (selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id),
    ))
    .map((item) => item.normalized_type);
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  requirement.confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  invalidateDownstreamFrom(
    "requirements",
    `「${room.label}」的家具需求已修改，第 6 步需要重新產生。`,
  );
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureVariant(normalizedType, furnitureId) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const previous = (furniture.selected || []).find(
    (item) => String(item.normalized_type) === String(normalizedType),
  );
  const next = (furniture.selected || []).filter(
    (item) => String(item.normalized_type) !== String(normalizedType),
  );
  next.push({
    ...questionnaireFurnitureSelectionItem(offer, next.length + 1),
    count: Math.max(1, Number(previous?.count) || 1),
    user_selected: true,
  });
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已更新 ${room.label} 的家具尺寸，第 6 步需要重新建立配置。`);
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureQuantity(furnitureId, delta, roomId = null) {
  const room = roomId
    ? state.rooms.find((candidate) => String(candidate.id) === String(roomId))
    : activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !delta) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const selected = furniture.selected || [];
  const existing = selected.find((item) => String(item.furniture_id) === String(furnitureId));
  // Older saved questionnaire selections predate the count field.  A selected
  // item without it is one item, rather than an empty selection.
  const current = existing ? Math.max(1, Number(existing.count) || 1) : 0;
  const roomDimensionsValue = roomDimensions(room);
  const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
  const maximum = Math.max(1, Math.min(6, Math.floor(
    (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
  ) || 1));
  const nextCount = Math.max(0, Math.min(maximum, current + Number(delta)));
  if (nextCount === current) {
    setStatus(`「${questionnaireFurnitureDisplayName(offer)}」依本房可用面積最多可先選 ${maximum} 件。`);
    return;
  }
  const next = selected.filter((item) => String(item.furniture_id) !== String(furnitureId));
  if (nextCount > 0) {
    next.push({
      ...(existing || questionnaireFurnitureSelectionItem(offer, next.length + 1)),
      count: nextCount,
      user_selected: true,
    });
  }
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some((selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id)))
    .map((item) => item.normalized_type);
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `「${room.label}」的家具數量已修改，第 6 步需要重新產生。`);
  scheduleSave("requirements");
}

function refreshQuestionnaireFurnitureRecommendations() {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  delete state.roomFurnitureRecommendations[room.id];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  invalidateDownstreamFrom("requirements", `已更新「${room.label}」的家具偏好，第 6 步需要重新產生。`);
  scheduleSave("requirements");
  void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
}

function specsFromSelectionResponse(room, response, fallbackSpecs) {
  const selectedRoom = (response.rooms || []).find(
    (item) => String(item.room_id) === String(room.id),
  );
  if (!selectedRoom?.items?.length) return fallbackSpecs;
  const availableByType = new Map();
  selectedRoom.items.forEach((item) => {
    const type = String(item.normalized_type || "").trim();
    if (!type) return;
    const entries = availableByType.get(type) || [];
    const count = Math.max(1, Math.min(6, Number(item.count) || 1));
    for (let index = 0; index < count; index += 1) entries.push(item);
    availableByType.set(type, entries);
  });

  // RAG can replace a requested item with a better catalog match, but it must
  // never add new furniture types or quantities beyond the questionnaire.
  return fallbackSpecs.map(([type, variant, reason, autoAdded, catalogItem]) => {
    // Once the user confirms a concrete catalog item in the questionnaire,
    // its ID and verified GLB are authoritative for the generated schemes.
    // The Agent may still place it, but must not silently swap it for another
    // item of the same type (or for an incomplete catalog record).
    if (
      catalogItem?.user_selected === true
      && catalogItem?.furniture_id
      && catalogItemRenderable(catalogItem)
    ) {
      return [type, variant, reason, autoAdded, catalogItem];
    }
    const entries = availableByType.get(type);
    const matched = entries?.shift();
    if (!matched) return [type, variant, reason, autoAdded, catalogItem];
    const resolvedCatalogItem = {
      ...(catalogItem || {}),
      ...matched,
      furniture_id: matched.furniture_id || catalogItem?.furniture_id,
      model_url: matched.model_url || catalogItem?.model_url,
      render_mode: matched.render_mode || catalogItem?.render_mode,
      size_cm: matched.size_cm || catalogItem?.size_cm,
    };
    return [
      type,
      matched.variant_id || matched.variantId || variant || "standard",
      matched.reason || matched.match_reason || matched.selection_source || response.source || reason,
      false,
      resolvedCatalogItem,
    ];
  });
}

function specsAllowedByRoomFeasibility(requirement, specs) {
  const blocked = new Set(
    (requirement?.feasibility || [])
      .filter((item) => item.forcePlacement === false)
      .map((item) => item.optionId),
  );
  return specs.filter(([type, variant]) => {
    const normalized = `${type} ${variant}`.toLowerCase();
    if (blocked.has("bathtub") && normalized.includes("bathtub")) return false;
    if (blocked.has("double_vanity") && (
      normalized.includes("double-vanity")
      || normalized.includes("double_vanity")
    )) return false;
    if (blocked.has("large_dining_table") && (
      normalized.includes("large-dining")
      || normalized.includes("large_dining")
      || normalized.includes("rect-6")
      || normalized.includes("six-seat")
    )) return false;
    return true;
  });
}

  return {
    applyDefaultQuestionnaireFurnitureSelections,
    captureQuestionnaireFurniturePreference,
    catalogCandidatesForType,
    catalogFallbackOffersForSpec,
    catalogIdFromModelUrl,
    catalogItemRenderable,
    catalogItemRenderKey,
    catalogOffersForRoomPlans,
    catalogOffersForSpec,
    ensureQuestionnaireFurnitureRecommendations,
    ensureRoomUsage,
    furniture2dDefaultsForSceneObject,
    furnitureOfferFromSpec,
    knownUnavailableCatalogFurnitureIds,
    planCenterCm,
    questionnaireBedSizeFamily,
    questionnaireFurnitureDisplayLabel,
    questionnaireFurnitureDisplayName,
    questionnaireFurnitureGroups,
    questionnaireFurnitureOffers,
    questionnaireFurniturePreferenceTags,
    questionnaireFurnitureProgram,
    questionnaireFurnitureRequest,
    questionnaireFurnitureRole,
    questionnaireFurnitureSelectionItem,
    questionnaireFurnitureSizeLabel,
    questionnaireFurnitureSpecsForRoom,
    questionnaireOfferMatchesRequestedType,
    questionnaireOffersWithSizeChoices,
    questionnairePackForRoom,
    questionnairePreferenceFurnitureSpecs,
    refreshQuestionnaireFurnitureRecommendations,
    renderQuestionnaireFurniturePreferenceTags,
    renderQuestionnaireFurnitureRecommendations,
    renderQuestionnaireRoomUsage,
    roomFurnitureRequirement,
    roomIdForScenePosition,
    roomSurfaceAssignments,
    roomUsageOptions,
    scenePositionInsideRoom,
    specsAllowedByRoomFeasibility,
    specsFromSelectionResponse,
    toggleQuestionnaireFurniturePreferenceTag,
    updateQuestionnaireFurnitureQuantity,
    updateQuestionnaireFurnitureSelection,
    updateQuestionnaireFurnitureVariant,
    verifiedQuestionnaireCatalogOffers,
    verifyQuestionnaireCatalogModel,
  };
}
