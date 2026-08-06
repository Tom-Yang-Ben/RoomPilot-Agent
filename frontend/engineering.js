// 接管 window.fetch 以附加身分；成果報告端點全部需要登入。
import {
  authorizedObjectUrl,
  downloadAuthorized,
  getCurrentUser,
  requireSignedIn,
} from "./auth_client.js?v=sha256-b35a4ff11b37";
// geometry_core.js 零依賴，不屬於 scene 模組鏈——所以成果報告頁共用它不會被綁進
// scene 的相依圖。這是這裡不自己再寫一份射線法的原因。
import { pointInPolygon } from "./geometry_core.js?v=sha256-9f5b24aab5dd";

const $ = (selector) => document.querySelector(selector);

const state = {
  projectId: new URLSearchParams(location.search).get("project_id"),
  project: null,
  renders: [],
  snapshot: null,
  completeness: null,
  report: null,
  health: null,
};

const APPLIANCE_TYPES = new Set([
  "refrigerator", "washer", "washing-machine", "washing_machine", "dishwasher",
  "dryer", "oven", "microwave", "range-hood", "air-conditioner", "air_conditioner",
  "ceiling-cassette", "appliance",
]);

function errorMessage(error) {
  const detail = error?.detail;
  if (detail && typeof detail === "object") {
    return `${detail.error_code || detail.code || "ERROR"}：${detail.message || JSON.stringify(detail)}`;
  }
  return error?.message || String(error || "發生未預期錯誤");
}

async function api(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("json") ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(typeof body === "string" ? body : JSON.stringify(body));
    error.status = response.status;
    error.detail = body?.detail || body;
    throw error;
  }
  return body;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null));
}

