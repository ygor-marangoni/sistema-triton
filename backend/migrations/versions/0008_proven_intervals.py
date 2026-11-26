"""Persist interval evidence, audited permit links and approved curve validity."""
from alembic import context, op
import sqlalchemy as sa


revision = "0008_proven_intervals"
down_revision = "0007_integration_history"
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


def _has_constraint(table_name, name):
    if context.is_offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(item.get("name") == name for item in inspector.get_check_constraints(table_name))


def _ensure_table(name, *columns, **kwargs):
    if context.is_offline_mode():
        op.create_table(name, *columns, **kwargs)
        return
    if name not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(name, *columns, **kwargs)


def _ensure_index(name, table_name, columns):
    if context.is_offline_mode():
        op.create_index(name, table_name, columns)
        return
    inspector = sa.inspect(op.get_bind())
    if name not in {index["name"] for index in inspector.get_indexes(table_name)}:
        op.create_index(name, table_name, columns)


def upgrade():
    _add_column("monthly_balances", sa.Column("calculation_mode", sa.String(20), server_default="declarado", nullable=False))

    _add_column("hydrometer_readings", sa.Column("interval_start_at", sa.DateTime(timezone=True), nullable=True))

    _add_column("meteorological_observations", sa.Column("interval_start_at", sa.DateTime(timezone=True), nullable=True))
    _add_column("meteorological_observations", sa.Column("reference", sa.String(255), nullable=True))
    _add_column("meteorological_observations", sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    _add_column("meteorological_observations", sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    _add_column("meteorological_observations", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    _add_column("stage_volume_curves", sa.Column("valid_from", sa.Date(), nullable=True))
    _add_column("stage_volume_curves", sa.Column("valid_until", sa.Date(), nullable=True))
    _add_column("stage_volume_curves", sa.Column("is_approved", sa.Boolean(), server_default=sa.false(), nullable=False))
    _add_column("stage_volume_curves", sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    _add_column("stage_volume_curves", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    if not _has_constraint("stage_volume_curves", "ck_stage_curve_validity"):
        op.create_check_constraint(
            "ck_stage_curve_validity",
            "stage_volume_curves",
            "(valid_from IS NULL AND valid_until IS NULL) OR (valid_from IS NOT NULL AND valid_until IS NOT NULL AND valid_until >= valid_from)",
        )
    if not _has_constraint("stage_volume_curves", "ck_stage_curve_approval"):
        op.create_check_constraint(
            "ck_stage_curve_approval",
            "stage_volume_curves",
            "NOT is_approved OR (valid_from IS NOT NULL AND valid_until IS NOT NULL AND approved_by_id IS NOT NULL AND approved_at IS NOT NULL)",
        )

    _ensure_table(
        "hydrometer_outorga_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hydrometer_id", sa.Integer(), sa.ForeignKey("hydrometers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("outorga_id", sa.Integer(), sa.ForeignKey("outorgas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("valid_from_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outorga_valid_from_snapshot", sa.Date(), nullable=False),
        sa.Column("outorga_valid_until_snapshot", sa.Date(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("hydrometer_id", "valid_from_at", name="uq_hydrometer_outorga_link_start"),
        sa.CheckConstraint("valid_until_at IS NULL OR valid_until_at > valid_from_at", name="ck_hydrometer_outorga_link_period"),
    )
    _ensure_index("ix_hydrometer_outorga_links_property_id", "hydrometer_outorga_links", ["property_id"])
    _ensure_index("ix_hydrometer_outorga_links_hydrometer_id", "hydrometer_outorga_links", ["hydrometer_id"])
    _ensure_index("ix_hydrometer_outorga_links_outorga_id", "hydrometer_outorga_links", ["outorga_id"])
    _ensure_index("ix_hydrometer_outorga_link_period", "hydrometer_outorga_links", ["hydrometer_id", "valid_from_at", "valid_until_at"])

    _ensure_table(
        "balance_flow_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservoir_id", sa.Integer(), sa.ForeignKey("reservoirs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False, server_default="other_outflow"),
        sa.Column("value_m3", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False, server_default="m3"),
        sa.Column("period_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("quality", sa.String(40), nullable=False, server_default="pendente de revisao"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("value_m3 >= 0", name="ck_balance_flow_evidence_value"),
        sa.CheckConstraint("period_end_at > period_start_at", name="ck_balance_flow_evidence_period"),
    )
    _ensure_index("ix_balance_flow_evidence_reservoir_id", "balance_flow_evidence", ["reservoir_id"])
    _ensure_index("ix_balance_flow_reservoir_period", "balance_flow_evidence", ["reservoir_id", "period_start_at", "period_end_at"])


def downgrade():
    raise RuntimeError("Reversao bloqueada: remova apenas apos exportar e preservar os registros de proveniencia.")
