const STYLE_LABELS = Object.freeze({
  scandinavian: "北歐風",
  japanese: "日式風",
  modern_minimal: "現代簡約",
  cream: "奶油風",
  industrial: "工業風",
  american: "美式風",
});

const ROOM_LABELS = Object.freeze({
  living_room: "客廳",
  dining_room: "餐廳",
  bedroom: "臥室",
  master_bedroom: "主臥",
  kitchen: "廚房",
  bathroom: "浴室",
  toilet: "浴室",
  balcony: "陽台",
  storage: "儲藏室",
  circulation: "走道",
});

const ROOM_CATEGORY_PRIORITY = Object.freeze({
  bathroom: ["tile", "stone", "microcement", "paint"],
  toilet: ["tile", "stone", "microcement", "paint"],
  kitchen: ["tile", "stone", "microcement", "paint", "wood"],
  balcony: ["tile", "stone", "concrete", "microcement"],
  bedroom: ["wood", "paint", "plaster", "fabric", "tile"],
  master_bedroom: ["wood", "paint", "plaster", "fabric", "tile"],
  living_room: ["wood", "paint", "plaster", "stone", "tile"],
  dining_room: ["wood", "paint", "stone", "tile"],
  storage: ["paint", "wood", "tile"],
  circulation: ["tile", "wood", "stone", "paint"],
});

const WET_ROOM_FLOOR_CATEGORIES = new Set(["tile", "wood_tile"]);

const ROOM_REASON = Object.freeze({
  bathroom: "浴室先推薦常見的磁磚與石材視覺；防滑、耐潮等級仍須查產品規格。",
  toilet: "浴室先推薦常見的磁磚與石材視覺；防滑、耐潮等級仍須查產品規格。",
  kitchen: "廚房先推薦常見的磁磚與石材視覺；耐污與耐熱仍須查產品規格。",
  balcony: "陽台先推薦常見的磁磚與石材視覺；防水、止滑與耐候仍須查產品規格。",
  bedroom: "臥室先依目前風格推薦木質與低彩度視覺，實際性能仍須查產品規格。",
  master_bedroom: "主臥先依目前風格推薦木質與低彩度視覺，實際性能仍須查產品規格。",
  living_room: "客廳先依目前風格、色調與家具搭配推薦。",
  dining_room: "餐廳先依目前風格與餐廚色調銜接推薦，實際性能仍須查產品規格。",
  storage: "儲藏室先依目前風格與常見耐用視覺推薦，實際性能仍須查產品規格。",
  circulation: "走道先依目前風格與視覺延伸推薦；耐磨、止滑仍須查產品規格。",
});

const ROOM_TYPE_ALIASES = Object.freeze({
  dormitory: "bedroom",
  master_bedroom: "bedroom",
  deposit: "storage",
  living: "living_room",
  dining: "dining_room",
  toilet: "bathroom",
  washroom: "bathroom",
  corridor: "circulation",
  hallway: "circulation",
});

const STYLE_PROFILE_KEYS = Object.freeze({
  scandinavian: ["scandinavian", "nordic_modern"],
  japanese: ["wabi_sabi", "minimalist_muji"],
  modern_minimal: ["modern", "nordic_modern", "minimalist_muji"],
  cream: ["light_luxury", "melad"],
  industrial: ["industrial", "modern"],
  american: ["american", "american_country", "classical", "light_luxury"],
});

const STYLE_PACK_PROFILE_KEYS = Object.freeze({
  scandinavian_1: ["scandinavian"],
  scandinavian_2: ["nordic_modern", "scandinavian"],
  scandinavian_3: ["nordic_modern", "modern"],
  japanese_1: ["wabi_sabi"],
  japanese_2: ["wabi_sabi", "classical"],
  japanese_3: ["minimalist_muji", "modern"],
  modern_minimal_1: ["modern"],
  modern_minimal_2: ["modern", "light_luxury"],
  modern_minimal_3: ["minimalist_muji", "nordic_modern"],
  cream_1: ["melad"],
  cream_2: ["classical", "light_luxury"],
  cream_3: ["melad", "american_country"],
  industrial_1: ["industrial"],
  industrial_2: ["industrial", "eclectic"],
  industrial_3: ["industrial", "modern"],
  american_1: ["american_country", "american"],
  american_2: ["classical", "american"],
  american_3: ["light_luxury", "american"],
});

