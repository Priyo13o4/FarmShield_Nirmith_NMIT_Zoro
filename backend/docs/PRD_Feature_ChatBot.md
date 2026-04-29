# FarmShield Chatbot — Feature PRD

**Version:** 1.0.0
**Parent PRD:** FarmShield Backend PRD v1.0.0 (+ Amendments 1 & 2)
**Status:** Final
**Scope:** Chatbot backend feature only. Frontend rendering of chat UI is out of scope.

***

## 1. Feature Overview

Add a conversational AI assistant to FarmShield that answers natural language questions about live sensor data and general farming knowledge. The assistant is backed by Google Gemini via API — no local model, no GPU required. It routes queries through two distinct retrieval paths: text-to-SQL for live sensor data and FAISS vector search for domain knowledge.

The entire feature is gated behind `CHAT_ENABLED` in `.env`. When `CHAT_ENABLED=false` (the default), no LangChain code is imported, no Gemini connection is attempted, and zero RAM overhead is added. This matches the identical contract established by `ML_ENABLED` in the parent PRD.

***

## 2. Hard Constraints

| Constraint | Value |
|---|---|
| No new Docker containers | Everything runs inside the existing `farmshield-fastapi` container |
| RAM budget for this feature | ≤ 120 MB when enabled |
| No local LLM or embeddings model | Gemini API only — inference is remote |
| DB access from chatbot | Read-only — chatbot cannot write to any table |
| `CHAT_ENABLED=false` overhead | Exactly zero — no imports, no instantiation |
| Fallback behaviour | None permitted without explicit env config and WARNING log — same rule as parent PRD §20.1 |
| Session persistence | In-memory only — chat history is not persisted to DB |

***

## 3. Technology Stack Additions

| Package | Minimum Version | Purpose |
|---|---|---|
| `langchain` | ≥ 0.3.0 | Agent orchestration framework |
| `langchain-google-genai` | ≥ 2.0.0 | Gemini LLM + embedding model bindings |
| `langchain-community` | ≥ 0.3.0 | SQLDatabase utility, FAISS wrapper |
| `faiss-cpu` | ≥ 1.9.0 | Vector index for knowledge base RAG |

Added as an optional dependency group in `pyproject.toml`:

```toml
[project.optional-dependencies]
chat = [
    "langchain>=0.3.0",
    "langchain-google-genai>=2.0.0",
    "langchain-community>=0.3.0",
    "faiss-cpu>=1.9.0",
]
```

Install: `pip install -e ".[chat]"`

The Dockerfile must install this group when `CHAT_ENABLED=true`. The entrypoint script handles this:

```sh
# entrypoint.sh — add before alembic upgrade head
if [ "$CHAT_ENABLED" = "true" ]; then
    pip install --no-cache-dir -e ".[chat]"
fi
```

This keeps the base image lean and only pulls LangChain when the feature is actually used.

***

## 4. Environment Configuration

All new variables added to `.env.example` with inline comments. No variable may be hardcoded in source.

```dotenv
# =============================================================================
# CHATBOT FEATURE
# =============================================================================

# Master switch — false = zero overhead, feature entirely absent from runtime.
# Changing this requires container restart.
CHAT_ENABLED=false

# Google AI Studio API key.
# Get one free at: https://aistudio.google.com/app/apikey
# Required when CHAT_ENABLED=true. App fails at startup if missing.
GEMINI_API_KEY=your-key-here

# Gemini model for chat completions.
# gemini-2.0-flash → fast, free tier, recommended for demo
# gemini-2.5-pro   → higher quality, slower, uses more quota
GEMINI_MODEL=gemini-2.0-flash

# Gemini model for generating embeddings of knowledge base documents.
# Do not change unless Google deprecates this model.
GEMINI_EMBEDDING_MODEL=models/text-embedding-004

# Absolute path inside the container where the FAISS index is persisted.
# Mount a volume here if you want the index to survive container rebuilds.
# If the path does not exist at startup, the index is built from scratch
# from the documents in services/chat/knowledge/ — this takes ~10-20s.
FAISS_INDEX_PATH=app/services/chat/faiss_index

# Maximum number of previous message pairs (human + assistant) to keep
# in a session's context window. Higher = better memory, more tokens used.
CHAT_MAX_HISTORY=10

# Maximum tokens Gemini may generate per response.
CHAT_MAX_OUTPUT_TOKENS=1024

# Temperature for Gemini completions.
# 0.0 = fully deterministic. 0.2 = slight variation, recommended.
# Never go above 0.5 for a factual assistant.
CHAT_TEMPERATURE=0.2

# Read-only DB user for the SQL tool.
# This user must exist in TimescaleDB — see §6.3 for creation SQL.
# If not set, the chat SQL tool falls back to the main DB user with a
# WARNING log. This fallback is acceptable for demo but not production.
CHAT_DB_READONLY_USER=farmshield_readonly
CHAT_DB_READONLY_PASSWORD=readonly123
```

