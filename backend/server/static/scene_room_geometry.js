export function polygonArea(points) {
  if (!points?.length) return 0;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0) / 2);
}

export function roomPolygonsDiffer(first, second, toleranceCm = 0.01) {
  if ((first?.length || 0) !== (second?.length || 0)) return true;
  return (first || []).some((point, index) => (
    Math.abs(Number(point.x) - Number(second[index]?.x)) > toleranceCm
    || Math.abs(Number(point.y) - Number(second[index]?.y)) > toleranceCm
  ));
}

export function pointInPolygonCm(point, polygon) {
  if (!point || !Array.isArray(polygon) || polygon.length < 3) return false;
  let inside = false;
  for (let index = 0, previousIndex = polygon.length - 1; index < polygon.length; previousIndex = index, index += 1) {
    const current = polygon[index];
    const previous = polygon[previousIndex];
    const intersects = (
      (Number(current.y) > point.y) !== (Number(previous.y) > point.y)
      && point.x < (
        ((Number(previous.x) - Number(current.x)) * (point.y - Number(current.y)))
        / ((Number(previous.y) - Number(current.y)) || 1e-9)
        + Number(current.x)
      )
    );
    if (intersects) inside = !inside;
  }
  return inside;
}

export function roomCenter(room) {
  const polygon = room?.polygon_cm || [];
  if (!polygon.length) return { x: 0, y: 0 };
  return polygon.reduce((sum, point) => ({
    x: sum.x + Number(point.x || 0) / polygon.length,
    y: sum.y + Number(point.y || 0) / polygon.length,
  }), { x: 0, y: 0 });
}

export function convexHull(points) {
  const unique = [...new Map(
    points.map((point) => [`${point.x.toFixed(5)}:${point.y.toFixed(5)}`, point]),
  ).values()].sort((a, b) => a.x - b.x || a.y - b.y);
  if (unique.length <= 3) return unique;
  const cross = (origin, a, b) =>
    (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x);
  const lower = [];
  for (const point of unique) {
    while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), point) <= 0) lower.pop();
    lower.push(point);
  }
  const upper = [];
  for (const point of [...unique].reverse()) {
    while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), point) <= 0) upper.pop();
    upper.push(point);
  }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)];
}

export function clipPolygonByLine(points, start, end, keepPositive) {
  const side = (point) =>
    (end.x - start.x) * (point.y - start.y) - (end.y - start.y) * (point.x - start.x);
  const inside = (point) => keepPositive ? side(point) >= -1e-6 : side(point) <= 1e-6;
  const intersection = (a, b) => {
    const sideA = side(a);
    const sideB = side(b);
    const denominator = sideA - sideB;
    const t = Math.abs(denominator) < 1e-9 ? 0 : sideA / denominator;
    return {
      x: a.x + (b.x - a.x) * t,
      y: a.y + (b.y - a.y) * t,
    };
  };
  const result = [];
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const previous = points[(index + points.length - 1) % points.length];
    if (inside(current)) {
      if (!inside(previous)) result.push(intersection(previous, current));
      result.push(current);
    } else if (inside(previous)) {
      result.push(intersection(previous, current));
    }
  }
  return result;
}

export function roomDimensions(room) {
  const polygon = room.polygon_cm || [];
  const xs = polygon.map((point) => point.x);
  const ys = polygon.map((point) => point.y);
  if (polygon.length < 3) return { widthCm: 0, depthCm: 0, areaM2: 0 };
  return {
    widthCm: Math.max(...xs) - Math.min(...xs),
    depthCm: Math.max(...ys) - Math.min(...ys),
    areaM2: polygonArea(polygon) / 10_000,
  };
}

function orthogonalizeNearAxisEdges(
  points,
  { maxOffsetCm = 30, maxSlopeRatio = 0.15, minEdgeLengthCm = 40 } = {},
) {
  if (!Array.isArray(points) || points.length < 3) return points || [];
  const constraints = points.map(() => ({ x: [], y: [] }));
  points.forEach((point, index) => {
    const nextIndex = (index + 1) % points.length;
    const next = points[nextIndex];
    const dx = Number(next.x) - Number(point.x);
    const dy = Number(next.y) - Number(point.y);
    const length = Math.hypot(dx, dy);
    if (length < minEdgeLengthCm) return;
    if (
      Math.abs(dy) <= maxOffsetCm
      && Math.abs(dy) <= Math.abs(dx) * maxSlopeRatio
    ) {
      const y = (Number(point.y) + Number(next.y)) / 2;
      constraints[index].y.push(y);
      constraints[nextIndex].y.push(y);
      return;
    }
    if (
      Math.abs(dx) <= maxOffsetCm
      && Math.abs(dx) <= Math.abs(dy) * maxSlopeRatio
    ) {
      const x = (Number(point.x) + Number(next.x)) / 2;
      constraints[index].x.push(x);
      constraints[nextIndex].x.push(x);
    }
  });
  const average = (values, fallback) => (
    values.length
      ? values.reduce((sum, value) => sum + value, 0) / values.length
      : fallback
  );
  return points.map((point, index) => ({
    x: average(constraints[index].x, Number(point.x)),
    y: average(constraints[index].y, Number(point.y)),
  }));
}

export function repairLoadedRoomPolygon(points) {
  let repaired = (points || []).map((point) => ({ ...point }));
  let changed = true;
  while (changed && repaired.length > 3) {
    changed = false;
    const area = polygonArea(repaired);
    for (let index = 0; index < repaired.length; index += 1) {
      const previous = repaired[(index + repaired.length - 1) % repaired.length];
      const point = repaired[index];
      const following = repaired[(index + 1) % repaired.length];
      const dx = following.x - previous.x;
      const dy = following.y - previous.y;
      const base = Math.hypot(dx, dy);
      if (base <= 1e-6) continue;
      const projection = (
        (point.x - previous.x) * dx + (point.y - previous.y) * dy
      ) / (base * base);
      const height = Math.abs(
        dx * (previous.y - point.y) - (previous.x - point.x) * dy,
      ) / base;
      if (projection >= 0 && projection <= 1 && height <= 2) {
        repaired = repaired.filter((_, candidateIndex) => candidateIndex !== index);
        changed = true;
        break;
      }
      if (base > 35) continue;
      if (projection < 0.1 || projection > 0.9) continue;
      if (height < 15 || height < base * 0.75) continue;
      const candidate = repaired.filter((_, candidateIndex) => candidateIndex !== index);
      const areaChange = Math.abs(area - polygonArea(candidate));
      if (areaChange > Math.max(500, area * 0.05)) continue;
      repaired = candidate;
      changed = true;
      break;
    }
  }
  return orthogonalizeNearAxisEdges(repaired);
}
