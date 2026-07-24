import {
  buildRoomPreferenceSummary,
  cloneRoomAnswer,
  materialPreferenceOptions,
  normalizeAxisChoice,
  normalizeQuickValues,
  questionnaireCompletion,
  QUESTIONNAIRE_SCHEMA_VERSION,
  questionnaireRoomIdentity,
  reconcileRoomQuestionnaireState,
  roomQuestionTemplate,
  roomTechnicalAxes,
  validateCeilingPreference,
  WHOLE_HOUSE_QUESTIONS,
} from "./scene_requirements.js?v=sha256-b1ec853ceeac";
import {
  questionnairePlanPoint,
  questionnairePolygonLabelPoint,
  questionnaireRoomAnswerChanged,
  questionnaireRoomAnswerHasDraft,
  hydrateQuestionnaireTechnicalChoices,
  readQuestionnaireTechnicalChoices,
  renderQuestionnaireAxisChoices,
  renderQuestionnaireAxisCustomApproach,
  renderQuestionnaireTechnicalChoices,
  showQuestionnaireStep,
  updateQuestionnaireAxisCustomApproach,
  validateQuestionnaireStage,
  validateQuestionnaireTechnicalCeiling,
  validateQuestionnaireTechnicalChoices,
} from "./questionnaire_wizard.js?v=sha256-c49a7466e396";
import {
  clearQuestionnaireConflictDraft,
  restoreQuestionnaireConflictDraft,
  storeQuestionnaireConflictDraft,
} from "./scene_workflow.js?v=sha256-d0efd6389df5";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character],
);
const token = location.pathname.split("/").filter(Boolean).at(-1);
const state = {
  project: null,
  floorplan: null,
  rooms: [],
  requirements: {},
  baseRequirements: {},
  basic: {},
  answers: {},
  keepExistingRoomIds: [],
  activeRoomId: null,
  activeBasicQuestionIndex: 0,
  activeRoomQuestionIndex: 0,
  roomWarnings: [],
  activeWarningIndex: 0,
  history: [],
  revision: "",
  minimumFinishedHeightCm: 240,
};
let persistQueue = Promise.resolve();
let draftPersistTimer = null;

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.detail;
    const error = new Error(
      typeof detail === "object"
        ? detail.message || detail.code || "問卷載入失敗。"
        : detail || "問卷載入失敗。",
    );
    error.status = response.status;
    throw error;
  }
  return payload;
}

const clone = (value) => (
  value == null ? value : JSON.parse(JSON.stringify(value))
);

function currentQuestionnaireRequirements() {
  return {
    schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
    basic: state.basic,
    basicConfirmed: true,
    rooms: state.answers,
    keepExistingRoomIds: state.keepExistingRoomIds,
    settings: {
      minimumFinishedHeightCm: state.minimumFinishedHeightCm,
    },
  };
}

function clientPlanPoint(point) {
  return questionnairePlanPoint(point, state.floorplan);
}

function renderClientRoomLocator() {
  const locator = $("#questionnaire-client-room-locator");
  const image = $("#questionnaire-client-plan-image");
  const stage = $("#questionnaire-client-plan-stage");
  const overlay = $("#questionnaire-client-plan-overlay");
  const size = state.floorplan?.image_size_px;
  const width = Number(size?.width);
  const height = Number(size?.height);
  const available = Boolean(
    state.floorplan?.source_url
    && Number.isFinite(width)
    && width > 0
    && Number.isFinite(height)
    && height > 0
    && state.rooms.some((room) => Array.isArray(room.polygon_cm) && room.polygon_cm.length >= 3)
  );
  locator.hidden = !available;
  if (!available) return;
  if (image.getAttribute("src") !== state.floorplan.source_url) {
    image.src = state.floorplan.source_url;
  }
  stage.style.aspectRatio = `${width} / ${height}`;
  overlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
  overlay.innerHTML = state.rooms.map((room) => {
    const points = (room.polygon_cm || []).map(clientPlanPoint);
    if (points.length < 3) return "";
    const center = questionnairePolygonLabelPoint(points);
    const active = room.id === state.activeRoomId;
    return `
      <g data-client-plan-room="${escapeHtml(room.id)}" role="button" tabindex="0"
        aria-label="切換到${escapeHtml(room.label)}">
        <polygon points="${points.map((point) => `${point.x},${point.y}`).join(" ")}"
          fill="${active ? "rgba(47,111,135,.3)" : "rgba(36,107,85,.08)"}"
          stroke="${active ? "#2f6f87" : "#7b8f86"}" stroke-width="${active ? 6 : 3}"/>
        <text x="${center.x}" y="${center.y}" text-anchor="middle" dominant-baseline="central"
          class="${active ? "is-active" : ""}">${escapeHtml(room.label)}</text>
      </g>
    `;
  }).join("");
}

