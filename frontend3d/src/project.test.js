import assert from 'node:assert/strict'
import test from 'node:test'

import {
  PROJECT_CACHE_SCHEMA_VERSION,
  ProjectApiError,
  applyServerStyleCard,
  analyzeServerRequirements,
  analyzeServerFloorplan,
  cacheProject,
  calibrateServerFloorplan,
  confirmServerFloorplan,
  confirmServerRequirements,
  confirmServerWhiteModel,
  confirmServerViewpoint,
  createServerProject,
  createServerRender,
  listServerRenders,
  loadProjectCache,
  projectIdFromLocation,
  saveServerWorkflow,
  uploadServerFloorplan,
} from './project.js'

function memoryStorage() {
  const values = new Map()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  }
}

test('projectIdFromLocation reads the resumable project URL', () => {
  assert.equal(
    projectIdFromLocation({ href: 'http://localhost:5173/?project_id=abc123' }),
    'abc123',
  )
  assert.equal(projectIdFromLocation({ href: 'http://localhost:5173/' }), null)
})

test('project cache is namespaced per project and rejects old schemas', () => {
  const storage = memoryStorage()
  const project = { project_id: 'project-a', revision: 2, name: '住宅案' }
  assert.equal(cacheProject(project, { source: { kind: 'sample' } }, storage), true)
  assert.equal(loadProjectCache('project-a', storage).project.name, '住宅案')
  assert.equal(loadProjectCache('project-b', storage), null)

  const key = [...storage.values.keys()].find((candidate) => candidate.includes('project-cache'))
  const stale = JSON.parse(storage.getItem(key))
  storage.setItem(key, JSON.stringify({ ...stale, schemaVersion: PROJECT_CACHE_SCHEMA_VERSION - 1 }))
  assert.equal(loadProjectCache('project-a', storage), null)
})

test('quota fallback keeps metadata but drops placed furniture', () => {
  const storage = memoryStorage()
  const originalSet = storage.setItem
  let firstCacheWrite = true
  storage.setItem = (key, value) => {
    if (key.includes('project-cache') && firstCacheWrite) {
      firstCacheWrite = false
      throw new Error('quota exceeded')
    }
    originalSet(key, value)
  }

  const project = { project_id: 'project-a', revision: 0, name: '住宅案' }
  assert.equal(cacheProject(project, { furnitureItems: [{ id: 1 }] }, storage), false)
  assert.deepEqual(loadProjectCache('project-a', storage).snapshot.furnitureItems, [])
})

test('createServerProject sends the canonical JSON contract', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({ project: { project_id: 'p1' } }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const response = await createServerProject({ name: '住宅案', notes: '' }, fetchImpl)
  assert.equal(response.project.project_id, 'p1')
  assert.equal(request.path, '/api/projects')
  assert.equal(request.options.method, 'POST')
  assert.deepEqual(JSON.parse(request.options.body), { name: '住宅案', notes: '' })
})

test('workflow conflicts preserve status and localized server message', async () => {
  const fetchImpl = async () => new Response(JSON.stringify({
    detail: { code: 'project_revision_conflict', message: '專案已被更新。' },
  }), {
    status: 409,
    headers: { 'Content-Type': 'application/json' },
  })

  await assert.rejects(
    saveServerWorkflow('p1', { expected_revision: 0, workflow: {} }, fetchImpl),
    (error) => error instanceof ProjectApiError
      && error.status === 409
      && error.message === '專案已被更新。',
  )
})

test('floorplan upload carries the optimistic project revision', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({
      project: { project_id: 'p1', revision: 4 },
      upload: { filename: 'plan.png' },
    }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const file = new File(['png'], 'plan.png', { type: 'image/png' })

  await uploadServerFloorplan('p1', file, 3, fetchImpl)

  assert.equal(request.path, '/api/projects/p1/floorplan')
  assert.equal(request.options.method, 'POST')
  assert.equal(request.options.body.get('file').name, 'plan.png')
  assert.equal(request.options.body.get('expected_revision'), '3')
})

