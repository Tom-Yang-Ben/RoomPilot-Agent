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

function topologyGapKey(firstEndpoint = {}, secondEndpoint = {}) {
  const endpoints = [point(firstEndpoint), point(secondEndpoint)]
    .map((endpoint) => `${endpoint.x.toFixed(1)},${endpoint.z.toFixed(1)}`)
    .sort();
  return `gap:${endpoints.join("|")}`;
}

function pointDistance(left = {}, right = {}) {
  const a = point(left);
  const b = point(right);
  return Math.hypot(a.x - b.x, a.z - b.z);
}

function geometricOpeningWallInterval(segment, opening, wallThickness = 12) {
  const wall = segmentVector(segment);
  const aperture = segmentVector(opening);
  if (wall.length < 4 || aperture.length < 4) return null;
  const parallel = Math.abs(wall.unitX * aperture.unitX + wall.unitZ * aperture.unitZ);
  if (parallel < 0.82) return null;
  const centerX = (aperture.start.x + aperture.end.x) / 2;
  const centerZ = (aperture.start.z + aperture.end.z) / 2;
  const relX = centerX - wall.start.x;
  const relZ = centerZ - wall.start.z;
  const along = relX * wall.unitX + relZ * wall.unitZ;
  const perpendicular = Math.abs(relX * -wall.unitZ + relZ * wall.unitX);
  const width = Math.max(Number(opening.width_cm || opening.width) || aperture.length, 24);
  if (perpendicular > Math.max(28, Number(wallThickness) * 2.4)) return null;
  if (along < -width / 2 || along > wall.length + width / 2) return null;
  return { perpendicular };
}

export function closedDoorSegment(door = {}) {
  const primary = segmentVector(door);
  if (primary.length < 4) return null;

  const persisted = segmentVector(door.closed_segment || {});
  if (persisted.length >= 4) {
    return {
      source: door.closed_segment?.source || "closed_segment",
      start: persisted.start,
      end: persisted.end,
    };
  }
  if (!door.swing_end) {
    return { source: "primary_segment", start: primary.start, end: primary.end };
  }
  const swingEnd = point(door.swing_end);
  const swingLength = pointDistance(primary.start, swingEnd);
  const cross = primary.dx * (swingEnd.z - primary.start.z)
    - primary.dz * (swingEnd.x - primary.start.x);
  const sameRadius = Math.abs(swingLength - primary.length) <= Math.max(18, primary.length * 0.18);
  const perpendicular = primary.length && swingLength
    ? Math.abs((primary.dx * (swingEnd.x - primary.start.x)
      + primary.dz * (swingEnd.z - primary.start.z)) / (primary.length * swingLength))
    : 1;
  if (sameRadius && perpendicular <= 0.3 && Math.abs(cross) > 0.1) {
    return { source: "swing_radius", start: primary.start, end: swingEnd };
  }
  // 弧線不完整時不可把另一條半徑當成候選門洞，只保留原線待人工校正。
  return { source: "primary_segment", start: primary.start, end: primary.end };
}

