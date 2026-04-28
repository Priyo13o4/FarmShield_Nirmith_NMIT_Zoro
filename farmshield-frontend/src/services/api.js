import { isDemoMode } from '../config/runtime'
import {
  alertToUiShape,
  alertsToUiShape,
  createDemoHistoryPayload,
  demoAlerts,
  demoLatestSensorReading,
  historyReadingsToUiShape,
  historyToCsv,
  readingToUiShape,
} from '../mocks/demoData'

const LOCAL_KEYS = {
  apiUrl: 'fs_api_url',
  apiKey: 'fs_api_key',
  deviceId: 'fs_device_id',
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

export function getDeviceId() {
  return getStoredValue(LOCAL_KEYS.deviceId, 'esp32-node-1')
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
}
