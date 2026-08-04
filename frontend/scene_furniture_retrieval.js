export const FURNITURE_BY_IDS_BATCH_SIZE = 500;

export function chunkUniqueFurnitureItemIds(itemIds = [], batchSize = FURNITURE_BY_IDS_BATCH_SIZE) {
  const safeBatchSize = Math.max(1, Number(batchSize) || FURNITURE_BY_IDS_BATCH_SIZE);
  const uniqueIds = [...new Set(itemIds.filter(Boolean).map((itemId) => String(itemId)))];
  const batches = [];
  for (let index = 0; index < uniqueIds.length; index += safeBatchSize) {
    batches.push(uniqueIds.slice(index, index + safeBatchSize));
  }
  return batches;
}

function normalizedTokens(values) {
  return (Array.isArray(values) ? values : [values])
    .flatMap((value) => String(value || "").toLowerCase().split(/[\s,/_-]+/))
    .filter(Boolean);
}

function hexRgb(value) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(value || "").trim());
  if (!match) return null;
  const numeric = Number.parseInt(match[1], 16);
  return {
    r: (numeric >> 16) & 255,
    g: (numeric >> 8) & 255,
    b: numeric & 255,
  };
}

function colorScore(candidateColor, palette) {
  const candidate = hexRgb(candidateColor);
  const colors = (palette || []).map(hexRgb).filter(Boolean);
  if (!candidate || !colors.length) return 0;
  const distance = Math.min(...colors.map((color) => Math.sqrt(
    (candidate.r - color.r) ** 2
      + (candidate.g - color.g) ** 2
      + (candidate.b - color.b) ** 2,
  )));
  return Math.max(0, 24 - distance / 12);
}

function materialScore(candidate, requestedMaterials) {
  const requested = new Set(normalizedTokens(requestedMaterials));
  if (!requested.size) return 0;
  const candidateTokens = normalizedTokens([
    candidate.material,
    candidate.materials,
    candidate.name_en,
    candidate.name_zh,
    candidate.name_zh_raw,
  ]);
  return candidateTokens.some((token) => requested.has(token)) ? 32 : 0;
}

function sizeScore(candidate, request) {
  const width = Number(candidate.size_cm?.width || 0);
  const depth = Number(candidate.size_cm?.depth || 0);
  const requestedWidth = Number(request.widthCm || 0);
  const requestedDepth = Number(request.depthCm || 0);
  if (!width || !depth || !requestedWidth || !requestedDepth) return 0;
  const relativeDelta = (
    Math.abs(width - requestedWidth) / requestedWidth
      + Math.abs(depth - requestedDepth) / requestedDepth
  ) / 2;
  return Math.max(0, 28 * (1 - relativeDelta));
}

function roomTypeScore(candidate, request) {
  const roomType = String(request.roomType || "").toLowerCase();
  if (!roomType) return 0;
  const roomTypes = normalizedTokens(candidate.room_types);
  return roomTypes.includes(roomType) ? 44 : 0;
}

function roleScore(candidate, request) {
  const role = String(candidate.catalog_role || candidate.role || "").toLowerCase();
  if (!role) return 0;
  if (request.preferAnchor === true && role === "anchor") return 20;
  if (["anchor", "functional", "storage", "task"].includes(role)) return 12;
  return 0;
}

function semanticTextScore(candidate, request) {
  const queryTokens = new Set(normalizedTokens([
    request.queryText,
    request.roomLabel,
    request.materials,
    request.styleId,
    request.type,
  ]));
  if (!queryTokens.size) return 0;
  const candidateTokens = new Set(normalizedTokens([
    candidate.rag_text,
    candidate.description,
    candidate.search_keywords,
    candidate.features,
    candidate.mood_tags,
    candidate.object_type_zh,
    candidate.name_en,
    candidate.name_zh,
    candidate.name_zh_raw,
  ]));
  let hits = 0;
  queryTokens.forEach((token) => {
    if (candidateTokens.has(token)) hits += 1;
  });
  return Math.min(36, hits * 9);
}

const PRODUCT_NAME_RULES = {
  sofa: {
    positive: ["sofa", "couch", "loveseat", "settee"],
    negative: ["dining chair", "accent chair", "dresser", "bed frame", "headboard"],
  },
  bed: {
    positive: [" bed", "bed frame", "daybed", "loft bed"],
    negative: ["dresser", "lamp", "table"],
  },
  "mirror-cabinet": {
    positive: ["mirror cabinet", "doormirror cabinet"],
    negative: ["extractor", "hood"],
  },
  washer: {
    positive: ["washing machine", "washer dryer", "washer/dryer"],
    negative: ["pedestal", "sewing machine", "ironing", " iron", "belt-like"],
  },
  refrigerator: {
    positive: ["fridge", "freezer", "refrigerator"],
    negative: [],
  },
  "bathroom-vanity": {
    positive: ["bathroom storage cabinet", "vanity cabinet", "sink cabinet"],
    negative: ["vanity light", "lamp"],
  },
  "storage-cabinet": {
    positive: ["storage cabinet", "cupboard", "sideboard"],
    negative: ["heater"],
  },
  "appliance-cabinet": {
    positive: ["kitchen cart", "cabinet", "cupboard"],
    negative: ["heater"],
  },
};

function productNameScore(candidate, requestedType) {
  const rules = PRODUCT_NAME_RULES[requestedType];
  if (!rules) return 0;
  const name = String(
    candidate.name_en || candidate.name_zh || candidate.name_zh_raw || "",
  ).toLowerCase();
  const positive = rules.positive.some((keyword) => name.includes(keyword));
  const negative = rules.negative.some((keyword) => name.includes(keyword));
  return (positive ? 90 : 0) - (negative ? 140 : 0);
}

export function catalogFurnitureScore(candidate, request = {}) {
  if (!candidate?.model_url) return Number.NEGATIVE_INFINITY;
  const styleScore = request.styleId
    && [candidate.primary_style, candidate.style_primary, candidate.style_secondary].includes(request.styleId) ? 80 : 0;
  return styleScore
    + roomTypeScore(candidate, request)
    + roleScore(candidate, request)
    + semanticTextScore(candidate, request)
    + materialScore(candidate, request.materials)
    + colorScore(candidate.color, request.palette)
    + sizeScore(candidate, request)
    + productNameScore(candidate, request.type);
}

export function rankCatalogFurniture(candidates, request = {}) {
  return (candidates || [])
    .filter((candidate) => Boolean(candidate?.model_url))
    .map((candidate, index) => ({
      candidate,
      index,
      score: catalogFurnitureScore(candidate, request),
    }))
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .map(({ candidate, score }) => ({
      ...candidate,
      questionnaire_match_score: Math.round(score * 10) / 10,
    }));
}

export function catalogFurnitureOffer(candidate, {
  roomId,
  requestedType,
  requestedVariant,
  reason,
} = {}) {
  return {
    ...candidate,
    furniture_id: candidate.furniture_id,
    normalized_type: requestedType || candidate.normalized_type,
    variant_id: requestedVariant || candidate.variant_id || "standard",
    reason,
    selection_source: "questionnaire_catalog_rag",
    placement_room_id: roomId,
  };
}
