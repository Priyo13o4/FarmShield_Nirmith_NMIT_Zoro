import { isDemoMode } from '../config/runtime'
import {
  alertToUiShape,
  alertsToUiShape,
  createDemoHistoryPayload,
  demoAlerts,
  demoLatestSensorReading,
  generateDemoChatResponse,
  historyReadingsToUiShape,
  historyToCsv,
  readingToUiShape,
} from '../mocks/demoData'

const LOCAL_KEYS = {
  apiUrl: 'fs_api_url',
  apiKey: 'fs_api_key',
  deviceId: 'fs_device_id',
  deviceIds: 'fs_device_ids',
}

const API_PREFIX = '/api/v1'
const DEFAULT_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const DEFAULT_API_KEY = import.meta.env.VITE_API_KEY || ''
const CSV_FILE_NAME = 'farmshield-export.csv'
const DEMO_LATENCY_MS = 180

let demoPumpOn = demoLatestSensorReading.pumpon
let demoAlertsState = alertsToUiShape(demoAlerts)

function withDemoDelay(payload) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(payload), DEMO_LATENCY_MS)
  })
}

function getDemoLatestReadingUi() {
  return readingToUiShape({
    ...demoLatestSensorReading,
    pumpon: demoPumpOn,
  })
}

function getStoredValue(key, fallback = '') {
  const value = localStorage.getItem(key)
  return value ?? fallback
}

export function getApiConfig(overrides = {}) {
  return {
    url: overrides.url || getStoredValue(LOCAL_KEYS.apiUrl, DEFAULT_BASE_URL),
    apiKey: overrides.apiKey ?? getStoredValue(LOCAL_KEYS.apiKey, DEFAULT_API_KEY),
  }
}

/** Get the legacy single device ID (used as the "active" node) */
export function getDeviceId() {
  return getStoredValue(LOCAL_KEYS.deviceId, 'esp32-node-1')
}

/** Get all registered device IDs as an array */
export function getDeviceIds() {
  const stored = localStorage.getItem(LOCAL_KEYS.deviceIds)
  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed
      }
    } catch (_e) {
      // fall through
    }
  }
  // Fallback: migrate legacy single device ID
  const legacy = getDeviceId()
  return legacy ? [legacy] : ['esp32-node-1']
}

/** Save all device IDs */
export function setDeviceIds(ids) {
  const unique = [...new Set(ids.filter(Boolean))]
  localStorage.setItem(LOCAL_KEYS.deviceIds, JSON.stringify(unique))
  // Keep legacy key in sync with first device
  if (unique.length > 0) {
    localStorage.setItem(LOCAL_KEYS.deviceId, unique[0])
  }
}

/** Add a device ID to the list */
export function addDeviceId(id) {
  if (!id) return
  const current = getDeviceIds()
  if (!current.includes(id)) {
    setDeviceIds([...current, id])
  }
}

/** Remove a device ID from the list */
export function removeDeviceId(id) {
  const current = getDeviceIds()
  const next = current.filter((d) => d !== id)
  if (next.length === 0) return // Don't allow removing all devices
  setDeviceIds(next)
}

export function configureApi({ url, apiKey }) {
  if (typeof url === 'string') {
    localStorage.setItem(LOCAL_KEYS.apiUrl, url)
  }
  if (typeof apiKey === 'string') {
    localStorage.setItem(LOCAL_KEYS.apiKey, apiKey)
  }
}

function buildQuery(params = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  })
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

async function parseErrorResponse(response) {
  try {
    const payload = await response.json()
    return payload?.detail || payload?.message || 'Request failed'
  } catch (_error) {
    return 'Request failed'
  }
}

async function parseJsonResponse(response) {
  const text = await response.text()
  if (!text) {
    return null
  }
  return JSON.parse(text)
}

async function request(method, path, body, params, options = {}) {
  const { url, apiKey } = getApiConfig(options)
  const endpoint = `${url}${API_PREFIX}${path}${buildQuery(params)}`
  const headers = {
    Authorization: `Bearer ${apiKey || ''}`,
  }

  if (method === 'POST' || method === 'PATCH') {
    headers['Content-Type'] = 'application/json'
  }

  if (options.publicRequest) {
    delete headers.Authorization
  }

  const response = await fetch(endpoint, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const detail = await parseErrorResponse(response)
    throw { status: response.status, detail }
  }

  return parseJsonResponse(response)
}

function triggerCsvDownload(csvContent) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = CSV_FILE_NAME
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(objectUrl)
}

