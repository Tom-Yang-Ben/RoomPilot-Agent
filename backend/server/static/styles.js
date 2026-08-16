import { fetchStylesData, initBackgroundFx } from "./common.js?v=sha256-7df895e56814";

const data = await fetchStylesData();
const tabRow = document.getElementById("style-tab-row");
const taiwanStyleGallery = document.getElementById("taiwan-style-gallery");
const taiwanStyleCards = data.taiwan_style_cards || [];
const STYLE_CARD_STORAGE_KEY = "roompilot:selectedStyleCard";
const STYLE_CARD_PALETTE_LABELS = {
  japanese_2: ["榻榻米", "竹青", "胡桃木", "茶褐"],
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
  japanese_1:
    "侘寂自然重視不完美的痕跡，米灰牆面、粗陶器皿與低彩度木色會讓空間慢下來。適合喜歡安靜、手作感與留白的人。",
  japanese_2:
    "榻榻米、茶席與低家具把生活高度放低，胡桃木與竹青色讓空間有沉靜的禪意。適合想要閱讀、品茶、盤腿坐下來放鬆的日式角落。",
  japanese_3:
    "現代和風把日式木格柵、留白牆面與深色線條收得更俐落。它不像傳統和室那麼濃，而是適合都會住宅的安靜、克制與溫潤。",
  cream_1:
    "奶油米白把北歐風變得更柔軟，搭配淺木與圓角家具，能讓客廳有被陽光包住的感覺。適合想要明亮、溫柔、不壓迫的家。",
  cream_2:
    "法式柔霧把灰粉、霧面白與細緻曲線放在一起，氛圍比北歐更優雅。適合喜歡柔和線條、拱形元素與輕盈布料的人。",
  cream_3:
    "奶茶色像午後拿鐵一樣柔和，搭配圓弧沙發、霧面木皮與米白布料，讓家裡有溫柔的生活感；適合想要乾淨、暖心但不過度甜美的客廳。",
  industrial_1:
    "黑鐵、水泥與皮革色讓空間帶有倉庫感，但比例要乾淨才不會厚重。適合喜歡開放層架、金屬細節與俐落家具的人。",
  industrial_2:
    "復古工坊用舊木、焦糖皮革和暖黃燈光增加故事感，像有人長期使用過的工作室。適合收藏、書籍、音響或手作工具能被看見的空間。",
  industrial_3:
    "極簡冷調把工業風收斂成黑、灰、金屬與乾淨直線，少了粗獷，多了都會感。適合想要冷靜、俐落、帶一點科技感的住宅。",
  american_1:
    "鄉村溫馨用暖木、手感織品與低彩度牆面堆出安定感，像假日午後的慢生活。適合喜歡木桌、藤編、陶器與柔和燈光的人。",
  american_2:
    "經典優雅保留侘寂的安靜，但把線條整理得更端正。深木、米灰與少量深色能讓空間成熟耐看，適合沉穩、有儀式感的客廳。",
  american_3:
    "現代輕奢把侘寂的樸素感加上細緻金屬與深色家具，氣氛安靜但更有質感。適合想要低調、乾淨，又希望空間有一點精緻度的人。",
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
























renderTabs();
renderTaiwanStyleGallery();
initBackgroundFx();
