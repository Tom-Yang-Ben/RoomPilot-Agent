const round = (value, digits = 2) => {
  const factor = 10 ** digits;
  return Math.round((Number(value) + Number.EPSILON) * factor) / factor;
};

export function buildSpaceProportionSummary(rooms = [], uncertaintyRate = 0.05) {
  const normalized = rooms.map((room) => ({
    ...room,
    areaM2: Math.max(0, Number(room.areaM2) || 0),
  }));
  const totalAreaM2 = round(
    normalized.reduce((total, room) => total + room.areaM2, 0),
  );
  const roomsWithProportions = normalized.map((room) => ({
    ...room,
    areaM2: round(room.areaM2),
    areaMinM2: round(room.areaM2 * (1 - uncertaintyRate)),
    areaMaxM2: round(room.areaM2 * (1 + uncertaintyRate)),
    sharePercent: totalAreaM2 > 0 ? round((room.areaM2 / totalAreaM2) * 100, 1) : 0,
  }));
  const largest = roomsWithProportions.reduce(
    (current, room) => (!current || room.areaM2 > current.areaM2 ? room : current),
    null,
  );

  return {
    roomCount: roomsWithProportions.length,
    totalAreaM2,
    rooms: roomsWithProportions,
    largestRoom: largest
      ? { id: largest.id, label: largest.label, sharePercent: largest.sharePercent }
      : null,
  };
}
