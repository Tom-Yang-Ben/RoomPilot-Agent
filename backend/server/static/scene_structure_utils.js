function finitePoint(point) {
  const x = Number(point?.x);
  const y = Number(point?.y);
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

export function wallBoundarySide(
  wall,
  {
    widthCm,
    depthCm,
    toleranceCm,
  } = {},
) {
  const start = finitePoint(wall?.start);
  const end = finitePoint(wall?.end);
  const width = Number(widthCm);
  const depth = Number(depthCm);
  if (!start || !end || !(width > 0) || !(depth > 0)) return null;
  const tolerance = Number(toleranceCm) > 0
    ? Number(toleranceCm)
    : Math.max(8, Math.min(width, depth) * 0.02);
  const onBoundary = (first, second, boundary) =>
    Math.abs(first - boundary) <= tolerance
    && Math.abs(second - boundary) <= tolerance;
  if (onBoundary(start.x, end.x, 0)) return "left";
  if (onBoundary(start.x, end.x, width)) return "right";
  if (onBoundary(start.y, end.y, 0)) return "bottom";
  if (onBoundary(start.y, end.y, depth)) return "top";
  return null;
}

export function canMarkWallForDemolition(wall, floorplan) {
  return wallBoundarySide(wall, {
    widthCm: floorplan?.width_cm,
    depthCm: floorplan?.depth_cm,
  }) == null;
}

function windowAxis(item) {
  const start = finitePoint(item?.start);
  const end = finitePoint(item?.end);
  if (!start || !end) return null;
  const dx = Math.abs(end.x - start.x);
  const dy = Math.abs(end.y - start.y);
  const length = Math.hypot(dx, dy);
  if (length < 5) return null;
  if (dx > dy * 3) {
    return {
      orientation: "horizontal",
      constant: (start.y + end.y) / 2,
      low: Math.min(start.x, end.x),
      high: Math.max(start.x, end.x),
      length,
    };
  }
  if (dy > dx * 3) {
    return {
      orientation: "vertical",
      constant: (start.x + end.x) / 2,
      low: Math.min(start.y, end.y),
      high: Math.max(start.y, end.y),
      length,
    };
  }
  return null;
}

function windowCandidateScore(item) {
  return (item?.confirmed === true ? 100 : 0)
    + (item?.source === "manual" ? 20 : 0)
    + Math.max(0, Number(item?.confidence) || 0) * 10
    + (item?.estimated === false ? 5 : 0);
}

export function windowsOverlap(first, second) {
  if (!first || !second || first.id === second.id) return false;
  if (
    first.host_wall_id
    && second.host_wall_id
    && first.host_wall_id !== second.host_wall_id
  ) return false;
  const a = windowAxis(first);
  const b = windowAxis(second);
  if (!a || !b || a.orientation !== b.orientation) return false;
  if (Math.abs(a.constant - b.constant) > 18) return false;
  const overlap = Math.max(0, Math.min(a.high, b.high) - Math.max(a.low, b.low));
  return overlap / Math.min(a.length, b.length) >= 0.55;
}

export function dedupeWindowCandidates(candidates = []) {
  const windows = [];
  let removed = 0;
  for (const candidate of candidates) {
    const duplicateIndex = windows.findIndex((item) => windowsOverlap(item, candidate));
    if (duplicateIndex < 0) {
      windows.push(candidate);
      continue;
    }
    if (windowCandidateScore(candidate) > windowCandidateScore(windows[duplicateIndex])) {
      windows[duplicateIndex] = candidate;
    }
    removed += 1;
  }
  return { windows, removed };
}

function nearestSnapPoint(point, anchors, thresholdCm) {
  let best = null;
  let bestDistance = thresholdCm;
  for (const candidate of anchors || []) {
    const anchor = finitePoint(candidate);
    if (!anchor) continue;
    const distance = Math.hypot(anchor.x - point.x, anchor.y - point.y);
    if (distance <= bestDistance) {
      best = anchor;
      bestDistance = distance;
    }
  }
  return best;
}

export function beamDragGeometry(
  rawStart,
  rawEnd,
  anchors = [],
  { snapDistanceCm = 24, minLengthCm = 25 } = {},
) {
  const initialStart = finitePoint(rawStart) || { x: 0, y: 0 };
  const pointerEnd = finitePoint(rawEnd) || initialStart;
  const snappedStart = nearestSnapPoint(initialStart, anchors, snapDistanceCm);
  const start = snappedStart || initialStart;
  const dx = pointerEnd.x - start.x;
  const dy = pointerEnd.y - start.y;
  const axisEnd = Math.abs(dx) >= Math.abs(dy)
    ? { x: pointerEnd.x, y: start.y }
    : { x: start.x, y: pointerEnd.y };
  const snappedEnd = nearestSnapPoint(axisEnd, anchors, snapDistanceCm);
  const end = snappedEnd || axisEnd;
  const lengthCm = Math.round(Math.hypot(end.x - start.x, end.y - start.y) * 10000) / 10000;
  return {
    start,
    end,
    lengthCm,
    valid: lengthCm >= minLengthCm,
    snapped: Boolean(snappedStart || snappedEnd),
  };
}
