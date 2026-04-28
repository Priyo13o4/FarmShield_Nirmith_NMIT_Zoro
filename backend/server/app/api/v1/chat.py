"""
FarmShield Chat — API Route Handlers (Phase 8b).

Three endpoints:
  POST   /chat/message              — synchronous invoke
  GET    /chat/stream               — SSE streaming (auth via query param api_key)
  DELETE /chat/session/{session_id} — clear history

Minor fix (from verification): No per-handler `chat_enabled` guard.
The router is only registered when CHAT_ENABLED=true (see router.py).
Adding a redundant guard here would be dead code.

Error 4 fix: SSE generator checks "done" key in stream() yield dicts to extract sources.
"""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.dependencies import require_auth
from app.schemas.chat import ChatRequest, ChatResponse, SessionClearResponse
from app.services.chat.agent import farm_agent
from app.services.chat.session_store import session_store

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(require_auth)],
)


@router.post("/message", response_model=ChatResponse)
async def chat_message(body: ChatRequest) -> ChatResponse:
    """
    Send a message to the FarmShield AI assistant and receive a complete response.

    Maintains conversation context across requests using session_id.
    Session history is stored in memory (resets on server restart).
    """
    logger.info(
        "chat_message_received",
        session_id=body.session_id,
        msg_len=len(body.message),
    )
    result = await farm_agent.invoke(body.message, body.session_id)
    return ChatResponse(**result)


@router.get("/stream")
async def chat_stream(
    message: str,
    session_id: str,
    api_key: str | None = None,
) -> StreamingResponse:
    """
    Stream a response from the FarmShield AI assistant via Server-Sent Events.

    Uses api_key query parameter for auth (same pattern as WebSocket endpoints).
    Each SSE event is a JSON object:
      - {"token": "..."} — partial response token
      - {"done": true, "sources": [...], "session_id": "...", "ts": int} — terminal event

    Connect with: curl -N "http://host/api/v1/chat/stream?message=...&session_id=..."
    """
    if not message or not session_id:
        raise HTTPException(status_code=422, detail="message and session_id are required")

    logger.info("chat_stream_begin", session_id=session_id, msg_len=len(message))

    async def event_generator():
        async for item in farm_agent.stream(message, session_id):
            if "done" in item:
                # Terminal event — includes sources (Error 4 fix)
                yield f"data: {json.dumps(item)}\n\n"
            else:
                # Regular token event
                yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering for SSE
        },
    )


@router.delete("/session/{session_id}", response_model=SessionClearResponse)
async def clear_session(session_id: str) -> SessionClearResponse:
    """
    Clear the conversation history for a session.

    Returns 404 if session_id does not exist (never sent a message).
    """
    cleared = await session_store.clear(session_id)
    if not cleared:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Session not found.", "type": "NOT_FOUND"},
        )
    return SessionClearResponse(session_id=session_id, cleared=True)
