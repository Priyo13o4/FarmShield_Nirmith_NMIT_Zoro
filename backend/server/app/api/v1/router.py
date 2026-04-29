"""
FarmShield Backend — Router Aggregation.

Includes all sub-routers under the /api/v1 prefix.
Chat router is conditionally registered when CHAT_ENABLED=true — it is the
single guard for the feature. No per-handler chat_enabled checks needed.
"""

from fastapi import APIRouter

from app.api.v1 import alerts, control, health, sensors, ws
from app.config import settings

router = APIRouter(prefix="/api/v1")

# Health is included directly (no prefix beyond /api/v1)
router.include_router(health.router)

# Resource routers
router.include_router(sensors.router)
router.include_router(control.router)
router.include_router(alerts.router)

# WebSocket
router.include_router(ws.router)

# Dev overrides
from app.api.v1 import dev
router.include_router(dev.router)

# Chat — conditionally registered (Phase 8c)
# router.py is imported after Settings() is instantiated, so this works.
if settings.chat_enabled:
    from app.api.v1 import chat, voice  # noqa: E402
    router.include_router(chat.router)
    router.include_router(voice.router)
# Audio Pest Detection — conditionally registered
if settings.audio_enabled:
    from app.api.v1 import audio  # noqa: E402 — conditional import is intentional
    router.include_router(audio.router)

