"""
FarmShield Backend — Health Endpoint.

Always public — never guarded by auth (PRD §10.1).
Always returns 200 as long as the process is alive (PRD §20.7).
Reports actual state of MQTT and DB connections in the body.
"""

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal

router = APIRouter(tags=["health"])

logger = structlog.get_logger(__name__)

# MQTT client injected at startup
_mqtt_client = None

# Chat ready flag — set to True by main.py after farm_agent.load() completes
_chat_ready = False


def set_mqtt_client(client) -> None:
    """Called once during app startup to inject the MQTT client."""
    global _mqtt_client
    _mqtt_client = client


def set_chat_ready(ready: bool) -> None:
    """Called once during app startup after chat feature finishes loading."""
    global _chat_ready
    _chat_ready = ready


@router.get("/health")
async def health():
    """
    Liveness check.

    Always returns 200. The mqtt_connected and db_connected fields
    report actual state — they do not cause a non-200 response.
    """
    # Check DB connectivity
    db_connected = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_connected = True
    except Exception as e:
        logger.warning("health_db_check_failed", error=str(e))

    # Check MQTT connectivity
    mqtt_connected = False
    if _mqtt_client is not None:
        try:
            mqtt_connected = _mqtt_client.client.is_connected
        except AttributeError:
            # Defensive: gmqtt API may differ across versions
            logger.warning("health_mqtt_attribute_error")
            mqtt_connected = False

    response = {
        "status": "ok",
        "mqtt_connected": mqtt_connected,
        "db_connected": db_connected,
        "ml_enabled": settings.ml_enabled,
        "version": "1.0.0",
    }
    if settings.chat_enabled:
        response["chat_enabled"] = True
        response["chat_ready"] = _chat_ready
    return response
