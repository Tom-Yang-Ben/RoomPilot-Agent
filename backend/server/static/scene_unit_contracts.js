const CONTRACT_SCHEMA_VERSION = "2.0";

function numericDimension(item, cmKey, meterKey) {
  if (Number.isFinite(Number(item[cmKey]))) return Number(item[cmKey]);
  if (Number.isFinite(Number(item[meterKey]))) return Number(item[meterKey]) * 100;
  return undefined;
}

function pointScaleFor(item = {}, parentUnit) {
  if (item.coordinate_unit === "cm") return 1;
  if (item.coordinate_unit === "m") return 100;
  if (Object.keys(item).some((key) => key.endsWith("_m")) || "size_m" in item) return 100;
  if (parentUnit === "cm") return 1;
  return 100;
}

function editorPoint(value = {}, scale = 1) {
  return {
    x: Number(value.x ?? value[0] ?? 0) * scale,
    y: Number(value.y ?? value.z ?? value[1] ?? 0) * scale,
  };
}

function scenePoint(value = {}, scale = 1) {
  return {
    x: Number(value.x ?? value[0] ?? 0) * scale,
    z: Number(value.z ?? value.y ?? value[1] ?? 0) * scale,
  };
}

function centimeterDimensions(item = {}) {
  return {
    width_cm: numericDimension(item, "width_cm", "width_m"),
    thickness_cm: numericDimension(item, "thickness_cm", "thickness_m"),
    height_cm: numericDimension(item, "height_cm", "height_m"),
    top_cm: numericDimension(item, "top_cm", "top_m"),
    depth_cm: numericDimension(item, "depth_cm", "depth_m"),
    size_cm: numericDimension(item, "size_cm", "size_m"),
    sill_height_cm: numericDimension(item, "sill_height_cm", "sill_height_m"),
    head_height_cm: numericDimension(item, "head_height_cm", "head_height_m"),
  };
}

function withoutMeterDimensions(item = {}) {
  return Object.fromEntries(
    Object.entries(item).filter(([key]) => !key.endsWith("_m") && key !== "size_m"),
  );
}

export function normalizeSavedSpaceConfirmation(saved = {}) {
  const rooms = Array.isArray(saved.rooms) ? saved.rooms : [];
  const structures = saved.structures || {};
  const parentUnit = saved.coordinate_unit;

  const structure = (item = {}) => {
    const coordinateScale = pointScaleFor(item, parentUnit);
    const normalized = {
      ...withoutMeterDimensions(item),
      ...centimeterDimensions(item),
      coordinate_unit: "cm",
    };
    if (item.start) normalized.start = editorPoint(item.start, coordinateScale);
    if (item.end) normalized.end = editorPoint(item.end, coordinateScale);
    if (item.center) normalized.center = editorPoint(item.center, coordinateScale);
    if (item.swing_end) normalized.swing_end = editorPoint(item.swing_end, coordinateScale);
    return normalized;
  };

  const normalizedStructures = {};
  ["walls", "doors", "windows", "beams", "columns"].forEach((kind) => {
    normalizedStructures[kind] = (structures[kind] || []).map(structure);
  });

  return {
    coordinate_unit: "cm",
    schema_version: CONTRACT_SCHEMA_VERSION,
    dismissed_auto_room_ids: Array.isArray(saved.dismissed_auto_room_ids)
      ? saved.dismissed_auto_room_ids
      : [],
    design_schemes: saved.design_schemes || null,
    rooms: rooms.map((room, index) => {
      const polygon = Array.isArray(room.polygon_cm)
        ? room.polygon_cm
        : (Array.isArray(room.polygon_m) ? room.polygon_m : (room.polygon || []));
      const coordinateScale = Array.isArray(room.polygon_cm)
        ? 1
        : (Array.isArray(room.polygon_m) ? 100 : pointScaleFor(room, parentUnit));
      const {
        polygon_m: _polygonM,
        polygon: _polygon,
        ...roomFields
      } = room;
      return {
        ...roomFields,
        id: room.id || room.room_id || `room-${index + 1}`,
        coordinate_unit: "cm",
        polygon_cm: polygon.map((value) => editorPoint(value, coordinateScale)),
      };
    }).filter((room) => room.polygon_cm.length >= 3),
    structures: normalizedStructures,
  };
}

