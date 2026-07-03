import { fetchSiteData, initBackgroundFx, styleNameMap, formatSize } from "./common.js?v=20260703c";
import { createViewer } from "./viewer.js?v=20260703c";

const data = await fetchSiteData();
const styleNames = styleNameMap(data.styles);

const elements = {
  sceneStyleChips: document.getElementById("scene-style-chips"),
  viewerTitle: document.getElementById("viewer-title"),
  viewerStyle: document.getElementById("viewer-style"),
  viewerType: document.getElementById("viewer-type"),
  viewerSize: document.getElementById("viewer-size"),
  viewerStatus: document.getElementById("viewer-status"),
  viewerCanvas: document.getElementById("viewer-canvas"),
  resetViewer: document.getElementById("reset-viewer"),
  spinModel: document.getElementById("spin-model"),
};

const viewer = createViewer(elements.viewerCanvas, elements.viewerStatus);
let spinEnabled = false;

function formatStyleName(styleId) {
  return styleNames.get(styleId) || styleId || "未分類";
}

function setFurniture(item) {
  elements.viewerTitle.textContent = item.name_zh_raw || item.name_en || "未命名家具";
  elements.viewerStyle.textContent = formatStyleName(item.primary_style);
  elements.viewerType.textContent = item.normalized_type ?? "-";
  elements.viewerSize.textContent = formatSize(item.size_cm);

  if (item.has_model) {
    viewer.load(item.model_url);
  } else {
    elements.viewerStatus.textContent = item.missing_model_reason;
  }
}

data.styles.forEach((style) => {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = style.style_name_zh;
  chip.addEventListener("click", () => {
    const target = style.representative_furniture.find((item) => item.has_model);
    if (target) {
      setFurniture(target);
    } else {
      elements.viewerStatus.textContent = "這個風格目前代表家具都缺少可用 GLB。";
    }
  });
  elements.sceneStyleChips.appendChild(chip);
});

elements.resetViewer.addEventListener("click", () => viewer.resetCamera());
elements.spinModel.addEventListener("click", () => {
  spinEnabled = viewer.toggleSpin();
  elements.spinModel.textContent = spinEnabled ? "停止旋轉" : "模型旋轉展示";
});

const firstAvailable = data.styles
  .flatMap((style) => style.representative_furniture)
  .find((item) => item.has_model);

if (firstAvailable) {
  setFurniture(firstAvailable);
}

initBackgroundFx();
