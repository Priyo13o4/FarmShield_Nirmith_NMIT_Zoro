Here it is — the full PRD inline.

***

# FarmShield Backend — Product Requirements Document

**Version:** 1.0.0
**Status:** Final
**Scope:** Backend only (data ingestion, storage, ML inference, REST + WebSocket API). Frontend is explicitly out of scope.

***

## 1. Purpose & Goals

FarmShield is an edge-AI smart agriculture system. This PRD defines the backend software stack that bridges an ESP32 sensor node and any frontend consumer. The backend must:

- Receive continuous sensor telemetry from one ESP32 over MQTT
- Persist all readings to a time-series database
- Optionally run tabular ML inference on every ingested reading
- Expose a REST API and a live WebSocket stream
- Run identically on a developer laptop and a Raspberry Pi 4B using a single Docker Compose file where the only difference is values in a `.env` file
- Be modular enough that a new sensor, endpoint, or ML model can be added by touching the minimum number of files with zero ambiguity about where that change belongs

***

## 2. Hard Constraints

| Constraint | Value |
|---|---|
| Python version | **3.13** (enforced in Dockerfile base image) |
| TimescaleDB | **2.26.3** on PostgreSQL 18 (`timescale/timescaledb:2.26.3-pg18`) |
| All other dependencies | Latest stable at time of build — no pinned old versions |
| Fallbacks / silent error swallowing | **Prohibited.** Every failure must raise an exception and be logged. If a fallback is unavoidable it must be gated behind an explicit env var and documented in `.env.example` |
| Configuration drift | All tuneable values live in `.env`. No magic strings buried in source code |
| Frontend | Out of scope. The backend exposes contracts, not pages |
| Cloud dependency | None(AS OF THIS PRD). System must function entirely offline on LAN |

***

## 3. Technology Stack

### 3.1 Runtime & Framework

| Component | Package | Minimum Version | Notes |
|---|---|---|---|
| Language | Python | 3.13 | Enforced via Docker `FROM python:3.13-slim` |
| Web framework | `fastapi` | ≥ 0.115.0 | Latest stable |
| ASGI server | `uvicorn[standard]` | ≥ 0.34.0 | With `uvloop` + `httptools` |
| Data validation | `pydantic` | ≥ 2.11.0 | v2 only — no v1 compat shims |
| Config management | `pydantic-settings` | ≥ 2.7.0 | `.env` → typed `Settings` class |

### 3.2 Database

| Component | Package | Minimum Version | Notes |
|---|---|---|---|
| Time-series DB | `timescale/timescaledb:2.26.3-pg16` | **Exact image tag** | Docker image |
| Async ORM | `sqlalchemy[asyncio]` | ≥ 2.0.40 | 2.x async API only |
| Async PG driver | `asyncpg` | ≥ 0.30.0 | Used by SQLAlchemy under the hood |
| Migrations | `alembic` | ≥ 1.14.0 | Run inside the FastAPI container on startup |

### 3.3 Messaging

| Component | Package / Image | Version | Notes |
|---|---|---|---|
| MQTT Broker | `eclipse-mosquitto` | `2` (Docker latest) | Runs as its own container |
| MQTT Client (FastAPI) | `fastapi-mqtt` | ≥ 2.2.0 | Built on `gmqtt`, fully async |

### 3.4 Observability

| Component | Package | Minimum Version | Notes |
|---|---|---|---|
| Structured logging | `structlog` | ≥ 25.0.0 | JSON output in prod, pretty-print in dev |

### 3.5 Testing

| Component | Package | Minimum Version |
|---|---|---|
| Test runner | `pytest` | ≥ 8.0.0 |
| Async test support | `pytest-asyncio` | ≥ 0.25.0 |
| HTTP test client | `httpx` | ≥ 0.28.0 |
| Test env overrides | `pytest` fixtures + `pydantic-settings` | — |

### 3.6 Infrastructure

| Component | Version |
|---|---|
| Docker Engine | ≥ 27.x |
| Docker Compose | v2 (plugin, not standalone) |

***

## 4. Repository Layout

```
farmshield-backend/
├── .env.example                        ← CANONICAL config reference (all vars documented)
├── .env                                ← Local overrides — never commit
├── docker-compose.yml
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
└── server/
    ├── Dockerfile
    ├── pyproject.toml
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py
    │   └── versions/
    │       └── 0001_initial.py         ← Baseline schema migration
    └── app/
        ├── main.py
        ├── config.py
        ├── dependencies.py
        ├── api/
        │   └── v1/
        │       ├── router.py
        │       ├── sensors.py
        │       ├── control.py
        │       ├── alerts.py
        │       ├── health.py
        │       └── ws.py
        ├── core/
        │   ├── auth.py
        │   ├── logging.py
        │   └── exceptions.py
        ├── db/
        │   ├── session.py
        │   └── models.py
        ├── schemas/
        │   ├── sensor.py
        │   ├── control.py
        │   └── alert.py
        ├── services/
        │   ├── ingestion.py
        │   ├── sensor.py
        │   ├── control.py
        │   ├── alert.py
        │   ├── websocket.py
        │   └── ml/
        │       ├── runner.py
        │       └── models/             ← Drop .pkl / .tflite files here at runtime
        └── mqtt/
            ├── client.py
            └── handlers.py
tests/
├── conftest.py
├── test_sensors.py
├── test_control.py
├── test_ingestion.py
└── test_ml.py
```

