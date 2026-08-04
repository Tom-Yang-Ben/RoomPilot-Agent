// 佇列 7 巨石拆分第六批（6B）：碰 state 的家具候選集/檢索群與家具推薦 UI 群
// （含 6A 點名的糾纏對 renderQuestionnaireFinishes / selectQuestionnaireStylePack），
// 以工廠參數遮蔽法自 scene_v2.js 純搬家。工廠參數名與 scene_v2 模組作用域的
// 原名完全相同（state、element、$、escapeHtml、api、errorMessage、setStatus、
// scheduleSave、invalidateDownstreamFrom、normalizedRoomTypeValue、
// activeQuestionnaireRoom、activeQuestionnairePack、activeRoomFinishDraft、
// wholeHouseFinishDraft、livingRoomForCirculation、circulationStyleIsOverridden、
// copyLivingRoomStyleToCirculation、knownUnavailableCatalogFurnitureIds、
// replacementCandidateFitsRoom、unavailableCatalogModelUrls、
// verifiedCatalogModelUrls），函式本體 byte 級照搬、一字不改——閉包引用自動
// 改走工廠參數，因此本體維持原縮排（不重新內縮）。scene_v2 呼叫工廠後解構回
// 同名 const，呼叫端零改動；shortlistState 與 questionnaireFurnitureInFlight
// 兩個可變單例連同註解搬到本模組模組層，單例語意不變。

