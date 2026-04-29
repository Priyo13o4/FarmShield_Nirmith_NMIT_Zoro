"""
FarmShield Backend — MQTT Ingestion Pipeline.

The hottest path in the system (PRD §7.1 / §7.2):
  1. Validate payload with SensorPayload
  2. Convert ts (Unix epoch) → TIMESTAMPTZ
  3. Write SensorReading to DB
  4. Optionally run ML inference
  5. Broadcast to WebSocket clients
  6. Evaluate alert thresholds → create alerts if breached

This service manages its own DB session lifecycle because it is called
from the MQTT handler, not from a FastAPI route handler. The PRD §20.3
note about Depends(get_db) applies only to HTTP routes. This is documented
here to avoid confusion.
"""

from datetime import datetime, timezone
from pathlib import Path

import structlog
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db.models import MLInference, SensorReading
from app.db.session import AsyncSessionLocal
from app.schemas.sensor import SensorPayload, SensorReadingOut
from app.services import alert as alert_service
from app.services.websocket import ws_manager

logger = structlog.get_logger(__name__)

# ML runner — conditionally loaded at startup (see main.py lifespan)
_ml_runner = None


def set_ml_runner(runner) -> None:
    """Called once during app startup when ML_ENABLED=true."""
    global _ml_runner
    _ml_runner = runner


