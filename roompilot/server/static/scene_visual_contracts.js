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

export function computeExactModelScale(sourceSizeM, targetSizeM) {
  return {
    x: positiveRatio(targetSizeM.width, sourceSizeM.x),
    y: positiveRatio(targetSizeM.height, sourceSizeM.y),
    z: positiveRatio(targetSizeM.depth, sourceSizeM.z),
  };
}

export function clampWalkPosition(position, room, marginM = 0.25, eyeHeightM = 1.65) {
  const halfWidth = Math.max(Number(room.widthM || 0) / 2 - marginM, 0);
  const halfDepth = Math.max(Number(room.depthM || 0) / 2 - marginM, 0);
  const maxEyeHeight = Math.max(Number(room.wallHeight || 2.7) - 0.35, 1.2);
  return {
    x: Math.min(halfWidth, Math.max(-halfWidth, Number(position.x || 0))),
    y: Math.min(maxEyeHeight, Math.max(1.2, eyeHeightM)),
    z: Math.min(halfDepth, Math.max(-halfDepth, Number(position.z || 0))),
  };
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

export function synchronizedFloorRegions(floorplan = {}, widthM = 4.2, depthM = 3.6) {
  const regions = (floorplan.room_regions || [])
    .filter((region) => Array.isArray(region?.exterior) && region.exterior.length >= 3)
    .map((region, index) => ({
      room_id: String(region.room_id || `room-${index + 1}`),
      exterior: region.exterior,
      holes: Array.isArray(region.holes) ? region.holes : [],
    }));
  if (regions.length) return regions;

  const halfWidth = Math.max(Number(widthM) || 4.2, 0.1) / 2;
  const halfDepth = Math.max(Number(depthM) || 3.6, 0.1) / 2;
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

export function doorLeafTransform(opening = {}, swingDegrees = 58) {
  const start = opening.start || {};
  const end = opening.end || {};
  const startX = Number(start.x) || 0;
  const startZ = Number(start.z) || 0;
  const endX = Number(end.x) || 0;
  const endZ = Number(end.z) || 0;
  const dx = endX - startX;
  const dz = endZ - startZ;
  const measuredWidth = Math.hypot(dx, dz);
  const openingWidth = Math.max(Number(opening.width_m || opening.width) || measuredWidth, 0.68);
  const leafWidthM = Math.round(openingWidth * 0.94 * 10000) / 10000;
  const swingSign = opening.opening_direction === "left" ? 1 : -1;
  return {
    hinge: { x: startX, z: startZ },
    leafWidthM,
    leafCenterXM: leafWidthM / 2,
    closedRotationYRad: Math.atan2(-dz, dx),
    swingRotationYRad: swingSign * Number(swingDegrees) * Math.PI / 180,
  };
}
