const VIEW_PRESENTATIONS = Object.freeze({
  dollhouse: Object.freeze({
    walls: "full",
    hideOccludingWalls: false,
    fadeExteriorWalls: false,
    showFurniturePlanLabels: false,
  }),
  walk: Object.freeze({
    walls: "full",
    hideOccludingWalls: false,
    fadeExteriorWalls: false,
    showFurniturePlanLabels: false,
  }),
  topdown: Object.freeze({
    walls: "flattened",
    hideOccludingWalls: false,
    fadeExteriorWalls: false,
    showFurniturePlanLabels: true,
  }),
  orbit: Object.freeze({
    walls: "full",
    hideOccludingWalls: false,
    fadeExteriorWalls: false,
    showFurniturePlanLabels: false,
  }),
});

function positiveRatio(target, source) {
  const ratio = Number(target) / Number(source);
  return Number.isFinite(ratio) && ratio > 0 ? ratio : 1;
}

export function computeExactModelScale(sourceAssetSize, targetSizeCm) {
  return {
    x: positiveRatio(targetSizeCm.width, sourceAssetSize.x),
    y: positiveRatio(targetSizeCm.height, sourceAssetSize.y),
    z: positiveRatio(targetSizeCm.depth, sourceAssetSize.z),
  };
}

export function clampWalkPosition(position, room, marginCm = 25, eyeHeightCm = 165) {
  const halfWidth = Math.max(Number(room.widthCm || 0) / 2 - marginCm, 0);
  const halfDepth = Math.max(Number(room.depthCm || 0) / 2 - marginCm, 0);
  const maxEyeHeight = Math.max(Number(room.wallHeight || 270) - 35, 120);
  return {
    x: Math.min(halfWidth, Math.max(-halfWidth, Number(position.x || 0))),
    y: Math.min(maxEyeHeight, Math.max(120, eyeHeightCm)),
    z: Math.min(halfDepth, Math.max(-halfDepth, Number(position.z || 0))),
  };
}

export function findNearestWalkablePosition(
  position,
  room,
  isWalkable,
  stepCm = 25,
) {
  if (typeof isWalkable !== "function") return null;
  const preferred = clampWalkPosition(position, room);
  if (isWalkable(preferred)) return preferred;

  const step = Math.max(Number(stepCm) || 25, 5);
  const maxDistance = Math.hypot(
    Math.max(Number(room.widthCm) || 0, 0),
    Math.max(Number(room.depthCm) || 0, 0),
  );
  const ringCount = Math.max(Math.ceil(maxDistance / step), 1);
  const visited = new Set([`${preferred.x}:${preferred.z}`]);

  for (let ring = 1; ring <= ringCount; ring += 1) {
    const offsets = [];
    for (let x = -ring; x <= ring; x += 1) {
      for (let z = -ring; z <= ring; z += 1) {
        if (Math.max(Math.abs(x), Math.abs(z)) !== ring) continue;
        offsets.push({ x, z, distance: Math.hypot(x, z) });
      }
    }
    offsets.sort((left, right) => (
      left.distance - right.distance
      || left.x - right.x
      || left.z - right.z
    ));

    for (const offset of offsets) {
      const candidate = clampWalkPosition({
        x: preferred.x + offset.x * step,
        y: preferred.y,
        z: preferred.z + offset.z * step,
      }, room);
      const key = `${candidate.x}:${candidate.z}`;
      if (visited.has(key)) continue;
      visited.add(key);
      if (isWalkable(candidate)) return candidate;
    }
  }

  return null;
}

export function viewPresentation(mode) {
  return { ...(VIEW_PRESENTATIONS[mode] || VIEW_PRESENTATIONS.orbit) };
}

export function fallbackMaterialRole(furnitureType = "") {
  const type = String(furnitureType).toLowerCase();
  if (/lamp|light/.test(type)) return "metal";
  if (/bookcase|cabinet|cupboard|wardrobe|table|desk|shelf|dresser|storage|bedside/.test(type)) return "wood";
  if (/bed|sofa|chair|bench|stool/.test(type)) return "fabric";
  return null;
}

function floorplanPoint(value = {}) {
  return {
    x: Number(value?.x ?? value?.[0]),
    z: Number(value?.z ?? value?.y ?? value?.[1]),
  };
}

