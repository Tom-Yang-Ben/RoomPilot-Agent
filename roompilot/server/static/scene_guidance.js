export const ROOM_LABELS = Object.freeze({
  bedroom: "臥室",
  bathroom: "浴廁",
  kitchen: "廚房",
  dining_room: "餐廳",
  living_room: "客廳",
  balcony: "陽台",
  workspace: "工作空間",
});

const REVIEW_REASON_LABELS = Object.freeze({
  room_boundary_unresolved: "房間邊界尚未封閉",
  room_geometry_low_confidence: "房間尺寸信心不足",
  irregular_room_detailed_geometry_required: "不規則房間需要逐牆尺寸與可用區域確認",
});

const EVIDENCE_KIND_LABELS = Object.freeze({
  ocr_room_label: "圖面房名文字",
  inner_wall_boundary: "房間內牆邊界",
  column_geometry: "樑柱幾何",
  wall_geometry: "牆體幾何",
});

export function localizeEvidence(evidence = []) {
  return evidence.map((item) => ({
    ...structuredClone(item),
    displayLabel: EVIDENCE_KIND_LABELS[item.kind] || "圖面辨識證據",
  }));
}

export function buildFloorplanConfirmationCorrections(analysis = {}, scaleCm) {
  const distanceM = Number(scaleCm) / 100;
  const originalScale = analysis.scale || {};
  let pixelDistance = Number(originalScale.pixel_distance);
  if (!(pixelDistance > 0)) {
    const originalDistanceM = Number(originalScale.distance_m);
    const originalMPerPx = Number(originalScale.m_per_px);
    if (originalDistanceM > 0 && originalMPerPx > 0) {
      pixelDistance = originalDistanceM / originalMPerPx;
    }
  }
  if (!(distanceM > 0) || !(pixelDistance > 0)) {
    throw new Error("scale_reference_required");
  }
  return {
    walls: structuredClone(analysis.walls || []),
    doors: structuredClone(analysis.doors || []),
    windows: structuredClone(analysis.windows || []),
    scale: {
      ...structuredClone(originalScale),
      distance_m: distanceM,
      pixel_distance: pixelDistance,
      m_per_px: distanceM / pixelDistance,
      source: "manual_confirmation",
      confidence: 1,
    },
  };
}

function dimensionLabel(room) {
  const dimensions = room.inner_dimensions_m;
  const area = Number(room.net_area_m2);
  if (!dimensions || !Number.isFinite(area)) return "尺寸待局部修正";
  return `${Number(dimensions.width).toFixed(2)} × ${Number(dimensions.depth).toFixed(2)} m｜${area.toFixed(2)} m²`;
}

export function buildRecognitionPresentation(analysis = {}) {
  const report = analysis.spatial_report || {};
  const pendingByRoom = new Map(
    (report.review_items || [])
      .filter((item) => item.status !== "resolved")
      .map((item) => [item.room_id, item]),
  );
  const rooms = (report.rooms || []).map((room) => ({
    roomId: room.room_id,
    roomType: room.room_type,
    label: room.label || ROOM_LABELS[room.room_type] || room.room_type,
    dimensionLabel: dimensionLabel(room),
    confidence: room.confidence,
    polygonM: room.polygon_m,
    needsReview: pendingByRoom.has(room.room_id),
    evidence: room.evidence || [],
  }));
  const correctionPrompts = (report.review_items || [])
    .filter((item) => item.status !== "resolved")
    .map((item) => ({
      findingId: item.id,
      roomId: item.room_id,
      reason: item.reason,
      reasonLabel: REVIEW_REASON_LABELS[item.reason] || "此項辨識需要局部修正",
      maxChoices: 3,
    }));
  return {
    summary: { ...(report.room_counts || {}) },
    summaryItems: Object.entries(report.room_counts || {}).map(([type, count]) => ({
      type,
      label: ROOM_LABELS[type] || type,
      count,
    })),
    rooms,
    correctionPrompts,
    openingSummary: {
      doors: (analysis.doors || []).length,
      windows: (analysis.windows || []).length,
    },
  };
}

export function buildExplainableRecommendation(input = {}) {
  const choices = input.choices || [];
  if (!input.recommendation || !(input.evidence || []).length || !(input.rules || []).length) {
    throw new Error("recommendation_evidence_required");
  }
  if (!(input.tradeoffs || []).length || !input.confidence) {
    throw new Error("recommendation_limits_required");
  }
  if (choices.length > 3 || choices.filter((choice) => choice.recommended === true).length !== 1) {
    throw new Error("recommendation_choices_invalid");
  }
  return {
    recommendation: input.recommendation,
    evidence: localizeEvidence(input.evidence),
    customerNeeds: structuredClone(input.customerNeeds || []),
    rules: structuredClone(input.rules),
    tradeoffs: structuredClone(input.tradeoffs),
    assumptions: structuredClone(input.assumptions || []),
    confidence: input.confidence,
    choices: structuredClone(choices),
    status: input.status || "concept_recommendation",
  };
}
