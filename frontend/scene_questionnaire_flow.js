// 佇列 7 巨石拆分第六批：碰 state 的問卷流程，以工廠參數遮蔽法自 scene_v2.js
// 純搬家。工廠參數名與 scene_v2 模組作用域的原名完全相同（state、element、
// $$、escapeHtml、setStatus、scheduleSave、invalidateDownstreamFrom、
// renderVisualQuestionnaire、showQuestionnaireStage、activeQuestionnaireRoom、
// activeRoomRequirement），函式本體 byte 級照搬、一字不改——閉包引用自動改走
// 工廠參數，因此本體維持原縮排（不重新內縮）。scene_v2 呼叫工廠後解構回同名
// const，呼叫端零改動。這裡收四群：全屋表面一致性、初談流程、材質草稿層、
// renderDetailChoices。

import { resolveSurfaceOption } from "./scene_surface_materials.js?v=sha256-65c914d00995";
import {
  FIRST_MEETING_BUDGETS,
  FIRST_MEETING_GOALS,
  FIRST_MEETING_STEPS,
  FIRST_MEETING_TIMELINES,
  firstMeetingSummary,
  legacyBasicAnswersFromFirstMeeting,
  normalizeFirstMeeting,
} from "./scene_first_meeting.js?v=sha256-ed5e5f907eaa";
import {
  applyRoomFinishScope,
  evaluateConditionalOption,
  normalizeRoomRequirements,
} from "./scene_room_requirements.js?v=sha256-86b7bbecc47a";
import {
  CEILING_STYLES,
  LIGHT_STYLES,
  STYLE_PACKS,
} from "./scene_style_packs.js?v=sha256-fd8fa1eb64b1";
import {
  RENDER_DETAIL_FIELDS,
  firstMeetingCountOptions,
  firstMeetingStylePacks,
  isCirculationRoom,
  roomAllowsIndependentFloor,
  roomKeepsExplicitWallOverride,
  trimAccentWallSurfaces,
} from "./scene_questionnaire_data.js?v=sha256-dd94e51b2020";

export function createQuestionnaireFlow({
  state,
  element,
  $$,
  escapeHtml,
  setStatus,
  scheduleSave,
  invalidateDownstreamFrom,
  renderVisualQuestionnaire,
  showQuestionnaireStage,
  activeQuestionnaireRoom,
  activeRoomRequirement,
}) {
// 原 scene_v2 模組層變數，只有 scheduleFirstMeetingSave 讀寫，跟著搬進閉包。
let firstMeetingSaveTimer = null;

function livingRoomForCirculation() {
  return state.rooms.find((room) => {
    const type = String(room.type || room.room_type || room.visual_space_type || "").toLowerCase();
    return type === "living_room" || /客廳/.test(String(room.label || room.name || ""));
  }) || null;
}

function circulationStyleIsOverridden(room = {}) {
  return Boolean(
    state.roomRequirementModel?.roomRequirements?.[room.id]?.circulationStyleOverrideApproved,
  );
}

function copyLivingRoomStyleToCirculation(room, { force = false } = {}) {
  if (!isCirculationRoom(room)) return false;
  const livingRoom = livingRoomForCirculation();
  if (!livingRoom || livingRoom.id === room.id) return false;
  const requirements = state.roomRequirementModel?.roomRequirements || {};
  const requirement = requirements[room.id];
  const livingRequirement = requirements[livingRoom.id];
  if (!requirement || !livingRequirement || (!force && circulationStyleIsOverridden(room))) return false;
  const livingDraft = state.roomFinishDrafts?.[livingRoom.id];
  if (livingDraft) {
    state.roomFinishDrafts[room.id] = {
      ...livingDraft,
      wallOverrides: {},
      confirmed: state.roomFinishDrafts?.[room.id]?.confirmed || false,
    };
  }
  requirement.surfaces = trimAccentWallSurfaces({
    ...(livingRequirement.surfaces || {}),
  });
  requirement.climate = { ...(livingRequirement.climate || {}) };
  requirement.circulationStyleSourceRoomId = livingRoom.id;
  return true;
}

function synchronizeCirculationStyles() {
  state.rooms.filter(isCirculationRoom).forEach((room) => {
    copyLivingRoomStyleToCirculation(room);
  });
}

function wholeHouseMainFloorSurface() {
  const dryRoomFloor = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) =>
      state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.floor
    )
    .find((floor) => floor?.materialId || floor?.color);
  if (dryRoomFloor) return { ...dryRoomFloor };
  if (state.questionnaireFinishes.floorMaterial || state.questionnaireFinishes.floorColor) {
    return {
      materialId: state.questionnaireFinishes.floorMaterial || null,
      color: state.questionnaireFinishes.floorColor || null,
    };
  }
  return null;
}

