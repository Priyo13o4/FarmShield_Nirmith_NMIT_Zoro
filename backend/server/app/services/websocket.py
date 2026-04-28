"""
FarmShield Backend — WebSocket Connection Manager.

Maintains a set of active WebSocket connections.
Broadcasts sensor readings and alerts to all connected clients.

Disconnects are NOT errors (PRD §20.8) — handled gracefully with no
exception propagation.
"""

import json

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self._active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.info(
            "ws_client_connected",
            total_connections=len(self._active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection. Safe to call even if already removed."""
        self._active_connections.discard(websocket)
        logger.info(
            "ws_client_disconnected",
            total_connections=len(self._active_connections),
        )

    async def broadcast(self, data: dict) -> None:
        """
        Send JSON data to all connected clients.

        Disconnected clients are removed silently — disconnects are not errors.
        """
        if not self._active_connections:
            return

        message = json.dumps(data, default=str)
        stale: list[WebSocket] = []

        for connection in self._active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Client disconnected — not an error per PRD §20.8
                stale.append(connection)

        for connection in stale:
            self._active_connections.discard(connection)

        if stale:
            logger.debug(
                "ws_stale_connections_removed",
                removed=len(stale),
                remaining=len(self._active_connections),
            )

    @property
    def connection_count(self) -> int:
        """Number of currently active WebSocket connections."""
        return len(self._active_connections)


# Singleton instance — imported by ingestion service and WS route
ws_manager = ConnectionManager()
