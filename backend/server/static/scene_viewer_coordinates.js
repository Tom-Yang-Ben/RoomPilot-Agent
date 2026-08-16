import { openingWallInterval, wallSegmentForOpening } from "./scene_architecture.js?v=sha256-7899eae4c7ba";

function normalizeSceneRotationDeg(rotationDeg = 0) {
  return ((Number(rotationDeg) % 360) + 360) % 360;
}

function architecturalOpeningVector(opening = {}) {
  const start = opening.start || {};
  const end = opening.end || {};
  const startX = Number(start.x || 0);
  const startZ = Number(start.z || 0);
  const endX = Number(end.x || 0);
  const endZ = Number(end.z || 0);
  const dx = endX - startX;
  const dz = endZ - startZ;
  const length = Math.hypot(dx, dz);
  return {
    startX,
    startZ,
    endX,
    endZ,
    centerX: (startX + endX) / 2,
    centerZ: (startZ + endZ) / 2,
    length,
    unitX: length ? dx / length : 0,
    unitZ: length ? dz / length : 0,
  };
}

function architecturalOpeningsOverlap(left = {}, right = {}) {
  if (left.topology_gap === true || right.topology_gap === true) {
    return left.topology_gap === true
      && right.topology_gap === true
      && Boolean(left.topology_gap_key)
      && left.topology_gap_key === right.topology_gap_key;
  }
  const leftVector = architecturalOpeningVector(left);
  const rightVector = architecturalOpeningVector(right);
  if (leftVector.length < 4 || rightVector.length < 4) return false;
  const parallel = Math.abs(
    leftVector.unitX * rightVector.unitX + leftVector.unitZ * rightVector.unitZ,
  );
  if (parallel < 0.82) return false;
  const centerDistance = Math.hypot(
    leftVector.centerX - rightVector.centerX,
    leftVector.centerZ - rightVector.centerZ,
  );
  const endpointDistance = Math.min(
    Math.hypot(leftVector.startX - rightVector.startX, leftVector.startZ - rightVector.startZ)
      + Math.hypot(leftVector.endX - rightVector.endX, leftVector.endZ - rightVector.endZ),
    Math.hypot(leftVector.startX - rightVector.endX, leftVector.startZ - rightVector.endZ)
      + Math.hypot(leftVector.endX - rightVector.startX, leftVector.endZ - rightVector.startZ),
  );
  const width = Math.min(
    Number(left.width_cm || left.width || leftVector.length) || leftVector.length,
    Number(right.width_cm || right.width || rightVector.length) || rightVector.length,
  );
  return centerDistance <= Math.max(18, width * 0.28) || endpointDistance <= 36;
}

function openingWallCoverage(opening = {}, wallSegments = [], wallThickness = 12) {
  if (opening.topology_gap) return null;
  const hostSegment = wallSegmentForOpening(wallSegments, opening, wallThickness);
  if (!hostSegment) return null;
  const interval = openingWallInterval(hostSegment, opening, wallThickness, 24);
  if (!interval) return null;
  return { hostSegment, interval };
}

function openingAnchorOnWall(segment, interval) {
  const start = segment?.start || {};
  const end = segment?.end || {};
  const dx = Number(end.x) - Number(start.x);
  const dz = Number(end.z) - Number(start.z);
  const length = Math.hypot(dx, dz);
  if (length < 0.001 || !interval) return null;
  const center = (Number(interval.from) + Number(interval.to)) / 2;
  return {
    x: Number(start.x) + (dx / length) * center,
    z: Number(start.z) + (dz / length) * center,
  };
}

function openingAnchorForWallTopology(opening = {}, wallSegments = [], wallThickness = 12) {
  const coverage = openingWallCoverage(opening, wallSegments, wallThickness);
  return coverage ? openingAnchorOnWall(coverage.hostSegment, coverage.interval) : null;
}

