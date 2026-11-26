"""Restore interval checks omitted when tables were created by 0001 models."""
from alembic import context, op
import sqlalchemy as sa

revision = "0010_period_constraints"
down_revision = "0009_property_archive_tariff_source"
branch_labels = None
depends_on = None


def upgrade():
    for table, name, condition in (
        ("hydrometer_outorga_links", "ck_hydrometer_outorga_link_period", "valid_until_at IS NULL OR valid_until_at > valid_from_at"),
        ("balance_flow_evidence", "ck_balance_flow_evidence_period", "period_end_at > period_start_at"),
    ):
        if context.is_offline_mode():
            # Offline SQL may follow a revision that already created the check.
            op.execute(f"""DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = current_schema() AND t.relname = '{table}' AND c.conname = '{name}'
                ) THEN
                    ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({condition});
                END IF;
            END $$""")
        else:
            checks = sa.inspect(op.get_bind()).get_check_constraints(table)
            if not any(check.get("name") == name for check in checks):
                # Existing invalid rows cause the transaction to fail; none are rewritten.
                op.create_check_constraint(name, table, condition)


def downgrade():
    raise RuntimeError("Reversão bloqueada para preservar as validações de período.")