const SURFACE_OPTION_KEYWORDS = Object.freeze({
  warm_white: ["paint", "plaster", "塗料", "灰泥"],
  limewash: ["plaster", "paint", "microcement", "灰泥", "塗料", "礦物"],
  light_gray: ["concrete", "paint", "plaster", "水泥", "塗料", "灰泥"],
  charcoal: ["concrete", "paint", "brick", "水泥", "塗料", "磚"],
  light_oak: ["wood", "oak", "木"],
  walnut: ["wood", "walnut", "胡桃", "木"],
  stone_gray: ["stone", "tile", "concrete", "石", "磚", "水泥"],
  marble: ["marble", "stone", "tile", "大理石", "石", "磚"],
  microcement: ["microcement", "concrete", "cement", "微水泥", "水泥"],
});

function clampUnit(value) {
  return Math.max(0, Math.min(1, Number(value) || 0));
}

function rounded(value) {
  return Math.round(value * 10_000) / 10_000;
}

function surfaceCategory(surface) {
  return String(surface.category || surface.material_group || "").toLowerCase();
}

function styleFamilyFromCardId(styleId) {
  return String(styleId || "").replace(/_\d+$/, "");
}

function canonicalRoomType(roomType) {
  const normalized = String(roomType || "").toLowerCase();
  return ROOM_TYPE_ALIASES[normalized] || normalized;
}

export function isSurfaceEligibleForRoom(surface, usage, roomType) {
  if (
    !surface?.surface_id
    || !Array.isArray(surface.usage)
    || !surface.usage.includes(usage)
  ) {
    return false;
  }
  if (
    usage === "floor"
    && ["bathroom", "kitchen", "balcony"].includes(canonicalRoomType(roomType))
  ) {
    // This is a catalog eligibility boundary, not a recommendation bonus.
    // Individual products still need their slip, water and weather ratings
    // verified before specification.
    return WET_ROOM_FLOOR_CATEGORIES.has(surfaceCategory(surface));
  }
  return true;
}

export function validateSurfaceSelectionForRooms({
  rooms = [],
  targetRoomId = "all",
  selection = {},
  surfaceLookup = () => null,
} = {}) {
  const targets = targetRoomId === "all"
    ? rooms
    : rooms.filter((room) => room?.id === targetRoomId);
  const invalid = [];
  targets.forEach((room) => {
    [
      ["wall", selection.wallSurfaceId],
      ["floor", selection.floorSurfaceId],
    ].forEach(([usage, surfaceId]) => {
      if (
        !isSurfaceEligibleForRoom(
          surfaceLookup(surfaceId),
          usage,
          room?.type,
        )
      ) {
        invalid.push({
          roomId: String(room?.id || ""),
          roomLabel: String(room?.label || room?.id || "目前房間"),
          usage,
          surfaceId: String(surfaceId || ""),
        });
      }
    });
  });
  return {
    valid: invalid.length === 0,
    invalid,
  };
}

function normalizedHexColor(value) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(value || "").trim());
  if (!match) return null;
  return {
    r: Number.parseInt(match[1].slice(0, 2), 16),
    g: Number.parseInt(match[1].slice(2, 4), 16),
    b: Number.parseInt(match[1].slice(4, 6), 16),
  };
}

function colorSimilarityScore(left, right) {
  const a = normalizedHexColor(left);
  const b = normalizedHexColor(right);
  if (!a || !b) return 0;
  const distance = Math.hypot(a.r - b.r, a.g - b.g, a.b - b.b);
  return Math.max(0, Math.round((1 - distance / Math.sqrt(3 * 255 ** 2)) * 24));
}

function variantAffinityScore(stylePackId, surfaceId) {
  if (!/_\d+$/.test(String(stylePackId || ""))) return 0;
  // The source catalog intentionally keeps color metadata coarse. This stable,
  // low-weight affinity keeps three colorways from collapsing to one identical
  // page while the room, style, material and color scores remain dominant.
  const value = `${stylePackId}:${surfaceId}`;
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) % 401 / 100;
}

