export const ROOM_REQUIREMENTS_SCHEMA_VERSION = 1;

const clone = (value) => {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
};

const numberOrZero = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

function polygonBoundsCm(room = {}) {
  const points = room.polygon_cm || room.polygon || room.points || [];
  if (!Array.isArray(points) || points.length < 3) return null;
  const xs = points.map((point) => numberOrZero(point.x ?? point[0]));
  const ys = points.map((point) => numberOrZero(point.y ?? point[1]));
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
    widthCm: Math.max(...xs) - Math.min(...xs),
    depthCm: Math.max(...ys) - Math.min(...ys),
  };
}

export function roomMeasurements(room = {}) {
  const bounds = polygonBoundsCm(room);
  const widthCm = numberOrZero(
    room.width_cm ?? room.widthCm ?? room.dimensions?.width_cm ?? bounds?.widthCm,
  );
  const depthCm = numberOrZero(
    room.depth_cm
      ?? room.height_cm
      ?? room.depthCm
      ?? room.dimensions?.depth_cm
      ?? bounds?.depthCm,
  );
  const areaM2 = numberOrZero(
    room.area_m2 ?? room.areaM2 ?? ((widthCm * depthCm) / 10000),
  );
  return {
    widthCm,
    depthCm,
    shortSideCm: Math.min(widthCm, depthCm),
    areaM2,
  };
}

function emptyRoomRequirement(room = {}) {
  const roomId = String(room.id ?? room.room_id ?? "");
  return {
    roomId,
    roomType: room.type || room.room_type || "other",
    roomLabel: room.name || room.label || "未命名空間",
    axisAnswers: {},
    furniture: {
      required: [],
      optional: [],
    },
    climate: {
      airConditioning: null,
    },
    surfaces: {
      paletteId: null,
      wallDefault: {
        materialId: null,
        color: null,
      },
      wallSurfaceIds: [],
      wallOverrides: {},
      floor: {
        materialId: null,
        color: null,
      },
      ceiling: {
        materialId: null,
        styleId: null,
        lightingId: null,
        color: null,
      },
    },
    feasibility: [],
    specialRequests: [],
    confirmed: false,
  };
}

function migrateLegacyFinishes(target, legacyFinishes = {}) {
  if (!legacyFinishes || typeof legacyFinishes !== "object") return target;
  target.surfaces.paletteId = legacyFinishes.stylePackId || null;
  target.surfaces.wallDefault = {
    materialId: legacyFinishes.wallMaterial || null,
    color: legacyFinishes.wallColor || null,
  };
  target.surfaces.floor = {
    materialId: legacyFinishes.floorMaterial || null,
    color: legacyFinishes.floorColor || null,
  };
  target.surfaces.ceiling = {
    materialId: legacyFinishes.ceilingMaterial || null,
    styleId: legacyFinishes.ceilingStyle || null,
    lightingId: legacyFinishes.lightStyle || null,
    color: legacyFinishes.ceilingColor || null,
  };
  return target;
}

export function normalizeRoomRequirements(
  saved = {},
  rooms = [],
  legacy = {},
) {
  const savedRooms = saved.roomRequirements || saved.rooms || {};
  const roomRequirements = {};
  rooms.forEach((room) => {
    const base = emptyRoomRequirement(room);
    const roomId = base.roomId;
    const restored = savedRooms[roomId] || {};
    const migrated = migrateLegacyFinishes(base, legacy.finishes);
    roomRequirements[roomId] = {
      ...migrated,
      ...clone(restored),
      roomId,
      roomType: room.type || room.room_type || restored.roomType || "other",
      roomLabel: room.name || room.label || restored.roomLabel || "未命名空間",
      furniture: {
        ...migrated.furniture,
        ...(restored.furniture || {}),
      },
      climate: {
        ...migrated.climate,
        ...(restored.climate || {}),
      },
      surfaces: {
        ...migrated.surfaces,
        ...(restored.surfaces || {}),
        wallDefault: {
          ...migrated.surfaces.wallDefault,
          ...(restored.surfaces?.wallDefault || {}),
        },
        wallOverrides: clone(restored.surfaces?.wallOverrides || {}),
        wallSurfaceIds: clone(restored.surfaces?.wallSurfaceIds || []),
        floor: {
          ...migrated.surfaces.floor,
          ...(restored.surfaces?.floor || {}),
        },
        ceiling: {
          ...migrated.surfaces.ceiling,
          ...(restored.surfaces?.ceiling || {}),
        },
      },
    };
  });
  return {
    schemaVersion: ROOM_REQUIREMENTS_SCHEMA_VERSION,
    activeRoomId: saved.activeRoomId || rooms[0]?.id || null,
    roomRequirements,
    globalProfile: clone(saved.globalProfile || legacy.basic || {}),
    globalConfirmed: saved.globalConfirmed === true || legacy.basicConfirmed === true,
  };
}

export function applyRoomFinishScope(
  model,
  sourceRoomId,
  scope = "room",
  selectedRoomIds = [],
) {
  const next = clone(model);
  const source = next.roomRequirements?.[sourceRoomId];
  if (!source) return next;
  const allRooms = Object.values(next.roomRequirements);
  let targets = [source];
  if (scope === "all") targets = allRooms;
  if (scope === "same-type") {
    targets = allRooms.filter((room) => room.roomType === source.roomType);
  }
  if (scope === "selected") {
    const selected = new Set(selectedRoomIds.map(String));
    targets = allRooms.filter((room) => selected.has(String(room.roomId)));
  }
  targets.forEach((room) => {
    room.surfaces = clone(source.surfaces);
    room.climate = clone(source.climate);
    room.confirmed = false;
  });
  return next;
}