import {
  catalogFurnitureOffer,
  chunkUniqueFurnitureItemIds,
  rankCatalogFurniture,
} from "./scene_furniture_retrieval.js?v=sha256-6772c0c167b3";
import {
  createFurniture2DItem,
  recommendCompanionFurniture,
  recommendedFurnitureForRoom,
} from "./scene_layout2d.js?v=sha256-23d4de37dcfe";
import {
  renderMaterialPairPreviews,
} from "./scene_material_pair_preview.js?v=sha256-257a140bd340";
import {
  roomDimensions,
} from "./scene_plan_geometry.js?v=sha256-52ddaf293063";
import {
  evaluateConditionalOption,
} from "./scene_room_requirements.js?v=sha256-86b7bbecc47a";
import {
  CEILING_STYLES,
  LIGHT_STYLES,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-fd8fa1eb64b1";
import {
  CATALOG_RETRIEVAL_ROUTES,
  QUESTIONNAIRE_FALLBACK_CATALOG_RULES,
  QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS,
  REPLACEMENT_TYPE_LABELS,
  ROOM_USAGE_FURNITURE_SPECS,
  furnitureOfferFromSpec,
  isCirculationRoom,
  isFloorPlacedCatalogItem,
  isQuestionnaireFallbackTypeMatch,
  questionnaireFurnitureDisplayLabel,
  questionnaireFurnitureDisplayName,
  questionnaireFurnitureProgram,
  questionnaireFurnitureRole,
  questionnaireFurnitureSelectionItem,
  questionnaireFurnitureSizeLabel,
  questionnaireMaterialOptionsForPack,
  questionnaireMaterialPairsForPack,
  questionnaireOfferMatchesRequestedType,
  questionnaireOffersWithSizeChoices,
  roomAreaM2,
  roomUsageOptions,
} from "./scene_questionnaire_data.js?v=sha256-17c7e0ecc752";

// ── 家具候選集（第 5 步問卷送出時由後端 RAG 建立）──────────────────────
// 候選集把 8,557 筆型錄縮成每房數十筆，選件與擺放都只在這個子集上跑。
// 這裡只換「候選從哪來」，排序、尺寸選項與 offer 轉換全部沿用既有邏輯。
const shortlistState = {
  fingerprint: "",
  byRoom: new Map(),
  loading: null,
  ensureLoading: null,
  // 家具來源的誠實回報：候選集失效或某些族系退回全型錄時，使用者要看得到，
  // 不能只留 console.warn（QA 2026-08-03：靜默退化會讓人以為在用候選集）。
  active: false,
  notice: "",
  fallbackTypes: new Set(),
};

// 原 scene_v2 模組層變數：逐房推薦進行中的房號集合，只有本模組的推薦流程
// 讀寫，跟著搬進模組層。
const questionnaireFurnitureInFlight = new Set();

export function createFurnitureOffers({
  state,
  element,
  $,
  escapeHtml,
  api,
  errorMessage,
  setStatus,
  scheduleSave,
  invalidateDownstreamFrom,
  normalizedRoomTypeValue,
  activeQuestionnaireRoom,
  activeQuestionnairePack,
  activeRoomFinishDraft,
  wholeHouseFinishDraft,
  livingRoomForCirculation,
  circulationStyleIsOverridden,
  copyLivingRoomStyleToCirculation,
  knownUnavailableCatalogFurnitureIds,
  replacementCandidateFitsRoom,
  unavailableCatalogModelUrls,
  verifiedCatalogModelUrls,
}) {
function renderQuestionnaireMaterialOptions(kind, pack) {
  const draft = activeRoomFinishDraft();
  const host = kind === "wall"
    ? element.questionnaireWallOptions
    : element.questionnaireFloorOptions;
  const selectedKey = kind === "wall" ? "wallMaterial" : "floorMaterial";
  const options = questionnaireMaterialOptionsForPack(kind, pack);
  host.innerHTML = options.map((option) => `
    <button type="button" data-questionnaire-material="${escapeHtml(kind)}"
      data-questionnaire-material-id="${escapeHtml(option.id)}"
      class="${draft[selectedKey] === option.id ? "is-active" : ""}"
      aria-pressed="${draft[selectedKey] === option.id}">
      <span class="rp-material-preview" style="background-color:${escapeHtml(option.color)};background-image:url('${escapeHtml(option.materialPreview)}')"></span>
      <strong>${escapeHtml(option.label)}</strong>
      <small>${escapeHtml(option.note)}<em>${escapeHtml(`${pack.name} 推薦`)}</em></small>
    </button>
  `).join("");
}

// ── 本房牆＋地板搭配卡（bella-test1 fd0cee11／5d92e612／25b83f95 移植）──────
// 只顯示一組推薦（25b83f95）；若使用者已自選且與推薦不同，改顯示目前選擇。
function questionnaireMaterialPairCards(pack) {
  const draft = activeRoomFinishDraft();
  const room = activeQuestionnaireRoom();
  const selectedWall = questionnaireMaterialOptionsForPack("wall", pack)
    .find((option) => option.id === draft.wallMaterial);
  const selectedFloor = questionnaireMaterialOptionsForPack("floor", pack)
    .find((option) => option.id === draft.floorMaterial);
  const recommendations = questionnaireMaterialPairsForPack(pack, room);
  if (!selectedWall || !selectedFloor) return recommendations;
  const current = {
    wall: { ...selectedWall, color: draft.wallColor || selectedWall.color },
    floor: { ...selectedFloor, color: draft.floorColor || selectedFloor.color },
    isCurrentSelection: true,
  };
  const currentIsRecommended = recommendations.some((pair) => (
    pair.wall.id === current.wall.id && pair.floor.id === current.floor.id
  ));
  if (currentIsRecommended) {
    return [current, ...recommendations.filter((pair) => (
      pair.wall.id !== current.wall.id || pair.floor.id !== current.floor.id
    ))].slice(0, 1);
  }
  return [...recommendations, { ...current, isCustomSelection: true }].slice(0, 1);
}

function renderQuestionnaireMaterialPairs(pack) {
  const draft = activeRoomFinishDraft();
  const pairs = questionnaireMaterialPairCards(pack);
  const host = element.questionnaireMaterialPairs;
  if (!host) return pairs;
  host.hidden = false;
  host.innerHTML = `
    <div class="rp-questionnaire-section-heading"><div><span class="eyebrow">本房推薦</span><h3>牆與地板搭配</h3></div><p>這是依房型與全屋風格產生的一組預設搭配；需要調整時，再從下方材質庫選擇。</p></div>
    <div class="rp-material-pair-grid">${pairs.map((pair, index) => `
      <button type="button" class="rp-material-pair-card ${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id ? "is-active" : ""}"
        data-questionnaire-material-pair="${index}" aria-pressed="${draft.wallMaterial === pair.wall.id && draft.floorMaterial === pair.floor.id}">
        <canvas data-material-pair-preview aria-label="${escapeHtml(`${pair.wall.label} 與 ${pair.floor.label} 的立體搭配預覽`)}"></canvas>
        <span><strong>牆：${escapeHtml(pair.wall.label)}</strong><small>地：${escapeHtml(pair.floor.label)}</small>${pair.isCurrentSelection ? "<em>目前選擇</em>" : ""}${pair.isCustomSelection ? "<em>自訂選擇</em>" : ""}</span>
      </button>
    `).join("") || "<p class=\"rp-field-error\">找不到可搭配的牆面與地板材質，可改用下方自訂選擇。</p>"}</div>`;
  // 小預覽用的 textureUrl 沿用材質卡縮圖（本機材質縮圖即為可平鋪貼圖）。
  const previewPairs = pairs.map((pair) => ({
    wall: { ...pair.wall, textureUrl: pair.wall.textureUrl || pair.wall.materialPreview },
    floor: { ...pair.floor, textureUrl: pair.floor.textureUrl || pair.floor.materialPreview },
  }));
  if (pairs.length) requestAnimationFrame(() => renderMaterialPairPreviews(host, previewPairs));
  return pairs;
}

function selectQuestionnaireMaterialPair(pair) {
  const draft = activeRoomFinishDraft();
  draft.wallMaterial = pair.wall.id;
  draft.wallColor = pair.wall.color;
  draft.floorMaterial = pair.floor.id;
  draft.floorColor = pair.floor.color;
  if (state.selectedQuestionnaireWallId) {
    draft.wallOverrides[state.selectedQuestionnaireWallId] = { materialId: draft.wallMaterial, color: draft.wallColor };
  } else {
    draft.defaultWallMaterial = draft.wallMaterial;
    draft.defaultWallColor = draft.wallColor;
  }
  draft.confirmed = false;
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function renderQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  if (room && isCirculationRoom(room)) copyLivingRoomStyleToCirculation(room);
  const draft = activeRoomFinishDraft();
  if (!room || !draft) return;
  const roomNeedsOnly = state.questionnaireStage === "rooms";
  const circulationLocked = isCirculationRoom(room) && !circulationStyleIsOverridden(room);
  $("#questionnaire-finishes").classList.toggle("is-room-needs-only", roomNeedsOnly);
  $("#room-finish-title").textContent = roomNeedsOnly
    ? `${room.label}的用途與家具`
    : `${room.label}的設備與材質`;
  $("#questionnaire-finishes .rp-questionnaire-section-heading > p").textContent = roomNeedsOnly
    ? "先勾選這個空間的用途與想帶入的家具；全屋風格、材質與設備會在所有房間完成後一次設定。"
    : "材質與設備會由全屋風格預設帶入；你仍可在第 6 步針對個別空間微調。";
  element.circulationStyleNotice.hidden = !isCirculationRoom(room) || roomNeedsOnly;
  if (isCirculationRoom(room) && !roomNeedsOnly) {
    const livingRoom = livingRoomForCirculation();
    element.circulationStyleNotice.querySelector("strong").textContent = circulationLocked
      ? `走道沿用${livingRoom?.label || "客廳"}風格`
      : "走道使用獨立風格";
    element.circulationStyleNotice.querySelector("p").textContent = circulationLocked
      ? `走道會同步${livingRoom?.label || "客廳"}的牆面、地板、天花板與照明，讓全屋動線保持連續。`
      : "你已選擇走道獨立風格；第 6 步會保留這項設定並重新檢查銜接。";
    element.enableCirculationStyleOverride.hidden = !circulationLocked;
  }
  $("#confirm-questionnaire-finishes").textContent = roomNeedsOnly
    ? `確認${room.label}的用途與家具`
    : "確認設備與材質";
  renderQuestionnaireRoomUsage(room);
  renderQuestionnaireFurnitureRecommendations(room);
  void ensureQuestionnaireFurnitureRecommendations(room);
  const stylePreview = roomNeedsOnly ? wholeHouseFinishDraft() : draft;
  const previewPack = STYLE_PACKS.find((candidate) => candidate.id === stylePreview.stylePackId)
    || STYLE_PACKS.find((candidate) => candidate.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
  const styles = [...new Map(
    STYLE_PACKS.map((pack) => [pack.styleId, pack.styleLabel]),
  ).entries()];
  element.questionnaireStyleTabs.innerHTML = styles.map(([styleId, label]) => `
    <button type="button" data-questionnaire-style="${escapeHtml(styleId)}"
      class="${styleId === previewPack.styleId ? "is-active" : ""}"
      aria-pressed="${styleId === previewPack.styleId}" ${roomNeedsOnly ? "disabled" : ""}>${escapeHtml(label)}</button>
  `).join("");
  const packs = STYLE_PACKS.filter((pack) => pack.styleId === previewPack.styleId);
  element.questionnaireStyleGrid.innerHTML = packs.map((pack) => `
    <button type="button" data-questionnaire-style-pack="${escapeHtml(pack.id)}"
      class="${pack.id === previewPack.id ? "is-active" : ""}"
      aria-pressed="${pack.id === previewPack.id}" ${roomNeedsOnly ? "disabled" : ""}
      title="${escapeHtml(roomNeedsOnly ? "下一階段可調整全屋風格與材質" : "選擇此風格色卡")}">
      <img class="rp-style-card-preview" src="${escapeHtml(pack.sourceImage)}"
        alt="${escapeHtml(`${pack.styleLabel} ${pack.name}參考圖`)}" loading="lazy">
      ${roomNeedsOnly ? "" : `<span class="rp-style-swatches">${pack.palette
        .map((color) => `<i style="background:${escapeHtml(color)}"></i>`)
        .join("")}</span>`}
      <strong>${escapeHtml(pack.name)}</strong>
      ${roomNeedsOnly ? "<small>全屋風格預覽，下一階段可調整</small>" : ""}
    </button>
  `).join("");
  const pack = activeQuestionnairePack();
  renderQuestionnaireMaterialOptions("wall", pack);
  renderQuestionnaireMaterialOptions("floor", pack);
  renderQuestionnaireMaterialPairs(pack);
  element.questionnaireWallColor.value =
    draft.wallColor || pack.wall.color;
  element.questionnaireFloorColor.value =
    draft.floorColor || pack.floor.color;
  if (element.questionnaireWallPreference) {
    element.questionnaireWallPreference.value = draft.wallPreference || "";
  }
  if (element.questionnaireFloorPreference) {
    element.questionnaireFloorPreference.value = draft.floorPreference || "";
  }
  element.questionnaireCeilingMaterial.value =
    draft.ceilingMaterial || "flat-paint";
  element.questionnaireCeilingStyle.innerHTML = CEILING_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireLightStyle.innerHTML = LIGHT_STYLES.map((item) =>
    `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`
  ).join("");
  element.questionnaireCeilingStyle.value =
    draft.ceilingStyle
    || CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || CEILING_STYLES[0].id;
  element.questionnaireLightStyle.value =
    draft.lightStyle
    || LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))?.id
    || LIGHT_STYLES[0].id;
  element.questionnaireCeilingColor.value =
    draft.ceilingColor || "#f4f1eb";
  element.questionnaireAirConditioning.value = draft.airConditioning || "";
  const selectedWall = questionnaireMaterialOptionsForPack("wall", pack).find(
    (option) => option.id === draft.wallMaterial,
  );
  const wallLabel = selectedWall?.label || "本房預設牆材";
  element.selectedWallSurface.textContent = state.selectedQuestionnaireWallId
    ? `目前指定：牆面 ${state.selectedQuestionnaireWallId.split(":").at(-1)} 使用${wallLabel}`
    : `全房牆面目前使用：${wallLabel}`;
  element.questionnaireFinishRoomTargets.innerHTML = state.rooms
    .filter((candidate) => candidate.id !== room.id)
    .map((candidate) => `<label><input type="checkbox" value="${escapeHtml(candidate.id)}"> ${escapeHtml(candidate.label)}</label>`)
    .join("");
  element.questionnaireFinishRoomTargets.hidden =
    element.questionnaireFinishScope.value !== "selected";
  const finishControls = [
    element.questionnaireStyleTabs,
    element.questionnaireStyleGrid,
    element.questionnaireWallOptions,
    element.questionnaireFloorOptions,
    element.questionnaireWallColor,
    element.questionnaireFloorColor,
    element.questionnaireWallPreference,
    element.questionnaireFloorPreference,
    element.questionnaireCeilingMaterial,
    element.questionnaireCeilingStyle,
    element.questionnaireLightStyle,
    element.questionnaireCeilingColor,
    element.questionnaireAirConditioning,
    element.questionnaireFinishScope,
  ];
  finishControls.forEach((control) => {
    if (!control) return;
    control.classList.toggle("is-locked", circulationLocked);
    if ("disabled" in control) control.disabled = circulationLocked;
    control.querySelectorAll?.("button, input, select").forEach((input) => {
      input.disabled = circulationLocked;
    });
  });
  renderConditionalFeasibility(room);
}

function renderConditionalFeasibility(room) {
  const options = [
    ["bathtub", "浴缸"],
    ["double_vanity", "雙洗手台"],
    ["large_dining_table", "大型餐桌"],
  ];
  const relevant = room.type === "bathroom"
    ? options.slice(0, 2)
    : (room.type === "dining_room" || room.type === "kitchen"
      ? options.slice(2)
      : []);
  if (!relevant.length) {
    element.roomFeasibilityNotices.innerHTML = "";
    return;
  }
  element.roomFeasibilityNotices.innerHTML = relevant.map(([optionId, label]) => {
    const result = evaluateConditionalOption(room, optionId, state.structures.doors);
    return `
      <article class="${result.feasible ? "is-feasible" : "needs-review"}">
        <strong>${escapeHtml(label)}</strong>
        <span>${result.feasible ? "目前尺寸可列為一般選項" : "目前尺寸可能無法配置"}</span>
        ${result.feasible ? "" : `<small>${escapeHtml(result.warnings[0])}</small>`}
      </article>
    `;
  }).join("");
}

function selectQuestionnaireStylePack(packId) {
  const pack = STYLE_PACKS.find((candidate) => candidate.id === packId);
  if (!pack) return;
  const draft = activeRoomFinishDraft();
  const activeRoom = activeQuestionnaireRoom();
  if (activeRoom && isCirculationRoom(activeRoom) && !circulationStyleIsOverridden(activeRoom)) return;
  const wallOption = questionnaireMaterialOptionsForPack("wall", pack)[0];
  const floorOption = questionnaireMaterialOptionsForPack("floor", pack)[0];
  const wallMaterial = wallOption?.id || pack.wall.surfaceOption;
  const wallColor = wallOption?.color || pack.wall.color;
  const floorMaterial = floorOption?.id || pack.floor.surfaceOption;
  const floorColor = floorOption?.color || pack.floor.color;
  state.activeStyleId = pack.styleId;
  Object.assign(draft, {
    ...draft,
    confirmed: false,
    stylePackId: pack.id,
    wallMaterial,
    wallColor,
    defaultWallMaterial: wallMaterial,
    defaultWallColor: wallColor,
    floorMaterial,
    floorColor,
    ceilingMaterial: "flat-paint",
    ceilingStyle: CEILING_STYLES.find(
      (item) => item.styles.includes(pack.styleId),
    )?.id || CEILING_STYLES[0].id,
    lightStyle: LIGHT_STYLES.find(
      (item) => item.styles.includes(pack.styleId),
    )?.id || LIGHT_STYLES[0].id,
  });
  const room = activeRoom;
  if (room) {
    delete state.roomFurnitureRecommendations[room.id];
    void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
  }
  renderQuestionnaireFinishes();
  scheduleSave("requirements");
}

function questionnairePackForRoom(room) {
  const paletteId =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.paletteId;
  return STYLE_PACKS.find((pack) => pack.id === paletteId)
    || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId)
    || STYLE_PACKS[0];
}

