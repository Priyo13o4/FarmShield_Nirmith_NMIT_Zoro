import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react'

import { isDemoMode } from '../config/runtime'
import { api, getApiConfig, getDeviceId } from '../services/api'
import { wsManager } from '../services/websocket'

const POLLING_INTERVAL = 6000

const FarmContext = createContext(null)

const ACTIONS = {
  SET_LATEST: 'SET_LATEST',
  SET_CONNECTION_STATUS: 'SET_CONNECTION_STATUS',
  PREPEND_ALERT: 'PREPEND_ALERT',
  ACKNOWLEDGE_ALERT: 'ACKNOWLEDGE_ALERT',
  CLEAR_UNREAD: 'CLEAR_UNREAD',
  UPDATE_ALERTS: 'UPDATE_ALERTS',
  SET_PUMP_MODE: 'SET_PUMP_MODE',
  SET_LOADING: 'SET_LOADING',
  PATCH_SENSOR_DATA: 'PATCH_SENSOR_DATA',
}

const initialState = {
  sensorData: null,
  mlOutput: null,
  alerts: [],
  unreadAlertCount: 0,
  connectionStatus: 'connecting',
  pumpMode: 'AUTO',
  lastUpdated: null,
  isLoading: true,
}

function derivePumpMode(sensorData, fallbackMode) {
  if (!sensorData) {
    return fallbackMode
  }

  return sensorData.mode || sensorData.pumpMode || sensorData.controlMode || fallbackMode
}

function toUiSensorShape(data) {
  if (!data) {
    return null
  }

  return {
    ...data,
    soilPct: data.soilPct ?? data.soilpct ?? data.soil ?? data.soilMoisturePct,
    ph: data.ph,
    tdsPpm: data.tdsPpm ?? data.tdsppm ?? data.tds,
    tempC: data.tempC ?? data.tempc ?? data.temperature ?? data.temperatureC,
    humidityPct: data.humidityPct ?? data.humiditypct ?? data.humidity,
    rainMm: data.rainMm ?? data.rainraw ?? data.rain,
    motion: data.motion,
    npkN: data.npkN ?? data.npkn ?? data.nitrogen,
    npkP: data.npkP ?? data.npkp ?? data.phosphorus,
    npkK: data.npkK ?? data.npkk ?? data.potassium,
    leafR: data.leafR ?? data.leafr ?? data.leaf_r,
    leafG: data.leafG ?? data.leafg ?? data.leaf_g,
    leafB: data.leafB ?? data.leafb ?? data.leaf_b,
    pumpOn: data.pumpOn ?? data.pumpon ?? data.pumpState === 'ON',
  }
}

function normalizeLatestPayload(payload) {
  if (!payload) {
    return { data: null, mlOutput: null }
  }

  if (payload.data || payload.mlOutput) {
    return {
      data: toUiSensorShape(payload.data || null),
      mlOutput: payload.mlOutput || null,
    }
  }

  return {
    data: toUiSensorShape(payload),
    mlOutput: payload.mlOutput || null,
  }
}

function farmReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_LATEST: {
      const nextMode = derivePumpMode(action.payload.data, state.pumpMode)
      return {
        ...state,
        sensorData: action.payload.data,
        mlOutput: action.payload.mlOutput,
        lastUpdated: action.payload.lastUpdated,
        pumpMode: nextMode,
        isLoading: false,
      }
    }

    case ACTIONS.SET_CONNECTION_STATUS:
      return {
        ...state,
        connectionStatus: action.payload,
      }

    case ACTIONS.PREPEND_ALERT:
      return {
        ...state,
        alerts: [action.payload, ...state.alerts],
        unreadAlertCount: state.unreadAlertCount + 1,
      }

    case ACTIONS.ACKNOWLEDGE_ALERT:
      return {
        ...state,
        alerts: state.alerts.map((item) =>
          String(item.id) === String(action.payload)
            ? {
                ...item,
                acknowledged: true,
              }
            : item
        ),
      }

    case ACTIONS.CLEAR_UNREAD:
      return {
        ...state,
        unreadAlertCount: 0,
      }

    case ACTIONS.UPDATE_ALERTS:
      return {
        ...state,
        alerts: action.payload,
      }

    case ACTIONS.SET_PUMP_MODE:
      return {
        ...state,
        pumpMode: action.payload,
      }

    case ACTIONS.SET_LOADING:
      return {
        ...state,
        isLoading: action.payload,
      }

    case ACTIONS.PATCH_SENSOR_DATA:
      return {
        ...state,
        sensorData: {
          ...(state.sensorData || {}),
          ...action.payload,
        },
        lastUpdated: new Date().toISOString(),
      }

    default:
      return state
  }
}

