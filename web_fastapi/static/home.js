import { fetchSiteData, initBackgroundFx } from "./common.js?v=20260705f";

const workflowMeta = [
  {
    title: "2D 平面圖上傳",
    description: "匯入 DXF 或平面圖資訊，作為後續牆面、空間尺寸與家具配置的基礎。",
    iconClass: "upload-step",
  },
  {
    title: "12 種風格條件",
    description: "從 12 種室內風格中挑選方向，也能指定牆面、地板、色系與個人偏好。",
    iconClass: "palette-step",
  },
  {
    title: "GLB 家具資料庫",
    description: "從既有可載入家具模型中挑選候選，並依風格限制縮小成可配置的組合。",
    iconClass: "chair-step",
  },
  {
    title: "LLM 配置規劃",
    description: "LLM 會把需求整理成配置 JSON，再交給後端挑家具、排版並檢查限制。",
    iconClass: "ai-step",
  },
  {
    title: "3D 場景預覽",
    description: "使用 Three.js 輸出可瀏覽的 3D 室內空間，方便展示、旋轉查看與後續調整。",
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
    card.dataset.flowIndex = String(index);
    card.innerHTML = `
      <span class="home-step-number">${String(index + 1).padStart(2, "0")}</span>
      <span class="home-step-icon ${item.iconClass}" aria-hidden="true"></span>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
    `;
    scopeList.appendChild(card);
  });
}

const flowSteps = Array.from(document.querySelectorAll(".home-flow-step"));
const featureCards = Array.from(document.querySelectorAll(".home-feature-strip article"));

function setActiveFlowIndex(index) {
  flowSteps.forEach((step, stepIndex) => {
    step.classList.toggle("is-highlighted", stepIndex === index);
  });
  featureCards.forEach((card, cardIndex) => {
    card.classList.toggle("is-linked-active", cardIndex === index);
  });
}

function clearActiveFlowIndex() {
  flowSteps.forEach((step) => step.classList.remove("is-highlighted"));
  featureCards.forEach((card) => card.classList.remove("is-linked-active"));
}

featureCards.forEach((card, index) => {
  card.dataset.flowIndex = String(index);
  card.tabIndex = 0;
  card.addEventListener("mouseenter", () => setActiveFlowIndex(index));
  card.addEventListener("focus", () => setActiveFlowIndex(index));
  card.addEventListener("mouseleave", clearActiveFlowIndex);
  card.addEventListener("blur", clearActiveFlowIndex);
});

initBackgroundFx();
