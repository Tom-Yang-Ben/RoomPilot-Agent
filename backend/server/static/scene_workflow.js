export const WORKFLOW_SCHEMA_VERSION = 2;
export const WORKFLOW_STORAGE_KEY = "roompilot.workflow.v2";

export const WORKFLOW_STEPS = Object.freeze([
  "project",
  "upload",
  "recognition",
  "calibration",
  "space_confirmation",
  "requirements",
  "layout_2d",
  "white_model_3d",
  "realistic_3d",
  "proposal_review",
  "ai_render",
]);

export const WORKFLOW_PANEL_BY_STEP = Object.freeze({
  project: "project",
  upload: "upload",
  recognition: "scale",
  calibration: "scale",
  space_confirmation: "space",
  requirements: "requirements",
  layout_2d: "layout-2d",
  white_model_3d: "white-model-3d",
  realistic_3d: "white-model-3d",
  proposal_review: "proposal-review",
  ai_render: "ai-render",
});

export function shouldReplayPendingSave(pendingSave, serverProject) {
  try {
    const payload = typeof pendingSave === "string" ? JSON.parse(pendingSave) : pendingSave;
    const baseUpdatedAt = String(payload?.base_updated_at || "");
    const serverUpdatedAt = String(serverProject?.updated_at || "");
    return Boolean(baseUpdatedAt && serverUpdatedAt && baseUpdatedAt === serverUpdatedAt);
  } catch {
    return false;
  }
}

const REQUIRED_COMPLETIONS = Object.freeze({
  upload: ["project"],
  recognition: ["project", "upload"],
  calibration: ["project", "upload", "recognition"],
  space_confirmation: ["project", "upload", "recognition", "calibration"],
  requirements: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
  ],
  layout_2d: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
  ],
  white_model_3d: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
  ],
  realistic_3d: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
    "white_model_3d",
  ],
  proposal_review: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
    "white_model_3d",
    "realistic_3d",
  ],
  ai_render: [
    "project",
    "upload",
    "recognition",
    "calibration",
    "space_confirmation",
    "requirements",
    "layout_2d",
    "white_model_3d",
    "realistic_3d",
    "proposal_review",
  ],
});

function storageKey(projectId) {
  return `${WORKFLOW_STORAGE_KEY}:${projectId}`;
}

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function initialState(projectId) {
  return {
    schemaVersion: WORKFLOW_SCHEMA_VERSION,
    projectId,
    currentStep: "project",
    completed: [],
    data: {},
    staleFrom: null,
    updatedAt: new Date().toISOString(),
  };
}

function validCompletion(step, data) {
  if (step === "project") return Boolean(String(data?.name || "").trim());
  if (step === "upload") return Boolean(String(data?.filename || "").trim());
  if (step === "recognition") return data?.engine === "cody" || data?.engine === "dxf";
  if (step === "calibration") return Number(data?.distanceCm) > 0;
  if (step === "space_confirmation") {
    return data?.roomsConfirmed === true
      && data?.structureConfirmed === true
      && data?.proportionsConfirmed === true;
  }
  if (step === "requirements") {
    return data?.basicConfirmed === true && data?.roomsResolved === true;
  }
  if (step === "layout_2d") return data?.confirmed === true;
  if (step === "white_model_3d") {
    const expectedFurnitureCount = Number(data?.expectedFurnitureCount);
    return data?.confirmed === true
      && (
        expectedFurnitureCount === 0
        || Number(data?.visibleFurnitureCount) > 0
      );
  }
  if (step === "realistic_3d") return data?.confirmed === true;
  if (step === "proposal_review") {
    const camera = data?.masterView?.camera;
    return data?.confirmed === true
      && Array.isArray(camera?.position_cm)
      && camera.position_cm.length === 3
      && Array.isArray(camera?.target_cm)
      && camera.target_cm.length === 3
      && Number(camera?.fov_deg) > 0;
  }
  if (step === "ai_render") return data?.confirmed === true;
  return false;
}

function canEnter(state, step) {
  if (!WORKFLOW_STEPS.includes(step)) return false;
  const required = REQUIRED_COMPLETIONS[step] || [];
  return required.every((item) => state.completed.includes(item));
}