function candidateGapForDoor(segments, opening, wallThickness = 12) {
  const aperture = segmentVector(opening);
  const requestedWidth = Number(opening.width_cm || opening.width) || aperture.length;
  const maximumGap = Math.max(180, requestedWidth * 1.45);
  const endpointTolerance = Math.max(35, Number(wallThickness) * 2.2, requestedWidth * 0.28);
  const candidates = [];
  segments.forEach((first, firstIndex) => {
    const firstVector = segmentVector(first);
    if (firstVector.length < 4) return;
    segments.slice(firstIndex + 1).forEach((second) => {
      const secondVector = segmentVector(second);
      if (secondVector.length < 4) return;
      if (Math.abs(firstVector.unitX * secondVector.unitX + firstVector.unitZ * secondVector.unitZ) < 0.98) return;
      [firstVector.start, firstVector.end].forEach((firstEndpoint) => {
        [secondVector.start, secondVector.end].forEach((secondEndpoint) => {
          const gapX = secondEndpoint.x - firstEndpoint.x;
          const gapZ = secondEndpoint.z - firstEndpoint.z;
          const gapLength = Math.hypot(gapX, gapZ);
          if (gapLength < 50 || gapLength > maximumGap) return;
          const followsOpening = Math.abs(
            (gapX / gapLength) * aperture.unitX + (gapZ / gapLength) * aperture.unitZ,
          );
          if (followsOpening < 0.98) return;
          const direct = pointDistance(aperture.start, firstEndpoint)
            + pointDistance(aperture.end, secondEndpoint);
          const reverse = pointDistance(aperture.start, secondEndpoint)
            + pointDistance(aperture.end, firstEndpoint);
          const endpointDistance = Math.min(direct, reverse) / 2;
          const widthDifference = Math.abs(gapLength - requestedWidth);
          if (endpointDistance > endpointTolerance || widthDifference > Math.max(30, requestedWidth * 0.3)) return;
          candidates.push({ firstEndpoint, secondEndpoint, score: endpointDistance + widthDifference * 0.5 });
        });
      });
    });
  });
  return candidates.sort((left, right) => left.score - right.score)[0] || null;
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
  const closed = closedDoorSegment(door);
  if (leaf.length < 4 || !closed) return door;
  const closedOpening = {
    ...door,
    start: { ...closed.start },
    end: { ...closed.end },
    closed_segment: {
      start: { ...closed.start },
      end: { ...closed.end },
      source: closed.source,
    },
  };

  // 「已確認有這扇門」不等於「已人工確認它屬於這面牆」。辨識器
  // 預填的 host_wall_id 仍可能錯誤；只有使用者手動貼齊後才可鎖牆。
  const confirmedHost = (
    door.host_wall_confirmed === true
    || door.source === "manual"
  )
    ? wallSegmentForOpening(segments, closedOpening, wallThickness)
    : null;
  if (confirmedHost && openingWallInterval(confirmedHost, closedOpening, wallThickness, 68)) {
    return {
      ...closedOpening,
      topology_gap: false,
      original_host_wall_id: null,
    };
  }

  // 開合門的關門線已由 closedDoorSegment 正規化。原始主線是打開後的
  // 門片，只保留供第 4 步顯示與鉸鏈判讀，絕不可再成為第二個門洞。
  const gapCandidate = candidateGapForDoor(segments, closedOpening, wallThickness);
  if (gapCandidate) {
    const best = gapCandidate;
    return {
      ...closedOpening,
      start: { ...best.firstEndpoint },
      end: { ...best.secondEndpoint },
      original_host_wall_id: door.host_wall_id || null,
      host_wall_id: null,
      topology_gap: true,
      topology_gap_key: topologyGapKey(best.firstEndpoint, best.secondEndpoint),
      opening_source: closed.source,
      door_leaf_segment: {
        start: { ...leaf.start },
        end: { ...leaf.end },
      },
    };
  }

  const directCandidate = segments.map((segment) => {
    const geometricInterval = geometricOpeningWallInterval(segment, closedOpening, wallThickness);
    const renderInterval = openingWallInterval(segment, closedOpening, wallThickness, 68);
    if (!geometricInterval || !renderInterval) return null;
    const requestedWidth = Number(closedOpening.width_cm || closedOpening.width)
      || segmentVector(closedOpening).length;
    if (renderInterval.width < Math.max(68, requestedWidth * 0.65)) return null;
    return { segment, score: geometricInterval.perpendicular };
  })
    .filter(Boolean)
    .sort((left, right) => left.score - right.score)[0];
  if (directCandidate) {
    return {
      ...closedOpening,
      host_wall_id: segmentId(directCandidate.segment) || null,
      original_host_wall_id: door.host_wall_id || null,
      topology_gap: false,
      opening_source: closed.source,
      door_leaf_segment: {
        start: { ...leaf.start },
        end: { ...leaf.end },
      },
    };
  }

  const requestedWidth = Number(closedOpening.width_cm || closedOpening.width)
    || segmentVector(closedOpening).length;
  const hingeCandidates = [closed.start, closed.end];
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
          const closedPerpendicular = Math.abs(
            gapUnitX * segmentVector(closedOpening).unitX
              + gapUnitZ * segmentVector(closedOpening).unitZ,
          );
          if (closedPerpendicular > 0.35) return;

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

  if (!candidates.length) {
    return {
      ...closedOpening,
      opening_source: closed.source,
      needs_manual_host_confirmation: true,
    };
  }
  const best = candidates.sort((left, right) => left.score - right.score)[0];
  return {
    ...closedOpening,
    start: { ...best.firstEndpoint },
    end: { ...best.secondEndpoint },
    original_host_wall_id: door.host_wall_id || null,
    host_wall_id: null,
    topology_gap: true,
    topology_gap_key: topologyGapKey(best.firstEndpoint, best.secondEndpoint),
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