function questionnaireFurnitureRequest(room, spec) {
  const [type, variant] = spec;
  const template = createFurniture2DItem(type, variant, { roomId: room.id });
  const pack = questionnairePackForRoom(room);
  const surfaces =
    state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces || {};
  const requirement = state.roomRequirementModel?.roomRequirements?.[room.id] || {};
  return {
    type,
    roomType: room.type || room.room_type || "",
    roomLabel: room.label || room.name || "",
    styleId: pack.styleId,
    palette: pack.palette,
    queryText: [
      room.label,
      room.type,
      requirement.summary,
      requirement.notes,
      requirement.usage,
      requirement.furniture?.selected?.map((item) => item.label || item.type).join(" "),
      requirement.furniture?.preferenceText,
      requirement.furniture?.preferenceTags?.join(" "),
    ].filter(Boolean).join(" "),
    preferAnchor: ["bed", "sofa", "dining-table", "storage-cabinet", "appliance-cabinet"].includes(type),
    materials: [
      ...(pack.furniture?.materialLanguage || []),
      surfaces.wallDefault?.materialId,
      surfaces.floor?.materialId,
    ].filter(Boolean),
    widthCm: template.widthCm,
    depthCm: template.depthCm,
  };
}

async function catalogCandidatesForType(
  type,
  { styleId = "", query = "", catalogType = "", searchAll = false } = {},
) {
  const route = CATALOG_RETRIEVAL_ROUTES[type]
    || { endpoint: "/api/furniture", type };
  const canSearchAll = searchAll && route.endpoint === "/api/furniture";
  const routeTypes = canSearchAll
    ? [""]
    : (catalogType ? [catalogType] : (route.types || [route.type]));
  const candidateGroups = await Promise.all(routeTypes.map(async (routeType) => {
    const params = new URLSearchParams({
      detail: "scene",
      page_size: "80",
    });
    if (routeType) params.set("type", routeType);
    if (route.endpoint === "/api/furniture") params.set("has_model", "true");
    const searchQuery = [route.query, query].filter(Boolean).join(" ");
    if (searchQuery) params.set("q", searchQuery);
    if (styleId && route.endpoint === "/api/furniture") {
      params.set("style", styleId);
    }
    let payload = await api(`${route.endpoint}?${params.toString()}`);
    if (!(payload.items || []).length && params.has("style")) {
      params.delete("style");
      payload = await api(`${route.endpoint}?${params.toString()}`);
    }
    return payload.items || [];
  }));
  return candidateGroups.flat();
}

