# FarmShield Chatbot — Amendment 1: Dual-Mode Voice Layer

***

## Overview

This amendment extends the FarmShield chatbot with a **voice interaction layer**. The core principle is a **dual-mode architecture**: the system supports both text-based chat and voice-based chat, and switches between the two modes based on how the user initiates a message. Each mode uses a different underlying model and transport protocol, optimized for that modality. No changes are made to the existing text chat pipeline.

***

## Background and Motivation

The existing chatbot is text-only: the user types a message in the browser, the FastAPI backend processes it through a LangChain agent backed by Gemma 4 31B, and a text reply is returned. This works well for operators at a desk, but FarmShield's target users are farmers who may be in the field, wearing gloves, or unable to type. Voice input removes that friction.

The challenge is that no single model satisfies all constraints simultaneously:

- **Gemma 4 31B** handles structured reasoning, SQL tool calling, and FAISS RAG — but has no audio capability whatsoever.
- **Gemini 3 Flash Live** (`gemini-3.1-flash-live-preview`) supports native audio input/output and function calling — but uses a WebSocket (Live API) transport, not HTTP, and has a 131K token input limit.

Rather than choosing one or forcing a workaround, this amendment defines both modes as first-class citizens, selected at the moment of input.

***

## Goals

- Allow farmers to interact with FarmShield entirely by voice through the existing browser UI
- Preserve the full functionality of the text chat (SQL tool, FAISS RAG, session memory, streaming) without any modification
- Keep both modes running within the constraints of the Raspberry Pi deployment environment
- Ensure the transition between modes is seamless and invisible to the user — no page reload, no re-authentication, no session reset

***

## Non-Goals

- This amendment does not add a native mobile app or a separate voice-only device interface
- This amendment does not implement wake-word detection ("Hey FarmShield")
- This amendment does not support simultaneous text and voice in a single turn
- This amendment does not replace or refactor the existing LangChain agent or any of its tools
- This amendment does not change the database schema, sensor pipeline, or authentication system

***

## User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-V1 | Farmer in the field | Tap a mic button and speak my question | I can ask about soil moisture without typing |
| US-V2 | Farmer | Hear the answer read back to me | I don't have to look at the screen for the reply |
| US-V3 | Operator at desk | Continue typing as normal | My existing workflow is unaffected |
| US-V4 | Any user | Switch freely between voice and text in the same session | I can choose how to interact turn by turn |
| US-V5 | Any user | Have my session history preserved regardless of mode | My previous questions and answers persist across both |

***

## Architecture

### Dual-Mode Routing

The frontend determines the mode at the moment of submission:

- If the user clicks **Send** (or presses Enter) on a typed message → **Text Mode**
- If the user clicks the **Mic button**, records audio, and submits → **Voice Mode**

The backend exposes two separate endpoints. There is no shared endpoint that tries to detect modality — the mode is declared by the client.

```
Browser
├── Text input → POST /api/v1/chat/message        → Text Mode (existing)
└── Mic input  → WebSocket /api/v1/chat/voice/ws  → Voice Mode (new)
```

### Text Mode (Existing — No Changes)

**Transport:** HTTP POST  
**Model:** `gemma-4-31b-it` via Gemini API  
**Agent:** LangChain with SQL tool and FAISS RAG  
**Session:** Existing in-memory session store  
**Response format:** Streamed JSON (text)  

Text mode is fully defined in the parent PRD. This amendment makes no changes to it.

### Voice Mode (New)

**Transport:** WebSocket (persistent, bidirectional)  
**Model:** `gemini-3.1-flash-live-preview` via Gemini Live API  
**Function Calling:** Synchronous — the model pauses and waits for tool responses before continuing  
**Audio In:** Browser `MediaRecorder` → WebM or PCM audio bytes → sent over WebSocket  
**Audio Out:** Model returns audio bytes → streamed back over WebSocket → browser `AudioContext` plays  
**Session:** Shared session ID with text mode (session history is unified)  

***

## Mode-Switch Behavior

When a user switches from one mode to the other mid-session:

- The **session ID remains the same** — both modes read from and write to the same conversation history store
- No state is lost; the new mode picks up the full prior context
- The frontend does not need to close any connection proactively — the WebSocket for voice is opened on mic activation and closed on reply completion (or on explicit disconnect)
- There is no concept of a "locked" mode — every turn independently selects its mode based on input type

***

## Voice Mode — Detailed Specification

### Frontend Responsibilities

The frontend (browser) handles all audio hardware interaction. The backend never touches audio hardware.

