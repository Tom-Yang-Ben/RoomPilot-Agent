/**
 * 辨識複核（`spatial_report.review_items`）的前端消費端。
 *
 * 後端逐房自我評分後產出「這幾間的辨識需要人工複核」清單，理由值以
 * `backend/floorplan/vision/spatial_report.py` 為準；新增理由而未補標籤時，
 * `tests/test_recognition_review_wiring.py` 會紅。
 *
 * 「已複核」刻意不另設狀態欄位：被標記的房間經使用者確認（含改名後確認）
 * 即視為已複核；房間被刪除、合併或切割（id 消失）也算，因為那本身就是
 * 人工介入。一鍵確認會跳過被標記的房間，避免訊號被整批略過。
 */

export const REVIEW_REASON_LABELS = Object.freeze({
  room_label_icon_evidence_conflict:
    "房名與家具圖示證據衝突：請確認空間名稱是否正確，必要時直接改選。",
  room_geometry_low_confidence:
    "房間範圍辨識信心不足：請核對框線與長寬是否符合原圖。",
  irregular_room_detailed_geometry_required:
    "形狀不規則：請逐牆確認範圍，必要時拖曳節點調整。",
  room_boundary_unresolved:
    "無法解析房間邊界：請手動框選這個空間的範圍。",
});

const FALLBACK_LABEL = "此項辨識需要人工確認。";

export function reviewReasonLabel(reason) {
  return REVIEW_REASON_LABELS[reason] || FALLBACK_LABEL;
}

export function reviewItemsFromAnalysis(analysis) {
  const items = analysis?.spatial_report?.review_items;
  if (!Array.isArray(items)) return [];
  return items.filter(
    (item) => item && item.room_id != null && typeof item.reason === "string",
  );
}

/**
 * 尚未複核的房間：review item 指到的房間仍存在且未確認。
 * 回傳 [{ room, reasons }]，reasons 已去重並保持後端輸出順序。
 */
export function unresolvedReviewRooms(items, rooms) {
  const roomsById = new Map(
    (rooms || [])
      .filter((room) => room && room.id != null)
      .map((room) => [String(room.id), room]),
  );
  const reasonsByRoom = new Map();
  for (const item of items || []) {
    const room = roomsById.get(String(item.room_id));
    if (!room || room.confirmed === true) continue;
    const key = String(item.room_id);
    if (!reasonsByRoom.has(key)) reasonsByRoom.set(key, { room, reasons: [] });
    const entry = reasonsByRoom.get(key);
    if (!entry.reasons.includes(item.reason)) entry.reasons.push(item.reason);
  }
  return [...reasonsByRoom.values()];
}