function axisAlignedSpan(startValue, endValue) {
  const start = floorplanPoint(startValue);
  const end = floorplanPoint(endValue);
  if (![start.x, start.z, end.x, end.z].every(Number.isFinite)) return null;
  const dx = end.x - start.x;
  const dz = end.z - start.z;
  const length = Math.hypot(dx, dz);
  if (length < 4) return null;
  const vertical = Math.abs(dz) > Math.abs(dx);
  const crossAxisDelta = vertical ? Math.abs(dx) : Math.abs(dz);
  if (crossAxisDelta > Math.max(2, length * 0.02)) return null;
  return vertical
    ? {
        orientation: "vertical",
        normal: (start.x + end.x) / 2,
        from: Math.min(start.z, end.z),
        to: Math.max(start.z, end.z),
      }
    : {
        orientation: "horizontal",
        normal: (start.z + end.z) / 2,
        from: Math.min(start.x, end.x),
        to: Math.max(start.x, end.x),
      };
}

function roomBoundarySpans(floorplan = {}) {
  return (floorplan.room_regions || []).flatMap((region) => {
    const points = region?.exterior || [];
    if (points.length < 3) return [];
    return points
      .map((point, index) => axisAlignedSpan(point, points[(index + 1) % points.length]))
      .filter(Boolean);
  });
}

function median(values = []) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function inferredWallThicknessCm(floorplan = {}, fallbackCm = 12) {
  const fallback = Number(fallbackCm) > 0 ? Number(fallbackCm) : 12;
  const walls = floorplan.wall_segments || [];
  const boundaries = roomBoundarySpans(floorplan);
  const inferred = walls.flatMap((wall) => {
    const span = axisAlignedSpan(wall.start, wall.end);
    if (!span) return [];
    const signedDistances = boundaries
      .filter((boundary) => (
        boundary.orientation === span.orientation
        && Math.min(boundary.to, span.to) - Math.max(boundary.from, span.from) >= 4
      ))
      .map((boundary) => boundary.normal - span.normal)
      .filter((distance) => Math.abs(distance) >= 2 && Math.abs(distance) <= 35);
    const positive = signedDistances.filter((distance) => distance > 0);
    const negative = signedDistances.filter((distance) => distance < 0).map(Math.abs);
    const positiveFace = positive.length ? Math.min(...positive) : null;
    const negativeFace = negative.length ? Math.min(...negative) : null;
    const thickness = positiveFace != null && negativeFace != null
      ? positiveFace + negativeFace
      : 2 * (positiveFace ?? negativeFace ?? 0);
    return thickness >= 8 && thickness <= 60 ? [thickness] : [];
  });
  const inferredMedian = median(inferred);
  if (inferredMedian != null) return Math.round(inferredMedian * 1000) / 1000;

  const measured = [
    Number(floorplan.wall_thickness_cm),
    ...walls.map((wall) => Number(wall.thickness_cm)),
  ].filter((value) => Number.isFinite(value) && value >= 8 && value <= 60);
  const measuredMedian = median(measured);
  return measuredMedian == null ? fallback : Math.round(measuredMedian * 1000) / 1000;
}

function normalizedDegrees(value = 0) {
  const degrees = Number(value);
  return ((Number.isFinite(degrees) ? degrees : 0) % 360 + 360) % 360;
}

function furnitureHalfExtents(sizeCm = {}, rotationDeg = 0) {
  const width = Number(sizeCm.width);
  const depth = Number(sizeCm.depth);
  if (!(width > 0) || !(depth > 0)) return null;
  const radians = normalizedDegrees(rotationDeg) * Math.PI / 180;
  return {
    x: (width * Math.abs(Math.cos(radians)) + depth * Math.abs(Math.sin(radians))) / 2,
    z: (width * Math.abs(Math.sin(radians)) + depth * Math.abs(Math.cos(radians))) / 2,
  };
}