function wholeHouseMainWallSurface() {
  const configured = state.questionnaireFinishes || {};
  if (configured.wallMaterial || configured.wallColor) {
    return {
      materialId: configured.wallMaterial || configured.defaultWallMaterial || null,
      color: configured.wallColor || configured.defaultWallColor || null,
    };
  }
  const dryRoomWall = state.rooms
    .filter((room) => !roomAllowsIndependentFloor(room))
    .map((room) => state.roomRequirementModel?.roomRequirements?.[room.id]?.surfaces?.wallDefault)
    .find((wall) => wall?.materialId || wall?.color);
  return dryRoomWall ? { ...dryRoomWall } : null;
}

function normalizedRoomSurfaces(room, surfaces = {}) {
  const next = trimAccentWallSurfaces(surfaces);
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  if (mainWall && !roomKeepsExplicitWallOverride(room, next)) {
    next.wallDefault = { ...mainWall };
  }
  if (!roomAllowsIndependentFloor(room) && mainFloor) {
    next.floor = { ...mainFloor };
  }
  return next;
}

function applyWholeHouseSurfaceConsistency() {
  synchronizeCirculationStyles();
  const mainWall = wholeHouseMainWallSurface();
  const mainFloor = wholeHouseMainFloorSurface();
  Object.entries(state.roomRequirementModel?.roomRequirements || {}).forEach(([roomId, requirement]) => {
    const room = state.rooms.find((candidate) => String(candidate.id) === String(roomId));
    requirement.surfaces = trimAccentWallSurfaces(requirement.surfaces || {});
    if (room && mainWall && !roomKeepsExplicitWallOverride(room, requirement.surfaces)) {
      requirement.surfaces.wallDefault = { ...mainWall };
    }
    if (room && !roomAllowsIndependentFloor(room) && mainFloor) {
      requirement.surfaces.floor = { ...mainFloor };
    }
  });
}

function normalizeSavedSceneWallSurfaces(sceneData) {
  if (!sceneData?.surface_overrides?.length) return 0;
  const mainWall = wholeHouseMainWallSurface();
  if (!mainWall?.materialId && !mainWall?.color) return 0;

  const resolvedOption = mainWall.materialId
    ? resolveSurfaceOption(sceneData.surface_catalog, "wall", mainWall.materialId)
    : null;
  let repaired = 0;
  sceneData.surface_overrides.forEach((override) => {
    const room = state.rooms.find((candidate) => String(candidate.id) === String(override.room_id));
    if (roomKeepsExplicitWallOverride(room, override)) return;
    const nextOption = resolvedOption || mainWall.materialId || override.wall_option || "auto";
    const nextColor = mainWall.color || override.wall_color_hex || null;
    if (
      override.wall_option !== nextOption
      || override.wall_color_hex !== nextColor
      || (override.wall_surface_ids || []).length
      || Object.keys(override.wall_overrides || {}).length
    ) {
      override.wall_option = nextOption;
      override.wall_color_hex = nextColor;
      override.wall_surface_ids = [];
      override.wall_overrides = {};
      repaired += 1;
    }
  });
  return repaired;
}

function firstMeetingStepIndex() {
  const index = FIRST_MEETING_STEPS.findIndex((step) => step.id === state.firstMeetingStep);
  return index >= 0 ? index : 0;
}

