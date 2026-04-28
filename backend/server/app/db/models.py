"""
FarmShield Backend — ORM Models.

Maps to the TimescaleDB schema defined in PRD §9.
Hypertable creation and indexes are handled in Alembic migrations,
not by SQLAlchemy's create_all().

Note on primary keys:
  - sensor_readings: composite (time, device_id) in ORM only — no PK constraint
    in DDL since TimescaleDB hypertables require the partition column in any unique index.
  - ml_inferences: same pattern as sensor_readings.
  - alerts: standard UUID PK with gen_random_uuid() default.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, Integer, SmallInteger, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SensorReading(Base):
    """Raw sensor telemetry from ESP32 — stored in a TimescaleDB hypertable."""

    __tablename__ = "sensor_readings"

    # Composite ORM identity key (no actual PK constraint in DDL)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False, default="farmshield_node1"
        # default matches DEVICE_ID constant in ESP32 firmware
    )

    # Sensor fields — all nullable to tolerate individual sensor failures
    soil_pct: Mapped[float | None] = mapped_column(Double, nullable=True)
    ph: Mapped[float | None] = mapped_column(Double, nullable=True)
    tds_ppm: Mapped[float | None] = mapped_column(Double, nullable=True)
    temp_c: Mapped[float | None] = mapped_column(Double, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Double, nullable=True)
    rain_raw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motion: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    npk_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    npk_p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    npk_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    npk_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # Modbus read success flag
    leaf_r: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    leaf_g: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    leaf_b: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Pump state — always reported
    pump_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Firmware state fields (added in migration 0003)
    mode: Mapped[str | None] = mapped_column(Text, nullable=True)       # "AUTO" or "MANUAL"
    uptime_s: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds since last ESP32 boot


class Alert(Base):
    """Generated alerts based on threshold breaches."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MLInference(Base):
    """ML inference results — one row per prediction run."""

    __tablename__ = "ml_inferences"

    # UUID primary key (for audio and future ML features)
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )

    # Composite ORM identity key (hypertable, no DDL PK)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    device_id: Mapped[str] = mapped_column(Text, nullable=False)

    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    input_features: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    inference_ms: Mapped[float | None] = mapped_column(Double, nullable=True)

    # Audio pest detection fields (added in migration 0005)
    prediction: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

