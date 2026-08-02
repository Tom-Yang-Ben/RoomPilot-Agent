import {
  fetchStylesData,
  formatList,
  formatTypeLabel,
  initBackgroundFx,
  reportPageBootFailure,
} from "./common.js?v=sha256-5e0e1418411f";

// 型錄 503 時退回空資料集：畫面會是空的風格牆加一條錯誤橫幅，而不是白畫布。
let data = {};
try {
  data = await fetchStylesData();
} catch (error) {
  reportPageBootFailure(error, "風格資料");
}
const tabRow = document.getElementById("style-tab-row");
const taiwanStyleGallery = document.getElementById("taiwan-style-gallery");
const taiwanStyleCards = data.taiwan_style_cards || [];
const taiwanStyleById = new Map(taiwanStyleCards.map((style) => [style.style_id, style]));
const surfaceCatalog = data.surface_catalog || { surfaces: [], style_surface_profiles: {} };
const surfaceById = new Map((surfaceCatalog.surfaces || []).map((surface) => [surface.surface_id, surface]));
const STYLE_CARD_STORAGE_KEY = "roompilot:selectedStyleCard";
const STYLE_CARD_PALETTE_LABELS = {
  japanese_tea_zen: ["榻榻米", "竹青", "胡桃木", "茶褐"],
};
const STYLE_CARD_COPY = {
  scandinavian_1:
    "淺木、米白與棉麻讓空間像早晨的客廳，明亮但不刺眼。適合喜歡植物、木質收納與柔軟布沙發的人，家裡會呈現乾淨、放鬆、很好生活的北歐感。",
  scandinavian_2:
    "白牆、淡綠與清透木色把視覺變輕，像把窗邊的自然感留在室內。適合小坪數或採光普通的家，能讓家具輪廓更清爽，氣氛也更有呼吸感。",
  scandinavian_3:
    "低彩度灰、霧面材質與深色點綴，讓北歐風從可愛轉向成熟。適合想要安靜、耐看、不容易膩的空間，保留溫度但少一點甜味。",
  modern_minimal_1:
    "黑白對比讓線條變得俐落，適合重視秩序、收納與乾淨視覺的人。家具不需要很多裝飾，靠比例、留白和材質細節就能撐起現代感。",
  modern_minimal_2:
    "暖灰比純灰更適合居家，能把石材、布料和霧面金屬收在同一個柔和層次裡。整體氣質沉穩、細膩，適合想要高級但不冰冷的現代空間。",
  modern_minimal_3:
    "自然留白讓牆面、地板與家具之間保有距離，視覺不擁擠。適合生活物件多、但希望家看起來仍然清爽的人，用少量木色建立溫度。",
  japanese_minimal_1:
    "侘寂自然重視不完美的痕跡，米灰牆面、粗陶器皿與低彩度木色會讓空間慢下來。適合喜歡安靜、手作感與留白的人。",
  japanese_minimal_2:
    "榻榻米、茶席與低家具把生活高度放低，胡桃木與竹青色讓空間有沉靜的禪意。適合想要閱讀、品茶、盤腿坐下來放鬆的日式角落。",
  japanese_minimal_3:
    "現代和風把日式木格柵、留白牆面與深色線條收得更俐落。它不像傳統和室那麼濃，而是適合都會住宅的安靜、克制與溫潤。",
  nordic_modern_1:
    "奶油米白把北歐風變得更柔軟，搭配淺木與圓角家具，能讓客廳有被陽光包住的感覺。適合想要明亮、溫柔、不壓迫的家。",
  nordic_modern_2:
    "法式柔霧把灰粉、霧面白與細緻曲線放在一起，氛圍比北歐更優雅。適合喜歡柔和線條、拱形元素與輕盈布料的人。",
  nordic_modern_3:
    "奶茶色像午後拿鐵一樣柔和，搭配圓弧沙發、霧面木皮與米白布料，讓家裡有溫柔的生活感；適合想要乾淨、暖心但不過度甜美的客廳。",
  industrial_1:
    "黑鐵、水泥與皮革色讓空間帶有倉庫感，但比例要乾淨才不會厚重。適合喜歡開放層架、金屬細節與俐落家具的人。",
  industrial_2:
    "復古工坊用舊木、焦糖皮革和暖黃燈光增加故事感，像有人長期使用過的工作室。適合收藏、書籍、音響或手作工具能被看見的空間。",
  industrial_3:
    "極簡冷調把工業風收斂成黑、灰、金屬與乾淨直線，少了粗獷，多了都會感。適合想要冷靜、俐落、帶一點科技感的住宅。",
  wabi_sabi_1:
    "鄉村溫馨用暖木、手感織品與低彩度牆面堆出安定感，像假日午後的慢生活。適合喜歡木桌、藤編、陶器與柔和燈光的人。",
  wabi_sabi_2:
    "經典優雅保留侘寂的安靜，但把線條整理得更端正。深木、米灰與少量深色能讓空間成熟耐看，適合沉穩、有儀式感的客廳。",
  wabi_sabi_3:
    "現代輕奢把侘寂的樸素感加上細緻金屬與深色家具，氣氛安靜但更有質感。適合想要低調、乾淨，又希望空間有一點精緻度的人。",
};
const STYLE_IMAGE_VERSION = "20260708d";

const STYLE_IMAGE_MAP = {
  scandinavian: "/static/style_images/scandinavian.png",
  modern: "/static/style_images/modern.png",
  minimalist_muji: "/static/style_images/minimalist_muji_variant.png",
  nordic_modern: "/static/style_images/nordic_modern.png",
  industrial: "/static/style_images/industrial.png",
  wabi_sabi: "/static/style_images/wabi_sabi.png",
  melad: "/static/style_images/melad.png",
  american: "/static/style_images/american.png",
  american_country: "/static/style_images/american_country.png",
  light_luxury: "/static/style_images/light_luxury.png",
  classical: "/static/style_images/classical.png",
  eclectic: "/static/style_images/eclectic.png",
};

const STYLE_ANNOTATIONS = {
  scandinavian: [
    ["大面採光窗", 18, 22],
    ["淺木層架", 72, 24],
    ["植栽點綴", 82, 58],
    ["淺米布沙發", 30, 73],
    ["溫潤木桌", 58, 82],
  ],
  modern: [
    ["俐落線條", 22, 24],
    ["低彩度主牆", 70, 24],
    ["金屬與玻璃", 74, 62],
    ["模組沙發", 32, 72],
    ["留白動線", 56, 82],
  ],
  minimalist_muji: [
    ["低飽和米白", 22, 24],
    ["自然木質收納", 68, 24],
    ["少量生活器物", 78, 58],
    ["低矮家具", 31, 74],
    ["乾淨留白", 57, 82],
  ],
  nordic_modern: [
    ["灰白基底", 22, 24],
    ["淺木與黑框", 70, 24],
    ["機能層架", 78, 58],
    ["柔和布料", 32, 72],
    ["簡潔光源", 56, 82],
  ],
  industrial: [
    ["深色鐵件", 22, 25],
    ["灰階牆面", 68, 24],
    ["粗獷木紋", 78, 58],
    ["皮革或深色沙發", 31, 73],
    ["外露結構感", 57, 82],
  ],
  wabi_sabi: [
    ["霧面礦物牆", 23, 24],
    ["不規則陶器", 70, 25],
    ["自然枯枝植栽", 80, 58],
    ["低矮厚實座椅", 32, 74],
    ["留白與陰影", 58, 82],
  ],
  melad: [
    ["焦糖棕主色", 22, 24],
    ["深木材質", 70, 24],
    ["暖黃光源", 80, 58],
    ["棕色皮革/布料", 31, 73],
    ["濃郁層次", 58, 82],
  ],
  american: [
    ["大尺度沙發", 22, 24],
    ["線板或木質牆", 70, 25],
    ["沉穩木櫃", 78, 58],
    ["厚實抱枕", 31, 73],
    ["對稱陳列", 58, 82],
  ],
  american_country: [
    ["鄉村木紋", 22, 24],
    ["暖白牆面", 70, 24],
    ["藤編與植栽", 80, 58],
    ["格紋/棉麻布料", 31, 73],
    ["手作感配件", 58, 82],
  ],
  light_luxury: [
    ["大理石紋", 22, 24],
    ["金屬線條", 70, 24],
    ["玻璃反光", 78, 58],
    ["絨布座椅", 31, 73],
    ["精緻對比", 58, 82],
  ],
  classical: [
    ["古典線板", 22, 24],
    ["深木家具", 70, 24],
    ["花紋材質", 80, 58],
    ["厚實沙發", 31, 73],
    ["對稱比例", 58, 82],
  ],
  eclectic: [
    ["跳色牆面", 22, 24],
    ["混搭圖案", 70, 24],
    ["藝術裝飾", 80, 58],
    ["不同材質並置", 31, 73],
    ["強烈個性", 58, 82],
  ],
};

