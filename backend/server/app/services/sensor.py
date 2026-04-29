"""
FarmShield Backend — Sensor Query Service.

Pure data-access functions. No HTTP or MQTT concerns.
"""

import csv
import io
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SensorReading

logger = structlog.get_logger(__name__)


async def get_latest(
    db: AsyncSession,
    device_id: str,
) -> SensorReading | None:
    """Return the most recent sensor reading for a device."""
    stmt = (
        select(SensorReading)
        .where(SensorReading.device_id == device_id)
        .order_by(SensorReading.time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_history(
    db: AsyncSession,
    device_id: str,
    hours: int = 24,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[SensorReading], int]:
    """
    Return paginated historical readings within a lookback window.

    Returns:
        Tuple of (readings list, total count within the window).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Count total within window
    count_stmt = (
        select(func.count())
        .select_from(SensorReading)
        .where(
            SensorReading.device_id == device_id,
            SensorReading.time >= cutoff,
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Fetch paginated data
    data_stmt = (
        select(SensorReading)
        .where(
            SensorReading.device_id == device_id,
            SensorReading.time >= cutoff,
        )
        .order_by(SensorReading.time.desc())
        .limit(limit)
        .offset(offset)
    )
    data_result = await db.execute(data_stmt)
    readings = list(data_result.scalars().all())

    logger.debug(
        "sensor_history_query",
        device_id=device_id,
        hours=hours,
        total=total,
        returned=len(readings),
    )

    return readings, total


async def export_csv_data(
    db: AsyncSession,
    device_id: str,
    hours: int = 24,
    limit: int = 500,
    offset: int = 0,
) -> str:
    """
    Export sensor readings as a CSV string.

    Returns:
        CSV-formatted string with headers.
    """
    readings, _ = await get_history(db, device_id, hours, limit, offset)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "time", "device_id", "soil_pct", "tds_ppm", "temp_c",
        "humidity_pct", "rain_raw", "motion", "npk_n", "npk_p", "npk_k",
        "leaf_r", "leaf_g", "leaf_b", "pump_on",
    ])

    for r in readings:
        writer.writerow([
            r.time.isoformat(), r.device_id, r.soil_pct, r.tds_ppm,
            r.temp_c, r.humidity_pct, r.rain_raw, r.motion, r.npk_n,
            r.npk_p, r.npk_k, r.leaf_r, r.leaf_g, r.leaf_b, r.pump_on,
        ])

    return output.getvalue()
