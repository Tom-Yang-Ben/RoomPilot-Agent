const GEOMETRY_SCHEMA_VERSION = "2.0";

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function legacyMeterPath(value, path = "project") {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const nested = legacyMeterPath(value[index], `${path}[${index}]`);
      if (nested) return nested;
    }
    return "";
  }
  if (!value || typeof value !== "object") return "";
  for (const [key, item] of Object.entries(value)) {
    if (key.endsWith("_m") || key === "m_per_px" || key === "distance_m") {
      return `${path}.${key}`;
    }
    const nested = legacyMeterPath(item, `${path}.${key}`);
    if (nested) return nested;
  }
  return "";
}

function requireCentimeterGeometry(value, label) {
  const meterPath = legacyMeterPath(value, label);
  if (meterPath) throw new Error(`project_schema_upgrade_required:${meterPath}`);
}

export function normalizeSavedSpaceConfirmation(saved = {}) {
  if (
    !saved
    || typeof saved !== "object"
    || Array.isArray(saved)
    || Object.keys(saved).length === 0
  ) return {
    coordinate_unit: "cm",
    schema_version: GEOMETRY_SCHEMA_VERSION,
    dismissed_auto_room_ids: [],
    rooms: [],
    structures: { walls: [], doors: [], windows: [], beams: [], columns: [] },
  };
  if (
    saved.coordinate_unit !== "cm"
    || String(saved.schema_version) !== GEOMETRY_SCHEMA_VERSION
  ) {
    throw new Error("project_space_schema_upgrade_required");
  }
  requireCentimeterGeometry(saved, "space_confirmation");
  const result = clone(saved);
  result.dismissed_auto_room_ids = Array.isArray(result.dismissed_auto_room_ids)
    ? result.dismissed_auto_room_ids
    : [];
  result.rooms = Array.isArray(result.rooms) ? result.rooms : [];
  result.structures = Object.fromEntries(
    ["walls", "doors", "windows", "beams", "columns"].map((kind) => [
      kind,
      Array.isArray(result.structures?.[kind]) ? result.structures[kind] : [],
    ]),
  );
  return result;
}

export function normalizeSavedSceneData(saved) {
  if (!saved || typeof saved !== "object") return null;
  const floorplan = saved.floorplan || {};
  if (
    floorplan.coordinate_unit !== "cm"
    || String(floorplan.schema_version) !== GEOMETRY_SCHEMA_VERSION
  ) {
    throw new Error("project_scene_schema_upgrade_required");
  }
  requireCentimeterGeometry(saved, "sceneData");
  return clone(saved);
}