***

## 5. Environment Configuration Reference

The `.env.example` file is the single source of truth for all configuration. Every variable below **must** appear in `.env.example` with an inline comment explaining it. No variable may be hardcoded anywhere in application source.

```dotenv
# =============================================================================
# FARMSHIELD BACKEND — ENVIRONMENT CONFIGURATION
# Copy this file to .env and fill in values.
# For laptop dev: leave MQTT_BROKER_HOST and DB_HOST as "localhost" equivalents.
# For Pi deployment: update the IP fields to your Pi's LAN IP where needed,
# and set ESP32_MQTT_HOST to the Pi's LAN IP so the ESP32 can reach Mosquitto.
# =============================================================================

# -----------------------------------------------------------------------------
# DEPLOYMENT TARGET
# Used for documentation only — does not change code behaviour.
# Set to "laptop" or "pi" so team members know which context this .env is for.
# -----------------------------------------------------------------------------
TARGET_ENV=laptop

# -----------------------------------------------------------------------------
# NETWORK — ESP32 FIRMWARE REFERENCE
# This is the IP the ESP32 must be pointed at in its firmware.
# On laptop: your machine's LAN IP (e.g. 192.168.1.10)
# On Pi: the Pi's LAN IP (e.g. 192.168.1.50)
# This value is NOT read by the backend — it is here as a reminder.
# -----------------------------------------------------------------------------
ESP32_MQTT_TARGET_IP=192.168.1.10

# -----------------------------------------------------------------------------
# FASTAPI
# -----------------------------------------------------------------------------
FASTAPI_HOST=0.0.0.0        # Bind address inside the container
FASTAPI_PORT=8000            # Exposed port on the host
FASTAPI_RELOAD=true          # Set to false in Pi/production deployment

# -----------------------------------------------------------------------------
# MQTT BROKER (Mosquitto container)
# The backend connects to the broker using MQTT_BROKER_HOST.
# Inside Docker Compose, this is always "mosquitto" (service name).
# If running the backend outside Docker, set to "localhost".
# -----------------------------------------------------------------------------
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MQTT_USERNAME=farmshield
MQTT_PASSWORD=farmshield123
MQTT_CLIENT_ID=farmshield-backend
MQTT_QOS=1                   # 0 = fire and forget | 1 = at least once
MQTT_TOPIC_SENSORS=farmshield/sensors       # ESP32 publishes here
MQTT_TOPIC_CONTROL=farmshield/control       # Backend publishes pump/mode/buzzer commands here
MQTT_TOPIC_ALERTS=farmshield/alerts         # Backend publishes generated alerts here

# -----------------------------------------------------------------------------
# DATABASE (TimescaleDB / PostgreSQL)
# Inside Docker Compose, DB_HOST is always "timescaledb" (service name).
# If running the backend outside Docker, set to "localhost".
# -----------------------------------------------------------------------------
DB_HOST=timescaledb
DB_PORT=5432
DB_NAME=farmshield
DB_USER=farmshield
DB_PASSWORD=farmshield123
DB_POOL_SIZE=5               # SQLAlchemy async pool size — reduce to 3 on Pi
DB_POOL_MAX_OVERFLOW=10

# -----------------------------------------------------------------------------
# AUTHENTICATION
# AUTH_ENABLED=true enforces Bearer API key on all endpoints except /health.
# AUTH_ENABLED=false disables auth entirely — single config change, no code change.
# API_KEY must be a strong random string in production.
# -----------------------------------------------------------------------------
AUTH_ENABLED=true
API_KEY=changeme-replace-with-random-string

# -----------------------------------------------------------------------------
# ML INFERENCE
# ML_ENABLED=false disables all ML inference with zero performance cost.
# ML_MODEL_PATH is relative to the server/ directory.
# ML_MODEL_TYPE: "sklearn" (.pkl via joblib) | "tflite" (.tflite)
# When ML_ENABLED=true and the model file is missing, the app must FAIL at startup
# with a clear error — not silently skip inference.
# -----------------------------------------------------------------------------
ML_ENABLED=false
ML_MODEL_PATH=app/services/ml/models/irrigation_model.pkl
ML_MODEL_TYPE=sklearn         # "sklearn" or "tflite"

# -----------------------------------------------------------------------------
# DATA RETENTION
# TimescaleDB drop policy: raw rows older than RETENTION_DAYS are deleted.
# Default 7 days is sufficient for demo purposes.
# Set to 0 to disable automatic data drop.
# -----------------------------------------------------------------------------
RETENTION_DAYS=7

# -----------------------------------------------------------------------------
# LOGGING
# LOG_LEVEL: DEBUG | INFO | WARNING | ERROR
# LOG_JSON: true = machine-readable JSON output (use in Pi/prod)
#           false = human-readable coloured output (use on laptop/dev)
# -----------------------------------------------------------------------------
LOG_LEVEL=INFO
LOG_JSON=false
```

