const ICONS = Object.freeze({
  sofa2: "M4 8h40v20H4zM8 4h32v7H8zM8 25h32v7H8z",
  sofaL: "M4 5h28v10H14v28H4zM14 33h24v10H14zM32 5h8v28h-8z",
  tableRound: "M24 4a20 20 0 1 0 0 40 20 20 0 1 0 0-40zM22 2h4v44h-4zM2 22h44v4H2z",
  tableRect: "M4 8h40v32H4zM8 12h32v24H8zM2 4h8v6H2zM38 4h8v6h-8zM2 38h8v6H2zM38 38h8v6h-8z",
  bed: "M4 5h40v38H4zM8 9h32v9H8zM8 21h32v18H8zM9 10h14v7H9zM25 10h14v7H25z",
  desk: "M4 8h40v25H4zM8 12h32v17H8zM7 33h5v11H7zM36 33h5v11h-5z",
  chair: "M12 5h24v19H12zM9 24h30v8H9zM12 32h5v12h-5zM31 32h5v12h-5z",
  cabinet: "M7 4h34v40H7zM11 8h13v32H11zM26 8h11v32H26zM22 22h3v3h-3z",
  appliance: "M7 4h34v40H7zM11 8h26v7H11zM13 21h22v19H13zM31 10h3v3h-3z",
  bath: "M6 7h36v28c0 6-6 9-18 9S6 41 6 35zM11 12h26v20H11z",
  decor: "M24 4l6 12 13 2-10 9 3 13-12-7-12 7 3-13-10-9 13-2z",
  beam: "M3 18h42v12H3zM7 21h34v6H7z",
  column: "M8 8h32v32H8zM13 13h22v22H13z",
});

function variant(id, label, widthCm, depthCm, iconPath, heightCm = 75) {
  return { id, label, widthCm, depthCm, heightCm, iconPath };
}

