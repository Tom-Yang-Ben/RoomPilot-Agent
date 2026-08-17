// Step 5 whole-house and per-room questionnaire, materials, and confirmation workflow.
export function createSceneQuestionnaireController({
  $,
  $$,
  api,
  applyRoomFinishScope,
  applyVerifiedRandomQuestionnaireFurniture,
  autoLayoutFurniture,
  beginPlacementBusy,
  buildRoomRequirementsPayload,
  CEILING_DESIGN_PACKS,
  CEILING_STYLES,
  cmToPixel,
  element,
  endPlacementBusy,
  ensureQuestionnaireFurnitureRecommendations,
  ensureRoomUsage,
  errorMessage,
  escapeHtml,
  evaluateConditionalOption,
  finishesGate,
  generateWhiteModelFromRequirements,
  invalidateDownstreamFrom,
  LIGHT_STYLES,
  normalizeRoomRequirements,
  planGeometry,
  previewStepSixRoomSurfaces,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureProgram,
  questionnaireRuntimeState,
  questionnaireSummary,
  renderFurnitureLibrary,
  renderGenerativeEquipment,
  renderMaterialPairPreviews,
  renderQuestionnaireFurnitureRecommendations,
  renderQuestionnaireRoomUsage,
  roomCenter,
  roomFurnitureRequirement,
  roomPolygonSvg,
  roomUsageOptions,
  scheduleSave,
  setStatus,
  settleQuestionnaireRagForLayout,
  startQuestionnaireRag,
  state,
  STYLE_FAMILIES,
  STYLE_PACKS,
  stylePackByIdSafe,
  syncOverlayToImage,
  WHOLE_HOUSE_QUESTIONS,
}) {
const QUESTIONNAIRE_STAGES = Object.freeze([
  "profile",
  "rooms",
  "summary",
]);

const ROOM_REQUIREMENT_POLAR_AXES = Object.freeze({
  living_room: [
    { axis: "use", left: "獨處放鬆", right: "多人社交" },
    { axis: "lighting", left: "柔和間接光", right: "明亮主燈" },
  ],
  bedroom: [
    { axis: "use", left: "深度睡眠", right: "工作收納" },
    { axis: "atmosphere", left: "安靜包覆", right: "清爽明亮" },
  ],
  kitchen: [
    { axis: "use", left: "快速備餐", right: "聚餐烹飪" },
    { axis: "lighting", left: "餐吊燈", right: "均勻工作光" },
  ],
  bathroom: [
    { axis: "use", left: "快速乾濕分離", right: "泡澡放鬆" },
    { axis: "maintenance", left: "低維護", right: "飯店感" },
  ],
  storage: [
    { axis: "use", left: "專注工作", right: "彈性閱讀" },
    { axis: "lighting", left: "防眩任務光", right: "展示氛圍光" },
  ],
  balcony: [
    { axis: "use", left: "洗曬機能", right: "休憩植栽" },
    { axis: "storage", left: "完全收納", right: "開放展示" },
  ],
  entryway: [
    { axis: "use", left: "快速出入", right: "完整落塵收納" },
    { axis: "lighting", left: "感應安全光", right: "端景展示光" },
  ],
  hallway: [
    { axis: "use", left: "保持通行", right: "增加收納" },
    { axis: "lighting", left: "感應安全光", right: "端景展示光" },
  ],
  garage: [
    { axis: "use", left: "停車淨空", right: "工具收納" },
    { axis: "lighting", left: "安全照明", right: "工作照明" },
  ],
  default: [
    { axis: "use", left: "極簡留白", right: "高機能收納" },
    { axis: "atmosphere", left: "安靜低調", right: "明亮展示" },
  ],
});

const TEST_REQUIREMENT_PROFILE_NOTES = Object.freeze([
  "測試需求：偏低維護、好整理、保留寬走道。",
  "測試需求：偏展示感、材質層次明顯、照明要有重點。",
  "測試需求：偏高收納、家具要實用、動線不能被堵住。",
  "測試需求：偏放鬆舒適、光線柔和、少尖角。",
]);

const TEST_AIR_CONDITIONING_OPTIONS = Object.freeze([
  "wall-split",
  "ceiling-cassette",
  "ducted",
  "none",
]);

const QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT = 4;
const INDEPENDENT_FLOOR_ROOM_TYPES = new Set([
  "bathroom",
  "kitchen",
  "entryway",
  "balcony",
  "laundry",
  "utility",
]);
const INDEPENDENT_FLOOR_LABEL_PATTERNS = [
  "浴",
  "廁",
  "衛",
  "廚",
  "玄關",
  "陽台",
  "洗衣",
  "家務",
];

const PREFERENCE_WEIGHT_OPTIONS = Object.freeze([
  { value: -2, label: "強偏 A" },
  { value: -1, label: "偏 A" },
  { value: 0, label: "平衡" },
  { value: 1, label: "偏 B" },
  { value: 2, label: "強偏 B" },
]);

function randomItem(items, fallback = null) {
  const candidates = (items || []).filter(Boolean);
  if (!candidates.length) return fallback;
  return candidates[Math.floor(Math.random() * candidates.length)];
}

function roomAllowsIndependentFloor(room = {}) {
  const type = String(room.type || room.room_type || "").toLowerCase();
  const label = String(room.label || room.name || "");
  return INDEPENDENT_FLOOR_ROOM_TYPES.has(type)
    || INDEPENDENT_FLOOR_LABEL_PATTERNS.some((pattern) => label.includes(pattern));
}

function trimAccentWallSurfaces(surfaces = {}) {
  return {
    ...surfaces,
    // Step 5 provides a whole-house wall finish.  Per-wall accents are not
    // carried into Step 6 unless a future explicit room override is added.
    wallSurfaceIds: [],
    wallOverrides: {},
  };
}

function isCirculationRoom(room = {}) {
  const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
  const label = String(room.label || room.name || "");
  return type === "hallway" || /走道|動線/.test(label);
}

function livingRoomForCirculation() {
  return state.rooms.find((room) => {
    const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
    return type === "living_room" || /客廳/.test(String(room.label || room.name || ""));
  }) || null;
}

function circulationStyleIsOverridden(room = {}) {
  return Boolean(
    state.roomRequirementModel?.roomRequirements?.[room.id]?.circulationStyleOverrideApproved,
  );
}

function copyLivingRoomStyleToCirculation(room, { force = false } = {}) {
  if (!isCirculationRoom(room)) return false;
  const livingRoom = livingRoomForCirculation();
  if (!livingRoom || livingRoom.id === room.id) return false;
  const requirements = state.roomRequirementModel?.roomRequirements || {};
  const requirement = requirements[room.id];
  const livingRequirement = requirements[livingRoom.id];
  if (!requirement || !livingRequirement || (!force && circulationStyleIsOverridden(room))) return false;
  const livingDraft = state.roomFinishDrafts?.[livingRoom.id];
  if (livingDraft) {
    state.roomFinishDrafts[room.id] = {
      ...livingDraft,
      wallOverrides: {},
      confirmed: state.roomFinishDrafts?.[room.id]?.confirmed || false,
    };
  }
  requirement.surfaces = trimAccentWallSurfaces({
    ...(livingRequirement.surfaces || {}),
  });
  requirement.climate = { ...(livingRequirement.climate || {}) };
  requirement.circulationStyleSourceRoomId = livingRoom.id;
  return true;
}

function synchronizeCirculationStyles() {
  state.rooms.filter(isCirculationRoom).forEach((room) => {
    copyLivingRoomStyleToCirculation(room);
  });
}

function wholeHouseMainFloorSurface() {
  const dryRoomFloor = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) =>
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.floor
    )
    .find((floor) => floor?.materialId || floor?.color);
  if (dryRoomFloor) return { ...dryRoomFloor };
  if (state.questionnaireFinishes.floorMaterial || state.questionnaireFinishes.floorColor) {
    return {
      materialId: state.questionnaireFinishes.floorMaterial || null,
      color: state.questionnaireFinishes.floorColor || null,
    };
  }
  return null;
}

function wholeHouseMainWallSurface() {
  const configured = state.questionnaireFinishes || {};
  if (configured.wallMaterial || configured.wallColor) {
    return {
      materialId: configured.wallMaterial || configured.defaultWallMaterial || null,
      color: configured.wallColor || configured.defaultWallColor || null,
    };
  }
  const dryRoomWall = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) => state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.wallDefault)
    .find((wall) => wall?.materialId || wall?.color);
  return dryRoomWall ? { ...dryRoomWall } : null;
}


function normalizedRoomSurfaces(room, surfaces = {}) {
  const next = trimAccentWallSurfaces(surfaces);
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  if (mainWall && !next.wallDefault?.materialId && !next.wallDefault?.color) {
    next.wallDefault = { ...mainWall };
  }
  if (mainFloor && !next.floor?.materialId && !next.floor?.color) {
    next.floor = { ...mainFloor };
  }
  return next;
}

function applyWholeHouseSurfaceConsistency() {
  synchronizeCirculationStyles();
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  Object.entries(state.roomRequirementModel?.roomRequirements || {}).forEach(([roomId, requirement]) => {
    requirement.surfaces = trimAccentWallSurfaces(requirement.surfaces || {});
    if (mainWall && !requirement.surfaces.wallDefault?.materialId && !requirement.surfaces.wallDefault?.color) {
      requirement.surfaces.wallDefault = { ...mainWall };
    }
    if (mainFloor && !requirement.surfaces.floor?.materialId && !requirement.surfaces.floor?.color) {
      requirement.surfaces.floor = { ...mainFloor };
    }
  });
}

function normalizeSavedSceneWallSurfaces(sceneData) {
  if (!sceneData?.surface_overrides?.length) return 0;
  let repaired = 0;
  sceneData.surface_overrides.forEach((override) => {
    const hasRoomWall = Boolean(override.wall_option || override.wall_color_hex);
    if (hasRoomWall && override.wallOverrideExplicit !== true) {
      override.wallOverrideExplicit = true;
      repaired += 1;
    }
  });
  return repaired;
}

function stableStringNumber(value = "") {
  return String(value).split("").reduce(
    (total, char, index) => total + char.charCodeAt(0) * (index + 1),
    0,
  );
}

function materialOptionForPack(option, pack) {
  return {
    ...option,
    // The catalog record owns the swatch, color, and material wording.
    note: option.note,
    recommendation: pack.name,
  };
}

function materialCatalogText(surface) {
  return [
    surface.surface_id,
    surface.name_zh,
    surface.preview_url,
    surface.texture_url,
  ].filter(Boolean).join(" ").toLowerCase();
}

function catalogSurfaceIsUsableInRoom(kind, surface) {
  const text = materialCatalogText(surface);
  if (kind === "floor") {
    // Import folders contain bark, wallpaper, wicker, and ground studies. They are
    // legitimate textures, but not products that can honestly be offered as floors.
    return !/(?:bark|wallpaper|wicker|ground)/.test(text);
  }
  return !/(?:bark|wallpaper|wicker|ground)/.test(text);
}

function userFacingMaterialLabel(surface) {
  return String(surface.visual_profile?.label_zh || "紋理待確認").trim();
}

function materialVisualTags(surface) {
  const tags = surface.visual_profile?.tags;
  return Array.isArray(tags) && tags.length === 3
    ? tags.map((tag) => String(tag).trim()).filter(Boolean)
    : ["待確認"];
}

function materialVisualTagMarkup(tags) {
  return `<span class="rp-material-visual-tags">${(tags || []).map((tag) =>
    `<em>${escapeHtml(tag)}</em>`,
  ).join("")}</span>`;
}

function addMaterialDisplayOrdinals(options) {
  return options;
}

function catalogMaterialOptionsForPack(kind, pack) {
  const usage = kind === "wall" ? "wall" : "floor";
  const catalog = state.surfaceCatalog || state.sceneData?.surface_catalog || {};
  const surfaces = (catalog.surfaces || [])
    .filter((surface) => Array.isArray(surface.usage) && surface.usage.includes(usage))
    .filter((surface) => surface.surface_id && surface.preview_url && surface.texture_url)
    .filter((surface) => catalogSurfaceIsUsableInRoom(kind, surface))
    .map((surface) => ({
      id: surface.surface_id,
      label: userFacingMaterialLabel(surface),
      color: surface.visual_profile?.primary_hex || surface.color_hex || "#d5d0c7",
      materialPreview: surface.preview_url,
      textureUrl: surface.texture_url,
      materialGroup: surface.material_group || surface.category || "材質",
      visualTags: materialVisualTags(surface),
      searchText: [
        surface.surface_id,
        surface.name_zh,
        surface.material_group,
        surface.category,
        ...(surface.visual_profile?.tags || []),
      ].filter(Boolean).join(" ").toLowerCase(),
      source: "catalog",
      suitable: (surface.suitable_styles || []).includes(pack.styleId),
    }));
  const sorted = surfaces.sort((left, right) => {
    if (left.suitable !== right.suitable) return left.suitable ? -1 : 1;
    return stableStringNumber(`${pack.id}:${left.id}`) - stableStringNumber(`${pack.id}:${right.id}`);
  });
  return addMaterialDisplayOrdinals(sorted).map((option) => materialOptionForPack({
    ...option,
    note: [...option.visualTags, option.materialGroup].join("・"),
  }, pack));
}

function questionnaireMaterialOptionsForPack(kind, pack) {
  return styleCompatibleMaterialOptionsForPack(kind, pack)
    .slice(0, QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT);
}

function materialCatalogType(option) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  if (/木|wood|oak|walnut|plank/.test(text)) return "wood";
  if (/磚|tile|marble|stone|石/.test(text)) return "stone";
  if (/水泥|cement|concrete/.test(text)) return "cement";
  return "paint";
}

function materialCatalogColor(option) {
  const hex = String(option.color || "#d5d0c7").replace("#", "");
  const value = Number.parseInt(hex.length === 3 ? hex.split("").map((part) => part + part).join("") : hex, 16);
  const red = value >> 16;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  const lightness = (red + green + blue) / 3;
  if (lightness < 105) return "dark";
  if (Math.max(red, green, blue) - Math.min(red, green, blue) < 24) return "gray";
  if (red > blue + 14) return "warm";
  return "light";
}