function renderFurnitureSourceNotice() {
  const node = $("#furniture-source-notice");
  if (!node) return;
  const parts = [];
  if (shortlistState.notice) parts.push(shortlistState.notice);
  if (shortlistState.active && shortlistState.fallbackTypes.size) {
    const labels = [...shortlistState.fallbackTypes]
      .map((type) => REPLACEMENT_TYPE_LABELS[type] || type);
    parts.push(`候選集中查無「${labels.join("、")}」，這幾類已改用全型錄補搜。`);
  }
  node.textContent = parts.join(" ");
  node.hidden = !parts.length;
}

function noteShortlistFallback(type) {
  // 整份候選集都不存在時主通知已經說明是全型錄模式，逐類記錄只是雜訊。
  if (!shortlistState.active) return;
  if (shortlistState.fallbackTypes.has(type)) return;
  shortlistState.fallbackTypes.add(type);
  renderFurnitureSourceNotice();
}

function storedFurnitureShortlist() {
  return state.project?.workflow?.furniture_shortlist || null;
}

/** 一次把整份候選集的完整型錄資料取回並依房間分組。 */
async function loadShortlistCandidates() {
  const shortlist = storedFurnitureShortlist();
  if (!shortlist?.rooms?.length) {
    shortlistState.byRoom = new Map();
    shortlistState.fingerprint = "";
    return shortlistState.byRoom;
  }
  if (shortlistState.fingerprint === shortlist.fingerprint && shortlistState.byRoom.size) {
    return shortlistState.byRoom;
  }
  if (shortlistState.loading) return shortlistState.loading;

  shortlistState.loading = (async () => {
    const itemIds = [];
    const roomOf = new Map();
    shortlist.rooms.forEach((room) => {
      (room.items || []).forEach((item) => {
        const itemId = String(item.item_id || "");
        if (!itemId) return;
        itemIds.push(itemId);
        if (!roomOf.has(itemId)) roomOf.set(itemId, []);
        if (!roomOf.get(itemId).includes(room.room_id)) roomOf.get(itemId).push(room.room_id);
      });
    });
    if (!itemIds.length) return new Map();
    // detail: "scene" 才會帶 placement_surface 等第 6 步需要的欄位，
    // 與 catalogCandidatesForType 走的是同一種 payload。
    const payloads = [];
    for (const batch of chunkUniqueFurnitureItemIds(itemIds)) {
      payloads.push(await api("/api/furniture/by-ids", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_ids: batch, detail: "scene" }),
      }));
    }
    const payload = {
      items: payloads.flatMap((item) => item.items || []),
      missing: payloads.flatMap((item) => item.missing || []),
    };
    const byRoom = new Map();
    (payload.items || []).forEach((item) => {
      const id = String(item.furniture_id || item.id || "");
      (roomOf.get(id) || []).forEach((roomId) => {
        if (!byRoom.has(roomId)) byRoom.set(roomId, []);
        byRoom.get(roomId).push(item);
      });
    });
    shortlistState.byRoom = byRoom;
    shortlistState.fingerprint = shortlist.fingerprint || "";
    if ((payload.missing || []).length) {
      console.warn("候選集有品項已不在型錄", payload.missing.length);
    }
    return byRoom;
  })().finally(() => {
    shortlistState.loading = null;
  });
  return shortlistState.loading;
}

function shortlistCandidatesForRoom(roomId) {
  return shortlistState.byRoom.get(String(roomId)) || [];
}

