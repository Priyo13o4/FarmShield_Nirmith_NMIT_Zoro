"""
0004_readonly_user — Create read-only PostgreSQL user for chatbot SQL tool.

The chatbot's query_sensor_data tool connects as farmshield_readonly, which
has SELECT-only access to sensor_readings and alerts. It cannot read
ml_inferences or alembic_version, and cannot write to any table.

Password is read from env var to stay in sync with CHAT_DB_READONLY_PASSWORD
in .env. The CREATE USER statement is idempotent (EXCEPTION WHEN duplicate_object).
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    password = os.environ.get("CHAT_DB_READONLY_PASSWORD", "readonly123")

    # Idempotent user creation — safe to run multiple times
    op.execute(
        "DO $$ BEGIN "
        f"CREATE USER farmshield_readonly WITH PASSWORD '{password}'; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute("GRANT CONNECT ON DATABASE farmshield TO farmshield_readonly;")
    op.execute("GRANT USAGE ON SCHEMA public TO farmshield_readonly;")
    op.execute("GRANT SELECT ON sensor_readings TO farmshield_readonly;")
    op.execute("GRANT SELECT ON alerts TO farmshield_readonly;")
    # ml_inferences and alembic_version are intentionally not granted.
    # PostgreSQL denies access by default — no explicit REVOKE needed.


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON sensor_readings FROM farmshield_readonly;")
    op.execute("REVOKE ALL PRIVILEGES ON alerts FROM farmshield_readonly;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM farmshield_readonly;")
    op.execute("REVOKE CONNECT ON DATABASE farmshield FROM farmshield_readonly;")
    op.execute("DROP USER IF EXISTS farmshield_readonly;")
