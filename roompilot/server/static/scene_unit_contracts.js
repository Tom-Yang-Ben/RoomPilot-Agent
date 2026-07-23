function numericDimension(item, cmKey, meterKey) {
  if (Number.isFinite(Number(item[cmKey]))) return Number(item[cmKey]);
  if (Number.isFinite(Number(item[meterKey]))) return Number(item[meterKey]) * 100;
  return undefined;
}

export function normalizeSavedSpaceConfirmation(saved = {}) {
  const rooms = Array.isArray(saved.rooms) ? saved.rooms : [];
  const structures = saved.structures || {};
  const hasCentimeterFields = rooms.some((room) => Array.isArray(room.polygon_cm))
    || Object.values(structures).some((items) =>
      (items || []).some((item) => Object.keys(item || {}).some((key) => key.endsWith("_cm"))));
  const coordinateScale = saved.coordinate_unit === "cm" || hasCentimeterFields ? 1 : 100;
  const point = (value = {}) => ({
    x: Number(value.x ?? value[0] ?? 0) * coordinateScale,
    y: Number(value.y ?? value.z ?? value[1] ?? 0) * coordinateScale,
  });
  const structure = (item = {}) => {
    const normalized = {
      ...Object.fromEntries(
        Object.entries(item).filter(([key]) => !key.endsWith("_m") && key !== "size_m"),
      ),
      width_cm: numericDimension(item, "width_cm", "width_m"),
      thickness_cm: numericDimension(item, "thickness_cm", "thickness_m"),
      height_cm: numericDimension(item, "height_cm", "height_m"),
      top_cm: numericDimension(item, "top_cm", "top_m"),
      depth_cm: numericDimension(item, "depth_cm", "depth_m"),
      size_cm: numericDimension(item, "size_cm", "size_m"),
      sill_height_cm: numericDimension(item, "sill_height_cm", "sill_height_m"),
      head_height_cm: numericDimension(item, "head_height_cm", "head_height_m"),
    };
    if (item.start) normalized.start = point(item.start);
    if (item.end) normalized.end = point(item.end);
    if (item.center) normalized.center = point(item.center);
    if (item.swing_end) normalized.swing_end = point(item.swing_end);
    return normalized;
  };
  const normalizedStructures = {};
  ["walls", "doors", "windows", "beams", "columns"].forEach((kind) => {
    normalizedStructures[kind] = (structures[kind] || []).map(structure);
  });
  return {
    coordinate_unit: "cm",
    rooms: rooms.map((room, index) => ({
      ...room,
      id: room.id || room.room_id || `room-${index + 1}`,
      polygon_cm: (room.polygon_cm || room.polygon_m || room.polygon || [])
        .map(point),
    })).filter((room) => room.polygon_cm.length >= 3),
    structures: normalizedStructures,
  };
}