function scheduleFirstMeetingSave() {
  window.clearTimeout(firstMeetingSaveTimer);
  firstMeetingSaveTimer = window.setTimeout(() => {
    scheduleSave("requirements");
    element.firstMeetingStatus.textContent = "面談紀錄已保存";
  }, 240);
}

function markFirstMeetingChanged({ rerender = false } = {}) {
  state.firstMeeting = normalizeFirstMeeting({
    ...state.firstMeeting,
    started: true,
    confirmed: false,
  }, state.rooms);
  element.firstMeetingError.textContent = "";
  element.firstMeetingStatus.textContent = "正在保存面談紀錄…";
  scheduleFirstMeetingSave();
  if (rerender) renderFirstMeeting();
}

function firstMeetingQuestionMarkup(step) {
  const meeting = state.firstMeeting;
  if (step === "residents") {
    const fields = [
      ["adults", "成人", 1],
      ["children", "兒童", 0],
      ["elderly", "長輩", 0],
      ["pets", "寵物", 0],
    ];
    return `
      <header><span class="eyebrow">QUESTION 1</span><h3>這個家有哪些人使用？</h3><p>只記錄人數與會影響空間安排的特殊條件。</p></header>
      <div class="rp-first-meeting-residents">
        ${fields.map(([id, label, minimum]) => `
          <label><span>${label}</span><select data-first-meeting-resident="${id}">
            ${firstMeetingCountOptions(meeting.residents[id], { minimum })}
          </select></label>
        `).join("")}
      </div>
      <label class="rp-first-meeting-text"><span>需要特別照顧的條件 <small>選填</small></span>
        <textarea data-first-meeting-special-needs rows="3" maxlength="200" placeholder="例如：輪椅迴轉、幼兒安全、貓咪活動區">${escapeHtml(meeting.residents.specialNeeds)}</textarea>
      </label>`;
  }
  if (step === "goals") {
    return `
      <header><span class="eyebrow">QUESTION 2</span><h3>這次最想改善哪三件事？</h3><p>請選三項。點選順序就是優先順序。</p></header>
      <div class="rp-first-meeting-choice-grid">
        ${FIRST_MEETING_GOALS.map((goal) => {
          const rank = meeting.goalIds.indexOf(goal.id);
          return `<button type="button" class="rp-first-meeting-choice ${rank >= 0 ? "is-selected" : ""}"
            data-first-meeting-goal="${goal.id}"><b>${rank >= 0 ? rank + 1 : "＋"}</b><span>${goal.label}</span></button>`;
        }).join("")}
      </div>`;
  }
  if (step === "rooms") {
    return `
      <header><span class="eyebrow">QUESTION 3</span><h3>今天優先談哪些空間？</h3><p>最多三個；每個空間只留一句最重要的提醒。</p></header>
      <div class="rp-first-meeting-room-grid">
        ${state.rooms.map((room) => {
          const roomId = String(room.id);
          const selected = meeting.priorityRoomIds.includes(roomId);
          return `<article class="rp-first-meeting-room ${selected ? "is-selected" : ""}">
            <button type="button" data-first-meeting-room="${escapeHtml(roomId)}" aria-pressed="${selected}">
              <b>${selected ? meeting.priorityRoomIds.indexOf(roomId) + 1 : "＋"}</b>
              <span><strong>${escapeHtml(room.label || room.name || "未命名空間")}</strong><small>${selected ? "已列入優先討論" : "點選加入"}</small></span>
            </button>
            ${selected ? `<label><span>一句提醒</span><textarea data-first-meeting-room-note="${escapeHtml(roomId)}" rows="2" maxlength="160" placeholder="例如：希望餐桌可坐六人">${escapeHtml(meeting.roomNotes[roomId] || "")}</textarea></label>` : ""}
          </article>`;
        }).join("")}
      </div>`;
  }
  if (step === "constraints") {
    return `
      <header><span class="eyebrow">QUESTION 4</span><h3>有什麼一定要保留，或不能改？</h3><p>沒有也可以直接下一題；一段話就夠。</p></header>
      <label class="rp-first-meeting-text rp-first-meeting-text-large"><span>不可變條件 <small>選填</small></span>
        <textarea data-first-meeting-constraints rows="6" maxlength="300" placeholder="例如：保留鋼琴、廚房位置不動、不能拆除主臥衣櫃">${escapeHtml(meeting.constraints)}</textarea>
      </label>`;
  }
  if (step === "budget") {
    const options = (values, selected) => values.map((value) =>
      `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`
    ).join("");
    return `
      <header><span class="eyebrow">QUESTION 5</span><h3>預算與希望完成時間？</h3><p>先抓範圍即可，不需要在初談做細項估價。</p></header>
      <div class="rp-first-meeting-budget-grid">
        <label><span>設計與工程預算</span><select data-first-meeting-budget>${options(FIRST_MEETING_BUDGETS, meeting.budgetRange)}</select></label>
        <label><span>希望完成時間</span><select data-first-meeting-timeline>${options(FIRST_MEETING_TIMELINES, meeting.targetTimeline)}</select></label>
      </div>`;
  }
  if (step === "style") {
    return `
      <header><span class="eyebrow">QUESTION 6</span><h3>選兩張喜歡，一張不喜歡</h3><p>不用替風格命名；設計師只要追問「你喜歡或不喜歡哪裡」。</p></header>
      <div class="rp-first-meeting-style-grid">
        ${firstMeetingStylePacks().map((pack) => {
          const liked = meeting.likedStylePackIds.includes(pack.id);
          const disliked = meeting.dislikedStylePackId === pack.id;
          return `<article class="rp-first-meeting-style ${liked ? "is-liked" : ""} ${disliked ? "is-disliked" : ""}">
            <img src="${escapeHtml(pack.sourceImage)}" alt="${escapeHtml(pack.styleLabel)}參考圖" loading="lazy" />
            <div><strong>${escapeHtml(pack.styleLabel)}</strong><small>${escapeHtml(pack.name)}</small></div>
            <footer>
              <button type="button" data-first-meeting-style-like="${escapeHtml(pack.id)}" aria-pressed="${liked}">${liked ? "✓ 喜歡" : "喜歡"}</button>
              <button type="button" data-first-meeting-style-dislike="${escapeHtml(pack.id)}" aria-pressed="${disliked}">${disliked ? "✓ 不喜歡" : "不喜歡"}</button>
            </footer>
          </article>`;
        }).join("")}
      </div>
      <label class="rp-first-meeting-text"><span>設計師筆記 <small>選填</small></span>
        <textarea data-first-meeting-style-note rows="3" maxlength="200" placeholder="例如：喜歡留白和木色，不喜歡深色與厚重線板">${escapeHtml(meeting.styleNote)}</textarea>
      </label>`;
  }

  const summary = firstMeetingSummary(meeting, state.rooms, STYLE_PACKS);
  const followUp = meeting.budgetRange === "尚未確定" && meeting.targetTimeline !== "時間彈性"
    ? "完成時間較明確，但預算尚未確定：第一輪提案要以哪個預算上限為準？"
    : "沒有明顯衝突，可直接進入第一輪配置。";
  return `
    <header><span class="eyebrow">MEETING SUMMARY</span><h3>初談摘要</h3><p>這份摘要會成為第一輪配置的依據，細部選件留到下一階段。</p></header>
    <div class="rp-first-meeting-summary">
      <section><span>居住者</span><strong>${escapeHtml(summary.residents)}</strong><small>${escapeHtml(summary.specialNeeds)}</small></section>
      <section><span>前三項目標</span><strong>${summary.goals.map((goal, index) => `${index + 1}. ${escapeHtml(goal)}`).join("　")}</strong></section>
      <section><span>優先空間</span><div>${summary.priorityRooms.map((room) => `<p><b>${escapeHtml(room.label)}</b>${escapeHtml(room.note)}</p>`).join("")}</div></section>
      <section><span>不可變條件</span><strong>${escapeHtml(summary.constraints)}</strong></section>
      <section><span>預算與時程</span><strong>${escapeHtml(summary.budgetTimeline)}</strong></section>
      <section><span>風格方向</span><strong>喜歡：${escapeHtml(summary.likedStyles.join("、"))}</strong><small>不喜歡：${escapeHtml(summary.dislikedStyle)}${summary.styleNote ? `；${escapeHtml(summary.styleNote)}` : ""}</small></section>
      <section class="rp-first-meeting-follow-up"><span>唯一待確認</span><strong>${escapeHtml(followUp)}</strong></section>
    </div>`;
}