/** 問卷送出時建立候選集。失敗不擋流程，第 6 步會退回既有的全庫路徑。 */
async function ensureFurnitureShortlist() {
  if (!state.projectId) return false;
  if (shortlistState.ensureLoading) return shortlistState.ensureLoading;
  shortlistState.ensureLoading = (async () => {
    try {
    const result = await api(`/api/projects/${state.projectId}/furniture-shortlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (state.project?.workflow) {
      state.project.workflow.furniture_shortlist = result.shortlist;
    }
    await loadShortlistCandidates();
    const total = result.summary?.total_items || 0;
    const missing = (result.summary?.rooms || [])
      .filter((room) => (room.missing_families || []).length);
    shortlistState.active = total > 0;
    shortlistState.fallbackTypes = new Set();
    if (!shortlistState.active) {
      shortlistState.notice = "這個專案沒有建立家具候選集，選件將以全型錄搜尋，載入較慢。";
    } else if (missing.length) {
      shortlistState.notice =
        `候選集已建立；${missing.length} 個空間有需求在型錄查無對應品項，該類會以全型錄補搜。`;
      console.warn("部分空間沒有候選家具，將退回全型錄搜尋", missing);
    } else {
      shortlistState.notice = "";
    }
    renderFurnitureSourceNotice();
      return total > 0;
    } catch (error) {
    // 模型尚未載入、資料庫不可用或專案還沒確認空間都會走到這裡。
    // 不擋流程，但退化必須可見：全型錄模式載入明顯較慢，使用者要知道原因。
    shortlistState.active = false;
    shortlistState.notice =
      `候選集建立失敗（${errorMessage(error)}），本次選件改用全型錄搜尋，載入較慢。`;
    renderFurnitureSourceNotice();
    console.warn("候選集建立失敗，改用全型錄搜尋", error);
      return false;
    }
  })().finally(() => {
    shortlistState.ensureLoading = null;
  });
  return shortlistState.ensureLoading;
}

async function catalogOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  // 候選集優先：命中就省掉一次全型錄分頁查詢。篩不出這個族系時（例如
  // 型錄該房型沒有對應品項）照舊走原本的路徑，行為不會比先前差。
  const pooled = shortlistCandidatesForRoom(room.id);
  let matchingCandidates = pooled
    .filter(isFloorPlacedCatalogItem)
    .filter((candidate) => isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  if (!matchingCandidates.length) {
    noteShortlistFallback(spec[0]);
    const candidates = await catalogCandidatesForType(spec[0], {
      styleId: request.styleId,
      query: request.queryText,
    });
    matchingCandidates = candidates
      .filter(isFloorPlacedCatalogItem)
      .filter((candidate) => isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  }
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => catalogFurnitureOffer(candidate, {
    roomId: room.id,
    requestedType: spec[0],
    requestedVariant: spec[1],
    reason: spec[2]
      || `${room.label}的問卷風格、色卡、材質與實際尺寸綜合匹配`,
  }));
}

async function catalogFallbackOffersForSpec(room, spec, index) {
  const request = questionnaireFurnitureRequest(room, spec);
  const rule = QUESTIONNAIRE_FALLBACK_CATALOG_RULES[spec[0]] || {};
  const label = rule.query || REPLACEMENT_TYPE_LABELS[spec[0]] || spec[0];
  // 「找相似」本來就是全型錄補搜；候選集啟用時記下來，讓來源通知誠實列出。
  noteShortlistFallback(spec[0]);
  let candidates = await catalogCandidatesForType(spec[0], {
    query: label,
    searchAll: true,
  });
  if (!candidates.length) {
    candidates = await catalogCandidatesForType(spec[0], { searchAll: true });
  }
  const matchingCandidates = candidates.filter((candidate) =>
    isQuestionnaireFallbackTypeMatch(candidate, spec[0]));
  const ranked = rankCatalogFurniture(matchingCandidates, request);
  return questionnaireOffersWithSizeChoices(spec[0], ranked).map((candidate) => ({
    ...catalogFurnitureOffer(candidate, {
      roomId: room.id,
      requestedType: spec[0],
      requestedVariant: spec[1],
      reason: `${room.label}未取得精準風格結果，改以同類可配置家具推薦`,
    }),
    recommendation_tier: "similar",
  }));
}

async function catalogOffersForRoomPlans(roomPlans) {
  // 重新開啟既有專案時不會經過問卷送出，這裡補上候選集載入；已載入或
  // 專案沒有候選集時都是零成本。
  try {
    const byRoom = await loadShortlistCandidates();
    shortlistState.active = byRoom.size > 0;
    if (!shortlistState.active && storedFurnitureShortlist()) {
      shortlistState.notice = "候選集載入失敗，本次選件改用全型錄搜尋，載入較慢。";
    }
    renderFurnitureSourceNotice();
  } catch (error) {
    shortlistState.active = false;
    shortlistState.notice = "候選集載入失敗，本次選件改用全型錄搜尋，載入較慢。";
    renderFurnitureSourceNotice();
    console.warn("候選集載入失敗，改用全型錄搜尋", error);
  }
  return Object.fromEntries(await Promise.all(roomPlans.map(async ({ room, specs }) => {
    const groups = await Promise.all(specs.map(async (spec, index) => {
      try {
        return await catalogOffersForSpec(room, spec, index);
      } catch (error) {
        console.warn("Catalog RAG retrieval fallback", error);
        return [];
      }
    }));
    return [room.id, groups.flatMap((offers, index) => (
      offers.length
        ? offers
        : [furnitureOfferFromSpec(room, specs[index], index)]
    ))];
  })));
}

function questionnaireFurniturePreferenceTags(room) {
  const styleId = questionnairePackForRoom(room)?.styleId || "default";
  return QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS[styleId]
    || QUESTIONNAIRE_FURNITURE_PREFERENCE_TAGS.default;
}

function renderQuestionnaireFurniturePreferenceTags(room = activeQuestionnaireRoom()) {
  if (!element.questionnaireFurniturePreferenceTags || !room) return;
  const selected = new Set(roomFurnitureRequirement(room.id)?.preferenceTags || []);
  element.questionnaireFurniturePreferenceTags.innerHTML = questionnaireFurniturePreferenceTags(room)
    .map((tag) => `<button type="button" data-questionnaire-furniture-tag="${escapeHtml(tag)}"
      class="${selected.has(tag) ? "is-active" : ""}" aria-pressed="${selected.has(tag)}">${escapeHtml(tag)}</button>`)
    .join("");
}

function toggleQuestionnaireFurniturePreferenceTag(tag) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !tag) return;
  const tags = new Set(furniture.preferenceTags || []);
  if (tags.has(tag)) tags.delete(tag);
  else tags.add(tag);
  furniture.preferenceTags = [...tags];
  const text = element.questionnaireFurniturePreference?.value.trim() || "";
  const values = new Set(text.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean));
  furniture.preferenceTags.forEach((value) => values.add(value));
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = [...values].join("、");
  }
  furniture.preferenceText = element.questionnaireFurniturePreference?.value.trim() || "";
  renderQuestionnaireFurniturePreferenceTags(room);
  scheduleSave("requirements");
}

/**
 * 這間臥室是主臥還是次臥。
 *
 * 第 4 步的房名收斂後只有單一「臥室」類，主次由面積推導：最大的那間是主臥。
 * 沒有這個判斷，兒童房也會拿到主臥的雙人床配置。
 */
function bedroomRoleFor(room) {
  const bedrooms = state.rooms.filter(
    (candidate) => normalizedRoomTypeValue(candidate.type) === "bedroom",
  );
  if (bedrooms.length <= 1) return "primary";
  const ranked = [...bedrooms].sort((a, b) => roomAreaM2(b) - roomAreaM2(a));
  return String(ranked[0]?.id) === String(room.id) ? "primary" : "secondary";
}

function occupancyForRoom(room) {
  const residents = state.firstMeeting?.residents || {};
  const adults = Math.max(0, Number(residents.adults) || 0);
  const children = Math.max(0, Number(residents.children) || 0);
  const elderly = Math.max(0, Number(residents.elderly) || 0);
  return {
    adults,
    children,
    // 用餐人數＝全體住戶，至少兩人；沒有這個數字餐椅永遠只有一張。
    diningSeats: Math.max(2, adults + children + elderly),
    bedroomRole: bedroomRoleFor(room),
  };
}

function questionnaireFurnitureSpecsForRoom(room) {
  const recommended = recommendedFurnitureForRoom(room, occupancyForRoom(room));
  const usageSpecs = ensureRoomUsage(room).flatMap(
    (usage) => ROOM_USAGE_FURNITURE_SPECS[usage] || [],
  );
  const companions = recommendCompanionFurniture(
    room.type,
    [...recommended, ...usageSpecs].map(([type]) => type),
  ).map((item) => [item.type, item.variantId, item.reason, true]);
  const seen = new Set();
  return [...recommended, ...usageSpecs, ...companions].filter(([type, variant]) => {
    const key = `${type}:${variant || "standard"}`;
    if (!type || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function ensureRoomUsage(room) {
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  if (!requirement) return [];
  const available = roomUsageOptions(room);
  const availableIds = new Set(available.map((item) => item.id));
  const existing = Array.isArray(requirement.usage)
    ? requirement.usage.filter((item) => availableIds.has(item))
    : [];
  requirement.usage = existing.length ? existing : [available[0]?.id].filter(Boolean);
  return requirement.usage;
}

function renderQuestionnaireRoomUsage(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireRoomUsageOptions) return;
  const selected = new Set(ensureRoomUsage(room));
  element.questionnaireRoomUsageOptions.innerHTML = roomUsageOptions(room).map((option) => `
    <label class="${selected.has(option.id) ? "is-selected" : ""}">
      <input type="checkbox" data-questionnaire-room-usage="${escapeHtml(option.id)}"
        ${selected.has(option.id) ? "checked" : ""}>
      <span>${escapeHtml(option.label)}</span>
    </label>
  `).join("");
}

function roomFurnitureRequirement(roomId) {
  const requirement = state.roomRequirementModel.roomRequirements[roomId];
  if (!requirement) return null;
  requirement.furniture = {
    required: [],
    optional: [],
    selected: [],
    deferred: [],
    ...(requirement.furniture || {}),
  };
  return requirement.furniture;
}

function questionnaireFurnitureOffers(room) {
  const recommended = state.roomFurnitureRecommendations[room.id] || [];
  const selected = roomFurnitureRequirement(room.id)?.selected || [];
  const byId = new Map(
    [...selected, ...recommended]
      .filter((item) => item?.furniture_id && questionnaireOfferMatchesRequestedType(item))
      .map((item) => [String(item.furniture_id), item]),
  );
  return [...byId.values()];
}

function questionnaireFurnitureGroups(room, offers) {
  const selectedByType = new Map(
    (roomFurnitureRequirement(room.id)?.selected || [])
      .filter((item) => item?.normalized_type)
      .map((item) => [String(item.normalized_type), item]),
  );
  const groups = new Map();
  offers.forEach((offer) => {
    const type = String(offer.normalized_type || "other");
    const group = groups.get(type) || { type, offers: [] };
    group.offers.push(offer);
    groups.set(type, group);
  });
  return [...groups.values()].map((group) => {
    const selected = selectedByType.get(group.type);
    const active = group.offers.find((offer) => (
      String(offer.furniture_id) === String(selected?.furniture_id)
    )) || group.offers[0];
    return {
      ...group,
      active,
      selected,
      role: questionnaireFurnitureRole(room, active),
    };
  }).sort((left, right) => left.role.rank - right.role.rank || left.type.localeCompare(right.type));
}

function renderQuestionnaireFurnitureRecommendations(room = activeQuestionnaireRoom()) {
  if (!room || !element.questionnaireFurnitureOptions) return;
  const furniture = roomFurnitureRequirement(room.id);
  const offers = questionnaireFurnitureOffers(room);
  const groups = questionnaireFurnitureGroups(room, offers);
  if (element.questionnaireFurniturePreference) {
    element.questionnaireFurniturePreference.value = furniture?.preferenceText || "";
  }
  renderQuestionnaireFurniturePreferenceTags(room);
  const loading = questionnaireFurnitureInFlight.has(String(room.id));
  const error = state.roomFurnitureRecommendationErrors[room.id];
  const expectedTypes = questionnaireFurnitureSpecsForRoom(room);
  if (loading && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      `正在從資料庫取得「${room.label}」適用家具…`;
    element.questionnaireFurnitureOptions.innerHTML =
      '<p class="rp-control-hint">正在比對房間用途、色卡、材質與尺寸。</p>';
    return;
  }
  if (error && !offers.length) {
    element.questionnaireFurnitureStatus.textContent =
      "資料庫推薦暫時無法載入，請稍後重試。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<button type="button" class="secondary-action" data-retry-questionnaire-furniture="${escapeHtml(room.id)}">重新取得推薦</button>`;
    return;
  }
  if (!offers.length) {
    element.questionnaireFurnitureStatus.textContent = expectedTypes.length
      ? "暫時找不到可直接配置的 GLB；此需求會在第 6 步列為待處理，現在仍可繼續。"
      : "這個空間沒有預設家具需求，可直接確認其他設定。";
    element.questionnaireFurnitureOptions.innerHTML =
      `<div class="rp-questionnaire-furniture-empty">
        <p class="rp-control-hint">此需求不會卡住問卷。第 6 步會說明缺少 GLB 或配置風險，並提供替代、替換或刪除選項。</p>
        <button type="button" class="secondary-action" data-open-questionnaire-furniture-catalog="${escapeHtml(room.id)}">開啟家具資料庫</button>
      </div>`;
    return;
  }
  const similarCount = offers.filter((offer) => offer.recommendation_tier === "similar").length;
  element.questionnaireFurnitureStatus.textContent =
    similarCount
      ? `已提供 ${offers.length} 件可配置家具，其中 ${similarCount} 件為相近推薦；勾選後會原樣帶入第 6 步。`
      : `已依「${room.label}」推薦 ${offers.length} 件；勾選的款式會原樣帶入第 6 步。`;
  element.questionnaireFurnitureOptions.innerHTML = groups.map((group) => {
    const offer = group.active;
    const furnitureId = String(offer.furniture_id);
    const selected = Boolean(group.selected);
    const quantity = Math.max(1, Math.min(6, Number(group.selected?.count) || 1));
    const selectedQuantity = selected ? quantity : 0;
    const roomDimensionsValue = roomDimensions(room);
    const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
    const maximumQuantity = Math.max(1, Math.min(6, Math.floor(
      (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
    ) || 1));
    const shortLabel = questionnaireFurnitureDisplayLabel(offer);
    return `
      <article class="${selected ? "is-selected" : ""}">
        <label class="rp-questionnaire-furniture-select">
          <input type="checkbox" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}"
            ${selected ? "checked" : ""}>
          <span>
            <strong>${escapeHtml(shortLabel)}</strong>
            <small>${escapeHtml(questionnaireFurnitureSizeLabel(offer))}</small>
          </span>
        </label>
        <div class="rp-questionnaire-furniture-card-actions">
          <label class="rp-questionnaire-furniture-size">
            <span>尺寸</span>
            <select data-questionnaire-furniture-variant-type="${escapeHtml(group.type)}">
              ${group.offers.map((candidate, index) => `
                <option value="${escapeHtml(candidate.furniture_id)}" ${String(candidate.furniture_id) === furnitureId ? "selected" : ""}>
                  ${escapeHtml(questionnaireFurnitureDisplayLabel(candidate))} · ${escapeHtml(questionnaireFurnitureSizeLabel(candidate))}${index ? `（款式 ${index + 1}）` : ""}
                </option>
              `).join("")}
            </select>
          </label>
          <div class="rp-furniture-quantity" aria-label="${escapeHtml(questionnaireFurnitureDisplayName(offer))} 數量">
            <button type="button" data-questionnaire-furniture-quantity="-1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${selectedQuantity > 0 ? "" : "disabled"} aria-label="減少數量">−</button>
            <output>${selectedQuantity}</output>
            <button type="button" data-questionnaire-furniture-quantity="1" data-questionnaire-furniture-id="${escapeHtml(furnitureId)}" ${selectedQuantity < maximumQuantity ? "" : "disabled"} aria-label="增加數量">＋</button>
          </div>
          <small class="rp-furniture-quantity-limit">最多 ${maximumQuantity} 件</small>
          ${offer.room_fit_checked === false ? '<small class="rp-questionnaire-fit-risk">尺寸僅為初步估計，第 6 步將檢查實際 GLB、門窗與走道。</small>' : ''}
        </div>
      </article>
    `;
  }).join("");
  element.questionnaireFurnitureOptions
    .querySelectorAll('input[data-questionnaire-furniture-id]')
    .forEach((input) => {
      input.onchange = (event) => {
        event.stopPropagation();
        updateQuestionnaireFurnitureSelection(
          input.dataset.questionnaireFurnitureId,
          input.checked,
        );
      };
    });
  element.questionnaireFurnitureOptions
    .querySelectorAll('select[data-questionnaire-furniture-variant-type]')
    .forEach((select) => {
      select.onchange = (event) => {
        event.stopPropagation();
        updateQuestionnaireFurnitureVariant(
          select.dataset.questionnaireFurnitureVariantType,
          select.value,
        );
      };
    });
  element.questionnaireFurnitureOptions
    .querySelectorAll("[data-questionnaire-furniture-quantity]")
    .forEach((button) => {
      button.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        updateQuestionnaireFurnitureQuantity(
          button.dataset.questionnaireFurnitureId,
          Number(button.dataset.questionnaireFurnitureQuantity),
        );
      };
    });
  element.questionnaireFurnitureOptions.dataset.furnitureControlsBound = "true";
  if (element.refreshQuestionnaireFurniture) {
    element.refreshQuestionnaireFurniture.onclick = (event) => {
      event.preventDefault();
      refreshQuestionnaireFurnitureRecommendations();
    };
  }
}

function revokeStaleAutoRecommendations(room, offers) {
  // 契約(BEN_第5第6步整合規格):RAG 重跑後沒結果的自動套用家具必須撤回,
  // 使用者手選的家具(沒有 default_recommendation 標記)一律保留。
  const furniture = roomFurnitureRequirement(room.id);
  if (!furniture?.selected?.length) return;
  const available = new Set(offers.map((offer) => String(offer.furniture_id)));
  const kept = furniture.selected.filter((item) => (
    item.selection_source !== "questionnaire_default_recommendation"
    || available.has(String(item.furniture_id))
  ));
  if (kept.length === furniture.selected.length) return;
  furniture.selected = kept;
  furniture.required = [...new Set(kept.map((item) => item.normalized_type).filter(Boolean))];
}

function applyDefaultQuestionnaireFurnitureSelections(room, offers) {
  const furniture = roomFurnitureRequirement(room.id);
  if (!furniture || furniture.selected?.length || !offers.length) return;
  const program = questionnaireFurnitureProgram(room);
  const defaults = program.defaults.map((type) => offers.find((offer) => (
    offer.normalized_type === type
  ))).filter(Boolean);
  if (!defaults.length) return;
  furniture.selected = defaults.map((offer, index) => ({
    ...questionnaireFurnitureSelectionItem(offer, index + 1),
    default_recommendation: true,
    selection_source: "questionnaire_default_recommendation",
  }));
  furniture.required = [...new Set(defaults.map((offer) => offer.normalized_type))];
  furniture.optional = offers
    .filter((offer) => !defaults.some((selected) => String(selected.furniture_id) === String(offer.furniture_id)))
    .map((offer) => offer.normalized_type);
}

async function ensureQuestionnaireFurnitureRecommendations(
  room = activeQuestionnaireRoom(),
  { force = false } = {},
) {
  if (!room) return;
  const roomId = String(room.id);
  if (!force && state.roomFurnitureRecommendations[room.id]) return;
  if (questionnaireFurnitureInFlight.has(roomId)) return;
  questionnaireFurnitureInFlight.add(roomId);
  delete state.roomFurnitureRecommendationErrors[room.id];
  renderQuestionnaireFurnitureRecommendations(room);
  try {
    const specs = questionnaireFurnitureSpecsForRoom(room);
    const remembered = roomFurnitureRequirement(room.id);
    if (remembered?.selected?.length) {
      remembered.selected = remembered.selected.filter(questionnaireOfferMatchesRequestedType);
      remembered.required = [...new Set(
        remembered.selected.map((item) => item.normalized_type),
      )];
    }
    const unavailableCatalogIds = knownUnavailableCatalogFurnitureIds();
    const groups = await Promise.all(specs.map(async (spec, index) => {
      let offers = await catalogOffersForSpec(room, spec, index);
      if (!offers.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
      }
      let candidates = offers.filter((offer) =>
        !unavailableCatalogIds.has(String(offer.furniture_id))
        && Boolean(offer.model_url)
        && !unavailableCatalogModelUrls.has(String(offer.model_url)),
      );
      if (!candidates.length) {
        offers = await catalogFallbackOffersForSpec(room, spec, index);
        candidates = offers.filter((offer) =>
          !unavailableCatalogIds.has(String(offer.furniture_id))
          && Boolean(offer.model_url)
          && !unavailableCatalogModelUrls.has(String(offer.model_url)),
        );
      }
      const fittingCandidates = candidates.filter((offer) => replacementCandidateFitsRoom(offer, room));
      return questionnaireOffersWithSizeChoices(spec[0], candidates).map((offer) => ({
        ...offer,
        room_fit_checked: fittingCandidates.includes(offer),
        model_load_verified: verifiedCatalogModelUrls.has(String(offer.model_url)),
        model_load_verification: "deferred",
      }));
    }));
    state.roomFurnitureRecommendations[room.id] = groups.flat();
    revokeStaleAutoRecommendations(room, state.roomFurnitureRecommendations[room.id]);
    applyDefaultQuestionnaireFurnitureSelections(
      room,
      state.roomFurnitureRecommendations[room.id],
    );
  } catch (error) {
    console.warn("Questionnaire furniture recommendations", error);
    state.roomFurnitureRecommendationErrors[room.id] = errorMessage(error);
  } finally {
    questionnaireFurnitureInFlight.delete(roomId);
    if (String(activeQuestionnaireRoom()?.id) === roomId) {
      renderQuestionnaireFurnitureRecommendations(room);
    }
  }
}

function captureQuestionnaireFurniturePreference(room = activeQuestionnaireRoom()) {
  const furniture = roomFurnitureRequirement(room?.id);
  if (!furniture || !element.questionnaireFurniturePreference) return;
  furniture.preferenceText = element.questionnaireFurniturePreference.value.trim();
}

function updateQuestionnaireFurnitureSelection(furnitureId, selected) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const next = (furniture.selected || []).filter(
    (item) => String(item.furniture_id) !== String(furnitureId),
  );
  if (selected) {
    next.push(questionnaireFurnitureSelectionItem(offer, next.length + 1));
  }
  furniture.selected = next.map((item, index) => ({
    ...item,
    user_selected: true,
    selection_priority: index + 1,
  }));
  furniture.required = [...new Set(
    furniture.selected.map((item) => item.normalized_type),
  )];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some(
      (selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id),
    ))
    .map((item) => item.normalized_type);
  const requirement = state.roomRequirementModel.roomRequirements[room.id];
  requirement.confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom(
    "requirements",
    `「${room.label}」的家具需求已修改，第 6 步需要重新產生。`,
  );
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureVariant(normalizedType, furnitureId) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const previous = (furniture.selected || []).find(
    (item) => String(item.normalized_type) === String(normalizedType),
  );
  const next = (furniture.selected || []).filter(
    (item) => String(item.normalized_type) !== String(normalizedType),
  );
  next.push({
    ...questionnaireFurnitureSelectionItem(offer, next.length + 1),
    count: Math.max(1, Number(previous?.count) || 1),
    user_selected: true,
  });
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `已更新 ${room.label} 的家具尺寸，第 6 步需要重新建立配置。`);
  scheduleSave("requirements");
}