function finishedSurfaceSpans(floorplan = {}, roomId = "") {
  const expectedId = String(roomId || "");
  const region = (floorplan.room_regions || []).find((candidate, index) => (
    String(candidate?.room_id || candidate?.id || `room-${index + 1}`) === expectedId
  ));
  const points = (region?.exterior || []).map(floorplanPoint)
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.z));
  if (points.length < 3) return [];
  const center = points.reduce((total, point) => ({
    x: total.x + point.x / points.length,
    z: total.z + point.z / points.length,
  }), { x: 0, z: 0 });
  const boundaries = points.map((point, index) => {
    const span = axisAlignedSpan(point, points[(index + 1) % points.length]);
    if (!span) return null;
    const inwardDirection = Math.sign(
      (span.orientation === "vertical" ? center.x : center.z) - span.normal,
    );
    return { ...span, inwardDirection: inwardDirection || 1 };
  }).filter(Boolean);
  const walls = (floorplan.wall_segments || [])
    .map((wall) => axisAlignedSpan(wall.start, wall.end))
    .filter(Boolean);
  if (!walls.length) return boundaries;
  return boundaries.flatMap((boundary) => walls.flatMap((wall) => {
    if (wall.orientation !== boundary.orientation || Math.abs(wall.normal - boundary.normal) > 35) {
      return [];
    }
    const from = Math.max(boundary.from, wall.from);
    const to = Math.min(boundary.to, wall.to);
    return to - from >= 4 ? [{ ...boundary, from, to }] : [];
  }));
}

function roundedCoordinate(value) {
  return Math.round(value * 1000) / 1000;
}

export function snapFurnitureToRoomSurface({
  floorplan = {},
  roomId = "",
  sizeCm = {},
  position = {},
  rotationDeg = 0,
  snapRangeCm = 30,
  gridCm = 5,
} = {}) {
  const surfaces = finishedSurfaceSpans(floorplan, roomId);
  const width = Number(sizeCm.width);
  const depth = Number(sizeCm.depth);
  const x = Number(position.x);
  const z = Number(position.z);
  if (!surfaces.length || !(width > 0) || !(depth > 0) || !Number.isFinite(x) || !Number.isFinite(z)) {
    return null;
  }

  const snapRange = Math.max(Number(snapRangeCm) || 30, 0);
  const grid = Math.max(Number(gridCm) || 5, 1);
  const candidates = surfaces.flatMap((surface) => {
    const targetRotation = surface.orientation === "vertical" ? 90 : 0;
    const half = furnitureHalfExtents({ width, depth }, targetRotation);
    const along = surface.orientation === "vertical" ? z : x;
    const alongHalf = surface.orientation === "vertical" ? half.z : half.x;
    if (along < surface.from - alongHalf || along > surface.to + alongHalf) return [];
    const normalHalf = surface.orientation === "vertical" ? half.x : half.z;
    const value = surface.normal + surface.inwardDirection * normalHalf;
    const distance = Math.abs((surface.orientation === "vertical" ? x : z) - value);
    return distance <= snapRange
      ? [{ ...surface, value, distance, rotationDeg: targetRotation }]
      : [];
  }).sort((left, right) => left.distance - right.distance);

  const primary = candidates[0];
  if (!primary) {
    return {
      x: Math.round(x / grid) * grid,
      z: Math.round(z / grid) * grid,
      rotationDeg: normalizedDegrees(rotationDeg),
      kind: "grid",
    };
  }

  const snapped = { x, z };
  snapped[primary.orientation === "vertical" ? "x" : "z"] = primary.value;
  const finalHalf = furnitureHalfExtents({ width, depth }, primary.rotationDeg);
  const secondary = surfaces.filter((surface) => surface.orientation !== primary.orientation)
    .flatMap((surface) => {
      const along = surface.orientation === "vertical" ? snapped.z : snapped.x;
      const alongHalf = surface.orientation === "vertical" ? finalHalf.z : finalHalf.x;
      if (along < surface.from - alongHalf || along > surface.to + alongHalf) return [];
      const normalHalf = surface.orientation === "vertical" ? finalHalf.x : finalHalf.z;
      const value = surface.normal + surface.inwardDirection * normalHalf;
      const distance = Math.abs((surface.orientation === "vertical" ? x : z) - value);
      return distance <= snapRange ? [{ ...surface, value, distance }] : [];
    })
    .sort((left, right) => left.distance - right.distance)[0];
  if (secondary) snapped[secondary.orientation === "vertical" ? "x" : "z"] = secondary.value;

  return {
    x: roundedCoordinate(snapped.x),
    z: roundedCoordinate(snapped.z),
    rotationDeg: primary.rotationDeg,
    kind: secondary ? "corner" : "wall",
  };
}