function renderBasic() {
  $("#questionnaire-client-basic-fields").innerHTML = WHOLE_HOUSE_QUESTIONS.map((question) => {
    const inputType = question.type === "multi" ? "checkbox" : "radio";
    return `
      <fieldset data-client-basic="${escapeHtml(question.id)}">
        <legend>${escapeHtml(question.label)}</legend>
        <div class="rp-choice-grid">
          ${question.options.map((option) => `
            <label>
              <input type="${inputType}" name="client-${escapeHtml(question.id)}" value="${escapeHtml(option.value)}"/>
              <span>${escapeHtml(option.label)}</span>
            </label>
          `).join("")}
        </div>
        <label class="rp-question-note">
          <span>補充（選填）</span>
          <textarea rows="2" placeholder="${escapeHtml(question.example)}"></textarea>
        </label>
      </fieldset>
    `;
  }).join("");
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-client-basic="${question.id}"]`);
    const values = Array.isArray(state.basic[question.id])
      ? state.basic[question.id]
      : [state.basic[question.id]];
    $$("input", host).forEach((input) => { input.checked = values.includes(input.value); });
    host.querySelector("textarea").value = state.basic.notes?.[question.id] || "";
    if (question.type === "multi" && question.exclusiveValues?.length) {
      host.addEventListener("change", (event) => {
        const changed = event.target.closest("input[type='checkbox']");
        if (!changed?.checked) return;
        const exclusive = new Set(question.exclusiveValues);
        $$("input[type='checkbox']", host).forEach((input) => {
          if (input === changed) return;
          if (exclusive.has(changed.value) || exclusive.has(input.value)) input.checked = false;
        });
      });
    }
  });
  renderBasicQuestionStep();
}

function renderBasicQuestionStep(index = state.activeBasicQuestionIndex) {
  const questions = $$("[data-client-basic]", $("#questionnaire-client-basic-fields"));
  if (!questions.length) return;
  const step = showQuestionnaireStep(questions, index);
  state.activeBasicQuestionIndex = step.index;
  const definition = WHOLE_HOUSE_QUESTIONS[state.activeBasicQuestionIndex];
  $("#questionnaire-client-basic-progress").textContent =
    `基本資料 ${state.activeBasicQuestionIndex + 1}/${step.total} · ${definition.label}`;
  $("#questionnaire-client-basic-previous").disabled = state.activeBasicQuestionIndex === 0;
  $("#questionnaire-client-basic-next").hidden =
    state.activeBasicQuestionIndex === step.total - 1;
  $("#questionnaire-client-basic-done").hidden =
    state.activeBasicQuestionIndex !== step.total - 1;
}

function advanceBasicQuestion(direction) {
  if (direction > 0) {
    const definition = WHOLE_HOUSE_QUESTIONS[state.activeBasicQuestionIndex];
    const host = $(`[data-client-basic="${definition.id}"]`);
    if (definition.required && !host.querySelector("input:checked")) {
      $("#questionnaire-client-status").textContent = `請先回答「${definition.label}」。`;
      return;
    }
  }
  $("#questionnaire-client-status").textContent = "";
  renderBasicQuestionStep(state.activeBasicQuestionIndex + direction);
}

function collectBasic() {
  const basic = { notes: {} };
  WHOLE_HOUSE_QUESTIONS.forEach((question) => {
    const host = $(`[data-client-basic="${question.id}"]`);
    const values = $$("input:checked", host).map((input) => input.value);
    basic[question.id] = question.type === "multi"
      ? normalizeQuickValues(question, values)
      : values[0] || "";
    basic.notes[question.id] = host.querySelector("textarea").value.trim();
  });
  return basic;
}

function renderRoomTabs() {
  $("#questionnaire-client-room-tabs").innerHTML = state.rooms.map((room) => {
    const resolved = state.answers[room.id]?.confirmed || state.keepExistingRoomIds.includes(room.id);
    return `<button type="button" data-client-room="${escapeHtml(room.id)}" class="${room.id === state.activeRoomId ? "is-active" : ""}">${escapeHtml(room.label)}${resolved ? " · 已完成" : ""}</button>`;
  }).join("");
}

function readActiveClientRoomAnswer({ confirmed = false } = {}) {
  const room = state.rooms.find((item) => item.id === state.activeRoomId);
  const axisHost = $("#questionnaire-client-room-axes");
  if (!room || !axisHost.children.length) return null;
  const template = roomQuestionTemplate(room.type);
  const existing = state.answers[room.id] || {};
  const axes = { ...(existing.axes || {}) };
  const customNotes = { ...(existing.customNotes || {}) };
  Object.assign(
    axes,
    readQuestionnaireTechnicalChoices({
      container: $("#questionnaire-client-room-technical"),
      axes: roomTechnicalAxes(room.type),
      dataAttribute: "data-client-technical-axis",
    }),
  );
  template.axes.forEach((axis) => {
    const host = $(`[data-client-axis="${axis.id}"]`);
    axes[axis.id] = host?.querySelector("input:checked")?.value || "";
    customNotes[axis.id] = host?.querySelector("textarea")?.value.trim() || "";
  });
  return {
    schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
    roomIdentity: questionnaireRoomIdentity(room),
    confirmed,
    axes,
    customNotes,
    stageNotes: {
      uses: $("#questionnaire-client-room-use-note").value.trim(),
      furniture: $("#questionnaire-client-room-furniture-note").value.trim(),
    },
    uses: $$("input:checked", $("#questionnaire-client-room-uses"))
      .map((input) => input.value),
    furniture: $$("input:checked", $("#questionnaire-client-room-furniture"))
      .map((input) => input.value),
    personalNeeds: $("#questionnaire-client-room-note").value.trim(),
    materialPreferences: {
      wall: Array.from($("#questionnaire-client-wall").selectedOptions)
        .map((option) => option.value),
      floor: Array.from($("#questionnaire-client-floor").selectedOptions)
        .map((option) => option.value),
      furniture: Array.from($("#questionnaire-client-furniture-material").selectedOptions)
        .map((option) => option.value),
      color: Array.from($("#questionnaire-client-color").selectedOptions)
        .map((option) => option.value),
      finish: Array.from($("#questionnaire-client-finish").selectedOptions)
        .map((option) => option.value),
      cuts: $("#questionnaire-client-material-cuts").value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    },
  };
}

function captureActiveClientRoomDraft() {
  const roomId = state.activeRoomId;
  const draft = readActiveClientRoomAnswer();
  if (!roomId || !draft || !questionnaireRoomAnswerHasDraft(draft)) return false;
  if (!questionnaireRoomAnswerChanged(draft, state.answers[roomId])) return false;
  state.answers[roomId] = draft;
  state.keepExistingRoomIds = state.keepExistingRoomIds.filter((id) => id !== roomId);
  return true;
}

function renderClientRoomIntegratedSummary() {
  const room = state.rooms.find((item) => item.id === state.activeRoomId);
  const host = $("#questionnaire-client-room-summary");
  if (!room || !host) return;
  const draft = readActiveClientRoomAnswer() || state.answers[room.id] || {};
  const summary = buildRoomPreferenceSummary(room, draft);
  state.roomWarnings = summary.warnings;
  state.activeWarningIndex = Math.min(
    Math.max(0, state.activeWarningIndex),
    Math.max(0, state.roomWarnings.length - 1),
  );
  host.innerHTML = `
    <strong>${escapeHtml(summary.headline)}</strong>
    ${summary.basis.length
      ? `<ul>${summary.basis.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "<p>完成 A／B 對照題後，這裡會整理選擇理由與配置依據。</p>"}
    ${summary.other_approaches.length
      ? `<p><strong>補充想法：</strong>${escapeHtml(summary.other_approaches.join("；"))}</p>`
      : ""}
  `;
  renderClientQuestionnaireWarning();
}