function renderFirstMeeting() {
  state.firstMeeting = normalizeFirstMeeting(state.firstMeeting, state.rooms);
  const currentIndex = firstMeetingStepIndex();
  const step = FIRST_MEETING_STEPS[currentIndex];
  element.firstMeetingProgress.innerHTML = FIRST_MEETING_STEPS.map((item, index) => `
    <button type="button" data-first-meeting-step="${item.id}"
      class="${index === currentIndex ? "is-active" : ""} ${index < currentIndex ? "is-complete" : ""}"
      ${index > currentIndex ? "disabled" : ""}><b>${index + 1}</b><span>${item.label}</span></button>
  `).join("");
  element.firstMeetingPanel.innerHTML = firstMeetingQuestionMarkup(step.id);
  const guides = {
    residents: ["約 1 分鐘", "先確認誰會使用這個家，以及需要優先照顧的條件。"],
    goals: ["約 2 分鐘", "請客戶取捨到三項；排序比補充更多答案更重要。"],
    rooms: ["約 2 分鐘", "挑出最多三個空間，每個空間只記一句關鍵提醒。"],
    constraints: ["約 1 分鐘", "記錄不可拆、必須保留或工程上不能碰的條件。"],
    budget: ["約 1 分鐘", "先確認可接受的範圍與期待時程，不在此處拆估價。"],
    style: ["約 2 分鐘", "用圖片談感受，不要求客戶先懂風格名稱。"],
    summary: ["約 1 分鐘", "一起朗讀摘要；若有衝突，只追問畫面上的一件事。"],
  };
  [element.firstMeetingTime.textContent, element.firstMeetingGuideText.textContent] = guides[step.id];
  element.firstMeetingBack.disabled = currentIndex === 0;
  element.firstMeetingNext.textContent = step.id === "summary" ? "確認並建立 2D＋3D 配置" : "下一題";
  element.firstMeetingStatus.textContent = step.id === "summary"
    ? "確認後會建立第一輪方案"
    : `第 ${currentIndex + 1}／6 題 · 作答後自動保存`;
  element.firstMeetingError.textContent = "";
}

