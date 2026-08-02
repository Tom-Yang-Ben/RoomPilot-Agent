/**
 * 檯面小物的宿主吸附（2026-08-03 Ben 拍板「檯面吸附最小模型」）。
 *
 * 花瓶、抱枕等 TABLETOP 品項不佔垂直空間、不算碰撞，但要「站在哪件家具
 * 檯面上」才有意義。這裡負責：型別分類、宿主相容表、放下時的宿主命中
 * 判定與 3D 呈現高度。
 *
 * 相容表必須與 backend/catalog/style_db.py 的 TABLETOP_HOST_TYPES 一致，
 * tests/test_tabletop_hosts_frontend.py 做奇偶檢查；改一邊沒改另一邊會紅。
 * 平面包含的權威判定在 backend/engine/geometry.rests_within_host——這裡的
 * 命中測試只是吸附用的前端鏡像，最終合法性仍由伺服器說了算。
 */

export const TABLETOP_TYPES = Object.freeze([
  "vase",
  "decoration",
  "pillow-cushion",
  "storage-boxes-basket",
  "sheepskins-cowhide",
]);

const SURFACE_HOSTS = Object.freeze([
  "dining-table",
  "coffee-table",
  "sideboard",
  "bedside-table",
  "chests-of-drawer",
  "tv-bench",
  "tv-media-furniture",
  "desk",
  "bookcase",
  "shelving-unit",
  "cabinet-cupboard",
  "table",
  "bar-table",
]);

const SEATING_HOSTS = Object.freeze([
  "sofa",
  "fabric-sofa",
  "leather-sofa",
  "modular-sofa",
  "sofa-bed",
  "armchair",
  "bed",
  "stool-bench",
]);

export const TABLETOP_HOST_TYPES = Object.freeze({
  vase: SURFACE_HOSTS,
  decoration: Object.freeze([...SURFACE_HOSTS, "display-cabinet"]),
  "storage-boxes-basket": Object.freeze([
    "bookcase",
    "shelving-unit",
    "storage-solution-system",
    "storage-furniture",
    "cabinet-cupboard",
    "chests-of-drawer",
    "tv-bench",
    "wardrobe",
    "pax-wardrobe",
  ]),
  "pillow-cushion": SEATING_HOSTS,
  "sheepskins-cowhide": SEATING_HOSTS,
});

const SEATING_HOST_SET = new Set(SEATING_HOSTS);

export function isTabletopType(type) {
  return TABLETOP_TYPES.includes(String(type || "").trim().toLowerCase());
}

export function allowedHostTypesFor(tabletopType) {
  return TABLETOP_HOST_TYPES[String(tabletopType || "").trim().toLowerCase()] || [];
}

/**
 * 小物在 3D 的呈現高度＝宿主表面高度。
 * 硬檯面就是宿主全高；座面與床取半高並夾在 35–50cm（沙發全高 80 但坐面
 * 約 45——抱枕該在坐面不是浮在椅背頂）。
 */
export function hostSurfaceHeightCm(hostType, hostHeightCm) {
  const height = Math.max(0, Number(hostHeightCm) || 0);
  if (SEATING_HOST_SET.has(String(hostType || "").trim().toLowerCase())) {
    return Math.min(50, Math.max(35, height * 0.5)) || 0;
  }
  return height;
}

/** 點是否落在（可能旋轉的）家具腳印內，容差公分數與後端判定一致取 2。 */
export function pointWithinItemFootprint(x, y, item, toleranceCm = 2) {
  const radians = ((Number(item?.rotationDeg) || 0) * Math.PI) / 180;
  const dx = Number(x) - (Number(item?.xCm) || 0);
  const dy = Number(y) - (Number(item?.yCm) || 0);
  // 轉進宿主的局部座標再比半寬半深。
  const localX = dx * Math.cos(radians) + dy * Math.sin(radians);
  const localY = -dx * Math.sin(radians) + dy * Math.cos(radians);
  const halfW = (Number(item?.widthCm) || 0) / 2 + toleranceCm;
  const halfD = (Number(item?.depthCm) || 0) / 2 + toleranceCm;
  return Math.abs(localX) <= halfW && Math.abs(localY) <= halfD;
}

/**
 * 在同房家具中找放下點命中的相容宿主。
 * 多個命中時取腳印最小的——花瓶放在「茶几壓著地毯」的位置該吸茶几。
 */
export function findHostAt(x, y, tabletopType, candidates) {
  const allowed = new Set(allowedHostTypesFor(tabletopType));
  if (!allowed.size) return null;
  const hits = (candidates || []).filter((item) =>
    item
    && allowed.has(String(item.type || "").trim().toLowerCase())
    && pointWithinItemFootprint(x, y, item));
  if (!hits.length) return null;
  return hits.reduce((best, item) => {
    const area = (Number(item.widthCm) || 0) * (Number(item.depthCm) || 0);
    const bestArea = (Number(best.widthCm) || 0) * (Number(best.depthCm) || 0);
    return area < bestArea ? item : best;
  });
}