function renderClientQuestionnaireWarning() {
  const card = $("#questionnaire-client-warning");
  const warning = state.roomWarnings[state.activeWarningIndex];
  card.hidden = !warning;
  if (!warning) return;
  $("#questionnaire-client-warning-position").textContent = warning.position;
  $("#questionnaire-client-warning-room").textContent = warning.roomLabel;
  $("#questionnaire-client-warning-reason").textContent = warning.reason;
  $("#questionnaire-client-warning-previous").disabled =
    state.activeWarningIndex <= 0;
  $("#questionnaire-client-warning-next").disabled =
    state.activeWarningIndex >= state.roomWarnings.length - 1;
}

function reportClientDraftError(error) {
  $("#questionnaire-client-status").textContent =
    error.message === "project_version_conflict"
      ? "草稿已有較新的修改，請重新整理後再繼續。"
      : `草稿保存失敗：${error.message}`;
}

function saveCapturedClientDraft(captured) {
  if (!captured) return;
  persist({ quiet: true }).catch(reportClientDraftError);
}

function scheduleActiveClientDraftSave() {
  clearTimeout(draftPersistTimer);
  draftPersistTimer = setTimeout(() => {
    saveCapturedClientDraft(captureActiveClientRoomDraft());
  }, 500);
}

function selectRoom(
  roomId,
  recordHistory = true,
  captureDraft = true,
  forceReload = false,
) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  const roomChanged = state.activeRoomId !== roomId;
  if (
    !forceReload
    && !roomChanged
    && $("#questionnaire-client-room-axes").children.length
  ) return;
  clearTimeout(draftPersistTimer);
  const draftCaptured = captureDraft
    && state.activeRoomId
    && state.activeRoomId !== roomId
    && captureActiveClientRoomDraft();
  saveCapturedClientDraft(draftCaptured);
  if (recordHistory && state.activeRoomId && state.activeRoomId !== roomId) {
    state.history.push(state.activeRoomId);
  }
  state.activeRoomId = roomId;
  if (roomChanged) state.activeWarningIndex = 0;
  $("#questionnaire-client-room-locator-title").textContent = room.label;
  renderClientRoomLocator();
  const template = roomQuestionTemplate(room.type);
  const materialOptions = materialPreferenceOptions(room.type);
  const existing = state.answers[room.id];
  $("#questionnaire-client-room-title").textContent = `${room.label}的使用偏好`;
  $("#questionnaire-client-room-axes").innerHTML = template.axes.map((axis) => `
    <fieldset class="rp-room-axis" data-client-axis="${escapeHtml(axis.id)}">
      <legend>${escapeHtml(axis.label)}</legend>
      <p>${escapeHtml(axis.prompt)}</p>
      ${renderQuestionnaireAxisChoices({
        axisDefinition: axis,
        inputName: `client-axis-${axis.id}`,
      })}
      ${renderQuestionnaireAxisCustomApproach({
        axisLabel: axis.label,
        customExample: axis.customExample,
        existingNote: existing?.customNotes?.[axis.id],
      })}
    </fieldset>
  `).join("");
  template.axes.forEach((axis) => {
    const host = $(`[data-client-axis="${axis.id}"]`);
    const selected = normalizeAxisChoice(axis, existing?.axes?.[axis.id]);
    $$("input", host).forEach((input) => { input.checked = input.value === selected; });
    host.querySelector("textarea").value = existing?.customNotes?.[axis.id] || "";
  });
  $("#questionnaire-client-room-uses").innerHTML = template.uses.map((value) =>
    `<label><input type="checkbox" value="${escapeHtml(value)}"/><span>${escapeHtml(value)}</span></label>`
  ).join("");
  $("#questionnaire-client-room-furniture").innerHTML = template.furniture.map((value) =>
    `<label><input type="checkbox" value="${escapeHtml(value)}"/><span>${escapeHtml(value)}</span></label>`
  ).join("");
  const technicalAxes = roomTechnicalAxes(room.type);
  $("#questionnaire-client-room-technical").innerHTML =
    renderQuestionnaireTechnicalChoices({
      axes: technicalAxes,
      inputPrefix: "client-technical",
      dataAttribute: "data-client-technical-axis",
    });
  hydrateQuestionnaireTechnicalChoices({
    container: $("#questionnaire-client-room-technical"),
    axes: technicalAxes,
    values: existing?.axes || {},
    dataAttribute: "data-client-technical-axis",
    normalizeChoice: normalizeAxisChoice,
  });
  [
    ["#questionnaire-client-wall", materialOptions.wall],
    ["#questionnaire-client-floor", materialOptions.floor],
    ["#questionnaire-client-furniture-material", materialOptions.furniture],
    ["#questionnaire-client-color", materialOptions.color],
    ["#questionnaire-client-finish", materialOptions.finish],
  ].forEach(([selector, options]) => {
    $(selector).innerHTML = options.map((option) =>
      `<option value="${escapeHtml(option.value)}" data-image-key="${escapeHtml(option.imageKey)}">${escapeHtml(option.label)}</option>`
    ).join("");
  });
  $$("input", $("#questionnaire-client-room-uses")).forEach((input) => {
    input.checked = (existing?.uses || []).includes(input.value);
  });
  if (!(existing?.uses || []).length) {
    const firstUse = $("#questionnaire-client-room-uses input");
    if (firstUse) firstUse.checked = true;
  }
  $$("input", $("#questionnaire-client-room-furniture")).forEach((input) => {
    input.checked = (existing?.furniture || []).includes(input.value);
  });
  $("#questionnaire-client-room-use-note").value = existing?.stageNotes?.uses || "";
  $("#questionnaire-client-room-furniture-note").value =
    existing?.stageNotes?.furniture || "";
  $("#questionnaire-client-room-note").value =
    existing?.personalNeeds === "無" ? "" : (existing?.personalNeeds || "");
  const preferences = existing?.materialPreferences || {};
  [
    ["#questionnaire-client-wall", preferences.wall || []],
    ["#questionnaire-client-floor", preferences.floor || []],
    ["#questionnaire-client-furniture-material", preferences.furniture || []],
    ["#questionnaire-client-color", preferences.color || []],
    ["#questionnaire-client-finish", preferences.finish || []],
  ].forEach(([selector, values]) => {
    Array.from($(selector).options).forEach((option) => {
      option.selected = values.includes(option.value);
    });
  });
  $("#questionnaire-client-material-cuts").value = (preferences.cuts || []).join("\n");
  $("#questionnaire-client-copy-source").innerHTML = [
    '<option value="">選擇已填寫空間</option>',
    ...state.rooms
      .filter((item) => item.id !== room.id && state.answers[item.id]?.confirmed)
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`),
  ].join("");
  state.activeRoomQuestionIndex = 0;
  renderRoomTabs();
  refreshProgress();
  renderClientRoomIntegratedSummary();
  renderRoomQuestionStep();
}

function clientRoomQuestionStages() {
  return [
    ...$$("[data-client-axis]", $("#questionnaire-client-room-axes")),
    ...$$("[data-client-room-stage]"),
  ];
}

function clientRoomStageLabel(stage) {
  return stage.querySelector("legend")?.textContent
    || stage.querySelector("span")?.textContent
    || "整合確認";
}

function renderRoomQuestionStep(index = state.activeRoomQuestionIndex) {
  const stages = clientRoomQuestionStages();
  if (!stages.length) return;
  const step = showQuestionnaireStep(stages, index);
  state.activeRoomQuestionIndex = step.index;
  const room = state.rooms.find((item) => item.id === state.activeRoomId);
  $("#questionnaire-client-room-progress").textContent =
    `${room?.label || "空間"} · ${clientRoomStageLabel(step.current)} `
    + `${state.activeRoomQuestionIndex + 1}/${step.total}`;
  $("#questionnaire-client-room-previous-question").disabled =
    state.activeRoomQuestionIndex === 0;
  $("#questionnaire-client-room-next-question").hidden =
    state.activeRoomQuestionIndex === step.total - 1;
  $("#questionnaire-client-room-save").hidden =
    state.activeRoomQuestionIndex !== step.total - 1;
}

function advanceRoomQuestion(direction) {
  const stages = clientRoomQuestionStages();
  const stage = stages[state.activeRoomQuestionIndex];
  if (direction > 0 && stage) {
    const technicalValidation = validateQuestionnaireTechnicalChoices({
      container: stage,
      dataAttribute: "data-client-technical-axis",
    });
    if (
      stage.dataset.clientRoomStage === "technical"
      && !technicalValidation.ready
    ) {
      $("#questionnaire-client-status").textContent =
        "請先完成這個房間的天花、冷氣與燈光選擇。";
      return;
    }
    const result = validateQuestionnaireStage(stage, {
      axisDatasetKey: "clientAxis",
      usesDatasetKey: "clientRoomStage",
    });
    if (result.kind === "axis") {
      $("#questionnaire-client-status").textContent =
        `請先完成「${result.label}」。`;
      return;
    }
    if (result.kind === "uses") {
      $("#questionnaire-client-status").textContent = "請至少選擇一項空間用途。";
      return;
    }
    if (result.ready && stage.dataset.clientRoomStage === "technical") {
      const room = state.rooms.find((item) => item.id === state.activeRoomId);
      const ceilingResult = validateQuestionnaireTechnicalCeiling({
        container: stage,
        axes: roomTechnicalAxes(room?.type),
        dataAttribute: "data-client-technical-axis",
        roomHeightCm: Number(state.floorplan?.room_height_cm || 270),
        minimumFinishedHeightCm: state.minimumFinishedHeightCm,
        validatePreference: validateCeilingPreference,
      });
      if (!ceilingResult.ready) {
        $("#questionnaire-client-status").textContent =
          `此天花方案預估完成淨高 ${ceilingResult.finishedHeightCm} 公分，低於設計師設定的 `
          + `${ceilingResult.minimumFinishedHeightCm} 公分，不能繼續。`;
        return;
      }
    }
  }
  $("#questionnaire-client-status").textContent = "";
  renderRoomQuestionStep(state.activeRoomQuestionIndex + direction);
}

function persist({ quiet = false } = {}) {
  const save = async () => {
    let result;
    try {
      result = await api(`/api/questionnaire/${token}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_updated_at: state.revision,
          requirements: currentQuestionnaireRequirements(),
        }),
      });
    } catch (error) {
      if (error.status === 409) {
        storeQuestionnaireConflictDraft({
          token,
          baseUpdatedAt: state.revision,
          baseRequirements: state.baseRequirements,
          requirements: currentQuestionnaireRequirements(),
        });
      }
      throw error;
    }
    state.revision = result.updated_at;
    state.baseRequirements = clone(currentQuestionnaireRequirements());
    clearQuestionnaireConflictDraft({ token });
    if (!quiet) $("#questionnaire-client-status").textContent = "已保存到本專案。";
  };
  persistQueue = persistQueue.then(save, save);
  return persistQueue;
}

