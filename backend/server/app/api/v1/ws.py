"""
FarmShield Backend — WebSocket Endpoint.

WS /ws/live?api_key=<key> — live sensor stream.
Auth is passed as a query parameter since WebSocket clients cannot
set Authorization headers.
"""

import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.websocket import ws_manager

router = APIRouter(tags=["websocket"])

logger = structlog.get_logger(__name__)


@router.websocket("/ws/live")
async def websocket_live(
    websocket: WebSocket,
    api_key: str = Query(default=""),
):
    """
    Live sensor data stream over WebSocket.

    Server pushes sensor_reading and alert messages.
    Client can send {"type": "ping"} to keep alive; server responds with {"type": "pong"}.
    """
    # Auth check via query param
    if settings.auth_enabled:
        if api_key != settings.api_key:
            await websocket.close(code=1008, reason="Invalid or missing API key")
            return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Listen for client messages (ping/pong keep-alive)
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                logger.debug("ws_invalid_json_from_client", raw=raw[:100])
    except WebSocketDisconnect:
        # Client disconnected — not an error per PRD §20.8
        ws_manager.disconnect(websocket)
    except Exception:
        # Any other error — disconnect gracefully
        ws_manager.disconnect(websocket)
