import { fetchSiteData, formatTypeLabel, initBackgroundFx } from "./common.js?v=20260707a";

const data = await fetchSiteData();
const tabRow = document.getElementById("style-tab-row");
const detailPanel = document.getElementById("style-detail-panel");
const STYLE_IMAGE_VERSION = "20260706i";

const STYLE_IMAGE_MAP = {
  scandinavian: "/static/style_images/scandinavian.png",
  modern: "/static/style_images/modern.png",
  minimalist_muji: "/static/style_images/minimalist_muji_variant.png",
  nordic_modern: "/static/style_images/nordic_modern.png",
  industrial: "/static/style_images/industrial.png",
  wabi_sabi: "/static/style_images/wabi_sabi.png",
  japanese: "/static/style_images/japanese.png",
  melad: "/static/style_images/melad.png",
  american: "/static/style_images/american_taiwan.png",
  american_country: "/static/style_images/american_country.png",
  light_luxury: "/static/style_images/light_luxury.png",
  classical: "/static/style_images/classical.png",
  eclectic: "/static/style_images/eclectic.png",
};

const STYLE_STAGE_MEDIA = {
  scandinavian: { position: "50% 52%", scale: 1.02 },
  modern: { position: "50% 50%", scale: 1.03 },
  minimalist_muji: { position: "50% 50%", scale: 1.08 },
  nordic_modern: { position: "50% 51%", scale: 1.04 },
  industrial: { position: "50% 50%", scale: 1.04 },
  wabi_sabi: { position: "49% 45%", scale: 1.06 },
  japanese: { position: "50% 50%", scale: 1.04 },
  melad: { position: "52% 52%", scale: 1.03 },
  american: { position: "50% 50%", scale: 1.05 },
  american_country: { position: "50% 54%", scale: 1.06 },
  light_luxury: { position: "50% 52%", scale: 1.04 },
  classical: { position: "50% 52%", scale: 1.04 },
  eclectic: { position: "50% 52%", scale: 1.05 },
};