function applyFirstMeetingToRequirements() {
  state.firstMeeting = normalizeFirstMeeting({ ...state.firstMeeting, confirmed: true }, state.rooms);
  const pack = STYLE_PACKS.find((item) => item.id === state.firstMeeting.likedStylePackIds[0])
    || STYLE_PACKS[0];
  const ceiling = CEILING_STYLES.find((item) => item.styles.includes(pack.styleId))
    || CEILING_STYLES[0];
  const light = LIGHT_STYLES.find((item) => item.styles.includes(pack.styleId))
    || LIGHT_STYLES[0];
  state.questionnaireFinishes = {
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial: pack.wall.surfaceOption,
    wallColor: pack.wall.color,
    floorMaterial: pack.floor.surfaceOption,
    floorColor: pack.floor.color,
    ceilingMaterial: "flat-paint",
    ceilingStyle: ceiling.id,
    lightStyle: light.id,
    ceilingColor: "#f4f1eb",
  };
  state.basicAnswers = legacyBasicAnswersFromFirstMeeting(state.firstMeeting, STYLE_PACKS);
  state.basicConfirmed = true;
  state.roomRequirementModel = normalizeRoomRequirements(
    state.roomRequirementModel,
    state.rooms,
    {
      basic: state.basicAnswers,
      basicConfirmed: true,
      finishes: state.questionnaireFinishes,
    },
  );
  state.roomRequirementModel.globalProfile = { ...state.basicAnswers };
  state.roomRequirementModel.globalConfirmed = true;
  state.rooms.forEach((room) => {
    const requirement = state.roomRequirementModel.roomRequirements[room.id];
    if (!requirement) return;
    const roomId = String(room.id);
    requirement.axisAnswers = {};
    requirement.climate = { ...(requirement.climate || {}), airConditioning: "designer-review" };
    requirement.surfaces = {
      ...(requirement.surfaces || {}),
      paletteId: pack.id,
      wallDefault: { materialId: pack.wall.surfaceOption, color: pack.wall.color },
      wallOverrides: {},
      wallSurfaceIds: [],
      floor: { materialId: pack.floor.surfaceOption, color: pack.floor.color },
      ceiling: {
        materialId: "flat-paint",
        styleId: ceiling.id,
        lightingId: light.id,
        color: "#f4f1eb",
      },
    };
    requirement.specialRequests = state.firstMeeting.roomNotes[roomId] || "";
    requirement.feasibility = [];
    requirement.confirmed = true;
  });
  state.visualCatalogVersion = "first-meeting-1.0";
  state.visualAnswers = {};
  state.skippedVisualSpaceTypes = [];
  state.activeStyleId = pack.styleId;
  state.activeStylePackId = pack.id;
  applyWholeHouseSurfaceConsistency();
}