async def process(raw_payload: dict) -> None:
    """
    Process a single MQTT sensor payload end-to-end.

    This is the main ingestion entry point called by mqtt/handlers.py.
    """
    # ── Step 1: Validate ────────────────────────────────────────────────
    try:
        payload = SensorPayload(**raw_payload)
    except ValidationError as e:
        logger.error(
            "ingestion_validation_failed",
            errors=e.errors(),
            raw_keys=list(raw_payload.keys()),
        )
        return

    # ── Step 1.5: NPK override hook ─────────────────────────────────────
    if settings.npk_override_enabled:
        from app.services.dev.npk_override import npk_override
        payload.npk_n, payload.npk_p, payload.npk_k, payload.npk_ok = \
            npk_override.apply(payload.npk_n, payload.npk_p, payload.npk_k, payload.npk_ok)

    # ── Step 2: Convert timestamp ───────────────────────────────────────
    if payload.ts is not None:
        try:
            reading_time = datetime.fromtimestamp(payload.ts, tz=timezone.utc)
        except (ValueError, OSError, OverflowError) as e:
            logger.warning(
                "ingestion_ts_unparseable",
                ts=payload.ts,
                error=str(e),
                fallback="NOW()",
            )
            reading_time = datetime.now(timezone.utc)
    else:
        logger.warning(
            "ingestion_ts_missing",
            device_id=payload.device_id,
            fallback="NOW()",
        )
        reading_time = datetime.now(timezone.utc)

    # ── Step 3: Write to DB (INSERT ... ON CONFLICT DO NOTHING) ────────
    # The UNIQUE index on (time, device_id) means exact retransmissions
    # from the ESP32 (same ts, same device) are deduplicated here.
    # A skipped insert is logged as WARNING — not silently dropped,
    # not treated as an error.
    row_values = {
        "time": reading_time,
        "device_id": payload.device_id,
        "soil_pct": payload.soil_pct,
        "tds_ppm": payload.tds_ppm,
        "temp_c": payload.temp_c,
        "humidity_pct": payload.humidity_pct,
        "rain_raw": payload.rain_raw,
        "motion": payload.motion,
        "npk_n": payload.npk_n,
        "npk_p": payload.npk_p,
        "npk_k": payload.npk_k,
        "npk_ok": payload.npk_ok,       # Modbus read success flag from firmware
        "leaf_r": payload.leaf_r,
        "leaf_g": payload.leaf_g,
        "leaf_b": payload.leaf_b,
        "pump_on": payload.pump_on,
        "mode": payload.mode,           # "AUTO" or "MANUAL" from firmware
        "uptime_s": payload.uptime_s,   # seconds since last ESP32 boot
    }

    stmt = (
        pg_insert(SensorReading)
        .values(**row_values)
        .on_conflict_do_nothing(index_elements=["time", "device_id"])
    )

    inserted = False
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(stmt)
            await db.commit()
            inserted = result.rowcount > 0
    except Exception as e:
        logger.error(
            "ingestion_db_write_failed",
            device_id=payload.device_id,
            error=str(e),
            exc_info=True,
        )
        return

    if not inserted:
        logger.warning(
            "ingestion_duplicate_skipped",
            device_id=payload.device_id,
            ts=int(reading_time.timestamp()),
            note="Same (time, device_id) already exists — MQTT retransmit or clock collision",
        )
        return  # Do not broadcast or alert for a duplicate

    logger.info(
        "reading_ingested",
        device_id=payload.device_id,
        ts=int(reading_time.timestamp()),
    )

    # Reconstruct ORM-like object for downstream use (WS broadcast, alerts)
    db_row = SensorReading(**row_values)

    # ── Step 4: ML inference (conditional) ──────────────────────────────
    ml_output = None
    if settings.ml_enabled and _ml_runner is not None:
        # Build feature dict — exclude None values
        features = {
            k: v
            for k, v in {
                "soil_pct": payload.soil_pct,
                "tds_ppm": payload.tds_ppm,
                "temp_c": payload.temp_c,
                "humidity_pct": payload.humidity_pct,
                "rain_raw": float(payload.rain_raw) if payload.rain_raw is not None else None,
                "npk_n": float(payload.npk_n) if payload.npk_n is not None else None,
                "npk_p": float(payload.npk_p) if payload.npk_p is not None else None,
                "npk_k": float(payload.npk_k) if payload.npk_k is not None else None,
                "leaf_r": float(payload.leaf_r) if payload.leaf_r is not None else None,
                "leaf_g": float(payload.leaf_g) if payload.leaf_g is not None else None,
                "leaf_b": float(payload.leaf_b) if payload.leaf_b is not None else None,
            }.items()
            if v is not None
        }

        import time

        start = time.monotonic()
        ml_output = _ml_runner.predict(features)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Persist inference
        try:
            async with AsyncSessionLocal() as db:
                inference = MLInference(
                    time=reading_time,
                    device_id=payload.device_id,
                    model_name=Path(settings.ml_model_path).stem,
                    input_features=features,
                    output=ml_output,
                    inference_ms=elapsed_ms,
                )
                db.add(inference)
                await db.commit()
        except Exception as e:
            logger.error(
                "ingestion_ml_write_failed",
                device_id=payload.device_id,
                error=str(e),
                exc_info=True,
            )

    # ── Step 5: WebSocket broadcast ─────────────────────────────────────
    reading_out = SensorReadingOut.model_validate(db_row)
    ws_message: dict = {
        "type": "sensor_reading",
        "data": reading_out.model_dump(mode="json"),
    }
    if ml_output is not None:
        ws_message["ml_output"] = ml_output

    await ws_manager.broadcast(ws_message)

    # ── Step 6: Alert evaluation ────────────────────────────────────────
    alert_defs = alert_service.evaluate_thresholds(reading_out)
    for alert_def in alert_defs:
        try:
            async with AsyncSessionLocal() as db:
                alert = await alert_service.create_alert(
                    db=db,
                    device_id=payload.device_id,
                    alert_type=alert_def["type"],
                    severity=alert_def["severity"],
                    message=alert_def["message"],
                )
                # Broadcast alert over WebSocket
                from app.schemas.alert import AlertOut

                alert_out = AlertOut.model_validate(alert)
                await ws_manager.broadcast({
                    "type": "alert",
                    "data": alert_out.model_dump(mode="json"),
                })
        except Exception as e:
            logger.error(
                "ingestion_alert_creation_failed",
                device_id=payload.device_id,
                alert_type=alert_def["type"],
                error=str(e),
                exc_info=True,
            )