export const FURNITURE_2D_LIBRARY = Object.freeze([
  {
    type: "sofa",
    label: "沙發",
    variants: [
      variant("two-seat", "雙人沙發", 160, 85, ICONS.sofa2, 82),
      variant("three-seat", "三人沙發", 210, 90, ICONS.sofa2, 82),
      variant("l-shape", "L 型沙發", 260, 180, ICONS.sofaL, 82),
    ],
  },
  {
    type: "coffee-table",
    label: "茶几",
    variants: [
      variant("round", "圓形茶几", 80, 80, ICONS.tableRound, 42),
      variant("rect", "長方形茶几", 110, 60, ICONS.tableRect, 42),
    ],
  },
  {
    type: "dining-table",
    label: "餐桌",
    variants: [
      variant("round-4", "四人圓桌", 110, 110, ICONS.tableRound, 75),
      variant("rect-4", "四人長桌", 140, 80, ICONS.tableRect, 75),
      variant("rect-6", "六人長桌", 180, 90, ICONS.tableRect, 75),
    ],
  },
  {
    type: "dining-chair",
    label: "餐椅",
    variants: [variant("standard", "餐椅", 48, 52, ICONS.chair, 82)],
  },
  {
    type: "bed",
    label: "床",
    variants: [
      variant("single", "單人床", 105, 200, ICONS.bed, 55),
      variant("double", "雙人床", 152, 200, ICONS.bed, 55),
      variant("queen", "加大雙人床", 182, 212, ICONS.bed, 58),
    ],
  },
  {
    type: "desk",
    label: "書桌",
    variants: [
      variant("compact", "小型書桌", 100, 55, ICONS.desk, 75),
      variant("standard", "標準書桌", 140, 65, ICONS.desk, 75),
    ],
  },
  {
    type: "office-chair",
    label: "工作椅",
    variants: [variant("task", "工作椅", 62, 62, ICONS.chair, 95)],
  },
  {
    type: "lounge-chair",
    label: "單椅",
    variants: [
      variant("accent", "休閒單椅", 76, 78, ICONS.chair, 82),
      variant("outdoor", "戶外椅", 62, 66, ICONS.chair, 82),
    ],
  },
  {
    type: "wardrobe",
    label: "衣櫃",
    variants: [
      variant("two-door", "雙門衣櫃", 100, 60, ICONS.cabinet, 210),
      variant("sliding", "滑門衣櫃", 180, 65, ICONS.cabinet, 220),
    ],
  },
  {
    type: "bedside-table",
    label: "床頭櫃",
    variants: [variant("compact", "床頭櫃", 45, 40, ICONS.cabinet, 55)],
  },
  {
    type: "storage-cabinet",
    label: "收納櫃",
    variants: [
      variant("low", "低收納櫃", 120, 45, ICONS.cabinet, 75),
      variant("tall", "高收納櫃", 90, 45, ICONS.cabinet, 180),
    ],
  },
  {
    type: "vanity-table",
    label: "梳妝台",
    variants: [variant("standard", "梳妝台", 100, 48, ICONS.desk, 75)],
  },
  {
    type: "sideboard",
    label: "餐邊櫃",
    variants: [variant("standard", "餐邊櫃", 140, 45, ICONS.cabinet, 90)],
  },
  {
    type: "appliance-cabinet",
    label: "電器櫃",
    variants: [variant("standard", "電器櫃", 80, 60, ICONS.appliance, 180)],
  },
  {
    type: "kitchen-island",
    label: "中島",
    variants: [variant("standard", "廚房中島", 180, 90, ICONS.tableRect, 90)],
  },
  {
    type: "bathroom-vanity",
    label: "浴櫃",
    variants: [variant("standard", "浴櫃", 90, 55, ICONS.cabinet, 85)],
  },
  {
    type: "mirror-cabinet",
    label: "鏡櫃",
    variants: [variant("standard", "鏡櫃", 75, 18, ICONS.cabinet, 80)],
  },
  {
    type: "flower-pots-planter",
    label: "植栽",
    variants: [variant("floor", "落地植栽", 35, 35, ICONS.decor, 85)],
  },
  {
    type: "plant-shelf",
    label: "植栽架",
    variants: [variant("standard", "植栽架", 90, 38, ICONS.decor, 150)],
  },
  {
    type: "tv-bench",
    label: "電視櫃",
    variants: [variant("low", "矮電視櫃", 180, 45, ICONS.cabinet, 55)],
  },
  {
    type: "armchair",
    label: "單人椅",
    variants: [variant("standard", "單人休閒椅", 78, 82, ICONS.chair, 88)],
  },
  {
    type: "bookcase",
    label: "書櫃",
    variants: [
      variant("low", "矮書櫃", 100, 35, ICONS.cabinet, 90),
      variant("tall", "高書櫃", 90, 35, ICONS.cabinet, 180),
    ],
  },
  {
    type: "bathtub",
    label: "浴缸",
    variants: [variant("standard", "標準浴缸", 160, 75, ICONS.bath, 58)],
  },
  {
    type: "table",
    label: "桌",
    variants: [variant("standard", "一般桌", 120, 70, ICONS.tableRect, 75)],
  },
  {
    type: "chair",
    label: "椅",
    variants: [variant("standard", "一般椅", 48, 52, ICONS.chair, 82)],
  },
]);

export function findFurniture2DVariant(type, variantId) {
  const category = FURNITURE_2D_LIBRARY.find((item) => item.type === type);
  if (!category) return null;
  const selected = category.variants.find((item) => item.id === variantId)
    || category.variants[0];
  return { category, selected };
}

export function recommendCompanionFurniture(roomType, selectedTypes = []) {
  const selected = new Set(selectedTypes);
  if (!selected.size) return [];
  const recommendations = [];
  const add = (type, variantId, reason) => {
    if (selected.has(type) || recommendations.some((item) => item.type === type)) return;
    recommendations.push({ type, variantId, reason, autoAdded: true });
  };

  if (roomType === "living_room") {
    if (selected.has("sofa")) {
      add("tv-bench", "low", "依沙發使用情境補上視聽收納。");
    }
    add("flower-pots-planter", "floor", "補上不影響主要動線的軟裝植栽。");
  } else if (roomType === "bedroom" && selected.has("bed")) {
    add("bedside-table", "compact", "依床側使用需求補上床頭收納。");
  } else if (roomType === "balcony") {
    add("flower-pots-planter", "floor", "依陽台用途補上植栽。");
  }
  return recommendations;
}