function refreshProgress() {
  const completion = questionnaireCompletion({
    basicAnswers: state.basic,
    rooms: state.rooms,
    answers: state.answers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  $("#questionnaire-client-progress").textContent =
    `房間 ${completion.completedRooms}/${completion.totalRooms}；未完成 ${completion.incomplete.length} 項`;
}

async function saveActiveRoom(keepExisting = false) {
  clearTimeout(draftPersistTimer);
  const room = state.rooms.find((item) => item.id === state.activeRoomId);
  if (!room) return;
  if (keepExisting) {
    state.keepExistingRoomIds = [...new Set([...state.keepExistingRoomIds, room.id])];
    state.answers[room.id] = {
      schemaVersion: QUESTIONNAIRE_SCHEMA_VERSION,
      confirmed: false,
      keepExisting: true,
      roomIdentity: questionnaireRoomIdentity(room),
    };
  } else {
    const template = roomQuestionTemplate(room.type);
    const answer = readActiveClientRoomAnswer({ confirmed: true });
    const missing = template.axes.find((axis) => {
      return axis.required && !answer?.axes[axis.id];
    });
    if (missing || !answer?.uses.length) {
      $("#questionnaire-client-status").textContent =
        missing ? `請完成「${missing.label}」。` : "請至少選擇一項空間用途。";
      if (missing) {
        renderRoomQuestionStep(
          clientRoomQuestionStages().findIndex(
            (stage) => stage.dataset.clientAxis === missing.id
          )
        );
      } else {
        renderRoomQuestionStep(
          clientRoomQuestionStages().findIndex(
            (stage) => stage.dataset.clientRoomStage === "uses"
          )
        );
      }
      return;
    }
    state.keepExistingRoomIds = state.keepExistingRoomIds.filter((id) => id !== room.id);
    state.answers[room.id] = answer;
  }
  await persist();
  const completion = questionnaireCompletion({
    basicAnswers: state.basic,
    rooms: state.rooms,
    answers: state.answers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  if (completion.nextIncomplete?.roomId) {
    selectRoom(completion.nextIncomplete.roomId, true, false);
  }
  else refreshProgress();
}

async function startRooms() {
  state.basic = collectBasic();
  const completion = questionnaireCompletion({
    basicAnswers: state.basic,
    rooms: [],
    answers: {},
  });
  if (!completion.ready) {
    const first = completion.nextIncomplete;
    $("#questionnaire-client-status").textContent = `請完成「${first.label}」。`;
    renderBasicQuestionStep(
      WHOLE_HOUSE_QUESTIONS.findIndex((question) => question.id === first.questionId)
    );
    return;
  }
  await persist();
  $("#questionnaire-client-basic").hidden = true;
  $("#questionnaire-client-room").hidden = false;
  $("#questionnaire-previous").hidden = false;
  selectRoom(state.activeRoomId || state.rooms[0]?.id);
}

function jumpIncomplete() {
  const completion = questionnaireCompletion({
    basicAnswers: state.basic,
    rooms: state.rooms,
    answers: state.answers,
    keepExistingRoomIds: state.keepExistingRoomIds,
  });
  if (!completion.nextIncomplete) {
    $("#questionnaire-client-status").textContent = "問卷已全部完成。";
  } else if (completion.nextIncomplete.kind === "basic") {
    saveCapturedClientDraft(captureActiveClientRoomDraft());
    $("#questionnaire-client-basic").hidden = false;
    $("#questionnaire-client-room").hidden = true;
    $("#questionnaire-previous").hidden = true;
    renderBasicQuestionStep(
      WHOLE_HOUSE_QUESTIONS.findIndex(
        (question) => question.id === completion.nextIncomplete.questionId
      )
    );
  } else {
    $("#questionnaire-client-basic").hidden = true;
    $("#questionnaire-client-room").hidden = false;
    $("#questionnaire-previous").hidden = false;
    selectRoom(completion.nextIncomplete.roomId);
  }
}

async function initialize() {
  try {
    const payload = await api(`/api/questionnaire/${token}`);
    state.project = payload.project;
    state.floorplan = payload.floorplan || null;
    state.revision = payload.updated_at;
    state.rooms = payload.rooms;
    state.baseRequirements = clone(payload.requirements || {});
    const restoredRequirements = restoreQuestionnaireConflictDraft({
      token,
      serverRequirements: state.baseRequirements,
      updatedAt: state.revision,
    });
    state.requirements = restoredRequirements || state.baseRequirements;
    state.basic = state.requirements.basic || {};
    const reconciled = reconcileRoomQuestionnaireState({
      rooms: state.rooms,
      answers: state.requirements.rooms || {},
      keepExistingRoomIds: state.requirements.keepExistingRoomIds || [],
    });
    state.answers = reconciled.answers;
    state.keepExistingRoomIds = reconciled.keepExistingRoomIds;
    state.minimumFinishedHeightCm = Number(
      state.requirements.settings?.minimumFinishedHeightCm || 240
    );
    state.activeRoomId = state.rooms[0]?.id || null;
    $("#questionnaire-project-name").textContent = state.project.name;
    renderBasic();
    renderRoomTabs();
    refreshProgress();
    if (state.requirements.basicConfirmed) {
      $("#questionnaire-client-basic").hidden = true;
      $("#questionnaire-client-room").hidden = false;
      $("#questionnaire-previous").hidden = false;
      selectRoom(state.activeRoomId);
    }
    if (restoredRequirements) {
      $("#questionnaire-client-status").textContent =
        "已合併伺服器最新內容並復原這台裝置尚未送出的問卷草稿；保存成功後才會清除草稿。";
    }
  } catch (error) {
    $("#questionnaire-client-status").textContent = error.message;
  }
}

function randomizeActiveRoom() {
  $$("[data-client-axis]", $("#questionnaire-client-room-axes")).forEach((host) => {
    const choices = $$("input[type='radio']", host);
    const choice = choices[Math.floor(Math.random() * choices.length)];
    if (choice) choice.checked = true;
  });
  $("#questionnaire-client-status").textContent = "已提供隨機靈感；確認此房間前不會保存。";
}

function copySelectedRoom() {
  const sourceRoomId = $("#questionnaire-client-copy-source").value;
  const copied = cloneRoomAnswer(state.answers[sourceRoomId], { sourceRoomId });
  if (!copied || !state.activeRoomId) {
    $("#questionnaire-client-status").textContent = "請先選擇一個已完成空間。";
    return;
  }
  state.answers[state.activeRoomId] = copied;
  selectRoom(state.activeRoomId, false, false, true);
  $("#questionnaire-client-status").textContent = "已複製共同設定；請補完這個房間專屬題目後再確認。";
}

async function runSaveAction(action) {
  const buttons = [
    $("#questionnaire-client-basic-done"),
    $("#questionnaire-client-room-save"),
    $("#questionnaire-client-room-skip"),
  ];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    await action();
  } catch (error) {
    $("#questionnaire-client-status").textContent =
      error.message === "project_version_conflict"
        ? "問卷已有較新的修改；草稿已保留。重新整理後會與最新內容合併。"
        : `保存失敗：${error.message}`;
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

$("#questionnaire-client-basic-done").addEventListener("click", () => runSaveAction(startRooms));
$("#questionnaire-client-basic-previous").addEventListener("click", () => advanceBasicQuestion(-1));
$("#questionnaire-client-basic-next").addEventListener("click", () => advanceBasicQuestion(1));
$("#questionnaire-client-room-save").addEventListener("click", () => runSaveAction(() => saveActiveRoom(false)));
$("#questionnaire-client-room-skip").addEventListener("click", () => runSaveAction(() => saveActiveRoom(true)));
$("#questionnaire-client-random").addEventListener("click", randomizeActiveRoom);
$("#questionnaire-client-copy").addEventListener("click", copySelectedRoom);
$("#questionnaire-client-room-previous-question").addEventListener("click", () => advanceRoomQuestion(-1));
$("#questionnaire-client-room-next-question").addEventListener("click", () => advanceRoomQuestion(1));
$("#questionnaire-client-warning-previous").addEventListener("click", () => {
  state.activeWarningIndex = Math.max(0, state.activeWarningIndex - 1);
  renderClientQuestionnaireWarning();
});
$("#questionnaire-client-warning-next").addEventListener("click", () => {
  state.activeWarningIndex = Math.min(
    state.roomWarnings.length - 1,
    state.activeWarningIndex + 1,
  );
  renderClientQuestionnaireWarning();
});
$("#questionnaire-client-room-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-client-room]");
  if (button) selectRoom(button.dataset.clientRoom);
});
$("#questionnaire-client-plan-overlay").addEventListener("click", (event) => {
  const room = event.target.closest("[data-client-plan-room]");
  if (room) selectRoom(room.dataset.clientPlanRoom);
});
$("#questionnaire-client-plan-overlay").addEventListener("keydown", (event) => {
  if (!["Enter", " "].includes(event.key)) return;
  const room = event.target.closest("[data-client-plan-room]");
  if (!room) return;
  event.preventDefault();
  selectRoom(room.dataset.clientPlanRoom);
});
$("#questionnaire-client-room").addEventListener("input", (event) => {
    updateQuestionnaireAxisCustomApproach(
      event.target.closest(".rp-axis-custom-approach"),
    );
  renderClientRoomIntegratedSummary();
  scheduleActiveClientDraftSave();
});
$("#questionnaire-client-room").addEventListener("change", () => {
  renderClientRoomIntegratedSummary();
  scheduleActiveClientDraftSave();
});
$("#questionnaire-next-incomplete").addEventListener("click", jumpIncomplete);
$("#questionnaire-previous").addEventListener("click", () => {
  const previousRoomId = state.history.pop();
  if (previousRoomId) selectRoom(previousRoomId, false);
  else {
    clearTimeout(draftPersistTimer);
    saveCapturedClientDraft(captureActiveClientRoomDraft());
    $("#questionnaire-client-basic").hidden = false;
    $("#questionnaire-client-room").hidden = true;
    $("#questionnaire-previous").hidden = true;
  }
});

initialize();
