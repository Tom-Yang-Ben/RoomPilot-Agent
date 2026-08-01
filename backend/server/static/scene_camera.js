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
