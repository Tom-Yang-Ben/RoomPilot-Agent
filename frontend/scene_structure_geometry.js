// pointToSegmentDistance 原本在本檔有一份與 scene_camera.js 等價的實作，現在共用
// geometry_core.js。呼叫端名稱保留——本檔的四處用法都在講「點到牆面的距離」。
import { distanceToSegment as pointToSegmentDistance } from "./geometry_core.js?v=sha256-9f5b24aab5dd";

function segmentLength(item) {
  if (!item?.start || !item?.end) return 0;
  return Math.hypot(
    Number(item.end.x || 0) - Number(item.start.x || 0),
    Number(item.end.y || 0) - Number(item.start.y || 0),
  );
}

function segmentRotation(item) {
  if (!item?.start || !item?.end) return Number(item?.rotation_deg || 0);
  return Math.atan2(
    Number(item.end.y || 0) - Number(item.start.y || 0),
    Number(item.end.x || 0) - Number(item.start.x || 0),
  ) * 180 / Math.PI;
}

function rectangleFootprint(center, lengthCm, widthCm, rotationDeg = 0) {
  const angle = Number(rotationDeg || 0) * Math.PI / 180;
  const along = { x: Math.cos(angle), y: Math.sin(angle) };
  const across = { x: -along.y, y: along.x };
  const halfLength = Math.max(0, Number(lengthCm) || 0) / 2;
  const halfWidth = Math.max(0, Number(widthCm) || 0) / 2;
  return [
    { x: center.x - along.x * halfLength - across.x * halfWidth, y: center.y - along.y * halfLength - across.y * halfWidth },
    { x: center.x + along.x * halfLength - across.x * halfWidth, y: center.y + along.y * halfLength - across.y * halfWidth },
    { x: center.x + along.x * halfLength + across.x * halfWidth, y: center.y + along.y * halfLength + across.y * halfWidth },
    { x: center.x - along.x * halfLength + across.x * halfWidth, y: center.y - along.y * halfLength + across.y * halfWidth },
  ];
}

function segmentFootprint(item, widthCm) {
  if (!item?.start || !item?.end) return null;
  const start = { x: Number(item.start.x), y: Number(item.start.y) };
  const end = { x: Number(item.end.x), y: Number(item.end.y) };
  if (![start.x, start.y, end.x, end.y].every(Number.isFinite)) return null;
  const lengthCm = Math.hypot(end.x - start.x, end.y - start.y);
  if (lengthCm < 0.1) return null;
  return rectangleFootprint(
    { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 },
    lengthCm,
    widthCm,
    Math.atan2(end.y - start.y, end.x - start.x) * 180 / Math.PI,
  );
}

function polygonAxes(polygon) {
  return polygon.map((point, index) => {
    const next = polygon[(index + 1) % polygon.length];
    const edge = { x: next.x - point.x, y: next.y - point.y };
    const length = Math.hypot(edge.x, edge.y) || 1;
    return { x: -edge.y / length, y: edge.x / length };
  });
}

function projectionRange(polygon, axis) {
  const values = polygon.map((point) => point.x * axis.x + point.y * axis.y);
  return { min: Math.min(...values), max: Math.max(...values) };
}

function polygonCenter(polygon) {
  return polygon.reduce(
    (center, point) => ({
      x: center.x + point.x / polygon.length,
      y: center.y + point.y / polygon.length,
    }),
    { x: 0, y: 0 },
  );
}

function polygonPenetration(polygonA, polygonB, touchToleranceCm, preferredPoint = null) {
  let minimum = null;
  for (const axis of [...polygonAxes(polygonA), ...polygonAxes(polygonB)]) {
    const a = projectionRange(polygonA, axis);
    const b = projectionRange(polygonB, axis);
    const overlap = Math.min(a.max, b.max) - Math.max(a.min, b.min);
    if (overlap <= touchToleranceCm) return null;
    if (!minimum || overlap < minimum.overlap) minimum = { axis, overlap };
  }
  if (!minimum) return null;
  const centerA = polygonCenter(polygonA);
  const centerB = polygonCenter(polygonB);
  const preferred = {
    x: Number(preferredPoint?.x),
    y: Number(preferredPoint?.y),
  };
  const direction = Number.isFinite(preferred.x) && Number.isFinite(preferred.y)
    ? { x: preferred.x - centerA.x, y: preferred.y - centerA.y }
    : { x: centerA.x - centerB.x, y: centerA.y - centerB.y };
  const directionDot = direction.x * minimum.axis.x + direction.y * minimum.axis.y;
  const sign = directionDot < 0 ? -1 : 1;
  const distanceCm = minimum.overlap + touchToleranceCm;
  return {
    x: minimum.axis.x * sign * distanceCm,
    y: minimum.axis.y * sign * distanceCm,
    distanceCm,
  };
}

