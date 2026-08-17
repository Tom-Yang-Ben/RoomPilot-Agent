const STRUCTURE_COLLECTIONS = ["walls", "doors", "windows", "beams", "columns"];

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

export function normalizeConfigurationState(saved = {}) {
  if (
    saved
    && typeof saved === "object"
    && !Array.isArray(saved)
    && Object.keys(saved).length === 0
  ) {
    saved = { schema_version: 4 };
  }
  if (Number(saved.schema_version) !== 4) {
    throw new Error("project_configuration_schema_upgrade_required");
  }
  return {
    schema_version: 4,
    furniture: clone(saved.furniture || []),
    sceneData: clone(saved.sceneData || null),
    stale: saved.stale === true,
    staleReason: String(saved.staleReason || ""),
    locked: saved.locked === true,
    configuration_snapshot: saved.configuration_snapshot
      && typeof saved.configuration_snapshot === "object"
      ? clone(saved.configuration_snapshot)
      : null,
  };
}

export function markConfigurationStale(configurationState, reason) {
  configurationState.stale = true;
  configurationState.staleReason = reason || "結構已變更，請重新計算家具配置。";
  configurationState.sceneData = null;
  configurationState.locked = false;
}

export function cloneStructures(structures = {}) {
  return Object.fromEntries(
    STRUCTURE_COLLECTIONS.map((collection) => [
      collection,
      clone(structures[collection] || []),
    ]),
  );
}

export function attachedOpenings(structures = {}, wallId) {
  return ["doors", "windows"].flatMap((collection) =>
    (structures[collection] || [])
      .filter((item) => item.host_wall_id === wallId)
      .map((item) => ({ collection, item })),
  );
}

export function persistConfigurationState(configurationState, {
  furniture,
  sceneData,
} = {}) {
  if (Array.isArray(furniture)) configurationState.furniture = clone(furniture);
  if (sceneData !== undefined) configurationState.sceneData = clone(sceneData);
}
