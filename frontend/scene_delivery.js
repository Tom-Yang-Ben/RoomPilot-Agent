import { VIEW_MODES } from "./scene_view_modes.js";

export function buildDeliveryManifest(scene, { hasConfirmedDxf = false, costReport = null } = {}) {
  let knownSubtotalTwd = 0;
  const pendingEstimateIds = [];
  const items = (scene.scene_objects || []).map((item) => {
    const priceTwd = Number(item.price_twd ?? item.price_ntd);
    const hasKnownPrice = Number.isFinite(priceTwd) && priceTwd > 0;
    if (hasKnownPrice) knownSubtotalTwd += priceTwd;
    else pendingEstimateIds.push(item.furniture_id);
    return {
      furnitureId: item.furniture_id,
      name: item.name_zh_raw || item.normalized_type || item.furniture_id,
      priceTwd: hasKnownPrice ? priceTwd : null,
      priceStatus: hasKnownPrice ? "known" : "pending_estimate",
    };
  });
  const sourceIds = [...new Set((costReport?.items || []).flatMap((item) => item.source_ids || []))];
  return {
    viewModes: [...VIEW_MODES],
    outputs: ["png", "glb", ...(hasConfirmedDxf ? ["dxf"] : []), "pdf"],
    bom: { items, knownSubtotalTwd, pendingEstimateIds },
    engineeringEstimate: {
      status: costReport?.status || "not_estimated",
      totalsTwd: costReport?.totals_twd || { low: 0, base: 0, high: 0 },
      sourceIds,
      needsQuoteIds: (costReport?.needs_quote || []).map((item) => item.id),
      disclaimerZh: costReport?.disclaimer_zh || "網路公開行情概算；施工前須現場丈量並取得正式報價。",
    },
    privacy: {
      projectOnly: true,
      usedForTraining: false,
      crossProjectReuse: false,
    },
    usesGenerativeImageApi: false,
  };
}