export function synchronizedFloorRegions(floorplan = {}, widthCm = 420, depthCm = 360) {
  const regions = (floorplan.room_regions || [])
    .filter((region) => Array.isArray(region?.exterior) && region.exterior.length >= 3)
    .map((region, index) => ({
      room_id: String(region.room_id || `room-${index + 1}`),
      exterior: region.exterior,
      holes: Array.isArray(region.holes) ? region.holes : [],
    }));
  if (regions.length) return regions;

  const halfWidth = Math.max(Number(widthCm) || 420, 10) / 2;
  const halfDepth = Math.max(Number(depthCm) || 360, 10) / 2;
  return [{
    room_id: "whole-floor",
    exterior: [
      [-halfWidth, -halfDepth],
      [halfWidth, -halfDepth],
      [halfWidth, halfDepth],
      [-halfWidth, halfDepth],
    ],
    holes: [],
  }];
}

export function expandedFloorSlabRing(ring = [], bleedCm = 0) {
  // 房間 region 是「室內淨空」多邊形:相鄰房之間隔著整條牆帶(floor04 實測約
  // 26.9cm),門洞下方與牆體下方因此完全沒有地板,俯視會看到一條條透到背景的
  // 破口。基底樓板把每個 region 外環向外偏移 bleedCm,讓地板延伸到牆體下方與
  // 門檻;偏移量以「蓋住半條牆帶」為準,仍小於外牆外緣,不會露出屋外。
  // 純幾何、不依賴 three:每條邊沿外法線平移後與相鄰邊求交(miter)。
  const pts = ring
    .map((point) => ({
      x: Number(Array.isArray(point) ? point[0] : point?.x),
      z: Number(Array.isArray(point) ? point[1] : point?.z),
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.z));
  if (pts.length > 1
    && pts[0].x === pts[pts.length - 1].x
    && pts[0].z === pts[pts.length - 1].z) {
    pts.pop();
  }
  if (pts.length < 3 || !(Number(bleedCm) > 0)) {
    return pts.map((point) => [point.x, point.z]);
  }

  let doubledArea = 0;
  for (let i = 0; i < pts.length; i += 1) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    doubledArea += a.x * b.z - b.x * a.z;
  }
  const outwardSign = doubledArea >= 0 ? 1 : -1;

  const offsetEdges = pts.map((a, i) => {
    const b = pts[(i + 1) % pts.length];
    const dx = b.x - a.x;
    const dz = b.z - a.z;
    const length = Math.hypot(dx, dz) || 1;
    const nx = (outwardSign * dz) / length;
    const nz = (outwardSign * -dx) / length;
    return { ax: a.x + nx * bleedCm, az: a.z + nz * bleedCm, dx, dz };
  });

  return offsetEdges.map((edge, i) => {
    const prev = offsetEdges[(i - 1 + offsetEdges.length) % offsetEdges.length];
    const det = prev.dx * edge.dz - prev.dz * edge.dx;
    if (Math.abs(det) < 1e-9) return [edge.ax, edge.az];
    const t = ((edge.ax - prev.ax) * edge.dz - (edge.az - prev.az) * edge.dx) / det;
    return [prev.ax + prev.dx * t, prev.az + prev.dz * t];
  });
}

export function doorLeafTransform(opening = {}, swingDegrees = 0) {
  const start = opening.start || {};
  const end = opening.end || {};
  const startX = Number(start.x) || 0;
  const startZ = Number(start.z) || 0;
  const endX = Number(end.x) || 0;
  const endZ = Number(end.z) || 0;
  const dx = endX - startX;
  const dz = endZ - startZ;
  const measuredWidth = Math.hypot(dx, dz);
  const openingWidth = Math.max(Number(opening.width_cm || opening.width) || measuredWidth, 68);
  const leafWidthCm = Math.round(openingWidth * 0.94 * 10) / 10;
  const swingSign = opening.opening_direction === "left" ? 1 : -1;
  return {
    hinge: { x: startX, z: startZ },
    leafWidthCm,
    leafCenterXCm: leafWidthCm / 2,
    closedRotationYRad: Math.atan2(-dz, dx),
    swingRotationYRad: swingSign * Number(swingDegrees) * Math.PI / 180,
  };
}
