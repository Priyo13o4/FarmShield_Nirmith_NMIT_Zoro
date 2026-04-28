"""
FarmShield Backend — MQTT Topic Handlers.

on_connect: subscribe to the sensor topic.
on_message: parse JSON, call ingestion.process().

No direct DB access — all writes go through services.
"""

import json

import structlog

from app.config import settings
from app.mqtt.client import fast_mqtt
from app.services import ingestion

logger = structlog.get_logger(__name__)


@fast_mqtt.on_connect()
def on_connect(client, flags, rc, properties):
    """Subscribe to the sensor topic on successful MQTT connection."""
    fast_mqtt.client.subscribe(
        settings.mqtt_topic_sensors,
        qos=settings.mqtt_qos,
    )
    logger.info(
        "mqtt_connected",
        topic=settings.mqtt_topic_sensors,
        qos=settings.mqtt_qos,
        rc=rc,
    )


@fast_mqtt.on_message()
async def on_message(client, topic, payload, qos, properties):
    """
    Handle incoming MQTT messages on subscribed topics.

    Parses raw bytes to dict and delegates to the ingestion pipeline.
    """
    if topic != settings.mqtt_topic_sensors:
        logger.debug("mqtt_unhandled_topic", topic=topic)
        return

    try:
        raw = payload.decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error(
            "mqtt_payload_parse_failed",
            topic=topic,
            error=str(e),
            raw_preview=str(payload[:200]) if payload else "empty",
        )
        return

    logger.debug("mqtt_message_received", topic=topic, device_id=data.get("device_id"))

    await ingestion.process(data)


@fast_mqtt.on_disconnect()
def on_disconnect(client, packet, exc=None):
    """Log MQTT disconnections."""
    logger.warning("mqtt_disconnected", exc=str(exc) if exc else None)


# ── Audio pest detection handler ─────────────────────────────────────────────
from app.services import audio_inference as _audio_inference  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

if settings.audio_enabled:

    @fast_mqtt.on_connect()
    def on_audio_connect(client, flags, rc, properties):
        """Subscribe to the audio topic on successful MQTT connection."""
        fast_mqtt.client.subscribe(
            settings.audio_mqtt_topic,
            qos=settings.mqtt_qos,
        )
        logger.info(
            "mqtt_audio_subscribed",
            topic=settings.audio_mqtt_topic,
            qos=settings.mqtt_qos,
        )

    @fast_mqtt.on_message()
    async def on_audio_message(client, topic, payload, qos, properties):
        if topic != settings.audio_mqtt_topic:
            return
        try:
            raw = json.loads(payload.decode("utf-8"))
            async with AsyncSessionLocal() as db:
                await _audio_inference.process_audio(raw, db)
        except Exception as exc:
            logger.error("audio_handler_error", error=str(exc), exc_info=True)

