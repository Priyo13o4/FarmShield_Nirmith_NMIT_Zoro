const SENSOR_THRESHOLDS = {
  soilPct: {
    criticalBelow: 30,
    warningAbove: 85,
  },
  ph: {
    warningBelow: 5.5,
    warningAbove: 7.5,
  },
  tdsPpm: {
    warningAbove: 1500,
  },
  tempC: {
    warningAbove: 38,
  },
}

export function getSensorStatus(key, value) {
  if (value === null || value === undefined) {
    return 'unknown'
  }

  if (key === 'motion') {
    return value ? 'critical' : 'ok'
  }

  if (key === 'soilPct') {
    if (value < SENSOR_THRESHOLDS.soilPct.criticalBelow) {
      return 'critical'
    }
    if (value > SENSOR_THRESHOLDS.soilPct.warningAbove) {
      return 'warning'
    }
    return 'ok'
  }

  if (key === 'ph') {
    if (
      value < SENSOR_THRESHOLDS.ph.warningBelow ||
      value > SENSOR_THRESHOLDS.ph.warningAbove
    ) {
      return 'warning'
    }
    return 'ok'
  }

  if (key === 'tdsPpm') {
    return value > SENSOR_THRESHOLDS.tdsPpm.warningAbove ? 'warning' : 'ok'
  }

  if (key === 'tempC') {
    return value > SENSOR_THRESHOLDS.tempC.warningAbove ? 'warning' : 'ok'
  }

  return 'ok'
}
