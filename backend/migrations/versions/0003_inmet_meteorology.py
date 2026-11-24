"""Link meteorological records and collection runs to property/station.

Revision ID: 0003_inmet_meteorology
Revises: 0002_alert_workflow
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_inmet_meteorology"
down_revision = "0002_alert_workflow"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name):
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "meteorological_stations"):
        op.create_table(
            "meteorological_stations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(40), nullable=False, server_default="INMET"),
            sa.Column("station_code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("city", sa.String(100), nullable=True),
            sa.Column("state", sa.String(2), nullable=True),
            sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("property_id", "source", "station_code", name="uq_weather_property_source_station"),
        )
        op.create_index("ix_weather_property_active", "meteorological_stations", ["property_id", "is_active"])

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "meteorological_observations"):
        raise RuntimeError("Tabela meteorological_observations ausente; aplique as migrações anteriores primeiro")
    weather_columns = {item["name"] for item in inspector.get_columns("meteorological_observations")}
    value_type = next(item["type"] for item in inspector.get_columns("meteorological_observations") if item["name"] == "value")
    value_needs_widening = getattr(value_type, "precision", None) != 20 or getattr(value_type, "scale", None) != 8
    weather_unique = {item.get("name"): set(item.get("column_names") or []) for item in inspector.get_unique_constraints("meteorological_observations")}
    has_new_unique = {"property_id", "station_id", "variable", "observed_at"} in weather_unique.values()
    has_old_unique = {"source", "station_code", "variable", "observed_at"} in weather_unique.values()
    weather_changes = "property_id" not in weather_columns or "station_id" not in weather_columns or "quality" not in weather_columns or has_old_unique or not has_new_unique or value_needs_widening
    if weather_changes:
        with op.batch_alter_table("meteorological_observations", recreate="always" if bind.dialect.name == "sqlite" else "auto") as batch:
            if "property_id" not in weather_columns:
                batch.add_column(sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=True))
            if "station_id" not in weather_columns:
                batch.add_column(sa.Column("station_id", sa.Integer(), sa.ForeignKey("meteorological_stations.id", ondelete="SET NULL"), nullable=True))
            if "quality" not in weather_columns:
                batch.add_column(sa.Column("quality", sa.String(80), nullable=False, server_default="raw_unvalidated"))
            if value_needs_widening:
                batch.alter_column("value", existing_type=value_type, type_=sa.Numeric(20, 8), existing_nullable=False)
            if has_old_unique:
                old_name = next(name for name, cols in weather_unique.items() if cols == {"source", "station_code", "variable", "observed_at"})
                if old_name:
                    batch.drop_constraint(old_name, type_="unique")
            if not has_new_unique:
                batch.create_unique_constraint("uq_weather_property_station_observation", ["property_id", "station_id", "variable", "observed_at"])

    inspector = sa.inspect(bind)
    weather_indexes = {item["name"] for item in inspector.get_indexes("meteorological_observations")}
    for column_name in ("property_id", "station_id"):
        index_name = f"ix_meteorological_observations_{column_name}"
        if column_name in {item["name"] for item in inspector.get_columns("meteorological_observations")} and index_name not in weather_indexes:
            op.create_index(index_name, "meteorological_observations", [column_name])

    inspector = sa.inspect(bind)
    run_columns = {item["name"] for item in inspector.get_columns("collection_runs")}
    if "requested_year" not in run_columns:
        op.add_column("collection_runs", sa.Column("requested_year", sa.Integer(), nullable=True))
    if "property_id" not in run_columns:
        op.add_column("collection_runs", sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=True))
    if "station_id" not in run_columns:
        op.add_column("collection_runs", sa.Column("station_id", sa.Integer(), sa.ForeignKey("meteorological_stations.id", ondelete="SET NULL"), nullable=True))
    run_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("collection_runs")}
    for column_name in ("property_id", "station_id"):
        index_name = f"ix_collection_runs_{column_name}"
        if index_name not in run_indexes:
            op.create_index(index_name, "collection_runs", [column_name])


def downgrade():
    # Keep station/readings linkage intact. Dropping it would orphan newly collected
    # observations or risk deleting pre-existing meteorological data.
    pass
