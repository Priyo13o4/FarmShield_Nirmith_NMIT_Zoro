import { isDemoMode } from '../config/runtime'
import {
  alertToUiShape,
  createDemoAlert,
  demoLatestSensorReading,
  demoMlOutput,
  generateNextDemoReading,
  readingToUiShape,
} from '../mocks/demoData'

const WS_PATH = '/api/v1/ws/live'
const RECONNECT_START_DELAY = 2000
const RECONNECT_CAP_DELAY = 30000
const PING_INTERVAL = 25000
const DEMO_CONNECT_DELAY = 500
const DEMO_SENSOR_INTERVAL = 5000
const DEMO_ALERT_EVERY_N_TICKS = 5

class WSManager {
  constructor() {
    this.ws = null
    this.listeners = new Map()
    this.reconnectDelay = RECONNECT_START_DELAY
    this.reconnectTimeout = null
    this.pingInterval = null
    this.intentionallyClosed = false
    this.connectionConfig = null
    this.demoConnected = false
    this.demoConnectTimeout = null
    this.demoTick = 0
    this.demoReading = demoLatestSensorReading
    this.demoSensorTimer = null
  }

  connect(baseUrl, apiKey) {
    if (isDemoMode) {
      this.connectDemoMode(baseUrl, apiKey)
      return
    }

    this.connectionConfig = { baseUrl, apiKey }
    this.intentionallyClosed = false

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return
    }

    const wsUrl = `${baseUrl.replace('http', 'ws')}${WS_PATH}`

    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.emit('connected')
      this.reconnectDelay = RECONNECT_START_DELAY
      this.startPing()
    }

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        // Backend sends "sensor_reading" type. Also handle "sensorreading" for backward compat.
        if (payload.type === 'sensorreading' || payload.type === 'sensor_reading') {
          this.emit('sensorData', {
            data: payload.data,
            mlOutput: payload.mlOutput,
          })
          return
        }
        if (payload.type === 'alert') {
          this.emit('alert', payload.data?.data || payload.data)
          return
        }
      } catch (_error) {
        // Ignore invalid frame payloads.
      }
    }

    this.ws.onclose = () => {
      this.clearPing()
      this.emit('disconnected')

      if (this.intentionallyClosed) {
        return
      }

      this.reconnectTimeout = setTimeout(() => {
        this.connect(this.connectionConfig.baseUrl, this.connectionConfig.apiKey)
      }, this.reconnectDelay)

      this.reconnectDelay = Math.min(
        this.reconnectDelay * 2,
        RECONNECT_CAP_DELAY
      )
    }

    this.ws.onerror = (error) => {
      this.emit('error', error)
      console.error('FarmShield websocket error', error)
    }
  }

  connectDemoMode(baseUrl, apiKey) {
    this.connectionConfig = { baseUrl, apiKey }
    this.intentionallyClosed = false

    if (this.demoConnected || this.demoConnectTimeout || this.demoSensorTimer) {
      return
    }

    this.demoConnectTimeout = setTimeout(() => {
      this.demoConnected = true
      this.demoConnectTimeout = null
      this.reconnectDelay = RECONNECT_START_DELAY
      this.emit('connected')
      this.startDemoStream()
    }, DEMO_CONNECT_DELAY)
  }

  startDemoStream() {
    this.stopDemoStream()

    this.demoSensorTimer = setInterval(() => {
      this.demoTick += 1
      this.demoReading = generateNextDemoReading(this.demoReading, this.demoTick)

      this.emit('sensorData', {
        data: readingToUiShape(this.demoReading),
        mlOutput: demoMlOutput,
      })

      if (this.demoTick % DEMO_ALERT_EVERY_N_TICKS === 0) {
        this.emit('alert', alertToUiShape(createDemoAlert(this.demoTick)))
      }
    }, DEMO_SENSOR_INTERVAL)
  }

  stopDemoStream() {
    if (this.demoSensorTimer) {
      clearInterval(this.demoSensorTimer)
      this.demoSensorTimer = null
    }

    if (this.demoConnectTimeout) {
      clearTimeout(this.demoConnectTimeout)
      this.demoConnectTimeout = null
    }
  }

  startPing() {
    this.clearPing()
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, PING_INTERVAL)
  }

  clearPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  disconnect() {
    if (isDemoMode) {
      this.intentionallyClosed = true
      this.stopDemoStream()
      const wasConnected = this.demoConnected
      this.demoConnected = false
      if (wasConnected) {
        this.emit('disconnected')
      }
      return
    }

    this.intentionallyClosed = true
    this.clearPing()

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }

    const listeners = this.listeners.get(event)
    listeners.add(callback)

    return () => {
      listeners.delete(callback)
      if (!listeners.size) {
        this.listeners.delete(event)
      }
    }
  }

  emit(event, data) {
    const listeners = this.listeners.get(event)
    if (!listeners) {
      return
    }

    listeners.forEach((callback) => callback(data))
  }

  isConnected() {
    if (isDemoMode) {
      return this.demoConnected
    }

    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const wsManager = new WSManager()