function materialCatalogChroma(option) {
  const hex = String(option.color || "#d5d0c7").replace("#", "");
  const value = Number.parseInt(hex.length === 3 ? hex.split("").map((part) => part + part).join("") : hex, 16);
  const red = value >> 16;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return Math.max(red, green, blue) - Math.min(red, green, blue);
}

function isHighChromaMaterial(option) {
  return materialCatalogChroma(option) >= 52;
}

const MATERIAL_TYPE_LABELS = Object.freeze({ all: "全部", wood: "木質", stone: "石材／磁磚", cement: "水泥", paint: "塗料" });
const MATERIAL_COLOR_LABELS = Object.freeze({ all: "全部", light: "淺色", warm: "暖色", gray: "灰色", dark: "深色" });

// Automatic recommendations are style-aware. The full catalog is still
// available for deliberate custom choices in the material picker.
const STYLE_MATERIAL_RULES = Object.freeze({
  scandinavian: { wall: ["paint", "cement"], floor: ["wood"], colors: ["light", "warm"] },
  japanese: { wall: ["paint", "cement"], floor: ["wood"], colors: ["light", "warm"] },
  modern_minimal: { wall: ["paint", "cement"], floor: ["wood", "stone", "cement"], colors: ["light", "gray"] },
  cream: { wall: ["paint", "cement"], floor: ["wood", "stone"], colors: ["light", "warm"] },
  industrial: { wall: ["paint", "cement"], floor: ["wood", "stone", "cement"], colors: ["gray", "dark"] },
  american: { wall: ["paint", "cement"], floor: ["wood"], colors: ["warm", "dark"] },
});

function isWetAreaRoom(room) {
  return ["bath", "bathroom", "kitchen"].includes(String(room?.type || room?.room_type || "").toLowerCase());
}

function isBathroomRoom(room) {
  return ["bath", "bathroom"].includes(String(room?.type || room?.room_type || "").toLowerCase());
}

function isPoolSurface(option) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  return /pool|swimming|泳池/.test(text);
}

function isMosaicSurface(option) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  return /mosaic|馬賽克/.test(text);
}

function styleCompatibleMaterialOptionsForPack(kind, pack, room = activeQuestionnaireRoom()) {
  const all = catalogMaterialOptionsForPack(kind, pack);
  const rule = STYLE_MATERIAL_RULES[pack.styleId];
  const wetArea = isWetAreaRoom(room);
  const bathroom = isBathroomRoom(room);
  const compatible = all.filter((option) => {
    if (isPoolSurface(option)) return false;
    if (isMosaicSurface(option) && !bathroom) return false;
    if (isHighChromaMaterial(option)) return false;
    const type = materialCatalogType(option);
    const color = materialCatalogColor(option);
    if (!wetArea && kind === "wall" && type === "stone") return false;
    if (!rule) return true;
    if (!rule[kind].includes(type)) return false;
    return rule.colors.includes(color);
  });
  const fallback = all.filter((option) =>
    !isPoolSurface(option)
      && (!isMosaicSurface(option) || bathroom)
      && !isHighChromaMaterial(option),
  );
  return (compatible.length ? compatible : fallback)
    .sort((left, right) => materialPairScore(kind, right, pack, room) - materialPairScore(kind, left, pack, room));
}

function renderMaterialFilterChips(host, labels, selected, countById, dataset) {
  host.innerHTML = Object.entries(labels).filter(([id]) => id === "all" || countById[id]).map(([id, label]) => `
    <button type="button" class="rp-filter-chip ${selected === id ? "is-active" : ""}" data-${dataset}="${id}" aria-pressed="${selected === id}">${label}${id === "all" ? "" : ` (${countById[id]})`}</button>
  `).join("");
}

