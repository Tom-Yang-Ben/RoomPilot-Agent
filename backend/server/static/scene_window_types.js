export const WINDOW_TYPES = Object.freeze({
  standard: "standard",
  floorToCeiling: "floor_to_ceiling",
});

const roundCentimeters = (value) => Math.round(Number(value) * 10) / 10;

export function normalizedWindowType(value) {
  return value === WINDOW_TYPES.floorToCeiling
    ? WINDOW_TYPES.floorToCeiling
    : WINDOW_TYPES.standard;
}

export function applyWindowTypePreset(opening = {}, type, ceilingHeightCm = 270) {
  const windowType = normalizedWindowType(type);
  if (windowType === WINDOW_TYPES.floorToCeiling) {
    const headHeightCm = Math.max(35, Number(ceilingHeightCm || 270) - 8);
    return {
      ...opening,
      window_type: windowType,
      sill_height_cm: 0,
      height_cm: headHeightCm,
      head_height_cm: headHeightCm,
    };
  }
  return {
    ...opening,
    window_type: windowType,
    sill_height_cm: 90,
    height_cm: 120,
    head_height_cm: 210,
  };
}

export function windowOpeningMetrics(opening = {}, wallHeightCm = 270) {
  const wallHeight = Math.max(43, Number(wallHeightCm) || 270);
  const windowType = normalizedWindowType(opening.window_type);
  const floorToCeiling = windowType === WINDOW_TYPES.floorToCeiling;
  const requestedSill = floorToCeiling ? 0 : Number(opening.sill_height_cm ?? 90);
  const sillHeightCm = Math.max(0, Math.min(requestedSill, wallHeight - 43));
  const fallbackHeight = floorToCeiling ? wallHeight - 8 : 120;
  const requestedHeight = Math.max(35, Number(opening.height_cm) || fallbackHeight);
  const requestedHead = Number(opening.head_height_cm);
  const headHeightCm = Math.min(
    Number.isFinite(requestedHead) ? requestedHead : sillHeightCm + requestedHeight,
    wallHeight - 8,
  );
  const glazingHeightCm = roundCentimeters(Math.max(35, headHeightCm - sillHeightCm));

  return {
    windowType,
    sillHeightCm: roundCentimeters(sillHeightCm),
    headHeightCm: roundCentimeters(headHeightCm),
    glazingHeightCm,
  };
}
