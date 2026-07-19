export function viewpointConfirmationPayload(viewpoint, expectedRevision) {
  if (!viewpoint?.position_cm || !viewpoint?.target_cm) {
    throw new Error('找不到目前攝影機視角。')
  }
  return {
    expected_revision: expectedRevision,
    user_reviewed: true,
    projection: 'perspective',
    position_cm: viewpoint.position_cm,
    target_cm: viewpoint.target_cm,
    fov_deg: Number(viewpoint.fov_deg),
  }
}

export function flattenStyleCards(styles = []) {
  return styles.flatMap((style) => (style.cards || []).map((card) => ({
    ...card,
    style_id: style.scene_style_id || style.style_id,
    style_name_zh: style.style_name_zh,
  })))
}

export function isUserSelectedFurniture(item = {}) {
  return Boolean(
    item.userRequired
    || item.user_required
    || item.selectionSource === 'user'
    || item.selection_source === 'user'
    || item.userSelectedModel
    || item.user_selected_model
  )
}