function openingsShareWallCoverage(left = {}, right = {}, wallSegments = [], wallThickness = 12) {
  const leftCoverage = openingWallCoverage(left, wallSegments, wallThickness);
  const rightCoverage = openingWallCoverage(right, wallSegments, wallThickness);
  if (!leftCoverage || !rightCoverage || leftCoverage.hostSegment !== rightCoverage.hostSegment) {
    return false;
  }
  const overlap = Math.min(leftCoverage.interval.to, rightCoverage.interval.to)
    - Math.max(leftCoverage.interval.from, rightCoverage.interval.from);
  const narrowerWidth = Math.min(
    leftCoverage.interval.to - leftCoverage.interval.from,
    rightCoverage.interval.to - rightCoverage.interval.from,
  );
  // A repeated recognition can be offset from the wall line, but still cuts the
  // same physical span. Do not collapse neighbouring, genuinely separate doors.
  return overlap >= Math.max(24, narrowerWidth * 0.55);
}

function architecturalOpeningScore(opening = {}, wallSegments = [], wallThickness = 12) {
  const coverage = openingWallCoverage(opening, wallSegments, wallThickness);
  const vector = architecturalOpeningVector(opening);
  const host = coverage ? architecturalOpeningVector(coverage.hostSegment) : null;
  const centerOffset = host
    ? Math.abs(
      (vector.centerX - host.startX) * -host.unitZ
      + (vector.centerZ - host.startZ) * host.unitX,
    )
    : 0;
  return (opening.topology_gap ? 100 : 0)
    + (opening.confirmed ? 18 : 0)
    + (opening.source === "manual" ? 14 : 0)
    + Math.min(12, Number(opening.confidence || 0) * 12)
    - Math.min(30, centerOffset * 0.25);
}

function dedupeArchitecturalOpeningsFor3d(openings = [], wallSegments = [], wallThickness = 12) {
  const result = [];
  openings.filter(Boolean).forEach((opening) => {
    const openingId = String(opening?.id || "").trim();
    const duplicateIndex = result.findIndex(
      (candidate) => {
        const candidateId = String(candidate?.id || "").trim();
        if (openingId && candidateId && openingId === candidateId) return true;
        // Step 4 owns door identity; Step 6 must never merge distinct doors.
        // Each persisted door ID represents a separately confirmed physical door.
        if (openingId && candidateId) return false;
        const samePhysicalSpan = architecturalOpeningsOverlap(candidate, opening)
          || openingsShareWallCoverage(candidate, opening, wallSegments, wallThickness);
        return samePhysicalSpan;
      },
    );
    if (duplicateIndex < 0) {
      result.push(opening);
      return;
    }
    if (
      architecturalOpeningScore(opening, wallSegments, wallThickness)
      > architecturalOpeningScore(result[duplicateIndex], wallSegments, wallThickness)
    ) {
      result[duplicateIndex] = opening;
    }
  });
  return result;
}

function sceneToWorldPosition(position = {}) {
  return {
    x: Number(position.x || 0),
    z: -Number(position.z || 0),
  };
}

function worldToScenePosition(position = {}) {
  return {
    x: Math.round(Number(position.x || 0) * 100) / 100,
    z: Math.round(-Number(position.z || 0) * 100) / 100,
  };
}

function sceneToWorldRotationDeg(rotationDeg = 0) {
  return normalizeSceneRotationDeg(-Number(rotationDeg || 0));
}

function worldToSceneRotationDeg(rotationDeg = 0) {
  return normalizeSceneRotationDeg(-Number(rotationDeg || 0));
}

function flipPointZ(point) {
  if (Array.isArray(point)) return [Number(point[0] || 0), -Number(point[1] || 0)];
  if (!point || typeof point !== "object") return point;
  const next = { ...point };
  if ("z" in next) next.z = -Number(next.z || 0);
  if ("y" in next && !("z" in next)) next.y = -Number(next.y || 0);
  return next;
}