***

## 5. Repository Changes

```
server/app/
├── services/
│   └── chat/                              ← new module
│       ├── __init__.py
│       ├── agent.py                       ← LangChain agent + executor
│       ├── sql_tool.py                    ← text-to-SQL LangChain tool
│       ├── rag_tool.py                    ← FAISS retriever + Gemini embeddings tool
│       ├── session_store.py               ← in-memory session chat history
│       └── knowledge/                     ← drop farming .md/.txt docs here
│           ├── soil_guide.md
│           ├── irrigation_guide.md
│           └── npk_reference.md
├── api/
│   └── v1/
│       └── chat.py                        ← new route file
└── schemas/
    └── chat.py                            ← new schema file

tests/
└── test_chat.py                           ← new test file
```

**Files modified (not created):**

| File | Change |
|---|---|
| `app/config.py` | Add all new env vars as typed `Settings` attributes |
| `app/main.py` | Conditional chat module init in lifespan |
| `app/api/v1/router.py` | Include chat router when `CHAT_ENABLED=true` |
| `server/entrypoint.sh` | Conditional `pip install -e ".[chat]"` |
| `pyproject.toml` | Add `[chat]` optional dependency group |
| `.env.example` | Add all new vars with comments |

***

## 6. File Responsibilities

### 6.1 `services/chat/agent.py`

**Single responsibility:** Own the LangChain agent — LLM instantiation, tool binding, prompt, and executor. Nothing else.

```python
# Exact interface the rest of the codebase uses:

class FarmShieldAgent:
    def load(self) -> None:
        """
        Called once during app lifespan startup when CHAT_ENABLED=true.
        Instantiates ChatGoogleGenerativeAI, binds tools, builds AgentExecutor.
        Raises ValueError at startup if GEMINI_API_KEY is missing or invalid.
        App must not start if this raises — same contract as ML runner.
        """

    async def invoke(
        self,
        message: str,
        session_id: str,
    ) -> dict:
        """
        Runs the agent for one user message.
        Retrieves history from session_store, appends to context.
        Returns {"reply": str, "sources": list[str], "session_id": str}
        Never raises — on any error returns:
        {"reply": "I encountered an error processing your request.",
         "sources": [], "session_id": session_id, "error": "<message>"}
        and logs at ERROR level.
        """

    async def stream(
        self,
        message: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Same as invoke() but yields token strings as they arrive from Gemini.
        Used for SSE streaming endpoint.
        """
```

**System prompt (defined as a constant in this file, not in config):**

```
You are FarmShield Assistant — an AI embedded in a smart agriculture monitoring system.

You have access to two tools:
- query_sensor_data: use for ANY question involving numbers, readings, sensor values,
  alerts, pump status, or anything that requires looking up actual farm data.
  Always use this for questions like "what is", "how much", "when did", "show me".
- search_farming_knowledge: use for general questions about crop care, soil science,
  irrigation techniques, nutrient deficiencies, or best practices.
  Use this when no sensor data lookup is needed.

Rules:
- Always use query_sensor_data before making any claim about current or historical conditions.
- Never invent sensor values. If a query returns no data, say so.
- Keep answers concise and actionable. Farmers want facts, not essays.
- If a question is unrelated to agriculture or this farm system, politely decline.
- Default device_id for all queries: {device_id}
```

The `device_id` placeholder is filled from `settings.mqtt_client_id` at load time. This keeps the prompt dynamic without hardcoding `esp32-node-1`.

***

### 6.2 `services/chat/sql_tool.py`

**Single responsibility:** Expose a LangChain `@tool` that translates natural language to SQL and runs it against TimescaleDB read-only.

```python
@tool
def query_sensor_data(question: str) -> str:
    """
    Query live or historical sensor data from the FarmShield database.
    Use for ANY question about soil moisture, temperature, humidity,
    TDS, rain, NPK levels, leaf colour, pump status, or alerts.
    Input: a natural language question about farm data.
    Output: a text answer derived from real database results.
    """
```