function findTaiwanStyleCard(cardId) {
  if (!cardId) return null;
  const group = taiwanStyleCards.find((style) => style.cards?.some((card) => card.card_id === cardId));
  const card = group?.cards?.find((item) => item.card_id === cardId);
  return group && card ? { group, card } : null;
}

function readStoredStyleCardSelection() {
  try {
    const raw = sessionStorage.getItem(STYLE_CARD_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

const storedStyleCardSelection = readStoredStyleCardSelection();
let selectedStyleCardId = storedStyleCardSelection?.style_card || null;
if (selectedStyleCardId && !findTaiwanStyleCard(selectedStyleCardId)) {
  selectedStyleCardId = null;
}

let activeStyleId =
  findTaiwanStyleCard(selectedStyleCardId)?.group.scene_style_id ||
  taiwanStyleCards[0]?.scene_style_id ||
  data.styles[0]?.style_id ||
  null;
let surfaceCarouselTimers = [];
const SURFACE_CAROUSEL_INTERVAL_MS = 1500;

const STYLE_NAME_BY_ID = new Map(data.styles.map((style) => [style.style_id, style.style_name_zh || style.style_id]));

const STYLE_DETAIL_OVERRIDES = {
  melad: {
    keywords_zh: ["暖棕", "焦糖", "咖啡", "皮革", "秋日", "低光"],
    main_colors_zh: ["焦糖棕", "咖啡棕", "奶茶色"],
    palette_hex: ["#b97845", "#6f452d", "#c7a17d"],
    materials_zh: ["焦糖皮革", "深胡桃木", "礦物塗料", "銅色金屬", "粗織毯"],
    shape_features_zh: ["低矮厚實", "圓角包覆", "大片暖棕色塊", "柔和低光"],
    avoid_elements_zh: ["高彩度冷色", "亮白線板", "過多黑白對比", "鄉村碎花"],
  },
  american: {
    keywords_zh: ["奶油線板", "對稱櫃體", "壁爐主牆", "厚實沙發", "藍灰單椅", "經典過渡"],
    main_colors_zh: ["奶油白", "木色棕", "藍灰色"],
    palette_hex: ["#efe6d8", "#7b5435", "#5e7084"],
    materials_zh: ["線板牆", "內嵌書櫃", "深木茶几", "布面沙發", "黃銅壁燈"],
    shape_features_zh: ["左右對稱", "壁爐中心軸", "厚實扶手", "收邊線條明確"],
    avoid_elements_zh: ["全室焦糖棕", "過度昏暗", "無線板的極簡牆", "過多復古鄉村花紋"],
  },
};

data.styles.forEach((style) => {
  Object.assign(style, STYLE_DETAIL_OVERRIDES[style.style_id] || {});
});

function positiveStyleCandidates(item) {
  return (item?.style_candidates || []).filter((candidate) => {
    if (!candidate) return false;
    if (typeof candidate === "string") return true;
    return Boolean(candidate.style_id) && Number(candidate.score ?? 1) > 0;
  });
}

function styleCandidateIds(item) {
  return positiveStyleCandidates(item).map((candidate) => (typeof candidate === "string" ? candidate : candidate.style_id));
}

function hasStyleTag(item, styleId) {
  return styleCandidateIds(item).includes(styleId);
}

function countFurnitureForStyle(styleId) {
  return data.style_furniture_counts?.[styleId] ?? 0;
}

function countFurnitureTypes(items) {
  const counts = new Map();
  items.forEach((item) => {
    const typeName = item.normalized_type || "unknown";
    counts.set(typeName, (counts.get(typeName) || 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || formatTypeLabel(a[0]).localeCompare(formatTypeLabel(b[0]), "zh-Hant"));
}

function renderTypeCloud(typeCounts, emptyText = "目前沒有可列出的家具類型") {
  if (!typeCounts.length) return `<p>${emptyText}</p>`;
  return `
    <div class="style-type-cloud">
      ${typeCounts
        .map(
          ([typeName, count]) => `
            <span class="style-type-chip">
              <strong>${formatTypeLabel(typeName)}</strong>
              <small>${count}</small>
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

const FURNITURE_GROUPS = [
  { label: "桌子", match: ["desk", "table", "coffee-table", "dining-table", "side-table", "nightstand", "bedside-table", "console"] },
  { label: "椅子 / 座椅", match: ["chair", "armchair", "stool", "bench", "sofa", "loveseat", "seat", "seating"] },
  { label: "墊子 / 地毯", match: ["rug", "mat", "pad", "cushion", "pillow", "mattress"] },
  { label: "櫃子 / 收納", match: ["cabinet", "cupboard", "drawer", "storage", "wardrobe", "closet", "tv-bench", "sideboard", "shelving", "shelf", "bookcase", "rack"] },
  { label: "床 / 臥室", match: ["bed", "bed-frame", "headboard"] },
  { label: "燈具", match: ["lamp", "light", "lighting", "lantern"] },
  { label: "家電", match: ["fridge", "freezer", "air-conditioner", "washer", "washing", "dishwasher", "toaster", "kitchen-appliance", "fan", "purifier", "vacuum", "robot-vacuum", "hood", "dryer"] },
  { label: "裝飾 / 植栽", match: ["decoration", "decor", "plant", "planter", "vase", "flower", "art", "mirror", "clock"] },
  { label: "戶外家具", match: ["outdoor", "patio", "garden"] },
  { label: "其他家具", match: [""] },
];

const CLEAN_FURNITURE_GROUPS = [
  { label: "桌子", match: ["desk", "table", "coffee-table", "dining-table", "side-table", "nightstand", "bedside-table", "console"] },
  { label: "椅子 / 座椅", match: ["chair", "armchair", "stool", "bench", "sofa", "loveseat", "seat", "seating"] },
  { label: "墊子 / 地毯", match: ["rug", "mat", "pad", "cushion", "pillow", "mattress"] },
  { label: "櫃體 / 收納", match: ["cabinet", "cupboard", "drawer", "storage", "wardrobe", "closet", "tv-bench", "sideboard", "shelving", "shelf", "bookcase", "rack"] },
  { label: "床 / 臥室", match: ["bed", "bed-frame", "headboard"] },
  { label: "燈具", match: ["lamp", "light", "lighting", "lantern"] },
  { label: "家電", match: ["fridge", "freezer", "air-conditioner", "washer", "washing", "dishwasher", "toaster", "kitchen-appliance", "fan", "purifier", "vacuum", "robot-vacuum", "hood", "dryer"] },
  { label: "裝飾 / 植栽", match: ["decoration", "decor", "plant", "planter", "vase", "flower", "art", "mirror", "clock"] },
  { label: "戶外家具", match: ["outdoor", "patio", "garden"] },
];

function furnitureGroupLabel(typeName) {
  const normalized = String(typeName || "unknown").toLowerCase();
  const translated = formatTypeLabel(typeName).toLowerCase();
  const target = `${normalized} ${translated}`;
  const cleanGroup = CLEAN_FURNITURE_GROUPS.find((group) => group.match.some((keyword) => target.includes(keyword)));
  if (cleanGroup) return cleanGroup.label;
  return FURNITURE_GROUPS.find((group) => group.match.some((keyword) => target.includes(keyword)))?.label || "其他家具";
}

function countFurnitureGroups(items) {
  const counts = new Map();
  items.forEach((item) => {
    const groupName = furnitureGroupLabel(item.normalized_type);
    counts.set(groupName, (counts.get(groupName) || 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-Hant"));
}

function typeCountsToGroupCounts(typeCounts = []) {
  const counts = new Map();
  typeCounts.forEach(([typeName, count]) => {
    const groupName = furnitureGroupLabel(typeName);
    counts.set(groupName, (counts.get(groupName) || 0) + Number(count || 0));
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-Hant"));
}

function renderGroupCloud(groupCounts, emptyText = "目前沒有可列出的家具分類") {
  if (!groupCounts.length) return `<p>${emptyText}</p>`;
  return `
    <div class="style-type-cloud style-group-cloud">
      ${groupCounts
        .map(
          ([groupName, count]) => `
            <span class="style-type-chip style-group-chip">
              <strong>${groupName}</strong>
              <small>${count}</small>
            </span>
          `
        )
        .join("")}
    </div>
  `;
}

function renderStyleTagSummary(style) {
  const summary = data.summary || {};
  const totalItems = summary.total_furniture || 0;
  const taggedCount = summary.styled_furniture || 0;
  const activeGroupCounts = typeCountsToGroupCounts(data.style_type_counts?.[style.style_id] || []);

  return `
    <div class="style-db-summary-grid compact">
      <div>
        <span>全資料庫家具</span>
        <strong>${totalItems}</strong>
      </div>
      <div>
        <span>已具風格標籤</span>
        <strong>${taggedCount}/${totalItems}</strong>
      </div>
    </div>
    <h4>${style.style_name_zh} 命中的家具類型</h4>
    ${renderGroupCloud(activeGroupCounts)}
  `;
}

const STYLE_ANNOTATIONS_CLEAN = {
  scandinavian: [["大面採光窗", 24, 27], ["淺木開放層架", 47, 28], ["米白布沙發", 61, 63], ["藤編蒲團", 19, 74], ["低矮淺木茶几", 49, 82]],
  modern: [["深色電視主牆", 52, 31], ["深色收納層板", 66, 30], ["低彩度布沙發", 66, 63], ["黑色細腳邊几", 82, 70], ["玻璃金屬茶几", 42, 75]],
  minimalist_muji: [["障子窗光影", 29, 24], ["低矮原木茶几", 49, 67], ["留白電視牆", 74, 34], ["淺木電視櫃", 72, 62], ["米色布沙發", 65, 78]],
  nordic_modern: [["明亮大窗", 43, 29], ["淺木電視櫃", 29, 48], ["灰白布沙發", 68, 62], ["柔軟織品披毯", 65, 76], ["圓凳與小邊桌", 34, 78]],
  industrial: [["黑框大面窗", 20, 29], ["粗獷水泥牆", 55, 31], ["金屬開放層架", 73, 39], ["深色皮革座椅", 24, 73], ["黑鐵細框茶几", 52, 78]],
  wabi_sabi: [["米灰礦物牆面", 52, 30], ["拱形壁龕", 72, 41], ["圓潤布藝單椅", 22, 67], ["不規則木茶几", 50, 78], ["低彩度陶器", 43, 59]],
  melad: [["暖棕木質層架", 70, 24], ["壁爐中心視覺", 49, 43], ["厚實布沙發", 69, 66], ["深木茶几", 47, 78], ["暖色織品抱枕", 76, 57]],
  american: [["格窗自然採光", 20, 31], ["白色美式櫃體", 64, 42], ["對稱植栽層架", 72, 24], ["舒適布沙發", 29, 69], ["實木抽屜茶几", 48, 78]],
  american_country: [["鄉村格窗採光", 20, 30], ["白色壁爐櫃體", 56, 43], ["花卉與藤編感", 74, 28], ["條紋休閒椅", 86, 70], ["仿舊木茶几", 50, 78]],
  light_luxury: [["大理石電視牆", 53, 36], ["金屬吊燈線條", 50, 20], ["絨面單椅點綴", 22, 68], ["高級灰米沙發", 67, 64], ["石材茶几", 50, 77]],
  classical: [["水晶吊燈", 48, 18], ["對稱展示櫃", 68, 38], ["深色雕花木作", 49, 44], ["古典扶手椅", 25, 70], ["厚實布沙發", 72, 73]],
  eclectic: [["植栽與藝術牆", 20, 31], ["開放書牆混搭", 70, 36], ["復古圖紋地毯", 49, 82], ["異材質茶几組", 54, 70], ["跳色單椅", 80, 68]],
};

const STYLE_ANNOTATIONS_ROOM_FOCUS = {
  scandinavian: [["淺木收納櫃", 50, 29], ["米白布沙發", 58, 63], ["溫潤木茶几", 49, 78], ["編織地毯", 33, 75], ["植栽點綴", 78, 42]],
  modern: [["深色電視主牆", 52, 31], ["深色收納層板", 66, 30], ["低彩度布沙發", 66, 63], ["黑色細腳邊几", 82, 70], ["玻璃金屬茶几", 42, 75]],
  minimalist_muji: [["留白電視牆", 74, 34], ["淺木電視櫃", 72, 62], ["低矮原木茶几", 49, 67], ["米色布沙發", 65, 78], ["格柵收納線條", 59, 25]],
  nordic_modern: [["淺木電視櫃", 29, 48], ["灰白布沙發", 68, 62], ["柔軟織品披毯", 65, 76], ["圓凳與小邊桌", 34, 78], ["黑白細框線條", 43, 29]],
  industrial: [["黑框金屬隔間", 20, 29], ["粗獷深色牆面", 55, 31], ["開放式層架", 73, 39], ["皮革座椅", 24, 73], ["深色木質桌面", 52, 78]],
  wabi_sabi: [["米灰礦物牆面", 55, 30], ["拱形牆面", 42, 29], ["壁龕陶器", 82, 43], ["圓潤布藝單椅", 35, 69], ["不規則木茶几", 55, 77]],
  melad: [["奶茶礦物牆", 38, 34], ["焦糖皮革沙發", 65, 63], ["深胡桃木層架", 73, 28], ["深木厚茶几", 45, 77], ["銅色桌燈", 86, 58]],
  american: [["深木對稱壁櫃", 54, 27], ["壁爐主牆", 50, 48], ["皮革鉚釘單椅", 37, 62], ["厚重木茶几", 58, 74], ["黃銅黑色桌燈", 79, 42]],
  american_country: [["刷舊木櫃", 56, 43], ["花器與陶罐", 74, 28], ["格紋織品座椅", 86, 70], ["復古木茶几", 50, 78], ["溫暖米色牆面", 20, 30]],
  light_luxury: [["石材電視牆", 53, 36], ["金屬線條櫃體", 50, 20], ["絨面單椅", 22, 68], ["灰米色沙發", 67, 64], ["大理石茶几", 50, 77]],
  classical: [["天花線板", 48, 18], ["展示收納櫃", 68, 38], ["深色雕花桌", 49, 44], ["古典扶手椅", 25, 70], ["厚實布沙發", 72, 73]],
  eclectic: [["植栽與裝飾混搭", 20, 31], ["彩色層架", 70, 36], ["圖案地毯", 49, 82], ["異材質茶几", 54, 70], ["亮色抱枕", 80, 68]],
};

const STYLE_ANNOTATION_OVERRIDES = {
  melad: [["奶茶礦物牆", 40, 34], ["焦糖皮革沙發", 66, 63], ["深胡桃木層架", 73, 28], ["咖啡厚木茶几", 46, 77], ["銅色桌燈", 86, 58]],
  american: [["奶油線板牆", 53, 28], ["壁爐中心軸", 51, 58], ["對稱內嵌櫃", 68, 31], ["藍灰布面單椅", 25, 67], ["厚實深木茶几", 47, 76]],
  american_country: [["白色壁爐櫃體", 66, 43], ["藤編置物籃", 72, 23], ["花卉棉麻抱枕", 43, 58], ["仿舊木茶几", 55, 75], ["條紋休閒椅", 84, 69]],
  eclectic: [["植栽與藝術牆", 39, 31], ["開放書牆混搭", 70, 31], ["異材質茶几組", 57, 72], ["復古圖紋地毯", 49, 82], ["跳色單椅", 66, 50]],
};

const SURFACE_DISPLAY = {
  wood_light_oak_floor_039: ["淺橡木木地板", "木地板", "淺橡木色"],
  wood_warm_floor_051: ["溫潤橡木木地板", "木地板", "暖橡木色"],
  wood_deep_floor_064: ["深胡桃木木地板", "木地板", "深胡桃木色"],
  wood_dark_panel_093: ["深色木紋板", "木紋", "深木色"],
  woodtile_light_cci212048: ["淺木紋磚", "木紋磚", "淺木色"],
  woodtile_warm_cal288017: ["暖木紋磚", "木紋磚", "暖木色"],
  woodtile_gray_cdg212132: ["灰木紋磚", "木紋磚", "灰木色"],
  woodtile_clean_cal160101: ["淨灰木紋磚", "木紋磚", "淺灰木色"],
  tile_marble_cal330121: ["米白大理石磚", "磁磚 / 石材", "米白色"],
  tile_gray_cdg212132: ["灰石紋磁磚", "磁磚 / 石材", "石灰色"],
  tile_warm_ced360298: ["暖灰霧面磁磚", "磁磚 / 石材", "暖灰色"],
  tile_pattern_cal288001: ["花磚 / 圖紋磚", "磁磚 / 石材", "圖紋暖色"],
};

const GENERATED_WALLS = {
  scandinavian: [["暖白霧面牆", "#f4ede3", "明亮乾淨，作為北歐風的安靜背景，不與地板材質混用。"], ["淺灰礦物牆", "#d8d6cf", "低彩度霧面牆面，讓淺木家具與植栽更突出。"]],
  modern: [["霧白微水泥牆", "#ebe8e2", "用程式生成細緻霧面質感，維持現代風的俐落基底。"], ["冷灰重點牆", "#9da1a3", "局部冷灰牆面，支撐黑白灰與金屬線條。"]],
  minimalist_muji: [["奶油白塗料牆", "#f2eadf", "柔和白牆搭配淺木，避免牆面材質過度搶戲。"], ["米灰石灰感牆", "#d7cabb", "程式生成輕微手刷紋理，保留無印風的自然留白。"]],
  nordic_modern: [["冷白牆面", "#edf0ef", "乾淨冷白提高採光感，讓灰階家具更俐落。"], ["淺灰藍牆", "#c9d0d2", "低飽和冷調，連接北歐與現代感。"]],
  industrial: [["炭灰微水泥牆", "#57504a", "程式生成粗霧面質感，搭配黑鐵與深木。"], ["水泥灰牆", "#9b9790", "保留粗獷感，但不直接套用地板材質。"]],
  wabi_sabi: [["暖灰礦物牆", "#cfc4b4", "霧面、低反光、帶手作感，是侘寂風主牆基底。"], ["砂岩米牆", "#d8c6ad", "自然不均勻色差，襯托陶器與低矮家具。"]],
  melad: [["奶茶棕牆", "#b99678", "溫暖棕調牆面，搭配深木與黃銅。"], ["焦糖米牆", "#c8a681", "讓美拉德色系更有包覆感。"]],
  american: [["暖白線板牆", "#efe6da", "可程式生成線板與暖白底，維持美式大器感。"], ["奶油米牆", "#e5d4bf", "柔和牆色搭配深木家具。"]],
  american_country: [["鄉村暖白牆", "#f0e6d8", "搭配木作與棉麻軟裝，牆面保持乾淨。"], ["淡米灰牆", "#d8cbb9", "讓圖紋與藤編成為重點。"]],
  light_luxury: [["米白石紋生成牆", "#ece5dc", "以程式生成細緻石紋感，不把地板材質直接搬到牆上。"], ["霧灰精品牆", "#cbc9c4", "低彩度底色襯托金屬與玻璃。"]],
  classical: [["暖白線板牆", "#eadfce", "古典風以線板與比例塑造牆面，不依賴地板材質。"], ["米金壁面", "#d8c2a2", "帶溫度的古典背景，適合深木與花紋。"]],
  eclectic: [["跳色重點牆", "#b86f5a", "由程式依風格生成局部跳色，搭配圖紋家具。"], ["暖米背景牆", "#e1cfb9", "讓混搭家具與飾品有穩定背景。"]],
};

const GENERATED_WALL_OPTIONS = {
  scandinavian: [
    ["暖白霧面牆", "#f4ede3", "明亮乾淨，讓淺木、米白布料與自然採光成為主角。"],
    ["燕麥米牆", "#e8dccb", "比純白更柔和，適合北歐風的低彩度溫度。"],
    ["淺灰綠牆", "#d8dfd5", "帶一點植栽感，不破壞清爽自然的基調。"],
    ["霧灰白牆", "#d9d8d2", "適合想要更安靜、低反光的北歐背景。"],
    ["淡奶茶牆", "#dfcdb8", "和藤編、淺木地板相容，讓空間更溫暖。"],
    ["雪白主牆", "#f7f5ef", "保留最大採光感，適合小坪數或明亮客廳。"],
  ],
  modern: [
    ["霧白微水泥牆", "#ebe8e2", "維持現代風的俐落基底。"],
    ["冷灰主牆", "#9da1a3", "搭配黑白灰與金屬線條。"],
    ["炭灰重點牆", "#56595b", "強化電視牆與深色家具的俐落感。"],
    ["石墨米灰牆", "#c7c2ba", "保留溫度又不失現代感。"],
    ["純白展示牆", "#f5f5f2", "適合凸顯黑色細框與燈具。"],
    ["淺水泥灰牆", "#b8b6b0", "降低反光，讓空間更成熟。"],
  ],
  minimalist_muji: [
    ["奶油白塗料牆", "#f2eadf", "柔和白牆搭配淺木，避免過度搶戲。"],
    ["米灰石灰感牆", "#d7cabb", "保留無印風的自然留白。"],
    ["原棉白牆", "#f6f1e8", "最乾淨、最適合收納展示的底色。"],
    ["亞麻米牆", "#e3d7c6", "讓棉麻、藤編與低矮家具更協調。"],
    ["淡木灰牆", "#d4d1c7", "適合搭配淺橡木與灰白地板。"],
    ["溫潤砂色牆", "#cfc1ad", "增加一點手作溫度。"],
  ],
  nordic_modern: [
    ["冷白牆面", "#edf0ef", "提高採光感，讓灰階家具更俐落。"],
    ["淺灰藍牆", "#c9d0d2", "連接北歐與現代感。"],
    ["雲霧灰牆", "#d9dedf", "適合藍灰布沙發與白色櫃體。"],
    ["霜白牆", "#f3f5f1", "保留北歐明亮、乾淨的表情。"],
    ["淡鼠尾草牆", "#cbd7cd", "帶自然感但不偏鄉村。"],
    ["暖灰米牆", "#ded8cd", "讓現代線條不會太冷。"],
  ],
  industrial: [
    ["炭灰微水泥牆", "#57504a", "搭配黑鐵與深木。"],
    ["水泥灰牆", "#9b9790", "保留粗獷感，但不套用地板材質。"],
    ["煙燻黑牆", "#373432", "適合局部重點牆與皮革家具。"],
    ["鏽棕灰牆", "#756357", "呼應金屬、舊木與暖燈。"],
    ["裸灰牆", "#b0aaa2", "降低壓迫感，適合小空間工業風。"],
    ["深橄欖灰牆", "#555a4f", "讓植栽與黑鐵層架更有層次。"],
  ],
  wabi_sabi: [
    ["暖灰礦物牆", "#cfc4b4", "低反光、帶手作感，是侘寂風主牆基底。"],
    ["砂岩米牆", "#d8c6ad", "自然不均勻色差，襯托陶器與低矮家具。"],
    ["陶土米牆", "#cbb49b", "讓空間有安靜的粗樸感。"],
    ["灰褐石灰牆", "#b7aa9b", "適合搭配圓潤沙發與原木茶几。"],
    ["霧白泥牆", "#e8dfd2", "保留留白，又有細緻紋理感。"],
    ["淡岩灰牆", "#cac8bf", "讓陶器與枯枝更凸顯。"],
  ],
  melad: [
    ["奶茶棕牆", "#b99678", "溫暖棕調牆面，搭配深木與黃銅。"],
    ["焦糖米牆", "#c8a681", "讓美拉德色系更有包覆感。"],
    ["可可棕牆", "#8a6248", "適合作為局部重點牆。"],
    ["杏仁拿鐵牆", "#d7b99b", "讓沙發與木作更溫暖。"],
    ["淺駝色牆", "#c7a78a", "適合搭配米白布料。"],
    ["深摩卡牆", "#6d4f3d", "用在小面積能增加精緻度。"],
  ],
  american: [
    ["暖白線板牆", "#efe6da", "維持美式大器感。"],
    ["奶油米牆", "#e5d4bf", "柔和牆色搭配深木家具。"],
    ["象牙白牆", "#f2eadf", "適合線板、壁爐與大窗。"],
    ["淡卡其牆", "#d8c2aa", "讓厚實沙發與木質茶几更穩重。"],
    ["淺灰藍牆", "#c6d0d1", "可做美式清爽版本。"],
    ["溫灰牆", "#c8c1b7", "降低鄉村感，轉向都會美式。"],
  ],
  american_country: [
    ["鄉村暖白牆", "#f0e6d8", "搭配木作與棉麻軟裝。"],
    ["淡米灰牆", "#d8cbb9", "讓圖紋與藤編成為重點。"],
    ["奶油黃牆", "#ead8b8", "帶一點田園陽光感。"],
    ["鼠尾草綠牆", "#b9c6b0", "適合花卉、格紋與白木櫃。"],
    ["仿舊米牆", "#d1bfa8", "搭配仿舊木地板更自然。"],
    ["柔白木作牆", "#f6efe5", "讓壁爐與櫃體保持清爽。"],
  ],
  light_luxury: [
    ["米白石紋生成牆", "#ece5dc", "細緻石紋感，不把地板材質搬到牆上。"],
    ["霧灰精品牆", "#cbc9c4", "襯托金屬與玻璃。"],
    ["香檳米牆", "#e5d4bf", "呼應金屬線條與暖光。"],
    ["珍珠白牆", "#f4f1ec", "讓大理石與燈具更亮。"],
    ["冷灰石牆", "#b7b9b7", "適合更現代的輕奢版本。"],
    ["深墨綠牆", "#344840", "局部使用可凸顯高級感。"],
  ],
  classical: [
    ["暖白線板牆", "#eadfce", "用線板與比例塑造古典背景。"],
    ["米金壁面", "#d8c2a2", "適合深木與花紋。"],
    ["象牙白牆", "#f2eadf", "讓雕花與吊燈保持明亮。"],
    ["古典灰綠牆", "#aeb8a7", "適合展示櫃與深木家具。"],
    ["深胡桃牆", "#5b3f2f", "局部使用可拉出厚重感。"],
    ["玫瑰米牆", "#d5b8aa", "讓古典風更柔和。"],
  ],
  eclectic: [
    ["跳色重點牆", "#b86f5a", "搭配圖紋家具與藝術牆。"],
    ["暖米背景牆", "#e1cfb9", "讓混搭家具有穩定背景。"],
    ["墨綠展示牆", "#40584a", "適合植栽、畫作與復古家具。"],
    ["靛藍局部牆", "#43566c", "讓跳色單椅與地毯更有舞台感。"],
    ["芥末黃牆", "#c8a14a", "小面積使用能增加混搭趣味。"],
    ["煙粉牆", "#c99c91", "讓復古與現代物件更柔和。"],
  ],
};

function readable(value) {
  const text = String(value ?? "").trim();
  return Boolean(text) && !text.includes("\ufffd") && !text.includes("嚙") && !text.includes("?");
}

function safeList(items = [], fallback = "尚未整理") {
  const filtered = items.filter(readable);
  return filtered.length ? formatList(filtered) : fallback;
}

function styleSurfaces(style, usage) {
  const profile = style.surface_profile || surfaceCatalog.style_surface_profiles?.[style.style_id] || {};
  const ids = usage === "wall" ? profile.wall_surface_ids : profile.floor_surface_ids;
  return (ids || []).map((id) => surfaceById.get(id)).filter(Boolean);
}

function defaultSurface(style, usage) {
  const profile = style.surface_profile || surfaceCatalog.style_surface_profiles?.[style.style_id] || {};
  const id = usage === "wall" ? profile.default_wall_surface_id : profile.default_floor_surface_id;
  return surfaceById.get(id) || styleSurfaces(style, usage)[0] || null;
}

function surfaceReason(style, surface, usage) {
  if (!surface) return "尚未整理材質說明。";
  const target = usage === "wall" ? "牆面" : "地板";
  return `${surface.style_notes_zh || "適合作為此風格的主要材質。"} 用在${target}時，可強化 ${style.style_name_zh} 的材質語彙。`;
}

function renderTabs() {
  tabRow.innerHTML = "";
  taiwanStyleCards.forEach((style, index) => {
    const colors = style.palette_hex?.length
      ? style.palette_hex
      : style.cards?.[0]?.palette_hex?.length
        ? style.cards[0].palette_hex
        : ["#f4eadc", "#d7c2a8", "#a88462"];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "style-tab-button";
    button.style.setProperty("--tab-tone-a", colors[0]);
    button.style.setProperty("--tab-tone-b", colors[1] ?? colors[0]);
    button.innerHTML = `
      <span class="style-tab-index">${String(index + 1).padStart(2, "0")}</span>
      <span class="style-tab-title">${style.style_name_zh}</span>
    `;
    if (style.scene_style_id === activeStyleId) button.classList.add("active");
    button.addEventListener("click", () => {
      activeStyleId = style.scene_style_id;
      renderTabs();
      renderTaiwanStyleGallery();
      taiwanStyleGallery?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    tabRow.appendChild(button);
  });
}

function rememberSelectedStyleCard(group, card) {
  selectedStyleCardId = card.card_id;
  try {
    sessionStorage.setItem(
      STYLE_CARD_STORAGE_KEY,
      JSON.stringify({
        style: group.scene_style_id,
        style_id: group.style_id,
        style_name_zh: group.style_name_zh,
        style_card: card.card_id,
        card_name_zh: card.name_zh,
        palette_hex: card.palette_hex || [],
      })
    );
  } catch (error) {
    // sessionStorage may be unavailable in privacy modes; UI selection still works.
  }
}

function updateSelectedStyleCardUI(cardId = selectedStyleCardId) {
  if (!taiwanStyleGallery) return;
  taiwanStyleGallery.querySelectorAll("[data-style-card-id]").forEach((item) => {
    item.classList.toggle("is-selected", item.dataset.styleCardId === cardId);
  });
  taiwanStyleGallery.querySelectorAll("[data-card-action]").forEach((control) => {
    const isSelected = control.dataset.cardId === cardId;
    control.setAttribute("aria-pressed", isSelected ? "true" : "false");
    const isImageButton =
      control.classList.contains("taiwan-style-feature-image") ||
      control.classList.contains("taiwan-style-card-image-button");
    if (control.dataset.cardAction === "select" && !isImageButton) {
      control.textContent = isSelected ? "已選擇此色調" : "選擇這組色調";
    }
  });
}

function selectTaiwanStyleCard(group, card) {
  rememberSelectedStyleCard(group, card);
  updateSelectedStyleCardUI(card.card_id);
}

function renderPaletteLabelOverlay(card) {
  const labels = STYLE_CARD_PALETTE_LABELS[card.card_id];
  if (!labels?.length) return "";
  return `
    <span class="taiwan-style-palette-label-overlay" aria-hidden="true">
      ${labels.map((label) => `<span>${label}</span>`).join("")}
    </span>
  `;
}

function renderTaiwanStyleGalleryLegacy() {
  if (!taiwanStyleGallery) return;
  taiwanStyleGallery.innerHTML = taiwanStyleCards
    .map((style) => `
      <section id="taiwan-style-${style.style_id}" class="taiwan-style-group" style="--style-card-a:${style.cards[0]?.palette_hex?.[0] || "#f3eadc"}; --style-card-b:${style.cards[0]?.palette_hex?.[1] || "#d1b79a"};">
        <div class="taiwan-style-group-heading">
          <div>
            <span class="style-group-number">${String(taiwanStyleCards.indexOf(style) + 1).padStart(2, "0")}</span>
            <h2>${style.style_name_zh}</h2>
          </div>
          <p>${style.description_zh}</p>
        </div>
        <div class="taiwan-style-card-grid">
          ${style.cards.map((card) => `
            <article class="taiwan-style-card" data-style-card-id="${card.card_id}">
              <button type="button" class="taiwan-style-card-image-button" data-card-action="select" data-card-id="${card.card_id}" aria-label="選擇 ${style.style_name_zh} ${card.name_zh}">
                <img src="${card.image_url}" alt="${style.style_name_zh} ${card.name_zh}" loading="lazy" />
                <span class="taiwan-style-card-overlay">選擇這組色調</span>
              </button>
              <div class="taiwan-style-card-body">
                <div><span class="style-card-kicker">${style.style_name_zh}</span><h3>${card.name_zh}</h3></div>
                <button type="button" class="secondary-action taiwan-style-card-cta" data-card-action="apply" data-card-id="${card.card_id}">帶入 3D 場景 →</button>
              </div>
            </article>
          `).join("")}
        </div>
      </section>
    `)
    .join("");

  taiwanStyleGallery.querySelectorAll("[data-card-action]").forEach((control) => {
    control.addEventListener("click", () => {
      const cardId = control.dataset.cardId;
      const group = taiwanStyleCards.find((style) => style.cards.some((card) => card.card_id === cardId));
      const card = group?.cards.find((item) => item.card_id === cardId);
      if (!group || !card) return;
      if (control.dataset.cardAction === "select") {
        selectTaiwanStyleCard(group, card);
        return;
      }
      selectTaiwanStyleCard(group, card);
      const query = new URLSearchParams({ style: group.scene_style_id, style_card: card.card_id });
      window.location.href = `/scene?${query.toString()}`;
    });
  });
}

function cardToneDescription(style, card) {
  if (STYLE_CARD_COPY[card.card_id]) return STYLE_CARD_COPY[card.card_id];
  const base = (style.description_zh || "").replace(/。$/, "");
  return `「${card.name_zh}」把 ${style.style_name_zh} 的色彩收在日常尺度裡，讓牆面、家具與光線之間更有層次。${base}`;
}

function renderTaiwanStyleGallery() {
  if (!taiwanStyleGallery) return;
  const activeStyle =
    taiwanStyleCards.find((style) => style.scene_style_id === activeStyleId) ||
    taiwanStyleCards[0];
  if (!activeStyle) {
    taiwanStyleGallery.innerHTML = "";
    return;
  }

  const styleIndex = taiwanStyleCards.indexOf(activeStyle);
  taiwanStyleGallery.innerHTML = `
      <section id="taiwan-style-${activeStyle.style_id}" class="taiwan-style-group" style="--style-card-a:${activeStyle.cards[0]?.palette_hex?.[0] || "#f3eadc"}; --style-card-b:${activeStyle.cards[0]?.palette_hex?.[1] || "#d1b79a"};">
        <div class="taiwan-style-group-heading">
          <div>
            <span class="style-group-number">${String(styleIndex + 1).padStart(2, "0")}</span>
            <h2>${activeStyle.style_name_zh}</h2>
          </div>
          <p>${activeStyle.description_zh}</p>
        </div>
        <div class="taiwan-style-card-list">
          ${activeStyle.cards.map((card, cardIndex) => {
            const tones = card.palette_hex || [];
            const isSelectedCard = selectedStyleCardId === card.card_id;
            return `
            <article class="taiwan-style-feature-card ${cardIndex % 2 === 1 ? "is-reversed" : ""} ${isSelectedCard ? "is-selected" : ""}" data-style-card-id="${card.card_id}" style="--card-tone-a:${tones[0] || "#f6eadc"}; --card-tone-b:${tones[1] || "#d8bea0"}; --card-tone-c:${tones[2] || "#8d735c"};">
              <span class="taiwan-style-selected-badge">已選擇</span>
              <button type="button" class="taiwan-style-feature-image" data-card-action="select" data-card-id="${card.card_id}" aria-pressed="${isSelectedCard ? "true" : "false"}" aria-label="選擇 ${activeStyle.style_name_zh} ${card.name_zh}">
                <img src="${card.image_url}" alt="${activeStyle.style_name_zh} ${card.name_zh}" loading="lazy" />
                ${renderPaletteLabelOverlay(card)}
                <span class="taiwan-style-card-overlay">選擇這組色調</span>
              </button>
              <div class="taiwan-style-feature-copy">
                <span class="style-card-kicker">${activeStyle.style_name_zh} / ${String(cardIndex + 1).padStart(2, "0")}</span>
                <h3>${card.name_zh}</h3>
                <p>${cardToneDescription(activeStyle, card)}</p>
                <div class="taiwan-style-card-actions">
                  <button type="button" class="secondary-action" data-card-action="select" data-card-id="${card.card_id}" aria-pressed="${isSelectedCard ? "true" : "false"}">${isSelectedCard ? "已選擇此色調" : "選擇這組色調"}</button>
                  <button type="button" class="secondary-action taiwan-style-card-cta" data-card-action="apply" data-card-id="${card.card_id}">帶入 3D 場景 →</button>
                </div>
              </div>
            </article>
          `;
          }).join("")}
        </div>
      </section>
    `;

  taiwanStyleGallery.querySelectorAll("[data-card-action]").forEach((control) => {
    control.addEventListener("click", () => {
      const cardId = control.dataset.cardId;
      const group = taiwanStyleCards.find((style) => style.cards.some((card) => card.card_id === cardId));
      const card = group?.cards.find((item) => item.card_id === cardId);
      if (!group || !card) return;
      if (control.dataset.cardAction === "select") {
        selectTaiwanStyleCard(group, card);
        return;
      }
      selectTaiwanStyleCard(group, card);
      const query = new URLSearchParams({ style: group.scene_style_id, style_card: card.card_id });
      window.location.href = `/scene?${query.toString()}`;
    });
  });
}

function renderAnnotations(styleId) {
  const labels = STYLE_ANNOTATION_OVERRIDES[styleId] || STYLE_ANNOTATIONS_ROOM_FOCUS[styleId] || STYLE_ANNOTATIONS_ROOM_FOCUS.eclectic;
  return labels
    .map(
      ([text, x, y]) => {
        const safeX = Math.min(86, Math.max(31, Number(x) || 50));
        const safeY = Math.min(86, Math.max(18, Number(y) || 50));
        return `
        <div class="style-annotation ${safeX > 62 ? "reverse" : ""}" style="left:${safeX}%; top:${safeY}%;">
          <span class="style-annotation-dot"></span>
          <span class="style-annotation-line"></span>
          <span class="style-annotation-label">${text}</span>
        </div>
      `;
      }
    )
    .join("");
}

function renderStyleStage(style) {
  const colors = style.palette_hex?.length ? style.palette_hex : ["#f6f1e8", "#d8c8b0", "#a88a67"];
  const imageBase = STYLE_IMAGE_MAP[style.style_id] ?? STYLE_IMAGE_MAP.eclectic;
  const count = countFurnitureForStyle(style.style_id);
  return `
    <div class="style-stage" style="--tone-a:${colors[0]}; --tone-b:${colors[1] ?? colors[0]}; --tone-c:${colors[2] ?? colors[1] ?? colors[0]};">
      <img class="style-stage-image" src="${imageBase}?v=${STYLE_IMAGE_VERSION}" alt="${style.style_name_zh} 風格示意圖" />
      <div class="style-stage-overlay"></div>
      <div class="style-stage-header">
        <span class="style-stage-label">STYLE VISUAL</span>
        <div class="badge-row">
          <span class="badge">${style.style_name_zh}</span>
          <span class="badge">${style.style_name_en ?? ""}</span>
          <span class="badge">${count} 件家具</span>
        </div>
      </div>
      <div class="style-stage-title"><strong>${style.style_name_zh}</strong></div>
      <div class="style-stage-annotation-layer">${renderAnnotations(style.style_id)}</div>
    </div>
  `;
}

function surfaceLabel(surface) {
  return SURFACE_DISPLAY[surface?.surface_id]?.[0] || surface?.name_zh || surface?.surface_id || "資料庫材質";
}

function surfaceGroup(surface) {
  return SURFACE_DISPLAY[surface?.surface_id]?.[1] || surface?.material_group || "材質";
}

function surfaceColor(surface) {
  return SURFACE_DISPLAY[surface?.surface_id]?.[2] || surface?.color_zh || "色彩未標註";
}

function floorDbMatches(style) {
  return styleSurfaces(style, "floor").filter((surface) => surface?.usage?.includes("floor"));
}

function allFloorSurfaces() {
  return (surfaceCatalog.surfaces || []).filter((surface) => surface?.usage?.includes("floor"));
}

function wallDbMatches(style) {
  return styleSurfaces(style, "wall").filter((surface) => surface?.usage?.includes("wall"));
}

function allWallSurfaces() {
  return (surfaceCatalog.surfaces || []).filter((surface) => surface?.usage?.includes("wall"));
}

function wallSurfacePool(style) {
  const recommended = wallDbMatches(style);
  const recommendedIds = new Set(recommended.map((surface) => surface.surface_id));
  const remaining = allWallSurfaces().filter((surface) => !recommendedIds.has(surface.surface_id));
  return [...recommended, ...remaining];
}

function floorSurfacePool(style) {
  const recommended = floorDbMatches(style);
  const recommendedIds = new Set(recommended.map((surface) => surface.surface_id));
  const remaining = allFloorSurfaces().filter((surface) => !recommendedIds.has(surface.surface_id));
  return [...recommended, ...remaining];
}

function floorReason(style, surface) {
  const isExplicitMatch = surface?.suitable_styles?.includes(style.style_id);
  const source = isExplicitMatch
    ? `資料庫 suitable_styles 明確包含「${style.style_name_zh}」`
    : `列在「${style.style_name_zh}」地板推薦 pool，建議後續補 suitable_styles 標註`;
  return `${source}。作為地板時，能支撐此風格的色彩、明度與材質語彙。`;
}

function renderGeneratedWallRecommendations(style) {
  const walls = GENERATED_WALL_OPTIONS[style.style_id] || GENERATED_WALL_OPTIONS.scandinavian;
  return `
    <div class="surface-carousel" data-surface-carousel="wall">
      <button type="button" class="surface-carousel-auto-toggle" data-carousel-auto-toggle aria-pressed="false">自動播放</button>
      <button type="button" class="surface-carousel-button prev" data-carousel-step="-1" aria-label="\u4e0a\u4e00\u500b\u7246\u9762\u6750\u8cea">&lsaquo;</button>
      <div class="surface-recommendation-list generated-wall-list wall-material-row surface-carousel-track">
        ${walls
          .map(
            ([name, color, reason]) => `
              <article class="surface-recommendation-item generated-wall-card">
                <span class="generated-wall-swatch" style="--generated-wall:${color};"></span>
                <div>
                  <div class="surface-recommendation-head">
                    <strong>${name}</strong>
                    <span>?????? / ???????</span>
                  </div>
                  <p>${reason}</p>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <button type="button" class="surface-carousel-button next" data-carousel-step="1" aria-label="\u4e0b\u4e00\u500b\u7246\u9762\u6750\u8cea">&rsaquo;</button>
    </div>
  `;
}

function renderFloorRecommendations(style) {
  const recommended = floorDbMatches(style);
  const recommendedIds = new Set(recommended.map((surface) => surface.surface_id));
  const surfaces = floorSurfacePool(style);
  if (!surfaces.length) return "<p>????????????????????</p>";
  return `
    <p class="surface-section-note">?? catalog ? ${allFloorSurfaces().length} ???????????? ${recommended.length} ???????????????? pool??????????????</p>
    <div class="surface-carousel" data-surface-carousel="floor">
      <button type="button" class="surface-carousel-auto-toggle" data-carousel-auto-toggle aria-pressed="false">自動播放</button>
      <button type="button" class="surface-carousel-button prev" data-carousel-step="-1" aria-label="\u4e0a\u4e00\u500b\u5730\u677f\u6750\u8cea">&lsaquo;</button>
      <div class="surface-recommendation-list floor-material-row surface-carousel-track">
        ${surfaces
          .map(
            (surface) => `
              <article class="surface-recommendation-item has-preview floor-db-card ${recommendedIds.has(surface.surface_id) ? "is-recommended" : "is-pool"}">
                <span class="surface-recommendation-preview" style="background-image:url('${surface.preview_url}');"></span>
                <div>
                  <div class="surface-recommendation-head">
                    <strong>${surfaceLabel(surface)}</strong>
                    <span>${surfaceGroup(surface)} / ${surfaceColor(surface)}</span>
                  </div>
                  <p>${floorReason(style, surface)}</p>
                  ${recommendedIds.has(surface.surface_id) ? `<small class="surface-db-proof">??????</small>` : `<small class="surface-db-proof muted">?????</small>`}
                  <small class="surface-db-proof">??? ID?${surface.surface_id}</small>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <button type="button" class="surface-carousel-button next" data-carousel-step="1" aria-label="\u4e0b\u4e00\u500b\u5730\u677f\u6750\u8cea">&rsaquo;</button>
    </div>
  `;
}

function renderSurfaceRecommendations(style, usage) {
  const surfaces = styleSurfaces(style, usage).slice(0, 3);
  if (!surfaces.length) return "<p>尚未整理材質推薦。</p>";
  return `
    <div class="surface-recommendation-list">
      ${surfaces
        .map(
          (surface) => `
            <article class="surface-recommendation-item has-preview">
              <span class="surface-recommendation-preview" style="background-image:url('${surface.preview_url}');"></span>
              <div>
                <div class="surface-recommendation-head">
                  <strong>${surface.name_zh}</strong>
                  <span>${surface.material_group} / ${surface.color_zh}</span>
                </div>
                <p>${surfaceReason(style, surface, usage)}</p>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderPairRecommendations(style) {
  const profile = style.surface_profile || surfaceCatalog.style_surface_profiles?.[style.style_id] || {};
  const pairs = profile.surface_pairings || [];
  const floor = defaultSurface(style, "floor");
  const generatedWall = (GENERATED_WALLS[style.style_id] || GENERATED_WALLS.scandinavian)[0];
  const wallPreview = `linear-gradient(135deg, ${generatedWall[1]}, color-mix(in srgb, ${generatedWall[1]} 72%, white))`;
  const floorPreview = floor?.preview_url ? `url('${floor.preview_url}')` : "linear-gradient(135deg,#d8b783,#a88462)";
  return `
    <div class="surface-mini-room">
      <div>
        <div class="style-chip-row">
          ${
            pairs.length
              ? pairs.map((pair) => `<span class="style-chip">生成牆面 + ${surfaceLabel(surfaceById.get(pair.floor))}</span>`).join("")
              : `<span class="style-chip">${generatedWall[0]} + ${surfaceLabel(floor)}</span>`
          }
        </div>
        <p>右側簡易 3D 以「程式生成牆面」與「資料庫地板材質」組合示意，牆面不與地板材質混用。</p>
      </div>
      <div class="surface-mini-room-stage" style="--wall-preview:${wallPreview}; --floor-preview:${floorPreview};"></div>
    </div>
  `;
}

function renderSurfacePool(style, usage) {
  const surfaces = usage === "floor" ? floorSurfacePool(style) : styleSurfaces(style, usage);
  if (!surfaces.length) return `<p>尚未整理 ${usage === "wall" ? "牆面" : "地板"} 材質 pool。</p>`;
  const recommendedIds = new Set(styleSurfaces(style, usage).map((surface) => surface.surface_id));
  return `
    <div class="surface-pool-grid">
      ${surfaces
        .map(
          (surface) => `
            <article class="surface-pool-card">
              <span class="surface-pool-swatch" style="background-image:url('${surface.preview_url}');"></span>
              <strong>${surfaceLabel(surface)}</strong>
              <small>${surfaceGroup(surface)} / ${surfaceColor(surface)}</small>
              ${recommendedIds.has(surface.surface_id) ? `<em>符合此風格</em>` : `<em class="muted">可作備選</em>`}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function initSurfaceCarousels() {
  surfaceCarouselTimers.forEach((timerId) => window.clearInterval(timerId));
  surfaceCarouselTimers = [];
  detailPanel.querySelectorAll("[data-surface-carousel]").forEach((carousel) => {
    const track = carousel.querySelector(".surface-carousel-track");
    if (!track) return;

    let paused = false;
    const cardWidth = () => {
      const firstCard = track.querySelector(".surface-recommendation-item");
      return firstCard ? firstCard.getBoundingClientRect().width + 16 : Math.max(260, track.clientWidth * 0.72);
    };
    const showAutoFade = () => {
      carousel.classList.add("is-auto-scrolling");
      window.setTimeout(() => {
        carousel.classList.remove("is-auto-scrolling");
      }, 900);
    };
    const step = (direction = 1, isAuto = false) => {
      if (!track.scrollWidth || track.scrollWidth <= track.clientWidth + 8) return;
      if (isAuto) showAutoFade();
      const nearEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 12;
      const nearStart = track.scrollLeft <= 12;
      if (direction > 0 && nearEnd) {
        track.scrollTo({ left: 0, behavior: "smooth" });
        return;
      }
      if (direction < 0 && nearStart) {
        track.scrollTo({ left: track.scrollWidth, behavior: "smooth" });
        return;
      }
      track.scrollBy({ left: cardWidth() * direction, behavior: "smooth" });
    };

    carousel.querySelectorAll("[data-carousel-step]").forEach((button) => {
      button.addEventListener("click", () => step(Number(button.dataset.carouselStep) || 1));
    });
    carousel.addEventListener("mouseenter", () => { paused = true; });
    carousel.addEventListener("mouseleave", () => { paused = false; });
    carousel.addEventListener("focusin", () => { paused = true; });
    carousel.addEventListener("focusout", () => { paused = false; });

    let timerId = null;
    const toggleButton = carousel.querySelector("[data-carousel-auto-toggle]");
    const stopAuto = () => {
      if (timerId) {
        window.clearInterval(timerId);
        timerId = null;
      }
      carousel.classList.remove("is-auto-enabled");
      if (toggleButton) {
        toggleButton.textContent = "\u81ea\u52d5\u64ad\u653e";
        toggleButton.setAttribute("aria-pressed", "false");
      }
    };
    const startAuto = () => {
      stopAuto();
      carousel.classList.add("is-auto-enabled");
      if (toggleButton) {
        toggleButton.textContent = "\u505c\u6b62\u52d5\u756b";
        toggleButton.setAttribute("aria-pressed", "true");
      }
      timerId = window.setInterval(() => {
        if (!paused) step(1, true);
      }, SURFACE_CAROUSEL_INTERVAL_MS);
      surfaceCarouselTimers.push(timerId);
    };
    toggleButton?.addEventListener("click", () => {
      if (timerId) {
        stopAuto();
      } else {
        startAuto();
      }
    });
  });
}

function renderGeneratedWallCarousel(style) {
  const walls = GENERATED_WALL_OPTIONS[style.style_id] || GENERATED_WALL_OPTIONS.scandinavian || [];
  return `
    <div class="surface-carousel" data-surface-carousel="wall">
      <button type="button" class="surface-carousel-auto-toggle" data-carousel-auto-toggle aria-pressed="false">&#33258;&#21205;&#25773;&#25918;</button>
      <button type="button" class="surface-carousel-button prev" data-carousel-step="-1" aria-label="上一個牆面顏色">&lsaquo;</button>
      <div class="surface-recommendation-list wall-material-row surface-carousel-track">
        ${walls
          .map(
            ([name, color, reason]) => `
              <article class="surface-recommendation-item generated-wall-card">
                <span class="generated-wall-swatch" style="--generated-wall:${color};"></span>
                <div class="surface-card-copy">
                  <div class="surface-recommendation-head">
                    <strong>${name}</strong>
                    <span>程式生成牆面</span>
                  </div>
                  <p>${reason}</p>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <button type="button" class="surface-carousel-button next" data-carousel-step="1" aria-label="下一個牆面顏色">&rsaquo;</button>
    </div>
  `;
}

function wallReasonSummary(style, surface, recommendedIds) {
  if (recommendedIds.has(surface.surface_id)) {
    return `符合「${style.style_name_zh}」牆面 pool：${surface.style_notes_zh || "色調、材質與風格語彙符合目前風格。"}`;
  }
  return "資料庫備選牆材：可手動改用，但不是目前風格的優先推薦。";
}

function renderWallCarousel(style) {
  const recommended = wallDbMatches(style);
  const recommendedIds = new Set(recommended.map((surface) => surface.surface_id));
  const surfaces = wallSurfacePool(style);
  if (!surfaces.length) return renderGeneratedWallCarousel(style);
  return `
    <p class="surface-section-note">目前共有 ${allWallSurfaces().length} 張牆面材質，此風格推薦 ${recommended.length} 張；牆面資料庫只篩選 wall 材質，不會混入地板。</p>
    <div class="surface-carousel" data-surface-carousel="wall">
      <button type="button" class="surface-carousel-auto-toggle" data-carousel-auto-toggle aria-pressed="false">&#33258;&#21205;&#25773;&#25918;</button>
      <button type="button" class="surface-carousel-button prev" data-carousel-step="-1" aria-label="上一個牆面材質">&lsaquo;</button>
      <div class="surface-recommendation-list wall-material-row surface-carousel-track">
        ${surfaces
          .map(
            (surface) => `
              <article class="surface-recommendation-item has-preview wall-db-card ${recommendedIds.has(surface.surface_id) ? "is-recommended" : "is-pool"}">
                <span class="surface-recommendation-preview" style="background-image:url('${surface.preview_url}');"></span>
                <div class="surface-card-copy">
                  <div class="surface-recommendation-head">
                    <strong>${surfaceLabel(surface)}</strong>
                    <span>${surfaceGroup(surface)} / ${surfaceColor(surface)}</span>
                  </div>
                  <p>${wallReasonSummary(style, surface, recommendedIds)}</p>
                  ${recommendedIds.has(surface.surface_id) ? `<small class="surface-db-proof">符合目前風格</small>` : `<small class="surface-db-proof muted">可作備選</small>`}
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <button type="button" class="surface-carousel-button next" data-carousel-step="1" aria-label="下一個牆面材質">&rsaquo;</button>
    </div>
  `;
}

function floorReasonSummary(style, surface, recommendedIds) {
  if (recommendedIds.has(surface.surface_id)) {
    return `適合「${style.style_name_zh}」：色調、明度與材質語彙符合目前風格。`;
  }
  return `可作備選：同屬地板資料庫，可依使用者偏好再挑選。`;
}

function renderFloorCarousel(style) {
  const recommended = floorDbMatches(style);
  const recommendedIds = new Set(recommended.map((surface) => surface.surface_id));
  const surfaces = floorSurfacePool(style);
  if (!surfaces.length) return "<p>目前沒有可用的地板材質。</p>";
  return `
    <p class="surface-section-note">目前共有 ${allFloorSurfaces().length} 張地板材質，此風格推薦 ${recommended.length} 張；先顯示推薦，再接完整資料庫。</p>
    <div class="surface-carousel" data-surface-carousel="floor">
      <button type="button" class="surface-carousel-auto-toggle" data-carousel-auto-toggle aria-pressed="false">&#33258;&#21205;&#25773;&#25918;</button>
      <button type="button" class="surface-carousel-button prev" data-carousel-step="-1" aria-label="上一個地板材質">&lsaquo;</button>
      <div class="surface-recommendation-list floor-material-row surface-carousel-track">
        ${surfaces
          .map(
            (surface) => `
              <article class="surface-recommendation-item has-preview floor-db-card ${recommendedIds.has(surface.surface_id) ? "is-recommended" : "is-pool"}">
                <span class="surface-recommendation-preview" style="background-image:url('${surface.preview_url}');"></span>
                <div class="surface-card-copy">
                  <div class="surface-recommendation-head">
                    <strong>${surfaceLabel(surface)}</strong>
                    <span>${surfaceGroup(surface)} / ${surfaceColor(surface)}</span>
                  </div>
                  <p>${floorReasonSummary(style, surface, recommendedIds)}</p>
                  <small class="surface-db-proof ${recommendedIds.has(surface.surface_id) ? "" : "muted"}">
                    ${recommendedIds.has(surface.surface_id) ? "適合目前風格" : "可作備選"}
                  </small>
                </div>
              </article>
            `
          )
          .join("")}
      </div>
      <button type="button" class="surface-carousel-button next" data-carousel-step="1" aria-label="下一個地板材質">&rsaquo;</button>
    </div>
  `;
}
function renderActiveStyle() {
  const style = data.styles.find((item) => item.style_id === activeStyleId);
  if (!style) return;

  const theme = style.visual_theme ?? {};
  const accentFill = theme.accent_fill ?? "#ead8c5";
  const panelFill = theme.panel_fill ?? "#fffaf4";
  const panelOutline = theme.panel_outline ?? "#d8c7b5";
  const titleColor = theme.title_color ?? "#2d2926";
  const bodyColor = theme.body_color ?? "#564e47";
  const shellToneA = style.palette_hex?.[0] ?? "#f8f2e8";
  const shellToneB = style.palette_hex?.[1] ?? "#e2d3c0";
  const shellToneC = style.palette_hex?.[2] ?? "#b69474";
  document.documentElement.style.setProperty("--style-shell-a", shellToneA);
  document.documentElement.style.setProperty("--style-shell-b", shellToneB);
  document.documentElement.style.setProperty("--style-shell-c", shellToneC);

  const cardStyle = `--panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor}; --accent-fill:${accentFill};`;
  detailPanel.innerHTML = `
    <div class="style-hero-card style-enter" style="${cardStyle}">
      ${renderStyleStage(style)}
    </div>

    <div class="style-section-grid">
      <article class="style-info-card style-enter" style="--delay:40ms; ${cardStyle}">
        <h3>關鍵字</h3>
        <p>${safeList(style.keywords_zh)}</p>
      </article>
      <article class="style-info-card style-enter" style="--delay:80ms; ${cardStyle}">
        <h3>主色</h3>
        <div class="swatch-row">
          ${(style.main_colors_zh ?? [])
            .filter(readable)
            .map(
              (name, index) => `
                <span class="color-pill">
                  <span class="color-dot" style="background:${style.palette_hex?.[index] ?? "#d9d9d9"}"></span>
                  ${name}
                </span>
              `
            )
            .join("")}
        </div>
      </article>
      <article class="style-info-card style-enter" style="--delay:120ms; ${cardStyle}">
        <h3>材質</h3>
        <p>${safeList(style.materials_zh)}</p>
      </article>
      <article class="style-info-card style-enter" style="--delay:160ms; ${cardStyle}">
        <h3>造型特徵</h3>
        <p>${safeList(style.shape_features_zh)}</p>
      </article>
      <article class="style-info-card style-enter" style="--delay:200ms; ${cardStyle}">
        <h3>避免元素</h3>
        <p>${safeList(style.avoid_elements_zh)}</p>
      </article>
      <article class="style-info-card style-enter" style="--delay:240ms; ${cardStyle}">
        <h3>空間背景與用材</h3>
        <p>牆面：由程式依風格生成，不混用地板或家具材質。</p>
        <p>地板：${surfaceLabel(defaultSurface(style, "floor"))}</p>
        <p>整體：${readable(style.scene_background?.overall_zh) ? style.scene_background.overall_zh : "依風格維持色彩、家具與地板的整體一致性。"}</p>
      </article>
      <article class="style-info-card style-enter" style="--delay:280ms; ${cardStyle}">
        <h3>牆面生成方案</h3>
        ${renderWallCarousel(style)}
      </article>
      <article class="style-info-card style-enter" style="--delay:320ms; ${cardStyle}">
        <h3>地板資料庫推薦</h3>
        ${renderFloorCarousel(style)}
      </article>
      <article class="style-info-card wide style-enter legacy-floor-pool-card" style="--delay:380ms; ${cardStyle}">
        <h3>地板真材質 pool</h3>
        <p>以下只列資料庫中的地板材質，且優先取目前風格推薦 pool。</p>
        <h4>地板</h4>
        
      </article>
      <article class="style-info-card wide style-enter" style="--delay:400ms; ${cardStyle}">
        <h3>資料庫對應</h3>
        ${renderStyleTagSummary(style)}
      </article>
    </div>
  `;
  initSurfaceCarousels();
}

renderTabs();
renderTaiwanStyleGallery();
initBackgroundFx();
