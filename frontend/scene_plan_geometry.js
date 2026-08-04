// 佇列 7 巨石拆分第二批：純搬家自 scene_v2.js，函式內容一字未改。
// 這裡只收平面幾何純函式——僅依賴參數、彼此與標準庫，不碰 state、element、DOM。
// 為了維持「純搬家」紀律，函式主體保持原樣，統一在檔尾 export。

// polygonArea 與射線法都搬進 geometry_core.js——engineering.js 那條獨立頁面鏈
// 也要用，不能讓它們住在名字綁 scene 的模組裡。pointInPolygonCm 保留為別名：
// scene 側的多邊形一律是公分，名稱帶著這個單位契約，中立核心刻意不帶。
import {
  pointInPolygon as pointInPolygonCm,
  polygonArea,
} from "./geometry_core.js?v=sha256-9f5b24aab5dd";

function roomPolygonsDiffer(first, second, toleranceCm = 0.01) {
  if ((first?.length || 0) !== (second?.length || 0)) return true;
  return (first || []).some((point, index) => (
    Math.abs(Number(point.x) - Number(second[index]?.x)) > toleranceCm
    || Math.abs(Number(point.y) - Number(second[index]?.y)) > toleranceCm
  ));
}

function convexHull(points) {
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

function clipPolygonByLine(points, start, end, keepPositive) {
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

function roomDimensions(room) {
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

function nearestPointOnRoomEdge(point, polygon) {
  let closest = null;
  polygon.forEach((start, edgeIndex) => {
    const end = polygon[(edgeIndex + 1) % polygon.length];
    const projected = nearestPointOnSegment(point, start, end);
    const distance = Math.hypot(point.x - projected.x, point.y - projected.y);
    if (!closest || distance < closest.distance) {
      closest = { edgeIndex, projected, distance };
    }
  });
  return closest;
}

function nearestPointOnSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function nearestPointOnLine(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy || 1;
  const t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared;
  return { x: start.x + t * dx, y: start.y + t * dy, t };
}

function roomCenter(room) {
  return room.polygon_cm.reduce((sum, point) => ({
    x: sum.x + point.x / room.polygon_cm.length,
    y: sum.y + point.y / room.polygon_cm.length,
  }), { x: 0, y: 0 });
}

// 場景座標同時存在兩種形狀：物件 {x, z}（或 {x, y}）與陣列 [x, y]。
// 單房裁切／平移時兩種都要正確處理，否則陣列點會原地不動（bella 23de9dda）。
function scenePointCoordinates(point = {}) {
  if (Array.isArray(point)) {
    return {
      x: Number(point[0] || 0),
      z: Number(point[1] || 0),
    };
  }
  return {
    x: Number(point.x || 0),
    z: Number(point.z ?? point.y ?? 0),
  };
}

function segmentEndpoint(point = {}) {
  return scenePointCoordinates(point);
}

function segmentOverlapsBounds(segment, bounds, padding = 32) {
  if (!segment || !bounds) return false;
  const start = segmentEndpoint(segment.start || segment[0]);
  const end = segmentEndpoint(segment.end || segment[1]);
  const minX = Math.min(start.x, end.x);
  const maxX = Math.max(start.x, end.x);
  const minZ = Math.min(start.z, end.z);
  const maxZ = Math.max(start.z, end.z);
  return (
    maxX >= bounds.minX - padding
    && minX <= bounds.maxX + padding
    && maxZ >= bounds.minZ - padding
    && minZ <= bounds.maxZ + padding
  );
}

function shiftScenePoint(point = {}, offset) {
  if (!offset) return Array.isArray(point) ? [...point] : { ...point };
  if (Array.isArray(point)) {
    return [
      Number(point[0] || 0) - offset.x,
      Number(point[1] || 0) - offset.z,
    ];
  }
  const next = { ...point };
  if ("x" in next) next.x = Number(next.x || 0) - offset.x;
  if ("z" in next) next.z = Number(next.z || 0) - offset.z;
  if ("y" in next && !("z" in next)) next.y = Number(next.y || 0) - offset.z;
  return next;
}

function shiftSceneSegment(segment, offset) {
  if (!segment) return segment;
  if (Array.isArray(segment)) {
    return segment.map((point) => shiftScenePoint(point, offset));
  }
  return {
    ...segment,
    start: shiftScenePoint(segment.start, offset),
    end: shiftScenePoint(segment.end, offset),
  };
}

function shiftFloorplanRegion(region, offset) {
  if (!region || !offset) return region;
  const next = { ...region };
  ["exterior", "polygon_cm", "polygon_m", "room_polygon_cm"].forEach((key) => {
    if (Array.isArray(next[key])) next[key] = next[key].map((point) => shiftScenePoint(point, offset));
  });
  if (Array.isArray(next.holes)) {
    next.holes = next.holes.map((ring) => (
      Array.isArray(ring) ? ring.map((point) => shiftScenePoint(point, offset)) : ring
    ));
  }
  return next;
}

function shiftRoomSurfaceAssignment(assignment, offset) {
  if (!assignment || !offset) return assignment;
  const next = { ...assignment };
  if (next.room_bounds_cm) {
    next.room_bounds_cm = {
      ...next.room_bounds_cm,
      minX: Number(next.room_bounds_cm.minX || 0) - offset.x,
      maxX: Number(next.room_bounds_cm.maxX || 0) - offset.x,
      minZ: Number(next.room_bounds_cm.minZ || 0) - offset.z,
      maxZ: Number(next.room_bounds_cm.maxZ || 0) - offset.z,
    };
  }
  if (Array.isArray(next.room_polygon_cm)) {
    next.room_polygon_cm = next.room_polygon_cm.map((point) => shiftScenePoint(point, offset));
  }
  return next;
}

export {
  clipPolygonByLine,
  convexHull,
  nearestPointOnLine,
  nearestPointOnRoomEdge,
  nearestPointOnSegment,
  pointInPolygonCm,
  polygonArea,
  roomCenter,
  roomDimensions,
  roomPolygonsDiffer,
  scenePointCoordinates,
  segmentEndpoint,
  segmentOverlapsBounds,
  shiftFloorplanRegion,
  shiftRoomSurfaceAssignment,
  shiftScenePoint,
  shiftSceneSegment,
};