function normalizeSceneSegment(segment = {}, scale = 1) {
  const normalized = {
    ...withoutMeterDimensions(segment),
    ...centimeterDimensions(segment),
    coordinate_unit: "cm",
  };
  if (segment.start) normalized.start = scenePoint(segment.start, scale);
  if (segment.end) normalized.end = scenePoint(segment.end, scale);
  if (segment.swing_end) normalized.swing_end = scenePoint(segment.swing_end, scale);
  return normalized;
}

function normalizeRing(ring = [], scale = 1) {
  return ring.map((point) => [
    Number(point[0] ?? point.x ?? 0) * scale,
    Number(point[1] ?? point.z ?? point.y ?? 0) * scale,
  ]);
}

function normalizePolygon(polygon = {}, scale = 1) {
  return {
    ...polygon,
    exterior: normalizeRing(polygon.exterior, scale),
    holes: (polygon.holes || []).map((ring) => normalizeRing(ring, scale)),
  };
}

function objectCoordinateScale(item = {}, fallbackScale = 1) {
  if (item.coordinate_unit === "cm") return 1;
  if (item.coordinate_unit === "m") return 100;
  return fallbackScale;
}

function inferredGeometryScale(points, floorplan, fallbackScale) {
  if (floorplan.schema_version === CONTRACT_SCHEMA_VERSION) return 1;
  if (fallbackScale === 100) return 100;
  const coordinates = points
    .map((point) => [
      Number(point?.x ?? point?.[0]),
      Number(point?.z ?? point?.y ?? point?.[1]),
    ])
    .filter(([x, z]) => Number.isFinite(x) && Number.isFinite(z));
  if (!coordinates.length) return fallbackScale;

  const xs = coordinates.map(([x]) => x);
  const zs = coordinates.map(([, z]) => z);
  const observedExtent = Math.max(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...zs) - Math.min(...zs),
    Math.max(...xs.map((value) => Math.abs(value))) * 2,
    Math.max(...zs.map((value) => Math.abs(value))) * 2,
  );
  const expectedExtent = Math.max(
    Number(floorplan.width_cm) || 0,
    Number(floorplan.depth_cm) || 0,
  );
  if (expectedExtent > 0 && observedExtent > 0 && observedExtent <= expectedExtent / 20) {
    return 100;
  }
  return fallbackScale;
}

function segmentPoints(segments = []) {
  return segments.flatMap((segment) => [segment.start, segment.end].filter(Boolean));
}

function polygonPoints(polygons = []) {
  return polygons.flatMap((polygon) => [
    ...(polygon.exterior || []),
    ...(polygon.holes || []).flat(),
  ]);
}

const WALL_ANCHORED_FURNITURE_TYPES = new Set([
  "appliance-cabinet",
  "bathroom-vanity",
  "bed",
  "bed-frame",
  "bookcase",
  "cabinet",
  "desk",
  "mirror-cabinet",
  "refrigerator",
  "sideboard",
  "sofa",
  "sofa-bed",
  "storage-cabinet",
  "tv-bench",
  "wardrobe",
  "washer",
]);

