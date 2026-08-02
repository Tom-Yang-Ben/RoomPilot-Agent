// 佇列 7 巨石拆分第五批：純搬家自 scene_v2.js，內容一字未改。
// 這裡只收問卷區塊的常數表與純函式——問卷階段/選項定義、材質推薦排序、
// 家具程式表、offer 標籤與 payload 組裝器。它們僅依賴參數、彼此、標準庫
// 與既有共用模組，不碰 state、element、DOM。
// 為了維持「純搬家」紀律，主體保持原樣，統一在檔尾 export。

import {
  createFurniture2DItem,
} from "./scene_layout2d.js?v=sha256-4a2749522d19";
import {
  roomDimensions,
} from "./scene_plan_geometry.js?v=sha256-2cbf87c33fa5";
import {
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-097f1470f5a3";
import {
  CEILING_STYLES,
  LIGHT_STYLES,
  STYLE_MATERIAL_OPTIONS,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-1c8390b903e5";

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
  dining_room: [
    { axis: "use", left: "日常快餐", right: "聚餐儀式" },
    { axis: "lighting", left: "低位餐吊燈", right: "均勻工作光" },
  ],
  kitchen: [
    { axis: "use", left: "快速備餐", right: "重度烹飪" },
    { axis: "storage", left: "檯面留白", right: "高量收納" },
  ],
  bathroom: [
    { axis: "use", left: "快速乾濕分離", right: "泡澡放鬆" },
    { axis: "maintenance", left: "低維護", right: "飯店感" },
  ],
  workspace: [
    { axis: "use", left: "專注工作", right: "彈性閱讀" },
    { axis: "lighting", left: "防眩任務光", right: "展示氛圍光" },
  ],
  balcony: [
    { axis: "use", left: "洗曬機能", right: "休憩植栽" },
    { axis: "storage", left: "完全收納", right: "開放展示" },
  ],
  entry: [
    { axis: "use", left: "快速出入", right: "完整落塵收納" },
    { axis: "lighting", left: "感應安全光", right: "端景展示光" },
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
  "entry",
  "foyer",
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
  return type === "circulation" || /走道|動線|玄關走廊/.test(label);
}

function roomKeepsExplicitWallOverride(room, surfaces = {}) {
  return roomAllowsIndependentFloor(room) && surfaces.wallOverrideExplicit === true;
}

function stableStringNumber(value = "") {
  return String(value).split("").reduce(
    (total, char, index) => total + char.charCodeAt(0) * (index + 1),
    0,
  );
}

function uniqueMaterialOptions(kind) {
  const seen = new Set();
  return Object.values(STYLE_MATERIAL_OPTIONS).flatMap((style) => style[kind] || [])
    .filter((option) => {
      if (!option?.id || seen.has(option.id)) return false;
      seen.add(option.id);
      return true;
    });
}

function materialOptionForPack(option, pack) {
  return {
    ...option,
    // 材質卡的縮圖、色票與 3D 套用色都必須沿用同一筆材質資料。
    // 風格色卡只影響排序與推薦，不能改寫 material_id 的原始色碼。
    note: option.note,
    recommendation: pack.name,
  };
}

function questionnaireMaterialOptionsForPack(kind, pack) {
  const styleOptions = STYLE_MATERIAL_OPTIONS[pack.styleId]?.[kind] || [];
  const allOptions = uniqueMaterialOptions(kind);
  const preferredId = kind === "wall" ? pack.wall.surfaceOption : pack.floor.surfaceOption;
  const preferred = allOptions.find((option) => option.id === preferredId)
    || styleOptions.find((option) => option.id === preferredId);
  const pool = [preferred, ...styleOptions, ...allOptions].filter(Boolean);
  const unique = [];
  const seen = new Set();
  pool.forEach((option) => {
    if (!option?.id || seen.has(option.id)) return;
    seen.add(option.id);
    unique.push(option);
  });
  const [first, ...rest] = unique;
  const shift = rest.length
    ? stableStringNumber(`${pack.id}:${kind}`) % rest.length
    : 0;
  const rotated = rest.slice(shift).concat(rest.slice(0, shift));
  return [first, ...rotated]
    .slice(0, QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT)
    .map((option) => materialOptionForPack(option, pack));
}

function randomWholeHouseAnswers() {
  const note = randomItem(TEST_REQUIREMENT_PROFILE_NOTES, TEST_REQUIREMENT_PROFILE_NOTES[0]);
  return Object.fromEntries(WHOLE_HOUSE_QUESTIONS.map((question) => {
    if (question.type === "select") return [question.id, randomItem(question.options, "")];
    return [question.id, note];
  }));
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

function firstMeetingStylePacks() {
  return [...new Map(STYLE_PACKS.map((pack) => [pack.styleId, pack])).values()];
}

function firstMeetingCountOptions(selected, { minimum = 0 } = {}) {
  return Array.from({ length: 6 }, (_, index) => index + minimum)
    .map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}${value === 5 + minimum ? "+" : ""}</option>`)
    .join("");
}

function preferenceWeightLabel(weight) {
  return PREFERENCE_WEIGHT_OPTIONS.find((item) => item.value === Number(weight))?.label || "";
}

const ROOM_QUESTIONNAIRE_SECTIONS = Object.freeze([
  "preferences",
  "equipment",
  "materials",
]);

function progressPercent({ completed, total }) {
  return total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;
}

// 第 8 步生圖才用得到的細節。這些軸在 3D 場景裡沒有對應物件，模型本來就得
// 自行補完；問了之後是把「亂補」變成「照需求補」，不會與家具鎖定衝突，也
// 完全不進引擎——擺放參數不受影響，既有配置不會因此位移。
// 天花形式、照明形式與冷氣形式不列在這裡：上方「天花與設備」已經在問，而且
// 選項比視覺題庫的二選一更細，重複問只會產生互相矛盾的答案。
const RENDER_DETAIL_FIELDS = Object.freeze([
  {
    key: "indirectLight",
    element: "renderDetailIndirectLight",
    label: "間接光",
    labels: { minimal: "維持乾淨，少用間接光", featured: "以間接光為主要氛圍" },
  },
  {
    key: "ceilingZoning",
    element: "renderDetailCeilingZoning",
    label: "天花分區",
    labels: { room: "每個空間各自造型", continuous: "全屋連續同一平面" },
  },
  {
    key: "airflowStrategy",
    element: "renderDetailAirflowStrategy",
    label: "送風方式",
    labels: { direct: "直吹，出風口明顯", indirect: "導流，避免直吹人" },
  },
  {
    key: "serviceVisibility",
    element: "renderDetailServiceVisibility",
    label: "維修口",
    labels: { hidden: "盡量隱藏", accessible: "保留明顯好維修" },
  },
  {
    key: "ceilingFan",
    element: "renderDetailCeilingFan",
    label: "吊扇",
    labels: { yes: "要有吊扇", no: "不要吊扇" },
  },
  {
    key: "applianceVisibility",
    element: "renderDetailApplianceVisibility",
    label: "廚房家電",
    labels: { integrated: "嵌入櫃體隱藏", visible: "外露看得到" },
  },
]);

// 第 8 步生圖要的是「人看得懂的需求」，不是 materialId。這裡在前端就解析成
// 使用者在畫面上看到的同一組標籤，後端不必再維護第二份型錄對照表。
function surfaceMaterialLabel(kind, materialId) {
  if (!materialId) return "";
  const match = uniqueMaterialOptions(kind).find((option) => option.id === materialId);
  return match?.label || String(materialId);
}

function styleCatalogLabel(catalog, id) {
  if (!id) return "";
  return catalog.find((item) => item.id === id)?.label || String(id);
}

function surfacePhrase(label, colorHex) {
  return [label, colorHex].filter(Boolean).join(" ");
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

const CATALOG_RETRIEVAL_ROUTES = {
  "sofa": {
    endpoint: "/api/furniture",
    types: ["fabric-sofa", "leather-sofa", "modular-sofa", "sofa"],
  },
  "storage-cabinet": { endpoint: "/api/furniture", type: "cabinet-cupboard" },
  "appliance-cabinet": { endpoint: "/api/furniture", type: "cabinet-cupboard" },
  "bathroom-vanity": {
    endpoint: "/api/furniture",
    type: "cabinet-cupboard",
    query: "bathroom storage",
  },
  "mirror-cabinet": {
    endpoint: "/api/furniture",
    type: "mirror-cabinet",
    query: "mirror cabinet",
  },
};

const REPLACEMENT_TYPE_LABELS = {
  bed: "床",
  wardrobe: "衣櫃",
  "bedside-table": "床邊桌",
  "fabric-sofa": "布沙發",
  "leather-sofa": "皮沙發",
  "modular-sofa": "模組沙發",
  "sofa": "一般沙發",
  "fridge-freezer": "冰箱",
  "washing-machine": "洗衣機／洗脫烘",
  "cabinet-cupboard": "收納櫃",
  "mirror-cabinet": "鏡櫃",
};

const QUESTIONNAIRE_FALLBACK_CATALOG_RULES = Object.freeze({
  bed: { query: "bed frame", types: ["bed"], keywords: ["bed", "床架", "床"] },
  wardrobe: { query: "wardrobe", types: ["wardrobe"], keywords: ["wardrobe", "衣櫃"] },
  "bedside-table": { query: "bedside table", keywords: ["bedside", "床頭"] },
  desk: { query: "desk", types: ["desk"], keywords: ["desk", "書桌"] },
  "office-chair": { query: "office chair", keywords: ["chair", "椅"] },
  "lounge-chair": { query: "lounge chair", keywords: ["chair", "椅"] },
  "dining-chair": { query: "dining chair", keywords: ["chair", "椅"] },
  "dining-table": { query: "dining table", keywords: ["table", "餐桌"] },
  "tv-bench": { query: "tv stand", keywords: ["tv", "television", "電視"] },
  "storage-cabinet": { query: "storage cabinet", keywords: ["cabinet", "storage", "收納", "櫃"] },
});

function isQuestionnaireFallbackTypeMatch(candidate, type) {
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[type];
  if (!rule) return candidate.normalized_type === type;
  const description = [
    candidate.name_zh,
    candidate.name_zh_raw,
    candidate.name_en,
    candidate.category_label,
    candidate.taxonomy_type_zh,
  ].filter(Boolean).join(" ").toLowerCase();
  const keywordMatches = (rule.keywords || []).some((keyword) =>
    description.includes(keyword.toLowerCase()));
  if (!keywordMatches) return false;
  return !rule.types?.length || rule.types.includes(candidate.normalized_type);
}

// 型錄用 placement_surface 宣告品項是落地家具、桌面擺飾、壁掛還是地面覆蓋物
// （backend/catalog/placement_surface.py）。第 6 步的牆界、碰撞與淨空只對落地家具
// 有意義；18 公分的玻璃花瓶、抱枕、壁掛層架被當成落地家具送進去算，就會「放不下」
// 而永遠卡在待處理清單（QA #7）。這裡只遵守型錄宣告的欄位，不自行用尺寸猜類別。
function isFloorPlacedCatalogItem(candidate = {}) {
  // 型別與尺寸兜不起來的列（例如標成 bed 的 468cm 斗櫃）不進自動選件，
  // 否則整間臥室會被一件標錯的家具吃掉。型錄仍查得到，只是不自動選。
  if (candidate.size_is_implausible === true) return false;
  const surface = candidate.placement_surface;
  return !surface || surface === "floor";
}

const QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS = Object.freeze({
  bedroom: {
    defaults: ["bed", "wardrobe"],
    required: ["bed"],
    labels: { bed: "睡眠的基本配置", wardrobe: "日常衣物收納", "bedside-table": "床邊置物" },
  },
  living_room: {
    defaults: ["sofa"],
    required: ["sofa"],
    labels: { sofa: "休息與招待的基本配置", "coffee-table": "客廳置物與活動中心", "tv-bench": "影音設備收納", "lounge-chair": "閱讀或獨立休息" },
  },
  dining_room: {
    defaults: ["dining-table", "dining-chair"],
    required: ["dining-table"],
    labels: { "dining-table": "用餐的基本配置", "dining-chair": "搭配餐桌的座位" },
  },
  kitchen: {
    defaults: ["appliance-cabinet"],
    required: ["appliance-cabinet"],
    labels: { "appliance-cabinet": "備餐與廚房收納", "storage-cabinet": "補充收納" },
  },
  storage: {
    defaults: ["storage-cabinet"],
    required: ["storage-cabinet"],
    labels: { "storage-cabinet": "儲藏的基本配置" },
  },
  bathroom: {
    defaults: ["bathroom-vanity", "mirror-cabinet"],
    required: ["bathroom-vanity"],
    labels: { "bathroom-vanity": "盥洗與收納的基本配置", "mirror-cabinet": "鏡面與用品收納" },
  },
  balcony: {
    defaults: [],
    required: [],
    labels: { "flower-pots-planter": "陽台綠化", "lounge-chair": "短暫休憩" },
  },
  circulation: { defaults: [], required: [], labels: {} },
  study: {
    defaults: ["desk", "office-chair"],
    required: ["desk"],
    labels: { desk: "工作或閱讀的基本配置", "office-chair": "搭配書桌的座位", "storage-cabinet": "文件收納" },
  },
  default: { defaults: [], required: [], labels: {} },
});

const QUESTIONNAIRE_FURNITURE_SHORT_LABELS = Object.freeze({
  bed: "床",
  wardrobe: "衣櫃",
  "bedside-table": "床邊桌",
  sofa: "沙發",
  "coffee-table": "茶几",
  "tv-bench": "電視櫃",
  "lounge-chair": "單椅",
  desk: "書桌",
  "office-chair": "工作椅",
  "dining-table": "餐桌",
  "dining-chair": "餐椅",
  "appliance-cabinet": "廚房收納櫃",
  "storage-cabinet": "收納櫃",
  "bathroom-vanity": "浴櫃",
  "mirror-cabinet": "鏡櫃",
  "flower-pots-planter": "植栽",
});

const QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS = Object.freeze({
  scandinavian: ["淺木色", "圓角", "自然布料", "可收納", "輕盈"],
  japanese: ["淺木色", "低矮", "留白", "藤編", "自然材質"],
  modern_minimal: ["霧面", "俐落線條", "隱藏收納", "低彩度", "金屬"],
  industrial: ["黑色金屬", "木紋", "耐用", "開放層架", "皮革"],
  american: ["厚實", "布料", "溫暖木色", "大尺寸", "舒適"],
  creamy: ["圓弧", "奶油色", "柔軟布料", "淺色木紋", "收納"],
  default: ["淺木色", "圓角", "可收納", "耐用", "金屬"],
});

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

function roomAreaM2(room) {
  const dimensions = roomDimensions(room);
  return Number(dimensions?.areaM2) || 0;
}

const ROOM_USAGE_OPTIONS = Object.freeze({
  living_room: [
    { id: "rest", label: "休息聊天" },
    { id: "watch", label: "看電視／影音" },
    { id: "host", label: "接待客人" },
    { id: "read", label: "閱讀休息" },
  ],
  bedroom: [
    { id: "sleep", label: "睡眠休息" },
    { id: "work", label: "閱讀／工作" },
    { id: "dressing", label: "收納更衣" },
  ],
  dining_room: [
    { id: "dine", label: "日常用餐" },
    { id: "host", label: "招待聚餐" },
    { id: "work", label: "工作／閱讀" },
  ],
  kitchen: [
    { id: "cook", label: "日常下廚" },
    { id: "prep", label: "備料收納" },
    { id: "dine", label: "簡單用餐" },
  ],
  storage: [
    { id: "store", label: "集中收納" },
    { id: "laundry", label: "洗衣整理" },
  ],
  bathroom: [
    { id: "bathe", label: "盥洗淋浴" },
    { id: "store", label: "衛浴收納" },
  ],
  balcony: [
    { id: "laundry", label: "洗曬衣物" },
    { id: "rest", label: "休憩植栽" },
  ],
  default: [
    { id: "flex", label: "彈性使用" },
    { id: "store", label: "收納整理" },
  ],
});

const ROOM_USAGE_FURNITURE_SPECS = Object.freeze({
  watch: [["tv-bench", "low"]],
  read: [["desk", "compact"], ["office-chair", "task"]],
  work: [["desk", "compact"], ["office-chair", "task"]],
  dressing: [["wardrobe", "two-door"], ["vanity-table", "standard"]],
  host: [["lounge-chair", "accent"]],
  dine: [["dining-table", "round-4"], ["dining-chair", "standard"]],
  prep: [["storage-cabinet", "low"]],
  store: [["storage-cabinet", "tall"]],
  laundry: [["storage-cabinet", "low"]],
});

function roomUsageOptions(room) {
  return ROOM_USAGE_OPTIONS[room?.type] || ROOM_USAGE_OPTIONS.default;
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

function questionnaireFurnitureSizeLabel(offer) {
  const size = offer?.size_cm || {};
  const width = Math.round(Number(size.width || 0));
  const depth = Math.round(Number(size.depth || 0));
  return width && depth ? `${width} × ${depth} cm` : "尺寸待確認";
}

function specsFromSelectionResponse(room, response, fallbackSpecs) {
  const selectedRoom = (response.rooms || []).find((item) => item.room_id === room.id);
  if (!selectedRoom?.items?.length) return fallbackSpecs;
  const specs = [];
  selectedRoom.items.forEach((item) => {
    const count = Math.max(1, Math.min(6, Number(item.count) || 1));
    for (let index = 0; index < count; index += 1) {
      specs.push([
        item.normalized_type,
        item.variant_id || item.variantId || "standard",
        item.reason || item.match_reason || item.selection_source || response.source,
        item.auto_added === true,
        item,
      ]);
    }
  });
  return specs.length ? specs : fallbackSpecs;
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

export {
  CATALOG_RETRIEVAL_ROUTES,
  INDEPENDENT_FLOOR_LABEL_PATTERNS,
  INDEPENDENT_FLOOR_ROOM_TYPES,
  PREFERENCE_WEIGHT_OPTIONS,
  QUESTIONNAIRE_FALLBACK_CATALOG_RULES,
  QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS,
  QUESTIONNAIRE_FURNITURE_SHORT_LABELS,
  QUESTIONNAIRE_MATERIAL_RECOMMENDATION_COUNT,
  QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS,
  QUESTIONNAIRE_STAGES,
  RENDER_DETAIL_FIELDS,
  REPLACEMENT_TYPE_LABELS,
  ROOM_QUESTIONNAIRE_SECTIONS,
  ROOM_REQUIREMENT_POLAR_AXES,
  ROOM_USAGE_FURNITURE_SPECS,
  ROOM_USAGE_OPTIONS,
  TEST_AIR_CONDITIONING_OPTIONS,
  TEST_REQUIREMENT_PROFILE_NOTES,
  firstMeetingCountOptions,
  firstMeetingStylePacks,
  furnitureOfferFromSpec,
  isCirculationRoom,
  isFloorPlacedCatalogItem,
  isQuestionnaireFallbackTypeMatch,
  materialOptionForPack,
  preferenceWeightLabel,
  progressPercent,
  questionnaireBedSizeFamily,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureDisplayName,
  questionnaireFurnitureProgram,
  questionnaireFurnitureRole,
  questionnaireFurnitureSelectionItem,
  questionnaireFurnitureSizeLabel,
  questionnaireMaterialOptionsForPack,
  questionnaireOfferMatchesRequestedType,
  questionnaireOffersWithSizeChoices,
  randomItem,
  randomRoomAxisNote,
  randomRoomFinishDraft,
  randomWholeHouseAnswers,
  roomAllowsIndependentFloor,
  roomAreaM2,
  roomKeepsExplicitWallOverride,
  roomUsageOptions,
  specsAllowedByRoomFeasibility,
  specsFromSelectionResponse,
  stableStringNumber,
  styleCatalogLabel,
  surfaceMaterialLabel,
  surfacePhrase,
  trimAccentWallSurfaces,
  uniqueMaterialOptions,
};