***

## 6. Docker Compose Specification

```yaml
# docker-compose.yml
# All tuneable values are injected from .env
# Run: docker compose up --build
# Pi deployment: update .env and run the same command

services:

  mosquitto:
    image: eclipse-mosquitto:2
    container_name: farmshield-mosquitto
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mosquitto_pub", "-h", "localhost", "-t", "healthcheck", "-m", "ping", "-u", "${MQTT_USERNAME}", "-P", "${MQTT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 3

  timescaledb:
    image: timescale/timescaledb:2.26.3-pg16
    container_name: farmshield-timescaledb
    ports:
      - "${DB_PORT}:5432"
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    command: >
      postgres
        -c shared_buffers=256MB
        -c work_mem=4MB
        -c maintenance_work_mem=64MB
        -c effective_cache_size=512MB
        -c max_connections=50
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5

  fastapi:
    build:
      context: ./server
      dockerfile: Dockerfile
    container_name: farmshield-fastapi
    ports:
      - "${FASTAPI_PORT}:8000"
    env_file:
      - .env
    depends_on:
      timescaledb:
        condition: service_healthy
      mosquitto:
        condition: service_healthy
    volumes:
      - ./server:/app               # Live reload in dev (FASTAPI_RELOAD=true)
      - ./server/app/services/ml/models:/app/app/services/ml/models  # ML model hot-drop
    restart: unless-stopped

volumes:
  timescaledb_data:
  mosquitto_data:
  mosquitto_log:
```

### 6.1 Mosquitto Configuration

```conf
# mosquitto/config/mosquitto.conf
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd

# Persistence
persistence true
persistence_location /mosquitto/data/

# Logging
log_dest stdout
log_type error
log_type warning
log_type notice
log_type information
```

> **Note:** The password file must be generated once with `mosquitto_passwd`. Add a `mosquitto_passwd` generation step to the project README. The username/password must match `MQTT_USERNAME` / `MQTT_PASSWORD` in `.env`.

### 6.2 Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# System deps for asyncpg compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY . .

# Run Alembic migrations then start Uvicorn
CMD alembic upgrade head && \
    uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
