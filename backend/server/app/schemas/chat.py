"""
FarmShield Chat — Pydantic Schemas (Phase 8a).

Matches PRD §8 exactly.
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /chat/message."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    """Response body for POST /chat/message."""
    reply: str
    session_id: str
    sources: list[str]
    ts: int


class SessionClearResponse(BaseModel):
    """Response body for DELETE /chat/session/{session_id}."""
    session_id: str
    cleared: bool
