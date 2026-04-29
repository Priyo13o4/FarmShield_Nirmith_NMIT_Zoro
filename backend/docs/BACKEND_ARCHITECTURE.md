# FarmShield Backend — Comprehensive Architecture & Implementation Guide

**Version:** 1.0.0  
**Last Updated:** April 28, 2026  
**Audience:** Developers adding features, fixing bugs, or extending the system

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Directory Structure & File Purposes](#directory-structure--file-purposes)
5. [Central Files & Key Components](#central-files--key-components)
6. [Application Initialization Flow](#application-initialization-flow)
7. [Configuration & Environment Variables](#configuration--environment-variables)
8. [API Endpoints Reference](#api-endpoints-reference)
9. [Database Models & Schemas](#database-models--schemas)
10. [Services & Business Logic](#services--business-logic)
11. [MQTT Data Pipeline](#mqtt-data-pipeline)
12. [Reusable Modules & Functions](#reusable-modules--functions)
13. [Adding New Features](#adding-new-features)
14. [Testing Strategy](#testing-strategy)
15. [Deployment & Docker](#deployment--docker)

---

## Project Overview

**FarmShield** is an edge-AI smart agriculture system that bridges an ESP32 sensor node and multiple frontend consumers. The backend:

- **Receives** continuous sensor telemetry from ESP32 over MQTT
- **Persists** all readings to TimescaleDB (time-series PostgreSQL)
- **Analyzes** sensor data against configurable thresholds → generates alerts
- **Optionally runs** ML inference on every ingested reading
- **Exposes** REST API + WebSocket live streams
- **Supports** remote control of pump, mode, and buzzer
- **Conditionally enables** AI chatbot backed by Google Gemini
- **Runs identically** on laptop and Raspberry Pi 4B with single Docker Compose file

### Key Design Principles

1. **Configuration → Environment**: All tuneable values live in `.env`, not hardcoded
2. **No fallbacks without gatekeeping**: Every failure raises an exception and logs it
3. **Modular by design**: Adding sensor, endpoint, or model touches minimum files unambiguously
4. **Async-first architecture**: All I/O is async (FastAPI, SQLAlchemy 2.0 async, MQTT)
5. **Feature gating**: `CHAT_ENABLED`, `ML_ENABLED` flags disable entire subsystems with zero overhead
6. **Single source of truth for config**: `.env.example` documents every variable

---

## Technology Stack

### Runtime & Framework

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.13 | Language (enforced via Dockerfile) |
| FastAPI | ≥ 0.115.0 | Web framework |
| Uvicorn | ≥ 0.34.0 | ASGI server with uvloop + httptools |
| Pydantic | ≥ 2.11.0 | Data validation (v2 only) |
| pydantic-settings | ≥ 2.7.0 | `.env` → typed `Settings` class |

### Database

| Component | Version | Purpose |
|-----------|---------|---------|
| TimescaleDB | 2.26.3-pg16 | Time-series database (Docker image) |
| SQLAlchemy | ≥ 2.0.40 | Async ORM |
| asyncpg | ≥ 0.30.0 | Async PostgreSQL driver |
| Alembic | ≥ 1.14.0 | Database migrations |

### Messaging

| Component | Version | Purpose |
|-----------|---------|---------|
| Eclipse Mosquitto | 2 | MQTT broker (Docker) |
| fastapi-mqtt | ≥ 2.2.0 | Async MQTT client |

### Optional Features (Feature-Gated)

| Component | Version | Feature Flag | Purpose |
|-----------|---------|--------------|---------|
| langchain | ≥ 0.3.0 | `CHAT_ENABLED` | Agent orchestration |
| langchain-google-genai | ≥ 2.0.0 | `CHAT_ENABLED` | Gemini LLM + embeddings |
| faiss-cpu | ≥ 1.9.0 | `CHAT_ENABLED` | Vector search for knowledge base |
| scikit-learn | ≥ 1.6.0 | `ML_ENABLED` | ML inference (sklearn) |
| joblib | ≥ 1.4.0 | `ML_ENABLED` | Pickle serialization |
| tflite-runtime | ≥ 2.14.0 | `ML_ENABLED` | ML inference (TensorFlow Lite) |

### Observability

| Component | Version | Purpose |
|-----------|---------|---------|
| structlog | ≥ 25.0.0 | Structured logging (JSON in prod, pretty in dev) |

### Development & Testing

| Component | Version | Purpose |
|-----------|---------|---------|
| pytest | ≥ 8.0.0 | Test runner |
| pytest-asyncio | ≥ 0.25.0 | Async test support |
| httpx | ≥ 0.28.0 | HTTP test client |

---

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FARMSHIELD ECOSYSTEM                      │
└─────────────────────────────────────────────────────────────────────┘

ESP32 Node (firmware sends MQTT)
        │
        │ MQTT (JSON sensor telemetry)
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      MQTT Broker (Mosquitto)                        │
│                    Subtopics (TLS not implemented)                  │
│  ├─ farmshield/sensors         (ESP32 → Backend)                    │
│  ├─ farmshield/control/pump    (Backend → ESP32)                    │
│  ├─ farmshield/control/mode    (Backend → ESP32)                    │
│  ├─ farmshield/control/buzzer  (Backend → ESP32)                    │
│  └─ farmshield/alerts          (Backend → ESP32)                    │
└─────────────────────────────────────────────────────────────────────┘
        │
        │ MQTT (fire-and-forget)
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│           FastAPI + Uvicorn (Async Backend Container)               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │               API Routes (HTTP + WebSocket)                 │  │
│  │  /api/v1/health           (liveness probe)                  │  │
│  │  /api/v1/sensors/*        (GET latest, history, export)     │  │
│  │  /api/v1/control/*        (POST pump, mode, buzzer)         │  │
│  │  /api/v1/alerts/*         (GET list, POST ack)              │  │
│  │  /ws                       (WebSocket live stream)           │  │
│  │  /api/v1/chat             (LLM query — if CHAT_ENABLED)     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              MQTT Client + Handlers                         │  │
│  │  mqtt/client.py      → FastMQTT singleton config            │  │
│  │  mqtt/handlers.py    → on_connect, on_message, on_disconnect│  │
│  │                                                               │  │
│  │  → Parses JSON → calls ingestion.process()                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           ↓                                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │           Ingestion Service (Hot Path)                      │  │
│  │  1. Validate payload (SensorPayload schema)                 │  │
│  │  2. Convert ts → datetime                                   │  │
│  │  3. Write to DB (INSERT ... ON CONFLICT)                    │  │
│  │  4. Optional: Run ML inference                              │  │
│  │  5. Broadcast to WebSocket clients                          │  │
│  │  6. Evaluate alert thresholds → publish alerts              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│           ↓ (step 3)        ↓ (step 5)      ↓ (step 6)             │
│      [DB Write]        [WS Broadcast]   [MQTT Publish]             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Optional Services                              │  │
│  │  • ML Runner: loads model, runs inference (sklearn/tflite)  │  │
│  │  • Chat Agent: RAG + SQL tools, Gemini completion           │  │
│  │  • Alert Service: threshold evaluation + CRUD               │  │
│  │  • Control Service: publishes MQTT commands                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
        │
        │ SQL (async)
        ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    TimescaleDB (PostgreSQL 16)                      │
│                      Hypertable: sensor_readings                    │
│                      Regular tables: alerts, ml_inferences          │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├─ Web Frontends (HTTP client) ← REST API responses
        │
        ├─ WebSocket Consumers ← live sensor/alert broadcasts
        │
        └─ (Optional) LLM Chatbot ← SQL queries + vector search
```

### Data Flow (Critical Path)

```
ESP32 publishes JSON on MQTT topic
          │
          ↓
Mosquitto broker routes message
          │
          ↓
FastAPI MQTT handler receives bytes
          │
          ↓
on_message() parses JSON → calls ingestion.process()
          │
          ├─→ Validate with SensorPayload ✓
          │
          ├─→ Convert timestamp (Unix epoch → datetime)
          │
          ├─→ INSERT sensor_readings (with deduplication)
          │
          ├─→ [IF ML_ENABLED] Run inference → INSERT ml_inferences
          │
          ├─→ Broadcast JSON to WebSocket clients
          │
          └─→ Evaluate thresholds → CREATE alerts (if breached)
                 → PUBLISH alerts to MQTT
```

### Architectural Layers

1. **HTTP Boundary** (routes in `api/v1/`)
   - Handles REST requests, validates auth, returns JSON
   - All route handlers inject `AsyncSession` via `Depends(get_db)`
   - Each route is thin wrapper over service call

2. **Service Layer** (functions in `services/`)
   - Business logic: threshold evaluation, query building, command publishing
   - Pure functions where possible (e.g., `evaluate_thresholds()`)
   - Database I/O, external API calls, state mutations all here
   - **No HTTP or FastAPI concerns**

3. **Database Layer** (SQLAlchemy + Alembic)
   - ORM models in `db/models.py`
   - Schema migrations in `alembic/versions/`
   - Async session management in `db/session.py`

4. **Integration Layer** (MQTT, WebSocket, optional LLM)
   - MQTT: `mqtt/client.py`, `mqtt/handlers.py`
   - WebSocket: `services/websocket.py`, `api/v1/ws.py`
   - Chat: `services/chat/` (only imported if `CHAT_ENABLED=true`)

5. **Cross-Cutting Concerns**
   - Authentication: `core/auth.py` → `require_auth` dependency
   - Logging: `core/logging.py` → structured logging setup
   - Exception handling: `core/exceptions.py` → consistent error responses
   - Configuration: `config.py` → Pydantic Settings

---

## Directory Structure & File Purposes

```
backend/
├── .env                              # Local config (never commit; git-ignored)
├── .env.example                      # CANONICAL reference for all variables
├── .gitignore                        # Standard Python + Docker ignores
├── docker-compose.yml                # Multi-container orchestration
├── docker-compose.override.yml       # Local dev overrides
│
├── server/
│   ├── pyproject.toml                # Dependencies + extras (ml-sklearn, ml-tflite, chat, dev)
│   ├── Dockerfile                    # Python 3.13 slim + entrypoint logic
│   ├── entrypoint.sh                 # Runs alembic migrate, optional pip install
│   ├── alembic.ini                   # Alembic config (DB URL injected at startup)
│   │
│   ├── alembic/
│   │   ├── env.py                    # Migration runner config
│   │   └── versions/
│   │       ├── 0001_initial.py       # Baseline schema (hypertables, tables, indexes)
│   │       ├── 0002_*.py             # Constraint fixes
│   │       ├── 0003_*.py             # Firmware fields (mode, uptime)
│   │       └── 0004_*.py             # Read-only user for chat
│   │
│   └── app/
│       ├── main.py                   # FastAPI app, lifespan context manager
│       ├── config.py                 # Settings class (TypedDict-like pydantic)
│       ├── dependencies.py           # FastAPI dependencies (get_db, require_auth)
│       │
│       ├── api/
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py          # Aggregates all sub-routers
│       │       ├── health.py          # GET /health (no auth)
│       │       ├── sensors.py         # GET /sensors/latest, /history, /export
│       │       ├── control.py         # POST /control/pump, /mode, /buzzer
│       │       ├── alerts.py          # GET /alerts/list, POST /alerts/:id/acknowledge
│       │       ├── ws.py              # WebSocket /ws endpoint
│       │       └── chat.py            # POST /chat/query (only if CHAT_ENABLED)
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── auth.py                # require_auth() dependency
│       │   ├── logging.py             # configure_logging() for structlog
│       │   └── exceptions.py          # Exception handlers, error formatting
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── session.py             # SQLAlchemy async engine + session factory
│       │   └── models.py              # ORM models (SensorReading, Alert, MLInference)
│       │
│       ├── mqtt/
│       │   ├── __init__.py
│       │   ├── client.py              # FastMQTT singleton, config
│       │   └── handlers.py            # on_connect, on_message, on_disconnect
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── sensor.py              # SensorPayload (MQTT in), SensorReadingOut (API out)
│       │   ├── control.py             # PumpCommand, ModeCommand, BuzzerCommand
│       │   ├── alert.py               # AlertOut, AlertAckRequest
│       │   └── chat.py                # ChatRequest, ChatResponse (only if CHAT_ENABLED)
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── ingestion.py           # process() → HOT PATH (validates, writes, broadcasts)
│       │   ├── sensor.py              # Query service (get_latest, get_history, export_csv)
│       │   ├── control.py             # Dispatch service (send_pump, send_mode, send_buzzer)
│       │   ├── alert.py               # Alert CRUD + threshold evaluation
│       │   ├── websocket.py           # ConnectionManager for WS broadcast
│       │   │
│       │   ├── ml/
│       │   │   ├── __init__.py
│       │   │   ├── runner.py           # MLRunner class (load model, run inference)
│       │   │   └── models/             # Drop .pkl or .tflite files here at runtime
│       │   │
│       │   └── chat/ (only if CHAT_ENABLED)
│       │       ├── __init__.py
│       │       ├── rag_tool.py         # RagTool (FAISS indexing + retrieval)
│       │       ├── sql_tool.py         # SQL table + column metadata for LLM
│       │       ├── agent.py            # farm_agent orchestration
│       │       └── knowledge/          # Markdown documents for FAISS indexing
│       │
│       └── __init__.py
│
├── mosquitto/
│   └── config/
│       ├── mosquitto.conf             # MQTT broker config (ACL, listeners)
│       └── passwd                     # MQTT username:password (generated at runtime)
│
├── Hardware/
│   └── farmshield.ino                 # ESP32 firmware (reference only)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # pytest fixtures (test client, mock DB)
│   ├── test_sensors.py                # Test sensor endpoints + service
│   ├── test_control.py                # Test control endpoints
│   ├── test_ingestion.py              # Test MQTT pipeline, thresholds
│   ├── test_ml.py                     # Test ML runner (if ML_ENABLED)
│   └── test_chat.py                   # Test chat agent (if CHAT_ENABLED)
│
└── docs/
    ├── PRD.md                         # Product Requirements Document
    ├── PRD_Feature_ChatBot.md         # Chat feature specifications
    ├── API_REFERENCE.md               # OpenAPI endpoint reference
    ├── DEPLOYMENT.md                  # Production deployment guide
    ├── ISSUES_FIXES.md                # Known issues + workarounds
    └── BACKEND_ARCHITECTURE.md        # THIS FILE
```

---

## Central Files & Key Components

### 1. **main.py** — Application Entry Point

**Purpose**: Initializes FastAPI app, manages startup/shutdown lifecycle  
**Key Functions**:
- `lifespan()` context manager: Controls startup sequence (logging → DB test → ML load → MQTT start → chat init)
- Creates FastAPI app with CORS middleware
- Registers exception handlers
- Registers API routers (conditionally includes chat router if enabled)

**When to modify**: Adding new startup steps, new middleware, new middleware

**Startup Order** (critical to follow):
1. Configure logging (via structlog)
2. Validate environment variables (pydantic-settings)
3. Test DB connection (SELECT 1)
4. Apply retention policy (if `RETENTION_DAYS > 0`)
5. Load ML model (if `ML_ENABLED=true`)
6. Initialize chat feature (if `CHAT_ENABLED=true`)
7. Start MQTT client (side-effect imports handlers)

### 2. **config.py** — Configuration Management

**Purpose**: Single `Settings` class that loads `.env` file and validates all environment variables  
**Key Class**: `Settings` (Pydantic BaseSettings)
- All attributes are typed (no magic strings)
- Properties: `db_url`, `chat_db_readonly_url` (computed)
- Validators: `validate_chat_config()` checks if GEMINI_API_KEY is set when chat enabled
- Exported as singleton: `settings = Settings()`

**When to modify**: Adding new configuration variable, changing a default value

**Pattern for adding new variable**:
```python
# In config.py
my_new_setting: str = "default_value"  # Add typed attribute
chat_enabled: bool = False              # Already exists as example

# In .env.example
# ─────────────────────────────────────
# MY NEW FEATURE
# ─────────────────────────────────────
MY_NEW_SETTING=default_value           # Add with documentation comment
```

### 3. **dependencies.py** — FastAPI Dependency Injection

**Purpose**: Centralized dependency providers for route handlers  
**Key Functions**:
- `get_db()` → AsyncGenerator that yields AsyncSession
- `require_auth` → Re-exported from `core.auth` for convenience

**Usage in routes**:
```python
@router.get("/sensors/latest")
async def get_latest(db: AsyncSession = Depends(get_db)):
    reading = await sensor_service.get_latest(db, device_id)
    return reading
```

**When to modify**: Adding new shared dependencies (e.g., auth roles, feature flags)

### 4. **api/v1/router.py** — Route Aggregation

**Purpose**: Central router that includes all sub-routers  
**Pattern**:
- Each resource (sensors, control, alerts, etc.) is a separate module with its own `router`
- `router.py` aggregates them with `include_router()`
- Chat router is conditionally included based on `settings.chat_enabled`

**When to modify**: Adding new resource endpoints, conditionally registering routers

### 5. **db/models.py** — ORM Models

**Purpose**: SQLAlchemy models mapping to TimescaleDB tables  
**Key Models**:

| Model | Table | Purpose | Notes |
|-------|-------|---------|-------|
| `SensorReading` | `sensor_readings` | Raw telemetry from ESP32 | Hypertable; time + device_id = composite key |
| `Alert` | `alerts` | Generated threshold breaches | UUID primary key |
| `MLInference` | `ml_inferences` | Prediction results | Hypertable; time + device_id = composite key |

**When to modify**: Adding new sensor field, new model, changing column type

**Pattern**:
```python
from sqlalchemy import Double, Text
from sqlalchemy.orm import Mapped, mapped_column

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    
    # Composite key (ORM level, not DDL)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    device_id: Mapped[str] = mapped_column(Text, primary_key=True)
    
    # Optional sensor field
    soil_pct: Mapped[float | None] = mapped_column(Double, nullable=True)
```

### 6. **schemas/** — Pydantic Validation Schemas

**Purpose**: Request/response validation and serialization  
**Key Files**:

| File | Classes | Purpose |
|------|---------|---------|
| `sensor.py` | `SensorPayload`, `SensorReadingOut`, `SensorHistoryResponse` | MQTT inbound, API outbound |
| `control.py` | `PumpCommand`, `ModeCommand`, `BuzzerCommand`, `ControlResponse` | Control commands |
| `alert.py` | `AlertOut`, `AlertAckRequest` | Alert responses |
| `chat.py` | `ChatRequest`, `ChatResponse` | Chat LLM queries (if CHAT_ENABLED) |

**Pattern for aliasing** (firmware sends different names than DB):
```python
class SensorPayload(BaseModel):
    # Firmware sends "temperature"; DB column is "temp_c"
    temp_c: float | None = Field(default=None, alias="temperature")
    
    # Flatten nested objects from firmware JSON
    @model_validator(mode="before")
    @classmethod
    def flatten_nested_objects(cls, data):
        # Before field assignment, flatten {"color": {"r": 80, ...}}
        # into flat leaf_r, leaf_g, leaf_b attributes
        ...
```

### 7. **services/ingestion.py** — Critical Hot Path

**Purpose**: Main entry point for MQTT data processing  
**Key Function**: `async def process(raw_payload: dict)`

**Processing Steps**:
1. **Validate** with `SensorPayload` schema
2. **Convert timestamp** (Unix epoch → UTC datetime, fallback to NOW())
3. **Write to DB** (INSERT ... ON CONFLICT DO NOTHING for deduplication)
4. **Optional ML inference** (if `ML_ENABLED` and model loaded)
5. **Broadcast to WebSocket** (all connected clients)
6. **Evaluate alert thresholds** (pure function → publish MQTT alerts)

**When to modify**: Adding processing step, changing MQTT message handling

### 8. **services/alert.py** — Alert Logic

**Purpose**: Threshold evaluation + alert CRUD  
**Key Functions**:
- `evaluate_thresholds(reading: SensorReadingOut) → list[dict]` (pure function)
- `create_alert()` → INSERT into DB
- `acknowledge_alert()` → UPDATE alerts SET acknowledged=true

**Threshold Configuration**: All thresholds are environment variables (see `.env.example`)
- `ALERT_SOIL_DRY_PCT`, `ALERT_SOIL_FLOOD_PCT`
- `ALERT_TEMP_HIGH_C`, `ALERT_PH_LOW`, `ALERT_PH_HIGH`
- `ALERT_TDS_HIGH_PPM`, `ALERT_RAIN_DRY_RAW`

**When to modify**: Adding new alert type, changing threshold logic

### 9. **mqtt/handlers.py** — MQTT Subscription & Routing

**Purpose**: Decorators that subscribe to MQTT topics and route messages  
**Key Decorators**:
- `@fast_mqtt.on_connect()` → Subscribe to sensor topic
- `@fast_mqtt.on_message()` → Parse JSON, call `ingestion.process()`
- `@fast_mqtt.on_disconnect()` → Log disconnection

**Pattern**:
```python
@fast_mqtt.on_message()
async def on_message(client, topic, payload, qos, properties):
    if topic != settings.mqtt_topic_sensors:
        return
    data = json.loads(payload.decode("utf-8"))
    await ingestion.process(data)
```

**When to modify**: Adding new MQTT topic handler, changing subscription logic

### 10. **services/control.py** — Outbound MQTT Commands

**Purpose**: Publish control commands to ESP32  
**Key Functions**:
- `send_pump_command(state: str)` → Publish to `MQTT_TOPIC_CONTROL_PUMP`
- `send_mode_command(state: str)` → Publish to `MQTT_TOPIC_CONTROL_MODE`
- `send_buzzer_command(state: str)` → Publish to `MQTT_TOPIC_CONTROL_BUZZER`

**Payload Format**: Raw strings (e.g., `"ON"`, `"AUTO"`), NOT JSON

**When to modify**: Adding new control command, changing MQTT topics

### 11. **services/websocket.py** — Live Broadcast Manager

**Purpose**: Manages WebSocket connections and broadcasts  
**Key Class**: `ConnectionManager`
- `connect()` → Accept and register connection
- `disconnect()` → Remove connection
- `broadcast(data: dict)` → Send JSON to all clients (stale connections cleaned up silently)

**Usage**:
```python
from app.services.websocket import ws_manager

# In ingestion.py after writing to DB:
await ws_manager.broadcast({
    "type": "sensor_reading",
    "data": reading_dict
})
```

**When to modify**: Adding new broadcast type, changing connection management

### 12. **core/auth.py** — Authentication Dependency

**Purpose**: Validates Bearer API key  
**Key Function**: `require_auth()` dependency
- If `AUTH_ENABLED=true`: validates `Authorization: Bearer <key>`
- If `AUTH_ENABLED=false`: no-op with zero overhead

**Usage in routes**:
```python
@router.get("/sensors/latest", dependencies=[Depends(require_auth)])
async def get_latest(...):
    ...
```

**When to modify**: Adding role-based auth, adding new auth schemes

### 13. **core/exceptions.py** — Error Handling

**Purpose**: Centralized exception handlers with consistent JSON response format  
**Response Format**:
```json
{
  "detail": "Human-readable message",
  "type": "VALIDATION_ERROR | AUTH_ERROR | NOT_FOUND | INTERNAL_ERROR"
}
```

**When to modify**: Adding new exception type, changing error response format

---

## Application Initialization Flow

```python
# 1. Startup
main.py → FastAPI(lifespan=lifespan)
    ├─ app_startup():
    │   ├─ configure_logging(settings.log_level, settings.log_json)
    │   ├─ Test DB: SELECT 1
    │   ├─ Apply retention: SELECT add_retention_policy(...)
    │   ├─ [IF ML_ENABLED] Load ML model
    │   ├─ [IF CHAT_ENABLED] Initialize chat (FAISS, SQL tools)
    │   └─ Start MQTT client (imports mqtt/handlers.py → registers decorators)
    │
    └─ return app
        ├─ register_exception_handlers(app)
        └─ include_router(api_v1_router)

# 2. Request lifecycle
Request → FastAPI middleware → route handler
    ├─ Validate Authorization header (if not /health)
    ├─ Inject AsyncSession via Depends(get_db)
    ├─ Call service function
    ├─ Return response (validated by schema)
    └─ Exception handler (if error)

# 3. MQTT message lifecycle
Mosquitto publishes → FastMQTT handler
    ├─ on_message() receives payload
    ├─ Parse JSON
    ├─ Call ingestion.process(data)
    │   ├─ Validate SensorPayload
    │   ├─ Write to DB
    │   ├─ Optional: Run ML
    │   ├─ Broadcast to WS clients
    │   └─ Evaluate thresholds → Create alerts
    └─ Done (no response to MQTT)

# 4. Shutdown
    └─ close MQTT client
    └─ close DB connections
```

---

## Configuration & Environment Variables

### Complete `.env.example` Reference

All variables are documented in the `.env.example` file. Key categories:

#### **Deployment Target**
- `TARGET_ENV=laptop` → For documentation only

#### **FastAPI**
- `FASTAPI_HOST=0.0.0.0` → Bind address
- `FASTAPI_PORT=8000` → Exposed port
- `FASTAPI_RELOAD=true` → Auto-reload on changes

#### **MQTT**
- `MQTT_BROKER_HOST=mosquitto` → Broker address (inside Docker: service name)
- `MQTT_BROKER_PORT=1883` → Default MQTT port
- `MQTT_USERNAME`, `MQTT_PASSWORD` → Credentials
- `MQTT_TOPIC_SENSORS=farmshield/sensors` → ESP32 publishes here
- `MQTT_TOPIC_CONTROL_PUMP=farmshield/control/pump` → Backend publishes pump commands
- `MQTT_TOPIC_CONTROL_MODE=farmshield/control/mode` → Mode commands
- `MQTT_TOPIC_CONTROL_BUZZER=farmshield/control/buzzer` → Buzzer commands

#### **Database**
- `DB_HOST=timescaledb` → Database address
- `DB_PORT=5432` → PostgreSQL port
- `DB_NAME=farmshield` → Database name
- `DB_USER`, `DB_PASSWORD` → Credentials
- `DB_POOL_SIZE=5` → Connection pool size
- `DB_POOL_MAX_OVERFLOW=10` → Max overflow connections

#### **Authentication**
- `AUTH_ENABLED=true` → Require API key on all endpoints except /health
- `API_KEY=changeme-...` → Bearer token

#### **ML Inference**
- `ML_ENABLED=false` → Enable/disable ML feature (zero overhead when false)
- `ML_MODEL_PATH=app/services/ml/models/irrigation_model.pkl` → Model file path
- `ML_MODEL_TYPE=sklearn` → "sklearn" or "tflite"

#### **Chat Feature**
- `CHAT_ENABLED=false` → Enable/disable chat (zero overhead when false)
- `GEMINI_API_KEY=...` → Google Gemini API key (required if CHAT_ENABLED=true)
- `GEMINI_MODEL=gemini-2.0-flash` → LLM model name
- `GEMINI_EMBEDDING_MODEL=models/text-embedding-004` → Embedding model
- `FAISS_INDEX_PATH=app/services/chat/faiss_index` → Vector index storage

#### **Data Retention**
- `RETENTION_DAYS=7` → Auto-delete rows older than N days (0 = disabled)

#### **Logging**
- `LOG_LEVEL=INFO` → DEBUG | INFO | WARNING | ERROR
- `LOG_JSON=false` → true = JSON (prod), false = pretty-print (dev)

#### **Alert Thresholds**
All optional sensor thresholds:
- `ALERT_SOIL_DRY_PCT=30.0`, `ALERT_SOIL_FLOOD_PCT=85.0`
- `ALERT_TEMP_HIGH_C=38.0`, `ALERT_PH_LOW=5.5`, `ALERT_PH_HIGH=7.5`
- `ALERT_TDS_HIGH_PPM=1500.0`, `ALERT_RAIN_DRY_RAW=2500`

### Pattern: Adding New Configuration

1. Add typed attribute to `Settings` class in `config.py`
2. Add variable to `.env.example` with inline comment
3. Use via `from app.config import settings` then `settings.my_var`

---

## API Endpoints Reference

All endpoints are prefixed with `/api/v1/`. Full reference in `API_REFERENCE.md`.

### Health Check
- **GET** `/health` — No auth required

### Sensors
- **GET** `/sensors/latest` — Most recent reading
- **GET** `/sensors/history` — Paginated history
- **GET** `/sensors/export` — CSV download

### Control
- **POST** `/control/pump` — Turn pump ON/OFF
- **POST** `/control/mode` — Switch AUTO/MANUAL
- **POST** `/control/buzzer` — Silence buzzer

### Alerts
- **GET** `/alerts/list` — Get all alerts (paginated)
- **POST** `/alerts/{id}/acknowledge` — Mark alert as read

### WebSocket
- **GET** `/ws` — Subscribe to live sensor + alert broadcasts

### Chat (if CHAT_ENABLED)
- **POST** `/chat/query` — Natural language query about farm data

### Interactive Documentation
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

---

## Database Models & Schemas

### Table: `sensor_readings` (Hypertable)

**Purpose**: Store all raw sensor telemetry from ESP32

**Columns**:

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `time` | TIMESTAMPTZ | false | Partition column (hypertable) |
| `device_id` | TEXT | false | ESP32 device identifier |
| `soil_pct` | DOUBLE PRECISION | true | Soil moisture 0–100% |

| `tds_ppm` | DOUBLE PRECISION | true | Total dissolved solids |
| `temp_c` | DOUBLE PRECISION | true | Air temperature |
| `humidity_pct` | DOUBLE PRECISION | true | Relative humidity |
| `rain_raw` | INTEGER | true | ADC value ~0 wet, ~4095 dry |
| `motion` | BOOLEAN | true | PIR motion detector |
| `npk_n` | INTEGER | true | Nitrogen mg/kg |
| `npk_p` | INTEGER | true | Phosphorus mg/kg |
| `npk_k` | INTEGER | true | Potassium mg/kg |
| `npk_ok` | BOOLEAN | true | Modbus read success flag |
| `leaf_r` | SMALLINT | true | Color sensor red channel |
| `leaf_g` | SMALLINT | true | Color sensor green channel |
| `leaf_b` | SMALLINT | true | Color sensor blue channel |
| `pump_on` | BOOLEAN | false | Pump relay state |
| `mode` | TEXT | true | AUTO or MANUAL (firmware state) |
| `uptime_s` | INTEGER | true | Seconds since ESP32 boot |

**Indexes**:
- Composite unique: `(time, device_id)` for deduplication
- Regular: `device_id, time DESC` for fast queries
- TimescaleDB automatic chunking on time

### Table: `alerts`

**Purpose**: Store generated threshold breach alerts

**Columns**:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key, auto-generated |
| `time` | TIMESTAMPTZ | Alert creation timestamp |
| `device_id` | TEXT | Source device |
| `type` | TEXT | SOIL_DRY, SOIL_FLOOD, TEMP_HIGH, PH_LOW, PH_HIGH, TDS_HIGH, RAIN_DRY, etc. |
| `severity` | TEXT | INFO, WARNING, CRITICAL |
| `message` | TEXT | Human-readable alert message |
| `acknowledged` | BOOLEAN | Whether user has seen it |

### Table: `ml_inferences` (Hypertable)

**Purpose**: Store ML prediction results (if ML_ENABLED)

**Columns**:

| Column | Type | Notes |
|--------|------|-------|
| `time` | TIMESTAMPTZ | Partition column |
| `device_id` | TEXT | Source device |
| `model_name` | TEXT | e.g., "irrigation_model" |
| `input_features` | JSONB | Input feature dict |
| `output` | JSONB | Model output (prediction) |
| `inference_ms` | DOUBLE PRECISION | Inference duration |

### Pydantic Schemas

#### `SensorPayload` (MQTT inbound)
```python
# Accepted from ESP32; all numeric fields optional
class SensorPayload(BaseModel):
    device: str  # Aliased to device_id
    temperature: float | None  # Aliased to temp_c
    humidity: float | None  # Aliased to humidity_pct
    soil: float | None  # Aliased to soil_pct
    ph: float | None
    tds: float | None  # Aliased to tds_ppm
    # ...
    @model_validator(mode="before")
    def flatten_nested_objects(cls, data):
        # Flatten {"color": {"r": 80, "g": 140, "b": 60}}
        # into leaf_r, leaf_g, leaf_b
        ...
```

#### `SensorReadingOut` (API response)
```python
# Matches DB schema exactly
class SensorReadingOut(BaseModel):
    time: datetime
    device_id: str
    soil_pct: float | None
    ph: float | None
    # ... all fields from DB model
    model_config = ConfigDict(from_attributes=True)
```

---

## Services & Business Logic

### Core Services

#### **ingestion.py** — `process(raw_payload: dict)`
**Hot path**: Called for every MQTT message  
**Steps**:
1. Validate with `SensorPayload` schema
2. Convert timestamp (Unix epoch → UTC datetime)
3. Write to DB with deduplication
4. Optional ML inference
5. Broadcast to WebSocket clients
6. Evaluate thresholds → create alerts

**Handles errors**: Logs and continues (no re-raises)

#### **sensor.py** — Query Service
**Functions**:
- `get_latest(db, device_id)` → Latest SensorReading
- `get_history(db, device_id, hours, limit, offset)` → Paginated history
- `export_csv_data(db, device_id, hours, limit, offset)` → CSV string

#### **control.py** — Command Dispatch Service
**Functions**:
- `send_pump_command(state: str)` → Publish to MQTT
- `send_mode_command(state: str)` → Publish to MQTT
- `send_buzzer_command(state: str)` → Publish to MQTT

**Payload format**: Raw strings (e.g., "ON", "AUTO"), not JSON

#### **alert.py** — Alert CRUD + Thresholds
**Functions**:
- `evaluate_thresholds(reading) → list[dict]` (pure function)
- `create_alert(db, device_id, type, severity, message)` → INSERT
- `get_alerts(db, device_id, limit, offset)` → Paginated list
- `acknowledge_alert(db, alert_id)` → UPDATE

#### **websocket.py** — `ConnectionManager` Class
**Methods**:
- `connect(ws)` → Accept + register
- `disconnect(ws)` → Remove safely
- `broadcast(data)` → Send to all clients (cleans stale automatically)

### Optional Services

#### **ml/runner.py** — ML Inference (if ML_ENABLED)
**Class**: `MLRunner`
- `load()` → Load model from disk (sklearn or tflite)
- `predict(features: dict) → dict` → Run inference, time it

#### **chat/** — Chatbot (if CHAT_ENABLED)
**Modules**:
- `rag_tool.py` → FAISS vector indexing + retrieval
- `sql_tool.py` → SQL tools for Gemini agent
- `agent.py` → LangChain agent orchestration

---

## MQTT Data Pipeline

### Inbound: Sensor Data

**Topic**: `MQTT_TOPIC_SENSORS` (e.g., `farmshield/sensors`)  
**Sender**: ESP32 firmware  
**Frequency**: Configurable in ESP32 firmware (typically 10–30 seconds)  
**Payload**: JSON

```json
{
  "device": "farmshield_node1",
  "temperature": 29.1,
  "humidity": 58.0,
  "soil": 42.5,
  "ph": 6.81,
  "tds": 410.0,
  "rain": 3200,
  "motion": false,
  "npk": { "n": 45, "p": 30, "k": 60, "ok": true },
  "color": { "r": 80, "g": 140, "b": 60 },
  "pump": false,
  "mode": "AUTO",
  "uptime_s": 3601
}
```

**Processing**:
1. `mqtt/handlers.py` receives bytes
2. Decodes UTF-8 → JSON
3. Calls `ingestion.process(data)`
4. Validates → Writes → Broadcasts → Checks thresholds

### Outbound: Control Commands

**Topics** (three subtopics):
- `MQTT_TOPIC_CONTROL_PUMP` (e.g., `farmshield/control/pump`)
- `MQTT_TOPIC_CONTROL_MODE` (e.g., `farmshield/control/mode`)
- `MQTT_TOPIC_CONTROL_BUZZER` (e.g., `farmshield/control/buzzer`)

**Sender**: Backend (via `control.py` service)  
**Receiver**: ESP32 firmware  
**Payload**: Raw string (not JSON!)

```
Topic: farmshield/control/pump
Payload: ON
---
Topic: farmshield/control/mode
Payload: AUTO
---
Topic: farmshield/control/buzzer
Payload: OFF
```

**Triggering**: HTTP endpoint
```bash
curl -X POST http://localhost:8000/api/v1/control/pump \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"state": "ON"}'
```

### Outbound: Alerts

**Topic**: `MQTT_TOPIC_ALERTS` (e.g., `farmshield/alerts`)  
**Sender**: Backend (via `ingestion.py` after threshold breach)  
**Receiver**: ESP32 firmware (can trigger buzzer, LED, etc.)  
**Payload**: JSON

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "SOIL_DRY",
  "severity": "WARNING",
  "message": "Soil moisture below threshold (28.5% < 30%)"
}
```

---

## Reusable Modules & Functions

### Common Imports Pattern

```python
# Service layer (no HTTP concerns)
from app.config import settings
from app.db.models import SensorReading, Alert
from app.db.session import AsyncSessionLocal
from app.schemas.sensor import SensorReadingOut
import structlog

logger = structlog.get_logger(__name__)

async def my_service_function(db: AsyncSession, device_id: str):
    # Use db for queries
    # Use settings for config
    # Use logger for logging
    # Return plain data (dict or Pydantic model)
    pass
```

### Database Query Pattern

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

async def get_readings_since(db: AsyncSession, device_id: str, hours: int):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(SensorReading)
        .where(SensorReading.device_id == device_id, SensorReading.time >= cutoff)
        .order_by(SensorReading.time.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
```

### MQTT Publish Pattern

```python
# In control.py or alert service
from app.mqtt.client import fast_mqtt
from app.config import settings

await fast_mqtt.publish(
    settings.mqtt_topic_control_pump,
    "ON",  # payload as string
    qos=settings.mqtt_qos
)
```

### WebSocket Broadcast Pattern

```python
# After inserting sensor reading
from app.services.websocket import ws_manager
from app.schemas.sensor import SensorReadingOut

reading_out = SensorReadingOut.model_validate(reading)
await ws_manager.broadcast({
    "type": "sensor_reading",
    "data": reading_out.model_dump(),
})
```

### Dependency Injection Pattern

```python
# In route handler
from fastapi import APIRouter, Depends
from app.dependencies import get_db, require_auth

@router.get("/endpoint")
async def my_endpoint(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_auth),
):
    # db is injected, auth is validated
    pass
```

### Logging Pattern

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info("operation_name", device_id=device_id, reading_count=len(readings))
logger.warning("unusual_condition", reason="low_battery", voltage_v=2.8)
logger.error("critical_failure", exc_info=True, topic=mqtt_topic)
```

### Error Handling Pattern

```python
from fastapi import HTTPException, status

# Raise HTTPException for expected client errors
if reading is None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No reading found for device {device_id}"
    )

# Log and re-raise for unexpected errors
except ValidationError as e:
    logger.error("validation_failed", errors=e.errors())
    raise
```

---

## Adding New Features

### Example: Add New Sensor Field

**Scenario**: ESP32 adds a new sensor (e.g., light level in lux)

**Steps**:

1. **Update ESP32 firmware** (outside scope, but firmware must publish a new field in MQTT JSON)

2. **Update `.env.example`** — add alert threshold for new sensor:
   ```dotenv
   ALERT_LIGHT_LOW_LUX=100.0
   ```

3. **Update `config.py`** — add setting:
   ```python
   alert_light_low_lux: float = 100.0
   ```

4. **Update `db/models.py`** — add column:
   ```python
   class SensorReading(Base):
       # ... existing fields ...
       light_lux: Mapped[float | None] = mapped_column(Double, nullable=True)
   ```

5. **Create Alembic migration**:
   ```bash
   cd backend/server
   alembic revision --autogenerate -m "add_light_lux_sensor"
   ```
   Edit generated file in `alembic/versions/` to customize if needed.

6. **Update `schemas/sensor.py`** — add to `SensorPayload`:
   ```python
   class SensorPayload(BaseModel):
       # ... existing fields ...
       light_lux: float | None = Field(default=None, alias="light")
   ```

7. **Update `services/alert.py`** — add threshold check:
   ```python
   def evaluate_thresholds(reading: SensorReadingOut) -> list[dict]:
       alerts: list[dict] = []
       
       # ... existing checks ...
       
       if reading.light_lux is not None and reading.light_lux < settings.alert_light_low_lux:
           alerts.append({
               "type": "LIGHT_LOW",
               "severity": "WARNING",
               "message": f"Light level too low ({reading.light_lux} lux < {settings.alert_light_low_lux} lux)"
           })
       
       return alerts
   ```

8. **Update API docs** — add to `API_REFERENCE.md`:
   ```markdown
   | `light_lux` | `float | null` | lux | Ambient light level |
   ```

9. **Test**:
   ```bash
   pytest tests/test_ingestion.py -v
   ```

### Example: Add New API Endpoint

**Scenario**: Add endpoint to get control history (pump on/off events)

**Steps**:

1. **Create migration** if needed (new DB table for control events):
   ```bash
   alembic revision -m "add_pump_events_table"
   ```

2. **Update `db/models.py`**:
   ```python
   class ControlEvent(Base):
       __tablename__ = "control_events"
       id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
       time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
       device_id: Mapped[str] = mapped_column(Text, nullable=False)
       command_type: Mapped[str] = mapped_column(Text, nullable=False)  # "pump", "mode", "buzzer"
       command_state: Mapped[str] = mapped_column(Text, nullable=False)
   ```

3. **Create schema** in `schemas/control.py`:
   ```python
   class ControlEventOut(BaseModel):
       id: uuid.UUID
       time: datetime
       device_id: str
       command_type: str
       command_state: str
       model_config = ConfigDict(from_attributes=True)
   ```

4. **Create service** function:
   ```python
   # In services/control.py (new file or extend existing)
   async def get_control_history(
       db: AsyncSession,
       device_id: str,
       hours: int = 24,
       limit: int = 100,
   ) -> tuple[list[ControlEvent], int]:
       cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
       count_stmt = select(func.count()).select_from(ControlEvent).where(
           ControlEvent.device_id == device_id,
           ControlEvent.time >= cutoff,
       )
       count = await db.execute(count_stmt)
       
       data_stmt = (
           select(ControlEvent)
           .where(ControlEvent.device_id == device_id, ControlEvent.time >= cutoff)
           .order_by(ControlEvent.time.desc())
           .limit(limit)
       )
       result = await db.execute(data_stmt)
       events = result.scalars().all()
       return events, count.scalar()
   ```

5. **Create route** in `api/v1/control.py`:
   ```python
   @router.get("/history", response_model=list[ControlEventOut])
   async def get_history(
       device_id: str = Query(default="farmshield_node1"),
       hours: int = Query(default=24, ge=1, le=168),
       limit: int = Query(default=100, ge=1, le=1000),
       db: AsyncSession = Depends(get_db),
   ):
       events, _ = await control_service.get_control_history(db, device_id, hours, limit)
       return events
   ```

6. **Test**:
   ```bash
   pytest tests/test_control.py::test_get_control_history -v
   ```

### Example: Enable ML Inference

**Scenario**: You have a trained irrigation model and want to run predictions on every sensor reading

**Steps**:

1. **Obtain model file**: Place `.pkl` or `.tflite` model in `server/app/services/ml/models/`
   ```bash
   # Example sklearn model
   server/app/services/ml/models/irrigation_model.pkl
   ```

2. **Update `.env`**:
   ```dotenv
   ML_ENABLED=true
   ML_MODEL_TYPE=sklearn  # or "tflite"
   ML_MODEL_PATH=app/services/ml/models/irrigation_model.pkl
   ```

3. **Rebuild Docker image** (model will be loaded at startup):
   ```bash
   docker compose up --build
   ```

4. **Verify**: Check logs for `ml_runner_loaded`

5. **Query predictions**: GET `/api/v1/sensors/ml_inferences` (endpoint already exists, or create if needed)

### Example: Enable Chat Feature

**Scenario**: You want to add Gemini chatbot that can answer questions about farm data

**Steps**:

1. **Get Gemini API key** from https://aistudio.google.com/app/apikey

2. **Update `.env`**:
   ```dotenv
   CHAT_ENABLED=true
   GEMINI_API_KEY=<your-key>
   GEMINI_MODEL=gemini-2.0-flash
   FAISS_INDEX_PATH=app/services/chat/faiss_index
   ```

3. **Add knowledge base documents** to `server/app/services/chat/knowledge/`:
   ```
   knowledge/
   ├── farming_tips.md
   ├── soil_management.md
   └── irrigation_guide.md
   ```

4. **Rebuild container** (chat dependencies will be auto-installed):
   ```bash
   docker compose up --build
   ```

5. **Query chatbot**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/chat/query \
     -H "Authorization: Bearer <API_KEY>" \
     -H "Content-Type: application/json" \
     -d '{"question": "What should I do if soil moisture is too high?"}'
   ```

---

## Testing Strategy

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (test client, mock DB)
├── test_sensors.py          # Sensor endpoints + service
├── test_control.py          # Control endpoints + service
├── test_ingestion.py        # MQTT pipeline, thresholds
├── test_ml.py               # ML runner (if ML_ENABLED)
└── test_chat.py             # Chat agent (if CHAT_ENABLED)
```

### Running Tests

```bash
# All tests
pytest

# Single file
pytest tests/test_sensors.py -v

# Single test
pytest tests/test_sensors.py::test_get_latest_reading -v

# With coverage
pytest --cov=app --cov-report=html
```

### Test Fixtures (conftest.py)

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

@pytest.fixture
async def test_db():
    """In-memory SQLite database for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield async_session_maker
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client(test_db):
    """FastAPI test client."""
    app = create_app()
    # Override get_db dependency
    async def override_get_db():
        async with test_db() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Example Test

```python
async def test_get_latest_reading(client, test_db):
    """Test GET /sensors/latest endpoint."""
    # Arrange: Insert test data
    async with test_db() as db:
        reading = SensorReading(
            time=datetime.now(timezone.utc),
            device_id="test_device",
            soil_pct=50.0,
            temp_c=25.0,
            pump_on=False,
        )
        db.add(reading)
        await db.commit()
    
    # Act
    response = await client.get(
        "/api/v1/sensors/latest?device_id=test_device"
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == "test_device"
    assert data["soil_pct"] == 50.0
    assert data["temp_c"] == 25.0
```

### Testing MQTT Pipeline

```python
async def test_mqtt_ingestion(test_db):
    """Test ingestion.process() with mock payload."""
    payload = {
        "device": "test_device",
        "temperature": 28.0,
        "humidity": 60.0,
        "soil": 45.0,
    }
    
    await ingestion.process(payload)
    
    async with test_db() as db:
        result = await db.execute(
            select(SensorReading).where(
                SensorReading.device_id == "test_device"
            )
        )
        reading = result.scalar_one()
        assert reading.temp_c == 28.0
        assert reading.soil_pct == 45.0
```

---

## Deployment & Docker

### Docker Compose Files

**`docker-compose.yml`** — Main configuration  
**`docker-compose.override.yml`** — Local dev overrides (mounts source code for reload)

### Building & Running Locally

```bash
# Build images
docker compose build

# Start all containers
docker compose up

# View logs
docker compose logs -f farmshield-fastapi

# Stop
docker compose down
```

### Deployment to Raspberry Pi

1. **Update `.env` for Pi**:
   ```dotenv
   TARGET_ENV=pi
   FASTAPI_RELOAD=false
   DB_HOST=192.168.1.50  # Pi's LAN IP
   MQTT_BROKER_HOST=192.168.1.50
   ESP32_MQTT_TARGET_IP=192.168.1.50  # Tell ESP32 where Pi is
   ```

2. **Copy to Pi**:
   ```bash
   scp -r backend/ pi@192.168.1.50:/home/pi/farmshield/
   ```

3. **SSH into Pi**:
   ```bash
   ssh pi@192.168.1.50
   cd /home/pi/farmshield/backend
   ```

4. **Run**:
   ```bash
   docker compose up --build -d
   ```

5. **Verify**:
   ```bash
   curl http://192.168.1.50:8000/api/v1/health
   ```

### Key Docker Settings

**`server/Dockerfile`**:
- Base image: `python:3.13-slim`
- Installs dependencies from `pyproject.toml`
- Conditionally installs chat/ML extras based on env vars
- Runs `entrypoint.sh` which:
  1. Runs Alembic migrations
  2. Starts FastAPI server

**`mosquitto/config/mosquitto.conf`**:
- Listener on port 1883 (plain MQTT, no TLS in PRD scope)
- ACL based on username

**Volume mounts**:
- `mosquitto_data` → persists MQTT queue
- `timescaledb_data` → persists database
- Local source code (dev) → enables FastAPI reload

---

---

## Audio Pest Detection Feature (AUDIO_ENABLED)

### Overview

When `AUDIO_ENABLED=true`, FarmShield adds acoustic pest detection: the ESP32 streams FFT frequency band data via MQTT, a rule-based classifier identifies pest species (grasshopper, cricket, cicada, mosquito, or no_pest), and automated alerts + buzzer trigger on detection. Includes a demo endpoint for judge demonstrations.

### Architecture

**New Files Created:**
- `app/schemas/audio.py` — AudioPayload (MQTT inbound), AudioInferenceOut (API response), DemoTriggerRequest, DemoTriggerResponse
- `app/services/audio_inference.py` — Rule-based classifier + processing pipeline
- `app/api/v1/audio.py` — GET /latest, GET /history, POST /demo endpoints

**Modified Files:**
- `app/config.py` — Added 4 settings: `audio_enabled`, `audio_mqtt_topic`, `audio_alert_threshold`, `audio_publish_interval_s`
- `app/db/models.py` — MLInference model reused (stores with `model_name="audio_rule_v1"`)
- `app/mqtt/handlers.py` — Added conditional audio MQTT handler (if `AUDIO_ENABLED=true`)
- `app/api/v1/router.py` — Conditionally register audio router (if `AUDIO_ENABLED=true`)

### Data Flow

```
ESP32 (FFT bands) 
  ↓ (MQTT: farmshield/audio)
handlers.py (on_audio_message)
  ↓
audio_inference.process_audio()
  ├─ validate payload (AudioPayload schema)
  ├─ classify(payload) → returns pest_class, confidence
  ├─ persist to MLInference table (model_name="audio_rule_v1")
  ├─ if confidence >= threshold:
  │    ├─ publish "ON" to buzzer MQTT topic
  │    ├─ create alert via alert.py
  │    └─ log warning
  └─ broadcast {type: "audio_detection", data: {...}} to WebSocket
```

### Classification Logic (Rule-Based)

Classifier returns one of 5 classes based on FFT bands + dB level:

| Class | Frequency Range | Rule | Confidence Formula |
|---|---|---|---|
| **mosquito** | < 900 Hz | `band_0 > 60 dB` | `0.70 + (band_0 / 300)` |
| **cicada** | 900–3500 Hz | `db > 65` | `0.72 + (db / 350)` |
| **cricket** | 3500–5500 Hz | `band_4 > 55 dB` | `0.68 + (band_4 / 280)` |
| **grasshopper** | > 5000 Hz | `band_5 > 50 dB` | `0.71 + (band_5 / 290)` |
| **no_pest** | any | `db < 42` (noise floor) | 0.88–0.94 (fixed) |

Confidence is clamped to `[0.01, 0.99]`.

### API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/audio/latest?deviceid=...` | Bearer | Latest audio inference |
| `GET` | `/api/v1/audio/history?deviceid=...&limit=50&offset=0` | Bearer | Paginated history |
| `POST` | `/api/v1/audio/demo` | Bearer | Trigger demo detection |

**Demo Request:**
```json
{
  "pest_class": "grasshopper",
  "deviceid": "farmshield-node-1"
}
```

**Demo Response:**
```json
{
  "status": "ok",
  "pest_class": "grasshopper",
  "confidence": 0.976,
  "alert_triggered": true,
  "mqtt_payload_published": true
}
```

### Configuration

Add to `.env`:
```dotenv
AUDIO_ENABLED=true
AUDIO_MQTT_TOPIC=farmshield/audio
AUDIO_ALERT_THRESHOLD=0.75
AUDIO_PUBLISH_INTERVAL_S=10
```

### Database Schema

Reuses existing `MLInference` table:
- `model_name = "audio_rule_v1"`
- `prediction` → pest class (grasshopper, cricket, etc.)
- `confidence` → float 0.0–1.0
- `raw_output` → JSON with all confidence scores + `_db_level`, `_dominant_freq_hz`

No new table or migration required.

### Field Name Conventions

**Note on `deviceid` vs `device_id`:**
- **MQTT/Wire Format**: Uses `deviceid` (ESP32 hardware convention)
- **ORM/Database**: Uses `device_id` (FarmShield schema convention)
- **Schema Layer**: AudioPayload field is `deviceid`, converted to `device_id` for ORM

This dual naming is intentional — hardware protocols rarely match database naming.

### WebSocket Broadcast

When a pest is detected, all connected WebSocket clients receive:
```json
{
  "type": "audio_detection",
  "data": {
    "id": "uuid",
    "time": "2026-04-28T23:00:00Z",
    "deviceid": "farmshield-node-1",
    "pest_class": "grasshopper",
    "confidence": 0.976,
    "db_level": 74.3,
    "dominant_freq_hz": 5820.5,
    "all_scores": {
      "grasshopper": 0.976,
      "no_pest": 0.024,
      "cricket": 0.01,
      "cicada": 0.01,
      "mosquito": 0.01
    },
    "alert_triggered": true
  }
}
```

---

## Summary: File Control Map

| What | Where | Key Files |
|------|-------|-----------|
| **Entry point** | `app/main.py` | Lifespan, app creation |
| **Configuration** | `app/config.py` | Settings class |
| **Routes** | `api/v1/` | Each resource module (sensors.py, etc.) |
| **Models** | `db/models.py` | SensorReading, Alert, MLInference |
| **Schemas** | `schemas/` | Pydantic validation models |
| **MQTT inbound** | `mqtt/handlers.py`, `services/ingestion.py` | Parse & process |
| **MQTT outbound** | `services/control.py`, `services/alert.py` | Publish commands |
| **Alerts** | `services/alert.py` | Threshold evaluation |
| **ML (optional)** | `services/ml/runner.py` | Load & inference |
| **Chat (optional)** | `services/chat/` | RAG, SQL tools, agent |
| **Audio (optional)** | `services/audio_inference.py`, `api/v1/audio.py` | Acoustic pest detection |
| **WebSocket** | `services/websocket.py`, `api/v1/ws.py` | Broadcast |
| **Auth** | `core/auth.py` | Bearer token validation |
| **Logging** | `core/logging.py` | Structured logging setup |
| **Exceptions** | `core/exceptions.py` | Error handling |
| **Database** | `db/session.py` | SQLAlchemy setup |
| **Migrations** | `alembic/` | Schema versioning |
| **Tests** | `tests/` | pytest fixtures & tests |
| **Environment** | `.env.example` | All configuration reference |
| **Docker** | `docker-compose.yml` | Services config |

---

## Checklist: Before Adding a Feature

- [ ] **Read this document** — understand the architecture
- [ ] **Review relevant PRD section** — understand requirements
- [ ] **Check `.env.example`** — understand existing config pattern
- [ ] **Run existing tests** — ensure baseline passes
- [ ] **Write test first** — red → green → refactor
- [ ] **Update `.env.example`** — document new config
- [ ] **Update `config.py`** — add new Setting
- [ ] **Update database schema** — Alembic migration if needed
- [ ] **Update schemas** — Pydantic models for input/output
- [ ] **Update services** — implement business logic
- [ ] **Update routes** — expose via API or MQTT
- [ ] **Update docs** — API_REFERENCE.md, BACKEND_ARCHITECTURE.md
- [ ] **Test locally** — docker compose up + manual testing
- [ ] **Test on Pi** — if hardware-dependent

---

## Quick Reference: File Ownership

**If you're adding...**
- New sensor field → modify `models.py`, `schemas/sensor.py`, `services/ingestion.py`, `.env.example`, `config.py`
- New API endpoint → create route in `api/v1/`, create service in `services/`, update `schemas/`
- New alert type → modify `services/alert.py`, `.env.example`, `config.py`
- ML inference → modify `services/ml/runner.py`, update startup in `main.py`
- Chat feature → modify `services/chat/`, update startup in `main.py`
- Control command → modify `services/control.py`, `api/v1/control.py`, `schemas/control.py`
- Database table → create migration, add model to `db/models.py`
- Configuration → `.env.example`, `config.py`
- Dependency → `dependencies.py`
- Authentication scheme → `core/auth.py`
- Error handling → `core/exceptions.py`

---

**Document Version:** 1.0.0  
**Last Reviewed:** April 28, 2026  
**Maintainer:** FarmShield Team

For questions or clarifications, refer to PRD.md, PRD_Feature_ChatBot.md, or API_REFERENCE.md.
