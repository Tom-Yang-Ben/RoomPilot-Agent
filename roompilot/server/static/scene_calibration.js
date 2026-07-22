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

export function calibrationActionState(points, distanceCm) {
  if (!Array.isArray(points) || points.length !== 2) {
    return {
      ready: false,
      message: "請先在平面圖上定位兩個端點。",
    };
  }
  const [start, end] = points;
  const pixelDistance = Math.hypot(
    Number(end?.x) - Number(start?.x),
    Number(end?.y) - Number(start?.y),
  );
  if (!(pixelDistance > 0)) {
    return {
      ready: false,
      message: "兩個端點不能重疊，請重新拖曳其中一點。",
    };
  }
  if (!(Number(distanceCm) > 0)) {
    return {
      ready: false,
      message: "請輸入大於 0 的實際公分尺寸。",
    };
  }
  return {
    ready: true,
    message: "尺寸資料已完成，可以確認並顯示房間。",
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
