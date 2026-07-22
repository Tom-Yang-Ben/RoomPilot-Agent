import assert from 'node:assert/strict'
import test from 'node:test'

import {
  addDraftSegment,
  calibrationPayload,
  clientPointToViewBox,
  confirmationPayload,
  makeFloorplanReviewDraft,
  removeDraftSegment,
  snapPointToWall,
  updateDraftRoomType,
} from './floorplanReview.js'

function floorplan() {
  return {
    bbox: { minx: -3, minz: -2, maxx: 3, maxz: 2 },
    wall_polys: [],
    room_regions: [{
      room_id: 'room-a',
      exterior: [[-3, -2], [3, -2], [3, 2], [-3, 2], [-3, -2]],
      holes: [],
      value: 'living_room',
      label_zh: '客廳',
    }],
    doors: [{ x1: -1, z1: -2, x2: 0, z2: -2 }],
    windows: [],
  }
}

test('review draft accepts old value field and normalizes the editable contract', () => {
  const draft = makeFloorplanReviewDraft(floorplan())

  assert.equal(draft.rooms[0].room_type, 'living_room')
  assert.equal(draft.doors.length, 1)
  assert.equal(draft.room_type_options.at(-1).value, 'other')
})

test('room labels and door/window suggestions can be corrected before confirmation', () => {
  let draft = makeFloorplanReviewDraft(floorplan())
  draft = updateDraftRoomType(draft, 'room-a', 'bedroom')
  draft = addDraftSegment(draft, 'windows', { x: 1, z: 2 }, { x: 2, z: 2 })
  draft = addDraftSegment(draft, 'doors', { x: 0, z: 0 }, { x: 0.01, z: 0 })
  draft = removeDraftSegment(draft, 'doors', 0)

  assert.equal(draft.rooms[0].room_type, 'bedroom')
  assert.equal(draft.windows.length, 1)
  assert.equal(draft.doors.length, 0)
})

test('confirmation payload contains only stable ids, chosen types and metre segments', () => {
  const draft = updateDraftRoomType(
    makeFloorplanReviewDraft(floorplan()),
    'room-a',
    'kitchen',
  )

  assert.deepEqual(confirmationPayload(draft, 7), {
    expected_revision: 7,
    rooms: [{ room_id: 'room-a', room_type: 'kitchen' }],
    doors: [{ x1: -1, z1: -2, x2: 0, z2: -2 }],
    windows: [],
  })
})

test('calibration payload converts the recognized metre geometry to centimetres', () => {
  assert.deepEqual(calibrationPayload({
    start: { x: -1.25, z: 0.5 },
    end: { x: 1.75, z: 0.5 },
  }, 420, 8), {
    expected_revision: 8,
    reference_cm: { x1_cm: -125, z1_cm: 50, x2_cm: 175, z2_cm: 50 },
    actual_length_cm: 420,
  })
})

test('scale endpoints snap to the nearest recognized wall line', () => {
  const draft = makeFloorplanReviewDraft({
    ...floorplan(),
    wall_segments: [{
      start: { x: -2, z: 1 },
      end: { x: 2, z: 1 },
    }],
  })

  const snapped = snapPointToWall(draft, { x: 0.75, z: 1.08 }, 0.1)

  assert.equal(snapped.x, 0.75)
  assert.equal(snapped.z, 1)
  assert.equal(snapped.wall_index, 0)
  assert.ok(snapped.distance_m < 0.1)
  assert.equal(snapPointToWall(draft, { x: 0.75, z: 1.5 }, 0.1), null)
})

test('second scale endpoint is constrained to the wall selected by the first endpoint', () => {
  const draft = makeFloorplanReviewDraft({
    ...floorplan(),
    wall_segments: [
      { start: { x: -2, z: 1 }, end: { x: 2, z: 1 } },
      { start: { x: 1, z: -1 }, end: { x: 1, z: 2 } },
    ],
  })
  const start = snapPointToWall(draft, { x: 0.7, z: 1.04 }, 0.1)

  const unconstrained = snapPointToWall(draft, { x: 1.02, z: 1.7 }, 0.1)
  const constrained = snapPointToWall(draft, { x: 1.02, z: 1.7 }, 1, start.wall_index)

  assert.equal(unconstrained.wall_index, 1)
  assert.equal(constrained.wall_index, 0)
  assert.equal(constrained.z, 1)
  assert.equal(constrained.x, 1.02)
})

test('legacy centimetre wall segments are normalized against the metre bbox', () => {
  const draft = makeFloorplanReviewDraft({
    ...floorplan(),
    wall_segments: [{
      start: { x: -300, z: -200 },
      end: { x: 300, z: -200 },
    }],
  })

  assert.deepEqual(draft.wall_segments[0], { x1: -3, z1: -2, x2: 3, z2: -2 })
  const snapped = snapPointToWall(draft, { x: 1, z: -1.92 }, 0.1)
  assert.equal(snapped.x, 1)
  assert.equal(snapped.z, -2)
  assert.ok(snapped.distance_m < 0.1)
})

test('pointer mapping removes SVG letterbox padding before wall snapping', () => {
  assert.deepEqual(clientPointToViewBox(
    { x: 250, y: 250 },
    { left: 0, top: 0, width: 500, height: 500 },
    { minx: -5, minz: -2.5, width: 10, depth: 5 },
  ), { x: 0, z: 0 })
  assert.deepEqual(clientPointToViewBox(
    { x: 0, y: 125 },
    { left: 0, top: 0, width: 500, height: 500 },
    { minx: -5, minz: -2.5, width: 10, depth: 5 },
  ), { x: -5, z: -2.5 })
})