export function roomTypeFromName(room = {}) {
  const explicitType = String(room.type || room.room_type || "default").toLowerCase();
  if (explicitType && !["default", "unknown", "other"].includes(explicitType)) {
    return explicitType;
  }
  const label = String(room.label || room.name || "").toLowerCase();
  const rules = [
    ["bedroom", /bedroom|dormitory|master\s*bed|臥室|主臥|次臥/],
    ["kitchen", /kitchen|廚房/],
    ["storage", /deposit|storage|store\s*room|儲藏|儲物|收納/],
    ["bathroom", /bathroom|toilet|washroom|浴室|浴廁|衛生間|廁所/],
    ["living_room", /living\s*room|lounge|客廳/],
    ["dining_room", /dining\s*room|飯廳|餐廳/],
    ["balcony", /balcony|terrace|陽台/],
    ["circulation", /circulation|corridor|hallway|走道|走廊|玄關/],
    ["workspace", /study|office|den|書房|工作室/],
  ];
  return rules.find(([, pattern]) => pattern.test(label))?.[0] || "default";
}

/** 用餐人數 → 餐桌型號。座位數決定桌子，不是反過來。 */
function diningTableVariant(seats) {
  if (seats >= 6) return "rect-6";
  return seats > 4 ? "rect-4" : "round-4";
}

/**
 * 臥室床型。
 *
 * 舊版所有臥室一律雙人床，兒童房也照放——這是 QA 2026-08-01 實測的問題：
 * 住戶人數與兒童數完全不影響配置。次臥有兒童時給單人床與書桌，主臥依成人
 * 人數決定單／雙人床。
 */
function bedroomFurniture({ adults = 2, children = 0, bedroomRole = "primary" } = {}) {
  if (bedroomRole === "secondary" && children > 0) {
    return [["bed", "single"], ["wardrobe", "two-door"], ["desk", "compact"]];
  }
  if (bedroomRole === "secondary") {
    return [["bed", "single"], ["wardrobe", "two-door"]];
  }
  return [["bed", adults >= 2 ? "double" : "single"], ["wardrobe", "two-door"]];
}

export function recommendedFurnitureForRoom(room = {}, occupancy = {}) {
  const roomType = roomTypeFromName(room);
  // 餐椅數量依用餐人數展開。舊版只放一張，八人份問卷也一樣。
  const diningSeats = Math.max(2, Math.min(6, Number(occupancy.diningSeats) || 4));
  const recommendations = {
    living_room: [["sofa", "three-seat"], ["coffee-table", "rect"], ["tv-bench", "low"]],
    bedroom: bedroomFurniture(occupancy),
    dining_room: [
      ["dining-table", diningTableVariant(diningSeats)],
      ...Array.from({ length: diningSeats }, () => ["dining-chair", "standard"]),
    ],
    kitchen: [["appliance-cabinet", "standard"]],
    storage: [["storage-cabinet", "tall"]],
    workspace: [["desk", "standard"], ["office-chair", "task"]],
    bathroom: [["bathroom-vanity", "standard"], ["mirror-cabinet", "standard"]],
    balcony: [["flower-pots-planter", "floor"]],
    circulation: [],
  };
  return recommendations[roomType] || [];
}

