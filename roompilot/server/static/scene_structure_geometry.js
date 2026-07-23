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

function rectangleFootprint(center, lengthM, widthM, rotationDeg = 0) {
  const angle = Number(rotationDeg || 0) * Math.PI / 180;
  const along = { x: Math.cos(angle), y: Math.sin(angle) };
  const across = { x: -along.y, y: along.x };
  const halfLength = Math.max(0, Number(lengthM) || 0) / 2;
  const halfWidth = Math.max(0, Number(widthM) || 0) / 2;
  return [
    { x: center.x - along.x * halfLength - across.x * halfWidth, y: center.y - along.y * halfLength - across.y * halfWidth },
    { x: center.x + along.x * halfLength - across.x * halfWidth, y: center.y + along.y * halfLength - across.y * halfWidth },
    { x: center.x + along.x * halfLength + across.x * halfWidth, y: center.y + along.y * halfLength + across.y * halfWidth },
    { x: center.x - along.x * halfLength + across.x * halfWidth, y: center.y - along.y * halfLength + across.y * halfWidth },
  ];
}

function segmentFootprint(item, widthM) {
  if (!item?.start || !item?.end) return null;
  const start = { x: Number(item.start.x), y: Number(item.start.y) };
  const end = { x: Number(item.end.x), y: Number(item.end.y) };
  if (![start.x, start.y, end.x, end.y].every(Number.isFinite)) return null;
  const lengthM = Math.hypot(end.x - start.x, end.y - start.y);
  if (lengthM < 0.001) return null;
  return rectangleFootprint(
    { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 },
    lengthM,
    widthM,
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

function polygonPenetration(polygonA, polygonB, touchToleranceM, preferredPoint = null) {
  let minimum = null;
  for (const axis of [...polygonAxes(polygonA), ...polygonAxes(polygonB)]) {
    const a = projectionRange(polygonA, axis);
    const b = projectionRange(polygonB, axis);
    const overlap = Math.min(a.max, b.max) - Math.max(a.min, b.min);
    if (overlap <= touchToleranceM) return null;
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
  const distanceM = minimum.overlap + touchToleranceM;
  return {
    x: minimum.axis.x * sign * distanceM,
    y: minimum.axis.y * sign * distanceM,
    distanceM,
  };
}

function structureFootprint(item, kind) {
  if (kind === "beam") {
    return segmentFootprint(item, Math.max(0.01, Number(item?.thickness_m) || 0.3));
  }
  if (kind === "column") {
    const center = {
      x: Number(item?.center?.x),
      y: Number(item?.center?.y ?? item?.center?.z),
    };
    if (!Number.isFinite(center.x) || !Number.isFinite(center.y)) return null;
    return rectangleFootprint(
      center,
      Math.max(0.01, Number(item?.size_m) || 0.35),
      Math.max(0.01, Number(item?.depth_m) || Number(item?.size_m) || 0.35),
      Number(item?.rotation_deg) || 0,
    );
  }
  return null;
}

function pointToSegmentDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared <= 1e-9) return Math.hypot(point.x - start.x, point.y - start.y);
  const t = Math.max(0, Math.min(
    1,
    ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared,
  ));
  return Math.hypot(
    point.x - (start.x + dx * t),
    point.y - (start.y + dy * t),
  );
}

function beamEndpointSupportedByWall(item, wall, wallWidthM, touchToleranceM) {
  if (!item?.start || !item?.end || !wall?.start || !wall?.end) return false;
  const beamDx = Number(item.end.x) - Number(item.start.x);
  const beamDy = Number(item.end.y) - Number(item.start.y);
  const wallDx = Number(wall.end.x) - Number(wall.start.x);
  const wallDy = Number(wall.end.y) - Number(wall.start.y);
  const beamLength = Math.hypot(beamDx, beamDy);
  const wallLength = Math.hypot(wallDx, wallDy);
  if (beamLength < 0.001 || wallLength < 0.001) return false;
  const parallelDot = Math.abs(
    (beamDx / beamLength) * (wallDx / wallLength)
    + (beamDy / beamLength) * (wallDy / wallLength),
  );
  if (parallelDot > 0.25) return false;
  const wallStart = { x: Number(wall.start.x), y: Number(wall.start.y) };
  const wallEnd = { x: Number(wall.end.x), y: Number(wall.end.y) };
  const threshold = wallWidthM / 2 + touchToleranceM;
  return [item.start, item.end].some((endpoint) =>
    pointToSegmentDistance(
      { x: Number(endpoint.x), y: Number(endpoint.y) },
      wallStart,
      wallEnd,
    ) <= threshold
  );
}

function trimBeamEndpointsToWallFaces(item, walls, touchToleranceM) {
  const next = {
    ...item,
    start: { ...item.start },
    end: { ...item.end },
  };
  let totalTrimM = 0;
  for (const endpointKey of ["start", "end"]) {
    const otherKey = endpointKey === "start" ? "end" : "start";
    for (const wall of walls) {
      const beamDx = Number(next.end.x) - Number(next.start.x);
      const beamDy = Number(next.end.y) - Number(next.start.y);
      const wallDx = Number(wall?.end?.x) - Number(wall?.start?.x);
      const wallDy = Number(wall?.end?.y) - Number(wall?.start?.y);
      const beamLength = Math.hypot(beamDx, beamDy);
      const wallLength = Math.hypot(wallDx, wallDy);
      if (beamLength < 0.001 || wallLength < 0.001) continue;
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
        Math.max(0.01, Number(wall.thickness_m) || 0.12) / 2 + touchToleranceM;
      if (distance >= targetDistance) continue;
      const inward = {
        x: (other.x - point.x) / Math.hypot(other.x - point.x, other.y - point.y),
        y: (other.y - point.y) / Math.hypot(other.x - point.x, other.y - point.y),
      };
      const probe = {
        x: point.x + inward.x * 0.01,
        y: point.y + inward.y * 0.01,
      };
      if (pointToSegmentDistance(probe, wallStart, wallEnd) + 1e-6 < distance) {
        continue;
      }
      const trimM = targetDistance - distance;
      next[endpointKey] = {
        x: point.x + inward.x * trimM,
        y: point.y + inward.y * trimM,
      };
      totalTrimM += trimM;
    }
  }
  return { item: next, totalTrimM };
}

export function findStructureWallCollision(
  item,
  kind,
  walls = [],
  { touchToleranceM = 0.005, preferredPoint = null } = {},
) {
  const footprint = structureFootprint(item, kind);
  if (!footprint) return null;
  for (let index = 0; index < walls.length; index += 1) {
    const wall = walls[index];
    const wallWidthM = Math.max(0.01, Number(wall?.thickness_m) || 0.12);
    const wallFootprint = segmentFootprint(
      wall,
      wallWidthM,
    );
    const translation = wallFootprint
      ? polygonPenetration(footprint, wallFootprint, touchToleranceM, preferredPoint)
      : null;
    if (
      translation
      && !(kind === "beam"
        && beamEndpointSupportedByWall(item, wall, wallWidthM, touchToleranceM))
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
    touchToleranceM = 0.005,
    maxAutoShiftM = 0.75,
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
    ? trimBeamEndpointsToWallFaces(original, walls, touchToleranceM)
    : { item: original, totalTrimM: 0 };
  let candidate = trimmed.item;
  let totalShiftM = trimmed.totalTrimM;
  if (totalShiftM > maxAutoShiftM) {
    return { item: original, resolved: false, moved: false, totalShiftM: 0 };
  }
  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    const collision = findStructureWallCollision(candidate, kind, walls, {
      touchToleranceM,
      preferredPoint,
    });
    if (!collision) {
      return {
        item: candidate,
        resolved: true,
        moved: totalShiftM > 0,
        totalShiftM,
      };
    }
    totalShiftM += collision.translation.distanceM;
    if (totalShiftM > maxAutoShiftM) {
      return { item: original, resolved: false, moved: false, totalShiftM: 0 };
    }
    candidate = translatedStructure(candidate, kind, collision.translation);
  }
  return { item: original, resolved: false, moved: false, totalShiftM: 0 };
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
  { minimumDimensionM = 0.1, defaultHeightM = 2.7 } = {},
) {
  const widthM = Math.max(
    minimumDimensionM,
    Number(item?.size_m) || 0.35,
  );
  const depthM = Math.max(
    minimumDimensionM,
    Number(item?.depth_m) || Number(item?.size_m) || 0.35,
  );
  const heightM = Math.max(
    minimumDimensionM,
    Number(item?.height_m) || Number(defaultHeightM) || 2.7,
  );
  return {
    widthM,
    depthM,
    heightM,
    centerX: Number(item?.center?.x || 0),
    centerZ: Number(item?.center?.z ?? item?.center?.y ?? 0),
    centerHeightM: heightM / 2,
    rotationDeg: Number(item?.rotation_deg) || 0,
  };
}

export function structurePreviewDescriptor(
  item,
  kind,
  { ceilingHeightM = 2.7, planWidthM = 0, planDepthM = 0 } = {},
) {
  const safeCeilingHeight = Math.max(2.1, Number(ceilingHeightM) || 2.7);
  const centerX = kind === "column"
    ? Number(item?.center?.x || 0) - Number(planWidthM || 0) / 2
    : (Number(item?.start?.x || 0) + Number(item?.end?.x || 0)) / 2
      - Number(planWidthM || 0) / 2;
  const centerZ = kind === "column"
    ? Number(item?.center?.y ?? item?.center?.z ?? 0) - Number(planDepthM || 0) / 2
    : (Number(item?.start?.y ?? item?.start?.z ?? 0)
      + Number(item?.end?.y ?? item?.end?.z ?? 0)) / 2
      - Number(planDepthM || 0) / 2;
  if (kind === "beam") {
    const heightM = Math.max(0.1, Number(item?.height_m) || 0.35);
    return {
      kind,
      lengthM: Math.max(0.3, segmentLength(item)),
      widthM: Math.max(0.1, Number(item?.thickness_m) || 0.3),
      heightM,
      centerHeightM: safeCeilingHeight - heightM / 2,
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
      minimumDimensionM: 0.1,
      defaultHeightM: safeCeilingHeight,
    });
    return {
      kind,
      lengthM: column.widthM,
      widthM: column.depthM,
      heightM: column.heightM,
      centerHeightM: column.centerHeightM,
      centerX: column.centerX,
      centerZ: column.centerZ,
      rotationDeg: column.rotationDeg,
    };
  }
  return null;
}
