import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clientPointToLayout,
  layoutConfirmationPayload,
  layoutObjectsToThreeItems,
  layoutValidationPayload,
  layoutView,
  moveLayoutObject,
  rotateLayoutObject,
} from './layout2d.js'
import {
  analyzeServerLayout,
  confirmServerLayout,
  validateServerLayout,
} from './project.js'

const object = {
  instance_id: 'room-a-1-sofa',
  furniture_id: 'sofa-id',
  name_zh_raw: '沙發',
  normalized_type: 'fabric-sofa',
  model_url: '/api/furniture/sofa-id/model',
  primary_style: 'scandinavian',
  placement_room_id: 'room-a',
  user_required: true,
  selection_source: 'user',
  mobility: 'movable',
  size_cm: { width: 200, depth: 90, height: 80 },
  footprint_cm: { width: 200, depth: 90 },
  position_cm: { x: 120, z: -80 },
  rotation_y_deg: 0,
  position_locked: false,
  placement_failed: false,
  placement_reason: null,
}

test('layout pointer mapping and edits keep the centimetre contract', () => {
  const view = layoutView({ bbox: { minx: -4, minz: -3, maxx: 4, maxz: 3 } })
  const point = clientPointToLayout(
    { x: 400, y: 300 },
    { left: 0, top: 0, width: 800, height: 600 },
    view,
  )
  assert.ok(Math.abs(point.x_cm) < 0.001)
  assert.ok(Math.abs(point.z_cm) < 0.001)

  const moved = moveLayoutObject([object], object.instance_id, { x_cm: 75, z_cm: -25 })
  assert.deepEqual(moved[0].position_cm, { x: 75, z: -25 })
  assert.equal(moved[0].position_locked, true)
  const rotated = rotateLayoutObject(moved, object.instance_id)
  assert.equal(rotated[0].rotation_y_deg, 90)
  assert.deepEqual(rotated[0].footprint_cm, { width: 90, depth: 200 })
})

test('validation and confirmation carry the full project-scoped proposal', () => {
  const validation = layoutValidationPayload([object], object.instance_id, 7)
  assert.equal(validation.expected_revision, 7)
  assert.equal(validation.item.instance_id, object.instance_id)
  assert.deepEqual(validation.others, [])

  const confirmation = layoutConfirmationPayload({
    source: 'openrouter',
    openrouter: { requested: true, sent: true, status: 'suggested', model: 'mock' },
  }, [object], 7)
  assert.equal(confirmation.user_reviewed, true)
  assert.equal(confirmation.proposal_source, 'openrouter')
  assert.equal(confirmation.scene_objects[0].furniture_id, 'sofa-id')
})

test('confirmed layout objects map from plan centimetres into the R3F world', () => {
  const items = layoutObjectsToThreeItems([object])
  assert.deepEqual(items[0], {
    id: object.instance_id,
    file: object.model_url,
    modelUrl: object.model_url,
    furnitureId: object.furniture_id,
    name: '沙發',
    normalizedType: object.normalized_type,
    sizeCm: object.size_cm,
    placementRoomId: object.placement_room_id,
    userRequired: true,
    selectionSource: 'user',
    userSelectedModel: true,
    x: 1.2,
    z: 0.8,
    yaw: 0,
    autoLayout: true,
    renderState: 'white_model',
  })

  const withoutModel = layoutObjectsToThreeItems([{ ...object, instance_id: 'no-glb', model_url: null }])
  assert.equal(withoutModel.length, 1)
  assert.equal(withoutModel[0].file, null)
  assert.deepEqual(withoutModel[0].sizeCm, object.size_cm)
})

test('layout API clients use analyze, validate and confirm endpoints separately', async () => {
  const calls = []
  const fetchImpl = async (path, options) => {
    calls.push({ path, options })
    return { ok: true, status: 200, json: async () => ({ ok: true }) }
  }
  await analyzeServerLayout('project 1', { expected_revision: 3, allow_openrouter: false }, fetchImpl)
  await validateServerLayout('project 1', { expected_revision: 3, item: object, others: [] }, fetchImpl)
  await confirmServerLayout('project 1', { expected_revision: 3, user_reviewed: true, scene_objects: [object] }, fetchImpl)
  assert.deepEqual(calls.map((call) => call.path), [
    '/api/projects/project%201/layout-2d/analyze',
    '/api/projects/project%201/layout-2d/validate',
    '/api/projects/project%201/layout-2d/confirm',
  ])
  assert.ok(calls.every((call) => call.options.method === 'POST'))
})