async function randomizeRequirementsForTesting() {
  if (!state.rooms.length) {
    element.firstMeetingError.textContent = "請先完成空間確認，再填入 Demo 範例。";
    return;
  }
  const packs = firstMeetingStylePacks();
  const priorityRoomIds = state.rooms.slice(0, 3).map((room) => String(room.id));
  state.firstMeeting = normalizeFirstMeeting({
    started: true,
    residents: { adults: 2, children: 1, elderly: 0, pets: 1, specialNeeds: "幼兒活動區避免尖角，並保留寵物休息位置。" },
    goalIds: ["circulation", "storage", "daylight"],
    priorityRoomIds,
    roomNotes: Object.fromEntries(priorityRoomIds.map((roomId, index) => [
      roomId,
      ["希望日常動線更順", "需要整合主要收納", "改善自然採光"][index] || "優先改善使用方式",
    ])),
    constraints: "保留現有餐桌；廚房與浴室管線位置不變。",
    budgetRange: "100–200 萬",
    targetTimeline: "3–6 個月",
    likedStylePackIds: packs.slice(0, 2).map((pack) => pack.id),
    dislikedStylePackId: packs[4]?.id || packs[2]?.id,
    styleNote: "喜歡明亮、留白與自然木色；不希望空間過暗或太厚重。",
  }, state.rooms);
  state.firstMeetingStep = "summary";
  invalidateDownstreamFrom("requirements", "已填入初談 Demo 範例，後續配置已標記需重新生成。");
  renderFirstMeeting();
  setStatus("已填入六題初談 Demo 範例，請與客戶一起確認摘要。");
  scheduleSave("requirements");
}

function activeQuestionnairePack() {
  const draft = activeRoomFinishDraft();
  return STYLE_PACKS.find(
    (pack) => pack.id === draft.stylePackId,
  ) || STYLE_PACKS.find((pack) => pack.styleId === state.activeStyleId) || STYLE_PACKS[0];
}

function activeRoomFinishDraft() {
  const requirement = activeRoomRequirement();
  const roomId = requirement?.roomId;
  if (!roomId) return state.questionnaireFinishes;
  if (!state.roomFinishDrafts[roomId]) {
    const surfaces = requirement.surfaces || {};
    state.roomFinishDrafts[roomId] = {
      confirmed: requirement.confirmed === true,
      stylePackId: surfaces.paletteId || null,
      wallMaterial: surfaces.wallDefault?.materialId || null,
      wallColor: surfaces.wallDefault?.color || null,
      defaultWallMaterial: surfaces.wallDefault?.materialId || null,
      defaultWallColor: surfaces.wallDefault?.color || null,
      wallOverrides: { ...(surfaces.wallOverrides || {}) },
      wallPreference: surfaces.wallPreference || "",
      floorMaterial: surfaces.floor?.materialId || null,
      floorColor: surfaces.floor?.color || null,
      floorPreference: surfaces.floorPreference || "",
      ceilingMaterial: surfaces.ceiling?.materialId || null,
      ceilingStyle: surfaces.ceiling?.styleId || null,
      lightStyle: surfaces.ceiling?.lightingId || null,
      ceilingColor: surfaces.ceiling?.color || "#f4f1eb",
      airConditioning: requirement.climate?.airConditioning || "",
    };
  }
  return state.roomFinishDrafts[roomId];
}