**On mic button press:**
1. Request microphone permission via `getUserMedia`
2. Open a WebSocket connection to `/api/v1/chat/voice/ws?session_id={session_id}`
3. Start `MediaRecorder` — capture audio as `audio/webm` chunks
4. Stream audio chunks over the WebSocket as binary frames while the user is speaking
5. On mic button release (or silence detection): send a control message `{ "event": "end_of_speech" }` over the WebSocket

**On receiving response:**
1. Receive audio binary frames from the WebSocket
2. Decode and play via `AudioContext` / `AudioWorklet`
3. Optionally receive a `{ "event": "transcript", "text": "..." }` text frame to display the spoken reply as a subtitle in the chat UI
4. On `{ "event": "turn_complete" }`, close the WebSocket

**Mic button states:** idle → listening → processing → speaking  
**Error handling:** On WebSocket error or timeout, fall back to displaying a text error message in the chat UI

### Backend Responsibilities

The backend `/api/v1/chat/voice/ws` WebSocket endpoint:

1. Accepts the WebSocket connection, reads `session_id` from query params
2. Loads conversation history for that `session_id` from the shared session store
3. Opens a Live API session with `gemini-3.1-flash-live-preview`, passing:
   - System prompt (same farm context prompt used in text mode)
   - Tool definitions: SQL sensor query tool, FAISS RAG search tool
   - Session history: prior turns formatted as Live API message history
4. Streams incoming audio binary frames from the browser directly to the Live API session
5. When the model calls a tool (function calling), the backend:
   - Intercepts the tool call
   - Executes the actual tool (SQL query or FAISS search)
   - Returns the result to the Live API session
   - The model then continues generating its audio response
6. Streams audio response frames from the Live API back to the browser
7. After turn completion, writes the turn (transcript + reply text) to the shared session store
8. Closes the Live API session and the WebSocket

### Tool Definitions for Voice Mode

The same two tools used in text mode are registered with the Live API session. Tool definitions follow the Gemini function calling schema (JSON Schema format).

| Tool | Input | Output | Notes |
|------|-------|--------|-------|
| `query_sensor_data` | field_id, metric, time_range | JSON array of readings | Direct SQL query on TimescaleDB |
| `search_knowledge_base` | query_text | List of document chunks | FAISS similarity search |

The tool implementation code is shared with text mode — voice mode does not duplicate tool logic.

### Audio Format Specification

| Parameter | Value |
|-----------|-------|
| Input format (browser → backend) | `audio/webm; codecs=opus` (MediaRecorder default) |
| Input format (backend → Live API) | Passed through as-is; Live API accepts WebM |
| Output format (Live API → backend) | PCM 24kHz or as negotiated by Live API |
| Output format (backend → browser) | Binary WebSocket frames (PCM or as received) |
| Max turn duration | 60 seconds of audio input per turn |
| Silence threshold | Configurable; default 1.5 seconds of silence triggers `end_of_speech` |

***

## Session Unification

Both text mode and voice mode share a single session history store. The store key is `session_id`.

Each turn written to the store includes:
- `mode`: `"text"` or `"voice"`
- `user_input`: the text transcript of what was said or typed
- `assistant_reply`: the text of the reply
- `timestamp`: ISO 8601
- `tools_called`: list of tool names invoked during the turn

When voice mode loads history to pass to the Live API, it reads from this same store and reformats prior turns into the Live API's expected message history format. This means a farmer can ask a question by voice, then follow up by typing, and the model in either mode will have full context.

***

## Environment Variables

The following new environment variables are added. No existing variables are changed.

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `VOICE_ENABLED` | bool | Feature flag to enable/disable voice mode | `true` |
| `VOICE_MODEL` | string | Gemini Live model name | `gemini-3.1-flash-live-preview` |
| `VOICE_MAX_TURN_SECONDS` | int | Max audio input duration per turn (seconds) | `60` |
| `VOICE_SILENCE_TIMEOUT_MS` | int | Silence duration before auto end-of-speech (ms) | `1500` |
| `VOICE_SYSTEM_PROMPT_OVERRIDE` | string | Optional: override system prompt for voice turns | *(empty = use default)* |

***

## API Specification

### New Endpoint: WebSocket Voice Chat

**Path:** `ws://{host}/api/v1/chat/voice/ws`  
**Protocol:** WebSocket  
**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session identifier, shared with text mode |
| `language` | string | No | BCP-47 language tag hint, e.g. `hi-IN`, `en-IN` |

**Message Types (Client → Server):**

