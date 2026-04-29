"""
0001_initial — Baseline schema migration.

Creates:
  - TimescaleDB extension (if not present)
  - sensor_readings hypertable
  - alerts table with UUID PK and severity CHECK constraint
  - ml_inferences hypertable (always created, even when ML_ENABLED=false)
  - Indexes per PRD §9
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Ensure TimescaleDB extension is available ───────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ── sensor_readings ─────────────────────────────────────────────────
    op.create_table(
        "sensor_readings",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False, server_default="esp32-node-1"),
        sa.Column("soil_pct", sa.Double(), nullable=True),

        sa.Column("tds_ppm", sa.Double(), nullable=True),
        sa.Column("temp_c", sa.Double(), nullable=True),
        sa.Column("humidity_pct", sa.Double(), nullable=True),
        sa.Column("rain_raw", sa.Integer(), nullable=True),
        sa.Column("motion", sa.Boolean(), nullable=True),
        sa.Column("npk_n", sa.Integer(), nullable=True),
        sa.Column("npk_p", sa.Integer(), nullable=True),
        sa.Column("npk_k", sa.Integer(), nullable=True),
        sa.Column("leaf_r", sa.SmallInteger(), nullable=True),
        sa.Column("leaf_g", sa.SmallInteger(), nullable=True),
        sa.Column("leaf_b", sa.SmallInteger(), nullable=True),
        sa.Column("pump_on", sa.Boolean(), nullable=False, server_default="false"),
        # No PRIMARY KEY — TimescaleDB hypertable manages partitioning on 'time'
    )

    op.execute("SELECT create_hypertable('sensor_readings', 'time')")
    op.execute("CREATE INDEX ix_sensor_readings_device_time ON sensor_readings (device_id, time DESC)")

    # ── alerts ──────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_alerts_severity"),
    )

    op.execute("CREATE INDEX ix_alerts_device_time ON alerts (device_id, time DESC)")

    # ── ml_inferences (always created — empty table has zero cost) ─────
    op.create_table(
        "ml_inferences",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("input_features", JSONB(), nullable=False),
        sa.Column("output", JSONB(), nullable=False),
        sa.Column("inference_ms", sa.Double(), nullable=True),
        # No PRIMARY KEY — hypertable
    )

    op.execute("SELECT create_hypertable('ml_inferences', 'time')")


def downgrade() -> None:
    op.drop_table("ml_inferences")
    op.drop_table("alerts")
    op.drop_table("sensor_readings")