function materialPairScore(kind, option, pack, room) {
  const text = `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase();
  let score = option.suitable ? 18 : 0;
  if (isHighChromaMaterial(option)) score -= 180;
  const rule = STYLE_MATERIAL_RULES[pack.styleId];
  if (rule?.colors.includes(materialCatalogColor(option))) score += 24;
  if (kind === "wall" && !["kitchen", "bathroom"].includes(room?.type) && /磚|tile|brick/.test(text)) score -= 100;
  if (kind === "wall" && /塗料|漆|plaster|limewash|礦物/.test(text)) score += 12;
  if (kind === "floor" && /木|wood|oak|walnut|石|stone|microcement|水泥/.test(text)) score += 10;
  score += stableStringNumber(`${pack.id}:${kind}:${option.id}`) / 100000;
  return score;
}

function questionnaireMaterialPairsForPack(pack, room = activeQuestionnaireRoom()) {
  const walls = styleCompatibleMaterialOptionsForPack("wall", pack, room)
    .slice(0, 4);
  const floors = styleCompatibleMaterialOptionsForPack("floor", pack, room)
    .slice(0, 4);
  return walls.flatMap((wall) => floors.map((floor) => ({
    wall,
    floor,
    score: materialPairScore("wall", wall, pack, room) + materialPairScore("floor", floor, pack, room),
  }))).sort((left, right) => right.score - left.score)
    .slice(0, 1);
}

function repairAutomaticMaterialRecommendation(room, draft, pack) {
  if (!room || !draft || draft.materialSelectionMode === "custom") return false;
  const compatibleWalls = styleCompatibleMaterialOptionsForPack("wall", pack, room);
  const compatibleFloors = styleCompatibleMaterialOptionsForPack("floor", pack, room);
  const wallIsCompatible = compatibleWalls.some((option) => option.id === draft.wallMaterial);
  const floorIsCompatible = compatibleFloors.some((option) => option.id === draft.floorMaterial);
  if (wallIsCompatible && floorIsCompatible) return false;
  const pair = questionnaireMaterialPairsForPack(pack, room)[0];
  if (!pair) return false;
  Object.assign(draft, {
    wallMaterial: pair.wall.id,
    wallColor: pair.wall.color,
    defaultWallMaterial: pair.wall.id,
    defaultWallColor: pair.wall.color,
    wallOverrides: {},
    floorMaterial: pair.floor.id,
    floorColor: pair.floor.color,
    materialSelectionMode: "auto",
    confirmed: false,
  });
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (requirement) {
    requirement.confirmed = false;
    requirement.surfaces = {
      ...requirement.surfaces,
      paletteId: pack.id,
      materialSelectionMode: "auto",
      wallDefault: { materialId: pair.wall.id, color: pair.wall.color },
      wallOverrides: {},
      floor: { materialId: pair.floor.id, color: pair.floor.color },
    };
  }
  return true;
}

function questionnaireMaterialPairCards(pack) {
  const draft = activeRoomFinishDraft();
  const selectedWall = catalogMaterialOptionsForPack("wall", pack)
    .find((option) => option.id === draft.wallMaterial);
  const selectedFloor = catalogMaterialOptionsForPack("floor", pack)
    .find((option) => option.id === draft.floorMaterial);
  const recommendations = questionnaireMaterialPairsForPack(pack);
  if (!selectedWall || !selectedFloor) return recommendations;
  const current = {
    wall: { ...selectedWall, color: draft.wallColor || selectedWall.color },
    floor: { ...selectedFloor, color: draft.floorColor || selectedFloor.color },
    isCurrentSelection: true,
  };
  const currentIsRecommended = recommendations.some((pair) => (
    pair.wall.id === current.wall.id && pair.floor.id === current.floor.id
  ));
  if (currentIsRecommended) {
    return [current, ...recommendations.filter((pair) => (
      pair.wall.id !== current.wall.id || pair.floor.id !== current.floor.id
    ))].slice(0, 1);
  }
  return [{ ...current, isCustomSelection: true }, ...recommendations].slice(0, 1);
}

function renderQuestionnaireMaterialPairs(pack) {
  const draft = activeRoomFinishDraft();
  const pairs = questionnaireMaterialPairCards(pack);
  const host = element.questionnaireMaterialPairs;
  if (!host) return pairs;
  host.hidden = false;
  host.innerHTML = `
    <div class="rp-questionnaire-section-heading"><div><span class="eyebrow">本房推薦</span><h3>牆與地板搭配</h3></div><p>這是依房型與全屋風格產生的一組預設搭配；需要調整時，再從下方材質庫選擇。</p></div>
    <div class="rp-material-pair-grid">${pairs.map((pair, index) => `
      <button type="button" class="rp-material-pair-card ${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id ? "is-active" : ""}"
        data-questionnaire-material-pair="${index}" aria-pressed="${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id}">
        <canvas data-material-pair-preview aria-label="${escapeHtml(`${pair.wall.label} 與 ${pair.floor.label} 的立體搭配預覽`)}"></canvas>
        <span><strong>牆：${escapeHtml(pair.wall.label)}</strong><small>地：${escapeHtml(pair.floor.label)}</small>${pair.isCurrentSelection ? "<em>目前選擇</em>" : ""}${pair.isCustomSelection ? "<em>自訂選擇</em>" : ""}</span>
      </button>
    `).join("") || "<p class=\"rp-field-error\">找不到可搭配的牆面與地板材質，可改用下方自訂選擇。</p>"}</div>`;
  if (pairs.length) requestAnimationFrame(() => renderMaterialPairPreviews(host, pairs));
  return pairs;
}

function selectQuestionnaireMaterialPair(pair) {
  const draft = activeRoomFinishDraft();
  draft.wallMaterial = pair.wall.id;
  draft.wallColor = pair.wall.color;
  draft.floorMaterial = pair.floor.id;
  draft.floorColor = pair.floor.color;
  if (state.selectedQuestionnaireWallId) {
    draft.wallOverrides[state.selectedQuestionnaireWallId] = { materialId: draft.wallMaterial, color: draft.wallColor };
  } else {
    draft.defaultWallMaterial = draft.wallMaterial;
    draft.defaultWallColor = draft.wallColor;
  }
  draft.confirmed = false;
  draft.materialSelectionMode = "custom";
  draft.styleReviewRequired = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function renderQuestionnaireMaterialCatalog(kind, search = questionnaireRuntimeState.materialCatalogSearch) {
  if (!element.questionnaireMaterialCatalogDialog) {
    setStatus("材質資料庫尚未載入完成，請重新整理後再試。", "error");
    return;
  }
  questionnaireRuntimeState.materialCatalogKind = kind;
  questionnaireRuntimeState.materialCatalogSearch = String(search || "").trim();
  const pack = activeQuestionnairePack();
  const allOptions = catalogMaterialOptionsForPack(kind, pack);
  const searchTerm = questionnaireRuntimeState.materialCatalogSearch.toLowerCase();
  const typeCounts = allOptions.reduce((counts, option) => ({ ...counts, [materialCatalogType(option)]: (counts[materialCatalogType(option)] || 0) + 1 }), {});
  const colorCounts = allOptions.reduce((counts, option) => ({ ...counts, [materialCatalogColor(option)]: (counts[materialCatalogColor(option)] || 0) + 1 }), {});
  const options = allOptions.filter((option) =>
    (questionnaireRuntimeState.materialCatalogType === "all" || materialCatalogType(option) === questionnaireRuntimeState.materialCatalogType)
    && (questionnaireRuntimeState.materialCatalogColor === "all" || materialCatalogColor(option) === questionnaireRuntimeState.materialCatalogColor)
    && (!searchTerm || `${option.label} ${option.note} ${option.searchText || ""}`.toLowerCase().includes(searchTerm)),
  );
  const title = kind === "wall" ? "選擇本房牆面材質" : "選擇本房地板材質";
  element.questionnaireMaterialCatalogSource.hidden = false;
  element.questionnaireMaterialCatalogSource.textContent = "本機材質資料庫";
  element.questionnaireMaterialCatalogTitle.textContent = title;
  element.questionnaireMaterialCatalogHelp.textContent = questionnaireRuntimeState.stepSixMaterialCatalogKind
    ? "選取後先更新目前房間草稿與 3D 預覽；按「確認此房間材質」才會正式鎖定。"
    : "選取後會更新目前房間的問卷草稿。";
  element.questionnaireMaterialCatalogSearch.value = questionnaireRuntimeState.materialCatalogSearch;
  renderMaterialFilterChips(element.questionnaireMaterialTypeFilters, MATERIAL_TYPE_LABELS, questionnaireRuntimeState.materialCatalogType, typeCounts, "questionnaire-material-type");
  renderMaterialFilterChips(element.questionnaireMaterialColorFilters, MATERIAL_COLOR_LABELS, questionnaireRuntimeState.materialCatalogColor, colorCounts, "questionnaire-material-color");
  element.questionnaireMaterialCatalogResultCount.textContent = searchTerm
    ? `找到 ${options.length} 項符合「${questionnaireRuntimeState.materialCatalogSearch}」的材質`
    : `共 ${allOptions.length} 項材質，可用關鍵字縮小範圍`;
  element.questionnaireMaterialCatalogOptions.innerHTML = options.map((option) => `
    <button type="button" data-questionnaire-catalog-material="${escapeHtml(kind)}"
      data-questionnaire-catalog-material-id="${escapeHtml(option.id)}">
      <span class="rp-material-catalog-sample">
        <img src="${escapeHtml(option.materialPreview)}" alt="${escapeHtml(`${option.label} 材質樣本`)}" loading="lazy">
        <i style="--material-primary:${escapeHtml(option.color)}" aria-label="圖片主色 ${escapeHtml(option.color)}"></i>
      </span>
      <span class="rp-material-catalog-copy">
        <strong>${escapeHtml(option.label)}</strong>
        ${materialVisualTagMarkup(option.visualTags)}
        <small>${escapeHtml(option.materialGroup)}</small>
      </span>
    </button>
  `).join("") || "<p class=\"rp-field-error\">找不到符合的材質。請換個關鍵字，或回到推薦項目。</p>";
  if (!element.questionnaireMaterialCatalogDialog.open) {
    element.questionnaireMaterialCatalogDialog.showModal();
  }
}

function randomWholeHouseAnswers() {
  const note = randomItem(TEST_REQUIREMENT_PROFILE_NOTES, TEST_REQUIREMENT_PROFILE_NOTES[0]);
  return Object.fromEntries(WHOLE_HOUSE_QUESTIONS.map((question) => {
    if (question.type === "select") return [question.id, randomItem(question.options, "")];
    return [question.id, note];
  }));
}

function randomAnswerForQuestion(question) {
  const useBalanced = question.allow_both === true && Math.random() < 0.18;
  if (useBalanced) {
    return {
      optionId: "both",
      custom: "測試隨機：兩端需求都要保留，交給配置時依房間尺寸取捨。",
      preferenceWeight: 0,
      preferenceDirection: "balanced",
    };
  }
  const option = randomItem(question.options, question.options?.[0]);
  const optionIndex = Math.max(0, question.options?.indexOf(option) ?? 0);
  const preferenceWeight = optionIndex === 0 ? randomItem([-2, -1], -2) : randomItem([1, 2], 2);
  return {
    optionId: option?.option_id || "",
    custom: randomItem(TEST_REQUIREMENT_PROFILE_NOTES, ""),
    forcePlacement: true,
    preferenceWeight,
    preferenceDirection: preferenceWeight < 0 ? "a" : "b",
  };
}

function randomRoomAxisNote(room) {
  const axes = ROOM_REQUIREMENT_POLAR_AXES[room.type]
    || ROOM_REQUIREMENT_POLAR_AXES.default;
  return axes.map((axis) => {
    const side = Math.random() < 0.5 ? axis.left : axis.right;
    return `${axis.axis}:${side}`;
  });
}

function randomRoomFinishDraft() {
  const pack = randomItem(STYLE_PACKS, STYLE_PACKS[0]);
  const wallOption = randomItem(questionnaireMaterialOptionsForPack("wall", pack), null);
  const floorOption = randomItem(questionnaireMaterialOptionsForPack("floor", pack), null);
  const wallMaterial = wallOption?.id || pack.wall.surfaceOption;
  const wallColor = wallOption?.color || pack.wall.color;
  const floorMaterial = floorOption?.id || pack.floor.surfaceOption;
  const floorColor = floorOption?.color || pack.floor.color;
  const ceilingStyle = randomItem(
    CEILING_STYLES.filter((item) => item.styles.includes(pack.styleId)),
    CEILING_STYLES[0],
  );
  const lightStyle = randomItem(
    LIGHT_STYLES.filter((item) => item.styles.includes(pack.styleId)),
    LIGHT_STYLES[0],
  );
  return {
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial,
    wallColor,
    defaultWallMaterial: wallMaterial,
    defaultWallColor: wallColor,
    wallOverrides: {},
    floorMaterial,
    floorColor,
    ceilingMaterial: randomItem(["flat-paint", "mineral-paint", "wood-veneer", "exposed-concrete"], "flat-paint"),
    ceilingStyle: ceilingStyle.id,
    lightStyle: lightStyle.id,
    ceilingColor: randomItem(pack.palette, "#f4f1eb"),
    airConditioning: randomItem(TEST_AIR_CONDITIONING_OPTIONS, "wall-split"),
  };
}

function applyRandomRoomRequirement(room, draft) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return;
  const roomQuestions = state.visualQuestions.filter(
    (question) => String(question.room_id) === String(room.id),
  );
  const axisAnswers = Object.fromEntries(roomQuestions.map((question) => {
    const answer = randomAnswerForQuestion(question);
    state.visualAnswers[question.question_id] = answer;
    return [
      question.source_question_id || question.question_id,
      { ...answer },
    ];
  }));
  const axisNotes = randomRoomAxisNote(room);
  requirement.axisAnswers = axisAnswers;
  requirement.usage = roomUsageOptions(room)
    .slice(0, 1)
    .map((option) => option.id)
    .filter(Boolean);
  requirement.furniture = {
    // Random test data must be replaced with verified catalog entries below.
    // Keeping free-text requirement labels here used to make Step 6 auto-add
    // types that had no usable GLB model.
    required: [],
    optional: [],
    selected: [],
    deferred: [],
    catalog_only: true,
  };
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
    materialSelectionMode: draft.materialSelectionMode || "auto",
    styleReviewRequired: false,
    wallPreference: draft.wallPreference || "",
    floorPreference: draft.floorPreference || "",
    wallDefault: {
      materialId: draft.defaultWallMaterial || draft.wallMaterial,
      color: draft.defaultWallColor || draft.wallColor,
    },
    wallOverrides: {},
    wallSurfaceIds: [],
    floor: {
      materialId: draft.floorMaterial,
      color: draft.floorColor,
    },
    ceiling: {
      materialId: draft.ceilingMaterial,
      styleId: draft.ceilingStyle,
      lightingId: draft.lightStyle,
      color: draft.ceilingColor,
    },
  };
  requirement.specialRequests = axisNotes;
  requirement.feasibility = [];
  requirement.confirmed = true;
}

async function randomizeRequirementsForTesting() {
  element.requirementsError.textContent = "";
  if (!state.rooms.length) {
    throw new Error("請先完成空間確認，才能帶入預設需求。");
  }
  try {
    await ensureVisualQuestionnaireLoaded();
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    throw error;
  }
  state.roomRequirementModel = normalizeRoomRequirements(
    state.roomRequirementModel,
    state.rooms,
    {
      basic: state.basicAnswers,
      basicConfirmed: state.basicConfirmed,
      finishes: state.questionnaireFinishes,
    },
  );
  state.basicAnswers = randomWholeHouseAnswers();
  state.basicConfirmed = true;
  state.roomRequirementModel.globalProfile = { ...state.basicAnswers };
  state.roomRequirementModel.globalConfirmed = true;
  state.visualAnswers = {};
  state.skippedVisualSpaceTypes = [];
  state.roomFinishDrafts = {};
  state.rooms.forEach((room) => {
    const draft = randomRoomFinishDraft();
    state.roomFinishDrafts[room.id] = { ...draft };
    applyRandomRoomRequirement(room, draft);
  });
  await Promise.all(state.rooms.map((room) => (
    ensureQuestionnaireFurnitureRecommendations(room, { force: true })
  )));
  // The test-fill path is a real configuration path, not a mock. Replace each
  // room's generic requirement labels with verified, room-fitting catalog items.
  state.rooms.forEach((room) => {
    applyVerifiedRandomQuestionnaireFurniture(room);
  });
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (requirement) requirement.confirmed = true;
    if (state.roomFinishDrafts[room.id]) state.roomFinishDrafts[room.id].confirmed = true;
  });
  const firstRoomId = state.rooms[0]?.id;
  state.roomRequirementModel.activeRoomId = firstRoomId || null;
  state.questionnaireFinishes = {
    ...(state.roomFinishDrafts[firstRoomId] || randomRoomFinishDraft()),
    confirmed: true,
  };
  applyWholeHouseSurfaceConsistency();
  state.visualQuestionIndex = 0;
  state.selectedQuestionnaireWallId = null;
  state.questionnaireStage = "summary";
  invalidateDownstreamFrom("requirements", "已隨機產生測試需求，後續配置已標記需重新生成。");
  const firstPack = STYLE_PACKS.find((pack) => pack.id === state.questionnaireFinishes.stylePackId);
  if (firstPack) {
    state.activeStyleId = firstPack.styleId;
    state.activeStylePackId = firstPack.id;
  }
  renderWholeHouseQuestionnaire();
  renderVisualQuestionnaire();
  renderQuestionnaireFinishes();
  renderQuestionnaireSummary();
  showQuestionnaireStage("summary");
  setStatus("已隨機完成逐房需求、全屋資料、天花板、照明、冷氣與材質。");
  scheduleSave("requirements");
}

async function skipQuestionnaireWithDefaults() {
  const buttons = [
    element.randomizeRequirements,
    element.randomizeRequirementsSummary,
  ].filter(Boolean);
  if (!buttons.length || buttons.some((button) => button.disabled)) return;
  const controls = [...buttons, element.confirmRequirements].filter(Boolean);
  controls.forEach((control) => {
    control.disabled = true;
    control.setAttribute("aria-busy", "true");
  });
  element.requirementsError.textContent = "";
  setStatus("正在帶入系統預設需求…");
  try {
    await randomizeRequirementsForTesting();
    setStatus("已帶入系統預設需求；可在摘要檢查或返回逐房修改。", "success");
  } catch (error) {
    const message = `無法帶入預設需求：${errorMessage(error)}`;
    element.requirementsError.textContent = message;
    setStatus(message, "error");
  } finally {
    controls.forEach((control) => {
      control.disabled = false;
      control.removeAttribute("aria-busy");
    });
  }
}

async function prepareQuestionnaireStep() {
  if (!state.surfaceCatalog) {
    try {
      const bootstrap = await api("/api/scene/bootstrap");
      state.surfaceCatalog = bootstrap.surface_catalog || { surfaces: [] };
      state.surfaceCatalogProvider = bootstrap.catalog_status?.surfaces?.provider || "unknown";
      state.surfaceCatalogLoadError = null;
    } catch (error) {
      state.surfaceCatalog = { surfaces: [] };
      state.surfaceCatalogProvider = "unavailable";
      state.surfaceCatalogLoadError = errorMessage(error);
    }
  }
  state.roomRequirementModel = normalizeRoomRequirements(
    state.roomRequirementModel,
    state.rooms,
    {
      basic: state.basicAnswers,
      basicConfirmed: state.basicConfirmed,
      finishes: state.questionnaireFinishes,
    },
  );
  renderWholeHouseQuestionnaire();
  try {
    await ensureVisualQuestionnaireLoaded();
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    state.questionnaireStage = "profile";
  }
  showQuestionnaireStage(state.questionnaireStage);
}

function roomQuestionnaireProgress() {
  const rooms = state.rooms || [];
  const completed = rooms.filter((room) => roomQuestionnaireSectionProgress(room).confirmed).length;
  return {
    completed,
    total: rooms.length,
    ready: rooms.length > 0 && completed === rooms.length,
  };
}

function questionnaireStageUnlocked(stage) {
  if (stage === "profile") return true;
  if (stage === "rooms") return state.basicConfirmed;
  return roomQuestionnaireProgress().ready && state.basicConfirmed;
}

function showQuestionnaireStage(stage) {
  const requested = QUESTIONNAIRE_STAGES.includes(stage) ? stage : "profile";
  const nextStage = questionnaireStageUnlocked(requested) ? requested : "profile";
  state.questionnaireStage = nextStage;
  $$("[data-questionnaire-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.questionnairePanel !== nextStage;
  });
  $$("[data-questionnaire-stage]", element.questionnaireStageNav).forEach((button) => {
    const target = button.dataset.questionnaireStage;
    button.disabled = !questionnaireStageUnlocked(target);
    button.classList.toggle("is-active", target === nextStage);
    button.classList.toggle(
      "is-complete",
      QUESTIONNAIRE_STAGES.indexOf(target) < QUESTIONNAIRE_STAGES.indexOf(nextStage),
    );
  });
  const labels = {
    rooms: `逐房需求 ${roomQuestionnaireProgress().completed} / ${roomQuestionnaireProgress().total}`,
    profile: "全屋條件與主風格",
    summary: "確認方案",
  };
  element.requirementsProgress.textContent = labels[nextStage];
  element.requirementsError.textContent = "";
  if (nextStage === "rooms") {
    renderVisualQuestionnaire();
  } else if (nextStage === "profile") {
    renderWholeHouseQuestionnaire();
  } else if (nextStage === "summary") {
    renderQuestionnaireSummary();
  }
  scheduleSave("requirements");
}

async function ensureVisualQuestionnaireLoaded() {
  if (state.visualCatalog) {
    state.visualQuestions = [];
    state.visualAnswers = {};
    state.skippedVisualSpaceTypes = [];
    return;
  }
  const catalog = await api("/api/questionnaire/visual-catalog");
  const restoredCatalogVersion = state.visualCatalogVersion;
  state.visualCatalog = catalog;
  // The visual catalog remains available to RAG, but it is no longer a required
  // question-by-question user flow. Step 5 asks only for furniture and finishes.
  state.visualQuestions = [];
  if (
    restoredCatalogVersion
    && restoredCatalogVersion !== catalog.version
  ) {
    state.visualAnswers = {};
    state.skippedVisualSpaceTypes = [];
    state.questionnaireStage = "rooms";
    invalidateDownstreamFrom(
      "requirements",
      "推薦題庫已更新，後續 2D、3D 與渲染結果需要重新確認。",
    );
    setStatus("推薦題庫已更新，請重新確認家具與材質。");
  }
  state.visualCatalogVersion = catalog.version;
  state.visualAnswers = {};
  state.skippedVisualSpaceTypes = [];
  state.visualQuestionIndex = 0;
  $("#visual-questionnaire-notice").textContent = "";
}

function visualQuestionAt(index = state.visualQuestionIndex) {
  return state.visualQuestions[index] || null;
}

function answerWeightDirection(weight) {
  if (Number(weight) < 0) return "a";
  if (Number(weight) > 0) return "b";
  return "balanced";
}

function weightedOptionId(question, weight, currentOptionId = "") {
  if (!question?.options?.length) return currentOptionId;
  if (Number(weight) < 0) return question.options[0]?.option_id || currentOptionId;
  if (Number(weight) > 0) return question.options[1]?.option_id || currentOptionId;
  return question.allow_both ? "both" : (currentOptionId || question.options[0]?.option_id || "");
}

function preferenceWeightFromOption(question, optionId, fallback = null) {
  if (Number.isFinite(Number(fallback))) return Number(fallback);
  if (!question?.options?.length) return 0;
  if (optionId === "both") return 0;
  const index = question.options.findIndex((option) => option.option_id === optionId);
  if (index === 0) return -2;
  if (index === 1) return 2;
  return 0;
}

function preferenceWeightLabel(weight) {
  return PREFERENCE_WEIGHT_OPTIONS.find((item) => item.value === Number(weight))?.label || "";
}


function resolvedVisualPreferences(questions = state.visualQuestions) {
  return questions.flatMap((question) => {
    if (state.skippedVisualSpaceTypes.includes(question.space_type)) return [];
    const answer = state.visualAnswers[question.question_id];
    if (!answer?.optionId) return [];
    const option = question.options.find(
      (candidate) => candidate.option_id === answer.optionId,
    );
    return [{
      question_id: question.question_id,
      space_type: question.space_type,
      option_id: answer.optionId,
      custom: answer.custom || "",
      special_request: answer.specialRequest === true,
      force_placement: answer.forcePlacement !== false,
      preference_weight: Number(answer.preferenceWeight ?? 0),
      preference_direction: answer.preferenceDirection
        || answerWeightDirection(answer.preferenceWeight),
      engine_effects: answer.forcePlacement === false ? {} : (option?.engine_effects || {}),
    }];
  });
}

function visualPreferencesForRoom(room) {
  return resolvedVisualPreferences(
    state.visualQuestions.filter(
      (question) => String(question.room_id) === String(room.id),
    ),
  );
}

function saveVisualCustomAnswer() {
  const question = visualQuestionAt();
  if (!question) return false;
  const custom = element.visualCustomAnswer.value.trim();
  const previous = state.visualAnswers[question.question_id];
  if (!custom && !previous) return false;
  if ((previous?.custom || "") === custom) return false;
  state.visualAnswers[question.question_id] = {
    ...(previous || {}),
    custom,
  };
  return true;
}

function activeQuestionnaireRoom() {
  const roomId = state.roomRequirementModel?.activeRoomId
    || state.rooms[0]?.id;
  return state.rooms.find((room) => String(room.id) === String(roomId)) || state.rooms[0] || null;
}

function activeRoomRequirement() {
  const room = activeQuestionnaireRoom();
  return room
    ? state.roomRequirementModel?.roomRequirements?.[room.id]
    : null;
}

function renderQuestionnairePlan() {
  if (!element.questionnairePlanImage?.naturalWidth) return;
  syncOverlayToImage(
    element.questionnairePlanStage,
    element.questionnairePlanImage,
    element.questionnairePlanOverlay,
  );
  const activeRoom = activeQuestionnaireRoom();
  const polygons = state.rooms.map((room) => {
    const active = room.id === activeRoom?.id;
    const center = cmToPixel(roomCenter(room));
    return `
      <g data-questionnaire-room="${escapeHtml(room.id)}">
        <polygon points="${roomPolygonSvg(room)}"
          fill="${active ? "rgba(47,111,135,.24)" : "rgba(36,107,85,.08)"}"
          stroke="${active ? "#2f6f87" : "#5b786d"}" stroke-width="${active ? 6 : 3}"/>
        <text x="${center.x}" y="${center.y}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="7" paint-order="stroke"
          font-size="22" font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>
      </g>
    `;
  }).join("");
  const wallSegments = activeRoom?.polygon_cm?.map((point, index, polygon) => {
    const start = cmToPixel(point);
    const end = cmToPixel(polygon[(index + 1) % polygon.length]);
    const wallId = `${activeRoom.id}:wall:${index}`;
    const selected = state.selectedQuestionnaireWallId === wallId;
    return `<line data-questionnaire-wall="${escapeHtml(wallId)}"
      x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="${selected ? "#bd5c36" : "transparent"}" stroke-width="16"
      class="rp-questionnaire-wall-hit"/>`;
  }).join("") || "";
  element.questionnairePlanOverlay.innerHTML = `${polygons}${wallSegments}`;
}

function renderVisualSpaceNav() {
  const currentRoomId = activeQuestionnaireRoom()?.id;
  element.visualSpaceNav.innerHTML = state.rooms.map((room) => {
    const progress = roomQuestionnaireSectionProgress(room);
    const furnitureCount = roomFurnitureRequirement(room.id)?.selected?.length || 0;
    const ragStatus = state.roomRagJobs?.[room.id]?.status || "";
    const roomState = progress.confirmed
      ? (ragStatus === "queued" || ragStatus === "running" ? "rag-pending" : "confirmed")
      : (progress.complete ? "ready" : "draft");
    return `
      <button type="button" data-visual-room="${escapeHtml(room.id)}"
        class="${room.id === currentRoomId ? "is-active" : ""} is-${roomState}"
        aria-current="${room.id === currentRoomId ? "true" : "false"}">
        <strong>${escapeHtml(room.label)}</strong>
        <i class="rp-room-nav-state" aria-hidden="true"></i>
        <small>${progress.confirmed ? "本房需求已確認" : (progress.complete ? "待使用者確認" : `需求填寫中・${furnitureCount} 件家具`)}</small>
      </button>
    `;
  }).join("");
}



function renderVisualQuestionnaire() {
  const room = activeQuestionnaireRoom();
  if (!room) return;
  element.visualQuestionCard.hidden = true;
  element.visualQuestionCard.replaceChildren();
  renderVisualSpaceNav();
  state.roomRequirementModel.activeRoomId = room.id;
  renderQuestionnairePlan();
  renderQuestionnaireFinishes();
}

function selectVisualOption(optionId, {
  specialRequest = false,
  forcePlacement = true,
  custom = element.visualCustomAnswer.value.trim(),
  preferenceWeight = null,
} = {}) {
  const question = visualQuestionAt();
  if (!question) return;
  const weight = preferenceWeightFromOption(question, optionId, preferenceWeight);
  state.skippedVisualSpaceTypes = state.skippedVisualSpaceTypes.filter(
    (spaceType) => spaceType !== question.space_type,
  );
  state.visualAnswers[question.question_id] = {
    optionId,
    custom,
    specialRequest,
    forcePlacement,
    preferenceWeight: weight,
    preferenceDirection: answerWeightDirection(weight),
  };
  renderVisualQuestionnaire();
  invalidateDownstreamFrom("requirements", "視覺偏好已修改，2D 家具與 3D 需要重新產生。");
  scheduleSave("requirements");
}

function selectPreferenceWeight(weight) {
  const question = visualQuestionAt();
  if (!question) return;
  const parsed = Number(weight);
  if (!Number.isFinite(parsed)) return;
  const previous = state.visualAnswers[question.question_id] || {};
  const optionId = weightedOptionId(question, parsed, previous.optionId);
  selectVisualOption(optionId, {
    ...previous,
    custom: element.visualCustomAnswer.value.trim(),
    preferenceWeight: parsed,
  });
}

function moveVisualQuestion(offset) {
  if (saveVisualCustomAnswer()) scheduleSave("requirements");
  const question = visualQuestionAt();
  const skipped = state.skippedVisualSpaceTypes.includes(question?.space_type);
  if (offset > 0 && !state.visualAnswers[question?.question_id]?.optionId && !skipped) {
    element.requirementsError.textContent = "請先選擇一個方向，或將這個空間標示為暫不作答。";
    return;
  }
  element.requirementsError.textContent = "";
  const roomId = question?.room_id;
  const roomQuestionIndexes = state.visualQuestions
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => String(candidate.room_id) === String(roomId))
    .map(({ index }) => index);
  const roomPosition = roomQuestionIndexes.indexOf(state.visualQuestionIndex);
  const nextIndex = offset > 0
    ? roomQuestionIndexes
      .slice(roomPosition + 1)
      .find((index) => !state.visualAnswers[state.visualQuestions[index].question_id]?.optionId)
    : roomQuestionIndexes[roomPosition + offset];
  if (Number.isInteger(nextIndex)) {
    state.visualQuestionIndex = nextIndex;
    renderVisualQuestionnaire();
    return;
  }
  if (offset > 0) {
    $("#questionnaire-finishes").scrollIntoView({ block: "start", behavior: "smooth" });
  }
}



function wholeHouseStylePack() {
  return STYLE_PACKS.find((pack) => pack.id === state.questionnaireFinishes?.stylePackId)
    || STYLE_PACKS.find((pack) => pack.id === state.activeStylePackId)
    || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
}

function activeQuestionnairePack() {
  return wholeHouseStylePack();
}

function activeRoomFinishDraft() {
  const requirement = activeRoomRequirement();
  const roomId = requirement?.roomId;
  if (!roomId) return state.questionnaireFinishes;
  if (!state.roomFinishDrafts[roomId]) {
    const surfaces = requirement.surfaces || {};
    state.roomFinishDrafts[roomId] = {
      confirmed: requirement.confirmed === true,
      materialSelectionMode: surfaces.materialSelectionMode || "auto",
      styleReviewRequired: surfaces.styleReviewRequired === true,
      stylePackId: surfaces.paletteId || null,
      wallMaterial: surfaces.wallDefault?.materialId || null,
      wallColor: surfaces.wallDefault?.color || null,
      defaultWallMaterial: surfaces.wallDefault?.materialId || null,
      defaultWallColor: surfaces.wallDefault?.color || null,
      wallOverrides: { ...(surfaces.wallOverrides || {}) },
      wallPreference: surfaces.wallPreference || "",
      floorMaterial: surfaces.floor?.materialId || null,
      floorColor: surfaces.floor?.color || null,
      floorPreference: surfaces.floorPreference || "",
      ceilingMaterial: surfaces.ceiling?.materialId || null,
      ceilingStyle: surfaces.ceiling?.styleId || null,
      lightStyle: surfaces.ceiling?.lightingId || null,
      ceilingColor: surfaces.ceiling?.color || "#f4f1eb",
      airConditioning: requirement.climate?.airConditioning || "",
    };
  }
  // Style identity is global. A room may vary its compatible finishes, never
  // its style pack.
  const draft = state.roomFinishDrafts[roomId];
  const pack = wholeHouseStylePack();
  draft.stylePackId = pack.id;
  // Existing projects can have drafts created before ceiling defaults were
  // persisted. Treat the compatible global defaults as selected instead of
  // blocking the user on a field that already has a visible recommendation.
  draft.ceilingMaterial ||= "flat-paint";
  draft.ceilingStyle ||= recommendedCeilingStyleForPack(pack);
  draft.lightStyle ||= recommendedLightStyleForPack(pack);
  return draft;
}

function renderQuestionnaireMaterialOptions(kind, pack) {
  const draft = activeRoomFinishDraft();
  const host = kind === "wall"
    ? element.questionnaireWallOptions
    : element.questionnaireFloorOptions;
  const selectedKey = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const materialLabel = kind === "wall" ? "牆面" : "地板";
  const options = questionnaireMaterialOptionsForPack(kind, pack);
  const recommendationCards = options.map((option) => `
    <button type="button" data-questionnaire-material="${escapeHtml(kind)}"
      data-questionnaire-material-id="${escapeHtml(option.id)}"
      class="${draft[selectedKey] === option.id ? "is-active" : ""}"
      aria-pressed="${draft[selectedKey] === option.id}">
      <span class="rp-material-preview" style="background-color:${escapeHtml(option.color)};background-image:url('${escapeHtml(option.materialPreview)}')"></span>
      <strong>${escapeHtml(option.label)}</strong>
       <small>${escapeHtml(option.note)}<em>推薦</em></small>
    </button>
  `).join("") || `<p class="rp-field-error">找不到符合目前條件的${kind === "wall" ? "牆面" : "地板"}材質，可調整需求後重試。</p>`;
  host.innerHTML = `
    <div class="rp-material-catalog-entry">
      <div>
        <strong>想換${materialLabel}？</strong>
        <small>可搜尋並從材質資料庫挑選。</small>
      </div>
      <button type="button" class="secondary-action rp-open-material-catalog"
        data-open-material-catalog="${escapeHtml(kind)}">從材質資料庫挑選${materialLabel}</button>
    </div>
    <div class="rp-material-option-list">${recommendationCards}</div>`;
}

function roomQuestionnaireSectionProgress(room) {
  const requirement = state.roomRequirementModel?.roomRequirements?.[room?.id] || {};
  const surfaces = requirement.surfaces || {};
  const ceiling = surfaces.ceiling || {};
  const usage = room ? ensureRoomUsage(room) : [];
  const furnitureCount = roomFurnitureRequirement(room?.id)?.selected?.length || 0;
  const furnitureRequired = questionnaireFurnitureProgram(room).required.length > 0;
  const sections = {
    usage: usage.length > 0,
    furniture: !furnitureRequired || furnitureCount > 0,
    surfaces: Boolean(surfaces.wallDefault?.materialId && surfaces.floor?.materialId),
    ceiling: Boolean(ceiling.styleId && ceiling.lightingId),
  };
  const complete = Object.values(sections).every(Boolean);
  return {
    sections,
    complete,
    confirmed: complete && requirement.confirmed === true,
  };
}

function questionnaireUsageSummary(room) {
  const selected = new Set(ensureRoomUsage(room));
  return roomUsageOptions(room)
    .filter((option) => selected.has(option.id))
    .map((option) => option.label)
    .join("、") || "待設定";
}

const QUESTIONNAIRE_ROOM_SECTIONS = Object.freeze([
  { id: "usage", label: "房間用途", summary: questionnaireUsageSummary },
  { id: "furniture", label: "家具配置", summary: (room) => `${roomFurnitureRequirement(room?.roomId)?.selected?.length || 0} 件家具` },
  { id: "surfaces", label: "牆面與地板", summary: (room) => room?.surfaces?.wallDefault?.materialId && room?.surfaces?.floor?.materialId ? "已選搭配" : "待設定" },
  { id: "ceiling", label: "天花與照明", summary: (room) => room?.surfaces?.ceiling?.styleId && room?.surfaces?.ceiling?.lightingId ? "已選搭配" : "待設定" },
  { id: "review", label: "檢查並確認", summary: (room) => room?.confirmed ? "本房已確認" : "確認後儲存" },
]);

function questionnaireRoomEditorElements() {
  return {
    editor: $(".rp-room-questionnaire-editor"),
    nav: $("#questionnaire-room-section-nav"),
    title: $("#questionnaire-active-room-title"),
    saveState: $("#questionnaire-room-save-state"),
  };
}

function ensureQuestionnaireRoomActionBar() {
  const editor = questionnaireRoomEditorElements().editor;
  if (!editor) return null;
  let bar = $("#questionnaire-room-action-bar", editor);
  if (bar) return bar;
  bar = document.createElement("footer");
  bar.id = "questionnaire-room-action-bar";
  bar.className = "rp-questionnaire-room-action-bar";
  bar.innerHTML = `<p id="questionnaire-room-action-status"></p><div><button id="questionnaire-room-section-back" type="button" class="secondary-action">上一區</button><button id="questionnaire-room-section-next" type="button" class="primary-action">下一區</button></div>`;
  editor.append(bar);
  $("#questionnaire-room-section-back", bar).addEventListener("click", () => moveQuestionnaireRoomSection(-1));
  $("#questionnaire-room-section-next", bar).addEventListener("click", () => moveQuestionnaireRoomSection(1));
  return bar;
}

function renderQuestionnaireRoomReview(room, requirement) {
  let review = $("#questionnaire-room-review");
  if (!review) {
    review = document.createElement("section");
    review.id = "questionnaire-room-review";
    review.className = "rp-questionnaire-room-review";
    review.dataset.roomSectionPanel = "review";
    $("#questionnaire-finishes")?.append(review);
  }
  const draft = activeRoomFinishDraft();
  const furniture = roomFurnitureRequirement(room?.id)?.selected || [];
  const lines = [
    ["用途", questionnaireUsageSummary(room), "usage"],
    ["家具", furniture.length ? `${furniture.length} 件已加入配置` : "尚未選擇", "furniture"],
    ["牆面與地板", draft.wallMaterial && draft.floorMaterial ? `已選牆地搭配${draft.wallPreference || draft.floorPreference ? "，含生圖偏好" : ""}` : "尚未選擇", "surfaces"],
    ["天花與照明", draft.ceilingStyle && draft.lightStyle ? "已選相容搭配" : "尚未選擇", "ceiling"],
  ];
  const pack = activeQuestionnairePack();
  const wall = catalogMaterialOptionsForPack("wall", pack).find((item) => item.id === draft.wallMaterial);
  const floor = catalogMaterialOptionsForPack("floor", pack).find((item) => item.id === draft.floorMaterial);
  const ceiling = CEILING_STYLES.find((item) => item.id === draft.ceilingStyle);
  const lighting = LIGHT_STYLES.find((item) => item.id === draft.lightStyle);
  const furnitureImages = furniture
    .map((item) => ({
      label: item.name_zh || item.name_zh_raw || item.name_en || "家具",
      url: item.image_url || item.thumbnail_url || item.preview_url || "",
    }))
    .filter((item) => item.url)
    .slice(0, 3);
  const visualSummary = `<section class="rp-room-review-preview" aria-label="本房已選項目預覽">
    <article class="rp-room-review-finish"><span class="rp-room-review-material" style="background-color:${escapeHtml(wall?.color || draft.wallColor || "#f4f1eb")};background-image:url('${escapeHtml(wall?.materialPreview || "")}')"></span><div><small>牆面</small><strong>${escapeHtml(wall?.label || "尚未選擇")}</strong></div></article>
    <article class="rp-room-review-finish"><span class="rp-room-review-material" style="background-color:${escapeHtml(floor?.color || draft.floorColor || "#d5d0c7")};background-image:url('${escapeHtml(floor?.materialPreview || "")}')"></span><div><small>地板</small><strong>${escapeHtml(floor?.label || "尚未選擇")}</strong></div></article>
    <article class="rp-room-review-ceiling"><span class="rp-ceiling-choice-visual" data-ceiling-style-visual="${escapeHtml(ceiling?.id || "flat")}"></span><div><small>天花／照明</small><strong>${escapeHtml(`${ceiling?.label || "尚未選擇"}／${lighting?.label || "尚未選擇"}`)}</strong></div></article>
    <article class="rp-room-review-furniture"><div class="rp-room-review-furniture-images">${furnitureImages.map((item) => `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.label)}">`).join("") || "<span>尚無商品圖片</span>"}</div><div><small>已選家具</small><strong>${furniture.length ? `${furniture.length} 件加入配置` : "尚未選擇"}</strong></div></article>
  </section>`;
  review.innerHTML = `<div class="rp-questionnaire-section-heading"><div><span class="eyebrow">最後檢查</span><h3>確認${escapeHtml(room?.label || "本房")}需求</h3></div><p>確認後會儲存本房需求；第 6 步才會統一產生 A／B 的 2D＋3D 配置，並驗證家具碰撞、門片與走道淨空。</p></div>${visualSummary}<div class="rp-room-review-list">${lines.map(([label, value, target]) => `<button type="button" data-questionnaire-room-section="${target}"><span>${label}</span><strong>${escapeHtml(value)}</strong><em>編輯</em></button>`).join("")}</div>`;
}

function renderQuestionnaireRoomSections() {
  const room = activeQuestionnaireRoom();
  const requirement = activeRoomRequirement();
  const { editor, nav, title, saveState } = questionnaireRoomEditorElements();
  if (!room || !requirement || !editor || !nav) return;
  const validSection = QUESTIONNAIRE_ROOM_SECTIONS.some((section) => section.id === questionnaireRuntimeState.roomSection);
  if (!validSection) questionnaireRuntimeState.roomSection = "usage";
  const currentIndex = QUESTIONNAIRE_ROOM_SECTIONS.findIndex((section) => section.id === questionnaireRuntimeState.roomSection);
  const progress = roomQuestionnaireSectionProgress(room);
  const confirmed = progress.confirmed;
  title.textContent = `${room.label}需求`;
  saveState.textContent = confirmed
    ? "本房需求已確認"
    : (progress.complete ? "資料完整，尚待確認" : "自動暫存，需求未完成");
  editor.dataset.roomSection = questionnaireRuntimeState.roomSection;
  nav.innerHTML = QUESTIONNAIRE_ROOM_SECTIONS.map((section, index) => {
    const complete = section.id === "review"
      ? confirmed
      : progress.sections[section.id] === true;
    const active = section.id === questionnaireRuntimeState.roomSection;
    return `<button type="button" data-questionnaire-room-section="${section.id}" class="${active ? "is-active" : ""} ${complete ? "is-complete" : ""}" aria-current="${active ? "step" : "false"}"><b>${complete ? "✓" : index + 1}</b><span><strong>${section.label}</strong><small>${escapeHtml(section.summary(requirement))}</small></span></button>`;
  }).join("");
  renderQuestionnaireRoomReview(room, requirement);
  const bar = ensureQuestionnaireRoomActionBar();
  const actionStatus = $("#questionnaire-room-action-status", bar);
  const back = $("#questionnaire-room-section-back", bar);
  const next = $("#questionnaire-room-section-next", bar);
  actionStatus.textContent = confirmed
    ? "本房資料已確認"
    : (progress.complete ? "資料完整，等待使用者確認" : "自動暫存，尚未完成");
  back.hidden = currentIndex === 0;
  next.hidden = questionnaireRuntimeState.roomSection === "review";
  const nextSection = QUESTIONNAIRE_ROOM_SECTIONS[currentIndex + 1];
  next.textContent = nextSection ? `下一步：${nextSection.label}` : "下一區";
  const confirm = $("#confirm-questionnaire-finishes");
  if (confirm) {
    bar.querySelector("div")?.append(confirm);
    confirm.hidden = questionnaireRuntimeState.roomSection !== "review";
    confirm.textContent = confirmed ? "更新本房確認" : `確認${room.label}並前往下一房`;
  }
}

function moveQuestionnaireRoomSection(offset) {
  const index = QUESTIONNAIRE_ROOM_SECTIONS.findIndex((section) => section.id === questionnaireRuntimeState.roomSection);
  const next = QUESTIONNAIRE_ROOM_SECTIONS[index + offset];
  if (!next) return;
  questionnaireRuntimeState.roomSection = next.id;
  renderQuestionnaireRoomSections();
  $(".rp-room-questionnaire-editor")?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function scrollQuestionnaireToNextRoomStart() {
  const editor = $(".rp-room-questionnaire-editor") || $("#questionnaire-finishes");
  if (!editor) return;
  window.requestAnimationFrame(() => {
    const top = window.scrollY + editor.getBoundingClientRect().top - 16;
    window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
  });
}

function selectQuestionnaireMaterial(kind, materialId) {
  const key = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const colorKey = kind === "wall" ? "wallColor" : "floorColor";
  const draft = activeRoomFinishDraft();
  draft[key] = materialId;
  const option = catalogMaterialOptionsForPack(kind, activeQuestionnairePack())
    .find((candidate) => candidate.id === materialId);
  if (option?.color) draft[colorKey] = option.color;
  if (kind === "wall") {
    if (state.selectedQuestionnaireWallId) {
      draft.wallOverrides[state.selectedQuestionnaireWallId] = {
        materialId: draft.wallMaterial,
        color: draft.wallColor,
      };
    } else {
      draft.defaultWallMaterial = draft.wallMaterial;
      draft.defaultWallColor = draft.wallColor;
    }
  }
  draft.confirmed = false;
  draft.materialSelectionMode = "custom";
  draft.styleReviewRequired = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function selectStepSixCatalogMaterial(kind, materialId) {
  const pack = stylePackByIdSafe(state.activeStylePackId) || activeQuestionnairePack();
  const option = catalogMaterialOptionsForPack(kind, pack)
    .find((candidate) => candidate.id === materialId);
  const select = $("#" + kind + "-material");
  const color = $("#" + kind + "-color");
  if (!select || !option) return;
  if (![...select.options].some((item) => item.value === materialId)) {
    select.add(new Option(option.label, option.id));
  }
  select.value = materialId;
  if (color && option.color) color.value = option.color;
  state.stepSixSurfaceKind = kind;
  void previewStepSixRoomSurfaces({ userInitiated: true });
}

function ceilingPickerItems(kind) {
  return kind === "style" ? CEILING_STYLES : LIGHT_STYLES;
}

function renderQuestionnaireCeilingQuickChoices(draft) {
  const pack = activeQuestionnairePack();
  const options = [...CEILING_DESIGN_PACKS].sort((left, right) => {
    const leftPreferred = left.styles.includes(pack.styleId) ? 1 : 0;
    const rightPreferred = right.styles.includes(pack.styleId) ? 1 : 0;
    return rightPreferred - leftPreferred;
  });
  const groups = CEILING_STYLES.map((ceiling) => ({
    ceiling,
    designs: options.filter((option) => option.ceilingStyle === ceiling.id),
  })).filter((group) => group.designs.length);
  element.questionnaireCeilingQuickChoices.innerHTML = `
    <div class="rp-questionnaire-section-heading"><div><h3>天花施工形式</h3></div><p>先選施工形式；再於下一個視窗選相容的材質與照明搭配。</p></div>
    <div class="rp-ceiling-design-packs">${groups.map(({ ceiling, designs }) => {
      const active = draft.ceilingStyle === ceiling.id;
      return `<button type="button" class="rp-ceiling-design-pack ${active ? "is-active" : ""}" data-open-questionnaire-ceiling-design-style="${escapeHtml(ceiling.id)}" aria-pressed="${active}">
        <span class="rp-ceiling-choice-visual" data-ceiling-style-visual="${escapeHtml(ceiling.id)}"></span>
        <span><strong>${escapeHtml(ceiling.label)}</strong><small>${designs.length} 組相容材質與照明搭配</small><em>選擇搭配</em></span>
      </button>`;
    }).join("")}</div>
  `;
}

function openQuestionnaireCeilingDesignStyle(styleId) {
  const ceiling = CEILING_STYLES.find((item) => item.id === styleId);
  const designs = CEILING_DESIGN_PACKS.filter((item) => item.ceilingStyle === styleId);
  const draft = activeRoomFinishDraft();
  element.questionnaireCeilingPickerTitle.textContent = `${ceiling?.label || "天花"}搭配`;
  element.questionnaireCeilingPickerHelp.textContent = ceiling?.id === "flat"
    ? "平釘天花是施工形式，不是燈具。可搭配無主燈、崁燈、吊燈或軌道燈；選取後會依房間淨高與用途再檢查。"
    : "每張卡的材質、天花形式與照明已經過相容檢查，選取後一次套用三項。";
  element.questionnaireCeilingPickerOptions.innerHTML = designs.map((design) => {
    const active = draft.ceilingMaterial === design.material && draft.ceilingStyle === design.ceilingStyle && draft.lightStyle === design.lightStyle;
    const lighting = LIGHT_STYLES.find((item) => item.id === design.lightStyle);
    return `<button type="button" class="rp-ceiling-picker-card ${active ? "is-active" : ""}" data-questionnaire-ceiling-design-pack="${escapeHtml(design.id)}" aria-pressed="${active}">
      <span class="rp-ceiling-choice-visual" data-ceiling-design-visual="${escapeHtml(design.id)}"></span>
      <strong>${escapeHtml(design.label)}</strong><small>照明：${escapeHtml(lighting?.label || "未指定")}</small><em>${escapeHtml(design.note || "")}</em>
    </button>`;
  }).join("");
  element.questionnaireCeilingPickerDialog.showModal();
}

function selectQuestionnaireCeilingDesignPack(packId) {
  const design = CEILING_DESIGN_PACKS.find((item) => item.id === packId);
  if (!design) return;
  const draft = activeRoomFinishDraft();
  draft.ceilingMaterial = design.material;
  draft.ceilingStyle = design.ceilingStyle;
  draft.lightStyle = design.lightStyle;
  draft.confirmed = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function openQuestionnaireCeilingPicker(kind) {
  questionnaireRuntimeState.ceilingPickerKind = kind;
  const isCeiling = kind === "style";
  const selectedId = isCeiling
    ? activeRoomFinishDraft().ceilingStyle
    : activeRoomFinishDraft().lightStyle;
  const items = ceilingPickerItems(kind);
  element.questionnaireCeilingPickerTitle.textContent = isCeiling
    ? "選擇天花板形式"
    : "選擇照明形式";
  element.questionnaireCeilingPickerHelp.textContent = isCeiling
    ? "照片用來比較施工形式；選取後會保留在本房草稿，確認本房才會套用。"
    : "照片用來比較光感與燈具形式；選取後會保留在本房草稿，確認本房才會套用。";
  element.questionnaireCeilingPickerOptions.innerHTML = items.map((item) => `
    <button type="button" class="rp-ceiling-picker-card ${item.id === selectedId ? "is-active" : ""}"
      data-questionnaire-ceiling-picker-item="${escapeHtml(item.id)}" aria-pressed="${item.id === selectedId}">
      <span class="${isCeiling ? "rp-ceiling-choice-visual" : "rp-light-choice-visual"}"
        data-${isCeiling ? "ceiling" : "light"}-style-visual="${escapeHtml(item.id)}"></span>
      <strong>${escapeHtml(item.label)}</strong>
    </button>
  `).join("");
  element.questionnaireCeilingPickerDialog.showModal();
}

function selectQuestionnaireCeilingPickerItem(itemId) {
  if (!questionnaireRuntimeState.ceilingPickerKind) return;
  const key = questionnaireRuntimeState.ceilingPickerKind === "style" ? "ceilingStyle" : "lightStyle";
  const draft = activeRoomFinishDraft();
  draft[key] = itemId;
  draft.confirmed = false;
  element.questionnaireCeilingPickerDialog.close();
  questionnaireRuntimeState.ceilingPickerKind = null;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function renderQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  if (room && isCirculationRoom(room)) copyLivingRoomStyleToCirculation(room);
  const draft = activeRoomFinishDraft();
  if (!room || !draft) return;
  const requiredFinishControls = [
    $("#questionnaire-finishes"),
    $("#room-finish-title"),
    $("#confirm-questionnaire-finishes"),
    element.questionnaireStyleTabs,
    element.questionnaireStyleGrid,
    element.questionnaireMaterialGrid,
    element.questionnaireWallColor,
    element.questionnaireFloorColor,
    element.questionnaireWallPreference,
    element.questionnaireFloorPreference,
    element.questionnaireCeilingMaterial,
    element.questionnaireCeilingStyle,
    element.questionnaireLightStyle,
    element.questionnaireCeilingColor,
    element.questionnaireAirConditioning,
    element.questionnaireFinishScope,
    element.questionnaireFinishRoomTargets,
    element.selectedWallSurface,
  ];
  if (requiredFinishControls.some((control) => !control)) return;
  const pack = activeQuestionnairePack();
  if (repairAutomaticMaterialRecommendation(room, draft, pack)) {
    scheduleSave("requirements");
  }
  const roomNeedsOnly = false;
  const circulationLocked = isCirculationRoom(room) && !circulationStyleIsOverridden(room);
  $("#questionnaire-finishes").classList.toggle("is-room-needs-only", roomNeedsOnly);
  $("#room-finish-title").textContent = `${room.label}規劃`;
  $("#questionnaire-finishes .rp-questionnaire-section-heading > p").textContent = "選用途與家具；材質和照明在下方調整。";
  element.circulationStyleNotice.hidden = !isCirculationRoom(room) || roomNeedsOnly;
  if (isCirculationRoom(room) && !roomNeedsOnly) {
    const livingRoom = livingRoomForCirculation();
    element.circulationStyleNotice.querySelector("strong").textContent = circulationLocked
      ? `走道沿用${livingRoom?.label || "客廳"}風格`
      : "走道使用獨立風格";
    element.circulationStyleNotice.querySelector("p").textContent = circulationLocked
      ? `走道會同步${livingRoom?.label || "客廳"}的牆面、地板、天花板與照明，讓全屋動線保持連續。`
      : "你已選擇走道獨立風格；第 6 步會保留這項設定並重新檢查銜接。";
    element.enableCirculationStyleOverride.hidden = !circulationLocked;
  }
  $("#confirm-questionnaire-finishes").textContent = `確認${room.label}的用途、家具與材質`;
  element.questionnaireStyleTabs.hidden = true;
  element.questionnaireStyleGrid.hidden = false;
  element.questionnaireStyleGrid.classList.add("is-fixed-style");
  element.questionnaireMaterialGrid.hidden = false;
  renderQuestionnaireRoomUsage(room);
  renderGenerativeEquipment(room);
  renderQuestionnaireFurnitureRecommendations(room);
  void ensureQuestionnaireFurnitureRecommendations(room);
  const stylePreview = roomNeedsOnly ? wholeHouseFinishDraft() : draft;
  const previewPack = STYLE_PACKS.find((candidate) => candidate.id === stylePreview.stylePackId)
    || STYLE_PACKS.find((candidate) => candidate.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
  const family = STYLE_FAMILIES.find((item) => item.id === previewPack.styleId) || STYLE_FAMILIES[0];
  element.questionnaireStyleTabs.replaceChildren();
  element.questionnaireStyleGrid.innerHTML = `
    <article class="rp-fixed-style-reference">
      <img class="rp-style-card-preview" src="${escapeHtml(family.referenceImage)}"
        alt="${escapeHtml(`${family.label} 台灣住宅風格參考圖`)}" loading="lazy">
      <div><span class="eyebrow">已選全屋主風格</span><strong>${escapeHtml(family.label)}</strong><small>逐房僅調整相容的牆面、地板、天花與照明；色卡將在第 7 步統一選擇。</small></div>
    </article>
  `;
  renderQuestionnaireMaterialOptions("wall", pack);
  renderQuestionnaireMaterialOptions("floor", pack);
  renderQuestionnaireMaterialPairs(pack);
  element.questionnaireWallColor.value =
    draft.wallColor || pack.wall.color;
  element.questionnaireFloorColor.value =
    draft.floorColor || pack.floor.color;
  element.questionnaireWallPreference.value = draft.wallPreference || "";
  element.questionnaireFloorPreference.value = draft.floorPreference || "";
  element.questionnaireCeilingMaterial.value =
    draft.ceilingMaterial || "flat-paint";
  element.questionnaireCeilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireLightStyle.innerHTML = LIGHT_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireCeilingStyle.value =
    draft.ceilingStyle
    || CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || CEILING_STYLES[0].id;
  element.questionnaireLightStyle.value =
    draft.lightStyle
    || LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || LIGHT_STYLES[0].id;
  element.questionnaireCeilingColor.value =
    draft.ceilingColor || "#f4f1eb";
  element.questionnaireAirConditioning.value = draft.airConditioning || "";
  renderQuestionnaireCeilingQuickChoices(draft);
  element.selectedWallSurface.hidden = true;
  element.selectedWallSurface.textContent = "";
  element.questionnaireFinishRoomTargets.innerHTML = state.rooms
    .filter((candidate) => candidate.id !== room.id)
    .map((candidate) => `<label><input type="checkbox" value="${escapeHtml(candidate.id)}"> ${escapeHtml(candidate.label)}</label>`)
    .join("");
  element.questionnaireFinishRoomTargets.hidden =
    element.questionnaireFinishScope.value !== "selected";
  const finishControls = [
    element.questionnaireStyleTabs,
    element.questionnaireStyleGrid,
    element.questionnaireWallOptions,
    element.questionnaireFloorOptions,
    element.questionnaireWallColor,
    element.questionnaireFloorColor,
    element.questionnaireWallPreference,
    element.questionnaireFloorPreference,
    element.questionnaireCeilingMaterial,
    element.questionnaireCeilingStyle,
    element.questionnaireLightStyle,
    element.questionnaireCeilingColor,
    element.questionnaireAirConditioning,
    element.questionnaireFinishScope,
  ];
  finishControls.forEach((control) => {
    if (!control) return;
    control.classList.toggle("is-locked", circulationLocked);
    if ("disabled" in control) control.disabled = circulationLocked;
    control.querySelectorAll?.("button, input, select").forEach((input) => {
      input.disabled = circulationLocked;
    });
  });
  renderConditionalFeasibility(room);
  renderQuestionnaireRoomSections();
}

function renderConditionalFeasibility(room) {
  const options = [
    ["bathtub", "浴缸"],
    ["double_vanity", "雙洗手台"],
    ["large_dining_table", "大型餐桌"],
  ];
  const relevant = room.type === "bathroom"
    ? options.slice(0, 2)
    : (room.type === "kitchen"
      ? options.slice(2)
      : []);
  if (!relevant.length) {
    element.roomFeasibilityNotices.innerHTML = "";
    return;
  }
  element.roomFeasibilityNotices.innerHTML = relevant.map(([optionId, label]) => {
    const result = evaluateConditionalOption(room, optionId, state.structures.doors);
    return `
      <article class="${result.feasible ? "is-feasible" : "needs-review"}">
        <strong>${escapeHtml(label)}</strong>
        <span>${result.feasible ? "目前尺寸可列為一般選項" : "目前尺寸可能無法配置"}</span>
        ${result.feasible ? "" : `<small>${escapeHtml(result.warnings[0])}</small>`}
      </article>
    `;
  }).join("");
}

function selectQuestionnaireStylePack(packId) {
  const wholeHousePack = wholeHouseStylePack();
  if (packId !== wholeHousePack.id) {
    setStatus("風格由全屋設定統一管理；請回全屋設定變更。", "error");
  }
}

function confirmQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  const requirement = activeRoomRequirement();
  const draft = activeRoomFinishDraft();
  if (!room || !requirement) return;
  if (state.questionnaireStage === "rooms") {
    // `confirmed` is written just below. Validate the selected values first;
    // otherwise every new room draft fails before it can ever be confirmed.
    const finishGate = finishesGate({ ...draft, confirmed: true });
    if (!finishGate.ready) {
      element.requirementsError.textContent = `請完成本房材質：${finishGate.missing.join("、")}`;
      setStatus(element.requirementsError.textContent, "error");
      return;
    }
  }
  const pack = wholeHouseStylePack();
  Object.assign(draft, {
    ...draft,
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial: draft.wallMaterial || pack.wall.surfaceOption,
    wallColor: element.questionnaireWallColor.value,
    floorMaterial: draft.floorMaterial || pack.floor.surfaceOption,
    floorColor: element.questionnaireFloorColor.value,
    ceilingMaterial: element.questionnaireCeilingMaterial.value,
    ceilingStyle: element.questionnaireCeilingStyle.value,
    lightStyle: element.questionnaireLightStyle.value,
    ceilingColor: element.questionnaireCeilingColor.value,
    airConditioning: element.questionnaireAirConditioning.value || "auto",
  });
  delete requirement.preferenceSuggestion;
  requirement.axisAnswers = {};
  const conditionalOptionIds = room.type === "bathroom"
    ? ["bathtub", "double_vanity"]
    : (room.type === "kitchen"
      ? ["large_dining_table"]
      : []);
  requirement.feasibility = conditionalOptionIds
    .map((optionId) => evaluateConditionalOption(room, optionId, state.structures.doors))
    .filter((result) => !result.feasible)
    .map((result) => ({
      optionId: result.optionId,
      forcePlacement: false,
      message: result.warnings[0],
    }));
  requirement.specialRequests = [];
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
    wallDefault: {
      materialId: draft.defaultWallMaterial || draft.wallMaterial,
      color: draft.defaultWallColor || draft.wallColor,
    },
    wallOverrides: { ...(requirement.surfaces.wallOverrides || {}), ...(draft.wallOverrides || {}) },
    floor: { materialId: draft.floorMaterial, color: draft.floorColor },
    ceiling: {
      materialId: draft.ceilingMaterial,
      styleId: draft.ceilingStyle,
      lightingId: draft.lightStyle,
      color: draft.ceilingColor,
    },
  };
  if (state.selectedQuestionnaireWallId) {
    requirement.surfaces.wallSurfaceIds = [
      ...new Set([
        ...(requirement.surfaces.wallSurfaceIds || []),
        state.selectedQuestionnaireWallId,
      ]),
    ];
  }
  requirement.confirmed = true;
  // This is intentionally non-blocking: RAG changes ranking, never room completion.
  if (state.questionnaireStage === "rooms") void startQuestionnaireRag(room);
  state.questionnaireFinishes = { ...draft };
  const scope = element.questionnaireFinishScope.value;
  const selectedRoomIds = $$("input:checked", element.questionnaireFinishRoomTargets)
    .map((input) => input.value);
  state.roomRequirementModel = applyRoomFinishScope(
    state.roomRequirementModel,
    room.id,
    scope,
    selectedRoomIds,
  );
  applyWholeHouseSurfaceConsistency();
  state.roomRequirementModel.roomRequirements[room.id].confirmed = true;
  element.requirementsError.textContent = "";
  invalidateDownstreamFrom("requirements", "風格與材質偏好已修改，後續配置需要重新產生。");
  state.activeStylePackId = pack.id;
  const nextRoom = state.rooms.find(
    (candidate) => !state.roomRequirementModel.roomRequirements[candidate.id]?.confirmed,
  );
  if (nextRoom) {
    state.roomRequirementModel.activeRoomId = nextRoom.id;
    state.selectedQuestionnaireWallId = null;
    questionnaireRuntimeState.roomSection = "usage";
    renderVisualQuestionnaire();
    scrollQuestionnaireToNextRoomStart();
    setStatus(
      `已確認「${room.label}」；接著確認「${nextRoom.label}」。`,
    );
    scheduleSave("requirements");
  } else {
    showQuestionnaireStage(state.questionnaireStage === "rooms" ? "summary" : "profile");
  }
}

const QUESTIONNAIRE_SUMMARY_AIR_CONDITIONING_LABELS = Object.freeze({
  auto: "依房間條件建議",
  "wall-split": "壁掛式冷氣",
  "ceiling-cassette": "嵌入式冷氣",
  ducted: "隱藏式冷氣",
  none: "暫不規劃冷氣",
});

const QUESTIONNAIRE_SUMMARY_CEILING_MATERIAL_LABELS = Object.freeze({
  "flat-paint": "平光乳膠漆",
  "mineral-paint": "礦物塗料",
  "wood-veneer": "木質飾面",
  "exposed-concrete": "清水混凝土",
});

function questionnaireSummarySurfaceLabel(kind, materialId) {
  if (!materialId) return "未選擇";
  const catalog = state.surfaceCatalog || state.sceneData?.surface_catalog || {};
  const surface = (catalog.surfaces || []).find(
    (candidate) => candidate.surface_id === materialId,
  );
  if (surface) return userFacingMaterialLabel(surface);

  const fallback = String(materialId)
    .replace(/^wall_json_ambientcg_wall_paint_/i, "")
    .replace(/^(?:wood|tile)_ccity_tile_flooring_/i, "")
    .replace(/_/g, " ")
    .trim();
  if (!fallback || fallback === "auto") return kind === "wall" ? "依風格建議" : "依風格建議";
  return kind === "wall" ? "已選牆面材質" : "已選地板材質";
}

function questionnaireSummaryFurnitureLabel(item) {
  const label = questionnaireFurnitureDisplayLabel(item);
  return label && !/[A-Za-z]/.test(label) ? label : "其他家具";
}

function questionnaireSummaryRoomUses(room, requirement) {
  const labels = new Map(roomUsageOptions(room).map((option) => [option.id, option.label]));
  return (requirement?.usage || [])
    .map((usage) => labels.get(usage))
    .filter(Boolean)
    .join("、") || "尚未設定";
}

function renderQuestionnaireSummary() {
  const basicRows = WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle").map((question) =>
    `<article class="rp-questionnaire-summary-card"><span>${escapeHtml(question.label)}</span><strong>${escapeHtml(state.basicAnswers[question.id] || "未填")}</strong></article>`
  ).join("");
  const wholeHouseNotes = WHOLE_HOUSE_QUESTIONS
    .filter((question) => question.type === "textarea")
    .map((question) => ({
      label: question.label,
      value: String(state.basicAnswers[question.id] || "").trim(),
    }))
    .filter((item) => item.value)
    .map((item) => `<li><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></li>`)
    .join("");
  const roomRows = state.rooms.map((room, index) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    const axes = Object.entries(requirement?.axisAnswers || {}).map(([questionId, answer]) => {
      const question = state.visualQuestions.find(
        (candidate) => candidate.source_question_id === questionId
          && String(candidate.room_id) === String(room.id),
      );
      const option = question?.options.find(
        (candidate) => candidate.option_id === answer.optionId,
      );
      const weightLabel = preferenceWeightLabel(answer.preferenceWeight);
      const answerLabel = [
        option?.label_zh || answer.optionId || "未填",
        weightLabel,
      ].filter(Boolean).join(" / ");
      return `<li><span>${escapeHtml(question?.title_zh || questionId)}</span><strong>${escapeHtml(answerLabel)}</strong></li>`;
    }).join("");
    const surfaces = normalizedRoomSurfaces(room, requirement?.surfaces || {});
    const selectedFurniture = requirement?.furniture?.selected || [];
    const deferredFurniture = requirement?.furniture?.deferred || [];
    const furniturePreference = String(requirement?.furniture?.preferenceText || "").trim();
    const furnitureTags = (requirement?.furniture?.preferenceTags || [])
      .map((tag) => String(tag).trim())
      .filter(Boolean)
      .join("、");
    const generationNotes = String(requirement?.generativeEquipment?.generationNotes || "").trim();
    const wallPreference = String(surfaces.wallPreference || "").trim();
    const floorPreference = String(surfaces.floorPreference || "").trim();
    const noteRows = [
      furniturePreference && ["家具偏好", furniturePreference],
      furnitureTags && ["偏好標籤", furnitureTags],
      wallPreference && ["牆面補充", wallPreference],
      floorPreference && ["地板補充", floorPreference],
      generationNotes && ["設計與生圖補充", generationNotes],
    ].filter(Boolean).map(([label, value]) => (
      `<li><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></li>`
    )).join("");
    const notices = (requirement?.feasibility || []).map(
      (item) => `<li>${escapeHtml(item.message || item)}</li>`,
    ).join("");
    return `
      <details class="rp-room-summary" ${index === 0 ? "open" : ""}>
        <summary>
          <span class="rp-room-summary-title"><strong>${escapeHtml(room.label)}</strong></span>
          <span class="rp-room-summary-status ${requirement?.confirmed ? "is-confirmed" : ""}">${requirement?.confirmed ? "已確認" : "待確認"}</span>
        </summary>
        <div class="rp-room-summary-body">
          <section class="rp-room-summary-item"><h4>空間用途</h4><p>${escapeHtml(questionnaireSummaryRoomUses(room, requirement))}</p></section>
          <section class="rp-room-summary-item"><h4>已選家具</h4>
            <p>${escapeHtml(selectedFurniture.map(questionnaireSummaryFurnitureLabel).join("、") || "將依需求推薦")}</p>
            ${deferredFurniture.length ? `<p>暫不放入：${escapeHtml(deferredFurniture.map(questionnaireSummaryFurnitureLabel).join("、"))}</p>` : ""}
          </section>
          <section class="rp-room-summary-item"><h4>冷氣與天花</h4>
            <p>冷氣：${escapeHtml(QUESTIONNAIRE_SUMMARY_AIR_CONDITIONING_LABELS[requirement?.climate?.airConditioning] || "依房間條件建議")}</p>
            <p>天花：${escapeHtml(QUESTIONNAIRE_SUMMARY_CEILING_MATERIAL_LABELS[surfaces.ceiling?.materialId] || "已選天花材質")}、${escapeHtml(CEILING_STYLES.find((item) => item.id === surfaces.ceiling?.styleId)?.label || "依風格建議")}、${escapeHtml(LIGHT_STYLES.find((item) => item.id === surfaces.ceiling?.lightingId)?.label || "依風格建議")}</p>
          </section>
          <section class="rp-room-summary-item"><h4>牆面與地板</h4><p>牆面：${escapeHtml(questionnaireSummarySurfaceLabel("wall", surfaces.wallDefault?.materialId))}</p><p>地板：${escapeHtml(questionnaireSummarySurfaceLabel("floor", surfaces.floor?.materialId))}</p></section>
          ${noteRows ? `<section class="rp-room-summary-notes"><h4>文字補充</h4><ul>${noteRows}</ul></section>` : ""}
          ${notices ? `<section class="needs-review"><h4>需要確認</h4><ul>${notices}</ul></section>` : ""}
        </div>
      </details>
    `;
  }).join("");
  element.questionnaireSummary.innerHTML = `
    <section class="rp-questionnaire-summary-section rp-questionnaire-summary-overview">
      <div class="rp-questionnaire-summary-heading"><h3>全屋需求</h3></div>
      <div class="rp-questionnaire-summary-grid">${basicRows}</div>
      ${wholeHouseNotes ? `<div class="rp-questionnaire-summary-notes"><h4>文字補充</h4><ul>${wholeHouseNotes}</ul></div>` : ""}
    </section>
    <section class="rp-questionnaire-summary-section"><div class="rp-questionnaire-summary-heading"><h3>各房間摘要</h3></div>${roomRows}</section>
  `;
}

function renderWholeHouseQuestionnaire() {
  const profileQuestions = WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle");
  element.wholeHouseFields.innerHTML = profileQuestions.map((question) => {
    if (question.type === "select") {
      const options = question.options.map((option) =>
        `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`
      ).join("");
      return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><select><option value="">請選擇</option>${options}</select></label>`;
    }
    return `<label data-basic-question="${escapeHtml(question.id)}"><span>${escapeHtml(question.label)}</span><textarea rows="2" placeholder="${escapeHtml(question.placeholder || "")}"></textarea></label>`;
  }).join("");
  profileQuestions.forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    const control = host?.querySelector("select, textarea");
    if (control) control.value = state.basicAnswers[question.id] || "";
  });
  renderWholeHouseStyleEditor();
}