function axisAlignedRegionBounds(region = {}) {
  if ((region.holes || []).length) return null;
  const points = (region.exterior || [])
    .map((point) => [Number(point?.[0] ?? point?.x), Number(point?.[1] ?? point?.z ?? point?.y)])
    .filter(([x, z]) => Number.isFinite(x) && Number.isFinite(z));
  const xs = [...new Set(points.map(([x]) => x))];
  const zs = [...new Set(points.map(([, z]) => z))];
  const corners = new Set(points.map(([x, z]) => `${x}:${z}`));
  if (xs.length !== 2 || zs.length !== 2 || corners.size !== 4) return null;
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minZ: Math.min(...zs),
    maxZ: Math.max(...zs),
  };
}

function rotatedFootprintCm(item = {}) {
  const width = Number(item.size_cm?.width);
  const depth = Number(item.size_cm?.depth);
  if (!(width > 0) || !(depth > 0)) return null;
  const radians = Math.abs((Number(item.rotation_y_deg) || 0) % 180) * Math.PI / 180;
  const cos = Math.abs(Math.cos(radians));
  const sin = Math.abs(Math.sin(radians));
  return {
    width: width * cos + depth * sin,
    depth: width * sin + depth * cos,
  };
}

function legacyWallGapPosition(item, bounds) {
  const footprint = rotatedFootprintCm(item);
  const x = Number(item.position_cm?.x);
  const z = Number(item.position_cm?.z);
  if (!footprint || !Number.isFinite(x) || !Number.isFinite(z)) return null;
  const halfWidth = footprint.width / 2;
  const halfDepth = footprint.depth / 2;
  const gaps = {
    left: x - halfWidth - bounds.minX,
    right: bounds.maxX - x - halfWidth,
    top: z - halfDepth - bounds.minZ,
    bottom: bounds.maxZ - z - halfDepth,
  };
  if (Object.values(gaps).some((gap) => gap < -0.5)) return null;

  const isLegacyGap = (gap) => gap >= 7.5 && gap <= 8.5;
  const next = { x, z };
  let changed = false;
  if (isLegacyGap(gaps.left)) {
    next.x = bounds.minX + halfWidth;
    changed = true;
  } else if (isLegacyGap(gaps.right)) {
    next.x = bounds.maxX - halfWidth;
    changed = true;
  }
  if (isLegacyGap(gaps.top)) {
    next.z = bounds.minZ + halfDepth;
    changed = true;
  } else if (isLegacyGap(gaps.bottom)) {
    next.z = bounds.maxZ - halfDepth;
    changed = true;
  }
  if (!changed) return null;
  return {
    position: {
      x: Math.round(next.x * 1000) / 1000,
      z: Math.round(next.z * 1000) / 1000,
    },
    footprint: {
      width: Math.round(footprint.width * 1000) / 1000,
      depth: Math.round(footprint.depth * 1000) / 1000,
    },
  };
}

export function repairLegacyWallFurnitureGaps(sceneData, furniture2d = []) {
  if (!sceneData || typeof sceneData !== "object") {
    return { sceneData: null, furniture2d: [...(furniture2d || [])], repairedIds: [] };
  }
  const regions = new Map(
    (sceneData.floorplan?.room_regions || [])
      .map((region) => [String(region.room_id || region.id || ""), axisAlignedRegionBounds(region)])
      .filter(([roomId, bounds]) => roomId && bounds),
  );
  const repairedPositions = new Map();
  const repairedSceneObjects = (sceneData.scene_objects || []).map((item) => {
    const furnitureId = String(item.furniture_id || "");
    const roomBounds = regions.get(String(item.placement_room_id || ""));
    if (
      !furnitureId
      || !roomBounds
      || item.placement_engine !== "furniture_engine"
      || item.position_locked !== true
      || !WALL_ANCHORED_FURNITURE_TYPES.has(String(item.normalized_type || ""))
    ) {
      return item;
    }
    const repaired = legacyWallGapPosition(item, roomBounds);
    if (!repaired) return item;
    repairedPositions.set(furnitureId, repaired.position);
    return {
      ...item,
      position_cm: { ...(item.position_cm || {}), ...repaired.position },
      footprint_cm: repaired.footprint,
    };
  });
  const repairedFurniture2d = (furniture2d || []).map((item) => {
    const position = repairedPositions.get(String(item.id || ""));
    return position ? { ...item, xCm: position.x, yCm: position.z } : item;
  });
  return {
    sceneData: { ...sceneData, scene_objects: repairedSceneObjects },
    furniture2d: repairedFurniture2d,
    repairedIds: [...repairedPositions.keys()],
  };
}