```

> The `--reload` flag is controlled by the process, not the Dockerfile. For Pi deployment, override `CMD` in `docker-compose.override.yml` or remove `--reload` when `FASTAPI_RELOAD=false`. The simplest approach: read `FASTAPI_RELOAD` in a shell entrypoint script and construct the uvicorn command conditionally.

***

## 7. Application Architecture

### 7.1 File Responsibilities

Every file has exactly one responsibility. Adding a feature means identifying one correct file per layer.

| File | Responsibility | What belongs here | What does NOT belong here |
|---|---|---|---|
| `main.py` | App factory + lifespan | `FastAPI()` instance, `lifespan` context manager (MQTT start/stop, DB pool), include all routers, register exception handlers | Business logic, DB queries |
| `config.py` | Settings | One `Settings` class using `pydantic-settings`, reads from `.env`. Exported as a singleton `settings = Settings()`. All env vars are typed attributes | Hardcoded values, logic |
| `dependencies.py` | FastAPI DI | `get_db()` (async session), `require_auth()` (API key check, reads `AUTH_ENABLED`). These are `Depends()` callables only | Business logic |
| `api/v1/router.py` | Router aggregation | `APIRouter` that includes `sensors`, `control`, `alerts`, `health` sub-routers with their prefixes and tags | Any logic |
| `api/v1/*.py` | Route handlers | HTTP method + path, input validation via Pydantic schema, call exactly one service function, return schema | DB queries, MQTT publish, ML calls |
| `core/auth.py` | Auth logic | `verify_api_key()` function that checks `Authorization: Bearer <key>` header against `settings.API_KEY`. Returns 401 if `AUTH_ENABLED=true` and key is wrong. Is a no-op if `AUTH_ENABLED=false` | Business logic |
| `core/logging.py` | Logging setup | `configure_logging()` that sets up structlog with JSON or pretty renderer based on `LOG_JSON`. Called once in `main.py` lifespan | Logging calls (those happen in services) |
| `core/exceptions.py` | Exception handlers | `@app.exception_handler` registrations for `HTTPException`, `RequestValidationError`, unhandled `Exception`. All return structured JSON `{"detail": ..., "type": ...}` | Raising exceptions (that happens in services) |
| `db/session.py` | DB connection | `async_engine`, `AsyncSessionLocal`, `Base` (declarative base). Exports `get_async_session()` context manager | ORM models, queries |
| `db/models.py` | ORM models | SQLAlchemy `Table` / `MappedClass` definitions matching the TimescaleDB schema exactly | Query logic |
| `schemas/sensor.py` | Sensor Pydantic models | `SensorPayload` (raw MQTT), `SensorReadingOut` (API response), `SensorHistoryParams` (query params) | DB models |
| `schemas/control.py` | Control Pydantic models | `PumpCommand`, `ModeCommand`, `BuzzerCommand`, `ControlResponse` | — |
| `schemas/alert.py` | Alert Pydantic models | `AlertOut`, `AlertListResponse` | — |
| `services/ingestion.py` | MQTT ingestion pipeline | Validate payload → write to DB → conditionally call ML runner → broadcast to WebSocket manager → conditionally generate alert. This is the hottest path in the system | HTTP routing, MQTT client setup |
| `services/sensor.py` | Sensor query logic | `get_latest()`, `get_history(hours)` async functions that accept a DB session and return typed results | HTTP concerns |
| `services/control.py` | Control dispatch | `send_pump_command()`, `send_mode_command()`, `send_buzzer_command()` — publish MQTT command + log | DB writes for commands |
| `services/alert.py` | Alert logic | `create_alert()`, `get_alerts(limit)` | ML inference |
| `services/websocket.py` | WS connection manager | `ConnectionManager` class: `connect()`, `disconnect()`, `broadcast(data)`. Maintains a `set` of active `WebSocket` connections | Route handling |
| `services/ml/runner.py` | ML inference | `load_model()` at startup (raises if file missing and `ML_ENABLED=true`), `predict(features: dict) -> dict` at inference time. Handles both `sklearn` and `tflite` based on `ML_MODEL_TYPE` | Model training, data collection |
| `mqtt/client.py` | MQTT client instance | `MQTTConfig` + `FastMQTT` instance creation using `settings`. Exported as `mqtt_client` singleton. No handlers here | Business logic |
| `mqtt/handlers.py` | Topic handlers | `@mqtt_client.on_message()` and `@mqtt_client.on_connect()` decorators. On connect: subscribe to `MQTT_TOPIC_SENSORS`. On message: parse JSON, call `ingestion.process()` | DB access directly (must go through services) |

### 7.2 Request Lifecycle

```
ESP32 publishes JSON to farmshield/sensors (QoS 1)
  │
  ▼
Mosquitto broker (container) receives, acknowledges
  │
  ▼
mqtt/handlers.py  on_message()
  │  → parse raw bytes to dict
  │  → call services/ingestion.process(payload)
  │
  ▼
services/ingestion.process()
  ├─ Validate with schemas/sensor.SensorPayload (raises ValidationError → logged, dropped)
  ├─ Write to TimescaleDB via db/models + async session
  ├─ if ML_ENABLED: call services/ml/runner.predict(features)
  │     → append inference result to DB row or separate table (see §9.3)
  ├─ services/websocket.broadcast(reading + inference result)
  └─ Evaluate alert thresholds → if breach: services/alert.create_alert()
       └─ Publish to MQTT_TOPIC_ALERTS
```

***

## 8. MQTT Contract

### 8.1 ESP32 → Backend (Sensor Topic)

**Topic:** value of `MQTT_TOPIC_SENSORS` (default: `farmshield/sensors`)
**Direction:** ESP32 publishes, backend subscribes
**QoS:** value of `MQTT_QOS` (default: 1)
**Frequency:** every 5 seconds
**Payload:** UTF-8 JSON, no trailing newline

```json
{
  "device_id": "esp32-node-1",
  "soil_pct": 42.5,
  "ph": 6.81,
  "tds_ppm": 410.0,
  "temp_c": 29.1,
  "humidity_pct": 58.0,
  "rain_raw": 3200,
  "motion": false,
  "npk_n": 45,
  "npk_p": 30,
  "npk_k": 60,
  "leaf_r": 80,
  "leaf_g": 140,
  "leaf_b": 60,
  "pump_on": false,
  "ts": 1745678901
}
```

**Field notes:**
- `ts` is a Unix timestamp (seconds, integer) set by the ESP32. The backend stores this as the authoritative `time` column. If absent or unparseable, the backend uses `NOW()` — this fallback **must** be logged as a warning.
- All numeric fields are optional in the Pydantic schema (nullable) to tolerate individual sensor failures. A payload with no numeric fields at all must be rejected with a logged error.
- `device_id` is required. Unknown device IDs are accepted and stored as-is (single-node now, but field is preserved for future multi-node).

### 8.2 Backend → ESP32 (Control Topic)

**Topic:** value of `MQTT_TOPIC_CONTROL` (default: `farmshield/control`)
**Direction:** Backend publishes, ESP32 subscribes
**QoS:** 1

```json
{ "command": "pump",   "state": "ON"     }
{ "command": "pump",   "state": "OFF"    }
{ "command": "mode",   "state": "AUTO"   }
{ "command": "mode",   "state": "MANUAL" }
{ "command": "buzzer", "state": "OFF"    }
```

### 8.3 Backend → Alert Topic

**Topic:** value of `MQTT_TOPIC_ALERTS` (default: `farmshield/alerts`)
**Direction:** Backend publishes

```json
{
  "alert_id": "uuid-v4",
  "type": "SOIL_DRY",
  "severity": "WARNING",
  "message": "Soil moisture below threshold (42.5% < 30%)",
  "ts": 1745678901
}
```

***

## 9. Database Schema

### 9.1 `sensor_readings` (Hypertable)

```sql
CREATE TABLE sensor_readings (
    time            TIMESTAMPTZ     NOT NULL,
    device_id       TEXT            NOT NULL    DEFAULT 'esp32-node-1',
    soil_pct        DOUBLE PRECISION,
    ph              DOUBLE PRECISION,
    tds_ppm         DOUBLE PRECISION,
    temp_c          DOUBLE PRECISION,
    humidity_pct    DOUBLE PRECISION,
    rain_raw        INTEGER,
    motion          BOOLEAN,
    npk_n           INTEGER,
    npk_p           INTEGER,
    npk_k           INTEGER,
    leaf_r          SMALLINT,
    leaf_g          SMALLINT,
    leaf_b          SMALLINT,
    pump_on         BOOLEAN         NOT NULL    DEFAULT FALSE
);

SELECT create_hypertable('sensor_readings', 'time');

-- Index for device-scoped queries
CREATE INDEX ON sensor_readings (device_id, time DESC);
```

### 9.2 `alerts`

```sql
CREATE TABLE alerts (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    time        TIMESTAMPTZ     NOT NULL    DEFAULT NOW(),
    device_id   TEXT            NOT NULL,
    type        TEXT            NOT NULL,
    severity    TEXT            NOT NULL    CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    message     TEXT            NOT NULL,
    acknowledged BOOLEAN        NOT NULL    DEFAULT FALSE
);

CREATE INDEX ON alerts (device_id, time DESC);
```

### 9.3 `ml_inferences`

Created only if `ML_ENABLED=true`. The Alembic migration for this table must be conditional on a runtime check, or simply always created (empty table has zero cost).

```sql
CREATE TABLE ml_inferences (
    time            TIMESTAMPTZ     NOT NULL,
    device_id       TEXT            NOT NULL,
    model_name      TEXT            NOT NULL,
    input_features  JSONB           NOT NULL,
    output          JSONB           NOT NULL,
    inference_ms    DOUBLE PRECISION
);

SELECT create_hypertable('ml_inferences', 'time');
```

### 9.4 Data Retention Policy

Applied at app startup via `services/ingestion.py` calling raw SQL on the DB session. The value of `RETENTION_DAYS` drives this. If `RETENTION_DAYS=0`, the policy is not applied.

```sql
-- Applied to sensor_readings
SELECT add_retention_policy('sensor_readings',
       INTERVAL '7 days',   -- parameterised from RETENTION_DAYS
       if_not_exists => TRUE);
```

***

## 10. API Endpoints

All endpoints require `Authorization: Bearer <API_KEY>` header when `AUTH_ENABLED=true`. The `/health` endpoint is **always public** regardless of `AUTH_ENABLED`.

Base path: `/api/v1`

### 10.1 Health

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | ❌ Public | Liveness check |

**Response 200:**
```json
{
  "status": "ok",
  "mqtt_connected": true,
  "db_connected": true,
  "ml_enabled": false,
  "version": "1.0.0"
}
```

### 10.2 Sensors

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/sensors/latest` | ✅ | Most recent reading for `device_id` |
| `GET` | `/sensors/history` | ✅ | Paginated historical readings |

**`GET /sensors/latest` — Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `device_id` | `string` | `esp32-node-1` | Target device |

**Response 200:** Single `SensorReadingOut` object (see §11).

**`GET /sensors/history` — Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `device_id` | `string` | `esp32-node-1` | Target device |
| `hours` | `int` | `24` | Lookback window (max 168 = 7 days) |
| `limit` | `int` | `500` | Max rows returned (max 5000) |
| `offset` | `int` | `0` | Pagination offset |

**Response 200:**
```json
{
  "count": 288,
  "device_id": "esp32-node-1",
  "readings": [ ...SensorReadingOut... ]
}
```

### 10.3 Control

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/control/pump` | ✅ | Turn pump ON or OFF |
| `POST` | `/control/mode` | ✅ | Switch AUTO / MANUAL |
| `POST` | `/control/buzzer` | ✅ | Silence buzzer |

**`POST /control/pump` — Request body:**
```json
{ "state": "ON" }
```
`state` must be `"ON"` or `"OFF"`. Any other value returns 422.

**`POST /control/mode` — Request body:**
```json
{ "state": "AUTO" }
```
`state` must be `"AUTO"` or `"MANUAL"`.

**`POST /control/buzzer` — Request body:**
```json
{ "state": "OFF" }
```
`state` must be `"OFF"`. Only silencing is supported from the API.

**All control responses 200:**
```json
{
  "command": "pump",
  "state": "ON",
  "published": true,
  "ts": 1745678901
}
```

### 10.4 Alerts

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/alerts` | ✅ | List recent alerts |
| `PATCH` | `/alerts/{alert_id}/acknowledge` | ✅ | Mark alert acknowledged |

**`GET /alerts` — Query params:**

| Param | Type | Default | Description |
|---|---|---|---|
| `device_id` | `string` | `esp32-node-1` | Target device |
| `limit` | `int` | `50` | Max alerts returned |
| `unacknowledged_only` | `bool` | `false` | Filter to unacked only |

**Response 200:**
```json
{
  "count": 3,
  "alerts": [ ...AlertOut... ]
}
```

### 10.5 WebSocket

| Protocol | Path | Auth | Description |
|---|---|---|---|
| `WS` | `/ws/live` | ✅ (query param) | Live sensor stream |

**Connection URL:** `ws://<host>:<port>/api/v1/ws/live?api_key=<API_KEY>`

Auth is passed as a query parameter since WebSocket clients cannot set `Authorization` headers. If `AUTH_ENABLED=false`, the `api_key` param is accepted but not validated.

**Server → Client message** (pushed on every MQTT ingestion):
```json
{
  "type": "sensor_reading",
  "data": { ...SensorReadingOut... },
  "ml_output": { "irrigation_score": 0.82, "action": "IRRIGATE" }
}
```

`ml_output` key is omitted entirely when `ML_ENABLED=false`.

**Server → Client on alert:**
```json
{
  "type": "alert",
  "data": { ...AlertOut... }
}
```

Client → Server ping (keep-alive):
```json
{ "type": "ping" }
```
Server responds:
```json
{ "type": "pong" }
```

***

## 11. Pydantic Schemas # NOTE : AMBIGUIDTY HERE , SCHEMA MISSING REQUEST BODIES , INFER FROM CONTEXT FROM ABOVE

### `SensorReadingOut`
```python
class SensorReadingOut(BaseModel):
    time: datetime
    device_id: str
    soil_pct: float | None
    ph: float | None
    tds_ppm: float | None
    temp_c: float | None
    humidity_pct: float | None
    rain_raw: int | None
    motion: bool | None
    npk_n: int | None
    npk_p: int | None
    npk_k: int | None
    leaf_r: int | None
    leaf_g: int | None
    leaf_b: int | None
    pump_on: bool

    model_config = ConfigDict(from_attributes=True)
```

### `AlertOut`
```python
class AlertOut(BaseModel):
    id: UUID
    time: datetime
    device_id: str
    type: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    message: str
    acknowledged: bool

    model_config = ConfigDict(from_attributes=True)
```

***

## 12. ML Integration Specification

### 12.1 Model Contract

The `services/ml/runner.py` module defines a strict interface. All ML logic lives here. Nothing outside this module interacts with model files or inference libraries directly.

```python
# services/ml/runner.py

class MLRunner:
    def load(self) -> None:
        """
        Called once during app lifespan startup.
        Reads ML_MODEL_PATH and ML_MODEL_TYPE from settings.
        If ML_ENABLED=False: does nothing.
        If ML_ENABLED=True and model file not found: raises FileNotFoundError
          with a message instructing the user to drop a model file at the configured path.
          The app MUST NOT start if this raises.
        """

    def predict(self, features: dict) -> dict:
        """
        Called on every ingested MQTT message when ML_ENABLED=True.
        Input: dict of sensor field names to float values (None values are excluded).
        Output: dict with at least {"action": str, "confidence": float}.
                The exact output keys depend on the model — the runner returns
                whatever the model outputs as a plain dict.
        Must never raise — on inference error, logs the error and returns
          {"action": "UNKNOWN", "confidence": 0.0, "error": "<message>"}.
        """
```

### 12.2 Supported Model Types

| `ML_MODEL_TYPE` | File extension | Load method |
|---|---|---|
| `sklearn` | `.pkl` | `joblib.load(path)` |
| `tflite` | `.tflite` | `tflite_runtime.interpreter.Interpreter(model_path=path)` |

The runner checks `ML_MODEL_TYPE` at load time. Any other value raises `ValueError` at startup.

### 12.3 Feature Vector

The ingestion service passes this dict to `runner.predict()`:

```python
{
    "soil_pct": float,
    "ph": float,
    "tds_ppm": float,
    "temp_c": float,
    "humidity_pct": float,
    "rain_raw": float,
    "npk_n": float,
    "npk_p": float,
    "npk_k": float,
    "leaf_r": float,
    "leaf_g": float,
    "leaf_b": float,
}
```

`None` fields are excluded before passing. The runner is responsible for handling missing features gracefully.

### 12.4 Training (Out of Backend Scope)

Model training is done externally (laptop, Colab, etc.) using data exported from the TimescaleDB. The backend provides one export endpoint for this purpose:

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/sensors/export` | ✅ | Download CSV of historical readings |

**Query params:** same as `/sensors/history`. Response is `text/csv` with `Content-Disposition: attachment; filename=farmshield_export.csv`.

This endpoint enables the workflow: export CSV → train model externally → drop `.pkl` into `server/app/services/ml/models/` → set `ML_ENABLED=true` in `.env` → `docker compose restart fastapi`.

***

## 13. Alert Threshold Definitions

Alert thresholds are **not hardcoded**. They must be defined as typed attributes in `config.py` and therefore configurable via `.env`. Default values below are agronomic starting points.

```dotenv
# Alert thresholds — add to .env.example
ALERT_SOIL_DRY_PCT=30.0        # Soil below this → SOIL_DRY WARNING
ALERT_SOIL_FLOOD_PCT=85.0      # Soil above this → SOIL_FLOOD WARNING
ALERT_TEMP_HIGH_C=38.0         # Temp above this → TEMP_HIGH WARNING
ALERT_PH_LOW=5.5               # pH below this → PH_LOW WARNING
ALERT_PH_HIGH=7.5              # pH above this → PH_HIGH WARNING
ALERT_TDS_HIGH_PPM=1500.0      # TDS above this → TDS_HIGH WARNING
ALERT_RAIN_DRY_RAW=2500        # Rain raw reading above this = dry conditions
```

`services/alert.py` evaluates thresholds inside a pure function `evaluate_thresholds(reading: SensorReadingOut) -> list[AlertCreate]`. No threshold logic lives in `ingestion.py`.

***

## 14. Logging Specification

`core/logging.py` calls `structlog.configure()` once at app startup. All application code uses `structlog.get_logger(__name__)`. Standard library `logging` is bridged via `structlog.stdlib`.

**Log levels:**
- `DEBUG` — raw MQTT payloads, SQL queries (dev only, `LOG_LEVEL=DEBUG`)
- `INFO` — every ingested reading (device_id + timestamp only, no full payload), every API request, every alert created, every control command published
- `WARNING` — missing `ts` field in payload, ML inference fallback, auth failure, threshold breach
- `ERROR` — DB write failure, MQTT publish failure, ML model file missing (when ML_ENABLED=true)

**Prohibited logging patterns:**
- Never log full sensor payloads at INFO or above (privacy + noise)
- Never swallow an exception without logging it at ERROR level
- Never use `print()` anywhere in application code

**Log format (dev, `LOG_JSON=false`):**
```
2026-04-26 23:01.45 [INFO ] ingestion: reading ingested  device_id=esp32-node-1 ts=1745678901
```

**Log format (prod, `LOG_JSON=true`):**
```json
{"event":"reading ingested","level":"info","logger":"ingestion","device_id":"esp32-node-1","ts":1745678901,"timestamp":"2026-04-26T23:01:45Z"}
```

***

## 15. Authentication Specification

`core/auth.py` exports a single `require_auth` callable used as a FastAPI dependency.

```python
# Pseudocode — implement exactly this logic

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer(auto_error=False))
) -> None:
    if not settings.AUTH_ENABLED:
        return                          # No-op — zero overhead
    if credentials is None or credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

All route handlers in `api/v1/` (except `health.py`) include `Depends(require_auth)`. The health endpoint never has this dependency.

***

## 16. Error Response Contract

All error responses — from validation errors, auth failures, or unhandled exceptions — return this JSON shape:

```json
{
  "detail": "human-readable description of the error",
  "type": "VALIDATION_ERROR | AUTH_ERROR | NOT_FOUND | INTERNAL_ERROR"
}
```

`core/exceptions.py` registers handlers for:
- `RequestValidationError` → 422, `type: VALIDATION_ERROR`
- `HTTPException` → status passthrough, `type` derived from status code
- `Exception` (catch-all) → 500, `type: INTERNAL_ERROR`, full traceback logged at ERROR, generic message returned to client

**There is no circumstance where a raw Python traceback or SQLAlchemy error reaches the API response.**

***

## 17. `pyproject.toml` Specification

```toml
[project]
name = "farmshield-backend"
version = "1.0.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.11.0",
    "pydantic-settings>=2.7.0",
    "sqlalchemy[asyncio]>=2.0.40",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "fastapi-mqtt>=2.2.0",
    "structlog>=25.0.0",
]

[project.optional-dependencies]
ml-sklearn = ["scikit-learn>=1.6.0", "joblib>=1.4.0"]
ml-tflite  = ["tflite-runtime>=2.14.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "httpx>=0.28.0",
]
```

Install for dev: `pip install -e ".[dev]"`
Install with sklearn ML: `pip install -e ".[ml-sklearn]"`
Install with tflite ML: `pip install -e ".[ml-tflite]"`

***

## 18. Testing Specification

### 18.1 Structure

```
tests/
├── conftest.py         ← pytest fixtures: test DB session, mock MQTT client,
│                         override settings (AUTH_ENABLED=false, ML_ENABLED=false),
│                         async test client (httpx.AsyncClient)
├── test_sensors.py     ← GET /sensors/latest, GET /sensors/history, GET /sensors/export
├── test_control.py     ← POST /control/pump, /mode, /buzzer — valid + invalid states
├── test_ingestion.py   ← process() with valid payload, missing fields, malformed JSON,
│                         DB write verification, WS broadcast mock
└── test_ml.py          ← runner.predict() with mock .pkl, missing model file with
                          ML_ENABLED=true, ML_ENABLED=false no-op
```

### 18.2 Rules

- All tests are async (`@pytest.mark.asyncio`)
- Tests never connect to a real DB or MQTT broker. Use `pytest` fixtures with mocked sessions
- Auth tests: one fixture with `AUTH_ENABLED=true`, one with `AUTH_ENABLED=false` — test both
- `pytest.ini` or `pyproject.toml` section sets `asyncio_mode = "auto"` for `pytest-asyncio`
- Run with: `pytest tests/ -v --tb=short`

***

## 19. Startup Sequence

The `lifespan` context manager in `main.py` governs startup in this exact order:

1. `core/logging.py` — `configure_logging()` first, before anything else logs
2. Validate that all required env vars are present (pydantic-settings does this automatically on `Settings()` instantiation — if a required var is missing the app exits with a clear error)
3. `db/session.py` — create async engine, test connection with a simple `SELECT 1`
4. Alembic — `upgrade head` (run via subprocess in the Dockerfile CMD before uvicorn starts, not in lifespan)
5. Apply TimescaleDB retention policy if `RETENTION_DAYS > 0`
6. `services/ml/runner.py` — `load()` if `ML_ENABLED=true`
7. `mqtt/client.py` — `await mqtt_client.mqtt_startup()`

On shutdown (lifespan exit):
1. `await mqtt_client.mqtt_shutdown()`
2. Dispose async engine

***

## 20. Non-Negotiables for the Implementing Agent

These rules apply to every file written:

1. **No silent fallbacks.** If a config value is wrong, a file is missing, or a connection fails — raise immediately with a descriptive message. Do not substitute defaults without logging a WARNING at minimum.
2. **No logic in route handlers.** Route handlers call one service function and return its result. Period.
3. **No direct DB access outside `services/`.** Route handlers receive a DB session via `Depends(get_db)` and pass it to a service function. They do not execute queries themselves.
4. **No hardcoded strings for topics, credentials, thresholds, or timeouts.** Everything routes through `settings.*`.
5. **Every `except` block must log.** `except Exception as e: pass` is a defect.
6. **`ML_ENABLED=false` must add zero overhead.** The ML runner must not be imported or instantiated when disabled.
7. **The health endpoint must always return 200** as long as the process is alive, even if MQTT is disconnected. The `mqtt_connected` and `db_connected` fields report actual state — they do not cause a non-200 response.
8. **WebSocket disconnects are not errors.** `ConnectionManager` must handle client disconnect gracefully with no exception propagation.

---

***

## Amendment 1 — Docker Compose Split

**Section 6 (Docker Compose Specification)** currently puts the FastAPI bind mount and `FASTAPI_RELOAD` inside the single `docker-compose.yml`. That needs to be split:

- `docker-compose.yml` — base file, **no bind mount on fastapi**, `FASTAPI_RELOAD` not set here
- `docker-compose.override.yml` — dev-only file, adds the bind mount + sets `FASTAPI_RELOAD=true`, merged automatically by Docker Compose on laptop

Add this file to the repository and document it in `.env.example` comments.

***

## Amendment 2 — Dockerfile CMD

**Section 6.2 (Dockerfile)** has a note saying *"the `--reload` flag is controlled by the process, not the Dockerfile"* and suggests a shell entrypoint script — but doesn't define it. That ambiguity would confuse an implementing agent.

The clean fix: replace the `CMD` in the Dockerfile with an explicit entrypoint script:

```bash
#!/bin/sh
# server/entrypoint.sh

# Always run migrations first
alembic upgrade head

# Start server — reload mode controlled by env
if [ "$FASTAPI_RELOAD" = "true" ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
```

And update the Dockerfile `CMD` to:
```dockerfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

`entrypoint.sh` gets committed to the repo. `FASTAPI_RELOAD` is set in `.env` — already in the existing `.env.example` spec, so no change there.

***
