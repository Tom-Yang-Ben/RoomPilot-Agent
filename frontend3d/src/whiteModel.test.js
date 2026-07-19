import test from 'node:test'
import assert from 'node:assert/strict'

import {
  whiteModelConfirmationPayload,
  whiteModelDiagnostics,
} from './whiteModel.js'


test('white model is ready only when every expected neutral geometry is visible', () => {
  const items = [{ id: 'sofa-1' }, { id: 'table-1' }]
  const incomplete = whiteModelDiagnostics(items, ['sofa-1'])
  assert.equal(incomplete.ready, false)
  assert.deepEqual(incomplete.missingInstanceIds, ['table-1'])
  assert.throws(() => whiteModelConfirmationPayload(incomplete, 4), /不能確認/)

  const ready = whiteModelDiagnostics(items, ['table-1', 'sofa-1', 'unknown'])
  assert.equal(ready.ready, true)
  assert.equal(ready.visibleFurnitureCount, 2)
  assert.deepEqual(whiteModelConfirmationPayload(ready, 4), {
    expected_revision: 4,
    user_reviewed: true,
    renderer: 'neutral_geometry',
    visible_instance_ids: ['table-1', 'sofa-1'],
  })
})


test('an empty pure-structure white model can still be confirmed', () => {
  const diagnostics = whiteModelDiagnostics([], [])
  assert.equal(diagnostics.ready, true)
  assert.equal(diagnostics.expectedFurnitureCount, 0)
})
