"""Persist private ruler images and human review history.

Revision ID: 0004_ruler_image_review
Revises: 0003_inmet_meteorology
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_ruler_image_review"
down_revision = "0003_inmet_meteorology"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "level_image_reviews" not in tables:
        op.create_table(
            "level_image_reviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
            sa.Column("station_id", sa.Integer(), sa.ForeignKey("level_stations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("storage_key", sa.String(80), nullable=False, unique=True),
            sa.Column("original_name", sa.String(180), nullable=False),
            sa.Column("content_type", sa.String(40), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("width_px", sa.Integer(), nullable=False),
            sa.Column("height_px", sa.Integer(), nullable=False),
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("unit", sa.String(8), nullable=False, server_default="m"),
            sa.Column("status", sa.String(24), nullable=False, server_default="inconclusive"),
            sa.Column("method", sa.String(80), nullable=False),
            sa.Column("suggested_level_m", sa.Numeric(8, 3), nullable=True),
            sa.Column("confirmed_level_m", sa.Numeric(8, 3), nullable=True),
            sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
            sa.Column("inconclusive_reason", sa.Text(), nullable=True),
            sa.Column("analysis_details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("calibration", sa.JSON(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('inconclusive', 'pending_review', 'confirmed')", name="ck_level_image_review_status"),
            sa.CheckConstraint("size_bytes > 0 AND width_px > 0 AND height_px > 0", name="ck_level_image_review_file_dimensions"),
        )
        op.create_index("ix_level_image_reviews_property_id", "level_image_reviews", ["property_id"])
        op.create_index("ix_level_image_reviews_station_id", "level_image_reviews", ["station_id"])
        op.create_index("ix_level_image_review_station_captured", "level_image_reviews", ["station_id", "captured_at"])

    inspector = sa.inspect(bind)
    if "level_image_review_revisions" not in inspector.get_table_names():
        op.create_table(
            "level_image_review_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("review_id", sa.Integer(), sa.ForeignKey("level_image_reviews.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("previous_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("corrected_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_level_image_review_revisions_review_id", "level_image_review_revisions", ["review_id"])

    inspector = sa.inspect(bind)
    reading_columns = {item["name"] for item in inspector.get_columns("level_readings")}
    reading_uniques = [set(item.get("column_names") or []) for item in inspector.get_unique_constraints("level_readings")]
    if "image_review_id" not in reading_columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("level_readings", recreate="always") as batch:
                batch.add_column(sa.Column("image_review_id", sa.Integer(), sa.ForeignKey("level_image_reviews.id", ondelete="SET NULL"), nullable=True))
                batch.create_unique_constraint("uq_level_reading_image_review", ["image_review_id"])
        else:
            op.add_column("level_readings", sa.Column("image_review_id", sa.Integer(), sa.ForeignKey("level_image_reviews.id", ondelete="SET NULL"), nullable=True))
            op.create_unique_constraint("uq_level_reading_image_review", "level_readings", ["image_review_id"])
    elif {"image_review_id"} not in reading_uniques:
        op.create_unique_constraint("uq_level_reading_image_review", "level_readings", ["image_review_id"])


def downgrade():
    # Keep uploaded evidence, confirmed readings, and their revision trail intact.
    pass
