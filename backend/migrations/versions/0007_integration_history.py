"""Add append-only audit, document and survey metadata without rewriting existing rows."""
from alembic import context, op
import sqlalchemy as sa

revision = "0007_integration_history"
down_revision = "0006_nullable_interval_volume"
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    if context.is_offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names() and column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _add_column(table_name, column):
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _ensure_index(name, table_name, columns):
    if context.is_offline_mode():
        op.create_index(name, table_name, columns)
        return
    inspector = sa.inspect(op.get_bind())
    if name not in {index["name"] for index in inspector.get_indexes(table_name)}:
        op.create_index(name, table_name, columns)


def _ensure_table(name, *columns, **kwargs):
    if context.is_offline_mode():
        op.create_table(name, *columns, **kwargs)
        return
    if name not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(name, *columns, **kwargs)


def upgrade():
    _add_column("outorgas", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column("hydrometers", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column("managed_documents", sa.Column("sha256", sa.String(64)))
    _add_column("managed_documents", sa.Column("extracted_text", sa.Text()))
    _add_column("managed_documents", sa.Column("reviewed_fields", sa.JSON()))
    _ensure_table("record_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False), sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False), sa.Column("previous_values", sa.JSON(), nullable=False),
        sa.Column("new_values", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    _ensure_index("ix_record_revisions_property_id", "record_revisions", ["property_id"])
    _ensure_table("stage_volume_curves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservoir_id", sa.Integer(), sa.ForeignKey("reservoirs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("survey_date", sa.Date(), nullable=False), sa.Column("survey_source", sa.String(255), nullable=False),
        sa.Column("survey_responsible", sa.String(160), nullable=False), sa.Column("level_unit", sa.String(8), nullable=False),
        sa.Column("volume_unit", sa.String(8), nullable=False), sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    _ensure_index("ix_stage_volume_curves_reservoir_id", "stage_volume_curves", ["reservoir_id"])
    _ensure_table("alert_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False))
    _ensure_index("ix_alert_evaluations_property_id", "alert_evaluations", ["property_id"])
    _ensure_table("normalized_telemetry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("component_type", sa.String(32), nullable=False), sa.Column("component_id", sa.Integer(), nullable=False),
        sa.Column("variable", sa.String(32), nullable=False), sa.Column("value", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False), sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False), sa.Column("origin_id", sa.String(120), nullable=False),
        sa.Column("out_of_order", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("property_id", "component_type", "component_id", "source", "origin_id", name="uq_normalized_telemetry_origin"))
    _ensure_index("ix_normalized_telemetry_property_id", "normalized_telemetry", ["property_id"])
    _ensure_table("monthly_balances", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservoir_id", sa.Integer(), sa.ForeignKey("reservoirs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False), sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    _ensure_index("ix_monthly_balances_reservoir_id", "monthly_balances", ["reservoir_id"])
    _ensure_table("totalizer_events", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hydrometer_id", sa.Integer(), sa.ForeignKey("hydrometers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    _ensure_index("ix_totalizer_events_hydrometer_id", "totalizer_events", ["hydrometer_id"])


def downgrade():
    raise RuntimeError("Reversão bloqueada: preserve histórico e documentos antes de qualquer migração manual.")
