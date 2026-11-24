"""Add explicit, optional geographic coordinates to properties.

Revision ID: 0005_property_map_coordinates
Revises: 0004_ruler_image_review
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_property_map_coordinates"
down_revision = "0004_ruler_image_review"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("properties")}
    if "latitude" not in columns:
        op.add_column("properties", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    if "longitude" not in columns:
        op.add_column("properties", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))


def downgrade():
    # Preserve user-entered property locations if a downgrade is requested.
    pass
