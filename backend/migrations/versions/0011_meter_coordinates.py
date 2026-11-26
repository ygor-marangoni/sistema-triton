"""Preserve existing meters while enabling optional mapped coordinates."""
from alembic import context, op
import sqlalchemy as sa

revision = "0011_meter_coordinates"
down_revision = "0010_period_constraints"
branch_labels = None
depends_on = None


def upgrade():
    columns = set() if context.is_offline_mode() else {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("hydrometers")
    }
    for name in ("latitude", "longitude"):
        if name not in columns:
            op.add_column("hydrometers", sa.Column(name, sa.Numeric(9, 6), nullable=True))


def downgrade():
    raise RuntimeError("Reversão bloqueada para preservar coordenadas cadastradas.")
