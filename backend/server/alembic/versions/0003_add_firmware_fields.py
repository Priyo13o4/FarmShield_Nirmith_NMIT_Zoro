"""
0003_add_firmware_fields — Add mode, uptime_s, npk_ok columns to sensor_readings.

These fields are published by the ESP32 firmware and were not in the original schema:
  - mode: "AUTO" or "MANUAL" — firmware operating mode at time of reading
  - uptime_s: seconds since last ESP32 boot — useful for detecting reboots
  - npk_ok: whether the Modbus NPK sensor read succeeded (null = read not attempted)

All three are nullable — existing rows default to NULL without data migration.
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sensor_readings", sa.Column("mode", sa.Text(), nullable=True))
    op.add_column("sensor_readings", sa.Column("uptime_s", sa.Integer(), nullable=True))
    op.add_column("sensor_readings", sa.Column("npk_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("sensor_readings", "npk_ok")
    op.drop_column("sensor_readings", "uptime_s")
    op.drop_column("sensor_readings", "mode")
