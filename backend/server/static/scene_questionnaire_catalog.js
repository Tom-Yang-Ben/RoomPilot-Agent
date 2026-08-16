// Pure questionnaire/catalog configuration shared by the scene workflow.

export const CATALOG_RETRIEVAL_ROUTES = {
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

export const REPLACEMENT_TYPE_LABELS = {
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

export const QUESTIONNAIRE_FALLBACK_CATALOG_RULES = Object.freeze({
  bed: { query: "bed frame", types: ["bed"], keywords: ["bed", "床架", "床"] },
  wardrobe: { query: "wardrobe", types: ["wardrobe"], keywords: ["wardrobe", "衣櫃"] },
  "bedside-table": { query: "bedside table", keywords: ["bedside", "床頭"] },
  desk: { query: "desk", types: ["desk"], keywords: ["desk", "書桌"] },
  "office-chair": { query: "office chair", keywords: ["chair", "椅"] },
  "lounge-chair": { query: "lounge chair", keywords: ["chair", "椅"] },
  "dining-chair": { query: "dining chair", keywords: ["chair", "椅"] },
  "dining-table": { query: "dining table", keywords: ["table", "餐桌"] },
  // 電視櫃:keywords「電視/tv」太泛,會把「電視壁掛安裝臂/支架」這類安裝五金誤配成
  // 電視櫃(名稱都含 TV/電視)。mustInclude 要求名稱含家具本體名詞(櫃/stand/console…),
  // exclude 直接擋掉安裝臂/支架/bracket 等五金。floating wall-mounted TV stand 仍過關
  // (含 stand;不擋 wall mount 以免誤殺壁掛式電視櫃)。
  // query 必須是「會逐字出現在型錄名稱裡的單一詞」:catalogFallbackOffersForSpec 把
  // rule.query 當 `q` 送進 /api/furniture,伺服器 _furniture_matches_query 是「整串
  // 連續子字串」比對(main.py:1308)。原本的「tv stand console cabinet」是關鍵字清單、
  // 不是任何名稱的連續子字串 → tier-1 撈 0 筆;tier-2 無 query 不排序、page_size=80
  // 只回自然序前 80(電視櫃在型錄第 331 筆起)→ 也 0 筆 → 客廳電視櫃永遠選不到、
  // 連 待處理 都不出現(feedback floor04:電視櫃完全不在清單)。改用「電視櫃」逐字命中
  // (實測 /api/furniture?q=電視櫃 → 128 筆、前 80 含 71 件電視櫃族),mustInclude/exclude
  // 仍在候選層擋掉安裝臂。沙發用「sofa」、茶几用「coffee table」皆為逐字詞,同理。
  "tv-bench": {
    query: "電視櫃",
    keywords: ["tv", "television", "電視"],
    mustInclude: ["櫃", "bench", "stand", "console", "unit", "cabinet", "media", "storage"],
    exclude: ["安裝臂", "掛臂", "支臂", "支架", "掛架", "托架", "壁掛架", "bracket", "mounting arm", "full motion", "full-motion", "articulating", "swivel"],
  },
  "storage-cabinet": { query: "storage cabinet", keywords: ["cabinet", "storage", "收納", "櫃"] },
  // 沙發家族原本沒 fallback 規則 → isQuestionnaireFallbackTypeMatch 退回精確
  // normalized_type 比對:type=fabric-sofa 查到的沙發只要 normalized_type 不是一模一樣
  // 就被濾光 → 客廳整組沙發撈不到,連坐砍掉茶几/電視櫃(log: 候選缺基礎家具 sofa)。
  // 改用關鍵字比對(照 tv-bench),任一沙發皆可入選;子類型互通(皮/布/模組)無妨,
  // 排序階段再挑最合風格。不設 types 以免又卡在 normalized_type 命名差異。
  sofa: { query: "sofa", keywords: ["sofa", "沙發", "couch", "settee"] },
  "fabric-sofa": { query: "fabric sofa", keywords: ["sofa", "沙發", "couch"] },
  "leather-sofa": { query: "leather sofa", keywords: ["sofa", "沙發", "couch"] },
  "modular-sofa": { query: "modular sofa sectional", keywords: ["sofa", "沙發", "couch", "sectional", "模組"] },
  "coffee-table": { query: "coffee table", keywords: ["coffee", "茶几"] },
});

export function isQuestionnaireFallbackTypeMatch(candidate, type) {
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[type];
  if (!rule) return candidate.normalized_type === type;
  const description = [
    candidate.name_zh,
    candidate.name_zh_raw,
    candidate.name_en,
    candidate.category_label,
    candidate.taxonomy_type_zh,
  ].filter(Boolean).join(" ").toLowerCase();
  // 安裝五金/配件排除:名稱含「電視/TV」的壁掛安裝臂會被 keywords 誤配成電視櫃。
  if ((rule.exclude || []).some((keyword) => description.includes(keyword.toLowerCase()))) {
    return false;
  }
  const keywordMatches = (rule.keywords || []).some((keyword) =>
    description.includes(keyword.toLowerCase()));
  if (!keywordMatches) return false;
  // mustInclude 查「名稱」(非分類,分類可能被誤標):泛型 keyword(tv/電視)須再具備
  // 家具本體名詞(櫃/stand/console…),安裝臂/支架這類無本體名詞的五金即被擋下。
  if (rule.mustInclude?.length) {
    const name = [candidate.name_zh, candidate.name_zh_raw, candidate.name_en]
      .filter(Boolean).join(" ").toLowerCase();
    if (!rule.mustInclude.some((keyword) => name.includes(keyword.toLowerCase()))) {
      return false;
    }
  }
  return !rule.types?.length || rule.types.includes(candidate.normalized_type);
}

export const QUESTIONNAIRE_ROOM_FURNITURE_PROGRAMS = Object.freeze({
  bedroom: {
    defaults: ["bed", "wardrobe"],
    required: [],
    labels: { bed: "睡眠的基本配置", wardrobe: "日常衣物收納", "bedside-table": "床邊置物" },
  },
  living_room: {
    // 客廳沙發組 = 基礎配置:沙發 + 茶几 + 電視櫃一起自動選入,不再只有沙發或
    // (沙發放不下時)退成單椅。單椅仍是沙發整組都放不下時的最後退路。
    defaults: ["sofa", "coffee-table", "tv-bench"],
    fallbackDefaults: ["lounge-chair"],
    required: [],
    labels: { sofa: "休息與招待的基本配置", "coffee-table": "客廳置物與活動中心", "tv-bench": "影音設備收納", "lounge-chair": "閱讀或獨立休息" },
  },
  kitchen: {
    defaults: ["dining-table", "dining-chair"],
    required: [],
    labels: { "dining-table": "用餐的基本配置", "dining-chair": "搭配餐桌的座位", "appliance-cabinet": "備餐與廚房收納", "storage-cabinet": "補充收納" },
  },
  storage: {
    defaults: ["storage-cabinet"],
    required: [],
    labels: { desk: "工作或閱讀的基本配置", "office-chair": "搭配書桌的座位", "storage-cabinet": "文件與用品收納" },
  },
  bathroom: {
    defaults: [],
    required: [],
    labels: { "bathroom-vanity": "盥洗與收納的基本配置", "mirror-cabinet": "鏡面與用品收納" },
  },
  balcony: {
    defaults: [],
    required: [],
    labels: { "flower-pots-planter": "陽台綠化", "lounge-chair": "短暫休憩" },
  },
  entryway: { defaults: [], required: [], labels: { mirror: "玄關整理與出門前使用" } },
  hallway: { defaults: [], required: [], labels: { mirror: "保留走道淨寬；只建議薄型靠牆物件" } },
  stair: { defaults: [], required: [], labels: { lighting: "樓梯僅提供照明；不配置可移動家具" } },
  garage: { defaults: [], required: [], labels: { "storage-cabinet": "工具與用品收納" } },
  default: { defaults: [], required: [], labels: {} },
});

export const QUESTIONNAIRE_FURNITURE_SHORT_LABELS = Object.freeze({
  bed: "床",
  wardrobe: "衣櫃",
  "bedside-table": "床邊桌",
  chair: "椅子",
  armchair: "扶手椅",
  "lounge-chair": "休閒椅",
  "dining-chair": "餐椅",
  "office-chair": "辦公椅",
  "gaming-chair": "電競椅",
  "kids-chairs-stool": "兒童椅／凳",
  "stool-bench": "椅凳",
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

export const QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS = Object.freeze({
  scandinavian: ["淺木色", "圓角", "自然布料", "可收納", "輕盈"],
  japanese: ["淺木色", "低矮", "留白", "藤編", "自然材質"],
  modern_minimal: ["霧面", "俐落線條", "隱藏收納", "低彩度", "金屬"],
  industrial: ["黑色金屬", "木紋", "耐用", "開放層架", "皮革"],
  american: ["厚實", "布料", "溫暖木色", "大尺寸", "舒適"],
  creamy: ["圓弧", "奶油色", "柔軟布料", "淺色木紋", "收納"],
  default: ["淺木色", "圓角", "可收納", "耐用", "金屬"],
});

export const QUESTIONNAIRE_CATALOG_EXTRA_DISPLAY_LABELS = Object.freeze({
  "pax-wardrobe": "系統衣櫃",
  "fabric-sofa": "布沙發",
  "leather-sofa": "皮沙發",
  "modular-sofa": "模組沙發",
  table: "多用途桌",
  "bar-table": "吧檯桌",
  "cabinets-cupboard": "收納櫃",
  "cabinet-cupboard": "收納櫃",
  "shelving-unit": "層架組",
  "storage-boxes-basket": "收納盒籃",
  "storage-solution-system": "收納系統",
  "wall-shelf": "壁掛層架",
  "shoe-cabinet": "鞋櫃",
  "clothes-rack": "衣帽架",
  "tv-media-furniture": "影音櫃",
  "chests-of-drawer": "抽屜櫃",
  mirror: "鏡子",
  "large-medium-rug": "地毯",
  "runner-small-rug": "走道地毯",
  "floor-lamp": "立燈",
  planter: "植栽盆器",
  decoration: "裝飾擺件",
  "pillow-cushion": "抱枕",
  shelf: "層架",
  bookcase: "書櫃",
  "storage-bench": "收納椅凳",
  "storage-box": "收納盒",
  lighting: "照明燈具",
});

export const QUESTIONNAIRE_PREFERENCE_FURNITURE_TYPES = Object.freeze({
  chair: { kitchen: ["dining-chair"], storage: ["office-chair"], living_room: ["lounge-chair"], bedroom: ["lounge-chair"], balcony: ["lounge-chair"], default: ["lounge-chair"] },
  desk: { default: ["desk"] },
  table: { kitchen: ["dining-table"], living_room: ["coffee-table"], default: ["desk"] },
  sofa: { default: ["sofa"] },
  wardrobe: { default: ["wardrobe"] },
  storage: { default: ["storage-cabinet"] },
});

export const ROOM_TYPE_EXCLUDED_FURNITURE_TYPES = Object.freeze({
  balcony: ["storage-cabinet", "wardrobe"],
});

export const ROOM_USAGE_OPTIONS = Object.freeze({
  living_room: [
    { id: "rest", label: "休息聊天" },
    { id: "watch", label: "看電視／影音" },
    { id: "host", label: "接待客人" },
    { id: "read", label: "閱讀休息" },
    { id: "work", label: "閱讀／工作" },
    { id: "shared_dining", label: "客餐廳共用" },
    { id: "kids", label: "兒童使用" },
  ],
  bedroom: [
    { id: "sleep", label: "睡眠休息" },
    { id: "work", label: "閱讀／工作" },
    { id: "dressing", label: "收納更衣" },
    { id: "kids", label: "兒童使用" },
  ],
  kitchen: [
    { id: "cook", label: "日常下廚" },
    { id: "prep", label: "備料收納" },
    { id: "dine", label: "簡單用餐" },
    { id: "host", label: "招待聚餐" },
  ],
  storage: [
    { id: "store", label: "集中收納" },
    { id: "laundry", label: "洗衣整理" },
    { id: "work", label: "閱讀／工作" },
    { id: "kids", label: "兒童使用" },
  ],
  bathroom: [
    { id: "bathe", label: "盥洗淋浴" },
    { id: "store", label: "衛浴收納" },
  ],
  balcony: [
    { id: "laundry", label: "洗曬衣物" },
    { id: "rest", label: "休憩植栽" },
  ],
  garage: [
    { id: "store", label: "工具與用品收納" },
    { id: "flex", label: "保留停車淨空" },
  ],
  entryway: [
    { id: "arrival", label: "出入整理" },
    { id: "store", label: "鞋物收納" },
  ],
  hallway: [
    { id: "passage", label: "通行動線" },
    { id: "store", label: "薄型收納" },
  ],
  stair: [
    { id: "passage", label: "上下通行" },
  ],
  default: [
    { id: "flex", label: "彈性使用" },
    { id: "store", label: "收納整理" },
  ],
});

export const ROOM_USAGE_FURNITURE_SPECS = Object.freeze({
  watch: [["tv-bench", "low"]],
  read: [["desk", "compact"], ["office-chair", "task"]],
  work: [["desk", "compact"], ["office-chair", "task"]],
  dressing: [["wardrobe", "two-door"], ["vanity-table", "standard"]],
  host: [["lounge-chair", "accent"]],
  dine: [["dining-table", "round-4"], ["dining-chair", "standard"]],
  prep: [["storage-cabinet", "low"]],
  store: [["storage-cabinet", "tall"]],
  laundry: [["storage-cabinet", "low"]],
  shared_dining: [["dining-table", "round-4"], ["dining-chair", "standard"]],
  arrival: [["mirror", "wall"]],
  // Corridors and stairs need clear circulation. Lighting belongs to the
  // ceiling/equipment flow, not the movable-furniture catalog.
  passage: [],
  kids: [["storage-cabinet", "low"]],
});

// 第 5 步只用用途情境幫使用者快速理解選擇；實際家具仍由既有
// 型錄、RAG 與第 6 步配置流程決定。用途不使用容易誤導的風格照片，
// 改以一致的空間用途圖示呈現，讓每個房型都有可辨識的視覺提示。
export const ROOM_USAGE_VISUALS = Object.freeze({
  sleep: { symbol: "床", tone: "rest", caption: "以睡眠與放鬆為主" },
  rest: { symbol: "休", tone: "rest", caption: "保留舒適的休息留白" },
  watch: { symbol: "影", tone: "social", caption: "影音與日常休憩" },
  host: { symbol: "客", tone: "social", caption: "方便聊天與招待" },
  read: { symbol: "讀", tone: "focus", caption: "閱讀與安靜停留" },
  work: { symbol: "桌", tone: "focus", caption: "專注工作與收納" },
  dressing: { symbol: "衣", tone: "care", caption: "更衣與梳妝收納" },
  kids: { symbol: "童", tone: "play", caption: "保留安全活動範圍" },
  cook: { symbol: "爐", tone: "kitchen", caption: "以烹飪動線為主" },
  prep: { symbol: "檯", tone: "kitchen", caption: "備料與收納更順手" },
  dine: { symbol: "餐", tone: "social", caption: "規劃日常用餐位置" },
  shared_dining: { symbol: "餐", tone: "social", caption: "兼顧用餐與交流" },
  store: { symbol: "櫃", tone: "storage", caption: "提高收納與分類效率" },
  laundry: { symbol: "洗", tone: "service", caption: "保留洗曬與家事動線" },
  bathe: { symbol: "浴", tone: "care", caption: "以清潔與安全為主" },
  arrival: { symbol: "玄", tone: "arrival", caption: "進出、落塵與隨手收納" },
  passage: { symbol: "路", tone: "service", caption: "保留清楚通行寬度" },
  flex: { symbol: "多", tone: "flex", caption: "保留可調整的多用途空間" },
});

export function roomUsageVisual(optionId) {
  return ROOM_USAGE_VISUALS[optionId] || ROOM_USAGE_VISUALS.flex;
}

export const QUESTIONNAIRE_CATALOG_SPACES = Object.freeze([
  { id: "entryway", label: "玄關", group: "storage" },
  { id: "hallway", label: "走道", group: "storage" },
  { id: "living_room", label: "客廳", group: "living" },
  { id: "kitchen", label: "廚房", group: "dining_kitchen" },
  { id: "bedroom", label: "臥室", group: "bedroom" },
  { id: "bathroom", label: "浴室", group: "bathroom" },
  { id: "balcony", label: "陽台", group: "outdoor" },
  { id: "storage", label: "儲藏室", group: "study" },
  { id: "garage", label: "車庫", group: "storage" },
]);

export const QUESTIONNAIRE_CATALOG_PURPOSES = Object.freeze({
  bedroom: [
    ["sleep", "睡眠", ["bed", "bedside-table"]],
    ["storage", "收納", ["wardrobe", "storage-cabinet"]],
    ["dress", "更衣", ["wardrobe", "mirror", "stool-bench"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair", "lounge-chair"]],
    ["vanity", "梳妝", ["mirror", "desk", "stool-bench"]],
  ],
  living_room: [
    ["rest", "休息聊天", ["sofa", "coffee-table", "lounge-chair"]],
    ["media", "影音", ["tv-bench", "sofa", "lounge-chair"]],
    ["dining", "用餐", ["dining-table", "dining-chair", "storage-cabinet"]],
    ["work", "閱讀工作", ["desk", "office-chair", "armchair", "lounge-chair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "storage-cabinet", "stool-bench"]],
  ],
  kitchen: [
    ["dining", "用餐", ["dining-table", "dining-chair"]],
    ["prep", "備餐收納", ["appliance-cabinet", "storage-cabinet"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "dining-chair"]],
  ],
  storage: [
    ["storage", "收納整理", ["storage-cabinet", "wardrobe", "shelf"]],
    ["work", "閱讀工作", ["desk", "office-chair"]],
    ["kids", "兒童使用", ["kids-chairs-stool", "storage-cabinet"]],
  ],
  entryway: [["entry", "出門整理", ["mirror", "storage-cabinet", "stool-bench"]]],
  hallway: [["passage", "走道收納", ["mirror", "storage-cabinet"]]],
  bathroom: [["wash", "盥洗收納", ["bathroom-vanity", "mirror-cabinet", "storage-cabinet"]]],
  balcony: [["relax", "休憩植栽", ["lounge-chair", "flower-pots-planter", "stool-bench"]]],
  garage: [["garage", "工具收納", ["storage-cabinet", "shelf"]]],
});

export const QUESTIONNAIRE_CATALOG_PURPOSE_TYPES = Object.freeze({
  "bedroom:sleep": ["bed", "mattress"],
  "bedroom:storage": ["pax-wardrobe", "wardrobe", "chests-of-drawer"],
  "bedroom:dress": ["pax-wardrobe", "wardrobe", "mirror", "stool-bench"],
  "bedroom:work": ["desk", "office-chair", "armchair", "lounge-chair"],
  "bedroom:vanity": ["mirror", "desk", "stool-bench"],
  "living_room:rest": ["fabric-sofa", "sofa", "leather-sofa", "modular-sofa", "coffee-table", "armchair"],
  "living_room:media": ["tv-bench", "tv-media-furniture", "sofa", "armchair"],
  "living_room:dining": ["dining-table", "dining-chair", "bar-table"],
  "living_room:work": ["desk", "office-chair", "armchair", "lounge-chair"],
  "living_room:kids": ["kids-chairs-stool", "storage-boxes-basket", "stool-bench"],
  "kitchen:dining": ["dining-table", "dining-chair", "bar-table"],
  "kitchen:prep": ["table", "bar-table", "stool-bench"],
  "kitchen:kids": ["dining-chair", "kids-chairs-stool", "stool-bench"],
  "storage:storage": ["cabinet-cupboard", "shelving-unit", "bookcase", "storage-boxes-basket"],
  "storage:work": ["desk", "office-chair", "gaming-chair"],
  "storage:kids": ["storage-boxes-basket", "kids-chairs-stool", "stool-bench"],
  "entryway:entry": ["shoe-cabinet", "mirror", "stool-bench", "clothes-rack"],
  "hallway:passage": ["wall-shelf", "mirror", "shoe-cabinet"],
  "bathroom:wash": ["mirror-cabinet", "bathroom-vanity", "storage-cabinet"],
  "balcony:relax": ["lounge-chair", "flower-pots-planter", "stool-bench"],
  "garage:garage": ["cabinet-cupboard", "shelving-unit", "storage-solution-system"],
});

export const QUESTIONNAIRE_CATALOG_TYPE_PURPOSE_LABELS = Object.freeze({
  "office-chair": "閱讀工作", "gaming-chair": "閱讀工作", armchair: "閱讀休憩",
  "lounge-chair": "閱讀休憩", "dining-chair": "用餐", "stool-bench": "梳妝／臨時座位",
  "kids-chairs-stool": "兒童使用", bed: "睡眠", wardrobe: "收納更衣", desk: "閱讀工作",
  "dining-table": "用餐", sofa: "休息聊天", "coffee-table": "客廳置物", "tv-bench": "影音",
  "storage-cabinet": "收納整理",
});

export const QUESTIONNAIRE_CATALOG_EXTRA_PURPOSE_LABELS = Object.freeze({
  "pax-wardrobe": "收納更衣",
  "fabric-sofa": "休息招待",
  "leather-sofa": "休息招待",
  "modular-sofa": "休息招待",
  table: "備餐整理",
  "bar-table": "用餐備餐",
  "cabinets-cupboard": "收納整理",
  "cabinet-cupboard": "收納整理",
  "shelving-unit": "收納整理",
  "storage-boxes-basket": "收納整理",
  "storage-solution-system": "收納整理",
  "wall-shelf": "走道收納",
  "shoe-cabinet": "玄關整理",
  "clothes-rack": "玄關整理",
  "tv-media-furniture": "影音設備",
  "chests-of-drawer": "收納整理",
  mirror: "更衣梳妝",
  "large-medium-rug": "休息活動區",
  "runner-small-rug": "走道鋪設",
  "floor-lamp": "閱讀照明",
  planter: "陽台休憩",
  decoration: "空間點綴",
  "pillow-cushion": "休息舒適",
  shelf: "收納整理",
  bookcase: "閱讀工作",
  "storage-bench": "收納整理",
  "storage-box": "收納整理",
  lighting: "照明安全",
});

export const CATALOG_FACET_TRADITIONAL_LABELS = Object.freeze({
  color: Object.freeze({
    "dark grey": "深灰色",
    "dark gray": "深灰色",
    oak: "橡木色",
    anthracite: "煤灰色",
    bamboo: "竹色",
    birch: "樺木色",
    white: "白色",
    ivory: "象牙白",
    cream: "奶油色",
    beige: "米色",
    grey: "灰色",
    gray: "灰色",
    black: "黑色",
    brown: "棕色",
    blue: "藍色",
    green: "綠色",
    yellow: "黃色",
    red: "紅色",
    natural: "自然原木色",
    wood: "木色",
    walnut: "胡桃木色",
    pine: "松木色",
  }),
  material: Object.freeze({
    "glb材質（未標示）": "模型材質（未標示）",
    acacia: "相思木",
    aluminium: "鋁",
    aluminum: "鋁",
    wood: "木材",
    metal: "金屬",
    steel: "鋼材",
    "stainless steel": "不鏽鋼",
    iron: "鐵材",
    plastic: "塑膠",
    "polystyrene plastic": "聚苯乙烯塑膠",
    fabric: "布料",
    textile: "織物",
    leather: "皮革",
    "faux fur": "仿毛皮",
    sheepskin: "羊皮",
    glass: "玻璃",
    rattan: "藤編",
    bamboo: "竹材",
    beech: "櫸木",
    birch: "樺木",
    brass: "黃銅",
    chrome: "鍍鉻",
    cork: "軟木",
    nickel: "鎳",
    pine: "松木",
    foam: "泡棉",
    cotton: "棉",
    "pu皮革": "人造皮革",
    pvc: "聚氯乙烯塑膠",
    ceramic: "陶瓷",
    marble: "大理石",
    stone: "石材",
    concrete: "混凝土",
    terracotta: "赤陶",
    velvet: "絲絨",
    seagrass: "海草",
    "water hyacinth": "水葫蘆纖維",
    plywood: "夾板",
    veneer: "木皮",
    "wood veneer": "木皮",
    "solid wood": "實木",
    mdf: "密集板",
    particleboard: "塑合板",
    walnut: "胡桃木",
    oak: "橡木",
  }),
});
