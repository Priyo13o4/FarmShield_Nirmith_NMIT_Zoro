import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTranslation } from 'react-i18next'

import Skeleton from '../common/Skeleton'

const CHART_HEIGHT = 'var(--chart-height)'

const SENSOR_LINE_COLOR = {
  soilPct: 'var(--chart-soil)',
  ph: 'var(--chart-ph)',
  tdsPpm: 'var(--chart-tds)',
  tempC: 'var(--chart-temp)',
  humidityPct: 'var(--chart-humidity)',
  rainMm: 'var(--chart-rain)',
}

function CustomTooltip({ active, payload, label, t }) {
  if (!active || !payload?.length) {
    return null
  }

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{label}</div>
      {payload.map((lineItem) => (
        <div className="chart-tooltip-item" key={lineItem.dataKey}>
          <span>{t(`sensors.${lineItem.dataKey.replace('Pct', '').replace('Mm', '').replace('C', '').replace('Ppm', '')}`, lineItem.dataKey)}</span>
          <span>{lineItem.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function SensorChart({ data, selectedSensors, isLoading, emptyState }) {
  const { t } = useTranslation()

  if (isLoading) {
    return <Skeleton width="100%" height={CHART_HEIGHT} borderRadius="var(--radius-4)" />
  }

  if (!data?.length || !selectedSensors?.length) {
    return emptyState
  }

  return (
    <div className="chart-wrap">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 12, right: 16, left: 8, bottom: 8 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="timestampLabel"
            tick={{ fill: 'var(--color-text-tertiary)', fontSize: 12 }}
            axisLine={{ stroke: 'var(--color-border)' }}
            tickLine={{ stroke: 'var(--color-border)' }}
          />
          <YAxis
            tick={{ fill: 'var(--color-text-tertiary)', fontSize: 12 }}
            axisLine={{ stroke: 'var(--color-border)' }}
            tickLine={{ stroke: 'var(--color-border)' }}
          />
          <Tooltip content={<CustomTooltip t={t} />} />
          {selectedSensors.map((sensorKey) => (
            <Line
              key={sensorKey}
              type="monotone"
              dataKey={sensorKey}
              stroke={SENSOR_LINE_COLOR[sensorKey] || 'var(--color-primary)'}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
