const elements = {
  form: document.querySelector("#rag-search-form"),
  query: document.querySelector("#rag-query"),
  count: document.querySelector("#rag-query-count"),
  submit: document.querySelector("#rag-submit"),
  error: document.querySelector("#rag-form-error"),
  loading: document.querySelector("#rag-loading"),
  progressStage: document.querySelector("#rag-progress-stage"),
  progressPercent: document.querySelector("#rag-progress-percent"),
  progressTrack: document.querySelector("#rag-progress-track"),
  progressFill: document.querySelector("#rag-progress-fill"),
  progressMessage: document.querySelector("#rag-progress-message"),
  progressElapsed: document.querySelector("#rag-progress-elapsed"),
  results: document.querySelector("#rag-results"),
  summary: document.querySelector("#rag-result-summary"),
  clarification: document.querySelector("#rag-clarification"),
  blocks: document.querySelector("#rag-result-blocks"),
  debug: document.querySelector("#rag-debug-json"),
  readyBadge: document.querySelector("#rag-ready-badge"),
  stages: document.querySelector("#rag-stage-list"),
  statusNote: document.querySelector("#rag-status-note"),
  refreshStatus: document.querySelector("#rag-refresh-status"),
};

let activeRequest = null;

function createElement(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = text;
  return node;
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function formatCurrency(value) {
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0
    ? `NT$ ${new Intl.NumberFormat("zh-TW").format(amount)}`
    : "價格未提供";
}

function formatMilliseconds(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? `${amount.toLocaleString("zh-TW")} ms` : "—";
}

function formatElapsed(value) {
  const totalSeconds = Math.max(0, Math.round(Number(value || 0) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes ? `已等待 ${minutes} 分 ${seconds} 秒` : `已等待 ${seconds} 秒`;
}

function progressStageLabel(stage) {
  return {
    queued: "等待執行",
    starting: "啟動 RAG",
    readiness: "檢查服務",
    parsing: "解析自然語言",
    planning: "規劃品項與預算",
    embedding: "產生 BGE-M3 向量",
    vector_search: "PostgreSQL 向量檢索",
    reranking: "Django reranker 排序",
    hydrating: "讀取正式家具資料",
    formatting: "整理檢索結果",
    completed: "搜尋完成",
    failed: "搜尋失敗",
  }[stage] || "處理中";
}

function updateProgress(job = {}) {
  const percent = Math.max(0, Math.min(100, Math.round(Number(job.progress || 0))));
  elements.progressStage.textContent = progressStageLabel(job.stage);
  elements.progressPercent.textContent = `${percent}%`;
  elements.progressFill.style.width = `${percent}%`;
  elements.progressTrack.setAttribute("aria-valuenow", String(percent));
  elements.progressMessage.textContent = job.message || "RAG 搜尋處理中。";
  elements.progressElapsed.textContent = formatElapsed(job.elapsed_ms);
}

function pollDelay(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function waitForJob(initialJob, requestController) {
  let job = initialJob;
  while (true) {
    updateProgress(job);
    if (job.status === "completed") return job.result;
    if (job.status === "failed") {
      throw new Error(job.error?.message || "RAG 搜尋失敗。");
    }
    await pollDelay(750, requestController.signal);
    const response = await fetch(
      `/api/rag/search/jobs/${encodeURIComponent(job.job_id)}`,
      { cache: "no-store", signal: requestController.signal },
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail?.message || `RAG progress failed (${response.status})`);
    }
    job = payload;
  }
}

function appendChip(host, text) {
  host.append(createElement("span", "rag-chip", text));
}

function stage(label, ok, detail) {
  const row = createElement("div", `rag-stage${ok ? " is-ok" : ""}`);
  row.append(createElement("span", "rag-stage-dot"));
  row.append(createElement("strong", "", label));
  row.append(createElement("small", "", detail));
  return row;
}

function renderStatus(status) {
  elements.stages.replaceChildren();
  const parser = status.parser || {};
  const models = status.models || {};
  const database = status.database || {};
  const packagesReady = Object.values(models.packages || {}).every(Boolean);

  elements.stages.append(
    stage(`${parser.provider === "anthropic" ? "Anthropic" : "OpenAI"} 解析`, parser.key_configured && parser.package_available, parser.model || "未設定"),
    stage("BGE-M3", packagesReady && models.embedding_cached, models.loaded ? `已載入 · ${models.device}` : "lazy load"),
    stage("Reranker", packagesReady && models.reranker_cached, models.reranker_model || "未快取"),
    stage("PostgreSQL", database.available && database.search_function_available, `${Number(database.current_embeddings || 0).toLocaleString("zh-TW")} vectors`),
  );

  elements.readyBadge.className = `rag-ready-badge ${status.ready ? "is-ready" : "is-blocked"}`;
  elements.readyBadge.textContent = status.ready ? "READY" : "NOT READY";
  elements.statusNote.textContent = status.ready
    ? "完整檢索鏈已就緒；大型模型會在第一次查詢時載入。"
    : `尚缺：${(status.blockers || []).join("、") || "無法取得狀態"}`;
  elements.submit.disabled = !status.ready;
}

async function refreshStatus() {
  elements.refreshStatus.disabled = true;
  try {
    const response = await fetch("/api/rag/status", { cache: "no-store" });
    if (!response.ok) throw new Error("status_unavailable");
    renderStatus(await response.json());
  } catch {
    renderStatus({ ready: false, blockers: ["status_unavailable"], parser: {}, models: {}, database: {} });
  } finally {
    elements.refreshStatus.disabled = false;
  }
}

function renderClarification(clarification) {
  elements.clarification.replaceChildren();
  if (!clarification?.needed) return;
  const card = createElement("div", "rag-clarification-card");
  card.append(createElement("p", "", clarification.question || "需要補充哪些條件？"));
  const options = createElement("div", "rag-examples");
  for (const option of clarification.options || []) {
    const button = createElement("button", "", option);
    button.type = "button";
    button.addEventListener("click", () => {
      elements.query.value = `${elements.query.value.trim()}，${option}`;
      updateCount();
      elements.form.requestSubmit();
    });
    options.append(button);
  }
  card.append(options);
  elements.clarification.append(card);
}

function filterLabel(key, value) {
  const labels = {
    room_type: "房型",
    categories: "類別",
    price_min: "最低價",
    price_max: "最高價",
    max_width_cm: "最大寬",
    max_height_cm: "最大高",
    role: "角色",
    size_class: "尺寸級距",
  };
  if (Array.isArray(value)) return `${labels[key] || key}：${value.join("、")}`;
  if (["price_min", "price_max"].includes(key)) return `${labels[key]}：${formatCurrency(value)}`;
  if (["max_width_cm", "max_height_cm"].includes(key)) return `${labels[key]}：${value} cm`;
  return `${labels[key] || key}：${value}`;
}

function furnitureCard(hit) {
  const furniture = hit.furniture || {};
  const card = createElement("article", "rag-furniture-card");
  const imageHost = createElement("div", "rag-card-image");
  const imageUrl = safeHttpUrl(furniture.image_url);
  if (imageUrl) {
    const image = createElement("img");
    image.src = imageUrl;
    image.alt = furniture.name_zh || "家具圖片";
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    imageHost.append(image);
  } else {
    imageHost.textContent = "NO PREVIEW";
  }

  const body = createElement("div", "rag-card-body");
  body.append(createElement("span", "rag-card-rank", `RANK ${hit.rank}`));
  body.append(createElement("h4", "", furniture.name_zh || furniture.item_id || "未命名家具"));
  body.append(createElement("p", "rag-price", formatCurrency(furniture.price_twd)));

  const metadata = createElement("div", "rag-furniture-meta");
  appendChip(metadata, furniture.category || "未分類");
  if (furniture.style_primary) appendChip(metadata, furniture.style_primary);
  const dimensions = [furniture.width_cm, furniture.depth_cm, furniture.height_cm];
  if (dimensions.every((value) => value != null)) {
    appendChip(metadata, `${dimensions.join(" × ")} cm`);
  }
  body.append(metadata);

  const scores = createElement("div", "rag-score-row");
  appendChip(scores, `FINAL ${Number(hit.scores?.final || 0).toFixed(3)}`);
  appendChip(scores, `RR ${Number(hit.scores?.rerank || 0).toFixed(3)}`);
  appendChip(scores, `STYLE ${Number(hit.scores?.style || 0).toFixed(2)}`);
  appendChip(scores, `MOOD ${Number(hit.scores?.mood || 0).toFixed(2)}`);
  body.append(scores);
  card.append(imageHost, body);
  return card;
}

function renderBlock(block) {
  const section = createElement("section", "rag-block");
  const heading = createElement("div", "rag-block-heading");
  const copy = createElement("div");
  copy.append(createElement("p", "rag-kicker", `${block.item_id} · ${block.category_group || "semantic only"}`));
  copy.append(createElement("h3", "", block.label_zh));
  copy.append(createElement("p", "", `${block.quantity} 件${block.is_inferred ? " · 系統推測品項" : " · 使用者指定"}`));
  heading.append(copy);
  if (block.price_cap) heading.append(createElement("span", "rag-source-pill", `上限 ${formatCurrency(block.price_cap)}`));
  section.append(heading);

  const filters = createElement("div", "rag-filter-list");
  for (const [key, value] of Object.entries(block.filters || {})) {
    if (value == null || (Array.isArray(value) && value.length === 0)) continue;
    appendChip(filters, filterLabel(key, value));
  }
  if (filters.childElementCount) section.append(filters);

  if (!block.hits?.length) {
    section.append(createElement("p", "rag-empty", "目前硬條件下沒有可用家具；請放寬尺寸、價格或類別後再試。"));
    return section;
  }
  const grid = createElement("div", "rag-card-grid");
  for (const hit of block.hits) grid.append(furnitureCard(hit));
  section.append(grid);
  return section;
}

function renderResults(payload) {
  elements.summary.replaceChildren();
  elements.blocks.replaceChildren();
  const heading = createElement("div", "rag-summary-heading");
  const copy = createElement("div");
  copy.append(createElement("p", "rag-kicker", "RETRIEVAL EVIDENCE"));
  copy.append(createElement("h2", "", `${payload.style_zh || payload.dominant_style || "語意"}檢索結果`));
  heading.append(copy, createElement("span", "rag-source-pill", payload.source?.vector_store || "postgresql_pgvector"));
  elements.summary.append(heading);

  const meta = createElement("div", "rag-summary-meta");
  appendChip(meta, `${Number(payload.source?.current_embeddings || 0).toLocaleString("zh-TW")} vectors`);
  appendChip(meta, `總耗時 ${formatMilliseconds(payload.timings_ms?.total)}`);
  appendChip(meta, `解析 ${formatMilliseconds(payload.timings_ms?.parse)}`);
  appendChip(meta, `檢索排序 ${formatMilliseconds(payload.timings_ms?.retrieve_and_rerank)}`);
  if (payload.budget_total) appendChip(meta, `預算 ${formatCurrency(payload.budget_total)}`);
  appendChip(meta, `首選估價 ${formatCurrency(payload.estimated_total)}`);
  elements.summary.append(meta);

  renderClarification(payload.clarification);
  for (const block of payload.blocks || []) elements.blocks.append(renderBlock(block));
  elements.debug.textContent = JSON.stringify({
    source: payload.source,
    parsed_query: payload.parsed_query,
    parser_usage: payload.parser_usage,
    timings_ms: payload.timings_ms,
    boundary: payload.boundary,
  }, null, 2);
  elements.results.hidden = false;
}

function updateCount() {
  elements.count.textContent = `${elements.query.value.length} / 1000`;
}

async function submitSearch(event) {
  event.preventDefault();
  const query = elements.query.value.trim();
  if (!query) {
    elements.error.textContent = "請先輸入家具需求。";
    elements.query.focus();
    return;
  }
  activeRequest?.abort();
  const requestController = new AbortController();
  activeRequest = requestController;
  elements.error.textContent = "";
  elements.results.hidden = true;
  elements.loading.hidden = false;
  elements.submit.disabled = true;
  updateProgress({
    progress: 0,
    stage: "queued",
    message: "建立背景搜尋工作。",
    elapsed_ms: 0,
  });

  try {
    const response = await fetch("/api/rag/search/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 8 }),
      signal: requestController.signal,
    });
    const job = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(job.detail?.message || `RAG request failed (${response.status})`);
    const payload = await waitForJob(job, requestController);
    renderResults(payload);
  } catch (error) {
    if (error.name !== "AbortError") elements.error.textContent = error.message || "RAG 檢索失敗。";
  } finally {
    if (activeRequest === requestController) {
      elements.loading.hidden = true;
      elements.submit.disabled = false;
    }
  }
}

elements.form.addEventListener("submit", submitSearch);
elements.query.addEventListener("input", updateCount);
elements.refreshStatus.addEventListener("click", refreshStatus);
for (const button of document.querySelectorAll("[data-example]")) {
  button.addEventListener("click", () => {
    elements.query.value = button.dataset.example || "";
    updateCount();
    elements.query.focus();
  });
}

updateCount();
refreshStatus();
