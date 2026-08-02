export const ROOM_DIMENSION_COLORS = [
  "#27745f",
  "#2f7890",
  "#b76536",
  "#7656a6",
  "#a9473b",
  "#367b78",
  "#9a731f",
];

const round = (value, digits = 2) => {
  const factor = 10 ** digits;
  return Math.round((Number(value) + Number.EPSILON) * factor) / factor;
};

const clamp = (value, minimum, maximum) =>
  Math.max(minimum, Math.min(maximum, value));

const escapeXml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#39;");

const validPoint = (point) =>
  Number.isFinite(Number(point?.x)) && Number.isFinite(Number(point?.y));

function dimensionLine({
  x1,
  y1,
  x2,
  y2,
  label,
  color,
  fontSize,
  vertical = false,
}) {
  const tick = fontSize * 0.42;
  const labelX = (x1 + x2) / 2;
  const labelY = (y1 + y2) / 2;
  const ticks = vertical
    ? `<path d="M ${x1 - tick} ${y1} H ${x1 + tick} M ${x2 - tick} ${y2} H ${x2 + tick}"/>`
    : `<path d="M ${x1} ${y1 - tick} V ${y1 + tick} M ${x2} ${y2 - tick} V ${y2 + tick}"/>`;
  const transform = vertical
    ? ` transform="rotate(-90 ${labelX} ${labelY})"`
    : "";
  const textX = vertical ? labelX : labelX;
  const textY = vertical ? labelY - fontSize * 0.45 : labelY - fontSize * 0.45;
  return `
    <g class="rp-plan-dimension" stroke="${color}" stroke-width="2.4" fill="none">
      <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>
      ${ticks}
      <text x="${textX}" y="${textY}"${transform} text-anchor="middle"
        fill="${color}" stroke="#fff" stroke-width="${fontSize * 0.34}"
        paint-order="stroke" font-size="${fontSize}" font-weight="800">${escapeXml(label)}</text>
    </g>`;
}

export function buildDimensionedPlanAnnotations(
  rooms = [],
  { imageWidth = 1000, imageHeight = 1000 } = {},
) {
  const width = Math.max(1, Number(imageWidth) || 1000);
  const height = Math.max(1, Number(imageHeight) || 1000);
  const fontSize = clamp(Math.min(width, height) * 0.021, 13, 21);
  const normalizedRooms = rooms.map((room, index) => {
    const polygon = (room.polygonPx || []).filter(validPoint).map((point) => ({
      x: clamp(Number(point.x), 0, width),
      y: clamp(Number(point.y), 0, height),
    }));
    if (polygon.length < 3) return null;
    const xs = polygon.map((point) => point.x);
    const ys = polygon.map((point) => point.y);
    const bounds = {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
    const center = polygon.reduce(
      (sum, point) => ({ x: sum.x + point.x / polygon.length, y: sum.y + point.y / polygon.length }),
      { x: 0, y: 0 },
    );
    return {
      ...room,
      polygon,
      bounds,
      center,
      color: ROOM_DIMENSION_COLORS[index % ROOM_DIMENSION_COLORS.length],
      widthCm: Math.max(0, Number(room.widthCm) || 0),
      depthCm: Math.max(0, Number(room.depthCm) || 0),
      areaM2: Math.max(0, Number(room.areaM2) || 0),
    };
  }).filter(Boolean);

  const svg = normalizedRooms.map((room) => {
    const { bounds, center, color } = room;
    const roomWidthPx = bounds.maxX - bounds.minX;
    const roomHeightPx = bounds.maxY - bounds.minY;
    const roomFontSize = clamp(Math.min(roomWidthPx, roomHeightPx) * 0.105, 10, fontSize);
    const roomLabelSize = roomFontSize * 1.08;
    const compact = roomWidthPx < fontSize * 9;
    const inset = clamp(
      Math.min(roomWidthPx, roomHeightPx) * 0.1,
      roomFontSize * 0.8,
      roomFontSize * 1.5,
    );
    const horizontalY = clamp(bounds.minY + inset, fontSize, height - fontSize);
    const verticalX = clamp(bounds.minX + inset, fontSize, width - fontSize);
    const horizontalStart = bounds.minX + Math.min(5, roomWidthPx * 0.08);
    const horizontalEnd = bounds.maxX - Math.min(5, roomWidthPx * 0.08);
    const verticalStart = bounds.minY + Math.min(5, roomHeightPx * 0.08);
    const verticalEnd = bounds.maxY - Math.min(5, roomHeightPx * 0.08);
    const points = room.polygon.map((point) => `${round(point.x, 1)},${round(point.y, 1)}`).join(" ");
    return `
      <g data-dimension-room="${escapeXml(room.id)}" pointer-events="none">
        <polygon points="${points}" fill="${color}" fill-opacity="0.09"
          stroke="${color}" stroke-width="3.2" stroke-dasharray="11 6"/>
        ${dimensionLine({
          x1: round(horizontalStart, 1),
          y1: round(horizontalY, 1),
          x2: round(horizontalEnd, 1),
          y2: round(horizontalY, 1),
          label: `${Math.round(room.widthCm)} cm`,
          color,
          fontSize: roomFontSize,
        })}
        ${dimensionLine({
          x1: round(verticalX, 1),
          y1: round(verticalStart, 1),
          x2: round(verticalX, 1),
          y2: round(verticalEnd, 1),
          label: `${Math.round(room.depthCm)} cm`,
          color,
          fontSize: roomFontSize,
          vertical: true,
        })}
        <text x="${round(center.x, 1)}" y="${round(center.y - roomLabelSize * 0.18, 1)}"
          text-anchor="middle" fill="${color}" stroke="#fff" stroke-width="${roomLabelSize * 0.38}"
          paint-order="stroke" font-size="${roomLabelSize}" font-weight="900">${escapeXml(room.label)}</text>
        <text x="${round(center.x, 1)}" y="${round(center.y + roomLabelSize * 0.92, 1)}"
          text-anchor="middle" fill="${color}" stroke="#fff" stroke-width="${roomFontSize * 0.34}"
          paint-order="stroke" font-size="${roomFontSize}" font-weight="800">${room.areaM2.toFixed(2)} m²${compact ? "" : " · ±5%"}</text>
      </g>`;
  }).join("");

  return {
    svg,
    roomCount: normalizedRooms.length,
    totalAreaM2: round(normalizedRooms.reduce((sum, room) => sum + room.areaM2, 0)),
    rooms: normalizedRooms.map((room) => ({
      id: room.id,
      label: room.label,
      color: room.color,
      widthCm: round(room.widthCm),
      depthCm: round(room.depthCm),
      areaM2: round(room.areaM2),
    })),
  };
}