function confirmQuestionnaireFinishes() {
  const room = activeQuestionnaireRoom();
  const requirement = activeRoomRequirement();
  const draft = activeRoomFinishDraft();
  if (!room || !requirement) return;
  if (state.questionnaireStage === "rooms") {
    requirement.confirmed = true;
    delete requirement.preferenceSuggestion;
    element.requirementsError.textContent = "";
    invalidateDownstreamFrom("requirements", "逐房用途或家具已修改，後續配置需要重新產生。");
    const nextRoom = state.rooms.find(
      (candidate) => !state.roomRequirementModel.roomRequirements[candidate.id]?.confirmed,
    );
    if (nextRoom) {
      state.roomRequirementModel.activeRoomId = nextRoom.id;
      renderVisualQuestionnaire();
      setStatus(`已確認「${room.label}」；接著確認「${nextRoom.label}」。`);
      scheduleSave("requirements");
    } else {
      showQuestionnaireStage("summary");
    }
    return;
  }
  const pack = draft.stylePackId ? activeQuestionnairePack() : STYLE_PACKS[0];
  Object.assign(draft, {
    ...draft,
    confirmed: true,
    stylePackId: pack.id,
    wallMaterial: draft.wallMaterial || pack.wall.surfaceOption,
    wallColor: element.questionnaireWallColor.value,
    floorMaterial: draft.floorMaterial || pack.floor.surfaceOption,
    floorColor: element.questionnaireFloorColor.value,
    ceilingMaterial: element.questionnaireCeilingMaterial.value,
    ceilingStyle: element.questionnaireCeilingStyle.value,
    lightStyle: element.questionnaireLightStyle.value,
    ceilingColor: element.questionnaireCeilingColor.value,
    airConditioning: element.questionnaireAirConditioning.value || "auto",
  });
  delete requirement.preferenceSuggestion;
  requirement.axisAnswers = {};
  const conditionalOptionIds = room.type === "bathroom"
    ? ["bathtub", "double_vanity"]
    : (room.type === "dining_room" || room.type === "kitchen"
      ? ["large_dining_table"]
      : []);
  requirement.feasibility = conditionalOptionIds
    .map((optionId) => evaluateConditionalOption(room, optionId, state.structures.doors))
    .filter((result) => !result.feasible)
    .map((result) => ({
      optionId: result.optionId,
      forcePlacement: false,
      message: result.warnings[0],
    }));
  requirement.specialRequests = [];
  requirement.climate.airConditioning = draft.airConditioning;
  requirement.surfaces = {
    ...requirement.surfaces,
    paletteId: draft.stylePackId,
    // 牆地生圖偏好文字：同時進 RAG 查詢與第 8 步生圖需求，不得只留在前端。
    wallPreference: draft.wallPreference || "",
    floorPreference: draft.floorPreference || "",
    wallDefault: {
      materialId: draft.defaultWallMaterial || draft.wallMaterial,
      color: draft.defaultWallColor || draft.wallColor,
    },
    wallOverrides: { ...(requirement.surfaces.wallOverrides || {}), ...(draft.wallOverrides || {}) },
    floor: { materialId: draft.floorMaterial, color: draft.floorColor },
    ceiling: {
      materialId: draft.ceilingMaterial,
      styleId: draft.ceilingStyle,
      lightingId: draft.lightStyle,
      color: draft.ceilingColor,
    },
  };
  if (state.selectedQuestionnaireWallId) {
    requirement.surfaces.wallSurfaceIds = [
      ...new Set([
        ...(requirement.surfaces.wallSurfaceIds || []),
        state.selectedQuestionnaireWallId,
      ]),
    ];
  }
  requirement.confirmed = true;
  state.questionnaireFinishes = { ...draft };
  const scope = element.questionnaireFinishScope.value;
  const selectedRoomIds = $$("input:checked", element.questionnaireFinishRoomTargets)
    .map((input) => input.value);
  state.roomRequirementModel = applyRoomFinishScope(
    state.roomRequirementModel,
    room.id,
    scope,
    selectedRoomIds,
  );
  applyWholeHouseSurfaceConsistency();
  state.roomRequirementModel.roomRequirements[room.id].confirmed = true;
  if (scope !== "room") {
    state.roomFinishDrafts = {};
  }
  element.requirementsError.textContent = "";
  invalidateDownstreamFrom("requirements", "風格與材質偏好已修改，後續配置需要重新產生。");
  state.activeStylePackId = pack.id;
  const nextRoom = state.rooms.find(
    (candidate) => !state.roomRequirementModel.roomRequirements[candidate.id]?.confirmed,
  );
  if (nextRoom) {
    state.roomRequirementModel.activeRoomId = nextRoom.id;
    state.selectedQuestionnaireWallId = null;
    renderVisualQuestionnaire();
    setStatus(
      `已確認「${room.label}」；接著確認「${nextRoom.label}」。`,
    );
    scheduleSave("requirements");
  } else {
    showQuestionnaireStage("profile");
  }
}