function finite(value, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function normalizedPoint(point = {}) {
  return {
    x_cm: finite(point.x_cm ?? point.x),
    y_cm: finite(point.y_cm ?? point.y ?? point.z),
  };
}

function polygonBounds(points) {
  const normalized = (points || []).map(normalizedPoint);
  if (normalized.length < 3) return null;
  const xs = normalized.map((point) => point.x_cm);
  const ys = normalized.map((point) => point.y_cm);
  return {
    points: normalized,
    minX: Math.min(...xs), maxX: Math.max(...xs),
    minY: Math.min(...ys), maxY: Math.max(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    depth: Math.max(...ys) - Math.min(...ys),
  };
}

// geometry_core 只認 { x, y }。本檔的平面座標一律是 { x_cm, y_cm }——`bounds.points`
// 會原樣進 payload（見 polygon_cm），欄位名受 AGENTS.md 的公分契約約束不能改，
// 所以在呼叫邊界轉，不動 schema。
function planXY(point) {
  return { x: point.x_cm, y: point.y_cm };
}

function explicitOpeningAreaM2(structures = {}, roomId, singleRoom) {
  return [...(structures.doors || []), ...(structures.windows || [])].reduce((sum, item) => {
    const openingRoomId = item.room_id || item.roomId || null;
    if (!singleRoom && String(openingRoomId || "") !== String(roomId)) return sum;
    const start = item.start || {};
    const end = item.end || {};
    const widthCm = finite(item.width_cm, Math.hypot(
      finite(end.x) - finite(start.x),
      finite(end.y ?? end.z) - finite(start.y ?? start.z),
    ));
    const explicitHeight = finite(
      item.height_cm,
      Number.isFinite(Number(item.top_cm)) && Number.isFinite(Number(item.bottom_cm))
        ? Number(item.top_cm) - Number(item.bottom_cm)
        : 0,
    );
    return explicitHeight > 0 ? sum + (widthCm * explicitHeight) / 10000 : sum;
  }, 0);
}

function normalizeEquipmentType(value) {
  const type = String(value || "appliance").toLowerCase().replaceAll("-", "_");
  const aliases = { washer: "washing_machine", washingmachine: "washing_machine", airconditioner: "air_conditioner" };
  return aliases[type] || type;
}

function materialSelections(surface = {}, requirement = {}) {
  const surfaces = requirement.surfaces || {};
  const candidates = [
    {
      part: "floor",
      id: surface.floor_material_id || surfaces.floor?.materialId,
      description: surfaces.floor?.color || surface.floor_color_hex,
      waste: 0.08,
    },
    {
      part: "wall",
      id: surface.wall_material_id || surfaces.wallDefault?.materialId,
      description: surfaces.wallDefault?.color || surface.wall_color_hex,
      waste: 0.05,
    },
    {
      part: "ceiling",
      id: surface.ceiling_material_id || surfaces.ceiling?.materialId,
      description: surfaces.ceiling?.styleId || surface.ceiling_style_id,
      waste: 0.05,
    },
  ];
  return candidates.filter((item) => item.id).map((item) => ({
    material_id: String(item.id),
    part: item.part,
    name: String(item.id),
    description: item.description ? String(item.description) : null,
    waste_rate: item.waste,
  }));
}

function renderReferencesForRoom(room, workflow, renders) {
  const jobs = workflow.proposal_review?.jobs || [];
  const matches = jobs.filter((job) => String(job.room_id || job.roomId || "") === String(room.id));
  const refs = matches.map((job, index) => ({
    render_url: job.image_url || job.output_url || job.preview_url,
    view_name: job.label || `${room.label || room.name || room.id} 生圖 ${index + 1}`,
    render_id: job.render_id || job.job_id || null,
    prompt_hash: job.prompt_hash || null,
  })).filter((item) => item.render_url);
  if (refs.length || renders.length === 0) return refs;
  // render_outputs 已落地 room_id（2026-08-06）：jobs 遺失時多房專案也能逐房回查；
  // 舊紀錄沒有 room_id，維持只有單房專案才回退整包 render history 的原規則。
  const roomRenders = renders.filter((render) => String(render.room_id || "") === String(room.id));
  const pool = roomRenders.length
    ? roomRenders
    : ((workflow.space_confirmation?.rooms || []).length === 1 ? renders : []);
  return pool.map((render, index) => ({
    render_url: `/api/projects/${encodeURIComponent(render.project_id)}/renders/${encodeURIComponent(render.render_id)}/png`,
    view_name: render.filename || `專案生圖 ${index + 1}`,
    render_id: render.render_id,
    prompt_hash: render.prompt_hash || null,
  }));
}

export function buildProjectSnapshot(project, renders = []) {
  const workflow = project.workflow || {};
  const roomState = workflow.space_confirmation || {};
  const rooms = roomState.rooms || [];
  if (!rooms.length) throw new Error("目前 project state 沒有已確認房間，無法建立 ProjectSnapshot。");
  const scene = workflow.white_model_3d?.sceneData || {};
  const floorplan = scene.floorplan || workflow.confirmed_floorplan?.floorplan || workflow.confirmed_floorplan || null;
  const roomRequirements = workflow.requirements?.roomRequirementModel?.roomRequirements
    || scene.room_requirements || scene.questionnaire?.room_requirements || {};
  const surfaces = scene.room_surface_assignments || scene.surface_overrides || [];
  const surfaceByRoom = new Map(surfaces.map((item) => [String(item.room_id), item]));
  const layoutFurniture = workflow.layout_2d?.furniture || [];
  const roomByFurniture = new Map(layoutFurniture.map((item) => [
    String(item.id || item.furniture_id),
    String(item.roomId || item.room_id || ""),
  ]));
  const roomPolygons = rooms.map((room) => ({ room, bounds: polygonBounds(room.polygon_cm || room.polygon || []) }));
  const planBounds = polygonBounds(roomPolygons.flatMap((item) => item.bounds?.points || []));
  const planCenter = planBounds ? {
    x_cm: (planBounds.minX + planBounds.maxX) / 2,
    y_cm: (planBounds.minY + planBounds.maxY) / 2,
  } : { x_cm: 0, y_cm: 0 };

  function inferredRoomId(object) {
    const explicit = object.placement_room_id || roomByFurniture.get(String(object.furniture_id));
    if (explicit) return String(explicit);
    const position = object.position_cm || {};
    const planPoint = {
      x_cm: planCenter.x_cm + finite(position.x),
      y_cm: planCenter.y_cm + finite(position.z ?? position.y),
    };
    const containing = roomPolygons.find((item) => (
      item.bounds && pointInPolygon(planXY(planPoint), item.bounds.points.map(planXY))
    ));
    return String(containing?.room.id || (rooms.length === 1 ? rooms[0].id : ""));
  }

  const applianceRequirements = scene.render_context?.appliance_requirements
    || scene.questionnaire?.appliance_requirements || [];
  const heightCm = finite(floorplan?.room_height_cm, 270);
  const snapshotRooms = rooms.map((room) => {
    const bounds = polygonBounds(room.polygon_cm || room.polygon || []);
    if (!bounds || bounds.width <= 0 || bounds.depth <= 0) {
      throw new Error(`${room.label || room.id} 缺少有效 polygon_cm。`);
    }
    const roomId = String(room.id || room.room_id);
    const requirement = roomRequirements[roomId] || {};
    const roomFurniture = (scene.scene_objects || []).filter((item) => (
      !APPLIANCE_TYPES.has(String(item.normalized_type || "").toLowerCase())
      && inferredRoomId(item) === roomId
    )).map((item) => ({
      furniture_id: String(item.furniture_id),
      catalog_furniture_id: item.catalog_furniture_id ? String(item.catalog_furniture_id) : null,
      name: String(item.name_zh || item.name_zh_raw || item.normalized_type || item.furniture_id),
      category: String(item.normalized_type || "furniture"),
      width_cm: finite(item.size_cm?.width, 1),
      depth_cm: finite(item.size_cm?.depth, 1),
      height_cm: finite(item.size_cm?.height, 1),
      quantity: 1,
      x_cm: finite(item.position_cm?.x),
      y_cm: finite(item.position_cm?.z ?? item.position_cm?.y),
      rotation_deg: finite(item.rotation_y_deg),
      position_reference: "center",
      placement_failed: item.placement_failed === true,
      placement_reason: item.placement_reason || null,
      needs_power: item.needs_power === true,
      needs_water: item.needs_water === true,
      needs_drain: item.needs_drain === true,
      asset_url: item.model_url || item.glb_url || null,
    }));
    const equipment = applianceRequirements.filter((item) => (
      String(item.room_id || "") === roomId || (rooms.length === 1 && !item.room_id)
    )).map((item, index) => ({
      equipment_id: String(item.furniture_id || `appliance-${roomId}-${index + 1}`),
      name: String(item.name_zh || item.name_zh_raw || item.normalized_type || "家電"),
      category: normalizeEquipmentType(item.normalized_type),
      quantity: 1,
      source: "scene_context",
    }));
    if (requirement.climate?.airConditioning) {
      equipment.push({
        equipment_id: `hvac-${roomId}`,
        name: String(requirement.climate.airConditioning),
        category: "air_conditioner",
        quantity: 1,
        source: "questionnaire",
      });
    }
    const matchingRegions = (floorplan?.room_regions || []).filter(
      (region) => String(region.room_id || "") === roomId,
    );
    const layoutForRoom = floorplan ? {
      ...clone(floorplan),
      room_regions: matchingRegions.length ? matchingRegions : [{
        room_id: roomId,
        label: String(room.label || room.name || roomId),
        room_type: String(room.type || room.room_type || "other"),
        exterior: bounds.points.map((point) => [
          point.x_cm - planCenter.x_cm,
          point.y_cm - planCenter.y_cm,
        ]),
        holes: [],
      }],
    } : null;
    return {
      room_id: roomId,
      name: String(room.label || room.name || roomId),
      room_type: String(room.type || room.room_type || requirement.roomType || "other"),
      style: workflow.realistic_3d?.activeStylePackId || scene.style?.style_id || null,
      geometry: {
        length_cm: bounds.width,
        width_cm: bounds.depth,
        height_cm: heightCm,
        opening_area_m2: explicitOpeningAreaM2(
          roomState.structures || {}, roomId, rooms.length === 1,
        ),
        polygon_cm: bounds.points,
      },
      layout_json: layoutForRoom,
      materials: materialSelections(surfaceByRoom.get(roomId) || {}, requirement),
      furniture: roomFurniture,
      equipment_requirements: equipment,
      mep_points: [],
      renders: renderReferencesForRoom(room, workflow, renders),
    };
  });
  return {
    schema_version: "roompilot.project-snapshot.v1",
    coordinate_unit: "cm",
    project_id: String(project.project_id),
    project_name: String(project.name || "RoomPilot 專案"),
    revision: `D${project.revision}`,
    source_project_revision: Number(project.revision),
    approval_status: "draft",
    region: "Taiwan",
    pricing_basis_date: new Date().toISOString().slice(0, 10),
    confirmed_by: null,
    confirmed_at: null,
    rooms: snapshotRooms,
    assumptions: [
      "ProjectSnapshot 由正式前端 state adapter 建立；跨模組尺寸與座標單位為 cm。",
      "門窗開口面積只使用 state 中已明示的高度與寬度；缺少尺寸時不補猜。",
    ],
  };
}

function renderState() {
  $("#project-name").textContent = state.project?.name || "—";
  $("#revision").textContent = state.snapshot?.revision || (state.project ? `D${state.project.revision}` : "—");
  $("#completeness").textContent = state.completeness ? `${state.completeness.score}%` : "—";
  $("#lock-status").textContent = state.snapshot?.approval_status === "designer_confirmed" ? "已鎖定" : "Draft";
  const locked = state.snapshot?.approval_status === "designer_confirmed";
  $("#save-draft").disabled = locked || !state.project;
  $("#lock-revision").disabled = locked || !state.snapshot;
  $("#generate-package").disabled = !locked;
  const issues = [
    ...(state.completeness?.missing || []).map((item) => `缺少：${item}`),
    ...(state.completeness?.warnings || []).map((item) => `待確認：${item}`),
  ];
  $("#completeness-list").innerHTML = (issues.length ? issues : ["目前沒有 Adapter 完整性問題"])
    .map((item) => `<li>${String(item).replaceAll("<", "&lt;")}</li>`).join("");
}

async function loadCurrentProject() {
  if (!state.projectId) throw new Error("網址缺少 project_id，請先從設計專案進入。");
  const [projectResult, renderResult, health] = await Promise.all([
    api(`/api/projects/${encodeURIComponent(state.projectId)}`),
    api(`/api/projects/${encodeURIComponent(state.projectId)}/renders`).catch(() => ({ renders: [] })),
    api("/api/v1/engineering/health"),
  ]);
  state.project = projectResult.project;
  state.renders = renderResult.renders || [];
  state.health = health;
  $("#back-to-project").href = `/scene?project_id=${encodeURIComponent(state.projectId)}`;
  $("#demo-banner").hidden = health.demo_mode !== true;
  $("#retriever-banner").textContent = health.advanced_rag.semantic_retriever === "noop_not_vector_retrieval"
    ? "Advanced RAG：Structured Retrieval 已啟用；工程 Vector Retriever 目前為 Mock／Noop，不是真正 Vector Retrieval。"
    : `Advanced RAG：${health.advanced_rag.semantic_retriever}`;
  try {
    const adaptedSnapshot = buildProjectSnapshot(state.project, state.renders);
    try {
      const existing = await api(
        `/api/v1/projects/${encodeURIComponent(state.projectId)}/revisions/${encodeURIComponent(adaptedSnapshot.revision)}/snapshot`,
      );
      state.snapshot = existing.snapshot;
      state.completeness = existing.completeness;
      $("#snapshot-status").textContent = state.snapshot.approval_status === "designer_confirmed"
        ? `${state.snapshot.revision} 已由 ${state.snapshot.confirmed_by || "設計師"} 鎖定；後續修改必須建立新 revision。`
        : `${state.snapshot.revision} Draft 已保存；來源 project revision = ${state.snapshot.source_project_revision}。`;
    } catch (error) {
      if (error.status !== 404) throw error;
      state.snapshot = adaptedSnapshot;
      state.completeness = null;
      $("#snapshot-status").textContent = "已由目前 project state 建立本機 Draft；請保存後再鎖定。";
    }
  } catch (error) {
    state.snapshot = null;
    $("#snapshot-status").textContent = errorMessage(error);
  }
  renderState();
}

async function saveDraft() {
  if (!state.project) return false;
  let saved = false;
  try {
    state.snapshot = buildProjectSnapshot(state.project, state.renders);
    state.snapshot.region = "Taiwan";
    const result = await api(
      `/api/v1/projects/${encodeURIComponent(state.projectId)}/revisions/${encodeURIComponent(state.snapshot.revision)}/snapshot`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.snapshot),
      },
    );
    state.snapshot = result.snapshot;
    state.completeness = result.completeness;
    $("#snapshot-status").textContent = `Draft 已保存；來源 project revision = ${state.snapshot.source_project_revision}。`;
    $("#job-error").textContent = "";
    saved = true;
  } catch (error) {
    $("#job-error").textContent = errorMessage(error);
  }
  renderState();
  return saved;
}

