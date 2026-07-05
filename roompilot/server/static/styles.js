import { fetchSiteData, formatList, initBackgroundFx } from "./common.js?v=20260704e";

const data = await fetchSiteData();
const tabRow = document.getElementById("style-tab-row");
const detailPanel = document.getElementById("style-detail-panel");

const STYLE_IMAGE_MAP = {
  scandinavian: "/static/style_images/scandinavian.png",
  modern: "/static/style_images/modern.png",
  minimalist_muji: "/static/style_images/minimalist_muji.png",
  nordic_modern: "/static/style_images/nordic_modern.png",
  industrial: "/static/style_images/industrial.png",
  wabi_sabi: "/static/style_images/wabi_sabi.png",
  japanese: "/static/style_images/japanese.png",
  american: "/static/style_images/american.png",
  american_country: "/static/style_images/american_country.png",
  light_luxury: "/static/style_images/light_luxury.png",
  classical: "/static/style_images/classical.png",
  eclectic: "/static/style_images/eclectic.png",
  melad: "/static/style_images/eclectic.png",
};

const STYLE_SURFACE_FALLBACKS = {
  scandinavian: {
    wall_recommendations: [
      { name_zh: "暖白牆面", tone_zh: "暖白", finish_zh: "霧面乳膠漆", why_zh: "保留北歐風最需要的明亮採光感，和淺木家具最協調。" },
      { name_zh: "奶油米灰牆", tone_zh: "奶油米灰", finish_zh: "柔霧塗裝", why_zh: "讓空間更溫暖，不會像純白那麼冷。" },
      { name_zh: "霧灰白牆", tone_zh: "低彩灰白", finish_zh: "礦物感漆面", why_zh: "適合想保留留白但又多一點層次的版本。" },
    ],
    floor_recommendations: [
      { name_zh: "淺橡木地板", material_zh: "木地板 / SPC", finish_zh: "自然木紋", why_zh: "最符合北歐風常見的淺木、輕量、自然感。" },
      { name_zh: "白橡木地板", material_zh: "超耐磨木地板", finish_zh: "低反光霧面", why_zh: "適合搭配白牆與亞麻、棉麻布料。" },
      { name_zh: "米灰石紋地坪", material_zh: "石紋磚 / SPC", finish_zh: "細緻霧面", why_zh: "想要更現代一點但仍維持低彩時很好用。" },
    ],
    recommended_wall_floor_pairs_zh: ["暖白牆面 + 淺橡木地板", "奶油米灰牆 + 白橡木地板"],
  },
  modern: {
    wall_recommendations: [
      { name_zh: "冷白灰牆", tone_zh: "冷白灰", finish_zh: "細霧面", why_zh: "讓俐落線條更乾淨，適合現代簡約的大面收納。" },
      { name_zh: "石墨灰重點牆", tone_zh: "石墨灰", finish_zh: "消光漆面", why_zh: "適合電視牆或主牆，強化現代感。" },
      { name_zh: "霧感淺灰牆", tone_zh: "淺灰", finish_zh: "平整塗裝", why_zh: "中性、安全，容易搭配玻璃與金屬。" },
    ],
    floor_recommendations: [
      { name_zh: "灰石紋地板", material_zh: "石紋磚 / SPC", finish_zh: "低反光", why_zh: "最能呼應現代風常見的理性中性色。" },
      { name_zh: "煙燻木地板", material_zh: "木地板", finish_zh: "細木紋", why_zh: "比淺木更成熟，適合黑白灰家具。" },
      { name_zh: "微水泥地坪", material_zh: "微水泥", finish_zh: "連續面", why_zh: "很適合極簡、櫃體一體化的空間。" },
    ],
    recommended_wall_floor_pairs_zh: ["冷白灰牆 + 灰石紋地板", "石墨灰重點牆 + 微水泥地坪"],
  },
  minimalist_muji: {
    wall_recommendations: [
      { name_zh: "米白牆面", tone_zh: "米白", finish_zh: "柔霧漆", why_zh: "符合無印風放鬆、低壓、留白的基底。" },
      { name_zh: "淡奶茶牆", tone_zh: "淡奶茶", finish_zh: "礦物霧面", why_zh: "比純白更有生活感，也更接近日系住宅。" },
      { name_zh: "柔灰白牆", tone_zh: "柔灰白", finish_zh: "低彩塗裝", why_zh: "適合搭配原木與藤編元素。" },
    ],
    floor_recommendations: [
      { name_zh: "自然木地板", material_zh: "木地板", finish_zh: "原木感", why_zh: "最能表現無印風的自然與安定感。" },
      { name_zh: "淺梣木地板", material_zh: "超耐磨地板", finish_zh: "細木紋", why_zh: "色澤更輕，適合小空間。" },
      { name_zh: "米灰木石混搭地坪", material_zh: "SPC", finish_zh: "低彩霧面", why_zh: "適合希望更好清潔的住宅版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["米白牆面 + 自然木地板", "淡奶茶牆 + 淺梣木地板"],
  },
  nordic_modern: {
    wall_recommendations: [
      { name_zh: "暖灰白牆", tone_zh: "暖灰白", finish_zh: "霧面", why_zh: "保留北歐明亮基底，但更靠近現代風收斂感。" },
      { name_zh: "灰藍點綴牆", tone_zh: "霧灰藍", finish_zh: "局部主牆", why_zh: "可以把灰藍點綴拉進背景層次。" },
      { name_zh: "奶霧白牆", tone_zh: "奶霧白", finish_zh: "柔霧塗裝", why_zh: "很適合搭配木質 + 金屬家具。" },
    ],
    floor_recommendations: [
      { name_zh: "淺木地板", material_zh: "木地板", finish_zh: "低反光", why_zh: "維持北歐基底，讓家具更好搭。" },
      { name_zh: "淺灰橡木地板", material_zh: "木地板 / SPC", finish_zh: "淡灰木紋", why_zh: "和灰藍、現代櫃體很合。" },
      { name_zh: "米灰石紋地坪", material_zh: "石紋地板", finish_zh: "大板感", why_zh: "讓整體更都會。" },
    ],
    recommended_wall_floor_pairs_zh: ["暖灰白牆 + 淺木地板", "灰藍點綴牆 + 淺灰橡木地板"],
  },
  industrial: {
    wall_recommendations: [
      { name_zh: "水泥灰牆", tone_zh: "中灰", finish_zh: "礦物塗料", why_zh: "工業風最常見的基礎牆面語言。" },
      { name_zh: "炭灰主牆", tone_zh: "炭灰", finish_zh: "消光漆", why_zh: "適合搭配黑鐵件與深色家具。" },
      { name_zh: "舊化米灰牆", tone_zh: "舊化灰米", finish_zh: "刷痕感", why_zh: "能保留粗獷感但不會太冷硬。" },
    ],
    floor_recommendations: [
      { name_zh: "微水泥地坪", material_zh: "微水泥", finish_zh: "連續面", why_zh: "最直接地建立工業風氛圍。" },
      { name_zh: "深木地板", material_zh: "木地板", finish_zh: "深木紋", why_zh: "讓黑鐵與皮革更穩重。" },
      { name_zh: "深灰石紋地板", material_zh: "石紋磚", finish_zh: "霧面", why_zh: "適合更現代的工業風版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["水泥灰牆 + 微水泥地坪", "炭灰主牆 + 深木地板"],
  },
  wabi_sabi: {
    wall_recommendations: [
      { name_zh: "礦物米灰牆", tone_zh: "米灰", finish_zh: "礦物塗料", why_zh: "能做出侘寂風最重要的手感與不均質感。" },
      { name_zh: "泥灰土色牆", tone_zh: "土灰褐", finish_zh: "手抹紋理", why_zh: "很適合搭配弧形牆面與陶器。" },
      { name_zh: "暖灰褐牆", tone_zh: "暖灰褐", finish_zh: "柔霧塗層", why_zh: "比純灰更有靜謐感。" },
    ],
    floor_recommendations: [
      { name_zh: "微水泥地坪", material_zh: "微水泥", finish_zh: "柔霧", why_zh: "最能延續侘寂的礦物質感。" },
      { name_zh: "自然木地板", material_zh: "木地板", finish_zh: "低彩木紋", why_zh: "讓空間更溫潤。" },
      { name_zh: "米灰石紋地坪", material_zh: "石紋磚", finish_zh: "不規則霧面", why_zh: "適合更乾淨的現代侘寂版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["礦物米灰牆 + 微水泥地坪", "泥灰土色牆 + 自然木地板"],
  },
  melad: {
    wall_recommendations: [
      { name_zh: "焦糖奶茶牆", tone_zh: "焦糖棕", finish_zh: "柔霧", why_zh: "讓美拉德風的暖棕層次更完整。" },
      { name_zh: "可可米色牆", tone_zh: "可可米", finish_zh: "細緻塗裝", why_zh: "比深咖更耐看，適合日常住宅。" },
      { name_zh: "暖褐灰牆", tone_zh: "褐灰", finish_zh: "低彩漆面", why_zh: "適合搭配皮革、胡桃木與奶油色布料。" },
    ],
    floor_recommendations: [
      { name_zh: "胡桃木地板", material_zh: "木地板", finish_zh: "深木紋", why_zh: "最能建立美拉德風溫暖厚度。" },
      { name_zh: "榛果木地板", material_zh: "木地板 / SPC", finish_zh: "暖棕木紋", why_zh: "比胡桃木輕一點，更適合中小空間。" },
      { name_zh: "暖米石紋地坪", material_zh: "石紋磚", finish_zh: "霧面", why_zh: "適合想加入現代感的版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["焦糖奶茶牆 + 胡桃木地板", "可可米色牆 + 榛果木地板"],
  },
  american: {
    wall_recommendations: [
      { name_zh: "奶油白牆", tone_zh: "奶油白", finish_zh: "平整漆面", why_zh: "適合美式風寬敞舒適的家庭感。" },
      { name_zh: "線板暖白牆", tone_zh: "暖白", finish_zh: "線板搭配", why_zh: "可直接呼應美式經典立面。" },
      { name_zh: "大地米灰牆", tone_zh: "米灰", finish_zh: "柔霧", why_zh: "和皮革沙發很協調。" },
    ],
    floor_recommendations: [
      { name_zh: "中木色地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "美式空間最常見的穩定基底。" },
      { name_zh: "深橡木地板", material_zh: "木地板", finish_zh: "微亮木紋", why_zh: "適合搭配厚實家具。" },
      { name_zh: "暖米石紋地坪", material_zh: "石紋磚", finish_zh: "柔光", why_zh: "能讓大空間更有整潔感。" },
    ],
    recommended_wall_floor_pairs_zh: ["線板暖白牆 + 中木色地板", "大地米灰牆 + 深橡木地板"],
  },
  american_country: {
    wall_recommendations: [
      { name_zh: "奶油米白牆", tone_zh: "奶油米白", finish_zh: "柔霧", why_zh: "適合美式鄉村的溫馨與懷舊感。" },
      { name_zh: "淡鼠尾草牆", tone_zh: "低彩綠灰", finish_zh: "霧面漆", why_zh: "很適合木作與鄉村布藝。" },
      { name_zh: "暖粉灰牆", tone_zh: "暖粉灰", finish_zh: "柔霧塗層", why_zh: "讓空間更柔和、有手作感。" },
    ],
    floor_recommendations: [
      { name_zh: "刷舊木地板", material_zh: "木地板", finish_zh: "仿舊木紋", why_zh: "很符合鄉村風的歲月感。" },
      { name_zh: "淺胡桃木地板", material_zh: "木地板", finish_zh: "暖棕木紋", why_zh: "可以保留溫暖感又不過深。" },
      { name_zh: "奶油石紋磚", material_zh: "石紋磚", finish_zh: "柔霧", why_zh: "適合想更好清潔的住宅版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["奶油米白牆 + 刷舊木地板", "淡鼠尾草牆 + 淺胡桃木地板"],
  },
  light_luxury: {
    wall_recommendations: [
      { name_zh: "奶霧白牆", tone_zh: "奶霧白", finish_zh: "平整漆面", why_zh: "讓金屬、大理石與玻璃更乾淨地被看見。" },
      { name_zh: "香檳米牆", tone_zh: "香檳米", finish_zh: "細緻微光", why_zh: "比白牆更有奢雅感。" },
      { name_zh: "霧灰主牆", tone_zh: "灰米", finish_zh: "柔光漆面", why_zh: "適合和鍍鈦、黃銅一起搭配。" },
    ],
    floor_recommendations: [
      { name_zh: "大理石紋地坪", material_zh: "拋光磚 / 石紋磚", finish_zh: "細亮面", why_zh: "最能表現輕奢風的精緻質感。" },
      { name_zh: "煙燻木地板", material_zh: "木地板", finish_zh: "高級木紋", why_zh: "讓空間多一點溫度，不會太冷。" },
      { name_zh: "淺灰石紋地板", material_zh: "石紋磚", finish_zh: "柔霧", why_zh: "適合比較內斂的輕奢版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["奶霧白牆 + 大理石紋地坪", "香檳米牆 + 煙燻木地板"],
  },
  classical: {
    wall_recommendations: [
      { name_zh: "米白古典牆", tone_zh: "米白", finish_zh: "線板漆面", why_zh: "適合古典風的對稱與雕飾。" },
      { name_zh: "暖金米牆", tone_zh: "暖金米", finish_zh: "柔光漆面", why_zh: "可襯托古典家具與金色細節。" },
      { name_zh: "灰褐古典牆", tone_zh: "灰褐", finish_zh: "低反光", why_zh: "更成熟穩重。" },
    ],
    floor_recommendations: [
      { name_zh: "深胡桃木地板", material_zh: "木地板", finish_zh: "細緻深木紋", why_zh: "和古典家具最協調。" },
      { name_zh: "石紋拼花地坪", material_zh: "磁磚", finish_zh: "拼花感", why_zh: "適合較正式的古典空間。" },
      { name_zh: "暖米大理石紋地坪", material_zh: "石紋磚", finish_zh: "微亮", why_zh: "可增加華麗度。" },
    ],
    recommended_wall_floor_pairs_zh: ["米白古典牆 + 深胡桃木地板", "暖金米牆 + 暖米大理石紋地坪"],
  },
  eclectic: {
    wall_recommendations: [
      { name_zh: "暖白基底牆", tone_zh: "暖白", finish_zh: "柔霧", why_zh: "混搭風最需要一個能包容多家具的乾淨背景。" },
      { name_zh: "灰米過渡牆", tone_zh: "灰米", finish_zh: "平整塗裝", why_zh: "適合承接不同材質與跳色家具。" },
      { name_zh: "低彩奶茶牆", tone_zh: "奶茶", finish_zh: "柔霧塗層", why_zh: "讓空間更溫暖，也能減少混搭雜亂感。" },
    ],
    floor_recommendations: [
      { name_zh: "中性木地板", material_zh: "木地板", finish_zh: "自然木紋", why_zh: "最容易包容不同家具。" },
      { name_zh: "淺灰石紋地坪", material_zh: "石紋磚 / SPC", finish_zh: "霧面", why_zh: "適合偏都會混搭。" },
      { name_zh: "暖米水泥地坪", material_zh: "微水泥", finish_zh: "柔霧", why_zh: "適合更有個性的混搭版本。" },
    ],
    recommended_wall_floor_pairs_zh: ["暖白基底牆 + 中性木地板", "灰米過渡牆 + 淺灰石紋地坪"],
  },
};

const STYLE_ANNOTATIONS = {
  scandinavian: [
    { text: "大面採光窗", x: 16, y: 18 },
    { text: "淺木層架", x: 60, y: 22 },
    { text: "植栽點綴", x: 73, y: 34 },
    { text: "奶白沙發", x: 28, y: 70 },
    { text: "溫潤木桌", x: 66, y: 76 },
  ],
  modern: [
    { text: "俐落收納牆", x: 28, y: 22 },
    { text: "幾何線條", x: 14, y: 18 },
    { text: "玻璃隔間", x: 74, y: 28 },
    { text: "中性色沙發", x: 65, y: 58 },
    { text: "低裝飾量體", x: 24, y: 66 },
  ],
  minimalist_muji: [
    { text: "留白牆面", x: 18, y: 18 },
    { text: "自然木桌", x: 50, y: 70 },
    { text: "薄邊櫃體", x: 74, y: 22 },
    { text: "棉麻織品", x: 29, y: 62 },
    { text: "柔和低彩度", x: 72, y: 74 },
  ],
  nordic_modern: [
    { text: "灰藍櫃體", x: 76, y: 28 },
    { text: "現代電視牆", x: 73, y: 58 },
    { text: "輕量木椅", x: 20, y: 66 },
    { text: "木質 + 金屬", x: 47, y: 82 },
    { text: "明亮基底", x: 15, y: 14 },
  ],
  industrial: [
    { text: "裸露樑柱", x: 28, y: 18 },
    { text: "黑鐵燈具", x: 76, y: 24 },
    { text: "水泥牆面", x: 72, y: 60 },
    { text: "粗獷木桌", x: 30, y: 74 },
    { text: "深色沙發", x: 58, y: 76 },
  ],
  wabi_sabi: [
    { text: "亞麻窗簾", x: 15, y: 26 },
    { text: "弧形拱門", x: 42, y: 48 },
    { text: "礦物塗料牆", x: 64, y: 22 },
    { text: "紙燈罩", x: 79, y: 18 },
    { text: "低飽和陶器", x: 69, y: 76 },
  ],
  japanese: [
    { text: "木格柵", x: 74, y: 22 },
    { text: "低矮家具", x: 28, y: 72 },
    { text: "榻榻米感地面", x: 46, y: 82 },
    { text: "留白牆面", x: 18, y: 18 },
    { text: "柔和光影", x: 59, y: 20 },
  ],
  melad: [
    { text: "暖棕牆面", x: 22, y: 20 },
    { text: "焦糖布沙發", x: 68, y: 60 },
    { text: "深木家具", x: 30, y: 74 },
    { text: "金屬燈具", x: 75, y: 24 },
    { text: "濃郁棕調", x: 51, y: 84 },
  ],
  american: [
    { text: "線板牆面", x: 18, y: 18 },
    { text: "厚實皮革", x: 69, y: 58 },
    { text: "大地色主體", x: 52, y: 16 },
    { text: "大件木桌", x: 28, y: 74 },
    { text: "寬敞客廳感", x: 77, y: 24 },
  ],
  american_country: [
    { text: "白框窗景", x: 18, y: 20 },
    { text: "鄉村木餐桌", x: 51, y: 74 },
    { text: "溫暖布織感", x: 74, y: 60 },
    { text: "自然木色", x: 69, y: 24 },
    { text: "柔和家飾", x: 28, y: 60 },
  ],
  light_luxury: [
    { text: "大理石桌面", x: 29, y: 74 },
    { text: "金屬框線", x: 74, y: 22 },
    { text: "絲絨沙發", x: 65, y: 58 },
    { text: "高級燈飾", x: 48, y: 16 },
    { text: "低調奢華", x: 75, y: 76 },
  ],
  classical: [
    { text: "古典線板", x: 18, y: 18 },
    { text: "對稱構圖", x: 52, y: 16 },
    { text: "雕飾家具", x: 28, y: 74 },
    { text: "厚窗簾", x: 69, y: 26 },
    { text: "華麗燈飾", x: 75, y: 60 },
  ],
  eclectic: [
    { text: "異材質組合", x: 18, y: 20 },
    { text: "混搭家具", x: 71, y: 26 },
    { text: "跳色家飾", x: 29, y: 68 },
    { text: "個性單椅", x: 70, y: 62 },
    { text: "層次色塊", x: 52, y: 84 },
  ],
};

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
      <span class="style-tab-title">${style.style_name_zh}</span>
    `;

    if (style.style_id === activeStyleId) button.classList.add("active");
    button.addEventListener("click", () => {
      activeStyleId = style.style_id;
      renderTabs();
      renderActiveStyle();
    });
    tabRow.appendChild(button);
  });
}

function renderAnnotations(styleId) {
  const annotations = STYLE_ANNOTATIONS[styleId] ?? STYLE_ANNOTATIONS.eclectic;
  return annotations
    .map(
      (item) => `
        <div class="style-annotation" style="left:${item.x}%; top:${item.y}%;">
          <span class="style-annotation-dot"></span>
          <span class="style-annotation-line"></span>
          <span class="style-annotation-label">${item.text}</span>
        </div>
      `
    )
    .join("");
}

function renderSurfaceRecommendations(items, categoryLabel) {
  if (!items?.length) {
    return `<p>尚未整理 ${categoryLabel} 推薦。</p>`;
  }

  return `
    <div class="surface-recommendation-list">
      ${items
        .map((item) => {
          const detailParts = [
            item.tone_zh ?? item.material_zh,
            item.finish_zh,
          ].filter(Boolean);

          return `
            <article class="surface-recommendation-item">
              <div class="surface-recommendation-head">
                <strong>${item.name_zh ?? "-"}</strong>
                ${detailParts.length ? `<span>${detailParts.join(" / ")}</span>` : ""}
              </div>
              <p>${item.why_zh ?? "適合作為該風格的延伸背景。"}</p>
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
      ${pairs.map((pair) => `<span class="style-chip">${pair}</span>`).join("")}
    </div>
  `;
}

function getSurfaceFallback(style) {
  return STYLE_SURFACE_FALLBACKS[style.style_id] ?? {
    wall_recommendations: [],
    floor_recommendations: [],
    recommended_wall_floor_pairs_zh: [],
  };
}

function renderStyleStage(style) {
  const colors = style.palette_hex?.length ? style.palette_hex : ["#f6f1e8", "#d8c8b0", "#a88a67"];
  const imageUrl = STYLE_IMAGE_MAP[style.style_id] ?? STYLE_IMAGE_MAP.eclectic;
  const count = style.stats?.matched_furniture_count ?? 0;

  return `
    <div class="style-stage" style="--tone-a:${colors[0]}; --tone-b:${colors[1] ?? colors[0]}; --tone-c:${colors[2] ?? colors[1] ?? colors[0]};">
      <img class="style-stage-image" src="${imageUrl}" alt="${style.style_name_zh} 風格示意圖" />
      <div class="style-stage-overlay"></div>
      <div class="style-stage-header">
        <span class="style-stage-label">STYLE VISUAL</span>
        <div class="badge-row">
          <span class="badge">${style.style_name_zh}</span>
          <span class="badge">${style.style_name_en}</span>
          <span class="badge">${count} 件家具</span>
        </div>
      </div>
      <div class="style-stage-title">
        <strong>${style.style_name_zh}</strong>
      </div>
      <div class="style-stage-annotation-layer">
        ${renderAnnotations(style.style_id)}
      </div>
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
  const topCount = style.stats?.matched_furniture_count ?? 0;
  const topTypes = (style.stats?.top_types ?? [])
    .slice(0, 4)
    .map(([typeName, count]) => `${typeName} ${count}`)
    .join(" / ");
  const surfaceFallback = getSurfaceFallback(style);
  const wallRecommendations = style.wall_recommendations?.length ? style.wall_recommendations : surfaceFallback.wall_recommendations;
  const floorRecommendations = style.floor_recommendations?.length ? style.floor_recommendations : surfaceFallback.floor_recommendations;
  const recommendedPairs = style.recommended_wall_floor_pairs_zh?.length
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
        <p>${formatList(style.keywords_zh)}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:80ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>主色</h3>
        <div class="swatch-row">
          ${(style.main_colors_zh ?? [])
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

      <article class="style-info-card style-enter" style="--delay:120ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>材質</h3>
        <p>${formatList(style.materials_zh)}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:160ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>造型特徵</h3>
        <p>${formatList(style.shape_features_zh)}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:200ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>不要的元素</h3>
        <p>${formatList(style.avoid_elements_zh)}</p>
      </article>

      <article class="style-info-card style-enter" style="--delay:240ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>空間背景</h3>
        <p>牆面：${style.scene_background?.wall_zh ?? "-"}</p>
        <p>地板：${style.scene_background?.floor_zh ?? "-"}</p>
        <p>整體：${style.scene_background?.overall_zh ?? "-"}</p>
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
        <p>主要家具類型：${topTypes || "尚未整理"}</p>
      </article>
    </div>
  `;
}

renderTabs();
renderActiveStyle();
initBackgroundFx();
