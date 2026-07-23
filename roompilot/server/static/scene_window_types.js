export const WINDOW_TYPES = Object.freeze({
  standard: "standard",
  floorToCeiling: "floor_to_ceiling",
});

const roundMeters = (value) => Math.round(Number(value) * 1000) / 1000;

export function normalizedWindowType(value) {
  return value === WINDOW_TYPES.floorToCeiling
    ? WINDOW_TYPES.floorToCeiling
    : WINDOW_TYPES.standard;
}

export function applyWindowTypePreset(opening = {}, type, ceilingHeightM = 2.7) {
  const windowType = normalizedWindowType(type);
  if (windowType === WINDOW_TYPES.floorToCeiling) {
    const headHeightM = Math.max(0.35, Number(ceilingHeightM || 2.7) - 0.08);
    return {
      ...opening,
      window_type: windowType,
      sill_height_m: 0,
      height_m: headHeightM,
      head_height_m: headHeightM,
    };
  }
  return {
    ...opening,
    window_type: windowType,
    sill_height_m: 0.9,
    height_m: 1.2,
    head_height_m: 2.1,
  };
}

export function windowOpeningMetrics(opening = {}, wallHeightM = 2.7) {
  const wallHeight = Math.max(0.43, Number(wallHeightM) || 2.7);
  const windowType = normalizedWindowType(opening.window_type);
  const floorToCeiling = windowType === WINDOW_TYPES.floorToCeiling;
  const requestedSill = floorToCeiling ? 0 : Number(opening.sill_height_m ?? 0.9);
  const sillHeightM = Math.max(0, Math.min(requestedSill, wallHeight - 0.43));
  const fallbackHeight = floorToCeiling ? wallHeight - 0.08 : 1.2;
  const requestedHeight = Math.max(0.35, Number(opening.height_m) || fallbackHeight);
  const requestedHead = Number(opening.head_height_m);
  const headHeightM = Math.min(
    Number.isFinite(requestedHead) ? requestedHead : sillHeightM + requestedHeight,
    wallHeight - 0.08,
  );
  const glazingHeightM = roundMeters(Math.max(0.35, headHeightM - sillHeightM));

  return {
    windowType,
    sillHeightM: roundMeters(sillHeightM),
    headHeightM: roundMeters(headHeightM),
    glazingHeightM,
  };
}
