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

export function normalizeDesignSchemes(saved = {}) {
  if (
    saved
    && typeof saved === "object"
    && !Array.isArray(saved)
    && Object.keys(saved).length === 0
  ) {
    saved = { schema_version: 3 };
  }
  if (Number(saved.schema_version) !== 3) {
    throw new Error("project_configuration_schema_upgrade_required");
  }
  const savedSchemes = saved?.schemes || {};
  const schemeA = {
    ...emptyScheme("A", "baseline"),
    ...(savedSchemes.A || {}),
  };
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
    schema_version: 3,
    active_scheme_id: activeId,
    locked_scheme_id: lockedId,
    room_selections: validRoomSelections(saved.room_selections),
    configuration_snapshot: saved.configuration_snapshot
      && typeof saved.configuration_snapshot === "object"
      ? clone(saved.configuration_snapshot)
      : null,
    schemes: {
      A: schemeA,
      ...(schemeB ? { B: schemeB } : {}),
    },
  };
}

function validRoomSelections(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value)
      .filter(([roomId, schemeId]) => String(roomId).trim() && ["A", "B"].includes(schemeId))
      .map(([roomId, schemeId]) => [String(roomId), schemeId]),
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

export function markSchemeLayoutsStale(designSchemes, reason) {
  Object.values(designSchemes.schemes).forEach((scheme) => {
    scheme.stale = true;
    scheme.staleReason = reason || "結構已變更，請重新計算家具配置。";
    scheme.sceneData = null;
  });
  designSchemes.locked_scheme_id = null;
}

export function structuresForScheme(structures = {}, schemeId = "A") {
  void schemeId;
  return Object.fromEntries(
    COLLECTIONS.map((collection) => [
      collection,
      clone(structures[collection] || []),
    ]),
  );
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

export function selectSchemeForRoom(designSchemes, roomId, schemeId) {
  if (!designSchemes?.schemes?.[schemeId] || !["A", "B"].includes(schemeId)) return false;
  const normalizedRoomId = String(roomId || "").trim();
  if (!normalizedRoomId) return false;
  designSchemes.room_selections = validRoomSelections(designSchemes.room_selections);
  designSchemes.room_selections[normalizedRoomId] = schemeId;
  designSchemes.configuration_snapshot = null;
  designSchemes.locked_scheme_id = null;
  return true;
}

export function allRoomsHaveSchemeSelections(designSchemes, rooms = []) {
  if (!rooms.length) return false;
  const selections = validRoomSelections(designSchemes?.room_selections);
  return rooms.every((room) => ["A", "B"].includes(selections[String(room.id)]));
}

export function selectedSchemeForRoom(designSchemes, roomId, fallback = "A") {
  const selected = validRoomSelections(designSchemes?.room_selections)[String(roomId)];
  return ["A", "B"].includes(selected) ? selected : fallback;
}