function flipSegmentZ(segment) {
  if (!segment || typeof segment !== "object") return segment;
  return {
    ...segment,
    start: flipPointZ(segment.start),
    end: flipPointZ(segment.end),
    swing_end: segment.swing_end ? flipPointZ(segment.swing_end) : segment.swing_end,
    confirmed_wall_opening: segment.confirmed_wall_opening
      ? flipSegmentZ(segment.confirmed_wall_opening)
      : segment.confirmed_wall_opening,
    wall_opening_segment: segment.wall_opening_segment
      ? flipSegmentZ(segment.wall_opening_segment)
      : segment.wall_opening_segment,
    closed_leaf_segment: segment.closed_leaf_segment
      ? flipSegmentZ(segment.closed_leaf_segment)
      : segment.closed_leaf_segment,
    rotation_deg: "rotation_deg" in segment
      ? sceneToWorldRotationDeg(segment.rotation_deg)
      : segment.rotation_deg,
  };
}

function flipBoundsZ(bounds) {
  if (!bounds || typeof bounds !== "object") return bounds;
  const minZ = Number(bounds.minZ);
  const maxZ = Number(bounds.maxZ);
  if (!Number.isFinite(minZ) || !Number.isFinite(maxZ)) return { ...bounds };
  return { ...bounds, minZ: -maxZ, maxZ: -minZ };
}

function flipPolygonRegionZ(region) {
  if (!region || typeof region !== "object") return region;
  return {
    ...region,
    exterior: (region.exterior || []).map(flipPointZ),
    holes: (region.holes || []).map((ring) => (ring || []).map(flipPointZ)),
    polygon_cm: (region.polygon_cm || []).map(flipPointZ),
  };
}

function floorplanForWorld(sceneData) {
  const floorplan = JSON.parse(JSON.stringify(sceneData?.floorplan || {}));
  [
    "wall_segments",
    "door_segments",
    "window_segments",
    "door_openings",
    "beam_segments",
  ].forEach((key) => {
    if (Array.isArray(floorplan[key])) floorplan[key] = floorplan[key].map(flipSegmentZ);
  });
  if (Array.isArray(floorplan.columns)) {
    floorplan.columns = floorplan.columns.map((column) => ({
      ...column,
      center: flipPointZ(column.center),
      rotation_deg: "rotation_deg" in column
        ? sceneToWorldRotationDeg(column.rotation_deg)
        : column.rotation_deg,
    }));
  }
  if (Array.isArray(floorplan.wall_polys)) {
    floorplan.wall_polys = floorplan.wall_polys.map(flipPolygonRegionZ);
  }
  if (Array.isArray(floorplan.room_regions)) {
    floorplan.room_regions = floorplan.room_regions.map(flipPolygonRegionZ);
  }
  return floorplan;
}

function sceneDataForWorld(sceneData) {
  const worldScene = {
    ...sceneData,
    floorplan: floorplanForWorld(sceneData),
    surface_overrides: (sceneData?.surface_overrides || []).map((override) => ({
      ...override,
      room_bounds_cm: flipBoundsZ(override.room_bounds_cm),
      room_polygon_cm: (override.room_polygon_cm || []).map(flipPointZ),
    })),
  };
  if (worldScene.material_boundary?.room_bounds_cm) {
    worldScene.material_boundary = {
      ...worldScene.material_boundary,
      room_bounds_cm: flipBoundsZ(worldScene.material_boundary.room_bounds_cm),
      line_cm: (worldScene.material_boundary.line_cm || []).map(flipPointZ),
    };
  }
  return worldScene;
}

export {
  dedupeArchitecturalOpeningsFor3d,
  openingAnchorForWallTopology,
  openingAnchorOnWall,
  sceneDataForWorld,
  sceneToWorldPosition,
  sceneToWorldRotationDeg,
  worldToScenePosition,
  worldToSceneRotationDeg,
};