function wholeHouseFinishDraft() {
  const fallbackPack = STYLE_PACKS.find(
    (pack) => pack.id === state.activeStylePackId,
  ) || STYLE_PACKS[0];
  const draft = state.questionnaireFinishes || {};
  return {
    stylePackId: draft.stylePackId || fallbackPack.id,
    wallMaterial: draft.wallMaterial || fallbackPack.wall.surfaceOption,
    wallColor: draft.wallColor || fallbackPack.wall.color,
    floorMaterial: draft.floorMaterial || fallbackPack.floor.surfaceOption,
    floorColor: draft.floorColor || fallbackPack.floor.color,
    ceilingMaterial: draft.ceilingMaterial || "flat-paint",
    ceilingStyle: CEILING_STYLES.some((item) => item.id === draft.ceilingStyle)
      ? draft.ceilingStyle
      : CEILING_STYLES[0].id,
    lightStyle: draft.lightStyle || LIGHT_STYLES[0].id,
    ceilingColor: draft.ceilingColor || "#f4f1eb",
    ceilingDesignStep: Number(draft.ceilingDesignStep || 1),
    airConditioning: draft.airConditioning || "auto",
    applyStyleToAllRooms: true,
    applyAirConditioningToEligibleRooms: draft.applyAirConditioningToEligibleRooms !== false,
  };
}

