// 逐房鏡頭建議。
//
// scene_json 的 polygon_cm 走場景座標，而 viewer 內部的世界座標 z 與場景 z 反向
// （scene_viewer.js 的 sceneToWorldPosition 對 z 取負）。setCameraState 收的是世界
// 座標——它與 getCameraState 對稱，存下來的鏡頭才能原樣還原——所以場景→世界的
// 翻面必須在這裡做完。少了這一步，每間房的鏡頭都會落在 x 軸鏡像的位置：廚房視角
// 照到床、臥室視角照到餐桌，第 8 步的逐房生圖輸入也整批是錯的。

const DEFAULT_PLAN_WIDTH_CM = 420;
const DEFAULT_PLAN_DEPTH_CM = 360;
const DEFAULT_ROOM_WIDTH_CM = 320;
const DEFAULT_ROOM_DEPTH_CM = 280;

/** 場景 z → 世界 z。與 scene_viewer.js 的 sceneToWorldPosition 是同一個約定。 */
export function sceneToWorldZCm(sceneZCm) {
  return -Number(sceneZCm || 0);
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function finiteTriplet(value) {
  return Array.isArray(value)
    && value.length === 3
    && value.every((item) => Number.isFinite(Number(item)));
}

function pointOnSegment(point, start, end, tolerance = 0.01) {
  const cross = (point.y - start.y) * (end.x - start.x)
    - (point.x - start.x) * (end.y - start.y);
  if (Math.abs(cross) > tolerance) return false;
  const dot = (point.x - start.x) * (end.x - start.x)
    + (point.y - start.y) * (end.y - start.y);
  if (dot < -tolerance) return false;
  const lengthSquared = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
  return dot <= lengthSquared + tolerance;
}

function pointInPolygon(point, polygon) {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const start = polygon[previous];
    const end = polygon[index];
    if (pointOnSegment(point, start, end)) return true;
    const crosses = (end.y > point.y) !== (start.y > point.y)
      && point.x < ((start.x - end.x) * (point.y - end.y)) / (start.y - end.y) + end.x;
    if (crosses) inside = !inside;
  }
  return inside;
}

function distanceToSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx ** 2 + dy ** 2;
  if (!lengthSquared) return Math.hypot(point.x - start.x, point.y - start.y);
  const ratio = Math.max(0, Math.min(1,
    ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return Math.hypot(point.x - (start.x + ratio * dx), point.y - (start.y + ratio * dy));
}

export function validateRoomCamera(camera, room, floorplan = {}) {
  if (!camera || camera.camera_type !== "perspective") {
    return { valid: false, code: "camera_requires_perspective" };
  }
  if (!finiteTriplet(camera.position_cm) || !finiteTriplet(camera.target_cm)) {
    return { valid: false, code: "camera_coordinates_invalid" };
  }
  const [positionX, , positionZ] = camera.position_cm.map(Number);
  const [targetX, , targetZ] = camera.target_cm.map(Number);
  const viewingDistance = Math.hypot(positionX - targetX, positionZ - targetZ);
  if (viewingDistance < 40) {
    return { valid: false, code: "camera_distance_too_short" };
  }

  const polygon = (Array.isArray(room?.polygon_cm) ? room.polygon_cm : [])
    .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (polygon.length < 3) return { valid: true, code: "" };

  const planWidthCm = Number(floorplan?.width_cm) || DEFAULT_PLAN_WIDTH_CM;
  const planDepthCm = Number(floorplan?.depth_cm) || DEFAULT_PLAN_DEPTH_CM;
  const worldToPlan = ([x, , z]) => ({
    x: Number(x) + planWidthCm / 2,
    y: planDepthCm / 2 - Number(z),
  });
  const position = worldToPlan(camera.position_cm);
  const target = worldToPlan(camera.target_cm);
  if (!pointInPolygon(target, polygon)) {
    return { valid: false, code: "camera_target_outside_room" };
  }
  if (!pointInPolygon(position, polygon)) {
    return { valid: false, code: "camera_position_outside_room" };
  }
  const wallClearanceCm = Math.min(...polygon.map((start, index) =>
    distanceToSegment(position, start, polygon[(index + 1) % polygon.length])));
  if (wallClearanceCm < 8) {
    return { valid: false, code: "camera_too_close_to_wall" };
  }
  return { valid: true, code: "" };
}

export function roomCameraSuggestion(room, floorplan = {}) {
  const polygon = Array.isArray(room?.polygon_cm) ? room.polygon_cm : [];
  const planWidthCm = Number(floorplan?.width_cm) || DEFAULT_PLAN_WIDTH_CM;
  const planDepthCm = Number(floorplan?.depth_cm) || DEFAULT_PLAN_DEPTH_CM;
  const xs = polygon.map((point) => Number(point.x));
  const zs = polygon.map((point) => Number(point.y));

  const centerXCm = average(xs) - planWidthCm / 2;
  const sceneCenterZCm = average(zs) - planDepthCm / 2;
  const widthCm = xs.length ? Math.max(...xs) - Math.min(...xs) : DEFAULT_ROOM_WIDTH_CM;
  const depthCm = zs.length ? Math.max(...zs) - Math.min(...zs) : DEFAULT_ROOM_DEPTH_CM;
  const worldCenterZCm = sceneToWorldZCm(sceneCenterZCm);

  return {
    camera_type: "perspective",
    view_mode: "orbit",
    preset: "room",
    position_cm: [centerXCm + widthCm * 0.28, 145, worldCenterZCm + depthCm * 0.28],
    target_cm: [centerXCm, 82, worldCenterZCm],
    up: [0, 1, 0],
    fov_deg: 58,
    zoom: 1,
  };
}