export function createFurniture2DItem(type, variantId, overrides = {}) {
  const match = findFurniture2DVariant(type, variantId);
  if (!match) throw new Error(`unknown_furniture_type:${type}`);
  const { category, selected } = match;
  return {
    id: overrides.id || `${type}-${selected.id}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    variantId: selected.id,
    label: selected.label,
    widthCm: Number(overrides.widthCm) || selected.widthCm,
    depthCm: Number(overrides.depthCm) || selected.depthCm,
    heightCm: Number(overrides.heightCm) || selected.heightCm,
    iconPath: selected.iconPath,
    xCm: Number(overrides.xCm) || 0,
    yCm: Number(overrides.yCm) || 0,
    rotationDeg: Number(overrides.rotationDeg) || 0,
    locked: overrides.locked === true,
    userRequired: overrides.userRequired === true,
    categoryLabel: category.label,
    roomId: overrides.roomId || null,
    reason: overrides.reason || "",
    // 檯面小物的宿主（花瓶站在哪張桌上）；落地家具一律 null。
    hostObjectId: overrides.hostObjectId || null,
    hostSurfaceHeightCm: Number(overrides.hostSurfaceHeightCm) || 0,
  };
}

export function replaceFurniture2DItem(current, type, variantId) {
  if (!current) return createFurniture2DItem(type, variantId);
  const replacement = createFurniture2DItem(type, variantId, {
    id: current.id,
    xCm: current.xCm,
    yCm: current.yCm,
    rotationDeg: current.rotationDeg,
    locked: current.locked,
    userRequired: current.userRequired,
  });
  return {
    ...replacement,
    roomId: current.roomId,
    reason: `使用者把「${current.label}」更換為「${replacement.label}」。`,
    catalogFurnitureId: null,
  };
}

export function planCmToLayerPixel(point, geometry, pixelsPerCm = null) {
  const scale = Math.max(Number(geometry?.scale) || 0, 0.0001);
  const bbox = Array.isArray(geometry?.bbox) && geometry.bbox.length === 4
    ? geometry.bbox.map(Number)
    : [0, 0, 0, 0];
  const renderedScale = Number(pixelsPerCm) > 0
    ? Number(pixelsPerCm)
    : 1 / scale;
  return {
    x: (bbox[0] * scale + Number(point?.x || 0)) * renderedScale,
    y: (bbox[3] * scale - Number(point?.y || 0)) * renderedScale,
  };
}

export function furnitureCollisionFootprintCm(item) {
  const width = Math.max(0, Number(item?.widthCm) || 0);
  const depth = Math.max(0, Number(item?.depthCm) || 0);
  const radians = (Number(item?.rotationDeg) || 0) * Math.PI / 180;
  const cosine = Math.abs(Math.cos(radians));
  const sine = Math.abs(Math.sin(radians));
  return {
    width: Math.round((width * cosine + depth * sine) * 1000) / 1000,
    depth: Math.round((width * sine + depth * cosine) * 1000) / 1000,
  };
}

export function furnitureFootprintStyle(item, pixelsPerCm) {
  const scale = Math.max(Number(pixelsPerCm) || 0, 0.05);
  return {
    width: `${Math.max(item.widthCm * scale, 28)}px`,
    height: `${Math.max(item.depthCm * scale, 28)}px`,
    transform: `translate(-50%, -50%) rotate(${Number(item.rotationDeg) || 0}deg)`,
  };
}

export function toSceneFurniture(item, { positionLocked = true } = {}) {
  return {
    furniture_id: item.id,
    catalog_furniture_id: item.catalogFurnitureId || null,
    normalized_type: item.type,
    name_zh_raw: item.label,
    model_url: item.model_url || null,
    has_model: Boolean(item.model_url),
    primary_style: item.primaryStyle || null,
    color: item.catalogColor || null,
    material: item.catalogMaterial || null,
    selection_source: item.selectionSource || null,
    match_reason: item.catalogMatchReason || item.reason || null,
    size_cm: {
      width: item.widthCm,
      depth: item.depthCm,
      height: item.heightCm,
    },
    position_cm: { x: item.xCm, z: item.yCm },
    rotation_y_deg: item.rotationDeg,
    position_locked: positionLocked,
    user_specified: item.locked === true,
    user_required: item.userRequired === true,
    placement_room_id: item.roomId,
    // 檯面小物的宿主關係（選填）：3D 以 host_surface_height_cm 決定 y。
    host_object_id: item.hostObjectId || null,
    host_surface_height_cm: Number(item.hostSurfaceHeightCm) || 0,
  };
}

export function mergeCatalogFurniture(item, catalogItem) {
  const sceneItem = toSceneFurniture(item);
  return {
    ...catalogItem,
    ...sceneItem,
    furniture_id: item.id,
    catalog_furniture_id: catalogItem.furniture_id,
    model_url: catalogItem.model_url,
    has_model: Boolean(catalogItem.model_url),
    size_cm: sceneItem.size_cm,
    catalog_size_cm: catalogItem.size_cm,
    requested_size_cm: sceneItem.size_cm,
    closest_size_match: true,
  };
}
