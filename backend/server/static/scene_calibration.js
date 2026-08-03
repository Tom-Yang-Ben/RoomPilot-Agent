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
    cm_per_px: distance / pixelDistance,
  };
}

export function calibrationPointsFromAnalysis(analysis, savedCalibration = null) {
  const savedStart = savedCalibration?.start_px;
  const savedEnd = savedCalibration?.end_px;
  if (Array.isArray(savedStart) && Array.isArray(savedEnd)) {
    return [
      { x: Number(savedStart[0]), y: Number(savedStart[1]) },
      { x: Number(savedEnd[0]), y: Number(savedEnd[1]) },
    ];
  }

  const scaleEvidence = (analysis?.evidence || []).find(
    (item) => Array.isArray(item.start_px) && Array.isArray(item.end_px),
  );
  if (scaleEvidence) {
    return [
      { x: Number(scaleEvidence.start_px[0]), y: Number(scaleEvidence.start_px[1]) },
      { x: Number(scaleEvidence.end_px[0]), y: Number(scaleEvidence.end_px[1]) },
    ];
  }

  const pixelDistance = Number(analysis?.scale?.pixel_distance);
  const width = Number(analysis?.image_size_px?.width);
  const height = Number(analysis?.image_size_px?.height);
  if (!(pixelDistance > 0) || !(width > 0) || !(height > 0)) return [];

  if (pixelDistance <= width) {
    return [{ x: 0, y: 0 }, { x: pixelDistance, y: 0 }];
  }
  if (pixelDistance <= height) {
    return [{ x: 0, y: 0 }, { x: 0, y: pixelDistance }];
  }
  if (pixelDistance <= Math.hypot(width, height)) {
    return [{ x: 0, y: 0 }, {
      x: width,
      y: Math.sqrt((pixelDistance ** 2) - (width ** 2)),
    }];
  }
  return [];
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
