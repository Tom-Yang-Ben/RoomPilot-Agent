// 逐房鏡頭建議。
//
// scene_json 的 polygon_cm 走場景座標，而 viewer 內部的世界座標 z 與場景 z 反向
// （scene_viewer.js 的 sceneToWorldPosition 對 z 取負）。setCameraState 收的是世界
// 座標——它與 getCameraState 對稱，存下來的鏡頭才能原樣還原——所以場景→世界的
// 翻面必須在這裡做完。少了這一步，每間房的鏡頭都會落在 x 軸鏡像的位置：廚房視角
// 照到床、臥室視角照到餐桌，第 8 步的逐房生圖輸入也整批是錯的。

import {
  distanceToSegment,
  pointInPolygon,
} from "./geometry_core.js?v=sha256-9f5b24aab5dd";

// 逐房鏡頭要的是「邊界算室內」：target 落在牆線上不能判成室外，否則貼牆的鏡頭
// 會整批變成 camera_target_outside_room。中立核心預設是標準射線法（邊界未定義），
// 所以這裡必須顯式開啟——見 tests/test_scene_room_camera.py 的兩支邊界測試。
const ROOM_CONTAINMENT = { includeBoundary: true };

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
  if (!pointInPolygon(target, polygon, ROOM_CONTAINMENT)) {
    return { valid: false, code: "camera_target_outside_room" };
  }
  if (!pointInPolygon(position, polygon, ROOM_CONTAINMENT)) {
    return { valid: false, code: "camera_position_outside_room" };
  }
  const wallClearanceCm = Math.min(...polygon.map((start, index) =>
    distanceToSegment(position, start, polygon[(index + 1) % polygon.length])));
  if (wallClearanceCm < 8) {
    return { valid: false, code: "camera_too_close_to_wall" };
  }
  return { valid: true, code: "" };
}

function polygonCentroid(polygon) {
  let doubleArea = 0;
  let centroidX = 0;
  let centroidY = 0;
  for (let index = 0; index < polygon.length; index += 1) {
    const start = polygon[index];
    const end = polygon[(index + 1) % polygon.length];
    const cross = start.x * end.y - end.x * start.y;
    doubleArea += cross;
    centroidX += (start.x + end.x) * cross;
    centroidY += (start.y + end.y) * cross;
  }
  if (Math.abs(doubleArea) < 1e-6) {
    return {
      x: average(polygon.map((point) => point.x)),
      y: average(polygon.map((point) => point.y)),
    };
  }
  return { x: centroidX / (3 * doubleArea), y: centroidY / (3 * doubleArea) };
}

export function clampRoomCamera(camera, room, floorplan = {}, wallClearanceCm = 12) {
  // 候選鏡頭以外接框比例推位置；窄房間（走道、陽台、L 型）會落在 8cm 淨距內
  // 或牆外，三個候選全滅、第 7 步逐房視角就此卡死（floor04 陽台實測）。這裡
  // 沿「鏡頭→目標」線段把 position 內插回第一個滿足淨距與 40cm 視距的取樣點
  // ——由遠而近掃，成立的第一點就是視距最大的合法點；target 不在房內時拉回
  // 多邊形質心。只動水平座標，鏡頭高度與俯角語意不變。整段掃不到合法點
  // （房間窄於兩倍淨距）時退回淨距最大的房內取樣點，最終合法性仍由
  // validateRoomCamera 裁決，這裡不放行任何未經驗證的鏡頭。
  const polygon = (Array.isArray(room?.polygon_cm) ? room.polygon_cm : [])
    .map((point) => ({ x: Number(point?.x), y: Number(point?.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (
    polygon.length < 3
    || !finiteTriplet(camera?.position_cm)
    || !finiteTriplet(camera?.target_cm)
  ) {
    return camera;
  }
  const planWidthCm = Number(floorplan?.width_cm) || DEFAULT_PLAN_WIDTH_CM;
  const planDepthCm = Number(floorplan?.depth_cm) || DEFAULT_PLAN_DEPTH_CM;
  const worldToPlan = ([x, , z]) => ({
    x: Number(x) + planWidthCm / 2,
    y: planDepthCm / 2 - Number(z),
  });
  let targetPlan = worldToPlan(camera.target_cm);
  if (!pointInPolygon(targetPlan, polygon, ROOM_CONTAINMENT)) {
    targetPlan = polygonCentroid(polygon);
  }
  const positionPlan = worldToPlan(camera.position_cm);
  const clearanceOf = (point) => Math.min(...polygon.map((start, index) =>
    distanceToSegment(point, start, polygon[(index + 1) % polygon.length])));
  let chosen = null;
  let fallback = null;
  let fallbackClearance = -Infinity;
  for (let t = 0; t <= 1.00001; t += 0.02) {
    const sample = {
      x: positionPlan.x + (targetPlan.x - positionPlan.x) * t,
      y: positionPlan.y + (targetPlan.y - positionPlan.y) * t,
    };
    if (!pointInPolygon(sample, polygon, ROOM_CONTAINMENT)) continue;
    const clearance = clearanceOf(sample);
    if (clearance > fallbackClearance) {
      fallbackClearance = clearance;
      fallback = sample;
    }
    const viewingDistance = Math.hypot(
      sample.x - targetPlan.x,
      sample.y - targetPlan.y,
    );
    if (clearance >= wallClearanceCm && viewingDistance >= 40) {
      chosen = sample;
      break;
    }
  }
  if (!chosen) {
    // 線段方向與窄軸垂直時（陽台的旋轉候選），「淨距 ≥ 門檻」與「視距 ≥ 40」
    // 在那條線上沒有交集。第二階段繞 target 掃射線：方向從原方位就近轉開、
    // 半徑由遠而近，第一個合法點就是保住最多視距、轉向最小的解——窄長房間
    // 的解落在長軸方向上。
    const bearing = Math.atan2(
      positionPlan.y - targetPlan.y,
      positionPlan.x - targetPlan.x,
    );
    const xs = polygon.map((point) => point.x);
    const ys = polygon.map((point) => point.y);
    const maxRadius = Math.hypot(
      Math.max(...xs) - Math.min(...xs),
      Math.max(...ys) - Math.min(...ys),
    );
    outer: for (const step of [0, 1, -1, 2, -2, 3, -3, 4]) {
      const angle = bearing + (step * Math.PI) / 4;
      for (let radius = maxRadius; radius >= 40; radius -= 4) {
        const sample = {
          x: targetPlan.x + Math.cos(angle) * radius,
          y: targetPlan.y + Math.sin(angle) * radius,
        };
        if (!pointInPolygon(sample, polygon, ROOM_CONTAINMENT)) continue;
        if (clearanceOf(sample) >= wallClearanceCm) {
          chosen = sample;
          break outer;
        }
      }
    }
  }
  const finalPlan = chosen || fallback;
  if (!finalPlan) return camera;
  return {
    ...camera,
    position_cm: [
      finalPlan.x - planWidthCm / 2,
      Number(camera.position_cm[1]),
      planDepthCm / 2 - finalPlan.y,
    ],
    target_cm: [
      targetPlan.x - planWidthCm / 2,
      Number(camera.target_cm[1]),
      planDepthCm / 2 - targetPlan.y,
    ],
  };
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
