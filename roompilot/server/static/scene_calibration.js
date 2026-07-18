export function buildScaleCalibration(points, distanceCm) {
  if (!Array.isArray(points) || points.length !== 2) throw new Error("calibration_points_required");
  const [start, end] = points;
  const distance = Number(distanceCm);
  const pixelDistance = Math.hypot(Number(end.x) - Number(start.x), Number(end.y) - Number(start.y));
  if (!(distance > 0) || !(pixelDistance > 0)) throw new Error("calibration_measurement_invalid");
  return {
    distance_cm: distance,
    start_px: [Number(start.x), Number(start.y)],
    end_px: [Number(end.x), Number(end.y)],
    pixel_distance: pixelDistance,
    m_per_px: distance / 100 / pixelDistance,
  };
}

export function pointerToImagePoint(pointer, displayedRect, naturalSize) {
  if (!(displayedRect.width > 0) || !(displayedRect.height > 0)) {
    throw new Error("calibration_preview_unavailable");
  }
  return {
    x: Math.round((Number(pointer.clientX) - Number(displayedRect.left)) * Number(naturalSize.width) / Number(displayedRect.width)),
    y: Math.round((Number(pointer.clientY) - Number(displayedRect.top)) * Number(naturalSize.height) / Number(displayedRect.height)),
  };
}
