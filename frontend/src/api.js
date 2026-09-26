// Thin fetch layer mirroring the backend contracts documented in docs/API.md.
// All paths are relative so the SPA works both behind the Vite dev proxy and
// when served from FastAPI itself.

const TOKEN_KEY = 'safety_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(path, { ...options, headers })
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  if (!response.ok) {
    throw new ApiError(data?.detail || data || response.statusText || '请求失败', response.status)
  }
  return data
}

const json = (body) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const login = (username, password) => request('/api/v1/auth/login', { method: 'POST', ...json({ username, password }) })
export const health = () => request('/health')
export const metrics = () => request('/api/v1/metrics/summary')
export const listCameras = () => request('/api/v1/cameras')
export const createCamera = (payload) => request('/api/v1/cameras', { method: 'POST', ...json(payload) })
export const listZones = () => request('/api/v1/zones')
export const createZone = (cameraId, payload) => request(`/api/v1/cameras/${cameraId}/zones`, { method: 'POST', ...json(payload) })
export const deleteZone = (zoneId) => request(`/api/v1/zones/${zoneId}`, { method: 'DELETE' })
export const listEvents = (query = {}) => request(`/api/v1/events?${new URLSearchParams(query)}`)
export const updateEvent = (eventId, status) => request(`/api/v1/events/${eventId}`, { method: 'PATCH', ...json({ status }) })
export const listJobs = (query = {}) => request(`/api/v1/jobs?${new URLSearchParams(query)}`)
export const jobResult = (jobId) => request(`/api/v1/jobs/${encodeURIComponent(jobId)}/result`)
export const listDemoAssets = () => request('/api/v1/demo/assets')
export const experiments = () => request('/api/v1/experiments/summary')
export const inferImage = (form) => request('/api/v1/inference/images', { method: 'POST', body: form })
export const inferVideo = (form) => request('/api/v1/inference/videos', { method: 'POST', body: form })