**Implementation notes:**
- Uses `langchain_community.utilities.SQLDatabase` with `include_tables=["sensor_readings", "alerts"]` — the chatbot must never see `ml_inferences` or `alembic_version`
- `sample_rows_in_table_info=3` — gives the LLM schema context with example values
- Connection string uses `CHAT_DB_READONLY_USER` / `CHAT_DB_READONLY_PASSWORD` from settings
- If readonly user is not configured, logs WARNING and uses main DB user — this fallback is only acceptable for demo, must be documented
- Query results are truncated to 50 rows before returning to the LLM to prevent token overflow
- Raw SQL generated by LangChain is logged at DEBUG level for traceability

***

### 6.3 Read-Only Database User

Migration `0003_readonly_user.py` creates the read-only PostgreSQL user and grants appropriate permissions:

```sql
-- 0003_readonly_user.py upgrade()
CREATE USER farmshield_readonly WITH PASSWORD 'readonly123';
GRANT CONNECT ON DATABASE farmshield TO farmshield_readonly;
GRANT USAGE ON SCHEMA public TO farmshield_readonly;
GRANT SELECT ON sensor_readings TO farmshield_readonly;
GRANT SELECT ON alerts TO farmshield_readonly;
-- Explicitly denied: ml_inferences, alembic_version, any future write tables
```

**Important:** The password here must match `CHAT_DB_READONLY_PASSWORD` in `.env`. Since both are in the same TimescaleDB container, this migration handles user creation idempotently:

```python
op.execute("DO $$ BEGIN "
           "CREATE USER farmshield_readonly WITH PASSWORD 'readonly123'; "
           "EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
```

***

### 6.4 `services/chat/rag_tool.py`

**Single responsibility:** Expose a LangChain `@tool` backed by a FAISS vector index over farming knowledge documents.

```python
@tool
def search_farming_knowledge(query: str) -> str:
    """
    Search the FarmShield farming knowledge base for information about
    crop care, soil science, irrigation techniques, nutrient management,
    plant diseases, or agricultural best practices.
    Do NOT use this for questions about actual sensor readings or alerts.
    Input: a natural language question about farming or agriculture.
    Output: relevant information from the knowledge base.
    """
```

**FAISS index lifecycle:**

```
App startup (CHAT_ENABLED=true)
  │
  ├─ Does FAISS_INDEX_PATH exist on disk?
  │   ├─ YES → load index from disk (~100ms)
  │   └─ NO  → build index from scratch:
  │             1. Load all .md and .txt files from services/chat/knowledge/
  │             2. Split into chunks (chunk_size=500, overlap=50)
  │             3. Embed each chunk via Gemini text-embedding-004 API
  │             4. Build FAISS index
  │             5. Persist to FAISS_INDEX_PATH
  │             (Takes 10-30s depending on doc count + API latency)
  │
  └─ Index ready — retriever configured for top-3 chunks per query
```

**Volume mount for index persistence** (add to `docker-compose.override.yml`):
```yaml
fastapi:
  volumes:
    - ./server/app/services/chat/faiss_index:/app/app/services/chat/faiss_index
```

Without this mount, the index rebuilds from scratch on every container restart, costing ~20 extra seconds at startup and Gemini API embedding calls each time.

**Knowledge base documents** — minimum required files for a working demo:

| File | Contents |
|---|---|
| `soil_guide.md` | Soil moisture requirements, interpretation of NPK values |
| `irrigation_guide.md` | When to irrigate, TDS thresholds for water quality, rain sensor interpretation |
| `npk_reference.md` | Nitrogen/phosphorus/potassium deficiency symptoms, recommended NPK ratios |

These files must be committed to the repo. They do not need to be exhaustive — 3–5 pages of plain text per file is sufficient for a demo knowledge base.

***

### 6.5 `services/chat/session_store.py`

**Single responsibility:** In-memory store for per-session chat history.

```python
class SessionStore:
    """
    Thread-safe in-memory store for chat session histories.
    Keys are session_id strings (UUID recommended from frontend).
    Values are lists of LangChain BaseMessage objects (HumanMessage + AIMessage).
    History is capped at CHAT_MAX_HISTORY message pairs.
    Sessions are never persisted — all history is lost on container restart.
    There is no session expiry — sessions accumulate until container restart.
    For a demo this is acceptable. For production, add TTL.
    """

    def get_history(self, session_id: str) -> list[BaseMessage]
    def append(self, session_id: str, human: str, assistant: str) -> None
    def clear(self, session_id: str) -> None
```

