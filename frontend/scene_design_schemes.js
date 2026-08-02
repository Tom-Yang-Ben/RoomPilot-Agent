const COLLECTIONS = ["walls", "doors", "windows", "beams", "columns"];

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function emptyScheme(id, kind) {
  return {
    id,
    kind,
    label: id === "A" ? "方案 A" : "方案 B",
    furniture: [],
    sceneData: null,
    stale: false,
    staleReason: "",
  };
}

export function normalizeDesignSchemes(saved = {}, legacy = {}) {
  const savedSchemes = saved?.schemes || {};
  const schemeA = {
    ...emptyScheme("A", "baseline"),
    ...(savedSchemes.A || {}),
  };
  if (!schemeA.furniture.length && Array.isArray(legacy.furniture)) {
    schemeA.furniture = clone(legacy.furniture);
  }
  if (!schemeA.sceneData && legacy.sceneData) {
    schemeA.sceneData = clone(legacy.sceneData);
  }
  const schemeB = savedSchemes.B
    ? {
        ...emptyScheme("B", "alternative"),
        ...savedSchemes.B,
      }
    : null;
  const activeId = saved.active_scheme_id === "B" && schemeB ? "B" : "A";
  const lockedId = ["A", "B"].includes(saved.locked_scheme_id)
    && (saved.locked_scheme_id !== "B" || schemeB)
    ? saved.locked_scheme_id
    : null;
  return {
    schema_version: 1,
    active_scheme_id: activeId,
    locked_scheme_id: lockedId,
    schemes: {
      A: schemeA,
      ...(schemeB ? { B: schemeB } : {}),
    },
  };
}

export function compactDesignSchemesForSpace(designSchemes = {}) {
  const compact = clone(designSchemes) || {};
  compact.schemes = Object.fromEntries(
    Object.entries(compact.schemes || {}).map(([id, scheme]) => [
      id,
      {
        ...scheme,
        furniture: [],
        sceneData: null,
      },
    ]),
  );
  return compact;
}

export function hasRenovationChanges(structures = {}) {
  const walls = structures.walls || [];
  if (walls.some((wall) => wall.demolition_candidate === true)) return true;
  return COLLECTIONS.some((collection) =>
    (structures[collection] || []).some((item) => item.scheme_id === "B")
  );
}

export function ensureSchemeB(designSchemes, { reason = "manual" } = {}) {
  if (!designSchemes.schemes.B) {
    designSchemes.schemes.B = {
      ...emptyScheme("B", "alternative"),
      created_reason: reason,
    };
  }
  return designSchemes.schemes.B;
}

export function deleteSchemeB(designSchemes) {
  delete designSchemes.schemes.B;
  if (designSchemes.active_scheme_id === "B") designSchemes.active_scheme_id = "A";
  if (designSchemes.locked_scheme_id === "B") designSchemes.locked_scheme_id = null;
}

export function markSchemeLayoutsStale(designSchemes, reason) {
  Object.values(designSchemes.schemes).forEach((scheme) => {
    scheme.stale = true;
    scheme.staleReason = reason || "結構已變更，請重新計算家具配置。";
    scheme.sceneData = null;
  });
  designSchemes.locked_scheme_id = null;
}

export function structuresForScheme(structures = {}, schemeId = "A") {
  const output = Object.fromEntries(
    COLLECTIONS.map((collection) => [
      collection,
      clone((structures[collection] || []).filter((item) =>
        schemeId === "B" || item.scheme_id !== "B"
      )),
    ]),
  );
  if (schemeId !== "B") return output;

  const demolishedWallIds = new Set(
    output.walls
      .filter((wall) => wall.demolition_candidate === true)
      .map((wall) => wall.id),
  );
  output.walls = output.walls.filter((wall) => !demolishedWallIds.has(wall.id));
  for (const collection of ["doors", "windows"]) {
    output[collection] = output[collection].filter((opening) => {
      if (!demolishedWallIds.has(opening.host_wall_id)) return true;
      return opening.host_wall_relation_uncertain === true;
    });
  }
  return output;
}

export function attachedOpenings(structures = {}, wallId) {
  return ["doors", "windows"].flatMap((collection) =>
    (structures[collection] || [])
      .filter((item) => item.host_wall_id === wallId)
      .map((item) => ({ collection, item }))
  );
}

export function persistActiveScheme(designSchemes, {
  furniture,
  sceneData,
} = {}) {
  const active = designSchemes.schemes[designSchemes.active_scheme_id];
  if (!active) return;
  if (Array.isArray(furniture)) active.furniture = clone(furniture);
  if (sceneData !== undefined) active.sceneData = clone(sceneData);
}

export function activateScheme(designSchemes, schemeId) {
  if (!designSchemes.schemes[schemeId]) return null;
  designSchemes.active_scheme_id = schemeId;
  return clone(designSchemes.schemes[schemeId]);
}

