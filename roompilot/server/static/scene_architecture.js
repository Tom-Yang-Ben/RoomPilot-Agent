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

export function openingBelongsToWall(segment, opening, wallThickness = 0.12) {
  const wall = segmentVector(segment);
  const aperture = segmentVector(opening);
  if (wall.length < 0.04 || aperture.length < 0.04) return false;

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
  const proximity = Math.max(0.28, Number(wallThickness) * 2.4);
  const endTolerance = Math.max(aperture.length / 2, 0.35);

  return perpendicular <= proximity
    && along >= -endTolerance
    && along <= wall.length + endTolerance;
}
