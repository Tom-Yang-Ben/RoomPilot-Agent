function polygonArea(points) {
  if (!points?.length) return 0;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0) / 2);
}

export function repairLoadedRoomPolygon(points) {
  let repaired = (points || []).map((point) => ({ ...point }));
  let changed = true;
  while (changed && repaired.length > 3) {
    changed = false;
    const area = polygonArea(repaired);
    for (let index = 0; index < repaired.length; index += 1) {
      const previous = repaired[(index + repaired.length - 1) % repaired.length];
      const point = repaired[index];
      const following = repaired[(index + 1) % repaired.length];
      const dx = following.x - previous.x;
      const dy = following.y - previous.y;
      const base = Math.hypot(dx, dy);
      if (base <= 1e-6) continue;
      const projection = (
        (point.x - previous.x) * dx + (point.y - previous.y) * dy
      ) / (base * base);
      const height = Math.abs(
        dx * (previous.y - point.y) - (previous.x - point.x) * dy,
      ) / base;
      if (projection >= 0 && projection <= 1 && height <= 2) {
        repaired = repaired.filter((_, candidateIndex) => candidateIndex !== index);
        changed = true;
        break;
      }
      if (base > 35) continue;
      if (projection < 0.1 || projection > 0.9) continue;
      if (height < 15 || height < base * 0.75) continue;
      const candidate = repaired.filter((_, candidateIndex) => candidateIndex !== index);
      const areaChange = Math.abs(area - polygonArea(candidate));
      if (areaChange > Math.max(500, area * 0.05)) continue;
      repaired = candidate;
      changed = true;
      break;
    }
  }
  return repaired;
}
