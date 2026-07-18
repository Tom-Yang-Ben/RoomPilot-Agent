const VIEW_PRESENTATIONS = Object.freeze({
  dollhouse: Object.freeze({
    walls: "full",
    hideOccludingWalls: true,
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
    hideOccludingWalls: true,
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