***

### 6.6 `api/v1/chat.py`

Route handlers only. Each handler calls one service function and returns its result. No agent logic here.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/chat/message` | ✅ | Send a message, get a complete reply |
| `GET` | `/chat/stream` | ✅ (query param) | SSE stream of a reply token by token |
| `DELETE` | `/chat/session/{session_id}` | ✅ | Clear session history |

***

## 7. API Endpoint Specification

### `POST /api/v1/chat/message`

Non-streaming. Returns complete reply after Gemini finishes generation.

**Request body:**
```json
{
  "message": "What was the average soil moisture in the last 6 hours?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | `string` | ✅ | Min length 1, max length 2000 |
| `session_id` | `string` | ✅ | Frontend generates UUID v4 per user session. Reuse across messages for context |

**Response 200:**
```json
{
  "reply": "The average soil moisture over the last 6 hours was 47.3%. It peaked at 58.1% at 14:20 IST and dropped to a low of 38.4% at 17:45 IST. Current threshold for irrigation is 30%.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "sources": ["sensor_data"],
  "ts": 1745700000
}
```

`sources` is a list of which tools were used: `["sensor_data"]`, `["farming_knowledge"]`, or `["sensor_data", "farming_knowledge"]`. Frontend can use this to show a source badge.

**Response 503** (when `CHAT_ENABLED=false`):
```json
{
  "detail": "Chat feature is not enabled on this deployment.",
  "type": "FEATURE_DISABLED"
}
```

***

### `GET /api/v1/chat/stream`

SSE streaming. Frontend connects here to get the typing effect.

**Query params:**

| Param | Type | Required | Notes |
|---|---|---|---|
| `message` | `string` | ✅ | URL-encoded user message |
| `session_id` | `string` | ✅ | Same session UUID |
| `api_key` | `string` | When `AUTH_ENABLED=true` | Same pattern as WebSocket |

**Response:** `text/event-stream`

```
data: {"token": "The "}
data: {"token": "average "}
data: {"token": "soil "}
...
data: {"token": "47.3%."}
data: {"done": true, "sources": ["sensor_data"], "session_id": "550e..."}
```

The `{"done": true}` event is the terminal signal. Frontend closes the connection on receiving it.

***

### `DELETE /api/v1/chat/session/{session_id}`

Clears chat history for a session. Call this when the user starts a new conversation.

**Response 200:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "cleared": true
}
```

**Response 404** if `session_id` not found in store:
```json
{
  "detail": "Session not found.",
  "type": "NOT_FOUND"
}
```

***

## 8. Pydantic Schemas (`schemas/chat.py`)

```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[str]    # subset of ["sensor_data", "farming_knowledge"]
    ts: int               # Unix timestamp of response

class SessionClearResponse(BaseModel):
    session_id: str
    cleared: bool
```

***

## 9. `main.py` Lifespan Changes

Add to the existing startup sequence **after** ML runner init:

```python
# Pseudocode — add to lifespan in correct position

if settings.chat_enabled:
    from app.services.chat.agent import farm_agent     # import ONLY when enabled
    from app.services.chat.rag_tool import rag_tool    # import ONLY when enabled
    log.info("chat_startup_begin")
    await rag_tool.load_or_build_index()               # FAISS load/build
    farm_agent.load()                                  # LLM + tools init
    log.info("chat_startup_complete")
```

**The `from` imports are inside the `if` block.** This is the only way to guarantee zero import overhead when `CHAT_ENABLED=false`. If the imports are at the top of `main.py`, Python loads LangChain regardless of the flag.

On shutdown (inside lifespan exit):

```python
if settings.chat_enabled:
    # No explicit cleanup needed — Gemini API is stateless HTTP
    log.info("chat_shutdown")
```

***

## 10. `config.py` Additions

```python
# Add to Settings class in config.py

# Chat
chat_enabled: bool = False
gemini_api_key: str = ""          # no default — must be set if chat_enabled=true
gemini_model: str = "gemini-2.0-flash"
gemini_embedding_model: str = "models/text-embedding-004"
faiss_index_path: str = "app/services/chat/faiss_index"
chat_max_history: int = 10
chat_max_output_tokens: int = 1024
chat_temperature: float = 0.2
chat_db_readonly_user: str = "farmshield_readonly"
chat_db_readonly_password: str = "readonly123"

