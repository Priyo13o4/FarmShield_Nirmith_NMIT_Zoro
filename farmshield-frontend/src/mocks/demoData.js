import { demoDeviceId } from '../config/runtime'

const DAY_MS = 24 * 60 * 60 * 1000

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function round(value, digits = 1) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function sinusoid(seed, amplitude, period, phase = 0) {
  return Math.sin((seed / period) * Math.PI * 2 + phase) * amplitude
}

function buildReading(seed, timestamp, overrides = {}) {
  const soilpct = clamp(round(50 + sinusoid(seed, 7, 36) + sinusoid(seed, 2.5, 12), 1), 32, 62)
  const ph = clamp(round(6.7 + sinusoid(seed, 0.24, 40), 2), 6.2, 7.2)
  const tdsppm = clamp(Math.round(520 + sinusoid(seed, 120, 30) + sinusoid(seed, 45, 9)), 280, 780)
  const tempc = clamp(round(31 + sinusoid(seed, 2.4, 28) + sinusoid(seed, 0.9, 10), 1), 27.2, 34.4)
  const humiditypct = clamp(round(66 + sinusoid(seed, 8.5, 30), 1), 54, 76)
  const rainraw = clamp(Math.round(3120 + sinusoid(seed, 370, 22)), 2580, 3620)
  const motion = false
  const npkn = clamp(Math.round(34 + sinusoid(seed, 5, 50)), 26, 42)
  const npkp = clamp(Math.round(28 + sinusoid(seed, 4, 44)), 20, 34)
  const npkk = clamp(Math.round(30 + sinusoid(seed, 5, 47)), 22, 37)
  const leafr = clamp(Math.round(84 + sinusoid(seed, 7, 33)), 70, 94)
  const leafg = clamp(Math.round(146 + sinusoid(seed, 10, 31)), 128, 164)
  const leafb = clamp(Math.round(78 + sinusoid(seed, 6, 29)), 64, 90)

  return {
    time: new Date(timestamp).toISOString(),
    deviceid: demoDeviceId,
    soilpct,
    ph,
    tdsppm,
    tempc,
    humiditypct,
    rainraw,
    motion,
    npkn,
    npkp,
    npkk,
    leafr,
    leafg,
    leafb,
    pumpon: false,
    ...overrides,
  }
}

function buildRange(hours, points) {
  const now = Date.now()
  const totalMs = hours * 60 * 60 * 1000
  const stepMs = Math.max(Math.floor(totalMs / points), 60 * 1000)

  return Array.from({ length: points }, (_, index) => {
    const timestamp = now - totalMs + stepMs * index
    return buildReading(index + hours * 7, timestamp)
  })
}

export const demoLatestSensorReading = buildReading(99, Date.now(), {
  soilpct: 51.4,
  ph: 6.8,
  tdsppm: 548,
  tempc: 31.2,
  humiditypct: 68.5,
  rainraw: 3186,
  npkn: 35,
  npkp: 29,
  npkk: 31,
  leafr: 82,
  leafg: 149,
  leafb: 76,
  motion: false,
  pumpon: false,
})

export const demoHistoryReadings = {
  '1h': buildRange(1, 24),
  '6h': buildRange(6, 48),
  '24h': buildRange(24, 96),
  '7d': buildRange(168, 120),
}

export const demoAlerts = [
  {
    id: 'demo-alert-001',
    time: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    deviceid: demoDeviceId,
    type: 'SOIL_DRY',
    severity: 'WARNING',
    message: 'Soil moisture is trending down in zone A. Consider irrigation in the next cycle.',
    acknowledged: false,
  },
  {
    id: 'demo-alert-002',
    time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    deviceid: demoDeviceId,
    type: 'TEMP_HIGH',
    severity: 'WARNING',
    message: 'Canopy temperature crossed the recommended threshold for 20 minutes.',
    acknowledged: true,
  },
  {
    id: 'demo-alert-003',
    time: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    deviceid: demoDeviceId,
    type: 'MOTION_DETECTED',
    severity: 'CRITICAL',
    message: 'Intrusion detected near northern field gate.',
    acknowledged: false,
  },
  {
    id: 'demo-alert-004',
    time: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    deviceid: demoDeviceId,
    type: 'PH_LOW',
    severity: 'WARNING',
    message: 'pH level dropped below the optimal hydroponic range.',
    acknowledged: false,
  },
  {
    id: 'demo-alert-005',
    time: new Date(Date.now() - DAY_MS).toISOString(),
    deviceid: demoDeviceId,
    type: 'RAIN_SENSOR_VARIANCE',
    severity: 'INFO',
    message: 'Rain sensor calibration drift observed and auto-corrected.',
    acknowledged: true,
  },
]

export const demoMlOutput = {
  action: 'MONITOR',
  confidence: 0.87,
  irrigationScore: 0.41,
}