const STYLE_ANNOTATIONS = {
  scandinavian: [
    { text: "大面採光窗", anchorX: 14, anchorY: 37, labelX: 22, labelY: 24, align: "left" },
    { text: "淺木層架", anchorX: 48, anchorY: 29, labelX: 58, labelY: 24, align: "left" },
    { text: "植栽點綴", anchorX: 81, anchorY: 42, labelX: 89, labelY: 41, align: "left" },
    { text: "淺米布沙發", anchorX: 58, anchorY: 72, labelX: 45, labelY: 73, align: "right" },
    { text: "溫潤木桌", anchorX: 61, anchorY: 81, labelX: 76, labelY: 79, align: "left" },
  ],
  modern: [
    { text: "幾何線條", anchorX: 40, anchorY: 30, labelX: 28, labelY: 20, align: "right" },
    { text: "低裝飾量體", anchorX: 17, anchorY: 68, labelX: 28, labelY: 62, align: "left" },
    { text: "俐落收納", anchorX: 81, anchorY: 36, labelX: 72, labelY: 28, align: "right" },
    { text: "玻璃 / 金屬", anchorX: 68, anchorY: 60, labelX: 77, labelY: 58, align: "left" },
    { text: "中性色基底", anchorX: 51, anchorY: 77, labelX: 58, labelY: 76, align: "left" },
  ],
  minimalist_muji: [
    { text: "障子推拉窗", anchorX: 17, anchorY: 27, labelX: 13, labelY: 18, align: "left" },
    { text: "木格柵屏風", anchorX: 57, anchorY: 24, labelX: 66, labelY: 16, align: "left" },
    { text: "格柵電視櫃", anchorX: 79, anchorY: 61, labelX: 87, labelY: 54, align: "left" },
    { text: "低檯木桌", anchorX: 46, anchorY: 78, labelX: 54, labelY: 72, align: "left" },
    { text: "和紙立燈", anchorX: 95, anchorY: 58, labelX: 88, labelY: 47, align: "right" },
  ],
  nordic_modern: [
    { text: "灰藍點綴", anchorX: 78, anchorY: 29, labelX: 88, labelY: 22, align: "left" },
    { text: "現代櫃體", anchorX: 73, anchorY: 58, labelX: 85, labelY: 56, align: "left" },
    { text: "輕量家具", anchorX: 20, anchorY: 66, labelX: 28, labelY: 60, align: "left" },
    { text: "木質 + 金屬", anchorX: 49, anchorY: 82, labelX: 58, labelY: 80, align: "left" },
    { text: "明亮基底", anchorX: 16, anchorY: 14, labelX: 20, labelY: 10, align: "left" },
  ],
  industrial: [
    { text: "黑鐵層架", x: 28, y: 18 },
    { text: "深色櫃體", x: 76, y: 24 },
    { text: "水泥塗層牆", x: 72, y: 60 },
    { text: "粗獷木桌", x: 30, y: 74 },
    { text: "工業吊燈", x: 58, y: 76 },
  ],
  wabi_sabi: [
    { text: "亞麻窗簾", anchorX: 11, anchorY: 36, labelX: 20, labelY: 24, align: "left" },
    { text: "弧形拱門", anchorX: 33, anchorY: 28, labelX: 44, labelY: 40, align: "left" },
    { text: "礦物塗料牆", anchorX: 60, anchorY: 29, labelX: 77, labelY: 22, align: "left" },
    { text: "紙燈罩", anchorX: 50, anchorY: 14, labelX: 71, labelY: 15, align: "left" },
    { text: "低彩陶器", anchorX: 69, anchorY: 39, labelX: 82, labelY: 58, align: "left" },
  ],
  japanese: [
    { text: "木格柵牆", x: 74, y: 22 },
    { text: "原木矮櫃", x: 28, y: 72 },
    { text: "榻榻米 / 低平台", x: 46, y: 82 },
    { text: "留白牆面", x: 18, y: 18 },
    { text: "柔和光影", x: 59, y: 20 },
  ],
  melad: [
    { text: "奶油線板", anchorX: 47, anchorY: 31, labelX: 57, labelY: 18, align: "left" },
    { text: "暖調畫作", anchorX: 78, anchorY: 24, labelX: 84, labelY: 20, align: "left" },
    { text: "棕咖疊色", anchorX: 76, anchorY: 57, labelX: 83, labelY: 56, align: "left" },
    { text: "深木茶几", anchorX: 35, anchorY: 78, labelX: 25, labelY: 74, align: "right" },
    { text: "厚織抱枕", anchorX: 73, anchorY: 61, labelX: 79, labelY: 63, align: "left" },
  ],
  american: [
    { text: "採光大窗", anchorX: 10, anchorY: 24, labelX: 17, labelY: 18, align: "left" },
    { text: "花布抱枕", anchorX: 20, anchorY: 61, labelX: 30, labelY: 58, align: "left" },
    { text: "實木茶几", anchorX: 44, anchorY: 80, labelX: 35, labelY: 75, align: "right" },
    { text: "藤編收納籃", anchorX: 64, anchorY: 12, labelX: 74, labelY: 10, align: "left" },
    { text: "線板收納櫃", anchorX: 66, anchorY: 42, labelX: 81, labelY: 24, align: "left" },
  ],
  american_country: [
    { text: "碎花窗簾", x: 18, y: 20 },
    { text: "木作茶几", x: 51, y: 74 },
    { text: "鄉村電視櫃", x: 74, y: 60 },
    { text: "淺木邊几", x: 69, y: 24 },
    { text: "柔布沙發", x: 28, y: 60 },
  ],
  light_luxury: [
    { text: "大理石茶几", x: 29, y: 74 },
    { text: "金屬燈飾", x: 74, y: 22 },
    { text: "絲絨單椅", x: 65, y: 58 },
    { text: "玻璃展示", x: 48, y: 16 },
    { text: "暖光層次", x: 75, y: 76 },
  ],
  classical: [
    { text: "古典線板", x: 18, y: 18 },
    { text: "對稱畫框", x: 52, y: 16 },
    { text: "深色木作", x: 28, y: 74 },
    { text: "拱形壁龕", x: 69, y: 26 },
    { text: "高背沙發", x: 75, y: 60 },
  ],
  eclectic: [
    { text: "多風格掛畫", anchorX: 39, anchorY: 11, labelX: 29, labelY: 14, align: "right" },
    { text: "黑色書櫃", anchorX: 68, anchorY: 21, labelX: 79, labelY: 18, align: "left" },
    { text: "紅棕單椅", anchorX: 60, anchorY: 57, labelX: 71, labelY: 54, align: "left" },
    { text: "跳色靠枕", anchorX: 81, anchorY: 60, labelX: 84, labelY: 54, align: "left" },
    { text: "花紋腳凳", anchorX: 36, anchorY: 84, labelX: 28, labelY: 77, align: "right" },
  ],
};