const CONDITIONAL_OPTIONS = Object.freeze({
  bathtub: {
    minAreaM2: 4.5,
    minShortSideCm: 170,
    doorClearanceCm: 80,
    requiredInteriorDepthCm: 170,
  },
  double_vanity: {
    minAreaM2: 5.2,
    minShortSideCm: 185,
    doorClearanceCm: 80,
    requiredInteriorDepthCm: 185,
  },
  large_dining_table: {
    minAreaM2: 10,
    minShortSideCm: 280,
    doorClearanceCm: 90,
    requiredInteriorDepthCm: 280,
  },
});

export function evaluateConditionalOption(room, optionId, openings = []) {
  const rule = CONDITIONAL_OPTIONS[optionId];
  if (!rule) {
    return {
      optionId,
      feasible: true,
      forcePlacement: false,
      warnings: [],
    };
  }
  const measurements = roomMeasurements(room);
  const roomId = String(room.id ?? room.room_id ?? "");
  const roomDoors = openings.filter((opening) => {
    const roomIds = Array.isArray(opening.room_ids)
      ? opening.room_ids.map(String)
      : [];
    return String(opening.room_id ?? opening.roomId ?? "") === roomId
      || roomIds.includes(roomId);
  });
  const narrowDoor = roomDoors.some((door) =>
    numberOrZero(door.width_cm ?? door.widthCm) > 0
      && numberOrZero(door.width_cm ?? door.widthCm) < rule.doorClearanceCm
  );
  const bounds = polygonBoundsCm(room);
  const doorMetrics = roomDoors.map((door) => {
    const start = door.start || door.hinge || {};
    const end = door.end || {};
    const widthCm = numberOrZero(door.width_cm ?? door.widthCm)
      || Math.hypot(
        numberOrZero(end.x) - numberOrZero(start.x),
        numberOrZero(end.y ?? end.z) - numberOrZero(start.y ?? start.z),
      );
    const centerX = (numberOrZero(start.x) + numberOrZero(end.x ?? start.x)) / 2;
    const centerY = (
      numberOrZero(start.y ?? start.z)
      + numberOrZero(end.y ?? end.z ?? start.y ?? start.z)
    ) / 2;
    const horizontal = Math.abs(
      numberOrZero(end.x) - numberOrZero(start.x),
    ) >= Math.abs(
      numberOrZero(end.y ?? end.z) - numberOrZero(start.y ?? start.z),
    );
    const availableInteriorDepthCm = horizontal
      ? Math.max(
        centerY - numberOrZero(bounds?.minY),
        numberOrZero(bounds?.maxY) - centerY,
      )
      : Math.max(
        centerX - numberOrZero(bounds?.minX),
        numberOrZero(bounds?.maxX) - centerX,
      );
    return { widthCm, availableInteriorDepthCm };
  });
  const doorSwingAreaM2 = doorMetrics.reduce(
    (total, door) => total + Math.PI * door.widthCm * door.widthCm / 4 / 10000,
    0,
  );
  const effectiveAreaM2 = Math.max(0, measurements.areaM2 - doorSwingAreaM2);
  const doorPositionConflict = doorMetrics.some(
    (door) => door.availableInteriorDepthCm > 0
      && door.availableInteriorDepthCm < rule.requiredInteriorDepthCm,
  );
  const feasible = effectiveAreaM2 >= rule.minAreaM2
    && measurements.shortSideCm >= rule.minShortSideCm
    && !narrowDoor
    && !doorPositionConflict;
  return {
    optionId,
    feasible,
    forcePlacement: false,
    warnings: feasible
      ? []
      : ["目前尺寸可能無法配置；可保留為特殊需求，家具引擎不會強制擺入。"],
    measurements,
    doorSwingAreaM2,
    effectiveAreaM2,
    doorPositionConflict,
    required: clone(rule),
  };
}

function roomRequirementComplete(room = {}) {
  const ceiling = room.surfaces?.ceiling || {};
  return room.confirmed === true
    && Boolean(room.climate?.airConditioning)
    && Boolean(room.surfaces?.wallDefault?.materialId)
    && Boolean(room.surfaces?.floor?.materialId)
    && Boolean(ceiling.materialId)
    && Boolean(ceiling.styleId)
    && Boolean(ceiling.lightingId);
}

export function buildRoomRequirementsPayload(
  model,
  { planGeometry = null, questionnaireVersion = null } = {},
) {
  const rooms = Object.values(model?.roomRequirements || {});
  const allRoomsConfirmed = rooms.length > 0 && rooms.every(roomRequirementComplete);
  const globalConfirmed = model?.globalConfirmed === true;
  const readyForRag = allRoomsConfirmed && globalConfirmed;
  return {
    schemaVersion: ROOM_REQUIREMENTS_SCHEMA_VERSION,
    questionnaireVersion,
    readyForRag,
    allRoomsConfirmed,
    globalConfirmed,
    roomRequirements: clone(rooms),
    globalProfile: clone(model?.globalProfile || {}),
    planGeometry: clone(planGeometry),
  };
}
