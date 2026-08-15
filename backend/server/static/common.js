export async function fetchSiteData() {
  const response = await fetch("/api/site-data");
  return response.json();
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${url}`);
  }
  return response.json();
}

export async function fetchHomeData() {
  return fetchJson("/api/home-data");
}

export async function fetchStylesData() {
  try {
    return await fetchJson("/api/styles");
  } catch (error) {
    if (String(error?.message || "").startsWith("HTTP 404")) {
      console.warn("找不到 /api/styles，暫時退回 /api/site-data。請重啟後端以使用快速拆分 API。");
      return fetchSiteData();
    }
    throw error;
  }
}

export async function fetchSceneBootstrap() {
  return fetchJson("/api/scene/bootstrap");
}

export async function fetchFurniturePage(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson(`/api/furniture${suffix}`);
}

export function formatList(items = []) {
  return items.filter(Boolean).join(" / ");
}

function formatSizeBase(size) {
  if (!size) return "尺寸未填";

  const values = [size.width ?? size.w, size.depth ?? size.d, size.height ?? size.h]
    .map((value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
    })
    .filter((value) => value !== null);

  if (!values.length) return "尺寸未填";
  return `${values.join(" x ")} cm`;
}

const THIN_MIRROR_TYPES = new Set(["mirror", "large-mirror", "standing-mirror", "wall-mirror"]);
const NAME_DIMENSIONS = /(\d{2,3}(?:\.\d)?)\s*(?:cm|公分)?\s*[xX×＊*]\s*(\d{2,3}(?:\.\d)?)(?:\s*(?:cm|公分)?)?(?:\s*[xX×＊*]\s*(\d{1,3}(?:\.\d)?)(?:\s*(?:cm|公分)?)?)?/;

function extractNameDimensions(item) {
  const text = [item?.name_zh_raw, item?.name_zh, item?.name_en, item?.title].filter(Boolean).join(" ");
  const match = text.match(NAME_DIMENSIONS);
  if (!match) return [];
  return match.slice(1).filter(Boolean).map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0);
}

export function formatSize(size, item = null) {
  const itemType = item?.normalized_type || item?.type || "";
  if (!THIN_MIRROR_TYPES.has(itemType) || !size) {
    return formatSizeBase(size);
  }

  const nameDims = extractNameDimensions(item);
  if (nameDims.length >= 2) {
    const width = nameDims[0];
    const height = nameDims.length >= 3 ? nameDims[2] : nameDims[1];
    const namedThickness = nameDims.length >= 3 ? nameDims[1] : null;
    const rawThickness = Number(size.depth ?? size.d);
    const thickness = namedThickness && namedThickness <= 12 ? namedThickness : rawThickness > 0 && rawThickness <= 12 ? rawThickness : 3;
    return `${[width, height, thickness].join(" x ")} cm`;
  }

  const width = Number(size.width ?? size.w);
  const height = Number(size.height ?? size.h);
  const rawThickness = Number(size.depth ?? size.d);
  const thickness = rawThickness > 0 && rawThickness <= 12 ? rawThickness : 3;
  const values = [width, height, thickness]
    .filter((value) => Number.isFinite(value) && value > 0);

  return values.length ? `${values.join(" x ")} cm` : formatSizeBase(size);
}

export const TYPE_LABELS = {
  armchair: "扶手椅",
  "bar-table": "吧台桌",
  bed: "床",
  "bed-frame": "床架",
  "bedside-table": "床頭櫃",
  bookcase: "書櫃",
  "cabinet-cupboard": "櫃體",
  "cabinets-cupboard": "櫃體",
  "chests-of-drawer": "抽屜櫃",
  "childrens-furniture": "兒童家具",
  "childrens-rugs-curtain": "兒童地毯與窗簾",
  "childrens-stools-benche": "兒童椅凳",
  "childrens-table": "兒童桌",
  "clothes-rack": "衣架",
  "coffee-table": "茶几",
  decoration: "裝飾配件",
  desk: "書桌",
  "dining-chair": "餐椅",
  "dining-table": "餐桌",
  "display-cabinet": "展示櫃",
  "door-mat": "門墊",
  "fabric-sofa": "布沙發",
  "floor-lamp": "落地燈",
  "flower-pots-planter": "盆栽植器",
  "gaming-chair": "電競椅",
  "handmade-rug": "手工地毯",
  "kids-chairs-stool": "兒童椅凳",
  lamp: "燈具",
  "lamp-shades-base": "燈罩與燈座",
  "large-medium-rug": "中大型地毯",
  "large-mirror": "大型鏡子",
  "leather-sofa": "皮沙發",
  mattress: "床墊",
  mirror: "鏡子",
  "mirror-cabinet": "鏡櫃",
  "modular-sofa": "模組沙發",
  "office-chair": "辦公椅",
  "outdoor-coffee-side-table": "戶外茶几邊桌",
  "outdoor-dining": "戶外餐桌椅",
  "outdoor-furniture": "戶外家具",
  "outdoor-rug": "戶外地毯",
  "outdoor-seating": "戶外座椅",
  "pax-wardrobe": "衣櫃",
  "pillow-cushion": "抱枕靠墊",
  planter: "盆栽植器",
  "room-divider": "空間隔屏",
  "round-rug": "圓形地毯",
  rug: "地毯",
  "runner-small-rug": "走道地毯",
  "sheepskins-cowhide": "羊皮與牛皮毯",
  "shelving-unit": "層架",
  "side-table": "邊桌",
  sideboard: "邊櫃",
  sofa: "沙發",
  "sofa-bed": "沙發床",
  "standing-mirror": "立鏡",
  "stool-bench": "凳子／長凳",
  "storage-boxes-basket": "收納盒籃",
  "storage-furniture": "收納家具",
  "storage-solution-system": "收納系統",
  "sun-loungers-hammock": "躺椅與吊床",
  table: "桌子",
  "table-lamp": "檯燈",
  trolley: "推車",
  "tv-bench": "電視櫃",
  "tv-media-furniture": "電視與影音家具",
  vase: "花器",
  "wall-art": "牆面裝飾",
  "wall-mirror": "壁鏡",
  "wall-shelf": "壁架",
  wardrobe: "衣櫃",
  "work-lamp": "工作燈",
  "fridge-freezer": "冰箱／冷凍櫃",
  dishwasher: "洗碗機",
  "extractor-hood": "抽油煙機",
  oven: "烤箱",
  microwave: "微波爐",
  "small-kitchen-appliance": "小型廚房電器",
  toaster: "烤麵包機",
  "electric-fan": "電風扇",
  "air-conditioner": "冷氣",
  "air-purifier": "空氣清淨機",
  "robot-vacuum": "掃地機器人",
  "vacuum-cleaner": "吸塵器",
  "washing-machine": "洗衣機",
  iron: "熨斗",
  "hair-dryer": "吹風機",
};

export function formatTypeLabel(typeName) {
  return TYPE_LABELS[typeName] || typeName || "未分類";
}

const NAME_TOKEN_ZH = [
  ["Amazon Brand", "亞馬遜品牌"],
  ["Marque Amazon", "亞馬遜品牌"],
  ["Rivet", "Rivet 系列"],
  ["IKEA", "IKEA"],
  ["tufted", "絎縫"],
  ["velvet", "絨布"],
  ["fabric", "布質"],
  ["leather", "皮革"],
  ["loveseat", "雙人沙發"],
  ["sofa", "沙發"],
  ["sectional", "L 型沙發"],
  ["daybed", "沙發床"],
  ["armchair", "扶手椅"],
  ["chair", "椅"],
  ["bench", "長凳"],
  ["stool", "凳"],
  ["coffee table", "茶几"],
  ["table", "桌"],
  ["desk", "書桌"],
  ["bookcase", "書櫃"],
  ["shelf", "層架"],
  ["cabinet", "櫃體"],
  ["wardrobe", "衣櫃"],
  ["bed frame", "床架"],
  ["bed", "床"],
  ["rug", "地毯"],
  ["lamp", "燈具"],
  ["mirror", "鏡子"],
  ["modern", "現代"],
  ["mid-century", "中世紀現代"],
  ["contemporary", "當代"],
  ["classic", "經典"],
  ["scandinavian", "北歐"],
  ["industrial", "工業風"],
  ["country", "鄉村"],
  ["tapered", "錐形"],
  ["wood legs", "木腳"],
  ["metal legs", "金屬腳"],
  ["white", "白色"],
  ["black", "黑色"],
  ["grey", "灰色"],
  ["gray", "灰色"],
  ["light grey", "淺灰色"],
  ["charcoal", "炭灰色"],
  ["brown", "棕色"],
  ["beige", "米色"],
  ["denim", "丹寧色"],
  ["oak", "橡木"],
  ["walnut", "胡桃木"],
];

export function formatFurnitureName(item) {
  const raw = String(item?.name_zh_raw || item?.name_en || "").trim();
  const type = formatTypeLabel(item?.normalized_type);
  if (!raw) return type || "未命名家具";
  if (/[\u4e00-\u9fff]/.test(raw)) return raw;

  let translated = raw
    .replace(/B0[A-Z0-9]+/g, "")
    .replace(/\b\d+[- ]?[WHD]\b/gi, "")
    .replace(/\b\d+\s*x\s*\d+(?:\s*x\s*\d+)?\s*cm\b/gi, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/[_,]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  NAME_TOKEN_ZH.forEach(([token, label]) => {
    translated = translated.replace(new RegExp(token, "gi"), label);
  });

  translated = translated
    .replace(/\s*-\s*/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!translated || translated === raw) {
    const color = item?.color ? `，${item.color}` : "";
    return `${type}${color}`;
  }

  return translated.length > 48 ? `${translated.slice(0, 48)}...` : translated;
}

export function isLightFurniture(item) {
  const tokens = [item?.color, item?.name_en, item?.name_zh_raw, item?.material]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const stableLightKeywords = [
    "white",
    "ivory",
    "cream",
    "beige",
    "light",
    "natural",
    "oak",
    "birch",
    "maple",
    "\u767d",
    "\u7c73",
    "\u6dfa",
    "\u539f\u6728",
    "\u6dfa\u6728",
  ];
  if (stableLightKeywords.some((keyword) => tokens.includes(keyword))) return true;
  return ["white", "ivory", "cream", "beige", "light", "natural", "oak", "birch", "白", "米", "淺"].some((keyword) =>
    tokens.includes(keyword)
  );
}

export function isDarkFurniture(item) {
  const tokens = [item?.color, item?.name_en, item?.name_zh_raw, item?.material, item?.normalized_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const darkKeywords = ["black", "dark", "anthracite", "charcoal", "brown", "espresso", "walnut", "黑", "深", "炭", "胡桃"];

  return darkKeywords.some((keyword) => tokens.includes(keyword));
}

export function shouldUseDarkFurnitureStage(item) {
  const tokens = [item?.color, item?.name_en, item?.name_zh_raw, item?.material, item?.normalized_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  const applianceTypes = new Set([
    "small-kitchen-appliance",
    "fridge-freezer",
    "dishwasher",
    "extractor-hood",
    "oven",
    "microwave",
    "toaster",
    "air-conditioner",
    "air-purifier",
    "robot-vacuum",
    "vacuum-cleaner",
    "washing-machine",
    "iron",
    "hair-dryer",
  ]);
  const isDark = isDarkFurniture(item);
  if (applianceTypes.has(item?.normalized_type) && !isDark) return true;
  if (isLightFurniture(item) && !isDark) return true;
  const lightKeywords = [
    "white",
    "ivory",
    "cream",
    "beige",
    "light",
    "natural",
    "oak",
    "birch",
    "fridge",
    "freezer",
    "refrigerator",
    "白",
    "米",
    "淺",
    "冰箱",
    "冷凍",
    "冷藏",
  ];

  return lightKeywords.some((keyword) => tokens.includes(keyword)) && !isDarkFurniture(item);
}

export function styleNameMap(styles) {
  return new Map(styles.map((style) => [style.style_id, style.style_name_zh]));
}

export function scrollPageTop(target = null, offset = 24) {
  const anchor =
    target instanceof Element
      ? target
      : document.querySelector("main") || document.querySelector(".page-shell") || document.body;
  const top = Math.max(0, window.scrollY + anchor.getBoundingClientRect().top - offset);

  window.scrollTo({ top, behavior: "smooth" });
  if (document.scrollingElement) document.scrollingElement.scrollTop = top;
  if (document.documentElement) document.documentElement.scrollTop = top;
  if (document.body) document.body.scrollTop = top;
}

export function initBackgroundFx() {
  const canvas = document.getElementById("fx-canvas");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.4 };
  let particles = [];
  let blueprintLines = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    particles = Array.from({ length: Math.min(56, Math.floor(window.innerWidth / 28)) }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.8 + 0.6,
      speedX: (Math.random() - 0.5) * 0.16,
      speedY: (Math.random() - 0.5) * 0.16,
      glow: Math.random() * 0.35 + 0.12,
    }));

    blueprintLines = Array.from({ length: 12 }, (_, index) => ({
      x: (index / 12) * canvas.width,
      y: ((index % 4) / 4) * canvas.height * 0.72 + 80,
      w: 120 + (index % 3) * 90,
      h: 70 + (index % 4) * 42,
    }));
  }

  function drawGlowParticles() {
    particles.forEach((particle) => {
      particle.x += particle.speedX + (pointer.x - canvas.width / 2) * 0.000015;
      particle.y += particle.speedY + (pointer.y - canvas.height / 2) * 0.000015;

      if (particle.x < 0) particle.x = canvas.width;
      if (particle.x > canvas.width) particle.x = 0;
      if (particle.y < 0) particle.y = canvas.height;
      if (particle.y > canvas.height) particle.y = 0;

      const gradient = context.createRadialGradient(
        particle.x,
        particle.y,
        0,
        particle.x,
        particle.y,
        particle.radius * 10
      );
      gradient.addColorStop(0, `rgba(255,255,255,${particle.glow})`);
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(particle.x, particle.y, particle.radius * 10, 0, Math.PI * 2);
      context.fill();
    });
  }

  function drawBlueprintLines() {
    if (document.body.dataset.page !== "home") return;
  }

  function animate() {
    context.clearRect(0, 0, canvas.width, canvas.height);
    drawBlueprintLines();
    drawGlowParticles();
    requestAnimationFrame(animate);
  }

  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  });

  resize();
  animate();
}
