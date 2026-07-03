import { fetchSiteData, formatList, formatSize, initBackgroundFx, styleNameMap } from "./common.js";

const data = await fetchSiteData();
const names = styleNameMap(data.styles);
const tabRow = document.getElementById("style-tab-row");
const detailPanel = document.getElementById("style-detail-panel");
const furniturePanel = document.getElementById("style-furniture-panel");
const sidePanel = document.getElementById("style-side-panel");

let activeStyleId = data.styles[0]?.style_id ?? null;

function modelBadge(item) {
  return item.has_model
    ? '<span class="badge success">GLB 可看</span>'
    : '<span class="badge warning">缺 GLB</span>';
}

function getFallbackRepresentativeFurniture(style) {
  return data.furniture
    .filter((item) => item.primary_style === style.style_id)
    .slice(0, 8)
    .map((item) => ({
      ...item,
      card_image_url: null,
    }));
}

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
    button.addEventListener("click", () => {
      activeStyleId = style.style_id;
      renderTabs();
      renderActiveStyle();
    });
    if (style.style_id === activeStyleId) {
      button.classList.add("active");
    }
    tabRow.appendChild(button);
  });
}

function renderGeneratedStyleStage(style) {
  const colors = style.palette_hex?.length ? style.palette_hex : ["#f6f1e8", "#d8c8b0", "#a88a67"];
  const keywords = (style.keywords_zh ?? []).slice(0, 4);
  return `
    <div class="style-stage" style="--tone-a:${colors[0]}; --tone-b:${colors[1] ?? colors[0]}; --tone-c:${colors[2] ?? colors[1] ?? colors[0]};">
      <div class="style-stage-glow"></div>
      <div class="style-stage-room">
        <div class="style-stage-wall"></div>
        <div class="style-stage-floor"></div>
        <div class="style-stage-block stage-sofa"></div>
        <div class="style-stage-block stage-table"></div>
        <div class="style-stage-block stage-lamp"></div>
      </div>
      <div class="style-stage-copy">
        <span class="style-stage-label">LIVE STYLE BOARD</span>
        <strong>${style.style_name_zh}</strong>
        <p>${style.scene_background?.overall_zh ?? ""}</p>
      </div>
      <div class="style-stage-tags">
        ${keywords.map((keyword) => `<span>${keyword}</span>`).join("")}
      </div>
    </div>
  `;
}

function renderRepresentativeCard(item, panelFill, panelOutline, titleColor, bodyColor) {
  return `
    <article class="representative-card elevated">
      ${
        item.card_image_url
          ? `<img src="${item.card_image_url}" alt="${item.name_zh_raw || item.name_en}" />`
          : `<div class="furniture-fallback-box">${item.normalized_type ?? "furniture"}</div>`
      }
      <div class="badge-row">
        ${modelBadge(item)}
        <span class="badge">${names.get(item.primary_style) || item.primary_style}</span>
      </div>
      <h4>${item.name_zh_raw || item.name_en}</h4>
      <p class="muted">${item.name_en || ""}</p>
      <div class="meta-list">
        <div><strong>類型：</strong>${item.normalized_type ?? "-"}</div>
        <div><strong>尺寸：</strong>${formatSize(item.size_cm)}</div>
      </div>
      ${
        item.has_model
          ? `<a class="button-link strong-link" href="/library">到資料庫頁看模型</a>`
          : `<p class="muted">${item.missing_model_reason ?? "目前沒有可用 GLB"}</p>`
      }
    </article>
  `;
}

function renderActiveStyle() {
  const style = data.styles.find((item) => item.style_id === activeStyleId);
  if (!style) return;

  const topCount = style.stats?.matched_furniture_count ?? 0;
  const topTypes = (style.stats?.top_types ?? [])
    .slice(0, 4)
    .map(([typeName, count]) => `${typeName} ${count}`)
    .join(" / ");
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

  sidePanel.style.setProperty("--panel-fill", panelFill);
  sidePanel.style.setProperty("--panel-outline", panelOutline);
  sidePanel.style.setProperty("--title-color", titleColor);
  sidePanel.style.setProperty("--body-color", bodyColor);
  sidePanel.style.setProperty("--accent-fill", accentFill);

  detailPanel.innerHTML = `
    <div class="style-hero-card style-enter" style="--panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor}; --accent-fill:${accentFill};">
      ${renderGeneratedStyleStage(style)}
      <div class="style-hero-meta">
        <div class="badge-row">
          <span class="badge">${style.style_name_zh}</span>
          <span class="badge">${style.style_name_en}</span>
          <span class="badge">${topCount} 件家具</span>
        </div>
        <h2>${style.style_name_zh}</h2>
        <p class="style-lead">${style.core_description_zh ?? ""}</p>
      </div>
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
      <article class="style-info-card wide style-enter" style="--delay:280ms; --panel-fill:${panelFill}; --panel-outline:${panelOutline}; --title-color:${titleColor}; --body-color:${bodyColor};">
        <h3>目前資料庫對應狀況</h3>
        <p>家具數量：${topCount}</p>
        <p>主要家具類型：${topTypes || "尚未整理"}</p>
      </article>
    </div>
  `;

  furniturePanel.innerHTML = "";
  const representativeFurniture =
    style.representative_furniture?.length > 0 ? style.representative_furniture : getFallbackRepresentativeFurniture(style);

  if (!representativeFurniture.length) {
    furniturePanel.innerHTML = `
      <section class="style-furniture-group style-enter">
        <div class="style-furniture-empty">
          <strong>目前尚未整理出這個風格的代表家具卡。</strong>
          <p>可以先到家具資料庫頁查看同風格的完整清單。</p>
          <a class="button-link strong-link" href="/library">前往家具資料庫</a>
        </div>
      </section>
    `;
    return;
  }

  const groupedFurniture = new Map();
  representativeFurniture.forEach((item) => {
    const groupName = item.normalized_type || "other";
    if (!groupedFurniture.has(groupName)) {
      groupedFurniture.set(groupName, []);
    }
    groupedFurniture.get(groupName).push(item);
  });

  [...groupedFurniture.entries()].forEach(([groupName, items], groupIndex) => {
    const groupBlock = document.createElement("section");
    groupBlock.className = "style-furniture-group style-enter";
    groupBlock.style.setProperty("--delay", `${80 + groupIndex * 60}ms`);
    groupBlock.innerHTML = `
      <div class="style-furniture-group-heading">
        <h3>${groupName}</h3>
        <span>${items.length} 件</span>
      </div>
      <div class="style-furniture-group-grid">
        ${items
          .map((item) => renderRepresentativeCard(item, panelFill, panelOutline, titleColor, bodyColor))
          .join("")}
      </div>
    `;
    furniturePanel.appendChild(groupBlock);
  });
}

renderTabs();
renderActiveStyle();
initBackgroundFx();
