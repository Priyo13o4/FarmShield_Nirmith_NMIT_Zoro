"""
0002_sensor_readings_unique_time_device — Deduplication constraint.

Adds a UNIQUE index on sensor_readings(time, device_id).

Without this, the hypertable accepts duplicate (time, device_id) rows —
TimescaleDB does not enforce uniqueness by default. This was discovered
in QA: the same MQTT message published twice resulted in two rows with
identical (time, device_id) but different sensor values, making
get_latest() non-deterministic.

The UNIQUE index allows ingestion.py to use
INSERT ... ON CONFLICT (time, device_id) DO NOTHING
so exact retransmissions are safely deduplicated and logged as warnings,
not silently stored or failed.

Note: TimescaleDB requires that any UNIQUE index on a hypertable must
include the partition column (time). This constraint satisfies that requirement.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create unique index — includes the hypertable partition column (time)
    op.execute(
        "CREATE UNIQUE INDEX uq_sensor_readings_time_device "
        "ON sensor_readings (time, device_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sensor_readings_time_device")
