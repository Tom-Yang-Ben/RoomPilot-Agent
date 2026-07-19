export const PROJECT_CACHE_SCHEMA_VERSION = 1
export const PROJECT_CACHE_PREFIX = 'roompilot.project-cache.v1'
export const LAST_PROJECT_KEY = 'roompilot.last-project.v1'

function cacheKey(projectId) {
  return `${PROJECT_CACHE_PREFIX}:${projectId}`
}

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

function compactSnapshot(snapshot = {}) {
  return {
    ...clone(snapshot),
    furnitureItems: [],
  }
}

export class ProjectApiError extends Error {
  constructor(message, { status = 0, payload = null } = {}) {
    super(message)
    this.name = 'ProjectApiError'
    this.status = status
    this.payload = payload
  }
}

function errorMessage(payload, fallback) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return fallback
}

async function requestJson(path, options = {}, fetchImpl = globalThis.fetch) {
  let response
  try {
    response = await fetchImpl(path, options)
  } catch (error) {
    throw new ProjectApiError(`無法連線專案服務：${error.message}`, { status: 0 })
  }

  let payload = null
  try {
    payload = await response.json()
  } catch {
    // Keep the HTTP status even if a proxy returned a non-JSON error page.
  }
  if (!response.ok) {
    throw new ProjectApiError(
      errorMessage(payload, `專案服務回傳 ${response.status}`),
      { status: response.status, payload },
    )
  }
  return payload
}

export function createServerProject(input, fetchImpl) {
  return requestJson('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function loadServerProject(projectId, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}`, {}, fetchImpl)
}

export function saveServerWorkflow(projectId, update, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/workflow`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  }, fetchImpl)
}

export function uploadServerFloorplan(projectId, file, expectedRevision, fetchImpl) {
  const body = new FormData()
  body.append('file', file)
  body.append('expected_revision', String(expectedRevision))
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/floorplan`, {
    method: 'POST',
    body,
  }, fetchImpl)
}

export function analyzeServerFloorplan(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/floorplan/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function calibrateServerFloorplan(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/floorplan/calibrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function confirmServerFloorplan(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/floorplan/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function analyzeServerRequirements(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/requirements/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function confirmServerRequirements(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/requirements/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function analyzeServerLayout(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/layout-2d/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function validateServerLayout(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/layout-2d/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function confirmServerLayout(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/layout-2d/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function confirmServerWhiteModel(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/white-model-3d/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function confirmServerViewpoint(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/viewpoint/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function applyServerStyleCard(projectId, input, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/style-card/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  }, fetchImpl)
}

export function createServerRender(projectId, blob, expectedRevision, fetchImpl) {
  const body = new FormData()
  body.append('file', blob, 'roompilot-final.png')
  body.append('expected_revision', String(expectedRevision))
  body.append('provider', 'browser_capture')
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/renders`, {
    method: 'POST',
    body,
  }, fetchImpl)
}

export function listServerRenders(projectId, fetchImpl) {
  return requestJson(`/api/projects/${encodeURIComponent(projectId)}/renders`, {}, fetchImpl)
}

export function projectIdFromLocation(location = globalThis.location) {
  if (!location?.href) return null
  const value = new URL(location.href).searchParams.get('project_id')
  return value?.trim() || null
}

export function setProjectInLocation(
  projectId,
  history = globalThis.history,
  location = globalThis.location,
) {
  if (!history?.replaceState || !location?.href) return
  const url = new URL(location.href)
  if (projectId) url.searchParams.set('project_id', projectId)
  else url.searchParams.delete('project_id')
  history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`)
}

export function loadLastProjectId(storage = globalThis.localStorage) {
  try {
    return storage?.getItem(LAST_PROJECT_KEY)?.trim() || null
  } catch {
    return null
  }
}

export function rememberProjectId(projectId, storage = globalThis.localStorage) {
  try {
    if (projectId) storage?.setItem(LAST_PROJECT_KEY, projectId)
    else storage?.removeItem(LAST_PROJECT_KEY)
  } catch {
    // Local cache is optional; the server remains canonical.
  }
}

export function loadProjectCache(projectId, storage = globalThis.localStorage) {
  if (!projectId) return null
  try {
    const parsed = JSON.parse(storage?.getItem(cacheKey(projectId)) || 'null')
    if (
      parsed?.schemaVersion === PROJECT_CACHE_SCHEMA_VERSION
      && parsed.project?.project_id === projectId
    ) {
      return parsed
    }
  } catch {
    // Corrupt or inaccessible cache is ignored.
  }
  return null
}

export function cacheProject(
  project,
  snapshot = {},
  storage = globalThis.localStorage,
) {
  if (!project?.project_id) return false
  const entry = {
    schemaVersion: PROJECT_CACHE_SCHEMA_VERSION,
    project: clone(project),
    snapshot: clone(snapshot),
    cachedAt: new Date().toISOString(),
  }
  try {
    storage?.setItem(cacheKey(project.project_id), JSON.stringify(entry))
    rememberProjectId(project.project_id, storage)
    return true
  } catch {
    try {
      storage?.setItem(
        cacheKey(project.project_id),
        JSON.stringify({ ...entry, snapshot: compactSnapshot(snapshot) }),
      )
      rememberProjectId(project.project_id, storage)
    } catch {
      // Quota errors must not interrupt the current browser session.
    }
    return false
  }
}