function structureFootprint(item, kind) {
  if (kind === "beam") {
    return segmentFootprint(item, Math.max(1, Number(item?.thickness_cm) || 30));
  }
  if (kind === "column") {
    const center = {
      x: Number(item?.center?.x),
      y: Number(item?.center?.y ?? item?.center?.z),
    };
    if (!Number.isFinite(center.x) || !Number.isFinite(center.y)) return null;
    return rectangleFootprint(
      center,
      Math.max(1, Number(item?.size_cm) || 35),
      Math.max(1, Number(item?.depth_cm) || Number(item?.size_cm) || 35),
      Number(item?.rotation_deg) || 0,
    );
  }
  return null;
}

function beamEndpointSupportedByWall(item, wall, wallWidthCm, touchToleranceCm) {
  if (!item?.start || !item?.end || !wall?.start || !wall?.end) return false;
  const beamDx = Number(item.end.x) - Number(item.start.x);
  const beamDy = Number(item.end.y) - Number(item.start.y);
  const wallDx = Number(wall.end.x) - Number(wall.start.x);
  const wallDy = Number(wall.end.y) - Number(wall.start.y);
  const beamLength = Math.hypot(beamDx, beamDy);
  const wallLength = Math.hypot(wallDx, wallDy);
  if (beamLength < 0.1 || wallLength < 0.1) return false;
  const parallelDot = Math.abs(
    (beamDx / beamLength) * (wallDx / wallLength)
    + (beamDy / beamLength) * (wallDy / wallLength),
  );
  if (parallelDot > 0.25) return false;
  const wallStart = { x: Number(wall.start.x), y: Number(wall.start.y) };
  const wallEnd = { x: Number(wall.end.x), y: Number(wall.end.y) };
  const threshold = wallWidthCm / 2 + touchToleranceCm;
  return [item.start, item.end].some((endpoint) =>
    pointToSegmentDistance(
      { x: Number(endpoint.x), y: Number(endpoint.y) },
      wallStart,
      wallEnd,
    ) <= threshold
  );
}

function trimBeamEndpointsToWallFaces(item, walls, touchToleranceCm) {
  const next = {
    ...item,
    start: { ...item.start },
    end: { ...item.end },
  };
  let totalTrimCm = 0;
  for (const endpointKey of ["start", "end"]) {
    const otherKey = endpointKey === "start" ? "end" : "start";
    for (const wall of walls) {
      const beamDx = Number(next.end.x) - Number(next.start.x);
      const beamDy = Number(next.end.y) - Number(next.start.y);
      const wallDx = Number(wall?.end?.x) - Number(wall?.start?.x);
      const wallDy = Number(wall?.end?.y) - Number(wall?.start?.y);
      const beamLength = Math.hypot(beamDx, beamDy);
      const wallLength = Math.hypot(wallDx, wallDy);
      if (beamLength < 0.1 || wallLength < 0.1) continue;
      const parallelDot = Math.abs(
        (beamDx / beamLength) * (wallDx / wallLength)
        + (beamDy / beamLength) * (wallDy / wallLength),
      );
      if (parallelDot > 0.25) continue;
      const point = next[endpointKey];
      const other = next[otherKey];
      const wallStart = { x: Number(wall.start.x), y: Number(wall.start.y) };
      const wallEnd = { x: Number(wall.end.x), y: Number(wall.end.y) };
      const distance = pointToSegmentDistance(point, wallStart, wallEnd);
      const targetDistance =
        Math.max(1, Number(wall.thickness_cm) || 12) / 2 + touchToleranceCm;
      if (distance >= targetDistance) continue;
      const inward = {
        x: (other.x - point.x) / Math.hypot(other.x - point.x, other.y - point.y),
        y: (other.y - point.y) / Math.hypot(other.x - point.x, other.y - point.y),
      };
      const probe = {
        x: point.x + inward.x,
        y: point.y + inward.y,
      };
      if (pointToSegmentDistance(probe, wallStart, wallEnd) + 1e-6 < distance) {
        continue;
      }
      const trimCm = targetDistance - distance;
      next[endpointKey] = {
        x: point.x + inward.x * trimCm,
        y: point.y + inward.y * trimCm,
      };
      totalTrimCm += trimCm;
    }
  }
  return { item: next, totalTrimCm };
}

