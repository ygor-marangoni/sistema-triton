"""Add alert fingerprints, contextual details and resolution actor.

Revision ID: 0002_alert_workflow
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_alert_workflow"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("alerts")}

    if "fingerprint" not in columns:
        op.add_column("alerts", sa.Column("fingerprint", sa.String(length=220), nullable=True))
        op.execute(sa.text("UPDATE alerts SET fingerprint = 'legacy:' || id WHERE fingerprint IS NULL"))
        op.alter_column("alerts", "fingerprint", existing_type=sa.String(length=220), nullable=False)

    if "details" not in columns:
        op.add_column("alerts", sa.Column("details", sa.JSON(), nullable=True))
        op.execute(sa.text("UPDATE alerts SET details = '{}' WHERE details IS NULL"))
        op.alter_column("alerts", "details", existing_type=sa.JSON(), nullable=False, server_default=sa.text("'{}'"))

    if "resolved_at" not in columns:
        op.add_column("alerts", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))

    if "resolved_by_id" not in columns:
        op.add_column("alerts", sa.Column("resolved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    inspector = sa.inspect(bind)
    has_fingerprint_unique = any(set(item.get("column_names") or []) == {"fingerprint"} for item in inspector.get_unique_constraints("alerts"))
    if not has_fingerprint_unique:
        op.create_unique_constraint("uq_alert_fingerprint", "alerts", ["fingerprint"])


def downgrade():
    op.drop_constraint("uq_alert_fingerprint", "alerts", type_="unique")
    op.drop_column("alerts", "resolved_by_id")
    op.drop_column("alerts", "resolved_at")
    op.drop_column("alerts", "details")
    op.drop_column("alerts", "fingerprint")
