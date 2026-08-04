// 平面幾何純函式的單一實作。
//
// 這裡刻意零依賴——不 import 任何模組，不碰 DOM、state、THREE——所以 scene 那條
// 模組鏈與 engineering.js 這種獨立頁面 bundle 都能引用，而不會因為共用一個
// point-in-polygon 就被綁進對方的相依圖。
//
// 座標一律是 { x, y } 平面座標。呼叫端自己的 schema——engineering 的
// { x_cm, y_cm }、viewer 的世界 { x, z }——必須在邊界轉好再進來。核心不認欄位
// 別名：每多接受一組別名，就多一組要維護、要測試的組合，而轉換本來就該發生在
// 知道單位與座標框的那一層。

/** 鞋帶公式。取絕對值，所以不帶繞向；需要判順逆時針的話另開 signedPolygonArea。 */
export function polygonArea(points) {
  if (!points?.length) return 0;
  return Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % points.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0) / 2);
}

/**
 * 點是否落在線段上。
 *
 * tolerance 是下在**外積**上的，不是垂距——等效垂距會隨邊長縮放（200cm 的牆
 * 約為 tolerance/200）。這是 scene_camera.js 原本的行為，統一時原樣保留。
 */
export function pointOnSegment(point, start, end, tolerance = 0.01) {
  const cross = (point.y - start.y) * (end.x - start.x)
    - (point.x - start.x) * (end.y - start.y);
  if (Math.abs(cross) > tolerance) return false;
  const dot = (point.x - start.x) * (end.x - start.x)
    + (point.y - start.y) * (end.y - start.y);
  if (dot < -tolerance) return false;
  const lengthSquared = (end.x - start.x) ** 2 + (end.y - start.y) ** 2;
  return dot <= lengthSquared + tolerance;
}

/**
 * 射線法。`includeBoundary` 決定落在邊上的點算不算室內。
 *
 * 預設 false 是標準射線法，邊界未定義——這是 scene_plan_geometry 與 engineering
 * 原本的行為。scene_camera 的逐房鏡頭驗證需要 true：target 落在牆線上要算室內，
 * 否則貼牆的鏡頭會整批被判 camera_target_outside_room。
 *
 * `|| 1e-9` 的除零保護實際上取不到——`crosses` 的第一項在兩端 y 相等時就是
 * false，`&&` 會短路。保留是因為三份原始實作有兩份帶著它，拿掉沒好處。
 */
export function pointInPolygon(point, polygon, options = {}) {
  const { includeBoundary = false, boundaryTolerance = 0.01 } = options;
  if (!point || !Array.isArray(polygon) || polygon.length < 3) return false;
  const x = Number(point.x);
  const y = Number(point.y);
  let inside = false;
  for (
    let index = 0, previousIndex = polygon.length - 1;
    index < polygon.length;
    previousIndex = index, index += 1
  ) {
    const currentX = Number(polygon[index]?.x);
    const currentY = Number(polygon[index]?.y);
    const previousX = Number(polygon[previousIndex]?.x);
    const previousY = Number(polygon[previousIndex]?.y);
    if (includeBoundary && pointOnSegment(
      { x, y },
      { x: previousX, y: previousY },
      { x: currentX, y: currentY },
      boundaryTolerance,
    )) {
      return true;
    }
    const crosses = (currentY > y) !== (previousY > y)
      && x < (
        ((previousX - currentX) * (y - currentY))
        / ((previousY - currentY) || 1e-9)
        + currentX
      );
    if (crosses) inside = !inside;
  }
  return inside;
}

/**
 * 點到線段的最短距離。
 *
 * 退化守衛用 `<= 1e-9`（約 3e-5 的邊長）。scene_camera.js 原本寫 `!lengthSquared`，
 * 只擋長度剛好為 0 的邊；統一成前者對亞微米級的退化邊更穩，也是原本
 * scene_structure_geometry.js 的寫法。
 */
export function distanceToSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared <= 1e-9) return Math.hypot(point.x - start.x, point.y - start.y);
  const ratio = Math.max(0, Math.min(
    1,
    ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared,
  ));
  return Math.hypot(
    point.x - (start.x + ratio * dx),
    point.y - (start.y + ratio * dy),
  );
}