// 只回傳使用者真的選過的項目；留白代表「依設計師建議」，不進 prompt。
function renderDetailChoices(finishes = state.questionnaireFinishes || {}) {
  return RENDER_DETAIL_FIELDS.flatMap(({ key, label, labels }) => {
    const value = finishes[key];
    if (!value) return [];
    return [`${label}：${labels[value] || value}`];
  });
}

function wholeHouseFinishDraft() {
  const fallbackPack = STYLE_PACKS.find(
    (pack) => pack.id === state.activeStylePackId,
  ) || STYLE_PACKS[0];
  const draft = state.questionnaireFinishes || {};
  return {
    stylePackId: draft.stylePackId || fallbackPack.id,
    wallMaterial: draft.wallMaterial || fallbackPack.wall.surfaceOption,
    wallColor: draft.wallColor || fallbackPack.wall.color,
    floorMaterial: draft.floorMaterial || fallbackPack.floor.surfaceOption,
    floorColor: draft.floorColor || fallbackPack.floor.color,
    ceilingMaterial: draft.ceilingMaterial || "flat-paint",
    ceilingStyle: draft.ceilingStyle || CEILING_STYLES[0].id,
    lightStyle: draft.lightStyle || LIGHT_STYLES[0].id,
    ceilingColor: draft.ceilingColor || "#f4f1eb",
    airConditioning: draft.airConditioning || "auto",
    applyStyleToAllRooms: draft.applyStyleToAllRooms !== false,
    applyAirConditioningToEligibleRooms: draft.applyAirConditioningToEligibleRooms !== false,
    // 生圖細節：3D 場景沒有對應物件，只在第 8 步 prompt 用。空字串＝未指定，
    // 交給生圖模型自行判斷，不阻擋問卷完成。
    ...Object.fromEntries(RENDER_DETAIL_FIELDS.map(
      ({ key }) => [key, draft[key] || ""],
    )),
  };
}

  return {
    livingRoomForCirculation,
    circulationStyleIsOverridden,
    copyLivingRoomStyleToCirculation,
    synchronizeCirculationStyles,
    wholeHouseMainFloorSurface,
    wholeHouseMainWallSurface,
    normalizedRoomSurfaces,
    applyWholeHouseSurfaceConsistency,
    normalizeSavedSceneWallSurfaces,
    firstMeetingStepIndex,
    scheduleFirstMeetingSave,
    markFirstMeetingChanged,
    firstMeetingQuestionMarkup,
    renderFirstMeeting,
    applyFirstMeetingToRequirements,
    randomizeRequirementsForTesting,
    activeQuestionnairePack,
    activeRoomFinishDraft,
    confirmQuestionnaireFinishes,
    renderDetailChoices,
    wholeHouseFinishDraft,
  };
}