const STYLE_SURFACE_FALLBACKS = {
  scandinavian: {
    wall_recommendations: [
      { name_zh: "暖白乳膠漆", tone_zh: "暖白", finish_zh: "霧面", why_zh: "保留自然採光感，讓淺木與布料更乾淨。" },
      { name_zh: "奶茶米色牆", tone_zh: "奶茶米色", finish_zh: "低反光", why_zh: "增加溫度感，但不會破壞北歐的留白。" },
    ],
    floor_recommendations: [
      { name_zh: "淺橡木地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "是最穩定的北歐搭配，視覺最輕盈。" },
      { name_zh: "白橡木 SPC", material_zh: "SPC", finish_zh: "細木紋", why_zh: "想保留好清潔與耐磨時很適合。" },
    ],
    recommended_wall_floor_pairs_zh: ["暖白乳膠漆 + 淺橡木地板", "奶茶米色牆 + 白橡木 SPC"],
  },
  modern: {
    wall_recommendations: [
      { name_zh: "冷灰白牆面", tone_zh: "冷灰白", finish_zh: "霧面", why_zh: "讓櫃體、金屬、玻璃線條更俐落。" },
      { name_zh: "石墨灰重點牆", tone_zh: "石墨灰", finish_zh: "平整漆面", why_zh: "適合做局部主牆，能拉出都會感。" },
    ],
    floor_recommendations: [
      { name_zh: "石紋灰地磚", material_zh: "磁磚", finish_zh: "大板石紋", why_zh: "乾淨、理性，和現代櫃體很合。" },
      { name_zh: "淺灰微水泥地坪", material_zh: "微水泥", finish_zh: "無縫質地", why_zh: "適合極簡、現代、收納牆主導的空間。" },
    ],
    recommended_wall_floor_pairs_zh: ["冷灰白牆面 + 石紋灰地磚", "石墨灰重點牆 + 淺灰微水泥地坪"],
  },
  minimalist_muji: {
    wall_recommendations: [
      { name_zh: "留白米白牆", tone_zh: "米白", finish_zh: "低光澤", why_zh: "讓木格柵、棉麻和留白感更明顯。" },
      { name_zh: "淡杏色礦物牆", tone_zh: "淡杏", finish_zh: "礦物塗層", why_zh: "增加柔和層次，又不會太裝飾。" },
    ],
    floor_recommendations: [
      { name_zh: "自然原木地板", material_zh: "木地板", finish_zh: "淺木紋", why_zh: "最能帶出 MUJI 的安靜生活感。" },
      { name_zh: "霧面淺木 SPC", material_zh: "SPC", finish_zh: "薄木紋", why_zh: "適合預算控制與日常使用。" },
    ],
    recommended_wall_floor_pairs_zh: ["留白米白牆 + 自然原木地板", "淡杏色礦物牆 + 霧面淺木 SPC"],
  },
  nordic_modern: {
    wall_recommendations: [
      { name_zh: "冷白灰牆", tone_zh: "冷白灰", finish_zh: "霧面", why_zh: "明亮基底更適合灰藍色與現代櫃體。" },
      { name_zh: "灰藍主牆", tone_zh: "灰藍", finish_zh: "平滑漆面", why_zh: "作為點綴牆，能和北歐現代更貼合。" },
    ],
    floor_recommendations: [
      { name_zh: "淡木紋地板", material_zh: "木地板", finish_zh: "低彩木紋", why_zh: "保留北歐輕量感，又不會太鄉村。" },
      { name_zh: "淺灰石紋地坪", material_zh: "磁磚", finish_zh: "細石紋", why_zh: "適合更都會、更現代的北歐版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["冷白灰牆 + 淡木紋地板", "灰藍主牆 + 淺灰石紋地坪"],
  },
  industrial: {
    wall_recommendations: [
      { name_zh: "水泥灰牆", tone_zh: "水泥灰", finish_zh: "微粗礦物感", why_zh: "最能撐起工業風的粗獷主調。" },
      { name_zh: "裸磚紅棕牆", tone_zh: "磚紅棕", finish_zh: "仿磚質感", why_zh: "適合和黑鐵、軌道燈一起搭配。" },
    ],
    floor_recommendations: [
      { name_zh: "深木地板", material_zh: "木地板", finish_zh: "深木紋", why_zh: "可平衡鐵件與灰牆的冷硬感。" },
      { name_zh: "清水模地坪", material_zh: "微水泥", finish_zh: "無縫粗霧面", why_zh: "想要更純工業感時最合適。" },
    ],
    recommended_wall_floor_pairs_zh: ["水泥灰牆 + 清水模地坪", "裸磚紅棕牆 + 深木地板"],
  },
  wabi_sabi: {
    wall_recommendations: [
      { name_zh: "礦物米灰牆", tone_zh: "米灰", finish_zh: "礦物塗層", why_zh: "表面帶不均勻感，最符合侘寂語彙。" },
      { name_zh: "暖灰土色牆", tone_zh: "暖灰土色", finish_zh: "霧面粗肌理", why_zh: "能搭配亞麻、陶器與紙燈罩。" },
    ],
    floor_recommendations: [
      { name_zh: "微水泥地坪", material_zh: "微水泥", finish_zh: "低反光", why_zh: "和弧形拱門、礦物牆最一致。" },
      { name_zh: "淺木自然地板", material_zh: "木地板", finish_zh: "柔和木紋", why_zh: "想更溫潤時可用木地板平衡空間。" },
    ],
    recommended_wall_floor_pairs_zh: ["礦物米灰牆 + 微水泥地坪", "暖灰土色牆 + 淺木自然地板"],
  },
  melad: {
    wall_recommendations: [
      { name_zh: "奶油暖米牆", tone_zh: "奶油米", finish_zh: "霧面", why_zh: "提供美拉德色系需要的暖底色。" },
      { name_zh: "焦糖米棕牆", tone_zh: "焦糖米棕", finish_zh: "低光澤", why_zh: "適合深木、棕咖抱枕與暖光。" },
    ],
    floor_recommendations: [
      { name_zh: "胡桃木地板", material_zh: "木地板", finish_zh: "深木紋", why_zh: "是最直覺的美拉德基底。" },
      { name_zh: "煙燻木地板", material_zh: "木地板", finish_zh: "低彩深木紋", why_zh: "可讓層次更穩重，不會太甜。" },
    ],
    recommended_wall_floor_pairs_zh: ["奶油暖米牆 + 胡桃木地板", "焦糖米棕牆 + 煙燻木地板"],
  },
  american: {
    wall_recommendations: [
      { name_zh: "奶油白線板牆", tone_zh: "奶油白", finish_zh: "半平滑", why_zh: "更符合台灣住宅常見的明亮美式客廳。" },
      { name_zh: "暖白櫃牆", tone_zh: "暖白", finish_zh: "平整漆面", why_zh: "能搭配收納櫃、藤編籃與家庭感軟裝。" },
    ],
    floor_recommendations: [
      { name_zh: "中木色地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "穩定、好搭，也不會像壁爐宅邸風。" },
      { name_zh: "暖木紋 SPC", material_zh: "SPC", finish_zh: "柔和木紋", why_zh: "適合台灣日常居家與好清潔需求。" },
    ],
    recommended_wall_floor_pairs_zh: ["奶油白線板牆 + 中木色地板", "暖白櫃牆 + 暖木紋 SPC"],
  },
  american_country: {
    wall_recommendations: [
      { name_zh: "暖白鄉村牆", tone_zh: "暖白", finish_zh: "霧面", why_zh: "讓碎花、木作與鄉村櫃體更柔和。" },
      { name_zh: "淡米杏牆", tone_zh: "淡米杏", finish_zh: "低光澤", why_zh: "能帶出更溫暖的家庭感。" },
    ],
    floor_recommendations: [
      { name_zh: "淺木地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "最適合鄉村風的日常住宅感。" },
      { name_zh: "仿舊木紋地板", material_zh: "木地板 / SPC", finish_zh: "仿舊木紋", why_zh: "可強化鄉村感與木作家具呼應。" },
    ],
    recommended_wall_floor_pairs_zh: ["暖白鄉村牆 + 淺木地板", "淡米杏牆 + 仿舊木紋地板"],
  },
  light_luxury: {
    wall_recommendations: [
      { name_zh: "冷灰白牆", tone_zh: "冷灰白", finish_zh: "細緻漆面", why_zh: "能襯托金屬、玻璃與大理石。" },
      { name_zh: "淡米石紋牆", tone_zh: "淡米灰", finish_zh: "石紋塗層", why_zh: "比純白更多層次，也更顯精緻。" },
    ],
    floor_recommendations: [
      { name_zh: "大理石地坪", material_zh: "石材 / 磁磚", finish_zh: "亮面石紋", why_zh: "最能直接拉出輕奢質感。" },
      { name_zh: "淺灰石紋磚", material_zh: "磁磚", finish_zh: "中高反光", why_zh: "適合較清爽、不過度奢華的版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["冷灰白牆 + 大理石地坪", "淡米石紋牆 + 淺灰石紋磚"],
  },
  classical: {
    wall_recommendations: [
      { name_zh: "古典米白線板牆", tone_zh: "米白", finish_zh: "平整漆面", why_zh: "最能支撐古典線板與對稱構圖。" },
      { name_zh: "暖米灰主牆", tone_zh: "暖米灰", finish_zh: "絲滑霧面", why_zh: "讓古典元素不會太厚重。" },
    ],
    floor_recommendations: [
      { name_zh: "深木地板", material_zh: "木地板", finish_zh: "深木紋", why_zh: "與古典家具、畫框最容易相呼應。" },
      { name_zh: "石紋拼花磚", material_zh: "磁磚", finish_zh: "古典拼花", why_zh: "適合想把古典感做得更完整時使用。" },
    ],
    recommended_wall_floor_pairs_zh: ["古典米白線板牆 + 深木地板", "暖米灰主牆 + 石紋拼花磚"],
  },
  eclectic: {
    wall_recommendations: [
      { name_zh: "中性暖白牆", tone_zh: "暖白", finish_zh: "霧面", why_zh: "給混搭家具一個穩定背景，不會太亂。" },
      { name_zh: "灰調主牆", tone_zh: "灰調", finish_zh: "低光澤", why_zh: "能承接異材質與跳色軟裝。" },
    ],
    floor_recommendations: [
      { name_zh: "中木色地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "混搭空間最需要一個穩定的底。" },
      { name_zh: "層次灰地毯搭配木地板", material_zh: "木地板 + 地毯", finish_zh: "軟硬混搭", why_zh: "更能呈現混搭的層次與生活感。" },
    ],
    recommended_wall_floor_pairs_zh: ["中性暖白牆 + 中木色地板", "灰調主牆 + 層次灰地毯搭配木地板"],
  },
};

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function joinList(items = []) {
  return items.filter(Boolean).join("、");
}

function normalizeAnnotation(item) {
  const labelX = item.labelX ?? item.x ?? 50;
  const labelY = item.labelY ?? item.y ?? 50;
  const align = item.align ?? (labelX > 64 ? "right" : "left");
  const fallbackOffset = align === "right" ? 6 : -6;
  const anchorX = item.anchorX ?? labelX + fallbackOffset;
  const anchorY = item.anchorY ?? labelY;
  return { ...item, labelX, labelY, anchorX, anchorY, align };
}

let activeStyleId = data.styles[0]?.style_id ?? null;

function renderTabs() {
  tabRow.innerHTML = "";

  data.styles.forEach((style, index) => {
    const colors = style.palette_hex?.length ? style.palette_hex : ["#f6f1e8", "#d8c8b0", "#a88a67"];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "style-tab-button";
    button.dataset.styleId = style.style_id;
    button.style.setProperty("--tab-tone-a", colors[0]);
    button.style.setProperty("--tab-tone-b", colors[1] ?? colors[0]);
    button.style.setProperty("--tab-tone-c", colors[2] ?? colors[1] ?? colors[0]);
    button.innerHTML = `
      <span class="style-tab-index">${String(index + 1).padStart(2, "0")}</span>
      <span class="style-tab-title">${escapeHtml(style.style_name_zh)}</span>
    `;

    if (style.style_id === activeStyleId) {
      button.classList.add("active");
    }

    button.addEventListener("click", () => {
      activeStyleId = style.style_id;
      renderTabs();
      renderActiveStyle();
    });

    tabRow.appendChild(button);
  });
}

function renderAnnotations(styleId) {
  const annotations = (STYLE_ANNOTATIONS[styleId] ?? STYLE_ANNOTATIONS.eclectic).map(normalizeAnnotation);
  const lineSvg = annotations
    .map(
      (item) => `
        <line x1="${item.anchorX}" y1="${item.anchorY}" x2="${item.labelX}" y2="${item.labelY}" />
        <circle cx="${item.anchorX}" cy="${item.anchorY}" r="0.9" />
      `
    )
    .join("");

  const labels = annotations
    .map(
      (item) => `
        <div class="style-annotation-label-badge align-${item.align}" style="left:${item.labelX}%; top:${item.labelY}%;">
          ${escapeHtml(item.text)}
        </div>
      `
    )
    .join("");

  return `
    <svg class="style-annotation-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      ${lineSvg}
    </svg>
    ${labels}
  `;
}

function buildSurfacePreviewStyle(item) {
  if (!item) return "";

  const imageUrl = item.preview_url || item.texture_url;
  if (imageUrl) {
    return [
      `background-image:url('${imageUrl}')`,
      "background-size:cover",
      "background-position:center",
    ].join(";");
  }

  const base = item.preview_hex || item.base_hex || "#e8dbc9";
  const accent = item.accent_hex || base;
  return `background:linear-gradient(135deg, ${base}, ${accent});`;
}

function renderSurfaceRecommendations(items, categoryLabel) {
  if (!items?.length) {
    return `<p>尚未整理 ${escapeHtml(categoryLabel)} 推薦。</p>`;
  }

  return `
    <div class="surface-recommendation-list">
      ${items
        .map((item) => {
          const detailParts = [item.tone_zh ?? item.material_zh, item.finish_zh].filter(Boolean);
          return `
            <article class="surface-recommendation-item">
              <div class="surface-recommendation-preview" style="${buildSurfacePreviewStyle(item)}"></div>
              <div class="surface-recommendation-body">
                <div class="surface-recommendation-head">
                <strong>${escapeHtml(item.name_zh ?? "-")}</strong>
                ${detailParts.length ? `<span>${escapeHtml(detailParts.join(" / "))}</span>` : ""}
              </div>
              <p>${escapeHtml(item.why_zh ?? "此推薦會依風格特徵與空間背景自動補齊。")}</p>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPairRecommendations(pairs) {
  if (!pairs?.length) {
    return "<p>尚未整理推薦搭配。</p>";
  }

  return `
    <div class="style-chip-row">
      ${pairs.map((pair) => `<span class="style-chip">${escapeHtml(pair)}</span>`).join("")}
    </div>
  `;
}

function getSurfaceFallback(style) {
  return (
    STYLE_SURFACE_FALLBACKS[style.style_id] ?? {
      wall_recommendations: [],
      floor_recommendations: [],
      recommended_wall_floor_pairs_zh: [],
    }
  );
}

function hasBrokenText(value) {
  const text = String(value ?? "").trim();
  return !text || text.includes("?") || text.includes("�");
}

function hasReadableSurfaceRecommendations(items = []) {
  return items.some((item) => !hasBrokenText(item.name_zh) && !hasBrokenText(item.why_zh));
}

function hasReadablePairs(items = []) {
  return items.some((item) => !hasBrokenText(item));
}

function renderStyleStage(style) {
  const colors = style.palette_hex?.length ? style.palette_hex : ["#f6f1e8", "#d8c8b0", "#a88a67"];
  const imageBase = STYLE_IMAGE_MAP[style.style_id] ?? STYLE_IMAGE_MAP.eclectic;
  const imageUrl = `${imageBase}${imageBase.includes("?") ? "&" : "?"}v=${STYLE_IMAGE_VERSION}`;
  const stageMedia = STYLE_STAGE_MEDIA[style.style_id] ?? STYLE_STAGE_MEDIA.eclectic;
  const count = style.stats?.matched_furniture_count ?? 0;

  return `
    <div class="style-stage" style="--tone-a:${colors[0]}; --tone-b:${colors[1] ?? colors[0]}; --tone-c:${colors[2] ?? colors[1] ?? colors[0]};">
      <img
        class="style-stage-image"
        src="${imageUrl}"
        alt="${escapeHtml(style.style_name_zh)} 風格示意圖"
        style="object-position:${stageMedia.position}; transform:scale(${stageMedia.scale});"
      />
      <div class="style-stage-overlay"></div>
      <div class="style-stage-header">
        <span class="style-stage-label">STYLE VISUAL</span>
        <div class="badge-row">
          <span class="badge">${escapeHtml(style.style_name_zh)}</span>
          <span class="badge">${escapeHtml(style.style_name_en ?? "")}</span>
          <span class="badge">${count} 件家具</span>
        </div>
      </div>
      <div class="style-stage-title">
        <strong>${escapeHtml(style.style_name_zh)}</strong>
      </div>
      <div class="style-stage-annotation-layer">
        ${renderAnnotations(style.style_id)}
      </div>
    </div>
  `;
}

function renderActiveStyle() {
  const style = data.styles.find((item) => item.style_id === activeStyleId);
  if (!style) {
    return;
  }

  const theme = style.visual_theme ?? {};
  const accentFill = theme.accent_fill ?? "#ead8c5";
  const panelFill = "#fffaf4";
  const panelOutline = "rgba(197, 176, 154, 0.48)";
  const titleColor = "#2d2926";
  const bodyColor = "#564e47";
  const shellToneA = "#fffaf4";
  const shellToneB = "#f1e7db";
  const shellToneC = "#dcc8af";
  const topCount = style.stats?.matched_furniture_count ?? 0;
  const topTypes = (style.stats?.top_types ?? [])
    .slice(0, 4)
    .map(([typeName, count]) => `${formatTypeLabel(typeName)} ${count}`)
    .join(" / ");

  const surfaceFallback = getSurfaceFallback(style);
  const wallRecommendations = hasReadableSurfaceRecommendations(style.wall_recommendations)
    ? style.wall_recommendations
    : surfaceFallback.wall_recommendations;
  const floorRecommendations = hasReadableSurfaceRecommendations(style.floor_recommendations)
    ? style.floor_recommendations
    : surfaceFallback.floor_recommendations;
  const recommendedPairs = hasReadablePairs(style.recommended_wall_floor_pairs_zh)
    ? style.recommended_wall_floor_pairs_zh
    : surfaceFallback.recommended_wall_floor_pairs_zh;

  document.documentElement.style.setProperty("--style-shell-a", shellToneA);
  document.documentElement.style.setProperty("--style-shell-b", shellToneB);
  document.documentElement.style.setProperty("--style-shell-c", shellToneC);

  detailPanel.innerHTML = `
    <div class="style-hero-card style-enter" style="--panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor}; --accent-fill:${accentFill};">
      ${renderStyleStage(style)}
    </div>

    <div class="style-section-grid">
      <article class="style-info-card style-enter" style="--delay:40ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>關鍵字</h3>
        <p>${escapeHtml(joinList(style.keywords_zh))}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:80ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>主色</h3>
        <div class="swatch-row">
          ${(style.main_colors_zh ?? [])
            .map(
              (name, index) => `
                <span class="color-pill">
                  <span class="color-dot" style="background:${style.palette_hex?.[index] ?? "#d9d9d9"}"></span>
                  ${escapeHtml(name)}
                </span>
              `
            )
            .join("")}
        </div>
      </article>

      <article class="style-info-card style-enter" style="--delay:120ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>材質</h3>
        <p>${escapeHtml(joinList(style.materials_zh))}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:160ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>造型特徵</h3>
        <p>${escapeHtml(joinList(style.shape_features_zh))}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:200ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>不要的元素</h3>
        <p>${escapeHtml(joinList(style.avoid_elements_zh))}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:240ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>空間背景</h3>
        <p>牆面：${escapeHtml(style.scene_background?.wall_zh ?? "-")}</p>
        <p>地板：${escapeHtml(style.scene_background?.floor_zh ?? "-")}</p>
        <p>整體：${escapeHtml(style.scene_background?.overall_zh ?? "-")}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:280ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>牆面推薦</h3>
        ${renderSurfaceRecommendations(wallRecommendations, "牆面")}
      </article>

      <article class="style-info-card style-enter" style="--delay:320ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>地板推薦</h3>
        ${renderSurfaceRecommendations(floorRecommendations, "地板")}
      </article>

      <article class="style-info-card wide style-enter" style="--delay:360ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>推薦搭配組合</h3>
        ${renderPairRecommendations(recommendedPairs)}
      </article>

      <article class="style-info-card wide style-enter" style="--delay:400ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>目前資料庫對應狀況</h3>
        <p>家具數量：${topCount}</p>
        <p>主要家具類型：${escapeHtml(topTypes || "尚未整理資料庫對應分類。")}</p>
      </article>
    </div>
  `;
}

renderTabs();
renderActiveStyle();
initBackgroundFx();
