import { fetchSiteData, initBackgroundFx } from "./common.js?v=20260705f";

const workflowMeta = [
  {
    title: "上傳平面圖",
    description: "匯入 DXF 或平面圖資訊，作為後續牆面、空間尺寸與家具配置的基礎。",
    iconClass: "upload-step",
  },
  {
    title: "選擇風格條件",
    description: "從 12 種室內風格中挑選方向，也能指定牆面、地板、色系與個人偏好。",
    iconClass: "palette-step",
  },
  {
    title: "挑選家具需求",
    description: "勾選沙發、茶几、電視櫃、床、書櫃等需求，讓系統知道要配置哪些家具。",
    iconClass: "chair-step",
  },
  {
    title: "AI 自動配置",
    description: "LLM 將問卷整理成配置 JSON，再依尺寸、風格與可用 GLB 模型挑選家具。",
    iconClass: "ai-step",
  },
  {
    title: "生成 3D 場景",
    description: "使用 Three.js 輸出可瀏覽的 3D 室內空間，方便展示與後續調整。",
    iconClass: "scene-step",
  },
];

const data = await fetchSiteData();
const furnitureMetric = document.getElementById("metric-furniture");
if (furnitureMetric) {
  furnitureMetric.textContent = String(data.summary.total_furniture ?? "-");
}

const scopeList = document.getElementById("scope-list");
if (scopeList) {
  workflowMeta.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "home-flow-step";
    card.innerHTML = `
      <span class="home-step-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="home-step-icon ${item.iconClass}" aria-hidden="true"></span>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
    `;
    scopeList.appendChild(card);
  });
}

initBackgroundFx();
