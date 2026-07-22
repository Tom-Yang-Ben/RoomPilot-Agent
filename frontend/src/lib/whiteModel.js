function uniqueStrings(values = []) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

export function whiteModelDiagnostics(items = [], visibleInstanceIds = []) {
  const expectedInstanceIds = uniqueStrings(items.map((item) => item.id))
  const expected = new Set(expectedInstanceIds)
  const visible = uniqueStrings(visibleInstanceIds).filter((id) => expected.has(id))
  const visibleSet = new Set(visible)
  const missingInstanceIds = expectedInstanceIds.filter((id) => !visibleSet.has(id))
  return {
    expectedInstanceIds,
    visibleInstanceIds: visible,
    missingInstanceIds,
    expectedFurnitureCount: expectedInstanceIds.length,
    visibleFurnitureCount: visible.length,
    ready: missingInstanceIds.length === 0,
  }
}

export function whiteModelConfirmationPayload(diagnostics, expectedRevision) {
  if (!diagnostics?.ready) throw new Error('仍有家具尚未顯示，不能確認 3D 白模。')
  return {
    expected_revision: expectedRevision,
    user_reviewed: true,
    renderer: 'neutral_geometry',
    visible_instance_ids: [...diagnostics.visibleInstanceIds],
  }
}
