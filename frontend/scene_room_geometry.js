// polygonArea 原本在本檔有一份與 scene_plan_geometry.js 逐字元相同的副本。
// 幾何純函式的匯出點是 scene_plan_geometry.js，這裡只消費不重寫。
import { polygonArea } from "./scene_plan_geometry.js?v=sha256-b77b33d86870";

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
