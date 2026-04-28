"""
FarmShield Chat — Session Store.

In-memory store keyed by session_id. Stores LangChain message objects so they
can be passed directly to the agent as chat_history. Uses asyncio.Lock to be
safe from concurrent FastAPI coroutines.

Exported singleton: session_store (created at import time, zero cost when
CHAT_ENABLED=false because this file is never imported in that case).
"""

import asyncio

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from app.config import settings

logger = structlog.get_logger(__name__)


class SessionStore:
    """Thread-safe in-memory store mapping session_id → list of LangChain messages."""

    def __init__(self, max_history: int) -> None:
        self._store: dict[str, list] = {}
        self._max_history = max_history
        self._lock = asyncio.Lock()

    async def get_history(self, session_id: str) -> list:
        """Return a copy of the history list for session_id (empty if new)."""
        async with self._lock:
            return list(self._store.get(session_id, []))

    async def append(self, session_id: str, human: str, assistant: str) -> None:
        """Append a human/assistant exchange and trim to max_history pairs."""
        async with self._lock:
            history = self._store.setdefault(session_id, [])
            history.append(HumanMessage(content=human))
            history.append(AIMessage(content=assistant))
            # Each exchange = 2 messages; trim from the front
            max_msgs = self._max_history * 2
            if len(history) > max_msgs:
                self._store[session_id] = history[-max_msgs:]
                logger.debug(
                    "session_history_trimmed",
                    session_id=session_id,
                    kept=max_msgs,
                )

    async def clear(self, session_id: str) -> bool:
        """Delete history for session_id. Returns True if it existed, False if not."""
        async with self._lock:
            if session_id not in self._store:
                return False
            del self._store[session_id]
            logger.info("session_cleared", session_id=session_id)
            return True


# Module-level singleton — cheap to create, only imported when CHAT_ENABLED=true
session_store = SessionStore(max_history=settings.chat_max_history)