export function normalizeSavedSceneData(saved) {
  if (!saved || typeof saved !== "object") return null;
  const floorplan = saved.floorplan || {};
  const defaultScale = floorplan.coordinate_unit === "cm" ? 1 : 100;
  const normalizedFloorplan = {
    ...floorplan,
    coordinate_unit: "cm",
    schema_version: CONTRACT_SCHEMA_VERSION,
  };

  [
    "wall_segments",
    "plan_segments",
    "door_segments",
    "window_segments",
    "beam_segments",
  ].forEach((key) => {
    const segments = floorplan[key] || [];
    const collectionScale = inferredGeometryScale(
      segmentPoints(segments),
      floorplan,
      defaultScale,
    );
    normalizedFloorplan[key] = segments.map((segment) => normalizeSceneSegment(
      segment,
      objectCoordinateScale(segment, collectionScale),
    ));
  });

  const columns = floorplan.columns || [];
  const columnScale = inferredGeometryScale(
    columns.map((column) => column.center).filter(Boolean),
    floorplan,
    defaultScale,
  );
  normalizedFloorplan.columns = columns.map((column) => {
    const normalized = {
      ...withoutMeterDimensions(column),
      ...centimeterDimensions(column),
      coordinate_unit: "cm",
    };
    if (column.center) {
      normalized.center = scenePoint(
        column.center,
        objectCoordinateScale(column, columnScale),
      );
    }
    return normalized;
  });
  const wallPolys = floorplan.wall_polys || [];
  const wallPolyScale = inferredGeometryScale(
    polygonPoints(wallPolys),
    floorplan,
    defaultScale,
  );
  normalizedFloorplan.wall_polys = wallPolys.map((polygon) => normalizePolygon(
    polygon,
    objectCoordinateScale(polygon, wallPolyScale),
  ));
  const roomRegions = floorplan.room_regions || [];
  const roomRegionScale = inferredGeometryScale(
    polygonPoints(roomRegions),
    floorplan,
    defaultScale,
  );
  normalizedFloorplan.room_regions = roomRegions.map((region) => normalizePolygon(
    region,
    objectCoordinateScale(region, roomRegionScale),
  ));

  if (floorplan.bbox) {
    const bboxScale = inferredGeometryScale(
      [
        [floorplan.bbox.minx, floorplan.bbox.minz],
        [floorplan.bbox.maxx, floorplan.bbox.maxz],
      ],
      floorplan,
      defaultScale,
    );
    normalizedFloorplan.bbox = Object.fromEntries(
      Object.entries(floorplan.bbox)
        .map(([key, value]) => [key, Number(value) * bboxScale]),
    );
  }
  ["doors", "windows"].forEach((key) => {
    const segments = floorplan[key] || [];
    const collectionScale = inferredGeometryScale(
      segments.flatMap((segment) => [
        [segment.x1, segment.z1],
        [segment.x2, segment.z2],
      ]),
      floorplan,
      defaultScale,
    );
    normalizedFloorplan[key] = segments.map((segment) => {
      const segmentScale = objectCoordinateScale(segment, collectionScale);
      return {
        ...segment,
        coordinate_unit: "cm",
        ...Object.fromEntries(
          ["x1", "z1", "x2", "z2"]
            .filter((axis) => axis in segment)
            .map((axis) => [axis, Number(segment[axis]) * segmentScale]),
        ),
      };
    });
  });

  return {
    ...saved,
    floorplan: normalizedFloorplan,
  };
}
