import {
  Cloud,
  CloudRain,
  Droplets,
  FlaskConical,
  Leaf,
  ShieldAlert,
  Thermometer,
  Waves,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useFarm } from '../../context/FarmContext'
import { getSensorStatus } from '../../utils/sensorStatus'
import SensorCard from './SensorCard'

const SENSOR_CONFIG = [
  {
    sensorKey: 'soilPct',
    labelKey: 'sensors.soil',
    unitKey: 'sensors.units.percent',
    icon: Droplets,
  },
  {
    sensorKey: 'ph',
    labelKey: 'sensors.ph',
    unitKey: 'sensors.units.ph',
    icon: FlaskConical,
  },
  {
    sensorKey: 'tdsPpm',
    labelKey: 'sensors.tds',
    unitKey: 'sensors.units.ppm',
    icon: Waves,
  },
  {
    sensorKey: 'tempC',
    labelKey: 'sensors.temp',
    unitKey: 'sensors.units.celsius',
    icon: Thermometer,
  },
  {
    sensorKey: 'humidityPct',
    labelKey: 'sensors.humidity',
    unitKey: 'sensors.units.percent',
    icon: Cloud,
  },
  {
    sensorKey: 'rainMm',
    labelKey: 'sensors.rain',
    unitKey: 'sensors.units.rain',
    icon: CloudRain,
  },
  {
    sensorKey: 'motion',
    labelKey: 'sensors.motion',
    unitKey: 'sensors.units.none',
    icon: ShieldAlert,
  },
]

const NPK_CONFIG = [
  {
    sensorKey: 'npkN',
    labelKey: 'sensors.npkN',
  },
  {
    sensorKey: 'npkP',
    labelKey: 'sensors.npkP',
  },
  {
    sensorKey: 'npkK',
    labelKey: 'sensors.npkK',
  },
]

function readSensorValue(sensorData, key) {
  if (!sensorData) {
    return null
  }

  const aliases = {
    soilPct: ['soilPct', 'soil', 'soilMoisturePct'],
    ph: ['ph'],
    tdsPpm: ['tdsPpm', 'tds'],
    tempC: ['tempC', 'temperature', 'temperatureC'],
    humidityPct: ['humidityPct', 'humidity'],
    rainMm: ['rainMm', 'rain'],
    motion: ['motion', 'intrusion'],
    npkN: ['npkN', 'nitrogen'],
    npkP: ['npkP', 'phosphorus'],
    npkK: ['npkK', 'potassium'],
    leafR: ['leafR', 'leaf_r'],
    leafG: ['leafG', 'leaf_g'],
    leafB: ['leafB', 'leaf_b'],
  }

  const keyAliases = aliases[key] || [key]
  const foundAlias = keyAliases.find((alias) => sensorData[alias] !== undefined)
  return foundAlias ? sensorData[foundAlias] : null
}

function classifyLeafHealth(red, green, blue) {
  if (red === null && green === null && blue === null) {
    return '—'
  }
  if (red === 0 && green === 0 && blue === 0) {
    return '—'
  }
  if (green > red && green > blue) {
    return 'Healthy'
  }
  if (red > green * 1.3) {
    return 'Stressed'
  }
  return 'Monitor'
}

export default function SensorGrid() {
  const { t } = useTranslation()
  const { sensorData, isLoading } = useFarm()

  const rawR = readSensorValue(sensorData, 'leafR')
  const leafR = rawR != null ? Number(rawR) : null
  const rawG = readSensorValue(sensorData, 'leafG')
  const leafG = rawG != null ? Number(rawG) : null
  const rawB = readSensorValue(sensorData, 'leafB')
  const leafB = rawB != null ? Number(rawB) : null

  const leafClass = classifyLeafHealth(leafR, leafG, leafB)
  const displayR = leafR ?? 0
  const displayG = leafG ?? 0
  const displayB = leafB ?? 0

  return (
    <section className="page-stack" aria-label={t('nav.dashboard')}>
      <div className="sensor-grid">
        {SENSOR_CONFIG.map((sensor) => {
          const value = readSensorValue(sensorData, sensor.sensorKey)
          const status = getSensorStatus(sensor.sensorKey, value)

          return (
            <SensorCard
              key={sensor.sensorKey}
              sensorKey={sensor.sensorKey}
              value={
                sensor.sensorKey === 'motion'
                  ? value != null
                    ? value
                      ? t('status.motion')
                      : t('status.noMotion')
                    : null
                  : value
              }
              unit={sensor.sensorKey === 'motion' ? '' : t(sensor.unitKey)}
              icon={sensor.icon}
              status={status}
              label={t(sensor.labelKey)}
              isLoading={isLoading}
            />
          )
        })}
      </div>

      <div className="sensor-subgrid">
        {NPK_CONFIG.map((sensor) => {
          const value = readSensorValue(sensorData, sensor.sensorKey)
          return (
            <SensorCard
              key={sensor.sensorKey}
              sensorKey={sensor.sensorKey}
              value={value}
              unit={t('sensors.units.none')}
              icon={Leaf}
              status="ok"
              label={t(sensor.labelKey)}
              isLoading={isLoading}
            />
          )
        })}

        <article className="sensor-card" data-status={leafClass === 'Stressed' ? 'warning' : 'ok'}>
          <header className="sensor-head">
            <div className="sensor-label">{t('sensors.leafColor')}</div>
            <Leaf size={18} className="sensor-icon" aria-hidden="true" />
          </header>

          {isLoading ? (
            <div className="sensor-value">
              <span className="skeleton" style={{ width: '8rem', height: '2rem', borderRadius: 'var(--radius-2)' }} />
            </div>
          ) : (
            <div className="sensor-value leaf-preview">
              <span
                className="leaf-color-dot"
                style={{
                  backgroundColor: leafClass === '—' ? 'var(--color-text-tertiary)' : `rgb(${displayR}, ${displayG}, ${displayB})`,
                }}
                aria-hidden="true"
              />
            </div>
          )}

          <footer className="sensor-status-row">
            <span>{t('dashboard.leafClassification')}</span>
            <span>{leafClass}</span>
          </footer>
        </article>
      </div>
    </section>
  )
}
