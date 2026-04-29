# FarmShield — API Reference

> **Base URL (laptop):** `http://localhost:8000`
> **Base URL (Pi / LAN):** `http://<pi-ip>:8000`
> **All endpoints are prefixed:** `/api/v1/`
> **Interactive docs (Swagger UI):** `http://localhost:8000/docs`

---

## Authentication

When `AUTH_ENABLED=true` (always on Pi), all endpoints except `/api/v1/health` require:

```
Authorization: Bearer <API_KEY>
```

When `AUTH_ENABLED=false` (local dev), the header is optional and ignored.

---

## Common Response Formats

### Error response (all 4xx / 5xx)

```json
{
  "detail": "Human-readable error message",
  "type": "VALIDATION_ERROR | NOT_FOUND | INTERNAL_SERVER_ERROR | UNAUTHORIZED"
}
```

### Timestamps

All timestamps are returned in **ISO 8601 UTC** format:
```
"2026-04-27T17:40:38.720815Z"
```

---

## Endpoints

### 1. Health Check

**`GET /api/v1/health`**

Always returns 200. No authentication required. Safe to poll as a liveness probe.

**Response `200`**

```json
{
  "status": "ok",
  "mqtt_connected": true,
  "db_connected": true,
  "ml_enabled": false,
  "version": "1.0.0"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | Always `"ok"` (endpoint always 200 — MQTT/DB state is informational) |
| `mqtt_connected` | `boolean` | Whether the backend has an active connection to Mosquitto |
| `db_connected` | `boolean` | Whether a DB query succeeded at startup |
| `ml_enabled` | `boolean` | Whether ML inference is enabled via `ML_ENABLED=true` |
| `version` | `string` | Backend version string |

---

### 2. Latest Sensor Reading

**`GET /api/v1/sensors/latest`**

Returns the most recent sensor reading for a device.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `device_id` | `string` | `farmshield_node1` | Target device ID |

**Response `200`**

```json
{
  "time": "2026-04-27T17:40:38.720815Z",
  "device_id": "farmshield_node1",
  "soil_pct": 42.5,

  "tds_ppm": 410.0,
  "temp_c": 29.1,
  "humidity_pct": 58.0,
  "rain_raw": 3200,
  "motion": false,
  "npk_n": 45,
  "npk_p": 30,
  "npk_k": 60,
  "npk_ok": true,
  "leaf_r": 80,
  "leaf_g": 140,
  "leaf_b": 60,
  "pump_on": false,
  "mode": "AUTO",
  "uptime_s": 3601
}
```

**Response `404`** — no readings found for the given `device_id`.

**Field reference**

| Field | Type | Unit | Notes |
|---|---|---|---|
| `time` | `string` (ISO 8601) | — | Timestamp when reading was stored (UTC) |
| `device_id` | `string` | — | Matches firmware `DEVICE_ID` constant |
| `soil_pct` | `float \| null` | % | 0–100, null = sensor failure |

| `tds_ppm` | `float \| null` | ppm | Total dissolved solids |
| `temp_c` | `float \| null` | °C | Air temperature (DHT11) |
| `humidity_pct` | `float \| null` | % | Relative humidity |
| `rain_raw` | `int \| null` | ADC | ~0 = wet, ~4095 = dry |
| `motion` | `bool \| null` | — | PIR sensor state |
| `npk_n` | `int \| null` | mg/kg | Nitrogen |
| `npk_p` | `int \| null` | mg/kg | Phosphorus |
| `npk_k` | `int \| null` | mg/kg | Potassium |
| `npk_ok` | `bool \| null` | — | Whether Modbus NPK read succeeded |
| `leaf_r` | `int \| null` | pulse | TCS3200 red channel |
| `leaf_g` | `int \| null` | pulse | TCS3200 green channel |
| `leaf_b` | `int \| null` | pulse | TCS3200 blue channel |
| `pump_on` | `bool` | — | Current pump relay state |
| `mode` | `string \| null` | — | `"AUTO"` or `"MANUAL"` |
| `uptime_s` | `int \| null` | seconds | Seconds since last ESP32 boot |

---

### 3. Sensor History

**`GET /api/v1/sensors/history`**

Returns paginated historical sensor readings within a lookback window.

**Query parameters**

| Param | Type | Default | Range | Description |
|---|---|---|---|---|
| `device_id` | `string` | `farmshield_node1` | — | Target device |
| `hours` | `int` | `24` | 1–168 | Lookback window (max 7 days) |
| `limit` | `int` | `500` | 1–5000 | Max rows returned |
| `offset` | `int` | `0` | ≥ 0 | Pagination offset |

**Response `200`**

```json
{
  "count": 288,
  "device_id": "farmshield_node1",
  "readings": [
    { ...SensorReadingOut... },
    { ...SensorReadingOut... }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `count` | `int` | Total matching rows (before limit/offset) |
| `device_id` | `string` | Echoed from query param |
| `readings` | `array` | Array of `SensorReadingOut` objects (see endpoint 2) |

---

### 4. Export Sensor Data (CSV)

**`GET /api/v1/sensors/export`**

Downloads sensor readings as a CSV file. Used for offline ML training or data analysis.

**Query parameters**

Same as `/history`: `device_id`, `hours` (1–168), `limit` (1–5000), `offset`.

**Response `200`**

- `Content-Type: text/csv; charset=utf-8`
- `Content-Disposition: attachment; filename=farmshield_export.csv`

```csv
time,device_id,soil_pct,tds_ppm,temp_c,humidity_pct,rain_raw,motion,npk_n,npk_p,npk_k,leaf_r,leaf_g,leaf_b,pump_on
2026-04-27T17:40:38+00:00,farmshield_node1,42.5,410.0,29.1,58.0,3200,False,45,30,60,80,140,60,False
```

**Example download:**

```bash
curl "http://localhost:8000/api/v1/sensors/export?hours=168" -o data.csv
```

---

### 5. List Alerts

**`GET /api/v1/alerts`**

Returns threshold-generated alerts, newest first.

**Query parameters**

| Param | Type | Default | Description |
|---|---|---|---|
| `device_id` | `string` | `farmshield_node1` | Target device |
| `limit` | `int` | `50` | Max alerts (1–500) |
| `unacknowledged_only` | `bool` | `false` | Filter to unacked alerts only |

**Response `200`**

```json
{
  "count": 2,
  "alerts": [
    {
      "id": "8c774ef8-3b85-48e9-8d96-88ca36ef685c",
      "time": "2026-04-27T17:40:38.136493Z",
      "device_id": "farmshield_node1",
      "type": "SOIL_DRY",
      "severity": "WARNING",
      "message": "Soil moisture below threshold (22.5% < 30.0%)",
      "acknowledged": false
    }
  ]
}
```

**Alert types and severities**

| `type` | `severity` | Trigger condition |
|---|---|---|
| `SOIL_DRY` | `WARNING` | `soil_pct < ALERT_SOIL_DRY_PCT` (default 30%) |
| `SOIL_FLOOD` | `WARNING` | `soil_pct > ALERT_SOIL_FLOOD_PCT` (default 85%) |
| `TEMP_HIGH` | `WARNING` | `temp_c > ALERT_TEMP_HIGH_C` (default 38°C) |

| `TDS_HIGH` | `WARNING` | `tds_ppm > ALERT_TDS_HIGH_PPM` (default 1500) |
| `RAIN_DRY` | `INFO` | `rain_raw > ALERT_RAIN_DRY_RAW` (default 2500) |
| `MOTION` | `INFO` | `motion == true` |

Thresholds are configurable in `.env`.

---

### 6. Acknowledge Alert

**`PATCH /api/v1/alerts/{alert_id}/acknowledge`**

Marks an alert as acknowledged. Acknowledged alerts are excluded from `unacknowledged_only=true` queries.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `alert_id` | `UUID` | Alert UUID from the list response |

**Request body** — none

**Response `200`**

```json
{
  "id": "8c774ef8-3b85-48e9-8d96-88ca36ef685c",
  "time": "2026-04-27T17:40:38.136493Z",
  "device_id": "farmshield_node1",
  "type": "SOIL_DRY",
  "severity": "WARNING",
  "message": "Soil moisture below threshold (22.5% < 30.0%)",
  "acknowledged": true
}
```

**Response `404`** — alert ID not found.

---

### 7. Control — Pump

**`POST /api/v1/control/pump`**

Turns the irrigation pump on or off. Publishes a raw `ON` or `OFF` string to `farmshield/control/pump`.

**Request body**

```json
{ "state": "ON" }
```

| Field | Type | Allowed values |
|---|---|---|
| `state` | `string` | `"ON"` or `"OFF"` |

**Response `200`**

```json
{
  "command": "pump",
  "state": "ON",
  "published": true,
  "ts": 1777311661
}
```

| Field | Type | Description |
|---|---|---|
| `command` | `string` | Always `"pump"` |
| `state` | `string` | Echoed from request |
| `published` | `bool` | Whether the MQTT publish succeeded |
| `ts` | `int` | Unix timestamp of the publish |

**Response `422`** — invalid state value (anything other than `"ON"` / `"OFF"`).

---

### 8. Control — Mode

**`POST /api/v1/control/mode`**

Sets the ESP32 operating mode. Publishes `AUTO` or `MANUAL` to `farmshield/control/mode`.

In `AUTO` mode the firmware manages irrigation autonomously. In `MANUAL` mode it only responds to pump commands.

**Request body**

```json
{ "state": "MANUAL" }
```

| Field | Type | Allowed values |
|---|---|---|
| `state` | `string` | `"AUTO"` or `"MANUAL"` |

**Response `200`** — same shape as pump response, `command` = `"mode"`.

**Response `422`** — invalid state value.

---

### 9. Control — Buzzer

**`POST /api/v1/control/buzzer`**

Silences the buzzer remotely. Publishes `OFF` to `farmshield/control/buzzer`.

> **Note:** Only `"OFF"` is accepted by the API — buzzer activation is handled autonomously by the firmware based on sensor alerts. This is an intentional product restriction.

**Request body**

```json
{ "state": "OFF" }
```

| Field | Type | Allowed values |
|---|---|---|
| `state` | `string` | `"OFF"` only |

**Response `200`** — same shape as pump response, `command` = `"buzzer"`.

**Response `422`** — any value other than `"OFF"`.

---

### 10. WebSocket — Live Feed

**`WS /api/v1/ws/live`**

Real-time sensor readings and alerts pushed to the client as they are ingested from the ESP32.

**Connection URL**

```
ws://localhost:8000/api/v1/ws/live
```

With authentication (when `AUTH_ENABLED=true`):

```
ws://localhost:8000/api/v1/ws/live?api_key=<API_KEY>
```

**Messages from server → client**

**Sensor reading** (every ~5 s, triggered by ESP32 publish):

```json
{
  "type": "sensor_reading",
  "data": {
    "time": "2026-04-27T17:40:38.720815Z",
    "device_id": "farmshield_node1",
    "soil_pct": 42.5,

    "tds_ppm": 410.0,
    "temp_c": 29.1,
    "humidity_pct": 58.0,
    "rain_raw": 3200,
    "motion": false,
    "npk_n": 45,
    "npk_p": 30,
    "npk_k": 60,
    "npk_ok": true,
    "leaf_r": 80,
    "leaf_g": 140,
    "leaf_b": 60,
    "pump_on": false,
    "mode": "AUTO",
    "uptime_s": 3601
  }
}
```

**Alert** (when a threshold breach is detected):

```json
{
  "type": "alert",
  "data": {
    "id": "8c774ef8-3b85-48e9-8d96-88ca36ef685c",
    "time": "2026-04-27T17:40:38.136493Z",
    "device_id": "farmshield_node1",
    "type": "SOIL_DRY",
    "severity": "WARNING",
    "message": "Soil moisture below threshold (22.5% < 30.0%)",
    "acknowledged": false
  }
}
```

**ML output** (only when `ML_ENABLED=true`, appended to sensor reading):

```json
{
  "type": "sensor_reading",
  "data": { ...SensorReadingOut... },
  "ml_output": {
    "action": "IRRIGATE",
    "confidence": 0.91
  }
}
```

**Messages from client → server**

**Ping** (keep-alive):

```json
{ "type": "ping" }
```

**Server response:**

```json
{ "type": "pong" }
```

**JavaScript connection example**

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/live');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'sensor_reading') {
    const d = msg.data;
    console.log(`Temp: ${d.temp_c}°C  Soil: ${d.soil_pct}%  Mode: ${d.mode}`);
  }

  if (msg.type === 'alert') {
    console.warn(`[${msg.data.severity}] ${msg.data.type}: ${msg.data.message}`);
  }
};

// Keep-alive ping every 30 s
setInterval(() => ws.send(JSON.stringify({ type: 'ping' })), 30000);
```

---

## Quick Reference — All Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/health` | ❌ No | Health + connectivity status |
| `GET` | `/api/v1/sensors/latest` | ✅ Yes | Latest sensor reading |
| `GET` | `/api/v1/sensors/history` | ✅ Yes | Paginated history |
| `GET` | `/api/v1/sensors/export` | ✅ Yes | CSV download |
| `GET` | `/api/v1/alerts` | ✅ Yes | List alerts (filterable) |
| `PATCH` | `/api/v1/alerts/{id}/acknowledge` | ✅ Yes | Acknowledge an alert |
| `POST` | `/api/v1/control/pump` | ✅ Yes | Pump ON/OFF |
| `POST` | `/api/v1/control/mode` | ✅ Yes | AUTO/MANUAL mode |
| `POST` | `/api/v1/control/buzzer` | ✅ Yes | Silence buzzer |
| `WS` | `/api/v1/ws/live` | ✅ Yes* | Live sensor + alert stream |

*WebSocket auth via query param: `?api_key=<key>`
