import { fetchSiteData, initBackgroundFx } from "./common.js";

const data = await fetchSiteData();

const workflowMeta = [
  {
    title: "輸入平面圖與需求文字",
    description: "讀取空間平面資訊與使用者指定的生活需求、動線與風格條件。",
    link: "/styles",
    linkLabel: "先看風格",
    icon: `
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <rect x="18" y="18" width="84" height="84" rx="18" fill="rgba(255,248,240,0.94)" />
        <rect x="32" y="34" width="56" height="42" rx="8" fill="none" stroke="#7c6553" stroke-width="4"/>
        <path d="M44 80h32" stroke="#7c6553" stroke-width="4" stroke-linecap="round"/>
        <path d="M40 48h40M40 60h22" stroke="#c2916b" stroke-width="4" stroke-linecap="round"/>
      </svg>
    `,
  },
  {
    title: "依風格規則挑選家具",
    description: "由資料庫中的家具尺寸、材質與風格分類，挑出最適合空間的候選模型。",
    link: "/library",
    linkLabel: "看家具庫",
    icon: `
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <rect x="18" y="18" width="84" height="84" rx="18" fill="rgba(255,248,240,0.94)" />
        <rect x="25" y="56" width="70" height="24" rx="10" fill="#d3b08e"/>
        <rect x="28" y="42" width="24" height="20" rx="10" fill="#ead7c3"/>
        <rect x="68" y="42" width="24" height="20" rx="10" fill="#ead7c3"/>
        <path d="M36 80v14M84 80v14" stroke="#7c6553" stroke-width="4" stroke-linecap="round"/>
      </svg>
    `,
  },
  {
    title: "輸出可瀏覽的 3D 場景",
    description: "將配置結果輸出到網頁端，使用 Three.js 直接呈現空間與家具配置成果。",
    link: "/scene",
    linkLabel: "看 3D 頁",
    icon: `
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <rect x="18" y="18" width="84" height="84" rx="18" fill="rgba(255,248,240,0.94)" />
        <path d="M60 30 87 46v30L60 92 33 76V46z" fill="none" stroke="#7c6553" stroke-width="4" stroke-linejoin="round"/>
        <path d="M60 30v62M33 46l27 16 27-16" stroke="#c2916b" stroke-width="4" stroke-linejoin="round"/>
      </svg>
    `,
  },
];

document.getElementById("project-subtitle").textContent = data.project.subtitle;
document.getElementById("metric-furniture").textContent = String(data.summary.total_furniture ?? "-");
document.getElementById("metric-styles").textContent = String(data.styles.length);

const scopeList = document.getElementById("scope-list");
workflowMeta.forEach((item, index) => {
  const card = document.createElement("article");
  card.className = `home-flow-card home-flow-tone-${index + 1}`;
  card.innerHTML = `
    <div class="home-flow-icon">${item.icon}</div>
    <div class="home-flow-copy">
      <span class="scope-index">0${index + 1}</span>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
      <a class="button-link" href="${item.link}">${item.linkLabel}</a>
    </div>
  `;
  scopeList.appendChild(card);
});

initBackgroundFx();
