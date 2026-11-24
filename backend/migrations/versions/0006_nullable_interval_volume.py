"""Allow unavailable totalizer intervals to remain unknown.

Revision ID: 0006_nullable_interval_volume
Revises: 0005_property_map_coordinates
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_nullable_interval_volume"
down_revision = "0005_property_map_coordinates"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("hydrometer_readings", "volume_m3", existing_type=sa.Numeric(14, 3), nullable=True)


def downgrade():
    # Do not silently replace unknown intervals with zero.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM hydrometer_readings WHERE volume_m3 IS NULL LIMIT 1")).first():
        raise RuntimeError("Existem volumes desconhecidos; resolva-os antes de reverter esta migração.")
    op.alter_column("hydrometer_readings", "volume_m3", existing_type=sa.Numeric(14, 3), nullable=False)
