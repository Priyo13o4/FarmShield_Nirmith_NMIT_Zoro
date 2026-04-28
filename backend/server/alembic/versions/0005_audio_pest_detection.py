"""
0005_audio_pest_detection — Schema changes for audio pest detection.

Adds:
  - id (UUID PK) column to ml_inferences
  - prediction (Text) column to ml_inferences
  - confidence (Double) column to ml_inferences
  - raw_output (Text) column to ml_inferences
  - Makes input_features and output nullable (audio uses prediction/confidence instead)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add UUID primary key
    op.add_column(
        "ml_inferences",
        sa.Column("id", UUID(as_uuid=True), nullable=True, server_default=sa.text("gen_random_uuid()")),
    )
    # Backfill existing rows (if any) with UUIDs
    op.execute("UPDATE ml_inferences SET id = gen_random_uuid() WHERE id IS NULL")

    # Add audio-specific columns
    op.add_column("ml_inferences", sa.Column("prediction", sa.Text(), nullable=True))
    op.add_column("ml_inferences", sa.Column("confidence", sa.Double(), nullable=True))
    op.add_column("ml_inferences", sa.Column("raw_output", sa.Text(), nullable=True))

    # Make input_features and output nullable (audio doesn't use them)
    op.alter_column("ml_inferences", "input_features", existing_type=sa.dialects.postgresql.JSONB(), nullable=True)
    op.alter_column("ml_inferences", "output", existing_type=sa.dialects.postgresql.JSONB(), nullable=True)


def downgrade() -> None:
    op.drop_column("ml_inferences", "raw_output")
    op.drop_column("ml_inferences", "confidence")
    op.drop_column("ml_inferences", "prediction")
    op.drop_column("ml_inferences", "id")
    op.alter_column("ml_inferences", "input_features", existing_type=sa.dialects.postgresql.JSONB(), nullable=False)
    op.alter_column("ml_inferences", "output", existing_type=sa.dialects.postgresql.JSONB(), nullable=False)