function recommendationProfileKeys(styleId, stylePack) {
  const packId = String(stylePack?.id || styleId || "");
  const family = String(stylePack?.styleId || styleFamilyFromCardId(packId));
  return [
    ...(STYLE_PACK_PROFILE_KEYS[packId] || []),
    ...(STYLE_PROFILE_KEYS[family] || [family]),
  ].filter((profile, index, profiles) => profile && profiles.indexOf(profile) === index);
}

function profileSurfaceRanks(styleProfiles, profileKeys, usage) {
  const ranks = new Map();
  const property = usage === "wall" ? "wall_surface_ids" : "floor_surface_ids";
  profileKeys.forEach((profileKey, profileIndex) => {
    const ids = styleProfiles?.[profileKey]?.[property] || [];
    ids.forEach((surfaceId, surfaceIndex) => {
      const rank = profileIndex * 12 + surfaceIndex;
      if (!ranks.has(surfaceId) || rank < ranks.get(surfaceId)) {
        ranks.set(surfaceId, rank);
      }
    });
  });
  return ranks;
}

function preferredSurfaceMatches(surface, preferredOption) {
  if (["light_oak", "walnut"].includes(String(preferredOption || ""))) {
    return surfaceCategory(surface) === "wood";
  }
  const keywords = SURFACE_OPTION_KEYWORDS[String(preferredOption || "")] || [];
  if (!keywords.length) return false;
  const searchText = [
    surface.category,
    surface.material_group,
    surface.name_zh,
    surface.style_notes_zh,
  ].join(" ").toLowerCase();
  return keywords.some((keyword) => searchText.includes(keyword));
}

export function groupStylePacks(stylePacks = []) {
  const grouped = new Map();
  stylePacks.forEach((pack) => {
    if (!pack?.styleId || !pack?.id) return;
    if (!grouped.has(pack.styleId)) {
      grouped.set(pack.styleId, {
        id: pack.styleId,
        label: pack.styleLabel || STYLE_LABELS[pack.styleId] || pack.styleId,
        packs: [],
      });
    }
    grouped.get(pack.styleId).packs.push(pack);
  });
  return [...grouped.values()];
}

export function applySurfaceSelectionToRooms({
  preferences = {},
  roomIds = [],
  targetRoomId = "all",
  selection = {},
} = {}) {
  const selectedSurface = {
    wallSurfaceId: String(selection.wallSurfaceId || ""),
    floorSurfaceId: String(selection.floorSurfaceId || ""),
    wallColor: String(selection.wallColor || "#f4efe4"),
    floorColor: String(selection.floorColor || "#c9a77d"),
  };
  const rooms = { ...(preferences.rooms || {}) };
  const targetRoomIds = targetRoomId === "all"
    ? roomIds
    : [targetRoomId];
  targetRoomIds
    .filter(Boolean)
    .forEach((roomId) => {
      rooms[roomId] = {
        ...(rooms[roomId] || {}),
        surfaceOverride: { ...selectedSurface },
      };
    });
  return {
    ...preferences,
    ...(targetRoomId === "all" ? { wholeHouse: { ...selectedSurface } } : {}),
    rooms,
  };
}

export function applyStylePackPreference({
  preferences = {},
  stylePack = null,
} = {}) {
  if (!stylePack?.id) return { ...preferences };
  const currentWholeHouse = preferences.wholeHouse || {};
  const wallColor = stylePack.wall?.color
    || currentWholeHouse.wallColor
    || "#f4efe4";
  const floorColor = stylePack.floor?.color
    || currentWholeHouse.floorColor
    || "#c9a77d";
  const rooms = Object.fromEntries(
    Object.entries(preferences.rooms || {}).map(([roomId, roomPreferences]) => {
      const current = roomPreferences || {};
      const override = current.surfaceOverride || {};
      const inheritsWholeHouse = current.confirmed !== true
        && !current.materialBoundary
        && ["wallSurfaceId", "floorSurfaceId", "wallColor", "floorColor"].every(
          (key) => String(override[key] || "") === String(currentWholeHouse[key] || ""),
        );
      if (!inheritsWholeHouse) return [roomId, current];
      return [roomId, {
        ...current,
        surfaceOverride: {
          ...override,
          wallColor,
          floorColor,
        },
      }];
    }),
  );
  return {
    ...preferences,
    styleId: stylePack.id,
    styleConfirmed: true,
    wholeHouse: {
      ...currentWholeHouse,
      wallColor,
      floorColor,
    },
    rooms,
  };
}

