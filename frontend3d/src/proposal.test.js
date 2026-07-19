import assert from 'node:assert/strict'
import test from 'node:test'

import {
  flattenStyleCards,
  isUserSelectedFurniture,
  viewpointConfirmationPayload,
} from './proposal.js'

test('viewpoint confirmation keeps the camera contract in centimetres', () => {
  const payload = viewpointConfirmationPayload({
    position_cm: { x: 100, y: 220, z: 350 },
    target_cm: { x: 0, y: 100, z: 0 },
    fov_deg: 45,
  }, 7)
  assert.deepEqual(payload, {
    expected_revision: 7,
    user_reviewed: true,
    projection: 'perspective',
    position_cm: { x: 100, y: 220, z: 350 },
    target_cm: { x: 0, y: 100, z: 0 },
    fov_deg: 45,
  })
})

test('style cards flatten to 18 selectable variants while retaining style ids', () => {
  const cards = flattenStyleCards([
    { style_id: 'scandinavian', style_name_zh: '北歐風', cards: [{ card_id: 'scandinavian_1' }] },
    { style_id: 'japanese', style_name_zh: '日式', cards: [{ card_id: 'japanese_1' }] },
  ])
  assert.deepEqual(cards.map((card) => [card.card_id, card.style_id]), [
    ['scandinavian_1', 'scandinavian'],
    ['japanese_1', 'japanese'],
  ])
})

test('only explicit furniture choices are protected from palette replacement', () => {
  assert.equal(isUserSelectedFurniture({ selection_source: 'user' }), true)
  assert.equal(isUserSelectedFurniture({ userRequired: true }), true)
  assert.equal(isUserSelectedFurniture({ selection_source: 'local_rules' }), false)
  assert.equal(isUserSelectedFurniture({ selection_source: 'style_card' }), false)
})
