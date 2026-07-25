export const DESIGN_PREFERENCE_SCHEMA_VERSION = "1.0";
export const DESIGN_SCHEME_SCHEMA_VERSION = "1.0";

export const DESIGN_STYLES = Object.freeze([
  { id: "scandinavian_1", label: "北歐自然木質", styleId: "scandinavian" },
  { id: "japanese_1", label: "日式侘寂自然", styleId: "japanese" },
  { id: "modern_minimal_1", label: "現代簡約", styleId: "modern_minimal" },
  { id: "cream_1", label: "奶油米白", styleId: "cream" },
  { id: "industrial_1", label: "黑鐵水泥", styleId: "industrial" },
  { id: "american_1", label: "美式鄉村溫馨", styleId: "american" },
]);

export const FALLBACK_SCHEME_BLUEPRINTS = Object.freeze([
  {
    id: "scheme-1",
    title: "方案 1｜保留優先",
    summary: "先滿足必要家具與既有格局，保留較多走道與調整空間。",
    policy: "preserve",
  },
  {
    id: "scheme-2",
    title: "方案 2｜需求平衡",
    summary: "平衡主要家具、收納與通行，是目前的建議起點。",
    policy: "balanced",
  },
  {
    id: "scheme-3",
    title: "方案 3｜機能加強",
    summary: "在可用空間內增加輔助家具與收納，仍須通過家具引擎。",
    policy: "functional",
  },
]);

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

export function normalizeDesignPreferences({
  styleId = "",
  wholeHouse = {},
  rooms = {},
  notes = "",
  confirmed = false,
  styleConfirmed = false,
  materialsConfirmed = false,
} = {}) {
  return {
    schemaVersion: DESIGN_PREFERENCE_SCHEMA_VERSION,
    styleId: String(styleId || ""),
    confirmed: confirmed === true,
    styleConfirmed: styleConfirmed === true,
    materialsConfirmed: materialsConfirmed === true,
    wholeHouse: {
      wallSurfaceId: String(wholeHouse.wallSurfaceId || ""),
      floorSurfaceId: String(wholeHouse.floorSurfaceId || ""),
      wallColor: String(wholeHouse.wallColor || "#f4efe4"),
      floorColor: String(wholeHouse.floorColor || "#c9a77d"),
    },
    rooms: clone(rooms || {}),
    notes: String(notes || ""),
  };
}

export function designPreferenceGate(preferences) {
  const normalized = normalizeDesignPreferences(preferences);
  const missing = [];
  if (!normalized.styleId) missing.push("style");
  if (!normalized.wholeHouse.wallSurfaceId) missing.push("wall_surface");
  if (!normalized.wholeHouse.floorSurfaceId) missing.push("floor_surface");
  return {
    ready: missing.length === 0,
    missing,
    preferences: normalized,
  };
}

export function buildFallbackSchemeSet({
  furnitureByPolicy = {},
  preferences = {},
} = {}) {
  const normalizedPreferences = normalizeDesignPreferences(preferences);
  return {
    schemaVersion: DESIGN_SCHEME_SCHEMA_VERSION,
    activeSchemeId: "scheme-2",
    generatedAt: new Date().toISOString(),
    schemes: FALLBACK_SCHEME_BLUEPRINTS.map((blueprint) => ({
      ...blueprint,
      status: "editable",
      furniture: clone(furnitureByPolicy[blueprint.policy] || []),
      preferences: clone(normalizedPreferences),
      generation: {
        source: "rule_fallback",
        ragStatus: "pending",
        agentStatus: "pending",
        placementEngine: "roompilot.engine",
      },
    })),
  };
}

export function replaceSchemeFurniture(schemeSet, schemeId, furniture) {
  const next = clone(schemeSet);
  next.schemes = (next.schemes || []).map((scheme) => (
    scheme.id === schemeId
      ? { ...scheme, furniture: clone(furniture || []), edited: true }
      : scheme
  ));
  return next;
}

export function replaceSchemePreferences(schemeSet, schemeId, preferences) {
  const next = clone(schemeSet);
  next.schemes = (next.schemes || []).map((scheme) => (
    scheme.id === schemeId
      ? {
        ...scheme,
        preferences: normalizeDesignPreferences(preferences),
        edited: true,
      }
      : scheme
  ));
  return next;
}

export function selectScheme(schemeSet, schemeId) {
  if (!(schemeSet?.schemes || []).some((scheme) => scheme.id === schemeId)) {
    return clone(schemeSet);
  }
  return { ...clone(schemeSet), activeSchemeId: schemeId };
}

export function activeScheme(schemeSet) {
  return (schemeSet?.schemes || []).find(
    (scheme) => scheme.id === schemeSet.activeSchemeId,
  ) || schemeSet?.schemes?.[0] || null;
}

export function schemeGenerationContract(schemeSet) {
  const generations = (schemeSet?.schemes || []).map((scheme) => scheme.generation || {});
  const aggregateStatus = (key) => {
    const connectedCount = generations.filter((item) => item[key] === "connected").length;
    if (generations.length > 0 && connectedCount === generations.length) return "connected";
    if (connectedCount > 0) return "partial";
    return "pending";
  };
  return {
    ragStatus: aggregateStatus("ragStatus"),
    agentStatus: aggregateStatus("agentStatus"),
    placementEngine: "roompilot.engine",
  };
}

export function isSchemePreviewCurrent({
  requestRevision,
  currentRevision,
  requestedSchemeId,
  activeSchemeId,
  activeView,
} = {}) {
  return requestRevision === currentRevision
    && requestedSchemeId === activeSchemeId
    && activeView === "3d";
}