export function rankSurfaceCatalog({
  surfaces = [],
  usage = "floor",
  roomType = "living_room",
  styleId = "",
  stylePack = null,
  styleProfiles = {},
  limit = 36,
} = {}) {
  const canonicalType = canonicalRoomType(roomType);
  const family = String(stylePack?.styleId || styleFamilyFromCardId(styleId));
  const profileKeys = recommendationProfileKeys(styleId, stylePack);
  const profileRanks = profileSurfaceRanks(styleProfiles, profileKeys, usage);
  const styleDescriptor = [stylePack?.styleLabel, stylePack?.name].filter(Boolean).join("・");
  const preferredSurfaceOption = (
    usage === "floor"
    && String(stylePack?.id || styleId) === "modern_minimal_2"
  )
    ? "light_oak"
    : stylePack?.[usage]?.surfaceOption || "";
  const targetColor = stylePack?.[usage]?.color
    || stylePack?.palette?.[usage === "wall" ? 0 : 2]
    || "";
  const categoryPriority = ROOM_CATEGORY_PRIORITY[canonicalType] || [];
  const roomLabel = ROOM_LABELS[canonicalType] || "此空間";
  const roomReason = ROOM_REASON[canonicalType] || `${roomLabel}依耐用性與整體風格推薦。`;
  const ranked = surfaces
    .filter((surface) => (
      surface?.surface_id
      && (surface.texture_url || surface.preview_url)
      && isSurfaceEligibleForRoom(surface, usage, canonicalType)
    ))
    .map((surface, sourceIndex) => {
      const category = surfaceCategory(surface);
      const categoryIndex = categoryPriority.findIndex(
        (candidate) => category.includes(candidate),
      );
      const styleMatched = (surface.suitable_styles || []).some(
        (candidate) => (
          candidate === family
          || profileKeys.includes(candidate)
          || family.includes(candidate)
        ),
      );
      const categoryScore = categoryIndex >= 0
        ? 50 - categoryIndex * 7
        : 0;
      const profileRank = profileRanks.get(surface.surface_id);
      const profileScore = Number.isInteger(profileRank)
        ? Math.max(10, 34 - Math.min(profileRank, 24))
        : 0;
      const optionMatched = preferredSurfaceMatches(surface, preferredSurfaceOption);
      const optionScore = optionMatched ? 28 : 0;
      const colorScore = colorSimilarityScore(surface.color_hex, targetColor);
      const affinityScore = variantAffinityScore(
        stylePack?.id || styleId,
        surface.surface_id,
      );
      const score = categoryScore
        + (styleMatched ? 20 : 0)
        + profileScore
        + optionScore
        + colorScore;
      const reasons = [];
      if (categoryIndex >= 0) reasons.push(roomReason);
      if (styleDescriptor && (styleMatched || profileScore || optionMatched || colorScore >= 16)) {
        reasons.push(`符合「${styleDescriptor}」色卡的色調與材質方向。`);
      } else if (styleMatched) {
        reasons.push("也符合目前選擇的整體風格。");
      }
      if (!reasons.length) reasons.push(`${roomLabel}可使用，請再依實品與施工條件確認。`);
      return {
        ...surface,
        recommendationScore: score,
        recommendationReason: reasons.join(""),
        _affinityScore: affinityScore,
        _sourceIndex: sourceIndex,
      };
    })
    .sort((left, right) => (
      right.recommendationScore - left.recommendationScore
      || right._affinityScore - left._affinityScore
      || left._sourceIndex - right._sourceIndex
    ))
    .slice(0, Math.max(1, Number(limit) || 36))
    .map(({ _affinityScore, _sourceIndex, ...surface }) => surface);
  return ranked.map((surface, index) => ({
    ...surface,
    recommended: index < 6 && surface.recommendationScore > 0,
  }));
}

