export const ROOM_LABELS = Object.freeze({
  bedroom: "臥室",
  bathroom: "浴廁",
  kitchen: "廚房",
  living_room: "客廳",
  balcony: "陽台",
  storage: "書房／儲藏室",
  entryway: "玄關",
  hallway: "走道／動線",
  garage: "車庫",
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
  const distanceCm = Number(scaleCm);
  const originalScale = analysis.scale || {};
  let pixelDistance = Number(originalScale.pixel_distance);
  if (!(pixelDistance > 0)) {
    const originalDistanceCm = Number(originalScale.distance_cm);
    const originalCmPerPx = Number(originalScale.cm_per_px);
    if (originalDistanceCm > 0 && originalCmPerPx > 0) {
      pixelDistance = originalDistanceCm / originalCmPerPx;
    }
  }
  if (!(distanceCm > 0) || !(pixelDistance > 0)) {
    throw new Error("scale_reference_required");
  }
  return {
    walls: structuredClone(analysis.walls || []),
    doors: structuredClone(analysis.doors || []),
    windows: structuredClone(analysis.windows || []),
    scale: {
      ...structuredClone(originalScale),
      distance_cm: distanceCm,
      pixel_distance: pixelDistance,
      cm_per_px: distanceCm / pixelDistance,
      source: "manual_confirmation",
      confidence: 1,
    },
  };
}

function dimensionLabel(room) {
  const dimensions = room.inner_dimensions_cm;
  const area = Number(room.net_area_m2);
  if (!dimensions || !Number.isFinite(area)) return "尺寸待局部修正";
  return `${Number(dimensions.width).toFixed(0)} × ${Number(dimensions.depth).toFixed(0)} cm｜${area.toFixed(2)} m²`;
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
    polygonCm: room.polygon_cm,
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