function updateQuestionnaireFurnitureQuantity(furnitureId, delta) {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture || !delta) return;
  captureQuestionnaireFurniturePreference(room);
  const offer = questionnaireFurnitureOffers(room).find(
    (item) => String(item.furniture_id) === String(furnitureId),
  );
  if (!offer) return;
  const selected = furniture.selected || [];
  const existing = selected.find((item) => String(item.furniture_id) === String(furnitureId));
  // Older saved questionnaire selections predate the count field.  A selected
  // item without it is one item, rather than an empty selection.
  const current = existing ? Math.max(1, Number(existing.count) || 1) : 0;
  const roomDimensionsValue = roomDimensions(room);
  const footprint = Math.max(1, Number(offer.size_cm?.width || 0) * Number(offer.size_cm?.depth || 0));
  const maximum = Math.max(1, Math.min(6, Math.floor(
    (roomDimensionsValue.areaM2 * 10_000 * 0.55) / footprint,
  ) || 1));
  const nextCount = Math.max(0, Math.min(maximum, current + Number(delta)));
  if (nextCount === current) {
    setStatus(`「${questionnaireFurnitureDisplayName(offer)}」依本房可用面積最多可先選 ${maximum} 件。`);
    return;
  }
  const next = selected.filter((item) => String(item.furniture_id) !== String(furnitureId));
  if (nextCount > 0) {
    next.push({
      ...(existing || questionnaireFurnitureSelectionItem(offer, next.length + 1)),
      count: nextCount,
      user_selected: true,
    });
  }
  furniture.selected = next.map((item, index) => ({ ...item, selection_priority: index + 1 }));
  furniture.required = [...new Set(furniture.selected.map((item) => item.normalized_type))];
  furniture.optional = questionnaireFurnitureOffers(room)
    .filter((item) => !furniture.selected.some((selectedItem) => String(selectedItem.furniture_id) === String(item.furniture_id)))
    .map((item) => item.normalized_type);
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  renderQuestionnaireFurnitureRecommendations(room);
  invalidateDownstreamFrom("requirements", `「${room.label}」的家具數量已修改，第 6 步需要重新產生。`);
  scheduleSave("requirements");
}