function renderWholeHouseStyleEditor() {
  const draft = wholeHouseFinishDraft();
  const pack = STYLE_PACKS.find((candidate) => candidate.id === draft.stylePackId) || STYLE_PACKS[0];
  state.questionnaireFinishes = { ...state.questionnaireFinishes, ...draft };
  state.activeStyleId = pack.styleId;
  element.wholeHouseStyleTabs.replaceChildren();
  element.wholeHouseStyleGrid.innerHTML = STYLE_FAMILIES.map((family) => `
    <button type="button" data-whole-house-style="${escapeHtml(family.id)}"
      data-whole-house-style-pack="${escapeHtml(family.defaultPackId)}"
      class="${family.id === pack.styleId ? "is-active" : ""}"
      aria-pressed="${family.id === pack.styleId}">
      <img class="rp-style-card-preview" src="${escapeHtml(family.referenceImage)}"
        alt="${escapeHtml(`${family.label} 台灣住宅風格參考圖`)}" loading="lazy">
      <strong>${escapeHtml(family.label)}</strong>
      <small>${escapeHtml(family.selectionCue || "")}</small>
      <em>${family.id === pack.styleId ? "已選擇此全屋風格" : "點選設為全屋風格"}</em>
    </button>
  `).join("");
  element.wholeHouseStyleSelection.textContent = `已選全屋主風格：${STYLE_FAMILIES.find((family) => family.id === pack.styleId)?.label || pack.name}。牆面、地板、天花與照明將在逐房問卷設定。`;
}

