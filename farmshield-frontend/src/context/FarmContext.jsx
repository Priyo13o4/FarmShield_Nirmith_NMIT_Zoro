import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react'

import { isDemoMode } from '../config/runtime'
import { api, getApiConfig, getDeviceId, getDeviceIds } from '../services/api'
import { wsManager } from '../services/websocket'

const POLLING_INTERVAL = 6000

const FarmContext = createContext(null)

const ACTIONS = {
  SET_LATEST: 'SET_LATEST',
  SET_NODE_DATA: 'SET_NODE_DATA',
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
  /** Active node's sensor data (for backward compat) */
  sensorData: null,
  mlOutput: null,
  /** Per-node sensor data map: { [deviceId]: { data, mlOutput, lastUpdated } } */
  nodesData: {},
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

function parseBoolean(val) {
  if (val === '0' || val === 0 || val === 'false' || val === 'OFF' || val === 'off' || val === false) {
    return false
  }
  if (val === '1' || val === 1 || val === 'true' || val === 'ON' || val === 'on' || val === true) {
    return true
  }
  return Boolean(val)
}

function toUiSensorShape(data) {
  if (!data) {
    return null
  }

  const pumpOnVal = data.pumpOn ?? data.pumpon ?? data.pumpState
  
  return {
    ...data,
    soilPct: data.soilPct ?? data.soilpct ?? data.soil ?? data.soilMoisturePct,
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
    pumpOn: parseBoolean(pumpOnVal),
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

    case ACTIONS.SET_NODE_DATA: {
      const { deviceId, data, mlOutput, lastUpdated } = action.payload
      return {
        ...state,
        nodesData: {
          ...state.nodesData,
          [deviceId]: { data, mlOutput, lastUpdated },
        },
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
  const [activeNodeId, setActiveNodeId] = useState(() => getDeviceId())
  const pollingRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  /** Refresh data for ALL registered nodes */
  const refreshAllNodes = useCallback(async () => {
    try {
      const nodesMap = await api.sensors.latestAll()
      const now = new Date().toISOString()

      Object.entries(nodesMap).forEach(([deviceId, rawData]) => {
        if (rawData) {
          const normalized = normalizeLatestPayload(rawData)
          dispatch({
            type: ACTIONS.SET_NODE_DATA,
            payload: {
              deviceId,
              data: normalized.data,
              mlOutput: normalized.mlOutput,
              lastUpdated: now,
            },
          })
        }
      })

      // Also set the active node as the primary sensorData for backward compat
      const activeData = nodesMap[activeNodeId]
      if (activeData) {
        const normalized = normalizeLatestPayload(activeData)
        dispatch({
          type: ACTIONS.SET_LATEST,
          payload: {
            ...normalized,
            lastUpdated: now,
          },
        })
      } else {
        dispatch({ type: ACTIONS.SET_LOADING, payload: false })
      }
    } catch (_error) {
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'offline' })
      dispatch({ type: ACTIONS.SET_LOADING, payload: false })
    }
  }, [activeNodeId])

  /** Switch the active node — update primary sensorData from cached nodesData */
  const switchActiveNode = useCallback((nodeId) => {
    setActiveNodeId(nodeId)
    // Immediately update primary sensorData from cache
    const cached = state.nodesData[nodeId]
    if (cached) {
      dispatch({
        type: ACTIONS.SET_LATEST,
        payload: {
          data: cached.data,
          mlOutput: cached.mlOutput,
          lastUpdated: cached.lastUpdated,
        },
      })
    }
  }, [state.nodesData])

  const startPolling = useCallback(() => {
    if (isDemoMode) {
      return
    }

    if (pollingRef.current) {
      return
    }

    pollingRef.current = setInterval(() => {
      refreshAllNodes()
    }, POLLING_INTERVAL)
  }, [refreshAllNodes])

  // Initial fetch
  useEffect(() => {
    refreshAllNodes()
  }, [refreshAllNodes])

  useEffect(() => {
    const { url, apiKey } = getApiConfig()

    const unsubscribeConnected = wsManager.on('connected', () => {
      stopPolling()
      dispatch({ type: ACTIONS.SET_CONNECTION_STATUS, payload: 'live' })
      dispatch({ type: ACTIONS.SET_LOADING, payload: false })
    })

    const unsubscribeSensorData = wsManager.on('sensorData', (payload) => {
      const deviceId = payload.data?.deviceid || payload.data?.deviceId || activeNodeId

      // Store in nodesData map
      dispatch({
        type: ACTIONS.SET_NODE_DATA,
        payload: {
          deviceId,
          data: payload.data,
          mlOutput: payload.mlOutput,
          lastUpdated: new Date().toISOString(),
        },
      })

      // If this data is for the active node, also update primary sensorData
      if (deviceId === activeNodeId) {
        dispatch({
          type: ACTIONS.SET_LATEST,
          payload: {
            data: payload.data,
            mlOutput: payload.mlOutput,
            lastUpdated: new Date().toISOString(),
          },
        })
      }

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
  }, [startPolling, stopPolling, activeNodeId])

  const commandPump = useCallback(async (nextState) => {
    // Optimistic update
    dispatch({
      type: ACTIONS.PATCH_SENSOR_DATA,
      payload: {
        pumpOn: nextState === 'ON',
        pumpon: nextState === 'ON',
        pumpState: nextState,
      },
    })

    try {
      await api.control.pump(nextState)
    } catch (error) {
      refreshAllNodes() // Rollback
      throw error
    }
  }, [refreshAllNodes])

  const commandMode = useCallback(async (nextMode) => {
    // Optimistic update
    dispatch({ type: ACTIONS.SET_PUMP_MODE, payload: nextMode })
    dispatch({
      type: ACTIONS.PATCH_SENSOR_DATA,
      payload: {
        controlMode: nextMode,
      },
    })

    try {
      await api.control.mode(nextMode)
    } catch (error) {
      refreshAllNodes() // Rollback
      throw error
    }
  }, [refreshAllNodes])

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

  const pumpOn = Boolean(state.sensorData?.pumpOn)

  const value = useMemo(
    () => ({
      ...state,
      pumpOn,
      activeNodeId,
      switchActiveNode,
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
      pumpOn,
      activeNodeId,
      switchActiveNode,
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
