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
  if (opening?.topology_gap) return false;
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

export function doorOpeningForWallTopology(
  segments = [],
  door = {},
  wallThickness = 12,
) {
  const leaf = segmentVector(door);
  if (leaf.length < 4) return door;
  const requestedWidth = Number(door.width_cm || door.width) || leaf.length;
  const hingeCandidates = [leaf.start, leaf.end];
  const maximumGap = Math.max(180, requestedWidth * 1.45);
  const hingeTolerance = Math.max(35, Number(wallThickness) * 1.8);
  const candidates = [];

  segments.forEach((first, firstIndex) => {
    const firstVector = segmentVector(first);
    if (firstVector.length < 4) return;
    segments.slice(firstIndex + 1).forEach((second) => {
      const secondVector = segmentVector(second);
      if (secondVector.length < 4) return;
      const wallParallel = Math.abs(
        firstVector.unitX * secondVector.unitX
        + firstVector.unitZ * secondVector.unitZ,
      );
      if (wallParallel < 0.98) return;

      [firstVector.start, firstVector.end].forEach((firstEndpoint) => {
        [secondVector.start, secondVector.end].forEach((secondEndpoint) => {
          const gapX = secondEndpoint.x - firstEndpoint.x;
          const gapZ = secondEndpoint.z - firstEndpoint.z;
          const gapLength = Math.hypot(gapX, gapZ);
          if (gapLength < 50 || gapLength > maximumGap) return;
          const gapUnitX = gapX / gapLength;
          const gapUnitZ = gapZ / gapLength;
          const gapFollowsWall = Math.abs(
            gapUnitX * firstVector.unitX + gapUnitZ * firstVector.unitZ,
          );
          if (gapFollowsWall < 0.98) return;
          const leafPerpendicular = Math.abs(
            gapUnitX * leaf.unitX + gapUnitZ * leaf.unitZ,
          );
          if (leafPerpendicular > 0.35) return;

          const hingeDistance = Math.min(
            ...hingeCandidates.flatMap((hinge) => [
              Math.hypot(hinge.x - firstEndpoint.x, hinge.z - firstEndpoint.z),
              Math.hypot(hinge.x - secondEndpoint.x, hinge.z - secondEndpoint.z),
            ]),
          );
          if (hingeDistance > hingeTolerance) return;
          const widthDifference = Math.abs(gapLength - requestedWidth);
          if (widthDifference > Math.max(30, requestedWidth * 0.3)) return;
          candidates.push({
            firstEndpoint,
            secondEndpoint,
            score: hingeDistance + widthDifference * 0.5,
          });
        });
      });
    });
  });

  if (!candidates.length) return door;
  const best = candidates.sort((left, right) => left.score - right.score)[0];
  return {
    ...door,
    start: { ...best.firstEndpoint },
    end: { ...best.secondEndpoint },
    original_host_wall_id: door.host_wall_id || null,
    host_wall_id: null,
    topology_gap: true,
    door_leaf_segment: {
      start: { ...leaf.start },
      end: { ...leaf.end },
    },
  };
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

export function wallEndpointBordersOpening(
  endpoint,
  openings = [],
  wallThickness = 12,
) {
  const target = point(endpoint);
  const tolerance = Math.max(1.5, Number(wallThickness) * 0.2);
  return openings.some((opening) => {
    const aperture = segmentVector(opening);
    return Math.hypot(target.x - aperture.start.x, target.z - aperture.start.z) <= tolerance
      || Math.hypot(target.x - aperture.end.x, target.z - aperture.end.z) <= tolerance;
  });
}

export function wallSectionSpan(from, to, wallLength, seamOverlap = 0.6) {
  const length = Math.max(0, Number(wallLength) || 0);
  return {
    from: Number(from) <= 0.1
      ? 0
      : Math.max(0, Number(from) - seamOverlap),
    to: Number(to) >= length - 0.1
      ? length
      : Math.min(length, Number(to) + seamOverlap),
  };
}

export function wallSegmentForOpening(
  segments = [],
  opening = {},
  wallThickness = 12,
) {
  const hostWallId = String(opening.host_wall_id || opening.hostWallId || "");
  if (hostWallId) {
    const confirmedHost = segments.find((segment) => segmentId(segment) === hostWallId);
    if (confirmedHost) return confirmedHost;
  }
  return segments.find(
    (segment) => openingBelongsToWall(segment, opening, wallThickness),
  ) || null;
}