export function findStructureWallCollision(
  item,
  kind,
  walls = [],
  { touchToleranceCm = 0.5, preferredPoint = null } = {},
) {
  const footprint = structureFootprint(item, kind);
  if (!footprint) return null;
  for (let index = 0; index < walls.length; index += 1) {
    const wall = walls[index];
    const wallWidthCm = Math.max(1, Number(wall?.thickness_cm) || 12);
    const wallFootprint = segmentFootprint(
      wall,
      wallWidthCm,
    );
    const translation = wallFootprint
      ? polygonPenetration(footprint, wallFootprint, touchToleranceCm, preferredPoint)
      : null;
    if (
      translation
      && !(kind === "beam"
        && beamEndpointSupportedByWall(item, wall, wallWidthCm, touchToleranceCm))
    ) {
      return { wallId: wall.id || null, wallIndex: index, translation };
    }
  }
  return null;
}

function translatedStructure(item, kind, translation) {
  const next = { ...item };
  if (kind === "column") {
    next.center = {
      ...item.center,
      x: Number(item.center?.x || 0) + translation.x,
      y: Number(item.center?.y ?? item.center?.z ?? 0) + translation.y,
    };
  } else if (kind === "beam") {
    next.start = {
      x: Number(item.start?.x || 0) + translation.x,
      y: Number(item.start?.y || 0) + translation.y,
    };
    next.end = {
      x: Number(item.end?.x || 0) + translation.x,
      y: Number(item.end?.y || 0) + translation.y,
    };
  }
  return next;
}

export function resolveStructureWallCollisions(
  item,
  kind,
  walls = [],
  {
    preferredPoint = null,
    touchToleranceCm = 0.5,
    maxAutoShiftCm = 75,
    maxIterations = 16,
  } = {},
) {
  const original = {
    ...item,
    ...(item?.center ? { center: { ...item.center } } : {}),
    ...(item?.start ? { start: { ...item.start } } : {}),
    ...(item?.end ? { end: { ...item.end } } : {}),
  };
  const trimmed = kind === "beam"
    ? trimBeamEndpointsToWallFaces(original, walls, touchToleranceCm)
    : { item: original, totalTrimCm: 0 };
  let candidate = trimmed.item;
  let totalShiftCm = trimmed.totalTrimCm;
  if (totalShiftCm > maxAutoShiftCm) {
    return { item: original, resolved: false, moved: false, totalShiftCm: 0 };
  }
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    const collision = findStructureWallCollision(candidate, kind, walls, {
      touchToleranceCm,
      preferredPoint,
    });
    if (!collision) {
      return {
        item: candidate,
        resolved: true,
        moved: totalShiftCm > 0,
        totalShiftCm,
      };
    }
    totalShiftCm += collision.translation.distanceCm;
    if (totalShiftCm > maxAutoShiftCm) {
      return { item: original, resolved: false, moved: false, totalShiftCm: 0 };
    }
    candidate = translatedStructure(candidate, kind, collision.translation);
  }
  return { item: original, resolved: false, moved: false, totalShiftCm: 0 };
}

