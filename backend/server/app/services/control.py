"""
FarmShield Backend — Control Dispatch Service.

Publishes MQTT commands to per-subtopic control channels.
No DB writes for commands — fire-and-forget per PRD.

The firmware listens on three separate subtopics and expects raw string
payloads (not JSON). Each function publishes directly to the correct
subtopic with the state string as the payload.
"""

import time

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# The mqtt_client singleton is set at startup by main.py lifespan.
# This avoids circular imports (mqtt/client.py imports config, not services).
_mqtt_client = None


def set_mqtt_client(client) -> None:
    """Called once during app startup to inject the MQTT client."""
    global _mqtt_client
    _mqtt_client = client


async def _publish_control(command: str, state: str, topic: str) -> dict:
    """
    Publish a raw string control command to a specific MQTT subtopic.

    The firmware expects raw strings (e.g. "ON", "OFF", "AUTO", "MANUAL"),
    not JSON. Payload is passed as a plain string.

    Raises RuntimeError if MQTT client is not available.
    """
    if _mqtt_client is None:
        logger.error("mqtt_client_not_set", command=command, state=state)
        raise RuntimeError("MQTT client not initialized")

    ts = int(time.time())

    try:
        _mqtt_client.publish(
            topic,
            state,       # raw string — not json.dumps(). Firmware uses equalsIgnoreCase().
            qos=settings.mqtt_qos,
        )
        published = True
        logger.info(
            "control_command_published",
            command=command,
            state=state,
            topic=topic,
        )
    except Exception as e:
        published = False
        logger.error(
            "control_publish_failed",
            command=command,
            state=state,
            topic=topic,
            error=str(e),
            exc_info=True,
        )
        raise

    return {
        "command": command,
        "state": state,
        "published": published,
        "ts": ts,
    }


async def send_pump_command(state: str) -> dict:
    """Publish pump ON/OFF to farmshield/control/pump as a raw string."""
    return await _publish_control("pump", state, settings.mqtt_topic_control_pump)


async def send_mode_command(state: str) -> dict:
    """Publish mode AUTO/MANUAL to farmshield/control/mode as a raw string."""
    return await _publish_control("mode", state, settings.mqtt_topic_control_mode)


async def send_buzzer_command(state: str) -> dict:
    """Publish buzzer OFF to farmshield/control/buzzer as a raw string."""
    return await _publish_control("buzzer", state, settings.mqtt_topic_control_buzzer)