async function lockRevision() {
  const confirmedBy = $("#confirmed-by").value.trim();
  if (!confirmedBy) {
    $("#job-error").textContent = "請先輸入設計師／確認者。";
    return false;
  }
  let locked = false;
  try {
    const result = await api(
      `/api/v1/projects/${encodeURIComponent(state.projectId)}/revisions/${encodeURIComponent(state.snapshot.revision)}/lock`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed_by: confirmedBy }),
      },
    );
    state.snapshot = result.snapshot;
    state.completeness = result.completeness;
    $("#snapshot-status").textContent = `${state.snapshot.revision} 已由 ${confirmedBy} 鎖定；後續修改必須建立新 revision。`;
    $("#job-error").textContent = "";
    locked = true;
  } catch (error) {
    $("#job-error").textContent = errorMessage(error);
  }
  renderState();
  return locked;
}

function updateJob(job) {
  $("#job-progress").value = job.progress || 0;
  $("#job-stage").textContent = `${job.stage} · ${job.progress}% · ${job.status}`;
  $("#job-error").textContent = job.error ? `${job.error_code || "ERROR"}：${job.error}` : "";
}

function availableDocumentTypes() {
  // XLSX 由 @oai/artifact-tool 生成；adapter 未設定時要求它只會讓整包
  // 失敗（XLSX_ADAPTER_UNAVAILABLE），HTML 與 JSON 也一起陪葬。手動與
  // 自動流程都只要求本機做得出來的文件，缺席原因如實顯示、不假裝成功。
  if (state.health?.xlsx?.module_path_configured) {
    return ["report_json", "report_html", "estimate_xlsx"];
  }
  return ["report_json", "report_html"];
}

