import assert from 'node:assert/strict'
import test from 'node:test'

import {
  makeRequirementsDraft,
  requirementsAnalyzePayload,
  requirementsConfirmationPayload,
  updateRequirementRoom,
  validateRequirementsDraft,
} from './requirements.js'

const rooms = [
  { room_id: 'room-a', room_type: 'living_room', label_zh: '客廳' },
  { room_id: 'room-b', room_type: 'bedroom', label_zh: '臥室' },
]

test('questionnaire draft is keyed by confirmed room id and carries room defaults', () => {
  const draft = makeRequirementsDraft(rooms)

  assert.equal(draft.style_id, 'scandinavian')
  assert.equal(draft.occupants.adults, 1)
  assert.deepEqual(
    draft.room_requirements.map((room) => [room.room_id, room.room_type, room.uses]),
    [
      ['room-a', 'living_room', ['family_gathering', 'relaxing']],
      ['room-b', 'bedroom', ['sleeping', 'clothing_storage']],
    ],
  )
  assert.equal(validateRequirementsDraft(draft), null)
})

test('default mode strips every hidden advanced answer from the API contract', () => {
  let draft = makeRequirementsDraft(rooms)
  draft = updateRequirementRoom(draft, 'room-a', {
    uses: ['watching_tv'],
    required_furniture_ids: ['fi-sofa'],
    special_materials: ['easy_cleaning'],
    special_notes: '不應送出',
  })
  draft.special_notes = '也不應送出'
  draft.allow_openrouter = true

  const payload = requirementsAnalyzePayload(draft, 7)

  assert.equal(payload.expected_revision, 7)
  assert.equal(payload.special_notes, '')
  assert.deepEqual(payload.room_requirements[0].uses, ['family_gathering', 'relaxing'])
  assert.deepEqual(payload.room_requirements[0].required_furniture_ids, [])
  assert.deepEqual(payload.room_requirements[0].special_materials, [])
  assert.equal(payload.room_requirements[0].special_notes, '')
  assert.equal(payload.allow_openrouter, true)
})

test('advanced mode preserves room answers and confirmation includes reviewed suggestion', () => {
  let draft = makeRequirementsDraft(rooms)
  draft = {
    ...draft,
    customization_mode: 'advanced',
    special_notes: '長者使用助行器',
    allow_openrouter: true,
  }
  draft = updateRequirementRoom(draft, 'room-b', {
    uses: ['sleeping'],
    special_materials: ['slip_resistant'],
    required_furniture_ids: ['fi-bed-1'],
  })
  const suggestion = {
    status: 'suggested',
    source: 'openrouter',
    model: 'mock/model',
    summary_zh: '已整理需求。',
    constraints: [],
    openrouter: { requested: true, sent: true, status: 'suggested' },
  }

  const analyzed = requirementsAnalyzePayload(draft, 8)
  const confirmed = requirementsConfirmationPayload(draft, 8, suggestion)

  assert.equal(analyzed.special_notes, '長者使用助行器')
  assert.deepEqual(analyzed.room_requirements[1].special_materials, ['slip_resistant'])
  assert.deepEqual(analyzed.room_requirements[1].required_furniture_ids, ['fi-bed-1'])
  assert.deepEqual(confirmed.suggestion, suggestion)
  assert.equal('allow_openrouter' in confirmed, false)
})

test('resident validation does not count pets as human occupants', () => {
  const draft = makeRequirementsDraft(rooms)
  draft.occupants = { adults: 0, children: 0, elderly: 0, pets: 2 }

  assert.equal(validateRequirementsDraft(draft), '至少需要一位居住者。')
})