export function paginateSurfaceCatalog(
  surfaces = [],
  { page = 1, pageSize = 6 } = {},
) {
  const normalizedPageSize = Math.max(1, Math.min(24, Math.floor(Number(pageSize) || 6)));
  const totalItems = Array.isArray(surfaces) ? surfaces.length : 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / normalizedPageSize));
  const normalizedPage = Math.max(
    1,
    Math.min(totalPages, Math.floor(Number(page) || 1)),
  );
  const startIndex = (normalizedPage - 1) * normalizedPageSize;
  const items = (Array.isArray(surfaces) ? surfaces : []).slice(
    startIndex,
    startIndex + normalizedPageSize,
  );
  return {
    items,
    page: normalizedPage,
    pageSize: normalizedPageSize,
    totalItems,
    totalPages,
    hasPrevious: normalizedPage > 1,
    hasNext: normalizedPage < totalPages,
  };
}

export function createMaterialBoundary({
  surface = "floor",
  wallFace = "north",
  start = { x: 0.5, y: 0.15 },
  end = { x: 0.5, y: 0.85 },
  primarySurfaceId = "",
  primaryColor = "#f4efe4",
  secondarySurfaceId = "",
  secondaryColor = "#8b684b",
} = {}) {
  const normalizedStart = {
    x: rounded(clampUnit(start.x)),
    y: rounded(clampUnit(start.y)),
  };
  const normalizedEnd = {
    x: rounded(clampUnit(end.x)),
    y: rounded(clampUnit(end.y)),
  };
  const horizontal = Math.abs(normalizedEnd.x - normalizedStart.x)
    >= Math.abs(normalizedEnd.y - normalizedStart.y);
  const direction = horizontal ? "horizontal" : "vertical";
  const drawnRatio = rounded(
    direction === "horizontal"
      ? (normalizedStart.y + normalizedEnd.y) / 2
      : (normalizedStart.x + normalizedEnd.x) / 2,
  );
  const ratio = direction === "horizontal"
    ? rounded(1 - drawnRatio)
    : drawnRatio;
  return {
    schemaVersion: "1.1",
    mode: "free_line",
    surface: surface === "wall" ? "wall" : "floor",
    wallFace: surface === "wall" ? String(wallFace || "north") : null,
    direction,
    coordinateSpace: "room-relative-ratio",
    coordinateUnit: "ratio",
    splitRatio: ratio,
    primarySurfaceId: String(primarySurfaceId || ""),
    primaryColor: String(primaryColor || "#f4efe4"),
    secondarySurfaceId: String(secondarySurfaceId || ""),
    secondaryColor: String(secondaryColor || "#8b684b"),
  };
}

export function roomMaterialCompletion(
  roomPreferences = {},
  { roomType = "", surfaceLookup = null } = {},
) {
  const override = roomPreferences.surfaceOverride || {};
  const missing = [];
  if (!override.wallSurfaceId) missing.push("wall");
  if (!override.floorSurfaceId) missing.push("floor");
  if (typeof surfaceLookup === "function") {
    if (
      override.wallSurfaceId
      && !isSurfaceEligibleForRoom(
        surfaceLookup(override.wallSurfaceId),
        "wall",
        canonicalRoomType(roomType),
      )
    ) {
      missing.push("wall_ineligible");
    }
    if (
      override.floorSurfaceId
      && !isSurfaceEligibleForRoom(
        surfaceLookup(override.floorSurfaceId),
        "floor",
        canonicalRoomType(roomType),
      )
    ) {
      missing.push("floor_ineligible");
    }
    const boundary = roomPreferences.materialBoundary;
    if (boundary?.secondarySurfaceId && ["wall", "floor"].includes(boundary.surface)) {
      if (
        !isSurfaceEligibleForRoom(
          surfaceLookup(boundary.secondarySurfaceId),
          boundary.surface,
          canonicalRoomType(roomType),
        )
      ) {
        missing.push(`secondary_${boundary.surface}_ineligible`);
      }
    }
  }
  if (roomPreferences.confirmed !== true) missing.push("confirmation");
  return {
    complete: missing.length === 0,
    missing,
  };
}