function createController(state, storage) {
  const persist = () => {
    state.updatedAt = new Date().toISOString();
    storage?.setItem(storageKey(state.projectId), JSON.stringify(state));
  };

  const markDownstreamStale = (step) => {
    const stepIndex = WORKFLOW_STEPS.indexOf(step);
    if (stepIndex < 0) return;
    const downstream = state.completed.filter(
      (item) => WORKFLOW_STEPS.indexOf(item) > stepIndex,
    );
    if (!downstream.length) return;
    state.staleFrom = step;
    state.completed = state.completed.filter(
      (item) => WORKFLOW_STEPS.indexOf(item) <= stepIndex,
    );
    downstream.forEach((item) => delete state.data[item]);
  };

  return {
    get schemaVersion() { return state.schemaVersion; },
    get projectId() { return state.projectId; },
    get currentStep() { return state.currentStep; },
    get completed() { return [...state.completed]; },
    get data() { return clone(state.data); },
    get staleFrom() { return state.staleFrom; },
    canEnter(step) { return canEnter(state, step); },
    canAnalyzeFloorplan() {
      const confirmation = state.data.floorplan_confirmation || {};
      const privacy = state.data.privacy || {};
      return state.completed.includes("project")
        && state.completed.includes("upload")
        && (
          confirmation.confirmed === true
          || (
            privacy.accepted === true
            && privacy.projectOnly === true
            && privacy.noTraining === true
          )
        );
    },
    setFloorplanConfirmation(confirmation = {}) {
      state.data.floorplan_confirmation = {
        confirmed: confirmation.confirmed === true,
        confirmedAt: confirmation.confirmed === true ? new Date().toISOString() : null,
      };
      persist();
      return state.data.floorplan_confirmation.confirmed;
    },
    setPrivacyConsent(consent = {}) {
      state.data.privacy = {
        accepted: consent.accepted === true,
        projectOnly: consent.projectOnly === true,
        noTraining: consent.noTraining === true,
        termsVersion: String(consent.termsVersion || "2026-07-17"),
        acceptedAt: consent.accepted === true ? new Date().toISOString() : null,
      };
      persist();
      return state.data.privacy.accepted;
    },
    setBasicProfile(profile = {}) {
      state.data.basic_profile = clone(profile);
      persist();
      return clone(state.data.basic_profile);
    },
    setRecognition({ rooms = [], reviewItems = [], engine = "cody" } = {}) {
      state.data.recognition = {
        engine,
        rooms: clone(rooms),
        reviewItems: clone(reviewItems),
      };
      persist();
      return clone(state.data.recognition);
    },
    resolveReviewItem(itemId, correction = {}) {
      const item = (state.data.recognition?.reviewItems || [])
        .find((candidate) => candidate.id === itemId);
      if (!item) return false;
      item.status = "resolved";
      item.correction = clone(correction);
      persist();
      return true;
    },
    setRoomBrief(roomId, brief = {}) {
      state.data.room_briefs = state.data.room_briefs || {};
      state.data.room_briefs[roomId] = {
        ...(state.data.room_briefs[roomId] || {}),
        ...clone(brief),
      };
      persist();
      return true;
    },
    setSpaceChanges(changes = []) {
      state.data.space_changes = clone(changes);
      persist();
      return clone(state.data.space_changes);
    },
    setCostReport(report = null) {
      state.data.cost_report = clone(report);
      persist();
      return clone(state.data.cost_report);
    },
    getDesignReadiness() {
      const blockers = [];
      if (!this.canAnalyzeFloorplan()) blockers.push("project_setup_incomplete");
      if (!state.completed.includes("recognition")) blockers.push("recognition_missing");
      if (!state.completed.includes("calibration")) blockers.push("calibration_missing");
      if (!state.completed.includes("space_confirmation")) {
        blockers.push("space_confirmation_incomplete");
      }
      return { ready: blockers.length === 0, blockers, incompleteRooms: [] };
    },
    goTo(step) {
      if (!canEnter(state, step)) return false;
      state.currentStep = step;
      persist();
      return true;
    },
    complete(step, data = {}) {
      if (!WORKFLOW_STEPS.includes(step) || !validCompletion(step, data)) return false;
      markDownstreamStale(step);
      state.data[step] = { ...(state.data[step] || {}), ...clone(data) };
      if (!state.completed.includes(step)) state.completed.push(step);
      state.currentStep = step;
      persist();
      return true;
    },
    invalidateFrom(step) {
      const stepIndex = WORKFLOW_STEPS.indexOf(step);
      if (stepIndex < 0) return false;
      const invalidated = state.completed.filter(
        (item) => WORKFLOW_STEPS.indexOf(item) >= stepIndex,
      );
      if (!invalidated.length) return true;
      state.staleFrom = step;
      state.completed = state.completed.filter(
        (item) => WORKFLOW_STEPS.indexOf(item) < stepIndex,
      );
      invalidated.forEach((item) => delete state.data[item]);
      persist();
      return true;
    },
    reset() {
      storage?.removeItem(storageKey(state.projectId));
      state = initialState(state.projectId);
      return true;
    },
    toJSON() { return clone(state); },
  };
}

export function createWorkflow({ projectId, storage = globalThis.localStorage } = {}) {
  if (!projectId) throw new Error("projectId is required");
  const state = initialState(projectId);
  const controller = createController(state, storage);
  storage?.setItem(storageKey(projectId), JSON.stringify(state));
  return controller;
}

export function restoreWorkflow({
  projectId,
  storage = globalThis.localStorage,
  snapshot = null,
} = {}) {
  if (!projectId) throw new Error("projectId is required");
  try {
    const parsed = snapshot
      || JSON.parse(storage?.getItem(storageKey(projectId)) || "null");
    if (
      parsed?.schemaVersion === WORKFLOW_SCHEMA_VERSION
      && parsed.projectId === projectId
    ) {
      const controller = createController(clone(parsed), storage);
      storage?.setItem(storageKey(projectId), JSON.stringify(controller.toJSON()));
      return controller;
    }
  } catch (error) {
    console.warn("無法還原 RoomPilot 專案流程，將建立新狀態。", error);
  }
  return createWorkflow({ projectId, storage });
}
