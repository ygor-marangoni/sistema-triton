"""Archive properties without deleting history and retain tariff source evidence."""
from alembic import context, op
import sqlalchemy as sa


revision = "0009_property_archive_tariff_source"
down_revision = "0008_proven_intervals"
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


def upgrade():
    # Alembic creates version_num as VARCHAR(32), but this revision ID has
    # more than 32 characters. Widen before Alembic records the new revision;
    # PostgreSQL TEXT preserves every existing value without a new length cap.
    if op.get_context().dialect.name == "postgresql":
        op.alter_column("alembic_version", "version_num", existing_type=sa.String(32), type_=sa.Text(), existing_nullable=False)

    _add_column("properties", sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False))
    _add_column("properties", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    _add_column("energy_tariffs", sa.Column("source_reference", sa.String(500), nullable=True))
    _add_column("energy_tariffs", sa.Column("source_details", sa.JSON(), nullable=True))
    _add_column("energy_tariffs", sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    indexes = set() if context.is_offline_mode() else {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("energy_tariffs")
    }
    if context.is_offline_mode() or "ix_energy_tariffs_created_by_id" not in indexes:
        op.create_index("ix_energy_tariffs_created_by_id", "energy_tariffs", ["created_by_id"])


def downgrade():
    raise RuntimeError("Reversão bloqueada para preservar o estado de arquivamento e a proveniência tarifária.")