function roomFinishDraftForStyleChange(room, requirement) {
  const existing = state.roomFinishDrafts[room.id];
  if (existing) return existing;
  const surfaces = requirement.surfaces || {};
  return {
    confirmed: requirement.confirmed === true,
    materialSelectionMode: surfaces.materialSelectionMode || "auto",
    styleReviewRequired: surfaces.styleReviewRequired === true,
    stylePackId: surfaces.paletteId || null,
    wallMaterial: surfaces.wallDefault?.materialId || null,
    wallColor: surfaces.wallDefault?.color || null,
    defaultWallMaterial: surfaces.wallDefault?.materialId || null,
    defaultWallColor: surfaces.wallDefault?.color || null,
    wallOverrides: { ...(surfaces.wallOverrides || {}) },
    floorMaterial: surfaces.floor?.materialId || null,
    floorColor: surfaces.floor?.color || null,
    ceilingMaterial: surfaces.ceiling?.materialId || null,
    ceilingStyle: surfaces.ceiling?.styleId || null,
    lightStyle: surfaces.ceiling?.lightingId || null,
    ceilingColor: surfaces.ceiling?.color || "#f4f1eb",
    airConditioning: requirement.climate?.airConditioning || "auto",
  };
}

function recommendedCeilingStyleForPack(pack) {
  return CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id || CEILING_STYLES[0].id;
}