export function FarmProvider({ children }) {
  const [state, dispatch] = useReducer(farmReducer, initialState)
  const pollingRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const refreshLatest = useCallback(async () => {
    try {
      const latest = await api.sensors.latest(getDeviceId())
      const normalized = normalizeLatestPayload(latest)
      dispatch({
        type: ACTIONS.SET_LATEST,
        payload: {
          ...normalized,
          lastUpdated: new Date().toISOString(),
        },
      })
    } catch (_error) {
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'offline' })
      dispatch({ type: ACTIONS.SET_LOADING, payload: false })
    }
  }, [])

  const startPolling = useCallback(() => {
    if (isDemoMode) {
      return
    }

    if (pollingRef.current) {
      return
    }

    pollingRef.current = setInterval(() => {
      refreshLatest()
    }, POLLING_INTERVAL)
  }, [refreshLatest])

  useEffect(() => {
    refreshLatest()
  }, [refreshLatest])

  useEffect(() => {
    const { url, apiKey } = getApiConfig()

    const unsubscribeConnected = wsManager.on('connected', () => {
      stopPolling()
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'live' })
      dispatch({ type: ACTIONS.SET_LOADING, payload: false })
    })

    const unsubscribeSensorData = wsManager.on('sensorData', (payload) => {
      dispatch({
        type: ACTIONS.SET_LATEST,
        payload: {
          data: payload.data,
          mlOutput: payload.mlOutput,
          lastUpdated: new Date().toISOString(),
        },
      })
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'live' })
    })

    const unsubscribeAlert = wsManager.on('alert', (payload) => {
      dispatch({ type: ACTIONS.PREPEND_ALERT, payload })
    })

    const unsubscribeDisconnected = wsManager.on('disconnected', () => {
      if (isDemoMode) {
        dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'offline' })
        return
      }

      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'polling' })
      startPolling()
    })

    const unsubscribeError = wsManager.on('error', () => {
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'offline' })
    })

    wsManager.connect(url, apiKey)

    return () => {
      unsubscribeConnected()
      unsubscribeSensorData()
      unsubscribeAlert()
      unsubscribeDisconnected()
      unsubscribeError()
      stopPolling()
      wsManager.disconnect()
    }
  }, [startPolling, stopPolling])

  const commandPump = useCallback(async (nextState) => {
    await api.control.pump(nextState)
    dispatch({
      type: ACTIONS.PATCH_SENSOR_DATA,
      payload: {
        pumpOn: nextState === 'ON',
        pumpon: nextState === 'ON',
        pumpState: nextState,
      },
    })
  }, [])

  const commandMode = useCallback(async (nextMode) => {
    await api.control.mode(nextMode)
    dispatch({ type: ACTIONS.SET_PUMP_MODE, payload: nextMode })
    dispatch({
      type: ACTIONS.PATCH_SENSOR_DATA,
      payload: {
        controlMode: nextMode,
      },
    })
  }, [])

  const silenceBuzzer = useCallback(async () => {
    await api.control.buzzer()
  }, [])

  const clearUnread = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_UNREAD })
  }, [])

  const acknowledgeAlertLocal = useCallback((alertId) => {
    dispatch({ type: ACTIONS.ACKNOWLEDGE_ALERT, payload: alertId })
  }, [])

  const updateAlerts = useCallback((alerts) => {
    dispatch({ type: ACTIONS.UPDATE_ALERTS, payload: alerts })
  }, [])

  const setPumpMode = useCallback((mode) => {
    dispatch({ type: ACTIONS.SET_PUMP_MODE, payload: mode })
  }, [])

  const value = useMemo(
    () => ({
      ...state,
      commandPump,
      commandMode,
      silenceBuzzer,
      clearUnread,
      acknowledgeAlertLocal,
      updateAlerts,
      setPumpMode,
    }),
    [
      state,
      commandPump,
      commandMode,
      silenceBuzzer,
      clearUnread,
      acknowledgeAlertLocal,
      updateAlerts,
      setPumpMode,
    ]
  )

  return <FarmContext.Provider value={value}>{children}</FarmContext.Provider>
}

export function useFarm() {
  const context = useContext(FarmContext)

  if (!context) {
    throw new Error('useFarm must be used inside FarmProvider')
  }

  return context
}
