function point(value = {}) {
  return {
    x: Number(value.x) || 0,
    z: Number(value.z) || 0,
  };
}

function segmentVector(segment = {}) {
  const start = point(segment.start);
  const end = point(segment.end);
  const dx = end.x - start.x;
  const dz = end.z - start.z;
  const length = Math.hypot(dx, dz);
  return {
    start,
    end,
    dx,
    dz,
    length,
    unitX: length ? dx / length : 0,
    unitZ: length ? dz / length : 0,
  };
}

function segmentId(segment = {}) {
  return String(segment.id || segment.wall_id || segment.segment_id || "");
}

export function openingBelongsToWall(segment, opening, wallThickness = 12) {
  const wall = segmentVector(segment);
  const aperture = segmentVector(opening);
  if (wall.length < 4 || aperture.length < 4) return false;

  const hostWallId = String(opening.host_wall_id || opening.hostWallId || "");
  const wallId = segmentId(segment);
  if (hostWallId && wallId) return hostWallId === wallId;

  const parallel = Math.abs(
    wall.unitX * aperture.unitX + wall.unitZ * aperture.unitZ,
  );
  if (parallel < 0.82) return false;

  const centerX = (aperture.start.x + aperture.end.x) / 2;
  const centerZ = (aperture.start.z + aperture.end.z) / 2;
  const relX = centerX - wall.start.x;
  const relZ = centerZ - wall.start.z;
  const along = relX * wall.unitX + relZ * wall.unitZ;
  const perpendicular = Math.abs(relX * -wall.unitZ + relZ * wall.unitX);
  const proximity = Math.max(28, Number(wallThickness) * 2.4);
  const endTolerance = Math.max(aperture.length / 2, 35);

  return perpendicular <= proximity
    && along >= -endTolerance
    && along <= wall.length + endTolerance;
}

export function openingWallInterval(
  segment,
  opening,
  wallThickness = 12,
  minimumOpeningWidth = 24,
) {
  if (!openingBelongsToWall(segment, opening, wallThickness)) return null;
  const wall = segmentVector(segment);
  const aperture = segmentVector(opening);
  const centerX = (aperture.start.x + aperture.end.x) / 2;
  const centerZ = (aperture.start.z + aperture.end.z) / 2;
  const relX = centerX - wall.start.x;
  const relZ = centerZ - wall.start.z;
  const along = relX * wall.unitX + relZ * wall.unitZ;
  const perpendicular = Math.abs(relX * -wall.unitZ + relZ * wall.unitX);
  if (perpendicular > Math.max(28, Number(wallThickness) * 2.4)) return null;

  const requestedWidth = Number(opening.width_cm || opening.width) || aperture.length;
  const width = Math.max(requestedWidth, Number(minimumOpeningWidth) || 24);
  const from = Math.max(0, along - width / 2);
  const to = Math.min(wall.length, along + width / 2);
  if (to - from < 24) return null;
  return { from, to, width: to - from, centerX, centerZ };
}