function recommendedLightStyleForPack(pack) {
  return LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id || LIGHT_STYLES[0].id;
}

function applyStyleChangeToRooms(pack) {
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (!requirement) return;
    const draft = roomFinishDraftForStyleChange(room, requirement);
    const preserveMaterials = draft.confirmed || draft.materialSelectionMode === "custom";
    const surfaces = requirement.surfaces || {};
    if (preserveMaterials) {
      Object.assign(draft, {
        stylePackId: pack.id,
        confirmed: false,
        styleReviewRequired: true,
      });
      requirement.surfaces = {
        ...surfaces,
        paletteId: pack.id,
        materialSelectionMode: "custom",
        styleReviewRequired: true,
      };
    } else {
      const recommendation = questionnaireMaterialPairsForPack(pack, room)[0];
      if (recommendation) {
        Object.assign(draft, {
          stylePackId: pack.id,
          wallMaterial: recommendation.wall.id,
          wallColor: recommendation.wall.color,
          defaultWallMaterial: recommendation.wall.id,
          defaultWallColor: recommendation.wall.color,
          wallOverrides: {},
          floorMaterial: recommendation.floor.id,
          floorColor: recommendation.floor.color,
          ceilingMaterial: draft.ceilingMaterial || "flat-paint",
          ceilingStyle: recommendedCeilingStyleForPack(pack),
          lightStyle: recommendedLightStyleForPack(pack),
          materialSelectionMode: "auto",
          confirmed: false,
          styleReviewRequired: false,
        });
        requirement.surfaces = {
          ...surfaces,
          paletteId: pack.id,
          materialSelectionMode: "auto",
          styleReviewRequired: false,
          wallDefault: { materialId: draft.wallMaterial, color: draft.wallColor },
          wallOverrides: {},
          floor: { materialId: draft.floorMaterial, color: draft.floorColor },
          ceiling: {
            ...(surfaces.ceiling || {}),
            styleId: draft.ceilingStyle,
            lightingId: draft.lightStyle,
          },
        };
      }
    }
    requirement.confirmed = false;
    state.roomFinishDrafts[room.id] = draft;
  });
}