export function getHistoryRangeKey(hours) {
  if (hours <= 1) {
    return '1h'
  }
  if (hours <= 6) {
    return '6h'
  }
  if (hours <= 24) {
    return '24h'
  }
  return '7d'
}

export function getDemoHistoryByHours(hours = 24) {
  const key = getHistoryRangeKey(hours)
  return demoHistoryReadings[key]
}

export function createDemoHistoryPayload({ hours = 24, deviceId = demoDeviceId, limit }) {
  const rows = getDemoHistoryByHours(hours)
  const sliced = typeof limit === 'number' ? rows.slice(-limit) : rows

  return {
    count: sliced.length,
    deviceid: deviceId,
    readings: sliced,
  }
}

export function readingToUiShape(reading) {
  if (!reading) {
    return null
  }

  return {
    ...reading,
    time: reading.time,
    deviceid: reading.deviceid,
    soilPct: reading.soilpct,
    ph: reading.ph,
    tdsPpm: reading.tdsppm,
    tempC: reading.tempc,
    humidityPct: reading.humiditypct,
    rainMm: reading.rainraw,
    motion: reading.motion,
    npkN: reading.npkn,
    npkP: reading.npkp,
    npkK: reading.npkk,
    leafR: reading.leafr,
    leafG: reading.leafg,
    leafB: reading.leafb,
    pumpOn: reading.pumpon,
  }
}

export function generateNextDemoReading(previousReading, tick = 1) {
  const source = previousReading || demoLatestSensorReading
  const seed = tick * 4

  const next = buildReading(seed, Date.now(), {
    pumpon: source.pumpon,
    motion: tick % 9 === 0,
    soilpct: clamp(round(source.soilpct + sinusoid(seed, 1.7, 11), 1), 34, 61),
    ph: clamp(round(source.ph + sinusoid(seed, 0.06, 14), 2), 6.3, 7.2),
    tdsppm: clamp(Math.round(source.tdsppm + sinusoid(seed, 26, 13)), 300, 740),
    tempc: clamp(round(source.tempc + sinusoid(seed, 0.45, 10), 1), 27.5, 34.5),
    humiditypct: clamp(round(source.humiditypct + sinusoid(seed, 1.8, 12), 1), 55, 76),
    rainraw: clamp(Math.round(source.rainraw + sinusoid(seed, 80, 18)), 2600, 3600),
  })

  return next
}

export function createDemoAlert(tick = 1) {
  const templates = [
    {
      type: 'SOIL_DRY',
      severity: 'WARNING',
      message: 'Soil moisture dropped below threshold in irrigation lane B.',
    },
    {
      type: 'TEMP_HIGH',
      severity: 'WARNING',
      message: 'Ambient temperature rose above target band.',
    },
    {
      type: 'MOTION_DETECTED',
      severity: 'CRITICAL',
      message: 'Unexpected motion detected near storage perimeter.',
    },
    {
      type: 'PH_LOW',
      severity: 'WARNING',
      message: 'Nutrient solution pH is below the recommended range.',
    },
  ]

  const template = templates[tick % templates.length]

  return {
    id: `demo-live-${Date.now()}`,
    time: new Date().toISOString(),
    deviceid: demoDeviceId,
    type: template.type,
    severity: template.severity,
    message: template.message,
    acknowledged: false,
  }
}

export function alertsToUiShape(alerts) {
  return alerts.map((alert) => ({
    ...alert,
    timestamp: alert.time,
    createdAt: alert.time,
  }))
}

export function alertToUiShape(alert) {
  if (!alert) {
    return null
  }

  return {
    ...alert,
    timestamp: alert.time,
    createdAt: alert.time,
  }
}

export function historyReadingsToUiShape(readings) {
  return readings.map((reading) => ({
    ...reading,
    timestamp: reading.time,
    soilPct: reading.soilpct,
    tdsPpm: reading.tdsppm,
    tempC: reading.tempc,
    humidityPct: reading.humiditypct,
    rainMm: reading.rainraw,
    npkN: reading.npkn,
    npkP: reading.npkp,
    npkK: reading.npkk,
    leafR: reading.leafr,
    leafG: reading.leafg,
    leafB: reading.leafb,
    pumpOn: reading.pumpon,
  }))
}

export function historyToCsv(readings) {
  const headers = [
    'time',
    'deviceid',
    'soilpct',
    'ph',
    'tdsppm',
    'tempc',
    'humiditypct',
    'rainraw',
    'motion',
    'npkn',
    'npkp',
    'npkk',
    'leafr',
    'leafg',
    'leafb',
    'pumpon',
  ]

  const rows = readings.map((reading) =>
    headers.map((header) => String(reading[header] ?? '')).join(',')
  )

  return [headers.join(','), ...rows].join('\n')
}
