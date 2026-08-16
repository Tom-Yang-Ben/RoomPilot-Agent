// Confirmed plan, room scheme comparison, and Step 6 surface workflow.
export function createSceneSchemeController({
  $,
  $$,
  activePanelName,
  activeScheme,
  activeSchemeId,
  allRoomsHaveSchemeSelections,
  applyWindowTypePreset,
  attachedOpenings,
  beamDragGeometry,
  buildDimensionedPlanAnnotations,
  canMarkWallForDemolition,
  clipPolygonByLine,
  configurationBlockingFurniture,
  confirmedWallGapForDoor,
  convexHull,
  deactivateWhiteInteractionMode,
  dedupeDoorCandidates,
  dedupeWindowCandidates,
  element,
  ensureRenovationScheme,
  ensureSchemeB,
  errorMessage,
  escapeHtml,
  findStructureWallCollision,
  glbThumbnailQueue,
  glbThumbnailViewer,
  goTo,
  imagePoint,
  instructions,
  invalidateDownstreamFrom,
  invalidateRenovationScheme,
  materialOptionsForStyle,
  nearestPointOnSegment,
  normalizedWindowType,
  openingHostWall,
  pointInPolygonCm,
  polygonArea,
  previewStepSixRoomSurfaces,
  renderStructureCounts,
  renderStructureSvg,
  renderStyleControls,
  renderWhiteWalkRoomSelector,
  renderWholeHouseQuestionnaire,
  repairLoadedRoomPolygon,
  repairLoadedStructureWallCollisions,
  resolveStructureWallCollisions,
  resolveSurfaceOption,
  reviewItemsFromAnalysis,
  ROOM_NAME_OPTIONS,
  roomDimensions,
  roomNameOptionFor,
  roomPolygonsDiffer,
  roomSchemePreviewCache,
  roomSchemePreviewViewer,
  roomSchemeRuntimeState,
  scheduleSave,
  selectedSchemeForRoom,
  selectSchemeForRoom,
  setStatus,
  showStep,
  state,
  structurePreview,
  structureRuntimeState,
  structuresForScheme,
  STYLE_MATERIAL_OPTIONS,
  syncOverlayToImage,
  unresolvedReviewRooms,
  userFacingMaterialLabel,
  validateColumnDimensionsCm,
  wallBoundarySide,
  whiteViewer,
  WINDOW_TYPES,
  windowsOverlap,
}) {
function planGeometry() {
  const imageWidth = state.analysis?.image_size_px?.width || element.spaceImage.naturalWidth || 1000;
  const imageHeight = state.analysis?.image_size_px?.height || element.spaceImage.naturalHeight || 1000;
  const scale = Number(state.analysis?.scale?.cm_per_px)
    || Number(state.analysis?.scale?.m_per_px) * 100
    || 1;
  const bbox = state.analysis?.plan_bbox_px || [0, 0, imageWidth, imageHeight];
  return { imageWidth, imageHeight, scale, bbox };
}

function confirmedFloorplanEditor(schemeId = activeSchemeId()) {
  if (
    !state.confirmedStructureSnapshot
    && state.workflow?.completed.includes("space_confirmation")
  ) {
    // Old saved projects did not persist this snapshot. Build it once from
    // their already-confirmed Step 4 structures, then keep it authoritative.
    state.confirmedStructureSnapshot = captureConfirmedStructureSnapshot();
  }
  const { scale, bbox } = planGeometry();
  const recognizedWidthCm = Math.max(240, (bbox[2] - bbox[0]) * scale);
  const recognizedDepthCm = Math.max(240, (bbox[3] - bbox[1]) * scale);
  return {
    coordinate_unit: "cm",
    width_cm: Number(
      state.confirmedFloorplan?.floorplan?.width_cm || recognizedWidthCm,
    ),
    depth_cm: Number(
      state.confirmedFloorplan?.floorplan?.depth_cm || recognizedDepthCm,
    ),
    room_height_cm: Number(
      state.confirmedFloorplan?.floorplan?.room_height_cm || 270,
    ),
    rooms: JSON.parse(JSON.stringify(state.rooms)),
    structures: structuresForScheme(
      state.confirmedStructureSnapshot || state.structures,
      schemeId,
    ),
  };
}

function captureConfirmedStructureSnapshot() {
  const snapshot = JSON.parse(JSON.stringify(state.structures));
  // Step 4 wall segments are the sole source of door apertures.  A door's
  // visible blue leaf is its open position, so it must never select or split
  // a host wall in Step 6.  The green swing radius is used only to render the
  // closed leaf inside the existing gap between confirmed wall segments.
  snapshot.doors = (snapshot.doors || []).map((door) => ({
    ...door,
    host_wall_id: null,
    host_wall_confirmed: false,
    step4_confirmed: true,
    step4_skip_wall_cut: true,
    doorway_source: "confirmed_wall_gap",
    confirmed_wall_opening: confirmedWallOpeningForSnapshot(
      door,
      snapshot.walls || [],
    ),
  }));
  // Windows are actual wall apertures, so they retain their confirmed host
  // wall and may cut that wall in the Step 6 model.
  snapshot.windows = (snapshot.windows || []).map((window) => {
    const liveWindow = state.structures.windows?.find((item) => item.id === window.id) || window;
    const host = openingHostWall(liveWindow);
    return {
      ...window,
      host_wall_id: host?.id || null,
      host_wall_confirmed: Boolean(host),
      step4_confirmed: true,
      step4_skip_wall_cut: !host,
    };
  });
  return snapshot;
}

function structuralSnapshotPoint(point = {}) {
  return {
    x: Number(point.x),
    z: Number(point.y),
  };
}

function isStructuralSnapshotPoint(point = {}) {
  return Number.isFinite(Number(point.x)) && Number.isFinite(Number(point.y));
}

function confirmedWallOpeningForSnapshot(door = {}, walls = []) {
  const persisted = door.confirmed_wall_opening;
  if (
    isStructuralSnapshotPoint(persisted?.start)
    && isStructuralSnapshotPoint(persisted?.end)
  ) {
    return {
      start: { ...persisted.start },
      end: { ...persisted.end },
    };
  }

  const sceneWalls = walls
    .filter((wall) => isStructuralSnapshotPoint(wall.start) && isStructuralSnapshotPoint(wall.end))
    .map((wall) => ({
      ...wall,
      start: structuralSnapshotPoint(wall.start),
      end: structuralSnapshotPoint(wall.end),
    }));
  const sceneDoor = (
    isStructuralSnapshotPoint(door.start)
    && isStructuralSnapshotPoint(door.end)
    && isStructuralSnapshotPoint(door.swing_end)
  )
    ? {
      ...door,
      start: structuralSnapshotPoint(door.start),
      end: structuralSnapshotPoint(door.end),
      swing_end: structuralSnapshotPoint(door.swing_end),
    }
    : null;
  const gap = sceneDoor
    ? confirmedWallGapForDoor(sceneWalls, sceneDoor, 12)
    : null;
  return gap
    ? {
      start: { x: gap.start.x, y: gap.start.z },
      end: { x: gap.end.x, y: gap.end.z },
    }
    : null;
}

function hydrateConfirmedStructureSnapshot(snapshot, fallbackStructures = state.structures) {
  if (!snapshot) return null;
  const walls = snapshot.walls?.length
    ? snapshot.walls
    : (fallbackStructures?.walls || []);
  return {
    ...snapshot,
    doors: (snapshot.doors || []).map((door) => ({
      ...door,
      confirmed_wall_opening: confirmedWallOpeningForSnapshot(door, walls),
    })),
  };
}

function confirmedRoomHeightCm() {
  return Math.max(210, Number(confirmedFloorplanEditor().room_height_cm) || 270);
}

function hydrateSceneWallMass() {
  if (!state.sceneData?.floorplan) return;
  const confirmedPolys = state.confirmedFloorplan?.floorplan?.wall_polys || [];
  if (!state.sceneData.floorplan.wall_polys?.length && confirmedPolys.length) {
    state.sceneData.floorplan.wall_polys = JSON.parse(JSON.stringify(confirmedPolys));
  }
}

function cmToPixel(point) {
  const { scale, bbox } = planGeometry();
  return {
    x: bbox[0] + Number(point.x) / scale,
    y: bbox[3] - Number(point.y) / scale,
  };
}

function pixelToCm(point) {
  const { scale, bbox } = planGeometry();
  return {
    x: (point.x - bbox[0]) * scale,
    y: (bbox[3] - point.y) * scale,
  };
}

const ICON_INFERENCE_MAX_ROOM_AREA_M2 = {
  bathroom: 30,
  bedroom: 80,
  kitchen: 80,
};
const STORAGE_INFERENCE_MAX_AREA_CM2 = 500_000;

function genericPendingRoomLabel(room, index) {
  const id = String(room?.id || room?.room_id || "");
  const suffix = id.split("-").at(-1);
  if (/^\d+$/.test(suffix)) return `空間 ${suffix}（待確認）`;
  return `空間 ${index + 1}（待確認）`;
}

function normalizeIconInferredRoomReview(room, polygonCm, index) {
  const next = { ...room };
  const roomType = next.type || next.room_type;
  const maxAreaM2 = ICON_INFERENCE_MAX_ROOM_AREA_M2[roomType];
  const areaM2 = polygonCm.length >= 3
    ? polygonArea(polygonCm) / 10_000
    : Number(next.area_m2 || next.net_area_m2 || 0);
  const reasons = Array.isArray(next.room_review_reasons)
    ? [...next.room_review_reasons]
    : [];
  if (
    next.source === "furniture_icon_inference"
    && maxAreaM2
    && areaM2 > maxAreaM2
  ) {
    next.type = "default";
    next.room_type = "default";
    next.label = genericPendingRoomLabel(next, index);
    next.room_review = true;
    next.confirmed = false;
    if (!reasons.includes("room_icon_area_implausible")) {
      reasons.push("room_icon_area_implausible");
    }
  }
  if (reasons.length) next.room_review_reasons = reasons;
  return next;
}

function pendingRoomBaseLabel(room, fallbackIndex) {
  const label = String(room?.label || room?.name || genericPendingRoomLabel(room, fallbackIndex));
  return label.replace(/\s*（待確認）\s*/g, "").trim() || `空間 ${fallbackIndex + 1}`;
}

function splitImplausibleIconRoomsByInteriorWalls(rooms, walls) {
  const result = [];
  let splitCount = 0;
  const icons = (state.analysis?.room_icon_evidence || [])
    .map((icon) => ({ ...icon, centroid_cm: roomIconCentroidCm(icon) }))
    .filter((icon) => icon.centroid_cm);
  rooms.forEach((room, index) => {
    const reasons = Array.isArray(room.room_review_reasons) ? room.room_review_reasons : [];
    const polygon = room.polygon_cm || [];
    const area = polygonArea(polygon);
    const iconsInRoom = icons.filter((icon) => pointInPolygonCm(icon.centroid_cm, polygon));
    const hasBedIcon = iconsInRoom.some((icon) => icon.class === "bed" && Number(icon.score || 0) >= 0.55);
    const splitDepth = Number(room.auto_split_depth || 0);
    const canContinueSplit = (
      room.auto_split_reason === "room_icon_area_implausible"
      && splitDepth < 2
      && !hasBedIcon
      && area > STORAGE_INFERENCE_MAX_AREA_CM2
    );
    if (
      !reasons.includes("room_icon_area_implausible")
      || polygon.length < 4
      || (room.auto_split_reason && !canContinueSplit)
    ) {
      result.push(room);
      return;
    }
    const xs = polygon.map((point) => Number(point.x || 0));
    const ys = polygon.map((point) => Number(point.y || 0));
    const bounds = {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;
    const candidates = (walls || [])
      .map((wall) => {
        const start = wall.start || {};
        const end = wall.end || {};
        const x0 = Number(start.x || 0);
        const y0 = Number(start.y || 0);
        const x1 = Number(end.x || 0);
        const y1 = Number(end.y || 0);
        const dx = Math.abs(x1 - x0);
        const dy = Math.abs(y1 - y0);
        const length = Math.hypot(dx, dy);
        if (length < 250) return null;
        const vertical = dy > dx * 3;
        const horizontal = dx > dy * 3;
        if (!vertical && !horizontal) return null;
        const midX = (x0 + x1) / 2;
        const midY = (y0 + y1) / 2;
        if (vertical && (midX <= bounds.minX + 60 || midX >= bounds.maxX - 60)) return null;
        if (horizontal && (midY <= bounds.minY + 60 || midY >= bounds.maxY - 60)) return null;
        const startPoint = vertical
          ? { x: midX, y: bounds.minY - 20 }
          : { x: bounds.minX - 20, y: midY };
        const endPoint = vertical
          ? { x: midX, y: bounds.maxY + 20 }
          : { x: bounds.maxX + 20, y: midY };
        const firstPolygon = clipPolygonByLine(polygon, startPoint, endPoint, true);
        const secondPolygon = clipPolygonByLine(polygon, startPoint, endPoint, false);
        const firstArea = polygonArea(firstPolygon);
        const secondArea = polygonArea(secondPolygon);
        const minArea = Math.min(firstArea, secondArea);
        if (
          firstPolygon.length < 3
          || secondPolygon.length < 3
          || minArea < 80_000
        ) return null;
        const spanRatio = vertical ? length / Math.max(height, 1) : length / Math.max(width, 1);
        return {
          firstPolygon,
          secondPolygon,
          score: (spanRatio * 100) + (minArea / Math.max(firstArea + secondArea, 1) * 40),
        };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score);
    const best = candidates[0];
    if (!best) {
      result.push(room);
      return;
    }
    const baseLabel = pendingRoomBaseLabel(room, index);
    [best.firstPolygon, best.secondPolygon].forEach((splitPolygon, splitIndex) => {
      result.push({
        ...room,
        id: `${room.id || `room-${index + 1}`}-auto-split-${splitIndex + 1}`,
        label: `${baseLabel}${splitIndex === 0 ? "A" : "B"}（待確認）`,
        type: "default",
        room_type: "default",
        confidence: Math.min(Number(room.confidence || 0.5), 0.62),
        confirmed: false,
        source: "auto_wall_split_review",
        split_from: room.id,
        root_split_from: room.root_split_from || room.split_from || room.id,
        auto_split_reason: "room_icon_area_implausible",
        auto_split_depth: splitDepth + 1,
        polygon_cm: splitPolygon,
      });
    });
    splitCount += 1;
  });
  if (splitCount > 0) {
    state.roomAutoSplitCount = (state.roomAutoSplitCount || 0) + splitCount;
    return splitImplausibleIconRoomsByInteriorWalls(result, walls);
  }
  return result;
}

function roomIconCentroidCm(icon) {
  const centroid = icon?.centroid_px;
  const bbox = state.analysis?.plan_bbox_px;
  const cmPerPx = Number(state.analysis?.scale?.cm_per_px)
    || Number(state.analysis?.scale?.m_per_px) * 100;
  if (!Array.isArray(centroid) || centroid.length < 2 || !Array.isArray(bbox) || bbox.length < 4 || !cmPerPx) {
    return null;
  }
  return {
    x: (Number(centroid[0]) - Number(bbox[0])) * cmPerPx,
    y: (Number(bbox[3]) - Number(centroid[1])) * cmPerPx,
  };
}

function addRoomReviewReason(room, reason) {
  const reasons = Array.isArray(room.room_review_reasons) ? [...room.room_review_reasons] : [];
  if (!reasons.includes(reason)) reasons.push(reason);
  room.room_review_reasons = reasons;
}

function isDismissedAutoRoom(room) {
  if (!room) return false;
  const dismissed = new Set(state.dismissedAutoRoomIds || []);
  return dismissed.has(room.id)
    || dismissed.has(room.split_from)
    || dismissed.has(room.root_split_from);
}

function applyDjangoZoneRoomLabels(rooms) {
  const icons = (state.analysis?.room_icon_evidence || [])
    .map((icon) => ({ ...icon, centroid_cm: roomIconCentroidCm(icon) }))
    .filter((icon) => icon.centroid_cm);
  if (!icons.length) return rooms;
  const groups = new Map();
  rooms.forEach((room) => {
    if (!room.split_from || room.auto_split_reason !== "room_icon_area_implausible") return;
    const groupKey = room.root_split_from || room.split_from;
    const siblings = groups.get(groupKey) || [];
    siblings.push(room);
    groups.set(groupKey, siblings);
  });
  groups.forEach((siblings) => {
    if (siblings.length < 2) return;
    const iconsByRoom = new Map(siblings.map((room) => [room.id, []]));
    icons.forEach((icon) => {
      const room = siblings.find((candidate) => pointInPolygonCm(icon.centroid_cm, candidate.polygon_cm));
      if (room) iconsByRoom.get(room.id)?.push(icon);
    });
    const bedroomRooms = siblings.filter((room) => (
      iconsByRoom.get(room.id)?.some((icon) => icon.class === "bed" && Number(icon.score || 0) >= 0.55)
    ));
    if (bedroomRooms.length !== 1) return;
    const bedroom = bedroomRooms[0];
    bedroom.type = "bedroom";
    bedroom.room_type = "bedroom";
    bedroom.label = "臥室（待確認）";
    bedroom.source = "django_zone_inference";
    bedroom.confirmed = false;
    bedroom.room_review = true;
    bedroom.confidence = Math.max(Number(bedroom.confidence || 0), 0.62);
    addRoomReviewReason(bedroom, "django_zone_bed_anchor");

    const bedroomArea = polygonArea(bedroom.polygon_cm || []);
    const storageCandidates = siblings
      .filter((room) => room.id !== bedroom.id && !(iconsByRoom.get(room.id) || []).length)
      .map((room) => ({ room, area: polygonArea(room.polygon_cm || []) }))
      .filter(({ area }) => area > 0 && area <= STORAGE_INFERENCE_MAX_AREA_CM2 && area <= Math.max(120_000, bedroomArea * 0.75))
      .sort((a, b) => a.area - b.area);
    const storage = storageCandidates[0]?.room;
    if (!storage) return;
    storage.type = "storage";
    storage.room_type = "storage";
    storage.label = "儲藏室（待確認）";
    storage.source = "django_zone_inference";
    storage.confirmed = false;
    storage.room_review = true;
    storage.confidence = Math.max(Number(storage.confidence || 0), 0.58);
    addRoomReviewReason(storage, "django_zone_storage_candidate");
    let pendingIndex = 2;
    siblings.forEach((room) => {
      if (room.id === bedroom.id || room.id === storage.id) return;
      if ((room.type || room.room_type) !== "default") return;
      room.label = `空間 ${pendingIndex}（待確認）`;
      pendingIndex += 1;
    });
  });
  return rooms;
}

function preparedAutoRoomLabels(rooms, walls) {
  return applyDjangoZoneRoomLabels(
    splitImplausibleIconRoomsByInteriorWalls(rooms, walls),
  ).filter((room) => !isDismissedAutoRoom(room));
}

const CANONICAL_ROOM_LABELS = Object.freeze({
  entryway: "玄關",
  living_room: "客廳",
  kitchen: "廚房",
  bedroom: "臥室",
  bathroom: "浴室",
  storage: "書房／儲藏室",
  balcony: "陽台",
  hallway: "走道／動線",
  stair: "樓梯",
  garage: "車庫",
});
const CIRCLED_ROOM_ORDINALS = Object.freeze(["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]);

function applyCanonicalRoomLabels(rooms) {
  const counts = new Map();
  rooms.forEach((room) => {
    const type = String(room.type || room.room_type || "");
    if (CANONICAL_ROOM_LABELS[type]) counts.set(type, (counts.get(type) || 0) + 1);
  });
  const seen = new Map();
  rooms.forEach((room, roomIndex) => {
    const type = String(room.type || room.room_type || "");
    const baseLabel = CANONICAL_ROOM_LABELS[type];
    if (!baseLabel) {
      if (type && type !== "default") {
        room.type = "default";
        room.room_type = "default";
        room.visual_space_type = "";
        room.label = genericPendingRoomLabel(room, roomIndex);
        room.confirmed = false;
      }
      return;
    }
    const index = (seen.get(type) || 0) + 1;
    seen.set(type, index);
    room.label = counts.get(type) > 1
      ? `${baseLabel}（${CIRCLED_ROOM_ORDINALS[index - 1] || index}）`
      : baseLabel;
    room.visual_space_type = type;
    room.type = type;
    room.room_type = type;
  });
  return rooms;
}

function initializeRoomsAndStructures() {
  const floorplan = state.analysis?.floorplan
    || state.confirmedFloorplan?.floorplan
    || {};
  const hasImageRooms = Boolean(state.analysis?.rooms?.length);
  const sourceRooms = hasImageRooms
    ? state.analysis.rooms
    : floorplan.room_regions || [];
  const widthCm = Number(floorplan.width_cm || 600);
  const depthCm = Number(floorplan.depth_cm || 400);
  const analysisUnit = String(state.analysis?.coordinate_system?.unit || "").toLowerCase();
  const analysisIsCm = ["cm", "centimeter", "centimetre"].includes(analysisUnit)
    || Number(state.analysis?.scale?.cm_per_px) > 0
    || sourceRooms.some((room) => Array.isArray(room?.polygon_cm));
  const sourceScale = hasImageRooms
    ? (analysisIsCm ? 1 : 100)
    : (floorplan.coordinate_unit === "cm" ? 1 : 100);
  const normalizePoint = (point, centered = false) => {
    const x = Number(point?.x ?? point?.[0] ?? 0) * sourceScale;
    const y = Number(point?.y ?? point?.z ?? point?.[1] ?? 0) * sourceScale;
    return {
      x: x + (centered ? widthCm / 2 : 0),
      y: y + (centered ? depthCm / 2 : 0),
    };
  };
  const canonicalStructure = (item = {}) => {
    const result = Object.fromEntries(
      Object.entries(item).filter(([key]) => !key.endsWith("_m") && key !== "size_m"),
    );
    const dimension = (cmKey, legacyKey, fallback) => {
      if (Number.isFinite(Number(item[cmKey]))) return Number(item[cmKey]);
      if (Number.isFinite(Number(item[legacyKey]))) return Number(item[legacyKey]) * 100;
      return fallback;
    };
    return {
      ...result,
      width_cm: dimension("width_cm", "width_m", undefined),
      thickness_cm: dimension("thickness_cm", "thickness_m", undefined),
      height_cm: dimension("height_cm", "height_m", undefined),
      top_cm: dimension("top_cm", "top_m", undefined),
      depth_cm: dimension("depth_cm", "depth_m", undefined),
      size_cm: dimension("size_cm", "size_m", undefined),
      sill_height_cm: dimension("sill_height_cm", "sill_height_m", undefined),
      head_height_cm: dimension("head_height_cm", "head_height_m", undefined),
    };
  };
  let repairedRoomCount = 0;
  state.rooms = sourceRooms.map((room, index) => {
    const polygon = room.polygon_cm || room.polygon_m || room.polygon || room.exterior || [];
    const normalizedPolygon = polygon.map((point) => normalizePoint(point, !hasImageRooms));
    const shouldRepair = (
      room.polygon_source === "cody_wall_enclosure"
      && room.confirmed !== true
    );
    const repairedPolygon = shouldRepair
      ? repairLoadedRoomPolygon(normalizedPolygon)
      : normalizedPolygon;
    const geometryRepaired = roomPolygonsDiffer(repairedPolygon, normalizedPolygon);
    if (geometryRepaired) repairedRoomCount += 1;
    const normalizedRoom = normalizeIconInferredRoomReview(room, repairedPolygon, index);
    return {
      ...normalizedRoom,
      id: room.id || room.room_id || `room-${index + 1}`,
      label: normalizedRoom.label || normalizedRoom.name || `空間 ${index + 1}`,
      type: normalizedRoom.type || normalizedRoom.room_type || "default",
      confirmed: geometryRepaired ? false : normalizedRoom.confirmed === true,
      geometry_repaired: geometryRepaired || room.geometry_repaired === true,
      polygon_cm: repairedPolygon,
    };
  }).filter((room) => room.polygon_cm.length >= 3);
  if (!state.rooms.length) {
    state.rooms = [{
      id: "room-1",
      label: "未命名空間",
      type: "default",
      confidence: 0.4,
      confirmed: false,
      polygon_cm: [{ x: 0, y: 0 }, { x: widthCm, y: 0 }, { x: widthCm, y: depthCm }, { x: 0, y: depthCm }],
    }];
  }
  const normalizeSegment = (item, index, kind, centered = false) => ({
    ...canonicalStructure(item),
    id: item.id || `${kind}-${index + 1}`,
    start: normalizePoint(item.start, centered),
    end: normalizePoint(item.end, centered),
  });
  const imageStructures = {
    walls: state.analysis?.walls || [],
    doors: state.analysis?.doors || [],
    windows: state.analysis?.windows || [],
    beams: state.analysis?.beams || [],
    columns: state.analysis?.columns || [],
  };
  const floorplanStructures = {
    walls: floorplan.wall_segments || floorplan.plan_segments || [],
    doors: floorplan.door_segments || [],
    windows: floorplan.window_segments || [],
    beams: floorplan.beam_segments || [],
    columns: floorplan.columns || [],
  };
  const sourceStructures = hasImageRooms ? imageStructures : floorplanStructures;
  state.structures = {
    walls: sourceStructures.walls.map((item, index) =>
      normalizeSegment(item, index, "wall", !hasImageRooms)),
    doors: sourceStructures.doors.map((item, index) =>
      normalizeSegment(item, index, "door", !hasImageRooms)),
    windows: sourceStructures.windows.map((item, index) =>
      normalizeSegment(item, index, "window", !hasImageRooms)),
    beams: sourceStructures.beams.map((item, index) =>
      normalizeSegment(item, index, "beam", !hasImageRooms)),
    columns: sourceStructures.columns.map((item, index) => ({
      ...canonicalStructure(item),
      id: item.id || `column-${index + 1}`,
      center: normalizePoint(item.center, !hasImageRooms),
    })),
  };
  state.rooms = applyCanonicalRoomLabels(preparedAutoRoomLabels(state.rooms, state.structures.walls));
  normalizeWallDemolitionCandidates();
  repairLoadedStructureWallCollisions();
  const normalizedDoors = dedupeDoorCandidates(state.structures.doors);
  state.structures.doors = normalizedDoors.doors;
  state.doorNormalizationRemoved = normalizedDoors.removed;
  const normalizedWindows = dedupeWindowCandidates(state.structures.windows);
  state.structures.windows = normalizedWindows.windows;
  state.windowNormalizationRemoved = normalizedWindows.removed;
  state.selectedRoomId = state.rooms[0]?.id || null;
  renderRooms();
  renderSpaceOverlay();
  renderStructureCounts();
  if (repairedRoomCount > 0) {
    element.spaceError.textContent =
      `已修復 ${repairedRoomCount} 個房間的異常岔出節點，請重新確認房間輪廓。`;
  }
}

function roomPolygonSvg(room) {
  return room.polygon_cm.map(cmToPixel).map((point) => `${point.x},${point.y}`).join(" ");
}

function roomReviewHint(room) {
  const reasons = Array.isArray(room.room_review_reasons) ? room.room_review_reasons : [];
  if (reasons.includes("room_icon_function_conflict")) {
    return "偵測到不同功能圖示，可能是多個空間，請切割或改名後再確認。";
  }
  if (reasons.includes("django_zone_storage_candidate")) {
    return "依家具圖示與分區推測可能為儲藏室，仍需人工確認。";
  }
  if (reasons.includes("django_zone_bed_anchor")) {
    return "依床的位置推測為臥室，仍需人工確認。";
  }
  if (reasons.includes("room_icon_area_implausible")) {
    return "圖示與房間面積不合理，請檢查是否需要切割空間。";
  }
  if (reasons.includes("room_icon_low_confidence")) {
    return "圖示辨識信心不足，請確認空間名稱。";
  }
  return "";
}

function analysisReviewItems() {
  return reviewItemsFromAnalysis(state.analysis);
}

function recognitionReviewSuffix() {
  const items = analysisReviewItems();
  if (!items.length) return "";
  // 第 3 步時 state.rooms 尚未 ingestion，以房間清單為基準會算成 0；
  // 房間還沒進來就直接數被標記的房間數。
  const flagged = state.rooms.length
    ? unresolvedReviewRooms(items, state.rooms).length
    : new Set(items.map((item) => String(item.room_id))).size;
  return flagged ? `；系統標記 ${flagged} 間房需人工複核` : "";
}

// 標題列與畫布工具列各有一顆「查看全部空間」。以前兩顆共用同一個 id，
// $() 只會抓到第一顆，第二顆完全沒有綁定也不會更新狀態。
const SHOW_ALL_ROOMS_BUTTONS = ["#show-all-rooms", "#show-all-rooms-canvas"];

function updateShowAllRoomsButton() {
  const button = $("#show-all-rooms");
  if (!button) return;
  const hasMultipleRooms = state.rooms.length > 1;
  button.disabled = !hasMultipleRooms;
  button.setAttribute(
    "aria-disabled",
    hasMultipleRooms ? "false" : "true",
  );
  button.title = hasMultipleRooms
    ? "顯示所有已框選的空間"
    : "目前只有一個空間，沒有其他框選可顯示";
}


function renderRooms() {
  element.roomList.innerHTML = state.rooms.map((room) => {
    const dimensions = roomDimensions(room);
    const active = room.id === state.selectedRoomId;
    const merging = state.mergeRoomIds.includes(room.id);
    const reviewHint = roomReviewHint(room);
    return `
      <article class="rp-room-item ${active ? "is-active" : ""} ${merging ? "is-merge-selected" : ""}">
        <button type="button" data-room-id="${escapeHtml(room.id)}" class="rp-room-select">
          <strong>${escapeHtml(room.label)}</strong>
          <span>${dimensions.areaM2.toFixed(2)} m²</span>
          <small>${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm</small>
          <small>${room.confirmed ? "已確認" : `信心 ${(Number(room.confidence || room.polygon_confidence || 0.7) * 100).toFixed(0)}%`}</small>
          ${reviewHint ? `<small class="rp-room-review-hint">${escapeHtml(reviewHint)}</small>` : ""}
        </button>
        <button type="button" data-confirm-room="${escapeHtml(room.id)}"
          class="rp-room-confirm ${room.confirmed ? "is-confirmed" : ""}">
          ${room.confirmed ? "已確認" : "確認"}
        </button>
        <button type="button" data-delete-room="${escapeHtml(room.id)}" class="rp-room-delete danger-action">
          刪除
        </button>
      </article>
    `;
  }).join("");
  const confirmedCount = state.rooms.filter((room) => room.confirmed).length;
  element.roomConfirmationProgress.textContent =
    `已確認 ${confirmedCount} / ${state.rooms.length} 個房間`;
  const confirmAllRoomsButton = $("#confirm-all-rooms");
  if (confirmAllRoomsButton) {
    const allConfirmed = state.rooms.length > 0 && confirmedCount === state.rooms.length;
    confirmAllRoomsButton.disabled = !state.rooms.length || allConfirmed;
    confirmAllRoomsButton.textContent = allConfirmed
      ? "全部房間已確認"
      : "一鍵確認全部房間";
  }
  updateShowAllRoomsButton();
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (room) {
    const dimensions = roomDimensions(room);
    element.roomEditor.hidden = false;
    element.roomName.value = roomNameOptionFor(room).id;
    element.roomArea.textContent =
      `系統依目前框選計算：${dimensions.widthCm.toFixed(0)} × ${dimensions.depthCm.toFixed(0)} cm，${dimensions.areaM2.toFixed(2)} m²`;
  } else {
    element.roomEditor.hidden = true;
  }
}

function confirmRoom(roomId) {
  const room = state.rooms.find((item) => item.id === roomId);
  if (!room) return;
  room.confirmed = true;
  room.confidence = 1;
  room.source = "manual_confirmation";
  room.label = room.label.replace(/\s*（待確認）\s*/g, "").trim() || "未命名空間";
  state.selectedRoomId = room.id;
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
  setStatus(`已確認「${room.label}」；請繼續確認其他房間。`);
}

function confirmAllRooms() {
  if (!state.rooms.length) return;
  state.rooms.forEach((room) => {
    room.confirmed = true;
    room.confidence = 1;
    room.source = "manual_confirmation";
    room.label = room.label.replace(/\s*（待確認）\s*/g, "").trim() || "未命名空間";
  });
  element.spaceError.textContent = "";
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
  setStatus(`已一次確認 ${state.rooms.length} 個房間；仍可逐房修改名稱或框選。`);
}

function deleteRoom(roomId = state.selectedRoomId) {
  const roomIndex = state.rooms.findIndex((item) => item.id === roomId);
  if (roomIndex < 0) return;
  if (state.rooms.length <= 1) {
    element.spaceError.textContent = "至少需要保留一個空間，無法刪除最後一個空間。";
    return;
  }
  const room = state.rooms[roomIndex];
  const message = room.confirmed
    ? `「${room.label}」已確認。確定要刪除此空間嗎？`
    : `確定要刪除「${room.label}」嗎？`;
  if (!confirm(message)) return;
  if (room.source === "auto_wall_split_review" || room.source === "django_zone_inference" || room.split_from) {
    state.dismissedAutoRoomIds = [
      ...new Set([
        ...(state.dismissedAutoRoomIds || []),
        room.id,
      ]),
    ];
  }
  state.rooms.splice(roomIndex, 1);
  const nextRoom = state.rooms[Math.min(roomIndex, state.rooms.length - 1)] || state.rooms[0] || null;
  state.selectedRoomId = nextRoom?.id || null;
  state.mergeRoomIds = state.mergeRoomIds.filter((id) => id !== room.id);
  state.roomGeometryMode = null;
  state.splitPoints = [];
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  state.showAllRooms = true;
  element.spaceError.textContent = "";
  updateRoomGeometryControls();
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已刪除，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus(`已刪除「${room.label}」。`);
}

function addMissedRoom() {
  const center = state.selectedRoomId
    ? roomCenter(state.rooms.find((room) => room.id === state.selectedRoomId))
    : planCenterCm();
  const widthCm = 240;
  const depthCm = 240;
  const room = {
    id: `room-manual-${Date.now()}`,
    label: `新增空間 ${state.rooms.length + 1}`,
    type: "default",
    confidence: 0.35,
    confirmed: false,
    manually_added: true,
    polygon_cm: [
      { x: center.x - widthCm / 2, y: center.y - depthCm / 2 },
      { x: center.x + widthCm / 2, y: center.y - depthCm / 2 },
      { x: center.x + widthCm / 2, y: center.y + depthCm / 2 },
      { x: center.x - widthCm / 2, y: center.y + depthCm / 2 },
    ],
  };
  state.rooms.push(room);
  state.selectedRoomId = room.id;
  state.showAllRooms = false;
  invalidateDownstreamFrom(
    "space_confirmation",
    "已新增漏辨識空間；請拖曳節點、命名並重新確認空間與結構。",
  );
  renderRooms();
  renderSpaceOverlay();
  scheduleSave("space_confirmation");
}

function updateRoomGeometryControls() {
  $$("[data-room-geometry-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.roomGeometryMode === state.roomGeometryMode);
  });
  $("#apply-room-merge").hidden =
    state.roomGeometryMode !== "merge" || state.mergeRoomIds.length !== 2;
  $("#cancel-room-geometry").hidden = !state.roomGeometryMode;
  if (state.roomGeometryMode === "merge") {
    element.roomGeometryGuidance.textContent = state.mergeRoomIds.length === 2
      ? "已選兩個房間。確認左圖範圍後，按「合併所選兩個房間」。"
      : `請在左圖或清單點選兩個相鄰房間，目前已選 ${state.mergeRoomIds.length} 個。`;
  } else if (state.roomGeometryMode === "split") {
    element.roomGeometryGuidance.textContent = state.splitPoints.length === 1
      ? "已設定切割線起點，請在左圖點第二點。"
      : "請先選取要切割的房間，再在左圖點兩點定義切割線。";
  } else {
    element.roomGeometryGuidance.textContent =
      "先逐一確認右側房間；需要時可合併或以兩點切割。";
  }
}

function setRoomGeometryMode(mode) {
  state.roomGeometryMode = state.roomGeometryMode === mode ? null : mode;
  state.mergeRoomIds = [];
  state.splitPoints = [];
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  state.showAllRooms = true;
  element.spaceError.textContent = "";
  updateRoomNodeControls();
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
}

function updateRoomNodeControls() {
  $$("[data-room-node-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.roomNodeMode === state.roomNodeMode);
  });
  $("#apply-node-merge").hidden =
    state.roomNodeMode !== "merge" || state.selectedRoomNodeIndices.length !== 2;
  $("#cancel-node-edit").hidden = !state.roomNodeMode;
  if (state.roomNodeMode === "merge") {
    element.roomNodeGuidance.textContent = state.selectedRoomNodeIndices.length === 2
      ? "已選兩點。確認是相鄰節點後，按「合併所選兩個節點」。"
      : `請在左圖點選兩個相鄰紫色節點，目前已選 ${state.selectedRoomNodeIndices.length} 個。`;
  } else if (state.roomNodeMode === "split") {
    element.roomNodeGuidance.textContent = "請直接點房間框的邊線，系統會在最近位置新增一個可拖曳節點。";
  } else {
    element.roomNodeGuidance.textContent = "需要微調輪廓時，可合併相鄰節點或在邊線新增節點。";
  }
}

function setRoomNodeMode(mode) {
  state.roomNodeMode = state.roomNodeMode === mode ? null : mode;
  state.selectedRoomNodeIndices = [];
  state.roomGeometryMode = null;
  state.mergeRoomIds = [];
  state.splitPoints = [];
  state.showAllRooms = false;
  element.spaceError.textContent = "";
  updateRoomGeometryControls();
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
}

function mergeSelectedRoomNodes() {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room || state.selectedRoomNodeIndices.length !== 2) return;
  const polygon = room.polygon_cm;
  const [first, second] = [...state.selectedRoomNodeIndices].sort((a, b) => a - b);
  const adjacent = second - first === 1 || (first === 0 && second === polygon.length - 1);
  if (!adjacent) {
    element.spaceError.textContent = "只能合併同一條邊上的兩個相鄰節點，請重新選擇。";
    return;
  }
  if (polygon.length <= 3) {
    element.spaceError.textContent = "房間至少需要三個節點，這兩點不能再合併。";
    return;
  }
  const midpoint = {
    x: (polygon[first].x + polygon[second].x) / 2,
    y: (polygon[first].y + polygon[second].y) / 2,
  };
  const mergedPolygon = polygon.map((point) => ({ ...point }));
  if (first === 0 && second === polygon.length - 1) {
    mergedPolygon[0] = midpoint;
    mergedPolygon.pop();
  } else {
    mergedPolygon[first] = midpoint;
    mergedPolygon.splice(second, 1);
  }
  if (polygonArea(mergedPolygon) < 5_000) {
    element.spaceError.textContent = "合併後房間面積會小於 0.5 m²，請保留這兩個節點。";
    return;
  }
  room.polygon_cm = mergedPolygon;
  room.confirmed = false;
  room.source = "manual_node_merge";
  element.spaceError.textContent = "";
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間節點已合併，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("兩個相鄰節點已合併；房間尺寸與面積已重新計算。");
}

function nearestPointOnRoomEdge(point, polygon) {
  let closest = null;
  polygon.forEach((start, edgeIndex) => {
    const end = polygon[(edgeIndex + 1) % polygon.length];
    const projected = nearestPointOnSegment(point, start, end);
    const distance = Math.hypot(point.x - projected.x, point.y - projected.y);
    if (!closest || distance < closest.distance) {
      closest = { edgeIndex, projected, distance };
    }
  });
  return closest;
}

function insertRoomNodeAt(point) {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room) return;
  const closest = nearestPointOnRoomEdge(point, room.polygon_cm);
  if (!closest || closest.distance > 35) {
    element.spaceError.textContent = "請點在房間框邊線附近，系統才可新增節點。";
    return;
  }
  const start = room.polygon_cm[closest.edgeIndex];
  const end = room.polygon_cm[(closest.edgeIndex + 1) % room.polygon_cm.length];
  if (
    Math.hypot(closest.projected.x - start.x, closest.projected.y - start.y) < 8
    || Math.hypot(closest.projected.x - end.x, closest.projected.y - end.y) < 8
  ) {
    element.spaceError.textContent = "新節點離既有節點太近，請改點邊線中間的位置。";
    return;
  }
  room.polygon_cm.splice(closest.edgeIndex + 1, 0, closest.projected);
  room.confirmed = false;
  room.source = "manual_node_split";
  element.spaceError.textContent = "";
  state.roomNodeMode = null;
  state.selectedRoomNodeIndices = [];
  updateRoomNodeControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間邊線已新增節點，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("已在房間邊線新增節點；可直接拖曳紫色節點調整輪廓。");
}

function mergeSelectedRooms() {
  if (state.mergeRoomIds.length !== 2) {
    element.spaceError.textContent = "請先選取兩個相鄰房間。";
    return;
  }
  const selected = state.mergeRoomIds
    .map((roomId) => state.rooms.find((room) => room.id === roomId))
    .filter(Boolean);
  if (selected.length !== 2) return;
  const polygon = convexHull(selected.flatMap((room) => room.polygon_cm));
  const originalArea = selected.reduce((sum, room) => sum + polygonArea(room.polygon_cm), 0);
  const mergedArea = polygonArea(polygon);
  if (polygon.length < 3 || mergedArea > originalArea * 1.2) {
    element.spaceError.textContent =
      "這兩個房間不相鄰，或合併後會涵蓋過多其他區域，請重新選擇。";
    return;
  }
  const cleanLabel = (label) => label.replace(/\s*（待確認）\s*/g, "").trim();
  const merged = {
    id: `room-merged-${Date.now()}`,
    label: `${cleanLabel(selected[0].label)}＋${cleanLabel(selected[1].label)}（待確認）`,
    type: selected[0].type === selected[1].type ? selected[0].type : "default",
    confidence: Math.min(...selected.map((room) => Number(room.confidence || 0.5))),
    confirmed: false,
    source: "manual_merge",
    merged_from: selected.map((room) => room.id),
    polygon_cm: polygon,
  };
  const selectedIds = new Set(state.mergeRoomIds);
  state.rooms = [...state.rooms.filter((room) => !selectedIds.has(room.id)), merged];
  state.selectedRoomId = merged.id;
  state.roomGeometryMode = null;
  state.mergeRoomIds = [];
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已合併，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("已合併兩個房間；請修改名稱並按房間確認鍵。");
}

function splitSelectedRoom(start, end) {
  const room = state.rooms.find((item) => item.id === state.selectedRoomId);
  if (!room || Math.hypot(end.x - start.x, end.y - start.y) < 10) {
    element.spaceError.textContent = "切割線太短，請重新點兩個不同位置。";
    state.splitPoints = [];
    updateRoomGeometryControls();
    return;
  }
  const firstPolygon = clipPolygonByLine(room.polygon_cm, start, end, true);
  const secondPolygon = clipPolygonByLine(room.polygon_cm, start, end, false);
  if (
    firstPolygon.length < 3
    || secondPolygon.length < 3
    || polygonArea(firstPolygon) < 5_000
    || polygonArea(secondPolygon) < 5_000
  ) {
    element.spaceError.textContent =
      "切割線沒有完整穿過房間，或切出的空間小於 0.5 m²，請重新畫線。";
    state.splitPoints = [];
    updateRoomGeometryControls();
    renderSpaceOverlay();
    return;
  }
  const baseLabel = room.label.replace(/\s*（待確認）\s*/g, "").trim();
  const roomIndex = state.rooms.findIndex((item) => item.id === room.id);
  const splitRooms = [firstPolygon, secondPolygon].map((polygon, index) => ({
    ...room,
    id: `room-split-${Date.now()}-${index + 1}`,
    label: `${baseLabel} ${index === 0 ? "A" : "B"}（待確認）`,
    confidence: Math.min(Number(room.confidence || 0.5), 0.7),
    confirmed: false,
    source: "manual_split",
    split_from: room.id,
    polygon_cm: polygon,
  }));
  state.rooms.splice(roomIndex, 1, ...splitRooms);
  state.selectedRoomId = splitRooms[0].id;
  state.roomGeometryMode = null;
  state.splitPoints = [];
  updateRoomGeometryControls();
  renderRooms();
  renderSpaceOverlay();
  invalidateDownstreamFrom("space_confirmation", "房間已切割，後續需求、家具與 3D 需要重新確認。");
  scheduleSave("space_confirmation");
  setStatus("房間已切成兩個範圍；請逐一命名並確認。");
}

function renderSpaceOverlay() {
  if (!element.spaceImage.naturalWidth || !state.rooms.length) return;
  const visibleRooms = state.spaceMode === "rooms"
    ? (state.showAllRooms
      ? state.rooms
      : state.rooms.filter((room) => room.id === state.selectedRoomId))
    : [];
  const polygons = visibleRooms.map((room) => {
    const active = room.id === state.selectedRoomId || state.mergeRoomIds.includes(room.id);
    const dimensions = roomDimensions(room);
    const center = cmToPixel(roomCenter(room));
    const nodes = active
      ? room.polygon_cm.map((point, index) => {
        const pixel = cmToPixel(point);
        const selected = state.roomNodeMode === "merge"
          && state.selectedRoomNodeIndices.includes(index);
        return `<circle data-room-point="${index}" cx="${pixel.x}" cy="${pixel.y}" r="${selected ? 12 : 9}"
          fill="${selected ? "#fff1e9" : "#fff"}" stroke="${selected ? "#bd5c36" : "#7755a6"}"
          stroke-width="${selected ? 7 : 5}"/>`;
      }).join("")
      : "";
    return `
      <g data-room-shape="${escapeHtml(room.id)}">
        <polygon points="${roomPolygonSvg(room)}" fill="${active ? "rgba(47,111,135,.20)" : "rgba(36,107,85,.10)"}"
          stroke="${active ? "#2f6f87" : "#246b55"}" stroke-width="${active ? 5 : 3}"/>
        <text x="${center.x}" y="${center.y - 8}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="8" paint-order="stroke"
          font-size="24" font-weight="800" pointer-events="none">${escapeHtml(room.label)}</text>
        <text x="${center.x}" y="${center.y + 22}" text-anchor="middle"
          fill="#173f35" stroke="#fff" stroke-width="7" paint-order="stroke"
          font-size="18" font-weight="700" pointer-events="none">${dimensions.areaM2.toFixed(2)} m²</text>
        ${nodes}
      </g>
    `;
  }).join("");
  const structures = state.spaceMode === "structure" ? renderStructureSvg() : "";
  const splitGuide = state.roomGeometryMode === "split" && state.splitPoints[0]
    ? (() => {
      const point = cmToPixel(state.splitPoints[0]);
      return `<circle cx="${point.x}" cy="${point.y}" r="10" fill="#fff" stroke="#bd5c36" stroke-width="5"/>`;
    })()
    : "";
  element.spaceOverlay.innerHTML = `${polygons}${structures}${splitGuide}`;
  renderSchemeComparison();
}

function segmentSvg(item, color, width = 5, dash = "") {
  const start = cmToPixel(item.start);
  const end = cmToPixel(item.end);
  return `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}" stroke="${color}" stroke-width="${width}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
}

const structureCollections = {
  door: "doors",
  window: "windows",
  wall: "walls",
  beam: "beams",
  column: "columns",
};

function attachedOpeningUpdates(oldWall, newWall, openingSnapshots) {
  const oldDx = oldWall.end.x - oldWall.start.x;
  const oldDy = oldWall.end.y - oldWall.start.y;
  const oldLengthSquared = oldDx * oldDx + oldDy * oldDy || 1;
  const newDx = newWall.end.x - newWall.start.x;
  const newDy = newWall.end.y - newWall.start.y;
  const newLength = Math.hypot(newDx, newDy);
  if (newLength < 1) return null;
  const axis = { x: newDx / newLength, y: newDy / newLength };
  const updates = [];
  for (const { collection, item } of openingSnapshots) {
    const center = {
      x: (item.start.x + item.end.x) / 2,
      y: (item.start.y + item.end.y) / 2,
    };
    const t = Math.max(0, Math.min(1, (
      (center.x - oldWall.start.x) * oldDx
      + (center.y - oldWall.start.y) * oldDy
    ) / oldLengthSquared));
    const width = Math.max(
      30,
      Number(item.width_cm || Math.hypot(
        item.end.x - item.start.x,
        item.end.y - item.start.y,
      )),
    );
    const margin = 5;
    if (newLength < width + margin * 2) return null;
    const halfT = width / newLength / 2;
    const clampedT = Math.max(halfT + margin / newLength, Math.min(
      1 - halfT - margin / newLength,
      t,
    ));
    const nextCenter = {
      x: newWall.start.x + newDx * clampedT,
      y: newWall.start.y + newDy * clampedT,
    };
    updates.push({
      collection,
      id: item.id,
      start: {
        x: nextCenter.x - axis.x * width / 2,
        y: nextCenter.y - axis.y * width / 2,
      },
      end: {
        x: nextCenter.x + axis.x * width / 2,
        y: nextCenter.y + axis.y * width / 2,
      },
    });
  }
  return updates;
}

function applyAttachedOpeningUpdates(updates) {
  (updates || []).forEach((update) => {
    const opening = state.structures[update.collection].find(
      (item) => item.id === update.id,
    );
    if (!opening) return;
    opening.start = update.start;
    opening.end = update.end;
    opening.confirmed = false;
    delete opening.swing_end;
  });
}

const structureSectionMeta = {
  door: {
    label: "門",
    listTitle: "門候選清單",
    addLabel: "＋ 新增門",
    unit: "扇門",
    guidance: "新增門後會磁吸最近牆；可拖曳、調整寬度、門向與鉸鏈端，再逐扇確認。",
  },
  window: {
    label: "窗",
    listTitle: "窗候選清單",
    addLabel: "＋ 新增窗",
    unit: "扇窗",
    guidance: "新增窗後會磁吸最近牆；可拖曳並調整窗寬、窗高與窗台離地高度，再逐扇確認。左圖只有帶編號的藍線是窗候選；未帶編號的原圖細線可能是門扇符號。",
  },
  wall: {
    label: "牆",
    listTitle: "牆體清單",
    addLabel: "＋ 畫牆",
    unit: "面牆",
    guidance: "畫牆後可拖曳端點或在選取牆段後調整尺寸。牆體會作為後續門、窗、家具配置的固定結構基準。",
  },
  beam: {
    label: "樑",
    listTitle: "樑體清單",
    addLabel: "＋ 畫樑",
    unit: "道樑",
    guidance: "按住左圖拖曳樑的起點至終點，放開即完成；端點會自動對齊水平或垂直並磁吸附近結構。",
  },
  column: {
    label: "柱",
    listTitle: "柱體清單",
    addLabel: "＋ 新增柱",
    unit: "根柱",
    guidance: "點左圖放置柱；可拖曳並調整柱寬與柱深，柱高會跟隨樓高。",
  },
};

function wallBoundaryContext() {
  const floorplan = confirmedFloorplanEditor();
  return {
    width_cm: Number(floorplan.width_cm || 0),
    depth_cm: Number(floorplan.depth_cm || 0),
  };
}

function wallBoundary(item) {
  const floorplan = wallBoundaryContext();
  return wallBoundarySide(item, {
    widthCm: floorplan.width_cm,
    depthCm: floorplan.depth_cm,
  });
}

function normalizeWallDemolitionCandidates() {
  state.structures.walls.forEach((wall) => {
    wall.demolition_candidate = false;
  });
  return 0;
}



function schemeStructureMarkup(schemeId) {
  const structures = structuresForScheme(state.structures, schemeId);
  const lines = (items, color, width) => items.map((item) => {
    if (!item.start || !item.end) return "";
    const start = cmToPixel(item.start);
    const end = cmToPixel(item.end);
    const uncertain = schemeId === "B"
      && item.host_wall_relation_uncertain === true
      && state.structures.walls.some(
        (wall) => wall.id === item.host_wall_id && wall.demolition_candidate === true,
      );
    return `<line x1="${start.x}" y1="${start.y}" x2="${end.x}" y2="${end.y}"
      stroke="${uncertain ? "#ef9f19" : color}" stroke-width="${width}"
      ${uncertain ? 'stroke-dasharray="12 8"' : ""}
      vector-effect="non-scaling-stroke">
      ${uncertain ? "<title>此門窗與可拆牆的關聯不確定，方案 B 暫時保留。</title>" : ""}
    </line>`;
  }).join("");
  return [
    lines(structures.walls, "#343434", 7),
    lines(structures.doors, "#bd5c36", 5),
    lines(structures.windows, "#2f8ba1", 5),
    lines(structures.beams, "#6b4d8a", 5),
  ].join("");
}

function schemeFurnitureForRoom(schemeId, roomId) {
  const resolvedSchemeId = String(
    schemeId
      || state.designSchemes.room_selections?.[String(roomId)]
      || state.designSchemes.active_scheme_id
      || "A",
  ).toUpperCase();
  const scheme = state.designSchemes.schemes[resolvedSchemeId] || state.designSchemes.schemes.A;
  return (scheme?.furniture || []).filter((item) => String(item.roomId || item.room_id || "") === String(roomId));
}

function roomSchemeSelectionRequired() {
  // 第 6 步的動線是「先逐房選定 A/B，再進工作台微調」
  // （現行流程與保存邊界見 docs/contracts/AGENT_FRONTEND_BACKEND_CONTRACT.md）。
  // 只有真的存在可比較的方案 B 時才擋；B 整組產不出來時直接走方案 A，
  // 不製造無從通過的關卡。
  if (!state.rooms.length) return false;
  const schemeB = state.designSchemes.schemes.B;
  if (!schemeB || schemeB.stale) return false;
  return state.rooms.some((room) => roomHasComparableSchemeB(room));
}

function roomSchemeGateBlocking() {
  return roomSchemeSelectionRequired()
    && !allRoomsHaveSchemeSelections(state.designSchemes, state.rooms);
}

function promptRoomSchemeSelection() {
  if (!roomSchemeSelectionRequired() || !state.rooms.length) return;
  // 建立 A、B 的過程會兩度 showStep("white_model_3d")；那時方案還沒齊，不能彈窗。
  if (state.autoGeneratingWhiteModel) return;
  if (allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) return;
  if (element.roomSchemeDialog?.open) return;
  deactivateWhiteInteractionMode();
  openRoomSchemeSelectionDialog();
  void ensureRoomSchemeAlternative();
}

async function ensureRoomSchemeAlternative() {
  if (roomSchemeRuntimeState.alternativeInFlight) return roomSchemeRuntimeState.alternativeInFlight;
  const schemeA = state.designSchemes.schemes.A;
  const schemeB = ensureSchemeB(state.designSchemes, { reason: "step_six_room_comparison" });
  if (schemeB.stale || (schemeB.furniture || []).length || !(schemeA?.furniture || []).length) {
    if (element.roomSchemeDialog?.open) renderRoomSchemeSelectionDialog();
    return schemeB;
  }
  roomSchemeRuntimeState.alternativeInFlight = (async () => {
    try {
      const alternativeFurniture = await relayoutFurnitureForScheme(schemeA.furniture, "B", { allowPending: true });
      if (!alternativeFurniture?.length) {
        schemeB.stale = true;
        schemeB.staleReason = "無法產生不同的家具擺設。";
        return schemeB;
      }
      schemeB.furniture = alternativeFurniture;
      schemeB.stale = false;
      schemeB.staleReason = "";
      roomSchemePreviewCache.clear();
      scheduleSave("layout_2d");
      return schemeB;
    } catch (error) {
      schemeB.stale = true;
      schemeB.staleReason = `無法產生替代擺設：${errorMessage(error)}`;
      return schemeB;
    } finally {
      roomSchemeRuntimeState.alternativeInFlight = null;
      if (element.roomSchemeDialog?.open) renderRoomSchemeSelectionDialog();
    }
  })();
  return roomSchemeRuntimeState.alternativeInFlight;
}

function snapshotCopy(value) {
  return JSON.parse(JSON.stringify(value ?? null));
}

function snapshotFurniture(item) {
  const size = item.size_cm || item.dimensions || {};
  const modelLocked = Boolean(item.model_locked);
  const materialLocked = Boolean(item.material_locked);
  const priceTwd = Number(item.price_twd ?? item.unit_price_twd ?? NaN);
  return {
    instance_id: item.id || item.instance_id || item.furniture_id || null,
    furniture_id: item.furniture_id || item.catalog_furniture_id || item.id || null,
    // furniture_id 這時多半已是引擎擺位 id（room-1-bed-1），對不到型錄。GLB 檔名
    // 是第 8 步唯一還查得到單價的線索（main._price_lookup_keys），拿掉這行，走
    // downloadEngineeringDelivery() 的報價單會整份變「待報價」。
    model_url: item.model_url || null,
    room_id: item.room_id || item.roomId || null,
    normalized_type: item.normalized_type || item.type || null,
    name_zh: item.name_zh_raw || item.name_zh || item.name || item.name_en || "",
    material: item.material || item.material_zh || null,
    price_twd: Number.isFinite(priceTwd) && priceTwd > 0 ? Math.round(priceTwd) : null,
    price_source: item.price_source || item.source_url || item.catalog_source || null,
    size_cm: snapshotCopy(size),
    position_cm: snapshotCopy(item.position_cm || item.position || null),
    rotation_y_deg: Number(item.rotation_y_deg ?? item.rotationDeg ?? item.rotation_deg ?? 0),
    locks: {
      model: modelLocked,
      material: materialLocked,
      placement: Boolean(item.position_locked),
      mode: modelLocked || materialLocked ? "locked" : "flexible",
    },
  };
}

function configurationSnapshot(previous = state.designSchemes.configuration_snapshot) {
  const now = new Date().toISOString();
  const revision = Number(previous?.revision || 0) + 1;
  const sceneVersion = currentSceneVersion();
  const sceneObjects = state.sceneData?.scene_objects?.length
    ? state.sceneData.scene_objects
    : composeSelectedRoomFurniture();
  const structures = state.structures || {};
  return {
    schema_version: 2,
    snapshot_id: `${state.projectId || "project"}:${sceneVersion}:${revision}`,
    revision,
    created_at: previous?.created_at || now,
    updated_at: now,
    scene_version: sceneVersion,
    room_selections: { ...(state.designSchemes.room_selections || {}) },
    fixed_structure: {
      walls: snapshotCopy(structures.walls || []),
      doors: snapshotCopy(structures.doors || []),
      windows: snapshotCopy(structures.windows || []),
      beams: snapshotCopy(structures.beams || []),
      columns: snapshotCopy(structures.columns || []),
    },
    rooms: state.rooms.map((room) => ({
      room_id: room.id,
      room_label: room.label,
      room_type: room.room_type || room.space_type || room.type || null,
      bounds: snapshotCopy(room.bounds || room.polygon || room.points || null),
      selected_scheme_id: selectedSchemeForRoom(state.designSchemes, room.id),
      furniture_count: sceneObjects.filter(
        (item) => String(item.room_id || item.roomId || "") === String(room.id),
      ).length,
    })),
    furniture: sceneObjects.map(snapshotFurniture),
    room_surface_assignments: roomSurfaceAssignments(),
    room_views: snapshotCopy(state.proposalReview.roomViews || {}),
    selected_style_card_id: state.proposalReview.confirmedStyleCardId || null,
  };
}

function refreshConfigurationSnapshot() {
  const snapshot = configurationSnapshot();
  state.designSchemes.configuration_snapshot = snapshot;
  if (state.proposalReview.masterView) {
    state.proposalReview.masterView.configuration_snapshot_id = snapshot.snapshot_id;
    state.proposalReview.masterView.scene_version = snapshot.scene_version;
  }
  return snapshot;
}

function lockedConfigurationSnapshot() {
  const snapshot = state.designSchemes.configuration_snapshot;
  if (!snapshot?.snapshot_id) {
    throw new Error("找不到第 7 步已鎖定的配置快照，請返回方案鎖定重新確認。");
  }
  return snapshotCopy(snapshot);
}

function composeSelectedRoomFurniture() {
  const baselineFurniture = state.designSchemes.schemes.A?.furniture || [];
  const composite = [];
  const usedFurnitureIds = new Set();
  const furnitureInstanceKey = (item = {}, roomId = "") => [
    String(roomId || item.roomId || item.room_id || ""),
    String(item.id || item.furniture_id || item.catalogFurnitureId || ""),
  ].join("::");
  const roomIds = new Set(state.rooms.map((room) => String(room.id)));
  state.rooms.forEach((room) => {
    const schemeId = selectedSchemeForRoom(state.designSchemes, room.id);
    schemeFurnitureForRoom(schemeId, room.id).forEach((item) => {
      const key = furnitureInstanceKey(item, room.id);
      if (key.endsWith("::") || usedFurnitureIds.has(key)) return;
      usedFurnitureIds.add(key);
      composite.push({ ...JSON.parse(JSON.stringify(item)), roomId: item.roomId || room.id });
    });
  });
  baselineFurniture.forEach((item) => {
    const roomId = String(item.roomId || item.room_id || "");
    const key = furnitureInstanceKey(item, roomId);
    if (roomIds.has(roomId) || key.endsWith("::") || usedFurnitureIds.has(key)) return;
    usedFurnitureIds.add(key);
    composite.push(JSON.parse(JSON.stringify(item)));
  });
  return composite;
}

// 未選定方案前不能微調：completeRoomSchemeSelection() 會用逐房合成的家具整包
// 覆蓋 state.furniture2d，先做的拖曳、替換與新增都會被丟掉。
function setRoomSchemeWorkbenchLocked(locked) {
  const reason = locked ? "請先完成逐房 A/B 方案選擇，才能微調家具。" : "";
  const editButton = $("[data-white-interaction=\"edit\"]");
  if (editButton) {
    editButton.disabled = locked;
    editButton.title = reason;
  }
  const catalogButton = $("#open-furniture-catalog");
  if (catalogButton) {
    catalogButton.disabled = locked;
    catalogButton.title = reason;
  }
  syncConfigurationConfirmButton();
}

function syncConfigurationConfirmButton() {
  const confirmButton = $("#confirm-white-model");
  if (!confirmButton) return;
  const schemeGated = roomSchemeGateBlocking();
  const blocking = schemeGated ? [] : configurationBlockingFurniture();
  confirmButton.disabled = schemeGated || blocking.length > 0;
  confirmButton.title = schemeGated
    ? "請先完成逐房 A/B 方案選擇，才能確認家具配置。"
    : (blocking.length ? `尚有 ${blocking.length} 件家具位置不合法，請先修正。` : "");
}

function renderRoomSchemeGate() {
  if (!element.roomSchemeGateStatus || !element.openRoomSchemeSelection) return;
  if (!roomSchemeSelectionRequired()) {
    element.roomSchemeGateStatus.textContent = "目前只有方案 A；可直接進行家具微調。";
    element.openRoomSchemeSelection.hidden = true;
    if (element.roomSchemeGate) {
      element.roomSchemeGate.hidden = true;
      element.roomSchemeGate.setAttribute("aria-hidden", "true");
    }
    setRoomSchemeWorkbenchLocked(false);
    return;
  }
  if (element.roomSchemeGate) {
    element.roomSchemeGate.hidden = false;
    element.roomSchemeGate.setAttribute("aria-hidden", "false");
  }
  const autoSelected = applyUnavailableRoomSchemeDefaults();
  const selectedCount = state.rooms.filter((room) => (
    ["A", "B"].includes(state.designSchemes.room_selections?.[String(room.id)])
  )).length;
  const ready = allRoomsHaveSchemeSelections(state.designSchemes, state.rooms);
  element.roomSchemeGateStatus.textContent = ready
    ? `已完成 ${selectedCount}/${state.rooms.length} 間房的方案選擇；${autoSelected ? "沒有完整方案 B 的房間已自動採用方案 A。" : ""}現在可以微調。`
    : `已選 ${selectedCount}/${state.rooms.length} 間。請先完成所有房間的 A/B 選擇，才可微調。`;
  element.openRoomSchemeSelection.hidden = false;
  element.openRoomSchemeSelection.textContent = ready ? "檢視逐房方案選擇" : "逐房比較並選擇方案";
  element.roomSchemeGate?.classList.toggle("is-scheme-pending", !ready);
  setRoomSchemeWorkbenchLocked(!ready);
}

function roomHasComparableSchemeB(room) {
  const schemeB = state.designSchemes.schemes.B;
  if (!room || !schemeB || schemeB.stale || !schemeFurnitureForRoom("B", room.id).length) {
    return false;
  }
  // B 與 A 在此房擺法完全相同 → 視為「沒有可比較的方案 B」。有些房幾何上只有一種
  // 合理擺法(客廳沙發+電視需兩面相對實牆+中間淨空走廊,門/窗/陽台開口多時只剩一組
  // 相對牆),variant B 找不到不同的合法擺法而回退成 A;此時不該顯示兩張一模一樣的卡。
  const fingerprint = (schemeId) => schemeFurnitureForRoom(schemeId, room.id)
    .map((item) => `${item.id}|${Math.round(item.xCm)}|${Math.round(item.yCm)}|${Math.round(item.rotationDeg || 0)}`)
    .sort()
    .join(";");
  return fingerprint("A") !== fingerprint("B");
}

function roomSchemePreviewKey(schemeId, roomId) {
  // The image cache must follow the same room-local furniture list as the
  // 2D plan.  A scheme may be regenerated while the dialog is open.
  const furnitureFingerprint = schemeFurnitureForRoom(schemeId, roomId)
    .map((item) => [
      item.id || item.furniture_id || item.catalogFurnitureId || "",
      item.xCm || 0,
      item.yCm || 0,
      item.rotationDeg || 0,
      item.model_url || "",
    ].join("|"))
    .sort()
    .join(";");
  return `${schemeId}:${roomId}:${furnitureFingerprint}`;
}

function roomSchemeFurnitureLabel(item = {}) {
  return replacementFurnitureName({
    ...item,
    name_zh_raw: item.label || item.name_zh_raw,
    normalized_type: item.type || item.normalized_type,
  });
}

function roomSchemePlanMarkup(room, furniture = []) {
  const polygon = room?.polygon_cm || [];
  if (polygon.length < 3) {
    return '<span class="rp-render-placeholder">沒有可用的房間平面資料</span>';
  }
  const center = planCenterCm();
  const points = polygon.map((point) => ({ x: Number(point.x || 0), y: Number(point.y || 0) }));
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const padding = 38;
  const minX = Math.min(...xs) - padding;
  const maxX = Math.max(...xs) + padding;
  const minY = Math.min(...ys) - padding;
  const maxY = Math.max(...ys) + padding;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const project = (point) => ({
    x: ((point.x - minX) / width) * 440,
    y: 300 - ((point.y - minY) / height) * 300,
  });
  const roomPath = points.map((point, index) => {
    const projected = project(point);
    return `${index ? 'L' : 'M'} ${projected.x.toFixed(1)} ${projected.y.toFixed(1)}`;
  }).join(' ') + ' Z';
  const furnitureMarkup = furniture.slice(0, 12).map((item) => {
    const location = project({ x: center.x + Number(item.xCm || 0), y: center.y + Number(item.yCm || 0) });
    const itemWidth = Math.max(22, (Number(item.widthCm || 60) / width) * 440);
    const itemHeight = Math.max(18, (Number(item.depthCm || 60) / height) * 300);
    const label = roomSchemeFurnitureLabel(item);
    return `<g class="rp-room-scheme-furniture" transform="translate(${location.x.toFixed(1)} ${location.y.toFixed(1)}) rotate(${-Number(item.rotationDeg || 0)})">
      <rect x="${(-itemWidth / 2).toFixed(1)}" y="${(-itemHeight / 2).toFixed(1)}" width="${itemWidth.toFixed(1)}" height="${itemHeight.toFixed(1)}" rx="3" />
      ${itemWidth > 62 && itemHeight > 30 ? `<text text-anchor="middle" dominant-baseline="middle">${escapeHtml(label.slice(0, 8))}</text>` : ''}
    </g>`;
  }).join('');
  return `<svg class="rp-room-scheme-plan" viewBox="0 0 440 300" role="img" aria-label="${escapeHtml(room.label || '房間')}的家具平面配置">
    <path class="rp-room-scheme-outline" d="${roomPath}" />
    ${furnitureMarkup || '<text class="rp-room-scheme-empty" x="200" y="130" text-anchor="middle">尚未配置家具</text>'}
  </svg>`;
}

function roomSchemeFurnitureLegend(furniture = []) {
  if (!furniture.length) return '<p class="rp-room-scheme-legend-empty">尚未配置家具</p>';
  return `<ul class="rp-room-scheme-legend">${furniture.slice(0, 6).map((item) => (
    `<li>${escapeHtml(roomSchemeFurnitureLabel(item))}</li>`
  )).join('')}</ul>`;
}

function hasStepFourConfirmedOpening(segment = {}) {
  const opening = segment.confirmed_wall_opening
    || segment.wall_opening_segment
    || segment.closed_leaf_segment;
  const isScenePlanPoint = (point = {}) => (
    Number.isFinite(Number(point.x))
    && Number.isFinite(Number(point.z ?? point.y))
  );
  return segment.step4_confirmed === true
    && isScenePlanPoint(opening?.start)
    && isScenePlanPoint(opening?.end);
}

function roomSchemePreviewFloorplan(baseScene = {}) {
  // The active scene is produced from the Step 4 confirmation.  A/B only
  // changes furniture placement, never the room envelope or its apertures.
  const activeFloorplan = state.sceneData?.floorplan;
  if (Array.isArray(activeFloorplan?.wall_segments) && activeFloorplan.wall_segments.length) {
    return activeFloorplan;
  }
  return baseScene.floorplan || {};
}

function buildRoomSchemePreviewScene(baseScene, room, furniture = []) {
  if (!room || !(baseScene?.floorplan || state.sceneData?.floorplan)) return null;
  const bounds = replacementRoomBounds(room);
  if (!bounds) return null;
  const offset = { x: bounds.centerX, z: bounds.centerZ };
  const scene = JSON.parse(JSON.stringify(baseScene));
  const confirmedFloorplan = roomSchemePreviewFloorplan(baseScene);
  const floorplan = scene.floorplan || {};
  const structureIssues = [];
  const doorDiagnostics = (() => {
    try {
      return JSON.parse($("#white-model-viewer")?.dataset.roompilotDoorDiagnostics || "{}");
    } catch {
      return {};
    }
  })();
  const expectedDoors = Number(doorDiagnostics.expected) || 0;
  const matchedDoors = (doorDiagnostics.comparisons || [])
    .filter((item) => item.status === "matched").length;
  if (expectedDoors && matchedDoors < expectedDoors) {
        structureIssues.push("部分門位仍待核對，請回到第 4 步確認。");
  }
  const confirmedDoorSegments = (confirmedFloorplan.door_segments || []).filter(
    hasStepFourConfirmedOpening,
  );
  const omittedDoors = (confirmedFloorplan.door_segments || []).filter((segment) => (
    segmentOverlapsBounds(segment, bounds) && !hasStepFourConfirmedOpening(segment)
  ));
  const confirmedWindowSegments = (confirmedFloorplan.window_segments || []).filter((segment) => (
    segment.step4_confirmed === true && segment.host_wall_confirmed === true
  ));
  const omittedWindows = (confirmedFloorplan.window_segments || []).filter((segment) => (
    segmentOverlapsBounds(segment, bounds)
    && !(segment.step4_confirmed === true && segment.host_wall_confirmed === true)
  ));
  if (omittedDoors.length) {
    structureIssues.push(`已略過 ${omittedDoors.length} 扇尚未在第 4 步確認洞口的門`);
  }
  if (omittedWindows.length) {
    structureIssues.push(`已略過 ${omittedWindows.length} 扇尚未在第 4 步確認牆面的窗`);
  }
  [
    'wall_segments',
    'beam_segments',
    'column_segments',
  ].forEach((key) => {
    const segments = confirmedFloorplan[key];
    if (!Array.isArray(segments)) return;
    floorplan[key] = segments
      .filter((segment) => segmentOverlapsBounds(segment, bounds))
      .map((segment) => shiftSceneSegment(segment, offset));
  });
  floorplan.door_segments = confirmedDoorSegments
    .filter((segment) => segmentOverlapsBounds(segment, bounds))
    .map((segment) => shiftSceneSegment(segment, offset));
  // Step 6 derives the physical aperture from the confirmed door segment.
  // Keeping a second inferred opening here can create the historic double-hole bug.
  floorplan.door_openings = [];
  floorplan.window_segments = confirmedWindowSegments
    .filter((segment) => segmentOverlapsBounds(segment, bounds))
    .map((segment) => shiftSceneSegment(segment, offset));
  if (Array.isArray(floorplan.wall_polys)) {
    floorplan.wall_polys = (confirmedFloorplan.wall_polys || [])
      .filter((region) => (region.exterior || region.polygon_cm || []).some((point) => {
        const coordinates = scenePointCoordinates(point);
        return (
          coordinates.x >= bounds.minX - 32
          && coordinates.x <= bounds.maxX + 32
          && coordinates.z >= bounds.minZ - 32
          && coordinates.z <= bounds.maxZ + 32
        );
      }))
      .map((region) => shiftFloorplanRegion(region, offset));
  }
  if (Array.isArray(floorplan.columns)) {
    floorplan.columns = (confirmedFloorplan.columns || [])
      .filter((column) => segmentOverlapsBounds({ start: column.center, end: column.center }, bounds))
      .map((column) => ({ ...column, center: shiftScenePoint(column.center, offset) }));
  }
  floorplan.room_regions = (confirmedFloorplan.room_regions || [])
    .filter((region) => String(region.room_id || region.id || '') === String(room.id))
    .map((region) => shiftFloorplanRegion(region, offset));
  if (Array.isArray(confirmedFloorplan.rooms)) {
    floorplan.rooms = confirmedFloorplan.rooms
      .filter((region) => String(region.room_id || region.id || '') === String(room.id))
      .map((region) => shiftFloorplanRegion(region, offset));
  }
  floorplan.width_cm = Math.max(240, (bounds.maxX - bounds.minX) + 120);
  floorplan.depth_cm = Math.max(240, (bounds.maxZ - bounds.minZ) + 120);
  scene.floorplan = floorplan;
  scene.room_surface_assignments = (scene.room_surface_assignments || [])
    .filter((assignment) => String(assignment.room_id || '') === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  scene.surface_overrides = (scene.surface_overrides || [])
    .filter((assignment) => String(assignment.room_id || '') === String(room.id))
    .map((assignment) => shiftRoomSurfaceAssignment(assignment, offset));
  const sourceObjects = scene.scene_objects || [];
  scene.scene_objects = furniture.map((item) => {
    const existing = sourceObjects.find((sceneObject) => sceneObjectMatchesLayoutFurniture(sceneObject, item)) || {};
    const fallbackSize = {
      width: Number(item.widthCm || item.size_cm?.width || 60),
      depth: Number(item.depthCm || item.size_cm?.depth || 60),
      height: Number(item.heightCm || item.size_cm?.height || 80),
    };
    return {
      ...existing,
      furniture_id: item.id,
      catalog_furniture_id: item.catalogFurnitureId || item.catalog_furniture_id || existing.catalog_furniture_id,
      name_zh_raw: item.label || existing.name_zh_raw,
      normalized_type: item.type || existing.normalized_type,
      model_url: item.model_url || existing.model_url,
      size_cm: {
        width: Number(existing.size_cm?.width || fallbackSize.width),
        depth: Number(existing.size_cm?.depth || fallbackSize.depth),
        height: Number(existing.size_cm?.height || fallbackSize.height),
      },
      position_cm: shiftScenePoint({ x: Number(item.xCm || 0), z: Number(item.yCm || 0) }, offset),
      rotation_y_deg: Number(item.rotationDeg || 0),
      placement_room_id: room.id,
      position_locked: true,
      placement_failed: item.placementFailed === true,
    };
  });
  if (!floorplan.wall_segments?.length) {
    structureIssues.push("找不到這個房間已確認的牆面");
  }
  return { scene, bounds, structureIssues };
}

function applyUnavailableRoomSchemeDefaults() {
  if (!roomSchemeSelectionRequired()) return false;
  let changed = false;
  state.rooms.forEach((room) => {
    if (roomHasComparableSchemeB(room)) return;
    if (state.designSchemes.room_selections?.[String(room.id)] === "A") return;
    changed = selectSchemeForRoom(state.designSchemes, room.id, "A") || changed;
  });
  return changed;
}

function openRoomSchemeSelectionDialog() {
  if (!element.roomSchemeDialog) return;
  if (applyUnavailableRoomSchemeDefaults()) scheduleSave("white_model_3d");
  // A/B thumbnails are rendered by an off-screen viewer.  Rebuild them whenever
  // the comparison opens so an earlier scene can never be shown beside a newly
  // loaded full preview.
  roomSchemePreviewCache.clear();
  state.selectedRoomSchemeId = state.selectedRoomSchemeId || state.rooms.find((room) => (
    !state.designSchemes.room_selections?.[String(room.id)]
  ))?.id || state.rooms[0]?.id || null;
  renderRoomSchemeSelectionDialog();
  // 自動彈出與使用者手動點開可能同時發生；對已開啟的 dialog 呼叫 showModal 會丟例外。
  if (!element.roomSchemeDialog.open) {
    if (typeof element.roomSchemeDialog.showModal === "function") element.roomSchemeDialog.showModal();
    else element.roomSchemeDialog.setAttribute("open", "");
  }
  void ensureRoomScheme3dPreviews();
}

function closeRoomSchemeSelectionDialog() {
  if (!element.roomSchemeDialog) return;
  if (typeof element.roomSchemeDialog.close === "function") element.roomSchemeDialog.close();
  else element.roomSchemeDialog.removeAttribute("open");
}



async function openRoomScheme3dPreview(schemeId) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId));
  if (!room) {
    setStatus("找不到要預覽的房間。", "warning");
    return;
  }
  const resolvedSchemeId = String(
    schemeId
      || state.designSchemes.room_selections?.[String(room.id)]
      || state.designSchemes.active_scheme_id
      || "A",
  ).toUpperCase();
  const scheme = state.designSchemes.schemes[resolvedSchemeId] || state.designSchemes.schemes.A;
  const baseScene = scheme?.sceneData || state.designSchemes.schemes.A?.sceneData || state.sceneData;
  const previewScene = buildRoomSchemePreviewScene(
    baseScene,
    room,
    schemeFurnitureForRoom(resolvedSchemeId, room.id),
  );
  if (!room || !previewScene) {
    setStatus("無法建立此房間的 3D 預覽。", "warning");
    return;
  }
  element.roomScheme3dPreviewTitle.textContent = `${room.label || "房間"}・方案 ${resolvedSchemeId}`;
  roomSchemeRuntimeState.previewSchemeId = resolvedSchemeId;
  const previewRoomIndex = state.rooms.findIndex((item) => String(item.id) === String(room.id));
  const previewPosition = $("#room-scheme-preview-position");
  if (previewPosition) {
    previewPosition.textContent = state.rooms.length > 1
      ? `第 ${previewRoomIndex + 1} / ${state.rooms.length} 房・${room.label || "房間"}`
      : `${room.label || "房間"}`;
  }
  const onlyOneRoom = state.rooms.length <= 1;
  const previewPrev = $("#room-scheme-preview-prev");
  const previewNext = $("#room-scheme-preview-next");
  if (previewPrev) previewPrev.disabled = onlyOneRoom;
  if (previewNext) previewNext.disabled = onlyOneRoom;
  element.roomSchemeStructureFix.hidden = previewScene.structureIssues.length === 0;
  setTaskDialogOpen(element.roomScheme3dPreviewDialog, true);
  try {
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await prepareRoomSchemePreviewViewer(roomSchemePreviewViewer, previewScene.scene);
    element.roomScheme3dPreviewStatus.textContent = previewScene.structureIssues.length
      ? `鳥瞰預覽已略過未確認結構：${previewScene.structureIssues.join("；")}。請回第 4 步確認後再看。`
      : "預設顯示房間鳥瞰；可拖曳旋轉、滾輪縮放，查看牆、地板、門窗與家具位置。";
  } catch (error) {
    element.roomScheme3dPreviewStatus.textContent = `3D 預覽載入失敗：${errorMessage(error)}`;
  }
}

// 逐房翻頁：在放大的可旋轉 3D 預覽裡直接切上一房/下一房（循環），沿用目前預覽的方案，
// 讓使用者不必關掉再重開就能逐一確認每個房間的門窗與家具。
function navigateRoomScheme3dPreview(delta) {
  if (!state.rooms.length) return;
  const index = state.rooms.findIndex(
    (item) => String(item.id) === String(state.selectedRoomSchemeId),
  );
  const base = index < 0 ? 0 : index;
  const next = state.rooms[(base + delta + state.rooms.length) % state.rooms.length];
  if (!next) return;
  state.selectedRoomSchemeId = next.id;
  void openRoomScheme3dPreview(roomSchemeRuntimeState.previewSchemeId);
}

async function waitForRoomSchemePreviewFrames(frameCount = 3) {
  for (let frame = 0; frame < frameCount; frame += 1) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
}

async function prepareRoomSchemePreviewViewer(viewer, scene) {
  await viewer.loadScene(scene);
  // Number markers are optional in the editor, but never belong in an A/B
  // comparison: the plan and the expanded preview must show the same furniture.
  viewer.setFurnitureNumberMarkersVisible(false);
  viewer.setCameraPreset("overview");
  await waitForRoomSchemePreviewFrames();
  // GLB loading may finish after the first render. Apply this once more after
  // the viewer settles so late-created markers cannot leak into thumbnails.
  viewer.setFurnitureNumberMarkersVisible(false);
  await waitForRoomSchemePreviewFrames(2);
}

function setTaskDialogOpen(dialog, isOpen) {
  if (!dialog) return;
  if (isOpen) {
    // 對已開啟的 <dialog> 再呼叫 showModal() 會丟 InvalidStateError（逐房翻頁會在
    // 對話框已開時重呼 openRoomScheme3dPreview）；已開就跳過，讓後續只重載場景。
    if (dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  } else if (typeof dialog.close === "function") {
    dialog.close();
  } else {
    dialog.removeAttribute("open");
  }
}

function selectedStepSixRoom() {
  return state.rooms.find((room) => String(room.id) === String(state.selectedRoomId))
    || state.rooms[0]
    || null;
}

function stepSixRoomSurfaceConfirmed(room) {
  return state.roomFinishDrafts?.[String(room?.id)]?.stepSixSurfaceConfirmed === true;
}

function confirmedStepSixSurfaceCount() {
  return state.rooms.filter(stepSixRoomSurfaceConfirmed).length;
}

function allStepSixRoomSurfacesConfirmed() {
  return state.rooms.length > 0 && confirmedStepSixSurfaceCount() === state.rooms.length;
}

function stepSixSurfacesFinalLocked() {
  return state.workflow?.completed.includes("realistic_3d") === true;
}

function roomFinishDraftFor(room) {
  const shared = state.questionnaireFinishes || {};
  const roomDraft = state.roomFinishDrafts?.[String(room?.id)] || {};
  return {
    ...shared,
    ...roomDraft,
    wallMaterial: roomDraft.wallMaterial || shared.wallMaterial || "",
    wallColor: roomDraft.wallColor || shared.wallColor || "",
    floorMaterial: roomDraft.floorMaterial || shared.floorMaterial || "",
    floorColor: roomDraft.floorColor || shared.floorColor || "",
    ceilingStyle: roomDraft.ceilingStyle || shared.ceilingStyle || "",
    lightStyle: roomDraft.lightStyle || shared.lightStyle || "",
  };
}

function roomQuestionnaireSummary(room) {
  if (!room) return "尚未選取房間。";
  const draft = roomFinishDraftFor(room);
  const materialLabel = (kind, id) => {
    const styleOption = Object.entries(STYLE_MATERIAL_OPTIONS).flatMap(([styleId, options]) =>
      materialOptionsForStyle(styleId, kind, options[kind]),
    ).find((option) => option.id === id);
    if (styleOption?.label) return styleOption.label;
    const catalogSurface = (state.surfaceCatalog?.surfaces || state.sceneData?.surface_catalog?.surfaces || [])
      .find((surface) => String(surface.surface_id) === String(id));
    if (catalogSurface) return userFacingMaterialLabel(catalogSurface);
    const resolved = resolveSurfaceOption(state.sceneData?.surface_catalog, kind, id);
    return resolved?.label || resolved?.name_zh || (kind === "wall" ? "自訂牆面材質" : "自訂地面材質");
  };
  const entries = [
    draft.wallMaterial ? "牆面：" + materialLabel("wall", draft.wallMaterial) : "",
    draft.floorMaterial ? "地面：" + materialLabel("floor", draft.floorMaterial) : "",
  ].filter(Boolean);
  return entries.length
    ? "問卷帶入：" + entries.join("、")
    : "本房尚未指定材質，先依全屋風格提供建議。";
}

function populateStepSixRoomSelectors(roomId = state.selectedRoomId) {
  const selectedId = String(roomId || state.rooms[0]?.id || "");
  state.selectedWalkRoomId = selectedId;
  renderWhiteWalkRoomSelector();
  if (element.whiteWalkRoom) element.whiteWalkRoom.value = selectedId;
  if (element.lightingRoomSelector) {
    element.lightingRoomSelector.innerHTML = state.rooms.map((room) =>
      `<option value="${escapeHtml(String(room.id))}">${escapeHtml(room.label)}</option>`,
    ).join("");
    element.lightingRoomSelector.value = selectedId;
  }
  const room = state.rooms.find((item) => String(item.id) === selectedId) || selectedStepSixRoom();
  if (element.surfaceRoomQuestionnaire) element.surfaceRoomQuestionnaire.textContent = roomQuestionnaireSummary(room);
  if (element.lightingRoomQuestionnaire) element.lightingRoomQuestionnaire.textContent = roomQuestionnaireSummary(room);
}

function setStepSixSurfaceStatus(message) {
  if (element.surfacePreviewStatus) element.surfacePreviewStatus.textContent = message;
  if (element.whiteStatus) element.whiteStatus.textContent = message;
}

function stepSixSurfaceUnlockButtons() {
  return [element.unlockRoomSurfaces, element.unlockRoomSurfacesSticky].filter(Boolean);
}

function renderStepSixSurfaceProgress() {
  const room = selectedStepSixRoom();
  const confirmed = stepSixRoomSurfaceConfirmed(room);
  const confirmedCount = confirmedStepSixSurfaceCount();
  const entry = $("#white-model-surface-entry");
  if (element.surfaceRoomTitle) {
    element.surfaceRoomTitle.textContent = room ? `${room.label || "此房間"}的牆面與地面` : "牆面與地面";
  }
  if (element.surfaceRoomProgress) {
    element.surfaceRoomProgress.textContent = `已確認 ${confirmedCount} / ${state.rooms.length} 間`;
  }
  if (element.surfaceRoomLockState) {
    element.surfaceRoomLockState.textContent = confirmed ? "已鎖定" : "草稿";
    element.surfaceRoomLockState.classList.toggle("is-locked", confirmed);
  }
  entry?.classList.toggle("is-room-locked", confirmed);
  entry?.querySelectorAll("[data-step-six-surface-panel] button, [data-step-six-surface-panel] input, [data-step-six-surface-panel] select")
    .forEach((control) => { control.disabled = confirmed; });
  if (element.confirmRoomSurfaces) element.confirmRoomSurfaces.hidden = confirmed;
  stepSixSurfaceUnlockButtons().forEach((button) => {
    button.hidden = !confirmed || stepSixSurfacesFinalLocked();
  });
  const finishButton = $("#save-realistic-scene");
  if (finishButton) {
    const allConfirmed = allStepSixRoomSurfacesConfirmed();
    finishButton.hidden = !allConfirmed;
    finishButton.disabled = !allConfirmed;
    finishButton.textContent = "確認全部材質，前往第 7 步";
  }
}

function setStepSixSurfaceKind(kind = "wall") {
  state.stepSixSurfaceKind = kind === "floor" ? "floor" : "wall";
  $$('[data-step-six-surface-kind]').forEach((button) => {
    const selected = button.dataset.stepSixSurfaceKind === state.stepSixSurfaceKind;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  $$('[data-step-six-surface-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.stepSixSurfacePanel !== state.stepSixSurfaceKind;
  });
  renderStepSixSurfaceProgress();
}

function focusStepSixRoom(roomId) {
  const room = state.rooms.find((item) => String(item.id) === String(roomId));
  if (!room) return;
  state.selectedRoomId = room.id;
  state.selectedWalkRoomId = room.id;
  const scope = $("#surface-scope");
  if (scope) scope.value = "room";
  populateStepSixRoomSelectors(room.id);
  renderStyleControls();
  if (state.sceneData) {
    void previewStepSixRoomSurfaces({ markDirty: false, preserveCamera: true });
    whiteViewer.setViewMode("orbit");
    whiteViewer.setCameraState(roomCameraSuggestion(room));
  }
  setStepSixSurfaceStatus(
    confirmedStepSixSurfaceCount() === state.rooms.length
      ? "所有房間材質皆已確認，可前往第 7 步。"
      : `正在預覽「${room.label || "此空間"}」；草稿只影響這個空間。`,
  );
}

function renderRoomSchemeSelectionDialog() {
  applyUnavailableRoomSchemeDefaults();
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId)) || state.rooms[0];
  if (!room || !element.roomSchemeList) return;
  const selected = selectedSchemeForRoom(state.designSchemes, room.id);
  const selectedRooms = state.rooms.filter((item) => state.designSchemes.room_selections?.[String(item.id)]).length;
  const roomPosition = Math.max(1, state.rooms.findIndex((item) => String(item.id) === String(room.id)) + 1);
  const dialogTitle = $("#room-scheme-dialog-title");
  if (dialogTitle) dialogTitle.textContent = `確認「${room.label || "此房間"}」的配置方案`;
  if (element.roomSchemeProgress) {
    element.roomSchemeProgress.textContent = `進度 ${selectedRooms}/${state.rooms.length} 間 · 目前第 ${roomPosition} 間`;
  }
  element.roomSchemeList.innerHTML = state.rooms.map((item) => {
    const selectedScheme = state.designSchemes.room_selections?.[String(item.id)];
    const isAutoSelected = selectedScheme === "A" && !roomHasComparableSchemeB(item);
    return `<button type="button" data-room-scheme-room="${escapeHtml(item.id)}"
      class="${String(item.id) === String(room.id) ? "is-active" : ""}">
      <strong>${escapeHtml(item.label || "未命名空間")}</strong>
      <small>${isAutoSelected ? "方案 A（此房無不同擺法可比較）" : (selectedScheme ? `已選方案 ${selectedScheme}` : "尚未選擇")}</small>
    </button>`;
  }).join("");
  const hasComparableB = roomHasComparableSchemeB(room);
  element.roomSchemeStatus.textContent = hasComparableB
    ? `請比較兩個方案的家具位置與 3D 房間畫面，再選擇較符合需求的一個。`
    : `此房沒有與方案 A 不同的擺法可比較（此房型幾何上僅一種合理配置，或方案 B 尚未就緒），系統已先採用方案 A；後續仍可挑選、替換與鎖定家具。`;
  element.roomSchemeChoiceGrid.innerHTML = ["A", ...(hasComparableB ? ["B"] : [])].map((schemeId) => {
    const scheme = state.designSchemes.schemes[schemeId];
    const furniture = schemeFurnitureForRoom(schemeId, room.id);
    const unavailable = !scheme || scheme.stale;
    const preview = roomSchemePreviewCache.get(roomSchemePreviewKey(schemeId, room.id));
    return `<article class="rp-scheme-choice-card ${selected === schemeId ? "is-selected" : ""}">
      <header><strong>方案 ${schemeId}</strong><span>${unavailable ? "需要重新配置" : `${furniture.length} 件家具`}</span></header>
      <div class="rp-scheme-preview-grid">
        <section class="rp-scheme-preview">
          <h4>2D 家具配置</h4>
          ${roomSchemePlanMarkup(room, furniture)}
          ${roomSchemeFurnitureLegend(furniture)}
        </section>
        <button type="button" class="rp-scheme-preview rp-scheme-preview--interactive" data-room-scheme-preview-3d="${schemeId}" aria-label="查看方案 ${schemeId} 的可旋轉 3D 預覽">
          <h4>3D 房間預覽 <span>點擊旋轉查看</span></h4>
          ${preview
            ? `<img src="${escapeHtml(preview)}" alt="方案 ${schemeId} 的 ${escapeHtml(room.label || "房間")} 3D 預覽" />`
            : `<span class="rp-render-placeholder">正在建立此房間的 3D 預覽…</span>`}
        </button>
      </div>
      <p class="rp-task-dialog-note">${unavailable ? (escapeHtml(scheme?.staleReason || "方案尚未可用") ) : (selected === schemeId ? "目前已選用此方案" : "選擇後將保留此方案的家具位置")}</p>
      <button type="button" class="${selected === schemeId ? "secondary-action" : "primary-action"}" data-room-scheme-choice="${schemeId}" ${unavailable ? "disabled" : ""}>${selected === schemeId ? "已選此方案" : `選擇方案 ${schemeId}`}</button>
    </article>`;
  }).join("");
  const missing = state.rooms.filter((item) => !state.designSchemes.room_selections?.[String(item.id)]);
  const ready = allRoomsHaveSchemeSelections(state.designSchemes, state.rooms);
  element.roomSchemeComplete.disabled = !ready;
  element.roomSchemeWarning.hidden = ready;
  element.roomSchemeWarning.textContent = ready
    ? ""
    : `尚有 ${missing.map((item) => item.label || "未命名空間").join("、")} 未選擇方案；家具微調仍會保持鎖定。`;
}

// A/B 是同一批家具的不同排法（relayoutFurnitureForScheme）。重載後非作用中方案沒有
// 自身 3D 場景（sceneData 不進存檔、又受 2MB 上限限制），就用作用中方案的全屋場景
// （shell + 已解析 GLB）依 furniture_id 把家具搬到該方案的座標重建預覽——不落地存檔、
// 不重跑生成、不動前景。該方案沒有或擺放失敗的家具不出現。
function schemeFurnitureSceneFromShell(baseScene, schemeFurniture) {
  if (!baseScene?.scene_objects?.length) return null;
  const byId = new Map(
    (schemeFurniture || [])
      .filter((item) => item && !item.placementFailed)
      .map((item) => [String(item.id || item.furniture_id), item]),
  );
  const sceneObjects = baseScene.scene_objects
    .map((obj) => {
      const item = byId.get(String(obj.furniture_id || obj.id));
      if (!item) return null;
      return {
        ...obj,
        position_cm: {
          ...(obj.position_cm || {}),
          x: Number(item.xCm || 0),
          z: Number(item.yCm || 0),
        },
        rotation_y_deg: Number(item.rotationDeg || 0),
        placement_room_id: item.roomId || obj.placement_room_id,
      };
    })
    .filter(Boolean);
  if (!sceneObjects.length) return null;
  return { ...baseScene, scene_objects: sceneObjects };
}

async function ensureRoomScheme3dPreviews() {
  if (roomSchemeRuntimeState.previewInFlight || !element.roomSchemeDialog?.open) return roomSchemeRuntimeState.previewInFlight;
  // 缺 scheme 自身 sceneData 時：作用中方案用已還原的全屋 state.sceneData；非作用中
  // 方案用「全屋 shell + 該方案家具座標」重建——都是從全房 3D 擷取，不重複建立。
  const schemeSceneFor = (schemeId) => {
    const own = state.designSchemes.schemes[schemeId]?.sceneData;
    if (own?.scene_objects) return own;
    if (schemeId === activeSchemeId()) return state.sceneData;
    return schemeFurnitureSceneFromShell(
      state.sceneData,
      state.designSchemes.schemes[schemeId]?.furniture,
    );
  };
  // 每個有場景的方案，列出還沒快取的房間。
  const jobs = ["A", "B"]
    .map((schemeId) => ({
      schemeId,
      scene: schemeSceneFor(schemeId),
      rooms: state.rooms.filter(
        (room) => !roomSchemePreviewCache.has(roomSchemePreviewKey(schemeId, room.id)),
      ),
    }))
    .filter((job) => job.scene?.scene_objects && job.rooms.length);
  if (!jobs.length) return null;
  // 背景建立 A/B 逐房預覽：離屏縮圖 viewer 的序列佇列，前景 whiteViewer 完全不動。
  // 每個方案的全屋場景「只載入一次」，一次拍完該方案所有房間再卸載——換房直接讀快取、
  // 不再每換房重載整棟（省算力）；峰值 GPU 仍只有一棟場景（拍完即卸載）。
  roomSchemeRuntimeState.previewInFlight = (async () => {
    try {
      for (const job of jobs) {
        glbThumbnailQueue.sequence = glbThumbnailQueue.sequence
          .catch(() => null)
          .then(async () => {
            try {
              await glbThumbnailViewer.loadScene(job.scene);
              for (const room of job.rooms) {
                const walkPayload = roomWalkPayload(room);
                const entered = walkPayload ? glbThumbnailViewer.setWalkRoom(walkPayload) : false;
                if (!entered) {
                  glbThumbnailViewer.setViewMode("orbit");
                  glbThumbnailViewer.setCameraPreset("corner");
                }
                await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                roomSchemePreviewCache.set(
                  roomSchemePreviewKey(job.schemeId, room.id),
                  glbThumbnailViewer.capturePng(),
                );
              }
            } finally {
              // 無論成功或中途 throw 都卸載：離屏 context 不留整棟 GPU 記憶體，避免 context loss。
              glbThumbnailViewer.unloadScene();
            }
          });
        await glbThumbnailQueue.sequence;
      }
    } catch (error) {
      setStatus(`無法建立候選 3D 預覽：${errorMessage(error)}`, "warning");
    } finally {
      roomSchemeRuntimeState.previewInFlight = null;
      if (element.roomSchemeDialog?.open) {
        renderRoomSchemeSelectionDialog();
        // 拍攝期間若有新方案/房間才就緒（例：方案 B 稍後生成並清了快取），再補一輪；
        // 全部已快取時 jobs 為空直接返回，不會無限迴圈。
        void ensureRoomScheme3dPreviews();
      }
    }
  })();
  return roomSchemeRuntimeState.previewInFlight;
}

function chooseRoomScheme(schemeId) {
  const room = state.rooms.find((item) => String(item.id) === String(state.selectedRoomSchemeId));
  if (!room || !selectSchemeForRoom(state.designSchemes, room.id, schemeId)) return;
  state.designSchemes.configuration_snapshot = null;
  renderRoomSchemeGate();
  renderRoomSchemeSelectionDialog();
  scheduleSave("white_model_3d");
}

function selectedSchemeMismatchNotice() {
  const mismatch = state.selectedSchemeMismatch;
  if (!mismatch) return "";
  const parts = [];
  if (mismatch.moved?.length) parts.push(`調整 ${mismatch.moved.length} 件位置`);
  if (mismatch.missing?.length) parts.push(`移除 ${mismatch.missing.length} 件放不下的家具`);
  if (mismatch.unexpected?.length) parts.push(`補入 ${mismatch.unexpected.length} 件`);
  if (!parts.length) return "";
  return `已合成配置：系統依空間與門窗淨空自動${parts.join("、")}，可在下一步微調。`;
}

async function completeRoomSchemeSelection() {
  applyUnavailableRoomSchemeDefaults();
  if (!allRoomsHaveSchemeSelections(state.designSchemes, state.rooms)) return;
  const compositeFurniture = composeSelectedRoomFurniture();
  if (!compositeFurniture.length && state.rooms.length) {
    element.roomSchemeWarning.hidden = false;
    element.roomSchemeWarning.textContent = "無法組合逐房方案：選定方案沒有可用家具資料。請重新產生 A/B 配置後再試。";
    return;
  }
  const schemeA = state.designSchemes.schemes.A;
  const originalFurniture = JSON.parse(JSON.stringify(schemeA.furniture || []));
  const originalScene = state.sceneData ? JSON.parse(JSON.stringify(state.sceneData)) : null;
  state.designSchemes.active_scheme_id = "A";
  state.furniture2d = compositeFurniture;
  state.sceneData = null;
  schemeA.furniture = JSON.parse(JSON.stringify(compositeFurniture));
  schemeA.sceneData = null;
  schemeA.stale = false;
  schemeA.staleReason = "";
  element.roomSchemeComplete.disabled = true;
  element.roomSchemeComplete.textContent = "正在合成並驗證最終配置…";
  try {
    // A room-by-room A/B decision is a final placement choice. Do not let
    // the generation endpoint drop missing models or append recommendations.
    const generated = await confirmLayout2d({ strictSelectedFurniture: true });
    if (!generated || !state.sceneData?.scene_objects) {
      throw new Error(state.lastWhiteModelGenerationError || "configuration_scene_generation_failed");
    }
    state.designSchemes.configuration_snapshot = configurationSnapshot();
    roomSchemePreviewCache.clear();   // 已進入下一流程，清除不再需要的逐房方案預覽快照
    renderRoomSchemeGate();
    closeRoomSchemeSelectionDialog();
    scheduleSave("white_model_3d");
    setStatus(
      selectedSchemeMismatchNotice()
        || "所有房間方案已合成為唯一配置，並已重新驗證 2D 與 3D 場景。",
      "success",
    );
  } catch (error) {
    schemeA.furniture = originalFurniture;
    schemeA.sceneData = originalScene;
    state.furniture2d = originalFurniture;
    state.sceneData = originalScene;
    element.roomSchemeWarning.hidden = false;
    element.roomSchemeWarning.textContent = `無法合成最終配置：${errorMessage(error)}`;
    element.roomSchemeComplete.disabled = false;
    element.roomSchemeComplete.textContent = "完成選擇並開始微調";
  }
}

function renderSchemeControls() {
  const hasB = Boolean(state.designSchemes.schemes.B);
  $$("[data-design-scheme]").forEach((button) => {
    const schemeId = button.dataset.designScheme;
    button.hidden = schemeId === "B" && !hasB;
    button.classList.toggle("is-active", schemeId === activeSchemeId());
    button.setAttribute("aria-selected", String(schemeId === activeSchemeId()));
  });
  if (element.layoutSchemeStatus) {
    const scheme = activeScheme();
    element.layoutSchemeStatus.textContent = scheme?.stale
      ? `方案 ${activeSchemeId()} 的結構已變更，請依問卷重新配置`
      : `目前編輯方案 ${activeSchemeId()}`;
  }
  if (element.lockedSchemeLabel) {
    element.lockedSchemeLabel.textContent = state.designSchemes.locked_scheme_id
      ? `已鎖定方案 ${state.designSchemes.locked_scheme_id}`
      : "尚未鎖定方案";
  }
  renderRoomSchemeGate();
}

function renderSchemeComparison() {
  if (!element.schemeCompare) return;
  // 第 4 步只確認唯一結構基準；家具方案比較留在第 6 步。
  const show = false;
  element.schemeCompare.hidden = !show;
  if (!show || !element.spaceImage?.src) return;
  element.schemeAImage.src = element.spaceImage.src;
  element.schemeBImage.src = element.spaceImage.src;
  const { imageWidth, imageHeight } = planGeometry();
  const aspectRatio = `${Math.max(1, element.spaceImage.naturalWidth || imageWidth)}
    / ${Math.max(1, element.spaceImage.naturalHeight || imageHeight)}`;
  [element.schemeAImage, element.schemeBImage].forEach((image) => {
    image.closest(".rp-scheme-plan-stage").style.aspectRatio = aspectRatio;
  });
  [element.schemeAOverlay, element.schemeBOverlay].forEach((overlay) => {
    overlay.setAttribute("viewBox", `0 0 ${imageWidth} ${imageHeight}`);
    overlay.setAttribute("preserveAspectRatio", "none");
  });
  element.schemeAOverlay.innerHTML = schemeStructureMarkup("A");
  element.schemeBOverlay.innerHTML = schemeStructureMarkup("B");
}

  return {
    addMissedRoom,
    addRoomReviewReason,
    allStepSixRoomSurfacesConfirmed,
    analysisReviewItems,
    applyAttachedOpeningUpdates,
    applyCanonicalRoomLabels,
    applyDjangoZoneRoomLabels,
    applyUnavailableRoomSchemeDefaults,
    attachedOpeningUpdates,
    buildRoomSchemePreviewScene,
    CANONICAL_ROOM_LABELS,
    captureConfirmedStructureSnapshot,
    chooseRoomScheme,
    CIRCLED_ROOM_ORDINALS,
    closeRoomSchemeSelectionDialog,
    cmToPixel,
    completeRoomSchemeSelection,
    composeSelectedRoomFurniture,
    configurationSnapshot,
    confirmAllRooms,
    confirmedFloorplanEditor,
    confirmedRoomHeightCm,
    confirmedStepSixSurfaceCount,
    confirmedWallOpeningForSnapshot,
    confirmRoom,
    deleteRoom,
    ensureRoomScheme3dPreviews,
    ensureRoomSchemeAlternative,
    focusStepSixRoom,
    genericPendingRoomLabel,
    hasStepFourConfirmedOpening,
    hydrateConfirmedStructureSnapshot,
    hydrateSceneWallMass,
    ICON_INFERENCE_MAX_ROOM_AREA_M2,
    initializeRoomsAndStructures,
    insertRoomNodeAt,
    isDismissedAutoRoom,
    isStructuralSnapshotPoint,
    lockedConfigurationSnapshot,
    mergeSelectedRoomNodes,
    mergeSelectedRooms,
    navigateRoomScheme3dPreview,
    nearestPointOnRoomEdge,
    normalizeIconInferredRoomReview,
    normalizeWallDemolitionCandidates,
    openRoomScheme3dPreview,
    openRoomSchemeSelectionDialog,
    pendingRoomBaseLabel,
    pixelToCm,
    planGeometry,
    populateStepSixRoomSelectors,
    preparedAutoRoomLabels,
    prepareRoomSchemePreviewViewer,
    promptRoomSchemeSelection,
    recognitionReviewSuffix,
    refreshConfigurationSnapshot,
    renderRooms,
    renderRoomSchemeGate,
    renderRoomSchemeSelectionDialog,
    renderSchemeComparison,
    renderSchemeControls,
    renderSpaceOverlay,
    renderStepSixSurfaceProgress,
    roomFinishDraftFor,
    roomHasComparableSchemeB,
    roomIconCentroidCm,
    roomPolygonSvg,
    roomQuestionnaireSummary,
    roomReviewHint,
    roomSchemeFurnitureLabel,
    roomSchemeFurnitureLegend,
    roomSchemeGateBlocking,
    roomSchemePlanMarkup,
    roomSchemePreviewFloorplan,
    roomSchemePreviewKey,
    roomSchemeSelectionRequired,
    schemeFurnitureForRoom,
    schemeFurnitureSceneFromShell,
    schemeStructureMarkup,
    segmentSvg,
    selectedSchemeMismatchNotice,
    selectedStepSixRoom,
    setRoomGeometryMode,
    setRoomNodeMode,
    setRoomSchemeWorkbenchLocked,
    setStepSixSurfaceKind,
    setStepSixSurfaceStatus,
    setTaskDialogOpen,
    SHOW_ALL_ROOMS_BUTTONS,
    snapshotCopy,
    snapshotFurniture,
    splitImplausibleIconRoomsByInteriorWalls,
    splitSelectedRoom,
    stepSixRoomSurfaceConfirmed,
    stepSixSurfacesFinalLocked,
    stepSixSurfaceUnlockButtons,
    STORAGE_INFERENCE_MAX_AREA_CM2,
    structuralSnapshotPoint,
    structureCollections,
    structureSectionMeta,
    syncConfigurationConfirmButton,
    updateRoomGeometryControls,
    updateRoomNodeControls,
    updateShowAllRoomsButton,
    waitForRoomSchemePreviewFrames,
    wallBoundary,
    wallBoundaryContext,
  };
}