| Type | Format | Description |
|------|--------|-------------|
| Audio chunk | Binary frame | Raw audio bytes from MediaRecorder |
| End of speech | Text frame: `{"event":"end_of_speech"}` | Signals end of user's audio input |
| Cancel | Text frame: `{"event":"cancel"}` | Abort current turn |

**Message Types (Server → Client):**

| Type | Format | Description |
|------|--------|-------------|
| Audio chunk | Binary frame | Audio response bytes for playback |
| Transcript | Text frame: `{"event":"transcript","text":"..."}` | Text of the model's reply (for subtitles) |
| User transcript | Text frame: `{"event":"user_transcript","text":"..."}` | What the model understood the user said |
| Turn complete | Text frame: `{"event":"turn_complete"}` | Signals end of model response |
| Error | Text frame: `{"event":"error","message":"..."}` | Error description |

***

## Constraints and Tradeoffs

### Known Limitations of Voice Mode

| Limitation | Detail |
|------------|--------|
| Synchronous function calling | The Live API pauses audio generation while waiting for tool results. A SQL query that takes 2–3 seconds will cause a brief silence mid-response. This is an API-level behavior, not a bug. |
| No structured output | Voice mode cannot return structured JSON (e.g., chart data). Any visualizations must be requested via text mode. |
| Preview model stability | `gemini-3.1-flash-live-preview` is a preview release. API behavior, pricing, and availability may change. A fallback path is defined below. |
| 131K context window | Significantly smaller than Gemma 4 31B's context. Very long sessions may require history truncation before passing to the Live API. |
| Internet required | Live API is cloud-only. No offline voice operation. (Text mode has the same dependency.) |

### Fallback Behavior

If `VOICE_ENABLED=false`, or if the WebSocket connection fails to establish, the frontend:
- Hides the mic button
- Displays a non-blocking toast: *"Voice unavailable — please type your message"*
- Continues to operate in text mode without interruption

If a voice turn fails mid-conversation (WebSocket drops), the frontend closes the connection, displays an error in the chat UI, and leaves the user on the text input field.

***

## Raspberry Pi Deployment Considerations

All voice mode processing (Live API calls, tool execution, session history management) runs inside the existing `farmshield-fastapi` Docker container.

**No additional RAM is consumed** for model weights or audio processing libraries, because:
- The Live API session is managed remotely by Google
- Audio bytes are streamed through (not buffered in full) in both directions
- Tool execution re-uses the existing SQL and FAISS code paths

**New Python dependencies** to be added to `requirements.txt`:

| Package | Purpose | Approx. install size |
|---------|---------|----------------------|
| `websockets` | WebSocket server support in FastAPI (via Starlette) | ~500 KB |
| `google-genai` (update) | Live API client support (if not already on latest version) | — |

No other dependencies are required. Browser-side audio is handled by native Web APIs (`MediaRecorder`, `AudioContext`, `WebSocket`) — no JavaScript libraries needed.

**Concurrency note:** Each active voice WebSocket holds one Live API session open. On a Pi, it is expected that only one or two users interact simultaneously. A configurable `VOICE_MAX_CONCURRENT_SESSIONS` limit (default: `2`) will reject new voice connections beyond this threshold with a `{"event":"error","message":"voice_capacity_exceeded"}` message.

***

## Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| OQ-1 | What happens to Live API session billing during long silences? Should a keepalive or timeout be implemented? | Backend | Open |
| OQ-2 | Should user transcripts (what the farmer said) be displayed in the chat UI for voice turns? | UX | Open |
| OQ-3 | Should voice turns appear in the chat history panel as a distinct visual style (e.g., mic icon)? | UX | Open |
| OQ-4 | What language(s) should be supported at launch? Should language be auto-detected or selected in settings? | Product | Open |
| OQ-5 | When the Live API preview becomes GA, what is the migration plan? | Backend | Open |

***

## Acceptance Criteria

| ID | Criteria |
|----|----------|
| AC-V1 | A user can tap the mic button, speak a question in English, and receive an accurate spoken answer |
| AC-V2 | A user can ask a voice question about sensor data and the correct TimescaleDB result is spoken back |
| AC-V3 | A user can switch from voice to text in the same session and the model retains full conversation context |
| AC-V4 | If `VOICE_ENABLED=false`, the mic button is hidden and text chat is unaffected |
| AC-V5 | A voice turn that triggers a tool call completes successfully end-to-end |
| AC-V6 | If the WebSocket drops mid-turn, the UI recovers gracefully without a page reload |
| AC-V7 | Two simultaneous voice sessions can be active without degrading text mode response times |
| AC-V8 | Voice turns are written to session history and visible in text mode context |