async function generatePackage(documentTypes) {
  $("#download-links").innerHTML = "";
  $("#html-preview").hidden = true;
  $("#json-details").hidden = true;
  const documents = Array.isArray(documentTypes) && documentTypes.length
    ? documentTypes
    : availableDocumentTypes();
  const xlsxSkipped = !documents.includes("estimate_xlsx");
  try {
    const queued = await api(`/api/v1/projects/${encodeURIComponent(state.projectId)}/engineering-packages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        revision: state.snapshot.revision,
        documents,
      }),
    });
    updateJob(queued);
    let job = queued;
    while (["queued", "processing"].includes(job.status)) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      job = await api(`/api/v1/jobs/${encodeURIComponent(job.job_id)}`);
      updateJob(job);
    }
    if (xlsxSkipped) {
      $("#job-stage").textContent += "；XLSX adapter（@oai/artifact-tool）未設定，本次未產生 Excel 估價表";
    }
    if (job.status === "failed") return;
    state.report = await api(`/api/v1/packages/${encodeURIComponent(job.package_id)}`);
    const labels = {
      report_html: "下載設計工程提案 HTML",
      estimate_xlsx: "下載工程估價與排程 XLSX",
      report_json: "下載 ReportPayload JSON",
    };
    // 下載與預覽都由瀏覽器直接發請求，不會經過 fetch 攔截器，因此改走
    // 帶身分的 fetch 再轉 blob；直接用 href/src 會一律 401。
    const downloads = $("#download-links");
    downloads.replaceChildren();
    state.report.documents.forEach((entry) => {
      const button = window.document.createElement("button");
      button.type = "button";
      button.className = "button";
      button.textContent = labels[entry.document_type] || entry.file_name;
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await downloadAuthorized(entry.download_url, entry.file_name);
        } catch (error) {
          $("#job-error").textContent = errorMessage(error);
        } finally {
          button.disabled = false;
        }
      });
      downloads.append(button);
    });
    const htmlDocument = state.report.documents.find((item) => item.document_type === "report_html");
    if (htmlDocument) {
      $("#html-preview").src = await authorizedObjectUrl(
        `${htmlDocument.download_url}?preview=1`,
        { cacheKey: "report-preview" },
      );
      $("#html-preview").hidden = false;
      $("#preview-placeholder").hidden = true;
    }
    renderReportSummary(state.report);
    $("#json-preview").textContent = JSON.stringify(state.report, null, 2);
    $("#json-details").hidden = false;
  } catch (error) {
    $("#job-error").textContent = errorMessage(error);
  }
}

const twd = (value) => (
  typeof value === "number" ? `NT$ ${value.toLocaleString("zh-TW")}` : "—"
);

/** 讓使用者不必開 HTML 就看得到四種數字的重點，以及它們各自的完整度。 */
function renderReportSummary(report) {
  const design = report.design_narrative || {};
  const furniture = report.furniture_estimate || {};
  const entries = [
    ["設計風格", design.style_name_zh || "未設定"],
    [
      "家具採購",
      furniture.estimated_total_twd !== null
      && furniture.estimated_total_twd !== undefined
        ? twd(furniture.estimated_total_twd)
        : `${twd(furniture.known_subtotal_twd)}（尚有 ${furniture.unpriced_count || 0} 項待詢價）`,
    ],
    [
      "工程施工費",
      report.estimate.estimated_total !== null
      && report.estimate.estimated_total !== undefined
        ? twd(report.estimate.estimated_total)
        : `${twd(report.estimate.known_subtotal)}（尚有 ${report.estimate.pending_quote_count} 項待詢價）`,
    ],
    [
      "初步工期",
      report.schedule.estimated_total_days !== null
      && report.schedule.estimated_total_days !== undefined
        ? `${report.schedule.estimated_total_days} 日`
        : `無法推算（${report.schedule.unknown_duration_count} 項缺工率）`,
    ],
    ["風險與待確認", `${report.risks.summary.risk_count} 項`],
  ];
  const grid = $("#report-summary-grid");
  grid.replaceChildren();
  entries.forEach(([label, value]) => {
    const term = window.document.createElement("dt");
    term.textContent = label;
    const definition = window.document.createElement("dd");
    definition.textContent = value;
    grid.append(term, definition);
  });
  // 兩種金額分開列示；相加會混淆「買家具」與「做工程」兩種預算。
  $("#report-summary-note").textContent =
    "家具採購與工程施工費為兩筆獨立預算，報告不予合計。"
    + (design.disclaimer_zh ? ` ${design.disclaimer_zh}` : "");
  $("#report-summary").hidden = false;
}

// 第 8 步「輸出簡報」入口帶 auto=1 進來：自動走「保存 Draft → 鎖定 → 生成」，
// 任一步失敗就停在原地，錯誤照常顯示，使用者可手動接續。
async function runAutoProposal() {
  if (!state.snapshot) return;
  if (state.snapshot.approval_status !== "designer_confirmed") {
    $("#job-stage").textContent = "輸出簡報：正在保存並鎖定目前設計…";
    if (!(await saveDraft())) return;
    const confirmedInput = $("#confirmed-by");
    if (!confirmedInput.value.trim()) {
      const user = getCurrentUser();
      confirmedInput.value = String(user?.display_name || user?.email || "").trim();
    }
    if (!(await lockRevision())) return;
  }
  $("#job-stage").textContent = "輸出簡報：正在生成提案文件…";
  await generatePackage();
}

$("#refresh-state").addEventListener("click", () => loadCurrentProject().catch((error) => {
  $("#job-error").textContent = errorMessage(error);
}));
$("#save-draft").addEventListener("click", saveDraft);
$("#lock-revision").addEventListener("click", lockRevision);
$("#generate-package").addEventListener("click", () => generatePackage());

if (requireSignedIn()) {
  const autoRun = new URLSearchParams(location.search).get("auto") === "1";
  loadCurrentProject().then(() => {
    if (autoRun) return runAutoProposal();
    return undefined;
  }).catch((error) => {
    $("#job-error").textContent = errorMessage(error);
    $("#snapshot-status").textContent = errorMessage(error);
    renderState();
  });
}
