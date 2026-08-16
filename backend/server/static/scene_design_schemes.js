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
    schema_version: 2,
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
  // 方案不再承載結構改造。第 4 步確認後，牆、門、窗、樑、柱是全案共用
  // 的基準資料；A、B 僅比較家具的選擇、位置與朝向。
  void structures;
  return false;
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
