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
