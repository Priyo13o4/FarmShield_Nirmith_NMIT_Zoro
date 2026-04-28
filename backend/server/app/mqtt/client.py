"""
FarmShield Backend — MQTT Client Instance.

Creates the FastMQTT singleton from settings.
No handlers here — those live in mqtt/handlers.py.
Exported as `fast_mqtt` for use in main.py lifespan.
"""

from fastapi_mqtt import FastMQTT, MQTTConfig

from app.config import settings

mqtt_config = MQTTConfig(
    host=settings.mqtt_broker_host,
    port=settings.mqtt_broker_port,
    username=settings.mqtt_username,
    password=settings.mqtt_password,
    will_message_topic=f"{settings.mqtt_topic_sensors}/status",
    will_message_payload="offline",
    will_delay_interval=2,
)

fast_mqtt = FastMQTT(config=mqtt_config)