test('project floorplan analysis sends the canonical tuning contract', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({
      project: { project_id: 'p1', revision: 5 },
      analysis: { source: 'image', floorplan: {} },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const input = {
    expected_revision: 4,
    scale_m: null,
    thickness: 0.18,
    height: 2.7,
  }

  await analyzeServerFloorplan('p1', input, fetchImpl)

  assert.equal(request.path, '/api/projects/p1/floorplan/analyze')
  assert.equal(request.options.method, 'POST')
  assert.deepEqual(JSON.parse(request.options.body), input)
})

test('floorplan confirmation sends user decisions to the project-scoped endpoint', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({
      project: { project_id: 'p1', revision: 6 },
      confirmation: { status: 'confirmed' },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const input = {
    expected_revision: 5,
    rooms: [{ room_id: 'room-a', room_type: 'bedroom' }],
    doors: [],
    windows: [],
  }

  await confirmServerFloorplan('p1', input, fetchImpl)

  assert.equal(request.path, '/api/projects/p1/floorplan/confirm')
  assert.equal(request.options.method, 'POST')
  assert.deepEqual(JSON.parse(request.options.body), input)
})

test('floorplan calibration sends the reference line without resending a file', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({
      project: { project_id: 'p1', revision: 6 },
      analysis: { floorplan: {} },
      calibration: { status: 'confirmed', scale_cm: 800 },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const input = {
    expected_revision: 5,
    reference_cm: { x1_cm: -100, z1_cm: 0, x2_cm: 100, z2_cm: 0 },
    actual_length_cm: 300,
  }

  await calibrateServerFloorplan('p1', input, fetchImpl)

  assert.equal(request.path, '/api/projects/p1/floorplan/calibrate')
  assert.equal(request.options.method, 'POST')
  assert.deepEqual(JSON.parse(request.options.body), input)
})

test('requirements analysis and confirmation use separate project-scoped endpoints', async () => {
  const requests = []
  const fetchImpl = async (path, options) => {
    requests.push({ path, options })
    return new Response(JSON.stringify(path.endsWith('/analyze')
      ? { suggestion: { status: 'suggested' } }
      : { project: { project_id: 'p1', revision: 9 }, requirements: { status: 'confirmed' } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const analyzeInput = { expected_revision: 8, allow_openrouter: false }
  const confirmInput = { expected_revision: 8, suggestion: { status: 'suggested' } }

  await analyzeServerRequirements('p1', analyzeInput, fetchImpl)
  await confirmServerRequirements('p1', confirmInput, fetchImpl)

  assert.equal(requests[0].path, '/api/projects/p1/requirements/analyze')
  assert.equal(requests[1].path, '/api/projects/p1/requirements/confirm')
  assert.deepEqual(JSON.parse(requests[0].options.body), analyzeInput)
  assert.deepEqual(JSON.parse(requests[1].options.body), confirmInput)
})

test('white model confirmation uses the project-scoped gate endpoint', async () => {
  let request
  const fetchImpl = async (path, options) => {
    request = { path, options }
    return new Response(JSON.stringify({
      project: { project_id: 'p1', revision: 12 },
      white_model: { status: 'confirmed' },
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const input = {
    expected_revision: 11,
    user_reviewed: true,
    renderer: 'neutral_geometry',
    visible_instance_ids: ['sofa-1'],
  }

  await confirmServerWhiteModel('project 1', input, fetchImpl)

  assert.equal(request.path, '/api/projects/project%201/white-model-3d/confirm')
  assert.equal(request.options.method, 'POST')
  assert.deepEqual(JSON.parse(request.options.body), input)
})

test('viewpoint, style card and PNG use separate project-scoped endpoints', async () => {
  const requests = []
  const fetchImpl = async (path, options) => {
    requests.push({ path, options })
    return new Response(JSON.stringify({ project: { project_id: 'p1', revision: 5 }, renders: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  await confirmServerViewpoint('p1', { expected_revision: 2 }, fetchImpl)
  await applyServerStyleCard('p1', { expected_revision: 3, card_id: 'cream_1' }, fetchImpl)
  await createServerRender('p1', new Blob(['png'], { type: 'image/png' }), 4, fetchImpl)
  await listServerRenders('p1', fetchImpl)

  assert.deepEqual(requests.map((entry) => entry.path), [
    '/api/projects/p1/viewpoint/confirm',
    '/api/projects/p1/style-card/apply',
    '/api/projects/p1/renders',
    '/api/projects/p1/renders',
  ])
  assert.equal(JSON.parse(requests[0].options.body).expected_revision, 2)
  assert.equal(JSON.parse(requests[1].options.body).card_id, 'cream_1')
  assert.equal(requests[2].options.body.get('expected_revision'), '4')
})
