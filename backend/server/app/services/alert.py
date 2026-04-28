"""
FarmShield Backend — Alert Service.

Alert CRUD + threshold evaluation.
Threshold logic is a pure function — no DB or MQTT concerns in evaluate_thresholds().
"""

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Alert
from app.schemas.sensor import SensorReadingOut

logger = structlog.get_logger(__name__)

# MQTT client injected at startup (same pattern as control.py)
_mqtt_client = None


def set_mqtt_client(client) -> None:
    """Called once during app startup to inject the MQTT client."""
    global _mqtt_client
    _mqtt_client = client


def evaluate_thresholds(reading: SensorReadingOut) -> list[dict]:
    """
    Evaluate alert thresholds against a sensor reading.

    Returns a list of alert dicts (may be empty). Each dict has:
      - type: str (e.g. "SOIL_DRY")
      - severity: str (INFO / WARNING / CRITICAL)
      - message: str
    """
    alerts: list[dict] = []

    if reading.soil_pct is not None and reading.soil_pct < settings.alert_soil_dry_pct:
        alerts.append({
            "type": "SOIL_DRY",
            "severity": "WARNING",
            "message": (
                f"Soil moisture below threshold "
                f"({reading.soil_pct}% < {settings.alert_soil_dry_pct}%)"
            ),
        })

    if reading.soil_pct is not None and reading.soil_pct > settings.alert_soil_flood_pct:
        alerts.append({
            "type": "SOIL_FLOOD",
            "severity": "WARNING",
            "message": (
                f"Soil moisture above flood threshold "
                f"({reading.soil_pct}% > {settings.alert_soil_flood_pct}%)"
            ),
        })

    if reading.temp_c is not None and reading.temp_c > settings.alert_temp_high_c:
        alerts.append({
            "type": "TEMP_HIGH",
            "severity": "WARNING",
            "message": (
                f"Temperature above threshold "
                f"({reading.temp_c}°C > {settings.alert_temp_high_c}°C)"
            ),
        })

    if reading.ph is not None and reading.ph < settings.alert_ph_low:
        alerts.append({
            "type": "PH_LOW",
            "severity": "WARNING",
            "message": (
                f"pH below threshold "
                f"({reading.ph} < {settings.alert_ph_low})"
            ),
        })

    if reading.ph is not None and reading.ph > settings.alert_ph_high:
        alerts.append({
            "type": "PH_HIGH",
            "severity": "WARNING",
            "message": (
                f"pH above threshold "
                f"({reading.ph} > {settings.alert_ph_high})"
            ),
        })

    if reading.tds_ppm is not None and reading.tds_ppm > settings.alert_tds_high_ppm:
        alerts.append({
            "type": "TDS_HIGH",
            "severity": "WARNING",
            "message": (
                f"TDS above threshold "
                f"({reading.tds_ppm} ppm > {settings.alert_tds_high_ppm} ppm)"
            ),
        })

    if reading.rain_raw is not None and reading.rain_raw > settings.alert_rain_dry_raw:
        alerts.append({
            "type": "RAIN_DRY",
            "severity": "INFO",
            "message": (
                f"Rain sensor indicates dry conditions "
                f"(raw {reading.rain_raw} > {settings.alert_rain_dry_raw})"
            ),
        })

    return alerts


async def create_alert(
    db: AsyncSession,
    device_id: str,
    alert_type: str,
    severity: str,
    message: str,
) -> Alert:
    """
    Persist an alert to the DB and publish it to the MQTT alerts topic.

    Returns the created Alert ORM instance.
    """
    alert = Alert(
        id=uuid.uuid4(),
        time=datetime.now(timezone.utc),
        device_id=device_id,
        type=alert_type,
        severity=severity,
        message=message,
        acknowledged=False,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    logger.info(
        "alert_created",
        alert_id=str(alert.id),
        device_id=device_id,
        type=alert_type,
        severity=severity,
    )

    # Publish to MQTT alerts topic
    if _mqtt_client is not None:
        try:
            mqtt_payload = json.dumps({
                "alert_id": str(alert.id),
                "type": alert_type,
                "severity": severity,
                "message": message,
                "ts": int(alert.time.timestamp()),
            })
            _mqtt_client.publish(
                settings.mqtt_topic_alerts,
                mqtt_payload,
                qos=settings.mqtt_qos,
            )
        except Exception as e:
            logger.error(
                "alert_mqtt_publish_failed",
                alert_id=str(alert.id),
                error=str(e),
                exc_info=True,
            )

    return alert


async def get_alerts(
    db: AsyncSession,
    device_id: str,
    limit: int = 50,
    unacknowledged_only: bool = False,
) -> list[Alert]:
    """Fetch recent alerts for a device, optionally filtered to unacknowledged only."""
    stmt = (
        select(Alert)
        .where(Alert.device_id == device_id)
    )
    if unacknowledged_only:
        stmt = stmt.where(Alert.acknowledged == False)  # noqa: E712

    stmt = stmt.order_by(Alert.time.desc()).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def acknowledge_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> Alert | None:
    """Mark an alert as acknowledged. Returns None if alert not found."""
    stmt = (
        update(Alert)
        .where(Alert.id == alert_id)
        .values(acknowledged=True)
        .returning(Alert)
    )
    result = await db.execute(stmt)
    await db.commit()
    alert = result.scalar_one_or_none()

    if alert is not None:
        logger.info("alert_acknowledged", alert_id=str(alert_id))
    else:
        logger.warning("alert_not_found_for_acknowledge", alert_id=str(alert_id))

    return alert