@property
def chat_db_readonly_url(self) -> str:
    return (
        f"postgresql+asyncpg://{self.chat_db_readonly_user}:"
        f"{self.chat_db_readonly_password}@"
        f"{self.db_host}:{self.db_port}/{self.db_name}"
    )
```

Add a startup validator:

```python
@model_validator(mode="after")
def validate_chat_config(self) -> "Settings":
    if self.chat_enabled and not self.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY must be set when CHAT_ENABLED=true. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )
    return self
```

***

## 11. Health Endpoint Update

When `CHAT_ENABLED=true`, the `/health` response gains a `chat_ready` field:

```json
{
  "status": "ok",
  "mqtt_connected": true,
  "db_connected": true,
  "ml_enabled": false,
  "chat_enabled": true,
  "chat_ready": true,
  "version": "1.0.0"
}
```

`chat_ready` is `true` only when the FAISS index has loaded and the LLM has been instantiated. It is `false` during the startup window while the index is building. Frontend can poll `/health` to know when chat is available.

When `CHAT_ENABLED=false`, the `chat_enabled` and `chat_ready` keys are omitted entirely.

***

## 12. Testing Specification

### `tests/test_chat.py`

```python
# Required test cases:

# --- CHAT_ENABLED=false ---
test_chat_disabled_returns_503()
    # POST /chat/message → 503 with FEATURE_DISABLED type

# --- CHAT_ENABLED=true, mocked agent ---
test_chat_message_valid()
    # POST /chat/message with valid body → 200, reply is non-empty string

test_chat_message_empty_string_rejected()
    # POST /chat/message with message="" → 422

test_chat_message_too_long_rejected()
    # POST /chat/message with 2001-char message → 422

test_chat_session_preserves_history()
    # Two sequential messages with same session_id
    # Second call receives non-empty history list

test_chat_session_clear()
    # POST two messages, DELETE session, history is empty

test_chat_session_clear_not_found()
    # DELETE unknown session_id → 404

test_chat_agent_error_returns_graceful_response()
    # Mock agent.invoke() to raise Exception
    # Endpoint returns 200 with error reply message (not 500)
    # ERROR is logged

test_sql_tool_only_reads_allowed_tables()
    # Verify SQLDatabase include_tables contains only sensor_readings and alerts
    # ml_inferences and alembic_version must NOT be present

# --- RAG tool ---
test_rag_tool_builds_index_from_knowledge_dir()
    # Create temp knowledge dir with one .md file
    # Call rag_tool.load_or_build_index()
    # Verify FAISS index file written to disk

test_rag_tool_loads_existing_index()
    # Pre-build index, call load_or_build_index() again
    # Verify Gemini embed API not called (index loaded from disk, not rebuilt)
```

All tests mock `ChatGoogleGenerativeAI` and embedding calls — no real Gemini API calls in CI.

***

## 13. Non-Negotiables

All rules from parent PRD §20 apply. Additional rules for this feature:

1. **Gemini imports are conditional.** `langchain`, `langchain_google_genai`, and `faiss` must never appear in top-level imports in any file. They are imported inside `if settings.chat_enabled` blocks or inside the service module files themselves, which are only imported conditionally from `main.py`.

2. **The SQL tool is read-only by user, not by honour system.** The connection string must use `CHAT_DB_READONLY_USER`. If that user doesn't exist (migration hasn't run), the app logs ERROR at startup and sets `chat_ready=false` — it does not fall back to the write user silently.

3. **Agent errors never surface as 500s.** `agent.invoke()` catches all exceptions internally and returns the graceful error dict. The route handler always gets a valid `ChatResponse`-shaped dict.

4. **Session IDs are opaque strings.** The backend does not validate that `session_id` is a UUID. Any non-empty string is accepted. The frontend decides the format.

5. **Knowledge base documents are version-controlled.** The `.md` files in `services/chat/knowledge/` are committed to the repo. The FAISS index is **not** committed — it is built at runtime and optionally persisted via volume mount.

6. **`CHAT_MAX_HISTORY` is enforced strictly.** When a session exceeds `CHAT_MAX_HISTORY` pairs, the oldest pair is dropped before the next API call. The store must never grow unbounded.