export const api = {
  health: {
    async check(overrides = {}) {
      if (isDemoMode) {
        return withDemoDelay({
          status: 'ok',
          mqttConnected: true,
          dbConnected: true,
          mlEnabled: false,
          version: 'demo-mode',
        })
      }

      const { url } = getApiConfig(overrides)
      const response = await fetch(`${url}/health`, {
        method: 'GET',
      })

      if (!response.ok) {
        const detail = await parseErrorResponse(response)
        throw { status: response.status, detail }
      }

      return parseJsonResponse(response)
    },
  },
  sensors: {
    latest(deviceId = 'esp32-node-1') {
      if (isDemoMode) {
        return withDemoDelay({
          ...getDemoLatestReadingUi(),
          deviceid: deviceId,
        })
      }

      return request('GET', '/sensors/latest', null, { deviceid: deviceId })
    },
    /** Fetch latest for ALL registered device IDs at once */
    async latestAll() {
      const ids = getDeviceIds()
      const results = await Promise.allSettled(
        ids.map((id) => api.sensors.latest(id))
      )
      const map = {}
      ids.forEach((id, idx) => {
        const result = results[idx]
        map[id] = result.status === 'fulfilled' ? result.value : null
      })
      return map
    },
    history({ deviceId, hours, limit, offset }) {
      if (isDemoMode) {
        const payload = createDemoHistoryPayload({
          hours,
          deviceId,
          limit,
          offset,
        })

        return withDemoDelay({
          count: payload.count,
          deviceid: payload.deviceid,
          readings: historyReadingsToUiShape(payload.readings),
        })
      }

      return request('GET', '/sensors/history', null, {
        deviceid: deviceId,
        hours,
        limit,
        offset,
      })
    },
    async export({ deviceId, hours, limit }) {
      if (isDemoMode) {
        const payload = createDemoHistoryPayload({
          hours,
          deviceId,
          limit,
        })
        const csv = historyToCsv(payload.readings)
        triggerCsvDownload(csv)
        return csv
      }

      const { url, apiKey } = getApiConfig()
      const endpoint = `${url}${API_PREFIX}/sensors/export${buildQuery({
        deviceid: deviceId,
        hours,
        limit,
      })}`
      const response = await fetch(endpoint, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${apiKey || ''}`,
        },
      })

      if (!response.ok) {
        const detail = await parseErrorResponse(response)
        throw { status: response.status, detail }
      }

      const csv = await response.text()
      triggerCsvDownload(csv)
      return csv
    },
  },
  control: {
    pump(state) {
      if (isDemoMode) {
        demoPumpOn = state === 'ON'
        return withDemoDelay({
          command: 'pump',
          state,
          published: true,
          ts: Math.floor(Date.now() / 1000),
        })
      }

      return request('POST', '/control/pump', { state })
    },
    mode(state) {
      if (isDemoMode) {
        return withDemoDelay({
          command: 'mode',
          state,
          published: true,
          ts: Math.floor(Date.now() / 1000),
        })
      }

      return request('POST', '/control/mode', { state })
    },
    buzzer() {
      if (isDemoMode) {
        return withDemoDelay({
          command: 'buzzer',
          state: 'OFF',
          published: true,
          ts: Math.floor(Date.now() / 1000),
        })
      }

      return request('POST', '/control/buzzer', { state: 'OFF' })
    },
  },
  alerts: {
    list({ deviceId, limit, unacknowledgedOnly }) {
      if (isDemoMode) {
        const alerts = [...demoAlertsState].filter((alert) => {
          if (!unacknowledgedOnly) {
            return true
          }
          return !alert.acknowledged
        })

        const limitedAlerts = typeof limit === 'number' ? alerts.slice(0, limit) : alerts

        return withDemoDelay({
          count: limitedAlerts.length,
          alerts: limitedAlerts.map((alert) => ({
            ...alert,
            deviceid: deviceId || alert.deviceid,
          })),
        })
      }

      return request('GET', '/alerts', null, {
        deviceid: deviceId,
        limit,
        unacknowledged_only: unacknowledgedOnly,
      })
    },
    acknowledge(alertId) {
      if (isDemoMode) {
        const nextAlerts = demoAlertsState.map((alert) =>
          String(alert.id) === String(alertId)
            ? {
                ...alert,
                acknowledged: true,
              }
            : alert
        )
        demoAlertsState = nextAlerts
        const alert = nextAlerts.find((item) => String(item.id) === String(alertId))
        return withDemoDelay(alertToUiShape(alert))
      }

      return request('PATCH', `/alerts/${alertId}/acknowledge`)
    },
  },

  chat: {
    async sendMessage({ message, sessionId }) {
      if (isDemoMode) {
        return new Promise((resolve) => {
          setTimeout(() => {
            const result = generateDemoChatResponse(message)
            resolve({
              reply: result.reply,
              session_id: sessionId,
              sources: result.sources,
              ts: Date.now() / 1000,
            })
          }, 800)
        })
      }
      return request('POST', '/chat/message', { message, session_id: sessionId })
    },
    streamMessage({ message, sessionId, onToken, onReasoning, onDone, onError }) {
      if (isDemoMode) {
        let isCancelled = false
        const result = generateDemoChatResponse(message)
        const tokens = result.reply.match(/[\s\S]{1,4}/g) || []
        
        setTimeout(() => {
          if (isCancelled) return
          
          // Simulate some reasoning first
          if (onReasoning) {
            onReasoning("I am checking the current sensor readings in the database...\n")
            onReasoning("Analyzing soil moisture levels across all nodes...\n")
          }

          let index = 0
          const timer = setInterval(() => {
            if (isCancelled) {
              clearInterval(timer)
              return
            }
            if (index < tokens.length) {
              onToken(tokens[index])
              index++
            } else {
              clearInterval(timer)
              onDone({ sources: result.sources, session_id: sessionId })
            }
          }, 80)
        }, 400)
        
        return () => { isCancelled = true }
      }

      const { url, apiKey } = getApiConfig({})
      const endpoint = `${url}${API_PREFIX}/chat/stream?message=${encodeURIComponent(message)}&session_id=${encodeURIComponent(sessionId)}&api_key=${encodeURIComponent(apiKey || '')}`
      
      const eventSource = new EventSource(endpoint)

      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data)
          if (parsed.done) {
            onDone({ sources: parsed.sources, session_id: parsed.session_id })
            eventSource.close()
          } else if (parsed.token) {
            onToken(parsed.token)
          } else if (parsed.reasoning) {
            if (onReasoning) onReasoning(parsed.reasoning)
          }
        } catch (err) {
          console.error('SSE parse error:', err)
        }
      }

      eventSource.onerror = (err) => {
        console.error('SSE connection error:', err)
        onError(err)
        eventSource.close()
      }

      return () => {
        eventSource.close()
      }
    },
    async clearSession(sessionId) {
      if (isDemoMode) {
        return withDemoDelay({ session_id: sessionId, cleared: true })
      }
      return request('DELETE', `/chat/session/${sessionId}`)
    },
  },
}