function selectWholeHouseStylePack(packId) {
  const pack = STYLE_PACKS.find((candidate) => candidate.id === packId);
  if (!pack) return;
  const previousPackId = wholeHouseFinishDraft().stylePackId;
  const family = STYLE_FAMILIES.find((item) => item.id === pack.styleId);
  const wallOption = questionnaireMaterialOptionsForPack("wall", pack)[0];
  const floorOption = questionnaireMaterialOptionsForPack("floor", pack)[0];
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  state.questionnaireFinishes = {
    ...wholeHouseFinishDraft(),
    stylePackId: pack.id,
    wallMaterial: wallOption?.id || pack.wall.surfaceOption,
    wallColor: wallOption?.color || pack.wall.color,
    floorMaterial: floorOption?.id || pack.floor.surfaceOption,
    floorColor: floorOption?.color || pack.floor.color,
    ceilingMaterial: wholeHouseFinishDraft().ceilingMaterial || "flat-paint",
    ceilingStyle: recommendedCeilingStyleForPack(pack),
    lightStyle: recommendedLightStyleForPack(pack),
  };
  // Keep the persisted profile and the style editor in lockstep. The profile
  // is restored on reload and is also part of the RAG/render request.
  state.basicAnswers = {
    ...state.basicAnswers,
    overallStyle: family?.label || pack.name,
  };
  state.roomRequirementModel.globalProfile = {
    ...(state.roomRequirementModel.globalProfile || {}),
    overallStyle: state.basicAnswers.overallStyle,
  };
  if (previousPackId && previousPackId !== pack.id) {
    applyStyleChangeToRooms(pack);
  }
  renderWholeHouseStyleEditor();
  setStatus(`已選擇全屋主風格：${family?.label || pack.name}。`);
  scheduleSave("requirements");
}

function applyWholeHouseFinishes() {
  const draft = wholeHouseFinishDraft();
  const pack = STYLE_PACKS.find((candidate) => candidate.id === draft.stylePackId) || STYLE_PACKS[0];
  state.questionnaireFinishes = draft;
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (!requirement) return;
    const recommendation = questionnaireMaterialPairsForPack(pack, room)[0];
    const roomDraft = roomFinishDraftForStyleChange(room, requirement);
    const preserveCustomChoice = roomDraft.materialSelectionMode === "custom";
    const existing = requirement.surfaces || {};
    requirement.surfaces = {
      ...existing,
      paletteId: draft.stylePackId,
      ...(preserveCustomChoice || !recommendation ? {} : {
        wallDefault: { materialId: recommendation.wall.id, color: recommendation.wall.color },
        floor: { materialId: recommendation.floor.id, color: recommendation.floor.color },
        ceiling: {
          materialId: roomDraft.ceilingMaterial || "flat-paint",
          styleId: recommendedCeilingStyleForPack(pack),
          lightingId: recommendedLightStyleForPack(pack),
          color: roomDraft.ceilingColor || "#f4f1eb",
        },
      }),
    };
    requirement.climate = {
      ...(requirement.climate || {}),
      airConditioning: requirement.climate?.airConditioning || "auto",
    };
    state.roomFinishDrafts[room.id] = {
      ...roomDraft,
      stylePackId: draft.stylePackId,
      wallMaterial: preserveCustomChoice ? roomDraft.wallMaterial : recommendation?.wall.id,
      wallColor: preserveCustomChoice ? roomDraft.wallColor : recommendation?.wall.color,
      floorMaterial: preserveCustomChoice ? roomDraft.floorMaterial : recommendation?.floor.id,
      floorColor: preserveCustomChoice ? roomDraft.floorColor : recommendation?.floor.color,
      ceilingMaterial: preserveCustomChoice ? roomDraft.ceilingMaterial : (roomDraft.ceilingMaterial || "flat-paint"),
      ceilingStyle: preserveCustomChoice ? roomDraft.ceilingStyle : recommendedCeilingStyleForPack(pack),
      lightStyle: preserveCustomChoice ? roomDraft.lightStyle : recommendedLightStyleForPack(pack),
      airConditioning: requirement.climate.airConditioning,
      confirmed: preserveCustomChoice ? roomDraft.confirmed : false,
    };
  });
}

function collectBasicAnswers() {
  const answers = {};
  WHOLE_HOUSE_QUESTIONS.filter((question) => question.id !== "overallStyle").forEach((question) => {
    const host = $(`[data-basic-question="${question.id}"]`);
    answers[question.id] = host?.querySelector("select, textarea")?.value.trim() || "";
  });
  const selectedFamily = STYLE_FAMILIES.find((family) => family.id === state.activeStyleId);
  answers.overallStyle = selectedFamily?.label || "";
  return answers;
}

async function confirmBasicQuestionnaire() {
  element.requirementsError.textContent = "";
  const answers = collectBasicAnswers();
  state.basicAnswers = answers;
  state.basicConfirmed = true;
  state.roomRequirementModel.globalProfile = { ...answers };
  state.roomRequirementModel.globalConfirmed = true;
  applyWholeHouseFinishes();
  invalidateDownstreamFrom(
    "requirements",
    "全屋風格與材質已確認，後續配置需要依完整需求重新產生。",
  );
  showQuestionnaireStage("rooms");
  scheduleSave("requirements");
}

function clearRequirementsGenerationHelp() {
  element.requirementsGenerationHelp?.setAttribute("hidden", "");
  if (element.requirementsGenerationHelpDetail) {
    element.requirementsGenerationHelpDetail.textContent = "";
  }
}

function showRequirementsGenerationHelp(detail) {
  if (!element.requirementsGenerationHelp || !element.requirementsGenerationHelpDetail) return;
  element.requirementsGenerationHelpDetail.textContent = detail;
  element.requirementsGenerationHelp.removeAttribute("hidden");
}

async function configurationCatalogReadiness() {
  try {
    const status = await api("/api/catalog/status");
    const catalog = status.catalog_provider || {};
    if (catalog.ready === false || catalog.available === false) {
      return {
        ready: false,
        reason: String(catalog.reason || "catalog_unavailable"),
      };
    }
    return { ready: true };
  } catch (error) {
    return { ready: false, reason: errorMessage(error) };
  }
}

async function confirmRequirements() {
  if (state.requirementsGenerationPending) {
    const message = "配置仍在建立中，請稍候。";
    element.requirementsError.textContent = message;
    setStatus(message, "warning");
    return;
  }
  state.requirementsGenerationPending = true;
  state.lastWhiteModelGenerationError = "";
  element.confirmRequirements?.setAttribute("aria-busy", "true");
  element.confirmRequirements?.setAttribute("disabled", "disabled");
  beginPlacementBusy("AI 正在為每間房挑選並擺放家具，請稍候…");
  try {
    await confirmRequirementsInternal();
  } catch (error) {
    const message = errorMessage(error);
    element.requirementsError.textContent = message;
    showRequirementsGenerationHelp(`建立配置時發生錯誤：${message}`);
    setStatus(message, "error");
  } finally {
    state.requirementsGenerationPending = false;
    element.confirmRequirements?.removeAttribute("aria-busy");
    element.confirmRequirements?.removeAttribute("disabled");
    endPlacementBusy();
  }
}

async function confirmRequirementsInternal() {
  element.requirementsError.textContent = "";
  clearRequirementsGenerationHelp();
  setStatus("正在依每個房間的需求搜尋可配置家具…");
  await settleQuestionnaireRagForLayout();
  const requirementsPayload = buildRoomRequirementsPayload(
    state.roomRequirementModel,
    {
      planGeometry: {
        rooms: state.rooms,
        structures: state.structures,
      },
      questionnaireVersion: state.visualCatalogVersion,
    },
  );
  if (!requirementsPayload.readyForRag) {
    element.requirementsError.textContent = "請先完成所有房間需求與材質，再確認全屋資料。";
    return;
  }
  const catalogReadiness = await configurationCatalogReadiness();
  if (!catalogReadiness.ready) {
    const message = "目前無法連線 Kai 家具型錄，尚未取得所選家具的可用 GLB，因此不能建立可靠的 2D+3D 配置。";
    element.requirementsError.textContent = message;
    showRequirementsGenerationHelp(`${message} 系統回報：${catalogReadiness.reason}。`);
    setStatus("Kai 家具型錄尚未就緒，已保留問卷答案並停止建立配置。", "error");
    return false;
  }
  try {
    setStatus("正在檢查空間規則並建立家具配置…");
    await autoLayoutFurniture();
    state.workflow.complete("requirements", {
      basicConfirmed: true,
      roomsResolved: true,
      visualPreferencesResolved: true,
      finishesConfirmed: true,
    });
    renderFurnitureLibrary();
    setStatus("正在載入資料庫家具與 3D 場景…");
    const generated = await generateWhiteModelFromRequirements({
      returnToRequirementsOnFailure: true,
    });
    if (!generated && !element.requirementsError.textContent.trim()) {
      const message = state.lastWhiteModelGenerationError
        || element.layoutError.textContent.trim()
        || "第 6 步沒有產生場景資料。請重新檢查型錄與平面圖後再試。";
      element.requirementsError.textContent = message;
      showRequirementsGenerationHelp(`建立配置未完成：${message}`);
    }
  } catch (error) {
    element.requirementsError.textContent = errorMessage(error);
    showRequirementsGenerationHelp(`系統回報：${errorMessage(error)}。`);
    setStatus(errorMessage(error), "error");
  }
}

  return {
    activeQuestionnairePack,
    activeQuestionnaireRoom,
    activeRoomFinishDraft,
    activeRoomRequirement,
    addMaterialDisplayOrdinals,
    answerWeightDirection,
    applyRandomRoomRequirement,
    applyStyleChangeToRooms,
    applyWholeHouseFinishes,
    applyWholeHouseSurfaceConsistency,
    catalogMaterialOptionsForPack,
    catalogSurfaceIsUsableInRoom,
    ceilingPickerItems,
    circulationStyleIsOverridden,
    clearRequirementsGenerationHelp,
    collectBasicAnswers,
    configurationCatalogReadiness,
    confirmBasicQuestionnaire,
    confirmQuestionnaireFinishes,
    confirmRequirements,
    confirmRequirementsInternal,
    copyLivingRoomStyleToCirculation,
    ensureQuestionnaireRoomActionBar,
    ensureVisualQuestionnaireLoaded,
    INDEPENDENT_FLOOR_LABEL_PATTERNS,
    INDEPENDENT_FLOOR_ROOM_TYPES,
    isBathroomRoom,
    isCirculationRoom,
    isHighChromaMaterial,
    isMosaicSurface,
    isPoolSurface,
    isWetAreaRoom,
    livingRoomForCirculation,
    MATERIAL_COLOR_LABELS,
    MATERIAL_TYPE_LABELS,
    materialCatalogChroma,
    materialCatalogColor,
    materialCatalogText,
    materialCatalogType,
    materialOptionForPack,
    materialPairScore,
    materialVisualTagMarkup,
    materialVisualTags,
    moveQuestionnaireRoomSection,
    moveVisualQuestion,
    normalizedRoomSurfaces,
    normalizeSavedSceneWallSurfaces,
    openQuestionnaireCeilingDesignStyle,
    openQuestionnaireCeilingPicker,
    PREFERENCE_WEIGHT_OPTIONS,
    preferenceWeightFromOption,
    preferenceWeightLabel,
    prepareQuestionnaireStep,
    QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT,
    QUESTIONNAIRE_ROOM_SECTIONS,
    QUESTIONNAIRE_STAGES,
    QUESTIONNAIRE_SUMMARY_AIR_CONDITIONING_LABELS,
    QUESTIONNAIRE_SUMMARY_CEILING_MATERIAL_LABELS,
    questionnaireMaterialOptionsForPack,
    questionnaireMaterialPairCards,
    questionnaireMaterialPairsForPack,
    questionnaireRoomEditorElements,
    questionnaireStageUnlocked,
    questionnaireSummaryFurnitureLabel,
    questionnaireSummaryRoomUses,
    questionnaireSummarySurfaceLabel,
    questionnaireUsageSummary,
    randomAnswerForQuestion,
    randomItem,
    randomizeRequirementsForTesting,
    randomRoomAxisNote,
    randomRoomFinishDraft,
    randomWholeHouseAnswers,
    recommendedCeilingStyleForPack,
    recommendedLightStyleForPack,
    renderConditionalFeasibility,
    renderMaterialFilterChips,
    renderQuestionnaireCeilingQuickChoices,
    renderQuestionnaireFinishes,
    renderQuestionnaireMaterialCatalog,
    renderQuestionnaireMaterialOptions,
    renderQuestionnaireMaterialPairs,
    renderQuestionnairePlan,
    renderQuestionnaireRoomReview,
    renderQuestionnaireRoomSections,
    renderQuestionnaireSummary,
    renderVisualQuestionnaire,
    renderVisualSpaceNav,
    renderWholeHouseQuestionnaire,
    renderWholeHouseStyleEditor,
    repairAutomaticMaterialRecommendation,
    resolvedVisualPreferences,
    ROOM_REQUIREMENT_POLAR_AXES,
    roomAllowsIndependentFloor,
    roomFinishDraftForStyleChange,
    roomQuestionnaireProgress,
    roomQuestionnaireSectionProgress,
    saveVisualCustomAnswer,
    scrollQuestionnaireToNextRoomStart,
    selectPreferenceWeight,
    selectQuestionnaireCeilingDesignPack,
    selectQuestionnaireCeilingPickerItem,
    selectQuestionnaireMaterial,
    selectQuestionnaireMaterialPair,
    selectQuestionnaireStylePack,
    selectStepSixCatalogMaterial,
    selectVisualOption,
    selectWholeHouseStylePack,
    showQuestionnaireStage,
    showRequirementsGenerationHelp,
    skipQuestionnaireWithDefaults,
    stableStringNumber,
    STYLE_MATERIAL_RULES,
    styleCompatibleMaterialOptionsForPack,
    synchronizeCirculationStyles,
    TEST_AIR_CONDITIONING_OPTIONS,
    TEST_REQUIREMENT_PROFILE_NOTES,
    trimAccentWallSurfaces,
    userFacingMaterialLabel,
    visualPreferencesForRoom,
    visualQuestionAt,
    weightedOptionId,
    wholeHouseFinishDraft,
    wholeHouseMainFloorSurface,
    wholeHouseMainWallSurface,
    wholeHouseStylePack,
  };
}