export function validateColumnDimensionsCm({
  widthCm,
  depthCm,
  heightCm,
  maxWidthCm = Number.POSITIVE_INFINITY,
  maxDepthCm = Number.POSITIVE_INFINITY,
  maxHeightCm = Number.POSITIVE_INFINITY,
  centerXcm = null,
  centerYcm = null,
  rotationDeg = 0,
}) {
  if ([widthCm, depthCm, heightCm].some((value) => value === "" || value === null || value === undefined)) {
    return { valid: false, message: "請完整輸入柱寬、深度與高度。" };
  }
  const values = {
    widthCm: Number(widthCm),
    depthCm: Number(depthCm),
    heightCm: Number(heightCm),
  };
  if (Object.values(values).some((value) => !Number.isFinite(value))) {
    return { valid: false, message: "請完整輸入柱寬、深度與高度。" };
  }
  if (values.widthCm < 10 || values.depthCm < 10 || values.heightCm < 30) {
    return { valid: false, message: "柱寬與深度至少 10 公分，高度至少 30 公分。" };
  }
  const limits = {
    maxWidthCm: Number(maxWidthCm),
    maxDepthCm: Number(maxDepthCm),
    maxHeightCm: Number(maxHeightCm),
  };
  const centerX = Number(centerXcm);
  const centerY = Number(centerYcm);
  const hasFootprintContext = centerXcm !== null
    && centerYcm !== null
    && Number.isFinite(centerX)
    && Number.isFinite(centerY)
    && Number.isFinite(limits.maxWidthCm)
    && Number.isFinite(limits.maxDepthCm);
  if (
    values.heightCm > limits.maxHeightCm
    || (!hasFootprintContext && (
      values.widthCm > limits.maxWidthCm
      || values.depthCm > limits.maxDepthCm
    ))
  ) {
    return {
      valid: false,
      message: `柱寬不可超過 ${Math.round(limits.maxWidthCm)} 公分、深度不可超過 ${Math.round(limits.maxDepthCm)} 公分、高度不可超過 ${Math.round(limits.maxHeightCm)} 公分。`,
    };
  }
  if (hasFootprintContext) {
    const angle = Number(rotationDeg || 0) * Math.PI / 180;
    const cos = Math.abs(Math.cos(angle));
    const sin = Math.abs(Math.sin(angle));
    const halfExtentX = (values.widthCm * cos + values.depthCm * sin) / 2;
    const halfExtentY = (values.widthCm * sin + values.depthCm * cos) / 2;
    const epsilonCm = 1e-6;
    const outside = centerX - halfExtentX < -epsilonCm
      || centerX + halfExtentX > limits.maxWidthCm + epsilonCm
      || centerY - halfExtentY < -epsilonCm
      || centerY + halfExtentY > limits.maxDepthCm + epsilonCm;
    if (outside) {
      return {
        valid: false,
        message: "旋轉後柱體超出平面圖範圍，請縮小尺寸、調整方向或移動位置。",
      };
    }
  }
  return { valid: true, values };
}

export function columnGeometryDescriptor(
  item,
  { minimumDimensionCm = 10, defaultHeightCm = 270 } = {},
) {
  const widthCm = Math.max(
    minimumDimensionCm,
    Number(item?.size_cm) || 35,
  );
  const depthCm = Math.max(
    minimumDimensionCm,
    Number(item?.depth_cm) || Number(item?.size_cm) || 35,
  );
  const heightCm = Math.max(
    minimumDimensionCm,
    Number(item?.height_cm) || Number(defaultHeightCm) || 270,
  );
  return {
    widthCm,
    depthCm,
    heightCm,
    centerX: Number(item?.center?.x || 0),
    centerZ: Number(item?.center?.z ?? item?.center?.y ?? 0),
    centerHeightCm: heightCm / 2,
    rotationDeg: Number(item?.rotation_deg) || 0,
  };
}

export function structurePreviewDescriptor(
  item,
  kind,
  { ceilingHeightCm = 270, planWidthCm = 0, planDepthCm = 0 } = {},
) {
  const safeCeilingHeight = Math.max(210, Number(ceilingHeightCm) || 270);
  const centerX = kind === "column"
    ? Number(item?.center?.x || 0) - Number(planWidthCm || 0) / 2
    : (Number(item?.start?.x || 0) + Number(item?.end?.x || 0)) / 2
      - Number(planWidthCm || 0) / 2;
  const centerZ = kind === "column"
    ? Number(item?.center?.y ?? item?.center?.z ?? 0) - Number(planDepthCm || 0) / 2
    : (Number(item?.start?.y ?? item?.start?.z ?? 0)
      + Number(item?.end?.y ?? item?.end?.z ?? 0)) / 2
      - Number(planDepthCm || 0) / 2;
  if (kind === "beam") {
    const heightCm = Math.max(10, Number(item?.height_cm) || 35);
    return {
      kind,
      lengthCm: Math.max(30, segmentLength(item)),
      widthCm: Math.max(10, Number(item?.thickness_cm) || 30),
      heightCm,
      centerHeightCm: safeCeilingHeight - heightCm / 2,
      centerX,
      centerZ,
      rotationDeg: segmentRotation(item),
    };
  }
  if (kind === "column") {
    const column = columnGeometryDescriptor({
      ...item,
      center: { x: centerX, z: centerZ },
    }, {
      minimumDimensionCm: 10,
      defaultHeightCm: safeCeilingHeight,
    });
    return {
      kind,
      lengthCm: column.widthCm,
      widthCm: column.depthCm,
      heightCm: column.heightCm,
      centerHeightCm: column.centerHeightCm,
      centerX: column.centerX,
      centerZ: column.centerZ,
      rotationDeg: column.rotationDeg,
    };
  }
  return null;
}