function refreshQuestionnaireFurnitureRecommendations() {
  const room = activeQuestionnaireRoom();
  const furniture = roomFurnitureRequirement(room?.id);
  if (!room || !furniture) return;
  captureQuestionnaireFurniturePreference(room);
  delete state.roomFurnitureRecommendations[room.id];
  state.roomRequirementModel.roomRequirements[room.id].confirmed = false;
  activeRoomFinishDraft().confirmed = false;
  invalidateDownstreamFrom("requirements", `已更新「${room.label}」的家具偏好，第 6 步需要重新產生。`);
  scheduleSave("requirements");
  void ensureQuestionnaireFurnitureRecommendations(room, { force: true });
}

  return {
    renderQuestionnaireMaterialOptions,
    questionnaireMaterialPairCards,
    renderQuestionnaireMaterialPairs,
    selectQuestionnaireMaterialPair,
    renderQuestionnaireFinishes,
    renderConditionalFeasibility,
    selectQuestionnaireStylePack,
    questionnairePackForRoom,
    questionnaireFurnitureRequest,
    catalogCandidatesForType,
    renderFurnitureSourceNotice,
    noteShortlistFallback,
    storedFurnitureShortlist,
    loadShortlistCandidates,
    shortlistCandidatesForRoom,
    ensureFurnitureShortlist,
    catalogOffersForSpec,
    catalogFallbackOffersForSpec,
    catalogOffersForRoomPlans,
    questionnaireFurniturePreferenceTags,
    renderQuestionnaireFurniturePreferenceTags,
    toggleQuestionnaireFurniturePreferenceTag,
    bedroomRoleFor,
    occupancyForRoom,
    questionnaireFurnitureSpecsForRoom,
    ensureRoomUsage,
    renderQuestionnaireRoomUsage,
    roomFurnitureRequirement,
    questionnaireFurnitureOffers,
    questionnaireFurnitureGroups,
    renderQuestionnaireFurnitureRecommendations,
    applyDefaultQuestionnaireFurnitureSelections,
    ensureQuestionnaireFurnitureRecommendations,
    captureQuestionnaireFurniturePreference,
    updateQuestionnaireFurnitureSelection,
    updateQuestionnaireFurnitureVariant,
    updateQuestionnaireFurnitureQuantity,
    refreshQuestionnaireFurnitureRecommendations,
  };
}
